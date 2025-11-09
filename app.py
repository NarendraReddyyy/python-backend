from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': int(os.getenv('DB_PORT'))
}

def get_db_connection():
    """Create and return a database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def init_database():
    """Initialize the database and create table if not exists"""
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            # Create database if not exists
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
            cursor.execute(f"USE {DB_CONFIG['database']}")
            
            # Create users table
            create_table_query = """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                age INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """
            cursor.execute(create_table_query)
            connection.commit()
            print("Database and table created successfully")
        except Error as e:
            print(f"Error creating database/table: {e}")
        finally:
            cursor.close()
            connection.close()

# Initialize database on startup
init_database()

@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        "message": "User Management API is running!",
        "endpoints": {
            "GET /api/users": "Get all users",
            "GET /api/users/<id>": "Get user by ID",
            "POST /api/users": "Create new user",
            "PUT /api/users/<id>": "Update user",
            "DELETE /api/users/<id>": "Delete user"
        }
    })

@app.route('/api/users', methods=['GET'])
def get_users():
    """GET: Retrieve all users"""
    connection = get_db_connection()
    if not connection:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
        users = cursor.fetchall()
        
        # Convert datetime objects to strings for JSON serialization
        for user in users:
            if user['created_at']:
                user['created_at'] = user['created_at'].isoformat()
            if user['updated_at']:
                user['updated_at'] = user['updated_at'].isoformat()
        
        return jsonify({
            "success": True,
            "data": users,
            "count": len(users)
        })
    except Error as e:
        return jsonify({"error": f"Failed to fetch users: {str(e)}"}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """GET: Retrieve a specific user by ID"""
    connection = get_db_connection()
    if not connection:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Convert datetime objects to strings
        if user['created_at']:
            user['created_at'] = user['created_at'].isoformat()
        if user['updated_at']:
            user['updated_at'] = user['updated_at'].isoformat()
        
        return jsonify({
            "success": True,
            "data": user
        })
    except Error as e:
        return jsonify({"error": f"Failed to fetch user: {str(e)}"}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/users', methods=['POST'])
def create_user():
    """POST: Create a new user"""
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['name', 'email']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"'{field}' is required"}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor()
        insert_query = """
        INSERT INTO users (name, email, age) 
        VALUES (%s, %s, %s)
        """
        cursor.execute(insert_query, (
            data['name'],
            data['email'],
            data.get('age')
        ))
        connection.commit()
        
        user_id = cursor.lastrowid
        
        return jsonify({
            "success": True,
            "message": "User created successfully",
            "data": {
                "id": user_id,
                "name": data['name'],
                "email": data['email'],
                "age": data.get('age')
            }
        }), 201
    except mysql.connector.IntegrityError:
        return jsonify({"error": "Email already exists"}), 409
    except Error as e:
        return jsonify({"error": f"Failed to create user: {str(e)}"}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """PUT: Update an existing user"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor()
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            return jsonify({"error": "User not found"}), 404
        
        # Build dynamic update query
        update_fields = []
        values = []
        
        if 'name' in data:
            update_fields.append("name = %s")
            values.append(data['name'])
        
        if 'email' in data:
            update_fields.append("email = %s")
            values.append(data['email'])
        
        if 'age' in data:
            update_fields.append("age = %s")
            values.append(data['age'])
        
        if not update_fields:
            return jsonify({"error": "No valid fields to update"}), 400
        
        values.append(user_id)
        update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
        
        cursor.execute(update_query, values)
        connection.commit()
        
        return jsonify({
            "success": True,
            "message": "User updated successfully",
            "updated_fields": list(data.keys())
        })
    except mysql.connector.IntegrityError:
        return jsonify({"error": "Email already exists"}), 409
    except Error as e:
        return jsonify({"error": f"Failed to update user: {str(e)}"}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """DELETE: Remove a user"""
    connection = get_db_connection()
    if not connection:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor()
        
        # Check if user exists
        cursor.execute("SELECT name, email FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Delete the user
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        connection.commit()
        
        return jsonify({
            "success": True,
            "message": f"User '{user[0]}' ({user[1]}) deleted successfully"
        })
    except Error as e:
        return jsonify({"error": f"Failed to delete user: {str(e)}"}), 500
    finally:
        cursor.close()
        connection.close()

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)