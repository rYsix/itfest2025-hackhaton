import random
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

# Замените 'apps.support.models' на ваш актуальный путь к моделям
from apps.support.models import (
    Client,
    Service,
    ClientService,
    Engineer,
    SupportTicket,
)

# ============================================================
# КОНСТАНТЫ И СЦЕНАРИИ
# ============================================================

LAST_NAMES = [
    "Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", "Соколов", 
    "Михайлов", "Новиков", "Федоров", "Морозов", "Волков", "Алексеев", "Лебедев", 
    "Семенов", "Егоров", "Павлов", "Козлов", "Степанов", "Николаев", "Алиев", 
    "Ким", "Пак", "Искаков", "Нургалиев", "Серикбаев", "Омаров"
]

FIRST_NAMES = [
    "Александр", "Сергей", "Владимир", "Елена", "Андрей", "Алексей", "Михаил", 
    "Дмитрий", "Екатерина", "Наталья", "Мария", "Анна", "Игорь", "Юрий", 
    "Николай", "Светлана", "Ержан", "Тимур", "Кайрат", "Азамат", "Даулет", 
    "Айгуль", "Динара", "Алия"
]

STREETS = [
    "Абая", "Ленина", "Мира", "Сатпаева", "Толе би", "Достык", "Гоголя", 
    "Сейфуллина", "Назарбаева", "Желтоксан", "Байтурсынова", "Гагарина"
]

# Словарь сценариев: Тип услуги -> Список проблем
# Каждая проблема содержит описание, решение для инженера, совет клиенту и вес (вероятность поломки)
SCENARIOS = {
    "networks": [
        {
            "desc": "Низкая скорость входящего соединения (спидтест показывает < 10 Мбит)",
            "eng": "Проверка порта на OLT, ошибок CRC нет. Переключение профиля скорости.",
            "client": "Пожалуйста, отключите VPN и торренты, замерьте скорость по кабелю напрямую.",
            "fix": "Профиль порта обновлен, скорость соответствует тарифу.",
            "prob": 30,
            "visit": 10
        },
        {
            "desc": "Периодические разрывы соединения (LOS мигает красным)",
            "eng": "Высокое затухание на линии (-29dBm). Требуется чистка коннектора в муфте или переварка.",
            "client": "Проверьте, не перегнут ли желтый оптический патч-корд.",
            "fix": "Произведена переварка волокна в распределительной коробке. Затухание в норме (-19dBm).",
            "prob": 50,
            "visit": 90
        },
        {
            "desc": "Не открываются некоторые зарубежные ресурсы",
            "eng": "Проверка маршрутизации и DNS серверов.",
            "client": "Попробуйте прописать DNS 8.8.8.8 в настройках роутера.",
            "fix": "Проблема на магистрали вышестоящего провайдера, трафик перенаправлен.",
            "prob": 20,
            "visit": 0
        },
    ],
    "ip_tv": [
        {
            "desc": "Рассыпается картинка, артефакты на экране",
            "eng": "Потери пакетов multicast во внутренней сети. Проверка IGMP snooping на свитче доступа.",
            "client": "Перезагрузите ТВ-приставку по питанию.",
            "fix": "Заменен порт коммутатора на чердаке.",
            "prob": 40,
            "visit": 60
        },
        {
            "desc": "Черный экран, пишет 'Нет сигнала'",
            "eng": "Диагностика STB, возможно выход из строя HDMI порта или самой приставки.",
            "client": "Проверьте, правильно ли выбран источник сигнала (Source/Input) на телевизоре.",
            "fix": "Абоненту заменена приставка на новую модель.",
            "prob": 30,
            "visit": 80
        },
    ],
    "local_phone": [
        {
            "desc": "Шум и треск в трубке",
            "eng": "Окисление контактов в КРТ или повреждение 'лапши' в квартире.",
            "client": "Попробуйте подключить другой телефонный аппарат для проверки.",
            "fix": "Замена телефонного кабеля от щитка до квартиры.",
            "prob": 50,
            "visit": 100
        }
    ],
    "it_services": [
        {
            "desc": "Не работает принтер по сети",
            "eng": "Проверка IP-адреса принтера и службы диспетчера печати.",
            "client": "Проверьте, включен ли принтер и горит ли индикатор Wi-Fi.",
            "fix": "Переустановлены драйверы, настроен статический IP.",
            "prob": 40,
            "visit": 50
        }
    ],
    # Fallback для остальных типов
    "default": [
        {
            "desc": "Общая консультация по услугам",
            "eng": "Консультация предоставлена.",
            "client": "Ознакомьтесь с инструкцией в личном кабинете.",
            "fix": "Закрыто по запросу клиента.",
            "prob": 10,
            "visit": 0
        }
    ]
}

