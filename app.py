from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request, send_from_directory, session, redirect, url_for
import db
import email_service
# from psycopg2.extras import RealDictCursor # Removed
import requests
from werkzeug.security import generate_password_hash, check_password_hash
import os
import re
from authlib.integrations.flask_client import OAuth
from bson.objectid import ObjectId
from datetime import datetime
import mimetypes
from utils.helpers import sanitize_input, validate_email, validate_phone, validate_positive_number, validate_integer_id, json_error
from utils.auth import login_required, admin_required, inventory_required, shipping_required

# Fix Windows MIME types - Python's mimetypes module returns application/x-css
# instead of text/css on Windows, which breaks CSS loading when combined with
# the X-Content-Type-Options: nosniff security header
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/javascript', '.js')

app = Flask(__name__, static_url_path='', static_folder='static')

# SECURITY: Use environment variable for secret key
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-static-key-12345')

# ==================== GOOGLE OAUTH CONFIGURATION ====================
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Security headers middleware
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# Serve frontend pages
@app.route('/')
def index_page():
    if 'user_id' not in session:
        return redirect('/customer/login.html')
    
    role = session.get('role')
    if role == 'customer':
        return redirect('/store/index.html')
    elif role == 'cashier':
        return redirect('/cashier/pos.html')
    elif role == 'inventory_manager':
        return redirect('/inventory/manage.html')
    elif role == 'shipping_manager':
        return redirect('/shipping/dashboard.html')
    else:
        return redirect('/admin/dashboard.html')

@app.route('/admin/login')
def staff_login_page():
    if 'user_id' in session and session.get('role') != 'customer':
        return redirect('/')
    return send_from_directory('static', 'admin/login.html')

@app.route('/customer/login.html')
def customer_login_page():
    if 'user_id' in session and session.get('role') == 'customer':
        return redirect('/customer/dashboard.html')
    return send_from_directory('static', 'customer/login.html')

@app.route('/login.html')
def legacy_login():
    return redirect('/admin/login')

@app.route('/store/')
def store_home():
    return send_from_directory('static', 'store/index.html')





@app.route('/api/login/staff', methods=['POST'])
def login_staff():
    return _handle_login(request.json, is_customer=False)

@app.route('/api/login/customer', methods=['POST'])
def login_customer():
    return _handle_login(request.json, is_customer=True)

# ==================== GOOGLE OAUTH ROUTES ====================

@app.route('/auth/google')
def google_login():
    next_url = request.args.get('next', '/customer/dashboard.html')
    session['oauth_next'] = next_url
    
    if not os.environ.get('GOOGLE_CLIENT_ID'):
        return redirect('/customer/login.html?error=google_not_configured')
    
    redirect_uri = request.url_root.rstrip('/') + '/auth/google/callback'
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/google/callback')
def google_callback():
    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo')
        
        if not user_info:
            return redirect('/customer/login.html?error=google_auth_failed')
        
        email = user_info.get('email')
        name = user_info.get('name', email.split('@')[0])
        google_id = user_info.get('sub')
        
        if not email:
            return redirect('/customer/login.html?error=no_email')
        
        database = db.get_db_connection()
        
        try:
            # Check if user exists
            user = database.users.find_one({'email': email})
            
            if user:
                # Existing user
                if user.get('role') != 'customer':
                    return redirect('/customer/login.html?error=staff_use_staff_login')
                
                session['user_id'] = str(user['_id'])
                session['email'] = user['email']
                session['role'] = user['role']
                session['login_method'] = 'google'
            else:
                # New user
                import secrets
                random_password = secrets.token_hex(32)
                hashed_pw = generate_password_hash(random_password)
                
                user_doc = {
                    'email': email,
                    'password_hash': hashed_pw,
                    'role': 'customer',
                    'google_id': google_id,
                    'created_at': datetime.utcnow()
                }
                result = database.users.insert_one(user_doc)
                user_id = result.inserted_id
                
                # Create customer profile
                customer_doc = {
                    'name': name,
                    'email': email,
                    'user_id': user_id,
                    'created_at': datetime.utcnow()
                }
                database.customers.insert_one(customer_doc)
                
                session['user_id'] = str(user_id)
                session['email'] = email
                session['role'] = 'customer'
                session['login_method'] = 'google'
                
                # Send welcome email (non-blocking, won't crash on failure)
                email_service.send_welcome_email(email, name)
            
            next_url = session.pop('oauth_next', '/customer/dashboard.html')
            return redirect(next_url)
            
        except Exception as e:
            print(f"DB Error: {e}")
            return redirect('/customer/login.html?error=db_error')
            
    except Exception as e:
        print(f"OAuth Error: {e}")
        return redirect('/customer/login.html?error=google_auth_failed')

def _handle_login(data, is_customer):
    if not data:
        return json_error('No data provided', 400)
    
    email = sanitize_input(data.get('email', ''), 100)
    password = data.get('password', '')
    
    if not email or not validate_email(email):
        return json_error('Valid email is required', 400)
    
    if not password:
        return json_error('Password is required', 400)
    
    database = db.get_db_connection()
    
    try:
        user = database.users.find_one({'email': email})
        
        if user and check_password_hash(user.get('password_hash') or user.get('password', ''), password):
            # Role Check
            if is_customer and user.get('role') != 'customer':
                return json_error('Staff cannot login here. Please use Staff Login.', 403)
            if not is_customer and user.get('role') == 'customer':
                return json_error('Customers cannot login here. Please use Customer Login.', 403)

            session['user_id'] = str(user['_id'])
            session['email'] = user['email']
            session['role'] = user['role']
            return jsonify({'message': 'Login successful', 'role': user['role']}), 200
        
        return json_error('Invalid credentials', 401)
    except Exception as e:
        return json_error(str(e), 500)

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    
    if not data:
        return json_error('No data provided', 400)
    
    email = sanitize_input(data.get('email', ''), 100)
    name = sanitize_input(data.get('name', ''), 100)
    phone = sanitize_input(data.get('phone', ''), 20)
    password = data.get('password', '')
    
    if not email or not validate_email(email):
        return json_error('Valid email is required', 400)
    
    if not name or len(name) < 2:
        return json_error('Name must be at least 2 characters', 400)
    
    if not validate_phone(phone):
        return json_error('Invalid phone number format', 400)
    
    if not password or len(password) < 6:
        return json_error('Password must be at least 6 characters', 400)
    
    database = db.get_db_connection()
    
    try:
        # Check if email exists
        if database.users.find_one({'email': email}):
            return json_error('Email already registered', 400)
            
        # Check if phone exists (in customers)
        if phone:
            if database.customers.find_one({'phone': phone}):
                 return json_error('Phone number already registered', 400)

        # Create User
        hashed_pw = generate_password_hash(password)
        user_doc = {
            'email': email,
            'password_hash': hashed_pw,
            'role': 'customer',
            'created_at': datetime.utcnow()
        }
        result = database.users.insert_one(user_doc)
        user_id = result.inserted_id
        
        # Create Customer
        customer_doc = {
            'name': name,
            'email': email,
            'phone': phone,
            'user_id': user_id,
            'points': 0,
            'created_at': datetime.utcnow()
        }
        database.customers.insert_one(customer_doc)
        
        # Auto-login
        session['user_id'] = str(user_id)
        session['email'] = email
        session['role'] = 'customer'
        
        # Send welcome email
        email_service.send_welcome_email(email, name)
        
        return jsonify({'message': 'Registration successful'}), 201
        
    except Exception as e:
        return json_error(str(e), 500)


# ==================== STORE & DASHBOARD APIs (MongoDB) ====================

