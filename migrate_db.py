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
        # Check if column exists
        cursor.execute("PRAGMA table_info(user)")
        columns = [info[1] for info in cursor.fetchall()]

        if 'subscription_end_date' not in columns:
            print("Adding subscription_end_date column...")
            cursor.execute("ALTER TABLE user ADD COLUMN subscription_end_date DATETIME")
            conn.commit()
            print("Migration successful!")
        else:
            print("Column subscription_end_date already exists.")

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
