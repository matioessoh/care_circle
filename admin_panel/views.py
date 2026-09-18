from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponse
from datetime import date
from django.db.models import Count, Q
import csv

from audit.models import LoginLog

from patients.models import PatientProfile
from appointments.models import Doctor, Appointment, AvailabilitySlot
from forum.models import Post, Comment, Category, Report
from messaging.models import Conversation, Message


def _is_admin(user):
    return user.is_superuser


admin_required = user_passes_test(_is_admin, login_url='home')


@admin_required
def dashboard(request):
    stats = {
        'users': User.objects.count(),
        'patients': User.objects.filter(patient_profile__isnull=False).count(),
        'doctors': Doctor.objects.count(),
        'appointments': Appointment.objects.count(),
        'appointments_today': Appointment.objects.filter(date=date.today()).count(),
        'posts': Post.objects.count(),
        'comments': Comment.objects.count(),
        'pending_reports': Report.objects.filter(status='pending').count(),
        'conversations': Conversation.objects.count(),
        'messages': Message.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
    }
    recent_users = User.objects.order_by('-date_joined')[:10]
    recent_appointments = Appointment.objects.order_by('-created_at')[:10]
    recent_posts = Post.objects.order_by('-created_at')[:10]
    pending_reports = Report.objects.filter(status='pending').select_related('reporter', 'post', 'comment')[:10]

    # Appointments by status for the last 30 days
    appointments_by_status = (
        Appointment.objects.values('status').annotate(n=Count('id'))
    )
    doctors_top = (
        Doctor.objects.annotate(n=Count('appointments')).order_by('-n')[:10]
    )

    # New users count (last 30 days)
    month_ago = timezone.now() - timezone.timedelta(days=30)
    new_users_30 = User.objects.filter(date_joined__gte=month_ago).count()

    return render(request, 'admin_panel/dashboard.html', {
        'stats': stats,
        'recent_users': recent_users,
        'recent_appointments': recent_appointments,
        'recent_posts': recent_posts,
        'pending_reports': pending_reports,
        'appointments_by_status': appointments_by_status,
        'doctors_top': doctors_top,
        'new_users_30': new_users_30,
    })


@admin_required
def user_list(request):
    users = User.objects.select_related('patient_profile').annotate(
        post_count=Count('forum_posts', distinct=True),
        comment_count=Count('forum_comments', distinct=True),
    )
    query = request.GET.get('q')
    role = request.GET.get('role')
    if query:
        users = users.filter(
            Q(username__icontains=query) | Q(first_name__icontains=query) |
            Q(last_name__icontains=query) | Q(email__icontains=query)
        )
    if role == 'doctors':
        users = users.filter(doctor_profile__isnull=False)
    elif role == 'patients':
        users = users.filter(patient_profile__isnull=False)
    elif role == 'staff':
        users = users.filter(is_staff=True)
    elif role == 'superusers':
        users = users.filter(is_superuser=True)
    return render(request, 'admin_panel/users.html', {'users': users})


@admin_required
def user_toggle_active(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user == request.user:
        messages.error(request, 'Vous ne pouvez pas modifier votre propre compte.')
    else:
        user.is_active = not user.is_active
        user.save()
        state = 'activé' if user.is_active else 'désactivé'
        messages.success(request, f"Compte de {user.username} {state}.")
    return redirect('admin_users')


@admin_required
def user_deactivate(request, user_id):
    """Page de confirmation avant la désactivation du compte d'un utilisateur (patient, médecin, etc.)."""
    user = get_object_or_404(User, id=user_id)
    if user == request.user:
        messages.error(request, 'Vous ne pouvez pas désactiver votre propre compte.')
        return redirect('admin_users')
    if request.method == 'POST':
        if not user.is_active:
            messages.info(request, f"Le compte de {user.username} est déjà désactivé.")
        else:
            user.is_active = False
            user.save()
            messages.success(request, f"Compte de {user.username} désactivé. Il ne peut plus se connecter.")
        return redirect('admin_users')
    return render(request, 'admin_panel/user_delete.html', {'target_user': user})


@admin_required
def user_detail(request, user_id):
    user = get_object_or_404(User, id=user_id)
    profile = getattr(user, 'patient_profile', None)
    doctor = getattr(user, 'doctor_profile', None)
    appointments = Appointment.objects.filter(patient=user)
    posts = Post.objects.filter(author=user)
    comments = Comment.objects.filter(author=user)
    return render(request, 'admin_panel/user_detail.html', {
        'user': user,
        'profile': profile,
        'doctor': doctor,
        'appointments': appointments,
        'posts': posts,
        'comments': comments,
    })


@admin_required
def doctor_list_admin(request):
    doctors = Doctor.objects.select_related('user').annotate(
        n_appointments=Count('appointments')
    )
    query = request.GET.get('q')
    if query:
        doctors = doctors.filter(
            Q(user__username__icontains=query) | Q(specialty__icontains=query) |
            Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query)
        )
    return render(request, 'admin_panel/doctors.html', {'doctors': doctors})


