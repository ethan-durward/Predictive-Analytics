from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from .models import ValueBet, Game, Sport, UserProfile, UserBookmakerPreference, PlacedBet, ValueBetTracker
from .services_wrapper import update_value_bets_wrapper as update_value_bets
import time
from django.db.models import Avg, Count, Q, Sum, F, DecimalField, ExpressionWrapper, FloatField
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.urls import reverse
from django.contrib import messages
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

from .forms import CustomUserCreationForm, CustomAuthenticationForm, UserProfileForm, BookmakerPreferenceForm, PlacedBetResultForm

def home(request):
    """Home page view - displays value bets"""
    games = Game.objects.filter(commence_time__gte=timezone.now()).order_by('commence_time')
    sports = Sport.objects.all()
    
    # Get all distinct bookmakers from ValueBet model
    bookmakers = ValueBet.objects.values_list('bookmaker', flat=True).distinct()
    
    # Calculate stats
    total_value_bets = ValueBet.objects.count()
    high_value_count = ValueBet.objects.filter(expected_value__gt=1.05).count()
    good_value_count = ValueBet.objects.filter(expected_value__gt=1.0, expected_value__lte=1.05).count()
    avg_bet_size = ValueBet.objects.aggregate(avg_size=Avg('bet_size'))['avg_size'] or 0
    avg_bet_size = round(avg_bet_size)
    
    # Default edge threshold (can go down to 0.90 for testing)
    edge_threshold = 1.00
    
    # Check if in testing mode
    if request.GET.get('testing'):
        edge_threshold = 0.90
    
    # Apply user preferences if logged in (only for bookmaker preferences)
    if request.user.is_authenticated:
        # Get user's preferred bookmakers
        preferred_bookmakers = UserBookmakerPreference.objects.filter(
            user=request.user, is_enabled=True).values_list('bookmaker', flat=True)
        
        if preferred_bookmakers:
            # Only filter by bookmakers if the user has preferences
            games = games.filter(value_bets__bookmaker__in=preferred_bookmakers).distinct()
            
        # Use the user's edge threshold if they have one set
        try:
            edge_threshold = request.user.profile.default_edge_threshold
        except (AttributeError, UserProfile.DoesNotExist):
            pass  # Fall back to default edge threshold
    
    # Instead, we'll filter the value bets in the template context
    filtered_games = []
    for game in games:
        # Clone the game to avoid modifying the original query
        filtered_value_bets = game.value_bets.filter(expected_value__gte=edge_threshold)
        if filtered_value_bets.exists():
            # Only include games that have at least one value bet meeting the threshold
            game.filtered_value_bets = filtered_value_bets
            filtered_games.append(game)
    
    # Update the count to reflect only bets that meet the threshold
    total_value_bets = ValueBet.objects.filter(expected_value__gte=edge_threshold).count()
    
    # Get last update time
    try:
        last_update = ValueBet.objects.latest('timestamp').timestamp
    except ValueBet.DoesNotExist:
        last_update = None
    
    # Calculate counts for different thresholds for debugging
    ev_90_count = ValueBet.objects.filter(expected_value__gte=0.90).count()
    ev_95_count = ValueBet.objects.filter(expected_value__gte=0.95).count()
    ev_100_count = ValueBet.objects.filter(expected_value__gte=1.00).count()
    
    # Convert edge_threshold to percentage for template display
    edge_threshold_percent = edge_threshold * 100
    
    context = {
        'games': filtered_games,
        'sports': sports,
        'bookmakers': bookmakers,
        'total_value_bets': total_value_bets,
        'high_value_count': high_value_count,
        'good_value_count': good_value_count,
        'avg_bet_size': avg_bet_size,
        'last_update': last_update,
        'edge_threshold': edge_threshold_percent,  # Now sending as percentage
        'debug': {
            'ev_90_plus': ev_90_count,
            'ev_95_plus': ev_95_count,
            'ev_100_plus': ev_100_count,
            'threshold_used': edge_threshold
        }
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
    
    # For consistency with the home view, apply the same edge threshold
    # Default edge threshold is 1.00, but can go down to 0.90 for testing
    edge_threshold = 0.90 if request.GET.get('testing') else 1.00
    
    # If user is authenticated, use their threshold
    if request.user.is_authenticated:
        try:
            edge_threshold = request.user.profile.default_edge_threshold
        except (AttributeError, UserProfile.DoesNotExist):
            pass
    
    # Get counts for debugging
    total_bets = value_bets.count()
    ev_100_count = value_bets.filter(expected_value__gte=1.00).count()
    ev_95_count = value_bets.filter(expected_value__gte=0.95).count() - ev_100_count
    ev_90_count = value_bets.filter(expected_value__gte=0.90).count() - ev_100_count - ev_95_count
    

            
    filtered_value_bets = value_bets.filter(expected_value__gte=edge_threshold)
    
    # Calculate additional statistics
    high_value_count = filtered_value_bets.filter(expected_value__gt=1.05).count()
    
    return JsonResponse({
        'status': 'success',
        'message': f"Updated {filtered_value_bets.count()} value bets in {end_time - start_time:.2f} seconds",
        'last_update': last_update.strftime('%Y-%m-%d %H:%M:%S'),
        'count': filtered_value_bets.count(),
        'high_value_count': high_value_count,
        'debug': {
            'total_bets': total_bets,
            'ev_90_plus': ev_90_count,
            'ev_95_plus': ev_95_count,
            'ev_100_plus': ev_100_count,
            'threshold_used': edge_threshold
        }
    })

def register(request):
    if request.user.is_authenticated:
        return redirect('betting:home')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Set up initial bookmaker preferences
            bookmakers = ValueBet.objects.values_list('bookmaker', flat=True).distinct()
            for bookmaker in bookmakers:
                UserBookmakerPreference.objects.create(user=user, bookmaker=bookmaker, is_enabled=True)
            
            # Log in the user
            login(request, user)
            messages.success(request, 'Account created successfully. Welcome to ValueBet!')
            return redirect('betting:home')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'betting/register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('betting:home')
    
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect('betting:home')
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'betting/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('betting:home')

@login_required
def profile(request):
    user = request.user
    
    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, instance=user.profile)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, 'Your profile has been updated.')
            return redirect('betting:profile')
    else:
        profile_form = UserProfileForm(instance=user.profile)
    
    # Get user's bet statistics
    bet_stats = {
        'total_bets': PlacedBet.objects.filter(user=user).count(),
        'pending_bets': PlacedBet.objects.filter(user=user, status='pending').count(),
        'won_bets': PlacedBet.objects.filter(user=user, status='won').count(),
        'lost_bets': PlacedBet.objects.filter(user=user, status='lost').count(),
        'profit_loss': PlacedBet.objects.filter(user=user, status__in=['won', 'lost']).aggregate(
            total=Sum('profit_loss'))['total'] or Decimal('0.00'),
        'total_wagered': PlacedBet.objects.filter(user=user).aggregate(
            total=Sum('stake'))['total'] or Decimal('0.00'),
        'avg_odds': PlacedBet.objects.filter(user=user).aggregate(
            avg=Avg('odds'))['avg'] or 0,
    }
    
    # Calculate ROI
    if bet_stats['total_wagered'] > 0:
        bet_stats['roi'] = (bet_stats['profit_loss'] / bet_stats['total_wagered']) * 100
    else:
        bet_stats['roi'] = 0
    
    context = {
        'profile_form': profile_form,
        'bet_stats': bet_stats,
    }
    
    return render(request, 'betting/profile.html', context)

