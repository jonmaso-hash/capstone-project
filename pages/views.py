from django.shortcuts import render, redirect  # Added redirect here
from django.core.mail import send_mail 
from django.contrib import messages 
from .forms import contactForm  # Added your form import back

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
            company_name = form.cleaned_data['company']
            phone_number = form.cleaned_data['phone']
            message = form.cleaned_data['message']

            # Formatted string for the email content
            message_body = (
                f'You have a new inquiry\n\n'
                f'Name: {name}\n'
                f'Email: {email}\n'
                f'Company Name: {company_name}\n'
                f'Phone Number: {phone_number}\n\n'
                f'Message:\n{message}'
            )

            try:
                send_mail(
                    subject=f"Email From KCV Capital: {name}",
                    message=message_body,
                    from_email=None,      # Uses EMAIL_HOST_USER from settings.py
                    recipient_list=['jonmaso@gmail.com'],
                    fail_silently=False,
                )
                messages.success(request, "Message sent successfully!")
                return redirect('contact') # This clears the form and shows the success message

            except Exception as e:
                messages.error(request, f"Error sending email: {e}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = contactForm()

    return render(request, 'pages/contact.html', {'form': form})