@admin_required
def doctor_toggle_available(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)
    doctor.is_available = not doctor.is_available
    doctor.save()
    state = 'de nouveau disponible' if doctor.is_available else 'marqué indisponible'
    messages.success(request, f"Dr {doctor.user.get_full_name() or doctor.user.username} {state}.")
    return redirect('admin_doctors')


@admin_required
def doctor_create(request, user_id=None):
    """Créer un profil médecin. Optionnellement lié à un utilisateur existant."""
    initial_user = None
    if user_id:
        initial_user = get_object_or_404(User, id=user_id)
        if hasattr(initial_user, 'doctor_profile'):
            messages.error(request, "Cet utilisateur est déjà médecin.")
            return redirect('admin_user_detail', user_id=user_id)
    users_without_doctor = User.objects.exclude(doctor_profile__isnull=False)
    if request.method == 'POST':
        sel_user = request.POST.get('user')
        user = User.objects.filter(id=sel_user).first() if sel_user else None
        if not user:
            messages.error(request, 'Veuillez choisir un utilisateur.')
        else:
            Doctor.objects.create(
                user=user,
                specialty=request.POST.get('specialty', ''),
                license_number=request.POST.get('license_number', ''),
                clinic_name=request.POST.get('clinic_name', ''),
                clinic_address=request.POST.get('clinic_address', ''),
                bio=request.POST.get('bio', ''),
                phone=request.POST.get('phone', ''),
                consultation_fee=request.POST.get('consultation_fee') or None,
                is_available=request.POST.get('is_available') == 'on',
            )
            messages.success(request, f"Médecin créé : Dr {user.get_full_name() or user.username}.")
            return redirect('admin_doctors')
    return render(request, 'admin_panel/doctor_form.html', {
        'users': users_without_doctor,
        'initial_user': initial_user,
    })


@admin_required
def doctor_account_create(request):
    """Créer un compte complet pour un médecin : utilisateur + profil Docteur,
    avec un mot de passe généré et envoyé par email."""
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        specialty = request.POST.get('specialty', '').strip()
        phone = request.POST.get('phone', '').strip()
        clinic_name = request.POST.get('clinic_name', '').strip()
        license_number = request.POST.get('license_number', '').strip()

        errors = []
        if not email:
            errors.append("L'adresse e-mail est obligatoire.")
        elif User.objects.filter(email__iexact=email).exists():
            errors.append("Un compte existe déjà avec cette adresse e-mail.")
        if not first_name and not last_name:
            errors.append("Le nom est obligatoire.")
        if not specialty:
            errors.append("La spécialité est obligatoire.")

        if not errors:
            # Username généré à partir du nom (plus un suffixe si nécessaire).
            base = (first_name or last_name).lower().replace(' ', '_')[:12]
            username = base
            while User.objects.filter(username=username).exists():
                username = f"{base}_{get_random_string(4).lower()}"

            # Mot de passe aléatoire robuste (respecte les validateurs Django).
            password = get_random_string(14)
            while not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
                password = get_random_string(14)

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
            )
            Doctor.objects.create(
                user=user,
                specialty=specialty,
                license_number=license_number,
                clinic_name=clinic_name,
                phone=phone,
                is_available=True,
            )

            # Envoi des identifiants par email.
            email_sent = False
            if settings.EMAIL_BACKEND.endswith('smtp.EmailBackend'):
                try:
                    send_mail(
                        subject='Vos identifiants de connexion — CareCircle',
                        message=(
                            f"Bonjour Dr {first_name} {last_name},\n\n"
                            "Votre compte médecin a été créé sur CareCircle.\n\n"
                            f"Lien de connexion : https://care-circle-hazel.vercel.app/accounts/login/\n"
                            f"Identifiant : {username}\n"
                            f"Mot de passe : {password}\n\n"
                            "Vous pouvez modifier votre mot de passe après la première connexion.\n"
                            "L'équipe CareCircle."
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email],
                        fail_silently=False,
                    )
                    email_sent = True
                except Exception:
                    email_sent = False

            return render(request, 'admin_panel/doctor_account_created.html', {
                'user': user,
                'password': password,
                'email_sent': email_sent,
            })

        for err in errors:
            messages.error(request, err)
        return render(request, 'admin_panel/doctor_account_form.html', {
            'initial': {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'specialty': specialty,
                'phone': phone,
                'clinic_name': clinic_name,
                'license_number': license_number,
            },
        })

    return render(request, 'admin_panel/doctor_account_form.html', {})


