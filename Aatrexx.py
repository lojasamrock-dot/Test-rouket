import streamlit as st
import json
import os
import requests
import logging
from collections import Counter, deque, defaultdict
from streamlit_autorefresh import st_autorefresh
import pickle
from datetime import datetime
import time

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_roleta.json"
PERFORMANCE_PATH = "performance_bot.json"
PERFORMANCE_MOTORES_PATH = "performance_motores.json"

def salvar_sessao():
    try:
        if 'sistema' not in st.session_state or st.session_state.sistema is None:
            return False
        
        performance_data = {
            'acertos': st.session_state.sistema.bot.performance['acertos'],
            'erros': st.session_state.sistema.bot.performance['erros'],
            'historico': list(st.session_state.sistema.bot.performance['historico'])
        }
        with open(PERFORMANCE_PATH, 'w') as f:
            json.dump(performance_data, f)
        
        perf_motores_serializable = {}
        for motor, dados in st.session_state.sistema.bot.performance_motores.items():
            perf_motores_serializable[motor] = {
                'acertos': dados['acertos'], 'erros': dados['erros'], 'total': dados['total'],
                'historico': list(dados['historico']), 'forca_media': dados['forca_media'],
                'ultima_forca': dados['ultima_forca']
            }
        with open(PERFORMANCE_MOTORES_PATH, 'w') as f:
            json.dump(perf_motores_serializable, f)
        
        session_data = {
            'historico': st.session_state.get('historico', []),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'sistema_acertos': st.session_state.sistema.acertos,
            'sistema_erros': st.session_state.sistema.erros,
            'historico_numeros': list(st.session_state.sistema.bot.historico),
            'historico_lucky': list(st.session_state.sistema.bot.lucky),
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'top_n_apostas': st.session_state.get('top_n_apostas', 13),
            'forca_minima_entrada': st.session_state.get('forca_minima_entrada', 30),
            'repetir_entrada': st.session_state.get('repetir_entrada', True),
            'repetir_acerto': st.session_state.get('repetir_acerto', True),
            'max_repeticoes_acerto': st.session_state.get('max_repeticoes_acerto', 3),
            'ultima_entrada_numeros': st.session_state.sistema.ultima_entrada_numeros
        }
        
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f)
        return True
    except Exception as e:
        logging.error(f"❌ Erro ao salvar: {e}")
        return False

def carregar_dados_persistidos():
    if os.path.exists(SESSION_DATA_PATH):
        try:
            with open(SESSION_DATA_PATH, 'rb') as f: return pickle.load(f)
        except: pass
    return None

# =============================
# NOTIFICAÇÕES & API
# =============================
def enviar_telegram(mensagem):
    token = st.session_state.get('telegram_token')
    chat_id = st.session_state.get('telegram_chat_id')
    if not token or not chat_id: return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}, timeout=10)
        return True
    except: return False

API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# =============================
# ROLETA BASE & MOTORES ÚNICOS
# =============================
class RoletaBase:
    def __init__(self):
        self.race = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        self.vermelhos = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        self.pretos = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
        self.voisins_du_zero = {22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25}
        self.orphelins = {1, 20, 14, 31, 9, 17, 34, 6}
        self.tiers_du_cylindre = {27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33}

    def get_vizinhos(self, numero, raio=2):
        if numero not in self.race: return []
        idx = self.race.index(numero)
        return [self.race[(idx + i) % 37] for i in range(-raio, raio + 1)]

    def get_distancia_fisica(self, n1, n2):
        idx1, idx2 = self.race.index(n1), self.race.index(n2)
        dist = abs(idx1 - idx2)
        return min(dist, 37 - dist)

    def get_setor_frances(self, numero):
        if numero in self.voisins_du_zero: return 'Voisins'
        if numero in self.orphelins: return 'Orphelins'
        if numero in self.tiers_du_cylindre: return 'Tiers'
        return 'Zero' if numero == 0 else 'Outro'

# --- Estratégias Filtradas (Sem Redundância) ---

