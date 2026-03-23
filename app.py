from flask import Flask, render_template, request, redirect, session, flash
import mysql.connector
from mysql.connector import Error
from datetime import date as d, datetime
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

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

@app.after_request
def add_header(response):
    """Add headers to prevent caching"""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

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
    return redirect('/')

# --- HOMEPAGE ROUTE ---
@app.route('/')
def homepage():
    """Homepage displaying center information"""
    return render_template('homepage.html')

# --- BOOKING ROUTE ---
@app.route('/booking', methods=['GET'])
def booking():
    try:
        db = get_db_connection()
        if db is None:
            return "Database connection failed", 500
        
        cursor = db.cursor()
        
        # Ensure status column exists
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'status'")
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE bookings ADD COLUMN status VARCHAR(20) DEFAULT NULL")
                db.commit()
            except Exception as e:
                print(f"Error adding status column: {e}")

        # Get selected date
        selected_date = request.args.get("date")
        if not selected_date:
            selected_date = d.today().strftime("%Y-%m-%d")

        # Get booked slots for selected date (only confirmed bookings block slots)
        cursor.execute(
            "SELECT slot_time FROM bookings WHERE booking_date=%s AND status='confirmed'",
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
            "booking.html",
            slots=slots,
            booked=booked,
            date=selected_date,
            today_date=today_date
        )
    
    except Exception as e:
        print(f"Error in booking route: {e}")
        return f"An error occurred: {str(e)}", 500

# --- BOOK ROUTE (Process booking) ---
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

        # Ensure status column exists
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'status'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE bookings ADD COLUMN status VARCHAR(20) DEFAULT NULL")
            db.commit()

        # Check if slot already booked and confirmed
        cursor.execute("""
            SELECT * FROM bookings
            WHERE turf=%s AND slot_time=%s AND booking_date=%s AND status='confirmed'
        """, (turf, slot, booking_date))

        existing = cursor.fetchone()

        if existing:
            cursor.close()
            db.close()
            return "Slot already booked for this turf!"

        # Insert booking with pending status (waiting for admin approval)
        cursor.execute("""
            INSERT INTO bookings (name, sport, turf, slot_time, booking_date, status)
            VALUES (%s, %s, %s, %s, %s, 'pending')
        """, (name, sport, turf, slot, booking_date))

        db.commit()
        
        cursor.close()
        db.close()
        
        flash('Booking request submitted successfully! Waiting for admin confirmation.', 'success')
        return redirect('/mybookings')
    
    except Exception as e:
        print(f"Error in book route: {e}")
        return f"An error occurred while booking: {str(e)}", 500

# --- MY BOOKINGS ROUTE (UPDATED) ---
@app.route('/mybookings')
def mybookings():
    """View user's own bookings"""
    try:
        db = get_db_connection()
        if db is None:
            return "Database connection failed", 500
        
        cursor = db.cursor()
        
        # Check if status column exists
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'status'")
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE bookings ADD COLUMN status VARCHAR(20) DEFAULT 'pending'")
                db.commit()
            except Exception as e:
                print(f"Error adding status column: {e}")
        
        # Get all bookings
        cursor.execute("SELECT * FROM bookings ORDER BY booking_date DESC, slot_time DESC")
        all_bookings = cursor.fetchall()
        
        # Get precise column names to prevent index mismatch errors
        column_names = [desc[0].lower() for desc in cursor.description]
        
        cursor.close()
        db.close()
        
        # Safely find exact indices for every column based on the database schema
        id_idx = column_names.index('id') if 'id' in column_names else 0
        name_idx = column_names.index('name') if 'name' in column_names else 1
        sport_idx = column_names.index('sport') if 'sport' in column_names else 2
        turf_idx = column_names.index('turf') if 'turf' in column_names else 3
        time_idx = column_names.index('slot_time') if 'slot_time' in column_names else 4
        date_idx = column_names.index('booking_date') if 'booking_date' in column_names else 5
        status_idx = column_names.index('status') if 'status' in column_names else -1

        normalized_bookings = []
        confirmed_count = 0
        pending_count = 0
        
        for booking in all_bookings:
            status = 'pending' # Default fallback
            
            # Extract real status dynamically from its true index
            if status_idx != -1 and len(booking) > status_idx:
                db_status = booking[status_idx]
                if db_status:
                    status = str(db_status).strip().lower()
            
            if status == 'confirmed':
                confirmed_count += 1
            else:
                pending_count += 1
                
            # Pack the tuple EXACTLY the way the mybookings.html template expects: 
            # [id, name, sport, turf, time, date, status]
            clean_booking = (
                booking[id_idx],
                booking[name_idx],
                booking[sport_idx],
                booking[turf_idx],
                booking[time_idx],
                booking[date_idx],
                status
            )
            
            normalized_bookings.append(clean_booking)
        
        total_bookings = len(normalized_bookings)
        
        return render_template(
            "mybookings.html",
            bookings=normalized_bookings,
            total_bookings=total_bookings,
            confirmed_count=confirmed_count,
            pending_count=pending_count
        )
    
    except Exception as e:
        print(f"Error in mybookings route: {e}")
        return f"An error occurred: {str(e)}", 500

