from django.urls import path
from . import views

app_name = 'banka_islemleri'  # URL namespace'i ekledik

urlpatterns = [
    path('', views.home, name='home'),  # Ana sayfa
    path('firma-sec/', views.firma_sec, name='firma_sec'),
    path('pdf-yukle/', views.pdf_yukle, name='pdf_yukle'),
    path('hareket-filtrele/', views.hareket_filtrele, name='hareket_filtrele'),
    path('muhasebe-tanimla/<int:hareket_id>/', views.muhasebe_tanimla, name='muhasebe_tanimla'),
    path('muhasebe-kodu-ekle/', views.muhasebe_kodu_ekle, name='muhasebe_kodu_ekle'),
    path('muhasebe-kodlari-aktar/', views.muhasebe_kodlari_aktar, name='muhasebe_kodlari_aktar'),
    path('excel-sablon-indir/', views.excel_sablon_indir, name='excel_sablon_indir'),
    path('muhasebe-kodu-duzenle/<int:kod_id>/', views.muhasebe_kodu_duzenle, name='muhasebe_kodu_duzenle'),
    path('muhasebe-kodu-sil/<int:kod_id>/', views.muhasebe_kodu_sil, name='muhasebe_kodu_sil'),
    path('banka-listesi/', views.banka_listesi, name='banka_listesi'),
    path('banka-ekle/', views.banka_ekle, name='banka_ekle'),
    path('banka-duzenle/<int:banka_id>/', views.banka_duzenle, name='banka_duzenle'),
    path('banka-durum-degistir/<int:banka_id>/', views.banka_durum_degistir, name='banka_durum_degistir'),
    path('banka-tarih-araligi/', views.banka_tarih_araligi, name='banka_tarih_araligi'),
    path('firmalar/', views.firma_listesi, name='firma_listesi'),
    path('firma-ekle/', views.firma_ekle, name='firma_ekle'),
    path('firma-duzenle/<int:firma_id>/', views.firma_duzenle, name='firma_duzenle'),
    path('firma-durum-degistir/<int:firma_id>/', views.firma_durum_degistir, name='firma_durum_degistir'),
    path('muhasebe-tanimlari/', views.muhasebe_tanimlari, name='muhasebe_tanimlari'),
    path('muhasebe-tanimi-ekle/', views.muhasebe_tanimi_ekle, name='muhasebe_tanimi_ekle'),
    path('muhasebe-tanimi-duzenle/<int:tanim_id>/', views.muhasebe_tanimi_duzenle, name='muhasebe_tanimi_duzenle'),
    path('muhasebe-tanimi-sil/<int:tanim_id>/', views.muhasebe_tanimi_sil, name='muhasebe_tanimi_sil'),
    path('muhasebe-tanimlari-ara/', views.muhasebe_tanimlari_ara, name='muhasebe_tanimlari_ara'),
    path('vakifbank-pdf-onizle/', views.vakifbank_pdf_onizle, name='vakifbank_pdf_onizle'),
    path('vakifbank-pdf-onizle-sayfa/', views.vakifbank_pdf_onizle_sayfa, name='vakifbank_pdf_onizle_sayfa'),
    path('hareketleri-sil/', views.hareketleri_sil, name='hareketleri_sil'),
    path('banka-pdf-onizle/', views.banka_pdf_onizle, name='banka_pdf_onizle'),
    path('banka-pdf-onizle-sayfa/<int:banka_id>/', views.banka_pdf_onizle_sayfa, name='banka_pdf_onizle_sayfa'),
    path('muhasebe-fisi-aktar/', views.muhasebe_fisi_aktar, name='muhasebe_fisi_aktar'),
] 