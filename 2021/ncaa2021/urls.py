from django.contrib import admin
from django.urls import path
from bracketeering.views import *

urlpatterns = [
    path('admin/', admin.site.urls),
    path('bracket/<int:bid>/', BracketView.as_view(), name='bracket'),
    path('owner/<str:name>/', OwnerView.as_view(), name='owner'),
    path('game/<int:gid>/', GameView.as_view(), name='game'),
    path('team/<str:name>/', TeamView.as_view(), name='team'),
    path('about/', AboutView.as_view(), name='about'),
    path('draft/', DraftView.as_view(), name='draft'),
    path('', MainView.as_view(), name='main'),
]
