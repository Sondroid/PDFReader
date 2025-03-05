from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from banka_islemleri.views import home

urlpatterns = [
    path('', home, name='home'),  # Ana sayfa
    path('admin/', admin.site.urls),
    path('banka/', include('banka_islemleri.urls', namespace='banka_islemleri')),
    path('users/', include('users.urls', namespace='users')),  # users uygulaması URL'leri
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) 