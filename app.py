from flask import Flask, Response, abort, render_template, redirect, url_for, request, jsonify, flash, send_file, session as flask_session
from flask.typing import ResponseReturnValue
from flask_sqlalchemy import SQLAlchemy
from flask_assets import Environment
from webassets.bundle import Bundle
from flask_compress import Compress
from flask_mail import Mail, Message
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta
import math
import os
import json
import ast
import base64
import sys
import shutil
import uuid
import secrets
import hmac
import hashlib
import logging
import threading
import time
import unicodedata
import csv
import zipfile
import urllib.request
import urllib.error
import stripe
from stripe import error as stripe_error
from typing import Any, Mapping, Optional, Tuple, cast
from xml.sax.saxutils import escape as xml_escape

# Para compatibilidade, criar alias
SignatureVerificationError = stripe_error.SignatureVerificationError  # type: ignore[attr-defined]

import pytz
import bleach
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from user_agents import parse as parse_ua

# Importar correções de compatibilidade Flask 3.x (módulo opcional)
try:
    from flask3_compat import fix_importlib_warnings  # type: ignore[import-not-found]
    fix_importlib_warnings()
except ImportError:
    pass

from werkzeug.security import generate_password_hash, check_password_hash
# Importar url_parse baseado na versão disponível
from urllib.parse import quote, urlparse as url_parse
from itsdangerous import URLSafeTimedSerializer as Serializer
import re
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from PIL import Image, ImageOps
from PIL.Image import Resampling
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
import cloudinary.api
from services.entitlement_service import (
    PLAN_ENTITLEMENTS,
    can_request_priority_content,
    can_use_public_chat,
    get_plan_entitlements as resolve_plan_entitlements,
)
from technical_content.content import build_post_copy, category_for_file_type
from technical_content.parsers import (
    ArchiveSafetyError,
    format_board_code,
    inspect_zip_archive,
    normalize_board_code,
    parse_technical_filename,
    sha256_file,
)
from technical_content.storage import (
    HttpStorageProvider,
    StorageError,
    filename_from_content_disposition,
    sanitize_download_name,
)
from technical_content.datasheets.normalization import (
    looks_like_part_number,
    normalize_manufacturer as normalize_component_manufacturer,
    normalize_part_number as normalize_component_part_number,
    safe_slug as datasheet_safe_slug,
)
from technical_content.datasheets.policy import persistence_policy, publication_policy
from technical_content.datasheets.services.translation import generate_component_summary, translate_specifications
from sqlalchemy.exc import IntegrityError
try:
    import firebase_admin
    from firebase_admin import credentials, auth as firebase_auth, firestore as firebase_firestore
except Exception:  # pragma: no cover - fallback quando dependência não está instalada
    firebase_admin = None
    credentials = None
    firebase_auth = None
    firebase_firestore = None

try:
    from google.cloud.firestore_v1 import FieldFilter as FirestoreFieldFilter
except Exception:  # pragma: no cover - compatibilidade quando Firestore não está instalado
    FirestoreFieldFilter = None

try:
    from google.api_core import exceptions as google_api_exceptions
except Exception:  # pragma: no cover - compatibilidade quando google-api-core não está instalado
    google_api_exceptions = None

try:
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_auth_requests
except Exception:  # pragma: no cover - fallback quando dependência não está instalada
    google_id_token = None
    google_auth_requests = None

# Verificar versão do Python e ajustar configurações
python_version = sys.version_info
if python_version.major == 3 and python_version.minor >= 13:
    # Ajustes para Python 3.13+
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    # Desativa algumas funcionalidades avançadas de tipagem que podem causar problemas
    os.environ['SQLALCHEMY_WARN_20'] = '1'

# Carregar variáveis de ambiente
load_dotenv()
DEFAULT_SUPPORT_EMAIL = os.environ.get('SUPPORT_EMAIL', 'suporte@mundodainformatica.com').strip() or 'suporte@mundodainformatica.com'

def is_production_environment():
    """Detecta ambiente de produção com a convenção oficial do projeto."""
    return os.environ.get('FLASK_ENV') == 'production' or bool(os.environ.get('RENDER'))


# Verificar se está em modo debug
DEBUG_MODE = not is_production_environment()

def debug_log(message):
    """Log apenas em modo de desenvolvimento"""
    if DEBUG_MODE:
        print(f"[DEBUG] {message}")

class AbacatePayAPIError(Exception):
    """Erro normalizado para respostas da API AbacatePay."""

    def __init__(self, message, status_code=None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


def get_abacatepay_api_url(path):
    base_url = (app.config.get('ABACATEPAY_API_URL') or '').rstrip('/')
    return f"{base_url}/{path.lstrip('/')}"


def get_abacatepay_headers():
    api_key = (app.config.get('ABACATEPAY_API_KEY') or '').strip()
    if not api_key:
        raise AbacatePayAPIError('Chave da AbacatePay não configurada.')
    return {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }


def get_abacatepay_error_message(payload, fallback):
    if isinstance(payload, dict):
        error = payload.get('error')
        if isinstance(error, dict):
            return error.get('message') or error.get('code') or json.dumps(error, ensure_ascii=False)
        if error:
            return str(error)
    return fallback


def abacatepay_request(method, path, **kwargs):
    import requests

    response = requests.request(
        method,
        get_abacatepay_api_url(path),
        headers=get_abacatepay_headers(),
        timeout=kwargs.pop('timeout', 15),
        **kwargs,
    )

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    success = payload.get('success') if isinstance(payload, dict) else None
    error = payload.get('error') if isinstance(payload, dict) else None
    if response.status_code >= 400 or success is False or error:
        message = get_abacatepay_error_message(payload, 'Erro ao consultar a AbacatePay.')
        raise AbacatePayAPIError(message, status_code=response.status_code, payload=payload)

    if not isinstance(payload, dict):
        raise AbacatePayAPIError('Resposta inválida da AbacatePay.', status_code=response.status_code)

    return payload.get('data') or {}


def build_abacatepay_customer(user):
    customer = {
        'name': (getattr(user, 'name', None) or getattr(user, 'username', '') or 'Cliente').strip(),
        'email': (getattr(user, 'email', '') or '').strip(),
    }
    phone = re.sub(r'\D+', '', getattr(user, 'phone', '') or '')
    if phone:
        customer['cellphone'] = phone
    return {key: value for key, value in customer.items() if value}


def verify_abacatepay_signature(raw_body, signature_from_header):
    public_key = (app.config.get('ABACATEPAY_PUBLIC_KEY') or '').strip()
    if not public_key or not signature_from_header:
        return False
    expected = hmac.new(
        public_key.encode('utf-8'),
        raw_body,
        hashlib.sha256,
    ).digest()
    expected_b64 = base64.b64encode(expected).decode('utf-8')
    return hmac.compare_digest(expected_b64, signature_from_header)


def verify_abacatepay_webhook_request(raw_body: bytes) -> Optional[ResponseReturnValue]:
    webhook_secret = (app.config.get('ABACATEPAY_WEBHOOK_SECRET') or '').strip()
    if webhook_secret:
        received_secret = (request.args.get('webhookSecret') or '').strip()
        if not hmac.compare_digest(received_secret, webhook_secret):
            return jsonify({'error': 'Unauthorized'}), 401

    signature = request.headers.get('X-Webhook-Signature', '')
    if signature and not verify_abacatepay_signature(raw_body, signature):
        return jsonify({'error': 'Invalid signature'}), 400

    if webhook_secret and not signature and is_production_environment():
        return jsonify({'error': 'Missing signature'}), 400

    return None


def get_abacatepay_remote_id(transaction):
    return transaction.abacatepay_charge_id or (
        transaction.abacatepay_billing_id
        if transaction.abacatepay_billing_id and transaction.abacatepay_billing_id.startswith(('pix_char_', 'char_', 'bole_'))
        else None
    )


def sync_abacatepay_transaction_status(transaction, charge_data):
    status = str((charge_data or {}).get('status') or '').upper()
    if status in {'PAID', 'COMPLETE', 'COMPLETED'}:
        handle_abacatepay_payment_success(transaction, charge_data)
    elif status in {'REFUNDED'}:
        handle_abacatepay_payment_refunded(transaction, charge_data)
    elif status in {'EXPIRED', 'FAILED', 'LOST'}:
        handle_abacatepay_payment_failed(transaction, charge_data)
    elif status == 'CANCELLED' and transaction.status != 'completed':
        transaction.status = 'cancelled'
        db.session.commit()


def find_abacatepay_transaction(charge_id=None, external_id=None):
    if charge_id:
        transaction = Transaction.query.filter_by(abacatepay_charge_id=charge_id).first()
        if transaction:
            return transaction
        transaction = Transaction.query.filter_by(abacatepay_billing_id=charge_id).first()
        if transaction:
            return transaction

    if external_id:
        return Transaction.query.filter_by(abacatepay_billing_id=external_id).first()

    return None

# Configuração da aplicação Flask
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Usar SECRET_KEY forte - obrigatório em produção
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    if is_production_environment():
        raise ValueError('SECRET_KEY deve ser definida em produção!')
    secret_key = 'dev_key_5f352a14cb7e4b119811'
app.config['SECRET_KEY'] = secret_key

# Configurações de segurança de sessão
app.config['SESSION_COOKIE_SECURE'] = is_production_environment()  # HTTPS apenas em produção
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Não acessível via JavaScript
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Proteção CSRF
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # Sessão expira em 24h
app.config['SUPPORT_EMAIL'] = DEFAULT_SUPPORT_EMAIL
app.config['SITE_URL'] = (
    os.environ.get('SITE_URL')
    or os.environ.get('BASE_URL')
    or os.environ.get('PUBLIC_URL')
    or os.environ.get('RENDER_EXTERNAL_URL')
    or ''
)

# Configuração do Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
app.config['STRIPE_PUBLIC_KEY'] = os.environ.get('STRIPE_PUBLIC_KEY')

# Configuração do Meta Pixel (Facebook) - Conversions API
app.config['META_PIXEL_ID'] = os.environ.get('META_PIXEL_ID', '')
app.config['META_ACCESS_TOKEN'] = os.environ.get('META_ACCESS_TOKEN')

# Configuração Firebase (Google Sign-In)
app.config['FIREBASE_API_KEY'] = os.environ.get('FIREBASE_API_KEY', '')
app.config['FIREBASE_AUTH_DOMAIN'] = os.environ.get('FIREBASE_AUTH_DOMAIN', '')
app.config['FIREBASE_PROJECT_ID'] = os.environ.get('FIREBASE_PROJECT_ID', '')
app.config['FIREBASE_STORAGE_BUCKET'] = os.environ.get('FIREBASE_STORAGE_BUCKET', '')
app.config['FIREBASE_MESSAGING_SENDER_ID'] = os.environ.get('FIREBASE_MESSAGING_SENDER_ID', '')
app.config['FIREBASE_APP_ID'] = os.environ.get('FIREBASE_APP_ID', '')
app.config['FIREBASE_MEASUREMENT_ID'] = os.environ.get('FIREBASE_MEASUREMENT_ID', '')
app.config['FIREBASE_SERVICE_ACCOUNT_PATH'] = os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH', '')
app.config['FIREBASE_SERVICE_ACCOUNT_JSON'] = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON', '')

# Configuração do Abacate Pay
app.config['ABACATEPAY_API_KEY'] = os.environ.get('ABACATEPAY_API_KEY')
app.config['ABACATEPAY_API_URL'] = os.environ.get('ABACATEPAY_API_URL', 'https://api.abacatepay.com/v2').rstrip('/')
app.config['ABACATEPAY_WEBHOOK_SECRET'] = os.environ.get('ABACATEPAY_WEBHOOK_SECRET', '')
app.config['ABACATEPAY_PUBLIC_KEY'] = os.environ.get('ABACATEPAY_PUBLIC_KEY', '')

# Configuração do Cloudinary
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True
)

# Garantir que o diretório instance existe
os.makedirs(app.instance_path, exist_ok=True)

# Banco configurável: SQLite é o padrão atual e PostgreSQL permanece compatível.
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    # Desenvolvimento: caminho relativo local
    database_url = f'sqlite:///{os.path.join(app.instance_path, "site.db")}'

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)
app.logger.info("Banco de dados configurado com o driver %s", database_url.split(':', 1)[0])

# Configurações específicas do SQLite
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Configuração de e-mail
app.config['MAIL_SERVER'] = (os.environ.get('MAIL_SERVER') or '').strip() or None
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', '587'))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('true', '1', 'yes', 'y', 'on')
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'false').lower() in ('true', '1', 'yes', 'y', 'on')
app.config['MAIL_USERNAME'] = (os.environ.get('MAIL_USERNAME') or '').strip() or None
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = (
    (os.environ.get('MAIL_DEFAULT_SENDER') or '').strip()
    or app.config['MAIL_USERNAME']
    or DEFAULT_SUPPORT_EMAIL
)
app.config['MAIL_SUPPRESS_SEND'] = not app.config['MAIL_SERVER'] and not is_production_environment()

# Configuração de Timezone para horário de Brasília
BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')

def get_brazil_time():
    """Retorna datetime atual no fuso horário de Brasília"""
    return datetime.now(BRAZIL_TZ)

# Definição de constantes
UPLOAD_FOLDER = 'static/uploads/profiles'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
CONTACT_ALLOWED_EXTENSIONS = {
    'bin', 'csv', 'doc', 'docx', 'gif', 'jpeg', 'jpg', 'pdf', 'png',
    'rar', 'rom', 'txt', 'webp', 'xls', 'xlsx', 'zip', '7z'
}
CONTACT_MAX_ATTACHMENTS = 5
CONTACT_MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024

# Configurações adicionais
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', str(64 * 1024 * 1024)))
app.config['DOWNLOAD_DELIVERY_MODE'] = os.environ.get('DOWNLOAD_DELIVERY_MODE', 'proxy').strip().lower()
app.config['TECHNICAL_IMPORT_ENABLED'] = os.environ.get('TECHNICAL_IMPORT_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')
app.config['TECHNICAL_CONTRIBUTIONS_ENABLED'] = os.environ.get('TECHNICAL_CONTRIBUTIONS_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')
app.config['TECHNICAL_IMPORT_TEMP_DIR'] = os.environ.get(
    'TECHNICAL_IMPORT_TEMP_DIR', os.path.join(app.instance_path, 'technical-imports')
)
app.config['TECHNICAL_LOCAL_STORAGE_DIR'] = os.environ.get(
    'TECHNICAL_LOCAL_STORAGE_DIR', os.path.join(app.instance_path, 'technical-files')
)
app.config['ENABLE_DATASHEET_ENGINE'] = os.environ.get('ENABLE_DATASHEET_ENGINE', 'true').lower() in ('true', '1', 'yes', 'on')
app.config['ENABLE_SOURCE_PARTS'] = os.environ.get('ENABLE_SOURCE_PARTS', 'true').lower() in ('true', '1', 'yes', 'on')
app.config['ENABLE_ALLDATASHEET_API'] = os.environ.get('ENABLE_ALLDATASHEET_API', 'false').lower() in ('true', '1', 'yes', 'on')
app.config['ENABLE_ALLDATASHEET_HTML'] = os.environ.get('ENABLE_ALLDATASHEET_HTML', 'false').lower() in ('true', '1', 'yes', 'on')
app.config['ENABLE_DATASHEETS_COM_API'] = os.environ.get('ENABLE_DATASHEETS_COM_API', 'false').lower() in ('true', '1', 'yes', 'on')
app.config['ENABLE_DATASHEETS_COM_HTML'] = os.environ.get('ENABLE_DATASHEETS_COM_HTML', 'false').lower() in ('true', '1', 'yes', 'on')
app.config['DISABLE_ALL_DATASHEET_AUTOMATION'] = os.environ.get('DISABLE_ALL_DATASHEET_AUTOMATION', 'false').lower() in ('true', '1', 'yes', 'on')

# Inicializar as extensões
db = SQLAlchemy(app)
compress = Compress(app)
assets = Environment(app)
mail = Mail(app)

# Proteção CSRF
app.config['WTF_CSRF_ENABLED'] = True
csrf = CSRFProtect(app)

# Rate Limiting para evitar ataques de força bruta
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
)


# A aplicação ainda contém estilos e scripts inline legados. ``unsafe-inline``
# fica restrito a esses dois tipos até a migração gradual para nonces/hashes.
CONTENT_SECURITY_POLICY = {
    'default-src': ["'self'"],
    'base-uri': ["'self'"],
    'object-src': ["'none'"],
    'frame-ancestors': ["'self'"],
    'form-action': ["'self'", 'https://checkout.stripe.com'],
    'script-src': [
        "'self'", "'unsafe-inline'", 'https://cdnjs.cloudflare.com',
        'https://cdn.jsdelivr.net', 'https://www.gstatic.com',
        'https://js.stripe.com', 'https://connect.facebook.net',
        'https://www.googletagmanager.com',
    ],
    'style-src': [
        "'self'", "'unsafe-inline'", 'https://fonts.googleapis.com',
        'https://cdnjs.cloudflare.com', 'https://cdn.jsdelivr.net',
    ],
    'font-src': ["'self'", 'data:', 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com'],
    'img-src': ["'self'", 'data:', 'blob:', 'https:'],
    'connect-src': [
        "'self'", 'https://api.stripe.com', 'https://*.googleapis.com',
        'https://*.firebaseio.com', 'wss://*.firebaseio.com',
        'wss://*.googleapis.com', 'https://www.google-analytics.com',
        'https://region1.google-analytics.com', 'https://graph.facebook.com',
        'https://api.cloudinary.com',
    ],
    'frame-src': [
        "'self'", 'https://js.stripe.com', 'https://hooks.stripe.com',
        'https://accounts.google.com',
    ],
}

talisman = Talisman(
    app,
    force_https=is_production_environment(),
    strict_transport_security=is_production_environment(),
    strict_transport_security_max_age=31536000,
    strict_transport_security_include_subdomains=True,
    content_security_policy=CONTENT_SECURITY_POLICY,
    referrer_policy='strict-origin-when-cross-origin',
    frame_options='SAMEORIGIN',
)


def _is_json_like_request():
    accepts_json = request.accept_mimetypes['application/json'] >= request.accept_mimetypes['text/html']
    return request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or accepts_json


def _is_ajax_request() -> bool:
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json


def split_full_name(full_name: str) -> Tuple[str, str]:
    full_name = (full_name or '').strip()
    if not full_name:
        return '', ''
    parts = full_name.split()
    first_name = parts[0]
    last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
    return first_name[:50], last_name[:50]


def build_safe_username(raw_value: str, fallback_prefix: str = 'user') -> str:
    base = re.sub(r'[^a-zA-Z0-9_]', '', (raw_value or '').strip())
    if not base:
        base = f"{fallback_prefix}{secrets.token_hex(2)}"
    if len(base) < 4:
        base = (base + 'user')[:4]
    return base[:50]


def get_unique_username(seed: str, fallback_prefix: str = 'user') -> str:
    base = build_safe_username(seed, fallback_prefix=fallback_prefix)
    candidate = base
    suffix = 1
    while User.query.filter_by(username=candidate).first():
        suffix_token = f"_{suffix}"
        allowed = 50 - len(suffix_token)
        candidate = f"{base[:allowed]}{suffix_token}"
        suffix += 1
    return candidate


def get_image_url_for_response(image_path, folder='profiles', default='default.jpg'):
    if not image_path or image_path in ('default.jpg', 'default_profile.jpg'):
        if folder == 'posts' and default in ('default.jpg', 'post-placeholder.svg'):
            return url_for('static', filename=f'images/{default}')
        return url_for('static', filename=f'images/{folder}/{default}')

    if str(image_path).startswith('http://') or str(image_path).startswith('https://'):
        return image_path

    normalized = str(image_path).lstrip('/')
    if normalized.startswith('uploads/'):
        return url_for('static', filename=normalized)
    if normalized.startswith('images/'):
        return url_for('static', filename=normalized)
    if normalized.startswith('posts/'):
        return url_for('static', filename=f'images/{normalized}')
    if normalized in ('post-placeholder.svg', 'default.jpg', 'default_profile.jpg'):
        return url_for('static', filename=f'images/{normalized}')
    if folder == 'posts':
        return url_for('static', filename=f'images/posts/{normalized}')
    return url_for('static', filename=f'uploads/{folder}/{normalized}')


def get_safe_internal_path(raw_path: str | None, fallback: str = '/') -> str:
    candidate = (raw_path or '').strip()
    if not candidate:
        return fallback

    try:
        parsed = url_parse(candidate)
        if parsed.netloc:
            return fallback
        if not parsed.path.startswith('/'):
            return fallback
        return candidate
    except (ValueError, TypeError, AttributeError):
        return fallback


def serialize_comment(comment: "Comment") -> dict[str, Any]:
    if comment.user_id and comment.user:
        author_name = comment.user.username
        profile_image = get_image_url_for_response(
            getattr(comment.user, 'profile_image', None),
            folder='profiles',
            default='default_profile.jpg'
        )
        user_id = comment.user_id
    else:
        author_name = comment.author_name or 'Usuario'
        profile_image = None
        user_id = None

    comment_data: dict[str, Any] = {
        'id': comment.id,
        'author': author_name,
        'content': comment.content,
        'date': comment.date_posted.strftime('%d/%m/%Y %H:%M'),
        'profile_image': profile_image,
        'user_id': user_id,
        'is_edited': bool(getattr(comment, 'is_edited', False)),
        'parent_id': getattr(comment, 'parent_id', None)
    }

    if comment.is_edited and getattr(comment, 'date_edited', None):
        comment_data['date_edited'] = comment.date_edited.strftime('%d/%m/%Y %H:%M')

    return comment_data


def serialize_comment_thread(comments: list["Comment"]) -> list[dict[str, Any]]:
    serialized_by_id: dict[int, dict[str, Any]] = {}
    roots: list[dict[str, Any]] = []

    for comment in comments:
        payload = serialize_comment(comment)
        payload['replies'] = []
        serialized_by_id[comment.id] = payload

    for comment in comments:
        payload = serialized_by_id[comment.id]
        parent_id = getattr(comment, 'parent_id', None)
        if parent_id and parent_id in serialized_by_id:
            serialized_by_id[parent_id]['replies'].append(payload)
        else:
            roots.append(payload)

    return roots


def request_prefers_json_response() -> bool:
    return bool(
        request.is_json
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in (request.headers.get('Accept') or '')
    )


def redirect_back_to_post(post: "Post | None", fallback_endpoint: str = 'home'):
    if post is not None:
        if getattr(post, 'slug', None) and getattr(post, 'category_str', None):
            return redirect(url_for('post_by_slug', category=generate_slug(post.category_str), slug=post.slug))
        if getattr(post, 'id', None):
            return redirect(url_for('post', post_id=post.id))

    return redirect(url_for(fallback_endpoint))


def get_admin_posts_overview() -> dict[str, int]:
    return {
        'total_posts': Post.query.count(),
        'active_posts': Post.query.filter_by(is_active=True).count(),
        'featured_posts': Post.query.filter_by(featured=True).count()
    }


DEFAULT_DOWNLOAD_FILE_TYPES = [
    {'label': 'BIOS', 'icon': 'fas fa-microchip', 'color': '#3a86ff'},
    {'label': 'EC', 'icon': 'fas fa-memory', 'color': '#7c3aed'},
    {'label': 'ME', 'icon': 'fas fa-shield-alt', 'color': '#f59e0b'},
    {'label': 'Outros', 'icon': 'fas fa-file-archive', 'color': '#64748b'},
    {'label': 'BoardView', 'icon': 'fas fa-project-diagram', 'color': '#0891b2'},
]

DOWNLOAD_FILE_TYPE_PRESENTATION = {
    item['label'].casefold(): dict(item)
    for item in DEFAULT_DOWNLOAD_FILE_TYPES
}

CATEGORY_ICON_FALLBACKS = {
    'bios': 'fas fa-microchip',
    'esquemas': 'fas fa-project-diagram',
    'drivers': 'fas fa-cogs',
    'softwares': 'fas fa-laptop-code',
    'impressoras': 'fas fa-print',
    'cursos': 'fas fa-graduation-cap',
    'datasheet': 'fas fa-file-alt',
}


def normalize_download_file_type_label(value: Any) -> str:
    label = str(value or '').strip()
    label = re.sub(r'\s+', ' ', label)
    aliases = {
        'bios': 'BIOS', 'ec': 'EC', 'me': 'ME',
        'outro': 'Outros', 'outros': 'Outros',
        'board view': 'BoardView', 'boardview': 'BoardView',
    }
    return aliases.get(label.casefold(), label)[:30]


def get_download_file_type_presentation(value: Any) -> dict[str, str]:
    label = normalize_download_file_type_label(value) or 'Outros'
    presentation = DOWNLOAD_FILE_TYPE_PRESENTATION.get(label.casefold())
    if presentation:
        return dict(presentation)
    return {'label': label, 'icon': 'fas fa-file', 'color': '#64748b'}


def normalize_download_file_types(raw_types: Any) -> list[dict[str, str]]:
    if not isinstance(raw_types, list):
        return []

    normalized_types: list[dict[str, str]] = []
    used_labels: set[str] = set()

    for item in raw_types:
        raw_label = item.get('label') if isinstance(item, dict) else item
        label = normalize_download_file_type_label(raw_label)
        label_key = label.casefold()

        if not label or label_key in used_labels:
            continue

        normalized_types.append({'label': label})
        used_labels.add(label_key)

        if len(normalized_types) >= 12:
            break

    return normalized_types


def get_download_file_types() -> list[dict[str, str]]:
    configured_types = SiteConfig.get_value('download_file_types', None)
    normalized_types = normalize_download_file_types(configured_types)
    merged_labels = [item['label'] for item in DEFAULT_DOWNLOAD_FILE_TYPES]
    merged_labels.extend(item['label'] for item in normalized_types)
    unique_labels = list(dict.fromkeys(label.casefold() for label in merged_labels))
    label_by_key = {label.casefold(): label for label in merged_labels}
    return [get_download_file_type_presentation(label_by_key[key]) for key in unique_labels[:12]]


def get_download_file_type_labels() -> list[str]:
    return [item['label'] for item in get_download_file_types()]


def get_category_icon(category_or_name: Any) -> str:
    if hasattr(category_or_name, 'name'):
        category_name = getattr(category_or_name, 'name', '')
    else:
        category_name = str(category_or_name or '')

    slug = generate_slug(category_name)
    if slug in CATEGORY_ICON_FALLBACKS:
        return CATEGORY_ICON_FALLBACKS[slug]
    if hasattr(category_or_name, 'icon') and getattr(category_or_name, 'icon', None):
        return getattr(category_or_name, 'icon')
    return 'fas fa-folder'


def get_default_category_subcategories() -> dict[str, list[str]]:
    return {
        'BIOS': ['bios-notebook', 'bios-desktop', 'bios-all-in-one'],
        'Esquemas': ['esquemas-placa-mae', 'esquemas-fonte', 'esquemas-monitor'],
        'Drivers': ['drivers-video', 'drivers-audio', 'drivers-rede', 'drivers-chipset'],
        'Softwares': ['softwares-diagnostico', 'softwares-recuperacao', 'softwares-otimizacao'],
        'Impressoras': ['impressoras-hp', 'impressoras-canon', 'impressoras-epson', 'impressoras-samsung'],
        'Cursos': ['cursos-hardware', 'cursos-software', 'cursos-redes'],
        'Datasheet': ['datasheet-ics', 'datasheet-transistores', 'datasheet-semicondutores']
    }

def format_subcategory_label(subcategory_slug: str) -> str:
    labels = {
        'bios-notebook': 'BIOS Notebook',
        'bios-desktop': 'BIOS Desktop',
        'bios-all-in-one': 'BIOS All-in-One',
        'esquemas-placa-mae': 'Esquemas Placa-Mãe',
        'esquemas-fonte': 'Esquemas Fonte',
        'esquemas-monitor': 'Esquemas Monitor',
        'drivers-video': 'Drivers Vídeo',
        'drivers-audio': 'Drivers Áudio',
        'drivers-rede': 'Drivers Rede',
        'drivers-chipset': 'Drivers Chipset',
        'softwares-diagnostico': 'Diagnóstico',
        'softwares-recuperacao': 'Recuperação',
        'softwares-otimizacao': 'Otimização',
        'impressoras-hp': 'HP',
        'impressoras-canon': 'Canon',
        'impressoras-epson': 'Epson',
        'impressoras-samsung': 'Samsung',
        'cursos-hardware': 'Hardware',
        'cursos-software': 'Software',
        'cursos-redes': 'Redes',
        'datasheet-ics': 'Circuitos Integrados',
        'datasheet-transistores': 'Transistores',
        'datasheet-semicondutores': 'Semicondutores'
    }
    return labels.get(subcategory_slug, subcategory_slug.replace('-', ' ').title())

def get_category_subcategories_map(include_defaults: bool = False) -> dict[str, list[str]]:
    subcategories_map: dict[str, list[str]] = {}

    if include_defaults:
        default_subcategories = get_default_category_subcategories()
        categories = Category.query.filter_by(is_active=True, is_visible=True).all()
        for category in categories:
            defaults = default_subcategories.get(category.name, [])
            if defaults:
                subcategories_map[str(category.id)] = list(defaults)

    rows = db.session.query(Post.category_id, Post.subcategory).filter(
        Post.category_id.isnot(None),
        Post.subcategory.isnot(None),
        Post.subcategory != ''
    ).distinct().order_by(Post.subcategory.asc()).all()

    for category_id, subcategory in rows:
        key = str(category_id)
        subcategories_map.setdefault(key, [])
        if subcategory not in subcategories_map[key]:
            subcategories_map[key].append(subcategory)

    return subcategories_map


def get_plain_text_excerpt(content: str | None, limit: int = 220) -> str:
    normalized = re.sub(
        r'\s+',
        ' ',
        bleach.clean(content or '', tags=[], strip=True)
    ).strip()

    if limit > 0 and len(normalized) > limit:
        return f"{normalized[:limit].rstrip()}..."

    return normalized


def get_search_parts(value: Any) -> tuple[str, str]:
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(char for char in text if not unicodedata.combining(char)).casefold()
    spaced = re.sub(r'[^a-z0-9]+', ' ', text).strip()
    compact = re.sub(r'[^a-z0-9]+', '', text)
    return spaced, compact


def get_search_match_score(query: str, *values: Any) -> int | None:
    query_spaced, query_compact = get_search_parts(query)
    if not query_spaced and not query_compact:
        return 0

    value_parts = [get_search_parts(value) for value in values if value is not None]
    if not value_parts:
        return None

    spaced_values = [spaced for spaced, _compact in value_parts if spaced]
    compact_values = [compact for _spaced, compact in value_parts if compact]
    spaced_blob = ' '.join(spaced_values)
    compact_blob = ' '.join(compact_values)

    if query_spaced and any(query_spaced == spaced for spaced in spaced_values):
        return 0
    if query_compact and any(query_compact == compact for compact in compact_values):
        return 0
    if query_spaced and any(spaced.startswith(query_spaced) for spaced in spaced_values):
        return 1
    if query_compact and any(compact.startswith(query_compact) for compact in compact_values):
        return 1
    if query_spaced and query_spaced in spaced_blob:
        return 2
    if query_compact and query_compact in compact_blob:
        return 2

    tokens = [token for token in query_spaced.split() if token]
    if tokens and all(token in spaced_blob or token in compact_blob for token in tokens):
        return 3

    return None


def get_related_posts_for_post(post: "Post", limit: int = 9) -> list["Post"]:
    seen_ids = {post.id}
    related_posts: list[Post] = []

    def extend_with(posts: list["Post"]) -> None:
        for candidate in posts:
            if candidate.id in seen_ids:
                continue
            seen_ids.add(candidate.id)
            related_posts.append(candidate)
            if len(related_posts) >= limit:
                break

    same_category = Post.query.filter(
        Post.is_active.is_(True),
        Post.id != post.id,
        Post.category_str == post.category_str
    ).order_by(Post.views.desc(), Post.date_posted.desc()).limit(limit).all()
    extend_with(same_category)

    if len(related_posts) < limit and post.subcategory:
        same_subcategory = Post.query.filter(
            Post.is_active.is_(True),
            Post.id != post.id,
            Post.subcategory == post.subcategory
        ).order_by(Post.views.desc(), Post.date_posted.desc()).limit(limit).all()
        extend_with(same_subcategory)

    if len(related_posts) < limit:
        fallback_posts = Post.query.filter(
            Post.is_active.is_(True),
            Post.id != post.id
        ).order_by(Post.views.desc(), Post.date_posted.desc()).limit(limit * 2).all()
        extend_with(fallback_posts)

    return related_posts[:limit]


def parse_donation_amount_to_cents(raw_amount: Any) -> tuple[bool, int | None, str | None]:
    normalized = str(raw_amount or '').strip().replace('R$', '').replace(' ', '')
    normalized = normalized.replace('.', '').replace(',', '.')

    if not normalized:
        return False, None, 'Informe um valor de doacao.'

    try:
        amount = Decimal(normalized)
    except (InvalidOperation, TypeError, ValueError):
        return False, None, 'Valor de doacao invalido.'

    if amount < Decimal('5.00'):
        return False, None, 'A doacao minima e de R$ 5,00.'

    if amount > Decimal('5000.00'):
        return False, None, 'O valor maximo por doacao e de R$ 5.000,00.'

    cents = int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    return True, cents, None


def allowed_contact_attachment(filename: str) -> bool:
    if not filename or '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in CONTACT_ALLOWED_EXTENSIONS


def prepare_contact_email_attachments(uploaded_files) -> tuple[bool, list[tuple[str, str, bytes]], str | None]:
    files = [
        uploaded_file for uploaded_file in (uploaded_files or [])
        if uploaded_file and getattr(uploaded_file, 'filename', '').strip()
    ]

    if len(files) > CONTACT_MAX_ATTACHMENTS:
        return False, [], f'Voce pode anexar no maximo {CONTACT_MAX_ATTACHMENTS} arquivos.'

    attachments: list[tuple[str, str, bytes]] = []
    for uploaded_file in files:
        filename = secure_filename(uploaded_file.filename or '')
        if not filename:
            return False, [], 'Um dos arquivos anexados possui um nome invalido.'

        if not allowed_contact_attachment(filename):
            return False, [], f'Tipo de arquivo nao permitido: {filename}.'

        file_bytes = uploaded_file.read()
        if not file_bytes:
            continue

        if len(file_bytes) > CONTACT_MAX_ATTACHMENT_BYTES:
            return False, [], f'O arquivo {filename} excede o limite de 5MB.'

        attachments.append((
            filename,
            uploaded_file.mimetype or 'application/octet-stream',
            file_bytes,
        ))

    return True, attachments, None


def send_contact_support_email(
    *,
    name: str,
    email: str,
    phone: str,
    category: str,
    subject: str,
    message: str,
    attachments: list[tuple[str, str, bytes]],
) -> None:
    category_labels = {
        'suporte': 'Suporte Tecnico',
        'solicitacao': 'Solicitacao de Recurso',
        'problema': 'Reportar Problema',
        'sugestao': 'Sugestao',
        'parcerias': 'Parcerias',
        'outros': 'Outros',
    }
    normalized_category = category_labels.get(category, category or 'Nao informado')
    support_email: str = str(SiteConfig.get_value('contact_email', None) or app.config.get('SUPPORT_EMAIL') or DEFAULT_SUPPORT_EMAIL)

    email_body = "\n".join([
        "Nova mensagem enviada pelo formulario de contato do site.",
        "",
        f"Nome: {name}",
        f"Email: {email}",
        f"Telefone: {phone or 'Nao informado'}",
        f"Categoria: {normalized_category}",
        f"Assunto: {subject}",
        "",
        "Mensagem:",
        message,
    ])

    msg = Message(
        subject=f"[Contato] {subject}",
        recipients=[support_email],
        reply_to=email,
        body=email_body,
    )

    for filename, mimetype, file_bytes in attachments:
        msg.attach(filename, mimetype, file_bytes)

    mail.send(msg)


def send_password_reset_email(user, token: str) -> bool:
    """Envia recuperação de senha sem registrar o token em logs."""
    if not app.config.get('MAIL_SERVER'):
        app.logger.warning('SMTP nao configurado; email de redefinicao nao enviado')
        return False

    reset_url = _absolute_public_url(url_for('reset_password', token=token))
    message = Message(
        subject='Redefinição de senha — Mundo da Informática',
        recipients=[user.email],
        body=(
            'Recebemos uma solicitação para redefinir sua senha.\n\n'
            f'Acesse o link abaixo para escolher uma nova senha:\n{reset_url}\n\n'
            'Se você não fez esta solicitação, ignore este email.'
        ),
    )
    mail.send(message)
    return True


def serialize_post_for_admin(post):
    category = post.category_rel or (db.session.get(Category, post.category_id) if post.category_id else None)
    schedule = getattr(post, 'scheduled_publication', None)
    publication_status = 'scheduled' if schedule and schedule.status == 'pending' else ('published' if post.is_active else 'draft')
    posted_at = to_brazil_time(post.date_posted) if post.date_posted else None
    scheduled_at = to_brazil_time(schedule.scheduled_for) if schedule and schedule.status == 'pending' else None
    return {
        'id': post.id,
        'title': post.title,
        'description': get_plain_text_excerpt(post.content, limit=220),
        'excerpt': get_plain_text_excerpt(post.content, limit=120),
        'category_id': post.category_id,
        'category_name': category.name if category else (post.category_str or 'Sem categoria'),
        'category_icon': get_category_icon(category or post.category_str),
        'category_color': (getattr(category, 'color', None) if category else None) or '#3a86ff',
        'image_url': get_image_url_for_response(post.image_url, folder='posts', default='default.jpg'),
        'date_posted': posted_at.strftime('%d/%m/%Y') if posted_at else '',
        'time_posted': posted_at.strftime('%H:%M') if posted_at else '',
        'views': post.views or 0,
        'downloads': post.downloads or 0,
        'featured': bool(post.featured),
        'is_active': bool(post.is_active),
        'publication_status': publication_status,
        'scheduled_for': scheduled_at.isoformat() if scheduled_at else None,
        'post_url': url_for('post', post_id=post.id),
    }


_firebase_initialized = False


def _sanitize_service_account_dict(data: dict) -> dict:
    normalized = dict(data)

    private_key = normalized.get('private_key')
    if isinstance(private_key, str):
        normalized['private_key'] = private_key.replace('\\n', '\n').replace('\r\n', '\n')

    return normalized


def _normalize_service_account_json(raw_value: str) -> Optional[dict]:
    raw = (raw_value or '').strip()
    if not raw:
        return None

    candidates = [raw]
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        candidates.append(raw[1:-1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return _sanitize_service_account_dict(parsed)
        except Exception:
            continue

    try:
        parsed_literal = ast.literal_eval(raw)
        if isinstance(parsed_literal, dict):
            return _sanitize_service_account_dict(parsed_literal)
    except Exception:
        pass

    # Fallback para JSON com quebras reais de linha dentro da private_key
    if '"private_key"' in raw and 'BEGIN PRIVATE KEY' in raw and 'END PRIVATE KEY' in raw:
        def _repair_private_key(match):
            key_content = match.group(1)
            key_content = key_content.replace('\r', '').replace('\n', '\\n')
            return f'"private_key":"{key_content}"'

        repaired = re.sub(
            r'"private_key"\s*:\s*"(.*?)"',
            _repair_private_key,
            raw,
            flags=re.S
        )
        try:
            parsed = json.loads(repaired)
            if isinstance(parsed, dict):
                return _sanitize_service_account_dict(parsed)
        except Exception:
            pass

    return None


def _build_service_account_from_split_env() -> Optional[dict]:
    client_email = os.environ.get('FIREBASE_CLIENT_EMAIL', '').strip()
    private_key = os.environ.get('FIREBASE_PRIVATE_KEY', '').strip()
    private_key_id = os.environ.get('FIREBASE_PRIVATE_KEY_ID', '').strip()
    project_id = app.config.get('FIREBASE_PROJECT_ID', '')

    if not client_email or not private_key or not project_id:
        return None

    normalized_private_key = private_key.replace('\\n', '\n')

    return {
        'type': 'service_account',
        'project_id': project_id,
        'private_key_id': private_key_id or None,
        'private_key': normalized_private_key,
        'client_email': client_email,
        'token_uri': 'https://oauth2.googleapis.com/token'
    }


def _build_service_account_from_base64_env() -> Optional[dict]:
    raw_b64 = os.environ.get('FIREBASE_SERVICE_ACCOUNT_B64', '').strip()
    if not raw_b64:
        return None

    try:
        decoded = base64.b64decode(raw_b64).decode('utf-8')
        parsed = json.loads(decoded)
        if isinstance(parsed, dict):
            return _sanitize_service_account_dict(parsed)
    except Exception as e:
        app.logger.warning(f'FIREBASE_SERVICE_ACCOUNT_B64 inválido: {e}')

    return None


def _build_service_account_from_dotenv_block() -> Optional[dict]:
    """
    Fallback para desenvolvimento local:
    lê FIREBASE_SERVICE_ACCOUNT_JSON em formato multiline diretamente do arquivo .env.
    """
    dotenv_candidates = [
        os.path.join(os.getcwd(), '.env'),
        os.path.join(os.path.dirname(__file__), '.env')
    ]

    for dotenv_path in dotenv_candidates:
        if not os.path.exists(dotenv_path):
            continue

        try:
            with open(dotenv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            continue

        for idx, raw_line in enumerate(lines):
            stripped = raw_line.strip()
            if not stripped.startswith('FIREBASE_SERVICE_ACCOUNT_JSON='):
                continue

            first_chunk = stripped.split('=', 1)[1].strip()
            if not first_chunk:
                continue

            block = first_chunk
            balance = block.count('{') - block.count('}')
            line_cursor = idx + 1

            while balance > 0 and line_cursor < len(lines):
                next_line = lines[line_cursor].rstrip('\n')
                block += '\n' + next_line
                balance += next_line.count('{') - next_line.count('}')
                line_cursor += 1

            parsed = _normalize_service_account_json(block)
            if parsed:
                return parsed

    return None


def is_firebase_admin_configured() -> bool:
    """Retorna True quando ha credenciais de servidor suficientes para o chat."""
    if firebase_admin is None or credentials is None:
        return False

    service_account_path = (app.config.get('FIREBASE_SERVICE_ACCOUNT_PATH', '') or '').strip()
    service_account_json = (app.config.get('FIREBASE_SERVICE_ACCOUNT_JSON', '') or '').strip()
    service_account_b64 = os.environ.get('FIREBASE_SERVICE_ACCOUNT_B64', '').strip()
    split_client_email = os.environ.get('FIREBASE_CLIENT_EMAIL', '').strip()
    split_private_key = os.environ.get('FIREBASE_PRIVATE_KEY', '').strip()
    project_id = (app.config.get('FIREBASE_PROJECT_ID', '') or '').strip()

    return bool(
        service_account_json
        or service_account_b64
        or (service_account_path and os.path.exists(service_account_path))
        or (split_client_email and split_private_key and project_id)
        or _build_service_account_from_dotenv_block()
    )


def initialize_firebase_admin() -> bool:
    global _firebase_initialized
    if _firebase_initialized:
        return True

    if firebase_admin is None or credentials is None:
        app.logger.warning('firebase_admin não está disponível. Instale a dependência firebase-admin.')
        return False

    try:
        if firebase_admin._apps:  # type: ignore[attr-defined]
            _firebase_initialized = True
            return True
    except Exception:
        pass

    service_account_path = app.config.get('FIREBASE_SERVICE_ACCOUNT_PATH', '')
    service_account_json = app.config.get('FIREBASE_SERVICE_ACCOUNT_JSON', '')
    service_account_json_invalid = False

    try:
        if service_account_json:
            cred_data = _normalize_service_account_json(service_account_json)
            if cred_data:
                cred = credentials.Certificate(cred_data)
                firebase_admin.initialize_app(cred)
                _firebase_initialized = True
                return True
            service_account_json_invalid = True

        if service_account_path and os.path.exists(service_account_path):
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            return True

        b64_cred_data = _build_service_account_from_base64_env()
        if b64_cred_data:
            cred = credentials.Certificate(b64_cred_data)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            return True

        split_cred_data = _build_service_account_from_split_env()
        if split_cred_data:
            cred = credentials.Certificate(split_cred_data)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            return True

        dotenv_cred_data = _build_service_account_from_dotenv_block()
        if dotenv_cred_data:
            cred = credentials.Certificate(dotenv_cred_data)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            return True

        if service_account_json_invalid:
            app.logger.warning('FIREBASE_SERVICE_ACCOUNT_JSON inválido. Tentando outros formatos de configuração.')
        app.logger.warning('Firebase Admin não configurado. Defina FIREBASE_SERVICE_ACCOUNT_PATH, FIREBASE_SERVICE_ACCOUNT_JSON ou FIREBASE_SERVICE_ACCOUNT_B64.')
        return False
    except Exception as e:
        app.logger.error(f'Erro ao inicializar Firebase Admin: {e}')
        return False


def _verify_firebase_token_via_identity_toolkit(id_token: str) -> Optional[dict]:
    api_key = (app.config.get('FIREBASE_API_KEY', '') or '').strip()
    if not api_key:
        return None

    endpoint = f'https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={api_key}'
    payload = json.dumps({'idToken': id_token}).encode('utf-8')
    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode('utf-8')
        except Exception:
            error_body = ''
        app.logger.warning(f'Falha HTTP no fallback Identity Toolkit: {e.code} {error_body}')
        return None
    except Exception as e:
        app.logger.warning(f'Falha no fallback Identity Toolkit: {e}')
        return None

    users = body.get('users') or []
    if not users:
        return None

    user_info = users[0]
    provider_user_info = user_info.get('providerUserInfo') or []
    provider_ids = {
        (item.get('providerId') or '').strip()
        for item in provider_user_info
        if isinstance(item, dict)
    }

    # Se há provider explicitado e não inclui Google, rejeita.
    if provider_ids and 'google.com' not in provider_ids:
        return None

    email = (user_info.get('email') or '').strip().lower()
    if not email:
        return None

    return {
        'uid': user_info.get('localId'),
        'email': email,
        'email_verified': bool(user_info.get('emailVerified')),
        'name': user_info.get('displayName') or '',
        'picture': user_info.get('photoUrl') or '',
        'firebase': {
            'sign_in_provider': 'google.com' if 'google.com' in provider_ids else ''
        }
    }


def verify_firebase_google_token(id_token: str) -> Optional[dict]:
    if not id_token:
        return None

    # Caminho principal: Firebase Admin SDK
    if firebase_auth is not None and initialize_firebase_admin():
        try:
            decoded = firebase_auth.verify_id_token(id_token)
            provider = decoded.get('firebase', {}).get('sign_in_provider')
            if provider and provider != 'google.com':
                return None
            return decoded
        except Exception as e:
            app.logger.warning(f'Falha na validação via Firebase Admin: {e}')

    # Fallback: validação pública do token Firebase sem credencial de service account
    if google_id_token is not None and google_auth_requests is not None:
        project_id = app.config.get('FIREBASE_PROJECT_ID', '') or None
        try:
            decoded = google_id_token.verify_firebase_token(
                id_token,
                google_auth_requests.Request(),
                project_id
            )
            if not decoded:
                return None

            if not isinstance(decoded, Mapping):
                return None

            decoded_dict: dict[str, Any] = dict(decoded)
            firebase_claim = decoded_dict.get('firebase')
            provider = ''
            if isinstance(firebase_claim, Mapping):
                provider_value = firebase_claim.get('sign_in_provider')
                if isinstance(provider_value, str):
                    provider = provider_value

            if provider and provider != 'google.com':
                return None
            return decoded_dict
        except Exception as e:
            app.logger.warning(f'Falha na validação fallback do token Firebase: {e}')

    # Fallback final: validação via API oficial Identity Toolkit
    decoded_by_api = _verify_firebase_token_via_identity_toolkit(id_token)
    if decoded_by_api:
        return decoded_by_api

    return None


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    message = 'Token CSRF ausente, inválido ou expirado. Atualize a página e tente novamente.'
    if _is_json_like_request():
        return jsonify({'success': False, 'error': message, 'details': e.description}), 400

    flash(message, 'danger')
    return redirect(request.referrer or url_for('home')), 400


@app.errorhandler(403)
def handle_403_error(e):
    message = 'Ação não permitida. Verifique sua sessão e tente novamente.'
    if _is_json_like_request():
        return jsonify({'success': False, 'error': message}), 403

    return render_template('errors/403.html', title='Acesso não permitido'), 403


@app.errorhandler(404)
def handle_404_error(e):
    if _is_json_like_request():
        return jsonify({'success': False, 'error': 'Recurso não encontrado.'}), 404
    return render_template('errors/404.html', title='Página não encontrada'), 404


@app.errorhandler(500)
def handle_500_error(e):
    db.session.rollback()
    if _is_json_like_request():
        return jsonify({'success': False, 'error': 'Erro interno do servidor.'}), 500
    return render_template('errors/500.html', title='Erro interno'), 500


@app.errorhandler(400)
def handle_400_error(e):
    if isinstance(e, CSRFError):
        return handle_csrf_error(e)

    message = 'Não foi possível processar sua solicitação.'
    if _is_json_like_request():
        return jsonify({'success': False, 'error': message}), 400

    flash(message, 'warning')
    return redirect(request.referrer or url_for('home')), 400

# Bundles de CSS e JS para otimização
css = Bundle('css/style.css', 'css/additional.css', 'css/social.css', filters='cssmin', output='gen/style.min.css')
js = Bundle('js/main.js', filters='jsmin', output='gen/script.min.js')
assets.register('css_all', css)
assets.register('js_all', js)

# Modelos adicionais para maior flexibilidade
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(50), nullable=True)  # Classe de ícone FontAwesome
    color = db.Column(db.String(20), default='#4a90e2')
    slug = db.Column(db.String(50), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=True)
    is_visible = db.Column(db.Boolean, default=True, nullable=False)
    featured = db.Column(db.Boolean, default=False)  # Campo para categorias em destaque
    show_in_menu = db.Column(db.Boolean, default=True)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Data de criação
    posts = db.relationship('Post', backref='category_rel', lazy=True,
                            primaryjoin="and_(Category.id==Post.category_id, Post.is_active==True)")

    def __repr__(self):
        return f"Category('{self.name}')"

# Adicionando mais campos ao Post para flexibilidade
class Post(db.Model):
    __tablename__ = 'posts'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    date_updated = db.Column(db.DateTime, nullable=True)

    # Autor e categoria
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    category_str = db.Column(db.String(100), nullable=True)  # Para compatibilidade
    subcategory = db.Column(db.String(30), nullable=True)

    # Status e controle
    is_active = db.Column(db.Boolean, default=True)
    featured = db.Column(db.Boolean, default=False)

    # Métricas
    views = db.Column(db.Integer, default=0)
    downloads = db.Column(db.Integer, default=0)

    # Arquivos e mídia
    thumbnail = db.Column(db.String(200))
    image_url = db.Column(db.String(200), nullable=True, default='default.jpg')
    file_path = db.Column(db.String(255))
    file_size = db.Column(db.Float)  # em MB
    download_link = db.Column(db.String(200), nullable=False)

    # SEO e organização
    tags = db.Column(db.String(200), nullable=True)
    seo_title = db.Column(db.String(100), nullable=True)
    seo_description = db.Column(db.String(200), nullable=True)
    slug = db.Column(db.String(250), nullable=True)  # URL amigável

    # Metadados flexíveis em formato JSON
    custom_metadata = db.Column(db.Text, nullable=True)

    # Metadados técnicos estruturados (todos opcionais para compatibilidade).
    manufacturer = db.Column(db.String(120), nullable=True)
    brand = db.Column(db.String(120), nullable=True)
    model = db.Column(db.String(160), nullable=True)
    series = db.Column(db.String(160), nullable=True)
    board_code = db.Column(db.String(120), nullable=True, index=True)
    board_revision = db.Column(db.String(80), nullable=True)
    platform = db.Column(db.String(120), nullable=True)
    bios_chip = db.Column(db.String(120), nullable=True)
    ec_chip = db.Column(db.String(120), nullable=True)
    me_chip = db.Column(db.String(120), nullable=True)
    file_type = db.Column(db.String(80), nullable=True)
    file_extension = db.Column(db.String(30), nullable=True)
    technical_file_size = db.Column(db.String(50), nullable=True)
    version = db.Column(db.String(80), nullable=True)
    sha256 = db.Column(db.String(64), nullable=True)
    last_verified_at = db.Column(db.DateTime, nullable=True)
    verification_status = db.Column(db.String(30), nullable=False, default='unverified')
    compatibility = db.Column(db.Text, nullable=True)
    technical_notes = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"Post('{self.title}', '{self.date_posted}')"

    def to_dict(self):
        # Método aprimorado para incluir todos os campos - versão compatível Flask 3.x
        result = {}
        # Usar inspecção dos atributos ao invés de __table__ para compatibilidade
        try:
            # SQLAlchemy 2.0+ approach
            from sqlalchemy import inspect
            mapper = inspect(self.__class__)
            for column in mapper.columns:
                result[column.name] = getattr(self, column.name)
        except (AttributeError, TypeError, ValueError):
            # Fallback manual para campos conhecidos
            result = {
                'id': self.id,
                'title': self.title,
                'content': self.content,
                'date_posted': self.date_posted,
                'date_updated': self.date_updated,
                'author_id': self.author_id,
                'category_id': self.category_id,
                'category_str': self.category_str,
                'is_active': self.is_active,
                'featured': self.featured,
                'views': self.views,
                'downloads': self.downloads,
                'tags': self.tags,
                'download_link': self.download_link,
                'image_url': self.image_url
            }

        # Formatar campos de data
        if self.date_posted:
            result['date_posted'] = self.date_posted.strftime('%d/%m/%Y')
        if self.date_updated:
            result['date_updated'] = self.date_updated.strftime('%d/%m/%Y')
        # Adicionar metadados se existirem
        if self.custom_metadata:
            try:
                metadata_dict = json.loads(self.custom_metadata)
                result['custom_metadata'] = metadata_dict
            except (json.JSONDecodeError, TypeError, ValueError):
                result['custom_metadata'] = {}

        return result

    def get_metadata(self, key=None, default=None):
        """Recupera metadados do post como um dicionário ou um valor específico"""
        if not self.custom_metadata:
            return default if key else {}

        try:
            metadata_dict = json.loads(self.custom_metadata)
            if key:
                return metadata_dict.get(key, default)
            return metadata_dict
        except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
            return default if key else {}

    def set_metadata(self, key, value):
        """Define um valor de metadados para o post"""
        try:
            metadata_dict = json.loads(self.custom_metadata) if self.custom_metadata else {}
        except (json.JSONDecodeError, TypeError, ValueError):
            metadata_dict = {}

        metadata_dict[key] = value
        self.custom_metadata = json.dumps(metadata_dict)

    @property
    def is_verified_file(self):
        return self.verification_status == 'verified'

    @property
    def technical_details(self):
        """Linhas preenchidas para exibição, sem inventar dados ausentes."""
        details = (
            ('Fabricante', self.manufacturer),
            ('Marca', self.brand),
            ('Modelo', self.model),
            ('Série', self.series),
            ('Código da placa', self.board_code),
            ('Revisão da placa', self.board_revision),
            ('Plataforma', self.platform),
            ('Chip BIOS', self.bios_chip),
            ('Chip EC', self.ec_chip),
            ('Chip ME', self.me_chip),
            ('Tipo de arquivo', self.file_type),
            ('Formato', self.file_extension),
            ('Tamanho', self.technical_file_size),
            ('Versão', self.version),
            ('Compatibilidade', self.compatibility),
            ('Observações técnicas', self.technical_notes),
        )
        return [(label, value) for label, value in details if value]


class ScheduledPost(db.Model):
    """Fila persistente para publicações criadas como agendadas."""

    __tablename__ = 'scheduled_posts'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False, unique=True, index=True)
    scheduled_for = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    created_by = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    published_at = db.Column(db.DateTime, nullable=True)

    post = db.relationship('Post', backref=db.backref('scheduled_publication', uselist=False))


_scheduled_post_worker_lock = threading.Lock()
_scheduled_post_worker_started = False


def publish_due_scheduled_posts(now=None):
    """Publica de forma idempotente os itens vencidos da fila."""
    current_time = now or datetime.utcnow()
    due_items = ScheduledPost.query.filter(
        ScheduledPost.status == 'pending',
        ScheduledPost.scheduled_for <= current_time,
    ).order_by(ScheduledPost.scheduled_for.asc()).all()

    published = 0
    for item in due_items:
        if not item.post:
            item.status = 'cancelled'
            continue
        item.post.is_active = True
        item.post.date_posted = item.scheduled_for
        item.post.date_updated = current_time
        item.status = 'published'
        item.published_at = current_time
        published += 1

    if due_items:
        db.session.commit()
    return published


def ensure_scheduled_post_worker():
    """Inicia uma verificação leve da fila uma vez por processo web."""
    global _scheduled_post_worker_started
    if app.testing or _scheduled_post_worker_started:
        return

    with _scheduled_post_worker_lock:
        if _scheduled_post_worker_started:
            return
        _scheduled_post_worker_started = True

        def worker():
            while True:
                try:
                    with app.app_context():
                        publish_due_scheduled_posts()
                except Exception:
                    app.logger.exception('Erro ao processar publicações agendadas')
                    try:
                        with app.app_context():
                            db.session.rollback()
                    except Exception:
                        pass
                time.sleep(20)

        threading.Thread(target=worker, name='scheduled-post-publisher', daemon=True).start()


POST_TECHNICAL_FIELDS = (
    'manufacturer', 'brand', 'model', 'series', 'board_code', 'board_revision',
    'platform', 'bios_chip', 'ec_chip', 'me_chip', 'file_type',
    'file_extension', 'technical_file_size', 'version', 'compatibility',
    'technical_notes',
)
VERIFICATION_STATUSES = {'unverified', 'verified', 'needs_review'}


def parse_optional_date(value):
    raw_value = str(value or '').strip()
    if not raw_value:
        return None
    for date_format in ('%Y-%m-%d', '%Y-%m-%dT%H:%M', '%d/%m/%Y'):
        try:
            return datetime.strptime(raw_value, date_format)
        except ValueError:
            continue
    raise ValueError('Data de verificação inválida.')


def normalize_sha256(value):
    normalized = re.sub(r'\s+', '', str(value or '')).lower()
    if normalized and not re.fullmatch(r'[a-f0-9]{64}', normalized):
        raise ValueError('O SHA-256 deve conter exatamente 64 caracteres hexadecimais.')
    return normalized or None


def normalize_download_url(value):
    """Aceita somente URLs HTTP(S) ou caminhos internos absolutos."""
    candidate = str(value or '').strip()
    if not candidate:
        return None
    try:
        parsed = url_parse(candidate)
    except (TypeError, ValueError):
        return None
    if parsed.scheme in {'http', 'https'} and parsed.netloc:
        return candidate
    if not parsed.scheme and not parsed.netloc and candidate.startswith('/') and not candidate.startswith('//'):
        return candidate
    return None


def normalize_optional_external_url(value):
    """Normaliza um link opcional de perfil e rejeita esquemas executáveis."""
    candidate = str(value or '').strip()
    if not candidate:
        return ''
    try:
        parsed = url_parse(candidate)
    except (TypeError, ValueError) as exc:
        raise ValueError('Informe uma URL válida, iniciada por http:// ou https://.') from exc
    if parsed.scheme.lower() not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('Informe uma URL válida, iniciada por http:// ou https://.')
    return candidate


def normalize_download_files(raw_value):
    """Valida metadados de múltiplos arquivos antes de armazená-los como JSON."""
    if not raw_value:
        return []
    try:
        items = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError('A lista de arquivos é inválida.') from exc
    if not isinstance(items, list):
        raise ValueError('A lista de arquivos é inválida.')

    normalized_files = []
    for item in items[:20]:
        if not isinstance(item, dict):
            continue
        file_url = normalize_download_url(item.get('url'))
        if not file_url:
            raise ValueError('Um dos links de download é inválido.')
        normalized_files.append({
            'type': normalize_download_file_type_label(item.get('type') or 'Outros'),
            'url': file_url,
            'name': sanitize_input(str(item.get('name') or ''))[:200],
            'format': sanitize_input(str(item.get('format') or ''))[:30],
            'size': sanitize_input(str(item.get('size') or ''))[:50],
            'sha256': normalize_sha256(item.get('sha256')),
        })
    return normalized_files


def get_public_download_files(post):
    """Expõe metadados úteis sem revelar os links externos de origem."""
    files = post.get_metadata('download_files') or []
    if isinstance(files, list) and files:
        public_files = []
        for index, item in enumerate(files):
            if not isinstance(item, dict):
                continue
            try:
                file_hash = normalize_sha256(item.get('sha256')) or ''
            except ValueError:
                file_hash = ''
            public_files.append({
                'type': normalize_download_file_type_label(item.get('type') or 'Outros'),
                'name': sanitize_input(str(item.get('name') or ''))[:200],
                'format': sanitize_input(str(item.get('format') or ''))[:30],
                'size': sanitize_input(str(item.get('size') or ''))[:50],
                'sha256': file_hash,
                'url': url_for('download_post', post_id=post.id, file=index),
            })
        return public_files

    persisted_files = TechnicalFile.query.filter_by(
        post_id=post.id, is_active=True,
    ).order_by(TechnicalFile.id.asc()).all()
    return [technical_file.public_dict() for technical_file in persisted_files]


def sync_post_download_summary(post, download_files):
    """Sincroniza o resumo e registros legados sem trocar BIOS/EC pela ordem de clique."""
    if not download_files:
        return

    types = list(dict.fromkeys(
        normalize_download_file_type_label(item.get('type') or 'Outros')
        for item in download_files
    ))
    formats = list(dict.fromkeys(
        sanitize_input(str(item.get('format') or '')).upper()[:30]
        for item in download_files if item.get('format')
    ))
    post.file_type = '/'.join(types)[:80] or None
    post.file_extension = '/'.join(formats)[:30] or None
    post.technical_file_size = sanitize_input(str(download_files[0].get('size') or ''))[:50] or None

    persisted_files = TechnicalFile.query.filter_by(post_id=post.id).all() if post.id else []
    for item in download_files:
        source_url = normalize_download_url(item.get('url'))
        if not source_url:
            continue
        technical_file = next((candidate for candidate in persisted_files if source_url in {
            candidate.provider_url, candidate.provider_direct_url, candidate.source_url,
        }), None)
        if not technical_file:
            continue
        technical_file.file_type = normalize_download_file_type_label(item.get('type') or 'Outros')[:80]
        technical_file.extension = sanitize_input(str(item.get('format') or ''))[:30] or None


def format_technical_file_size(size_bytes):
    if size_bytes is None:
        return ''
    try:
        size = float(size_bytes)
    except (TypeError, ValueError):
        return ''
    units = ('B', 'KB', 'MB', 'GB', 'TB')
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    precision = 0 if unit_index == 0 else 1
    return f'{size:.{precision}f} {units[unit_index]}'


def apply_post_technical_form(post, form, *, preserve_missing=False):
    """Valida e aplica os campos técnicos enviados pelo painel."""
    for field_name in POST_TECHNICAL_FIELDS:
        if preserve_missing and field_name not in form:
            continue
        raw_value = str(form.get(field_name, '') or '').strip()
        max_length = 2000 if field_name in {'compatibility', 'technical_notes'} else 160
        setattr(post, field_name, sanitize_input(raw_value[:max_length]) or None)

    raw_status = str(form.get('verification_status', '') or '').strip().lower()
    if preserve_missing and 'verification_status' not in form:
        return
    status = raw_status or 'unverified'
    if status not in VERIFICATION_STATUSES:
        raise ValueError('Status de verificação inválido.')

    post.verification_status = status
    if not preserve_missing or 'last_verified_at' in form:
        post.last_verified_at = parse_optional_date(form.get('last_verified_at'))
    if not preserve_missing or 'sha256' in form:
        post.sha256 = normalize_sha256(form.get('sha256'))


def post_search_values(post):
    return (
        post.title, post.model, post.manufacturer, post.brand, post.series,
        post.board_code, post.board_revision, post.platform, post.bios_chip,
        post.ec_chip, post.me_chip, post.file_type, post.file_extension,
        post.version, post.compatibility, post.technical_notes, post.content,
        post.seo_title, post.seo_description, post.tags, post.category_str,
        post.subcategory, post.slug,
    )


def get_post_search_score(query, post):
    """Prioriza código exato de placa e depois os demais campos técnicos."""
    board_score = get_search_match_score(query, post.board_code)
    if board_score is not None:
        return board_score - 20

    model_score = get_search_match_score(query, post.model)
    if model_score is not None:
        return model_score - 8

    return get_search_match_score(query, *post_search_values(post))

# Funções helper para analytics
def get_device_type(user_agent_string):
    """Detecta o tipo de dispositivo baseado no user agent"""
    if not user_agent_string:
        return 'Unknown'

    try:
        parsed_agent = parse_ua(user_agent_string)
        if parsed_agent.is_tablet:
            return 'Tablet'
        if parsed_agent.is_mobile:
            return 'Mobile'
        if parsed_agent.is_pc:
            return 'Desktop'
        if parsed_agent.is_bot:
            return 'Bot'
    except Exception:
        pass

    user_agent = user_agent_string.lower()
    if any(device in user_agent for device in ['ipad', 'tablet', 'kindle', 'silk']):
        return 'Tablet'
    if any(device in user_agent for device in ['iphone', 'android', 'mobile', 'windows phone']):
        return 'Mobile'
    if any(device in user_agent for device in ['bot', 'crawler', 'spider']):
        return 'Bot'
    return 'Desktop'

def get_browser_name(user_agent_string):
    """Detecta o nome do navegador baseado no user agent"""
    if not user_agent_string:
        return 'Unknown'

    try:
        browser_family = parse_ua(user_agent_string).browser.family or ''
        normalized_browser = browser_family.strip()
        if normalized_browser:
            browser_map = {
                'Chrome Mobile': 'Chrome',
                'Chrome Mobile iOS': 'Chrome',
                'Mobile Safari': 'Safari',
                'Firefox Mobile': 'Firefox',
                'Firefox iOS': 'Firefox',
                'Edge': 'Edge',
                'Edge Mobile': 'Edge',
                'Opera Mobile': 'Opera',
                'Samsung Internet': 'Samsung Internet'
            }
            return browser_map.get(normalized_browser, normalized_browser)
    except Exception:
        pass

    user_agent = user_agent_string.lower()
    if any(token in user_agent for token in ['edg/', 'edga/', 'edgios/']):
        return 'Edge'
    if any(token in user_agent for token in ['opr/', 'opera']):
        return 'Opera'
    if 'samsungbrowser' in user_agent:
        return 'Samsung Internet'
    if any(token in user_agent for token in ['firefox', 'fxios']):
        return 'Firefox'
    if any(token in user_agent for token in ['crios', 'chrome']) and 'chromium' not in user_agent:
        return 'Chrome'
    if 'safari' in user_agent:
        return 'Safari'
    return 'Outro'

# ==========================================
# FUNÇÕES UTILITÁRIAS
# ==========================================
def generate_slug(text):
    """Gera um slug URL-friendly a partir de um texto"""
    import unicodedata

    # Normalizar caracteres unicode
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')

    # Converter para minúsculas e substituir espaços por hífens
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    text = text.strip('-')

    return text


def generate_image_filename(title, file_extension):
    """Gera um nome de arquivo para imagem baseado no título do post

    Args:
        title: Título do post
        file_extension: Extensão do arquivo (jpg, png, etc.)

    Returns:
        Nome do arquivo formatado (ex: Acer_Aspire_A315-53_(Intel_i5_7_Geracao).jpg)
    """
    import unicodedata

    # Normalizar caracteres unicode e remover acentos
    text = unicodedata.normalize('NFKD', title)
    text = text.encode('ascii', 'ignore').decode('ascii')

    # Substituir espaços por underscores
    text = text.replace(' ', '_')

    # Remover caracteres especiais, mantendo letras, números, underscores, hífens e parênteses
    text = re.sub(r'[^\w\s\-()\_-]', '', text)

    # Remover múltiplos underscores consecutivos
    text = re.sub(r'_+', '_', text)

    # Remover underscores no início e fim
    text = text.strip('_')

    # Garantir extensão em minúsculas
    file_extension = file_extension.lower()

    return f"{text}.{file_extension}"


def validate_comment_data(data) -> tuple[bool, str | None, dict | None]:
    """
    Valida dados de um comentário.

    Args:
        data: Dicionário com os dados do comentário

    Returns:
        tuple: (success: bool, error_message: str or None, validated_data: dict or None)
        - Se success=True: (True, None, {'content': str, 'author_name': str, 'author_email': str})
        - Se success=False: (False, error_message: str, None)
    """
    content = data.get('content', '').strip()
    author_name = data.get('name', '').strip()
    author_email = data.get('email', '').strip()

    # Validações
    if not content:
        return False, 'O comentário não pode estar vazio.', None

    if len(content) < 3:
        return False, 'O comentário deve ter pelo menos 3 caracteres.', None

    if len(content) > 1000:
        return False, 'O comentário não pode ter mais de 1000 caracteres.', None

    # Sanitizar conteúdo para prevenir XSS
    content = sanitize_html(content)

    # Validação opcional de nome (se fornecido)
    if author_name:
        if len(author_name) > 100:
            return False, 'O nome não pode ter mais de 100 caracteres.', None
        author_name = sanitize_input(author_name)

    # Validação opcional de email (se fornecido)
    if author_email:
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, author_email):
            return False, 'Email inválido.', None
        author_email = sanitize_input(author_email)

    validated_data = {
        'content': content,
        'author_name': author_name,
        'author_email': author_email
    }

    return True, None, validated_data


def sanitize_input(text):
    """Remove HTML e scripts perigosos de inputs de texto"""
    if not text:
        return text
    # Remove tags HTML e normaliza espaços
    text = bleach.clean(text, tags=[], strip=True)
    return text.strip()


def sanitize_html(html_content):
    """Sanitiza conteúdo HTML permitindo apenas tags seguras"""
    if not html_content:
        return html_content

    # Tags e atributos permitidos
    allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li', 'blockquote', 'code']
    allowed_attributes = {'a': ['href', 'title']}

    # Limpar HTML mantendo apenas tags seguras
    clean_html = bleach.clean(
        html_content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True
    )

    return clean_html


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Valida a força de uma senha

    Args:
        password: Senha a ser validada

    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    if not password:
        return False, 'A senha não pode estar vazia.'

    if len(password) < 8:
        return False, 'A senha deve ter pelo menos 8 caracteres.'

    if len(password) > 128:
        return False, 'A senha não pode ter mais de 128 caracteres.'

    # Verificar se contém pelo menos uma letra maiúscula
    if not re.search(r'[A-Z]', password):
        return False, 'A senha deve conter pelo menos uma letra maiúscula.'

    # Verificar se contém pelo menos uma letra minúscula
    if not re.search(r'[a-z]', password):
        return False, 'A senha deve conter pelo menos uma letra minúscula.'

    # Verificar se contém pelo menos um número
    if not re.search(r'\d', password):
        return False, 'A senha deve conter pelo menos um número.'

    # Verificar se contém pelo menos um caractere especial
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, 'A senha deve conter pelo menos um caractere especial (!@#$%^&*(),.?":{}|<>).'

    return True, ''


def delete_old_image(image_path, protected_images=None):
    """
    Deleta uma imagem antiga do filesystem.

    Args:
        image_path (str): Caminho relativo da imagem (ex: 'posts/abc123.jpg' ou 'profile.jpg')
        protected_images (list): Lista de imagens que não devem ser deletadas

    Returns:
        bool: True se deletou com sucesso ou não era necessário, False se houve erro
    """
    if protected_images is None:
        protected_images = ['default.jpg', 'admin-avatar.jpg']

    try:
        # Verificar se não é uma imagem protegida
        filename = os.path.basename(image_path)
        if filename in protected_images or not image_path:
            return True

        # Construir caminho completo
        # Se já tiver 'static/' no início, remover
        if image_path.startswith('static/'):
            image_path = image_path[7:]

        # Caminho pode ser:
        # - "posts/image.jpg" (precisa adicionar static/images/)
        # - "profile.jpg" (precisa adicionar static/uploads/profiles/)
        # - "images/posts/image.jpg" (precisa adicionar apenas static/)

        if image_path.startswith('posts/'):
            full_path = os.path.join(app.root_path, 'static', 'images', image_path)
        elif image_path.startswith('images/'):
            full_path = os.path.join(app.root_path, 'static', image_path)
        else:
            # Assume que é uma imagem de perfil
            full_path = os.path.join(app.root_path, 'static', 'uploads', 'profiles', image_path)

        # Deletar se existir
        if os.path.exists(full_path):
            os.remove(full_path)
            app.logger.info('Imagem antiga removida: %s', full_path)
            return True

        return True  # Não existia, então não há problema

    except Exception as e:
        app.logger.error('Erro ao remover imagem %s: %s', image_path, e)
        return False

# ==========================================
# DADOS PADRÃO DAS CATEGORIAS
# ==========================================
def get_default_category_data():
    """
    Retorna o mapeamento padrão de ícones e descrições para as categorias.
    Este padrão é usado em toda a aplicação (home, página de categorias, admin).
    """
    return {
        'BIOS': {
            'icon': 'fas fa-microchip',
            'description': 'Arquivos de BIOS organizados por modelo e código da placa, conforme os cadastros disponíveis.'
        },
        'Esquemas': {
            'icon': 'fas fa-project-diagram',
            'description': 'Esquemas elétricos e documentos de placa organizados para consulta em diagnóstico e reparo.'
        },
        'Drivers': {
            'icon': 'fas fa-cogs',
            'description': 'Drivers cadastrados por dispositivo, fabricante e compatibilidade informada.'
        },
        'Softwares': {
            'icon': 'fas fa-laptop-code',
            'description': 'Programas e utilitários para diagnóstico, manutenção e recuperação, conforme o acervo cadastrado.'
        },
        'Impressoras': {
            'icon': 'fas fa-print',
            'description': 'Drivers, firmwares e recursos de impressoras organizados por marca e modelo.'
        },
        'Cursos': {
            'icon': 'fas fa-graduation-cap',
            'description': 'Materiais educativos e cursos cadastrados sobre informática, eletrônica e tecnologia.'
        },
        'Datasheet': {
            'icon': 'fas fa-file-alt',
            'description': 'Datasheets de componentes eletrônicos, circuitos integrados e semicondutores para consulta.'
        }
    }

def apply_default_category_data(category):
    """
    Preenche ícone e descrição padrão sem sobrescrever personalizações do admin.
    """
    default_data = get_default_category_data()
    if category.name in default_data:
        if not category.icon:
            category.icon = default_data[category.name]['icon']
        if not category.description:
            category.description = default_data[category.name]['description']
    return category

def coerce_bool(value, default=False):
    """Converte valores de formulário/JSON para boolean sem tratar 'false' como True."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'true', '1', 'on', 'yes', 'sim'}:
            return True
        if normalized in {'false', '0', 'off', 'no', 'nao', 'não', ''}:
            return False
    return default

def coerce_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_float(value: object) -> float:
    """Converte entrada numérica validada sem aceitar ``None`` silenciosamente."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise TypeError('Valor numérico inválido.')
    if isinstance(value, str) and not value.strip():
        raise ValueError('Valor numérico vazio.')
    return float(value)


def category_public_url_value(category):
    return category.slug or generate_slug(category.name)

def get_category_query_filter(category):
    category_record = Category.query.filter(
        db.or_(
            Category.slug == category,
            Category.name == category
        )
    ).first()

    if category_record:
        if not category_record.is_active or not category_record.is_visible:
            abort(404)
        category_filter = db.or_(
            Post.category_id == category_record.id,
            Post.category_str == category_record.name
        )
        return category_record, category_filter, category_record.name

    category_filter = Post.category_str == category
    return None, category_filter, category

def build_category_admin_payload(category):
    apply_default_category_data(category)
    post_filter = db.or_(Post.category_id == category.id, Post.category_str == category.name)
    post_count = Post.query.filter(post_filter, Post.is_active == True).count()
    featured_posts = Post.query.filter(post_filter, Post.is_active == True, Post.featured == True).count()
    total_downloads = db.session.query(db.func.sum(Post.downloads)).filter(post_filter, Post.is_active == True).scalar() or 0
    last_post = Post.query.filter(post_filter, Post.is_active == True).order_by(Post.date_posted.desc()).first()

    return {
        'id': category.id,
        'name': category.name,
        'slug': category.slug,
        'description': category.description or '',
        'icon': category.icon or 'fas fa-folder',
        'color': category.color or '#4a90e2',
        'post_count': post_count,
        'featured_posts': featured_posts,
        'total_downloads': int(total_downloads or 0),
        'is_active': bool(category.is_active),
        'is_visible': bool(category.is_visible),
        'is_featured': bool(category.featured),
        'featured': bool(category.featured),
        'show_in_menu': bool(category.show_in_menu),
        'order': category.order or 0,
        'created_at': category.created_at if hasattr(category, 'created_at') else None,
        'last_post_date': last_post.date_posted if last_post else None,
        'last_post_title': last_post.title if last_post else None
    }


def get_public_categories_partition():
    """Separa categorias com conteúdo das categorias ainda em expansão."""
    visible_categories = Category.query.filter_by(is_active=True, is_visible=True).order_by(
        Category.order.asc(), Category.name.asc()
    ).all()
    populated = []
    empty = []
    for category in visible_categories:
        category_filter = db.or_(Post.category_id == category.id, Post.category_str == category.name)
        category.public_post_count = Post.query.filter(category_filter, Post.is_active == True).count()
        (populated if category.public_post_count else empty).append(category)
    return populated, empty

class ListPagination:
    def __init__(self, items, page=1, per_page=10):
        self.page = max(1, int(page or 1))
        self.per_page = max(1, int(per_page or 10))
        self.total = len(items)
        self.pages = max(1, math.ceil(self.total / self.per_page))
        self.page = min(self.page, self.pages)
        start = (self.page - 1) * self.per_page
        end = start + self.per_page
        self.items = items[start:end]

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def prev_num(self):
        return self.page - 1 if self.has_prev else None

    @property
    def next_num(self):
        return self.page + 1 if self.has_next else None

    def iter_pages(self, left_edge=1, left_current=1, right_current=2, right_edge=1):
        last = 0
        for num in range(1, self.pages + 1):
            if (
                num <= left_edge
                or (num > self.page - left_current - 1 and num < self.page + right_current)
                or num > self.pages - right_edge
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num

def create_database_backup():
    """Cria backup do banco de dados"""
    try:
        # Diretório para backups
        backup_dir = os.path.join(app.instance_path, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        # Nome do arquivo de backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"database_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_filename)

        # Copiar o banco de dados
        db_path = os.path.join(app.instance_path, 'site.db')
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)

            # Obter tamanho do arquivo
            file_size = os.path.getsize(backup_path)

            return {
                'success': True,
                'filename': backup_filename,
                'file_path': backup_path,
                'file_size': file_size
            }
        else:
            return {'success': False, 'error': 'Banco de dados não encontrado'}

    except Exception as e:
        return {'success': False, 'error': str(e)}

def create_files_backup():
    """Cria backup dos arquivos estáticos"""
    try:
        import zipfile

        # Diretório para backups
        backup_dir = os.path.join(app.instance_path, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        # Nome do arquivo de backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"files_backup_{timestamp}.zip"
        backup_path = os.path.join(backup_dir, backup_filename)

        # Diretórios para incluir no backup
        dirs_to_backup = [
            'static/uploads',
            'static/images/profiles',
            'templates'
        ]

        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for dir_name in dirs_to_backup:
                dir_path = os.path.join(os.path.dirname(__file__), dir_name)
                if os.path.exists(dir_path):
                    for root, _, files in os.walk(dir_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(__file__))
                            zipf.write(file_path, arcname)

        # Obter tamanho do arquivo
        file_size = os.path.getsize(backup_path)

        return {
            'success': True,
            'filename': backup_filename,
            'file_path': backup_path,
            'file_size': file_size
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}

def create_full_backup():
    """Cria backup completo (banco de dados + arquivos)"""
    try:
        import zipfile

        # Diretório para backups
        backup_dir = os.path.join(app.instance_path, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        # Nome do arquivo de backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"full_backup_{timestamp}.zip"
        backup_path = os.path.join(backup_dir, backup_filename)

        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Adicionar banco de dados
            db_path = os.path.join(app.instance_path, 'site.db')
            if os.path.exists(db_path):
                zipf.write(db_path, 'database/site.db')

            # Adicionar arquivos
            dirs_to_backup = [
                'static/uploads',
                'static/images/profiles',
                'templates'
            ]

            for dir_name in dirs_to_backup:
                dir_path = os.path.join(os.path.dirname(__file__), dir_name)
                if os.path.exists(dir_path):
                    for root, _, files in os.walk(dir_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(__file__))
                            zipf.write(file_path, f"files/{arcname}")

        # Obter tamanho do arquivo
        file_size = os.path.getsize(backup_path)

        return {
            'success': True,
            'filename': backup_filename,
            'file_path': backup_path,
            'file_size': file_size
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}

def log_admin_activity(user_id, action, description=None, metadata=None):
    """Registra atividade administrativa"""
    try:
        # Pegar informações da requisição
        ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()

        user_agent = request.headers.get('User-Agent', '')

        # Converter metadata para JSON se necessário
        metadata_json = None
        if metadata:
            try:
                metadata_json = json.dumps(metadata)
            except (TypeError, ValueError):
                metadata_json = str(metadata)

        activity = AdminActivity(
            user_id=user_id,
            action=action,
            description=description,
            activity_metadata=metadata_json,
            ip_address=ip_address,
            user_agent=user_agent
        )

        db.session.add(activity)
        db.session.commit()

    except Exception as e:
        app.logger.error('Erro ao registrar atividade administrativa: %s', e)
        try:
            db.session.rollback()
        except Exception:
            pass

def log_visitor():
    """Registra informações do visitante para analytics"""
    try:
        # Pegar informações da requisição
        ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()

        user_agent = request.headers.get('User-Agent', '')
        referrer = request.headers.get('Referer', '')
        device_type = get_device_type(user_agent)
        browser = get_browser_name(user_agent)

        # Verificar se já existe um log recente para este IP (últimas 30 minutos)
        recent_log = VisitorLog.query.filter(
            VisitorLog.ip_address == ip_address,
            VisitorLog.visit_time >= datetime.utcnow() - timedelta(minutes=30)
        ).first()

        # Só criar novo log se não houver um recente
        if not recent_log:
            visitor_log = VisitorLog(
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else '',  # Limitar tamanho
                referrer=referrer[:500] if referrer else '',  # Limitar tamanho
                device_type=device_type,
                browser=browser,
                visit_time=datetime.utcnow()
            )
            db.session.add(visitor_log)
            db.session.commit()
    except Exception as e:
        # Em caso de erro, apenas logar mas não interromper a aplicação
        app.logger.error('Erro ao registrar visitante: %s', e)
        try:
            db.session.rollback()
        except Exception:
            pass

def increment_post_views(post_id):
    """Incrementa as visualizações de um post"""
    try:
        post = Post.query.get(post_id)
        if post:
            post.views = (post.views or 0) + 1
            db.session.commit()

        # Também registrar em PostStats para estatísticas diárias
        today = datetime.utcnow().date()
        post_stat = PostStats.query.filter_by(post_id=post_id, date=today).first()

        if post_stat:
            post_stat.views += 1
        else:
            post_stat = PostStats(post_id=post_id, date=today, views=1, downloads=0)
            db.session.add(post_stat)

        db.session.commit()
    except Exception as e:
        app.logger.error('Erro ao incrementar visualizacoes do post %s: %s', post_id, e)
        try:
            db.session.rollback()
        except Exception:
            pass

def increment_post_downloads(post_id):
    """Incrementa os downloads de um post"""
    try:
        post = Post.query.get(post_id)
        if post:
            post.downloads = (post.downloads or 0) + 1
            db.session.commit()

        # Também registrar em PostStats para estatísticas diárias
        today = datetime.utcnow().date()
        post_stat = PostStats.query.filter_by(post_id=post_id, date=today).first()

        if post_stat:
            post_stat.downloads += 1
        else:
            post_stat = PostStats(post_id=post_id, date=today, views=0, downloads=1)
            db.session.add(post_stat)

        db.session.commit()
    except Exception as e:
        app.logger.error('Erro ao incrementar downloads do post %s: %s', post_id, e)
        try:
            db.session.rollback()
        except Exception:
            pass

@app.before_request
def before_request():
    """Executado antes de cada requisição"""
    ensure_scheduled_post_worker()
    try:
        publish_due_scheduled_posts()
    except Exception:
        db.session.rollback()
        app.logger.exception('Erro ao verificar publicações agendadas durante a requisição')

    canonical_host = (os.environ.get('CANONICAL_HOST') or 'mundodainformatica.com').strip().lower()
    request_host = (request.host or '').split(':', 1)[0].lower()
    alternate_hosts = {f'www.{canonical_host}'} if not canonical_host.startswith('www.') else {canonical_host[4:]}
    if is_production_environment() and request_host in alternate_hosts:
        canonical_target = f'https://{canonical_host}{request.full_path if request.query_string else request.path}'
        return redirect(canonical_target.rstrip('?'), code=301)

    if request.path == '/home':
        return redirect('/', code=301)

    # Atualizar last_login do usuário autenticado
    if current_user.is_authenticated:
        # Atualizar a cada request, mas apenas se passou mais de 5 minutos desde a última atualização
        # para evitar sobrecarga no banco de dados
        if current_user.last_login is None or (datetime.utcnow() - current_user.last_login).total_seconds() > 300:
            try:
                current_user.last_login = datetime.utcnow()
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error('Erro ao atualizar last_login: %s', e)

    # Verificar modo de manutenção
    try:
        maintenance_mode = SiteConfig.get_value('maintenance_mode', False)
        if maintenance_mode and not (current_user.is_authenticated and current_user.role in ('admin', 'editor')):
            # Permitir acesso apenas a rotas específicas durante manutenção
            allowed_routes = ['static', 'admin', 'login', 'maintenance', 'api_site_settings']
            if not request.endpoint or not any(request.endpoint.startswith(route) for route in allowed_routes):
                return render_template('errors/maintenance.html'), 503
    except Exception:
        pass  # Em caso de erro, continuar normalmente
    # Registrar visitante apenas para páginas principais (não admin, static, etc)
    if request.endpoint and not request.endpoint.startswith(('admin', 'static')):
        log_visitor()

@app.context_processor
def utility_processor():
    """Funções utilitárias para templates"""
    def get_image_url(image_path, folder='profiles', default='default.jpg'):
        return get_image_url_for_response(image_path, folder=folder, default=default)

    return dict(get_image_url=get_image_url, get_category_icon=get_category_icon)

@app.context_processor
def inject_admin_data():
    """Injeta dados administrativos em todos os templates"""
    if request.endpoint and request.endpoint.startswith('admin'):
        try:
            return {
                'post_count': Post.query.filter_by(is_active=True).count(),
                'category_count': Category.query.filter_by(is_active=True).count(),
                'unread_comments': Comment.query.count(),
                'total_users': User.query.filter_by(is_active=True).count(),
                'total_subscribers': Subscriber.query.filter_by(is_active=True).count(),
                'content_request_count': ContentRequest.query.filter(ContentRequest.status.in_(['pending', 'reviewing', 'searching'])).count(),
                'technical_review_count': (
                    ImportItem.query.filter(ImportItem.status.in_(['pending_review', 'needs_storage', 'needs_review'])).count()
                    + DatasheetImportQueue.query.filter_by(status='needs_review').count()
                ),
                'download_file_types': get_download_file_types(),
                'app_version': '1.6.2'
            }
        except Exception as e:
            app.logger.error('Erro ao injetar dados admin: %s', e)
            return {
                'post_count': 0,
                'category_count': 0,
                'unread_comments': 0,
                'total_users': 0,
                'total_subscribers': 0,
                'content_request_count': 0,
                'technical_review_count': 0,
                'download_file_types': [dict(item) for item in DEFAULT_DOWNLOAD_FILE_TYPES],
                'app_version': '1.6.2'
            }
    return {}

# Modelo para usuários e administradores
class User(db.Model, UserMixin):
    """Modelo de usuário para armazenar informações de contas"""
    __tablename__ = 'user'
    __table_args__ = {'extend_existing': True}  # Permitir redefinição da tabela

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100))  # Nome completo
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))

    # Informações de perfil
    profile_image = db.Column(db.String(120), default='default_profile.jpg')
    bio = db.Column(db.Text)
    location = db.Column(db.String(100))

    # Contato
    phone = db.Column(db.String(20))
    website = db.Column(db.String(120))

    # Redes sociais
    facebook = db.Column(db.String(200))
    twitter = db.Column(db.String(200))
    instagram = db.Column(db.String(200))
    linkedin = db.Column(db.String(200))
    github = db.Column(db.String(200))

    # Controle de acesso e status
    role = db.Column(db.String(20), default='user')  # 'admin', 'editor', 'user'
    plan = db.Column(db.String(20), default='free')  # 'free', 'premium', 'vip'
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)

    # Datas importantes
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    subscription_end_date = db.Column(db.DateTime, nullable=True)

    # Preferências
    email_notifications = db.Column(db.Boolean, default=True)
    theme_preference = db.Column(db.String(20), default='light')
    preferences = db.Column(db.Text)

    # Token para redefinição de senha (expira após 24 horas)
    reset_token = db.Column(db.String(100))
    reset_token_expiry = db.Column(db.DateTime)

    # Dados de rastreamento e navegação
    ip_address = db.Column(db.String(45))  # Suporta IPv4 e IPv6


    browser = db.Column(db.String(100))  # Tipo de navegador e versão
    operating_system = db.Column(db.String(100))  # Sistema operacional

    # Controle de dispositivos simultâneos
    active_sessions = db.Column(db.Integer, default=0)  # Número de sessões ativas
    pages_visited = db.Column(db.Text)  # JSON com páginas visitadas
    time_on_pages = db.Column(db.Text)  # JSON com tempo em cada página
    access_timestamps = db.Column(db.Text)  # JSON com data/hora de acessos
    referrer = db.Column(db.String(500))  # Site de onde o usuário veio

    # Controle de downloads diários
    daily_downloads = db.Column(db.Integer, default=0)  # Contador de downloads do dia
    download_reset_date = db.Column(db.DateTime)  # Data de reset do contador

    # Controle de downloads semanais (para plano Premium)
    weekly_downloads = db.Column(db.Integer, default=0)  # Contador de downloads da semana
    week_reset_date = db.Column(db.DateTime)  # Data de reset semanal (domingo 00:00)

    # Permissões de download personalizadas
    can_download = db.Column(db.Boolean, default=True)  # Permite ou bloqueia downloads totalmente
    custom_daily_limit = db.Column(db.Integer, nullable=True)  # Limite diário personalizado (None = usar padrão do plano)
    custom_weekly_limit = db.Column(db.Integer, nullable=True)  # Limite semanal personalizado (None = usar padrão do plano)

    def set_password(self, password):
        """Gera hash da senha fornecida"""
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        """Verifica se a senha fornecida corresponde ao hash armazenado"""
        return check_password_hash(self.password_hash, password)

    def get_reset_token(self, expires_sec=86400):
        """Gera um token para redefinição de senha"""
        s = Serializer(app.config['SECRET_KEY'])
        token_data = s.dumps({'user_id': self.id})
        # O token já é uma string nas versões mais recentes
        self.reset_token = str(token_data)
        self.reset_token_expiry = datetime.utcnow() + timedelta(seconds=expires_sec)
        db.session.commit()
        return self.reset_token

    @staticmethod
    def verify_reset_token(token):
        """Verifica se o token de redefinição é válido"""
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=86400)['user_id']
            return User.query.get(user_id)
        except (ValueError, TypeError, KeyError):
            return None

    def get_full_name(self):
        """Retorna o nome completo do usuário"""
        if hasattr(self, 'name') and self.name:
            return self.name
        elif self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return self.username

    def is_admin(self):
        """Verifica se o usuário é um administrador"""
        return self.role == 'admin'

    def is_editor(self):
        """Verifica se o usuário é um editor"""
        return self.role == 'editor'

    def update_last_login(self):
        """Atualiza a data do último login"""
        self.last_login = datetime.utcnow()
        db.session.commit()

    def get_initials(self):
        """Gera as iniciais do nome do usuário para exibição em placeholders."""
        if not self.first_name and not self.last_name:
            return "MI"

        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)

        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        elif len(parts) == 1:
            return parts[0][0].upper()
        else:
            return "MI"

    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.role}')"

class Download(db.Model):
    """Modelo para rastrear downloads de usuários"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    technical_file_id = db.Column(db.Integer, db.ForeignKey('technical_files.id'), nullable=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('technical_resources.id'), nullable=True)
    plan_snapshot = db.Column(db.String(20), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    user = db.relationship('User', backref=db.backref('download_records', lazy=True, cascade="all, delete"))
    post = db.relationship('Post', backref=db.backref('download_records', lazy=True, cascade="all, delete"))

    # Constraint para evitar duplicatas no mesmo momento
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', 'timestamp', name='unique_user_post_download_time'),)


class HardwareBoard(db.Model):
    """Placa normalizada compartilhada por posts e recursos técnicos."""
    __tablename__ = 'hardware_boards'

    id = db.Column(db.Integer, primary_key=True)
    manufacturer = db.Column(db.String(120), nullable=True, index=True)
    board_manufacturer = db.Column(db.String(120), nullable=True)
    device_model = db.Column(db.String(160), nullable=True, index=True)
    device_series = db.Column(db.String(160), nullable=True)
    board_code = db.Column(db.String(120), nullable=False)
    normalized_board_code = db.Column(db.String(120), nullable=False, index=True)
    board_revision = db.Column(db.String(80), nullable=True)
    platform = db.Column(db.String(120), nullable=True)
    chipset = db.Column(db.String(120), nullable=True)
    cpu_family = db.Column(db.String(120), nullable=True)
    super_io = db.Column(db.String(120), nullable=True)
    ec_controller = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    slug = db.Column(db.String(250), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ContentSource(db.Model):
    """Origem técnica e política de confiança/distribuição."""
    __tablename__ = 'content_sources'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    provider_type = db.Column(db.String(40), nullable=False, default='manual')
    trust_level = db.Column(db.String(1), nullable=False, default='C')
    auto_publish = db.Column(db.Boolean, nullable=False, default=False)
    metadata_allowed = db.Column(db.Boolean, nullable=False, default=True)
    distribution_allowed = db.Column(db.Boolean, nullable=False, default=False)
    file_mirroring_allowed = db.Column(db.Boolean, nullable=False, default=False)
    attribution_required = db.Column(db.Boolean, nullable=False, default=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    config_json = db.Column(db.Text, nullable=True)
    last_sync_at = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def configuration(self):
        try:
            value = json.loads(self.config_json or '{}')
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}


class TechnicalResource(db.Model):
    __tablename__ = 'technical_resources'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=True, index=True)
    board_id = db.Column(db.Integer, db.ForeignKey('hardware_boards.id'), nullable=True, index=True)
    resource_type = db.Column(db.String(40), nullable=False, default='other')
    title = db.Column(db.String(200), nullable=False)
    manufacturer = db.Column(db.String(120), nullable=True)
    model = db.Column(db.String(160), nullable=True)
    part_number = db.Column(db.String(160), nullable=True, index=True)
    board_code = db.Column(db.String(120), nullable=True, index=True)
    board_revision = db.Column(db.String(80), nullable=True)
    chip = db.Column(db.String(120), nullable=True)
    chip_position = db.Column(db.String(50), nullable=True)
    version = db.Column(db.String(80), nullable=True)
    source_type = db.Column(db.String(40), nullable=False, default='manual')
    source_provider = db.Column(db.String(120), nullable=True)
    source_reference = db.Column(db.Text, nullable=True)
    external_id = db.Column(db.String(255), nullable=True, index=True)
    external_version = db.Column(db.String(120), nullable=True)
    last_synced_at = db.Column(db.DateTime, nullable=True)
    verification_status = db.Column(db.String(30), nullable=False, default='needs_review')
    verification_date = db.Column(db.DateTime, nullable=True)
    license_status = db.Column(db.String(40), nullable=False, default='unknown')
    distribution_policy = db.Column(db.String(40), nullable=False, default='unknown')
    metadata_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    board = db.relationship('HardwareBoard', backref=db.backref('resources', lazy=True))
    post = db.relationship('Post', backref=db.backref('technical_resources', lazy=True))


class TechnicalFile(db.Model):
    __tablename__ = 'technical_files'

    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('technical_resources.id'), nullable=True, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=True, index=True)
    display_filename = db.Column(db.String(200), nullable=False)
    original_filename = db.Column(db.String(255), nullable=True)
    file_type = db.Column(db.String(80), nullable=False, default='Arquivo')
    chip = db.Column(db.String(120), nullable=True)
    chip_position = db.Column(db.String(50), nullable=True)
    version = db.Column(db.String(80), nullable=True)
    extension = db.Column(db.String(30), nullable=True)
    mime_type = db.Column(db.String(120), nullable=True)
    file_size = db.Column(db.BigInteger, nullable=True)
    sha256 = db.Column(db.String(64), nullable=True, index=True)
    storage_provider = db.Column(db.String(40), nullable=False, default='http')
    provider_file_id = db.Column(db.String(255), nullable=True)
    provider_url = db.Column(db.Text, nullable=True)
    provider_direct_url = db.Column(db.Text, nullable=True)
    provider_metadata_json = db.Column(db.Text, nullable=True)
    source_provider = db.Column(db.String(120), nullable=True)
    source_url = db.Column(db.Text, nullable=True)
    link_status = db.Column(db.String(30), nullable=False, default='unchecked')
    last_link_check_at = db.Column(db.DateTime, nullable=True)
    last_link_http_status = db.Column(db.Integer, nullable=True)
    verification_status = db.Column(db.String(30), nullable=False, default='needs_review')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    resource = db.relationship('TechnicalResource', backref=db.backref('files', lazy=True, cascade='all, delete-orphan'))
    post = db.relationship('Post', backref=db.backref('technical_files', lazy=True))

    def public_dict(self):
        return {
            'id': self.id,
            'type': self.file_type,
            'name': self.display_filename,
            'format': self.extension or '',
            'size': format_technical_file_size(self.file_size),
            'sha256': self.sha256 or '',
            'url': url_for('download_technical_file', file_id=self.id),
        }


class ImportJob(db.Model):
    __tablename__ = 'import_jobs'

    id = db.Column(db.Integer, primary_key=True)
    job_type = db.Column(db.String(40), nullable=False)
    source = db.Column(db.String(120), nullable=False, default='admin')
    status = db.Column(db.String(30), nullable=False, default='pending')
    automation_mode = db.Column(db.String(20), nullable=False, default='semi')
    total_items = db.Column(db.Integer, nullable=False, default=0)
    processed_items = db.Column(db.Integer, nullable=False, default=0)
    success_count = db.Column(db.Integer, nullable=False, default=0)
    duplicate_count = db.Column(db.Integer, nullable=False, default=0)
    review_count = db.Column(db.Integer, nullable=False, default=0)
    error_count = db.Column(db.Integer, nullable=False, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    log_summary = db.Column(db.Text, nullable=True)

    creator = db.relationship('User', backref=db.backref('technical_import_jobs', lazy=True))


class ImportItem(db.Model):
    __tablename__ = 'import_items'

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('import_jobs.id'), nullable=False, index=True)
    source_name = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), nullable=False, default='pending_review')
    confidence = db.Column(db.Integer, nullable=False, default=0)
    raw_data_json = db.Column(db.Text, nullable=True)
    normalized_data_json = db.Column(db.Text, nullable=True)
    temp_path = db.Column(db.Text, nullable=True)
    sha256 = db.Column(db.String(64), nullable=True, index=True)
    duplicate_file_id = db.Column(db.Integer, db.ForeignKey('technical_files.id'), nullable=True)
    technical_file_id = db.Column(db.Integer, db.ForeignKey('technical_files.id'), nullable=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('technical_resources.id'), nullable=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    decision_reason = db.Column(db.Text, nullable=True)
    published_automatically = db.Column(db.Boolean, nullable=False, default=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    job = db.relationship('ImportJob', backref=db.backref('items', lazy=True, cascade='all, delete-orphan'))

    def normalized_data(self):
        try:
            return json.loads(self.normalized_data_json or '{}')
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}


class FileContribution(db.Model):
    __tablename__ = 'file_contributions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False, default='pending_review')
    original_filename = db.Column(db.String(255), nullable=False)
    temp_path = db.Column(db.Text, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=True)
    board_code = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    import_item_id = db.Column(db.Integer, db.ForeignKey('import_items.id'), nullable=True, index=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    contributor = db.relationship('User', foreign_keys=[user_id], backref=db.backref('file_contributions', lazy=True))
    import_item = db.relationship('ImportItem', foreign_keys=[import_item_id], backref=db.backref('contribution', uselist=False))


class DatasheetProviderConfig(db.Model):
    """Política persistente de um provider, sem armazenar credenciais."""
    __tablename__ = 'datasheet_provider_configs'

    id = db.Column(db.Integer, primary_key=True)
    provider_name = db.Column(db.String(80), nullable=False, unique=True, index=True)
    display_name = db.Column(db.String(120), nullable=False)
    provider_kind = db.Column(db.String(30), nullable=False, default='api')
    enabled = db.Column(db.Boolean, nullable=False, default=False)
    mode = db.Column(db.String(30), nullable=False, default='semi_automatic')
    priority = db.Column(db.Integer, nullable=False, default=100)
    api_enabled = db.Column(db.Boolean, nullable=False, default=False)
    html_discovery_enabled = db.Column(db.Boolean, nullable=False, default=False)
    search_strategy = db.Column(db.String(30), nullable=False, default='priority_fallback')
    auto_publish_threshold = db.Column(db.Float, nullable=False, default=0.95)
    max_items_per_job = db.Column(db.Integer, nullable=False, default=25)
    interval_seconds = db.Column(db.Float, nullable=False, default=1.0)
    fallback_enabled = db.Column(db.Boolean, nullable=False, default=True)
    retention_days = db.Column(db.Integer, nullable=False, default=30)
    metadata_persistence_allowed = db.Column(db.Boolean, nullable=False, default=False)
    public_republish_allowed = db.Column(db.Boolean, nullable=False, default=False)
    pdf_reference_allowed = db.Column(db.Boolean, nullable=False, default=False)
    pdf_stream_allowed = db.Column(db.Boolean, nullable=False, default=False)
    pdf_mirror_allowed = db.Column(db.Boolean, nullable=False, default=False)
    attribution_required = db.Column(db.Boolean, nullable=False, default=True)
    written_permission_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    source_policy_allows_html_discovery = db.Column(db.Boolean, nullable=False, default=False)
    permission_reference = db.Column(db.String(500), nullable=True)
    permission_notes = db.Column(db.Text, nullable=True)
    robots_allowed = db.Column(db.Boolean, nullable=False, default=False)
    robots_last_checked_at = db.Column(db.DateTime, nullable=True)
    terms_last_checked_at = db.Column(db.DateTime, nullable=True)
    terms_version_or_date = db.Column(db.String(120), nullable=True)
    requests_per_minute = db.Column(db.Integer, nullable=False, default=30)
    requests_per_hour = db.Column(db.Integer, nullable=False, default=500)
    requests_per_day = db.Column(db.Integer, nullable=False, default=5000)
    requests_per_month = db.Column(db.Integer, nullable=False, default=0)
    timeout_seconds = db.Column(db.Float, nullable=False, default=15.0)
    retry_limit = db.Column(db.Integer, nullable=False, default=2)
    provider_status = db.Column(db.String(40), nullable=False, default='not_configured')
    consecutive_failures = db.Column(db.Integer, nullable=False, default=0)
    circuit_open_until = db.Column(db.DateTime, nullable=True)
    credits_remaining = db.Column(db.Integer, nullable=True)
    last_credit_check_at = db.Column(db.DateTime, nullable=True)
    last_success_at = db.Column(db.DateTime, nullable=True)
    last_error_at = db.Column(db.DateTime, nullable=True)
    last_error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ElectronicComponent(db.Model):
    __tablename__ = 'electronic_components'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=True, index=True)
    manufacturer = db.Column(db.String(160), nullable=True, index=True)
    normalized_manufacturer = db.Column(db.String(160), nullable=False, default='', index=True)
    part_number = db.Column(db.String(160), nullable=False, index=True)
    normalized_part_number = db.Column(db.String(160), nullable=False, index=True)
    title_ptbr = db.Column(db.String(300), nullable=False)
    description_ptbr = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(120), nullable=True)
    subcategory = db.Column(db.String(120), nullable=True)
    package = db.Column(db.String(120), nullable=True)
    lifecycle_status = db.Column(db.String(80), nullable=True)
    confidence = db.Column(db.Float, nullable=False, default=0.0)
    verification_status = db.Column(db.String(30), nullable=False, default='needs_review')
    specifications_json = db.Column(db.Text, nullable=True)
    slug = db.Column(db.String(200), nullable=False, unique=True, index=True)
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    publication_mode = db.Column(db.String(20), nullable=False, default='manual')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    published_at = db.Column(db.DateTime, nullable=True)

    post = db.relationship('Post', backref=db.backref('datasheet_component', uselist=False))

    __table_args__ = (
        db.UniqueConstraint('normalized_manufacturer', 'normalized_part_number', name='uq_component_identity'),
    )

    def specifications(self):
        try:
            value = json.loads(self.specifications_json or '{}')
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}


class ComponentAlias(db.Model):
    __tablename__ = 'component_aliases'

    id = db.Column(db.Integer, primary_key=True)
    component_id = db.Column(db.Integer, db.ForeignKey('electronic_components.id'), nullable=False, index=True)
    alias = db.Column(db.String(160), nullable=False)
    normalized_alias = db.Column(db.String(160), nullable=False, unique=True, index=True)
    confirmed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    component = db.relationship('ElectronicComponent', backref=db.backref('aliases', lazy=True, cascade='all, delete-orphan'))


class ComponentSourceRecord(db.Model):
    __tablename__ = 'component_source_records'

    id = db.Column(db.Integer, primary_key=True)
    component_id = db.Column(db.Integer, db.ForeignKey('electronic_components.id'), nullable=False, index=True)
    provider = db.Column(db.String(80), nullable=False, index=True)
    external_id = db.Column(db.String(255), nullable=True)
    field_name = db.Column(db.String(120), nullable=False)
    field_value_hash = db.Column(db.String(64), nullable=False)
    license_policy = db.Column(db.String(80), nullable=False, default='metadata_only')
    first_seen_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    confidence = db.Column(db.Float, nullable=False, default=0.0)
    persisted_value_allowed = db.Column(db.Boolean, nullable=False, default=False)
    component = db.relationship('ElectronicComponent', backref=db.backref('source_records', lazy=True, cascade='all, delete-orphan'))


class DatasheetDocument(db.Model):
    __tablename__ = 'datasheet_documents'

    id = db.Column(db.Integer, primary_key=True)
    component_id = db.Column(db.Integer, db.ForeignKey('electronic_components.id'), nullable=False, index=True)
    document_title = db.Column(db.String(300), nullable=False)
    revision = db.Column(db.String(80), nullable=True)
    document_date = db.Column(db.String(40), nullable=True)
    language = db.Column(db.String(20), nullable=True)
    pages = db.Column(db.Integer, nullable=True)
    source_provider = db.Column(db.String(80), nullable=False)
    source_reference = db.Column(db.Text, nullable=True)
    distribution_policy = db.Column(db.String(50), nullable=False, default='metadata_only')
    pdf_storage_provider = db.Column(db.String(40), nullable=True)
    pdf_internal_reference = db.Column(db.Text, nullable=True)
    sha256 = db.Column(db.String(64), nullable=True, index=True)
    file_size = db.Column(db.BigInteger, nullable=True)
    verification_status = db.Column(db.String(30), nullable=False, default='needs_review')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    component = db.relationship('ElectronicComponent', backref=db.backref('documents', lazy=True, cascade='all, delete-orphan'))


class BoardComponent(db.Model):
    __tablename__ = 'board_components'

    id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey('hardware_boards.id'), nullable=False, index=True)
    component_id = db.Column(db.Integer, db.ForeignKey('electronic_components.id'), nullable=False, index=True)
    reference_designator = db.Column(db.String(50), nullable=True)
    source_resource_id = db.Column(db.Integer, db.ForeignKey('technical_resources.id'), nullable=True)
    verified = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    board = db.relationship('HardwareBoard', backref=db.backref('component_links', lazy=True, cascade='all, delete-orphan'))
    component = db.relationship('ElectronicComponent', backref=db.backref('board_links', lazy=True, cascade='all, delete-orphan'))
    __table_args__ = (db.UniqueConstraint('board_id', 'component_id', 'reference_designator', name='uq_board_component_ref'),)


class DatasheetImportQueue(db.Model):
    __tablename__ = 'datasheet_import_queue'

    id = db.Column(db.Integer, primary_key=True)
    part_number = db.Column(db.String(160), nullable=False)
    normalized_part_number = db.Column(db.String(160), nullable=False, index=True)
    manufacturer_hint = db.Column(db.String(160), nullable=True)
    source_board_id = db.Column(db.Integer, db.ForeignKey('hardware_boards.id'), nullable=True, index=True)
    source_resource_id = db.Column(db.Integer, db.ForeignKey('technical_resources.id'), nullable=True, index=True)
    priority = db.Column(db.Integer, nullable=False, default=0, index=True)
    status = db.Column(db.String(40), nullable=False, default='queued', index=True)
    requested_strategy = db.Column(db.String(30), nullable=False, default='priority_fallback')
    attempt_count = db.Column(db.Integer, nullable=False, default=0)
    best_confidence = db.Column(db.Float, nullable=False, default=0.0)
    selected_provider = db.Column(db.String(80), nullable=True)
    candidate_count = db.Column(db.Integer, nullable=False, default=0)
    result_json = db.Column(db.Text, nullable=True)
    conflict_json = db.Column(db.Text, nullable=True)
    component_id = db.Column(db.Integer, db.ForeignKey('electronic_components.id'), nullable=True, index=True)
    requested_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    admin_decision = db.Column(db.String(40), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    component = db.relationship('ElectronicComponent', foreign_keys=[component_id])
    source_board = db.relationship('HardwareBoard', foreign_keys=[source_board_id])

    def result(self):
        try:
            value = json.loads(self.result_json or '{}')
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    def conflicts(self):
        try:
            value = json.loads(self.conflict_json or '{}')
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}


class DatasheetDemand(db.Model):
    __tablename__ = 'datasheet_demands'

    id = db.Column(db.Integer, primary_key=True)
    normalized_query = db.Column(db.String(160), nullable=False, unique=True, index=True)
    display_query = db.Column(db.String(160), nullable=False)
    request_count = db.Column(db.Integer, nullable=False, default=1)
    last_requested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class DatasheetProviderEvent(db.Model):
    __tablename__ = 'datasheet_provider_events'

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(80), nullable=False, index=True)
    normalized_query = db.Column(db.String(160), nullable=False, index=True)
    status = db.Column(db.String(40), nullable=False, index=True)
    result_count = db.Column(db.Integer, nullable=False, default=0)
    selected = db.Column(db.Boolean, nullable=False, default=False)
    exact_match = db.Column(db.Boolean, nullable=False, default=False)
    confidence = db.Column(db.Float, nullable=True)
    conflict = db.Column(db.Boolean, nullable=False, default=False)
    duration_ms = db.Column(db.Integer, nullable=False, default=0)
    message = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

# Modelo de Favoritos
class Favorite(db.Model):
    __tablename__ = 'favorites'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    position = db.Column(db.Integer, default=0)

    # Relacionamentos
    user = db.relationship('User', backref=db.backref('favorites', lazy=True, cascade="all, delete"))
    post = db.relationship('Post', backref=db.backref('favorited_by', lazy=True, cascade="all, delete"))

    # Constraint para evitar duplicatas
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_favorite'),)

    def __repr__(self):
        return f"Favorite(user_id={self.user_id}, post_id={self.post_id})"

# Modelo de Transações de Pagamento
class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Gateway de pagamento ('stripe' ou 'abacatepay')
    payment_gateway = db.Column(db.String(20), default='stripe', nullable=False)

    # Dados do Stripe
    stripe_session_id = db.Column(db.String(255), unique=True, nullable=True)  # checkout.session.id
    stripe_customer_id = db.Column(db.String(255), nullable=True)  # customer ID do Stripe
    stripe_subscription_id = db.Column(db.String(255), nullable=True)  # subscription ID do Stripe
    stripe_payment_intent_id = db.Column(db.String(255), nullable=True)  # payment_intent ID

    # Dados do Abacate Pay
    abacatepay_billing_id = db.Column(db.String(255), unique=True, nullable=True)  # ID da cobrança
    abacatepay_charge_id = db.Column(db.String(255), unique=True, nullable=True)  # ID real do Checkout Transparente na AbacatePay
    abacatepay_payment_url = db.Column(db.Text, nullable=True)  # URL de pagamento
    abacatepay_qr_code = db.Column(db.Text, nullable=True)  # QR Code PIX em base64
    abacatepay_pix_code = db.Column(db.Text, nullable=True)  # Código PIX copia-e-cola

    # Dados da transação
    plan_type = db.Column(db.String(20), nullable=False)  # 'premium' ou 'vip'
    amount = db.Column(db.Integer, nullable=False)  # Valor em centavos
    currency = db.Column(db.String(3), default='brl')  # Moeda
    status = db.Column(db.String(20), default='pending')  # 'pending', 'completed', 'failed', 'refunded'

    # Datas
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)  # Quando o pagamento foi confirmado

    # Relacionamento
    user = db.relationship('User', backref=db.backref('transactions', lazy=True, cascade="all, delete"))

    def __repr__(self):
        return f"Transaction(user_id={self.user_id}, plan={self.plan_type}, gateway={self.payment_gateway}, status={self.status})"


class PaymentWebhookEvent(db.Model):
    """Registro mínimo para garantir processamento idempotente de webhooks."""
    __tablename__ = 'payment_webhook_events'
    __table_args__ = (
        db.UniqueConstraint('provider', 'external_event_id', name='uq_webhook_provider_event'),
    )

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(30), nullable=False)
    external_event_id = db.Column(db.String(255), nullable=False)
    event_type = db.Column(db.String(120), nullable=True)
    received_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(30), nullable=False, default='processing')
    payload_hash = db.Column(db.String(64), nullable=False)
    error_message = db.Column(db.String(500), nullable=True)


class ContentRequest(db.Model):
    """Sugestões gerais e buscas prioritárias do plano VIP."""
    __tablename__ = 'content_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    request_type = db.Column(db.String(30), nullable=False, default='suggestion')
    requester_plan = db.Column(db.String(20), nullable=False, default='guest')
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=True)
    board_code = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(30), nullable=False, default='pending')
    priority = db.Column(db.Integer, nullable=False, default=0)
    admin_notes = db.Column(db.Text, nullable=True)
    requester_name = db.Column(db.String(120), nullable=True)
    requester_email = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('content_requests', lazy=True))


def begin_webhook_event(provider: str, external_event_id: str, event_type: str, raw_body: bytes):
    """Reserva um evento antes de executar efeitos financeiros.

    A restrição única no banco resolve inclusive entregas concorrentes. Eventos
    que falharam podem ser tentados novamente; processados ou em andamento são
    reconhecidos como duplicados.
    """
    provider = (provider or '').strip().lower()[:30]
    external_event_id = (external_event_id or '').strip()[:255]
    if not provider or not external_event_id:
        raise ValueError('Webhook sem identificador idempotente.')

    event = PaymentWebhookEvent(
        provider=provider,
        external_event_id=external_event_id,
        event_type=(event_type or '')[:120] or None,
        payload_hash=hashlib.sha256(raw_body).hexdigest(),
        status='processing',
    )
    db.session.add(event)
    try:
        db.session.commit()
        return event.id, False
    except IntegrityError:
        db.session.rollback()
        existing = PaymentWebhookEvent.query.filter_by(
            provider=provider,
            external_event_id=external_event_id,
        ).first()
        if existing and existing.status == 'failed':
            existing.status = 'processing'
            existing.error_message = None
            existing.payload_hash = hashlib.sha256(raw_body).hexdigest()
            existing.received_at = datetime.utcnow()
            db.session.commit()
            return existing.id, False
        return existing.id if existing else None, True


def finish_webhook_event(event_id: int | None, status: str, error: Exception | str | None = None):
    if not event_id:
        return
    event = db.session.get(PaymentWebhookEvent, event_id)
    if not event:
        return
    event.status = status
    event.processed_at = datetime.utcnow()
    event.error_message = str(error)[:500] if error else None
    db.session.commit()

# Adicionar o modelo Comment depois de definir User
class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)

    # Campos para usuários não logados
    author_name = db.Column(db.String(100), nullable=True)
    author_email = db.Column(db.String(120), nullable=True)

    # Status de aprovação
    is_approved = db.Column(db.Boolean, default=False)
    moderation_status = db.Column(db.String(20), nullable=False, default='pending', index=True)

    # Campos para edição
    is_edited = db.Column(db.Boolean, default=False)
    date_edited = db.Column(db.DateTime, nullable=True)

    # Adicionar chave estrangeira para User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Adicionar chave estrangeira para Post
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)

    # Comentário pai para respostas encadeadas
    parent_id = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=True)

    # Relacionamento com User
    user = db.relationship('User', backref='comments')

    # Relacionamento com Post
    post = db.relationship('Post', backref='comments')

    # Relacionamento para respostas
    parent = db.relationship(
        'Comment',
        remote_side=[id],
        backref=db.backref('replies', lazy=True, cascade="all, delete-orphan")
    )

    @property
    def status(self):
        """Retorna o status persistido, preservando dados legados."""
        normalized = (self.moderation_status or '').strip().lower()
        # Registros antigos só possuíam ``is_approved``. Priorizar esse sinal
        # evita que um comentário aprovado antes da migração apareça como
        # pendente apenas porque a nova coluna recebeu o valor padrão.
        if self.is_approved:
            return 'approved'
        if normalized == 'rejected':
            return 'rejected'
        return 'pending'

    @status.setter
    def status(self, value):
        normalized = str(value or '').strip().lower()
        if normalized not in {'pending', 'approved', 'rejected'}:
            normalized = 'pending'
        self.moderation_status = normalized
        self.is_approved = normalized == 'approved'

    @property
    def created_at(self):
        """Alias para date_posted para compatibilidade com template"""
        return self.date_posted

    def __repr__(self):
        return f"Comment('{self.content}', '{self.date_posted}')"

# Configuração do LoginManager
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # type: ignore
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'info'

# Handler para requisições não autorizadas (incluindo AJAX)
@login_manager.unauthorized_handler
def unauthorized():
    # Verificar se é uma requisição AJAX
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': False, 'message': 'Sessão expirada. Faça login novamente.'}), 401
    # Requisição normal - redirecionar para login
    flash('Por favor, faça login para acessar esta página.', 'info')
    return redirect(url_for('login', next=request.url))

# Função para carregar o usuário
@app.before_request
def check_subscription_expiration():
    if current_user.is_authenticated and current_user.plan != 'free':
        if current_user.subscription_end_date and current_user.subscription_end_date < datetime.utcnow():
            current_user.plan = 'free'
            current_user.subscription_end_date = None
            db.session.commit()
            flash('Sua assinatura expirou. Você voltou para o plano Grátis.', 'info')

@login_manager.user_loader
def load_user(user_id):
    # Usar a sintaxe recomendada pelo SQLAlchemy 2.0
    return db.session.get(User, int(user_id))
    # Antiga forma: return User.query.get(int(user_id))

# Função auxiliar para obter estatísticas da sidebar
def get_admin_sidebar_stats():
    """
    Retorna as estatísticas reais para exibir na sidebar do painel administrativo
    """
    debug_log("Calculando stats da sidebar...")

    post_count = Post.query.filter_by(is_active=True).count()
    category_count = Category.query.filter_by(is_active=True).count()
    comment_count = Comment.query.count()
    user_count = User.query.count()
    subscriber_count = Subscriber.query.count()

    debug_log(f"Posts: {post_count}, Categorias: {category_count}, Comentários: {comment_count}")
    debug_log(f"Usuários: {user_count}, Inscritos: {subscriber_count}")

    return {
        'post_count': post_count,
        'category_count': category_count,
        'comment_count': comment_count,
        'unread_comments': comment_count,
        'user_count': user_count,
        'subscriber_count': subscriber_count
    }

# Decorador para rotas que requerem acesso de administrador
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Você não tem permissão para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorador para rotas que requerem acesso de editor OU administrador
def editor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('admin', 'editor'):
            flash('Você não tem permissão para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Configurações do site dinâmicas
class SiteConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    value_type = db.Column(db.String(20), default='string')  # string, int, float, bool, json
    description = db.Column(db.String(200), nullable=True)
    is_public = db.Column(db.Boolean, default=True)  # Se pode ser exibido no frontend

    @staticmethod
    def _converted_value(config, default=None):
        """Converte o valor persistido sem executar uma nova consulta."""
        value = config.value
        if config.value_type == 'int':
            return int(value) if value else default
        elif config.value_type == 'float':
            return float(value) if value else default
        elif config.value_type == 'bool':
            return value.lower() in ('true', '1', 'yes', 'y', 't') if value else default
        elif config.value_type == 'json':
            try:
                return json.loads(value) if value else default
            except (json.JSONDecodeError, TypeError, ValueError):
                return default
        # Default: string
        return value if value is not None else default

    @staticmethod
    def get_value(key, default=None):
        """Obtém o valor de uma configuração, convertido para o tipo apropriado"""
        config = SiteConfig.query.filter_by(key=key).first()
        if not config:
            return default
        return SiteConfig._converted_value(config, default)

    @staticmethod
    def get_config():
        """Retorna um dicionário com todas as configurações públicas do site"""
        try:
            configs = SiteConfig.query.filter_by(is_public=True).all()
            config_dict = {}
            for config in configs:
                config_dict[config.key] = SiteConfig._converted_value(config)

            # Configurações padrão caso não existam no banco
            defaults = {
                'site_name': 'Mundo da Informática',
                'site_description': 'Biblioteca técnica de BIOS, EC, BoardView, esquemas e recursos para profissionais de manutenção.',
                'footer_text': 'Mundo da Informática - Todos os direitos reservados',
                'footer_description': 'Recursos técnicos organizados por modelo e placa para profissionais de manutenção.',
                'home_hero_title': 'Encontre o arquivo certo para o reparo!',
                'home_hero_subtitle': 'BIOS, EC, BoardView, esquemas e recursos técnicos organizados por modelo e placa.',
                'enable_dark_mode': True,
                'primary_color': '#3a86ff',
                'secondary_color': '#8338ec',
                'google_analytics': '',
                'maintenance_mode': False,
                'contact_email': DEFAULT_SUPPORT_EMAIL,
                'contact_phone': '(21) 97879-4705',
                'contact_address': 'Internet - Brasil',
                'social_facebook': '#',
                'social_twitter': '#',
                'social_instagram': '#',
                'social_youtube': '#',
                'phone': '(21) 97879-4705',
                'whatsapp': '5521978794705',
                'address': 'Internet - Brasil',
                'social_links': {
                    'facebook': '',
                    'instagram': '',
                    'twitter': '',
                    'youtube': 'https://www.youtube.com/@_RDTech'
                },
                'download_file_types': [dict(item) for item in DEFAULT_DOWNLOAD_FILE_TYPES],
                'plan_enabled_free': True,
                'plan_enabled_premium': True,
                'plan_enabled_vip': True,
                'plan_name_free': 'Grátis',
                'plan_name_premium': 'Premium',
                'plan_name_vip': 'VIP',
                'plan_price_premium': 29.90,
                'plan_price_vip': 49.90,
                'plan_card_enabled_premium': True,
                'plan_card_enabled_vip': True,
                'plan_pix_enabled_premium': True,
                'plan_pix_enabled_vip': True,
                'technical_import_enabled': True,
                'technical_automation_mode': 'semi',
                'technical_automation_percentage': 100,
                'technical_auto_publish_threshold': 85,
                'technical_require_storage_ready': True,
            }

            # Mesclar com valores padrão
            for key, default_value in defaults.items():
                if key not in config_dict:
                    config_dict[key] = default_value

            if not config_dict.get('contact_email') or config_dict.get('contact_email') == 'contato@mundodainformatica.com':
                config_dict['contact_email'] = DEFAULT_SUPPORT_EMAIL

            if not config_dict.get('contact_phone'):
                config_dict['contact_phone'] = '(21) 97879-4705'

            social_links = config_dict.get('social_links')
            if not isinstance(social_links, dict):
                social_links = {}
            config_dict['social_links'] = {
                'facebook': social_links.get('facebook', ''),
                'instagram': social_links.get('instagram', ''),
                'twitter': social_links.get('twitter', ''),
                'youtube': social_links.get('youtube', 'https://www.youtube.com/@_RDTech')
            }

            return config_dict

        except Exception:
            # Em caso de erro, retorna configurações básicas
            return {
                'site_name': 'Mundo da Informática',
                'site_description': 'Biblioteca técnica de BIOS, EC, BoardView, esquemas e recursos para profissionais de manutenção.',
                'footer_text': 'Mundo da Informática - Todos os direitos reservados',
                'footer_description': 'Recursos técnicos organizados por modelo e placa para profissionais de manutenção.',
                'home_hero_title': 'Encontre o arquivo certo para o reparo!',
                'home_hero_subtitle': 'BIOS, EC, BoardView, esquemas e recursos técnicos organizados por modelo e placa.',
                'enable_dark_mode': True,
                'primary_color': '#3a86ff',
                'secondary_color': '#8338ec',
                'google_analytics': '',
                'maintenance_mode': False,
                'contact_email': DEFAULT_SUPPORT_EMAIL,
                'contact_phone': '(21) 97879-4705',
                'contact_address': 'Internet - Brasil',
                'social_facebook': '#',
                'social_twitter': '#',
                'social_instagram': '#',
                'social_youtube': '#',
                'phone': '(21) 97879-4705',
                'whatsapp': '5521978794705',
                'address': 'Internet - Brasil',
                'social_links': {
                    'facebook': '',
                    'instagram': '',
                    'twitter': '',
                    'youtube': 'https://www.youtube.com/@_RDTech'
                },
                'download_file_types': [dict(item) for item in DEFAULT_DOWNLOAD_FILE_TYPES],
                'plan_enabled_free': True,
                'plan_enabled_premium': True,
                'plan_enabled_vip': True,
                'plan_name_free': 'Grátis',
                'plan_name_premium': 'Premium',
                'plan_name_vip': 'VIP',
                'plan_price_premium': 29.90,
                'plan_price_vip': 49.90,
                'plan_card_enabled_premium': True,
                'plan_card_enabled_vip': True,
                'plan_pix_enabled_premium': True,
                'plan_pix_enabled_vip': True,
                'technical_import_enabled': True,
                'technical_automation_mode': 'semi',
                'technical_automation_percentage': 100,
                'technical_auto_publish_threshold': 85,
                'technical_require_storage_ready': True,
            }

    @staticmethod
    def set_value(key, value, value_type='string', description=None, is_public=True):
        """Define o valor de uma configuração"""
        # Converter o valor para string conforme o tipo
        if value_type == 'json' and not isinstance(value, str):
            value = json.dumps(value)
        elif value is not None and not isinstance(value, str):
            value = str(value)

        config = SiteConfig.query.filter_by(key=key).first()
        if config:
            config.value = value
            if description:
                config.description = description
            if value_type:
                config.value_type = value_type
            config.is_public = is_public
        else:
            config = SiteConfig(
                key=key, value=value, value_type=value_type,
                description=description, is_public=is_public
            )
            db.session.add(config)

        db.session.commit()
        return config


TECHNICAL_AUTOMATION_KEYS = {
    'technical_import_enabled',
    'technical_automation_mode',
    'technical_automation_percentage',
    'technical_auto_publish_threshold',
    'technical_require_storage_ready',
}


def get_technical_automation_settings():
    mode = str(SiteConfig.get_value('technical_automation_mode', 'semi') or 'semi').lower()
    if mode not in {'off', 'semi', 'full'}:
        mode = 'semi'
    enabled = bool(SiteConfig.get_value('technical_import_enabled', True))
    return {
        'feature_enabled': bool(app.config.get('TECHNICAL_IMPORT_ENABLED')),
        'configured_enabled': enabled,
        'enabled': bool(app.config.get('TECHNICAL_IMPORT_ENABLED')) and enabled and mode != 'off',
        'mode': mode,
        'percentage': max(0, min(100, coerce_int(SiteConfig.get_value('technical_automation_percentage', 100), 100))),
        'threshold': max(0, min(100, coerce_int(SiteConfig.get_value('technical_auto_publish_threshold', 85), 85))),
        'require_storage_ready': bool(SiteConfig.get_value('technical_require_storage_ready', True)),
    }


def ensure_default_content_sources():
    defaults = (
        ('Admin', 'manual', 'C', False, True, True, True, False),
        ('Contribuição de usuário', 'contribution', 'D', False, True, False, False, True),
        ('Dell', 'official', 'A', True, True, False, False, True),
        ('HP', 'official', 'A', True, True, False, False, True),
        ('Lenovo', 'official', 'A', True, True, False, False, True),
        ('Feed licenciado', 'licensed', 'B', False, True, False, False, True),
    )
    removed = ContentSource.query.filter_by(provider_type='api').delete(synchronize_session=False)
    changed = bool(removed)
    for name, provider_type, trust, auto, metadata, distribution, mirror, attribution in defaults:
        if ContentSource.query.filter_by(name=name).first():
            continue
        db.session.add(ContentSource(
            name=name,
            provider_type=provider_type,
            trust_level=trust,
            auto_publish=auto,
            metadata_allowed=metadata,
            distribution_allowed=distribution,
            file_mirroring_allowed=mirror,
            attribution_required=attribution,
            enabled=True,
        ))
        changed = True
    if changed:
        db.session.commit()


DATASHEET_SETTING_KEYS = {
    'datasheet_engine_enabled',
    'datasheet_auto_publish_enabled',
    'datasheet_automation_paused',
    'datasheet_search_strategy',
    'datasheet_max_providers',
}

DATASHEET_PROVIDER_ENV_FLAGS = {
    'source_parts': 'ENABLE_SOURCE_PARTS',
    'alldatasheet_api': 'ENABLE_ALLDATASHEET_API',
    'alldatasheet_html': 'ENABLE_ALLDATASHEET_HTML',
    'datasheets_com_api': 'ENABLE_DATASHEETS_COM_API',
    'datasheets_com_html': 'ENABLE_DATASHEETS_COM_HTML',
    'manufacturer_official': 'ENABLE_DATASHEET_ENGINE',
    'licensed_provider': 'ENABLE_DATASHEET_ENGINE',
}

DATASHEET_CREDENTIAL_ENV = {
    'source_parts': ('SOURCE_PARTS_API_KEY', 'SOURCE_PARTS_USER_AGENT'),
    'alldatasheet_api': (
        'ALLDATASHEET_API_KEY', 'ALLDATASHEET_API_URL',
        'ALLDATASHEET_API_AUTH_HEADER', 'ALLDATASHEET_API_QUERY_PARAMETER',
    ),
    'alldatasheet_html': ('ALLDATASHEET_HTML_SEARCH_URL', 'DATASHEET_DISCOVERY_USER_AGENT'),
    'datasheets_com_api': ('DATASHEETS_COM_API_KEY',),
    'datasheets_com_html': ('DATASHEETS_COM_HTML_SEARCH_URL', 'DATASHEET_DISCOVERY_USER_AGENT'),
    'manufacturer_official': ('MANUFACTURER_DATASHEET_FEED_URL',),
    'licensed_provider': ('LICENSED_DATASHEET_FEED_URL',),
}


def get_datasheet_settings():
    strategy = str(SiteConfig.get_value('datasheet_search_strategy', 'priority_fallback') or 'priority_fallback')
    if strategy not in {'priority_fallback', 'parallel_compare', 'maximum_precision'}:
        strategy = 'priority_fallback'
    environment_kill_switch = bool(app.config.get('DISABLE_ALL_DATASHEET_AUTOMATION'))
    configured_paused = bool(SiteConfig.get_value('datasheet_automation_paused', False))
    feature_enabled = bool(app.config.get('ENABLE_DATASHEET_ENGINE'))
    configured_enabled = bool(SiteConfig.get_value('datasheet_engine_enabled', True))
    auto_publish_configured = bool(SiteConfig.get_value('datasheet_auto_publish_enabled', False))
    if not configured_enabled:
        mode = 'off'
    elif auto_publish_configured:
        mode = 'full'
    else:
        mode = 'semi'
    return {
        'feature_enabled': feature_enabled,
        'configured_enabled': configured_enabled,
        'auto_publish_configured': auto_publish_configured,
        'auto_publish_enabled': bool(
            feature_enabled
            and configured_enabled
            and auto_publish_configured
            and not environment_kill_switch
            and not configured_paused
        ),
        'mode': mode,
        'paused': environment_kill_switch or configured_paused,
        'environment_kill_switch': environment_kill_switch,
        'strategy': strategy,
        'max_providers': max(1, min(10, coerce_int(SiteConfig.get_value('datasheet_max_providers', 2), 2))),
    }


def ensure_default_datasheet_providers():
    """Cria providers conservadores; nunca ativa HTML nem direitos por suposição."""
    defaults = (
        ('source_parts', 'Source Parts', 'api', 1, True, True, 0.95, 60, 1000, 5000, 0),
        ('manufacturer_official', 'Fabricantes oficiais', 'official', 2, True, True, 0.97, 30, 500, 2000, 0),
        ('alldatasheet_api', 'AllDatasheet API', 'api', 3, False, True, 0.97, 20, 200, 1000, 0),
        ('alldatasheet_html', 'AllDatasheet HTML Discovery', 'html', 4, False, False, 0.98, 6, 60, 200, 0),
        ('datasheets_com_api', 'Datasheets.com API', 'api', 5, False, True, 0.95, 60, 500, 5000, 5000),
        ('datasheets_com_html', 'Datasheets.com HTML Discovery', 'html', 6, False, False, 0.98, 6, 60, 200, 0),
        ('licensed_provider', 'Provider licenciado', 'licensed', 7, False, True, 0.95, 30, 500, 2000, 0),
    )
    changed = False
    for name, display, kind, priority, enabled, api_enabled, threshold, per_minute, per_hour, per_day, per_month in defaults:
        if DatasheetProviderConfig.query.filter_by(provider_name=name).first():
            continue
        db.session.add(DatasheetProviderConfig(
            provider_name=name,
            display_name=display,
            provider_kind=kind,
            enabled=enabled,
            mode='semi_automatic',
            priority=priority,
            api_enabled=api_enabled,
            html_discovery_enabled=False,
            auto_publish_threshold=threshold,
            metadata_persistence_allowed=False,
            public_republish_allowed=False,
            pdf_reference_allowed=False,
            pdf_stream_allowed=False,
            pdf_mirror_allowed=False,
            attribution_required=True,
            requests_per_minute=per_minute,
            requests_per_hour=per_hour,
            requests_per_day=per_day,
            requests_per_month=per_month,
            provider_status='not_configured',
        ))
        changed = True
    if changed:
        db.session.commit()


def datasheet_provider_credentials_status(config):
    required = DATASHEET_CREDENTIAL_ENV.get(config.provider_name, ())
    configured = all((os.environ.get(key) or '').strip() for key in required)
    # Feeds normalizados podem ser públicos e, portanto, não exigem token.
    return {
        'configured': configured,
        'required_env': list(required),
    }


def _provider_environment_enabled(config):
    flag = DATASHEET_PROVIDER_ENV_FLAGS.get(config.provider_name, 'ENABLE_DATASHEET_ENGINE')
    return bool(app.config.get(flag))


def build_configured_datasheet_providers(configs=None):
    from technical_content.datasheets.providers import (
        AllDatasheetApiProvider,
        AllDatasheetHtmlProvider,
        DatasheetsComApiProvider,
        DatasheetsComHtmlProvider,
        LicensedDatasheetProvider,
        ManufacturerProvider,
        SourcePartsProvider,
    )
    from technical_content.datasheets.services.resolver import ConfiguredProvider

    configs = configs or DatasheetProviderConfig.query.order_by(DatasheetProviderConfig.priority.asc()).all()
    result = []
    for config in configs:
        if not _provider_environment_enabled(config):
            continue
        common = {
            'timeout': config.timeout_seconds,
            'retry_limit': config.retry_limit,
            'requests_per_minute': config.requests_per_minute,
            'requests_per_hour': config.requests_per_hour,
            'requests_per_day': config.requests_per_day,
            'requests_per_month': config.requests_per_month,
            'minimum_interval': config.interval_seconds,
        }
        if config.provider_name == 'source_parts':
            provider = SourcePartsProvider(
                os.environ.get('SOURCE_PARTS_API_KEY', ''),
                os.environ.get('SOURCE_PARTS_USER_AGENT', ''),
                base_url=os.environ.get('SOURCE_PARTS_API_URL', 'https://api.source.parts/v1'),
                **common,
            )
        elif config.provider_name == 'alldatasheet_api':
            provider = AllDatasheetApiProvider(
                os.environ.get('ALLDATASHEET_API_KEY', ''),
                os.environ.get('ALLDATASHEET_API_URL', ''),
                os.environ.get('ALLDATASHEET_API_AUTH_HEADER', ''),
                query_parameter=os.environ.get('ALLDATASHEET_API_QUERY_PARAMETER', ''),
                **common,
            )
        elif config.provider_name == 'alldatasheet_html':
            provider = AllDatasheetHtmlProvider(
                os.environ.get('ALLDATASHEET_HTML_SEARCH_URL', ''),
                os.environ.get('DATASHEET_DISCOVERY_USER_AGENT', ''),
                robots_confirmed=config.robots_allowed,
                **common,
            )
        elif config.provider_name == 'datasheets_com_api':
            provider = DatasheetsComApiProvider(
                os.environ.get('DATASHEETS_COM_API_KEY', ''),
                endpoint=os.environ.get('DATASHEETS_COM_API_URL', 'https://www.datasheets.com/api/v1/search'),
                **common,
            )
        elif config.provider_name == 'datasheets_com_html':
            provider = DatasheetsComHtmlProvider(
                os.environ.get('DATASHEETS_COM_HTML_SEARCH_URL', ''),
                os.environ.get('DATASHEET_DISCOVERY_USER_AGENT', ''),
                robots_confirmed=config.robots_allowed,
                **common,
            )
        elif config.provider_name == 'manufacturer_official':
            provider = ManufacturerProvider(
                os.environ.get('MANUFACTURER_DATASHEET_FEED_URL', ''),
                os.environ.get('MANUFACTURER_DATASHEET_FEED_TOKEN', ''),
                provider_name='manufacturer_official',
                **common,
            )
        else:
            provider = LicensedDatasheetProvider(
                os.environ.get('LICENSED_DATASHEET_FEED_URL', ''),
                os.environ.get('LICENSED_DATASHEET_FEED_TOKEN', ''),
                provider_name=config.provider_name,
                **common,
            )
        result.append(ConfiguredProvider(provider=provider, config=config))
    return result


def find_component_by_identity(manufacturer, part_number):
    normalized_part = normalize_component_part_number(part_number)
    normalized_manufacturer = normalize_component_manufacturer(manufacturer).casefold()
    query = ElectronicComponent.query.filter_by(normalized_part_number=normalized_part)
    if normalized_manufacturer:
        match = query.filter(db.func.lower(ElectronicComponent.normalized_manufacturer) == normalized_manufacturer).first()
        if match:
            return match
    alias = ComponentAlias.query.filter_by(normalized_alias=normalized_part).first()
    return alias.component if alias else query.first()


def enqueue_datasheet(part_number, manufacturer_hint=None, *, priority=0, strategy=None, requested_by=None, board_id=None, resource_id=None):
    normalized = normalize_component_part_number(part_number)
    if not normalized:
        raise ValueError('Informe um part number válido.')
    existing = DatasheetImportQueue.query.filter(
        DatasheetImportQueue.normalized_part_number == normalized,
        DatasheetImportQueue.status.in_(['queued', 'processing', 'found', 'needs_review', 'approved']),
    ).first()
    if existing:
        existing.priority = max(existing.priority, int(priority or 0))
        db.session.commit()
        return existing, False
    settings = get_datasheet_settings()
    queue_item = DatasheetImportQueue(
        part_number=str(part_number).strip()[:160],
        normalized_part_number=normalized,
        manufacturer_hint=sanitize_input(str(manufacturer_hint or ''))[:160] or None,
        priority=max(0, min(10000, int(priority or 0))),
        requested_strategy=strategy if strategy in {'priority_fallback', 'parallel_compare', 'maximum_precision'} else settings['strategy'],
        requested_by=requested_by,
        source_board_id=board_id,
        source_resource_id=resource_id,
        status='queued',
    )
    db.session.add(queue_item)
    db.session.commit()
    return queue_item, True


def _record_datasheet_resolution(resolution, provider_configs):
    config_map = {config.provider_name: config for config in provider_configs}
    selected_provider = resolution.selected.provider if resolution.selected else None
    for trace in resolution.traces:
        selected_candidate = next(
            (candidate for candidate in resolution.candidates if candidate.provider == trace.provider and candidate.provider == selected_provider),
            None,
        )
        db.session.add(DatasheetProviderEvent(
            provider=trace.provider,
            normalized_query=resolution.normalized_query,
            status=trace.status,
            result_count=trace.result_count,
            selected=bool(selected_candidate),
            exact_match=bool(selected_candidate and selected_candidate.exact_match),
            confidence=selected_candidate.confidence if selected_candidate else None,
            conflict=bool(resolution.conflicts),
            duration_ms=trace.duration_ms,
            message=sanitize_input(str(trace.message or ''))[:500] or None,
        ))
        config = config_map.get(trace.provider)
        if not config:
            continue
        if trace.status in {'success', 'not_found'}:
            config.provider_status = 'online'
            config.consecutive_failures = 0
            config.circuit_open_until = None
            config.last_success_at = datetime.utcnow()
            config.last_error_message = None
            if config.provider_kind == 'html':
                config.robots_last_checked_at = datetime.utcnow()
        elif trace.status not in {'disabled'}:
            config.provider_status = trace.status
            config.consecutive_failures = (config.consecutive_failures or 0) + 1
            config.last_error_at = datetime.utcnow()
            config.last_error_message = sanitize_input(str(trace.message or trace.status))[:2000]
            if config.consecutive_failures >= 3:
                config.provider_status = 'temporarily_unhealthy'
                config.circuit_open_until = datetime.utcnow() + timedelta(minutes=15)


def process_datasheet_queue_item(queue_item, *, configured_providers=None, provider_configs=None):
    from technical_content.datasheets.services.resolver import DatasheetResolver

    settings = get_datasheet_settings()
    if not settings['feature_enabled'] or not settings['configured_enabled']:
        queue_item.status = 'blocked_by_policy'
        queue_item.error_message = 'O motor de datasheets está desativado.'
        queue_item.finished_at = datetime.utcnow()
        db.session.commit()
        return queue_item
    if settings['paused']:
        queue_item.status = 'blocked_by_policy'
        queue_item.error_message = 'A automação de datasheets está pausada pelo kill switch.'
        queue_item.finished_at = datetime.utcnow()
        db.session.commit()
        return queue_item

    ensure_default_datasheet_providers()
    configs = (
        provider_configs
        if provider_configs is not None
        else DatasheetProviderConfig.query.order_by(DatasheetProviderConfig.priority.asc()).all()
    )
    configured = (
        configured_providers
        if configured_providers is not None
        else build_configured_datasheet_providers(configs)
    )
    if not configured:
        queue_item.status = 'blocked_by_policy'
        queue_item.error_message = 'Nenhum provider de datasheet está ativo no ambiente e no painel.'
        queue_item.finished_at = datetime.utcnow()
        db.session.commit()
        return queue_item
    queue_item.status = 'processing'
    queue_item.started_at = datetime.utcnow()
    queue_item.attempt_count = (queue_item.attempt_count or 0) + 1
    queue_item.error_message = None
    db.session.commit()

    resolver = DatasheetResolver(configured, global_disabled=False)
    max_providers = settings['max_providers'] if queue_item.requested_strategy == 'parallel_compare' else None
    resolution = resolver.resolve(
        queue_item.part_number,
        strategy=queue_item.requested_strategy,
        max_providers=max_providers,
    )
    _record_datasheet_resolution(resolution, configs)
    queue_item.candidate_count = len(resolution.candidates)
    queue_item.best_confidence = resolution.confidence
    queue_item.conflict_json = json.dumps(resolution.conflicts, ensure_ascii=False)
    queue_item.finished_at = datetime.utcnow()

    if not resolution.selected:
        statuses = {trace.status for trace in resolution.traces}
        if statuses and statuses <= {'disabled', 'blocked_by_policy', 'not_configured', 'temporarily_unhealthy'}:
            queue_item.status = 'blocked_by_policy'
        elif statuses & {'failed', 'rate_limited'}:
            queue_item.status = 'failed'
        else:
            queue_item.status = 'not_found'
        queue_item.error_message = '; '.join(
            f'{trace.provider}: {trace.message or trace.status}' for trace in resolution.traces if trace.status not in {'success', 'not_found'}
        )[:4000] or None
        db.session.commit()
        return queue_item

    config_map = {config.provider_name: config for config in configs}
    selected_config = config_map.get(resolution.selected.provider)
    if not selected_config:
        queue_item.status = 'failed'
        queue_item.error_message = 'A configuração da fonte selecionada não foi encontrada.'
        db.session.commit()
        return queue_item

    persistence = persistence_policy(selected_config)
    candidate_summaries = []
    for candidate in resolution.candidates:
        candidate_config = config_map.get(candidate.provider)
        include_values = bool(candidate_config and persistence_policy(candidate_config).allowed)
        candidate_summaries.append(candidate.public_summary(include_values=include_values))

    if not persistence.allowed:
        queue_item.status = 'blocked_by_policy'
        queue_item.selected_provider = resolution.selected.provider
        queue_item.result_json = json.dumps({
            'query': resolution.query,
            'confidence': resolution.confidence,
            'provider_candidates': candidate_summaries,
            'policy_message': persistence.reason,
        }, ensure_ascii=False)
        queue_item.error_message = persistence.reason
        db.session.commit()
        return queue_item

    selected = resolution.selected.public_summary(include_values=True)
    selected['specifications'] = translate_specifications(resolution.selected.specifications)
    queue_item.selected_provider = resolution.selected.provider
    queue_item.result_json = json.dumps({
        'query': resolution.query,
        'confidence': resolution.confidence,
        'selected': selected,
        'provider_candidates': candidate_summaries,
        'traces': [
            {
                'provider': trace.provider,
                'status': trace.status,
                'result_count': trace.result_count,
                'duration_ms': trace.duration_ms,
                'message': trace.message,
            }
            for trace in resolution.traces
        ],
    }, ensure_ascii=False)

    duplicate = find_component_by_identity(resolution.selected.manufacturer, resolution.selected.part_number)
    if duplicate:
        queue_item.component_id = duplicate.id
        queue_item.status = 'duplicate'
        queue_item.admin_decision = 'duplicate_detected'
        db.session.commit()
        return queue_item

    decision = publication_policy(
        selected_config,
        confidence=resolution.confidence,
        has_conflicts=resolution.has_conflicts,
        duplicate=False,
        required_fields_present=bool(resolution.selected.part_number and resolution.selected.manufacturer),
        global_auto_publish=settings['auto_publish_enabled'],
    )
    queue_item.status = decision.status if decision.status in {
        'needs_review', 'blocked_by_policy', 'duplicate', 'approved'
    } else 'needs_review'
    queue_item.error_message = None if queue_item.status == 'needs_review' else decision.reason
    db.session.commit()
    if decision.allowed:
        materialize_datasheet_component(queue_item, reviewer_id=None, publish=True, automatic=True)
    return queue_item


def _unique_component_slug(part_number, manufacturer=None):
    base = datasheet_safe_slug(part_number)
    candidate = base
    counter = 2
    while ElectronicComponent.query.filter_by(slug=candidate).first():
        suffix = datasheet_safe_slug(manufacturer) if manufacturer and counter == 2 else str(counter)
        candidate = f'{base}-{suffix}'[:200]
        counter += 1
    return candidate


def _ensure_datasheet_post(component, selected, *, author_id, publish, automatic=False):
    """Mantém o componente e o post público de datasheet como uma única publicação."""
    post = component.post
    expected_slug = f'datasheet-{component.slug}'[:250]
    if post is None:
        candidate = Post.query.filter_by(slug=expected_slug).first()
        try:
            candidate_metadata = json.loads(candidate.custom_metadata or '{}') if candidate else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            candidate_metadata = {}
        if not isinstance(candidate_metadata, dict):
            candidate_metadata = {}
        if candidate and candidate_metadata.get('electronic_component_id') == component.id:
            post = candidate

    category = Category.query.filter(db.func.lower(Category.name) == 'datasheet').first()
    if category is None:
        category = Category(
            name='Datasheet',
            slug='datasheet',
            description='Datasheets e informações técnicas de componentes eletrônicos.',
            icon='fas fa-file-alt',
            is_active=True,
            is_visible=True,
            show_in_menu=True,
        )
        db.session.add(category)
        db.session.flush()

    details = [
        ('Fabricante', component.manufacturer),
        ('Part number', component.part_number),
        ('Categoria', component.category),
        ('Subcategoria', component.subcategory),
        ('Encapsulamento', component.package),
        ('Ciclo de vida', component.lifecycle_status),
    ]
    specifications = component.specifications()
    description = component.description_ptbr or generate_component_summary(
        component.part_number, component.manufacturer, component.category
    )
    content_parts = [f'<p>{xml_escape(description)}</p>', '<ul>']
    content_parts.extend(
        f'<li><strong>{xml_escape(label)}:</strong> {xml_escape(str(value))}</li>'
        for label, value in details if value
    )
    content_parts.extend(
        f'<li><strong>{xml_escape(str(label))}:</strong> {xml_escape(str(value))}</li>'
        for label, value in specifications.items() if value not in (None, '')
    )
    content_parts.append('</ul>')
    content = sanitize_html(''.join(content_parts))
    title = sanitize_input(component.title_ptbr or f'{component.part_number} Datasheet')[:200]
    source_provider = sanitize_input(str(selected.get('provider') or selected.get('source_provider') or ''))[:120]
    metadata = {
        'electronic_component_id': component.id,
        'datasheet_slug': component.slug,
        'source_provider': source_provider or None,
    }

    if post is None:
        post = Post(
            title=title,
            content=content,
            author_id=author_id,
            category_id=category.id,
            category_str=category.name,
            is_active=bool(publish),
            download_link=f'/datasheet/{component.slug}',
            tags=', '.join(filter(None, ['datasheet', component.part_number, component.manufacturer]))[:200],
            seo_title=title[:100],
            seo_description=sanitize_input(description)[:200],
            slug=_unique_post_slug(expected_slug),
            manufacturer=component.manufacturer,
            brand=component.manufacturer,
            model=component.part_number,
            file_type='Datasheet',
            verification_status='verified' if component.verification_status == 'verified_consensus' else 'unverified',
            technical_notes='Publicado automaticamente pelo motor de datasheets.' if automatic else 'Aprovado pelo técnico no painel.',
            custom_metadata=json.dumps(metadata, ensure_ascii=False),
        )
        db.session.add(post)
        db.session.flush()
        component.post_id = post.id
    else:
        component.post_id = post.id
        post.title = title
        post.content = content
        post.author_id = post.author_id or author_id
        post.category_id = category.id
        post.category_str = category.name
        post.is_active = bool(publish)
        post.download_link = f'/datasheet/{component.slug}'
        post.manufacturer = component.manufacturer
        post.brand = component.manufacturer
        post.model = component.part_number
        post.file_type = 'Datasheet'
        post.date_updated = datetime.utcnow()
        post.custom_metadata = json.dumps(metadata, ensure_ascii=False)
    return post


def materialize_datasheet_component(queue_item, *, reviewer_id, publish, automatic=False):
    payload = queue_item.result()
    selected = payload.get('selected') if isinstance(payload.get('selected'), dict) else {}
    if not selected:
        raise ValueError('O item não possui metadados persistíveis para publicação.')
    config = DatasheetProviderConfig.query.filter_by(provider_name=queue_item.selected_provider).first()
    if not config or not config.metadata_persistence_allowed:
        raise ValueError('A fonte não autoriza persistência dos metadados.')
    if publish and (not config.public_republish_allowed or not config.written_permission_confirmed):
        raise ValueError('Registre autorização de republicação pública antes de publicar.')

    part_number = sanitize_input(str(selected.get('part_number') or queue_item.part_number))[:160]
    manufacturer = sanitize_input(str(selected.get('manufacturer') or queue_item.manufacturer_hint or ''))[:160] or None
    duplicate = find_component_by_identity(manufacturer, part_number)
    if duplicate:
        if publish and duplicate.post_id is None:
            _ensure_datasheet_post(duplicate, selected, author_id=reviewer_id, publish=True, automatic=automatic)
        queue_item.component_id = duplicate.id
        queue_item.status = 'duplicate'
        queue_item.admin_decision = 'marked_duplicate'
        queue_item.reviewed_by = reviewer_id
        db.session.commit()
        return duplicate

    specifications = selected.get('specifications') if isinstance(selected.get('specifications'), dict) else {}
    component = ElectronicComponent(
        manufacturer=manufacturer,
        normalized_manufacturer=normalize_component_manufacturer(manufacturer),
        part_number=part_number,
        normalized_part_number=normalize_component_part_number(part_number),
        title_ptbr=f'{part_number} Datasheet' + (f' — {manufacturer}' if manufacturer else ''),
        description_ptbr=generate_component_summary(part_number, manufacturer, selected.get('category')),
        category=sanitize_input(str(selected.get('category') or ''))[:120] or None,
        subcategory=sanitize_input(str(selected.get('subcategory') or ''))[:120] or None,
        package=sanitize_input(str(selected.get('package') or ''))[:120] or None,
        lifecycle_status=sanitize_input(str(selected.get('lifecycle_status') or ''))[:80] or None,
        confidence=max(0.0, min(1.0, float(queue_item.best_confidence or 0))),
        verification_status='verified_consensus' if not queue_item.conflicts() else 'admin_reviewed',
        specifications_json=json.dumps(specifications, ensure_ascii=False),
        slug=_unique_component_slug(part_number, manufacturer),
        is_published=bool(publish),
        publication_mode='automatic' if automatic else 'manual',
        published_at=datetime.utcnow() if publish else None,
    )
    db.session.add(component)
    db.session.flush()

    for candidate in payload.get('provider_candidates', []):
        if not isinstance(candidate, dict):
            continue
        candidate_provider = str(candidate.get('provider') or '')[:80]
        candidate_config = DatasheetProviderConfig.query.filter_by(provider_name=candidate_provider).first()
        allowed = bool(candidate_config and candidate_config.metadata_persistence_allowed)
        for field_name in ('part_number', 'manufacturer', 'category', 'package', 'lifecycle_status', 'datasheet_reference'):
            value = candidate.get(field_name)
            if value in (None, ''):
                continue
            db.session.add(ComponentSourceRecord(
                component_id=component.id,
                provider=candidate_provider,
                external_id=sanitize_input(str(candidate.get('external_id') or ''))[:255] or None,
                field_name=field_name,
                field_value_hash=hashlib.sha256(str(value).encode('utf-8')).hexdigest(),
                license_policy='public_republish' if candidate_config and candidate_config.public_republish_allowed else 'metadata_only',
                confidence=max(0.0, min(1.0, float(candidate.get('confidence') or 0))),
                persisted_value_allowed=allowed,
            ))

    reference = sanitize_input(str(selected.get('datasheet_reference') or ''))[:2000] or None
    if reference and config.pdf_reference_allowed:
        distribution_policy = 'stream_allowed' if config.pdf_stream_allowed else 'reference_only'
        if config.pdf_mirror_allowed:
            distribution_policy = 'mirror_allowed'
        db.session.add(DatasheetDocument(
            component_id=component.id,
            document_title=sanitize_input(str(selected.get('document_title') or f'Datasheet {part_number}'))[:300],
            revision=sanitize_input(str(selected.get('document_revision') or ''))[:80] or None,
            document_date=sanitize_input(str(selected.get('document_date') or ''))[:40] or None,
            language=sanitize_input(str(selected.get('document_language') or ''))[:20] or None,
            pages=coerce_int(selected.get('pages'), 0) or None,
            source_provider=config.provider_name,
            source_reference=reference,
            distribution_policy=distribution_policy,
            verification_status='policy_reviewed',
        ))

    if queue_item.source_board_id:
        db.session.add(BoardComponent(
            board_id=queue_item.source_board_id,
            component_id=component.id,
            source_resource_id=queue_item.source_resource_id,
            verified=bool(reviewer_id),
        ))
    _ensure_datasheet_post(
        component,
        selected,
        author_id=reviewer_id,
        publish=publish,
        automatic=automatic,
    )
    queue_item.component_id = component.id
    queue_item.reviewed_by = reviewer_id
    queue_item.admin_decision = 'published' if publish else 'draft'
    queue_item.status = 'published' if publish else 'approved'
    queue_item.finished_at = datetime.utcnow()
    db.session.commit()
    return component


def technical_auto_publish_decision(item, source=None):
    settings = get_technical_automation_settings()
    if not settings['enabled'] or settings['mode'] != 'full':
        return False, 'Modo semiautomático: aprovação administrativa obrigatória.'
    if item.confidence < settings['threshold']:
        return False, f'Confiança {item.confidence}% abaixo do mínimo de {settings["threshold"]}%.'
    if not source:
        return False, 'Fonte não cadastrada; revisão obrigatória.'
    if not source.enabled or not source.auto_publish or source.trust_level not in {'A', 'B'}:
        return False, 'A política da fonte exige revisão.'
    if not source.metadata_allowed:
        return False, 'A fonte não autoriza o uso dos metadados.'
    metadata = item.normalized_data()
    storage_ready = bool(metadata.get('provider_url') or metadata.get('provider_direct_url') or item.temp_path)
    distribution_policy = str(metadata.get('distribution_policy') or 'unknown').lower()
    if distribution_policy == 'metadata_only' and not storage_ready:
        return False, 'Metadados prontos; associe um arquivo distribuível antes da publicação.'
    if storage_ready and distribution_policy != 'metadata_only' and not source.distribution_allowed:
        return False, 'A fonte não autoriza distribuição automática de arquivos.'
    if settings['require_storage_ready'] and not storage_ready and metadata.get('distribution_policy') != 'metadata_only':
        return False, 'Arquivo ainda não possui storage pronto.'
    rollout_seed = item.sha256 or f'import-item-{item.id}'
    rollout_value = int(hashlib.sha256(rollout_seed.encode('utf-8')).hexdigest()[:8], 16) % 100
    if rollout_value >= settings['percentage']:
        return False, f'Item fora da faixa atual de automação ({settings["percentage"]}%).'
    return True, 'Elegível para publicação automática pela política atual.'


TECHNICAL_UPLOAD_EXTENSIONS = {
    'bin', 'rom', 'fd', 'cap', 'hex', 'efi', 'bio', 'pdf', 'brd', 'bdv', 'fz',
    'sch', 'zip', 'rar', '7z', 'cab', 'exe', 'msi', 'inf', 'txt', 'csv', 'json',
}


def _technical_job_directory(job_id):
    root = os.path.abspath(app.config['TECHNICAL_IMPORT_TEMP_DIR'])
    directory = os.path.join(root, str(int(job_id)))
    os.makedirs(directory, exist_ok=True)
    return directory


def _safe_write_uploaded_file(upload, job_id):
    original = sanitize_download_name(upload.filename or 'arquivo-tecnico')
    extension = os.path.splitext(original)[1].lower().lstrip('.')
    if extension not in TECHNICAL_UPLOAD_EXTENSIONS:
        raise ValueError(f'Extensão .{extension or "(sem extensão)"} não permitida.')
    if original.lower().endswith(('.html', '.htm', '.svg', '.js', '.php', '.py', '.sh')):
        raise ValueError('Tipo de arquivo executável ou ativo não permitido.')
    destination = os.path.join(_technical_job_directory(job_id), f'{uuid.uuid4().hex}-{secure_filename(original)}')
    upload.save(destination)
    if not os.path.isfile(destination) or os.path.getsize(destination) == 0:
        raise ValueError('O arquivo enviado está vazio.')
    _validate_technical_file_content(destination, original)
    return destination, original


def _validate_technical_file_content(path, original_name):
    size = os.path.getsize(path)
    max_bytes = int(os.environ.get('TECHNICAL_MAX_FILE_BYTES', str(256 * 1024 * 1024)))
    if size > max_bytes:
        raise ValueError(f'Arquivo excede o limite individual de {format_technical_file_size(max_bytes)}.')
    suffixes = [suffix.lower() for suffix in os.path.basename(original_name).split('.')[1:]]
    if len(suffixes) > 1 and suffixes[-1] in {'exe', 'msi', 'js', 'html', 'svg', 'sh'} and suffixes[-2] in TECHNICAL_UPLOAD_EXTENSIONS:
        raise ValueError('Arquivo com extensão dupla ambígua não permitido.')
    with open(path, 'rb') as source:
        prefix = source.read(1024).lstrip().lower()
    active_prefixes = (b'<!doctype html', b'<html', b'<svg', b'<?php', b'<script', b'#!/bin/sh', b'#!/usr/bin/env')
    if prefix.startswith(active_prefixes):
        raise ValueError('Conteúdo ativo ou executável incompatível com o tipo informado.')


def _merge_parsed_metadata(filename, overrides=None):
    parsed = parse_technical_filename(filename).to_dict()
    overrides = overrides or {}
    allowed = {
        'manufacturer', 'model', 'board_code', 'board_revision', 'version',
        'file_type', 'chip_type', 'chip_position', 'part_number', 'source_provider',
        'source_url', 'provider_url', 'provider_direct_url', 'storage_provider',
        'distribution_policy', 'license_status', 'mime_type', 'title', 'description',
        'external_id', 'external_version',
    }
    for key in allowed:
        value = overrides.get(key)
        if value not in (None, ''):
            parsed[key] = sanitize_input(str(value))[:2000]
    parsed['board_code'] = format_board_code(parsed.get('board_code'))
    parsed.setdefault('distribution_policy', 'local_allowed' if overrides.get('temp_path') else 'unknown')
    parsed.setdefault('license_status', 'unknown')
    parsed['copy'] = build_post_copy(parsed)
    confidence = coerce_int(overrides.get('confidence'), parsed.get('confidence', 0))
    if overrides.get('source_provider'):
        confidence = min(100, confidence + 5)
    parsed['confidence'] = max(0, min(100, confidence))
    return parsed


def _append_import_item(job, metadata, *, source_name=None, temp_path=None, file_hash=None, raw=None):
    if file_hash:
        duplicate = TechnicalFile.query.filter_by(sha256=file_hash).first()
    else:
        duplicate = None
    status = 'duplicate' if duplicate else 'pending_review'
    item = ImportItem(
        job=job,
        source_name=source_name or metadata.get('original_name') or metadata.get('title'),
        status=status,
        confidence=max(0, min(100, coerce_int(metadata.get('confidence'), 0))),
        raw_data_json=json.dumps(raw or {}, ensure_ascii=False, default=str),
        normalized_data_json=json.dumps(metadata, ensure_ascii=False, default=str),
        temp_path=temp_path,
        sha256=file_hash,
        duplicate_file_id=duplicate.id if duplicate else None,
        decision_reason='SHA-256 já cadastrado.' if duplicate else 'Aguardando decisão de publicação.',
    )
    db.session.add(item)
    job.total_items += 1
    job.processed_items += 1
    if duplicate:
        job.duplicate_count += 1
    else:
        job.review_count += 1
    return item


def _cleanup_import_item_temp(item):
    """Remove somente o temporário pertencente ao motor e preserva a auditoria."""
    path = os.path.abspath(item.temp_path) if item.temp_path else None
    root = os.path.abspath(app.config['TECHNICAL_IMPORT_TEMP_DIR'])
    if path:
        try:
            if os.path.commonpath([root, path]) == root and os.path.isfile(path):
                os.remove(path)
        except (OSError, ValueError):
            app.logger.warning('Não foi possível remover o temporário do item %s.', item.id)
        item.temp_path = None

    terminal = {'published', 'duplicate', 'rejected', 'error'}
    if item.job and item.job.items and all(candidate.status in terminal for candidate in item.job.items):
        directory = os.path.abspath(os.path.join(root, str(item.job.id)))
        try:
            if os.path.commonpath([root, directory]) == root and directory != root and os.path.isdir(directory):
                shutil.rmtree(directory)
        except (OSError, ValueError):
            app.logger.warning('Não foi possível limpar o diretório temporário do job %s.', item.job.id)


def _analyze_uploaded_file(job, upload):
    path, original_name = _safe_write_uploaded_file(upload, job.id)
    if original_name.lower().endswith('.zip'):
        archive_members = inspect_zip_archive(path)
        archive_metadata = _merge_parsed_metadata(original_name, {'temp_path': path})
        created = []
        with zipfile.ZipFile(path) as archive:
            for member in archive_members:
                extension = member.extension.lower()
                if extension not in TECHNICAL_UPLOAD_EXTENSIONS or extension == 'zip':
                    continue
                member_name = sanitize_download_name(member.name)
                destination = os.path.join(
                    _technical_job_directory(job.id),
                    f'{uuid.uuid4().hex}-{secure_filename(member_name)}',
                )
                with archive.open(member.name) as source, open(destination, 'wb') as target:
                    shutil.copyfileobj(source, target, 1024 * 1024)
                _validate_technical_file_content(destination, member_name)
                parsed = _merge_parsed_metadata(member.name, {'temp_path': destination})
                for inherited in ('manufacturer', 'model', 'board_code', 'board_revision'):
                    if not parsed.get(inherited) and archive_metadata.get(inherited):
                        parsed[inherited] = archive_metadata[inherited]
                parsed['copy'] = build_post_copy(parsed)
                created.append(_append_import_item(
                    job, parsed, source_name=member.name, temp_path=destination,
                    file_hash=sha256_file(destination), raw={'archive': original_name, 'member': member.to_dict()},
                ))
        if not created:
            raise ValueError('O ZIP não contém arquivos técnicos reconhecidos.')
        return created

    if original_name.lower().endswith('.csv'):
        created = []
        with open(path, 'r', encoding='utf-8-sig', newline='') as csv_file:
            for row_number, row in enumerate(csv.DictReader(csv_file), start=2):
                if row_number > 501:
                    raise ValueError('CSV excede o limite de 500 registros.')
                filename = row.get('filename') or row.get('original_filename') or row.get('title') or f'linha-{row_number}'
                parsed = _merge_parsed_metadata(filename, row)
                created.append(_append_import_item(
                    job, parsed, source_name=filename, raw={'row': row_number, 'data': row},
                ))
        if not created:
            raise ValueError('O CSV não contém registros.')
        return created

    parsed = _merge_parsed_metadata(original_name, {'temp_path': path})
    return [_append_import_item(
        job, parsed, source_name=original_name, temp_path=path,
        file_hash=sha256_file(path), raw={'filename': original_name},
    )]


def _create_board_from_metadata(metadata):
    board_code = format_board_code(metadata.get('board_code'))
    if not board_code:
        return None
    manufacturer = sanitize_input(str(metadata.get('manufacturer') or ''))[:120] or None
    board = HardwareBoard.query.filter_by(
        normalized_board_code=normalize_board_code(board_code),
        manufacturer=manufacturer,
    ).first()
    if board:
        return board
    slug_base = generate_slug(' '.join(filter(None, [manufacturer, board_code]))) or f'placa-{uuid.uuid4().hex[:8]}'
    slug = slug_base
    suffix = 2
    while HardwareBoard.query.filter_by(slug=slug).first():
        slug = f'{slug_base}-{suffix}'
        suffix += 1
    board = HardwareBoard(
        manufacturer=manufacturer,
        device_model=sanitize_input(str(metadata.get('model') or ''))[:160] or None,
        board_code=board_code,
        normalized_board_code=normalize_board_code(board_code),
        board_revision=sanitize_input(str(metadata.get('board_revision') or ''))[:80] or None,
        platform=sanitize_input(str(metadata.get('platform') or ''))[:120] or None,
        slug=slug,
    )
    db.session.add(board)
    db.session.flush()
    return board


def _unique_post_slug(base_value):
    base = generate_slug(base_value) or f'recurso-{uuid.uuid4().hex[:8]}'
    slug = base
    suffix = 2
    while Post.query.filter_by(slug=slug).first():
        slug = f'{base}-{suffix}'
        suffix += 1
    return slug


def _technical_group_identity(metadata):
    board_code = normalize_board_code(metadata.get('board_code'))
    if board_code:
        return f'board:{board_code}'
    manufacturer = generate_slug(metadata.get('manufacturer') or '')
    model = generate_slug(metadata.get('model') or '')
    if manufacturer and model:
        return f'model:{manufacturer}:{model}'
    return None


def _published_group_resource(item, metadata) -> Optional['TechnicalResource']:
    identity = _technical_group_identity(metadata)
    if not identity or not item.job_id:
        return None
    siblings = ImportItem.query.filter(
        ImportItem.job_id == item.job_id,
        ImportItem.id != item.id,
        ImportItem.status == 'published',
        ImportItem.resource_id.isnot(None),
    ).order_by(ImportItem.id.asc()).all()
    for sibling in siblings:
        if sibling.resource_id and _technical_group_identity(sibling.normalized_data()) == identity:
            return db.session.get(TechnicalResource, sibling.resource_id)
    return None


def publish_import_item(item, reviewer_id=None, automatic=False):
    if item.status == 'published':
        return item
    if item.status == 'duplicate':
        raise ValueError('O item é duplicado e não será publicado novamente.')
    metadata = item.normalized_data()
    verification_status = str(metadata.get('verification_status') or 'unverified').lower()
    if verification_status not in VERIFICATION_STATUSES:
        verification_status = 'unverified'
    post_copy = metadata.get('copy') if isinstance(metadata.get('copy'), dict) else build_post_copy(metadata)
    resource: Optional[TechnicalResource] = _published_group_resource(item, metadata)
    post: Optional[Post] = db.session.get(Post, resource.post_id) if resource and resource.post_id else None
    is_new_post = post is None
    category = None
    if is_new_post:
        category_name = post_copy.get('category') or category_for_file_type(metadata.get('file_type', ''))
        category = Category.query.filter(db.func.lower(Category.name) == category_name.lower()).first()
        if not category:
            category = Category(
                name=category_name[:50], slug=generate_slug(category_name)[:50],
                description='Recursos técnicos importados e revisados.', is_active=True,
                is_visible=True, show_in_menu=True,
            )
            db.session.add(category)
            db.session.flush()
        if category is None:
            raise RuntimeError('Não foi possível criar ou localizar a categoria do recurso técnico.')

    provider_url = normalize_download_url(metadata.get('provider_direct_url') or metadata.get('provider_url'))
    storage_provider = str(metadata.get('storage_provider') or ('local' if item.temp_path else 'http')).lower()
    local_final_path = None
    if item.temp_path and os.path.isfile(item.temp_path):
        storage_root = os.path.abspath(app.config['TECHNICAL_LOCAL_STORAGE_DIR'])
        os.makedirs(storage_root, exist_ok=True)
        extension = os.path.splitext(item.temp_path)[1].lower()
        storage_name = f'{item.sha256 or sha256_file(item.temp_path)}{extension}'
        local_final_path = os.path.join(storage_root, storage_name)
        if not os.path.exists(local_final_path):
            shutil.copy2(item.temp_path, local_final_path)
        storage_provider = 'local'
    elif not provider_url:
        if metadata.get('distribution_policy') == 'metadata_only':
            item.status = 'needs_storage'
            item.decision_reason = 'Metadado analisado; associe um arquivo distribuível antes de publicar no acervo.'
            db.session.commit()
            raise ValueError(item.decision_reason)
        item.status = 'needs_storage'
        item.decision_reason = 'Informe um link direto privado ou envie o arquivo antes de publicar.'
        db.session.commit()
        raise ValueError(item.decision_reason)

    if is_new_post:
        board = _create_board_from_metadata(metadata)
        post = Post(
            title=sanitize_input(str(post_copy.get('title') or metadata.get('title') or item.source_name or 'Recurso técnico'))[:200],
            content=sanitize_html(str(post_copy.get('content') or metadata.get('description') or 'Recurso técnico importado.')),
            author_id=reviewer_id,
            category_id=category.id,
            category_str=category.name,
            is_active=True,
            download_link='/download/pending',
            tags=sanitize_input(str(post_copy.get('tags') or ''))[:200] or None,
            seo_title=sanitize_input(str(post_copy.get('seo_title') or ''))[:100] or None,
            seo_description=sanitize_input(str(post_copy.get('seo_description') or ''))[:200] or None,
            slug=_unique_post_slug(post_copy.get('slug') or post_copy.get('title') or item.source_name),
            manufacturer=sanitize_input(str(metadata.get('manufacturer') or ''))[:120] or None,
            brand=sanitize_input(str(metadata.get('manufacturer') or ''))[:120] or None,
            model=sanitize_input(str(metadata.get('model') or ''))[:160] or None,
            board_code=format_board_code(metadata.get('board_code')),
            board_revision=sanitize_input(str(metadata.get('board_revision') or ''))[:80] or None,
            file_type=sanitize_input(str(metadata.get('file_type') or 'Arquivo técnico'))[:80],
            file_extension=sanitize_input(str(metadata.get('extension') or ''))[:30] or None,
            version=sanitize_input(str(metadata.get('version') or ''))[:80] or None,
            sha256=item.sha256,
            verification_status=verification_status,
            compatibility=sanitize_input(str(post_copy.get('compatibility') or ''))[:2000] or None,
            technical_notes='Publicado automaticamente.' if automatic else 'Revisado no centro de importação.',
        )
        db.session.add(post)
        db.session.flush()

        resource = TechnicalResource(
            post_id=post.id,
            board_id=board.id if board else None,
            resource_type=generate_slug(metadata.get('file_type') or 'other').replace('-', '_')[:40],
            title=post.title,
            manufacturer=post.manufacturer,
            model=post.model,
            part_number=sanitize_input(str(metadata.get('part_number') or ''))[:160] or None,
            board_code=post.board_code,
            board_revision=post.board_revision,
            chip=sanitize_input(str(metadata.get('chip_type') or metadata.get('chip') or ''))[:120] or None,
            chip_position=sanitize_input(str(metadata.get('chip_position') or ''))[:50] or None,
            version=post.version,
            source_type='automatic' if automatic else 'admin',
            source_provider=sanitize_input(str(metadata.get('source_provider') or 'Admin'))[:120],
            source_reference=sanitize_input(str(metadata.get('source_url') or ''))[:2000] or None,
            external_id=sanitize_input(str(metadata.get('external_id') or ''))[:255] or None,
            external_version=sanitize_input(str(metadata.get('external_version') or metadata.get('version') or ''))[:120] or None,
            last_synced_at=datetime.utcnow() if automatic or metadata.get('external_id') else None,
            verification_status=post.verification_status,
            verification_date=datetime.utcnow() if verification_status == 'verified' else None,
            license_status=sanitize_input(str(metadata.get('license_status') or 'unknown'))[:40],
            distribution_policy=sanitize_input(str(metadata.get('distribution_policy') or 'unknown'))[:40],
            metadata_json=json.dumps(metadata, ensure_ascii=False, default=str),
        )
        db.session.add(resource)
        db.session.flush()

    if post is None or resource is None:
        raise RuntimeError('Não foi possível criar ou localizar o recurso técnico agrupado.')

    display_filename = sanitize_download_name(
        metadata.get('original_name') or item.source_name or f'{post.slug}.{metadata.get("extension") or "bin"}'
    )
    technical_file = TechnicalFile(
        resource_id=resource.id,
        post_id=post.id,
        display_filename=display_filename,
        original_filename=display_filename,
        file_type=sanitize_input(str(metadata.get('file_type') or 'Arquivo'))[:80],
        chip=sanitize_input(str(metadata.get('chip_type') or ''))[:120] or None,
        chip_position=sanitize_input(str(metadata.get('chip_position') or ''))[:50] or None,
        version=sanitize_input(str(metadata.get('version') or ''))[:80] or None,
        extension=(metadata.get('extension') or os.path.splitext(display_filename)[1].lstrip('.'))[:30],
        mime_type=sanitize_input(str(metadata.get('mime_type') or ''))[:120] or None,
        file_size=os.path.getsize(local_final_path) if local_final_path else coerce_int(metadata.get('file_size'), 0) or None,
        sha256=item.sha256,
        storage_provider=storage_provider,
        provider_file_id=os.path.basename(local_final_path) if local_final_path else sanitize_input(str(metadata.get('provider_file_id') or ''))[:255] or None,
        provider_url=provider_url if storage_provider != 'local' else None,
        provider_direct_url=provider_url if storage_provider != 'local' else None,
        source_provider=resource.source_provider,
        source_url=resource.source_reference,
        link_status='online' if storage_provider == 'local' else 'unchecked',
        verification_status=resource.verification_status,
        is_active=True,
    )
    db.session.add(technical_file)
    db.session.flush()
    if is_new_post:
        post.download_link = url_for('download_technical_file', file_id=technical_file.id)
        post.file_size = (technical_file.file_size / (1024 * 1024)) if technical_file.file_size else None
        post.technical_file_size = format_technical_file_size(technical_file.file_size) or None
    item.status = 'published'
    item.post_id = post.id
    item.resource_id = resource.id
    item.technical_file_id = technical_file.id
    item.reviewed_by = reviewer_id
    item.reviewed_at = datetime.utcnow()
    item.decision_reason = 'Publicado automaticamente.' if automatic else 'Aprovado pelo administrador.'
    item.published_automatically = bool(automatic)
    item.job.success_count += 1
    item.job.review_count = max(0, item.job.review_count - 1)
    if not item.job.items or all(candidate.status in {'published', 'duplicate', 'rejected', 'error'} for candidate in item.job.items):
        item.job.status = 'completed'
        item.job.finished_at = datetime.utcnow()
    db.session.commit()
    _cleanup_import_item_temp(item)
    if item.contribution:
        item.contribution.status = 'published'
        item.contribution.reviewed_by = reviewer_id
        item.contribution.reviewed_at = datetime.utcnow()
    db.session.commit()
    return item


def normalize_hex_color(value, default='#3a86ff'):
    color = (value or '').strip()
    if re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        return color
    return default


def hex_to_rgb_string(value, default='58, 134, 255'):
    color = normalize_hex_color(value, '')
    if not color:
        return default
    try:
        return ', '.join(str(int(color[index:index + 2], 16)) for index in (1, 3, 5))
    except (TypeError, ValueError):
        return default


def whatsapp_link_from_phone(phone_value):
    digits = re.sub(r'\D+', '', phone_value or '')
    if len(digits) in (10, 11) and not digits.startswith('55'):
        digits = f'55{digits}'
    return f'https://wa.me/{digits}' if digits else '#'


LIVE_SITE_SETTING_KEYS = (
    'site_name',
    'site_description',
    'footer_text',
    'footer_description',
    'home_hero_title',
    'home_hero_subtitle',
    'enable_dark_mode',
    'primary_color',
    'secondary_color',
    'contact_email',
    'contact_phone',
    'contact_address',
    'social_links',
    'plan_enabled_free',
    'plan_enabled_premium',
    'plan_enabled_vip',
    'plan_name_free',
    'plan_name_premium',
    'plan_name_vip',
    'plan_price_premium',
    'plan_price_vip',
    'plan_card_enabled_premium',
    'plan_card_enabled_vip',
    'plan_pix_enabled_premium',
    'plan_pix_enabled_vip',
    'google_analytics',
    'maintenance_mode',
)


def get_live_site_settings():
    """Retorna apenas configurações públicas usadas pela atualização dinâmica."""
    config = SiteConfig.get_config()
    settings = {key: config.get(key) for key in LIVE_SITE_SETTING_KEYS}
    settings['primary_color'] = normalize_hex_color(settings.get('primary_color'), '#3a86ff')
    settings['secondary_color'] = normalize_hex_color(settings.get('secondary_color'), '#8338ec')
    settings['primary_rgb'] = hex_to_rgb_string(settings['primary_color'])
    settings['secondary_rgb'] = hex_to_rgb_string(settings['secondary_color'], '131, 56, 236')
    settings['contact_whatsapp_url'] = whatsapp_link_from_phone(settings.get('contact_phone'))
    settings['current_year'] = datetime.now(BRAZIL_TZ).year
    return settings


def get_plan_entitlements(user_or_plan):
    """Retorna a matriz canônica de recursos do plano informado."""
    return resolve_plan_entitlements(user_or_plan)


def get_user_plan_limits(user):
    entitlements = get_plan_entitlements(user)
    period = entitlements['download_period']
    default_limit = entitlements['download_limit']

    daily_limit = None
    weekly_limit = None
    if period == 'daily':
        daily_limit = user.custom_daily_limit if user.custom_daily_limit is not None else default_limit
    elif period == 'weekly':
        weekly_limit = user.custom_weekly_limit if user.custom_weekly_limit is not None else default_limit

    return {
        'daily_limit': daily_limit,
        'weekly_limit': weekly_limit,
        'download_period': period,
    }


def serialize_user_for_admin(user):
    """Payload unico para modais e atualizacoes dinamicas do admin."""
    limits = get_user_plan_limits(user)
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    return {
        'id': user.id,
        'username': user.username,
        'name': user.name or '',
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'display_name': user.get_full_name(),
        'email': user.email,
        'role': user.role,
        'plan': user.plan,
        'is_active': bool(user.is_active),
        'is_verified': bool(user.is_verified),
        'email_notifications': bool(user.email_notifications),
        'bio': user.bio or '',
        'location': user.location or '',
        'phone': user.phone or '',
        'website': user.website or '',
        'facebook': user.facebook or '',
        'twitter': user.twitter or '',
        'instagram': user.instagram or '',
        'linkedin': user.linkedin or '',
        'github': user.github or '',
        'ip_address': user.ip_address or '',
        'browser': user.browser or '',
        'operating_system': user.operating_system or '',
        'referrer': user.referrer or '',
        'date_joined': user.date_joined.isoformat() if user.date_joined else None,
        'date_joined_label': user.date_joined.strftime('%d/%m/%Y %H:%M') if user.date_joined else 'N/A',
        'last_login': user.last_login.isoformat() if user.last_login else None,
        'last_login_label': user.last_login.strftime('%d/%m/%Y %H:%M') if user.last_login else 'N/A',
        'profile_image_url': get_image_url_for_response(user.profile_image, folder='profiles', default='default_profile.jpg'),
        'daily_limit': limits['daily_limit'],
        'weekly_limit': limits['weekly_limit'],
        'download_period': limits['download_period'],
        'daily_downloads': user.daily_downloads or 0,
        'weekly_downloads': user.weekly_downloads or 0,
        'download_reset_date': user.download_reset_date.isoformat() if user.download_reset_date else (today_start + timedelta(days=1)).isoformat(),
        'week_reset_date': user.week_reset_date.isoformat() if user.week_reset_date else (week_start + timedelta(days=7)).isoformat(),
        'can_download': bool(user.can_download),
        'custom_daily_limit': user.custom_daily_limit,
        'custom_weekly_limit': user.custom_weekly_limit,
    }


PLAN_METADATA = {
    'free': {
        'label': 'Grátis',
        'icon': 'fas fa-user',
        'theme': 'free'
    },
    'premium': {
        'label': 'Premium',
        'icon': 'fas fa-star',
        'theme': 'premium'
    },
    'vip': {
        'label': 'VIP',
        'icon': 'fas fa-crown',
        'theme': 'vip'
    }
}

DEFAULT_PLAN_PRICE_CENTS = {
    'premium': 2990,
    'vip': 4990
}

STRIPE_PLAN_PRODUCT_IDS = {
    'premium': os.environ.get('STRIPE_PRODUCT_PREMIUM', '').strip(),
    'vip': os.environ.get('STRIPE_PRODUCT_VIP', '').strip(),
}

STRIPE_PLAN_PRICE_CACHE_TTL_SECONDS = 300
CHAT_PUBLIC_ROOM_ID = 'todos'
CHAT_MESSAGE_LIMIT = 80
CHAT_MESSAGE_EDIT_WINDOW_MS = 10 * 60 * 1000

_stripe_plan_price_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def normalize_plan_key(plan: str | None) -> str:
    normalized = str(plan or 'free').strip().lower()
    return normalized if normalized in PLAN_METADATA else 'free'


def get_plan_metadata(
    plan: str | None,
    config_values: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Metadados visuais do plano, incluindo o nome configurado pelo admin."""
    plan_key = normalize_plan_key(plan)
    metadata = dict(PLAN_METADATA.get(plan_key, PLAN_METADATA['free']))
    config_key = f'plan_name_{plan_key}'
    configured_label = (
        config_values.get(config_key)
        if config_values is not None and config_key in config_values
        else SiteConfig.get_value(config_key, metadata['label'])
    )
    normalized_label = ' '.join(str(configured_label or '').split()).strip()
    metadata['label'] = normalized_label or metadata['label']
    return metadata


def is_plan_enabled(plan: str | None, config_values: Mapping[str, Any] | None = None) -> bool:
    """Indica se um plano pode receber novas adesoes ou alteracoes."""
    plan_key = normalize_plan_key(plan)
    config_key = f'plan_enabled_{plan_key}'
    raw_value = (
        config_values.get(config_key)
        if config_values is not None and config_key in config_values
        else SiteConfig.get_value(config_key, True)
    )
    return coerce_bool(raw_value, default=True)


def is_plan_payment_method_enabled(
    plan: str | None,
    method: str,
    config_values: Mapping[str, Any] | None = None,
) -> bool:
    """Indica se o método pode iniciar novas assinaturas para o plano."""
    plan_key = normalize_plan_key(plan)
    method_key = str(method or '').strip().lower()
    if plan_key not in DEFAULT_PLAN_PRICE_CENTS or method_key not in {'card', 'pix'}:
        return False

    config_key = f'plan_{method_key}_enabled_{plan_key}'
    raw_value = (
        config_values.get(config_key)
        if config_values is not None and config_key in config_values
        else SiteConfig.get_value(config_key, True)
    )
    return coerce_bool(raw_value, default=True)


def format_brl_from_cents(amount_cents: int) -> str:
    amount = Decimal(max(0, int(amount_cents or 0))) / Decimal('100')
    formatted = f'{amount:,.2f}'
    return formatted.replace(',', 'X').replace('.', ',').replace('X', '.')


def get_plan_price_cents(plan: str | None, config_values: Mapping[str, Any] | None = None) -> int:
    plan_key = normalize_plan_key(plan)
    default_cents = DEFAULT_PLAN_PRICE_CENTS.get(plan_key, 0)
    if plan_key not in DEFAULT_PLAN_PRICE_CENTS:
        return default_cents

    config_key = f'plan_price_{plan_key}'
    raw_value = (
        config_values.get(config_key)
        if config_values is not None and config_key in config_values
        else SiteConfig.get_value(config_key, Decimal(default_cents) / Decimal('100'))
    )

    try:
        amount = Decimal(str(raw_value).replace(',', '.'))
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal(default_cents) / Decimal('100')

    if amount < 0:
        amount = Decimal('0')

    return int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def get_plan_pricing_config(config_values: Mapping[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    pricing: dict[str, dict[str, Any]] = {
        'free': {
            **get_plan_metadata('free', config_values=config_values),
            'amount_cents': 0,
            'display_amount': '0',
            'enabled': is_plan_enabled('free', config_values=config_values),
            'card_enabled': False,
            'pix_enabled': False,
        }
    }

    for plan_key in DEFAULT_PLAN_PRICE_CENTS:
        amount_cents = get_plan_price_cents(plan_key, config_values=config_values)
        pricing[plan_key] = {
            **get_plan_metadata(plan_key, config_values=config_values),
            'amount_cents': amount_cents,
            'display_amount': format_brl_from_cents(amount_cents),
            'enabled': is_plan_enabled(plan_key, config_values=config_values),
            'card_enabled': is_plan_payment_method_enabled(plan_key, 'card', config_values=config_values),
            'pix_enabled': is_plan_payment_method_enabled(plan_key, 'pix', config_values=config_values),
        }

    return pricing


def get_stripe_product_id_for_plan(plan: str | None) -> str | None:
    return STRIPE_PLAN_PRODUCT_IDS.get(normalize_plan_key(plan))


def _extract_valid_stripe_subscription_price(price_data: Any, expected_product_id: str | None = None) -> dict[str, Any] | None:
    if not price_data:
        return None

    try:
        price_id = str(price_data.get('id') or '')
        product_id = str(price_data.get('product') or '')
        currency = str(price_data.get('currency') or 'brl').lower()
        unit_amount = int(price_data.get('unit_amount') or 0)
        recurring = price_data.get('recurring') or {}
        is_active = bool(price_data.get('active', True))
    except Exception:
        return None

    if not price_id or unit_amount <= 0 or not is_active:
        return None

    if expected_product_id and product_id and product_id != expected_product_id:
        return None

    if str(recurring.get('interval') or '').lower() != 'month':
        return None

    return {
        'price_id': price_id,
        'product_id': product_id or expected_product_id or '',
        'currency': currency,
        'unit_amount': unit_amount,
    }


def get_stripe_subscription_price(plan: str | None) -> dict[str, Any] | None:
    plan_key = normalize_plan_key(plan)
    product_id = get_stripe_product_id_for_plan(plan_key)
    if not product_id or not stripe.api_key:
        return None

    now_ts = datetime.utcnow().timestamp()
    cached = _stripe_plan_price_cache.get(plan_key)
    if cached and (now_ts - cached[0]) < STRIPE_PLAN_PRICE_CACHE_TTL_SECONDS:
        return cached[1]

    resolved_price: dict[str, Any] | None = None

    try:
        product = stripe.Product.retrieve(product_id, expand=['default_price'])
        default_price = product.get('default_price')
        if isinstance(default_price, str):
            default_price = stripe.Price.retrieve(default_price)

        resolved_price = _extract_valid_stripe_subscription_price(default_price, expected_product_id=product_id)

        if not resolved_price:
            price_list = stripe.Price.list(
                product=product_id,
                active=True,
                type='recurring',
                limit=10
            )

            fallback_price = None
            for price_data in price_list.get('data', []):
                parsed_price = _extract_valid_stripe_subscription_price(price_data, expected_product_id=product_id)
                if not parsed_price:
                    continue
                if parsed_price['currency'] == 'brl':
                    resolved_price = parsed_price
                    break
                if fallback_price is None:
                    fallback_price = parsed_price

            if not resolved_price:
                resolved_price = fallback_price
    except Exception as exc:
        app.logger.error(f'Erro ao obter preço Stripe do plano {plan_key}: {exc}')
        return None

    if resolved_price:
        _stripe_plan_price_cache[plan_key] = (now_ts, resolved_price)

    return resolved_price


def get_effective_plan_charge_cents(plan: str | None) -> int:
    """Valor canônico de cobrança, controlado pelas configurações do painel."""
    return get_plan_price_cents(plan)

# Modelo para tracking de atividades administrativas
class AdminActivity(db.Model):
    __tablename__ = 'admin_activities'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    activity_metadata = db.Column(db.Text, nullable=True)  # JSON data
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamento com User
    user = db.relationship('User', backref=db.backref('admin_activities', lazy=True))

    def __repr__(self):
        return f"AdminActivity('{self.action}', '{self.user.username}', '{self.created_at}')"

# Modelo para tracking de visitantes e analytics
class VisitorLog(db.Model):
    __tablename__ = 'visitor_logs'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False)
    user_agent = db.Column(db.Text)
    referrer = db.Column(db.String(500))
    page_visited = db.Column(db.String(200))
    visit_time = db.Column(db.DateTime, default=datetime.utcnow)
    session_id = db.Column(db.String(100))
    country = db.Column(db.String(50))
    device_type = db.Column(db.String(50))  # mobile, desktop, tablet
    browser = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

class Subscriber(db.Model):
    __tablename__ = 'subscribers'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    name = db.Column(db.String(100))
    subscribed_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    confirm_token = db.Column(db.String(100), unique=True)
    confirmed = db.Column(db.Boolean, default=False)

    # Relacionamento com grupos
    groups = db.relationship('NewsletterGroup', secondary='subscriber_groups', back_populates='subscribers')

    def get_groups_names(self):
        """Retorna nomes dos grupos separados por vírgula"""
        try:
            # Verificar se o relacionamento existe e foi carregado
            if hasattr(self, 'groups'):
                # Forçar carregamento do relacionamento
                groups_query = db.session.query(NewsletterGroup).join(
                    subscriber_groups, NewsletterGroup.id == subscriber_groups.c.group_id
                ).filter(subscriber_groups.c.subscriber_id == self.id).all()

                if groups_query:
                    return ', '.join([group.name for group in groups_query])
            return 'Geral'
        except (AttributeError, TypeError, Exception):
            return 'Geral'

# Modelo para grupos de newsletter
class NewsletterGroup(db.Model):
    __tablename__ = 'newsletter_groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamento com assinantes
    subscribers = db.relationship('Subscriber', secondary='subscriber_groups', back_populates='groups')

    def __repr__(self):
        return f"NewsletterGroup('{self.name}')"

# Tabela de associação para many-to-many entre Subscriber e NewsletterGroup
subscriber_groups = db.Table('subscriber_groups',
    db.Column('subscriber_id', db.Integer, db.ForeignKey('subscribers.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('newsletter_groups.id'), primary_key=True)
)

# Modelo para backups
class Backup(db.Model):
    __tablename__ = 'backups'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    backup_type = db.Column(db.String(50), nullable=False)  # 'database', 'files', 'full'
    file_size = db.Column(db.BigInteger, nullable=False)  # tamanho em bytes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_automatic = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='completed')  # 'pending', 'in_progress', 'completed', 'failed'

    # Relacionamento com usuário
    user = db.relationship('User', backref=db.backref('backups', lazy=True))

    def get_file_size_formatted(self):
        """Retorna o tamanho do arquivo formatado"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def __repr__(self):
        return f"Backup('{self.filename}', '{self.backup_type}')"

# Modelo para estatísticas de posts
class PostStats(db.Model):
    __tablename__ = 'post_stats'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    views = db.Column(db.Integer, default=0)
    downloads = db.Column(db.Integer, default=0)

# Adicionar modelo Contact para mensagens de contato
class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=True)
    message = db.Column(db.Text, nullable=False)
    date_sent = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"Contact('{self.email}', '{self.subject}')"

# Contexto global mais completo para templates
@app.context_processor
def inject_global_data():
    # Função helper para gerar URL de post
    def post_url(post):
        if post.slug and post.category_str:
            category_slug = generate_slug(post.category_str)
            return url_for('post_by_slug', category=category_slug, slug=post.slug)
        return url_for('post', post_id=post.id)

    # Função helper para gerar URL de imagem (local ou Cloudinary)
    def get_image_url(image_path, folder='profiles', default='default.jpg'):
        return get_image_url_for_response(image_path, folder=folder, default=default)

    # Categorias públicas, sempre vindas do banco para refletir o painel admin.
    populated_categories, expanding_categories = get_public_categories_partition()
    categories = sorted(
        [*populated_categories, *expanding_categories],
        key=lambda category_item: (category_item.order or 0, category_item.name.casefold()),
    )
    for category_item in categories:
        apply_default_category_data(category_item)
    menu_categories = [category_item for category_item in categories if category_item.show_in_menu]
    home_categories = [category_item for category_item in categories if category_item.featured] or categories

    # Posts em destaque
    featured_posts = Post.query.filter_by(featured=True, is_active=True).order_by(Post.date_posted.desc()).limit(4).all()

    # Configurações do site
    config = SiteConfig.get_config()
    plan_pricing = get_plan_pricing_config(config)
    primary_color = normalize_hex_color(config.get('primary_color'), '#3a86ff')
    secondary_color = normalize_hex_color(config.get('secondary_color'), '#8338ec')

    # Estatísticas para o frontend
    stats = {
        "total_posts": Post.query.filter_by(is_active=True).count(),
        "total_users": User.query.filter_by(is_active=True).count(),
        "total_downloads": db.session.query(db.func.sum(Post.downloads)).scalar() or 0,
        "total_subscribers": Subscriber.query.filter_by(is_active=True).count(),
        "total_comments": Comment.query.count()
    }

    firebase_public_config = {
        'apiKey': app.config.get('FIREBASE_API_KEY', ''),
        'authDomain': app.config.get('FIREBASE_AUTH_DOMAIN', ''),
        'projectId': app.config.get('FIREBASE_PROJECT_ID', ''),
        'storageBucket': app.config.get('FIREBASE_STORAGE_BUCKET', ''),
        'messagingSenderId': app.config.get('FIREBASE_MESSAGING_SENDER_ID', ''),
        'appId': app.config.get('FIREBASE_APP_ID', ''),
        'measurementId': app.config.get('FIREBASE_MEASUREMENT_ID', '')
    }
    analytics_event = flask_session.pop('analytics_event', '')
    if analytics_event not in {'login', 'sign_up'}:
        analytics_event = ''

    # Dados específicos para admin (só quando necessário)
    admin_data = {}
    if request.endpoint and request.endpoint.startswith('admin'):
        admin_data.update({
            'post_count': Post.query.filter_by(is_active=True).count(),
            'category_count': Category.query.filter_by(is_active=True).count(),
            'user_count': User.query.filter_by(is_active=True).count(),
            'comment_count': Comment.query.count(),
            'subscriber_count': Subscriber.query.filter_by(is_active=True).count(),
            'unread_comments': Comment.query.count()  # Todos os comentários por enquanto
        })

    return dict(
        categories=categories,
        menu_categories=menu_categories,
        home_categories=home_categories,
        menu_subcategories_map=get_category_subcategories_map(include_defaults=True),
        category_public_url_value=category_public_url_value,
        format_subcategory_label=format_subcategory_label,
        featured_posts=featured_posts,
        post_url=post_url,
        get_image_url=get_image_url,  # Adicionar helper de imagens
        get_public_download_files=get_public_download_files,
        hex_to_rgb=hex_to_rgb_string,
        whatsapp_link_from_phone=whatsapp_link_from_phone,
        config=config,
        site_configs=config,  # Adicionar alias para compatibilidade
        site_primary_color=primary_color,
        site_secondary_color=secondary_color,
        site_primary_rgb=hex_to_rgb_string(primary_color),
        site_secondary_rgb=hex_to_rgb_string(secondary_color, '131, 56, 236'),
        stats=stats,
        plan_pricing=plan_pricing,
        plan_entitlements=PLAN_ENTITLEMENTS,
        canonical_url=_absolute_public_url(request.path),
        public_base_url=_get_public_base_url(),
        firebase_public_config=firebase_public_config,
        meta_pixel_id=app.config.get('META_PIXEL_ID', ''),
        chat_backend_available=is_firebase_admin_configured(),
        analytics_event=analytics_event,
        current_year=datetime.now(BRAZIL_TZ).year,
        datetime=datetime,  # Adicionar datetime para uso em templates
        **admin_data
    )

# Adicione isso na seção de inicialização da aplicação, próximo ao início do arquivo
@app.template_filter('initials')
def initials_filter(name):
    """Gera as iniciais do nome para exibição em placeholders."""
    if not name:
        return "MI"
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    elif len(parts) == 1:
        return parts[0][:2].upper()
    else:
        return "MI"

@app.template_filter('apply_theme_colors')
def apply_theme_colors(css_content):
    """Aplica as cores do tema no CSS"""
    try:
        primary_color = SiteConfig.get_value('primary_color', '#3a86ff')
        secondary_color = SiteConfig.get_value('secondary_color', '#8338ec')

        # Substitui as variáveis CSS pelos valores configurados
        css_content = css_content.replace('var(--primary-color)', primary_color)
        css_content = css_content.replace('var(--secondary-color)', secondary_color)
        css_content = css_content.replace('#3a86ff', primary_color)
        css_content = css_content.replace('#8338ec', secondary_color)

        return css_content
    except Exception:
        return css_content

@app.template_filter('to_brazil_time')
def to_brazil_time(utc_datetime):
    """Converte datetime UTC para horário de Brasília"""
    if not utc_datetime:
        return None

    # Se o datetime não tem timezone, assume UTC
    if utc_datetime.tzinfo is None:
        utc_datetime = pytz.UTC.localize(utc_datetime)

    # Converte para horário de Brasília
    brazil_time = utc_datetime.astimezone(BRAZIL_TZ)
    return brazil_time

@app.template_filter('format_date_pt')
def format_date_pt(date_value, format_string='%d de %B de %Y'):
    """Formata datas em português brasileiro"""
    if not date_value:
        return 'Data não disponível'

    # Converte para horário de Brasília se for datetime
    if isinstance(date_value, datetime):
        date_value = to_brazil_time(date_value)

    # Mapeamento de meses em português
    months_pt = {
        'January': 'Janeiro',
        'February': 'Fevereiro',
        'March': 'Março',
        'April': 'Abril',
        'May': 'Maio',
        'June': 'Junho',
        'July': 'Julho',
        'August': 'Agosto',
        'September': 'Setembro',
        'October': 'Outubro',
        'November': 'Novembro',
        'December': 'Dezembro'
    }

    # Formatar a data usando strftime
    formatted = date_value.strftime(format_string)

    # Substituir nomes de meses em inglês por português
    for eng, pt in months_pt.items():
        formatted = formatted.replace(eng, pt)

    return formatted


SEO_SITE_URL_ENV_KEYS = ('SITE_URL', 'BASE_URL', 'PUBLIC_URL', 'RENDER_EXTERNAL_URL')

SEO_PUBLIC_STATIC_PAGES = (
    ('/', 'daily', '1.0'),
    ('/categorias', 'daily', '0.9'),
    ('/posts', 'daily', '0.9'),
    ('/datasheets', 'daily', '0.8'),
    ('/sobre', 'monthly', '0.6'),
    ('/faq', 'monthly', '0.6'),
    ('/contato', 'monthly', '0.5'),
    ('/planos', 'monthly', '0.5'),
    ('/termos-de-uso', 'yearly', '0.3'),
    ('/politica-de-privacidade', 'yearly', '0.3'),
)

SEO_ROBOTS_DISALLOW_PATHS = (
    '/admin',
    '/api/',
    '/debug/',
    '/setup',
    '/login',
    '/register',
    '/logout',
    '/profile',
    '/reset-password',
    '/area-vip',
    '/download/',
    '/favorite/',
    '/unfavorite/',
    '/newsletter',
    '/clear-download-history',
    '/update-profile-image',
    '/remove-profile-image',
    '/update-password',
    '/downgrade_plan',
    '/create-checkout-session',
    '/create-donation-checkout-session',
    '/checkout-success',
    '/checkout-cancel',
    '/donation-success',
    '/create-pix-checkout',
    '/create-donation-pix-checkout',
    '/process-pix-async/',
    '/pix-checkout',
    '/pix-checkout-error',
    '/pix-checkout-success',
    '/cancel-pix-transaction/',
    '/check-pix-payment/',
    '/stripe-webhook',
    '/abacatepay-webhook',
    '/pesquisa',
    '/test-password-toggle',
    '/*/comments',
)


def _normalize_public_base_url(raw_url: str | None) -> str | None:
    raw_url = (raw_url or '').strip()
    if not raw_url:
        return None

    if raw_url.startswith('//'):
        raw_url = f'https:{raw_url}'
    elif not re.match(r'^https?://', raw_url, flags=re.IGNORECASE):
        raw_url = f'https://{raw_url}'

    parsed = url_parse(raw_url)
    if not parsed.netloc:
        return None

    scheme = parsed.scheme.lower()
    if scheme not in {'http', 'https'}:
        scheme = 'https'

    base_path = parsed.path.rstrip('/')
    return f'{scheme}://{parsed.netloc}{base_path}'.rstrip('/')


def _get_public_base_url() -> str:
    for env_key in SEO_SITE_URL_ENV_KEYS:
        configured_url = _normalize_public_base_url(os.environ.get(env_key))
        if configured_url:
            return configured_url

    configured_url = _normalize_public_base_url(app.config.get('SITE_URL'))
    if configured_url:
        return configured_url

    forwarded_host = request.headers.get('X-Forwarded-Host', '').split(',', 1)[0].strip()
    forwarded_proto = request.headers.get('X-Forwarded-Proto', '').split(',', 1)[0].strip()
    host = forwarded_host or request.host or url_parse(request.url_root).netloc
    scheme = forwarded_proto or request.scheme or 'https'

    if is_production_environment() and scheme == 'http':
        scheme = 'https'

    return _normalize_public_base_url(f'{scheme}://{host}') or request.url_root.rstrip('/')


def _absolute_public_url(path: str) -> str:
    if re.match(r'^https?://', path, flags=re.IGNORECASE):
        return path

    if not path.startswith('/'):
        path = f'/{path}'

    return f'{_get_public_base_url()}{path}'


def _coerce_sitemap_datetime(value):
    if not value:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(pytz.UTC).replace(tzinfo=None)
        return value

    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(pytz.UTC).replace(tzinfo=None)
            return parsed
        except ValueError:
            return None

    return None


def _format_sitemap_lastmod(value) -> str | None:
    value = _coerce_sitemap_datetime(value)
    if not value:
        return None
    return value.date().isoformat()


def _latest_active_post_date(*filters):
    posted_query = db.session.query(db.func.max(Post.date_posted)).filter(Post.is_active == True)
    updated_query = db.session.query(db.func.max(Post.date_updated)).filter(Post.is_active == True)

    for filter_condition in filters:
        posted_query = posted_query.filter(filter_condition)
        updated_query = updated_query.filter(filter_condition)

    dates = [
        _coerce_sitemap_datetime(posted_query.scalar()),
        _coerce_sitemap_datetime(updated_query.scalar()),
    ]
    dates = [date_value for date_value in dates if date_value]
    return max(dates) if dates else None


def _post_sitemap_lastmod(post):
    dates = [
        _coerce_sitemap_datetime(post.date_posted),
        _coerce_sitemap_datetime(post.date_updated),
    ]
    dates = [date_value for date_value in dates if date_value]
    return max(dates) if dates else None


def _post_public_path(post):
    category_name = post.category_str or (post.category_rel.name if post.category_rel else '')
    if post.slug and category_name:
        return url_for('post_by_slug', category=generate_slug(category_name), slug=post.slug)
    return url_for('post', post_id=post.id)


def _add_sitemap_entry(entries, seen_urls, path, lastmod=None, changefreq=None, priority=None):
    loc = _absolute_public_url(path)
    if loc in seen_urls:
        return

    seen_urls.add(loc)
    entry = {'loc': loc}

    formatted_lastmod = _format_sitemap_lastmod(lastmod)
    if formatted_lastmod:
        entry['lastmod'] = formatted_lastmod
    if changefreq:
        entry['changefreq'] = str(changefreq)
    if priority:
        entry['priority'] = str(priority)

    entries.append(entry)


def _build_sitemap_entries() -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    latest_content_date = _latest_active_post_date()

    for path, changefreq, priority in SEO_PUBLIC_STATIC_PAGES:
        lastmod = latest_content_date if path in {'/', '/categorias', '/posts'} else None
        _add_sitemap_entry(entries, seen_urls, path, lastmod=lastmod, changefreq=changefreq, priority=priority)

    categories, _expanding_categories = get_public_categories_partition()
    for category_item in categories:
        category_filter = db.or_(Post.category_id == category_item.id, Post.category_str == category_item.name)
        _add_sitemap_entry(
            entries,
            seen_urls,
            url_for('category', category=category_public_url_value(category_item)),
            lastmod=_latest_active_post_date(category_filter),
            changefreq='weekly',
            priority='0.8',
        )

    subcategories = db.session.query(Post.subcategory).filter(
        Post.is_active == True,
        Post.subcategory.isnot(None),
        Post.subcategory != ''
    ).distinct().order_by(Post.subcategory.asc()).all()
    for (subcategory_slug,) in subcategories:
        _add_sitemap_entry(
            entries,
            seen_urls,
            url_for('subcategory', subcategory=subcategory_slug),
            lastmod=_latest_active_post_date(Post.subcategory == subcategory_slug),
            changefreq='weekly',
            priority='0.7',
        )

    active_posts = Post.query.filter_by(is_active=True).order_by(Post.date_posted.desc()).all()
    for post_item in active_posts:
        _add_sitemap_entry(
            entries,
            seen_urls,
            _post_public_path(post_item),
            lastmod=_post_sitemap_lastmod(post_item),
            changefreq='weekly',
            priority='0.7',
        )

    for board_item in HardwareBoard.query.order_by(HardwareBoard.updated_at.desc()).all():
        _add_sitemap_entry(
            entries,
            seen_urls,
            url_for('hardware_board_detail', slug=board_item.slug),
            lastmod=board_item.updated_at,
            changefreq='weekly',
            priority='0.7',
        )

    published_components = ElectronicComponent.query.filter_by(is_published=True).order_by(
        ElectronicComponent.updated_at.desc()
    ).all()
    for component_item in published_components:
        _add_sitemap_entry(
            entries,
            seen_urls,
            url_for('datasheet_component_detail', slug=component_item.slug),
            lastmod=component_item.updated_at,
            changefreq='monthly',
            priority='0.6',
        )

    return entries


def _render_sitemap_xml(entries: list[dict[str, str]]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for entry in entries:
        lines.append('  <url>')
        lines.append(f'    <loc>{xml_escape(entry["loc"])}</loc>')
        if entry.get('lastmod'):
            lines.append(f'    <lastmod>{xml_escape(entry["lastmod"])}</lastmod>')
        if entry.get('changefreq'):
            lines.append(f'    <changefreq>{xml_escape(entry["changefreq"])}</changefreq>')
        if entry.get('priority'):
            lines.append(f'    <priority>{xml_escape(entry["priority"])}</priority>')
        lines.append('  </url>')

    lines.append('</urlset>')
    return '\n'.join(lines) + '\n'


@app.route('/robots.txt')
@limiter.exempt
def robots_txt():
    lines = [
        'User-agent: *',
        'Allow: /',
        'Allow: /static/',
    ]

    for path in SEO_ROBOTS_DISALLOW_PATHS:
        lines.append(f'Disallow: {path}')

    lines.extend(['', f'Sitemap: {_absolute_public_url(url_for("sitemap_xml"))}'])
    response = Response('\n'.join(lines) + '\n', content_type='text/plain; charset=utf-8')
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return response


@app.route('/sitemap.xml')
@limiter.exempt
def sitemap_xml():
    response = Response(_render_sitemap_xml(_build_sitemap_entries()), content_type='application/xml; charset=utf-8')
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return response


# Rotas principais
@app.route('/')
@app.route('/home')
def home():
    try:
        page = request.args.get('page', 1, type=int)
        posts_query = Post.query.filter_by(is_active=True).order_by(Post.date_posted.desc())
        posts_paginated = posts_query.paginate(page=page, per_page=8, error_out=False)
        posts = posts_paginated.items
        featured = Post.query.filter_by(featured=True).limit(4).all()
        most_used = Post.query.filter(Post.is_active == True, Post.downloads > 0).order_by(
            Post.downloads.desc(), Post.date_posted.desc()
        ).limit(4).all()

        # Lista de IDs de posts favoritados pelo usuário atual
        favorite_post_ids = []
        if current_user.is_authenticated:
            # Forçar refresh da sessão para evitar cache
            db.session.expire_all()
            favorite_post_ids = [f.post_id for f in Favorite.query.filter_by(user_id=current_user.id).all()]

        # Estatísticas reais para a página inicial
        stats = {
            'total_posts': Post.query.filter_by(is_active=True).count(),
            'total_downloads': db.session.query(db.func.sum(Post.downloads)).scalar() or 0,
            'total_users': User.query.filter_by(is_active=True).count(),
            'total_subscribers': Subscriber.query.filter_by(is_active=True).count()
        }

        return render_template('index.html', posts=posts, posts_pagination=posts_paginated,
                               featured=featured, most_used=most_used, stats=stats,
                               favorite_post_ids=favorite_post_ids, title='Início')
    except Exception:
        app.logger.exception('Erro ao carregar a pagina inicial')
        return render_template('errors/500.html', title='Erro interno'), 500

# Atualizar a rota /setup para redirecionar para o painel admin
@app.route('/setup')
def setup():
    """Rota depreciada - redireciona para o painel administrativo"""
    flash('A página de configuração foi movida para o painel administrativo.', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/categorias')
def all_categories():
    """Página exclusiva de todas as categorias"""
    populated_categories, empty_categories = get_public_categories_partition()
    categories = sorted(
        [*populated_categories, *empty_categories],
        key=lambda item: (item.order or 0, item.name.casefold()),
    )
    for cat in categories:
        apply_default_category_data(cat)

    return render_template('categories.html', categories=categories,
                           expanding_categories=[],
                           title='Todas as Categorias')

@app.route('/categoria/<string:category>')
def category(category):
    page = request.args.get('page', 1, type=int)
    category_record, category_filter, category_name = get_category_query_filter(category)
    posts = Post.query.filter(category_filter, Post.is_active == True).order_by(Post.date_posted.desc()).paginate(page=page, per_page=8)

    subcategory_query = db.session.query(Post.subcategory).filter(
        category_filter,
        Post.subcategory.isnot(None),
        Post.subcategory != ''
    ).distinct()
    subcategories = subcategory_query.all()
    subcategories = [subcategory[0] for subcategory in subcategories if subcategory[0]]

    # Obter IDs dos posts favoritados do usuário logado
    favorite_post_ids = set()
    if current_user.is_authenticated:
        favorite_post_ids = {f.post_id for f in Favorite.query.filter_by(user_id=current_user.id).all()}

    return render_template(
        'category.html',
        posts=posts,
        category=category_name,
        category_record=category_record,
        subcategories=subcategories,
        favorite_post_ids=favorite_post_ids,
        title=f'Categoria - {category_name}'
    )

@app.route('/subcategoria/<string:subcategory>')
def subcategory(subcategory):
    page = request.args.get('page', 1, type=int)
    posts = Post.query.filter_by(subcategory=subcategory, is_active=True).order_by(Post.date_posted.desc()).paginate(page=page, per_page=8)
    category_name = subcategory.replace('-', ' ').title()
    category_name = category_name.replace('Bios', 'BIOS').replace('Usb', 'USB')

    subcategories = []
    first_post = posts.items[0] if posts.items else None
    parent_category = first_post.category_str if first_post and first_post.category_str else ''
    if first_post and first_post.category_str:
        sibling_rows = db.session.query(Post.subcategory).filter(
            Post.category_str == first_post.category_str,
            Post.subcategory.isnot(None),
            Post.subcategory != ''
        ).distinct().all()
        subcategories = [row[0] for row in sibling_rows if row[0]]

    if not parent_category:
        prefix_map = {
            'bios': 'BIOS',
            'drivers': 'Drivers',
            'esquemas': 'Esquemas',
            'softwares': 'Softwares',
            'impressoras': 'Impressoras',
            'cursos': 'Cursos',
            'datasheet': 'Datasheet'
        }
        parent_category = prefix_map.get(subcategory.split('-', 1)[0].lower(), '')

    favorite_post_ids = set()
    if current_user.is_authenticated:
        favorite_post_ids = {f.post_id for f in Favorite.query.filter_by(user_id=current_user.id).all()}

    return render_template(
        'category.html',
        posts=posts,
        category=category_name,
        parent_category=parent_category,
        subcategory=subcategory,
        subcategories=subcategories,
        favorite_post_ids=favorite_post_ids,
        title=f'Subcategoria - {category_name}'
    )

@app.route('/post/<int:post_id>')
def post(post_id):
    """Rota antiga - redireciona para URL amigável"""
    post = Post.query.get_or_404(post_id)

    # Redirecionar para URL amigável
    if post.slug and post.category_str:
        category_slug = generate_slug(post.category_str)
        return redirect(url_for('post_by_slug', category=category_slug, slug=post.slug), code=301)

    # Se não tiver slug, continuar com a rota antiga
    increment_post_views(post_id)
    related_posts = get_related_posts_for_post(post, limit=9)
    comments = Comment.query.filter_by(
        post_id=post.id,
        is_approved=True
    ).order_by(Comment.date_posted.desc()).all()

    favorite_post_ids = []
    if current_user.is_authenticated:
        favorites = Favorite.query.filter_by(user_id=current_user.id).all()
        favorite_post_ids = [fav.post_id for fav in favorites]

    return render_template(
        'post.html',
        post=post,
        related_posts=related_posts,
        comments=comments,
        favorite_post_ids=favorite_post_ids,
        title=post.title
    )

@app.route('/<string:category>/<string:slug>')
def post_by_slug(category, slug):
    """Nova rota com URL amigável: /categoria/nome-do-post"""
    post = Post.query.filter_by(slug=slug).first_or_404()

    # Incrementar visualizações
    increment_post_views(post.id)

    # Obter posts relacionados baseados na categoria
    related_posts = get_related_posts_for_post(post, limit=9)

    # Obter comentários aprovados
    comments = Comment.query.filter_by(
        post_id=post.id,
        is_approved=True
    ).order_by(Comment.date_posted.desc()).all()

    # Obter IDs dos posts favoritos do usuário atual
    favorite_post_ids = []
    if current_user.is_authenticated:
        favorites = Favorite.query.filter_by(user_id=current_user.id).all()
        favorite_post_ids = [fav.post_id for fav in favorites]

    return render_template('post.html', post=post, related_posts=related_posts, comments=comments,
                         favorite_post_ids=favorite_post_ids, title=post.title)

def check_download_limit_legacy(user):
    """[DEPRECATED] Verifica se o usuário pode fazer download baseado no plano - Use check_user_download_limit()"""
    can_download, remaining, limit, reset_time, period = check_user_download_limit(user)
    if period == 'unlimited':
        return True, "Downloads ilimitados."
    if period == 'blocked':
        return False, "Downloads bloqueados para este usuário."
    if can_download:
        return True, f"Download autorizado. Você tem {int(remaining)} download(s) restante(s) nesta semana."

    reset_label = reset_time.strftime('%d/%m/%Y às %H:%M') if reset_time else 'data não informada'
    return False, f"Você atingiu seu limite de {int(limit)} download(s) semanais. Próximo reset: {reset_label}."

@app.route('/download/<int:post_id>')
@login_required
def download_post(post_id):
    """Wrapper legado: preserva URLs antigas e resolve um TechnicalFile."""
    post = Post.query.get_or_404(post_id)
    redirect_url = post.download_link
    download_files = post.get_metadata('download_files')
    selected_index = None
    selected_metadata = {}
    if isinstance(download_files, list) and download_files:
        file_index = request.args.get('file', type=int)
        download_type = request.args.get('type', '')
        if file_index is not None and 0 <= file_index < len(download_files):
            selected_index = file_index
            selected_metadata = download_files[file_index]
            redirect_url = selected_metadata.get('url', post.download_link)
        elif download_type:
            for index, download_file in enumerate(download_files):
                if download_file.get('type') == download_type:
                    selected_index = index
                    selected_metadata = download_file
                    redirect_url = download_file.get('url', post.download_link)
                    break
    redirect_url = normalize_download_url(redirect_url)
    if not redirect_url:
        flash('Link de download indisponível ou inválido para este post.', 'error')
        return redirect(url_for('post', post_id=post_id))

    # Posts novos já apontam para a rota canônica. O redirect continua interno
    # e o limite só será consumido uma vez na rota final.
    canonical_match = re.fullmatch(r'/download/file/(\d+)', redirect_url)
    if canonical_match:
        return redirect(url_for('download_technical_file', file_id=int(canonical_match.group(1))))

    technical_file = None
    persisted = TechnicalFile.query.filter_by(post_id=post.id, is_active=True).order_by(TechnicalFile.id.asc()).all()
    if redirect_url.startswith(('http://', 'https://')):
        technical_file = TechnicalFile.query.filter(
            TechnicalFile.post_id == post.id,
            db.or_(
                TechnicalFile.provider_direct_url == redirect_url,
                TechnicalFile.provider_url == redirect_url,
                TechnicalFile.source_url == redirect_url,
            ),
        ).first()
    if not technical_file and not selected_metadata and selected_index is not None and selected_index < len(persisted):
        technical_file = persisted[selected_index]
    if technical_file and selected_metadata:
        technical_file.file_type = normalize_download_file_type_label(
            selected_metadata.get('type') or technical_file.file_type or 'Outros'
        )[:80]
        technical_file.extension = sanitize_input(
            str(selected_metadata.get('format') or technical_file.extension or '')
        )[:30] or None
    if not technical_file:
        resource = TechnicalResource.query.filter_by(post_id=post.id).first()
        if not resource:
            resource = TechnicalResource(
                post_id=post.id,
                resource_type=generate_slug(selected_metadata.get('type') or post.file_type or 'other').replace('-', '_'),
                title=post.title,
                manufacturer=post.manufacturer,
                model=post.model,
                board_code=post.board_code,
                board_revision=post.board_revision,
                source_type='legacy',
                source_provider='Acervo legado',
                verification_status=post.verification_status,
                license_status='unknown',
                distribution_policy='external_storage_allowed',
            )
            db.session.add(resource)
            db.session.flush()
        technical_file = TechnicalFile(
            resource_id=resource.id,
            post_id=post.id,
            display_filename=sanitize_download_name(selected_metadata.get('name') or f'{post.slug or post.id}.{selected_metadata.get("format") or post.file_extension or "bin"}'),
            original_filename=sanitize_download_name(selected_metadata.get('name') or post.title),
            file_type=sanitize_input(str(selected_metadata.get('type') or post.file_type or 'Arquivo'))[:80],
            extension=sanitize_input(str(selected_metadata.get('format') or post.file_extension or ''))[:30] or None,
            sha256=normalize_sha256(selected_metadata.get('sha256')) if selected_metadata.get('sha256') else post.sha256,
            storage_provider='http',
            provider_url=redirect_url,
            provider_direct_url=redirect_url,
            source_provider='Acervo legado',
            link_status='unchecked',
            verification_status=post.verification_status,
            is_active=True,
        )
        db.session.add(technical_file)
        db.session.commit()
    return _deliver_technical_file(technical_file)


def _download_denied_response(remaining, limit, period, post_id):
    download_text = 'download' if limit == 1 else 'downloads'
    period_text = 'diários' if period == 'daily' else 'semanais' if period == 'weekly' else ''
    reset_text = 'à meia-noite' if period == 'daily' else 'no domingo às 00:00' if period == 'weekly' else ''
    message = f'Você atingiu o limite de {int(limit)} {download_text} {period_text}. Próximo reset {reset_text}.'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': False,
            'message': message,
            'can_download': False,
            'remaining': int(remaining) if remaining != float('inf') else 'unlimited',
            'limit': int(limit) if limit != float('inf') else 'unlimited',
        }), 403
    flash(message, 'warning')
    return redirect(url_for('post', post_id=post_id))


def _record_successful_download(technical_file, period, http_status=None):
    user = current_user
    post = technical_file.post
    db.session.add(Download(
        user_id=user.id,
        post_id=post.id,
        technical_file_id=technical_file.id,
        resource_id=technical_file.resource_id,
        plan_snapshot=user.plan,
        timestamp=datetime.utcnow(),
    ))
    if period == 'weekly':
        user.weekly_downloads = (user.weekly_downloads or 0) + 1
    elif period == 'daily':
        user.daily_downloads = (user.daily_downloads or 0) + 1
    technical_file.link_status = 'online'
    technical_file.last_link_check_at = datetime.utcnow()
    technical_file.last_link_http_status = http_status
    db.session.commit()
    increment_post_downloads(post.id)
    try:
        log_admin_activity(
            user_id=user.id,
            action='file_downloaded',
            description=f'Download do arquivo: {post.title}',
            metadata={
                'post_id': post.id,
                'technical_file_id': technical_file.id,
                'resource_id': technical_file.resource_id,
                'plan': user.plan,
            },
        )
    except Exception:
        pass


def _deliver_technical_file(technical_file):
    if not technical_file or not technical_file.is_active or not technical_file.post or not technical_file.post.is_active:
        abort(404)
    can_download, remaining, limit, _reset_time, period = check_user_download_limit(current_user)
    if not can_download:
        return _download_denied_response(remaining, limit, period, technical_file.post_id)

    filename = sanitize_download_name(technical_file.display_filename)
    if technical_file.storage_provider == 'local':
        storage_root = os.path.abspath(app.config['TECHNICAL_LOCAL_STORAGE_DIR'])
        local_path = os.path.abspath(os.path.join(storage_root, technical_file.provider_file_id or ''))
        if os.path.commonpath([storage_root, local_path]) != storage_root or not os.path.isfile(local_path):
            technical_file.link_status = 'broken'
            technical_file.last_link_check_at = datetime.utcnow()
            db.session.commit()
            abort(404)
        _record_successful_download(technical_file, period, http_status=200)
        return send_file(
            local_path,
            as_attachment=True,
            download_name=filename,
            mimetype=technical_file.mime_type or 'application/octet-stream',
            conditional=True,
            etag=True,
        )

    provider_url = technical_file.provider_direct_url or technical_file.provider_url
    if not provider_url:
        abort(404)
    if app.config.get('DOWNLOAD_DELIVERY_MODE') == 'redirect':
        _record_successful_download(technical_file, period)
        return redirect(provider_url)

    allowed_hosts = {
        host.strip().lower()
        for host in os.environ.get('STORAGE_ALLOWED_HOSTS', '').split(',')
        if host.strip()
    }
    storage = HttpStorageProvider(
        allowed_hosts=allowed_hosts,
        connect_timeout=float(os.environ.get('STORAGE_CONNECT_TIMEOUT', '5')),
        read_timeout=float(os.environ.get('STORAGE_READ_TIMEOUT', '45')),
    )
    try:
        upstream = storage.open(provider_url, request.headers.get('Range'))
    except StorageError as exc:
        technical_file.link_status = 'broken'
        technical_file.last_link_check_at = datetime.utcnow()
        technical_file.last_link_http_status = exc.status_code
        db.session.commit()
        app.logger.warning('Falha no storage do arquivo técnico %s: %s', technical_file.id, exc)
        message = 'Não foi possível iniciar este download no momento. Tente novamente em instantes.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': message}), 502
        flash(message, 'error')
        return redirect(url_for('post', post_id=technical_file.post_id))

    headers = dict(upstream.headers)
    upstream_filename = filename_from_content_disposition(headers.pop('Content-Disposition', None))
    if upstream_filename:
        filename = upstream_filename
        technical_file.display_filename = upstream_filename
        technical_file.original_filename = upstream_filename
    _record_successful_download(technical_file, period, http_status=upstream.status_code)
    ascii_filename = filename.encode('ascii', 'ignore').decode('ascii') or 'arquivo-tecnico'
    headers['Content-Disposition'] = (
        f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{quote(filename, safe="")}'
    )
    headers['X-Content-Type-Options'] = 'nosniff'
    headers['Cache-Control'] = 'private, no-store'
    response = Response(upstream.iterator, status=upstream.status_code, headers=headers, direct_passthrough=True)
    response.call_on_close(upstream.close)
    return response


@app.route('/download/file/<int:file_id>')
@login_required
def download_technical_file(file_id):
    return _deliver_technical_file(TechnicalFile.query.get_or_404(file_id))


# ====================
# ROTAS DE COMENTÁRIOS
# ====================

@app.route('/<string:category>/<string:slug>/comments', methods=['GET'])
def get_post_comments_by_slug(category, slug):
    """Retorna os comentários aprovados de um post específico usando slug"""
    try:
        # Buscar post pelo slug
        post = Post.query.filter_by(slug=slug).first_or_404()

        # Buscar apenas comentários aprovados
        comments = Comment.query.filter_by(
            post_id=post.id,
            is_approved=True
        ).order_by(Comment.date_posted.desc(), Comment.id.desc()).all()

        comments_list = serialize_comment_thread(comments)

        return jsonify({
            'success': True,
            'comments': comments_list,
            'count': len(comments)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao carregar comentários: {str(e)}'
        }), 500


@app.route('/post/<int:post_id>/comments', methods=['GET'])
def get_post_comments(post_id):
    """Retorna os comentários aprovados de um post específico (rota legada)"""
    try:
        # Verifica se o post existe (lança 404 se não existir)
        Post.query.get_or_404(post_id)

        # Buscar apenas comentários aprovados
        comments = Comment.query.filter_by(
            post_id=post_id,
            is_approved=True
        ).order_by(Comment.date_posted.desc(), Comment.id.desc()).all()

        comments_list = serialize_comment_thread(comments)

        return jsonify({
            'success': True,
            'comments': comments_list,
            'count': len(comments)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao carregar comentários: {str(e)}'
        }), 500


@app.route('/<string:category>/<string:slug>/comments', methods=['POST'])
def add_post_comment_by_slug(category, slug):
    """Adiciona um novo comentário a um post específico usando slug"""
    try:
        # Buscar post pelo slug
        post = Post.query.filter_by(slug=slug).first_or_404()

        # Obter e validar dados do formulário
        data = request.get_json(silent=True) if request.is_json else request.form
        if request.is_json and not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'JSON inválido'}), 400
        is_valid, error_message, validated_data = validate_comment_data(data)

        if not is_valid:
            if request_prefers_json_response():
                return jsonify({
                    'success': False,
                    'message': error_message
                }), 400
            flash(error_message or 'Não foi possível validar o comentário.', 'error')
            return redirect_back_to_post(post)

        # Type guard: garantir que validated_data não é None após validação bem-sucedida
        assert validated_data is not None, "validated_data should not be None when is_valid is True"

        parent_id = None
        raw_parent_id = str((data or {}).get('parent_id', '')).strip() if data else ''
        if raw_parent_id:
            if not raw_parent_id.isdigit():
                return jsonify({'success': False, 'message': 'Comentário pai inválido.'}), 400
            parent_comment = Comment.query.filter_by(id=int(raw_parent_id), post_id=post.id).first()
            if parent_comment is None:
                return jsonify({'success': False, 'message': 'Comentário pai não encontrado.'}), 404
            parent_id = parent_comment.id

        # Se usuário estiver logado, usar seus dados
        if current_user.is_authenticated:
            # Verificar limite de comentários baseado no plano
            allowed, message = check_comment_limit(current_user)
            if not allowed:
                if request_prefers_json_response():
                    return jsonify({
                        'success': False,
                        'message': message
                    }), 403
                flash(message, 'warning')
                return redirect_back_to_post(post)

            new_comment = Comment(
                content=validated_data['content'],
                post_id=post.id,
                user_id=current_user.id,
                author_name=current_user.name or current_user.username,
                author_email=current_user.email,
                is_approved=True,  # Comentários de usuários logados são aprovados automaticamente
                parent_id=parent_id
            )
        else:
            # Validar nome e email para usuários não logados
            if not validated_data['author_name'] or not validated_data['author_email']:
                if request_prefers_json_response():
                    return jsonify({
                        'success': False,
                        'message': 'Nome e email são obrigatórios.'
                    }), 400
                flash('Nome e email são obrigatórios.', 'error')
                return redirect_back_to_post(post)

            new_comment = Comment(
                content=validated_data['content'],
                post_id=post.id,
                author_name=validated_data['author_name'],
                author_email=validated_data['author_email'],
                is_approved=False,  # Comentários de não logados precisam aprovação
                parent_id=parent_id
            )

        # Salvar no banco
        db.session.add(new_comment)
        db.session.commit()

        # Preparar resposta
        response_data = {
            'success': True,
            'message': 'Comentário enviado com sucesso!' if new_comment.is_approved else 'Comentário enviado! Aguarde aprovação.',
            'comment': {
                **serialize_comment(new_comment),
                'is_approved': new_comment.is_approved
            }
        }

        if request_prefers_json_response():
            return jsonify(response_data), 201

        flash(response_data['message'], 'success' if new_comment.is_approved else 'info')
        return redirect_back_to_post(post)

    except Exception as e:
        db.session.rollback()
        if request_prefers_json_response():
            return jsonify({
                'success': False,
                'message': f'Erro ao adicionar comentário: {str(e)}'
            }), 500
        flash('Erro ao adicionar comentário. Tente novamente.', 'error')
        return redirect_back_to_post(post if 'post' in locals() else None)


@app.route('/<string:category>/<string:slug>/comments/<int:comment_id>', methods=['DELETE'])
@login_required
@editor_required
def delete_comment_by_slug(category, slug, comment_id):
    """Deleta um comentário (admins e editores)"""
    try:
        # Buscar post pelo slug
        post = Post.query.filter_by(slug=slug).first_or_404()

        # Buscar comentário
        comment = Comment.query.filter_by(id=comment_id, post_id=post.id).first_or_404()

        db.session.delete(comment)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Comentário deletado com sucesso!'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro ao deletar comentário: {str(e)}'
        }), 500


@app.route('/<string:category>/<string:slug>/comments/<int:comment_id>', methods=['PUT'])
@login_required
def edit_comment_by_slug(category, slug, comment_id):
    """Edita um comentário (apenas autor ou admin)"""
    try:
        # Buscar post pelo slug
        post = Post.query.filter_by(slug=slug).first_or_404()

        # Buscar comentário
        comment = Comment.query.filter_by(id=comment_id, post_id=post.id).first_or_404()

        # Verificar permissão: apenas o autor, admin ou editor pode editar
        if comment.user_id != current_user.id and current_user.role not in ('admin', 'editor'):
            return jsonify({
                'success': False,
                'message': 'Você não tem permissão para editar este comentário.'
            }), 403

        # Obter novo conteúdo
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'JSON inválido'}), 400
        new_content = data.get('content', '').strip()

        # Validações
        if not new_content:
            return jsonify({
                'success': False,
                'message': 'O comentário não pode estar vazio.'
            }), 400

        if len(new_content) < 3:
            return jsonify({
                'success': False,
                'message': 'O comentário deve ter pelo menos 3 caracteres.'
            }), 400

        if len(new_content) > 1000:
            return jsonify({
                'success': False,
                'message': 'O comentário não pode ter mais de 1000 caracteres.'
            }), 400

        # Sanitizar conteúdo para evitar XSS ao renderizar comentário editado
        new_content = sanitize_html(new_content)

        # Atualizar comentário
        comment.content = new_content
        comment.is_edited = True
        comment.date_edited = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Comentário editado com sucesso!',
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'is_edited': True,
                'date_edited': comment.date_edited.strftime('%d/%m/%Y %H:%M')
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro ao editar comentário: {str(e)}'
        }), 500


@app.route('/post/<int:post_id>/comments', methods=['POST'])
def add_post_comment(post_id):
    """Adiciona um novo comentário a um post específico (rota legada)"""
    try:
        post = Post.query.get_or_404(post_id)

        # Verifica se o post existe (lança 404 se não existir)
        data = request.get_json(silent=True) if request.is_json else request.form
        if request.is_json and not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'JSON inválido'}), 400
        is_valid, error_message, validated_data = validate_comment_data(data)

        if not is_valid:
            if request_prefers_json_response():
                return jsonify({
                    'success': False,
                    'message': error_message
                }), 400
            flash(error_message or 'Não foi possível validar o comentário.', 'error')
            return redirect_back_to_post(post)

        # Type guard: garantir que validated_data não é None após validação bem-sucedida
        assert validated_data is not None, "validated_data should not be None when is_valid is True"

        parent_id = None
        raw_parent_id = str((data or {}).get('parent_id', '')).strip() if data else ''
        if raw_parent_id:
            if not raw_parent_id.isdigit():
                return jsonify({'success': False, 'message': 'Comentário pai inválido.'}), 400
            parent_comment = Comment.query.filter_by(id=int(raw_parent_id), post_id=post_id).first()
            if parent_comment is None:
                return jsonify({'success': False, 'message': 'Comentário pai não encontrado.'}), 404
            parent_id = parent_comment.id

        # Se usuário estiver logado, usar seus dados
        if current_user.is_authenticated:
            # Verificar limite de comentários baseado no plano
            allowed, message = check_comment_limit(current_user)
            if not allowed:
                if request_prefers_json_response():
                    return jsonify({
                        'success': False,
                        'message': message
                    }), 403
                flash(message, 'warning')
                return redirect_back_to_post(post)

            new_comment = Comment(
                content=validated_data['content'],
                post_id=post_id,
                user_id=current_user.id,
                author_name=current_user.name or current_user.username,
                author_email=current_user.email,
                is_approved=True,  # Comentários de usuários logados são aprovados automaticamente
                parent_id=parent_id
            )
        else:
            # Validar nome e email para usuários não logados
            if not validated_data['author_name'] or not validated_data['author_email']:
                if request_prefers_json_response():
                    return jsonify({
                        'success': False,
                        'message': 'Nome e email são obrigatórios.'
                    }), 400
                flash('Nome e email são obrigatórios.', 'error')
                return redirect_back_to_post(post)

            new_comment = Comment(
                content=validated_data['content'],
                post_id=post_id,
                author_name=validated_data['author_name'],
                author_email=validated_data['author_email'],
                is_approved=False,  # Comentários de não logados precisam aprovação
                parent_id=parent_id
            )

        # Salvar no banco
        db.session.add(new_comment)
        db.session.commit()

        # Preparar resposta
        response_data = {
            'success': True,
            'message': 'Comentário enviado com sucesso!' if new_comment.is_approved else 'Comentário enviado! Aguarde aprovação.',
            'comment': {
                **serialize_comment(new_comment),
                'is_approved': new_comment.is_approved
            }
        }

        if request_prefers_json_response():
            return jsonify(response_data), 201

        flash(response_data['message'], 'success' if new_comment.is_approved else 'info')
        return redirect_back_to_post(post)

    except Exception as e:
        db.session.rollback()
        if request_prefers_json_response():
            return jsonify({
                'success': False,
                'message': f'Erro ao enviar comentário: {str(e)}'
            }), 500
        flash('Erro ao enviar comentário. Tente novamente.', 'error')
        return redirect_back_to_post(post if 'post' in locals() else None)


@app.route('/post/<int:post_id>/comments/<int:comment_id>', methods=['DELETE'])
@login_required
@editor_required
def delete_comment(post_id, comment_id):
    """Deleta um comentário via rota legada."""
    try:
        Post.query.get_or_404(post_id)
        comment = Comment.query.filter_by(id=comment_id, post_id=post_id).first_or_404()

        db.session.delete(comment)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Comentário deletado com sucesso!'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro ao deletar comentário: {str(e)}'
        }), 500


@app.route('/post/<int:post_id>/comments/<int:comment_id>', methods=['PUT'])
@login_required
def edit_comment(post_id, comment_id):
    """Edita um comentário via rota legada."""
    try:
        Post.query.get_or_404(post_id)
        comment = Comment.query.filter_by(id=comment_id, post_id=post_id).first_or_404()

        if comment.user_id != current_user.id and current_user.role not in ('admin', 'editor'):
            return jsonify({
                'success': False,
                'message': 'Você não tem permissão para editar este comentário.'
            }), 403

        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'JSON inválido'}), 400
        new_content = (data.get('content') or '').strip()

        if not new_content:
            return jsonify({
                'success': False,
                'message': 'O comentário não pode estar vazio.'
            }), 400

        if len(new_content) < 3:
            return jsonify({
                'success': False,
                'message': 'O comentário deve ter pelo menos 3 caracteres.'
            }), 400

        if len(new_content) > 1000:
            return jsonify({
                'success': False,
                'message': 'O comentário não pode ter mais de 1000 caracteres.'
            }), 400

        comment.content = sanitize_html(new_content)
        comment.is_edited = True
        comment.date_edited = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Comentário editado com sucesso!',
            'comment': serialize_comment(comment)
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro ao editar comentário: {str(e)}'
        }), 500


@app.route('/pesquisa')
def search():
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    filter_type = request.args.get('filter', 'all').strip()  # all, posts, categories, datasheets
    if filter_type not in {'all', 'posts', 'categories', 'datasheets'}:
        filter_type = 'all'

    if not query:
        # Se for requisição AJAX, retornar JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': 'Por favor, digite algo para pesquisar.'
            }), 400
        flash('Por favor, digite algo para pesquisar.', 'warning')
        return redirect(url_for('home'))

    # Busca inteligente: sugestão de correção usando similaridade
    from difflib import get_close_matches

    # Lista de termos conhecidos para sugestão
    all_categories = Category.query.filter_by(is_active=True, is_visible=True).all()
    category_names = [cat.name.lower() for cat in all_categories]
    all_posts = Post.query.filter_by(is_active=True).all()
    post_titles = [post.title.lower() for post in all_posts]
    all_components = ElectronicComponent.query.filter_by(is_published=True).all()
    component_terms = [
        term.lower()
        for component in all_components
        for term in (component.part_number, component.manufacturer, component.title_ptbr)
        if term
    ]
    known_terms = category_names + post_titles + component_terms

    # Buscar sugestão se não houver resultados exatos
    suggestion = None
    close_matches = get_close_matches(query.lower(), known_terms, n=1, cutoff=0.6)
    if close_matches and close_matches[0].lower() != query.lower():
        suggestion = close_matches[0]

    # Buscar categorias que correspondem à pesquisa (apenas se filter != 'posts')
    categories = []
    if filter_type in ['all', 'categories']:
        scored_categories = []
        for cat in Category.query.filter_by(is_active=True, is_visible=True).all():
            score = get_search_match_score(query, cat.name, cat.description, cat.slug)
            if score is not None:
                scored_categories.append((score, cat.name.casefold(), cat))

        categories = [cat for _score, _name, cat in sorted(scored_categories, key=lambda item: (item[0], item[1]))]

    # Buscar posts (apenas se filter != 'categories')
    posts = []
    if filter_type in ['all', 'posts']:
        posts_query = Post.query.filter_by(is_active=True)
        if category:
            posts_query = posts_query.filter(Post.category_str == category)

        scored_posts = []
        for post in posts_query.all():
            score = get_post_search_score(query, post)
            if score is not None:
                sort_date = post.date_posted or datetime.min
                scored_posts.append((score, -sort_date.toordinal(), post.title.casefold(), post))

        posts = [post for _score, _date, _title, post in sorted(scored_posts, key=lambda item: (item[0], item[1], item[2]))]

        debug_log(f"SEARCH Query: '{query}', Posts found: {len(posts)}")  # DEBUG

    components = []
    if filter_type in {'all', 'datasheets'}:
        scored_components = []
        for component in all_components:
            alias_values = ' '.join(alias.alias for alias in component.aliases)
            score = get_search_match_score(
                query,
                component.part_number,
                component.normalized_part_number,
                component.manufacturer,
                component.title_ptbr,
                component.category,
                component.package,
                alias_values,
            )
            if score is not None:
                scored_components.append((score, component.part_number.casefold(), component))
        components = [
            component
            for _score, _part, component in sorted(scored_components, key=lambda item: (item[0], item[1]))
        ]

    if not posts and not categories and not components and looks_like_part_number(query):
        normalized_query = normalize_component_part_number(query)
        demand = DatasheetDemand.query.filter_by(normalized_query=normalized_query).first()
        if demand:
            demand.request_count = (demand.request_count or 0) + 1
            demand.last_requested_at = datetime.utcnow()
        else:
            db.session.add(DatasheetDemand(
                normalized_query=normalized_query,
                display_query=query[:160],
                request_count=1,
            ))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()

    return render_template('search.html',
                         posts=posts,
                         categories=categories,
                         components=components,
                         query=query,
                         category=category,
                         filter_type=filter_type,
                         suggestion=suggestion,
                         title=f'Pesquisa: {query}')

@app.route('/sobre')
def about():
    stats = {
        'total_posts': Post.query.filter_by(is_active=True).count(),
        'total_downloads': db.session.query(db.func.sum(Post.downloads)).scalar() or 0,
        'total_users': User.query.filter_by(is_active=True).count(),
        'total_subscribers': Subscriber.query.filter_by(is_active=True).count(),
    }

    categories = Category.query.order_by(Category.name).all()
    for category in categories:
        stats[f'{category.slug}_count'] = Post.query.filter_by(category_id=category.id, is_active=True).count()

    return render_template('about.html',
                         title='Sobre',
                         about_stats=stats,
                         stats=stats)  # Para compatibilidade com o template stats.html

@app.route('/planos')
def plans():
    """Página de planos e preços"""
    requested_checkout = str(request.args.get('checkout') or '').strip().lower()
    checkout_plan = requested_checkout if requested_checkout in ('premium', 'vip') else ''
    return render_template('plans.html', title='Planos e Preços', stripe_public_key=app.config['STRIPE_PUBLIC_KEY'], checkout_plan=checkout_plan)


@app.route('/api/plan-prices')
def api_plan_prices():
    """Retorna precos e disponibilidade para atualizacao dinamica dos planos."""
    pricing = get_plan_pricing_config()
    response = jsonify({
        'success': True,
        'plans': {
            plan_key: {
                'label': plan_data['label'],
                'amount_cents': plan_data['amount_cents'],
                'display_amount': plan_data['display_amount'],
                'display_full': f"R$ {plan_data['display_amount']}",
                'enabled': bool(plan_data['enabled']),
                'card_enabled': bool(plan_data['card_enabled']),
                'pix_enabled': bool(plan_data['pix_enabled']),
            }
            for plan_key, plan_data in pricing.items()
        }
    })
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response


@app.route('/api/site-settings')
def api_site_settings():
    """Snapshot público para sincronizar a aparência e os contatos sem reload."""
    response = jsonify({
        'success': True,
        'settings': get_live_site_settings(),
    })
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response


@app.route('/api/public-content-version')
def api_public_content_version():
    """Versão compacta do acervo para atualizar páginas públicas sem recarregar o site."""
    posts_snapshot = [
        {
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'category_id': post.category_id,
            'category_str': post.category_str,
            'subcategory': post.subcategory,
            'is_active': bool(post.is_active),
            'featured': bool(post.featured),
            'image_url': post.image_url,
            'download_link': post.download_link,
            'tags': post.tags,
            'slug': post.slug,
            'metadata': post.custom_metadata,
            'verification_status': post.verification_status,
            'updated_at': post.date_updated.isoformat() if post.date_updated else None,
        }
        for post in Post.query.order_by(Post.id.asc()).all()
    ]
    categories_snapshot = [
        {
            'id': category.id,
            'name': category.name,
            'slug': category.slug,
            'description': category.description,
            'icon': category.icon,
            'color': category.color,
            'is_active': bool(category.is_active),
            'is_visible': bool(category.is_visible),
            'show_in_menu': bool(category.show_in_menu),
            'order': category.order,
        }
        for category in Category.query.order_by(Category.id.asc()).all()
    ]
    raw_snapshot = json.dumps(
        {'posts': posts_snapshot, 'categories': categories_snapshot},
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    )
    response = jsonify({
        'success': True,
        'version': hashlib.sha256(raw_snapshot.encode('utf-8')).hexdigest(),
    })
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response


@app.route('/api/user/permissions')
@login_required
def get_user_permissions():
    """Retorna as permissões e limites do usuário baseado no plano"""
    user = current_user
    entitlements = get_plan_entitlements(user)

    # Calcular downloads restantes
    can_download, remaining, download_limit, reset_time, download_period = check_user_download_limit(user)
    if download_period == 'unlimited':
        downloads_info = {
            'limit': 'ilimitado',
            'period': 'sempre',
            'used': 0,
            'remaining': 'ilimitado',
            'can_download': True,
            'reset_time': None,
        }
    else:
        used = (user.weekly_downloads or 0) if download_period == 'weekly' else (user.daily_downloads or 0)
        downloads_info = {
            'limit': int(download_limit),
            'period': 'semana' if download_period == 'weekly' else 'dia',
            'used': used,
            'remaining': int(remaining),
            'can_download': can_download,
            'reset_time': reset_time.isoformat() if reset_time else None,
        }

    # Calcular comentários restantes hoje
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    comments_today = Comment.query.filter(
        Comment.user_id == user.id,
        Comment.date_posted >= today_start
    ).count()

    comment_limit = entitlements['comments_limit']
    if comment_limit is None:
        comments_info = {
            'allowed': True,
            'limit': 'ilimitado',
            'used': comments_today,
            'remaining': 'ilimitado'
        }
    else:
        comments_info = {
            'allowed': comments_today < comment_limit,
            'limit': comment_limit,
            'used': comments_today,
            'remaining': max(0, comment_limit - comments_today)
        }

    # Favoritos
    favorites_count = Favorite.query.filter_by(user_id=user.id).count()
    favorite_limit = entitlements['favorites_limit']
    if favorite_limit is not None:
        favorites_info = {
            'limit': favorite_limit,
            'used': favorites_count,
            'remaining': max(0, favorite_limit - favorites_count)
        }
    else:
        favorites_info = {
            'limit': 'ilimitado',
            'used': favorites_count,
            'remaining': 'ilimitado'
        }

    # Histórico de downloads
    history_access, history_limit = check_download_history_access(user)

    permissions = {
        'plan': user.plan,
        'plan_name': get_plan_metadata(user.plan)['label'],
        'downloads': downloads_info,
        'comments': comments_info,
        'favorites': favorites_info,
        'download_history': {
            'access': history_access,
            'limit': history_limit if history_limit else ('completo' if history_access else 'nenhum')
        },
        'support': check_support_priority(user),
        'devices': {
            'limit': entitlements['device_limit'],
            'active': user.active_sessions
        },
        'can_request_content': can_request_specific_content(user),
        'vip_area': entitlements['vip_area'],
        'live_chat': {
            'community': _can_user_write_public_chat(user),
            'support': True
        }
    }

    return jsonify(permissions)

@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'error': 'JSON inválido'}), 400
        if not data:
            return jsonify({'error': 'Dados inválidos'}), 400
        plan_type = data.get('plan')

        if not plan_type:
            return jsonify({'error': 'Plano é obrigatório'}), 400

        debug_log(f'Stripe Checkout - Dados recebidos: {data}')
        debug_log(f'Stripe Checkout - Plano: {plan_type}')

        plan_key = normalize_plan_key(plan_type)
        if plan_key not in DEFAULT_PLAN_PRICE_CENTS:
            debug_log(f'Stripe Checkout - Plano inválido: {plan_type}')
            return jsonify({'error': 'Plano inválido'}), 400

        if not is_plan_enabled(plan_key):
            return jsonify({'error': 'Este plano está temporariamente indisponível para novas assinaturas.'}), 409

        if not is_plan_payment_method_enabled(plan_key, 'card'):
            return jsonify({'error': 'A assinatura por cartão está temporariamente indisponível para este plano.'}), 409

        amount_cents = get_plan_price_cents(plan_key)
        if amount_cents <= 0:
            return jsonify({'error': 'Preço do plano inválido. Ajuste o valor no painel administrativo.'}), 400

        product_id = get_stripe_product_id_for_plan(plan_key)
        price_data: stripe.checkout.Session.CreateParamsLineItemPriceData = {
            'currency': 'brl',
            'unit_amount': amount_cents,
            'recurring': {'interval': 'month'},
        }
        if product_id:
            price_data['product'] = product_id
        else:
            metadata = get_plan_metadata(plan_key)
            price_data['product_data'] = {
                'name': f"Plano {metadata['label']} - Mundo da Informática",
                'description': 'Assinatura mensal da plataforma Mundo da Informática.',
            }

        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price_data': price_data,
                    'quantity': 1,
                },
            ],
            ui_mode='embedded',  # Modo embutido
            mode='subscription',
            payment_method_types=['card'],  # Apenas cartão de crédito
            return_url=url_for('checkout_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            customer_email=current_user.email,
            metadata={
                'user_id': str(current_user.id),
                'plan': plan_key
            }
        )
        return jsonify({'clientSecret': checkout_session.client_secret})
    except Exception as e:
        app.logger.exception('Erro ao criar sessão de checkout Stripe')
        return jsonify({'error': 'Erro interno do servidor'}), 500


@app.route('/create-donation-checkout-session', methods=['POST'])
@login_required
def create_donation_checkout_session():
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'error': 'JSON inválido'}), 400

        ok, amount_cents, error_message = parse_donation_amount_to_cents(data.get('amount'))
        if not ok or amount_cents is None:
            return jsonify({'error': error_message or 'Valor inválido.'}), 400

        next_path = get_safe_internal_path(data.get('next') or request.referrer, fallback=url_for('about'))
        checkout_session = stripe.checkout.Session.create(
            mode='payment',
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'brl',
                        'unit_amount': amount_cents,
                        'product_data': {
                            'name': 'Doacao para o Mundo da Informatica',
                            'description': 'Contribuição avulsa para apoiar a plataforma.'
                        }
                    },
                    'quantity': 1
                }
            ],
            success_url=url_for('donation_success', _external=True) + f'?session_id={{CHECKOUT_SESSION_ID}}&next={quote(next_path)}',
            cancel_url=url_for('about', _external=True) if next_path == url_for('about') else request.host_url.rstrip('/') + next_path,
            customer_email=current_user.email,
            metadata={
                'user_id': str(current_user.id),
                'plan': 'donation',
                'next': next_path
            }
        )

        transaction = Transaction(
            user_id=current_user.id,
            payment_gateway='stripe',
            stripe_session_id=checkout_session.id,
            stripe_payment_intent_id=checkout_session.payment_intent,
            plan_type='donation',
            amount=amount_cents,
            currency='brl',
            status='pending'
        )
        db.session.add(transaction)
        db.session.commit()

        return jsonify({'success': True, 'url': checkout_session.url})
    except Exception:
        db.session.rollback()
        app.logger.exception('Erro ao criar sessao de doacao Stripe')
        return jsonify({'error': 'Erro interno do servidor'}), 500

@app.route('/checkout-success')
@login_required
def checkout_success():
    session_id = request.args.get('session_id')
    if not session_id:
        flash('Erro: Sessão de pagamento não encontrada.', 'danger')
        return redirect(url_for('plans'))

    try:
        # Retrieve the session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)

        # Verificar se já existe uma transação registrada para esta sessão
        existing_transaction = Transaction.query.filter_by(stripe_session_id=session_id).first()

        # Check if the payment was successful
        if session.payment_status == 'paid':
            plan_type = session.metadata.get('plan')

            if plan_type in ['premium', 'vip']:
                # Atualizar usuário apenas se ainda não foi processado
                if current_user.plan == 'free' or not existing_transaction or existing_transaction.status != 'completed':
                    current_user.plan = plan_type
                    # Set expiration to exactly 1 month from now
                    current_user.subscription_end_date = datetime.utcnow() + relativedelta(months=1)

                    # Criar ou atualizar registro de transação
                    if not existing_transaction:
                        transaction = Transaction(
                            user_id=current_user.id,
                            stripe_session_id=session_id,
                            stripe_customer_id=session.customer,
                            stripe_subscription_id=session.subscription,
                            plan_type=plan_type,
                            amount=session.amount_total,
                            currency=session.currency,
                            status='completed',
                            paid_at=datetime.utcnow()
                        )
                        db.session.add(transaction)
                    else:
                        existing_transaction.status = 'completed'
                        existing_transaction.paid_at = datetime.utcnow()

                    db.session.commit()
                    flash(f'Assinatura {plan_type.upper()} realizada com sucesso! Bem-vindo ao seu novo plano.', 'success')
                else:
                    flash('Sua assinatura já está ativa!', 'info')
            else:
                flash('Erro: Plano desconhecido na confirmação do pagamento.', 'warning')
        else:
            flash('O pagamento ainda não foi confirmado. Aguarde alguns instantes ou entre em contato com o suporte.', 'warning')

    except Exception:
        app.logger.exception('Erro ao verificar pagamento Stripe')
        flash('Não foi possível verificar o pagamento agora. Tente novamente em instantes.', 'danger')

    return redirect(url_for('plans'))


@app.route('/donation-success')
@login_required
def donation_success():
    session_id = request.args.get('session_id')
    next_path = get_safe_internal_path(request.args.get('next'), fallback=url_for('about'))

    if not session_id:
        flash('Sessão de doação não encontrada.', 'warning')
        return redirect(next_path)

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status != 'paid' or session.metadata.get('plan') != 'donation':
            flash('A doação ainda não foi confirmada.', 'warning')
            return redirect(next_path)

        transaction = Transaction.query.filter_by(stripe_session_id=session_id).first()
        if transaction:
            transaction.status = 'completed'
            transaction.paid_at = datetime.utcnow()
            transaction.amount = session.amount_total or transaction.amount
            transaction.currency = session.currency or transaction.currency
        else:
            transaction = Transaction(
                user_id=current_user.id,
                payment_gateway='stripe',
                stripe_session_id=session_id,
                stripe_customer_id=session.customer,
                stripe_payment_intent_id=session.payment_intent,
                plan_type='donation',
                amount=session.amount_total or 0,
                currency=session.currency or 'brl',
                status='completed',
                paid_at=datetime.utcnow()
            )
            db.session.add(transaction)

        db.session.commit()
        flash('Doação realizada com sucesso. Muito obrigado pelo apoio!', 'success')
    except Exception:
        db.session.rollback()
        app.logger.exception('Erro ao confirmar doacao Stripe')
        flash('Não foi possível confirmar a doação agora. Tente novamente em instantes.', 'danger')

    return redirect(next_path)

@app.route('/checkout-cancel')
@login_required
def checkout_cancel():
    flash('O processo de assinatura foi cancelado.', 'info')
    return redirect(url_for('plans'))

@app.route('/create-pix-checkout', methods=['POST'])
@login_required
def create_pix_checkout():
    """
    Cria um QR Code PIX via Abacate Pay - Redirecionamento Assíncrono
    """
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'error': 'JSON inválido'}), 400
        if not data:
            return jsonify({'error': 'Dados inválidos'}), 400
        plan_type = data.get('plan')

        if not plan_type:
            return jsonify({'error': 'Plano é obrigatório'}), 400

        plan_key = normalize_plan_key(plan_type)
        if plan_key not in DEFAULT_PLAN_PRICE_CENTS:
            app.logger.warning('Tentativa de checkout PIX com plano invalido')
            return jsonify({'error': 'Plano inválido'}), 400

        if not is_plan_enabled(plan_key):
            return jsonify({'error': 'Este plano está temporariamente indisponível para novas assinaturas.'}), 409

        if not is_plan_payment_method_enabled(plan_key, 'pix'):
            return jsonify({'error': 'O pagamento via PIX está temporariamente indisponível para este plano.'}), 409

        amount = get_plan_price_cents(plan_key)
        if amount <= 0:
            app.logger.error('Preco PIX invalido para o plano %s', plan_key)
            return jsonify({'error': 'Preço do plano inválido. Ajuste o valor visual no painel administrativo.'}), 400

        # Gerar ID único para o PIX
        pix_id = f'{plan_key}_{current_user.id}_{int(datetime.utcnow().timestamp())}'

        # Criar transação pendente IMEDIATAMENTE para redirecionamento rápido
        try:
            transaction = Transaction(
                user_id=current_user.id,
                payment_gateway='abacatepay',
                abacatepay_billing_id=pix_id,
                plan_type=plan_key,
                amount=amount,
                currency='brl',
                status='processing'  # Status temporário até API responder
            )
            db.session.add(transaction)
            db.session.commit()

        except Exception:
            db.session.rollback()
            app.logger.exception('Erro ao salvar transacao PIX')
            return jsonify({'error': 'Erro ao salvar transação'}), 500

        # Retornar imediatamente para redirecionamento rápido
        # O processamento da API será feito em background
        redirect_url = url_for('pix_checkout_page', billing_id=pix_id, _external=True)

        return jsonify({
            'billing_id': pix_id,
            'transaction_id': transaction.id,
            'redirect_url': redirect_url,
            'success_redirect_url': url_for('pix_checkout_success', billing_id=pix_id, next=url_for('plans'))
        })

    except Exception:
        app.logger.exception('Erro geral ao criar checkout PIX')
        return jsonify({'error': 'Erro interno do servidor'}), 500


@app.route('/create-donation-pix-checkout', methods=['POST'])
@login_required
def create_donation_pix_checkout():
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'error': 'JSON inválido'}), 400

        ok, amount_cents, error_message = parse_donation_amount_to_cents(data.get('amount'))
        if not ok or amount_cents is None:
            return jsonify({'error': error_message or 'Valor inválido.'}), 400

        next_path = get_safe_internal_path(data.get('next') or request.referrer, fallback=url_for('about'))
        pix_id = f'donation_{current_user.id}_{int(datetime.utcnow().timestamp())}'

        transaction = Transaction(
            user_id=current_user.id,
            payment_gateway='abacatepay',
            abacatepay_billing_id=pix_id,
            plan_type='donation',
            amount=amount_cents,
            currency='brl',
            status='processing',
            abacatepay_payment_url=next_path
        )
        db.session.add(transaction)
        db.session.commit()

        return jsonify({
            'success': True,
            'billing_id': pix_id,
            'transaction_id': transaction.id,
            'redirect_url': url_for('pix_checkout_page', billing_id=pix_id, next=next_path, _external=True),
            'success_redirect_url': url_for('pix_checkout_success', billing_id=pix_id, next=next_path)
        })
    except Exception:
        db.session.rollback()
        app.logger.exception('Erro ao criar checkout PIX de doacao')
        return jsonify({'error': 'Erro interno do servidor'}), 500


@app.route('/process-pix-async/<billing_id>', methods=['POST'])
@login_required
def process_pix_async(billing_id):
    """
    Processa a criação do QR Code PIX em background
    """
    try:
        transaction = Transaction.query.filter_by(
            abacatepay_billing_id=billing_id,
            user_id=current_user.id
        ).first()

        if not transaction:
            return jsonify({'error': 'Transação não encontrada'}), 404

        # Se já foi processado, retornar os dados salvos sem criar uma nova cobrança.
        if transaction.status in ['pending', 'completed'] and (transaction.abacatepay_qr_code or transaction.abacatepay_pix_code):
            return jsonify({
                'status': 'success',
                'charge_id': transaction.abacatepay_charge_id,
                'qr_code': transaction.abacatepay_qr_code,
                'pix_code': transaction.abacatepay_pix_code
            })

        # Se foi cancelado, retornar erro
        if transaction.status == 'cancelled':
            return jsonify({'error': 'Transação foi cancelada'}), 400

        plan_type = transaction.plan_type
        amount = transaction.amount

        description = 'Doacao para o Mundo da Informatica' if plan_type == 'donation' else f'Plano {plan_type.upper()}'
        payload_data = {
            'amount': amount,
            'expiresIn': 3600,
            'description': description,
            'externalId': billing_id,
            'metadata': {
                'externalId': billing_id,
                'transaction_id': str(transaction.id),
                'user_id': str(current_user.id),
                'plan': plan_type
            }
        }

        payload = {
            'method': 'PIX',
            'data': payload_data
        }

        debug_log(f'Processando PIX async para billing_id: {billing_id}')

        try:
            pix_data = abacatepay_request('POST', '/transparents/create', json=payload)
            pix_charge_id = pix_data.get('id')
            pix_code = pix_data.get('brCode')
            qr_code_base64 = pix_data.get('brCodeBase64')

            if not pix_charge_id or not (pix_code or qr_code_base64):
                raise AbacatePayAPIError('Resposta da AbacatePay sem dados do PIX.')

            transaction.abacatepay_charge_id = pix_charge_id
            transaction.abacatepay_qr_code = qr_code_base64
            transaction.abacatepay_pix_code = pix_code
            transaction.status = 'pending'
            db.session.commit()

            debug_log(f'PIX QR Code criado com sucesso: {pix_charge_id}')

            return jsonify({
                'status': 'success',
                'charge_id': pix_charge_id,
                'qr_code': qr_code_base64,
                'pix_code': pix_code
            })

        except AbacatePayAPIError as e:
            debug_log(f'Erro ao processar PIX async: {str(e)}')
            transaction.status = 'failed'
            db.session.commit()
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 400
        except Exception as e:
            debug_log(f'Erro ao processar PIX async: {str(e)}')
            transaction.status = 'failed'
            db.session.commit()
            return jsonify({
                'status': 'error',
                'message': 'Erro ao processar pagamento PIX.'
            }), 500

    except Exception as e:
        debug_log(f'Erro geral no process_pix_async: {str(e)}')
        import traceback
        debug_log(traceback.format_exc())
        return jsonify({'error': 'Erro interno do servidor'}), 500


@app.route('/pix-checkout/<billing_id>')
@login_required
def pix_checkout_page(billing_id):
    """
    Página de checkout PIX com QR Code
    """
    transaction = Transaction.query.filter_by(
        abacatepay_billing_id=billing_id,
        user_id=current_user.id
    ).first_or_404()

    return render_template('pix_checkout.html',
                         transaction=transaction,
                         billing_id=billing_id,
                         return_path=get_safe_internal_path(
                             request.args.get('next') or transaction.abacatepay_payment_url,
                             fallback=url_for('about' if transaction.plan_type == 'donation' else 'plans')
                         ))

@app.route('/pix-checkout-error/<int:transaction_id>')
@login_required
def pix_checkout_error(transaction_id):
    """
    Página de erro de checkout PIX
    """
    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id
    ).first_or_404()

    return render_template('pix_checkout_error.html', transaction=transaction)

@app.route('/pix-checkout-success')
@login_required
def pix_checkout_success():
    """
    Página de sucesso após pagamento PIX
    """
    billing_id = request.args.get('billing_id')
    transaction = None

    if billing_id:
        transaction = Transaction.query.filter_by(
            abacatepay_billing_id=billing_id,
            user_id=current_user.id
        ).first()

        if transaction and transaction.status == 'completed':
            if transaction.plan_type == 'donation':
                flash('Doação realizada com sucesso via PIX. Muito obrigado pelo apoio!', 'success')
            else:
                flash(f'Assinatura {transaction.plan_type.upper()} realizada com sucesso via PIX!', 'success')
        else:
            if transaction and transaction.plan_type == 'donation':
                flash('Aguardando confirmação da doação PIX. Você receberá a atualização assim que o pagamento for processado.', 'info')
            else:
                flash('Aguardando confirmação do pagamento PIX. Você receberá uma notificação quando for processado.', 'info')
    else:
        flash('Pagamento PIX em processamento.', 'info')

    fallback_endpoint = 'plans'
    if billing_id and transaction and transaction.plan_type == 'donation':
        fallback_endpoint = 'about'
    return redirect(get_safe_internal_path(request.args.get('next'), fallback=url_for(fallback_endpoint)))

@app.route('/cancel-pix-transaction/<billing_id>', methods=['POST'])
@login_required
def cancel_pix_transaction(billing_id):
    """
    Cancela uma transação PIX quando o usuário abandona a página
    """
    try:
        transaction = Transaction.query.filter_by(
            abacatepay_billing_id=billing_id,
            user_id=current_user.id
        ).first()

        if not transaction:
            return jsonify({'status': 'not_found'}), 404

        # Cancelar apenas se ainda está em processamento ou pendente
        if transaction.status in ['processing', 'pending']:
            transaction.status = 'cancelled'
            db.session.commit()
            debug_log(f'Transação {billing_id} cancelada pelo usuário ao sair da página')
            return jsonify({'status': 'cancelled'}), 200

        return jsonify({'status': transaction.status}), 200

    except Exception as e:
        debug_log(f'Erro ao cancelar transação: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/check-pix-payment/<billing_id>')
@login_required
def check_pix_payment(billing_id):
    """
    Verifica o status do pagamento PIX
    """
    try:
        transaction = Transaction.query.filter_by(
            abacatepay_billing_id=billing_id,
            user_id=current_user.id
        ).first()

        if not transaction:
            return jsonify({'status': 'not_found'}), 404

        # Se a transação foi cancelada, parar polling
        if transaction.status == 'cancelled':
            return jsonify({
                'status': 'cancelled',
                'paid': False,
                'stop_polling': True
            })

        remote_id = get_abacatepay_remote_id(transaction)
        remote_status = None
        if remote_id and transaction.status in ['processing', 'pending']:
            try:
                charge_data = abacatepay_request('GET', '/transparents/check', params={'id': remote_id})
                remote_status = charge_data.get('status')
                sync_abacatepay_transaction_status(transaction, charge_data)
            except AbacatePayAPIError as e:
                debug_log(f'Erro ao consultar status AbacatePay: {str(e)}')

        return jsonify({
            'status': transaction.status,
            'remote_status': remote_status,
            'paid': transaction.status == 'completed',
            'stop_polling': transaction.status in ['failed', 'refunded', 'cancelled']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/stripe-webhook', methods=['POST'])
@csrf.exempt
def stripe_webhook():
    """
    Webhook do Stripe para processar eventos de pagamento automaticamente.
    Este é o método RECOMENDADO e mais seguro para processar pagamentos.

    Configure este endpoint no Dashboard do Stripe:
    https://dashboard.stripe.com/webhooks

    Eventos importantes:
    - checkout.session.completed: Sessão de checkout concluída
    - customer.subscription.created: Assinatura criada
    - customer.subscription.updated: Assinatura atualizada
    - customer.subscription.deleted: Assinatura cancelada
    - invoice.payment_succeeded: Pagamento de fatura bem-sucedido
    - invoice.payment_failed: Falha no pagamento
    """
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

    is_production = is_production_environment()

    if not webhook_secret:
        debug_log('AVISO: STRIPE_WEBHOOK_SECRET não configurado! Webhook não pode verificar assinatura.')
        # Em produção, você DEVE rejeitar webhooks sem verificação
        if is_production:
            return jsonify({'error': 'Webhook secret not configured'}), 500

    try:
        # Verificar assinatura antes de persistir ou processar o evento.
        if webhook_secret:
            if not sig_header:
                debug_log('ERRO CRÍTICO: Stripe-Signature ausente com STRIPE_WEBHOOK_SECRET configurado.')
                return jsonify({'error': 'Missing signature'}), 400
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        else:
            # Fallback somente em desenvolvimento explícito
            if os.environ.get('FLASK_ENV') != 'development':
                debug_log('ERRO CRÍTICO: Fallback sem assinatura bloqueado fora de FLASK_ENV=development.')
                return jsonify({'error': 'Webhook secret not configured'}), 500
            app.logger.warning('Validação da assinatura Stripe desativada apenas no ambiente de desenvolvimento.')
            event = json.loads(payload)
    except SignatureVerificationError as e:
        app.logger.warning('Assinatura Stripe inválida: %s', e)
        return jsonify({'error': 'Invalid signature'}), 400
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        app.logger.warning('Payload Stripe inválido: %s', e)
        return jsonify({'error': 'Invalid payload'}), 400

    event_record_id = None
    try:
        event_type = str(event.get('type') or '')
        event_id = str(event.get('id') or '')
        event_record_id, duplicate = begin_webhook_event('stripe', event_id, event_type, payload)
        if duplicate:
            return jsonify({'status': 'duplicate'}), 200

        debug_log(f'Webhook Stripe recebido: {event_type}')
        if event_type == 'checkout.session.completed':
            session = event['data']['object']
            handle_checkout_completed(session)
        elif event_type == 'customer.subscription.created':
            subscription = event['data']['object']
            debug_log(f'Assinatura criada: {subscription["id"]}')
        elif event_type == 'customer.subscription.updated':
            subscription = event['data']['object']
            handle_subscription_updated(subscription)
        elif event_type == 'customer.subscription.deleted':
            subscription = event['data']['object']
            handle_subscription_cancelled(subscription)
        elif event_type == 'invoice.payment_succeeded':
            invoice = event['data']['object']
            debug_log(f'Pagamento bem-sucedido: {invoice["id"]}')
        elif event_type == 'invoice.payment_failed':
            invoice = event['data']['object']
            debug_log(f'Falha no pagamento: {invoice["id"]}')

        finish_webhook_event(event_record_id, 'processed')
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        db.session.rollback()
        finish_webhook_event(event_record_id, 'failed', e)
        app.logger.exception('Erro ao processar webhook Stripe')
        return jsonify({'error': 'Erro interno do servidor'}), 500

@app.route('/abacatepay-webhook', methods=['POST'])
@csrf.exempt
def abacatepay_webhook():
    """
    Webhook do Abacate Pay para processar eventos de pagamento PIX.

    Configure este endpoint no Dashboard do Abacate Pay.

    Eventos importantes:
    - transparent.completed: Cobrança PIX paga com sucesso (V2)
    - transparent.refunded: Pagamento estornado (V2)
    - transparent.disputed/transparent.lost: Pagamento contestado/perdido (V2)
    - billing.paid/billing.failed/billing.refunded: compatibilidade com payloads antigos
    """
    event_record_id = None
    try:
        raw_body = request.get_data(cache=True)
        webhook_error = verify_abacatepay_webhook_request(raw_body)
        if webhook_error is not None:
            return webhook_error

        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({'error': 'JSON inválido'}), 400
        if not payload:
            return jsonify({'error': 'Dados inválidos'}), 400

        event_type = str(payload.get('event') or '')
        event_data = payload.get('data') or {}
        if not isinstance(event_data, dict):
            return jsonify({'error': 'Payload inválido'}), 400

        transparent_data = event_data.get('transparent')
        if not isinstance(transparent_data, dict):
            transparent_data = event_data

        metadata = transparent_data.get('metadata') if isinstance(transparent_data.get('metadata'), dict) else {}
        billing_data = transparent_data
        charge_id = transparent_data.get('id') or event_data.get('id')
        external_id = (
            transparent_data.get('externalId')
            or event_data.get('externalId')
            or metadata.get('externalId')
        )

        if not charge_id and not external_id:
            debug_log('ERRO: identificador da cobrança não encontrado no webhook')
            return jsonify({'error': 'Missing billing_id'}), 400

        provider_event_id = str(
            payload.get('id')
            or f"{event_type}:{charge_id or external_id}"
        )
        event_record_id, duplicate = begin_webhook_event(
            'abacatepay', provider_event_id, event_type, raw_body
        )
        if duplicate:
            return jsonify({'status': 'duplicate'}), 200

        transaction = find_abacatepay_transaction(charge_id=charge_id, external_id=external_id)

        if not transaction:
            debug_log(f'ERRO: Transação não encontrada para charge_id={charge_id} external_id={external_id}')
            finish_webhook_event(event_record_id, 'failed', 'Transação não encontrada')
            return jsonify({'error': 'Transaction not found'}), 404

        if charge_id and not transaction.abacatepay_charge_id:
            transaction.abacatepay_charge_id = charge_id

        normalized_event = event_type.lower()
        if normalized_event in {'transparent.completed', 'billing.paid'}:
            handle_abacatepay_payment_success(transaction, billing_data)
        elif normalized_event in {'transparent.lost', 'transparent.disputed', 'billing.failed'}:
            handle_abacatepay_payment_failed(transaction, billing_data)
        elif normalized_event in {'transparent.refunded', 'billing.refunded'}:
            handle_abacatepay_payment_refunded(transaction, billing_data)
        else:
            sync_abacatepay_transaction_status(transaction, billing_data)

        finish_webhook_event(event_record_id, 'processed')
        return jsonify({'status': 'success'}), 200

    except Exception as e:
        db.session.rollback()
        finish_webhook_event(event_record_id, 'failed', e)
        app.logger.exception('Erro ao processar webhook Abacate Pay')
        return jsonify({'error': 'Erro interno do servidor'}), 500

def send_meta_conversion_event(event_name, user, plan_type, amount_cents, event_id=None):
    """Envia evento para a Conversions API do Meta (Facebook) sem quebrar o fluxo de pagamento"""
    access_token = (app.config.get('META_ACCESS_TOKEN') or '').strip()
    if not access_token:
        app.logger.warning('META_ACCESS_TOKEN não configurado; evento %s não enviado ao Meta Pixel', event_name)
        return

    pixel_id = (app.config.get('META_PIXEL_ID') or '').strip()
    if not pixel_id:
        app.logger.warning('META_PIXEL_ID não configurado; evento %s não enviado ao Meta Pixel', event_name)
        return

    try:
        import requests

        event_time = int(datetime.utcnow().timestamp())
        if not event_id:
            event_id = f'{event_name}-{user.id if user else "anon"}-{event_time}'

        # Dados do usuário hasheados (SHA256) conforme exigido pela Conversions API
        user_data = {}
        if user:
            email = (getattr(user, 'email', '') or '').strip().lower()
            if email:
                user_data['em'] = [hashlib.sha256(email.encode('utf-8')).hexdigest()]
            user_data['external_id'] = [hashlib.sha256(str(user.id).encode('utf-8')).hexdigest()]

        payload = {
            'data': [{
                'event_name': event_name,
                'event_time': event_time,
                'action_source': 'website',
                'event_source_url': f"{app.config.get('SITE_URL', '').rstrip('/')}/planos",
                'event_id': event_id,
                'user_data': user_data,
                'custom_data': {
                    'value': (amount_cents or 0) / 100,
                    'currency': 'BRL',
                    'content_name': plan_type,
                },
            }]
        }

        response = requests.post(
            f'https://graph.facebook.com/v21.0/{pixel_id}/events',
            params={'access_token': access_token},
            json=payload,
            timeout=5,
        )
        if response.status_code != 200:
            app.logger.error(
                'Meta Conversions API retornou %s para evento %s: %s',
                response.status_code, event_name, response.text[:200]
            )
        else:
            debug_log(f'Evento {event_name} enviado ao Meta Pixel (event_id={event_id})')
    except Exception as e:
        # Nunca propagar: falha no rastreamento não pode quebrar o webhook de pagamento
        app.logger.error(f'Erro ao enviar evento {event_name} ao Meta Pixel: {str(e)}')


def handle_abacatepay_payment_success(transaction, billing_data):
    """Processa pagamento PIX bem-sucedido"""
    debug_log(f'Pagamento PIX confirmado: {transaction.abacatepay_billing_id}')

    try:
        user = User.query.get(transaction.user_id)
        if not user:
            raise ValueError(f'Usuário {transaction.user_id} não encontrado.')

        if transaction.plan_type not in {'premium', 'vip', 'donation'}:
            raise ValueError('Plano inválido na transação Abacate Pay.')

        # Verificar se já foi processado
        if transaction.status == 'completed':
            debug_log(f'Transação já processada: {transaction.abacatepay_billing_id}')
            return

        if transaction.plan_type != 'donation':
            # ATIVAR PLANO PREMIUM/VIP
            user.plan = transaction.plan_type
            user.subscription_end_date = datetime.utcnow() + relativedelta(months=1)

        # Atualizar transação
        transaction.status = 'completed'
        transaction.paid_at = datetime.utcnow()

        db.session.commit()

        if transaction.plan_type == 'donation':
            debug_log(f'Doação PIX confirmada para usuário {user.id}')
        else:
            debug_log(f'Plano {transaction.plan_type} ativado para usuário {user.id} via PIX')

            # Disparar eventos do Meta Pixel (Conversions API) para planos pagos
            if transaction.plan_type in ('premium', 'vip'):
                send_meta_conversion_event(
                    'Subscribe', user, transaction.plan_type, transaction.amount,
                    event_id=f'sub-{transaction.id}'
                )
                send_meta_conversion_event(
                    'Purchase', user, transaction.plan_type, transaction.amount,
                    event_id=f'pur-{transaction.id}'
                )

    except Exception as e:
        debug_log(f'Erro ao processar pagamento PIX: {str(e)}')
        db.session.rollback()
        raise

def handle_abacatepay_payment_failed(transaction, billing_data):
    """Processa falha no pagamento PIX"""
    debug_log(f'Pagamento PIX falhou: {transaction.abacatepay_billing_id}')

    try:
        transaction.status = 'failed'
        db.session.commit()
    except Exception as e:
        debug_log(f'Erro ao processar falha PIX: {str(e)}')
        db.session.rollback()
        raise

def handle_abacatepay_payment_refunded(transaction, billing_data):
    """Processa estorno de pagamento PIX"""
    debug_log(f'Pagamento PIX estornado: {transaction.abacatepay_billing_id}')

    try:
        user = User.query.get(transaction.user_id)
        if user and transaction.plan_type != 'donation' and user.plan != 'free':
            # Reverter para plano gratuito
            user.plan = 'free'
            user.subscription_end_date = None

        transaction.status = 'refunded'
        db.session.commit()
    except Exception as e:
        debug_log(f'Erro ao processar estorno PIX: {str(e)}')
        db.session.rollback()
        raise

def handle_checkout_completed(session):
    """Processa checkout completado - ATIVA O PLANO AUTOMATICAMENTE"""
    session_id = session['id']
    user_id = session['metadata'].get('user_id')
    plan_type = session['metadata'].get('plan')

    debug_log(f'Checkout completado: session_id={session_id}, user_id={user_id}, plan={plan_type}')

    if not user_id or plan_type not in {'premium', 'vip', 'donation'}:
        raise ValueError('Metadata de checkout ausente ou inválida.')
    if session.get('payment_status') not in {'paid', 'no_payment_required'}:
        raise ValueError('Checkout ainda não possui pagamento confirmado.')

    try:
        user = User.query.get(int(user_id))
        if not user:
            raise ValueError(f'Usuário {user_id} não encontrado.')

        if plan_type == 'donation':
            existing_transaction = Transaction.query.filter_by(stripe_session_id=session_id).first()
            if existing_transaction and existing_transaction.status == 'completed':
                debug_log(f'Transação de doação já processada: {session_id}')
                return

            if existing_transaction:
                existing_transaction.status = 'completed'
                existing_transaction.paid_at = datetime.utcnow()
                existing_transaction.amount = session.get('amount_total') or existing_transaction.amount
                existing_transaction.currency = session.get('currency') or existing_transaction.currency
                existing_transaction.stripe_customer_id = session.get('customer')
                existing_transaction.stripe_payment_intent_id = session.get('payment_intent')
            else:
                db.session.add(Transaction(
                    user_id=int(user_id),
                    payment_gateway='stripe',
                    stripe_session_id=session_id,
                    stripe_customer_id=session.get('customer'),
                    stripe_payment_intent_id=session.get('payment_intent'),
                    plan_type='donation',
                    amount=session.get('amount_total') or 0,
                    currency=session.get('currency') or 'brl',
                    status='completed',
                    paid_at=datetime.utcnow()
                ))

            db.session.commit()
            debug_log(f'✅ Doação confirmada para usuário {user.username} via webhook')
            return

        # Verificar se já foi processado
        existing_transaction = Transaction.query.filter_by(stripe_session_id=session_id).first()
        if existing_transaction and existing_transaction.status == 'completed':
            debug_log(f'Transação já processada: {session_id}')
            return

        # ATIVAR PLANO PREMIUM/VIP
        user.plan = plan_type
        user.subscription_end_date = datetime.utcnow() + relativedelta(months=1)

        # Registrar transação
        if not existing_transaction:
            transaction = Transaction(
                user_id=user.id,
                stripe_session_id=session_id,
                stripe_customer_id=session.get('customer'),
                stripe_subscription_id=session.get('subscription'),
                plan_type=plan_type,
                amount=session.get('amount_total', 0),
                currency=session.get('currency', 'brl'),
                status='completed',
                paid_at=datetime.utcnow()
            )
            db.session.add(transaction)
        else:
            existing_transaction.status = 'completed'
            existing_transaction.paid_at = datetime.utcnow()
            existing_transaction.stripe_customer_id = session.get('customer')
            existing_transaction.stripe_subscription_id = session.get('subscription')

        db.session.commit()
        debug_log(f'✅ Plano {plan_type.upper()} ativado para usuário {user.username} via webhook')

        # Disparar eventos do Meta Pixel (Conversions API) para planos pagos
        if plan_type in ('premium', 'vip'):
            completed_transaction = transaction if not existing_transaction else existing_transaction
            send_meta_conversion_event(
                'Subscribe', user, completed_transaction.plan_type, completed_transaction.amount,
                event_id=f'sub-{completed_transaction.id}'
            )
            send_meta_conversion_event(
                'Purchase', user, completed_transaction.plan_type, completed_transaction.amount,
                event_id=f'pur-{completed_transaction.id}'
            )

    except Exception as e:
        db.session.rollback()
        debug_log(f'ERRO ao processar checkout: {str(e)}')
        raise

def handle_subscription_updated(subscription):
    """Processa atualização de assinatura"""
    subscription_id = subscription['id']
    status = subscription['status']

    debug_log(f'Assinatura atualizada: {subscription_id}, status={status}')

    transaction = Transaction.query.filter_by(stripe_subscription_id=subscription_id).first()
    if not transaction:
        debug_log(f'Transação não encontrada para subscription_id: {subscription_id}')
        return

    user = User.query.get(transaction.user_id)
    if not user:
        return

    # Se assinatura foi cancelada ou expirou
    if status in ['canceled', 'unpaid', 'past_due']:
        user.plan = 'free'
        user.subscription_end_date = None
        db.session.commit()
        debug_log(f'⚠️ Plano do usuário {user.username} revertido para FREE (status: {status})')

def handle_subscription_cancelled(subscription):
    """Processa cancelamento de assinatura"""
    subscription_id = subscription['id']

    debug_log(f'Assinatura cancelada: {subscription_id}')

    transaction = Transaction.query.filter_by(stripe_subscription_id=subscription_id).first()
    if not transaction:
        return

    user = User.query.get(transaction.user_id)
    if not user:
        return

    # Reverter para plano gratuito
    user.plan = 'free'
    user.subscription_end_date = None
    db.session.commit()
    debug_log(f'❌ Assinatura cancelada - usuário {user.username} voltou ao plano FREE')

@app.route('/faq')
def faq():
    return render_template('faq.html', title='Perguntas Frequentes')


@app.route('/debug/check-limits')
@login_required
def debug_check_limits():
    """Rota de debug para verificar os limites do usuário"""
    user = current_user
    now = datetime.utcnow()

    # Verificar downloads
    one_day_ago = now - timedelta(days=1)
    one_week_ago = now - timedelta(days=7)
    downloads_today = Download.query.filter(
        Download.user_id == user.id,
        Download.timestamp >= one_day_ago
    ).count()
    downloads_week = Download.query.filter(
        Download.user_id == user.id,
        Download.timestamp >= one_week_ago
    ).count()

    # Verificar comentários
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    comments_today = Comment.query.filter(
        Comment.user_id == user.id,
        Comment.date_posted >= today_start
    ).count()

    # Verificar favoritos
    favorites_count = Favorite.query.filter_by(user_id=user.id).count()

    debug_info = {
        'user': {
            'username': user.username,
            'plan': user.plan,
            'active_sessions': user.active_sessions
        },
        'downloads': {
            'today': downloads_today,
            'this_week': downloads_week,
            'can_download': check_user_download_limit(user)[0],
            'remaining': check_user_download_limit(user)[1],
            'limit': check_user_download_limit(user)[2]
        },
        'comments': {
            'today': comments_today,
            'can_comment': check_comment_limit(user)[0],
            'message': check_comment_limit(user)[1]
        },
        'favorites': {
            'total': favorites_count,
            'can_add': check_favorite_limit(user)[0],
            'message': check_favorite_limit(user)[1]
        },
        'devices': {
            'active_sessions': user.active_sessions,
            'can_login': check_device_limit(user)[0],
            'message': check_device_limit(user)[1]
        }
    }

    return jsonify(debug_info)


@app.route('/termos-de-uso')
def terms_of_service():
    return render_template('termos-de-uso.html', title='Termos de Uso')

@app.route('/politica-de-privacidade')
def privacy_policy():
    return render_template('politica-de-privacidade.html', title='Política de Privacidade')

@app.route('/area-vip')
@login_required
def vip_area():
    if current_user.plan != 'vip':
        flash('A Área VIP é exclusiva para assinantes VIP. Conheça o plano VIP para liberar esse acesso.', 'warning')
        return redirect(url_for('plans'))

    return render_template('vip-area.html', title='Área VIP')

@app.route('/contato', methods=['GET', 'POST'])
def contact():
    if request.args.get('category') == 'solicitacao':
        return redirect(url_for('content_requests'))
    if request.method == 'POST':
        category = sanitize_input(request.form.get('category', ''))
        if category == 'solicitacao':
            target = url_for('content_requests')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'redirect_url': target})
            return redirect(target)
        raw_phone = request.form.get('phone', '').strip()
        phone_digits = re.sub(r'\D', '', raw_phone)
        if len(phone_digits) > 11:
            phone_digits = phone_digits[:11]

        if phone_digits:
            if len(phone_digits) not in (10, 11):
                error_msg = 'Telefone inválido'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': error_msg})
                flash(error_msg, 'danger')
                return redirect(url_for('contact'))

            if len(phone_digits) == 11:
                phone = f'({phone_digits[:2]}) {phone_digits[2:7]}-{phone_digits[7:11]}'
            else:
                phone = f'({phone_digits[:2]}) {phone_digits[2:6]}-{phone_digits[6:10]}'
        else:
            phone = ''

        # Sanitizar e validar inputs
        name = sanitize_input(request.form.get('name', '').strip())
        email = request.form.get('email', '').strip().lower()
        subject = sanitize_input(request.form.get('subject', '').strip())
        message = sanitize_html(request.form.get('message', '').strip())

        # Validar tamanhos
        if not name or len(name) > 100:
            error_msg = 'Nome inválido ou muito longo'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_msg})
            flash(error_msg, 'danger')
            return redirect(url_for('contact'))

        if not email or len(email) > 255 or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            error_msg = 'Email inválido'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_msg})
            flash(error_msg, 'danger')
            return redirect(url_for('contact'))

        if not subject or len(subject) > 200:
            error_msg = 'Assunto inválido ou muito longo'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_msg})
            flash(error_msg, 'danger')
            return redirect(url_for('contact'))

        if phone and len(phone) > 30:
            error_msg = 'Telefone inválido ou muito longo'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_msg})
            flash(error_msg, 'danger')
            return redirect(url_for('contact'))

        if not message or len(message) > 5000:
            error_msg = 'Mensagem inválida ou muito longa'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_msg})
            flash(error_msg, 'danger')
            return redirect(url_for('contact'))

        attachments_valid, attachments, attachments_error = prepare_contact_email_attachments(
            request.files.getlist('attachments')
        )
        if not attachments_valid:
            attachments_error_message = attachments_error or 'Não foi possível processar os anexos enviados.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': attachments_error_message})
            flash(attachments_error_message, 'danger')
            return redirect(url_for('contact'))

        message_prefix = []
        if category:
            message_prefix.append(f'Categoria: {category}')
        if phone:
            message_prefix.append(f'Telefone: {phone}')
        if attachments:
            attachment_names = ', '.join(filename for filename, _, _ in attachments)
            message_prefix.append(f'Anexos: {attachment_names}')

        stored_message = f"{chr(10).join(message_prefix)}{chr(10) * 2}{message}" if message_prefix else message
        new_contact = Contact(name=name, email=email, subject=subject, message=stored_message)
        db.session.add(new_contact)
        db.session.commit()

        try:
            send_contact_support_email(
                name=name,
                email=email,
                phone=phone,
                category=category,
                subject=subject,
                message=message,
                attachments=attachments,
            )
        except Exception:
            app.logger.exception('Erro ao enviar formulario de contato por email')
            error_msg = 'Não foi possível encaminhar sua mensagem ao suporte agora. Tente novamente em instantes.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_msg}), 500
            flash(error_msg, 'danger')
            return redirect(url_for('contact'))

        # Retornar JSON se for AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': f'Sua mensagem foi enviada com sucesso para {app.config["SUPPORT_EMAIL"]}!'
            })

        flash(f'Sua mensagem foi enviada com sucesso para {app.config["SUPPORT_EMAIL"]}!', 'success')
        return redirect(url_for('contact'))

    return render_template('contact.html', title='Contato')


CONTENT_REQUEST_STATUSES = {
    'pending': 'Recebida',
    'reviewing': 'Em análise',
    'searching': 'Em busca',
    'found': 'Encontrado',
    'completed': 'Concluído',
    'unavailable': 'Indisponível',
    'rejected': 'Não aprovado',
}


@app.route('/solicitacoes', methods=['GET', 'POST'])
@limiter.limit('10 per hour', methods=['POST'])
def content_requests():
    """Sugestões abertas a todos e buscas prioritárias exclusivas do VIP."""
    if request.method == 'POST':
        request_type = str(request.form.get('request_type') or 'suggestion').strip().lower()
        if request_type not in {'suggestion', 'vip_priority'}:
            return jsonify({'success': False, 'message': 'Tipo de solicitação inválido.'}), 400

        if request_type == 'vip_priority':
            if not current_user.is_authenticated:
                flash('Entre na sua conta VIP para solicitar uma busca prioritária.', 'warning')
                return redirect(url_for('login', next=url_for('content_requests', type='vip_priority')))
            if not can_request_specific_content(current_user):
                flash('A busca prioritária é exclusiva do plano VIP. Você ainda pode enviar uma sugestão.', 'warning')
                return redirect(url_for('content_requests', type='suggestion'))

        title = sanitize_input(str(request.form.get('title') or '').strip())
        description = sanitize_input(str(request.form.get('description') or '').strip())
        category_name = sanitize_input(str(request.form.get('category') or '').strip())
        board_code = sanitize_input(str(request.form.get('board_code') or '').strip())
        requester_name = sanitize_input(str(request.form.get('requester_name') or '').strip())
        requester_email = str(request.form.get('requester_email') or '').strip().lower()

        if not title or len(title) > 200:
            flash('Informe o conteúdo procurado em até 200 caracteres.', 'danger')
            return redirect(url_for('content_requests'))
        if len(description) > 4000 or len(board_code) > 120 or len(category_name) > 100:
            flash('Revise os campos: um dos valores excede o tamanho permitido.', 'danger')
            return redirect(url_for('content_requests'))

        user_id = current_user.id if current_user.is_authenticated else None
        if current_user.is_authenticated:
            requester_name = current_user.get_full_name()
            requester_email = current_user.email
        elif not requester_name or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', requester_email):
            flash('Informe nome e e-mail válidos para enviar a sugestão.', 'danger')
            return redirect(url_for('content_requests'))

        content_request = ContentRequest(
            user_id=user_id,
            request_type=request_type,
            requester_plan=normalize_plan_key(current_user.plan) if current_user.is_authenticated else 'guest',
            title=title,
            description=description or None,
            category=category_name or None,
            board_code=board_code or None,
            priority=100 if request_type == 'vip_priority' else 0,
            requester_name=requester_name or None,
            requester_email=requester_email or None,
        )
        db.session.add(content_request)
        db.session.commit()
        flash(
            'Busca prioritária recebida. A disponibilidade depende da possibilidade de obtenção do arquivo.'
            if request_type == 'vip_priority'
            else 'Sugestão recebida. Ela será considerada na expansão do acervo, sem prazo ou prioridade garantidos.',
            'success',
        )
        return redirect(url_for('content_requests'))

    selected_type = str(request.args.get('type') or 'suggestion').strip().lower()
    priority_locked = selected_type == 'vip_priority' and not (
        current_user.is_authenticated and can_request_specific_content(current_user)
    )
    if selected_type == 'vip_priority' and not (
        current_user.is_authenticated and can_request_specific_content(current_user)
    ):
        selected_type = 'suggestion'
    own_requests = []
    if current_user.is_authenticated:
        own_requests = ContentRequest.query.filter_by(user_id=current_user.id).order_by(
            ContentRequest.created_at.desc()
        ).all()
    public_categories, empty_categories = get_public_categories_partition()
    public_categories = sorted(
        [*public_categories, *empty_categories],
        key=lambda category_item: (category_item.order or 0, category_item.name.casefold()),
    )
    return render_template(
        'content_requests.html',
        title='Sugestões e solicitações',
        selected_type=selected_type,
        priority_locked=priority_locked,
        requested_query=str(request.args.get('q') or '').strip(),
        own_requests=own_requests,
        request_statuses=CONTENT_REQUEST_STATUSES,
        request_categories=public_categories,
    )


@app.route('/admin/solicitacoes')
@login_required
@admin_required
def admin_content_requests():
    requests_list = ContentRequest.query.order_by(
        ContentRequest.priority.desc(), ContentRequest.created_at.asc()
    ).all()
    return render_template(
        'admin/content_requests.html',
        title='Solicitações de conteúdo',
        content_requests=requests_list,
        request_statuses=CONTENT_REQUEST_STATUSES,
        request_summary={
            'total': len(requests_list),
            'pending': sum(item.status == 'pending' for item in requests_list),
            'vip': sum((item.requester_plan or (item.user.plan if item.user else 'guest')) == 'vip' for item in requests_list),
            'completed': sum(item.status == 'completed' for item in requests_list),
        },
    )


@app.route('/admin/solicitacoes/<int:request_id>/status', methods=['POST'])
@login_required
@admin_required
def admin_update_content_request(request_id):
    content_request = ContentRequest.query.get_or_404(request_id)
    status = str(request.form.get('status') or '').strip().lower()
    if status not in CONTENT_REQUEST_STATUSES:
        flash('Status inválido.', 'danger')
        return redirect(url_for('admin_content_requests'))
    content_request.status = status
    content_request.admin_notes = sanitize_input(str(request.form.get('admin_notes') or '').strip())[:4000] or None
    content_request.updated_at = datetime.utcnow()
    db.session.commit()
    flash('Solicitação atualizada.', 'success')
    return redirect(url_for('admin_content_requests'))

@app.route('/newsletter', methods=['POST'])
@limiter.limit("10 per hour")  # Limitar inscrições na newsletter
def newsletter():
    email = request.form.get('email', '').strip().lower()

    if not email or len(email) > 255:
        return jsonify({'success': False, 'message': 'E-mail é obrigatório'})

    # Validar formato de email
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({'success': False, 'message': 'Email inválido'})

    existing = Subscriber.query.filter_by(email=email).first()

    if existing:
        return jsonify({'success': False, 'message': 'Este e-mail já está inscrito na nossa newsletter'})

    new_subscriber = Subscriber(email=email)
    db.session.add(new_subscriber)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Inscrição realizada com sucesso!'})

# API para posts
@app.route('/posts')
def posts():
    """Página que lista todos os posts ativos"""
    page = request.args.get('page', 1, type=int)
    posts = Post.query.filter_by(is_active=True).order_by(Post.date_posted.desc()).paginate(
        page=page, per_page=8, error_out=False
    )

    # Lista de IDs de posts favoritados pelo usuário atual
    favorite_post_ids = []
    if current_user.is_authenticated:
        # Forçar refresh da sessão para evitar cache
        db.session.expire_all()
        favorite_post_ids = [f.post_id for f in Favorite.query.filter_by(user_id=current_user.id).all()]
        debug_log(f"POSTS Usuário {current_user.id} tem {len(favorite_post_ids)} favoritos: {favorite_post_ids}")

    return render_template('posts.html', posts=posts, favorite_post_ids=favorite_post_ids, title='Todos os Posts')

@app.route('/api/posts')
def api_posts():
    page = request.args.get('page', 1, type=int)
    posts_query = Post.query.filter_by(is_active=True).order_by(Post.date_posted.desc())
    posts_paginated = posts_query.paginate(page=page, per_page=8, error_out=False)

    favorite_post_ids = []
    if current_user.is_authenticated:
        favorite_post_ids = [f.post_id for f in Favorite.query.filter_by(user_id=current_user.id).all()]

    posts_data = _serialize_posts(posts_paginated.items, favorite_post_ids)

    return jsonify({
        'success': True,
        'posts': posts_data,
        'has_next': posts_paginated.has_next,
        'next_page': posts_paginated.next_num,
        'total': posts_paginated.total,
        'is_authenticated': current_user.is_authenticated
    })

@app.route('/api/recent-posts')
def api_recent_posts():
    """API para paginação AJAX dos posts recentes na homepage"""
    page = request.args.get('page', 1, type=int)
    posts_query = Post.query.filter_by(is_active=True).order_by(Post.date_posted.desc())
    posts_paginated = posts_query.paginate(page=page, per_page=8, error_out=False)

    favorite_post_ids = []
    if current_user.is_authenticated:
        favorite_post_ids = [f.post_id for f in Favorite.query.filter_by(user_id=current_user.id).all()]

    posts_data = _serialize_posts(posts_paginated.items, favorite_post_ids)

    pages = []
    for p in posts_paginated.iter_pages(left_edge=1, right_edge=1, left_current=1, right_current=2):
        pages.append(p)

    return jsonify({
        'success': True,
        'posts': posts_data,
        'pagination': {
            'page': posts_paginated.page,
            'pages': posts_paginated.pages,
            'total': posts_paginated.total,
            'has_prev': posts_paginated.has_prev,
            'has_next': posts_paginated.has_next,
            'prev_num': posts_paginated.prev_num,
            'next_num': posts_paginated.next_num,
            'iter_pages': pages
        },
        'is_authenticated': current_user.is_authenticated
    })

@app.route('/api/category-posts/<string:category_name>')
def api_category_posts(category_name):
    """API para carregar mais posts de uma categoria"""
    page = request.args.get('page', 1, type=int)
    posts_query = Post.query.filter_by(category_str=category_name, is_active=True).order_by(Post.date_posted.desc())
    posts_paginated = posts_query.paginate(page=page, per_page=8, error_out=False)

    favorite_post_ids = []
    if current_user.is_authenticated:
        favorite_post_ids = [f.post_id for f in Favorite.query.filter_by(user_id=current_user.id).all()]

    posts_data = _serialize_posts(posts_paginated.items, favorite_post_ids)

    return jsonify({
        'success': True,
        'posts': posts_data,
        'has_next': posts_paginated.has_next,
        'next_page': posts_paginated.next_num,
        'total': posts_paginated.total,
        'is_authenticated': current_user.is_authenticated
    })


@app.route('/api/subcategory-posts/<string:subcategory_name>')
def api_subcategory_posts(subcategory_name):
    """API para carregar mais posts de uma subcategoria."""
    page = request.args.get('page', 1, type=int)
    posts_query = Post.query.filter_by(subcategory=subcategory_name, is_active=True).order_by(Post.date_posted.desc())
    posts_paginated = posts_query.paginate(page=page, per_page=8, error_out=False)

    favorite_post_ids = []
    if current_user.is_authenticated:
        favorite_post_ids = [f.post_id for f in Favorite.query.filter_by(user_id=current_user.id).all()]

    posts_data = _serialize_posts(posts_paginated.items, favorite_post_ids)

    return jsonify({
        'success': True,
        'posts': posts_data,
        'has_next': posts_paginated.has_next,
        'next_page': posts_paginated.next_num,
        'total': posts_paginated.total,
        'is_authenticated': current_user.is_authenticated
    })


def _serialize_posts(posts_list, favorite_post_ids):
    """Serializa uma lista de posts para JSON"""
    icon_map = {'BIOS': 'fas fa-microchip', 'Esquemas': 'fas fa-project-diagram', 'Drivers': 'fas fa-cogs',
                'Softwares': 'fas fa-laptop-code', 'Impressoras': 'fas fa-print', 'Cursos': 'fas fa-graduation-cap',
                'Datasheet': 'fas fa-file-alt'}
    posts_data = []
    for post in posts_list:
        dl_files = get_public_download_files(post)
        cat_slug = generate_slug(post.category_str) if post.category_str else ''
        post_link = f'/{cat_slug}/{post.slug}' if post.slug and cat_slug else f'/post/{post.id}'
        img_url = ''
        if post.image_url:
            if post.image_url.startswith('http'):
                img_url = post.image_url
            else:
                img_url = f'/static/uploads/posts/{post.image_url}'
        else:
            img_url = '/static/images/posts/default.jpg'

        cat_icon = 'fas fa-folder'
        if post.category_rel and post.category_rel.icon:
            cat_icon = post.category_rel.icon
        elif post.category_str in icon_map:
            cat_icon = icon_map[post.category_str]

        posts_data.append({
            'id': post.id,
            'title': post.title,
            'content': post.content or '',
            'date_posted': post.date_posted.strftime('%d/%m/%Y') if post.date_posted else '',
            'views': post.views or 0,
            'image_url': img_url,
            'download_link': url_for('download_post', post_id=post.id) if post.download_link else '',
            'category_str': post.category_str or 'Geral',
            'category_icon': cat_icon,
            'post_url': post_link,
            'featured': post.featured,
            'download_files': dl_files,
            'is_favorited': post.id in favorite_post_ids
        })
    return posts_data

@app.route('/api/debug/posts')
@login_required
@admin_required
def api_debug_posts():
    """Endpoint de debug para verificar posts no banco"""
    total_posts = Post.query.count()
    active_posts = Post.query.filter_by(is_active=True).count()
    inactive_posts = Post.query.filter_by(is_active=False).count()

    # Pegar os últimos 5 posts
    recent_posts = Post.query.order_by(Post.date_posted.desc()).limit(5).all()

    posts_info = []
    for post in recent_posts:
        posts_info.append({
            'id': post.id,
            'title': post.title,
            'is_active': post.is_active,
            'category': post.category_str,
            'date_posted': post.date_posted.strftime('%Y-%m-%d %H:%M:%S') if post.date_posted else None
        })

    return jsonify({
        'total_posts': total_posts,
        'active_posts': active_posts,
        'inactive_posts': inactive_posts,
        'recent_posts': posts_info
    })


@app.route('/api/posts/<int:post_id>')
def api_post(post_id):
    post = Post.query.get_or_404(post_id)
    return jsonify({
        'id': post.id,
        'title': post.title,
        'content': post.content,
        'date_posted': post.date_posted.isoformat() if post.date_posted else None,
        'category': post.category_rel.name if post.category_rel else post.category_str,
        'model': post.model,
        'board_code': post.board_code,
        'file_type': post.file_type,
        'verification_status': post.verification_status,
        'download_files': get_public_download_files(post),
        'download_url': url_for('download_post', post_id=post.id) if post.download_link else None,
    })

@app.route('/api/search/suggestions')
def search_suggestions():
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    max_suggestions = 10

    debug_log(f" Search query: '{query}', category: '{category}'")  # DEBUG

    if not query or len(query) < 1:
        debug_log(" Query too short or empty")  # DEBUG
        return jsonify([])

    suggestions = []

    # Se não há categoria específica, buscar categorias também
    if not category:
        scored_categories = []
        for cat in Category.query.filter_by(is_active=True, is_visible=True).all():
            score = get_search_match_score(query, cat.name, cat.description, cat.slug)
            if score is not None:
                scored_categories.append((score, cat.name.casefold(), cat))

        categories = [
            cat
            for _score, _name, cat in sorted(scored_categories, key=lambda item: (item[0], item[1]))[:2]
        ]

        for cat in categories:
            suggestions.append({
                'type': 'category',
                'title': cat.name,
                'description': f'Categoria - {cat.description or "Ver todos os posts desta categoria"}',
                'url': url_for('category', category=cat.name),
                'icon': cat.icon or 'fas fa-folder'
            })

        scored_boards = []
        for board in HardwareBoard.query.all():
            score = get_search_match_score(
                query, board.board_code, board.normalized_board_code,
                board.device_model, board.device_series, board.manufacturer,
            )
            if score is not None:
                scored_boards.append((score, board.board_code.casefold(), board))
        for _score, _code, board in sorted(scored_boards, key=lambda entry: (entry[0], entry[1]))[:2]:
            suggestions.append({
                'type': 'board',
                'title': board.board_code,
                'description': ' · '.join(filter(None, [board.manufacturer, board.device_model, board.board_revision])),
                'url': url_for('hardware_board_detail', slug=board.slug),
                'icon': 'fas fa-microchip',
            })

        scored_components = []
        for component in ElectronicComponent.query.filter_by(is_published=True).all():
            aliases = ' '.join(alias.alias for alias in component.aliases)
            score = get_search_match_score(
                query, component.part_number, component.normalized_part_number,
                component.manufacturer, component.title_ptbr, aliases,
            )
            if score is not None:
                scored_components.append((score, component.part_number.casefold(), component))
        for _score, _part, component in sorted(scored_components, key=lambda entry: (entry[0], entry[1]))[:3]:
            suggestions.append({
                'type': 'datasheet',
                'title': component.part_number,
                'description': ' · '.join(filter(None, [component.manufacturer, component.category, component.package, 'Datasheet'])),
                'url': url_for('datasheet_component_detail', slug=component.slug),
                'icon': 'fas fa-file-pdf',
            })

    posts_query = Post.query.filter_by(is_active=True)
    if category:
        posts_query = posts_query.filter(Post.category_str == category)

    scored_posts = []
    for post in posts_query.all():
        score = get_post_search_score(query, post)
        if score is not None:
            sort_date = post.date_posted or datetime.min
            scored_posts.append((score, -sort_date.toordinal(), post.title.casefold(), post))

    remaining_slots = max(max_suggestions - len(suggestions), 0)
    posts = [
        post
        for _score, _date, _title, post in sorted(scored_posts, key=lambda item: (item[0], item[1], item[2]))[:remaining_slots]
    ]

    # Verificar total de posts ativos no banco
    total_active_posts = Post.query.filter_by(is_active=True).count()
    debug_log(f" Total active posts in database: {total_active_posts}")  # DEBUG
    debug_log(f" Returning {len(posts)} suggestions")  # DEBUG

    for post in posts:
        category_name = post.category_str or (post.category_rel.name if post.category_rel else 'Sem categoria')
        download_types = []
        for download_file in get_public_download_files(post):
            file_type = str(download_file.get('type') or '').strip()
            if file_type and file_type.casefold() not in {item.casefold() for item in download_types}:
                download_types.append(file_type)
        file_type_label = '/'.join(download_types) or post.file_type or category_name

        # Determinar o ícone baseado na categoria
        category_icon = 'fas fa-file-alt'
        if post.category_str == 'BIOS':
            category_icon = 'fas fa-microchip'
        elif post.category_str == 'Drivers':
            category_icon = 'fas fa-cogs'
        elif post.category_str == 'Esquemas':
            category_icon = 'fas fa-project-diagram'
        elif post.category_str == 'Softwares':
            category_icon = 'fas fa-laptop-code'
        elif post.category_str == 'Impressoras':
            category_icon = 'fas fa-print'
        elif post.category_str == 'Cursos':
            category_icon = 'fas fa-graduation-cap'

        suggestions.append({
            'type': 'post',
            'title': post.title,
            'description': ' · '.join(filter(None, [post.model, post.board_code, file_type_label])),
            'category': category_name,
            'file_types': download_types or [file_type_label],
            'url': url_for('post_by_slug', category=generate_slug(post.category_str), slug=post.slug) if post.slug else url_for('post', post_id=post.id),
            'icon': category_icon,
            'image_url': get_image_url_for_response(post.image_url, folder='posts', default='default.jpg')
        })

    unique_suggestions = []
    seen_suggestions = set()
    for item in suggestions:
        key = (
            str(item.get('type') or ''),
            str(item.get('url') or ''),
            str(item.get('title') or '').strip().lower()
        )
        if key in seen_suggestions:
            continue
        seen_suggestions.add(key)
        unique_suggestions.append(item)

    return jsonify(unique_suggestions[:max_suggestions])


@app.route('/placa/<string:slug>')
def hardware_board_detail(slug):
    board = HardwareBoard.query.filter_by(slug=slug).first_or_404()
    resources = TechnicalResource.query.filter_by(board_id=board.id).order_by(TechnicalResource.created_at.desc()).all()
    public_resources = [resource for resource in resources if resource.post and resource.post.is_active]
    component_links = BoardComponent.query.join(ElectronicComponent).filter(
        BoardComponent.board_id == board.id,
        ElectronicComponent.is_published.is_(True),
    ).order_by(ElectronicComponent.part_number.asc()).all()
    return render_template(
        'hardware_board.html',
        board=board,
        resources=public_resources,
        component_links=component_links,
        title=f'{board.board_code} - Placa técnica',
    )


@app.route('/api/placas/<string:slug>')
def hardware_board_api(slug):
    board = HardwareBoard.query.filter_by(slug=slug).first_or_404()
    resources = []
    for resource in TechnicalResource.query.filter_by(board_id=board.id).all():
        if not resource.post or not resource.post.is_active:
            continue
        resources.append({
            'id': resource.id,
            'title': resource.title,
            'type': resource.resource_type,
            'version': resource.version,
            'verification_status': resource.verification_status,
            'source_provider': resource.source_provider,
            'post_url': url_for('post', post_id=resource.post_id),
            'files': [file.public_dict() for file in resource.files if file.is_active],
        })
    return jsonify({
        'id': board.id,
        'manufacturer': board.manufacturer,
        'device_model': board.device_model,
        'device_series': board.device_series,
        'board_code': board.board_code,
        'board_revision': board.board_revision,
        'platform': board.platform,
        'chipset': board.chipset,
        'resources': resources,
        'components': [
            {
                'part_number': link.component.part_number,
                'manufacturer': link.component.manufacturer,
                'reference_designator': link.reference_designator,
                'verified': link.verified,
                'url': url_for('datasheet_component_detail', slug=link.component.slug),
            }
            for link in BoardComponent.query.join(ElectronicComponent).filter(
                BoardComponent.board_id == board.id,
                ElectronicComponent.is_published.is_(True),
            ).all()
        ],
    })


@app.route('/datasheets')
def datasheet_library():
    query = sanitize_input(str(request.args.get('q') or ''))[:160]
    category = sanitize_input(str(request.args.get('category') or ''))[:120]
    manufacturer = sanitize_input(str(request.args.get('manufacturer') or ''))[:160]
    components_query = ElectronicComponent.query.filter_by(is_published=True)
    if category:
        components_query = components_query.filter(ElectronicComponent.category == category)
    if manufacturer:
        components_query = components_query.filter(ElectronicComponent.manufacturer == manufacturer)
    components = components_query.order_by(ElectronicComponent.part_number.asc()).all()
    if query:
        components = [
            component for component in components
            if get_search_match_score(
                query, component.part_number, component.normalized_part_number,
                component.manufacturer, component.title_ptbr, component.category,
                ' '.join(alias.alias for alias in component.aliases),
            ) is not None
        ]
        if not components and looks_like_part_number(query):
            normalized_query = normalize_component_part_number(query)
            demand = DatasheetDemand.query.filter_by(normalized_query=normalized_query).first()
            if demand:
                demand.request_count = (demand.request_count or 0) + 1
                demand.last_requested_at = datetime.utcnow()
            else:
                db.session.add(DatasheetDemand(
                    normalized_query=normalized_query, display_query=query, request_count=1,
                ))
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
    categories = [
        row[0] for row in db.session.query(ElectronicComponent.category).filter(
            ElectronicComponent.is_published.is_(True),
            ElectronicComponent.category.isnot(None),
        ).distinct().order_by(ElectronicComponent.category.asc()).all() if row[0]
    ]
    manufacturers = [
        row[0] for row in db.session.query(ElectronicComponent.manufacturer).filter(
            ElectronicComponent.is_published.is_(True),
            ElectronicComponent.manufacturer.isnot(None),
        ).distinct().order_by(ElectronicComponent.manufacturer.asc()).all() if row[0]
    ]
    return render_template(
        'datasheets.html', components=components, query=query, category=category,
        manufacturer=manufacturer, component_categories=categories,
        component_manufacturers=manufacturers, title='Datasheets de componentes',
    )


@app.route('/datasheet/<string:slug>')
def datasheet_component_detail(slug):
    component = ElectronicComponent.query.filter_by(slug=slug, is_published=True).first_or_404()
    attribution_names = []
    for source_record in component.source_records:
        source_config = DatasheetProviderConfig.query.filter_by(provider_name=source_record.provider).first()
        if source_config and source_config.attribution_required and source_config.display_name not in attribution_names:
            attribution_names.append(source_config.display_name)
    documents = []
    for document in component.documents:
        if not document.is_active:
            continue
        config = DatasheetProviderConfig.query.filter_by(provider_name=document.source_provider).first()
        if not config or not config.public_republish_allowed:
            continue
        documents.append((document, config))
    board_links = BoardComponent.query.join(HardwareBoard).filter(
        BoardComponent.component_id == component.id
    ).order_by(HardwareBoard.board_code.asc()).all()
    related = ElectronicComponent.query.filter(
        ElectronicComponent.is_published.is_(True),
        ElectronicComponent.id != component.id,
        ElectronicComponent.category == component.category,
    ).order_by(ElectronicComponent.confidence.desc()).limit(6).all() if component.category else []
    return render_template(
        'datasheet_detail.html', component=component, documents=documents,
        board_links=board_links, related_components=related,
        attribution_names=attribution_names,
        title=f'{component.part_number} Datasheet',
    )


@app.route('/datasheet/documento/<int:document_id>/download')
@login_required
@limiter.limit('30 per hour')
def download_datasheet_document(document_id):
    document = DatasheetDocument.query.get_or_404(document_id)
    if not document.is_active or not document.component or not document.component.is_published:
        abort(404)
    config = DatasheetProviderConfig.query.filter_by(provider_name=document.source_provider).first()
    if not config or not (
        config.enabled and config.written_permission_confirmed and config.public_republish_allowed
        and config.pdf_stream_allowed and document.distribution_policy in {'stream_allowed', 'mirror_allowed'}
    ):
        abort(403)

    filename = sanitize_download_name(f'{document.component.part_number}-datasheet.pdf')
    if document.pdf_storage_provider == 'local' and document.pdf_internal_reference:
        storage_root = os.path.abspath(app.config['TECHNICAL_LOCAL_STORAGE_DIR'])
        local_path = os.path.abspath(os.path.join(storage_root, document.pdf_internal_reference))
        if os.path.commonpath([storage_root, local_path]) != storage_root or not os.path.isfile(local_path):
            abort(404)
        return send_file(local_path, as_attachment=True, download_name=filename, conditional=True)

    if not document.source_reference:
        abort(404)
    allowed_hosts = {
        host.strip().lower()
        for host in os.environ.get('DATASHEET_STORAGE_ALLOWED_HOSTS', '').split(',')
        if host.strip()
    }
    storage = HttpStorageProvider(
        allowed_hosts=allowed_hosts,
        connect_timeout=float(os.environ.get('STORAGE_CONNECT_TIMEOUT', '5')),
        read_timeout=float(os.environ.get('STORAGE_READ_TIMEOUT', '45')),
    )
    try:
        upstream = storage.open(document.source_reference, request.headers.get('Range'))
    except StorageError as exc:
        app.logger.warning('Falha ao entregar datasheet %s: %s', document.id, exc)
        return jsonify({'success': False, 'message': 'Documento indisponível no momento.'}), 502
    headers = dict(upstream.headers)
    upstream_filename = filename_from_content_disposition(headers.pop('Content-Disposition', None))
    filename = upstream_filename or filename
    ascii_filename = filename.encode('ascii', 'ignore').decode('ascii') or 'datasheet.pdf'
    headers['Content-Disposition'] = f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{quote(filename, safe="")}'
    headers['X-Content-Type-Options'] = 'nosniff'
    headers['Cache-Control'] = 'private, no-store'
    response = Response(upstream.iterator, status=upstream.status_code, headers=headers, direct_passthrough=True)
    response.call_on_close(upstream.close)
    return response


@app.route('/contribuir-arquivo', methods=['GET', 'POST'])
@login_required
@limiter.limit('5 per day')
def contribute_technical_file():
    if not app.config.get('TECHNICAL_CONTRIBUTIONS_ENABLED'):
        abort(404)
    if request.method == 'GET':
        contributions = FileContribution.query.filter_by(user_id=current_user.id).order_by(FileContribution.created_at.desc()).all()
        return render_template('contribute_file.html', contributions=contributions, title='Contribuir com arquivo')

    upload = request.files.get('file')
    if not upload or not upload.filename:
        return jsonify({'success': False, 'message': 'Selecione um arquivo técnico.'}), 400
    original = sanitize_download_name(upload.filename or 'arquivo-tecnico')
    extension = os.path.splitext(original)[1].lower().lstrip('.')
    if extension not in TECHNICAL_UPLOAD_EXTENSIONS or extension in {'html', 'svg', 'js'}:
        return jsonify({'success': False, 'message': 'Tipo de arquivo não permitido.'}), 400
    contribution_root = os.path.abspath(os.path.join(app.config['TECHNICAL_IMPORT_TEMP_DIR'], 'contributions'))
    os.makedirs(contribution_root, exist_ok=True)
    destination = os.path.join(contribution_root, f'{uuid.uuid4().hex}-{secure_filename(original)}')
    upload.save(destination)
    if not os.path.isfile(destination) or os.path.getsize(destination) == 0:
        return jsonify({'success': False, 'message': 'O arquivo enviado está vazio.'}), 400
    try:
        _validate_technical_file_content(destination, original)
        if extension == 'zip':
            inspect_zip_archive(destination)
    except (ValueError, ArchiveSafetyError, OSError) as exc:
        try:
            os.remove(destination)
        except OSError:
            pass
        return jsonify({'success': False, 'message': str(exc)}), 400
    file_hash = sha256_file(destination)
    duplicate = TechnicalFile.query.filter_by(sha256=file_hash).first()
    contribution = FileContribution(
        user_id=current_user.id,
        status='duplicate' if duplicate else 'pending_review',
        original_filename=original,
        temp_path=destination,
        sha256=file_hash,
        title=sanitize_input(str(request.form.get('title') or ''))[:200] or None,
        board_code=format_board_code(request.form.get('board_code')),
        notes=sanitize_input(str(request.form.get('notes') or ''))[:2000] or None,
    )
    db.session.add(contribution)
    db.session.commit()
    message = 'Este arquivo já existe no acervo e foi marcado como duplicado.' if duplicate else 'Arquivo enviado para revisão administrativa.'
    return jsonify({'success': True, 'message': message, 'status': contribution.status}), 201

@app.route('/admin/posts/<int:post_id>/toggle-active', methods=['POST'])
@login_required
@editor_required
def admin_toggle_post_active(post_id):
    """Ativar/Desativar um post"""
    post = Post.query.get_or_404(post_id)

    try:
        post.is_active = not post.is_active
        if post.scheduled_publication and post.scheduled_publication.status == 'pending':
            post.scheduled_publication.status = 'cancelled'
        db.session.commit()

        status = "ativado" if post.is_active else "desativado"
        flash(f'Post "{post.title}" foi {status} com sucesso!', 'success')

        return jsonify({
            'success': True,
            'is_active': post.is_active,
            'message': f'Post {status} com sucesso!'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro ao alterar status: {str(e)}'
        }), 500

@app.route('/admin/posts/<int:post_id>/delete', methods=['POST'])
@login_required
@editor_required
def admin_delete_post(post_id):
    """Excluir um post"""
    post = Post.query.get_or_404(post_id)
    post_title = post.title

    try:
        if post.scheduled_publication:
            db.session.delete(post.scheduled_publication)

        # Deletar imagem do Cloudinary ou filesystem
        if post.image_url:
            if 'cloudinary.com' in post.image_url:
                delete_from_cloudinary(post.image_url)
            else:
                delete_old_image(post.image_url)

        db.session.delete(post)
        db.session.commit()
        if _is_ajax_request():
            return jsonify({
                'success': True,
                'message': f'Post "{post_title}" foi excluído com sucesso!',
                'post_id': post_id,
                'stats': get_admin_posts_overview()
            })
        flash(f'Post "{post_title}" foi excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        if _is_ajax_request():
            return jsonify({'success': False, 'message': f'Erro ao excluir o post: {str(e)}'}), 500
        flash('Erro ao excluir o post. Tente novamente.', 'error')

    # Redireciona para a página de listagem de posts após exclusão
    return redirect(url_for('admin_posts'))

@app.route('/admin/posts/<int:post_id>/duplicate', methods=['POST'])
@login_required
@editor_required
def admin_duplicate_post(post_id):
    """Duplicar um post"""
    original_post = Post.query.get_or_404(post_id)

    try:
        # Gerar slug único para a cópia
        base_slug = generate_slug(f"{original_post.title} (Cópia)")
        slug = base_slug
        counter = 1
        while Post.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        # A imagem duplicada mantém a mesma URL do Cloudinary (não precisa copiar)
        # URLs do Cloudinary podem ser usadas por múltiplos posts
        duplicated_image_url = original_post.image_url

        # Criar uma cópia do post
        new_post = Post(
            title=f"{original_post.title} (Cópia)",
            content=original_post.content,
            category_id=original_post.category_id,
            category_str=original_post.category_str,
            subcategory=original_post.subcategory,
            download_link=original_post.download_link,
            image_url=duplicated_image_url,
            featured=False,  # Cópias não são destacadas por padrão
            is_active=False,  # Cópias ficam inativas por padrão
            author_id=current_user.id,
            views=0,
            downloads=0,
            tags=original_post.tags,
            seo_title=original_post.seo_title,
            seo_description=original_post.seo_description,
            slug=slug
        )
        for field_name in POST_TECHNICAL_FIELDS:
            setattr(new_post, field_name, getattr(original_post, field_name))
        new_post.sha256 = original_post.sha256
        new_post.last_verified_at = original_post.last_verified_at
        new_post.verification_status = original_post.verification_status

        db.session.add(new_post)

        original_download_files = original_post.get_metadata('download_files')
        if isinstance(original_download_files, list) and original_download_files:
            new_post.set_metadata('download_files', original_download_files)

        db.session.commit()

        # Log da atividade
        log_admin_activity(
            user_id=current_user.id,
            action='duplicate_post',
            description=f'Duplicou o post "{original_post.title}"',
            metadata={
                'original_post_id': post_id,
                'new_post_id': new_post.id,
                'original_title': original_post.title,
                'new_title': new_post.title
            }
        )

        if _is_ajax_request():
            return jsonify({
                'success': True,
                'message': f'Post "{original_post.title}" foi duplicado com sucesso!',
                'post': serialize_post_for_admin(new_post),
                'stats': get_admin_posts_overview()
            })

        flash(f'Post "{original_post.title}" foi duplicado com sucesso!', 'success')
        return redirect(url_for('admin_posts'))

    except Exception as e:
        db.session.rollback()
        if _is_ajax_request():
            return jsonify({'success': False, 'message': f'Erro ao duplicar o post: {str(e)}'}), 500
        flash(f'Erro ao duplicar o post: {str(e)}', 'error')
        return redirect(url_for('admin_posts'))

@app.route('/admin/posts/<int:post_id>/data')
@login_required
@editor_required
def admin_post_data(post_id):
    """Retorna dados do post em JSON para edição"""
    post = Post.query.get_or_404(post_id)

    technical_data = {
        field_name: getattr(post, field_name)
        for field_name in POST_TECHNICAL_FIELDS
    }
    technical_data.update({
        'sha256': post.sha256 or '',
        'verification_status': post.verification_status or 'unverified',
        'last_verified_at': post.last_verified_at.strftime('%Y-%m-%d') if post.last_verified_at else '',
    })

    return jsonify({
        'id': post.id,
        'title': post.title,
        'content': post.content,
        'category_id': post.category_id,
        'category_str': post.category_str,
        'subcategory': post.subcategory,
        'download_link': post.download_link,
        'image_url': post.image_url,
        'image_preview_url': get_image_url_for_response(post.image_url, folder='posts', default='default.jpg'),
        'featured': post.featured,
        'is_active': post.is_active,
        'author_id': post.author_id,
        'views': post.views,
        'downloads': post.downloads,
        'date_posted': post.date_posted.isoformat() if post.date_posted else None,
        'tags': post.tags,
        'seo_title': post.seo_title,
        'seo_description': post.seo_description,
        'custom_metadata': post.get_metadata() or {},
        **technical_data,
    })

@app.route('/admin/posts/<int:post_id>/update', methods=['POST'])
@login_required
@editor_required
def admin_update_post(post_id):
    """Atualiza dados do post"""
    try:
        post = Post.query.get_or_404(post_id)

        # Obter dados do formulário
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        category_id = request.form.get('category_id')
        download_link = request.form.get('download_link', '').strip()
        download_files_json = request.form.get('download_files', '')
        image_url = request.form.get('image_url', '').strip()
        tags = request.form.get('tags', '').strip()
        seo_title = request.form.get('seo_title', '').strip()
        seo_description = request.form.get('seo_description', '').strip()
        featured = request.form.get('featured') == 'true'
        is_active = request.form.get('is_active') == 'true'

        # Validações
        if download_link and not normalize_download_url(download_link):
            return jsonify({'success': False, 'message': 'Link de download inválido.'}), 400
        if not title:
            return jsonify({'success': False, 'message': 'Título é obrigatório'})

        if not content:
            return jsonify({'success': False, 'message': 'Conteúdo é obrigatório'})

        # Processar upload de imagem se fornecido
        image_file = request.files.get('image_file')
        if image_file and image_file.filename:
            # Validar extensão
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            file_ext = image_file.filename.rsplit('.', 1)[1].lower() if '.' in image_file.filename else ''

            if file_ext not in allowed_extensions:
                return jsonify({'success': False, 'message': 'Formato de imagem não permitido. Use: PNG, JPG, GIF, WebP'})

            # Deletar imagem antiga do Cloudinary se existir
            if post.image_url and post.image_url != 'post-placeholder.svg' and post.image_url.startswith('https://res.cloudinary.com'):
                delete_from_cloudinary(post.image_url)

            # Upload para Cloudinary
            success, result = upload_to_cloudinary(image_file, folder='posts')

            if success:
                image_url = result  # URL do Cloudinary
            else:
                return jsonify({'success': False, 'message': f'Erro ao fazer upload da imagem: {result}'})

        elif image_url and image_url != post.image_url:
            # Se o image_url foi alterado (nova URL externa)
            # Deletar imagem antiga do Cloudinary se existir
            if post.image_url and post.image_url != 'post-placeholder.svg' and post.image_url.startswith('https://res.cloudinary.com'):
                delete_from_cloudinary(post.image_url)

        # Atualizar dados
        old_data = {
            'title': post.title,
            'content': post.content,
            'category_id': post.category_id,
            'download_link': post.download_link,
            'image_url': post.image_url,
            'featured': post.featured,
            'is_active': post.is_active
        }

        # Se o título mudou, gerar novo slug
        if post.title != title:
            base_slug = generate_slug(title)
            slug = base_slug
            counter = 1
            while Post.query.filter_by(slug=slug).filter(Post.id != post_id).first():
                slug = f"{base_slug}-{counter}"
                counter += 1
            post.slug = slug

        category = Category.query.get(int(category_id)) if category_id else None

        post.title = title
        post.content = content
        post.category_id = int(category_id) if category_id else None
        post.category_str = category.name if category else 'Sem categoria'
        post.download_link = download_link if download_link else None
        post.image_url = image_url if image_url else 'post-placeholder.svg'
        post.featured = featured
        post.is_active = is_active
        if is_active and post.scheduled_publication and post.scheduled_publication.status == 'pending':
            post.scheduled_publication.status = 'cancelled'
        post.tags = tags or None
        post.seo_title = seo_title or None
        post.seo_description = seo_description or None
        post.date_updated = datetime.utcnow()
        apply_post_technical_form(post, request.form, preserve_missing=True)

        # Armazenar download_files no custom_metadata
        if download_files_json:
            download_files = normalize_download_files(download_files_json)
            if download_files:
                post.set_metadata('download_files', download_files)
                sync_post_download_summary(post, download_files)
                if not download_link:
                    post.download_link = download_files[0]['url']

        db.session.commit()

        # Log da atividade

        log_admin_activity(
            current_user.id,
            'update_post',
            f'Atualizou post: {post.title}',
            metadata={'old': old_data, 'new': request.form.to_dict()}
        )

        return jsonify({
            'success': True,
            'message': 'Post atualizado com sucesso!',
            'post': serialize_post_for_admin(post),
            'stats': get_admin_posts_overview()
        })

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao atualizar post: {str(e)}'}), 500


@app.route('/admin/posts/<int:post_id>/quick-update', methods=['POST'])
@login_required
@editor_required
def admin_quick_update_post(post_id):
    """Atualiza categoria ou status diretamente pela tabela administrativa."""
    post = Post.query.get_or_404(post_id)
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({'success': False, 'message': 'JSON inválido.'}), 400

    changed_fields = []

    try:
        if 'category_id' in data:
            raw_category_id = data.get('category_id')
            if raw_category_id in (None, ''):
                post.category_id = None
                post.category_str = 'Sem categoria'
            else:
                try:
                    category_id = int(raw_category_id)
                except (TypeError, ValueError):
                    return jsonify({'success': False, 'message': 'Categoria inválida.'}), 400

                category = db.session.get(Category, category_id)
                if not category:
                    return jsonify({'success': False, 'message': 'Categoria não encontrada.'}), 404

                post.category_id = category.id
                post.category_str = category.name
            changed_fields.append('categoria')

        if 'status' in data:
            status = str(data.get('status') or '').strip().lower()
            if status == 'featured':
                post.is_active = True
                post.featured = True
            elif status == 'active':
                post.is_active = True
                post.featured = False
            elif status == 'inactive':
                post.is_active = False
                post.featured = False
            else:
                return jsonify({'success': False, 'message': 'Status inválido.'}), 400
            if post.scheduled_publication and post.scheduled_publication.status == 'pending':
                post.scheduled_publication.status = 'cancelled'
            changed_fields.append('status')

        if not changed_fields:
            return jsonify({'success': False, 'message': 'Nenhuma alteração informada.'}), 400

        post.date_updated = datetime.utcnow()
        db.session.commit()

        try:
            log_admin_activity(
                current_user.id,
                'quick_update_post',
                f'Atualizou {" e ".join(changed_fields)} do post: {post.title}',
                metadata={'post_id': post.id, 'fields': changed_fields}
            )
        except Exception as log_error:
            app.logger.warning('Erro ao registrar atualização rápida do post: %s', log_error)

        if changed_fields == ['categoria']:
            success_message = 'Categoria atualizada com sucesso!'
        elif changed_fields == ['status']:
            success_message = 'Status atualizado com sucesso!'
        else:
            success_message = 'Categoria e status atualizados com sucesso!'
        return jsonify({
            'success': True,
            'message': success_message,
            'post': serialize_post_for_admin(post),
            'stats': get_admin_posts_overview()
        })
    except Exception as exc:
        db.session.rollback()
        app.logger.exception('Erro ao atualizar post rapidamente')
        return jsonify({'success': False, 'message': f'Erro ao atualizar post: {str(exc)}'}), 500


@app.route('/admin/posts/<int:post_id>/toggle-featured', methods=['POST'])
@login_required
@editor_required
def admin_toggle_featured(post_id):
    """Alternar status de destaque do post"""
    post = Post.query.get_or_404(post_id)

    try:
        post.featured = not post.featured
        db.session.commit()
        status = 'destacado' if post.featured else 'removido dos destaques'
        flash(f'Post "{post.title}" foi {status}!', 'success')
    except Exception:
        db.session.rollback()
        flash('Erro ao atualizar o post. Tente novamente.', 'error')

    return redirect(url_for('admin_dashboard'))

# Função para criar script de atualização do banco de dados
def create_db_upgrade_script(script_path):
    """
    Cria um script auxiliar para migração do banco de dados
    quando são detectadas alterações no esquema.
    """
    script_content = '''
# Script para migração de banco de dados
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand
import sys
import os

# Importar a aplicação principal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import app, db
    print("Aplicação importada com sucesso!")
except Exception as e:
    print(f"Erro ao importar a aplicação: {e}")
    sys.exit(1)

# Inicializar Flask-Migrate
migrate = Migrate(app, db)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'init':
            # Iniciar repositório de migração
            os.system('flask db init')
            print("Repositório de migração inicializado")

        elif sys.argv[1] == 'migrate':
            # Gerar migração
            os.system('flask db migrate -m "Migração automática"')
            print("Migração gerada. Verifique o arquivo e faça ajustes se necessário.")

        elif sys.argv[1] == 'upgrade':
            # Aplicar migração
            os.system('flask db upgrade')
            print("Migração aplicada com sucesso")

        elif sys.argv[1] == 'all':
            # Executar todo o processo
            os.system('flask db init')
            os.system('flask db migrate -m "Migração automática"')
            os.system('flask db upgrade')
            print("Processo completo de migração executado")

        else:
            print("Comando não reconhecido. Use: init, migrate, upgrade ou all")
    else:
        print("Uso: python db_upgrade.py [comando]")
        print("Comandos disponíveis:")
        print("  init     - Inicializa o repositório de migração")
        print("  migrate  - Gera scripts de migração baseado nas alterações dos modelos")
        print("  upgrade  - Aplica migrações pendentes ao banco de dados")
        print("  all      - Executa todo o processo (init, migrate, upgrade)")
'''
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content.strip())

# Inicialização do banco de dados SQLite
# Inicialização do banco de dados SQLite
def initialize_db():
    """Inicializa o banco de dados SQLite"""
    try:
        # Criar diretório instance se necessário
        instance_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')
        os.makedirs(instance_dir, exist_ok=True)

        db_path = os.path.join(instance_dir, 'site.db')
        db_exists = os.path.exists(db_path)

        app.logger.info('Banco SQLite %s em %s', 'encontrado' if db_exists else 'sera criado', db_path)

        # Criar todas as tabelas
        db.create_all()
        app.logger.info('Tabelas SQLite criadas/verificadas')

        # Adicionar configurações iniciais do site se não existirem
        if SiteConfig.query.count() == 0:
            default_configs = [
                SiteConfig(key='site_name', value='Mundo da Informática'),
                SiteConfig(
                    key='site_description',
                    value='Biblioteca técnica de BIOS, EC, BoardView, esquemas e recursos para profissionais de manutenção.',
                ),
                SiteConfig(key='contact_email', value=DEFAULT_SUPPORT_EMAIL),
                SiteConfig(key='contact_phone', value='(21) 97879-4705'),
                SiteConfig(key='admin_email', value='admin@mundodainformatica.com'),
                SiteConfig(key='site_keywords', value='tecnologia, informática, downloads, software'),
                SiteConfig(key='enable_comments', value='true'),
                SiteConfig(key='posts_per_page', value='10'),
                SiteConfig(key='site_theme', value='default'),
                SiteConfig(key='social_links', value=json.dumps({
                    'facebook': '',
                    'instagram': '',
                    'twitter': '',
                    'youtube': 'https://www.youtube.com/@_RDTech'
                }), value_type='json'),
                SiteConfig(
                    key='download_file_types',
                    value=json.dumps([dict(item) for item in DEFAULT_DOWNLOAD_FILE_TYPES]),
                    value_type='json',
                    description='Tipos disponíveis no dropdown de links de download',
                    is_public=False
                ),
                SiteConfig(key='plan_price_premium', value='29.90', value_type='float'),
                SiteConfig(key='plan_price_vip', value='49.90', value_type='float')
            ]

            for config in default_configs:
                db.session.add(config)

            app.logger.info('Configuracoes iniciais do site adicionadas')

        # Adicionar categorias padrão que não existirem
        default_categories = [
            {'name': 'BIOS', 'slug': 'bios', 'description': 'Atualizações e tutoriais de BIOS', 'order': 1},
            {'name': 'Esquemas', 'slug': 'esquemas', 'description': 'Esquemas elétricos de notebooks e placas-mãe', 'order': 2},
            {'name': 'Drivers', 'slug': 'drivers', 'description': 'Drivers para diversos dispositivos', 'order': 3},
            {'name': 'Softwares', 'slug': 'softwares', 'description': 'Programas e aplicativos úteis', 'order': 4},
            {'name': 'Impressoras', 'slug': 'impressoras', 'description': 'Drivers e softwares para impressoras', 'order': 5},
            {'name': 'Cursos', 'slug': 'cursos', 'description': 'Cursos e materiais de estudo', 'order': 6},
            {'name': 'Datasheet', 'slug': 'datasheet', 'description': 'Datasheets técnicos de componentes eletrônicos', 'order': 7},
        ]

        existing_slugs = {c.slug for c in Category.query.with_entities(Category.slug).all()}
        added_count = 0
        for cat_data in default_categories:
            if cat_data['slug'] not in existing_slugs:
                db.session.add(Category(
                    name=cat_data['name'],
                    slug=cat_data['slug'],
                    description=cat_data['description'],
                    is_active=True,
                    order=cat_data['order']
                ))
                added_count += 1
                app.logger.info('Categoria padrao adicionada: %s', cat_data['name'])

        if added_count > 0:
            app.logger.info('%s categoria(s) padrao adicionada(s)', added_count)
        else:
            app.logger.debug('Todas as categorias padrao ja existem')

        # Salvar todas as configurações
        db.session.commit()
        app.logger.info('Banco SQLite inicializado')

        # Exibir estatísticas
        app.logger.info(
            'Status do banco: posts=%s categorias=%s usuarios=%s',
            Post.query.count(), Category.query.count(), User.query.count()
        )

    except Exception as e:
        db.session.rollback()
        app.logger.exception('Erro na inicializacao do banco: %s', e)


# Rota de login
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("30 per minute")  # Limitar tentativas de login
def login():
    # Se o usuário já estiver logado, redirecione para a página inicial
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username_email = request.form.get('username_email', '').strip()
        password = request.form.get('password', '')
        remember = True if request.form.get('remember') else False

        # Validação de entrada
        if not username_email or not password:
            flash('Por favor, preencha todos os campos', 'danger')
            return redirect(url_for('login'))

        # Sanitizar input de username/email
        username_email = bleach.clean(username_email, tags=[], strip=True)

        # Limitar tamanho do input
        if len(username_email) > 255 or len(password) > 128:
            flash('Dados inválidos', 'danger')
            return redirect(url_for('login'))

        # Verificar se é um email ou nome de usuário
        if '@' in username_email:
            # Login com email
            user = User.query.filter_by(email=username_email).first()
        else:
            # Login com nome de usuário
            user = User.query.filter_by(username=username_email).first()

        # Verificar se o usuário existe
        if not user:
            flash('Usuário não encontrado. Verifique suas credenciais e tente novamente.', 'danger')
            return redirect(url_for('login'))

        # Verificar senha
        if not user.verify_password(password):
            flash('Senha incorreta. Por favor, tente novamente.', 'danger')
            return redirect(url_for('login'))

        # Verificar se a conta está ativa
        if not user.is_active:
            flash('Esta conta está desativada. Entre em contato com o administrador.', 'danger')
            return redirect(url_for('login'))

        # Verificar limite de dispositivos simultâneos antes do login
        allowed, device_message = check_device_limit(user)
        if not allowed:
            flash(device_message, 'warning')
            return redirect(url_for('plans'))

        # Login bem-sucedido
        login_user(user, remember=remember)

        # Incrementar sessões ativas
        user.active_sessions = (user.active_sessions or 0) + 1

        # Atualizar a data do último login e dados de rastreamento
        user.last_login = datetime.utcnow()
        # Capturar dados de rastreamento (sanitizado) e parseado corretamente
        user_agent = parse_ua(request.user_agent.string)
        user.ip_address = request.remote_addr or 'unknown'
        user.browser = f"{user_agent.browser.family} {user_agent.browser.version_string}"
        user.operating_system = f"{user_agent.os.family} {user_agent.os.version_string}"
        # Fallback safe
        if len(user.browser) > 50: user.browser = user.browser[:50]
        if len(user.operating_system) > 50: user.operating_system = user.operating_system[:50]
        user.referrer = (request.referrer or 'Direct Access')[:500]  # Limitar tamanho
        db.session.commit()

        flash('Login realizado com sucesso!', 'success')
        flask_session['analytics_event'] = 'login'

        # Redirecionar para a página que o usuário tentou acessar ou para o dashboard
        next_page = request.args.get('next')
        try:
            parsed = url_parse(next_page) if next_page else None
            if not next_page or (parsed and parsed.netloc != ''):
                if user.role in ('admin', 'editor'):
                    next_page = url_for('admin_dashboard')
                else:
                    next_page = url_for('home')
        except (ValueError, TypeError, AttributeError):
            # Fallback se houver problema com url_parse
            if user.role in ('admin', 'editor'):
                next_page = url_for('admin_dashboard')
            else:
                next_page = url_for('home')

        return redirect(next_page)

    return render_template('login.html', title='Login')


@app.route('/auth/google', methods=['POST'])
@limiter.limit("20 per minute")
def auth_google():
    """
    Login/Cadastro via Google utilizando token validado pelo Firebase Admin.
    """
    payload = request.get_json(silent=True) or {}
    id_token = (payload.get('idToken') or '').strip()
    requested_next = (payload.get('next') or request.args.get('next') or '').strip()

    if not id_token:
        return jsonify({'success': False, 'message': 'Token Google ausente.'}), 400

    decoded = verify_firebase_google_token(id_token)
    if not decoded:
        return jsonify({'success': False, 'message': 'Falha ao validar autenticação Google.'}), 401

    email = (decoded.get('email') or '').strip().lower()
    if not email:
        return jsonify({'success': False, 'message': 'Conta Google sem email válido.'}), 400

    if not decoded.get('email_verified', False):
        return jsonify({'success': False, 'message': 'Confirme seu email no Google para continuar.'}), 400

    display_name = bleach.clean((decoded.get('name') or '').strip(), tags=[], strip=True)[:100]
    first_name, last_name = split_full_name(display_name)
    photo_url = (decoded.get('picture') or '').strip()

    user = User.query.filter_by(email=email).first()
    created_with_google = user is None

    try:
        if user is None:
            username_seed = display_name or email.split('@')[0] or 'google_user'
            username = get_unique_username(username_seed, fallback_prefix='google')

            user = User(
                username=username,
                email=email,
                name=display_name or username,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                is_verified=True,
                plan='free',
                date_joined=datetime.utcnow(),
            )
            user.set_password(secrets.token_urlsafe(32))

            if photo_url.startswith('http://') or photo_url.startswith('https://'):
                user.profile_image = photo_url

            db.session.add(user)
            db.session.flush()

        if not user.is_active:
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Esta conta está desativada. Entre em contato com o administrador.'}), 403

        # Verificar limite de dispositivos
        allowed, device_message = check_device_limit(user)
        if not allowed:
            db.session.rollback()
            return jsonify({'success': False, 'message': device_message, 'redirect_url': url_for('plans')}), 403

        login_user(user, remember=True)
        user.active_sessions = (user.active_sessions or 0) + 1
        user.last_login = datetime.utcnow()

        user_agent = parse_ua(request.user_agent.string)
        user.ip_address = request.remote_addr or 'unknown'
        user.browser = f"{user_agent.browser.family} {user_agent.browser.version_string}"[:50]
        user.operating_system = f"{user_agent.os.family} {user_agent.os.version_string}"[:50]
        user.referrer = (request.referrer or 'Google Sign-In')[:500]

        db.session.commit()
        flask_session['analytics_event'] = 'sign_up' if created_with_google else 'login'
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Erro no login Google: {e}')
        return jsonify({'success': False, 'message': 'Não foi possível autenticar com Google agora.'}), 500

    # Redirecionamento seguro
    redirect_url = ''
    try:
        parsed = url_parse(requested_next) if requested_next else None
        if requested_next and parsed and parsed.netloc == '':
            redirect_url = requested_next
    except (ValueError, TypeError, AttributeError):
        redirect_url = ''

    if not redirect_url:
        redirect_url = url_for('admin_dashboard') if user.role in ('admin', 'editor') else url_for('home')

    return jsonify({
        'success': True,
        'message': 'Login com Google realizado com sucesso!',
        'redirect_url': redirect_url
    })


@app.route('/api/chat/firebase-token', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
def chat_firebase_token():
    """
    Gera token customizado do Firebase para o chat em tempo real.
    Somente usuários autenticados no site podem obter este token.
    """
    if not current_user.is_active:
        return jsonify({'success': False, 'message': 'Conta desativada.'}), 403

    if firebase_auth is None:
        return jsonify({'success': False, 'message': 'Firebase Admin indisponível no servidor.'}), 503

    if not is_firebase_admin_configured():
        return jsonify({'success': True, 'token': '', 'uid': '', 'chatUnavailable': True, 'chatDisabled': True})

    if not initialize_firebase_admin():
        return jsonify({
            'success': False,
            'message': 'Chat temporariamente indisponível.',
            'chatUnavailable': True
        }), 503, {'Retry-After': '30'}

    try:
        firebase_uid = f"site_user_{current_user.id}"
        additional_claims = {
            'site_user_id': str(current_user.id),
            'site_role': str(current_user.role or 'user')
        }
        token = firebase_auth.create_custom_token(firebase_uid, additional_claims)
        token_str = token.decode('utf-8') if isinstance(token, bytes) else str(token)
        return jsonify({'success': True, 'token': token_str, 'uid': firebase_uid})
    except Exception as e:
        app.logger.error(f'Erro ao criar token customizado do chat: {e}')
        return jsonify({'success': False, 'message': 'Não foi possível conectar ao chat agora.'}), 500


# ---------------------------------------------------------------------------
# Circuit breaker para Firestore – evita crash loop quando quota é atingida.
# Usa arquivo em /tmp para que o estado persista entre restarts de workers
# do gunicorn (variáveis in-memory se perdem quando o master mata o worker).
# Quando uma chamada transitória falha (429/timeout/rede), o circuito abre por 30s
# e _get_firestore_client() retorna None → rotas de chat respondem 503
# imediatamente sem tentar gRPC → worker não bloqueia → site funciona.
# ---------------------------------------------------------------------------
import os as _cb_os
import time as _cb_time

_FIRESTORE_CIRCUIT_FILE = '/tmp/_firestore_circuit_open'
_FIRESTORE_CIRCUIT_COOLDOWN = 30


def _is_firestore_circuit_open() -> bool:
    try:
        if _cb_os.path.exists(_FIRESTORE_CIRCUIT_FILE):
            mtime = _cb_os.path.getmtime(_FIRESTORE_CIRCUIT_FILE)
            if _cb_time.time() - mtime < _FIRESTORE_CIRCUIT_COOLDOWN:
                return True
            _cb_os.unlink(_FIRESTORE_CIRCUIT_FILE)
    except OSError:
        pass
    return False


def _is_transient_firestore_error(error: BaseException) -> bool:
    """Distingue falhas recuperáveis de erros de regra/configuração."""
    if google_api_exceptions is not None:
        transient_types = tuple(
            error_type
            for error_type in (
                getattr(google_api_exceptions, 'DeadlineExceeded', None),
                getattr(google_api_exceptions, 'ResourceExhausted', None),
                getattr(google_api_exceptions, 'ServiceUnavailable', None),
                getattr(google_api_exceptions, 'TooManyRequests', None),
                getattr(google_api_exceptions, 'InternalServerError', None)
            )
            if isinstance(error_type, type)
        )
        if transient_types and isinstance(error, transient_types):
            return True

    normalized_message = str(error or '').casefold()
    return any(marker in normalized_message for marker in (
        '429', '503', 'deadline exceeded', 'quota', 'resource exhausted',
        'service unavailable', 'temporarily unavailable', 'timeout',
        'timed out', 'connection reset', 'connection aborted'
    ))


def _trip_firestore_circuit(error: BaseException | None = None) -> None:
    if error is not None and not _is_transient_firestore_error(error):
        app.logger.warning('[CHAT] Falha não transitória não abriu o circuito: %s', error)
        return

    try:
        with open(_FIRESTORE_CIRCUIT_FILE, 'w') as f:
            f.write(str(_cb_time.time()))
    except OSError:
        pass
    app.logger.warning(
        f'[CHAT] Circuit breaker ABERTO (arquivo) por {_FIRESTORE_CIRCUIT_COOLDOWN}s '
        f'– nova tentativa automática após o cooldown.'
    )


def _get_firestore_client():
    if firebase_firestore is None:
        return None
    if not is_firebase_admin_configured():
        return None
    if not initialize_firebase_admin():
        return None
    if _is_firestore_circuit_open():
        return None
    try:
        return firebase_firestore.client()
    except Exception as e:
        app.logger.error(f'Erro ao obter cliente Firestore: {e}')
        _trip_firestore_circuit(e)
        return None


def _get_firestore_document_snapshot(document_ref):
    # O SDK do Firestore expõe tipos dinâmicos e o Pylance pode inferir a variante assíncrona aqui.
    # Fazemos o cast para manter o comportamento síncrono real usado pelo projeto.
    return cast(Any, document_ref.get(timeout=10))


def _delete_chat_room_recursive(db_firestore, room_id: str) -> None:
    room_ref = db_firestore.collection('chat_rooms').document(room_id)
    messages = list(room_ref.collection('messages').stream(timeout=10))

    if messages:
        batch = db_firestore.batch()
        operations = 0
        for message_doc in messages:
            batch.delete(message_doc.reference)
            operations += 1
            if operations >= 400:
                batch.commit(timeout=10)
                batch = db_firestore.batch()
                operations = 0
        if operations:
            batch.commit(timeout=10)

    room_ref.delete(timeout=10)


def _firestore_server_timestamp():
    if firebase_firestore is None:
        return None
    # Evita warning de tipagem do Pylance para atributo dinâmico do SDK.
    server_timestamp = getattr(firebase_firestore, 'SERVER_TIMESTAMP', None)
    return server_timestamp


def _firestore_timestamp_to_millis(value):
    if value is None:
        return 0

    timestamp_method = getattr(value, 'timestamp', None)
    if callable(timestamp_method):
        try:
            timestamp_seconds = timestamp_method()
            if isinstance(timestamp_seconds, (int, float)):
                return int(timestamp_seconds * 1000)
        except Exception:
            return 0

    return 0


def _is_chat_admin(user) -> bool:
    return bool(getattr(user, 'role', '') == 'admin')


def _get_chat_support_room_id(user_id: int | str) -> str:
    return f"support_user_{user_id}"


def _extract_chat_support_owner_id(room_id: str) -> str:
    room_value = str(room_id or '')
    if not room_value.startswith('support_user_'):
        return ''
    return room_value.replace('support_user_', '', 1)


def _chat_actor_name(user) -> str:
    return (user.get_full_name() or user.username or f'Usuario {user.id}')[:80]


def _chat_actor_role(user) -> str:
    return 'admin' if _is_chat_admin(user) else 'user'


def _can_user_write_public_chat(user) -> bool:
    # O cargo administrativo não altera benefícios comerciais do plano.
    return bool(can_use_public_chat(user))


def _get_chat_permissions_for_user(user) -> dict[str, Any]:
    has_public_chat_access = _can_user_write_public_chat(user)
    return {
        'public_read': has_public_chat_access,
        'public_write': has_public_chat_access,
        # O atendimento individual existe em todos os planos; prioridade e SLA
        # continuam sendo definidos pela matriz comercial do plano.
        'support_read': True,
        'support_write': True,
        'vip_area': bool(get_plan_entitlements(user)['vip_area'])
    }


def _chat_disabled_payload_for_user(user) -> dict[str, Any]:
    support_room_id = _get_chat_support_room_id(user.id)
    return {
        'success': True,
        'chatUnavailable': True,
        'chatDisabled': True,
        'message': 'Chat nao configurado no servidor.',
        'todos_room_id': CHAT_PUBLIC_ROOM_ID,
        'support_room_id': support_room_id,
        'is_admin': _is_chat_admin(user),
        'permissions': _get_chat_permissions_for_user(user),
        'rooms': {
            'todos': _serialize_chat_room(CHAT_PUBLIC_ROOM_ID, {}),
            'support': _serialize_chat_room(support_room_id, {})
        },
        'tickets': []
    }


def _chat_backend_unavailable_response(user):
    """Separa chat não configurado de uma interrupção temporária recuperável."""
    if not is_firebase_admin_configured():
        return jsonify(_chat_disabled_payload_for_user(user))

    return jsonify({
        'success': False,
        'chatUnavailable': True,
        'chatDisabled': False,
        'message': 'Chat temporariamente indisponível. Tentando reconectar...',
        'permissions': _get_chat_permissions_for_user(user)
    }), 503, {'Retry-After': str(_FIRESTORE_CIRCUIT_COOLDOWN)}


def _validate_chat_room_access(user, room_id: str, *, write: bool = False) -> tuple[bool, str, int]:
    normalized_room_id = str(room_id or '').strip()
    if not normalized_room_id:
        return False, 'Sala de chat inválida.', 400

    if normalized_room_id == CHAT_PUBLIC_ROOM_ID:
        permissions = _get_chat_permissions_for_user(user)
        permission_key = 'public_write' if write else 'public_read'
        if not permissions[permission_key]:
            return (
                False,
                'A sala Todos é exclusiva para assinantes VIP. Use a aba Suporte ou assine o plano VIP para participar.',
                403
            )
        return True, '', 200

    owner_id = _extract_chat_support_owner_id(normalized_room_id)
    if owner_id:
        if _is_chat_admin(user) or owner_id == str(user.id):
            return True, '', 200
        return False, 'Este chamado pertence a outro usuário.', 403

    return False, 'Sala de chat inválida.', 400


def _serialize_chat_room(room_id: str, data: Mapping[str, Any] | None) -> dict[str, Any]:
    room_data = dict(data or {})
    return {
        'id': str(room_data.get('id') or room_id),
        'type': str(room_data.get('type') or ('public' if room_id == CHAT_PUBLIC_ROOM_ID else 'support')),
        'name': str(room_data.get('name') or ('Todos' if room_id == CHAT_PUBLIC_ROOM_ID else 'Suporte')),
        'ownerName': str(room_data.get('ownerName') or ''),
        'ownerSiteUserId': str(room_data.get('ownerSiteUserId') or ''),
        'ownerPlan': normalize_plan_key(room_data.get('ownerPlan')),
        'lastMessage': str(room_data.get('lastMessage') or ''),
        'lastSender': str(room_data.get('lastSender') or ''),
        'lastSenderRole': str(room_data.get('lastSenderRole') or ''),
        'lastSenderSiteUserId': str(room_data.get('lastSenderSiteUserId') or ''),
        'lastSenderPlan': normalize_plan_key(room_data.get('lastSenderPlan')),
        'updatedAtMs': _firestore_timestamp_to_millis(room_data.get('updatedAt')) or int(room_data.get('updatedAtMs') or 0)
    }


def _serialize_chat_message(message_doc) -> dict[str, Any]:
    data = message_doc.to_dict() or {}
    return {
        'id': str(message_doc.id),
        'text': str(data.get('text') or ''),
        'senderName': str(data.get('senderName') or 'Usuario'),
        'senderAvatar': str(data.get('senderAvatar') or ''),
        'senderRole': str(data.get('senderRole') or 'user'),
        'senderPlan': normalize_plan_key(data.get('senderPlan')),
        'senderSiteUserId': str(data.get('senderSiteUserId') or ''),
        'senderAuthUid': str(data.get('senderAuthUid') or ''),
        'createdAtMs': _firestore_timestamp_to_millis(data.get('createdAt')),
        'editedAtMs': _firestore_timestamp_to_millis(data.get('editedAt')),
        'isEdited': bool(data.get('isEdited')),
        'replyToMessageId': str(data.get('replyToMessageId') or ''),
        'replyToSenderName': str(data.get('replyToSenderName') or ''),
        'replyToText': str(data.get('replyToText') or '')
    }


def _build_chat_room_metadata(room_id: str, actor_user, last_message: str, existing_room_data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    room_data = dict(existing_room_data or {})
    base_metadata = {
        'id': room_id,
        'updatedAt': _firestore_server_timestamp(),
        'lastMessage': str(last_message or '')[:140],
        'lastSender': _chat_actor_name(actor_user),
        'lastSenderRole': _chat_actor_role(actor_user),
        'lastSenderSiteUserId': str(actor_user.id),
        'lastSenderPlan': normalize_plan_key(actor_user.plan)
    }

    if room_id == CHAT_PUBLIC_ROOM_ID:
        return {
            **base_metadata,
            'type': 'public',
            'name': 'Todos'
        }

    owner_id = _extract_chat_support_owner_id(room_id)
    owner_name = str(room_data.get('ownerName') or _chat_actor_name(actor_user))
    owner_plan = normalize_plan_key(room_data.get('ownerPlan') or actor_user.plan)

    if owner_id and owner_id != str(actor_user.id):
        try:
            ticket_owner = db.session.get(User, int(owner_id))
        except (TypeError, ValueError):
            ticket_owner = None

        if ticket_owner is not None:
            owner_name = _chat_actor_name(ticket_owner)
            owner_plan = normalize_plan_key(ticket_owner.plan)

    return {
        **base_metadata,
        'type': 'support',
        'name': f'Suporte - {owner_name}',
        'ownerSiteUserId': owner_id or str(actor_user.id),
        'ownerName': owner_name,
        'ownerPlan': owner_plan
    }


def _sync_chat_room_metadata_from_latest(db_firestore, room_id: str) -> None:
    try:
        room_ref = db_firestore.collection('chat_rooms').document(room_id)
        room_snapshot = _get_firestore_document_snapshot(room_ref)
        existing_room_data = room_snapshot.to_dict() or {}
        query_direction = getattr(getattr(firebase_firestore, 'Query', None), 'DESCENDING', 'DESCENDING')
        latest_docs = list(
            room_ref.collection('messages')
            .order_by('createdAt', direction=query_direction)
            .limit(1)
            .stream(timeout=5)
        )

        if not latest_docs:
            serialized_room = _serialize_chat_room(room_id, existing_room_data)
            room_ref.set({
                'id': serialized_room['id'],
                'type': serialized_room['type'],
                'name': serialized_room['name'],
                'ownerName': serialized_room['ownerName'],
                'ownerSiteUserId': serialized_room['ownerSiteUserId'],
                'ownerPlan': serialized_room['ownerPlan'],
                'updatedAt': _firestore_server_timestamp(),
                'lastMessage': '',
                'lastSender': '',
                'lastSenderRole': '',
                'lastSenderSiteUserId': '',
                'lastSenderPlan': ''
            }, merge=True, timeout=5)
            return

        latest_data = latest_docs[0].to_dict() or {}
        actor_user = None
        sender_site_user_id = str(latest_data.get('senderSiteUserId') or '')
        if sender_site_user_id.isdigit():
            actor_user = db.session.get(User, int(sender_site_user_id))
        if actor_user is None:
            actor_user = current_user

        room_ref.set({
            **_build_chat_room_metadata(
                room_id,
                actor_user,
                str(latest_data.get('text') or ''),
                existing_room_data=existing_room_data
            ),
            'lastSender': str(latest_data.get('senderName') or ''),
            'lastSenderRole': str(latest_data.get('senderRole') or ''),
            'lastSenderSiteUserId': str(latest_data.get('senderSiteUserId') or ''),
            'lastSenderPlan': normalize_plan_key(latest_data.get('senderPlan'))
        }, merge=True, timeout=5)
    except BaseException as e:
        _trip_firestore_circuit(e)
        app.logger.warning(f'Firestore indisponível ao sincronizar metadados da sala {room_id}: {e}')


def _get_chat_support_tickets(db_firestore) -> list[dict[str, Any]]:
    tickets = []
    try:
        chat_rooms = db_firestore.collection('chat_rooms')
        if FirestoreFieldFilter is not None:
            query = chat_rooms.where(filter=FirestoreFieldFilter('type', '==', 'support'))
        else:
            query = chat_rooms.where('type', '==', 'support')
        docs = list(query.limit(100).stream(timeout=10))
    except BaseException as e:
        _trip_firestore_circuit(e)
        app.logger.warning(f'Firestore indisponível ao listar tickets de suporte: {e}')
        return tickets

    for doc in docs:
        data = doc.to_dict() or {}
        room_id = str(data.get('id') or doc.id)
        if not room_id.startswith('support_user_'):
            continue

        owner_site_user_id = str(data.get('ownerSiteUserId') or '')
        owner_plan = normalize_plan_key(data.get('ownerPlan'))
        if owner_site_user_id and owner_plan == 'free':
            try:
                ticket_owner = db.session.get(User, int(owner_site_user_id))
            except (TypeError, ValueError):
                ticket_owner = None

            if ticket_owner is not None:
                owner_plan = normalize_plan_key(ticket_owner.plan)

        tickets.append({
            'id': room_id,
            'data': {
                **_serialize_chat_room(room_id, data),
                'ownerPlan': owner_plan
            }
        })

    # VIP entra primeiro na fila, seguido de Premium e Grátis; dentro de cada
    # plano, o chamado mais recente aparece antes.
    support_priority = {'vip': 0, 'premium': 1, 'free': 2}
    tickets.sort(key=lambda item: (
        support_priority.get(normalize_plan_key(item['data'].get('ownerPlan')), 2),
        -int(item['data'].get('updatedAtMs') or 0),
    ))
    return tickets


# Cache in-memory para evitar escritas repetidas ao Firestore em cada request
_chat_rooms_ensured_cache: dict[str, float] = {}
_CHAT_ROOMS_CACHE_TTL = 300  # 5 minutos


def _ensure_chat_base_rooms_for_user(db_firestore, user) -> tuple[str, str]:
    import time as _time

    support_room_id = _get_chat_support_room_id(user.id)
    cache_key = f'{CHAT_PUBLIC_ROOM_ID}:{support_room_id}'
    now = _time.monotonic()

    # Se já garantimos as salas recentemente, pula as escritas no Firestore
    if cache_key in _chat_rooms_ensured_cache and (now - _chat_rooms_ensured_cache[cache_key]) < _CHAT_ROOMS_CACHE_TTL:
        return CHAT_PUBLIC_ROOM_ID, support_room_id

    owner_name = _chat_actor_name(user)
    owner_plan = normalize_plan_key(user.plan)
    server_timestamp = _firestore_server_timestamp()

    try:
        db_firestore.collection('chat_rooms').document(CHAT_PUBLIC_ROOM_ID).set({
            'id': CHAT_PUBLIC_ROOM_ID,
            'type': 'public',
            'name': 'Todos',
            'updatedAt': server_timestamp
        }, merge=True, timeout=5)

        db_firestore.collection('chat_rooms').document(support_room_id).set({
            'id': support_room_id,
            'type': 'support',
            'name': f'Suporte - {owner_name}',
            'ownerSiteUserId': str(user.id),
            'ownerName': owner_name,
            'ownerPlan': owner_plan,
            'updatedAt': server_timestamp
        }, merge=True, timeout=5)

        _chat_rooms_ensured_cache[cache_key] = now
    except BaseException as e:
        _trip_firestore_circuit(e)
        app.logger.warning(f'Firestore indisponível ao garantir salas de chat (quota/rede): {e}')
        # Mesmo com erro, retorna os IDs — as salas provavelmente já existem

    return CHAT_PUBLIC_ROOM_ID, support_room_id


@app.route('/api/chat/bootstrap', methods=['GET'])
@login_required
@limiter.limit("120 per minute")
def chat_bootstrap():
    """
    Garante as salas base do chat em tempo real usando credenciais de servidor.
    """
    if not current_user.is_active:
        return jsonify({'success': False, 'message': 'Conta desativada.'}), 403

    db_firestore = _get_firestore_client()
    if db_firestore is None:
        return _chat_backend_unavailable_response(current_user)

    try:
        todos_room_id, support_room_id = _ensure_chat_base_rooms_for_user(db_firestore, current_user)

        return jsonify({
            'success': True,
            'todos_room_id': todos_room_id,
            'support_room_id': support_room_id,
            'is_admin': _is_chat_admin(current_user),
            'permissions': _get_chat_permissions_for_user(current_user)
        })
    except BaseException as e:
        _trip_firestore_circuit(e)
        app.logger.error(f'Erro no bootstrap das salas de chat: {e}')
        return jsonify({'success': False, 'message': 'Chat temporariamente indisponível.', 'chatUnavailable': True}), 503, {'Retry-After': str(_FIRESTORE_CIRCUIT_COOLDOWN)}


@app.route('/api/chat/state', methods=['GET'])
@login_required
@limiter.limit("120 per minute")
def chat_state():
    if not current_user.is_active:
        return jsonify({'success': False, 'message': 'Conta desativada.'}), 403

    db_firestore = _get_firestore_client()
    if db_firestore is None:
        return _chat_backend_unavailable_response(current_user)

    try:
        todos_room_id, support_room_id = _ensure_chat_base_rooms_for_user(db_firestore, current_user)
        todos_snapshot = _get_firestore_document_snapshot(
            db_firestore.collection('chat_rooms').document(todos_room_id)
        )
        support_snapshot = _get_firestore_document_snapshot(
            db_firestore.collection('chat_rooms').document(support_room_id)
        )

        payload = {
            'success': True,
            'todos_room_id': todos_room_id,
            'support_room_id': support_room_id,
            'is_admin': _is_chat_admin(current_user),
            'permissions': _get_chat_permissions_for_user(current_user),
            'rooms': {
                'todos': _serialize_chat_room(todos_room_id, todos_snapshot.to_dict() if todos_snapshot.exists else {}),
                'support': _serialize_chat_room(support_room_id, support_snapshot.to_dict() if support_snapshot.exists else {})
            }
        }

        if _is_chat_admin(current_user):
            payload['tickets'] = _get_chat_support_tickets(db_firestore)

        return jsonify(payload)
    except BaseException as e:
        _trip_firestore_circuit(e)
        app.logger.error(f'Erro ao carregar estado do chat: {e}')
        return jsonify({'success': False, 'message': 'Chat temporariamente indisponível.', 'chatUnavailable': True}), 503, {'Retry-After': str(_FIRESTORE_CIRCUIT_COOLDOWN)}


@app.route('/api/chat/rooms/<string:room_id>/messages', methods=['GET', 'POST'])
@login_required
@limiter.limit("240 per minute")
def chat_room_messages(room_id):
    if not current_user.is_active:
        return jsonify({'success': False, 'message': 'Conta desativada.'}), 403

    db_firestore = _get_firestore_client()
    if db_firestore is None:
        return jsonify({'success': False, 'message': 'Chat temporariamente indisponível.', 'chatUnavailable': True}), 503, {'Retry-After': str(_FIRESTORE_CIRCUIT_COOLDOWN)}

    wants_write = request.method == 'POST'
    allowed, denial_message, denial_status = _validate_chat_room_access(current_user, room_id, write=wants_write)
    if not allowed:
        return jsonify({'success': False, 'message': denial_message}), denial_status

    try:
        _ensure_chat_base_rooms_for_user(db_firestore, current_user)
        room_ref = db_firestore.collection('chat_rooms').document(room_id)

        if request.method == 'GET':
            message_limit = request.args.get('limit', CHAT_MESSAGE_LIMIT, type=int) or CHAT_MESSAGE_LIMIT
            message_limit = max(1, min(message_limit, CHAT_MESSAGE_LIMIT))
            query_direction = getattr(getattr(firebase_firestore, 'Query', None), 'DESCENDING', 'DESCENDING')
            docs = room_ref.collection('messages').order_by('createdAt', direction=query_direction).limit(message_limit).stream(timeout=10)
            messages = [_serialize_chat_message(doc) for doc in docs]
            return jsonify({'success': True, 'messages': messages})

        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'JSON inválido.'}), 400

        text = sanitize_input(str(data.get('text') or ''))[:500].strip()
        if not text:
            return jsonify({'success': False, 'message': 'Digite uma mensagem para continuar.'}), 400

        payload = {
            'text': text,
            'senderName': _chat_actor_name(current_user),
            'senderAvatar': get_image_url_for_response(current_user.profile_image, folder='profiles', default='default_profile.jpg'),
            'senderRole': _chat_actor_role(current_user),
            'senderPlan': normalize_plan_key(current_user.plan),
            'senderSiteUserId': str(current_user.id),
            'senderAuthUid': f'site_user_{current_user.id}',
            'createdAt': _firestore_server_timestamp()
        }

        reply_message_id = str(data.get('replyToMessageId') or '').strip()
        if reply_message_id:
            payload.update({
                'replyToMessageId': reply_message_id,
                'replyToSenderName': sanitize_input(str(data.get('replyToSenderName') or 'Usuario'))[:80],
                'replyToText': sanitize_input(str(data.get('replyToText') or ''))[:180]
            })

        new_message_ref = room_ref.collection('messages').document()
        new_message_ref.set(payload, timeout=5)
        _sync_chat_room_metadata_from_latest(db_firestore, room_id)

        created_doc = _get_firestore_document_snapshot(new_message_ref)
        return jsonify({
            'success': True,
            'message': _serialize_chat_message(created_doc) if created_doc.exists else {**payload, 'id': new_message_ref.id}
        })
    except BaseException as e:
        _trip_firestore_circuit(e)
        app.logger.error(f'Erro ao processar mensagens da sala {room_id}: {e}')
        return jsonify({'success': False, 'message': 'Chat temporariamente indisponível.', 'chatUnavailable': True}), 503, {'Retry-After': str(_FIRESTORE_CIRCUIT_COOLDOWN)}


@app.route('/api/chat/rooms/<string:room_id>/messages/<string:message_id>', methods=['PATCH', 'DELETE'])
@login_required
@limiter.limit("180 per minute")
def chat_room_message_actions(room_id, message_id):
    if not current_user.is_active:
        return jsonify({'success': False, 'message': 'Conta desativada.'}), 403

    db_firestore = _get_firestore_client()
    if db_firestore is None:
        return jsonify({'success': False, 'message': 'Chat temporariamente indisponível.', 'chatUnavailable': True}), 503, {'Retry-After': str(_FIRESTORE_CIRCUIT_COOLDOWN)}

    allowed, denial_message, denial_status = _validate_chat_room_access(current_user, room_id, write=True)
    if not allowed:
        return jsonify({'success': False, 'message': denial_message}), denial_status

    try:
        message_ref = (
            db_firestore.collection('chat_rooms')
            .document(room_id)
            .collection('messages')
            .document(message_id)
        )
        message_snapshot = _get_firestore_document_snapshot(message_ref)
        if not message_snapshot.exists:
            return jsonify({'success': False, 'message': 'Mensagem não encontrada.'}), 404

        message_data = message_snapshot.to_dict() or {}
        is_admin_delete = request.method == 'DELETE' and _is_chat_admin(current_user)
        sender_site_user_id = str(message_data.get('senderSiteUserId') or '')
        created_at_ms = _firestore_timestamp_to_millis(message_data.get('createdAt'))
        can_manage_own_message = (
            sender_site_user_id == str(current_user.id)
            and created_at_ms > 0
            and (int(datetime.utcnow().timestamp() * 1000) - created_at_ms) <= CHAT_MESSAGE_EDIT_WINDOW_MS
        )

        if request.method == 'PATCH':
            if not can_manage_own_message:
                return jsonify({'success': False, 'message': 'Você só pode editar mensagens próprias enviadas há menos de 10 minutos.'}), 403

            data = request.get_json(silent=True) or {}
            if not isinstance(data, dict):
                return jsonify({'success': False, 'message': 'JSON inválido.'}), 400

            text = sanitize_input(str(data.get('text') or ''))[:500].strip()
            if not text:
                return jsonify({'success': False, 'message': 'Digite uma mensagem válida para editar.'}), 400

            message_ref.update({
                'text': text,
                'isEdited': True,
                'editedAt': _firestore_server_timestamp()
            }, timeout=5)
            _sync_chat_room_metadata_from_latest(db_firestore, room_id)
            updated_snapshot = _get_firestore_document_snapshot(message_ref)
            return jsonify({
                'success': True,
                'message': _serialize_chat_message(updated_snapshot) if updated_snapshot.exists else None
            })

        if not (is_admin_delete or can_manage_own_message):
            return jsonify({'success': False, 'message': 'Você não pode excluir esta mensagem.'}), 403

        message_ref.delete(timeout=5)
        _sync_chat_room_metadata_from_latest(db_firestore, room_id)
        return jsonify({'success': True, 'message': 'Mensagem excluída com sucesso.'})
    except BaseException as e:
        _trip_firestore_circuit(e)
        app.logger.error(f'Erro ao processar ação da mensagem {message_id} na sala {room_id}: {e}')
        return jsonify({'success': False, 'message': 'Chat temporariamente indisponível.', 'chatUnavailable': True}), 503, {'Retry-After': str(_FIRESTORE_CIRCUIT_COOLDOWN)}


@app.route('/api/chat/admin/tickets', methods=['GET'])
@login_required
@limiter.limit("120 per minute")
def chat_admin_tickets():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403

    db_firestore = _get_firestore_client()
    if db_firestore is None:
        return jsonify({'success': False, 'message': 'Chat temporariamente indisponível.', 'chatUnavailable': True}), 503, {'Retry-After': str(_FIRESTORE_CIRCUIT_COOLDOWN)}

    try:
        return jsonify({'success': True, 'tickets': _get_chat_support_tickets(db_firestore)})
    except BaseException as e:
        _trip_firestore_circuit(e)
        app.logger.error(f'Erro ao listar chamados do chat: {e}')
        return jsonify({'success': False, 'message': 'Chat temporariamente indisponível.', 'chatUnavailable': True}), 503, {'Retry-After': str(_FIRESTORE_CIRCUIT_COOLDOWN)}


@app.route('/api/chat/admin/tickets/<string:room_id>', methods=['DELETE'])
@login_required
@limiter.limit("60 per minute")
def chat_admin_delete_ticket(room_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403

    if not str(room_id).startswith('support_user_'):
        return jsonify({'success': False, 'message': 'Chamado inválido.'}), 400

    db_firestore = _get_firestore_client()
    if db_firestore is None:
        return jsonify({'success': False, 'message': 'Chat temporariamente indisponível.', 'chatUnavailable': True}), 503, {'Retry-After': str(_FIRESTORE_CIRCUIT_COOLDOWN)}

    try:
        _delete_chat_room_recursive(db_firestore, room_id)
        return jsonify({'success': True, 'message': 'Chamado excluído com sucesso.', 'room_id': room_id})
    except BaseException as e:
        _trip_firestore_circuit(e)
        app.logger.error(f'Erro ao excluir chamado do chat {room_id}: {e}')
        return jsonify({'success': False, 'message': 'Chat temporariamente indisponível.', 'chatUnavailable': True}), 503, {'Retry-After': str(_FIRESTORE_CIRCUIT_COOLDOWN)}

# Rota de cadastro
@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("10 per minute")  # Limitar criação de contas
def register():
    # Se o usuário já estiver logado, redirecione para a página inicial
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    requested_plan = str(
        request.form.get('selected_plan')
        or request.args.get('plan')
        or ''
    ).strip().lower()
    selected_plan = requested_plan if requested_plan in ('premium', 'vip') else ''
    register_url = url_for('register', plan=selected_plan) if selected_plan else url_for('register')

    if request.method == 'POST':
        # Obter dados do formulário e sanitizar
        name = sanitize_input(request.form.get('name', '').strip())
        username = sanitize_input(request.form.get('username', '').strip())
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        terms = True if request.form.get('terms') else False

        # Validações de tamanho antes de processar
        if name and len(name) > 100:
            flash('Nome muito longo (máximo 100 caracteres)', 'danger')
            return redirect(register_url)

        if username and len(username) > 50:
            flash('Nome de usuário muito longo (máximo 50 caracteres)', 'danger')
            return redirect(register_url)

        if email and len(email) > 255:
            flash('Email muito longo', 'danger')
            return redirect(register_url)

        # Validações
        error = ''

        if not name or not username or not email or not password or not confirm_password:
            error = 'Todos os campos são obrigatórios.'
        elif len(username) < 4:
            error = 'O nome de usuário deve ter pelo menos 4 caracteres.'
        elif not username.replace('_', '').isalnum():
            error = 'O nome de usuário deve conter apenas letras, números e underscore (_).'
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            error = 'Por favor, insira um endereço de email válido.'
        elif password != confirm_password:
            error = 'As senhas não correspondem.'
        elif not terms:
            error = 'Você precisa aceitar os Termos de Uso e Política de Privacidade.'
        else:
            # Validar força da senha
            is_valid, password_error = validate_password_strength(password)
            if not is_valid:
                error = password_error

        # Se houver erro, exiba a mensagem e redirecione
        if error:
            flash(error, 'danger')
            return redirect(register_url)

        # Verificar se usuário ou email já existem
        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            flash('Este nome de usuário já está em uso. Escolha outro.', 'danger')
            return redirect(register_url)

        email_exists = User.query.filter_by(email=email).first()
        if email_exists:
            flash('Este email já está cadastrado. Faça login ou recupere sua senha.', 'danger')
            return redirect(register_url)

        # Criar novo usuário
        name = name or ""  # Garantir que name não seja None
        name_parts = name.split() if name else [""]
        new_user = User(
            first_name=name_parts[0] if name_parts else "",  # Primeiro nome
            last_name=' '.join(name_parts[1:]) if len(name_parts) > 1 else '',  # Sobrenome (se houver)
            username=username,
            email=email,
            is_active=True,
            plan='free',
            date_joined=datetime.utcnow()
        )

        # Definir a senha usando o método seguro
        new_user.set_password(password)

        # Salvar no banco de dados
        try:
            db.session.add(new_user)
            db.session.commit()
            flask_session['analytics_event'] = 'sign_up'

            # Feedback de sucesso
            flash('Conta criada com sucesso! Você já pode fazer login.', 'success')
            if selected_plan:
                return redirect(url_for('login', next=url_for('plans', checkout=selected_plan)))
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Erro ao registrar usuário: {e}")
            flash('Ocorreu um erro ao criar sua conta. Por favor, tente novamente.', 'danger')
            return redirect(register_url)

    return render_template('register.html', title='Criar Conta', selected_plan=selected_plan)

# Rota de recuperação de senha (nova)
@app.route('/reset-password', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form.get('email')

        if not email:
            flash('Por favor, insira seu email', 'danger')
            return redirect(url_for('reset_password_request'))

        user = User.query.filter_by(email=email).first()

        # Sempre mostrar a mesma mensagem para não dar pistas sobre emails cadastrados
        flash('Se este email estiver registrado, você receberá instruções para redefinir sua senha.', 'info')

        if user:
            # Gerar token de redefinição
            token = user.get_reset_token()
            try:
                send_password_reset_email(user, token)
            except Exception:
                app.logger.exception('Falha ao enviar email de redefinicao para user_id=%s', user.id)

        return redirect(url_for('login'))

    return render_template('reset_password_request.html', title='Redefinir Senha')

# Rota para processar o token de redefinição de senha
@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    user = User.verify_reset_token(token)
    if not user:
        flash('O link de redefinição é inválido ou expirou', 'danger')
        return redirect(url_for('reset_password_request'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not password or not confirm_password:
            flash('Por favor, preencha todos os campos', 'danger')
            return redirect(url_for('reset_password', token=token))

        if password != confirm_password:
            flash('As senhas não coincidem', 'danger')
            return redirect(url_for('reset_password', token=token))

        is_valid, password_error = validate_password_strength(password)
        if not is_valid:
            flash(password_error or 'Senha inválida.', 'danger')
            return redirect(url_for('reset_password', token=token))

        # Atualizar a senha
        user.set_password(password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()

        flash('Sua senha foi atualizada com sucesso! Você já pode fazer login.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html', title='Nova Senha')

# Rotas administrativas
@app.route('/admin')
@app.route('/admin/dashboard')
@login_required
@editor_required
def admin_dashboard():
    """
    Painel de controle administrativo
    """
    # Estatísticas dinâmicas do banco de dados
    posts_count = Post.query.filter_by(is_active=True).count()
    categories_count = Category.query.filter_by(is_active=True).count()
    users_count = User.query.filter_by(is_active=True).count()
    subscribers_count = Subscriber.query.filter_by(is_active=True).count()
    comments_count = Comment.query.count()

    # Estatísticas detalhadas reais
    featured_posts_count = Post.query.filter_by(is_active=True, featured=True).count()
    total_views = db.session.query(db.func.sum(Post.views)).filter_by(is_active=True).scalar() or 0
    total_downloads = db.session.query(db.func.sum(Post.downloads)).filter_by(is_active=True).scalar() or 0

    # Usuários administradores
    admin_users_count = User.query.filter_by(role='admin', is_active=True).count()

    # Usuários registrados hoje
    today = datetime.utcnow().date()
    new_users_today = User.query.filter(
        db.func.date(User.date_joined) == today
    ).count()

    # Downloads hoje usando PostStats
    try:
        downloads_today = db.session.query(db.func.sum(PostStats.downloads)).filter(
            PostStats.date == today
        ).scalar() or 0
    except Exception:
        downloads_today = 0

    # Posts por categoria (média)
    avg_posts_per_category = round(posts_count / categories_count, 1) if categories_count > 0 else 0

    # Visitantes únicos (usando VisitorLog se existir)
    try:
        unique_visitors = VisitorLog.query.with_entities(VisitorLog.ip_address).distinct().count()
        page_views = VisitorLog.query.count()
    except Exception:
        unique_visitors = 0
        page_views = 0

    # Campanhas de newsletter enviadas (implementar quando tiver tabela)
    campaigns_sent = 0  # Implementar quando tiver modelo Newsletter Campaign

    # Calcular tendências comparando com período anterior
    def calculate_trend(current_value, previous_value):
        if previous_value == 0:
            return 100 if current_value > 0 else 0
        return round(((current_value - previous_value) / previous_value) * 100, 1)

    # Posts de 30 dias atrás para comparação
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    posts_trend = calculate_trend(
        posts_count,
        Post.query.filter(Post.date_posted < thirty_days_ago).filter_by(is_active=True).count()
    )

    # Usuários de 30 dias atrás
    users_trend = calculate_trend(
        users_count,
        User.query.filter(User.date_joined < thirty_days_ago).filter_by(is_active=True).count()
    )

    # Subscribers de 30 dias atrás
    subscribers_trend = calculate_trend(
        subscribers_count,
        Subscriber.query.filter(Subscriber.subscribed_date < thirty_days_ago).filter_by(is_active=True).count()
    )

    # Sem uma série histórica equivalente não exibimos percentuais artificiais.
    categories_trend = 0  # Categorias são mais estáveis
    downloads_trend = 0
    views_trend = 0

    # Dados para gráficos - últimos 7 dias de visualizações
    chart_data = {
        'views_data': [],
        'downloads_by_category': []
    }

    # Gráfico de visualizações dos últimos 7 dias
    for i in range(7):
        date = datetime.utcnow().date() - timedelta(days=6-i)
        try:
            daily_views = db.session.query(db.func.count(VisitorLog.id)).filter(
                db.func.date(VisitorLog.visit_time) == date
            ).scalar() or 0
        except Exception:
            daily_views = 0

        chart_data['views_data'].append({
            'date': date.strftime('%a'),  # Mon, Tue, etc
            'views': daily_views
        })

    # Gráfico de downloads por categoria
    try:
        category_downloads = db.session.query(
            Category.name,
            db.func.sum(Post.downloads).label('total_downloads')
        ).join(Post, Category.id == Post.category_id)\
         .filter_by(is_active=True)\
         .group_by(Category.name)\
         .order_by(db.func.sum(Post.downloads).desc())\
         .all()

        for cat in category_downloads:
            chart_data['downloads_by_category'].append({
                'name': cat.name,
                'downloads': cat.total_downloads or 0
            })
    except Exception:
        # Se não há dados, criar estrutura vazia
        chart_data['downloads_by_category'] = []

    stats = {
        "posts": posts_count,
        "categories": categories_count,
        "users": users_count,
        "subscribers": subscribers_count,
        "featured_posts": featured_posts_count,
        "total_views": total_views,
        "total_downloads": total_downloads,
        "admin_users": admin_users_count,
        "new_users_today": new_users_today,
        "downloads_today": downloads_today,
        "avg_posts_per_category": avg_posts_per_category,
        "unique_visitors": unique_visitors,
        "page_views": page_views,
        "campaigns_sent": campaigns_sent,
        # Tendências
        "posts_trend": posts_trend,
        "categories_trend": categories_trend,
        "users_trend": users_trend,
        "subscribers_trend": subscribers_trend,
        "downloads_trend": downloads_trend,
        "views_trend": views_trend
    }

    # Posts recentes para exibição na tabela
    recent_posts = Post.query.filter_by(is_active=True).order_by(Post.date_posted.desc()).limit(10).all()

    # Categorias para o modal de criação de posts
    categories = Category.query.filter_by(is_active=True).order_by(Category.order, Category.name).all()

    # Buscar atividades recentes do banco de dados
    recent_activities = []
    # 1. Posts mais recentes
    latest_posts = Post.query.filter_by(is_active=True).order_by(Post.date_posted.desc()).limit(12).all()
    for post in latest_posts:
        author_name = "Admin"  # Default
        if post.author_id:
            author = User.query.get(post.author_id)
            if author:
                author_name = author.get_full_name()

        recent_activities.append({
            'type': 'post_created',
            'icon': 'fas fa-plus',
            'bg_class': 'bg-primary',
            'title': 'Novo post adicionado',
            'description': f'{post.title} foi adicionado por {author_name}',
            'date': post.date_posted
        })

    # 2. Usuários recém-cadastrados
    latest_users = User.query.filter_by(is_active=True).order_by(User.date_joined.desc()).limit(12).all()
    for user in latest_users:
        recent_activities.append({
            'type': 'user_registered',
            'icon': 'fas fa-user',
            'bg_class': 'bg-warning',
            'title': 'Novo usuário cadastrado',
            'description': f'{user.get_full_name()} se registrou no site',
            'date': user.date_joined
        })

    # 3. Posts atualizados recentemente
    updated_posts = Post.query.filter(Post.date_updated.isnot(None), Post.is_active==True).order_by(Post.date_updated.desc()).limit(12).all()
    for post in updated_posts:
        author_name = "Admin"
        if post.author_id:
            author = User.query.get(post.author_id)
            if author:
                author_name = author.get_full_name()

        recent_activities.append({
            'type': 'post_updated',
            'icon': 'fas fa-edit',
            'bg_class': 'bg-success',
            'title': 'Post atualizado',
            'description': f'{post.title} foi atualizado por {author_name}',
            'date': post.date_updated
        })

    # 4. Comentários recentes
    latest_comments = Comment.query.order_by(Comment.date_posted.desc()).limit(12).all()
    for comment in latest_comments:
        user_name = "Usuário"
        if comment.user_id:
            user = User.query.get(comment.user_id)
            if user:
                user_name = user.get_full_name()

        post_title = "Post"
        if comment.post_id:
            post = Post.query.get(comment.post_id)
            if post:
                post_title = post.title

        recent_activities.append({
            'type': 'comment_added',
            'icon': 'fas fa-comment',
            'bg_class': 'bg-info',
            'title': 'Novo comentário',
            'description': f'{user_name} comentou em "{post_title}"',
            'date': comment.date_posted
        })

    # 5. Ações administrativas registradas
    admin_activity_icon_map = {
        'criar_categoria': ('fas fa-folder-plus', 'bg-primary', 'Categoria criada'),
        'atualizar_categoria': ('fas fa-folder-open', 'bg-success', 'Categoria atualizada'),
        'excluir_categoria': ('fas fa-trash', 'bg-danger', 'Categoria excluída'),
        'toggle_destaque_categoria': ('fas fa-star', 'bg-warning', 'Destaque alterado'),
        'toggle_status_categoria': ('fas fa-toggle-on', 'bg-info', 'Status alterado'),
        'bulk_delete': ('fas fa-layer-group', 'bg-danger', 'Ação em massa'),
        'bulk_feature': ('fas fa-star', 'bg-warning', 'Ação em massa'),
        'bulk_unfeature': ('fas fa-star-half-alt', 'bg-secondary', 'Ação em massa'),
        'bulk_toggle_status': ('fas fa-toggle-on', 'bg-info', 'Ação em massa')
    }
    latest_admin_activities = AdminActivity.query.order_by(AdminActivity.created_at.desc()).limit(18).all()
    for admin_activity in latest_admin_activities:
        icon, bg_class, title = admin_activity_icon_map.get(
            admin_activity.action,
            ('fas fa-clipboard-list', 'bg-secondary', 'Ação administrativa')
        )
        actor_name = admin_activity.user.get_full_name() if admin_activity.user else 'Admin'
        recent_activities.append({
            'type': 'admin_activity',
            'icon': icon,
            'bg_class': bg_class,
            'title': title,
            'description': admin_activity.description or f'Ação registrada por {actor_name}',
            'date': admin_activity.created_at
        })

    # Ordenar atividades por data (mais recente primeiro) e paginar a cada 6 itens.
    recent_activities.sort(key=lambda x: x['date'], reverse=True)
    activity_page = request.args.get('activity_page', 1, type=int)
    recent_activities_pagination = ListPagination(recent_activities, page=activity_page, per_page=6)
    recent_activities = recent_activities_pagination.items

    # Dados para a sidebar
    context = {
        "title": "Dashboard",
        "stats": stats,
        "recent_posts": recent_posts,
        "recent_activities": recent_activities,
        "recent_activities_pagination": recent_activities_pagination,
        "categories": categories,
        "category_subcategories_map": get_category_subcategories_map(),
        "post_count": stats["posts"],
        "category_count": stats["categories"],
        "unread_comments": comments_count,  # Total de comentários
        "system_status": "online",
        "app_version": "1.6.2",
        "chart_data": chart_data  # Dados dos gráficos
    }

    debug_log(f"- Context stats sendo enviado para o template: {context['stats']}")

    return render_template('admin/dashboard.html', **context)


@app.route('/admin/dashboard/stats')
@login_required
@editor_required
def admin_dashboard_stats():
    """Snapshot real usado pela atualização periódica do dashboard."""
    try:
        page_views = VisitorLog.query.count()
    except Exception:
        page_views = 0

    response = jsonify({
        'success': True,
        'stats': {
            'posts': Post.query.filter_by(is_active=True).count(),
            'categories': Category.query.filter_by(is_active=True).count(),
            'users': User.query.filter_by(is_active=True).count(),
            'subscribers': Subscriber.query.filter_by(is_active=True).count(),
            'total_downloads': db.session.query(db.func.sum(Post.downloads)).filter_by(is_active=True).scalar() or 0,
            'page_views': page_views,
        },
    })
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response

# Rota para exportar posts
@app.route("/admin/posts/export")
@login_required
@editor_required
def admin_export_posts():
    """Exportar posts para CSV"""
    import csv
    import io
    from flask import Response

    posts = Post.query.all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Cabeçalho
    writer.writerow(['ID', 'Título', 'Categoria', 'Data Publicação', 'Views', 'Downloads', 'Status', 'Destaque'])

    # Dados
    for post in posts:
        # Determinar nome da categoria
        category_name = post.category_str or 'Sem categoria'
        if hasattr(post, 'category_rel') and post.category_rel:
            category_name = post.category_rel.name

        writer.writerow([
            post.id,
            post.title,
            category_name,
            post.date_posted.strftime('%Y-%m-%d %H:%M:%S') if post.date_posted else '',
            post.views,
            post.downloads,
            'Ativo' if post.is_active else 'Inativo',
            'Sim' if post.featured else 'Não'
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=posts_export.csv"}
    )

# Rota para exportar inscritos da newsletter
@app.route("/admin/newsletter/export/subscribers")
@login_required
@admin_required
def admin_export_subscribers():
    """Exportar inscritos para CSV"""
    import csv
    import io
    from flask import Response

    subscribers = Subscriber.query.all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Cabeçalho
    writer.writerow(['ID', 'Email', 'Nome', 'Data Inscrição', 'Status', 'Confirmado'])

    # Dados
    for sub in subscribers:
        writer.writerow([
            sub.id,
            sub.email,
            sub.name or '',
            sub.subscribed_date.strftime('%Y-%m-%d %H:%M:%S') if sub.subscribed_date else '',
            'Ativo' if sub.is_active else 'Inativo',
            'Sim' if sub.confirmed else 'Não'
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=subscribers_export.csv"}
    )

# Rota para exportar comentários
@app.route("/admin/comments/export")
@login_required
@editor_required
def admin_export_comments():
    """Exportar comentários para CSV"""
    import csv
    import io
    from flask import Response

    comments = Comment.query.all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Cabeçalho
    writer.writerow(['ID', 'Autor', 'Email', 'Data', 'Status', 'Post', 'Conteúdo'])

    # Dados
    for comment in comments:
        # Determinar autor
        author_name = comment.author_name
        author_email = comment.author_email
        if comment.user_id and comment.user:
            author_name = comment.user.name or comment.user.username
            author_email = comment.user.email

        # Determinar post
        post_title = comment.post.title if comment.post else 'Post excluído'

        writer.writerow([
            comment.id,
            author_name,
            author_email,
            comment.date_posted.strftime('%Y-%m-%d %H:%M:%S') if comment.date_posted else '',
            'Aprovado' if comment.is_approved else 'Pendente',
            post_title,
            comment.content[:100]  # Truncar conteúdo longo
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=comments_export.csv"}
    )

# Rota para criar um novo post
@app.route("/admin/posts/create", methods=['GET', 'POST'])
@login_required
@editor_required
def admin_create_post():
    """
    Rota para criação de novos posts pelo painel administrativo
    """
    # Se for GET, redirecionar para a página de posts
    if request.method == 'GET':
        return redirect(url_for('admin_posts'))
    try:
        # Extrair dados do formulário
        title = request.form.get('title')
        category_id = request.form.get('category')
        content = request.form.get('content')
        download_link = request.form.get('download_link', '')
        download_files_json = request.form.get('download_files', '')
        tags = request.form.get('tags', '').strip()
        seo_title = request.form.get('seo_title', '').strip()
        seo_description = request.form.get('seo_description', '').strip()
        publication_status = str(request.form.get('status') or 'published').strip().lower()
        if publication_status not in {'draft', 'published', 'scheduled'}:
            publication_status = 'published'

        scheduled_for = None
        scheduled_for_label = ''
        raw_publish_date = str(request.form.get('publish_date') or '').strip()
        if publication_status == 'scheduled' and raw_publish_date:
            try:
                local_schedule = datetime.fromisoformat(raw_publish_date.replace('Z', '+00:00'))
                if local_schedule.tzinfo is None:
                    local_schedule = BRAZIL_TZ.localize(local_schedule)
                else:
                    local_schedule = local_schedule.astimezone(BRAZIL_TZ)
                scheduled_for_label = local_schedule.strftime('%d/%m/%Y %H:%M')
                scheduled_for = local_schedule.astimezone(pytz.UTC).replace(tzinfo=None)
            except (TypeError, ValueError, pytz.AmbiguousTimeError, pytz.NonExistentTimeError):
                scheduled_for = None
        # Proteção contra NaN injection
        featured_value = request.form.get('featured', '')
        if isinstance(featured_value, str) and featured_value.lower() in ('nan', 'infinity', '-infinity'):
            featured = False
        else:
            # Converter para boolean de forma segura sem usar bool() diretamente em input
            featured = featured_value in ('true', '1', 'on', 'yes') if featured_value else False


        errors = {}
        if download_link and not normalize_download_url(download_link):
            errors['download_link'] = 'O link de download é inválido.'
        if not title:
            errors['title'] = 'O título é obrigatório.'
        if not content:
            errors['content'] = 'A descrição é obrigatória.'
        if not category_id:
            errors['category'] = 'A categoria é obrigatória.'
        if not download_link:
            errors['download_link'] = 'O link é obrigatório.'
        if publication_status == 'scheduled' and not scheduled_for:
            errors['publish_date'] = 'Informe uma data e horário válidos para o agendamento.'
        elif scheduled_for and scheduled_for <= datetime.utcnow():
            errors['publish_date'] = 'O agendamento precisa ser em uma data e horário futuros.'

        if errors:
            if _is_ajax_request():
                first_error = next(iter(errors.values()))
                return jsonify({'success': False, 'message': first_error, 'errors': errors}), 400
            # Recarregar categorias para o modal
            categories = Category.query.order_by(Category.name).all()
            # Repassar valores preenchidos e erros para o template
            context = {
                "title": "Gerenciar Posts",
                "categories": categories,
                "form_errors": errors,
                "form_data": {
                    'title': title,
                    'content': content,
                    'category': category_id,
                    'download_link': download_link,
                    'tags': tags,
                    'seo_title': seo_title,
                    'seo_description': seo_description,
                    'featured': featured,
                    'status': publication_status,
                    'publish_date': request.form.get('publish_date', ''),
                },
                # Repassar posts e stats para manter a página
                **get_admin_sidebar_stats()
            }
            page = request.args.get('page', 1, type=int)
            per_page = 10
            class SimplePagination:
                def __init__(self, page, per_page, total, items):
                    self.page = page
                    self.per_page = per_page
                    self.total = total
                    self.items = items
                @property
                def pages(self):
                    return max(1, math.ceil(self.total / self.per_page))
                @property
                def has_prev(self):
                    return self.page > 1
                @property
                def has_next(self):
                    return self.page < self.pages
                @property
                def prev_num(self):
                    return self.page - 1 if self.has_prev else None
                @property
                def next_num(self):
                    return self.page + 1 if self.has_next else None
                def iter_pages(self, left_edge=2, left_current=2, right_current=5, right_edge=2):
                    last = 0
                    for num in range(1, self.pages + 1):
                        if num <= left_edge or \
                           (num > self.page - left_current - 1 and num < self.page + right_current) or \
                           num > self.pages - right_edge:
                            if last + 1 != num:
                                yield None
                            yield num
                            last = num
            posts_pagination = Post.query.order_by(Post.date_posted.desc()).paginate(page=page, per_page=per_page, error_out=False)
            pagination = SimplePagination(page, per_page, posts_pagination.total, posts_pagination.items)
            context["posts"] = pagination
            context["pagination"] = pagination
            context["posts_overview"] = get_admin_posts_overview()
            context["category_subcategories_map"] = get_category_subcategories_map()
            context["current_filters"] = {'q': '', 'category': '', 'status': '', 'sort': 'date'}
            context["system_status"] = "online"
            context["app_version"] = "1.6.2"
            return render_template('admin/posts.html', **context)

        # Buscar categoria
        category = Category.query.get(category_id) if category_id else None

        # Processar upload de imagem se fornecido
        image_url = request.form.get('image_url', '').strip()
        image_file = request.files.get('image_file')

        if image_file and image_file.filename:
            # Validar extensão
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            file_ext = image_file.filename.rsplit('.', 1)[1].lower() if '.' in image_file.filename else ''

            if file_ext not in allowed_extensions:
                if _is_ajax_request():
                    return jsonify({'success': False, 'message': 'Formato de imagem não permitido. Use: PNG, JPG, GIF, WebP'}), 400
                flash('Formato de imagem não permitido. Use: PNG, JPG, GIF, WebP', 'error')
                return redirect(url_for('admin_posts'))

            # Upload para Cloudinary
            success, result = upload_to_cloudinary(image_file, folder='posts')

            if success:
                image_url = result  # URL do Cloudinary
            else:
                if _is_ajax_request():
                    return jsonify({'success': False, 'message': f'Erro ao fazer upload da imagem: {result}'}), 400
                flash(f'Erro ao fazer upload da imagem: {result}', 'error')
                return redirect(url_for('admin_posts'))

        # Se não houver imagem, usar placeholder
        if not image_url:
            image_url = 'post-placeholder.svg'

        # Gerar slug único para o post
        base_slug = generate_slug(title)
        slug = base_slug
        counter = 1
        while Post.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        # Criar novo post
        new_post = Post(
            title=title,
            content=content,
            category_id=category_id if category else None,
            category_str=category.name if category else 'Sem categoria',
            download_link=download_link,
            image_url=image_url,
            featured=featured,
            author_id=current_user.id,
            is_active=publication_status == 'published',
            tags=tags or None,
            seo_title=seo_title or None,
            seo_description=seo_description or None,
            slug=slug
        )

        apply_post_technical_form(new_post, request.form)

        db.session.add(new_post)
        db.session.flush()

        if publication_status == 'scheduled' and scheduled_for:
            new_post.date_posted = scheduled_for
            db.session.add(ScheduledPost(
                post_id=new_post.id,
                scheduled_for=scheduled_for,
                status='pending',
                created_by=current_user.id,
            ))

        # Armazenar download_files no custom_metadata
        if download_files_json:
            download_files = normalize_download_files(download_files_json)
            if download_files:
                new_post.set_metadata('download_files', download_files)
                sync_post_download_summary(new_post, download_files)

        db.session.commit()

        if _is_ajax_request():
            return jsonify({
                'success': True,
                'message': (
                    f'Post "{title}" agendado para {scheduled_for_label}.'
                    if publication_status == 'scheduled' and scheduled_for
                    else f'Post "{title}" criado com sucesso!'
                ),
                'post': serialize_post_for_admin(new_post),
                'stats': get_admin_posts_overview()
            })

        if publication_status == 'scheduled' and scheduled_for:
            flash(f'Post "{title}" agendado para {scheduled_for_label}.', 'success')
        elif publication_status == 'draft':
            flash(f'Rascunho "{title}" salvo com sucesso!', 'success')
        else:
            flash(f'Post "{title}" criado com sucesso!', 'success')
        return redirect(url_for('admin_posts'))

    except ValueError as e:
        db.session.rollback()
        if _is_ajax_request():
            return jsonify({'success': False, 'message': str(e)}), 400
        flash(str(e), 'error')
        return redirect(url_for('admin_posts'))
    except Exception as e:
        db.session.rollback()
        if _is_ajax_request():
            return jsonify({'success': False, 'message': f'Erro ao criar post: {str(e)}'}), 500
        flash(f'Erro ao criar post: {str(e)}', 'error')
        return redirect(url_for('admin_posts'))

# Rota para criar uma nova categoria

# Rota para criar um novo usuário
@app.route("/admin/users/create", methods=['POST'])
@login_required
@admin_required
def admin_create_user():
    """
    Rota para criação de novos usuários pelo painel administrativo
    """
    try:
        # Extrair dados do formulário
        name = sanitize_input((request.form.get('name') or '').strip())
        username = build_safe_username((request.form.get('username') or '').strip(), fallback_prefix='user')
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        role = (request.form.get('role', 'user') or 'user').strip().lower()

        # Validações básicas
        if not all([name, username, email, password]):
            flash('Todos os campos são obrigatórios', 'error')
            return redirect(url_for('admin_users'))

        if role not in ('admin', 'editor', 'user'):
            role = 'user'

        if len(email) > 255 or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Email inválido', 'error')
            return redirect(url_for('admin_users'))

        is_valid, password_error = validate_password_strength(password)
        if not is_valid:
            flash(password_error, 'error')
            return redirect(url_for('admin_users'))

        # Verificar se já existe usuário com este username ou email
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Já existe um usuário com este username ou email', 'error')
            return redirect(url_for('admin_users'))

        first_name, last_name = split_full_name(name)

        # Criar novo usuário
        new_user = User(
            name=name,
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            role=role,
            is_active=True
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        flash(f'Usuário "{username}" criado com sucesso!', 'success')
        return redirect(url_for('admin_users'))

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar usuário: {str(e)}', 'error')
        return redirect(url_for('admin_users'))

# Rota para exportar usuários
@app.route("/admin/users/export")
@login_required
@admin_required
def admin_export_users():
    """Exportar usuários para CSV"""
    import csv
    import io
    from flask import Response

    users = User.query.all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Cabeçalho
    writer.writerow(['ID', 'Username', 'Nome', 'Email', 'Função', 'Data Cadastro', 'Status'])

    # Dados
    for user in users:
        writer.writerow([
            user.id,
            user.username,
            user.name,
            user.email,
            user.role,
            user.date_joined.strftime('%Y-%m-%d %H:%M:%S') if user.date_joined else '',
            'Ativo' if user.is_active else 'Inativo'
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=users_export.csv"}
    )

# Rotas de exclusão

@app.route("/admin/users/delete/<int:user_id>", methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    """Excluir um usuário"""
    try:
        user = User.query.get_or_404(user_id)
        if user.id == current_user.id:
            flash('Você não pode excluir sua própria conta!', 'error')
            return redirect(url_for('admin_users'))

        username = user.username
        db.session.delete(user)
        db.session.commit()
        flash(f'Usuário "{username}" excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir usuário: {str(e)}', 'error')
    return redirect(url_for('admin_users'))

# Rota para a página de posts
@app.route("/admin/posts")
@app.route("/admin/posts/")
@login_required
@editor_required
def admin_posts():
    """
    Página para gerenciar posts
    """
    page = request.args.get('page', 1, type=int)
    per_page = 10
    search_query = request.args.get('q', '').strip()
    category_filter = request.args.get('category', '').strip()
    status_filter = request.args.get('status', '').strip()
    sort_by = request.args.get('sort', 'date').strip() or 'date'

    posts_list = Post.query.all()

    if search_query:
        posts_list = [
            post for post in posts_list
            if get_post_search_score(search_query, post) is not None
        ]

    if category_filter:
        try:
            category_id = int(category_filter)
            posts_list = [post for post in posts_list if post.category_id == category_id]
        except ValueError:
            posts_list = []

    if status_filter == 'active':
        posts_list = [post for post in posts_list if post.is_active and not post.featured]
    elif status_filter == 'featured':
        posts_list = [post for post in posts_list if post.featured]
    elif status_filter == 'scheduled':
        posts_list = [
            post for post in posts_list
            if post.scheduled_publication and post.scheduled_publication.status == 'pending'
        ]
    elif status_filter == 'inactive':
        posts_list = [
            post for post in posts_list
            if not post.is_active
            and not (post.scheduled_publication and post.scheduled_publication.status == 'pending')
        ]

    if sort_by == 'title':
        posts_list.sort(key=lambda post: (post.title or '').casefold())
    elif sort_by == 'views':
        posts_list.sort(key=lambda post: post.views or 0, reverse=True)
    elif sort_by == 'downloads':
        posts_list.sort(key=lambda post: post.downloads or 0, reverse=True)
    else:
        sort_by = 'date'
        posts_list.sort(key=lambda post: post.date_posted or datetime.min, reverse=True)

    total_posts = len(posts_list)
    total_pages = max(1, math.ceil(total_posts / per_page))
    page = min(max(page, 1), total_pages)
    start = (page - 1) * per_page
    end = start + per_page

    class SimplePagination:
        def __init__(self, page, per_page, total, items):
            self.page = page
            self.per_page = per_page
            self.total = total
            self.items = items

        @property
        def pages(self):
            return max(1, math.ceil(self.total / self.per_page))

        @property
        def has_prev(self):
            return self.page > 1

        @property
        def has_next(self):
            return self.page < self.pages

        @property
        def prev_num(self):
            return self.page - 1 if self.has_prev else None

        @property
        def next_num(self):
            return self.page + 1 if self.has_next else None

        def iter_pages(self, left_edge=2, left_current=2, right_current=5, right_edge=2):
            last = 0
            for num in range(1, self.pages + 1):
                if num <= left_edge or \
                   (num > self.page - left_current - 1 and num < self.page + right_current) or \
                   num > self.pages - right_edge:
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num

    pagination = SimplePagination(page, per_page, total_posts, posts_list[start:end])

    # Obter estatísticas para a sidebar
    sidebar_stats = get_admin_sidebar_stats()

    # Categorias para o modal
    categories = Category.query.order_by(Category.name).all()

    context = {
        "title": "Gerenciar Posts",
        "posts": pagination,
        "pagination": pagination,
        "posts_overview": get_admin_posts_overview(),
        "categories": categories,
        "category_subcategories_map": get_category_subcategories_map(),
        "current_filters": {
            'q': search_query,
            'category': category_filter,
            'status': status_filter,
            'sort': sort_by,
        },
        "system_status": "online",
        "app_version": "1.6.2",
        **sidebar_stats
    }

    return render_template('admin/posts.html', **context)


@app.route('/admin/download-types', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_download_types():
    """Lista e salva os tipos globais usados nos links de download dos posts."""
    if request.method == 'GET':
        return jsonify({'success': True, 'types': get_download_file_types()})

    payload = request.get_json(silent=True) or {}
    next_types = normalize_download_file_types(payload.get('types'))

    if not next_types:
        return jsonify({
            'success': False,
            'message': 'Informe pelo menos um tipo de arquivo.'
        }), 400

    previous_labels = get_download_file_type_labels()
    next_labels = [item['label'] for item in next_types]

    try:
        SiteConfig.set_value(
            'download_file_types',
            next_types,
            value_type='json',
            description='Tipos disponíveis no dropdown de links de download',
            is_public=False
        )

        renamed_labels: dict[str, str] = {}
        if len(previous_labels) == len(next_labels):
            renamed_labels = {
                old_label: new_label
                for old_label, new_label in zip(previous_labels, next_labels)
                if old_label != new_label
            }

        updated_posts_count = 0
        if renamed_labels:
            posts_with_metadata = Post.query.filter(cast(Any, Post.custom_metadata).isnot(None)).all()
            for post in posts_with_metadata:
                metadata = post.get_metadata()
                download_files = metadata.get('download_files') if isinstance(metadata, dict) else None
                if not isinstance(download_files, list):
                    continue

                changed = False
                for download_file in download_files:
                    if not isinstance(download_file, dict):
                        continue
                    current_type = download_file.get('type')
                    if current_type in renamed_labels:
                        download_file['type'] = renamed_labels[current_type]
                        changed = True

                if changed:
                    metadata['download_files'] = download_files
                    post.custom_metadata = json.dumps(metadata)
                    updated_posts_count += 1

            if updated_posts_count:
                db.session.commit()

        log_admin_activity(
            current_user.id,
            'update_download_types',
            'Atualizou os tipos de arquivo de download',
            metadata={'types': next_labels, 'updated_posts': updated_posts_count}
        )

        return jsonify({
            'success': True,
            'message': 'Tipos de download salvos com sucesso.',
            'types': next_types
        })
    except Exception as exc:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro ao salvar tipos de download: {str(exc)}'
        }), 500


# Adicionar as demais rotas administrativas
@app.route("/admin/analytics")
@login_required
@editor_required
def admin_analytics():
    """
    Página de estatísticas com dados reais do banco de dados
    """
    def normalize_referrer_label(value):
        raw_value = str(value or '').strip()
        if not raw_value or raw_value.lower() in {'direct', 'direct access', 'none', 'unknown'}:
            return 'Direto'
        try:
            parsed_referrer = url_parse(raw_value)
            if parsed_referrer.netloc:
                return parsed_referrer.netloc.replace('www.', '')
        except Exception:
            pass
        return raw_value[:60]

    def counts_to_payload(counts, label_key):
        ordered_items = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        payload = [
            {label_key: str(label or 'Não identificado'), 'count': int(count or 0)}
            for label, count in ordered_items
            if int(count or 0) > 0
        ]
        return payload or [{label_key: 'Sem dados', 'count': 0}]

    def parse_date_param(value):
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    today = datetime.utcnow().date()
    allowed_periods = {7, 30, 90, 365}
    requested_days = request.args.get('days', 30, type=int)
    period_days = requested_days if requested_days in allowed_periods else 30
    start_date = parse_date_param(request.args.get('start'))
    end_date = parse_date_param(request.args.get('end'))

    if not start_date or not end_date or start_date > end_date:
        end_date = today
        start_date = today - timedelta(days=period_days - 1)
    else:
        period_days = max(1, (end_date - start_date).days + 1)

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    # Calcular estatísticas reais
    total_posts = Post.query.filter_by(is_active=True).count()
    total_categories = Category.query.filter_by(is_active=True).count()
    total_users = User.query.filter_by(is_active=True).count()
    total_comments = Comment.query.count()
    total_subscribers = Subscriber.query.filter_by(is_active=True).count()

    period_views = db.session.query(db.func.sum(PostStats.views)).filter(
        PostStats.date >= start_date,
        PostStats.date <= end_date
    ).scalar() or 0
    period_downloads = db.session.query(db.func.sum(PostStats.downloads)).filter(
        PostStats.date >= start_date,
        PostStats.date <= end_date
    ).scalar() or 0

    total_views = period_views or db.session.query(db.func.sum(Post.views)).filter(Post.is_active == True).scalar() or 0
    total_downloads = period_downloads or db.session.query(db.func.sum(Post.downloads)).filter(Post.is_active == True).scalar() or 0

    # Novos usuários no período selecionado
    new_users = User.query.filter(User.date_joined >= start_dt, User.date_joined <= end_dt).count()
    new_users_week = User.query.filter(User.date_joined >= seven_days_ago).count()

    # Novos posts no período selecionado
    new_posts = Post.query.filter(
        Post.date_posted >= start_dt,
        Post.date_posted <= end_dt,
        Post.is_active == True
    ).count()

    total_unique_visits = db.session.query(db.func.count(db.func.distinct(VisitorLog.ip_address))).filter(
        VisitorLog.visit_time >= start_dt,
        VisitorLog.visit_time <= end_dt
    ).scalar() or 0
    if total_unique_visits == 0:
        total_unique_visits = int(total_views or 0)

    visitor_daily_rows = db.session.query(
        db.func.date(VisitorLog.visit_time).label('day'),
        db.func.count(db.func.distinct(VisitorLog.ip_address)).label('visits')
    ).filter(
        VisitorLog.visit_time >= start_dt,
        VisitorLog.visit_time <= end_dt
    ).group_by(db.func.date(VisitorLog.visit_time)).all()

    stats_daily_rows = db.session.query(
        PostStats.date.label('day'),
        db.func.sum(PostStats.views).label('views')
    ).filter(
        PostStats.date >= start_date,
        PostStats.date <= end_date
    ).group_by(PostStats.date).all()

    visitor_daily_lookup = {str(row.day): int(row.visits or 0) for row in visitor_daily_rows}
    stats_daily_lookup = {str(row.day): int(row.views or 0) for row in stats_daily_rows}
    use_stats_fallback = not any(visitor_daily_lookup.values()) and any(stats_daily_lookup.values())
    daily_visits = []
    for offset in range(period_days):
        date = start_date + timedelta(days=offset)
        date_key = date.isoformat()
        daily_visits.append({
            'date': date_key,
            'visits': stats_daily_lookup.get(date_key, 0) if use_stats_fallback else visitor_daily_lookup.get(date_key, 0)
        })

    visitor_fingerprints = VisitorLog.query.with_entities(
        VisitorLog.user_agent,
        VisitorLog.device_type,
        VisitorLog.browser
    ).filter(
        VisitorLog.visit_time >= start_dt,
        VisitorLog.visit_time <= end_dt
    ).all()

    if not visitor_fingerprints:
        visitor_fingerprints = VisitorLog.query.with_entities(
            VisitorLog.user_agent,
            VisitorLog.device_type,
            VisitorLog.browser
        ).all()

    device_counts = {}
    browser_counts = {}
    for user_agent, stored_device, stored_browser in visitor_fingerprints:
        normalized_device = get_device_type(user_agent) if user_agent else (stored_device or 'Não identificado')
        normalized_browser = get_browser_name(user_agent) if user_agent else (stored_browser or 'Não identificado')
        device_counts[normalized_device] = device_counts.get(normalized_device, 0) + 1
        browser_counts[normalized_browser] = browser_counts.get(normalized_browser, 0) + 1

    if not browser_counts:
        user_browser_stats = db.session.query(
            User.browser,
            db.func.count(User.id).label('count')
        ).filter(User.browser.isnot(None))\
         .group_by(User.browser)\
         .order_by(db.func.count(User.id).desc())\
         .limit(5).all()
        browser_counts = {
            row.browser or 'Não identificado': int(row.count or 0)
            for row in user_browser_stats
        }

    browser_payload = counts_to_payload(browser_counts, 'browser')
    device_payload = counts_to_payload(device_counts, 'device')

    category_payload = []
    for category in Category.query.filter_by(is_active=True).order_by(Category.order.asc(), Category.name.asc()).all():
        apply_default_category_data(category)
        category_filter = db.or_(Post.category_id == category.id, Post.category_str == category.name)
        category_payload.append({
            'name': category.name,
            'post_count': int(Post.query.filter(category_filter, Post.is_active == True).count() or 0),
            'downloads': int(db.session.query(db.func.sum(Post.downloads)).filter(category_filter, Post.is_active == True).scalar() or 0)
        })

    if not category_payload:
        category_payload = [{'name': 'Sem dados', 'post_count': 0, 'downloads': 0}]

    popular_page = request.args.get('popular_page', 1, type=int)
    popular_posts_pagination = Post.query.filter_by(is_active=True)\
        .order_by(Post.views.desc(), Post.downloads.desc(), Post.date_posted.desc())\
        .paginate(page=popular_page, per_page=6, error_out=False)

    traffic_rows = db.session.query(
        VisitorLog.referrer,
        db.func.count(VisitorLog.id).label('count')
    ).filter(
        VisitorLog.visit_time >= start_dt,
        VisitorLog.visit_time <= end_dt
    ).group_by(VisitorLog.referrer)\
     .order_by(db.func.count(VisitorLog.id).desc())\
     .limit(10).all()

    traffic_counts = {}
    for row in traffic_rows:
        label = normalize_referrer_label(row.referrer)
        traffic_counts[label] = traffic_counts.get(label, 0) + int(row.count or 0)

    if not traffic_counts:
        user_referrer_rows = db.session.query(
            User.referrer,
            db.func.count(User.id).label('count')
        ).filter(User.referrer.isnot(None))\
         .group_by(User.referrer)\
         .order_by(db.func.count(User.id).desc())\
         .limit(10).all()
        for row in user_referrer_rows:
            label = normalize_referrer_label(row.referrer)
            traffic_counts[label] = traffic_counts.get(label, 0) + int(row.count or 0)

    if not traffic_counts and total_unique_visits:
        traffic_counts['Direto'] = int(total_unique_visits)

    traffic_payload = counts_to_payload(traffic_counts, 'source')

    # Calcular taxa de engajamento real (comentários / posts)
    engagement_rate = round((total_comments / total_posts) * 100, 1) if total_posts > 0 else 0

    analytics_data = {
        'total_visits': int(total_unique_visits or 0),
        'total_downloads': int(total_downloads or 0),
        'new_users': new_users,
        'new_users_week': new_users_week,
        'new_posts': new_posts,
        'engagement_rate': f'{engagement_rate}%',
        'total_posts': total_posts,
        'total_categories': total_categories,
        'total_users': total_users,
        'total_comments': total_comments,
        'total_subscribers': total_subscribers,
        'daily_visits': daily_visits,
        'device_stats': device_payload,
        'browser_stats': browser_payload,
        'category_stats': category_payload,
        'popular_posts': popular_posts_pagination.items,
        'traffic_sources': traffic_payload,
        'period_days': period_days,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat()
    }

    analytics_chart_data = {
        'dailyVisits': {
            'labels': [item['date'][5:].replace('-', '/') for item in daily_visits],
            'values': [int(item['visits'] or 0) for item in daily_visits]
        },
        'categories': {
            'labels': [item['name'] for item in category_payload],
            'posts': [int(item['post_count'] or 0) for item in category_payload],
            'downloads': [int(item['downloads'] or 0) for item in category_payload]
        },
        'trafficSources': {
            'labels': [item['source'] for item in traffic_payload],
            'values': [int(item['count'] or 0) for item in traffic_payload]
        },
        'devices': {
            'labels': [item['device'] for item in device_payload],
            'values': [int(item['count'] or 0) for item in device_payload]
        },
        'browsers': {
            'labels': [item['browser'] for item in browser_payload],
            'values': [int(item['count'] or 0) for item in browser_payload]
        }
    }

    # Obter estatísticas para a sidebar
    sidebar_stats = get_admin_sidebar_stats()

    return render_template('admin/analytics.html',
                         title="Estatísticas",
                         analytics=analytics_data,
                         analytics_chart_data=analytics_chart_data,
                         popular_posts_pagination=popular_posts_pagination,
                         **sidebar_stats)

@app.route("/admin/categories")
@login_required
@editor_required
def admin_categories():
    """
    Página para gerenciar categorias com dados reais e estatísticas detalhadas
    """
    # Obter todas as categorias ordenadas
    categories = Category.query.order_by(Category.order.asc(), Category.name.asc()).all()

    # Calcular estatísticas detalhadas para cada categoria
    category_stats = []
    total_posts = 0
    featured_count = 0

    for category in categories:
        category_payload = build_category_admin_payload(category)
        if category_payload['is_featured']:
            featured_count += 1

        category_stats.append(category_payload)
        total_posts += category_payload['post_count']

    # Calcular estatísticas gerais
    active_categories = len([cat for cat in category_stats if cat['is_active']])
    inactive_categories = len(category_stats) - active_categories
    avg_posts_per_category = round(total_posts / len(category_stats), 1) if category_stats else 0

    # Categoria com mais posts
    top_category = max(category_stats, key=lambda x: x['post_count']) if category_stats else None

    # Preparar dados para gráfico de pizza (posts por categoria)
    chart_data = {
        'labels': [cat['name'] for cat in category_stats[:5]],  # Top 5 categorias
        'data': [cat['post_count'] for cat in category_stats[:5]],
        'colors': ['#3a86ff', '#ff006e', '#8338ec', '#38b000', '#ffbe0b']
    }

    # Estatísticas resumidas
    summary_stats = {
        'total_categories': len(category_stats),
        'active_categories': active_categories,
        'inactive_categories': inactive_categories,
        'featured_categories': featured_count,
        'total_posts': total_posts,
        'avg_posts_per_category': avg_posts_per_category,
        'top_category': top_category
    }

    # Obter estatísticas para a sidebar
    sidebar_stats = get_admin_sidebar_stats()

    # Log da atividade administrativa
    log_admin_activity(
        user_id=current_user.id,
        action='visualizar_categorias',
        description='Acessou a página de gerenciamento de categorias'
    )

    return render_template('admin/categories.html',
                         title="Gerenciar Categorias",
                         categories=category_stats,
                         summary_stats=summary_stats,
                         chart_data=chart_data,
                         **sidebar_stats)

@app.route("/admin/categories/create", methods=['POST'])
@login_required
@editor_required
def admin_create_category():
    """
    Criar uma nova categoria
    """
    try:
        data = request.get_json(silent=True) if request.is_json else request.form
        if request.is_json and not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'JSON inválido'}), 400

        name = sanitize_input((data.get('name') or '').strip())
        slug = generate_slug((data.get('slug') or '').strip())
        description = sanitize_input((data.get('description') or '').strip())
        icon = sanitize_input((data.get('icon') or 'fas fa-folder').strip()) or 'fas fa-folder'
        color = sanitize_input((data.get('color') or '#4a90e2').strip()) or '#4a90e2'
        order = coerce_int(data.get('order'), 0)
        is_active = coerce_bool(data.get('is_active'), True)
        is_visible = coerce_bool(data.get('is_visible'), True)
        featured = coerce_bool(data.get('featured'), False)
        show_in_menu = coerce_bool(data.get('show_in_menu'), True)

        # Validações
        if not name:
            return jsonify({'success': False, 'message': 'Nome da categoria é obrigatório.'}), 400

        # Gerar slug automaticamente se não fornecido
        if not slug:
            slug = generate_slug(name)

        # Verificar se slug já existe (ignorando a categoria atual se estiver editando)
        existing_category = Category.query.filter_by(slug=slug).first()
        if existing_category:
            # Adicionar sufixo numérico ao slug para torná-lo único
            counter = 1
            original_slug = slug
            while existing_category:
                slug = f"{original_slug}-{counter}"
                existing_category = Category.query.filter_by(slug=slug).first()
                counter += 1

        # Criar nova categoria
        new_category = Category(
            name=name,
            slug=slug,
            description=description,
            icon=icon,
            color=color,
            order=order,
            is_active=is_active,
            is_visible=is_visible,
            show_in_menu=show_in_menu
        )

        # Adicionar campo featured se existe no modelo
        if hasattr(new_category, 'featured'):
            new_category.featured = featured

        # Aplicar ícone e descrição padrão se a categoria corresponder a um padrão
        apply_default_category_data(new_category)

        db.session.add(new_category)
        db.session.commit()

        # Log da atividade
        log_admin_activity(
            user_id=current_user.id,
            action='criar_categoria',
            description=f'Criou a categoria "{name}"',
            metadata={'category_id': new_category.id, 'name': name, 'slug': slug}
        )

        return jsonify({
            'success': True,
            'message': 'Categoria criada com sucesso!',
            'category': build_category_admin_payload(new_category)
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao criar categoria: {str(e)}'}), 500

@app.route("/admin/categories/<int:category_id>/edit", methods=['GET'])
@login_required
@editor_required
def admin_get_category(category_id):
    """
    Buscar dados de uma categoria para edição
    """
    try:
        category = Category.query.get_or_404(category_id)

        return jsonify({
            'success': True,
            'category': {
                'id': category.id,
                'name': category.name,
                'slug': category.slug,
                'description': category.description or '',
                'icon': category.icon or 'fas fa-folder',
                'color': category.color or '#4a90e2',
                'order': category.order or 0,
                'is_active': category.is_active,
                'is_visible': bool(category.is_visible),
                'is_featured': bool(category.featured),
                'show_in_menu': bool(category.show_in_menu),
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao buscar categoria: {str(e)}'}), 500

@app.route("/admin/categories/<int:category_id>/update", methods=['PUT', 'POST'])
@login_required
@editor_required
def admin_update_category(category_id):
    """
    Atualizar uma categoria existente
    """
    try:
        category = Category.query.get_or_404(category_id)
        data = request.get_json(silent=True) if request.is_json else request.form
        if request.is_json and not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'JSON inválido'}), 400

        old_name = category.name
        name = sanitize_input((data.get('name', category.name) or category.name).strip())
        slug = generate_slug((data.get('slug', category.slug) or '').strip())
        description = sanitize_input((data.get('description', category.description or '') or '').strip())
        icon = sanitize_input((data.get('icon', category.icon or 'fas fa-folder') or 'fas fa-folder').strip()) or 'fas fa-folder'
        color = sanitize_input((data.get('color', category.color or '#4a90e2') or '#4a90e2').strip()) or '#4a90e2'
        order = coerce_int(data.get('order'), category.order or 0)
        is_active = coerce_bool(data.get('is_active'), bool(category.is_active))
        is_visible = coerce_bool(data.get('is_visible'), bool(category.is_visible))
        featured = coerce_bool(data.get('featured'), bool(category.featured))
        show_in_menu = coerce_bool(data.get('show_in_menu'), bool(category.show_in_menu))

        # Validações
        if not name:
            return jsonify({'success': False, 'message': 'Nome da categoria é obrigatório.'}), 400

        if not slug:
            slug = generate_slug(name)

        # Verificar se slug já existe em outra categoria
        if slug != category.slug:
            existing_category = Category.query.filter_by(slug=slug).first()
            if existing_category and existing_category.id != category_id:
                return jsonify({'success': False, 'message': 'URL amigável (slug) já existe.'}), 400

        # Atualizar campos
        category.name = name
        category.slug = slug
        category.description = description
        category.icon = icon
        category.color = color
        category.order = order
        category.is_active = is_active
        category.is_visible = is_visible
        category.show_in_menu = show_in_menu

        # Atualizar campo featured se existe
        if hasattr(category, 'featured'):
            category.featured = featured

        # Aplicar ícone e descrição padrão se a categoria corresponder a um padrão
        apply_default_category_data(category)

        Post.query.filter(
            db.or_(
                Post.category_id == category.id,
                Post.category_str == old_name
            )
        ).update({'category_str': category.name}, synchronize_session=False)

        db.session.commit()

        # Log da atividade
        log_admin_activity(
            user_id=current_user.id,
            action='atualizar_categoria',
            description=f'Atualizou a categoria "{old_name}" para "{name}"',
            metadata={'category_id': category.id, 'old_name': old_name, 'new_name': name}
        )

        return jsonify({
            'success': True,
            'message': 'Categoria atualizada com sucesso!',
            'category': build_category_admin_payload(category)
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao atualizar categoria: {str(e)}'}), 500

@app.route("/admin/categories/<int:category_id>/delete", methods=['DELETE', 'POST'])
@login_required
@editor_required
def admin_delete_category(category_id):
    """
    Excluir uma categoria
    """
    try:
        category = Category.query.get_or_404(category_id)
        category_name = category.name

        # Verificar se há posts nesta categoria
        post_filter = db.or_(Post.category_id == category_id, Post.category_str == category_name)
        post_count = Post.query.filter(post_filter).count()

        if post_count > 0:
            # Opção 1: Mover posts para categoria "Sem Categoria" ou primeira categoria disponível
            default_category = Category.query.filter(Category.id != category_id).order_by(Category.order.asc(), Category.name.asc()).first()
            if default_category:
                Post.query.filter(post_filter).update({
                    'category_id': default_category.id,
                    'category_str': default_category.name
                }, synchronize_session=False)
                message = f'Categoria excluída. {post_count} posts foram movidos para "{default_category.name}".'
            else:
                return jsonify({
                    'success': False,
                    'message': 'Não é possível excluir a única categoria. Crie outra categoria primeiro.'
                }), 400
        else:
            message = 'Categoria excluída com sucesso!'

        # Excluir a categoria
        db.session.delete(category)
        db.session.commit()

        # Log da atividade
        log_admin_activity(
            user_id=current_user.id,
            action='excluir_categoria',
            description=f'Excluiu a categoria "{category_name}"',
            metadata={'category_id': category_id, 'name': category_name, 'posts_moved': post_count}
        )

        return jsonify({
            'success': True,
            'message': message
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao excluir categoria: {str(e)}'}), 500

@app.route("/admin/categories/<int:category_id>/toggle-featured", methods=['POST'])
@login_required
@editor_required
def admin_toggle_category_featured(category_id):
    """
    Alternar status de destaque de uma categoria
    """
    try:
        category = Category.query.get_or_404(category_id)

        # Alternar o status de destaque
        category.featured = not category.featured
        status = 'destacada' if category.featured else 'removida dos destaques'

        db.session.commit()

        # Log da atividade
        log_admin_activity(
            user_id=current_user.id,
            action='toggle_destaque_categoria',
            description=f'Categoria "{category.name}" {status}',
            metadata={'category_id': category.id, 'featured': category.featured}
        )

        return jsonify({
            'success': True,
            'message': f'Categoria {status} com sucesso!',
            'featured': category.featured
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao alterar destaque: {str(e)}'}), 500

@app.route("/admin/categories/<int:category_id>/toggle-status", methods=['POST'])
@login_required
@editor_required
def admin_toggle_category_status(category_id):
    """
    Alternar status ativo/inativo de uma categoria
    """
    try:
        category = Category.query.get_or_404(category_id)

        # Alternar o status
        category.is_active = not category.is_active
        status = 'ativada' if category.is_active else 'desativada'

        db.session.commit()

        # Log da atividade
        log_admin_activity(
            user_id=current_user.id,
            action='toggle_status_categoria',
            description=f'Categoria "{category.name}" {status}',
            metadata={'category_id': category.id, 'is_active': category.is_active}
        )

        return jsonify({
            'success': True,
            'message': f'Categoria {status} com sucesso!',
            'is_active': category.is_active
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao alterar status: {str(e)}'}), 500

@app.route("/admin/categories/stats", methods=['GET'])
@login_required
@editor_required
def admin_categories_stats():
    """
    Retornar estatísticas atualizadas das categorias
    """
    try:
        categories = Category.query.order_by(Category.order.asc(), Category.name.asc()).all()
        category_payloads = [build_category_admin_payload(category) for category in categories]
        total_categories = len(category_payloads)
        active_categories = sum(1 for category in category_payloads if category['is_active'])
        featured_categories = sum(1 for category in category_payloads if category['is_featured'])
        inactive_categories = total_categories - active_categories
        total_posts = sum(int(category['post_count'] or 0) for category in category_payloads)
        average = round(total_posts / total_categories, 1) if total_categories else 0
        top_category = max(category_payloads, key=lambda category: category['post_count']) if category_payloads else None

        return jsonify({
            'success': True,
            'total': total_categories,
            'active': active_categories,
            'inactive': inactive_categories,
            'featured': featured_categories,
            'total_posts': total_posts,
            'average': average,
            'top_category': {
                'name': top_category['name'],
                'post_count': top_category['post_count'],
            } if top_category else None,
            'chart': {
                'labels': [category['name'] for category in category_payloads[:5]],
                'data': [category['post_count'] for category in category_payloads[:5]],
                'colors': ['#3a86ff', '#ff006e', '#8338ec', '#38b000', '#ffbe0b'],
            },
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao buscar estatísticas: {str(e)}'}), 500

@app.route("/admin/categories/bulk-action", methods=['POST'])
@login_required
@editor_required
def admin_categories_bulk_action():
    """
    Executar ações em massa em categorias
    """
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'JSON inválido'}), 400
        if not data:
            return jsonify({'success': False, 'message': 'Dados inválidos'}), 400

        action = data.get('action')
        category_ids = data.get('category_ids', [])

        if not isinstance(category_ids, list):
            return jsonify({'success': False, 'message': 'Dados inválidos'}), 400

        if not action or not category_ids:
            return jsonify({'success': False, 'message': 'Ação e IDs são obrigatórios'}), 400

        categories = Category.query.filter(Category.id.in_(category_ids)).all()

        if not categories:
            return jsonify({'success': False, 'message': 'Nenhuma categoria encontrada'}), 404

        if action == 'toggle-status':
            # Toggle status: ativa desativados e desativa ativados
            for category in categories:
                category.is_active = not category.is_active

            db.session.commit()
            log_admin_activity(
                current_user.id,
                'bulk_toggle_status',
                f'Status alternado em massa para {len(categories)} categorias'
            )
            return jsonify({
                'success': True,
                'message': f'Status alternado para {len(categories)} categorias',
                'count': len(categories)
            })

        elif action == 'feature':
            # Marcar como destaque
            for category in categories:
                category.featured = True

            db.session.commit()
            log_admin_activity(
                current_user.id,
                'bulk_feature',
                f'{len(categories)} categorias marcadas como destaque'
            )
            return jsonify({
                'success': True,
                'message': f'{len(categories)} categorias marcadas como destaque',
                'count': len(categories)
            })

        elif action == 'unfeature':
            # Remover destaque
            for category in categories:
                category.featured = False

            db.session.commit()
            log_admin_activity(
                current_user.id,
                'bulk_unfeature',
                f'Destaque removido de {len(categories)} categorias'
            )
            return jsonify({
                'success': True,
                'message': f'Destaque removido de {len(categories)} categorias',
                'count': len(categories)
            })

        elif action == 'delete':
            # Excluir categorias
            fallback_category = Category.query.filter(~Category.id.in_(category_ids)).order_by(Category.order.asc(), Category.name.asc()).first()
            categories_with_posts = []

            for category in categories:
                post_filter = db.or_(Post.category_id == category.id, Post.category_str == category.name)
                post_count = Post.query.filter(post_filter).count()
                if post_count > 0:
                    categories_with_posts.append(category.name)
                    if not fallback_category:
                        return jsonify({
                            'success': False,
                            'message': 'Não é possível excluir todas as categorias enquanto houver posts associados.'
                        }), 400
                    Post.query.filter(post_filter).update({
                        'category_id': fallback_category.id,
                        'category_str': fallback_category.name
                    }, synchronize_session=False)
                db.session.delete(category)

            db.session.commit()
            moved_suffix = ''
            if categories_with_posts and fallback_category:
                moved_suffix = f' Posts associados foram movidos para "{fallback_category.name}".'
            log_admin_activity(
                current_user.id,
                'bulk_delete',
                f'{len(categories)} categorias excluídas em massa'
            )
            return jsonify({
                'success': True,
                'message': f'{len(categories)} categorias excluídas.{moved_suffix}',
                'count': len(categories)
            })

        else:
            return jsonify({'success': False, 'message': 'Ação inválida'}), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao executar ação em massa: {str(e)}'}), 500

@app.route("/admin/posts/<int:post_id>/toggle-status", methods=['POST'])
@login_required
@editor_required
def admin_toggle_post_status(post_id):
    """
    Alternar status ativo/inativo de um post
    """
    try:
        post = Post.query.get_or_404(post_id)

        # Alternar o status
        post.is_active = not post.is_active
        if post.scheduled_publication and post.scheduled_publication.status == 'pending':
            post.scheduled_publication.status = 'cancelled'
        status = 'ativado' if post.is_active else 'desativado'

        db.session.commit()

        # Log da atividade
        log_admin_activity(
            user_id=current_user.id,
            action='toggle_status_post',
            description=f'Post "{post.title}" {status}',
            metadata={'post_id': post.id, 'is_active': post.is_active}
        )

        return jsonify({
            'success': True,
            'message': f'Post {status} com sucesso!',
            'is_active': post.is_active
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao alterar status: {str(e)}'}), 500

@app.route("/admin/comments")
@login_required
@editor_required
def admin_comments():
    """
    Página para gerenciar comentários
    """
    # Buscar comentários reais do banco de dados
    comments = Comment.query.order_by(Comment.date_posted.desc()).all()

    # Paginação
    page = request.args.get('page', 1, type=int)
    per_page = 10
    total = len(comments)

    # Calcular itens da página atual
    start = (page - 1) * per_page
    end = start + per_page
    page_comments = comments[start:end]

    # Criar objeto de paginação simples
    class SimplePagination:
        def __init__(self, page, per_page, total, items):
            self.page = page
            self.per_page = per_page
            self.total = total
            self.items = items

        @property
        def pages(self):
            return max(1, math.ceil(self.total / self.per_page))

        @property
        def has_prev(self):
            return self.page > 1

        @property
        def has_next(self):
            return self.page < self.pages

        @property
        def prev_num(self):
            return self.page - 1 if self.has_prev else None

        @property
        def next_num(self):
            return self.page + 1 if self.has_next else None

        def iter_pages(self, left_edge=2, left_current=2, right_current=5, right_edge=2):
            """Método para iterar pelas páginas disponíveis"""
            last = 0
            for num in range(1, self.pages + 1):
                if num <= left_edge or \
                   (num > self.page - left_current - 1 and num < self.page + right_current) or \
                   num > self.pages - right_edge:
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num

    pagination = SimplePagination(page, per_page, total, page_comments)

    # Obter estatísticas para a sidebar
    sidebar_stats = get_admin_sidebar_stats()

    return render_template('admin/comments.html',
                         title="Comentários",
                         comments=page_comments,
                         pagination=pagination,
                         **sidebar_stats)

@app.route("/admin/comments/<int:comment_id>/approve", methods=['POST'])
@login_required
@editor_required
def admin_approve_comment(comment_id):
    """Aprovar um comentário"""
    comment = Comment.query.get_or_404(comment_id)

    try:
        comment.status = 'approved'
        db.session.commit()

        # Log da atividade
        log_admin_activity(
            user_id=current_user.id,
            action='approve_comment',
            description=f'Aprovou comentário de {comment.author_name}',
            metadata={
                'comment_id': comment_id,
                'author': comment.author_name,
                'post_id': comment.post_id
            }
        )
        if _is_ajax_request():
            return jsonify({
                'success': True,
                'message': 'Comentário aprovado com sucesso!',
                'comment_id': comment.id,
                'status': comment.status,
                'total_comments': Comment.query.count(),
            })
        flash('Comentário aprovado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        if _is_ajax_request():
            return jsonify({'success': False, 'message': f'Erro ao aprovar comentário: {str(e)}'}), 500
        flash(f'Erro ao aprovar comentário: {str(e)}', 'error')

    return redirect(url_for('admin_comments'))

@app.route("/admin/comments/<int:comment_id>/reject", methods=['POST'])
@login_required
@editor_required
def admin_reject_comment(comment_id):
    """Rejeitar um comentário"""
    comment = Comment.query.get_or_404(comment_id)

    try:
        comment.status = 'rejected'
        db.session.commit()

        # Log da atividade
        log_admin_activity(
            user_id=current_user.id,
            action='reject_comment',
            description=f'Rejeitou comentário de {comment.author_name}',
            metadata={
                'comment_id': comment_id,
                'author': comment.author_name,
                'post_id': comment.post_id
            }
        )
        if _is_ajax_request():
            return jsonify({
                'success': True,
                'message': 'Comentário rejeitado com sucesso!',
                'comment_id': comment.id,
                'status': comment.status,
                'total_comments': Comment.query.count(),
            })
        flash('Comentário rejeitado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        if _is_ajax_request():
            return jsonify({'success': False, 'message': f'Erro ao rejeitar comentário: {str(e)}'}), 500
        flash(f'Erro ao rejeitar comentário: {str(e)}', 'error')

    return redirect(url_for('admin_comments'))


@app.route("/admin/comments/bulk", methods=['POST'])
@login_required
@editor_required
def admin_bulk_comments():
    """Executa a moderação em massa via JSON, sem navegar para uma tela de redirect."""
    payload = request.get_json(silent=True) or {}
    action = str(payload.get('action') or '').strip().lower()
    raw_ids = payload.get('comment_ids') or []
    all_pending = bool(payload.get('all_pending'))
    if action not in {'approve', 'reject', 'delete', 'spam'}:
        return jsonify({'success': False, 'message': 'Ação de moderação inválida.'}), 400

    try:
        if all_pending:
            comments = Comment.query.filter(
                Comment.is_approved.is_(False),
                db.or_(Comment.moderation_status.is_(None), Comment.moderation_status == 'pending'),
            ).all()
        else:
            if not isinstance(raw_ids, list):
                return jsonify({'success': False, 'message': 'Lista de comentários inválida.'}), 400
            comment_ids = [int(value) for value in raw_ids]
            comments = Comment.query.filter(Comment.id.in_(comment_ids)).all() if comment_ids else []

        if not comments:
            return jsonify({'success': False, 'message': 'Nenhum comentário encontrado para processar.'}), 404

        effective_action = {
            'approve': 'approved',
            'reject': 'rejected',
            'spam': 'rejected',
            'delete': 'delete',
        }[action]
        for comment in comments:
            if effective_action == 'delete':
                db.session.delete(comment)
            else:
                comment.status = effective_action
        db.session.commit()
        log_admin_activity(
            current_user.id,
            'bulk_moderate_comments',
            f'{len(comments)} comentário(s) processado(s): {action}',
            metadata={'action': action, 'count': len(comments)},
        )
        return jsonify({
            'success': True,
            'message': f'{len(comments)} comentário(s) processado(s) com sucesso!',
            'processed_ids': [comment.id for comment in comments],
            'action': effective_action,
            'total_comments': Comment.query.count(),
        })
    except (TypeError, ValueError):
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Identificador de comentário inválido.'}), 400
    except Exception as exc:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao processar comentários: {str(exc)}'}), 500

@app.route("/admin/comments/<int:comment_id>/delete", methods=['POST'])
@login_required
@editor_required
def admin_delete_comment(comment_id):
    """Excluir um comentário"""
    comment = Comment.query.get_or_404(comment_id)
    author_name = comment.author_name
    post_id = comment.post_id
    ajax_request = _is_ajax_request()

    try:
        db.session.delete(comment)
        db.session.commit()

        # Log da atividade
        log_admin_activity(
            user_id=current_user.id,
            action='delete_comment',
            description=f'Excluiu comentário de {author_name}',
            metadata={
                'comment_id': comment_id,
                'author': author_name,
                'post_id': post_id
            }
        )

        if ajax_request:
            return jsonify({
                'success': True,
                'message': 'Comentário excluído com sucesso!',
                'comment_id': comment_id,
                'total_comments': Comment.query.count()
            })
        flash('Comentário excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        if ajax_request:
            return jsonify({
                'success': False,
                'message': f'Erro ao excluir comentário: {str(e)}'
            }), 500
        flash(f'Erro ao excluir comentário: {str(e)}', 'error')

    return redirect(url_for('admin_comments'))

@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    """
    Página para gerenciar usuários
    """
    search_query = request.args.get('q', '').strip()
    role_filter = request.args.get('role', '').strip()
    status_filter = request.args.get('status', '').strip()
    sort_by = request.args.get('sort', '').strip()

    # Buscar todos os usuários reais do banco de dados
    users = User.query.order_by(User.date_joined.desc()).all()
    identities_fixed = False

    # Corrigir dados legados inválidos que podem gerar linhas quebradas no admin
    for user in users:
        user_changed = False
        username = (user.username or '').strip()

        if len(username) < 4:
            seed = (user.email or '').split('@')[0] or f'user{user.id}'
            safe_username = get_unique_username(seed, fallback_prefix='user')
            if safe_username != user.username:
                user.username = safe_username
                user_changed = True

        if not (user.name or '').strip():
            fallback_name = f"{(user.first_name or '').strip()} {(user.last_name or '').strip()}".strip() or user.username
            if fallback_name and fallback_name != user.name:
                user.name = fallback_name
                user_changed = True

        if user_changed:
            identities_fixed = True

    if identities_fixed:
        try:
            db.session.commit()
            users = User.query.order_by(User.date_joined.desc()).all()
        except Exception:
            db.session.rollback()

    user_totals = {
        'total': len(users),
        'admins': sum(1 for user in users if user.role == 'admin'),
        'editors': sum(1 for user in users if user.role == 'editor'),
        'users': sum(1 for user in users if user.role == 'user'),
        'active': sum(1 for user in users if user.is_active),
    }

    filtered_users = list(users)

    if search_query:
        filtered_users = [
            user for user in filtered_users
            if get_search_match_score(
                search_query,
                user.username,
                user.name,
                user.first_name,
                user.last_name,
                user.email,
                user.role,
                user.plan,
                user.location,
                user.phone,
            ) is not None
        ]

    if role_filter:
        filtered_users = [user for user in filtered_users if user.role == role_filter]

    if status_filter == 'active':
        filtered_users = [user for user in filtered_users if user.is_active]
    elif status_filter == 'inactive':
        filtered_users = [user for user in filtered_users if not user.is_active]

    if sort_by == 'email':
        filtered_users.sort(key=lambda user: (user.email or '').casefold())
    elif sort_by == 'role':
        filtered_users.sort(key=lambda user: (user.role or '').casefold())
    elif sort_by == 'date':
        filtered_users.sort(key=lambda user: user.date_joined or datetime.min, reverse=True)
    elif sort_by == 'name':
        filtered_users.sort(key=lambda user: (user.name or user.username or '').casefold())

    # Paginação
    page = request.args.get('page', 1, type=int)
    per_page = 10
    total = len(filtered_users)
    total_pages = max(1, math.ceil(total / per_page))
    page = min(max(page, 1), total_pages)

    # Calcular itens da página atual
    start = (page - 1) * per_page
    end = start + per_page
    page_users = filtered_users[start:end]

    # Criar objeto de paginação
    class SimplePagination:
        def __init__(self, page, per_page, total, items):
            self.page = page
            self.per_page = per_page
            self.total = total
            self.items = items

        @property
        def pages(self):
            return max(1, math.ceil(self.total / self.per_page))

        @property
        def has_prev(self):
            return self.page > 1

        @property
        def has_next(self):
            return self.page < self.pages

        @property
        def prev_num(self):
            return self.page - 1 if self.has_prev else None

        @property
        def next_num(self):
            return self.page + 1 if self.has_next else None

        def iter_pages(self, left_edge=2, left_current=2, right_current=5, right_edge=2):
            """Método para iterar pelas páginas disponíveis"""
            last = 0
            for num in range(1, self.pages + 1):
                if num <= left_edge or \
                   (num > self.page - left_current - 1 and num < self.page + right_current) or \
                   num > self.pages - right_edge:
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num

    pagination = SimplePagination(page, per_page, total, page_users)

    # Obter estatísticas para a sidebar
    sidebar_stats = get_admin_sidebar_stats()

    return render_template('admin/users.html',
                         title="Usuários",
                         users=page_users,
                         pagination=pagination,
                         user_totals=user_totals,
                         current_filters={
                             'q': search_query,
                             'role': role_filter,
                             'status': status_filter,
                             'sort': sort_by,
                         },
                         **sidebar_stats)

@app.route("/admin/users/<int:user_id>/data")
@login_required
@admin_required
def admin_user_data(user_id):
    """Retorna dados do usuário em JSON para edição"""
    user = User.query.get_or_404(user_id)
    return jsonify(serialize_user_for_admin(user))

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_user_delete(user_id):
    """Rota para excluir um usuário"""
    user = User.query.get_or_404(user_id)

    # Prevenir auto-exclusão
    if user.id == current_user.id:
        flash('Você não pode excluir sua própria conta.', 'danger')
        return redirect(url_for('admin_users'))

    try:
        # Excluir downloads associados? O cascade deve cuidar disso se configurado
        # Excluir usuário
        db.session.delete(user)
        db.session.commit()
        flash(f'Usuário {user.username} excluído com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Erro ao excluir usuário {user.id}: {e}")
        flash('Erro ao excluir usuário. Pode haver registros associados.', 'danger')

    return redirect(url_for('admin_users'))


@app.route("/admin/users/<int:user_id>/update", methods=['POST'])
@login_required
@admin_required
def admin_update_user(user_id):
    """Atualiza dados do usuário"""
    try:
        user = User.query.get_or_404(user_id)
        incoming_json = request.get_json(silent=True) if request.is_json else None
        source = incoming_json if isinstance(incoming_json, dict) else request.form

        def field_value(name, current=None):
            value = source.get(name, current)
            if isinstance(value, str):
                return value.strip()
            return value

        # Obter dados do formulário (permitir atualização parcial)
        username = field_value('username', user.username)
        name = field_value('name', user.name or '')
        email = field_value('email', user.email)
        role = field_value('role', user.role)
        plan = field_value('plan', user.plan)
        is_active = coerce_bool(source.get('is_active'), user.is_active) if 'is_active' in source else user.is_active
        is_verified = coerce_bool(source.get('is_verified'), user.is_verified) if 'is_verified' in source else user.is_verified
        email_notifications = coerce_bool(source.get('email_notifications'), user.email_notifications) if 'email_notifications' in source else user.email_notifications

        first_name = field_value('first_name', user.first_name or '')
        last_name = field_value('last_name', user.last_name or '')
        bio = field_value('bio', user.bio or '')
        location = field_value('location', user.location or '')
        phone = field_value('phone', user.phone or '')
        website = field_value('website', user.website or '')
        facebook = field_value('facebook', user.facebook or '')
        twitter = field_value('twitter', user.twitter or '')
        instagram = field_value('instagram', user.instagram or '')
        linkedin = field_value('linkedin', user.linkedin or '')
        github = field_value('github', user.github or '')
        ip_address = field_value('ip_address', user.ip_address or '')
        browser = field_value('browser', user.browser or '')
        operating_system = field_value('operating_system', user.operating_system or '')
        referrer = field_value('referrer', user.referrer or '')

        # Novos campos de permissões de download
        can_download = coerce_bool(source.get('can_download'), user.can_download) if 'can_download' in source else user.can_download
        custom_daily_limit = field_value('custom_daily_limit', user.custom_daily_limit if user.custom_daily_limit is not None else '')
        custom_weekly_limit = field_value('custom_weekly_limit', user.custom_weekly_limit if user.custom_weekly_limit is not None else '')

        def parse_optional_limit(value, maximum):
            if value in ('', None):
                return None
            parsed = int(value)
            if parsed < 0 or parsed > maximum:
                raise ValueError
            return parsed

        try:
            parsed_daily_limit = parse_optional_limit(custom_daily_limit, 1000)
            parsed_weekly_limit = parse_optional_limit(custom_weekly_limit, 10000)
        except (TypeError, ValueError):
            return jsonify({
                'success': False,
                'message': 'Informe limites de download válidos e não negativos.'
            }), 400

        # Validações
        # Validações de segurança
        if user_id == current_user.id and not is_active:
            return jsonify({'success': False, 'message': 'Você não pode desativar sua própria conta.'})

        if not username:
            return jsonify({'success': False, 'message': 'Nome de usuário é obrigatório'})

        if not email:
            return jsonify({'success': False, 'message': 'Email é obrigatório'})

        if role not in ['user', 'editor', 'admin']:
            return jsonify({'success': False, 'message': 'Função inválida'})

        if plan not in ['free', 'premium', 'vip']:
            return jsonify({'success': False, 'message': 'Plano inválido'})

        # Verificar se username já existe (exceto para o próprio usuário)
        existing_user = User.query.filter(User.username == username, User.id != user_id).first()
        if existing_user:
            return jsonify({'success': False, 'message': 'Nome de usuário já existe'})

        # Verificar se email já existe (exceto para o próprio usuário)
        existing_email = User.query.filter(User.email == email, User.id != user_id).first()
        if existing_email:
            return jsonify({'success': False, 'message': 'Email já está em uso'})

        # Atualizar dados
        old_data = {
            'username': user.username,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'plan': user.plan,
            'is_active': user.is_active,
            'is_verified': user.is_verified,
            'email_notifications': user.email_notifications,
            'can_download': user.can_download if hasattr(user, 'can_download') else True,
            'custom_daily_limit': user.custom_daily_limit if hasattr(user, 'custom_daily_limit') else None,
            'custom_weekly_limit': user.custom_weekly_limit if hasattr(user, 'custom_weekly_limit') else None
        }

        user.username = username
        user.name = name if name else None
        user.email = email
        user.role = role
        user.plan = plan
        user.is_active = is_active
        user.is_verified = is_verified
        user.email_notifications = email_notifications
        user.first_name = first_name or None
        user.last_name = last_name or None
        user.bio = bio or None
        user.location = location or None
        user.phone = phone or None
        user.website = website or None
        user.facebook = facebook or None
        user.twitter = twitter or None
        user.instagram = instagram or None
        user.linkedin = linkedin or None
        user.github = github or None
        # ip_address, browser, operating_system e referrer são gerenciados
        # automaticamente pelo sistema de login e não devem ser editados manualmente

        # Atualizar permissões de download
        user.can_download = can_download
        user.custom_daily_limit = parsed_daily_limit
        user.custom_weekly_limit = parsed_weekly_limit

        db.session.commit()

        # Log da atividade
        log_admin_activity(
            user_id=current_user.id,
            action='update_user',
            description=f'Atualizou dados do usuário {username}',
            metadata={
                'target_user_id': user_id,
                'old_data': old_data,
                'new_data': {
                    'username': username,
                    'name': name,
                    'email': email,
                    'role': role,
                    'plan': plan,
                    'is_active': is_active,
                    'is_verified': is_verified,
                    'email_notifications': email_notifications,
                    'can_download': can_download,
                    'custom_daily_limit': user.custom_daily_limit,
                    'custom_weekly_limit': user.custom_weekly_limit
                }
            }
        )

        return jsonify({
            'success': True,
            'message': 'Usuário atualizado com sucesso',
            'user': serialize_user_for_admin(user)
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao atualizar usuário: {str(e)}'})

@app.route("/admin/users/<int:user_id>/reset-password", methods=['POST'])
@login_required
@admin_required
def admin_reset_user_password(user_id):
    """Redefinir senha do usuário pelo admin"""
    try:
        user = User.query.get_or_404(user_id)

        # Obter nova senha do JSON
        data = request.get_json() or {}
        new_password = data.get('new_password', '').strip()

        # Validações
        if not new_password:
            return jsonify({'success': False, 'message': 'Nova senha é obrigatória'})

        is_valid, password_error = validate_password_strength(new_password)
        if not is_valid:
            return jsonify({'success': False, 'message': password_error}), 400

        # Não permitir redefinir senha do próprio usuário desta forma
        if user.id == current_user.id:
            return jsonify({'success': False, 'message': 'Use a página de perfil para alterar sua própria senha'})

        # Atualizar senha
        user.password = generate_password_hash(new_password)
        db.session.commit()
        app.logger.info(f"Reset de senha executado para user_id={user.id} por admin_id={current_user.id}")

        # Log da atividade
        log_admin_activity(
            user_id=current_user.id,
            action='reset_user_password',
            description=f'Redefiniu a senha do usuário {user.username}',
            metadata={
                'target_user_id': user_id,
                'target_username': user.username
            }
        )

        return jsonify({'success': True, 'message': f'Senha do usuário {user.username} redefinida com sucesso'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao redefinir senha: {str(e)}'})

@app.route("/admin/users/<int:user_id>/download-limits", methods=['POST'])
@login_required
@admin_required
def admin_update_download_limits(user_id):
    """Atualizar limites de download do usuário"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'JSON inválido'}), 400
        if not data:
            return jsonify({'success': False, 'message': 'Dados inválidos'}), 400

        action = data.get('action')
        period = data.get('period', 'daily')  # daily, weekly, monthly
        value = data.get('value', 0)

        brasilia = pytz.timezone('America/Sao_Paulo')
        now = datetime.now(brasilia)

        old_values = {
            'daily_downloads': user.daily_downloads,
            'weekly_downloads': user.weekly_downloads
        }

        if action == 'reset':
            # Resetar contadores
            if period == 'daily' or period == 'all':
                user.daily_downloads = 0
                user.download_reset_date = now + timedelta(days=1)
                user.download_reset_date = user.download_reset_date.replace(hour=0, minute=0, second=0, microsecond=0)

            if period == 'weekly' or period == 'all':
                user.weekly_downloads = 0
                # Próximo domingo
                days_until_sunday = (6 - now.weekday()) % 7
                if days_until_sunday == 0:
                    days_until_sunday = 7
                next_sunday = now + timedelta(days=days_until_sunday)
                user.week_reset_date = next_sunday.replace(hour=0, minute=0, second=0, microsecond=0)

            message = f"Limite de download {'diário e semanal' if period == 'all' else period} resetado"

        elif action == 'set':
            # Definir valor exato
            if period == 'daily':
                user.daily_downloads = int(value)
            elif period == 'weekly':
                user.weekly_downloads = int(value)
            message = f"Downloads {period} definidos para {value}"

        elif action == 'increase':
            # Aumentar valor
            if period == 'daily':
                user.daily_downloads = (user.daily_downloads or 0) + int(value)
            elif period == 'weekly':
                user.weekly_downloads = (user.weekly_downloads or 0) + int(value)
            message = f"Downloads {period} aumentados em {value}"

        elif action == 'decrease':
            # Diminuir valor
            if period == 'daily':
                user.daily_downloads = max(0, (user.daily_downloads or 0) - int(value))
            elif period == 'weekly':
                user.weekly_downloads = max(0, (user.weekly_downloads or 0) - int(value))
            message = f"Downloads {period} diminuídos em {value}"
        else:
            return jsonify({'success': False, 'message': 'Ação inválida'})

        db.session.commit()

        # Log da atividade
        log_admin_activity(
            user_id=current_user.id,
            action='update_download_limits',
            description=f'Atualizou limites de download de {user.username}',
            metadata={
                'target_user_id': user_id,
                'action': action,
                'period': period,
                'value': value,
                'old_values': old_values,
                'new_values': {
                    'daily_downloads': user.daily_downloads,
                    'weekly_downloads': user.weekly_downloads
                }
            }
        )

        return jsonify({
            'success': True,
            'message': message,
            'daily_downloads': user.daily_downloads,
            'weekly_downloads': user.weekly_downloads
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao atualizar limites: {str(e)}'})

@app.route("/admin/users/<int:user_id>/verify", methods=['POST'])
@login_required
@admin_required
def admin_verify_user(user_id):
    """Verificar ou desverificar email do usuário"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'JSON inválido'}), 400

        verify = data.get('verify', True)
        user.is_verified = verify

        db.session.commit()

        # Log da atividade
        log_admin_activity(
            user_id=current_user.id,
            action='verify_user' if verify else 'unverify_user',
            description=f'{"Verificou" if verify else "Desverificou"} o email de {user.username}',
            metadata={
                'target_user_id': user_id,
                'verified': verify
            }
        )

        return jsonify({
            'success': True,
            'message': f'Email {"verificado" if verify else "desverificado"} com sucesso!'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao atualizar verificação: {str(e)}'})

@app.route("/admin/users/<int:user_id>/permissions", methods=['POST'])
@login_required
@admin_required
def admin_update_permissions(user_id):
    """Atualizar permissões (role) do usuário"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'JSON inválido'}), 400
        if not data:
            return jsonify({'success': False, 'message': 'Dados inválidos'}), 400

        new_role = data.get('role', 'user')

        # Validar role
        if new_role not in ['user', 'editor', 'admin']:
            return jsonify({'success': False, 'message': 'Função inválida'})

        # Prevenir que o admin remova seu próprio acesso admin
        if user.id == current_user.id and new_role != 'admin':
            return jsonify({'success': False, 'message': 'Você não pode remover suas próprias permissões de admin'})

        old_role = user.role
        user.role = new_role

        db.session.commit()

        # Log da atividade
        log_admin_activity(
            user_id=current_user.id,
            action='update_user_permissions',
            description=f'Alterou permissões de {user.username} de {old_role} para {new_role}',
            metadata={
                'target_user_id': user_id,
                'old_role': old_role,
                'new_role': new_role
            }
        )

        return jsonify({
            'success': True,
            'message': f'Permissões atualizadas! Usuário agora é {new_role}'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao atualizar permissões: {str(e)}'})

@app.route("/admin/newsletter")
@login_required
@admin_required
def admin_newsletter():
    """
    Página para gerenciar a newsletter
    """
    # Buscar todos os inscritos reais da newsletter
    subscribers = Subscriber.query.order_by(Subscriber.subscribed_date.desc()).all()

    # Paginação para assinantes
    page = request.args.get('page', 1, type=int)
    per_page = 10
    total_subscribers_count = len(subscribers)

    # Calcular itens da página atual
    start = (page - 1) * per_page
    end = start + per_page
    page_subscribers = subscribers[start:end]

    # Criar objeto de paginação
    class SimplePagination:
        def __init__(self, page, per_page, total, items):
            self.page = page
            self.per_page = per_page
            self.total = total
            self.items = items

        @property
        def pages(self):
            return max(1, math.ceil(self.total / self.per_page))

        @property
        def has_prev(self):
            return self.page > 1

        @property
        def has_next(self):
            return self.page < self.pages

        @property
        def prev_num(self):
            return self.page - 1 if self.has_prev else None

        @property
        def next_num(self):
            return self.page + 1 if self.has_next else None

        def iter_pages(self, left_edge=2, left_current=2, right_current=5, right_edge=2):
            """Método para iterar pelas páginas disponíveis"""
            last = 0
            for num in range(1, self.pages + 1):
                if num <= left_edge or \
                   (num > self.page - left_current - 1 and num < self.page + right_current) or \
                   num > self.pages - right_edge:
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num

    pagination = SimplePagination(page, per_page, total_subscribers_count, page_subscribers)

    # Estatísticas da newsletter
    total_subscribers = total_subscribers_count
    active_subscribers = len([s for s in subscribers if s.is_active])
    recent_subscribers = len([s for s in subscribers if s.subscribed_date >= (datetime.utcnow() - timedelta(days=30))])
    newsletter_groups = NewsletterGroup.query.order_by(NewsletterGroup.name.asc()).all()
    newsletter_group_counts = {
        group.id: sum(1 for subscriber in group.subscribers if subscriber.is_active)
        for group in newsletter_groups
    }

    # Obter estatísticas para a sidebar
    sidebar_stats = get_admin_sidebar_stats()

    return render_template('admin/newsletter.html',
                         title="Newsletter",
                         subscribers=page_subscribers,
                         pagination=pagination,
                         total_subscribers=total_subscribers,
                         active_subscribers=active_subscribers,
                         recent_subscribers=recent_subscribers,
                         newsletter_groups=newsletter_groups,
                         newsletter_group_counts=newsletter_group_counts,
                         **sidebar_stats)

@app.route('/downgrade_plan', methods=['POST'])
@login_required
def downgrade_plan():
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'JSON inválido'}), 400
        target_plan = data.get('target_plan', 'free')

        # Validar plano de destino
        if target_plan not in ['free', 'premium', 'vip']:
            return jsonify({'success': False, 'message': 'Plano inválido.'}), 400

        if not is_plan_enabled(target_plan):
            return jsonify({
                'success': False,
                'message': 'Este plano está temporariamente indisponível para alterações.'
            }), 409

        # Verificar se é realmente um downgrade
        plan_hierarchy = {'free': 0, 'premium': 1, 'vip': 2}
        current_level = plan_hierarchy.get(current_user.plan, 0)
        target_level = plan_hierarchy.get(target_plan, 0)

        if target_level >= current_level:
            return jsonify({'success': False, 'message': 'Isso não é um downgrade.'}), 400

        # Realizar downgrade
        current_user.plan = target_plan
        db.session.commit()

        # Mensagem personalizada
        plan_name = get_plan_metadata(target_plan)['label']
        message = f'Seu plano foi alterado para {plan_name} com sucesso.'

        return jsonify({'success': True, 'message': message})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao alterar plano: {str(e)}'}), 500


@app.route("/admin/tools/backup")
@login_required
@admin_required
def admin_tools_backup():
    """
    Página para gerenciar backups
    """
    # Obter estatísticas para a sidebar
    sidebar_stats = get_admin_sidebar_stats()

    # Obter lista de backups existentes
    backups = Backup.query.order_by(Backup.created_at.desc()).all()

    return render_template('admin/tools_backup.html',
                         title="Backup e Restauração",
                         backups=backups,
                         **sidebar_stats)

@app.route("/admin/tools/backup/create", methods=['POST'])
@login_required
@admin_required
def admin_create_backup():
    """
    Criar novo backup
    """
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'JSON inválido'}), 400
        backup_type = data.get('backup_type', 'database')
        description = data.get('description', '')

        # Executar backup baseado no tipo
        if backup_type == 'database':
            result = create_database_backup()
        elif backup_type == 'files':
            result = create_files_backup()
        elif backup_type == 'full':
            result = create_full_backup()
        else:
            return jsonify({'success': False, 'message': 'Tipo de backup inválido'})

        if result['success']:
            # Salvar informações do backup no banco
            backup = Backup(
                filename=result['filename'],
                file_path=result['file_path'],
                backup_type=backup_type,
                file_size=result['file_size'],
                created_by=current_user.id,
                description=description,
                is_automatic=False,
                status='completed'
            )

            db.session.add(backup)
            db.session.commit()

            # Log da atividade
            log_admin_activity(
                user_id=current_user.id,
                action="backup_created",
                description=f"Backup {backup_type} criado: {result['filename']}",
                metadata={
                    'backup_type': backup_type,
                    'filename': result['filename'],
                    'file_size': result['file_size']
                }
            )

            return jsonify({
                'success': True,
                'message': 'Backup criado com sucesso!',
                'backup': {
                    'id': backup.id,
                    'filename': backup.filename,
                    'backup_type': backup.backup_type,
                    'file_size': backup.get_file_size_formatted(),
                    'created_at': backup.created_at.strftime('%d/%m/%Y às %H:%M')
                }
            })
        else:
            return jsonify({'success': False, 'message': f'Erro ao criar backup: {result["error"]}'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro interno: {str(e)}'})

@app.route("/admin/tools/backup/download/<int:backup_id>")
@login_required
@admin_required
def admin_download_backup(backup_id):
    """
    Download de backup
    """
    try:
        backup = Backup.query.get_or_404(backup_id)

        if os.path.exists(backup.file_path):
            # Log da atividade
            log_admin_activity(
                user_id=current_user.id,
                action="backup_downloaded",
                description=f"Download do backup: {backup.filename}",
                metadata={
                    'backup_id': backup_id,
                    'filename': backup.filename
                }
            )

            return send_file(
                backup.file_path,
                as_attachment=True,
                download_name=backup.filename
            )
        else:
            flash('Arquivo de backup não encontrado', 'error')
            return redirect(url_for('admin_tools_backup'))

    except Exception as e:
        flash(f'Erro ao baixar backup: {str(e)}', 'error')
        return redirect(url_for('admin_tools_backup'))

@app.route("/admin/tools/backup/delete/<int:backup_id>", methods=['DELETE'])
@login_required
@admin_required
def admin_delete_backup(backup_id):
    """
    Excluir backup
    """
    try:
        backup = Backup.query.get_or_404(backup_id)

        # Remover arquivo físico
        if os.path.exists(backup.file_path):
            os.remove(backup.file_path)

        # Remover do banco
        db.session.delete(backup)
        db.session.commit()

        # Log da atividade
        log_admin_activity(
            user_id=current_user.id,
            action="backup_deleted",
            description=f"Backup excluído: {backup.filename}",
            metadata={
                'backup_id': backup_id,
                'filename': backup.filename
            }
        )

        return jsonify({'success': True, 'message': 'Backup excluído com sucesso!'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao excluir backup: {str(e)}'})

@app.route("/admin/tools/import")
@login_required
@admin_required
def admin_tools_import():
    """Central única de ingestão, datasheets, revisão e publicação."""
    ensure_default_content_sources()
    ensure_default_datasheet_providers()
    sidebar_stats = get_admin_sidebar_stats()
    jobs = ImportJob.query.order_by(ImportJob.created_at.desc()).limit(25).all()
    review_items = ImportItem.query.filter(
        ImportItem.status.in_(['pending_review', 'needs_review', 'needs_storage', 'duplicate', 'error'])
    ).order_by(ImportItem.created_at.desc()).limit(100).all()
    automatic_items = ImportItem.query.filter_by(
        status='published', published_automatically=True
    ).order_by(ImportItem.reviewed_at.desc()).limit(50).all()
    automatic_datasheets = ElectronicComponent.query.filter_by(
        publication_mode='automatic', is_published=True
    ).filter(ElectronicComponent.post_id.isnot(None)).order_by(
        ElectronicComponent.published_at.desc()
    ).limit(50).all()
    sources = ContentSource.query.order_by(ContentSource.trust_level.asc(), ContentSource.name.asc()).all()
    contributions = FileContribution.query.order_by(FileContribution.created_at.desc()).limit(50).all()
    health_files = TechnicalFile.query.order_by(
        TechnicalFile.last_link_check_at.desc().nullslast(), TechnicalFile.created_at.desc()
    ).limit(100).all()
    link_health = {
        'active': TechnicalFile.query.filter_by(is_active=True, link_status='online').count(),
        'broken': TechnicalFile.query.filter_by(is_active=True, link_status='broken').count(),
        'unchecked': TechnicalFile.query.filter(
            TechnicalFile.is_active == True,
            TechnicalFile.link_status.in_(['unchecked', 'unknown', 'needs_review']),
        ).count(),
        'total': TechnicalFile.query.filter_by(is_active=True).count(),
    }
    datasheet_items = DatasheetImportQueue.query.order_by(
        DatasheetImportQueue.priority.desc(), DatasheetImportQueue.created_at.desc()
    ).limit(100).all()
    datasheet_stats = {
        'queued': DatasheetImportQueue.query.filter_by(status='queued').count(),
        'review': DatasheetImportQueue.query.filter_by(status='needs_review').count(),
        'published': DatasheetImportQueue.query.filter_by(status='published').count(),
        'posts': ElectronicComponent.query.filter(ElectronicComponent.post_id.isnot(None)).count(),
    }
    source_parts = DatasheetProviderConfig.query.filter_by(provider_name='source_parts').first()
    datasheet_source = {
        'name': source_parts.display_name if source_parts else 'Source Parts',
        'enabled': bool(source_parts and source_parts.enabled),
        'credentials_configured': bool(
            source_parts and datasheet_provider_credentials_status(source_parts)['configured']
        ),
        'publication_ready': bool(
            source_parts
            and source_parts.metadata_persistence_allowed
            and source_parts.public_republish_allowed
            and source_parts.written_permission_confirmed
        ),
        'permission_reference': source_parts.permission_reference if source_parts else '',
    }
    sidebar_stats['technical_review_count'] = len(review_items) + datasheet_stats['review']
    return render_template('admin/tools_import.html',
                         title="Conteúdo Técnico",
                         jobs=jobs,
                         review_items=review_items,
                         automatic_items=automatic_items,
                         automatic_datasheets=automatic_datasheets,
                         sources=sources,
                         contributions=contributions,
                         health_files=health_files,
                         link_health=link_health,
                         automation=get_technical_automation_settings(),
                         datasheet_settings=get_datasheet_settings(),
                         datasheet_items=datasheet_items,
                         datasheet_stats=datasheet_stats,
                         datasheet_source=datasheet_source,
                         **sidebar_stats)


@app.route('/api/admin/technical-import/settings', methods=['POST'])
@login_required
@admin_required
def admin_technical_import_settings():
    payload = request.get_json(silent=True) or {}
    unknown = set(payload) - TECHNICAL_AUTOMATION_KEYS
    if unknown:
        return jsonify({'success': False, 'message': f'Configurações não suportadas: {", ".join(sorted(unknown))}'}), 400
    mode = str(payload.get('technical_automation_mode', SiteConfig.get_value('technical_automation_mode', 'semi'))).lower()
    if mode not in {'off', 'semi', 'full'}:
        return jsonify({'success': False, 'message': 'Modo inválido.'}), 400
    enabled = mode != 'off'
    automation_percentage_default = coerce_int(
        SiteConfig.get_value('technical_automation_percentage', 100),
        100,
    )
    auto_publish_threshold_default = coerce_int(
        SiteConfig.get_value('technical_auto_publish_threshold', 85),
        85,
    )
    require_storage_ready_default = coerce_bool(
        SiteConfig.get_value('technical_require_storage_ready', True),
        True,
    )
    values = {
        'technical_import_enabled': (
            coerce_bool(payload.get('technical_import_enabled'), enabled) if mode != 'off' else False,
            'bool',
        ),
        'technical_automation_mode': (mode, 'string'),
        'technical_automation_percentage': (
            max(0, min(100, coerce_int(
                payload.get('technical_automation_percentage'),
                automation_percentage_default,
            ))), 'int'
        ),
        'technical_auto_publish_threshold': (
            max(0, min(100, coerce_int(
                payload.get('technical_auto_publish_threshold'),
                auto_publish_threshold_default,
            ))), 'int'
        ),
        'technical_require_storage_ready': (
            coerce_bool(
                payload.get('technical_require_storage_ready'),
                require_storage_ready_default,
            ),
            'bool',
        ),
    }
    for key, (value, value_type) in values.items():
        SiteConfig.set_value(key, value, value_type=value_type, is_public=False)
    SiteConfig.set_value('datasheet_engine_enabled', enabled, value_type='bool', is_public=False)
    SiteConfig.set_value('datasheet_auto_publish_enabled', mode == 'full', value_type='bool', is_public=False)
    SiteConfig.set_value('datasheet_automation_paused', False, value_type='bool', is_public=False)
    ensure_default_datasheet_providers()
    provider_mode = {'off': 'disabled', 'semi': 'semi_automatic', 'full': 'automatic'}[mode]
    DatasheetProviderConfig.query.update({DatasheetProviderConfig.mode: provider_mode})
    db.session.commit()
    return jsonify({
        'success': True,
        'settings': get_technical_automation_settings(),
        'datasheet_settings': get_datasheet_settings(),
    })


@app.route('/api/admin/technical-import/datasheets/source-policy', methods=['POST'])
@login_required
@admin_required
def admin_datasheet_source_policy():
    """Configura somente a autorização necessária para gerar posts; PDFs permanecem protegidos."""
    payload = request.get_json(silent=True) or {}
    confirmed = coerce_bool(payload.get('publication_authorized'), False)
    reference = sanitize_input(str(payload.get('permission_reference') or ''))[:500]
    if confirmed and not reference:
        return jsonify({
            'success': False,
            'message': 'Informe o contrato, termo, e-mail ou outra referência que autoriza a publicação.',
        }), 400
    ensure_default_datasheet_providers()
    config = DatasheetProviderConfig.query.filter_by(provider_name='source_parts').first_or_404()
    config.metadata_persistence_allowed = confirmed
    config.public_republish_allowed = confirmed
    config.written_permission_confirmed = confirmed
    config.permission_reference = reference or None
    config.terms_last_checked_at = datetime.utcnow() if confirmed else config.terms_last_checked_at
    db.session.commit()
    return jsonify({
        'success': True,
        'publication_ready': confirmed,
        'message': 'Autorização da fonte atualizada.',
    })


@app.route('/api/admin/technical-import/sources/<int:source_id>', methods=['PATCH', 'POST'])
@login_required
@admin_required
def admin_technical_source_update(source_id):
    source = ContentSource.query.get_or_404(source_id)
    payload = request.get_json(silent=True) or request.form.to_dict()
    trust = str(payload.get('trust_level', source.trust_level)).upper()
    if trust not in {'A', 'B', 'C', 'D'}:
        return jsonify({'success': False, 'message': 'Nível de confiança inválido.'}), 400
    source.trust_level = trust
    for field in (
        'enabled', 'auto_publish', 'metadata_allowed', 'distribution_allowed',
        'file_mirroring_allowed', 'attribution_required',
    ):
        if field in payload:
            setattr(source, field, coerce_bool(payload[field], getattr(source, field)))
    if 'part_numbers' in payload:
        raw_parts = payload.get('part_numbers') or ''
        if isinstance(raw_parts, str):
            raw_parts = re.split(r'[,;\n]+', raw_parts)
        parts = []
        for raw_part in list(raw_parts)[:100]:
            part = sanitize_input(str(raw_part)).strip()[:160]
            if part and part.lower() not in {existing.lower() for existing in parts}:
                parts.append(part)
        config = source.configuration()
        config['part_numbers'] = parts
        source.config_json = json.dumps(config, ensure_ascii=False)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Política da fonte atualizada.'})


@app.route('/api/admin/technical-import/sources/<int:source_id>/sync', methods=['POST'])
@login_required
@admin_required
@limiter.limit('10 per hour')
def admin_technical_source_sync(source_id):
    source = ContentSource.query.get_or_404(source_id)
    if not source.enabled:
        return jsonify({'success': False, 'message': 'Ative a fonte antes de sincronizar.'}), 409
    # Import tardio evita acoplamento circular no boot dos jobs CLI.
    from jobs.sync_configured_sources import run as run_source_sync
    result = run_source_sync({source.name}, reviewer_id=current_user.id)
    items_count = coerce_int(result.get('items'), 0)
    raw_messages = result.get('messages')
    messages = raw_messages if isinstance(raw_messages, list) else []
    if not items_count:
        message = messages[0] if messages else (source.last_error or 'Nenhum item novo foi encontrado.')
        return jsonify({'success': False, 'message': message, 'result': result}), 409
    return jsonify({
        'success': True,
        'message': f'{items_count} item(ns) analisado(s); previews atualizados.',
        'result': result,
    })


@app.route('/api/admin/technical-import/analyze', methods=['POST'])
@login_required
@admin_required
@limiter.limit('20 per hour')
def admin_technical_import_analyze():
    if not app.config.get('TECHNICAL_IMPORT_ENABLED'):
        return jsonify({'success': False, 'message': 'O motor está desativado pela configuração de ambiente.'}), 503
    automation = get_technical_automation_settings()
    job_type = sanitize_input(str(request.form.get('type') or (request.get_json(silent=True) or {}).get('type') or 'files'))[:40]
    source_name = sanitize_input(str(request.form.get('source') or (request.get_json(silent=True) or {}).get('source') or 'Admin'))[:120]
    job = ImportJob(
        job_type=job_type,
        source=source_name,
        status='processing',
        automation_mode=automation['mode'],
        created_by=current_user.id,
        started_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db.session.add(job)
    db.session.flush()
    created_items = []
    errors = []
    try:
        uploads = request.files.getlist('files') or request.files.getlist('files[]')
        if request.files.get('file'):
            uploads.append(request.files['file'])
        for upload in uploads[:50]:
            try:
                created_items.extend(_analyze_uploaded_file(job, upload))
            except (ValueError, ArchiveSafetyError, OSError) as exc:
                errors.append(f'{sanitize_download_name(upload.filename or "arquivo-tecnico")}: {exc}')
                job.error_count += 1

        payload = request.get_json(silent=True) or request.form.to_dict()
        if job_type in {'link', 'links'}:
            link_items = payload.get('items') or []
            if isinstance(link_items, str):
                try:
                    link_items = json.loads(link_items)
                except (TypeError, ValueError, json.JSONDecodeError):
                    link_items = [{'provider_url': link_items}]
            if payload.get('provider_url'):
                link_items.append(payload)
            for link_data in list(link_items)[:100]:
                if not isinstance(link_data, dict):
                    continue
                provider_url = normalize_download_url(link_data.get('provider_url') or link_data.get('url'))
                if not provider_url or not provider_url.startswith(('http://', 'https://')):
                    errors.append('Um link informado é inválido.')
                    job.error_count += 1
                    continue
                filename = link_data.get('filename') or os.path.basename(url_parse(provider_url).path) or 'arquivo-tecnico.bin'
                metadata = _merge_parsed_metadata(filename, {
                    **link_data,
                    'provider_url': provider_url,
                    'distribution_policy': link_data.get('distribution_policy') or 'external_storage_allowed',
                })
                created_items.append(_append_import_item(job, metadata, source_name=filename, raw={'kind': 'link'}))

        if not created_items:
            job.status = 'error'
            job.finished_at = datetime.utcnow()
            job.log_summary = '\n'.join(errors) or 'Nenhum item técnico foi recebido.'
            db.session.commit()
            return jsonify({'success': False, 'message': job.log_summary, 'job_id': job.id}), 400

        job.status = 'reviewing'
        job.log_summary = '\n'.join(errors) if errors else 'Análise concluída.'
        db.session.commit()

        for duplicate_item in created_items:
            if duplicate_item.status == 'duplicate':
                _cleanup_import_item_temp(duplicate_item)
        db.session.commit()

        source = ContentSource.query.filter(db.func.lower(ContentSource.name) == source_name.lower()).first()
        auto_published = 0
        for created in list(created_items):
            created = db.session.get(ImportItem, created.id)
            if created.status == 'duplicate':
                continue
            should_publish, reason = technical_auto_publish_decision(created, source)
            created.decision_reason = reason
            db.session.commit()
            if should_publish:
                try:
                    publish_import_item(created, reviewer_id=current_user.id, automatic=True)
                    auto_published += 1
                except ValueError as exc:
                    created.decision_reason = str(exc)
                    db.session.commit()

        return jsonify({
            'success': True,
            'job_id': job.id,
            'items': len(created_items),
            'errors': errors,
            'auto_published': auto_published,
            'message': 'Análise concluída. Os previews estão disponíveis no painel.',
        }), 201
    except Exception as exc:
        db.session.rollback()
        app.logger.exception('Falha ao analisar importação técnica')
        return jsonify({'success': False, 'message': f'Falha na análise: {exc}'}), 500


@app.route('/api/admin/technical-import/items/<int:item_id>', methods=['PATCH'])
@login_required
@admin_required
def admin_technical_import_item_update(item_id):
    item = ImportItem.query.get_or_404(item_id)
    if item.status == 'published':
        return jsonify({'success': False, 'message': 'O item já foi publicado.'}), 409
    payload = request.get_json(silent=True) or {}
    metadata = item.normalized_data()
    editable = {
        'manufacturer', 'model', 'board_code', 'board_revision', 'version', 'file_type',
        'chip_type', 'chip_position', 'part_number', 'source_provider', 'source_url',
        'provider_url', 'provider_direct_url', 'storage_provider', 'distribution_policy',
        'license_status', 'mime_type', 'title', 'description',
        'external_id', 'external_version',
    }
    for key in editable:
        if key in payload:
            metadata[key] = sanitize_input(str(payload[key] or ''))[:2000]
    if 'confidence' in payload:
        item.confidence = max(0, min(100, coerce_int(payload['confidence'], item.confidence)))
        metadata['confidence'] = item.confidence
    metadata['board_code'] = format_board_code(metadata.get('board_code'))
    metadata['copy'] = build_post_copy(metadata)
    item.normalized_data_json = json.dumps(metadata, ensure_ascii=False)
    item.status = 'pending_review'
    item.decision_reason = 'Preview editado; aguardando aprovação.'
    db.session.commit()
    return jsonify({'success': True, 'message': 'Preview atualizado.', 'item': metadata})


@app.route('/api/admin/technical-import/items/<int:item_id>/approve', methods=['POST'])
@login_required
@admin_required
def admin_technical_import_item_approve(item_id):
    item = ImportItem.query.get_or_404(item_id)
    try:
        publish_import_item(item, reviewer_id=current_user.id, automatic=False)
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc), 'status': item.status}), 409
    return jsonify({
        'success': True,
        'message': 'Item publicado com sucesso.',
        'post_id': item.post_id,
        'url': url_for('post', post_id=item.post_id),
    })


@app.route('/api/admin/technical-import/items/<int:item_id>/reject', methods=['POST'])
@login_required
@admin_required
def admin_technical_import_item_reject(item_id):
    item = ImportItem.query.get_or_404(item_id)
    if item.status == 'published':
        return jsonify({'success': False, 'message': 'Posts publicados devem ser gerenciados na tela de posts.'}), 409
    payload = request.get_json(silent=True) or {}
    item.status = 'rejected'
    item.reviewed_by = current_user.id
    item.reviewed_at = datetime.utcnow()
    item.decision_reason = sanitize_input(str(payload.get('reason') or 'Rejeitado pelo administrador.'))[:500]
    item.job.review_count = max(0, item.job.review_count - 1)
    terminal = {'published', 'duplicate', 'rejected', 'error'}
    if all(candidate.status in terminal for candidate in item.job.items):
        item.job.status = 'completed'
        item.job.finished_at = datetime.utcnow()
    if item.contribution:
        item.contribution.status = 'rejected'
        item.contribution.reviewed_by = current_user.id
        item.contribution.reviewed_at = datetime.utcnow()
    _cleanup_import_item_temp(item)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Item rejeitado e mantido no histórico de auditoria.'})


@app.route('/api/admin/technical-import/contributions/<int:contribution_id>/analyze', methods=['POST'])
@login_required
@admin_required
def admin_technical_contribution_analyze(contribution_id):
    contribution = FileContribution.query.get_or_404(contribution_id)
    if contribution.import_item_id:
        return jsonify({
            'success': True,
            'message': 'A contribuição já possui preview.',
            'item_id': contribution.import_item_id,
        })
    if contribution.status == 'duplicate':
        return jsonify({'success': False, 'message': 'O arquivo já existe no acervo.'}), 409
    if contribution.status == 'rejected':
        return jsonify({'success': False, 'message': 'A contribuição foi rejeitada.'}), 409
    if not os.path.isfile(contribution.temp_path):
        contribution.status = 'error'
        db.session.commit()
        return jsonify({'success': False, 'message': 'O arquivo temporário da contribuição não está disponível.'}), 410
    try:
        _validate_technical_file_content(contribution.temp_path, contribution.original_filename)
    except (ValueError, OSError) as exc:
        contribution.status = 'error'
        db.session.commit()
        return jsonify({'success': False, 'message': str(exc)}), 400

    automation = get_technical_automation_settings()
    job = ImportJob(
        job_type='contribution',
        source='Contribuição de usuário',
        status='reviewing',
        automation_mode='semi',
        created_by=current_user.id,
        started_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        log_summary='Contribuição encaminhada para revisão humana obrigatória.',
    )
    db.session.add(job)
    db.session.flush()
    metadata = _merge_parsed_metadata(contribution.original_filename, {
        'title': contribution.title,
        'description': contribution.notes,
        'board_code': contribution.board_code,
        'source_provider': 'Contribuição de usuário',
        'distribution_policy': 'manual_review',
        'license_status': 'needs_review',
        'temp_path': contribution.temp_path,
    })
    item = _append_import_item(
        job,
        metadata,
        source_name=contribution.original_filename,
        temp_path=contribution.temp_path,
        file_hash=contribution.sha256,
        raw={'contribution_id': contribution.id, 'user_id': contribution.user_id},
    )
    db.session.flush()
    item.decision_reason = 'Contribuição de usuário: revisão administrativa obrigatória.'
    contribution.import_item_id = item.id
    contribution.status = 'pending_review'
    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Preview gerado para revisão; a contribuição nunca será autopublicada.',
        'item_id': item.id,
        'automation': automation['mode'],
    }), 201


@app.route('/api/admin/technical-import/contributions/<int:contribution_id>/reject', methods=['POST'])
@login_required
@admin_required
def admin_technical_contribution_reject(contribution_id):
    contribution = FileContribution.query.get_or_404(contribution_id)
    if contribution.status == 'published':
        return jsonify({'success': False, 'message': 'Gerencie o post publicado na tela de posts.'}), 409
    contribution.status = 'rejected'
    contribution.reviewed_by = current_user.id
    contribution.reviewed_at = datetime.utcnow()
    if contribution.import_item and contribution.import_item.status != 'published':
        contribution.import_item.status = 'rejected'
        contribution.import_item.reviewed_by = current_user.id
        contribution.import_item.reviewed_at = datetime.utcnow()
        contribution.import_item.decision_reason = 'Contribuição rejeitada pelo administrador.'
        contribution.import_item.job.review_count = max(0, contribution.import_item.job.review_count - 1)
        _cleanup_import_item_temp(contribution.import_item)
    else:
        root = os.path.abspath(app.config['TECHNICAL_IMPORT_TEMP_DIR'])
        path = os.path.abspath(contribution.temp_path)
        try:
            if os.path.commonpath([root, path]) == root and os.path.isfile(path):
                os.remove(path)
        except (OSError, ValueError):
            pass
    db.session.commit()
    return jsonify({'success': True, 'message': 'Contribuição rejeitada.'})


@app.route('/api/admin/technical-import/files/<int:file_id>/health', methods=['POST'])
@login_required
@admin_required
def admin_technical_file_health(file_id):
    technical_file = TechnicalFile.query.get_or_404(file_id)
    if technical_file.storage_provider == 'local':
        root = os.path.abspath(app.config['TECHNICAL_LOCAL_STORAGE_DIR'])
        path = os.path.abspath(os.path.join(root, technical_file.provider_file_id or ''))
        online = os.path.commonpath([root, path]) == root and os.path.isfile(path)
        message = 'online' if online else 'Arquivo local ausente.'
        status_code = 200 if online else None
    else:
        storage = HttpStorageProvider()
        online, message, status_code = storage.health(technical_file.provider_direct_url or technical_file.provider_url or '')
    technical_file.link_status = 'online' if online else 'broken'
    technical_file.last_link_check_at = datetime.utcnow()
    technical_file.last_link_http_status = status_code
    db.session.commit()
    return jsonify({
        'success': True,
        'online': online,
        'status': technical_file.link_status,
        'message': message,
        'http_status': status_code,
    })


def _datasheet_provider_admin_dict(config):
    credential = datasheet_provider_credentials_status(config)
    return {
        'id': config.id,
        'provider_name': config.provider_name,
        'display_name': config.display_name,
        'provider_kind': config.provider_kind,
        'enabled': config.enabled,
        'mode': config.mode,
        'priority': config.priority,
        'api_enabled': config.api_enabled,
        'html_discovery_enabled': config.html_discovery_enabled,
        'auto_publish_threshold': config.auto_publish_threshold,
        'max_items_per_job': config.max_items_per_job,
        'interval_seconds': config.interval_seconds,
        'retention_days': config.retention_days,
        'fallback_enabled': config.fallback_enabled,
        'metadata_persistence_allowed': config.metadata_persistence_allowed,
        'public_republish_allowed': config.public_republish_allowed,
        'pdf_reference_allowed': config.pdf_reference_allowed,
        'pdf_stream_allowed': config.pdf_stream_allowed,
        'pdf_mirror_allowed': config.pdf_mirror_allowed,
        'attribution_required': config.attribution_required,
        'written_permission_confirmed': config.written_permission_confirmed,
        'source_policy_allows_html_discovery': config.source_policy_allows_html_discovery,
        'permission_reference': config.permission_reference or '',
        'permission_notes': config.permission_notes or '',
        'robots_allowed': config.robots_allowed,
        'robots_last_checked_at': config.robots_last_checked_at.isoformat() if config.robots_last_checked_at else None,
        'terms_last_checked_at': config.terms_last_checked_at.isoformat() if config.terms_last_checked_at else None,
        'terms_version_or_date': config.terms_version_or_date or '',
        'requests_per_minute': config.requests_per_minute,
        'requests_per_hour': config.requests_per_hour,
        'requests_per_day': config.requests_per_day,
        'requests_per_month': config.requests_per_month,
        'timeout_seconds': config.timeout_seconds,
        'retry_limit': config.retry_limit,
        'provider_status': config.provider_status,
        'circuit_open_until': config.circuit_open_until.isoformat() if config.circuit_open_until else None,
        'credits_remaining': config.credits_remaining,
        'last_success_at': config.last_success_at.isoformat() if config.last_success_at else None,
        'last_error_at': config.last_error_at.isoformat() if config.last_error_at else None,
        'last_error_message': config.last_error_message or '',
        'credentials_configured': credential['configured'],
        'required_env': credential['required_env'],
        'environment_enabled': _provider_environment_enabled(config),
    }


@app.route('/admin/datasheets')
@login_required
@admin_required
def admin_datasheets():
    """Compatibilidade para favoritos antigos; a tela foi incorporada à central técnica."""
    return redirect(url_for('admin_tools_import', section='datasheets'))


@app.route('/api/admin/datasheets/settings', methods=['PATCH', 'POST'])
@login_required
@admin_required
def admin_datasheet_settings_update():
    payload = request.get_json(silent=True) or {}
    unknown = set(payload) - DATASHEET_SETTING_KEYS
    if unknown:
        return jsonify({'success': False, 'message': f'Configurações não suportadas: {", ".join(sorted(unknown))}'}), 400
    strategy = str(payload.get('datasheet_search_strategy', get_datasheet_settings()['strategy']))
    if strategy not in {'priority_fallback', 'parallel_compare', 'maximum_precision'}:
        return jsonify({'success': False, 'message': 'Estratégia inválida.'}), 400
    values = {
        'datasheet_engine_enabled': (coerce_bool(payload.get('datasheet_engine_enabled'), True), 'bool'),
        'datasheet_auto_publish_enabled': (coerce_bool(payload.get('datasheet_auto_publish_enabled'), False), 'bool'),
        'datasheet_automation_paused': (coerce_bool(payload.get('datasheet_automation_paused'), False), 'bool'),
        'datasheet_search_strategy': (strategy, 'string'),
        'datasheet_max_providers': (max(1, min(10, coerce_int(payload.get('datasheet_max_providers'), 2))), 'int'),
    }
    for key, (value, value_type) in values.items():
        SiteConfig.set_value(key, value, value_type=value_type, is_public=False)
    return jsonify({'success': True, 'settings': get_datasheet_settings()})


@app.route('/api/admin/datasheets/providers/<int:provider_id>', methods=['PATCH', 'POST'])
@login_required
@admin_required
def admin_datasheet_provider_update(provider_id):
    config = DatasheetProviderConfig.query.get_or_404(provider_id)
    payload = request.get_json(silent=True) or request.form.to_dict()
    mode = str(payload.get('mode', config.mode))
    if mode not in {'disabled', 'semi_automatic', 'automatic'}:
        return jsonify({'success': False, 'message': 'Modo do provider inválido.'}), 400
    permission_reference = sanitize_input(str(payload.get('permission_reference', config.permission_reference or '')))[:500] or None
    written_permission = coerce_bool(payload.get('written_permission_confirmed'), config.written_permission_confirmed)
    protected_permissions = any(coerce_bool(payload.get(field), getattr(config, field)) for field in (
        'public_republish_allowed', 'pdf_stream_allowed', 'pdf_mirror_allowed',
    ))
    if protected_permissions and (not written_permission or not permission_reference):
        return jsonify({
            'success': False,
            'message': 'Republicação, streaming e espelhamento exigem autorização escrita e referência preenchida.',
        }), 409
    html_enabled = coerce_bool(payload.get('html_discovery_enabled'), config.html_discovery_enabled)
    robots_allowed = coerce_bool(payload.get('robots_allowed'), config.robots_allowed)
    policy_allows_html = coerce_bool(
        payload.get('source_policy_allows_html_discovery'), config.source_policy_allows_html_discovery
    )
    if html_enabled and (
        not permission_reference or not robots_allowed or not (written_permission or policy_allows_html)
    ):
        return jsonify({
            'success': False,
            'message': 'HTML discovery exige referência da permissão/política e robots.txt permitido.',
        }), 409

    config.mode = mode
    config.enabled = coerce_bool(payload.get('enabled'), config.enabled) and mode != 'disabled'
    config.api_enabled = coerce_bool(payload.get('api_enabled'), config.api_enabled)
    config.html_discovery_enabled = html_enabled
    config.priority = max(1, min(999, coerce_int(payload.get('priority'), config.priority)))
    try:
        threshold_value = parse_float(payload.get('auto_publish_threshold', config.auto_publish_threshold))
        interval_value = parse_float(payload.get('interval_seconds', config.interval_seconds))
        timeout_value = parse_float(payload.get('timeout_seconds', config.timeout_seconds))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Threshold, intervalo ou timeout inválido.'}), 400
    config.auto_publish_threshold = max(0.5, min(1.0, threshold_value))
    config.interval_seconds = max(0.0, min(60.0, interval_value))
    config.timeout_seconds = max(1.0, min(60.0, timeout_value))
    config.max_items_per_job = max(1, min(500, coerce_int(payload.get('max_items_per_job'), config.max_items_per_job)))
    config.retention_days = max(1, min(3650, coerce_int(payload.get('retention_days'), config.retention_days)))
    config.requests_per_minute = max(1, min(10000, coerce_int(payload.get('requests_per_minute'), config.requests_per_minute)))
    config.requests_per_hour = max(1, min(100000, coerce_int(payload.get('requests_per_hour'), config.requests_per_hour)))
    config.requests_per_day = max(1, min(1000000, coerce_int(payload.get('requests_per_day'), config.requests_per_day)))
    config.requests_per_month = max(0, min(10000000, coerce_int(payload.get('requests_per_month'), config.requests_per_month)))
    config.retry_limit = max(0, min(5, coerce_int(payload.get('retry_limit'), config.retry_limit)))
    for field in (
        'fallback_enabled', 'metadata_persistence_allowed', 'public_republish_allowed',
        'pdf_reference_allowed', 'pdf_stream_allowed', 'pdf_mirror_allowed',
        'attribution_required', 'source_policy_allows_html_discovery', 'robots_allowed',
    ):
        if field in payload:
            setattr(config, field, coerce_bool(payload[field], getattr(config, field)))
    config.written_permission_confirmed = written_permission
    config.permission_reference = permission_reference
    config.permission_notes = sanitize_input(str(payload.get('permission_notes', config.permission_notes or '')))[:4000] or None
    config.terms_version_or_date = sanitize_input(str(payload.get('terms_version_or_date', config.terms_version_or_date or '')))[:120] or None
    if payload.get('mark_terms_reviewed'):
        config.terms_last_checked_at = datetime.utcnow()
    if payload.get('mark_robots_checked'):
        config.robots_last_checked_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True, 'provider': _datasheet_provider_admin_dict(config)})


@app.route('/api/admin/datasheets/providers/<int:provider_id>/kill', methods=['POST'])
@login_required
@admin_required
def admin_datasheet_provider_kill(provider_id):
    config = DatasheetProviderConfig.query.get_or_404(provider_id)
    config.enabled = False
    config.mode = 'disabled'
    config.provider_status = 'disabled'
    db.session.commit()
    return jsonify({'success': True, 'message': f'{config.display_name} foi desativado imediatamente.'})


@app.route('/api/admin/datasheets/providers/<int:provider_id>/test', methods=['POST'])
@login_required
@admin_required
@limiter.limit('30 per hour')
def admin_datasheet_provider_test(provider_id):
    from technical_content.datasheets.services.resolver import DatasheetResolver

    config = DatasheetProviderConfig.query.get_or_404(provider_id)
    payload = request.get_json(silent=True) or request.form.to_dict()
    part_number = sanitize_input(str(payload.get('part_number') or ''))[:160]
    if not looks_like_part_number(part_number):
        return jsonify({'success': False, 'message': 'Informe um part number válido para o teste.'}), 400
    configured = build_configured_datasheet_providers([config])
    if not configured:
        return jsonify({'success': False, 'message': 'O provider está desativado pela feature flag do ambiente.'}), 409
    resolution = DatasheetResolver(configured, global_disabled=False).resolve(part_number, strategy='priority_fallback')
    _record_datasheet_resolution(resolution, [config])
    provider = configured[0].provider if configured else None
    if provider and hasattr(provider, 'credit_balance'):
        try:
            config.credits_remaining = provider.credit_balance()
            config.last_credit_check_at = datetime.utcnow()
        except Exception as exc:
            app.logger.info('Consulta de créditos indisponível para %s: %s', config.provider_name, exc)
    db.session.commit()
    return jsonify({
        'success': True,
        'found': resolution.found,
        'confidence': resolution.confidence,
        'conflicts': resolution.conflicts,
        'candidates': [candidate.public_summary(include_values=True) for candidate in resolution.candidates],
        'traces': [trace.__dict__ if hasattr(trace, '__dict__') else {
            'provider': trace.provider, 'status': trace.status, 'result_count': trace.result_count,
            'duration_ms': trace.duration_ms, 'message': trace.message,
        } for trace in resolution.traces],
    })


@app.route('/api/admin/datasheets/benchmark', methods=['POST'])
@login_required
@admin_required
@limiter.limit('5 per hour')
def admin_datasheet_benchmark():
    from technical_content.datasheets.services.resolver import DatasheetResolver

    payload = request.get_json(silent=True) or {}
    raw_values = payload.get('part_numbers') or ''
    values = re.split(r'[,;\n]+', raw_values) if isinstance(raw_values, str) else list(raw_values or [])
    part_numbers = [sanitize_input(str(value))[:160] for value in values if looks_like_part_number(value)][:20]
    if not part_numbers:
        return jsonify({'success': False, 'message': 'Informe ao menos um part number válido.'}), 400
    ensure_default_datasheet_providers()
    configs = DatasheetProviderConfig.query.order_by(DatasheetProviderConfig.priority.asc()).all()
    configured = build_configured_datasheet_providers(configs)
    rows = []
    totals = {config.provider_name: {'queries': 0, 'hits': 0, 'exact': 0, 'duration_ms': 0} for config in configs}
    for part_number in part_numbers:
        resolution = DatasheetResolver(configured, global_disabled=False).resolve(
            part_number, strategy='parallel_compare', max_providers=10,
        )
        _record_datasheet_resolution(resolution, configs)
        row = {'part_number': part_number, 'selected': resolution.selected.provider if resolution.selected else None, 'providers': {}}
        for trace in resolution.traces:
            candidate = next((item for item in resolution.candidates if item.provider == trace.provider), None)
            row['providers'][trace.provider] = {
                'status': trace.status, 'results': trace.result_count, 'duration_ms': trace.duration_ms,
                'exact': bool(candidate and candidate.exact_match),
                'confidence': round((candidate.confidence if candidate else 0) * 100, 1),
            }
            if trace.provider in totals:
                totals[trace.provider]['queries'] += 1
                totals[trace.provider]['hits'] += int(trace.result_count > 0)
                totals[trace.provider]['exact'] += int(bool(candidate and candidate.exact_match))
                totals[trace.provider]['duration_ms'] += trace.duration_ms
        rows.append(row)
    db.session.commit()
    summary = {}
    for provider, values in totals.items():
        queries = values['queries']
        summary[provider] = {
            **values,
            'coverage': round((values['hits'] / queries) * 100, 1) if queries else 0,
            'exact_rate': round((values['exact'] / queries) * 100, 1) if queries else 0,
            'average_ms': round(values['duration_ms'] / queries) if queries else 0,
        }
    return jsonify({'success': True, 'rows': rows, 'summary': summary})


@app.route('/api/admin/datasheets/queue', methods=['POST'])
@login_required
@admin_required
def admin_datasheet_queue_create():
    strategy = request.form.get('strategy') or (request.get_json(silent=True) or {}).get('strategy')
    entries = []
    upload = request.files.get('csv_file')
    if upload and upload.filename:
        try:
            text_value = upload.stream.read(1_000_000).decode('utf-8-sig')
            for row in csv.DictReader(text_value.splitlines()):
                entries.append((row.get('part_number'), row.get('manufacturer')))
        except (UnicodeDecodeError, csv.Error) as exc:
            return jsonify({'success': False, 'message': f'CSV inválido: {exc}'}), 400
    payload = request.get_json(silent=True) or request.form.to_dict()
    raw_parts = payload.get('part_numbers') or payload.get('part_number') or ''
    if isinstance(raw_parts, str):
        for value in re.split(r'[,;\n]+', raw_parts):
            if value.strip():
                entries.append((value.strip(), payload.get('manufacturer')))
    created = 0
    existing = 0
    for part_number, manufacturer in entries[:500]:
        if not looks_like_part_number(part_number):
            continue
        _, was_created = enqueue_datasheet(
            part_number,
            manufacturer,
            priority=coerce_int(payload.get('priority'), 0),
            strategy=strategy,
            requested_by=current_user.id,
        )
        created += int(was_created)
        existing += int(not was_created)
    if not created and not existing:
        return jsonify({'success': False, 'message': 'Nenhum part number válido foi informado.'}), 400
    return jsonify({'success': True, 'created': created, 'existing': existing, 'message': f'{created} item(ns) adicionado(s) à fila.'}), 201


@app.route('/api/admin/datasheets/queue/process', methods=['POST'])
@login_required
@admin_required
@limiter.limit('20 per hour')
def admin_datasheet_queue_process_batch():
    limit = max(1, min(100, coerce_int((request.get_json(silent=True) or {}).get('limit'), 10)))
    active_configs = DatasheetProviderConfig.query.filter(
        DatasheetProviderConfig.enabled.is_(True), DatasheetProviderConfig.mode != 'disabled'
    ).all()
    configured = build_configured_datasheet_providers(active_configs)
    if configured:
        limit = min(limit, min(max(1, item.config.max_items_per_job) for item in configured))
    items = DatasheetImportQueue.query.filter_by(status='queued').order_by(
        DatasheetImportQueue.priority.desc(), DatasheetImportQueue.created_at.asc()
    ).limit(limit).all()
    result = {'processed': 0, 'review': 0, 'published': 0, 'failed': 0}
    for queue_item in items:
        process_datasheet_queue_item(
            queue_item, configured_providers=configured, provider_configs=active_configs,
        )
        result['processed'] += 1
        result['published'] += int(queue_item.status == 'published')
        result['review'] += int(queue_item.status == 'needs_review')
        result['failed'] += int(queue_item.status in {'failed', 'blocked_by_policy'})
    return jsonify({'success': True, **result})


@app.route('/api/admin/datasheets/queue/<int:item_id>/process', methods=['POST'])
@login_required
@admin_required
@limiter.limit('30 per hour')
def admin_datasheet_queue_process_one(item_id):
    queue_item = DatasheetImportQueue.query.get_or_404(item_id)
    if queue_item.status == 'published':
        return jsonify({'success': False, 'message': 'O componente já foi publicado.'}), 409
    process_datasheet_queue_item(queue_item)
    return jsonify({'success': True, 'status': queue_item.status, 'confidence': queue_item.best_confidence})


@app.route('/api/admin/datasheets/queue/<int:item_id>', methods=['PATCH'])
@login_required
@admin_required
def admin_datasheet_queue_update(item_id):
    queue_item = DatasheetImportQueue.query.get_or_404(item_id)
    if queue_item.status == 'published':
        return jsonify({'success': False, 'message': 'O componente já foi publicado.'}), 409
    payload = request.get_json(silent=True) or {}
    result = queue_item.result()
    selected = result.get('selected') if isinstance(result.get('selected'), dict) else {}
    for field in ('part_number', 'manufacturer', 'category', 'subcategory', 'package', 'lifecycle_status'):
        if field in payload:
            selected[field] = sanitize_input(str(payload[field] or ''))[:300]
    result['selected'] = selected
    queue_item.result_json = json.dumps(result, ensure_ascii=False)
    queue_item.status = 'needs_review'
    queue_item.admin_decision = 'edited'
    queue_item.reviewed_by = current_user.id
    db.session.commit()
    return jsonify({'success': True, 'message': 'Preview atualizado.'})


@app.route('/api/admin/datasheets/queue/<int:item_id>/<string:action>', methods=['POST'])
@login_required
@admin_required
def admin_datasheet_queue_action(item_id, action):
    queue_item = DatasheetImportQueue.query.get_or_404(item_id)
    payload = request.get_json(silent=True) or {}
    if action == 'publish':
        try:
            component = materialize_datasheet_component(queue_item, reviewer_id=current_user.id, publish=True)
        except ValueError as exc:
            return jsonify({'success': False, 'message': str(exc)}), 409
        return jsonify({
            'success': True,
            'component_id': component.id,
            'post_id': component.post_id,
            'url': url_for('post', post_id=component.post_id) if component.post_id else url_for('datasheet_component_detail', slug=component.slug),
        })
    if action == 'draft':
        try:
            component = materialize_datasheet_component(queue_item, reviewer_id=current_user.id, publish=False)
        except ValueError as exc:
            return jsonify({'success': False, 'message': str(exc)}), 409
        return jsonify({'success': True, 'component_id': component.id, 'message': 'Componente salvo como rascunho.'})
    if action == 'ignore':
        queue_item.status = 'ignored'
        queue_item.admin_decision = 'ignored'
    elif action == 'duplicate':
        component_id = coerce_int(payload.get('component_id'), 0)
        component = db.session.get(ElectronicComponent, component_id) if component_id else find_component_by_identity(
            queue_item.manufacturer_hint, queue_item.part_number
        )
        if not component:
            return jsonify({'success': False, 'message': 'Informe um componente existente para marcar a duplicata.'}), 400
        queue_item.status = 'duplicate'
        queue_item.component_id = component.id
        queue_item.admin_decision = 'marked_duplicate'
    elif action == 'reprocess':
        queue_item.status = 'queued'
        queue_item.error_message = None
        queue_item.started_at = None
        queue_item.finished_at = None
        queue_item.admin_decision = 'reprocess'
    else:
        return jsonify({'success': False, 'message': 'Ação não suportada.'}), 400
    queue_item.reviewed_by = current_user.id
    db.session.commit()
    return jsonify({'success': True, 'status': queue_item.status})

@app.route("/admin/settings")
@login_required
@admin_required
def admin_settings():
    """
    Página de configurações
    """
    # Obter estatísticas para a sidebar
    sidebar_stats = get_admin_sidebar_stats()

    # Obter configurações atuais do site
    site_configs = SiteConfig.get_config()

    return render_template('admin/settings.html',
                         title="Configurações",
                         site_configs=site_configs,
                         plan_product_ids=STRIPE_PLAN_PRODUCT_IDS,
                         **sidebar_stats)

@app.route("/admin/save_settings", methods=['POST'])
@login_required
@admin_required
def admin_save_settings():
    """
    Salvar configurações do site
    """
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'JSON inválido'}), 400

        if not data:
            return jsonify({'success': False, 'message': 'Dados inválidos'}), 400

        unsupported_keys = set(data) - set(LIVE_SITE_SETTING_KEYS)
        if unsupported_keys:
            return jsonify({'success': False, 'message': 'Uma ou mais configurações não são permitidas.'}), 400

        for price_key in ('plan_price_premium', 'plan_price_vip'):
            if price_key not in data:
                continue
            raw_price = data[price_key].get('value') if isinstance(data[price_key], dict) else None
            try:
                normalized_price = Decimal(str(raw_price).replace(',', '.'))
            except (InvalidOperation, TypeError, ValueError):
                return jsonify({'success': False, 'message': 'Informe preços válidos para os planos.'}), 400
            if normalized_price <= 0 or normalized_price > Decimal('9999.99'):
                return jsonify({'success': False, 'message': 'O preço do plano deve ficar entre R$ 0,01 e R$ 9.999,99.'}), 400

        for name_key in ('plan_name_free', 'plan_name_premium', 'plan_name_vip'):
            if name_key not in data:
                continue
            name_config = data[name_key]
            raw_name = name_config.get('value') if isinstance(name_config, dict) else ''
            normalized_name = ' '.join(str(raw_name or '').split()).strip()
            if len(normalized_name) < 2 or len(normalized_name) > 40:
                return jsonify({'success': False, 'message': 'O nome de cada plano deve ter entre 2 e 40 caracteres.'}), 400
            name_config['value'] = normalized_name
            name_config['type'] = 'string'

        # Salvar cada configuração
        for key, config in data.items():
            if not isinstance(config, dict):
                return jsonify({'success': False, 'message': 'Dados inválidos'}), 400
            value = config.get('value')
            value_type = config.get('type', 'string')

            SiteConfig.set_value(
                key=key,
                value=value,
                value_type=value_type,
                is_public=True
            )

        if any(key.startswith('plan_price_') for key in data):
            _stripe_plan_price_cache.clear()

        # Log da atividade
        try:
            log_admin_activity(
                user_id=current_user.id,
                action="settings_updated",
                description=f"Configurações do site atualizadas",
                metadata={'updated_keys': list(data.keys())}
            )
        except Exception as e:
            app.logger.error('Erro ao registrar atividade: %s', e)

        return jsonify({
            'success': True,
            'message': 'Configurações salvas com sucesso!',
            'settings': get_live_site_settings(),
        })

    except Exception:
        app.logger.exception('Erro ao salvar configuracoes')
        return jsonify({'success': False, 'message': 'Erro interno do servidor'})

@app.route("/admin/profile")
@login_required
@editor_required
def admin_profile():
    """
    Página de perfil do usuário
    """
    # Obter estatísticas para a sidebar
    sidebar_stats = get_admin_sidebar_stats()
    try:
        profile_preferences = json.loads(current_user.preferences or '{}')
    except (TypeError, ValueError, json.JSONDecodeError):
        profile_preferences = {}

    return render_template('admin/profile.html',
                         title="Meu Perfil",
                         profile_preferences=profile_preferences,
                         **sidebar_stats)

@app.route('/profile')
@app.route('/profile/<int:user_id>')
@login_required
def profile(user_id=None):
    """Página de perfil do usuário"""
    if user_id:
        user = User.query.get_or_404(user_id)
    else:
        user = current_user

    # Estatísticas do usuário
    user_posts = Post.query.filter_by(author_id=user.id, is_active=True).count() if hasattr(user, 'id') else 0
    user_comments = Comment.query.filter_by(user_id=user.id).count() if hasattr(user, 'id') else 0
    category_count = Category.query.filter_by(is_active=True).count()  # noqa: F841

    # Buscar favoritos do usuário
    favorite_posts = []
    if hasattr(user, 'id') and current_user.is_authenticated and current_user.id == user.id:
        favorites = Favorite.query.filter_by(user_id=user.id).order_by(Favorite.position.asc(), Favorite.date_added.desc()).all()
        favorite_posts = [fav.post for fav in favorites if fav.post and fav.post.is_active]

    # Buscar histórico de downloads baseado no plano
    download_history = []
    if hasattr(user, 'id') and current_user.is_authenticated and current_user.id == user.id:
        has_access, limit = check_download_history_access(user)
        if has_access:
            # Buscar apenas o download mais recente de cada post (evita duplicatas)
            from sqlalchemy import func

            # Subquery para pegar o ID do download mais recente de cada post
            subquery = db.session.query(
                Download.post_id,
                func.max(Download.timestamp).label('max_timestamp')
            ).filter(
                Download.user_id == user.id
            ).group_by(Download.post_id).subquery()

            # Query principal juntando com a subquery
            query = db.session.query(Download).join(
                subquery,
                db.and_(
                    Download.post_id == subquery.c.post_id,
                    Download.timestamp == subquery.c.max_timestamp
                )
            ).filter(Download.user_id == user.id).order_by(Download.timestamp.desc())

            if limit:
                # Premium: últimos 5 downloads únicos
                downloads = query.limit(limit).all()
            else:
                # VIP: todos os downloads únicos
                downloads = query.all()

            # Carregar posts e categorias para cada download
            brasilia_tz = pytz.timezone('America/Sao_Paulo')
            for download in downloads:
                if download.post:
                    # Carregar a categoria se não estiver carregada
                    if download.post.category_id and not hasattr(download.post, '_category_cache'):
                        # type: ignore - atributo dinâmico para cache de categoria
                        setattr(download.post, '_category_cache', Category.query.get(download.post.category_id))

                    # Converter timestamp para timezone de Brasília
                    if download.timestamp:
                        utc_time = pytz.utc.localize(download.timestamp)
                        # type: ignore - atributo dinâmico para timestamp em Brasília
                        setattr(download, '_brasilia_time', utc_time.astimezone(brasilia_tz))

            download_history = downloads

    # Calcular dias como membro
    days_as_member = 0
    if user.date_joined:
        delta = datetime.utcnow() - user.date_joined
        days_as_member = delta.days

    return render_template('profile.html',
                         user=user,
                         title=f'Perfil - {user.get_full_name() or user.username}',
                         user_posts=user_posts,
                         user_comments=user_comments,
                         category_count=category_count,
                         days_as_member=days_as_member,
                         favorite_posts=favorite_posts,
                         download_history=download_history)

# Rota para obter favoritos do usuário (API JSON)
@app.route('/api/user-favorites', methods=['GET'])
@login_required
def get_user_favorites_api():
    """Retorna os favoritos do usuário em JSON para atualização em tempo real"""
    try:
        user = current_user

        # Buscar favoritos do usuário
        favorites = Favorite.query.filter_by(user_id=user.id).order_by(Favorite.position.asc(), Favorite.date_added.desc()).all()

        posts_data = []
        for favorite in favorites[:6]:  # Limitar a 6 posts para a página de perfil
            post = Post.query.get(favorite.post_id)
            if post and post.is_active:
                posts_data.append({
                    'id': post.id,
                    'title': post.title,
                    'slug': post.slug,
                    'content': post.content,
                    'image_url': post.image_url,
                    'category_str': post.category_str or 'Geral',
                    'category_slug': Category.query.get(post.category_id).slug if post.category_id else None,
                    'download_link': url_for('download_post', post_id=post.id) if post.download_link else '',
                    'download_files': get_public_download_files(post),
                    'date_posted': post.date_posted.strftime('%d/%m/%Y') if post.date_posted else '',
                    'views': post.views or 0,
                    'downloads': post.downloads or 0,
                    'featured': post.featured or False
                })

        return jsonify({
            'success': True,
            'posts': posts_data,
            'total': len(favorites)
        })
    except Exception:
        app.logger.exception('Erro ao buscar favoritos')
        return jsonify({'success': False, 'message': 'Não foi possível buscar os favoritos.'}), 500

@app.route('/api/reorder-favorites', methods=['POST'])
@login_required
def reorder_favorites_api():
    """Reordena os favoritos do usuário"""
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'JSON inválido'}), 400
        if not data:
            return jsonify({'success': False, 'message': 'Dados inválidos'}), 400
        order = data.get('order', [])
        if not order or not isinstance(order, list):
            return jsonify({'success': False, 'message': 'Ordem inválida'}), 400

        for idx, post_id in enumerate(order):
            post_id = int(post_id)
            fav = Favorite.query.filter_by(user_id=current_user.id, post_id=post_id).first()
            if fav:
                fav.position = idx

        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# Rota para obter histórico de downloads (API JSON)
@app.route('/api/download-history', methods=['GET'])
@login_required
def get_download_history_api():
    """Retorna o histórico de downloads em JSON para atualização em tempo real"""
    try:
        user = current_user
        has_access, limit = check_download_history_access(user)

        if not has_access:
            return jsonify({'success': False, 'message': 'Acesso negado'}), 403

        from sqlalchemy import func

        # Subquery para pegar o ID do download mais recente de cada post
        subquery = db.session.query(
            Download.post_id,
            func.max(Download.timestamp).label('max_timestamp')
        ).filter(
            Download.user_id == user.id
        ).group_by(Download.post_id).subquery()

        # Query principal
        query = db.session.query(Download).join(
            subquery,
            db.and_(
                Download.post_id == subquery.c.post_id,
                Download.timestamp == subquery.c.max_timestamp
            )
        ).filter(Download.user_id == user.id).order_by(Download.timestamp.desc())

        if limit:
            downloads = query.limit(limit).all()
        else:
            downloads = query.all()

        # Converter para JSON
        brasilia_tz = pytz.timezone('America/Sao_Paulo')
        downloads_data = []

        for download in downloads:
            if download.post:
                category = Category.query.get(download.post.category_id) if download.post.category_id else None

                # Converter timestamp
                utc_time = pytz.utc.localize(download.timestamp)
                brasilia_time = utc_time.astimezone(brasilia_tz)

                downloads_data.append({
                    'id': download.id,
                    'post_id': download.post.id,
                    'post_title': download.post.title,
                    'post_slug': download.post.slug,
                    'post_image': download.post.image_url,
                    'download_link': url_for('download_post', post_id=download.post.id) if download.post.download_link else '',
                    'download_files': get_public_download_files(download.post),
                    'category_name': category.name if category else None,
                    'category_slug': category.slug if category else None,
                    'timestamp': brasilia_time.strftime('%d/%m/%Y às %H:%M')
                })

        return jsonify({'success': True, 'downloads': downloads_data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Rota para limpar histórico de downloads
@app.route('/clear-download-history', methods=['POST'])
@login_required
def clear_download_history():
    """Limpa o histórico de downloads do usuário"""
    try:
        has_access, _limit = check_download_history_access(current_user)
        if not has_access:
            return jsonify({'success': False, 'message': 'Seu plano não inclui histórico de downloads.'}), 403

        # Deletar todos os downloads do usuário
        Download.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Histórico limpo com sucesso!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao limpar histórico: {str(e)}'}), 500

# Rota para remover um download individual
@app.route('/api/remove-download/<int:download_id>', methods=['DELETE'])
@login_required
def remove_download(download_id):
    """Remove um download específico do histórico"""
    try:
        has_access, _limit = check_download_history_access(current_user)
        if not has_access:
            return jsonify({'success': False, 'message': 'Seu plano não inclui histórico de downloads.'}), 403

        download = Download.query.filter_by(id=download_id, user_id=current_user.id).first()
        if not download:
            return jsonify({'success': False, 'message': 'Download não encontrado'}), 404

        db.session.delete(download)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Download removido do histórico!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao remover download: {str(e)}'}), 500

# Rota para limpar todos os favoritos
@app.route('/api/clear-all-favorites', methods=['POST'])
@login_required
def clear_all_favorites():
    """Remove todos os favoritos do usuário"""
    try:
        # Deletar todos os favoritos do usuário
        Favorite.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Todos os favoritos foram removidos!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao limpar favoritos: {str(e)}'}), 500

# Rota para verificar limite de downloads
@app.route('/check-download-limit', methods=['GET'])
@login_required
def check_download_limit_route():
    """Verifica se o usuário pode fazer download"""
    can_download, remaining, limit, reset_time, period = check_user_download_limit(current_user)

    return jsonify({
        'can_download': can_download,
        'remaining': int(remaining) if remaining != float('inf') else 'unlimited',
        'limit': int(limit) if limit != float('inf') else 'unlimited',
        'reset_time': reset_time.isoformat() if reset_time else None,
        'plan': current_user.plan,
        'period': period  # 'daily', 'weekly' ou 'unlimited'
    })

# Rota de logout
@app.route('/logout')
@login_required
def logout():
    """Desconecta o usuário atual"""
    # Decrementar sessões ativas
    if current_user.is_authenticated:
        current_user.active_sessions = max(0, (current_user.active_sessions or 0) - 1)
        db.session.commit()

    logout_user()
    flash('Você foi desconectado com sucesso!', 'info')
    return redirect(url_for('home'))

# Função auxiliar para verificar se o arquivo tem uma extensão permitida
def allowed_file(filename):
    """Verifica se o arquivo tem uma extensão permitida"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_image_file(file):
    """
    Valida um arquivo de imagem de forma rigorosa

    Args:
        file: Objeto de arquivo do Flask

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if not file or not file.filename:
        return False, 'Nenhum arquivo foi fornecido.'

    # Verificar extensão
    if not allowed_file(file.filename):
        return False, f'Tipo de arquivo não permitido. Use apenas: {", ".join(ALLOWED_EXTENSIONS)}'

    # Verificar tamanho (já configurado no MAX_CONTENT_LENGTH, mas validar aqui também)
    file.seek(0, 2)  # Ir para o final do arquivo
    size = file.tell()
    file.seek(0)  # Voltar ao início

    max_size = 5 * 1024 * 1024  # 5MB
    if size > max_size:
        return False, f'O arquivo é muito grande. Tamanho máximo: 5MB'

    if size == 0:
        return False, 'O arquivo está vazio.'

    # Validar que é realmente uma imagem usando Pillow
    try:
        img = Image.open(file)
        img.verify()  # Verifica se é uma imagem válida
        file.seek(0)  # Resetar o ponteiro do arquivo após verificação

        # Verificar formato
        if img.format.lower() not in ['jpeg', 'jpg', 'png', 'gif', 'webp']:
            return False, 'Formato de imagem inválido.'

        # Verificar dimensões razoáveis
        width, height = img.size
        if width > 5000 or height > 5000:
            return False, 'As dimensões da imagem são muito grandes (máximo: 5000x5000).'

        if width < 10 or height < 10:
            return False, 'As dimensões da imagem são muito pequenas (mínimo: 10x10).'

    except Exception as e:
        return False, f'Arquivo não é uma imagem válida: {str(e)}'

    return True, None

def upload_to_cloudinary(file, folder='profiles'):
    """
    Faz upload de imagem para o Cloudinary

    Args:
        file: Objeto de arquivo do Flask
        folder: Pasta no Cloudinary (profiles, posts, etc.)

    Returns:
        tuple: (success: bool, url_or_error: str)
    """
    try:
        # Processar a imagem sem duplicar todos os pixels em memória.
        img = Image.open(file.stream)
        img = ImageOps.exif_transpose(img)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        max_size = (800, 800) if folder == 'profiles' else (1600, 1600)
        img.thumbnail(max_size, Resampling.LANCZOS)

        # Salvar em buffer temporário
        from io import BytesIO
        buffer = BytesIO()
        img.save(buffer, format='JPEG', optimize=True, quality=82, progressive=True)
        buffer.seek(0)

        # Upload para Cloudinary
        result = cloudinary.uploader.upload(
            buffer,
            folder=f'mundodainformatica/{folder}',
            resource_type='image',
            format='jpg',
            transformation=[
                {'width': max_size[0], 'height': max_size[1], 'crop': 'limit'},
                {'quality': 'auto:good'},
                {'fetch_format': 'auto'}
            ]
        )

        return True, result['secure_url']

    except Exception as e:
        app.logger.error('Erro ao fazer upload para Cloudinary: %s', e)
        return False, str(e)

def delete_from_cloudinary(image_url):
    """
    Deleta imagem do Cloudinary

    Args:
        image_url: URL da imagem no Cloudinary
    """
    try:
        # Extrair public_id da URL
        # URL formato: https://res.cloudinary.com/cloud_name/image/upload/v123/folder/public_id.jpg
        if 'cloudinary.com' in image_url:
            parts = image_url.split('/')
            # Pegar folder/public_id (últimas 2 partes antes da extensão)
            public_id_with_ext = '/'.join(parts[-2:])
            public_id = public_id_with_ext.rsplit('.', 1)[0]

            cloudinary.uploader.destroy(public_id)
            app.logger.info('Imagem removida do Cloudinary: %s', public_id)
    except Exception as e:
        app.logger.error('Erro ao remover imagem do Cloudinary: %s', e)

# Rotas para atualizar a imagem de perfil de usuários regulares
@app.route('/update-profile-image', methods=['POST'])
@login_required
@limiter.limit("10 per hour")  # Limitar uploads de imagem
def update_profile_image():
    """Atualiza a imagem de perfil do usuário logado"""
    if 'profile_image' not in request.files:
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(url_for('profile'))

    file = request.files['profile_image']

    if file.filename == '':
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(url_for('profile'))

    # Validação rigorosa da imagem
    is_valid, error_message = validate_image_file(file)
    if not is_valid:
        flash(error_message or 'Arquivo de imagem inválido', 'error')
        return redirect(url_for('profile'))

    if file and file.filename and allowed_file(file.filename):
        try:
            # Deletar imagem antiga do Cloudinary se existir
            if current_user.profile_image and 'cloudinary.com' in current_user.profile_image:
                delete_from_cloudinary(current_user.profile_image)
            elif current_user.profile_image and current_user.profile_image != 'default.jpg':
                # Deletar imagem antiga local (fallback)
                delete_old_image(current_user.profile_image)

            # Upload para Cloudinary
            success, result = upload_to_cloudinary(file, folder='profiles')

            if success:
                # Salvar URL do Cloudinary no banco
                current_user.profile_image = result
                db.session.commit()
                flash('Imagem de perfil atualizada com sucesso!', 'success')
            else:
                flash(f'Erro ao fazer upload da imagem: {result}', 'error')

        except Exception:
            app.logger.exception('Erro ao processar imagem de perfil')
            flash('Erro ao processar a imagem. Tente novamente.', 'error')
    else:
        flash('Formato de arquivo não permitido. Use JPG, JPEG, PNG ou GIF.', 'error')

    return redirect(url_for('profile'))

@app.route('/remove-profile-image', methods=['POST'])
@login_required
def remove_profile_image():
    """Remove a imagem de perfil do usuário logado"""
    try:
        # Deletar do Cloudinary ou filesystem
        if current_user.profile_image:
            if 'cloudinary.com' in current_user.profile_image:
                delete_from_cloudinary(current_user.profile_image)
            else:
                delete_old_image(current_user.profile_image)

        # Limpa a imagem de perfil do usuário atual
        current_user.profile_image = ""
        db.session.commit()

        # Se for requisição AJAX, retorna JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': 'Imagem de perfil removida com sucesso!'
            })

        flash('Imagem de perfil removida com sucesso!', 'success')
        return redirect(url_for('profile'))
    except Exception as e:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': f'Erro ao remover imagem: {str(e)}'
            }), 500
        flash(f'Erro ao remover imagem: {str(e)}', 'error')
        return redirect(url_for('profile'))

# Rota para atualizar a imagem de perfil do admin
@app.route('/admin/update-profile-image', methods=['POST'])
@login_required
@editor_required
def admin_update_profile_image():
    if 'profile_image' not in request.files:
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(url_for('admin_profile'))

    file = request.files['profile_image']

    if file.filename == '':
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(url_for('admin_profile'))

    if file and file.filename and allowed_file(file.filename):
        # Crie o diretório de upload se não existir
        upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
        os.makedirs(upload_path, exist_ok=True)

        # Crie um nome de arquivo seguro e único
        filename = secure_filename(file.filename)
        # Adicione um timestamp ao nome do arquivo para evitar cache do navegador
        base, ext = os.path.splitext(filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"{base}_{timestamp}{ext}"

        filepath = os.path.join(upload_path, filename)

        try:
            # Deletar imagem antiga se existir
            if current_user.profile_image:
                delete_old_image(current_user.profile_image)

            # Redimensione e salve a imagem para otimização
            # Usar o stream do FileStorage para evitar warning do Pylance
            img = Image.open(file.stream)
            img = img.convert('RGB')  # Converte para RGB (remove alfa se existir)
            img.thumbnail((300, 300))  # Redimensiona mantendo proporção
            img.save(filepath, optimize=True, quality=85)

            # Atualiza o perfil do usuário com apenas o nome do arquivo
            current_user.profile_image = filename
            db.session.commit()

            flash('Imagem de perfil atualizada com sucesso!', 'success')
        except Exception:
            app.logger.exception('Erro ao processar imagem administrativa')
            flash('Erro ao processar a imagem. Tente novamente.', 'error')
    else:
        flash('Formato de arquivo não permitido. Use JPG, JPEG, PNG ou GIF.', 'error')

    return redirect(url_for('admin_profile'))

@app.route('/admin/remove-profile-image', methods=['POST'])
@login_required
@admin_required
def admin_remove_profile_image():
    # Deletar a imagem física do filesystem
    if current_user.profile_image:
        delete_old_image(current_user.profile_image)

    # Limpa a imagem de perfil do usuário atual
    current_user.profile_image = ""
    db.session.commit()

    flash('Imagem de perfil removida com sucesso!', 'success')
    return redirect(url_for('admin_profile'))


@app.route('/admin/users/<int:user_id>/update-photo', methods=['POST'])
@login_required
@admin_required
def admin_update_user_photo(user_id):
    """Admin altera a foto de perfil de outro usuário"""
    user = User.query.get_or_404(user_id)
    if 'profile_image' not in request.files:
        return jsonify({'success': False, 'message': 'Nenhum arquivo enviado'}), 400
    file = request.files['profile_image']
    if not file.filename or not allowed_file(file.filename):
        return jsonify({'success': False, 'message': 'Formato inválido. Use JPG, PNG ou GIF'}), 400

    upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    os.makedirs(upload_path, exist_ok=True)
    filename = secure_filename(file.filename)
    base, ext = os.path.splitext(filename)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    filename = f"{base}_{timestamp}{ext}"
    filepath = os.path.join(upload_path, filename)
    try:
        if user.profile_image:
            delete_old_image(user.profile_image)
        img = Image.open(file.stream)
        img = img.convert('RGB')
        img.thumbnail((300, 300))
        img.save(filepath, optimize=True, quality=85)
        user.profile_image = filename
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Foto atualizada com sucesso',
            'photo_url': get_image_url_for_response(filename, folder='profiles', default='default_profile.jpg')
        })
    except Exception as e:
        app.logger.error(f'Erro ao processar imagem do usuário {user_id}: {e}')
        return jsonify({'success': False, 'message': 'Erro ao processar a imagem'}), 500


@app.route('/admin/users/<int:user_id>/remove-photo', methods=['POST'])
@login_required
@admin_required
def admin_remove_user_photo(user_id):
    """Admin remove a foto de perfil de outro usuário"""
    user = User.query.get_or_404(user_id)
    if user.profile_image:
        delete_old_image(user.profile_image)
    user.profile_image = ''
    db.session.commit()
    return jsonify({'success': True, 'message': 'Foto removida com sucesso'})

# Adicione estas rotas se ainda não existirem

@app.route('/admin/update-profile', methods=['POST'])
@login_required
def admin_update_profile():
    """Atualiza somente o perfil da conta autenticada, com validação no servidor."""
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return_endpoint = 'admin_profile' if request.form.get('profile_context') == 'admin' else 'profile'

    def validation_error(message, status=400):
        if is_ajax:
            return jsonify({'success': False, 'message': message}), status
        flash(message, 'error')
        return redirect(url_for(return_endpoint))

    name = sanitize_input(request.form.get('name', ''))[:100]
    username = sanitize_input(request.form.get('username', '')).strip()[:50]
    email = sanitize_input(request.form.get('email', '')).strip().lower()[:120]
    if not name:
        return validation_error('Informe seu nome.')
    if not re.fullmatch(r'[A-Za-z0-9_]{3,20}', username):
        return validation_error('O usuário deve ter de 3 a 20 caracteres: letras, números ou _.')
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        return validation_error('Informe um email válido.')
    if User.query.filter(db.func.lower(User.username) == username.lower(), User.id != current_user.id).first():
        return validation_error('Este nome de usuário já está em uso.', 409)
    if User.query.filter(db.func.lower(User.email) == email, User.id != current_user.id).first():
        return validation_error('Este email já está em uso.', 409)

    try:
        current_user.name = name
        current_user.username = username
        current_user.email = email
        if 'bio' in request.form:
            current_user.bio = sanitize_input(request.form.get('bio', ''))[:300]
        if 'phone' in request.form:
            current_user.phone = sanitize_input(request.form.get('phone', ''))[:20]
        if 'location' in request.form:
            current_user.location = sanitize_input(request.form.get('location', ''))[:100]

        for field_name in ('website', 'facebook', 'twitter', 'instagram', 'linkedin', 'github'):
            if field_name in request.form:
                setattr(current_user, field_name, normalize_optional_external_url(request.form.get(field_name)))

        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return validation_error(str(exc))
    except IntegrityError:
        db.session.rollback()
        return validation_error('Usuário ou email já cadastrado.', 409)
    except Exception:
        db.session.rollback()
        app.logger.exception('Erro ao atualizar perfil')
        return validation_error('Não foi possível atualizar o perfil.', 500)

    # Se for uma requisição AJAX, retorna JSON com todos os dados
    if is_ajax:
        return jsonify({
                'success': True,
                'message': 'Perfil atualizado com sucesso!',
                'user': {
                    'name': current_user.name,
                    'username': current_user.username,
                    'email': current_user.email,
                    'bio': current_user.bio,
                    'phone': current_user.phone,
                    'location': current_user.location,
                    'website': current_user.website,
                    'facebook_url': current_user.facebook,
                    'twitter_url': current_user.twitter,
                    'instagram_url': current_user.instagram,
                    'linkedin_url': current_user.linkedin,
                    'github_url': current_user.github,
                    'profile_image': current_user.profile_image
                }
        })

    flash('Perfil atualizado com sucesso!', 'success')

    return redirect(url_for(return_endpoint))

@app.route('/update-password', methods=['POST'])
@login_required
def update_password():
    """Atualiza a senha do usuário"""
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    # Verificar se os campos estão preenchidos
    if not current_password or not new_password or not confirm_password:
        flash('Todos os campos são obrigatórios', 'error')
        return redirect(url_for('profile'))

    # Verifique se a senha atual está correta
    if not current_user.verify_password(current_password):
        flash('Senha atual incorreta', 'error')
        return redirect(url_for('profile'))

    # Verifique se a nova senha corresponde à confirmação
    if new_password != confirm_password:
        flash('As senhas não correspondem', 'error')
        return redirect(url_for('profile'))

    # Validar força da senha
    is_valid, password_error = validate_password_strength(new_password)
    if not is_valid:
        flash(password_error or 'Senha inválida.', 'error')
        return redirect(url_for('profile'))

    # Atualize a senha
    current_user.set_password(new_password)
    db.session.commit()

    flash('Senha atualizada com sucesso!', 'success')
    return redirect(url_for('profile'))

# Rotas de Favoritos

def check_favorite_limit(user):
    """Verifica se o usuário pode adicionar favoritos baseado no plano"""
    limit = get_plan_entitlements(user)['favorites_limit']
    if limit is None:
        return True, "Favoritos ilimitados."

    count = Favorite.query.filter_by(user_id=user.id).count()
    if count >= limit:
        return False, f"Você atingiu o limite de {limit} favoritos do seu plano. Faça upgrade para ter favoritos ilimitados."
    return True, "Favorito autorizado."


def check_comment_limit(user):
    """Verifica se o usuário pode comentar baseado no plano"""
    limit = get_plan_entitlements(user)['comments_limit']
    if limit is None:
        return True, "Comentários ilimitados no plano VIP."

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Contar comentários de hoje
    count = Comment.query.filter(
        Comment.user_id == user.id,
        Comment.date_posted >= today_start
    ).count()

    if count >= limit:
        return False, f"Você atingiu o limite de {limit} comentários diários do seu plano. Faça upgrade para ampliar esse limite."
    return True, f"Comentário autorizado. Você tem {limit - count} comentários restantes hoje."


def check_download_history_access(user):
    """Verifica se o usuário pode acessar o histórico de downloads"""
    entitlements = get_plan_entitlements(user)
    return (
        bool(entitlements['download_history_access']),
        entitlements['download_history_limit'],
    )


def check_user_download_limit(user):
    """Verifica o limite de download definido pela matriz canônica de planos."""

    # Verificar se o usuário tem permissão para fazer downloads
    if hasattr(user, 'can_download') and not user.can_download:
        return False, 0, 0, None, 'blocked'

    brasilia_tz = pytz.timezone('America/Sao_Paulo')
    now = datetime.utcnow()
    now_brasilia = pytz.utc.localize(now).astimezone(brasilia_tz)

    entitlements = get_plan_entitlements(user)
    period = entitlements['download_period']

    if period == 'unlimited':
        return True, float('inf'), float('inf'), None, 'unlimited'

    if period == 'weekly':
        # Usar limite personalizado se definido, caso contrário usar padrão
        custom_limit = getattr(user, 'custom_weekly_limit', None)
        limit = custom_limit if custom_limit is not None else entitlements['download_limit']

        # Calcular próximo domingo às 00:00 (horário Brasília)
        days_until_sunday = (6 - now_brasilia.weekday()) % 7  # 0=segunda, 6=domingo
        if days_until_sunday == 0 and now_brasilia.hour >= 0:
            days_until_sunday = 7  # Já é domingo, próximo reset é em 7 dias

        next_sunday = (now_brasilia + timedelta(days=days_until_sunday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        reset_time = next_sunday.astimezone(pytz.utc).replace(tzinfo=None)

        # Resetar contador se passou da data de reset
        if user.week_reset_date:
            if now >= user.week_reset_date:
                user.weekly_downloads = 0
                user.week_reset_date = reset_time
                db.session.commit()
        else:
            user.week_reset_date = reset_time
            db.session.commit()

        current_downloads = user.weekly_downloads or 0
        remaining = max(0, limit - current_downloads)
        can_download = current_downloads < limit

        return can_download, remaining, limit, reset_time, 'weekly'

    if period == 'daily':
        # Usar limite personalizado se definido, caso contrário usar padrão
        custom_limit = getattr(user, 'custom_daily_limit', None)
        limit = custom_limit if custom_limit is not None else entitlements['download_limit']

        # Calcular próxima meia-noite (horário Brasília)
        next_midnight = (now_brasilia + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        reset_time = next_midnight.astimezone(pytz.utc).replace(tzinfo=None)

        # Resetar contador se passou da data de reset
        if user.download_reset_date:
            if now >= user.download_reset_date:
                user.daily_downloads = 0
                user.download_reset_date = reset_time
                db.session.commit()
        else:
            user.download_reset_date = reset_time
            db.session.commit()

        current_downloads = user.daily_downloads or 0
        remaining = max(0, limit - current_downloads)
        can_download = current_downloads < limit

        return can_download, remaining, limit, reset_time, 'daily'

    return False, 0, 0, None, 'blocked'


def check_support_priority(user):
    """Retorna o tempo de resposta do suporte baseado no plano"""
    return str(get_plan_entitlements(user)['support'])


def check_device_limit(user):
    """Verifica se o usuário pode acessar de mais dispositivos"""
    limit = int(get_plan_entitlements(user)['device_limit'])

    if user.active_sessions >= limit:
        return False, f"Você atingiu o limite de {limit} dispositivo(s) simultâneo(s) do plano {user.plan.capitalize()}. Faça upgrade para acessar de mais dispositivos."

    return True, f"Acesso autorizado. Você pode usar até {limit} dispositivo(s)."


def can_request_specific_content(user):
    """Verifica se o usuário pode abrir uma busca prioritária de conteúdo."""
    return can_request_priority_content(user)

@app.route('/favorite/<int:post_id>', methods=['POST'])
@login_required
def add_favorite(post_id):
    """Adiciona um post aos favoritos do usuário"""
    try:
        # Verifica se o post existe
        post = Post.query.get_or_404(post_id)

        # Limpa o cache da sessão
        db.session.expire_all()

        # Verifica se já está nos favoritos
        existing = Favorite.query.filter_by(
            user_id=current_user.id,
            post_id=post_id
        ).first()

        if existing:
            return jsonify({
                'success': True,
                'message': 'Post já está nos favoritos',
                'is_favorited': True
            })

        # Verificar limite de favoritos
        allowed, message = check_favorite_limit(current_user)

        if not allowed:
            return jsonify({
                'success': False,
                'message': message,
                'is_favorited': False
            }), 403

        # Adiciona aos favoritos
        favorite = Favorite(user_id=current_user.id, post_id=post_id)
        db.session.add(favorite)
        db.session.flush()
        db.session.commit()
        db.session.refresh(favorite)

        # Invalidar cache
        cache_key = f'fav_{current_user.id}_{post_id}'
        _favorite_check_cache[cache_key] = True
        _favorite_check_timestamps[cache_key] = __import__('time').time()

        return jsonify({
            'success': True,
            'message': 'Post adicionado aos favoritos',
            'is_favorited': True
        })

    except Exception:
        db.session.rollback()
        app.logger.exception('Erro ao adicionar favorito')
        return jsonify({
            'success': False,
            'message': 'Não foi possível adicionar o favorito.'
        }), 500

@app.route('/unfavorite/<int:post_id>', methods=['POST'])
@login_required
def remove_favorite(post_id):
    """Remove um post dos favoritos do usuário"""
    try:
        # Limpa o cache da sessão
        db.session.expire_all()

        # Busca o favorito
        favorite = Favorite.query.filter_by(
            user_id=current_user.id,
            post_id=post_id
        ).first()

        if not favorite:
            return jsonify({
                'success': True,
                'message': 'Post não está nos favoritos',
                'is_favorited': False
            })

        # Remove dos favoritos
        favorite_id = favorite.id
        db.session.delete(favorite)
        db.session.flush()
        db.session.commit()

        # Verifica se realmente foi removido
        still_exists = Favorite.query.get(favorite_id)
        if still_exists:
            db.session.delete(still_exists)
            db.session.commit()

        # Invalidar cache
        cache_key = f'fav_{current_user.id}_{post_id}'
        _favorite_check_cache[cache_key] = False
        _favorite_check_timestamps[cache_key] = __import__('time').time()

        return jsonify({
            'success': True,
            'message': 'Post removido dos favoritos',
            'is_favorited': False
        })

    except Exception:
        db.session.rollback()
        app.logger.exception('Erro ao remover favorito')
        return jsonify({
            'success': False,
            'message': 'Não foi possível remover o favorito.'
        }), 500

# Cache global para check-favorite com timestamp
_favorite_check_cache = {}
_favorite_check_timestamps = {}

@app.route('/api/check-favorite/<int:post_id>', methods=['GET'])
@login_required
def check_favorite(post_id):
    """Verifica se um post está nos favoritos do usuário com rate limiting"""
    try:
        import time
        cache_key = f'fav_{current_user.id}_{post_id}'
        current_time = time.time()

        # Verificar se existe cache válido (menos de 30 segundos)
        if cache_key in _favorite_check_timestamps:
            time_diff = current_time - _favorite_check_timestamps[cache_key]
            if time_diff < 30:  # 30 segundos de cache
                if cache_key in _favorite_check_cache:
                    response = jsonify({'is_favorited': _favorite_check_cache[cache_key]})
                    response.headers['X-From-Cache'] = 'true'
                    response.headers['Cache-Control'] = 'public, max-age=30'
                    return response

        # Buscar no banco
        db.session.expire_all()
        is_favorited = Favorite.query.filter_by(
            user_id=current_user.id,
            post_id=post_id
        ).first() is not None

        # Atualizar cache
        _favorite_check_cache[cache_key] = is_favorited
        _favorite_check_timestamps[cache_key] = current_time

        # Limpar cache antigo (mais de 60 segundos)
        keys_to_remove = [k for k, v in _favorite_check_timestamps.items() if current_time - v > 60]
        for k in keys_to_remove:
            _favorite_check_cache.pop(k, None)
            _favorite_check_timestamps.pop(k, None)

        response = jsonify({'is_favorited': is_favorited})
        response.headers['Cache-Control'] = 'public, max-age=30'
        return response

    except Exception:
        return jsonify({'is_favorited': False}), 500

@app.route('/admin/update-preferences', methods=['POST'])
@login_required
@admin_required
def admin_update_preferences():
    # Atualiza as preferências do usuário
    if request.method == 'POST':
        # Armazene as preferências em um campo JSON ou coluna específica no banco de dados
        # Este é apenas um exemplo - você precisará adicionar esses campos ao seu modelo de usuário
        preferences = {
            'language': request.form.get('language'),
            'timezone': request.form.get('timezone'),
            'email_notifications': 'email_notifications' in request.form,
            'browser_notifications': 'browser_notifications' in request.form
        }

        current_user.email_notifications = preferences['email_notifications']
        current_user.preferences = json.dumps(preferences)
        db.session.commit()

        flash('Preferências atualizadas com sucesso!', 'success')
    return redirect(url_for('admin_profile'))

@app.route('/test-password-toggle')
@login_required
@admin_required
def test_password_toggle():
    """Página de teste para debug do botão password toggle"""
    return render_template('test_password_toggle.html')

# Sincronizar categorias padrão (roda tanto com python app.py quanto com gunicorn)
def ensure_default_categories():
    """Garante que todas as categorias padrão existam no banco de dados"""
    default_categories = [
        {'name': 'BIOS', 'slug': 'bios', 'description': 'Atualizações e tutoriais de BIOS', 'order': 1},
        {'name': 'Esquemas', 'slug': 'esquemas', 'description': 'Esquemas elétricos de notebooks e placas-mãe', 'order': 2},
        {'name': 'Drivers', 'slug': 'drivers', 'description': 'Drivers para diversos dispositivos', 'order': 3},
        {'name': 'Softwares', 'slug': 'softwares', 'description': 'Programas e aplicativos úteis', 'order': 4},
        {'name': 'Impressoras', 'slug': 'impressoras', 'description': 'Drivers e softwares para impressoras', 'order': 5},
        {'name': 'Cursos', 'slug': 'cursos', 'description': 'Cursos e materiais de estudo', 'order': 6},
        {'name': 'Datasheet', 'slug': 'datasheet', 'description': 'Datasheets técnicos de componentes eletrônicos', 'order': 7},
    ]
    try:
        existing_slugs = {c.slug for c in Category.query.with_entities(Category.slug).all()}
        added_count = 0
        for cat_data in default_categories:
            if cat_data['slug'] not in existing_slugs:
                db.session.add(Category(
                    name=cat_data['name'],
                    slug=cat_data['slug'],
                    description=cat_data['description'],
                    is_active=True,
                    order=cat_data['order']
                ))
                added_count += 1
                app.logger.info('Categoria padrao adicionada: %s', cat_data['name'])
        if added_count > 0:
            db.session.commit()
            app.logger.info('%s categoria(s) padrao adicionada(s)', added_count)
    except Exception as e:
        db.session.rollback()
        app.logger.error('Erro ao verificar categorias padrao: %s', e)

with app.app_context():
    try:
        db.create_all()
        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                category_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(category)"))]
                if 'color' not in category_cols:
                    conn.execute(text("ALTER TABLE category ADD COLUMN color VARCHAR(20) DEFAULT '#4a90e2'"))
                    conn.commit()
                    app.logger.info("Coluna 'color' adicionada a category")
                if 'show_in_menu' not in category_cols:
                    conn.execute(text("ALTER TABLE category ADD COLUMN show_in_menu BOOLEAN DEFAULT 1"))
                    conn.commit()
                    app.logger.info("Coluna 'show_in_menu' adicionada a category")
        except Exception:
            pass
        ensure_default_categories()
        ensure_default_content_sources()
        # Garantir que colunas novas existam em tabelas existentes
        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                cols = [row[1] for row in conn.execute(text("PRAGMA table_info(favorites)"))]
                if 'position' not in cols:
                    conn.execute(text("ALTER TABLE favorites ADD COLUMN position INTEGER DEFAULT 0"))
                    conn.commit()
                    app.logger.info("Coluna 'position' adicionada a favorites")
                comment_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(comments)"))]
                if 'parent_id' not in comment_cols:
                    conn.execute(text("ALTER TABLE comments ADD COLUMN parent_id INTEGER"))
                    conn.commit()
                    app.logger.info("Coluna 'parent_id' adicionada a comments")
                user_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(user)"))]
                if 'preferences' not in user_cols:
                    conn.execute(text("ALTER TABLE user ADD COLUMN preferences TEXT"))
                    conn.commit()
                    app.logger.info("Coluna 'preferences' adicionada a user")
                transaction_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(transactions)"))]
                if transaction_cols and 'abacatepay_charge_id' not in transaction_cols:
                    conn.execute(text("ALTER TABLE transactions ADD COLUMN abacatepay_charge_id VARCHAR(255)"))
                    conn.commit()
                    app.logger.info("Coluna 'abacatepay_charge_id' adicionada a transactions")
                request_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(content_requests)"))]
                if request_cols and 'requester_plan' not in request_cols:
                    conn.execute(text("ALTER TABLE content_requests ADD COLUMN requester_plan VARCHAR(20) NOT NULL DEFAULT 'guest'"))
                    conn.execute(text(
                        "UPDATE content_requests "
                        "SET requester_plan = COALESCE((SELECT plan FROM user WHERE user.id = content_requests.user_id), 'guest') "
                        "WHERE user_id IS NOT NULL"
                    ))
                    conn.commit()
                    app.logger.info("Coluna 'requester_plan' adicionada a content_requests")
                category_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(category)"))]
                if 'color' not in category_cols:
                    conn.execute(text("ALTER TABLE category ADD COLUMN color VARCHAR(20) DEFAULT '#4a90e2'"))
                    conn.commit()
                    app.logger.info("Coluna 'color' adicionada a category")
                if 'show_in_menu' not in category_cols:
                    conn.execute(text("ALTER TABLE category ADD COLUMN show_in_menu BOOLEAN DEFAULT 1"))
                    conn.commit()
                    app.logger.info("Coluna 'show_in_menu' adicionada a category")
        except Exception:
            pass
    except Exception:
        app.logger.exception('Erro na inicializacao automatica')

# Criar o script de upgrade de banco de dados se ele não existir
if __name__ == '__main__':
    # Verificar se o script de atualização do banco de dados existe
    upgrade_script_path = os.path.join(os.path.dirname(__file__), 'db_upgrade.py')
    if not os.path.exists(upgrade_script_path):
        create_db_upgrade_script(upgrade_script_path)
        print(f"Criado script de atualização em: {upgrade_script_path}")
        print("Para migrar o banco de dados, execute: python db_upgrade.py all")

    # Inicializar o banco de dados dentro do contexto da aplicação apenas uma vez
    with app.app_context():
        try:
            # Verificar se as tabelas já existem antes de inicializar
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            if not inspector.has_table('user'):
                initialize_db()
            else:
                print("📁 Banco de dados já inicializado, pulando inicialização...")
        except Exception as e:
            print(f"Iniciando banco pela primeira vez: {e}")
            initialize_db()

    # Iniciar o aplicativo Flask com argumentos de host e porta
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', default=int(os.environ.get('PORT', '5000')), type=int)
    args = parser.parse_args()

    # Usar variável de ambiente para debug - segurança
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')

    # Verificação de segurança para ambiente Render
    if os.environ.get('RENDER'):
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("WARNING: You are running 'python app.py' in a production Render environment.")
        print("This uses the Werkzeug development server which is NOT suitable for production.")
        print("Please update your Render Start Command to: 'gunicorn app:app'")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

    app.run(debug=debug_mode, host=args.host, port=args.port)
