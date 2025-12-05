from django.db import models
from django.utils import timezone


# ============================================================
# Модель Клиент
# ============================================================

class Client(models.Model):
    full_name = models.CharField(
        max_length=255,
        verbose_name="ФИО"
    )

    account_number = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name="Лицевой счёт"
    )

    phone_number = models.CharField(
        max_length=20,
        verbose_name="Номер телефона"
    )

    email = models.EmailField(
        verbose_name="E-mail"
    )

    service_address = models.CharField(
        max_length=255,
        verbose_name="Адрес оказываемых услуг"
    )

    age = models.PositiveIntegerField(
        verbose_name="Возраст клиента",
        default=0,
        help_text="Возраст клиента в полных годах (необязательно)"
    )

    is_company = models.BooleanField(
        default=False,
        verbose_name="Юридическое лицо?"
    )

    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"

    def __str__(self):
        return f"{self.full_name} ({self.account_number})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            base = 100000
            self.account_number = str(base + self.id)
            super().save(update_fields=["account_number"])


# ============================================================
# Модель Услуга
# ============================================================

class Service(models.Model):

    SERVICE_TYPES = [
        ("networks", "Сеть передачи данных"),
        ("external_calls", "Разговоры со сторонними операторами"),
        ("it_services", "IT-услуги"),
        ("local_phone", "Местная телефония"),
        ("ip_tv", "IP-телевидение"),
    ]

    title = models.CharField(
        max_length=255,
        verbose_name="Название услуги"
    )

    service_type = models.CharField(
        max_length=50,
        choices=SERVICE_TYPES,
        verbose_name="Тип услуги"
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Цена услуги"
    )

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"

    def __str__(self):
        return self.title


# ============================================================
# Модель Услуга клиента
# ============================================================

class ClientService(models.Model):
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        verbose_name="Клиент"
    )

    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        verbose_name="Услуга"
    )

    service_number = models.CharField(
        max_length=25,
        unique=True,
        blank=True,
        verbose_name="Номер услуги"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создано"
    )

    class Meta:
        verbose_name = "Услуга клиента"
        verbose_name_plural = "Услуги клиентов"

    def __str__(self):
        return f"{self.client.full_name} — {self.service.title}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        now = timezone.now()
        super().save(*args, **kwargs)

        if is_new:
            prefix = "SL"
            self.service_number = f"{prefix}-{now.year}-{now.month:02d}-{self.id:06d}"
            super().save(update_fields=["service_number"])


# ============================================================
# Модель Инженер
# ============================================================

class Engineer(models.Model):
    full_name = models.CharField(
        max_length=255,
        verbose_name="ФИО"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен?"
    )

    class Meta:
        verbose_name = "Инженер"
        verbose_name_plural = "Инженеры"

    def __str__(self):
        return self.full_name

    @property
    def active_tickets_count(self):
        return self.supportticket_set.filter(
            status__in=["new", "in_progress"]
        ).count()


# ============================================================
# Модель Заявка
# ============================================================

class SupportTicket(models.Model):

    STATUSES = [
        ("new", "Новая"),
        ("in_progress", "В работе"),
        ("done", "Закрыта"),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        verbose_name="Клиент"
    )

    engineer = models.ForeignKey(
        Engineer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Инженер"
    )

    description = models.TextField(
        verbose_name="Описание проблемы"
    )

    priority_score = models.PositiveSmallIntegerField(
        default=50,
        verbose_name="Приоритет заявки"
    )

    engineer_visit_probability = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Вероятность вызова инженера (0–100)",
        help_text="Целое число процентов."
    )

    proposed_solution = models.TextField(
        null=True,
        blank=True,
        verbose_name="Предложенное решение",
        help_text="Автоматически предложенное ИИ решение на основе похожих обращений. Как заметка оператору и инженеру."
    )

    final_resolution = models.TextField(
        null=True,
        blank=True,
        verbose_name="Финальное решение проблемы",
        help_text="Итоговое решение инженера после завершения работы по заявке."
    )

    status = models.CharField(
        max_length=20,
        choices=STATUSES,
        default="new",
        verbose_name="Статус"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создана"
    )

    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Закрыта"
    )

    class Meta:
        verbose_name = "Заявка"
        verbose_name_plural = "Заявки"

    def __str__(self):
        return f"Заявка #{self.id} от {self.client.full_name}"