class EstrategiaSniper:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico):
        if len(historico) < 15: return None
        recentes = historico[-15:]
        duzias = Counter([(n-1)//12+1 for n in recentes if n != 0])
        colunas = Counter([(n-1)%3+1 for n in recentes if n != 0])
        melhor_d = duzias.most_common(1)[0][0] if duzias else 1
        melhor_c = colunas.most_common(1)[0][0] if colunas else 1
        base = set(range((melhor_d-1)*12+1, melhor_d*12+1)).intersection(set(range(melhor_c, 37, 3)))
        return {'base': base, 'forca': 60, 'estrategias': ['Sniper D/C']}

class EstrategiaMarkov:
    def __init__(self): self.transicoes = defaultdict(list)
    def analisar(self, historico):
        if len(historico) < 15: return None
        for i in range(len(historico)-1): self.transicoes[historico[i]].append(historico[i+1])
        ultimo = historico[-1]
        seguidores = self.transicoes.get(ultimo, [])
        if seguidores:
            top = [n for n, c in Counter(seguidores).most_common(5) if c >= 2]
            return {'base': set(top[:6]), 'forca': 55, 'estrategias': ['Markov Chain']}
        return None

class EstrategiaFrequencia:
    def analisar(self, historico):
        if len(historico) < 10: return None
        quentes = [n for n, _ in Counter(historico[-20:]).most_common(6)]
        return {'base': set(quentes), 'forca': 45, 'estrategias': ['Hot Numbers']}

class EstrategiaGap:
    def analisar(self, historico):
        if len(historico) < 5: return None
        ultimo = historico[-1]
        if len(historico) >= 4 and (historico[-3] == ultimo or historico[-4] == ultimo):
            return {'base': {ultimo, historico[-2]}, 'forca': 65, 'estrategias': ['Gap Repetition']}
        return None

class EstrategiaTerminais:
    def __init__(self): self.mapa = {i: [n for n in range(37) if n%10==i] for i in range(10)}
    def analisar(self, historico):
        if len(historico) < 12: return None
        finais = Counter([n%10 for n in historico[-15:]])
        base, t = set(), finais.most_common(1)[0]
        if t[1] >= 3:
            base.update(self.mapa[t[0]])
            return {'base': base, 'forca': 50 + (t[1]*5), 'estrategias': [f'Terminal {t[0]}']}
        return None

class EstrategiaSetoresFranceses:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico):
        if len(historico) < 5: return None
        ultimo = historico[-1]
        setor = self.roleta.get_setor_frances(ultimo)
        if setor == 'Orphelins': return {'base': self.roleta.voisins_du_zero, 'forca': 55, 'estrategias': ['Ponte Orph->Voisins']}
        if setor == 'Voisins': return {'base': self.roleta.voisins_du_zero, 'forca': 45, 'estrategias': ['Voisins Heat']}
        return None

class EstrategiaSaltoFisico:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico):
        if len(historico) < 6: return None
        dists = [self.roleta.get_distancia_fisica(historico[i], historico[i+1]) for i in range(len(historico)-5, len(historico)-1)]
        if all(d <= 4 for d in dists):
            return {'base': set(self.roleta.get_vizinhos(historico[-1], 3)), 'forca': 60, 'estrategias': ['Cluster Fisico']}
        return None

# =============================
# BOT UNIFICADO (17 MOTORES SELECIONADOS)
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        self.motores = {
            'sniper': EstrategiaSniper(self.roleta),
            'markov': EstrategiaMarkov(),
            'freq': EstrategiaFrequencia(),
            'gap': EstrategiaGap(),
            'terminais': EstrategiaTerminais(),
            'frances': EstrategiaSetoresFranceses(self.roleta),
            'salto': EstrategiaSaltoFisico(self.roleta),
            'quadrantes': lambda h: {'base': set(range(1,10)), 'forca': 40, 'estrategias':['Q1 Heat']} if all(n > 9 for n in h[-6:]) else None,
            'simetria': lambda h: {'base': {int(str(h[-1])[::-1]) if h[-1] > 10 and int(str(h[-1])[::-1]) <= 36 else h[-1]}, 'forca': 50, 'estrategias':['Mirror']} if h else None,
            'zero_hunt': lambda h: {'base': {0, 32, 26, 3, 35, 15}, 'forca': 60, 'estrategias':['Zero Hunt']} if 0 not in h[-20:] else None,
            'cor_reversal': lambda h: {'base': self.roleta.vermelhos, 'forca': 50, 'estrategias':['Red Reversal']} if all(n in self.roleta.pretos for n in h[-5:]) else None,
            'lucky_hunt': lambda h, l: {'base': set(l[-3:] if l else []), 'forca': 45, 'estrategias':['Lightning Hunt']} if l else None,
            'espelho_temp': lambda h: {'base': {h[-8]}, 'forca': 40, 'estrategias':['Temporal Mirror']} if len(h) > 10 and h[-1] == h[-9] else None,
            'duzias_atraso': lambda h: {'base': set(range(25,37)), 'forca': 50, 'estrategias':['D3 Atrasada']} if not any(25<=n<=36 for n in h[-8:]) else None,
            'momentum': lambda h: {'base': self.roleta.tiers_du_cylindre, 'forca': 55, 'estrategias':['Tiers Momentum']} if Counter([self.roleta.get_setor_frances(n) for n in h[-10:]])['Tiers'] >= 4 else None,
            'sombra': lambda h, l: {'base': set(l[-1:] if l else []), 'forca': 50, 'estrategias':['Shadow Lucky']} if l else None,
            'terminal_fixo': lambda h: {'base': {3, 13, 23, 33, 6, 16, 26, 36, 9, 19, 29}, 'forca': 45, 'estrategias':['T-369 Heat']} if sum(1 for n in h[-10:] if n%10 in [3,6,9]) >= 4 else None
        }
        self.historico = []
        self.lucky = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': deque(maxlen=50)}
        self.performance_motores = {k: {'acertos':0, 'erros':0, 'total':0, 'historico':[], 'forca_media':0, 'ultima_forca':0} for k in self.motores.keys()}
        self._ultimo_timestamp = None

    def atualizar(self, numero, timestamp=None, lucky_nums=None):
        if timestamp and self._ultimo_timestamp == timestamp: return False
        self._ultimo_timestamp = timestamp
        self.historico.append(numero)
        self.lucky.append(lucky_nums or [])
        if len(self.historico) > 150: self.historico.pop(0); self.lucky.pop(0)
        return True

    def analisar_e_prever(self, top_n=13, forca_minima=30):
        if len(self.historico) < 10: return None
        votos = Counter()
        meta_dados = []
        
        for k, motor in self.motores.items():
            res = motor(self.historico, self.lucky[-1]) if callable(motor) and k in ['lucky_hunt', 'sombra'] else \
                  motor(self.historico) if callable(motor) else motor.analisar(self.historico)
            
            if res and res['forca'] >= forca_minima:
                for n in res['base']: votos[n] += (res['forca'] / 100)
                meta_dados.append((k, res))

        if not votos: return None
        
        # Ordenação por peso e seleção do top N
        sorted_nums = [n for n, v in votos.most_common(top_n)]
        avg_forca = int(sum(r['forca'] for _, r in meta_dados) / len(meta_dados))
        
        return {
            'numeros_apostar': sorted(sorted_nums),
            'forca_real': min(100, avg_forca),
            'motor': meta_dados[0][0],
            'estrategias_ativas': [r['estrategias'][0] for _, r in meta_dados][:3]
        }

