import copy
import json
import logging
import math
from urllib import request
from django.core.exceptions import ValidationError
from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.urls import reverse

from estocasticos.api.inputs import format_bound, read_choice, read_fields, read_number
from estocasticos.labels import stat_labels
from estocasticos.use_cases.cadeia_markov_use_case import MAX_MARKOV_STEPS
from estocasticos.use_cases.financial_options.black_scholes_merton_use_case import BlackScholesMertonUseCase
from estocasticos.use_cases.financial_options.black_sholes_use_case import BlackScholesModelUseCase
from estocasticos.use_cases.financial_options.cox_ross_rubinstein_use_case import CoxRossRubinsteinUseCase
from estocasticos.use_cases.financial_options.generalized_black_scholes_merton_use_case import GeneralizedBlackScholesMertonUseCase
from financial_options.models import FinantialModels, FinantialModelsChoices
from financial_options.report_html import sanitize_report_html
from financial_options.report_registry import (
    MONTE_CARLO_AMERICAN_LIMITS, MONTE_CARLO_EUROPEAN_LIMITS, REGISTRY, REPORT_HTML_FIELDS,
)
from financial_options.use_cases.finite_difference_european import FDMEuropeanUseCase
from financial_options.use_cases.option_price_use_Case import create_plots, option_price_use_case
from financial_options.use_cases.option_price_american_use_case import create_american_option_plots, american_option_lsmc

logger = logging.getLogger(__name__)


def _initial_data(request, model_type):
    """Screen defaults from the registry; query-string values override them."""
    return {key: request.GET.get(key, value) for key, value in REGISTRY[model_type].defaults.items()}


def _render_screen(request, model_type, extra_context=None):
    language = request.session.get('language', 'pt')
    extra = extra_context or {}
    screen = REGISTRY[model_type]
    context = {
        # A saved project brings its own data: the defaults are not read at all then.
        'initial_data': extra['initial_data'] if 'initial_data' in extra
                        else _initial_data(request, model_type),
        'language': language,
        'stat_labels': stat_labels(language),
        'max_markov_steps': MAX_MARKOV_STEPS,
        # The screen reads its ranges from the registry, so HTML, messages and the
        # save validation cannot drift apart. Copies, because the registry's dicts
        # live as long as the process and are shared by every request.
        'limits': copy.deepcopy(screen.limits),
        # The same bounds as text, written the way the server's messages write
        # them, so a screen can name a limit without rephrasing it.
        'limit_text': {key: format_bound(value, language) for key, value in screen.limits.items()},
        # The example of the screen, still reachable after a saved project replaced
        # `initial_data`.
        'screen_defaults': copy.deepcopy(screen.defaults),
    }
    context.update(extra)
    return render(request, screen.template, context)


@login_required(login_url='/admin/login/')
def cox_ross_rubinstein_template(request):
    return _render_screen(request, FinantialModelsChoices.COX_ROSS)

@login_required(login_url='/admin/login/')
def basic_concepts_overview_view(request):
    return render(request, 'site/financeiros/basic_concepts_overview.html', {'title': 'Basic Concepts Overview'})

@login_required(login_url='/admin/login/')
def black_scholes_overview_view(request):
    return render(request, 'site/financeiros/black_scholes_overview.html', {'title': 'Black Scholes Merton Overview'})

@login_required(login_url='/admin/login/')
def cox_ross_overview_view(request):
    return render(request, 'site/financeiros/cox_ross_overview.html', {'title': 'Cox Ross Overview'})

@login_required(login_url='/admin/login/')
def monte_carlo_overview_view(request):
    return render(request, 'site/financeiros/monte_carlo_overview.html', {'title': 'Monte Carlo Overview'})

@login_required(login_url='/admin/login/')
def finite_difference_overview_view(request):
    return render(request, 'site/financeiros/finite_difference_overview.html', {'title': 'Monte Carlo Overview'})

@login_required(login_url='/admin/login/')
def call_put_options_view(request):
    return _render_screen(request, FinantialModelsChoices.CALL_PUT_PAYOFF, {'title': 'Call and Put Options'})

@login_required(login_url='/admin/login/')
def collar_strategy_simulator_view(request):
    return _render_screen(request, FinantialModelsChoices.COLLAR, {'title': 'Collar Option Strategy Simulator'})


@login_required(login_url='/admin/login/')
def asset_put_combination_view(request):
    return _render_screen(request, FinantialModelsChoices.ASSET_PUT_COMBINATION, {'title': 'Combination - asset purchase and put option'})

@login_required(login_url='/admin/login/')
def bull_bear_spread_view(request):
    return _render_screen(request, FinantialModelsChoices.BULL_BEAR_SPREAD, {'title': 'Combination - bull and bear spread'})


