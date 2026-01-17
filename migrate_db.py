import sqlite3
import os

# Path to the database
db_path = os.path.join('instance', 'site.db')

def migrate():
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if columns exist
        cursor.execute("PRAGMA table_info(user)")
        columns = [info[1] for info in cursor.fetchall()]

        migrations_applied = False

        if 'subscription_end_date' not in columns:
            print("Adding subscription_end_date column...")
            cursor.execute("ALTER TABLE user ADD COLUMN subscription_end_date DATETIME")
            migrations_applied = True
            print("✓ subscription_end_date column added")

        if 'active_sessions' not in columns:
            print("Adding active_sessions column...")
            cursor.execute("ALTER TABLE user ADD COLUMN active_sessions INTEGER DEFAULT 0")
            migrations_applied = True
            print("✓ active_sessions column added")

        # Novas colunas para controle de downloads
        if 'daily_downloads' not in columns:
            print("Adding daily_downloads column...")
            cursor.execute("ALTER TABLE user ADD COLUMN daily_downloads INTEGER DEFAULT 0")
            migrations_applied = True
            print("✓ daily_downloads column added")

        if 'download_reset_date' not in columns:
            print("Adding download_reset_date column...")
            cursor.execute("ALTER TABLE user ADD COLUMN download_reset_date DATETIME")
            migrations_applied = True
            print("✓ download_reset_date column added")

        if 'weekly_downloads' not in columns:
            print("Adding weekly_downloads column...")
            cursor.execute("ALTER TABLE user ADD COLUMN weekly_downloads INTEGER DEFAULT 0")
            migrations_applied = True
            print("✓ weekly_downloads column added")

        if 'week_reset_date' not in columns:
            print("Adding week_reset_date column...")
            cursor.execute("ALTER TABLE user ADD COLUMN week_reset_date DATETIME")
            migrations_applied = True
            print("✓ week_reset_date column added")

        # Verificar se tabela transactions existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
        transactions_table_exists = cursor.fetchone() is not None

        if not transactions_table_exists:
            print("Creating transactions table...")
            cursor.execute("""
                CREATE TABLE transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    payment_gateway VARCHAR(20) NOT NULL DEFAULT 'stripe',
                    stripe_session_id VARCHAR(255) NULL,
                    stripe_customer_id VARCHAR(255) NULL,
                    stripe_subscription_id VARCHAR(255) NULL,
                    stripe_payment_intent_id VARCHAR(255) NULL,
                    abacatepay_billing_id VARCHAR(255) NULL,
                    abacatepay_payment_url TEXT NULL,
                    abacatepay_qr_code TEXT NULL,
                    abacatepay_pix_code TEXT NULL,
                    plan_type VARCHAR(20) NOT NULL,
                    amount INTEGER NOT NULL,
                    currency VARCHAR(3) DEFAULT 'brl',
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    paid_at DATETIME NULL,
                    FOREIGN KEY (user_id) REFERENCES user (id)
                )
            """)
            migrations_applied = True
            print("✓ transactions table created")
        else:
            # Se a tabela já existe mas foi criada errada, precisamos recriar
            print("Checking if transactions table needs to be recreated...")
            cursor.execute("PRAGMA table_info(transactions)")
            trans_columns = {col[1]: col for col in cursor.fetchall()}

            # Verificar se stripe_session_id está como NOT NULL (notnull=1)
            if 'stripe_session_id' in trans_columns and trans_columns['stripe_session_id'][3] == 1:
                print("Recreating transactions table with correct NULL constraints...")

                # Backup dos dados existentes
                cursor.execute("SELECT * FROM transactions")
                existing_data = cursor.fetchall()

                # Dropar e recriar
                cursor.execute("DROP TABLE transactions")
                cursor.execute("""
                    CREATE TABLE transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        payment_gateway VARCHAR(20) NOT NULL DEFAULT 'stripe',
                        stripe_session_id VARCHAR(255) NULL,
                        stripe_customer_id VARCHAR(255) NULL,
                        stripe_subscription_id VARCHAR(255) NULL,
                        stripe_payment_intent_id VARCHAR(255) NULL,
                        abacatepay_billing_id VARCHAR(255) NULL,
                        abacatepay_payment_url TEXT NULL,
                        abacatepay_qr_code TEXT NULL,
                        abacatepay_pix_code TEXT NULL,
                        plan_type VARCHAR(20) NOT NULL,
                        amount INTEGER NOT NULL,
                        currency VARCHAR(3) DEFAULT 'brl',
                        status VARCHAR(20) DEFAULT 'pending',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        paid_at DATETIME NULL,
                        FOREIGN KEY (user_id) REFERENCES user (id)
                    )
                """)

                # Restaurar dados se houver
                if existing_data:
                    cursor.executemany(
                        "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        existing_data
                    )

                migrations_applied = True
                print("✓ transactions table recreated with correct constraints")

        if migrations_applied:
            conn.commit()
            print("\n✅ All migrations completed successfully!")
        else:
            print("✓ All columns already exist. No migrations needed.")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
