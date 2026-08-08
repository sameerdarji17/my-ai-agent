from django.contrib import admin
from .models import Conversation, Message, ToolCallLog


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "created_at", "updated_at"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "conversation", "role", "created_at"]
    list_filter = ["role"]


@admin.register(ToolCallLog)
class ToolCallLogAdmin(admin.ModelAdmin):
    list_display = ["id", "conversation", "tool_name", "succeeded", "duration_ms", "created_at"]
    list_filter = ["tool_name", "succeeded"]
