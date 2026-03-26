from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_mail import Mail, Message
import mysql.connector
from mysql.connector import Error
from datetime import date as d
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sports-center-secure-key-2026')

# --- MAIL CONFIGURATION ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME') 
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = ('Sports Center Admin', os.environ.get('MAIL_USERNAME'))

mail = Mail(app)

DB_CONFIG = {
    'host': 'autorack.proxy.rlwy.net',
    'user': 'root',
    'password': 'PRlkjHknXZNbCjcqMbmxqexeHKawUqow',
    'database': 'railway',
    'port': 37887,
    'connection_timeout': 10 # Prevents the "slow" feeling by timing out early
}

def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        print(f"DB Connection Error: {e}")
        return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# --- UPDATED REJECT ROUTE (FIXES THE 500 ERROR) ---
@app.route('/admin/reject/<int:id>')
@login_required
def reject_booking(id):
    db = get_db_connection()
    if not db:
        flash("Database busy. Please try again.", "error")
        return redirect('/admin')
    
    cursor = db.cursor()
    try:
        # 1. Fetch data for email
        cursor.execute("SELECT name, email, booking_date, slot_time FROM bookings WHERE id=%s", (id,))
        user = cursor.fetchone()
        
        if user:
            name, email, b_date, b_time = user
            
            # 2. Delete first (so the UI updates immediately)
            cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
            db.commit()
            
            # 3. Attempt to send email (wrapped in its own try/except so it doesn't crash the 500)
            if email:
                try:
                    msg = Message('Booking Update - Sports Center', recipients=[email])
                    msg.html = render_template('cancellation_email.html', name=name, date=b_date, time=b_time)
                    mail.send(msg)
                except Exception as mail_err:
                    print(f"Mail failed but booking deleted: {mail_err}")
            
            flash(f'Booking #{id} removed successfully.', 'info')
        else:
            flash('Booking not found.', 'error')

    except Exception as e:
        print(f"Server Error: {e}")
        flash("An error occurred while processing the request.", "error")
    finally:
        cursor.close()
        db.close() # CRITICAL: This fixes the slow/hanging issue
        
    return redirect('/admin')

# --- UPDATED CONFIRM ROUTE ---
@app.route('/admin/confirm/<int:id>')
@login_required
def confirm_booking(id):
    db = get_db_connection()
    if not db: return redirect('/admin')
    cursor = db.cursor()
    try:
        cursor.execute("SELECT name, email, booking_date, slot_time, turf FROM bookings WHERE id=%s", (id,))
        user = cursor.fetchone()
        if user:
            cursor.execute("UPDATE bookings SET status='confirmed' WHERE id=%s", (id,))
            db.commit()
            if user[1]:
                try:
                    msg = Message('Booking Confirmed!', recipients=[user[1]])
                    msg.html = render_template('payment_confirmation_email.html', name=user[0], date=user[2], time=user[3], turf=user[4])
                    mail.send(msg)
                except: pass
        flash('Booking confirmed!', 'success')
    finally:
        cursor.close()
        db.close()
    return redirect('/admin')

# ... Rest of your routes (booking, mybookings, etc) ...
# Ensure every route uses the 'finally: db.close()' pattern!

if __name__ == '__main__':
    app.run(debug=False) # Turn off debug for production speed
