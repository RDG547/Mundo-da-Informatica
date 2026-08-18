"""Migrações aditivas e idempotentes do Mundo da Informática.

Executado no build antes do Gunicorn. Nunca remove ou recria tabelas: somente
cria estruturas ausentes e acrescenta colunas opcionais. Compatível com SQLite
e PostgreSQL por meio da URL configurada em DATABASE_URL.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    inspect,
    text,
)


load_dotenv()
PROJECT_ROOT = Path(__file__).resolve().parent


def get_database_url() -> str:
    configured = (os.environ.get("DATABASE_URL") or "").strip()
    if configured.startswith("postgres://"):
        return configured.replace("postgres://", "postgresql://", 1)
    if configured:
        return configured
    return f"sqlite:///{PROJECT_ROOT / 'instance' / 'site.db'}"


def column_names(connection, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(connection).get_columns(table_name)}


def add_missing_columns(connection, table_name: str, definitions: dict[str, str]) -> int:
    inspector = inspect(connection)
    if not inspector.has_table(table_name):
        return 0

    existing = column_names(connection, table_name)
    applied = 0
    preparer = connection.dialect.identifier_preparer
    quoted_table = preparer.quote(table_name)
    for name, ddl in definitions.items():
        if name in existing:
            continue
        if connection.dialect.name == "postgresql":
            ddl = ddl.replace("DATETIME", "TIMESTAMP")
        quoted_name = preparer.quote(name)
        connection.execute(text(f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_name} {ddl}"))
        print(f"  + {table_name}.{name}")
        applied += 1
    return applied


def create_auxiliary_tables(connection) -> int:
    """Cria tabelas novas sem importar a aplicação nem tocar nas existentes."""
    tables = set(inspect(connection).get_table_names())
    metadata = MetaData()

    # A FK só é declarada quando a tabela de usuários já existe. Em um
    # banco vazio, app.py criará todo o esquema de uma vez no primeiro start.
    if "user" in tables:
        Table("user", metadata, autoload_with=connection)

    webhook_events = Table(
        "payment_webhook_events",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("provider", String(30), nullable=False),
        Column("external_event_id", String(255), nullable=False),
        Column("event_type", String(120)),
        Column("received_at", DateTime, nullable=False),
        Column("processed_at", DateTime),
        Column("status", String(30), nullable=False, server_default="processing"),
        Column("payload_hash", String(64), nullable=False),
        Column("error_message", String(500)),
        UniqueConstraint("provider", "external_event_id", name="uq_webhook_provider_event"),
        extend_existing=True,
    )

    user_id_column = (
        Column("user_id", Integer, ForeignKey("user.id"), nullable=True)
        if "user" in tables
        else Column("user_id", Integer, nullable=True)
    )
    content_requests = Table(
        "content_requests",
        metadata,
        Column("id", Integer, primary_key=True),
        user_id_column,
        Column("request_type", String(30), nullable=False, server_default="suggestion"),
        Column("title", String(200), nullable=False),
        Column("description", Text),
        Column("category", String(100)),
        Column("board_code", String(120)),
        Column("status", String(30), nullable=False, server_default="pending"),
        Column("priority", Integer, nullable=False, server_default="0"),
        Column("admin_notes", Text),
        Column("requester_name", String(120)),
        Column("requester_email", String(255)),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        extend_existing=True,
    )

    created = 0
    for table in (webhook_events, content_requests):
        if table.name not in tables:
            table.create(connection, checkfirst=True)
            print(f"  + tabela {table.name}")
            created += 1
    return created


def update_legacy_public_copy(connection) -> int:
    """Atualiza somente textos-padrão antigos, sem tocar em personalizações."""
    if not inspect(connection).has_table("site_config"):
        return 0

    replacements = {
        "home_hero_title": (
            ("Bem-vindo ao Mundo da Informática",),
            "Encontre o arquivo certo para o reparo.",
        ),
        "home_hero_subtitle": (
            ("Seu portal completo de recursos para técnicos e entusiastas de informática",),
            "BIOS, EC, BoardView, esquemas e recursos técnicos organizados por modelo e placa.",
        ),
        "site_description": (
            (
                "Portal de tecnologia e informática",
                "Seu portal de tecnologia",
                "Seu portal de recursos para técnicos de informática",
            ),
            "Biblioteca técnica de BIOS, EC, BoardView, esquemas e recursos para profissionais de manutenção.",
        ),
        "footer_description": (
            (
                "Seu portal completo de recursos para técnicos e entusiastas de informática, com suporte, downloads e conteúdo especializado.",
            ),
            "Recursos técnicos organizados por modelo e placa para profissionais de manutenção.",
        ),
    }
    applied = 0
    statement = text(
        "UPDATE site_config SET value = :new_value "
        "WHERE key = :config_key AND value = :old_value"
    )
    for config_key, (old_values, new_value) in replacements.items():
        for old_value in old_values:
            result = connection.execute(statement, {
                "config_key": config_key,
                "old_value": old_value,
                "new_value": new_value,
            })
            changed = max(int(result.rowcount or 0), 0)
            if changed:
                print(f"  ~ site_config.{config_key}")
                applied += changed
    return applied


def migrate() -> None:
    database_url = get_database_url()
    if database_url.startswith("sqlite:///"):
        database_file = Path(database_url.removeprefix("sqlite:///"))
        database_file.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(database_url, pool_pre_ping=True)
    safe_url = engine.url.render_as_string(hide_password=True)
    print(f"Aplicando migrações aditivas em {safe_url}")

    applied = 0
    with engine.begin() as connection:
        applied += add_missing_columns(connection, "user", {
            "subscription_end_date": "DATETIME",
            "active_sessions": "INTEGER DEFAULT 0",
            "daily_downloads": "INTEGER DEFAULT 0",
            "download_reset_date": "DATETIME",
            "weekly_downloads": "INTEGER DEFAULT 0",
            "week_reset_date": "DATETIME",
            "preferences": "TEXT",
        })
        applied += add_missing_columns(connection, "favorites", {"position": "INTEGER DEFAULT 0"})
        applied += add_missing_columns(connection, "comments", {"parent_id": "INTEGER"})
        applied += add_missing_columns(connection, "transactions", {
            "abacatepay_charge_id": "VARCHAR(255)",
        })
        applied += add_missing_columns(connection, "category", {
            "color": "VARCHAR(20) DEFAULT '#4a90e2'",
            "show_in_menu": "BOOLEAN DEFAULT TRUE",
            "is_visible": "BOOLEAN NOT NULL DEFAULT TRUE",
        })
        applied += add_missing_columns(connection, "posts", {
            "manufacturer": "VARCHAR(120)",
            "brand": "VARCHAR(120)",
            "model": "VARCHAR(160)",
            "series": "VARCHAR(160)",
            "board_code": "VARCHAR(120)",
            "board_revision": "VARCHAR(80)",
            "platform": "VARCHAR(120)",
            "bios_chip": "VARCHAR(120)",
            "ec_chip": "VARCHAR(120)",
            "me_chip": "VARCHAR(120)",
            "file_type": "VARCHAR(80)",
            "file_extension": "VARCHAR(30)",
            "technical_file_size": "VARCHAR(50)",
            "version": "VARCHAR(80)",
            "sha256": "VARCHAR(64)",
            "last_verified_at": "DATETIME",
            "verification_status": "VARCHAR(30) NOT NULL DEFAULT 'unverified'",
            "compatibility": "TEXT",
            "technical_notes": "TEXT",
        })
        applied += update_legacy_public_copy(connection)
        applied += create_auxiliary_tables(connection)

        if inspect(connection).has_table("posts"):
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_posts_board_code ON posts (board_code)"))

    if applied:
        print(f"Migração concluída: {applied} alteração(ões) aplicada(s).")
    else:
        print("Esquema já atualizado; nenhuma alteração necessária.")


if __name__ == "__main__":
    migrate()
