import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
import json
import os
import uuid
import math
import warnings
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta
from scipy.stats import norm, binom, chi2, pearsonr
from scipy.signal import find_peaks
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.calibration import CalibratedClassifierCV
try:
    # sklearn >= 1.6 removed CalibratedClassifierCV(cv='prefit') in favor of FrozenEstimator
    from sklearn.frozen import FrozenEstimator
    def _calibrar_modelo_prefit(modelo_base):
        return CalibratedClassifierCV(FrozenEstimator(modelo_base), method='sigmoid')
except ImportError:
    def _calibrar_modelo_prefit(modelo_base):
        return CalibratedClassifierCV(modelo_base, cv='prefit', method='sigmoid')
from sklearn.metrics import accuracy_score, classification_report
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="🎯 LOTOFÁCIL - DS Elite 3.0",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# CSS PERSONALIZADO
# =====================================================

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
.lotofacil-highlight { background: linear-gradient(135deg, #4cc9f030 0%, #feca5730 50%, #4ade8030 100%); border: 2px solid #4cc9f0; padding: 15px; border-radius: 12px; margin: 10px 0; }
.elite-lf-highlight { background: linear-gradient(135deg, #9b59b630 0%, #feca5730 50%, #4ade8030 100%); border: 2px solid #9b59b6; padding: 15px; border-radius: 12px; margin: 10px 0; }
.ia-lf-highlight { background: linear-gradient(135deg, #4cc9f030 0%, #4ade8030 50%, #9b59b630 100%); border: 2px solid #4cc9f0; padding: 15px; border-radius: 12px; margin: 10px 0; }
.download-section { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 20px; border-radius: 15px; margin: 20px 0; border: 2px solid #4cc9f0; text-align: center; }
.ranking-card { background: #0e1117; border: 1px solid #262730; border-radius: 10px; padding: 10px; margin: 5px 0; }
.pos-1 { color: #ffd700; font-weight: bold; }
.pos-2 { color: #c0c0c0; font-weight: bold; }
.pos-3 { color: #cd7f32; font-weight: bold; }
.tendencia-up { color: #4ade80; }
.tendencia-down { color: #ff6b6b; }
.tendencia-stable { color: #feca57; }
.footer-premium{width:100%;text-align:center;padding:22px 10px;margin-top:40px;background:linear-gradient(180deg,#0b0b0b,#050505);color:#ffffff;border-top:1px solid #222;position:relative;}
.footer-premium::before{content:"";position:absolute;top:0;left:0;width:100%;height:2px;background:linear-gradient(90deg,#4cc9f0,#feca57,#4ade80,#4cc9f0);box-shadow:0 0 10px #4cc9f0;}
.footer-title{font-size:16px;font-weight:800;letter-spacing:3px;text-transform:uppercase;text-shadow:0 0 6px rgba(76,201,240,0.6);}
.footer-sub{font-size:11px;color:#bfbfbf;margin-top:4px;letter-spacing:1.5px;}
</style>
""", unsafe_allow_html=True)

st.title("🎯 LOTOFÁCIL - DS Elite 3.0")
st.caption("Sistema Avançado de Análise Estatística, IA e Geração Inteligente")

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

def salvar_jogos_lf_elite(jogos, parametros, estatisticas=None):
    try:
        if not os.path.exists("jogos_salvos_lf_elite"):
            os.makedirs("jogos_salvos_lf_elite")
        jogo_id = str(uuid.uuid4())[:8]
        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"jogos_salvos_lf_elite/jogos_{data_hora}_{jogo_id}.json"
        jogos_convertidos = convert_numpy_types(jogos)
        dados = {
            "id": jogo_id,
            "data_geracao": datetime.now().isoformat(),
            "jogos": jogos_convertidos,
            "parametros": convert_numpy_types(parametros),
            "estatisticas": convert_numpy_types(estatisticas) if estatisticas else {},
            "schema_version": "3.0"
        }
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        return nome_arquivo, jogo_id
    except Exception as e:
        st.error(f"Erro ao salvar jogos: {e}")
        return None, None

def carregar_jogos_lf_elite():
    jogos_salvos = []
    try:
        if os.path.exists("jogos_salvos_lf_elite"):
            for arquivo in os.listdir("jogos_salvos_lf_elite"):
                if arquivo.endswith(".json"):
                    try:
                        with open(f"jogos_salvos_lf_elite/{arquivo}", 'r', encoding='utf-8') as f:
                            dados = json.load(f)
                            dados["arquivo"] = arquivo
                            jogos_salvos.append(dados)
                    except Exception:
                        continue
            jogos_salvos.sort(key=lambda x: x.get("data_geracao", ""), reverse=True)
    except Exception as e:
        st.error(f"Erro ao carregar jogos: {e}")
    return jogos_salvos

def formatar_jogo_html_lf(jogo, destaque_primos=True):
    primos = [2, 3, 5, 7, 11, 13, 17, 19, 23]
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

def contar_pares_lf(jogo):
    return sum(1 for d in jogo if d % 2 == 0)

def contar_primos_lf(jogo):
    primos = {2, 3, 5, 7, 11, 13, 17, 19, 23}
    return sum(1 for d in jogo if d in primos)

def contar_consecutivos_lf(jogo):
    jogo = sorted(jogo)
    return sum(1 for i in range(len(jogo)-1) if jogo[i+1] == jogo[i] + 1)

def distribuir_faixas_lf(jogo):
    faixas = [0, 0, 0]
    for n in jogo:
        if 1 <= n <= 8:
            faixas[0] += 1
        elif 9 <= n <= 16:
            faixas[1] += 1
        else:
            faixas[2] += 1
    return faixas

def distribuir_linhas_lf(jogo):
    linhas = [0] * 5
    for n in jogo:
        linhas[(n-1)//5] += 1
    return linhas

def distribuir_colunas_lf(jogo):
    colunas = [0] * 5
    for n in jogo:
        colunas[(n-1)%5] += 1
    return colunas

# =====================================================
# FUNÇÃO PARA BUSCAR DADOS DA LOTOFÁCIL
# =====================================================

def buscar_historico_lotofacil(quantidade=300):
    try:
        url_lista = "https://loteriascaixa-api.herokuapp.com/api/lotofacil"
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
# MÓDULO 1: BANCO DE DADOS INTELIGENTE - LOTOFÁCIL
# =====================================================

class BancoDadosLFInteligente:
    """Módulo 1 - Banco de Dados Inteligente para Lotofácil"""
    
    def __init__(self, dados_api):
        self.dados_api = dados_api
        self.concursos = []
        self._processar_dados()
        
    def _processar_dados(self):
        for concurso in self.dados_api:
            if 'dezenas' in concurso:
                dezenas = sorted(map(int, concurso['dezenas']))
                self.concursos.append({
                    'numero': concurso.get('concurso', concurso.get('numeroDoConcurso', 0)),
                    'data': concurso.get('data', concurso.get('dataApuracao', '')),
                    'dezenas': dezenas,
                    'pares': contar_pares_lf(dezenas),
                    'impares': 15 - contar_pares_lf(dezenas),
                    'primos': contar_primos_lf(dezenas),
                    'soma': sum(dezenas),
                    'consecutivos': contar_consecutivos_lf(dezenas),
                    'faixas': distribuir_faixas_lf(dezenas),
                    'linhas': distribuir_linhas_lf(dezenas),
                    'colunas': distribuir_colunas_lf(dezenas)
                })
        
        # Ordena por número do concurso
        self.concursos.sort(key=lambda x: x['numero'], reverse=True)
    
    def get_ultimo_concurso(self):
        return self.concursos[0] if self.concursos else None
    
    def get_historico_dezenas(self):
        return [c['dezenas'] for c in self.concursos]
    
    def get_estatisticas_concurso(self, concurso):
        if isinstance(concurso, dict):
            return concurso
        return None

# =====================================================
# MÓDULO 2: ESTATÍSTICAS AVANÇADAS - LOTOFÁCIL
# =====================================================

class EstatisticasLFAvancadas:
    """Módulo 2 - Estatísticas Avançadas para Lotofácil"""
    
    def __init__(self, banco_dados):
        self.banco = banco_dados
        self.dezenas = range(1, 26)
        self._calcular_estatisticas()
        
    def _calcular_estatisticas(self):
        historico = self.banco.get_historico_dezenas()
        self.total_concursos = len(historico)
        
        # Frequências
        self.frequencias = self._calcular_frequencias(historico)
        self.frequencias_periodos = self._calcular_frequencias_periodos(historico)
        
        # Atrasos
        self.atrasos = self._calcular_atrasos(historico)
        self.atraso_relativo = self._calcular_atraso_relativo()
        
        # Tendências
        self.tendencias = self._calcular_tendencias(historico)
        
        # Distribuições
        self.distribuicao_faixas = self._calcular_distribuicao_faixas(historico)
        self.distribuicao_linhas = self._calcular_distribuicao_linhas(historico)
        self.distribuicao_colunas = self._calcular_distribuicao_colunas(historico)
        self.distribuicao_paridade = self._calcular_distribuicao_paridade(historico)
        self.distribuicao_soma = self._calcular_distribuicao_soma(historico)
        self.distribuicao_repetidas = self._calcular_distribuicao_repetidas(historico)
        
        # Estatísticas adicionais
        self.media_soma = np.mean([c['soma'] for c in self.banco.concursos])
        self.std_soma = np.std([c['soma'] for c in self.banco.concursos])
        self.media_pares = np.mean([c['pares'] for c in self.banco.concursos])
        self.media_linhas = np.mean([len([l for l in c['linhas'] if l > 0]) for c in self.banco.concursos])
        
    def _calcular_frequencias(self, historico):
        freq = Counter()
        for concurso in historico:
            freq.update(concurso)
        return freq
    
    def _calcular_frequencias_periodos(self, historico):
        periodos = [10, 20, 50, 100, 300]
        resultado = {}
        for p in periodos:
            if len(historico) >= p:
                freq = Counter()
                for concurso in historico[:p]:
                    freq.update(concurso)
                resultado[p] = freq
            else:
                resultado[p] = self.frequencias
        return resultado
    
    def _calcular_atrasos(self, historico):
        atrasos = {i: 0 for i in range(1, 26)}
        if not historico:
            return atrasos
        for dezena in range(1, 26):
            atraso = 0
            for concurso in historico:
                if dezena in concurso:
                    break
                atraso += 1
            atrasos[dezena] = atraso
        return atrasos
    
    def _calcular_atraso_relativo(self):
        max_atraso = max(self.atrasos.values()) if self.atrasos else 1
        return {num: atraso / max_atraso for num, atraso in self.atrasos.items()}
    
    def _calcular_tendencias(self, historico):
        tendencias = {}
        for num in range(1, 26):
            janelas = [10, 20, 50, 100]
            freq_janelas = []
            for janela in janelas:
                freq = Counter()
                for concurso in historico[:janela]:
                    if num in concurso:
                        freq[num] += 1
                freq_janelas.append(freq.get(num, 0) / janela)
            
            if len(freq_janelas) >= 2:
                x = np.array(range(len(freq_janelas)))
                y = np.array(freq_janelas)
                slope = np.polyfit(x, y, 1)[0] if len(x) > 1 else 0
                
                if slope > 0.005:
                    tendencia = 'subindo'
                elif slope < -0.005:
                    tendencia = 'caindo'
                else:
                    tendencia = 'estavel'
                
                tendencias[num] = {
                    'inclinacao': slope,
                    'tendencia': tendencia,
                    'freq_janelas': freq_janelas
                }
            else:
                tendencias[num] = {
                    'inclinacao': 0,
                    'tendencia': 'estavel',
                    'freq_janelas': [0] * 4
                }
        return tendencias
    
    def _calcular_distribuicao_faixas(self, historico):
        faixas = [0, 0, 0]
        for concurso in historico:
            for num in concurso:
                if 1 <= num <= 8:
                    faixas[0] += 1
                elif 9 <= num <= 16:
                    faixas[1] += 1
                else:
                    faixas[2] += 1
        total = sum(faixas) if sum(faixas) > 0 else 1
        return [f/total for f in faixas]
    
    def _calcular_distribuicao_linhas(self, historico):
        linhas = [0] * 5
        for concurso in historico:
            for num in concurso:
                linha = (num - 1) // 5
                if linha < 5:
                    linhas[linha] += 1
        total = sum(linhas) if sum(linhas) > 0 else 1
        return [l/total for l in linhas]
    
    def _calcular_distribuicao_colunas(self, historico):
        colunas = [0] * 5
        for concurso in historico:
            for num in concurso:
                coluna = (num - 1) % 5
                if coluna < 5:
                    colunas[coluna] += 1
        total = sum(colunas) if sum(colunas) > 0 else 1
        return [c/total for c in colunas]
    
    def _calcular_distribuicao_paridade(self, historico):
        pares_total = 0
        impares_total = 0
        for concurso in historico:
            pares = contar_pares_lf(concurso)
            pares_total += pares
            impares_total += 15 - pares
        total = pares_total + impares_total
        if total == 0:
            return {'pares': 0.5, 'impares': 0.5}
        return {'pares': pares_total/total, 'impares': impares_total/total}
    
    def _calcular_distribuicao_soma(self, historico):
        somas = [sum(concurso) for concurso in historico]
        return {
            'media': np.mean(somas) if somas else 0,
            'std': np.std(somas) if somas else 0,
            'min': min(somas) if somas else 0,
            'max': max(somas) if somas else 0,
            'percentil_25': np.percentile(somas, 25) if somas else 0,
            'percentil_75': np.percentile(somas, 75) if somas else 0
        }
    
    def _calcular_distribuicao_repetidas(self, historico):
        repetidas = []
        for i in range(len(historico) - 1):
            rep = len(set(historico[i]) & set(historico[i+1]))
            repetidas.append(rep)
        if repetidas:
            return {
                'media': np.mean(repetidas),
                'std': np.std(repetidas),
                'max': max(repetidas),
                'min': min(repetidas),
                'distribuicao': Counter(repetidas)
            }
        return {'media': 0, 'std': 0, 'max': 0, 'min': 0, 'distribuicao': {}}
    
    def get_estatisticas_dezena(self, numero):
        """Retorna todas as estatísticas de uma dezena"""
        return {
            'numero': numero,
            'frequencia': self.frequencias.get(numero, 0),
            'frequencia_periodos': {p: self.frequencias_periodos[p].get(numero, 0) for p in self.frequencias_periodos},
            'atraso': self.atrasos.get(numero, 0),
            'atraso_relativo': self.atraso_relativo.get(numero, 0),
            'tendencia': self.tendencias.get(numero, {'tendencia': 'estavel', 'inclinacao': 0}),
            'probabilidade': self.frequencias.get(numero, 0) / (self.total_concursos * 15) if self.total_concursos > 0 else 0
        }

# =====================================================
# MÓDULO 3: MOTOR DE PONTUAÇÃO - LOTOFÁCIL
# =====================================================

class MotorPontuacaoLF:
    """Módulo 3 - Motor de Pontuação para Lotofácil"""
    
    def __init__(self, estatisticas):
        self.estatisticas = estatisticas
        self.pesos = self._definir_pesos()
        self.pontuacoes = self._calcular_pontuacoes()
        
    def _definir_pesos(self):
        return {
            'frequencia_recente': 0.25,
            'frequencia_historica': 0.20,
            'atraso': 0.20,
            'tendencia': 0.15,
            'equilibrio': 0.10,
            'diversidade': 0.10
        }
    
    def _calcular_pontuacoes(self):
        pontuacoes = {}
        
        # Normaliza métricas
        max_freq = max(self.estatisticas.frequencias.values()) if self.estatisticas.frequencias else 1
        max_freq_recente = max(self.estatisticas.frequencias_periodos[20].values()) if 20 in self.estatisticas.frequencias_periodos else 1
        max_atraso = max(self.estatisticas.atrasos.values()) if self.estatisticas.atrasos else 1
        
        for num in range(1, 26):
            # Frequência recente (20 últimos)
            freq_recente = self.estatisticas.frequencias_periodos.get(20, {}).get(num, 0) / max_freq_recente
            
            # Frequência histórica
            freq_historica = self.estatisticas.frequencias.get(num, 0) / max_freq
            
            # Atraso (invertido)
            atraso = 1 - (self.estatisticas.atrasos.get(num, 0) / max_atraso)
            
            # Tendência
            tendencia_info = self.estatisticas.tendencias.get(num, {})
            inclinacao = tendencia_info.get('inclinacao', 0)
            tendencia_norm = (inclinacao + 1) / 2
            
            # Equilíbrio
            equilibrio = self._calcular_equilibrio(num)
            
            # Diversidade
            diversidade = self._calcular_diversidade(num)
            
            # Pontuação final
            pontuacao = (
                freq_recente * self.pesos['frequencia_recente'] +
                freq_historica * self.pesos['frequencia_historica'] +
                atraso * self.pesos['atraso'] +
                tendencia_norm * self.pesos['tendencia'] +
                equilibrio * self.pesos['equilibrio'] +
                diversidade * self.pesos['diversidade']
            )
            
            pontuacoes[num] = round(pontuacao * 100, 2)
        
        return pontuacoes
    
    def _calcular_equilibrio(self, numero):
        """Calcula fator de equilíbrio baseado na posição da dezena"""
        # Verifica distribuição por faixa
        faixa = 0 if numero <= 8 else 1 if numero <= 16 else 2
        freq_faixas = self.estatisticas.distribuicao_faixas
        
        if faixa < len(freq_faixas):
            proporcao = freq_faixas[faixa]
            ideal = 1/3
            equilibrio = 1 - abs(proporcao - ideal) * 2
            return max(0, min(1, equilibrio))
        return 0.5
    
    def _calcular_diversidade(self, numero):
        """Calcula fator de diversidade"""
        freq = self.estatisticas.frequencias.get(numero, 0)
        media = np.mean(list(self.estatisticas.frequencias.values())) if self.estatisticas.frequencias else 0
        
        if freq < media * 0.5:
            return 1.0
        elif freq > media * 1.5:
            return 0.3
        else:
            return 0.7
    
    def get_ranking(self, top_n=25):
        """Retorna ranking das dezenas"""
        ranking = sorted(self.pontuacoes.items(), key=lambda x: x[1], reverse=True)
        return ranking[:top_n]

# =====================================================
# MÓDULO 4: IA ESTATÍSTICA - LOTOFÁCIL
# =====================================================

class IAEstatisticaLF:
    """Módulo 4 - IA Estatística para Lotofácil
    
    CORREÇÃO CRÍTICA: a versão anterior calculava features (frequência, atraso,
    tendência) usando `self.estatisticas`, que é computada com TODO o histórico
    carregado — incluindo concursos futuros em relação a cada linha de treino.
    Isso é "look-ahead bias": o modelo via, indiretamente, o resultado que estava
    tentando prever. Além de vazar informação, essas métricas eram CONSTANTES
    (o mesmo valor de frequência/atraso era usado para todas as 500 linhas de
    um número, não importa a época do concurso), então o modelo não tinha como
    aprender um padrão temporal real.
    
    Agora cada concurso usa apenas dados anteriores a ele (walk-forward), como
    seria em produção: no momento de prever o concurso N, só sabemos o que
    aconteceu até o concurso N-1.
    """
    
    JANELAS_TENDENCIA = [10, 20, 50, 100]
    AQUECIMENTO_MINIMO = 30  # nº de concursos necessários antes de começar a gerar linhas de treino
    
    def __init__(self, banco_dados, estatisticas):
        self.banco = banco_dados
        self.estatisticas = estatisticas
        self.modelos = {}
        self.dados_processados = None
        self._preparar_dados()
        
    def _preparar_dados(self):
        """Prepara dados de treino com features ponto-no-tempo (sem look-ahead bias)."""
        # concursos_asc: do mais antigo para o mais recente
        concursos_asc = list(reversed(self.banco.concursos))
        n = len(concursos_asc)
        
        aquecimento = min(self.AQUECIMENTO_MINIMO, max(5, n // 4))
        
        freq_total = Counter()
        janela20 = deque(maxlen=20)
        freq_janela20 = Counter()
        
        janelas_dict = {w: deque(maxlen=w) for w in self.JANELAS_TENDENCIA}
        freq_janelas_dict = {w: Counter() for w in self.JANELAS_TENDENCIA}
        
        ultimo_indice_visto = {num: -1 for num in range(1, 26)}
        
        features = []
        targets = []
        
        for t, concurso in enumerate(concursos_asc):
            dezenas = concurso['dezenas']
            dezenas_set = set(dezenas)
            
            if t >= aquecimento:
                # --- Features calculadas SOMENTE com dados de t-1 e anteriores ---
                atrasos_pt = {}
                for num in range(1, 26):
                    if ultimo_indice_visto[num] >= 0:
                        atrasos_pt[num] = t - 1 - ultimo_indice_visto[num]
                    else:
                        atrasos_pt[num] = t
                
                tendencia_pt = {}
                for num in range(1, 26):
                    freq_j = [freq_janelas_dict[w].get(num, 0) / w for w in self.JANELAS_TENDENCIA]
                    x = np.arange(len(freq_j))
                    tendencia_pt[num] = np.polyfit(x, freq_j, 1)[0] if len(freq_j) > 1 else 0
                
                pares_prop = sum(1 for nn in dezenas if nn % 2 == 0) / 15
                faixa_baixa_prop = sum(1 for nn in dezenas if nn <= 8) / 15
                faixa_media_prop = sum(1 for nn in dezenas if 9 <= nn <= 16) / 15
                soma_prop = sum(dezenas) / 25
                
                # "Vizinhança quente": frequência histórica média dos números
                # próximos (num-3..num+3), calculada só com dados anteriores.
                # IMPORTANTE: ao contrário da versão anterior, isso NÃO usa o
                # resultado do concurso que está sendo rotulado — só estatística
                # ponto-no-tempo — então não vaza a resposta certa (a versão
                # antiga dava 0 para toda dezena não sorteada e >0 quase sempre
                # para a sorteada, o que é basicamente entregar o gabarito).
                max_freq_total = max(freq_total.values()) if freq_total else 1
                
                for num in range(1, 26):
                    vizinhos = [v for v in range(max(1, num - 3), min(25, num + 3) + 1) if v != num]
                    proximidade = (np.mean([freq_total.get(v, 0) for v in vizinhos]) / max_freq_total) if vizinhos else 0
                    features.append([
                        freq_total.get(num, 0),
                        freq_janela20.get(num, 0),
                        atrasos_pt.get(num, 0),
                        tendencia_pt.get(num, 0),
                        pares_prop,
                        faixa_baixa_prop,
                        faixa_media_prop,
                        soma_prop,
                        proximidade
                    ])
                    targets.append(1 if num in dezenas_set else 0)
            
            # --- Atualiza acumuladores DEPOIS de gerar as features (dados só ficam
            # "disponíveis" para o próximo concurso) ---
            freq_total.update(dezenas)
            
            if len(janela20) == 20:
                freq_janela20.subtract(janela20[0])
            janela20.append(dezenas)
            freq_janela20.update(dezenas)
            
            for w in self.JANELAS_TENDENCIA:
                dq = janelas_dict[w]
                if len(dq) == w:
                    freq_janelas_dict[w].subtract(dq[0])
                dq.append(dezenas)
                freq_janelas_dict[w].update(dezenas)
            
            for num in dezenas:
                ultimo_indice_visto[num] = t
        
        self.dados_processados = {
            'features': np.array(features) if features else np.empty((0, 9)),
            'targets': np.array(targets) if targets else np.empty((0,))
        }
    
    def _split_cronologico(self, X, y):
        """Divide em treino/calibração/teste respeitando a ordem temporal
        (sem embaralhar), para não misturar 'futuro' com 'passado' na avaliação."""
        n = len(X)
        i_train = int(n * 0.70)
        i_calib = int(n * 0.85)
        return (X[:i_train], y[:i_train]), (X[i_train:i_calib], y[i_train:i_calib]), (X[i_calib:], y[i_calib:])
    
    def treinar_random_forest(self):
        """Treina Random Forest com split cronológico + calibração de probabilidades"""
        try:
            X = self.dados_processados['features']
            y = self.dados_processados['targets']
            
            if len(X) < 200:
                st.warning("⚠️ Poucos dados para treino confiável (carregue mais concursos).")
                return False
            
            (X_train, y_train), (X_calib, y_calib), (X_test, y_test) = self._split_cronologico(X, y)
            
            modelo_base = RandomForestClassifier(
                n_estimators=150,
                max_depth=12,
                min_samples_split=5,
                random_state=42,
                n_jobs=-1
            )
            modelo_base.fit(X_train, y_train)
            
            modelo_calibrado = _calibrar_modelo_prefit(modelo_base)
            modelo_calibrado.fit(X_calib, y_calib)
            
            y_pred = modelo_calibrado.predict(X_test)
            acuracia = accuracy_score(y_test, y_pred)
            
            self.modelos['random_forest'] = {
                'modelo': modelo_calibrado,
                'acuracia': acuracia,
                'feature_importance': modelo_base.feature_importances_
            }
            
            return True
        except Exception as e:
            st.error(f"Erro ao treinar Random Forest: {e}")
            return False
    
    def treinar_xgboost(self):
        """Treina Gradient Boosting com split cronológico + calibração de probabilidades"""
        try:
            X = self.dados_processados['features']
            y = self.dados_processados['targets']
            
            if len(X) < 200:
                st.warning("⚠️ Poucos dados para treino confiável (carregue mais concursos).")
                return False
            
            (X_train, y_train), (X_calib, y_calib), (X_test, y_test) = self._split_cronologico(X, y)
            
            modelo_base = GradientBoostingClassifier(
                n_estimators=150,
                learning_rate=0.1,
                max_depth=6,
                random_state=42
            )
            modelo_base.fit(X_train, y_train)
            
            modelo_calibrado = _calibrar_modelo_prefit(modelo_base)
            modelo_calibrado.fit(X_calib, y_calib)
            
            y_pred = modelo_calibrado.predict(X_test)
            acuracia = accuracy_score(y_test, y_pred)
            
            self.modelos['xgboost'] = {
                'modelo': modelo_calibrado,
                'acuracia': acuracia,
                'feature_importance': modelo_base.feature_importances_
            }
            
            return True
        except Exception as e:
            st.error(f"Erro ao treinar XGBoost: {e}")
            return False
    
    def prever_probabilidades(self, jogo):
        """Prevê probabilidades para um jogo"""
        if not self.modelos:
            return None
        
        max_freq_total = max(self.estatisticas.frequencias.values()) if self.estatisticas.frequencias else 1
        
        features = []
        for num in jogo:
            vizinhos = [v for v in range(max(1, num - 3), min(25, num + 3) + 1) if v != num]
            proximidade = (np.mean([self.estatisticas.frequencias.get(v, 0) for v in vizinhos]) / max_freq_total) if vizinhos else 0
            features.append([
                self.estatisticas.frequencias.get(num, 0),
                self.estatisticas.frequencias_periodos.get(20, {}).get(num, 0),
                self.estatisticas.atrasos.get(num, 0),
                self.estatisticas.tendencias.get(num, {}).get('inclinacao', 0),
                contar_pares_lf(jogo) / 15,
                sum([1 for n in jogo if n <= 8]) / 15,
                sum([1 for n in jogo if 9 <= n <= 16]) / 15,
                sum(jogo) / 25,
                proximidade
            ])
        
        features = np.array(features)
        
        resultados = {}
        for nome, info in self.modelos.items():
            modelo = info['modelo']
            probs = modelo.predict_proba(features)
            resultados[nome] = {
                'probabilidades': probs[:, 1].tolist(),
                'media': np.mean(probs[:, 1]),
                'acuracia': info.get('acuracia', 0)
            }
        
        return resultados

# =====================================================
# MÓDULO 5: FILTROS INTELIGENTES - LOTOFÁCIL
# =====================================================

class FiltrosInteligentesLF:
    """Módulo 5 - Filtros Inteligentes para Lotofácil"""
    
    def __init__(self, estatisticas):
        self.estatisticas = estatisticas
        self.filtros_padrao = self._definir_filtros_padrao()
    
    def _definir_filtros_padrao(self):
        soma_stats = self.estatisticas.distribuicao_soma
        return {
            'pares_min': 6,
            'pares_max': 9,
            'soma_min': max(160, int(soma_stats['percentil_25'] - 10)),
            'soma_max': min(240, int(soma_stats['percentil_75'] + 10)),
            'faixa_min': 4,
            'faixa_max': 6,
            'consecutivos_max': 4,
            'repetidas_max': 10,
            'primos_min': 3,
            'primos_max': 7,
            # CORREÇÃO: numa combinação de 15 dezenas em 25 (5 linhas de 5),
            # é matematicamente quase impossível deixar mais de 1 linha vazia
            # (>97% dos jogos ativam as 5 linhas, ~2.4% ativam 4, e ativar só
            # 2-3 linhas é praticamente 0%). O default anterior (min:2, max:4)
            # rejeitava >97% de QUALQUER combinação válida — inclusive sorteios
            # reais da Lotofácil — fazendo o gerador quase sempre falhar ou cair
            # no fallback de filtros flexíveis.
            'linhas_min': 4,
            'linhas_max': 5,
            'colunas_min': 4,
            'colunas_max': 5
        }
    
    def aplicar_filtros(self, jogo, filtros=None):
        """Aplica filtros ao jogo"""
        if filtros is None:
            filtros = self.filtros_padrao
        
        # Paridade
        pares = contar_pares_lf(jogo)
        if not (filtros.get('pares_min', 6) <= pares <= filtros.get('pares_max', 9)):
            return False, f'Paridade: {pares} pares'
        
        # Soma
        soma = sum(jogo)
        if not (filtros.get('soma_min', 160) <= soma <= filtros.get('soma_max', 240)):
            return False, f'Soma: {soma}'
        
        # Distribuição por faixas
        faixas = distribuir_faixas_lf(jogo)
        for f in faixas:
            if not (filtros.get('faixa_min', 4) <= f <= filtros.get('faixa_max', 6)):
                return False, f'Faixa com {f} números'
        
        # Consecutivos
        consec = contar_consecutivos_lf(jogo)
        if consec > filtros.get('consecutivos_max', 4):
            return False, f'{consec} números consecutivos'
        
        # Primos
        primos = contar_primos_lf(jogo)
        if not (filtros.get('primos_min', 3) <= primos <= filtros.get('primos_max', 7)):
            return False, f'{primos} números primos'
        
        # Linhas
        linhas = distribuir_linhas_lf(jogo)
        linhas_ativas = len([l for l in linhas if l > 0])
        if not (filtros.get('linhas_min', 2) <= linhas_ativas <= filtros.get('linhas_max', 4)):
            return False, f'{linhas_ativas} linhas ativas'
        
        # Colunas
        colunas = distribuir_colunas_lf(jogo)
        colunas_ativas = len([c for c in colunas if c > 0])
        if not (filtros.get('colunas_min', 2) <= colunas_ativas <= filtros.get('colunas_max', 4)):
            return False, f'{colunas_ativas} colunas ativas'
        
        # Repetidas do último concurso
        if self.estatisticas.banco.concursos:
            ultimo = self.estatisticas.banco.concursos[0]['dezenas']
            repetidas = len(set(jogo) & set(ultimo))
            if repetidas > filtros.get('repetidas_max', 10):
                return False, f'{repetidas} números repetidos'
        
        return True, 'Aprovado'
    
    def get_filtros_recomendados(self):
        """Retorna filtros recomendados baseados nas estatísticas"""
        soma_stats = self.estatisticas.distribuicao_soma
        rep_stats = self.estatisticas.distribuicao_repetidas
        
        return {
            'pares_min': 6,
            'pares_max': 9,
            'soma_min': int(soma_stats['percentil_25'] - 5),
            'soma_max': int(soma_stats['percentil_75'] + 5),
            'faixa_min': 4,
            'faixa_max': 6,
            'consecutivos_max': 4,
            'repetidas_max': int(rep_stats.get('media', 8) + 1),
            'primos_min': 3,
            'primos_max': 7,
            'linhas_min': 4,
            'linhas_max': 5,
            'colunas_min': 4,
            'colunas_max': 5
        }

# =====================================================
# MÓDULO 6: GERADOR PREMIUM - LOTOFÁCIL (CORRIGIDO)
# =====================================================

class GeradorPremiumLF:
    """Módulo 6 - Gerador Premium para Lotofácil"""
    
    def __init__(self, banco_dados, estatisticas, pontuacao, filtros, ia=None):
        self.banco = banco_dados
        self.estatisticas = estatisticas
        self.pontuacao = pontuacao
        self.filtros = filtros
        self.ia = ia
    
    def gerar_jogos(self, qtd=10, estrategia='equilibrada', dezenas_base=None, filtros_personalizados=None, max_tentativas=None):
        """Gera jogos baseados na estratégia escolhida"""
        if filtros_personalizados is None:
            filtros_personalizados = self.filtros.get_filtros_recomendados()
        
        # CORREÇÃO: com exatamente 15 dezenas-base só existe 1 combinação possível.
        # O código anterior tentava gerar `qtd` jogos amostrando 15-de-15 repetidamente,
        # o que sempre produz o mesmo jogo — a checagem "not in jogos" bloqueava
        # qualquer repetição e o loop rodava até `max_tentativas` sem nunca completar.
        if dezenas_base:
            dezenas_base = sorted(set(dezenas_base))
            if len(dezenas_base) < 15:
                st.warning(f"⚠️ Dezenas-base precisa ter pelo menos 15 números únicos (recebido: {len(dezenas_base)}). Ignorando dezenas-base.")
                dezenas_base = None
            elif len(dezenas_base) == 15:
                st.info("ℹ️ Exatamente 15 dezenas-base: só existe 1 jogo possível com essa combinação.")
        
        jogos = []
        tentativas = 0
        if max_tentativas is None:
            max_tentativas = qtd * 10000
        
        # Obtém ranking das dezenas
        ranking = self.pontuacao.get_ranking(20)
        dezenas_prioritarias = [n for n, _ in ranking]
        
        # Estratégias
        estrategias = {
            'conservadora': self._gerar_conservadora,
            'equilibrada': self._gerar_equilibrada,
            'diversificada': self._gerar_diversificada
        }
        
        gerador = estrategias.get(estrategia, self._gerar_equilibrada)
        
        if dezenas_base and len(dezenas_base) == 15:
            return [sorted(dezenas_base)]
        
        progress_bar = st.progress(0, text="Gerando jogos...")
        
        while len(jogos) < qtd and tentativas < max_tentativas:
            tentativas += 1
            
            # Gera o jogo usando a estratégia escolhida
            if dezenas_base and len(dezenas_base) >= 15:
                # Usa dezenas base se fornecidas
                jogo = sorted(random.sample(dezenas_base, 15))
            else:
                # Gera jogo com a estratégia
                jogo = gerador(dezenas_prioritarias)
                
                # Garante que o jogo tem 15 números
                while len(jogo) < 15:
                    novo = random.randint(1, 25)
                    if novo not in jogo:
                        jogo.append(novo)
                jogo = sorted(jogo)
            
            # Aplica filtros
            aprovado, mensagem = self.filtros.aplicar_filtros(jogo, filtros_personalizados)
            
            if aprovado and jogo not in jogos:
                jogos.append(jogo)
            
            if tentativas % 200 == 0:
                progress_bar.progress(
                    min(len(jogos)/qtd, 1.0),
                    text=f"Gerados {len(jogos)}/{qtd} jogos (tentativas: {tentativas})"
                )
        
        progress_bar.empty()
        
        # Se não gerou todos os jogos, tenta com menos filtros
        if len(jogos) < qtd:
            st.warning(f"⚠️ Gerados apenas {len(jogos)} de {qtd} jogos com os filtros atuais. Tentando com filtros mais flexíveis...")
            
            # Filtros mais flexíveis
            filtros_flexiveis = filtros_personalizados.copy()
            filtros_flexiveis['pares_min'] = max(4, filtros_personalizados.get('pares_min', 6) - 2)
            filtros_flexiveis['pares_max'] = min(11, filtros_personalizados.get('pares_max', 9) + 2)
            filtros_flexiveis['soma_min'] = max(150, filtros_personalizados.get('soma_min', 180) - 20)
            filtros_flexiveis['soma_max'] = min(250, filtros_personalizados.get('soma_max', 210) + 20)
            filtros_flexiveis['consecutivos_max'] = min(6, filtros_personalizados.get('consecutivos_max', 4) + 2)
            filtros_flexiveis['faixa_min'] = max(3, filtros_personalizados.get('faixa_min', 4) - 1)
            filtros_flexiveis['faixa_max'] = min(7, filtros_personalizados.get('faixa_max', 6) + 1)
            filtros_flexiveis['linhas_min'] = min(3, filtros_personalizados.get('linhas_min', 4))
            filtros_flexiveis['colunas_min'] = min(3, filtros_personalizados.get('colunas_min', 4))
            
            tentativas_extra = 0
            while len(jogos) < qtd and tentativas_extra < 5000:
                tentativas_extra += 1
                jogo = sorted(random.sample(range(1, 26), 15))
                aprovado, mensagem = self.filtros.aplicar_filtros(jogo, filtros_flexiveis)
                if aprovado and jogo not in jogos:
                    jogos.append(jogo)
        
        return jogos
    
    def _gerar_conservadora(self, dezenas_prioritarias):
        """Estratégia Conservadora: prioriza números mais frequentes"""
        jogo = set()
        
        # Pega 10 números do top ranking
        top = dezenas_prioritarias[:15]
        qtd_top = min(10, len(top))
        if qtd_top > 0:
            jogo.update(random.sample(top, qtd_top))
        
        # Completa com números aleatórios
        while len(jogo) < 15:
            novo = random.randint(1, 25)
            if novo not in jogo:
                jogo.add(novo)
        
        return sorted(list(jogo))
    
    def _gerar_equilibrada(self, dezenas_prioritarias):
        """Estratégia Equilibrada: balanceia frequência e diversidade"""
        jogo = set()
        
        # Pega 8 números do ranking
        top = dezenas_prioritarias[:20]
        qtd_top = min(8, len(top))
        if qtd_top > 0:
            jogo.update(random.sample(top, qtd_top))
        
        # Pega 4 números de fora do top
        fora_top = [n for n in range(1, 26) if n not in top]
        if fora_top and len(jogo) < 14:
            qtd_fora = min(4, len(fora_top), 15 - len(jogo))
            jogo.update(random.sample(fora_top, qtd_fora))
        
        # Completa com números aleatórios
        while len(jogo) < 15:
            novo = random.randint(1, 25)
            if novo not in jogo:
                jogo.add(novo)
        
        return sorted(list(jogo))
    
    def _gerar_diversificada(self, dezenas_prioritarias):
        """Estratégia Diversificada: mistura diferentes tipos"""
        jogo = set()
        
        # Pega 6 do ranking
        top = dezenas_prioritarias[:20]
        qtd_top = min(6, len(top))
        if qtd_top > 0:
            jogo.update(random.sample(top, qtd_top))
        
        # Pega 5 atrasados
        atrasados = sorted(self.estatisticas.atrasos.items(), key=lambda x: x[1], reverse=True)[:10]
        atrasados_nums = [n for n, _ in atrasados]
        if atrasados_nums and len(jogo) < 14:
            qtd_atrasados = min(5, len(atrasados_nums), 15 - len(jogo))
            jogo.update(random.sample(atrasados_nums, qtd_atrasados))
        
        # Completa com números aleatórios
        while len(jogo) < 15:
            novo = random.randint(1, 25)
            if novo not in jogo:
                jogo.add(novo)
        
        return sorted(list(jogo))

# =====================================================
# MÓDULO 7: BACKTESTS - LOTOFÁCIL
# =====================================================

class _BancoTemporal:
    """Wrapper leve que expõe apenas os concursos anteriores a um certo ponto no
    tempo, para permitir recalcular estatísticas 'como se estivéssemos naquela
    época' — necessário para um backtest sem look-ahead bias."""
    def __init__(self, concursos):
        self.concursos = concursos
    
    def get_historico_dezenas(self):
        return [c['dezenas'] for c in self.concursos]


class BacktestsLF:
    """Módulo 7 - Backtests para Lotofácil"""
    
    AQUECIMENTO_MINIMO = 30  # concursos mínimos de histórico antes de testar um ponto
    
    def __init__(self, banco_dados, estatisticas, filtros):
        self.banco = banco_dados
        self.estatisticas = estatisticas
        self.filtros = filtros
    
    def testar_estrategia(self, estrategia='equilibrada', num_testes=50, filtros_personalizados=None, jogos_por_teste=5):
        """Testa uma estratégia no histórico.
        
        CORREÇÃO CRÍTICA: a versão anterior gerava os jogos de teste usando
        `self.estatisticas`, calculada com TODOS os concursos carregados —
        incluindo os próprios concursos que estavam sendo testados (que são
        justamente os mais recentes). Ou seja, o "backtest" estava usando
        frequência/atraso que já 'sabiam' o resultado que tentavam prever,
        inflando artificialmente os acertos.
        
        Agora, para cada concurso testado, as estatísticas são recalculadas
        usando apenas concursos estritamente ANTERIORES a ele — replicando o
        que estaria disponível no momento real da aposta.
        """
        if filtros_personalizados is None:
            filtros_personalizados = self.filtros.get_filtros_recomendados()
        
        resultados = []
        historico = self.banco.concursos  # mais recente primeiro
        
        testes = historico[:min(num_testes, len(historico))]
        
        progress_bar = st.progress(0, text=f"Executando backtest (ponto-no-tempo) - {estrategia}...")
        pulados = 0
        
        for i, concurso in enumerate(testes):
            dezenas_reais = concurso['dezenas']
            
            # `testes` é um prefixo de `historico`, então a posição em `testes`
            # é a mesma posição em `historico` (mais recente = índice 0)
            concursos_anteriores = historico[i + 1:]  # apenas dados mais antigos que o teste
            
            if len(concursos_anteriores) < self.AQUECIMENTO_MINIMO:
                pulados += 1
                progress_bar.progress((i + 1) / len(testes))
                continue
            
            banco_pt = _BancoTemporal(concursos_anteriores)
            estatisticas_pt = EstatisticasLFAvancadas(banco_pt)
            filtros_pt = FiltrosInteligentesLF(estatisticas_pt)
            pontuacao_pt = MotorPontuacaoLF(estatisticas_pt)
            
            gerador_temp = GeradorPremiumLF(banco_pt, estatisticas_pt, pontuacao_pt, filtros_pt)
            
            jogos = gerador_temp.gerar_jogos(
                qtd=jogos_por_teste,
                estrategia=estrategia,
                filtros_personalizados=filtros_personalizados,
                max_tentativas=jogos_por_teste * 2000
            )
            
            for jogo in jogos:
                acertos = len(set(jogo) & set(dezenas_reais))
                resultados.append(acertos)
            
            progress_bar.progress((i + 1) / len(testes))
        
        progress_bar.empty()
        
        if pulados:
            st.caption(f"ℹ️ {pulados} concurso(s) pulado(s) por não terem histórico anterior suficiente ({self.AQUECIMENTO_MINIMO}+ concursos).")
        
        return {
            'estrategia': estrategia,
            'total_simulacoes': len(resultados),
            'media': np.mean(resultados) if resultados else 0,
            'mediana': np.median(resultados) if resultados else 0,
            'std': np.std(resultados) if resultados else 0,
            'max': max(resultados) if resultados else 0,
            'min': min(resultados) if resultados else 0,
            'distribuicao': Counter(resultados) if resultados else {},
            'percentil_75': np.percentile(resultados, 75) if resultados else 0,
            'percentil_25': np.percentile(resultados, 25) if resultados else 0
        }
    
    def comparar_estrategias(self, estrategias=['conservadora', 'equilibrada', 'diversificada'], num_testes=50):
        """Compara múltiplas estratégias"""
        resultados = {}
        for estrategia in estrategias:
            resultados[estrategia] = self.testar_estrategia(estrategia, num_testes)
        return resultados

# =====================================================
# FUNÇÃO PARA TESTAR A GERAÇÃO
# =====================================================

def testar_geracao():
    """Função de teste para verificar se os jogos estão sendo gerados corretamente"""
    
    # Cria dados de teste
    dados_teste = []
    for i in range(100):
        dados_teste.append({
            'concurso': i + 1,
            'data': f'01/01/202{i}',
            'dezenas': sorted(random.sample(range(1, 26), 15))
        })
    
    # Inicializa módulos
    banco = BancoDadosLFInteligente(dados_teste)
    estatisticas = EstatisticasLFAvancadas(banco)
    pontuacao = MotorPontuacaoLF(estatisticas)
    filtros = FiltrosInteligentesLF(estatisticas)
    
    # Cria gerador
    gerador = GeradorPremiumLF(banco, estatisticas, pontuacao, filtros)
    
    # Testa geração
    st.write("🧪 Testando geração de jogos...")
    
    for estrategia in ['conservadora', 'equilibrada', 'diversificada']:
        st.write(f"\n📊 Estratégia: {estrategia}")
        jogos = gerador.gerar_jogos(qtd=5, estrategia=estrategia)
        
        if jogos:
            st.success(f"✅ Gerados {len(jogos)} jogos")
            for i, jogo in enumerate(jogos[:3]):
                st.write(f"  Jogo {i+1}: {jogo} (tamanho: {len(jogo)})")
        else:
            st.error("❌ Nenhum jogo gerado")
    
    st.success("\n✅ Teste concluído!")

# =====================================================
# INTERFACE PRINCIPAL
# =====================================================

def main():
    # Inicializa session state
    if "dados_api" not in st.session_state:
        st.session_state.dados_api = None
    if "banco_dados" not in st.session_state:
        st.session_state.banco_dados = None
    if "estatisticas" not in st.session_state:
        st.session_state.estatisticas = None
    if "pontuacao" not in st.session_state:
        st.session_state.pontuacao = None
    if "ia" not in st.session_state:
        st.session_state.ia = None
    if "filtros" not in st.session_state:
        st.session_state.filtros = None
    if "gerador" not in st.session_state:
        st.session_state.gerador = None
    if "backtests" not in st.session_state:
        st.session_state.backtests = None
    if "jogos_gerados" not in st.session_state:
        st.session_state.jogos_gerados = []
    if "jogos_salvos" not in st.session_state:
        st.session_state.jogos_salvos = []
    if "ia_treinada" not in st.session_state:
        st.session_state.ia_treinada = False

    # Barra Lateral
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        qtd_concursos = st.slider("Qtd concursos históricos", 50, 500, 200)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Carregar Lotofácil", use_container_width=True):
                with st.spinner("Carregando dados da Lotofácil..."):
                    dados = buscar_historico_lotofacil(qtd_concursos)
                    if dados and len(dados) > 0:
                        st.session_state.dados_api = dados
                        
                        # Inicializa módulos
                        st.session_state.banco_dados = BancoDadosLFInteligente(dados)
                        st.session_state.estatisticas = EstatisticasLFAvancadas(st.session_state.banco_dados)
                        st.session_state.pontuacao = MotorPontuacaoLF(st.session_state.estatisticas)
                        st.session_state.filtros = FiltrosInteligentesLF(st.session_state.estatisticas)
                        
                        # IA
                        st.session_state.ia = IAEstatisticaLF(st.session_state.banco_dados, st.session_state.estatisticas)
                        
                        st.session_state.gerador = GeradorPremiumLF(
                            st.session_state.banco_dados,
                            st.session_state.estatisticas,
                            st.session_state.pontuacao,
                            st.session_state.filtros,
                            st.session_state.ia
                        )
                        
                        st.session_state.backtests = BacktestsLF(
                            st.session_state.banco_dados,
                            st.session_state.estatisticas,
                            st.session_state.filtros
                        )
                        
                        st.success(f"✅ {len(dados)} concursos carregados!")
                        st.info("🔄 IA pronta para treinamento")
        
        with col2:
            if st.button("🧠 Treinar IA", use_container_width=True):
                with st.spinner("Treinando modelos de IA..."):
                    if st.session_state.ia:
                        rf_ok = st.session_state.ia.treinar_random_forest()
                        xgb_ok = st.session_state.ia.treinar_xgboost()
                        if rf_ok or xgb_ok:
                            st.session_state.ia_treinada = True
                            st.success("✅ IA treinada com sucesso!")
        
        st.markdown("---")
        
        # Informações do sistema
        if st.session_state.banco_dados:
            ultimo = st.session_state.banco_dados.get_ultimo_concurso()
            if ultimo:
                st.markdown("### 📅 Último Concurso")
                st.markdown(f"**#{ultimo['numero']}**")
                st.markdown(f"📆 {ultimo['data']}")
                dezenas = ultimo['dezenas']
                st.markdown(f"🎯 {', '.join(f'{d:02d}' for d in dezenas)}")
        
        st.markdown("---")
        st.caption("LOTOFÁCIL Elite 3.0 v1.0")

    # Conteúdo Principal
    if not st.session_state.dados_api:
        st.info("👈 Carregue os dados da Lotofácil na barra lateral para começar.")
        return

    st.subheader("🎯 LOTOFÁCIL Elite 3.0 - Sistema Avançado")

    # Tabs
    tabs = st.tabs([
        "📊 Dashboard",
        "🏆 Ranking",
        "🧠 IA Estatística",
        "🎲 Gerador Premium",
        "🔬 Backtests",
        "📈 Análise Avançada",
        "💾 Salvos"
    ])

    # ================= TAB 1: DASHBOARD =================
    with tabs[0]:
        st.markdown("### 📊 Dashboard - Visão Geral")
        
        if st.session_state.estatisticas:
            stats = st.session_state.estatisticas
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Concursos", stats.total_concursos)
            with col2:
                st.metric("📊 Média Soma", f"{stats.media_soma:.1f}")
            with col3:
                st.metric("⚖️ Média Pares", f"{stats.media_pares:.1f}")
            with col4:
                st.metric("📊 Média Linhas", f"{stats.media_linhas:.1f}")
            
            # Gráficos interativos
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 📊 Frequência das Dezenas")
                df_freq = pd.DataFrame({
                    'Dezena': range(1, 26),
                    'Frequência': [stats.frequencias.get(i, 0) for i in range(1, 26)]
                })
                fig = px.bar(df_freq, x='Dezena', y='Frequência', title='Frequência por Dezena')
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("### ⏰ Atraso das Dezenas")
                df_atraso = pd.DataFrame({
                    'Dezena': range(1, 26),
                    'Atraso': [stats.atrasos.get(i, 0) for i in range(1, 26)]
                })
                fig = px.bar(df_atraso, x='Dezena', y='Atraso', title='Atraso por Dezena',
                            color='Atraso', color_continuous_scale='Viridis')
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

    # ================= TAB 2: RANKING =================
    with tabs[1]:
        st.markdown("### 🏆 Ranking das Dezenas")
        
        if st.session_state.pontuacao:
            pontuacao = st.session_state.pontuacao
            stats = st.session_state.estatisticas
            
            col1, col2 = st.columns(2)
            with col1:
                top_n = st.slider("Top N dezenas", 5, 25, 15)
            with col2:
                mostrar_detalhes = st.checkbox("Mostrar detalhes", True)
            
            ranking = pontuacao.get_ranking(top_n)
            
            for pos, (num, score) in enumerate(ranking, 1):
                medalha = "🥇" if pos == 1 else "🥈" if pos == 2 else "🥉" if pos == 3 else f"{pos}º"
                classe = f"pos-{pos}" if pos <= 3 else ""
                
                stats_dezena = stats.get_estatisticas_dezena(num)
                tendencia = stats_dezena['tendencia']['tendencia']
                tendencia_cls = "tendencia-up" if tendencia == "subindo" else "tendencia-down" if tendencia == "caindo" else "tendencia-stable"
                tendencia_icon = "⬆️" if tendencia == "subindo" else "⬇️" if tendencia == "caindo" else "➡️"
                
                detalhes = ""
                if mostrar_detalhes:
                    freq_periodos = stats_dezena['frequencia_periodos']
                    detalhes = f"""
                    <small style='color:#aaa;'>
                        Freq: {stats_dezena['frequencia']} | 
                        Últimos 20: {freq_periodos.get(20, 0)} | 
                        Atraso: {stats_dezena['atraso']} | 
                        Tendência: <span class='{tendencia_cls}'>{tendencia_icon} {tendencia}</span>
                    </small>
                    """
                
                st.markdown(f"""
                <div class='ranking-card'>
                    <div>
                        <span class='{classe}'>{medalha}</span>
                        <strong>Dezena {num:02d}</strong>
                        <span style='float: right;'>
                            <strong>Score: {score:.2f}</strong>
                        </span>
                    </div>
                    {detalhes}
                </div>
                """, unsafe_allow_html=True)

    # ================= TAB 3: IA ESTATÍSTICA =================
    with tabs[2]:
        st.markdown("### 🧠 IA Estatística")
        st.markdown("""
        <div class="ia-lf-highlight">
            <strong>🤖 Modelos de IA:</strong><br>
            • Random Forest: Classifica combinações baseado em padrões históricos<br>
            • XGBoost: Gradient Boosting para análise de tendências<br>
            • Análise de Feature Importance para identificar fatores relevantes
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.ia:
            ia = st.session_state.ia
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Modelos Treinados", len(ia.modelos))
            with col2:
                st.metric("Dados de Treino", len(ia.dados_processados['features']) if ia.dados_processados else 0)
            with col3:
                status = "✅ Treinada" if st.session_state.ia_treinada else "⚠️ Não treinada"
                st.metric("Status", status)
            
            if ia.modelos:
                st.markdown("### 📊 Performance dos Modelos")
                
                for nome, info in ia.modelos.items():
                    st.markdown(f"**{nome.upper()}**")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Acurácia", f"{info.get('acuracia', 0)*100:.2f}%")
                    with col2:
                        if 'feature_importance' in info:
                            importance = info['feature_importance']
                            st.metric("Importância Média", f"{np.mean(importance):.3f}")
                
                # Feature Importance
                st.markdown("### 📈 Feature Importance")
                
                feature_names = ['Frequência', 'Freq. Recente', 'Atraso', 'Tendência', 
                               'Proporção Pares', 'Faixa Baixa', 'Faixa Média', 'Soma', 'Proximidade']
                
                for nome, info in ia.modelos.items():
                    if 'feature_importance' in info:
                        df_imp = pd.DataFrame({
                            'Feature': feature_names[:len(info['feature_importance'])],
                            'Importância': info['feature_importance']
                        }).sort_values('Importância', ascending=True)
                        
                        fig = px.bar(df_imp, x='Importância', y='Feature', 
                                    title=f'Feature Importance - {nome.upper()}',
                                    orientation='h')
                        st.plotly_chart(fig, use_container_width=True)

    # ================= TAB 4: GERADOR PREMIUM =================
    with tabs[3]:
        st.markdown("### 🎲 Gerador Premium")
        
        if st.session_state.gerador:
            gerador = st.session_state.gerador
            
            # Botão de teste rápido
            if st.button("🧪 Testar Geração", use_container_width=True):
                testar_geracao()
            
            with st.expander("⚙️ Configurações", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    qtd_jogos = st.slider("Quantidade de jogos", 1, 50, 10)
                    estrategia = st.selectbox("Estratégia", 
                                             ['conservadora', 'equilibrada', 'diversificada'],
                                             index=1)
                with col2:
                    usar_base = st.checkbox("Usar dezenas-base")
                    dezenas_base = []
                    if usar_base:
                        base_input = st.text_input("Dezenas base (separadas por vírgula)", 
                                                  "1,2,3,4,5,6,7,8,9,10,11,12,13,14,15")
                        try:
                            dezenas_base = [int(x.strip()) for x in base_input.split(",") if x.strip()]
                            dezenas_base = sorted(dezenas_base)[:20]
                            st.success(f"✅ {len(dezenas_base)} dezenas base carregadas")
                        except:
                            st.warning("Formato inválido. Use números separados por vírgula.")
                with col3:
                    usar_filtros_personalizados = st.checkbox("Filtros personalizados")
                    if usar_filtros_personalizados:
                        pares_min = st.slider("Mínimo Pares", 0, 15, 6)
                        pares_max = st.slider("Máximo Pares", 0, 15, 9)
                        soma_min = st.slider("Soma Mínima", 150, 300, 180)
                        soma_max = st.slider("Soma Máxima", 150, 300, 210)
                        consec_max = st.slider("Máx. Consecutivos", 1, 10, 4)
                        linhas_min = st.slider("Mínimo Linhas ativas", 1, 5, 4, help="Em 15 dezenas de 25, quase sempre 4 ou 5 das 5 linhas ficam ativas. Valores abaixo de 4 raramente são satisfeitos.")
                        linhas_max = st.slider("Máximo Linhas ativas", 1, 5, 5)
                    else:
                        filtros_recomendados = st.session_state.filtros.get_filtros_recomendados()
                        pares_min = filtros_recomendados['pares_min']
                        pares_max = filtros_recomendados['pares_max']
                        soma_min = filtros_recomendados['soma_min']
                        soma_max = filtros_recomendados['soma_max']
                        consec_max = filtros_recomendados['consecutivos_max']
                        linhas_min = filtros_recomendados['linhas_min']
                        linhas_max = filtros_recomendados['linhas_max']
                
                # Monta filtros (corrige min/max invertidos, já que os sliders
                # são independentes e nada impedia pares_min > pares_max etc.)
                pares_min, pares_max = min(pares_min, pares_max), max(pares_min, pares_max)
                soma_min, soma_max = min(soma_min, soma_max), max(soma_min, soma_max)
                linhas_min, linhas_max = min(linhas_min, linhas_max), max(linhas_min, linhas_max)
                
                filtros = {
                    'pares_min': pares_min,
                    'pares_max': pares_max,
                    'soma_min': soma_min,
                    'soma_max': soma_max,
                    'faixa_min': 4,
                    'faixa_max': 6,
                    'consecutivos_max': consec_max,
                    'repetidas_max': 10,
                    'primos_min': 3,
                    'primos_max': 7,
                    'linhas_min': linhas_min,
                    'linhas_max': linhas_max,
                    'colunas_min': 2,
                    'colunas_max': 4
                }
            
            if st.button("🎯 GERAR JOGOS", use_container_width=True, type="primary"):
                with st.spinner(f"Gerando {qtd_jogos} jogos com estratégia {estrategia}..."):
                    jogos = gerador.gerar_jogos(
                        qtd=qtd_jogos,
                        estrategia=estrategia,
                        dezenas_base=dezenas_base if usar_base else None,
                        filtros_personalizados=filtros
                    )
                    
                    if jogos:
                        st.session_state.jogos_gerados = jogos
                        st.success(f"✅ {len(jogos)} jogos gerados!")
                    else:
                        st.error("❌ Nenhum jogo foi gerado. Tente ajustar os filtros.")
            
            if st.session_state.jogos_gerados:
                jogos = st.session_state.jogos_gerados
                st.markdown(f"### 📋 Jogos Gerados ({len(jogos)})")
                
                # Verifica tamanho dos jogos
                tamanhos = [len(j) for j in jogos]
                if all(t == 15 for t in tamanhos):
                    st.success("✅ Todos os jogos têm 15 números")
                else:
                    st.warning(f"⚠️ Alguns jogos não têm 15 números: {tamanhos}")
                
                # Análise com IA se disponível
                if st.session_state.ia and st.session_state.ia_treinada:
                    st.markdown("#### 🤖 Análise IA dos Jogos")
                    for i, jogo in enumerate(jogos[:10]):
                        probs = st.session_state.ia.prever_probabilidades(jogo)
                        if probs:
                            cols = st.columns([3, 2])
                            with cols[0]:
                                st.markdown(f"**Jogo {i+1}:** {formatar_jogo_html_lf(jogo)}", unsafe_allow_html=True)
                            with cols[1]:
                                for nome, info in probs.items():
                                    st.metric(f"{nome.upper()} Score", f"{info['media']*100:.1f}%")
                
                # Exibição dos jogos
                for i, jogo in enumerate(jogos):
                    medalha = "🏆" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "📌"
                    
                    pares = contar_pares_lf(jogo)
                    primos = contar_primos_lf(jogo)
                    soma = sum(jogo)
                    consec = contar_consecutivos_lf(jogo)
                    faixas = distribuir_faixas_lf(jogo)
                    linhas = distribuir_linhas_lf(jogo)
                    linhas_ativas = len([l for l in linhas if l > 0])
                    
                    stats = f"⚖️ {pares}p/{15-pares}i | 🔢 {primos} primos | ➕ {soma} | 🔗 {consec} consec | 📊 {linhas_ativas} linhas"
                    
                    st.markdown(f"""
                    <div class='card' style='border-left: 5px solid {"#ffd700" if i == 0 else "#4cc9f0"};'>
                        {medalha} <strong>Jogo {i+1:2d}</strong><br>
                        {formatar_jogo_html_lf(jogo)}<br>
                        <small style='color:#aaa;'>{stats}</small>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Botões de ação
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("💾 Salvar Jogos", key="salvar_lf_elite", use_container_width=True):
                        arquivo, jogo_id = salvar_jogos_lf_elite(jogos, {
                            'estrategia': estrategia,
                            'filtros': filtros,
                            'qtd': qtd_jogos
                        })
                        if arquivo:
                            st.success(f"✅ Jogos salvos! ID: {jogo_id}")
                with col2:
                    df_export = pd.DataFrame({
                        'Jogo': range(1, len(jogos)+1),
                        'Dezenas': [', '.join(f'{d:02d}' for d in j) for j in jogos],
                        'Pares': [contar_pares_lf(j) for j in jogos],
                        'Soma': [sum(j) for j in jogos],
                        'Primos': [contar_primos_lf(j) for j in jogos],
                        'Consecutivos': [contar_consecutivos_lf(j) for j in jogos]
                    })
                    st.download_button(
                        label="📥 Exportar CSV",
                        data=df_export.to_csv(index=False),
                        file_name=f"lotofacil_elite3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                with col3:
                    txt_content = "LOTOFÁCIL ELITE 3.0 - JOGOS GERADOS\n"
                    txt_content += "=" * 50 + "\n"
                    txt_content += f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
                    txt_content += f"Estratégia: {estrategia}\n"
                    txt_content += f"Total: {len(jogos)} jogos\n\n"
                    
                    for i, jogo in enumerate(jogos):
                        txt_content += f"Jogo {i+1:2d}: {', '.join(f'{d:02d}' for d in jogo)}\n"
                    
                    st.download_button(
                        label="📝 Exportar TXT",
                        data=txt_content,
                        file_name=f"lotofacil_elite3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )

    # ================= TAB 5: BACKTESTS =================
    with tabs[4]:
        st.markdown("### 🔬 Backtests - Teste de Estratégias")
        st.markdown("""
        <div class="lotofacil-highlight">
            <strong>🎯 OBJETIVO:</strong> Testar diferentes estratégias usando dados históricos<br>
            <strong>⚠️ ATENÇÃO:</strong> Resultados passados NÃO garantem resultados futuros
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.backtests:
            backtests = st.session_state.backtests
            
            col1, col2 = st.columns(2)
            with col1:
                estrategias_backtest = st.multiselect(
                    "Selecione estratégias para testar",
                    ['conservadora', 'equilibrada', 'diversificada'],
                    default=['conservadora', 'equilibrada', 'diversificada']
                )
            with col2:
                num_testes = st.slider("Número de concursos para teste", 10, 100, 50)
            
            if st.button("🔬 EXECUTAR BACKTEST", use_container_width=True, type="primary"):
                with st.spinner(f"Executando {num_testes} simulações por estratégia..."):
                    resultados = backtests.comparar_estrategias(estrategias_backtest, num_testes)
                    
                    st.markdown("### 📊 Resultados do Backtest")
                    
                    dados_comp = []
                    for estrategia, res in resultados.items():
                        dados_comp.append({
                            'Estratégia': estrategia.capitalize(),
                            'Média': round(res['media'], 2),
                            'Mediana': round(res['mediana'], 2),
                            'Desvio': round(res['std'], 2),
                            'Máximo': res['max'],
                            'Mínimo': res['min'],
                            'P75': round(res['percentil_75'], 1),
                            'P25': round(res['percentil_25'], 1)
                        })
                    
                    df_comp = pd.DataFrame(dados_comp)
                    st.dataframe(df_comp, use_container_width=True, hide_index=True)
                    
                    fig = make_subplots(rows=1, cols=2, 
                                       subplot_titles=('Média de Acertos', 'Distribuição'))
                    
                    fig.add_trace(
                        go.Bar(x=df_comp['Estratégia'], y=df_comp['Média'],
                              name='Média', marker_color='#4cc9f0'),
                        row=1, col=1
                    )
                    
                    for estrategia, res in resultados.items():
                        dist = res['distribuicao']
                        df_dist = pd.DataFrame(list(dist.items()), columns=['Acertos', 'Frequência'])
                        fig.add_trace(
                            go.Bar(x=df_dist['Acertos'], y=df_dist['Frequência'],
                                  name=estrategia.capitalize()),
                            row=1, col=2
                        )
                    
                    fig.update_layout(height=500, showlegend=True)
                    st.plotly_chart(fig, use_container_width=True)

    # ================= TAB 6: ANÁLISE AVANÇADA =================
    with tabs[5]:
        st.markdown("### 📈 Análise Avançada")
        
        if st.session_state.estatisticas:
            stats = st.session_state.estatisticas
            
            # Análise de Correlação
            st.markdown("### 🔗 Análise de Correlação entre Dezenas")
            
            matriz = np.zeros((25, 25))
            for concurso in stats.banco.concursos:
                dezenas = concurso['dezenas']
                for i in dezenas:
                    for j in dezenas:
                        if i != j:
                            matriz[i-1][j-1] += 1
            
            for i in range(25):
                total = matriz[i].sum()
                if total > 0:
                    matriz[i] = matriz[i] / total
            
            fig = go.Figure(data=go.Heatmap(
                z=matriz,
                x=[f"{i+1:02d}" for i in range(25)],
                y=[f"{i+1:02d}" for i in range(25)],
                colorscale='Viridis'
            ))
            fig.update_layout(title='Matriz de Correlação entre Dezenas',
                            height=600)
            st.plotly_chart(fig, use_container_width=True)
            
            # Análise de Linhas e Colunas
            st.markdown("### 📊 Análise de Distribuição")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Distribuição por Linhas**")
                df_linhas = pd.DataFrame({
                    'Linha': [1,2,3,4,5],
                    'Frequência': stats.distribuicao_linhas
                })
                fig = px.bar(df_linhas, x='Linha', y='Frequência', title='Distribuição por Linhas')
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("**Distribuição por Colunas**")
                df_colunas = pd.DataFrame({
                    'Coluna': [1,2,3,4,5],
                    'Frequência': stats.distribuicao_colunas
                })
                fig = px.bar(df_colunas, x='Coluna', y='Frequência', title='Distribuição por Colunas')
                st.plotly_chart(fig, use_container_width=True)

    # ================= TAB 7: SALVOS =================
    with tabs[6]:
        st.markdown("### 💾 Jogos Salvos")
        
        jogos_salvos = carregar_jogos_lf_elite()
        
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
<div class="footer-premium">
    <div class="footer-title">LOTOFÁCIL ELITE 3.0 SYSTEM</div>
    <div class="footer-sub">SAMUCJ TECNOLOGIA © 2026</div>
</div>
""", unsafe_allow_html=True)
