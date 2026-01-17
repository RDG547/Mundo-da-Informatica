from flask import Flask, render_template, redirect, url_for, request, jsonify, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_assets import Environment
from webassets.bundle import Bundle
from flask_compress import Compress
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import math
import os
import json
import sys
import shutil
import uuid
import stripe
from stripe import error as stripe_error
import pytz
import bleach
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps

# Importar correções de compatibilidade Flask 3.x (módulo opcional)
try:
    from flask3_compat import fix_importlib_warnings  # type: ignore[import-not-found]
    fix_importlib_warnings()
except ImportError:
    pass

from werkzeug.security import generate_password_hash, check_password_hash
# Importar url_parse baseado na versão disponível
from urllib.parse import urlparse as url_parse
from itsdangerous import URLSafeTimedSerializer as Serializer
import re
from werkzeug.utils import secure_filename
from PIL import Image
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
import cloudinary.api

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

# Verificar se está em modo debug
DEBUG_MODE = os.environ.get('FLASK_ENV') != 'production' and not os.environ.get('RENDER')

def debug_log(message):
    """Log apenas em modo de desenvolvimento"""
    if DEBUG_MODE:
        print(f"[DEBUG] {message}")

# Configuração da aplicação Flask
app = Flask(__name__)

# Usar SECRET_KEY forte - obrigatório em produção
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    if os.environ.get('FLASK_ENV') == 'production' or os.environ.get('RENDER'):
        raise ValueError('SECRET_KEY deve ser definida em produção!')
    secret_key = 'dev_key_5f352a14cb7e4b119811'
app.config['SECRET_KEY'] = secret_key

# Configurações de segurança de sessão
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production' or os.environ.get('RENDER')  # HTTPS apenas em produção
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Não acessível via JavaScript
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Proteção CSRF
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # Sessão expira em 24h

# Configuração do Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
app.config['STRIPE_PUBLIC_KEY'] = os.environ.get('STRIPE_PUBLIC_KEY')

# Configuração do Abacate Pay
app.config['ABACATEPAY_API_KEY'] = os.environ.get('ABACATEPAY_API_KEY', 'abc_prod_QUeb3CYeWdLghPg02rFpQU1N')
app.config['ABACATEPAY_API_URL'] = 'https://api.abacatepay.com/v1'

# Configuração do Cloudinary
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True
)

# Garantir que o diretório instance existe
os.makedirs(app.instance_path, exist_ok=True)

# Configuração do banco SQLite
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    # Desenvolvimento: caminho relativo local
    database_url = f'sqlite:///{os.path.join(app.instance_path, "site.db")}'

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

print(f"📁 Banco SQLite: Será criado em {database_url}")

# Configurações específicas do SQLite
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Configuração de Timezone para horário de Brasília
BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')

def get_brazil_time():
    """Retorna datetime atual no fuso horário de Brasília"""
    return datetime.now(BRAZIL_TZ)

# Definição de constantes
UPLOAD_FOLDER = 'static/uploads/profiles'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Configurações adicionais
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB máximo

# Inicializar as extensões
db = SQLAlchemy(app)
compress = Compress(app)
assets = Environment(app)

# Proteção CSRF - Desabilitada temporariamente
# TODO: Adicionar tokens CSRF em todos os formulários antes de habilitar
# csrf = CSRFProtect(app)
app.config['WTF_CSRF_ENABLED'] = False  # Desabilitar CSRF globalmente por enquanto

# Rate Limiting para evitar ataques de força bruta
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Headers de Segurança HTTP (Talisman)
# DESABILITADO: CSP estava bloqueando recursos externos
# TODO: Reconfigurar CSP adequadamente no futuro
# if os.environ.get('FLASK_ENV') == 'production' or os.environ.get('RENDER'):
#     Talisman(app,
#              force_https=True,
#              strict_transport_security=True,
#              content_security_policy=csp,
#              content_security_policy_nonce_in=['script-src'])

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
    slug = db.Column(db.String(50), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=True)
    featured = db.Column(db.Boolean, default=False)  # Campo para categorias em destaque
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

# Funções helper para analytics
def get_device_type(user_agent_string):
    """Detecta o tipo de dispositivo baseado no user agent"""
    if not user_agent_string:
        return 'Unknown'

    user_agent = user_agent_string.lower()

    if any(device in user_agent for device in ['iphone', 'android', 'mobile']):
        return 'Mobile'
    elif any(device in user_agent for device in ['ipad', 'tablet']):
        return 'Tablet'
    else:
        return 'Desktop'

def get_browser_name(user_agent_string):
    """Detecta o nome do navegador baseado no user agent"""
    if not user_agent_string:
        return 'Unknown'

    user_agent = user_agent_string.lower()

    if 'chrome' in user_agent and 'edg' not in user_agent:
        return 'Chrome'
    elif 'firefox' in user_agent:
        return 'Firefox'
    elif 'safari' in user_agent and 'chrome' not in user_agent:
        return 'Safari'
    elif 'edg' in user_agent:
        return 'Edge'
    elif 'opera' in user_agent:
        return 'Opera'
    else:
        return 'Other'

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


