import pdfplumber
from django.shortcuts import render, redirect
from .models import BankaHareketi, MuhasebeTanimi, MuhasebePlani, Firma, Banka
from django.http import JsonResponse
from datetime import datetime, date
from django.views.decorators.csrf import csrf_exempt
import json
import re
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Min, Max
import pandas as pd
from django.contrib import messages
from django.http import HttpResponse
import io
from django.template.context_processors import request
from django.db.models import Q
import xlsxwriter
from django.contrib.auth.decorators import login_required
from .forms import FirmaForm

def parse_date(date_str):
    # Tarih formatlarını kontrol et
    formats = [
        '%b. %d, %Y',  # Jan. 27, 2025
        '%d.%m.%Y',    # 27.01.2025
        '%d/%m/%Y',    # 27/01/2025
        '%Y/%m/%d',    # 2025/01/27
        '%Y-%m-%d',    # 2025-01-27
        '%m/%d/%Y',    # 12/19/2024 (Amerikan formatı)
        '%d/%m/%y',    # 19/12/24
        '%y/%m/%d'     # 24/12/19
    ]
    
    print(f"Tarih ayrıştırma deneniyor: {date_str}")
    for fmt in formats:
        try:
            print(f"Format deneniyor: {fmt}")
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            print(f"Format uyumsuz: {fmt}")
            continue
    
    print(f"Hiçbir format uymadı: {date_str}")
    raise ValueError(f"Tarih formatı tanınamadı: {date_str}")

def parse_amount(amount_str):
    try:
        # None veya boş string kontrolü
        if not amount_str:
            return Decimal('0.0')
        
        # String'e çevir ve boşlukları temizle
        amount_str = str(amount_str).strip()
        
        print(f"\nPARSE AMOUNT GİRİŞ: {amount_str}")
        
        # Para birimi sembollerini ve boşlukları kaldır
        amount_str = amount_str.replace('₺', '').replace('TL', '').strip()
        
        # Binlik ayracı olan noktaları kaldır (örn: 1.234,56 -> 1234,56)
        if ',' in amount_str:
            amount_str = amount_str.replace('.', '')
        
        # Virgülü noktaya çevir
        amount_str = amount_str.replace(',', '.')
        
        # Parantez içindeki sayıları negatife çevir (örn: (123.45) -> -123.45)
        if amount_str.startswith('(') and amount_str.endswith(')'):
            amount_str = '-' + amount_str[1:-1]
        
        # Sayısal olmayan tüm karakterleri kaldır (- işareti hariç)
        cleaned = re.sub(r'[^\d.-]', '', amount_str)
        
        print(f"TEMİZLENMİŞ DEĞER: {cleaned}")
        
        # Boş string kontrolü
        if not cleaned:
            print("BOŞ DEĞER -> 0.0")
            return Decimal('0.0')
        
        # Decimal'e çevir
        result = Decimal(cleaned)
        print(f"SONUÇ: {result}")
        return result
        
    except Exception as e:
        print(f"PARSE HATA: {e} - Orijinal değer: {amount_str}")
        return Decimal('0.0')

def parse_pdf_garanti(page):
    """Garanti Bankası PDF formatı için parser"""
    print("\nGARANTİ BANKASI PDF İŞLENİYOR")
    
    # Önce PDF'in text içeriğini kontrol et
    text = page.extract_text()
    if not text or text.isspace():
        print("HATA: PDF'den metin çıkarılamadı veya PDF boş!")
        return []
    
    print("\nPDF Text İçeriği:")
    print(text)
    print("=" * 50)
    
    # Satırları işle
    lines = text.split('\n')
    hareketler = []
    islem_alani = False
    onceki_aciklama = None  # Önceki satırdaki açıklamayı saklamak için
    
    # Başlık için olası varyasyonlar
    baslik_varyasyonlari = [
        "Tarih Açıklama Etiket Tutar Bakiye",
        "Tarih Açıklama Tutar Bakiye",
        "İşlem Tarihi Açıklama Tutar Bakiye",
        "Tarih Açıklama Borç Alacak Bakiye",
        "İşlem Tarihi Açıklama Borç Alacak Bakiye",
        # Türkçe karakter varyasyonları
        "Tarih Aciklama Etiket Tutar Bakiye",
        "Tarih Aciklama Tutar Bakiye",
        "Islem Tarihi Aciklama Tutar Bakiye",
        "Tarih Aciklama Borc Alacak Bakiye",
        "Islem Tarihi Aciklama Borc Alacak Bakiye"
    ]
    
    # İşlem alanı sonu kontrol kelimeleri
    bitis_kelimeleri = [
        "TOPLAM",
        "Sayfa",
        "Dekont Yerine Geçmez",
        "Müşteri / Hesap No",
        "Musteri / Hesap No",
        "Müsteri / Hesap No",
        "Devir Bakiye",
        "Dönem Sonu",
        "Donem Sonu"
    ]
    
    # Başlık bulundu mu kontrolü
    baslik_bulundu = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        print(f"\nİşlenen satır: {line}")
        
        # İşlem alanının başlangıcını bul
        if any(baslik in line for baslik in baslik_varyasyonlari):
            print(f"Başlık bulundu: {line}")
            islem_alani = True
            baslik_bulundu = True
            continue
        
        # İşlem alanının sonunu kontrol et
        if any(bitis in line for bitis in bitis_kelimeleri):
            print(f"Bitiş kelimesi bulundu: {line}")
            islem_alani = False
            continue
        
        if not islem_alani:
            continue
            
        try:
            # Tarih kontrolü yap (GG.AA.YYYY formatı)
            tarih_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', line)
            if not tarih_match:
                # Eğer tarih yoksa ve önceki açıklama varsa, bu satır muhtemelen önceki açıklamanın devamı
                if onceki_aciklama:
                    print(f"Önceki açıklamaya ekleme: {line}")
                    hareketler[-1]['aciklama'] += ' ' + line
                continue
            
            tarih_str = tarih_match.group(1)
            print(f"Tarih bulundu: {tarih_str}")
            
            # Kalan metni al
            kalan_metin = line[len(tarih_match.group(0)):].strip()
            print(f"Kalan metin: {kalan_metin}")
            
            # Tutarları bul (TL işaretini de dahil et)
            tutarlar = re.findall(r'[-]?(?:\d{1,3}(?:[.,]\d{3})*|\d+)(?:[.,]\d{2})?\s*TL', kalan_metin)
            if not tutarlar:
                print("Tutar bulunamadı")
                continue
            
            print(f"Bulunan tutarlar: {tutarlar}")
            
            # Son iki tutarı al (bakiye hariç)
            if len(tutarlar) >= 2:
                tutar_str = tutarlar[-2].replace('TL', '').strip()  # İşlem tutarı
                bakiye_str = tutarlar[-1].replace('TL', '').strip()  # Bakiye
            else:
                tutar_str = tutarlar[0].replace('TL', '').strip()
                bakiye_str = tutarlar[0].replace('TL', '').strip()
            
            print(f"İşlem tutarı: {tutar_str}, Bakiye: {bakiye_str}")
            
            # Açıklamayı al (tutarları çıkar)
            aciklama = kalan_metin
            for tutar in tutarlar:
                aciklama = aciklama.replace(tutar, '')
            aciklama = ' '.join(aciklama.split())
            print(f"Açıklama: {aciklama}")
            
            # Tarihi işle
            tarih = datetime.strptime(tarih_str, '%d.%m.%Y').date()
            
            # Tutarları işle
            tutar = parse_amount(tutar_str)
            bakiye = parse_amount(bakiye_str)
            
            # Borç/Alacak belirleme
            if tutar >= 0:
                borc = tutar
                alacak = Decimal('0.0')
            else:
                borc = Decimal('0.0')
                alacak = abs(tutar)
            
            hareket = {
                'tarih': tarih,
                'aciklama': aciklama,
                'borc': borc,
                'alacak': alacak,
                'bakiye': bakiye,
                'muhasebe_kodu': None
            }
            hareketler.append(hareket)
            onceki_aciklama = aciklama
            print(f"Hareket eklendi: {hareket}")
            
        except Exception as e:
            print(f"Satır işleme hatası: {e}")
            continue
    
    if not baslik_bulundu:
        print("UYARI: PDF'de Garanti Bankası formatına uygun başlık bulunamadı!")
        print("Aranan başlıklar:", baslik_varyasyonlari)
    
    # Hareketleri tarihe göre sırala
    hareketler.sort(key=lambda x: x['tarih'])
    
    print(f"\nToplam {len(hareketler)} hareket bulundu")
    return hareketler

