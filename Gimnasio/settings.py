"""
Django settings for Gimnasio project.
"""
import os
from pathlib import Path
import dj_database_url  # Librería para conectar la BD de Neon

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# SEGURIDAD Y ENTORNO
# ==============================================================================

# Clave secreta: En producción la tomará de Render, en local usa la insegura
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-=z4&=g+wg@8lu&kr$1ag3@eqm=0r$0s7*bmzf*c1ved)w4hl@b')

# DEBUG: False si estamos en Render, True si estamos en local
DEBUG = 'RENDER' not in os.environ

# Permitir hosts: Necesario para que Render funcione
ALLOWED_HOSTS = ['*']

# ==============================================================================
# APLICACIONES E INSTALACIÓN
# ==============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'Clientes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # <--- IMPORTANTE: Whitenoise para estilos en la nube
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'Gimnasio.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'Gimnasio.wsgi.application'

# ==============================================================================
# BASE DE DATOS (CONFIGURACIÓN HÍBRIDA)
# ==============================================================================

# Si existe DATABASE_URL en las variables de entorno (Render/Neon), usa PostgreSQL.
# Si no existe, usa MySQL (Tu XAMPP local).

if 'DATABASE_URL' in os.environ:
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL'),
            conn_max_age=600
        )
    }
else:
    # Configuración Local (XAMPP/MySQL)
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': 'GimnasioDB',
                'USER': 'root',
                'PASSWORD': ''
            }
        }
    except ImportError:
        # Fallback por si pymysql no está instalado en algún entorno
        pass

# ==============================================================================
# VALIDACIÓN DE PASSWORD
# ==============================================================================

AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]

# ==============================================================================
# IDIOMA Y ZONA HORARIA
# ==============================================================================

LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

# ==============================================================================
# ARCHIVOS ESTÁTICOS (CSS, JS, IMAGES)
# ==============================================================================

STATIC_URL = 'static/'

# Carpeta donde buscarás tus estáticos en desarrollo
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')] # Corregido de STATICFILES_DIR a STATICFILES_DIRS

# Carpeta donde Whitenoise/Django recolectará todo para producción
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Configuración de almacenamiento para Whitenoise (Compresión y Cache)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ==============================================================================
# ARCHIVOS MEDIA (SUBIDAS DE USUARIOS)
# ==============================================================================

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'Clientes', 'media')

# ==============================================================================
# CONFIGURACIÓN PERSONALIZADA (USUARIOS, EMAIL, LOGIN)
# ==============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'Clientes.CustomUser'

# Custom Authentication Backend
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',  # Para /admin
    'Clientes.backends.RUTorEmailBackend',        # Para login con RUT/Email
]

# Login redirect
LOGIN_URL = '/'
LOGIN_REDIRECT_URL = '/'

# Configuración de Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'alextheprolapz@gmail.com'
EMAIL_HOST_PASSWORD = 'wsvv idno esbi fyjn'
DEFAULT_FROM_EMAIL = 'ClubHouse Digital <alextheprolapz@gmail.com>'