def validate_password_strength(password):
    """
    Valida a força de uma senha

    Args:
        password: Senha a ser validada

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
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

    return True, None


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
            print(f"✓ Imagem antiga deletada: {full_path}")
            return True

        return True  # Não existia, então não há problema

    except Exception as e:
        print(f"✗ Erro ao deletar imagem {image_path}: {e}")
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
            'description': 'Arquivos de BIOS atualizados para diversos modelos de notebooks e desktops, facilitando reparos e atualizações de hardware.'
        },
        'Esquemas': {
            'icon': 'fas fa-project-diagram',
            'description': 'Esquemas elétricos detalhados de placas-mãe e outros componentes eletrônicos, essenciais para manutenção e reparo avançado.'
        },
        'Drivers': {
            'icon': 'fas fa-cogs',
            'description': 'Drivers atualizados para diversos componentes de hardware, incluindo placas de rede, áudio, vídeo e periféricos específicos.'
        },
        'Softwares': {
            'icon': 'fas fa-laptop-code',
            'description': 'Programas essenciais para técnicos de informática, incluindo ferramentas de diagnóstico, otimização e recuperação de dados.'
        },
        'Impressoras': {
            'icon': 'fas fa-print',
            'description': 'Drivers, firmwares e recursos especializados para impressoras de diversas marcas e modelos, facilitando manutenção e configuração.'
        },
        'Cursos': {
            'icon': 'fas fa-graduation-cap',
            'description': 'Materiais educativos e cursos técnicos para aprimoramento profissional em informática, eletrônica e tecnologia.'
        }
    }

def apply_default_category_data(category):
    """
    Aplica ícone e descrição padrão para uma categoria se ela estiver no mapeamento.
    """
    default_data = get_default_category_data()
    if category.name in default_data:
        category.icon = default_data[category.name]['icon']
        category.description = default_data[category.name]['description']
    return category

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
        print(f"Erro ao registrar atividade administrativa: {e}")
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
        print(f"Erro ao registrar visitante: {e}")
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
        print(f"Erro ao incrementar views do post {post_id}: {e}")
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
        print(f"Erro ao incrementar downloads do post {post_id}: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass

@app.before_request
def before_request():
    """Executado antes de cada requisição"""
    # Verificar modo de manutenção
    try:
        maintenance_mode = SiteConfig.get_value('maintenance_mode', False)
        if maintenance_mode and not (current_user.is_authenticated and current_user.role == 'admin'):
            # Permitir acesso apenas a rotas específicas durante manutenção
            allowed_routes = ['static', 'admin', 'login', 'maintenance']
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
    def get_image_url(image_path, default='default.jpg'):
        """Retorna URL correta da imagem (Cloudinary ou local)"""
        if not image_path:
            return url_for('static', filename=f'images/profiles/{default}')

        # Se já for URL do Cloudinary, retornar diretamente
        if 'cloudinary.com' in image_path or image_path.startswith('http'):
            return image_path

        # Se for caminho local
        if image_path.startswith('posts/'):
            return url_for('static', filename=f'images/{image_path}')

        return url_for('static', filename=f'uploads/profiles/{image_path}')

    return dict(get_image_url=get_image_url)

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
                'app_version': '1.6.2'
            }
        except Exception as e:
            print(f"Erro ao injetar dados admin: {e}")
            return {
                'post_count': 0,
                'category_count': 0,
                'unread_comments': 0,
                'total_users': 0,
                'total_subscribers': 0,
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
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    user = db.relationship('User', backref=db.backref('download_records', lazy=True, cascade="all, delete"))
    post = db.relationship('Post', backref=db.backref('download_records', lazy=True, cascade="all, delete"))

    # Constraint para evitar duplicatas no mesmo momento
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', 'timestamp', name='unique_user_post_download_time'),)

# Modelo de Favoritos
class Favorite(db.Model):
    __tablename__ = 'favorites'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

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

    # Campos para edição
    is_edited = db.Column(db.Boolean, default=False)
    date_edited = db.Column(db.DateTime, nullable=True)

    # Adicionar chave estrangeira para User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Adicionar chave estrangeira para Post
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)

    # Relacionamento com User
    user = db.relationship('User', backref='comments')

    # Relacionamento com Post
    post = db.relationship('Post', backref='comments')

    @property
    def status(self):
        """Retorna o status do comentário baseado em is_approved"""
        return 'approved' if self.is_approved else 'pending'

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

# Configurações do site dinâmicas
class SiteConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    value_type = db.Column(db.String(20), default='string')  # string, int, float, bool, json
    description = db.Column(db.String(200), nullable=True)
    is_public = db.Column(db.Boolean, default=True)  # Se pode ser exibido no frontend

    @staticmethod
    def get_value(key, default=None):
        """Obtém o valor de uma configuração, convertido para o tipo apropriado"""
        config = SiteConfig.query.filter_by(key=key).first()
        if not config:
            return default

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
    def get_config():
        """Retorna um dicionário com todas as configurações públicas do site"""
        try:
            configs = SiteConfig.query.filter_by(is_public=True).all()
            config_dict = {}
            for config in configs:
                config_dict[config.key] = SiteConfig.get_value(config.key)

            # Configurações padrão caso não existam no banco
            defaults = {
                'site_name': 'Mundo da Informática',
                'site_description': 'Portal de tecnologia e informática',
                'contact_email': 'contato@mundodainformatica.com',
                'social_facebook': '#',
                'social_twitter': '#',
                'social_instagram': '#',
                'social_youtube': '#',
                'phone': '(11) 99999-9999',
                'whatsapp': '5511999999999',
                'address': 'São Paulo - SP'
            }

            # Mesclar com valores padrão
            for key, default_value in defaults.items():
                if key not in config_dict:
                    config_dict[key] = default_value

            return config_dict

        except Exception:
            # Em caso de erro, retorna configurações básicas
            return {
                'site_name': 'Mundo da Informática',
                'site_description': 'Portal de tecnologia e informática',
                'contact_email': 'contato@mundodainformatica.com',
                'social_facebook': '#',
                'social_twitter': '#',
                'social_instagram': '#',
                'social_youtube': '#',
                'phone': '(11) 99999-9999',
                'whatsapp': '5511999999999',
                'address': 'São Paulo - SP'
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
        """
        Retorna a URL correta da imagem (Cloudinary ou local)

        Args:
            image_path: Caminho da imagem (pode ser URL do Cloudinary ou nome do arquivo)
            folder: Pasta local caso seja arquivo local
            default: Imagem padrão se não houver imagem

        Returns:
            str: URL completa da imagem
        """
        if not image_path or image_path == 'default.jpg':
            return url_for('static', filename=f'images/{folder}/{default}')

        # Se já é uma URL do Cloudinary, retornar diretamente
        if image_path.startswith('http://') or image_path.startswith('https://'):
            return image_path

        # Caso contrário, é um arquivo local
        return url_for('static', filename=f'uploads/{folder}/{image_path}')

    # Categorias
    categories = Category.query.filter_by(is_active=True).order_by(Category.order).all()

    # Posts em destaque
    featured_posts = Post.query.filter_by(featured=True, is_active=True).order_by(Post.date_posted.desc()).limit(4).all()

    # Configurações do site
    config = SiteConfig.get_config()

    # Estatísticas para o frontend
    stats = {
        "total_posts": Post.query.filter_by(is_active=True).count(),
        "total_users": User.query.filter_by(is_active=True).count(),
        "total_downloads": db.session.query(db.func.sum(Post.downloads)).scalar() or 0,
        "total_subscribers": Subscriber.query.filter_by(is_active=True).count(),
        "total_comments": Comment.query.count()
    }

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
        featured_posts=featured_posts,
        post_url=post_url,
        get_image_url=get_image_url,  # Adicionar helper de imagens
        config=config,
        site_configs=config,  # Adicionar alias para compatibilidade
        stats=stats,
        current_year=datetime.now().year,
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

# Rotas principais
@app.route('/')
@app.route('/home')
def home():
    try:
        page = request.args.get('page', 1, type=int)
        posts_query = Post.query.filter_by(is_active=True).order_by(Post.date_posted.desc())
        posts_paginated = posts_query.paginate(page=page, per_page=6, error_out=False)
        posts = posts_paginated.items
        featured = Post.query.filter_by(featured=True).limit(4).all()

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

        return render_template('index.html', posts=posts, posts_pagination=posts_paginated, featured=featured, stats=stats, favorite_post_ids=favorite_post_ids, title='Início')
    except Exception as e:
        print(f"Erro ao acessar a página inicial: {e}")
        # Tentar inicializar o banco de dados novamente (já estamos no contexto da rota)
        initialize_db()
        # Tentar novamente após inicialização
        posts = Post.query.order_by(Post.date_posted.desc()).limit(6).all()
        featured = Post.query.filter_by(featured=True).limit(4).all()

        # Estatísticas reais para fallback
        stats = {
            'total_posts': Post.query.filter_by(is_active=True).count(),
            'total_downloads': db.session.query(db.func.sum(Post.downloads)).scalar() or 0,
            'total_users': User.query.filter_by(is_active=True).count(),
            'total_subscribers': Subscriber.query.filter_by(is_active=True).count()
        }

        return render_template('index.html', posts=posts, featured=featured, stats=stats, title='Início')

# Atualizar a rota /setup para redirecionar para o painel admin
@app.route('/setup')
def setup():
    """Rota depreciada - redireciona para o painel administrativo"""
    flash('A página de configuração foi movida para o painel administrativo.', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/categorias')
def all_categories():
    """Página exclusiva de todas as categorias"""
    # Buscar todas as categorias do banco de dados
    categories = Category.query.filter_by(is_active=True).order_by(Category.order.asc()).all()

    # Aplicar ícones e descrições padrão
    default_data = get_default_category_data()

    if categories:
        for cat in categories:
            if cat.name in default_data:
                # Sempre usar ícone e descrição padrão
                cat.icon = default_data[cat.name]['icon']
                cat.description = default_data[cat.name]['description']
    else:
        # Se não houver categorias no banco, criar objetos dict com dados padrão
        categories = [
            {'name': name, 'icon': data['icon'], 'description': data['description']}
            for name, data in default_data.items()
        ]

    return render_template('categories.html', categories=categories, title='Todas as Categorias')

@app.route('/categoria/<string:category>')
def category(category):
    page = request.args.get('page', 1, type=int)
    # Alterar category para category_str na consulta
    posts = Post.query.filter_by(category_str=category).order_by(Post.date_posted.desc()).paginate(page=page, per_page=12)

    # Obter subcategorias disponíveis - alterar category para category_str
    subcategories = db.session.query(Post.subcategory).filter(Post.category_str == category, Post.subcategory != None).distinct().all()
    subcategories = [subcategory[0] for subcategory in subcategories if subcategory[0]]

    # Obter IDs dos posts favoritados do usuário logado
    favorite_post_ids = set()
    if current_user.is_authenticated:
        favorite_post_ids = {f.post_id for f in Favorite.query.filter_by(user_id=current_user.id).all()}

    return render_template('category.html', posts=posts, category=category, subcategories=subcategories, favorite_post_ids=favorite_post_ids, title=f'Categoria - {category}')

@app.route('/subcategoria/<string:subcategory>')
def subcategory(subcategory):
    page = request.args.get('page', 1, type=int)
    posts = Post.query.filter_by(subcategory=subcategory).order_by(Post.date_posted.desc()).paginate(page=page, per_page=12)
    return render_template('category.html', posts=posts, subcategory=subcategory, title=f'Subcategoria - {subcategory}')

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
    related_posts = Post.query.filter(Post.category_str == post.category_str, Post.id != post.id).order_by(Post.views.desc()).limit(3).all()
    return render_template('post.html', post=post, related_posts=related_posts, title=post.title)

@app.route('/<string:category>/<string:slug>')
def post_by_slug(category, slug):
    """Nova rota com URL amigável: /categoria/nome-do-post"""
    post = Post.query.filter_by(slug=slug).first_or_404()

    # Incrementar visualizações
    increment_post_views(post.id)

    # Obter posts relacionados baseados na categoria
    related_posts = Post.query.filter(
        Post.category_str == post.category_str,
        Post.id != post.id
    ).order_by(Post.views.desc()).limit(3).all()

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
    if user.role == 'admin' or user.role == 'editor':
        return True, "Acesso administrativo."

    if user.plan == 'vip':
        return True, "Downloads ilimitados no plano VIP."

    # Converter para horário de Brasília (UTC-3)
    from pytz import timezone
    brasilia_tz = timezone('America/Sao_Paulo')
    now_utc = datetime.utcnow().replace(tzinfo=timezone('UTC'))
    now_brasilia = now_utc.astimezone(brasilia_tz)

    if user.plan == 'premium':
        # 15 downloads semanais - Reset toda segunda às 9h
        # Encontrar a última segunda-feira às 9h
        days_since_monday = (now_brasilia.weekday()) % 7  # 0 = segunda
        last_monday = now_brasilia.replace(hour=9, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)

        # Se ainda não passou das 9h da segunda atual, voltar para segunda anterior
        if now_brasilia < last_monday:
            last_monday -= timedelta(days=7)

        # Converter para UTC para comparação no banco
        last_monday_utc = last_monday.astimezone(timezone('UTC')).replace(tzinfo=None)

        count = Download.query.filter(
            Download.user_id == user.id,
            Download.timestamp >= last_monday_utc
        ).count()

        if count >= 15:
            # Calcular próxima segunda às 9h
            days_until_monday = (7 - now_brasilia.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            next_reset = (now_brasilia + timedelta(days=days_until_monday)).replace(hour=9, minute=0, second=0, microsecond=0)
            return False, f"Você atingiu seu limite de 15 downloads semanais. Próximo reset: {next_reset.strftime('%d/%m/%Y às %H:%M')}. Faça upgrade para VIP para downloads ilimitados."
        return True, f"Download autorizado. Você tem {15 - count} downloads restantes esta semana."

    # Plano Grátis: 1 download por dia - Reset todo dia às 9h
    today_9am = now_brasilia.replace(hour=9, minute=0, second=0, microsecond=0)

    # Se ainda não passou das 9h hoje, considerar o reset de ontem às 9h
    if now_brasilia < today_9am:
        last_reset = today_9am - timedelta(days=1)
    else:
        last_reset = today_9am

    # Converter para UTC para comparação no banco
    last_reset_utc = last_reset.astimezone(timezone('UTC')).replace(tzinfo=None)

    count = Download.query.filter(
        Download.user_id == user.id,
        Download.timestamp >= last_reset_utc
    ).count()

    if count >= 1:
        # Calcular próximo reset
        if now_brasilia < today_9am:
            next_reset = today_9am
        else:
            next_reset = today_9am + timedelta(days=1)
        return False, f"Você atingiu seu limite de 1 download diário. Próximo reset: {next_reset.strftime('%d/%m/%Y às %H:%M')}. Faça upgrade para Premium (15/semana) ou VIP (ilimitado)."

    return True, "Download autorizado."

@app.route('/download/<int:post_id>')
@login_required
def download_post(post_id):
    """Rota para downloads que incrementa o contador e verifica permissões"""
    post = Post.query.get_or_404(post_id)
    user = current_user

    # Log para debug
    debug_log(f"Usuário {user.username} (plano: {user.plan}) tentando download do post {post_id}")

    # Verificar permissões baseadas no plano ANTES de registrar o download
    can_download, remaining, limit, reset_time, period = check_user_download_limit(user)
    debug_log(f"Verificação de limite: can_download={can_download}, remaining={remaining}/{limit}, period={period}")

    if not can_download:
        # Se a verificação JavaScript falhou ou foi bypassada, retornar erro 403
        # O frontend DEVE fazer a verificação primeiro via /check-download-limit
        download_text = "download" if limit == 1 else "downloads"
        period_text = "diários" if period == 'daily' else "semanais" if period == 'weekly' else ""
        reset_text = "à meia-noite" if period == 'daily' else "no domingo às 00:00" if period == 'weekly' else ""
        message = f"Você atingiu o limite de {int(limit)} {download_text} {period_text}. Próximo reset {reset_text}."

        debug_log(f"Download negado para {user.username}")

        # Retornar JSON se for requisição AJAX, senão mostrar flash message
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': message,
                'can_download': False,
                'remaining': int(remaining) if remaining != float('inf') else 'unlimited',
                'limit': int(limit) if limit != float('inf') else 'unlimited'
            }), 403
        else:
            flash(message, 'warning')
            return redirect(url_for('post', post_id=post_id))

    # Registrar download (isso incrementa o contador para próxima verificação)
    new_download = Download(user_id=user.id, post_id=post.id, timestamp=datetime.utcnow())
    db.session.add(new_download)

    # Incrementar contador correto baseado no plano
    if user.plan == 'premium':
        user.weekly_downloads = (user.weekly_downloads or 0) + 1
        debug_log(f"Download registrado para {user.username} - Total esta semana: {user.weekly_downloads}")
    else:
        user.daily_downloads = (user.daily_downloads or 0) + 1
        debug_log(f"Download registrado para {user.username} - Total hoje: {user.daily_downloads}")

    db.session.commit()

    # Incrementar downloads do post
    increment_post_downloads(post_id)

    # Log da atividade de download
    try:
        log_admin_activity(
            user_id=current_user.id if current_user.is_authenticated else None,
            action="file_downloaded",
            description=f"Download do arquivo: {post.title}",
            metadata={
                'post_id': post_id,
                'post_title': post.title,
                'download_url': post.download_link
            }
        )
    except Exception:
        pass  # Não interromper o download se o log falhar

    # Redirecionar para o link de download real
    if post.download_link:
        return redirect(post.download_link)
    else:
        flash('Link de download não disponível para este post.', 'error')
        return redirect(url_for('post', post_id=post_id))


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
        ).order_by(Comment.date_posted.desc()).all()

        comments_list = []
        for comment in comments:
            # Determinar o nome do autor e foto de perfil
            if comment.user_id:
                author_name = comment.user.username
                profile_image = comment.user.profile_image if hasattr(comment.user, 'profile_image') else None
                user_id = comment.user_id
            else:
                author_name = comment.author_name
                profile_image = None
                user_id = None

            comment_data = {
                'id': comment.id,
                'author': author_name,
                'content': comment.content,
                'date': comment.date_posted.strftime('%d/%m/%Y %H:%M'),
                'profile_image': profile_image,
                'user_id': user_id,
                'is_edited': comment.is_edited if hasattr(comment, 'is_edited') else False
            }

            # Adicionar data de edição se foi editado
            if comment.is_edited and hasattr(comment, 'date_edited') and comment.date_edited:
                comment_data['date_edited'] = comment.date_edited.strftime('%d/%m/%Y %H:%M')

            comments_list.append(comment_data)

        return jsonify({
            'success': True,
            'comments': comments_list,
            'count': len(comments_list)
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
        ).order_by(Comment.date_posted.desc()).all()

        comments_list = []
        for comment in comments:
            # Determinar o nome do autor
            if comment.user_id:
                author_name = comment.user.username
            else:
                author_name = comment.author_name

            comments_list.append({
                'id': comment.id,
                'author': author_name,
                'content': comment.content,
                'date': comment.date_posted.strftime('%d/%m/%Y %H:%M')
            })

        return jsonify({
            'success': True,
            'comments': comments_list,
            'count': len(comments_list)
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
        data = request.get_json() if request.is_json else request.form
        is_valid, error_message, validated_data = validate_comment_data(data)

        if not is_valid:
            return jsonify({
                'success': False,
                'message': error_message
            }), 400

        # Type guard: garantir que validated_data não é None após validação bem-sucedida
        assert validated_data is not None, "validated_data should not be None when is_valid is True"

        # Se usuário estiver logado, usar seus dados
        if current_user.is_authenticated:
            # Verificar limite de comentários baseado no plano
            allowed, message = check_comment_limit(current_user)
            if not allowed:
                return jsonify({
                    'success': False,
                    'message': message
                }), 403

            new_comment = Comment(
                content=validated_data['content'],
                post_id=post.id,
                user_id=current_user.id,
                is_approved=True  # Comentários de usuários logados são aprovados automaticamente
            )
        else:
            # Validar nome e email para usuários não logados
            if not validated_data['author_name'] or not validated_data['author_email']:
                return jsonify({
                    'success': False,
                    'message': 'Nome e email são obrigatórios.'
                }), 400

            new_comment = Comment(
                content=validated_data['content'],
                post_id=post.id,
                author_name=validated_data['author_name'],
                author_email=validated_data['author_email'],
                is_approved=False  # Comentários de não logados precisam aprovação
            )

        # Salvar no banco
        db.session.add(new_comment)
        db.session.commit()

        # Preparar resposta
        response_data = {
            'success': True,
            'message': 'Comentário enviado com sucesso!' if new_comment.is_approved else 'Comentário enviado! Aguarde aprovação.',
            'comment': {
                'id': new_comment.id,
                'author': current_user.username if current_user.is_authenticated else validated_data['author_name'],
                'content': validated_data['content'],
                'date': new_comment.date_posted.strftime('%d/%m/%Y %H:%M'),
                'is_approved': new_comment.is_approved,
                'profile_image': current_user.profile_image if current_user.is_authenticated and hasattr(current_user, 'profile_image') else None
            }
        }

        return jsonify(response_data), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro ao adicionar comentário: {str(e)}'
        }), 500


@app.route('/<string:category>/<string:slug>/comments/<int:comment_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_comment_by_slug(category, slug, comment_id):
    """Deleta um comentário (apenas admins)"""
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

        # Verificar permissão: apenas o autor ou admin pode editar
        if comment.user_id != current_user.id and current_user.role != 'admin':
            return jsonify({
                'success': False,
                'message': 'Você não tem permissão para editar este comentário.'
            }), 403

        # Obter novo conteúdo
        data = request.get_json()
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
                'content': new_content,
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
        # Verifica se o post existe (lança 404 se não existir)
        Post.query.get_or_404(post_id)

        # Obter e validar dados do formulário
        data = request.get_json() if request.is_json else request.form
        is_valid, error_message, validated_data = validate_comment_data(data)

        if not is_valid:
            return jsonify({
                'success': False,
                'message': error_message
            }), 400

        # Type guard: garantir que validated_data não é None após validação bem-sucedida
        assert validated_data is not None, "validated_data should not be None when is_valid is True"

        # Se usuário estiver logado, usar seus dados
        if current_user.is_authenticated:
            # Verificar limite de comentários baseado no plano
            allowed, message = check_comment_limit(current_user)
            if not allowed:
                return jsonify({
                    'success': False,
                    'message': message
                }), 403

            new_comment = Comment(
                content=validated_data['content'],
                post_id=post_id,
                user_id=current_user.id,
                is_approved=True  # Comentários de usuários logados são aprovados automaticamente
            )
        else:
            # Validar nome e email para usuários não logados
            if not validated_data['author_name'] or not validated_data['author_email']:
                return jsonify({
                    'success': False,
                    'message': 'Nome e email são obrigatórios.'
                }), 400

            new_comment = Comment(
                content=validated_data['content'],
                post_id=post_id,
                author_name=validated_data['author_name'],
                author_email=validated_data['author_email'],
                is_approved=False  # Comentários de não logados precisam aprovação
            )

        # Salvar no banco
        db.session.add(new_comment)
        db.session.commit()

        # Preparar resposta
        response_data = {
            'success': True,
            'message': 'Comentário enviado com sucesso!' if new_comment.is_approved else 'Comentário enviado! Aguarde aprovação.',
            'comment': {
                'id': new_comment.id,
                'author': current_user.username if current_user.is_authenticated else validated_data['author_name'],
                'content': validated_data['content'],
                'date': new_comment.date_posted.strftime('%d/%m/%Y %H:%M'),
                'is_approved': new_comment.is_approved
            }
        }

        return jsonify(response_data), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erro ao enviar comentário: {str(e)}'
        }), 500


@app.route('/pesquisa')
def search():
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    filter_type = request.args.get('filter', 'all').strip()  # all, posts, categories

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
    all_categories = Category.query.all()
    category_names = [cat.name.lower() for cat in all_categories]
    all_posts = Post.query.filter_by(is_active=True).all()
    post_titles = [post.title.lower() for post in all_posts]
    known_terms = category_names + post_titles

    # Buscar sugestão se não houver resultados exatos
    suggestion = None
    close_matches = get_close_matches(query.lower(), known_terms, n=1, cutoff=0.6)
    if close_matches and close_matches[0].lower() != query.lower():
        suggestion = close_matches[0]

    # Buscar categorias que correspondem à pesquisa (apenas se filter != 'posts')
    categories = []
    if filter_type in ['all', 'categories']:
        # Busca mais restritiva - apenas se começar com a query ou for muito similar
        categories = Category.query.filter(
            db.or_(
                Category.name.ilike(f'{query}%'),  # Começa com
                Category.name.ilike(f'%{query}%')   # Contém (menos prioritário)
            )
        ).all()

        # Ordenar: exatas primeiro, depois que começam, depois que contêm
        def category_score(cat):
            name_lower = cat.name.lower()
            query_lower = query.lower()
            if name_lower == query_lower:
                return 0  # Exata
            elif name_lower.startswith(query_lower):
                return 1  # Começa com
            else:
                return 2  # Contém

        categories.sort(key=category_score)

    # Buscar posts (apenas se filter != 'categories')
    posts = []
    if filter_type in ['all', 'posts']:
        # Realizar pesquisa - Priorizar posts que começam com a query
        search_filter_starts = Post.query.filter_by(is_active=True)
        search_filter_contains = Post.query.filter_by(is_active=True)

        # Se há categoria específica, filtrar por ela
        if category:
            search_filter_starts = search_filter_starts.filter(Post.category_str == category)
            search_filter_contains = search_filter_contains.filter(Post.category_str == category)

        # Buscar posts que COMEÇAM com a query
        results_starts = search_filter_starts.filter(
            db.or_(
                Post.title.ilike(f'{query}%'),
                Post.seo_title.ilike(f'{query}%')
            )
        ).order_by(Post.date_posted.desc()).all()

        # Buscar posts que CONTÊM a query (mas não começam)
        results_contains = search_filter_contains.filter(
            db.or_(
                Post.title.ilike(f'%{query}%'),
                Post.content.ilike(f'%{query}%'),
                Post.seo_title.ilike(f'%{query}%'),
                Post.seo_description.ilike(f'%{query}%'),
                db.and_(Post.tags.isnot(None), Post.tags.ilike(f'%{query}%'))
            )
        ).filter(
            # Excluir os que já começam com a query no título ou SEO title
            ~db.or_(
                Post.title.ilike(f'{query}%'),
                Post.seo_title.ilike(f'{query}%')
            )
        ).order_by(Post.date_posted.desc()).all()

        # Combinar resultados (começam primeiro, depois contém)
        posts = results_starts + results_contains

        debug_log(f"SEARCH Query: '{query}', Posts found: {len(posts)}")  # DEBUG

    return render_template('search.html',
                         posts=posts,
                         categories=categories,
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
        'satisfaction_rate': 98  # Este pode ficar fixo ou ser calculado de outra forma
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
    checkout_plan = request.args.get('checkout')
    return render_template('plans.html', title='Planos e Preços', stripe_public_key=app.config['STRIPE_PUBLIC_KEY'], checkout_plan=checkout_plan)


@app.route('/api/user/permissions')
@login_required
def get_user_permissions():
    """Retorna as permissões e limites do usuário baseado no plano"""
    user = current_user

    # Calcular downloads restantes
    now = datetime.utcnow()
    downloads_info = {}

    if user.plan == 'free':
        one_day_ago = now - timedelta(days=1)
        count = Download.query.filter(Download.user_id == user.id, Download.timestamp >= one_day_ago).count()
        downloads_info = {
            'limit': 1,
            'period': 'dia',
            'used': count,
            'remaining': max(0, 1 - count)
        }
    elif user.plan == 'premium':
        one_week_ago = now - timedelta(days=7)
        count = Download.query.filter(Download.user_id == user.id, Download.timestamp >= one_week_ago).count()
        downloads_info = {
            'limit': 15,
            'period': 'semana',
            'used': count,
            'remaining': max(0, 15 - count)
        }
    else:  # VIP
        downloads_info = {
            'limit': 'ilimitado',
            'period': 'sempre',
            'used': 0,
            'remaining': 'ilimitado'
        }

    # Calcular comentários restantes hoje
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    comments_today = Comment.query.filter(
        Comment.user_id == user.id,
        Comment.date_posted >= today_start
    ).count()

    comments_info = {}
    if user.plan == 'free':
        comments_info = {
            'allowed': False,
            'limit': 0,
            'used': 0,
            'remaining': 0
        }
    elif user.plan == 'premium':
        comments_info = {
            'allowed': True,
            'limit': 2,
            'used': comments_today,
            'remaining': max(0, 2 - comments_today)
        }
    else:  # VIP
        comments_info = {
            'allowed': True,
            'limit': 'ilimitado',
            'used': comments_today,
            'remaining': 'ilimitado'
        }

    # Favoritos
    favorites_count = Favorite.query.filter_by(user_id=user.id).count()
    favorites_info = {}
    if user.plan == 'free':
        favorites_info = {
            'limit': 10,
            'used': favorites_count,
            'remaining': max(0, 10 - favorites_count)
        }
    else:  # Premium e VIP
        favorites_info = {
            'limit': 'ilimitado',
            'used': favorites_count,
            'remaining': 'ilimitado'
        }

    # Histórico de downloads
    history_access, history_limit = check_download_history_access(user)

    permissions = {
        'plan': user.plan,
        'plan_name': {'free': 'Grátis', 'premium': 'Premium', 'vip': 'VIP'}.get(user.plan, 'Grátis'),
        'downloads': downloads_info,
        'comments': comments_info,
        'favorites': favorites_info,
        'download_history': {
            'access': history_access,
            'limit': history_limit if history_limit else ('completo' if history_access else 'nenhum')
        },
        'support': check_support_priority(user),
        'devices': {
            'limit': {'free': 1, 'premium': 2, 'vip': 5}.get(user.plan, 1),
            'active': user.active_sessions
        },
        'can_request_content': can_request_specific_content(user),
        'vip_area': user.plan == 'vip'
    }

    return jsonify(permissions)

@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    try:
        data = request.get_json()
        plan_type = data.get('plan')

        debug_log(f'Stripe Checkout - Dados recebidos: {data}')
        debug_log(f'Stripe Checkout - Plano: {plan_type}')

        # Define prices (Replace with your actual Stripe Price IDs from env)
        prices = {
            'premium': os.environ.get('STRIPE_PRICE_PREMIUM', 'price_premium_placeholder'),
            'vip': os.environ.get('STRIPE_PRICE_VIP', 'price_vip_placeholder')
        }

        price_id = prices.get(plan_type)
        if not price_id:
            debug_log(f'Stripe Checkout - Plano inválido: {plan_type}')
            return jsonify({'error': 'Plano inválido'}), 400

        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': price_id,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            payment_method_types=['card'],  # Apenas cartão de crédito
            success_url=url_for('checkout_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('checkout_cancel', _external=True),
            customer_email=current_user.email,
            metadata={
                'user_id': str(current_user.id),
                'plan': plan_type
            }
        )
        return jsonify({'id': checkout_session.id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

    except Exception as e:
        flash(f'Erro ao verificar pagamento: {str(e)}', 'danger')
        print(f"Error verifying payment: {e}")

    return redirect(url_for('plans'))

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
        data = request.get_json()
        plan_type = data.get('plan')

        print(f'[PIX] Dados recebidos: {data}')
        print(f'[PIX] Plano: {plan_type}')
        print(f'[PIX] User ID: {current_user.id}')

        if plan_type not in ['premium', 'vip']:
            print(f'[PIX] ERRO - Plano inválido: {plan_type}')
            return jsonify({'error': 'Plano inválido'}), 400

        # Define preços em centavos
        prices = {
            'premium': 2990,  # R$ 29,90
            'vip': 4990       # R$ 49,90
        }

        amount = prices.get(plan_type)
        print(f'[PIX] Amount: {amount}')

        # Gerar ID único para o PIX
        pix_id = f'{plan_type}_{current_user.id}_{int(datetime.utcnow().timestamp())}'
        print(f'[PIX] PIX ID gerado: {pix_id}')

        # Criar transação pendente IMEDIATAMENTE para redirecionamento rápido
        try:
            transaction = Transaction(
                user_id=current_user.id,
                payment_gateway='abacatepay',
                abacatepay_billing_id=pix_id,
                plan_type=plan_type,
                amount=amount,
                currency='brl',
                status='processing'  # Status temporário até API responder
            )
            print(f'[PIX] Transaction object criado')

            db.session.add(transaction)
            print(f'[PIX] Transaction adicionado à sessão')

            db.session.commit()
            print(f'[PIX] Commit realizado - Transaction ID: {transaction.id}')

        except Exception as db_error:
            db.session.rollback()
            print(f'[PIX] ERRO DATABASE: {str(db_error)}')
            import traceback
            print(traceback.format_exc())
            return jsonify({'error': 'Erro ao salvar transação'}), 500

        # Retornar imediatamente para redirecionamento rápido
        # O processamento da API será feito em background
        redirect_url = url_for('pix_checkout_page', billing_id=pix_id, _external=True)
        print(f'[PIX] Redirect URL: {redirect_url}')

        return jsonify({
            'billing_id': pix_id,
            'transaction_id': transaction.id,
            'redirect_url': redirect_url
        })

    except Exception as e:
        print(f'[PIX] ERRO GERAL: {str(e)}')
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': 'Erro interno do servidor'}), 500


@app.route('/process-pix-async/<billing_id>', methods=['POST'])
@login_required
def process_pix_async(billing_id):
    """
    Processa a criação do QR Code PIX em background
    """
    try:
        import requests

        transaction = Transaction.query.filter_by(
            abacatepay_billing_id=billing_id,
            user_id=current_user.id
        ).first()

        if not transaction:
            return jsonify({'error': 'Transação não encontrada'}), 404

        # Se já foi processado, retornar sucesso
        if transaction.status in ['pending', 'completed']:
            return jsonify({
                'status': 'success',
                'qr_code': transaction.abacatepay_qr_code,
                'pix_code': transaction.abacatepay_pix_code
            })

        # Se foi cancelado, retornar erro
        if transaction.status == 'cancelled':
            return jsonify({'error': 'Transação foi cancelada'}), 400

        plan_type = transaction.plan_type
        amount = transaction.amount

        # Configuração API Abacate Pay
        api_key = app.config['ABACATEPAY_API_KEY']
        api_url = app.config['ABACATEPAY_API_URL']

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        # Payload para criar PIX QR Code
        payload = {
            'amount': amount,
            'expiresIn': 3600,
            'description': f'Plano {plan_type.upper()}',
            'customer': {
                'name': current_user.username,
                'cellphone': '+5511999999999',
                'email': current_user.email,
                'taxId': '11144477735'
            },
            'metadata': {
                'externalId': billing_id,
                'user_id': str(current_user.id),
                'plan': plan_type
            }
        }

        debug_log(f'Processando PIX async para billing_id: {billing_id}')

        try:
            response = requests.post(
                f'{api_url}/pixQrCode/create',
                headers=headers,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                pix_data = result.get('data', {})
                pix_charge_id = pix_data.get('id')
                pix_code = pix_data.get('brCode')
                qr_code_base64 = pix_data.get('brCodeBase64')

                # Atualizar transação com os dados do QR Code
                # IMPORTANTE: Manter o billing_id original para não quebrar o polling
                transaction.abacatepay_qr_code = qr_code_base64
                transaction.abacatepay_pix_code = pix_code
                transaction.status = 'pending'
                db.session.commit()

                debug_log(f'PIX QR Code criado com sucesso: {pix_charge_id}')

                return jsonify({
                    'status': 'success',
                    'qr_code': qr_code_base64,
                    'pix_code': pix_code
                })
            else:
                debug_log(f'Erro API Abacate Pay: {response.status_code}')
                transaction.status = 'failed'
                db.session.commit()
                return jsonify({
                    'status': 'error',
                    'message': 'Erro ao processar pagamento'
                }), 400

        except Exception as e:
            debug_log(f'Erro ao processar PIX async: {str(e)}')
            transaction.status = 'failed'
            db.session.commit()
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

    except Exception as e:
        debug_log(f'Erro geral no process_pix_async: {str(e)}')
        import traceback
        debug_log(traceback.format_exc())
        return jsonify({'error': 'Erro interno do servidor'}), 500
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
                         billing_id=billing_id)

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

    if billing_id:
        transaction = Transaction.query.filter_by(
            abacatepay_billing_id=billing_id,
            user_id=current_user.id
        ).first()

        if transaction and transaction.status == 'completed':
            flash(f'Assinatura {transaction.plan_type.upper()} realizada com sucesso via PIX!', 'success')
        else:
            flash('Aguardando confirmação do pagamento PIX. Você receberá uma notificação quando for processado.', 'info')
    else:
        flash('Pagamento PIX em processamento.', 'info')

    return redirect(url_for('plans'))

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

        return jsonify({
            'status': transaction.status,
            'paid': transaction.status == 'completed',
            'stop_polling': False
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/stripe-webhook', methods=['POST'])
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

    if not webhook_secret:
        debug_log('AVISO: STRIPE_WEBHOOK_SECRET não configurado! Webhook não pode verificar assinatura.')
        # Em produção, você DEVE rejeitar webhooks sem verificação
        if os.environ.get('FLASK_ENV') == 'production':
            return jsonify({'error': 'Webhook secret not configured'}), 500

    try:
        # Verificar assinatura do webhook (SEGURANÇA CRÍTICA)
        if webhook_secret and sig_header:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        else:
            # Modo dev sem verificação (NÃO USE EM PRODUÇÃO!)
            event = json.loads(payload)

        debug_log(f'Webhook recebido: {event["type"]}')

        # Processar eventos de pagamento
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            handle_checkout_completed(session)

        elif event['type'] == 'customer.subscription.created':
            subscription = event['data']['object']
            debug_log(f'Assinatura criada: {subscription["id"]}')

        elif event['type'] == 'customer.subscription.updated':
            subscription = event['data']['object']
            handle_subscription_updated(subscription)

        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            handle_subscription_cancelled(subscription)

        elif event['type'] == 'invoice.payment_succeeded':
            invoice = event['data']['object']
            debug_log(f'Pagamento bem-sucedido: {invoice["id"]}')

        elif event['type'] == 'invoice.payment_failed':
            invoice = event['data']['object']
            debug_log(f'Falha no pagamento: {invoice["id"]}')

        return jsonify({'status': 'success'}), 200

    except ValueError as e:
        # Payload inválido
        debug_log(f'Erro no payload do webhook: {str(e)}')
        return jsonify({'error': 'Invalid payload'}), 400

    except stripe_error.SignatureVerificationError as e:
        # Assinatura inválida
        debug_log(f'Erro na verificação da assinatura: {str(e)}')
        return jsonify({'error': 'Invalid signature'}), 400

    except Exception as e:
        debug_log(f'Erro ao processar webhook: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/abacatepay-webhook', methods=['POST'])
def abacatepay_webhook():
    """
    Webhook do Abacate Pay para processar eventos de pagamento PIX.

    Configure este endpoint no Dashboard do Abacate Pay.

    Eventos importantes:
    - billing.paid: Cobrança paga com sucesso
    - billing.failed: Falha no pagamento
    - billing.refunded: Pagamento estornado
    """
    try:
        payload = request.get_json()

        debug_log(f'Webhook Abacate Pay recebido: {payload}')

        # Extrair dados do evento
        event_type = payload.get('event')  # Ex: 'billing.paid'
        billing_data = payload.get('data', {})
        billing_id = billing_data.get('id')

        if not billing_id:
            debug_log('ERRO: billing_id não encontrado no webhook')
            return jsonify({'error': 'Missing billing_id'}), 400

        # Buscar transação
        transaction = Transaction.query.filter_by(abacatepay_billing_id=billing_id).first()

        if not transaction:
            debug_log(f'ERRO: Transação não encontrada para billing_id: {billing_id}')
            return jsonify({'error': 'Transaction not found'}), 404

        # Processar evento
        if event_type == 'billing.paid':
            handle_abacatepay_payment_success(transaction, billing_data)
        elif event_type == 'billing.failed':
            handle_abacatepay_payment_failed(transaction, billing_data)
        elif event_type == 'billing.refunded':
            handle_abacatepay_payment_refunded(transaction, billing_data)

        return jsonify({'status': 'success'}), 200

    except Exception as e:
        debug_log(f'Erro ao processar webhook Abacate Pay: {str(e)}')
        return jsonify({'error': str(e)}), 500

def handle_abacatepay_payment_success(transaction, billing_data):
    """Processa pagamento PIX bem-sucedido"""
    debug_log(f'Pagamento PIX confirmado: {transaction.abacatepay_billing_id}')

    try:
        user = User.query.get(transaction.user_id)
        if not user:
            debug_log(f'ERRO: Usuário {transaction.user_id} não encontrado')
            return

        # Verificar se já foi processado
        if transaction.status == 'completed':
            debug_log(f'Transação já processada: {transaction.abacatepay_billing_id}')
            return

        # ATIVAR PLANO PREMIUM/VIP
        user.plan = transaction.plan_type
        user.subscription_end_date = datetime.utcnow() + relativedelta(months=1)

        # Atualizar transação
        transaction.status = 'completed'
        transaction.paid_at = datetime.utcnow()

        db.session.commit()

        debug_log(f'Plano {transaction.plan_type} ativado para usuário {user.id} via PIX')

    except Exception as e:
        debug_log(f'Erro ao processar pagamento PIX: {str(e)}')
        db.session.rollback()

def handle_abacatepay_payment_failed(transaction, billing_data):
    """Processa falha no pagamento PIX"""
    debug_log(f'Pagamento PIX falhou: {transaction.abacatepay_billing_id}')

    try:
        transaction.status = 'failed'
        db.session.commit()
    except Exception as e:
        debug_log(f'Erro ao processar falha PIX: {str(e)}')
        db.session.rollback()

def handle_abacatepay_payment_refunded(transaction, billing_data):
    """Processa estorno de pagamento PIX"""
    debug_log(f'Pagamento PIX estornado: {transaction.abacatepay_billing_id}')

    try:
        user = User.query.get(transaction.user_id)
        if user and user.plan != 'free':
            # Reverter para plano gratuito
            user.plan = 'free'
            user.subscription_end_date = None

        transaction.status = 'refunded'
        db.session.commit()
    except Exception as e:
        debug_log(f'Erro ao processar estorno PIX: {str(e)}')
        db.session.rollback()

def handle_checkout_completed(session):
    """Processa checkout completado - ATIVA O PLANO AUTOMATICAMENTE"""
    session_id = session['id']
    user_id = session['metadata'].get('user_id')
    plan_type = session['metadata'].get('plan')

    debug_log(f'Checkout completado: session_id={session_id}, user_id={user_id}, plan={plan_type}')

    if not user_id or not plan_type:
        debug_log('ERRO: Metadata incompleto no checkout')
        return

    try:
        user = User.query.get(int(user_id))
        if not user:
            debug_log(f'ERRO: Usuário {user_id} não encontrado')
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

    except Exception as e:
        db.session.rollback()
        debug_log(f'ERRO ao processar checkout: {str(e)}')

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

@app.route('/contato', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        category = sanitize_input(request.form.get('category', ''))

        # Verificar plano apenas para categoria 'solicitacao'
        if category == 'solicitacao' and current_user.is_authenticated and current_user.plan == 'free':
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': 'A solicitação de conteúdo está disponível apenas para planos Premium e VIP.',
                    'requires_upgrade': True
                }), 403
            else:
                flash('A solicitação de conteúdo está disponível apenas para planos Premium e VIP. Faça upgrade para ter acesso!', 'warning')
                return redirect(url_for('plans'))

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

        if not message or len(message) > 5000:
            error_msg = 'Mensagem inválida ou muito longa'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_msg})
            flash(error_msg, 'danger')
            return redirect(url_for('contact'))

        new_contact = Contact(name=name, email=email, subject=subject, message=message)
        db.session.add(new_contact)
        db.session.commit()

        # Retornar JSON se for AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': 'Sua mensagem foi enviada com sucesso! Entraremos em contato em breve.'
            })

        flash('Sua mensagem foi enviada com sucesso! Entraremos em contato em breve.', 'success')
        return redirect(url_for('contact'))

    return render_template('contact.html', title='Contato')

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
        page=page, per_page=12, error_out=False
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
    posts = Post.query.order_by(Post.date_posted.desc()).limit(10).all()
    return jsonify([post.to_dict() for post in posts])

@app.route('/api/debug/posts')
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
    return jsonify(post.to_dict())

@app.route('/api/search/suggestions')
def search_suggestions():
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()

    debug_log(f" Search query: '{query}', category: '{category}'")  # DEBUG

    if not query or len(query) < 1:
        debug_log(" Query too short or empty")  # DEBUG
        return jsonify([])

    suggestions = []

    # Se não há categoria específica, buscar categorias também
    if not category:
        # Buscar categorias que COMEÇAM com a query (prioridade)
        categories_starts = Category.query.filter(
            Category.name.ilike(f'{query}%')
        ).filter_by(is_active=True).limit(2).all()

        debug_log(f" Categories starting with '{query}': {len(categories_starts)}")  # DEBUG

        # Buscar categorias que CONTÉM a query (caso não encontre suficientes)
        if len(categories_starts) < 2:
            categories_contains = Category.query.filter(
                Category.name.ilike(f'%{query}%'),
                ~Category.name.ilike(f'{query}%')  # Excluir as que já começam
            ).filter_by(is_active=True).limit(2 - len(categories_starts)).all()
            categories = categories_starts + categories_contains
        else:
            categories = categories_starts

        for cat in categories:
            suggestions.append({
                'type': 'category',
                'title': cat.name,
                'description': f'Categoria - {cat.description or "Ver todos os posts desta categoria"}',
                'url': url_for('category', category=cat.name),
                'icon': cat.icon or 'fas fa-folder'
            })

    # Buscar posts que COMEÇAM com a query (prioridade)
    posts_starts = Post.query.filter(
        Post.title.ilike(f'{query}%')
    ).filter_by(is_active=True)

    # Se há categoria específica, filtrar por ela
    if category:
        posts_starts = posts_starts.filter(Post.category_str == category)

    posts_starts_list = posts_starts.limit(5).all()

    debug_log(f" Posts starting with '{query}': {len(posts_starts_list)}")  # DEBUG

    # Buscar posts que CONTÉM a query (caso não encontre suficientes)
    posts_contains_list = []
    if len(posts_starts_list) < 5:
        posts_contains = Post.query.filter(
            db.or_(
                Post.title.ilike(f'%{query}%'),
                Post.content.ilike(f'%{query}%'),
                Post.seo_title.ilike(f'%{query}%'),
                Post.seo_description.ilike(f'%{query}%'),
                db.and_(Post.tags.isnot(None), Post.tags.ilike(f'%{query}%'))
            )
        ).filter_by(is_active=True)

        # Excluir posts que já começam com a query (já foram incluídos)
        if posts_starts_list:
            posts_contains = posts_contains.filter(
                ~Post.id.in_([p.id for p in posts_starts_list])
            )

        if category:
            posts_contains = posts_contains.filter(Post.category_str == category)

        posts_contains_list = posts_contains.limit(5 - len(posts_starts_list)).all()

        debug_log(f" Posts containing '{query}': {len(posts_contains_list)}")  # DEBUG

    posts = posts_starts_list + posts_contains_list

    # Verificar total de posts ativos no banco
    total_active_posts = Post.query.filter_by(is_active=True).count()
    debug_log(f" Total active posts in database: {total_active_posts}")  # DEBUG
    debug_log(f" Returning {len(posts)} suggestions")  # DEBUG

    for post in posts:
        category_name = post.category_str or (post.category_rel.name if post.category_rel else 'Sem categoria')

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
            'description': f'{category_name}',
            'category': category_name,
            'url': url_for('post_by_slug', category=generate_slug(post.category_str), slug=post.slug) if post.slug else url_for('post', post_id=post.id),
            'icon': category_icon
        })

    return jsonify(suggestions[:8])  # Limitar a 8 sugestões

@app.route('/admin/posts/<int:post_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def admin_toggle_post_active(post_id):
    """Ativar/Desativar um post"""
    post = Post.query.get_or_404(post_id)

    try:
        post.is_active = not post.is_active
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
@admin_required
def admin_delete_post(post_id):
    """Excluir um post"""
    post = Post.query.get_or_404(post_id)

    try:
        # Deletar imagem do Cloudinary ou filesystem
        if post.image_url:
            if 'cloudinary.com' in post.image_url:
                delete_from_cloudinary(post.image_url)
            else:
                delete_old_image(post.image_url)

        db.session.delete(post)
        db.session.commit()
        flash(f'Post "{post.title}" foi excluído com sucesso!', 'success')
    except Exception:
        db.session.rollback()
        flash('Erro ao excluir o post. Tente novamente.', 'error')

    # Redireciona para a página de listagem de posts após exclusão
    return redirect(url_for('admin_posts'))

@app.route('/admin/posts/<int:post_id>/duplicate', methods=['POST'])
@login_required
@admin_required
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
            download_link=original_post.download_link,
            image_url=duplicated_image_url,
            featured=False,  # Cópias não são destacadas por padrão
            is_active=False,  # Cópias ficam inativas por padrão
            author_id=current_user.id,
            views=0,
            downloads=0,
            slug=slug
        )

        db.session.add(new_post)
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

        flash(f'Post "{original_post.title}" foi duplicado com sucesso!', 'success')
        return redirect(url_for('admin_posts'))

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao duplicar o post: {str(e)}', 'error')
        return redirect(url_for('admin_posts'))

@app.route('/admin/posts/<int:post_id>/data')
@login_required
@admin_required
def admin_post_data(post_id):
    """Retorna dados do post em JSON para edição"""
    post = Post.query.get_or_404(post_id)

    return jsonify({
        'id': post.id,
        'title': post.title,
        'content': post.content,
        'category_id': post.category_id,
        'category_str': post.category_str,
        'download_link': post.download_link,
        'image_url': post.image_url,
        'featured': post.featured,
        'is_active': post.is_active,
        'author_id': post.author_id,
        'views': post.views,
        'downloads': post.downloads,
        'date_posted': post.date_posted.isoformat() if post.date_posted else None
    })

@app.route('/admin/posts/<int:post_id>/update', methods=['POST'])
@login_required
@admin_required
def admin_update_post(post_id):
    """Atualiza dados do post"""
    try:
        post = Post.query.get_or_404(post_id)

        # Obter dados do formulário
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        category_id = request.form.get('category_id')
        download_link = request.form.get('download_link', '').strip()
        image_url = request.form.get('image_url', '').strip()
        featured = request.form.get('featured') == 'true'
        is_active = request.form.get('is_active') == 'true'

        # Validações
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

        post.title = title
        post.content = content
        post.category_id = int(category_id) if category_id else None
        post.download_link = download_link if download_link else None
        post.image_url = image_url if image_url else 'default.jpg'
        post.featured = featured
        post.is_active = is_active

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
            'post': {
                'id': post.id,
                'title': post.title,
                'category_name': post.category_rel.name if post.category_rel else 'Sem Categoria',
                'views': post.views,
                'downloads': post.downloads,
                'is_active': post.is_active,
                'featured': post.featured,
                'date': post.date_posted.strftime('%d/%m/%Y')
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao atualizar post: {str(e)}'}), 500

@app.route('/admin/posts/<int:post_id>/toggle-featured', methods=['POST'])
@login_required
@admin_required
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

        print(f"📁 Banco SQLite: {'Encontrado' if db_exists else 'Será criado'} em {db_path}")

        # Criar todas as tabelas
        db.create_all()
        print("✅ Tabelas SQLite criadas/verificadas com sucesso!")

        # Adicionar configurações iniciais do site se não existirem
        if SiteConfig.query.count() == 0:
            default_configs = [
                SiteConfig(key='site_name', value='Mundo da Informática'),
                SiteConfig(key='site_description', value='Seu portal de tecnologia'),
                SiteConfig(key='contact_email', value='contato@mundodainformatica.com'),
                SiteConfig(key='admin_email', value='admin@mundodainformatica.com'),
                SiteConfig(key='site_keywords', value='tecnologia, informática, downloads, software'),
                SiteConfig(key='enable_comments', value='true'),
                SiteConfig(key='posts_per_page', value='10'),
                SiteConfig(key='site_theme', value='default')
            ]

            for config in default_configs:
                db.session.add(config)

            print("✅ Configurações iniciais do site adicionadas!")

        # Adicionar categorias padrão se não existirem
        if Category.query.count() == 0:
            default_categories = [
                Category(name='BIOS', slug='bios', description='Atualizações e tutoriais de BIOS', is_active=True, order=1),
                Category(name='Esquemas', slug='esquemas', description='Esquemas elétricos de notebooks e placas-mãe', is_active=True, order=2),
                Category(name='Drivers', slug='drivers', description='Drivers para diversos dispositivos', is_active=True, order=3),
                Category(name='Softwares', slug='softwares', description='Programas e aplicativos úteis', is_active=True, order=4),
                Category(name='Impressoras', slug='impressoras', description='Drivers e softwares para impressoras', is_active=True, order=5),
                Category(name='Cursos', slug='cursos', description='Cursos e materiais de estudo', is_active=True, order=6)
            ]

            for category in default_categories:
                db.session.add(category)

            print("✅ Categorias padrão adicionadas!")

        # Salvar todas as configurações
        db.session.commit()
        print("✅ Banco de dados SQLite inicializado com sucesso!")

        # Exibir estatísticas
        print(f"📊 Status: Posts: {Post.query.count()}, Categorias: {Category.query.count()}, Usuários: {User.query.count()}")

    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro na inicialização do banco: {e}")
        print("🔄 Continuando com configuração mínima...")


# Rota de login
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # Limitar tentativas de login
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
        # Capturar dados de rastreamento (sanitizado)
        user.ip_address = request.remote_addr or 'unknown'
        user.browser = request.user_agent.browser or 'unknown'
        user.operating_system = request.user_agent.platform or 'unknown'
        user.referrer = (request.referrer or 'Direct Access')[:500]  # Limitar tamanho
        db.session.commit()

        flash('Login realizado com sucesso!', 'success')

        # Redirecionar para a página que o usuário tentou acessar ou para o dashboard
        next_page = request.args.get('next')
        try:
            parsed = url_parse(next_page) if next_page else None
            if not next_page or (parsed and parsed.netloc != ''):
                if user.role == 'admin':
                    next_page = url_for('admin_dashboard')
                else:
                    next_page = url_for('home')
        except (ValueError, TypeError, AttributeError):
            # Fallback se houver problema com url_parse
            if user.role == 'admin':
                next_page = url_for('admin_dashboard')
            else:
                next_page = url_for('home')

        return redirect(next_page)

    return render_template('login.html', title='Login')

# Rota de cadastro
@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour")  # Limitar criação de contas
def register():
    # Se o usuário já estiver logado, redirecione para a página inicial
    if current_user.is_authenticated:
        return redirect(url_for('home'))

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
            return redirect(url_for('register'))

        if username and len(username) > 50:
            flash('Nome de usuário muito longo (máximo 50 caracteres)', 'danger')
            return redirect(url_for('register'))

        if email and len(email) > 255:
            flash('Email muito longo', 'danger')
            return redirect(url_for('register'))

        # Validações
        error = None

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
            return redirect(url_for('register'))

        # Verificar se usuário ou email já existem
        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            flash('Este nome de usuário já está em uso. Escolha outro.', 'danger')
            return redirect(url_for('register'))

        email_exists = User.query.filter_by(email=email).first()
        if email_exists:
            flash('Este email já está cadastrado. Faça login ou recupere sua senha.', 'danger')
            return redirect(url_for('register'))

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

            # Feedback de sucesso
            flash('Conta criada com sucesso! Você já pode fazer login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Erro ao registrar usuário: {e}")
            flash('Ocorreu um erro ao criar sua conta. Por favor, tente novamente.', 'danger')
            return redirect(url_for('register'))

    return render_template('register.html', title='Criar Conta')

# Rota de recuperação de senha (nova)
@app.route('/reset-password', methods=['GET', 'POST'])
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

            # Na versão atual, apenas simulamos o envio do email
            # No futuro, você pode implementar o envio real
            app.logger.info(f"Link de redefinição para {email}: {url_for('reset_password', token=token, _external=True)}")

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

        if len(password) < 6:
            flash('A senha deve ter pelo menos 6 caracteres', 'danger')
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
@admin_required
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

    # Outras tendências (simplificadas por enquanto)
    categories_trend = 0  # Categorias são mais estáveis
    downloads_trend = 25 if total_downloads > 0 else 0
    views_trend = 18 if page_views > 0 else 0

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
         .limit(5).all()

        for cat in category_downloads:
            chart_data['downloads_by_category'].append({
                'name': cat.name,
                'downloads': cat.total_downloads or 0
            })
    except Exception:
        # Se não há dados, criar estrutura vazia
        chart_data['downloads_by_category'] = []

    # Debug: Imprimir valores reais no console
    debug_log(f"- Stats reais do banco:")
    print(f"  Posts ativos: {posts_count}")
    print(f"  Posts em destaque: {featured_posts_count}")
    print(f"  Total de visualizações: {total_views}")
    print(f"  Categorias ativas: {categories_count}")
    print(f"  Usuários ativos: {users_count}")
    print(f"  Admins: {admin_users_count}")
    print(f"  Novos usuários hoje: {new_users_today}")
    print(f"  Inscritos ativos: {subscribers_count}")
    print(f"  Total downloads: {total_downloads}")
    print(f"  Downloads hoje: {downloads_today}")
    print(f"  Visitantes únicos: {unique_visitors}")
    print(f"  Visualizações de página: {page_views}")
    print(f"  Comentários: {comments_count}")

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
    # 1. Posts mais recentes (últimos 5)
    latest_posts = Post.query.filter_by(is_active=True).order_by(Post.date_posted.desc()).limit(5).all()
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

    # 2. Usuários recém-cadastrados (últimos 3)
    latest_users = User.query.filter_by(is_active=True).order_by(User.date_joined.desc()).limit(3).all()
    for user in latest_users:
        recent_activities.append({
            'type': 'user_registered',
            'icon': 'fas fa-user',
            'bg_class': 'bg-warning',
            'title': 'Novo usuário cadastrado',
            'description': f'{user.get_full_name()} se registrou no site',
            'date': user.date_joined
        })

    # 3. Posts atualizados recentemente (últimos 3 com date_updated)
    updated_posts = Post.query.filter(Post.date_updated.isnot(None), Post.is_active==True).order_by(Post.date_updated.desc()).limit(3).all()
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

    # 4. Comentários recentes (últimos 3)
    latest_comments = Comment.query.order_by(Comment.date_posted.desc()).limit(3).all()
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

    # Ordenar atividades por data (mais recente primeiro) e limitar a 10
    recent_activities.sort(key=lambda x: x['date'], reverse=True)
    recent_activities = recent_activities[:10]

    # Dados para a sidebar
    context = {
        "title": "Dashboard",
        "stats": stats,
        "recent_posts": recent_posts,
        "recent_activities": recent_activities,
        "categories": categories,
        "post_count": stats["posts"],
        "category_count": stats["categories"],
        "unread_comments": comments_count,  # Total de comentários
        "system_status": "online",
        "app_version": "1.6.2",
        "chart_data": chart_data  # Dados dos gráficos
    }

    debug_log(f"- Context stats sendo enviado para o template: {context['stats']}")

    return render_template('admin/dashboard.html', **context)

# Rota para exportar posts
@app.route("/admin/posts/export")
@login_required
@admin_required
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
@admin_required
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
@admin_required
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
        # Proteção contra NaN injection
        featured_value = request.form.get('featured', '')
        if isinstance(featured_value, str) and featured_value.lower() in ('nan', 'infinity', '-infinity'):
            featured = False
        else:
            # Converter para boolean de forma segura sem usar bool() diretamente em input
            featured = featured_value in ('true', '1', 'on', 'yes') if featured_value else False


        errors = {}
        if not title:
            errors['title'] = 'O título é obrigatório.'
        if not content:
            errors['content'] = 'A descrição é obrigatória.'
        if not category_id:
            errors['category'] = 'A categoria é obrigatória.'
        if not download_link:
            errors['download_link'] = 'O link é obrigatório.'

        if errors:
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
                    'tags': request.form.get('tags', ''),
                    'seo_title': request.form.get('seo_title', ''),
                    'seo_description': request.form.get('seo_description', ''),
                    'featured': featured,
                },
                # Repassar posts e stats para manter a página
                **get_admin_sidebar_stats()
            }
            # Paginação e posts
            posts = Post.query.order_by(Post.date_posted.desc()).all()
            page = request.args.get('page', 1, type=int)
            per_page = 10
            total = len(posts)
            start = (page - 1) * per_page
            end = start + per_page
            page_posts = posts[start:end]
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
            pagination = SimplePagination(page, per_page, total, page_posts)
            context["posts"] = pagination
            context["pagination"] = pagination
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
                flash('Formato de imagem não permitido. Use: PNG, JPG, GIF, WebP', 'error')
                return redirect(url_for('admin_posts'))

            # Upload para Cloudinary
            success, result = upload_to_cloudinary(image_file, folder='posts')

            if success:
                image_url = result  # URL do Cloudinary
            else:
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
            is_active=True,
            slug=slug
        )

        db.session.add(new_post)
        db.session.commit()

        flash(f'Post "{title}" criado com sucesso!', 'success')
        return redirect(url_for('admin_posts'))

    except Exception as e:
        db.session.rollback()
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
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'user')

        # Validações básicas
        if not all([name, username, email, password]):
            flash('Todos os campos são obrigatórios', 'error')
            return redirect(url_for('admin_users'))

        # Verificar se já existe usuário com este username ou email
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Já existe um usuário com este username ou email', 'error')
            return redirect(url_for('admin_users'))

        # Criar novo usuário
        new_user = User(
            name=name,
            username=username,
            email=email,
            password=generate_password_hash(password) if password else "",
            role=role,
            is_active=True
        )

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
@admin_required
def admin_posts():
    """
    Página para gerenciar posts
    """
    # Implementar paginação com dados reais
    class _Pagination:
        def __init__(self, items, page, per_page=10, total=0):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total or len(items)

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

    # Buscar posts reais do banco de dados
    posts = Post.query.order_by(Post.date_posted.desc()).all()

    # Paginação
    page = request.args.get('page', 1, type=int)
    per_page = 10
    total = len(posts)

    # Calcular itens da página atual
    start = (page - 1) * per_page
    end = start + per_page
    page_posts = posts[start:end]

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

    pagination = SimplePagination(page, per_page, total, page_posts)

    # Obter estatísticas para a sidebar
    sidebar_stats = get_admin_sidebar_stats()

    # Categorias para o modal
    categories = Category.query.order_by(Category.name).all()

    context = {
        "title": "Gerenciar Posts",
        "posts": pagination,
        "pagination": pagination,
        "categories": categories,
        "system_status": "online",
        "app_version": "1.6.2",
        **sidebar_stats
    }

    return render_template('admin/posts.html', **context)

# Adicionar as demais rotas administrativas
@app.route("/admin/analytics")
@login_required
@admin_required
def admin_analytics():
    """
    Página de estatísticas com dados reais do banco de dados
    """
    # Calcular estatísticas reais
    total_posts = Post.query.filter_by(is_active=True).count()
    total_categories = Category.query.filter_by(is_active=True).count()
    total_users = User.query.filter_by(is_active=True).count()
    total_comments = Comment.query.count()
    total_subscribers = Subscriber.query.filter_by(is_active=True).count()

    # Calcular total de visualizações e downloads reais dos posts
    total_views = db.session.query(db.func.sum(Post.views)).scalar() or 0
    total_downloads = db.session.query(db.func.sum(Post.downloads)).scalar() or 0

    # Últimos 30 dias de dados
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    # Novos usuários nos últimos 30 dias
    new_users = User.query.filter(User.date_joined >= thirty_days_ago).count()
    new_users_week = User.query.filter(User.date_joined >= seven_days_ago).count()

    # Novos posts nos últimos 30 dias
    new_posts = Post.query.filter(Post.date_posted >= thirty_days_ago).filter_by(is_active=True).count()

    # Calcular visitas totais únicas (baseado em IPs únicos nos VisitorLogs)
    total_unique_visits = db.session.query(
        db.func.count(db.func.distinct(VisitorLog.ip_address))
    ).scalar() or 0

    # Se não houver dados de visitantes, usar visualizações de posts como fallback
    if total_unique_visits == 0:
        total_unique_visits = total_views

    # Logs de visitantes dos últimos 7 dias
    daily_visits = []
    for i in range(7):
        date = datetime.utcnow().date() - timedelta(days=i)
        # Contar visitantes únicos por IP para cada data
        unique_ips = db.session.query(VisitorLog.ip_address).filter(
            db.func.date(VisitorLog.visit_time) == date
        ).distinct().count()

        # Se não há dados de visitantes, usar 0
        daily_visits.append({
            'date': date.strftime('%Y-%m-%d'),
            'visits': unique_ips
        })

    daily_visits.reverse()  # Ordem cronológica

    # Estatísticas de dispositivos (últimos 30 dias)
    device_stats = db.session.query(
        VisitorLog.device_type,
        db.func.count(VisitorLog.id).label('count')
    ).filter(VisitorLog.visit_time >= thirty_days_ago)\
     .group_by(VisitorLog.device_type).all()

    # Estatísticas de navegadores (últimos 30 dias)
    browser_stats = db.session.query(
        VisitorLog.browser,
        db.func.count(VisitorLog.id).label('count')
    ).filter(VisitorLog.visit_time >= thirty_days_ago)\
     .group_by(VisitorLog.browser)\
     .order_by(db.func.count(VisitorLog.id).desc())\
     .limit(5).all()

    # Se não há dados de visitantes, criar lista vazia
    if not browser_stats:
        browser_stats = []

    # Posts por categoria
    category_stats = db.session.query(
        Category.name,
        db.func.count(Post.id).label('post_count')
    ).outerjoin(Post, (Category.id == Post.category_id) & (Post.is_active == True))\
     .filter_by(is_active=True)\
     .group_by(Category.name).all()

    # Posts mais populares (últimos 30 dias)
    popular_posts = Post.query.filter_by(is_active=True)\
                             .order_by(Post.views.desc())\
                             .limit(5).all()

    # Origem de tráfego baseada em referrers
    traffic_sources = db.session.query(
        VisitorLog.referrer,
        db.func.count(VisitorLog.id).label('count')
    ).filter(VisitorLog.visit_time >= thirty_days_ago)\
     .group_by(VisitorLog.referrer)\
     .order_by(db.func.count(VisitorLog.id).desc())\
     .limit(10).all()

    # Calcular taxa de engajamento real (comentários / posts)
    engagement_rate = 0
    if total_posts > 0:
        engagement_rate = round((total_comments / total_posts) * 100, 1)

    analytics_data = {
        'total_visits': total_unique_visits,  # Visitas únicas reais
        'total_downloads': total_downloads,  # Downloads reais dos posts
        'new_users': new_users,  # Novos usuários últimos 30 dias
        'new_users_week': new_users_week,  # Novos usuários últimos 7 dias
        'new_posts': new_posts,
        'engagement_rate': f'{engagement_rate}%',  # Taxa real baseada em comentários
        'total_posts': total_posts,
        'total_categories': total_categories,
        'total_users': total_users,
        'total_comments': total_comments,
        'total_subscribers': total_subscribers,
        'daily_visits': daily_visits,
        'device_stats': [{'device': d.device_type or 'Unknown', 'count': d.count} for d in device_stats],
        'browser_stats': [{'browser': getattr(b, 'browser', 'Unknown'), 'count': getattr(b, 'count', 0)} for b in browser_stats],
        'category_stats': [{'name': c.name, 'post_count': c.post_count} for c in category_stats],
        'popular_posts': popular_posts,
        'traffic_sources': [{'source': t.referrer or 'Direct', 'count': t.count} for t in traffic_sources]
    }

    # Obter estatísticas para a sidebar
    sidebar_stats = get_admin_sidebar_stats()

    return render_template('admin/analytics.html',
                         title="Estatísticas",
                         analytics=analytics_data,
                         **sidebar_stats)

@app.route("/admin/categories")
@login_required
@admin_required
def admin_categories():
    """
    Página para gerenciar categorias com dados reais e estatísticas detalhadas
    """
    # Obter todas as categorias ordenadas
    categories = Category.query.order_by(Category.order, Category.name).all()

    # Aplicar ícones e descrições padrão
    for category in categories:
        apply_default_category_data(category)

    # Calcular estatísticas detalhadas para cada categoria
    category_stats = []
    total_posts = 0
    featured_count = 0

    for category in categories:
        # Posts ativos nesta categoria
        post_count = Post.query.filter_by(category_id=category.id, is_active=True).count()

        # Posts em destaque nesta categoria
        featured_posts = Post.query.filter_by(category_id=category.id, is_active=True, featured=True).count()

        # Total de downloads desta categoria
        total_downloads = db.session.query(db.func.sum(Post.downloads)).filter_by(category_id=category.id, is_active=True).scalar() or 0

        # Último post publicado nesta categoria
        last_post = Post.query.filter_by(category_id=category.id, is_active=True).order_by(Post.date_posted.desc()).first()

        # Verificar se categoria é destacada (assumindo campo featured)
        is_featured = getattr(category, 'featured', False)
        if is_featured:
            featured_count += 1

        category_stats.append({
            'id': category.id,
            'name': category.name,
            'slug': category.slug,
            'description': category.description or '',
            'icon': category.icon or 'fas fa-folder',
            'post_count': post_count,
            'featured_posts': featured_posts,
            'total_downloads': total_downloads,
            'is_active': category.is_active,
            'is_featured': is_featured,
            'order': category.order,
            'created_at': category.created_at if hasattr(category, 'created_at') else None,
            'last_post_date': last_post.date_posted if last_post else None,
            'last_post_title': last_post.title if last_post else None
        })

        total_posts += post_count

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
@admin_required
def admin_create_category():
    """
    Criar uma nova categoria
    """
    try:
        data = request.get_json() if request.is_json else request.form

        name = data.get('name', '').strip()
        slug = data.get('slug', '').strip()
        description = data.get('description', '').strip()
        icon = data.get('icon', 'fas fa-folder').strip()
        order = int(data.get('order', 0))
        is_active = bool(data.get('is_active', True))
        featured = bool(data.get('featured', False))

        # Validações
        if not name:
            return jsonify({'success': False, 'message': 'Nome da categoria é obrigatório.'}), 400

        # Gerar slug automaticamente se não fornecido
        if not slug:
            slug = re.sub(r'[^\w\s-]', '', name.lower())
            slug = re.sub(r'[-\s]+', '-', slug)

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
            order=order,
            is_active=is_active
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
            'category': {
                'id': new_category.id,
                'name': new_category.name,
                'slug': new_category.slug,
                'description': new_category.description,
                'icon': new_category.icon,
                'order': new_category.order,
                'is_active': new_category.is_active,
                'featured': getattr(new_category, 'featured', False)
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao criar categoria: {str(e)}'}), 500

@app.route("/admin/categories/<int:category_id>/update", methods=['PUT', 'POST'])
@login_required
@admin_required
def admin_update_category(category_id):
    """
    Atualizar uma categoria existente
    """
    try:
        category = Category.query.get_or_404(category_id)
        data = request.get_json() if request.is_json else request.form

        name = data.get('name', '').strip()
        slug = data.get('slug', '').strip()
        description = data.get('description', '').strip()
        icon = data.get('icon', 'fas fa-folder').strip()
        order = int(data.get('order', 0))
        is_active = bool(data.get('is_active', True))
        featured = bool(data.get('featured', False))

        # Validações
        if not name:
            return jsonify({'success': False, 'message': 'Nome da categoria é obrigatório.'}), 400

        # Verificar se slug já existe em outra categoria
        if slug != category.slug:
            existing_category = Category.query.filter_by(slug=slug).first()
            if existing_category and existing_category.id != category_id:
                return jsonify({'success': False, 'message': 'URL amigável (slug) já existe.'}), 400

        # Atualizar campos
        old_name = category.name
        category.name = name
        category.slug = slug
        category.description = description
        category.icon = icon
        category.order = order
        category.is_active = is_active

        # Atualizar campo featured se existe
        if hasattr(category, 'featured'):
            category.featured = featured

        # Aplicar ícone e descrição padrão se a categoria corresponder a um padrão
        apply_default_category_data(category)

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
            'category': {
                'id': category.id,
                'name': category.name,
                'slug': category.slug,
                'description': category.description,
                'icon': category.icon,
                'order': category.order,
                'is_active': category.is_active,
                'featured': getattr(category, 'featured', False)
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao atualizar categoria: {str(e)}'}), 500

@app.route("/admin/categories/<int:category_id>/delete", methods=['DELETE', 'POST'])
@login_required
@admin_required
def admin_delete_category(category_id):
    """
    Excluir uma categoria
    """
    try:
        category = Category.query.get_or_404(category_id)
        category_name = category.name

        # Verificar se há posts nesta categoria
        post_count = Post.query.filter_by(category_id=category_id).count()

        if post_count > 0:
            # Opção 1: Mover posts para categoria "Sem Categoria" ou primeira categoria disponível
            default_category = Category.query.filter(Category.id != category_id).first()
            if default_category:
                Post.query.filter_by(category_id=category_id).update({'category_id': default_category.id})
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
@admin_required
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
@admin_required
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
@admin_required
def admin_categories_stats():
    """
    Retornar estatísticas atualizadas das categorias
    """
    try:
        total_categories = Category.query.count()
        active_categories = Category.query.filter_by(is_active=True).count()
        featured_categories = Category.query.filter_by(featured=True).count()

        return jsonify({
            'success': True,
            'total': total_categories,
            'active': active_categories,
            'featured': featured_categories
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao buscar estatísticas: {str(e)}'}), 500

@app.route("/admin/categories/bulk-action", methods=['POST'])
@login_required
@admin_required
def admin_categories_bulk_action():
    """
    Executar ações em massa em categorias
    """
    try:
        data = request.get_json()
        action = data.get('action')
        category_ids = data.get('category_ids', [])

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
            for category in categories:
                db.session.delete(category)

            db.session.commit()
            log_admin_activity(
                current_user.id,
                'bulk_delete',
                f'{len(categories)} categorias excluídas em massa'
            )
            return jsonify({
                'success': True,
                'message': f'{len(categories)} categorias excluídas',
                'count': len(categories)
            })

        else:
            return jsonify({'success': False, 'message': 'Ação inválida'}), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro ao executar ação em massa: {str(e)}'}), 500

@app.route("/admin/posts/<int:post_id>/toggle-status", methods=['POST'])
@login_required
@admin_required
def admin_toggle_post_status(post_id):
    """
    Alternar status ativo/inativo de um post
    """
    try:
        post = Post.query.get_or_404(post_id)

        # Alternar o status
        post.is_active = not post.is_active
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
@admin_required
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
@admin_required
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

        flash('Comentário aprovado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao aprovar comentário: {str(e)}', 'error')

    return redirect(url_for('admin_comments'))

@app.route("/admin/comments/<int:comment_id>/reject", methods=['POST'])
@login_required
@admin_required
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

        flash('Comentário rejeitado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao rejeitar comentário: {str(e)}', 'error')

    return redirect(url_for('admin_comments'))

@app.route("/admin/comments/<int:comment_id>/delete", methods=['POST'])
@login_required
@admin_required
def admin_delete_comment(comment_id):
    """Excluir um comentário"""
    comment = Comment.query.get_or_404(comment_id)
    author_name = comment.author_name

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
                'post_id': comment.post_id
            }
        )

        flash('Comentário excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir comentário: {str(e)}', 'error')

    return redirect(url_for('admin_comments'))

@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    """
    Página para gerenciar usuários
    """
    # Buscar todos os usuários reais do banco de dados
    users = User.query.order_by(User.date_joined.desc()).all()

    # Paginação
    page = request.args.get('page', 1, type=int)
    per_page = 10
    total = len(users)

    # Calcular itens da página atual
    start = (page - 1) * per_page
    end = start + per_page
    page_users = users[start:end]

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
                         **sidebar_stats)

@app.route("/admin/users/<int:user_id>/data")
@login_required
@admin_required
def admin_user_data(user_id):
    """Retorna dados do usuário em JSON para edição"""
    user = User.query.get_or_404(user_id)

    # Calcular limites baseados no plano
    if user.plan == 'free':
        daily_limit = 1
        weekly_limit = 7
    elif user.plan == 'premium':
        daily_limit = 5
        weekly_limit = 15
    elif user.plan == 'vip':
        daily_limit = 999
        weekly_limit = 999
    else:
        daily_limit = 1
        weekly_limit = 7

    return jsonify({
        'id': user.id,
        'username': user.username,
        'name': user.name,
        'email': user.email,
        'role': user.role,
        'plan': user.plan,
        'is_active': user.is_active,
        'date_joined': user.date_joined.isoformat() if user.date_joined else None,
        'daily_downloads': user.daily_downloads or 0,
        'weekly_downloads': user.weekly_downloads or 0,
        'daily_limit': user.custom_daily_limit if hasattr(user, 'custom_daily_limit') and user.custom_daily_limit else daily_limit,
        'weekly_limit': user.custom_weekly_limit if hasattr(user, 'custom_weekly_limit') and user.custom_weekly_limit else weekly_limit,
        'download_reset_date': user.download_reset_date.isoformat() if user.download_reset_date else None,
        'week_reset_date': user.week_reset_date.isoformat() if user.week_reset_date else None,
        'can_download': user.can_download if hasattr(user, 'can_download') else True,
        'custom_daily_limit': user.custom_daily_limit if hasattr(user, 'custom_daily_limit') else None,
        'custom_weekly_limit': user.custom_weekly_limit if hasattr(user, 'custom_weekly_limit') else None
    })

@app.route("/admin/users/<int:user_id>/update", methods=['POST'])
@login_required
@admin_required
def admin_update_user(user_id):
    """Atualiza dados do usuário"""
    try:
        user = User.query.get_or_404(user_id)

        # Obter dados do formulário (permitir atualização parcial)
        username = request.form.get('username', user.username).strip()
        name = request.form.get('name', user.name or '').strip()
        email = request.form.get('email', user.email).strip()
        role = request.form.get('role', user.role)
        plan = request.form.get('plan', user.plan)
        is_active = request.form.get('is_active') == 'true' if 'is_active' in request.form else user.is_active

        # Novos campos de permissões de download
        can_download = request.form.get('can_download') == 'on' or request.form.get('can_download') == 'true' if 'can_download' in request.form else (user.can_download if hasattr(user, 'can_download') else True)
        custom_daily_limit = request.form.get('custom_daily_limit', '').strip()
        custom_weekly_limit = request.form.get('custom_weekly_limit', '').strip()

        # Validações
        if not username:
            return jsonify({'success': False, 'message': 'Nome de usuário é obrigatório'})

        if not email:
            return jsonify({'success': False, 'message': 'Email é obrigatório'})

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

        # Atualizar permissões de download
        user.can_download = can_download
        user.custom_daily_limit = int(custom_daily_limit) if custom_daily_limit else None
        user.custom_weekly_limit = int(custom_weekly_limit) if custom_weekly_limit else None

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
                    'can_download': can_download,
                    'custom_daily_limit': user.custom_daily_limit,
                    'custom_weekly_limit': user.custom_weekly_limit
                }
            }
        )

        return jsonify({'success': True, 'message': 'Usuário atualizado com sucesso'})

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
        data = request.get_json()
        new_password = data.get('new_password', '').strip()

        # Validações
        if not new_password:
            return jsonify({'success': False, 'message': 'Nova senha é obrigatória'})

        if len(new_password) < 6:
            return jsonify({'success': False, 'message': 'A senha deve ter pelo menos 6 caracteres'})

        # Não permitir redefinir senha do próprio usuário desta forma
        if user.id == current_user.id:
            return jsonify({'success': False, 'message': 'Use a página de perfil para alterar sua própria senha'})

        # Atualizar senha
        user.password = generate_password_hash(new_password)
        db.session.commit()

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
        data = request.get_json()

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
        data = request.get_json()

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
        data = request.get_json()

        new_role = data.get('role', 'user')

        # Validar role
        if new_role not in ['user', 'admin']:
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

    # Obter estatísticas para a sidebar
    sidebar_stats = get_admin_sidebar_stats()

    return render_template('admin/newsletter.html',
                         title="Newsletter",
                         subscribers=page_subscribers,
                         pagination=pagination,
                         total_subscribers=total_subscribers,
                         active_subscribers=active_subscribers,
                         recent_subscribers=recent_subscribers,
                         **sidebar_stats)

@app.route('/downgrade_plan', methods=['POST'])
@login_required
def downgrade_plan():
    try:
        data = request.get_json()
        target_plan = data.get('target_plan', 'free') if data else 'free'

        # Validar plano de destino
        if target_plan not in ['free', 'premium', 'vip']:
            return jsonify({'success': False, 'message': 'Plano inválido.'}), 400

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
        plan_names = {'free': 'Grátis', 'premium': 'Premium', 'vip': 'VIP'}
        message = f'Seu plano foi alterado para {plan_names[target_plan]} com sucesso.'

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
        data = request.get_json()
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
    """
    Página para importação de dados
    """
    # Obter estatísticas para a sidebar
    sidebar_stats = get_admin_sidebar_stats()

    return render_template('admin/tools_import.html',
                         title="Importar Dados",
                         **sidebar_stats)

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
                         **sidebar_stats)

@app.route("/admin/save_settings", methods=['POST'])
@login_required
@admin_required
def admin_save_settings():
    """
    Salvar configurações do site
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'success': False, 'message': 'Dados não fornecidos'})

        # Salvar cada configuração
        for key, config in data.items():
            value = config.get('value')
            value_type = config.get('type', 'string')

            SiteConfig.set_value(
                key=key,
                value=value,
                value_type=value_type,
                is_public=True
            )

        # Log da atividade
        try:
            log_admin_activity(
                user_id=current_user.id,
                action="settings_updated",
                description=f"Configurações do site atualizadas",
                metadata={'updated_keys': list(data.keys())}
            )
        except Exception as e:
            print(f"Erro ao registrar atividade: {e}")

        return jsonify({'success': True, 'message': 'Configurações salvas com sucesso!'})

    except Exception as e:
        print(f"Erro ao salvar configurações: {e}")
        return jsonify({'success': False, 'message': 'Erro interno do servidor'})

