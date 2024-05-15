# stats/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.player_stats, name='player_stats'),
]
