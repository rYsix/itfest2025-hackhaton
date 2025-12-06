# app/chat/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path("chat/", views.chat_view, name="chat"),          # Страница с фронтом
    path("api/send/", views.api_send_message, name="api_send"),  # API для отправки сообщения
]
