from flask import Flask, request, jsonify
from pymongo import MongoClient
from bson import Binary
from dotenv import load_dotenv
import bcrypt, ssl, requests, os, time, threading 

env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../.env'))
load_dotenv(dotenv_path=env_path)
ODDS_API_KEY = os.getenv('ODDS_API_KEY')
MONGODB_URI = os.getenv('MONGODB_URI')



app = Flask(__name__)

# Connect to MongoDB
client = MongoClient(
    MONGODB_URI,
    tls=True,
    tlsAllowInvalidCertificates=True
    )
db = client['betting_app']  # Create a database named 'betting_app'
users_collection = db['users']  # Create a collection named 'users'

@app.route('/')
def home():
    return "Betting App API is running!"

# Register a new user
@app.route('/register', methods=['POST'])
def register_user():
    data = request.json
    if 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Invalid data'}), 400

    # Hash the password and store it as bytes
    hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
    
    users_collection.insert_one({
        'username': data['username'],
        'password': Binary(hashed_password),  # Store hashed password as bytes
        'preferences': {}
    })
    
    return jsonify({'message': 'User registered successfully'}), 201


# Login a user
@app.route('/login', methods=['POST'])
def login_user():
    data = request.json
    if 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Invalid data'}), 400

    user = users_collection.find_one({'username': data['username']})
    if not user or not bcrypt.checkpw(data['password'].encode('utf-8'), user['password']):
        return jsonify({'error': 'Invalid username or password'}), 401

    return jsonify({'message': 'Login successful'}), 200


