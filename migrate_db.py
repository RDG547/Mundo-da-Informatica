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
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
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
    if "posts" in tables:
        Table("posts", metadata, autoload_with=connection)

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
        Column("requester_plan", String(20), nullable=False, server_default="guest"),
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

    hardware_boards = Table(
        "hardware_boards", metadata,
        Column("id", Integer, primary_key=True),
        Column("manufacturer", String(120)),
        Column("board_manufacturer", String(120)),
        Column("device_model", String(160)),
        Column("device_series", String(160)),
        Column("board_code", String(120), nullable=False),
        Column("normalized_board_code", String(120), nullable=False),
        Column("board_revision", String(80)),
        Column("platform", String(120)),
        Column("chipset", String(120)),
        Column("cpu_family", String(120)),
        Column("super_io", String(120)),
        Column("ec_controller", String(120)),
        Column("notes", Text),
        Column("slug", String(250), nullable=False, unique=True),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        extend_existing=True,
    )
    content_sources = Table(
        "content_sources", metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(120), nullable=False, unique=True),
        Column("provider_type", String(40), nullable=False, server_default="manual"),
        Column("trust_level", String(1), nullable=False, server_default="C"),
        Column("auto_publish", Boolean, nullable=False, server_default="false"),
        Column("metadata_allowed", Boolean, nullable=False, server_default="true"),
        Column("distribution_allowed", Boolean, nullable=False, server_default="false"),
        Column("file_mirroring_allowed", Boolean, nullable=False, server_default="false"),
        Column("attribution_required", Boolean, nullable=False, server_default="false"),
        Column("enabled", Boolean, nullable=False, server_default="true"),
        Column("config_json", Text),
        Column("last_sync_at", DateTime),
        Column("last_error", Text),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        extend_existing=True,
    )
    post_id_resource = (
        Column("post_id", Integer, ForeignKey("posts.id"), nullable=True)
        if "posts" in tables else Column("post_id", Integer, nullable=True)
    )
    technical_resources = Table(
        "technical_resources", metadata,
        Column("id", Integer, primary_key=True),
        post_id_resource,
        Column("board_id", Integer, ForeignKey("hardware_boards.id")),
        Column("resource_type", String(40), nullable=False, server_default="other"),
        Column("title", String(200), nullable=False),
        Column("manufacturer", String(120)),
        Column("model", String(160)),
        Column("part_number", String(160)),
        Column("board_code", String(120)),
        Column("board_revision", String(80)),
        Column("chip", String(120)),
        Column("chip_position", String(50)),
        Column("version", String(80)),
        Column("source_type", String(40), nullable=False, server_default="manual"),
        Column("source_provider", String(120)),
        Column("source_reference", Text),
        Column("external_id", String(255)),
        Column("external_version", String(120)),
        Column("last_synced_at", DateTime),
        Column("verification_status", String(30), nullable=False, server_default="needs_review"),
        Column("verification_date", DateTime),
        Column("license_status", String(40), nullable=False, server_default="unknown"),
        Column("distribution_policy", String(40), nullable=False, server_default="unknown"),
        Column("metadata_json", Text),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        extend_existing=True,
    )
    post_id_file = (
        Column("post_id", Integer, ForeignKey("posts.id"), nullable=True)
        if "posts" in tables else Column("post_id", Integer, nullable=True)
    )
    technical_files = Table(
        "technical_files", metadata,
        Column("id", Integer, primary_key=True),
        Column("resource_id", Integer, ForeignKey("technical_resources.id")),
        post_id_file,
        Column("display_filename", String(200), nullable=False),
        Column("original_filename", String(255)),
        Column("file_type", String(80), nullable=False, server_default="Arquivo"),
        Column("chip", String(120)),
        Column("chip_position", String(50)),
        Column("version", String(80)),
        Column("extension", String(30)),
        Column("mime_type", String(120)),
        Column("file_size", BigInteger),
        Column("sha256", String(64)),
        Column("storage_provider", String(40), nullable=False, server_default="http"),
        Column("provider_file_id", String(255)),
        Column("provider_url", Text),
        Column("provider_direct_url", Text),
        Column("provider_metadata_json", Text),
        Column("source_provider", String(120)),
        Column("source_url", Text),
        Column("link_status", String(30), nullable=False, server_default="unchecked"),
        Column("last_link_check_at", DateTime),
        Column("last_link_http_status", Integer),
        Column("verification_status", String(30), nullable=False, server_default="needs_review"),
        Column("is_active", Boolean, nullable=False, server_default="true"),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        extend_existing=True,
    )
    created_by_column = (
        Column("created_by", Integer, ForeignKey("user.id"))
        if "user" in tables else Column("created_by", Integer)
    )
    import_jobs = Table(
        "import_jobs", metadata,
        Column("id", Integer, primary_key=True),
        Column("job_type", String(40), nullable=False),
        Column("source", String(120), nullable=False, server_default="admin"),
        Column("status", String(30), nullable=False, server_default="pending"),
        Column("automation_mode", String(20), nullable=False, server_default="semi"),
        Column("total_items", Integer, nullable=False, server_default="0"),
        Column("processed_items", Integer, nullable=False, server_default="0"),
        Column("success_count", Integer, nullable=False, server_default="0"),
        Column("duplicate_count", Integer, nullable=False, server_default="0"),
        Column("review_count", Integer, nullable=False, server_default="0"),
        Column("error_count", Integer, nullable=False, server_default="0"),
        created_by_column,
        Column("created_at", DateTime, nullable=False),
        Column("started_at", DateTime),
        Column("finished_at", DateTime),
        Column("log_summary", Text),
        extend_existing=True,
    )
    reviewed_by_column = (
        Column("reviewed_by", Integer, ForeignKey("user.id"))
        if "user" in tables else Column("reviewed_by", Integer)
    )
    import_items = Table(
        "import_items", metadata,
        Column("id", Integer, primary_key=True),
        Column("job_id", Integer, ForeignKey("import_jobs.id"), nullable=False),
        Column("source_name", String(255)),
        Column("status", String(30), nullable=False, server_default="pending_review"),
        Column("confidence", Integer, nullable=False, server_default="0"),
        Column("raw_data_json", Text),
        Column("normalized_data_json", Text),
        Column("temp_path", Text),
        Column("sha256", String(64)),
        Column("duplicate_file_id", Integer, ForeignKey("technical_files.id")),
        Column("technical_file_id", Integer, ForeignKey("technical_files.id")),
        Column("resource_id", Integer, ForeignKey("technical_resources.id")),
        Column("post_id", Integer),
        Column("error_message", Text),
        Column("decision_reason", Text),
        Column("published_automatically", Boolean, nullable=False, server_default="false"),
        reviewed_by_column,
        Column("reviewed_at", DateTime),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        extend_existing=True,
    )
    contribution_user_column = (
        Column("user_id", Integer, ForeignKey("user.id"), nullable=False)
        if "user" in tables else Column("user_id", Integer, nullable=False)
    )
    file_contributions = Table(
        "file_contributions", metadata,
        Column("id", Integer, primary_key=True),
        contribution_user_column,
        Column("status", String(30), nullable=False, server_default="pending_review"),
        Column("original_filename", String(255), nullable=False),
        Column("temp_path", Text, nullable=False),
        Column("sha256", String(64), nullable=False),
        Column("title", String(200)),
        Column("board_code", String(120)),
        Column("notes", Text),
        Column("import_item_id", Integer, ForeignKey("import_items.id")),
        Column("reviewed_by", Integer),
        Column("reviewed_at", DateTime),
        Column("created_at", DateTime, nullable=False),
        extend_existing=True,
    )
    datasheet_provider_configs = Table(
        "datasheet_provider_configs", metadata,
        Column("id", Integer, primary_key=True),
        Column("provider_name", String(80), nullable=False, unique=True),
        Column("display_name", String(120), nullable=False),
        Column("provider_kind", String(30), nullable=False, server_default="api"),
        Column("enabled", Boolean, nullable=False, server_default="false"),
        Column("mode", String(30), nullable=False, server_default="semi_automatic"),
        Column("priority", Integer, nullable=False, server_default="100"),
        Column("api_enabled", Boolean, nullable=False, server_default="false"),
        Column("html_discovery_enabled", Boolean, nullable=False, server_default="false"),
        Column("search_strategy", String(30), nullable=False, server_default="priority_fallback"),
        Column("auto_publish_threshold", Float, nullable=False, server_default="0.95"),
        Column("max_items_per_job", Integer, nullable=False, server_default="25"),
        Column("interval_seconds", Float, nullable=False, server_default="1.0"),
        Column("fallback_enabled", Boolean, nullable=False, server_default="true"),
        Column("retention_days", Integer, nullable=False, server_default="30"),
        Column("metadata_persistence_allowed", Boolean, nullable=False, server_default="false"),
        Column("public_republish_allowed", Boolean, nullable=False, server_default="false"),
        Column("pdf_reference_allowed", Boolean, nullable=False, server_default="false"),
        Column("pdf_stream_allowed", Boolean, nullable=False, server_default="false"),
        Column("pdf_mirror_allowed", Boolean, nullable=False, server_default="false"),
        Column("attribution_required", Boolean, nullable=False, server_default="true"),
        Column("written_permission_confirmed", Boolean, nullable=False, server_default="false"),
        Column("source_policy_allows_html_discovery", Boolean, nullable=False, server_default="false"),
        Column("permission_reference", String(500)),
        Column("permission_notes", Text),
        Column("robots_allowed", Boolean, nullable=False, server_default="false"),
        Column("robots_last_checked_at", DateTime),
        Column("terms_last_checked_at", DateTime),
        Column("terms_version_or_date", String(120)),
        Column("requests_per_minute", Integer, nullable=False, server_default="30"),
        Column("requests_per_hour", Integer, nullable=False, server_default="500"),
        Column("requests_per_day", Integer, nullable=False, server_default="5000"),
        Column("requests_per_month", Integer, nullable=False, server_default="0"),
        Column("timeout_seconds", Float, nullable=False, server_default="15"),
        Column("retry_limit", Integer, nullable=False, server_default="2"),
        Column("provider_status", String(40), nullable=False, server_default="not_configured"),
        Column("consecutive_failures", Integer, nullable=False, server_default="0"),
        Column("circuit_open_until", DateTime),
        Column("credits_remaining", Integer),
        Column("last_credit_check_at", DateTime),
        Column("last_success_at", DateTime),
        Column("last_error_at", DateTime),
        Column("last_error_message", Text),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        extend_existing=True,
    )
    electronic_components = Table(
        "electronic_components", metadata,
        Column("id", Integer, primary_key=True),
        Column("manufacturer", String(160)),
        Column("normalized_manufacturer", String(160), nullable=False, server_default=""),
        Column("part_number", String(160), nullable=False),
        Column("normalized_part_number", String(160), nullable=False),
        Column("title_ptbr", String(300), nullable=False),
        Column("description_ptbr", Text),
        Column("category", String(120)),
        Column("subcategory", String(120)),
        Column("package", String(120)),
        Column("lifecycle_status", String(80)),
        Column("confidence", Float, nullable=False, server_default="0"),
        Column("verification_status", String(30), nullable=False, server_default="needs_review"),
        Column("specifications_json", Text),
        Column("slug", String(200), nullable=False, unique=True),
        Column("is_published", Boolean, nullable=False, server_default="false"),
        Column("publication_mode", String(20), nullable=False, server_default="manual"),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        Column("published_at", DateTime),
        UniqueConstraint("normalized_manufacturer", "normalized_part_number", name="uq_component_identity"),
        extend_existing=True,
    )
    component_alias_confirmed_by = (
        Column("confirmed_by", Integer, ForeignKey("user.id"))
        if "user" in tables else Column("confirmed_by", Integer)
    )
    component_aliases = Table(
        "component_aliases", metadata,
        Column("id", Integer, primary_key=True),
        Column("component_id", Integer, ForeignKey("electronic_components.id"), nullable=False),
        Column("alias", String(160), nullable=False),
        Column("normalized_alias", String(160), nullable=False, unique=True),
        component_alias_confirmed_by,
        Column("created_at", DateTime, nullable=False),
        extend_existing=True,
    )
    component_source_records = Table(
        "component_source_records", metadata,
        Column("id", Integer, primary_key=True),
        Column("component_id", Integer, ForeignKey("electronic_components.id"), nullable=False),
        Column("provider", String(80), nullable=False),
        Column("external_id", String(255)),
        Column("field_name", String(120), nullable=False),
        Column("field_value_hash", String(64), nullable=False),
        Column("license_policy", String(80), nullable=False, server_default="metadata_only"),
        Column("first_seen_at", DateTime, nullable=False),
        Column("last_seen_at", DateTime, nullable=False),
        Column("confidence", Float, nullable=False, server_default="0"),
        Column("persisted_value_allowed", Boolean, nullable=False, server_default="false"),
        extend_existing=True,
    )
    datasheet_documents = Table(
        "datasheet_documents", metadata,
        Column("id", Integer, primary_key=True),
        Column("component_id", Integer, ForeignKey("electronic_components.id"), nullable=False),
        Column("document_title", String(300), nullable=False),
        Column("revision", String(80)),
        Column("document_date", String(40)),
        Column("language", String(20)),
        Column("pages", Integer),
        Column("source_provider", String(80), nullable=False),
        Column("source_reference", Text),
        Column("distribution_policy", String(50), nullable=False, server_default="metadata_only"),
        Column("pdf_storage_provider", String(40)),
        Column("pdf_internal_reference", Text),
        Column("sha256", String(64)),
        Column("file_size", BigInteger),
        Column("verification_status", String(30), nullable=False, server_default="needs_review"),
        Column("is_active", Boolean, nullable=False, server_default="true"),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        extend_existing=True,
    )
    board_components = Table(
        "board_components", metadata,
        Column("id", Integer, primary_key=True),
        Column("board_id", Integer, ForeignKey("hardware_boards.id"), nullable=False),
        Column("component_id", Integer, ForeignKey("electronic_components.id"), nullable=False),
        Column("reference_designator", String(50)),
        Column("source_resource_id", Integer, ForeignKey("technical_resources.id")),
        Column("verified", Boolean, nullable=False, server_default="false"),
        Column("created_at", DateTime, nullable=False),
        UniqueConstraint("board_id", "component_id", "reference_designator", name="uq_board_component_ref"),
        extend_existing=True,
    )
    datasheet_queue_requested_by = (
        Column("requested_by", Integer, ForeignKey("user.id"))
        if "user" in tables else Column("requested_by", Integer)
    )
    datasheet_queue_reviewed_by = (
        Column("reviewed_by", Integer, ForeignKey("user.id"))
        if "user" in tables else Column("reviewed_by", Integer)
    )
    datasheet_import_queue = Table(
        "datasheet_import_queue", metadata,
        Column("id", Integer, primary_key=True),
        Column("part_number", String(160), nullable=False),
        Column("normalized_part_number", String(160), nullable=False),
        Column("manufacturer_hint", String(160)),
        Column("source_board_id", Integer, ForeignKey("hardware_boards.id")),
        Column("source_resource_id", Integer, ForeignKey("technical_resources.id")),
        Column("priority", Integer, nullable=False, server_default="0"),
        Column("status", String(40), nullable=False, server_default="queued"),
        Column("requested_strategy", String(30), nullable=False, server_default="priority_fallback"),
        Column("attempt_count", Integer, nullable=False, server_default="0"),
        Column("best_confidence", Float, nullable=False, server_default="0"),
        Column("selected_provider", String(80)),
        Column("candidate_count", Integer, nullable=False, server_default="0"),
        Column("result_json", Text),
        Column("conflict_json", Text),
        Column("component_id", Integer, ForeignKey("electronic_components.id")),
        datasheet_queue_requested_by,
        datasheet_queue_reviewed_by,
        Column("admin_decision", String(40)),
        Column("created_at", DateTime, nullable=False),
        Column("started_at", DateTime),
        Column("finished_at", DateTime),
        Column("error_message", Text),
        extend_existing=True,
    )
    datasheet_demands = Table(
        "datasheet_demands", metadata,
        Column("id", Integer, primary_key=True),
        Column("normalized_query", String(160), nullable=False, unique=True),
        Column("display_query", String(160), nullable=False),
        Column("request_count", Integer, nullable=False, server_default="1"),
        Column("last_requested_at", DateTime, nullable=False),
        extend_existing=True,
    )
    datasheet_provider_events = Table(
        "datasheet_provider_events", metadata,
        Column("id", Integer, primary_key=True),
        Column("provider", String(80), nullable=False),
        Column("normalized_query", String(160), nullable=False),
        Column("status", String(40), nullable=False),
        Column("result_count", Integer, nullable=False, server_default="0"),
        Column("selected", Boolean, nullable=False, server_default="false"),
        Column("exact_match", Boolean, nullable=False, server_default="false"),
        Column("confidence", Float),
        Column("conflict", Boolean, nullable=False, server_default="false"),
        Column("duration_ms", Integer, nullable=False, server_default="0"),
        Column("message", String(500)),
        Column("created_at", DateTime, nullable=False),
        extend_existing=True,
    )

    created = 0
    tables_to_create = [
        webhook_events, content_requests, hardware_boards, content_sources,
        technical_resources, technical_files, import_jobs, import_items,
        file_contributions, datasheet_provider_configs, electronic_components,
        component_aliases, component_source_records, datasheet_documents,
        board_components, datasheet_import_queue, datasheet_demands,
        datasheet_provider_events,
    ]
    for table in tables_to_create:
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
            (
                "Encontre o arquivo certo para o reparo.",
                "Bem-vindo ao Mundo da Informática",
            ),
            "Encontre o arquivo certo para o reparo!",
        ),
        "home_hero_subtitle": (
            (
                "Seu portal completo de recursos para técnicos e entusiastas de informática",
                "Recursos essenciais para técnicos",
            ),
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
        applied += add_missing_columns(connection, "content_requests", {
            "requester_plan": "VARCHAR(20) NOT NULL DEFAULT 'guest'",
        })
        if inspect(connection).has_table("content_requests") and inspect(connection).has_table("user"):
            connection.execute(text(
                'UPDATE content_requests '
                'SET requester_plan = COALESCE((SELECT plan FROM "user" WHERE "user".id = content_requests.user_id), \'guest\') '
                "WHERE user_id IS NOT NULL AND (requester_plan IS NULL OR requester_plan = 'guest')"
            ))
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
        applied += create_auxiliary_tables(connection)
        applied += add_missing_columns(connection, "datasheet_provider_configs", {
            "requests_per_month": "INTEGER NOT NULL DEFAULT 0",
        })
        applied += add_missing_columns(connection, "technical_resources", {
            "external_id": "VARCHAR(255)",
            "external_version": "VARCHAR(120)",
            "last_synced_at": "DATETIME",
        })
        applied += add_missing_columns(connection, "technical_files", {
            "last_link_http_status": "INTEGER",
        })
        applied += add_missing_columns(connection, "file_contributions", {
            "import_item_id": "INTEGER",
        })
        applied += add_missing_columns(connection, "import_items", {
            "published_automatically": "BOOLEAN NOT NULL DEFAULT FALSE",
        })
        applied += add_missing_columns(connection, "download", {
            "technical_file_id": "INTEGER",
            "resource_id": "INTEGER",
            "plan_snapshot": "VARCHAR(20)",
        })
        applied += update_legacy_public_copy(connection)
        if inspect(connection).has_table("content_sources"):
            removed_api_sources = connection.execute(text(
                "DELETE FROM content_sources WHERE provider_type = 'api'"
            ))
            if removed_api_sources.rowcount and removed_api_sources.rowcount > 0:
                applied += removed_api_sources.rowcount

        if inspect(connection).has_table("posts"):
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_posts_board_code ON posts (board_code)"))
        for table_name, statement in (
            ("hardware_boards", "CREATE INDEX IF NOT EXISTS ix_hardware_boards_normalized_board_code ON hardware_boards (normalized_board_code)"),
            ("technical_resources", "CREATE INDEX IF NOT EXISTS ix_technical_resources_board_code ON technical_resources (board_code)"),
            ("technical_resources", "CREATE INDEX IF NOT EXISTS ix_technical_resources_external_id ON technical_resources (external_id)"),
            ("technical_files", "CREATE INDEX IF NOT EXISTS ix_technical_files_sha256 ON technical_files (sha256)"),
            ("import_items", "CREATE INDEX IF NOT EXISTS ix_import_items_status ON import_items (status)"),
            ("file_contributions", "CREATE INDEX IF NOT EXISTS ix_file_contributions_status ON file_contributions (status)"),
            ("file_contributions", "CREATE INDEX IF NOT EXISTS ix_file_contributions_import_item_id ON file_contributions (import_item_id)"),
            ("datasheet_provider_configs", "CREATE INDEX IF NOT EXISTS ix_datasheet_provider_name ON datasheet_provider_configs (provider_name)"),
            ("electronic_components", "CREATE INDEX IF NOT EXISTS ix_component_part_number ON electronic_components (normalized_part_number)"),
            ("electronic_components", "CREATE INDEX IF NOT EXISTS ix_component_published ON electronic_components (is_published)"),
            ("datasheet_import_queue", "CREATE INDEX IF NOT EXISTS ix_datasheet_queue_status_priority ON datasheet_import_queue (status, priority)"),
            ("datasheet_provider_events", "CREATE INDEX IF NOT EXISTS ix_datasheet_event_provider_created ON datasheet_provider_events (provider, created_at)"),
            ("datasheet_demands", "CREATE INDEX IF NOT EXISTS ix_datasheet_demand_count ON datasheet_demands (request_count)"),
        ):
            if inspect(connection).has_table(table_name):
                connection.execute(text(statement))

    if applied:
        print(f"Migração concluída: {applied} alteração(ões) aplicada(s).")
    else:
        print("Esquema já atualizado; nenhuma alteração necessária.")


if __name__ == "__main__":
    migrate()
