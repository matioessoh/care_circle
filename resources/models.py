from django.db import models
from django.conf import settings


class ArticleCategory(models.Model):
    name = models.CharField('Nom', max_length=100)
    slug = models.SlugField('Slug', max_length=120, unique=True)

    class Meta:
        verbose_name = 'Catégorie d\'article'
        verbose_name_plural = 'Catégories d\'articles'
        ordering = ['name']

    def __str__(self):
        return self.name


class HealthArticle(models.Model):
    title = models.CharField('Titre', max_length=200)
    slug = models.SlugField('Slug', max_length=220, unique=True)
    category = models.ForeignKey(
        ArticleCategory, on_delete=models.CASCADE, related_name='articles',
        verbose_name='Catégorie'
    )
    summary = models.TextField('Résumé', blank=True)
    content = models.TextField('Contenu')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='resource_articles', verbose_name='Auteur'
    )
    is_published = models.BooleanField('Publié', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Fiche info'
        verbose_name_plural = 'Fiches info'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class FAQItem(models.Model):
    question = models.CharField('Question', max_length=250)
    answer = models.TextField('Réponse')
    order = models.PositiveIntegerField('Ordre', default=0)
    is_active = models.BooleanField('Active', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Question FAQ'
        verbose_name_plural = 'Questions FAQ'
        ordering = ['order', 'id']

    def __str__(self):
        return self.question