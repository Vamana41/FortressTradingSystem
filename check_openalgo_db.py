#!/usr/bin/env python3
"""
Check OpenAlgo Database Structure
"""

import sqlite3
import os

def check_database(db_path):
    """Check database structure"""
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"Database: {db_path}")
        print(f"Tables: {len(tables)}")
        
        for table in tables:
            table_name = table[0]
            print(f"\nTable: {table_name}")
            
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            for column in columns:
                print(f"  {column[1]} ({column[2]})")
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  Rows: {count}")
            
            # Show sample data for small tables
            if count <= 5:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
                rows = cursor.fetchall()
                for row in rows:
                    print(f"  {row}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error checking database: {e}")

def main():
    """Main function"""
    databases = [
        "openalgo/db/openalgo.db",
        "openalgo/openalgo/db/openalgo.db"
    ]
    
    for db_path in databases:
        if os.path.exists(db_path):
            check_database(db_path)
            break
    else:
        print("No OpenAlgo database found")

if __name__ == "__main__":
    main()