@app.route('/api/my-orders', methods=['GET'])
@login_required
def my_orders():
    database = db.get_db_connection()
    try:
        # Get customer_id from user_id
        # user_id is stored as string in session
        user_id = session.get('user_id')
        if not user_id:
             return json_error('User ID missing', 400)

        # Find customer profile
        customer = database.customers.find_one({'user_id': ObjectId(user_id)})
        
        if not customer:
            return jsonify([]), 200
            
        customer_id = customer['_id']
        
        # Get orders
        # In MongoDB, we will store items EMBEDDED in the order document.
        # So no need to join.
        orders_cursor = database.orders.find({'customer_id': customer_id}).sort('order_date', -1)
        
        orders = []
        for order in orders_cursor:
            order['id'] = str(order['_id'])
            del order['_id']
            # Convert other ObjectIds
            if 'customer_id' in order: order['customer_id'] = str(order['customer_id'])
            # Serialize order_date
            if 'order_date' in order and hasattr(order['order_date'], 'isoformat'):
                order['order_date'] = order['order_date'].isoformat()
            # Ensure items are formatted correctly
            if 'items' in order:
                for item in order['items']:
                    if 'book_id' in item: item['book_id'] = str(item['book_id'])
            orders.append(order)
            
        return jsonify(orders)
    except Exception as e:
        print(f"Error fetching orders: {e}")
        return json_error(str(e), 400)

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out'})

@app.route('/api/current_user')
def get_current_user():
    if 'user_id' in session:
        user_data = {'id': session['user_id'], 'email': session.get('email'), 'role': session['role']}
        # Include customer details for checkout auto-fill
        if session['role'] == 'customer':
            try:
                database = db.get_db_connection()
                cust = database.customers.find_one({'user_id': ObjectId(session['user_id'])})
                if cust:
                    user_data['name'] = cust.get('name', '')
                    user_data['phone'] = cust.get('phone', '')
            except Exception:
                pass
        return jsonify(user_data)
    return jsonify({}), 401


@app.route('/api/stats', methods=['GET'])
@login_required
def get_dashboard_stats():
    database = db.get_db_connection()
    
    role = session['role']
    username = session.get('email', 'User').split('@')[0]
    
    cards = []
    graph = {'labels': [], 'data': []}
    recent_sales = []
    top_products = []
    cashier_stats = []
    active_shifts = []

    try:
        # 1. KPI Cards Logic
        if role == 'cashier':
            # Get current shift stats
            shift_id = session.get('shift_id')
            shift_total = 0.0
            if shift_id:
                shift = database.shifts.find_one({'_id': ObjectId(shift_id)})
                if shift:
                    # Sum sales since shift start
                    start_time = shift['start_time']
                    pipeline = [
                        {'$match': {'sale_date': {'$gte': start_time}, 'created_by': ObjectId(session['user_id'])}},
                        {'$group': {'_id': None, 'total': {'$sum': '$total_amount'}, 'count': {'$sum': 1}}}
                    ]
                    sales_data = list(database.sales.aggregate(pipeline))
                    
                    if sales_data:
                        shift_total = float(sales_data[0]['total'])
                        count = sales_data[0]['count']
                    else:
                        shift_total = 0.0
                        count = 0
                    
                    cards.append({'label': 'Shift Revenue', 'value': f'₹{shift_total:,.2f}', 'subtext': 'Since login'})
                    cards.append({'label': 'Transactions', 'value': str(count), 'subtext': 'This shift'})
        else:
            # Admin: Total Revenue Today
            # Get start of today
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            pipeline = [
                {'$match': {'sale_date': {'$gte': today_start}}},
                {'$group': {'_id': None, 'total': {'$sum': '$total_amount'}}}
            ]
            res = list(database.sales.aggregate(pipeline))
            today_total = res[0]['total'] if res else 0
            
            cards.append({'label': 'Revenue Today', 'value': f'₹{float(today_total):,.2f}', 'subtext': 'Global'})
            
            # Admin: Low Stock
            low_stock = database.books.count_documents({'stock': {'$lt': 5}})
            cards.append({'label': 'Low Stock Items', 'value': str(low_stock), 'subtext': 'Needs Reorder'})

            # Admin: Total Orders Today
            today_orders = database.sales.count_documents({'sale_date': {'$gte': today_start}})
            cards.append({'label': 'Orders Today', 'value': str(today_orders), 'subtext': 'Transactions'})

            # Admin: Top Selling
            # Unwind items from sales and group by book title
            pipeline = [
                {'$unwind': '$items'},
                {'$group': {'_id': '$items.title', 'qty': {'$sum': '$items.quantity'}}},
                {'$sort': {'qty': -1}},
                {'$limit': 5}
            ]
            top_products_res = list(database.sales.aggregate(pipeline))
            for item in top_products_res:
                 top_products.append({'title': item['_id'], 'qty': item['qty']})

            # Admin: Recent 5 Sales
            recent_cursor = database.sales.find().sort('sale_date', -1).limit(5)
            for sale in recent_cursor:
                items_count = len(sale.get('items', []))
                recent_sales.append({
                    'id': str(sale['_id']),
                    'time': sale['sale_date'].strftime('%Y-%m-%d %H:%M'),
                    'total_amount': sale['total_amount'],
                    'payment_method': sale.get('payment_method', 'Cash'),
                    'items_count': items_count
                })

            # Admin: Cashier Performance (Shift based)
            # Aggregate shifts for cashiers
            # We need users who are cashiers
            cashiers = list(database.users.find({'role': 'cashier'}))
            cashier_ids = [c['_id'] for c in cashiers]
            
            pipeline = [
                {'$match': {'user_id': {'$in': cashier_ids}, 'status': 'closed'}},
                {'$group': {
                    '_id': '$user_id', 
                    'shifts_count': {'$sum': 1}, 
                    'total_revenue': {'$sum': '$cash_collected'}
                }}
            ]
            stats_res = list(database.shifts.aggregate(pipeline))
            
            # Map back to email
            user_map = {c['_id']: c['email'] for c in cashiers}
            
            for stat in stats_res:
                email = user_map.get(stat['_id'], 'Unknown')
                cashier_stats.append({
                    'email': email,
                    'username': email.split('@')[0],
                    'shifts_count': stat['shifts_count'],
                    'total_revenue': stat['total_revenue']
                })
            
            # Active Shifts
            active_cursor = database.shifts.find({'status': 'active'})
            for shift in active_cursor:
                # Find user email (inefficient n+1 but low volume)
                u = database.users.find_one({'_id': shift['user_id']})
                email = u['email'] if u else 'Unknown'
                
                # Current sales for this shift
                # Sum sales after start_time
                s_pipeline = [
                    {'$match': {'sale_date': {'$gte': shift['start_time']}}},
                    {'$group': {'_id': None, 'total': {'$sum': '$total_amount'}}}
                ]
                s_res = list(database.sales.aggregate(s_pipeline))
                current_sales = s_res[0]['total'] if s_res else 0
                
                active_shifts.append({
                    'email': email,
                    'username': email.split('@')[0],
                    'start_time': shift['start_time'],
                    'current_sales': current_sales
                })

        # 2. Graph Data (Last 7 Days)
        # Global sales history
        seven_days_ago = datetime.utcnow() # - timedelta(days=7) -> handled by comparison logic or simpler:
        # Actually need date math.
        from datetime import timedelta
        start_date = datetime.utcnow() - timedelta(days=7)
        
        pipeline = [
            {'$match': {'sale_date': {'$gte': start_date}}},
            {
                '$group': {
                    '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$sale_date'}},
                    'total': {'$sum': '$total_amount'}
                }
            },
            {'$sort': {'_id': 1}}
        ]
        graph_res = list(database.sales.aggregate(pipeline))
        
        # Format for frontend (MM-DD)
        graph['labels'] = [datetime.strptime(r['_id'], '%Y-%m-%d').strftime('%b %d') for r in graph_res]
        graph['data'] = [float(r['total']) for r in graph_res]
        
    except Exception as e:
        print(f"Stats Error: {e}")
        # Return empty/safe data on error
        pass
    
    return jsonify({
        'user': {'username': username, 'role': role},
        'cards': cards,
        'graph': graph,
        'recent_sales': recent_sales,
        'top_products': top_products,
        'cashier_stats': cashier_stats,
        'active_shifts': active_shifts
    })

