from django.urls import path
from . import views

urlpatterns = [
    path('', views.resources_home, name='resources_home'),
    path('articles/', views.article_list, name='resources_articles'),
    path('articles/<slug:slug>/', views.article_detail, name='resource_article_detail'),
    path('faq/', views.faq, name='resources_faq'),
]