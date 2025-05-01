from flask import jsonify, request, url_for
from db_utils import get_db_connection
from dropbox_utils import upload_attachment_to_dropbox
from dropbox.exceptions import AuthError, ApiError
import redis
import json
import uuid
from datetime import datetime

def register_chat_routes(app, db_pool, redis_pool):
    SESSION_TTL = 1800

    def get_session_key(user_id1, user_id2):
        """Generate a consistent session key for two users"""
        sorted_ids = sorted([int(user_id1), int(user_id2)])
        return f"chat_session:{sorted_ids[0]}:{sorted_ids[1]}"

    def flush_messages_to_db(session_key, connection):
        """Flush cached messages from Redis to MySQL"""
        try:
            r = redis.Redis(connection_pool=redis_pool)
            messages = r.lrange(session_key, 0, -1)
            if not messages:
                return
            app.logger.info(f"Flushing {len(messages)} messages to DB for session: {session_key}")
            
            with connection.cursor() as cursor:
                for msg in messages:
                    try:
                        # Handle both bytes and string messages
                        if isinstance(msg, bytes):
                            msg_data = json.loads(msg.decode('utf-8'))
                        else:
                            msg_data = json.loads(msg)
                            
                        cursor.execute(
                            """INSERT INTO messages 
                            (sender_id, receiver_id, message, attachment_url, timestamp) 
                            VALUES (%s, %s, %s, %s, %s)""",
                            (
                                msg_data['sender_id'],
                                msg_data['receiver_id'],
                                msg_data['message'],
                                msg_data.get('attachment_url'),
                                msg_data['timestamp']
                            )
                        )
                    except json.JSONDecodeError as e:
                        app.logger.error(f"Failed to decode message: {msg}. Error: {str(e)}")
                        continue
                connection.commit()
            r.delete(session_key)
        except Exception as e:
            app.logger.error(f"Error flushing messages to DB: {str(e)}")
            connection.rollback()
            raise

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
        """Get all messages between two users, including cached messages from Redis"""
        try:
            sender_id = request.args.get('sender_id')
            receiver_id = request.args.get('receiver_id')
            if not sender_id or not receiver_id:
                return jsonify({"error": "Both sender_id and receiver_id are required"}), 400
                
            session_key = get_session_key(sender_id, receiver_id)
            r = redis.Redis(connection_pool=redis_pool)
            
            # Get cached messages from Redis
            cached_messages = []
            try:
                raw_messages = r.lrange(session_key, 0, -1)
                for msg in raw_messages:
                    try:
                        if isinstance(msg, bytes):
                            msg_data = json.loads(msg.decode('utf-8'))
                        else:
                            msg_data = json.loads(msg)
                            
                        cached_messages.append({
                            'id': None,  # Indicates it's a cached message
                            'sender_id': msg_data['sender_id'],
                            'receiver_id': msg_data['receiver_id'],
                            'message': msg_data['message'],
                            'timestamp': msg_data['timestamp'],
                            'attachment_url': msg_data.get('attachment_url'),
                            'sender': {
                                'first_name': None,  # Will be filled from DB
                                'middle_name': None,
                                'last_name': None,
                                'profile_picture': None
                            },
                            'receiver': {
                                'first_name': None,
                                'middle_name': None,
                                'last_name': None,
                                'profile_picture': None
                            }
                        })
                    except (json.JSONDecodeError, KeyError) as e:
                        app.logger.error(f"Invalid message format in Redis: {msg}. Error: {str(e)}")
                        continue
            except redis.RedisError as e:
                app.logger.error(f"Redis error: {str(e)}")
                # Continue with DB fetch even if Redis fails

            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    # Get messages from database
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
                    db_messages = cursor.fetchall()
                    
                    formatted_messages = []
                    for msg in db_messages:
                        formatted_messages.append({
                            'id': msg['id'],
                            'sender_id': msg['sender_id'],
                            'receiver_id': msg['receiver_id'],
                            'message': msg['message'],
                            'timestamp': msg['timestamp'].isoformat() if msg['timestamp'] else None,
                            'attachment_url': msg['attachment_url'],
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
                        })
                    
                    # Combine and sort all messages
                    all_messages = formatted_messages + cached_messages
                    all_messages.sort(key=lambda x: x['timestamp'])
                    
                    return jsonify(all_messages), 200
        except Exception as e:
            app.logger.error(f"Error fetching messages: {str(e)}", exc_info=True)
            return jsonify({'error': 'An error occurred while fetching messages'}), 500

    @app.route("/send_messages", methods=["POST"])
    def send_message():
        """Send a message between two users with optional attachment, cache in Redis"""
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
            session_key = get_session_key(sender_id, receiver_id)
            print(f"[SESSION STARTED] sender_id: {sender_id}, receiver_id: {receiver_id}, session_key: {session_key}")
            r = redis.Redis(connection_pool=redis_pool)
            message_data = {
                'sender_id': sender_id,
                'receiver_id': receiver_id,
                'message': message,
                'timestamp': datetime.utcnow().isoformat(),
            }
            if attachment_url:
                message_data['attachment_url'] = attachment_url
            r.rpush(session_key, json.dumps(message_data))
            r.expire(session_key, SESSION_TTL)  # Refresh TTL
            return jsonify({
                "message": message,
                "sender_id": sender_id,
                "receiver_id": receiver_id,
                "attachment_url": attachment_url
            }), 201
        except Exception as e:
            app.logger.error(f"Error sending message: {str(e)}")
            return jsonify({"error": "Internal server error"}), 500

    @app.route("/end_chat_session", methods=["POST"])
    def end_chat_session():
        """End a chat session and flush cached messages to MySQL"""
        try:
            data = request.get_json()
            sender_id = data.get('sender_id')
            receiver_id = data.get('receiver_id')
            
            if not sender_id or not receiver_id:
                return jsonify({"error": "Both sender_id and receiver_id are required"}), 400

            session_key = get_session_key(sender_id, receiver_id)
            app.logger.info(f"Ending chat session: {session_key}")
            
            with get_db_connection(db_pool) as connection:
                flush_messages_to_db(session_key, connection)
                return jsonify({"message": "Chat session ended and messages saved"}), 200
        except Exception as e:
            app.logger.error(f"Error ending chat session: {str(e)}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500