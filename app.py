from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from datetime import datetime
from dotenv import load_dotenv
import os
import requests

# Load environment variables
load_dotenv()

# Flask App Initialization
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# MongoDB Setup
client = MongoClient('mongodb://localhost:27017/')
db = client["INTMAX"]
users_collection = db["users"]
engagements_collection = db["engagements"]

# Flask-Login Setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'



from authlib.integrations.flask_client import OAuth

oauth = OAuth(app)

twitter = oauth.register(
    name='twitter',
    client_id='TWITTER_API_KEY',
    client_secret='TWITTER_API_SECRET',
    request_token_url='https://api.twitter.com/oauth/request_token',
    request_token_params=None,
    access_token_url='https://api.twitter.com/oauth/access_token',
    access_token_params=None,
    authorize_url='https://api.twitter.com/oauth/authenticate',
    api_base_url='https://api.twitter.com/1.1/',
    client_kwargs=None,
)

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data.get('username')
        self.role = user_data.get('role')
        self.email = user_data.get('email', '')
        self.twitter_id = user_data.get('twitter_id', '')
        self.created_at = user_data.get('created_at', datetime.utcnow())

@login_manager.user_loader
def load_user(user_id):
    user_data = users_collection.find_one({'_id': ObjectId(user_id)})
    return User(user_data) if user_data else None

# ---------------- Routes ---------------- #

@app.route('/')
def home():
    return render_template('reg.html')

@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login/twitter')
def login_twitter():
    try:
        redirect_uri = url_for('twitter_auth', _external=True)
        return twitter.authorize_redirect(redirect_uri)
    except Exception as e:
        flash(f"OAuth redirect failed: {e}")
        return redirect(url_for('login'))

@app.route('/auth/twitter')
def twitter_auth():
    try:
        token = twitter.authorize_access_token()
        resp = twitter.get('account/verify_credentials.json')  # v1.1 endpoint
        profile = resp.json()

        twitter_id = str(profile.get('id'))
        username = profile.get('screen_name')

        user_data = users_collection.find_one({'twitter_id': twitter_id})

        if not user_data:
            # Redirect to registration
            return redirect(url_for('complete_registration', twitter_id=twitter_id, username=username))

        # Login existing user
        user = User(user_data)
        login_user(user)
        fetch_twitter_metrics(twitter_id)
        return redirect(url_for('dashboard'))

    except Exception as e:
        flash(f"Twitter authentication failed: {e}")
        return redirect(url_for('login'))

@app.route('/complete-registration', methods=['GET', 'POST'])
def complete_registration():
    if request.method == 'POST':
        twitter_id = request.form['twitter_id']
        username = request.form['username']
        email = request.form['email']

        if users_collection.find_one({'email': email}):
            flash('Email already registered.')
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

# ---------------- Utilities ---------------- #

def fetch_twitter_metrics(twitter_id):
    try:
        user_data = users_collection.find_one({'twitter_id': twitter_id})
        if not user_data:
            return

        headers = {
            'Authorization': f'Bearer {os.getenv("TWITTER_BEARER_TOKEN")}'
        }
        tweets_url = f'https://api.twitter.com/2/users/{twitter_id}/tweets?tweet.fields=public_metrics'
        response = requests.get(tweets_url, headers=headers)
        tweets = response.json().get('data', [])

        metrics = {
            'views': sum(t.get('public_metrics', {}).get('impression_count', 0) for t in tweets),
            'likes': sum(t.get('public_metrics', {}).get('like_count', 0) for t in tweets),
            'retweets': sum(t.get('public_metrics', {}).get('retweet_count', 0) for t in tweets),
            'updated_at': datetime.utcnow()
        }

        engagements_collection.update_one(
            {'user_id': str(user_data['_id'])},
            {'$set': metrics},
            upsert=True
        )

    except Exception as e:
        print(f"Error fetching Twitter metrics: {e}")

# Optional: fallback route
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

# ---------------- Main ---------------- #

if __name__ == '__main__':
    app.run(debug=True, port=5000)
