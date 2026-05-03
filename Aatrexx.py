import streamlit as st
import json
import os
import requests
import logging
import random
from collections import Counter, deque, defaultdict
from streamlit_autorefresh import st_autorefresh
import pickle
from datetime import datetime
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_roleta.json"
PERFORMANCE_PATH = "performance_bot.json"
ENTRADAS_PATH = "historico_entradas.json"

def salvar_sessao():
    try:
        if 'sistema' not in st.session_state or st.session_state.sistema is None:
            return False
        sis = st.session_state.sistema
        
        performance_data = {
            'acertos': sis.acertos,
            'erros': sis.erros
        }
        with open(PERFORMANCE_PATH, 'w') as f:
            json.dump(performance_data, f)
        
        with open(ENTRADAS_PATH, 'w') as f:
            json.dump(sis.historico_entradas, f)
        
        session_data = {
            'historico': st.session_state.get('historico', []),
            'historico_numeros': list(sis.historico_numeros),
            'entrada_ativa': sis.entrada_ativa,
            'sistema_acertos': sis.acertos,
            'sistema_erros': sis.erros,
            'modo_duzia_ai': st.session_state.get('modo_duzia_ai', True),
            'janela_duzia_ai': st.session_state.get('janela_duzia_ai', 30),
            'acertos_duzia': st.session_state.get('acertos_duzia', 0),
            'erros_duzia': st.session_state.get('erros_duzia', 0),
            'acertos_duzia_sec': st.session_state.get('acertos_duzia_sec', 0),
            'erros_duzia_sec': st.session_state.get('erros_duzia_sec', 0),
            'modo_agressivo': st.session_state.get('modo_agressivo', False),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'modo_automatico': st.session_state.get('modo_automatico', True),
        }
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f)
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar: {e}")
        return False

def carregar_dados_persistidos():
    try:
        if os.path.exists(SESSION_DATA_PATH):
            with open(SESSION_DATA_PATH, 'rb') as f:
                return pickle.load(f)
    except:
        pass
    return None

def limpar_sessao():
    try:
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH, ENTRADAS_PATH]:
            if os.path.exists(path):
                os.remove(path)
        st.session_state.clear()
        st.rerun()
    except Exception as e:
        logging.error(f"Erro ao limpar sessão: {e}")

# =============================
# NOTIFICAÇÕES
# =============================
def enviar_previsao_auto(previsao):
    try:
        numeros = sorted(previsao.get('numeros_apostar', []))
        forca = previsao.get('forca_real', 0)
        motor = previsao.get('motor', '')
        gatilho = previsao.get('gatilho', '')
        
        emoji = "🔥" if forca >= 65 else "🎯" if forca >= 55 else "⚠️"
        st.toast(f"{emoji} {motor} - {forca}%")
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"🔔 F{forca}% | {motor}\n{gatilho}\n🔢 " + " ".join(map(str, numeros)))
        
        salvar_sessao()
    except:
        pass

def enviar_resultado_auto(numero_real, acerto, lucky=False):
    try:
        st.toast(f"{'✅' if acerto else '❌'} {numero_real}" + (" 🍀" if lucky else ""))
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"📢 {'✅' if acerto else '❌'} {numero_real}" + (" 🍀" if lucky else ""))
        salvar_sessao()
    except:
        pass

def enviar_telegram(mensagem):
    try:
        token = st.session_state.get('telegram_token', '')
        chat_id = st.session_state.get('telegram_chat_id', '')
        if not token or not chat_id:
            return
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"},
            timeout=10
        )
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Erro ao enviar Telegram: {e}")

# =============================
# API
# =============================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# =============================
# FUNÇÕES DE MAPEAMENTO
# =============================
def get_duzia(numero):
    if numero == 0: return 0
    elif 1 <= numero <= 12: return 1
    elif 13 <= numero <= 24: return 2
    else: return 3

