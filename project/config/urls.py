from django.contrib import admin
from django.urls import include, path
from core import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", views.login_page, name="login"),
    path("", include("core.urls")),
]