@app.route('/api/shift/start', methods=['POST'])
@login_required
def start_shift():
    """Start a new shift for the current cashier."""
    database = db.get_db_connection()
    
    # Check if there's already an active shift
    existing_shift_id = session.get('shift_id')
    if existing_shift_id:
        try:
            existing = database.shifts.find_one({'_id': ObjectId(existing_shift_id), 'status': 'active'})
            if existing:
                return jsonify({'message': 'Shift already active', 'shift_id': str(existing['_id'])}), 200
        except:
            pass
    
    try:
        shift_doc = {
            'user_id': ObjectId(session['user_id']),
            'start_time': datetime.utcnow(),
            'status': 'active'
        }
        result = database.shifts.insert_one(shift_doc)
        session['shift_id'] = str(result.inserted_id)
        return jsonify({'message': 'Shift started', 'shift_id': str(result.inserted_id)}), 201
    except Exception as e:
        return json_error(str(e), 400)

@app.route('/api/shift/summary', methods=['GET'])
@login_required
def get_shift_summary():
    database = db.get_db_connection()
    shift_id = session.get('shift_id')
    if not shift_id:
        return jsonify({'total_sales': 0, 'start_time': None})
        
    try:
        # Get shift start time
        shift = database.shifts.find_one({'_id': ObjectId(shift_id)})
        if not shift:
             return jsonify({'total_sales': 0})
        
        start_time = shift['start_time']
        
        # Sum sales since start_time
        pipeline = [
            {'$match': {'sale_date': {'$gte': start_time}, 'created_by': ObjectId(session['user_id'])}},
            {'$group': {'_id': None, 'total': {'$sum': '$total_amount'}}}
        ]
        res = list(database.sales.aggregate(pipeline))
        total = res[0]['total'] if res else 0.0
        
        return jsonify({'total_sales': float(total)})
    except Exception as e:
        return json_error(str(e), 400)

@app.route('/api/shift/end', methods=['POST'])
@login_required
def end_shift():
    database = db.get_db_connection()
    shift_id = session.get('shift_id')
    
    total = 0.0
    if shift_id:
        try:
            shift = database.shifts.find_one({'_id': ObjectId(shift_id)})
            if shift:
                start_time = shift['start_time']
                
                # Calculate total
                pipeline = [
                    {'$match': {'sale_date': {'$gte': start_time}, 'created_by': ObjectId(session['user_id'])}},
                    {'$group': {'_id': None, 'total': {'$sum': '$total_amount'}}}
                ]
                res = list(database.sales.aggregate(pipeline))
                total = res[0]['total'] if res else 0.0
                
                database.shifts.update_one(
                    {'_id': ObjectId(shift_id)},
                    {'$set': {
                        'end_time': datetime.utcnow(),
                        'cash_collected': total,
                        'status': 'closed'
                    }}
                )
        except Exception as e:
            return json_error(str(e), 400)
        
    session.clear()
    return jsonify({'message': 'Shift ended', 'total_sales': float(total) if shift_id else 0})

@app.route('/billing')
@login_required
def billing_page():
    if session.get('role') == 'admin':
        return "<h1>Access Denied: Admins cannot use POS.</h1><a href='/admin/dashboard.html'>Go to Dashboard</a>", 403
    return redirect('/cashier/pos.html')

@app.route('/sales-page')
@login_required
def sales_page():
    # Redirect based on role
    if session.get('role') in ['admin', 'shipping_manager']:
        return redirect('/admin/sales.html')
    return redirect('/cashier/sales.html') if session.get('role') == 'cashier' else redirect('/store/index.html')

@app.route('/admin')
@admin_required
def admin_page():
    return redirect('/admin/dashboard.html')



# PUBLIC STORE API (no login required)
@app.route('/api/store/books')
def public_store_books():
    """Public endpoint for store customers to browse books"""
    database = db.get_db_connection()
    try:
        # Find books with stock > 0
        books_cursor = database.books.find({'stock': {'$gt': 0}}).sort('title', 1)
        books = []
        for b in books_cursor:
            b['id'] = str(b['_id'])
            del b['_id']
            # Ensure defaults
            if 'rating_average' not in b: b['rating_average'] = 0
            if 'rating_count' not in b: b['rating_count'] = 0
            books.append(b)
        return jsonify(books)
    except Exception as e:
        return json_error(str(e), 500)

@app.route('/api/store/books/<id>') # Changed to string ID (ObjectId)
def public_get_book(id):
    """Public endpoint for single book details"""
    database = db.get_db_connection()
    try:
        book = database.books.find_one({'_id': ObjectId(id)})
        if not book:
            return json_error('Book not found', 404)
        
        book['id'] = str(book['_id'])
        del book['_id']
        return jsonify(book)
    except Exception:
        return json_error('Invalid Book ID', 400)

@app.route('/api/store/books/<id>/reviews', methods=['POST'])
@login_required
def add_review(id):
    # Handle both JSON and multipart/form-data
    if request.is_json:
        rating = (request.json or {}).get('rating')
    else:
        rating = request.form.get('rating')
    if request.is_json:
        comment = sanitize_input((request.json or {}).get('comment', ''), 1000)
    else:
        comment = sanitize_input(request.form.get('comment', ''), 1000)
    user_id = session['user_id']
    image_file = request.files.get('image')
    
    try:
        rating = int(rating)
        if not (1 <= rating <= 5): raise ValueError()
    except:
        return json_error('Rating must be between 1 and 5', 400)

    database = db.get_db_connection()
    try:
        # Check if user already reviewed
        existing = database.reviews.find_one({'user_id': ObjectId(user_id), 'book_id': ObjectId(id)})
        if existing:
            return json_error('You have already reviewed this book', 400)

        # Handle Image Upload
        image_url = None
        if image_file and image_file.filename:
            # Vercel has a read-only filesystem — skip file uploads
            if os.environ.get('VERCEL'):
                pass  # Image uploads not supported on Vercel serverless
            else:
                from werkzeug.utils import secure_filename
                import time
                
                filename = secure_filename(image_file.filename)
                timestamp = int(time.time())
                ext = os.path.splitext(filename)[1].lower()
                if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                     return json_error('Invalid image format', 400)
                     
                new_filename = f"review_{id}_{user_id}_{timestamp}{ext}"
                save_path = os.path.join(app.static_folder, 'uploads', 'reviews', new_filename)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                image_file.save(save_path)
                image_url = f"/uploads/reviews/{new_filename}"

        # Insert review
        review_doc = {
            'user_id': ObjectId(user_id),
            'book_id': ObjectId(id),
            'rating': rating,
            'comment': comment,
            'image_url': image_url,
            'created_at': datetime.utcnow()
        }
        database.reviews.insert_one(review_doc)
        
        # Update book statistics
        pipeline = [
            {'$match': {'book_id': ObjectId(id)}},
            {'$group': {'_id': None, 'avg': {'$avg': '$rating'}, 'count': {'$sum': 1}}}
        ]
        res = list(database.reviews.aggregate(pipeline))
        if res:
            new_avg = res[0]['avg']
            new_count = res[0]['count']
            database.books.update_one(
                {'_id': ObjectId(id)},
                {'$set': {'rating_average': new_avg, 'rating_count': new_count}}
            )
        
        return jsonify({'message': 'Review added successfully'}), 201
    except Exception as e:
        print(f"Review Error: {e}")
        return json_error('Failed to add review', 500)

