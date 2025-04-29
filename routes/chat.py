from flask import jsonify, request, url_for
from db_utils import get_db_connection
from dropbox_utils import upload_attachment_to_dropbox
from dropbox.exceptions import AuthError, ApiError

def register_chat_routes(app, db_pool):
    @app.route("/chat_list", methods=["GET"])
    def chat_list():
        """Get list of all distinct users the current user has chatted with, along with latest message"""
        try:
            user_id = request.args.get('id')
            if not user_id:
                return jsonify({"error": "User ID is required"}), 400
            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    query = """
                    SELECT 
                        m.id as message_id,
                        m.message,
                        m.timestamp,
                        CASE 
                            WHEN m.sender_id = %s THEN m.receiver_id
                            ELSE m.sender_id
                        END as partner_id,
                        MAX(m.timestamp) OVER (PARTITION BY 
                            CASE 
                                WHEN m.sender_id = %s THEN m.receiver_id
                                ELSE m.sender_id
                            END
                        ) as latest_timestamp
                    FROM messages m
                    WHERE m.sender_id = %s OR m.receiver_id = %s
                    ORDER BY latest_timestamp DESC
                    """
                    cursor.execute(query, (user_id, user_id, user_id, user_id))
                    messages = cursor.fetchall()
                    partners = {}
                    for msg in messages:
                        partner_id = msg['partner_id']
                        if partner_id not in partners or msg['timestamp'] == msg['latest_timestamp']:
                            partners[partner_id] = {
                                'latest_message': msg['message'],
                                'timestamp': msg['timestamp'].isoformat() if msg['timestamp'] else None,
                                'message_id': msg['message_id']
                            }
                    if not partners:
                        return jsonify([])
                    partner_ids = list(partners.keys())
                    format_strings = ','.join(['%s'] * len(partner_ids))
                    user_query = f"""
                    SELECT 
                        ud.id,
                        ud.first_name,
                        ud.middle_name,
                        ud.last_name,
                        ud.designation,
                        ud.company,
                        ud.profile_picture
                    FROM user_details ud
                    WHERE ud.id IN ({format_strings})
                    """
                    cursor.execute(user_query, tuple(partner_ids))
                    user_details = cursor.fetchall()
                    result = []
                    for user in user_details:
                        partner_id = user['id']
                        result.append({
                            'id': partner_id,
                            'first_name': user['first_name'],
                            'middle_name': user['middle_name'],
                            'last_name': user['last_name'],
                            'designation': user['designation'],
                            'company': user['company'],
                            'profile_picture': user['profile_picture'] or url_for('static', filename='default_profile.png', _external=True),
                            'latest_message': partners[partner_id]['latest_message'],
                            'timestamp': partners[partner_id]['timestamp'],
                            'message_id': partners[partner_id]['message_id']
                        })
                    return jsonify(result), 200
        except Exception as e:
            app.logger.error(f"Error in chat_list: {str(e)}")
            return jsonify({'error': 'An error occurred while fetching chat list'}), 500

    @app.route("/messages", methods=["GET"])
    def get_messages():
        """Get all messages between two users"""
        try:
            sender_id = request.args.get('sender_id')
            receiver_id = request.args.get('receiver_id')
            if not sender_id or not receiver_id:
                return jsonify({"error": "Both sender_id and receiver_id are required"}), 400
            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    query = """
                    SELECT 
                        m.id,
                        m.sender_id,
                        m.receiver_id,
                        m.message,
                        m.timestamp,
                        m.attachment_url,
                        sender.first_name as sender_first_name,
                        sender.middle_name as sender_middle_name,
                        sender.last_name as sender_last_name,
                        sender.profile_picture as sender_profile_picture,
                        receiver.first_name as receiver_first_name,
                        receiver.middle_name as receiver_middle_name,
                        receiver.last_name as receiver_last_name,
                        receiver.profile_picture as receiver_profile_picture
                    FROM messages m
                    JOIN user_details sender ON m.sender_id = sender.id
                    JOIN user_details receiver ON m.receiver_id = receiver.id
                    WHERE (m.sender_id = %s AND m.receiver_id = %s)
                    OR (m.sender_id = %s AND m.receiver_id = %s)
                    ORDER BY m.timestamp ASC
                    """
                    cursor.execute(query, (sender_id, receiver_id, receiver_id, sender_id))
                    messages = cursor.fetchall()
                    formatted_messages = []
                    for msg in messages:
                        formatted_message = {
                            'id': msg['id'],
                            'sender_id': msg['sender_id'],
                            'receiver_id': msg['receiver_id'],
                            'message': msg['message'],
                            'timestamp': msg['timestamp'].isoformat() if msg['timestamp'] else None,
                            'attachment_url': msg['attachment_url'] if 'attachment_url' in msg and msg['attachment_url'] else None,
                            'sender': {
                                'first_name': msg['sender_first_name'],
                                'middle_name': msg['sender_middle_name'],
                                'last_name': msg['sender_last_name'],
                                'profile_picture': msg['sender_profile_picture'] or url_for('static', filename='default_profile.png', _external=True)
                            },
                            'receiver': {
                                'first_name': msg['receiver_first_name'],
                                'middle_name': msg['receiver_middle_name'],
                                'last_name': msg['receiver_last_name'],
                                'profile_picture': msg['receiver_profile_picture'] or url_for('static', filename='default_profile.png', _external=True)
                            }
                        }
                        formatted_message = {k: v for k, v in formatted_message.items() if v is not None}
                        formatted_messages.append(formatted_message)
                    return jsonify(formatted_messages), 200
        except Exception as e:
            app.logger.error(f"Error fetching messages: {str(e)}")
            return jsonify({'error': 'An error occurred while fetching messages'}), 500

    @app.route("/send_messages", methods=["POST"])
    def send_message():
        """Send a message between two users with optional attachment"""
        try:
            attachment_url = None
            if 'attachment' in request.files:
                file = request.files['attachment']
                try:
                    attachment_url = upload_attachment_to_dropbox(file)
                except (AuthError, ApiError) as e:
                    app.logger.error(f"Dropbox error: {str(e)}")
                    return jsonify({"error": "File upload service unavailable"}), 503
                except ValueError as e:
                    return jsonify({"error": str(e)}), 400
                except Exception as e:
                    app.logger.error(f"Upload failed: {str(e)}")
                    return jsonify({"error": "File upload failed"}), 500
            sender_id = request.form.get('sender_id') or request.json.get('sender_id')
            receiver_id = request.form.get('receiver_id') or request.json.get('receiver_id')
            message = request.form.get('message', '') or request.json.get('message', '')
            if not all([sender_id, receiver_id]):
                return jsonify({"error": "Missing required fields"}), 400
            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    if attachment_url:
                        cursor.execute(
                            """INSERT INTO messages 
                            (sender_id, receiver_id, message, attachment_url) 
                            VALUES (%s, %s, %s, %s)""",
                            (sender_id, receiver_id, message, attachment_url)
                        )
                    else:
                        cursor.execute(
                            """INSERT INTO messages 
                            (sender_id, receiver_id, message) 
                            VALUES (%s, %s, %s)""",
                            (sender_id, receiver_id, message)
                        )
                    connection.commit()
                    return jsonify({
                        "message": message,
                        "attachment_url": attachment_url
                    }), 201
        except Exception as e:
            app.logger.error(f"Error sending message: {str(e)}")
            return jsonify({"error": "Internal server error"}), 500