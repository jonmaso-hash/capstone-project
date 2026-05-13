from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='root'),
    path('home/', views.home_view, name='home'),
    path('services', views.services, name='services'),
    path('about', views.about, name= 'about'),
    path('contact/', views.contact_view, name='contact'),
    path('bulletin_board/', views.bulletin_board, name='bulletin_board'),

]