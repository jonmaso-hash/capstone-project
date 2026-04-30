from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login

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