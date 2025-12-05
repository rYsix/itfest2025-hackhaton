import random
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

# Замените 'apps.support.models' на ваш актуальный путь к моделям
# ВАЖНО: Убедитесь, что этот импорт соответствует вашему проекту
from apps.support.models import (
    Client,
    Service,
    ClientService,
    Engineer,
    SupportTicket,
)

# ============================================================
# КОНСТАНТЫ И СЦЕНАРИИ (с увеличением казахских имен)
# ============================================================

# Усиление казахских фамилий и русских
LAST_NAMES = [
    # Казахские (70%)
    "Алиев", "Искаков", "Нургалиев", "Серикбаев", "Омаров", "Кадыров", 
    "Жумабаев", "Ахметов", "Тарасов", "Келимбетов", "Мухамеджанов", 
    "Султанов", "Ермеков", "Абдрахманов", "Сагитов",
    # Русские (30%)
    "Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", 
    "Михайлов", "Новиков", "Федоров"
]

# Усиление казахских имен и русских
FIRST_NAMES = [
    # Казахские (70%)
    "Ержан", "Тимур", "Кайрат", "Азамат", "Даулет", "Айгуль", "Динара", 
    "Алия", "Бауыржан", "Нурлан", "Мадина", "Зарина", "Аслан", "Айдос", 
    "Самат",
    # Русские (30%)
    "Александр", "Сергей", "Елена", "Андрей", "Алексей", "Екатерина", 
    "Наталья", "Мария", "Анна"
]

STREETS = [
    # Казахские (70%)
    "Абая", "Сатпаева", "Толе би", "Достык", "Сейфуллина", "Назарбаева", 
    "Желтоксан", "Байтурсынова", "Аль-Фараби", "Рыскулова",
    # Русские (30%)
    "Ленина", "Мира", "Гагарина", "Гоголя"
]

# Казахские слова для названий компаний
COMPANY_PREFIXES = ["ТОО", "АО", "ИП", "ПК"]
KAZAKH_COMPANY_WORDS = [
    "Жер", "Алатау", "Коркем", "Даму", "Алтын", "Куат", "Береке", "Сапа"
]

