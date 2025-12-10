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

        if migrations_applied:
            conn.commit()
            print("\n✅ All migrations completed successfully!")
        else:
            print("✓ All columns already exist. No migrations needed.")

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