@app.route('/api/store/books/<id>/reviews', methods=['GET'])
def get_reviews(id):
    database = db.get_db_connection()
    try:
        # Join with users to get reviewer name
        pipeline = [
            {'$match': {'book_id': ObjectId(id)}},
            {'$sort': {'created_at': -1}},
            {'$lookup': {
                'from': 'users',
                'localField': 'user_id',
                'foreignField': '_id',
                'as': 'user'
            }},
            {'$unwind': '$user'},
            {'$project': {
                '_id': 0,
                'id': {'$toString': '$_id'},
                'rating': 1,
                'comment': 1,
                'image_url': 1,
                'created_at': 1,
                'reviewer': {'$arrayElemAt': [{'$split': ['$user.email', '@']}, 0]}
            }}
        ]
        reviews = list(database.reviews.aggregate(pipeline))
        return jsonify(reviews)
    except Exception as e:
        return json_error(str(e), 400)

@app.route('/api/books/sync-ratings', methods=['POST'])
@inventory_required
def sync_ratings():
    """Fetch ratings from Google Books API and update local DB"""
    database = db.get_db_connection()
    
    try:
        # Get all books
        books = list(database.books.find({}, {'_id': 1, 'title': 1, 'author': 1}))
        updated_count = 0
        
        for book in books:
            try:
                # Basic search by title and author
                query = f"intitle:{book.get('title', '')}"
                if book.get('author'):
                    query += f"+inauthor:{book['author']}"
                
                url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=1"
                res = requests.get(url, timeout=5)
                
                if res.status_code == 200:
                    data = res.json()
                    if 'items' in data and len(data['items']) > 0:
                        info = data['items'][0].get('volumeInfo', {})
                        rating = info.get('averageRating')
                        count = info.get('ratingsCount')
                        
                        if rating:
                            database.books.update_one(
                                {'_id': book['_id']},
                                {'$set': {'rating_average': rating, 'rating_count': count or 0}}
                            )
                            updated_count += 1
            except:
                continue
                
        return jsonify({'message': f'Updated ratings for {updated_count} books'}), 200
        
    except Exception as e:
        return json_error(str(e), 400)

@app.route('/api/sales', methods=['GET'])
@login_required
def get_sales():
    database = db.get_db_connection()
    try:
        # Simple fetch, maybe join customer if needed
        # In Mongo, we might have customer_name embedded or just fetch it.
        # Let's assume we want to join customers.
        pipeline = [
            {'$sort': {'sale_date': -1}},
            {'$lookup': {
                'from': 'customers',
                'localField': 'customer_id',
                'foreignField': '_id',
                'as': 'customer'
            }},
            # Join books for search text? Expensive.
            # Let's just return sales for now.
             {'$addFields': {
                'customer_name': {'$arrayElemAt': ['$customer.name', 0]},
                # Flatten items info for search
                'searchable_text': {
                    '$reduce': {
                        'input': '$items',
                        'initialValue': '',
                        'in': {'$concat': ['$$value', ' ', '$$this.title', ' ', '$$this.author']}
                    }
                }
            }}
        ]
        sales = list(database.sales.aggregate(pipeline))
        
        # Serialize ObjectIds
        for s in sales:
            s['id'] = str(s['_id'])
            del s['_id']
            if 'customer_id' in s and s['customer_id']: s['customer_id'] = str(s['customer_id'])
            if 'created_by' in s and s['created_by']: s['created_by'] = str(s['created_by'])
            if 'customer' in s: del s['customer'] # Clean up
            # Convert ObjectIds in nested items
            for item in s.get('items', []):
                if 'book_id' in item: item['book_id'] = str(item['book_id'])
                if '_id' in item: item['_id'] = str(item['_id'])
            # Convert dates
            if 'sale_date' in s and hasattr(s['sale_date'], 'isoformat'):
                s['sale_date'] = s['sale_date'].isoformat()
            
        return jsonify(sales)
    except Exception as e:
        return json_error(str(e), 400)

@app.route('/api/sales/<id>/items', methods=['GET'])
@login_required
def get_sale_items(id):
    database = db.get_db_connection()
    try:
        sale = database.sales.find_one({'_id': ObjectId(id)})
        if not sale: return jsonify([])
        
        # Items are embedded — serialize ObjectIds
        items = sale.get('items', [])
        for item in items:
            if 'book_id' in item: item['book_id'] = str(item['book_id'])
            if '_id' in item: item['_id'] = str(item['_id'])
        return jsonify(items)
    except Exception as e:
        return json_error(str(e), 400)

# ========= COUPON & PROMOTION APIs =========

@app.route('/api/coupons', methods=['GET'])
@login_required
def get_coupons():
    database = db.get_db_connection()
    try:
        coupons_cursor = database.coupons.find().sort('_id', -1)
        coupons = []
        for c in coupons_cursor:
            c['id'] = str(c['_id'])
            del c['_id']
            # valid_from/until are datetime, JSON serializer handles them or we format strings?
            # Flask jsonify handles datetime usually (GMT).
            coupons.append(c)
        return jsonify(coupons)
    except Exception as e:
        return json_error(str(e), 400)

@app.route('/api/coupons', methods=['POST'])
@admin_required
def create_coupon():
    data = request.json
    database = db.get_db_connection()
    try:
        # Structure constraints
        constraints = {}
        if data.get('min_cart_value'):
            constraints['min_cart_value'] = float(data['min_cart_value'])
        if data.get('min_quantity'):
            constraints['min_quantity'] = int(data['min_quantity'])
        if data.get('required_category'):
            cats = data.get('required_category')
            if isinstance(cats, str):
                cats = [cats]
            constraints['categories'] = cats
        
        # Insert
        coupon_doc = {
            'code': data['code'],
            'description': data.get('description', ''),
            'discount_type': data['discount_type'],
            'discount_value': float(data['discount_value']),
            'valid_from': data.get('valid_from'), # Expecting ISO string or datetime?
            # If string, Mongo saves as string? Better to parse to datetime if possible.
            # But let's assume ISO string is fine or frontend sends something compatible.
            # Best practice: Convert to datetime objects.
            'valid_until': data.get('valid_until'),
            'constraints': constraints, # Store as dict, not JSON string
            'max_uses': int(data['max_uses']) if data.get('max_uses') else None,
            'used_count': 0,
            'active': True,
            'created_at': datetime.utcnow()
        }
        
        # Parse Dates if strings
        if coupon_doc['valid_from'] and isinstance(coupon_doc['valid_from'], str):
            try: coupon_doc['valid_from'] = datetime.fromisoformat(coupon_doc['valid_from'].replace('Z', '+00:00'))
            except: pass
        if coupon_doc['valid_until'] and isinstance(coupon_doc['valid_until'], str):
             try: coupon_doc['valid_until'] = datetime.fromisoformat(coupon_doc['valid_until'].replace('Z', '+00:00'))
             except: pass

        result = database.coupons.insert_one(coupon_doc)
        return jsonify({'id': str(result.inserted_id), 'message': 'Coupon created'}), 201
    except Exception as e:
        return json_error(str(e), 400)