def parse_pdf_yapi_kredi(page):
    try:
        text = page.extract_text()
        if not text:
            return [], "PDF'den metin çıkarılamadı"

        hareketler = []
        lines = text.split('\n')
        
        # Sayfa sonu bilgilerini içeren kelimeler
        bitis_kelimeleri = [
            "Yapı ve Kredi Bankası A.Ş.",
            "www.yapikredi.com.tr",
            "Ticaret Sicil Numarası:",
            "Mersis No:",
            "İşletmenin Merkezi:",
            "Blok",
            "T:",
            "F:"
        ]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Sayfa sonu bilgilerini kontrol et
            if any(kelime in line for kelime in bitis_kelimeleri):
                continue
                
            print(f"\nİşlenen satır: {line}")
            
            # Tarih ve saat kontrolü - birkaç farklı format için kontrol
            tarih = None
            # Format 1: DD/MM/YYYY HH:mm:ss
            tarih_match = re.search(r'(\d{2}/\d{2}/\d{4})\s+\d{2}:\d{2}:\d{2}', line)
            if tarih_match:
                tarih = tarih_match.group(1)
            else:
                # Format 2: DD/MM/YYYY
                tarih_match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
                if tarih_match:
                    tarih = tarih_match.group(1)
            
            if not tarih:
                print("Tarih bulunamadı")
                continue
                
            print(f"Tarih bulundu: {tarih}")
            
            # Tutar ve bakiye kontrolü - En sondaki iki TL'li sayıyı bul
            tutarlar = re.findall(r'([-]?\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*TL', line)
            if len(tutarlar) < 2:
                print("Tutar veya bakiye bulunamadı")
                continue
                
            # Son iki tutarı al (sondan birinci bakiye, sondan ikinci işlem tutarı)
            tutar_str = tutarlar[-2]
            bakiye_str = tutarlar[-1]
            
            print(f"Tutar string: {tutar_str}")
            print(f"Bakiye string: {bakiye_str}")
            
            try:
                # Tutarı dönüştür
                tutar_str = tutar_str.replace('.', '').replace(',', '.')
                tutar = float(tutar_str)
                print(f"Dönüştürülmüş tutar: {tutar}")
                
                # Bakiyeyi dönüştür
                bakiye_str = bakiye_str.replace('.', '').replace(',', '.')
                bakiye = float(bakiye_str)
                print(f"Dönüştürülmüş bakiye: {bakiye}")
            except ValueError as e:
                print(f"Sayı dönüşüm hatası: {str(e)}")
                continue
            
            # Açıklama işleme
            aciklama = line
            print(f"Ham satır: {aciklama}")
            
            # Tarih ve saati çıkar
            aciklama = re.sub(r'\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}', '', aciklama)
            print(f"Tarih ve saat çıkarıldı: {aciklama}")
            
            # Sadece tarihi çıkar (eğer saat yoksa)
            aciklama = re.sub(r'\d{2}/\d{2}/\d{4}', '', aciklama)
            print(f"Sadece tarih çıkarıldı: {aciklama}")
            
            # Tutarları çıkar
            aciklama = re.sub(r'[-]?\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s*TL', '', aciklama)
            print(f"Tutarlar çıkarıldı: {aciklama}")
            
            # Fazladan boşlukları temizle
            aciklama = ' '.join(aciklama.split())
            aciklama = aciklama.strip()
            print(f"Boşluklar temizlendi: {aciklama}")
            
            # Açıklamayı düzenle
            aciklama = aciklama.replace("Para Transferleri Diğer ", "")
            print(f"Son açıklama: {aciklama}")
            
            # Borç/Alacak belirleme
            borc = abs(tutar) if tutar > 0 else 0
            alacak = abs(tutar) if tutar < 0 else 0
            
            hareket = {
                'tarih': tarih,  # Tarihi string olarak bırakıyoruz
                'aciklama': aciklama,
                'borc': borc,
                'alacak': alacak,
                'bakiye': bakiye
            }
            hareketler.append(hareket)
            print(f"Hareket eklendi: {hareket}")
            
        if not hareketler:
            return [], "PDF'den işlem çıkarılamadı"
            
        return hareketler, None
        
    except Exception as e:
        print(f"Yapı Kredi PDF parse hatası: {str(e)}")
        return [], f"PDF işlenirken hata oluştu: {str(e)}"

def parse_pdf_is_bankasi(page):
    try:
        text = page.extract_text()
        if not text:
            return [], "PDF'den metin çıkarılamadı"

        hareketler = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            print(f"\nİşlenen satır: {line}")
            
            try:
                # Tarih kontrolü yap (GG.AA.YYYY veya GG/AA/YYYY formatı)
                tarih_match = re.search(r'(\d{2}[./]\d{2}[./]\d{4})', line)
                if not tarih_match:
                    continue
                    
                tarih = tarih_match.group(1)
                print(f"Tarih bulundu: {tarih}")
                
                # Tutar ve bakiye kontrolü
                tutarlar = re.findall(r'([-]?\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*TL', line)
                if len(tutarlar) < 2:
                    continue
                    
                # Son iki tutarı al (sondan birinci bakiye, sondan ikinci işlem tutarı)
                tutar_str = tutarlar[-2]
                bakiye_str = tutarlar[-1]
                
                print(f"Tutar string: {tutar_str}")
                print(f"Bakiye string: {bakiye_str}")
                
                try:
                    # Tutarı dönüştür
                    tutar_str = tutar_str.replace('.', '').replace(',', '.')
                    tutar = float(tutar_str)
                    print(f"Dönüştürülmüş tutar: {tutar}")
                    
                    # Bakiyeyi dönüştür
                    bakiye_str = bakiye_str.replace('.', '').replace(',', '.')
                    bakiye = float(bakiye_str)
                    print(f"Dönüştürülmüş bakiye: {bakiye}")
                except ValueError as e:
                    print(f"Sayı dönüşüm hatası: {str(e)}")
                    continue
                
                # Açıklama işleme
                aciklama = line
                aciklama = re.sub(r'\d{2}[./]\d{2}[./]\d{4}', '', aciklama)  # Tarihi çıkar
                aciklama = re.sub(r'[-]?\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s*TL', '', aciklama)  # Tutarları çıkar
                aciklama = aciklama.strip()
                print(f"Açıklama: {aciklama}")
                
                # Borç/Alacak belirleme
                borc = abs(tutar) if tutar > 0 else 0
                alacak = abs(tutar) if tutar < 0 else 0
                
                hareket = {
                    'tarih': tarih,
                    'aciklama': aciklama,
                    'borc': borc,
                    'alacak': alacak,
                    'bakiye': bakiye
                }
                hareketler.append(hareket)
                print(f"Hareket eklendi: {hareket}")
                
            except Exception as e:
                print(f"Satır işleme hatası: {e}")
                continue
        
        if not hareketler:
            return [], "PDF'den işlem çıkarılamadı"
            
        return hareketler, None
        
    except Exception as e:
        print(f"İş Bankası PDF parse hatası: {str(e)}")
        return [], f"PDF işlenirken hata oluştu: {str(e)}"

