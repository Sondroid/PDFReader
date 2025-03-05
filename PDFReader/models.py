from django.db import models

class BankaHareketi(models.Model):
    tarih = models.DateField()
    aciklama = models.TextField()
    tutar = models.DecimalField(max_digits=10, decimal_places=2)
    islem_tipi = models.CharField(max_length=20)  # borç/alacak
    bakiye = models.DecimalField(max_digits=10, decimal_places=2)
    muhasebe_kodu = models.CharField(max_length=20, null=True, blank=True)
    
class MuhasebeTanimi(models.Model):
    arama_kelimesi = models.CharField(max_length=100)
    muhasebe_kodu = models.CharField(max_length=20)
    aciklama = models.TextField() 