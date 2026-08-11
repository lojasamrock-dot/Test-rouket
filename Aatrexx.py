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
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier, StackingClassifier
from sklearn.linear_model import LogisticRegression
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

def contar_fibonacci_lf(jogo):
    """Módulo 4 - DNA: quantidade de dezenas que pertencem à sequência de Fibonacci (dentro de 1-25)."""
    fibonacci = {1, 2, 3, 5, 8, 13, 21}
    return sum(1 for d in jogo if d in fibonacci)

def contar_moldura_centro_lf(jogo):
    """
    Módulo 4 - DNA: no painel 5x5 da Lotofácil, classifica cada dezena do
    jogo como 'moldura' (borda) ou 'centro' (miolo 3x3) e retorna a
    contagem de cada grupo.
    """
    moldura, centro = 0, 0
    for n in jogo:
        linha, coluna = (n - 1) // 5, (n - 1) % 5
        if linha in (0, 4) or coluna in (0, 4):
            moldura += 1
        else:
            centro += 1
    return {'moldura': moldura, 'centro': centro}

def calcular_amplitude_lf(jogo):
    """Módulo 4 - DNA: diferença entre a maior e a menor dezena do jogo."""
    return max(jogo) - min(jogo)

def calcular_desvio_padrao_lf(jogo):
    """Módulo 4 - DNA: desvio padrão das dezenas do jogo."""
    return float(np.std(jogo))

def calcular_saltos_lf(jogo):
    """Módulo 4 - DNA: distância (salto) média entre dezenas consecutivas do jogo ordenado."""
    jogo_ordenado = sorted(jogo)
    if len(jogo_ordenado) < 2:
        return 0.0
    saltos = [jogo_ordenado[i+1] - jogo_ordenado[i] for i in range(len(jogo_ordenado)-1)]
    return float(np.mean(saltos))

def analisar_sequencias_lf(jogo):
    """
    Módulo 4 / 13 - DNA e Sequências: identifica blocos de dezenas
    consecutivas no jogo (ex.: 4,5,6 é uma sequência de tamanho 3) e os
    classifica em pequenas (2), médias (3-4) e longas (5+).
    """
    jogo_ordenado = sorted(jogo)
    blocos = []
    atual = [jogo_ordenado[0]] if jogo_ordenado else []
    for n in jogo_ordenado[1:]:
        if n == atual[-1] + 1:
            atual.append(n)
        else:
            if len(atual) >= 2:
                blocos.append(len(atual))
            atual = [n]
    if len(atual) >= 2:
        blocos.append(len(atual))

    return {
        'blocos': blocos,
        'pequenas': sum(1 for b in blocos if b == 2),
        'medias': sum(1 for b in blocos if 3 <= b <= 4),
        'longas': sum(1 for b in blocos if b >= 5),
        'maior_sequencia': max(blocos) if blocos else 1
    }

def calcular_entropia_lf(jogo):
    """
    Módulo 4 / 15 - DNA e Entropia: mede a dispersão das dezenas do jogo
    pelas 5 linhas do painel 5x5 usando entropia de Shannon normalizada
    (0 = todas as dezenas concentradas numa linha só, 1 = distribuição
    perfeitamente uniforme entre as 5 linhas). Jogos muito previsíveis
    tendem a ter entropia baixa.
    """
    linhas = distribuir_linhas_lf(jogo)
    total = sum(linhas)
    if total == 0:
        return 0.0
    probs = [c / total for c in linhas if c > 0]
    entropia = -sum(p * math.log2(p) for p in probs)
    entropia_max = math.log2(5)
    return round(entropia / entropia_max, 4) if entropia_max else 0.0

def calcular_dna_jogo_lf(jogo):
    """Módulo 4 - DNA: consolida todas as características estatísticas de um jogo em um único dicionário."""
    moldura_centro = contar_moldura_centro_lf(jogo)
    sequencias = analisar_sequencias_lf(jogo)
    return {
        'pares': contar_pares_lf(jogo),
        'impares': 15 - contar_pares_lf(jogo),
        'primos': contar_primos_lf(jogo),
        'fibonacci': contar_fibonacci_lf(jogo),
        'moldura': moldura_centro['moldura'],
        'centro': moldura_centro['centro'],
        'soma': sum(jogo),
        'amplitude': calcular_amplitude_lf(jogo),
        'desvio_padrao': calcular_desvio_padrao_lf(jogo),
        'salto_medio': calcular_saltos_lf(jogo),
        'sequencias': sequencias,
        'entropia': calcular_entropia_lf(jogo)
    }

def calcular_similaridade_dna_lf(jogo, dna_historico):
    """
    Módulo 4 - DNA Estatístico: compara o DNA de um jogo candidato com o
    perfil médio histórico (média + desvio padrão de cada característica),
    usando uma curva gaussiana por métrica. Retorna um score de 0 a 1: 1
    significa que o jogo é bem "típico" (parecido com o padrão histórico
    de pares, primos, fibonacci, moldura/centro, amplitude, desvio padrão,
    salto médio e entropia); valores baixos indicam um jogo atípico.
    """
    if not dna_historico or not dna_historico.get('amostras'):
        return 1.0

    dna_jogo = calcular_dna_jogo_lf(sorted(jogo))
    metricas = ['pares', 'primos', 'fibonacci', 'moldura', 'centro',
                'amplitude', 'desvio_padrao', 'salto_medio', 'entropia']

    scores = []
    for metrica in metricas:
        media = dna_historico.get(f'{metrica}_media')
        desvio = dna_historico.get(f'{metrica}_desvio')
        if media is None:
            continue
        sigma = max(desvio, 0.35) if desvio else 0.35
        diff = dna_jogo[metrica] - media
        scores.append(math.exp(-(diff ** 2) / (2 * (sigma ** 2))))

    return round(float(np.mean(scores)), 4) if scores else 1.0

def passa_filtro_dna_lf(jogo, dna_historico, similaridade_minima=0.5):
    """
    Módulo 4 - DNA Estatístico: só aceita o jogo se a similaridade com o
    DNA histórico (ver `calcular_similaridade_dna_lf`) for maior ou igual
    a `similaridade_minima`, descartando jogos estatisticamente atípicos.
    """
    return calcular_similaridade_dna_lf(jogo, dna_historico) >= similaridade_minima

def calcular_meta_score_jogo(jogo, estatisticas, pontuacao, ia=None):
    """
    Módulo 19 - Meta Score.

    Combina, em uma única nota de 0 a 100 avaliada no JOGO como um todo
    (e não em cada dezena isolada), os módulos que só fazem sentido nesse
    nível:

    - `motor`: a pontuação média das 15 dezenas do jogo no MotorPontuacaoLF,
      que já soma os Módulos 1 (Frequência Inteligente), 2 (Atraso), 3
      (Ciclos), 5 (Bayes), 6 (Markov) e 7 (Correlação);
    - `dna`: a similaridade do DNA do jogo com o perfil histórico (Módulo 4);
    - `ml`: quando há modelos de IA treinados (Módulo 18), a probabilidade
      média prevista pelos modelos para as dezenas do jogo.

    Cada módulo contribui uma nota de 0 a 1; a nota final é a média
    ponderada delas, escalada para 0-100.
    """
    pontuacao_media = float(np.mean([pontuacao.pontuacoes.get(n, 0) for n in jogo])) / 100.0
    dna_similaridade = calcular_similaridade_dna_lf(jogo, estatisticas.dna_historico)

    componentes = {'motor': pontuacao_media, 'dna': dna_similaridade}
    pesos = {'motor': 0.55, 'dna': 0.25}

    ml_prob = None
    if ia is not None and getattr(ia, 'modelos', None):
        previsoes = ia.prever_probabilidades(jogo)
        if previsoes:
            ml_prob = float(np.mean([info['media'] for info in previsoes.values()]))
            componentes['ml'] = ml_prob
            pesos['ml'] = 0.20

    soma_pesos = sum(pesos.values()) or 1.0
    nota = sum(componentes[k] * pesos[k] for k in componentes) / soma_pesos

    return {
        'nota': round(nota * 100, 2),
        'motor_medio': round(pontuacao_media * 100, 2),
        'dna_similaridade': round(dna_similaridade * 100, 2),
        'ml_probabilidade': round(ml_prob * 100, 2) if ml_prob is not None else None
    }

def passa_meta_score_lf(jogo, estatisticas, pontuacao, corte=60, ia=None):
    """
    Módulo 19 - Meta Score: só sobrevivem jogos com nota final (0-100)
    maior ou igual ao `corte` definido.
    """
    return calcular_meta_score_jogo(jogo, estatisticas, pontuacao, ia)['nota'] >= corte

def passa_filtros_qualidade_lf(jogo, ultimo_concurso=None,
                                pares_min=7, pares_max=8,
                                soma_min=170, soma_max=220,
                                primos_min=3, primos_max=5,
                                repetidas_min=4, repetidas_max=6):
    """
    Filtro de qualidade opcional para descartar jogos que fujam de
    padrões historicamente comuns na Lotofácil (pares, soma, primos,
    quantidade de dezenas repetidas em relação ao último concurso).
    """
    pares = contar_pares_lf(jogo)
    if not (pares_min <= pares <= pares_max):
        return False

    soma = sum(jogo)
    if not (soma_min <= soma <= soma_max):
        return False

    primos = contar_primos_lf(jogo)
    if not (primos_min <= primos <= primos_max):
        return False

    if ultimo_concurso:
        repetidas = len(set(jogo) & set(ultimo_concurso))
        if not (repetidas_min <= repetidas <= repetidas_max):
            return False

    return True

def contar_categorias_atraso_lf(jogo, atraso_categoria):
    """
    Conta quantas dezenas de um jogo pertencem a cada categoria de
    atraso inteligente (Módulo 2): Muito Quente, Quente, Neutra, Fria,
    Muito Fria, Fóssil.
    """
    contagem = Counter()
    for dezena in jogo:
        categoria = atraso_categoria.get(dezena, 'Neutra')
        contagem[categoria] += 1
    return contagem

def respeita_quotas_atraso_lf(jogo, atraso_categoria, quotas):
    """
    Módulo 2 - Atraso Inteligente: verifica se um jogo respeita as quotas
    (mínimo/máximo de dezenas) definidas para cada categoria de atraso.

    `quotas` é um dict no formato {categoria: (minimo, maximo)}. Categorias
    ausentes de `quotas` não são restringidas.
    """
    contagem = contar_categorias_atraso_lf(jogo, atraso_categoria)
    for categoria, (minimo, maximo) in quotas.items():
        qtd = contagem.get(categoria, 0)
        if not (minimo <= qtd <= maximo):
            return False
    return True

def contar_clusters_jogo(jogo, clusters_dezena):
    """
    Módulo 8 - Clusters: conta quantas dezenas de um jogo pertencem a cada
    grupo (Quente, Frio, Oscilante, Estável).
    """
    contagem = Counter()
    for dezena in jogo:
        grupo = clusters_dezena.get(dezena, 'Estável')
        contagem[grupo] += 1
    return contagem

def respeita_quotas_cluster_lf(jogo, clusters_dezena, quotas):
    """
    Módulo 8 - Clusters: verifica se um jogo respeita as quotas
    (mínimo/máximo de dezenas) definidas para cada cluster. `quotas` é um
    dict {grupo: (minimo, maximo)}; grupos ausentes não são restringidos.
    """
    contagem = contar_clusters_jogo(jogo, clusters_dezena)
    for grupo, (minimo, maximo) in quotas.items():
        qtd = contagem.get(grupo, 0)
        if not (minimo <= qtd <= maximo):
            return False
    return True

def calcular_distancia_jogos_lf(jogo_a, jogo_b):
    """
    Módulo 16 - Distância entre Jogos.

    Conta quantas dezenas diferem entre dois jogos de mesmo tamanho (ex.:
    dois jogos de 15 dezenas com 9 dezenas em comum têm distância 6). Usada
    para evitar jogos "clones" dentro de um mesmo fechamento — a
    recomendação do estudo é distância mínima de 6, idealmente 7 ou 8.
    """
    return len(set(jogo_a) - set(jogo_b))

def gerar_fechamento_lf(dezenas_pool, qtd_jogos, tamanho_jogo=15, max_tentativas=None, filtro_fn=None, distancia_minima=None):
    """
    Gera um fechamento (roda de jogos) usando um pool fixo de dezenas
    (ex.: as 21 dezenas mais bem rankeadas). Produz `qtd_jogos` jogos
    distintos entre si, balanceando a frequência de aparição de cada
    dezena do pool ao longo dos jogos gerados. Se `filtro_fn` for
    informado, só aceita jogos para os quais `filtro_fn(jogo)` seja True.
    Se `distancia_minima` for informado (Módulo 16), só aceita um jogo se
    ele diferir de TODOS os jogos já aceitos em pelo menos essa quantidade
    de dezenas, evitando jogos "clones" dentro do mesmo fechamento.
    """
    dezenas_pool = sorted(set(dezenas_pool))
    n_pool = len(dezenas_pool)

    if n_pool < tamanho_jogo or qtd_jogos <= 0:
        return []

    max_combinacoes = math.comb(n_pool, tamanho_jogo)
    qtd_jogos = min(qtd_jogos, max_combinacoes)

    if max_tentativas is None:
        max_tentativas = qtd_jogos * (2500 if distancia_minima else 600) + 4000

    contagem = {d: 0 for d in dezenas_pool}
    jogos = []
    jogos_set = set()
    tentativas = 0

    while len(jogos) < qtd_jogos and tentativas < max_tentativas:
        tentativas += 1

        # Pesos inversamente proporcionais à contagem atual: favorece
        # dezenas menos usadas até agora, equilibrando o fechamento
        pool_restante = list(dezenas_pool)
        pesos_restante = [1.0 / (1 + contagem[d]) for d in pool_restante]

        jogo = []
        for _ in range(tamanho_jogo):
            escolhido = random.choices(pool_restante, weights=pesos_restante, k=1)[0]
            idx = pool_restante.index(escolhido)
            jogo.append(escolhido)
            pool_restante.pop(idx)
            pesos_restante.pop(idx)

        jogo_ordenado = tuple(sorted(jogo))

        if jogo_ordenado in jogos_set:
            continue
        if filtro_fn is not None and not filtro_fn(list(jogo_ordenado)):
            continue
        if distancia_minima and any(
            calcular_distancia_jogos_lf(jogo_ordenado, existente) < distancia_minima for existente in jogos
        ):
            continue

        jogos_set.add(jogo_ordenado)
        jogos.append(list(jogo_ordenado))
        for d in jogo_ordenado:
            contagem[d] += 1

    return jogos

