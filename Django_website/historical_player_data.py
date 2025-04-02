from nba_api.stats.static import players
import json
from nba_api.stats.endpoints import playergamelog
import pandas as pd
import time
from requests.exceptions import Timeout


# Function to fetch data for all active NBA players
def fetch_all_players_data():
    all_players = players.get_players()
    active_players = [player for player in all_players if player['is_active']]
    return active_players


# Function to save data to a JSON file
def save_data_to_json(data, filename):
    with open(filename, 'w') as file:
        json.dump(data, file)




def fetch_player_game_stats(player_id, season):
    attempts = 0
    max_attempts = 5
    waittime = 40
    
    while attempts < max_attempts:
        try:
            game_log = playergamelog.PlayerGameLog(player_id=player_id, season=season)
            return game_log.get_data_frames()[0]
        except Timeout:
            attempts += 1
            print(f"Timeout error occurred for player {player_id}, season {season}. Waiting {waittime} seconds before trying again.")
            time.sleep(waittime)
            waittime *= 2
        except Exception as e:
            print(f"An error occurred: {e}")
            break
    return pd.DataFrame()


with open('./JSON/nba_player_short.json', 'r') as file:
    all_players_data = json.load(file)
    player_ids = [player['id'] for player in all_players_data]

    detailed_stats = []

    for player_id in player_ids:
        for season in ['2022-23', '2023-24']: #['2019-20', '2020-21', '2021-22']:
            try:
                stats = fetch_player_game_stats(player_id, season)
                detailed_stats.extend(stats.to_dict('records'))
            except Exception as e:
                print(f"Error fetching data for player {player_id}, season {season}: {e}")

# Save to JSON
save_data_to_json(detailed_stats, './JSON/detailed_player_stats.json')





# # Main script to get all players and their ID's. Should be run at the beginning of every season to get new players. 
# if __name__ == "__main__":
#     try:
#         all_players_data = fetch_all_players_data()
#         save_data_to_json(all_players_data, './JSON/nba_players.json')
#         print("All NBA players data successfully saved to nba_players.json.")
#     except Exception as e:
#         print(f"An error occurred: {e}")