@app.route('/api/coupons/<id>', methods=['DELETE']) # String ID
@admin_required
def delete_coupon(id):
    database = db.get_db_connection()
    try:
        database.coupons.update_one({'_id': ObjectId(id)}, {'$set': {'active': False}})
        return jsonify({'message': 'Coupon deactivated'}), 200
    except Exception as e:
        return json_error(str(e), 400)


# === RULE ENGINE HELPER ===
def check_rules(coupon, cart):
    constraints = coupon.get('constraints') or {}
    
    # Cart Stats
    cart_total = sum(float(item.get('price', 0)) * item.get('quantity', 0) for item in cart)
    cart_quantity = sum(item.get('quantity', 0) for item in cart)
    
    # 1. Min Cart Value
    min_val = float(constraints.get('min_cart_value', 0))
    if cart_total < min_val:
         return False, f"Minimum cart value of ${min_val:.2f} required."

    # 2. Min Quantity
    min_qty = int(constraints.get('min_quantity', 0))
    if cart_quantity < min_qty:
         return False, f"Minimum of {min_qty} items required."

    # 3. Category Match (ANY item in cart matches ANY required category)
    req_cats = constraints.get('categories', [])
    if req_cats:
        has_match = False
        for item in cart:
            item_cats = item.get('categories', [])
            # Intersection check
            if any(c in item_cats for c in req_cats):
                has_match = True
                break
        
        if not has_match:
            return False, "This coupon requires specific category items."

    return True, None

@app.route('/api/validate-coupon', methods=['POST'])
@login_required
def validate_coupon():
    data = request.json
    code = data.get('code', '').upper()
    cart = data.get('cart', [])
    
    database = db.get_db_connection()
    
    try:
        # Regex for case insensitive search if needed, but we stored as is. 
        # Ideally store uppercase or search with regex.
        # Let's search exact match first, assuming we save standard.
        # Use regex for Safety:
        coupon = database.coupons.find_one({'code': {'$regex': f'^{re.escape(code)}$', '$options': 'i'}})
        
        if not coupon:
            return jsonify({'valid': False, 'error': 'Invalid coupon code.'}), 400
        
        if not coupon.get('active', True):
             return jsonify({'valid': False, 'error': 'Coupon deactivated.'}), 400
            
        now = datetime.utcnow()
        if coupon.get('valid_until') and coupon['valid_until'] < now:
            return jsonify({'valid': False, 'error': 'Coupon expired.'}), 400
        if coupon.get('valid_from') and coupon['valid_from'] > now:
            return jsonify({'valid': False, 'error': 'Coupon not yet valid.'}), 400
        if coupon.get('max_uses') and coupon.get('used_count', 0) >= coupon['max_uses']:
            return jsonify({'valid': False, 'error': 'Usage limit reached.'}), 400

        # Run Rules
        is_valid, error_msg = check_rules(coupon, cart)
        if not is_valid:
            return jsonify({'valid': False, 'error': error_msg}), 400

        # Calculate discount (Subtotal basis for now)
        cart_total = sum(float(item.get('price', 0)) * item.get('quantity', 0) for item in cart)
        
        if coupon['discount_type'] == 'percentage':
            discount = cart_total * (float(coupon['discount_value']) / 100)
        else:
            discount = float(coupon['discount_value'])
        
        discount = min(discount, cart_total)
        
        # Serialize for JSON
        coupon['_id'] = str(coupon['_id'])
        
        return jsonify({
            'valid': True,
            'coupon': coupon,
            'discount_amount': discount,
            'final_total': cart_total - discount
        }), 200
        
    except Exception as e:
        return json_error(str(e), 400)

@app.route('/api/promotions', methods=['GET'])
@login_required
def get_promotions():
    database = db.get_db_connection()
    now = datetime.utcnow()
    cursor = database.promotions.find({
        'active': True,
        '$and': [
            {'$or': [{'start_date': {'$exists': False}}, {'start_date': None}, {'start_date': {'$lte': now}}]},
            {'$or': [{'end_date': {'$exists': False}}, {'end_date': None}, {'end_date': {'$gte': now}}]}
        ]
    }).sort('discount_percentage', -1)
    
    promotions = []
    for p in cursor:
        p['id'] = str(p['_id'])
        del p['_id']
        # Serialize datetime objects for JSON
        if 'start_date' in p and hasattr(p['start_date'], 'isoformat'):
            p['start_date'] = p['start_date'].isoformat()
        if 'end_date' in p and hasattr(p['end_date'], 'isoformat'):
            p['end_date'] = p['end_date'].isoformat()
        promotions.append(p)
    return jsonify(promotions)

@app.route('/api/promotions', methods=['POST'])
@admin_required
def create_promotion():
    data = request.json
    database = db.get_db_connection()
    try:
        cats = data.get('categories')
        if isinstance(cats, str):
            cats = [cats]
            
        doc = {
            'name': data['name'],
            'description': data.get('description', ''),
            'categories': cats,
            'discount_percentage': data['discount_percentage'],
            'start_date': data.get('start_date'),
            'end_date': data.get('end_date'),
            'active': True
        }
        # Parse dates
        if doc['start_date']:
             try: doc['start_date'] = datetime.fromisoformat(doc['start_date'].replace('Z', '+00:00'))
             except: pass
        if doc['end_date']:
             try: doc['end_date'] = datetime.fromisoformat(doc['end_date'].replace('Z', '+00:00'))
             except: pass

        result = database.promotions.insert_one(doc)
        return jsonify({'id': str(result.inserted_id), 'message': 'Promotion created'}), 201
    except Exception as e:
        return json_error(str(e), 400)

@app.route('/api/promotions/<id>', methods=['PUT']) # String ID
@admin_required
def update_promotion(id):
    data = request.json
    database = db.get_db_connection()
    try:
        database.promotions.update_one({'_id': ObjectId(id)}, {'$set': {'active': data.get('active', True)}})
        return jsonify({'message': 'Promotion updated'}), 200
    except Exception as e:
        return json_error(str(e), 400)

