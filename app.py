from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_mail import Mail, Message
import mysql.connector
from mysql.connector import Error
from datetime import date as d, datetime
import os
from functools import wraps

app = Flask(__name__)
# Best practice: Set these in Render Environment Variables
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

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

def get_db_connection():
    """Establishes database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"MySQL Connection Error: {e}")
        return None

def ensure_schema(cursor, db):
    """Checks and adds necessary columns automatically"""
    try:
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'status'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE bookings ADD COLUMN status VARCHAR(20) DEFAULT 'pending'")
        
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'email'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE bookings ADD COLUMN email VARCHAR(120) DEFAULT NULL")
            
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'phone'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE bookings ADD COLUMN phone VARCHAR(20) DEFAULT NULL")
            
        db.commit()
    except Exception as e:
        print(f"Schema auto-update error: {e}")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please login to access the admin panel', 'error')
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

@app.after_request
def add_header(response):
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

        selected_date = request.args.get("date") or d.today().strftime("%Y-%m-%d")
        cursor.execute("SELECT slot_time FROM bookings WHERE booking_date=%s AND status='confirmed'", (selected_date,))
        booked = [row[0] for row in cursor.fetchall()]
        
        today_date = d.today().strftime("%Y-%m-%d")
        slots = ["06:00 AM","07:00 AM","08:00 AM","09:00 AM", "10:00 AM","11:00 AM", 
                 "12:00 PM","01:00 PM","02:00 PM","03:00 PM", "04:00 PM","05:00 PM", 
                 "06:00 PM","07:00 PM","08:00 PM","09:00 PM", "10:00 PM","11:00 PM"]

        cursor.close()
        db.close()
        return render_template("booking.html", slots=slots, booked=booked, date=selected_date, today_date=today_date)
    except Exception as e:
        return f"An error occurred: {str(e)}", 500

@app.route('/book', methods=['POST'])
def book():
    """Triggers IMMEDIATE email request for payment with QR Code"""
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

        cursor.execute("""
            INSERT INTO bookings (name, email, phone, sport, turf, slot_time, booking_date, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (name, email, phone, sport, turf, slot, booking_date))
        db.commit()

        # --- SEND IMMEDIATE PAYMENT REQUEST EMAIL ---
        if email:
            msg = Message('Action Required: Confirm your Sports Center Booking', recipients=[email])
            msg.html = render_template('email_template.html', 
                                     name=name, date=booking_date, time=slot, 
                                     turf=turf, total=TOTAL_AMOUNT, advance=ADVANCE_AMOUNT, 
                                     remaining=REMAINING_AMOUNT, PAYMENT_NUMBER=PAYMENT_NUMBER)
            try:
                # Embed QR code from static folder
                with app.open_resource("static/qr_code.png") as fp:
                    msg.attach("qr_code.png", "image/png", fp.read(), headers=[['Content-ID', '<qr_code>']])
                mail.send(msg)
            except Exception as e:
                print(f"Booking Email failed: {e}")

        cursor.close()
        db.close()
        flash('Request submitted! Please check your email to pay the advance.', 'success')
        return redirect('/mybookings')
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/mybookings')
def mybookings():
    try:
        db = get_db_connection()
        cursor = db.cursor()
        ensure_schema(cursor, db)
        cursor.execute("SELECT id, name, phone, sport, turf, slot_time, booking_date, status FROM bookings ORDER BY booking_date DESC")
        bookings = cursor.fetchall()
        db.close()
        return render_template("mybookings.html", bookings=bookings, total_bookings=len(bookings))
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

@app.route('/admin
