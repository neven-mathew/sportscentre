app.py
from flask import Flask, render_template, request, redirect
import mysql.connector
from mysql.connector import Error
from datetime import date as d
import os

app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    'host': 'autorack.proxy.rlwy.net',
    'user': 'root',
    'password': 'PRlkjHknXZNbCjcqMbmxqexeHKawUqow',
    'database': 'railway',
    'port': 37887
}

def get_db_connection():
    """Create database connection with error handling"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"MySQL Connection Error: {e}")
        return None

def fix_table_structure():
    """Fix the table structure without dropping data"""
    db = get_db_connection()
    if db is None:
        print("Failed to connect to database")
        return False
    
    cursor = db.cursor()
    
    try:
        # Check current table structure
        cursor.execute("SHOW COLUMNS FROM bookings")
        columns = cursor.fetchall()
        print("Current table structure:", columns)
        
        # Modify the id column to be AUTO_INCREMENT
        cursor.execute("""
            ALTER TABLE bookings 
            MODIFY COLUMN id INT NOT NULL AUTO_INCREMENT
        """)
        db.commit()
        print("Successfully modified id column to AUTO_INCREMENT")
        
        cursor.close()
        db.close()
        return True
        
    except Error as e:
        print(f"Error fixing table structure: {e}")
        db.rollback()
        cursor.close()
        db.close()
        return False

# Try to fix table structure on startup
print("Checking and fixing table structure...")
fix_table_structure()

# --- INDEX ROUTE ---
@app.route('/', methods=['GET'])
def index():
    try:
        db = get_db_connection()
        if db is None:
            return "Database connection failed", 500
        
        cursor = db.cursor()

        # Get all bookings
        cursor.execute("SELECT * FROM bookings ORDER BY booking_date DESC, slot_time")
        all_bookings = cursor.fetchall()

        # Get selected date
        selected_date = request.args.get("date")

        if not selected_date:
            selected_date = d.today().strftime("%Y-%m-%d")

        # Get booked slots
        cursor.execute(
            "SELECT slot_time FROM bookings WHERE booking_date=%s",
            (selected_date,)
        )
        booked = [row[0] for row in cursor.fetchall()]

        # Slots
        slots = [
            "06:00 AM","07:00 AM","08:00 AM","09:00 AM",
            "10:00 AM","11:00 AM","12:00 PM","01:00 PM",
            "02:00 PM","03:00 PM","04:00 PM","05:00 PM",
            "06:00 PM","07:00 PM","08:00 PM","09:00 PM",
            "10:00 PM","11:00 PM"
        ]

        cursor.close()
        db.close()

        return render_template(
            "index.html",
            bookings=all_bookings,
            slots=slots,
            booked=booked,
            date=selected_date
        )
    
    except Exception as e:
        print(f"Error in index route: {e}")
        return f"An error occurred: {str(e)}", 500

# --- BOOK ROUTE ---
@app.route('/book', methods=['POST'])
def book():
    try:
        db = get_db_connection()
        if db is None:
            return "Database connection failed", 500
        
        cursor = db.cursor()

        name = request.form.get('name')
        sport = request.form.get('sport')
        turf = request.form.get('turf')
        slot = request.form.get('slot')
        booking_date = request.form.get('date')

        # Validate inputs
        if not all([name, sport, turf, slot, booking_date]):
            return "All fields are required!", 400

        # Check if slot already booked
        cursor.execute("""
            SELECT * FROM bookings
            WHERE turf=%s AND slot_time=%s AND booking_date=%s
        """, (turf, slot, booking_date))

        existing = cursor.fetchone()

        if existing:
            cursor.close()
            db.close()
            return "Slot already booked for this turf!"

        # Insert booking
        cursor.execute("""
            INSERT INTO bookings (name, sport, turf, slot_time, booking_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, sport, turf, slot, booking_date))

        db.commit()
        
        cursor.close()
        db.close()
        
        return redirect('/')
    
    except Exception as e:
        print(f"Error in book route: {e}")
        return f"An error occurred while booking: {str(e)}", 500

# --- CANCEL ROUTES ---
@app.route('/cancelpage/<int:id>')
def cancelpage(id):
    try:
        db = get_db_connection()
        if db is None:
            return "Database connection failed", 500
        
        cursor = db.cursor()
        cursor.execute("SELECT * FROM bookings WHERE id=%s", (id,))
        booking = cursor.fetchone()
        
        cursor.close()
        db.close()

        if not booking:
            return "Booking not found", 404

        return render_template("cancel.html", booking=booking)
    
    except Exception as e:
        print(f"Error in cancelpage route: {e}")
        return f"An error occurred: {str(e)}", 500

@app.route('/confirmcancel/<int:id>', methods=['POST'])
def confirmcancel(id):
    try:
        db = get_db_connection()
        if db is None:
            return "Database connection failed", 500
        
        cursor = db.cursor()
        
        cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
        db.commit()
        
        affected_rows = cursor.rowcount
        cursor.close()
        db.close()
        
        if affected_rows == 0:
            return "Booking not found", 404
            
        return redirect('/')
    
    except Exception as e:
        print(f"Error in confirmcancel route: {e}")
        return f"An error occurred while cancelling: {str(e)}", 500

@app.route('/check-db')
def check_db():
    """Endpoint to check database structure"""
    db = get_db_connection()
    if db is None:
        return "Database connection failed", 500
    
    cursor = db.cursor()
    
    try:
        # Show table structure
        cursor.execute("SHOW COLUMNS FROM bookings")
        columns = cursor.fetchall()
        
        result = "Table structure:\n"
        for col in columns:
            result += f"{col[0]} - {col[1]} - Null: {col[2]} - Key: {col[3]} - Default: {col[4]} - Extra: {col[5]}\n"
        
        # Show some data
        cursor.execute("SELECT COUNT(*) FROM bookings")
        count = cursor.fetchone()[0]
        result += f"\nTotal records: {count}"
        
        cursor.close()
        db.close()
        
        return f"<pre>{result}</pre>"
        
    except Error as e:
        return f"Error: {e}", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
