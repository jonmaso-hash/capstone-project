# matchmaking/context_processors.py
from .models import InvestorApplication  # Adjust import path if the model is in accounts.models

def investor_status(request):
    """
    Globally injects a boolean flag checking if the logged-in user 
    has an Investor Application.
    """
    if request.user.is_authenticated:
        # Check if an InvestorApplication exists matching this user
        is_investor = InvestorApplication.objects.filter(user=request.user).exists()
        return {'global_is_investor': is_investor}
    
    return {'global_is_investor': False}