def black_scholes_view(request):
    if request.method == 'POST':
        try:
            S = float(request.POST.get('asset_price', 0))
            E = float(request.POST.get('exercise_price', 0))
            r = float(request.POST.get('interest_rate', 0))
            sigma = float(request.POST.get('volatility', 0))
            T = float(request.POST.get('time_to_expiration', 0))
            option_type = request.POST.get('option_type', 'call')
            # Validate inputs
            if S <= 0 or E <= 0 or T <= 0 or sigma <= 0:
                return JsonResponse({'error': 'All values must be positive.'})
            model = BlackScholesModelUseCase(S, E, r, sigma, T, option_type)
            probability_chart = model.generate_probability_curve(S, sigma/100, T, r/100)
            d1, d2, n_d1, n_d2 = model.calculate_d_values()
            option_price = model.calculate_price()
            greeks = model.calculate_greeks()
            price_plot = model.plot_price_vs_underlying()
            payoff_plot = model.plot_payoff_at_expiration()

            break_even = 0
            # Interpretation text
            if option_type == 'call':
                break_even = round(E + option_price, 2)
                interpretation = f"""
                <h4>Interpretação dos Resultados:</h4>
                <p>O preço teórico da opção de compra é <strong>R$ {option_price}</strong>.</p>
                <p><strong>Delta de {greeks['delta']}</strong> significa que para cada R$ 1,00 de aumento no preço do ativo subjacente, 
                o preço da opção aumentará aproximadamente R$ {greeks['delta']}.</p>
                <p><strong>Gamma de {greeks['gamma']}</strong> indica quanto o delta mudará para cada R$ 1,00 de movimento no preço do ativo subjacente.</p>
                <p><strong>Theta de {greeks['theta']}</strong> mostra quanto valor a opção perde por dia apenas com a passagem do tempo.</p>
                <p><strong>Vega de {greeks['vega']}</strong> representa quanto o preço da opção mudará para cada 1% de alteração na volatilidade.</p>
                <p>Seu <strong>ponto de equilíbrio</strong> é quando o ativo subjacente atinge R$ {break_even} no vencimento.</p>
                <p>Seu <strong>risco máximo</strong> é o prêmio pago pela opção: R$ {option_price}.</p>
                <p>Seu <strong>ganho potencial é teoricamente ilimitado</strong> se o preço do ativo subjacente subir significativamente.</p>
                """
            else:
                break_even = round(E - option_price, 2)
                interpretation = f"""
                <h4>Interpretação dos Resultados:</h4>
                <p>O preço teórico da opção de venda é <strong>R$ {option_price}</strong>.</p>
                <p><strong>Delta de {greeks['delta']}</strong> significa que para cada R$ 1,00 de aumento no preço do ativo subjacente, 
                o preço da opção diminuirá aproximadamente R$ {abs(greeks['delta'])}.</p>
                <p><strong>Gamma de {greeks['gamma']}</strong> indica quanto o delta mudará para cada R$ 1,00 de movimento no preço do ativo subjacente.</p>
                <p><strong>Theta de {greeks['theta']}</strong> mostra quanto valor a opção perde por dia apenas com a passagem do tempo.</p>
                <p><strong>Vega de {greeks['vega']}</strong> representa quanto o preço da opção mudará para cada 1% de alteração na volatilidade.</p>
                <p>Seu <strong>ponto de equilíbrio</strong> é quando o ativo subjacente atinge R$ {break_even} no vencimento.</p>
                <p>Seu <strong>risco máximo</strong> é o prêmio pago pela opção: R$ {option_price}.</p>
                <p>Seu <strong>ganho potencial máximo</strong> é de R$ {break_even} se o preço do ativo subjacente cair para zero.</p>
                """
            
            return JsonResponse({
                'option_price': option_price,
                'greeks': greeks,
                'price_plot': price_plot,
                'payoff_plot': payoff_plot,
                'interpretation': interpretation,
                'd1': round(d1, 4),
                'd2': round(d2, 4),
                'n_d1': (round(n_d1, 4)*100),
                'n_d2': (round(n_d2, 4)*100),
                'break_even' :break_even,
                'max_loss' : option_price,
                'probability_chart' : probability_chart
            })
            
        except ValueError as e:
            return JsonResponse({'error': 'Por favor, insira valores numéricos válidos.'})
        except Exception as e:
            return JsonResponse({'error': str(e)})
    else:
        return _render_screen(request, FinantialModelsChoices.BLACK_SCHOLES)

def _read_project_name(data, language, required=False):
    name = data.get('name', '')
    if not isinstance(name, str) or len(name.strip()) > 255:
        raise ValidationError(
            'Project name must be text with at most 255 characters.' if language == 'en'
            else 'O nome do projeto deve ser um texto com até 255 caracteres.')
    name = name.strip()
    if required and not name:
        raise ValidationError('Enter a project name.' if language == 'en' else 'Informe um nome para o projeto.')
    return name


@login_required(login_url='/admin/login/')
@require_POST
def save_financial_model(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON format.'}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({'success': False, 'error': 'Invalid JSON format.'}, status=400)

    language = request.session.get('language', 'pt')
    try:
        name = _read_project_name(data, language)
    except ValidationError as error:
        return JsonResponse({'success': False, 'error': ' '.join(error.messages)}, status=400)

    model_type = data.get('model_type')
    parameters = data.get('parameters')
    results = data.get('results')
    if not all([model_type, parameters, results]):
        return JsonResponse({'success': False, 'error': 'Missing data in request.'}, status=400)
    if not isinstance(parameters, dict) or not isinstance(results, dict):
        return JsonResponse({'success': False, 'error': 'Invalid JSON format.'}, status=400)

    # Models that declare one check their own payload: size, types and finiteness of
    # the series the browser calculated.
    spec = REGISTRY.get(model_type)
    if spec is not None and spec.validate_payload is not None:
        error = spec.validate_payload(parameters, results, language)
        if error:
            return JsonResponse({'success': False, 'error': error}, status=400)

    financial_model = FinantialModels(
        usuario=request.user,
        name=name,
        model_type=model_type,
        parameters=parameters,
        results=results,
        report='online' if model_type in REGISTRY else None,
    )
    try:
        financial_model.save()
    except ValidationError as e:
        return JsonResponse({'success': False, 'error': ' '.join(e.messages)}, status=400)
    except Exception as e:
        print(f"Error saving financial model: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': True, 'message': 'Project saved successfully!',
                         'id': financial_model.id, 'name': financial_model.name,
                         'report_url': reverse('view_report', args=[financial_model.id])
                         if model_type in REGISTRY else None})


