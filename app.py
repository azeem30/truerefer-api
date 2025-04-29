from flask import Flask
from flask_cors import CORS
from db_utils import create_db_pool
from routes.auth import register_auth_routes
from routes.profile import register_profile_routes
from routes.chat import register_chat_routes
from routes.referral import register_referral_routes
from routes.analytics import register_analytics_routes
from routes.user_analytics import register_user_analytics_routes
import os

app = Flask(__name__)
CORS(app)

db_pool = create_db_pool()

register_auth_routes(app, db_pool)
register_profile_routes(app, db_pool)
register_chat_routes(app, db_pool)
register_referral_routes(app, db_pool)
register_analytics_routes(app, db_pool)
register_user_analytics_routes(app, db_pool)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)