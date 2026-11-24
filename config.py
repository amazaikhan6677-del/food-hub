"""
config.py
Central configuration for the FoodHub Flask application.
"""

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Secret key used for sessions / CSRF. In production, set this via an
    # environment variable instead of hard-coding it.
    SECRET_KEY = os.environ.get("FOODHUB_SECRET_KEY", "foodhub-dev-secret-key-change-me")

    # Vercel serverless instances have a read-only project filesystem.
    # /tmp is writable but ephemeral: data may disappear between instances.
    if os.environ.get("VERCEL"):
        RUNTIME_DIR = "/tmp"
    else:
        RUNTIME_DIR = BASE_DIR

    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(RUNTIME_DIR, "foodhub.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload folder for admin-uploaded food images.
    UPLOAD_FOLDER = os.path.join(RUNTIME_DIR, "uploads")
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    # Business rules
    DELIVERY_FEE = 150.0               # flat delivery fee (Rs.)
    FREE_DELIVERY_THRESHOLD = 2000.0   # orders above this get free delivery

    # Default admin credentials (created automatically on first run).
    DEFAULT_ADMIN_USERNAME = os.environ.get("FOODHUB_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD = os.environ.get("FOODHUB_ADMIN_PASSWORD", "admin123")
