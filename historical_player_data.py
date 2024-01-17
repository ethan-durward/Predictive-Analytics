from nba_api.stats.static import players
import json
from nba_api.stats.endpoints import playergamelog


# Function to fetch data for all active NBA players
def fetch_all_players_data():
    all_players = players.get_players()
    active_players = [player for player in all_players if player['is_active']]
    return active_players


# Function to save data to a JSON file
def save_data_to_json(data, filename):
    with open(filename, 'w') as file:
        json.dump(data, file)

# Main script
if __name__ == "__main__":
    try:
        all_players_data = fetch_all_players_data()
        save_data_to_json(all_players_data, 'nba_players.json')
        print("All NBA players data successfully saved to nba_players.json.")
    except Exception as e:
        print(f"An error occurred: {e}")



def fetch_player_game_stats(player_id, season):
    game_log = playergamelog.PlayerGameLog(player_id=player_id, season=season)
    return game_log.get_data_frames()[0]

player_ids = [player['id'] for player in all_players_data]  # Assuming all_players_data is your initial data

detailed_stats = []

for player_id in player_ids:
    for season in ['2021-22']: #['2019-20', '2020-21', '2021-22']:
        try:
            stats = fetch_player_game_stats(player_id, season)
            detailed_stats.extend(stats.to_dict('records'))
        except Exception as e:
            print(f"Error fetching data for player {player_id}, season {season}: {e}")

# Save to JSON
with open('detailed_player_stats.json', 'w') as file:
    json.dump(detailed_stats, file)
