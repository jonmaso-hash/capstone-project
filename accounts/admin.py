from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from accounts.models import FounderApplication, InvestorApplication


User = get_user_model()

# 1. Unregister the default User admin
admin.site.unregister(User)

# 2. Re-register it using your own class (or the base one)
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # This ensures it uses the nice built-in User layout 
    # while living in your accounts app.
    pass





@admin.register(FounderApplication)
class FounderApplicationAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'sector', 'user', 'funding_stage')
    search_fields = ('company_name', 'sector')

@admin.register(InvestorApplication)
class InvestorApplicationAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'investment_focus', 'user')
    search_fields = ('company_name', 'investment_focus')

