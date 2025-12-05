from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class TimezoneMiddleware(MiddlewareMixin):
    """Активирует временную зону из cookie 'timezone' (IANA string)."""

    COOKIE_NAME = "timezone"
    def process_request(self, request):
        tzname = request.COOKIES.get(self.COOKIE_NAME)
        try:
            if tzname:
                timezone.activate(tzname)
            else:
                timezone.deactivate()
        except Exception:
            timezone.deactivate()
