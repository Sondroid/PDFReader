import pdfplumber
from django.shortcuts import render
from .models import BankaHareketi, MuhasebeTanimi
from django.http import JsonResponse
from datetime import datetime

def pdf_yukle(request):
    if request.method == 'POST' and request.FILES['pdf_dosya']:
        pdf_dosya = request.FILES['pdf_dosya']
        
        with pdfplumber.open(pdf_dosya) as pdf:
            for sayfa in pdf.pages:
                tablo = sayfa.extract_table()
                if tablo:
                    for satir in tablo[1:]:  # Başlık satırını atla
                        BankaHareketi.objects.create(
                            tarih=parse_date(satir[0]),
                            aciklama=satir[1],
                            tutar=float(satir[2].replace(',', '.')),
                            islem_tipi=satir[3],
                            bakiye=float(satir[4].replace(',', '.'))
                        )
        
        return JsonResponse({'message': 'PDF başarıyla işlendi'})
    return render(request, 'pdf_yukle.html')

def hareket_filtrele(request):
    aranan_kelime = request.GET.get('aranan_kelime', '')
    hareketler = BankaHareketi.objects.filter(
        aciklama__icontains=aranan_kelime,
        muhasebe_kodu__isnull=True
    )
    return render(request, 'hareket_listesi.html', {
        'hareketler': hareketler
    })

def muhasebe_tanimla(request, hareket_id):
    if request.method == 'POST':
        hareket = BankaHareketi.objects.get(id=hareket_id)
        muhasebe_kodu = request.POST.get('muhasebe_kodu')
        
        # Hareketi güncelle
        hareket.muhasebe_kodu = muhasebe_kodu
        hareket.save()
        
        # Benzer hareketler için tanım kaydet
        MuhasebeTanimi.objects.create(
            arama_kelimesi=request.POST.get('arama_kelimesi'),
            muhasebe_kodu=muhasebe_kodu,
            aciklama=f"{hareket.aciklama} için otomatik tanım"
        )
        
        return JsonResponse({'success': True}) 