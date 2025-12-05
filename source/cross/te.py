import math


# ============================================================
# Базовые приоритеты типов услуг
# ============================================================

SERVICE_BASE_SCORES = {
    "networks": 70,
    "it_services": 65,
    "local_phone": 55,
    "external_calls": 50,
    "ip_tv": 40,
}


# ============================================================
# Множитель для типа клиента
# ============================================================

def get_client_type_multiplier(is_company: bool) -> float:
    """
    Юр лицо важнее — множитель больше.
    """
    return 1.20 if is_company else 1.00


# ============================================================
# Фактор количества услуг
# ============================================================

def get_service_count_factor(service_count: int) -> float:
    """
    Логарифмический рост:
    - 1 услуга → слабое влияние
    - 10 → заметное
    - 100 → сильное
    - 1000 → очень сильное, но в границах
    """
    return 1 + math.log(service_count + 1, 10)  # log10


# ============================================================
# Фактор общей суммы услуг клиента
# ============================================================

def get_total_price_factor(total_price: float) -> float:
    """
    Цена влияет мягко.
    50 000 тенге → x2
    10 000 → x1.2
    """
    return 1 + (total_price / 50000)


# ============================================================
# Базовый приоритет услуги в заявке
# ============================================================

def get_base_score(service_type: str) -> float:
    return SERVICE_BASE_SCORES.get(service_type, 50)


# ============================================================
# Главная функция подсчёта приоритета заявки
# ============================================================

def calculate_priority(
    service_type: str,
    service_count: int,
    total_price: float,
    is_company: bool,
) -> float:
    """
    Комплексная оценка приоритета заявки на поддержку.
    """

    base = get_base_score(service_type)
    type_coef = get_client_type_multiplier(is_company)
    count_factor = get_service_count_factor(service_count)
    price_factor = get_total_price_factor(total_price)

    final = base * type_coef * count_factor * price_factor

    return round(final, 2)


# ============================================================
# Тестовые примеры
# ============================================================

if __name__ == "__main__":
    examples = [
        {
            "title": "Физ лицо, 2 услуги, сумма 8000, заявка networks",
            "args": ("networks", 2, 8000, False),
        },
        {
            "title": "Юр лицо, 20 услуг, 40 000 тг, заявка it_services",
            "args": ("it_services", 20, 40000, True),
        },
        {
            "title": "1000 дешевых услуг, 10 000 тг, networks",
            "args": ("networks", 1000, 10000, False),
        },
    ]

    for ex in examples:
        result = calculate_priority(*ex["args"])
        print(f"{ex['title']} → приоритет = {result}")
