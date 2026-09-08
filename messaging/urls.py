from django.urls import path
from . import views

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('conversation/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path('conversation/<int:conversation_id>/poll/', views.conversation_poll, name='conversation_poll'),
    path('conversation/<int:conversation_id>/send/', views.conversation_send_ajax, name='conversation_send_ajax'),
    path('start/<int:user_id>/', views.start_conversation, name='start_conversation'),
]
