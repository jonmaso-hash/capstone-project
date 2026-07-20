from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('', views.billing_page, name='billing_page'),
    path('checkout/', views.create_checkout_session, name='create_checkout_session'),
    path('checkout/firm/', views.create_firm_checkout_session, name='create_firm_checkout_session'),
    path('checkout/valuation/', views.create_valuation_purchase_checkout_session, name='create_valuation_purchase_checkout_session'),
    path('firm/join/', views.join_firm, name='join_firm'),
    path('portal/', views.create_billing_portal_session, name='create_billing_portal_session'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
]
