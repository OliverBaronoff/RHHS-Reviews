from flask import Flask, render_template, request, redirect, url_for, session
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import uuid, json, os, random
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'dev'

USERS_FILE = 'users.json'
REVIEWS_FILE = 'reviews.json'
VERIFICATION_FILE = 'pending_verifications.json'

# Load email password
with open('password.txt') as f:
    email_password = f.read().strip()

# Email configuration
app.config['MAIL_SERVER'] = 'mail.spacemail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = 'contact@rousehillhighschool.com'
app.config['MAIL_PASSWORD'] = email_password
app.config['MAIL_DEFAULT_SENDER'] = ('Rouse Hill High School', 'contact@rousehillhighschool.com')
mail = Mail(app)

# JSON helpers
def load_json(file):
    if os.path.exists(file):
        try:
            with open(file, 'r') as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
        except json.JSONDecodeError:
            pass
    return []

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

# Auth decorator
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    sort = request.args.get('sort', 'newest')
    reviews = load_json(REVIEWS_FILE)
    if sort == 'oldest':
        reviews.sort(key=lambda r: r['timestamp'])
    elif sort == 'stars':
        reviews.sort(key=lambda r: r['stars'], reverse=True)
    else:
        reviews.sort(key=lambda r: r['timestamp'], reverse=True)
    return render_template('index.html', reviews=reviews)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password'].strip()

        users = load_json(USERS_FILE)
        if any(u['email'] == email for u in users):
            return render_template('signup.html', error="Email already registered.")

        code = str(random.randint(100000, 999999))
        pending = load_json(VERIFICATION_FILE)
        pending.append({
            "email": email,
            "password": password,
            "code": code
        })
        save_json(VERIFICATION_FILE, pending)

        msg = Message("Your Verification Code", recipients=[email])
        msg.body = f"Your verification code for RouseHillHighSchool.com is: {code}"
        msg.html = f"""
        <p>Hello,</p>
        <p>Your verification code for <strong>RouseHillHighSchool.com</strong> is: <strong>{code}</strong></p>
        <p>Please enter this code to complete your signup.</p>
        <p>Regards,<br>RouseHillHighSchool.com</p>
        """
        mail.send(msg)

        session['verify_email'] = email
        return redirect(url_for('verify_email'))

    return render_template('signup.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify_email():
    email = session.get('verify_email')
    if not email:
        return redirect(url_for('signup'))

    if request.method == 'POST':
        entered_code = request.form['code'].strip()
        pending = load_json(VERIFICATION_FILE)
        user_entry = next((p for p in pending if p['email'] == email and p['code'] == entered_code), None)

        if user_entry:
            users = load_json(USERS_FILE)
            if not any(u['email'] == email for u in users):
                users.append({'email': email, 'password': user_entry['password']})
                save_json(USERS_FILE, users)

            pending = [p for p in pending if p['email'] != email]
            save_json(VERIFICATION_FILE, pending)

            session.pop('verify_email', None)
            return redirect(url_for('login'))
        else:
            return render_template('verify.html', email=email, error="Incorrect verification code")

    return render_template('verify.html', email=email)

@app.route('/login', methods=['GET', 'POST'])
def login():
    login_error = None
    signup_error = None
    active_tab = 'login'  # Default to login tab

    if request.method == 'POST':
        action = request.form.get('action')
        email = request.form['email'].strip().lower()
        password = request.form['password'].strip()

        if action == 'login':
            active_tab = 'login'
            users = load_json(USERS_FILE)
            user = next((u for u in users if u['email'] == email), None)
            if user and check_password_hash(user['password'], password):
                session['email'] = email
                return redirect(url_for('review'))
            else:
                login_error = "Invalid login credentials."

        elif action == 'signup':
            active_tab = 'signup'
            confirm_password = request.form['confirm_password'].strip()
            if not email.endswith('@education.nsw.gov.au'):
                signup_error = "Email must end with @education.nsw.gov.au."
            elif password != confirm_password:
                signup_error = "Passwords do not match."
            else:
                users = load_json(USERS_FILE)
                if any(u['email'] == email for u in users):
                    signup_error = "Email is already registered."
                else:
                    code = str(random.randint(100000, 999999))
                    pending = load_json(VERIFICATION_FILE)
                    pending.append({
                        "email": email,
                        "password": generate_password_hash(password),
                        "code": code
                    })
                    save_json(VERIFICATION_FILE, pending)

                    msg = Message("Your Verification Code", recipients=[email])
                    msg.body = f"Your verification code is: {code}"
                    msg.html = f"<p>Your verification code is: <strong>{code}</strong></p>"
                    mail.send(msg)

                    session['verify_email'] = email
                    return redirect(url_for('verify_email'))

    return render_template(
        'login.html',
        login_error=login_error,
        signup_error=signup_error,
        active_tab=active_tab
    )

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/review', methods=['GET', 'POST'])
@login_required
def review():
    if request.method == 'POST':
        name = request.form['name'].strip()
        stars = int(request.form['stars'])
        comment = request.form['comment'].strip()
        anonymous = 'anonymous' in request.form

        review = {
            'email': session['email'],
            'name': 'Anonymous' if anonymous else name,
            'review_id': str(uuid.uuid4()),
            'stars': stars,
            'comment': comment,
            'anonymous': anonymous,
            'timestamp': datetime.utcnow().isoformat()
        }

        reviews = load_json(REVIEWS_FILE)
        reviews.append(review)
        save_json(REVIEWS_FILE, reviews)

        return redirect(url_for('index'))

    return render_template('review.html')

# Ensure valid JSON files exist
for f in [USERS_FILE, REVIEWS_FILE, VERIFICATION_FILE]:
    if not os.path.exists(f):
        with open(f, 'w') as file:
            json.dump([], file)

if __name__ == '__main__':
    app.run(debug=True)
