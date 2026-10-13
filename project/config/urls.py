from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views
#urlpatterns = [path("admin/", admin.site.urls), path("", include("core.urls"))]
#urlpatterns = [path("admin/", admin.site.urls), path("login/", auth_views.LoginView.as_view(template_name="core/login.html")), path("", include("core.urls"))]
#login = auth_views.LoginView.as_view(template_name="core/login.html")#test
urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="core/login.html"), name="login"),
    path("", include("core.urls")),
]