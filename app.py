from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import os
from werkzeug.utils import secure_filename
from pymongo import MongoClient
import joblib
from sklearn.preprocessing import StandardScaler

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bikerental.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Mail settings
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

# Initialize extensions
db = SQLAlchemy(app)
mail = Mail(app)

def send_email(to, subject, body):
    """
    Send email with improved error handling and logging
    Returns: Boolean indicating success/failure
    """
    if not all([
        app.config['MAIL_USERNAME'],
        app.config['MAIL_PASSWORD'],
        app.config['MAIL_SERVER'],
        app.config['MAIL_PORT']
    ]):
        print("Email configuration error:")
        print(f"MAIL_USERNAME: {app.config['MAIL_USERNAME']}")
        print(f"MAIL_SERVER: {app.config['MAIL_SERVER']}")
        print(f"MAIL_PORT: {app.config['MAIL_PORT']}")
        return False

    if not to:
        print("No recipient email provided")
        return False

    try:
        msg = Message(
            subject=subject,
            recipients=[to],
            body=body,
            sender=app.config['MAIL_DEFAULT_SENDER']
        )
        
        # Add error handling around the actual send
        try:
            mail.send(msg)
            print(f"Email sent successfully to {to}")
            return True
        except Exception as send_error:
            print(f"SMTP Error sending to {to}: {str(send_error)}")
            return False
            
    except Exception as e:
        print(f"Error creating email message: {str(e)}")
        return False

# Add configurations for image uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'bike_images')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def save_image(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        # Use forward slashes for URL paths
        return 'bike_images/' + filename  # Return relative path with forward slash
    return None

@app.route('/static/<path:filename>')
def serve_static(filename):
    # Normalize the path to use forward slashes
    filename = filename.replace('\\', '/')
    if filename.startswith('bike_images/'):
        # For bike images, serve from the bike_images subdirectory
        image_name = filename.replace('bike_images/', '')
        return send_from_directory(app.config['UPLOAD_FOLDER'], image_name)
    # For other static files
    return send_from_directory('static', filename)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    mobile = db.Column(db.String(15))
    owned_bikes = db.relationship('Bike', backref=db.backref('owner_user', lazy=True), foreign_keys='Bike.owner_id')
    purchases_made = db.relationship('Purchase', foreign_keys='Purchase.buyer_id', backref=db.backref('buyer_user', lazy=True))
    purchases_sold = db.relationship('Purchase', foreign_keys='Purchase.seller_id', backref=db.backref('seller_user', lazy=True))
    rentals_given = db.relationship('Rental', foreign_keys='Rental.owner_id', backref='owner', lazy=True)
    rentals_taken = db.relationship('Rental', foreign_keys='Rental.renter_id', backref='renter', lazy=True)
    # Relationship is defined in RentalRequest model

# Bike Model
class Bike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    brand = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    engine_cc = db.Column(db.Integer, nullable=False)
    km_driven = db.Column(db.Integer, nullable=False)
    mileage = db.Column(db.Float, nullable=False)
    condition = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    listing_type = db.Column(db.String(10), nullable=False)  # 'rent' or 'sale'
    price_per_day = db.Column(db.Float, nullable=True)
    sale_price = db.Column(db.Float, nullable=True)
    image_url_1 = db.Column(db.String(200))
    image_url_2 = db.Column(db.String(200))
    image_url_3 = db.Column(db.String(200))
    rentals = db.relationship('Rental', backref='bike', lazy=True)
    rental_requests = db.relationship('RentalRequest', backref='bike', lazy=True)
    bike_purchases = db.relationship('Purchase', backref=db.backref('bike_details', lazy=True))

