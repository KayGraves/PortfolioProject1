import os
import base64
import json
import requests
from flask import Flask, redirect, request, session, url_for, render_template
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from io import BytesIO
from flask import Response
import matplotlib.pyplot as plt
import numpy as np


# Load environment variables
load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# Check if the environment variables are loaded correctly
if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    raise ValueError("Missing environment variables. Ensure CLIENT_ID, CLIENT_SECRET, and REDIRECT_URI are set.")

print("CLIENT_ID:", CLIENT_ID)
print("CLIENT_SECRET:", CLIENT_SECRET)
print("REDIRECT_URI:", REDIRECT_URI)

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Spotify API credentials
SCOPE = 'user-library-read user-top-read playlist-modify-public'

# Set up Spotify OAuth
sp_oauth = SpotifyOAuth(client_id=CLIENT_ID,
                        client_secret=CLIENT_SECRET,
                        redirect_uri=REDIRECT_URI,
                        scope=SCOPE)

def get_token():
    auth_string = CLIENT_ID + ":" + CLIENT_SECRET
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = str(base64.b64encode(auth_bytes), "utf-8")

    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Authorization": "Basic " + auth_base64,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials"
    }
    result = requests.post(url, headers=headers, data=data)
    json_result = json.loads(result.content)
    token = json_result["access_token"]
    return token

def get_auth_header(token):
    return {"Authorization": "Bearer " + token}

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login():
    # Clear session data before authentication
    session.clear()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    if not token_info:
        token_info = sp_oauth.get_access_token(code)
    session["token_info"] = token_info
    return redirect(url_for('dashboard'))



def generate_chart(df):
    plt.figure(figsize=(10, 6))

    # Scatter plot with danceability vs energy
    plt.scatter(df['danceability'], df['energy'], c=df['valence'], cmap='coolwarm', alpha=0.7)
    plt.colorbar(label='Valence')
    plt.xlabel('Danceability')
    plt.ylabel('Energy')
    plt.title('Danceability vs Energy (Valence Colormap)')
    plt.grid(True)
    plt.tight_layout()

    # Save the plot to a BytesIO object
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.close()

    # Convert the BytesIO object to base64 encoded string
    chart_img = base64.b64encode(buffer.getvalue()).decode()

    return chart_img



@app.route('/dashboard')
def dashboard():
    token_info = session.get("token_info", None)
    if not token_info:
        return redirect(url_for('login'))

    sp = spotipy.Spotify(auth=token_info['access_token'])

    # Get user's top tracks
    top_tracks = sp.current_user_top_tracks(limit=50)
    track_ids = [track['id'] for track in top_tracks['items']]

    # Fetch audio features for top tracks
    audio_features = sp.audio_features(track_ids)
    df = pd.DataFrame(audio_features)
    features = df[['danceability', 'energy', 'loudness', 'speechiness', 'acousticness', 'instrumentalness', 'liveness', 'valence', 'tempo']]

    # Generate the Data Analytics Chart
    chart_img = generate_chart(df)

    # Train nearest neighbors model
    nn = NearestNeighbors(n_neighbors=10, algorithm='ball_tree')
    nn.fit(features)

    # Get recommendations for the first track
    track_index = 0  # You can change this to get recommendations for a different track
    distances, indices = nn.kneighbors([features.iloc[track_index]])
    recommendations = df.iloc[indices[0]]

    # Display recommendations
    result = ""
    for idx, row in recommendations.iterrows():
        track = sp.track(row['id'])
        image_url = track['album']['images'][0]['url']  # Get the album image
        track_url = track['external_urls']['spotify']  # Get the track URL
        result += f"""
        <div class="song-container">
            <div class="image-container">
                <img src="{image_url}" alt="Album Art" class="album-image">
                <div class="song-info">
                    <p><strong>{track['name']}</strong> by {track['artists'][0]['name']}</p>
                    <a href="{track_url}" class="listen-link" target="_blank">Listen here</a>
                </div>
            </div>
        </div>
        """

    # Add explanation below the recommendations
    explanation = """
    <div class="explanation">
        <h3>How Recommendations are Selected:</h3>
        <p>These 10 tracks are recommended based on the audio features of your top tracks. I use the following process to find the recommendations:</p>
        <ul>
            <li>Retrieve your top 50 tracks from Spotify.</li>
            <li>Extract audio features for these tracks, including danceability, energy, loudness, speechiness, acousticness, instrumentalness, liveness, valence, and tempo.</li>
            <li>Use a nearest neighbors algorithm to find the tracks most similar to a given track in your top 50.</li>
            <li>The 10 tracks displayed are the most similar to the selected track based on these audio features.</li>
        </ul>
    </div>
    """
    # Add description of data analytics chart
    data_analytics_description = """
       <div class="data-analytics-description">
           <h3>Data Analytics Chart:</h3>
           <p>This chart visualizes the danceability and energy of your top 50 tracks. The color represents the valence of each track, where a higher valence indicates a more positive mood.</p>
       </div>
       """
    html_content = f"""
    <html>
    <head>
        <style>
            body {{
                background-color: #FFFFFF;
                color: #000000;
                font-family: Arial, sans-serif;
            }}
            .song-container {{
                margin-bottom: 20px;
                display: inline-block;
            }}
            .image-container {{
                position: relative;
                overflow: hidden;
                display: inline-block;
                margin-right: 10px; /* Adjust spacing between images */
            }}
            .album-image {{
                width: 300px; /* Double the original size */
                height: auto;
                transition: transform 0.3s ease;
            }}
            .song-info {{
                background-color: rgba(0, 0, 0, 0.8); /* Transparent black */
                color: #FFFFFF;
                padding: 5px;
                position: absolute;
                bottom: 0;
                left: 0;
                width: 100%;
                transform: translateY(100%);
                transition: transform 0.3s ease;
            }}
            .image-container:hover .album-image {{
                transform: translateY(-10px); /* Adjust as needed */
            }}
            .image-container:hover .song-info {{
                transform: translateY(0);
            }}
            .listen-link {{
                color: #6D1F7B; /* Light purple */
                text-decoration: none;
                transition: color 0.3s ease;
            }}
            .listen-link:hover {{
                color: #4B2354; /* Dark purple */
            }}
            .explanation {{
                margin-top: 40px;
                padding: 20px;
                background-color:
                                #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 8px;
            }}
        </style>
        </head>
    <body>
        <h2>Recommended Songs:</h2>
        <div style="display: flex; flex-wrap: wrap;">  <!-- Flexbox container -->
            {result}
        </div>
        {explanation}
        {data_analytics_description}
        <img src="data:image/png;base64, {chart_img}" alt="Data Analytics Chart">
    </body>
    </html>
    """

    response = Response(html_content)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response



if __name__ == '__main__':
    app.run(debug=True)