def parse_pdf_halk(page):
    """Halkbank PDF formatı için parser"""
    print("\nHALKBANK PDF İŞLENİYOR")
    
    # Önce PDF'in text içeriğini kontrol et ve karakter kodlamasını düzelt
    text = page.extract_text()
    if not text or text.isspace():
        print("HATA: PDF'den metin çıkarılamadı veya PDF boş!")
        return []
    
    # PDF'in resim içerip içermediğini kontrol et
    images = page.images
    if images:
        print(f"BİLGİ: PDF'de {len(images)} adet resim bulundu.")
        print("PDF'de resimler var ancak metin çıkarma işlemi denenecek.")
    
    print("\nPDF Text İçeriği:")
    print("=" * 50)
    print(text)
    print("=" * 50)
    
    # Satırları işle
    lines = text.split('\n')
    hareketler = []
    islem_alani = False
    
    # Başlık için olası Türkçe karakter varyasyonları
    baslik_varyasyonlari = [
        "İşlem Tarihi Valör Tarihi Açıklama İşlem Tutarı Bakiye",
        "Islem Tarihi Valör Tarihi Açıklama Islem Tutarı Bakiye",
        "İslem Tarihi Valör Tarihi Açıklama İslem Tutarı Bakiye",
        "Islem Tarihi Valor Tarihi Aciklama Islem Tutari Bakiye"
    ]
    
    # Türkçe karakter düzeltme sözlüğü - Genişletilmiş versiyon
    turkce_karakter_map = {
        # Büyük harfler
        'Ý': 'İ', 'Þ': 'Ş', 'Ð': 'Ğ', 'Ü': 'Ü', 'Ö': 'Ö', 'Ç': 'Ç', 'I': 'I',
        # Küçük harfler
        'ý': 'i', 'þ': 'ş', 'ð': 'ğ', 'ü': 'ü', 'ö': 'ö', 'ç': 'ç', 'ı': 'ı',
        # PDF'den gelen özel karakterler ve BLOB karakterleri
        '\x00': '', '\x01': '', '\x02': '', '\x03': '', '\x04': '', '\x05': '', 
        '\x06': '', '\x07': '', '\x08': '', '\x0b': '', '\x0c': '', '\x0e': '', 
        '\x0f': '', '\x10': '', '\x11': '', '\x12': '', '\x13': '', '\x14': '',
        '\x15': '', '\x16': '', '\x17': '', '\x18': '', '\x19': '', '\x1a': '',
        '\x1b': '', '\x1c': '', '\x1d': '', '\x1e': '', '\x1f': '',
        # Özel karakterler ve semboller
        '\u0080': '', '\u0081': '', '\u0082': '', '\u0083': '', '\u0084': '',
        '\u0085': '', '\u0086': '', '\u0087': '', '\u0088': '', '\u0089': '',
        '\u008a': '', '\u008b': '', '\u008c': '', '\u008d': '', '\u008e': '',
        '\u008f': '', '\u0090': '', '\u0091': '', '\u0092': '', '\u0093': '',
        '\u0094': '', '\u0095': '', '\u0096': '', '\u0097': '', '\u0098': '',
        '\u0099': '', '\u009a': '', '\u009b': '', '\u009c': '', '\u009d': '',
        '\u009e': '', '\u009f': '',
        # PDF'den gelen özel karakterler
        'ð': 'ğ', 'þ': 'ş', 'ý': 'i', 'Ý': 'İ',
        # i ve ı harfi varyasyonları
        'ī': 'i', 'ı̇': 'i', 'і': 'i', 'ĭ': 'i', 'ĩ': 'i', 'î': 'i',
        'İ': 'İ', 'I': 'I', 'Î': 'İ', 'Ī': 'İ', 'Ĭ': 'İ', 'Ĩ': 'İ',
        # Diğer özel karakterler
        'â': 'a', 'û': 'u', 'î': 'i',
        # Özel kelime düzeltmeleri
        'isyeri': 'işyeri',
        'musteri': 'müşteri',
        'komisyon': 'komisyon',
        'islemi': 'işlemi',
        'odeme': 'ödeme',
        'ucret': 'ücret',
        'havale': 'havale',
        'eft': 'EFT',
        'çekme': 'ÇEKME',
        'Çekme': 'ÇEKME'
    }
    
    def temizle_metin(metin):
        if not metin:
            return ""
        
        try:
            # Metni UTF-8'e dönüştür
            if isinstance(metin, bytes):
                metin = metin.decode('utf-8', errors='ignore')
            
            # BLOB ve binary karakterleri temizle
            temiz_metin = ""
            for karakter in metin:
                # Sadece yazdırılabilir karakterleri ve Türkçe karakterleri kabul et
                if karakter in turkce_karakter_map:
                    temiz_metin += turkce_karakter_map[karakter]
                elif karakter.isprintable():
                    temiz_metin += karakter
            
            # Özel karakter dönüşümleri
            for eski, yeni in turkce_karakter_map.items():
                temiz_metin = temiz_metin.replace(eski, yeni)
            
            # Gereksiz boşlukları temizle
            temiz_metin = ' '.join(temiz_metin.split())
            
            # ":" karakterinden sonra boşluk ekle (eğer yoksa)
            temiz_metin = re.sub(r':(?!\s)', ': ', temiz_metin)
            
            return temiz_metin
            
        except Exception as e:
            print(f"Metin temizleme hatası: {e}")
            return str(metin).strip()
    
    # Her satırı kontrol et
    for line in lines:
        line = temizle_metin(line.strip())  # Her satırı temizle
        if not line:
            continue
        
        # İşlem alanının başlangıcını bul
        if any(baslik in line for baslik in baslik_varyasyonlari):
            islem_alani = True
            continue
        
        # İşlem alanının sonunu kontrol et
        if "HESAP ÖZETİ" in line or "HESAP OZETI" in line or "Dekont yerine kullanılamaz" in line:
            islem_alani = False
            continue
        
        if not islem_alani:
            continue
        
        try:
            # Tarih kontrolü yap
            tarih_match = re.match(r'(\d{2}-\d{2}-\d{4})\s+(\d{2}-\d{2}-\d{4})', line)
            if not tarih_match:
                continue
            
            islem_tarihi_str = tarih_match.group(1)
            valor_tarihi_str = tarih_match.group(2)
            
            # Kalan metni al
            kalan_metin = line[len(tarih_match.group(0)):].strip()
            
            # Son iki sayıyı bul (İşlem Tutarı ve Bakiye)
            tutarlar = re.findall(r'-?(?:\d{1,3}\.)*\d{1,3}(?:,\d{2})?', kalan_metin)
            if len(tutarlar) < 2:
                continue
            
            islem_tutari_str = tutarlar[-2]  # Sondan bir önceki sayı
            
            # Açıklamayı al ve temizle
            aciklama = kalan_metin
            for tutar in tutarlar[-2:]:  # Son iki tutarı çıkar
                aciklama = aciklama.replace(tutar, '')
            
            # Açıklamayı temizle
            aciklama = temizle_metin(aciklama)
            
            # Debug: Açıklama metnindeki karakterleri göster
            print(f"Orijinal açıklama: {kalan_metin}")
            print(f"Temizlenmiş açıklama: {aciklama}")
            
            # Tarihleri ve tutarı işle
            islem_tarihi = datetime.strptime(islem_tarihi_str, '%d-%m-%Y').date()
            valor_tarihi = datetime.strptime(valor_tarihi_str, '%d-%m-%Y').date()
            islem_tutari = parse_amount(islem_tutari_str)
            
            # Pozitif tutar borç, negatif tutar alacak olarak kaydedilir
            if islem_tutari >= 0:
                borc = islem_tutari
                alacak = Decimal('0.0')
            else:
                borc = Decimal('0.0')
                alacak = abs(islem_tutari)
            
            hareket = {
                'tarih': islem_tarihi,
                'valor_tarihi': valor_tarihi,
                'aciklama': aciklama,
                'borc': borc,
                'alacak': alacak,
                'muhasebe_kodu': None
            }
            hareketler.append(hareket)
            print(f"Hareket eklendi: {hareket}")
            
        except Exception as e:
            print(f"Satır işleme hatası: {e}")
            continue
    
    # Hareketleri tarihe göre sırala
    hareketler.sort(key=lambda x: x['tarih'])
    
    print(f"\nToplam {len(hareketler)} hareket bulundu")
    if not hareketler:
        print("\nÖNEMLİ: Hiç hareket bulunamadı!")
        print("PDF formatı tanınamadı veya işlenebilir veri bulunamadı.")
        print("\nBeklenen format:")
        print("İşlem Tarihi | Valör Tarihi | Açıklama | İşlem Tutarı | Bakiye")
        print("02-10-2024  | 02-10-2024   | Açıklama | -664,22      | 289,68")
    
    return hareketler

