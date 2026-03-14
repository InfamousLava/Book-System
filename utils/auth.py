from functools import wraps
from flask import session, jsonify

def json_error(msg, status=400):
    return jsonify({'error': msg}), status

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return json_error('Unauthorized', 401)
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            return json_error('Admin access required', 403)
        return f(*args, **kwargs)
    return decorated_function

def inventory_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        role = session.get('role')
        if not role:
             return json_error('Not logged in', 401)
        if role not in ['admin', 'inventory_manager']:
            return json_error(f'Access denied. Your role ({role}) cannot perform this action.', 403)
        return f(*args, **kwargs)
    return decorated_function

def shipping_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        role = session.get('role')
        if not role:
             return json_error('Not logged in', 401)
        if role not in ['admin', 'shipping_manager']:
            return json_error(f'Access denied. Your role ({role}) cannot perform this action.', 403)
        return f(*args, **kwargs)
    return decorated_function
