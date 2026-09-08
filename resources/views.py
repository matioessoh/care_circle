from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Q
from .models import HealthArticle, FAQItem, ArticleCategory


def article_list(request):
    articles = HealthArticle.objects.filter(is_published=True).select_related('category')
    query = request.GET.get('q')
    cat = request.GET.get('category')
    if query:
        articles = articles.filter(title__icontains=query)
    if cat:
        articles = articles.filter(category__slug=cat)
    categories = ArticleCategory.objects.annotate(
        n=Count('articles', filter=Q(articles__is_published=True))
    )
    return render(request, 'resources/article_list.html', {
        'articles': articles,
        'categories': categories,
        'current_category': cat,
        'current_query': query,
    })


def article_detail(request, slug):
    article = get_object_or_404(HealthArticle, slug=slug, is_published=True)
    related = article.category.articles.filter(is_published=True).exclude(id=article.id)[:3]
    return render(request, 'resources/article_detail.html', {
        'article': article,
        'related': related,
    })


def faq(request):
    faqs = FAQItem.objects.filter(is_active=True)
    return render(request, 'resources/faq.html', {'faqs': faqs})


def resources_home(request):
    recent = HealthArticle.objects.filter(is_published=True).select_related('category')[:6]
    faqs = FAQItem.objects.filter(is_active=True)[:5]
    return render(request, 'resources/resources_home.html', {
        'recent_articles': recent,
        'faqs': faqs,
    })