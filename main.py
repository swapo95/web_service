import os
import re
from datetime import date
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, Date, select, or_
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import IntegrityError

# -----------------------------
# DB
# -----------------------------
DB_URL = os.getenv("DB_URL", "sqlite:///./app.db")

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    birth_date = Column(Date, nullable=False)

    email = Column(String(255), nullable=False, unique=True, index=True)
    phone = Column(String(50), nullable=False)
    username = Column(String(150), nullable=False, unique=True, index=True)

Base.metadata.create_all(bind=engine)

# -----------------------------
# Schemi API
# -----------------------------
class UserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    birth_date: date
    email: EmailStr
    phone: str = Field(min_length=3, max_length=50)

class UserOut(BaseModel):
    first_name: str
    last_name: str
    birth_date: date
    email: EmailStr
    phone: str
    username: str

    class Config:
        from_attributes = True

# -----------------------------
# Username generation
# -----------------------------
def slugify(s: str) -> str:
    s = s.strip().lower()
    # tiene solo lettere e numeri; rimuove spazi e simboli
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s

def generate_unique_username(db, first_name: str, last_name: str) -> str:
    base = slugify((first_name[:1] + last_name))
    if not base:
        base = "user"

    candidate = base
    suffix = 2

    while True:
        exists = db.execute(select(User).where(User.username == candidate)).scalar_one_or_none()
        if not exists:
            return candidate
        candidate = f"{base}{suffix}"
        suffix += 1

# -----------------------------
# App
# -----------------------------
app = FastAPI(title="Users Service", version="1.0.0")

@app.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate):
    db = SessionLocal()
    try:
        username = generate_unique_username(db, payload.first_name, payload.last_name)
        user = User(
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            birth_date=payload.birth_date,
            email=str(payload.email).lower().strip(),
            phone=payload.phone.strip(),
            username=username,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        # tipicamente email duplicata (username lo gestiamo con i suffix)
        raise HTTPException(status_code=409, detail="Email già esistente")
    finally:
        db.close()

@app.get("/users", response_model=List[UserOut])
def search_users(
    q: Optional[str] = Query(default=None, description="Ricerca full-text su nome/cognome/email/telefono/username"),
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    username: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    db = SessionLocal()
    try:
        stmt = select(User)

        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    User.first_name.ilike(like),
                    User.last_name.ilike(like),
                    User.email.ilike(like),
                    User.phone.ilike(like),
                    User.username.ilike(like),
                )
            )

        if first_name:
            stmt = stmt.where(User.first_name.ilike(f"%{first_name.strip()}%"))
        if last_name:
            stmt = stmt.where(User.last_name.ilike(f"%{last_name.strip()}%"))
        if email:
            stmt = stmt.where(User.email.ilike(f"%{email.strip().lower()}%"))
        if phone:
            stmt = stmt.where(User.phone.ilike(f"%{phone.strip()}%"))
        if username:
            stmt = stmt.where(User.username.ilike(f"%{username.strip().lower()}%"))

        stmt = stmt.offset(offset).limit(limit)
        users = db.execute(stmt).scalars().all()
        return users
    finally:
        db.close()

@app.delete("/users/{username}", status_code=204)
def delete_user(username: str):
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Utente non trovato")
        db.delete(user)
        db.commit()
        return
    finally:
        db.close()

@app.get("/users/{username}", response_model=UserOut)
def get_user(username: str):
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Utente non trovato")
        return user
    finally:
        db.close()
