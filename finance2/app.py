import os
import re
import csv
import io
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECORDS_DIR = os.path.join(BASE_DIR, 'records')
DB_PATH = os.path.join(BASE_DIR, 'app.db')

os.makedirs(RECORDS_DIR, exist_ok=True)

app = Flask(__name__)

# Secret key (from environment or fallback)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-for-local')

# SQLAlchemy config (PostgreSQL for Render)
database_url = os.environ.get('DATABASE_URL')

# Render sometimes provides 'postgres://' instead of 'postgresql://'
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://")

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(120), unique=True, nullable=False)
    total_loan = db.Column(db.Float, nullable=False)
    contact_info = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    payments = db.relationship('Payment', backref='user', cascade='all, delete-orphan', lazy=True)


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    payment_amount = db.Column(db.Float, nullable=False)
    remaining_balance = db.Column(db.Float, nullable=False)
    notes = db.Column(db.String(255), nullable=True)


CSV_HEADERS = ['Date', 'Payment_Amount', 'Remaining_Balance', 'Notes']


def sanitize_username(name: str) -> str:
    """Return a filesystem-safe username (lowercase, alnum and underscore)."""
    s = name.strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_\-]", "", s)
    return s


def list_users():
    users = User.query.order_by(User.username).all()
    return [u.username for u in users]


def init_db():
    # Create database tables if they don't exist
    db.create_all()


with app.app_context():
    db.create_all()


@app.route('/')
def index():
    users = list_users()
    return render_template('index.html', users=users)


@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        total_loan = request.form.get('total_loan', '').strip()
        contact_info = request.form.get('contact_info', '').strip()

        if not name or not total_loan:
            flash('Name and Total Loan Amount are required.', 'danger')
            return redirect(url_for('add_user'))

        try:
            total_loan_val = float(total_loan)
        except ValueError:
            flash('Total Loan Amount must be a number.', 'danger')
            return redirect(url_for('add_user'))

        uname = sanitize_username(name)
        if User.query.filter_by(username=uname).first():
            flash('User already exists. Choose a different name or record payments.', 'warning')
            return redirect(url_for('add_user'))

        user = User(name=name, username=uname, total_loan=total_loan_val, contact_info=contact_info)
        db.session.add(user)
        # initial payment row with 0 payment and initial remaining balance
        date = datetime.now().strftime('%Y-%m-%d')
        payment = Payment(user=user, date=date, payment_amount=0.0, remaining_balance=total_loan_val, notes='Loan started' + (f' | {contact_info}' if contact_info else ''))
        db.session.add(payment)
        db.session.commit()

        flash(f'User "{name}" created successfully.', 'success')
        return redirect(url_for('index'))

    return render_template('add_user.html')


@app.route('/record_payment', methods=['GET', 'POST'])
def record_payment():
    users = list_users()
    if request.method == 'POST':
        username = request.form.get('username')
        payment_amount = request.form.get('payment_amount', '').strip()
        notes = request.form.get('notes', '').strip()

        if not username or not payment_amount:
            flash('User and payment amount are required.', 'danger')
            return redirect(url_for('record_payment'))

        try:
            payment_val = float(payment_amount)
        except ValueError:
            flash('Payment amount must be a number.', 'danger')
            return redirect(url_for('record_payment'))

        user = User.query.filter_by(username=username).first()
        if not user:
            flash('Selected user does not exist.', 'danger')
            return redirect(url_for('record_payment'))

        # get last remaining balance
        last_payment = Payment.query.filter_by(user_id=user.id).order_by(Payment.id.desc()).first()
        prev_balance = last_payment.remaining_balance if last_payment else user.total_loan
        new_balance = prev_balance - float(payment_val)

        date = datetime.now().strftime('%Y-%m-%d')
        payment = Payment(user=user, date=date, payment_amount=payment_val, remaining_balance=new_balance, notes=notes)
        db.session.add(payment)
        db.session.commit()

        flash(f'Payment added successfully. New remaining balance: {new_balance}', 'success')
        return redirect(url_for('view_history', username=username))

    return render_template('record_payment.html', users=users)


@app.route('/view_history/<username>')
def view_history(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('index'))

    records = Payment.query.filter_by(user_id=user.id).order_by(Payment.id.asc()).all()

    total_paid = sum((r.payment_amount for r in records), 0.0)
    remaining_balance = records[-1].remaining_balance if records else user.total_loan

    # Convert records to list of dicts for template compatibility
    recs = []
    for r in records:
        recs.append({
            'Date': r.date,
            'Payment_Amount': f"{r.payment_amount}",
            'Remaining_Balance': f"{r.remaining_balance}",
            'Notes': r.notes or ''
        })

    return render_template('view_history.html', username=username, users=list_users(), records=recs, total_paid=total_paid, remaining_balance=remaining_balance)


@app.route('/download/<username>')
def download(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        abort(404)

    records = Payment.query.filter_by(user_id=user.id).order_by(Payment.id.asc()).all()

    # generate CSV in memory
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(CSV_HEADERS)
    for r in records:
        writer.writerow([r.date, f"{r.payment_amount}", f"{r.remaining_balance}", r.notes or ''])

    mem = io.BytesIO()
    mem.write(si.getvalue().encode('utf-8'))
    mem.seek(0)
    return send_file(mem, as_attachment=True, download_name=f"{username}.csv", mimetype='text/csv')


@app.route('/health')
def health():
    return 'ok', 200


if __name__ == '__main__':
    # Ensure DB exists when running directly
    init_db()
    app.run(debug=True)




