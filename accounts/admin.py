from django.contrib import admin
from .models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("company_name", "founder_name", "email", "created_at")
    search_fields = ("company_name", "founder_name", "email")
    list_filter = ("sector", "stage", "created_at")