from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='journal_dashboard'),
    path('entries/', views.entry_list, name='entry_list'),
    path('entries/new/', views.entry_create, name='entry_create'),
    path('entries/<int:pk>/', views.entry_detail, name='entry_detail'),
    path('entries/<int:pk>/edit/', views.entry_edit, name='entry_edit'),
    path('entries/<int:pk>/delete/', views.entry_delete, name='entry_delete'),
    path('medications/', views.medication_list, name='medication_list'),
    path('medications/new/', views.medication_create, name='medication_create'),
    path('vitals/', views.vitals_list, name='vitals_list'),
    path('vitals/new/', views.vitals_create, name='vitals_create'),
    path('export/', views.export_journal, name='journal_export'),
]