def parse_pdf_ziraat(page):
    """Ziraat Bankası PDF formatı için parser"""
    print("\nZİRAAT BANKASI PDF İŞLENİYOR")
    
    # Önce PDF'in text içeriğini kontrol et
    text = page.extract_text()
    if not text or text.isspace():
        print("HATA: PDF'den metin çıkarılamadı veya PDF boş!")
        return []
    
    print("\nPDF Text İçeriği:")
    print("=" * 50)
    print(text)
    print("=" * 50)
    
    # Satırları işle
    lines = text.split('\n')
    hareketler = []
    islem_alani = False
    onceki_aciklama = None  # Önceki satırdaki açıklamayı saklamak için
    
    # Başlık için olası Türkçe karakter varyasyonları
    baslik_varyasyonlari = [
        "Tarih Referans Tutar Bakiye Açıklama",
        "Tarih Referans No Tutar Bakiye Açıklama",
        "Tarih Referans Tutar Bakiye",
        "Tarih Referans No Tutar Bakiye",
        "Tarih Referans Tutar",
        "Tarih Referans No Tutar",
        # Türkçe karakter varyasyonları
        "Tarih Referans Tutar Bakiye Aciklama",
        "Tarih Referans No Tutar Bakiye Aciklama",
        "Tarih Referans Tutar Bakiye Acıklama",
        "Tarih Referans No Tutar Bakiye Acıklama",
        # Yeni eklenen varyasyonlar
        "Tarih Ref. No Tutar Bakiye Açıklama",
        "Tarih Ref.No Tutar Bakiye Açıklama",
        "Tarih Ref No Tutar Bakiye Açıklama"
    ]
    
    # İşlem alanı sonu kontrol kelimeleri
    bitis_kelimeleri = [
        "Taraflar arasında tüm uyuşmazlıklarda",
        "Müşteri / Hesap No",
        "Musteri / Hesap No",
        "Müsteri / Hesap No",
        "Sayfa No:",
        "Dönemi:",
        "Donemi:",
        "Bakiye :",
        "KMH Limit :",
        "Kullanılabilir Bakiye :",
        "Kullanilabilir Bakiye :",
        "Devir Bakiye",
        "Dekont yerine kullanılamaz",
        "Dekont yerine kullanilamaz"
    ]
    
    # Türkçe karakter düzeltme sözlüğü
    turkce_karakter_map = {
        # Büyük harfler
        'Ý': 'İ', 'Þ': 'Ş', 'Ð': 'Ğ', 'Ü': 'Ü', 'Ö': 'Ö', 'Ç': 'Ç', 'I': 'I',
        # Küçük harfler
        'ý': 'i', 'þ': 'ş', 'ð': 'ğ', 'ü': 'ü', 'ö': 'ö', 'ç': 'ç', 'ı': 'ı',
        # PDF'den gelen özel karakterler
        'ð': 'ğ', 'þ': 'ş', 'ý': 'i', 'Ý': 'İ',
        # i ve ı harfi varyasyonları
        'ī': 'i', 'ı̇': 'i', 'і': 'i', 'ĭ': 'i', 'ĩ': 'i', 'î': 'i',
        'İ': 'İ', 'I': 'I', 'Î': 'İ', 'Ī': 'İ', 'Ĭ': 'İ', 'Ĩ': 'İ',
        # Diğer özel karakterler
        'â': 'a', 'û': 'u', 'î': 'i',
        # Özel kelime düzeltmeleri
        'isyeri': 'işyeri',
        'musteri': 'müşteri',
        'komisyon': 'komisyon',
        'islemi': 'işlemi',
        'odeme': 'ödeme',
        'ucret': 'ücret',
        'havale': 'havale',
        'eft': 'EFT',
        'çekme': 'ÇEKME',
        'Çekme': 'ÇEKME'
    }
    
    def temizle_metin(metin):
        if not metin:
            return ""
        
        try:
            # Metni UTF-8'e dönüştür
            if isinstance(metin, bytes):
                metin = metin.decode('utf-8', errors='ignore')
            
            # Orijinal metni koru
            orijinal_metin = metin
            
            # Özel karakter dönüşümleri
            for eski, yeni in turkce_karakter_map.items():
                metin = metin.replace(eski, yeni)
            
            # Gereksiz boşlukları temizle
            metin = ' '.join(metin.split())
            
            # ":" karakterinden sonra boşluk ekle (eğer yoksa)
            metin = re.sub(r':(?!\s)', ': ', metin)
            
            # Orijinal metni döndür
            return orijinal_metin
            
        except Exception as e:
            print(f"Metin temizleme hatası: {e}")
            return str(metin).strip()
    
    # Her satırı kontrol et
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        
        # İşlem alanının başlangıcını bul
        if any(baslik in line for baslik in baslik_varyasyonlari):
            islem_alani = True
            i += 1
            continue
        
        # İşlem alanının sonunu kontrol et
        if any(bitis in line for bitis in bitis_kelimeleri):
            islem_alani = False
            i += 1
            continue
        
        try:
            # Tarih ve referans kontrolü yap (Ziraat formatı: DD.MM.YY Z12345)
            tarih_match = re.match(r'(\d{2}\.\d{2}\.\d{2})\s+([A-Z]\d{5}|\d{2}\.\d{2}\.\d{2})', line)
            if not tarih_match:
                i += 1
                continue
            
            islem_tarihi_str = tarih_match.group(1)
            referans = tarih_match.group(2)
            
            # Kalan metni al
            kalan_metin = line[len(tarih_match.group(0)):].strip()
            
            # Tutarları bul
            tutarlar = re.findall(r'[-]?(?:\d{1,3}(?:[.,]\d{3})*|\d+)(?:[.,]\d{2})?', kalan_metin)
            if not tutarlar:
                i += 1
                continue
            
            # İlk tutarı al (Tutar sütunu)
            islem_tutari_str = tutarlar[0]
            
            # İlk iki tutarı ve sonrasındaki boşluğu kaldır
            if len(tutarlar) >= 2:
                # İlk iki tutarı bul ve kaldır
                ilk_tutar_index = kalan_metin.find(tutarlar[0])
                ikinci_tutar_index = kalan_metin.find(tutarlar[1], ilk_tutar_index + len(tutarlar[0]))
                if ikinci_tutar_index != -1:
                    # İkinci tutarın sonundaki boşluğa kadar olan kısmı kaldır
                    aciklama_baslangic = ikinci_tutar_index + len(tutarlar[1])
                    while aciklama_baslangic < len(kalan_metin) and kalan_metin[aciklama_baslangic].isspace():
                        aciklama_baslangic += 1
                    aciklama = kalan_metin[aciklama_baslangic:]
                else:
                    aciklama = kalan_metin
            else:
                aciklama = kalan_metin
            
            # Sonraki satırı kontrol et ve açıklamaya ekle
            if i + 1 < len(lines):
                sonraki_satir = lines[i + 1].strip()
                # Eğer sonraki satır tarih içermiyorsa ve boş değilse
                if not re.match(r'(\d{2}\.\d{2}\.\d{2})', sonraki_satir) and sonraki_satir:
                    aciklama = f"{aciklama} {sonraki_satir}"
                    i += 1  # Sonraki satırı atla
            
            # Debug: Açıklama metnini göster
            print(f"Orijinal metin: {kalan_metin}")
            print(f"Düzenlenmiş açıklama: {aciklama}")
            
            # Tarihi işle (YY formatını YYYY'ye çevir)
            yil = "20" + islem_tarihi_str[-2:]  # 24 -> 2024
            islem_tarihi = datetime.strptime(f"{islem_tarihi_str[:-2]}{yil}", '%d.%m.%Y').date()
            
            # Tutarı işle
            islem_tutari = parse_amount(islem_tutari_str)
            
            # Para çekme işlemlerini negatif yap
            if any(kelime in aciklama for kelime in ["PARA ÇEKME", "ATM PARA ÇEKME", "PARA CEKME", "ATM PARA CEKME"]):
                islem_tutari = -abs(islem_tutari)
            
            # Pozitif tutar borç, negatif tutar alacak olarak kaydedilir
            if islem_tutari >= 0:
                borc = islem_tutari
                alacak = Decimal('0.0')
            else:
                borc = Decimal('0.0')
                alacak = abs(islem_tutari)
            
            hareket = {
                'tarih': islem_tarihi,
                'valor_tarihi': islem_tarihi,  # Ziraat'te valör tarihi verilmediği için işlem tarihini kullan
                'aciklama': aciklama,  # Düzenlenmiş açıklamayı kullan
                'borc': borc,
                'alacak': alacak,
                'muhasebe_kodu': None
            }
            hareketler.append(hareket)
            print(f"Hareket eklendi: {hareket}")
            
        except Exception as e:
            print(f"Satır işleme hatası: {e}")
            
        i += 1
    
    # Hareketleri tarihe göre sırala
    hareketler.sort(key=lambda x: x['tarih'])
    
    print(f"\nToplam {len(hareketler)} hareket bulundu")
    if not hareketler:
        print("\nÖNEMLİ: Hiç hareket bulunamadı!")
        print("PDF formatı tanınamadı veya işlenebilir veri bulunamadı.")
        print("\nBeklenen format:")
        print("Tarih Referans Tutar Bakiye Açıklama")
        print("01.10.24 Z01080 154,90 229,55 İşyeri no:000000000605318...")
    
    return hareketler

def parse_pdf_vakif(page):
    """Vakıfbank PDF formatı için parser"""
    print("\nVAKIFBANK PDF İŞLENİYOR")
    
    # Önce PDF'in text içeriğini kontrol et
    text = page.extract_text()
    print("\nPDF Text İçeriği:")
    print(text)
    print("=" * 50)
    
    # Çizgileri bul
    lines = page.lines
    hareketler = []
    
    if lines:
        print(f"Bulunan çizgi sayısı: {len(lines)}")
        # Yatay çizgileri bul ve sırala
        horizontals = [line for line in lines if abs(line['top'] - line['bottom']) < 2]
        horizontals.sort(key=lambda x: x['top'])
        
        # Çizgiler arasındaki metinleri al
        for i in range(len(horizontals) - 1):
            # İki çizgi arasındaki alanı belirle
            top = horizontals[i]['top']
            bottom = horizontals[i + 1]['top']
            
            # Bu alandaki metni çıkar
            crop = page.crop((0, top, page.width, bottom))
            text = crop.extract_text()
            
            if text:
                try:
                    # Tarih, saat ve işlem numarası formatını tanımla
                    # Örnek: 02.10.2024 15:00 2024012945386976 10.000,00 78.874,08
                    pattern = r'(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})\s+(\d+)\s+([-]?\d+(?:\.\d{3})*(?:,\d{2})?)\s+([-]?\d+(?:\.\d{3})*(?:,\d{2})?)'
                    match = re.search(pattern, text)
                    
                    if match:
                        # Grupları al
                        tarih_str = match.group(1)
                        saat = match.group(2)
                        islem_no = match.group(3)
                        tutar_str = match.group(4)
                        bakiye_str = match.group(5)
                        
                        # Tarihi işle
                        tarih = parse_date(tarih_str)
                        
                        # Tutarı işle
                        tutar = parse_amount(tutar_str)
                        
                        # Açıklamayı al (eşleşen kısmı çıkar)
                        aciklama = text.replace(match.group(0), '').strip()
                        
                        # Özet satırlarını kontrol et
                        if not any(kelime in text.upper() for kelime in [
                            'TOPLAM', 'BAKİYE', 'DEVIR', 'SAYFA', 'AÇILIŞ',
                            'DEKONT YERİNE KULLANILAMAZ', 'UYUŞMAZLIK', 'BANKA KAYITLARI',
                            'WWW.VAKIFBANK.COM.TR', '444 0 724',
                            'TÜRKİYE VAKIFLAR BANKASI', 'BÜYÜK MÜKELLEFLER',
                            'FİNANSKENT MAHALLESİ', 'ÜMRANİYE', 'İSTANBUL',
                            'SİCİL NUMARASI', 'V.D.'
                        ]):
                            hareket = {
                                'tarih': tarih,
                                'aciklama': aciklama.strip(),  # Düzenlenmiş açıklamayı kullan
                                'borc': tutar if tutar and tutar >= 0 else Decimal('0.0'),
                                'alacak': abs(tutar) if tutar and tutar < 0 else Decimal('0.0'),
                                'muhasebe_kodu': None  # Muhasebe kodu için alan ekle
                            }
                            hareketler.append(hareket)
                            print(f"Hareket eklendi: {hareket}")
                    
                except Exception as e:
                    print(f"Satır işleme hatası: {e}")
                    continue
    
    # Hareketleri tarihe göre sırala
    hareketler.sort(key=lambda x: x['tarih'])
    
    print(f"\nToplam {len(hareketler)} hareket bulundu")
    return hareketler

# Diğer bankalar için benzer fonksiyonlar...

