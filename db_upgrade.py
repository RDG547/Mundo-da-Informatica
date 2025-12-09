# Script para migração de banco de dados
from flask_migrate import Migrate
import sys
import os

# Importar a aplicação principal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import app, db
    print("Aplicação importada com sucesso!")
except Exception as e:
    print(f"Erro ao importar a aplicação: {e}")
    sys.exit(1)

# Inicializar Flask-Migrate
migrate = Migrate(app, db)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'init':
            # Iniciar repositório de migração
            os.system('flask db init')
            print("Repositório de migração inicializado")

        elif sys.argv[1] == 'migrate':
            # Gerar migração
            os.system('flask db migrate -m "Migração automática"')
            print("Migração gerada. Verifique o arquivo e faça ajustes se necessário.")

        elif sys.argv[1] == 'upgrade':
            # Aplicar migração
            os.system('flask db upgrade')
            print("Migração aplicada com sucesso")

        elif sys.argv[1] == 'all':
            # Executar todo o processo
            os.system('flask db init')
            os.system('flask db migrate -m "Migração automática"')
            os.system('flask db upgrade')
            print("Processo completo de migração executado")

        else:
            print("Comando não reconhecido. Use: init, migrate, upgrade ou all")
    else:
        print("Uso: python db_upgrade.py [comando]")
        print("Comandos disponíveis:")
        print("  init     - Inicializa o repositório de migração")
        print("  migrate  - Gera scripts de migração baseado nas alterações dos modelos")
        print("  upgrade  - Aplica migrações pendentes ao banco de dados")
        print("  all      - Executa todo o processo (init, migrate, upgrade)")
