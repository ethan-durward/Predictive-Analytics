import requests, os
from dotenv import load_dotenv
from scipy.optimize import fsolve
from datetime import datetime
import pytz
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import json
import base64
from email.mime.text import MIMEText


def get_nba_total_score_odds(api_key, url):
    params = {
        'apiKey': api_key,
        'regions': 'us',  # Region can be us, uk, eu, au, etc.
        'markets': 'h2h',  # Specify the market for which odds are required
        'oddsFormat': 'decimal',
        'dateFormat': 'iso',
    }
    # url = 'https://api.the-odds-api.com/v4/sports/basketball_nba/odds/'
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        return response.json()  # This will return a JSON object with all NBA games and their total score odds
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None


def one_over_input(decimal):
    '''
    Takes in a decimal odd and returns the implied probability of that return
    Does NOT account for rake
    '''
    return 1 / decimal


def calculate_bet_size(home_odds, away_odds, default_bet = 100):
    """
    Calculate recommended bet size based on:
    1. Risk (using true probability - lower prob means higher risk)
    2. Expected Value (higher EV means bigger bet)
    
    Args:
        true_prob: Your estimated true probability (0-1)
        offered_odds: Decimal odds from bookmaker
        expected_value: Calculated EV
        base_unit: Base betting unit (default $100)
    """
    return (default_bet/home_odds, default_bet/away_odds)






####### Main Program #######
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../.env'))
load_dotenv(dotenv_path=env_path)

api_key = os.getenv('ODDS_API_KEY')
threshold = float(os.getenv('ARBITRAGE_THRESHOLD'))
url_nba = os.getenv('NBA_URL')
email_status = os.getenv('EMAIL_STATUS')
email_type = os.getenv("EMAIL_TYPE")

nba_odds = get_nba_total_score_odds(api_key, url_nba)
games_dict = dict()

if nba_odds:
    for game in nba_odds:
        # Parse the ISO timestamp and convert to Eastern Time
        utc_time = datetime.fromisoformat(game.get('commence_time').replace('Z', '+00:00'))
        eastern = pytz.timezone('America/Toronto')
        game_datetime = utc_time.astimezone(eastern)
        
        # # continue to next game if this game is live
        # if utc_time < datetime.now(utc_time.tzinfo):
        #     continue
        
        # Format date and time (12-hour format in ET)
        formatted_date = game_datetime.strftime('%Y-%m-%d')
        formatted_time = game_datetime.strftime('%I:%M %p ET')  # Added ET indicator
    
        home_team = game['home_team']
        away_team = game['away_team']
        
        # Create game title with date and time
        game_title = f"{home_team} VS. {away_team} @ {formatted_date} {formatted_time}"
        games_dict[game_title] = dict()
        
        
        # moneyline/head to head for home and away lists
        game_h2h_home_list = []
        game_h2h_away_list = []
        
        
        for bookmaker in game['bookmakers']:
            games_dict[game_title][bookmaker['key']] = dict()
            for market in bookmaker['markets']:
                # print(f"Market: {market['key']}")
                outcomes = market['outcomes']
                if len(outcomes) == 2:  # Ensure there are two outcomes to calculate probabilities
                    if market['key'] == 'h2h':
                        # getting the return/odds for each side of the moneyline/h2h bet
                        # odds_1 is for home, odds_2 is for away
                        if outcomes[0]['name'] == home_team:
                            home_odds = outcomes[0]['price']
                            away_odds = outcomes[1]['price']
                        else:
                            home_odds = outcomes[1]['price']
                            away_odds = outcomes[0]['price']
            games_dict[game_title][bookmaker['key']] = {'home': home_odds, 'away': away_odds}
print('*'*50)





####### FINDING ARBITRAGE BETS #######
arbitrage_bets = {}

for game in games_dict:
    # Debug print
    print(f"\nChecking game: {game}")
    
    for bookmaker in games_dict[game]:
        # Skip non-bookmaker entries
        if bookmaker in ["average_home", "average_away"]:
            continue
            
        # Get decimal odds offered by bookmaker
        bookie_home_odds = games_dict[game][bookmaker]['home']
        bookie_away_odds = games_dict[game][bookmaker]['away']
        
        for inner_bookmaker in games_dict[game]:
            if inner_bookmaker == bookmaker:
                continue
            
            inner_bookie_home_odds = games_dict[game][inner_bookmaker]['home']
            inner_bookie_away_odds = games_dict[game][inner_bookmaker]['away']
            home_ev = 1 + 1 - (one_over_input(bookie_home_odds) + one_over_input(inner_bookie_away_odds))
            away_ev = 1 + 1 - (one_over_input(bookie_away_odds) + one_over_input(inner_bookie_home_odds))
            # print(home_ev, away_ev)
            
            if home_ev > (1 + threshold):
                if game not in arbitrage_bets:
                    arbitrage_bets[game] = []
                
                home_bet, away_bet = calculate_bet_size(bookie_home_odds, inner_bookie_away_odds)
                arb_bet = {
                    'home_bookmaker': bookmaker,
                    'away_bookmaker': inner_bookmaker,
                    'home_odds': bookie_home_odds,
                    'away_odds': inner_bookie_away_odds,
                    'expected_value': home_ev ,
                    'home_bet_size': home_bet,
                    'away_bet_size': away_bet
                }
                if arb_bet not in arbitrage_bets[game]:
                    arbitrage_bets[game].append(arb_bet)
                    print(f"ARBITRAGE FOUND ON {game} with {bookmaker} and {inner_bookmaker}")
                
            if away_ev > (1 + threshold):
                if game not in arbitrage_bets:
                    arbitrage_bets[game] = []
                
                home_bet, away_bet = calculate_bet_size(inner_bookie_home_odds, bookie_away_odds)
                arb_bet = {
                    'home_bookmaker': inner_bookmaker,
                    'away_bookmaker': bookmaker,
                    'home_odds': inner_bookie_home_odds,
                    'away_odds': bookie_away_odds,
                    'expected_value': away_ev,
                    'home_bet_size': home_bet,
                    'away_bet_size': away_bet
                }
                if arb_bet not in arbitrage_bets[game]:
                    arbitrage_bets[game].append(arb_bet)
                    print(f"ARBITRAGE FOUND ON {game} with {bookmaker} and {inner_bookmaker}")
                
        



