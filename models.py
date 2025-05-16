from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from quart_auth import AuthUser

db = SQLAlchemy()

class User(AuthUser, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tiktok_username = db.Column(db.String(80), unique=True, nullable=False)
    tiktok_id = db.Column(db.String(80), unique=True)
    display_name = db.Column(db.String(80))
    avatar_url = db.Column(db.String(200))
    email = db.Column(db.String(120), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relation avec les vidéos
    videos = db.relationship('Video', backref='user', lazy=True)
    
    # Relation avec les parties
    games_created = db.relationship('Game', backref='creator', lazy=True, foreign_keys='Game.creator_id')
    games_played = db.relationship('GamePlayer', backref='user', lazy=True)
    
    def get_id(self):
        return str(self.id)
    
    @property
    def is_active(self):
        return True
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_anonymous(self):
        return False

    def __repr__(self):
        return f'<User {self.tiktok_username}>'

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='waiting')  # waiting, playing, finished
    max_rounds = db.Column(db.Integer, default=5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    
    # Relations
    players = db.relationship('GamePlayer', backref='game', lazy=True)
    rounds = db.relationship('Round', backref='game', lazy=True)
    
    def __repr__(self):
        return f'<Game {self.code}>'

class GamePlayer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    score = db.Column(db.Integer, default=0)
    joker_used = db.Column(db.Boolean, default=False)
    
    # Relations
    user = db.relationship('User', backref='games_played')
    
    def __repr__(self):
        return f'<GamePlayer {self.user_id} in game {self.game_id}>'

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tiktok_id = db.Column(db.String(50), unique=True)
    url = db.Column(db.String(255))
    download_url = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    rounds = db.relationship('Round', backref='video', lazy=True)
    
    def __repr__(self):
        return f'<Video {self.tiktok_id}>'

class Round(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'))
    round_number = db.Column(db.Integer)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Utilisateur dont c'est la vidéo
    status = db.Column(db.String(20), default='voting')  # voting, finished
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)
    
    # Relations
    votes = db.relationship('Vote', backref='round', lazy=True)
    user = db.relationship('User')
    
    def __repr__(self):
        return f'<Round {self.round_number} of game {self.game_id}>'

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    round_id = db.Column(db.Integer, db.ForeignKey('round.id'))
    voter_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    voted_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    voter = db.relationship('User', foreign_keys=[voter_id])
    voted_user = db.relationship('User', foreign_keys=[voted_user_id])
    
    def __repr__(self):
        return f'<Vote by {self.voter_id} for {self.voted_user_id} in round {self.round_id}>' 