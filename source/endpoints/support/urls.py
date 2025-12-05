from django.urls import path
from . import views

urlpatterns = [
    path("", views.support_view, name="support"),
    path("check/", views.check_support_view, name="support_check"),
]
