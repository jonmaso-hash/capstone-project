# matchmaking/enterprise_views.py
"""
Enterprise API tier — read-only endpoints external firms can consume with
an APIKey (see api_auth.py). Deliberately narrow: curated public fields
only, same privacy rules as the internal global_search/CSV export
(is_private=False, excludes DENIED), never raw model dumps.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .api_auth import APIKeyAuthentication, APIKeyRateThrottle
from .models import Application, InvestorApplication, visible_profile_fields
from .views import _filtered_public_applications


class EnterpriseFounderSearchView(APIView):
    """
    GET /api/v1/enterprise/founders/
    Same filters as the internal global_search (state, location, industry,
    stage, capital, revenue query params), curated fields only.
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [APIKeyRateThrottle]

    # Founder-controlled fields, and the JSON key each is published under.
    # raising_amount and current_revenue were published here unconditionally,
    # despite being login-gated everywhere else: an API-key holder received
    # financial figures the founder had disclosed to nobody.
    CONTROLLED_FIELDS = {
        'sector': 'sector',
        'stage': 'stage',
        'geography': 'location',
        'raising_amount': 'raising_amount',
        'current_revenue': 'current_revenue',
        'team_size': 'team_size',
        'years_in_business': 'years_in_business',
        'company_website': 'website',
    }

    def get(self, request):
        queryset, filters = _filtered_public_applications(request)
        results = []
        for app in queryset[:100]:
            shown = visible_profile_fields(request.user, app, self.CONTROLLED_FIELDS)
            row = {'company_name': app.company_name}
            for field, key in self.CONTROLLED_FIELDS.items():
                if field not in shown:
                    # Omitted, never null: a null still says the field exists
                    # and was withheld, and invites a consumer to read it as
                    # "this company has no revenue".
                    continue
                value = shown[field]
                row[key] = str(value) if field in ('raising_amount', 'current_revenue') and value is not None else value
            results.append(row)

        return Response({
            'count': len(results),
            'filters_applied': filters,
            'results': results,
        })


class EnterprisePlatformStatsView(APIView):
    """
    GET /api/v1/enterprise/stats/
    High-level, non-sensitive platform counts — no per-user data.
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [APIKeyRateThrottle]

    def get(self, request):
        founder_count = Application.objects.discoverable().exclude(review_status='DENIED').count()
        investor_count = InvestorApplication.objects.discoverable().exclude(review_status='DENIED').count()
        return Response({
            'founder_count': founder_count,
            'investor_count': investor_count,
        })
