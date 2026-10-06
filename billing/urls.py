from django.urls import path
from . import views
from . import zelda_views

app_name = 'billing'

urlpatterns = [
    path('zelda/catalog/', zelda_views.product_catalog, name='zelda_catalog'),
    path('zelda/search/', zelda_views.external_search, name='zelda_external_search'),
    path('zelda/intake/', zelda_views.product_intake, name='zelda_intake'),
    path('zelda/checkout/', zelda_views.product_checkout, name='zelda_checkout'),
    path('zelda/orders/<uuid:order_id>/', zelda_views.order_page, name='zelda_order'),
    path('zelda/orders/<uuid:order_id>/status/', zelda_views.order_status, name='zelda_order_status'),
    path('zelda/orders/<uuid:order_id>/retry/', zelda_views.retry_order, name='zelda_order_retry'),
    path('zelda/orders/<uuid:order_id>/reports/<str:report_key>/', zelda_views.purchased_report, name='zelda_report'),
    path('', views.billing_page, name='billing_page'),
    path('checkout/', views.create_checkout_session, name='create_checkout_session'),
    path('checkout/firm/', views.create_firm_checkout_session, name='create_firm_checkout_session'),
    path('checkout/valuation/', views.create_valuation_purchase_checkout_session, name='create_valuation_purchase_checkout_session'),
    path('firm/join/', views.join_firm, name='join_firm'),
    path('cancel/', views.cancel_subscription, name='cancel_subscription'),
    path('portal/', views.create_billing_portal_session, name='create_billing_portal_session'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
]
