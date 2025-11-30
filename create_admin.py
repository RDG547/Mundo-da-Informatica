#!/usr/bin/env python3
"""
Script para criar usuário administrador
Execute este script no Shell do Render ou localmente
"""

from app import app, db, User
from datetime import datetime

def create_admin_user():
    """Cria o usuário administrador RD Tech"""

    with app.app_context():
        # Verificar se o usuário já existe
        existing_user = User.query.filter_by(email='rodrigotavaresvieira12@gmail.com').first()

        if existing_user:
            print(f"⚠️  Usuário já existe: {existing_user.username}")
            print(f"   Email: {existing_user.email}")
            print(f"   Role: {existing_user.role}")

            # Atualizar para admin se não for
            if existing_user.role != 'admin':
                existing_user.role = 'admin'
                db.session.commit()
                print("✅ Role atualizada para 'admin'")
            else:
                print("✅ Usuário já é admin")
            return

        # Criar novo usuário admin
        admin_user = User(
            username='rdtech',
            email='rodrigotavaresvieira12@gmail.com',
            name='RD Tech',
            first_name='RD',
            last_name='Tech',
            role='admin',
            plan='vip',  # Plano VIP para admin
            is_active=True,
            is_verified=True,
            date_joined=datetime.utcnow(),
            last_login=datetime.utcnow()
        )

        # Definir senha
        admin_user.set_password('Rodiguin547*#')

        # Adicionar ao banco
        db.session.add(admin_user)
        db.session.commit()

        print("✅ Usuário administrador criado com sucesso!")
        print(f"   Username: {admin_user.username}")
        print(f"   Email: {admin_user.email}")
        print(f"   Nome: {admin_user.name}")
        print(f"   Role: {admin_user.role}")
        print(f"   Plano: {admin_user.plan}")
        print(f"   ID: {admin_user.id}")

if __name__ == '__main__':
    try:
        create_admin_user()
    except Exception as e:
        print(f"❌ Erro ao criar usuário: {e}")
        import traceback
        traceback.print_exc()
