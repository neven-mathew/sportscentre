from flask import Flask, render_template, request, redirect, session, flash
import mysql.connector
from mysql.connector import Error
from datetime import date as d, datetime
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')

# Database configuration
DB_CONFIG = {
    'host': 'autorack.proxy.rlwy.net',
    'user': 'root',
    'password': 'PRlkjHknXZNbCjcqMbmxqexeHKawUqow',
    'database': 'railway',
    'port': 37887
}

# Admin credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

def get_db_connection():
    """Create database connection with error handling"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"MySQL Connection Error: {e}")
        return None

def login_required(f):
    """Decorator to require login for admin routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please login to access the admin panel', 'error')
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# --- LOGIN ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect('/admin')
        else:
            flash('Invalid username or password', 'error')
            return redirect('/login')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect('/login')

# --- INDEX ROUTE ---
@app.route('/', methods=['GET'])
def index():
    try:
        db = get_db_connection()
        if db is None:
            return "Database connection failed", 500
        
        cursor = db.cursor()

        # Check if status column exists
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'status'")
        status_exists = cursor.fetchone()
        
        if status_exists:
            # Get only confirmed bookings
            cursor.execute("SELECT * FROM bookings WHERE status='confirmed' ORDER BY booking_date DESC, slot_time")
        else:
            # Get all bookings if status column doesn't exist
            cursor.execute("SELECT * FROM bookings ORDER BY booking_date DESC, slot_time")
        
        all_bookings = cursor.fetchall()

        # Get selected date
        selected_date = request.args.get("date")

        if not selected_date:
            selected_date = d.today().strftime("%Y-%m-%d")

        # Get booked slots
        if status_exists:
            cursor.execute(
                "SELECT slot_time FROM bookings WHERE booking_date=%s AND status='confirmed'",
                (selected_date,)
            )
        else:
            cursor.execute(
                "SELECT slot_time FROM bookings WHERE booking_date=%s",
                (selected_date,)
            )
        booked = [row[0] for row in cursor.fetchall()]

        # Get today's date for min attribute
        today_date = d.today().strftime("%Y-%m-%d")

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
            date=selected_date,
            today_date=today_date
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

        # Check if booking date is in the past
        today = d.today()
        selected_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
        
        if selected_date < today:
            return "Cannot book for past dates! Please select today or a future date.", 400

        # Check if status column exists
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'status'")
        status_exists = cursor.fetchone()

        # Check if slot already booked and confirmed
        if status_exists:
            cursor.execute("""
                SELECT * FROM bookings
                WHERE turf=%s AND slot_time=%s AND booking_date=%s AND status='confirmed'
            """, (turf, slot, booking_date))
        else:
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
        if status_exists:
            cursor.execute("""
                INSERT INTO bookings (name, sport, turf, slot_time, booking_date, status)
                VALUES (%s, %s, %s, %s, %s, 'pending')
            """, (name, sport, turf, slot, booking_date))
            flash('Booking request submitted successfully! Waiting for admin confirmation.', 'success')
        else:
            cursor.execute("""
                INSERT INTO bookings (name, sport, turf, slot_time, booking_date)
                VALUES (%s, %s, %s, %s, %s)
            """, (name, sport, turf, slot, booking_date))
            flash('Booking confirmed successfully!', 'success')

        db.commit()
        
        cursor.close()
        db.close()
        
        return redirect('/')
    
    except Exception as e:
        print(f"Error in book route: {e}")
        return f"An error occurred while booking: {str(e)}", 500

# --- ADMIN PANEL ROUTES ---
@app.route('/admin')
@login_required
def admin_panel():
    try:
        db = get_db_connection()
        if db is None:
            return "Database connection failed", 500
        
        cursor = db.cursor()
        
        # Check if status column exists
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'status'")
        status_exists = cursor.fetchone()
        
        if not status_exists:
            # Add status column automatically
            try:
                cursor.execute("ALTER TABLE bookings ADD COLUMN status VARCHAR(20) DEFAULT 'confirmed'")
                db.commit()
                flash('Status column added successfully!', 'success')
            except Exception as e:
                flash(f'Error adding status column: {str(e)}', 'error')
                cursor.close()
                db.close()
                return redirect('/')
        
        # Get pending bookings
        cursor.execute("""
            SELECT * FROM bookings 
            WHERE status='pending' 
            ORDER BY booking_date ASC, slot_time ASC
        """)
        pending_bookings = cursor.fetchall()
        
        # Get confirmed bookings
        cursor.execute("""
            SELECT * FROM bookings 
            WHERE status='confirmed' 
            ORDER BY booking_date DESC, slot_time DESC
        """)
        confirmed_bookings = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        return render_template(
            "admin.html",
            pending_bookings=pending_bookings,
            confirmed_bookings=confirmed_bookings,
            username=session.get('username')
        )
    
    except Exception as e:
        print(f"Error in admin panel: {e}")
        return f"An error occurred: {str(e)}", 500

