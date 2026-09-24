from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils.dateparse import parse_date, parse_time
from django.contrib.auth.decorators import user_passes_test
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from django.http import JsonResponse
from django.utils.crypto import get_random_string
from django.contrib.auth import login as auth_login
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from datetime import date, timedelta
import logging
import re

from .models import Appointment, Doctor, AvailabilitySlot
from patients.models import PatientProfile
from forum.models import Community, CommunityMembership


logger = logging.getLogger(__name__)


def _get_doctor(user):
    return getattr(user, 'doctor_profile', None)


def _is_doctor(user):
    return bool(getattr(user, 'doctor_profile', None))


def doctor_list(request):
    doctors = (Doctor.objects
               .filter(user__is_active=True)
               .exclude(user__is_superuser=True)
               .exclude(user__is_staff=True)
               .select_related('user'))
    return render(request, 'appointments/doctor_list.html', {'doctors': doctors})


def doctor_detail(request, pk):
    doctor = get_object_or_404(Doctor, pk=pk)
    slots = AvailabilitySlot.objects.filter(
        doctor=doctor, is_booked=False, date__gte=date.today()
    ).select_related()
    return render(request, 'appointments/doctor_detail.html', {'doctor': doctor, 'slots': slots})


def doctor_appointments(request, pk):
    doctor = get_object_or_404(Doctor, pk=pk)
    appointments = doctor.appointments.select_related('patient').order_by('-date', '-time')
    return render(request, 'appointments/doctor_appointments.html', {
        'doctor': doctor,
        'appointments': appointments,
    })


