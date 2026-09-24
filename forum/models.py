from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Category(models.Model):
    name = models.CharField('Nom', max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField('Description', blank=True)

    class Meta:
        verbose_name = 'Catégorie'
        verbose_name_plural = 'Catégories'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Community(models.Model):
    """Communauté thérapeutique. Seul un médecin peut y inscrire un patient."""
    name = models.CharField('Nom', max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField('Description', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_communities')
    is_active = models.BooleanField('Active', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(
        User, through='CommunityMembership', through_fields=('community', 'user'),
        related_name='communities'
    )

    class Meta:
        verbose_name = 'Communauté'
        verbose_name_plural = 'Communautés'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def members_count(self):
        return self.memberships.count()


class CommunityMembership(models.Model):
    """Inscription d'un patient dans une communauté par un médecin."""
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='community_memberships')
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='added_community_memberships')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Membre de communauté'
        verbose_name_plural = 'Membres de communautés'
        unique_together = ('community', 'user')

    def __str__(self):
        return f"{self.user} -> {self.community}"


class Post(models.Model):
    title = models.CharField('Titre', max_length=200)
    slug = models.SlugField(unique=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_posts')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    community = models.ForeignKey(Community, on_delete=models.CASCADE, null=True, blank=True, related_name='posts')
    content = models.TextField('Contenu')
    is_published = models.BooleanField('Publié', default=True)
    is_hidden = models.BooleanField('Masqué par modération', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    likes = models.ManyToManyField(User, related_name='liked_posts', blank=True)

    class Meta:
        verbose_name = 'Article'
        verbose_name_plural = 'Articles'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def likes_count(self):
        return self.likes.count()


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_comments')
    content = models.TextField('Commentaire')
    is_hidden = models.BooleanField('Masqué par modération', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Commentaire'
        verbose_name_plural = 'Commentaires'
        ordering = ['created_at']

    def __str__(self):
        return f"Commentaire de {self.author} sur {self.post}"


class Report(models.Model):
    REASON_CHOICES = [
        ('spam', _('Spam')),
        ('offensive', _('Contenu offensant')),
        ('harassment', _('Harcèlement')),
        ('medical_advice', _('Conseil médical dangereux')),
        ('inappropriate', _('Contenu inapproprié')),
        ('other', _('Autre')),
    ]

    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('reviewed', 'Traité'),
        ('dismissed', 'Rejeté'),
    ]

    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_made')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    reason = models.CharField('Motif', max_length=30, choices=REASON_CHOICES)
    description = models.TextField('Description', blank=True)
    status = models.CharField('Statut', max_length=12, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_reports')
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Signalement'
        verbose_name_plural = 'Signalements'
        ordering = ['created_at']

    def __str__(self):
        target = f"article « {self.post.title} »" if self.post else f"commentaire #{self.comment_id}"
        return f"Signalement de {self.reporter} : {target}"
