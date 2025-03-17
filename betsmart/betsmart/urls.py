from django.contrib import admin
from django.urls import path, include
from stats import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.player_stats, name='home'),  # Default to player_stats for the base URL
    path('stats/', include('stats.urls'))
]
