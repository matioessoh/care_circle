from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils.dateparse import parse_date, parse_time
from django.contrib.auth.decorators import user_passes_test
from django.core.mail import send_mail
from django.conf import settings
from datetime import date, timedelta
from .models import Appointment, Doctor, AvailabilitySlot


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
            if new_status in ('confirmed', 'cancelled') and appointment.patient.email:
                try:
                    send_mail(
                        subject="Votre rendez-vous a été " + ("confirmé" if new_status == 'confirmed' else "annulé"),
                        message=(
                            f"Bonjour {appointment.patient.get_full_name() or appointment.patient.username},\n\n"
                            f"Le Dr {appointment.doctor.user.get_full_name() or appointment.doctor.user.username} "
                            f"a {('confirmé' if new_status == 'confirmed' else 'annulé')} votre rendez-vous :\n"
                            f"  Date : {appointment.date.strftime('%d/%m/%Y')}\n"
                            f"  Heure : {appointment.time.strftime('%H:%M') if appointment.time else '—'}\n"
                            f"  Motif : {appointment.title}\n\n"
                            f"Connectez-vous à Care Circle pour plus de détails."
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[appointment.patient.email],
                        fail_silently=True,
                    )
                except Exception:
                    pass
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


@user_passes_test(_is_doctor, login_url='home')
def patient_medical_record(request, patient_id):
    """Le médecin consulte les informations médicales du patient (avec avertissement)."""
    doctor = _get_doctor(request.user)
    patient = get_object_or_404(User, id=patient_id)
    # Vérifier que le médecin a au moins un rendez-vous avec ce patient
    has_relation = doctor.appointments.filter(patient=patient, status__in=['pending', 'confirmed', 'completed']).exists()
    profile = getattr(patient, 'patient_profile', None)
    appointments = doctor.appointments.filter(patient=patient).order_by('-date')
    return render(request, 'appointments/patient_medical_record.html', {
        'patient': patient,
        'profile': profile,
        'appointments': appointments,
        'has_relation': has_relation,
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
                pass
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
                pass
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
