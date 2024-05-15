# stats/views.py
from django.shortcuts import render
from nba_api.stats.endpoints import playercareerstats
from nba_api.stats.static import players

def player_stats(request):
    context = {
        'leagues': ['NBA', 'NFL', 'NHL'],
        'players': []
    }

    if request.method == 'POST':
        league = request.POST.get('league')
        player_id = request.POST.get('player')

        if league == 'NBA' and player_id:
            career = playercareerstats.PlayerCareerStats(player_id=player_id).get_data_frames()[0]
            context['stats'] = career.to_dict('records')

        active_players = players.get_active_players()
        context['players'] = sorted(active_players, key=lambda x: x['full_name'])

    return render(request, 'stats/player_stats.html', context)
