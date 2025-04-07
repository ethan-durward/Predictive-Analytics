from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from .models import ValueBet, Game, Sport
from .services_wrapper import update_value_bets_wrapper as update_value_bets
import time
from django.db.models import Avg, Count, Q

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
    
    # Calculate additional statistics for the enhanced UI
    value_bets = ValueBet.objects.all()
    high_value_count = value_bets.filter(expected_value__gt=1.05).count()
    good_value_count = value_bets.filter(expected_value__gt=1.0, expected_value__lte=1.05).count()
    avg_bet_size = value_bets.aggregate(avg_size=Avg('bet_size'))['avg_size']
    
    if avg_bet_size is None:
        avg_bet_size = 0
    else:
        avg_bet_size = round(avg_bet_size)
    
    # Get list of bookmakers for filters
    bookmakers = ValueBet.objects.values_list('bookmaker', flat=True).distinct()
    
    context = {
        'games': games_with_bets,
        'last_update': last_update,
        'high_value_count': high_value_count,
        'good_value_count': good_value_count,
        'avg_bet_size': avg_bet_size,
        'bookmakers': bookmakers,
        'total_value_bets': value_bets.count(),
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
    
    # Calculate additional statistics
    high_value_count = value_bets.filter(expected_value__gt=1.05).count()
    
    return JsonResponse({
        'status': 'success',
        'message': f"Updated {value_bets.count()} value bets in {end_time - start_time:.2f} seconds",
        'last_update': last_update.strftime('%Y-%m-%d %H:%M:%S'),
        'count': value_bets.count(),
        'high_value_count': high_value_count
    })
