from django.shortcuts import render
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import teamgamelog, playergamelog, playercareerstats, commonteamroster
from django.http import HttpResponse
import pandas as pd
import time


def team_stats(request):
    leagues = ["NBA", "NFL", "NHL"]
    selected_league = request.POST.get("league")
    selected_team = request.POST.get("team")
    team_list = []
    if selected_league == "NBA":
        team_list = teams.get_teams()
    
    players_stats = []
    player_map = {}
    last_5_games_stats = []
    
    if selected_team:
        team_name = next((team['full_name'] for team in team_list if str(team['id']) == selected_team), None)
        common_team_roster = commonteamroster.CommonTeamRoster(team_id=selected_team, season="2023-24")
        players = common_team_roster.get_dict()['resultSets'][0]['rowSet']
        
        for player in players:
            player_id = player[14]  # either 0 or 14
            # print(player)
            player_name = player[3]  # This index should be correct for player_name
            player_map[player_id] = player_name
            
            
            # for recent games stats
            recent_games_endpoint = playergamelog.PlayerGameLog(player_id=player_id).get_data_frames()[0].head(5)
            recent_games = recent_games_endpoint.to_dict('records')
            last_5_games_avg = recent_games_endpoint.mean(numeric_only=True).to_dict()    
            last_5_games_stats.append(last_5_games_avg)        
            
            
            # for season records 
            stats = playercareerstats.PlayerCareerStats(player_id=player_id).get_data_frames()[0].to_dict('records')
            for stat in stats:
                # print("\n\n", stat)
                if stat['SEASON_ID'] == '2023-24':
                    stat['player_name'] = player_name
                    players_stats.append(stat)
                    # print(stat)
                    break
            time.sleep(5)
            


        context = {
            "leagues": leagues,
            "selected_league": selected_league,
            "teams": team_list,
            "selected_team": selected_team,
            "recent_games": recent_games,
            "players_stats": players_stats,
            "last_5_games_stats": last_5_games_stats,
            "team_name": team_name,
            "player_map": player_map,
        }
        print("team list: ", context["teams"])
        print("\n\nselected_league: ", context["selected_league"])
        print("\n\nselected_team: ", context["selected_team"])
        print("\n\nplayers_stats: ", context["players_stats"])
        print("\n\nlast_5_games_stats: ", context["last_5_games_stats"])
        print("\n\nteam_name: ", context["team_name"])
        print("\n\nplayer_map: ", context["player_map"])
    else:
        context = {
            "leagues": leagues,
            "teams": team_list,
            "selected_league": selected_league,
            "selected_team": selected_team,
        }

    return render(request, 'stats/team_stats.html', context)



def player_stats(request):
    leagues = ['NBA', 'NFL', 'NHL']
    selected_league = request.POST.get('league')
    selected_player = request.POST.get('player')
    stats  = recent_games = last_5_games_avg = last_10_games_avg = player_name = None

    if selected_league and selected_player:
        player_id = selected_player
        career = playercareerstats.PlayerCareerStats(player_id=player_id).get_data_frames()[0]
        stats = career.to_dict('records')
        player_name = players.find_player_by_id(player_id)['full_name']

        recent_games_endpoint = playergamelog.PlayerGameLog(player_id=player_id).get_data_frames()[0].head(10)
        recent_games = recent_games_endpoint.to_dict('records')
        last_5_games_avg = recent_games_endpoint.head(5).mean(numeric_only=True).to_dict()
        last_10_games_avg = recent_games_endpoint.mean(numeric_only=True).to_dict()

    return render(request, 'stats/player_stats.html', {
        'leagues': leagues,
        'selected_league': selected_league,
        'recent_games': recent_games,
        'selected_player': selected_player,
        'players': players.get_active_players(),
        'stats': stats,
        'last_5_games_avg': last_5_games_avg,
        'last_10_games_avg': last_10_games_avg,
        'player_name': player_name,
    })

def probabilities(request):
    return render(request, 'stats/probabilities.html')

def smart_bets(request):
    return render(request, 'stats/smart_bets.html')