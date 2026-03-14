import re

def sanitize_input(value, max_length=500):
    """Sanitize string input to prevent XSS and limit length"""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    value = str(value).strip()[:max_length]
    value = re.sub(r'[<>]', '', value)
    return value

def validate_email(email):
    """Validate email format"""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_phone(phone):
    """Validate phone number format"""
    if not phone:
        return True
    pattern = r'^[\d\s\-\+]{7,20}$'
    return bool(re.match(pattern, phone))

def validate_positive_number(value):
    try:
        num = float(value)
        return num >= 0
    except (ValueError, TypeError):
        return False

def validate_integer_id(value):
    return True # Allow strings for ObjectId

def json_error(msg, status=400):
    from flask import jsonify
    return jsonify({'error': msg}), status
