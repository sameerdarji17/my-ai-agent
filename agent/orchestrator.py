"""
The orchestrator is the "loop" that makes this a genuine agent rather than a
plain chatbot:

    1. Send conversation history + tool definitions to the LLM
    2. If the LLM wants to use a tool -> run it, feed the result back
    3. Repeat until the LLM gives a final text answer (or max_turns hit)

Two providers are supported (set LLM_PROVIDER in .env):
    - "groq"      (default) -- free tier, OpenAI-compatible API, no billing needed
    - "anthropic" -- paid, higher quality, used if you set LLM_PROVIDER=anthropic
"""

import json
import logging
import re
import time

from django.conf import settings

from .models import Message, ToolCallLog
from .tools import TOOL_DEFINITIONS, IMAGE_GEN_TOOL_DEFINITION, run_tool, to_openai_tools, to_anthropic_tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a helpful AI agent with tools: web_search, read_file, list_files, execute_code.\n\n"
    "ACCURACY (applies to EVERY topic — news, astrology, medical, legal, tech, "
    "anything): if your memory could be outdated or wrong, use web_search first. "
    "If asked about an uploaded file, use read_file first — never guess contents. "
    "Answer only from what tools actually returned, never invent facts/sources. "
    "If results are unclear, say so honestly instead of faking confidence. Don't "
    "mention that you searched or cite source names in your visible reply — just "
    "give a clean, natural answer. You have no general vision, but text in "
    "uploaded images is OCR'd for you automatically (e.g. error screenshots) — "
    "read and use it normally. You cannot edit/enhance uploaded images, only "
    "generate new ones from a text prompt.\n\n"
    "Think step by step; use tools when they improve accuracy.\n\n"
    "LANGUAGE: Always reply in the same language AND script the user just used — "
    "Devanagari Hindi in, Devanagari Hindi out; Hinglish (Roman script) in, "
    "Hinglish out; Gujarati in, Gujarati out; English in, English out; any other "
    "language, mirror it too. Match each message as it comes, like a fluent "
    "multilingual speaker naturally switching languages."
)


