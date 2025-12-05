from django.urls import path
from django.shortcuts import redirect
from . import views

urlpatterns = [
    # redirect /admin/ → /admin/dashboard/
    path("", lambda request: redirect("admin_dashboard"), name="admin_root"),

    # dashboard page
    path("dashboard/", views.admin_dashboard_view, name="admin_dashboard"),

]
