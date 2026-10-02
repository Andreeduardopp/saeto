from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from estocasticos.api.inputs import InvalidInput, check_grid, read_choice, read_number, read_seed
from estocasticos.use_cases.abm_use_case import ArithmeticBrownianMotionUseCase
from estocasticos.use_cases.cadeia_markov_use_case import CadeiaMarkovUseCase
from estocasticos.use_cases.comparacao_modelos_use_case import ComparacaoModelosUseCase
from estocasticos.use_cases.mbg_ito_use_case import GeometricBrownianMotionUseCase
from estocasticos.use_cases.modelo_reversao_media_use_case import ReversaoMediaUseCase
from estocasticos.use_cases.monte_carlos_use_case import PERIOD_IN_YEARS, MonteCarloUseCase
from estocasticos.use_cases.random_walk_normal_use_case import RandomWalkNormalUseCase
from estocasticos.use_cases.random_walk_use_case import RandomWalkUseCase
from estocasticos.use_cases.simulation_support import number_of_steps
from financial_options.api.views import _render_screen
from financial_options.models import FinantialModelsChoices as Choices

LOGIN_URL = '/admin/login/'


def _language(request):
    return request.session.get('language', 'pt')


# --------------------------- pages -------------------------------------------

@login_required(login_url=LOGIN_URL)
def processos_home(request):
    return render(request, "site/processos-estocasticos/processos_home.html")


@login_required(login_url=LOGIN_URL)
def cadeia_markov(request):
    return _render_screen(request, Choices.MARKOV_CHAIN)


@login_required(login_url=LOGIN_URL)
def random_walk_overview(request):
    return render(request, "site/processos-estocasticos/random_walk_overview.html")


@login_required(login_url=LOGIN_URL)
def random_walk_normal(request):
    return _render_screen(request, Choices.RANDOM_WALK_NORMAL)


@login_required(login_url=LOGIN_URL)
def random_walk_template(request):
    return _render_screen(request, Choices.RANDOM_WALK)


@login_required(login_url=LOGIN_URL)
def monte_carlos(request):
    return _render_screen(request, Choices.GBM_MONTE_CARLO)


@login_required(login_url=LOGIN_URL)
def mbg_overview(request):
    return render(request, "site/processos-estocasticos/mbg_overview.html")


@login_required(login_url=LOGIN_URL)
def mbg_ito(request):
    return _render_screen(request, Choices.GBM_ITO)


@login_required(login_url=LOGIN_URL)
def abm(request):
    return _render_screen(request, Choices.ARITHMETIC_BROWNIAN_MOTION)


@login_required(login_url=LOGIN_URL)
def mbg_teoria(request):
    return render(request, "site/teoria/mbg.html")


@login_required(login_url=LOGIN_URL)
def modelo_reversao_media(request):
    return _render_screen(request, Choices.MEAN_REVERSION)


@login_required(login_url=LOGIN_URL)
def vizualizacao_modelos(request):
    return _render_screen(request, Choices.MODELS_COMPARISON)


comparacao_modelos_template = vizualizacao_modelos


@login_required(login_url=LOGIN_URL)
def teoria_opcoes_financeiras(request):
    return render(request, "partials/teoria_opcoes_financeiras.html")


@login_required(login_url=LOGIN_URL)
def teoria_opcoes_reais(request):
    return render(request, "partials/teoria_opcoes_reais.html")


# --------------------------- calculations ------------------------------------

def calculation(handler):
    """Logged-in POST only; an InvalidInput becomes a 400 with the message in the session language."""
    @login_required(login_url=LOGIN_URL)
    @require_POST
    @wraps(handler)
    def view(request):
        language = _language(request)
        try:
            return JsonResponse(handler(request.POST, language))
        except InvalidInput as error:
            return JsonResponse({'error': error.message(language)}, status=400)
    return view


SIMULATIONS = ('Número de simulações', 'Number of simulations')
HORIZON = ('Horizonte de tempo (T)', 'Time horizon (T)')
TIME_STEP = ('Passo de tempo (dt)', 'Time step (dt)')
VOLATILITY = ('Volatilidade (σ)', 'Volatility (σ)')
DRIFT = ('Drift (μ)', 'Drift (μ)')


def _read_diffusion_grid(data):
    """T, dt and the number of simulations, checked so the run stays small."""
    T = read_number(data, 'T', HORIZON, above=0, maximum=100)
    dt = read_number(data, 'dt', TIME_STEP, above=0)
    if dt > T:
        raise InvalidInput('O passo de tempo (dt) não pode ser maior que o horizonte (T).',
                           'The time step (dt) cannot be greater than the horizon (T).')
    n_simulations = read_number(data, 'n_simulations', SIMULATIONS, minimum=2, maximum=1000, integer=True)
    check_grid(number_of_steps(T, dt), n_simulations)
    return T, dt, n_simulations