# =============================
# 🧠 DUZIA AI V3.5 PRO
# =============================
class DuziaAI:
    def __init__(self, window=30):
        self.historico = deque(maxlen=window)
        self.historico_completo = []
        self.numeros_completos = []
    
    def adicionar(self, numero):
        d = get_duzia(numero)
        self.historico.append(d)
        self.historico_completo.append(d)
        self.numeros_completos.append(numero)
        if len(self.historico_completo) > 200:
            self.historico_completo = self.historico_completo[-200:]
        if len(self.numeros_completos) > 200:
            self.numeros_completos = self.numeros_completos[-200:]
    
    def frequencia_ponderada(self):
        freq = Counter()
        total = len(self.historico)
        for i, d in enumerate(self.historico):
            pos = i / max(1, total - 1)
            peso = 1 + (pos ** 1.5) * 7
            freq[d] += peso
        return freq
    
    def frequencia(self):
        return Counter(self.historico)
    
    def streak(self):
        if not self.historico:
            return 0, None
        last = self.historico[-1]
        count = 0
        for d in reversed(self.historico):
            if d == last:
                count += 1
            else:
                break
        return count, last
    
    def transicao(self):
        if len(self.historico) < 2:
            return None
        return self.historico[-2], self.historico[-1]
    
    def matriz_transicao(self):
        matriz = {1: {1: 0, 2: 0, 3: 0},
                  2: {1: 0, 2: 0, 3: 0},
                  3: {1: 0, 2: 0, 3: 0}}
        totais = {1: 0, 2: 0, 3: 0}
        for i in range(len(self.historico_completo) - 1):
            o = self.historico_completo[i]
            d = self.historico_completo[i + 1]
            if o != 0 and d != 0:
                peso = 1 + (i / max(1, len(self.historico_completo))) * 2
                matriz[o][d] += peso
                totais[o] += peso
        prob = {}
        for o in [1, 2, 3]:
            prob[o] = {}
            for d in [1, 2, 3]:
                prob[o][d] = (matriz[o][d] / totais[o] * 100) if totais[o] > 0 else 33.3
        return prob
    
    def detectar_ciclos(self):
        if len(self.historico) < 6:
            return None
        u = list(self.historico)
        if len(u) >= 4 and u[-4] == u[-2] and u[-3] == u[-1] and u[-4] != u[-3]:
            return u[-3]
        if len(u) >= 6 and u[-6:-3] == u[-3:]:
            return u[-6]
        return None
    
    def ausencia(self):
        aus = {1: 0, 2: 0, 3: 0}
        for d in reversed(self.historico):
            for dz in aus:
                if d != dz:
                    aus[dz] += 1
        dz = max(aus, key=aus.get)
        if aus[dz] >= 6:
            return dz, aus[dz]
        return None
    
    def terminais(self):
        if len(self.numeros_completos) < 10:
            return None
        nums = self.numeros_completos[-10:]
        terms = [n % 10 for n in nums if n != 0]
        top = [t[0] for t in Counter(terms).most_common(2)]
        score = {1: 0, 2: 0, 3: 0}
        for n in range(1, 37):
            dz = get_duzia(n)
            if n % 10 in top:
                score[dz] += 1
        best = max(score, key=score.get)
        if score[best] >= 4:
            return best, score[best]
        return None
    
    def detectar_regime(self):
        freq = self.frequencia()
        total = sum(freq.values())
        if total == 0:
            return "NEUTRO"
        if max(freq.values()) / total > 0.5:
            return "DOMINANTE"
        elif len([d for d in freq if freq[d] > 0]) == 3:
            return "DISTRIBUIDO"
        else:
            return "TRANSICAO"
    
    def calcular_score(self):
        score = {1: 0, 2: 0, 3: 0}
        freq = self.frequencia_ponderada()
        streak_count, streak_d = self.streak()
        trans = self.transicao()
        prob = self.matriz_transicao()
        regime = self.detectar_regime()
        
        for d in score:
            score[d] += freq[d] * 0.7
        
        if streak_d:
            score[streak_d] += streak_count * (2.5 if regime == "DOMINANTE" else 1.5)
        
        if trans and regime != "DOMINANTE":
            ant, _ = trans
            if ant != 0:
                score[ant] += 2
        
        if streak_count >= 3:
            viz = {1: 2, 2: 3, 3: 2}
            if streak_d in viz:
                score[viz[streak_d]] += 4
        
        if self.historico:
            ultima = self.historico[-1]
            for d in score:
                p = prob[ultima][d]
                if p > 45:
                    score[d] += (p - 35) / 10
        
        ciclo = self.detectar_ciclos()
        if ciclo and max(score.values()) > 5:
            score[ciclo] += 4
        
        aus = self.ausencia()
        if aus:
            dz, g = aus
            score[dz] += min(4, g * 0.4)
        
        term = self.terminais()
        if term:
            dz, q = term
            score[dz] += q * 0.2
        
        total = sum(score.values())
        if total > 0:
            for d in score:
                score[d] = (score[d] / total) * 100
        
        return score, regime
    
    def prever(self):
        score, regime = self.calcular_score()
        ranking = sorted(score.items(), key=lambda x: x[1], reverse=True)
        d1, s1 = ranking[0]
        d2, s2 = ranking[1]
        
        ratio = s1 / max(1, s2)
        vol = np.std(list(score.values()))
        confianca = (ratio * 2) + (1 / (1 + vol))
        
        if regime == "DISTRIBUIDO" or confianca < 4:
            return {
                "entrar": False,
                "motivo": "Mercado ruim" if regime == "DISTRIBUIDO" else "Confiança baixa",
                "score": score,
                "regime": regime,
                "confianca": round(confianca, 2),
                "duzia": d1,
                "duzia_secundaria": d2
            }
        
        return {
            "entrar": True,
            "duzia": d1,
            "duzia_secundaria": d2,
            "confianca": round(confianca, 2),
            "score": score,
            "regime": regime
        }

# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaBot:
    def __init__(self):
        janela = st.session_state.get('janela_duzia_ai', 30)
        self.duzia_ai = DuziaAI(window=janela)
        self.historico_numeros = deque(maxlen=200)
        self.entrada_ativa = None
        self.historico_entradas = []
        self.acertos = 0
        self.erros = 0
        self.ultimo_numero = None
    
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data['number']
        else:
            nr = int(numero_data)
        
        self.duzia_ai.adicionar(nr)
        self.historico_numeros.append(nr)
        self.ultimo_numero = nr
        
        # Verifica acerto da entrada anterior
        if self.entrada_ativa:
            duzia_real = get_duzia(nr)
            duzia_prevista = self.entrada_ativa.get('duzia_prevista')
            duzia_sec_prevista = self.entrada_ativa.get('duzia_sec_prevista')
            
            acerto_primaria = (duzia_real == duzia_prevista) if duzia_prevista and nr != 0 else False
            acerto_secundaria = (duzia_real == duzia_sec_prevista) if duzia_sec_prevista and nr != 0 else False
            
            if acerto_primaria:
                self.acertos += 1
                st.session_state.acertos_duzia = st.session_state.get('acertos_duzia', 0) + 1
            elif acerto_secundaria:
                st.session_state.acertos_duzia_sec = st.session_state.get('acertos_duzia_sec', 0) + 1
                self.acertos += 0.5
            else:
                self.erros += 1
                st.session_state.erros_duzia = st.session_state.get('erros_duzia', 0) + 1
            
            entrada_info = {
                'rodada': len(self.historico_numeros) - 1,
                'hora': datetime.now().strftime('%H:%M:%S'),
                'resultado': nr,
                'acerto': acerto_primaria or acerto_secundaria,
                'duzia_prevista': duzia_prevista,
                'duzia_sec_prevista': duzia_sec_prevista,
                'duzia_real': duzia_real,
                'acerto_primaria': acerto_primaria,
                'acerto_secundaria': acerto_secundaria,
            }
            self.historico_entradas.append(entrada_info)
            if len(self.historico_entradas) > 50:
                self.historico_entradas = self.historico_entradas[-50:]
            
            enviar_resultado_auto(nr, acerto_primaria or acerto_secundaria)
            self.entrada_ativa = None
        
        # Gera nova previsão
        previsao = self.duzia_ai.prever()
        
        if previsao['entrar']:
            duzia_map = {
                1: list(range(1, 13)),
                2: list(range(13, 25)),
                3: list(range(25, 37))
            }
            
            numeros_principais = duzia_map.get(previsao['duzia'], [])
            numeros_secundarios = duzia_map.get(previsao.get('duzia_secundaria', previsao['duzia']), [])
            
            if st.session_state.get('modo_agressivo', False) and previsao.get('duzia_secundaria'):
                numeros_apostar = list(set(numeros_principais + numeros_secundarios))
            else:
                numeros_apostar = numeros_principais
            
            self.entrada_ativa = {
                'numeros_apostar': numeros_apostar,
                'duzia_prevista': previsao['duzia'],
                'duzia_sec_prevista': previsao.get('duzia_secundaria'),
                'confianca': previsao.get('confianca', 0),
                'regime': previsao.get('regime', 'NEUTRO'),
                'score': previsao.get('score', {})
            }
            
            enviar_previsao_auto({
                'numeros_apostar': numeros_apostar,
                'forca_real': min(95, previsao.get('confianca', 0) * 8),
                'motor': f"DuziaAI D{previsao['duzia']}",
                'gatilho': f"Regime: {previsao.get('regime', '?')} | Conf: {previsao.get('confianca', 0):.1f}"
            })
    
    def zerar(self):
        self.acertos = 0
        self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear()
        self.entrada_ativa = None
        self.ultimo_numero = None
        janela = st.session_state.get('janela_duzia_ai', 30)
        self.duzia_ai = DuziaAI(window=janela)
        st.session_state.acertos_duzia = 0
        st.session_state.erros_duzia = 0
        st.session_state.acertos_duzia_sec = 0
        st.session_state.erros_duzia_sec = 0
        salvar_sessao()

