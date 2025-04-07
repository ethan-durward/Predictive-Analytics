from django.db import models
import uuid
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

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
        
    @property
    def true_probability(self):
        return self.true_prob

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    default_edge_threshold = models.FloatField(default=1.00)  # Default to 0% edge
    bankroll = models.DecimalField(max_digits=10, decimal_places=2, default=1000.00)
    kelly_fraction = models.FloatField(default=0.5)  # Half Kelly by default
    
    def __str__(self):
        return f"{self.user.username}'s Profile"

class UserBookmakerPreference(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmaker_preferences')
    bookmaker = models.CharField(max_length=100)
    is_enabled = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('user', 'bookmaker')
    
    def __str__(self):
        return f"{self.user.username} - {self.bookmaker}"

class PlacedBet(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('won', 'Won'),
        ('lost', 'Lost'),
        ('push', 'Push'),
        ('cancelled', 'Cancelled'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='placed_bets')
    value_bet = models.ForeignKey('ValueBet', on_delete=models.SET_NULL, null=True, related_name='placed_bets')
    game = models.ForeignKey('Game', on_delete=models.SET_NULL, null=True)
    bookmaker = models.CharField(max_length=100)
    bet_type = models.CharField(max_length=100)  # home, away, over, under, etc.
    odds = models.FloatField()
    stake = models.DecimalField(max_digits=10, decimal_places=2)
    expected_value = models.FloatField()
    true_probability = models.FloatField()
    placed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result_updated_at = models.DateTimeField(null=True, blank=True)
    profit_loss = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.bookmaker} - {self.bet_type} - {self.status}"

    def calculate_profit_loss(self):
        if self.status == 'won':
            self.profit_loss = self.stake * (self.odds - 1)
        elif self.status == 'lost':
            self.profit_loss = -self.stake
        elif self.status == 'push':
            self.profit_loss = 0
        else:
            self.profit_loss = None
        return self.profit_loss
    
    def save(self, *args, **kwargs):
        if self.status in ['won', 'lost', 'push'] and self.profit_loss is None:
            self.calculate_profit_loss()
        super().save(*args, **kwargs)

class ValueBetTracker(models.Model):
    RESULT_CHOICES = (
        ('pending', 'Pending'),
        ('won', 'Won'),
        ('lost', 'Lost'),
        ('push', 'Push'),
        ('cancelled', 'Cancelled'),
    )
    
    value_bet = models.OneToOneField(ValueBet, on_delete=models.CASCADE, related_name='tracker')
    game = models.ForeignKey(Game, on_delete=models.SET_NULL, null=True)
    bookmaker = models.CharField(max_length=100)
    bet_type = models.CharField(max_length=100)
    odds = models.FloatField()
    true_probability = models.FloatField()
    expected_value = models.FloatField()
    bet_size = models.DecimalField(max_digits=10, decimal_places=2)
    theoretical_profit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default='pending')
    result_updated_at = models.DateTimeField(null=True, blank=True)
    identified_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-identified_at']
    
    def __str__(self):
        return f"{self.game.title} - {self.bookmaker} - {self.bet_type} - {self.result}"
    
    def calculate_theoretical_profit(self):
        if self.result == 'won':
            return self.bet_size * (self.odds - 1)
        elif self.result == 'lost':
            return -self.bet_size
        elif self.result == 'push':
            return 0
        else:
            return None
    
    def save(self, *args, **kwargs):
        if self.result in ['won', 'lost', 'push']:
            self.theoretical_profit = self.calculate_theoretical_profit()
        super().save(*args, **kwargs)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if not hasattr(instance, 'profile'):
        UserProfile.objects.create(user=instance)
    instance.profile.save()

@receiver(post_save, sender=ValueBet)
def create_value_bet_tracker(sender, instance, created, **kwargs):
    """Create a ValueBetTracker entry whenever a new ValueBet is created"""
    if created:
        ValueBetTracker.objects.create(
            value_bet=instance,
            game=instance.game,
            bookmaker=instance.bookmaker,
            bet_type=instance.bet_type,
            odds=instance.offered_odds,
            true_probability=instance.true_prob,
            expected_value=instance.expected_value,
            bet_size=instance.bet_size,
            result='pending'
        )
