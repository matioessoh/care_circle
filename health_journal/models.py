from django.db import models
from django.contrib.auth.models import User


class HealthEntry(models.Model):
    MOOD_CHOICES = [
        ('great', 'Très bien'),
        ('good', 'Bien'),
        ('okay', 'Passable'),
        ('bad', 'Mauvais'),
        ('terrible', 'Très mauvais'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='health_entries')
    date = models.DateField('Date')
    mood = models.CharField('Humeur', max_length=10, choices=MOOD_CHOICES)
    symptoms = models.TextField('Symptômes', blank=True)
    medications = models.TextField('Médicaments pris', blank=True)
    notes = models.TextField('Notes', blank=True)
    sleep_hours = models.DecimalField('Heures de sommeil', max_digits=3, decimal_places=1, null=True, blank=True)
    pain_level = models.IntegerField('Niveau de douleur (0-10)', null=True, blank=True)
    weight = models.DecimalField('Poids (kg)', max_digits=5, decimal_places=1, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Entrée santé'
        verbose_name_plural = 'Entrées santé'
        ordering = ['-date']

    def __str__(self):
        return f"{self.user} - {self.date} ({self.get_mood_display()})"


class Medication(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='medications')
    name = models.CharField('Nom', max_length=200)
    dosage = models.CharField('Dosage', max_length=100)
    frequency = models.CharField('Fréquence', max_length=100)
    start_date = models.DateField('Date de début', null=True, blank=True)
    end_date = models.DateField('Date de fin', null=True, blank=True)
    is_active = models.BooleanField('Actif', default=True)
    notes = models.TextField('Notes', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Médicament'
        verbose_name_plural = 'Médicaments'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.dosage})"


class VitalSign(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vital_signs')
    date = models.DateTimeField('Date et heure')
    systolic_bp = models.IntegerField('Pression systolique', null=True, blank=True)
    diastolic_bp = models.IntegerField('Pression diastolique', null=True, blank=True)
    heart_rate = models.IntegerField('Fréquence cardiaque', null=True, blank=True)
    temperature = models.DecimalField('Température', max_digits=4, decimal_places=1, null=True, blank=True)
    blood_sugar = models.DecimalField('Glycémie', max_digits=5, decimal_places=1, null=True, blank=True)
    notes = models.TextField('Notes', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Signe vital'
        verbose_name_plural = 'Signes vitaux'
        ordering = ['-date']

    def __str__(self):
        return f"{self.user} - {self.date}"
