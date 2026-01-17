#!/usr/bin/env python3
"""
Script de migração para adicionar campos de permissões de download
"""
import sys
import os

# Adicionar o diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text

def migrate_database():
    """Adiciona novos campos à tabela user"""
    with app.app_context():
        try:
            print("Iniciando migração do banco de dados...")

            # Verificar se as colunas já existem
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('user')]

            # Adicionar coluna can_download
            if 'can_download' not in columns:
                print("Adicionando coluna 'can_download'...")
                db.session.execute(text(
                    'ALTER TABLE user ADD COLUMN can_download BOOLEAN DEFAULT 1'
                ))
                print("✓ Coluna 'can_download' adicionada")
            else:
                print("⊘ Coluna 'can_download' já existe")

            # Adicionar coluna custom_daily_limit
            if 'custom_daily_limit' not in columns:
                print("Adicionando coluna 'custom_daily_limit'...")
                db.session.execute(text(
                    'ALTER TABLE user ADD COLUMN custom_daily_limit INTEGER NULL'
                ))
                print("✓ Coluna 'custom_daily_limit' adicionada")
            else:
                print("⊘ Coluna 'custom_daily_limit' já existe")

            # Adicionar coluna custom_weekly_limit
            if 'custom_weekly_limit' not in columns:
                print("Adicionando coluna 'custom_weekly_limit'...")
                db.session.execute(text(
                    'ALTER TABLE user ADD COLUMN custom_weekly_limit INTEGER NULL'
                ))
                print("✓ Coluna 'custom_weekly_limit' adicionada")
            else:
                print("⊘ Coluna 'custom_weekly_limit' já existe")

            # Commit das alterações
            db.session.commit()
            print("\n✅ Migração concluída com sucesso!")
            print("\nNovos campos adicionados à tabela 'user':")
            print("  - can_download: Controla se o usuário pode fazer downloads")
            print("  - custom_daily_limit: Limite diário personalizado de downloads")
            print("  - custom_weekly_limit: Limite semanal personalizado de downloads")

        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Erro durante a migração: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

        return True

if __name__ == '__main__':
    success = migrate_database()
    sys.exit(0 if success else 1)
