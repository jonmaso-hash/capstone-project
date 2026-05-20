# legal_api/admin.py
from django.contrib import admin
from .models import LegalContract, RiskFlag, ConflictEvaluation

@admin.register(LegalContract)
class LegalContractAdmin(admin.ModelAdmin):
    # Columns displayed in the admin dashboard list view
    list_display = ('contract_type', 'governing_jurisdiction', 'uploaded_at')
    
    # Allows you to filter results by jurisdiction or upload date in the sidebar
    list_filter = ('governing_jurisdiction', 'uploaded_at')
    
    # Adds a search bar targeting specific contract metadata fields
    search_fields = ('contract_type', 'governing_jurisdiction')
    
    # Automatically organizes fields by newest records first
    ordering = ('-uploaded_at',)


@admin.register(RiskFlag)
class RiskFlagAdmin(admin.ModelAdmin):
    list_display = ('contract', 'clause_type', 'severity', 'created_at')
    list_filter = ('severity', 'clause_type')
    search_fields = ('contract__contract_type', 'issue', 'original_text_snippet')


@admin.register(ConflictEvaluation)
class ConflictEvaluationAdmin(admin.ModelAdmin):
    list_display = ('adversary_party_name', 'conflict_status', 'confidence_score', 'evaluated_at')
    list_filter = ('conflict_status', 'evaluated_at')
    search_fields = ('adversary_party_name', 'matter_description', 'system_rationale')
    ordering = ('-evaluated_at',)