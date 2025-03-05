from django.db import models
from decimal import Decimal
from django.contrib.auth.models import User

class Firma(models.Model):
    ad = models.CharField(max_length=100)
    vergi_no = models.CharField(max_length=11, unique=True)
    adres = models.TextField(blank=True)
    telefon = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    kullanici = models.ForeignKey(User, on_delete=models.CASCADE, related_name='firmalar', null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    aktif = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Firma"
        verbose_name_plural = "Firmalar"
        ordering = ['ad']
    
    def __str__(self):
        return f"{self.ad} - {self.vergi_no}"

class Banka(models.Model):
    firma = models.ForeignKey(Firma, on_delete=models.CASCADE, related_name='bankalar')
    ad = models.CharField("Banka Adı", max_length=100)
    sube = models.CharField("Şube", max_length=100, blank=True)
    hesap_no = models.CharField("Hesap No", max_length=50, blank=True)
    iban = models.CharField("IBAN", max_length=50, blank=True)
    muhasebe_kodu = models.CharField("Muhasebe Kodu", max_length=20, blank=True)
    aktif = models.BooleanField("Aktif", default=True)
    aciklama = models.TextField("Açıklama", blank=True)
    olusturma_tarihi = models.DateTimeField(auto_now_add=True)
    
    # PDF format seçenekleri
    PDF_FORMATLARI = [
        ('GARANTI', 'Garanti Bankası'),
        ('YAPI_KREDI', 'Yapı Kredi Bankası'),
        ('IS_BANKASI', 'İş Bankası'),
        ('ZIRAAT', 'Ziraat Bankası'),
        ('HALK', 'Halk Bankası'),
        ('VAKIF', 'Vakıfbank'),
        ('DIGER', 'Diğer'),
    ]
    
    pdf_format = models.CharField(
        "PDF Format",
        max_length=20,
        choices=PDF_FORMATLARI,
        default='DIGER'
    )
    
    class Meta:
        verbose_name = "Banka"
        verbose_name_plural = "Bankalar"
        ordering = ['ad', 'sube']
        unique_together = ['firma', 'iban']  # Aynı firmada aynı IBAN'dan olamaz
    
    def __str__(self):
        return f"{self.ad} - {self.sube} ({self.hesap_no})"

class BankaHareketi(models.Model):
    firma = models.ForeignKey(Firma, on_delete=models.CASCADE, related_name='banka_hareketleri')
    banka = models.ForeignKey(Banka, on_delete=models.CASCADE, related_name='hareketler')
    tarih = models.DateField()
    aciklama = models.CharField(max_length=200)
    borc = models.DecimalField(max_digits=10, decimal_places=2)
    alacak = models.DecimalField(max_digits=10, decimal_places=2)
    bakiye = models.DecimalField(max_digits=10, decimal_places=2)
    muhasebe_kodu = models.CharField(max_length=20, null=True, blank=True)
    
    class Meta:
        verbose_name = "Banka Hareketi"
        verbose_name_plural = "Banka Hareketleri"
        ordering = ['-tarih']
    
    def __str__(self):
        return f"{self.tarih} - {self.aciklama[:50]}"

class MuhasebeTanimi(models.Model):
    firma = models.ForeignKey(Firma, on_delete=models.CASCADE, related_name='muhasebe_tanimlari')
    arama_kelimesi = models.CharField(max_length=100)
    muhasebe_kodu = models.CharField(max_length=20)
    aciklama = models.TextField()
    
    class Meta:
        verbose_name = "Muhasebe Tanımı"
        verbose_name_plural = "Muhasebe Tanımları"
        unique_together = ['firma', 'arama_kelimesi']
        
    def __str__(self):
        return f"{self.arama_kelimesi} - {self.muhasebe_kodu}"

class MuhasebePlani(models.Model):
    firma = models.ForeignKey(Firma, on_delete=models.CASCADE, related_name='muhasebe_plani')
    muhasebe_kodu = models.CharField(max_length=20)
    aciklama = models.CharField(max_length=200)
    
    class Meta:
        verbose_name = "Muhasebe Planı"
        verbose_name_plural = "Muhasebe Planı"
        ordering = ['muhasebe_kodu']
        unique_together = ['firma', 'muhasebe_kodu']
    
    def __str__(self):
        return f"{self.muhasebe_kodu} - {self.aciklama}" 