from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm




def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home') # Ensure you have a 'home' named URL
    else:
        form = UserCreationForm()
    return render(request, 'accounts/signup.html', {'form': form})

def profile_view(request, username):
    # Your profile logic here
    return render(request, 'accounts/profile.html', {'username': username})

class ContactView(LoginRequiredMixin, TemplateView):
    template_name = 'pages/contact.html'
    login_url = 'accounts:signup'

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')

    return render(request, 'accounts/login.html', {'form': form})