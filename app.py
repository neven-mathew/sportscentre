from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_mail import Mail, Message
import mysql.connector
from mysql.connector import Error
from datetime import date as d, datetime
import os
from functools import wraps

app = Flask(__name__)
# It's best to set this in Render Environment Variables as SECRET_KEY
app.secret_key = os.environ.get('SECRET_KEY', 'sports-center-secure-key-2026')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# --- MAIL CONFIGURATION ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME') 
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

mail = Mail(app)

# --- PAYMENT CONFIGURATION ---
PAYMENT_NUMBER = '7012631996' 
TOTAL_AMOUNT = 800
ADVANCE_AMOUNT = 300
REMAINING_AMOUNT = TOTAL_AMOUNT - ADVANCE_AMOUNT

# --- DATABASE CONFIGURATION ---
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

def ensure_schema(cursor, db):
    """Ensures all necessary columns (status, email, phone) exist in the table"""
    try:
        # Check Status
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'status'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE bookings ADD COLUMN status VARCHAR(20) DEFAULT 'pending'")
        
        # Check Email
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'email'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE bookings ADD COLUMN email VARCHAR(120) DEFAULT NULL")
            
        # Check Phone
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'phone'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE bookings ADD COLUMN phone VARCHAR(20) DEFAULT NULL")
            
        db.commit()
    except Exception as e:
        print(f"Schema update error: {e}")

def login_required(f):
    """Decorator to protect admin routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please login to access the admin panel', 'error')
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

@app.after_request
def add_header(response):
    """Add headers to prevent caching issues"""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# --- PUBLIC ROUTES ---

@app.route('/')
def homepage():
    return render_template('homepage.html')

@app.route('/booking', methods=['GET'])
def booking():
    try:
        db = get_db_connection()
        if db is None: return "Database connection failed", 500
        cursor = db.cursor()
        ensure_schema(cursor, db)

        selected_date = request.args.get("date")
        if not selected_date:
            selected_date = d.today().strftime("%Y-%m-%d")

        cursor.execute(
            "SELECT slot_time FROM bookings WHERE booking_date=%s AND status='confirmed'",
            (selected_date,)
        )
        booked = [row[0] for row in cursor.fetchall()]
        today_date = d.today().strftime("%Y-%m-%d")

        slots = [
            "06:00 AM","07:00 AM","08:00 AM","09:00 AM", "10:00 AM","11:00 AM",
            "12:00 PM","01:00 PM","02:00 PM","03:00 PM", "04:00 PM","05:00 PM",
            "06:00 PM","07:00 PM","08:00 PM","09:00 PM", "10:00 PM","11:00 PM"
        ]

        cursor.close()
        db.close()
        return render_template("booking.html", slots=slots, booked=booked, date=selected_date, today_date=today_date)
    except Exception as e:
        return f"An error occurred: {str(e)}", 500

@app.route('/book', methods=['POST'])
def book():
    try:
        db = get_db_connection()
        cursor = db.cursor()
        ensure_schema(cursor, db)

        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        sport = request.form.get('sport')
        turf = request.form.get('turf')
        slot = request.form.get('slot')
        booking_date = request.form.get('date')

        if not all([name, email, phone, sport, turf, slot, booking_date]):
            return "All fields are required!", 400

        # Check for confirmed double bookings
        cursor.execute("""
            SELECT id FROM bookings 
            WHERE turf=%s AND slot_time=%s AND booking_date=%s AND status='confirmed'
        """, (turf, slot, booking_date))
        
        if cursor.fetchone():
            return "Slot already confirmed for someone else!", 400

        cursor.execute("""
            INSERT INTO bookings (name, email, phone, sport, turf, slot_time, booking_date, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (name, email, phone, sport, turf, slot, booking_date))
        db.commit()

        # Send 'Request Received' email
        try:
            msg = Message('Booking Request Received - Sports Center', recipients=[email])
            msg.body = f"Hi {name},\n\nWe received your request for {turf} on {booking_date}. Your request is now with our admin for confirmation.\n\nYou will receive another email shortly with payment instructions once approved.\n\nThanks!"
            mail.send(msg)
        except Exception as e:
            print(f"Mail delivery failed: {e}")

        cursor.close()
        db.close()
        flash('Request submitted! Check your email for updates.', 'success')
        return redirect('/mybookings')
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/mybookings')
def mybookings():
    try:
        db = get_db_connection()
        cursor = db.cursor()
        ensure_schema(cursor, db)
        # Fetching specific columns to match mybookings.html template index
        cursor.execute("SELECT id, name, phone, sport, turf, slot_time, booking_date, status FROM bookings ORDER BY booking_date DESC")
        bookings = cursor.fetchall()
        
        confirmed_count = sum(1 for b in bookings if b[7] == 'confirmed')
        pending_count = len(bookings) - confirmed_count
        
        cursor.close()
        db.close()
        return render_template("mybookings.html", bookings=bookings, total_bookings=len(bookings), confirmed_count=confirmed_count, pending_count=pending_count)
    except Exception as e:
        return f"Error: {str(e)}", 500