PDF_PARSERS = {
    'GARANTI': {
        'name': 'Garanti Bankası',
        'parser': parse_pdf_garanti,
        'description': 'Garanti Bankası hesap hareketleri için PDF formatı'
    },
    'YAPI_KREDI': {
        'name': 'Yapı Kredi Bankası',
        'parser': parse_pdf_yapi_kredi,
        'description': 'Yapı Kredi Bankası hesap hareketleri için PDF formatı'
    },
    'IS_BANKASI': {
        'name': 'İş Bankası',
        'parser': parse_pdf_is_bankasi,
        'description': 'İş Bankası hesap hareketleri için PDF formatı'
    },
    'VAKIF': {
        'name': 'Vakıfbank',
        'parser': parse_pdf_vakif,
        'description': 'Vakıfbank hesap hareketleri için PDF formatı'
    },
    'HALK': {
        'name': 'Halkbank',
        'parser': parse_pdf_halk,
        'description': 'Halkbank hesap hareketleri için PDF formatı'
    },
    'ZIRAAT': {
        'name': 'Ziraat Bankası',
        'parser': parse_pdf_ziraat,
        'description': 'Ziraat Bankası hesap hareketleri için PDF formatı'
    }
}

def pdf_yukle(request):
    firma_id = request.session.get('secili_firma_id')
    if not firma_id:
        messages.error(request, 'Lütfen önce firma seçiniz')
        return redirect('firma_sec')

    try:
        firma = Firma.objects.get(id=firma_id)
        bankalar = Banka.objects.filter(firma=firma, aktif=True)
        muhasebe_plani = MuhasebePlani.objects.filter(firma=firma).order_by('muhasebe_kodu')
        
        if request.method == 'POST' and request.FILES.get('pdf_dosya'):
            try:
                banka_id = request.POST.get('banka_id')
                if not banka_id:
                    return JsonResponse({'error': 'Lütfen banka seçiniz'}, status=400)
                
                banka = Banka.objects.get(id=banka_id, firma=firma)
                print(f"\nSeçilen banka: {banka.ad} ({banka.pdf_format})")
                
                # PDF format kontrolü
                if not banka.pdf_format:
                    return JsonResponse({
                        'error': 'Seçili banka hesabı için PDF formatı tanımlanmamış. ' +
                                'Lütfen önce banka hesabı ayarlarından PDF formatını belirleyin.'
                    }, status=400)
                
                # PDF formatının geçerli olup olmadığını kontrol et
                if banka.pdf_format not in PDF_PARSERS:
                    return JsonResponse({
                        'error': f'Geçersiz PDF formatı: {banka.pdf_format}. ' +
                                'Lütfen banka hesabı ayarlarından PDF formatını düzeltin.'
                    }, status=400)
                
                pdf_dosya = request.FILES['pdf_dosya']
                print(f"\nPDF dosya adı: {pdf_dosya.name}")
                
                with pdfplumber.open(pdf_dosya) as pdf:
                    print(f"\nPDF açıldı, sayfa sayısı: {len(pdf.pages)}")
                    hareketler = []
                    
                    # Banka formatına göre parser seç
                    parser = PDF_PARSERS[banka.pdf_format]['parser']
                    print(f"Seçilen banka formatı: {PDF_PARSERS[banka.pdf_format]['name']}")
                    
                    # Muhasebe tanımlarını al
                    muhasebe_tanimlari = MuhasebeTanimi.objects.filter(firma=firma)
                    
                    # Tüm sayfaları işle
                    for sayfa_no, page in enumerate(pdf.pages, 1):
                        print(f"\nSayfa {sayfa_no} işleniyor...")
                        try:
                            # Seçilen parser ile sayfayı işle
                            if banka.pdf_format == 'YAPI_KREDI':
                                sayfa_hareketleri, hata = parser(page)
                                if hata:
                                    print(f"Sayfa {sayfa_no} işlenirken hata: {hata}")
                                    return JsonResponse({'error': hata}, status=400)
                            else:
                                sayfa_hareketleri = parser(page)
                            
                            print(f"Sayfa {sayfa_no}'dan {len(sayfa_hareketleri)} hareket çıkarıldı")
                            hareketler.extend(sayfa_hareketleri)
                            
                        except Exception as e:
                            print(f"Sayfa {sayfa_no} işlenirken hata: {str(e)}")
                            continue
                    
                    if not hareketler:
                        return JsonResponse({
                            'error': 'PDF dosyasından işlem çıkarılamadı'
                        }, status=400)
                    
                    print(f"\nToplam {len(hareketler)} hareket bulundu")
                    
                    # Hareketleri tarihe göre sırala
                    hareketler.sort(key=lambda x: x['tarih'])
                    
                    # Hareketleri kaydet
                    kaydedilen = 0
                    for hareket in hareketler:
                        try:
                            # Tarihi datetime objesine çevir
                            tarih = datetime.strptime(hareket['tarih'], '%d/%m/%Y')
                            
                            # Sayısal değerleri float'a çevir
                            borc = float(hareket['borc']) if hareket['borc'] else 0
                            alacak = float(hareket['alacak']) if hareket['alacak'] else 0
                            bakiye = float(hareket.get('bakiye', 0))
                            
                            # Hareketi kaydet
                            BankaHareketi.objects.create(
                                firma=firma,
                                banka=banka,
                                tarih=tarih,
                                aciklama=hareket['aciklama'],
                                borc=borc,
                                alacak=alacak,
                                bakiye=bakiye
                            )
                            kaydedilen += 1
                            
                        except Exception as e:
                            print(f"Hareket kaydedilirken hata: {str(e)}")
                            print(f"Hatalı hareket: {hareket}")
                            continue
                    
                    print(f"\n{kaydedilen} hareket başarıyla kaydedildi")
                    
                    return JsonResponse({
                        'success': True,
                        'message': f'{kaydedilen} adet işlem başarıyla kaydedildi.'
                    })
                    
            except Banka.DoesNotExist:
                return JsonResponse({
                    'error': 'Seçili banka bulunamadı'
                }, status=400)
            except Exception as e:
                print(f"\nPDF işleme hatası: {str(e)}")
                return JsonResponse({
                    'error': f'PDF işlenirken hata oluştu: {str(e)}'
                }, status=400)
        
        return render(request, 'pdf_yukle.html', {
            'bankalar': bankalar,
            'muhasebe_plani': muhasebe_plani
        })
        
    except Firma.DoesNotExist:
        messages.error(request, 'Seçili firma bulunamadı')
        return redirect('firma_sec')

@login_required
def firma_sec(request):
    firmalar = Firma.objects.filter(kullanici=request.user)
    if request.method == 'POST':
        firma_id = request.POST.get('firma_id')
        if firma_id:
            firma = Firma.objects.get(id=firma_id, kullanici=request.user)
            request.session['secili_firma_id'] = firma.id
            request.session['secili_firma_ad'] = firma.ad
            return redirect('banka_islemleri:home')
    return render(request, 'firma_sec.html', {'firmalar': firmalar})

def hareket_filtrele(request):
    firma_id = request.session.get('secili_firma_id')
    if not firma_id:
        messages.error(request, 'Lütfen önce firma seçiniz')
        return redirect('firma_sec')

    try:
        firma = Firma.objects.get(id=firma_id)
        bankalar = Banka.objects.filter(firma=firma, aktif=True)
        
        # Filtreleri al
        banka_id = request.GET.get('banka')
        baslangic_tarihi = request.GET.get('baslangic_tarihi')
        bitis_tarihi = request.GET.get('bitis_tarihi')
        arama = request.GET.get('arama', '').strip()
        
        # Temel sorgu
        hareketler = BankaHareketi.objects.filter(firma=firma)
        
        # Banka filtresi
        if banka_id:
            hareketler = hareketler.filter(banka_id=banka_id)
        
        # Tarih filtresi
        if baslangic_tarihi:
            hareketler = hareketler.filter(tarih__gte=baslangic_tarihi)
        if bitis_tarihi:
            hareketler = hareketler.filter(tarih__lte=bitis_tarihi)
        
        # Arama filtresi
        if arama:
            hareketler = hareketler.filter(aciklama__icontains=arama)
        
        # Sıralama
        hareketler = hareketler.order_by('tarih')
        
        # Muhasebe planını al
        muhasebe_plani = MuhasebePlani.objects.filter(firma=firma)
        
        # Toplam borç ve alacak hesapla
        toplam_borc = hareketler.aggregate(Sum('borc'))['borc__sum'] or 0
        toplam_alacak = hareketler.aggregate(Sum('alacak'))['alacak__sum'] or 0
        son_bakiye = toplam_borc - toplam_alacak
        
        return render(request, 'hareket_listesi.html', {
            'hareketler': hareketler,
            'bankalar': bankalar,
            'muhasebe_plani': muhasebe_plani,
            'toplam_borc': toplam_borc,
            'toplam_alacak': toplam_alacak,
            'son_bakiye': son_bakiye,
            'selected_banka': int(banka_id) if banka_id else None,
            'baslangic_tarihi': baslangic_tarihi,
            'bitis_tarihi': bitis_tarihi,
            'arama': arama,
        })
        
    except Firma.DoesNotExist:
        messages.error(request, 'Seçili firma bulunamadı')
        return redirect('firma_sec')

