# Generated by Django 5.1.6 on 2025-03-04 14:43

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Banka',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ad', models.CharField(max_length=100, verbose_name='Banka Adı')),
                ('sube', models.CharField(blank=True, max_length=100, verbose_name='Şube')),
                ('hesap_no', models.CharField(blank=True, max_length=50, verbose_name='Hesap No')),
                ('iban', models.CharField(blank=True, max_length=50, verbose_name='IBAN')),
                ('muhasebe_kodu', models.CharField(blank=True, max_length=20, verbose_name='Muhasebe Kodu')),
                ('aktif', models.BooleanField(default=True, verbose_name='Aktif')),
                ('aciklama', models.TextField(blank=True, verbose_name='Açıklama')),
                ('olusturma_tarihi', models.DateTimeField(auto_now_add=True)),
                ('pdf_format', models.CharField(choices=[('GARANTI', 'Garanti Bankası'), ('YAPI_KREDI', 'Yapı Kredi Bankası'), ('IS_BANKASI', 'İş Bankası'), ('ZIRAAT', 'Ziraat Bankası'), ('HALK', 'Halk Bankası'), ('VAKIF', 'Vakıfbank'), ('DIGER', 'Diğer')], default='DIGER', max_length=20, verbose_name='PDF Format')),
            ],
            options={
                'verbose_name': 'Banka',
                'verbose_name_plural': 'Bankalar',
                'ordering': ['ad', 'sube'],
            },
        ),
        migrations.CreateModel(
            name='Firma',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ad', models.CharField(max_length=100)),
                ('vergi_no', models.CharField(max_length=11, unique=True)),
                ('adres', models.TextField(blank=True)),
                ('telefon', models.CharField(blank=True, max_length=20)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('aktif', models.BooleanField(default=True)),
                ('kullanici', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='firmalar', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Firma',
                'verbose_name_plural': 'Firmalar',
                'ordering': ['ad'],
            },
        ),
        migrations.CreateModel(
            name='BankaHareketi',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tarih', models.DateField()),
                ('aciklama', models.CharField(max_length=200)),
                ('borc', models.DecimalField(decimal_places=2, max_digits=10)),
                ('alacak', models.DecimalField(decimal_places=2, max_digits=10)),
                ('bakiye', models.DecimalField(decimal_places=2, max_digits=10)),
                ('muhasebe_kodu', models.CharField(blank=True, max_length=20, null=True)),
                ('banka', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hareketler', to='banka_islemleri.banka')),
                ('firma', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='banka_hareketleri', to='banka_islemleri.firma')),
            ],
            options={
                'verbose_name': 'Banka Hareketi',
                'verbose_name_plural': 'Banka Hareketleri',
                'ordering': ['-tarih'],
            },
        ),
        migrations.AddField(
            model_name='banka',
            name='firma',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bankalar', to='banka_islemleri.firma'),
        ),
        migrations.AlterUniqueTogether(
            name='banka',
            unique_together={('firma', 'iban')},
        ),
        migrations.CreateModel(
            name='MuhasebePlani',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('muhasebe_kodu', models.CharField(max_length=20)),
                ('aciklama', models.CharField(max_length=200)),
                ('firma', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='muhasebe_plani', to='banka_islemleri.firma')),
            ],
            options={
                'verbose_name': 'Muhasebe Planı',
                'verbose_name_plural': 'Muhasebe Planı',
                'ordering': ['muhasebe_kodu'],
                'unique_together': {('firma', 'muhasebe_kodu')},
            },
        ),
        migrations.CreateModel(
            name='MuhasebeTanimi',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('arama_kelimesi', models.CharField(max_length=100)),
                ('muhasebe_kodu', models.CharField(max_length=20)),
                ('aciklama', models.TextField()),
                ('firma', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='muhasebe_tanimlari', to='banka_islemleri.firma')),
            ],
            options={
                'verbose_name': 'Muhasebe Tanımı',
                'verbose_name_plural': 'Muhasebe Tanımları',
                'unique_together': {('firma', 'arama_kelimesi')},
            },
        ),
    ]
