# config/settings.py
import os
from pathlib import Path
from decouple import config
import json

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='your-secret-key-here')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'apps.blockchain',
    'apps.prescriptions',
    'apps.ai_engine',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

ML_MODELS_PATH = os.path.join(
    BASE_DIR, 'apps', 'ml_prediction', 'ml_models'
)

# ============================================
# FIX 1 - UNIFIED BLOCKCHAIN CONFIGURATION
# Single config dict used by ALL files
# ============================================
def load_contract_abi():
    """Always load from Path1 — Hardhat compiled artifact"""
    # Path1 — always use this (freshest ABI)
    path1 = (
        BASE_DIR / 'artifacts' / 'contracts' /
        'PrescriptionStorage.sol' / 'PrescriptionStorage.json'
    )
    # Path2 — fallback only
    path2 = (
        BASE_DIR / 'apps' / 'blockchain' /
        'contracts' / 'PrescriptionStorage.json'
    )

    abi_path = path1 if path1.exists() else (
        path2 if path2.exists() else None
    )

    if not abi_path:
        print('WARNING: ABI not found. Run: npx hardhat compile')
        return []

    with open(abi_path, 'r') as f:
        artifact = json.load(f)
        abi = artifact.get('abi', [])

    # Verify critical functions exist
    fn_names = [
        item['name'] for item in abi
        if item.get('type') == 'function'
    ]
    print(f'ABI loaded from: {abi_path}')
    print(f'Functions: {fn_names}')

    if 'isDoctor' not in fn_names:
        print('WARNING: isDoctor missing. Run: npx hardhat compile')

    return abi


BLOCKCHAIN_CONFIG = {
    'RPC_URL': config(
        'BLOCKCHAIN_RPC_URL',
        default='http://127.0.0.1:8545'  # ← Fixed: was 7545
    ),
    'CHAIN_ID':          config('CHAIN_ID', default=1337, cast=int),
    'CONTRACT_ADDRESS':  config('CONTRACT_ADDRESS', default=''),
    'PRIVATE_KEY':       config('PRIVATE_KEY', default=''),
    'CONTRACT_ABI':      load_contract_abi(),
    'GAS_LIMIT':         500000,
    'GAS_MULTIPLIER':    1.2,
}

BLOCKCHAIN_MODE     = 'HYBRID'
BLOCKCHAIN_NODE_URL = BLOCKCHAIN_CONFIG['RPC_URL']
CONTRACT_ADDRESS    = BLOCKCHAIN_CONFIG['CONTRACT_ADDRESS']
CONTRACT_ABI        = BLOCKCHAIN_CONFIG['CONTRACT_ABI']
# Login redirects
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# CSRF for fetch() API calls from templates
CSRF_COOKIE_HTTPONLY = False  # JS must read this
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# Session security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
