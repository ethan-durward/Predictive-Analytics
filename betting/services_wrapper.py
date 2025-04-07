import os
from .services import get_sport_all_odds, find_value_bets, calculate_averages
from .models import Sport, ValueBet

def update_value_bets_wrapper():
    """
    A wrapper for the update_value_bets function that handles the mismatch
    between what calculate_averages returns and what update_value_bets expects
    """
    api_key = os.getenv('ODDS_API_KEY')
    threshold = float(os.getenv('THRESHOLD', '-0.1'))  # Default to -10% (90% EV) if not set
    print(f"Using threshold value: {threshold}")
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
                # Call calculate_averages and handle its 3-value return
                result = calculate_averages(sports_odds, sport_obj)
                
                # Extract just the games_dict from the returned tuple
                games_dict = result[0] if isinstance(result, tuple) else result
                
                # Pass the games_dict to find_value_bets
                find_value_bets(games_dict, threshold)
                
    return ValueBet.objects.all() 