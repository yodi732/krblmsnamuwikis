from datetime import datetime
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, Boolean, ForeignKey, DateTime

from app import db

class User(db.Model):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class Document(db.Model):
    __tablename__ = "document"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("document.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    __mapper_args__ = {"order_by": created_at.asc()}
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True, index=True)
    # app.py — Document 모델 정의 부분 수정
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True, index=True)

    # ↓ children 관계의 기본 정렬을 'created_at 오름차순'으로 고정
    parent = db.relationship(
        "Document",
        remote_side=[id],
        backref=db.backref("children", lazy="dynamic", order_by="Document.created_at.asc()")
    )