def black_scholes_merton_view(request):
    """Handle API requests for Black-Scholes-Merton calculations."""
    if request.method == 'POST':
        try:
            # Extract parameters from POST data
            S = float(request.POST.get('asset_price', 0))
            E = float(request.POST.get('exercise_price', 0))
            r = float(request.POST.get('interest_rate', 0))
            sigma = float(request.POST.get('volatility', 0))
            T = float(request.POST.get('time_to_expiration', 0))
            option_type = request.POST.get('option_type', 'call')
            dividend_yield = float(request.POST.get('dividend_yield', 0))
            
            # Validate input
            if S <= 0 or E <= 0 or T <= 0 or sigma <= 0:
                return JsonResponse({'error': 'All values must be positive.'})
            
            # Create model and perform calculations
            model = BlackScholesMertonUseCase(S, E, r, sigma, T, option_type, dividend_yield)
            d1, d2, n_d1, n_d2 = model.calculate_d_values()
            option_price = model.calculate_price()
            greeks = model.calculate_greeks()
            price_plot = model.plot_price_vs_underlying()
            payoff_plot = model.plot_payoff_at_expiration()
            current_language = request.session.get('language')  

            d_interpretation = ""
            if current_language == 'pt':
                d_interpretation = """
                <p>Nos modelos de Black-Scholes-Merton, os termos intermediários **d1, N(d1), d2 e N(d2)** ajudam a determinar o valor de opções europeias de compra ou venda (Black e Scholes, 1973). Uma interpretação básica é:</p>
                <ul>
                    <li>(i) o termo **d1** representa a posição do preço do ativo-objeto em relação ao preço de exercício, considerando o tempo e a volatilidade;</li>
                    <li>(ii) o termo **d2** é uma adaptação de d1;</li>
                    <li>(iii) o termo **N(d1)** determina a probabilidade de a opção ser exercida, ou seja, ficar "in the money" na data de vencimento;</li>
                    <li>(iv) e o termo **N(d2)** não é tão fácil de interpretar (Hull, 2021).</li>
                </ul>
                """
            else: # Default to English
                d_interpretation = """
                <p>In Black-Scholes-Merton models, the intermediate terms **d1, N(d1), d2, and N(d2)** help determine the value of European call or put options (Black and Scholes, 1973). A basic interpretation is:</p>
                <ul>
                    <li>(i) the term **d1** represents the position of the underlying asset price relative to the strike price, considering time and volatility;</li>
                    <li>(ii) the term **d2** is an adaptation of d1;</li>
                    <li>(iii) the term **N(d1)** determines the probability that the option will be exercised, i.e., be "in the money" at expiration;</li>
                    <li>(iv) and the term **N(d2)** is not as straightforward to interpret (Hull, 2021).</li>
                </ul>
                """
            # Existing interpretation text
            interpretation = ""
            if option_type == 'call':
                break_even = round(E + option_price, 2)
                if current_language == 'pt':
                    interpretation = f"""
                    <h4>Interpretação dos Resultados:</h4>
                    {d_interpretation}
                    <p>O preço teórico da opção de compra é <strong>R$ {option_price:.2f}</strong>.</p>
                    <p><strong>Delta de {greeks['delta']:.4f}</strong> significa que para cada R$ 1,00 de aumento no preço do ativo subjacente,
                    o preço da opção aumentará aproximadamente R$ {greeks['delta']:.4f}.</p>
                    <p><strong>Gamma de {greeks['gamma']:.4f}</strong> indica quanto o delta mudará para cada R$ 1,00 de movimento no preço do ativo subjacente.</p>
                    <p><strong>Theta de {greeks['theta']:.4f}</strong> mostra quanto valor a opção perde por dia apenas com a passagem do tempo.</p>
                    <p><strong>Vega de {greeks['vega']:.4f}</strong> representa quanto o preço da opção mudará para cada 1% de alteração na volatilidade.</p>
                    <p>Seu <strong>ponto de equilíbrio</strong> é quando o ativo subjacente atinge R$ {break_even} no vencimento.</p>
                    <p>Seu <strong>risco máximo</strong> é o prêmio pago pela opção: R$ {option_price:.2f}.</p>
                    <p>Seu <strong>ganho potencial é teoricamente ilimitado</strong> se o preço do ativo subjacente subir significativamente.</p>
                    """
                else:
                     interpretation = f"""
                    <h4>Interpretation of Results:</h4>
                    {d_interpretation}
                    <p>The theoretical price of the call option is <strong>$ {option_price:.2f}</strong>.</p>
                    <p>A **Delta of {greeks['delta']:.4f}** means that for every $1.00 increase in the underlying asset price,
                    the option's price will increase by approximately $ {greeks['delta']:.4f}.</p>
                    <p>A **Gamma of {greeks['gamma']:.4f}** indicates how much the delta will change for every $1.00 movement in the underlying asset price.</p>
                    <p>A **Theta of {greeks['theta']:.4f}** shows how much value the option loses per day due to the passage of time alone.</p>
                    <p>A **Vega of {greeks['vega']:.4f}** represents how much the option price will change for every 1% change in volatility.</p>
                    <p>Your **break-even point** is when the underlying asset reaches $ {break_even} at expiration.</p>
                    <p>Your **maximum risk** is the premium paid for the option: $ {option_price:.2f}.</p>
                    <p>Your **potential gain is theoretically unlimited** if the underlying asset price rises significantly.</p>
                    """
            else: # Put option
                break_even = round(E - option_price, 2)
                if current_language == 'pt':
                    interpretation = f"""
                    <h4>Interpretação dos Resultados:</h4>
                    {d_interpretation}
                    <p>O preço teórico da opção de venda é <strong>R$ {option_price:.2f}</strong>.</p>
                    <p><strong>Delta de {greeks['delta']:.4f}</strong> significa que para cada R$ 1,00 de aumento no preço do ativo subjacente,
                    o preço da opção diminuirá aproximadamente R$ {abs(greeks['delta']):.4f}.</p>
                    <p><strong>Gamma de {greeks['gamma']:.4f}</strong> indica quanto o delta mudará para cada R$ 1,00 de movimento no preço do ativo subjacente.</p>
                    <p><strong>Theta de {greeks['theta']:.4f}</strong> mostra quanto valor a opção perde por dia apenas com a passagem do tempo.</p>
                    <p><strong>Vega de {greeks['vega']:.4f}</strong> representa quanto o preço da opção mudará para cada 1% de alteração na volatilidade.</p>
                    <p>Seu <strong>ponto de equilíbrio</strong> é quando o ativo subjacente atinge R$ {break_even} no vencimento.</p>
                    <p>Seu <strong>risco máximo</strong> é o prêmio pago pela opção: R$ {option_price:.2f}.</p>
                    <p>Seu <strong>ganho potencial máximo</strong> é de R$ {break_even} se o preço do ativo subjacente cair para zero.</p>
                    """
                else:
                    interpretation = f"""
                    <h4>Interpretation of Results:</h4>
                    {d_interpretation}
                    <p>The theoretical price of the put option is <strong>$ {option_price:.2f}</strong>.</p>
                    <p>A **Delta of {greeks['delta']:.4f}** means that for every $1.00 increase in the underlying asset price,
                    the option's price will decrease by approximately $ {abs(greeks['delta']):.4f}.</p>
                    <p>A **Gamma of {greeks['gamma']:.4f}** indicates how much the delta will change for every $1.00 movement in the underlying asset price.</p>
                    <p>A **Theta of {greeks['theta']:.4f}** shows how much value the option loses per day due to the passage of time alone.</p>
                    <p>A **Vega of {greeks['vega']:.4f}** represents how much the option price will change for every 1% change in volatility.</p>
                    <p>Your **break-even point** is when the underlying asset reaches $ {break_even} at expiration.</p>
                    <p>Your **maximum risk** is the premium paid for the option: $ {option_price:.2f}.</p>
                    <p>Your **maximum potential gain** is $ {break_even} if the underlying asset price falls to zero.</p>
                    """
            
            # Return JSON response with calculations
            return JsonResponse({
                'option_price': option_price,
                'greeks': greeks,
                'price_plot': price_plot,
                'payoff_plot': payoff_plot,
                'interpretation': interpretation,
                'd1': round(d1, 4),
                'd2': round(d2, 4),
                'n_d1': (round(n_d1, 4)*100),
                'n_d2': (round(n_d2, 4)*100),
                'break_even': break_even,
                'max_loss': option_price,
            })
            
        except ValueError:
            return JsonResponse({'error': 'Por favor, insira valores numéricos válidos.'})
        except Exception as e:
            return JsonResponse({'error': str(e)})
    
    else:
        return _render_screen(request, FinantialModelsChoices.BLACK_SCHOLES_MERTON)

