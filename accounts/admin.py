from django.contrib import admin
from zelda_api.models import ArticlePost, ArticleCategory

@admin.register(ArticlePost)
class ArticlePostAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'status', 'created_at']
    list_filter = ['status', 'category']
    prepopulated_fields = {'slug': ('title',)}

@admin.register(ArticleCategory)
class ArticleCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


# Accounts are deleted only through accounts/deletion.py -- from Settings, or by
# staff from the ops dashboard -- which cancels Stripe subscriptions first, keeps
# safety records and cleans up files and chat. Django admin's own delete would
# skip all of that, so it is switched off for users.
from django.contrib import admin as _admin
from django.contrib.auth import get_user_model as _get_user_model
from django.contrib.auth.admin import UserAdmin as _DjangoUserAdmin


class UserAdminWithoutDeletion(_DjangoUserAdmin):

    def has_delete_permission(self, request, obj=None):
        return False


_User = _get_user_model()
if _admin.site.is_registered(_User):
    _admin.site.unregister(_User)
_admin.site.register(_User, UserAdminWithoutDeletion)
