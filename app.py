from flask import Flask, render_template, session, redirect, url_for, request as flask_request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.secret_key = 'super_secret_key'
db = SQLAlchemy(app)

# =========================== MODELS ===========================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    requests = db.relationship('Request', backref='requester', lazy=True)
    transactions = db.relationship('Transaction', foreign_keys='Transaction.buyer_id', backref='buyer', lazy=True)

class Admin(User):
    __tablename__ = 'admin'
    id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)

class Charity(User):
    __tablename__ = 'charity'
    id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)

class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(100), nullable=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))
    status = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    decision_time = db.Column(db.DateTime)
    listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    strategy = None

    __mapper_args__ = {
        'polymorphic_identity': 'request',
        'polymorphic_on': type
    }

    def approve(self):
        if self.strategy:
            self.strategy.approve(self)

    def reject(self):
        if self.strategy:
            self.strategy.reject(self)

    def set_strategy(self, strategy):
        self.strategy = strategy

class SupportTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='open')  # open, in_progress, closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='support_tickets')


class PurchaseRequest(Request):
    __tablename__ = 'purchase_request'
    id = db.Column(db.Integer, db.ForeignKey('request.id'), primary_key=True)
    proposed_price = db.Column(db.Float)
    __mapper_args__ = {
        'polymorphic_identity': 'purchase_request'
    }

class BorrowRequest(Request):
    __tablename__ = 'borrow_request'
    id = db.Column(db.Integer, db.ForeignKey('request.id'), primary_key=True)
    borrow_start = db.Column(db.Date)
    borrow_end = db.Column(db.Date)
    __mapper_args__ = {
        'polymorphic_identity': 'borrow_request'
    }

class TradeRequest(Request):
    __tablename__ = 'trade_request'
    id = db.Column(db.Integer, db.ForeignKey('request.id'), primary_key=True)
    offered_item_id = db.Column(db.Integer, db.ForeignKey('listing.id'))
    __mapper_args__ = {
        'polymorphic_identity': 'trade_request'
    }

class DonationRequest(Request):
    __tablename__ = 'donation_request'
    id = db.Column(db.Integer, db.ForeignKey('request.id'), primary_key=True)
    reason = db.Column(db.String(255))
    __mapper_args__ = {
        'polymorphic_identity': 'donation_request'
    }

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    generated_by = db.Column(db.Integer, db.ForeignKey('admin.id'))
    data = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# =========================== DESIGN PATTERNS ===========================

class ListingFactory:
    @staticmethod
    def create_listing(type, data):
        return Listing(**data)

class ItemObserver:
    def update(self, listing):
        raise NotImplementedError

class ListingDecorator:
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def get_title(self):
        return self.wrapped.title

    def get_description(self):
        return self.wrapped.description

class FeaturedListing(ListingDecorator):
    def get_title(self):
        return "[FEATURED] " + super().get_title()

class UrgentListing(ListingDecorator):
    def get_title(self):
        return "[URGENT] " + super().get_title()

class VerifiedListing(ListingDecorator):
    def get_title(self):
        return "[VERIFIED] " + super().get_title()

class RequestStrategy:
    def approve(self, request):
        raise NotImplementedError

    def reject(self, request):
        raise NotImplementedError

class PurchaseStrategy(RequestStrategy):
    def approve(self, request):
        request.status = "approved"

    def reject(self, request):
        request.status = "rejected"

class BorrowStrategy(RequestStrategy):
    def approve(self, request):
        request.status = "approved"

    def reject(self, request):
        request.status = "rejected"

class TradeStrategy(RequestStrategy):
    def approve(self, request):
        request.status = "approved"

    def reject(self, request):
        request.status = "rejected"

class ReportGenerator:
    _instance = None

    @staticmethod
    def get_instance():
        if ReportGenerator._instance is None:
            ReportGenerator._instance = ReportGenerator()
        return ReportGenerator._instance

    def generate_report(self, admin_id):
        return Report(generated_by=admin_id, data="System Report", created_at=datetime.utcnow())

# =========================== ROUTES ===========================

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/login")
def login():
    return render_template('login.html')

@app.route("/createacc")
def createacc():
    return render_template('createaccount.html')

@app.route("/insertpassword")
def password():
    return render_template('insertpassword.html')

@app.route("/homepage")
def homepage():
    return render_template('homepage.html')

@app.route("/sellitem")
def sellitem():
    return render_template('sellitem.html')

@app.route("/sellitem2")
def sellitem2():
    return render_template('sellitem2.html')

@app.route("/sellitem3")
def sellitem3():
    return render_template('sellitem3.html')

@app.route("/sellitem4")
def sellitem4():
    return render_template('sellitem4.html')

@app.route("/itemsuccess")
def itemsuccess():
    return render_template('itemsuccess.html')

dummy_products = {
    1: {
        "name": "Blouse Besaty White Blue Beau",
        "original_price": 48,
        "discounted_price": None,
        "description": "Beautiful H&M blouse with blue floral pattern.",
        "image_path": "beau.png",
        "seller_name": "H&M",
        "location_image": "map1.png"
    },
    2: {
        "name": "Zara Classic White Shirt - White - M",
        "original_price": 58,
        "discounted_price": 28,
        "description": "Zara's clean-cut white shirt for modern style.",
        "image_path": "shirt.png",
        "seller_name": "H&M",
        "location_image": "map2.png"
    },
    3: {
        "name": "Zara Classic Man Black Shirt",
        "original_price": 60,
        "discounted_price": 28,
        "description": "Elegant black shirt by Zara for men.",
        "image_path": "blackshirt.png",
        "seller_name": "Vrinda",
        "location_image": "map3.png"
    },
    4: {
        "name": "Sleeveless Rock Black Marita",
        "original_price": 55,
        "discounted_price": None,
        "description": "Stylish sleeveless dress perfect for events.",
        "image_path": "marita.png",
        "seller_name": "Barbara",
        "location_image": "map4.png"
    },
    5: {
        "name": "Blouse Besaty White Blue Beau",
        "original_price": 48,
        "discounted_price": None,
        "description": "Same stylish blouse, another listing.",
        "image_path": "beau.png",
        "seller_name": "H&M",
        "location_image": "map1.png"
    },
    6: {
        "name": "Zara Classic White Shirt - White - M",
        "original_price": 58,
        "discounted_price": 28,
        "description": "Another listing for Zara classic white shirt.",
        "image_path": "shirt.png",
        "seller_name": "H&M",
        "location_image": "map2.png"
    }
    
}

@app.route('/product/<int:product_id>')
def product_page(product_id):
    product = dummy_products.get(product_id)
    if not product:
        return "Product not found", 404

    # If discounted_price is None or not less than original_price,
    # set discounted_price to original_price so your template can handle it cleanly.
    if product['discounted_price'] is None or product['discounted_price'] >= product['original_price']:
        product['discounted_price'] = product['original_price']

    return render_template('productpage.html', product=product)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
