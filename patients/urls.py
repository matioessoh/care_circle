from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/<str:username>/', views.profile, name='user_profile'),
    path('members/', views.members, name='members'),
    path('members/connect/<int:user_id>/', views.send_connection, name='send_connection'),
    path('connections/', views.my_connections, name='my_connections'),
    path('connections/accept/<int:connection_id>/', views.accept_connection, name='accept_connection'),
]
