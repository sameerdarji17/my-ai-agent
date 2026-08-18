import os
import re
import time
import json
import logging
from django.conf import settings
from .models import Message

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    GENAI_AVAILABLE = False

SYSTEM_INSTRUCTIONS = """
You are "SD AGENT", a highly intelligent, natural, and versatile AI companion developed by SAMEER DARJI.

CORE CONVERSATIONAL BEHAVIOR:
1. Natural Flow: Chat naturally and politely. Do NOT introduce yourself or announce your creator in every message.
2. Identity Query Rule: ONLY state your name ("SD AGENT") or creator ("SAMEER DARJI") WHEN the user explicitly asks questions like "Who are you?", "What is your name?", or "Who developed/created you?". Otherwise, just answer the user's question directly and smoothly.
3. Strict Identity Protection: NEVER mention or identify as Google, Gemini, OpenAI, ChatGPT, Claude, or any external entity under any circumstances.

DOMAINS & CAPABILITIES:
1. Astrology & Kundali Analysis: You are fully capable of Vedic astrology, Kundali interpretation, Rashi analysis, planet positions (Graha/Dasha), matchmaking, and astrological guidance. When users share birth details (Date, Time, Place), provide insightful and structured astrological readings.
2. Coding, Productivity & General Knowledge: Provide accurate, structured, step-by-step answers across programming, tech, studies, and general queries.
3. Multilingual & Adaptive: Respond naturally in Hindi, Hinglish, English, or Gujarati based on how the user talks.
4. Clean Output: Never output internal tags, function markers, or raw code structures in responses.
"""

class AgentOrchestrator:
    def __init__(self, conversation, is_premium=False, style="normal"):
        self.conversation = conversation
        self.is_premium = is_premium
        self.style = style
        self.api_keys = self._load_api_keys()

    def _load_api_keys(self):
        """Loads single or comma-separated API keys from settings or environment."""
        raw_keys = getattr(settings, "GEMINI_API_KEYS", "") or getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
        keys = [k.strip() for k in str(raw_keys).split(",") if k.strip()]
        return keys

    def _get_history(self):
        history = []
        messages = self.conversation.messages.order_by("created_at")
        for msg in messages:
            role = "user" if msg.role == "user" else "model"
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            history.append({"role": role, "parts": [content]})
        return history

    def _get_active_model_name(self):
        """Prefers 1.5-flash for generous 1500 RPD free quota over low quota 2.5-flash."""
        try:
            available_models = [
                m.name for m in genai.list_models()
                if 'generateContent' in m.supported_generation_methods
            ]

            # 1.5-flash provides the best rate limits for free tier
            for target in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-2.5-flash"]:
                for full_name in available_models:
                    if target in full_name:
                        return full_name

            if available_models:
                return available_models[0]
        except Exception as e:
            logger.warning(f"Could not list models dynamically: {e}")

        return "models/gemini-1.5-flash"

    def run(self, user_message):
        Message.objects.create(
            conversation=self.conversation,
            role="user",
            content=user_message
        )

        if not GENAI_AVAILABLE:
            reply_text = "Error: 'google-generativeai' package is not installed on server."
            Message.objects.create(conversation=self.conversation, role="assistant", content=reply_text)
            return {"reply": reply_text, "tool_trace": []}

        if not self.api_keys:
            reply_text = "Error: GEMINI_API_KEY is not configured in Railway environment variables."
            Message.objects.create(conversation=self.conversation, role="assistant", content=reply_text)
            return {"reply": reply_text, "tool_trace": []}

        reply_text = ""
        last_error = None

        # Rotate across available API keys on rate-limit / quota errors
        for key_index, current_key in enumerate(self.api_keys):
            try:
                genai.configure(api_key=current_key)
                selected_model_name = self._get_active_model_name()

                model = genai.GenerativeModel(
                    model_name=selected_model_name,
                    system_instruction=SYSTEM_INSTRUCTIONS
                )

                history = self._get_history()[:-1]
                chat = model.start_chat(history=history)

                response = chat.send_message(user_message)
                reply_text = response.text or ""

                if "<function" in reply_text:
                    reply_text = re.sub(r'<function/?[^>]+>', '', reply_text).strip()
                    if not reply_text:
                        reply_text = "Here is the information based on your request."

                if reply_text:
                    break

            except Exception as e:
                err_msg = str(e)
                logger.warning(f"API Key [{key_index + 1}/{len(self.api_keys)}] encountered error: {err_msg}")
                last_error = e
                # Check for 429 rate limit or quota issues and retry with next key
                if "429" in err_msg or "quota" in err_msg.lower() or "resourceexhausted" in err_msg.lower():
                    time.sleep(0.5)
                    continue
                else:
                    break

        if not reply_text:
            if last_error and ("429" in str(last_error) or "quota" in str(last_error).lower()):
                reply_text = "⚡ SD AGENT is currently handling high query volume. Please wait a few seconds and send your query again!"
            else:
                reply_text = "Something went wrong while processing your request. Please try again in a moment."

        Message.objects.create(
            conversation=self.conversation,
            role="assistant",
            content=reply_text
        )

        return {"reply": reply_text, "tool_trace": []}