def _diffusion_response(model):
    return {
        'paths_plot': model.plot_paths(),
        'distribution_plot': model.plot_distribution(),
        'statistics': model.statistics(),
        'seed': model.seed,
    }


@calculation
def markov_simulator(data, language):
    num_states = read_number(data, 'num_states', ('Número de estados', 'Number of states'), minimum=2, maximum=10, integer=True)
    states = [name.strip() for name in data.get('states', '').split(',')]
    if len(states) != num_states or not all(states):
        raise InvalidInput(
            f'Informe {num_states} nomes de estados, separados por vírgula.',
            f'Enter {num_states} state names, separated by commas.',
        )
    if len(set(states)) != len(states):
        raise InvalidInput('Os nomes dos estados devem ser diferentes.', 'The state names must be different.')

    matrix = []
    for i in range(num_states):
        row = [
            read_number(data, f'transition_matrix[{i}][{j}]', (f'P({states[i]} → {states[j]})',) * 2, minimum=0, maximum=100)
            for j in range(num_states)
        ]
        if abs(sum(row) - 100) > 0.01:
            raise InvalidInput(
                f'A linha "{states[i]}" da matriz de transição soma {sum(row):g}%; deve somar 100%.',
                f'Row "{states[i]}" of the transition matrix adds up to {sum(row):g}%; it must add up to 100%.',
            )
        matrix.append([value / 100 for value in row])

    initial = [
        read_number(data, f'initial_percentages[{i}]', (f'Inicial ({states[i]})', f'Initial ({states[i]})'), minimum=0, maximum=100)
        for i in range(num_states)
    ]
    if abs(sum(initial) - 100) > 0.01:
        raise InvalidInput(
            f'As porcentagens iniciais somam {sum(initial):g}%; devem somar 100%.',
            f'The initial percentages add up to {sum(initial):g}%; they must add up to 100%.',
        )
    iterations = read_number(data, 'iterations', ('Número de iterações', 'Number of iterations'), minimum=1, maximum=50, integer=True)

    chain = CadeiaMarkovUseCase(states, matrix, [value / 100 for value in initial], iterations, language)
    evolution = chain.simulate()
    return {'plot': chain.generate_plot(evolution), 'evolution': evolution, 'states': states}


@calculation
def random_walk_view(data, language):
    steps = read_number(data, 'steps', ('Número de passos', 'Number of steps'), minimum=1, maximum=10000, integer=True)
    walk = RandomWalkUseCase(steps, read_seed(data), language)
    return {'plot_image': walk.generate_plot(), 'statistics': walk.statistics(), 'seed': walk.seed}


@calculation
def random_walk_normal_view(data, language):
    paths = read_number(data, 'paths', ('Número de caminhos', 'Number of paths'), minimum=1, maximum=20, integer=True)
    steps = read_number(data, 'steps', ('Número de passos', 'Number of steps'), minimum=4, maximum=100, integer=True)
    walks = RandomWalkNormalUseCase(steps, paths, read_seed(data), language)
    return {
        'walk_plot': walks.plot_walks(),
        'histograms_plot': walks.plot_histograms(),
        'statistics': walks.statistics(),
        'seed': walks.seed,
    }


@calculation
def monte_carlo_view(data, language):
    S0 = read_number(data, 'S0', ('Preço inicial (S0)', 'Initial price (S0)'), above=0)
    mu = read_number(data, 'mu', ('Retorno anual (μ)', 'Annual return (μ)'), minimum=-1, maximum=1)
    sigma = read_number(data, 'sigma', VOLATILITY, above=0, maximum=2)
    time_unit = read_choice(data, 'time_unit', ('Unidade de tempo', 'Time unit'), PERIOD_IN_YEARS)
    num_periods = read_number(data, 'num_periods', ('Número de períodos', 'Number of periods'), minimum=1, maximum=1000, integer=True)
    num_simulations = read_number(data, 'num_simulations', SIMULATIONS, minimum=2, maximum=100000, integer=True)
    check_grid(num_periods, num_simulations, max_steps=1000)

    simulator = MonteCarloUseCase(S0, mu, sigma, time_unit, num_periods, num_simulations, read_seed(data), language)
    simulator.run_simulation()
    statistics = simulator.get_statistics()
    return {
        'price_plot': simulator.plot_simulation(),
        'distribution_plot': simulator.get_final_price_distribution(),
        'convergence_plot': simulator.plot_convergence(),
        'stats_descriptive': statistics['descriptive'],
        'stats_inferential': statistics['inferential'],
        'seed': simulator.seed,
    }