class Command(BaseCommand):
    help = "Генерация реалистичных тестовых данных для системы поддержки"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("\n=== НАЧАЛО ЗАПОЛНЕНИЯ БД ===\n"))

        with transaction.atomic():
            self._delete_all()
            services = self._seed_services()
            engineers = self._seed_engineers()
            clients = self._seed_clients(count=40) # Генерируем 40 клиентов
            self._seed_client_services(clients, services)
            self._seed_tickets(clients, engineers, count=150) # 150 заявок

        self.stdout.write(self.style.SUCCESS("\n=== ГОТОВО! БД ЗАПОЛНЕНА ===\n"))

    def _delete_all(self):
        self.stdout.write("Очистка старых данных...")
        SupportTicket.objects.all().delete()
        ClientService.objects.all().delete()
        Engineer.objects.all().delete()
        Client.objects.all().delete()
        Service.objects.all().delete()

    def _seed_services(self):
        self.stdout.write("Создание каталога услуг...")
        data = [
            ("Тариф 'Домашний' (100 Мбит)", "networks", 4500),
            ("Тариф 'Геймер' (500 Мбит)", "networks", 7900),
            ("Бизнес-канал (1 Гбит)", "networks", 25000),
            ("Городской телефон", "local_phone", 1200),
            ("IP-TV (150 каналов)", "ip_tv", 2100),
            ("SIP-Телефония", "external_calls", 3000),
            ("Настройка ПО и серверов", "it_services", 5000),
        ]
        services = []
        for t, st, p in data:
            s = Service.objects.create(title=t, service_type=st, price=p)
            services.append(s)
        return services

    def _seed_engineers(self):
        self.stdout.write("Наем инженеров...")
        names = ["Ерлан", "Дмитрий", "Азамат", "Виктор", "Максим", "Олег", "Рустем"]
        engineers = []
        for n in names:
            full_name = f"{n} Инженеров"
            engineers.append(Engineer.objects.create(full_name=full_name))
        return engineers

    def _seed_clients(self, count):
        self.stdout.write(f"Регистрация {count} клиентов...")
        clients = []
        for i in range(count):
            f_name = random.choice(FIRST_NAMES)
            l_name = random.choice(LAST_NAMES)
            full_name = f"{l_name} {f_name}"
            
            is_company = random.random() < 0.15 # 15% что это юрлицо
            if is_company:
                full_name = f'ТОО "{l_name} и партнеры"'

            phone = f"+77{random.choice(['01','02','05','77'])}{random.randint(1000000, 9999999)}"
            email = f"user_{i}@example.com"
            street = random.choice(STREETS)
            address = f"г. Алматы, ул. {street}, д. {random.randint(1, 200)}, кв. {random.randint(1, 150)}"

            client = Client.objects.create(
                full_name=full_name,
                email=email,
                phone_number=phone,
                service_address=address,
                age=random.randint(20, 70),
                is_company=is_company
            )
            clients.append(client)
        return clients

    def _seed_client_services(self, clients, services):
        self.stdout.write("Подключение услуг...")
        for client in clients:
            # Каждому клиенту от 1 до 3 услуг
            num_services = random.randint(1, 3)
            # Если юрлицо - дадим IT услуги и бизнес канал с большей вероятностью
            if client.is_company:
                pool = [s for s in services if s.service_type in ['it_services', 'networks']]
            else:
                pool = [s for s in services if s.service_type != 'it_services']
            
            # Fallback если пул пуст
            if not pool: pool = services

            to_add = random.sample(pool, min(len(pool), num_services))
            for s in to_add:
                ClientService.objects.create(client=client, service=s)

    def _seed_tickets(self, clients, engineers, count):
        self.stdout.write(f"Генерация {count} заявок с историей...")
        
        # Период: последние 90 дней
        end_date = timezone.now()
        start_date = end_date - datetime.timedelta(days=90)

        created_tickets = []

        for _ in range(count):
            client = random.choice(clients)
            
            # 1. Определяем, на какую услугу жалуемся
            client_services = ClientService.objects.filter(client=client).select_related('service')
            if not client_services.exists():
                continue # Пропускаем клиентов без услуг
            
            target_cs = random.choice(client_services)
            s_type = target_cs.service.service_type

            # 2. Выбираем сценарий проблемы
            scenarios = SCENARIOS.get(s_type, SCENARIOS["default"])
            scenario = random.choice(scenarios)

            # 3. Дата создания (случайная за последние 90 дней)
            random_seconds = random.randint(0, int((end_date - start_date).total_seconds()))
            created_at = start_date + datetime.timedelta(seconds=random_seconds)

            # 4. Статус и инженер
            # Чем старее заявка, тем вероятнее она закрыта
            days_passed = (end_date - created_at).days
            
            status = "new"
            closed_at = None
            final_res = None
            engineer = None

            # Если заявке больше 5 дней, она скорее всего закрыта
            if days_passed > 5:
                status = "done"
                engineer = random.choice(engineers)
                # Закрыли через 2-48 часов после создания
                duration = datetime.timedelta(hours=random.randint(2, 48))
                closed_at = created_at + duration
                final_res = scenario["fix"]
            elif days_passed > 1:
                status = "in_progress"
                engineer = random.choice(engineers)
            else:
                # Совсем свежая
                status = random.choice(["new", "new", "in_progress"]) # Чаще new
                if status == "in_progress":
                    engineer = random.choice(engineers)

            # 5. Приоритет зависит от типа клиента и рандома
            base_priority = 50
            if client.is_company: base_priority += 20
            priority = min(100, base_priority + random.randint(-10, 20))

            # Создаем объект
            ticket = SupportTicket.objects.create(
                client=client,
                engineer=engineer,
                description=scenario["desc"],
                priority_score=priority,
                engineer_visit_probability=scenario["visit"],
                why_engineer_needed="Требуется физический доступ" if scenario["visit"] > 50 else None,
                proposed_solution_engineer=scenario["eng"],
                proposed_solution_client=scenario["client"],
                final_resolution=final_res,
                status=status,
                closed_at=closed_at
            )

            # !ВАЖНО: Поле created_at имеет auto_now_add=True, поэтому при create() оно ставится в Current Time.
            # Мы должны обновить его через update() напрямую в БД, чтобы обойти это.
            SupportTicket.objects.filter(pk=ticket.pk).update(created_at=created_at)
            
            created_tickets.append(ticket)