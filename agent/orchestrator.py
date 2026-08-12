import json
import logging
from django.conf import settings
from .models import Message

logger = logging.getLogger(__name__)

# Safe import for Google Generative AI
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    GENAI_AVAILABLE = False

SYSTEM_INSTRUCTIONS = """
You are SD AGENT, an intelligent, helpful, and highly versatile AI partner.

CRITICAL RESPONSE RULES:
1. NEVER display raw function code, JSON objects, internal tool structures, or tags like '<function/web_search ...>' or '<function=...>' in your final conversational response to the user.
2. Tool execution must happen silently in the backend. Once you retrieve tool results, synthesize the information and respond in clear, clean, natural language.
3. Provide real, accurate, and comprehensive answers.
"""


class AgentOrchestrator:
    def __init__(self, conversation, is_premium=False, style="normal"):
        self.conversation = conversation
        self.is_premium = is_premium
        self.style = style
        self.api_key = getattr(settings, "GEMINI_API_KEY", "")

    def _get_history(self):
        history = []
        messages = self.conversation.messages.order_by("created_at")
        for msg in messages:
            role = "user" if msg.role == "user" else "model"
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            history.append({"role": role, "parts": [content]})
        return history

    def run(self, user_message):
        Message.objects.create(
            conversation=self.conversation,
            role="user",
            content=user_message
        )

        if not GENAI_AVAILABLE:
            reply_text = "Server configuration error: 'google-generativeai' package is not installed."
            Message.objects.create(conversation=self.conversation, role="assistant", content=reply_text)
            return {"reply": reply_text, "tool_trace": []}

        if not self.api_key:
            reply_text = "API Key error: GEMINI_API_KEY is missing in settings."
            Message.objects.create(conversation=self.conversation, role="assistant", content=reply_text)
            return {"reply": reply_text, "tool_trace": []}

        try:
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=SYSTEM_INSTRUCTIONS
            )

            history = self._get_history()[:-1]
            chat = model.start_chat(history=history)

            response = chat.send_message(user_message)
            reply_text = response.text or ""

            if "<function" in reply_text:
                import re
                reply_text = re.sub(r'<function/?[^>]+>', '', reply_text).strip()
                if not reply_text:
                    reply_text = "Aapke request ke mutabiq jankari nikal li gayi hai."

            Message.objects.create(
                conversation=self.conversation,
                role="assistant",
                content=reply_text
            )

            return {"reply": reply_text, "tool_trace": []}

        except Exception as e:
            logger.error(f"Error in AgentOrchestrator: {e}", exc_info=True)
            fallback_reply = "Kucch technical error aayi h, kripya dubara try karein."
            Message.objects.create(conversation=self.conversation, role="assistant", content=fallback_reply)
            return {"reply": fallback_reply, "tool_trace": []}