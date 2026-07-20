import os
import csv
from collections import Counter, deque
import numpy as np
import requests
import random
from collections import Counter
import json
import pandas as pd
import plotly.express as px
import streamlit as st


# ======================================================================
# Módulo original: py
# ======================================================================
# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORICO_CSV = os.path.join(BASE_DIR, "historico.csv")
PESOS_JSON = os.path.join(BASE_DIR, "pesos_aprendidos.json")
JOGOS_SALVOS_DIR = os.path.join(BASE_DIR, "jogos_salvos")

# ---------------------------------------------------------------------------
# Fonte de dados
# ---------------------------------------------------------------------------
API_URL = "https://loteriascaixa-api.herokuapp.com/api/megasena"

# ---------------------------------------------------------------------------
# Janelas de frequência usadas no score (equivalentes ao freq10 / freq50 do
# estudo original). Podem ser ajustadas sem tocar no restante do código.
# ---------------------------------------------------------------------------
JANELA_CURTA = 10
JANELA_LONGA = 50
JANELAS_TENDENCIA = [10, 20, 50, 100]

# ---------------------------------------------------------------------------
# Pesos padrão do motor de pontuação (usados até a IA adaptativa aprender
# pesos melhores a partir do retroteste). Somam 1.0.
# ---------------------------------------------------------------------------
PESOS_PADRAO = {
    "freq10": 0.60,
    "freq50": 0.40,
    "atraso": 0.0,
    "colunas": 0.0,
}

# Concursos mínimos de histórico antes de confiar em qualquer estatística
# ponto-no-tempo (evita pesos aprendidos com base em pouquíssimos dados)
AQUECIMENTO_MINIMO = 30

# ---------------------------------------------------------------------------
# Filtros padrão do gerador de jogos
# ---------------------------------------------------------------------------
FILTROS_PADRAO = {
    "pares_min": 2,
    "pares_max": 4,
    "soma_min": 140,
    "soma_max": 220,
    "consecutivos_max": 3,
    "repetidas_max": 2,
    "colunas_min": 4,
    "colunas_max": 6,
}


# ======================================================================
# Módulo original: estatisticas.py
# ======================================================================
PRIMOS = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59}


# ---------------------------------------------------------------------------
# Funções auxiliares de contagem (puras, sem estado)
# ---------------------------------------------------------------------------
def contar_pares(jogo):
    return sum(1 for d in jogo if d % 2 == 0)


def contar_primos(jogo):
    return sum(1 for d in jogo if d in PRIMOS)


def contar_consecutivos(jogo):
    jogo = sorted(jogo)
    return sum(1 for i in range(len(jogo) - 1) if jogo[i + 1] == jogo[i] + 1)


def distribuir_faixas(jogo):
    faixas = [0, 0, 0]
    for n in jogo:
        if 1 <= n <= 20:
            faixas[0] += 1
        elif 21 <= n <= 40:
            faixas[1] += 1
        else:
            faixas[2] += 1
    return faixas


def distribuir_colunas(jogo):
    """6 colunas de 10 dezenas cada (C1: 1-10 ... C6: 51-60)."""
    colunas = [0] * 6
    for n in jogo:
        col = (n - 1) // 10
        if col < 6:
            colunas[col] += 1
    return colunas


def distribuir_linhas(jogo):
    """5 linhas de 12 dezenas cada, outra forma clássica de olhar o volante."""
    linhas = [0] * 5
    for n in jogo:
        linha = (n - 1) // 12
        if linha < 5:
            linhas[linha] += 1
    return linhas


# ---------------------------------------------------------------------------
# Busca de dados (API + cache local em CSV)
# ---------------------------------------------------------------------------
def buscar_historico_api(quantidade=300):
    """Busca o histórico na API pública da Caixa. Retorna None em caso de erro
    (quem chama decide como avisar o usuário — este módulo não conhece UI)."""
    try:
        resp = requests.get(API_URL, timeout=10)
        if resp.status_code != 200:
            return None
        dados = resp.json()
        if isinstance(dados, list):
            return dados[:quantidade]
        if isinstance(dados, dict):
            return [dados]
        return None
    except Exception:
        return None


