import os
import re
import time
import json
import logging
from PIL import Image
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
You are "SD AGENT", an intelligent, versatile, and helpful AI assistant developed by SAMEER DARJI.

IDENTITY & INTRO RULES:
1. When asked "What is your name?", "Who are you?", or "Who made/created you?":
   ALWAYS respond with your full identity: "My name is SD AGENT, and I was developed by SAMEER DARJI."
2. Regular Conversations: In all other greetings (like "Hi", "Hello", "Kaise ho") and everyday queries, do NOT repeat your name or creator. Chat naturally and directly help the user.
3. Strict Restriction: NEVER mention or identify as Google, Gemini, OpenAI, ChatGPT, or Claude.

CORE CAPABILITIES:
1. Vision & Image Understanding: You can deeply analyze images, documents, photos, diagrams, and screenshots provided by the user. Describe, explain, or extract data accurately from images.
2. Astrology & Kundali Analysis: You excel at Vedic astrology, Kundali matching, Graha-Dasha analysis, and Rashi readings with structured insights.
3. Coding & Problem Solving: Provide clean, accurate, and step-by-step logic for programming, tech, and academic tasks.
4. Language: Seamlessly reply in Hindi, Hinglish, English, or Gujarati matching the user's input.
5. Clean Output: Never output raw function markers, tags, or JSON code in user chats.

SHOPPING, PRODUCTS & E-COMMERCE RULES:
1. NEVER say "I cannot browse the internet", "I cannot give links", or "I cannot do live shopping".
2. When a user asks to buy any product, find deals, compare prices, or requests shopping links:
   - Provide genuine buying advice, specifications, and top product recommendations.
   - Automatically generate direct, clickable markdown search links for Amazon India, Flipkart, and Google Shopping.
   - Format exact search query links like this:
     • [Buy on Amazon](https://www.amazon.in/s?k=PRODUCT_QUERY)
     • [Search on Flipkart](https://www.flipkart.com/search?q=PRODUCT_QUERY)
     • [Check Google Shopping](https://www.google.com/search?tbm=shop&q=PRODUCT_QUERY)
   (Replace PRODUCT_QUERY with the exact item name separated by '+').
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
        """Prefers 1.5-flash / 2.0-flash which natively support image & multimodal analysis."""
        try:
            available_models = [
                m.name for m in genai.list_models()
                if 'generateContent' in m.supported_generation_methods
            ]

            for target in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]:
                for full_name in available_models:
                    if target in full_name:
                        return full_name

            if available_models:
                return available_models[0]
        except Exception as e:
            logger.warning(f"Could not list models dynamically: {e}")

        return "models/gemini-1.5-flash"

    def run(self, user_message, image_file=None):
        # Record user message in DB
        display_content = user_message or ""
        if image_file and not display_content:
            display_content = "📷 [Uploaded Image]"

        Message.objects.create(
            conversation=self.conversation,
            role="user",
            content=display_content
        )

        if not GENAI_AVAILABLE:
            reply_text = "Error: 'google-generativeai' package is not installed on server."
            Message.objects.create(conversation=self.conversation, role="assistant", content=reply_text)
            return {"reply": reply_text, "tool_trace": []}

        if not self.api_keys:
            reply_text = "Error: GEMINI_API_KEY is not configured in environment variables."
            Message.objects.create(conversation=self.conversation, role="assistant", content=reply_text)
            return {"reply": reply_text, "tool_trace": []}

        reply_text = ""
        last_error = None

        # Load image with PIL if provided
        pil_image = None
        if image_file:
            try:
                pil_image = Image.open(image_file)
            except Exception as img_err:
                logger.error(f"Error reading uploaded image: {img_err}")

        # Rotate across available API keys on rate-limit / quota errors
        for key_index, current_key in enumerate(self.api_keys):
            try:
                genai.configure(api_key=current_key)
                selected_model_name = self._get_active_model_name()

                model = genai.GenerativeModel(
                    model_name=selected_model_name,
                    system_instruction=SYSTEM_INSTRUCTIONS
                )

                # Multimodal prompt construction
                prompt_parts = []
                if pil_image:
                    prompt_parts.append(pil_image)
                if user_message:
                    prompt_parts.append(user_message)
                elif pil_image:
                    prompt_parts.append("Explain or describe what is in this image in detail.")

                # If image is attached, generate content directly; otherwise use chat session
                if pil_image:
                    response = model.generate_content(prompt_parts)
                else:
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