# Rental Model
class Rental(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bike_id = db.Column(db.Integer, db.ForeignKey('bike.id'), nullable=False)
    renter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, active, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Rental Request Model
class RentalRequest(db.Model):
    __tablename__ = 'rental_request'
    id = db.Column(db.Integer, primary_key=True)
    bike_id = db.Column(db.Integer, db.ForeignKey('bike.id'), nullable=False)
    renter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    renter = db.relationship('User', foreign_keys=[renter_id], backref=db.backref('rental_requests_made', lazy=True))

# Purchase Model
class Purchase(db.Model):
    __tablename__ = 'purchase'
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True)
    
    # Core Details
    bike_id = db.Column(db.Integer, db.ForeignKey('bike.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    
    # Status and Messages
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, accepted, rejected, completed, cancelled
    message = db.Column(db.Text, nullable=True)  # Buyer's message
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert purchase object to dictionary"""
        return {
            'id': self.id,
            'bike_id': self.bike_id,
            'buyer_id': self.buyer_id,
            'seller_id': self.seller_id,
            'price': self.price,
            'status': self.status,
            'message': self.message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# Login decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please login first')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Context processor to add pending requests count to all templates
@app.context_processor
def utility_processor():
    def get_pending_requests_count():
        if not session.get('user_id'):
            return 0
        # Count pending requests for bikes owned by the current user
        return RentalRequest.query.join(Bike).filter(
            Bike.owner_id == session['user_id'],
            RentalRequest.status == 'pending'
        ).count()
    return dict(pending_requests_count=get_pending_requests_count())

def send_notification_email(subject, recipient, template, **kwargs):
    try:
        msg = Message(
            subject,
            recipients=[recipient]
        )
        msg.html = render_template(template, **kwargs)
        mail.send(msg)
        print(f"Email sent successfully to {recipient}")
    except Exception as e:
        print(f"Failed to send email: {str(e)}")

@app.route('/')
def index():
    bikes = Bike.query.filter_by(is_available=True).order_by(Bike.created_at.desc()).all()
    return render_template('index.html', bikes=bikes)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        mobile = request.form['mobile']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))

        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))

        # Create new user
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, mobile=mobile, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # First try to find user by username
        user = User.query.filter_by(username=username).first()
        
        # If user not found by username, try email (as fallback)
        if not user:
            user = User.query.filter_by(email=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            flash('Logged in successfully!', 'success')
            return redirect(url_for('my_bikes'))
        
        flash('Invalid username/email or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out')
    return redirect(url_for('index'))

# MongoDB connection
mongo_client = MongoClient(os.getenv('MONGO_URI'))
mongo_db = mongo_client['bike_rental']
bikes_collection = mongo_db['bikes']

# Bike Management Routes
@app.route('/bikes/add', methods=['GET', 'POST'])
@login_required
def add_bike():
    if request.method == 'GET':
        return render_template('add_bike.html')

    try:
        # Determine if it's an API request
        is_api = request.headers.get('Content-Type') == 'application/json'
        
        # Get data from either JSON or form
        data = request.get_json() if is_api else request.form
        files = {} if is_api else request.files

        # Validate required fields based on the Bike model
        required_fields = [
            'brand',
            'model',
            'year',
            'engine_cc',
            'km_driven',
            'mileage',
            'condition',
            'description',
            'listing_type'
        ]
        
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            if is_api:
                return jsonify({'error': error_msg}), 400
            flash(error_msg, 'danger')
            return redirect(url_for('add_bike'))

        # Validate listing type and prices
        listing_type = data.get('listing_type')
        if listing_type == 'rent':
            price_per_day = float(data.get('price_per_day', 0))
            sale_price = None
            if not price_per_day:
                error_msg = 'Price per day is required for rental listings'
                if is_api:
                    return jsonify({'error': error_msg}), 400
                flash(error_msg, 'danger')
                return redirect(url_for('add_bike'))
        elif listing_type == 'sale':
            price_per_day = None
            sale_price = float(data.get('sale_price', 0))
            if not sale_price:
                error_msg = 'Sale price is required for sale listings'
                if is_api:
                    return jsonify({'error': error_msg}), 400
                flash(error_msg, 'danger')
                return redirect(url_for('add_bike'))
        else:
            error_msg = 'Invalid listing type'
            if is_api:
                return jsonify({'error': error_msg}), 400
            flash(error_msg, 'danger')
            return redirect(url_for('add_bike'))

        # Handle image uploads
        image_urls = []
        for i in range(1, 4):
            image = files.get(f'image{i}') if not is_api else None
            if image and allowed_file(image.filename):
                filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{image.filename}")
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_urls.append(os.path.join('bike_images', filename))
            else:
                image_urls.append(None)

        # Create SQL bike record with all required fields
        new_bike = Bike(
            brand=data.get('brand'),
            model=data.get('model'),
            year=int(data.get('year')),
            engine_cc=int(data.get('engine_cc')),
            km_driven=int(data.get('km_driven')),
            mileage=float(data.get('mileage')),
            condition=data.get('condition'),
            description=data.get('description'),
            listing_type=listing_type,
            price_per_day=price_per_day,
            sale_price=sale_price,
            owner_id=session['user_id'],
            image_url_1=image_urls[0],
            image_url_2=image_urls[1],
            image_url_3=image_urls[2]
        )

        db.session.add(new_bike)
        db.session.commit()

        # Update MongoDB document structure
        mongo_bike = {
            'sql_id': new_bike.id,
            'brand': data.get('brand'),
            'model': data.get('model'),
            'year': int(data.get('year')),
            'engine_cc': int(data.get('engine_cc')),
            'km_driven': int(data.get('km_driven')),
            'mileage': float(data.get('mileage')),
            'condition': data.get('condition'),
            'listing_type': listing_type,
            'price_per_day': price_per_day,
            'sale_price': sale_price,
            'description': data.get('description'),
            'owner_id': session['user_id'],
            'images': image_urls,
            'created_at': datetime.utcnow(),
            'is_available': True,
            'metadata': {
                'views': 0,
                'favorites': 0,
                'last_viewed': None,
                'search_keywords': [
                    data.get('brand', '').lower(),
                    data.get('model', '').lower(),
                    str(data.get('year')),
                    data.get('condition', '').lower()
                ]
            }
        }

        bikes_collection.insert_one(mongo_bike)

        if is_api:
            return jsonify({
                'status': 'success',
                'message': 'Bike added successfully',
                'bike': {
                    'id': new_bike.id,
                    'brand': new_bike.brand,
                    'model': new_bike.model,
                    'year': new_bike.year,
                    'listing_type': new_bike.listing_type,
                    'price_per_day': new_bike.price_per_day,
                    'sale_price': new_bike.sale_price,
                    'images': image_urls
                }
            }), 201

        flash('Bike added successfully!', 'success')
        return redirect(url_for('my_bikes'))

    except Exception as e:
        db.session.rollback()
        # Cleanup MongoDB if SQL insert failed
        if 'new_bike' in locals() and new_bike.id:
            bikes_collection.delete_one({'sql_id': new_bike.id})
        
        error_msg = f"Error adding bike: {str(e)}"
        if is_api:
            return jsonify({'error': error_msg}), 500
        
        print(error_msg)
        flash('Error adding bike. Please try again.', 'danger')
        return redirect(url_for('add_bike'))

@app.route('/bikes/my-bikes')
@login_required
def my_bikes():
    user = User.query.get(session.get('user_id'))
    if not user:
        flash('Please login first', 'danger')
        return redirect(url_for('login'))
    
    return render_template('my_bikes.html', bikes=user.owned_bikes)

@app.route('/bikes/<int:bike_id>')
def view_bike(bike_id):
    bike = Bike.query.get_or_404(bike_id)
    current_time = datetime.utcnow()
    
    # Get current and future rentals for this bike
    active_rentals = Rental.query.filter(
        Rental.bike_id == bike_id,
        Rental.status == 'active',
        Rental.end_date > current_time
    ).order_by(Rental.start_date).all()
    
    # Get pending rental requests
    pending_requests = RentalRequest.query.filter(
        RentalRequest.bike_id == bike_id,
        RentalRequest.status == 'pending'
    ).order_by(RentalRequest.created_at).all()
    
    # Get pending purchase requests
    pending_purchases = Purchase.query.filter(
        Purchase.bike_id == bike_id,
        Purchase.status == 'pending'
    ).order_by(Purchase.created_at).all()
    
    return render_template('view_bike.html', 
                         bike=bike, 
                         active_rentals=active_rentals,
                         pending_requests=pending_requests,
                         pending_purchases=pending_purchases,
                         current_time=current_time)

@app.route('/bikes/<int:bike_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_bike(bike_id):
    bike = Bike.query.get_or_404(bike_id)
    
    # Check if the current user is the owner
    if bike.owner_id != session['user_id']:
        flash('You can only edit your own bikes.', 'danger')
        return redirect(url_for('my_bikes'))
    
    if request.method == 'POST':
        try:
            bike.name = request.form.get('name')
            bike.model = request.form.get('model')
            bike.year = request.form.get('year')
            bike.condition = request.form.get('condition')
            bike.description = request.form.get('description')
            bike.listing_type = request.form.get('listing_type')
            bike.is_available = 'is_available' in request.form
            
            # Handle prices based on listing type
            if bike.listing_type == 'rent':
                price_per_day = request.form.get('price_per_day')
                bike.price_per_day = float(price_per_day) if price_per_day else None
                bike.sale_price = None
            else:
                sale_price = request.form.get('sale_price')
                bike.sale_price = float(sale_price) if sale_price else None
                bike.price_per_day = None
            
            # Handle image uploads
            for i in range(1, 4):
                image = request.files.get(f'image{i}')
                if image and allowed_file(image.filename):
                    filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{image.filename}")
                    image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    setattr(bike, f'image_url_{i}', os.path.join('bike_images', filename))

            db.session.commit()
            flash('Bike updated successfully!', 'success')
            return redirect(url_for('my_bikes'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error updating bike: {str(e)}")
            flash('Error updating bike. Please try again.', 'danger')
            return redirect(url_for('edit_bike', bike_id=bike_id))
    
    return render_template('edit_bike.html', bike=bike)

@app.route('/bikes/<int:bike_id>/delete')
@login_required
def delete_bike(bike_id):
    bike = Bike.query.get_or_404(bike_id)
    if bike.owner_id != session['user_id']:
        flash('You can only delete your own bikes')
        return redirect(url_for('my_bikes'))
    
    try:
        db.session.delete(bike)
        db.session.commit()
        flash('Bike deleted successfully!')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting bike. Please try again.')
    
    return redirect(url_for('my_bikes'))

@app.route('/bikes/<int:bike_id>/rent', methods=['GET', 'POST'])
@login_required
def rent_bike(bike_id):
    return redirect(url_for('request_rental', bike_id=bike_id))

@app.route('/bikes/<int:bike_id>/request-rental', methods=['GET', 'POST'])
@login_required
def request_rental(bike_id):
    bike = Bike.query.get_or_404(bike_id)
    
    if request.method == 'POST':
        if bike.owner_id == session['user_id']:
            flash('You cannot request to rent your own bike')
            return redirect(url_for('view_bike', bike_id=bike_id))
            
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
        message = request.form.get('message', '')
        
        if start_date >= end_date:
            flash('End date must be after start date')
            return redirect(url_for('request_rental', bike_id=bike_id))
            
        if not bike.is_available:
            flash('This bike is not available for the selected dates')
            return redirect(url_for('view_bike', bike_id=bike_id))
            
        print(f"Creating rental request for bike {bike_id} from user {session['user_id']}")
        rental_request = RentalRequest(
            bike_id=bike_id,
            renter_id=session['user_id'],
            start_date=start_date,
            end_date=end_date,
            message=message,
            status='pending'
        )
        
        db.session.add(rental_request)
        db.session.commit()
        print(f"Rental request {rental_request.id} created successfully")
        
        if bike.owner_user.email:
            send_notification_email(
                'New Rental Request',
                bike.owner_user.email,
                'email/new_request.html',
                user=User.query.get(session['user_id']),
                bike=bike,
                request=rental_request
            )
        
        flash('Your rental request has been sent! The owner will review it and respond soon.')
        return redirect(url_for('my_rental_requests'))
        
    return render_template('request_rental.html', bike=bike, today=datetime.now().strftime('%Y-%m-%d'))

@app.route('/bikes/purchase/<int:bike_id>', methods=['GET', 'POST'])
@login_required
def request_purchase(bike_id):
    bike = Bike.query.get_or_404(bike_id)
    buyer = User.query.get(session['user_id'])
    seller = bike.owner_user

    if request.method == 'POST':
        try:
            # Validate request data
            message = request.form.get('message', '')

            # Validate bike availability and conditions
            if not bike.is_available:
                flash('Sorry, this bike is no longer available.', 'error')
                return redirect(url_for('view_bike', bike_id=bike_id))

            if bike.owner_id == session['user_id']:
                flash('You cannot purchase your own bike.', 'error')
                return redirect(url_for('view_bike', bike_id=bike_id))

            if bike.listing_type != 'sale':
                flash('This bike is not listed for sale.', 'error')
                return redirect(url_for('view_bike', bike_id=bike_id))

            # Check for existing pending request
            existing_request = Purchase.query.filter_by(
                bike_id=bike_id,
                buyer_id=session['user_id'],
                status='pending'
            ).first()

            if existing_request:
                flash('You already have a pending request for this bike.', 'warning')
                return redirect(url_for('view_bike', bike_id=bike_id))

            # Create purchase request
            purchase = Purchase(
                bike_id=bike_id,
                buyer_id=session['user_id'],
                seller_id=bike.owner_id,
                price=bike.sale_price,
                message=message,
                status='pending',
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            db.session.add(purchase)
            db.session.commit()

            # Send notifications
            try:
                send_email(
                    to=buyer.email,
                    subject=f"Purchase Request Sent - {bike.brand}",
                    body=f"""Hi {buyer.username},

Your purchase request has been sent for {bike.brand}.

Details:
- Bike: {bike.brand} ({bike.year} {bike.brand} {bike.model})
- Price: ${bike.sale_price:,.2f}

The seller will review your request and respond soon.

Best regards,
The Bike Rental Team"""
                )

                send_email(
                    to=seller.email,
                    subject=f"New Purchase Request - {bike.brand}",
                    body=f"""Hi {seller.username},

{buyer.username} wants to buy your {bike.brand}.

Buyer Details:
- Name: {buyer.username}
- Contact: {buyer.mobile if buyer.mobile else 'Not provided'}

Message: {message}

Review this request in your dashboard.

Best regards,
The Bike Rental Team"""
                )
            except Exception as e:
                print(f"Error sending emails: {str(e)}")

            flash('Purchase request sent successfully!', 'success')
            return redirect(url_for('view_bike', bike_id=bike_id))  # Changed to redirect

        except Exception as e:
            db.session.rollback()
            flash(f'Error processing purchase request: {str(e)}', 'error')
            return redirect(url_for('view_bike', bike_id=bike_id))  # Changed to redirect

    # GET request - redirect to view_bike
    return redirect(url_for('view_bike', bike_id=bike_id))

@app.route('/my-purchase-requests')
@login_required
def my_purchase_requests():
    # Get requests for bikes I'm selling
    selling_requests = Purchase.query.join(Bike).filter(
        Bike.owner_id == session['user_id'],
        Purchase.status == 'pending'
    ).all()
    
    # Get my requests to buy bikes
    buying_requests = Purchase.query.filter_by(
        buyer_id=session['user_id']
    ).all()
    
    return render_template(
        'my_purchase_requests.html',
        selling_requests=selling_requests,
        buying_requests=buying_requests
    )

@app.route('/handle-purchase-request/<int:request_id>', methods=['POST'])
@login_required
def handle_purchase_request(request_id):
    purchase = Purchase.query.get_or_404(request_id)
    bike = Bike.query.get_or_404(purchase.bike_id)
    
    # Verify the current user is the seller
    if bike.owner_id != session['user_id']:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('my_purchase_requests'))
    
    action = request.form.get('action')
    if action not in ['accept', 'reject']:
        flash('Invalid action.', 'danger')
        return redirect(url_for('my_purchase_requests'))
    
    try:
        if action == 'accept':
            # Mark the purchase as accepted
            purchase.status = 'accepted'
            purchase.seller_id = session['user_id']  # Set the seller_id
            # Mark the bike as unavailable
            bike.is_available = False
            # Reject all other pending requests for this bike
            other_requests = Purchase.query.filter(
                Purchase.bike_id == bike.id,
                Purchase.id != purchase.id,
                Purchase.status == 'pending'
            ).all()
            for req in other_requests:
                req.status = 'rejected'
                # Send rejection email
                send_email(
                    to=req.buyer_user.email,
                    subject=f"Purchase Request Rejected - {bike.brand}",
                    body=f"""Hi {req.buyer_user.username},

Unfortunately, your purchase request for {bike.brand} was not accepted as the bike has been sold to another buyer.

You can continue browsing other available bikes on our platform.

Best regards,
The Bike Rental Team"""
                )
            
            # Send acceptance email
            send_email(
                to=purchase.buyer_user.email,
                subject=f"Purchase Request Accepted - {bike.brand}",
                body=f"""Hi {purchase.buyer_user.username},

Great news! {bike.owner_user.username} has accepted your purchase request for {bike.brand}.

Seller Contact:
{bike.owner_user.mobile if bike.owner_user.mobile else 'Not provided'}

Please contact the seller to arrange the payment and pickup.

Best regards,
The Bike Rental Team"""
            )
            
            # Send notification to seller
            send_email(
                to=bike.owner_user.email,
                subject=f"You've Accepted a Purchase Request - {bike.brand}",
                body=f"""Hi {bike.owner_user.username},

You have accepted the purchase request from {purchase.buyer_user.username} for your bike {bike.brand}.

Buyer Contact:
{purchase.buyer_user.mobile if purchase.buyer_user.mobile else 'Not provided'}

Please wait for the buyer to contact you to arrange the payment and pickup.

Best regards,
The Bike Rental Team"""
            )
            
        else:  # reject
            purchase.status = 'rejected'
            purchase.seller_id = session['user_id']  # Set the seller_id
            send_email(
                to=purchase.buyer_user.email,
                subject=f"Purchase Request Rejected - {bike.brand}",
                body=f"""Hi {purchase.buyer_user.username},

Unfortunately, your purchase request for {bike.brand} was not accepted.

You can continue browsing other available bikes on our platform.

Best regards,
The Bike Rental Team"""
            )
        
        db.session.commit()
        flash(f'Purchase request {action}ed successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Error handling purchase request: {str(e)}")
        flash('Error processing your request. Please try again.', 'danger')
    
    return redirect(url_for('my_purchase_requests'))

@app.route('/rentals/my-rentals')
@login_required
def my_rentals():
    # Get rentals where user is the renter
    my_rentals = Rental.query.filter_by(
        renter_id=session['user_id']
    ).order_by(Rental.created_at.desc()).all()
    
    # Get rentals of bikes owned by the user
    owned_bikes = Bike.query.filter_by(owner_id=session['user_id']).with_entities(Bike.id).all()
    owned_bike_ids = [bike[0] for bike in owned_bikes]
    rentals_of_my_bikes = Rental.query.filter(
        Rental.bike_id.in_(owned_bike_ids)
    ).order_by(Rental.created_at.desc()).all() if owned_bike_ids else []
    
    # Debug logging
    print(f"User ID: {session['user_id']}")
    print(f"My rentals count: {len(my_rentals)}")
    print(f"Rentals of my bikes count: {len(rentals_of_my_bikes)}")
    
    return render_template('my_rentals.html', 
                         my_rentals=my_rentals,
                         rentals_of_my_bikes=rentals_of_my_bikes)

@app.route('/rentals/<int:rental_id>/status', methods=['POST'])
@login_required
def update_rental_status(rental_id):
    rental = Rental.query.get_or_404(rental_id)
    
    if rental.renter_id != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    new_status = data.get('status')
    
    if new_status not in ['pending', 'active', 'completed', 'cancelled']:
        return jsonify({'error': 'Invalid status'}), 400
    
    rental.status = new_status
    if new_status in ['completed', 'cancelled']:
        rental.bike.is_available = True
    
    db.session.commit()
    return jsonify({'message': 'Status updated successfully'}), 200

@app.route('/rentals/<int:rental_id>/complete', methods=['POST'])
@login_required
def complete_rental(rental_id):
    rental = Rental.query.get_or_404(rental_id)
    
    # Verify that the current user is the bike owner
    if rental.bike.owner_id != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Only active rentals can be marked as complete
    if rental.status != 'active':
        return jsonify({'error': 'Only active rentals can be marked as complete'}), 400
    
    try:
        rental.status = 'completed'
        rental.bike.is_available = True  # Make the bike available again
        db.session.commit()
        return jsonify({'message': 'Rental marked as complete successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/my-rental-requests')
@login_required
def my_rental_requests():
    user_id = session.get('user_id')
    
    # Get requests sent by the user
    sent_requests = RentalRequest.query.filter_by(renter_id=user_id).order_by(RentalRequest.created_at.desc()).all()
    
    # Get requests received for user's bikes
    owned_bikes = Bike.query.filter_by(owner_id=user_id).all()
    owned_bike_ids = [bike.id for bike in owned_bikes]
    
    received_requests = RentalRequest.query.filter(
        RentalRequest.bike_id.in_(owned_bike_ids)
    ).order_by(RentalRequest.created_at.desc()).all() if owned_bike_ids else []
    
    # Debug logging
    print(f"User ID: {user_id}")
    print(f"Owned Bikes: {owned_bike_ids}")
    print(f"Sent Requests: {len(sent_requests)}")
    print(f"Received Requests: {len(received_requests)}")
    
    return render_template('my_rental_requests.html', 
                         sent_requests=sent_requests,
                         received_requests=received_requests)

@app.route('/rental-requests/<int:request_id>/handle', methods=['POST'])
@login_required
def handle_rental_request(request_id):
    rental_request = RentalRequest.query.get_or_404(request_id)
    bike = rental_request.bike
    
    if bike.owner_id != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403
        
    action = request.form.get('action')
    if action not in ['approve', 'reject']:
        return jsonify({'error': 'Invalid action'}), 400
    
    if rental_request.status != 'pending':
        return jsonify({'error': 'Request has already been processed'}), 400
        
    requester = User.query.get(rental_request.renter_id)
    
    try:
        if action == 'approve':
            # Calculate rental duration and total price
            rental_days = (rental_request.end_date - rental_request.start_date).days
            total_price = rental_days * bike.price_per_day
            
            # Create a new rental with status 'active'
            rental = Rental(
                bike_id=bike.id,
                renter_id=rental_request.renter_id,
                owner_id=bike.owner_id,
                start_date=rental_request.start_date,
                end_date=rental_request.end_date,
                total_price=total_price,
                status='active'  # Explicitly set status to active
            )
            
            # Update bike and request status
            bike.is_available = False
            rental_request.status = 'approved'
            
            # Add and commit the rental
            db.session.add(rental)
            db.session.commit()
            
            if requester.email:
                send_notification_email(
                    'Your Rental Request was Approved!',
                    requester.email,
                    'email/request_approved.html',
                    user=requester,
                    bike=bike,
                    request=rental_request,
                    rental=rental
                )
            
            return jsonify({'message': 'Request approved successfully'})
            
        else:  # reject
            rental_request.status = 'rejected'
            db.session.commit()
            
            if requester.email:
                send_notification_email(
                    'Update on Your Rental Request',
                    requester.email,
                    'email/request_rejected.html',
                    user=requester,
                    bike=bike,
                    request=rental_request
                )
            
            return jsonify({'message': 'Request rejected successfully'})
            
    except Exception as e:
        db.session.rollback()
        print(f"Error handling rental request: {str(e)}")
        return jsonify({'error': str(e)}), 500

def send_purchase_confirmation_email(purchase):
    buyer_email = purchase.buyer_user.email
    seller_email = purchase.seller_user.email
    bike_name = purchase.bike_details.name
    
    # Send email to buyer
    buyer_subject = f"Purchase Confirmation - {bike_name}"
    buyer_body = f"""
    Dear {purchase.buyer_user.username},
    
    Your purchase of {bike_name} has been confirmed!
    
    Purchase Details:
    - Bike: {bike_name}
    - Price: ₹{purchase.price:.2f}
    - Purchase Date: {purchase.purchase_date.strftime('%Y-%m-%d %H:%M:%S')}
    - Seller: {purchase.seller_user.username}
    
    Thank you for using our platform!
    """
    
    # Send email to seller
    seller_subject = f"Bike Sold - {bike_name}"
    seller_body = f"""
    Dear {purchase.seller_user.username},
    
    Your bike {bike_name} has been sold!
    
    Sale Details:
    - Bike: {bike_name}
    - Price: ₹{purchase.price:.2f}
    - Sale Date: {purchase.purchase_date.strftime('%Y-%m-%d %H:%M:%S')}
    - Buyer: {purchase.buyer_user.username}
    
    Thank you for using our platform!
    """
    
    try:
        msg_buyer = Message(buyer_subject,
                          sender=app.config['MAIL_DEFAULT_SENDER'],
                          recipients=[buyer_email],
                          body=buyer_body)
        mail.send(msg_buyer)
        
        msg_seller = Message(seller_subject,
                           sender=app.config['MAIL_DEFAULT_SENDER'],
                           recipients=[seller_email],
                           body=seller_body)
        mail.send(msg_seller)
    except Exception as e:
        print(f"Error sending purchase confirmation emails: {str(e)}")

# Create database tables
def init_db():
    print("Initializing database...")
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")

@app.route('/api/bikes/search', methods=['GET'])
def search_bikes():
    try:
        # Get query parameters with defaults
        name = request.args.get('name', '').strip()
        model = request.args.get('model', '').strip()
        year = request.args.get('year', type=int)
        price_low = request.args.get('price_low', type=float, default=0)
        price_high = request.args.get('price_high', type=float)

        # Build MongoDB query
        query = {'is_available': True}
        
        # Add filters if parameters are provided
        if name:
            query['name'] = {'$regex': name, '$options': 'i'}  # case-insensitive search
        if model:
            query['model'] = {'$regex': model, '$options': 'i'}
        if year:
            query['year'] = year
            
        # Price filter for both rental and sale listings
        if price_high or price_low > 0:
            price_query = []
            if price_high:
                price_query.append({
                    'listing_type': 'rent',
                    'price_per_day': {'$gte': price_low, '$lte': price_high}
                })
                price_query.append({
                    'listing_type': 'sale',
                    'sale_price': {'$gte': price_low, '$lte': price_high}
                })
            else:
                price_query.append({
                    'listing_type': 'rent',
                    'price_per_day': {'$gte': price_low}
                })
                price_query.append({
                    'listing_type': 'sale',
                    'sale_price': {'$gte': price_low}
                })
            query['$or'] = price_query

        # Execute MongoDB query
        bikes = bikes_collection.find(query)

        # Format results
        results = []
        for bike in bikes:
            results.append({
                'id': bike['sql_id'],  # Keep the SQL ID for compatibility
                'name': bike['name'],
                'model': bike['model'],
                'year': bike['year'],
                'condition': bike['condition'],
                'listing_type': bike['listing_type'],
                'price_per_day': bike['price_per_day'],
                'sale_price': bike['sale_price'],
                'is_available': bike['is_available'],
                'owner': {
                    'id': bike['owner_id'],
                    'username': User.query.get(bike['owner_id']).username  # Get username from SQL
                },
                'images': bike['images'],
                'metadata': {
                    'views': bike['metadata']['views'],
                    'favorites': bike['metadata']['favorites']
                }
            })

        return jsonify({
            'status': 'success',
            'count': len(results),
            'bikes': results
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/rental-requests', methods=['GET'])
@login_required
def get_rental_requests():
    try:
        # Get query parameters for filtering
        status = request.args.get('status')
        bike_id = request.args.get('bike_id')
        renter_id = request.args.get('renter_id')

        # Start with base query
        query = RentalRequest.query

        # Apply filters if provided
        if status:
            query = query.filter(RentalRequest.status == status)
        if bike_id:
            query = query.filter(RentalRequest.bike_id == bike_id)
        if renter_id:
            query = query.filter(RentalRequest.renter_id == renter_id)

        # Order by created_at descending
        rental_requests = query.order_by(RentalRequest.created_at.desc()).all()

        # Format the response
        requests_data = []
        for request in rental_requests:
            requests_data.append({
                'id': request.id,
                'bike_id': request.bike_id,
                'bike': {
                    'brand': request.bike.brand,
                    'model': request.bike.model,
                    'year': request.bike.year
                },
                'renter_id': request.renter_id,
                'renter': {
                    'username': request.renter.username,
                    'email': request.renter.email
                },
                'start_date': request.start_date.strftime('%Y-%m-%d'),
                'end_date': request.end_date.strftime('%Y-%m-%d'),
                'status': request.status,
                'message': request.message,
                'created_at': request.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })

        return jsonify({
            'status': 'success',
            'count': len(requests_data),
            'rental_requests': requests_data
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/clear-rental-requests', methods=['GET'])
def clear_rental_requests():
    if not app.debug:
        return jsonify({
            'status': 'error',
            'message': 'This endpoint is only available in debug mode'
        }), 403
    
    try:
        # Get optional parameters
        status = request.args.get('status')  # Clear only requests with specific status
        older_than = request.args.get('older_than')  # Clear requests older than X days
        
        # Start with base query
        query = RentalRequest.query
        
        # Apply filters if provided
        if status:
            query = query.filter(RentalRequest.status == status)
        if older_than:
            cutoff_date = datetime.now(datetime.timezone.utc) - timedelta(days=int(older_than))
            query = query.filter(RentalRequest.created_at < cutoff_date)
            
        # Count requests before deletion
        count = query.count()
        
        # Delete the filtered requests
        query.delete()
        
        # Commit the changes
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully deleted {count} rental requests',
            'count': count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/dev/clear-db-confirm', methods=['GET'])
def clear_db_confirm():
    if not app.debug:
        return "This route is only available in debug mode", 403
            # Clear SQLite tables
    db.drop_all()
    db.create_all()
            
    # Clear MongoDB collections
    mongo_db.bikes.delete_many({})
            
    flash("Databases cleared successfully!", "success")
    
    return redirect(url_for('index'))


@app.route('/api/clear-purchases', methods=['GET'])
def clear_purchases():
    if not app.debug:
        return jsonify({
            'status': 'error',
            'message': 'This endpoint is only available in debug mode'
        }), 403
    
    try:
        # Get optional parameters
        status = request.args.get('status')  # Clear only purchases with specific status
        older_than = request.args.get('older_than')  # Clear purchases older than X days
        bike_id = request.args.get('bike_id')  # Clear purchases for specific bike
        buyer_id = request.args.get('buyer_id')  # Clear purchases by specific buyer
        seller_id = request.args.get('seller_id')  # Clear purchases by specific seller
        
        # Start with base query
        query = Purchase.query
        
        # Apply filters if provided
        if status:
            query = query.filter(Purchase.status == status)
        if older_than:
            cutoff_date = datetime.utcnow() - timedelta(days=int(older_than))
            query = query.filter(Purchase.created_at < cutoff_date)
        if bike_id:
            query = query.filter(Purchase.bike_id == int(bike_id))
        if buyer_id:
            query = query.filter(Purchase.buyer_id == int(buyer_id))
        if seller_id:
            query = query.filter(Purchase.seller_id == int(seller_id))
            
        # Count purchases before deletion
        count = query.count()
        
        # Delete the filtered purchases
        query.delete()
        
        # Commit the changes
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully deleted {count} purchases',
            'count': count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/test-mail')
def test_mail():
    if not app.debug:
        return "Test route only available in debug mode", 403
    
    success = send_email(
        to=app.config['MAIL_USERNAME'],
        subject="Test Email",
        body="This is a test email to verify the configuration."
    )
    
    return jsonify({
        'success': success,
        'mail_config': {
            'server': app.config['MAIL_SERVER'],
            'port': app.config['MAIL_PORT'],
            'username': app.config['MAIL_USERNAME'],
            'use_tls': app.config['MAIL_USE_TLS'],
            'default_sender': app.config['MAIL_DEFAULT_SENDER']
        }
    })

# Load the trained model and preprocessing objects
# model_artifacts = joblib.load('bike_price_model.joblib')
import joblib

# Use the absolute path of the model file
model_path = "C:/Users/syeds/OneDrive/Desktop/Bike-Rental-Platform-BITS (3)/Bike-Rental-Platform-BITS/bike_price_model.joblib"

# Load the model
model_artifacts = joblib.load(model_path)

rf_model = model_artifacts['model']
scaler = model_artifacts['scaler']
label_encoders = model_artifacts['label_encoders']

@app.route('/api/bikes/<int:bike_id>/analyze', methods=['GET'])
def analyze_bike(bike_id):
    try:
        # Get bike from MongoDB using SQL ID
        bike = bikes_collection.find_one({'sql_id': bike_id})
        
        if not bike:
            return jsonify({
                'success': False,
                'message': 'Bike not found'
            }), 404

        # Prepare input data
        input_data = {
            'brand': bike['brand'],
            'model': bike['model'],
            'year': int(bike['year']),
            'engine_cc': int(bike['engine_cc']),
            'km_driven': int(bike['km_driven']),
            'mileage': float(bike['mileage']),
            'condition': bike['condition']
        }

        # Transform categorical variables
        brand_encoded = label_encoders['brand'].transform([input_data['brand']])[0]
        model_encoded = label_encoders['model'].transform([input_data['model']])[0]
        condition_encoded = label_encoders['condition'].transform([input_data['condition']])[0]

        # Create feature vector
        X_input = [[
            brand_encoded,
            model_encoded,
            input_data['year'],
            input_data['engine_cc'],
            input_data['km_driven'],
            input_data['mileage'],
            condition_encoded
        ]]

        # Scale features
        X_input_scaled = scaler.transform(X_input)

        # Make prediction
        estimated_price = rf_model.predict(X_input_scaled)[0]

        return jsonify({
            'success': True,
            'estimated_price': float(estimated_price),
            'actual_price': float(bike['sale_price']),
            'parameters': input_data
        }), 200

    except Exception as e:
        print(f"Analysis error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Analysis error: {str(e)}"
        }), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Database initialized successfully!")
    app.run(debug=True, port=5002)