@admin_required
def doctor_edit(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)
    if request.method == 'POST':
        doctor.specialty = request.POST.get('specialty', doctor.specialty)
        doctor.license_number = request.POST.get('license_number', doctor.license_number)
        doctor.clinic_name = request.POST.get('clinic_name', doctor.clinic_name)
        doctor.clinic_address = request.POST.get('clinic_address', doctor.clinic_address)
        doctor.bio = request.POST.get('bio', doctor.bio)
        doctor.phone = request.POST.get('phone', doctor.phone)
        doctor.consultation_fee = request.POST.get('consultation_fee') or None
        doctor.is_available = request.POST.get('is_available') == 'on'
        doctor.save()
        messages.success(request, 'Profil médecin mis à jour.')
        return redirect('admin_doctors')
    return render(request, 'admin_panel/doctor_form.html', {'doctor': doctor, 'edit': True})


@admin_required
def doctor_detail_admin(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)
    slots = AvailabilitySlot.objects.filter(doctor=doctor)
    appointments = doctor.appointments.select_related('patient')
    return render(request, 'admin_panel/doctor_detail.html', {
        'doctor': doctor,
        'slots': slots,
        'appointments': appointments,
    })


@admin_required
def doctor_delete(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)
    if request.method == 'POST':
        name = doctor.user.get_full_name() or doctor.user.username
        doctor.delete()
        messages.success(request, f"Profil médecin de Dr {name} supprimé.")
        return redirect('admin_doctors')
    return render(request, 'admin_panel/doctor_delete.html', {'doctor': doctor})


@admin_required
def doctor_toggle_active(request, doctor_id):
    """Réactiver le compte utilisateur du médecin (désactivation via page de confirmation)."""
    doctor = get_object_or_404(Doctor, id=doctor_id)
    user = doctor.user
    if user == request.user:
        messages.error(request, 'Vous ne pouvez pas désactiver votre propre compte.')
    elif user.is_active:
        return redirect('admin_doctor_deactivate', doctor_id=doctor.id)
    else:
        user.is_active = True
        user.save()
        messages.success(request, f"Compte du Dr {user.get_full_name() or user.username} réactivé.")
    return redirect('admin_doctors')


@admin_required
def doctor_deactivate(request, doctor_id):
    """Page de confirmation avant la désactivation du compte du médecin."""
    doctor = get_object_or_404(Doctor, id=doctor_id)
    user = doctor.user
    if user == request.user:
        messages.error(request, 'Vous ne pouvez pas désactiver votre propre compte.')
    elif request.method == 'POST':
        if not user.is_active:
            messages.info(request, f"Le compte de Dr {user.get_full_name() or user.username} est déjà désactivé.")
        else:
            user.is_active = False
            user.save()
            messages.success(request, f"Compte du Dr {user.get_full_name() or user.username} désactivé. Il ne peut plus se connecter.")
        return redirect('admin_doctors')
    return render(request, 'admin_panel/doctor_delete.html', {'doctor': doctor, 'deactivate': True})


@admin_required
def forum_posts(request):
    posts = Post.objects.select_related('author', 'category').annotate(
        n_comments=Count('comments'), n_reports=Count('reports')
    )
    query = request.GET.get('q')
    if query:
        posts = posts.filter(Q(title__icontains=query) | Q(content__icontains=query) | Q(author__username__icontains=query))
    status = request.GET.get('status')
    if status == 'hidden':
        posts = posts.filter(is_hidden=True)
    elif status == 'published':
        posts = posts.filter(is_published=True)
    return render(request, 'admin_panel/forum_posts.html', {'posts': posts})


