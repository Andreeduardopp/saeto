import json
import math
import traceback
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from estocasticos.use_cases.financial_options.black_scholes_merton_use_case import BlackScholesMertonUseCase
from estocasticos.use_cases.financial_options.black_sholes_use_case import BlackScholesModelUseCase
from estocasticos.use_cases.financial_options.cox_ross_rubinstein_use_case import CoxRossRubinsteinUseCase
from estocasticos.use_cases.financial_options.generalized_black_scholes_merton_use_case import GeneralizedBlackScholesMertonUseCase
from financial_options.models import FinantialModels
from financial_options.use_cases.generate_save_pdf import generate_and_save_pdf, generate_and_save_pdf_mcs
from financial_options.use_cases.option_price_use_Case import create_plots, option_price_use_case
from financial_options.use_cases.option_price_american_use_case import create_american_option_plots, american_option_lsmc

@login_required(login_url='/admin/login/')
def black_scholes_template(request):
    return render(request, "site/financeiros/black-sholes.html")

@login_required(login_url='/admin/login/')
def black_scholes_merton_template(request):
    return render(request, "site/financeiros/black-scholes-merton.html")

@login_required(login_url='/admin/login/')
def cox_ross_rubinstein_template(request):
    initial_data = {
        'asset_price': request.GET.get('asset_price', 100.0),
        'exercise_price': request.GET.get('exercise_price', 100.0),
        'time_to_expiration': request.GET.get('time_to_expiration', 30),
        'interest_rate': request.GET.get('interest_rate', 5),
        'volatility': request.GET.get('volatility', 30),
        'option_type': request.GET.get('option_type', 'call'),
        'steps': request.GET.get('steps', 3),
        'dividend_yield': request.GET.get('dividend_yield', 0),
    }
    context = {
        'initial_data': initial_data,
        'language': request.session.get('language', 'pt')
    }
    return render(request, "site/financeiros/cox-ross-rubinstein.html", context)

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
def call_put_options_view(request):
    return render(request, 'site/financeiros/call_put_options.html', {'title': 'Call and Put Options'})

@login_required(login_url='/admin/login/')
def collar_strategy_simulator_view(request):
    return render(request, 'site/financeiros/collar_option.html', {'title': 'Collar Option Strategy Simulator'})


@login_required(login_url='/admin/login/')
def asset_put_combination_view(request):
    return render(request, 'site/financeiros/asset_put_combination.html', {'title': 'Combination - asset purchase and put option'})

@login_required(login_url='/admin/login/')
def bull_bear_spread_view(request):
    return render(request, 'site/financeiros/bull_bear_spread.html', {'title': 'Combination - bull and bear spread'})


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
        initial_data = {
            'asset_price': request.GET.get('asset_price', 100.0),
            'exercise_price': request.GET.get('exercise_price', 100.0),
            'time_to_expiration': request.GET.get('time_to_expiration', 30),
            'interest_rate': request.GET.get('interest_rate', 5),
            'volatility': request.GET.get('volatility', 20),
            'option_type': request.GET.get('option_type', 'call'),
        }
            
        context = {
            'initial_data': initial_data,
            'language': request.session.get('language', 'pt')
        }
        return render(request, "site/financeiros/black-sholes.html", context)

