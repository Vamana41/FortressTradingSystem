#!/usr/bin/env python3
"""
Examine OpenAlgo database structure and contents.
"""

import sqlite3
import os

def examine_database(db_path):
    """Examine the structure and contents of a SQLite database."""
    print(f"\n=== Examining {db_path} ===")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        print(f"Found {len(tables)} tables:")
        for table in tables:
            table_name = table[0]
            print(f"\nTable: {table_name}")

            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            print("Columns:")
            for col in columns:
                print(f"  {col[1]} ({col[2]})")

            # Get sample data (first 3 rows)
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3;")
            rows = cursor.fetchall()
            if rows:
                print(f"Sample data ({len(rows)} rows):")
                for i, row in enumerate(rows):
                    print(f"  Row {i+1}: {row}")
            else:
                print("  No data in this table")

        conn.close()

    except Exception as e:
        print(f"Error examining {db_path}: {e}")

def main():
    """Main function."""
    # Check the main OpenAlgo database
    openalgo_db = "openalgo/db/openalgo.db"
    if os.path.exists(openalgo_db):
        examine_database(openalgo_db)
    else:
        print(f"OpenAlgo database not found at {openalgo_db}")

    # Check the backup database
    backup_db = "openalgo_backup_1763227490/openalgo.db"
    if os.path.exists(backup_db):
        examine_database(backup_db)

if __name__ == "__main__":
    main()