# --- ADMIN ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            session['username'] = ADMIN_USERNAME
            return redirect('/admin')
        flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/admin')
@login_required
def admin_panel():
    try:
        db = get_db_connection()
        cursor = db.cursor()
        ensure_schema(cursor, db)
        
        cursor.execute("SELECT id, name, phone, sport, turf, slot_time, booking_date, status, email FROM bookings WHERE status='pending' ORDER BY booking_date ASC")
        pending = cursor.fetchall()
        
        cursor.execute("SELECT id, name, phone, sport, turf, slot_time, booking_date, status, email FROM bookings WHERE status='confirmed' ORDER BY booking_date DESC")
        confirmed = cursor.fetchall()
        
        cursor.close()
        db.close()
        return render_template("admin.html", pending_bookings=pending, confirmed_bookings=confirmed, username=session.get('username'))
    except Exception as e:
        return f"Admin Panel Error: {str(e)}", 500

@app.route('/admin/confirm/<int:id>')
@login_required
def confirm_booking(id):
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        cursor.execute("SELECT name, email, sport, turf, slot_time, booking_date FROM bookings WHERE id=%s", (id,))
        user = cursor.fetchone()
        
        if not user:
            flash('Booking not found', 'error')
            return redirect('/admin')
            
        name, email, sport, turf, slot_time, booking_date = user
        
        cursor.execute("UPDATE bookings SET status='confirmed' WHERE id=%s", (id,))
        db.commit()
        
        # --- SEND THE RICH HTML EMAIL ---
        if email:
            msg = Message('Action Required: Confirm your Sports Center Booking', recipients=[email])
            msg.html = render_template('email_template.html', 
                                     name=name, date=booking_date, time=slot_time, 
                                     turf=turf, total=TOTAL_AMOUNT, advance=ADVANCE_AMOUNT, 
                                     remaining=REMAINING_AMOUNT, PAYMENT_NUMBER=PAYMENT_NUMBER)

            # Embed the QR Code
            try:
                with app.open_resource("static/qr_code.png") as fp:
                    msg.attach("qr_code.png", "image/png", fp.read(), headers=[['Content-ID', '<qr_code>']])
                mail.send(msg)
            except Exception as e:
                print(f"Mail error: {e}")

        flash(f'Confirmed and Email sent to {name}!', 'success')
        cursor.close()
        db.close()
        return redirect('/admin')
    except Exception as e:
        flash(f"Error: {str(e)}", 'error')
        return redirect('/admin')

@app.route('/admin/reject/<int:id>')
@login_required
def reject_booking(id):
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT name, email FROM bookings WHERE id=%s", (id,))
        user = cursor.fetchone()
        
        if user and user[1]:
            msg = Message('Booking Update - Sports Center', recipients=[user[1]])
            msg.body = f"Hi {user[0]},\n\nWe regret to inform you that your booking request could not be confirmed at this time. Please try a different slot.\n\nThanks!"
            try: mail.send(msg)
            except: pass
            
        cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
        db.commit()
        flash('Booking rejected and deleted.', 'info')
        cursor.close()
        db.close()
        return redirect('/admin')
    except Exception as e:
        flash(f"Error: {str(e)}", 'error')
        return redirect('/admin')

@app.route('/admin/cancel_booking/<int:id>')
@login_required
def admin_cancel_booking(id):
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
        db.commit()
        flash('Confirmed booking has been cancelled.', 'success')
        cursor.close()
        db.close()
        return redirect('/admin')
    except Exception as e:
        flash(f"Error: {str(e)}", 'error')
        return redirect('/admin')

# --- USER CANCEL ROUTES ---

@app.route('/cancelpage/<int:id>')
def cancelpage(id):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id, name, phone, sport, turf, slot_time, booking_date, status FROM bookings WHERE id=%s", (id,))
    booking = cursor.fetchone()
    db.close()
    if not booking or booking[7] != 'confirmed':
        flash('Only confirmed bookings can be cancelled here.', 'error')
        return redirect('/mybookings')
    return render_template("cancel.html", booking=booking)

@app.route('/confirmcancel/<int:id>', methods=['POST'])
def confirmcancel(id):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
    db.commit()
    db.close()
    flash('Booking cancelled successfully.', 'success')
    return redirect('/mybookings')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
