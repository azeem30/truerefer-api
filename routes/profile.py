from flask import jsonify, request, url_for
from db_utils import get_db_connection
from dropbox_utils import upload_to_dropbox
from werkzeug.utils import secure_filename

def register_profile_routes(app, db_pool):
    @app.route("/profile", methods=["GET"])
    def get_profile():
        """Get user profile information"""
        try:
            user_id = request.args.get('id')
            if not user_id:
                return jsonify({"error": "User ID is required"}), 400
            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    query = """
                    SELECT 
                        ud.id, ud.first_name, ud.middle_name, ud.last_name, 
                        ud.college, ud.company, ud.experience, ud.designation, 
                        ud.country, ud.profile_picture, ud.resume, ud.linkedin,
                        ud.degree, ud.start_year, ud.end_year
                    FROM user_details ud
                    WHERE ud.id = %s
                    """
                    cursor.execute(query, (user_id,))
                    profile = cursor.fetchone()
                    cursor.close()
                    if not profile:
                        return jsonify({"error": "Profile not found"}), 404
                    response = {
                        "id": profile["id"],
                        "first_name": profile["first_name"],
                        "middle_name": profile["middle_name"],
                        "last_name": profile["last_name"],
                        "designation": profile["designation"],
                        "company": profile["company"],
                        "experience": profile["experience"],
                        "country": profile["country"],
                        "profile_picture": profile["profile_picture"],
                        "resume": profile["resume"],
                        "linkedin": profile["linkedin"],
                        "degree": profile["degree"],
                        "start_year": profile["start_year"],
                        "end_year": profile["end_year"],
                        "college": profile["college"],
                        "role": profile["designation"]
                    }
                    return jsonify(response), 200
            return jsonify({"error": "Profile not found"}), 404
        except Exception as e:
            app.logger.error(f"Error fetching profile: {str(e)}")
            return jsonify({"error": str(e)}), 500

    @app.route("/edit_profile", methods=["POST"])
    def edit_profile():
        """Update user profile information with Dropbox file storage"""
        try:
            form_data = request.form
            profile_picture = request.files.get('profilePicture')
            resume = request.files.get('resume')
            user_id = form_data.get('id')
            if not user_id or user_id == 'undefined':
                return jsonify({"error": "Invalid user ID"}), 400
            update_fields = {
                'first_name': str(form_data.get('firstName', '')),
                'middle_name': str(form_data.get('middleName', '')),
                'last_name': str(form_data.get('lastName', '')),
                'college': str(form_data.get('college', '')),
                'company': str(form_data.get('company', '')),
                'designation': str(form_data.get('role', '')),
                'experience': int(form_data.get('experience', 0)),
                'country': str(form_data.get('location', '')),
                'linkedin': str(form_data.get('linkedinProfile', '')),
                'degree': str(form_data.get('degree', '')),
                'start_year': int(form_data.get('startYear', 0)) if form_data.get('startYear') else None,
                'end_year': int(form_data.get('endYear', 0)) if form_data.get('endYear') else None
            }
            try:
                if profile_picture and profile_picture.filename:
                    if profile_picture.content_length > 10 * 1024 * 1024:
                        return jsonify({"error": "Profile picture must be less than 10MB"}), 400
                    profile_picture_url = upload_to_dropbox(profile_picture, "profile_picture", user_id)
                    update_fields['profile_picture'] = profile_picture_url

                if resume and resume.filename:
                    if resume.content_length > 10 * 1024 * 1024:
                        return jsonify({"error": "Resume must be less than 10MB"}), 400
                    allowed_extensions = {'.pdf', '.doc', '.docx'}
                    ext = os.path.splitext(resume.filename)[1].lower()
                    if ext not in allowed_extensions:
                        return jsonify({"error": "Resume must be PDF or Word document"}), 400
                    resume_url = upload_to_dropbox(resume, "resume", user_id)
                    update_fields['resume'] = resume_url
            except Exception as e:
                return jsonify({"error": f"File upload failed: {str(e)}"}), 500
            update_data = {k: v for k, v in update_fields.items() if v is not None}
            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    try:
                        cursor.execute("SELECT id FROM user_details WHERE id = %s", (user_id,))
                        exists = cursor.fetchone()
                        if exists:
                            set_parts = []
                            values = []
                            for key, value in update_data.items():
                                set_parts.append(f"{key} = %s")
                                values.append(value)
                            values.append(user_id)
                            query = """
                                UPDATE user_details 
                                SET {}
                                WHERE id = %s
                            """.format(", ".join(set_parts))
                            cursor.execute(query, values)
                        else:
                            columns = ["id"] + list(update_data.keys())
                            placeholders = ["%s"] * len(columns)
                            values = [user_id] + list(update_data.values())
                            query = """
                                INSERT INTO user_details ({})
                                VALUES ({})
                            """.format(", ".join(columns), ", ".join(placeholders))
                            cursor.execute(query, values)
                        connection.commit()
                        return jsonify({"message": "Profile updated successfully"}), 200
                    except Exception as db_error:
                        connection.rollback()
                        app.logger.error(f"Database error: {str(db_error)}")
                        return jsonify({"error": "Profile not found"}), 404
            return jsonify({"error": "Profile not found"}), 404
        except Exception as e:
            app.logger.error(f"Error fetching profile: {str(e)}")
            return jsonify({"error": str(e)}), 500

    @app.route("/search_users", methods=["GET"])
    def search_users():
        """Search users by company name"""
        try:
            search_query = request.args.get('q', '').strip()
            if not search_query:
                return jsonify([])
            with get_db_connection(db_pool) as connection:
                with connection.cursor() as cursor:
                    query = """
                    SELECT 
                        ud.id,
                        ud.first_name,
                        ud.middle_name,
                        ud.last_name,
                        ud.designation,
                        ud.company,
                        ud.profile_picture
                    FROM user_details ud
                    WHERE ud.company LIKE %s
                    ORDER BY 
                        CASE 
                            WHEN ud.company = %s THEN 1
                            WHEN ud.company LIKE %s THEN 2
                            ELSE 3
                        END,
                        ud.company
                    LIMIT 50
                    """
                    exact_match = search_query
                    starts_with = f"{search_query}%"
                    contains = f"%{search_query}%"
                    cursor.execute(query, (contains, exact_match, starts_with))
                    results = cursor.fetchall()
                    formatted_results = []
                    for user in results:
                        formatted_results.append({
                            'id': user['id'],
                            'first_name': user['first_name'],
                            'middle_name': user['middle_name'],
                            'last_name': user['last_name'],
                            'designation': user['designation'],
                            'company': user['company'],
                            'profile_picture': user['profile_picture'] or url_for('static', filename='default_profile.png', _external=True)
                        })
                    return jsonify(formatted_results)
        except Exception as e:
            app.logger.error(f"Error in search_users: {str(e)}")
            return jsonify({'error': 'An error occurred during search'}), 500