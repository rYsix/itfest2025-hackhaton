from django.contrib import admin
from django.urls import path, include
from django.shortcuts import  render
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns


def test_view(request):
    return render(request, "test.html", {"total_price": 1,"client":2})


urlpatterns = [
    path("dj-admin/", admin.site.urls),

    # auth endpoints
    path("auth", include("endpoints.userauth.urls")),

    # test endpoint
    path("", test_view, ),

    path("test/", test_view, name="test_page"),
]


# ============================================================
# DEBUG STATIC FILES
# ============================================================
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=getattr(settings, "MEDIA_ROOT", None),
    )
