from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse
from .notify import notify

_PREV_STATUS = {}


def _pretty_date(value):
    if hasattr(value, 'strftime'):
        return value.strftime('%d/%m/%Y')
    return str(value)


@receiver(pre_save, sender='appointments.Appointment')
def capture_appointment_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            _PREV_STATUS[instance.pk] = sender.objects.get(pk=instance.pk).status
        except sender.DoesNotExist:
            _PREV_STATUS[instance.pk] = None


@receiver(post_save, sender='appointments.Appointment')
def appointment_notifications(sender, instance, created, **kwargs):
    url = reverse('appointment_detail', args=[instance.pk])
    # Nouveau rendez-vous demandé -> prévenir le médecin
    if created:
        if instance.doctor and instance.doctor.user_id != instance.patient_id:
            notify(
                user=instance.doctor.user,
                kind='appointment',
                title='Nouveau rendez-vous demandé',
                message=f"{instance.patient.get_full_name() or instance.patient.username} "
                        f"a demandé un rendez-vous : {instance.title} "
                        f"{_pretty_date(instance.date)}.",
                url=url,
            )
        return

    prev = _PREV_STATUS.get(instance.pk)
    current = instance.status
    doctor_name = ''
    if instance.doctor:
        doctor_name = f"Le Dr {instance.doctor.user.get_full_name() or instance.doctor.user.username} "
    # Changement de statut -> prévenir le patient
    if prev != current:
        if current == 'confirmed':
            notify(
                user=instance.patient,
                kind='appointment',
                title='Rendez-vous confirmé',
                message=f"{doctor_name}a confirmé votre rendez-vous : {instance.title} "
                        f"{_pretty_date(instance.date)}.",
                url=url,
            )
        elif current == 'cancelled':
            notify(
                user=instance.patient,
                kind='appointment',
                title='Rendez-vous annulé',
                message=f"{doctor_name}a annulé votre rendez-vous : {instance.title}.",
                url=url,
            )
        elif current == 'completed':
            notify(
                user=instance.patient,
                kind='appointment',
                title='Rendez-vous terminé',
                message=f"Votre rendez-vous « {instance.title} » avec {doctor_name}est terminé.",
                url=url,
            )
        _PREV_STATUS.pop(instance.pk, None)


@receiver(post_save, sender='messaging.Message')
def message_notifications(sender, instance, created, **kwargs):
    if not created:
        return
    # Notifier tous les autres participants de la conversation
    others = instance.conversation.participants.exclude(id=instance.sender_id)
    url = reverse('conversation_detail', args=[instance.conversation_id])
    for other in others:
        notify(
            user=other,
            kind='message',
            title=f'Nouveau message de {instance.sender.username}',
            message=instance.content[:120],
            url=url,
        )


@receiver(pre_save, sender='patients.Connection')
def capture_connection_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            _PREV_STATUS[('conn', instance.pk)] = sender.objects.get(pk=instance.pk).status
        except sender.DoesNotExist:
            _PREV_STATUS[('conn', instance.pk)] = None


@receiver(post_save, sender='patients.Connection')
def connection_notifications(sender, instance, created, **kwargs):
    # Nouvelle demande de connexion -> notifier le destinataire
    if created:
        if instance.to_user_id != instance.from_user_id:
            notify(
                user=instance.to_user,
                kind='connection',
                title='Nouvelle demande de connexion',
                message=f"{instance.from_user.username} souhaite se connecter avec vous.",
                url=reverse('my_connections'),
            )
        return

    prev = _PREV_STATUS.get(('conn', instance.pk))
    if prev == 'pending' and instance.status == 'accepted':
        notify(
            user=instance.from_user,
            kind='connection',
            title='Demande de connexion acceptée',
            message=f"{instance.to_user.username} a accepté votre demande de connexion.",
            url=reverse('my_connections'),
        )
    _PREV_STATUS.pop(('conn', instance.pk), None)


@receiver(post_save, sender='forum.Comment')
def comment_notifications(sender, instance, created, **kwargs):
    if not created:
        return
    post = instance.post
    if instance.author_id != post.author_id:
        notify(
            user=post.author,
            kind='forum',
            title='Nouveau commentaire sur votre publication',
            message=f"{instance.author.username} a commenté « {post.title[:60]} ».",
            url=reverse('post_detail', args=[post.slug]),
        )