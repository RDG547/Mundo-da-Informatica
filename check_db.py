import sqlite3
import os

# Path to the database
db_path = os.path.join('instance', 'site.db')

def check_schema():
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(user)")
        columns = cursor.fetchall()
        print("Columns in 'user' table:")
        for col in columns:
            print(f"- {col[1]} ({col[2]})")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    check_schema()
