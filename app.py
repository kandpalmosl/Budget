from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import bcrypt
import os

DEFAULT_EXPENSE_CATEGORIES = ["Food", "Transport", "Utilities", "Shopping"]
DEFAULT_INCOME_CATEGORIES = ["Salary", "Freelance", "Investments"]
DEFAULT_ACCOUNTS = ["Cash", "Savings Account", "Card"]

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# ✅ Database setup
db_path = os.path.join('/tmp', 'budget.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
db = SQLAlchemy(app)

@app.before_first_request
def create_tables():
    db.create_all()


# ✅ User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.LargeBinary, nullable=False)

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    initial_balance = db.Column(db.Float, nullable=False)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    category_type = db.Column(db.String(10), nullable=False)  # 'income' or 'expense'

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    description = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.now)
    transaction_type = db.Column(db.String(10), nullable=False)  # 'income' or 'expense'

# ✅ Routes
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))

        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
            
        # Add default income categories
        for name in DEFAULT_INCOME_CATEGORIES:
            db.session.add(Category(name=name, category_type='income', user_id=new_user.id))

        # Add default expense categories
        for name in DEFAULT_EXPENSE_CATEGORIES:
            db.session.add(Category(name=name, category_type='expense', user_id=new_user.id))

        # Add default accounts
        for name in DEFAULT_ACCOUNTS:
            db.session.add(Account(name=name, initial_balance=0, user_id=new_user.id))

        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')

        user = User.query.filter_by(username=username).first()
        if user and bcrypt.checkpw(password, user.password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))

    user_id = session['user_id']
    username = session['username']
    accounts = Account.query.filter_by(user_id=user_id).all()
    
    return render_template('dashboard.html', username=username, accounts=accounts)


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out', 'info')
    return redirect(url_for('login'))

@app.route('/transactions', methods=['GET', 'POST'])
def transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    if request.method == 'POST':
        amount = float(request.form['amount'])
        category_id = int(request.form['category'])
        account_id = int(request.form['account'])
        description = request.form.get('description', '')
        timestamp_str = request.form['timestamp']
        transaction_type = request.form['transaction_type']
        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M')

        new_txn = Transaction(
            user_id=user_id,
            amount=amount,
            category_id=category_id,
            account_id=account_id,
            description=description,
            timestamp=timestamp,
            transaction_type=transaction_type
        )
        db.session.add(new_txn)
        db.session.commit()
        flash('Transaction added!', 'success')
        return redirect(url_for('transactions'))

    transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.timestamp.desc()).all()
    accounts = Account.query.filter_by(user_id=user_id).all()
    categories = Category.query.filter_by(user_id=user_id).all()

    return render_template('transactions.html', transactions=transactions, accounts=accounts, categories=categories)

@app.route('/manage_accounts', methods=['POST'])
def manage_accounts():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    name = request.form['name']
    balance = float(request.form['initial_balance'])
    account = Account(user_id=session['user_id'], name=name, initial_balance=balance)
    db.session.add(account)
    db.session.commit()
    flash('Account added!', 'success')
    return redirect(url_for('transactions'))

@app.route('/manage_categories', methods=['POST'])
def manage_categories():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    name = request.form['name']
    category_type = request.form['category_type']  # income or expense
    category = Category(user_id=session['user_id'], name=name, category_type=category_type)
    db.session.add(category)
    db.session.commit()
    flash('Category added!', 'success')
    return redirect(url_for('transactions'))

@app.context_processor
def inject_balance():
    def get_account_balance(account_id):
        account = Account.query.get(account_id)
        transactions = Transaction.query.filter_by(account_id=account_id).all()
        balance = account.initial_balance
        for txn in transactions:
            if txn.transaction_type == 'income':
                balance += txn.amount
            elif txn.transaction_type == 'expense':
                balance -= txn.amount
        return balance
    return dict(get_account_balance=get_account_balance)

# ✅ Run server and create DB
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