def cox_ross_rubinstein_view(request):
    """Handle API requests for Cox-Ross-Rubinstein calculations."""
    if request.method == 'POST':
        try:
            # Extract parameters from POST data
            S = float(request.POST.get('asset_price', 0))
            E = float(request.POST.get('exercise_price', 0))
            r = float(request.POST.get('interest_rate', 0))
            sigma = float(request.POST.get('volatility', 0))
            T = float(request.POST.get('time_to_expiration', 0))
            option_type = request.POST.get('option_type', 'call')
            steps = int(request.POST.get('steps', 5))
            dividend_yield = float(request.POST.get('dividend_yield', 0))
            
            # Validate input
            if S <= 0 or E <= 0 or T <= 0 or sigma <= 0 or steps <= 0:
                return JsonResponse({'error': 'All values must be positive. Steps must be a positive integer.'})
            
            # Limit steps to a reasonable number for visualization
            if steps > 10:
                steps = 10
            
            # Create model and perform calculations
            model = CoxRossRubinsteinUseCase(S, E, r, sigma, T, option_type, steps, dividend_yield)
            option_price = model.calculate_price()
            greeks = model.calculate_greeks()
            
            # Get lattice data and generate HTML
            lattice_html = model.generate_lattice_html()
            lattice_data = model.get_lattice_data()
            years  = T / 365
            rate = r / 100
            pv = (E * math.exp(-rate * years))
            traditional_npv = S - pv
            
            expanded_npv = traditional_npv + option_price if traditional_npv < 0 else traditional_npv
            
            # Value of flexibility (equals option value for negative NPV projects)
            flexibility_value = expanded_npv - traditional_npv
            
            # Option value / investment cost ratio
            option_ratio = option_price / abs(traditional_npv) if traditional_npv != 0 else 0 
            
            # Calculate break-even point
            if option_type == 'call':
                break_even = round(E + option_price, 2)
                interpretation = f"""
                <h4>Interpretação dos Resultados:</h4>
                <p>O preço da opção de compra calculado pelo modelo binomial de Cox-Ross-Rubinstein é <strong>R$ {option_price}</strong>.</p>
                <p>O modelo usa <strong>{steps} passos</strong> para construir uma árvore binomial, com fator de alta (u) de {lattice_data['u']} e fator de baixa (d) de {lattice_data['d']}.</p>
                <p><strong>Delta de {greeks['delta']}</strong> significa que para cada R$ 1,00 de aumento no preço do ativo subjacente, 
                o preço da opção aumentará aproximadamente R$ {greeks['delta']}.</p>
                <p><strong>Gamma de {greeks['gamma']}</strong> indica quanto o delta mudará para cada R$ 1,00 de movimento no preço do ativo subjacente.</p>
                <p><strong>Theta de {greeks['theta']}</strong> mostra quanto valor a opção perde por dia apenas com a passagem do tempo.</p>
                <p><strong>Vega de {greeks['vega']}</strong> representa quanto o preço da opção mudará para cada 1% de alteração na volatilidade.</p>
                <p><strong>Rho de {greeks['rho']}</strong> indica a sensibilidade do preço da opção em relação a mudanças na taxa de juros livre de risco.</p>
                <p>O rendimento de dividendos de <strong>{dividend_yield}%</strong> reduz o valor da opção de compra em comparação com um ativo sem dividendos.</p>
                <p>Seu <strong>ponto de equilíbrio</strong> é quando o ativo subjacente atinge R$ {break_even} no vencimento.</p>
                <p>Seu <strong>risco máximo</strong> é o prêmio pago pela opção: R$ {option_price}.</p>
                <p>Seu <strong>ganho potencial é teoricamente ilimitado</strong> se o preço do ativo subjacente subir significativamente.</p>
                <p>A probabilidade neutra ao risco (p) usada no modelo é de <strong>{lattice_data['p'] * 100:.2f}%</strong>.</p>
                
                <h5>Análise de Opções Reais:</h5>
                <p>Se este fosse um projeto de investimento real:</p>
                <ul>
                    <li>O VPL tradicional seria <strong>R$ {traditional_npv:.2f}</strong></li>
                    <li>O VPL expandido (com flexibilidade) seria <strong>R$ {expanded_npv:.2f}</strong></li>
                    <li>O valor da flexibilidade seria <strong>R$ {flexibility_value:.2f}</strong></li>
                    <li>A razão valor da opção / custo de investimento seria <strong>{option_ratio:.4f}</strong></li>
                </ul>
                
                <h5>Interpretação da Treliça Binomial:</h5>
                <p>Na visualização da treliça binomial:</p>
                <ul>
                    <li><strong>Preço da Ação</strong>: Valor do ativo subjacente em cada nó</li>
                    <li><strong>Valor da Opção</strong>: Valor da opção em cada nó</li>
                    <li><strong>Valor Intrínseco</strong>: Valor de exercício imediato (max(0, S-K) para calls)</li>
                </ul>
                <p>As células verdes representam situações onde a opção está "in-the-money" (preço do ativo > preço de exercício para calls).</p>
                """
            else:  # put option
                break_even = round(E - option_price, 2)
                interpretation = f"""
                <h4>Interpretação dos Resultados:</h4>
                <p>O preço da opção de venda calculado pelo modelo binomial de Cox-Ross-Rubinstein é <strong>R$ {option_price}</strong>.</p>
                <p>O modelo usa <strong>{steps} passos</strong> para construir uma árvore binomial, com fator de alta (u) de {lattice_data['u']} e fator de baixa (d) de {lattice_data['d']}.</p>
                <p><strong>Delta de {greeks['delta']}</strong> significa que para cada R$ 1,00 de aumento no preço do ativo subjacente, 
                o preço da opção diminuirá aproximadamente R$ {abs(greeks['delta'])}.</p>
                <p><strong>Gamma de {greeks['gamma']}</strong> indica quanto o delta mudará para cada R$ 1,00 de movimento no preço do ativo subjacente.</p>
                <p><strong>Theta de {greeks['theta']}</strong> mostra quanto valor a opção perde por dia apenas com a passagem do tempo.</p>
                <p><strong>Vega de {greeks['vega']}</strong> representa quanto o preço da opção mudará para cada 1% de alteração na volatilidade.</p>
                <p><strong>Rho de {greeks['rho']}</strong> indica a sensibilidade do preço da opção em relação a mudanças na taxa de juros livre de risco.</p>
                <p>O rendimento de dividendos de <strong>{dividend_yield}%</strong> aumenta o valor da opção de venda em comparação com um ativo sem dividendos.</p>
                <p>Seu <strong>ponto de equilíbrio</strong> é quando o ativo subjacente atinge R$ {break_even} no vencimento.</p>
                <p>Seu <strong>risco máximo</strong> é o prêmio pago pela opção: R$ {option_price}.</p>
                <p>Seu <strong>ganho potencial máximo</strong> é de R$ {break_even} se o preço do ativo subjacente cair para zero.</p>
                <p>A probabilidade neutra ao risco (p) usada no modelo é de <strong>{lattice_data['p'] * 100:.2f}%</strong>.</p>
                
                <h5>Análise de Opções Reais:</h5>
                <p>Se este fosse um projeto de investimento real (opção de abandono):</p>
                <ul>
                    <li>O VPL tradicional seria <strong>R$ {traditional_npv:.2f}</strong></li>
                    <li>O VPL expandido (com flexibilidade) seria <strong>R$ {expanded_npv:.2f}</strong></li>
                    <li>O valor da flexibilidade seria <strong>R$ {flexibility_value:.2f}</strong></li>
                    <li>A razão valor da opção / custo de investimento seria <strong>{option_ratio:.4f}</strong></li>
                </ul>
                
                <h5>Interpretação da Treliça Binomial:</h5>
                <p>Na visualização da treliça binomial:</p>
                <ul>
                    <li><strong>Preço da Ação</strong>: Valor do ativo subjacente em cada nó</li>
                    <li><strong>Valor da Opção</strong>: Valor da opção em cada nó</li>
                    <li><strong>Valor Intrínseco</strong>: Valor de exercício imediato (max(0, K-S) para puts)</li>
                </ul>
                <p>As células verdes representam situações onde a opção está "in-the-money" (preço do ativo < preço de exercício para puts).</p>
                """
            
            # Return JSON response with calculations
            response_data = {
                'option_price': option_price,
                'greeks': greeks,
                'lattice_html': lattice_html,
                'interpretation': interpretation,
                'break_even': break_even,
                'max_loss': option_price,
                'u': lattice_data['u'],
                'd': lattice_data['d'],
                'p': lattice_data['p'],
                'dt': lattice_data['dt'],
                'traditional_npv': traditional_npv,
                'expanded_npv': expanded_npv,
                'flexibility_value': flexibility_value,
                'option_ratio': option_ratio
            }
            
            return JsonResponse(response_data)
            
        except ValueError:
            return JsonResponse({'error': 'Por favor, insira valores numéricos válidos. O número de passos deve ser um número inteiro.'})
        except Exception as e:
            return JsonResponse({'error': str(e)})
    
    # If not POST, just render the template
    else:
        return _render_screen(request, FinantialModelsChoices.COX_ROSS)



