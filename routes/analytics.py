from flask import jsonify
from db_utils import get_db_connection

def register_analytics_routes(app, db_pool):
    @app.route("/analytics/platform-growth", methods=["GET"])
    def platform_growth():
        """Show user growth over time"""
        try:
            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT DATE_FORMAT(createdAt, '%Y-%m') AS month, 
                            COUNT(*) AS new_users
                        FROM users
                        GROUP BY month
                        ORDER BY month
                    """)
                    growth_data = cursor.fetchall()
                    cursor.execute("""
                        SELECT COUNT(*) AS total_users,
                            SUM(verified = 1) AS verified_users,
                            (SELECT COUNT(*) FROM user_details) AS profiles_completed
                        FROM users
                    """)
                    totals = cursor.fetchone()
                    return jsonify({
                        "growth_trend": growth_data,
                        "totals": totals
                    }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/analytics/user-demographics", methods=["GET"])
    def user_demographics():
        """Show breakdown of user types and locations"""
        try:
            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT userType, COUNT(*) AS count 
                        FROM users
                        GROUP BY userType
                    """)
                    user_types = cursor.fetchall()
                    cursor.execute("""
                        SELECT country, COUNT(*) AS count
                        FROM user_details
                        GROUP BY country
                        ORDER BY count DESC
                        LIMIT 5
                    """)
                    top_countries = cursor.fetchall()
                    cursor.execute("""
                        SELECT company, COUNT(*) AS referrers
                        FROM user_details
                        WHERE company IS NOT NULL
                        GROUP BY company
                        ORDER BY referrers DESC
                        LIMIT 5
                    """)
                    top_companies = cursor.fetchall()
                    return jsonify({
                        "user_types": user_types,
                        "top_countries": top_countries,
                        "top_companies": top_companies
                    }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/analytics/referral-network", methods=["GET"])
    def referral_network():
        """Show referral network statistics"""
        try:
            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM referrals")
                    total_referrals = cursor.fetchone()["COUNT(*)"]
                    cursor.execute("""
                        SELECT u.email, ud.first_name, ud.last_name, COUNT(*) AS referrals
                        FROM referrals r
                        JOIN users u ON r.referred_by = u.id
                        JOIN user_details ud ON u.id = ud.id
                        GROUP BY r.referred_by
                        ORDER BY referrals DESC
                        LIMIT 5
                    """)
                    top_referrers = cursor.fetchall()
                    cursor.execute("""
                        SELECT referred_via, COUNT(*) AS count
                        FROM referrals
                        GROUP BY referred_via
                    """)
                    referral_channels = cursor.fetchall()
                    return jsonify({
                        "total_referrals": total_referrals,
                        "top_referrers": top_referrers,
                        "referral_channels": referral_channels
                    }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/analytics/engagement", methods=["GET"])
    def engagement_metrics():
        """Show user engagement statistics"""
        try:
            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT DATE_FORMAT(timestamp, '%Y-%m') AS month,
                            COUNT(*) AS messages
                        FROM messages
                        GROUP BY month
                        ORDER BY month
                    """)
                    messaging_activity = cursor.fetchall()
                    cursor.execute("""
                        SELECT COUNT(DISTINCT 
                            LEAST(sender_id, receiver_id),
                            GREATEST(sender_id, receiver_id)
                        ) AS active_conversations
                        FROM messages
                    """)
                    active_conversations = cursor.fetchone()["active_conversations"]
                    cursor.execute("""
                        SELECT 
                            (SELECT COUNT(*) FROM user_details) AS completed,
                            (SELECT COUNT(*) FROM users) AS total,
                            (SELECT COUNT(*) FROM user_details) / (SELECT COUNT(*) FROM users) * 100 AS completion_rate
                    """)
                    completion_stats = cursor.fetchone()
                    
                    return jsonify({
                        "messaging_activity": messaging_activity,
                        "active_conversations": active_conversations,
                        "profile_completion": completion_stats
                    }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/analytics/success-stories", methods=["GET"])
    def success_stories():
        """Show successful referrals with placement details"""
        try:
            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT 
                            r.id AS referral_id,
                            referrer.first_name AS referrer_first_name,
                            referrer.last_name AS referrer_last_name,
                            referrer.company AS referrer_company,
                            referred.first_name AS referred_first_name,
                            referred.last_name AS referred_last_name,
                            r.referred_at,
                            r.referred_via
                        FROM referrals r
                        JOIN user_details referrer ON r.referred_by = referrer.id
                        JOIN user_details referred ON r.referred = referred.id
                        ORDER BY r.referred_at DESC
                        LIMIT 5
                    """)
                    success_stories = cursor.fetchall()
                    
                    return jsonify({
                        "success_stories": success_stories,
                        "count": len(success_stories)
                    }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/analytics/college-stats", methods=["GET"])
    def college_stats():
        """Show statistics by educational institutions"""
        try:
            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT college, COUNT(*) AS students
                        FROM user_details
                        WHERE college IS NOT NULL
                        GROUP BY college
                        ORDER BY students DESC
                        LIMIT 5
                    """)
                    top_colleges = cursor.fetchall()
                    cursor.execute("""
                        SELECT college, company, COUNT(*) AS hires
                        FROM user_details
                        WHERE college IS NOT NULL AND company IS NOT NULL
                        GROUP BY college, company
                        ORDER BY college, hires DESC
                    """)
                    college_hiring = cursor.fetchall()
                    
                    return jsonify({
                        "top_colleges": top_colleges,
                        "college_hiring_patterns": college_hiring
                    }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500