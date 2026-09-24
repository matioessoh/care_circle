from django.contrib import admin
from .models import Category, Post, Comment, Report, Community, CommunityMembership

admin.site.register(Category)
admin.site.register(Post)
admin.site.register(Comment)
admin.site.register(Report)
admin.site.register(Community)
admin.site.register(CommunityMembership)
