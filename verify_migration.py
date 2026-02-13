import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000"
SESSION = requests.Session()

def print_result(name, response, expected_status=200):
    if response.status_code == expected_status:
        print(f"[PASS] {name}")
        return True
    else:
        print(f"[FAIL] {name} - Status: {response.status_code}")
        try:
            print(response.json())
        except:
            print(response.text[:200])
        return False

def verify():
    print("Starting MongoDB Migration Verification...")
    print("=" * 50)
    passed = 0
    failed = 0
    
    # 1. Get Books
    try:
        res = requests.get(f"{BASE_URL}/api/store/books")
        if print_result("Get Store Books", res):
            passed += 1
            books = res.json()
            if not books:
                print("[WARN] No books found. Run init_db.py to seed data.")
            else:
                print(f"[INFO] Found {len(books)} books.")
        else:
            failed += 1
            print("[FATAL] Cannot proceed without book data.")
            return
    except Exception as e:
        print(f"[FAIL] Connection Error: {e}")
        print("[INFO] Make sure the Flask server is running: python app.py")
        return

    # 2. Register
    email = f"test_{int(time.time())}@example.com"
    password = "password123"
    res = SESSION.post(f"{BASE_URL}/api/register", json={
        "email": email,
        "password": password,
        "name": "Test User",
        "phone": "1234567890"
    })
    if res.status_code == 400 and "already" in res.text.lower():
        print("[INFO] User already exists, proceeding to login.")
        passed += 1
    elif print_result("Register User", res, 201):
        passed += 1
    else:
        failed += 1

    # 3. Login
    res = SESSION.post(f"{BASE_URL}/api/login/customer", json={
        "email": email,
        "password": password
    })
    if print_result("Login User", res):
        passed += 1
    else:
        failed += 1

    # 4. Create Online Order
    if books:
        book_id = books[0]['id']
        order_data = {
            "customer_name": "Test Customer",
            "customer_email": email,
            "customer_phone": "1234567890",
            "shipping_address": "123 Test St",
            "total_amount": 10.0,
            "items": [
                {"book_id": book_id, "quantity": 1, "price": 10.0}
            ]
        }
        res = SESSION.post(f"{BASE_URL}/api/orders", json=order_data)
        if print_result("Create Online Order", res, 201):
            passed += 1
        else:
            failed += 1

    # 5. Get My Orders
    res = SESSION.get(f"{BASE_URL}/api/my-orders")
    if print_result("Get My Orders", res):
        passed += 1
        try:
            orders = res.json()
            print(f"[INFO] Found {len(orders)} orders.")
        except:
            pass
    else:
        failed += 1

    # Summary
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("[SUCCESS] All migration tests passed!")
    else:
        print("[WARNING] Some tests failed. Review the output above.")

if __name__ == "__main__":
    verify()
