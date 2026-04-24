import streamlit as st
import json
import os
import requests
import logging
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import pickle
from datetime import datetime

# Configurações de Persistência e Caminhos
SESSION_DATA_PATH = "session_data_v4.pkl"
HISTORICO_PATH = "historico_roleta.json"

# =============================
# ANALISADOR SNIPER PRO (V4)
# =============================
class AnalisadorRoletaPro:
    def __init__(self, janela_analise=37):
        self.janela_analise = janela_analise
        self.layout_roda = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 
                           11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 
                           9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        self.vermelhos = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        
    def mapear(self, n):
        if n == 0: return {'d': 0, 'c': 0}
        return {'d': (n-1)//12 + 1, 'c': (n-1)%3 + 1}
    
    def get_vizinhos(self, numero, raio=2):
        if numero not in self.layout_roda: return []
        idx = self.layout_roda.index(numero)
        return [self.layout_roda[(idx + i) % 37] for i in range(-raio, raio + 1)]

    def analisar(self, hist, lucky_hist):
        if len(hist) < 20: return None
        
        # Segmentação de janelas
        curto = hist[-12:]
        longo = hist[-self.janela_analise:]
        ultimo = hist[-1]
        
        # 1. Análise de Frequência e Setores
        freq_longo = Counter(longo)
        duzias = Counter([self.mapear(n)['d'] for n in curto if n != 0])
        colunas = Counter([self.mapear(n)['c'] for n in curto if n != 0])
        
        # 2. Identificação de Cluster Físico (Roda)
        roda_check = []
        for n in curto: roda_check.extend(self.get_vizinhos(n, raio=1))
        zona_alvo = Counter(roda_check).most_common(1)[0][0]
        
        # 3. Cálculo de Força Dinâmica
        forca = 0
        gatilhos = []
        
        # Critério A: Confluência Dúzia/Coluna (Peso 40)
        m_duzia = duzias.most_common(1)[0][0] if duzias else None
        m_coluna = colunas.most_common(1)[0][0] if colunas else None
        if duzias.get(m_duzia, 0) >= 5 and colunas.get(m_coluna, 0) >= 5:
            forca += 40
            gatilhos.append(f"D{m_duzia}+C{m_coluna}")

        # Critério B: Repetição de Zona (Peso 40)
        hits_zona = sum(1 for n in curto if n in self.get_vizinhos(zona_alvo, 2))
        if hits_zona >= 4:
            forca += 40
            gatilhos.append("Setor Aquecido")

        # Critério C: Lucky Factor (Peso 20)
        lucky_recentes = [n for sub in lucky_hist[-15:] for n in sub]
        lucky_top = Counter(lucky_recentes).most_common(3)
        lucky_nums = [n[0] for n in lucky_top]
        if any(n in self.get_vizinhos(zona_alvo, 2) for n in lucky_nums):
            forca += 20
            gatilhos.append("Raio Próximo")

        return {
            'forca': min(100, forca),
            'gatilho': " | ".join(gatilhos),
            'zona': zona_alvo,
            'duzia': m_duzia,
            'coluna': m_coluna,
            'quentes': [n[0] for n in freq_longo.most_common(5)],
            'lucky': lucky_nums
        }

# =============================
# MOTOR DO BOT PRO
# =============================
class BotSniperPro:
    def __init__(self):
        self.analisador = AnalisadorRoletaPro()
        self.hist_n = deque(maxlen=100)
        self.hist_l = deque(maxlen=100)
        self.perf = {'w': 0, 'l': 0, 'log': []}

    def sugerir(self, top_n=6, min_f=60):
        res = self.analisador.analisar(list(self.hist_n), list(self.hist_l))
        if not res or res['forca'] < min_f: return None

        aposta = set()
        # Regra de Expansão: Se forca alta, cobre mais vizinhos
        raio = 3 if res['forca'] >= 85 else 2
        aposta.update(self.analisador.get_vizinhos(res['zona'], raio))
        
        # Interseção D/C para refinar
        if res['duzia'] and res['coluna']:
            d_nums = set(range((res['duzia']-1)*12 + 1, res['duzia']*12 + 1))
            c_nums = set(range(res['coluna'], 37, 3))
            inter = d_nums.intersection(c_nums)
            aposta.update(list(inter)[:2]) # Adiciona os 2 melhores da interseção

        # Filtro de resfriamento (não repetir o último número se forca < 90)
        if res['forca'] < 90 and self.hist_n[-1] in aposta:
            aposta.remove(self.hist_n[-1])

        final = list(aposta)[:top_n]
        return {
            'nums': sorted(final),
            'forca': res['forca'],
            'msg': res['gatilho'],
            'conf': "ALTA" if res['forca'] >= 80 else "MÉDIA"
        }

# =============================
# INTERFACE E LÓGICA STREAMLIT
# =============================
st.set_page_config(page_title="Sniper Pro V4", layout="wide")

if "bot" not in st.session_state:
    st.session_state.bot = BotSniperPro()
    st.session_state.historico_local = []

# --- SIDEBAR ---
st.sidebar.header("🕹️ Painel de Controle")
top_n = st.sidebar.slider("Quantidade de Números", 4, 8, 6)
min_f = st.sidebar.slider("Força de Entrada", 40, 90, 60)
st.sidebar.divider()

if st.sidebar.button("🗑️ Resetar Dados"):
    st.session_state.bot = BotSniperPro()
    st.session_state.historico_local = []
    st.rerun()

# --- FUNÇÕES DE API ---
def get_data():
    try:
        r = requests.get("https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest", timeout=5)
        data = r.json()['data']
        res = data['result']
        ln = [x['number'] for x in res.get('luckyNumbersList', [])]
        return {'n': res['outcome']['number'], 'ts': data['startedAt'], 'l': ln}
    except: return None

# --- PROCESSAMENTO ---
refresh = st_autorefresh(interval=4000, key="bot_refresh")
atual = get_data()

if atual:
    ultimo_ts = st.session_state.historico_local[-1]['ts'] if st.session_state.historico_local else ""
    if atual['ts'] != ultimo_ts:
        # Verifica acerto antes de atualizar
        if hasattr(st.session_state, 'previsao'):
            prev = st.session_state.previsao
            if prev:
                win = atual['n'] in prev['nums']
                st.session_state.bot.perf['w' if win else 'l'] += 1
                st.session_state.bot.perf['log'].append(win)
        
        st.session_state.bot.hist_n.append(atual['n'])
        st.session_state.bot.hist_l.append(atual['l'])
        st.session_state.historico_local.append(atual)
        st.session_state.previsao = st.session_state.bot.sugerir(top_n, min_f)

# --- VISUALIZAÇÃO ---
st.title("🎯 Sniper Pro V4 - Inteligência Setorial")

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Greens", st.session_state.bot.perf['w'])
with c2:
    st.metric("Reds", st.session_state.bot.perf['l'])
with c3:
    total = max(1, st.session_state.bot.perf['w'] + st.session_state.bot.perf['l'])
    st.metric("Assertividade", f"{(st.session_state.bot.perf['w']/total)*100:.1f}%")

st.divider()

# Exibição do Sinal
if hasattr(st.session_state, 'previsao') and st.session_state.previsao:
    p = st.session_state.previsao
    color = "green" if p['conf'] == "ALTA" else "orange"
    st.markdown(f"### 📢 SINAL ATIVO: :{color}[{p['conf']}]")
    st.info(f"**Gatilhos:** {p['msg']} | **Força:** {p['forca']}%")
    
    # Números em destaque
    cols = st.columns(len(p['nums']))
    for i, n in enumerate(p['nums']):
        cols[i].button(f"{n}", key=f"btn_{n}", use_container_width=True)
else:
    st.warning("🎲 Aguardando Padrão de Alta Assertividade...")

# Histórico Recente
st.subheader("📜 Últimos Giros")
if st.session_state.historico_local:
    rec = [str(x['n']) for x in st.session_state.historico_local[-15:]]
    st.write(" ← ".join(rec[::-1]))

# Log de Operações
with st.expander("📊 Log de Backtest"):
    for i, res in enumerate(reversed(st.session_state.bot.perf['log'][-10:])):
        st.write(f"Rodada -{i+1}: {'✅ ACERTO' if res else '❌ ERRO'}")
