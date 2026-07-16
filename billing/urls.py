from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('', views.billing_page, name='billing_page'),
    path('checkout/', views.create_checkout_session, name='create_checkout_session'),
    path('portal/', views.create_billing_portal_session, name='create_billing_portal_session'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
]
