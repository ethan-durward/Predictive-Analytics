import requests
import os
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


def estimated_probability_single(odds):
    '''
    Takes in a decimal odd and returns the estimated probability of that event
    Accounts for rake
    Accounts for rake of 5% (1.05)
    '''
    # Convert decimal odds to implied probabilities
    implied_prob = 1 / odds
    
    # Calculate the overround/vig
    overround = 1.05
    
    # Normalize the probabilities to account for the overround
    normalized_prob = implied_prob / overround
    
    # Return the estimated probability (typically of the first outcome)
    return normalized_prob


def multiplicative_devig(p1, p2):
    """Multiplicative de-vigging method"""
    sum_p = p1 + p2
    
    true_p1 = p1/sum_p
    true_p2 = p2/sum_p
    
    return max(min(true_p1,1),0), max(min(true_p2,1),0)

def additive_devig(p1, p2):
    """Additive de-vigging method"""
    excess = (p1 + p2 - 1) / 2
    
    true_p1 = p1 - excess
    true_p2 = p2 - excess
    
    return max(min(true_p1,1),0), max(min(true_p2,1),0)

def power_devig(p1, p2):
    """Power de-vigging method"""
    overround = p1 + p2
    
    def power_equation(k):
        return (p1 / overround)**k + (p2 / overround)**k - 1
    
    k_solution = fsolve(power_equation, 1)[0]
    
    true_p1 = (p1 / overround) ** k_solution
    true_p2 = (p2 / overround) ** k_solution
    
    return max(min(true_p1,1),0), max(min(true_p2,1),0)

def shin_devig(p1, p2):
    """Shin's method for de-vigging"""
    def shin_margin_equation(z):
        term_1 = p1 / (1-z*p1)
        term_2 = p2 / (1-z*p2)
        return term_1 + term_2 - 1
    
    z_solution = fsolve(shin_margin_equation, 0.01)[0]
    
    adjusted_prob_1 = p1 / (1 - z_solution * p1)
    adjusted_prob_2 = p2 / (1 - z_solution * p2)

    # Normalize probabilities to ensure they sum to 1
    total_adjusted_prob = adjusted_prob_1 + adjusted_prob_2
    adjusted_prob_1 /= total_adjusted_prob
    adjusted_prob_2 /= total_adjusted_prob

    return max(min(adjusted_prob_1,1),0), max(min(adjusted_prob_2,1),0)

def hybrid_devig(odds1, odds2):
    """
    Hybrid de-vigging approach that weights different methods based on odds characteristics
    """
    # Calculate how close the odds are to even money (2.0 in decimal odds)
    # old_evenness = 1 - (abs(2.0 - ((odds1 + odds2) / 2)) / 2)
    difference = min(abs(odds1 - odds2), 5) / 5  # from 0-1, 0 being even, 1 being maximum unevenness 
    evenness = max(min((1 - difference), 1), 0) ** 1.5  # 0 is uneven, 1 is even. Squared to emphasize impact 
    print(f'Evenness: {evenness}')
    
    # Calculate margin size
    p1 = one_over_input(odds1)
    p2 = one_over_input(odds2)
    margin = (p1 + p2) - 1
    
    # Calculate weights for each method
    mult_weight = 0.3 * evenness  # Higher weight when odds are closer to even
    add_weight = 0.4 * (1 - evenness)  # Higher weight when odds are uneven
    power_weight = 0.3  # Constant weight
    shin_weight = 0.2 * (1 - evenness)
    
    # Normalize weights
    total_weight = mult_weight + add_weight + power_weight + shin_weight
    mult_weight /= total_weight
    add_weight /= total_weight
    power_weight /= total_weight
    shin_weight /= total_weight
    
    # Calculate probabilities using each method
    mult_p1, mult_p2 = multiplicative_devig(p1, p2)
    add_p1, add_p2 = additive_devig(p1, p2)
    power_p1, power_p2 = power_devig(p1, p2)
    shin_p1, shin_p2 = shin_devig(p1, p2)
    
    # Combine probabilities using weights
    # final_p1 = min(mult_p1, add_p1, power_p1, shin_p1)
    # final_p2 = min(mult_p2, add_p2, power_p2, shin_p2)
    final_p1 = (mult_p1 * mult_weight + 
                add_p1 * add_weight + 
                power_p1 * power_weight + 
                shin_p1 * shin_weight)
    
    final_p2 = (mult_p2 * mult_weight + 
                add_p2 * add_weight + 
                power_p2 * power_weight + 
                shin_p2 * shin_weight)
    total_prob = final_p1 + final_p2
    final_p1 /= total_prob
    final_p2 /= total_prob
    print(final_p1)
    print(final_p2)
    print()
    
    return max(min(final_p1,1),0), max(min(final_p2,1),0)

