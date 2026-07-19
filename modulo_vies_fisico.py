"""
modulo_vies_fisico.py
======================
Rastreador de VIÉS FÍSICO DE RODA (wheel bias) — a única hipótese
estatisticamente legítima de sinal numa roleta com roda física.

Diferença fundamental em relação ao módulo de ML por dúzia:
- ML por dúzia parte da premissa (falsa) de que rodadas passadas informam
  a próxima rodada. Rodadas são i.i.d. — isso não existe.
- Viés físico parte da premissa (real, documentada) de que uma roda física
  específica pode ter desgaste mecânico que favorece levemente alguns
  NÚMEROS específicos (não dúzias) de forma PERSISTENTE ao longo de
  milhares de rodadas na MESMA mesa (table_id).

Por isso este módulo:
  1. Acumula contagens por table_id, SEM reset por sessão (o desgaste da
     roda não sabe que você abriu uma sessão nova no app).
  2. Exige um N mínimo grande antes de calcular qualquer coisa.
  3. Faz um teste global primeiro (qui-quadrado, 36 graus de liberdade) e
     só investiga número a número se o teste global já rejeitou a
     hipótese de uniformidade — evita "fishing" (testar 37 números soltos
     até achar um "significativo" por acaso).
  4. Usa correção de Bonferroni nos testes por número.

LIMITAÇÃO HONESTA (leia antes de usar):
  Como esse painel fica visível e é consultado a cada rodada (peeking
  contínuo), a taxa de falso-positivo real ao longo do tempo é MAIOR que o
  alfa nominal usado aqui (isso é o "optional stopping problem" /
  problema de comparações múltiplas ao longo do tempo). Não há correção
  sequencial (alpha-spending) implementada. Trate qualquer número marcado
  como "suspeito" como HIPÓTESE A CONFIRMAR com mais dados, nunca como
  confirmação definitiva. Mesas online de cassinos regulados também
  costumam monitorar e rotacionar rodas justamente para evitar viés
  detectável — não espere encontrar nada na maioria das mesas, na maioria
  do tempo. Se isso nunca disparar, esse é o comportamento ESPERADO e
  correto, não um bug.
"""

import os
import json
import math
import logging
from collections import defaultdict

try:
    from scipy.stats import chi2 as _chi2_dist, norm as _norm_dist
    _SCIPY_DISPONIVEL = True
except ImportError:
    _SCIPY_DISPONIVEL = False


# Ordem física REAL dos números na roda europeia (zero único), no sentido
# em que aparecem fisicamente — NÃO é a ordem numérica da mesa. Setores de
# desgaste mecânico (frete deformado, roda desalinhada) afetam um arco
# CONTÍGUO nesta ordem, não números vizinhos por valor.
ORDEM_FISICA_RODA_EUROPEIA = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
    5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26,
]


def montar_setores(n_setores=6, ordem_roda=None):
    """
    Divide a roda (na ordem física real) em n_setores arcos contíguos.
    Retorna lista de listas de números — setores[i] = números daquele arco.
    """
    ordem = ordem_roda or ORDEM_FISICA_RODA_EUROPEIA
    total = len(ordem)
    tamanho_base = total // n_setores
    resto = total % n_setores
    setores = []
    idx = 0
    for i in range(n_setores):
        tamanho = tamanho_base + (1 if i < resto else 0)
        setores.append(ordem[idx: idx + tamanho])
        idx += tamanho
    return setores


def _mapa_numero_para_setor(setores):
    mapa = {}
    for i, setor in enumerate(setores):
        for num in setor:
            mapa[num] = i
    return mapa


