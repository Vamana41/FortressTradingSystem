#!/usr/bin/env python3
"""
Nuclear Option: Complete Database Reset for OpenAlgo - Targeted Version
This will wipe out the OpenAlgo database files.
"""

import os
import shutil
import time

def reset_openalgo_database():
    """Reset OpenAlgo database by removing the database files."""

    print("☢️  Nuclear Option: OpenAlgo Database Reset")
    print("=" * 50)
    print("⚠️  WARNING: This will permanently delete all OpenAlgo data!")
    print("⚠️  All user accounts, API keys, broker credentials, and logs will be lost!")
    print("=" * 50)

    # List of OpenAlgo database files to remove
    db_files = [
        "openalgo/openalgo/db/openalgo.db",
        "openalgo/db/openalgo.db",
        "db/openalgo.db",
        "openalgo/openalgo/db/logs.db",
        "openalgo/db/logs.db",
        "db/logs.db",
        "openalgo/openalgo/db/latency.db",
        "openalgo/db/latency.db",
        "db/latency.db",
        "openalgo/openalgo/db/sandbox.db",
        "openalgo/db/sandbox.db",
        "db/sandbox.db"
    ]

    found_files = []

    # Check which files exist
    print("🔍 Checking for database files...")
    for db_file in db_files:
        if os.path.exists(db_file):
            found_files.append(db_file)
            print(f"  Found: {db_file}")

    if not found_files:
        print("ℹ️  No OpenAlgo database files found - may already be reset")
        return True

    print(f"\n📊 Found {len(found_files)} database file(s) to remove")

    # Ask for confirmation
    response = input(f"\nType 'RESET' to permanently delete these files: ")

    if response != 'RESET':
        print("❌ Database reset cancelled")
        return False

    # Create backup directory
    backup_dir = f"openalgo_backup_{int(time.time())}"
    os.makedirs(backup_dir, exist_ok=True)

    print(f"\n🗂️  Backing up and removing database files...")

    removed_count = 0

    for db_file in found_files:
        try:
            # Create backup
            filename = os.path.basename(db_file)
            backup_path = os.path.join(backup_dir, filename)

            if os.path.exists(db_file):
                shutil.copy2(db_file, backup_path)
                print(f"  💾 Backed up: {filename}")

                # Remove original
                os.remove(db_file)
                print(f"  🗑️  Removed: {db_file}")
                removed_count += 1

        except Exception as e:
            print(f"  ❌ Error with {db_file}: {e}")

    print(f"\n✅ Database reset complete!")
    print(f"📊 Removed {removed_count} database file(s)")
    print(f"💾 Backed up to: {backup_dir}")

    return True

def create_reset_instructions():
    """Create instructions for after the reset."""

    instructions_file = "openalgo_reset_instructions.txt"

    with open(instructions_file, "w") as f:
        f.write("OpenAlgo Database Reset Complete\n")
        f.write("=" * 40 + "\n\n")
        f.write("✅ Database has been successfully reset\n\n")
        f.write("Next Steps:\n")
        f.write("1. Restart OpenAlgo server: python openalgo/app.py\n")
        f.write("2. Go to http://localhost:5000\n")
        f.write("3. Create a new user account\n")
        f.write("4. Configure your broker credentials (Fyers)\n")
        f.write("5. Generate a new API key\n")
        f.write("6. Update Fortress .env file with the new API key\n")
        f.write("7. Test the complete workflow\n\n")
        f.write("Important Notes:\n")
        f.write("- All previous data has been permanently deleted\n")
        f.write("- You will need to reconfigure all broker settings\n")
        f.write("- Previous API keys will no longer work\n")
        f.write("- Database backup was created in case you need to restore\n")

    print(f"📝 Created instructions: {instructions_file}")

def main():
    """Main function."""
    # Reset the database
    success = reset_openalgo_database()

    if success:
        # Create instructions
        create_reset_instructions()

        print(f"\n🎉 OpenAlgo database reset successful!")
        print(f"\n🚀 Ready for next steps:")
        print(f"1. Start OpenAlgo: python openalgo/app.py")
        print(f"2. Create new account at http://localhost:5000")
        print(f"3. Configure Fyers broker credentials")
        print(f"4. Generate new API key")
        print(f"5. Update Fortress configuration")
    else:
        print(f"\n❌ Database reset was cancelled or failed")

if __name__ == "__main__":
    main()
