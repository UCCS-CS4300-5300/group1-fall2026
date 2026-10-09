from django.shortcuts import render
from .models import StarterItem
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import logout, login
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from .forms import AccountCreationForm

@login_required
def home(request):
    items = StarterItem.objects.filter(is_active=True).order_by("title")
    return render(request, "core/home.html", {"items": items})

@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You've been logged out.")
    return redirect("login")

def account_creation(request):
    if request.method == "POST":
        form = AccountCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("core:home")
    else:
        form = AccountCreationForm()
    return render(request, "core/account_creation.html", {"form": form})