class RastreadorViesFisico:
    # N mínimo de rodadas NA MESMA MESA antes de calcular qualquer coisa.
    # Abaixo disso, o teste qui-quadrado não tem poder estatístico nenhum
    # (regra prática: contagem esperada por célula >= 5 já é o mínimo só
    # para a aproximação qui-quadrado valer; para ter chance real de
    # detectar um viés modesto, o número precisa ser bem maior).
    N_MINIMO_TESTE = 1500

    # Significância do teste GLOBAL (omnibus, 36 graus de liberdade).
    ALPHA_GLOBAL = 0.01

    def __init__(self, caminho="vies_fisico_rodas.json"):
        self.caminho = caminho
        self.contagens_por_mesa = defaultdict(lambda: [0] * 37)
        self.nomes_mesa = {}
        self._carregar()

    def _carregar(self):
        try:
            if os.path.exists(self.caminho):
                with open(self.caminho, "r") as f:
                    dados = json.load(f)
                for tid, info in dados.items():
                    self.contagens_por_mesa[tid] = info.get("contagens", [0] * 37)
                    self.nomes_mesa[tid] = info.get("nome", tid)
        except Exception as e:
            logging.error(f"❌ Erro ao carregar rastreador de viés físico: {e}")

    def _salvar(self):
        try:
            dados = {
                tid: {"contagens": cont, "nome": self.nomes_mesa.get(tid, tid)}
                for tid, cont in self.contagens_por_mesa.items()
            }
            caminho_tmp = self.caminho + ".tmp"
            with open(caminho_tmp, "w") as f:
                json.dump(dados, f)
            os.replace(caminho_tmp, self.caminho)
        except Exception as e:
            logging.error(f"❌ Erro ao salvar rastreador de viés físico: {e}")

    def adicionar(self, table_id, table_name, numero):
        """Alimenta o rastreador com um número real sorteado numa mesa."""
        if not table_id or table_id == "unknown":
            return
        if numero is None or not (0 <= numero <= 36):
            return
        self.contagens_por_mesa[table_id][numero] += 1
        self.nomes_mesa[table_id] = table_name or table_id
        self._salvar()

    def analisar_mesa(self, table_id):
        """
        Retorna um relatório estatístico honesto para a mesa. Nunca inventa
        significância: se N < mínimo, retorna status 'insuficiente' e nada
        mais — sem sugestão de números, sem "quase lá".
        """
        contagens = self.contagens_por_mesa.get(table_id)
        if not contagens or sum(contagens) == 0:
            return {"status": "sem_dados", "n_total": 0, "n_minimo": self.N_MINIMO_TESTE}

        n_total = sum(contagens)
        if n_total < self.N_MINIMO_TESTE:
            return {
                "status": "insuficiente",
                "n_total": n_total,
                "n_minimo": self.N_MINIMO_TESTE,
                "faltam": self.N_MINIMO_TESTE - n_total,
            }

        esperado = n_total / 37.0
        chi2_stat = sum((o - esperado) ** 2 / esperado for o in contagens)

        p_global = None
        if _SCIPY_DISPONIVEL:
            p_global = float(1 - _chi2_dist.cdf(chi2_stat, df=36))

        resultado = {
            "status": "ok",
            "n_total": n_total,
            "chi2": round(chi2_stat, 2),
            "p_global": round(p_global, 5) if p_global is not None else None,
            "significativo_global": bool(p_global is not None and p_global < self.ALPHA_GLOBAL),
            "numeros_suspeitos": [],
            "scipy_disponivel": _SCIPY_DISPONIVEL,
        }

        # Só olha número a número SE o teste global já rejeitou a
        # uniformidade. Sem isso, seria testar 37 hipóteses soltas até achar
        # uma "significativa" por puro acaso (fishing).
        if resultado["significativo_global"] and _SCIPY_DISPONIVEL:
            alpha_corrigido = self.ALPHA_GLOBAL / 37.0  # Bonferroni
            desvio_padrao = math.sqrt(esperado * (1 - 1.0 / 37.0))
            for num, obs in enumerate(contagens):
                z = (obs - esperado) / desvio_padrao
                p_num = 2 * (1 - _norm_dist.cdf(abs(z)))
                if p_num < alpha_corrigido:
                    resultado["numeros_suspeitos"].append({
                        "numero": num,
                        "observado": obs,
                        "esperado": round(esperado, 1),
                        "z": round(z, 2),
                        "p": round(p_num, 6),
                    })
            resultado["numeros_suspeitos"].sort(key=lambda x: x["z"], reverse=True)

        return resultado

    def analisar_mesa_setor(self, table_id, n_setores=6):
        """
        Mesma ideia do analisar_mesa, mas agrupando os números em setores
        físicos contíguos da roda antes do teste. Usa a MESMA contagem por
        número já acumulada — não precisa coletar dados de novo.

        N mínimo escala com o número de setores: exige esperado >= 25 por
        setor (mais conservador que a regra mínima de validade, que seria
        >=5, porque validade != poder de detecção).
        """
        contagens = self.contagens_por_mesa.get(table_id)
        if not contagens or sum(contagens) == 0:
            return {"status": "sem_dados", "n_total": 0}

        n_total = sum(contagens)
        n_minimo_setor = 25 * n_setores
        setores = montar_setores(n_setores)

        if n_total < n_minimo_setor:
            return {
                "status": "insuficiente",
                "n_total": n_total,
                "n_minimo": n_minimo_setor,
                "faltam": n_minimo_setor - n_total,
                "n_setores": n_setores,
                "setores": setores,
            }

        contagens_setor = [sum(contagens[num] for num in setor) for setor in setores]
        esperado = n_total / n_setores
        chi2_stat = sum((o - esperado) ** 2 / esperado for o in contagens_setor)

        p_global = None
        if _SCIPY_DISPONIVEL:
            p_global = float(1 - _chi2_dist.cdf(chi2_stat, df=n_setores - 1))

        resultado = {
            "status": "ok",
            "n_total": n_total,
            "n_setores": n_setores,
            "setores": setores,
            "contagens_setor": contagens_setor,
            "esperado_por_setor": round(esperado, 1),
            "chi2": round(chi2_stat, 2),
            "p_global": round(p_global, 5) if p_global is not None else None,
            "significativo_global": bool(p_global is not None and p_global < self.ALPHA_GLOBAL),
            "setores_suspeitos": [],
            "scipy_disponivel": _SCIPY_DISPONIVEL,
        }

        if resultado["significativo_global"] and _SCIPY_DISPONIVEL:
            alpha_corrigido = self.ALPHA_GLOBAL / n_setores  # Bonferroni entre setores
            desvio_padrao = math.sqrt(esperado * (1 - 1.0 / n_setores))
            for i, obs in enumerate(contagens_setor):
                z = (obs - esperado) / desvio_padrao
                p_setor = 2 * (1 - _norm_dist.cdf(abs(z)))
                if p_setor < alpha_corrigido:
                    resultado["setores_suspeitos"].append({
                        "indice": i,
                        "numeros": setores[i],
                        "observado": obs,
                        "esperado": round(esperado, 1),
                        "z": round(z, 2),
                        "p": round(p_setor, 6),
                    })
            resultado["setores_suspeitos"].sort(key=lambda x: x["z"], reverse=True)

        return resultado


