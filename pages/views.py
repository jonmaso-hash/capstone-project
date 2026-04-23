from django.shortcuts import render
from .forms import contactForm
from django.core.mail import send_mail 

# Create your views here.
# Create your views here.
def home_view(request):
    return render(request, 'pages/home.html')

def services(request):
    return render(request, 'pages/services.html')

def about(request):
    return render(request, 'pages/about.html')

def contact_view(request):
    if request.method == 'POST':
        form = contactForm(request.POST)

        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            message = form.cleaned_data['message']

            message_body = (
                f'You have a new email from your portfolio\n'
                f'Name: {name}\n'
                f'Email: {email}\n'
                f'Message: {message}\n'
            )

            try:
                send_mail(
                    "Email From Portfolio",
                    message_body,
                    email,
                    ['jonmaso@gmail.com'],
                )
                print("Email sent successfully")
                form = contactForm()  # reset form after success

            except Exception as e:
                print(f'Error sending email: {e}')

        else:
            print("Form is not valid")
            print(form.errors)

    else:
        form = contactForm()

    return render(request, 'pages/contact.html', {'form': form})