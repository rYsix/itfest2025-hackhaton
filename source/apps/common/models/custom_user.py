from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    """Менеджер для модели CustomUser."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Поле Email обязательно для заполнения.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not password:
            raise ValueError("Необходимо указать пароль для суперпользователя.")
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """Пользовательская модель, использующая Email в качестве логина."""

    email = models.EmailField(unique=True, verbose_name="Почта", help_text="Уникальный адрес электронной почты пользователя.")
    full_name = models.CharField(max_length=255, verbose_name="Полное имя", help_text="Укажите фамилию и имя полностью.")
    is_active = models.BooleanField(default=True, verbose_name="Активен?")
    is_staff = models.BooleanField(default=False, verbose_name="Сотрудник?")
    date_joined = models.DateTimeField(default=timezone.now, verbose_name="Дата регистрации")

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["id"]

    def __str__(self):
        return f"id {self.id}: {self.full_name} {self.email}"