# =============================
# FUNÇÕES AUXILIARES
# =============================
def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    try:
        with open(caminho, "w") as f:
            json.dump(historico, f, indent=2)
    except:
        pass

def fetch_latest_result():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=5)
        r.raise_for_status()
        d = r.json()
        gd = d.get("data", {})
        rs = gd.get("result", {})
        nm = rs.get("outcome", {}).get("number")
        ts = gd.get("startedAt")
        ln, lm = [], {}
        for item in rs.get('luckyNumbersList', []):
            n = item.get('number')
            if n is not None:
                ln.append(n)
                m = item.get('roundedMultiplier')
                if m is not None:
                    lm[n] = m
        return {"number": nm, "timestamp": ts, "luckyNumbers": ln, "luckyMultipliers": lm}
    except Exception as e:
        logging.warning(f"Erro ao buscar API: {e}")
        return None

def exportar_historico(historico, formato='json'):
    if formato == 'json':
        return json.dumps(historico, indent=2, ensure_ascii=False)
    linhas = ["numero,timestamp,multiplicador"]
    for item in historico:
        if isinstance(item, dict):
            n = item.get('number', '')
            linhas.append(f"{n},{item.get('timestamp','')},{item.get('luckyMultipliers',{}).get(n,'')}")
        else:
            linhas.append(f"{item},,")
    return "\n".join(linhas)

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎰 DuziaAI V3.5 PRO - Dashboard", layout="wide")
st.title("🎰 DuziaAI V3.5 PRO - Dashboard Profissional")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    sis = st.session_state.sistema
    numeros = dados.get('historico_numeros', [])
    for n in numeros:
        sis.duzia_ai.adicionar(n)
        sis.historico_numeros.append(n)
    sis.acertos = dados.get('sistema_acertos', 0)
    sis.erros = dados.get('sistema_erros', 0)
    sis.entrada_ativa = dados.get('entrada_ativa', None)
    st.session_state.acertos_duzia = dados.get('acertos_duzia', 0)
    st.session_state.erros_duzia = dados.get('erros_duzia', 0)
    st.session_state.acertos_duzia_sec = dados.get('acertos_duzia_sec', 0)
    st.session_state.erros_duzia_sec = dados.get('erros_duzia_sec', 0)
    st.session_state.modo_agressivo = dados.get('modo_agressivo', False)
    if os.path.exists(ENTRADAS_PATH):
        try:
            with open(ENTRADAS_PATH, 'r') as f:
                sis.historico_entradas = json.load(f)
        except:
            pass

