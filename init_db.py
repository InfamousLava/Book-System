from db import get_db_connection
from werkzeug.security import generate_password_hash
from datetime import datetime

def init_db():
    db = get_db_connection()
    if db is None:
        print("[X] Database connection failed. check .env file.")
        return

    # Seed Users
    users = db.users
    if users.count_documents({}) == 0:
        print("[*] Seeding Users...")
        users.insert_many([
            {
                "email": "admin@inventro.local",
                "password_hash": generate_password_hash("admin123"),
                "role": "admin",
                "name": "Admin User",
                "created_at": datetime.utcnow()
            },
            {
                "email": "cashier@inventro.local",
                "password_hash": generate_password_hash("cashier123"),
                "role": "cashier",
                "name": "Cashier User",
                "created_at": datetime.utcnow()
            },
            {
                "email": "shipping@inventro.local",
                "password_hash": generate_password_hash("shipping123"),
                "role": "shipping",
                "name": "Shipping User",
                "created_at": datetime.utcnow()
            }
        ])
    else:
        print("users collection already exists.")

    # Seed Books (Sample Data)
    books = db.books
    if books.count_documents({}) == 0:
        print("[*] Seeding Books...")
        books.insert_many([
            {
                "title": "The Great Gatsby",
                "author": "F. Scott Fitzgerald",
                "price": 10.99,
                "stock": 50,
                "isbn": "9780743273565",
                "category": "Fiction",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/7/7a/The_Great_Gatsby_Cover_1925_Retouched.jpg"
            },
            {
                "title": "1984",
                "author": "George Orwell",
                "price": 8.99,
                "stock": 100,
                "isbn": "9780451524935",
                "category": "Dystopian",
                "image_url": "https://upload.wikimedia.org/wikipedia/en/5/51/1984_first_edition_cover.jpg"
            },
            {
                "title": "The Catcher in the Rye",
                "author": "J.D. Salinger",
                "price": 9.99,
                "stock": 30,
                "isbn": "9780316769480",
                "category": "Fiction",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/8/89/The_Catcher_in_the_Rye_%281951%2C_first_edition_cover%29.jpg"
            }
        ])
    else:
        print("books collection already exists.")

    print("[V] Database initialization complete.")

if __name__ == '__main__':
    init_db()
