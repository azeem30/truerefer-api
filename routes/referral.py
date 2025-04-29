from flask import jsonify, request
from db_utils import get_db_connection
import random
import string
import time

def generate_referral_id():
    """Generate a unique 10-character referral ID without database checks"""
    timestamp_part = str(int(time.time() * 1000))[-5:]
    random_part = ''.join(random.choices(
        string.ascii_uppercase + string.digits, 
        k=5
    ))
    referral_id = (timestamp_part + random_part)[:10]
    return referral_id

def register_referral_routes(app, db_pool):
    @app.route("/grant_referral", methods=["POST"])
    def grant_referral():
        try:
            data = request.get_json()
            required_fields = ['referred_by', 'referred', 'referred_via', 'referred_at']
            if not all(field in data for field in required_fields):
                return jsonify({"error": "Missing required fields"}), 400
            referral_id = generate_referral_id()
            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("""
                    INSERT INTO referrals 
                    (id, referred_by, referred, referred_at, referred_via)
                    VALUES (%s, %s, %s, %s, %s)
                    """, (
                    referral_id,
                    data['referred_by'],
                    data['referred'],
                    data['referred_at'],
                    data['referred_via']
                    ))
                    connection.commit()
            return jsonify({
                "success": True,
                "referral_id": referral_id,
                "message": "Referral granted successfully"
            }), 201
        except Exception as e:
            app.logger.error(f"Error granting referral: {str(e)}")
            return jsonify({"error": str(e)}), 500