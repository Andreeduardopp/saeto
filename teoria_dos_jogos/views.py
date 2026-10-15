from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from estocasticos.api.inputs import InvalidInput, format_bound, read_choice, read_number
from .use_cases.dilema_prisioneiro_use_case import (
    DEFAULT_ITERATIONS, HISTORY_PAGE_SIZE, MAX_ITERATIONS, MIN_ITERATIONS, STRATEGIES,
    DilemaPrisioneiroUseCase,
)

TEMPLATE = 'site/teoria_dos_jogos/dilema_prisioneiro.html'

PLAYER_1 = ('Estratégia do Jogador 1', "Player 1's strategy")
PLAYER_2 = ('Estratégia do Jogador 2', "Player 2's strategy")
ITERATIONS = ('Iterações', 'Iterations')


@login_required(login_url='/admin/login/')
def dilema_do_prisioneiro_view(request):
    """
    The iterated prisoner's dilemma.

    The limits live here, on the server, so a screen cannot skip them; the
    message comes back in the session language and the screen shows it as is.
    """
    language = request.session.get('language', 'pt')
    if request.method != 'POST':
        return render(request, TEMPLATE, {
            'language': language,
            'iterations': DEFAULT_ITERATIONS,
            'min_iterations': MIN_ITERATIONS,
            'max_iterations': MAX_ITERATIONS,
            # The bounds written the way the server's message writes them, so the
            # screen and the message name the same limit the same way.
            'min_iterations_text': format_bound(MIN_ITERATIONS, language),
            'max_iterations_text': format_bound(MAX_ITERATIONS, language),
            'history_page_size': HISTORY_PAGE_SIZE,
        })

    try:
        strategy1 = read_choice(request.POST, 'strategy1', PLAYER_1, STRATEGIES)
        strategy2 = read_choice(request.POST, 'strategy2', PLAYER_2, STRATEGIES)
        iterations = read_number(request.POST, 'iterations', ITERATIONS,
                                 minimum=MIN_ITERATIONS, maximum=MAX_ITERATIONS, integer=True)
    except InvalidInput as error:
        return JsonResponse({'error': error.message(language)}, status=400)

    result = DilemaPrisioneiroUseCase(strategy1, strategy2, iterations).run_simulation()
    return JsonResponse({
        'result': result,
        'strategy1': strategy1,
        'strategy2': strategy2,
        'iterations': iterations,
    })
