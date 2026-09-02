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
from .models import Application, InvestorApplication
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

    def get(self, request):
        queryset, filters = _filtered_public_applications(request)
        results = [{
            'company_name': app.company_name,
            'sector': app.sector,
            'stage': app.stage,
            'location': app.geography,
            'raising_amount': str(app.raising_amount) if app.raising_amount is not None else None,
            'current_revenue': str(app.current_revenue) if app.current_revenue is not None else None,
            'team_size': app.team_size,
            'years_in_business': app.years_in_business,
            'website': app.company_website,
        } for app in queryset[:100]]

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
