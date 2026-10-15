from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import resolve, reverse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from core.navigation import BY_SLUG, navigation_context


@login_required
@require_GET
@never_cache
def tool_page(request, slug='retorno-volatilidade', simulation_id=None):
    page = BY_SLUG.get(slug)
    if page is None:
        raise Http404
    enhanced = page.enhanced
    if simulation_id:
        from financial_options.models import FinantialModels, FinantialModelsChoices
        from financial_options.api.views import rerun_simulation_view
        simulation = get_object_or_404(FinantialModels, pk=simulation_id, usuario=request.user)
        enhanced = simulation.model_type == FinantialModelsChoices.RETURN_VOLATILITY
        page = BY_SLUG['retorno-volatilidade'] if enhanced else BY_SLUG['projetos']
        response = rerun_simulation_view(request, simulation_id)
    else:
        match = resolve(reverse(page.view))
        response = match.func(request, *match.args, **match.kwargs)
    if response.status_code != 200:
        return response
    context = navigation_context(request, page, simulation_id, enhanced)
    if simulation_id:
        title = context['page_title'] if enhanced else simulation.get_model_type_display()
        context['page_title'] = context['navigation']['title'] = f'{title} · {simulation.name}'
    context['initial_content'] = response.content.decode(response.charset)
    if request.headers.get('X-SAETO-Fragment') == '1':
        return JsonResponse({'html': context['initial_content'], 'page': context['navigation']})
    return render(request, 'site/home/home.html', context)


@login_required
@require_GET
@never_cache
def home_page(request):
    context = navigation_context(request)
    context['initial_content'] = render_to_string('site/home/welcome.html', request=request)
    if request.headers.get('X-SAETO-Fragment') == '1':
        return JsonResponse({'html': context['initial_content'], 'page': context['navigation']})
    return render(request, 'site/home/home.html', context)
