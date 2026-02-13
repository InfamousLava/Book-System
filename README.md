# 📚 Inventro Bookstore

A full-stack bookstore management system with POS, inventory, shipping, and online store.

## Features
- **Admin Dashboard** — Revenue stats, staff management, sales history
- **Cashier POS** — Barcode scanning, cart, checkout with coupons/promotions
- **Inventory Manager** — Stock management, book CRUD, barcode scanner
- **Shipping Manager** — Order pipeline, tracking numbers, status updates
- **Online Store** — Browse catalog, product details, reviews with images
- **Customer Portal** — Registration, order history, Google OAuth login

## Quick Setup

### Prerequisites
- **Python 3.10+**
- **PostgreSQL** (running on localhost:5432)

### One-Command Setup
```bash
python setup.py
```

### Manual Setup
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy environment file
cp .env.example .env
# Edit .env with your database credentials

# 3. Initialize database
python init_db.py

# 4. Start the server
python app.py
```

### Open in browser
```
http://127.0.0.1:5000
```

## Default Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@inventro.local | admin123 |
| Cashier | cashier@inventro.local | cashier123 |
| Shipping | shipping@inventro.local | shipping123 |

## Project Structure
```
├── app.py              # Main Flask application
├── db.py               # Database connection
├── schema.sql          # PostgreSQL schema
├── init_db.py          # Database initializer
├── setup.py            # One-click setup script
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variables template
├── static/
│   ├── admin/          # Admin portal pages
│   ├── cashier/        # Cashier POS
│   ├── inventory/      # Inventory management
│   ├── shipping/       # Shipping dashboard
│   ├── store/          # Online store (public)
│   ├── customer/       # Login & registration
│   ├── css/            # Role-specific stylesheets
│   └── js/             # Shared JavaScript
└── api/                # Vercel serverless entry
```

## Environment Variables
See `.env.example` for all available options. Key variables:
- `FLASK_SECRET_KEY` — Session encryption key
- `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASS` — PostgreSQL connection
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — Google OAuth (optional)

## Transferring to Another Computer

1. **Zip the project folder** (or use the backup script):
   ```bash
   python create_backup.py
   ```
2. **Copy the zip** to the other computer
3. **Extract** and run:
   ```bash
   python setup.py
   ```
4. Make sure PostgreSQL is installed and running on the new machine

> **Note:** The database data is NOT included in the backup. Run `python init_db.py` to create fresh tables with default data.
