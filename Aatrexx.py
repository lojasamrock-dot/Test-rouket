import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
import json
import os
import uuid
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from scipy.stats import norm, binom, chi2
from scipy.signal import find_peaks
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import warnings
warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="🎯 DS Elite 2.0 - Dia de Sorte",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.block-container { padding-top: 1rem; padding-bottom: 2rem; }
h1,h2,h3 { text-align: center; }
.card { background: #0e1117; border-radius: 14px; padding: 16px; margin-bottom: 12px; border: 1px solid #262730; color: white; }
.stButton>button { width: 100%; height: 3.2em; border-radius: 14px; font-size: 1.05em; }
input, textarea { border-radius: 12px !important; }
.concurso-info { background: #1e1e2e; padding: 10px; border-radius: 10px; margin: 10px 0; }
.metric-card { background: #16213e; padding: 10px; border-radius: 10px; text-align: center; }
.highlight { background: #00ffaa20; border-left: 4px solid #00ffaa; padding: 10px; border-radius: 8px; margin: 10px 0; }
.ds-highlight { background: linear-gradient(135deg, #ff6b6b30 0%, #feca5730 50%, #4ecdc430 100%); border: 2px solid #feca57; padding: 15px; border-radius: 12px; margin: 10px 0; }
.elite-ds-highlight { background: linear-gradient(135deg, #9b59b630 0%, #feca5730 50%, #4ecdc430 100%); border: 2px solid #9b59b6; padding: 15px; border-radius: 12px; margin: 10px 0; }
.download-section { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 20px; border-radius: 15px; margin: 20px 0; border: 2px solid #feca57; text-align: center; }
.ranking-card { background: #0e1117; border: 1px solid #262730; border-radius: 10px; padding: 10px; margin: 5px 0; }
.pos-1 { color: #ffd700; font-weight: bold; }
.pos-2 { color: #c0c0c0; font-weight: bold; }
.pos-3 { color: #cd7f32; font-weight: bold; }
.tendencia-up { color: #4ade80; }
.tendencia-down { color: #ff6b6b; }
.tendencia-stable { color: #feca57; }
</style>
""", unsafe_allow_html=True)

st.title("🎯 DS Elite 2.0 - Dia de Sorte")
st.caption("Sistema Avançado de Análise Estatística e Geração Inteligente")

# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================

def convert_numpy_types(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_numpy_types(item) for item in obj)
    elif isinstance(obj, Counter):
        return dict(obj)
    else:
        return obj

def salvar_jogos_elite(jogos, parametros, estatisticas=None):
    try:
        if not os.path.exists("jogos_salvos_elite"):
            os.makedirs("jogos_salvos_elite")
        jogo_id = str(uuid.uuid4())[:8]
        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"jogos_salvos_elite/jogos_{data_hora}_{jogo_id}.json"
        jogos_convertidos = convert_numpy_types(jogos)
        dados = {
            "id": jogo_id,
            "data_geracao": datetime.now().isoformat(),
            "jogos": jogos_convertidos,
            "parametros": convert_numpy_types(parametros),
            "estatisticas": convert_numpy_types(estatisticas) if estatisticas else {},
            "schema_version": "2.0"
        }
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        return nome_arquivo, jogo_id
    except Exception as e:
        st.error(f"Erro ao salvar jogos: {e}")
        return None, None

def carregar_jogos_elite():
    jogos_salvos = []
    try:
        if os.path.exists("jogos_salvos_elite"):
            for arquivo in os.listdir("jogos_salvos_elite"):
                if arquivo.endswith(".json"):
                    try:
                        with open(f"jogos_salvos_elite/{arquivo}", 'r', encoding='utf-8') as f:
                            dados = json.load(f)
                            dados["arquivo"] = arquivo
                            jogos_salvos.append(dados)
                    except Exception:
                        continue
            jogos_salvos.sort(key=lambda x: x.get("data_geracao", ""), reverse=True)
    except Exception as e:
        st.error(f"Erro ao carregar jogos: {e}")
    return jogos_salvos

def formatar_jogo_html_ds(jogo, destaque_primos=True):
    primos = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31]
    if isinstance(jogo, str):
        dezenas = [int(d.strip()) for d in jogo.split(",")]
    else:
        dezenas = jogo
    if not dezenas:
        return "Jogo inválido"
    html = ""
    for num in dezenas:
        if num in primos and destaque_primos:
            html += f"<span style='background:#4cc9f020; border:1px solid #4cc9f0; border-radius:20px; padding:5px 8px; margin:2px; display:inline-block; font-weight:bold;'>{num:02d}</span>"
        else:
            html += f"<span style='background:#0e1117; border:1px solid #262730; border-radius:20px; padding:5px 8px; margin:2px; display:inline-block;'>{num:02d}</span>"
    return html

def contar_pares_ds(jogo):
    return sum(1 for d in jogo if d % 2 == 0)

def contar_primos_ds(jogo):
    primos = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}
    return sum(1 for d in jogo if d in primos)

def contar_consecutivos_ds(jogo):
    jogo = sorted(jogo)
    return sum(1 for i in range(len(jogo)-1) if jogo[i+1] == jogo[i] + 1)

# =====================================================
# FUNÇÃO PARA BUSCAR DADOS DO DIA DE SORTE
# =====================================================

def buscar_historico_dia_de_sorte(quantidade=200):
    try:
        url_lista = "https://loteriascaixa-api.herokuapp.com/api/diadesorte"
        response = requests.get(url_lista, timeout=10)
        
        if response.status_code == 200:
            dados = response.json()
            if isinstance(dados, list):
                return dados[:quantidade]
            elif isinstance(dados, dict):
                return [dados]
        return None
    except Exception as e:
        st.error(f"❌ Erro na requisição: {e}")
        return None

# =====================================================
# CLASSE DS ELITE 2.0 - MOTOR PRINCIPAL
# =====================================================

class DSElite20:
    """
    DS Elite 2.0 - Sistema Avançado para Dia de Sorte
    Arquitetura baseada em análise estatística e aprendizado de máquina
    """
    
    def __init__(self, dados_api, qtd_concursos=200):
        self.dados_api = dados_api
        self.qtd_concursos = min(qtd_concursos, len(dados_api))
        
        # Meses do ano
        self.meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                      'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        
        # Processa concursos
        self.concursos = []
        self.meses_historicos = []
        self.dados_completos = []
        
        for concurso in dados_api[:self.qtd_concursos]:
            if 'dezenas' in concurso:
                dezenas = sorted(map(int, concurso['dezenas']))
                self.concursos.append(dezenas)
                
                mes = concurso.get('mesDaSorte', 'Junho')
                self.meses_historicos.append(mes)
                
                self.dados_completos.append({
                    'concurso': concurso.get('concurso', concurso.get('numeroDoConcurso', 0)),
                    'data': concurso.get('data', concurso.get('dataApuracao', '')),
                    'dezenas': dezenas,
                    'mes': mes
                })
        
        self.ultimo_concurso = self.concursos[0] if self.concursos else []
        self.ultimo_mes = self.meses_historicos[0] if self.meses_historicos else 'Junho'
        
        # Inicializa motores
        self.motor_estatistico = MotorEstatistico(self.concursos)
        self.sistema_pontuacao = SistemaPontuacao(self.motor_estatistico)
        self.gerador_inteligente = GeradorInteligente(self.motor_estatistico, self.sistema_pontuacao)
        self.simulador = Simulador(self.concursos, self.motor_estatistico)
        
        # Análises extras
        self.analise_cluster = self._analisar_clusters()
        self.analise_tendencia = self._analisar_tendencias()
        
    def _analisar_clusters(self):
        """Análise de clusters das dezenas"""
        try:
            # Prepara dados
            features = []
            for num in range(1, 32):
                freq = self.motor_estatistico.frequencias.get(num, 0)
                atraso = self.motor_estatistico.atrasos.get(num, 0)
                freq_recente = self.motor_estatistico.frequencia_recente.get(num, 0)
                features.append([freq, atraso, freq_recente])
            
            # Normaliza
            scaler = StandardScaler()
            features_scaled = scaler.fit_transform(features)
            
            # K-Means
            kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
            clusters = kmeans.fit_predict(features_scaled)
            
            # PCA para visualização
            pca = PCA(n_components=2)
            features_2d = pca.fit_transform(features_scaled)
            
            return {
                'clusters': clusters,
                'features_2d': features_2d,
                'centroids': kmeans.cluster_centers_
            }
        except:
            return None
    
    def _analisar_tendencias(self):
        """Análise de tendência das dezenas"""
        tendencias = {}
        for num in range(1, 32):
            freq = self.motor_estatistico.frequencias.get(num, 0)
            freq_recente = self.motor_estatistico.frequencia_recente.get(num, 0)
            atraso = self.motor_estatistico.atrasos.get(num, 0)
            
            # Classifica tendência
            if freq_recente > freq * 1.2:
                tendencia = 'subindo'
            elif freq_recente < freq * 0.8:
                tendencia = 'caindo'
            else:
                tendencia = 'estavel'
            
            tendencias[num] = {
                'tendencia': tendencia,
                'diferenca': freq_recente - freq,
                'score_tendencia': (freq_recente / max(freq, 1)) * (1 + (1 / (atraso + 1)))
            }
        
        return tendencias

# =====================================================
# MOTOR ESTATÍSTICO
# =====================================================

class MotorEstatistico:
    """
    Motor Estatístico - Análise completa das dezenas
    """
    
    def __init__(self, concursos):
        self.concursos = concursos
        self.total_concursos = len(concursos)
        
        # Frequências
        self.frequencias = self._calcular_frequencias()
        self.frequencia_recente = self._calcular_frequencia_recente()
        self.frequencia_historica = self._calcular_frequencia_historica()
        
        # Atrasos
        self.atrasos = self._calcular_atrasos()
        self.media_atrasos = self._calcular_media_atrasos()
        
        # Análises
        self.probabilidades = self._calcular_probabilidades()
        self.tendencias = self._calcular_tendencias()
        
    def _calcular_frequencias(self):
        freq = Counter()
        for concurso in self.concursos:
            freq.update(concurso)
        return freq
    
    def _calcular_frequencia_recente(self, ultimos=20):
        freq = Counter()
        for concurso in self.concursos[:ultimos]:
            freq.update(concurso)
        return freq
    
    def _calcular_frequencia_historica(self, periodos=[10, 20, 50, 100]):
        historico = {}
        for periodo in periodos:
            freq = Counter()
            for concurso in self.concursos[:periodo]:
                freq.update(concurso)
            historico[periodo] = freq
        return historico
    
    def _calcular_atrasos(self):
        atrasos = {i: 0 for i in range(1, 32)}
        if not self.concursos:
            return atrasos
        for dezena in range(1, 32):
            atraso = 0
            for concurso in self.concursos:
                if dezena in concurso:
                    break
                atraso += 1
            atrasos[dezena] = atraso
        return atrasos
    
    def _calcular_media_atrasos(self):
        medias = {}
        for num in range(1, 32):
            atrasos = []
            atraso_atual = 0
            for concurso in self.concursos:
                if num in concurso:
                    atrasos.append(atraso_atual)
                    atraso_atual = 0
                else:
                    atraso_atual += 1
            medias[num] = np.mean(atrasos) if atrasos else 0
        return medias
    
    def _calcular_probabilidades(self):
        """Calcula probabilidades baseadas em frequência"""
        total = sum(self.frequencias.values())
        if total == 0:
            return {i: 1/31 for i in range(1, 32)}
        return {num: freq/total for num, freq in self.frequencias.items()}
    
    def _calcular_tendencias(self):
        """Calcula tendências usando regressão simples"""
        tendencias = {}
        for num in range(1, 32):
            # Pega frequência em janelas
            janelas = [10, 20, 50, 100]
            freq_janelas = []
            for janela in janelas:
                freq = Counter()
                for concurso in self.concursos[:janela]:
                    if num in concurso:
                        freq[num] += 1
                freq_janelas.append(freq.get(num, 0) / janela)
            
            # Calcula inclinação
            if len(freq_janelas) >= 2:
                x = np.array(range(len(freq_janelas)))
                y = np.array(freq_janelas)
                slope = np.polyfit(x, y, 1)[0] if len(x) > 1 else 0
                tendencias[num] = slope
            else:
                tendencias[num] = 0
        
        return tendencias
    
    def get_estatisticas_dezena(self, numero):
        """Retorna todas as estatísticas de uma dezena"""
        return {
            'numero': numero,
            'frequencia': self.frequencias.get(numero, 0),
            'frequencia_recente': self.frequencia_recente.get(numero, 0),
            'atraso': self.atrasos.get(numero, 0),
            'media_atraso': self.media_atrasos.get(numero, 0),
            'probabilidade': self.probabilidades.get(numero, 0),
            'tendencia': self.tendencias.get(numero, 0),
            'frequencias_historicas': {p: self.frequencia_historica[p].get(numero, 0) for p in [10, 20, 50, 100]}
        }

# =====================================================
# SISTEMA DE PONTUAÇÃO
# =====================================================

class SistemaPontuacao:
    """
    Sistema de Pontuação - Rankeamento inteligente das dezenas
    """
    
    def __init__(self, motor_estatistico):
        self.motor = motor_estatistico
        self.pesos = self._definir_pesos()
        self.pontuacoes = self._calcular_pontuacoes()
        
    def _definir_pesos(self):
        """Define pesos para cada fator de pontuação"""
        return {
            'frequencia_recente': 0.30,
            'frequencia_historica': 0.20,
            'atraso': 0.20,
            'tendencia': 0.15,
            'equilibrio': 0.15
        }
    
    def _calcular_pontuacoes(self):
        """Calcula pontuação para todas as dezenas"""
        pontuacoes = {}
        
        # Normaliza métricas
        max_freq = max(self.motor.frequencias.values()) if self.motor.frequencias else 1
        max_freq_recente = max(self.motor.frequencia_recente.values()) if self.motor.frequencia_recente else 1
        max_atraso = max(self.motor.atrasos.values()) if self.motor.atrasos else 1
        
        for num in range(1, 32):
            # Frequência recente (normalizada)
            freq_recente = self.motor.frequencia_recente.get(num, 0) / max_freq_recente
            
            # Frequência histórica (normalizada)
            freq_historica = self.motor.frequencias.get(num, 0) / max_freq
            
            # Atraso (invertido, quanto maior atraso, maior pontuação)
            atraso = 1 - (self.motor.atrasos.get(num, 0) / max_atraso)
            
            # Tendência (normalizada)
            tendencia = self.motor.tendencias.get(num, 0)
            tendencia_norm = (tendencia + 1) / 2  # Normaliza para 0-1
            
            # Equilíbrio (baseado na distribuição)
            equilibrio = self._calcular_equilibrio(num)
            
            # Pontuação final
            pontuacao = (
                freq_recente * self.pesos['frequencia_recente'] +
                freq_historica * self.pesos['frequencia_historica'] +
                atraso * self.pesos['atraso'] +
                tendencia_norm * self.pesos['tendencia'] +
                equilibrio * self.pesos['equilibrio']
            )
            
            pontuacoes[num] = round(pontuacao * 100, 2)
        
        return pontuacoes
    
    def _calcular_equilibrio(self, numero):
        """Calcula fator de equilíbrio baseado na posição da dezena"""
        # Distribuição ideal: equilíbrio entre faixas
        faixa = 1 if numero <= 10 else 2 if numero <= 21 else 3
        
        # Verifica frequência por faixa
        freq_faixas = {1: 0, 2: 0, 3: 0}
        for n in range(1, 32):
            f = 1 if n <= 10 else 2 if n <= 21 else 3
            freq_faixas[f] += self.motor.frequencias.get(n, 0)
        
        total = sum(freq_faixas.values())
        if total == 0:
            return 0.5
        
        # Score de equilíbrio: quanto mais balanceado, maior
        freq_faixa = freq_faixas[faixa]
        proporcao = freq_faixa / total
        ideal = 1/3
        
        # Quanto mais próximo do ideal, maior o score
        equilibrio = 1 - abs(proporcao - ideal) * 2
        return max(0, min(1, equilibrio))
    
    def get_ranking(self, top_n=31):
        """Retorna ranking das dezenas"""
        ranking = sorted(self.pontuacoes.items(), key=lambda x: x[1], reverse=True)
        return ranking[:top_n]

# =====================================================
# GERADOR INTELIGENTE
# =====================================================

class GeradorInteligente:
    """
    Gerador Inteligente - Geração de jogos com filtros
    """
    
    def __init__(self, motor_estatistico, sistema_pontuacao):
        self.motor = motor_estatistico
        self.sistema = sistema_pontuacao
        
    def gerar_jogo(self, filtros=None):
        """Gera um jogo com base nos filtros"""
        if filtros is None:
            filtros = {
                'pares_min': 3,
                'pares_max': 4,
                'soma_min': 70,
                'soma_max': 130,
                'faixa_min': 1,
                'faixa_max': 4,
                'consecutivos_max': 3,
                'repetidas_max': 3
            }
        
        # Pega ranking das dezenas
        ranking = self.sistema.get_ranking(20)
        dezenas_prioritarias = [n for n, _ in ranking]
        
        # Tenta gerar jogo com filtros
        tentativas = 0
        while tentativas < 10000:
            tentativas += 1
            
            # Seleciona baseado em probabilidade ponderada
            jogo = set()
            
            # Pega 4-5 dezenas prioritárias
            qtd_prioritarias = random.randint(4, 5)
            prioridades = random.sample(dezenas_prioritarias, min(qtd_prioritarias, len(dezenas_prioritarias)))
            jogo.update(prioridades)
            
            # Completa com números aleatórios
            while len(jogo) < 7:
                novo = random.randint(1, 31)
                if novo not in jogo:
                    jogo.add(novo)
            
            jogo = sorted(jogo)
            
            # Aplica filtros
            if self._aplicar_filtros(jogo, filtros):
                return jogo
        
        return sorted(random.sample(range(1, 32), 7))
    
    def _aplicar_filtros(self, jogo, filtros):
        """Aplica todos os filtros ao jogo"""
        # Paridade
        pares = contar_pares_ds(jogo)
        if not (filtros.get('pares_min', 3) <= pares <= filtros.get('pares_max', 4)):
            return False
        
        # Soma
        soma = sum(jogo)
        if not (filtros.get('soma_min', 70) <= soma <= filtros.get('soma_max', 130)):
            return False
        
        # Distribuição por faixas
        faixas = [0, 0, 0]
        for n in jogo:
            if 1 <= n <= 10:
                faixas[0] += 1
            elif 11 <= n <= 21:
                faixas[1] += 1
            else:
                faixas[2] += 1
        
        for f in faixas:
            if not (filtros.get('faixa_min', 1) <= f <= filtros.get('faixa_max', 4)):
                return False
        
        # Consecutivos
        if contar_consecutivos_ds(jogo) > filtros.get('consecutivos_max', 3):
            return False
        
        # Repetidas do último concurso (se disponível)
        if self.motor.concursos:
            ultimo = self.motor.concursos[0]
            repetidas = len(set(jogo) & set(ultimo))
            if repetidas > filtros.get('repetidas_max', 3):
                return False
        
        return True
    
    def gerar_multiplos_jogos(self, qtd=10, filtros=None):
        """Gera múltiplos jogos"""
        jogos = []
        tentativas = 0
        max_tentativas = qtd * 1000
        
        while len(jogos) < qtd and tentativas < max_tentativas:
            tentativas += 1
            jogo = self.gerar_jogo(filtros)
            if jogo and jogo not in jogos:
                jogos.append(jogo)
        
        return jogos

# =====================================================
# SIMULADOR
# =====================================================

class Simulador:
    """
    Simulador - Backtesting de estratégias
    """
    
    def __init__(self, concursos, motor_estatistico):
        self.concursos = concursos
        self.motor = motor_estatistico
        
    def simular_estrategia(self, estrategia, num_simulacoes=1000):
        """Simula uma estratégia no histórico"""
        resultados = []
        
        for _ in range(num_simulacoes):
            # Seleciona um concurso aleatório para teste
            idx = random.randint(10, len(self.concursos) - 1)
            concurso_teste = self.concursos[idx]
            
            # Gera jogos baseados na estratégia (simplificado)
            jogo = self._gerar_jogo_estrategia(estrategia)
            
            # Calcula acertos
            acertos = len(set(jogo) & set(concurso_teste))
            resultados.append(acertos)
        
        return {
            'media': np.mean(resultados),
            'mediana': np.median(resultados),
            'std': np.std(resultados),
            'max': max(resultados),
            'min': min(resultados),
            'distribuicao': Counter(resultados)
        }
    
    def _gerar_jogo_estrategia(self, estrategia):
        """Gera um jogo baseado na estratégia (simplificado)"""
        # Estratégia: usar números mais frequentes
        if estrategia == 'frequencia':
            top = sorted(self.motor.frequencias.items(), key=lambda x: x[1], reverse=True)[:15]
            numeros = [n for n, _ in top]
            return sorted(random.sample(numeros, 7))
        
        # Estratégia: usar números atrasados
        elif estrategia == 'atraso':
            top = sorted(self.motor.atrasos.items(), key=lambda x: x[1], reverse=True)[:15]
            numeros = [n for n, _ in top]
            return sorted(random.sample(numeros, 7))
        
        # Estratégia: aleatória
        else:
            return sorted(random.sample(range(1, 32), 7))
    
    def comparar_estrategias(self, estrategias=['frequencia', 'atraso', 'aleatoria']):
        """Compara diferentes estratégias"""
        resultados = {}
        for estrategia in estrategias:
            resultados[estrategia] = self.simular_estrategia(estrategia, 500)
        return resultados

# =====================================================
# INTERFACE PRINCIPAL
# =====================================================

def main():
    # Inicializa session state
    if "dados_api" not in st.session_state:
        st.session_state.dados_api = None
    if "ds_elite" not in st.session_state:
        st.session_state.ds_elite = None
    if "jogos_gerados" not in st.session_state:
        st.session_state.jogos_gerados = []
    if "jogos_salvos" not in st.session_state:
        st.session_state.jogos_salvos = []
    if "ranking_atual" not in st.session_state:
        st.session_state.ranking_atual = None

    # Barra Lateral
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        qtd_concursos = st.slider("Qtd concursos históricos", 50, 500, 200)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Carregar Dados", use_container_width=True):
                with st.spinner("Carregando dados do Dia de Sorte..."):
                    dados = buscar_historico_dia_de_sorte(qtd_concursos)
                    if dados and len(dados) > 0:
                        st.session_state.dados_api = dados
                        st.session_state.ds_elite = DSElite20(dados, qtd_concursos)
                        st.session_state.ranking_atual = st.session_state.ds_elite.sistema_pontuacao.get_ranking()
                        st.success(f"✅ {len(dados)} concursos carregados!")
        
        with col2:
            if st.button("🔄 Atualizar", use_container_width=True):
                st.rerun()
        
        st.markdown("---")
        
        # Informações do último concurso
        if st.session_state.dados_api:
            ultimo = st.session_state.dados_api[0]
            st.markdown("### 📅 Último Concurso")
            st.markdown(f"**#{ultimo.get('concurso', ultimo.get('numeroDoConcurso', 'N/A'))}**")
            st.markdown(f"📆 {ultimo.get('data', ultimo.get('dataApuracao', 'N/A'))}")
            st.markdown(f"🌙 {ultimo.get('mesDaSorte', 'N/A')}")
            if 'dezenas' in ultimo:
                dezenas = sorted(map(int, ultimo['dezenas']))
                st.markdown(f"🎯 {', '.join(f'{d:02d}' for d in dezenas)}")
        
        st.markdown("---")
        st.caption("DS Elite 2.0 v1.0")

    # Conteúdo Principal
    if not st.session_state.dados_api:
        st.info("👈 Carregue os dados do Dia de Sorte na barra lateral para começar.")
        return

    st.subheader("🎯 DS Elite 2.0 - Sistema Avançado")

    # Tabs
    tabs = st.tabs([
        "📊 Dashboard",
        "🏆 Ranking",
        "🎲 Gerador",
        "🔬 Simulador",
        "📈 Análise",
        "💾 Salvos"
    ])

    # ================= TAB 1: DASHBOARD =================
    with tabs[0]:
        st.markdown("### 📊 Dashboard - Visão Geral")
        
        if st.session_state.ds_elite:
            elite = st.session_state.ds_elite
            motor = elite.motor_estatistico
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Concursos", motor.total_concursos)
            with col2:
                st.metric("Mês + Frequente", elite.ultimo_mes)
            with col3:
                media_repetidas = sum(1 for i in range(len(motor.concursos)-1) 
                                     if len(set(motor.concursos[i]) & set(motor.concursos[i+1])) > 0) / max(len(motor.concursos)-1, 1)
                st.metric("Média Repetidas", f"{media_repetidas:.2f}")
            with col4:
                dezena_mais_freq = max(motor.frequencias.items(), key=lambda x: x[1])[0]
                st.metric("Dezena + Frequente", f"{dezena_mais_freq:02d}")
            
            # Gráficos
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 📊 Frequência das Dezenas")
                df_freq = pd.DataFrame({
                    'Dezena': range(1, 32),
                    'Frequência': [motor.frequencias.get(i, 0) for i in range(1, 32)]
                })
                st.bar_chart(df_freq.set_index('Dezena'))
            
            with col2:
                st.markdown("### ⏰ Atraso das Dezenas")
                df_atraso = pd.DataFrame({
                    'Dezena': range(1, 32),
                    'Atraso': [motor.atrasos.get(i, 0) for i in range(1, 32)]
                })
                st.bar_chart(df_atraso.set_index('Dezena'))
            
            # Distribuição dos Meses
            st.markdown("### 🌙 Distribuição dos Meses da Sorte")
            meses_count = Counter(elite.meses_historicos)
            df_meses = pd.DataFrame(list(meses_count.items()), columns=['Mês', 'Frequência'])
            st.bar_chart(df_meses.set_index('Mês'))

    # ================= TAB 2: RANKING =================
    with tabs[1]:
        st.markdown("### 🏆 Ranking das Dezenas")
        
        if st.session_state.ds_elite:
            elite = st.session_state.ds_elite
            
            # Filtros para o ranking
            col1, col2, col3 = st.columns(3)
            with col1:
                top_n = st.slider("Top N dezenas", 5, 31, 15)
            with col2:
                ordenar_por = st.selectbox("Ordenar por", ['Pontuação', 'Frequência', 'Atraso'])
            with col3:
                mostrar_detalhes = st.checkbox("Mostrar detalhes", True)
            
            ranking = elite.sistema_pontuacao.get_ranking(top_n)
            
            # Cria DataFrame do ranking
            dados_ranking = []
            for pos, (num, score) in enumerate(ranking, 1):
                stats = elite.motor_estatistico.get_estatisticas_dezena(num)
                
                # Classificação
                if pos <= 3:
                    classe = f"pos-{pos}"
                else:
                    classe = ""
                
                # Tendência
                tendencia = stats['tendencia']
                if tendencia > 0.01:
                    tendencia_str = "⬆️ subindo"
                    tendencia_cls = "tendencia-up"
                elif tendencia < -0.01:
                    tendencia_str = "⬇️ caindo"
                    tendencia_cls = "tendencia-down"
                else:
                    tendencia_str = "➡️ estável"
                    tendencia_cls = "tendencia-stable"
                
                dados_ranking.append({
                    'Posição': pos,
                    'Dezena': f"{num:02d}",
                    'Pontuação': score,
                    'Classe': classe,
                    'Frequência': stats['frequencia'],
                    'Freq. Recente': stats['frequencia_recente'],
                    'Atraso': stats['atraso'],
                    'Média Atraso': round(stats['media_atraso'], 1),
                    'Tendência': tendencia_str,
                    'Tendência Classe': tendencia_cls,
                    'Probabilidade': f"{stats['probabilidade']*100:.2f}%"
                })
            
            df_ranking = pd.DataFrame(dados_ranking)
            
            # Exibe ranking
            for _, row in df_ranking.iterrows():
                medalha = "🥇" if row['Posição'] == 1 else "🥈" if row['Posição'] == 2 else "🥉" if row['Posição'] == 3 else f"{row['Posição']}º"
                
                detalhes = ""
                if mostrar_detalhes:
                    detalhes = f"""
                    <small style='color:#aaa;'>
                        Freq: {row['Frequência']} | Freq Recente: {row['Freq. Recente']} | 
                        Atraso: {row['Atraso']} | Média: {row['Média Atraso']} | 
                        Tendência: <span class='{row['Tendência Classe']}'>{row['Tendência']}</span>
                    </small>
                    """
                
                st.markdown(f"""
                <div class='ranking-card'>
                    <div>
                        <span class='{row['Classe']}'>{medalha}</span>
                        <strong>Dezena {row['Dezena']}</strong>
                        <span style='float: right;'>
                            <strong>Score: {row['Pontuação']}</strong>
                            <span style='margin-left: 10px; color: #aaa;'>| {row['Probabilidade']}</span>
                        </span>
                    </div>
                    {detalhes}
                </div>
                """, unsafe_allow_html=True)

    # ================= TAB 3: GERADOR =================
    with tabs[2]:
        st.markdown("### 🎲 Gerador Inteligente")
        
        if st.session_state.ds_elite:
            elite = st.session_state.ds_elite
            
            with st.expander("⚙️ Configurar Filtros", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    pares_min = st.slider("Mínimo Pares", 1, 6, 3)
                    pares_max = st.slider("Máximo Pares", 1, 6, 4)
                with col2:
                    soma_min = st.slider("Soma Mínima", 50, 150, 70)
                    soma_max = st.slider("Soma Máxima", 50, 150, 130)
                with col3:
                    consec_max = st.slider("Máx. Consecutivos", 1, 6, 3)
                    repet_max = st.slider("Máx. Repetidas", 0, 5, 3)
                
                filtros = {
                    'pares_min': pares_min,
                    'pares_max': pares_max,
                    'soma_min': soma_min,
                    'soma_max': soma_max,
                    'faixa_min': 1,
                    'faixa_max': 4,
                    'consecutivos_max': consec_max,
                    'repetidas_max': repet_max
                }
            
            col1, col2 = st.columns(2)
            with col1:
                qtd_jogos = st.slider("Quantidade de jogos", 1, 50, 10)
            with col2:
                usar_ranking = st.checkbox("Usar ranking de dezenas", True)
            
            if st.button("🎯 GERAR JOGOS", use_container_width=True, type="primary"):
                with st.spinner(f"Gerando {qtd_jogos} jogos..."):
                    gerador = elite.gerador_inteligente
                    jogos = gerador.gerar_multiplos_jogos(qtd_jogos, filtros)
                    
                    if jogos:
                        st.session_state.jogos_gerados = jogos
                        st.success(f"✅ {len(jogos)} jogos gerados!")
            
            if st.session_state.jogos_gerados:
                jogos = st.session_state.jogos_gerados
                st.markdown(f"### 📋 Jogos Gerados ({len(jogos)})")
                
                for i, jogo in enumerate(jogos[:20]):
                    medalha = "🏆" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "📌"
                    
                    # Estatísticas do jogo
                    pares = contar_pares_ds(jogo)
                    primos = contar_primos_ds(jogo)
                    soma = sum(jogo)
                    consec = contar_consecutivos_ds(jogo)
                    
                    stats = f"⚖️ {pares}p/{7-pares}i | 🔢 {primos} primos | ➕ {soma} | 🔗 {consec} consec"
                    
                    st.markdown(f"""
                    <div class='card' style='border-left: 5px solid {"#ffd700" if i == 0 else "#4cc9f0"};'>
                        {medalha} <strong>Jogo {i+1:2d}</strong><br>
                        {formatar_jogo_html_ds(jogo)}<br>
                        <small style='color:#aaa;'>{stats}</small>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Botões de ação
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("💾 Salvar Jogos", key="salvar_elite", use_container_width=True):
                        arquivo, jogo_id = salvar_jogos_elite(jogos, filtros)
                        if arquivo:
                            st.success(f"✅ Jogos salvos! ID: {jogo_id}")
                with col2:
                    df_export = pd.DataFrame({
                        'Jogo': range(1, len(jogos)+1),
                        'Dezenas': [', '.join(f'{d:02d}' for d in j) for j in jogos],
                        'Pares': [contar_pares_ds(j) for j in jogos],
                        'Soma': [sum(j) for j in jogos]
                    })
                    st.download_button(
                        label="📥 Exportar CSV",
                        data=df_export.to_csv(index=False),
                        file_name=f"ds_elite_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

    # ================= TAB 4: SIMULADOR =================
    with tabs[3]:
        st.markdown("### 🔬 Simulador de Estratégias")
        
        if st.session_state.ds_elite:
            elite = st.session_state.ds_elite
            
            col1, col2 = st.columns(2)
            with col1:
                estrategias_selecionadas = st.multiselect(
                    "Selecione estratégias",
                    ['frequencia', 'atraso', 'aleatoria', 'ranking'],
                    default=['frequencia', 'atraso']
                )
            with col2:
                num_sim = st.slider("Número de simulações", 100, 5000, 1000)
            
            if st.button("🔬 EXECUTAR SIMULAÇÃO", use_container_width=True, type="primary"):
                with st.spinner(f"Executando {num_sim} simulações por estratégia..."):
                    simulador = elite.simulador
                    resultados = simulador.comparar_estrategias(estrategias_selecionadas)
                    
                    st.markdown("### 📊 Resultados da Simulação")
                    
                    # Tabela comparativa
                    dados_comparacao = []
                    for estrategia, res in resultados.items():
                        dados_comparacao.append({
                            'Estratégia': estrategia.capitalize(),
                            'Média': round(res['media'], 2),
                            'Mediana': round(res['mediana'], 2),
                            'Desvio': round(res['std'], 2),
                            'Máximo': res['max'],
                            'Mínimo': res['min']
                        })
                    
                    df_comp = pd.DataFrame(dados_comparacao)
                    st.dataframe(df_comp, use_container_width=True, hide_index=True)
                    
                    # Gráfico de distribuição
                    st.markdown("### 📈 Distribuição de Acertos")
                    for estrategia, res in resultados.items():
                        st.markdown(f"**{estrategia.capitalize()}**")
                        df_dist = pd.DataFrame(list(res['distribuicao'].items()), columns=['Acertos', 'Frequência'])
                        st.bar_chart(df_dist.set_index('Acertos'))

    # ================= TAB 5: ANÁLISE =================
    with tabs[4]:
        st.markdown("### 📈 Análise Avançada")
        
        if st.session_state.ds_elite:
            elite = st.session_state.ds_elite
            
            # Análise de Clusters
            st.markdown("### 🎯 Análise de Clusters (Machine Learning)")
            if elite.analise_cluster:
                clusters = elite.analise_cluster['clusters']
                
                # Distribuição dos clusters
                df_clusters = pd.DataFrame({
                    'Dezena': range(1, 32),
                    'Cluster': clusters
                })
                
                st.markdown("**Distribuição por Cluster:**")
                col1, col2, col3, col4 = st.columns(4)
                for i in range(4):
                    with [col1, col2, col3, col4][i]:
                        dezenas = df_clusters[df_clusters['Cluster'] == i]['Dezena'].tolist()
                        st.metric(f"Cluster {i+1}", len(dezenas))
                        st.markdown(f"Dezenas: {dezenas}")
            
            # Análise de Tendência
            st.markdown("### 📊 Análise de Tendência")
            tendencias = elite.analise_tendencia
            
            df_tend = pd.DataFrame([
                {'Dezena': num, 'Tendência': info['tendencia'], 'Score': info['score_tendencia']}
                for num, info in tendencias.items()
            ])
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Subindo**")
                subindo = df_tend[df_tend['Tendência'] == 'subindo'].sort_values('Score', ascending=False)
                st.dataframe(subindo[['Dezena', 'Score']], hide_index=True)
            with col2:
                st.markdown("**Caindo**")
                caindo = df_tend[df_tend['Tendência'] == 'caindo'].sort_values('Score', ascending=True)
                st.dataframe(caindo[['Dezena', 'Score']], hide_index=True)

    # ================= TAB 6: SALVOS =================
    with tabs[5]:
        st.markdown("### 💾 Jogos Salvos")
        
        jogos_salvos = carregar_jogos_elite()
        
        if not jogos_salvos:
            st.warning("Nenhum jogo salvo encontrado.")
        else:
            for jogo in jogos_salvos[:10]:
                st.markdown(f"""
                <div class='card'>
                    <strong>ID:</strong> {jogo['id']} | 
                    <strong>Data:</strong> {jogo['data_geracao'][:19]} |
                    <strong>Jogos:</strong> {len(jogo['jogos'])}
                </div>
                """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()

st.markdown("""
<style>
.footer-premium{width:100%;text-align:center;padding:22px 10px;margin-top:40px;background:linear-gradient(180deg,#0b0b0b,#050505);color:#ffffff;border-top:1px solid #222;position:relative;}
.footer-premium::before{content:"";position:absolute;top:0;left:0;width:100%;height:2px;background:linear-gradient(90deg,#9b59b6,#feca57,#4ecdc4,#9b59b6);box-shadow:0 0 10px #9b59b6;}
.footer-title{font-size:16px;font-weight:800;letter-spacing:3px;text-transform:uppercase;text-shadow:0 0 6px rgba(155,89,182,0.6);}
.footer-sub{font-size:11px;color:#bfbfbf;margin-top:4px;letter-spacing:1.5px;}
</style>
<div class="footer-premium"><div class="footer-title">DS ELITE 2.0 SYSTEM</div><div class="footer-sub">SAMUCJ TECNOLOGIA © 2026</div></div>
""", unsafe_allow_html=True)
