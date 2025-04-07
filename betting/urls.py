from django.urls import path
from . import views

app_name = 'betting'

urlpatterns = [
    path('', views.home, name='home'),
    path('refresh/', views.refresh_value_bets, name='refresh_value_bets'),
    
    # Authentication routes
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # User profile routes
    path('profile/', views.profile, name='profile'),
    path('preferences/', views.preferences, name='preferences'),
    
    # Bet tracking routes
    path('place-bet/<uuid:bet_id>/', views.place_bet, name='place_bet'),
    path('my-bets/', views.my_bets, name='my_bets'),
    path('bet/<int:bet_id>/update/', views.update_bet_result, name='update_bet_result'),
    path('bet/<int:bet_id>/delete/', views.delete_bet, name='delete_bet'),
    path('bet-history/', views.bet_history, name='bet_history'),
    
    # Master PNL tracker routes
    path('master-pnl/', views.master_pnl_tracker, name='master_pnl_tracker'),
    path('update-tracker-results/', views.update_tracker_results, name='update_tracker_results'),
    
    # User preferences
    path('save-edge-threshold/', views.save_edge_threshold, name='save_edge_threshold'),
] 