@app.route("/admin/profile")
@login_required
def admin_profile():
    """
    Página de perfil do usuário
    """
    # Obter estatísticas para a sidebar
    sidebar_stats = get_admin_sidebar_stats()

    return render_template('admin/profile.html',
                         title="Meu Perfil",
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
        favorites = Favorite.query.filter_by(user_id=user.id).order_by(Favorite.date_added.desc()).all()
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
        favorites = Favorite.query.filter_by(user_id=user.id).order_by(Favorite.date_added.desc()).all()

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
                    'download_link': post.download_link,
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
    except Exception as e:
        print(f"[ERRO] Ao buscar favoritos: {str(e)}")
        import traceback
        traceback.print_exc()
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
        # Processar a imagem antes do upload
        img = Image.open(file.stream)

        # Remover dados EXIF (segurança)
        img_data = list(img.getdata())
        img_without_exif = Image.new(img.mode, img.size)
        img_without_exif.putdata(img_data)
        img_without_exif = img_without_exif.convert('RGB')

        # Redimensionar para otimizar (máximo 800x800 para perfis)
        if folder == 'profiles':
            img_without_exif.thumbnail((800, 800))

        # Salvar em buffer temporário
        from io import BytesIO
        buffer = BytesIO()
        img_without_exif.save(buffer, format='JPEG', optimize=True, quality=85)
        buffer.seek(0)

        # Upload para Cloudinary
        result = cloudinary.uploader.upload(
            buffer,
            folder=f'mundodainformatica/{folder}',
            resource_type='image',
            format='jpg',
            transformation=[
                {'width': 800, 'height': 800, 'crop': 'limit'},
                {'quality': 'auto:good'},
                {'fetch_format': 'auto'}
            ]
        )

        return True, result['secure_url']

    except Exception as e:
        print(f"Erro ao fazer upload para Cloudinary: {e}")
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
            print(f"Imagem deletada do Cloudinary: {public_id}")
    except Exception as e:
        print(f"Erro ao deletar do Cloudinary: {e}")

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

        except Exception as e:
            print(f"Erro ao processar imagem: {e}")
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
@admin_required
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
        except Exception as e:
            print(f"Erro ao processar imagem: {e}")
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

# Adicione estas rotas se ainda não existirem

@app.route('/admin/update-profile', methods=['POST'])
@login_required
def admin_update_profile():
    # Atualiza os dados básicos do perfil
    if request.method == 'POST':
        current_user.name = request.form.get('name')
        current_user.username = request.form.get('username')
        current_user.email = request.form.get('email')
        current_user.bio = request.form.get('bio')
        current_user.phone = request.form.get('phone')
        current_user.location = request.form.get('location')
        current_user.website = request.form.get('website')

        # Redes sociais
        current_user.facebook = request.form.get('facebook')
        current_user.twitter = request.form.get('twitter')
        current_user.instagram = request.form.get('instagram')
        current_user.linkedin = request.form.get('linkedin')
        current_user.github = request.form.get('github')

        db.session.commit()

        # Se for uma requisição AJAX, retorna JSON com todos os dados
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
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

    # Redirecionar para a página de perfil
    return redirect(url_for('profile'))

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
    if len(new_password) < 6:
        flash('A nova senha deve ter pelo menos 6 caracteres', 'error')
        return redirect(url_for('profile'))

    # Atualize a senha
    current_user.set_password(new_password)
    db.session.commit()

    flash('Senha atualizada com sucesso!', 'success')
    return redirect(url_for('profile'))

# Rotas de Favoritos

def check_favorite_limit(user):
    """Verifica se o usuário pode adicionar favoritos baseado no plano"""
    if user.role == 'admin' or user.role == 'editor':
        return True, "Acesso administrativo."
    if user.plan in ['premium', 'vip']:
        return True, "Favoritos ilimitados."

    # Plano Grátis: Máximo 10 favoritos
    count = Favorite.query.filter_by(user_id=user.id).count()
    if count >= 10:
        return False, "Você atingiu o limite de 10 favoritos do plano Grátis. Faça upgrade para Premium ou VIP para favoritos ilimitados."
    return True, "Favorito autorizado."


def check_comment_limit(user):
    """Verifica se o usuário pode comentar baseado no plano"""
    if user.role == 'admin' or user.role == 'editor':
        return True, "Acesso administrativo."

    if user.plan == 'vip':
        return True, "Comentários ilimitados no plano VIP."

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Contar comentários de hoje
    count = Comment.query.filter(
        Comment.user_id == user.id,
        Comment.date_posted >= today_start
    ).count()

    if user.plan == 'premium':
        # Premium: 2 comentários diários
        if count >= 2:
            return False, "Você atingiu o limite de 2 comentários diários. Faça upgrade para VIP para comentários ilimitados."
        return True, f"Comentário autorizado. Você tem {2 - count} comentários restantes hoje."

    # Plano Grátis: Sem permissão para comentar
    return False, "Comentários não estão disponíveis no plano Grátis. Faça upgrade para Premium (2/dia) ou VIP (ilimitado) para comentar."


def check_download_history_access(user):
    """Verifica se o usuário pode acessar o histórico de downloads"""
    if user.role == 'admin' or user.role == 'editor':
        return True, None  # Acesso total

    if user.plan == 'vip':
        return True, None  # Histórico completo

    if user.plan == 'premium':
        return True, 5  # Últimos 5 downloads

    # Plano Grátis: Sem acesso ao histórico
    return False, None


def check_user_download_limit(user):
    """Verifica se o usuário atingiu o limite de downloads (diários para Free, semanais para Premium)"""

    # Verificar se o usuário tem permissão para fazer downloads
    if hasattr(user, 'can_download') and not user.can_download:
        return False, 0, 0, None, 'blocked'

    if user.role == 'admin' or user.role == 'editor':
        return True, float('inf'), float('inf'), None, 'unlimited'  # Sem limites

    brasilia_tz = pytz.timezone('America/Sao_Paulo')
    now = datetime.utcnow()
    now_brasilia = pytz.utc.localize(now).astimezone(brasilia_tz)

    # VIP: ilimitado
    if user.plan == 'vip':
        return True, float('inf'), float('inf'), None, 'unlimited'

    # PREMIUM: 15 downloads semanais (reset domingo 00:00 Brasília) - ou limite personalizado
    elif user.plan == 'premium':
        # Usar limite personalizado se definido, caso contrário usar padrão
        limit = user.custom_weekly_limit if hasattr(user, 'custom_weekly_limit') and user.custom_weekly_limit else 15

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

    # FREE: 1 download diário (reset meia-noite Brasília) - ou limite personalizado
    else:
        # Usar limite personalizado se definido, caso contrário usar padrão
        limit = user.custom_daily_limit if hasattr(user, 'custom_daily_limit') and user.custom_daily_limit else 1

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


def check_support_priority(user):
    """Retorna o tempo de resposta do suporte baseado no plano"""
    if user.role == 'admin' or user.role == 'editor':
        return "Suporte prioritário"

    if user.plan == 'vip':
        return "Suporte Prioritário"

    if user.plan == 'premium':
        return "Suporte em até 24H"

    # Plano Grátis
    return "Suporte em até 48H"


def check_device_limit(user):
    """Verifica se o usuário pode acessar de mais dispositivos"""
    if user.role == 'admin' or user.role == 'editor':
        return True, "Acesso administrativo."

    max_devices = {
        'vip': 5,
        'premium': 2,
        'free': 1
    }

    limit = max_devices.get(user.plan, 1)

    if user.active_sessions >= limit:
        return False, f"Você atingiu o limite de {limit} dispositivo(s) simultâneo(s) do plano {user.plan.capitalize()}. Faça upgrade para acessar de mais dispositivos."

    return True, f"Acesso autorizado. Você pode usar até {limit} dispositivo(s)."


def can_request_specific_content(user):
    """Verifica se o usuário pode solicitar conteúdo específico"""
    if user.role == 'admin' or user.role == 'editor':
        return True

    # Apenas VIP pode pedir conteúdo específico
    return user.plan == 'vip'

@app.route('/favorite/<int:post_id>', methods=['POST'])
@login_required
def add_favorite(post_id):
    """Adiciona um post aos favoritos do usuário"""
    try:
        print(f"[FAVORITOS] Tentando adicionar post {post_id} para usuário {current_user.id}")

        # Verifica se o post existe
        post = Post.query.get_or_404(post_id)
        print(f"[FAVORITOS] Post encontrado: {post.title}")

        # Limpa o cache da sessão
        db.session.expire_all()

        # Verifica se já está nos favoritos
        existing = Favorite.query.filter_by(
            user_id=current_user.id,
            post_id=post_id
        ).first()

        if existing:
            print(f"[FAVORITOS] Post {post_id} já está nos favoritos")
            return jsonify({
                'success': True,
                'message': 'Post já está nos favoritos',
                'is_favorited': True
            })

        # Verificar limite de favoritos
        print(f"[FAVORITOS] Verificando limites para usuário {current_user.username} (plano: {current_user.plan})")
        allowed, message = check_favorite_limit(current_user)
        print(f"[FAVORITOS] Resultado verificação: allowed={allowed}, message={message}")

        if not allowed:
            print(f"[FAVORITOS] Limite atingido: {message}")
            return jsonify({
                'success': False,
                'message': message,
                'is_favorited': False
            }), 403

        # Adiciona aos favoritos
        print(f"[FAVORITOS] Adicionando ao banco de dados")
        favorite = Favorite(user_id=current_user.id, post_id=post_id)
        db.session.add(favorite)
        db.session.flush()
        db.session.commit()
        db.session.refresh(favorite)

        # Invalidar cache
        cache_key = f'fav_{current_user.id}_{post_id}'
        _favorite_check_cache[cache_key] = True
        _favorite_check_timestamps[cache_key] = __import__('time').time()

        print(f"[FAVORITOS] Favorito adicionado com sucesso: ID={favorite.id}")
        return jsonify({
            'success': True,
            'message': 'Post adicionado aos favoritos',
            'is_favorited': True
        })

    except Exception as e:
        db.session.rollback()
        print(f"[ERRO] Ao adicionar favorito: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erro ao adicionar favorito: {str(e)}'
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

    except Exception as e:
        db.session.rollback()
        print(f"[ERRO] Ao remover favorito: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erro ao remover favorito: {str(e)}'
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

        # Supondo que você tenha um campo preferences no modelo User
        current_user.preferences = json.dumps(preferences)
        db.session.commit()

        flash('Preferências atualizadas com sucesso!', 'success')
    return redirect(url_for('admin_profile'))

@app.route('/test-password-toggle')
def test_password_toggle():
    """Página de teste para debug do botão password toggle"""
    return render_template('test_password_toggle.html')

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
    parser.add_argument('--port', default=5000, type=int)
    args = parser.parse_args()

    # Usar variável de ambiente para debug - segurança
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
    app.run(debug=debug_mode, host=args.host, port=args.port)
