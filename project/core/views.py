from .models_repkin import Repkin
from django.shortcuts import render
from .models import StarterItem
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import logout, login
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from .forms import AccountCreationForm, RepkinSetupForm


DEFAULT_REPKIN = {"mood": "content", "color": "green"}

def get_repkin(user):
    repkin, _ = Repkin.objects.get_or_create(owner=user, defaults=DEFAULT_REPKIN)
    return repkin

@login_required
def repkin_setup(request):
    if request.method != "POST":
        return redirect("core:home")
    repkin = get_repkin(request.user)
    form = RepkinSetupForm(request.POST, instance=repkin)
    if form.is_valid():
        repkin = form.save(commit=False)
        repkin.setup_complete = True
        repkin.save()
        return redirect("core:home")
    repkin.refresh_from_db()
    return render_home(request, repkin, form, open_setup=True)

@login_required
def home(request):
    repkin = get_repkin(request.user)
    return render_home(request, repkin, RepkinSetupForm(instance=repkin))

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

def render_home(request, repkin, setup_form, open_setup=False):
    items = StarterItem.objects.filter(is_active=True).order_by("title")
    context = {
        "items": items,
        "repkin": repkin,
        "setup_form": setup_form,
        "open_setup": open_setup,
    }
    return render(request, "core/home.html", context)