def gerar_fechamento_cobertura_lf(dezenas_pool, qtd_jogos, tamanho_jogo=15, k_garantia=11,
                                   n_candidatos=600, n_amostras_subconjuntos=2500,
                                   filtro_fn=None, semente=None):
    """
    Fechamento por cobertura aproximada (Greedy Set-Cover heurístico).

    Gera um conjunto de jogos candidatos e, a cada rodada, escolhe o
    candidato que cobre o maior número de subconjuntos de tamanho
    `k_garantia` (amostrados aleatoriamente dentro do pool) ainda não
    cobertos por nenhum jogo já selecionado. Isso tende a distribuir
    melhor a cobertura das combinações possíveis do que uma seleção
    puramente aleatória ou só balanceada por frequência.

    IMPORTANTE: como o pool costuma ter 21 dezenas, o número total de
    subconjuntos de tamanho 11 é C(21,11) ≈ 352 mil — grande demais para
    testar cobertura exaustiva em tempo real. Por isso este método usa
    uma AMOSTRA de subconjuntos-alvo (`n_amostras_subconjuntos`) como
    estimativa: é uma heurística de boa cobertura, não uma garantia
    matemática formal de que qualquer combinação de `k_garantia` acertos
    dentro do pool será sempre coberta por algum jogo.

    Retorna (jogos_selecionados, taxa_cobertura_estimada).
    """
    dezenas_pool = sorted(set(dezenas_pool))
    n_pool = len(dezenas_pool)

    if n_pool < tamanho_jogo or n_pool < k_garantia or qtd_jogos <= 0:
        return [], 0.0

    rng = random.Random(semente)
    idx_map = {d: i for i, d in enumerate(dezenas_pool)}

    def to_mask(nums):
        m = 0
        for n in nums:
            m |= (1 << idx_map[n])
        return m

    # ---- Gera jogos candidatos distintos (respeitando filtro de qualidade, se houver) ----
    max_comb_jogo = math.comb(n_pool, tamanho_jogo)
    n_candidatos = min(n_candidatos, max_comb_jogo)

    candidatos = set()
    tentativas = 0
    max_tent_cand = n_candidatos * 40 + 4000
    while len(candidatos) < n_candidatos and tentativas < max_tent_cand:
        tentativas += 1
        jogo = tuple(sorted(rng.sample(dezenas_pool, tamanho_jogo)))
        if jogo in candidatos:
            continue
        if filtro_fn is not None and not filtro_fn(list(jogo)):
            continue
        candidatos.add(jogo)

    candidatos = list(candidatos)
    if not candidatos:
        return [], 0.0

    candidatos_mask = np.array([to_mask(c) for c in candidatos], dtype=np.int64)
    qtd_jogos = min(qtd_jogos, len(candidatos))

    # ---- Amostra subconjuntos-alvo de tamanho k_garantia para estimar cobertura ----
    max_comb_sub = math.comb(n_pool, k_garantia)
    n_amostras_subconjuntos = min(n_amostras_subconjuntos, max_comb_sub)

    subconjuntos = set()
    tent_sub = 0
    max_tent_sub = n_amostras_subconjuntos * 40 + 4000
    while len(subconjuntos) < n_amostras_subconjuntos and tent_sub < max_tent_sub:
        tent_sub += 1
        sub = tuple(sorted(rng.sample(dezenas_pool, k_garantia)))
        subconjuntos.add(sub)

    sub_masks = np.array([to_mask(s) for s in subconjuntos], dtype=np.int64)
    if len(sub_masks) == 0:
        return [], 0.0

    disponivel_cand = np.ones(len(candidatos_mask), dtype=bool)
    restante_masks = sub_masks.copy()
    total_subs = len(sub_masks)

    selecionados_idx = []

    for _ in range(qtd_jogos):
        if len(restante_masks) == 0 or not disponivel_cand.any():
            break

        cand_idx_disp = np.where(disponivel_cand)[0]
        cm = candidatos_mask[cand_idx_disp][:, None]   # (C, 1)
        sm = restante_masks[None, :]                    # (1, S)
        cobre = (sm & cm) == sm                          # (C, S) booleano
        contagem = cobre.sum(axis=1)                     # (C,)

        melhor_pos = int(np.argmax(contagem))
        if contagem[melhor_pos] <= 0 and len(selecionados_idx) > 0:
            # Nenhum candidato restante cobre algo novo; melhor parar aqui
            # do que preencher jogos sem ganho de cobertura.
            break

        melhor_i_global = int(cand_idx_disp[melhor_pos])
        disponivel_cand[melhor_i_global] = False

        cobertos_bool = cobre[melhor_pos]
        restante_masks = restante_masks[~cobertos_bool]
        selecionados_idx.append(melhor_i_global)

    jogos_selecionados = [list(candidatos[i]) for i in selecionados_idx]
    cobertura_total = total_subs - len(restante_masks)
    taxa_cobertura = cobertura_total / total_subs if total_subs else 0.0

    return jogos_selecionados, taxa_cobertura

def _crossover_jogo_lf(pai_a, pai_b, dezenas_pool, tamanho_jogo=15):
    """
    Módulo 17 - Algoritmo Genético: cruzamento. O filho herda primeiro as
    dezenas em comum entre os dois pais (o que os dois "concordam" ser
    bom); o restante das vagas é preenchido com dezenas que aparecem em
    QUALQUER um dos dois pais, e só recorre ao pool geral se isso ainda
    não for suficiente.
    """
    comuns = list(set(pai_a) & set(pai_b))
    uniao = list(set(pai_a) | set(pai_b))
    random.shuffle(comuns)
    random.shuffle(uniao)

    filho = comuns[:tamanho_jogo]
    for d in uniao:
        if len(filho) >= tamanho_jogo:
            break
        if d not in filho:
            filho.append(d)

    if len(filho) < tamanho_jogo:
        resto_pool = [d for d in dezenas_pool if d not in filho]
        random.shuffle(resto_pool)
        while len(filho) < tamanho_jogo and resto_pool:
            filho.append(resto_pool.pop())

    return sorted(filho[:tamanho_jogo])

def _mutar_jogo_lf(jogo, dezenas_pool, taxa_mutacao=0.15):
    """
    Módulo 17 - Algoritmo Genético: mutação. Com probabilidade
    `taxa_mutacao`, troca uma dezena do jogo por outra do pool que ainda
    não estava presente — mantém diversidade genética na população e
    evita convergência prematura para um único padrão de jogo.
    """
    jogo = list(jogo)
    fora_pool = [d for d in dezenas_pool if d not in jogo]
    if random.random() < taxa_mutacao and fora_pool:
        idx = random.randrange(len(jogo))
        jogo[idx] = random.choice(fora_pool)
    return sorted(jogo)

