import os
from datetime import timedelta

class Config:
    # Configuration de base
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-who-liked-app'
    
    # Configuration de la base de données
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///wholiked.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuration de Flask-Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    
    # Configuration du téléchargement de fichiers
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    
    # Configuration TikTok
    TIKTOK_TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_data')
    RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY') or '694e7658bamsh43695bc5f6f53f8p1d29c6jsn5365263eaadb'
    
    # Création des dossiers nécessaires
    @staticmethod
    def init_app(app):
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.TIKTOK_TEMP_DIR, exist_ok=True) 