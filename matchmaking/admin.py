from django.contrib import admin
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib import messages
from .models import Application, InvestorApplication, AIMatch, Connection, MatchFeedback
from django.core.mail import EmailMessage
from django.conf import settings
from django.template.loader import render_to_string

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
    list_display = ('user', 'company_name', 'sector', 'stage', 'created_at')
    list_filter = ('sector', 'stage', 'is_private')
    search_fields = ('company_name', 'user__username', 'email')
    readonly_fields = ('created_at', 'updated_at')
    
    # Registered the custom action here
    actions = [forward_to_investor]


@admin.register(InvestorApplication)
class InvestorApplicationAdmin(admin.ModelAdmin):
    list_display = ("company_name", "full_name", "investment_stage", "investment_amount", "is_private", "created_at")
    list_filter = ("investment_stage", "is_private")
    search_fields = ("company_name", "full_name", "email", "investment_focus")
    readonly_fields = ("created_at", "updated_at")


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