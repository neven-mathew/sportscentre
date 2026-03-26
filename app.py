from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_mail import Mail, Message
import mysql.connector
from mysql.connector import Error
from datetime import date as d, datetime
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sports-center-secure-key-2026')

# --- MAIL CONFIGURATION ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME') 
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = ('Sports Center Admin', os.environ.get('MAIL_USERNAME'))

mail = Mail(app)

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
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        print(f"Database Error: {e}")
        return None

def ensure_schema(cursor, db):
    try:
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'status'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE bookings ADD COLUMN status VARCHAR(20) DEFAULT 'pending'")
        db.commit()
    except:
        pass

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES ---

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
        
        # Get confirmed slots for the date
        cursor.execute("SELECT slot_time FROM bookings WHERE booking_date=%s AND status='confirmed'", (selected_date,))
        booked = [row[0] for row in cursor.fetchall()]
        
        # DEFINED SLOTS LIST
        slots = [
            "06:00 AM","07:00 AM","08:00 AM","09:00 AM", "10:00 AM","11:00 AM", 
            "12:00 PM","01:00 PM","02:00 PM","03:00 PM", "04:00 PM","05:00 PM", 
            "06:00 PM","07:00 PM","08:00 PM","09:00 PM", "10:00 PM","11:00 PM"
        ]
        
        db.close()
        return render_template("booking.html", slots=slots, booked=booked, date=selected_date, today_date=d.today().strftime("%Y-%m-%d"))
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/book', methods=['POST'])
def book():
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        sport = request.form.get('sport')
        turf = request.form.get('turf')
        slot = request.form.get('slot')
        booking_date = request.form.get('date')

        cursor.execute("INSERT INTO bookings (name, email, phone, sport, turf, slot_time, booking_date, status) VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')", (name, email, phone, sport, turf, slot, booking_date))
        db.commit()

        if email:
            msg = Message('Action Required: Payment for Booking', recipients=[email])
            msg.html = render_template('email_template.html', name=name, date=booking_date, time=slot, turf=turf, total=800, advance=300, remaining=500, PAYMENT_NUMBER='7012631996')
            try: mail.send(msg)
            except: pass

        db.close()
        return redirect(url_for('payment_page', name=name))
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/payment/<name>')
def payment_page(name):
    return render_template('payment.html', name=name)

@app.route('/mybookings')
def mybookings():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id, name, phone, sport, turf, slot_time, booking_date, status FROM bookings ORDER BY id DESC")
    bookings = cursor.fetchall()
    db.close()
    return render_template("mybookings.html", bookings=bookings, total_bookings=len(bookings), 
                           confirmed_count=sum(1 for b in bookings if b[7] == 'confirmed'),
                           pending_count=sum(1 for b in bookings if b[7] != 'confirmed'))

# --- ADMIN ROUTES (Login, Confirm, Reject) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect('/admin')
    return render_template('login.html')

@app.route('/admin')
@login_required
def admin_panel():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id, name, phone, sport, turf, slot_time, booking_date, status, email FROM bookings WHERE status='pending'")
    pending = cursor.fetchall()
    cursor.execute("SELECT id, name, phone, sport, turf, slot_time, booking_date, status, email FROM bookings WHERE status='confirmed'")
    confirmed = cursor.fetchall()
    db.close()
    return render_template("admin.html", pending_bookings=pending, confirmed_bookings=confirmed)

@app.route('/admin/confirm/<int:id>')
@login_required
def confirm_booking(id):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT name, email, booking_date, slot_time, turf FROM bookings WHERE id=%s", (id,))
    user = cursor.fetchone()
    if user:
        cursor.execute("UPDATE bookings SET status='confirmed' WHERE id=%s", (id,))
        db.commit()
        if user[1]:
            msg = Message('Booking Confirmed!', recipients=[user[1]])
            msg.html = render_template('payment_confirmation_email.html', name=user[0], date=user[2], time=user[3], turf=user[4])
            try: mail.send(msg)
            except: pass
    db.close()
    return redirect('/admin')

@app.route('/admin/reject/<int:id>')
@login_required
def reject_booking(id):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT name, email, booking_date, slot_time FROM bookings WHERE id=%s", (id,))
    user = cursor.fetchone()
    if user and user[1]:
        msg = Message('Booking Cancelled', recipients=[user[1]])
        msg.html = render_template('cancellation_email.html', name=user[0], date=user[2], time=user[3])
        try: mail.send(msg)
        except: pass
    cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
    db.commit()
    db.close()
    return redirect('/admin')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
    