# --- Monte Carlo option screens ---------------------------------------------

# The labels the messages name the fields by, in the order of the forms.
_MONTE_CARLO_LABELS = {
    'S0': ('Preço Atual do Ativo (S0)', 'Initial Asset Price (S0)'),
    'K': ('Preço de Exercício (K)', 'Strike Price (K)'),
    'T': ('Tempo até o Vencimento (T)', 'Time to Maturity (T)'),
    'r': ('Taxa de Juros Livre de Risco (r)', 'Risk-Free Rate (r)'),
    'sigma': ('Volatilidade (sigma)', 'Volatility (sigma)'),
    'num_simulacoes': ('Número de Simulações', 'Number of Simulations'),
    'num_passos': ('Número de Passos no Tempo', 'Number of Time Steps'),
    'option_type': ('Tipo de Opção', 'Option Type'),
}


def _simulation_failed(language):
    """What a failed simulation says; the cause goes to the log, not to the screen."""
    return ('An unexpected error occurred during the simulation.' if language == 'en'
            else 'Ocorreu um erro inesperado durante a simulação.')


def _read_option_inputs(data, language, limits):
    """
    The inputs both Monte Carlo option screens share, read against `limits`.

    The ranges come from the registry, so the HTML of the screen, this
    validation and the message the user reads cannot drift apart (plan §10, U6).
    `num_passos` is read only for the screen that walks the time steps.
    """
    label = _MONTE_CARLO_LABELS
    fields = {
        'S0': lambda d: read_number(d, 'S0', label['S0'], above=0),
        'K': lambda d: read_number(d, 'K', label['K'], above=0),
        'T': lambda d: read_number(d, 'T', label['T'], above=0),
        'r': lambda d: read_number(d, 'r', label['r'],
                                   minimum=limits['min_rate'], maximum=limits['max_rate']),
        'sigma': lambda d: read_number(d, 'sigma', label['sigma'],
                                       minimum=limits['min_volatility'], maximum=limits['max_volatility']),
        'num_simulacoes': lambda d: read_number(d, 'num_simulacoes', label['num_simulacoes'],
                                                minimum=limits['min_simulations'],
                                                maximum=limits['max_simulations'], integer=True),
    }
    if 'max_steps' in limits:
        fields['num_passos'] = lambda d: read_number(d, 'num_passos', label['num_passos'],
                                                     minimum=limits['min_steps'],
                                                     maximum=limits['max_steps'], integer=True)
    fields['option_type'] = lambda d: read_choice(d, 'option_type', label['option_type'], ('call', 'put'))
    return read_fields(data, language, fields)