# --- ADMIN PANEL ROUTES ---
@app.route('/admin')
@login_required
def admin_panel():
    try:
        db = get_db_connection()
        if db is None:
            return "Database connection failed", 500
        
        cursor = db.cursor()
        
        # Ensure status column exists
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'status'")
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE bookings ADD COLUMN status VARCHAR(20) DEFAULT NULL")
                db.commit()
                cursor.execute("UPDATE bookings SET status = 'pending' WHERE status IS NULL")
                db.commit()
                flash('✅ Status column added successfully!', 'success')
            except Exception as e:
                flash(f'Error adding status column: {str(e)}', 'error')
        
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
            flash("Database connection failed", "error")
            return redirect('/admin')
        
        cursor = db.cursor()
        
        # Check if the booking exists and is pending
        cursor.execute("SELECT * FROM bookings WHERE id=%s AND status='pending'", (id,))
        booking = cursor.fetchone()
        
        if not booking:
            flash('Booking not found or already processed', 'error')
            return redirect('/admin')
        
        # Confirm the booking - set status to confirmed
        cursor.execute("UPDATE bookings SET status='confirmed' WHERE id=%s", (id,))
        db.commit()
        
        # Verify the update
        cursor.execute("SELECT status FROM bookings WHERE id=%s", (id,))
        updated = cursor.fetchone()
        
        if updated and updated[0] == 'confirmed':
            flash(f'✅ Booking confirmed for {booking[1]} on {booking[5]} at {booking[4]}', 'success')
        else:
            flash(f'⚠️ Booking confirmed but status may need refresh', 'info')
        
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
            flash("Database connection failed", "error")
            return redirect('/admin')
        
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
        
        flash(f'❌ Booking rejected for {booking[1]}', 'info')
        
        cursor.close()
        db.close()
        
        return redirect('/admin')
    
    except Exception as e:
        print(f"Error in reject_booking: {e}")
        flash(f'Error rejecting booking: {str(e)}', 'error')
        return redirect('/admin')

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
        
        flash(f'✅ Booking cancelled successfully for {booking[1]} on {booking[5]} at {booking[4]}', 'success')
        
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
        
        # Get booking details
        cursor.execute("SELECT * FROM bookings WHERE id=%s", (id,))
        booking = cursor.fetchone()
        
        cursor.close()
        db.close()

        if not booking:
            flash('Booking not found', 'error')
            return redirect('/mybookings')

        # Only confirmed bookings can be cancelled by users
        if len(booking) > 6 and booking[6] != 'confirmed':
            flash('Cancelation for confirmed booking can be done by contacting admin office . Please contact admin office', 'error')
            return redirect('/mybookings')

        return render_template("cancel.html", booking=booking)
    
    except Exception as e:
        print(f"Error in cancelpage route: {e}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect('/mybookings')

@app.route('/confirmcancel/<int:id>', methods=['POST'])
def confirmcancel(id):
    try:
        db = get_db_connection()
        if db is None:
            return "Database connection failed", 500
        
        cursor = db.cursor()
        
        # Get booking details
        cursor.execute("SELECT * FROM bookings WHERE id=%s", (id,))
        booking = cursor.fetchone()
        
        if not booking:
            cursor.close()
            db.close()
            flash('Booking not found', 'error')
            return redirect('/mybookings')
        
        # Verify booking is confirmed before deletion
        if len(booking) > 6 and booking[6] != 'confirmed':
            cursor.close()
            db.close()
            flash('Cancelation for confirmed booking can be done by contacting admin office . Please contact admin office', 'error')
            return redirect('/mybookings')
        
        # Delete the booking
        cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
        db.commit()
        
        affected_rows = cursor.rowcount
        cursor.close()
        db.close()
        
        if affected_rows == 0:
            flash('Booking not found', 'error')
        else:
            flash('✅ Booking cancelled successfully!', 'success')
            
        return redirect('/mybookings')
    
    except Exception as e:
        print(f"Error in confirmcancel route: {e}")
        flash(f'An error occurred while cancelling: {str(e)}', 'error')
        return redirect('/mybookings')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
