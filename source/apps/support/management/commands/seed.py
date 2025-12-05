from django.core.management.base import BaseCommand
from django.utils import timezone
import random

from apps.support.models import (
    Client,
    Service,
    ClientService,
    Engineer,
    SupportTicket,
)


class Command(BaseCommand):
    help = "Fully reset support module and seed smart realistic data"

    # =====================================================================
    # MAIN ENTRY
    # =====================================================================
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("\n=== SEED START ===\n"))

        self._delete_all()
        services = self._seed_services()
        clients = self._seed_clients()
        self._seed_client_services(clients, services)
        engineers = self._seed_engineers()
        self._seed_tickets(clients, engineers)

        self.stdout.write(self.style.SUCCESS("\n=== SEED FINISHED ===\n"))

    # =====================================================================
    # DELETE DATA
    # =====================================================================
    def _delete_all(self):
        self.stdout.write(self.style.WARNING("Удаляем старые данные..."))

        SupportTicket.objects.all().delete()
        ClientService.objects.all().delete()
        Engineer.objects.all().delete()
        Client.objects.all().delete()
        Service.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("Данные очищены.\n"))

    # =====================================================================
    # SERVICES
    # =====================================================================
    def _seed_services(self):
        self.stdout.write(self.style.NOTICE("Создание услуг..."))

        services_data = [
            ("Интернет 100 Мбит/с", "networks", 4990),
            ("Интернет 300 Мбит/с", "networks", 6990),
            ("Разговоры внешние — 100 мин", "external_calls", 1500),
            ("IT-поддержка базовая", "it_services", 2500),
            ("Местная телефония — Стандарт", "local_phone", 990),
            ("IP-TV Базовый", "ip_tv", 1690),
        ]

        services = [
            Service.objects.create(title=t, service_type=st, price=p)
            for t, st, p in services_data
        ]

        self.stdout.write(self.style.SUCCESS(f"Создано услуг: {len(services)}\n"))
        return services

    # =====================================================================
    # CLIENTS
    # =====================================================================
    def _seed_clients(self):
        self.stdout.write(self.style.NOTICE("Создание клиентов..."))

        templates = [
            ("Иванов Иван Иванович", "ivanov@example.com", "+77010001122", "г. Астана, ул. Абая 10"),
            ("Петров Петр Петрович", "petrov@example.com", "+77070002211", "г. Алматы, ул. Сатпаева 5"),
            ("Карпов Сергей Николаевич", "karpov@example.com", "+77015556677", "г. Шымкент, ул. Байтурсынова 12"),
            ("Жумабеков Даурен Оразбекович", "dauren@example.com", "+77018883355", "г. Актобе, ул. Молдагуловой 7"),
            ("Серикбаева Алина Тимуровна", "alina@example.com", "+77023334455", "г. Кокшетау, ул. Назарбаева 12"),
            ("Асанова Жулдыз Ерлановна", "zhasan@mail.kz", "+77056661212", "г. Тараз, ул. Толе би 33"),
            ("Тлеуов Марат Сапарович", "m.tleuov@mail.com", "+77081112233", "г. Караганда, пр. Бухар жырау 18"),
        ]

        clients = []
        for name, email, phone, addr in templates:
            clients.append(
                Client.objects.create(
                    full_name=name,
                    email=email,
                    phone_number=phone,
                    service_address=addr,
                    age=random.randint(18, 80),
                    is_company=random.choice([True, False]),
                )
            )

        self.stdout.write(self.style.SUCCESS(f"Создано клиентов: {len(clients)}\n"))
        return clients

    # =====================================================================
    # CLIENT SERVICES
    # =====================================================================
    def _seed_client_services(self, clients, services):
        self.stdout.write(self.style.NOTICE("Назначение услуг клиентам..."))

        total = 0
        for client in clients:
            assigned = random.sample(services, random.randint(1, len(services)))
            for srv in assigned:
                ClientService.objects.create(client=client, service=srv)
                total += 1

        self.stdout.write(self.style.SUCCESS(f"Назначено клиентских услуг: {total}\n"))

    # =====================================================================
    # ENGINEERS
    # =====================================================================
    def _seed_engineers(self):
        self.stdout.write(self.style.NOTICE("Создание инженеров..."))

        names = [
            "Ерлан Бекенов",
            "Тимур Жанабеков",
            "Данияр Сейткалиев",
            "Антон Громов",
            "Руслан Каримов",
        ]

        engineers = [Engineer.objects.create(full_name=n) for n in names]

        self.stdout.write(self.style.SUCCESS(f"Создано инженеров: {len(engineers)}\n"))
        return engineers

    # =====================================================================
    # SUPPORT TICKETS
    # =====================================================================
    def _seed_tickets(self, clients, engineers):
        self.stdout.write(self.style.NOTICE("Создание заявок..."))

        problem_texts = [
            "Нет доступа в интернет",
            "Не работает IP-TV",
            "Плохое качество связи",
            "Проблемы с локальной телефонией",
            "Маршрутизатор периодически зависает",
            "Обрывы пакетов",
            "Низкая скорость передачи данных",
        ]

        ai_solutions = [
            "Перезагрузить маршрутизатор и проверить кабель.",
            "Обновить прошивку устройства.",
            "Проверить настройки VLAN.",
            "Рекомендовано проверить разъёмы и заменить патч-корд.",
            "Проверить уровень сигнала Wi-Fi и сменить канал.",
        ]

        final_resolutions = [
            "Заменён кабель, проблема устранена.",
            "Перенастроен маршрутизатор, подключение стабилизировано.",
            "Произведена чистка оборудования, всё работает корректно.",
            "Обнаружена проблема у клиента, предоставлена консультация.",
        ]

        tickets_count = 15
        created = []

        for _ in range(tickets_count):

            client = random.choice(clients)
            engineer = random.choice(engineers) if random.random() > 0.2 else None

            status = random.choice(["new", "in_progress", "done"])

            ticket = SupportTicket.objects.create(
                client=client,
                engineer=engineer,
                description=random.choice(problem_texts),
                priority_score=random.uniform(20, 95),
                engineer_visit_probability=random.uniform(10, 90),
                proposed_solution=random.choice(ai_solutions),
                status=status,
            )

            # Если заявка закрыта → ставим final_resolution и closed_at
            if status == "done":
                ticket.final_resolution = random.choice(final_resolutions)
                ticket.closed_at = timezone.now() - timezone.timedelta(hours=random.randint(1, 72))
                ticket.save(update_fields=["final_resolution", "closed_at"])

            created.append(ticket)

        self.stdout.write(self.style.SUCCESS(f"Создано заявок: {len(created)}\n"))
