from flask import Flask, render_template, request, redirect, url_for, session
from flask_mail import Mail, Message
import uuid, json, os, random
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'dev'

USERS_FILE = 'users.json'
REVIEWS_FILE = 'reviews.json'
VERIFICATION_FILE = 'pending_verifications.json'

# Read the email password from password.txt
with open('password.txt') as f:
    email_password = f.read().strip()

# Email config (replace with your SpaceMail credentials)
app.config['MAIL_SERVER'] = 'mail.spacemail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True    # <- Use SSL
app.config['MAIL_USE_TLS'] = False   # <- Turn off TLS
app.config['MAIL_USERNAME'] = 'contact@rousehillhighschool.com'
app.config['MAIL_PASSWORD'] = email_password
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

# Auth helpers
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
        email = request.form['email']
        password = request.form['password']
        # if not email.endswith('@education.nsw.gov.au'):
        #     return "Email must end with @education.nsw.gov.au"
        
        users = load_json(USERS_FILE)
        if any(u['email'] == email for u in users):
            return "Email already registered"

        # Generate and email verification code
        code = str(random.randint(100000, 999999))
        pending = load_json(VERIFICATION_FILE)
        pending.append({"email": email, "password": password, "code": code})
        save_json(VERIFICATION_FILE, pending)

        msg = Message("Your Verification Code",
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[email])
        msg.body = f"Your verification code is: {code}"
        mail.send(msg)

        return redirect(url_for('verify_email', email=email))
    return render_template('signup.html')

@app.route('/verify/<email>', methods=['GET', 'POST'])
def verify_email(email):
    if request.method == 'POST':
        code_input = request.form['code']
        pending = load_json(VERIFICATION_FILE)
        entry = next((p for p in pending if p['email'] == email), None)
        if entry and entry['code'] == code_input:
            # Add to users
            users = load_json(USERS_FILE)
            users.append({"email": entry['email'], "password": entry['password']})
            save_json(USERS_FILE, users)
            # Remove from pending
            pending = [p for p in pending if p['email'] != email]
            save_json(VERIFICATION_FILE, pending)
            return redirect(url_for('login'))
        return "Invalid code"
    return render_template('verify.html', email=email)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        users = load_json(USERS_FILE)
        user = next((u for u in users if u['email'] == email and u['password'] == password), None)
        if user:
            session['email'] = email
            return redirect(url_for('review'))
        else:
            return "Invalid credentials"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/review', methods=['GET', 'POST'])
@login_required
def review():
    if request.method == 'POST':
        name = request.form['name']
        stars = int(request.form['stars'])
        comment = request.form['comment']
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
