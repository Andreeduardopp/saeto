# core/precificacao_opcoes_monte_carlo.py
import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt
import io
import base64

def option_price_use_case(S0, K, T, r, sigma, num_simulacoes, option_type='call'):
    """
    Simula o preço de opções europeias usando o método de Monte Carlo.

    Args:
        S0 (float): Preço atual do ativo subjacente.
        K (float): Preço de exercício (strike) da opção.
        T (float): Tempo até o vencimento em anos.
        r (float): Taxa de juros livre de risco anual (em %).
        sigma (float): Volatilidade anual do ativo subjacente (em %).
        num_simulacoes (int): Número de simulações de Monte Carlo.
        option_type (str): Tipo da opção, 'call' ou 'put'.

    Returns:
        tuple: (preco_opcao, ST_array, statistics)
            preco_opcao (float): Preço estimado da opção europeia.
            ST_array (numpy.ndarray): Array dos preços simulados do ativo no vencimento.
            statistics (dict): Dicionário com estatísticas descritivas dos preços no vencimento.
    """
    # Converter taxas de porcentagem para decimal
    r_dec = r / 100.0
    sigma_dec = sigma / 100.0
    
    # Gerar números aleatórios da distribuição normal padrão
    z = np.random.standard_normal(num_simulacoes)
    
    # Simular os preços do ativo subjacente no vencimento (ST)
    ST = S0 * np.exp((r_dec - 0.5 * sigma_dec**2) * T + sigma_dec * np.sqrt(T) * z)

    # Calcular o payoff da opção com base no tipo
    if option_type == 'call':
        payoffs = np.maximum(ST - K, 0)
    elif option_type == 'put':
        payoffs = np.maximum(K - ST, 0)
    else:
        # Caso o tipo seja inválido, retorna um erro. A validação principal está na view.
        raise ValueError("Tipo de opção inválido. Escolha 'call' ou 'put'.")

    # Calcular o preço da opção como a média dos payoffs descontados
    preco_opcao = np.exp(-r_dec * T) * np.mean(payoffs)

    mean_st = np.mean(ST)
    std_st = np.std(ST, ddof=1) 
    n = len(ST)
    
    standard_error = std_st / np.sqrt(n)
    z_score = 1.96
    lower_ic = mean_st - (z_score * standard_error)
    upper_ic = mean_st + (z_score * standard_error)

    statistics = {
        "descriptive": {
            'Média (ST)': mean_st,
            'Mediana': np.median(ST),
            'Desvio Padrão': std_st,
            'Mínimo': np.min(ST),
            'Máximo': np.max(ST),
        },
        "inferential": {
            "Média Estimada": mean_st,
            "Erro Padrão": standard_error,
            "Limite Inferior (IC 95%)": lower_ic,
            "Limite Superior (IC 95%)": upper_ic
        }
    }

    return preco_opcao, ST, statistics

# core/precificacao_opcoes_monte_carlo.py

import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt
import io
import base64

# ... mantenha a função option_price_use_case igual ...

def create_plots(ST_array):
    """
    Cria gráficos para visualização dos resultados da simulação.
    Agora inclui o Intervalo de Confiança na convergência.
    """
    plt.style.use('seaborn-v0_8-darkgrid')
    
    # Prepara vetor de N (1 até número de simulações)
    n_simulations = len(ST_array)
    n_range = np.arange(1, n_simulations + 1)

    # --- Gráfico 1: Convergência da Média com Intervalo de Confiança ---
    
    # 1. Cálculo da Média Acumulada (E[x])
    cumulative_mean = np.cumsum(ST_array) / n_range

    # 2. Cálculo do Desvio Padrão Acumulada de forma vetorizada
    # Usamos a identidade: Var(X) = E[X^2] - (E[X])^2
    cumulative_sq_mean = np.cumsum(ST_array ** 2) / n_range
    running_var = cumulative_sq_mean - (cumulative_mean ** 2)
    # Correção para pequenos erros de ponto flutuante que podem gerar negativos
    running_var[running_var < 0] = 0 
    running_std = np.sqrt(running_var)

    # 3. Cálculo do Erro Padrão e Limites do IC (95% -> Z = 1.96)
    standard_error = running_std / np.sqrt(n_range)
    z_score = 1.96
    
    upper_bound = cumulative_mean + (z_score * standard_error)
    lower_bound = cumulative_mean - (z_score * standard_error)

    # Plotagem
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    
    # Plota a média simulada (Linha preta/escura)
    ax1.plot(n_range, cumulative_mean, color='#333333', lw=1.5, label='Média Simulada (MC)')
    
    # Plota a sombra do Intervalo de Confiança (Cinza)
    ax1.fill_between(n_range, lower_bound, upper_bound, color='gray', alpha=0.3, label='IC 95%')
    
    # Plota linha tracejada do valor final convergido (Vermelho)
    final_mean = cumulative_mean[-1]
    ax1.axhline(y=final_mean, color='firebrick', linestyle='--', alpha=0.8, label=f'Valor Final: {final_mean:.2f}')

    ax1.set_title('Convergência do Valor Esperado E(St) com IC 95%', fontsize=14)
    ax1.set_xlabel('Número de Simulações (n)', fontsize=12)
    ax1.set_ylabel('Preço Médio Estimado', fontsize=12)
    ax1.legend(loc='lower right')
    ax1.grid(True, alpha=0.5)
    
    # Para evitar que o gráfico fique muito "esticado" no início onde a variância é alta,
    # podemos focar o zoom após as primeiras 50 simulações se houver dados suficientes
    if n_simulations > 200:
        ax1.set_xlim(left=0) 
        # Opcional: ax1.set_ylim(bottom=min(lower_bound[50:]), top=max(upper_bound[50:]))

    buf_price = io.BytesIO()
    fig1.savefig(buf_price, format='png', bbox_inches='tight', dpi=100)
    data_price = base64.b64encode(buf_price.getvalue()).decode('utf-8')
    plt.close(fig1)

    fig2, ax2 = plt.subplots(figsize=(10, 6))
    
    # Melhorando o visual do histograma
    n, bins, patches = ax2.hist(ST_array, bins=70, density=True, alpha=0.7, color='steelblue', edgecolor='white', linewidth=0.5)
    
    # Adicionando uma linha de densidade (KDE simples ou apenas contorno)
    # Aqui apenas destacamos a média
    ax2.axvline(np.mean(ST_array), color='k', linestyle='dashed', linewidth=1, label=f'Média: {np.mean(ST_array):.2f}')
    
    ax2.set_title('Distribuição de Probabilidade dos Preços no Vencimento', fontsize=14)
    ax2.set_xlabel('Preço do Ativo (St)', fontsize=12)
    ax2.set_ylabel('Frequência / Densidade', fontsize=12)
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    buf_dist = io.BytesIO()
    fig2.savefig(buf_dist, format='png', bbox_inches='tight', dpi=100)
    data_dist = base64.b64encode(buf_dist.getvalue()).decode('utf-8')
    plt.close(fig2)

    return data_price, data_dist