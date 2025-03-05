from django.shortcuts import redirect
from .models import Firma

class FirmaSecimMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Admin paneli, firma seçim sayfası, login sayfası, register sayfası ve firma ekleme sayfası hariç kontrol et
        if not request.path.startswith('/admin/') and not request.path.startswith('/banka/firma-sec/') and not request.path.startswith('/users/login/') and not request.path.startswith('/users/register/') and not request.path.startswith('/banka/firma-ekle/'):
            # Oturum açılmış ve firma seçilmemiş ise
            if request.user.is_authenticated and 'secili_firma_id' not in request.session:
                return redirect('banka_islemleri:firma_sec')
        
        response = self.get_response(request)
        return response 