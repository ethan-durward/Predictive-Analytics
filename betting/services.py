import requests
import os
from scipy.optimize import fsolve
from datetime import datetime
import pytz
# from django.utils import timezone
from .models import Sport, Game, ValueBet

def get_sport_all_odds(api_key, url):
    params = {
        'apiKey': api_key,
        'regions': 'us',
        'markets': 'h2h',
        'oddsFormat': 'decimal',
        'dateFormat': 'iso',
    }
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None

def one_over_input(decimal):
    '''
    Takes in a decimal odd and returns the implied probability of that return
    Does NOT account for rake
    '''
    return 1 / decimal

def multiplicative_devig(p1, p2):
    """Multiplicative de-vigging method"""
    sum_p = p1 + p2
    
    true_p1 = p1/sum_p
    true_p2 = p2/sum_p
    
    return max(min(true_p1, p1, 1),0), max(min(true_p2, p2, 1),0)

def additive_devig(p1, p2):
    """Additive de-vigging method"""
    excess = (p1 + p2 - 1) / 2
    
    true_p1 = p1 - excess
    true_p2 = p2 - excess
    
    return max(min(true_p1, p1, 1),0), max(min(true_p2, p2, 1),0)

def power_devig(p1, p2):
    """Power de-vigging method"""
    overround = p1 + p2
    
    def power_equation(k):
        return (p1 / overround)**k + (p2 / overround)**k - 1
    
    k_solution = fsolve(power_equation, 1)[0]
    
    true_p1 = (p1 / overround) ** k_solution
    true_p2 = (p2 / overround) ** k_solution
    
    return max(min(true_p1, p1, 1),0), max(min(true_p2, p2, 1),0)

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

    return max(min(adjusted_prob_1, p1, 1),0), max(min(adjusted_prob_2, p2, 1),0)

def hybrid_devig(odds1, odds2):
    """
    Hybrid de-vigging approach that weights different methods based on odds characteristics
    """
    # Calculate how close the odds are to even money (2.0 in decimal odds)
    difference = min(abs(odds1 - odds2), 5) / 5  # from 0-1, 0 being even, 1 being maximum unevenness 
    evenness = max(min((1 - difference), 1), 0) ** 1.5  # Increased from 1.2 to 1.5 for more aggressive correction
    
    # Calculate margin size
    p1 = one_over_input(odds1)
    p2 = one_over_input(odds2)
    margin = (p1 + p2) - 1
    
    market_efficiency = max(0, 1 - (margin * 0.5))  # Increased from 0.4 to 0.5
    efficiency_factor = max(min(market_efficiency - (margin * 2), 1), 0)  # Increased from 1.5 to 2
    
    # Calculate weights for each method
    mult_weight = 0.3 * evenness * efficiency_factor  # Higher weight when odds are closer to even
    add_weight = 0.3 * (1 - evenness)  # Higher weight when odds are uneven
    power_weight = 0.4  # Constant weight
    shin_weight = 0.3 * (1 - evenness) * (1-efficiency_factor)  # Increased from 0.2 to 0.3
    
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
    final_p1 = (mult_p1 * mult_weight + 
                add_p1 * add_weight + 
                power_p1 * power_weight + 
                shin_p1 * shin_weight)
    
    final_p2 = (mult_p2 * mult_weight + 
                add_p2 * add_weight + 
                power_p2 * power_weight + 
                shin_p2 * shin_weight)
    
    # Ensure probabilities sum to 1
    total_prob = final_p1 + final_p2
    final_p1 /= total_prob
    final_p2 /= total_prob
    
    # Apply final constraint - making this less stringent to avoid overcorrection
    final_p1 = max(min(final_p1, p1, 1), 0)  # Allow 5% above implied probability (increased from 1%)
    final_p2 = max(min(final_p2, p2, 1), 0)  # Allow 5% above implied probability (increased from 1%)
    
    # Re-normalize after constraints
    total_final = final_p1 + final_p2
    final_p1 /= total_final
    final_p2 /= total_final
    
    return final_p1, final_p2

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
    risk_factor = true_prob ** 2 / 2 # Squared to penalize high risk more
    
    # EV factor (typically 1.0-1.2): higher EV means bigger bet
    ev_factor = max(0, (expected_value - 1) * 5)  # Scale EV to useful range
    
    # Combine factors
    bet_multiplier = risk_factor * (1 + ev_factor)
    
    # Calculate final bet size
    bet_size = round(base_unit * bet_multiplier)
    
    return min(bet_size, 20)  # Nothing higher than $20