# =============================
# SISTEMA & STREAMLIT
# =============================
class SistemaBot:
    def __init__(self):
        self.bot = RoletaBotUnificado()
        self.previsao_ativa = None
        self.acertos = 0
        self.erros = 0
        self.ultima_entrada_numeros = []

    def processar_novo_numero(self, data):
        num = data['number']
        if not self.bot.atualizar(num, data.get('timestamp'), data.get('luckyNumbers')): return
        
        if self.previsao_ativa:
            acerto = num in self.previsao_ativa['numeros_apostar']
            if acerto: self.acertos += 1
            else: self.erros += 1
            self.bot.performance['acertos'] = self.acertos
            self.bot.performance['erros'] = self.erros
            self.previsao_ativa = None
            st.toast(f"{'✅' if acerto else '❌'} Número: {num}")

        # Gera nova previsão
        nova = self.bot.analisar_e_prever(st.session_state.get('top_n_apostas', 13), st.session_state.get('forca_minima_entrada', 30))
        if nova:
            self.previsao_ativa = nova
            self.ultima_entrada_numeros = nova['numeros_apostar']

# --- Interface Streamlit ---
st.set_page_config(page_title="Elite Master - Bot 17 Motores", layout="centered")
st.title("🎯 Bot Unificado (17 Motores)")

if "sistema" not in st.session_state: st.session_state.sistema = SistemaBot()

# Sidebar
st.sidebar.header("Configurações")
st.session_state.top_n_apostas = st.sidebar.slider("Números", 10, 15, 13)
st.session_state.forca_minima_entrada = st.sidebar.slider("Força Mínima", 20, 60, 35)

if st.sidebar.button("Limpar Dados"):
    if os.path.exists(SESSION_DATA_PATH): os.remove(SESSION_DATA_PATH)
    st.rerun()

# Lógica de Update
res_api = fetch_latest_result() if st.session_state.get('modo_automatico', True) else None
if res_api:
    st.session_state.sistema.processar_novo_numero(res_api)

# UI Principal
sis = st.session_state.sistema
c1, c2, c3 = st.columns(3)
c1.metric("Acertos", sis.acertos)
c2.metric("Erros", sis.erros)
c3.metric("Taxa", f"{(sis.acertos/(sis.acertos+sis.erros)*100 if (sis.acertos+sis.erros)>0 else 0):.1f}%")

st.divider()

if sis.previsao_ativa:
    p = sis.previsao_ativa
    st.subheader(f"🔥 Entrada Ativa ({p['forca_real']}%)")
    st.caption(f"Motores: {', '.join(p['estrategias_ativas'])}")
    st.markdown(f"### {', '.join(map(str, p['numeros_apostar']))}")
else:
    st.info("Aguardando análise dos motores...")

st_autorefresh(interval=5000, key="bot_refresh")
salvar_sessao()
