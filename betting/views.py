from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from .models import ValueBet, Game, Sport
from .services_wrapper import update_value_bets_wrapper as update_value_bets
import time

def home(request):
    """Home page view - displays value bets"""
    # Get all value bets, organized by game
    games_with_bets = Game.objects.filter(value_bets__isnull=False).distinct()
    
    # Check if we need to update value bets (if none exist or it's been more than 5 minutes)
    if not games_with_bets.exists() or ValueBet.objects.count() == 0:
        update_value_bets()
        games_with_bets = Game.objects.filter(value_bets__isnull=False).distinct()
    
    # Get the last update time from the newest value bet
    try:
        last_update = ValueBet.objects.latest('timestamp').timestamp
    except ValueBet.DoesNotExist:
        last_update = timezone.now()
    
    context = {
        'games': games_with_bets,
        'last_update': last_update,
    }
    
    return render(request, 'betting/home.html', context)

def refresh_value_bets(request):
    """API endpoint to refresh value bets"""
    start_time = time.time()
    value_bets = update_value_bets()
    end_time = time.time()
    
    try:
        last_update = ValueBet.objects.latest('timestamp').timestamp
    except ValueBet.DoesNotExist:
        last_update = timezone.now()
    
    return JsonResponse({
        'status': 'success',
        'message': f"Updated {value_bets.count()} value bets in {end_time - start_time:.2f} seconds",
        'last_update': last_update.strftime('%Y-%m-%d %H:%M:%S'),
        'count': value_bets.count()
    })
