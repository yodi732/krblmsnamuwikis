
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql+psycopg://")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret")

db = SQLAlchemy(app)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)

with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"DB init skipped (not ready): {e}")

@app.route("/")
def index():
    docs = Document.query.all()
    return render_template("index.html", docs=docs)

@app.route("/add", methods=["POST"])
def add_doc():
    title = request.form["title"]
    content = request.form["content"]
    new_doc = Document(title=title, content=content)
    db.session.add(new_doc)
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/healthz")
def healthz():
    try:
        db.session.execute("SELECT 1")
        return "ok", 200
    except Exception as e:
        return str(e), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
