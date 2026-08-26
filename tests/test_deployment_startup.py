from pathlib import Path

from sqlalchemy import create_engine, inspect

import app as app_module
from app import app
from migrate_db import migrate


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_commands_migrate_persistent_database_before_gunicorn():
    render_config = (PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8")
    procfile = (PROJECT_ROOT / "Procfile").read_text(encoding="utf-8")
    gunicorn_config = (PROJECT_ROOT / "gunicorn.conf.py").read_text(encoding="utf-8")

    runtime_command = "python migrate_db.py && gunicorn app:app"
    assert runtime_command in render_config
    assert runtime_command in procfile
    assert "def on_starting(server):" in gunicorn_config
    assert "migrate()" in gunicorn_config


def test_runtime_migration_adds_comment_moderation_status_idempotently(tmp_path, monkeypatch):
    database = tmp_path / "legacy-comments.db"
    database_url = f"sqlite:///{database}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE comments ("
            "id INTEGER PRIMARY KEY, content TEXT, is_approved BOOLEAN DEFAULT 0)"
        )
        connection.exec_driver_sql(
            "INSERT INTO comments (id, content, is_approved) VALUES (1, 'Legado', 0)"
        )

    monkeypatch.setenv("DATABASE_URL", database_url)
    migrate()
    migrate()

    columns = {column["name"] for column in inspect(engine).get_columns("comments")}
    assert "moderation_status" in columns
    with engine.connect() as connection:
        row = connection.exec_driver_sql(
            "SELECT content, moderation_status FROM comments WHERE id = 1"
        ).one()
    assert row == ("Legado", "pending")


def test_home_fallback_uses_existing_error_template(client, monkeypatch):
    original_render_template = app_module.render_template

    def fail_only_home_template(template_name, *args, **kwargs):
        if template_name == "index.html":
            raise RuntimeError("falha simulada na página inicial")
        return original_render_template(template_name, *args, **kwargs)

    monkeypatch.setattr(app_module, "render_template", fail_only_home_template)
    response = client.get("/")

    assert response.status_code == 500
    assert "Não foi possível concluir agora" in response.get_data(as_text=True)
