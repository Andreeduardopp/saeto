import matplotlib
matplotlib.use('Agg') # Essencial para servidores web
import numpy as np
import matplotlib.pyplot as plt
import io
import base64

class MonteCarloUseCase:
    def __init__(self, S0, mu, sigma, time_unit, num_periods, num_simulations):
        self.S0 = float(S0)
        self.mu = float(mu)
        self.sigma = float(sigma)
        self.time_unit = time_unit
        self.num_periods = int(num_periods)
        self.num_simulations = int(num_simulations)
        self.prices = None

    def run_simulation(self):
        # Definição do dt baseada na unidade de tempo
        dt_map = {"Dia": 1/252, "Semana": 1/52, "Mês": 1/12, "Ano": 1.0}
        dt = dt_map.get(self.time_unit, 1.0)

        # Vetorização usando a Solução Exata do Movimento Browniano Geométrico (GBM)
        # S_t = S_0 * exp((mu - 0.5*sigma^2)*t + sigma*W_t)
        
        # 1. Gerar retornos aleatórios (movimento browniano)
        # Formato da matriz: (num_simulacoes, num_periodos)
        z = np.random.normal(0, 1, (self.num_simulations, self.num_periods))
        
        # 2. Calcular o expoente acumulado passo a passo
        drift = (self.mu - 0.5 * self.sigma**2) * dt
        diffusion = self.sigma * np.sqrt(dt) * z
        
        # 3. Calcular caminhos de preços
        # np.cumsum faz a soma acumulada ao longo do tempo (axis=1)
        log_returns = np.cumsum(drift + diffusion, axis=1)
        
        # Adicionar coluna de zeros no início para representar t=0 (Preço S0)
        log_returns = np.hstack((np.zeros((self.num_simulations, 1)), log_returns))
        
        self.prices = self.S0 * np.exp(log_returns)

        return self.prices

    def plot_simulation(self):
        plt.style.use('seaborn-v0_8-darkgrid')
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Plotar apenas os primeiros 100 caminhos para não pesar no gráfico
        paths_to_plot = min(100, self.num_simulations)
        ax.plot(self.prices[:paths_to_plot, :].T, lw=1, alpha=0.5)
        
        ax.set_title("Evolução dos Preços (Simulação Monte Carlo)")
        ax.set_xlabel(f"Períodos ({self.time_unit})")
        ax.set_ylabel("Preço do Ativo")
        ax.grid(True)

        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", bbox_inches='tight')
        buffer.seek(0)
        image_png = base64.b64encode(buffer.getvalue()).decode("utf-8")
        plt.close(fig)
        return image_png

    def get_final_price_distribution(self):
        plt.style.use('seaborn-v0_8-darkgrid')
        final_prices = self.prices[:, -1]
        
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.hist(final_prices, bins=50, alpha=0.75, color="steelblue", edgecolor="white")
        
        # Adiciona linha da média
        mean_price = np.mean(final_prices)
        ax.axvline(mean_price, color='firebrick', linestyle='--', label=f'Média: {mean_price:.2f}')
        
        ax.set_title("Distribuição dos Preços Finais")
        ax.set_xlabel("Preço do Ativo")
        ax.set_ylabel("Frequência")
        ax.legend()
        ax.grid(True)

        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", bbox_inches='tight')
        buffer.seek(0)
        image_png = base64.b64encode(buffer.getvalue()).decode("utf-8")
        plt.close(fig)
        return image_png

    def plot_convergence(self):
        """
        Gera o gráfico de convergência da média com Intervalo de Confiança de 95%.
        """
        plt.style.use('seaborn-v0_8-darkgrid')
        
        # Pegamos apenas os preços do último período de cada simulação
        final_prices = self.prices[:, -1]
        
        n_simulations = len(final_prices)
        n_range = np.arange(1, n_simulations + 1)

        # Cálculo vetorial da média acumulada e erro padrão
        cumulative_mean = np.cumsum(final_prices) / n_range
        
        # Variância acumulada: E[x^2] - (E[x])^2
        cumulative_sq_mean = np.cumsum(final_prices ** 2) / n_range
        running_var = cumulative_sq_mean - (cumulative_mean ** 2)
        running_var[running_var < 0] = 0 # Correção numérica
        running_std = np.sqrt(running_var)
        
        # Erro Padrão e IC 95%
        standard_error = running_std / np.sqrt(n_range)
        z_score = 1.96
        upper_bound = cumulative_mean + (z_score * standard_error)
        lower_bound = cumulative_mean - (z_score * standard_error)

        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Plot da média
        ax.plot(n_range, cumulative_mean, color='#333333', lw=1.5, label='Preço Médio Estimado')
        
        # Plot do IC (Sombra)
        ax.fill_between(n_range, lower_bound, upper_bound, color='gray', alpha=0.3, label='IC 95%')
        
        # Linha final
        ax.axhline(y=cumulative_mean[-1], color='firebrick', linestyle='--', alpha=0.8, label=f'Final: {cumulative_mean[-1]:.2f}')

        ax.set_title("Convergência da Média dos Preços Finais")
        ax.set_xlabel("Número de Simulações")
        ax.set_ylabel("Preço Médio Esperado")
        ax.legend()
        ax.grid(True, alpha=0.5)

        # Ajuste de zoom se houver muitas simulações
        if n_simulations > 200:
            ax.set_xlim(left=0)

        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", bbox_inches='tight')
        buffer.seek(0)
        image_png = base64.b64encode(buffer.getvalue()).decode("utf-8")
        plt.close(fig)
        return image_png

    def get_statistics(self):
        final_prices = self.prices[:, -1]
        n = len(final_prices)
        
        mean_val = np.mean(final_prices)
        std_dev = np.std(final_prices, ddof=1) # ddof=1 para desvio padrão amostral
        
        standard_error = std_dev / np.sqrt(n)
        z_score = 1.96
        lower_ic = mean_val - (z_score * standard_error)
        upper_ic = mean_val + (z_score * standard_error)

        return {
            "descriptive": {
                "Média (Esperança)": mean_val,
                "Desvio Padrão": std_dev,
                "Mínimo Absoluto": np.min(final_prices),
                "Máximo Absoluto": np.max(final_prices),
                "Retorno Médio (%)": (mean_val / self.S0 - 1) * 100
            },
            "inferential": {
                "Média Estimada": mean_val,
                "Erro Padrão da Média": standard_error,
                "Limite Inferior (IC 95%)": lower_ic,
                "Limite Superior (IC 95%)": upper_ic
            }
        }