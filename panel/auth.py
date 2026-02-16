import jwt
import bcrypt
import os
import sys
from functools import wraps
from datetime import datetime, timedelta

# Handle imports
try:
    from flask import request, jsonify
except ImportError:
    pass

try:
    from .db import fetch_one, insert
except ImportError:
    from db import fetch_one, insert

JWT_SECRET = os.environ.get('JWT_SECRET', 'mrm-dev-secret-change-in-production')
JWT_EXPIRY_HOURS = int(os.environ.get('JWT_EXPIRY_HOURS', '24'))

def hash_password(password):
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_jwt_token(user_id, username, role):
    """Create a JWT token."""
    payload = {
        'user_id': user_id,
        'username': username,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def verify_jwt_token(token):
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def token_required(f):
    """Decorator to require valid JWT token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check Authorization header
        if 'Authorization' in request.headers:
            try:
                token = request.headers['Authorization'].split(" ")[1]
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'error': 'Token required'}), 401
        
        payload = verify_jwt_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        request.current_user = payload
        return f(*args, **kwargs)
    
    return decorated

def admin_required(f):
    """Decorator to require admin or superadmin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(request, 'current_user') or not request.current_user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        if request.current_user['role'] not in ('admin', 'superadmin'):
            return jsonify({'error': 'Admin access required'}), 403
        
        return f(*args, **kwargs)
    
    return decorated

def superadmin_required(f):
    """Decorator to require superadmin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(request, 'current_user') or not request.current_user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        if request.current_user['role'] != 'superadmin':
            return jsonify({'error': 'Superadmin access required'}), 403
        
        return f(*args, **kwargs)
    
    return decorated

def authenticate_user(username, password):
    """Authenticate user and return user data if valid."""
    user = fetch_one("SELECT id, username, password_hash, role FROM users WHERE username=%s", (username,))
    
    if not user or not verify_password(password, user['password_hash']):
        return None
    
    return user

def create_root_superadmin(password=None):
    """Create or update the root superadmin user."""
    if password is None:
        password = 'admin123'  # Default for testing; should be changed
    
    password_hash = hash_password(password)
    
    # Check if root exists
    existing = fetch_one("SELECT id FROM users WHERE username=%s", ('root',))
    
    if existing:
        # Update root password
        try:
            from .db import update
        except ImportError:
            from db import update
        update('users', {'password_hash': password_hash}, 'username=%s', ('root',))
        return existing['id']
    else:
        # Create root
        user_id = insert('users', {
            'username': 'root',
            'password_hash': password_hash,
            'role': 'superadmin'
        })
        return user_id
