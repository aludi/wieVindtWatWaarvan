from datetime import datetime
from app import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash= db.Column(db.String(128))
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    
    def __repr__(self):
        return '<User {}>'.format(self.username)
        
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book = db.Column(db.String(200))
    rating = db.Column(db.String(5))
    color = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __repr__(self):
        return '<Post {}>'.format(self.book)
        

class Words(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    corpus_words_raw = db.Column(db.String(200))
    topic_words_raw = db.Column(db.String(200))
    max_texts = db.Column(db.Integer)
        
    def __repr__(self):
        return '<Query on topic {} in corpus {}>'.format(self.topic_words_raw, self.corpus_words_raw)

        
class Sents(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    corpus = db.Column(db.String(200))
    topic = db.Column(db.String(200))
    parties = db.Column(db.String(200))
    location = db.Column(db.String(200))
    date = db.Column(db.String(200))
    title= db.Column(db.String(200))
    entity = db.Column(db.String(200))
    polarity = db.Column(db.Integer)
    objectivity = db.Column(db.Integer)
    direct_words = db.Column(db.String(200))

        
    def __repr__(self):
        return '<Sentiments on {} in {}>'.format(self.entity, self.title)


    
    
    
