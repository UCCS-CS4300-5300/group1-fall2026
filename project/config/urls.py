from django.contrib import admin
from django.urls import include, path
from core import views
#urlpatterns = [path("admin/", admin.site.urls), path("", include("core.urls"))]
urlpatterns = [
    path("admin/", admin.site.urls),
    # Show the sign-in page when someone visits /login/.
    path("login/", views.login_page, name="login"),
    path("", include("core.urls")),
]