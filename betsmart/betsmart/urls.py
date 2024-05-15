# betsmart/urls.py
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('stats/', include('stats.urls')),
    path('', lambda request: redirect('stats/', permanent=False)),  # Redirect root to /stats/
]
