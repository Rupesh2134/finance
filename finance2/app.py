import os
import re
import csv
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECORDS_DIR = os.path.join(BASE_DIR, 'records')

os.makedirs(RECORDS_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-for-local')

CSV_HEADERS = ['Date', 'Payment_Amount', 'Remaining_Balance', 'Notes']


def sanitize_username(name: str) -> str:
    """Return a filesystem-safe username (lowercase, alnum and underscore)."""
    s = name.strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_\-]", "", s)
    return s


def user_filepath(username: str) -> str:
    return os.path.join(RECORDS_DIR, f"{username}.csv")


def list_users():
    users = []
    for fname in os.listdir(RECORDS_DIR):
        if fname.endswith('.csv'):
            users.append(os.path.splitext(fname)[0])
    users.sort()
    return users


def read_csv_records(username: str):
    path = user_filepath(username)
    if not os.path.exists(path):
        return []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_initial_csv(username: str, total_loan: float, contact_info: str = ''):
    path = user_filepath(username)
    date = datetime.now().strftime('%Y-%m-%d')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerow({
            'Date': date,
            'Payment_Amount': '0',
            'Remaining_Balance': str(float(total_loan)),
            'Notes': 'Loan started' + (f' | {contact_info}' if contact_info else '')
        })


def append_payment(username: str, payment_amount: float, notes: str = ''):
    path = user_filepath(username)
    if not os.path.exists(path):
        raise FileNotFoundError('User file does not exist')

    # get last remaining balance
    records = read_csv_records(username)
    if records:
        last = records[-1]
        try:
            prev_balance = float(last.get('Remaining_Balance', '0') or 0)
        except ValueError:
            prev_balance = 0.0
    else:
        prev_balance = 0.0

    new_balance = prev_balance - float(payment_amount)
    date = datetime.now().strftime('%Y-%m-%d')

    with open(path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerow({
            'Date': date,
            'Payment_Amount': str(float(payment_amount)),
            'Remaining_Balance': str(new_balance),
            'Notes': notes
        })

    return new_balance


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
        path = user_filepath(uname)
        if os.path.exists(path):
            flash('User already exists. Choose a different name or record payments.', 'warning')
            return redirect(url_for('add_user'))

        write_initial_csv(uname, total_loan_val, contact_info)
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

        try:
            new_balance = append_payment(username, payment_val, notes)
        except FileNotFoundError:
            flash('Selected user does not exist.', 'danger')
            return redirect(url_for('record_payment'))

        flash(f'Payment added successfully. New remaining balance: {new_balance}', 'success')
        return redirect(url_for('view_history', username=username))

    return render_template('record_payment.html', users=users)


@app.route('/view_history/<username>')
def view_history(username):
    users = list_users()
    if username not in users:
        flash('User not found.', 'danger')
        return redirect(url_for('index'))

    records = read_csv_records(username)

    total_paid = 0.0
    remaining_balance = None
    for r in records:
        try:
            total_paid += float(r.get('Payment_Amount', '0') or 0)
        except ValueError:
            pass
        try:
            remaining_balance = float(r.get('Remaining_Balance'))
        except Exception:
            pass

    return render_template('view_history.html', username=username, users=users, records=records, total_paid=total_paid, remaining_balance=remaining_balance)


@app.route('/download/<username>')
def download(username):
    users = list_users()
    if username not in users:
        abort(404)
    path = user_filepath(username)
    if not os.path.exists(path):
        abort(404)

    return send_file(path, as_attachment=True, download_name=f"{username}.csv", mimetype='text/csv')


if __name__ == '__main__':
    app.run(debug=True)
