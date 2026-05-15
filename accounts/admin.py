from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

User = get_user_model()

# 1. Unregister the default User admin
admin.site.unregister(User)

# 2. Re-register it using your own class (or the base one)
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # This ensures it uses the nice built-in User layout 
    # while living in your accounts app.
    pass