def calculate_order_totals(database, cart, coupon_code=None):
    # Pass 'database' object instead of 'cur'
    # Logic similar to SQL but uses Mongo queries
    
    total_amount = sum(float(item.get('price', 0)) * item.get('quantity', 0) for item in cart)
    discount_amount = 0
    coupon_discount = 0
    promo_discounts = {}
    applied_coupon = None
    breakdown = []
    
    now = datetime.utcnow()
    promotions = list(database.promotions.find({
        'active': True,
        '$and': [
            {'$or': [{'start_date': {'$exists': False}}, {'start_date': None}, {'start_date': {'$lte': now}}]},
            {'$or': [{'end_date': {'$exists': False}}, {'end_date': None}, {'end_date': {'$gte': now}}]}
        ]
    }))

    # Apply Automatic Promotions FIRST
    for item in cart:
        for promo in promotions:
             # Check match
             promo_cats = promo.get('categories')
             item_cats = item.get('categories', [])
             if isinstance(item_cats, str): item_cats = [item_cats] # Handle legacy string cats
             if not item_cats: item_cats = []
             
             is_match = False
             if not promo_cats:
                 is_match = True
             else:
                  if any(c in item_cats for c in promo_cats):
                      is_match = True
             
             if is_match:
                 item_total = float(item['price']) * item['quantity']
                 promo_discount = item_total * (float(promo['discount_percentage']) / 100)
                 
                 promo_id = str(promo['_id'])
                 if promo_id not in promo_discounts:
                     promo_discounts[promo_id] = {'promo': promo, 'amount': 0}
                 promo_discounts[promo_id]['amount'] += promo_discount
                 
                 if 'promo_discount' not in item:
                     item['promo_discount'] = 0
                 item['promo_discount'] += promo_discount
                 
                 break # One promo per item

    # Add promo discounts
    promo_total = 0
    for pid, pdata in promo_discounts.items():
        amount = pdata['amount']
        promo_total += amount
        discount_amount += amount
        breakdown.append(f"{pdata['promo']['name']} (-${amount:.2f})")

    # Apply Coupon
    if coupon_code:
        coupon = database.coupons.find_one({'code': {'$regex': f'^{re.escape(coupon_code)}$', '$options': 'i'}, 'active': True})
        
        if coupon:
             is_valid, _ = check_rules(coupon, cart)
             if is_valid:
                remaining_total = max(0, total_amount - promo_total)
                if coupon['discount_type'] == 'percentage':
                    coupon_amt = remaining_total * (float(coupon['discount_value']) / 100)
                else:
                    coupon_amt = float(coupon['discount_value'])
                
                coupon_discount = min(coupon_amt, remaining_total)
                discount_amount += coupon_discount
                
                # Prepare coupon/promo for JSON (str IDs)
                coupon['id'] = str(coupon['_id'])
                if '_id' in coupon: del coupon['_id']
                
                applied_coupon = coupon
                breakdown.append(f"Coupon {coupon['code']} (-${coupon_discount:.2f})")

    # Tax
    taxable_amount = max(0, total_amount - discount_amount)
    tax_amount = taxable_amount * 0.18
    final_total = taxable_amount + tax_amount
    
    # Serialize promo_discounts (fix structure for JSON)
    # Convert dict to simpler format if needed or cleaner loop above
    # Just ensure ObjectIds are strings
    for pid in promo_discounts:
        pdata = promo_discounts[pid]
        pdata['promo']['id'] = str(pdata['promo']['_id'])
        del pdata['promo']['_id']

    return {
        'total_amount': total_amount,
        'discount_amount': discount_amount,
        'tax_amount': tax_amount,
        'final_total': final_total,
        'breakdown': breakdown,
        'applied_coupon': applied_coupon,
        'promo_discounts': promo_discounts,
        'coupon_discount': coupon_discount
    }

@app.route('/api/calculate-totals', methods=['POST'])
@login_required
def calculate_totals_endpoint():
    database = db.get_db_connection()
    try:
        data = request.json
        cart = data.get('cart', [])
        coupon_code = data.get('coupon_code')
        
        totals = calculate_order_totals(database, cart, coupon_code)
        return jsonify(totals)
    except Exception as e:
        return json_error(str(e), 400)

@app.route('/api/customers', methods=['GET', 'POST'])
@login_required
def handle_customers():
    database = db.get_db_connection()
    
    if request.method == 'POST':
        data = request.json
        try:
            # Check if phone exists
            if data.get('phone'):
                existing = database.customers.find_one({'phone': data['phone']})
                if existing:
                     return json_error('Customer with this phone already exists', 400)

            doc = {
                'name': data['name'],
                'phone': data['phone'],
                'email': data.get('email'),
                'created_at': datetime.utcnow()
            }
            result = database.customers.insert_one(doc)
            return jsonify({'id': str(result.inserted_id), 'message': 'Customer created'}), 201
        except Exception as e:
            return json_error(str(e), 400)
            
    else: # GET Search
        phone = request.args.get('phone', '').strip()
        query = {}
        if phone:
            query = {'$or': [
                {'phone': {'$regex': phone, '$options': 'i'}},
                {'name': {'$regex': phone, '$options': 'i'}}
            ]}
        
        cursor = database.customers.find(query).sort('created_at', -1).limit(50)
        customers = []
        for c in cursor:
            c['id'] = str(c['_id'])
            del c['_id']
            if 'user_id' in c: c['user_id'] = str(c['user_id'])
            customers.append(c)
        return jsonify(customers)

# ==================== BOOK MANAGEMENT (CRUD) ====================

@app.route('/api/books', methods=['GET'])
def get_books():
    database = db.get_db_connection()
    try:
        query = {}
        
        search = request.args.get('search')
        if search:
            # Simple Regex search
            query['$or'] = [
                {'title': {'$regex': search, '$options': 'i'}},
                {'author': {'$regex': search, '$options': 'i'}},
                {'barcode': search}
            ]
            
        category = request.args.get('category')
        if category:
            query['categories'] = category
            
        cursor = database.books.find(query).sort('_id', -1)
        books = []
        for b in cursor:
            b['id'] = str(b['_id'])
            del b['_id']
            books.append(b)
        return jsonify(books)
    except Exception as e:
         return json_error(str(e), 500)

@app.route('/api/books', methods=['POST'])
@inventory_required
def add_book():
    try:
        data = request.json
        if not data:
            return json_error('No data provided', 400)
            
        required = ['title', 'author', 'price', 'stock']
        for field in required:
            if field not in data:
                return json_error(f'Missing field: {field}', 400)
        
        database = db.get_db_connection()
        
        # Check barcode uniqueness
        barcode = data.get('barcode')
        if barcode:
            if database.books.find_one({'barcode': barcode}):
                 return json_error('Barcode already exists', 400)
        
        doc = {
            'title': data['title'],
            'author': data['author'],
            'description': data.get('description', ''),
            'categories': data.get('categories', []),
            'price': float(data['price']),
            'stock': int(data['stock']),
            'barcode': barcode,
            'image_url': data.get('image_url'),
            'warehouse_location': data.get('warehouse_location'),
            'rating_average': 0,
            'rating_count': 0,
            'created_at': datetime.utcnow()
        }
        
        result = database.books.insert_one(doc)
        return jsonify({'id': str(result.inserted_id), 'message': 'Book added successfully'}), 201
        
    except Exception as e:
        return json_error(str(e), 500)

@app.route('/api/books/<id>', methods=['PUT']) # String ID
@inventory_required
def update_book(id):
    try:
        data = request.json
        database = db.get_db_connection()
        
        update_fields = {}
        if 'title' in data: update_fields['title'] = data['title']
        if 'author' in data: update_fields['author'] = data['author']
        if 'description' in data: update_fields['description'] = data['description']
        if 'price' in data: update_fields['price'] = float(data['price'])
        if 'stock' in data: update_fields['stock'] = int(data['stock'])
        if 'barcode' in data: update_fields['barcode'] = data['barcode']
        if 'categories' in data:
            update_fields['categories'] = data['categories'] if isinstance(data['categories'], list) else [data['categories']] if data['categories'] else []
        if 'image_url' in data: update_fields['image_url'] = data['image_url']
        if 'warehouse_location' in data: update_fields['warehouse_location'] = data['warehouse_location']
        
        result = database.books.update_one({'_id': ObjectId(id)}, {'$set': update_fields})
        
        if result.matched_count == 0:
             return json_error('Book not found', 404)
             
        return jsonify({'message': 'Book updated successfully'})
    except Exception as e:
        return json_error(str(e), 400)

@app.route('/api/books/<id>', methods=['DELETE'])
@inventory_required
def delete_book(id):
    database = db.get_db_connection()
    try:
        # Check references (e.g. in sales)
        # Mongo doesn't enforce FK, but good to check.
        # Check if book is in any sale items? Expensive check on `sales.items.book_id`.
        # For MVP, just delete.

        result = database.books.delete_one({'_id': ObjectId(id)})
        if result.deleted_count == 0:
            return json_error('Book not found', 404)
            
        return jsonify({'message': 'Book deleted'})
    except Exception as e:
        return json_error(str(e), 400)

