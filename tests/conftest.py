import os
import sys
from pathlib import Path

import pytest


# Mantém o módulo principal importável tanto com ``python -m pytest`` quanto
# pelo executável ``pytest`` instalado no ambiente virtual.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# A aplicação lê estas variáveis durante o import. O banco em memória impede
# que a suíte toque no arquivo de desenvolvimento.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FLASK_ENV"] = "development"
os.environ["SITE_URL"] = "https://mundodainformatica.com"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test"
# A suíte legada valida o feature flag de rollback por redirect. Testes do
# motor técnico ativam explicitamente o modo proxy e garantem que ele não
# devolve a URL externa.
os.environ["DOWNLOAD_DELIVERY_MODE"] = "redirect"

from app import app, db, limiter  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_database():
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        MAIL_SUPPRESS_SEND=True,
    )
    limiter.enabled = False
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client():
    return app.test_client()
