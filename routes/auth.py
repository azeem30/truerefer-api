from flask import jsonify, request
from config import FERNET, KEY, JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION
from db_utils import get_db_connection
from email_utils import send_verification_email
import uuid
from datetime import datetime, timedelta
import jwt

def register_auth_routes(app, db_pool):
    def encrypt_password(password):
        cipher_suite = FERNET
        encrypted_password = cipher_suite.encrypt(password.encode())
        return encrypted_password

    def decrypt_password(password, key):
        cipher_suite = FERNET
        decrypted_password = cipher_suite.decrypt(password).decode()
        return decrypted_password

    @app.route("/signup", methods=["POST"])
    def signup():
        """Register the user on the TrueRefer platform."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data provided"}), 400
            if not all(key in data for key in ("email", "contact", "role", "password")):
                return jsonify({"error": "Missing required fields"}), 400
            email = data["email"]
            phone = data["contact"]
            user_type = data["role"]
            password = data["password"]
            if user_type not in ["student", "referrer", "moderator"]:
                return jsonify({"error": "Invalid type"}), 400
            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor: 
                    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                    if cursor.fetchone():
                        return jsonify({"error": "Email already exists"}), 400
                    verification_token = str(uuid.uuid4())
                    expiration_time = datetime.now() + timedelta(hours=24)
                    cursor.execute(
                        """INSERT INTO users 
                        (email, phone, password, userType, verified, verification_token, token_expiration) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (email, phone, encrypt_password(password), user_type, 0, verification_token, expiration_time)
                    )
                    connection.commit()
                    if not send_verification_email(email, verification_token, app):
                        return jsonify({"error": "Failed to send verification email"}), 500
            return jsonify({"message": "User created successfully. Please check your email to activate your account."}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/verify-email/<token>", methods=["GET"])
    def verify_email(token):
        """Verify user's email using the token"""
        try:
            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT email FROM users WHERE verification_token = %s AND token_expiration > %s",
                        (token, datetime.now())
                    )
                    user = cursor.fetchone()
                    if not user:
                        return jsonify({"error": "Invalid or expired verification token"}), 400
                    cursor.execute(
                        "UPDATE users SET verified = 1, verification_token = NULL, token_expiration = NULL WHERE verification_token = %s",
                        (token,)
                    )
                    connection.commit()
            return jsonify({"message": "Email verified successfully. Your account is now active."}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/login", methods=["POST"])
    def login():
        """Authenticate user and return JWT token"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data provided"}), 400
            if not all(key in data for key in ("email", "password")):
                return jsonify({"error": "Missing email or password"}), 400
            email = data["email"]
            password = data["password"]
            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT id, email, password, userType, verified FROM users WHERE email = %s",
                        (email,)
                    )
                    user = cursor.fetchone()
                    if not user:
                        return jsonify({"error": "Invalid email or password"}), 401
                    if not user["verified"]:
                        return jsonify({"error": "Account not verified. Please check your email."}), 403
                    try:
                        decrypted_password = decrypt_password(user["password"], KEY)
                        if password != decrypted_password:
                            return jsonify({"error": "Invalid email or password"}), 401
                    except Exception as e:
                        app.logger.error(f"Password decryption failed: {str(e)}")
                        return jsonify({"error": "Authentication failed"}), 500
                    token_payload = {
                        "sub": user["id"],
                        "email": user["email"],
                        "type": user["userType"],
                        "iat": datetime.now(),
                        "exp": datetime.now() + JWT_EXPIRATION
                    }
                    token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
                    return jsonify({
                        "message": "Login successful",
                        "token": token,
                        "user": {
                            "id": user["id"],
                            "email": user["email"],
                            "type": user["userType"]
                        }
                    }), 200
        except Exception as e:
            app.logger.error(f"Login error: {str(e)}")
            return jsonify({"error": str(e)}), 500