class AgentOrchestrator:
    def __init__(self, conversation, is_premium=False, style="normal"):
        self.conversation = conversation
        self.provider = settings.LLM_PROVIDER
        self.is_premium = is_premium
        self.style = style

        if self.provider == "anthropic":
            import anthropic
            self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        else:
            # Groq speaks the OpenAI API format
            from openai import OpenAI
            self.client = OpenAI(api_key=settings.GROQ_API_KEY, base_url=settings.GROQ_BASE_URL)

    def _tool_defs(self):
        defs = list(TOOL_DEFINITIONS)
        if self.is_premium:
            defs.append(IMAGE_GEN_TOOL_DEFINITION)
        return defs

    @staticmethod
    def _ensure_image_urls_present(reply_text, tool_trace):
        """
        The model sometimes fails to correctly echo the generated image URL
        in its final reply (e.g. produces broken markdown like ![img]()).
        To guarantee the image always actually shows up, we pull the real
        URL straight from the tool's own output and append it if missing.
        """
        image_urls = []
        for call in tool_trace:
            if call.get("tool") == "generate_image":
                match = re.search(r"https?://\S+", call.get("output", ""))
                if match:
                    image_urls.append(match.group(0).rstrip(").,"))

        if not image_urls:
            return reply_text

        missing = [u for u in image_urls if u not in reply_text]
        if not missing:
            return reply_text
        return (reply_text or "").rstrip() + "\n\n" + "\n".join(missing)

    def _call_groq_with_retry(self, messages, tools, max_attempts=3):
        """
        Retries transient failures (rate limits, malformed tool-call glitches,
        brief timeouts) with a short backoff before giving up. This is what
        keeps momentary Groq hiccups invisible to the user instead of
        surfacing a "technical error" message on every small slowdown.
        """
        delay = 1.5
        for attempt in range(max_attempts):
            try:
                return self.client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=messages,
                    tools=tools,
                    max_tokens=2048,
                    timeout=30,
                )
            except Exception as exc:
                logger.warning("Groq API call failed (attempt %s/%s): %s", attempt + 1, max_attempts, exc)
                if attempt < max_attempts - 1:
                    time.sleep(delay)
                    delay *= 2
        return None

    def _build_system_prompt(self):
        if self.is_premium:
            image_note = (
                "You also have a generate_image tool available — use it whenever "
                "the user asks for an image, picture, drawing, or artwork. After "
                "calling it, just write a short natural sentence like 'Here's your "
                "image!' — don't worry about formatting the URL yourself, it will "
                "be attached automatically."
            )
        else:
            image_note = (
                "You do NOT have an image generation tool available on the Free "
                "plan. If the user asks you to create/draw/generate an image, "
                "politely tell them this needs the Premium plan and suggest they "
                "check /billing/plans/."
            )
        base = SYSTEM_PROMPT + "\n\n" + image_note

        if self.style == "simple":
            base += "\n\nRESPONSE STYLE: Keep answers short and simple — a few sentences, plain language, no unnecessary detail unless the user asks for more."
        elif self.style == "detailed":
            base += "\n\nRESPONSE STYLE: Give thorough, detailed answers — explain reasoning, provide context, and cover edge cases where relevant."

        return base

    # -- helpers -------------------------------------------------------

    def _persist(self, role, content):
        Message.objects.create(conversation=self.conversation, role=role, content=content)

    def _log_tool_call(self, name, tool_input, output, succeeded, duration_ms):
        ToolCallLog.objects.create(
            conversation=self.conversation,
            tool_name=name,
            tool_input=tool_input,
            tool_output=output[:5000],
            succeeded=succeeded,
            duration_ms=duration_ms,
        )

    # -- main entrypoint -------------------------------------------------

    def run(self, user_input: str) -> dict:
        self._persist("user", user_input)
        if self.provider == "anthropic":
            return self._run_anthropic(user_input)
        return self._run_groq(user_input)

    # -- Groq / OpenAI-format loop ----------------------------------------

    def _load_history_openai(self):
        history = [{"role": "system", "content": self._build_system_prompt()}]
        recent_messages = self.conversation.messages.order_by("created_at")
        # Only send the most recent turns to the API — keeps requests under
        # Groq's free-tier tokens-per-minute limit on long conversations.
        recent_messages = list(recent_messages)[-settings.MAX_HISTORY_MESSAGES:]
        for m in recent_messages:
            if m.role == "user":
                history.append({"role": "user", "content": m.content})
            elif m.role == "assistant":
                history.append(m.content)  # stored as full OpenAI-format message dict
            elif m.role == "tool_result":
                history.extend(m.content)  # list of {"role": "tool", ...} dicts
        return history

    def _run_groq(self, user_input: str) -> dict:
        messages = self._load_history_openai()
        tools = to_openai_tools(self._tool_defs())
        tool_trace = []

        for _ in range(settings.MAX_AGENT_TURNS):
            response = self._call_groq_with_retry(messages, tools)
            if response is None:
                friendly = (
                    "Maaf kijiye, is sawal ko process karte waqt server thoda busy tha aur "
                    "kai baar try karne ke baad bhi jawab nahi mil paya. Kripya thodi der "
                    "(1-2 minute) baad dobara try karein."
                )
                self._persist("assistant", {"role": "assistant", "content": friendly})
                return {"reply": friendly, "tool_trace": tool_trace}

            choice = response.choices[0]
            msg = choice.message

            assistant_msg = {
                "role": "assistant",
                "content": msg.content or "",
            }
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ]

            messages.append(assistant_msg)
            self._persist("assistant", assistant_msg)

            if not msg.tool_calls:
                final_text = self._ensure_image_urls_present(msg.content or "", tool_trace)
                return {"reply": final_text, "tool_trace": tool_trace}

            tool_messages = []
            for tc in msg.tool_calls:
                try:
                    tool_input = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    tool_input = {}
                if tool_input is None:
                    tool_input = {}
                output, succeeded, duration_ms = run_tool(tc.function.name, tool_input)
                self._log_tool_call(tc.function.name, tool_input, output, succeeded, duration_ms)
                tool_trace.append({"tool": tc.function.name, "input": tool_input, "output": output})
                tool_messages.append({"role": "tool", "tool_call_id": tc.id, "content": output})

            messages.extend(tool_messages)
            self._persist("tool_result", tool_messages)

        return {
            "reply": "Reached the maximum number of reasoning turns without a final answer.",
            "tool_trace": tool_trace,
        }

    # -- Anthropic-format loop (optional, paid) ----------------------------

    def _load_history_anthropic(self):
        history = []
        recent_messages = list(self.conversation.messages.order_by("created_at"))[-settings.MAX_HISTORY_MESSAGES:]
        for m in recent_messages:
            if m.role == "tool_result":
                continue
            history.append({"role": "user" if m.role == "user" else "assistant", "content": m.content})
        return history

    def _run_anthropic(self, user_input: str) -> dict:
        messages = self._load_history_anthropic()
        tools = to_anthropic_tools(self._tool_defs())
        tool_trace = []

        for _ in range(settings.MAX_AGENT_TURNS):
            try:
                response = self.client.messages.create(
                    model=settings.ANTHROPIC_MODEL,
                    max_tokens=2048,
                    system=self._build_system_prompt(),
                    tools=tools,
                    messages=messages,
                )
            except Exception as exc:
                logger.exception("Anthropic API call failed")
                friendly = (
                    "Maaf kijiye, is sawal ko process karte waqt ek technical error aa gaya. "
                    "Kripya dobara try karein ya sawal thoda alag tarike se poochein."
                )
                self._persist("assistant", [{"type": "text", "text": friendly}])
                return {"reply": friendly, "tool_trace": tool_trace}

            assistant_blocks = []
            for block in response.content:
                if block.type == "text":
                    assistant_blocks.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_blocks.append(
                        {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
                    )

            messages.append({"role": "assistant", "content": assistant_blocks})
            self._persist("assistant", assistant_blocks)

            if response.stop_reason != "tool_use":
                final_text = "".join(b["text"] for b in assistant_blocks if b["type"] == "text")
                final_text = self._ensure_image_urls_present(final_text, tool_trace)
                return {"reply": final_text, "tool_trace": tool_trace}

            tool_result_blocks = []
            for block in assistant_blocks:
                if block["type"] != "tool_use":
                    continue
                output, succeeded, duration_ms = run_tool(block["name"], block["input"])
                self._log_tool_call(block["name"], block["input"], output, succeeded, duration_ms)
                tool_trace.append({"tool": block["name"], "input": block["input"], "output": output})
                tool_result_blocks.append(
                    {"type": "tool_result", "tool_use_id": block["id"], "content": output}
                )

            messages.append({"role": "user", "content": tool_result_blocks})
            self._persist("tool_result", tool_result_blocks)

        return {
            "reply": "Reached the maximum number of reasoning turns without a final answer.",
            "tool_trace": tool_trace,
        }
