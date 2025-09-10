from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Configure PostgreSQL connection
db_config = {
    'host': 'postgres',
    'user': 'foodfast',
    'password': 'foodfast123',
    'dbname': 'foodfast_db'
}

def get_db_connection():
    return psycopg2.connect(**db_config)




# Create a new account
@app.route("/accounts", methods=["POST"])
def create_account():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"message": "Username and password required"}), 400

    hashed_password = generate_password_hash(password)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO accounts (username, password) VALUES (%s, %s)",
            (username, hashed_password)
        )
        conn.commit()
        return jsonify({"message": "Account created", "username": username}), 201
    except psycopg2.Error as err:
        return jsonify({"message": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# Get account details
@app.route("/accounts/<int:account_id>", methods=["GET"])
def get_account(account_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT id, username FROM accounts WHERE id = %s", (account_id,))
    account = cursor.fetchone()
    cursor.close()
    conn.close()
    if account:
        return jsonify({"message": "Account retrieved", "account": dict(account)}), 200
    else:
        return jsonify({"message": "Account not found"}), 404

# Update an account
@app.route("/accounts/<int:account_id>", methods=["PUT"])
def update_account(account_id):
    data = request.json
    username = data.get("username")
    password = data.get("password")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if password:
            hashed_password = generate_password_hash(password)
            cursor.execute(
                "UPDATE accounts SET username=%s, password=%s WHERE id=%s",
                (username, hashed_password, account_id)
            )
        else:
            cursor.execute(
                "UPDATE accounts SET username=%s WHERE id=%s",
                (username, account_id)
            )
        conn.commit()
        return jsonify({"message": "Account updated", "account_id": account_id}), 200
    except psycopg2.Error as err:
        return jsonify({"message": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# Delete an account
@app.route("/accounts/<int:account_id>", methods=["DELETE"])
def delete_account(account_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM accounts WHERE id=%s", (account_id,))
        conn.commit()
        return jsonify({"message": "Account deleted", "account_id": account_id}), 200
    except psycopg2.Error as err:
        return jsonify({"message": str(err)}), 500
    finally:
        cursor.close()
        conn.close()