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
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from scipy.stats import norm, binom, chi2, pearsonr
from scipy.signal import find_peaks
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="🎯 MEGA-SENA Elite 3.0",
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
.mega-highlight { background: linear-gradient(135deg, #ff6b6b30 0%, #ffd93d30 50%, #6bcb7730 100%); border: 2px solid #ff6b6b; padding: 15px; border-radius: 12px; margin: 10px 0; }
.elite-mega-highlight { background: linear-gradient(135deg, #9b59b630 0%, #ffd93d30 50%, #6bcb7730 100%); border: 2px solid #9b59b6; padding: 15px; border-radius: 12px; margin: 10px 0; }
.ia-mega-highlight { background: linear-gradient(135deg, #ff6b6b30 0%, #6bcb7730 50%, #9b59b630 100%); border: 2px solid #ff6b6b; padding: 15px; border-radius: 12px; margin: 10px 0; }
.download-section { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 20px; border-radius: 15px; margin: 20px 0; border: 2px solid #ffd93d; text-align: center; }
.ranking-card { background: #0e1117; border: 1px solid #262730; border-radius: 10px; padding: 10px; margin: 5px 0; }
.pos-1 { color: #ffd700; font-weight: bold; }
.pos-2 { color: #c0c0c0; font-weight: bold; }
.pos-3 { color: #cd7f32; font-weight: bold; }
.tendencia-up { color: #4ade80; }
.tendencia-down { color: #ff6b6b; }
.tendencia-stable { color: #ffd93d; }
.footer-premium{width:100%;text-align:center;padding:22px 10px;margin-top:40px;background:linear-gradient(180deg,#0b0b0b,#050505);color:#ffffff;border-top:1px solid #222;position:relative;}
.footer-premium::before{content:"";position:absolute;top:0;left:0;width:100%;height:2px;background:linear-gradient(90deg,#ff6b6b,#ffd93d,#6bcb77,#ff6b6b);box-shadow:0 0 10px #ff6b6b;}
.footer-title{font-size:16px;font-weight:800;letter-spacing:3px;text-transform:uppercase;text-shadow:0 0 6px rgba(255,107,107,0.6);}
.footer-sub{font-size:11px;color:#bfbfbf;margin-top:4px;letter-spacing:1.5px;}
</style>
""", unsafe_allow_html=True)

st.title("🎯 MEGA-SENA Elite 3.0")
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

def salvar_jogos_mega_elite(jogos, parametros, estatisticas=None):
    try:
        if not os.path.exists("jogos_salvos_mega_elite"):
            os.makedirs("jogos_salvos_mega_elite")
        jogo_id = str(uuid.uuid4())[:8]
        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"jogos_salvos_mega_elite/jogos_{data_hora}_{jogo_id}.json"
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

def carregar_jogos_mega_elite():
    jogos_salvos = []
    try:
        if os.path.exists("jogos_salvos_mega_elite"):
            for arquivo in os.listdir("jogos_salvos_mega_elite"):
                if arquivo.endswith(".json"):
                    try:
                        with open(f"jogos_salvos_mega_elite/{arquivo}", 'r', encoding='utf-8') as f:
                            dados = json.load(f)
                            dados["arquivo"] = arquivo
                            jogos_salvos.append(dados)
                    except Exception:
                        continue
            jogos_salvos.sort(key=lambda x: x.get("data_geracao", ""), reverse=True)
    except Exception as e:
        st.error(f"Erro ao carregar jogos: {e}")
    return jogos_salvos

def formatar_jogo_html_mega(jogo, destaque_primos=True):
    primos = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59]
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

def contar_pares_mega(jogo):
    return sum(1 for d in jogo if d % 2 == 0)

def contar_primos_mega(jogo):
    primos = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59}
    return sum(1 for d in jogo if d in primos)

def contar_consecutivos_mega(jogo):
    jogo = sorted(jogo)
    return sum(1 for i in range(len(jogo)-1) if jogo[i+1] == jogo[i] + 1)

def distribuir_faixas_mega(jogo):
    faixas = [0, 0, 0]
    for n in jogo:
        if 1 <= n <= 20:
            faixas[0] += 1
        elif 21 <= n <= 40:
            faixas[1] += 1
        else:
            faixas[2] += 1
    return faixas

def distribuir_colunas_mega(jogo):
    """Distribui as 6 dezenas em 6 colunas de 10 números cada (C1: 1-10, C2: 11-20, etc)"""
    colunas = [0] * 6
    for n in jogo:
        col = (n - 1) // 10
        if col < 6:
            colunas[col] += 1
    return colunas

# =====================================================
# FUNÇÃO PARA BUSCAR DADOS DA MEGA-SENA
# =====================================================

def buscar_historico_megasena(quantidade=300):
    try:
        url_lista = "https://loteriascaixa-api.herokuapp.com/api/megasena"
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
# MÓDULO 1: BANCO DE DADOS INTELIGENTE - MEGA
# =====================================================

class BancoDadosMegaInteligente:
    """Módulo 1 - Banco de Dados Inteligente para Mega-Sena"""
    
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
                    'pares': contar_pares_mega(dezenas),
                    'impares': 6 - contar_pares_mega(dezenas),
                    'primos': contar_primos_mega(dezenas),
                    'soma': sum(dezenas),
                    'consecutivos': contar_consecutivos_mega(dezenas),
                    'faixas': distribuir_faixas_mega(dezenas),
                    'colunas': distribuir_colunas_mega(dezenas)
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
# MÓDULO 2: ESTATÍSTICAS AVANÇADAS - MEGA
# =====================================================

class EstatisticasMegaAvancadas:
    """Módulo 2 - Estatísticas Avançadas para Mega-Sena"""
    
    def __init__(self, banco_dados):
        self.banco = banco_dados
        self.dezenas = range(1, 61)
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
        self.distribuicao_colunas = self._calcular_distribuicao_colunas(historico)
        self.distribuicao_paridade = self._calcular_distribuicao_paridade(historico)
        self.distribuicao_soma = self._calcular_distribuicao_soma(historico)
        self.distribuicao_repetidas = self._calcular_distribuicao_repetidas(historico)
        
        # Estatísticas adicionais
        self.media_soma = np.mean([c['soma'] for c in self.banco.concursos])
        self.std_soma = np.std([c['soma'] for c in self.banco.concursos])
        self.media_pares = np.mean([c['pares'] for c in self.banco.concursos])
        self.media_colunas = np.mean([len([c for c in colunas if c > 0]) for colunas in [c['colunas'] for c in self.banco.concursos]])
        
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
        atrasos = {i: 0 for i in range(1, 61)}
        if not historico:
            return atrasos
        for dezena in range(1, 61):
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
        for num in range(1, 61):
            janelas = [10, 20, 50, 100]
            freq_janelas = []
            for janela in janelas:
                freq = Counter()
                for concurso in historico[:janela]:
                    if num in concurso:
                        freq[num] += 1
                freq_janelas.append(freq.get(num, 0) / janela)
            
            if len(freq_janelas) >= 2:
                # CORRIGIDO: usa o tamanho real de cada janela (10,20,50,100) no eixo X.
                # Usar apenas o índice (0,1,2,3) distorce a inclinação porque as janelas
                # não são igualmente espaçadas.
                x = np.array(janelas, dtype=float)
                y = np.array(freq_janelas)
                slope = np.polyfit(x, y, 1)[0] if len(x) > 1 else 0
                
                if slope > 0.002:
                    tendencia = 'subindo'
                elif slope < -0.002:
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
                if 1 <= num <= 20:
                    faixas[0] += 1
                elif 21 <= num <= 40:
                    faixas[1] += 1
                else:
                    faixas[2] += 1
        total = sum(faixas) if sum(faixas) > 0 else 1
        return [f/total for f in faixas]
    
    def _calcular_distribuicao_colunas(self, historico):
        colunas = [0] * 6
        for concurso in historico:
            for num in concurso:
                col = (num - 1) // 10
                if col < 6:
                    colunas[col] += 1
        total = sum(colunas) if sum(colunas) > 0 else 1
        return [c/total for c in colunas]
    
    def _calcular_distribuicao_paridade(self, historico):
        pares_total = 0
        impares_total = 0
        for concurso in historico:
            pares = contar_pares_mega(concurso)
            pares_total += pares
            impares_total += 6 - pares
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
            'probabilidade': self.frequencias.get(numero, 0) / (self.total_concursos * 6) if self.total_concursos > 0 else 0
        }

# =====================================================
# MÓDULO 2B: MATEMÁTICA COMBINATÓRIA E TESTE DE ALEATORIEDADE
# =====================================================
# Este módulo não existia no código original. Ele traz duas coisas que faltavam
# e que são o estado da arte real para este tipo de sistema:
#
# 1) Probabilidades EXATAS via distribuição hipergeométrica (não estimativas
#    empíricas). Para a Mega-Sena, a chance de acertar exatamente k dezenas em
#    um jogo de 6 dezenas é:
#
#        P(k) = C(6,k) * C(54,6-k) / C(60,6)
#
#    Isso é constante e NÃO muda com base em histórico, "atraso" ou tendência,
#    porque cada sorteio é uma extração independente sem memória.
#
# 2) Um teste qui-quadrado de aderência à uniformidade, que verifica de forma
#    estatisticamente rigorosa se a frequência observada das 60 dezenas se
#    desvia do que se espera de um sorteio justo. Isso é o jeito correto de
#    checar "quente/frio" — e, na prática, para loterias oficiais bem
#    auditadas, o resultado esperado é NÃO rejeitar a hipótese de uniformidade.

class AnaliseCombinatoriaMega:
    """Módulo 2B - Combinatória exata e teste de aleatoriedade para Mega-Sena"""

    N_DEZENAS_UNIVERSO = 60
    N_DEZENAS_JOGO = 6

    @staticmethod
    def probabilidade_exata(k, tamanho_jogo=6, universo=60, sorteados=6):
        """P(acertar exatamente k dezenas) via hipergeométrica, para um jogo de
        `tamanho_jogo` dezenas (permite calcular também para jogos de 7, 8... dezenas)."""
        if k > min(tamanho_jogo, sorteados):
            return 0.0
        favoraveis = math.comb(tamanho_jogo, k) * math.comb(universo - tamanho_jogo, sorteados - k)
        total = math.comb(universo, sorteados)
        return favoraveis / total

    @classmethod
    def tabela_probabilidades(cls, tamanho_jogo=6):
        """Retorna P(k acertos) para todos os k possíveis, com o valor '1 em N'."""
        tabela = {}
        for k in range(0, min(tamanho_jogo, 6) + 1):
            p = cls.probabilidade_exata(k, tamanho_jogo=tamanho_jogo)
            tabela[k] = {
                'probabilidade': p,
                'um_em': (1 / p) if p > 0 else float('inf')
            }
        return tabela

    @staticmethod
    def teste_qui_quadrado_uniformidade(historico):
        """Testa H0: todas as 60 dezenas têm a mesma probabilidade de sair.
        Retorna estatística, p-valor e conclusão. p-valor baixo (<0.05) sugeriria
        viés real no sorteio; para uma loteria oficial auditada, o esperado é
        NÃO rejeitar H0 (ou seja, p-valor alto)."""
        freq_obs = Counter()
        for dezenas in historico:
            freq_obs.update(dezenas)

        total_sorteios = sum(freq_obs.values())
        if total_sorteios == 0:
            return {'estatistica': 0, 'p_valor': 1.0, 'conclusao': 'Sem dados suficientes'}

        esperado_por_dezena = total_sorteios / 60
        observados = np.array([freq_obs.get(n, 0) for n in range(1, 61)])
        esperados = np.full(60, esperado_por_dezena)

        chi2_stat = np.sum((observados - esperados) ** 2 / esperados)
        graus_liberdade = 59
        p_valor = 1 - chi2.cdf(chi2_stat, graus_liberdade)

        if p_valor < 0.05:
            conclusao = "Desvio estatisticamente significativo da uniformidade (raro para loteria oficial; investigar)."
        else:
            conclusao = "Nenhum desvio estatisticamente significativo da uniformidade — consistente com sorteio justo."

        return {
            'estatistica': chi2_stat,
            'p_valor': p_valor,
            'graus_liberdade': graus_liberdade,
            'conclusao': conclusao
        }

    @staticmethod
    def valor_esperado_aposta(preco_aposta, premios_medios, tamanho_jogo=6):
        """Calcula o valor esperado (EV) de uma aposta, dado o preço e os prêmios médios
        históricos por faixa de acerto. Uma aposta de loteria quase sempre tem EV negativo
        (é assim que o jogo se financia); isso NÃO é alterado por nenhuma estratégia de
        escolha de dezenas, já que a probabilidade de cada faixa é fixa."""
        ev = -preco_aposta
        for k, premio_medio in premios_medios.items():
            p = AnaliseCombinatoriaMega.probabilidade_exata(k, tamanho_jogo=tamanho_jogo)
            ev += p * premio_medio
        return ev


# =====================================================
# MÓDULO 3: MOTOR DE PONTUAÇÃO - MEGA
# =====================================================

class MotorPontuacaoMega:
    """Módulo 3 - Motor de Pontuação para Mega-Sena"""
    
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
        
        for num in range(1, 61):
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
        faixa = 0 if numero <= 20 else 1 if numero <= 40 else 2
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
    
    def get_ranking(self, top_n=60):
        """Retorna ranking das dezenas"""
        ranking = sorted(self.pontuacoes.items(), key=lambda x: x[1], reverse=True)
        return ranking[:top_n]

# =====================================================
# MÓDULO 4: IA ESTATÍSTICA - MEGA
# =====================================================

class IAEstatisticaMega:
    """Módulo 4 - IA Estatística para Mega-Sena"""
    
    def __init__(self, banco_dados, estatisticas):
        self.banco = banco_dados
        self.estatisticas = estatisticas
        self.modelos = {}
        self.dados_processados = None
        self._preparar_dados()
        
    def _preparar_dados(self):
        """Prepara dados para treinamento SEM vazamento de dados (look-ahead bias).

        PROBLEMA NA VERSÃO ANTERIOR: as features usavam `self.estatisticas.frequencias`,
        `atrasos` e `tendencias`, todos calculados sobre o histórico COMPLETO (passado E
        futuro em relação a cada concurso usado como exemplo de treino). Além disso,
        features como `sum(dezenas)/60` e `pares do próprio jogo` eram calculadas a partir
        do PRÓPRIO concurso que estava sendo rotulado — ou seja, o modelo "via" o resultado
        que deveria prever. Isso infla artificialmente a acurácia sem gerar nenhum poder
        preditivo real fora da amostra.

        CORREÇÃO: para cada concurso, as features usam apenas frequência e atraso
        acumulados a partir dos concursos ANTERIORES (ordem cronológica), nunca do
        concurso atual ou de concursos futuros.
        """
        features = []
        targets = []

        # self.banco.concursos vem ordenado do mais recente para o mais antigo.
        # Para simular "o que se sabia até aquele momento", percorremos em ordem
        # cronológica (do mais antigo para o mais novo).
        concursos_cronologicos = list(reversed(self.banco.concursos))
        janela_recente = 20

        freq_acumulada = Counter()
        historico_janela = []  # guarda as últimas `janela_recente` dezenas sorteadas
        ultima_aparicao = {}   # numero -> índice cronológico da última vez que saiu

        for idx, concurso in enumerate(concursos_cronologicos):
            dezenas = concurso['dezenas']
            max_freq_hist = max(freq_acumulada.values()) if freq_acumulada else 1

            freq_janela = Counter()
            for d in historico_janela:
                freq_janela.update(d)
            max_freq_janela = max(freq_janela.values()) if freq_janela else 1

            for num in range(1, 61):
                freq_hist_norm = freq_acumulada.get(num, 0) / max_freq_hist
                freq_recente_norm = freq_janela.get(num, 0) / max_freq_janela
                if num in ultima_aparicao:
                    atraso = idx - ultima_aparicao[num]
                else:
                    atraso = idx  # nunca saiu até agora nesta simulação
                atraso_norm = atraso / (idx + 1)

                features.append([freq_hist_norm, freq_recente_norm, atraso_norm])
                targets.append(1 if num in dezenas else 0)

            # só DEPOIS de gerar as features é que o concurso atual entra no histórico
            freq_acumulada.update(dezenas)
            historico_janela.append(dezenas)
            if len(historico_janela) > janela_recente:
                historico_janela.pop(0)
            for num in dezenas:
                ultima_aparicao[num] = idx

        self.dados_processados = {
            'features': np.array(features),
            'targets': np.array(targets),
            'concursos_totais': len(concursos_cronologicos)
        }
    
    def _split_temporal(self, test_frac=0.2):
        """Divide os dados por TEMPO (concursos mais antigos = treino, mais recentes = teste),
        nunca aleatoriamente. Um split aleatório misturaria as 60 linhas (uma por dezena)
        de um mesmo concurso entre treino e teste, o que também vaza informação porque
        essas linhas são estatisticamente dependentes (somam sempre 6 positivos)."""
        X = self.dados_processados['features']
        y = self.dados_processados['targets']
        n_concursos = self.dados_processados['concursos_totais']

        n_test_concursos = max(1, int(n_concursos * test_frac))
        linha_corte = (n_concursos - n_test_concursos) * 60

        X_train, X_test = X[:linha_corte], X[linha_corte:]
        y_train, y_test = y[:linha_corte], y[linha_corte:]
        return X_train, X_test, y_train, y_test

    def treinar_random_forest(self):
        """Treina modelo Random Forest"""
        try:
            X_train, X_test, y_train, y_test = self._split_temporal(test_frac=0.2)

            modelo = RandomForestClassifier(
                n_estimators=150,
                max_depth=12,
                min_samples_split=5,
                random_state=42,
                n_jobs=-1,
                class_weight='balanced'
            )
            modelo.fit(X_train, y_train)
            
            y_pred = modelo.predict(X_test)
            acuracia = accuracy_score(y_test, y_pred)
            
            self.modelos['random_forest'] = {
                'modelo': modelo,
                'acuracia': acuracia,
                'feature_importance': modelo.feature_importances_
            }
            
            return True
        except Exception as e:
            st.error(f"Erro ao treinar Random Forest: {e}")
            return False
    
    def treinar_xgboost(self):
        """Treina modelo XGBoost (Gradient Boosting)"""
        try:
            from sklearn.ensemble import GradientBoostingClassifier

            X_train, X_test, y_train, y_test = self._split_temporal(test_frac=0.2)

            # GradientBoostingClassifier não aceita class_weight; aplicamos sample_weight manualmente
            classes, contagens = np.unique(y_train, return_counts=True)
            peso_por_classe = {c: len(y_train) / (len(classes) * cnt) for c, cnt in zip(classes, contagens)}
            sample_weight = np.array([peso_por_classe[v] for v in y_train])

            modelo = GradientBoostingClassifier(
                n_estimators=150,
                learning_rate=0.1,
                max_depth=6,
                random_state=42
            )
            modelo.fit(X_train, y_train, sample_weight=sample_weight)
            
            y_pred = modelo.predict(X_test)
            acuracia = accuracy_score(y_test, y_pred)
            
            self.modelos['xgboost'] = {
                'modelo': modelo,
                'acuracia': acuracia,
                'feature_importance': modelo.feature_importances_
            }
            
            return True
        except Exception as e:
            st.error(f"Erro ao treinar XGBoost: {e}")
            return False
    
    def prever_probabilidades(self, jogo):
        """Prevê probabilidades para um jogo, usando o histórico completo conhecido
        até agora (features consistentes com as usadas no treino: freq histórica
        normalizada, freq recente normalizada e atraso normalizado)."""
        if not self.modelos:
            return None

        max_freq = max(self.estatisticas.frequencias.values()) if self.estatisticas.frequencias else 1
        freq_20 = self.estatisticas.frequencias_periodos.get(20, {})
        max_freq_20 = max(freq_20.values()) if freq_20 else 1
        max_atraso = max(self.estatisticas.atrasos.values()) if self.estatisticas.atrasos else 1

        features = []
        for num in jogo:
            freq_hist_norm = self.estatisticas.frequencias.get(num, 0) / max_freq
            freq_recente_norm = freq_20.get(num, 0) / max_freq_20
            atraso_norm = self.estatisticas.atrasos.get(num, 0) / max_atraso
            features.append([freq_hist_norm, freq_recente_norm, atraso_norm])

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
# MÓDULO 5: FILTROS INTELIGENTES - MEGA
# =====================================================

class FiltrosInteligentesMega:
    """Módulo 5 - Filtros Inteligentes para Mega-Sena"""
    
    def __init__(self, estatisticas):
        self.estatisticas = estatisticas
        self.filtros_padrao = self._definir_filtros_padrao()
    
    def _definir_filtros_padrao(self):
        soma_stats = self.estatisticas.distribuicao_soma
        return {
            'pares_min': 2,
            'pares_max': 4,
            'soma_min': max(100, int(soma_stats['percentil_25'] - 20)),
            'soma_max': min(300, int(soma_stats['percentil_75'] + 20)),
            'faixa_min': 1,
            'faixa_max': 4,
            'consecutivos_max': 3,
            'repetidas_max': 3,
            'primos_min': 1,
            'primos_max': 4,
            'colunas_min': 4,
            'colunas_max': 6
        }
    
    def aplicar_filtros(self, jogo, filtros=None):
        """Aplica filtros ao jogo"""
        if filtros is None:
            filtros = self.filtros_padrao
        
        # Paridade
        pares = contar_pares_mega(jogo)
        if not (filtros.get('pares_min', 2) <= pares <= filtros.get('pares_max', 4)):
            return False, f'Paridade: {pares} pares'
        
        # Soma
        soma = sum(jogo)
        if not (filtros.get('soma_min', 100) <= soma <= filtros.get('soma_max', 300)):
            return False, f'Soma: {soma}'
        
        # Distribuição por faixas
        faixas = distribuir_faixas_mega(jogo)
        for f in faixas:
            if not (filtros.get('faixa_min', 1) <= f <= filtros.get('faixa_max', 4)):
                return False, f'Faixa com {f} números'
        
        # Consecutivos
        consec = contar_consecutivos_mega(jogo)
        if consec > filtros.get('consecutivos_max', 3):
            return False, f'{consec} números consecutivos'
        
        # Primos
        primos = contar_primos_mega(jogo)
        if not (filtros.get('primos_min', 1) <= primos <= filtros.get('primos_max', 4)):
            return False, f'{primos} números primos'
        
        # Colunas
        colunas = distribuir_colunas_mega(jogo)
        colunas_ativas = len([c for c in colunas if c > 0])
        if not (filtros.get('colunas_min', 4) <= colunas_ativas <= filtros.get('colunas_max', 6)):
            return False, f'{colunas_ativas} colunas ativas'
        
        # Repetidas do último concurso
        if self.estatisticas.banco.concursos:
            ultimo = self.estatisticas.banco.concursos[0]['dezenas']
            repetidas = len(set(jogo) & set(ultimo))
            if repetidas > filtros.get('repetidas_max', 3):
                return False, f'{repetidas} números repetidos'
        
        return True, 'Aprovado'
    
    def get_filtros_recomendados(self):
        """Retorna filtros recomendados baseados nas estatísticas"""
        soma_stats = self.estatisticas.distribuicao_soma
        rep_stats = self.estatisticas.distribuicao_repetidas
        
        return {
            'pares_min': 2,
            'pares_max': 4,
            'soma_min': int(soma_stats['percentil_25'] - 10),
            'soma_max': int(soma_stats['percentil_75'] + 10),
            'faixa_min': 1,
            'faixa_max': 4,
            'consecutivos_max': 3,
            'repetidas_max': int(rep_stats.get('media', 2) + 1),
            'primos_min': 1,
            'primos_max': 4,
            'colunas_min': 4,
            'colunas_max': 6
        }

# =====================================================
# MÓDULO 6: GERADOR PREMIUM - MEGA
# =====================================================

class GeradorPremiumMega:
    """Módulo 6 - Gerador Premium para Mega-Sena"""
    
    def __init__(self, banco_dados, estatisticas, pontuacao, filtros, ia=None):
        self.banco = banco_dados
        self.estatisticas = estatisticas
        self.pontuacao = pontuacao
        self.filtros = filtros
        self.ia = ia
    
    def gerar_jogos(self, qtd=10, estrategia='equilibrada', dezenas_base=None, filtros_personalizados=None):
        """Gera jogos baseados na estratégia escolhida"""
        if filtros_personalizados is None:
            filtros_personalizados = self.filtros.get_filtros_recomendados()
        
        jogos = []
        tentativas = 0
        max_tentativas = qtd * 10000
        
        # Obtém ranking das dezenas
        ranking = self.pontuacao.get_ranking(40)
        dezenas_prioritarias = [n for n, _ in ranking]
        
        # Estratégias
        estrategias = {
            'conservadora': self._gerar_conservadora,
            'equilibrada': self._gerar_equilibrada,
            'diversificada': self._gerar_diversificada
        }
        
        gerador = estrategias.get(estrategia, self._gerar_equilibrada)
        
        progress_bar = st.progress(0, text="Gerando jogos...")
        
        while len(jogos) < qtd and tentativas < max_tentativas:
            tentativas += 1
            
            if dezenas_base and len(dezenas_base) >= 6:
                jogo = sorted(random.sample(dezenas_base, 6))
            else:
                jogo = gerador(dezenas_prioritarias)
            
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
        return jogos
    
    def _gerar_conservadora(self, dezenas_prioritarias):
        """Estratégia Conservadora: prioriza números mais frequentes"""
        jogo = set()
        
        # Pega 4 números do top ranking
        top = dezenas_prioritarias[:20]
        jogo.update(random.sample(top, min(4, len(top))))
        
        # Completa com números aleatórios
        while len(jogo) < 6:
            novo = random.randint(1, 60)
            if novo not in jogo:
                jogo.add(novo)
        
        return sorted(jogo)
    
    def _gerar_equilibrada(self, dezenas_prioritarias):
        """Estratégia Equilibrada: balanceia frequência e diversidade"""
        jogo = set()
        
        # Pega 3 números do ranking
        top = dezenas_prioritarias[:30]
        jogo.update(random.sample(top, min(3, len(top))))
        
        # Pega 2 números de fora do top
        fora_top = [n for n in range(1, 61) if n not in top]
        if fora_top and len(jogo) < 5:
            jogo.update(random.sample(fora_top, min(2, len(fora_top))))
        
        # Completa
        while len(jogo) < 6:
            novo = random.randint(1, 60)
            if novo not in jogo:
                jogo.add(novo)
        
        return sorted(jogo)
    
    def _gerar_diversificada(self, dezenas_prioritarias):
        """Estratégia Diversificada: mistura diferentes tipos"""
        jogo = set()
        
        # Pega 2 do ranking
        top = dezenas_prioritarias[:30]
        jogo.update(random.sample(top, min(2, len(top))))
        
        # Pega 2 atrasados
        atrasados = sorted(self.estatisticas.atrasos.items(), key=lambda x: x[1], reverse=True)[:15]
        atrasados_nums = [n for n, _ in atrasados]
        if atrasados_nums:
            jogo.update(random.sample(atrasados_nums, min(2, len(atrasados_nums))))
        
        # Pega 2 aleatórios
        while len(jogo) < 6:
            novo = random.randint(1, 60)
            if novo not in jogo:
                jogo.add(novo)
        
        return sorted(jogo)

# =====================================================
# MÓDULO 7: BACKTESTS - MEGA
# =====================================================

class BacktestsMega:
    """Módulo 7 - Backtests para Mega-Sena"""
    
    def __init__(self, banco_dados, estatisticas, filtros):
        self.banco = banco_dados
        self.estatisticas = estatisticas
        self.filtros = filtros
    
    def testar_estrategia(self, estrategia='equilibrada', num_testes=50, filtros_personalizados=None):
        """Testa uma estratégia no histórico"""
        if filtros_personalizados is None:
            filtros_personalizados = self.filtros.get_filtros_recomendados()
        
        resultados = []
        historico = self.banco.concursos
        
        # Seleciona concursos para teste
        testes = historico[:min(num_testes, len(historico))]
        
        progress_bar = st.progress(0, text=f"Executando backtest - {estrategia}...")
        
        for i, concurso in enumerate(testes):
            dezenas_reais = concurso['dezenas']
            
            # Gera jogos com a estratégia
            gerador_temp = GeradorPremiumMega(
                self.banco, self.estatisticas, 
                MotorPontuacaoMega(self.estatisticas),
                self.filtros
            )
            
            jogos = gerador_temp.gerar_jogos(
                qtd=10, 
                estrategia=estrategia,
                filtros_personalizados=filtros_personalizados
            )
            
            # Calcula acertos
            for jogo in jogos:
                acertos = len(set(jogo) & set(dezenas_reais))
                resultados.append(acertos)
            
            progress_bar.progress((i + 1) / len(testes))
        
        progress_bar.empty()
        
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
    
    def testar_baseline_aleatorio(self, num_testes=50, qtd_por_teste=10):
        """Baseline de controle: gera jogos 100% aleatórios (sem nenhuma estatística)
        e mede os acertos contra o mesmo histórico. Isso não existia no código original
        e é essencial: só faz sentido dizer que uma estratégia é boa se ela superar
        esta baseline de forma estatisticamente consistente. Para uma loteria justa,
        o esperado é que TODAS as estratégias, incluindo esta, produzam médias
        estatisticamente equivalentes."""
        historico = self.banco.concursos
        testes = historico[:min(num_testes, len(historico))]
        resultados = []

        for concurso in testes:
            dezenas_reais = concurso['dezenas']
            for _ in range(qtd_por_teste):
                jogo = random.sample(range(1, 61), 6)
                resultados.append(len(set(jogo) & set(dezenas_reais)))

        return {
            'estrategia': 'aleatorio_puro',
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
        """Compara múltiplas estratégias, incluindo sempre a baseline aleatória
        como referência de controle."""
        resultados = {}
        for estrategia in estrategias:
            resultados[estrategia] = self.testar_estrategia(estrategia, num_testes)
        resultados['aleatorio_puro'] = self.testar_baseline_aleatorio(num_testes)
        return resultados

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
            if st.button("📥 Carregar Mega-Sena", use_container_width=True):
                with st.spinner("Carregando dados da Mega-Sena..."):
                    dados = buscar_historico_megasena(qtd_concursos)
                    if dados and len(dados) > 0:
                        st.session_state.dados_api = dados
                        
                        # Inicializa módulos
                        st.session_state.banco_dados = BancoDadosMegaInteligente(dados)
                        st.session_state.estatisticas = EstatisticasMegaAvancadas(st.session_state.banco_dados)
                        st.session_state.pontuacao = MotorPontuacaoMega(st.session_state.estatisticas)
                        st.session_state.filtros = FiltrosInteligentesMega(st.session_state.estatisticas)
                        
                        # IA
                        st.session_state.ia = IAEstatisticaMega(st.session_state.banco_dados, st.session_state.estatisticas)
                        
                        st.session_state.gerador = GeradorPremiumMega(
                            st.session_state.banco_dados,
                            st.session_state.estatisticas,
                            st.session_state.pontuacao,
                            st.session_state.filtros,
                            st.session_state.ia
                        )
                        
                        st.session_state.backtests = BacktestsMega(
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
        st.caption("MEGA-SENA Elite 3.0 v1.0")

    # Conteúdo Principal
    if not st.session_state.dados_api:
        st.info("👈 Carregue os dados da Mega-Sena na barra lateral para começar.")
        return

    st.subheader("🎯 MEGA-SENA Elite 3.0 - Sistema Avançado")

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
                st.metric("📊 Média Colunas", f"{stats.media_colunas:.1f}")
            
            # Gráficos interativos
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 📊 Frequência das Dezenas")
                df_freq = pd.DataFrame({
                    'Dezena': range(1, 61),
                    'Frequência': [stats.frequencias.get(i, 0) for i in range(1, 61)]
                })
                fig = px.bar(df_freq, x='Dezena', y='Frequência', title='Frequência por Dezena')
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("### ⏰ Atraso das Dezenas")
                df_atraso = pd.DataFrame({
                    'Dezena': range(1, 61),
                    'Atraso': [stats.atrasos.get(i, 0) for i in range(1, 61)]
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
                top_n = st.slider("Top N dezenas", 5, 60, 20)
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
        <div class="ia-mega-highlight">
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
                                                  "1,2,3,4,5,6,7,8,9,10,11,12")
                        try:
                            dezenas_base = [int(x.strip()) for x in base_input.split(",") if x.strip()]
                            dezenas_base = sorted(dezenas_base)[:15]
                        except:
                            st.warning("Formato inválido. Use números separados por vírgula.")
                with col3:
                    usar_filtros_personalizados = st.checkbox("Filtros personalizados")
                    if usar_filtros_personalizados:
                        pares_min = st.slider("Mínimo Pares", 0, 6, 2)
                        pares_max = st.slider("Máximo Pares", 0, 6, 4)
                        soma_min = st.slider("Soma Mínima", 80, 300, 120)
                        soma_max = st.slider("Soma Máxima", 80, 300, 220)
                        consec_max = st.slider("Máx. Consecutivos", 1, 6, 3)
                        colunas_min = st.slider("Mínimo Colunas", 1, 6, 4)
                        colunas_max = st.slider("Máximo Colunas", 1, 6, 6)
                    else:
                        filtros_recomendados = st.session_state.filtros.get_filtros_recomendados()
                        pares_min = filtros_recomendados['pares_min']
                        pares_max = filtros_recomendados['pares_max']
                        soma_min = filtros_recomendados['soma_min']
                        soma_max = filtros_recomendados['soma_max']
                        consec_max = filtros_recomendados['consecutivos_max']
                        colunas_min = filtros_recomendados['colunas_min']
                        colunas_max = filtros_recomendados['colunas_max']
                
                # Monta filtros
                filtros = {
                    'pares_min': pares_min,
                    'pares_max': pares_max,
                    'soma_min': soma_min,
                    'soma_max': soma_max,
                    'faixa_min': 1,
                    'faixa_max': 4,
                    'consecutivos_max': consec_max,
                    'repetidas_max': 3,
                    'primos_min': 1,
                    'primos_max': 4,
                    'colunas_min': colunas_min,
                    'colunas_max': colunas_max
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
            
            if st.session_state.jogos_gerados:
                jogos = st.session_state.jogos_gerados
                st.markdown(f"### 📋 Jogos Gerados ({len(jogos)})")
                
                # Análise com IA se disponível
                if st.session_state.ia and st.session_state.ia_treinada:
                    st.markdown("#### 🤖 Análise IA dos Jogos")
                    for i, jogo in enumerate(jogos[:10]):
                        probs = st.session_state.ia.prever_probabilidades(jogo)
                        if probs:
                            cols = st.columns([3, 2])
                            with cols[0]:
                                st.markdown(f"**Jogo {i+1}:** {formatar_jogo_html_mega(jogo)}", unsafe_allow_html=True)
                            with cols[1]:
                                for nome, info in probs.items():
                                    st.metric(f"{nome.upper()} Score", f"{info['media']*100:.1f}%")
                
                # Exibição dos jogos
                for i, jogo in enumerate(jogos):
                    medalha = "🏆" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "📌"
                    
                    pares = contar_pares_mega(jogo)
                    primos = contar_primos_mega(jogo)
                    soma = sum(jogo)
                    consec = contar_consecutivos_mega(jogo)
                    faixas = distribuir_faixas_mega(jogo)
                    colunas = distribuir_colunas_mega(jogo)
                    colunas_ativas = len([c for c in colunas if c > 0])
                    
                    stats = f"⚖️ {pares}p/{6-pares}i | 🔢 {primos} primos | ➕ {soma} | 🔗 {consec} consec | 📊 {colunas_ativas} colunas"
                    
                    st.markdown(f"""
                    <div class='card' style='border-left: 5px solid {"#ffd700" if i == 0 else "#4cc9f0"};'>
                        {medalha} <strong>Jogo {i+1:2d}</strong><br>
                        {formatar_jogo_html_mega(jogo)}<br>
                        <small style='color:#aaa;'>{stats}</small>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Botões de ação
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("💾 Salvar Jogos", key="salvar_mega_elite", use_container_width=True):
                        arquivo, jogo_id = salvar_jogos_mega_elite(jogos, {
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
                        'Pares': [contar_pares_mega(j) for j in jogos],
                        'Soma': [sum(j) for j in jogos],
                        'Primos': [contar_primos_mega(j) for j in jogos],
                        'Consecutivos': [contar_consecutivos_mega(j) for j in jogos]
                    })
                    st.download_button(
                        label="📥 Exportar CSV",
                        data=df_export.to_csv(index=False),
                        file_name=f"mega_elite3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                with col3:
                    txt_content = "MEGA-SENA ELITE 3.0 - JOGOS GERADOS\n"
                    txt_content += "=" * 50 + "\n"
                    txt_content += f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
                    txt_content += f"Estratégia: {estrategia}\n"
                    txt_content += f"Total: {len(jogos)} jogos\n\n"
                    
                    for i, jogo in enumerate(jogos):
                        txt_content += f"Jogo {i+1:2d}: {', '.join(f'{d:02d}' for d in jogo)}\n"
                    
                    st.download_button(
                        label="📝 Exportar TXT",
                        data=txt_content,
                        file_name=f"mega_elite3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )

    # ================= TAB 5: BACKTESTS =================
    with tabs[4]:
        st.markdown("### 🔬 Backtests - Teste de Estratégias")
        st.markdown("""
        <div class="mega-highlight">
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
                    default=['conservadora', 'equilibrada', 'diversificada'],
                    help="A baseline 'aleatorio_puro' é sempre incluída automaticamente na comparação."
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

            # Teste de aleatoriedade (qui-quadrado) — não existia na versão anterior
            st.markdown("### 🎲 Teste de Aleatoriedade (Qui-Quadrado)")
            st.markdown("""
            <div class="highlight">
            Testa estatisticamente se as 60 dezenas saem com a mesma probabilidade.
            Para uma loteria oficial e auditada, o esperado é <strong>não rejeitar</strong>
            a hipótese de uniformidade — ou seja, nenhuma dezena é realmente "quente" ou "fria".
            </div>
            """, unsafe_allow_html=True)
            resultado_qui2 = AnaliseCombinatoriaMega.teste_qui_quadrado_uniformidade(
                stats.banco.get_historico_dezenas()
            )
            c1, c2, c3 = st.columns(3)
            c1.metric("Estatística χ²", f"{resultado_qui2['estatistica']:.2f}")
            c2.metric("p-valor", f"{resultado_qui2['p_valor']:.4f}")
            c3.metric("Graus de liberdade", resultado_qui2['graus_liberdade'])
            st.info(resultado_qui2['conclusao'])

            # Probabilidades exatas (hipergeométrica) — não existia na versão anterior
            st.markdown("### 🎯 Probabilidades Exatas por Faixa de Acerto")
            tabela_prob = AnaliseCombinatoriaMega.tabela_probabilidades()
            df_prob = pd.DataFrame([
                {
                    'Acertos': k,
                    'Probabilidade': f"{v['probabilidade']*100:.6f}%",
                    'Chance': f"1 em {v['um_em']:,.0f}".replace(",", ".") if v['um_em'] != float('inf') else "—"
                }
                for k, v in tabela_prob.items()
            ])
            st.dataframe(df_prob, use_container_width=True, hide_index=True)
            st.caption(
                "Estes valores são exatos e constantes — não mudam com histórico, "
                "'atraso' ou tendência, pois cada sorteio é uma extração independente."
            )

            # Análise de Correlação
            st.markdown("### 🔗 Análise de Correlação entre Dezenas")
            
            matriz = np.zeros((60, 60))
            for concurso in stats.banco.concursos:
                dezenas = concurso['dezenas']
                for i in dezenas:
                    for j in dezenas:
                        if i != j:
                            matriz[i-1][j-1] += 1
            
            for i in range(60):
                total = matriz[i].sum()
                if total > 0:
                    matriz[i] = matriz[i] / total
            
            fig = go.Figure(data=go.Heatmap(
                z=matriz,
                x=[f"{i+1:02d}" for i in range(60)],
                y=[f"{i+1:02d}" for i in range(60)],
                colorscale='Viridis'
            ))
            fig.update_layout(title='Matriz de Correlação entre Dezenas',
                            height=600)
            st.plotly_chart(fig, use_container_width=True)
            
            # Análise de Colunas
            st.markdown("### 📊 Análise de Colunas (C1-C6)")
            
            colunas_data = []
            for concurso in stats.banco.concursos[:100]:
                colunas = concurso['colunas']
                colunas_data.append({
                    'Concurso': concurso['numero'],
                    'C1': colunas[0],
                    'C2': colunas[1],
                    'C3': colunas[2],
                    'C4': colunas[3],
                    'C5': colunas[4],
                    'C6': colunas[5]
                })
            
            df_colunas = pd.DataFrame(colunas_data)
            fig = px.bar(df_colunas.melt(id_vars=['Concurso']), 
                        x='Concurso', y='value', color='variable',
                        title='Distribuição por Colunas (Últimos 100 Concursos)')
            st.plotly_chart(fig, use_container_width=True)

    # ================= TAB 7: SALVOS =================
    with tabs[6]:
        st.markdown("### 💾 Jogos Salvos")
        
        jogos_salvos = carregar_jogos_mega_elite()
        
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
    <div class="footer-title">MEGA-SENA ELITE 3.0 SYSTEM</div>
    <div class="footer-sub">SAMUCJ TECNOLOGIA © 2026</div>
</div>
""", unsafe_allow_html=True)
