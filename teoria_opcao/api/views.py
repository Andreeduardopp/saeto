from django.shortcuts import render
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
import numpy as np
import math
import json

from financial_options.api.views import _render_screen
from financial_options.models import FinantialModelsChoices

@login_required(login_url='/admin/login/')
def volatilidade_template(request):
    return _render_screen(request, FinantialModelsChoices.RETURN_VOLATILITY)


@login_required(login_url='/admin/login/')
def log_cf_volatility(request):
    """
    Deterministic volatility estimation approach using Logarithm Cash Flow Return.
    This is primarily used as a reference approach.
    """
    context = {
        "title": "Logarithm Cash Flow Return (LOG CF)",
        "description": "A deterministic approach used as a reference for volatility estimation in real options.",
    }
    return render(request, "site/teoria/volatility/log_cf.html", context)


@login_required(login_url='/admin/login/')
def copeland_antikarov_volatility(request):
    """
    Stochastic approach for volatility estimation using Copeland & Antikarov method.
    This method treats PV₀ as constant during simulation while CF₁ and PV₁ are stochastic.
    """
    return render(request, "site/teoria/copeland-antikarov-template.html")


@login_required(login_url='/admin/login/')
def herath_park_volatility(request):
    return render(request, "site/teoria/herath_park.html")


@login_required(login_url='/admin/login/')
def brandao_dyer_hahn_volatility(request):
    """
    Stochastic approach for volatility estimation using Brandão, Dyer & Hahn method.
    This method uses conditional probability where CF₂, CF₃, etc. are dependent on CF₁.
    """
    context = {
        "title": "Brandão, Dyer & Hahn Approach",
        "description": "Method where PV₀ and PV₁ are deterministic while CF₁ is stochastic, using conditional probability.",
    }
    return render(request, "site/teoria/volatility/brandao_dyer_hahn.html", context)


@login_required(login_url='/admin/login/')
def markowitz_mean_variance_volatility(request):
    """
    Stochastic approach for volatility estimation using Markowitz Mean-Variance method.
    This method calculates volatility as the coefficient of variation of NPV.
    """
    context = {
        "title": "Markowitz Mean-Variance Method",
        "description": "Method that calculates volatility as the coefficient of variation (σ/μ) of NPV.",
        "formula": "σₑ₋ᵥ(NPV) = σNPV/μNPV",
    }
    return render(
        request, "site/teoria/volatility/markowitz_mean_variance.html", context
    )


@login_required(login_url='/admin/login/')
def lewis_irr_volatility(request):
    """
    Stochastic approach for volatility estimation using Lewis et al. method.
    This method calculates volatility as the coefficient of variation of IRR.
    """
    context = {
        "title": "Lewis et al. IRR Approach",
        "description": "Method that calculates volatility as the coefficient of variation (σ/μ) of IRR.",
        "formula": "σₑ₋ᵥ(IRR) = σIRR/μIRR",
    }
    return render(request, "site/teoria/volatility/lewis_irr.html", context)


@login_required(login_url='/admin/login/')
def var_based_volatility(request):
    """
    New stochastic approach proposed by the authors for volatility estimation.
    This method is based on Value at Risk (VaR) at 5% level.
    """
    context = {
        "title": "Value at Risk (VaR) Approach",
        "description": "A new method based on management assumption using the Value at Risk (VaR).",
        "formula": "σ = (μNPV - VaR(5%))/(1.6449 × μNPV)",
    }
    return render(request, "site/teoria/volatility/var_based.html", context)


@login_required(login_url='/admin/login/')
def volatility_comparison(request):
    """
    Comprehensive view for comparing all volatility estimation methods.
    """
    context = {
        "title": "Volatility Methods Comparison",
        "description": "Compare results from different volatility estimation methods for the same investment project.",
    }
    return render(request, "site/teoria/volatility/comparison.html", context)



@login_required(login_url='/admin/login/')
def binomial_model_view(request):
    """
    View function to render the binomial model template.
    """
    return render(request, 'site/teoria/binomial_model.html')


@require_http_methods(["POST"])
def calculate_binomial_option(request):
    """
    API endpoint to calculate binomial option values.
    This could be used if you want to implement AJAX calls instead of client-side calculations.
    """
    try:
        # Parse JSON data from request
        data = json.loads(request.body)
        
        # Extract parameters
        S0 = float(data.get('initialValue', 1000000))
        K = float(data.get('strikePrice', 900000))
        T = float(data.get('timeToMaturity', 5))
        r = float(data.get('riskFreeRate', 5)) / 100
        sigma = float(data.get('volatility', 20)) / 100
        N = int(data.get('steps', 5))
        option_type = data.get('optionType', 'call')
        exercise_style = data.get('exerciseStyle', 'european')
        
        # Calculate option value using binomial model
        option_value, details = calculate_binomial_model(
            S0, K, T, r, sigma, N, option_type, exercise_style
        )
        
        # Return JSON response with results
        return JsonResponse({
            'success': True,
            'optionValue': option_value,
            'details': details
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


def calculate_binomial_model(S0, K, T, r, sigma, N, option_type='call', exercise_style='european'):

    dt = T / N
    
    u = math.exp(sigma * math.sqrt(dt))
    d = 1 / u
    
    p = (math.exp(r * dt) - d) / (u - d)
    
    stock_tree = np.zeros((N + 1, N + 1))
    option_tree = np.zeros((N + 1, N + 1))
    
    stock_tree[0, 0] = S0
    
    for i in range(1, N + 1):
        stock_tree[i, 0] = stock_tree[i-1, 0] * d
        for j in range(1, i + 1):
            stock_tree[i, j] = stock_tree[i-1, j-1] * u
    
    for j in range(N + 1):
        if option_type == 'call':
            option_tree[N, j] = max(0, stock_tree[N, j] - K)
        else:  # put option
            option_tree[N, j] = max(0, K - stock_tree[N, j])
    
    for i in range(N - 1, -1, -1):
        for j in range(i + 1):
            expected_value = math.exp(-r * dt) * (p * option_tree[i+1, j+1] + (1 - p) * option_tree[i+1, j])
            
            if exercise_style == 'american':
                if option_type == 'call':
                    exercise_value = max(0, stock_tree[i, j] - K)
                else:
                    exercise_value = max(0, K - stock_tree[i, j])
                option_tree[i, j] = max(expected_value, exercise_value)
            else:
                option_tree[i, j] = expected_value
    
    traditional_npv = S0 - K  
    option_value = option_tree[0, 0]
    expanded_npv = traditional_npv + option_value
    flexibility_value = option_value
    option_ratio = option_value / K if K != 0 else 0
    
    # Prepare lattice data for visualization
    lattice_data = {
        'stockTree': stock_tree.tolist(),
        'optionTree': option_tree.tolist()
    }
    
    # Compile results
    details = {
        'upFactor': u,
        'downFactor': d,
        'probability': p,
        'deltaT': dt,
        'traditionalNPV': traditional_npv,
        'expandedNPV': expanded_npv,
        'flexibilityValue': flexibility_value,
        'optionRatio': option_ratio,
        'lattice': lattice_data
    }
    
    return option_value, details