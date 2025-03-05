from django.contrib import admin
from .models import Firma, Banka, BankaHareketi, MuhasebePlani, MuhasebeTanimi

@admin.register(Firma)
class FirmaAdmin(admin.ModelAdmin):
    list_display = ('ad', 'vergi_no', 'telefon', 'created_at', 'kullanici')
    search_fields = ('ad', 'vergi_no')
    list_filter = ('kullanici', 'created_at')

@admin.register(Banka)
class BankaAdmin(admin.ModelAdmin):
    list_display = ('firma', 'ad', 'sube', 'hesap_no', 'iban', 'aktif')
    list_filter = ('firma', 'aktif', 'ad')
    search_fields = ('ad', 'sube', 'hesap_no', 'iban')

@admin.register(BankaHareketi)
class BankaHareketiAdmin(admin.ModelAdmin):
    list_display = ('banka', 'tarih', 'aciklama', 'borc', 'alacak', 'bakiye')
    list_filter = ('banka', 'tarih')
    search_fields = ('aciklama',)
    date_hierarchy = 'tarih'

@admin.register(MuhasebePlani)
class MuhasebePlaniAdmin(admin.ModelAdmin):
    list_display = ('firma', 'muhasebe_kodu', 'aciklama')
    list_filter = ('firma',)
    search_fields = ('muhasebe_kodu', 'aciklama')

@admin.register(MuhasebeTanimi)
class MuhasebeTanimiAdmin(admin.ModelAdmin):
    list_display = ('firma', 'arama_kelimesi', 'muhasebe_kodu', 'aciklama')
    list_filter = ('firma',)
    search_fields = ('arama_kelimesi', 'muhasebe_kodu', 'aciklama') 