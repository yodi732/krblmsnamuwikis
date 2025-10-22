from flask import Blueprint, render_template

legal_bp = Blueprint("legal", __name__)

@legal_bp.get("/legal/terms")
def terms():
    return render_template("legal/terms.html")

@legal_bp.get("/legal/privacy")
def privacy():
    return render_template("legal/privacy.html")