@app.route('/api/checkout', methods=['POST'])
@login_required # Only logged in users (like Cashiers) use this POS checkout
def checkout():
    data = request.json
    cart = data.get('cart') or data.get('items', [])
    coupon_code = data.get('coupon_code')
    payment_method = data.get('payment_method', 'Cash')
    customer_id = data.get('customer_id') 
    
    if not cart:
        return json_error('Cart is empty', 400)
        
    database = db.get_db_connection()
    
    try:
        # 1. Recalculate Totals
        totals = calculate_order_totals(database, cart, coupon_code)
        
        # 2. Check & Deduct Stock Atomically (prevents race conditions)
        for item in cart:
            result = database.books.find_one_and_update(
                {'_id': ObjectId(item['id']), 'stock': {'$gte': int(item['quantity'])}},
                {'$inc': {'stock': -int(item['quantity'])}}
            )
            if not result:
                # Rollback any stock already deducted in this loop
                for prev_item in cart:
                    if prev_item is item:
                        break
                    database.books.update_one(
                        {'_id': ObjectId(prev_item['id'])},
                        {'$inc': {'stock': int(prev_item['quantity'])}}
                    )
                return json_error(f"Insufficient stock for {item['title']}", 400)
        
        # 3. Create Sale Record
        sale_doc = {
            'sale_date': datetime.utcnow(),
            'total_amount': totals['final_total'],
            'discount_amount': totals['discount_amount'],
            'tax_amount': totals['tax_amount'],
            'payment_method': payment_method,
            'customer_id': ObjectId(customer_id) if customer_id else None,
            'created_by': ObjectId(session['user_id']), # Track cashier
            'coupon_code': coupon_code if totals['coupon_discount'] > 0 else None,
            'coupon_discount': totals['coupon_discount'],
            'items': [] # Embed items
        }
        
        # Prepare items
        for item in cart:
            item_doc = {
                'book_id': ObjectId(item['id']),
                'title': item['title'],
                'author': item.get('author'),
                'quantity': item['quantity'],
                'price_at_sale': float(item['price']),
                'promo_discount': item.get('promo_discount', 0)
            }
            sale_doc['items'].append(item_doc)
            
        # Insert Sale
        result = database.sales.insert_one(sale_doc)
        sale_id = result.inserted_id
        
        # 4. Update Coupon Usage (stock already deducted atomically above)
            
        if totals['applied_coupon']:
            database.coupons.update_one(
                {'_id': ObjectId(totals['applied_coupon']['id'])},
                {'$inc': {'used_count': 1}}
            )
            
        return jsonify({
            'message': 'Sale completed', 
            'sale_id': str(sale_id),
            'final_total': totals['final_total'],
            'discount_amount': totals['discount_amount']
        }), 200
        
    except Exception as e:
        print(f"Checkout Error: {e}")
        return json_error(str(e), 500)

@app.route('/cashiers')
@admin_required
def cashiers_page():
    return send_from_directory('static', 'cashiers.html')

@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    database = db.get_db_connection()
    users_cursor = database.users.find().sort('created_at', -1)
    users = []
    for u in users_cursor:
        u['id'] = str(u['_id'])
        del u['_id']
        u.pop('password', None)
        u.pop('password_hash', None)
        users.append(u)
    return jsonify(users)

@app.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    data = request.json
    if not data: return json_error('No data', 400)
    
    email = sanitize_input(data.get('email', ''), 100)
    password = data.get('password', '')
    role = sanitize_input(data.get('role', ''), 30)
    
    if not email or not validate_email(email):
        return json_error('Valid email is required', 400)
    if not password or len(password) < 6:
        return json_error('Password must be at least 6 characters', 400)
        
    valid_roles = ['admin', 'cashier', 'inventory_manager', 'shipping_manager']
    if role not in valid_roles:
         return json_error('Invalid role', 400)
         
    database = db.get_db_connection()
    try:
        if database.users.find_one({'email': email}):
             return json_error('Email already registered', 400)
             
        from werkzeug.security import generate_password_hash
        hashed = generate_password_hash(password)
        
        doc = {
            'email': email,
            'password_hash': hashed,
            'role': role,
            'created_at': datetime.utcnow()
        }
        result = database.users.insert_one(doc)
        return jsonify({'id': str(result.inserted_id), 'message': 'User created'}), 201
    except Exception as e:
        return json_error(str(e), 400)

@app.route('/api/users/<id>', methods=['DELETE'])
@admin_required
def delete_user(id):
    if id == session.get('user_id'):
        return json_error('Cannot delete yourself', 400)
        
    database = db.get_db_connection()
    result = database.users.delete_one({'_id': ObjectId(id)})
    if result.deleted_count == 0:
         return json_error('User not found', 404)
    return jsonify({'message': 'User deleted'})


@app.route('/api/admin/cashiers', methods=['GET'])
@admin_required
def get_cashier_management_stats():
    database = db.get_db_connection()
    try:
         # 1. Staff Performance (closed shifts)
         pipeline = [
            {'$match': {'status': 'closed'}},
            {'$group': {
                '_id': '$user_id', 
                'shifts_count': {'$sum': 1}, 
                'total_revenue': {'$sum': '$cash_collected'}
            }},
            {'$lookup': {
                'from': 'users',
                'localField': '_id',
                'foreignField': '_id',
                'as': 'user'
            }},
            {'$unwind': '$user'},
            {'$project': {
                'email': '$user.email',
                'username': '$user.username',
                'shifts_count': 1,
                'total_revenue': 1
            }}
        ]
         stats = list(database.shifts.aggregate(pipeline))
         
         # Serialize stats ObjectIds
         for s in stats:
             s['_id'] = str(s['_id'])
         
         # 2. Active Shifts
         pipeline_active = [
             {'$match': {'status': 'active'}},
             {'$lookup': {
                'from': 'users',
                'localField': 'user_id',
                'foreignField': '_id',
                'as': 'user'
             }},
             {'$unwind': '$user'},
             # Calculate current sales for this specific cashier's shift
             {'$lookup': {
                 'from': 'sales',
                 'let': {'start': '$start_time', 'uid': '$user_id'},
                 'pipeline': [
                     {'$match': {'$expr': {
                         '$and': [
                             {'$gte': ['$sale_date', '$$start']},
                             {'$eq': ['$created_by', '$$uid']}
                         ]
                     }}},
                     {'$group': {'_id': None, 'total': {'$sum': '$total_amount'}}}
                 ],
                 'as': 'sales_data'
             }},
             {'$addFields': {
                 'current_sales': {'$ifNull': [{'$arrayElemAt': ['$sales_data.total', 0]}, 0]}
             }},
             {'$project': {
                 'email': '$user.email',
                 'username': '$user.username',
                 'start_time': 1,
                 'current_sales': 1
             }}
         ]
         active = list(database.shifts.aggregate(pipeline_active))
         
         # Serialize active shifts ObjectIds and datetimes
         for a in active:
             a['_id'] = str(a['_id'])
             if 'start_time' in a and hasattr(a['start_time'], 'isoformat'):
                 a['start_time'] = a['start_time'].isoformat()
         
         return jsonify({'stats': stats, 'active': active})
    except Exception as e:
         return json_error(str(e), 400)

# ==================== ORDER APIs ====================

@app.route('/api/orders', methods=['GET'])
@login_required
def get_orders():
    """Get all orders (for shipping manager and admin)"""
    role = session.get('role')
    if role not in ['admin', 'shipping_manager']:
        return json_error('Access denied', 403)
    
    database = db.get_db_connection()
    
    status_filter = request.args.get('status')
    query = {}
    if status_filter:
        query['status'] = status_filter
        
    orders_cursor = database.orders.find(query).sort('order_date', -1)
    orders = []
    
    for o in orders_cursor:
        o['id'] = str(o['_id'])
        del o['_id']
        if 'customer_id' in o and o['customer_id']: o['customer_id'] = str(o['customer_id'])
        # Convert ObjectIds in nested items
        for item in o.get('items', []):
            if 'book_id' in item: item['book_id'] = str(item['book_id'])
            if '_id' in item: item['_id'] = str(item['_id'])
        if 'order_date' in o and hasattr(o['order_date'], 'isoformat'):
            o['order_date'] = o['order_date'].isoformat()
        orders.append(o)
        
    return jsonify(orders)

