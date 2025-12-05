from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from apps.support.models import (
    SupportTicket,
    Client,
    Service,
    ClientService,
    Engineer,
)

@login_required(login_url="/auth/login/")
def admin_dashboard_view(request):
    context = {
        "clients": Client.objects.all(),
        "services": Service.objects.all(),
        "client_services": ClientService.objects.select_related("client", "service"),
        "engineers": Engineer.objects.all(),
        "tickets": SupportTicket.objects.select_related("client", "engineer"),
    }

    return render(request, "cadmin/dash.html", context)
