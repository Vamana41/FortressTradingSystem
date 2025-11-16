#!/usr/bin/env python3
"""
Nuclear Option: Complete Database Reset for OpenAlgo
This will wipe out the entire database and all logs will be lost.
"""

import os
import sys
import glob
import shutil

def find_openalgo_db_files():
    """Find all OpenAlgo database files."""

    print("🔍 Searching for OpenAlgo database files...")

    # Common locations for OpenAlgo database files
    search_patterns = [
        "openalgo/*.db",
        "openalgo/*.sqlite",
        "openalgo/*.sqlite3",
        "openalgo/database/*.db",
        "openalgo/data/*.db",
        "*.db",
        "*.sqlite",
        "*.sqlite3"
    ]

    db_files = []

    for pattern in search_patterns:
        found_files = glob.glob(pattern, recursive=True)
        db_files.extend(found_files)

    # Also check for specific OpenAlgo database names
    specific_names = [
        "openalgo.db",
        "auth.db",
        "user.db",
        "trading.db",
        "logs.db",
        "app.db"
    ]

    for name in specific_names:
        if os.path.exists(name):
            db_files.append(name)

    # Remove duplicates and sort
    db_files = list(set(db_files))
    db_files.sort()

    return db_files

def backup_and_remove_db_files(db_files):
    """Backup and remove database files."""

    print(f"\n🗂️  Found {len(db_files)} database file(s):")

    if not db_files:
        print("❌ No database files found!")
        return False

    for db_file in db_files:
        print(f"  - {db_file}")

    print(f"\n⚠️  WARNING: This will permanently delete all database files!")
    print(f"All user accounts, API keys, broker credentials, and logs will be lost!")

    response = input(f"\nAre you sure you want to proceed? Type 'YES' to continue: ")

    if response != 'YES':
        print("❌ Database reset cancelled")
        return False

    print(f"\n🗑️  Removing database files...")

    backup_dir = "database_backup_" + str(int(os.time()))
    os.makedirs(backup_dir, exist_ok=True)

    for db_file in db_files:
        try:
            # Backup the file first
            backup_path = os.path.join(backup_dir, os.path.basename(db_file))
            shutil.copy2(db_file, backup_path)
            print(f"  💾 Backed up: {db_file} -> {backup_path}")

            # Remove the original file
            os.remove(db_file)
            print(f"  🗑️  Removed: {db_file}")

        except Exception as e:
            print(f"  ❌ Error with {db_file}: {e}")

    print(f"✅ Database files removed and backed up to {backup_dir}")
    return True

def create_reset_marker():
    """Create a reset marker file."""

    with open("openalgo_db_reset.txt", "w") as f:
        f.write(f"Database reset performed at: {os.time()}\n")
        f.write("All OpenAlgo database files have been removed.\n")
        f.write("You can now restart OpenAlgo and create a fresh account.\n")

    print(f"✅ Reset marker created: openalgo_db_reset.txt")

def main():
    """Main function."""
    print("☢️  Nuclear Option: Complete OpenAlgo Database Reset")
    print("=" * 60)
    print("⚠️  WARNING: This will permanently delete all data!")
    print("⚠️  All user accounts, API keys, broker credentials, and logs will be lost!")
    print("=" * 60)

    # Find database files
    db_files = find_openalgo_db_files()

    if db_files:
        # Backup and remove database files
        if backup_and_remove_db_files(db_files):
            # Create reset marker
            create_reset_marker()

            print(f"\n🎉 Database reset complete!")
            print(f"\nNext steps:")
            print(f"1. Restart the OpenAlgo server: python openalgo/app.py")
            print(f"2. Go to http://localhost:5000")
            print(f"3. Create a new user account")
            print(f"4. Configure your broker credentials")
            print(f"5. Generate a new API key")
            print(f"6. Update Fortress configuration with the new API key")
    else:
        print(f"ℹ️  No database files found - OpenAlgo may already be reset")
        print(f"Try restarting the OpenAlgo server and creating a new account")

if __name__ == "__main__":
    main()
