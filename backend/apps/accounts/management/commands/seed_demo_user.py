"""Management command: seed a demo account (for reviewer logins)."""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Create or reset the demo reviewer account."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="demo@example.com")
        parser.add_argument("--password", default="DemoPass!123")

    def handle(self, *args, **options):
        email = options["email"]
        password = options["password"]
        user, created = User.objects.get_or_create(email=email)
        user.set_password(password)
        user.is_staff = False
        user.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo account ready: {email} (created={created})"
            )
        )
