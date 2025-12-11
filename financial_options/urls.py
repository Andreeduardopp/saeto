from django.urls import path
from .api.views import *

urlpatterns = [
    path('save-financial-model/', save_black_schole_model_view, name='save_financial_model'),
    path('save-mcs-model/', save_mcs_model, name='save_mcs_model'),
    path('black-scholes/api/', black_scholes_view, name='black_scholes_api'),
    path('black-scholes-merton/', black_scholes_merton_template, name='black_scholes_merton'),
    path('black-scholes-merton/api/', black_scholes_merton_view, name='black_scholes_merton_api'),
    path('generalized-black-scholes-merton/', generalized_black_scholes_merton_template, name='generalized_black_scholes_merton'),
    path('generalized-black-scholes-merton/api/', generalized_black_scholes_merton_view, name='generalized_black_scholes_merton_api'),
    path('cox-ross-rubinstein/', cox_ross_rubinstein_template, name='cox_ross_rubinstein'),
    path('api/cox-ross-rubinstein/', cox_ross_rubinstein_view, name='cox_ross_rubinstein_api'),
    path('precificar/', precificar_opcao_view, name='precificar_opcao'),
    path('precificar-americana/', precificar_opcao_americana_view, name='precificar_opcao_americana'),
    path('financial_options/basic_concepts/overview/', basic_concepts_overview_view, name='basic_concepts_overview'),
    path('financial_options/black_scholes/overview/', black_scholes_overview_view, name='black_scholes_overview'),
    path('financial_options/cox_ross/overview/', cox_ross_overview_view, name='cox_ross_overview'),
    path('financial_options/monte_carlo/overview/', monte_carlo_overview_view, name='monte_carlo_overview'),
    path('financial_options/finite_difference/overview/', finite_difference_overview_view, name='finite_difference_overview'),
    # path('financial_options/european_finite_difference/overview/', european_finite_difference_view, name='european_finite_difference'),
    path('pricing/fdm/european/', fdm_european_view, name='european_finite_difference'),
    path('pricing/fdm/european/', fdm_european_view, name='fdm_european_api'),
    path('report/view/<uuid:simulation_id>/', view_report_view, name='view_report'),
    path('financial_options/basic_concepts/call_put_options/', call_put_options_view, name='call_put_options'),
    path('financial_options/basic_concepts/asset_put_combination/', asset_put_combination_view, name='asset_put_combination'),
    path('financial_options/basic_concepts/bull_bear_spread/', bull_bear_spread_view, name='bull_bear_spread'),
    path('financial_options/basic_concepts/collar_strategy_simulator/', collar_strategy_simulator_view, name='collar_strategy_simulator'),

    path('rerun_simulation/<uuid:simulation_id>/', rerun_simulation_view, name='rerun_simulation'),
    path('api/update_simulation_name/', update_simulation_name, name='update_simulation_name'),
]