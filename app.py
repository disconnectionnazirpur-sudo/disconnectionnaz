from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import base64
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'disconnection_secret_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///disconnection.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    agency_name = db.Column(db.String(100), nullable=True)

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contract_account = db.Column(db.String(100))
    name = db.Column(db.String(200))
    address = db.Column(db.String(300))
    total_due = db.Column(db.String(100))
    due_period = db.Column(db.String(100))
    meter_reading_unit = db.Column(db.String(100))
    current_due = db.Column(db.String(100))
    account_class = db.Column(db.String(100))
    mobile_no = db.Column(db.String(50))
    agency = db.Column(db.String(100))
    status = db.Column(db.String(50), default='Pending')
    updated_mobile = db.Column(db.String(50), nullable=True)
    status_image = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def init_db():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=generate_password_hash('admin123'), role='admin')
        db.session.add(admin)
        db.session.commit()

@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            session['username'] = user.username
            session['agency_name'] = user.agency_name
            return redirect(url_for('admin_dashboard') if user.role == 'admin' else url_for('agency_dashboard'))
        else:
            error = 'Invalid username or password.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    agencies = [a[0] for a in db.session.query(Account.agency).distinct().all() if a[0]]
    classes = [c[0] for c in db.session.query(Account.account_class).distinct().all() if c[0]]
    return render_template('admin.html', agencies=agencies, classes=classes)

@app.route('/admin/data')
def admin_data():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    query = Account.query
    agency_filter = request.args.get('agency', '')
    status_filter = request.args.get('status', '')
    period_filter = request.args.get('period', '')
    class_filter = request.args.get('account_class', '')
    search_kw = request.args.get('search', '').strip()
    if agency_filter:
        query = query.filter_by(agency=agency_filter)
    if status_filter:
        query = query.filter_by(status=status_filter)
    if period_filter:
        query = query.filter_by(due_period=period_filter)
    if class_filter:
        query = query.filter_by(account_class=class_filter)
    accounts = query.all()
    if search_kw:
        kw = search_kw.lower()
        accounts = [a for a in accounts if kw in (a.contract_account or '').lower() or kw in (a.name or '').lower() or kw in (a.meter_reading_unit or '').lower() or kw in (a.mobile_no or '').lower()]
    return jsonify({
        'accounts': [{
            'id': a.id, 'contract_account': a.contract_account, 'name': a.name,
            'address': a.address, 'total_due': a.total_due, 'due_period': a.due_period,
            'meter_reading_unit': a.meter_reading_unit, 'current_due': a.current_due,
            'account_class': a.account_class, 'mobile_no': a.mobile_no,
            'updated_mobile': a.updated_mobile or '',
            'agency': a.agency, 'status': a.status,
            'has_image': bool(a.status_image),
            'status_image': a.status_image or '',
            'updated_at': a.updated_at.strftime('%Y-%m-%d %H:%M:%S') if a.updated_at else ''
        } for a in accounts],
        'summary': {
            'total': Account.query.count(),
            'disconnected': Account.query.filter_by(status='Disconnected').count(),
            'paid': Account.query.filter_by(status='Paid').count(),
            'dispute': Account.query.filter_by(status='Dispute').count()
        }
    })

@app.route('/admin/import', methods=['POST'])
def import_excel():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    file = request.files.get('excel_file')
    if not file:
        return redirect(url_for('admin_dashboard'))
    df = pd.read_excel(file)
    df.columns = [str(c).strip() for c in df.columns]
    Account.query.delete()
    db.session.flush()
    agencies_added = set()
    for _, row in df.iterrows():
        agency_name = str(row.get('Agency', '')).strip()
        db.session.add(Account(
            contract_account=str(row.get('CONTRACT ACCOUNT', '')),
            name=str(row.get('Name', '')),
            address=str(row.get('Address', '')),
            total_due=str(row.get('Total Due', '')),
            due_period=str(row.get('Due Period', '')),
            meter_reading_unit=str(row.get('Meter reading unit', '')),
            current_due=str(row.get('Current Due', '')),
            account_class=str(row.get('class', '')),
            mobile_no=str(row.get('mobile no', '')),
            agency=agency_name,
            status=str(row.get('Status', 'Pending'))
        ))
        if agency_name and agency_name not in agencies_added:
            agencies_added.add(agency_name)
    db.session.flush()
    for agency_name in agencies_added:
        username = agency_name.lower().replace(' ', '_')
        if not User.query.filter_by(username=username).first():
            db.session.add(User(
                username=username,
                password=generate_password_hash('agency123'),
                role='agency',
                agency_name=agency_name
            ))
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update_status', methods=['POST'])
def admin_update_status():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    new_status = data.get('status')
    if new_status not in ['Disconnected', 'Paid', 'Dispute', 'Pending']:
        return jsonify({'error': 'Invalid status'}), 400
    account = Account.query.get(data.get('id'))
    if not account:
        return jsonify({'error': 'Not found'}), 404
    account.status = new_status
    account.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/reports')
