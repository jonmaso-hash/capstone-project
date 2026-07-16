from django.contrib import admin
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib import messages
from .models import (
    Application, InvestorApplication, AIMatch, Connection, MatchFeedback, InvestorInterestEvent,
    APIKey, InvestorPredictionSnapshot,
    SellerApplication, BuyerApplication, AcquisitionConnection, DealFeedback, AcquisitionInterestEvent,
    BuyerPredictionSnapshot, BusinessEmailVerification,
    DataRoomDocument, DataRoomAccessRequest, DataRoomDocumentView,
    PitchVideoComment,
)
from django.core.mail import EmailMessage
from django.conf import settings
from django.template.loader import render_to_string

@admin.action(description="Approve selected profile(s)")
def approve_profiles(modeladmin, request, queryset):
    updated = queryset.update(review_status='APPROVED', denial_reason='')
    modeladmin.message_user(request, f"Approved {updated} profile(s).", messages.SUCCESS)


@admin.action(description="Deny selected profile(s)")
def deny_profiles(modeladmin, request, queryset):
    if 'apply' in request.POST:
        reason = request.POST.get('denial_reason', '').strip()
        updated = queryset.update(review_status='DENIED', denial_reason=reason)
        modeladmin.message_user(request, f"Denied {updated} profile(s).", messages.SUCCESS)
        return HttpResponseRedirect(request.get_full_path())

    return render(request, 'admin/matchmaking/deny_profiles.html', {
        'objects': queryset,
        'action_name': 'deny_profiles',
        'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
    })


@admin.action(description="Forward selected Founder(s) to an Investor")
def forward_to_investor(modeladmin, request, queryset):
    if 'apply' in request.POST:
        investor_id = request.POST.get('investor')
        investor = InvestorApplication.objects.get(id=investor_id)
        
        connections_created = 0
        connections_updated = 0
        
        for founder in queryset:
            # 1. Database Logic: Get or Create the connection
            obj, created = Connection.objects.get_or_create(
                founder=founder, 
                investor=investor,
                defaults={'status': 'requested'} 
            )
            
            if not created:
                obj.status = 'requested'
                obj.save()
                connections_updated += 1
            else:
                connections_created += 1
            
            # 2. Email Logic: Render HTML and send
            try:
                html_content = render_to_string('emails/founder_match.html', {
                    'founder': founder,
                    'investor': investor,
                })
                
                msg = EmailMessage(
                    subject=f"Exclusive Founder Profile: {founder.company_name}",
                    body=html_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[investor.email],
                )
                msg.content_subtype = "html" 
                msg.send()
                
            except Exception as e:
                modeladmin.message_user(request, f"Error sending email to {investor.full_name}: {e}", messages.ERROR)

        # 3. Final Admin Feedback
        total_processed = connections_created + connections_updated
        modeladmin.message_user(
            request, 
            f"Success: Processed {total_processed} profile(s) for {investor.full_name}. ({connections_created} New, {connections_updated} Updated).", 
            messages.SUCCESS
        )
        return HttpResponseRedirect(request.get_full_path())
    
    # Selection page rendering
    active_investors = InvestorApplication.objects.all() 
    return render(request, 'admin/matchmaking/forward_to_investor.html', {
        'founders': queryset,
        'investors': active_investors,
        'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
    })
    
    # Render the selection page
    active_investors = InvestorApplication.objects.all() 
    return render(request, 'admin/matchmaking/forward_to_investor.html', {
        'founders': queryset,
        'investors': active_investors,
        'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
    })


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    # Merged the fields from both snippets so you keep all your columns and filters
    list_display = ('user', 'company_name', 'sector', 'stage', 'is_verified', 'review_status', 'created_at')
    list_filter = ('sector', 'stage', 'is_private', 'is_verified', 'review_status')
    list_editable = ('is_verified',)
    search_fields = ('company_name', 'user__username', 'email')
    readonly_fields = ('created_at', 'updated_at')

    # Registered the custom action here
    actions = [forward_to_investor, approve_profiles, deny_profiles]


@admin.register(InvestorApplication)
class InvestorApplicationAdmin(admin.ModelAdmin):
    list_display = ("company_name", "full_name", "investment_stage", "investment_amount", "is_private", "is_verified", "is_premium", "review_status", "created_at")
    list_filter = ("investment_stage", "is_private", "is_verified", "is_premium", "review_status")
    list_editable = ("is_verified", "is_premium")
    search_fields = ("company_name", "full_name", "email", "investment_focus")
    readonly_fields = ("created_at", "updated_at")
    actions = [approve_profiles, deny_profiles]


