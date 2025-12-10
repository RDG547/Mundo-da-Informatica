"""Script para adicionar campos de controle de downloads diários ao modelo User"""
from app import app, db
from sqlalchemy import text

def add_download_control_fields():
    """Adiciona campos daily_downloads e download_reset_date à tabela user"""
    with app.app_context():
        try:
            print("Verificando campos de controle de downloads...")
            
            # Verificar se as colunas já existem
            check_columns_query = text("""
                SELECT COUNT(*) FROM pragma_table_info('user') 
                WHERE name IN ('daily_downloads', 'download_reset_date')
            """)
            
            result = db.session.execute(check_columns_query)
            columns_exist = result.scalar()
            
            if columns_exist == 2:
                print("✅ Campos já existem no banco de dados.")
                return
            
            print("Adicionando campos de controle de downloads...")
            
            # Adicionar coluna daily_downloads se não existir
            try:
                db.session.execute(text("""
                    ALTER TABLE user ADD COLUMN daily_downloads INTEGER DEFAULT 0
                """))
                print("✅ Campo daily_downloads adicionado.")
            except Exception as e:
                if "duplicate column name" not in str(e).lower():
                    raise
                print("Campo daily_downloads já existe.")
            
            # Adicionar coluna download_reset_date se não existir
            try:
                db.session.execute(text("""
                    ALTER TABLE user ADD COLUMN download_reset_date DATETIME
                """))
                print("✅ Campo download_reset_date adicionado.")
            except Exception as e:
                if "duplicate column name" not in str(e).lower():
                    raise
                print("Campo download_reset_date já existe.")
            
            db.session.commit()
            print("✅ Migração concluída com sucesso!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao adicionar campos: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    print("Iniciando migração do banco de dados...")
    add_download_control_fields()
    print("Migração concluída!")