def precificar_opcao_view(request):
    if request.method != 'POST':
        return _render_screen(request, FinantialModelsChoices.MONTE_CARLO_EUROPEAN)

    language = request.session.get('language', 'pt')
    values, errors = _read_option_inputs(request.POST, language, MONTE_CARLO_EUROPEAN_LIMITS)
    if errors:
        return JsonResponse({'errors': errors}, status=400)

    try:
        preco_opcao, ST_array, statistics = option_price_use_case(
            values['S0'], values['K'], values['T'], values['r'], values['sigma'],
            values['num_simulacoes'], values['option_type'],
        )
        price_plot_base64, distribution_plot_base64 = create_plots(ST_array)
    except Exception:
        logger.exception('European Monte Carlo simulation failed')
        return JsonResponse({'error': _simulation_failed(language)}, status=500)

    # Numbers, not text: the screen formats them in the session language and the
    # saved run keeps the precision of the simulation.
    return JsonResponse({
        'preco_estimado': float(preco_opcao),
        'price_plot': price_plot_base64,
        'distribution_plot': distribution_plot_base64,
        'stats_descriptive': statistics['descriptive'],
        'stats_inferential': statistics['inferential'],
    })

def precificar_opcao_americana_view(request):
    """Prices an American option by least squares Monte Carlo."""
    if request.method != 'POST':
        return _render_screen(request, FinantialModelsChoices.MONTE_CARLO_AMERICAN)

    language = request.session.get('language', 'pt')
    values, errors = _read_option_inputs(request.POST, language, MONTE_CARLO_AMERICAN_LIMITS)
    if errors:
        return JsonResponse({'errors': errors}, status=400)

    try:
        option_price, S_paths, boundary, discounted_cashflows = american_option_lsmc(
            values['S0'], values['K'], values['T'], values['r'], values['sigma'],
            values['num_simulacoes'], values['num_passos'], values['option_type'],
        )
        convergence_plot_b64, paths_plot_b64, boundary_plot_b64 = create_american_option_plots(
            S_paths, boundary, values['option_type'], discounted_cashflows
        )
    except Exception:
        logger.exception('American Monte Carlo simulation failed')
        return JsonResponse({'error': _simulation_failed(language)}, status=500)

    return JsonResponse({
        'preco_estimado': float(option_price),
        'convergence_plot': convergence_plot_b64,
        'price_plot': paths_plot_b64,
        'exercise_boundary_plot': boundary_plot_b64,
    })


@login_required(login_url='/admin/login/')
def view_report_view(request, simulation_id):
    simulation = get_object_or_404(FinantialModels, id=simulation_id, usuario=request.user)
    spec = REGISTRY.get(simulation.model_type)
    if spec is None:
        raise Http404("No report for this model type.")

    language = request.session.get('language', 'pt')
    title_prefix = 'Report' if language == 'en' else 'Relatório'
    report = spec.build_report(simulation.parameters, simulation.results, language)
    # These fragments are rendered with |safe but were saved from the browser.
    for key in REPORT_HTML_FIELDS:
        if report.get(key):
            report[key] = sanitize_report_html(report[key])
    context = {
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
        'report_title': f"{title_prefix} - {simulation.get_model_type_display()}",
        'project_name': simulation.name,
        'language': language,
        'parameters': spec.label_parameters(simulation.parameters, language),
        **report,
    }
    return render(request, "site/financeiros/report/report_template.html", context)


@login_required(login_url='/admin/login/')
def rerun_simulation_view(request, simulation_id):
    simulation = get_object_or_404(FinantialModels, id=simulation_id, usuario=request.user)
    spec = REGISTRY.get(simulation.model_type)
    if spec is None:
        return redirect('simulation_list')

    return _render_screen(request, simulation.model_type, {
        # Defaults first, so saves made before a screen gained an input still re-run.
        'initial_data': {**spec.defaults, **simulation.parameters},
        # The screen says it is showing a saved project, not its own example, and
        # offers to restore these values after they are edited.
        'is_rerun': True,
        'saved_project_name': simulation.name,
    })

