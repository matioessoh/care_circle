from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings

from appointments.models import Appointment
from health_journal.models import Medication


class Command(BaseCommand):
    help = "Envoie les rappels de rendez-vous (aujourd'hui / demain) et de médicaments."

    def handle(self, *args, **options):
        today = date.today()
        tomorrow = today + timedelta(days=1)

        sent = 0
        # Rappels de rendez-vous confirmés
        for app in Appointment.objects.filter(
            status='confirmed',
            date__in=[today, tomorrow],
        ).select_related('patient', 'doctor__user'):
            if not app.patient.email:
                continue
            when = "aujourd'hui" if app.date == today else "demain"
            heure = app.time.strftime('%H:%M') if app.time else "à l'heure prévue"
            sujet = "Rappel : votre rendez-vous " + when
            corps = (
                "Bonjour " + (app.patient.get_full_name() or app.patient.username) + ",\n\n"
                "Rappel : vous avez un rendez-vous " + when + " à " + heure + ".\n"
                "  Dr " + (app.doctor.user.get_full_name() or app.doctor.user.username) + "\n"
                "  Motif : " + app.title + "\n\n"
                "Merci de vous connecter à Care Circle pour plus de détails."
            )
            try:
                send_mail(
                    subject=sujet,
                    message=corps,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[app.patient.email],
                    fail_silently=True,
                )
                sent += 1
            except Exception:
                pass

        # Rappels de médicaments actifs
        for med in Medication.objects.filter(is_active=True).select_related('user'):
            if not med.user.email:
                continue
            if med.end_date and med.end_date < today:
                continue
            try:
                send_mail(
                    subject="Rappel de traitement",
                    message=(
                        f"Bonjour {med.user.get_full_name() or med.user.username},\n\n"
                        f"Rappel : n'oubliez pas votre traitement aujourd'hui.\n"
                        f"  {med.name} — {med.dosage}\n"
                        f"  Fréquence : {med.frequency}\n\n"
                        f"Prenez soin de vous. — Care Circle"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[med.user.email],
                    fail_silently=True,
                )
                sent += 1
            except Exception:
                pass

        self.stdout.write(self.style.SUCCESS(f"{sent} email(s) de rappel envoyé(s)."))