# Словарь сценариев остается без изменений, он корректен
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
            # Увеличение числа активных инженеров для лучшего распределения заявок
            services = self._seed_services()
            engineers = self._seed_engineers()
            clients = self._seed_clients(count=50) # Увеличим число клиентов до 50
            self._seed_client_services(clients, services)
            self._seed_tickets(clients, engineers, count=200) # Увеличим число заявок до 200

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
            ("Бизнес-канал 'Алматы-Плюс' (1 Гбит)", "networks", 25000), # Более локализованное название
            ("Городской телефон (IP)", "local_phone", 1200),
            ("IP-TV 'Отау' (150 каналов)", "ip_tv", 2100), # Казахский бренд
            ("SIP-Телефония 'Global Call'", "external_calls", 3000),
            ("Настройка корпоративной сети", "it_services", 5000),
        ]
        services = []
        for t, st, p in data:
            s = Service.objects.create(title=t, service_type=st, price=p)
            services.append(s)
        return services

    def _seed_engineers(self):
        self.stdout.write("Наем инженеров...")
        # Усиление казахских имен
        names = [
            "Ерлан Инженеров", "Дмитрий Смирнов", "Азамат Айдаров", 
            "Виктор Петров", "Максим Иванов", "Олег Семенов", 
            "Рустем Нургалиев", "Бахтияр Султанов", "Марат Жумабаев"
        ]
        engineers = []
        for n in names:
            # С вероятностью 20% инженер неактивен (например, в отпуске)
            is_active = random.random() > 0.2
            engineers.append(Engineer.objects.create(full_name=n, is_active=is_active))
        return engineers

    def _seed_clients(self, count):
        self.stdout.write(f"Регистрация {count} клиентов...")
        clients = []
        for i in range(count):
            
            is_company = random.random() < 0.25 # Увеличим шанс до 25% что это юрлицо

            if is_company:
                company_name = random.choice(KAZAKH_COMPANY_WORDS)
                full_name = f'{random.choice(COMPANY_PREFIXES)} "{company_name} {random.randint(1, 99)}"'
                age = 0 # Для компаний возраст не важен
            else:
                # Генерация ФИО с учетом приоритета казахских имен/фамилий
                l_name = random.choice(LAST_NAMES)
                f_name = random.choice(FIRST_NAMES)
                # Иногда добавим отчество (имя отца), для реалистичности
                patronymic = random.choice(FIRST_NAMES) + "ұлы" if random.random() < 0.3 else ""
                full_name = f"{l_name} {f_name} {patronymic}".strip()
                age = random.randint(20, 70)

            phone = f"+77{random.choice(['01','02','05','70','77','47','17'])}{random.randint(1000000, 9999999)}"
            email = f"user_{i}_{random.randint(1, 1000)}@example.com"
            street = random.choice(STREETS)
            
            # Более разнообразные адреса (дом/офис, квартира/этаж)
            address_type = "офис" if is_company else "кв."
            address_num = random.randint(1, 150)
            
            address = f"г. Алматы, ул. {street}, д. {random.randint(1, 200)}, {address_type} {address_num}"

            client = Client.objects.create(
                full_name=full_name,
                email=email,
                phone_number=phone,
                service_address=address,
                age=age,
                is_company=is_company
            )
            clients.append(client)
        return clients

    def _seed_client_services(self, clients, services):
        self.stdout.write("Подключение услуг...")
        # Словарь для быстрого поиска по типу
        service_map = {s.service_type: s for s in services}
        
        for client in clients:
            # Каждому клиенту от 1 до 3 услуг
            num_services = random.randint(1, 3)
            
            pool = list(services) # Изначальный пул всех услуг

            if client.is_company:
                # Юрлицам обязательно дадим 'networks' (бизнес-канал) и повысим шанс на 'it_services'
                # Уберем "Тариф 'Домашний'" из выбора для юрлиц
                pool = [s for s in pool if s.title != "Тариф 'Домашний' (100 Мбит)"]
                
                # Добавляем IT-услугу
                if service_map.get('it_services') and service_map['it_services'] not in pool:
                    pool.append(service_map['it_services'])

            # Избегаем дубликатов
            to_add = random.sample(pool, min(len(pool), num_services))
            
            for s in to_add:
                ClientService.objects.create(client=client, service=s)

    def _seed_tickets(self, clients, engineers, count):
        self.stdout.write(f"Генерация {count} заявок с историей...")
        
        # Инженеры, которые могут быть назначены (активные)
        active_engineers = [e for e in engineers if e.is_active]
        if not active_engineers:
             self.stdout.write(self.style.ERROR("Нет активных инженеров для назначения заявок!"))
             active_engineers = engineers # Используем всех, если нет активных
        
        # Период: последние 120 дней
        end_date = timezone.now()
        start_date = end_date - datetime.timedelta(days=120)

        for _ in range(count):
            client = random.choice(clients)
            
            # 1. Определяем, на какую услугу жалуемся
            client_services = ClientService.objects.filter(client=client).select_related('service')
            if not client_services.exists():
                continue
            
            target_cs = random.choice(client_services)
            s_type = target_cs.service.service_type

            # 2. Выбираем сценарий проблемы
            scenarios = SCENARIOS.get(s_type, SCENARIOS["default"])
            # Взвешенный случайный выбор сценария на основе поля 'prob' (чем выше, тем чаще)
            weights = [s['prob'] for s in scenarios]
            scenario = random.choices(scenarios, weights=weights, k=1)[0]

            # 3. Дата создания (случайная за последние 120 дней)
            random_seconds = random.randint(0, int((end_date - start_date).total_seconds()))
            created_at = start_date + datetime.timedelta(seconds=random_seconds)

            # 4. Статус и инженер
            days_passed = (end_date - created_at).days
            
            status = "new"
            closed_at = None
            final_res = None
            engineer = None
            
            # Логика статусов:
            if days_passed > 7 and random.random() < 0.9: # Очень старые с 90% вероятностью закрыты
                status = "done"
            elif days_passed > 3 and random.random() < 0.7: # Средние с 70% вероятностью закрыты
                 status = "done"
            elif days_passed > 1:
                status = random.choices(["in_progress", "done"], weights=[70, 30], k=1)[0] # 70% в работе, 30% закрыты быстро
            else:
                # Совсем свежая
                status = random.choices(["new", "in_progress"], weights=[60, 40], k=1)[0]

            # Назначение инженера и закрытие
            if status == "in_progress" or status == "done":
                engineer = random.choice(active_engineers)
                if status == "done":
                    # Закрыли через 1-72 часа после создания
                    duration = datetime.timedelta(hours=random.randint(1, 72))
                    closed_at = created_at + duration
                    # Добавим немного рандома в финальное решение
                    final_res = f"{scenario['fix']}. {random.choice(['Проблема решена удаленно.', 'Выезд инженера не потребовался.', 'Клиент подтвердил работоспособность.'])}"
                
            # Если статус 'new', engineer остается None (ждет назначения)
            
            # 5. Приоритет
            base_priority = 50
            if client.is_company: base_priority += 20 # Приоритет для юрлиц выше
            # Если требуется выезд, повышаем приоритет
            if scenario["visit"] > 50: base_priority += 15
            priority = min(100, max(10, base_priority + random.randint(-15, 10))) # Диапазон 10-100

            # Почему нужен инженер (только если вероятность высока)
            why_needed = None
            if scenario["visit"] > 50 and status != "done":
                 why_needed = f"Требуется выезд по адресу {client.service_address}. Причина: {scenario['desc']}"


            # Создаем объект
            ticket = SupportTicket.objects.create(
                client=client,
                engineer=engineer,
                description=scenario["desc"],
                priority_score=priority,
                engineer_visit_probability=scenario["visit"],
                why_engineer_needed=why_needed,
                proposed_solution_engineer=scenario["eng"],
                proposed_solution_client=scenario["client"],
                final_resolution=final_res,
                status=status,
                closed_at=closed_at
            )

            # !!! ВАЖНО: Обновляем created_at, чтобы имитировать исторические данные
            SupportTicket.objects.filter(pk=ticket.pk).update(created_at=created_at)