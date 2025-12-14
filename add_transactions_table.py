"""
Script para adicionar a tabela Transaction ao banco de dados.
Executa: python add_transactions_table.py
"""
from app import app, db, Transaction
import sys

def create_transactions_table():
    """Cria a tabela de transações se não existir"""
    with app.app_context():
        try:
            print("🔄 Verificando tabela 'transactions'...")

            # Tentar criar a tabela
            db.create_all()

            # Verificar se foi criada
            inspector = db.inspect(db.engine)
            if 'transactions' in inspector.get_table_names():
                print("✅ Tabela 'transactions' criada/verificada com sucesso!")
                print("\nColunas da tabela:")
                for column in inspector.get_columns('transactions'):
                    print(f"  - {column['name']}: {column['type']}")
                return True
            else:
                print("❌ Erro: Tabela 'transactions' não foi criada")
                return False

        except Exception as e:
            print(f"❌ Erro ao criar tabela: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    print("=" * 60)
    print("ADICIONAR TABELA DE TRANSAÇÕES")
    print("=" * 60)

    success = create_transactions_table()

    if success:
        print("\n✅ Migração concluída com sucesso!")
        print("\n📝 PRÓXIMOS PASSOS:")
        print("1. Configure STRIPE_WEBHOOK_SECRET no seu .env")
        print("2. Configure o webhook no Stripe Dashboard:")
        print("   URL: https://seu-dominio.com/stripe-webhook")
        print("   Eventos: checkout.session.completed, customer.subscription.*")
        print("3. Teste o webhook com o Stripe CLI:")
        print("   stripe listen --forward-to localhost:5000/stripe-webhook")
        sys.exit(0)
    else:
        print("\n❌ Falha na migração!")
        sys.exit(1)
