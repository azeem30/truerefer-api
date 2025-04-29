import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from datetime import timedelta

load_dotenv()

# Encryption key
KEY = os.getenv("KEY")
FERNET = Fernet(KEY.encode()) if KEY else None

# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = os.getenv("GMAIL_ADDRESS")
SMTP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
EMAIL_FROM = os.getenv("GMAIL_ADDRESS")

# JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION = timedelta(hours=1)

# Dropbox configuration
DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN")
DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
DROPBOX_BASE_PATH = "/truerefer"

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'Azeem@123'),
    'database': os.getenv('DB_NAME', 'truerefer')
}