def admin_reports():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('reports.html')

@app.route('/admin/reports/data')
def admin_reports_data():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    accounts = Account.query.all()
    # Send all raw accounts so frontend can filter and regroup dynamically
    raw = [{
        'contract_account': a.contract_account,
        'name': a.name,
        'agency': a.agency or 'Unknown',
        'account_class': a.account_class or 'Unknown',
        'total_due': a.total_due,
        'status': a.status or 'Pending'
    } for a in accounts]
    return jsonify({'accounts': raw})

@app.route('/agency')
def agency_dashboard():
    if session.get('role') != 'agency':
        return redirect(url_for('login'))
    return render_template('agency.html', agency_name=session.get('agency_name'))

@app.route('/agency/data')
def agency_data():
    if session.get('role') != 'agency':
        return jsonify({'error': 'Unauthorized'}), 401
    accounts = Account.query.filter_by(agency=session.get('agency_name')).all()
    return jsonify({'accounts': [{
        'id': a.id, 'contract_account': a.contract_account, 'name': a.name,
        'address': a.address, 'total_due': a.total_due, 'due_period': a.due_period,
        'current_due': a.current_due, 'mobile_no': a.mobile_no,
        'meter_reading_unit': a.meter_reading_unit,
        'account_class': a.account_class,
        'updated_mobile': a.updated_mobile or '',
        'status_image': a.status_image or '',
        'has_image': bool(a.status_image),
        'status': a.status,
        'updated_at': a.updated_at.strftime('%Y-%m-%d %H:%M:%S') if a.updated_at else ''
    } for a in accounts]})

@app.route('/agency/update_status', methods=['POST'])
def update_status():
    if session.get('role') != 'agency':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    new_status = data.get('status')
    if new_status not in ['Disconnected', 'Paid', 'Dispute']:
        return jsonify({'error': 'Invalid status'}), 400
    account = Account.query.get(data.get('id'))
    if not account or account.agency != session.get('agency_name'):
        return jsonify({'error': 'Not allowed'}), 403
    account.status = new_status
    account.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})

@app.route('/agency/update_mobile', methods=['POST'])
def update_mobile():
    if session.get('role') != 'agency':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    account = Account.query.get(data.get('id'))
    if not account or account.agency != session.get('agency_name'):
        return jsonify({'error': 'Not allowed'}), 403
    account.updated_mobile = data.get('mobile', '').strip()
    account.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})

@app.route('/agency/upload_image', methods=['POST'])
def upload_image():
    if session.get('role') != 'agency':
        return jsonify({'error': 'Unauthorized'}), 401
    account_id = request.form.get('id')
    account = Account.query.get(account_id)
    if not account or account.agency != session.get('agency_name'):
        return jsonify({'error': 'Not allowed'}), 403
    file = request.files.get('image')
    if not file or file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    allowed = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed:
        return jsonify({'error': 'Invalid file type. Use PNG, JPG, GIF or WEBP'}), 400
    image_data = file.read()
    b64 = base64.b64encode(image_data).decode('utf-8')
    mime = 'image/' + ('jpeg' if ext == 'jpg' else ext)
    account.status_image = 'data:' + mime + ';base64,' + b64
    account.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True, 'image': account.status_image})

@app.route('/agency/delete_image', methods=['POST'])
def delete_image():
    if session.get('role') != 'agency':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    account = Account.query.get(data.get('id'))
    if not account or account.agency != session.get('agency_name'):
        return jsonify({'error': 'Not allowed'}), 403
    account.status_image = None
    db.session.commit()
    return jsonify({'success': True})

# --- User Management Routes ---

@app.route('/admin/users')
def manage_users():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    users = User.query.all()
    return render_template('users.html', users=users)

@app.route('/admin/users/add', methods=['POST'])
def add_user():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'agency')
    agency_name = data.get('agency_name', '').strip()
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 400
    if role not in ['admin', 'agency']:
        return jsonify({'error': 'Invalid role'}), 400
    user = User(
        username=username,
        password=generate_password_hash(password),
        role=role,
        agency_name=agency_name if role == 'agency' else None
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({'success': True, 'id': user.id})

@app.route('/admin/users/edit/<int:user_id>', methods=['POST'])
def edit_user(user_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    new_username = data.get('username', '').strip()
    new_password = data.get('password', '').strip()
    new_role = data.get('role', user.role)
    new_agency = data.get('agency_name', '').strip()
    if new_username and new_username != user.username:
        if User.query.filter_by(username=new_username).first():
            return jsonify({'error': 'Username already exists'}), 400
        user.username = new_username
    if new_password:
        user.password = generate_password_hash(new_password)
    if new_role in ['admin', 'agency']:
        user.role = new_role
    user.agency_name = new_agency if new_role == 'agency' else None
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    if user_id == session.get('user_id'):
        return jsonify({'error': 'Cannot delete your own account'}), 400
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)