def obter_rastreador_vies_fisico(st_session_state):
    """Singleton em session_state — evita recarregar o JSON a cada autorefresh."""
    if "rastreador_vies_fisico" not in st_session_state:
        st_session_state["rastreador_vies_fisico"] = RastreadorViesFisico()
    return st_session_state["rastreador_vies_fisico"]


def prever_vies_fisico(rastreador, table_id, n_setores=6):
    """
    Gera uma 'previsão' no formato do módulo de ML por dúzia, agora usando
    SETOR FÍSICO da roda (arco contíguo de números) em vez de número
    isolado. Aposta em todos os números do setor sinalizado.

    Se não houver setor confirmado, NÃO entra — mesmo que isso signifique
    nunca entrar por um bom tempo. É o comportamento correto.
    """
    relatorio = rastreador.analisar_mesa_setor(table_id, n_setores=n_setores)

    if relatorio["status"] in ("sem_dados", "insuficiente"):
        faltam = relatorio.get("faltam", relatorio.get("n_minimo", 0))
        return {
            "entrar": False,
            "motivo": f"📊 Coletando dados da mesa ({relatorio['n_total']}/{relatorio.get('n_minimo', 25 * n_setores)}, faltam {faltam})",
            "relatorio_vies_fisico": relatorio,
        }

    if not relatorio["significativo_global"]:
        return {
            "entrar": False,
            "motivo": f"📊 Mesa uniforme por setor até agora (N={relatorio['n_total']}, χ²={relatorio['chi2']}, p={relatorio['p_global']}) — sem entrada",
            "relatorio_vies_fisico": relatorio,
        }

    suspeitos = relatorio["setores_suspeitos"]
    if not suspeitos:
        return {
            "entrar": False,
            "motivo": f"📊 Desvio global entre setores detectado mas nenhum passou na correção de Bonferroni (N={relatorio['n_total']})",
            "relatorio_vies_fisico": relatorio,
        }

    melhor = suspeitos[0]
    numeros_apostar = melhor["numeros"]
    return {
        "entrar": True,
        "motivo": (
            f"🎯 Viés de setor — mesa N={relatorio['n_total']} | "
            f"setor {melhor['numeros']} saiu {melhor['observado']}x (esperado {melhor['esperado']}) "
            f"| z={melhor['z']} p={melhor['p']} (Bonferroni) | HIPÓTESE, não certeza"
        ),
        "numeros_apostar": numeros_apostar,
        "duzia": None,
        "incluir_zero": 0 in numeros_apostar,
        "confianca": None,
        "relatorio_vies_fisico": relatorio,
    }


