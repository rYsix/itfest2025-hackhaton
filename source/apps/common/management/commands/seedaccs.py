from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


DEMO_ACCOUNTS = [
    ("admin@admin.kz", "Admin123!"),
    ("test@test.kz", "Test123!"),
    ("test@test.test", "Test123!"),
    ("example@example.com", "Example123!"),
]


class Command(BaseCommand):
    help = "Create demo SUPERUSERS for AqylNet admin panel."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("\n=== Creating demo superusers ===\n"))

        created = 0
        skipped = 0

        for email, password in DEMO_ACCOUNTS:
            # Для кастомной модели User email может быть username
            if User.objects.filter(email=email).exists():
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(f"Skipped (exists): {email}")
                )
                continue

            User.objects.create_superuser(
                email=email,
                password=password,
            )

            created += 1
            self.stdout.write(self.style.SUCCESS(f"Superuser created: {email}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted! Created: {created}, skipped: {skipped}\n"
            )
        )
