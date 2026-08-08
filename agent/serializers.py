from rest_framework import serializers
from .models import Conversation, Message, ToolCallLog


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "created_at"]


class ToolCallLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ToolCallLog
        fields = ["id", "tool_name", "tool_input", "tool_output", "succeeded", "duration_ms", "created_at"]


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = ["id", "title", "created_at", "updated_at", "messages"]


class ChatRequestSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    message = serializers.CharField(allow_blank=False)
    style = serializers.ChoiceField(choices=["normal", "simple", "detailed"], required=False, default="normal")
