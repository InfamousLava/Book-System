"""
Inventro Bookstore - One-Click Setup Script
Run this on a fresh computer to get the project running.

Usage: python setup.py
"""

import subprocess
import sys
import os
import shutil

def run(cmd, check=True):
    print(f"\n{'='*50}")
    print(f"Running: {cmd}")
    print('='*50)
    result = subprocess.run(cmd, shell=True, check=check)
    return result.returncode == 0

def main():
    print("""
    ╔══════════════════════════════════════════╗
    ║     📚 Inventro Bookstore Setup         ║
    ║        One-Click Installer              ║
    ╚══════════════════════════════════════════╝
    """)

    # Step 1: Install Python dependencies
    print("\n📦 Step 1: Installing Python dependencies...")
    run(f"{sys.executable} -m pip install -r requirements.txt")

    # Step 2: Create .env from .env.example if it doesn't exist
    if not os.path.exists('.env'):
        if os.path.exists('.env.example'):
            shutil.copy('.env.example', '.env')
            print("\n✅ Created .env from .env.example")
            print("   ⚠️  Edit .env with your database credentials if needed!")
        else:
            print("\n⚠️  No .env.example found. Creating default .env...")
            with open('.env', 'w') as f:
                f.write("FLASK_SECRET_KEY=dev-static-key-12345\n")
                f.write("# DB_HOST=localhost\n")
                f.write("# DB_NAME=postgres\n")
                f.write("# DB_USER=postgres\n")
                f.write("# DB_PASS=admin\n")
            print("   ✅ Default .env created")
    else:
        print("\n✅ .env already exists, skipping...")

    # Step 3: Create uploads directory
    uploads_dir = os.path.join('static', 'uploads', 'reviews')
    os.makedirs(uploads_dir, exist_ok=True)
    print(f"\n📁 Created uploads directory: {uploads_dir}")

    # Step 4: Initialize database
    print("\n🗄️  Step 4: Setting up database...")
    print("   Make sure PostgreSQL is running!")
    print("   Default connection: localhost:5432, user=postgres, password=admin")
    
    try:
        choice = input("\n   Initialize database now? (y/n): ").strip().lower()
        if choice == 'y':
            run(f"{sys.executable} init_db.py")
            print("   ✅ Database initialized!")
        else:
            print("   ⏭️  Skipped. Run 'python init_db.py' later.")
    except EOFError:
        print("   ⏭️  Skipped (non-interactive). Run 'python init_db.py' later.")

    # Done!
    print(f"""
    ╔══════════════════════════════════════════════╗
    ║            ✅ Setup Complete!                ║
    ╠══════════════════════════════════════════════╣
    ║                                              ║
    ║  To start the server:                        ║
    ║    python app.py                             ║
    ║                                              ║
    ║  Then open: http://127.0.0.1:5000            ║
    ║                                              ║
    ║  Default Admin Login:                        ║
    ║    Email: admin@inventro.local               ║
    ║    Pass:  admin123                            ║
    ║                                              ║
    ╚══════════════════════════════════════════════╝
    """)

if __name__ == '__main__':
    main()
