from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib import messages
from django.db.models import Q
from .models import PatientProfile, Connection


def home(request):
    return render(request, 'home.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Ce nom d\'utilisateur est déjà pris.')
        elif password != password2:
            messages.error(request, 'Les mots de passe ne correspondent pas.')
        elif len(password) < 8:
            messages.error(request, 'Le mot de passe doit contenir au moins 8 caractères.')
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            login(request, user)
            messages.success(request, 'Inscription réussie ! Bienvenue.')
            return redirect('profile')
    return render(request, 'registration/register.html')


@login_required
def profile(request, username=None):
    if username:
        user = get_object_or_404(User, username=username)
    else:
        user = request.user
    profile, created = PatientProfile.objects.get_or_create(user=user)
    return render(request, 'patients/profile.html', {
        'profile_user': user,
        'profile': profile,
        'is_self': (request.user.is_authenticated and request.user == user),
    })


@login_required
def edit_profile(request):
    profile, created = PatientProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        profile.phone = request.POST.get('phone', '')
        profile.address = request.POST.get('address', '')
        profile.date_of_birth = request.POST.get('date_of_birth') or None
        profile.gender = request.POST.get('gender', '')
        profile.blood_type = request.POST.get('blood_type', '')
        profile.allergies = request.POST.get('allergies', '')
        profile.medical_conditions = request.POST.get('medical_conditions', '')
        profile.emergency_contact = request.POST.get('emergency_contact', '')
        profile.emergency_phone = request.POST.get('emergency_phone', '')
        profile.save()
        return redirect('profile')
    return render(request, 'patients/edit_profile.html', {'profile': profile})


@login_required
def members(request):
    users = (User.objects
             .exclude(id=request.user.id)
             .exclude(is_superuser=True)
             .exclude(is_staff=True)
             .select_related('patient_profile'))
    connections_sent = Connection.objects.filter(from_user=request.user).values_list('to_user_id', flat=True)
    connections_received = Connection.objects.filter(to_user=request.user).values_list('from_user_id', flat=True)
    connected_ids = set(connections_sent) | set(connections_received)
    return render(request, 'patients/members.html', {
        'members': users,
        'connected_ids': connected_ids,
    })


@login_required
def send_connection(request, user_id):
    to_user = get_object_or_404(User, id=user_id)
    Connection.objects.get_or_create(from_user=request.user, to_user=to_user)
    return redirect('members')


@login_required
def accept_connection(request, connection_id):
    connection = get_object_or_404(Connection, id=connection_id, to_user=request.user)
    connection.status = 'accepted'
    connection.save()
    return redirect('members')


@login_required
def my_connections(request):
    sent = Connection.objects.filter(from_user=request.user, status='pending')
    received = Connection.objects.filter(to_user=request.user, status='pending')
    accepted = Connection.objects.filter(
        Q(from_user=request.user) | Q(to_user=request.user),
        status='accepted'
    )
    accepted = [
        (c, c.to_user if c.from_user == request.user else c.from_user)
        for c in accepted
    ]
    return render(request, 'patients/connections.html', {
        'sent': sent,
        'received': received,
        'accepted_pairs': accepted,
    })
