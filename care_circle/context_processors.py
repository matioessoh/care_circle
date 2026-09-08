def user_role(request):
    """Injecte le r�le de l'utilisateur (patient / m�decin / admin) pour adapter le layout de navigation."""
    user = request.user
    role = 'guest'
    if user.is_authenticated:
        if getattr(user, 'is_superuser', False):
            role = 'admin'
        elif getattr(user, 'doctor_profile', None):
            role = 'doctor'
        else:
            role = 'patient'
    return {
        'user_role': role,
        'is_doctor_role': role == 'doctor',
        'is_admin_role': role == 'admin',
        'is_patient_role': role == 'patient',
    }


def notifications(request):
    """Injecte les notifications non lues et les dernières notifications de l'utilisateur."""
    if not request.user.is_authenticated:
        return {'unread_notifications_count': 0, 'recent_notifications': []}
    qs = request.user.notifications.all()
    return {
        'unread_notifications_count': qs.filter(is_read=False).count(),
        'recent_notifications': qs[:5],
    }
