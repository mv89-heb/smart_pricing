"""Shared Flask extension instances (kept separate from models/app to avoid circular imports)."""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
