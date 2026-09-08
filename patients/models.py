from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class PatientProfile(models.Model):
    GENDER_CHOICES = [
        ('M', _('Homme')),
        ('F', _('Femme')),
        ('O', _('Autre')),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    date_of_birth = models.DateField('Date de naissance', null=True, blank=True)
    gender = models.CharField('Genre', max_length=1, choices=GENDER_CHOICES, blank=True)
    phone = models.CharField('Téléphone', max_length=20, blank=True)
    address = models.TextField('Adresse', blank=True)
    blood_type = models.CharField('Groupe sanguin', max_length=5, blank=True)
    allergies = models.TextField('Allergies', blank=True)
    medical_conditions = models.TextField('Conditions médicales', blank=True)
    emergency_contact = models.CharField('Contact d\'urgence', max_length=200, blank=True)
    emergency_phone = models.CharField('Téléphone d\'urgence', max_length=20, blank=True)
    photo = models.ImageField('Photo', upload_to='patients/photos/', blank=True, null=True)
    share_medical_record = models.BooleanField(
        'Partager mes données médicales avec mon médecin',
        default=False,
        help_text='Autorise les médecins avec qui vous avez un rendez-vous à consulter votre dossier et votre journal de santé.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil patient'
        verbose_name_plural = 'Profils patients'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"


class Connection(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('accepted', 'Acceptée'),
        ('rejected', 'Refusée'),
    ]

    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='connections_sent')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='connections_received')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('from_user', 'to_user')
        verbose_name = 'Connexion'
        verbose_name_plural = 'Connexions'

    def __str__(self):
        return f"{self.from_user} -> {self.to_user} ({self.status})"
