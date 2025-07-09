from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from pymongo import MongoClient
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from datetime import datetime
import requests
import os
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# MongoDB Configuration
client = MongoClient( 'mongodb://localhost:27017/')
db = client["INTMAX"]
users_collection = db["users"]
engagements_collection = db["engagements"]

# Flask-Login Setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Twitter OAuth Setup
oauth = OAuth(app)
twitter = oauth.register(
    name='twitter',
    client_id=os.getenv('TWITTER_CLIENT_ID'),         # This is actually your API KEY
    client_secret=os.getenv('TWITTER_CLIENT_SECRET'), # This is your API SECRET KEY
    request_token_url='https://api.twitter.com/oauth/request_token',
    access_token_url='https://api.twitter.com/oauth/access_token',
    authorize_url='https://api.twitter.com/oauth/authenticate',
    api_base_url='https://api.twitter.com/1.1/'   #  CORRECT for OAuth 1.0a
)


class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']
        self.role = user_data['role']
        self.email = user_data.get('email', '')
        self.twitter_id = user_data.get('twitter_id', '')
        self.created_at = user_data.get('created_at', datetime.utcnow())

@login_manager.user_loader
def load_user(user_id):
    user_data = users_collection.find_one({'_id': ObjectId(user_id)})
    return User(user_data) if user_data else None

# Twitter Auth Routes
@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login/twitter')
def login_twitter():
    redirect_uri = url_for('twitter_auth', _external=True)
    return twitter.authorize_redirect(redirect_uri)

@app.route('/auth/twitter')
def twitter_auth():
    try:
        token = twitter.authorize_access_token()
        resp = twitter.get('users/me?user.fields=profile_image_url', token=token)
        profile = resp.json()
        
        # Check if user exists
        user_data = users_collection.find_one({'twitter_id': profile['data']['id']})
        
        if not user_data:
            # New registration
            return redirect(url_for('complete_registration', twitter_id=profile['data']['id'], 
                                  username=profile['data']['username']))
        
        # Existing user - login
        user = User(user_data)
        login_user(user)
        fetch_twitter_metrics(user.twitter_id)
        return redirect(url_for('dashboard'))
    
    except Exception as e:
        flash('Twitter authentication failed')
        return redirect(url_for('login'))

@app.route('/complete-registration', methods=['GET', 'POST'])
def complete_registration():
    if request.method == 'POST':
        twitter_id = request.form['twitter_id']
        username = request.form['username']
        email = request.form['email']
        
        if users_collection.find_one({'email': email}):
            flash('Email already registered')
            return redirect(url_for('complete_registration'))
        
        users_collection.insert_one({
            'username': username,
            'email': email,
            'twitter_id': twitter_id,
            'role': 'fellow',
            'created_at': datetime.utcnow()
        })
        
        user_data = users_collection.find_one({'twitter_id': twitter_id})
        user = User(user_data)
        login_user(user)
        fetch_twitter_metrics(twitter_id)
        return redirect(url_for('dashboard'))
    
    return render_template('complete_registration.html',
                         twitter_id=request.args.get('twitter_id'),
                         username=request.args.get('username'))

def fetch_twitter_metrics(twitter_id):
    try:
        user_data = users_collection.find_one({'twitter_id': twitter_id})
        if not user_data:
            return
        
        # Get Twitter metrics (simplified example)
        headers = {
            'Authorization': f'Bearer {os.getenv("TWITTER_BEARER_TOKEN")}'
        }
        tweets_url = f'https://api.twitter.com/2/users/{twitter_id}/tweets?tweet.fields=public_metrics'
        response = requests.get(tweets_url, headers=headers)
        tweets = response.json().get('data', [])
        
        # Calculate metrics
        metrics = {
            'views': sum(t['public_metrics']['impression_count'] for t in tweets),
            'likes': sum(t['public_metrics']['like_count'] for t in tweets),
            'retweets': sum(t['public_metrics']['retweet_count'] for t in tweets),
            'updated_at': datetime.utcnow()
        }
        
        # Store in database
        engagements_collection.update_one(
            {'user_id': str(user_data['_id'])},
            {'$set': metrics},
            upsert=True
        )
    except Exception as e:
        print(f"Error fetching Twitter metrics: {e}")

# Dashboard Routes
@app.route('/dashboard')
@login_required
def dashboard():
    engagements = list(engagements_collection.find({'user_id': current_user.id}))
    return render_template('Fellow_dash.html', user=current_user, engagements=engagements)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/")
def home():
    return render_template("reg.html")



if __name__ == '__main__':
    app.run(debug=True, port=5000) 



