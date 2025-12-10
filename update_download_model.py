"""Script para atualizar o modelo Download com constraint única"""
from app import app, db
from sqlalchemy import text

def add_download_unique_constraint():
    """Adiciona constraint única para evitar downloads duplicados"""
    with app.app_context():
        try:
            # Primeiro, remover duplicatas existentes mantendo apenas o mais recente de cada post
            print("Removendo duplicatas existentes...")
            
            # Query para encontrar e deletar downloads duplicados, mantendo apenas o mais recente
            delete_duplicates_query = text("""
                DELETE FROM download
                WHERE id NOT IN (
                    SELECT MAX(id)
                    FROM download
                    GROUP BY user_id, post_id
                )
            """)
            
            result = db.session.execute(delete_duplicates_query)
            db.session.commit()
            print(f"Removidas {result.rowcount} duplicatas.")
            
            # Verificar se a constraint já existe
            check_constraint_query = text("""
                SELECT COUNT(*)
                FROM sqlite_master
                WHERE type='index' AND name='unique_user_post_download_time'
            """)
            
            result = db.session.execute(check_constraint_query)
            constraint_exists = result.scalar() > 0
            
            if not constraint_exists:
                print("Adicionando constraint única...")
                # Criar a tabela temporária com a nova constraint
                db.session.execute(text("""
                    CREATE TABLE download_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        post_id INTEGER NOT NULL,
                        timestamp DATETIME,
                        FOREIGN KEY (user_id) REFERENCES user (id),
                        FOREIGN KEY (post_id) REFERENCES posts (id),
                        UNIQUE (user_id, post_id, timestamp)
                    )
                """))
                
                # Copiar dados da tabela antiga para a nova
                db.session.execute(text("""
                    INSERT INTO download_new (id, user_id, post_id, timestamp)
                    SELECT id, user_id, post_id, timestamp FROM download
                """))
                
                # Remover a tabela antiga
                db.session.execute(text("DROP TABLE download"))
                
                # Renomear a tabela nova
                db.session.execute(text("ALTER TABLE download_new RENAME TO download"))
                
                db.session.commit()
                print("✅ Constraint única adicionada com sucesso!")
            else:
                print("Constraint única já existe.")
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao adicionar constraint: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    print("Iniciando atualização do modelo Download...")
    add_download_unique_constraint()
    print("Atualização concluída!")
