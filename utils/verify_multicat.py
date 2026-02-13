import requests
import json

BASE_URL = 'http://127.0.0.1:5000/api'

def run_test():
    print("Starting Verification (Rule Engine)...")

    # 1. Create Coupon with JSON Rules (via Admin API logic)
    print("\n1. Creating Coupon 'RULE50'...")
    # Admin page sends: { ... "required_category": ["Fiction", "Science"] ... }
    coupon_data = {
        'code': 'RULE50',
        'discount_type': 'percentage',
        'discount_value': 50,
        'required_category': ['Fiction', 'Science'], # Matches new Multi-select logic
        'min_cart_value': 10
    }
    r = requests.post(f'{BASE_URL}/coupons', json=coupon_data)
    if r.status_code == 201:
        print("Coupon RULE50 created.")
    elif r.status_code == 400 and 'already exists' in r.text:
        print("Coupon RULE50 already exists, proceeding.")
    else:
        print(f"FAILED to create coupon: {r.text}")
        return

    # 2. Create Book with Category 'Science'
    print("\n2. Creating Book 'Cosmos' [Science]...")
    book_data = {
        'title': 'Cosmos',
        'author': 'Sagan',
        'categories': ['Science'],
        'price': 100.0,
        'stock': 100
    }
    r = requests.post(f'{BASE_URL}/books', json=book_data)
    if r.status_code == 201:
        book_id = r.json()['id']
        print(f"Book created with ID: {book_id}")
    else:
        # assume existing for idempotency
        print("Book creation failed or existed.")
        # Need ID to proceed? Fetch it.
        r = requests.get(f'{BASE_URL}/books')
        books = r.json()
        book_id = next((b['id'] for b in books if b['title'] == 'Cosmos'), None)
        if not book_id:
            print("Cannot find book, aborting.")
            return

    # 3. Verify Calculation
    print("\n3. Testing Cart Calculation...")
    cart = [{
        'id': book_id,
        'title': 'Cosmos',
        'author': 'Sagan',
        'categories': ['Science'], # Matches one of the required rules
        'price': 100.0,
        'quantity': 1
    }]

    payload = {
        'cart': cart,
        'coupon_code': 'RULE50'
    }
    
    r = requests.post(f'{BASE_URL}/calculate-totals', json=payload)
    if r.status_code != 200:
        print(f"Calculation API Failed: {r.text}")
        return
    
    data = r.json()
    print("Calculation Result:", json.dumps(data, indent=2))

    # Assertions
    # Coupon RULE50 is 50%
    if data['discount_amount'] == 50.0:
        print("\nSUCCESS: Rule Engine applied discount correctly.")
    else:
        print(f"\nFAILURE: Discount {data['discount_amount']} != expected 50.0")

if __name__ == '__main__':
    try:
        run_test()
    except Exception as e:
        print(f"Test Execution Error: {e}")
