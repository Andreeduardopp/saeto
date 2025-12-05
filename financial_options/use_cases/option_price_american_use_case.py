import numpy as np
import matplotlib
matplotlib.use('Agg') # Importante para evitar erros de GUI no servidor
import matplotlib.pyplot as plt
import io
import base64

def american_option_lsmc(S0, K, T, r, sigma, num_simulacoes, num_passos, option_type='put'):
    """
    Calcula o preço de uma opção Americana usando Longstaff-Schwartz (LSM).
    Retorna também o vetor de cashflows descontados para análise estatística.
    """
    dt = T / num_passos
    r_dec = r / 100.0
    sigma_dec = sigma / 100.0

    # 1. Gerar caminhos (Movimento Browniano Geométrico)
    S = np.zeros((num_passos + 1, num_simulacoes))
    S[0] = S0
    for t in range(1, num_passos + 1):
        z = np.random.standard_normal(num_simulacoes)
        S[t] = S[t - 1] * np.exp((r_dec - 0.5 * sigma_dec**2) * dt + sigma_dec * np.sqrt(dt) * z)

    # 2. Calcular payoff no vencimento
    if option_type == 'put':
        payoff = np.maximum(K - S, 0)
    else:
        payoff = np.maximum(S - K, 0)

    # cash_flow representa o valor da opção se exercida ou mantida (trazida a valor presente passo a passo)
    cash_flow = payoff[-1]
    
    # Para plotagem da fronteira
    exercise_boundary = np.full(num_passos + 1, np.nan)
    exercise_boundary[-1] = K

    # 3. Indução Retroativa (LSM)
    discount_factor = np.exp(-r_dec * dt)
    
    for t in range(num_passos - 1, 0, -1):
        # Desconta o cashflow do passo t+1 para t
        cash_flow = cash_flow * discount_factor
        
        in_the_money = payoff[t] > 0
        if not np.any(in_the_money):
            continue

        X = S[t, in_the_money]
        Y = cash_flow[in_the_money]
        
        # Regressão Polinomial (Grau 2) para estimar valor de continuação
        regression = np.polyfit(X, Y, 2)
        continuation_value = np.polyval(regression, X)
        
        # Lógica da Fronteira de Exercício (Apenas para visualização)
        try:
            if option_type == 'put':
                # K - x = ax^2 + bx + c
                coeffs = [regression[0], regression[1] + 1, regression[2] - K]
                roots = np.roots(coeffs)
                valid_roots = roots[(np.isreal(roots)) & (roots > 0) & (roots < S0*3)]
                if len(valid_roots) > 0:
                    exercise_boundary[t] = np.max(valid_roots.real) # Fronteira Put é o valor crítico superior para exercício "abaixo"
            else:
                # x - K = ax^2 + bx + c
                coeffs = [regression[0], regression[1] - 1, regression[2] + K]
                roots = np.roots(coeffs)
                valid_roots = roots[(np.isreal(roots)) & (roots > 0) & (roots < S0*3)]
                if len(valid_roots) > 0:
                     exercise_boundary[t] = np.min(valid_roots.real)
        except:
            pass

        # Decisão de exercício antecipado
        exercise_now = payoff[t, in_the_money] > continuation_value
        
        # Onde exercemos, o cashflow se torna o payoff imediato
        # Onde não exercemos, o cashflow continua sendo o valor futuro descontado (que já está em 'cash_flow')
        indices_itm = np.where(in_the_money)[0]
        indices_exercise = indices_itm[exercise_now]
        cash_flow[indices_exercise] = payoff[t, indices_exercise]

    # Desconto final de t=1 para t=0
    discounted_cashflows = cash_flow * discount_factor
    
    option_price = np.mean(discounted_cashflows)
    
    return option_price, S, exercise_boundary, discounted_cashflows

def create_american_option_plots(S, exercise_boundary, option_type, discounted_cashflows):
    """
    Gera 3 gráficos: Convergência, Caminhos e Fronteira.
    """
    plt.style.use('seaborn-v0_8-darkgrid')
    
    # --- Gráfico 1: Convergência do Preço (Igual ao Europeu) ---
    n_simulations = len(discounted_cashflows)
    n_range = np.arange(1, n_simulations + 1)
    
    cumulative_mean = np.cumsum(discounted_cashflows) / n_range
    cumulative_sq_mean = np.cumsum(discounted_cashflows ** 2) / n_range
    running_var = cumulative_sq_mean - (cumulative_mean ** 2)
    running_var[running_var < 0] = 0
    running_std = np.sqrt(running_var)
    standard_error = running_std / np.sqrt(n_range)
    
    z_score = 1.96 # 95% IC
    upper_bound = cumulative_mean + (z_score * standard_error)
    lower_bound = cumulative_mean - (z_score * standard_error)

    fig1, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(n_range, cumulative_mean, color='#333333', lw=1.5, label='Preço Estimado')
    ax1.fill_between(n_range, lower_bound, upper_bound, color='gray', alpha=0.3, label='IC 95%')
    ax1.axhline(y=cumulative_mean[-1], color='firebrick', linestyle='--', alpha=0.8, label=f'Final: {cumulative_mean[-1]:.2f}')
    
    ax1.set_title('Convergência do Preço da Opção Americana')
    ax1.set_xlabel('Simulações')
    ax1.set_ylabel('Preço')
    ax1.legend()
    ax1.grid(True, alpha=0.5)
    
    if n_simulations > 200:
         ax1.set_xlim(left=0)

    buf1 = io.BytesIO()
    fig1.savefig(buf1, format='png', bbox_inches='tight')
    convergence_plot = base64.b64encode(buf1.getvalue()).decode('utf-8')
    plt.close(fig1)

    # --- Gráfico 2: Caminhos do Ativo (Limitado a 100 para performance) ---
    fig2, ax2 = plt.subplots(figsize=(8, 5))
    num_steps = S.shape[0] - 1
    time_grid = np.linspace(0, num_steps, num_steps + 1)
    
    # Plotar no máximo 100 caminhos para não pesar no HTML
    paths_to_show = min(100, S.shape[1])
    ax2.plot(time_grid, S[:, :paths_to_show], lw=1, alpha=0.4)
    
    ax2.set_title(f'Trajetórias do Ativo (Primeiros {paths_to_show})')
    ax2.set_xlabel('Passos de Tempo')
    ax2.set_ylabel('Preço do Ativo')
    
    buf2 = io.BytesIO()
    fig2.savefig(buf2, format='png', bbox_inches='tight')
    paths_plot = base64.b64encode(buf2.getvalue()).decode('utf-8')
    plt.close(fig2)

    # --- Gráfico 3: Fronteira de Exercício ---
    fig3, ax3 = plt.subplots(figsize=(8, 5))
    # Filtra NaNs para o plot ficar limpo
    valid_idx = ~np.isnan(exercise_boundary)
    if np.any(valid_idx):
        ax3.plot(time_grid[valid_idx], exercise_boundary[valid_idx], 'r-o', markersize=4, label='Fronteira Ótima')
    else:
        ax3.text(0.5, 0.5, "Exercício Antecipado não foi ótimo em nenhum ponto", ha='center')

    ax3.set_title(f'Fronteira de Exercício ({option_type.capitalize()})')
    ax3.set_xlabel('Passos de Tempo')
    ax3.set_ylabel('Preço do Ativo')
    ax3.legend()
    
    buf3 = io.BytesIO()
    fig3.savefig(buf3, format='png', bbox_inches='tight')
    boundary_plot = base64.b64encode(buf3.getvalue()).decode('utf-8')
    plt.close(fig3)

    return convergence_plot, paths_plot, boundary_plot