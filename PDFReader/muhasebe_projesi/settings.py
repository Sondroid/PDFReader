INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'banka_islemleri',  # Yeni eklenen uygulama
]

# ... diğer ayarlar ...

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Template dizini eklendi
        'APP_DIRS': True,
        # ... diğer ayarlar ...
    },
] 