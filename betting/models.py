from django.db import models
import uuid

class Sport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name

class Game(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sport = models.ForeignKey(Sport, on_delete=models.CASCADE, related_name='games')
    title = models.CharField(max_length=255)
    home_team = models.CharField(max_length=100)
    away_team = models.CharField(max_length=100)
    commence_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title

class ValueBet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='value_bets')
    bookmaker = models.CharField(max_length=100)
    bet_type = models.CharField(max_length=50)
    true_prob = models.FloatField()
    offered_odds = models.FloatField()
    expected_value = models.FloatField()
    bet_size = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-expected_value']
    
    def __str__(self):
        return f"{self.game.title} - {self.bookmaker} - {self.bet_type}"
        
    @property
    def true_prob_percent(self):
        return f"{self.true_prob:.2%}"
        
    @property
    def is_high_value(self):
        return self.expected_value > 1.05
        
    @property
    def is_good_value(self):
        return 1.0 < self.expected_value <= 1.05