@admin_required
def post_toggle_hide(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    post.is_hidden = not post.is_hidden
    post.save()
    state = 'masqué' if post.is_hidden else 'rétabli'
    messages.success(request, f"Article « {post.title} » {state}.")
    return redirect('admin_forum_posts')


@admin_required
def post_delete_mod(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    title = post.title
    post.delete()
    messages.success(request, f"Article « {title} » supprimé.")
    return redirect('admin_forum_posts')


@admin_required
def forum_comments(request):
    comments = Comment.objects.select_related('author', 'post')
    query = request.GET.get('q')
    if query:
        comments = comments.filter(Q(content__icontains=query) | Q(author__username__icontains=query) | Q(post__title__icontains=query))
    status = request.GET.get('status')
    if status == 'hidden':
        comments = comments.filter(is_hidden=True)
    return render(request, 'admin_panel/forum_comments.html', {'comments': comments})


@admin_required
def comment_toggle_hide(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    comment.is_hidden = not comment.is_hidden
    comment.save()
    state = 'masqué' if comment.is_hidden else 'rétabli'
    messages.success(request, f"Commentaire #{comment.id} {state}.")
    return redirect('admin_forum_comments')


@admin_required
def comment_delete_mod(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    comment.delete()
    messages.success(request, f"Commentaire #{comment_id} supprimé.")
    return redirect('admin_forum_comments')


@admin_required
def categories_list(request):
    categories = Category.objects.annotate(n_posts=Count('posts'))
    return render(request, 'admin_panel/categories.html', {'categories': categories})


@admin_required
def category_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        if name:
            Category.objects.create(name=name, description=description)
            messages.success(request, f"Catégorie « {name} » créée.")
            return redirect('admin_categories')
        messages.error(request, 'Le nom est obligatoire.')
    return render(request, 'admin_panel/category_form.html')


@admin_required
def category_edit(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        category.name = request.POST.get('name')
        category.description = request.POST.get('description', '')
        category.save()
        messages.success(request, 'Catégorie modifiée.')
        return redirect('admin_categories')
    return render(request, 'admin_panel/category_form.html', {'category': category})


@admin_required
def category_delete(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f"Catégorie « {name} » supprimée.")
        return redirect('admin_categories')
    return render(request, 'admin_panel/category_delete.html', {'category': category})


@admin_required
def reports_list(request):
    reports = Report.objects.select_related('reporter', 'post', 'comment', 'resolved_by')
    status = request.GET.get('status')
    if status == 'reviewed':
        reports = reports.filter(status='reviewed')
    elif status == 'dismissed':
        reports = reports.filter(status='dismissed')
    else:
        reports = reports.filter(status='pending')
    return render(request, 'admin_panel/reports.html', {'reports': reports, 'current_status': status or 'pending'})


@admin_required
def report_detail(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    return render(request, 'admin_panel/report_detail.html', {'report': report})


@admin_required
def report_action(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'hide_post' and report.post:
            report.post.is_hidden = True
            report.post.save()
            report.status = 'reviewed'
            messages.success(request, 'Article masqué.')
        elif action == 'hide_comment' and report.comment:
            report.comment.is_hidden = True
            report.comment.save()
            report.status = 'reviewed'
            messages.success(request, 'Commentaire masqué.')
        elif action == 'delete_post' and report.post:
            Report.objects.filter(post=report.post).delete()
            report.post.delete()
            messages.success(request, 'Article supprimé.')
            return redirect('admin_reports')
        elif action == 'delete_comment' and report.comment:
            Report.objects.filter(comment=report.comment).delete()
            report.comment.delete()
            messages.success(request, 'Commentaire supprimé.')
            return redirect('admin_reports')
        elif action == 'dismiss':
            report.status = 'dismissed'
            messages.success(request, 'Signalement rejeté.')
        report.resolved_by = request.user
        report.resolved_at = timezone.now()
        report.save()
    return redirect('admin_reports')


@admin_required
def export_users(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="utilisateurs.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['ID', 'Pseudo', 'Nom', 'Email', 'Rôle', 'Actif', 'Date d\'inscription'])
    for u in User.objects.select_related('patient_profile', 'doctor_profile').order_by('id'):
        if hasattr(u, 'doctor_profile'):
            role = 'Médecin'
        elif hasattr(u, 'patient_profile'):
            role = 'Patient'
        else:
            role = 'Utilisateur'
        writer.writerow([u.id, u.username, u.get_full_name(), u.email, role,
                         'Oui' if u.is_active else 'Non', u.date_joined.isoformat()])
    return response


@admin_required
def export_appointments(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="rendez_vous.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    labels = dict(Appointment.STATUS_CHOICES)
    writer.writerow(['ID', 'Médecin', 'Patient', 'Date', 'Heure', 'Motif', 'Statut'])
    for a in Appointment.objects.select_related('doctor__user', 'patient').order_by('-created_at'):
        writer.writerow([
            a.id,
            a.doctor.user.get_full_name() or a.doctor.user.username,
            a.patient.get_full_name() or a.patient.username,
            a.date.isoformat(),
            a.time.strftime('%H:%M') if a.time else '',
            a.title,
            labels.get(a.status, a.status),
        ])
    return response


@admin_required
def login_audit(request):
    logs = LoginLog.objects.select_related('user')
    status = request.GET.get('status')
    if status == 'failed':
        logs = logs.filter(success=False)
    elif status == 'success':
        logs = logs.filter(success=True)
    logs = logs[:200]
    return render(request, 'admin_panel/login_audit.html', {
        'logs': logs,
        'current_status': status or 'all',
    })

