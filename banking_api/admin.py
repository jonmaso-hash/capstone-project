from django.contrib import admin
from .models import Transaction

# MUTED UNTIL WE LOCATE/BUILD THE MODEL (Do not delete)
# from accounts.models import LedgerAccount

# @admin.register(LedgerAccount)
# class LedgerAccountAdmin(admin.ModelAdmin):
#     list_display = (...)
#     ... (add a # in front of every line of this specific class)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    # Added 'idempotency_key', 'compliance_status' for visibility
    list_display = (
        'reference_id', 'account', 'amount', 'transaction_type', 
        'status', 'compliance_status', 'idempotency_key', 'execution_timestamp'
    )
    list_filter = ('transaction_type', 'status', 'compliance_status', 'execution_timestamp')
    search_fields = ('reference_id', 'account__account_number', 'description', 'idempotency_key')
    readonly_fields = ('idempotency_key',) # Protecting integrity
    ordering = ('-execution_timestamp',)