@login_required(login_url='/admin/login/')
def generalized_black_scholes_merton_template(request):
    return _render_screen(request, FinantialModelsChoices.GENERALIZED_BLACK_SCHOLES_MERTON)


def generalized_black_scholes_merton_view(request):
    """Handle API requests for Generalized Black-Scholes-Merton calculations."""
    if request.method == 'POST':
        try:
            S = float(request.POST.get('asset_price', 0))
            E = float(request.POST.get('exercise_price', 0))
            r = float(request.POST.get('interest_rate', 0))
            sigma = float(request.POST.get('volatility', 0))
            T = float(request.POST.get('time_to_expiration', 0))
            option_type = request.POST.get('option_type', 'call')
            cost_of_carry = float(request.POST.get('cost_of_carry', 0))
            dividend_yield = float(request.POST.get('dividend_yield',0))

            if S <= 0 or E <= 0 or T <= 0 or sigma <= 0:
                return JsonResponse({'error': 'All values must be positive.'})

            model = GeneralizedBlackScholesMertonUseCase(S, E, r, sigma, T, option_type, cost_of_carry, dividend_yield)
            d1, d2, n_d1, n_d2 = model.calculate_d_values()
            option_price = model.calculate_price()
            greeks = model.calculate_greeks()
            price_plot = model.plot_price_vs_underlying()
            payoff_plot = model.plot_payoff_at_expiration()
            current_language = request.session.get('language')

            b_interpretation = ""
            if current_language == 'pt':
                b_interpretation = f"""
                <p>O <strong>Custo de Carregamento (b)</strong> de <strong>{cost_of_carry:.2f}%</strong> é um parâmetro chave neste modelo generalizado. Ele representa o custo líquido de manter o ativo subjacente. O valor de 'b' muda dependendo do ativo:</p>
                <ul>
                    <li>Para uma <strong>ação que não paga dividendos</strong>, <code>b = r</code> (a taxa livre de risco).</li>
                    <li>Para uma <strong>ação que paga dividendos contínuos (q)</strong>, <code>b = r - q</code>.</li>
                    <li>Para um <strong>contrato futuro</strong>, <code>b = 0</code>.</li>
                    <li>Para uma <strong>opção de moeda</strong>, <code>b = r - rf</code> (onde rf é a taxa de juros estrangeira).</li>
                </ul>
                """
            else:  # English
                b_interpretation = f"""
                <p>The <strong>Cost of Carry (b)</strong> of <strong>{cost_of_carry:.2f}%</strong> is a key parameter in this generalized model. It represents the net cost of holding the underlying asset. The value of 'b' changes depending on the asset:</p>
                <ul>
                    <li>For a <strong>non-dividend-paying stock</strong>, <code>b = r</code> (the risk-free rate).</li>
                    <li>For a <strong>stock paying a continuous dividend (q)</strong>, <code>b = r - q</code>.</li>
                    <li>For a <strong>futures contract</strong>, <code>b = 0</code>.</li>
                    <li>For a <strong>currency option</strong>, <code>b = r - rf</code> (where rf is the foreign risk-free rate).</li>
                </ul>
                """

            if option_type == 'call':
                break_even = round(E + option_price, 2)
                if current_language == 'pt':
                    interpretation = f"""
                    <h4>Interpretação dos Resultados:</h4>
                    {b_interpretation}
                    <p>O preço teórico da opção de compra é <strong>R$ {option_price:.2f}</strong>.</p>
                    <p><strong>Delta de {greeks['delta']:.4f}</strong>: Para cada R$ 1,00 de aumento no preço do ativo, o preço da opção aumentará R$ {greeks['delta']:.4f}.</p>
                    <p><strong>Gamma de {greeks['gamma']:.4f}</strong>: Indica a taxa de variação do delta.</p>
                    <p><strong>Theta de {greeks['theta']:.4f}</strong>: Mostra a perda de valor da opção por dia devido à passagem do tempo.</p>
                    <p><strong>Vega de {greeks['vega']:.4f}</strong>: Representa a sensibilidade a uma mudança de 1% na volatilidade.</p>
                    <p>Seu <strong>ponto de equilíbrio</strong> no vencimento é R$ {break_even}.</p>
                    """
                else:  # English
                    interpretation = f"""
                    <h4>Interpretation of Results:</h4>
                    {b_interpretation}
                    <p>The theoretical price of the call option is <strong>$ {option_price:.2f}</strong>.</p>
                    <p>A **Delta of {greeks['delta']:.4f}** means the option's price will increase by approximately $ {greeks['delta']:.4f} for every $1.00 increase in the underlying asset price.</p>
                    <p>A **Gamma of {greeks['gamma']:.4f}** indicates the rate of change of delta.</p>
                    <p>A **Theta of {greeks['theta']:.4f}** shows the option's value decay per day.</p>
                    <p>A **Vega of {greeks['vega']:.4f}** represents the sensitivity to a 1% change in volatility.</p>
                    <p>Your **break-even point** at expiration is $ {break_even}.</p>
                    """
            else:  # Put
                break_even = round(E - option_price, 2)
                if current_language == 'pt':
                    interpretation = f"""
                    <h4>Interpretação dos Resultados:</h4>
                    {b_interpretation}
                    <p>O preço teórico da opção de venda é <strong>R$ {option_price:.2f}</strong>.</p>
                    <p><strong>Delta de {greeks['delta']:.4f}</strong>: Para cada R$ 1,00 de aumento no preço do ativo, o preço da opção diminuirá R$ {abs(greeks['delta']):.4f}.</p>
                    <p><strong>Gamma de {greeks['gamma']:.4f}</strong>: Indica a taxa de variação do delta.</p>
                    <p><strong>Theta de {greeks['theta']:.4f}</strong>: Mostra a perda de valor da opção por dia.</p>
                    <p><strong>Vega de {greeks['vega']:.4f}</strong>: Representa a sensibilidade a uma mudança de 1% na volatilidade.</p>
                    <p>Seu <strong>ponto de equilíbrio</strong> no vencimento é R$ {break_even}.</p>
                    """
                else:  # English
                    interpretation = f"""
                    <h4>Interpretation of Results:</h4>
                    {b_interpretation}
                    <p>The theoretical price of the put option is <strong>$ {option_price:.2f}</strong>.</p>
                    <p>A **Delta of {greeks['delta']:.4f}** means the option's price will decrease by approximately $ {abs(greeks['delta']):.4f} for every $1.00 increase in the underlying asset price.</p>
                    <p>A **Gamma of {greeks['gamma']:.4f}** indicates the rate of change of delta.</p>
                    <p>A **Theta of {greeks['theta']:.4f}** shows the option's value decay per day.</p>
                    <p>A **Vega of {greeks['vega']:.4f}** represents the sensitivity to a 1% change in volatility.</p>
                    <p>Your **break-even point** at expiration is $ {break_even}.</p>
                    """
            
            return JsonResponse({
                'option_price': option_price,
                'greeks': greeks,
                'price_plot': price_plot,
                'payoff_plot': payoff_plot,
                'interpretation': interpretation,
                'd1': round(d1, 4),
                'd2': round(d2, 4),
                'n_d1': (round(n_d1, 4)*100),
                'n_d2': (round(n_d2, 4)*100),
                'break_even': break_even,
                'max_loss': option_price,
            })

        except ValueError:
            return JsonResponse({'error': 'Por favor, insira valores numéricos válidos.'})
        except Exception as e:
            return JsonResponse({'error': str(e)})


