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
                cursor.execute("UPDATE bookings SET status = 'pending' WHERE status IS NULL")
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
        
        # Ensure status column exists
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'status'")
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE bookings ADD COLUMN status VARCHAR(20) DEFAULT NULL")
                db.commit()
                cursor.execute("UPDATE bookings SET status = 'pending' WHERE status IS NULL")
                db.commit()
            except Exception as e:
                print(f"Error adding status column: {e}")
        
        # Get all bookings
        cursor.execute("SELECT * FROM bookings ORDER BY booking_date DESC, slot_time DESC")
        raw_bookings = cursor.fetchall()
        cursor.close()
        db.close()
        
        # Normalize status to lowercase and ensure it's a string
        normalized_bookings = []
        for b in raw_bookings:
            booking_list = list(b)
            if len(booking_list) > 6:
                status = booking_list[6]
                if status is None:
                    status = 'pending'
                else:
                    status = status.lower()
                booking_list[6] = status
            normalized_bookings.append(tuple(booking_list))
        
        # Calculate statistics
        total = len(normalized_bookings)
        confirmed = 0
        pending = 0
        for b in normalized_bookings:
            if len(b) > 6:
                if b[6] == 'confirmed':
                    confirmed += 1
                else:
                    pending += 1
            else:
                pending += 1
        
        print(f"MyBookings -> Total: {total}, Confirmed: {confirmed}, Pending: {pending}")
        
        return render_template(
            "mybookings.html",
            bookings=normalized_bookings,
            total_bookings=total,
            confirmed_count=confirmed,
            pending_count=pending
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
        
        cursor.execute("SELECT * FROM bookings WHERE id=%s AND status='pending'", (id,))
        booking = cursor.fetchone()
        
        if not booking:
            flash('Booking not found or already processed', 'error')
            return redirect('/admin')
        
        # Set status to lowercase 'confirmed'
        cursor.execute("UPDATE bookings SET status='confirmed' WHERE id=%s", (id,))
        db.commit()
        
        flash(f'✅ Booking confirmed for {booking[1]} on {booking[5]} at {booking[4]}', 'success')
        
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
            flash('Only confirmed bookings can be cancelled. Please contact admin.', 'error')
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
            flash('Only confirmed bookings can be cancelled. Please contact admin.', 'error')
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

# --- DEBUG STATUS ROUTE ---
@app.route('/debug-status')
def debug_status():
    """Debug route to check status values"""
    try:
        db = get_db_connection()
        if db is None:
            return "Database connection failed", 500
        
        cursor = db.cursor()
        
        # Get all bookings with status
        cursor.execute("SELECT id, name, status FROM bookings ORDER BY id DESC")
        bookings = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Status Debug</title>
            <style>
                body { font-family: monospace; padding: 20px; background: #f5f5f5; }
                .container { background: white; padding: 20px; border-radius: 8px; }
                table { border-collapse: collapse; width: 100%; margin-top: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background: #4CAF50; color: white; }
                .pending { color: orange; font-weight: bold; }
                .confirmed { color: green; font-weight: bold; }
                .null { color: red; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Booking Status Debug</h1>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Name</th>
                            <th>Status Value</th>
                            <th>Status Type</th>
                        </thead>
                    </thead>
                    <tbody>
        """
        
        for booking in bookings:
            status = booking[2]
            status_class = ""
            status_display = ""
            
            if status == 'confirmed':
                status_class = "confirmed"
                status_display = "✅ Confirmed"
            elif status == 'pending':
                status_class = "pending"
                status_display = "⏳ Pending"
            elif status is None:
                status_class = "null"
                status_display = "❌ NULL"
            else:
                status_class = "null"
                status_display = f"❌ {status}"
            
            html += f"""
                        2
                            <td>#{booking[0]}</td>
                            <td>{booking[1]}</td>
                            <td class="{status_class}">{booking[2]}</td>
                            <td class="{status_class}">{status_display}</td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
                <br>
                <a href="/fix-database" style="background: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Fix Database</a>
                <a href="/mybookings" style="background: #2196F3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-left: 10px;">Back to My Bookings</a>
            </div>
        </body>
        </html>
        """
        
        return html
    
    except Exception as e:
        return f"Error: {str(e)}"

# --- FIX DATABASE ROUTE ---
@app.route('/fix-database')
def fix_database():
    """Fix database by properly setting status values"""
    try:
        db = get_db_connection()
        if db is None:
            return "Database connection failed", 500
        
        cursor = db.cursor()
        
        messages = []
        
        # Check if status column exists
        cursor.execute("SHOW COLUMNS FROM bookings LIKE 'status'")
        status_exists = cursor.fetchone()
        
        if not status_exists:
            cursor.execute("ALTER TABLE bookings ADD COLUMN status VARCHAR(20) DEFAULT NULL")
            db.commit()
            messages.append("✅ Status column added successfully!")
        
        # Update NULL or empty status to 'pending'
        cursor.execute("UPDATE bookings SET status = 'pending' WHERE status IS NULL OR status = ''")
        updated_count = cursor.rowcount
        messages.append(f"✅ Set {updated_count} bookings to 'pending' status")
        
        # Also update any invalid status values to 'pending'
        cursor.execute("UPDATE bookings SET status = 'pending' WHERE status NOT IN ('pending', 'confirmed')")
        invalid_count = cursor.rowcount
        if invalid_count > 0:
            messages.append(f"✅ Fixed {invalid_count} bookings with invalid status")
        
        # Get current bookings with status
        cursor.execute("SELECT id, name, status FROM bookings ORDER BY id DESC")
        bookings = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        # Calculate stats
        confirmed_count = sum(1 for b in bookings if b[2] == 'confirmed')
        pending_count = sum(1 for b in bookings if b[2] == 'pending')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Database Fix - Sports Center</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }}
                .container {{ background: white; padding: 20px; border-radius: 8px; max-width: 800px; margin: 0 auto; }}
                .success {{ color: green; font-weight: bold; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background: #4CAF50; color: white; }}
                .btn {{ display: inline-block; background: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 20px; margin-right: 10px; }}
                .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
                .stat-box {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; flex: 1; }}
                .stat-number {{ font-size: 32px; font-weight: bold; }}
                .stat-label {{ color: #666; margin-top: 5px; }}
                .confirmed {{ color: green; font-weight: bold; }}
                .pending {{ color: orange; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Database Fix Results</h1>
        """
        
        for msg in messages:
            html += f"<p class='success'>✓ {msg}</p>"
        
        html += f"""
                <div class="stats">
                    <div class="stat-box">
                        <div class="stat-number">{len(bookings)}</div>
                        <div class="stat-label">Total Bookings</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number" style="color: #28a745;">{confirmed_count}</div>
                        <div class="stat-label">Confirmed</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number" style="color: #ffc107;">{pending_count}</div>
                        <div class="stat-label">Pending</div>
                    </div>
                </div>
                
                <h2>Current Bookings with Status:</h2>
                <table>
                    <thead>
                        2
                            <th>ID</th>
                            <th>Name</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for booking in bookings:
            status_class = "confirmed" if booking[2] == 'confirmed' else "pending"
            status_display = "✅ Confirmed" if booking[2] == 'confirmed' else "⏳ Pending"
            html += f"""
                        <tr>
                            <td>#{booking[0]}</td>
                            <td>{booking[1]}</td>
                            <td class="{status_class}">{status_display}</td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
                <br>
                <p><strong>Note:</strong> All bookings are now set to 'pending'. Use the admin panel to confirm bookings.</p>
                <a href="/admin" class="btn" style="background: #2196F3;">Go to Admin Panel</a>
                <a href="/mybookings" class="btn">Go to My Bookings</a>
                <a href="/debug-status" class="btn" style="background: #666;">Debug Status</a>
            </div>
        </body>
        </html>
        """
        
        return html
    
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
