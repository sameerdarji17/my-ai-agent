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
You are "SD AGENT", an advanced, intelligent, and highly capable AI assistant and companion developed by SD AGENT.

CRITICAL IDENTITY RULES:
1. When asked about your name, who you are, or who built/created you, ALWAYS clearly state that your name is "SD AGENT" and you are developed by SD AGENT.
2. NEVER mention or identify yourself as Google, Google AI, Gemini, Claude, Anthropic, OpenAI, or ChatGPT under any circumstances.
3. Your brand identity is 100% "SD AGENT".

CRITICAL RESPONSE RULES:
1. NEVER display raw function code, JSON objects, internal tool structures, or tags like '<function/web_search ...>' or '<function=...>' in your final conversational response.
2. Tool execution must happen silently in the backend. Once you retrieve tool results, synthesize the information and respond in clear, clean, natural language.
3. Provide real, accurate, and comprehensive answers in clean plain text.
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

    def _get_active_model(self):
        """Dynamically fetches an available Gemini model that supports generateContent."""
        try:
            available_models = [
                m.name for m in genai.list_models()
                if 'generateContent' in m.supported_generation_methods
            ]

            # Prefer flash or pro models if available
            for target in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
                for full_name in available_models:
                    if target in full_name:
                        return full_name

            # Fallback to any supported model
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

        if not self.api_key:
            reply_text = "Error: GEMINI_API_KEY is not set in Railway environment variables."
            Message.objects.create(conversation=self.conversation, role="assistant", content=reply_text)
            return {"reply": reply_text, "tool_trace": []}

        try:
            genai.configure(api_key=self.api_key)

            # Get exact valid model string from account
            selected_model_name = self._get_active_model()

            model = genai.GenerativeModel(
                model_name=selected_model_name,
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
                    reply_text = "Aapke request ke anusar jankari mil gayi hai."

            Message.objects.create(
                conversation=self.conversation,
                role="assistant",
                content=reply_text
            )

            return {"reply": reply_text, "tool_trace": []}

        except Exception as e:
            logger.error(f"Error in AgentOrchestrator: {e}", exc_info=True)
            detailed_error = f"API Error: {str(e)}"
            Message.objects.create(conversation=self.conversation, role="assistant", content=detailed_error)
            return {"reply": detailed_error, "tool_trace": []}