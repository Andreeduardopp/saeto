import json
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator # For token generation
from django.contrib.sites.shortcuts import get_current_site # For building activation link
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib import messages
from django.urls import reverse 

def sing_up_template(request):
    return render(request, "site/usuario/cadastro.html")


LOGIN_URL_NAME = 'custom_login_template' 

def login_template(request):
    return render(request, "admin/login.html")

def send_verification_email(request, user):
    current_site = get_current_site(request)
    mail_subject = 'Activate your account.'
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    activation_link = reverse('account_verification_sent', kwargs={'uidb64': uid, 'token': token}) 
    
    message = render_to_string('account/email/account_activation_email.html', { 
        'user': user,
        'domain': current_site.domain,
        'activation_link': f"http://{current_site.domain}{activation_link}", # Construct full link
    })
    
    try:
        send_mail(mail_subject, message, 'saeto-pb@utfpr.edu.br', [user.email])
        return True
    except Exception as e:
        return False
    


def singup_view(request):
    if request.method == "POST":
        username = request.POST.get("username") 
        email = request.POST.get("email")
        password = request.POST.get("password1") 
        password2 = request.POST.get("password2")


        if not all([username, email, password, password2]):
            messages.error(request, "All fields are required.")
            return render(request, "site/usuario/cadastro.html", {"error_message": "All fields are required."})

        if password != password2: 
            messages.error(request, "The passwords don't match.")
            return render(request, "site/usuario/cadastro.html", {"error_message": "The passwords don't match."})
        
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return render(request, "site/usuario/cadastro.html", {"error_message": "Username already exists."})

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return render(request, "site/usuario/cadastro.html", {"error_message": "Email already registered."})

        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            user.is_active = False 
            user.save()

            email_sent = send_verification_email(request, user)

            if email_sent:
                messages.success(request, "Registration successful! Please check your email to verify your account before logging in.")
            else:
                messages.error(request, "Registration successful, but we couldn't send a verification email. Please contact support.")
            

            return redirect(reverse(LOGIN_URL_NAME)) 

        except Exception as e:
            messages.error(request, f"An error occurred during registration: {str(e)}")
            return render(request, "site/usuario/cadastro.html", {"error_message": f"An error occurred: {str(e)}"})

    return render(request, "site/usuario/cadastro.html")

from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth import login as auth_login

def verify_email_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Your email has been verified! You can now log in.')
        return redirect(reverse(LOGIN_URL_NAME))
    else:
        messages.error(request, 'Activation link is invalid or has expired.')
        return redirect(reverse(LOGIN_URL_NAME)) 
    
def update_profile_view(request):
    try:
        first_name = request.POST.get('first_name', '').strip()

        last_name = request.POST.get('last_name', '').strip() 

        if not first_name or not last_name:
            return JsonResponse({'status': 'error', 'message': 'First and last name are required.'}, status=400)

        # Update the user object
        user = request.user
        user.first_name = first_name
        user.last_name = last_name
        user.save()

        # Send a success response
        context = {
        "first_name" : request.user.first_name,
        "last_name" : request.user.last_name
            }
        return redirect("/home")

    except json.JSONDecodeError as e:
        print(e)
        return redirect("/home")
    except Exception as e:
        print(e)
        return redirect("/home")
