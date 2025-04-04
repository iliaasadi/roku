import os
from pathlib import Path

# Get the directory where this file is located
BASE_DIR = Path(__file__).resolve().parent

# Database configuration
SQLALCHEMY_DATABASE_URI = f'sqlite:///{BASE_DIR}/menu.db'
SQLALCHEMY_TRACK_MODIFICATIONS = False
SECRET_KEY = os.urandom(24) 