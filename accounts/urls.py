from django.urls import path
from . import views

# This 'app_name' is the "namespace". 
# It allows you to use {% url 'accounts:profile' %} in templates.
app_name = 'accounts'

urlpatterns = [
    # Signup View
    # If using a Class Based View, use views.SignUpView.as_view()
    # If using a function, use views.signup_view
    path('signup/', views.signup_view, name='signup'),

    # Profile View
    # This matches the 'user.username' argument in your template
    path('profile/<str:username>/', views.profile_view, name='profile'),
]