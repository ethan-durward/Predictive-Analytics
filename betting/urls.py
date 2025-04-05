from django.urls import path
from . import views

app_name = 'betting'

urlpatterns = [
    path('', views.home, name='home'),
    path('refresh/', views.refresh_value_bets, name='refresh'),
] 