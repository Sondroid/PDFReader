from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('users.urls', namespace='users')),
    path('banka/', include('banka_islemleri.urls')),
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
] 