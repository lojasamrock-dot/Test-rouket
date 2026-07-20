import streamlit as st
import requests
import random
import pandas as pd
import numpy as np
import json
import os
import uuid
import math
from collections import Counter
from datetime import datetime
from scipy.stats import norm, binom
from itertools import combinations
import warnings
warnings.filterwarnings("ignore")

try:
    from ortools.linear_solver import pywraplp
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False

st.set_page_config(
    page_title="🎯 MEGA-SENA - Análise e Geração",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
.block-container { padding-top: 1rem; padding-bottom: 2rem; }
h1,h2,h3 { text-align: center; }
.card { background: #0e1117; border-radius: 14px; padding: 16px; margin-bottom: 12px; border: 1px solid #262730; color: white; }
.stButton>button { width: 100%; height: 3.2em; border-radius: 14px; font-size: 1.05em; }
input, textarea { border-radius: 12px !important; }
.p12 { color: #4cc9f0; font-weight: bold; }
.p13 { color: #4ade80; font-weight: bold; }
.p14 { color: gold; font-weight: bold; }
.p15 { color: #f97316; font-weight: bold; }
.concurso-info { background: #1e1e2e; padding: 10px; border-radius: 10px; margin: 10px 0; }
.metric-card { background: #16213e; padding: 10px; border-radius: 10px; text-align: center; }
.cover-stats { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 15px; border-radius: 12px; margin: 10px 0; border: 1px solid #00ffaa20; }
.highlight { background: #00ffaa20; border-left: 4px solid #00ffaa; padding: 10px; border-radius: 8px; margin: 10px 0; }
.ilp-highlight { background: linear-gradient(135deg, #ff00ff20 0%, #aa00ff20 100%); border: 2px solid #ff00ff; padding: 15px; border-radius: 12px; margin: 10px 0; }
.ia7-highlight { background: linear-gradient(135deg, #ff880020 0%, #ff440020 100%); border: 2px solid #ff8800; padding: 15px; border-radius: 12px; margin: 10px 0; }
.nash-highlight { background: linear-gradient(135deg, #9b59b620 0%, #6c348320 100%); border: 2px solid #9b59b6; padding: 15px; border-radius: 12px; margin: 10px 0; }
.ev-highlight { background: linear-gradient(135deg, #00ff8820 0%, #00cc6620 100%); border: 2px solid #00ff88; padding: 15px; border-radius: 12px; margin: 10px 0; }
.img-analysis-highlight { background: linear-gradient(135deg, #ffd70020 0%, #ff8c0020 100%); border: 2px solid #ffd700; padding: 15px; border-radius: 12px; margin: 10px 0; }
.elite-master-highlight { background: linear-gradient(135deg, #ff880030 0%, #ff440030 100%); border: 2px solid #ff8800; padding: 15px; border-radius: 12px; margin: 10px 0; }
.regras-especiais-highlight { background: linear-gradient(135deg, #4cc9f030 0%, #f9731630 100%); border: 2px solid #4cc9f0; padding: 15px; border-radius: 12px; margin: 10px 0; }
.abc-highlight { background: linear-gradient(135deg, #4cc9f030 0%, #f9731630 50%, #00ff8830 100%); border: 2px solid #4cc9f0; padding: 15px; border-radius: 12px; margin: 10px 0; }
.v4-highlight { background: linear-gradient(135deg, #ff6b6b30 0%, #4ecdc430 50%, #45b7d130 100%); border: 2px solid #ff6b6b; padding: 15px; border-radius: 12px; margin: 10px 0; }
.download-section { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 20px; border-radius: 15px; margin: 20px 0; border: 2px solid #00ffaa; text-align: center; }
.download-btn { background: linear-gradient(90deg, #00ffaa, #00cc88); color: #000; padding: 12px 30px; border-radius: 25px; font-weight: bold; border: none; cursor: pointer; }
.jogo-v4-principal { border-left: 5px solid #4cc9f0; background: #0e1117; border-radius: 10px; padding: 15px; margin-bottom: 10px; }
.jogo-v4-protecao { border-left: 5px solid #f97316; background: #0e1117; border-radius: 10px; padding: 15px; margin-bottom: 10px; }
.jogo-v4-destaque { border-left: 5px solid #ffd700; background: #0e1117; border-radius: 10px; padding: 15px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("📊🎯 MEGA-SENA - Análise e Geração")
st.caption("Análise Estatística e Geração de Jogos com Filtros Matemáticos")

# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================

def garantir_jogos_como_listas(jogos_entrada):
    if jogos_entrada is None:
        return []
    if isinstance(jogos_entrada, list) and len(jogos_entrada) > 0:
        if isinstance(jogos_entrada[0], list) and all(isinstance(n, int) for n in jogos_entrada[0]):
            return jogos_entrada
    jogos_normalizados = []
    if isinstance(jogos_entrada, pd.DataFrame):
        for _, row in jogos_entrada.iterrows():
            for col in row.index:
                valor = row[col]
                if isinstance(valor, str) and ("," in valor or " " in valor):
                    if "," in valor:
                        dezenas = [int(d.strip()) for d in valor.split(",")]
                    else:
                        dezenas = [int(d) for d in valor.split()]
                    jogos_normalizados.append(sorted(dezenas))
                    break
                elif isinstance(valor, list):
                    jogos_normalizados.append(sorted([int(x) for x in valor]))
                    break
        return jogos_normalizados
    if isinstance(jogos_entrada, list):
        for item in jogos_entrada:
            if isinstance(item, dict):
                for chave in ["Dezenas", "dezenas", "Jogo", "jogo"]:
                    if chave in item:
                        valor = item[chave]
                        if isinstance(valor, str):
                            if "," in valor:
                                dezenas = [int(d.strip()) for d in valor.split(",")]
                            else:
                                dezenas = [int(d) for d in valor.split()]
                        elif isinstance(valor, list):
                            dezenas = [int(x) for x in valor]
                        else:
                            continue
                        jogos_normalizados.append(sorted(dezenas))
                        break
            elif isinstance(item, str):
                if "," in item:
                    dezenas = [int(d.strip()) for d in item.split(",")]
                else:
                    dezenas = [int(d) for d in item.split()]
                jogos_normalizados.append(sorted(dezenas))
            elif isinstance(item, (list, tuple)):
                jogos_normalizados.append(sorted([int(x) for x in item]))
    return jogos_normalizados

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

def salvar_jogos_gerados(jogos, fechamento, dna_params, numero_concurso_atual, data_concurso_atual, estatisticas=None):
    try:
        if not os.path.exists("jogos_salvos"):
            os.makedirs("jogos_salvos")
        jogo_id = str(uuid.uuid4())[:8]
        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"jogos_salvos/jogos_{data_hora}_{jogo_id}.json"
        jogos_convertidos = convert_numpy_types(jogos)
        dados = {
            "id": jogo_id,
            "data_geracao": datetime.now().isoformat(),
            "concurso_base": {"numero": int(numero_concurso_atual), "data": str(data_concurso_atual)},
            "jogos": jogos_convertidos,
            "estatisticas": convert_numpy_types(estatisticas) if estatisticas else {},
            "schema_version": "2.0"
        }
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        return nome_arquivo, jogo_id
    except Exception as e:
        st.error(f"Erro ao salvar jogos: {e}")
        return None, None

def carregar_jogos_salvos():
    jogos_salvos = []
    try:
        if os.path.exists("jogos_salvos"):
            for arquivo in os.listdir("jogos_salvos"):
                if arquivo.endswith(".json"):
                    try:
                        with open(f"jogos_salvos/{arquivo}", 'r', encoding='utf-8') as f:
                            dados = json.load(f)
                            if "concurso_base" not in dados:
                                dados["concurso_base"] = {"numero": 0, "data": "Desconhecido"}
                            dados["arquivo"] = arquivo
                            jogos_salvos.append(dados)
                    except Exception:
                        continue
            jogos_salvos.sort(key=lambda x: x.get("data_geracao", ""), reverse=True)
    except Exception as e:
        st.error(f"Erro ao carregar jogos salvos: {e}")
    return jogos_salvos

def formatar_jogo_html(jogo, destaque_primos=True):
    primos = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59]
    if isinstance(jogo, dict):
        dezenas = []
        for chave in ["dezenas", "Dezenas", "jogo", "Jogo"]:
            if chave in jogo:
                val = jogo[chave]
                if isinstance(val, str):
                    dezenas = [int(d.strip()) for d in val.split(",") if d.strip()]
                elif isinstance(val, list):
                    dezenas = [int(d) for d in val]
                break
    elif isinstance(jogo, str):
        if "," in jogo:
            dezenas = [int(d.strip()) for d in jogo.split(",")]
        else:
            dezenas = [int(d) for d in jogo.split()]
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

def contar_pares(jogo):
    return sum(1 for d in jogo if d % 2 == 0)

def contar_primos(jogo):
    primos = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59}
    return sum(1 for d in jogo if d in primos)

def contar_consecutivos(jogo):
    jogo = sorted(jogo)
    return sum(1 for i in range(len(jogo)-1) if jogo[i+1] == jogo[i] + 1)

def contar_por_faixa(jogo, faixa_limites):
    contagem = []
    for inicio, fim in faixa_limites:
        contagem.append(sum(1 for n in jogo if inicio <= n <= fim))
    return contagem

def distribuir_por_linhas(jogo, linhas=6):
    resultado = [0] * linhas
    for n in jogo:
        resultado[(n-1)//10] += 1
    return resultado

def distribuir_por_colunas(jogo):
    colunas = [0] * 10
    for n in jogo:
        colunas[(n-1)%10] += 1
    return colunas

# =====================================================
# FUNÇÃO PARA BUSCAR DADOS DA API COMPLETA
# =====================================================

def buscar_dados_loterias():
    """
    Busca todos os dados das loterias da API
    Retorna os dados da Mega-Sena especificamente
    """
    try:
        url = "https://loteriascaixa-api.herokuapp.com/api/v1/loterias"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            dados_completos = response.json()
            
            # Verifica se a Mega-Sena está nos dados
            if 'megasena' in dados_completos:
                dados_mega = dados_completos['megasena']
                
                # Converte para o formato esperado (lista de concursos)
                # A API retorna o último concurso, precisamos buscar o histórico
                return buscar_historico_megasena()
            else:
                st.warning("⚠️ Mega-Sena não encontrada na resposta da API")
                return None
        else:
            st.error(f"❌ Erro ao buscar dados: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"❌ Erro na requisição: {e}")
        return None

def buscar_historico_megasena(quantidade=100):
    """
    Busca o histórico de concursos da Mega-Sena
    """
    try:
        # Busca lista de concursos
        url_lista = "https://loteriascaixa-api.herokuapp.com/api/megasena"
        response = requests.get(url_lista, timeout=10)
        
        if response.status_code == 200:
            dados = response.json()
            
            # Se for uma lista, retorna os últimos 'quantidade'
            if isinstance(dados, list):
                return dados[:quantidade]
            # Se for um único concurso, retorna como lista
            elif isinstance(dados, dict):
                return [dados]
            else:
                return None
        else:
            # Fallback: busca concurso específico
            return buscar_concurso_especifico()
    except Exception as e:
        st.error(f"❌ Erro ao buscar histórico: {e}")
        return None

def buscar_concurso_especifico(numero=None):
    """
    Busca um concurso específico da Mega-Sena
    """
    try:
        if numero:
            url = f"https://loteriascaixa-api.herokuapp.com/api/megasena/{numero}"
        else:
            # Busca o último concurso
            url = "https://loteriascaixa-api.herokuapp.com/api/megasena/latest"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            dados = response.json()
            if isinstance(dados, dict):
                return [dados]
        return None
    except Exception as e:
        st.error(f"❌ Erro ao buscar concurso específico: {e}")
        return None

# =====================================================
# MEGA-SENA VERSÃO 4 - GERADOR INTELIGENTE
# =====================================================

class GeradorMegaSenaV4:
    """
    Versão 4 do gerador da Mega-Sena
    Baseado em análise de colunas e padrões históricos
    """
    
    def __init__(self, dados_api, qtd_concursos=50):
        self.dados_api = dados_api
        self.qtd_concursos = min(qtd_concursos, len(dados_api))
        
        # Definição das colunas (6 colunas de 10 números cada)
        self.colunas = {
            'C1': list(range(1, 11)),
            'C2': list(range(11, 21)),
            'C3': list(range(21, 31)),
            'C4': list(range(31, 41)),
            'C5': list(range(41, 51)),
            'C6': list(range(51, 61))
        }
        
        # Lista de números primos para destaque
        self.primos = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59}
        
        # Processa concursos
        self.concursos = []
        for concurso in dados_api[:self.qtd_concursos]:
            if 'dezenas' in concurso:
                dezenas = sorted(map(int, concurso['dezenas']))
                self.concursos.append(dezenas)
        
        self.ultimo_concurso = self.concursos[0] if self.concursos else []
        
        # Calcula frequências e análises
        self.frequencias = self._calcular_frequencias()
        self.atrasos = self._calcular_atrasos()
        self.analise_colunas = self._analisar_colunas()
        
    def _calcular_frequencias(self):
        freq = Counter()
        for concurso in self.concursos:
            freq.update(concurso)
        return freq
    
    def _calcular_atrasos(self):
        atrasos = {i: 0 for i in range(1, 61)}
        if not self.concursos:
            return atrasos
        for dezena in range(1, 61):
            atraso = 0
            for concurso in self.concursos:
                if dezena in concurso:
                    break
                atraso += 1
            atrasos[dezena] = atraso
        return atrasos
    
    def _analisar_colunas(self):
        """Analisa frequência de cada coluna nos últimos concursos"""
        contagem = {col: 0 for col in self.colunas}
        for concurso in self.concursos[:20]:  # Últimos 20 concursos
            for dezena in concurso:
                for col, intervalo in self.colunas.items():
                    if dezena in intervalo:
                        contagem[col] += 1
                        break
        
        # Ordena colunas por frequência
        colunas_ordenadas = sorted(contagem.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'contagem': contagem,
            'colunas_mais_frequentes': colunas_ordenadas,
            'coluna_principal': colunas_ordenadas[0][0] if colunas_ordenadas else 'C3',
            'coluna_apoio1': colunas_ordenadas[1][0] if len(colunas_ordenadas) > 1 else 'C4',
            'coluna_apoio2': colunas_ordenadas[2][0] if len(colunas_ordenadas) > 2 else 'C6'
        }
    
    def get_dezenas_por_coluna(self, coluna, quantidade, usar_frequentes=True):
        """Retorna dezenas específicas de uma coluna"""
        if coluna not in self.colunas:
            return []
        
        numeros_coluna = self.colunas[coluna]
        
        if usar_frequentes:
            # Pega números mais frequentes nesta coluna
            numeros_com_freq = [(n, self.frequencias.get(n, 0)) for n in numeros_coluna]
            numeros_com_freq.sort(key=lambda x: x[1], reverse=True)
            numeros_ordenados = [n for n, _ in numeros_com_freq]
        else:
            numeros_ordenados = numeros_coluna.copy()
            random.shuffle(numeros_ordenados)
        
        # Seleciona os primeiros 'quantidade' números
        selecionados = numeros_ordenados[:min(quantidade, len(numeros_ordenados))]
        
        # Se não tiver números suficientes, completa com aleatórios
        if len(selecionados) < quantidade:
            disponiveis = [n for n in numeros_coluna if n not in selecionados]
            if disponiveis:
                extras = random.sample(disponiveis, min(quantidade - len(selecionados), len(disponiveis)))
                selecionados.extend(extras)
        
        return sorted(selecionados)
    
    def criar_jogo(self, configuracao_colunas, usar_frequentes=True):
        """Cria um jogo baseado na configuração de colunas"""
        dezenas = []
        
        for coluna, quantidade in configuracao_colunas:
            numeros = self.get_dezenas_por_coluna(coluna, quantidade, usar_frequentes)
            dezenas.extend(numeros)
        
        # Remove duplicatas e ordena
        dezenas = sorted(list(set(dezenas)))
        
        # Se tiver mais de 6, corta
        if len(dezenas) > 6:
            dezenas = dezenas[:6]
        # Se tiver menos de 6, completa
        elif len(dezenas) < 6:
            todos_numeros = set(range(1, 61))
            usados = set(dezenas)
            disponiveis = list(todos_numeros - usados)
            if disponiveis:
                extras = random.sample(disponiveis, min(6 - len(dezenas), len(disponiveis)))
                dezenas.extend(extras)
                dezenas.sort()
        
        return dezenas
    
    def gerar_jogos_principais(self, qtd=10):
        """Gera os 10 jogos principais baseados na Versão 4"""
        coluna_principal = self.analise_colunas['coluna_principal']
        coluna_apoio1 = self.analise_colunas['coluna_apoio1']
        coluna_apoio2 = self.analise_colunas['coluna_apoio2']
        
        # Configuração dos jogos principais
        configs = [
            # Jogo 1: Base C3 + C6
            [(coluna_principal, 2), (coluna_apoio1, 1), (coluna_apoio2, 2), ('C1', 1)],
            # Jogo 2: Base C3 + C4
            [('C1', 1), (coluna_apoio1, 2), (coluna_principal, 2), ('C5', 1)],
            # Jogo 3: Base C3 + C4 + C6
            [(coluna_principal, 2), (coluna_apoio1, 2), (coluna_apoio2, 1), ('C1', 1)],
            # Jogo 4: Equilibrado
            [('C1', 2), (coluna_apoio2, 2), (coluna_principal, 1), (coluna_apoio1, 1)],
            # Jogo 5: Reforço C3
            [('C1', 1), (coluna_principal, 2), (coluna_apoio1, 1), (coluna_apoio2, 1), ('C5', 1)],
            # Jogo 6: Reforço C6
            [(coluna_principal, 1), (coluna_apoio2, 2), ('C1', 1), (coluna_apoio1, 1), ('C5', 1)],
            # Jogo 7: Miolo
            [('C5', 1), (coluna_apoio2, 1), (coluna_principal, 2), (coluna_apoio1, 1), ('C1', 1)],
            # Jogo 8: C1 + C6
            [(coluna_apoio2, 2), ('C1', 2), (coluna_apoio1, 1), (coluna_principal, 1)],
            # Jogo 9: Diversificado
            [('C5', 1), (coluna_apoio1, 1), (coluna_principal, 1), (coluna_apoio2, 2), ('C1', 1)],
            # Jogo 10: Fechamento
            [(coluna_apoio2, 1), ('C5', 1), ('C1', 1), (coluna_principal, 2), (coluna_apoio1, 1)]
        ]
        
        jogos = []
        for config in configs[:qtd]:
            jogo = self.criar_jogo(config, usar_frequentes=True)
            jogos.append(jogo)
        
        return jogos
    
    def gerar_jogos_protecao(self, qtd=5):
        """Gera os 5 jogos de proteção"""
        coluna_principal = self.analise_colunas['coluna_principal']
        coluna_apoio1 = self.analise_colunas['coluna_apoio1']
        coluna_apoio2 = self.analise_colunas['coluna_apoio2']
        
        configs = [
            # Proteção 1: C2
            [(coluna_principal, 2), ('C2', 1), ('C5', 1), (coluna_apoio1, 1), (coluna_apoio2, 1)],
            # Proteção 2: C2 + C5
            [('C2', 1), (coluna_principal, 2), (coluna_apoio1, 1), ('C5', 1), (coluna_apoio2, 1)],
            # Proteção 3: Cobertura total
            [('C2', 1), (coluna_principal, 1), (coluna_apoio1, 1), ('C1', 1), (coluna_apoio2, 1), ('C5', 1)],
            # Proteção 4: Reforço C2
            [(coluna_apoio1, 1), (coluna_apoio2, 1), ('C5', 1), ('C2', 2), (coluna_principal, 1)],
            # Proteção 5: Cobertura ampla
            [('C1', 1), ('C2', 1), (coluna_principal, 1), (coluna_apoio1, 1), ('C5', 1), (coluna_apoio2, 1)]
        ]
        
        jogos = []
        for config in configs[:qtd]:
            jogo = self.criar_jogo(config, usar_frequentes=True)
            jogos.append(jogo)
        
        return jogos
    
    def gerar_todos_jogos(self):
        """Gera todos os 15 jogos (10 principais + 5 proteção)"""
        principais = self.gerar_jogos_principais(10)
        protecao = self.gerar_jogos_protecao(5)
        
        return {
            'principais': principais,
            'protecao': protecao,
            'todos': principais + protecao
        }
    
    def analisar_jogo(self, jogo):
        """Analisa um jogo e retorna estatísticas"""
        if not jogo or len(jogo) != 6:
            return None
        
        # Contagem por coluna
        colunas_contagem = {col: 0 for col in self.colunas}
        for num in jogo:
            for col, intervalo in self.colunas.items():
                if num in intervalo:
                    colunas_contagem[col] += 1
                    break
        
        colunas_ativas = [col for col, qtd in colunas_contagem.items() if qtd > 0]
        
        return {
            'jogo': jogo,
            'pares': contar_pares(jogo),
            'impares': 6 - contar_pares(jogo),
            'primos': contar_primos(jogo),
            'soma': sum(jogo),
            'consecutivos': contar_consecutivos(jogo),
            'colunas_ativas': colunas_ativas,
            'quantidade_colunas': len(colunas_ativas),
            'colunas_contagem': colunas_contagem,
            'repetidas_ultimo': len(set(jogo) & set(self.ultimo_concurso)) if self.ultimo_concurso else 0
        }
    
    def get_recomendacoes_prioridade(self):
        """Retorna recomendações de prioridade dos jogos"""
        return {
            'prioridade_maxima': [0, 1, 2, 3, 7, 9],  # Jogos 1,2,3,4,8,10
            'prioridade_media': [4, 5, 6, 8],  # Jogos 5,6,7,9
            'protecao': [10, 11, 12, 13, 14]  # Proteções 1-5
        }
    
    def get_planos_jogo(self):
        """Retorna planos de jogo"""
        return {
            'economico': ['Jogo 1', 'Jogo 2', 'Jogo 3', 'Jogo 8'],
            'intermediario': ['Jogo 1', 'Jogo 2', 'Jogo 3', 'Jogo 4', 'Jogo 5', 'Jogo 8', 'Jogo 10', 'Proteção 1'],
            'completo': 'Todos os 15 jogos'
        }

# =====================================================
# FUNÇÕES DE DOWNLOAD
# =====================================================

def gerar_csv_download_mega(jogos, scores=None, estrategia="Padrão"):
    dados_export = []
    for i, jogo in enumerate(jogos):
        linha = {
            "Jogo": i + 1,
            "Dezenas": ", ".join(f"{n:02d}" for n in sorted(jogo)),
            "Pares": contar_pares(jogo),
            "Ímpares": 6 - contar_pares(jogo),
            "Primos": contar_primos(jogo),
            "Soma": sum(jogo),
            "Consecutivos": contar_consecutivos(jogo)
        }
        if scores and i < len(scores):
            if isinstance(scores[i], dict):
                linha["Score"] = scores[i].get("score_ajustado", scores[i].get("score", 0))
            else:
                linha["Score"] = scores[i]
        dados_export.append(linha)
    return pd.DataFrame(dados_export)

def detectar_estrategia_ativa_mega():
    if "v4_jogos" in st.session_state and st.session_state.v4_jogos:
        return "Mega-Sena V4"
    return "Padrão"

def conferir_jogos_mega(jogos, resultado_set):
    resultados = []
    for i, jogo in enumerate(jogos):
        if isinstance(jogo, str):
            dezenas = set(map(int, jogo.replace('"', '').replace(' ', '').split(',')))
        else:
            dezenas = set(jogo)
        acertos = dezenas.intersection(resultado_set)
        resultados.append({
            "Jogo": i + 1,
            "Acertos": len(acertos),
            "Acertos_Dezenas": sorted(acertos),
            "Dezenas": sorted(dezenas)
        })
    df = pd.DataFrame(resultados)
    return df.sort_values(by="Acertos", ascending=False).reset_index(drop=True)

# =====================================================
# INTERFACE PRINCIPAL
# =====================================================

def main():
    if "analise" not in st.session_state: st.session_state.analise = None
    if "jogos" not in st.session_state: st.session_state.jogos = []
    if "dados_api" not in st.session_state: st.session_state.dados_api = None
    if "jogos_salvos" not in st.session_state: st.session_state.jogos_salvos = []
    if "v4_jogos" not in st.session_state: st.session_state.v4_jogos = None
    if "v4_gerador" not in st.session_state: st.session_state.v4_gerador = None
    if "v4_scores" not in st.session_state: st.session_state.v4_scores = []
    if "v4_analise_detalhada" not in st.session_state: st.session_state.v4_analise_detalhada = []
    if "ultimo_concurso_info" not in st.session_state: st.session_state.ultimo_concurso_info = None

    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # Opção para carregar dados
        qtd = st.slider("Qtd concursos históricos", 20, 200, 100)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Carregar Mega-Sena", use_container_width=True):
                with st.spinner("Carregando dados da Mega-Sena..."):
                    # Tenta carregar da API completa primeiro
                    dados = buscar_historico_megasena(qtd)
                    
                    if dados is None:
                        # Fallback: tenta carregar da API específica
                        st.info("Tentando carregar da API específica...")
                        try:
                            url = "https://loteriascaixa-api.herokuapp.com/api/megasena"
                            response = requests.get(url, timeout=10)
                            if response.status_code == 200:
                                dados = response.json()
                                if isinstance(dados, list):
                                    dados = dados[:qtd]
                                elif isinstance(dados, dict):
                                    dados = [dados]
                        except Exception as e:
                            st.error(f"Erro ao carregar: {e}")
                    
                    if dados and len(dados) > 0:
                        st.session_state.dados_api = dados
                        
                        # Extrai informações do último concurso
                        ultimo = dados[0] if isinstance(dados, list) else dados
                        st.session_state.ultimo_concurso_info = {
                            'numero': ultimo.get('concurso', ultimo.get('numeroDoConcurso', 'N/A')),
                            'data': ultimo.get('data', ultimo.get('dataApuracao', 'N/A')),
                            'dezenas': ultimo.get('dezenas', [])
                        }
                        
                        # Inicializa gerador
                        st.session_state.v4_gerador = GeradorMegaSenaV4(dados, qtd)
                        st.success(f"✅ Carregados {len(dados)} concursos!")
                        st.success(f"📅 Último: #{st.session_state.ultimo_concurso_info['numero']} - {st.session_state.ultimo_concurso_info['data']}")
                    else:
                        st.error("❌ Não foi possível carregar os dados")
        
        with col2:
            if st.button("🔄 Atualizar Dados", use_container_width=True):
                with st.spinner("Atualizando dados..."):
                    try:
                        url = "https://loteriascaixa-api.herokuapp.com/api/megasena"
                        response = requests.get(url, timeout=10)
                        if response.status_code == 200:
                            dados = response.json()
                            if isinstance(dados, list):
                                dados = dados[:qtd]
                            elif isinstance(dados, dict):
                                dados = [dados]
                            
                            if dados and len(dados) > 0:
                                st.session_state.dados_api = dados
                                st.session_state.v4_gerador = GeradorMegaSenaV4(dados, qtd)
                                st.success(f"✅ Dados atualizados! {len(dados)} concursos")
                    except Exception as e:
                        st.error(f"Erro ao atualizar: {e}")

    # Exibe informações do último concurso se disponível
    if st.session_state.ultimo_concurso_info:
        info = st.session_state.ultimo_concurso_info
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**📅 Último Concurso:** #{info['numero']}")
        st.sidebar.markdown(f"**📆 Data:** {info['data']}")
        if info['dezenas']:
            dezenas = sorted(map(int, info['dezenas']))
            st.sidebar.markdown(f"**🎯 Resultado:** {', '.join(f'{d:02d}' for d in dezenas)}")

    if not st.session_state.dados_api:
        st.info("👈 Carregue os dados da Mega-Sena na barra lateral para começar.")
        return

    st.subheader("🎯 Análise e Geração de Jogos")

    # Criar abas
    tabs = st.tabs([
        "📊 Análise",
        "🎲 Gerador",
        "🔍 Conferência",
        "📈 Avaliação",
        "✅ Salvos",
        "🎯 V4 MEGA-SENA"
    ])

    # ================= TAB 1: ANÁLISE =================
    with tabs[0]:
        if st.session_state.dados_api:
            ultimo = st.session_state.dados_api[0]
            numeros_ultimo = sorted(map(int, ultimo['dezenas']))
            st.markdown(f"""
            <div class='concurso-info'>
                <strong>Concurso #{ultimo.get('concurso', ultimo.get('numeroDoConcurso', 'N/A'))}</strong> - {ultimo.get('data', ultimo.get('dataApuracao', 'N/A'))}
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**Dezenas sorteadas:**")
                st.markdown(formatar_jogo_html(numeros_ultimo), unsafe_allow_html=True)
            with col2:
                pares = contar_pares(numeros_ultimo)
                st.metric("Pares/Ímpares", f"{pares}×{6-pares}")
            with col3:
                st.metric("Soma total", sum(numeros_ultimo))
            
            st.markdown("### 📊 Estatísticas do Último Concurso")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Primos", contar_primos(numeros_ultimo))
            with col2:
                st.metric("Consecutivos", contar_consecutivos(numeros_ultimo))
            with col3:
                faixas = [(1, 20), (21, 40), (41, 60)]
                contagem = contar_por_faixa(numeros_ultimo, faixas)
                st.metric("Distribuição (B/M/A)", f"{contagem[0]}/{contagem[1]}/{contagem[2]}")
            with col4:
                linhas = distribuir_por_linhas(numeros_ultimo, 6)
                st.metric("Linhas (0-5)", f"{linhas[0]}-{linhas[1]}-{linhas[2]}-{linhas[3]}-{linhas[4]}-{linhas[5]}")

    # ================= TAB 2: GERADOR =================
    with tabs[1]:
        st.markdown("### 🎲 Gerador de Jogos da Mega-Sena")
        st.caption("Geração aleatória com filtros básicos")
        
        col1, col2 = st.columns(2)
        with col1:
            qtd_jogos = st.slider("Quantidade de jogos", 1, 20, 5)
        with col2:
            if st.button("🚀 GERAR JOGOS", use_container_width=True):
                with st.spinner(f"Gerando {qtd_jogos} jogos..."):
                    jogos = []
                    for _ in range(qtd_jogos * 3):
                        jogo = sorted(random.sample(range(1, 61), 6))
                        if jogo not in jogos:
                            jogos.append(jogo)
                        if len(jogos) >= qtd_jogos:
                            break
                    st.session_state.jogos = jogos
                    st.success(f"✅ {len(jogos)} jogos gerados!")
        
        if st.session_state.jogos:
            st.markdown(f"### 📋 Jogos Gerados ({len(st.session_state.jogos)})")
            for i, jogo in enumerate(st.session_state.jogos):
                st.markdown(f"""
                <div style='border-left: 5px solid #4cc9f0; background:#0e1117; border-radius:10px; padding:15px; margin-bottom:10px;'>
                    <strong>Jogo {i+1:2d}</strong><br>
                    {formatar_jogo_html(jogo)}
                </div>
                """, unsafe_allow_html=True)

    # ================= TAB 3: CONFERÊNCIA =================
    with tabs[2]:
        st.markdown("### 🔍 Conferência de Jogos")
        
        if st.session_state.dados_api:
            concurso_resultado = st.selectbox(
                "Selecione o concurso para conferência", 
                st.session_state.dados_api, 
                format_func=lambda c: f"#{c.get('concurso', c.get('numeroDoConcurso', 'N/A'))} - {c.get('data', c.get('dataApuracao', 'N/A'))}"
            )
            if concurso_resultado:
                resultado_oficial = set(map(int, concurso_resultado["dezenas"]))
                st.markdown(f"""<div class="highlight"><strong>🎯 Resultado #{concurso_resultado.get('concurso', concurso_resultado.get('numeroDoConcurso', 'N/A'))}:</strong><br>{formatar_jogo_html(sorted(resultado_oficial))}</div>""", unsafe_allow_html=True)
        
        opcao_jogos = st.radio("Origem dos jogos:", ["Jogos gerados na sessão atual", "Carregar de arquivo CSV", "Digitar manualmente"], horizontal=True)
        jogos_para_conferir = []
        
        if opcao_jogos == "Jogos gerados na sessão atual":
            if st.session_state.jogos:
                jogos_para_conferir = st.session_state.jogos
                st.info(f"{len(jogos_para_conferir)} jogos carregados da sessão atual")
        elif opcao_jogos == "Carregar de arquivo CSV":
            uploaded_file = st.file_uploader("Escolha um arquivo CSV", type="csv")
            if uploaded_file:
                df_carregado = pd.read_csv(uploaded_file)
                if "Dezenas" in df_carregado.columns:
                    jogos_para_conferir = df_carregado["Dezenas"].tolist()
        else:
            jogos_texto = st.text_area("Digite os jogos (um por linha, números separados por vírgula)", placeholder="1,2,3,4,5,6")
            if jogos_texto:
                for linha in jogos_texto.strip().split('\n'):
                    if linha.strip():
                        try:
                            dezenas = [int(n.strip()) for n in linha.split(',')]
                            if len(dezenas) == 6 and all(1 <= n <= 60 for n in dezenas):
                                jogos_para_conferir.append(sorted(dezenas))
                        except:
                            pass
        
        if jogos_para_conferir and 'resultado_oficial' in locals():
            if st.button("🔍 CONFERIR JOGOS", use_container_width=True, type="primary"):
                df_conferencia = conferir_jogos_mega(jogos_para_conferir, resultado_oficial)
                st.markdown("### 📊 Resultados da Conferência")
                col1, col2, col3, col4 = st.columns(4)
                with col1: st.metric("Total Jogos", len(df_conferencia))
                with col2: st.metric("Melhor Acerto", df_conferencia.iloc[0]["Acertos"])
                with col3: st.metric("Média Acertos", round(df_conferencia["Acertos"].mean(), 1))
                with col4: st.metric("Jogos com 4+", len(df_conferencia[df_conferencia["Acertos"] >= 4]))
                
                for i, row in df_conferencia.head(20).iterrows():
                    medalha = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "📌"
                    st.markdown(f"""
                    <div style='border-left: 5px solid {"#ffd700" if i == 0 else "#c0c0c0" if i == 1 else "#cd7f32" if i == 2 else "#4cc9f0"}; background:#0e1117; border-radius:10px; padding:12px; margin-bottom:8px;'>
                        {medalha} <strong>Jogo {row['Jogo']}</strong> — <span style='color:#00ffaa;'>{row['Acertos']} acertos</span><br>
                        {formatar_jogo_html(row['Dezenas'])}
                    </div>
                    """, unsafe_allow_html=True)

    # ================= TAB 4: AVALIAÇÃO =================
    with tabs[3]:
        st.markdown("### 📈 Avaliação Estatística dos Jogos")
        if st.session_state.jogos:
            avaliacao = []
            for i, jogo in enumerate(st.session_state.jogos):
                avaliacao.append({
                    "Jogo": i+1,
                    "Pares": contar_pares(jogo),
                    "Ímpares": 6 - contar_pares(jogo),
                    "Primos": contar_primos(jogo),
                    "Soma": sum(jogo),
                    "Consecutivos": contar_consecutivos(jogo)
                })
            df_avaliacao = pd.DataFrame(avaliacao)
            st.dataframe(df_avaliacao, use_container_width=True, hide_index=True)
        else:
            st.info("Gere jogos primeiro na aba 'Gerador'")

    # ================= TAB 5: SALVOS =================
    with tabs[4]:
        st.markdown("### ✅ Jogos Salvos")
        st.session_state.jogos_salvos = carregar_jogos_salvos()
        if not st.session_state.jogos_salvos:
            st.warning("Nenhum jogo salvo encontrado.")
        else:
            for jogo_salvo in st.session_state.jogos_salvos[:10]:
                st.markdown(f"""
                <div style='background:#0e1117; border:1px solid #262730; border-radius:10px; padding:10px; margin-bottom:8px;'>
                    <strong>ID:</strong> {jogo_salvo['id']} | <strong>Concurso:</strong> #{jogo_salvo['concurso_base']['numero']}
                </div>
                """, unsafe_allow_html=True)

    # ================= TAB 6: V4 MEGA-SENA =================
    with tabs[5]:
        st.markdown("### 🎯 MEGA-SENA V4 - Fechamento Inteligente")
        st.markdown("""
        <div class="v4-highlight">
            <strong>🎯 ESTRATÉGIA V4:</strong><br>
            • 10 jogos principais seguindo o padrão de colunas<br>
            • 5 jogos de proteção para cobertura de viradas<br>
            • Baseado em análise de frequência e colunas<br>
            • Foco em C3, C4 e C6 como colunas principais
        </div>
        """, unsafe_allow_html=True)
        
        # Inicializa gerador se necessário
        if st.session_state.v4_gerador is None and st.session_state.dados_api:
            st.session_state.v4_gerador = GeradorMegaSenaV4(st.session_state.dados_api, 50)
        
        with st.expander("📊 Análise de Colunas", expanded=True):
            if st.session_state.v4_gerador:
                analise = st.session_state.v4_gerador.analise_colunas
                st.markdown("**Frequência das Colunas nos Últimos 20 Concursos:**")
                cols = st.columns(6)
                for i, (col, qtd) in enumerate(analise['colunas_mais_frequentes']):
                    with cols[i]:
                        st.metric(col, f"{qtd}x")
                
                st.markdown(f"""
                <div style='background:#0e1117; border-radius:10px; padding:15px; margin-top:10px;'>
                    <strong>🎯 Coluna Principal:</strong> {analise['coluna_principal']}<br>
                    <strong>🔧 Colunas de Apoio:</strong> {analise['coluna_apoio1']}, {analise['coluna_apoio2']}
                </div>
                """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 GERAR V4 - 15 JOGOS", use_container_width=True, type="primary"):
                with st.spinner("Gerando 15 jogos com a estratégia V4..."):
                    if st.session_state.v4_gerador:
                        resultado = st.session_state.v4_gerador.gerar_todos_jogos()
                        st.session_state.v4_jogos = resultado
                        st.session_state.jogos = resultado['todos']
                        
                        # Calcula scores
                        scores = []
                        analises = []
                        for jogo in resultado['todos']:
                            analise = st.session_state.v4_gerador.analisar_jogo(jogo)
                            analises.append(analise)
                            score = 0
                            if analise:
                                if analise['quantidade_colunas'] >= 4:
                                    score += 3
                                if 2 <= analise['pares'] <= 4:
                                    score += 2
                                if 2 <= analise['primos'] <= 4:
                                    score += 2
                                if 180 <= analise['soma'] <= 220:
                                    score += 1
                                if analise['repetidas_ultimo'] in [2, 3, 4]:
                                    score += 2
                            scores.append(score)
                        
                        st.session_state.v4_scores = scores
                        st.session_state.v4_analise_detalhada = analises
                        st.success("✅ 15 jogos gerados com sucesso!")
        
        with col2:
            if st.button("🎲 GERAR SÓ PRINCIPAIS", use_container_width=True):
                with st.spinner("Gerando 10 jogos principais..."):
                    if st.session_state.v4_gerador:
                        principais = st.session_state.v4_gerador.gerar_jogos_principais(10)
                        st.session_state.v4_jogos = {'principais': principais, 'protecao': [], 'todos': principais}
                        st.session_state.jogos = principais
                        st.success("✅ 10 jogos principais gerados!")
        
        # Exibe jogos gerados
        if st.session_state.v4_jogos:
            jogos = st.session_state.v4_jogos
            scores = st.session_state.v4_scores if st.session_state.v4_scores else []
            analises = st.session_state.v4_analise_detalhada if st.session_state.v4_analise_detalhada else []
            
            st.markdown("### 📋 Jogos Gerados")
            
            # Bloco A - Jogos Principais
            st.markdown("#### 🔵 BLOCO A - 10 Jogos Principais")
            for i, jogo in enumerate(jogos['principais']):
                score = scores[i] if i < len(scores) else 0
                analise = analises[i] if i < len(analises) else None
                medalha = "🏆" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "📌"
                
                stats = ""
                if analise:
                    stats = f"⚖️ {analise['pares']}p/{analise['impares']}i | 🔢 {analise['primos']} primos | ➕ {analise['soma']} | 🔁 {analise['repetidas_ultimo']} rep | 📊 {analise['quantidade_colunas']} colunas"
                
                st.markdown(f"""
                <div class='jogo-v4-principal'>
                    {medalha} <strong>Jogo {i+1:2d}</strong> — Score: {score}<br>
                    {formatar_jogo_html(jogo)}<br>
                    <small style='color:#aaa;'>{stats}</small>
                </div>
                """, unsafe_allow_html=True)
            
            # Bloco B - Jogos de Proteção
            if jogos['protecao']:
                st.markdown("#### 🟢 BLOCO B - 5 Jogos de Proteção")
                for i, jogo in enumerate(jogos['protecao']):
                    idx = 10 + i
                    score = scores[idx] if idx < len(scores) else 0
                    analise = analises[idx] if idx < len(analises) else None
                    
                    stats = ""
                    if analise:
                        stats = f"⚖️ {analise['pares']}p/{analise['impares']}i | 🔢 {analise['primos']} primos | ➕ {analise['soma']} | 🔁 {analise['repetidas_ultimo']} rep | 📊 {analise['quantidade_colunas']} colunas"
                    
                    st.markdown(f"""
                    <div class='jogo-v4-protecao'>
                        🛡️ <strong>Proteção {i+1}</strong> — Score: {score}<br>
                        {formatar_jogo_html(jogo)}<br>
                        <small style='color:#aaa;'>{stats}</small>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Recomendações
            st.markdown("### 📊 Recomendações de Prioridade")
            
            if st.session_state.v4_gerador:
                recomendacoes = st.session_state.v4_gerador.get_recomendacoes_prioridade()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown("**🔥 Prioridade Máxima (6 jogos)**")
                    for idx in recomendacoes['prioridade_maxima']:
                        if idx < len(jogos['principais']):
                            st.markdown(f"Jogo {idx+1}")
                
                with col2:
                    st.markdown("**📊 Prioridade Média (4 jogos)**")
                    for idx in recomendacoes['prioridade_media']:
                        if idx < len(jogos['principais']):
                            st.markdown(f"Jogo {idx+1}")
                
                with col3:
                    st.markdown("**🛡️ Proteção (5 jogos)**")
                    for idx in range(len(jogos['protecao'])):
                        st.markdown(f"Proteção {idx+1}")
            
            # Planos de Jogo
            st.markdown("### 💰 Planos de Jogo")
            
            planos = st.session_state.v4_gerador.get_planos_jogo() if st.session_state.v4_gerador else {}
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**📌 Econômico (4 jogos)**")
                st.markdown("Jogos 1, 2, 3, 8")
            with col2:
                st.markdown("**📌 Intermediário (8 jogos)**")
                st.markdown("Jogos 1, 2, 3, 4, 5, 8, 10, Proteção 1")
            with col3:
                st.markdown("**📌 Completo (15 jogos)**")
                st.markdown("Todos os 15 jogos")
            
            # Botões de ação
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("💾 Salvar Jogos V4", key="salvar_v4", use_container_width=True):
                    ultimo = st.session_state.dados_api[0]
                    jogos_para_salvar = st.session_state.v4_jogos['todos']
                    arquivo, jogo_id = salvar_jogos_gerados(
                        jogos_para_salvar, [], 
                        {"versao": "Mega-Sena V4", "estrategia": "Colunas"},
                        ultimo.get('concurso', ultimo.get('numeroDoConcurso', 0)),
                        ultimo.get('data', ultimo.get('dataApuracao', '')),
                        {"scores": st.session_state.v4_scores}
                    )
                    if arquivo:
                        st.success(f"✅ Jogos salvos! ID: {jogo_id}")
                        st.session_state.jogos_salvos = carregar_jogos_salvos()
            
            with col2:
                df_export = gerar_csv_download_mega(st.session_state.v4_jogos['todos'], st.session_state.v4_scores, "Mega-Sena V4")
                st.download_button(
                    label="📥 Exportar CSV",
                    data=df_export.to_csv(index=False),
                    file_name=f"megasena_v4_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col3:
                json_data = json.dumps({
                    "versao": "Mega-Sena V4",
                    "data_geracao": datetime.now().isoformat(),
                    "total_jogos": len(st.session_state.v4_jogos['todos']),
                    "jogos_principais": st.session_state.v4_jogos['principais'],
                    "jogos_protecao": st.session_state.v4_jogos['protecao'],
                    "scores": st.session_state.v4_scores,
                    "analises": convert_numpy_types(st.session_state.v4_analise_detalhada)
                }, indent=2, ensure_ascii=False, default=str)
                
                st.download_button(
                    label="📦 Exportar JSON",
                    data=json_data,
                    file_name=f"megasena_v4_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
                )

if __name__ == "__main__":
    main()

st.markdown("""
<style>
.footer-premium{width:100%;text-align:center;padding:22px 10px;margin-top:40px;background:linear-gradient(180deg,#0b0b0b,#050505);color:#ffffff;border-top:1px solid #222;position:relative;}
.footer-premium::before{content:"";position:absolute;top:0;left:0;width:100%;height:2px;background:linear-gradient(90deg,#ff6b6b,#4ecdc4,#45b7d1,#ff6b6b);box-shadow:0 0 10px #ff6b6b;}
.footer-title{font-size:16px;font-weight:800;letter-spacing:3px;text-transform:uppercase;text-shadow:0 0 6px rgba(255,107,107,0.6);}
.footer-sub{font-size:11px;color:#bfbfbf;margin-top:4px;letter-spacing:1.5px;}
</style>
<div class="footer-premium"><div class="footer-title">MEGA-SENA ELITE SYSTEM</div><div class="footer-sub">SAMUCJ TECNOLOGIA © 2026</div></div>
""", unsafe_allow_html=True)