def calculate_bet_size(true_prob, offered_odds, expected_value, base_unit=100):
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
    # Risk factor (0-1): lower probability means higher risk
    risk_factor = true_prob ** 2  # Squared to penalize high risk more
    
    # EV factor (typically 1.0-1.2): higher EV means bigger bet
    ev_factor = max(0, (expected_value - 1) * 5)  # Scale EV to useful range
    
    # Combine factors
    bet_multiplier = risk_factor * (1 + ev_factor)
    
    # Calculate final bet size
    bet_size = round(base_unit * bet_multiplier)
    
    return min(bet_size, 20)  # Nothing higher than $20






####### Main Program #######
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../.env'))
load_dotenv(dotenv_path=env_path)

api_key = os.getenv('ODDS_API_KEY')
threshold = float(os.getenv('THRESHOLD'))
url_nba = os.getenv('NBA_URL')
email_status = os.getenv('EMAIL_STATUS')

nba_odds = get_nba_total_score_odds(api_key, url_nba)
games_dict = dict()

if nba_odds:
    for game in nba_odds:
        # Parse the ISO timestamp and convert to Eastern Time
        utc_time = datetime.fromisoformat(game.get('commence_time').replace('Z', '+00:00'))
        eastern = pytz.timezone('America/Toronto')
        game_datetime = utc_time.astimezone(eastern)
        
        # continue to next game if this game is live
        if utc_time < datetime.now(utc_time.tzinfo):
            continue
        
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
            # print(f"Bookmaker: {bookmaker['title']}")
            games_dict[game_title][bookmaker['title']] = dict()
            
            for market in bookmaker['markets']:
                last_update = market['last_update']
                print(f"Last Update: {last_update}")
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
                        # home_odds = outcomes[0]['price']
                        # away_odds = outcomes[1]['price']
                        
                        
                        # Calculate implied probabilities and adjust to estimate true probability
                        implied_prob_home = one_over_input(home_odds)
                        implied_prob_away = one_over_input(away_odds)
                        adjusted_prob_home, adjusted_prob_away = hybrid_devig(home_odds, away_odds)
                        
                        
                        game_h2h_home_list.append(adjusted_prob_home) # the estimated probability using hybrid devig
                        game_h2h_away_list.append(adjusted_prob_away) # used for calculating average/TRUE probability of event
                        
                        games_dict[game_title][bookmaker['title']]["implied_prob_home"] = implied_prob_home # the implied probability based on the bookmaker's odds
                        games_dict[game_title][bookmaker['title']]["implied_prob_away"] = implied_prob_away # used to refer back to when looking for value bets
        
####### CALCULATING AVERAGE PROBABILITIES #######
        if game_h2h_home_list and game_h2h_away_list:
            avg_h2h_home = sum(game_h2h_home_list) / len(game_h2h_home_list)
            avg_h2h_away = sum(game_h2h_away_list) / len(game_h2h_away_list)
            
            # Debug print
            # print(f"\nCalculating averages for {game_title}")
            # print(f"Home list: {game_h2h_home_list}")
            # print(f"Away list: {game_h2h_away_list}")
            # print(f"Averages - Home: {avg_h2h_home:.4f}, Away: {avg_h2h_away:.4f}")
            
            games_dict[game_title]["average_home"] = avg_h2h_home
            games_dict[game_title]["average_away"] = avg_h2h_away
        else:
            print(f"****ERROR**** No game_h2h_home_list or away list for {game_title}")
print('*'*50)

# After creating games_dict
# print("\nDEBUG: Games Dictionary Structure")
# print("="*80)
# for game in games_dict:
    # print(f"\nGame: {game}")
    # print("Keys in this game:", list(games_dict[game].keys()))
    # for key in games_dict[game]:
    #     if key not in ["average_home", "average_away"]:
#             print(f"\nBookmaker: {key}")
#             print("Data:", games_dict[game][key])
# print("="*80)





####### FINDING VALUE BETS #######
value_bets = {}
# print("\n" + "="*80)
# print("ANALYZING GAMES FOR VALUE BETS")
# print("="*80)

