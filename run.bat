@echo off
echo PDFReader3 programi baslatiliyor...
echo.

REM Sanal ortami aktif et
call .\venv\Scripts\activate.bat

REM Gerekli paketleri kontrol et ve yukle
echo Gerekli paketler kontrol ediliyor...
python -m pip install --upgrade pip
pip install django django-bootstrap5 xlsxwriter pandas pdfplumber requests

REM Veritabani migrationlarini uygula
echo Veritabani guncelleniyor...
python manage.py migrate

REM Statik dosyalari topla
echo Statik dosyalar toplaniyor...
python manage.py collectstatic --noinput

REM Sunucuyu baslat
echo.
echo Sunucu baslatiliyor...
echo Program hazir oldugunda tarayicinizda http://127.0.0.1:8000 adresini acin
echo Programi kapatmak icin bu pencereyi kapatabilirsiniz
echo.
python manage.py runserver

pause 