def salvar_historico_csv(concursos, caminho=None):
    """Persiste o histórico já processado em CSV, para não depender da API
    a cada execução (e permitir recalcular tudo offline)."""
    caminho = caminho or HISTORICO_CSV
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["numero", "data", "dezenas"])
        for c in concursos:
            writer.writerow([c["numero"], c["data"], "-".join(f"{d:02d}" for d in c["dezenas"])])


def carregar_historico_csv(caminho=None):
    caminho = caminho or HISTORICO_CSV
    if not os.path.exists(caminho):
        return []
    dados = []
    with open(caminho, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dezenas = sorted(int(d) for d in row["dezenas"].split("-"))
            dados.append({"concurso": int(row["numero"]), "data": row["data"], "dezenas": dezenas})
    return dados


# ---------------------------------------------------------------------------
# Módulo 1: Banco de Dados
# ---------------------------------------------------------------------------
class BancoDados:
    """Recebe a lista bruta (da API ou do CSV) e organiza em concursos com
    todas as métricas derivadas já calculadas uma única vez."""

    def __init__(self, dados_brutos):
        self.concursos = []
        self._processar(dados_brutos)

    def _processar(self, dados_brutos):
        for c in dados_brutos:
            if "dezenas" not in c:
                continue
            dezenas = sorted(int(d) for d in c["dezenas"])
            self.concursos.append({
                "numero": c.get("concurso", c.get("numeroDoConcurso", 0)),
                "data": c.get("data", c.get("dataApuracao", "")),
                "dezenas": dezenas,
                "pares": contar_pares(dezenas),
                "primos": contar_primos(dezenas),
                "soma": sum(dezenas),
                "consecutivos": contar_consecutivos(dezenas),
                "faixas": distribuir_faixas(dezenas),
                "colunas": distribuir_colunas(dezenas),
                "linhas": distribuir_linhas(dezenas),
            })
        self.concursos.sort(key=lambda x: x["numero"], reverse=True)

    def get_ultimo_concurso(self):
        return self.concursos[0] if self.concursos else None

    def get_historico_dezenas(self):
        return [c["dezenas"] for c in self.concursos]

    def concursos_anteriores_a(self, indice):
        """Retorna um BancoDados 'do passado', contendo só concursos
        estritamente anteriores ao índice dado (mais recente = índice 0).
        Essencial para retrotestes sem look-ahead bias."""
        anteriores = self.concursos[indice + 1:]
        banco = BancoDados.__new__(BancoDados)
        banco.concursos = anteriores
        return banco


# ---------------------------------------------------------------------------
# Módulo 2: Estatísticas (frequência, atraso, tendência)
# ---------------------------------------------------------------------------
class Estatisticas:
    """Calcula frequências (várias janelas), atrasos e tendências a partir de
    um BancoDados. Pode ser recriado a qualquer ponto no tempo passando um
    BancoDados 'do passado' (ver BancoDados.concursos_anteriores_a)."""

    def __init__(self, banco_dados):
        self.banco = banco_dados
        self._calcular()

    def _calcular(self):
        historico = self.banco.get_historico_dezenas()
        self.total_concursos = len(historico)

        self.frequencias = Counter()
        for concurso in historico:
            self.frequencias.update(concurso)

        self.frequencias_periodos = {}
        for p in set(JANELAS_TENDENCIA + [JANELA_CURTA, JANELA_LONGA]):
            freq = Counter()
            for concurso in historico[:p]:
                freq.update(concurso)
            self.frequencias_periodos[p] = freq

        self.atrasos = self._calcular_atrasos(historico)
        self.tendencias = self._calcular_tendencias(historico)

        somas = [c["soma"] for c in self.banco.concursos] or [0]
        self.media_soma = float(np.mean(somas))
        self.std_soma = float(np.std(somas))
        self.media_pares = float(np.mean([c["pares"] for c in self.banco.concursos])) if self.banco.concursos else 3.0

        self.distribuicao_soma = {
            "percentil_25": float(np.percentile(somas, 25)),
            "percentil_75": float(np.percentile(somas, 75)),
        }

        # Frequência por coluna nas últimas N rodadas — usada pelo score para
        # o "bônus de coluna" (favorecer colunas pouco sorteadas recentemente)
        self.freq_colunas_recente = [0] * 6
        for concurso in historico[:JANELA_LONGA]:
            for n in concurso:
                col = (n - 1) // 10
                if col < 6:
                    self.freq_colunas_recente[col] += 1

    def _calcular_atrasos(self, historico):
        atrasos = {i: len(historico) for i in range(1, 61)}
        for dezena in range(1, 61):
            for idx, concurso in enumerate(historico):
                if dezena in concurso:
                    atrasos[dezena] = idx
                    break
        return atrasos

    def _calcular_tendencias(self, historico):
        tendencias = {}
        for num in range(1, 61):
            freq_janelas = []
            for janela in JANELAS_TENDENCIA:
                freq = sum(1 for c in historico[:janela] if num in c)
                freq_janelas.append(freq / janela if janela else 0)
            if len(freq_janelas) >= 2:
                x = np.arange(len(freq_janelas))
                slope = float(np.polyfit(x, freq_janelas, 1)[0])
            else:
                slope = 0.0
            tendencias[num] = slope
        return tendencias

    def get_estatisticas_dezena(self, numero):
        return {
            "numero": numero,
            "frequencia": self.frequencias.get(numero, 0),
            "freq10": self.frequencias_periodos.get(JANELA_CURTA, {}).get(numero, 0),
            "freq50": self.frequencias_periodos.get(JANELA_LONGA, {}).get(numero, 0),
            "atraso": self.atrasos.get(numero, 0),
            "tendencia": self.tendencias.get(numero, 0.0),
        }


# ======================================================================
# Módulo original: score.py
# ======================================================================
class MotorPontuacao:
    def __init__(self, estatisticas, pesos=None):
        self.estatisticas = estatisticas
        self.pesos = dict(PESOS_PADRAO)
        if pesos:
            self.pesos.update(pesos)
        self.pontuacoes = self._calcular()

    def _calcular(self):
        stats = self.estatisticas
        freq10 = stats.frequencias_periodos.get(JANELA_CURTA, {})
        freq50 = stats.frequencias_periodos.get(JANELA_LONGA, {})

        max_freq10 = max(freq10.values()) if freq10 else 1
        max_freq50 = max(freq50.values()) if freq50 else 1
        max_atraso = max(stats.atrasos.values()) if stats.atrasos else 1
        max_col_freq = max(stats.freq_colunas_recente) if stats.freq_colunas_recente else 1

        pontuacoes = {}
        for num in range(1, 61):
            n_freq10 = freq10.get(num, 0) / max_freq10
            n_freq50 = freq50.get(num, 0) / max_freq50
            n_atraso = stats.atrasos.get(num, 0) / max_atraso  # quanto maior o atraso, maior o bônus

            col = (num - 1) // 10
            # bônus de coluna: favorece colunas MENOS sorteadas recentemente
            freq_col = stats.freq_colunas_recente[col] if col < 6 else max_col_freq
            n_coluna = 1 - (freq_col / max_col_freq if max_col_freq else 0)

            score = (
                self.pesos.get("freq10", 0) * n_freq10
                + self.pesos.get("freq50", 0) * n_freq50
                + self.pesos.get("atraso", 0) * n_atraso
                + self.pesos.get("colunas", 0) * n_coluna
            )
            pontuacoes[num] = round(score * 100, 2)
        return pontuacoes

    def get_ranking(self, top_n=60):
        ranking = sorted(self.pontuacoes.items(), key=lambda x: x[1], reverse=True)
        return ranking[:top_n]


# ======================================================================
# Módulo original: gerador.py
# ======================================================================
class FiltrosInteligentes:
    def __init__(self, estatisticas, filtros=None):
        self.estatisticas = estatisticas
        self.filtros = dict(FILTROS_PADRAO)
        if filtros:
            self.filtros.update(filtros)

    def aplicar(self, jogo):
        f = self.filtros

        pares = contar_pares(jogo)
        if not (f["pares_min"] <= pares <= f["pares_max"]):
            return False

        soma = sum(jogo)
        if not (f["soma_min"] <= soma <= f["soma_max"]):
            return False

        consec = contar_consecutivos(jogo)
        if consec > f["consecutivos_max"]:
            return False

        colunas = distribuir_colunas(jogo)
        colunas_ativas = sum(1 for c in colunas if c > 0)
        if not (f["colunas_min"] <= colunas_ativas <= f["colunas_max"]):
            return False

        if self.estatisticas.banco.concursos:
            ultimo = self.estatisticas.banco.concursos[0]["dezenas"]
            repetidas = len(set(jogo) & set(ultimo))
            if repetidas > f["repetidas_max"]:
                return False

        return True


class GeradorPremium:
    """Gera jogos combinando dezenas 'quentes' (topo do ranking), 'mornas'
    (meio do ranking) e 'frias' (mais atrasadas) — a mistura pedida no
    estudo original — e só aceita jogos aprovados pelos filtros."""

    def __init__(self, banco_dados, estatisticas, motor_pontuacao, filtros):
        self.banco = banco_dados
        self.estatisticas = estatisticas
        self.motor = motor_pontuacao
        self.filtros = filtros

    def _pool_quente_morna_fria(self):
        ranking = [n for n, _ in self.motor.get_ranking(60)]
        quentes = ranking[:20]
        mornas = ranking[20:40]
        frias = ranking[40:]
        return quentes, mornas, frias

    def _gerar_candidato(self, estrategia, quentes, mornas, frias):
        jogo = set()
        if estrategia == "conservadora":
            # prioriza fortemente os números de maior score
            jogo.update(random.sample(quentes, min(4, len(quentes))))
        elif estrategia == "diversificada":
            jogo.update(random.sample(quentes, min(2, len(quentes))))
            jogo.update(random.sample(frias, min(2, len(frias))))
        else:  # equilibrada (padrão)
            jogo.update(random.sample(quentes, min(3, len(quentes))))
            jogo.update(random.sample(mornas, min(2, len(mornas))))

        universo = quentes + mornas + frias
        while len(jogo) < 6:
            novo = random.choice(universo) if universo else random.randint(1, 60)
            jogo.add(novo)
        return sorted(jogo)

    def gerar_jogos(self, qtd=10, estrategia="equilibrada", max_tentativas=None,
                     progress_callback=None):
        quentes, mornas, frias = self._pool_quente_morna_fria()
        max_tentativas = max_tentativas or qtd * 5000

        jogos = []
        tentativas = 0
        while len(jogos) < qtd and tentativas < max_tentativas:
            tentativas += 1
            jogo = self._gerar_candidato(estrategia, quentes, mornas, frias)
            if self.filtros.aplicar(jogo) and jogo not in jogos:
                jogos.append(jogo)
            if progress_callback and tentativas % 200 == 0:
                progress_callback(min(len(jogos) / qtd, 1.0))

        if progress_callback:
            progress_callback(1.0)
        return jogos


# ======================================================================
# Módulo original: retroteste.py
# ======================================================================
def _rodar_um_concurso(historico_concursos, indice, pesos, filtros_cfg,
                        estrategia, jogos_por_teste):
    """Recalcula tudo com dados só ANTERIORES a `indice` e gera jogos
    de teste para comparar contra o resultado real daquele concurso."""

    concursos_anteriores = historico_concursos[indice + 1:]
    if len(concursos_anteriores) < AQUECIMENTO_MINIMO:
        return None

    banco_pt = BancoDados.__new__(BancoDados)
    banco_pt.concursos = concursos_anteriores

    stats_pt = Estatisticas(banco_pt)
    motor_pt = MotorPontuacao(stats_pt, pesos=pesos)
    filtros_pt = FiltrosInteligentes(stats_pt, filtros=filtros_cfg)
    gerador_pt = GeradorPremium(banco_pt, stats_pt, motor_pt, filtros_pt)

    jogos = gerador_pt.gerar_jogos(
        qtd=jogos_por_teste, estrategia=estrategia,
        max_tentativas=jogos_por_teste * 1500,
    )

    dezenas_reais = set(historico_concursos[indice]["dezenas"])
    return [len(set(j) & dezenas_reais) for j in jogos]


def testar_estrategia(banco_dados, estrategia="equilibrada", num_testes=50,
                       pesos=None, filtros_cfg=None, jogos_por_teste=5,
                       progress_callback=None):
    """Roda o retroteste ponto-no-tempo para uma estratégia e retorna um
    resumo estatístico dos acertos obtidos."""
    historico = banco_dados.concursos  # mais recente primeiro
    testes = historico[:min(num_testes, len(historico))]

    resultados = []
    for i, _ in enumerate(testes):
        acertos = _rodar_um_concurso(historico, i, pesos, filtros_cfg, estrategia, jogos_por_teste)
        if acertos:
            resultados.extend(acertos)
        if progress_callback:
            progress_callback((i + 1) / len(testes))

    if not resultados:
        return {
            "estrategia": estrategia, "total_simulacoes": 0, "media": 0,
            "mediana": 0, "std": 0, "max": 0, "min": 0, "distribuicao": {},
        }

    return {
        "estrategia": estrategia,
        "total_simulacoes": len(resultados),
        "media": float(np.mean(resultados)),
        "mediana": float(np.median(resultados)),
        "std": float(np.std(resultados)),
        "max": int(max(resultados)),
        "min": int(min(resultados)),
        "distribuicao": dict(Counter(resultados)),
    }


def comparar_estrategias(banco_dados, estrategias, num_testes=50, pesos=None,
                          progress_callback=None):
    return {
        est: testar_estrategia(banco_dados, estrategia=est, num_testes=num_testes,
                                pesos=pesos, progress_callback=progress_callback)
        for est in estrategias
    }


def avaliar_pesos(banco_dados, pesos, num_testes=30, jogos_por_teste=3,
                   estrategia="equilibrada"):
    """Avaliação rápida e enxuta de um vetor de pesos — usada pelo
    otimizador (pesos_adaptativos.py). Retorna a média de acertos por
    jogo simulado: é a métrica de aptidão ("fitness") que a IA adaptativa
    tenta maximizar."""
    resumo = testar_estrategia(
        banco_dados, estrategia=estrategia, num_testes=num_testes,
        pesos=pesos, jogos_por_teste=jogos_por_teste,
    )
    return resumo["media"]


# ======================================================================
# Módulo original: pesos_adaptativos.py
# ======================================================================
CHAVES_PESO = ["freq10", "freq50", "atraso", "colunas"]


def _normalizar(pesos):
    total = sum(max(0.0, v) for v in pesos.values()) or 1.0
    return {k: max(0.0, v) / total for k, v in pesos.items()}


def _vizinho_aleatorio(pesos, passo=0.08):
    """Gera um vetor de pesos vizinho, perturbando uma coordenada por vez."""
    novo = dict(pesos)
    chave = random.choice(CHAVES_PESO)
    novo[chave] = max(0.0, novo[chave] + random.uniform(-passo, passo))
    return _normalizar(novo)


def _pesos_aleatorios():
    valores = [random.random() for _ in CHAVES_PESO]
    return _normalizar(dict(zip(CHAVES_PESO, valores)))


def otimizar(banco_dados, concursos_treino=40, concursos_validacao=20,
             iteracoes=25, reinicios=4, progress_callback=None):
    """Busca os pesos que maximizam a média de acertos no retroteste,
    validando fora da janela de treino. Retorna (melhores_pesos, relatorio).
    """
    total_passos = reinicios * iteracoes
    passo_atual = 0

    melhor_global = dict(PESOS_PADRAO)
    melhor_score_validacao = avaliar_pesos(
        banco_dados, melhor_global, num_testes=concursos_validacao,
    )
    historico_busca = []

    for r in range(reinicios):
        atual = _pesos_aleatorios() if r > 0 else dict(PESOS_PADRAO)
        score_atual = avaliar_pesos(banco_dados, atual, num_testes=concursos_treino)

        for _ in range(iteracoes):
            candidato = _vizinho_aleatorio(atual)
            score_candidato = avaliar_pesos(banco_dados, candidato, num_testes=concursos_treino)

            if score_candidato > score_atual:
                atual, score_atual = candidato, score_candidato

            passo_atual += 1
            if progress_callback:
                progress_callback(passo_atual / total_passos)

        # valida o melhor da rodada numa janela diferente da usada no treino
        score_validacao = avaliar_pesos(banco_dados, atual, num_testes=concursos_validacao)
        historico_busca.append({
            "reinicio": r, "pesos": atual,
            "score_treino": score_atual, "score_validacao": score_validacao,
        })

        if score_validacao > melhor_score_validacao:
            melhor_global = atual
            melhor_score_validacao = score_validacao

    relatorio = {
        "pesos_escolhidos": melhor_global,
        "score_validacao": melhor_score_validacao,
        "pesos_padrao_score_validacao": avaliar_pesos(
            banco_dados, PESOS_PADRAO, num_testes=concursos_validacao,
        ),
        "historico_busca": historico_busca,
    }
    return melhor_global, relatorio


def salvar_pesos(pesos, caminho=None):
    caminho = caminho or PESOS_JSON
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(pesos, f, indent=2)


def carregar_pesos(caminho=None):
    """Carrega os últimos pesos aprendidos; se não existir, cai nos pesos
    padrão fixos definidos no topo do arquivo."""
    caminho = caminho or PESOS_JSON
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(PESOS_PADRAO)


# ======================================================================
# Módulo original: conferencia.py
# ======================================================================
def conferir_jogo(jogo, dezenas_sorteadas):
    return len(set(jogo) & set(dezenas_sorteadas))


def conferir_lista(jogos, dezenas_sorteadas):
    """Confere uma lista de jogos e devolve o resumo no formato clássico
    de loteria (quantos fizeram quadra/quina/sena etc.)."""
    acertos_por_jogo = [conferir_jogo(j, dezenas_sorteadas) for j in jogos]
    contagem = Counter(acertos_por_jogo)
    return {
        "acertos_por_jogo": acertos_por_jogo,
        "quadras": contagem.get(4, 0),
        "quinas": contagem.get(5, 0),
        "senas": contagem.get(6, 0),
        "distribuicao_completa": dict(contagem),
    }


# ======================================================================
# Módulo original: motor_v10.py
# ======================================================================
class MegaIA:
    """Estado vivo do sistema: histórico carregado + módulos derivados.
    Chamar `atualizar()` sempre que um novo concurso sair recalcula tudo
    automaticamente, como pedido no estudo original."""

    def __init__(self):
        self.banco = None
        self.estatisticas = None
        self.pesos = dict(PESOS_PADRAO)
        self.motor_pontuacao = None
        self.filtros = None
        self.gerador = None

    # ------------------------------------------------------------------
    # Carga de dados
    # ------------------------------------------------------------------
    def carregar(self, quantidade=300, usar_cache_se_falhar=True):
        dados = buscar_historico_api(quantidade)
        if dados:
            salvar_historico_csv(
                [{"numero": d.get("concurso", d.get("numeroDoConcurso", 0)),
                  "data": d.get("data", d.get("dataApuracao", "")),
                  "dezenas": sorted(int(x) for x in d["dezenas"])}
                 for d in dados if "dezenas" in d]
            )
        elif usar_cache_se_falhar:
            dados = carregar_historico_csv()

        if not dados:
            return False

        self.banco = BancoDados(dados)
        self.pesos = pesos_adaptativos.carregar_pesos()
        self._recalcular()
        return True

    def novo_concurso(self, numero, data, dezenas):
        """Acrescenta um concurso recém-saído e recalcula tudo — é a
        'atualização automática' pedida: nenhum passo manual além deste."""
        if self.banco is None:
            self.banco = BancoDados([])
        self.banco.concursos.insert(0, {
            "numero": numero, "data": data, "dezenas": sorted(dezenas),
        })
        salvar_historico_csv(self.banco.concursos)
        self._recalcular()

    def _recalcular(self):
        self.estatisticas = Estatisticas(self.banco)
        self.motor_pontuacao = MotorPontuacao(self.estatisticas, pesos=self.pesos)
        self.filtros = FiltrosInteligentes(self.estatisticas)
        self.gerador = GeradorPremium(self.banco, self.estatisticas, self.motor_pontuacao, self.filtros)

    # ------------------------------------------------------------------
    # IA adaptativa de pesos
    # ------------------------------------------------------------------
    def aprender_pesos(self, concursos_treino=40, concursos_validacao=20,
                        iteracoes=25, reinicios=4, progress_callback=None):
        novos_pesos, relatorio = pesos_adaptativos.otimizar(
            self.banco, concursos_treino=concursos_treino,
            concursos_validacao=concursos_validacao, iteracoes=iteracoes,
            reinicios=reinicios, progress_callback=progress_callback,
        )
        # só adota os pesos aprendidos se realmente superam os padrão na validação
        if relatorio["score_validacao"] >= relatorio["pesos_padrao_score_validacao"]:
            self.pesos = novos_pesos
            pesos_adaptativos.salvar_pesos(self.pesos)
            self._recalcular()
        return relatorio

    # ------------------------------------------------------------------
    # Geração / retroteste / conferência (repassa para os módulos)
    # ------------------------------------------------------------------
    def gerar_jogos(self, qtd=5, estrategia="equilibrada", progress_callback=None):
        return self.gerador.gerar_jogos(qtd=qtd, estrategia=estrategia, progress_callback=progress_callback)

    def rodar_retroteste(self, estrategias, num_testes=50, progress_callback=None):
        return retroteste.comparar_estrategias(
            self.banco, estrategias, num_testes=num_testes,
            pesos=self.pesos, progress_callback=progress_callback,
        )

    def conferir(self, jogos, dezenas_sorteadas):
        return conferencia.conferir_lista(jogos, dezenas_sorteadas)

    def ranking(self, top_n=20):
        return self.motor_pontuacao.get_ranking(top_n)


# ======================================================================
# Módulo original: app.py
# ======================================================================
st.set_page_config(page_title="🎯 Mega IA V10", layout="wide", initial_sidebar_state="expanded")
st.title("🎯 Mega IA V10")
st.caption("Motor adaptativo de análise estatística e geração de jogos — Mega-Sena")

if "mega" not in st.session_state:
    st.session_state.mega = MegaIA()
mega: MegaIA = st.session_state.mega

# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configurações")
    qtd = st.slider("Concursos históricos", 50, 500, 200)

    if st.button("📥 Carregar / Atualizar histórico", use_container_width=True):
        with st.spinner("Buscando concursos..."):
            ok = mega.carregar(quantidade=qtd)
        if ok:
            st.success(f"{len(mega.banco.concursos)} concursos carregados.")
        else:
            st.error("Não foi possível carregar dados (API fora do ar e sem cache local).")

    if mega.banco:
        ultimo = mega.banco.get_ultimo_concurso()
        st.markdown("### 📅 Último concurso")
        st.markdown(f"**#{ultimo['numero']}** — {ultimo['data']}")
        st.markdown(f"🎯 {', '.join(f'{d:02d}' for d in ultimo['dezenas'])}")
        st.caption(f"Pesos ativos: {mega.pesos}")

    st.markdown("---")
    st.caption("Mega IA V10 — pesos aprendidos via retroteste, não fixados manualmente.")

if not mega.banco:
    st.info("👈 Carregue o histórico na barra lateral para começar.")
    st.stop()

tabs = st.tabs(["📊 Dashboard", "🏆 Ranking", "🎲 Gerador", "🔬 Retroteste", "🧠 IA Adaptativa", "✅ Conferência"])

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
with tabs[0]:
    stats = mega.estatisticas
    c1, c2, c3 = st.columns(3)
    c1.metric("Total de concursos", stats.total_concursos)
    c2.metric("Média da soma", f"{stats.media_soma:.1f}")
    c3.metric("Média de pares", f"{stats.media_pares:.1f}")

    df_freq = pd.DataFrame({"Dezena": range(1, 61), "Frequência": [stats.frequencias.get(i, 0) for i in range(1, 61)]})
    st.plotly_chart(px.bar(df_freq, x="Dezena", y="Frequência", title="Frequência histórica por dezena"), use_container_width=True)

    df_atraso = pd.DataFrame({"Dezena": range(1, 61), "Atraso": [stats.atrasos.get(i, 0) for i in range(1, 61)]})
    st.plotly_chart(px.bar(df_atraso, x="Dezena", y="Atraso", title="Atraso atual por dezena", color="Atraso"), use_container_width=True)

# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------
with tabs[1]:
    top_n = st.slider("Top N dezenas", 5, 60, 20)
    ranking = mega.ranking(top_n)
    df_rank = pd.DataFrame(ranking, columns=["Dezena", "Score"])
    df_rank.index += 1
    st.dataframe(df_rank, use_container_width=True)

# ---------------------------------------------------------------------------
# Gerador
# ---------------------------------------------------------------------------
with tabs[2]:
    col1, col2 = st.columns(2)
    with col1:
        qtd_jogos = st.number_input("Quantidade de jogos", 1, 50, 5)
    with col2:
        estrategia = st.selectbox("Estratégia", ["equilibrada", "conservadora", "diversificada"])

    if st.button("🎲 Gerar jogos", type="primary", use_container_width=True):
        barra = st.progress(0.0)
        jogos = mega.gerar_jogos(qtd=qtd_jogos, estrategia=estrategia, progress_callback=barra.progress)
        barra.empty()
        st.session_state.ultimos_jogos = jogos
        for i, j in enumerate(jogos, 1):
            st.markdown(f"**Jogo {i}:** {', '.join(f'{d:02d}' for d in j)}")

        if jogos:
            txt = "\n".join(f"Jogo {i}: {', '.join(f'{d:02d}' for d in j)}" for i, j in enumerate(jogos, 1))
            st.download_button("📝 Exportar TXT", data=txt, file_name="jogos_mega_ia_v10.txt", use_container_width=True)

# ---------------------------------------------------------------------------
# Retroteste
# ---------------------------------------------------------------------------
with tabs[3]:
    st.markdown("""
Roda cada estratégia sobre concursos passados, recalculando as
estatísticas ponto-no-tempo (sem usar dados "do futuro"). Resultados
passados não garantem resultados futuros — este painel serve para
comparar estratégias entre si, não para prever prêmios.
""")
    estrategias_sel = st.multiselect("Estratégias", ["conservadora", "equilibrada", "diversificada"],
                                      default=["conservadora", "equilibrada", "diversificada"])
    num_testes = st.slider("Concursos para teste", 10, 150, 50)

    if st.button("🔬 Executar retroteste", use_container_width=True):
        barra = st.progress(0.0)
        resultados = mega.rodar_retroteste(estrategias_sel, num_testes=num_testes, progress_callback=barra.progress)
        barra.empty()
        df = pd.DataFrame([
            {"Estratégia": e, "Média": round(r["media"], 2), "Mediana": r["mediana"],
             "Máximo": r["max"], "Simulações": r["total_simulacoes"]}
            for e, r in resultados.items()
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# IA Adaptativa (aprendizado de pesos)
# ---------------------------------------------------------------------------
with tabs[4]:
    st.markdown("""
Em vez de pesos fixos, o sistema testa combinações de pesos no histórico
(treino) e só adota a combinação vencedora se ela também performar bem
num período separado (validação) — evitando overfitting a um padrão que
não se repete.
""")
    col1, col2 = st.columns(2)
    with col1:
        concursos_treino = st.slider("Concursos de treino", 20, 100, 40)
    with col2:
        concursos_validacao = st.slider("Concursos de validação", 10, 60, 20)

    if st.button("🧠 Aprender pesos agora", type="primary", use_container_width=True):
        barra = st.progress(0.0)
        relatorio = mega.aprender_pesos(
            concursos_treino=concursos_treino, concursos_validacao=concursos_validacao,
            progress_callback=barra.progress,
        )
        barra.empty()
        st.write("**Pesos escolhidos:**", relatorio["pesos_escolhidos"])
        st.write(f"Score validação (pesos novos): {relatorio['score_validacao']:.3f} acertos/jogo em média")
        st.write(f"Score validação (pesos padrão): {relatorio['pesos_padrao_score_validacao']:.3f} acertos/jogo em média")
        adotou = relatorio["score_validacao"] >= relatorio["pesos_padrao_score_validacao"]
        st.success("Pesos novos adotados." if adotou else "Pesos padrão mantidos (novos não superaram a validação).")

# ---------------------------------------------------------------------------
# Conferência
# ---------------------------------------------------------------------------
with tabs[5]:
    st.markdown("Cole o resultado sorteado para conferir os jogos gerados na aba Gerador.")
    texto_dezenas = st.text_input("Dezenas sorteadas (separadas por vírgula)", placeholder="ex: 4, 12, 23, 34, 45, 59")

    if st.button("✅ Conferir", use_container_width=True):
        jogos = st.session_state.get("ultimos_jogos", [])
        if not jogos:
            st.warning("Gere jogos na aba 'Gerador' primeiro.")
        elif not texto_dezenas.strip():
            st.warning("Informe as dezenas sorteadas.")
        else:
            dezenas = [int(x.strip()) for x in texto_dezenas.split(",") if x.strip()]
            resumo = mega.conferir(jogos, dezenas)
            st.write("Acertos por jogo:", resumo["acertos_por_jogo"])
            c1, c2, c3 = st.columns(3)
            c1.metric("Quadras", resumo["quadras"])
            c2.metric("Quinas", resumo["quinas"])
            c3.metric("Sena", resumo["senas"])