defaults = {
    'modo_automatico': True,
    'modo_duzia_ai': True,
    'modo_agressivo': False,
    'janela_duzia_ai': 30,
    'acertos_duzia': 0,
    'erros_duzia': 0,
    'acertos_duzia_sec': 0,
    'erros_duzia_sec': 0,
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "historico" not in st.session_state:
    st.session_state.historico = []
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                st.session_state.historico = json.load(f)
        except:
            pass

if "telegram_token" not in st.session_state:
    st.session_state.telegram_token = ""
if "telegram_chat_id" not in st.session_state:
    st.session_state.telegram_chat_id = ""

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.markdown("## ⚙️ Configurações")
    
    st.session_state.janela_duzia_ai = st.slider(
        "📏 Janela de Análise",
        10, 50, st.session_state.janela_duzia_ai, 5,
        help="Quantos giros o motor analisa"
    )
    
    st.session_state.modo_agressivo = st.checkbox(
        "🔥 Modo Agressivo (2 Dúzias)",
        value=st.session_state.modo_agressivo,
        help="Quando ativado, aposta na dúzia principal + secundária"
    )
    
    st.session_state.modo_automatico = st.checkbox(
        "🤖 Modo Automático",
        value=st.session_state.modo_automatico
    )
    
    st.markdown("---")
    
    with st.expander("🔔 Telegram", expanded=False):
        st.session_state.telegram_token = st.text_input(
            "Token", value=st.session_state.telegram_token, type="password"
        )
        st.session_state.telegram_chat_id = st.text_input(
            "Chat ID", value=st.session_state.telegram_chat_id
        )
    
    c1, c2 = st.columns(2)
    c1.button("💾 Salvar", on_click=lambda: [
        salvar_resultado_em_arquivo(st.session_state.historico),
        salvar_sessao(),
        st.success("✅")
    ], use_container_width=True)
    c2.button("🗑️ Zerar", on_click=lambda: st.session_state.sistema.zerar() or st.rerun(), use_container_width=True)

# =============================
# CONTEÚDO PRINCIPAL
# =============================
sis = st.session_state.sistema

# Input de números
st.subheader("🎲 Inserir Números")
c1, c2, c3 = st.columns([3, 1, 1])
with c1:
    entrada = st.text_input(
        "Número (0-36):",
        placeholder="Digite o número sorteado e pressione Enter",
        key="entrada_numero"
    )
with c2:
    if st.button("🎯 Enviar", use_container_width=True, type="primary"):
        if entrada and entrada.isdigit() and 0 <= int(entrada) <= 36:
            nr = int(entrada)
            item = {
                "number": nr,
                "timestamp": datetime.now().isoformat(),
                "luckyNumbers": [],
                "luckyMultipliers": {}
            }
            st.session_state.historico.append(item)
            sis.processar_novo_numero(item)
            salvar_resultado_em_arquivo(st.session_state.historico)
            salvar_sessao()
            st.rerun()
        else:
            st.error("Digite um número válido (0-36)")
with c3:
    if st.button("🔄 Auto", use_container_width=True):
        st.session_state.modo_automatico = not st.session_state.modo_automatico
        st.rerun()

# Auto refresh
if st.session_state.modo_automatico:
    st_autorefresh(interval=3000, key="auto_refresh")
    resultado = fetch_latest_result()
    if resultado and resultado.get("number") is not None:
        if not st.session_state.historico or resultado["timestamp"] != st.session_state.historico[-1].get("timestamp"):
            st.session_state.historico.append(resultado)
            sis.processar_novo_numero(resultado)
            salvar_resultado_em_arquivo(st.session_state.historico)
            salvar_sessao()
            st.rerun()

# =============================
# DASHBOARD PRINCIPAL
# =============================
st.markdown("---")

# Linha 1: Métricas
c1, c2, c3, c4, c5, c6 = st.columns(6)
total_entradas = int(sis.acertos + sis.erros)
tx_acerto = (sis.acertos / total_entradas * 100) if total_entradas > 0 else 0

ac_dz = st.session_state.get('acertos_duzia', 0)
er_dz = st.session_state.get('erros_duzia', 0)
total_dz = ac_dz + er_dz
tx_dz = (ac_dz / total_dz * 100) if total_dz > 0 else 0

c1.metric("✅ Acertos", int(sis.acertos))
c2.metric("❌ Erros", int(sis.erros))
c3.metric("📊 Win Rate", f"{tx_acerto:.1f}%")
c4.metric("🎯 Tx Dúzia Primária", f"{tx_dz:.1f}%")
c5.metric("📦 Total Entradas", total_entradas)
c6.metric("🔥 Modo", "Agressivo" if st.session_state.modo_agressivo else "Conservador")

st.markdown("---")

# Linha 2: Gráficos e Análise
col_grafico, col_entrada = st.columns([3, 2])

with col_grafico:
    st.subheader("📈 Análise em Tempo Real")
    
    if len(sis.historico_numeros) >= 5:
        score, regime = sis.duzia_ai.calcular_score()
        previsao = sis.duzia_ai.prever()
        
        # Gráfico de barras dos scores
        fig = go.Figure(data=[
            go.Bar(
                x=['D1 (1-12)', 'D2 (13-24)', 'D3 (25-36)'],
                y=[score[1], score[2], score[3]],
                marker_color=['#FF6B6B' if score[1] == max(score.values()) else '#4ECDC4',
                             '#FF6B6B' if score[2] == max(score.values()) else '#4ECDC4',
                             '#FF6B6B' if score[3] == max(score.values()) else '#4ECDC4'],
                text=[f'{score[1]:.1f}', f'{score[2]:.1f}', f'{score[3]:.1f}'],
                textposition='auto',
            )
        ])
        fig.update_layout(
            title=f"🎯 Scores das Dúzias | Regime: {regime}",
            yaxis_title="Score Normalizado",
            height=300,
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Gráfico de linha do histórico de dúzias
        if len(sis.historico_numeros) >= 10:
            ultimos_20 = list(sis.historico_numeros)[-20:]
            duzias_hist = [get_duzia(n) for n in ultimos_20]
            
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                y=duzias_hist,
                mode='lines+markers',
                name='Dúzia',
                line=dict(color='#FFD700', width=2),
                marker=dict(size=8)
            ))
            fig2.update_layout(
                title="📉 Histórico de Dúzias (Últimos 20 giros)",
                yaxis=dict(
                    title="Dúzia",
                    tickvals=[1, 2, 3],
                    ticktext=['D1', 'D2', 'D3'],
                    range=[0.5, 3.5]
                ),
                height=250,
                showlegend=False
            )
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info(f"⏳ Aguardando dados... ({len(sis.historico_numeros)}/5 giros mínimos)")

