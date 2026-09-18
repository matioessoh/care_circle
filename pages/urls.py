from django.urls import path
from . import views

urlpatterns = [
    path('a-propos/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('confidentialite/', views.privacy, name='privacy'),
    path('conditions-utilisation/', views.terms, name='terms'),
]