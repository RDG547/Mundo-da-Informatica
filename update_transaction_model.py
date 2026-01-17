"""
Script de migração para adicionar suporte ao Abacate Pay nas transações.

Executar: python update_transaction_model.py
"""

import os
import sys

# Adicionar o diretório do projeto ao path
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from app import app, db
from sqlalchemy import text, inspect

def column_exists(table_name, column_name):
    """Verifica se uma coluna existe na tabela"""
    try:
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def migrate_database():
    """Adiciona campos do Abacate Pay ao modelo Transaction"""
    with app.app_context():
        try:
            print("Verificando estrutura da tabela transactions...")

            # Adicionar campo payment_gateway
            if not column_exists('transactions', 'payment_gateway'):
                try:
                    db.session.execute(text("""
                        ALTER TABLE transactions
                        ADD COLUMN payment_gateway VARCHAR(20) DEFAULT 'stripe' NOT NULL
                    """))
                    db.session.commit()
                    print("✓ Campo payment_gateway adicionado")
                except Exception as e:
                    print(f"Erro ao adicionar payment_gateway: {e}")
                    db.session.rollback()
            else:
                print("Campo payment_gateway já existe")

            # Adicionar campo abacatepay_billing_id (sem UNIQUE para SQLite)
            if not column_exists('transactions', 'abacatepay_billing_id'):
                try:
                    db.session.execute(text("""
                        ALTER TABLE transactions
                        ADD COLUMN abacatepay_billing_id VARCHAR(255)
                    """))
                    db.session.commit()
                    print("✓ Campo abacatepay_billing_id adicionado")
                except Exception as e:
                    print(f"Erro ao adicionar abacatepay_billing_id: {e}")
                    db.session.rollback()
            else:
                print("Campo abacatepay_billing_id já existe")

            # Adicionar campo abacatepay_payment_url
            if not column_exists('transactions', 'abacatepay_payment_url'):
                try:
                    db.session.execute(text("""
                        ALTER TABLE transactions
                        ADD COLUMN abacatepay_payment_url TEXT
                    """))
                    db.session.commit()
                    print("✓ Campo abacatepay_payment_url adicionado")
                except Exception as e:
                    print(f"Erro ao adicionar abacatepay_payment_url: {e}")
                    db.session.rollback()
            else:
                print("Campo abacatepay_payment_url já existe")

            # Adicionar campo abacatepay_qr_code
            if not column_exists('transactions', 'abacatepay_qr_code'):
                try:
                    db.session.execute(text("""
                        ALTER TABLE transactions
                        ADD COLUMN abacatepay_qr_code TEXT
                    """))
                    db.session.commit()
                    print("✓ Campo abacatepay_qr_code adicionado")
                except Exception as e:
                    print(f"Erro ao adicionar abacatepay_qr_code: {e}")
                    db.session.rollback()
            else:
                print("Campo abacatepay_qr_code já existe")

            # Adicionar campo abacatepay_pix_code
            if not column_exists('transactions', 'abacatepay_pix_code'):
                try:
                    db.session.execute(text("""
                        ALTER TABLE transactions
                        ADD COLUMN abacatepay_pix_code TEXT
                    """))
                    db.session.commit()
                    print("✓ Campo abacatepay_pix_code adicionado")
                except Exception as e:
                    print(f"Erro ao adicionar abacatepay_pix_code: {e}")
                    db.session.rollback()
            else:
                print("Campo abacatepay_pix_code já existe")

            # SQLite não suporta ALTER COLUMN - seria necessário recriar a tabela
            # Mas em produção com PostgreSQL do Render isso não será necessário
            print("\nNOTA: Para remover NOT NULL de stripe_session_id no SQLite, é necessário recriar a tabela.")
            print("No PostgreSQL (Render), isso pode ser feito com ALTER COLUMN.")

            print("\n✓ Migração concluída com sucesso!")

        except Exception as e:
            db.session.rollback()
            print(f"\n✗ Erro durante a migração: {e}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == '__main__':
    print("="*50)
    print("Migração do Banco de Dados")
    print("Adicionando suporte ao Abacate Pay")
    print("="*50)
    print()
    migrate_database()
    print()
    print("="*50)
