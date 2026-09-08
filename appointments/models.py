from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    specialty = models.CharField('Spécialité', max_length=100)
    license_number = models.CharField('Numéro de licence', max_length=50, blank=True)
    clinic_name = models.CharField('Nom du cabinet', max_length=200, blank=True)
    clinic_address = models.TextField('Adresse du cabinet', blank=True)
    bio = models.TextField('Présentation', blank=True)
    phone = models.CharField('Téléphone', max_length=20, blank=True)
    consultation_fee = models.DecimalField('Honoraires', max_digits=8, decimal_places=2, null=True, blank=True)
    is_available = models.BooleanField('Disponible', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Médecin'
        verbose_name_plural = 'Médecins'
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        name = self.user.get_full_name() or self.user.username
        return f"Dr {name} - {self.specialty}"


class AvailabilitySlot(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='slots')
    date = models.DateField('Date')
    start_time = models.TimeField('Début')
    end_time = models.TimeField('Fin')
    is_booked = models.BooleanField('Réservé', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Créneau de disponibilité'
        verbose_name_plural = 'Créneaux de disponibilité'
        ordering = ['date', 'start_time']

    def __str__(self):
        return f"{self.doctor} - {self.date} {self.start_time}-{self.end_time}"

    @property
    def is_past(self):
        slot_datetime = timezone.make_aware(
            timezone.datetime.combine(self.date, self.start_time)
        )
        return slot_datetime < timezone.now()


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('confirmed', 'Confirmé'),
        ('cancelled', 'Annulé'),
        ('completed', 'Terminé'),
    ]

    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patient_appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, related_name='appointments', null=True, blank=True)
    slot = models.OneToOneField(AvailabilitySlot, on_delete=models.SET_NULL, related_name='appointment', null=True, blank=True)
    title = models.CharField('Titre', max_length=200)
    description = models.TextField('Description', blank=True)
    date = models.DateField('Date')
    time = models.TimeField('Heure')
    duration = models.DurationField('Durée', null=True, blank=True)
    location = models.CharField('Lieu', max_length=200, blank=True)
    status = models.CharField('Statut', max_length=10, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField('Notes', blank=True)
    doctor_notes = models.TextField('Notes de consultation', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_appointments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rendez-vous'
        verbose_name_plural = 'Rendez-vous'
        ordering = ['date', 'time']

    def __str__(self):
        return f"{self.title} - {self.date} {self.time}"

    def save(self, *args, **kwargs):
        if self.slot and not self.slot.is_booked:
            self.slot.is_booked = True
            self.slot.save()
        super().save(*args, **kwargs)

