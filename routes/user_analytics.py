from flask import jsonify, g, request
from db_utils import get_db_connection
import uuid

def register_user_analytics_routes(app, db_pool):
    @app.route("/analytics/profile-completeness", methods=["GET"])
    def profile_completeness():
        """Show the user's profile completion status"""
        try:
            user_id = request.args.get('user_id')  
            if not user_id:
                return jsonify({"error": "User not authenticated"}), 401

            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT 
                            first_name, middle_name, last_name, college, company, 
                            experience, designation, country, profile_picture, 
                            resume, linkedin, degree, start_year, end_year
                        FROM user_details
                        WHERE id = %s
                    """, (user_id,))
                    details = cursor.fetchone()

                    # Calculate completion status
                    completion_stats = {
                        "total_fields": 14,  # Total fields in user_details
                        "filled_fields": 0,
                        "missing_fields": []
                    }

                    if details:
                        for field, value in details.items():
                            if value is not None and value != '':
                                completion_stats["filled_fields"] += 1
                            else:
                                completion_stats["missing_fields"].append(field)
                        completion_stats["completion_percentage"] = (
                            completion_stats["filled_fields"] / completion_stats["total_fields"] * 100
                        )
                    else:
                        completion_stats["missing_fields"] = [
                            "first_name", "middle_name", "last_name", "college", "company",
                            "experience", "designation", "country", "profile_picture",
                            "resume", "linkedin", "degree", "start_year", "end_year"
                        ]
                        completion_stats["completion_percentage"] = 0

                    return jsonify({
                        "profile_completeness": completion_stats
                    }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/analytics/referral-activity", methods=["GET"])
    def referral_activity():
        """Show the user's referral statistics"""
        try:
            user_id = request.args.get('user_id')  
            if not user_id:
                return jsonify({"error": "User not authenticated"}), 401

            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    # Total referrals made
                    cursor.execute("""
                        SELECT COUNT(*) AS referral_count
                        FROM referrals
                        WHERE referred_by = %s
                    """, (user_id,))
                    total_referrals = cursor.fetchone()["referral_count"]

                    # Referral success (e.g., referred users who are verified)
                    cursor.execute("""
                        SELECT COUNT(*) AS successful_referrals
                        FROM referrals r
                        JOIN users u ON r.referred = u.id
                        WHERE r.referred_by = %s AND u.verified = 1
                    """, (user_id,))
                    successful_referrals = cursor.fetchone()["successful_referrals"]

                    # Referral methods
                    cursor.execute("""
                        SELECT referred_via, COUNT(*) AS count
                        FROM referrals
                        WHERE referred_by = %s
                        GROUP BY referred_via
                    """, (user_id,))
                    referral_methods = cursor.fetchall()

                    return jsonify({
                        "total_referrals": total_referrals,
                        "successful_referrals": successful_referrals,
                        "referral_methods": referral_methods
                    }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/analytics/network-insights", methods=["GET"])
    def network_insights():
        """Show the user's referral network"""
        try:
            user_id = request.args.get('user_id')  
            if not user_id:
                return jsonify({"error": "User not authenticated"}), 401

            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    # Users referred by this user
                    cursor.execute("""
                        SELECT 
                            r.id AS referral_id, 
                            u.email, 
                            ud.first_name, 
                            ud.last_name, 
                            r.referred_at, 
                            r.referred_via
                        FROM referrals r
                        JOIN users u ON r.referred = u.id
                        LEFT JOIN user_details ud ON u.id = ud.id
                        WHERE r.referred_by = %s
                        ORDER BY r.referred_at DESC
                        LIMIT 10
                    """, (user_id,))
                    referred_users = cursor.fetchall()

                    # Users who referred this user
                    cursor.execute("""
                        SELECT 
                            r.id AS referral_id, 
                            u.email, 
                            ud.first_name, 
                            ud.last_name, 
                            r.referred_at, 
                            r.referred_via
                        FROM referrals r
                        JOIN users u ON r.referred_by = u.id
                        LEFT JOIN user_details ud ON u.id = ud.id
                        WHERE r.referred = %s
                        ORDER BY r.referred_at DESC
                        LIMIT 10
                    """, (user_id,))
                    referrers = cursor.fetchall()

                    return jsonify({
                        "referred_users": referred_users,
                        "referrers": referrers
                    }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/analytics/demographic-comparison", methods=["GET"])
    def demographic_comparison():
        """Compare user's demographics to platform trends"""
        try:
            user_id = request.args.get('user_id')  
            if not user_id:
                return jsonify({"error": "User not authenticated"}), 401

            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    # Get user's demographics
                    cursor.execute("""
                        SELECT country, college, company
                        FROM user_details
                        WHERE id = %s
                    """, (user_id,))
                    user_demographics = cursor.fetchone()

                    # Platform-wide country distribution
                    cursor.execute("""
                        SELECT country, COUNT(*) AS count
                        FROM user_details
                        WHERE country IS NOT NULL
                        GROUP BY country
                        ORDER BY count DESC
                        LIMIT 5
                    """, ())
                    country_distribution = cursor.fetchall()

                    # Platform-wide college distribution
                    cursor.execute("""
                        SELECT college, COUNT(*) AS count
                        FROM user_details
                        WHERE college IS NOT NULL
                        GROUP BY college
                        ORDER BY count DESC
                        LIMIT 5
                    """, ())
                    college_distribution = cursor.fetchall()

                    # Platform-wide company distribution
                    cursor.execute("""
                        SELECT company, COUNT(*) AS count
                        FROM user_details
                        WHERE company IS NOT NULL
                        GROUP BY company
                        ORDER BY count DESC
                        LIMIT 5
                    """, ())
                    company_distribution = cursor.fetchall()

                    return jsonify({
                        "user_demographics": user_demographics or {},
                        "platform_trends": {
                            "country_distribution": country_distribution,
                            "college_distribution": college_distribution,
                            "company_distribution": company_distribution
                        }
                    }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500