from flask import Flask, render_template, request, redirect, session, flash, url_for
import mysql.connector
from mysql.connector import Error
from datetime import date as d, datetime
import os
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
from dotenv import load_dotenv

load_dotenv()

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

# Email configuration (Update with your email credentials)
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',  # For Gmail
    'smtp_port': 587,
    'sender_email': 'your-email@gmail.com',  # Replace with your email
    'sender_password': 'your-app-password',  # Replace with your app password
    'admin_email': 'admin@sportscenter.com'  # Admin email for notifications
}

# Payment configuration
PAYMENT_NUMBER = '7012631996'
BOOKING_AMOUNT = 200

def get_db_connection():
    """Create database connection with error handling"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"MySQL Connection Error: {e}")
        return None

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def send_email(to_email, subject, body):
    """Send email using SMTP"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email sending error: {e}")
        return False

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

        # Ensure email column exists
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'email'")
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE bookings ADD COLUMN email VARCHAR(100) DEFAULT NULL")
                db.commit()
            except Exception as e:
                print(f"Error adding email column: {e}")

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
        email = request.form.get('email')
        phone = request.form.get('phone')
        sport = request.form.get('sport')
        turf = request.form.get('turf')
        slot = request.form.get('slot')
        booking_date = request.form.get('date')

        # Validate inputs
        if not all([name, email, phone, sport, turf, slot, booking_date]):
            return "All fields are required!", 400

        # Validate email
        if not validate_email(email):
            flash('Please enter a valid email address', 'error')
            return redirect('/booking')

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

        # Insert booking with pending status
        cursor.execute("""
            INSERT INTO bookings (name, email, phone, sport, turf, slot_time, booking_date, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (name, email, phone, sport, turf, slot, booking_date))

        booking_id = cursor.lastrowid
        db.commit()
        
        # Send confirmation email to user
        email_subject = "Booking Request Received - Sports Center"
        email_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #27ae60;">Booking Request Received</h2>
            <p>Dear <strong>{name}</strong>,</p>
            <p>Your booking request has been received and is waiting for admin confirmation.</p>
            
            <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h3 style="margin-top: 0;">Booking Details:</h3>
                <p><strong>Booking ID:</strong> #{booking_id}</p>
                <p><strong>Sport:</strong> {sport}</p>
                <p><strong>Turf:</strong> {turf}</p>
                <p><strong>Date:</strong> {booking_date}</p>
                <p><strong>Time:</strong> {slot}</p>
                <p><strong>Name:</strong> {name}</p>
                <p><strong>Phone:</strong> {phone}</p>
            </div>
            
            <p>You will receive another email once your booking is confirmed or rejected by the admin.</p>
            <p>Thank you for choosing Sports Center!</p>
            <hr>
            <p style="font-size: 12px; color: #888;">Sports Center, Njarakkal</p>
        </body>
        </html>
        """
        
        send_email(email, email_subject, email_body)
        
        # Send notification to admin
        admin_subject = "New Booking Request - Pending Approval"
        admin_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #ffc107;">New Booking Request - Pending Approval</h2>
            <p><strong>Booking ID:</strong> #{booking_id}</p>
            <p><strong>Name:</strong> {name}</p>
            <p><strong>Email:</strong> {email}</p>
            <p><strong>Phone:</strong> {phone}</p>
            <p><strong>Sport:</strong> {sport}</p>
            <p><strong>Turf:</strong> {turf}</p>
            <p><strong>Date:</strong> {booking_date}</p>
            <p><strong>Time:</strong> {slot}</p>
            <br>
            <a href="http://your-domain.com/admin" style="background: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Go to Admin Panel</a>
        </body>
        </html>
        """
        
        send_email(EMAIL_CONFIG['admin_email'], admin_subject, admin_body)
        
        cursor.close()
        db.close()
        
        flash('Booking request submitted successfully! Check your email for confirmation.', 'success')
        return redirect('/mybookings')
    
    except Exception as e:
        print(f"Error in book route: {e}")
        return f"An error occurred while booking: {str(e)}", 500

# --- MY BOOKINGS ROUTE ---
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
        
        # Get precise column names
        column_names = [desc[0].lower() for desc in cursor.description]
        
        cursor.close()
        db.close()
        
        # Find indices
        id_idx = column_names.index('id') if 'id' in column_names else 0
        name_idx = column_names.index('name') if 'name' in column_names else 1
        sport_idx = column_names.index('sport') if 'sport' in column_names else 2
        turf_idx = column_names.index('turf') if 'turf' in column_names else 3
        time_idx = column_names.index('slot_time') if 'slot_time' in column_names else 4
        date_idx = column_names.index('booking_date') if 'booking_date' in column_names else 5
        status_idx = column_names.index('status') if 'status' in column_names else -1
        email_idx = column_names.index('email') if 'email' in column_names else -1
        phone_idx = column_names.index('phone') if 'phone' in column_names else -1

        normalized_bookings = []
        confirmed_count = 0
        pending_count = 0
        
        for booking in all_bookings:
            status = 'pending'
            
            if status_idx != -1 and len(booking) > status_idx:
                db_status = booking[status_idx]
                if db_status:
                    status = str(db_status).strip().lower()
            
            if status == 'confirmed':
                confirmed_count += 1
            else:
                pending_count += 1
                
            clean_booking = (
                booking[id_idx],
                booking[name_idx],
                booking[sport_idx],
                booking[turf_idx],
                booking[time_idx],
                booking[date_idx],
                status,
                booking[email_idx] if email_idx != -1 and len(booking) > email_idx else '',
                booking[phone_idx] if phone_idx != -1 and len(booking) > phone_idx else ''
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
        
        # Ensure columns exist
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'status'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE bookings ADD COLUMN status VARCHAR(20) DEFAULT NULL")
            db.commit()
        
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'email'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE bookings ADD COLUMN email VARCHAR(100) DEFAULT NULL")
            db.commit()
        
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'phone'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE bookings ADD COLUMN phone VARCHAR(20) DEFAULT NULL")
            db.commit()
        
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
        
        # Get booking details
        cursor.execute("SELECT * FROM bookings WHERE id=%s AND status='pending'", (id,))
        booking = cursor.fetchone()
        
        if not booking:
            flash('Booking not found or already processed', 'error')
            return redirect('/admin')
        
        # Get column indices
        column_names = [desc[0].lower() for desc in cursor.description]
        name_idx = column_names.index('name') if 'name' in column_names else 1
        email_idx = column_names.index('email') if 'email' in column_names else -1
        phone_idx = column_names.index('phone') if 'phone' in column_names else -1
        sport_idx = column_names.index('sport') if 'sport' in column_names else 2
        turf_idx = column_names.index('turf') if 'turf' in column_names else 3
        time_idx = column_names.index('slot_time') if 'slot_time' in column_names else 4
        date_idx = column_names.index('booking_date') if 'booking_date' in column_names else 5
        
        name = booking[name_idx]
        email = booking[email_idx] if email_idx != -1 and len(booking) > email_idx else ''
        phone = booking[phone_idx] if phone_idx != -1 and len(booking) > phone_idx else ''
        sport = booking[sport_idx]
        turf = booking[turf_idx]
        slot = booking[time_idx]
        booking_date = booking[date_idx]
        
        # Confirm the booking
        cursor.execute("UPDATE bookings SET status='confirmed' WHERE id=%s", (id,))
        db.commit()
        
        # Send confirmation email with payment details
        email_subject = "Booking Confirmed - Sports Center"
        email_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #27ae60;">Booking Confirmed! ✅</h2>
            <p>Dear <strong>{name}</strong>,</p>
            <p>Your booking has been <strong style="color: #28a745;">CONFIRMED</strong> by the admin.</p>
            
            <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h3 style="margin-top: 0;">Booking Details:</h3>
                <p><strong>Booking ID:</strong> #{id}</p>
                <p><strong>Sport:</strong> {sport}</p>
                <p><strong>Turf:</strong> {turf}</p>
                <p><strong>Date:</strong> {booking_date}</p>
                <p><strong>Time:</strong> {slot}</p>
            </div>
            
            <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 5px;">
                <h3 style="margin-top: 0; color: #856404;">Payment Instructions 💰</h3>
                <p><strong>Booking Amount:</strong> ₹{BOOKING_AMOUNT}</p>
                <p><strong>Payment Number (UPI):</strong> <span style="font-size: 20px; font-weight: bold;">{PAYMENT_NUMBER}</span></p>
                <p><strong>Payment Methods:</strong></p>
                <ul>
                    <li>Google Pay: {PAYMENT_NUMBER}</li>
                    <li>PhonePe: {PAYMENT_NUMBER}</li>
                    <li>Paytm: {PAYMENT_NUMBER}</li>
                </ul>
                <p><strong>QR Code:</strong> Please scan the QR code at the center to complete payment</p>
                <p style="color: #856404; margin-top: 10px;"><strong>⚠️ Note:</strong> Please complete the payment before your slot time. Show this confirmation email at the center.</p>
            </div>
            
            <p>If you have any questions, please contact us at +91 {PAYMENT_NUMBER}</p>
            <p>Thank you for choosing Sports Center!</p>
            <hr>
            <p style="font-size: 12px; color: #888;">Sports Center, Njarakkal | Phone: +91 {PAYMENT_NUMBER}</p>
        </body>
        </html>
        """
        
        if email:
            send_email(email, email_subject, email_body)
        
        flash(f'✅ Booking confirmed for {name}. Confirmation email sent.', 'success')
        
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
        
        # Get booking details
        cursor.execute("SELECT * FROM bookings WHERE id=%s AND status='pending'", (id,))
        booking = cursor.fetchone()
        
        if not booking:
            flash('Booking not found or already processed', 'error')
            return redirect('/admin')
        
        # Get column indices
        column_names = [desc[0].lower() for desc in cursor.description]
        name_idx = column_names.index('name') if 'name' in column_names else 1
        email_idx = column_names.index('email') if 'email' in column_names else -1
        
        name = booking[name_idx]
        email = booking[email_idx] if email_idx != -1 and len(booking) > email_idx else ''
        
        # Delete the pending booking
        cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
        db.commit()
        
        # Send rejection email
        if email:
            email_subject = "Booking Request Status - Sports Center"
            email_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #dc3545;">Booking Request Update</h2>
                <p>Dear <strong>{name}</strong>,</p>
                <p>We regret to inform you that your booking request has been <strong style="color: #dc3545;">REJECTED</strong>.</p>
                
                <div style="background: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0; border-radius: 5px;">
                    <p><strong>Reason:</strong> The requested slot is no longer available or does not meet the criteria.</p>
                    <p><strong>Booking ID:</strong> #{id}</p>
                </div>
                
                <p>Please try booking a different slot. We apologize for any inconvenience.</p>
                <p>Thank you for your interest in Sports Center!</p>
                <hr>
                <p style="font-size: 12px; color: #888;">Sports Center, Njarakkal</p>
            </body>
            </html>
            """
            send_email(email, email_subject, email_body)
        
        flash(f'❌ Booking rejected for {name}. Rejection email sent.', 'info')
        
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
    try:
        db = get_db_connection()
        if db is None:
            flash("Database connection failed", "error")
            return redirect('/admin')
        
        cursor = db.cursor()
        
        # Get booking details
        cursor.execute("SELECT * FROM bookings WHERE id=%s AND status='confirmed'", (id,))
        booking = cursor.fetchone()
        
        if not booking:
            flash('Booking not found or already cancelled', 'error')
            return redirect('/admin')
        
        # Get column indices
        column_names = [desc[0].lower() for desc in cursor.description]
        name_idx = column_names.index('name') if 'name' in column_names else 1
        email_idx = column_names.index('email') if 'email' in column_names else -1
        
        name = booking[name_idx]
        email = booking[email_idx] if email_idx != -1 and len(booking) > email_idx else ''
        
        # Delete the confirmed booking
        cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
        db.commit()
        
        # Send cancellation email
        if email:
            email_subject = "Booking Cancellation Notice - Sports Center"
            email_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #dc3545;">Booking Cancelled</h2>
                <p>Dear <strong>{name}</strong>,</p>
                <p>Your confirmed booking has been <strong style="color: #dc3545;">CANCELLED</strong> by the administrator.</p>
                
                <div style="background: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0; border-radius: 5px;">
                    <p><strong>Booking ID:</strong> #{id}</p>
                </div>
                
                <p>If you have already made the payment, please contact us for a refund.</p>
                <p>We apologize for any inconvenience caused.</p>
                <hr>
                <p style="font-size: 12px; color: #888;">Sports Center, Njarakkal | Contact: +91 {PAYMENT_NUMBER}</p>
            </body>
            </html>
            """
            send_email(email, email_subject, email_body)
        
        flash(f'✅ Booking cancelled successfully for {name}. Cancellation email sent.', 'success')
        
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
        
        # Get column indices
        column_names = [desc[0].lower() for desc in cursor.description]
        name_idx = column_names.index('name') if 'name' in column_names else 1
        email_idx = column_names.index('email') if 'email' in column_names else -1
        
        name = booking[name_idx]
        email = booking[email_idx] if email_idx != -1 and len(booking) > email_idx else ''
        
        # Delete the booking
        cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
        db.commit()
        
        # Send cancellation email
        if email:
            email_subject = "Booking Cancelled - Sports Center"
            email_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #dc3545;">Booking Cancelled</h2>
                <p>Dear <strong>{name}</strong>,</p>
                <p>Your booking has been successfully cancelled.</p>
                
                <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <p><strong>Booking ID:</strong> #{id}</p>
                </div>
                
                <p>If you have already made the payment, please contact us for a refund.</p>
                <p>We hope to see you again!</p>
                <hr>
                <p style="font-size: 12px; color: #888;">Sports Center, Njarakkal</p>
            </body>
            </html>
            """
            send_email(email, email_subject, email_body)
        
        affected_rows = cursor.rowcount
        cursor.close()
        db.close()
        
        if affected_rows == 0:
            flash('Booking not found', 'error')
        else:
            flash('✅ Booking cancelled successfully! A confirmation email has been sent.', 'success')
            
        return redirect('/mybookings')
    
    except Exception as e:
        print(f"Error in confirmcancel route: {e}")
        flash(f'An error occurred while cancelling: {str(e)}', 'error')
        return redirect('/mybookings')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