@app.route('/api/orders/<id>', methods=['GET'])
@login_required
def get_order(id):
    """Get order details with items"""
    database = db.get_db_connection()
    order = database.orders.find_one({'_id': ObjectId(id)})
    if not order:
        return json_error('Order not found', 404)
        
    order['id'] = str(order['_id'])
    del order['_id']
    if 'customer_id' in order and order['customer_id']: order['customer_id'] = str(order['customer_id'])
    # Serialize embedded item ObjectIds
    for item in order.get('items', []):
        if 'book_id' in item: item['book_id'] = str(item['book_id'])
        if '_id' in item: item['_id'] = str(item['_id'])
    # Serialize dates
    if 'order_date' in order and hasattr(order['order_date'], 'isoformat'):
        order['order_date'] = order['order_date'].isoformat()
    
    return jsonify(order)

@app.route('/api/orders', methods=['POST'])
def create_order():
    """Create a new order (from store checkout)"""
    data = request.json
    
    # INPUT VALIDATION
    if not data: return json_error('No data', 400)
    
    customer_name = sanitize_input(data.get('customer_name', ''), 100)
    customer_email = sanitize_input(data.get('customer_email', ''), 100)
    customer_phone = sanitize_input(data.get('customer_phone', ''), 20)
    shipping_address = sanitize_input(data.get('shipping_address', ''), 500)
    total_amount = data.get('total_amount', 0)
    items = data.get('items', [])
    
    if not customer_name: return json_error('Name required', 400)
    if not items: return json_error('Items required', 400)
    
    database = db.get_db_connection()
    try:
        # Check login
        customer_id = None
        if 'user_id' in session:
            cust = database.customers.find_one({'user_id': ObjectId(session['user_id'])})
            if cust: customer_id = cust['_id']
            
        # Generate Tracking (UUID-based to prevent collisions)
        import uuid
        tracking_number = f"INV-{uuid.uuid4().hex[:8].upper()}"
        
        # Prepare Order Doc
        order_doc = {
            'customer_name': customer_name,
            'customer_email': customer_email,
            'customer_phone': customer_phone,
            'shipping_address': shipping_address,
            'total_amount': float(total_amount),
            'status': 'pending',
            'customer_id': customer_id,
            'tracking_number': tracking_number,
            'order_date': datetime.utcnow(),
            'items': []
        }
        
        # Validate Items & Build item list
        for item in items:
            book = database.books.find_one({'_id': ObjectId(item['book_id'])})
            if not book: return json_error(f"Book {item['book_id']} not found", 400)
            
            qty = int(item['quantity'])
            order_doc['items'].append({
                'book_id': book['_id'],
                'title': book['title'],
                'author': book.get('author'),
                'quantity': qty,
                'price_at_order': float(item['price'])
            })
            
        # Insert Order
        result = database.orders.insert_one(order_doc)
        order_id = result.inserted_id
        
        # Deduct Stock Atomically (prevents race conditions)
        for i, item in enumerate(order_doc['items']):
            result = database.books.find_one_and_update(
                {'_id': item['book_id'], 'stock': {'$gte': item['quantity']}},
                {'$inc': {'stock': -item['quantity']}}
            )
            if not result:
                # Rollback previously deducted stock
                for prev_item in order_doc['items'][:i]:
                    database.books.update_one(
                        {'_id': prev_item['book_id']},
                        {'$inc': {'stock': prev_item['quantity']}}
                    )
                # Delete the already-inserted order
                database.orders.delete_one({'_id': order_id})
                return json_error(f"Insufficient stock for {item['title']}", 400)
        
        # Send order confirmation email
        if customer_email:
            email_service.send_order_confirmation(
                email=customer_email,
                name=customer_name,
                order_id=str(order_id),
                tracking_number=tracking_number,
                items=order_doc['items'],
                total_amount=order_doc['total_amount']
            )
            
        return jsonify({'order_id': str(order_id), 'tracking_number': tracking_number, 'message': 'Order placed successfully'}), 201
        
    except Exception as e:
        return json_error(str(e), 400)

@app.route('/api/orders/<id>/status', methods=['PUT'])
@shipping_required
def update_order_status(id):
    """Update order status"""
    data = request.json
    new_status = data.get('status')
    tracking = data.get('tracking_number')
    notes = data.get('notes')
    
    valid_statuses = ['pending', 'confirmed', 'packed', 'shipped', 'in_transit', 'out_for_delivery', 'delivered', 'cancelled']
    if new_status not in valid_statuses:
        return json_error('Invalid status', 400)
        
    database = db.get_db_connection()
    
    try:
        update_doc = {'status': new_status}
        if tracking: update_doc['tracking_number'] = tracking
        if notes: update_doc['notes'] = notes
        
        # Auto-generate tracking if needed
        if new_status in ['packed', 'shipped'] and 'tracking_number' not in update_doc:
            # Check if exists
            order = database.orders.find_one({'_id': ObjectId(id)})
            if order and not order.get('tracking_number'):
                import uuid
                update_doc['tracking_number'] = f"INV-{uuid.uuid4().hex[:8].upper()}"

        database.orders.update_one({'_id': ObjectId(id)}, {'$set': update_doc})
        return jsonify({'message': 'Order status updated'})
    except Exception as e:
        return json_error(str(e), 400)

@app.route('/api/orders/stats')
@shipping_required
def get_order_stats():
    """Get order statistics"""
    database = db.get_db_connection()
    
    pipeline = [
        {'$group': {
            '_id': '$status',
            'count': {'$sum': 1}
        }}
    ]
    res = list(database.orders.aggregate(pipeline))
    
    stats = {
        'pending': 0, 'confirmed': 0, 'packed': 0, 'shipped': 0, 
        'in_transit': 0, 'out_for_delivery': 0, 'delivered': 0, 'total': 0
    }
    
    for r in res:
        status = r['_id']
        if status in stats:
            stats[status] = r['count']
        stats['total'] += r['count']
        
    return jsonify(stats)

# ==================== CATCH-ALL STATIC FILES (must be last!) ====================
@app.route('/<path:path>')
def static_files(path):
    public_paths = ['admin/login.html', 'customer/login.html', 'customer/register.html', 'style.css', 'app.js', 'logo.png', 'css/', 'js/', 'store/', 'uploads/']
    is_public = any(path.startswith(p) or path == p for p in public_paths)
    
    if is_public or path.startswith('html5-qrcode'):
        return send_from_directory('static', path)
    
    if 'user_id' not in session:
        if path.endswith('.html'):
            if path.startswith('customer/'):
                return redirect('/customer/login.html')
            return redirect('/admin/login')
    
    return send_from_directory('static', path)

if __name__ == '__main__':
    # Ensure indexes (best effort on startup)
    try:
        from pymongo import ASCENDING, TEXT
        dbapi = db.get_db_connection()
        if dbapi:
            dbapi.books.create_index([('title', TEXT), ('author', TEXT), ('barcode', ASCENDING)])
            dbapi.users.create_index('email', unique=True)
            dbapi.customers.create_index('phone')
            dbapi.sales.create_index('sale_date')
    except:
        pass
        
    app.run(debug=True, host='0.0.0.0', port=5000)
