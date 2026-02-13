import requests

BASE = 'http://127.0.0.1:5000'
s = requests.Session()

# Login as admin
print('1. Logging in as admin...')
r = s.post(f'{BASE}/api/login/staff', json={'email': 'admin@inventro.local', 'password': 'admin123'})
print(f'   Login: {r.status_code} - {r.json()}')

# Get all orders
print('\n2. Fetching orders list...')
r = s.get(f'{BASE}/api/orders')
print(f'   Status: {r.status_code}')
orders = r.json()
print(f'   Orders count: {len(orders)}')

if orders:
    order_id = orders[0]['id']
    print(f'   First order ID: {order_id}')
    
    # Try to get order details
    print(f'\n3. Fetching order #{order_id} details...')
    r = s.get(f'{BASE}/api/orders/{order_id}')
    print(f'   Status: {r.status_code}')
    if r.status_code == 200:
        order = r.json()
        print(f'   Customer: {order.get("customer_name", "N/A")}')
        print(f'   Status: {order.get("status")}')
        print(f'   Items count: {len(order.get("items", []))}')
    else:
        print(f'   Error: {r.text}')
else:
    print('   No orders found - creating a test order...')
    
    # Get a book ID first
    r = s.get(f'{BASE}/api/store/books')
    books = r.json()
    if books:
        book = books[0]
        r = s.post(f'{BASE}/api/orders', json={
            'customer_name': 'Test Customer',
            'customer_email': 'test@example.com',
            'customer_phone': '1234567890',
            'shipping_address': '123 Test Street',
            'items': [{'book_id': book['id'], 'quantity': 1, 'price': book.get('price', 299)}],
            'total_amount': book.get('price', 299)
        })
        print(f'   Create order: {r.status_code}')
        print(f'   Response: {r.text[:300]}')