@login_required(login_url='/admin/login/')
@require_POST
def update_simulation_name(request):
    language = request.session.get('language', 'pt')
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)

    simulation_id = data.get('id')
    if not isinstance(simulation_id, str) or not simulation_id:
        return JsonResponse({'status': 'error', 'message': 'Invalid project ID.'}, status=400)
    try:
        new_name = _read_project_name(data, language, required=True)
        simulation = get_object_or_404(FinantialModels, id=simulation_id, usuario=request.user)
    except ValidationError as error:
        return JsonResponse({'status': 'error', 'message': ' '.join(error.messages)}, status=400)
    except Http404:
        return JsonResponse({'status': 'error', 'message': 'Simulation not found.'}, status=404)

    simulation.name = new_name
    simulation.save(update_fields=['name', 'alterado_em'])
    return JsonResponse({'status': 'success', 'message': 'Name updated successfully.', 'name': simulation.name})
    
def fdm_european_view(request):
    if request.method == 'POST':
        try:
            S = float(request.POST.get('asset_price', 0))
            E = float(request.POST.get('exercise_price', 0))
            r = float(request.POST.get('interest_rate', 0))
            sigma = float(request.POST.get('volatility', 0))
            T = float(request.POST.get('time_to_expiration', 0))
            option_type = request.POST.get('option_type', 'call')

            N_space = int(request.POST.get('grid_space_steps', 1000))
            if S <= 0 or E <= 0 or T <= 0 or sigma <= 0:
                return JsonResponse({'error': 'All values must be positive.'})

            model = FDMEuropeanUseCase(S, E, r, sigma, T, option_type, N_space)
            bs_model = BlackScholesModelUseCase(S, E, r, sigma, T, option_type)
            bs_price = bs_model.calculate_price()
            option_price = model.solve()
            absolute_error = abs(option_price - bs_price)
            percentage_error = (absolute_error / bs_price * 100) if bs_price != 0 else 0
            greeks = model.calculate_greeks()
            price_plot, diffusion_plot = model.get_plot_data()
            break_even = 0
            if option_type == 'call':
                break_even = round(E + option_price, 2)
                type_str = "Opção de Compra (Call)" if request.session.get('language') != 'en' else "Call Option"
            else:
                break_even = round(E - option_price, 2)
                type_str = "Opção de Venda (Put)" if request.session.get('language') != 'en' else "Put Option"

            if request.session.get('language') == 'en':
                interpretation = f"""
                <h4>FDM Analysis & Comparison:</h4>
                <p><strong>Method:</strong> Explicit Finite Difference.</p>
                <p><strong>Theoretical Price (FDM):</strong> ${option_price}</p>
                <p><strong>Analytical Price (Black-Scholes):</strong> ${bs_price}</p>
                <div class="alert {'alert-success' if percentage_error < 0.1 else 'alert-warning'}">
                    <strong>Accuracy:</strong> The FDM result deviates by 
                    <strong>{absolute_error:.6f}</strong> ({percentage_error:.4f}%) from the exact formula.
                </div>
                """
            else:
                interpretation = f"""
                <h4>Análise e Comparação FDM:</h4>
                <p><strong>Método:</strong> Diferenças Finitas Explícito.</p>
                <p><strong>Preço Teórico (MDF):</strong> R$ {option_price}</p>
                <p><strong>Preço Analítico (Black-Scholes):</strong> R$ {bs_price}</p>
                <div class="alert {'alert-success' if percentage_error < 0.1 else 'alert-warning'}">
                    <strong>Precisão:</strong> O resultado do MDF desvia 
                    <strong>{absolute_error:.6f}</strong> ({percentage_error:.4f}%) da fórmula exata.
                </div>
                """
            return JsonResponse({
                'option_price': option_price,
                'bs_price': bs_price, 
                'error_val': f"{absolute_error:.6f}",
                'greeks': greeks,
                'price_plot': price_plot,
                'payoff_plot': diffusion_plot, 
                'interpretation': interpretation,
                'grid_m': model.M_time,
                'grid_n': N_space,
                'break_even': break_even,
                'max_loss': option_price, 
            })

        except ValueError:
            return JsonResponse({'error': 'Invalid numeric inputs.'})
        except Exception as e:
            return JsonResponse({'error': str(e)})

    else:
        return _render_screen(request, FinantialModelsChoices.FDM_EUROPEAN)