def calculate_averages(sport_odds, sport_obj):
    # Clear existing games for this sport to avoid duplicates
    # Game.objects.filter(sport=sport_obj).delete()
    
    games_dict = {}
    created_games = []
    
    for game_data in sport_odds:
        # Parse the ISO timestamp and convert to Eastern Time
        utc_time = datetime.fromisoformat(game_data.get('commence_time').replace('Z', '+00:00'))
        eastern = pytz.timezone('America/Toronto')
        game_datetime = utc_time.astimezone(eastern)
        
        # Skip games that have already started
        if utc_time < datetime.now(utc_time.tzinfo):
            continue
        
        # Format date and time
        formatted_date = game_datetime.strftime('%Y-%m-%d')
        formatted_time = game_datetime.strftime('%I:%M %p ET')
        
        home_team = game_data['home_team']
        away_team = game_data['away_team']
        
        # Create game title with date and time
        game_title = f"{home_team} VS. {away_team} @ {formatted_date} {formatted_time}"
        
        # Create or update the Game object in the database
        game_obj, created = Game.objects.update_or_create(
            title=game_title,
            defaults={
                'sport': sport_obj,
                'home_team': home_team,
                'away_team': away_team,
                'commence_time': utc_time,
            }
        )
        created_games.append(game_obj)
        
        games_dict[game_title] = dict()
        
        # moneyline/head to head for home and away lists
        game_h2h_home_list = []
        game_h2h_away_list = []
        
        for bookmaker in game_data['bookmakers']:
            games_dict[game_title][bookmaker['title']] = dict()
            
            for market in bookmaker['markets']:
                outcomes = market['outcomes']
                if len(outcomes) == 2:  # Ensure there are two outcomes
                    if market['key'] == 'h2h':
                        # Getting the return/odds for each side of the bet
                        if outcomes[0]['name'] == home_team:
                            home_odds = outcomes[0]['price']
                            away_odds = outcomes[1]['price']
                        else:
                            home_odds = outcomes[1]['price']
                            away_odds = outcomes[0]['price']
                        
                        # Calculate implied probabilities and adjust
                        implied_prob_home = one_over_input(home_odds)
                        implied_prob_away = one_over_input(away_odds)
                        adjusted_prob_home, adjusted_prob_away = hybrid_devig(home_odds, away_odds)
                        
                        game_h2h_home_list.append(adjusted_prob_home)
                        game_h2h_away_list.append(adjusted_prob_away)
                        
                        games_dict[game_title][bookmaker['title']]["implied_prob_home"] = implied_prob_home
                        games_dict[game_title][bookmaker['title']]["implied_prob_away"] = implied_prob_away
        
        # Calculate average probabilities
        if game_h2h_home_list and game_h2h_away_list:
            avg_h2h_home = sum(game_h2h_home_list) / len(game_h2h_home_list)
            avg_h2h_away = sum(game_h2h_away_list) / len(game_h2h_away_list)
            
            games_dict[game_title]["average_home"] = avg_h2h_home
            games_dict[game_title]["average_away"] = avg_h2h_away
        
    # Delete games that were not in the API response
    Game.objects.filter(sport=sport_obj).exclude(id__in=[g.id for g in created_games]).delete()
    
    return games_dict, home_team, away_team

