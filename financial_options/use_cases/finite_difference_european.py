import numpy as np
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from scipy.interpolate import interp1d

class FDMEuropeanUseCase:
    def __init__(self, S0, K, r, sigma, T, option_type='call', N_space=1000):
        self.S0 = float(S0)
        self.K = float(K)
        self.r = float(r) / 100.0
        self.sigma = float(sigma) / 100.0
        self.T = float(T) / 365.0  
        self.option_type = option_type
        
        self.x_min = -5.0
        self.x_max = 5.0
        self.N_space = int(N_space)
        
        self.dx = (self.x_max - self.x_min) / self.N_space
        self.x_values = np.linspace(self.x_min, self.x_max, self.N_space + 1)
        
        self.final_price = 0.0
        self.u_final = None      # A curva u(x) final
        self.V_final_curve = None # A curva V(S) final (preço real)
        self.S_grid_real = None   # O grid de preços reais correspondente
        self.M_time = 0           # Será calculado dinamicamente

    def solve(self):
        sigma2 = self.sigma**2
        k_param = (2 * self.r) / sigma2
        alpha = -0.5 * (k_param - 1)
        beta  = -0.25 * ((k_param + 1)**2)
        
        # Tau máximo (Tempo transformado)
        tau_max = 0.5 * sigma2 * self.T

        # --- 2. Estabilidade (Cálculo do M dinâmico) ---
        # Condição CFL: dt <= 0.5 * dx^2 (usamos 0.45 para segurança)
        dt_stability = 0.45 * (self.dx**2)
        
        # Calculamos quantos passos de tempo são necessários
        self.M_time = int(np.ceil(tau_max / dt_stability))
        dt = tau_max / self.M_time
        gamma = dt / (self.dx**2)

        # --- 3. Condição Inicial (Payoff Transformado) ---
        # u(x, 0) = e^(-alpha*x) * Payoff(S)
        u = np.zeros(self.N_space + 1)
        
        for i in range(self.N_space + 1):
            if self.option_type == 'call':
                if self.x_values[i] > 0: # S > K
                    payoff_val = np.exp(self.x_values[i]) - 1.0
                    u[i] = np.exp(-alpha * self.x_values[i]) * payoff_val
            else: # Put
                if self.x_values[i] < 0: # S < K
                    payoff_val = 1.0 - np.exp(self.x_values[i])
                    u[i] = np.exp(-alpha * self.x_values[i]) * payoff_val

        # --- 4. Loop Temporal (Esquema Explícito) ---
        u_new = np.zeros_like(u)
        
        # Pré-cálculo de termos constantes para a fronteira (Otimização)
        term_S_factor = 1 - alpha
        term_K_factor = -(k_param + beta)

        # Matriz para guardar snapshot do heatmap (opcional, para não pesar memória)
        # Vamos salvar apenas 50 snapshots ao longo do tempo para o gráfico
        snapshot_interval = max(1, self.M_time // 50)
        self.heatmap_data = []

        for j in range(self.M_time):
            current_tau = (j + 1) * dt
            
            # Equação de Difusão (Vetorizada para performance)
            # u_new[i] = gamma*u[i-1] + (1-2gamma)*u[i] + gamma*u[i+1]
            u_new[1:-1] = gamma * u[0:-2] + (1 - 2*gamma) * u[1:-1] + gamma * u[2:]

            # --- Condições de Contorno ---
            if self.option_type == 'call':
                u_new[0] = 0.0 # S -> 0
                # Fronteira direita sofisticada (do seu código)
                term1 = np.exp(self.x_max * term_S_factor - beta * current_tau)
                term2 = np.exp(-alpha * self.x_max + term_K_factor * current_tau)
                u_new[-1] = term1 - term2
            else: # Put
                # Lógica espelhada para Put
                # S -> 0 (x -> -inf): Put vale K*e^-rt - S
                term1_put = np.exp(-alpha * self.x_min + term_K_factor * current_tau)
                term2_put = np.exp(self.x_min * term_S_factor - beta * current_tau)
                u_new[0] = term1_put - term2_put
                u_new[-1] = 0.0 # S -> Inf

            # Atualiza u
            u[:] = u_new[:]
            
            # Salvar snapshot para heatmap
            if j % snapshot_interval == 0:
                self.heatmap_data.append(u.copy())

        self.u_final = u

        # --- 5. Recuperação do Preço (Transformação Inversa) ---
        # V = K * e^(alpha*x + beta*tau) * u
        
        # Primeiro, calculamos o preço exato para o S0 solicitado usando interpolação
        x_target = np.log(self.S0 / self.K)
        u_interp = np.interp(x_target, self.x_values, u)
        
        factor = self.K * np.exp(alpha * x_target + beta * tau_max)
        self.final_price = factor * u_interp

        # Também vamos transformar a curva inteira de volta para Preços Reais (V vs S)
        # para poder plotar o gráfico em R$ e calcular Gregas
        self.S_grid_real = self.K * np.exp(self.x_values)
        self.V_final_curve = self.K * np.exp(alpha * self.x_values + beta * tau_max) * u
        
        return round(self.final_price, 4)

    def calculate_greeks(self):
        """
        Calcula as gregas usando diferenças finitas na curva final de Preços Reais (V vs S).
        Isso é feito após a transformação inversa.
        """
        # Encontrar o índice mais próximo de S0 no grid real
        idx = (np.abs(self.S_grid_real - self.S0)).argmin()
        
        # Garantir limites
        if idx < 1: idx = 1
        if idx >= len(self.S_grid_real) - 1: idx = len(self.S_grid_real) - 2

        S_minus = self.S_grid_real[idx-1]
        S_curr  = self.S_grid_real[idx]
        S_plus  = self.S_grid_real[idx+1]
        
        V_minus = self.V_final_curve[idx-1]
        V_curr  = self.V_final_curve[idx]
        V_plus  = self.V_final_curve[idx+1]

        # Delta: (V+ - V-) / (S+ - S-)
        delta = (V_plus - V_minus) / (S_plus - S_minus)
        
        # Gamma: Diferença dos Deltas / 0.5 * intervalo
        delta_plus = (V_plus - V_curr) / (S_plus - S_curr)
        delta_minus = (V_curr - V_minus) / (S_curr - S_minus)
        gamma = (delta_plus - delta_minus) / (0.5 * (S_plus - S_minus))
        
        # Theta: Precisaríamos do passo de tempo anterior. 
        # Como o método explícito tem passos muito pequenos, theta pode ser ruidoso.
        # Estimativa simples via Black-Scholes equation: Theta = rV - rS*Delta - 0.5*sigma^2*S^2*Gamma
        # (Usando a relação da PDE para obter theta sem precisar rodar outra simulação)
        theta_year = (self.r * V_curr) - (self.r * S_curr * delta) - (0.5 * (self.sigma**2) * (S_curr**2) * gamma)
        theta_day = theta_year / 365.0

        return {
            'delta': round(delta, 4),
            'gamma': round(gamma, 4),
            'theta': round(theta_day, 4),
            'vega': "Requer Simulação Extra"
        }

    def get_plot_data(self):
        # 1. Gráfico de Preço (V vs S)
        plt.figure(figsize=(7, 4.5))
        
        # Focamos o gráfico ao redor de S0 (ex: 50% a 150%) para visualização útil
        mask = (self.S_grid_real >= self.S0 * 0.5) & (self.S_grid_real <= self.S0 * 1.5)
        
        plt.plot(self.S_grid_real[mask], self.V_final_curve[mask], label='Curva FDM (t=0)', color='blue')
        plt.axvline(x=self.S0, color='red', linestyle='--', label=f'Spot: {self.S0}')
        plt.axvline(x=self.K, color='green', linestyle=':', label=f'Strike: {self.K}')
        
        plt.title(f'Preço da Opção {self.option_type.title()} (FDM Explícito)')
        plt.xlabel('Preço do Ativo (S)')
        plt.ylabel('Valor da Opção')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        buf = BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        price_plot = base64.b64encode(buf.getvalue()).decode('utf-8')

        # 2. Gráfico da Solução na Variável Transformada (u vs x)
        # Igual ao que você gerou no seu código local, para fins didáticos
        plt.figure(figsize=(7, 4.5))
        plt.plot(self.x_values, self.u_final, color='purple', label='u(x, tau_max)')
        x_target = np.log(self.S0 / self.K)
        plt.axvline(x=x_target, color='red', linestyle='--', label='x_target (S0)')
        plt.title('Solução da Eq. de Difusão (Espaço Logarítmico)')
        plt.xlabel('x = ln(S/K)')
        plt.ylabel('u(x)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        buf2 = BytesIO()
        plt.savefig(buf2, format='png')
        plt.close()
        diffusion_plot = base64.b64encode(buf2.getvalue()).decode('utf-8')

        return price_plot, diffusion_plot