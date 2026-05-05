from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Auth
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),

    # Profile
    path('profile/', views.profile, name='profile'),

    #  NEW: Founder application flow
    path('apply/', views.seeking_investment, name='apply'),
    
    # Investor application 
    path('investor-form/', views.investor_form, name= 'investor')
]