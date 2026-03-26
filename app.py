from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_mail import Mail, Message
import mysql.connector
from mysql.connector import Error
from datetime import date as d, datetime
import os
from functools import wraps

app = Flask(__name__)
# Set your secret key here or via Render Environment Variables
app.secret_key = os.environ.get('SECRET_KEY', 'sports-center-secure-key-2026')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# --- MAIL CONFIGURATION ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME') 
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = ('Sports Center Admin', os.environ.get('MAIL_USERNAME'))

mail = Mail(app)

# --- PAYMENT SETTINGS ---
PAYMENT_NUMBER = '7012631996' 
TOTAL_AMOUNT = 800
ADVANCE_AMOUNT = 300
REMAINING_AMOUNT = TOTAL_AMOUNT - ADVANCE_AMOUNT

# --- DATABASE SETTINGS ---
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
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Database Connection Error: {e}")
        return None

def ensure_schema(cursor, db):
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
        print(f"Schema check error: {e}")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please login to access admin.', 'error')
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
        cursor = db.cursor()
        ensure_schema(cursor, db)
        selected_date = request.args.get("date") or d.today().strftime("%Y-%m-%d")
        cursor.execute("SELECT slot_time FROM bookings WHERE booking_date=%s AND status='confirmed'", (selected_date,))
        booked = [row[0] for row in cursor.fetchall()]
        today_date = d.today().strftime("%Y-%m-%d")
        slots = ["06:00 AM","07:00 AM","08:00 AM","09:00 AM", "10:00 AM","11:00 AM", "12:00 PM","01:00 PM","02:00 PM","03:00 PM", "04:00 PM","05:00 PM", "06:00 PM","07:00 PM","08:00 PM","09:00 PM", "10:00 PM","11:00 PM"]
        db.close()
        return render_template("booking.html", slots=slots, booked=booked, date=selected_date, today_date=today_date)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/book', methods=['POST'])
def book():
    """Immediate Payment Email with Dynamic QR (No attachment needed)"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        ensure_schema(cursor, db)

        name, email, phone = request.form.get('name'), request.form.get('email'), request.form.get('phone')
        sport, turf, slot, booking_date = request.form.get('sport'), request.form.get('turf'), request.form.get('slot'), request.form.get('date')

        cursor.execute("INSERT INTO bookings (name, email, phone, sport, turf, slot_time, booking_date, status) VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')", (name, email, phone, sport, turf, slot, booking_date))
        db.commit()

        if email:
            msg = Message('Action Required: Payment for Sports Center Booking', recipients=[email])
            # email_template.html now contains the dynamic QR API link
            msg.html = render_template('email_template.html', name=name, date=booking_date, time=slot, turf=turf, total=TOTAL_AMOUNT, advance=ADVANCE_AMOUNT, remaining=REMAINING_AMOUNT, PAYMENT_NUMBER=PAYMENT_NUMBER)
            try:
                mail.send(msg)
                flash('Request Sent! Check email for payment link.', 'success')
            except Exception as e:
                flash(f'Booking saved, but Mail Server error: {str(e)}', 'error')

        db.close()
        return redirect('/mybookings')
    except Exception as e:
        return f"Database Error: {str(e)}", 500

@app.route('/mybookings')
def mybookings():
    db = get_db_connection()
    cursor = db.cursor()
    ensure_schema(cursor, db)
    # Order: 0:id, 1:name, 2:phone, 3:sport, 4:turf, 5:slot_time, 6:booking_date, 7:status
    cursor.execute("SELECT id, name, phone, sport, turf, slot_time, booking_date, status FROM bookings ORDER BY id DESC")
    bookings = cursor.fetchall()
    total_bookings = len(bookings)
    confirmed_count = sum(1 for b in bookings if b[7] == 'confirmed')
    pending_count = total_bookings - confirmed_count
    db.close()
    return render_template("mybookings.html", bookings=bookings, total_bookings=total_bookings, confirmed_count=confirmed_count, pending_count=pending_count)

# --- ADMIN ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            session['username'] = ADMIN_USERNAME
            return redirect('/admin')
        flash('Invalid Credentials', 'error')
    return render_template('login.html')

@app.route('/admin')
@login_required
def admin_panel():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id, name, phone, sport, turf, slot_time, booking_date, status, email FROM bookings WHERE status='pending' ORDER BY id ASC")
    pending = cursor.fetchall()
    cursor.execute("SELECT id, name, phone, sport, turf, slot_time, booking_date, status, email FROM bookings WHERE status='confirmed' ORDER BY id DESC")
    confirmed = cursor.fetchall()
    db.close()
    return render_template("admin.html", pending_bookings=pending, confirmed_bookings=confirmed, username=session.get('username'))

@app.route('/admin/confirm/<int:id>')
@login_required
def confirm_booking(id):
    """Confirm payment and send success email"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT name, email, booking_date, slot_time, turf FROM bookings WHERE id=%s", (id,))
        user = cursor.fetchone()
        if user:
            name, email, b_date, b_time, b_turf = user
            cursor.execute("UPDATE bookings SET status='confirmed' WHERE id=%s", (id,))
            db.commit()
            if email:
                msg = Message('Payment Received - Booking Confirmed', recipients=[email])
                msg.html = render_template('payment_confirmation_email.html', name=name, date=b_date, time=b_time, turf=b_turf)
                mail.send(msg)
        db.close()
        flash('Confirmed and email sent!', 'success')
        return redirect('/admin')
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/admin/reject/<int:id>')
@login_required
def reject_booking(id):
    """Reject and send cancellation email"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT name, email, booking_date, slot_time FROM bookings WHERE id=%s", (id,))
        user = cursor.fetchone()
        if user and user[1]:
            msg = Message('Booking Cancelled - Sports Center', recipients=[user[1]])
            msg.html = render_template('cancellation_email.html', name=user[0], date=user[2], time=user[3])
            mail.send(msg)
        cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
        db.commit()
        db.close()
        flash('Rejected and user notified.', 'info')
        return redirect('/admin')
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