@login_required
def preferences(request):
    user = request.user
    bookmakers = list(ValueBet.objects.values_list('bookmaker', flat=True).distinct())
    
    if request.method == 'POST':
        form = BookmakerPreferenceForm(request.POST, bookmakers=bookmakers, user=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your preferences have been updated.')
            return redirect('betting:preferences')
    else:
        form = BookmakerPreferenceForm(bookmakers=bookmakers, user=user)
    
    return render(request, 'betting/preferences.html', {'form': form})

@login_required
def place_bet(request, bet_id):
    value_bet = get_object_or_404(ValueBet, id=bet_id)
    game = value_bet.game
    
    # Check if user has already placed a bet on this game
    existing_game_bet = PlacedBet.objects.filter(user=request.user, game=game).first()
    if existing_game_bet:
        messages.warning(request, f'You already have a bet on this game with {existing_game_bet.bookmaker}.')
        return redirect('betting:my_bets')
    
    # Find the best value bet for this game across all bookmakers
    best_value_bet = ValueBet.objects.filter(game=game).order_by('-expected_value').first()
    
    # If the selected bet is not the best value bet, suggest the best one instead
    if best_value_bet.id != value_bet.id:
        messages.info(request, f'A better value bet is available on {best_value_bet.bookmaker} with expected value {best_value_bet.expected_value:.3f} vs {value_bet.expected_value:.3f}.')
        value_bet = best_value_bet
    
    # Calculate stake based on user's profile
    try:
        profile = request.user.profile
        stake = value_bet.bet_size
        if profile.bankroll and profile.kelly_fraction:
            # If user has set up bankroll, use their Kelly settings
            kelly_stake = (value_bet.expected_value - 1) / (value_bet.offered_odds - 1)
            kelly_stake = Decimal(str(kelly_stake)) * profile.bankroll * Decimal(str(profile.kelly_fraction))
            stake = min(kelly_stake, profile.bankroll * Decimal('0.05'))  # Cap at 5% of bankroll
    except UserProfile.DoesNotExist:
        stake = value_bet.bet_size
    
    # Create the placed bet
    placed_bet = PlacedBet.objects.create(
        user=request.user,
        value_bet=value_bet,
        game=value_bet.game,
        bookmaker=value_bet.bookmaker,
        bet_type=value_bet.bet_type,
        odds=value_bet.offered_odds,
        stake=stake,
        expected_value=value_bet.expected_value,
        true_probability=value_bet.true_prob,
        status='pending'
    )
    
    messages.success(request, f'Bet placed successfully with {value_bet.bookmaker} on {value_bet.bet_type}!')
    return redirect('betting:my_bets')

@login_required
def my_bets(request):
    # Get all user's bets
    placed_bets = PlacedBet.objects.filter(user=request.user).order_by('-placed_at')
    
    # Calculate summary statistics
    summary = {
        'total_bets': placed_bets.count(),
        'pending_bets': placed_bets.filter(status='pending').count(),
        'won_bets': placed_bets.filter(status='won').count(),
        'lost_bets': placed_bets.filter(status='lost').count(),
        'profit_loss': placed_bets.filter(status__in=['won', 'lost']).aggregate(
            total=Sum('profit_loss'))['total'] or Decimal('0.00'),
        'total_wagered': placed_bets.aggregate(total=Sum('stake'))['total'] or Decimal('0.00'),
    }
    
    # Calculate ROI
    if summary['total_wagered'] > 0:
        summary['roi'] = (summary['profit_loss'] / summary['total_wagered']) * 100
    else:
        summary['roi'] = 0
    
    # Group bets by status
    pending_bets = placed_bets.filter(status='pending')
    settled_bets = placed_bets.exclude(status='pending')
    
    context = {
        'pending_bets': pending_bets,
        'settled_bets': settled_bets,
        'summary': summary,
    }
    
    return render(request, 'betting/my_bets.html', context)

@login_required
def update_bet_result(request, bet_id):
    placed_bet = get_object_or_404(PlacedBet, id=bet_id, user=request.user)
    
    if request.method == 'POST':
        form = PlacedBetResultForm(request.POST, instance=placed_bet)
        if form.is_valid():
            bet = form.save(commit=False)
            bet.result_updated_at = timezone.now()
            bet.calculate_profit_loss()
            bet.save()
            messages.success(request, 'Bet result updated successfully.')
            return redirect('betting:my_bets')
    else:
        form = PlacedBetResultForm(instance=placed_bet)
    
    context = {
        'form': form,
        'bet': placed_bet
    }
    
    return render(request, 'betting/update_bet.html', context)

@login_required
def bet_history(request):
    # Get date range for filtering
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    # Get all settled bets within the date range
    bets = PlacedBet.objects.filter(
        user=request.user,
        status__in=['won', 'lost', 'push'],
        placed_at__gte=start_date
    ).order_by('-placed_at')
    
    # Calculate overall statistics
    stats = {
        'total_bets': bets.count(),
        'won_bets': bets.filter(status='won').count(),
        'lost_bets': bets.filter(status='lost').count(),
        'profit_loss': bets.aggregate(total=Sum('profit_loss'))['total'] or Decimal('0.00'),
        'total_wagered': bets.aggregate(total=Sum('stake'))['total'] or Decimal('0.00'),
    }
    
    # Calculate win rate and ROI
    if stats['total_bets'] > 0:
        stats['win_rate'] = (stats['won_bets'] / stats['total_bets']) * 100
    else:
        stats['win_rate'] = 0
    
    if stats['total_wagered'] > 0:
        stats['roi'] = (stats['profit_loss'] / stats['total_wagered']) * 100
    else:
        stats['roi'] = 0
    
    # Group bets by bookmaker for bookmaker performance
    bookmaker_stats = []
    bookmakers = bets.values_list('bookmaker', flat=True).distinct()
    
    for bookmaker in bookmakers:
        bookmaker_bets = bets.filter(bookmaker=bookmaker)
        bookmaker_stats.append({
            'name': bookmaker,
            'total_bets': bookmaker_bets.count(),
            'won_bets': bookmaker_bets.filter(status='won').count(),
            'profit_loss': bookmaker_bets.aggregate(total=Sum('profit_loss'))['total'] or Decimal('0.00'),
            'total_wagered': bookmaker_bets.aggregate(total=Sum('stake'))['total'] or Decimal('0.00'),
        })
    
    context = {
        'bets': bets,
        'stats': stats,
        'bookmaker_stats': bookmaker_stats,
        'days': days,
    }
    
    return render(request, 'betting/bet_history.html', context)

@login_required
def delete_bet(request, bet_id):
    bet = get_object_or_404(PlacedBet, id=bet_id, user=request.user)
    
    if request.method == 'POST':
        bet.delete()
        messages.success(request, 'Bet deleted successfully.')
        return redirect('betting:my_bets')
    
    return render(request, 'betting/delete_bet.html', {'bet': bet})

@login_required
def master_pnl_tracker(request):
    """View for the master PNL tracker to analyze the performance of all value bets"""
    # Get date range for filtering (default to last 30 days)
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    # Get status filter (default to all)
    status_filter = request.GET.get('status', 'all')
    
    # Get bookmaker filter (default to all)
    bookmaker_filter = request.GET.get('bookmaker', 'all')
    
    # Base query for all value bet trackers
    trackers = ValueBetTracker.objects.filter(identified_at__gte=start_date)
    
    # Apply filters
    if status_filter != 'all':
        trackers = trackers.filter(result=status_filter)
    
    if bookmaker_filter != 'all':
        trackers = trackers.filter(bookmaker=bookmaker_filter)
    
    # Calculate overall statistics
    stats = {
        'total_bets': trackers.count(),
        'settled_bets': trackers.exclude(result='pending').count(),
        'pending_bets': trackers.filter(result='pending').count(),
        'won_bets': trackers.filter(result='won').count(),
        'lost_bets': trackers.filter(result='lost').count(),
        'push_bets': trackers.filter(result='push').count(),
        'theoretical_profit': trackers.filter(result__in=['won', 'lost', 'push']).aggregate(
            total=Sum('theoretical_profit'))['total'] or Decimal('0.00'),
        'total_wagered': trackers.filter(result__in=['won', 'lost', 'push']).aggregate(
            total=Sum('bet_size'))['total'] or Decimal('0.00'),
        'avg_odds': trackers.aggregate(avg=Avg('odds'))['avg'] or 0,
        'avg_ev': trackers.aggregate(avg=Avg('expected_value'))['avg'] or 0,
    }
    
    # Calculate win rate and ROI
    if stats['settled_bets'] > 0:
        stats['win_rate'] = (stats['won_bets'] / stats['settled_bets']) * 100
    else:
        stats['win_rate'] = 0
    
    if stats['total_wagered'] > 0:
        stats['roi'] = (stats['theoretical_profit'] / stats['total_wagered']) * 100
    else:
        stats['roi'] = 0
    
    # Calculate expected win rate based on true probability
    expected_wins = trackers.filter(result__in=['won', 'lost']).aggregate(
        expected=Sum(F('true_probability')))['expected'] or 0
    
    actual_results = trackers.filter(result__in=['won', 'lost']).count()
    
    if actual_results > 0:
        stats['expected_win_rate'] = (expected_wins / actual_results) * 100
        stats['edge_realization'] = (stats['win_rate'] / stats['expected_win_rate']) * 100 if stats['expected_win_rate'] > 0 else 0
    else:
        stats['expected_win_rate'] = 0
        stats['edge_realization'] = 0
    
    # Get all unique bookmakers from ValueBetTracker
    all_bookmakers = ValueBetTracker.objects.values_list('bookmaker', flat=True).distinct()
    
    # Group by bookmaker for performance comparison
    bookmaker_stats = []
    for bookmaker in all_bookmakers:
        bookmaker_trackers = trackers.filter(bookmaker=bookmaker, result__in=['won', 'lost', 'push'])
        bk_won = bookmaker_trackers.filter(result='won').count()
        bk_settled = bookmaker_trackers.count()
        
        bookmaker_stats.append({
            'name': bookmaker,
            'total_bets': bookmaker_trackers.count(),
            'won_bets': bk_won,
            'win_rate': (bk_won / bk_settled) * 100 if bk_settled > 0 else 0,
            'profit_loss': bookmaker_trackers.aggregate(total=Sum('theoretical_profit'))['total'] or Decimal('0.00'),
            'total_wagered': bookmaker_trackers.aggregate(total=Sum('bet_size'))['total'] or Decimal('0.00'),
            'roi': ((bookmaker_trackers.aggregate(total=Sum('theoretical_profit'))['total'] or Decimal('0.00')) / 
                   (bookmaker_trackers.aggregate(total=Sum('bet_size'))['total'] or Decimal('1.00'))) * 100,
            'avg_ev': bookmaker_trackers.aggregate(avg=Avg('expected_value'))['avg'] or 0,
        })
    
    # Sort bookmakers by profit or ROI
    sort_by = request.GET.get('sort', 'profit')
    if sort_by == 'roi':
        bookmaker_stats.sort(key=lambda x: x['roi'], reverse=True)
    else:
        bookmaker_stats.sort(key=lambda x: x['profit_loss'], reverse=True)
    
    # Pagination for the trackers list
    page = request.GET.get('page', 1)
    paginator = Paginator(trackers.order_by('-identified_at'), 50)
    
    try:
        trackers_page = paginator.page(page)
    except PageNotAnInteger:
        trackers_page = paginator.page(1)
    except EmptyPage:
        trackers_page = paginator.page(paginator.num_pages)
    
    context = {
        'trackers': trackers_page,
        'stats': stats,
        'bookmaker_stats': bookmaker_stats,
        'all_bookmakers': all_bookmakers,
        'days': days,
        'status_filter': status_filter,
        'bookmaker_filter': bookmaker_filter,
        'sort_by': sort_by,
    }
    
    return render(request, 'betting/master_pnl.html', context)

@login_required
def update_tracker_results(request):
    """Batch update results for value bet trackers"""
    if request.method == 'POST':
        game_id = request.POST.get('game_id')
        result = request.POST.get('result')
        
        if game_id and result:
            # Update all trackers for this game
            trackers = ValueBetTracker.objects.filter(game_id=game_id, result='pending')
            
            # Process results based on bet type and game outcome
            for tracker in trackers:
                bet_result = calculate_bet_result(tracker.bet_type, result)
                tracker.result = bet_result
                tracker.result_updated_at = timezone.now()
                tracker.save()
            
            messages.success(request, f'Updated results for {trackers.count()} value bets.')
        
        return redirect('betting:master_pnl_tracker')
    
    # Show form to select game and result
    games = Game.objects.filter(
        commence_time__lt=timezone.now(),  # Games in the past
        tracker__result='pending',  # With pending bet trackers
    ).distinct().order_by('-commence_time')
    
    context = {
        'games': games,
    }
    
    return render(request, 'betting/update_tracker_results.html', context)

def calculate_bet_result(bet_type, game_result):
    """Helper function to determine bet result based on game outcome"""
    # This is a simplified example - would need logic specific to your bet types
    if bet_type.startswith('home') and game_result == 'home_win':
        return 'won'
    elif bet_type.startswith('away') and game_result == 'away_win':
        return 'won'
    elif bet_type.startswith('draw') and game_result == 'draw':
        return 'won'
    elif bet_type.startswith('over') and game_result == 'over':
        return 'won'
    elif bet_type.startswith('under') and game_result == 'under':
        return 'won'
    elif game_result == 'cancelled':
        return 'cancelled'
    elif game_result == 'push':
        return 'push'
    else:
        return 'lost'

@login_required
def save_edge_threshold(request):
    """Save the user's edge threshold preference"""
    if request.method == 'POST':
        try:
            threshold = float(request.POST.get('threshold', 1.00))
            # Ensure threshold is within valid range (0.90 to 1.50)
            threshold = max(0.90, min(threshold, 1.50))
            
            # Save to user profile
            profile = request.user.profile
            profile.default_edge_threshold = threshold
            profile.save()
            
            # Return percentage value in the success message
            threshold_percent = threshold * 100
            return JsonResponse({
                'status': 'success',
                'message': f'Edge threshold updated to {threshold_percent:.0f}%'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)
