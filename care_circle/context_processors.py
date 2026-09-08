def user_role(request):
    """Injecte le rôle de l'utilisateur (patient / médecin / admin) pour adapter le layout de navigation."""
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
