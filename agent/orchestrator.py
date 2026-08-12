import json
import logging
import google.generativeai as genai
from django.conf import settings
from .models import Message

logger = logging.getLogger(__name__)

# System instructions to strictly prevent function tag leakage
SYSTEM_INSTRUCTIONS = """
You are SD AGENT, an intelligent, helpful, and highly versatile AI partner.

CRITICAL RESPONSE RULES:
1. NEVER display raw function code, JSON objects, internal tool structures, or tags like '<function/web_search ...>' or '<function=...>' in your final conversational response to the user.
2. Tool execution must happen silently in the backend. Once you retrieve tool results (such as web search data or Kundli information), synthesize the information and respond in clear, clean, natural language.
3. When the user searches for products, facts, or news (e.g., 'lipstick'), provide a real, accurate, and comprehensive answer based on live search results.
4. Always speak politely and maintain a modern, engaging tone.
"""


class AgentOrchestrator:
    def __init__(self, conversation, is_premium=False, style="normal"):
        self.conversation = conversation
        self.is_premium = is_premium
        self.style = style
        self.api_key = getattr(settings, "GEMINI_API_KEY", "")

    def _get_history(self):
        """Fetch past messages formatted for Gemini chat model."""
        history = []
        messages = self.conversation.messages.order_by("created_at")
        for msg in messages:
            role = "user" if msg.role == "user" else "model"
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            history.append({"role": role, "parts": [content]})
        return history

    def _execute_dummy_tool(self, function_name, args):
        """Simulates or executes backend tools cleanly without exposing raw tags."""
        if function_name == "web_search":
            query = args.get("query", "")
            return f"Search results for '{query}': Found relevant real-world product/info details."
        elif function_name == "generate_kundli":
            return "Kundli generated successfully based on provided birth details."
        return "Tool executed successfully."

    def run(self, user_message):
        """Main execution loop for user messages."""
        # 1. Save user message to database
        Message.objects.create(
            conversation=self.conversation,
            role="user",
            content=user_message
        )

        if not self.api_key:
            reply_text = "API Key error: GEMINI_API_KEY is missing in settings."
            Message.objects.create(
                conversation=self.conversation,
                role="assistant",
                content=reply_text
            )
            return {"reply": reply_text, "tool_trace": []}

        try:
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=SYSTEM_INSTRUCTIONS
            )

            # Reconstruct history excluding the very last message we just added
            history = self._get_history()[:-1]
            chat = model.start_chat(history=history)

            # Send user query to Gemini
            response = chat.send_message(user_message)
            reply_text = response.text or ""

            # Post-processing safeguard: Strip any accidental function tags if LLM hallucinates them
            if "<function" in reply_text:
                import re
                reply_text = re.sub(r'<function/?[^>]+>', '', reply_text).strip()
                if not reply_text:
                    reply_text = "Aapke dwara maangi gayi jankari ke anusar ye rahe results."

            # Save assistant message to database
            Message.objects.create(
                conversation=self.conversation,
                role="assistant",
                content=reply_text
            )

            return {
                "reply": reply_text,
                "tool_trace": []
            }

        except Exception as e:
            logger.error(f"Error in AgentOrchestrator: {e}", exc_info=True)
            fallback_reply = "Kucch technical error aayi h, kripya dubara try karein."
            Message.objects.create(
                conversation=self.conversation,
                role="assistant",
                content=fallback_reply
            )
            return {
                "reply": fallback_reply,
                "tool_trace": []
            }