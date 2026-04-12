import json
import os
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import get_object_or_404, redirect, render
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
import requests
from estocasticos.use_cases.mbg_ito_use_case import GeneralizedBrownianMotionUseCase
from estocasticos.use_cases.modelo_reversao_media_use_case import ReversaoMediaUseCase
from estocasticos.use_cases.monte_carlos_use_case import MonteCarloUseCase
from estocasticos.use_cases.random_walk_normal_use_case import RandomWalkNormalUseCase
from estocasticos.use_cases.cadeia_markov_use_case import CadeiaMarkovUseCase
from estocasticos.use_cases.random_walk_use_case import RandomWalkUseCase
from financial_options.models import FinantialModels


def pagina_inicial(request):
    return render(request, "admin/login.html")

def perfil_view(request):
    context = {
        "first_name" : request.user.first_name,
        "last_name" : request.user.last_name
            }
    return render(request, "site/home/perfil.html", context)

def custom_admin_login(request):
    error_message = None
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            if user.is_superuser:
                return redirect("/admin/")
            else:
                return redirect("/home")
        else:
            error_message = "Incorrect username or password."

    else:
        form = AuthenticationForm()

    return render(
        request, "admin/login.html", {"form": form, "error_message": error_message}
    )


@login_required(login_url='/admin/login/')
def home_view(request):
    return render(request, "site/home/home.html")


@csrf_exempt
def set_language(request):
    if request.method == "POST":
        language = request.POST.get("language")
        if language in ["en", "pt"]:
            request.session["language"] = language
            return JsonResponse({"success": True})
    return JsonResponse({"success": False}, status=400)


def custom_logout(request):
    auth_logout(request)
    return redirect('login-customizado')

@login_required(login_url='/admin/login/')
def reference_view(request):
    return render(request, "site/home/references.html")

@login_required(login_url='/admin/login/')
def to_do_view(request):
    return render(request, "site/home/to_do_view.html")

from django.core.paginator import Paginator 

@login_required(login_url='/admin/login/')
def simulation_list_view(request):
    all_simulations = FinantialModels.objects.filter(usuario=request.user).order_by('-criado_em')

    paginator = Paginator(all_simulations, 10) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj 
    }
    return render(request, 'site/home/simulation_list.html', context)

@login_required
def download_report_view(request, simulation_id):
    simulation = get_object_or_404(FinantialModels, id=simulation_id, usuario=request.user)

    if not simulation.report:
        raise Http404("Report not found.")

    try:
        file_url = simulation.report.url
        response = requests.get(file_url, stream=True)
        response.raise_for_status() 
        filename = os.path.basename(simulation.report.name)
        
        http_response = HttpResponse(
            response.content,
            content_type=response.headers.get('content-type', 'application/octet-stream')
        )
        http_response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return http_response

    except requests.exceptions.RequestException as e:
        return HttpResponse(f"Error fetching file: {e}", status=500)


@login_required
def delete_simulation_view(request):
    try:
        data = json.loads(request.body)
        simulation_id = data.get('id')
        simulation = get_object_or_404(FinantialModels, id=simulation_id)
        if simulation.usuario != request.user:
            return JsonResponse({'status': 'error', 'message': 'Forbidden'}, status=403)
        
        simulation.delete()
        return JsonResponse({'status': 'success', 'message': 'Simulation deleted successfully.'})
    except:
        return JsonResponse({'status': 'error', 'message': 'Error deleting the project.'}, status=405)