@app.route('/admin/confirm/<int:id>')
@login_required
def confirm_booking(id):
    try:
        db = get_db_connection()
        if db is None:
            return "Database connection failed", 500
        
        cursor = db.cursor()
        
        # Check if the booking exists and is pending
        cursor.execute("SELECT * FROM bookings WHERE id=%s AND status='pending'", (id,))
        booking = cursor.fetchone()
        
        if not booking:
            flash('Booking not found or already processed', 'error')
            return redirect('/admin')
        
        # Confirm the booking
        cursor.execute("UPDATE bookings SET status='confirmed' WHERE id=%s", (id,))
        db.commit()
        
        flash(f'Booking confirmed for {booking[1]} on {booking[5]} at {booking[4]}', 'success')
        
        cursor.close()
        db.close()
        
        return redirect('/admin')
    
    except Exception as e:
        print(f"Error in confirm_booking: {e}")
        flash(f'Error confirming booking: {str(e)}', 'error')
        return redirect('/admin')

@app.route('/admin/reject/<int:id>')
@login_required
def reject_booking(id):
    try:
        db = get_db_connection()
        if db is None:
            return "Database connection failed", 500
        
        cursor = db.cursor()
        
        # Check if the booking exists and is pending
        cursor.execute("SELECT * FROM bookings WHERE id=%s AND status='pending'", (id,))
        booking = cursor.fetchone()
        
        if not booking:
            flash('Booking not found or already processed', 'error')
            return redirect('/admin')
        
        # Delete the pending booking (reject)
        cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
        db.commit()
        
        flash(f'Booking rejected for {booking[1]}', 'info')
        
        cursor.close()
        db.close()
        
        return redirect('/admin')
    
    except Exception as e:
        print(f"Error in reject_booking: {e}")
        flash(f'Error rejecting booking: {str(e)}', 'error')
        return redirect('/admin')

# --- ADMIN CANCEL BOOKING ROUTE ---
@app.route('/admin/cancel_booking/<int:id>')
@login_required
def admin_cancel_booking(id):
    """Admin route to cancel confirmed bookings"""
    try:
        db = get_db_connection()
        if db is None:
            flash("Database connection failed", "error")
            return redirect('/admin')
        
        cursor = db.cursor()
        
        # Check if the booking exists and is confirmed
        cursor.execute("SELECT * FROM bookings WHERE id=%s AND status='confirmed'", (id,))
        booking = cursor.fetchone()
        
        if not booking:
            flash('Booking not found or already cancelled', 'error')
            return redirect('/admin')
        
        # Delete the confirmed booking
        cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
        db.commit()
        
        flash(f'Booking cancelled successfully for {booking[1]} on {booking[5]} at {booking[4]}', 'success')
        
        cursor.close()
        db.close()
        
        return redirect('/admin')
    
    except Exception as e:
        print(f"Error in admin_cancel_booking: {e}")
        flash(f'Error cancelling booking: {str(e)}', 'error')
        return redirect('/admin')

# --- CANCEL ROUTES ---
@app.route('/cancelpage/<int:id>')
def cancelpage(id):
    try:
        db = get_db_connection()
        if db is None:
            return "Database connection failed", 500
        
        cursor = db.cursor()
        
        # Check if status column exists
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'status'")
        status_exists = cursor.fetchone()
        
        # Get booking details
        cursor.execute("SELECT * FROM bookings WHERE id=%s", (id,))
        booking = cursor.fetchone()
        
        cursor.close()
        db.close()

        if not booking:
            flash('Booking not found', 'error')
            return redirect('/')

        # If status column exists, only confirmed bookings can be cancelled
        if status_exists:
            if len(booking) > 6 and booking[6] != 'confirmed':
                flash('Confirmed bookings unfortunately cannot be cancelled. Please contact admin for cancellation of the bookings.', 'error')
                return redirect('/')

        return render_template("cancel.html", booking=booking)
    
    except Exception as e:
        print(f"Error in cancelpage route: {e}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect('/')

@app.route('/confirmcancel/<int:id>', methods=['POST'])
def confirmcancel(id):
    try:
        db = get_db_connection()
        if db is None:
            return "Database connection failed", 500
        
        cursor = db.cursor()
        
        # Check if status column exists
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'status'")
        status_exists = cursor.fetchone()
        
        # Get booking details
        cursor.execute("SELECT * FROM bookings WHERE id=%s", (id,))
        booking = cursor.fetchone()
        
        if not booking:
            cursor.close()
            db.close()
            flash('Booking not found', 'error')
            return redirect('/')
        
        # If status column exists, verify booking is confirmed before deletion
        if status_exists:
            if len(booking) > 6 and booking[6] != 'confirmed':
                cursor.close()
                db.close()
                flash('Confirmed bookings unfortunately cannot be cancelled. Please contact admin for cancellation of the bookings.', 'error')
                return redirect('/')
        
        # Delete the booking
        cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
        db.commit()
        
        affected_rows = cursor.rowcount
        cursor.close()
        db.close()
        
        if affected_rows == 0:
            flash('Booking not found', 'error')
        else:
            flash('Booking cancelled successfully!', 'success')
            
        return redirect('/')
    
    except Exception as e:
        print(f"Error in confirmcancel route: {e}")
        flash(f'An error occurred while cancelling: {str(e)}', 'error')
        return redirect('/')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
