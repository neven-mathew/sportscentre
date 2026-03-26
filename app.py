from flask import Flask, render_template, request, redirect, session, flash
from flask_mail import Mail, Message  # <-- ADD THIS
import mysql.connector
from mysql.connector import Error
from datetime import date as d, datetime
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# --- MAIL CONFIGURATION ---
# IMPORTANT: If using Gmail, use an "App Password" instead of your real password.
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com') 
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your-app-password')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')

mail = Mail(app)

# --- PAYMENT CONFIGURATION ---
# You can change this number whenever you need to
PAYMENT_NUMBER = '7012631996' 
ADVANCE_AMOUNT = '200'

# Database configuration
# ... (Keep your existing DB_CONFIG and get_db_connection)
