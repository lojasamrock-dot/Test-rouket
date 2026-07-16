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

st.set_page_config(
    page_title="🎯 DIA DE SORTE - DS Elite 10",
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
.concurso-info { background: #1e1e2e; padding: 10px; border-radius: 10px; margin: 10px 0; }
.metric-card { background: #16213e; padding: 10px; border-radius: 10px; text-align: center; }
.highlight { background: #00ffaa20; border-left: 4px solid #00ffaa; padding: 10px; border-radius: 8px; margin: 10px 0; }
.ds-highlight { background: linear-gradient(135deg, #ff6b6b30 0%, #feca5730 50%, #4ecdc430 100%); border: 2px solid #feca57; padding: 15px; border-radius: 12px; margin: 10px 0; }
.elite-ds-highlight { background: linear-gradient(135deg, #ff880030 0%, #feca5730 50%, #4ecdc430 100%); border: 2px solid #ff8800; padding: 15px; border-radius: 12px; margin: 10px 0; }
.download-section { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 20px; border-radius: 15px; margin: 20px 0; border: 2px solid #feca57; text-align: center; }
.jogo-ds-principal { border-left: 5px solid #4cc9f0; background: #0e1117; border-radius: 10px; padding: 15px; margin-bottom: 10px; }
.jogo-ds-protecao { border-left: 5px solid #f97316; background: #0e1117; border-radius: 10px; padding: 15px; margin-bottom: 10px; }
.jogo-ds-elite { border-left: 5px solid #feca57; background: #0e1117; border-radius: 10px; padding: 15px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("📊🎯 DIA DE SORTE - DS Elite 10")
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
        if not os.path.exists("jogos_salvos_ds"):
            os.makedirs("jogos_salvos_ds")
        jogo_id = str(uuid.uuid4())[:8]
        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"jogos_salvos_ds/jogos_{data_hora}_{jogo_id}.json"
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
        if os.path.exists("jogos_salvos_ds"):
            for arquivo in os.listdir("jogos_salvos_ds"):
                if arquivo.endswith(".json"):
                    try:
                        with open(f"jogos_salvos_ds/{arquivo}", 'r', encoding='utf-8') as f:
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

def formatar_jogo_html_ds(jogo, destaque_mes=False, mes_atual=None):
    """Formata um jogo do Dia de Sorte em HTML"""
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
        # Destaque para números primos
        if num in [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31]:
            html += f"<span style='background:#4cc9f020; border:1px solid #4cc9f0; border-radius:20px; padding:5px 8px; margin:2px; display:inline-block; font-weight:bold;'>{num:02d}</span>"
        else:
            html += f"<span style='background:#0e1117; border:1px solid #262730; border-radius:20px; padding:5px 8px; margin:2px; display:inline-block;'>{num:02d}</span>"
    
    if destaque_mes and mes_atual:
        html += f" <span style='background:#feca5740; border:1px solid #feca57; border-radius:20px; padding:5px 12px; margin:2px; display:inline-block; font-weight:bold;'>🌙 {mes_atual}</span>"
    
    return html

def contar_pares_ds(jogo):
    return sum(1 for d in jogo if d % 2 == 0)

def contar_primos_ds(jogo):
    primos = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}
    return sum(1 for d in jogo if d in primos)

def contar_consecutivos_ds(jogo):
    jogo = sorted(jogo)
    return sum(1 for i in range(len(jogo)-1) if jogo[i+1] == jogo[i] + 1)

def distribuir_por_faixas_ds(jogo):
    """Distribui os números por faixas: Baixa (1-10), Média (11-21), Alta (22-31)"""
    faixas = [0, 0, 0]
    for n in jogo:
        if 1 <= n <= 10:
            faixas[0] += 1
        elif 11 <= n <= 21:
            faixas[1] += 1
        else:  # 22-31
            faixas[2] += 1
    return faixas

# =====================================================
# FUNÇÃO PARA BUSCAR DADOS DO DIA DE SORTE
# =====================================================

def buscar_historico_dia_de_sorte(quantidade=100):
    """
    Busca o histórico de concursos do Dia de Sorte
    """
    try:
        # Busca lista de concursos
        url_lista = "https://loteriascaixa-api.herokuapp.com/api/diadesorte"
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
            st.error(f"❌ Erro ao buscar dados: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"❌ Erro na requisição: {e}")
        return None

# =====================================================
# CLASSE DS ELITE 10 - GERADOR AVANÇADO
# =====================================================

class GeradorDSElite10:
    """
    DS Elite 10 - Método Avançado para Dia de Sorte
    Baseado em cobertura estatística e análise histórica
    """
    
    def __init__(self, dados_api, qtd_concursos=100):
        self.dados_api = dados_api
        self.qtd_concursos = min(qtd_concursos, len(dados_api))
        
        # Meses do ano
        self.meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                      'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        
        # Processa concursos
        self.concursos = []
        self.meses_historicos = []
        for concurso in dados_api[:self.qtd_concursos]:
            if 'dezenas' in concurso:
                dezenas = sorted(map(int, concurso['dezenas']))
                self.concursos.append(dezenas)
                
                # Extrai mês da sorte
                if 'mesDaSorte' in concurso:
                    mes = concurso['mesDaSorte']
                    if mes in self.meses:
                        self.meses_historicos.append(mes)
                    else:
                        # Tenta encontrar o mês na lista
                        for m in self.meses:
                            if m.lower() in mes.lower():
                                self.meses_historicos.append(m)
                                break
                        else:
                            self.meses_historicos.append(mes)
        
        self.ultimo_concurso = self.concursos[0] if self.concursos else []
        self.ultimo_mes = self.meses_historicos[0] if self.meses_historicos else 'Junho'
        
        # Calcula análises
        self.frequencias = self._calcular_frequencias()
        self.atrasos = self._calcular_atrasos()
        self.frequencia_meses = self._calcular_frequencia_meses()
        self.media_repetidas = self._calcular_media_repetidas()
        
        # Classifica dezenas
        self.dezenas_classificadas = self._classificar_dezenas()
        
    def _calcular_frequencias(self):
        freq = Counter()
        for concurso in self.concursos:
            freq.update(concurso)
        return freq
    
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
    
    def _calcular_frequencia_meses(self):
        return Counter(self.meses_historicos)
    
    def _calcular_media_repetidas(self):
        if len(self.concursos) < 2:
            return 0
        total_repetidas = 0
        for i in range(len(self.concursos) - 1):
            repetidas = len(set(self.concursos[i]) & set(self.concursos[i+1]))
            total_repetidas += repetidas
        return total_repetidas / (len(self.concursos) - 1)
    
    def _classificar_dezenas(self):
        """Classifica dezenas em Quentes, Mornas, Frias e Muito Atrasadas"""
        if not self.frequencias:
            return {}
        
        freq_media = sum(self.frequencias.values()) / 31
        max_atraso = max(self.atrasos.values()) if self.atrasos else 0
        
        classificacao = {}
        for num in range(1, 32):
            freq = self.frequencias.get(num, 0)
            atraso = self.atrasos.get(num, 0)
            
            if freq > freq_media * 1.5:
                tipo = 'Quente'
            elif freq >= freq_media * 0.8:
                tipo = 'Morna'
            elif atraso > max_atraso * 0.7:
                tipo = 'Muito Atrasada'
            else:
                tipo = 'Fria'
            
            classificacao[num] = {
                'tipo': tipo,
                'frequencia': freq,
                'atraso': atraso,
                'score': (freq / max(freq_media, 1)) + (1 - (atraso / max(max_atraso, 1)))
            }
        
        return classificacao
    
    def get_melhor_mes(self):
        """Retorna o mês mais frequente"""
        if not self.frequencia_meses:
            return 'Junho'
        return self.frequencia_meses.most_common(1)[0][0]
    
    def get_distribuicao_meses(self, qtd=3):
        """Retorna os meses mais frequentes"""
        if not self.frequencia_meses:
            return ['Junho', 'Julho', 'Agosto']
        return [mes for mes, _ in self.frequencia_meses.most_common(qtd)]
    
    def gerar_jogo_elite(self, config):
        """
        Gera um jogo baseado na configuração Elite
        config: dict com quantidades por tipo
        """
        # Separa dezenas por classificação
        quentes = [n for n, info in self.dezenas_classificadas.items() if info['tipo'] == 'Quente']
        mornas = [n for n, info in self.dezenas_classificadas.items() if info['tipo'] == 'Morna']
        frias = [n for n, info in self.dezenas_classificadas.items() if info['tipo'] == 'Fria']
        muito_atrasadas = [n for n, info in self.dezenas_classificadas.items() if info['tipo'] == 'Muito Atrasada']
        
        # Configuração padrão: 3 quentes, 2 mornas, 2 atrasadas
        qtd_quentes = config.get('quentes', 3)
        qtd_mornas = config.get('mornas', 2)
        qtd_atrasadas = config.get('atrasadas', 2)
        
        jogo = set()
        
        # Seleciona quentes
        if quentes:
            jogo.update(random.sample(quentes, min(qtd_quentes, len(quentes))))
        
        # Seleciona mornas
        if mornas:
            jogo.update(random.sample(mornas, min(qtd_mornas, len(mornas))))
        
        # Seleciona atrasadas (frias + muito atrasadas)
        atrasadas = frias + muito_atrasadas
        if atrasadas:
            jogo.update(random.sample(atrasadas, min(qtd_atrasadas, len(atrasadas))))
        
        # Completa com números aleatórios se necessário
        while len(jogo) < 7:
            novo = random.randint(1, 31)
            if novo not in jogo:
                jogo.add(novo)
        
        return sorted(jogo)
    
    def aplicar_filtros_estatisticos(self, jogo):
        """Aplica filtros estatísticos ao jogo"""
        if len(jogo) != 7:
            return False
        
        # Filtro 1: 3 ou 4 números ímpares
        pares = contar_pares_ds(jogo)
        if pares not in [3, 4]:
            return False
        
        # Filtro 2: Soma dentro da faixa histórica (70-130)
        soma = sum(jogo)
        if not (70 <= soma <= 130):
            return False
        
        # Filtro 3: Distribuição por faixas
        faixas = distribuir_por_faixas_ds(jogo)
        if not (1 <= faixas[0] <= 4 and 1 <= faixas[1] <= 4 and 1 <= faixas[2] <= 4):
            return False
        
        # Filtro 4: Evitar sequências longas
        consecutivos = contar_consecutivos_ds(jogo)
        if consecutivos > 3:
            return False
        
        # Filtro 5: Máximo de 3 números da mesma classificação
        tipos = [self.dezenas_classificadas.get(n, {}).get('tipo', '') for n in jogo]
        for tipo in ['Quente', 'Morna', 'Fria', 'Muito Atrasada']:
            if tipos.count(tipo) > 4:
                return False
        
        return True
    
    def gerar_jogos_filtrados(self, qtd_jogos=10, config=None):
        """Gera múltiplos jogos com filtros estatísticos"""
        if config is None:
            config = {'quentes': 3, 'mornas': 2, 'atrasadas': 2}
        
        jogos = []
        tentativas = 0
        max_tentativas = qtd_jogos * 1000
        
        progress_bar = st.progress(0, text="Gerando jogos filtrados...")
        
        while len(jogos) < qtd_jogos and tentativas < max_tentativas:
            tentativas += 1
            jogo = self.gerar_jogo_elite(config)
            
            if self.aplicar_filtros_estatisticos(jogo) and jogo not in jogos:
                jogos.append(jogo)
            
            if tentativas % 100 == 0:
                progress_bar.progress(
                    min(len(jogos)/qtd_jogos, 1.0),
                    text=f"Encontrados {len(jogos)}/{qtd_jogos} jogos (tentativas: {tentativas})"
                )
        
        progress_bar.empty()
        return jogos
    
    def gerar_fechamento(self, pool_size=11, qtd_jogos=10):
        """
        Gera fechamento baseado em um pool de números
        """
        # Seleciona pool baseado em score
        numeros_ordenados = sorted(
            [(n, info['score']) for n, info in self.dezenas_classificadas.items()],
            key=lambda x: x[1], reverse=True
        )
        pool = [n for n, _ in numeros_ordenados[:pool_size]]
        
        jogos = []
        cobertura = set()
        
        # Gera combinações do pool
        for _ in range(qtd_jogos * 2):
            jogo = sorted(random.sample(pool, 7))
            if self.aplicar_filtros_estatisticos(jogo):
                # Verifica cobertura de combinações de 6
                cobertura_atual = 0
                for comb in combinations(jogo, 6):
                    if comb not in cobertura:
                        cobertura_atual += 1
                
                if cobertura_atual > 0:
                    jogos.append(jogo)
                    for comb in combinations(jogo, 6):
                        cobertura.add(comb)
                    
                    if len(jogos) >= qtd_jogos:
                        break
        
        return jogos, pool, cobertura
    
    def analisar_jogo(self, jogo):
        """Analisa um jogo e retorna estatísticas"""
        if not jogo or len(jogo) != 7:
            return None
        
        faixas = distribuir_por_faixas_ds(jogo)
        tipos = [self.dezenas_classificadas.get(n, {}).get('tipo', 'Desconhecido') for n in jogo]
        
        return {
            'jogo': jogo,
            'pares': contar_pares_ds(jogo),
            'impares': 7 - contar_pares_ds(jogo),
            'primos': contar_primos_ds(jogo),
            'soma': sum(jogo),
            'consecutivos': contar_consecutivos_ds(jogo),
            'faixas': {'Baixa': faixas[0], 'Média': faixas[1], 'Alta': faixas[2]},
            'tipos': {tipo: tipos.count(tipo) for tipo in set(tipos)},
            'repetidas_ultimo': len(set(jogo) & set(self.ultimo_concurso)) if self.ultimo_concurso else 0
        }
    
    def get_estatisticas_gerais(self):
        """Retorna estatísticas gerais do sistema"""
        freq_media = sum(self.frequencias.values()) / 31 if self.frequencias else 0
        
        return {
            'total_concursos': len(self.concursos),
            'frequencia_media': round(freq_media, 2),
            'media_repetidas': round(self.media_repetidas, 2),
            'mes_mais_frequente': self.get_melhor_mes(),
            'distribuicao_meses': dict(self.frequencia_meses.most_common(5)),
            'dezenas_mais_frequentes': self.frequencias.most_common(10),
            'dezenas_mais_atrasadas': sorted(self.atrasos.items(), key=lambda x: x[1], reverse=True)[:10]
        }

# =====================================================
# FUNÇÕES DE DOWNLOAD
# =====================================================

def gerar_csv_download_ds(jogos, scores=None, estrategia="DS Elite 10"):
    dados_export = []
    for i, jogo in enumerate(jogos):
        faixas = distribuir_por_faixas_ds(jogo)
        linha = {
            "Jogo": i + 1,
            "Dezenas": ", ".join(f"{n:02d}" for n in sorted(jogo)),
            "Pares": contar_pares_ds(jogo),
            "Ímpares": 7 - contar_pares_ds(jogo),
            "Primos": contar_primos_ds(jogo),
            "Soma": sum(jogo),
            "Consecutivos": contar_consecutivos_ds(jogo),
            "Faixa_Baixa": faixas[0],
            "Faixa_Média": faixas[1],
            "Faixa_Alta": faixas[2]
        }
        if scores and i < len(scores):
            if isinstance(scores[i], dict):
                linha["Score"] = scores[i].get("score", 0)
            else:
                linha["Score"] = scores[i]
        dados_export.append(linha)
    return pd.DataFrame(dados_export)

def conferir_jogos_ds(jogos, resultado_set):
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
    if "ds_gerador" not in st.session_state: st.session_state.ds_gerador = None
    if "ds_jogos" not in st.session_state: st.session_state.ds_jogos = None
    if "ds_scores" not in st.session_state: st.session_state.ds_scores = []
    if "ds_analise_detalhada" not in st.session_state: st.session_state.ds_analise_detalhada = []
    if "ultimo_concurso_info" not in st.session_state: st.session_state.ultimo_concurso_info = None

    with st.sidebar:
        st.header("⚙️ Configurações")
        
        qtd = st.slider("Qtd concursos históricos", 50, 300, 100)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Carregar Dia de Sorte", use_container_width=True):
                with st.spinner("Carregando dados do Dia de Sorte..."):
                    dados = buscar_historico_dia_de_sorte(qtd)
                    
                    if dados and len(dados) > 0:
                        st.session_state.dados_api = dados
                        
                        # Extrai informações do último concurso
                        ultimo = dados[0] if isinstance(dados, list) else dados
                        st.session_state.ultimo_concurso_info = {
                            'numero': ultimo.get('concurso', ultimo.get('numeroDoConcurso', 'N/A')),
                            'data': ultimo.get('data', ultimo.get('dataApuracao', 'N/A')),
                            'dezenas': ultimo.get('dezenas', []),
                            'mes': ultimo.get('mesDaSorte', 'N/A')
                        }
                        
                        # Inicializa gerador
                        st.session_state.ds_gerador = GeradorDSElite10(dados, qtd)
                        st.success(f"✅ Carregados {len(dados)} concursos!")
                        st.success(f"📅 Último: #{st.session_state.ultimo_concurso_info['numero']} - {st.session_state.ultimo_concurso_info['data']}")
                        st.success(f"🌙 Mês da Sorte: {st.session_state.ultimo_concurso_info['mes']}")
                    else:
                        st.error("❌ Não foi possível carregar os dados")
        
        with col2:
            if st.button("🔄 Atualizar Dados", use_container_width=True):
                with st.spinner("Atualizando dados..."):
                    dados = buscar_historico_dia_de_sorte(qtd)
                    if dados and len(dados) > 0:
                        st.session_state.dados_api = dados
                        st.session_state.ds_gerador = GeradorDSElite10(dados, qtd)
                        st.success(f"✅ Dados atualizados! {len(dados)} concursos")

    # Exibe informações do último concurso se disponível
    if st.session_state.ultimo_concurso_info:
        info = st.session_state.ultimo_concurso_info
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**📅 Último Concurso:** #{info['numero']}")
        st.sidebar.markdown(f"**📆 Data:** {info['data']}")
        st.sidebar.markdown(f"**🌙 Mês da Sorte:** {info['mes']}")
        if info['dezenas']:
            dezenas = sorted(map(int, info['dezenas']))
            st.sidebar.markdown(f"**🎯 Resultado:** {', '.join(f'{d:02d}' for d in dezenas)}")

    if not st.session_state.dados_api:
        st.info("👈 Carregue os dados do Dia de Sorte na barra lateral para começar.")
        return

    st.subheader("🎯 Análise e Geração de Jogos - DS Elite 10")

    # Criar abas
    tabs = st.tabs([
        "📊 Análise",
        "🎲 DS Elite 10",
        "🔍 Conferência",
        "📈 Avaliação",
        "✅ Salvos"
    ])

    # ================= TAB 1: ANÁLISE =================
    with tabs[0]:
        st.markdown("### 📊 Análise Estatística - DS Elite 10")
        
        if st.session_state.ds_gerador:
            gerador = st.session_state.ds_gerador
            stats = gerador.get_estatisticas_gerais()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Concursos", stats['total_concursos'])
            with col2:
                st.metric("Média Repetidas", f"{stats['media_repetidas']:.2f}")
            with col3:
                st.metric("Freq. Média", f"{stats['frequencia_media']:.2f}")
            with col4:
                st.metric("🌙 Mês + Frequente", stats['mes_mais_frequente'])
            
            # Distribuição de meses
            st.markdown("### 📅 Distribuição dos Meses da Sorte")
            df_meses = pd.DataFrame(list(stats['distribuicao_meses'].items()), columns=['Mês', 'Frequência'])
            st.bar_chart(df_meses.set_index('Mês'))
            
            # Dezenas mais frequentes
            st.markdown("### 🔥 Dezenas Mais Frequentes")
            cols = st.columns(10)
            for i, (num, freq) in enumerate(stats['dezenas_mais_frequentes'][:10]):
                with cols[i]:
                    st.metric(f"{num:02d}", f"{freq}x")
            
            # Dezenas mais atrasadas
            st.markdown("### ⏰ Dezenas Mais Atrasadas")
            cols = st.columns(10)
            for i, (num, atraso) in enumerate(stats['dezenas_mais_atrasadas'][:10]):
                with cols[i]:
                    st.metric(f"{num:02d}", f"{atraso} concursos")
            
            # Classificação das dezenas
            st.markdown("### 🎯 Classificação das Dezenas")
            
            # Cria tabela de classificação
            classificacao_data = []
            for num in range(1, 32):
                info = gerador.dezenas_classificadas.get(num, {})
                classificacao_data.append({
                    'Dezena': f"{num:02d}",
                    'Tipo': info.get('tipo', 'N/A'),
                    'Frequência': info.get('frequencia', 0),
                    'Atraso': info.get('atraso', 0),
                    'Score': round(info.get('score', 0), 3)
                })
            
            df_classificacao = pd.DataFrame(classificacao_data)
            
            # Cores para os tipos
            def color_tipo(val):
                colors = {
                    'Quente': 'background-color: #4cc9f040',
                    'Morna': 'background-color: #4ade8040',
                    'Fria': 'background-color: #f9731640',
                    'Muito Atrasada': 'background-color: #ff6b6b40'
                }
                return colors.get(val, '')
            
            st.dataframe(
                df_classificacao.style.applymap(color_tipo, subset=['Tipo']),
                use_container_width=True,
                hide_index=True
            )

    # ================= TAB 2: DS ELITE 10 =================
    with tabs[1]:
        st.markdown("### 🎯 DS Elite 10 - Método Avançado")
        st.markdown("""
        <div class="ds-highlight">
            <strong>🎯 MÉTODO DS ELITE 10:</strong><br>
            • Análise de frequência e atraso das dezenas (1 a 31)<br>
            • Classificação em Quentes, Mornas, Frias e Muito Atrasadas<br>
            • Composição otimizada: 3 Quentes + 2 Mornas + 2 Atrasadas<br>
            • Filtros estatísticos: paridade, soma, distribuição por faixas<br>
            • Fechamento matemático para maximizar cobertura
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.ds_gerador:
            gerador = st.session_state.ds_gerador
            
            with st.expander("⚙️ Configurações de Geração", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    qtd_jogos_ds = st.slider("Quantidade de jogos", 5, 50, 15)
                with col2:
                    qtd_quentes = st.slider("Números Quentes", 1, 5, 3)
                with col3:
                    qtd_atrasadas = st.slider("Números Atrasados", 1, 4, 2)
                
                # Configuração da composição
                config = {
                    'quentes': qtd_quentes,
                    'mornas': 7 - qtd_quentes - qtd_atrasadas,
                    'atrasadas': qtd_atrasadas
                }
                
                st.markdown(f"""
                <div style='background:#0e1117; border-radius:10px; padding:10px; margin-top:10px;'>
                    <strong>📊 Composição:</strong> {config['quentes']} Quentes + {config['mornas']} Mornas + {config['atrasadas']} Atrasadas
                </div>
                """, unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🎯 GERAR ELITE", use_container_width=True, type="primary"):
                    with st.spinner(f"Gerando {qtd_jogos_ds} jogos com método DS Elite 10..."):
                        jogos = gerador.gerar_jogos_filtrados(qtd_jogos_ds, config)
                        
                        if jogos:
                            st.session_state.ds_jogos = {'todos': jogos}
                            st.session_state.jogos = jogos
                            
                            # Analisa jogos
                            analises = []
                            scores = []
                            for jogo in jogos:
                                analise = gerador.analisar_jogo(jogo)
                                analises.append(analise)
                                if analise:
                                    score = 0
                                    if 3 <= analise['pares'] <= 4:
                                        score += 2
                                    if 2 <= analise['primos'] <= 4:
                                        score += 2
                                    if 70 <= analise['soma'] <= 130:
                                        score += 2
                                    if analise['repetidas_ultimo'] in [1, 2, 3]:
                                        score += 1
                                    scores.append(score)
                            
                            st.session_state.ds_scores = scores
                            st.session_state.ds_analise_detalhada = analises
                            st.success(f"✅ {len(jogos)} jogos gerados!")
            
            with col2:
                if st.button("🔒 FECHAMENTO", use_container_width=True):
                    with st.spinner("Gerando fechamento matemático..."):
                        pool_size = st.session_state.get('pool_size', 11)
                        jogos, pool, cobertura = gerador.gerar_fechamento(pool_size, qtd_jogos_ds)
                        
                        if jogos:
                            st.session_state.ds_jogos = {
                                'todos': jogos,
                                'pool': pool,
                                'cobertura': len(cobertura)
                            }
                            st.session_state.jogos = jogos
                            st.success(f"✅ {len(jogos)} jogos gerados com pool de {len(pool)} números!")
                            st.info(f"📊 Cobertura: {len(cobertura)} combinações de 6 números")
            
            with col3:
                if st.button("🌙 POR MÊS", use_container_width=True):
                    with st.spinner("Gerando jogos por mês..."):
                        meses = gerador.get_distribuicao_meses(3)
                        jogos_por_mes = []
                        for mes in meses:
                            # Gera alguns jogos para cada mês
                            for _ in range(qtd_jogos_ds // 3):
                                jogo = gerador.gerar_jogo_elite(config)
                                if gerador.aplicar_filtros_estatisticos(jogo):
                                    jogos_por_mes.append((jogo, mes))
                        
                        jogos = [j for j, _ in jogos_por_mes[:qtd_jogos_ds]]
                        meses_jogos = [m for _, m in jogos_por_mes[:qtd_jogos_ds]]
                        
                        if jogos:
                            st.session_state.ds_jogos = {
                                'todos': jogos,
                                'meses': meses_jogos
                            }
                            st.session_state.jogos = jogos
                            st.success(f"✅ {len(jogos)} jogos gerados com diferentes meses!")
            
            # Exibe jogos gerados
            if st.session_state.ds_jogos:
                jogos = st.session_state.ds_jogos['todos'] if 'todos' in st.session_state.ds_jogos else []
                scores = st.session_state.ds_scores if st.session_state.ds_scores else []
                analises = st.session_state.ds_analise_detalhada if st.session_state.ds_analise_detalhada else []
                meses = st.session_state.ds_jogos.get('meses', [])
                
                st.markdown(f"### 📋 Jogos Gerados ({len(jogos)})")
                
                for i, jogo in enumerate(jogos[:20]):
                    score = scores[i] if i < len(scores) else 0
                    analise = analises[i] if i < len(analises) else None
                    mes_atual = meses[i] if i < len(meses) else None
                    
                    medalha = "🏆" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "📌"
                    
                    stats = ""
                    if analise:
                        stats = f"⚖️ {analise['pares']}p/{analise['impares']}i | 🔢 {analise['primos']} primos | ➕ {analise['soma']} | 🔁 {analise['repetidas_ultimo']} rep"
                        stats += f" | 📊 B:{analise['faixas']['Baixa']} M:{analise['faixas']['Média']} A:{analise['faixas']['Alta']}"
                    
                    mes_html = f"🌙 {mes_atual}" if mes_atual else ""
                    
                    st.markdown(f"""
                    <div class='jogo-ds-elite'>
                        {medalha} <strong>Jogo {i+1:2d}</strong> — Score: {score} {mes_html}<br>
                        {formatar_jogo_html_ds(jogo, mes_atual is not None, mes_atual)}<br>
                        <small style='color:#aaa;'>{stats}</small>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Estatísticas do pool (se disponível)
                if 'pool' in st.session_state.ds_jogos:
                    st.markdown("### 📊 Pool Selecionado")
                    pool = st.session_state.ds_jogos['pool']
                    st.markdown(" ".join(f"<span style='background:#feca5740; border:1px solid #feca57; border-radius:15px; padding:5px 10px; margin:2px; display:inline-block;'>{n:02d}</span>" for n in pool), unsafe_allow_html=True)
                    st.caption(f"🔒 {len(pool)} números selecionados | {st.session_state.ds_jogos.get('cobertura', 0)} combinações de 6 cobertas")
                
                # Botões de ação
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("💾 Salvar Jogos DS", key="salvar_ds", use_container_width=True):
                        ultimo = st.session_state.dados_api[0]
                        jogos_para_salvar = st.session_state.ds_jogos['todos']
                        arquivo, jogo_id = salvar_jogos_gerados(
                            jogos_para_salvar, [], 
                            {"versao": "DS Elite 10", "estrategia": "Método Avançado"},
                            ultimo.get('concurso', ultimo.get('numeroDoConcurso', 0)),
                            ultimo.get('data', ultimo.get('dataApuracao', '')),
                            {"scores": st.session_state.ds_scores}
                        )
                        if arquivo:
                            st.success(f"✅ Jogos salvos! ID: {jogo_id}")
                            st.session_state.jogos_salvos = carregar_jogos_salvos()
                
                with col2:
                    df_export = gerar_csv_download_ds(st.session_state.ds_jogos['todos'], st.session_state.ds_scores, "DS Elite 10")
                    st.download_button(
                        label="📥 Exportar CSV",
                        data=df_export.to_csv(index=False),
                        file_name=f"dia_de_sorte_elite_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                with col3:
                    json_data = json.dumps({
                        "versao": "DS Elite 10",
                        "data_geracao": datetime.now().isoformat(),
                        "total_jogos": len(st.session_state.ds_jogos['todos']),
                        "jogos": st.session_state.ds_jogos['todos'],
                        "scores": st.session_state.ds_scores,
                        "analises": convert_numpy_types(st.session_state.ds_analise_detalhada)
                    }, indent=2, ensure_ascii=False, default=str)
                    
                    st.download_button(
                        label="📦 Exportar JSON",
                        data=json_data,
                        file_name=f"dia_de_sorte_elite_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        use_container_width=True
                    )

    # ================= TAB 3: CONFERÊNCIA =================
    with tabs[2]:
        st.markdown("### 🔍 Conferência de Jogos")
        
        if st.session_state.dados_api:
            concurso_resultado = st.selectbox(
                "Selecione o concurso para conferência", 
                st.session_state.dados_api, 
                format_func=lambda c: f"#{c.get('concurso', c.get('numeroDoConcurso', 'N/A'))} - {c.get('data', c.get('dataApuracao', 'N/A'))} - {c.get('mesDaSorte', '')}"
            )
            if concurso_resultado:
                resultado_oficial = set(map(int, concurso_resultado["dezenas"]))
                st.markdown(f"""
                <div class="highlight">
                    <strong>🎯 Resultado #{concurso_resultado.get('concurso', concurso_resultado.get('numeroDoConcurso', 'N/A'))}:</strong><br>
                    {formatar_jogo_html_ds(sorted(resultado_oficial))}<br>
                    <strong>🌙 Mês da Sorte:</strong> {concurso_resultado.get('mesDaSorte', 'N/A')}
                </div>
                """, unsafe_allow_html=True)
        
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
            jogos_texto = st.text_area("Digite os jogos (um por linha, números separados por vírgula)", placeholder="1,2,3,4,5,6,7")
            if jogos_texto:
                for linha in jogos_texto.strip().split('\n'):
                    if linha.strip():
                        try:
                            dezenas = [int(n.strip()) for n in linha.split(',')]
                            if len(dezenas) == 7 and all(1 <= n <= 31 for n in dezenas):
                                jogos_para_conferir.append(sorted(dezenas))
                        except:
                            pass
        
        if jogos_para_conferir and 'resultado_oficial' in locals():
            if st.button("🔍 CONFERIR JOGOS", use_container_width=True, type="primary"):
                df_conferencia = conferir_jogos_ds(jogos_para_conferir, resultado_oficial)
                st.markdown("### 📊 Resultados da Conferência")
                col1, col2, col3, col4 = st.columns(4)
                with col1: st.metric("Total Jogos", len(df_conferencia))
                with col2: st.metric("Melhor Acerto", df_conferencia.iloc[0]["Acertos"])
                with col3: st.metric("Média Acertos", round(df_conferencia["Acertos"].mean(), 1))
                with col4: st.metric("Jogos com 5+", len(df_conferencia[df_conferencia["Acertos"] >= 5]))
                
                for i, row in df_conferencia.head(20).iterrows():
                    medalha = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "📌"
                    st.markdown(f"""
                    <div style='border-left: 5px solid {"#ffd700" if i == 0 else "#c0c0c0" if i == 1 else "#cd7f32" if i == 2 else "#4cc9f0"}; background:#0e1117; border-radius:10px; padding:12px; margin-bottom:8px;'>
                        {medalha} <strong>Jogo {row['Jogo']}</strong> — <span style='color:#00ffaa;'>{row['Acertos']} acertos</span><br>
                        {formatar_jogo_html_ds(row['Dezenas'])}
                    </div>
                    """, unsafe_allow_html=True)

    # ================= TAB 4: AVALIAÇÃO =================
    with tabs[3]:
        st.markdown("### 📈 Avaliação Estatística dos Jogos")
        if st.session_state.jogos:
            avaliacao = []
            for i, jogo in enumerate(st.session_state.jogos):
                faixas = distribuir_por_faixas_ds(jogo)
                avaliacao.append({
                    "Jogo": i+1,
                    "Pares": contar_pares_ds(jogo),
                    "Ímpares": 7 - contar_pares_ds(jogo),
                    "Primos": contar_primos_ds(jogo),
                    "Soma": sum(jogo),
                    "Consecutivos": contar_consecutivos_ds(jogo),
                    "Faixa_Baixa": faixas[0],
                    "Faixa_Média": faixas[1],
                    "Faixa_Alta": faixas[2]
                })
            df_avaliacao = pd.DataFrame(avaliacao)
            st.dataframe(df_avaliacao, use_container_width=True, hide_index=True)
            
            # Estatísticas agregadas
            st.markdown("### 📊 Estatísticas Agregadas")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Média Pares", f"{df_avaliacao['Pares'].mean():.1f}")
            with col2:
                st.metric("Média Soma", f"{df_avaliacao['Soma'].mean():.1f}")
            with col3:
                st.metric("Média Primos", f"{df_avaliacao['Primos'].mean():.1f}")
            with col4:
                st.metric("Média Consecutivos", f"{df_avaliacao['Consecutivos'].mean():.1f}")
        else:
            st.info("Gere jogos primeiro na aba 'DS Elite 10'")

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

if __name__ == "__main__":
    main()

st.markdown("""
<style>
.footer-premium{width:100%;text-align:center;padding:22px 10px;margin-top:40px;background:linear-gradient(180deg,#0b0b0b,#050505);color:#ffffff;border-top:1px solid #222;position:relative;}
.footer-premium::before{content:"";position:absolute;top:0;left:0;width:100%;height:2px;background:linear-gradient(90deg,#ff6b6b,#feca57,#4ecdc4,#ff6b6b);box-shadow:0 0 10px #feca57;}
.footer-title{font-size:16px;font-weight:800;letter-spacing:3px;text-transform:uppercase;text-shadow:0 0 6px rgba(254,202,87,0.6);}
.footer-sub{font-size:11px;color:#bfbfbf;margin-top:4px;letter-spacing:1.5px;}
</style>
<div class="footer-premium"><div class="footer-title">DS ELITE 10 SYSTEM</div><div class="footer-sub">SAMUCJ TECNOLOGIA © 2026</div></div>
""", unsafe_allow_html=True)