def appointment_create_anonymous(request):
    """Prise de rendez-vous SANS compte : le patient laisse ses coordonnées.
    Le compte ne sera créé qu'à l'issue de la consultation, par le médecin."""
    if request.user.is_authenticated:
        return redirect('appointment_create')
    if request.method == 'POST':
        doctor_id = request.POST.get('doctor')
        slot_id = request.POST.get('slot')
        patient_name = request.POST.get('patient_name', '').strip()
        patient_email = request.POST.get('patient_email', '').strip()
        patient_phone = request.POST.get('patient_phone', '').strip()
        title = request.POST.get('title', '').strip()
        date_str = request.POST.get('date') or ''
        time_str = request.POST.get('time') or ''
        date_val = parse_date(date_str) if date_str else None
        time_val = parse_time(time_str) if time_str else None

        doctor = Doctor.objects.filter(id=doctor_id).first() if doctor_id else None
        slot = AvailabilitySlot.objects.filter(id=slot_id, is_booked=False).first() if slot_id else None
        if slot:
            slot.is_booked = True
            slot.save()
            date_val = slot.date
            time_val = slot.start_time

        if not patient_name or not patient_email:
            messages.error(request, 'Veuillez indiquer votre nom complet et votre email.')
            return redirect('appointment_create_anonymous')
        if not doctor or not date_val or not time_val:
            messages.error(request, 'Veuillez choisir un médecin, une date et une heure.')
            return redirect('appointment_create_anonymous')

        if not title:
            title = f"Consultation {patient_name}"

        appointment = Appointment.objects.create(
            patient=None,
            patient_name=patient_name,
            patient_email=patient_email,
            patient_phone=patient_phone,
            doctor=doctor,
            slot=slot,
            title=title,
            description=request.POST.get('description', ''),
            date=date_val,
            time=time_val,
            location=request.POST.get('location', ''),
            status='pending',
        )
        # Email au médecin
        if doctor and doctor.user.email:
            try:
                send_mail(
                    subject=f'Nouvelle demande de rendez-vous : {title}',
                    message=(
                        f"Bonjour Dr {doctor.user.get_full_name() or doctor.user.username},\n\n"
                        f"Une demande de rendez-vous a été réservée sur Care Circle :\n"
                        f"  Patient : {patient_name}\n"
                        f"  Email : {patient_email}\n"
                        f"  Téléphone : {patient_phone or '—'}\n"
                        f"  Date : {date_val.strftime('%d/%m/%Y')}\n"
                        f"  Heure : {time_val.strftime('%H:%M')}\n"
                        f"  Motif : {title}\n\n"
                        "Ce patient n'a pas encore de compte : après la consultation, vous pourrez "
                        "créer son compte et lui envoyer un lien de connexion depuis ce rendez-vous."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[doctor.user.email],
                    fail_silently=True,
                )
            except Exception:
                logger.exception("Échec envoi notification médecin RDV anonyme")
        messages.success(
            request,
            'Votre demande de rendez-vous a bien été envoyée. Vous recevrez un email de confirmation. '
            'Votre compte vous sera remis par le médecin à l\'issue de la consultation.',
        )
        return redirect('appointment_create_anonymous')
    doctors = (Doctor.objects
               .filter(is_available=True)
               .exclude(user__is_superuser=True)
               .exclude(user__is_staff=True)
               .select_related('user'))
    return render(request, 'appointments/create_anonymous.html', {'doctors': doctors})


def doctor_slots_api(request, pk):
    """API AJAX : créneaux libres d'un médecin pour les 30 prochains jours."""
    doctor = get_object_or_404(Doctor, pk=pk)
    slots = AvailabilitySlot.objects.filter(
        doctor=doctor,
        is_booked=False,
        date__gte=date.today(),
        date__lte=date.today() + timedelta(days=30),
    ).order_by('date', 'start_time')
    return JsonResponse({
        'slots': [
            {
                'id': slot.id,
                'date': slot.date.strftime('%Y-%m-%d'),
                'start_time': slot.start_time.strftime('%H:%M'),
                'end_time': slot.end_time.strftime('%H:%M'),
            }
            for slot in slots
        ]
    })


@login_required
def appointment_list(request):
    doctor = _get_doctor(request.user)
    if doctor:
        appointments = doctor.appointments.select_related('patient')
    else:
        appointments = Appointment.objects.filter(patient=request.user).select_related('doctor')
    status_filter = request.GET.get('status')
    if status_filter:
        appointments = appointments.filter(status=status_filter)
    return render(request, 'appointments/list.html', {
        'appointments': appointments,
        'is_doctor': bool(doctor),
        'current_status': status_filter,
    })


@login_required
def appointment_detail(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    doctor = _get_doctor(request.user)
    is_doctor = bool(doctor and doctor == appointment.doctor)
    return render(request, 'appointments/detail.html', {
        'appointment': appointment,
        'is_doctor': is_doctor,
    })


@user_passes_test(_is_doctor, login_url='home')
def doctor_dashboard(request):
    """Tableau de bord du médecin : RDV du jour, à venir, demandes en attente, patients."""
    doctor = _get_doctor(request.user)
    today = date.today()
    todays = doctor.appointments.filter(date=today).exclude(status='cancelled').select_related('patient').order_by('time')
    upcoming = doctor.appointments.filter(date__gt=today, status__in=['pending', 'confirmed']).select_related('patient').order_by('date', 'time')[:10]
    pending = doctor.appointments.filter(status='pending').select_related('patient').order_by('date', 'time')
    no_account = (doctor.appointments
                  .filter(patient__isnull=True)
                  .exclude(status='cancelled')
                  .order_by('date', 'time'))
    all_appointments = doctor.appointments.filter(status__in=['pending', 'confirmed', 'completed'])
    patients = (User.objects
                .filter(patient_appointments__doctor=doctor)
                .distinct()
                .exclude(is_superuser=True)
                .exclude(is_staff=True)
                .select_related('patient_profile'))
    return render(request, 'appointments/doctor_dashboard.html', {
        'doctor': doctor,
        'todays': todays,
        'upcoming': upcoming,
        'pending': pending,
        'patients': patients,
        'all_count': all_appointments.count(),
        'no_account': no_account,
    })


@user_passes_test(_is_doctor, login_url='home')
def appointment_update_status(request, pk):
    """Le médecin confirme/refuse/termine un rendez-vous."""
    appointment = get_object_or_404(Appointment, pk=pk, doctor=_get_doctor(request.user))
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in [s[0] for s in Appointment.STATUS_CHOICES]:
            appointment.status = new_status
            appointment.save()
            if new_status == 'cancelled' and appointment.slot:
                appointment.slot.is_booked = False
                appointment.slot.save()
            labels = dict(Appointment.STATUS_CHOICES)
            messages.success(request, f"Rendez-vous « {appointment.title} » : {labels.get(new_status)}.")
            if new_status in ('confirmed', 'cancelled'):
                recipient = getattr(appointment.patient, 'email', None) or appointment.patient_email
                if recipient:
                    patient_label = ''
                    if appointment.patient:
                        patient_label = appointment.patient.get_full_name() or appointment.patient.username
                    elif appointment.patient_name:
                        patient_label = appointment.patient_name
                    try:
                        send_mail(
                            subject="Votre rendez-vous a été " + ("confirmé" if new_status == 'confirmed' else "annulé"),
                            message=(
                                f"Bonjour {patient_label or 'cher patient'},\n\n"
                                f"Le Dr {appointment.doctor.user.get_full_name() or appointment.doctor.user.username} "
                                f"a {('confirmé' if new_status == 'confirmed' else 'annulé')} votre rendez-vous :\n"
                                f"  Date : {appointment.date.strftime('%d/%m/%Y')}\n"
                                f"  Heure : {appointment.time.strftime('%H:%M') if appointment.time else '—'}\n"
                                f"  Motif : {appointment.title}\n\n"
                                "Merci de vous présenter au cabinet avec une pièce d'identité.\n"
                                "L'équipe CareCircle."
                            ),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[recipient],
                            fail_silently=True,
                        )
                    except Exception:
                        logger.exception("Échec envoi notification patient RDV %s", appointment.pk)
    return redirect('appointment_detail', pk=pk)


@user_passes_test(_is_doctor, login_url='home')
def appointment_consult_notes(request, pk):
    """Le médecin ajoute ses notes de consultation au dossier patient."""
    appointment = get_object_or_404(Appointment, pk=pk, doctor=_get_doctor(request.user))
    if request.method == 'POST':
        appointment.doctor_notes = request.POST.get('doctor_notes', '')
        if request.POST.get('mark_completed') == 'on' and appointment.status != 'cancelled':
            appointment.status = 'completed'
        appointment.save()
        messages.success(request, 'Notes de consultation enregistrées.')
    return redirect('appointment_detail', pk=pk)


def _unique_username(base):
    base = re.sub(r'[^a-zA-Z0-9_.]', '', base or 'patient')[:12] or 'patient'
    username = base
    n = 1
    while User.objects.filter(username=username).exists():
        n += 1
        username = f"{base}_{n}"
    return username


def _split_name(full_name):
    parts = full_name.split()
    first = parts[0] if parts else ''
    last = ' '.join(parts[1:])
    return first, last


def _patient_login_link(request, user, appointment):
    """Lien d'activation à usage unique : valable 24 h (PASSWORD_RESET_TIMEOUT),
    invalidé dès que le patient a choisi son mot de passe."""
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return request.build_absolute_uri(reverse('patient_set_password', args=[appointment.pk, uid, token]))


def _send_login_link_email(request, doctor, appointment, user, assigned, created):
    """Envoie par email le lien de connexion au patient. Renvoie (email_sent, link)."""
    link = _patient_login_link(request, user, appointment)
    if not settings.EMAIL_BACKEND.endswith('smtp.EmailBackend'):
        return False, link
    community_lines = '\n'.join(
        f"  - {c.name} : {request.build_absolute_uri(reverse('community_detail', args=[c.slug]))}"
        for c in assigned
    )
    if created:
        message = (
            f"Bonjour {user.get_full_name() or user.username},\n\n"
            f"Le Dr {doctor.user.get_full_name() or doctor.user.username} a créé votre compte "
            f"patient à l'issue de sa consultation du {appointment.date.strftime('%d/%m/%Y')}.\n\n"
            "Pour activer votre compte et choisir votre mot de passe, cliquez sur ce lien "
            "(valable 24 heures) :\n\n"
            f"  {link}\n\n"
            "Une fois votre mot de passe défini, connectez-vous pour accéder à votre espace patient.\n"
            "Communautés / forums auxquels vous avez été ajouté :\n"
            f"{community_lines}\n\n"
            "L'équipe CareCircle."
        )
    else:
        message = (
            f"Bonjour {user.get_full_name() or user.username},\n\n"
            f"Le Dr {doctor.user.get_full_name() or doctor.user.username} vous a ajouté "
            f"aux communautés suivantes après votre consultation du "
            f"{appointment.date.strftime('%d/%m/%Y')} :\n"
            f"{community_lines or '  — aucune —'}\n\n"
            "Pour modifier votre mot de passe et accéder à votre espace patient, utilisez ce lien "
            "(valable 24 heures) :\n\n"
            f"  {link}\n\n"
            "L'équipe CareCircle."
        )
    try:
        send_mail(
            subject='Votre lien de connexion CareCircle',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return True, link
    except Exception:
        logger.exception("Échec envoi lien de connexion patient %s (RDV %s)", user.pk, appointment.pk)
        return False, link


@user_passes_test(_is_doctor, login_url='appointment_list')
def appointment_create_patient_account(request, pk):
    """À l'issue de la consultation : le médecin remplit le compte-rendu,
    crée le compte patient (si besoin), l'inclut dans des communautés/forums
    puis envoie au patient un lien de connexion à usage unique (valable 24 h)."""
    appointment = get_object_or_404(Appointment, pk=pk, doctor=_get_doctor(request.user))
    doctor = _get_doctor(request.user)
    communities = Community.objects.filter(is_active=True)

    if appointment.patient:
        messages.warning(request, 'Un compte patient est déjà rattaché à ce rendez-vous.')
        return redirect('appointment_detail', pk=pk)

    if request.method == 'POST':
        patient_name = request.POST.get('patient_name', '').strip() or appointment.patient_name
        patient_email = request.POST.get('patient_email', '').strip() or appointment.patient_email
        doctor_notes = request.POST.get('doctor_notes', '').strip()
        mark_completed = request.POST.get('mark_completed') == 'on'
        community_ids = request.POST.getlist('communities')

        if not patient_name or not patient_email:
            messages.error(request, 'Le nom et l\'email du patient sont obligatoires.')
            return render(request, 'appointments/create_patient_account.html', {
                'appointment': appointment,
                'communities': communities,
            })

        existing = (User.objects
                    .filter(email__iexact=patient_email)
                    .exclude(doctor_profile__isnull=False)
                    .exclude(is_superuser=True)
                    .exclude(is_staff=True)
                    .first())
        created = False
        if existing:
            user = existing
        else:
            first_name, last_name = _split_name(patient_name)
            username = _unique_username(first_name or last_name)
            user = User(
                username=username,
                email=patient_email,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
            )
            user.set_unusable_password()
            user.save()
            created = True
        PatientProfile.objects.get_or_create(user=user, defaults={'phone': appointment.patient_phone or ''})

        # Compte-rendu de consultation + rattachement du rendez-vous au compte
        appointment.patient = user
        appointment.doctor_notes = doctor_notes
        if mark_completed and appointment.status != 'cancelled':
            appointment.status = 'completed'
        appointment.credentials_sent = True
        appointment.credentials_sent_at = timezone.now()
        appointment.save()

        # Inclusion du patient dans les communautés / forums choisis par le médecin
        assigned = []
        for cid in community_ids:
            community = Community.objects.filter(id=cid, is_active=True).first()
            if community:
                CommunityMembership.objects.get_or_create(
                    community=community,
                    user=user,
                    defaults={'added_by': doctor.user},
                )
                assigned.append(community)

        email_sent, link = _send_login_link_email(request, doctor, appointment, user, assigned, created)

        return render(request, 'appointments/patient_account_created.html', {
            'created': created,
            'user': user,
            'appointment': appointment,
            'link': link,
            'email_sent': email_sent,
            'expiry_hours': settings.PASSWORD_RESET_TIMEOUT // 3600,
            'communities': assigned,
        })

    return render(request, 'appointments/create_patient_account.html', {
        'appointment': appointment,
        'communities': communities,
    })


def patient_set_password(request, pk, uid, token):
    """Le patient ouvre le lien de connexion reçu : il choisit son mot de passe,
    puis est connecté et redirigé vers son espace patient. Lien valable 24 h,
    à usage unique."""
    appointment = get_object_or_404(Appointment, pk=pk)
    user = None
    try:
        uid_value = urlsafe_base64_decode(force_str(uid))
        user = User.objects.get(pk=uid_value)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    valid = user is not None and default_token_generator.check_token(user, token)

    if not valid:
        return render(request, 'appointments/patient_set_password_invalid.html', {
            'appointment': appointment,
        }, status=400)

    if request.user.is_authenticated and request.user == user:
        return redirect('profile')

    if request.method == 'POST':
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        if password != password2:
            messages.error(request, 'Les mots de passe ne correspondent pas.')
            return render(request, 'appointments/patient_set_password.html', {
                'appointment': appointment,
                'user': user,
            })
        try:
            validate_password(password, user=user)
        except ValidationError as valid_errors:
            for err in valid_errors:
                messages.error(request, err)
        else:
            user.set_password(password)
            user.save()
            auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, 'Mot de passe défini. Bienvenue sur votre espace patient.')
            return redirect('profile')

    return render(request, 'appointments/patient_set_password.html', {
        'appointment': appointment,
        'user': user,
    })


@user_passes_test(_is_doctor, login_url='appointment_list')
def appointment_resend_login_link(request, pk):
    """Le médecin renvoie le lien de connexion (ex : lien expiré au bout de 24 h ou déjà utilisé)."""
    appointment = get_object_or_404(Appointment, pk=pk, doctor=_get_doctor(request.user))
    if not appointment.patient or not appointment.patient.email:
        messages.error(request, 'Aucun compte patient lié : impossible d\'envoyer un lien.')
        return redirect('appointment_detail', pk=pk)

    assigned = list(appointment.patient.communities.all())
    email_sent, link = _send_login_link_email(
        request, _get_doctor(request.user), appointment, appointment.patient, assigned, created=False
    )
    appointment.credentials_sent = True
    appointment.credentials_sent_at = timezone.now()
    appointment.save(update_fields=['credentials_sent', 'credentials_sent_at'])

    if email_sent:
        messages.success(request, 'Le lien de connexion a été renvoyé par email au patient.')
        return redirect('appointment_detail', pk=pk)

    return render(request, 'appointments/patient_account_created.html', {
        'created': False,
        'user': appointment.patient,
        'appointment': appointment,
        'link': link,
        'email_sent': False,
        'expiry_hours': settings.PASSWORD_RESET_TIMEOUT // 3600,
        'communities': assigned,
    })


@user_passes_test(_is_doctor, login_url='home')
def patient_medical_record(request, patient_id):
    """Le médecin consulte les informations médicales du patient (avec avertissement)."""
    doctor = _get_doctor(request.user)
    patient = get_object_or_404(User, id=patient_id)
    # Vérifier que le médecin a au moins un rendez-vous avec ce patient
    has_relation = doctor.appointments.filter(patient=patient, status__in=['pending', 'confirmed', 'completed']).exists()
    profile = getattr(patient, 'patient_profile', None)
    share_ok = bool(profile and profile.share_medical_record and has_relation)
    appointments = doctor.appointments.filter(patient=patient).order_by('-date')
    return render(request, 'appointments/patient_medical_record.html', {
        'patient': patient,
        'profile': profile,
        'appointments': appointments,
        'has_relation': has_relation,
        'share_ok': share_ok,
    })


@user_passes_test(_is_doctor, login_url='home')
def doctor_view_journal(request, patient_id):
    """Le médecin consulte le journal de santé du patient s'il y a consentement + relation."""
    doctor = _get_doctor(request.user)
    patient = get_object_or_404(User, id=patient_id)
    profile = getattr(patient, 'patient_profile', None)
    has_relation = doctor.appointments.filter(
        patient=patient, status__in=['pending', 'confirmed', 'completed']
    ).exists()
    if not (profile and profile.share_medical_record and has_relation):
        messages.error(request, 'Accès refusé : le patient n\'a pas autorisé le partage de son journal de santé.')
        return redirect('patient_medical_record', patient_id=patient.id)

    from health_journal.models import HealthEntry, Medication, VitalSign
    entries = HealthEntry.objects.filter(user=patient)
    medications = Medication.objects.filter(user=patient, is_active=True)
    vitals = VitalSign.objects.filter(user=patient)[:20]
    return render(request, 'appointments/doctor_view_journal.html', {
        'patient': patient,
        'entries': entries,
        'medications': medications,
        'vitals': vitals,
    })


@login_required
def appointment_create(request):
    """Patient prend un rendez-vous : choisit un médecin puis un créneau, ou saisit manuellement."""
    if request.method == 'POST':
        doctor_id = request.POST.get('doctor')
        slot_id = request.POST.get('slot')
        title = request.POST.get('title')
        date_str = request.POST.get('date') or ''
        time_str = request.POST.get('time') or ''
        date = parse_date(date_str) if date_str else None
        time = parse_time(time_str) if time_str else None

        doctor = Doctor.objects.filter(id=doctor_id).first() if doctor_id else None
        slot = AvailabilitySlot.objects.filter(id=slot_id, is_booked=False).first() if slot_id else None
        if slot:
            slot.is_booked = True
            slot.save()
            date = slot.date
            time = slot.start_time

        if not title:
            title = f"Rendez-vous avec Dr {doctor.user.last_name}" if doctor else 'Rendez-vous'
        if not date or not time:
            messages.error(request, 'Veuillez choisir une date et une heure.')
            return redirect('appointment_create')

        appointment = Appointment.objects.create(
            patient=request.user,
            doctor=doctor,
            slot=slot,
            title=title,
            description=request.POST.get('description', ''),
            date=date,
            time=time,
            location=request.POST.get('location', ''),
            notes=request.POST.get('notes', ''),
            created_by=request.user,
        )
        # Notification email au médecin
        if doctor and doctor.user.email:
            try:
                send_mail(
                    subject=f'Nouveau rendez-vous : {title}',
                    message=(
                        f"Bonjour Dr {doctor.user.get_full_name() or doctor.user.username},\n\n"
                        f"Un nouveau rendez-vous a été réservé sur Care Circle :\n"
                        f"  Patient : {request.user.get_full_name() or request.user.username}\n"
                        f"  Date : {date.strftime('%d/%m/%Y')}\n"
                        f"  Heure : {time.strftime('%H:%M')}\n"
                        f"  Motif : {title}\n\n"
                        f"Connectez-vous pour confirmer ce rendez-vous."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[doctor.user.email],
                    fail_silently=True,
                )
            except Exception:
                logger.exception("Échec envoi notification médecin RDV %s", pk)
        messages.success(request, 'Rendez-vous créé avec succès.')
        return redirect('appointment_list')
    doctors = Doctor.objects.filter(is_available=True).exclude(user__is_superuser=True).exclude(user__is_staff=True).select_related('user')
    return render(request, 'appointments/create.html', {'doctors': doctors})


@user_passes_test(_is_doctor, login_url='appointment_list')
def appointment_create_for_patient(request):
    """Un médecin programme un rendez-vous pour un patient."""
    if request.method == 'POST':
        patient_id = request.POST.get('patient')
        title = request.POST.get('title')
        date = parse_date(request.POST.get('date'))
        time = parse_time(request.POST.get('time'))
        patient = User.objects.filter(id=patient_id).first()

        if not patient or not date or not time:
            messages.error(request, 'Veuillez remplir tous les champs obligatoires.')
            return redirect('appointment_create_for_patient')

        Appointment.objects.create(
            patient=patient,
            doctor=_get_doctor(request.user),
            title=title or f"Consultation {patient.username}",
            description=request.POST.get('description', ''),
            date=date,
            time=time,
            location=request.POST.get('location', ''),
            notes=request.POST.get('notes', ''),
            created_by=request.user,
            status='confirmed',
        )
        # Notification email au patient
        if patient.email:
            try:
                send_mail(
                    subject='Votre rendez-vous a été programmé',
                    message=(
                        f"Bonjour {patient.get_full_name() or patient.username},\n\n"
                        f"Le Dr {request.user.get_full_name() or request.user.username} a programmé un rendez-vous pour vous :\n"
                        f"  Date : {date.strftime('%d/%m/%Y')}\n"
                        f"  Heure : {time.strftime('%H:%M')}\n"
                        f"  Motif : {title or 'Consultation'}\n\n"
                        f"Connectez-vous à Care Circle pour plus de détails."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[patient.email],
                    fail_silently=True,
                )
            except Exception:
                logger.exception("Échec envoi notification patient RDV programmé %s", pk)
        messages.success(request, 'Rendez-vous programmé pour le patient.')
        return redirect('appointment_list')
    patients = (User.objects
                .exclude(id=request.user.id)
                .exclude(is_superuser=True)
                .exclude(is_staff=True)
                .exclude(doctor_profile__isnull=False))
    return render(request, 'appointments/create_for_patient.html', {'patients': patients})


@login_required
def appointment_edit(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    doctor = _get_doctor(request.user)
    is_owner = request.user == appointment.patient or (doctor and doctor == appointment.doctor)
    if not is_owner:
        messages.error(request, 'Vous ne pouvez pas modifier ce rendez-vous.')
        return redirect('appointment_detail', pk=pk)
    if request.method == 'POST':
        appointment.title = request.POST.get('title', appointment.title)
        appointment.description = request.POST.get('description', appointment.description)
        if request.POST.get('date'):
            appointment.date = parse_date(request.POST.get('date'))
        if request.POST.get('time'):
            appointment.time = parse_time(request.POST.get('time'))
        appointment.location = request.POST.get('location', appointment.location)
        appointment.notes = request.POST.get('notes', appointment.notes)
        appointment.status = request.POST.get('status', appointment.status)
        appointment.save()
        messages.success(request, 'Rendez-vous modifié.')
        return redirect('appointment_detail', pk=pk)
    return render(request, 'appointments/edit.html', {'appointment': appointment})


@login_required
def appointment_cancel(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    if request.method == 'POST':
        appointment.status = 'cancelled'
        if appointment.slot:
            appointment.slot.is_booked = False
            appointment.slot.save()
        appointment.save()
        messages.success(request, 'Rendez-vous annulé.')
    return redirect('appointment_detail', pk=pk)


@user_passes_test(_is_doctor, login_url='appointments')
def my_slots(request):
    """Le médecin gère ses créneaux de disponibilité."""
    doctor = _get_doctor(request.user)
    existing = Appointment.objects.filter(doctor=doctor, slot__isnull=False).select_related('slot', 'patient')
    booked_slot_ids = existing.values_list('slot_id', flat=True)
    slots = AvailabilitySlot.objects.filter(doctor=doctor).select_related()
    return render(request, 'appointments/slots.html', {
        'doctor': doctor,
        'slots': slots,
        'booked_slot_ids': booked_slot_ids,
    })


@user_passes_test(_is_doctor, login_url='appointments')
def add_slot(request):
    """Le médecin ajoute des créneaux (répétables si souhaité)."""
    doctor = _get_doctor(request.user)
    if request.method == 'POST':
        day_start = parse_date(request.POST.get('start_date'))
        repeat_days = int(request.POST.get('repeat_days') or 1)
        start_time = parse_time(request.POST.get('start_time'))
        end_time = parse_time(request.POST.get('end_time'))
        from datetime import timedelta
        for i in range(repeat_days):
            d = day_start + timedelta(days=i)
            AvailabilitySlot.objects.create(
                doctor=doctor, date=d, start_time=start_time, end_time=end_time
            )
        messages.success(request, f'{repeat_days} créneau(x) ajouté(s).')
        return redirect('my_slots')
    return render(request, 'appointments/add_slot.html')