with col_entrada:
    st.subheader("🎰 Entrada Atual")
    
    if sis.entrada_ativa:
        ent = sis.entrada_ativa
        
        confianca = ent.get('confianca', 0)
        duzia_prevista = ent.get('duzia_prevista', 0)
        duzia_sec_prevista = ent.get('duzia_sec_prevista')
        regime = ent.get('regime', 'NEUTRO')
        numeros_apostar = ent.get('numeros_apostar', [])
        
        if confianca >= 6:
            cor = "#00CC00"
        elif confianca >= 4:
            cor = "#FFA500"
        else:
            cor = "#FF4444"
        
        if duzia_prevista == 1:
            limite = "1-12"
        elif duzia_prevista == 2:
            limite = "13-24"
        elif duzia_prevista == 3:
            limite = "25-36"
        else:
            limite = "?"
        
        st.markdown(f"""
        <div style="background-color: {cor}22; border: 2px solid {cor}; border-radius: 15px; padding: 20px; margin: 10px 0;">
            <h2 style="color: {cor}; text-align: center;">🎯 D{duzia_prevista} ({limite})</h2>
            <p style="text-align: center; font-size: 1.2em;">Confiança: {confianca:.2f} | Regime: {regime}</p>
            {f'<p style="text-align: center; color: #FFA500;">🛡️ Cobertura: D{duzia_sec_prevista}</p>' if st.session_state.modo_agressivo and duzia_sec_prevista else ''}
        </div>
        """, unsafe_allow_html=True)
        
        if numeros_apostar:
            st.write("**🎲 Números:**")
            cols = st.columns(6)
            for i, n in enumerate(sorted(numeros_apostar)):
                cols[i % 6].button(str(n), key=f"num_{n}", use_container_width=True)
        else:
            st.warning("Nenhum número disponível para aposta.")
        
    else:
        st.info("🔍 Analisando padrões... Aguardando sinal de entrada.")
        
        if len(sis.historico_numeros) >= 5:
            previsao = sis.duzia_ai.prever()
            if previsao and not previsao.get('entrar', False):
                st.warning(f"⚠️ {previsao.get('motivo', 'Sem sinal claro')}")
                st.caption(f"Regime: {previsao.get('regime', '?')} | Confiança: {previsao.get('confianca', 0)}")
    
    if sis.ultimo_numero is not None:
        st.markdown("---")
        duzia_ultimo = get_duzia(sis.ultimo_numero)
        st.write(f"**🔄 Último Giro:** #{sis.ultimo_numero} → D{duzia_ultimo}")

# Linha 3: Histórico de Entradas
st.markdown("---")
st.subheader("📝 Histórico de Entradas")

if sis.historico_entradas:
    dados_tabela = []
    for e in reversed(sis.historico_entradas[-20:]):
        dados_tabela.append({
            "Rodada": e.get('rodada', '-'),
            "Hora": e.get('hora', '-'),
            "Número": e.get('resultado', '-'),
            "Dúzia Real": f"D{e.get('duzia_real', '?')}" if e.get('duzia_real') else "-",
            "Dúzia Prevista": f"D{e.get('duzia_prevista', '?')}" if e.get('duzia_prevista') else "-",
            "Resultado": "✅" if e.get('acerto_primaria') else "🟡" if e.get('acerto_secundaria') else "❌"
        })
    
    st.dataframe(dados_tabela, use_container_width=True, height=300)
else:
    st.info("Nenhuma entrada registrada ainda.")

# Rodapé
st.markdown("---")
st.caption(f"🤖 DuziaAI V3.5 PRO | Dashboard Profissional | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

salvar_sessao()