def renderizar_painel_vies_fisico(st, rastreador, table_id, table_name, n_setores=6):
    """Painel Streamlit honesto, por SETOR físico — mostra 'coletando dados'
    na maior parte do tempo, e isso é o esperado."""
    relatorio = rastreador.analisar_mesa_setor(table_id, n_setores=n_setores)
    st.markdown(f"### 🎯 Viés por Setor — {table_name}")
    st.caption(f"{n_setores} setores contíguos na ordem física real da roda (não a ordem da mesa)")

    if relatorio["status"] == "sem_dados":
        st.info("Nenhum dado acumulado ainda para esta mesa.")
        return

    if relatorio["status"] == "insuficiente":
        st.warning(
            f"Coletando amostra: {relatorio['n_total']}/{relatorio['n_minimo']} rodadas "
            f"(faltam {relatorio['faltam']})."
        )
        st.progress(min(1.0, relatorio["n_total"] / relatorio["n_minimo"]))
        with st.expander("Ver composição dos setores"):
            for i, setor in enumerate(relatorio["setores"]):
                st.caption(f"Setor {i}: {setor}")
        return

    if not relatorio["scipy_disponivel"]:
        st.error("scipy não disponível — instale `scipy` para habilitar os testes estatísticos.")
        return

    st.caption(f"N acumulado nesta mesa: {relatorio['n_total']} rodadas")
    st.caption(f"χ² = {relatorio['chi2']} ({n_setores - 1} gl) | p global = {relatorio['p_global']} "
               f"| esperado/setor = {relatorio['esperado_por_setor']}")

    if relatorio["significativo_global"]:
        st.error(f"⚠️ Desvio significativo entre setores (p < {RastreadorViesFisico.ALPHA_GLOBAL})")
        if relatorio["setores_suspeitos"]:
            st.write("Setores com desvio individual significativo (Bonferroni):")
            for s in relatorio["setores_suspeitos"]:
                st.caption(
                    f"• Setor {s['indice']} {s['numeros']}: saiu {s['observado']}x "
                    f"(esperado {s['esperado']}) | z={s['z']} | p={s['p']}"
                )
            st.caption("⚠️ Tratar como hipótese a confirmar, não como padrão garantido — "
                       "peeking contínuo infla a taxa real de falso-positivo.")
        else:
            st.caption("Nenhum setor individual passou na correção de Bonferroni.")
    else:
        st.success("✅ Setores estatisticamente uniformes até agora — sem viés detectável")

    with st.expander("Ver contagem por setor"):
        for i, setor in enumerate(relatorio["setores"]):
            obs = relatorio["contagens_setor"][i]
            st.caption(f"Setor {i} {setor}: {obs}x (esperado {relatorio['esperado_por_setor']})")
