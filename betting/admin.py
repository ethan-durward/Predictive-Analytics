from django.contrib import admin
from .models import Sport, Game, ValueBet

@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    list_display = ('name', 'key')
    search_fields = ('name', 'key')

@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('title', 'sport', 'home_team', 'away_team', 'commence_time')
    list_filter = ('sport', 'commence_time')
    search_fields = ('title', 'home_team', 'away_team')

@admin.register(ValueBet)
class ValueBetAdmin(admin.ModelAdmin):
    list_display = ('game', 'bookmaker', 'bet_type', 'true_prob', 'offered_odds', 'expected_value', 'bet_size')
    list_filter = ('bookmaker', 'bet_type')
    search_fields = ('game__title', 'bookmaker')
