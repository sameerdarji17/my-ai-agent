"""
Quick terminal test loop:

    python manage.py chat_with_agent

Type messages and see the agent (with tools) respond, without needing to run
the full web server or a frontend.
"""

from django.core.management.base import BaseCommand
from agent.models import Conversation
from agent.orchestrator import AgentOrchestrator


class Command(BaseCommand):
    help = "Chat with the AI agent directly from the terminal."

    def handle(self, *args, **options):
        conversation = Conversation.objects.create(title="terminal-test")
        agent = AgentOrchestrator(conversation)

        self.stdout.write(self.style.SUCCESS("Agent ready. Type 'exit' to quit.\n"))
        while True:
            try:
                user_input = input("You: ")
            except (EOFError, KeyboardInterrupt):
                break
            if user_input.strip().lower() in ("exit", "quit"):
                break

            result = agent.run(user_input)

            for call in result["tool_trace"]:
                self.stdout.write(self.style.WARNING(f"  [tool] {call['tool']}({call['input']})"))

            self.stdout.write(self.style.SUCCESS(f"Agent: {result['reply']}\n"))
