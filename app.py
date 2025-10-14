from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg://bmspostgres_user:Hs1234%21@dpg-d3l64f2dbo4c73ekfru0-a.ap-northeast-1.aws.render.com:5432/bmspostgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    created_by = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

@app.route("/")
def index():
    docs = Document.query.order_by(Document.updated_at.desc()).all()
    return render_template("index.html", docs=docs)

# --- DB 부트스트랩: 누락된 테이블/컬럼 자동 생성 ---
with app.app_context():
    db.create_all()
    try:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS password VARCHAR(255);'))
        db.session.execute(text('ALTER TABLE document ADD COLUMN IF NOT EXISTS created_by VARCHAR(255);'))
        db.session.commit()
        print("✅ DB 스키마 확인/보정 완료")
    except Exception as e:
        db.session.rollback()
        print("⚠️ DB 스키마 보정 중 오류:", e)
# --- /DB 부트스트랩 ---

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
