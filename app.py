from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
import os

app = Flask(__name__)
app.secret_key = 'secret'

# DB 설정
db_url = os.getenv('DATABASE_URL')
if not db_url:
    db_url = 'sqlite:///app.db'
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    created_by = db.Column(db.String(100))
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    try:
        db.create_all()
        # password 컬럼이 없으면 전체 재생성
        cols = [c.name for c in User.__table__.columns]
        if 'password' not in cols:
            db.drop_all()
            db.create_all()
        if not User.query.filter_by(email='admin@school.kr').first():
            admin = User(email='admin@school.kr', password='admin')
            db.session.add(admin)
            db.session.commit()
    except Exception as e:
        print('DB Error:', e)

@app.route('/')
def index():
    docs = Document.query.order_by(Document.updated_at.desc()).all()
    return render_template('index.html', docs=docs)

@app.route('/create', methods=['GET','POST'])
@login_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        doc = Document(title=title, content=content, created_by=current_user.email)
        db.session.add(doc)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('create.html')

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    if not request.args.get('confirm'):
        return render_template('confirm_delete.html', id=id)
    doc = Document.query.get_or_404(id)
    db.session.delete(doc)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for('index'))
        flash('로그인 실패')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    return render_template('confirm_logout.html')

@app.route('/logout/confirm')
@login_required
def logout_confirm():
    logout_user()
    return redirect(url_for('index'))

@app.route('/withdraw')
@login_required
def withdraw():
    return render_template('confirm_withdraw.html')

@app.route('/withdraw/confirm')
@login_required
def withdraw_confirm():
    user = current_user
    logout_user()
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
