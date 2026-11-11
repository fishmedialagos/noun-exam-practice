import os
import secrets

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Use environment secret key if provided, or generate a safe random token in development
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'noun_exam.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Exam settings
    DEFAULT_EXAM_DURATION = 30  # minutes