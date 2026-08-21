"""Cria fontes padrão idempotentemente."""

from app import app, ensure_default_content_sources


if __name__ == "__main__":
    with app.app_context():
        ensure_default_content_sources()
    print("Fontes técnicas verificadas.")
