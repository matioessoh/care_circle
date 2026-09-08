from django.urls import path
from . import views

urlpatterns = [
    path('', views.appointment_list, name='appointment_list'),
    path('dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    path('new/', views.appointment_create, name='appointment_create'),
    path('new/for-patient/', views.appointment_create_for_patient, name='appointment_create_for_patient'),
    path('doctors/', views.doctor_list, name='doctor_list'),
    path('doctors/<int:pk>/', views.doctor_detail, name='doctor_detail'),
    path('doctors/<int:pk>/appointments/', views.doctor_appointments, name='doctor_appointments'),
    path('patients/<int:patient_id>/record/', views.patient_medical_record, name='patient_medical_record'),
    path('patients/<int:patient_id>/journal/', views.doctor_view_journal, name='doctor_view_journal'),
    path('slots/', views.my_slots, name='my_slots'),
    path('slots/add/', views.add_slot, name='add_slot'),
    path('<int:pk>/', views.appointment_detail, name='appointment_detail'),
    path('<int:pk>/edit/', views.appointment_edit, name='appointment_edit'),
    path('<int:pk>/cancel/', views.appointment_cancel, name='appointment_cancel'),
    path('<int:pk>/status/', views.appointment_update_status, name='appointment_update_status'),
    path('<int:pk>/consult-notes/', views.appointment_consult_notes, name='appointment_consult_notes'),
]
