"""Project Audit Script - Scans the database and checks for issues"""
import db
from psycopg2.extras import RealDictCursor

conn = db.get_db_connection()
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=" * 60)
print("INVENTRO BOOKSTORE - PROJECT AUDIT")
print("=" * 60)

# 1. Check tables
print("\n1. DATABASE TABLES")
print("-" * 40)
cur.execute("""
    SELECT table_name FROM information_schema.tables 
    WHERE table_schema = 'public' ORDER BY table_name
""")
tables = [r['table_name'] for r in cur.fetchall()]
for t in tables:
    cur.execute(f"SELECT COUNT(*) as cnt FROM {t}")
    cnt = cur.fetchone()['cnt']
    print(f"  - {t}: {cnt} rows")

# 2. Check users table schema
print("\n2. USERS TABLE SCHEMA")
print("-" * 40)
cur.execute("""
    SELECT column_name, data_type, is_nullable 
    FROM information_schema.columns 
    WHERE table_name = 'users' ORDER BY ordinal_position
""")
for col in cur.fetchall():
    print(f"  {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")

# 3. Check for schema mismatches
print("\n3. SCHEMA ISSUES")
print("-" * 40)
issues = []

# Check if users has email column
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='email'")
if not cur.fetchone():
    issues.append("users table missing 'email' column")

# Check if users has google_id column
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='google_id'")
if not cur.fetchone():
    issues.append("users table missing 'google_id' column (Google OAuth won't work)")

# Check if orders table exists
if 'orders' not in tables:
    issues.append("orders table is missing!")
else:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='orders' AND column_name='tracking_number'")
    if not cur.fetchone():
        issues.append("orders table missing 'tracking_number' column")

# Check if customers has user_id
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='customers' AND column_name='user_id'")
if not cur.fetchone():
    issues.append("customers table missing 'user_id' column (customer login won't work)")

if issues:
    for issue in issues:
        print(f"  [!] {issue}")
else:
    print("  [OK] No schema issues detected")

# 4. Check user roles
print("\n4. USER ROLES")
print("-" * 40)
cur.execute("SELECT role, COUNT(*) as cnt FROM users GROUP BY role")
for r in cur.fetchall():
    print(f"  {r['role']}: {r['cnt']} users")

# 5. Check orders
print("\n5. ORDER STATUS SUMMARY")
print("-" * 40)
if 'orders' in tables:
    cur.execute("SELECT status, COUNT(*) as cnt FROM orders GROUP BY status")
    for r in cur.fetchall():
        print(f"  {r['status']}: {r['cnt']} orders")
else:
    print("  [!] Orders table not found")

print("\n" + "=" * 60)
cur.close()
conn.close()