@require_POST 
def save_black_schole_model_view(request):
    try:
        data = json.loads(request.body)
        model_type = data.get('model_type')
        parameters = data.get('parameters')
        results = data.get('results')
        # Basic validation
        if not all([model_type, parameters, results]):
            return JsonResponse({'success': False, 'error': 'Missing data in request.'}, status=400)

        financial_model = FinantialModels(
            usuario=request.user,
            model_type=model_type,
            parameters=parameters,
            results=results,
            report=None
        )
        try:
            financial_model.save()
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Erro ao salvar o modelo financeiro inicialmente: {e}'}, status=500)
        resultados = financial_model.results
        if model_type in ('BLACK_SCHOLES','BLACK_SCHOLES_MERTON', 'GENERALIZED_BLACK_SCHOLES_MERTON', 'COX_ROSS'):
            financial_model.report = 'online'
            financial_model.save()
        return JsonResponse({'success': True, 'message': 'Project saved successfully!', 'id': financial_model.id})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON format.'}, status=400)
    except Exception as e:
        print(f"Error saving financial model: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


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
        initial_data = {
            'asset_price': request.GET.get('asset_price', 100.0),
            'exercise_price': request.GET.get('exercise_price', 100.0),
            'time_to_expiration': request.GET.get('time_to_expiration', 30),
            'interest_rate': request.GET.get('interest_rate', 5),
            'volatility': request.GET.get('volatility', 20),
            'dividend_yield': request.GET.get('dividend_yield', 2),
            'option_type': request.GET.get('option_type', 'call'),
        }
            
        context = {
            'initial_data': initial_data,
            'language': request.session.get('language', 'pt')
        }
        return render(request, 'site/financeiros/black-scholes-merton.html', context)

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
        initial_data = {
            'asset_price': request.GET.get('asset_price', 100.0),
            'exercise_price': request.GET.get('exercise_price', 100.0),
            'time_to_expiration': request.GET.get('time_to_expiration', 30),
            'interest_rate': request.GET.get('interest_rate', 5),
            'volatility': request.GET.get('volatility', 30),
            'option_type': request.GET.get('option_type', 'call'),
            'steps': request.GET.get('steps', 3),
            'dividend_yield': request.GET.get('dividend_yield', 0),
        }
        context = {
            'initial_data': initial_data,
            'language': request.session.get('language', 'pt')
        }
        return render(request, 'site/financeiros/cox-ross-rubinstein.html', context)



def precificar_opcao_view(request):
    if request.method == 'POST':
        errors = {}
        # Captura e valida os dados manualmente
        try:
            S0 = float(request.POST.get('S0'))
            if S0 <= 0.0:
                errors['S0'] = 'Preço Atual do Ativo (S0) deve ser maior que 0.'
        except (ValueError, TypeError):
            errors['S0'] = 'Preço Atual do Ativo (S0) inválido.'

        try:
            K = float(request.POST.get('K'))
            if K <= 0.0:
                errors['K'] = 'Preço de Exercício (K) deve ser maior que 0.'
        except (ValueError, TypeError):
            errors['K'] = 'Preço de Exercício (K) inválido.'

        try:
            T = float(request.POST.get('T'))
            if T <= 0.0:
                errors['T'] = 'Tempo até o Vencimento (T) deve ser maior que 0.'
        except (ValueError, TypeError):
            errors['T'] = 'Tempo até o Vencimento (T) inválido.'

        try:
            r = float(request.POST.get('r'))
            if not (0.0 <= r <= 100):
                errors['r'] = 'Taxa de Juros Livre de Risco (r) deve estar entre 0 e 100.'
        except (ValueError, TypeError):
            errors['r'] = 'Taxa de Juros Livre de Risco (r) inválida.'

        try:
            sigma = float(request.POST.get('sigma'))
            if not (0.1 <= sigma <= 200):
                errors['sigma'] = 'Volatilidade (sigma) deve estar entre 0.1 e 200.'
        except (ValueError, TypeError):
            errors['sigma'] = 'Volatilidade (sigma) inválida.'

        try:
            num_simulacoes = int(request.POST.get('num_simulacoes'))
            if not (1000 <= num_simulacoes <= 1000000):
                errors['num_simulacoes'] = 'Número de Simulações deve estar entre 1.000 e 1.000.000.'
        except (ValueError, TypeError):
            errors['num_simulacoes'] = 'Número de Simulações inválido.'
        
        # Validação para o novo campo 'option_type'
        option_type = request.POST.get('option_type')
        if option_type not in ['put', 'call']:
            errors['option_type'] = 'Tipo de opção inválido.'

        if errors:
            return JsonResponse({'errors': errors}, status=400)

        try:
            # Passa o 'option_type' para a função de cálculo
            preco_opcao, ST_array, statistics = option_price_use_case(
                S0, K, T, r, sigma, num_simulacoes, option_type
            )

            price_plot_base64, distribution_plot_base64 = create_plots(ST_array)

            formatted_stats = {k: f"{v:.4f}" for k, v in statistics.items()}

            return JsonResponse({
                'preco_estimado': f'{preco_opcao:.4f}',
                'price_plot': price_plot_base64,
                'distribution_plot': distribution_plot_base64,
                'statistics': formatted_stats,
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    else: # GET request
        initial_data = {
            'S0': request.GET.get('S0', 100.0),
            'K': request.GET.get('K', 100.0),
            'T': request.GET.get('T', 1.0),
            'r': request.GET.get('r', 5),
            'sigma': request.GET.get('sigma', 20),
            'num_simulacoes': request.GET.get('num_simulacoes', 100000),
            'option_type': request.GET.get('option_type', 'call'),
        }
        context = {
            'initial_data': initial_data,
            'language': request.session.get('language', 'pt')
        }
        # Certifique-se de que o caminho para o template está correto
        return render(request, 'site/financeiros/options_price_mcs.html', context)
    
def precificar_opcao_americana_view(request):
    """
    View to handle the pricing of American options via a web form.
    """
    if request.method == 'POST':
        errors = {}
        # Capture and validate the data from the form
        try:
            S0 = float(request.POST.get('S0'))
            if S0 <= 0:
                errors['S0'] = 'Initial Asset Price (S0) must be greater than 0.'
        except (ValueError, TypeError):
            errors['S0'] = 'Invalid Initial Asset Price (S0).'

        try:
            K = float(request.POST.get('K'))
            if K <= 0:
                errors['K'] = 'Strike Price (K) must be greater than 0.'
        except (ValueError, TypeError):
            errors['K'] = 'Invalid Strike Price (K).'

        try:
            T = float(request.POST.get('T'))
            if T <= 0:
                errors['T'] = 'Time to Maturity (T) must be greater than 0.'
        except (ValueError, TypeError):
            errors['T'] = 'Invalid Time to Maturity (T).'

        try:
            r = float(request.POST.get('r'))
            if not (0.0 <= r <= 100):
                errors['r'] = 'Risk-Free Rate (r) must be between 0 and 100.'
        except (ValueError, TypeError):
            errors['r'] = 'Invalid Risk-Free Rate (r).'

        try:
            sigma = float(request.POST.get('sigma'))
            if not (0.1 <= sigma <= 200):
                errors['sigma'] = 'Volatility (sigma) must be between 0.1 and 200.'
        except (ValueError, TypeError):
            errors['sigma'] = 'Invalid Volatility (sigma).'

        try:
            num_simulacoes = int(request.POST.get('num_simulacoes'))
            if not (1000 <= num_simulacoes <= 10000):
                errors['num_simulacoes'] = 'Number of Simulations must be between 1,000 and 100,000.'
        except (ValueError, TypeError):
            errors['num_simulacoes'] = 'Invalid Number of Simulations.'
            
        try:
            num_passos = int(request.POST.get('num_passos'))
            if not (10 <= num_passos <= 1000):
                errors['num_passos'] = 'Number of Time Steps must be between 10 and 1,000.'
        except (ValueError, TypeError):
            errors['num_passos'] = 'Invalid Number of Time Steps.'

        option_type = request.POST.get('option_type')
        if option_type not in ['put', 'call']:
            errors['option_type'] = 'Invalid option type selected.'

        if errors:
            return JsonResponse({'errors': errors}, status=400)

        try:
            # Call the calculation function with the validated data
            option_price, S_paths, boundary, discounted_cashflows = american_option_lsmc(
                S0, K, T, r, sigma, num_simulacoes, num_passos, option_type
            )
            
            # 2. Gera os gráficos (passando os cashflows)
            convergence_plot_b64, paths_plot_b64, boundary_plot_b64 = create_american_option_plots(
                S_paths, boundary, option_type, discounted_cashflows
            )
            
            # Return the results as a JSON response
            return JsonResponse({
                            'preco_estimado': f'{option_price:.4f}',
                            'convergence_plot': convergence_plot_b64, # NOVO
                            'price_plot': paths_plot_b64,
                            'exercise_boundary_plot': boundary_plot_b64,
                        })
        except Exception as e:
            # Log the exception for debugging purposes
            print(f"An error occurred during simulation: {e}")
            return JsonResponse({'error': 'An unexpected error occurred during the simulation.'}, status=500)

    else: # GET request
        # Provide initial data for the form when the page is first loaded
        initial_data = {
            'S0': request.GET.get('S0', 100.0),
            'K': request.GET.get('K', 100.0),
            'T': request.GET.get('T', 1.0),
            'r': request.GET.get('r', 5.0),
            'sigma': request.GET.get('sigma', 20.0),
            'num_simulacoes': request.GET.get('num_simulacoes', 10000),
            'num_passos': request.GET.get('num_passos', 100),
            'option_type': request.GET.get('option_type', 'put'), # Default option type
        }
        context = {
            'initial_data': initial_data,
            'language': request.session.get('language', 'pt')
        }
        # Ensure this template path matches your project structure
        return render(request, 'site/financeiros/options_price_american_mcs.html', context)


@require_POST 
def save_mcs_model(request):
    try:
        data = json.loads(request.body)
        model_type = data.get('model_type')
        parameters = data.get('parameters')
        results = data.get('results')
        title = data.get('title', 'Financial Report') 

        if not all([model_type, parameters, results]):
            return JsonResponse({'success': False, 'error': 'Missing data in request.'}, status=400)

        financial_model = FinantialModels(
            usuario=request.user,
            model_type=model_type,
            parameters=parameters,
            results=results,
            report='online'
        )
        financial_model.save()
        
        return JsonResponse({'success': True, 'message': 'Project saved successfully!', 'id': financial_model.id})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON format.'}, status=400)
    except Exception as e:
        # Log the full error for debugging
        print(f"Error in save_financial_model_view: {e}")
        return JsonResponse({'success': False, 'error': f'An unexpected error occurred: {e}'}, status=500)


@login_required(login_url='/admin/login/')
def view_report_view(request, simulation_id):
    simulation = get_object_or_404(FinantialModels, id=simulation_id, usuario=request.user)
    
    resultados = simulation.results
    parameters = simulation.parameters
    model_type = simulation.model_type
    context = {}
    language = request.session.get('language', 'pt')

    base_context = {
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
        'report_title': f"Relatório - {simulation.get_model_type_display()}",
        'language': language
    }

    if model_type in ('BLACK_SCHOLES','BLACK_SCHOLES_MERTON', 'GENERALIZED_BLACK_SCHOLES_MERTON'):
        context = {
            **base_context,
            'parameters': parameters,
            'results': {
                'Option price': resultados.get('option_price'),
                'd1': resultados.get('d1'),
                'd2': resultados.get('d2'),
                'N(d1)': resultados.get('n_d1'),
                'N(d2)': resultados.get('n_d2'),
                'Break-even point': resultados.get('break_even'),
                'Max loss': resultados.get('max_loss'),
            },
            'nested_results': {
                'Greeks (Medidas de Sensibilidade)': resultados.get('greeks', {})
            },
            'interpretation': resultados.get('interpretation'),
            'charts': {
                'Lucro/Prejuízo no Vencimento': resultados.get('payoff_plot'),
            }
        }
    elif model_type in ('COX_ROSS',):
        context = {
            **base_context,
            'parameters': parameters,
            'results': {
                'Option price': resultados.get('option_price'),
                'Up factor': resultados.get('upFactor'),
                'Down factor': resultados.get('d2'),
                'Break-even point': resultados.get('break_even'),
                'Max loss': resultados.get('max_loss'),
                'Risk-neutral probability (%)': (round(float(resultados.get('prob')),3)*100),
                'VPL Tradicional':resultados.get('traditionalNPV'),
                'VPL expandido':resultados.get('expandedNPV'),
                'Valor da opção / custo':resultados.get('optionRatio'),
            },
            'nested_results': {
                'Greeks (Medidas de Sensibilidade)': resultados.get('greeks', {})
            },
            'interpretation': resultados.get('interpretation'),
            'latticeContainer':  resultados.get('lattice'),
        }
    elif model_type in ('MONTE_CARLO_EUROPEAN', 'MONTE_CARLO_AMERICAN'):
        param_labels = {
            'en': {
                'S0': 'Initial Price (S0)', 'K': 'Strike Price (K)', 'T': 'Time to Maturity (T in years)',
                'r': 'Risk-Free Rate (r, %)', 'sigma': 'Volatility (σ, %)', 'num_simulacoes': 'Number of Simulations',
                'option_type': 'Option Type', 'num_passos': 'Number of Time Steps',
            },
            'pt': {
                'S0': 'Preço Atual do Ativo (S0)', 'K': 'Preço de Exercício (K)', 'T': 'Tempo até o Vencimento (T em anos)',
                'r': 'Taxa de Juros Livre de Risco (r, %)', 'sigma': 'Volatilidade (σ, %)', 'num_simulacoes': 'Número de Simulações',
                'option_type': 'Tipo de Opção', 'num_passos': 'Número de Passos de Tempo',
            }
        }
        labels_for_lang = param_labels.get(language, param_labels['pt'])
        formatted_params = {labels_for_lang.get(key, key): value for key, value in parameters.items()}
        
        base_context['parameters'] = formatted_params

        if model_type == 'MONTE_CARLO_EUROPEAN':
            context = {
                **base_context,
                'results': { 'Estimated Option Price': resultados.get('estimated_price'), },
                'nested_results': { 'Descriptive Statistics (Final Prices)': resultados.get('statistics', {}) },
                'charts': {
                    'Mean Price Convergence': resultados.get('price_plot'),
                    'Final Price Distribution': resultados.get('distribution_plot'),
                },
                'interpretation': resultados.get('interpretation'), 
            }
        elif model_type == 'MONTE_CARLO_AMERICAN':
            context = {
                **base_context,
                'results': { 'Estimated Option Price': resultados.get('preco_estimado'), },
                'nested_results': {},
                'charts': {
                    'Simulated Price Paths': resultados.get('price_plot'),
                    'Optimal Exercise Boundary': resultados.get('exercise_boundary_plot'),
                },
                'interpretation': resultados.get('interpretation'),
            }

    return render(request, "site/financeiros/report/report_template.html", context)


@login_required(login_url='/admin/login/')
def rerun_simulation_view(request, simulation_id):
    simulation = get_object_or_404(FinantialModels, id=simulation_id, usuario=request.user)
    params = simulation.parameters

    if simulation.model_type == 'BLACK_SCHOLES':
        template_name = 'site/financeiros/black-sholes.html'
    elif simulation.model_type == 'BLACK_SCHOLES_MERTON':
        template_name = 'site/financeiros/black-scholes-merton.html'
    elif simulation.model_type == 'GENERALIZED_BLACK_SCHOLES_MERTON':
        template_name = 'site/financeiros/generalized-black-scholes-merton.html'
    elif simulation.model_type == 'COX_ROSS':
        template_name = 'site/financeiros/cox-ross-rubinstein.html'
    elif simulation.model_type == 'MONTE_CARLO_EUROPEAN':
        template_name = 'site/financeiros/options_price_mcs.html'
    elif simulation.model_type == 'MONTE_CARLO_AMERICAN':
        template_name = 'site/financeiros/options_price_american_mcs.html'
    else:
        return redirect('simulation_list')

    context = {
        'initial_data': params,
        'language': request.session.get('language', 'pt')
    }
    return render(request, template_name, context)

@login_required(login_url='/admin/login/')
def generalized_black_scholes_merton_template(request):
    initial_data = {
        'asset_price': request.GET.get('asset_price', 100.0),
        'exercise_price': request.GET.get('exercise_price', 100.0),
        'time_to_expiration': request.GET.get('time_to_expiration', 30),
        'interest_rate': request.GET.get('interest_rate', 5),
        'volatility': request.GET.get('volatility', 20),
        'cost_of_carry': request.GET.get('cost_of_carry', 5),
        'option_type': request.GET.get('option_type', 'call'),
    }
    context = {
        'initial_data': initial_data,
        'language': request.session.get('language', 'pt')
    }
    return render(request, "site/financeiros/generalized-black-scholes-merton.html", context)


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
    try:
        data = json.loads(request.body)
        simulation_id = data.get('id')
        new_name = data.get('name', '').strip()

        if not simulation_id or not new_name:
            return JsonResponse({'status': 'error', 'message': 'Missing data.'}, status=400)

        simulation = get_object_or_404(FinantialModels, id=simulation_id, usuario=request.user)
        simulation.name = new_name
        simulation.save()

        return JsonResponse({'status': 'success', 'message': 'Name updated successfully.'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)
    except FinantialModels.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Simulation not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)