@csrf_exempt
def muhasebe_tanimla(request, hareket_id):
    if request.method == 'POST':
        try:
            # Firma kontrolü
            firma_id = request.session.get('secili_firma_id')
            if not firma_id:
                return JsonResponse({'success': False, 'error': 'Lütfen önce firma seçiniz'})

            # JSON verisini al
            data = json.loads(request.body)
            muhasebe_kodu = data.get('muhasebe_kodu')
            arama_kelimesi = data.get('arama_kelimesi')

            # Hareketi bul
            hareket = BankaHareketi.objects.get(id=hareket_id, firma_id=firma_id)
            
            # Muhasebe kodunu güncelle
            hareket.muhasebe_kodu = muhasebe_kodu
            hareket.save()
            
            # Eğer arama kelimesi girildiyse:
            # 1. Muhasebe tanımını kaydet
            # 2. Aynı açıklamaya sahip diğer hareketleri güncelle
            if arama_kelimesi:
                # Önce aynı arama kelimesi var mı kontrol et
                tanim, created = MuhasebeTanimi.objects.get_or_create(
                    firma_id=firma_id,
                    arama_kelimesi=arama_kelimesi,
                    defaults={
                        'muhasebe_kodu': muhasebe_kodu,
                        'aciklama': f"Otomatik oluşturuldu: {hareket.aciklama[:50]}"
                    }
                )
                
                # Eğer tanım zaten varsa ve muhasebe kodu farklıysa güncelle
                if not created and tanim.muhasebe_kodu != muhasebe_kodu:
                    tanim.muhasebe_kodu = muhasebe_kodu
                    tanim.aciklama = f"Güncellendi: {hareket.aciklama[:50]}"
                    tanim.save()
                
                # Aynı açıklamaya sahip diğer hareketleri bul ve güncelle
                benzer_hareketler = BankaHareketi.objects.filter(
                    firma_id=firma_id,
                    aciklama__icontains=arama_kelimesi,
                    muhasebe_kodu__isnull=True  # Sadece muhasebe kodu olmayanları güncelle
                ).exclude(id=hareket_id)  # Mevcut hareketi hariç tut
                
                # Toplu güncelleme yap
                guncellenen_sayisi = benzer_hareketler.update(muhasebe_kodu=muhasebe_kodu)
                
                return JsonResponse({
                    'success': True,
                    'message': f'İşlem başarılı. {guncellenen_sayisi} benzer hareket güncellendi.'
                })
            
            return JsonResponse({'success': True})
            
        except BankaHareketi.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Hareket bulunamadı'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@csrf_exempt
