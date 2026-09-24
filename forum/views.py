from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q, Count
from django.utils.text import slugify
from .models import Post, Comment, Category, Report, Community, CommunityMembership
from appointments.views import _is_doctor


def _can_access_post(user, post):
    """Un article de communauté n'est visible que par ses membres (ou un médecin/admin)."""
    if not post.community:
        return True
    if post.community.memberships.filter(user=user).exists():
        return True
    if getattr(user, 'is_authenticated', False) and (_is_doctor(user) or user.is_superuser or user.is_staff):
        return True
    return False


def post_list(request):
    posts = Post.objects.filter(is_published=True, is_hidden=False, community__isnull=True).select_related('author', 'category')
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
    if not _can_access_post(request.user, post):
        messages.info(request, 'Accès réservé aux membres de la communauté.')
        return redirect('community_detail', slug=post.community.slug)
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
    if not _can_access_post(request.user, post):
        messages.error(request, 'Accès réservé aux membres de la communauté.')
        return redirect('post_list')
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            Comment.objects.create(post=post, author=request.user, content=content)
    return redirect('post_detail', slug=slug)


@login_required
def toggle_like(request, slug):
    post = get_object_or_404(Post, slug=slug, is_published=True, is_hidden=False)
    if not _can_access_post(request.user, post):
        messages.error(request, 'Accès réservé aux membres de la communauté.')
        return redirect('post_list')
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


def community_list(request):
    """Liste des communautés thérapeutiques (accès réservé aux membres inscrits par un médecin)."""
    communities = Community.objects.filter(is_active=True).select_related('created_by')
    my_ids = set()
    my_communities = []
    if request.user.is_authenticated:
        my_ids = set(request.user.community_memberships.values_list('community_id', flat=True))
        my_communities = list(request.user.communities.filter(is_active=True))
    return render(request, 'forum/community_list.html', {
        'communities': communities,
        'my_ids': my_ids,
        'my_communities': my_communities,
    })


@login_required
def community_detail(request, slug):
    community = get_object_or_404(Community, slug=slug, is_active=True)
    is_member = community.memberships.filter(user=request.user).exists()
    is_doctor = _is_doctor(request.user)
    is_staff = request.user.is_superuser or request.user.is_staff
    if not (is_member or is_doctor or is_staff):
        messages.info(request, 'Accès réservé : ce forum vous sera ouvert par votre médecin.')
        return render(request, 'forum/community_locked.html', {'community': community})
    posts = community.posts.filter(is_published=True, is_hidden=False).select_related('author', 'category')
    return render(request, 'forum/community_detail.html', {
        'community': community,
        'posts': posts,
        'is_member': is_member,
    })


@login_required
def community_post_create(request, slug):
    """Publier un article dans le forum d'une communauté (réservé aux membres)."""
    community = get_object_or_404(Community, slug=slug, is_active=True)
    is_member = community.memberships.filter(user=request.user).exists()
    is_doctor = _is_doctor(request.user)
    is_staff = request.user.is_superuser or request.user.is_staff
    if not (is_member or is_doctor or is_staff):
        messages.error(request, 'Vous devez être membre de cette communauté pour publier.')
        return redirect('community_detail', slug=slug)
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        if not title or not content:
            messages.error(request, 'Le titre et le contenu sont obligatoires.')
            return redirect('community_post_create', slug=slug)
        base_slug = slugify(title) or 'article'
        final_slug = base_slug
        n = 1
        while Post.objects.filter(slug=final_slug).exists():
            n += 1
            final_slug = f"{base_slug}-{n}"
        Post.objects.create(
            title=title,
            slug=final_slug,
            content=content,
            author=request.user,
            community=community,
        )
        messages.success(request, 'Article publié dans la communauté.')
        return redirect('community_detail', slug=slug)
    return render(request, 'forum/community_post_create.html', {'community': community})


def advanced_search(request):
    query = request.GET.get('q', '').strip()
    scope = request.GET.get('scope', 'all')
    results = []
    counts = {'posts': 0, 'members': 0, 'doctors': 0}

    if query:
        if scope in ('all', 'posts'):
            posts = Post.objects.filter(
                is_published=True, is_hidden=False, community__isnull=True
            ).filter(
                Q(title__icontains=query) | Q(content__icontains=query) | Q(author__username__icontains=query)
            ).select_related('author', 'category')[:30]
            results.extend(('posts', p, None) for p in posts)
            counts['posts'] = len(posts)

        if scope in ('all', 'members'):
            members = User.objects.filter(
                Q(username__icontains=query) | Q(first_name__icontains=query) |
                Q(last_name__icontains=query) | Q(email__icontains=query)
            ).exclude(is_superuser=True).exclude(is_staff=True)[:30]
            results.extend(('members', None, m) for m in members)
            counts['members'] = len(members)

        if scope in ('all', 'doctors'):
            doctors = []
            from appointments.models import Doctor
            doctors = Doctor.objects.filter(
                Q(user__username__icontains=query) |
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(specialty__icontains=query) |
                Q(clinic_name__icontains=query)
            ).select_related('user')[:30]
            results.extend(('doctors', None, d) for d in doctors)
            counts['doctors'] = len(doctors)

    # Triage : posts d'abord, puis membres, puis médecins
    results.sort(key=lambda r: {'posts': 0, 'members': 1, 'doctors': 2}[r[0]])

    return render(request, 'forum/search.html', {
        'query': query,
        'scope': scope,
        'results': results,
        'counts': counts,
    })
