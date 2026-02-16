from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import secrets
import string
import qrcode
import io
import os
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

load_dotenv()
app=Flask(__name__)
#app.secret_key = os.getenv("SECRET_KEY") or "super_secret_dev_key"
#fernet = Fernet(os.environ.get("SECRET_KEY"))
# --- Configuration ---
#app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///keykeeper.db'
app.config['SECRET_KEY'] =os.getenv("SECRET_KEY") or 'your_secret_key_here'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# --- Login Manager ---
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Models ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
   # profile_picture = db.Column(db.String(120), default='default.jpg')
    #joined_on = db.Column(db.DateTime, default=datetime.utcnow)

class PasswordEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String(100), nullable=False)
    site_username = db.Column(db.String(100), nullable=False)
    site_password = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
  # email = db.Column(db.String(150), nullable=False)

class QRToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(100), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)

# --- Load User ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Create DB ---
with app.app_context():
    db.create_all()

# --- Routes ---
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/test_db')
def test_db():
    return str(PasswordEntry.query.all())

@app.route('/profile')
@login_required
def profile():
   return render_template('profile.html', user=current_user)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or email already exists!', 'danger')
            return redirect(url_for('register'))

        new_user = User(username=username, password=hashed_pw, email=email)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')
            
            if not username or not password:
                flash('Please enter both username and password', 'danger')
                return redirect(url_for('login'))
            
            user = User.query.filter_by(username=username).first()
            
            if not user:
                flash('Invalid username or password', 'danger')
                return redirect(url_for('login'))
            
            if bcrypt.check_password_hash(user.password, password):
                login_user(user)
                flash('Logged in successfully!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'danger')
                return redirect(url_for('login'))
                
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'danger')
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/view_passwords', methods=['GET', 'POST'])
@login_required
def view_passwords():
    passwords = []
    if request.method == 'POST':
        query = request.form['query']
        passwords = PasswordEntry.query.filter(
            PasswordEntry.user_id == current_user.id,
            (PasswordEntry.site_name.ilike(f"%{query}%")) |
            (PasswordEntry.site_username.ilike(f"%{query}%"))
        ).all()
    else:
        passwords = PasswordEntry.query.filter_by(user_id=current_user.id).all()
    return render_template('view_passwords.html', passwords=passwords)
    decrypted_passwords = []
    for p in passwords:
        decrypted_passwords.append({
        'id': p.id,
        'website': p.website,
        'username': p.username,
        'password': fernet.decrypt(p.password.encode()).decode()
    })
    
    

@app.route('/add_password', methods=['GET', 'POST'])
@login_required
def add_password():
    if request.method == 'POST':
        site_name = request.form['site_name']
        site_username = request.form['site_username']
        site_password = request.form['site_password']
        new_entry = PasswordEntry(
            site_name=site_name,
            site_username=site_username,
            site_password=site_password,
            user_id=current_user.id,
           # email=current_user.email
        )
        db.session.add(new_entry)
        db.session.commit()
        flash('Password added successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_password.html')
    encrypted_password = fernet.encrypt(password.encode()).decode()
    new_password = Password(
    website=website,
    username=username,
    password=encrypted_password,
    user_id=current_user.id)
    

@app.route('/edit_password/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def edit_password(entry_id):
    entry = PasswordEntry.query.get_or_404(entry_id)
    if entry.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('view_passwords'))

    if request.method == 'POST':
        entry.site_name = request.form['site_name']
        entry.site_username = request.form['site_username']
        entry.site_password = request.form['site_password']
        db.session.commit()
        flash('Password updated successfully!', 'success')
        return redirect(url_for('view_passwords'))

    return render_template('edit_password.html', entry=entry)

@app.route('/delete_password/<int:entry_id>', methods=['GET'])
@login_required
def delete_password(entry_id):
    entry = PasswordEntry.query.get_or_404(entry_id)
    if entry.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('view_passwords'))

    db.session.delete(entry)
    db.session.commit()
    flash('Password deleted successfully!', 'info')
    return redirect(url_for('view_passwords'))

@app.route('/generate_password')
def generate_password():
    length = 16
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(characters) for _ in range(length))
    return jsonify({'password': password})

@app.route('/generate_qr')
def generate_qr():
    if request.args.get('raw') == 'true':
        # Generate and return raw QR code image
        qr_data = url_for('qr_auth', _external=True)
        img = qrcode.make(qr_data)
        buffer = io.BytesIO()
        img.save(buffer, 'PNG')
        buffer.seek(0)
        return send_file(buffer, mimetype='image/png')
    else:
        # Show the QR code page
        return render_template('show_qr.html')

@app.route('/qr_auth', methods=['GET', 'POST'])
def qr_auth():
    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            flash("Email is required.", "error")
            return redirect(url_for('qr_auth'))

        user = User.query.filter_by(email=email).first()
        if user:
            print(f"[QR AUTH] Found user: {user.email}")
            login_user(user)
            flash("QR login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("No user found with this email.", "error")
            return redirect(url_for('qr_auth'))

    return render_template('qr_auth.html')

@app.route('/qr_scanner')
def qr_scanner():
    token = request.args.get('token')
    if not token:
        return redirect(url_for('login'))
    return render_template('qr_scanner.html', token=token)

@app.route('/check_qr_status/<token>')
def check_qr_status(token):
    stored_token = session.get('qr_token')
    token_time = datetime.fromisoformat(session.get('qr_token_time', datetime.utcnow().isoformat()))
    
    if not stored_token or stored_token != token:
        return jsonify({'status': 'invalid'})
    
    # Check if token is expired (5 minutes)
    token_age = datetime.utcnow() - token_time
    if token_age.total_seconds() > 300:  # 5 minutes
        return jsonify({'status': 'expired'})
    
    return jsonify({'status': 'valid'})

@app.route("/change_password", methods=["POST"])
@login_required
def change_password():
    current_password = request.form["current_password"]
    new_password = request.form["new_password"]
    confirm_password = request.form["confirm_password"]

    user = current_user

    # Check current password
    if not bcrypt.check_password_hash(user.password, current_password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("profile"))

    # Check new passwords match
    if new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return redirect(url_for("profile"))

    # Update password
    hashed_pw = bcrypt.generate_password_hash(new_password).decode("utf-8")
    user.password = hashed_pw
    db.session.commit()
    flash("Password changed successfully!", "success")
    return redirect(url_for("profile"))

@app.route('/delete_account', methods=['GET', 'POST'])
@login_required
def delete_account():
    if request.method == 'POST':
        db.session.delete(current_user)
        db.session.commit()
        logout_user()
        flash('Your account has been permanently deleted.', 'info')
        return redirect(url_for('login'))
    return render_template('delete_account.html')

# --- Run App ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

#if __name__ == '__main__':
#    app.run(host='0.0.0.0', port=5000, debug=True)
#with app.app_context():
 #   db.create_all()