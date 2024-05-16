# stats/views.py
from django.shortcuts import render
from nba_api.stats.endpoints import playercareerstats, playergamelog
from nba_api.stats.static import players
import pandas as pd

def player_stats(request):
    context = {
        'leagues': ['NBA', 'NFL', 'NHL'],
        'players': []
    }

    if request.method == 'POST':
        league = request.POST.get('league')
        player_id = request.POST.get('player')

        if league == 'NBA' and player_id:
            # Fetch career stats and order by season (most recent first)
            career = playercareerstats.PlayerCareerStats(player_id=player_id).get_data_frames()[0]
            career = career.sort_values(by='SEASON_ID', ascending=False)
            context['stats'] = career.to_dict('records')

            # Fetch recent 10 games
            recent_games = playergamelog.PlayerGameLog(player_id=player_id, season='2023-24').get_data_frames()[0]
            recent_games = recent_games.head(10)  # Get the most recent 10 games

            # Process the recent games for opponent and home/away
            recent_games['OPPONENT'] = recent_games['MATCHUP'].apply(lambda x: x.split()[2])
            recent_games['HOME_AWAY'] = recent_games['MATCHUP'].apply(lambda x: 'Home' if x.split()[1] == 'vs.' else 'Away')

            # Calculate averages for the last 5 and 10 games, excluding non-numeric columns and 'VIDEO_AVAILABLE'
            numeric_columns = recent_games.select_dtypes(include=['number']).columns
            numeric_columns = numeric_columns.drop('VIDEO_AVAILABLE', errors='ignore')
            last_5_games_avg = recent_games.head(5)[numeric_columns].mean().to_dict()
            last_10_games_avg = recent_games[numeric_columns].mean().to_dict()
            
            # Format percentage columns
            percentage_columns = ['FG_PCT', 'FG3_PCT', 'FT_PCT']
            for col in percentage_columns:
                if col in last_5_games_avg:
                    last_5_games_avg[col] = round(last_5_games_avg[col] * 100, 1)
                if col in last_10_games_avg:
                    last_10_games_avg[col] = round(last_10_games_avg[col] * 100, 1)

            # Remove PLAYER_ID column
            last_5_games_avg.pop('PLAYER_ID', None)
            last_10_games_avg.pop('PLAYER_ID', None)

            context['recent_games'] = recent_games.to_dict('records')
            context['last_5_games_avg'] = last_5_games_avg
            context['last_10_games_avg'] = last_10_games_avg

            # Get player's full name
            player_info = next((p for p in players.get_active_players() if p['id'] == int(player_id)), None)
            context['player_name'] = player_info['full_name'] if player_info else 'Player'

        active_players = players.get_active_players()
        context['players'] = sorted(active_players, key=lambda x: x['full_name'])
        context['selected_league'] = league
        context['selected_player'] = player_id

    return render(request, 'stats/player_stats.html', context)