# Update user preferences
@app.route('/update-preferences', methods=['PUT'])
def update_preferences():
    data = request.json
    if 'username' not in data or 'preferences' not in data:
        return jsonify({'error': 'Invalid data'}), 400

    username = data['username']
    preferences = data['preferences']  # This should be a dictionary containing preference data

    # Update the user's preferences in MongoDB
    result = users_collection.update_one(
        {'username': username},
        {'$set': {'preferences': preferences}}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({'message': 'Preferences updated successfully'}), 200


# Fetch user preferences
@app.route('/get-preferences/<username>', methods=['GET'])
def get_preferences(username):
    user = users_collection.find_one({'username': username}, {'_id': 0, 'preferences': 1})
    
    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify(user['preferences']), 200

##*****#*#*#*#*#*#*##*#**##*#*#*#*#*#*##*#*#*#*#*#*#**#*#*#*### THIS WORKS BUT DOESN'T SAVE TO THE DATABASE
# # Fetch all sports odds
# @app.route('/get-odds', methods=['GET'])
# def get_all_sports_odds():
#     # Fetch the list of available sports
#     sports_url = 'https://api.the-odds-api.com/v4/sports'
#     sports_params = {
#         'apiKey': ODDS_API_KEY,
#     }

#     try:
#         sports_response = requests.get(sports_url, params=sports_params)
#         sports_response.raise_for_status()
#     except requests.exceptions.RequestException as e:
#         return jsonify({'error': str(e)}), 500

#     sports_list = sports_response.json()  # List of sports available

#     all_odds_data = {}

#     # Loop through each sport to get odds data
#     for sport in sports_list:
#         sport_key = sport['key']
#         odds_url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds'
#         odds_params = {
#             'apiKey': ODDS_API_KEY,
#             'regions': 'us',  # You can modify regions as needed
#             'markets': 'h2h,spreads',  # Add more markets as needed
#         }

#         try:
#             odds_response = requests.get(odds_url, params=odds_params)
#             odds_response.raise_for_status()
#         except requests.exceptions.RequestException as e:
#             continue  # Skip sports that fail to fetch odds

#         odds_data = odds_response.json()
#         all_odds_data[sport_key] = odds_data

#     return jsonify(all_odds_data), 200


# Fetch all sports odds and save to MongoDB
@app.route('/get-odds', methods=['GET'])
def get_all_sports_odds():
    # Fetch the list of available sports
    sports_url = 'https://api.the-odds-api.com/v4/sports'
    sports_params = {
        'apiKey': ODDS_API_KEY,
    }

    try:
        sports_response = requests.get(sports_url, params=sports_params)
        sports_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500

    sports_list = sports_response.json()  # List of sports available

    all_odds_data = {}

    # Loop through each sport to get odds data
    for sport in sports_list:
        sport_key = sport['key']
        odds_url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds'
        odds_params = {
            'apiKey': ODDS_API_KEY,
            'regions': 'us',
            'markets': 'h2h,spreads',  # Add more markets as needed
        }

        try:
            odds_response = requests.get(odds_url, params=odds_params)
            odds_response.raise_for_status()
        except requests.exceptions.RequestException as e:
            continue  # Skip sports that fail to fetch odds

        odds_data = odds_response.json()
        all_odds_data[sport_key] = odds_data

        # Save the odds data to MongoDB
        for game in odds_data:
            bet_id = game['id']  # Assuming each game has a unique 'id'
            # Save or update each bet in the 'live_odds' collection
            db.live_odds.update_one(
                {'bet_id': bet_id},
                {'$set': {'sport': sport_key, 'odds_data': game}},
                upsert=True
            )

    return jsonify(all_odds_data), 200


# Track bets for a user
@app.route('/track-bet', methods=['POST'])
def track_bet():
    data = request.json
    if 'username' not in data or 'bet_id' not in data:
        return jsonify({'error': 'Invalid data'}), 400

    username = data['username']
    bet_id = data['bet_id']
    market = data.get('market', 'moneyline')  # Default to 'moneyline' if not specified

    # Fetch the current odds for the bet_id from the live_odds collection
    live_odds = db.live_odds.find_one({'bet_id': bet_id})
    if not live_odds:
        return jsonify({'error': 'Bet not found'}), 404

    # Get the current odds at the time of saving
    current_odds = live_odds['odds_data']

    # Store the tracked bet with initial odds
    tracked_bet_entry = {
        'bet_id': bet_id,
        'market': market,
        'initial_odds': current_odds  # Save the odds at the time of being saved
    }

    # Update user's tracked bets in MongoDB
    result = users_collection.update_one(
        {'username': username},
        {'$addToSet': {'tracked_bets': tracked_bet_entry}},
        upsert=True
    )

    if result.matched_count == 0:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({'message': 'Bet tracked successfully'}), 200



def monitor_tracked_bets():
    while True:
        # Fetch all users with tracked bets
        users = users_collection.find({'tracked_bets': {'$exists': True, '$ne': []}})

        for user in users:
            username = user['username']
            tracked_bets = user.get('tracked_bets', [])
            
            # Debug: Print the structure of tracked_bets
            print(f"DEBUG: tracked_bets for user {username}: {tracked_bets}")

            for tracked_bet in tracked_bets:
                bet_id = tracked_bet['bet_id']
                initial_odds = tracked_bet['initial_odds']  # Now this should be available

                # Fetch the latest odds for this bet_id from live_odds collection
                live_odds_data = db.live_odds.find_one({'bet_id': bet_id})
                if not live_odds_data:
                    continue  # Skip if no live odds are found

                current_odds = live_odds_data['odds_data']

                # Check if the odds have changed by more than the user's threshold
                line_change_threshold = user.get('preferences', {}).get('line_change_threshold', 10)  # Default to 10%

                # Implement logic to compare initial_odds with current_odds
                if is_significant_change(initial_odds, current_odds, line_change_threshold):
                    # Trigger notification
                    send_notification(username, bet_id, current_odds)

        # Wait for a specified interval before checking again
        time.sleep(120)  # Check every 2 minutes



def is_significant_change(initial_odds, current_odds, threshold):
    """
    Determine if the change in odds is significant based on the given threshold.

    Args:
        initial_odds (dict): The initial odds stored at the time of tracking.
        current_odds (dict): The current odds fetched from the live feed.
        threshold (float): The percentage change threshold to trigger a notification.

    Returns:
        bool: True if a significant change is detected; False otherwise.
    """
    # Loop through each bookmaker
    for bookmaker in initial_odds['bookmakers']:
        bookmaker_key = bookmaker['key']
        
        # Find the same bookmaker in current_odds
        current_bookmaker = next((b for b in current_odds['bookmakers'] if b['key'] == bookmaker_key), None)
        if not current_bookmaker:
            continue  # Skip if this bookmaker is not found in the current odds

        # Loop through each market (e.g., "h2h")
        for market in bookmaker['markets']:
            market_key = market['key']
            
            # Find the same market in current_odds
            current_market = next((m for m in current_bookmaker['markets'] if m['key'] == market_key), None)
            if not current_market:
                continue  # Skip if this market is not found in the current odds

            # Loop through each outcome (e.g., "D.C. United", "Draw")
            for outcome in market['outcomes']:
                outcome_name = outcome['name']
                initial_price = outcome['price']
                
                # Find the same outcome in current_odds
                current_outcome = next((o for o in current_market['outcomes'] if o['name'] == outcome_name), None)
                if not current_outcome:
                    continue  # Skip if this outcome is not found in the current odds

                current_price = current_outcome['price']

                # Calculate the percentage change
                change_percentage = abs((current_price - initial_price) / initial_price) * 100
                if change_percentage >= threshold:
                    return True

    return False



def send_notification(username, bet_id, current_odds_data):
    """
    Send a notification to the user.
    """
    # Implement notification logic here (e.g., use Firebase Cloud Messaging)
    print(f"Notification sent to {username} for bet_id {bet_id}: {current_odds_data}")

# Run the monitor_tracked_bets function in a separate thread
monitor_thread = threading.Thread(target=monitor_tracked_bets, daemon=True)
monitor_thread.start()





if __name__ == '__main__':
    app.run(debug=True)


# Example: Fetch user details
@app.route('/user/<username>', methods=['GET'])
def get_user(username):
    user = users_collection.find_one({'username': username}, {'_id': 0})
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(user), 200

if __name__ == '__main__':
    app.run(debug=True)