print("\n" + "="*80)
print("VALUE BETS SUMMARY")
print("="*80)

if not arbitrage_bets:
    print("No arbitrage bets found")
else:
    for game, bets in arbitrage_bets.items():
        print(f"\n🏀 GAME: {game}")
        print(f"Found {len(bets)} arbitrage bet(s):")
        
        for bet in bets:
            print("\n  📊 BET DETAILS:")
            print(f"    Home Bookmaker: {bet['home_bookmaker']}")
            print(f"    Away Bookmaker: {bet['away_bookmaker']}")
            print(f"    Home Odds: {bet['home_odds']}")
            print(f"    Away Odds: {bet['away_odds']}")
            print(f"    Expected Value: {bet['expected_value']}")
            print(f"    Recommended Home Bet: ${bet['home_bet_size']}") 
            print(f"    Recommended Away Bet: ${bet['away_bet_size']}") 
            
            if bet['expected_value'] > 1.05:
                print("    🔥 HIGH VALUE BET!")
            elif bet['expected_value'] > 1.00:
                print("    ✅ GOOD VALUE")
                
        print("\n" + "-"*60)

print("\nAnalysis complete!")


### EMAIL SERVICE ###
def get_gmail_service():
    """Gets Gmail API service instance."""
    SCOPES = ['https://www.googleapis.com/auth/gmail.send']
    creds = None
    
    # The file token.json stores the user's access and refresh tokens
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If no valid credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                './___ValueBetEmails/client_secret_gmail.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)

def create_value_bets_email(value_bets):
    """Creates email content from value bets."""
    email_content = "Value Bets Found:\n\n"
    
    if not value_bets:
        email_content = "No value bets found at this time."
    else:
        for game, bets in value_bets.items():
            email_content += f"\n🏀 GAME: {game}\n"
            email_content += f"Found {len(bets)} value bet(s):\n"
            
            for bet in bets:
                email_content += f"\n  📊 BET DETAILS:\n"
                email_content += f"    Home Bookmaker: {bet['home_bookmaker']}\n"
                email_content += f"    Away Bookmaker: {bet['away_bookmaker']}\n"
                email_content += f"    Home Odds: {bet['home_odds']:.2%}\n"
                email_content += f"    Away Odds: {bet['away_odds']:.2f}\n"
                email_content += f"    Expected Value: {bet['expected_value']:.3f}\n"
                email_content += f"    Recommended Bet: ${bet['bet_size']}\n"
                
                if bet['expected_value'] > 1.05:
                    email_content += "    🔥 HIGH VALUE BET!\n"
                elif bet['expected_value'] > 1.00:
                    email_content += "    ✅ GOOD VALUE\n"
                
            email_content += "\n" + "-"*60 + "\n"
    
    return email_content

def send_email(service, sender, to, subject, message_text):
    """Sends an email."""
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    try:
        service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
        print(f"Email sent successfully to {to}")
    except Exception as e:
        print(f"An error occurred: {e}")


# Script that actually runs :)
if email_status == "on":
    # After your value bets analysis, replace the existing if value_bets: block with:
    if arbitrage_bets:  # Only proceed if there are value bets
        try:
            # Load email list
            with open(f'./___ValueBetEmails/email_list.json', 'r') as f:
                email_data = json.load(f)
            
            # Get Gmail service
            service = get_gmail_service()
            
            # Create email content
            email_content = create_value_bets_email(arbitrage_bets)
            
            # Send to each email in the list
            for email in email_data[email_type]:
                send_email(
                    service=service,
                    sender="me",
                    to=email,
                    subject="NBA Arbitrage Bets Alert",
                    message_text=email_content
                )
                
        except Exception as e:
            print(f"Error sending emails: {e}")
    else:
        print("No value bets found - no emails sent")
