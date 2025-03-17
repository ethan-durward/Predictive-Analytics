from django.urls import path
from . import views

urlpatterns = [
    path('player_stats/', views.player_stats, name='player_stats'),
    path('team_stats/', views.team_stats, name='team_stats'),
    path('probabilities/', views.probabilities, name='probabilities'),
    path('smart_bets/', views.smart_bets, name='smart_bets'),
]
