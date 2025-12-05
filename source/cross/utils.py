from apps.support.models import Client, Engineer


def calculate_client_total_price(client):
    """
    Возвращает суммарную стоимость всех услуг клиента.
    """
    return sum(cs.service.price for cs in client.clientservice_set.all())


def calculate_client_importance_multiplier(client, min_coef=1.10, max_coef=1.20):
    """
    Динамически считает коэффициент важности клиента.
    Использует ранжирование по сумме расходов среди всех клиентов.
    
    Ничего не сохраняет в БД.
    """

    # Сначала считаем total price клиента отдельно
    client_total = calculate_client_total_price(client)

    # Берём суммы всех клиентов (только числа)
    all_totals = [
        calculate_client_total_price(c)
        for c in Client.objects.all()
    ]

    # Если все нулевые — у всех одинаковая важность
    if all(t == 0 for t in all_totals):
        return min_coef

    # Сортируем
    all_totals.sort()

    # Ищем ранг текущего клиента
    rank = all_totals.index(client_total)

    # Если клиент единственный
    if len(all_totals) == 1:
        p = 1.0
    else:
        # Перцентиль
        p = rank / (len(all_totals) - 1)

    # Преобразуем перцентиль в коэффициент
    coef = min_coef + p * (max_coef - min_coef)

    return round(coef, 4)


def get_most_free_engineer():
    """
    Возвращает инженера с минимальным количеством активных заявок.
    Если инженеров нет или все неактивны — возвращает None.
    """

    # Берём только активных инженеров
    engineers = Engineer.objects.filter(is_active=True)

    if not engineers.exists():
        return None

    # Используем Python-логику — проще и надёжнее
    return min(engineers, key=lambda e: e.active_tickets_count)