@calculation
def simulate_gbm_view(data, language):
    S0 = read_number(data, 'S0', ('Preço inicial (S₀)', 'Initial price (S₀)'), above=0)
    mu = read_number(data, 'mu', DRIFT, minimum=-1, maximum=1)
    sigma = read_number(data, 'sigma', VOLATILITY, above=0, maximum=2)
    T, dt, n_simulations = _read_diffusion_grid(data)
    return _diffusion_response(GeometricBrownianMotionUseCase(S0, mu, sigma, T, dt, n_simulations, read_seed(data), language))


@calculation
def simulate_abm_view(data, language):
    X0 = read_number(data, 'X0', ('Valor inicial (X₀)', 'Initial value (X₀)'))
    mu = read_number(data, 'mu', DRIFT)
    sigma = read_number(data, 'sigma', VOLATILITY, above=0)
    T, dt, n_simulations = _read_diffusion_grid(data)
    return _diffusion_response(ArithmeticBrownianMotionUseCase(X0, mu, sigma, T, dt, n_simulations, read_seed(data), language))


@calculation
def simulate_mean_reversion_view(data, language):
    S0 = read_number(data, 'S0', ('Valor inicial (X₀)', 'Initial value (X₀)'))
    mu = read_number(data, 'mu', ('Nível médio (μ)', 'Long-term level (μ)'))
    kappa = read_number(data, 'kappa', ('Velocidade de reversão (κ)', 'Reversion speed (κ)'), above=0)
    sigma = read_number(data, 'sigma', VOLATILITY, above=0)
    T, dt, n_simulations = _read_diffusion_grid(data)
    effective_dt = T / number_of_steps(T, dt)
    if kappa * effective_dt >= 1:
        raise InvalidInput(
            'κ·dt deve ser menor que 1 usando o passo efetivo da grade, senão a discretização ultrapassa a média a cada passo. Reduza o passo de tempo.',
            'κ·dt must be less than 1 using the effective grid step, otherwise the discretisation overshoots the mean at every step. Reduce the time step.',
        )
    return _diffusion_response(ReversaoMediaUseCase(S0, mu, kappa, sigma, T, dt, n_simulations, read_seed(data), language))


@calculation
def comparacao_modelos_view(data, language):
    s0 = read_number(data, 's0', ('Valor inicial (S0)', 'Initial value (S0)'), above=0)
    T = read_number(data, 't', ('Tempo total (T)', 'Total time (T)'), above=0, maximum=100)
    dt = read_number(data, 'dt', TIME_STEP, above=0)
    if dt > T:
        raise InvalidInput('O passo de tempo (dt) não pode ser maior que o tempo total (T).',
                           'The time step (dt) cannot be greater than the total time (T).')
    mu_gbm = read_number(data, 'mu_gbm', ('Taxa de drift do MBG (μ)', 'GBM drift rate (μ)'), minimum=-1, maximum=1)
    sigma_gbm = read_number(data, 'sigma_gbm', ('Volatilidade do MBG (σ)', 'GBM volatility (σ)'), above=0, maximum=2)
    kappa_mr = read_number(data, 'kappa_mr', ('Velocidade de reversão (κ)', 'Reversion speed (κ)'), above=0)
    mu_mr = read_number(data, 'mu_mr', ('Nível de longo prazo (μ)', 'Long-term level (μ)'))
    sigma_mr = read_number(data, 'sigma_mr', ('Volatilidade da reversão (σ)', 'Mean reversion volatility (σ)'), above=0)
    check_grid(number_of_steps(T, dt), 1)
    effective_dt = T / number_of_steps(T, dt)
    if kappa_mr * effective_dt >= 1:
        raise InvalidInput(
            'κ·dt deve ser menor que 1 usando o passo efetivo da grade, senão a discretização ultrapassa a média a cada passo. Reduza o passo de tempo.',
            'κ·dt must be less than 1 using the effective grid step, otherwise the discretisation overshoots the mean at every step. Reduce the time step.',
        )
    comparison = ComparacaoModelosUseCase(s0, mu_gbm, sigma_gbm, mu_mr, kappa_mr, sigma_mr, T, dt, read_seed(data), language)
    return {'plot_image': comparison.generate_plot(), 'final_values': comparison.final_values(), 'seed': comparison.seed}
