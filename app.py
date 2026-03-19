app.py
from flask import Flask, render_template, request, redirect
import mysql.connector
from datetime import date as d

app = Flask(__name__)

db = mysql.connector.connect(
    host="autorack.proxy.rlwy.net",
    user="root",app.py
from flask import Flask, render_template, request, redirect
import mysql.connector
from mysql.connector import Error
from datetime import date as d
import os

app = Flask(__name__)

# Database connection with error handling
def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host="autorack.proxy.rlwy.net",
            user="root",
            password="PRlkjHknXZNbCjcqMbmxqexeHKawUqow",
            database="railway",
            port=37887
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

# --- INDEX ROUTE ---
@app.route('/', methods=['GET'])
def index():
    db = get_db_connection()
    if db is None:
        return "Database connection failed", 500
    
    cursor = db.cursor(dictionary=True)

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

# --- BOOK ROUTE ---
@app.route('/book', methods=['POST'])
def book():
    db = get_db_connection()
    if db is None:
        return "Database connection failed", 500
    
    cursor = db.cursor()

    name = request.form['name']
    sport = request.form['sport']
    turf = request.form['turf']
    slot = request.form['slot']
    booking_date = request.form['date']

    try:
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
    
    except Error as e:
        print(f"Database error: {e}")
        db.rollback()
        cursor.close()
        db.close()
        return f"An error occurred: {e}", 500

# --- CANCEL ROUTES ---
@app.route('/cancelpage/<int:id>')
def cancelpage(id):
    db = get_db_connection()
    if db is None:
        return "Database connection failed", 500
    
    cursor = db.cursor()
    cursor.execute("SELECT * FROM bookings WHERE id=%s", (id,))
    booking = cursor.fetchone()
    
    cursor.close()
    db.close()

    return render_template("cancel.html", booking=booking)

@app.route('/confirmcancel/<int:id>')
def confirmcancel(id):
    db = get_db_connection()
    if db is None:
        return "Database connection failed", 500
    
    cursor = db.cursor()
    
    try:
        cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
        db.commit()
        cursor.close()
        db.close()
        return redirect('/')
    
    except Error as e:
        print(f"Error cancelling booking: {e}")
        db.rollback()
        cursor.close()
        db.close()
        return f"An error occurred while cancelling: {e}", 500

if __name__ == '__main__':
    app.run(debug=True)
    password="PRlkjHknXZNbCjcqMbmxqexeHKawUqow",
    database="railway",
    port=37887  # <-- Added missing comma after database parameter
)

# --- INDEX ROUTE ---
@app.route('/', methods=['GET'])
def index():
    cursor = db.cursor()

    # Get all bookings
    cursor.execute("SELECT * FROM bookings")
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

    return render_template(
        "index.html",
        bookings=all_bookings,
        slots=slots,
        booked=booked,
        date=selected_date
    )

# --- BOOK ROUTE (ONLY ONE) ---
@app.route('/book', methods=['POST'])
def book():
    name = request.form['name']
    sport = request.form['sport']
    turf = request.form['turf']
    slot = request.form['slot']
    booking_date = request.form['date']

    cursor = db.cursor()

    # Check if slot already booked
    cursor.execute("""
        SELECT * FROM bookings
        WHERE turf=%s AND slot_time=%s AND booking_date=%s
    """, (turf, slot, booking_date))

    existing = cursor.fetchone()

    if existing:
        return "Slot already booked for this turf!"

    # Insert booking
    cursor.execute("""
        INSERT INTO bookings (name, sport, turf, slot_time, booking_date)
        VALUES (%s, %s, %s, %s, %s)
    """, (name, sport, turf, slot, booking_date))

    db.commit()

    return redirect('/')

# --- CANCEL ROUTES ---
@app.route('/cancel/<int:id>')
def cancel(id):
    cursor = db.cursor()
    cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
    db.commit()
    return redirect('/')

@app.route('/cancelpage/<int:id>')
def cancelpage(id):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM bookings WHERE id=%s", (id,))
    booking = cursor.fetchone()

    return render_template("cancel.html", booking=booking)

@app.route('/confirmcancel/<int:id>')
def confirmcancel(id):
    cursor = db.cursor()
    cursor.execute("DELETE FROM bookings WHERE id=%s", (id,))
    db.commit()

    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