def gerar_fechamento_genetico_lf(dezenas_pool, qtd_jogos, estatisticas, pontuacao, ia=None,
                                  tamanho_jogo=15, geracoes=40, tamanho_populacao=60,
                                  taxa_mutacao=0.15, distancia_minima=6, filtro_fn=None):
    """
    Módulo 17 - Algoritmo Genético.

    Evolui uma população de jogos candidatos por várias gerações usando
    seleção por torneio, cruzamento e mutação. A aptidão (fitness) de cada
    jogo é o seu Meta Score (Módulo 19), que já combina Frequência
    Inteligente, Atraso, Ciclos, Bayes, Markov, Correlação, DNA e (quando
    disponível) Machine Learning. Ao final, seleciona os `qtd_jogos`
    melhores jogos distintos, priorizando quem respeita a distância
    mínima entre jogos (Módulo 16) — evitando que o fechamento final saia
    cheio de jogos "clones" uns dos outros.
    """
    dezenas_pool = sorted(set(dezenas_pool))
    if len(dezenas_pool) < tamanho_jogo or qtd_jogos <= 0:
        return []

    def fitness(jogo):
        if filtro_fn is not None and not filtro_fn(jogo):
            return -1.0
        return calcular_meta_score_jogo(jogo, estatisticas, pontuacao, ia=ia)['nota']

    # População inicial aleatória
    populacao = []
    tentativas_init = 0
    max_tentativas_init = tamanho_populacao * 30 + 500
    while len(populacao) < tamanho_populacao and tentativas_init < max_tentativas_init:
        tentativas_init += 1
        populacao.append(sorted(random.sample(dezenas_pool, tamanho_jogo)))

    if not populacao:
        return []

    for _ in range(geracoes):
        avaliados = [(jogo, fitness(jogo)) for jogo in populacao]
        avaliados.sort(key=lambda x: x[1], reverse=True)

        elite_tam = max(2, tamanho_populacao // 10)
        nova_populacao = [jogo for jogo, _ in avaliados[:elite_tam]]

        while len(nova_populacao) < tamanho_populacao:
            grupo_a = random.sample(avaliados, min(3, len(avaliados)))
            pai_a = max(grupo_a, key=lambda x: x[1])[0]
            grupo_b = random.sample(avaliados, min(3, len(avaliados)))
            pai_b = max(grupo_b, key=lambda x: x[1])[0]

            filho = _crossover_jogo_lf(pai_a, pai_b, dezenas_pool, tamanho_jogo)
            filho = _mutar_jogo_lf(filho, dezenas_pool, taxa_mutacao)
            nova_populacao.append(filho)

        populacao = nova_populacao

    avaliados_final = [(tuple(jogo), fitness(jogo)) for jogo in populacao]
    avaliados_final = sorted(set(avaliados_final), key=lambda x: x[1], reverse=True)

    selecionados = []
    # 1ª passada: exige a distância mínima entre jogos (Módulo 16)
    for jogo, nota in avaliados_final:
        if nota < 0:
            continue
        if distancia_minima and any(
            calcular_distancia_jogos_lf(jogo, sel) < distancia_minima for sel in selecionados
        ):
            continue
        selecionados.append(jogo)
        if len(selecionados) >= qtd_jogos:
            break

    # 2ª passada: quando a população converge para uma região estreita do
    # espaço de busca, "repara" os melhores candidatos restantes via
    # mutação sucessiva até satisfazerem a distância mínima em relação aos
    # já selecionados — evita que o fechamento saia cheio de jogos quase
    # idênticos só porque a evolução convergiu demais.
    if distancia_minima and len(selecionados) < qtd_jogos:
        candidatos_restantes = [j for j, n in avaliados_final if n >= 0 and j not in selecionados]
        for candidato in candidatos_restantes:
            if len(selecionados) >= qtd_jogos:
                break
            tentativa = list(candidato)
            for _ in range(80):
                if all(calcular_distancia_jogos_lf(tentativa, sel) >= distancia_minima for sel in selecionados):
                    break
                fora_pool = [d for d in dezenas_pool if d not in tentativa]
                if not fora_pool:
                    break
                idx_troca = random.randrange(len(tentativa))
                tentativa[idx_troca] = random.choice(fora_pool)
            tentativa_tupla = tuple(sorted(tentativa))
            if tentativa_tupla not in selecionados and all(
                calcular_distancia_jogos_lf(tentativa_tupla, sel) >= distancia_minima for sel in selecionados
            ):
                selecionados.append(tentativa_tupla)

    # 3ª passada: se ainda faltar jogo, completa relaxando a exigência de
    # distância mínima (mantendo só a regra de não repetir jogo já selecionado)
    if len(selecionados) < qtd_jogos:
        for jogo, nota in avaliados_final:
            if nota < 0 or jogo in selecionados:
                continue
            selecionados.append(jogo)
            if len(selecionados) >= qtd_jogos:
                break

    return [list(j) for j in selecionados]

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

        # Fatores adicionais para refinar a seleção da base de dezenas
        self.intervalos_medios = self._calcular_intervalos_medios(historico)
        self.moldura_miolo_freq = self._calcular_moldura_miolo_freq(historico)
        self.repetiu_ultimo_concurso = self._calcular_repetiu_ultimo_concurso(historico)
        self.correlacao_media = self._calcular_correlacao_media(historico)

        # Módulo 1 - Frequência Inteligente (multi-janela ponderada: 5, 10,
        # 20, 30, 50, 100 e 200 concursos, cada uma com peso próprio)
        self.frequencia_inteligente = self.calcular_frequencia_inteligente()

        # Módulo 2 - Atraso Inteligente (classifica cada dezena em Muito
        # Quente / Quente / Neutra / Fria / Muito Fria / Fóssil, comparando
        # o atraso atual com o intervalo médio histórico da própria dezena)
        self.atraso_categoria = self._classificar_atraso_inteligente()
        self.contagem_categorias_atraso = Counter(self.atraso_categoria.values())

        # Módulo 3 - Ciclos (dezenas que já fecharam o ciclo atual x
        # dezenas que ainda faltam sair para fechá-lo)
        self.ciclos = self._calcular_ciclos(historico)

        # Módulo 4 - DNA Estatístico (perfil médio histórico dos concursos:
        # pares, primos, fibonacci, moldura/centro, amplitude, entropia etc.)
        self.dna_historico = self._calcular_dna_historico(historico)

        # Módulo 5 - Redes Bayesianas (P(B sair | A saiu no mesmo concurso))
        self.rede_bayesiana = self._calcular_rede_bayesiana(historico)

        # Módulo 6 - Cadeias de Markov (P(B sair no concurso seguinte | A saiu no atual))
        self.cadeia_markov = self._calcular_cadeia_markov(historico)

        # Scores agregados (0-1) usados na nota final: o quão "influente"
        # cada dezena é nas relações bayesianas/markovianas encontradas
        self.bayes_forca = self._agregar_forca_matriz(self.rede_bayesiana['matriz'])
        self.markov_forca = self._agregar_forca_matriz(self.cadeia_markov['matriz'])

        # Módulo 7 - Correlação: pares de dezenas mais fortemente correlacionados
        # (positiva ou negativamente) ao longo do histórico
        self.pares_fortes = self._calcular_pares_fortes(historico)

        # Módulo 8 - Clusters: agrupa as dezenas em 4 grupos (Quente, Frio,
        # Oscilante, Estável) a partir do perfil atual de cada uma
        self.clusters_dezena, self.clusters_contagem = self._calcular_clusters()

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
        periodos = [5, 10, 20, 30, 50, 100, 200]
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

    def calcular_frequencia_inteligente(self, pesos_janelas=None):
        """
        Módulo 1 - Frequência Inteligente.

        Em vez de olhar para uma única janela de concursos, combina a
        frequência de cada dezena em várias janelas temporais (5, 10, 20,
        30, 50, 100 e 200 últimos concursos), cada uma com um peso
        próprio. Janelas curtas capturam o momento recente; janelas
        longas capturam o comportamento histórico de mais longo prazo.
        `pesos_janelas` pode ser informado (ex.: vindo de sliders na UI)
        para recalcular com pesos customizados. Retorna um score
        normalizado (0 a 1) por dezena.
        """
        pesos_janelas = pesos_janelas or {
            5: 0.05, 10: 0.10, 20: 0.15, 30: 0.20,
            50: 0.20, 100: 0.15, 200: 0.15
        }
        soma_pesos = sum(pesos_janelas.values()) or 1.0
        score = {n: 0.0 for n in range(1, 26)}

        for janela, peso in pesos_janelas.items():
            freq_dict = self.frequencias_periodos.get(janela, {})
            max_freq = max(freq_dict.values()) if freq_dict else 0
            for n in range(1, 26):
                freq_norm = (freq_dict.get(n, 0) / max_freq) if max_freq else 0
                score[n] += freq_norm * peso

        return {n: round(v / soma_pesos, 4) for n, v in score.items()}

    def _classificar_atraso_inteligente(self):
        """
        Módulo 2 - Atraso Inteligente.

        Compara o atraso atual de cada dezena com o intervalo médio
        histórico de saída DELA MESMA (não um valor fixo igual para
        todas), e classifica em 6 categorias:

        - Muito Quente: saiu bem antes do que costuma (razão < 0.3)
        - Quente: saiu um pouco antes do habitual (0.3 a 0.7)
        - Neutra: dentro do intervalo esperado (0.7 a 1.3)
        - Fria: já passou um pouco do intervalo esperado (1.3 a 2.0)
        - Muito Fria: bem além do esperado (2.0 a 3.0)
        - Fóssil: muitíssimo além do intervalo típico (> 3.0)

        Essas categorias são usadas depois para limitar automaticamente
        quantas dezenas de cada grupo podem entrar em um jogo gerado
        (ver `respeita_quotas_atraso_lf`).
        """
        categorias = {}
        for n in range(1, 26):
            atraso_atual = self.atrasos.get(n, 0)
            intervalo_medio = self.intervalos_medios.get(n, 1.6) or 1.6
            razao = atraso_atual / intervalo_medio

            if razao < 0.3:
                categoria = "Muito Quente"
            elif razao < 0.7:
                categoria = "Quente"
            elif razao < 1.3:
                categoria = "Neutra"
            elif razao < 2.0:
                categoria = "Fria"
            elif razao < 3.0:
                categoria = "Muito Fria"
            else:
                categoria = "Fóssil"

            categorias[n] = categoria
        return categorias

    def _calcular_ciclos(self, historico):
        """
        Módulo 3 - Ciclos.

        Um "ciclo" se fecha quando, percorrendo os concursos do mais
        recente para o mais antigo, todas as 25 dezenas já apareceram
        pelo menos uma vez. Esta função identifica o ciclo em andamento
        (quais dezenas já saíram nele e quais ainda faltam para fechá-lo)
        e, como referência estatística, o tamanho médio dos ciclos
        completos anteriores.
        """
        dezenas_todas = set(range(1, 26))
        default = {
            'dezenas_presentes_ciclo': set(),
            'dezenas_faltantes_ciclo': dezenas_todas,
            'concursos_no_ciclo_atual': 0,
            'ciclo_atual_fechado': False,
            'tamanho_medio_ciclo': 0.0,
            'tamanhos_ciclos_historico': []
        }
        if not historico:
            return default

        # Ciclo em andamento, a partir do concurso mais recente
        presentes = set()
        count = 0
        fechou = False
        for concurso in historico:
            presentes.update(concurso)
            count += 1
            if presentes == dezenas_todas:
                fechou = True
                break
        faltantes = dezenas_todas - presentes

        # Tamanho de ciclos completos anteriores (para referência estatística)
        resto = historico[count:]
        tamanhos = []
        idx = 0
        while idx < len(resto):
            presentes_tmp = set()
            inicio = idx
            while idx < len(resto) and presentes_tmp != dezenas_todas:
                presentes_tmp.update(resto[idx])
                idx += 1
            if presentes_tmp == dezenas_todas:
                tamanhos.append(idx - inicio)
            else:
                break

        tamanho_medio = float(np.mean(tamanhos)) if tamanhos else float(count)

        return {
            'dezenas_presentes_ciclo': presentes,
            'dezenas_faltantes_ciclo': faltantes,
            'concursos_no_ciclo_atual': count,
            'ciclo_atual_fechado': fechou,
            'tamanho_medio_ciclo': round(tamanho_medio, 2),
            'tamanhos_ciclos_historico': tamanhos[-20:]
        }

    def _calcular_dna_historico(self, historico):
        """
        Módulo 4 - DNA Estatístico.

        Calcula o "DNA" médio dos concursos históricos: perfil de pares,
        primos, fibonacci, moldura/centro, amplitude, desvio padrão,
        salto médio entre dezenas e entropia. Serve como referência para
        avaliar se um jogo gerado tem características parecidas com o
        que costuma sair (sem garantir nada, apenas como indicador
        estatístico de similaridade com o padrão histórico).
        """
        if not historico:
            return {}

        dnas = [calcular_dna_jogo_lf(sorted(c)) for c in historico]

        def media(chave):
            return float(np.mean([d[chave] for d in dnas]))

        def desvio(chave):
            return float(np.std([d[chave] for d in dnas]))

        return {
            'pares_media': round(media('pares'), 2),
            'pares_desvio': round(desvio('pares'), 2),
            'primos_media': round(media('primos'), 2),
            'primos_desvio': round(desvio('primos'), 2),
            'fibonacci_media': round(media('fibonacci'), 2),
            'fibonacci_desvio': round(desvio('fibonacci'), 2),
            'moldura_media': round(media('moldura'), 2),
            'moldura_desvio': round(desvio('moldura'), 2),
            'centro_media': round(media('centro'), 2),
            'centro_desvio': round(desvio('centro'), 2),
            'amplitude_media': round(media('amplitude'), 2),
            'amplitude_desvio': round(desvio('amplitude'), 2),
            'desvio_padrao_media': round(media('desvio_padrao'), 2),
            'desvio_padrao_desvio': round(desvio('desvio_padrao'), 2),
            'salto_medio_media': round(media('salto_medio'), 2),
            'salto_medio_desvio': round(desvio('salto_medio'), 2),
            'entropia_media': round(media('entropia'), 4),
            'entropia_desvio': round(desvio('entropia'), 4),
            'amostras': len(dnas)
        }

    def _calcular_rede_bayesiana(self, historico):
        """
        Módulo 5 - Redes Bayesianas.

        Para cada par de dezenas (A, B), calcula P(B | A) = probabilidade
        de B ter saído em um concurso, dado que A saiu NESSE MESMO
        concurso: (nº de concursos em que A e B saíram juntas) / (nº de
        concursos em que A saiu). Diferente de uma correlação simples, a
        direção importa aqui: P(B|A) pode ser bem diferente de P(A|B)
        quando A e B têm frequências históricas distintas.
        """
        contagem_individual = Counter()
        contagem_par = Counter()
        for concurso in historico:
            presentes = set(concurso)
            for a in presentes:
                contagem_individual[a] += 1
            for a in presentes:
                for b in presentes:
                    if a != b:
                        contagem_par[(a, b)] += 1

        matriz = {a: {} for a in range(1, 26)}
        for a in range(1, 26):
            total_a = contagem_individual.get(a, 0)
            for b in range(1, 26):
                if a == b:
                    continue
                matriz[a][b] = round(contagem_par.get((a, b), 0) / total_a, 4) if total_a > 0 else 0.0

        top_dependentes = {
            a: sorted(matriz[a].items(), key=lambda x: x[1], reverse=True)[:5]
            for a in range(1, 26)
        }

        return {'matriz': matriz, 'top_dependentes': top_dependentes}

    def _calcular_cadeia_markov(self, historico):
        """
        Módulo 6 - Cadeias de Markov.

        Para cada dezena A, calcula a probabilidade de cada dezena B
        aparecer no concurso IMEDIATAMENTE SEGUINTE (cronologicamente) a
        um concurso em que A apareceu: "A sai → qual a chance de B sair
        no próximo concurso". Diferente do Módulo 5 (mesmo concurso),
        aqui a relação é sequencial entre concursos consecutivos.
        """
        matriz_transicao = {a: Counter() for a in range(1, 26)}
        contagem_a = Counter()

        # historico[0] é o concurso mais recente e historico[k] é anterior
        # a historico[k-1]; logo o concurso seguinte (cronologicamente) a
        # historico[k] é historico[k-1].
        for k in range(len(historico) - 1, 0, -1):
            atual = set(historico[k])
            seguinte = set(historico[k - 1])
            for a in atual:
                contagem_a[a] += 1
                for b in seguinte:
                    matriz_transicao[a][b] += 1

        matriz = {a: {} for a in range(1, 26)}
        for a in range(1, 26):
            total_a = contagem_a.get(a, 0)
            for b in range(1, 26):
                if a == b:
                    continue
                matriz[a][b] = round(matriz_transicao[a].get(b, 0) / total_a, 4) if total_a > 0 else 0.0

        top_sucessoras = {
            a: sorted(matriz[a].items(), key=lambda x: x[1], reverse=True)[:5]
            for a in range(1, 26)
        }

        return {'matriz': matriz, 'top_sucessoras': top_sucessoras}

    def _agregar_forca_matriz(self, matriz):
        """
        Reduz uma matriz de dependência (Bayes ou Markov) a um único score
        0-1 por dezena, representando o quão forte/influente essa dezena é
        em média nas relações encontradas, normalizado pelo maior valor
        observado entre todas as dezenas.
        """
        medias = {}
        for a in range(1, 26):
            valores = list(matriz.get(a, {}).values())
            medias[a] = float(np.mean(valores)) if valores else 0.0
        max_v = max(medias.values()) if medias else 1.0
        max_v = max_v if max_v > 0 else 1.0
        return {a: round(v / max_v, 4) for a, v in medias.items()}

    def _calcular_pares_fortes(self, historico):
        """
        Módulo 7 - Correlação.

        Calcula a matriz completa de correlação de Pearson entre a
        presença de cada par de dezenas ao longo do histórico e extrai os
        10 pares mais fortemente correlacionados positivamente (tendem a
        sair juntas mais do que o esperado ao acaso) e os 10 mais
        correlacionados negativamente (tendem a se "evitar").
        """
        n = len(historico)
        if n < 3:
            return {'matriz': {}, 'top_positivos': [], 'top_negativos': []}

        presenca = np.zeros((25, n))
        for j, concurso in enumerate(historico):
            for num in concurso:
                presenca[num - 1, j] = 1

        with np.errstate(invalid='ignore', divide='ignore'):
            matriz_corr = np.corrcoef(presenca)
        matriz_corr = np.nan_to_num(matriz_corr, nan=0.0)

        matriz = {a: {} for a in range(1, 26)}
        pares = []
        for i in range(25):
            for j in range(i + 1, 25):
                valor = round(float(matriz_corr[i, j]), 4)
                matriz[i + 1][j + 1] = valor
                matriz[j + 1][i + 1] = valor
                pares.append((i + 1, j + 1, valor))

        top_positivos = sorted(pares, key=lambda x: x[2], reverse=True)[:10]
        top_negativos = sorted(pares, key=lambda x: x[2])[:10]

        return {'matriz': matriz, 'top_positivos': top_positivos, 'top_negativos': top_negativos}

    def _calcular_clusters(self):
        """
        Módulo 8 - Clusters.

        Agrupa as 25 dezenas em 4 clusters via K-Means, a partir de um
        perfil de cada dezena (frequência inteligente, atraso relativo e
        magnitude da tendência recente). Os clusters recebem rótulos com
        significado (Quente, Frio, Oscilante, Estável) de acordo com as
        características do centróide de cada grupo, em vez de um índice
        arbitrário do K-Means.
        """
        numeros = list(range(1, 26))
        features = []
        for n in numeros:
            freq = self.frequencia_inteligente.get(n, 0)
            atraso = self.atraso_relativo.get(n, 0)
            inclinacao = abs(self.tendencias.get(n, {}).get('inclinacao', 0))
            features.append([freq, atraso, inclinacao])

        X = np.array(features)
        valores_unicos = len(set(map(tuple, np.round(X, 6).tolist())))
        if valores_unicos < 4:
            grupo_dezena = {n: 'Estável' for n in numeros}
            return grupo_dezena, dict(Counter(grupo_dezena.values()))

        scaler = StandardScaler()
        X_escalado = scaler.fit_transform(X)

        kmeans = KMeans(n_clusters=4, n_init=10, random_state=42)
        indices = kmeans.fit_predict(X_escalado)
        centroides = kmeans.cluster_centers_  # colunas: [freq, atraso, inclinacao]

        restantes = set(range(4))
        rotulo_por_indice = {}

        # Quente: maior frequência relativa e menor atraso relativo
        scores = {i: centroides[i][0] - centroides[i][1] for i in restantes}
        idx = max(scores, key=scores.get)
        rotulo_por_indice[idx] = 'Quente'
        restantes.discard(idx)

        # Frio: maior atraso relativo e menor frequência relativa
        scores = {i: centroides[i][1] - centroides[i][0] for i in restantes}
        idx = max(scores, key=scores.get)
        rotulo_por_indice[idx] = 'Frio'
        restantes.discard(idx)

        # Oscilante: maior magnitude de tendência (mais instável)
        scores = {i: centroides[i][2] for i in restantes}
        idx = max(scores, key=scores.get)
        rotulo_por_indice[idx] = 'Oscilante'
        restantes.discard(idx)

        # Estável: o grupo restante
        for i in restantes:
            rotulo_por_indice[i] = 'Estável'

        grupo_dezena = {n: rotulo_por_indice[idx] for n, idx in zip(numeros, indices)}
        return grupo_dezena, dict(Counter(grupo_dezena.values()))

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

    def _calcular_intervalos_medios(self, historico):
        """
        Calcula o intervalo médio histórico (gap típico) entre aparições de
        cada dezena. Usado para julgar um 'atraso equilibrado': nem muito
        abaixo (dezena excessivamente quente) nem muito acima (fria demais)
        do que costuma ocorrer para aquela dezena especificamente.
        """
        intervalos = {}
        for num in range(1, 26):
            posicoes = [i for i, concurso in enumerate(historico) if num in concurso]
            if len(posicoes) >= 2:
                gaps = [posicoes[i+1] - posicoes[i] for i in range(len(posicoes) - 1)]
                intervalos[num] = float(np.mean(gaps)) if gaps else 1.6
            else:
                intervalos[num] = 1.6  # ~15/25 chance por concurso -> gap esperado
        return intervalos

    def _calcular_moldura_miolo_freq(self, historico):
        """
        Classifica as 25 dezenas em 'moldura' (borda do painel 5x5) e
        'miolo' (centro 3x3) e calcula a frequência relativa histórica
        de cada grupo, normalizada pelo tamanho do grupo.
        """
        miolo = {7, 8, 9, 12, 13, 14, 17, 18, 19}
        contagem_moldura = 0
        contagem_miolo = 0
        for concurso in historico:
            for num in concurso:
                if num in miolo:
                    contagem_miolo += 1
                else:
                    contagem_moldura += 1
        total = contagem_moldura + contagem_miolo
        if total == 0:
            return {'moldura': 0.5, 'miolo': 0.5, 'grupo': {n: ('miolo' if n in miolo else 'moldura') for n in range(1, 26)}}
        # Normaliza pela quantidade de dezenas em cada grupo (16 na moldura, 9 no miolo)
        media_moldura = (contagem_moldura / 16)
        media_miolo = (contagem_miolo / 9)
        soma = media_moldura + media_miolo if (media_moldura + media_miolo) > 0 else 1
        return {
            'moldura': media_moldura / soma,
            'miolo': media_miolo / soma,
            'grupo': {n: ('miolo' if n in miolo else 'moldura') for n in range(1, 26)}
        }

    def _calcular_repetiu_ultimo_concurso(self, historico):
        """Marca quais dezenas saíram no concurso mais recente."""
        if not historico:
            return {n: False for n in range(1, 26)}
        ultimo = set(historico[0])
        return {n: (n in ultimo) for n in range(1, 26)}

    def _calcular_correlacao_media(self, historico):
        """
        Para cada dezena, calcula a correlação de Pearson entre o vetor
        binário de presença dela e o de cada uma das outras 24 dezenas ao
        longo do histórico, e tira a média dos valores absolutos. Dezenas
        com correlação média alta tendem a co-ocorrer de forma mais
        consistente (positiva ou negativamente) com o restante do grupo.
        """
        n = len(historico)
        if n < 3:
            return {num: 0.0 for num in range(1, 26)}

        presenca = np.zeros((25, n))
        for j, concurso in enumerate(historico):
            for num in concurso:
                presenca[num - 1, j] = 1

        with np.errstate(invalid='ignore', divide='ignore'):
            matriz_corr = np.corrcoef(presenca)
        matriz_corr = np.nan_to_num(matriz_corr, nan=0.0)

        corr_media = {}
        for num in range(1, 26):
            linha = matriz_corr[num - 1]
            outros = np.delete(linha, num - 1)
            corr_media[num] = float(np.mean(np.abs(outros))) if len(outros) else 0.0
        return corr_media

    def get_estatisticas_dezena(self, numero):
        """Retorna todas as estatísticas de uma dezena"""
        return {
            'numero': numero,
            'frequencia': self.frequencias.get(numero, 0),
            'frequencia_periodos': {p: self.frequencias_periodos[p].get(numero, 0) for p in self.frequencias_periodos},
            'atraso': self.atrasos.get(numero, 0),
            'atraso_relativo': self.atraso_relativo.get(numero, 0),
            'atraso_categoria': self.atraso_categoria.get(numero, 'Neutra'),
            'frequencia_inteligente': self.frequencia_inteligente.get(numero, 0),
            'ciclo_status': 'Faltante (deve sair)' if numero in self.ciclos.get('dezenas_faltantes_ciclo', set()) else 'Já saiu no ciclo',
            'bayes_forca': self.bayes_forca.get(numero, 0),
            'markov_forca': self.markov_forca.get(numero, 0),
            'cluster': self.clusters_dezena.get(numero, 'Estável'),
            'tendencia': self.tendencias.get(numero, {'tendencia': 'estavel', 'inclinacao': 0}),
            'probabilidade': self.frequencias.get(numero, 0) / (self.total_concursos * 15) if self.total_concursos > 0 else 0
        }

# =====================================================
# MÓDULO 3: MOTOR DE PONTUAÇÃO - LOTOFÁCIL
# =====================================================

class MotorPontuacaoLF:
    """
    Motor de Pontuação — Teoria da Dança das Dezenas (TDD).

    Em vez de perguntar "qual dezena vai sair", este motor observa como o
    conjunto das 25 dezenas está se reorganizando concurso a concurso:
    permanências (núcleo forte), entradas/saídas, energia acumulada,
    movimento (subindo/estável/caindo) e a regularidade dos seus ciclos
    curtos de reaparição. A nota final de cada dezena combina esses
    sinais nos pesos definidos pela TDD.

    IMPORTANTE: assim como o restante do sistema, isto descreve
    tendências e recorrências históricas descritivas. Não há evidência
    de que um sorteio justo da Lotofácil seja previsível, e nenhuma nota
    aqui garante resultado algum em concursos futuros.
    """

    def __init__(self, estatisticas):
        self.estatisticas = estatisticas
        self.pesos = self._definir_pesos()
        self.pontuacoes = self._calcular_pontuacoes()

    def _definir_pesos(self):
        # Princípio 10 - Pontuação Final da Teoria da Dança das Dezenas
        return {
            'frequencia': 0.25,
            'estabilidade': 0.20,
            'coocorrencia': 0.20,
            'movimento': 0.15,
            'energia': 0.10,
            'ciclos': 0.10
        }

    def _calcular_pontuacoes(self):
        estabilidade = self._calcular_estabilidade()
        movimento = self._calcular_movimento()
        ciclos_curtos = self._calcular_ciclos_curtos()
        energia = self._calcular_energia(estabilidade)

        # Guarda os componentes para exploração/depuração na interface
        self.componentes = {
            'estabilidade': estabilidade,
            'movimento': movimento,
            'ciclos_curtos': ciclos_curtos,
            'energia': energia
        }

        pontuacoes = {}
        for num in range(1, 26):
            # Princípio 1 (via Módulo 1) - "Frequência" da TDD reaproveita
            # a Frequência Inteligente multi-janela já calculada
            frequencia = self.estatisticas.frequencia_inteligente.get(num, 0)

            # Princípio 4 - Coocorrência: reaproveita a força média das
            # dependências P(B|A) da Rede Bayesiana (Módulo 5) como medida
            # de o quanto essa dezena "caminha junto" com as demais
            coocorrencia = self.estatisticas.bayes_forca.get(num, 0)

            pontuacao = (
                frequencia * self.pesos['frequencia'] +
                estabilidade[num] * self.pesos['estabilidade'] +
                coocorrencia * self.pesos['coocorrencia'] +
                movimento[num] * self.pesos['movimento'] +
                energia[num] * self.pesos['energia'] +
                ciclos_curtos[num] * self.pesos['ciclos']
            )

            pontuacoes[num] = round(pontuacao * 100, 2)

        return pontuacoes

    def _calcular_estabilidade(self):
        """
        Princípio 1 - Núcleo Permanente: mede a sequência atual de
        concursos consecutivos (contando a partir do mais recente) em
        que a dezena apareceu sem quebra. Dezenas que formam um "núcleo
        forte" — vêm se repetindo concurso após concurso — recebem
        pontuação de estabilidade mais alta.
        """
        historico = self.estatisticas.banco.get_historico_dezenas()
        estabilidade = {}
        for n in range(1, 26):
            sequencia = 0
            for concurso in historico:
                if n in concurso:
                    sequencia += 1
                else:
                    break
            # 5 concursos seguidos já é considerado um núcleo bem forte
            estabilidade[n] = min(sequencia / 5.0, 1.0)
        return estabilidade

    def _calcular_movimento(self):
        """
        Princípio 6 - Matriz de Movimento: classifica cada dezena entre
        Subindo / Estável / Caindo a partir da tendência recente já
        calculada (frequência em janelas mais recentes vs. mais antigas),
        convertendo essa inclinação num score contínuo de 0 a 1 (0 =
        caindo forte, 0.5 = estável, 1 = subindo forte).
        """
        movimento = {}
        inclinacoes = {
            n: self.estatisticas.tendencias.get(n, {}).get('inclinacao', 0)
            for n in range(1, 26)
        }
        maior_abs = max((abs(v) for v in inclinacoes.values()), default=0) or 1.0
        for n in range(1, 26):
            movimento[n] = 0.5 + 0.5 * (inclinacoes[n] / maior_abs)
        return movimento

    def _calcular_ciclos_curtos(self):
        """
        Princípio 9 - Ciclos: observa os intervalos históricos entre as
        aparições de cada dezena e mede o quão regular (baixa
        variabilidade) é esse ciclo — quanto mais regular, maior a
        previsibilidade estatística descritiva (isso não é garantia de
        acerto, apenas uma recorrência histórica).
        """
        historico = self.estatisticas.banco.get_historico_dezenas()
        brutos = {}
        for n in range(1, 26):
            gaps = []
            gap_atual = 0
            apareceu_uma_vez = False
            for concurso in historico:
                if n in concurso:
                    if apareceu_uma_vez:
                        gaps.append(gap_atual)
                    apareceu_uma_vez = True
                    gap_atual = 0
                else:
                    gap_atual += 1

            if len(gaps) >= 2:
                media_gap = float(np.mean(gaps))
                desvio_gap = float(np.std(gaps))
                cv = desvio_gap / media_gap if media_gap > 0 else 1.0
                brutos[n] = 1.0 / (1.0 + cv)
            else:
                brutos[n] = 0.5

        max_v = max(brutos.values()) if brutos else 1.0
        max_v = max_v if max_v > 0 else 1.0
        return {n: v / max_v for n, v in brutos.items()}

    def _calcular_energia(self, estabilidade):
        """
        Princípio 3 - Energia: aumenta com frequência, estabilidade e
        coocorrência; diminui com o atraso. Tudo normalizado de 0 a 1
        no final para poder entrar na nota composta.
        """
        atraso_max = max(self.estatisticas.atrasos.values()) if self.estatisticas.atrasos else 1
        atraso_max = atraso_max if atraso_max > 0 else 1

        brutos = {}
        for n in range(1, 26):
            frequencia = self.estatisticas.frequencia_inteligente.get(n, 0)
            coocorrencia = self.estatisticas.bayes_forca.get(n, 0)
            atraso_norm = self.estatisticas.atrasos.get(n, 0) / atraso_max
            brutos[n] = frequencia + estabilidade[n] + coocorrencia - atraso_norm

        minimo = min(brutos.values()) if brutos else 0.0
        maximo = max(brutos.values()) if brutos else 1.0
        amplitude = (maximo - minimo) or 1.0
        return {n: (v - minimo) / amplitude for n, v in brutos.items()}

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

    def treinar_voting_ensemble(self):
        """
        Módulo 18 - Machine Learning: Voting Ensemble.

        Combina Random Forest e Gradient Boosting por votação suave (soft
        voting): a probabilidade final é a média das probabilidades de
        cada modelo. (Usa Gradient Boosting no lugar de LightGBM/XGBoost/
        CatBoost reais para não depender de bibliotecas externas que talvez
        não estejam disponíveis no ambiente de implantação.)
        """
        try:
            X = self.dados_processados['features']
            y = self.dados_processados['targets']

            if len(X) < 200:
                st.warning("⚠️ Poucos dados para treino confiável (carregue mais concursos).")
                return False

            (X_train, y_train), (X_calib, y_calib), (X_test, y_test) = self._split_cronologico(X, y)

            rf = RandomForestClassifier(n_estimators=150, max_depth=12, min_samples_split=5, random_state=42, n_jobs=-1)
            gb = GradientBoostingClassifier(n_estimators=150, learning_rate=0.1, max_depth=6, random_state=42)

            modelo_base = VotingClassifier(estimators=[('rf', rf), ('gb', gb)], voting='soft')
            modelo_base.fit(X_train, y_train)

            modelo_calibrado = _calibrar_modelo_prefit(modelo_base)
            modelo_calibrado.fit(X_calib, y_calib)

            y_pred = modelo_calibrado.predict(X_test)
            acuracia = accuracy_score(y_test, y_pred)

            self.modelos['voting_ensemble'] = {
                'modelo': modelo_calibrado,
                'acuracia': acuracia
            }

            return True
        except Exception as e:
            st.error(f"Erro ao treinar Voting Ensemble: {e}")
            return False

    def treinar_stacking(self):
        """
        Módulo 18 - Machine Learning: Stacking.

        Usa Random Forest e Gradient Boosting como modelos de base e uma
        Regressão Logística como meta-modelo, que aprende a PONDERAR as
        previsões dos dois (em vez de simplesmente tirar a média, como no
        Voting Ensemble).
        """
        try:
            X = self.dados_processados['features']
            y = self.dados_processados['targets']

            if len(X) < 200:
                st.warning("⚠️ Poucos dados para treino confiável (carregue mais concursos).")
                return False

            (X_train, y_train), (X_calib, y_calib), (X_test, y_test) = self._split_cronologico(X, y)

            rf = RandomForestClassifier(n_estimators=150, max_depth=12, min_samples_split=5, random_state=42, n_jobs=-1)
            gb = GradientBoostingClassifier(n_estimators=150, learning_rate=0.1, max_depth=6, random_state=42)

            modelo_base = StackingClassifier(
                estimators=[('rf', rf), ('gb', gb)],
                final_estimator=LogisticRegression(max_iter=1000),
                cv=3
            )
            modelo_base.fit(X_train, y_train)

            modelo_calibrado = _calibrar_modelo_prefit(modelo_base)
            modelo_calibrado.fit(X_calib, y_calib)

            y_pred = modelo_calibrado.predict(X_test)
            acuracia = accuracy_score(y_test, y_pred)

            self.modelos['stacking'] = {
                'modelo': modelo_calibrado,
                'acuracia': acuracia
            }

            return True
        except Exception as e:
            st.error(f"Erro ao treinar Stacking: {e}")
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

    def prever_probabilidades_dezenas(self):
        """
        Prevê, para cada uma das 25 dezenas, a probabilidade média (entre os
        modelos treinados) de sair no próximo concurso. Diferente de
        `prever_probabilidades`, que avalia um jogo específico já montado,
        este método não recebe um jogo pronto — por isso usa o contexto
        médio dos concursos mais recentes (proporção típica de pares,
        faixas e soma) como pano de fundo neutro para cada dezena.
        """
        if not self.modelos:
            return {}

        max_freq_total = max(self.estatisticas.frequencias.values()) if self.estatisticas.frequencias else 1

        concursos_recentes = self.banco.get_historico_dezenas()[:50]
        if concursos_recentes:
            pares_prop_medio = float(np.mean([contar_pares_lf(c) / 15 for c in concursos_recentes]))
            faixa_baixa_medio = float(np.mean([sum(1 for n in c if n <= 8) / 15 for c in concursos_recentes]))
            faixa_media_medio = float(np.mean([sum(1 for n in c if 9 <= n <= 16) / 15 for c in concursos_recentes]))
            soma_medio = float(np.mean([sum(c) / 25 for c in concursos_recentes]))
        else:
            pares_prop_medio = faixa_baixa_medio = faixa_media_medio = 0.5
            soma_medio = 0.5

        features = []
        for num in range(1, 26):
            vizinhos = [v for v in range(max(1, num - 3), min(25, num + 3) + 1) if v != num]
            proximidade = (np.mean([self.estatisticas.frequencias.get(v, 0) for v in vizinhos]) / max_freq_total) if vizinhos else 0
            features.append([
                self.estatisticas.frequencias.get(num, 0),
                self.estatisticas.frequencias_periodos.get(20, {}).get(num, 0),
                self.estatisticas.atrasos.get(num, 0),
                self.estatisticas.tendencias.get(num, {}).get('inclinacao', 0),
                pares_prop_medio,
                faixa_baixa_medio,
                faixa_media_medio,
                soma_medio,
                proximidade
            ])

        features = np.array(features)

        probs_por_modelo = []
        for nome, info in self.modelos.items():
            modelo = info['modelo']
            probs = modelo.predict_proba(features)[:, 1]
            probs_por_modelo.append(probs)

        if not probs_por_modelo:
            return {}

        probs_media = np.mean(probs_por_modelo, axis=0)
        return {num: float(probs_media[num - 1]) for num in range(1, 26)}

    def gerar_jogos_ia(self, qtd_jogos=3, tamanho_jogo=15, semente=None):
        """
        Gera jogos com base no que os modelos de IA treinados aprenderam:
        usa a probabilidade média prevista para cada dezena como peso em
        uma amostragem ponderada, produzindo `qtd_jogos` jogos distintos
        entre si (em vez de sempre repetir o mesmo Top 15 fixo).
        """
        probs_dezenas = self.prever_probabilidades_dezenas()
        if not probs_dezenas:
            return [], {}

        rng = random.Random(semente)
        dezenas = list(range(1, 26))
        pesos_base = [max(probs_dezenas.get(d, 0.0), 1e-6) for d in dezenas]

        jogos = []
        jogos_set = set()
        tentativas = 0
        max_tentativas = qtd_jogos * 500 + 2000

        while len(jogos) < qtd_jogos and tentativas < max_tentativas:
            tentativas += 1
            pool_restante = list(dezenas)
            pesos_restante = list(pesos_base)
            jogo = []
            for _ in range(tamanho_jogo):
                escolhido = rng.choices(pool_restante, weights=pesos_restante, k=1)[0]
                idx = pool_restante.index(escolhido)
                jogo.append(escolhido)
                pool_restante.pop(idx)
                pesos_restante.pop(idx)

            jogo_ordenado = tuple(sorted(jogo))
            if jogo_ordenado not in jogos_set:
                jogos_set.add(jogo_ordenado)
                jogos.append(list(jogo_ordenado))

        return jogos, probs_dezenas

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

    def testar_pool_fechamento(self, top_n=21, num_testes=50):
        """
        Backtest ponto-no-tempo do POOL FIXO usado na aba de Fechamento
        ("Top N do Ranking"). A aba de Fechamento monta o pool com o
        MotorPontuacaoLF calculado sobre TODO o histórico carregado —
        incluindo os concursos mais recentes — e nunca valida se esse
        corte em N dezenas historicamente deixa de fora dezenas que
        realmente saem. Este método corrige isso replicando a mesma
        lógica anti-vazamento já usada em `testar_estrategia`: para cada
        concurso testado, recalcula o ranking usando só concursos
        estritamente anteriores a ele, e mede quantas das dezenas
        sorteadas ficaram DENTRO e quantas ficaram FORA do Top N daquele
        momento.

        Sem este teste, um pool "ruim" (que sistematicamente deixa de
        fora dezenas frias que voltam a sair) só é percebido depois do
        sorteio — como aconteceu ao conferir o concurso 3758, em que 2
        das 15 dezenas sorteadas (09 e 25) estavam fora do Top 21 usado
        em todos os fechamentos gerados.
        """
        historico = self.banco.concursos  # mais recente primeiro
        testes = historico[:min(num_testes, len(historico))]

        capturadas_lista = []
        fora_lista = []
        pulados = 0

        progress_bar = st.progress(0, text=f"Executando backtest do pool Top {top_n}...")

        for i, concurso in enumerate(testes):
            dezenas_reais = set(concurso['dezenas'])
            concursos_anteriores = historico[i + 1:]

            if len(concursos_anteriores) < self.AQUECIMENTO_MINIMO:
                pulados += 1
                progress_bar.progress((i + 1) / len(testes))
                continue

            banco_pt = _BancoTemporal(concursos_anteriores)
            estatisticas_pt = EstatisticasLFAvancadas(banco_pt)
            pontuacao_pt = MotorPontuacaoLF(estatisticas_pt)
            pool_pt = set(n for n, _ in pontuacao_pt.get_ranking(top_n))

            capturadas_lista.append(len(dezenas_reais & pool_pt))
            fora_lista.append(len(dezenas_reais - pool_pt))

            progress_bar.progress((i + 1) / len(testes))

        progress_bar.empty()

        if pulados:
            st.caption(f"ℹ️ {pulados} concurso(s) pulado(s) por não terem histórico anterior suficiente ({self.AQUECIMENTO_MINIMO}+ concursos).")

        esperado_acaso = 15 * top_n / 25.0

        return {
            'top_n': top_n,
            'total_testes': len(capturadas_lista),
            'media_capturadas': float(np.mean(capturadas_lista)) if capturadas_lista else 0.0,
            'minimo_capturadas': int(min(capturadas_lista)) if capturadas_lista else 0,
            'media_fora_do_pool': float(np.mean(fora_lista)) if fora_lista else 0.0,
            'maximo_fora_do_pool': int(max(fora_lista)) if fora_lista else 0,
            'distribuicao_fora_do_pool': dict(Counter(fora_lista)) if fora_lista else {},
            'esperado_por_acaso': round(esperado_acaso, 2)
        }

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
    if "jogos_fechamento" not in st.session_state:
        st.session_state.jogos_fechamento = []
    if "fechamento_dezenas" not in st.session_state:
        st.session_state.fechamento_dezenas = []
    if "fechamento_metodo" not in st.session_state:
        st.session_state.fechamento_metodo = ""
    if "fechamento_cobertura" not in st.session_state:
        st.session_state.fechamento_cobertura = None
    if "resultado_conferencia" not in st.session_state:
        st.session_state.resultado_conferencia = []
    if "resultado_conferencia_meta" not in st.session_state:
        st.session_state.resultado_conferencia_meta = {}
    if "jogos_ia" not in st.session_state:
        st.session_state.jogos_ia = []
    if "probs_ia_dezenas" not in st.session_state:
        st.session_state.probs_ia_dezenas = {}
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
                        voting_ok = st.session_state.ia.treinar_voting_ensemble()
                        stacking_ok = st.session_state.ia.treinar_stacking()
                        if rf_ok or xgb_ok or voting_ok or stacking_ok:
                            st.session_state.ia_treinada = True
                            st.success("✅ IA treinada com sucesso!")

        if st.session_state.ia and getattr(st.session_state.ia, 'modelos', None):
            with st.expander("🤖 Módulo 18 · Acurácia dos modelos de Machine Learning"):
                st.caption(
                    "Acurácia medida em dados de teste cronologicamente posteriores ao treino "
                    "(nunca vistos pelo modelo). Como cada concurso é um sorteio aleatório, não "
                    "espere acurácia muito acima da taxa-base (~60%, já que em média 15 de 25 "
                    "dezenas saem a cada concurso) — o valor serve para comparar os modelos entre "
                    "si, não como garantia de acerto."
                )
                nomes_modelos = {
                    'random_forest': 'Random Forest',
                    'xgboost': 'Gradient Boosting',
                    'voting_ensemble': 'Voting Ensemble',
                    'stacking': 'Stacking'
                }
                for chave, info in st.session_state.ia.modelos.items():
                    st.metric(nomes_modelos.get(chave, chave), f"{info['acuracia']*100:.1f}%")
        
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
        "🔍 Conferência",
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

            st.markdown("---")
            col3, col4 = st.columns(2)
            with col3:
                st.markdown("### 🧠 Módulo 1 · Frequência Inteligente")
                st.caption("Combinação ponderada das janelas de 5, 10, 20, 30, 50, 100 e 200 concursos.")
                df_freq_int = pd.DataFrame({
                    'Dezena': range(1, 26),
                    'Score': [stats.frequencia_inteligente.get(i, 0) for i in range(1, 26)]
                })
                fig = px.bar(df_freq_int, x='Dezena', y='Score', title='Frequência Inteligente por Dezena',
                            color='Score', color_continuous_scale='Blues')
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

            with col4:
                st.markdown("### 🌡️ Módulo 2 · Atraso Inteligente")
                st.caption("Classificação de cada dezena comparando o atraso atual com o intervalo médio histórico dela.")
                ordem_categorias = ["Muito Quente", "Quente", "Neutra", "Fria", "Muito Fria", "Fóssil"]
                df_cat = pd.DataFrame({
                    'Categoria': ordem_categorias,
                    'Quantidade': [stats.contagem_categorias_atraso.get(c, 0) for c in ordem_categorias]
                })
                fig = px.bar(df_cat, x='Categoria', y='Quantidade', title='Dezenas por Categoria de Atraso',
                            color='Categoria',
                            color_discrete_map={
                                "Muito Quente": "#ff4d4d", "Quente": "#ff9d4d", "Neutra": "#feca57",
                                "Fria": "#4cc9f0", "Muito Fria": "#4d79ff", "Fóssil": "#8888aa"
                            })
                fig.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                with st.expander("Ver categoria de cada dezena"):
                    df_detalhe_cat = pd.DataFrame({
                        'Dezena': range(1, 26),
                        'Categoria': [stats.atraso_categoria.get(i, 'Neutra') for i in range(1, 26)],
                        'Atraso atual': [stats.atrasos.get(i, 0) for i in range(1, 26)]
                    })
                    st.dataframe(df_detalhe_cat, use_container_width=True, hide_index=True)

            st.markdown("---")
            col5, col6 = st.columns(2)
            with col5:
                st.markdown("### 🔄 Módulo 3 · Ciclos")
                ciclos = stats.ciclos
                faltantes = sorted(ciclos.get('dezenas_faltantes_ciclo', set()))
                presentes = sorted(ciclos.get('dezenas_presentes_ciclo', set()))
                st.caption(
                    f"Ciclo em andamento há {ciclos.get('concursos_no_ciclo_atual', 0)} concurso(s) "
                    f"(tamanho médio histórico: {ciclos.get('tamanho_medio_ciclo', 0)} concursos)."
                )
                cc1, cc2 = st.columns(2)
                with cc1:
                    st.metric("Dezenas já saíram no ciclo", len(presentes))
                with cc2:
                    st.metric("Dezenas faltando fechar ciclo", len(faltantes))
                if faltantes:
                    st.markdown("**Faltam para fechar o ciclo:**")
                    st.markdown(formatar_jogo_html_lf(faltantes), unsafe_allow_html=True)
                else:
                    st.success("✅ O ciclo atual já está fechado (todas as 25 dezenas já saíram).")

            with col6:
                st.markdown("### 🧬 Módulo 4 · DNA Estatístico")
                dna = stats.dna_historico
                if dna:
                    st.caption(f"Perfil médio calculado sobre {dna.get('amostras', 0)} concurso(s) do histórico carregado.")
                    dc1, dc2, dc3 = st.columns(3)
                    with dc1:
                        st.metric("Pares (média)", f"{dna.get('pares_media', 0):.1f}")
                        st.metric("Primos (média)", f"{dna.get('primos_media', 0):.1f}")
                    with dc2:
                        st.metric("Fibonacci (média)", f"{dna.get('fibonacci_media', 0):.1f}")
                        st.metric("Moldura (média)", f"{dna.get('moldura_media', 0):.1f}")
                    with dc3:
                        st.metric("Amplitude (média)", f"{dna.get('amplitude_media', 0):.1f}")
                        st.metric("Entropia (média)", f"{dna.get('entropia_media', 0):.3f}")
                    st.caption(f"Salto médio entre dezenas: {dna.get('salto_medio_media', 0):.2f} | Desvio padrão médio das dezenas: {dna.get('desvio_padrao_media', 0):.2f}")

            st.markdown("---")
            st.markdown("### 🔗 Módulos 5 e 6 · Redes Bayesianas & Cadeias de Markov")
            st.caption(
                "Escolha uma dezena para ver quais outras costumam sair JUNTO com ela (Bayes) "
                "e quais costumam sair no concurso SEGUINTE a ela (Markov)."
            )
            dezena_explorar = st.selectbox("Dezena para explorar", list(range(1, 26)), key="dezena_explorar_dependencias")

            col7, col8 = st.columns(2)
            with col7:
                st.markdown(f"**🧠 Módulo 5 · Redes Bayesianas — top dezenas junto com {dezena_explorar:02d}**")
                top_bayes = stats.rede_bayesiana['top_dependentes'].get(dezena_explorar, [])
                if top_bayes:
                    df_bayes = pd.DataFrame(
                        [(f"{b:02d}", f"{p*100:.1f}%") for b, p in top_bayes],
                        columns=["Dezena", f"P(sair | {dezena_explorar:02d} saiu)"]
                    )
                    st.dataframe(df_bayes, use_container_width=True, hide_index=True)
                else:
                    st.caption("Histórico insuficiente para calcular.")

            with col8:
                st.markdown(f"**⛓️ Módulo 6 · Cadeia de Markov — tende a vir depois de {dezena_explorar:02d}**")
                top_markov = stats.cadeia_markov['top_sucessoras'].get(dezena_explorar, [])
                if top_markov:
                    df_markov = pd.DataFrame(
                        [(f"{b:02d}", f"{p*100:.1f}%") for b, p in top_markov],
                        columns=["Dezena", f"P(sair no próximo | {dezena_explorar:02d} saiu)"]
                    )
                    st.dataframe(df_markov, use_container_width=True, hide_index=True)
                else:
                    st.caption("Histórico insuficiente para calcular.")

            st.markdown("---")
            col9, col10 = st.columns(2)
            with col9:
                st.markdown("### 🔀 Módulo 7 · Correlação — pares mais fortes")
                pares = stats.pares_fortes
                if pares.get('top_positivos'):
                    st.caption("Dezenas que mais tendem a sair JUNTAS (correlação positiva):")
                    df_pos = pd.DataFrame(
                        [(f"{a:02d} + {b:02d}", f"{v:.3f}") for a, b, v in pares['top_positivos'][:5]],
                        columns=["Par", "Correlação"]
                    )
                    st.dataframe(df_pos, use_container_width=True, hide_index=True)

                    st.caption("Dezenas que mais tendem a se EVITAR (correlação negativa):")
                    df_neg = pd.DataFrame(
                        [(f"{a:02d} + {b:02d}", f"{v:.3f}") for a, b, v in pares['top_negativos'][:5]],
                        columns=["Par", "Correlação"]
                    )
                    st.dataframe(df_neg, use_container_width=True, hide_index=True)
                else:
                    st.caption("Histórico insuficiente para calcular.")

            with col10:
                st.markdown("### 🧩 Módulo 8 · Clusters")
                st.caption("As 25 dezenas agrupadas por perfil atual (frequência, atraso e tendência).")
                ordem_clusters = ["Quente", "Oscilante", "Estável", "Frio"]
                df_clusters_count = pd.DataFrame({
                    'Grupo': ordem_clusters,
                    'Quantidade': [stats.clusters_contagem.get(g, 0) for g in ordem_clusters]
                })
                fig = px.bar(df_clusters_count, x='Grupo', y='Quantidade', title='Dezenas por Cluster',
                            color='Grupo',
                            color_discrete_map={
                                "Quente": "#ff4d4d", "Oscilante": "#feca57",
                                "Estável": "#4cc9f0", "Frio": "#4d79ff"
                            })
                fig.update_layout(height=320, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                with st.expander("Ver cluster de cada dezena"):
                    df_detalhe_cluster = pd.DataFrame({
                        'Dezena': range(1, 26),
                        'Cluster': [stats.clusters_dezena.get(i, 'Estável') for i in range(1, 26)]
                    })
                    st.dataframe(df_detalhe_cluster, use_container_width=True, hide_index=True)

    # ================= TAB 2: RANKING =================
    with tabs[1]:
        st.markdown("### 🏆 Ranking das Dezenas")
        st.caption(
            "🕺 Motor de Pontuação: **Teoria da Dança das Dezenas** — em vez de tratar cada dezena isoladamente, "
            "avalia como o conjunto de 25 dezenas se reorganiza a cada concurso (permanência, movimento, energia e "
            "ciclos). É uma forma mais estruturada de descrever tendências históricas, não uma previsão garantida."
        )
        
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
                    comp = pontuacao.componentes
                    detalhes = f"""
                    <small style='color:#aaa;'>
                        Freq: {stats_dezena['frequencia']} | 
                        Últimos 20: {freq_periodos.get(20, 0)} | 
                        Atraso: {stats_dezena['atraso']} ({stats_dezena['atraso_categoria']}) | 
                        Freq. Inteligente: {stats_dezena['frequencia_inteligente']:.3f}<br>
                        <em>Dança das Dezenas</em> — Estabilidade: {comp['estabilidade'].get(num, 0):.2f} | 
                        Movimento: {comp['movimento'].get(num, 0):.2f} | 
                        Energia: {comp['energia'].get(num, 0):.2f} | 
                        Ciclo curto: {comp['ciclos_curtos'].get(num, 0):.2f} | 
                        Coocorrência: {stats_dezena['bayes_forca']:.2f} | 
                        Cluster: {stats_dezena['cluster']} | 
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

            # ========= FECHAMENTO COM AS 21 DEZENAS DO RANKING =========
            st.markdown("---")
            st.markdown("### 🔒 Fechamento com as 21 Dezenas do Ranking")
            st.markdown("""
            <div class="lotofacil-highlight">
                <strong>🎯 O que é:</strong> Um fechamento usa um grupo fixo de dezenas
                (aqui, as 21 melhores do ranking) e gera vários jogos de 15 dezenas,
                todos distintos entre si, tentando equilibrar quantas vezes cada
                dezena do grupo aparece ao longo dos jogos gerados.
            </div>
            """, unsafe_allow_html=True)

            ranking_completo = pontuacao.get_ranking(25)
            ranking_top21 = ranking_completo[:21]
            ranking_risco = ranking_completo[21:25]
            dezenas_top21 = sorted([n for n, _ in ranking_top21])

            with st.expander("🧪 Validar este pool no histórico (backtest ponto-no-tempo)", expanded=False):
                st.caption(
                    "O Top 21 acima foi calculado com TODO o histórico carregado. Isso não garante nada "
                    "sobre o próximo concurso — sorteios da Lotofácil são eventos independentes e aleatórios. "
                    "Este teste apenas mostra, olhando para concursos passados (sem usar dados futuros em "
                    "cada ponto testado), quantas das 15 dezenas sorteadas historicamente ficaram FORA de um "
                    "corte Top 21 — ajuda a dimensionar o risco de deixar dezenas de fora, não a prever o futuro."
                )
                total_concursos_pool = len(st.session_state.banco_dados.concursos) if st.session_state.banco_dados else 0
                max_testes_pool = min(200, max(10, total_concursos_pool - 30))
                valor_padrao_pool = min(50, max_testes_pool)
                n_testes_pool = st.slider("Concursos a testar", 10, max_testes_pool, valor_padrao_pool, key="n_testes_pool_fechamento")
                if st.button("Rodar backtest do pool Top 21", key="btn_backtest_pool_fechamento"):
                    backtester = BacktestsLF(st.session_state.banco_dados, stats, st.session_state.filtros)
                    resultado_pool = backtester.testar_pool_fechamento(top_n=21, num_testes=n_testes_pool)
                    st.session_state.resultado_backtest_pool = resultado_pool

                resultado_pool = st.session_state.get("resultado_backtest_pool")
                if resultado_pool and resultado_pool['total_testes'] > 0:
                    colb1, colb2, colb3 = st.columns(3)
                    with colb1:
                        st.metric("Média dentro do pool", f"{resultado_pool['media_capturadas']:.1f} / 15")
                    with colb2:
                        st.metric("Esperado só por acaso", f"{resultado_pool['esperado_por_acaso']:.1f} / 15")
                    with colb3:
                        st.metric("Pior caso já visto (fora do pool)", resultado_pool['maximo_fora_do_pool'])
                    diferenca = resultado_pool['media_capturadas'] - resultado_pool['esperado_por_acaso']
                    if diferenca <= 0.3:
                        st.warning(
                            f"⚠️ Nos {resultado_pool['total_testes']} concursos testados, o Top 21 capturou em média "
                            f"{resultado_pool['media_capturadas']:.2f} das 15 dezenas — praticamente igual ao "
                            f"{resultado_pool['esperado_por_acaso']:.2f} esperado por puro acaso (21/25 das dezenas). "
                            "Ou seja, este ranking não mostrou vantagem histórica mensurável sobre escolher 21 "
                            "dezenas ao acaso; trate os jogos gerados como exploratórios, não como previsão."
                        )
                    else:
                        st.info(
                            f"Nos {resultado_pool['total_testes']} concursos testados, o Top 21 capturou em média "
                            f"{resultado_pool['media_capturadas']:.2f}/15 dezenas, um pouco acima do "
                            f"{resultado_pool['esperado_por_acaso']:.2f} esperado por acaso. Mesmo assim, em até "
                            f"{resultado_pool['maximo_fora_do_pool']} dezena(s) o sorteio real ficou fora do pool "
                            "em algum concurso testado — considere isso ao decidir o tamanho do pool."
                        )

            st.markdown("**⚠️ Zona de risco (dezenas logo fora do Top 21):**")
            if ranking_risco:
                partes_risco = []
                for num, score in ranking_risco:
                    saiu_ultimo = stats.repetiu_ultimo_concurso.get(num, False)
                    marcador = " 🔥 saiu no último concurso" if saiu_ultimo else ""
                    partes_risco.append(f"Dezena {num:02d} (score {score:.2f}){marcador}")
                st.caption(" | ".join(partes_risco))
            else:
                st.caption("Nenhuma dezena pontuada fora do Top 21.")

            incluir_seguranca = st.checkbox(
                "🛡️ Incluir automaticamente dezenas da zona de risco que saíram no último concurso",
                value=False,
                key="incluir_seguranca_fechamento",
                help="Troca a dezena de menor score do Top 21 (entre as que NÃO saíram no último concurso) por dezenas da zona de risco que saíram, reduzindo a chance de deixar de fora uma dezena 'quente' recente."
            )

            dezenas_fechamento = list(dezenas_top21)
            if incluir_seguranca:
                candidatas_seguranca = [num for num, _ in ranking_risco if stats.repetiu_ultimo_concurso.get(num, False)]
                if candidatas_seguranca:
                    top21_por_score_asc = sorted(ranking_top21, key=lambda x: x[1])
                    trocaveis = [num for num, _ in top21_por_score_asc if not stats.repetiu_ultimo_concurso.get(num, False)]

                    for candidata in candidatas_seguranca:
                        if not trocaveis:
                            break
                        removida = trocaveis.pop(0)
                        if removida in dezenas_fechamento:
                            dezenas_fechamento.remove(removida)
                            dezenas_fechamento.append(candidata)
                            st.info(f"🔄 Troca de segurança: dezena {removida:02d} (Top 21) substituída pela dezena {candidata:02d} (zona de risco, saiu no último concurso).")

                    dezenas_fechamento = sorted(set(dezenas_fechamento))
                else:
                    st.caption("Nenhuma dezena da zona de risco saiu no último concurso — nenhuma troca necessária.")

            if len(dezenas_fechamento) < 21:
                st.warning(f"⚠️ Só há {len(dezenas_fechamento)} dezenas pontuadas disponíveis (menos que 21).")

            st.markdown(f"**Dezenas usadas no fechamento ({len(dezenas_fechamento)}):**")
            st.markdown(formatar_jogo_html_lf(dezenas_fechamento), unsafe_allow_html=True)

            col_f1, col_f2 = st.columns(2)
            with col_f1:
                qtd_fechamento = st.select_slider(
                    "Quantidade de jogos do fechamento",
                    options=[5, 10, 15, 20, 25, 30, 35, 40, 45, 50],
                    value=10,
                    key="qtd_fechamento_slider"
                )
            with col_f2:
                max_combinacoes = math.comb(len(dezenas_fechamento), 15) if len(dezenas_fechamento) >= 15 else 0
                st.metric("Combinações possíveis (21 escolhe 15)", f"{max_combinacoes:,}".replace(",", "."))

            metodo_fechamento = st.radio(
                "Método do fechamento",
                ["⚖️ Balanceado (equilibra frequência das dezenas)",
                 "🧩 Cobertura otimizada (Greedy Set-Cover aproximado)",
                 "🧬 Algoritmo Genético (evolui pelo Meta Score)"],
                key="metodo_fechamento_radio",
                help="Cobertura tenta escolher jogos que, juntos, cubram o maior número possível de combinações de "
                     "dezenas dentro do pool (heurística por amostragem, não garantia formal). O Algoritmo Genético "
                     "evolui uma população de jogos por gerações, usando o Meta Score (Módulo 19) como aptidão."
            )
            usar_cobertura = metodo_fechamento.startswith("🧩")
            usar_genetico = metodo_fechamento.startswith("🧬")

            if usar_cobertura:
                k_garantia = st.slider(
                    "Tamanho do subconjunto de garantia (k)", 8, 14, 11,
                    help="O algoritmo tenta priorizar jogos que cubram combinações de k dezenas dentro do pool. "
                         "Valores menores de k são mais fáceis de cobrir bem; valores maiores (13, 14) exigem muito mais jogos."
                )

            if usar_genetico:
                colg1, colg2 = st.columns(2)
                with colg1:
                    geracoes_genetico = st.slider("Gerações", 10, 100, 40, key="geracoes_genetico_slider")
                with colg2:
                    populacao_genetica = st.slider("Tamanho da população", 20, 150, 60, key="populacao_genetica_slider")

            distancia_minima_jogos = st.slider(
                "📏 Módulo 16 · Distância mínima entre jogos (dezenas diferentes)",
                0, 12, 0, key="distancia_minima_slider",
                help="0 = desligado. O estudo recomenda mínimo de 6 dezenas diferentes entre quaisquer dois jogos do "
                     "fechamento (ideal 7 ou 8), para evitar jogos praticamente 'clones' uns dos outros."
            )

            with st.expander("🧪 Filtros de padrão histórico (opcional)"):
                aplicar_filtros_fechamento = st.checkbox("Aplicar filtros ao gerar os jogos", value=False, key="aplicar_filtros_fechamento_chk")
                colfa, colfb = st.columns(2)
                with colfa:
                    pares_min_f = st.slider("Pares mínimo", 0, 15, 7, key="pares_min_fechamento")
                    pares_max_f = st.slider("Pares máximo", 0, 15, 8, key="pares_max_fechamento")
                    primos_min_f = st.slider("Primos mínimo", 0, 9, 3, key="primos_min_fechamento")
                    primos_max_f = st.slider("Primos máximo", 0, 9, 5, key="primos_max_fechamento")
                with colfb:
                    soma_min_f = st.slider("Soma mínima", 150, 300, 170, key="soma_min_fechamento")
                    soma_max_f = st.slider("Soma máxima", 150, 300, 220, key="soma_max_fechamento")
                    repetidas_min_f = st.slider("Repetidas do último concurso (mín.)", 0, 15, 4, key="repetidas_min_fechamento")
                    repetidas_max_f = st.slider("Repetidas do último concurso (máx.)", 0, 15, 6, key="repetidas_max_fechamento")

            with st.expander("🌡️ Módulo 2 · Quotas por categoria de Atraso Inteligente (opcional)"):
                st.caption(
                    "Limita automaticamente quantas dezenas de cada categoria de atraso "
                    "(Muito Quente, Quente, Neutra, Fria, Muito Fria, Fóssil) podem entrar em cada jogo gerado."
                )
                aplicar_quotas_atraso = st.checkbox(
                    "Aplicar quotas de atraso inteligente ao gerar os jogos",
                    value=False, key="aplicar_quotas_atraso_chk"
                )
                categorias_quota = ["Muito Quente", "Quente", "Neutra", "Fria", "Muito Fria", "Fóssil"]
                contagem_pool = contar_categorias_atraso_lf(dezenas_fechamento, stats.atraso_categoria)
                quotas_atraso = {}
                colq = st.columns(3)
                for i, categoria in enumerate(categorias_quota):
                    with colq[i % 3]:
                        st.caption(f"{categoria} — {contagem_pool.get(categoria, 0)} dezena(s) no pool")
                        minimo_q = st.slider(f"Mín. {categoria}", 0, 15, 0, key=f"quota_min_{categoria}")
                        maximo_q = st.slider(f"Máx. {categoria}", 0, 15, 15, key=f"quota_max_{categoria}")
                        quotas_atraso[categoria] = (min(minimo_q, maximo_q), max(minimo_q, maximo_q))

            with st.expander("🧬 Módulo 4 · Filtro de similaridade de DNA (opcional)"):
                st.caption(
                    "Compara o DNA do jogo gerado (pares, primos, fibonacci, moldura/centro, amplitude, "
                    "desvio padrão, salto médio e entropia) com o perfil médio histórico, descartando jogos "
                    "estatisticamente muito atípicos."
                )
                aplicar_filtro_dna = st.checkbox(
                    "Aplicar filtro de similaridade de DNA ao gerar os jogos",
                    value=False, key="aplicar_filtro_dna_chk"
                )
                similaridade_minima_dna = st.slider(
                    "Similaridade mínima exigida (0 = qualquer jogo, 1 = idêntico ao perfil médio)",
                    0.0, 1.0, 0.5, step=0.05, key="similaridade_minima_dna_slider"
                )

            with st.expander("🧩 Módulo 8 · Quotas por Cluster (opcional)"):
                st.caption(
                    "Limita automaticamente quantas dezenas de cada cluster "
                    "(Quente, Frio, Oscilante, Estável) podem entrar em cada jogo gerado."
                )
                aplicar_quotas_cluster = st.checkbox(
                    "Aplicar quotas de cluster ao gerar os jogos",
                    value=False, key="aplicar_quotas_cluster_chk"
                )
                grupos_cluster = ["Quente", "Frio", "Oscilante", "Estável"]
                contagem_pool_cluster = contar_clusters_jogo(dezenas_fechamento, stats.clusters_dezena)
                quotas_cluster = {}
                colc = st.columns(4)
                for i, grupo in enumerate(grupos_cluster):
                    with colc[i % 4]:
                        st.caption(f"{grupo} — {contagem_pool_cluster.get(grupo, 0)} no pool")
                        minimo_c = st.slider(f"Mín. {grupo}", 0, 15, 0, key=f"cluster_min_{grupo}")
                        maximo_c = st.slider(f"Máx. {grupo}", 0, 15, 15, key=f"cluster_max_{grupo}")
                        quotas_cluster[grupo] = (min(minimo_c, maximo_c), max(minimo_c, maximo_c))

            with st.expander("🏆 Módulo 19 · Meta Score — corte de qualidade (opcional)"):
                st.caption(
                    "Combina, numa única nota de 0 a 100 por jogo, a pontuação média do Motor "
                    "(Módulos 1, 2, 3, 5, 6, 7), a similaridade de DNA (Módulo 4) e, se a IA já "
                    "tiver sido treinada, a probabilidade média prevista pelo Machine Learning "
                    "(Módulo 18). Só entram no fechamento os jogos com nota igual ou acima do corte."
                )
                aplicar_corte_meta_score = st.checkbox(
                    "Aplicar corte de Meta Score ao gerar os jogos",
                    value=False, key="aplicar_corte_meta_score_chk"
                )
                corte_meta_score = st.slider(
                    "Nota mínima exigida (0-100)", 0, 100, 60, key="corte_meta_score_slider"
                )
                if not (st.session_state.ia and getattr(st.session_state.ia, 'modelos', None)):
                    st.caption("ℹ️ IA ainda não treinada — a nota vai usar só Motor + DNA (sem o componente de ML).")

            if st.button("🔒 GERAR FECHAMENTO", use_container_width=True, type="primary", key="gerar_fechamento_btn"):
                if len(dezenas_fechamento) < 15:
                    st.error("❌ É preciso de pelo menos 15 dezenas pontuadas para gerar o fechamento.")
                else:
                    filtros_ativos = []
                    if aplicar_filtros_fechamento:
                        ultimo_concurso = st.session_state.banco_dados.get_ultimo_concurso()
                        ultimo_dezenas = ultimo_concurso['dezenas'] if ultimo_concurso else None
                        filtros_ativos.append(lambda j: passa_filtros_qualidade_lf(
                            j, ultimo_concurso=ultimo_dezenas,
                            pares_min=min(pares_min_f, pares_max_f), pares_max=max(pares_min_f, pares_max_f),
                            soma_min=min(soma_min_f, soma_max_f), soma_max=max(soma_min_f, soma_max_f),
                            primos_min=min(primos_min_f, primos_max_f), primos_max=max(primos_min_f, primos_max_f),
                            repetidas_min=min(repetidas_min_f, repetidas_max_f), repetidas_max=max(repetidas_min_f, repetidas_max_f)
                        ))
                    if aplicar_quotas_atraso:
                        filtros_ativos.append(lambda j: respeita_quotas_atraso_lf(j, stats.atraso_categoria, quotas_atraso))
                    if aplicar_filtro_dna:
                        filtros_ativos.append(lambda j: passa_filtro_dna_lf(j, stats.dna_historico, similaridade_minima_dna))
                    if aplicar_quotas_cluster:
                        filtros_ativos.append(lambda j: respeita_quotas_cluster_lf(j, stats.clusters_dezena, quotas_cluster))
                    if aplicar_corte_meta_score:
                        filtros_ativos.append(lambda j: passa_meta_score_lf(
                            j, stats, pontuacao, corte=corte_meta_score, ia=st.session_state.ia
                        ))

                    filtro_fn = None
                    if filtros_ativos:
                        filtro_fn = lambda j: all(f(j) for f in filtros_ativos)

                    with st.spinner(f"Gerando fechamento com {qtd_fechamento} jogos distintos..."):
                        if usar_cobertura:
                            jogos_fechamento, cobertura_estimada = gerar_fechamento_cobertura_lf(
                                dezenas_fechamento, qtd_fechamento, tamanho_jogo=15,
                                k_garantia=k_garantia, filtro_fn=filtro_fn
                            )
                        elif usar_genetico:
                            jogos_fechamento = gerar_fechamento_genetico_lf(
                                dezenas_fechamento, qtd_fechamento, stats, pontuacao,
                                ia=st.session_state.ia, geracoes=geracoes_genetico,
                                tamanho_populacao=populacao_genetica,
                                distancia_minima=distancia_minima_jogos or 0,
                                filtro_fn=filtro_fn
                            )
                            cobertura_estimada = None
                        else:
                            jogos_fechamento = gerar_fechamento_lf(
                                dezenas_fechamento, qtd_fechamento, tamanho_jogo=15,
                                filtro_fn=filtro_fn, distancia_minima=distancia_minima_jogos or None
                            )
                            cobertura_estimada = None

                        if jogos_fechamento:
                            st.session_state.jogos_fechamento = jogos_fechamento
                            st.session_state.fechamento_dezenas = dezenas_fechamento
                            st.session_state.fechamento_metodo = metodo_fechamento
                            st.session_state.fechamento_cobertura = cobertura_estimada
                            msg = f"✅ {len(jogos_fechamento)} jogos distintos gerados!"
                            if cobertura_estimada is not None:
                                msg += f" Cobertura estimada (amostral, k={k_garantia}): {cobertura_estimada*100:.1f}%"
                            st.success(msg)
                        else:
                            st.error("❌ Não foi possível gerar o fechamento com os filtros/parâmetros atuais. Tente relaxar os filtros.")

            if st.session_state.jogos_fechamento:
                jogos_fechamento = st.session_state.jogos_fechamento
                st.markdown(f"### 📋 Jogos do Fechamento ({len(jogos_fechamento)})")
                if st.session_state.fechamento_cobertura is not None:
                    st.caption(f"Método: {st.session_state.fechamento_metodo} | Cobertura estimada (amostral): {st.session_state.fechamento_cobertura*100:.1f}%")
                elif st.session_state.fechamento_metodo:
                    st.caption(f"Método: {st.session_state.fechamento_metodo}")

                # Balanceamento: quantas vezes cada dezena apareceu nos jogos
                contagem_final = Counter()
                for j in jogos_fechamento:
                    contagem_final.update(j)
                df_balanco = pd.DataFrame({
                    'Dezena': list(contagem_final.keys()),
                    'Aparições': list(contagem_final.values())
                }).sort_values('Dezena')

                if len(jogos_fechamento) > 1:
                    distancias_pares = [
                        calcular_distancia_jogos_lf(jogos_fechamento[i], jogos_fechamento[j])
                        for i in range(len(jogos_fechamento))
                        for j in range(i + 1, len(jogos_fechamento))
                    ]
                    st.caption(
                        f"📏 Módulo 16 · Distância entre jogos — mínima: {min(distancias_pares)} | "
                        f"média: {np.mean(distancias_pares):.1f} dezenas diferentes"
                    )

                with st.expander("⚖️ Balanceamento das dezenas no fechamento"):
                    fig = px.bar(df_balanco, x='Dezena', y='Aparições',
                                title='Quantas vezes cada dezena aparece nos jogos do fechamento')
                    st.plotly_chart(fig, use_container_width=True)

                for i, jogo in enumerate(jogos_fechamento):
                    pares = contar_pares_lf(jogo)
                    soma = sum(jogo)
                    meta = calcular_meta_score_jogo(jogo, stats, pontuacao, ia=st.session_state.ia)
                    st.markdown(f"""
                    <div class='card'>
                        📌 <strong>Jogo {i+1:02d}</strong>
                        <span style='float: right;'><strong>🏆 Meta Score: {meta['nota']:.1f}</strong></span><br>
                        {formatar_jogo_html_lf(jogo)}<br>
                        <small style='color:#aaa;'>⚖️ {pares}p/{15-pares}i | ➕ {soma} | Motor: {meta['motor_medio']:.1f} | DNA: {meta['dna_similaridade']:.1f}{' | ML: ' + str(meta['ml_probabilidade']) if meta['ml_probabilidade'] is not None else ''}</small>
                    </div>
                    """, unsafe_allow_html=True)

                col_fs1, col_fs2, col_fs3 = st.columns(3)
                with col_fs1:
                    if st.button("💾 Salvar Fechamento", key="salvar_fechamento_btn", use_container_width=True):
                        arquivo, jogo_id = salvar_jogos_lf_elite(jogos_fechamento, {
                            'tipo': 'fechamento_ranking_21',
                            'metodo': st.session_state.fechamento_metodo,
                            'cobertura_estimada': st.session_state.fechamento_cobertura,
                            'dezenas_pool': st.session_state.fechamento_dezenas,
                            'qtd_jogos': len(jogos_fechamento)
                        })
                        if arquivo:
                            st.success(f"✅ Fechamento salvo! ID: {jogo_id}")
                with col_fs2:
                    df_export_fech = pd.DataFrame({
                        'Jogo': range(1, len(jogos_fechamento) + 1),
                        'Dezenas': [', '.join(f'{d:02d}' for d in j) for j in jogos_fechamento],
                        'Meta Score': [calcular_meta_score_jogo(j, stats, pontuacao, ia=st.session_state.ia)['nota'] for j in jogos_fechamento],
                        'Pares': [contar_pares_lf(j) for j in jogos_fechamento],
                        'Soma': [sum(j) for j in jogos_fechamento],
                        'Primos': [contar_primos_lf(j) for j in jogos_fechamento],
                        'Consecutivos': [contar_consecutivos_lf(j) for j in jogos_fechamento]
                    })
                    st.download_button(
                        label="📥 Exportar CSV",
                        data=df_export_fech.to_csv(index=False),
                        file_name=f"fechamento_lf_21_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key="download_fechamento_csv"
                    )
                with col_fs3:
                    if st.button("🗑️ Limpar Fechamento", key="limpar_fechamento_btn", use_container_width=True):
                        st.session_state.jogos_fechamento = []
                        st.session_state.fechamento_metodo = ""
                        st.session_state.fechamento_cobertura = None
                        st.rerun()

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

                # ---- Geração de jogos segundo o que a IA aprendeu ----
                st.markdown("---")
                st.markdown("### 🎯 Gerar Jogos Segundo a IA Treinada")
                st.markdown("""
                <div class="ia-lf-highlight">
                    Usa a probabilidade que os modelos treinados calcularam para cada uma das
                    25 dezenas saírem no próximo concurso como peso para montar os jogos —
                    dezenas com maior probabilidade prevista tendem a aparecer mais nos jogos
                    gerados, mas o resultado não é sempre o mesmo Top 15 fixo.
                </div>
                """, unsafe_allow_html=True)

                qtd_jogos_ia = st.slider("Quantidade de jogos a gerar", 1, 10, 3, key="qtd_jogos_ia_slider")

                if st.button("🧠 GERAR JOGOS COM A IA", use_container_width=True, type="primary", key="gerar_jogos_ia_btn"):
                    with st.spinner("Calculando probabilidades e montando os jogos..."):
                        jogos_ia_gerados, probs_dezenas_ia = ia.gerar_jogos_ia(qtd_jogos=qtd_jogos_ia, tamanho_jogo=15)
                        if jogos_ia_gerados:
                            st.session_state.jogos_ia = jogos_ia_gerados
                            st.session_state.probs_ia_dezenas = probs_dezenas_ia
                            st.success(f"✅ {len(jogos_ia_gerados)} jogo(s) gerado(s) com base no treinamento da IA!")
                        else:
                            st.error("❌ Não foi possível gerar jogos com os modelos atuais.")

                if st.session_state.get("jogos_ia"):
                    jogos_ia = st.session_state.jogos_ia
                    probs_dezenas = st.session_state.get("probs_ia_dezenas", {})

                    st.markdown(f"#### 📋 Jogos Gerados pela IA ({len(jogos_ia)})")
                    for i, jogo in enumerate(jogos_ia):
                        pares = contar_pares_lf(jogo)
                        soma = sum(jogo)
                        prob_media_jogo = np.mean([probs_dezenas.get(d, 0) for d in jogo]) * 100 if probs_dezenas else 0
                        st.markdown(f"""
                        <div class='card'>
                            🧠 <strong>Jogo IA {i+1:02d}</strong><br>
                            {formatar_jogo_html_lf(jogo)}<br>
                            <small style='color:#aaa;'>⚖️ {pares}p/{15-pares}i | ➕ {soma} | 📈 Prob. média prevista: {prob_media_jogo:.1f}%</small>
                        </div>
                        """, unsafe_allow_html=True)

                    if probs_dezenas:
                        with st.expander("📊 Probabilidade prevista por dezena (próximo concurso)"):
                            df_probs = pd.DataFrame({
                                'Dezena': list(probs_dezenas.keys()),
                                'Probabilidade (%)': [v * 100 for v in probs_dezenas.values()]
                            }).sort_values('Probabilidade (%)', ascending=False)
                            fig = px.bar(df_probs, x='Dezena', y='Probabilidade (%)',
                                        title='Probabilidade prevista pela IA para cada dezena')
                            st.plotly_chart(fig, use_container_width=True)

                    col_ia1, col_ia2, col_ia3 = st.columns(3)
                    with col_ia1:
                        if st.button("💾 Salvar Jogos da IA", key="salvar_jogos_ia_btn", use_container_width=True):
                            arquivo, jogo_id = salvar_jogos_lf_elite(jogos_ia, {
                                'tipo': 'jogos_ia_treinada',
                                'modelos_usados': list(ia.modelos.keys()),
                                'qtd_jogos': len(jogos_ia)
                            })
                            if arquivo:
                                st.success(f"✅ Jogos da IA salvos! ID: {jogo_id}")
                    with col_ia2:
                        df_export_ia = pd.DataFrame({
                            'Jogo': range(1, len(jogos_ia) + 1),
                            'Dezenas': [', '.join(f'{d:02d}' for d in j) for j in jogos_ia],
                            'Pares': [contar_pares_lf(j) for j in jogos_ia],
                            'Soma': [sum(j) for j in jogos_ia],
                            'Prob. média prevista (%)': [round(np.mean([probs_dezenas.get(d, 0) for d in j]) * 100, 2) for j in jogos_ia]
                        })
                        st.download_button(
                            label="📥 Exportar CSV",
                            data=df_export_ia.to_csv(index=False),
                            file_name=f"jogos_ia_lf_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True,
                            key="download_jogos_ia_csv"
                        )
                    with col_ia3:
                        if st.button("🗑️ Limpar Jogos da IA", key="limpar_jogos_ia_btn", use_container_width=True):
                            st.session_state.jogos_ia = []
                            st.session_state.probs_ia_dezenas = {}
                            st.rerun()
            else:
                st.info("ℹ️ Treine ao menos um modelo (Random Forest ou XGBoost) nesta aba para poder gerar jogos com base na IA.")

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

    # ================= TAB 7: CONFERÊNCIA =================
    with tabs[6]:
        st.markdown("### 🔍 Conferência de Jogos com Concursos Anteriores")
        st.markdown("""
        <div class="lotofacil-highlight">
            <strong>🎯 O que é:</strong> Confira quantos acertos os jogos que você gerou (ou salvou)
            teriam feito nos concursos já sorteados da Lotofácil — para avaliar o desempenho real
            de uma estratégia antes de apostar de fato.
        </div>
        """, unsafe_allow_html=True)

        banco = st.session_state.banco_dados
        total_concursos_disp = len(banco.concursos) if banco else 0

        if not banco or total_concursos_disp == 0:
            st.warning("⚠️ Nenhum histórico de concursos carregado ainda.")
        else:
            # ---- 1) Escolha da origem dos jogos a conferir ----
            st.markdown("#### 1️⃣ Escolha os jogos a conferir")
            origem_jogos = st.radio(
                "Origem dos jogos",
                ["🎲 Jogos gerados na sessão (Gerador Premium)",
                 "🔒 Jogos do fechamento (Ranking)",
                 "💾 Jogos salvos (arquivo)",
                 "✍️ Colar jogos manualmente"],
                key="origem_jogos_conferencia"
            )

            jogos_para_conferir = []
            rotulo_origem = ""

            if origem_jogos.startswith("🎲"):
                jogos_para_conferir = st.session_state.get("jogos_gerados", [])
                rotulo_origem = "Gerador Premium (sessão atual)"
                if not jogos_para_conferir:
                    st.info("Nenhum jogo gerado nesta sessão ainda. Vá até a aba 🎲 Gerador Premium.")

            elif origem_jogos.startswith("🔒"):
                jogos_para_conferir = st.session_state.get("jogos_fechamento", [])
                rotulo_origem = "Fechamento (Ranking)"
                if not jogos_para_conferir:
                    st.info("Nenhum fechamento gerado nesta sessão ainda. Vá até a aba 🏆 Ranking.")

            elif origem_jogos.startswith("💾"):
                lista_salvos = carregar_jogos_lf_elite()
                if not lista_salvos:
                    st.info("Nenhum jogo salvo encontrado.")
                else:
                    opcoes_salvos = {
                        f"{s['id']} • {s['data_geracao'][:19]} • {len(s['jogos'])} jogo(s)": s
                        for s in lista_salvos
                    }
                    escolha_salvo = st.selectbox("Selecione o arquivo salvo", list(opcoes_salvos.keys()), key="select_salvo_conferencia")
                    salvo_selecionado = opcoes_salvos[escolha_salvo]
                    jogos_para_conferir = [j if isinstance(j, list) else [int(x) for x in j.split(",")] for j in salvo_selecionado['jogos']]
                    rotulo_origem = f"Salvo {salvo_selecionado['id']}"

            else:  # Colar manualmente
                texto_manual = st.text_area(
                    "Um jogo por linha, dezenas separadas por vírgula (ex.: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15)",
                    height=150, key="texto_jogos_manual_conferencia"
                )
                if texto_manual.strip():
                    jogos_para_conferir = []
                    linhas_invalidas = 0
                    for linha in texto_manual.strip().splitlines():
                        linha = linha.strip()
                        if not linha:
                            continue
                        try:
                            dezenas_linha = sorted(set(int(x.strip()) for x in linha.split(",") if x.strip()))
                            if all(1 <= d <= 25 for d in dezenas_linha) and len(dezenas_linha) >= 10:
                                jogos_para_conferir.append(dezenas_linha)
                            else:
                                linhas_invalidas += 1
                        except ValueError:
                            linhas_invalidas += 1
                    rotulo_origem = "Colado manualmente"
                    if linhas_invalidas:
                        st.warning(f"⚠️ {linhas_invalidas} linha(s) ignorada(s) por formato inválido.")

            if jogos_para_conferir:
                st.success(f"✅ {len(jogos_para_conferir)} jogo(s) prontos para conferência ({rotulo_origem}).")

                # ---- 2) Escolha do período de concursos ----
                st.markdown("#### 2️⃣ Escolha os concursos para conferir")
                periodo_conferencia = st.radio(
                    "Período",
                    ["Somente o último concurso", "Últimos N concursos", "Todo o histórico carregado"],
                    horizontal=True,
                    key="periodo_conferencia"
                )

                if periodo_conferencia == "Somente o último concurso":
                    concursos_alvo = banco.concursos[:1]
                elif periodo_conferencia == "Últimos N concursos":
                    n_concursos = st.slider("Quantidade de concursos mais recentes", 1, total_concursos_disp, min(20, total_concursos_disp), key="n_concursos_conferencia")
                    concursos_alvo = banco.concursos[:n_concursos]
                else:
                    concursos_alvo = banco.concursos

                if st.button("🔍 CONFERIR JOGOS", use_container_width=True, type="primary", key="conferir_jogos_btn"):
                    with st.spinner(f"Conferindo {len(jogos_para_conferir)} jogo(s) em {len(concursos_alvo)} concurso(s)..."):
                        linhas_resultado = []
                        for i, jogo in enumerate(jogos_para_conferir):
                            jogo_set = set(jogo)
                            melhor_acertos = -1
                            melhor_concurso = None
                            acertos_ultimo = None
                            for j, concurso in enumerate(concursos_alvo):
                                acertos = len(jogo_set & set(concurso['dezenas']))
                                if j == 0:
                                    acertos_ultimo = acertos
                                if acertos > melhor_acertos:
                                    melhor_acertos = acertos
                                    melhor_concurso = concurso['numero']
                            linhas_resultado.append({
                                'Jogo': i + 1,
                                'Dezenas': ', '.join(f'{d:02d}' for d in jogo),
                                'Acertos no último concurso': acertos_ultimo,
                                'Melhor resultado no período': melhor_acertos,
                                'Concurso do melhor resultado': melhor_concurso
                            })

                        st.session_state.resultado_conferencia = linhas_resultado
                        st.session_state.resultado_conferencia_meta = {
                            'origem': rotulo_origem,
                            'periodo': periodo_conferencia,
                            'qtd_concursos': len(concursos_alvo)
                        }

            if st.session_state.get("resultado_conferencia"):
                linhas_resultado = st.session_state.resultado_conferencia
                meta = st.session_state.get("resultado_conferencia_meta", {})
                df_resultado = pd.DataFrame(linhas_resultado)

                st.markdown("---")
                st.markdown(f"### 📋 Resultado da Conferência — {meta.get('origem', '')}")
                st.caption(f"Período: {meta.get('periodo', '')} ({meta.get('qtd_concursos', 0)} concurso(s) analisados)")

                melhores = df_resultado['Melhor resultado no período']
                col_r1, col_r2, col_r3, col_r4 = st.columns(4)
                with col_r1:
                    st.metric("🏆 Melhor acerto geral", int(melhores.max()) if len(melhores) else 0)
                with col_r2:
                    st.metric("📊 Média de acertos", f"{melhores.mean():.1f}" if len(melhores) else "0")
                with col_r3:
                    qtd_14_mais = int((melhores >= 14).sum())
                    st.metric("🎯 Jogos com 14+ acertos", qtd_14_mais)
                with col_r4:
                    qtd_15 = int((melhores == 15).sum())
                    st.metric("🏅 Jogos com 15 acertos", qtd_15)

                with st.expander("📈 Distribuição de acertos (melhor resultado por jogo)"):
                    dist = Counter(melhores.tolist())
                    df_dist = pd.DataFrame({
                        'Acertos': list(dist.keys()),
                        'Quantidade de jogos': list(dist.values())
                    }).sort_values('Acertos')
                    fig = px.bar(df_dist, x='Acertos', y='Quantidade de jogos',
                                title='Distribuição de acertos entre os jogos conferidos')
                    st.plotly_chart(fig, use_container_width=True)

                st.dataframe(df_resultado, use_container_width=True, hide_index=True)

                col_cd1, col_cd2 = st.columns(2)
                with col_cd1:
                    st.download_button(
                        label="📥 Exportar Conferência (CSV)",
                        data=df_resultado.to_csv(index=False),
                        file_name=f"conferencia_lf_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key="download_conferencia_csv"
                    )
                with col_cd2:
                    if st.button("🗑️ Limpar Resultado", key="limpar_conferencia_btn", use_container_width=True):
                        st.session_state.resultado_conferencia = []
                        st.session_state.resultado_conferencia_meta = {}
                        st.rerun()

    # ================= TAB 8: SALVOS =================
    with tabs[7]:
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
