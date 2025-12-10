#!/usr/bin/env python3
"""
Script de migração para adicionar campos de controle de downloads semanais.
Adiciona weekly_downloads e week_reset_date ao modelo User.
"""

import sqlite3
import os
from datetime import datetime

# Caminho do banco de dados
DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'site.db')

def migrate_database():
    """Adiciona colunas weekly_downloads e week_reset_date à tabela user"""
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Banco de dados não encontrado em: {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Verificar se as colunas já existem
        cursor.execute("PRAGMA table_info(user)")
        columns = [col[1] for col in cursor.fetchall()]
        
        changes_made = False
        
        # Adicionar weekly_downloads se não existir
        if 'weekly_downloads' not in columns:
            print("📝 Adicionando coluna 'weekly_downloads'...")
            cursor.execute("""
                ALTER TABLE user 
                ADD COLUMN weekly_downloads INTEGER DEFAULT 0
            """)
            changes_made = True
            print("✅ Coluna 'weekly_downloads' adicionada com sucesso!")
        else:
            print("ℹ️  Coluna 'weekly_downloads' já existe")
        
        # Adicionar week_reset_date se não existir
        if 'week_reset_date' not in columns:
            print("📝 Adicionando coluna 'week_reset_date'...")
            cursor.execute("""
                ALTER TABLE user 
                ADD COLUMN week_reset_date DATETIME
            """)
            changes_made = True
            print("✅ Coluna 'week_reset_date' adicionada com sucesso!")
        else:
            print("ℹ️  Coluna 'week_reset_date' já existe")
        
        if changes_made:
            conn.commit()
            print("\n✅ Migração concluída com sucesso!")
            print("📊 Banco de dados atualizado para suportar downloads semanais do Premium")
        else:
            print("\n✅ Banco de dados já está atualizado!")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Erro ao executar migração: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 60)
    print("🔄 MIGRAÇÃO: Adicionar Downloads Semanais")
    print("=" * 60)
    print()
    
    success = migrate_database()
    
    print()
    print("=" * 60)
    if success:
        print("✅ Migração finalizada!")
        print()
        print("📌 Próximos passos:")
        print("   1. Reinicie o servidor Flask")
        print("   2. Teste o sistema de downloads com usuário Premium")
        print("   3. Verifique que o reset acontece aos domingos à meia-noite")
    else:
        print("❌ Migração falhou!")
    print("=" * 60)
