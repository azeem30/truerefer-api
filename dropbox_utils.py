import dropbox
from dropbox import Dropbox
from dropbox.exceptions import AuthError, ApiError
from config import DROPBOX_ACCESS_TOKEN, DROPBOX_BASE_PATH
from datetime import datetime
from werkzeug.utils import secure_filename
import uuid

def get_dropbox_client():
    """Initialize and return a validated Dropbox client"""
    if not DROPBOX_ACCESS_TOKEN:
        raise ValueError("Dropbox access token not configured")
    
    try:
        dbx = Dropbox(DROPBOX_ACCESS_TOKEN)
        dbx.users_get_current_account()
        return dbx
    except AuthError as e:
        raise ValueError(f"Token validation failed: {e}")
    except Exception as e:
        raise Exception(f"Dropbox connection error: {e}")

def upload_to_dropbox(file, file_type, user_id):
    """Upload file to Dropbox and return public URL"""
    dbx = get_dropbox_client()
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    ext = os.path.splitext(file.filename)[1].lower()
    if file_type == "profile_picture":
        folder = f"{DROPBOX_BASE_PATH}/profile_pictures"
        filename = f"profile_{user_id}_{timestamp}{ext}"
    elif file_type == "resume":
        folder = f"{DROPBOX_BASE_PATH}/resumes"
        filename = f"resume_{user_id}_{timestamp}{ext}"
    else:
        raise ValueError("Invalid file type")
    
    dropbox_path = f"{folder}/{filename}"
    
    try:
        file.seek(0)
        dbx.files_upload(file.read(), dropbox_path, mode=dropbox.files.WriteMode("overwrite"))
        shared_link = dbx.sharing_create_shared_link_with_settings(dropbox_path)
        download_url = shared_link.url.replace('?dl=0', '?raw=1')
        return download_url
    except ApiError as e:
        raise ApiError(f"Dropbox API error: {str(e)}")
    except Exception as e:
        raise Exception(f"Error uploading to Dropbox: {str(e)}")

def upload_attachment_to_dropbox(attachment):
    """
    Uploads an attachment to Dropbox and returns a shareable download URL
    """
    if not attachment or attachment.filename == '':
        raise ValueError("No file provided or empty filename")
    try:
        dbx = get_dropbox_client()
        filename = secure_filename(attachment.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        dropbox_path = f"/truerefer/attachments/{unique_filename}"
        file_content = attachment.read()
        dbx.files_upload(file_content, dropbox_path)
        shared_link = dbx.sharing_create_shared_link(dropbox_path).url
        return shared_link
    except AuthError as e:
        raise AuthError(f"Dropbox authentication failed: {str(e)}")
    except ApiError as e:
        raise ApiError(f"Dropbox API error: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to upload attachment: {str(e)}")