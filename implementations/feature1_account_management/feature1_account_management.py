from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash
import os
import re
import uuid
from datetime import datetime, timedelta
import jwt

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'prod-super-long-random-key-here')

# PostgreSQL configuration
db_config = {
    'host': os.getenv('DB_HOST', 'postgres'),
    'user': os.getenv('DB_USER', 'foodfast'),
    'password': os.getenv('DB_PASSWORD', 'foodfast123'),
    'database': os.getenv('DB_NAME', 'foodfast_db'),
    'port': os.getenv('DB_PORT', 5432)
}

def get_db_connection():
    """Create a new database connection."""
    try:
        return psycopg2.connect(**db_config)
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def validate_email(email):
    """Validate email format."""
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(email_regex, email) is not None

def generate_token(user_id):
    """Generate JWT token."""
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def verify_token(token):
    """Verify JWT token."""
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None



# Health check endpoint
@app.route("/health", methods=["GET"])
def health():
    conn = get_db_connection()
    if conn:
        conn.close()
        return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 500



# Create a new user
@app.route("/users/register", methods=["POST"])
def register_user():
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400

    
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password")
    role = data.get("role", "customer")
    phone = data.get("phone", "").strip()

        # Validation
    if not name or len(name) < 2:
        return jsonify({"message": "Name must be at least 2 characters"}), 400
    
    if not email or not validate_email(email):
        return jsonify({"message": "Valid email required"}), 400
    
    if not password or len(password) < 6:
        return jsonify({"message": "Password must be at least 6 characters"}), 400
    
    if role not in ['customer', 'restaurant', 'driver', 'admin']:
        return jsonify({"message": "Invalid role"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Database connection error"}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"message": "Email already registered"}), 400
        
        hashed_password = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (role, name, email, password_hash, phone) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (role, name, email, hashed_password, phone if phone else None)
        )
        user_id = cursor.fetchone()[0]
        conn.commit()
        
        # Generate token
        token = generate_token(user_id)
        return jsonify({
            "message": "User registered successfully",
            "user": {
                "id": user_id,
                "name": name,
                "email": email,
                "role": role
            },
            "token": token
        }), 201
    
    except psycopg2.Error as err:
        conn.rollback()
        return jsonify({"message": f"Database error: {str(err)}"}), 500
    finally:
        cursor.close()
        conn.close()

#user login
@app.route("/users/login", methods=["POST"])
def login_user():
    data = request.get_json()
    
    if not data:
        return jsonify({"message": "No data provided"}), 400
    
    email = data.get("email", "").strip().lower()
    password = data.get("password")
    
    if not email or not password:
        return jsonify({"message": "Email and password required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Database connection failed"}), 500

    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute(
            "SELECT id, role, name, email, password_hash FROM users WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password_hash'], password):
            token = generate_token(user['id'])
            return jsonify({
                "message": "Login successful",
                "user": {
                    "id": user['id'],
                    "name": user['name'],
                    "email": user['email'],
                    "role": user['role']
                },
                "token": token
            }), 200
        else:
            return jsonify({"message": "Invalid credentials"}), 401
            
    except psycopg2.Error as err:
        return jsonify({"message": f"Database error: {str(err)}"}), 500
    finally:
        cursor.close()
        conn.close()

# Get user profile
@app.route("/users/profile", methods=["GET"])
def get_user_profile():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({"message": "Token is missing"}), 401
    
    #remove Bearer prefix if present
    if token.startswith('Bearer '):
        token = token[7:]
    
    user_id = verify_token(token)
    if not user_id:
        return jsonify({"message": "Invalid or expired token"}), 401

    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Database connection failed"}), 500

    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute(
            "SELECT id, role, name, email, phone, created_at FROM users WHERE id = %s",
            (user_id,)
        )
        user = cursor.fetchone()
        
        if user:
            return jsonify({
                "user": dict(user),
                "payment_methods": []  # Will be populated when we add payment methods
            }), 200
        else:
            return jsonify({"message": "User not found"}), 404
            
    except psycopg2.Error as err:
        return jsonify({"message": f"Database error: {str(err)}"}), 500
    finally:
        cursor.close()
        conn.close()

# Update user profile
@app.route("/users/profile", methods=["PUT"])
def update_user_profile():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({"message": "Token required"}), 401
    
    if token.startswith('Bearer '):
        token = token[7:]
    
    user_id = verify_token(token)
    if not user_id:
        return jsonify({"message": "Invalid or expired token"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"message": "No data provided"}), 400

    name = data.get("name", "").strip()
    phone = data.get("phone", "").strip()
    current_password = data.get("current_password")
    new_password = data.get("new_password")

    # Build update query dynamically
    update_fields = []
    update_values = []

    if name:
        if len(name) < 2:
            return jsonify({"message": "Name must be at least 2 characters"}), 400
        update_fields.append("name = %s")
        update_values.append(name)

    if phone:
        update_fields.append("phone = %s")
        update_values.append(phone)

    if not update_fields and not new_password:
        return jsonify({"message": "Nothing to update"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Database connection failed"}), 500

    cursor = conn.cursor()
    try:
        # If updating password, verify current password first
        if new_password:
            if not current_password:
                return jsonify({"message": "Current password required"}), 400
            
            if len(new_password) < 6:
                return jsonify({"message": "New password must be at least 6 characters"}), 400
            
            cursor.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
            result = cursor.fetchone()
            if not result or not check_password_hash(result[0], current_password):
                return jsonify({"message": "Current password incorrect"}), 401
            
            hashed_new_password = generate_password_hash(new_password)
            update_fields.append("password_hash = %s")
            update_values.append(hashed_new_password)

        if update_fields:
            update_values.append(user_id)
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
            cursor.execute(query, update_values)
            
            if cursor.rowcount == 0:
                return jsonify({"message": "User not found"}), 404
            
            conn.commit()
            return jsonify({"message": "Profile updated successfully"}), 200
        else:
            return jsonify({"message": "Nothing to update"}), 400

    except psycopg2.Error as err:
        conn.rollback()
        return jsonify({"message": f"Database error: {str(err)}"}), 500
    finally:
        cursor.close()
        conn.close()


# Add payment method
@app.route("/users/payment-methods", methods=["POST"])
def add_payment_method():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({"message": "Token required"}), 401
    
    if token.startswith('Bearer '):
        token = token[7:]
    
    user_id = verify_token(token)
    if not user_id:
        return jsonify({"message": "Invalid or expired token"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"message": "No data provided"}), 400

    card_number = data.get("card_number", "").strip()
    card_holder = data.get("card_holder", "").strip()
    expiry_month = data.get("expiry_month")
    expiry_year = data.get("expiry_year")
    cvv = data.get("cvv", "").strip()

    # Basic validation (in real app, use proper payment processor)
    if not all([card_number, card_holder, expiry_month, expiry_year, cvv]):
        return jsonify({"message": "All payment fields required"}), 400

    # Mock payment method storage (in real app, use tokenization)
    payment_method_id = str(uuid.uuid4())
    
    return jsonify({
        "message": "Payment method added successfully",
        "payment_method": {
            "id": payment_method_id,
            "card_last_four": card_number[-4:],
            "card_holder": card_holder,
            "expiry": f"{expiry_month:02d}/{expiry_year}"
        }
    }), 201


# Delete user
@app.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
        conn.commit()
        return jsonify({"message": "User deleted"}), 200
    except psycopg2.Error as err:
        conn.rollback()
        return jsonify({"message": str(err)}), 500
    finally:
        cursor.close()
        conn.close()



# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"message": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"message": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
