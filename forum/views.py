from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Post, Comment, Category, Report


def post_list(request):
    posts = Post.objects.filter(is_published=True, is_hidden=False).select_related('author', 'category')
    categories = Category.objects.all()
    category_slug = request.GET.get('category')
    if category_slug:
        posts = posts.filter(category__slug=category_slug)
    return render(request, 'forum/post_list.html', {
        'posts': posts,
        'categories': categories,
        'current_category': category_slug,
    })


def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, is_published=True, is_hidden=False)
    comments = post.comments.filter(is_hidden=False).select_related('author')
    return render(request, 'forum/post_detail.html', {
        'post': post,
        'comments': comments,
    })


@login_required
def post_create(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        category_id = request.POST.get('category')
        post = Post.objects.create(
            title=title,
            content=content,
            author=request.user,
            category_id=category_id or None,
        )
        messages.success(request, 'Article publié avec succès.')
        return redirect('post_detail', slug=post.slug)
    categories = Category.objects.all()
    return render(request, 'forum/post_create.html', {'categories': categories})


@login_required
def post_edit(request, slug):
    post = get_object_or_404(Post, slug=slug, author=request.user)
    if request.method == 'POST':
        post.title = request.POST.get('title', post.title)
        post.content = request.POST.get('content', post.content)
        post.category_id = request.POST.get('category') or post.category_id
        post.save()
        messages.success(request, 'Article modifié avec succès.')
        return redirect('post_detail', slug=post.slug)
    categories = Category.objects.all()
    return render(request, 'forum/post_edit.html', {'post': post, 'categories': categories})


@login_required
def post_delete(request, slug):
    post = get_object_or_404(Post, slug=slug, author=request.user)
    if request.method == 'POST':
        post.delete()
        messages.success(request, 'Article supprimé.')
        return redirect('post_list')
    return render(request, 'forum/post_delete.html', {'post': post})


@login_required
def add_comment(request, slug):
    post = get_object_or_404(Post, slug=slug, is_published=True)
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            Comment.objects.create(post=post, author=request.user, content=content)
    return redirect('post_detail', slug=slug)


@login_required
def toggle_like(request, slug):
    post = get_object_or_404(Post, slug=slug, is_published=True, is_hidden=False)
    if request.user in post.likes.all():
        post.likes.remove(request.user)
    else:
        post.likes.add(request.user)
    return redirect('post_detail', slug=slug)


@login_required
def report_post(request, slug):
    post = get_object_or_404(Post, slug=slug, is_published=True)
    if request.method == 'POST':
        Report.objects.create(
            reporter=request.user,
            post=post,
            reason=request.POST.get('reason', 'other'),
            description=request.POST.get('description', ''),
        )
        messages.success(request, 'Signalement envoyé. Merci de votre contribution.')
    return redirect('post_detail', slug=slug)


@login_required
def report_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if request.method == 'POST':
        Report.objects.create(
            reporter=request.user,
            comment=comment,
            reason=request.POST.get('reason', 'other'),
            description=request.POST.get('description', ''),
        )
        messages.success(request, 'Signalement envoyé.')
    return redirect('post_detail', slug=comment.post.slug)
