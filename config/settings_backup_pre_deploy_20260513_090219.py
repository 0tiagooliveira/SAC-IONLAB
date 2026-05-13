from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-dev-only-change-me')
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.security.UsuarioSistemaPermissaoMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.menu_lateral_sac',
                'core.context_processors.indicadores_globais_sac',
                'core.context_processors.menu_setores',
                'core.context_processors.fila_inteligente',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'sac_intranet'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', '123456'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/intra/'
LOGOUT_REDIRECT_URL = '/login/'

# ==========================
# E-mail / Alertas automáticos
# ==========================
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False').lower() == 'true'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'no-reply@ionlab.local')
SERVER_EMAIL = os.environ.get('SERVER_EMAIL', DEFAULT_FROM_EMAIL)

# Frequência/limiares de SLA
SLA_ALERTA_AMARELO_HORAS = int(os.environ.get('SLA_ALERTA_AMARELO_HORAS', '12'))
SLA_ALERTA_VERMELHO_HORAS = int(os.environ.get('SLA_ALERTA_VERMELHO_HORAS', '24'))
SLA_ALERTA_REINCIDENCIA_HORAS = int(os.environ.get('SLA_ALERTA_REINCIDENCIA_HORAS', '48'))

# Endereços internos padrão (separados por vírgula)
ALERTAS_EMAILS_INTERNOS = [
    item.strip() for item in os.environ.get('ALERTAS_EMAILS_INTERNOS', '').split(',') if item.strip()
]