def find_value_bets(games_dict, threshold):
    # Clear existing value bets
    ValueBet.objects.all().delete()
    value_bets = {}
    
    # For diagnostic purposes - track how many bets meet different thresholds
    ev_count_90 = 0
    ev_count_95 = 0
    ev_count_100 = 0
    
    for game_title in games_dict:
        if "average_home" not in games_dict[game_title] or "average_away" not in games_dict[game_title]:
            continue

        probability_home = games_dict[game_title]["average_home"]
        probability_away = games_dict[game_title]["average_away"]
        
        # Get the game object from database
        try:
            game_obj = Game.objects.get(title=game_title)
        except Game.DoesNotExist:
            continue
        
        for bookmaker in games_dict[game_title]:
            # Skip non-bookmaker entries
            if bookmaker in ["average_home", "average_away"]:
                continue
                
            # Verify the required fields exist for this bookmaker
            if ("implied_prob_home" not in games_dict[game_title][bookmaker] or 
                "implied_prob_away" not in games_dict[game_title][bookmaker]):
                continue
                
            # Get decimal odds offered by bookmaker
            bookie_home_odds = 1/games_dict[game_title][bookmaker]["implied_prob_home"]
            bookie_away_odds = 1/games_dict[game_title][bookmaker]["implied_prob_away"]
                    
            # Compare true probability with bookmaker odds
            home_value = probability_home * bookie_home_odds
            away_value = probability_away * bookie_away_odds

            # Count bets at different thresholds for debugging
            if home_value >= 0.90:
                ev_count_90 += 1
            if home_value >= 0.95:
                ev_count_95 += 1
            if home_value >= 1.00:
                ev_count_100 += 1
            
            if away_value >= 0.90:
                ev_count_90 += 1
            if away_value >= 0.95:
                ev_count_95 += 1
            if away_value >= 1.00:
                ev_count_100 += 1

            # Check for value bets (if expected value >= (1 + threshold))
            # With threshold = -0.1, this is equivalent to expected value >= 0.9 (90%)
            min_acceptable_value = 1 + threshold
            
            # Always record home value bets for testing
            if home_value >= min_acceptable_value:
                # Initialize game entry in value_bets if not exists
                if game_title not in value_bets:
                    value_bets[game_title] = []
                
                bet_size = calculate_bet_size(
                    true_prob=probability_home,
                    offered_odds=bookie_home_odds,
                    expected_value=home_value
                )

                # Create ValueBet object in database
                ValueBet.objects.create(
                    game=game_obj,
                    bookmaker=bookmaker,
                    bet_type='home',
                    true_prob=probability_home,
                    offered_odds=bookie_home_odds,
                    expected_value=home_value,
                    bet_size=bet_size
                )
                
                value_bets[game_title].append({
                    'bookmaker': bookmaker,
                    'bet_type': 'home',
                    'true_prob': probability_home,
                    'offered_odds': bookie_home_odds,
                    'expected_value': home_value,
                    'bet_size': bet_size
                })
                
            # Always record away value bets for testing
            if away_value >= min_acceptable_value:
                # Initialize game entry in value_bets if not exists
                if game_title not in value_bets:
                    value_bets[game_title] = []
                    
                bet_size = calculate_bet_size(
                    true_prob=probability_away,
                    offered_odds=bookie_away_odds,
                    expected_value=away_value
                )

                # Create ValueBet object in database
                ValueBet.objects.create(
                    game=game_obj,
                    bookmaker=bookmaker,
                    bet_type='away',
                    true_prob=probability_away,
                    offered_odds=bookie_away_odds,
                    expected_value=away_value,
                    bet_size=bet_size
                )

                value_bets[game_title].append({
                    'bookmaker': bookmaker,
                    'bet_type': 'away',
                    'true_prob': probability_away,
                    'offered_odds': bookie_away_odds,
                    'expected_value': away_value,
                    'bet_size': bet_size
                })
    
    # Print diagnostic info
    print(f"Value bet counts by threshold:")
    print(f"90%+ EV: {ev_count_90}")
    print(f"95%+ EV: {ev_count_95}")
    print(f"100%+ EV: {ev_count_100}")
    print(f"Current threshold ({1+threshold:.2%} EV): {len(value_bets)}")
    
    return value_bets

def update_value_bets():
    """
    Get the latest odds and calculate value bets for all sports
    """
    api_key = os.getenv('ODDS_API_KEY')
    threshold = -0.1  # Changed from -0.05 to -0.1 to allow for 90% expected value
    sports_list = os.getenv('SPORTS_LIST', '').split(' ')
    
    key_to_sport = {
        'basketball_nba': 'NBA',
        'basketball_ncaab': 'NCAA Basketball',
        'icehockey_nhl': 'NHL'
    }
    
    for sport_key in sports_list:
        if sport_key in key_to_sport:
            sport_name = key_to_sport[sport_key]
            print(f'Getting {sport_name} odds')
            
            # Create or get the Sport object
            sport_obj, created = Sport.objects.get_or_create(
                key=sport_key,
                defaults={'name': sport_name}
            )
            
            sports_url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds/'
            sports_odds = get_sport_all_odds(api_key, sports_url)
            
            if sports_odds:
                games_dict, home_team, away_team = calculate_averages(sports_odds, sport_obj)
                find_value_bets(games_dict, threshold)
                
    return ValueBet.objects.all() 