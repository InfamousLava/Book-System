import requests
import time

BASE = "http://127.0.0.1:5000"

def test(name, method, url, expected, json_data=None, session=None):
    s = session or requests
    try:
        if method == 'GET':
            r = s.get(f"{BASE}{url}", timeout=5, allow_redirects=False)
        else:
            r = s.post(f"{BASE}{url}", json=json_data, timeout=5)
        ok = r.status_code == expected
        detail = ""
        if not ok:
            try: detail = r.json().get('error', r.text[:80])
            except: detail = r.text[:80]
        print(f"[{'PASS' if ok else 'FAIL'}] {name} -> {r.status_code} (exp {expected}) {detail}")
        return r, ok
    except Exception as e:
        print(f"[ERROR] {name} -> {e}")
        return None, False

passed = failed = 0
def track(result):
    global passed, failed
    if result[1]: passed += 1
    else: failed += 1
    return result[0]

print("=" * 60)
print("COMPREHENSIVE TEST (dynamic book id)")
print("=" * 60)

# ===== PUBLIC ENDPOINTS =====
print("\n--- Public Pages ---")
track(test("Root (no session)", "GET", "/", 302))
track(test("Store Home", "GET", "/store/", 200))
track(test("Customer Login", "GET", "/customer/login.html", 200))
track(test("Admin Login", "GET", "/admin/login.html", 200))

print("\n--- CSS (MIME check) ---")
r = track(test("store.css", "GET", "/css/store.css", 200))
if r:
    ct = r.headers.get('Content-Type','')
    ok = 'text/css' in ct
    print(f"  Content-Type: {ct} {'PASS' if ok else 'FAIL - WRONG MIME!'}")
    if ok: passed += 1
    else: failed += 1

r = track(test("admin.css", "GET", "/css/admin.css", 200))

print("\n--- Public APIs ---")
r = track(test("Store Books", "GET", "/api/store/books", 200))
book_id = None
if r and r.status_code == 200:
    books = r.json()
    if books:
        book_id = books[0]['id']

if not book_id:
    print("NO BOOK ID FOUND. ABORTING.")
    exit(1)

r = track(test("Book Detail", "GET", f"/api/store/books/{book_id}", 200))

# ===== CUSTOMER FLOW =====
print("\n--- Customer Flow ---")
S = requests.Session()
email = f"fulltest_{int(time.time())}@example.com"

track(test("Register", "POST", "/api/register", 201, {
    "email": email, "password": "password123", 
    "name": "Test User", "phone": f"555{int(time.time()) % 10000000:07d}"
}, S))

track(test("Login Customer", "POST", "/api/login/customer", 200, {
    "email": email, "password": "password123"
}, S))

track(test("Current User", "GET", "/api/current_user", 200, session=S))
track(test("My Orders", "GET", "/api/my-orders", 200, session=S))

r, _ = test("Create Order", "POST", "/api/orders", 201, {
    "customer_name": "Test", "customer_email": email,
    "customer_phone": "1234567890", "shipping_address": "123 St",
    "total_amount": 10.0,
    "items": [{"book_id": book_id, "quantity": 1, "price": 10.0}]
}, S)
track((r, r and r.status_code == 201))

track(test("Logout", "POST", "/api/logout", 200, session=S))

# ===== STAFF/ADMIN FLOW =====
print("\n--- Admin Flow ---")
A = requests.Session()
track(test("Staff Login (admin)", "POST", "/api/login/staff", 200, {
    "email": "admin@inventro.local", "password": "admin123"
}, A))

track(test("Current User (admin)", "GET", "/api/current_user", 200, session=A))
track(test("Dashboard Stats", "GET", "/api/stats", 200, session=A))
track(test("Get Books (admin)", "GET", "/api/books", 200, session=A))
track(test("Get Orders (admin)", "GET", "/api/orders", 200, session=A))
track(test("Order Stats", "GET", "/api/orders/stats", 200, session=A))
track(test("Get Sales", "GET", "/api/sales", 200, session=A))
track(test("Get Customers", "GET", "/api/customers", 200, session=A))
track(test("Get Users", "GET", "/api/users", 200, session=A))
track(test("Get Coupons", "GET", "/api/coupons", 200, session=A))
track(test("Get Promotions", "GET", "/api/promotions", 200, session=A))

# ===== CASHIER FLOW =====
print("\n--- Cashier Flow ---")
C = requests.Session()
track(test("Staff Login (cashier)", "POST", "/api/login/staff", 200, {
    "email": "cashier@inventro.local", "password": "cashier123"
}, C))

track(test("Cashier Get Books", "GET", "/api/books", 200, session=C))
track(test("POS Checkout", "POST", "/api/checkout", 200, {
    "cart": [{"id": book_id, "title": "1984", "author": "George Orwell", "quantity": 1, "price": 8.99}],
    "payment_method": "cash"
}, C))

track(test("Shift Summary", "GET", "/api/shift/summary", 200, session=C))

# ===== REVIEW FLOW =====
print("\n--- Review APIs ---")
R = requests.Session()
track(test("Login for review", "POST", "/api/login/customer", 200, {
    "email": email, "password": "password123"
}, R))
track(test("Get Reviews", "GET", f"/api/store/books/{book_id}/reviews", 200, session=R))
track(test("Add Review", "POST", f"/api/store/books/{book_id}/reviews", 201, {
    "rating": 5, "comment": "Great book!"
}, R))

print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL TESTS PASSED!")
else:
    print("SOME TESTS FAILED - review output above")
print(f"{'='*60}")