@admin.register(AIMatch)
class AIMatchAdmin(admin.ModelAdmin):
    list_display = ("investor", "get_founder_company", "score", "created_at")
    list_filter = ("score", "created_at")
    readonly_fields = ("created_at",)

    def get_founder_company(self, obj):
        """Safely fetches target venture name from relation link."""
        return obj.application.company_name
    get_founder_company.short_description = "Founder Company"


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    # Note: If your model field is named 'application' instead of 'founder', update 'founder' below
    list_display = ("investor", "founder", "status", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("investor__company_name", "founder__company_name")


@admin.register(MatchFeedback)
class MatchFeedbackAdmin(admin.ModelAdmin):
    list_display = ("user", "application", "investor", "vote", "created_at")
    list_filter = ("vote", "created_at")
    
@admin.register(InvestorInterestEvent)
class InvestorInterestEventAdmin(admin.ModelAdmin):
    list_display = ['investor', 'founder', 'event_type', 'created_at']
    list_filter = ['event_type', 'created_at']
    search_fields = ['investor__username', 'founder__company_name']
    readonly_fields = ['created_at']


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ['firm_name', 'owner', 'key_preview', 'is_active', 'created_at', 'last_used_at']
    list_editable = ['is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['firm_name', 'owner__username']
    readonly_fields = ['key', 'created_at', 'last_used_at']

    def key_preview(self, obj):
        return f"···{obj.key[-4:]}" if obj.key else "—"
    key_preview.short_description = 'Key'


@admin.register(BusinessEmailVerification)
class BusinessEmailVerificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'business_email', 'status', 'attempts', 'created_at', 'expires_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'business_email']
    readonly_fields = ['code', 'created_at', 'verified_at']


@admin.register(DataRoomDocument)
class DataRoomDocumentAdmin(admin.ModelAdmin):
    list_display = ['label', 'founder', 'category', 'uploaded_at']
    list_filter = ['category', 'uploaded_at']
    search_fields = ['label', 'founder__company_name']


@admin.register(DataRoomAccessRequest)
class DataRoomAccessRequestAdmin(admin.ModelAdmin):
    list_display = ['document', 'investor', 'status', 'requested_at', 'decided_at']
    list_filter = ['status', 'requested_at']
    search_fields = ['document__label', 'investor__company_name']


@admin.register(DataRoomDocumentView)
class DataRoomDocumentViewAdmin(admin.ModelAdmin):
    list_display = ['document', 'viewer', 'created_at']
    readonly_fields = ['document', 'viewer', 'created_at']

    def has_add_permission(self, request):
        return False


@admin.register(PitchVideoComment)
class PitchVideoCommentAdmin(admin.ModelAdmin):
    list_display = ['author', 'founder', 'seller', 'created_at']
    list_filter = ['created_at']
    search_fields = ['author__username', 'founder__company_name', 'seller__company_name', 'body']


@admin.register(InvestorPredictionSnapshot)
class InvestorPredictionSnapshotAdmin(admin.ModelAdmin):
    """
    Staff-only visibility for the shadow prediction engine — never surfaced
    to end users. Lets us inspect predictions and grading accuracy directly.
    """
    list_display = ['investor', 'predicted_founder', 'predicted_score', 'is_resolved', 'grade', 'created_at']
    list_filter = ['is_resolved', 'grade', 'created_at']
    search_fields = ['investor__company_name', 'predicted_founder__company_name']
    readonly_fields = ['created_at', 'resolved_at']


@admin.register(SellerApplication)
class SellerApplicationAdmin(admin.ModelAdmin):
    list_display = ('user', 'company_name', 'industry', 'asking_price', 'is_verified', 'review_status', 'created_at')
    list_filter = ('industry', 'deal_structure', 'is_private', 'is_verified', 'review_status')
    list_editable = ('is_verified',)
    search_fields = ('company_name', 'user__username', 'email')
    readonly_fields = ('created_at', 'updated_at')
    actions = [approve_profiles, deny_profiles]


@admin.register(BuyerApplication)
class BuyerApplicationAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'full_name', 'budget_min', 'budget_max', 'is_private', 'is_verified', 'is_premium', 'review_status', 'created_at')
    list_filter = ('is_private', 'is_verified', 'is_premium', 'review_status')
    list_editable = ('is_verified', 'is_premium')
    search_fields = ('company_name', 'full_name', 'email', 'acquisition_thesis')
    readonly_fields = ('created_at', 'updated_at')
    actions = [approve_profiles, deny_profiles]


@admin.register(AcquisitionConnection)
class AcquisitionConnectionAdmin(admin.ModelAdmin):
    list_display = ("buyer", "seller", "status", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("buyer__company_name", "seller__company_name")


@admin.register(DealFeedback)
class DealFeedbackAdmin(admin.ModelAdmin):
    list_display = ("user", "seller", "buyer", "vote", "created_at")
    list_filter = ("vote", "created_at")


@admin.register(AcquisitionInterestEvent)
class AcquisitionInterestEventAdmin(admin.ModelAdmin):
    list_display = ['buyer', 'seller', 'event_type', 'created_at']
    list_filter = ['event_type', 'created_at']
    search_fields = ['buyer__username', 'seller__company_name']
    readonly_fields = ['created_at']


@admin.register(BuyerPredictionSnapshot)
class BuyerPredictionSnapshotAdmin(admin.ModelAdmin):
    """
    Staff-only visibility for the Business Marketplace's shadow prediction
    engine — never surfaced to end users.
    """
    list_display = ['buyer', 'predicted_seller', 'predicted_score', 'is_resolved', 'grade', 'created_at']
    list_filter = ['is_resolved', 'grade', 'created_at']
    search_fields = ['buyer__company_name', 'predicted_seller__company_name']
    readonly_fields = ['created_at', 'resolved_at']