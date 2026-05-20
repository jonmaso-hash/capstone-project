from django.contrib import admin
from .models import LedgerAccount, Transaction

@admin.register(LedgerAccount)
class LedgerAccountAdmin(admin.ModelAdmin):
    list_display = ('account_number', 'user', 'account_type', 'balance', 'currency', 'created_at')
    list_filter = ('account_type', 'currency')
    search_fields = ('account_number', 'user__username')
    ordering = ('-created_at',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('reference_id', 'account', 'transaction_type', 'amount', 'status', 'execution_timestamp')
    list_filter = ('transaction_type', 'status', 'execution_timestamp')
    search_fields = ('reference_id', 'account__account_number', 'description')
    ordering = ('-execution_timestamp',)