for game in games_dict:
    # Debug print
    print(f"\nChecking game: {game}")
    
    if "average_home" not in games_dict[game] or "average_away" not in games_dict[game]:
        print(f"Missing averages for {game}")
        print("Available keys:", list(games_dict[game].keys()))
        continue

    probability_home = games_dict[game]["average_home"]
    probability_away = games_dict[game]["average_away"]
    
    # Debug print
    # print(f"Found probabilities - Home: {probability_home:.4f}, Away: {probability_away:.4f}")
    
    for bookmaker in games_dict[game]:
        # Skip non-bookmaker entries
        if bookmaker in ["average_home", "average_away"]:
            continue
            
        # Verify the required fields exist for this bookmaker
        if ("implied_prob_home" not in games_dict[game][bookmaker] or 
            "implied_prob_away" not in games_dict[game][bookmaker]):
            continue
            
        # Get decimal odds offered by bookmaker
        bookie_home_odds = 1/games_dict[game][bookmaker]["implied_prob_home"]
        bookie_away_odds = 1/games_dict[game][bookmaker]["implied_prob_away"]
        
        # print(f"\nBookmaker: {bookmaker}")
        # print(f"  Offered odds - Home: {bookie_home_odds:.2f}, Away: {bookie_away_odds:.2f}")
        
        # Compare true probability with bookmaker odds
        # If true_prob * decimal_odds > 1, it's a value bet
        home_value = probability_home * bookie_home_odds
        away_value = probability_away * bookie_away_odds
        
        # print(f"  Value calculation:")
        # print(f"    Home: {probability_home:.4f} * {bookie_home_odds:.2f} = {home_value:.3f}")
        # print(f"    Away: {probability_away:.4f} * {bookie_away_odds:.2f} = {away_value:.3f}")


        
        # Check for value bets (if expected value > 1.05 meaning 5% edge)
        if home_value > 1 + threshold:
            # Initialize game entry in value_bets if not exists
            if game not in value_bets:
                value_bets[game] = []
            
            bet_size = calculate_bet_size(
                true_prob=probability_home,
                offered_odds=bookie_home_odds,
                expected_value=home_value
            )

            value_bets[game].append({
                'bookmaker': bookmaker,
                'bet_type': 'home',
                'true_prob': probability_home,
                'offered_odds': bookie_home_odds,
                'expected_value': home_value,
                'bet_size': bet_size
            })
            
            
            
        if away_value > 1 + threshold:
            # Initialize game entry in value_bets if not exists
            if game not in value_bets:
                value_bets[game] = []
                
            bet_size = calculate_bet_size(
                true_prob=probability_away,
                offered_odds=bookie_away_odds,
                expected_value=away_value
            )

            value_bets[game].append({
                'bookmaker': bookmaker,
                'bet_type': 'away',
                'true_prob': probability_away,
                'offered_odds': bookie_away_odds,
                'expected_value': away_value,
                'bet_size': bet_size
            })
            # print(f"    >>> VALUE BET FOUND ON AWAY <<<")

print("\n" + "="*80)
print("VALUE BETS SUMMARY")
print("="*80)

if not value_bets:
    print("No value bets found")
else:
    for game, bets in value_bets.items():
        print(f"\n🏀 GAME: {game}")
        print(f"Found {len(bets)} value bet(s):")
        
        for bet in bets:
            print("\n  📊 BET DETAILS:")
            print(f"    Bookmaker: {bet['bookmaker']}")
            print(f"    Bet Type: {bet['bet_type']}")
            print(f"    True Probability: {bet['true_prob']:.2%}")
            print(f"    Bookmaker Odds: {bet['offered_odds']:.2f}")
            print(f"    Expected Value: {bet['expected_value']:.3f}")
            print(f"    Recommended Bet: ${bet['bet_size']}") 
            
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
                email_content += f"    Bookmaker: {bet['bookmaker']}\n"
                email_content += f"    Bet Type: {bet['bet_type']}\n"
                email_content += f"    True Probability: {bet['true_prob']:.2%}\n"
                email_content += f"    Bookmaker Odds: {bet['offered_odds']:.2f}\n"
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
    if value_bets:  # Only proceed if there are value bets
        try:
            # Load email list
            with open('./___ValueBetEmails/email_list.json', 'r') as f:
                email_data = json.load(f)
            
            # Get Gmail service
            service = get_gmail_service()
            
            # Create email content
            email_content = create_value_bets_email(value_bets)
            
            # Send to each email in the list
            for email in email_data['email_list']:
                send_email(
                    service=service,
                    sender="me",
                    to=email,
                    subject="NBA Value Bets Alert",
                    message_text=email_content
                )
                
        except Exception as e:
            print(f"Error sending emails: {e}")
    else:
        print("No value bets found - no emails sent")
