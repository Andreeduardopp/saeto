"""
Labels of the statistics the stochastic-process screens show.

The simulators return statistics by key and save them that way, so a report
is labelled in the language it is opened in, not the one the run was saved in.
The screens get the labels of the session language through `stat_labels()`.
"""

STAT_LABELS = {
    'mean': ('Média', 'Mean'),
    'mean_theoretical': ('Média (teórica)', 'Mean (theoretical)'),
    'median': ('Mediana', 'Median'),
    'std': ('Desvio padrão', 'Standard deviation'),
    'std_theoretical': ('Desvio padrão (teórico)', 'Standard deviation (theoretical)'),
    'variance': ('Variância', 'Variance'),
    'variance_theoretical': ('Variância (teórica)', 'Variance (theoretical)'),
    'min': ('Mínimo', 'Min'),
    'max': ('Máximo', 'Max'),
    'p5': ('Percentil 5%', '5th percentile'),
    'p95': ('Percentil 95%', '95th percentile'),
    'final': ('Valor final', 'Final value'),
    'expected_return': ('Retorno médio (%)', 'Mean return (%)'),
    'standard_error': ('Erro padrão da média', 'Standard error of the mean'),
    'ci_lower': ('Limite inferior (IC 95%)', 'Lower bound (95% CI)'),
    'ci_upper': ('Limite superior (IC 95%)', 'Upper bound (95% CI)'),
}


def stat_label(key, language):
    pt, en = STAT_LABELS.get(key, (key, key))
    return en if language == 'en' else pt


def stat_labels(language):
    return {key: stat_label(key, language) for key in STAT_LABELS}
