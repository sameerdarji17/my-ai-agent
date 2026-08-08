import uuid
from django.conf import settings
from django.db import models


class Conversation(models.Model):
    """One chat thread. Everything the agent 'remembers' hangs off this."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="conversations"
    )
    session_key = models.CharField(max_length=64, blank=True, default="", db_index=True)
    is_shared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conversation {self.id} ({self.title or 'untitled'})"


class Message(models.Model):
    """
    A single turn in the conversation. `role` is one of:
      - "user"       : what the human typed
      - "assistant"  : what the model said (may include tool_use blocks)
      - "tool_result": the output returned by executing a tool
    `content` stores the raw structured content (string or JSON-serialisable
    list of content blocks) so the full Anthropic message format can be
    reconstructed when re-sending history to the API.
    """

    ROLE_CHOICES = [
        ("user", "user"),
        ("assistant", "assistant"),
        ("tool_result", "tool_result"),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.role}] {str(self.content)[:60]}"


class ToolCallLog(models.Model):
    """Audit trail: every tool invocation the agent made, for debugging/cost tracking."""

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="tool_calls")
    tool_name = models.CharField(max_length=100)
    tool_input = models.JSONField()
    tool_output = models.TextField()
    succeeded = models.BooleanField(default=True)
    duration_ms = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tool_name} @ {self.created_at}"
