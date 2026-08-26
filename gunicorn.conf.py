"""Proteção de inicialização para bancos persistentes.

O Gunicorn carrega este arquivo automaticamente a partir da raiz do projeto.
Executar a migração no processo mestre garante que todos os workers recebam
o esquema atualizado, inclusive quando o Start Command do provedor tiver sido
configurado manualmente e ainda contiver apenas ``gunicorn app:app``.
"""


def on_starting(server):
    server.log.info("Verificando migrações do banco antes de iniciar os workers")
    from migrate_db import migrate

    migrate()
