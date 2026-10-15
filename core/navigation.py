"""Explicit, shared catalogue of full pages and their legacy fragment views."""
from dataclasses import dataclass
from django.urls import reverse


@dataclass(frozen=True)
class Page:
    slug: str
    view: str
    pt: str
    en: str
    enhanced: bool = False
    parent: str = ''


PAGES = [
    Page('retorno-volatilidade', 'volatilidade_template', 'Retorno e volatilidade', 'Return and volatility', True),
    Page('conceitos-basicos', 'basic_concepts_overview', 'Conceitos básicos', 'Basic concepts', True),
    Page('black-scholes', 'black_scholes_overview', 'Modelos Black-Scholes-Merton', 'Black-Scholes-Merton models', True),
    Page('cox-ross', 'cox_ross_overview', 'Modelos Cox-Ross-Rubinstein', 'Cox-Ross-Rubinstein models', True),
    Page('monte-carlo', 'monte_carlo_overview', 'Métodos de Monte Carlo', 'Monte Carlo methods', True),
    Page('diferencas-finitas', 'finite_difference_overview', 'Diferenças finitas', 'Finite differences', True),
    Page('call-put', 'call_put_options', 'Call e Put', 'Call and Put', parent='conceitos-basicos'),
    Page('ativo-put', 'asset_put_combination', 'Ativo + Put', 'Asset + Put', parent='conceitos-basicos'),
    Page('bull-bear', 'bull_bear_spread', 'Bull/Bear Spread', 'Bull/Bear Spread', parent='conceitos-basicos'),
    Page('collar', 'collar_strategy_simulator', 'Collar', 'Collar', parent='conceitos-basicos'),
    Page('bs', 'black_scholes_api', 'Black-Scholes', 'Black-Scholes', parent='black-scholes'),
    Page('bsm', 'black_scholes_merton_api', 'Black-Scholes-Merton', 'Black-Scholes-Merton', parent='black-scholes'),
    Page('gbsm', 'generalized_black_scholes_merton', 'BSM generalizado', 'Generalized BSM', parent='black-scholes'),
    Page('crr', 'cox_ross_rubinstein', 'Cox-Ross-Rubinstein', 'Cox-Ross-Rubinstein', parent='cox-ross'),
    Page('mc-europeu', 'precificar_opcao', 'Monte Carlo europeu', 'European Monte Carlo', parent='monte-carlo'),
    Page('mc-americano', 'precificar_opcao_americana', 'Monte Carlo americano', 'American Monte Carlo', parent='monte-carlo'),
    Page('fdm-europeu', 'european_finite_difference', 'Diferenças finitas europeias', 'European finite differences', parent='diferencas-finitas'),
    Page('binomial-real', 'binomial_model', 'Modelo binomial real', 'Real binomial model'),
    Page('copeland-antikarov', 'copeland_antikarov_volatility', 'Copeland & Antikarov', 'Copeland & Antikarov'),
    Page('herath-park', 'herath_park_volatility', 'Herath & Park', 'Herath & Park'),
    Page('markov', 'cadeia_markov', 'Cadeias de Markov', 'Markov chains'),
    Page('random-walk', 'random_walk_overview', 'Random Walk', 'Random Walk', True),
    Page('random-walk-normal', 'random_walk_normal', 'Random Walk Normal', 'Normal Random Walk', parent='random-walk'),
    Page('random-walk-simples', 'random_walk_template', 'Random Walk simples', 'Simple Random Walk', parent='random-walk'),
    Page('browniano', 'mbg_overview', 'Movimento Browniano', 'Brownian motion', True),
    Page('abm', 'abm', 'Movimento Browniano aritmético', 'Arithmetic Brownian motion', parent='browniano'),
    Page('mbg-monte-carlo', 'monte_carlos', 'MBG Monte Carlo', 'GBM Monte Carlo', parent='browniano'),
    Page('mbg-ito', 'mbg_ito', 'MBG Itô', 'GBM Itô', parent='browniano'),
    Page('reversao-media', 'modelo_reversao_media', 'Reversão à média', 'Mean reversion'),
    Page('comparacao', 'vizualizacao_modelos', 'Visualização dos modelos', 'Model visualization'),
    Page('dilema-prisioneiro', 'dilema_do_prisioneiro', 'Dilema do Prisioneiro', "Prisoner's dilemma"),
    Page('projetos', 'simulation_list', 'Projetos salvos', 'Saved projects', True),
    Page('referencias', 'references', 'Referências', 'References', True),
    Page('aplicacoes', 'to_do', 'Aplicações', 'Applications', True),
    Page('perfil', 'perfil_view', 'Perfil', 'Profile'),
]
BY_SLUG = {page.slug: page for page in PAGES}
BY_VIEW = {page.view: page for page in PAGES}


def page_url(page):
    if page.slug == 'retorno-volatilidade':
        return reverse('return_volatility_page')
    return reverse('tool_page', kwargs={'slug': page.slug})


def canonical_url(view, *args):
    if view == 'rerun_simulation':
        return reverse('project_page', args=args)
    return page_url(BY_VIEW[view]) if view in BY_VIEW else reverse(view, args=args)


def navigation_context(request, page=None, project_id=None, enhanced=True):
    lang = request.session.get('language', 'pt')
    routes = [{'url': page_url(p), 'legacy': reverse(p.view), 'key': p.slug,
               'title': p.en if lang == 'en' else p.pt, 'enhanced': p.enhanced,
               'menu': p.parent or p.slug} for p in PAGES]
    routes.append({'url': reverse('home'), 'legacy': reverse('home'), 'key': 'home',
                   'title': 'SAETO', 'enhanced': True, 'menu': 'home'})
    key = page.slug if page else 'home'
    title = (page.en if lang == 'en' else page.pt) if page else 'SAETO'
    menu = 'projetos' if project_id else (page.parent or key) if page else key
    return {'page_title': title, 'navigation': {
        'routes': routes, 'user': str(request.user.pk), 'lang': lang,
        'key': key, 'project': str(project_id or ''), 'enhanced': enhanced,
        'url': request.get_full_path(), 'title': title,
        'menu': menu,
    }}
