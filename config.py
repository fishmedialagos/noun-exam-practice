import os
import secrets

basedir = os.path.abspath(os.path.dirname(__file__))

# Render provides DATABASE_URL starting with postgres:// or postgresql://
# When given postgresql://, SQLAlchemy may try to load psycopg (psycopg v3).
# Explicitly specifying postgresql+psycopg2:// ensures it uses psycopg2-binary.
db_url = os.environ.get('DATABASE_URL')
if db_url:
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql+psycopg2://', 1)
    elif db_url.startswith('postgresql://'):
        db_url = db_url.replace('postgresql://', 'postgresql+psycopg2://', 1)

class Config:
    # Use environment secret key if provided, or generate a safe random token in development
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = db_url or \
        'sqlite:///' + os.path.join(basedir, 'noun_exam.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Exam settings
    DEFAULT_EXAM_DURATION = 30  # minutes