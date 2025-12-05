from apps.support.models import Client


# ============================================================
# Сумма всех услуг клиента
# ============================================================
def calculate_client_total_price(client):
    """
    Возвращает суммарную стоимость всех услуг клиента.
    """
    return sum(cs.service.price for cs in client.clientservice_set.all())


# ============================================================
# Коэффициент важности клиента (динамический)
# ============================================================
def calculate_client_importance_multiplier(client, min_coef=1.10, max_coef=1.20):
    """
    Динамически считает коэффициент важности клиента.
    Основан на перцентильном ранжировании по сумме расходов.
    """
    client_total = calculate_client_total_price(client)

    all_totals = [
        calculate_client_total_price(c)
        for c in Client.objects.all()
    ]

    if not all_totals or all(t == 0 for t in all_totals):
        return min_coef

    all_totals.sort()
    rank = all_totals.index(client_total)

    if len(all_totals) == 1:
        p = 1.0
    else:
        p = rank / (len(all_totals) - 1)

    coef = min_coef + p * (max_coef - min_coef)
    return round(coef, 4)


# ============================================================
# Весовые коэффициенты типов услуг
# ============================================================
SERVICE_TYPE_WEIGHTS = {
    "networks":      {"mult": 1.10, "points": 5},
    "it_services":   {"mult": 1.08, "points": 3},
    "external_calls":{"mult": 1.04, "points": 2},
    "local_phone":   {"mult": 1.00, "points": 1},
    "ip_tv":         {"mult": 1.02, "points": 1},
}


# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ: Финальный приоритет клиента (0–100)
# ============================================================
def calculate_final_priority(initial_priority: int, client: Client) -> int:
    """
    Вычисляет финальный приоритет заявки на основе:
    - начального приоритета (AI) 30–70
    - важности клиента (динамический перцентиль)
    - корпоративного статуса
    - состава услуг клиента
    - веса типа каждой услуги (множитель + баллы)
    """

    priority = float(initial_priority)

    # 1. Важность клиента (перцентиль затрат)
    importance_multiplier = calculate_client_importance_multiplier(client)
    priority *= importance_multiplier

    # 2. Корпоративность клиента
    if client.is_company:
        priority *= 1.15

    # 3. Услуги клиента
    services = client.clientservice_set.all()

    total_multiplier = 1.0
    total_points = 0

    for cs in services:
        stype = cs.service.service_type
        weights = SERVICE_TYPE_WEIGHTS.get(stype)

        if weights:
            total_multiplier *= weights["mult"]
            total_points += weights["points"]

    # Применяем множители и баллы
    priority *= total_multiplier
    priority += total_points

    # 4. Дополнительные баллы за количество услуг
    priority += min(2 * len(services), 10)

    # 5. Нормализация 0–100
    priority = max(0, min(priority, 100))

    return int(round(priority))
    