def muhasebe_kodu_ekle(request):
    if request.method == 'POST':
        try:
            firma_id = request.session.get('secili_firma_id')
            if not firma_id:
                return JsonResponse({'success': False, 'error': 'Lütfen önce firma seçiniz'})

            data = json.loads(request.body)
            
            # Aynı kodun olup olmadığını kontrol et
            if MuhasebePlani.objects.filter(
                firma_id=firma_id, 
                muhasebe_kodu=data['muhasebe_kodu']
            ).exists():
                return JsonResponse({
                    'success': False, 
                    'error': 'Bu muhasebe kodu zaten mevcut'
                })

            # Yeni muhasebe kodunu kaydet
            yeni_kod = MuhasebePlani.objects.create(
                firma_id=firma_id,
                muhasebe_kodu=data['muhasebe_kodu'],
                aciklama=data['aciklama']
            )

            return JsonResponse({
                'success': True,
                'muhasebe_kodu': yeni_kod.muhasebe_kodu,
                'aciklama': yeni_kod.aciklama
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def home(request):
    if not request.session.get('secili_firma_id'):
        return redirect('banka_islemleri:firma_sec')
    return render(request, 'home.html')

def muhasebe_kodlari_aktar(request):
    firma_id = request.session.get('secili_firma_id')
    if not firma_id:
        messages.error(request, 'Lütfen önce firma seçiniz')
        return redirect('firma_sec')

    try:
        firma = Firma.objects.get(id=firma_id)
        muhasebe_kodlari = MuhasebePlani.objects.filter(firma=firma).order_by('muhasebe_kodu')
    except Firma.DoesNotExist:
        messages.error(request, 'Seçili firma bulunamadı')
        return redirect('firma_sec')

    if request.method == 'POST' and request.FILES.get('excel_dosya'):
        excel_dosya = request.FILES['excel_dosya']
        
        try:
            # Excel dosyasını oku
            df = pd.read_excel(excel_dosya)
            
            # Gerekli sütunları kontrol et
            required_columns = ['muhasebe_kodu', 'aciklama']
            if not all(col in df.columns for col in required_columns):
                messages.error(request, 'Excel dosyasında gerekli sütunlar bulunamadı.')
                return redirect('banka_islemleri:muhasebe_kodlari_aktar')
            
            # Verileri işle ve kaydet
            basarili = 0
            hatali = 0
            
            for _, row in df.iterrows():
                try:
                    MuhasebePlani.objects.create(
                        firma=firma,  # Firma'yı ekle
                        muhasebe_kodu=str(row['muhasebe_kodu']).strip(),
                        aciklama=str(row['aciklama']).strip()
                    )
                    basarili += 1
                except Exception as e:
                    print(f"Hata: {str(e)}")
                    hatali += 1
            
            messages.success(request, 
                f'Aktarım tamamlandı. {basarili} kayıt başarıyla eklendi. '
                f'{hatali} kayıt eklenemedi.')
            
        except Exception as e:
            messages.error(request, f'Dosya işlenirken hata oluştu: {str(e)}')
        
        return redirect('banka_islemleri:muhasebe_kodlari_aktar')
    
    # Template yolunu banka_islemleri/ ile başlat
    return render(request, 'muhasebe_kodlari_aktar.html', {
        'muhasebe_kodlari': muhasebe_kodlari
    })

def excel_sablon_indir(request):
    # Örnek veri oluştur
    data = {
        'muhasebe_kodu': ['100', '102', '320'],
        'aciklama': ['KASA', 'BANKALAR', 'SATICILAR']
    }
    
    # DataFrame oluştur
    df = pd.DataFrame(data)
    
    # Excel dosyası oluştur
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Muhasebe_Kodlari')
        
        # Sütun genişliklerini ayarla
        worksheet = writer.sheets['Muhasebe_Kodlari']
        worksheet.set_column('A:A', 15)  # muhasebe_kodu
        worksheet.set_column('B:B', 40)  # aciklama
    
    # Response oluştur
    excel_buffer.seek(0)
    response = HttpResponse(
        excel_buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=muhasebe_kodlari_sablon.xlsx'
    
    return response

def firma_context_processor(request):
    """Her template'e seçili firma bilgisini ekler"""
    context = {}
    if hasattr(request, 'session') and 'secili_firma_id' in request.session:
        try:
            firma = Firma.objects.get(id=request.session['secili_firma_id'])
            context['secili_firma'] = firma
        except Firma.DoesNotExist:
            pass
    return context 

@csrf_exempt
def muhasebe_kodu_duzenle(request, kod_id):
    if request.method == 'POST':
        try:
            firma_id = request.session.get('secili_firma_id')
            if not firma_id:
                return JsonResponse({'success': False, 'error': 'Lütfen önce firma seçiniz'})

            kod = MuhasebePlani.objects.get(id=kod_id, firma_id=firma_id)
            data = json.loads(request.body)
            
            kod.muhasebe_kodu = data.get('muhasebe_kodu')
            kod.aciklama = data.get('aciklama')
            kod.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@csrf_exempt
def muhasebe_kodu_sil(request, kod_id):
    if request.method == 'POST':
        try:
            firma_id = request.session.get('secili_firma_id')
            if not firma_id:
                return JsonResponse({'success': False, 'error': 'Lütfen önce firma seçiniz'})

            kod = MuhasebePlani.objects.get(id=kod_id, firma_id=firma_id)
            kod.delete()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@csrf_exempt
def banka_ekle(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            firma_id = request.session.get('secili_firma_id')
            if not firma_id:
                return JsonResponse({'success': False, 'error': 'Lütfen önce firma seçiniz'})

            # PDF format kontrolü
            pdf_format = data.get('pdf_format', '')
            if pdf_format and pdf_format not in PDF_PARSERS:
                return JsonResponse({
                    'success': False, 
                    'error': 'Geçersiz PDF formatı seçildi'
                })
            
            banka = Banka.objects.create(
                firma_id=firma_id,
                ad=data.get('ad'),
                sube=data.get('sube', ''),
                hesap_no=data.get('hesap_no', ''),
                iban=data.get('iban', ''),
                muhasebe_kodu=data.get('muhasebe_kodu', ''),
                pdf_format=pdf_format
            )
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def banka_listesi(request):
    firma_id = request.session.get('secili_firma_id')
    if not firma_id:
        messages.error(request, 'Lütfen önce firma seçiniz')
        return redirect('firma_sec')

    try:
        firma = Firma.objects.get(id=firma_id)
        bankalar = Banka.objects.filter(firma=firma).order_by('ad')
        muhasebe_plani = MuhasebePlani.objects.filter(firma=firma).order_by('muhasebe_kodu')
        
        pdf_formatlar = [
            {'key': 'GARANTI', 'name': 'Garanti Bankası', 'description': 'Garanti Bankası hesap hareketleri için PDF formatı'},
            {'key': 'YAPI_KREDI', 'name': 'Yapı Kredi Bankası', 'description': 'Yapı Kredi Bankası hesap hareketleri için PDF formatı'},
            {'key': 'IS_BANKASI', 'name': 'İş Bankası', 'description': 'İş Bankası hesap hareketleri için PDF formatı'},
            {'key': 'HALK', 'name': 'Halkbank', 'description': 'Halkbank hesap hareketleri için PDF formatı'},
            {'key': 'ZIRAAT', 'name': 'Ziraat Bankası', 'description': 'Ziraat Bankası hesap hareketleri için PDF formatı'},
            {'key': 'VAKIF', 'name': 'Vakıfbank', 'description': 'Vakıfbank hesap hareketleri için PDF formatı'}
        ]
        
        return render(request, 'banka_listesi.html', {
            'bankalar': bankalar,
            'muhasebe_plani': muhasebe_plani,
            'pdf_formatlar': pdf_formatlar
        })
        
    except Firma.DoesNotExist:
        messages.error(request, 'Seçili firma bulunamadı')
        return redirect('firma_sec')

@csrf_exempt
def banka_duzenle(request, banka_id):
    try:
        banka = Banka.objects.get(id=banka_id, firma_id=request.session.get('secili_firma_id'))
        
        if request.method == 'POST':
            data = json.loads(request.body)
            
            # PDF format kontrolü
            pdf_format = data.get('pdf_format', '').upper()  # Büyük harfe çevir
            if pdf_format and pdf_format not in PDF_PARSERS:
                return JsonResponse({
                    'success': False,
                    'error': f'Geçersiz PDF formatı. Lütfen şu formatlardan birini seçin: {", ".join(PDF_PARSERS.keys())}'
                })
            
            banka.ad = data.get('ad')
            banka.sube = data.get('sube', '')
            banka.hesap_no = data.get('hesap_no', '')
            banka.iban = data.get('iban', '')
            banka.muhasebe_kodu = data.get('muhasebe_kodu', '')
            banka.pdf_format = pdf_format
            banka.save()
            
            return JsonResponse({'success': True})
            
        # GET isteği için banka bilgilerini döndür
        return JsonResponse({
            'success': True,
            'banka': {
                'id': banka.id,
                'ad': banka.ad,
                'sube': banka.sube,
                'hesap_no': banka.hesap_no,
                'iban': banka.iban,
                'muhasebe_kodu': banka.muhasebe_kodu,
                'pdf_format': banka.pdf_format
            },
            'pdf_formatlar': [
                {'key': k, 'name': v['name'], 'description': v['description']} 
                for k, v in PDF_PARSERS.items()
            ]
        })
        
    except Banka.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Banka hesabı bulunamadı'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
def banka_durum_degistir(request, banka_id):
    if request.method == 'POST':
        try:
            firma_id = request.session.get('secili_firma_id')
            if not firma_id:
                return JsonResponse({'success': False, 'error': 'Lütfen önce firma seçiniz'})

            banka = Banka.objects.get(id=banka_id, firma_id=firma_id)
            banka.aktif = not banka.aktif
            banka.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def firma_listesi(request):
    firmalar = Firma.objects.filter(kullanici=request.user).order_by('-created_at')
    return render(request, 'firma_listesi.html', {'firmalar': firmalar})

@csrf_exempt
def firma_ekle(request):
    if request.method == 'POST':
        form = FirmaForm(request.POST)
        if form.is_valid():
            firma = form.save(commit=False)
            firma.kullanici = request.user
            firma.save()
            messages.success(request, 'Firma başarıyla eklendi.')
            return redirect('banka_islemleri:firma_sec')
    else:
        form = FirmaForm()
    return render(request, 'firma_ekle.html', {'form': form})

@csrf_exempt
def firma_duzenle(request, firma_id):
    if request.method == 'POST':
        try:
            firma = Firma.objects.get(id=firma_id)
            data = json.loads(request.body)
            
            # Vergi no kontrolü (kendi vergi nosu hariç)
            vergi_no = data.get('vergi_no')
            if Firma.objects.filter(vergi_no=vergi_no).exclude(id=firma_id).exists():
                return JsonResponse({
                    'success': False, 
                    'error': 'Bu vergi numarası ile kayıtlı başka bir firma bulunmaktadır'
                })
            
            firma.ad = data.get('ad')
            firma.vergi_no = vergi_no
            firma.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@csrf_exempt
def firma_durum_degistir(request, firma_id):
    if request.method == 'POST':
        try:
            firma = Firma.objects.get(id=firma_id)
            firma.aktif = not firma.aktif
            firma.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def muhasebe_tanimlari(request):
    firma_id = request.session.get('secili_firma_id')
    if not firma_id:
        messages.error(request, 'Lütfen önce firma seçiniz')
        return redirect('firma_sec')

    try:
        firma = Firma.objects.get(id=firma_id)
        tanimlar = MuhasebeTanimi.objects.filter(firma=firma).order_by('arama_kelimesi')
        return render(request, 'muhasebe_tanimlari.html', {
            'tanimlar': tanimlar
        })
    except Firma.DoesNotExist:
        messages.error(request, 'Seçili firma bulunamadı')
        return redirect('firma_sec')

@csrf_exempt
def muhasebe_tanimi_ekle(request):
    if request.method == 'POST':
        try:
            firma_id = request.session.get('secili_firma_id')
            if not firma_id:
                return JsonResponse({'success': False, 'error': 'Lütfen önce firma seçiniz'})

            data = json.loads(request.body)
            MuhasebeTanimi.objects.create(
                firma_id=firma_id,
                arama_kelimesi=data['arama_kelimesi'],
                muhasebe_kodu=data['muhasebe_kodu'],
                aciklama=data.get('aciklama', '')
            )
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@csrf_exempt
def muhasebe_tanimi_duzenle(request, tanim_id):
    if request.method == 'POST':
        try:
            firma_id = request.session.get('secili_firma_id')
            if not firma_id:
                return JsonResponse({'success': False, 'error': 'Lütfen önce firma seçiniz'})

            tanim = MuhasebeTanimi.objects.get(id=tanim_id, firma_id=firma_id)
            data = json.loads(request.body)
            
            tanim.arama_kelimesi = data['arama_kelimesi']
            tanim.muhasebe_kodu = data['muhasebe_kodu']
            tanim.aciklama = data.get('aciklama', '')
            tanim.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@csrf_exempt
def muhasebe_tanimi_sil(request, tanim_id):
    if request.method == 'POST':
        try:
            firma_id = request.session.get('secili_firma_id')
            if not firma_id:
                return JsonResponse({'success': False, 'error': 'Lütfen önce firma seçiniz'})

            tanim = MuhasebeTanimi.objects.get(id=tanim_id, firma_id=firma_id)
            tanim.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def muhasebe_tanimlari_ara(request):
    firma_id = request.session.get('secili_firma_id')
    if not firma_id:
        return JsonResponse({'error': 'Firma seçilmedi'}, status=400)

    q = request.GET.get('q', '').strip()
    tanimlar = MuhasebeTanimi.objects.filter(firma_id=firma_id)
    
    if q:
        tanimlar = tanimlar.filter(
            Q(arama_kelimesi__icontains=q) |
            Q(muhasebe_kodu__icontains=q) |
            Q(aciklama__icontains=q)
        )
    
    return JsonResponse(list(tanimlar.values()), safe=False)

def vakifbank_pdf_onizle(request):
    firma_id = request.session.get('secili_firma_id')
    if not firma_id:
        return JsonResponse({'error': 'Lütfen önce firma seçiniz'}, status=400)

    try:
        if request.method == 'POST' and request.FILES.get('pdf_dosya'):
            pdf_dosya = request.FILES['pdf_dosya']
            
            with pdfplumber.open(pdf_dosya) as pdf:
                hareketler = []
                
                # Tüm sayfaları işle
                for page in pdf.pages:
                    sayfa_hareketleri = parse_pdf_vakif(page)
                    hareketler.extend(sayfa_hareketleri)
                
                # Hareketleri tarihe göre sırala
                hareketler.sort(key=lambda x: x['tarih'])
                
                if not hareketler:
                    return JsonResponse({
                        'error': 'PDF dosyasından veri çıkarılamadı'
                    }, status=400)
                
                # Toplam borç, alacak ve bakiye hesapla
                toplam_borc = sum(h['borc'] for h in hareketler)
                toplam_alacak = sum(h['alacak'] for h in hareketler)
                bakiye = toplam_borc - toplam_alacak
                
                return JsonResponse({
                    'success': True,
                    'hareketler': [{
                        'tarih': h['tarih'].strftime('%d.%m.%Y'),
                        'aciklama': h['aciklama'],
                        'borc': float(h['borc']),
                        'alacak': float(h['alacak'])
                    } for h in hareketler],
                    'ozet': {
                        'hareket_sayisi': len(hareketler),
                        'toplam_borc': float(toplam_borc),
                        'toplam_alacak': float(toplam_alacak),
                        'bakiye': float(bakiye)
                    }
                })
                
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Geçersiz istek'}, status=400)

def vakifbank_pdf_onizle_sayfa(request):
    firma_id = request.session.get('secili_firma_id')
    if not firma_id:
        messages.error(request, 'Lütfen önce firma seçiniz')
        return redirect('firma_sec')

    try:
        firma = Firma.objects.get(id=firma_id)
        return render(request, 'vakifbank_pdf_onizle.html', {
            'firma': firma
        })
    except Firma.DoesNotExist:
        messages.error(request, 'Seçili firma bulunamadı')
        return redirect('firma_sec')

@csrf_exempt
def hareketleri_sil(request):
    if request.method == 'POST':
        try:
            firma_id = request.session.get('secili_firma_id')
            if not firma_id:
                return JsonResponse({'success': False, 'error': 'Lütfen önce firma seçiniz'})
            
            data = json.loads(request.body)
            hareket_idleri = data.get('hareket_idleri', [])
            
            # Hareketleri sil
            BankaHareketi.objects.filter(
                firma_id=firma_id,
                id__in=hareket_idleri
            ).delete()
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@csrf_exempt
def banka_pdf_onizle(request):
    if request.method == 'POST':
        try:
            pdf_dosya = request.FILES.get('pdf_dosya')
            banka_id = request.POST.get('banka_id')
            
            if not pdf_dosya or not banka_id:
                return JsonResponse({'error': 'PDF dosyası ve banka seçimi gereklidir.'}, status=400)
            
            # Banka bilgilerini al
            try:
                banka = Banka.objects.get(id=banka_id)
            except Banka.DoesNotExist:
                return JsonResponse({'error': 'Seçilen banka bulunamadı.'}, status=400)
            
            # PDF formatını kontrol et
            if not banka.pdf_format:
                return JsonResponse({'error': 'Banka için PDF formatı tanımlanmamış.'}, status=400)
            
            # PDF formatını parantez içindeki değere göre ayarla
            pdf_format = banka.pdf_format
            if '(' in pdf_format and ')' in pdf_format:
                pdf_format = pdf_format[pdf_format.find('(')+1:pdf_format.find(')')]
            
            # PDF parser'ı kontrol et
            if pdf_format not in PDF_PARSERS:
                return JsonResponse({'error': 'Bu banka için PDF parser bulunamadı.'}, status=400)
            
            # PDF'i işle
            try:
                with pdfplumber.open(pdf_dosya) as pdf:
                    hareketler = []
                    for page in pdf.pages:
                        parser = PDF_PARSERS[pdf_format]['parser']
                        page_hareketler, hata = parser(page)
                        if hata:
                            return JsonResponse({'error': hata}, status=400)
                        hareketler.extend(page_hareketler)
                    
                    if not hareketler:
                        return JsonResponse({'error': 'PDF\'den işlem çıkarılamadı.'}, status=400)
                    
                    return JsonResponse({
                        'success': True,
                        'hareketler': hareketler
                    })
                    
            except Exception as e:
                print(f"PDF işleme hatası: {str(e)}")
                return JsonResponse({'error': f'PDF işlenirken hata oluştu: {str(e)}'}, status=400)
                
        except Exception as e:
            print(f"Genel hata: {str(e)}")
            return JsonResponse({'error': f'Bir hata oluştu: {str(e)}'}, status=400)
    
    return JsonResponse({'error': 'Geçersiz istek metodu.'}, status=400)

def banka_pdf_onizle_sayfa(request, banka_id):
    firma_id = request.session.get('secili_firma_id')
    if not firma_id:
        messages.error(request, 'Lütfen önce firma seçiniz')
        return redirect('firma_sec')

    try:
        firma = Firma.objects.get(id=firma_id)
        banka = Banka.objects.get(id=banka_id, firma=firma)
        return render(request, 'banka_pdf_onizle.html', {
            'firma': firma,
            'banka': banka
        })
    except (Firma.DoesNotExist, Banka.DoesNotExist):
        messages.error(request, 'Seçili firma veya banka bulunamadı')
        return redirect('banka_listesi')

def muhasebe_fisi_aktar(request):
    firma_id = request.session.get('secili_firma_id')
    if not firma_id:
        return JsonResponse({'error': 'Lütfen önce firma seçiniz'}, status=400)

    try:
        banka_id = request.GET.get('banka_id')
        if not banka_id:
            return JsonResponse({'error': 'Lütfen banka seçiniz'}, status=400)

        # Banka ve firma kontrolü
        banka = Banka.objects.get(id=banka_id, firma_id=firma_id)
        
        # Tarih filtrelerini al
        baslangic_tarihi = request.GET.get('baslangic_tarihi')
        bitis_tarihi = request.GET.get('bitis_tarihi')
        
        # Banka hareketlerini al
        hareketler = BankaHareketi.objects.filter(
            firma_id=firma_id,
            banka_id=banka_id
        )
        
        # Tarih filtrelerini uygula
        if baslangic_tarihi:
            hareketler = hareketler.filter(tarih__gte=baslangic_tarihi)
        if bitis_tarihi:
            hareketler = hareketler.filter(tarih__lte=bitis_tarihi)
            
        hareketler = hareketler.order_by('tarih')
        
        # Muhasebe kodu eksik olan hareketleri kontrol et
        eksik_kodlu_hareketler = hareketler.filter(muhasebe_kodu__isnull=True)
        if eksik_kodlu_hareketler.exists():
            eksik_listesi = [
                {
                    'tarih': h.tarih.strftime('%d.%m.%Y'),
                    'aciklama': h.aciklama,
                    'tutar': float(h.borc if h.borc > 0 else h.alacak)
                }
                for h in eksik_kodlu_hareketler
            ]
            return JsonResponse({
                'error': 'Muhasebe kodu tanımlanmamış hareketler var',
                'eksik_hareketler': eksik_listesi
            }, status=400)
        
        # Hareketleri tarihe göre grupla
        tarih_gruplari = {}
        for hareket in hareketler:
            tarih = hareket.tarih
            if tarih not in tarih_gruplari:
                tarih_gruplari[tarih] = []
            tarih_gruplari[tarih].append(hareket)
        
        # Excel dosyası oluştur
        excel_buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(excel_buffer)
        worksheet = workbook.add_worksheet('Muhasebe Fişi')
        
        # Başlık formatları
        baslik_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        # Hücre formatları
        tarih_format = workbook.add_format({
            'num_format': 'dd.mm.yyyy',
            'align': 'center',
            'border': 1
        })
        metin_format = workbook.add_format({
            'align': 'left',
            'border': 1
        })
        sayi_format = workbook.add_format({
            'num_format': '#,##0.00',
            'align': 'right',
            'border': 1
        })
        
        # Başlıkları yaz
        headers = ['Tarih', 'Hesap Kodu', 'Açıklama', 'Borç', 'Alacak']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, baslik_format)
        
        # Sütun genişliklerini ayarla
        worksheet.set_column('A:A', 12)  # Tarih
        worksheet.set_column('B:B', 15)  # Hesap Kodu
        worksheet.set_column('C:C', 50)  # Açıklama
        worksheet.set_column('D:E', 15)  # Borç ve Alacak
        
        # Verileri yaz
        row = 1
        for tarih, hareket_listesi in sorted(tarih_gruplari.items()):
            for hareket in hareket_listesi:
                # Banka hesabı hareketi
                worksheet.write(row, 0, tarih, tarih_format)
                worksheet.write(row, 1, banka.muhasebe_kodu, metin_format)
                worksheet.write(row, 2, hareket.aciklama, metin_format)
                worksheet.write(row, 3, float(hareket.borc), sayi_format)
                worksheet.write(row, 4, float(hareket.alacak), sayi_format)
                row += 1
                
                # Karşı hesap hareketi
                worksheet.write(row, 0, tarih, tarih_format)
                worksheet.write(row, 1, hareket.muhasebe_kodu, metin_format)
                worksheet.write(row, 2, hareket.aciklama, metin_format)
                worksheet.write(row, 3, float(hareket.alacak), sayi_format)
                worksheet.write(row, 4, float(hareket.borc), sayi_format)
                row += 1
        
        workbook.close()
        
        # Response oluştur
        excel_buffer.seek(0)
        response = HttpResponse(
            excel_buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        # Dosya adını oluştur
        dosya_adi = f'muhasebe_fisi_{banka.ad}_{banka.hesap_no}'
        if baslangic_tarihi:
            baslangic = datetime.strptime(baslangic_tarihi, '%Y-%m-%d').strftime('%d_%m_%Y')
            dosya_adi += f'_{baslangic}'
        if bitis_tarihi:
            bitis = datetime.strptime(bitis_tarihi, '%Y-%m-%d').strftime('%d_%m_%Y')
            dosya_adi += f'_{bitis}'
        dosya_adi += '.xlsx'
        
        # Türkçe karakterleri ve boşlukları düzelt
        dosya_adi = dosya_adi.replace(' ', '_').replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c').replace('İ', 'I')
        
        response['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'{dosya_adi}'
        
        return response
        
    except Banka.DoesNotExist:
        return JsonResponse({'error': 'Seçili banka bulunamadı'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400) 

def banka_tarih_araligi(request):
    """Seçilen bankanın hareket tarih aralığını döndürür."""
    try:
        banka_id = request.GET.get('banka_id')
        firma_id = request.session.get('secili_firma_id')
        
        if not banka_id or not firma_id:
            return JsonResponse({'error': 'Geçersiz istek'}, status=400)
            
        hareketler = BankaHareketi.objects.filter(
            banka_id=banka_id,
            firma_id=firma_id
        ).aggregate(
            ilk_tarih=Min('tarih'),
            son_tarih=Max('tarih')
        )
        
        return JsonResponse({
            'success': True,
            'ilk_tarih': hareketler['ilk_tarih'].strftime('%Y-%m-%d') if hareketler['ilk_tarih'] else None,
            'son_tarih': hareketler['son_tarih'].strftime('%Y-%m-%d') if hareketler['son_tarih'] else None
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)