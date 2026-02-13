import requests
import json

try:
    # 1. Get Books
    print("Fetching books...")
    r = requests.get('http://127.0.0.1:5000/api/books')
    books = r.json()
    print("Books:", books)
    
    if not books:
        print("No books found.")
        exit()

    book = books[0]
    print(f"Testing with book: {book}")

    # 2. Checkout
    cart = [{
        'id': book['id'],
        'title': book['title'],
        'price': book['price'],
        'quantity': 1
    }]
    
    print("Attempting checkout with payload:", json.dumps({'cart': cart}))
    
    r = requests.post('http://127.0.0.1:5000/api/checkout', json={'cart': cart})
    
    print("Status Code:", r.status_code)
    print("Response:", r.text)

except Exception as e:
    print(f"Error: {e}")
