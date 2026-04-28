import streamlit as st
import json
import os
import requests
import logging
from collections import Counter, defaultdict, deque
from streamlit_autorefresh import st_autorefresh
import pickle
from datetime import datetime
import time
import numpy as np

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_roleta.json"
PERFORMANCE_PATH = "performance_bot.json"
PADROES_PATH = "padroes_sequencia.json"
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
                'acertos': dados['acertos'], 'erros': dados['erros'],
                'total': dados['total'], 'historico': list(dados['historico']),
                'forca_media': dados['forca_media'], 'ultima_forca': dados['ultima_forca']
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
            'estrategia_ativa_manual': st.session_state.sistema.estrategia_ativa_manual,
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'top_n_apostas': st.session_state.get('top_n_apostas', 13),
            'intervalo_minimo_entradas': st.session_state.get('intervalo_minimo_entradas', 0),
            'usar_sniper': st.session_state.get('usar_sniper', True),
            'usar_mineracao': st.session_state.get('usar_mineracao', True),
            'usar_giro': st.session_state.get('usar_giro', True),
            'usar_gap': st.session_state.get('usar_gap', True),
            'usar_sequencia': st.session_state.get('usar_sequencia', True),
            'usar_quadrantes': st.session_state.get('usar_quadrantes', True),
            'usar_terminais': st.session_state.get('usar_terminais', True),
            'usar_protecao_zero': st.session_state.get('usar_protecao_zero', True),
            'usar_lightning_hunt': st.session_state.get('usar_lightning_hunt', True),
            'usar_salto_curto': st.session_state.get('usar_salto_curto', True),
            'usar_cadeias_markov': st.session_state.get('usar_cadeias_markov', True),
            'usar_setores_franceses': st.session_state.get('usar_setores_franceses', True),
            'usar_ritmo_repeticao': st.session_state.get('usar_ritmo_repeticao', True),
            'usar_zero_vizinho': st.session_state.get('usar_zero_vizinho', True),
            'usar_ia_adaptativa': st.session_state.get('usar_ia_adaptativa', True),
            'usar_cluster_hibrido': st.session_state.get('usar_cluster_hibrido', True),
            'usar_compressao': st.session_state.get('usar_compressao', True),
            'usar_anti_humano': st.session_state.get('usar_anti_humano', True),
            'usar_rotacao_oculta': st.session_state.get('usar_rotacao_oculta', True),
            'forca_minima_entrada': st.session_state.get('forca_minima_entrada', 30),
            'repetir_entrada': st.session_state.get('repetir_entrada', True),
            'repetir_acerto': st.session_state.get('repetir_acerto', True),
            'max_repeticoes_acerto': st.session_state.get('max_repeticoes_acerto', 3),
            'giros_restantes_espera': st.session_state.sistema.giros_restantes_espera,
            'repeticoes_acerto_consecutivas': st.session_state.sistema.repeticoes_acerto_consecutivas,
            'ultima_entrada_numeros': st.session_state.sistema.ultima_entrada_numeros,
            'ultima_entrada_forca': st.session_state.sistema.ultima_entrada_forca,
            'ultima_entrada_motor': st.session_state.sistema.ultima_entrada_motor,
            'ultima_entrada_green': st.session_state.sistema.ultima_entrada_green
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
    except: pass
    return None

def limpar_sessao():
    try:
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH, PADROES_PATH, PERFORMANCE_MOTORES_PATH]:
            if os.path.exists(path): os.remove(path)
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
    except: pass

# =============================
# NOTIFICAÇÕES
# =============================
def enviar_previsao_auto(previsao):
    try:
        numeros = sorted(previsao['numeros_apostar'])
        forca = previsao.get('forca_real', 0)
        motor = previsao.get('motor', '')
        emoji = "🟢" if previsao.get('green') else "⏳" if previsao.get('repeticao') else "🔥" if forca >= 65 else "🎯" if forca >= 50 else "📊"
        st.toast(f"{emoji} {motor} - {forca}%", icon=emoji)
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"🔔 ENTRADA {forca}%\n🔢 {len(numeros)} números:\n{' '.join(map(str, numeros))}")
        salvar_sessao()
    except Exception as e: logging.error(f"Erro ao enviar previsão: {e}")

def enviar_resultado_auto(numero_real, acerto, multiplicador=None):
    try:
        msg = f"✅ ACERTO! {numero_real}" if acerto else f"❌ ERRO! {numero_real}"
        if multiplicador and multiplicador > 0: msg += f" ⚡{multiplicador}x"
        st.toast(msg, icon="✅" if acerto else "❌")
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"📢 {msg}")
        salvar_sessao()
    except: pass

def enviar_telegram(mensagem):
    try:
        token = st.session_state.get('telegram_token', '')
        chat_id = st.session_state.get('telegram_chat_id', '')
        if not token or not chat_id: return False
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                     json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}, timeout=10)
        return True
    except: return False

def testar_telegram():
    try:
        token = st.session_state.get('telegram_token', '')
        chat_id = st.session_state.get('telegram_chat_id', '')
        if not token or not chat_id: return False, "Token ou Chat ID não configurados"
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": chat_id, "text": "✅ Teste - Bot IA"}, timeout=10)
        return (True, "✅ Conexão OK!") if r.status_code == 200 else (False, f"❌ Erro: {r.status_code}")
    except Exception as e: return False, f"❌ Erro: {str(e)}"

# =============================
# API
# =============================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# =============================
# ROLETA BASE
# =============================
class RoletaBase:
    def __init__(self):
        self.race = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        self.vermelhos = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        self.pretos = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
        self.vizinhos_zero = {0, 32, 26, 3, 35, 12, 28, 7, 29}
        self.voisins_du_zero = {22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25}
        self.orphelins = {1, 20, 14, 31, 9, 17, 34, 6}
        self.tiers_du_cylindre = {27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33}
        self.vizinhos_proximos = {n: set(self.get_vizinhos(n, 1)) for n in self.race}
    
    def get_vizinhos(self, numero, raio=2):
        if numero not in self.race: return []
        idx = self.race.index(numero)
        return [self.race[(idx + i) % 37] for i in range(-raio, raio + 1)]
    
    def get_setor_frances(self, numero):
        if numero in self.voisins_du_zero: return 'Voisins'
        if numero in self.orphelins: return 'Orphelins'
        if numero in self.tiers_du_cylindre: return 'Tiers'
        return 'Zero'
    
    def get_distancia_fisica(self, n1, n2):
        if n1 not in self.race or n2 not in self.race: return 99
        i1, i2 = self.race.index(n1), self.race.index(n2)
        return min(abs(i1 - i2), 37 - abs(i1 - i2))
    
    def get_setor(self, numero): return 0 if numero == 0 else (numero - 1) // 12 + 1
    def get_coluna(self, numero): return 0 if numero == 0 else (numero - 1) % 3 + 1
    def get_cor(self, numero):
        if numero == 0: return 'Verde'
        return 'Vermelho' if numero in self.vermelhos else 'Preto'


# =============================
# ESTRATÉGIAS 1-14 (EXISTENTES)
# =============================
class EstrategiaSniper:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico, lucky_recentes):
        if len(historico) < 15: return None
        recentes = historico[-15:]
        duzias = Counter([self.roleta.get_setor(n) for n in recentes if n != 0])
        colunas = Counter([self.roleta.get_coluna(n) for n in recentes if n != 0])
        md = duzias.most_common(1)[0][0] if duzias else None
        mc = colunas.most_common(1)[0][0] if colunas else None
        roda = [n for r in recentes for n in self.roleta.get_vizinhos(r, 1)]
        zq = Counter(roda).most_common(1)[0][0] if roda else None
        vz = self.roleta.get_vizinhos(zq, 2) if zq else []
        f, b, e = 0, set(), []
        if md and mc and duzias[md] >= 7 and colunas[mc] >= 6:
            f += 60; b.update(set(range((md-1)*12+1, md*12+1)) & set(range(mc, 37, 3))); e.append("Interseção D/C")
        if zq and vz and sum(1 for n in recentes if n in vz) >= 5:
            f += 50; b.update(vz); e.append("Cluster Físico")
        return {'base': b, 'forca': min(100, f), 'estrategias': e} if f and b else None

class EstrategiaMineracao:
    def __init__(self): self.transicoes = defaultdict(list)
    def analisar(self, historico):
        if len(historico) < 10: return None
        self.transicoes.clear()
        for i in range(len(historico)-1): self.transicoes[historico[i]].append(historico[i+1])
        seg = self.transicoes.get(historico[-1], [])
        if seg:
            top = [n for n, c in Counter(seg).most_common(5) if c >= 2]
            if top: return {'base': set(top[:3]), 'forca': 35, 'estrategias': ['Markov']}
        return None

class EstrategiaPorGiro:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico, lucky_recentes):
        if len(historico) < 5: return None
        q = [n for n, _ in Counter(historico[-10:]).most_common(8)]
        return {'base': set(q[:6]), 'forca': 40, 'estrategias': ['Quentes']} if q else None

class EstrategiaGap:
    def analisar(self, historico):
        if len(historico) < 5: return None
        u = historico[-1]
        if len(historico) >= 3 and historico[-3] == u: return {'base': {u, historico[-2]}, 'forca': 60, 'estrategias': ['Gap1']}
        if len(historico) >= 4 and historico[-4] == u: return {'base': {u, historico[-2], historico[-3]}, 'forca': 50, 'estrategias': ['Gap2']}
        return None

class EstrategiaSequencia:
    def __init__(self): self.padroes = defaultdict(list)
    def treinar(self, h):
        self.padroes.clear()
        for i in range(len(h)-1): self.padroes[h[i]].append(h[i+1])
    def prever(self, n, top=10):
        return [x for x, _ in Counter(self.padroes.get(n, [])).most_common(top)]
    def analisar(self, historico):
        if len(historico) < 10: return None
        self.treinar(historico); p = self.prever(historico[-1], 10)
        return {'base': set(p[:6]), 'forca': 50, 'estrategias': ['Sequência']} if len(p) >= 3 else None

class EstrategiaCiclosQuadrantes:
    def __init__(self): self.q = {1: set(range(1,10)), 2: set(range(10,19)), 3: set(range(19,28)), 4: set(range(28,37))}
    def analisar(self, h, janela=8):
        if len(h) < janela: return None
        v = set()
        for n in list(h)[-janela:]:
            for qi, nums in self.q.items():
                if n in nums: v.add(qi); break
        a = set(self.q.keys()) - v
        if a:
            b = set()
            for qi in a: b.update(self.q[qi])
            return {'base': b, 'forca': 50 + len(a)*10, 'estrategias': [f"Quadrantes {a}"]}
        return None

class EstrategiaTerminais:
    def __init__(self): self.t = {i: [n for n in range(37) if n%10==i] for i in range(10)}
    def analisar(self, h, janela=12):
        if len(h) < janela: return None
        f = Counter([n%10 for n in h[-janela:]])
        b, fc, e = set(), 0, []
        for t, c in f.most_common(3):
            if c >= 2: b.update(self.t[t]); fc += 30 + c*5; e.append(f"Terminal {t} ({c}x)")
        return {'base': b, 'forca': min(100, fc), 'estrategias': e} if b else None

class EstrategiaProtecaoZero:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 10: return None
        z = h[-15:].count(0) if len(h) >= 15 else h.count(0)
        if z >= 2: return {'base': self.roleta.vizinhos_zero.copy(), 'forca': 65, 'estrategias': ['Zero Agressivo']}
        if len(h) >= 20 and 0 not in h[-20:]: return {'base': self.roleta.vizinhos_zero.copy(), 'forca': 45, 'estrategias': ['Zero Atrasado']}
        return None

class EstrategiaLightningHunt:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, hl):
        if not hl or len(h) < 3: return None
        lr = [n for sub in list(hl)[-3:] for n in sub]
        if not lr: return None
        b = set(list(set(lr))[:6]); fc = 35
        l10 = [n for sub in (list(hl)[-10:] if hl else []) for n in sub]
        if l10:
            rp = [n for n, c in Counter(l10).items() if c >= 2][:3]
            for n in rp: b.add(n); b.update(self.roleta.get_vizinhos(n, 1)[:2])
            if rp: fc += 20
        return {'base': b, 'forca': min(100, fc), 'estrategias': ['⚡ Lucky']} if b else None

class EstrategiaSaltoCurto:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 5: return None
        r = h[-10:]; sc = sum(1 for i in range(len(r)-1) if 1 <= self.roleta.get_distancia_fisica(r[i], r[i+1]) <= 3)
        tx = sc/(len(r)-1)*100 if len(r)>1 else 0
        b, e, fc = set(), [], 0
        if tx >= 50: b.update(self.roleta.get_vizinhos(h[-1], 3)); fc += 45 + int(tx/2); e.append(f"Salto Curto ({tx:.0f}%)")
        c = sum(1 for i in range(len(h[-5:])-1) if h[-5:][i+1] in self.roleta.vizinhos_proximos.get(h[-5:][i], set()))
        if c >= 2: b.update(self.roleta.get_vizinhos(h[-1], 2)); fc += 45 + c*10; e.append(f"Micro-Clusters ({c})")
        return {'base': b, 'forca': min(100, fc), 'estrategias': e} if b and fc >= 40 else None

class EstrategiaCadeiasMarkov:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 3: return None
        cd = {19:[23,27], 23:[27], 30:[20], 6:[33], 27:[13,36], 20:[14,31], 33:[1,20]}
        u = h[-1]
        if u not in cd: return None
        b = set(cd[u])
        for n in cd[u]: b.update(self.roleta.get_vizinhos(n, 1)[:1])
        fc = 55
        if len(h) >= 4 and h[-3]==19 and h[-2]==23 and h[-1]==27: b.update([13,36]); fc += 20
        return {'base': b, 'forca': min(100, fc), 'estrategias': [f"⛓️ {u}→{cd[u]}"]}

class EstrategiaSetoresFranceses:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 3: return None
        u = h[-1]; s = self.roleta.get_setor_frances(u)
        b, e, fc = set(), [], 0
        if s == 'Orphelins': b.update(self.roleta.voisins_du_zero); fc += 55; e.append("Orphelins→Voisins")
        if s == 'Voisins':
            b.update(self.roleta.voisins_du_zero)
            fc += 60 if len(h)>=2 and self.roleta.get_setor_frances(h[-2])=='Voisins' else 45
            e.append("Auto-Retenção Voisins" if fc>=60 else "Voisins Recente")
        if s == 'Tiers': b.update(self.roleta.voisins_du_zero); fc += 40; e.append("Tiers→Voisins")
        return {'base': b, 'forca': min(100, fc), 'estrategias': e} if b and fc >= 40 else None

class EstrategiaRitmoRepeticao:
    def analisar(self, h):
        if len(h) < 12: return None
        r20 = h[-20:]; ciclos = defaultdict(list)
        for i, n in enumerate(r20): ciclos[n].append(i)
        b, e, fc = set(), [], 0
        for num, pos in ciclos.items():
            if len(pos) >= 3:
                g = [pos[i+1]-pos[i] for i in range(len(pos)-1)]
                if len([x for x in g if 3<=x<=4]) >= 2: b.add(num); fc += 40; e.append(f"Espelho: {num}")
        gc = [r20[i] for i in range(len(r20)-3) if r20[i]==r20[i+3]]
        if len(gc) >= 2:
            top = [n for n, c in Counter(gc).most_common(4) if c >= 1]
            b.update(top); fc += 45; e.append(f"Gap Curto: {top[:3]}")
        rp = [n for n, c in Counter(h[-15:]).items() if c >= 2]
        if len(rp) >= 3: b.update(rp[:5]); fc += 50; e.append(f"Ritmo: {rp[:3]}")
        return {'base': b, 'forca': min(100, fc), 'estrategias': e} if b and fc >= 40 else None

class EstrategiaZeroVizinho:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, hlm):
        if not hlm: return None
        for md in reversed(list(hlm)[-5:]):
            if isinstance(md, dict):
                for n, m in md.items():
                    if m and m >= 200: return {'base': self.roleta.voisins_du_zero.copy(), 'forca': 50, 'estrategias': [f"Voisins após ⚡{n}"]}
        return None


# =============================
# 🆕 ESTRATÉGIA 15: IA ADAPTATIVA (MOTOR V3)
# =============================
class EstrategiaIAAdaptativa:
    """
    Motor IA Adaptativa V3:
    - Frequência dinâmica (janela móvel)
    - Atraso inteligente (normalizado)
    - Transição contextual
    - Entropia do sistema
    Score = 0.4*freq + 0.4*atraso + 0.2*transicao
    """
    def __init__(self):
        self.window = 50
    
    def _freq_score(self, historico):
        buffer = historico[-self.window:]
        contagem = Counter(buffer)
        total = len(buffer)
        return {n: contagem.get(n, 0)/total for n in range(37)}
    
    def _atraso_score(self, historico):
        atraso = {}
        total = len(historico)
        for n in range(37):
            indices = [i for i, x in enumerate(historico) if x == n]
            atraso[n] = (total - indices[-1]) / total if indices else 1.0
        return atraso
    
    def _transicao_score(self, historico):
        if len(historico) < 2: return {n: 0 for n in range(37)}
        ultimo = historico[-1]
        transicoes = defaultdict(list)
        for i in range(len(historico)-1):
            transicoes[historico[i]].append(historico[i+1])
        if ultimo not in transicoes: return {n: 0 for n in range(37)}
        contagem = Counter(transicoes[ultimo])
        total = sum(contagem.values())
        return {n: contagem.get(n, 0)/total for n in range(37)}
    
    def _entropia(self, historico):
        freq = self._freq_score(historico)
        probs = np.array([v for v in freq.values() if v > 0])
        if len(probs) == 0: return 3.5
        return -np.sum(probs * np.log(probs))
    
    def analisar(self, historico):
        if len(historico) < 20: return None
        
        freq = self._freq_score(historico)
        atraso = self._atraso_score(historico)
        trans = self._transicao_score(historico)
        ent = self._entropia(historico)
        
        score = {}
        for n in range(37):
            score[n] = 0.4 * freq.get(n, 0) + 0.4 * atraso.get(n, 0) + 0.2 * trans.get(n, 0)
        
        ranking = sorted(score.items(), key=lambda x: x[1], reverse=True)
        
        # Define modo baseado na entropia
        if ent < 3.0:
            modo = "AGRESSIVO"
            base = set([n for n, _ in ranking[:8]])
            forca = 70
        elif ent < 3.3:
            modo = "MODERADO"
            base = set([n for n, _ in ranking[:12]])
            forca = 55
        else:
            modo = "CONSERVADOR"
            base = set([n for n, _ in ranking[:6]])
            forca = 40
        
        return {
            'base': base,
            'forca': min(100, forca),
            'estrategias': [f"🧠 IA {modo} (Entropia: {ent:.2f})"],
            'entropia': ent,
            'modo': modo,
            'top10': [n for n, _ in ranking[:10]]
        }


# =============================
# 🆕 ESTRATÉGIA 16: CLUSTER HÍBRIDO
# =============================
class EstrategiaClusterHibrido:
    """
    Cluster Híbrido:
    3 HOT + 2 OVERDUE + 1 TRANSIÇÃO
    Combina números quentes, atrasados e de transição recente
    """
    def __init__(self, roleta): self.roleta = roleta
    
    def analisar(self, historico):
        if len(historico) < 15: return None
        
        # Hot numbers (últimos 30 giros)
        recentes = historico[-30:]
        freq = Counter(recentes)
        hots = [n for n, _ in freq.most_common(5)]
        
        # Overdue (mais atrasados)
        total = len(historico)
        atrasos = {}
        for n in range(37):
            indices = [i for i, x in enumerate(historico) if x == n]
            atrasos[n] = (total - indices[-1]) if indices else total
        overdues = sorted(atrasos, key=atrasos.get, reverse=True)[:5]
        
        # Transição do último
        ultimo = historico[-1]
        transicoes = defaultdict(list)
        for i in range(len(historico)-1):
            transicoes[historico[i]].append(historico[i+1])
        trans_ultimo = [n for n, _ in Counter(transicoes.get(ultimo, [])).most_common(3)]
        
        base = set()
        estrategias = []
        
        # 3 HOT
        base.update(hots[:3])
        # 2 OVERDUE (excluindo os já incluídos)
        for n in overdues:
            if n not in base:
                base.add(n)
                if len([x for x in base if x in overdues]) >= 2: break
        # 1 TRANSIÇÃO
        for n in trans_ultimo:
            if n not in base:
                base.add(n); break
        
        estrategias.append(f"🔀 Cluster: {len(hots[:3])}H + {len([x for x in base if x in overdues])}O + {len([x for x in base if x in trans_ultimo])}T")
        
        forca = 50
        return {'base': base, 'forca': forca, 'estrategias': estrategias} if len(base) >= 5 else None


# =============================
# 🆕 ESTRATÉGIA 17: COMPRESSÃO
# =============================
class EstrategiaCompressao:
    """
    Gatilho de Compressão:
    Quando a sequência está espalhada (sem repetição de setores),
    entra pesado em números atrasados + médio quentes
    """
    def __init__(self, roleta): self.roleta = roleta
    
    def analisar(self, historico):
        if len(historico) < 20: return None
        
        ultimos_10 = historico[-10:]
        recentes_30 = historico[-30:]
        
        # Verifica dispersão: quantos setores diferentes nos últimos 10
        setores = [self.roleta.get_setor_frances(n) for n in ultimos_10]
        setores_unicos = len(set(setores))
        
        # Se está muito espalhado (3+ setores diferentes em 10 giros)
        if setores_unicos >= 3:
            # Números atrasados
            total = len(historico)
            atrasos = {}
            for n in range(37):
                indices = [i for i, x in enumerate(historico) if x == n]
                atrasos[n] = (total - indices[-1]) / total if indices else 1.0
            overdues = sorted(atrasos, key=atrasos.get, reverse=True)[:8]
            
            # Médio quentes (frequência moderada)
            freq = Counter(recentes_30)
            medios = [n for n, c in freq.most_common(15) if 1 <= c <= 2][:6]
            
            base = set(overdues[:5] + medios[:4])
            forca = 55 + setores_unicos * 5
            
            return {
                'base': base,
                'forca': min(100, forca),
                'estrategias': [f"🗜️ Compressão ({setores_unicos} setores espalhados)"]
            }
        return None


# =============================
# 🆕 ESTRATÉGIA 18: ANTI-HUMANO
# =============================
class EstrategiaAntiHumano:
    """
    Anti-Humano:
    Evita sequências lógicas (1-2-3, dúzias óbvias)
    Foca em números que não apareceram juntos recentemente
    """
    def __init__(self):
        self.co_ocorrencias = defaultdict(set)
    
    def analisar(self, historico):
        if len(historico) < 15: return None
        
        # Constrói mapa de co-ocorrências recentes
        recentes = historico[-20:]
        self.co_ocorrencias.clear()
        for i in range(len(recentes)-1):
            for j in range(i+1, min(i+6, len(recentes))):
                self.co_ocorrencias[recentes[i]].add(recentes[j])
                self.co_ocorrencias[recentes[j]].add(recentes[i])
        
        # Números que NÃO co-ocorreram com os últimos 3
        ultimos_3 = set(historico[-3:])
        nao_co_ocorreram = []
        
        for n in range(37):
            if n not in ultimos_3:
                co_ocorreu = any(n in self.co_ocorrencias.get(u, set()) for u in ultimos_3)
                if not co_ocorreu:
                    nao_co_ocorreram.append(n)
        
        if len(nao_co_ocorreram) >= 6:
            base = set(nao_co_ocorreram[:8])
            
            # Adiciona números "anti-sequenciais"
            # Evita sequências óbvias como 1-2-3, 10-11-12
            for n in list(base):
                if n > 0 and (n-1) in base and (n+1) in base:
                    base.discard(n+1)  # Remove o meio da sequência
            
            return {
                'base': base,
                'forca': 50,
                'estrategias': [f"🚫 Anti-Humano ({len(base)} números não co-ocorrentes)"]
            }
        return None


# =============================
# 🆕 ESTRATÉGIA 19: ROTAÇÃO OCULTA
# =============================
class EstrategiaRotacaoOculta:
    """
    Rotação Oculta:
    Divide em blocos de 3 e rotaciona entre eles
    Nunca repete o mesmo combo seguido
    """
    def __init__(self):
        self.bloco_atual = 0
        self.ultimo_bloco_usado = -1
    
    def analisar(self, historico):
        if len(historico) < 20: return None
        
        # Gera 3 blocos baseados em análise
        recentes = historico[-30:]
        freq = Counter(recentes)
        
        # Bloco 1: Hot + Overdue
        hots = [n for n, _ in freq.most_common(6)]
        atrasos = {}
        total = len(historico)
        for n in range(37):
            indices = [i for i, x in enumerate(historico) if x == n]
            atrasos[n] = (total - indices[-1]) if indices else total
        overdues = sorted(atrasos, key=atrasos.get, reverse=True)[:3]
        
        blocos = [
            set(hots[:3] + overdues[:1]),                    # Bloco 1: Quentes + 1 atrasado
            set(overdues[:3] + hots[3:4]),                   # Bloco 2: Atrasados + 1 quente
            set(hots[1:4] + overdues[1:3]),                  # Bloco 3: Mistura
        ]
        
        # Rotaciona para o próximo bloco (diferente do último)
        self.bloco_atual = (self.ultimo_bloco_usado + 1) % 3
        if self.bloco_atual == self.ultimo_bloco_usado:
            self.bloco_atual = (self.bloco_atual + 1) % 3
        
        self.ultimo_bloco_usado = self.bloco_atual
        base = blocos[self.bloco_atual]
        
        return {
            'base': base,
            'forca': 45,
            'estrategias': [f"🔄 Rotação Oculta (Bloco {self.bloco_atual + 1}/3)"]
        }


# =============================
# BOT UNIFICADO (19 MOTORES + IA)
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        self.sniper = EstrategiaSniper(self.roleta)
        self.mineracao = EstrategiaMineracao()
        self.giro = EstrategiaPorGiro(self.roleta)
        self.gap = EstrategiaGap()
        self.sequencia = EstrategiaSequencia()
        self.quadrantes_strat = EstrategiaCiclosQuadrantes()
        self.terminais_strat = EstrategiaTerminais()
        self.protecao_zero = EstrategiaProtecaoZero(self.roleta)
        self.lightning_hunt = EstrategiaLightningHunt(self.roleta)
        self.salto_curto = EstrategiaSaltoCurto(self.roleta)
        self.cadeias_markov = EstrategiaCadeiasMarkov(self.roleta)
        self.setores_franceses = EstrategiaSetoresFranceses(self.roleta)
        self.ritmo_repeticao = EstrategiaRitmoRepeticao()
        self.zero_vizinho = EstrategiaZeroVizinho(self.roleta)
        # IA
        self.ia_adaptativa = EstrategiaIAAdaptativa()
        self.cluster_hibrido = EstrategiaClusterHibrido(self.roleta)
        self.compressao = EstrategiaCompressao(self.roleta)
        self.anti_humano = EstrategiaAntiHumano()
        self.rotacao_oculta = EstrategiaRotacaoOculta()
        
        self.historico = []
        self.lucky = []
        self.lucky_mult = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.performance_motores = {}
        self._init_performance_motores()
        self._ultimo_timestamp = None
    
    def _init_performance_motores(self):
        motores = ['Sniper','Mineração','Análise Giro','Gap','Sequência','CicloQuadrantes','Terminais',
                   'ProtecaoZero','LightningHunt','SaltoCurto','CadeiasMarkov','SetoresFranceses',
                   'RitmoRepeticao','ZeroVizinho','IA_Adaptativa','ClusterHibrido',
                   'Compressao','AntiHumano','RotacaoOculta','Green_Repeat','Erro_Repeat']
        for m in motores:
            self.performance_motores[m] = {'acertos': 0, 'erros': 0, 'total': 0, 'historico': [], 'forca_media': 0, 'ultima_forca': 0}
    
    def atualizar(self, numero, timestamp=None, lucky_nums=None, lucky_mults=None):
        if timestamp and self._ultimo_timestamp == timestamp: return False
        self._ultimo_timestamp = timestamp
        self.historico.append(numero)
        self.lucky.append(lucky_nums if lucky_nums else [])
        self.lucky_mult.append(lucky_mults if lucky_mults else {})
        if len(self.historico) > 300: self.historico = self.historico[-300:]; self.lucky = self.lucky[-300:]; self.lucky_mult = self.lucky_mult[-300:]
        if len(self.historico) >= 2: self.sequencia.treinar(list(self.historico))
        return True
    
    def atualizar_resultado(self, acerto):
        self.performance['historico'].append(1 if acerto else 0)
        if len(self.performance['historico']) > 50: self.performance['historico'] = self.performance['historico'][-50:]
        if acerto: self.performance['acertos'] += 1
        else: self.performance['erros'] += 1
    
    def atualizar_performance_motor(self, motor_nome, acerto, forca=0):
        if motor_nome not in self.performance_motores: return
        p = self.performance_motores[motor_nome]
        p['total'] += 1
        if acerto: p['acertos'] += 1
        else: p['erros'] += 1
        p['historico'].append(acerto)
        if len(p['historico']) > 20: p['historico'] = p['historico'][-20:]
        p['ultima_forca'] = forca
        if p['total'] > 0: p['forca_media'] = (p['forca_media']*(p['total']-1)+forca)/p['total']
    
    def get_taxa_motor(self, mn):
        if mn not in self.performance_motores: return 0, 0, 0
        p = self.performance_motores[mn]
        return (p['acertos']/p['total'], p['acertos'], p['total']) if p['total']>0 else (0,0,0)
    
    def get_melhores_motores(self, top_n=5):
        r = [(n, p['acertos']/p['total'], p['acertos'], p['total'], p['forca_media'])
             for n, p in self.performance_motores.items() if p['total'] >= 2]
        r.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return r[:top_n]
    
    def get_taxa_acerto(self):
        t = self.performance['acertos'] + self.performance['erros']
        return self.performance['acertos']/t if t > 0 else 0
    
    def get_total_tentativas(self): return self.performance['acertos'] + self.performance['erros']
    
    def analisar_e_prever(self, top_n=13, motores_ativos=None, forca_minima=30):
        hl = list(self.historico)
        if len(hl) < 5: return None
        
        if motores_ativos is None:
            motores_ativos = {k: True for k in ['sniper','mineracao','giro','gap','sequencia','quadrantes','terminais',
                           'protecao_zero','lightning_hunt','salto_curto','cadeias_markov','setores_franceses',
                           'ritmo_repeticao','zero_vizinho','ia_adaptativa','cluster_hibrido','compressao',
                           'anti_humano','rotacao_oculta']}
        
        lr = [n for sub in list(self.lucky)[-10:] for n in sub]
        resultados = []
        nm = {'sniper':'Sniper','mineracao':'Mineração','giro':'Análise Giro','gap':'Gap','sequencia':'Sequência',
              'quadrantes':'CicloQuadrantes','terminais':'Terminais','protecao_zero':'ProtecaoZero',
              'lightning_hunt':'LightningHunt','salto_curto':'SaltoCurto','cadeias_markov':'CadeiasMarkov',
              'setores_franceses':'SetoresFranceses','ritmo_repeticao':'RitmoRepeticao','zero_vizinho':'ZeroVizinho',
              'ia_adaptativa':'IA_Adaptativa','cluster_hibrido':'ClusterHibrido',
              'compressao':'Compressao','anti_humano':'AntiHumano','rotacao_oculta':'RotacaoOculta'}
        
        est = [
            ('sniper', lambda: self.sniper.analisar(hl, lr), 15),
            ('mineracao', lambda: self.mineracao.analisar(hl), 10),
            ('giro', lambda: self.giro.analisar(hl, lr), 5),
            ('gap', lambda: self.gap.analisar(hl), 5),
            ('sequencia', lambda: self.sequencia.analisar(hl), 10),
            ('quadrantes', lambda: self.quadrantes_strat.analisar(hl), 8),
            ('terminais', lambda: self.terminais_strat.analisar(hl), 8),
            ('protecao_zero', lambda: self.protecao_zero.analisar(hl), 10),
            ('lightning_hunt', lambda: self.lightning_hunt.analisar(hl, list(self.lucky)), 3),
            ('salto_curto', lambda: self.salto_curto.analisar(hl), 5),
            ('cadeias_markov', lambda: self.cadeias_markov.analisar(hl), 3),
            ('setores_franceses', lambda: self.setores_franceses.analisar(hl), 3),
            ('ritmo_repeticao', lambda: self.ritmo_repeticao.analisar(hl), 12),
            ('zero_vizinho', lambda: self.zero_vizinho.analisar(list(self.lucky_mult)), 3),
            ('ia_adaptativa', lambda: self.ia_adaptativa.analisar(hl), 20),
            ('cluster_hibrido', lambda: self.cluster_hibrido.analisar(hl), 15),
            ('compressao', lambda: self.compressao.analisar(hl), 20),
            ('anti_humano', lambda: self.anti_humano.analisar(hl), 15),
            ('rotacao_oculta', lambda: self.rotacao_oculta.analisar(hl), 20),
        ]
        
        for k, f, ml in est:
            if motores_ativos.get(k, True) and len(hl) >= ml:
                try:
                    r = f()
                    if r and r.get('forca', 0) >= forca_minima: resultados.append((nm.get(k, k), r))
                except: pass
        
        if not resultados: return None
        
        fb = Counter()
        for _, r in resultados:
            p = r['forca']/100
            for n in r['base']: fb[n] += p
        
        u10 = hl[-10:]; fr = Counter(u10)
        for n in fb:
            fc = fr.get(n, 0)
            if fc >= 2: fb[n] *= 1.5
            elif fc >= 1: fb[n] *= 1.2
        
        pr = [n for n, _ in fb.most_common()]
        if len(pr) < 12:
            for n, _ in fr.most_common(20):
                if n not in pr: pr.append(n)
                if len(pr) >= 12: break
        if len(pr) < 12:
            td = set()
            for _, r in resultados: td.update(r['base'])
            for n in td:
                if n not in pr: pr.append(n)
                if len(pr) >= 12: break
        
        bl = pr[:15]
        if len(bl) < 12:
            for n in range(37):
                if n not in bl: bl.append(n)
                if len(bl) >= 12: break
        
        te, ft, mp, mf = [], 0, "", 0
        for m, r in resultados:
            te.extend(r.get('estrategias', [])); ft += r['forca']
            if r['forca'] > mf: mf = r['forca']; mp = m
        
        fm = int(ft/len(resultados)) if resultados else 20
        fm = min(100, max(20, fm))
        
        return {
            'nome': 'Bot IA', 'numeros_apostar': sorted(bl),
            'gatilho': f"u={hl[-1]}", 'forca_real': fm,
            'confianca': 'Alta' if fm>=65 else 'Média' if fm>=45 else 'Baixa',
            'motor': mp, 'estrategias_ativas': list(set(te))[:5],
            'qtd_motores': len(resultados), 'repeticao': False, 'green': False, 'green_count': 0, 'giros_esperados': 0
        }
    
    def zerar(self):
        self.historico = []; self.lucky = []; self.lucky_mult = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self._init_performance_motores(); self._ultimo_timestamp = None


# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaBot:
    def __init__(self):
        self.bot = RoletaBotUnificado()
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0; self.erros = 0
        self.rodadas_sem_entrada = 0
        self.ultima_entrada_rodada = -10
        self.estrategia_ativa_manual = False
        self.giros_restantes_espera = 0
        self.repeticoes_acerto_consecutivas = 0
        self.ultima_entrada_green = False
        self.ultima_entrada_numeros = []
        self.ultima_entrada_forca = 0
        self.ultima_entrada_motor = ""
    
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data['number']
            lk = numero_data.get('luckyNumbers', [])
            lm = numero_data.get('luckyMultipliers', {})
            mt = lm.get(nr) if nr in lk else None
            ts = numero_data.get('timestamp', str(time.time()))
        else:
            nr = numero_data; lk = []; lm = {}; mt = None
            ts = str(time.time())
        
        if not self.bot.atualizar(nr, ts, lk, lm): return
        
        self.rodadas_sem_entrada += 1
        if self.giros_restantes_espera > 0: self.giros_restantes_espera -= 1
        
        if self.previsao_ativa:
            ac = nr in self.previsao_ativa.get('numeros_apostar', [])
            self.bot.atualizar_resultado(ac)
            
            mp = self.previsao_ativa.get('motor', '')
            fc = self.previsao_ativa.get('forca_real', 0)
            mperf = 'Green_Repeat' if self.previsao_ativa.get('green') else 'Erro_Repeat' if self.previsao_ativa.get('repeticao') else mp
            
            self.bot.atualizar_performance_motor(mperf, ac, fc)
            
            if ac:
                self.acertos += 1
                if st.session_state.get('repetir_acerto', True):
                    mx = st.session_state.get('max_repeticoes_acerto', 3)
                    if self.repeticoes_acerto_consecutivas < mx:
                        self.repeticoes_acerto_consecutivas += 1
                        self.ultima_entrada_green = True
                        self.ultima_entrada_numeros = self.previsao_ativa.get('numeros_apostar', [])
                        self.ultima_entrada_forca = fc + 10
                        self.ultima_entrada_motor = mp
                    else: self.repeticoes_acerto_consecutivas = 0; self.ultima_entrada_green = False
                self.giros_restantes_espera = 0
            else:
                self.erros += 1; self.repeticoes_acerto_consecutivas = 0; self.ultima_entrada_green = False
                if (st.session_state.get('repetir_entrada', True) and not self.previsao_ativa.get('repeticao')
                    and not self.previsao_ativa.get('green') and fc >= 45):
                    self.giros_restantes_espera = 1
                    self.ultima_entrada_numeros = self.previsao_ativa.get('numeros_apostar', [])
                    self.ultima_entrada_forca = fc; self.ultima_entrada_motor = mp
            
            enviar_resultado_auto(nr, ac, mt)
            self.historico_desempenho.append({'numero': nr, 'acerto': ac, 'multiplicador': mt, 'forca': fc, 'green': self.previsao_ativa.get('green', False), 'motor': mperf})
            self.previsao_ativa = None
            self.ultima_entrada_rodada = len(self.bot.historico)
            self.rodadas_sem_entrada = 0
        
        if self.estrategia_ativa_manual: return
        
        if len(self.bot.historico) >= 5 and len(self.bot.historico) - self.ultima_entrada_rodada >= st.session_state.get('intervalo_minimo_entradas', 0):
            
            if self.ultima_entrada_green and self.ultima_entrada_numeros and self.repeticoes_acerto_consecutivas > 0:
                self.previsao_ativa = {'nome': 'Bot IA', 'numeros_apostar': sorted(self.ultima_entrada_numeros), 'gatilho': f'🟢 GREEN #{self.repeticoes_acerto_consecutivas}!', 'forca_real': min(100, self.ultima_entrada_forca+15), 'confianca': 'Green', 'motor': self.ultima_entrada_motor, 'estrategias_ativas': [f'Green #{self.repeticoes_acerto_consecutivas}'], 'qtd_motores': 1, 'repeticao': False, 'green': True, 'green_count': self.repeticoes_acerto_consecutivas, 'giros_esperados': 0}
                self.ultima_entrada_green = False
                enviar_previsao_auto(self.previsao_ativa)
            elif self.giros_restantes_espera == 0 and self.ultima_entrada_numeros and not self.ultima_entrada_green:
                self.previsao_ativa = {'nome': 'Bot IA', 'numeros_apostar': sorted(self.ultima_entrada_numeros), 'gatilho': '⏳ REPETINDO', 'forca_real': self.ultima_entrada_forca, 'confianca': 'Repetição', 'motor': self.ultima_entrada_motor, 'estrategias_ativas': ['Repetição pós-erro'], 'qtd_motores': 1, 'repeticao': True, 'green': False, 'green_count': 0, 'giros_esperados': 1}
                self.ultima_entrada_numeros = []
                enviar_previsao_auto(self.previsao_ativa)
            elif self.giros_restantes_espera <= 0:
                tn = st.session_state.get('top_n_apostas', 13)
                fn = st.session_state.get('forca_minima_entrada', 30)
                ma = {k: st.session_state.get(f'usar_{k}', True) for k in ['sniper','mineracao','giro','gap','sequencia','quadrantes','terminais','protecao_zero','lightning_hunt','salto_curto','cadeias_markov','setores_franceses','ritmo_repeticao','zero_vizinho','ia_adaptativa','cluster_hibrido','compressao','anti_humano','rotacao_oculta']}
                nv = self.bot.analisar_e_prever(tn, ma, fn)
                if nv is not None: self.previsao_ativa = nv; enviar_previsao_auto(nv)
    
    def zerar_estatisticas(self):
        self.acertos = 0; self.erros = 0; self.historico_desempenho = []
        self.rodadas_sem_entrada = 0; self.ultima_entrada_rodada = -10
        self.giros_restantes_espera = 0; self.repeticoes_acerto_consecutivas = 0
        self.ultima_entrada_green = False; self.ultima_entrada_numeros = []
        self.bot.zerar(); salvar_sessao()
    
    def get_status(self):
        return {'acertos': self.acertos, 'erros': self.erros, 'total': self.acertos+self.erros, 'rodadas_sem_entrada': self.rodadas_sem_entrada}


# =============================
# FUNÇÕES AUXILIARES
# =============================
def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    try:
        with open(caminho, "w") as f: json.dump(historico, f, indent=2)
    except: pass

def extrair_numeros_raio(resultado_api):
    nr, mp = [], {}
    try:
        if resultado_api and isinstance(resultado_api, dict):
            for item in resultado_api.get('data', {}).get('result', {}).get('luckyNumbersList', []):
                n = item.get('number')
                if n is not None: nr.append(n)
                m = item.get('roundedMultiplier')
                if m is not None: mp[n] = m
    except: pass
    return nr, mp

def fetch_latest_result():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=5)
        r.raise_for_status()
        d = r.json()
        gd = d.get("data", {}); rs = gd.get("result", {})
        ot = rs.get("outcome", {})
        n = ot.get("number"); ts = gd.get("startedAt", str(time.time()))
        nr, mp = extrair_numeros_raio(d)
        return {"number": n, "timestamp": ts, "luckyNumbers": nr, "luckyMultipliers": mp}
    except: return None

def exportar_historico(historico, formato='json'):
    if formato == 'json': return json.dumps(historico, indent=2, ensure_ascii=False)
    lh = ["numero,timestamp,multiplicador"]
    for item in historico:
        if isinstance(item, dict):
            n = item.get('number', ''); ts = item.get('timestamp', '')
            mt = item.get('luckyMultipliers', {}).get(n, '')
            lh.append(f"{n},{ts},{mt}")
        else: lh.append(f"{item},,")
    return "\n".join(lh)


# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎯 Bot IA 19 Motores", layout="centered")
st.title("🎯 Bot Unificado — 19 Motores + IA Adaptativa")

if "sistema" not in st.session_state or st.session_state.sistema is None:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    sis = st.session_state.sistema
    sis.acertos = dados.get('sistema_acertos', 0); sis.erros = dados.get('sistema_erros', 0)
    sis.historico_desempenho = dados.get('sistema_historico_desempenho', [])
    sis.estrategia_ativa_manual = dados.get('estrategia_ativa_manual', False)
    sis.giros_restantes_espera = dados.get('giros_restantes_espera', 0)
    sis.repeticoes_acerto_consecutivas = dados.get('repeticoes_acerto_consecutivas', 0)
    sis.ultima_entrada_numeros = dados.get('ultima_entrada_numeros', [])
    sis.ultima_entrada_forca = dados.get('ultima_entrada_forca', 0)
    sis.ultima_entrada_motor = dados.get('ultima_entrada_motor', '')
    sis.ultima_entrada_green = dados.get('ultima_entrada_green', False)
    for num in dados.get('historico_numeros', []): sis.bot.historico.append(num)
    for lucky in dados.get('historico_lucky', []): sis.bot.lucky.append(lucky)
    if os.path.exists(PERFORMANCE_PATH):
        try:
            with open(PERFORMANCE_PATH, 'r') as f:
                p = json.load(f)
                sis.bot.performance = {'acertos': p.get('acertos', 0), 'erros': p.get('erros', 0), 'historico': p.get('historico', [])}
        except: pass
    if os.path.exists(PERFORMANCE_MOTORES_PATH):
        try:
            with open(PERFORMANCE_MOTORES_PATH, 'r') as f:
                for m, d in json.load(f).items(): sis.bot.performance_motores[m] = d
        except: pass
    if not st.session_state.get('historico'): st.session_state.historico = dados.get('historico', [])

defaults = {
    'modo_automatico': True, 'top_n_apostas': 13, 'intervalo_minimo_entradas': 0, 'forca_minima_entrada': 30,
    'usar_sniper': True, 'usar_mineracao': True, 'usar_giro': True, 'usar_gap': True,
    'usar_sequencia': True, 'usar_quadrantes': True, 'usar_terminais': True,
    'usar_protecao_zero': True, 'usar_lightning_hunt': True, 'usar_salto_curto': True,
    'usar_cadeias_markov': True, 'usar_setores_franceses': True, 'usar_ritmo_repeticao': True,
    'usar_zero_vizinho': True, 'usar_ia_adaptativa': True, 'usar_cluster_hibrido': True,
    'usar_compressao': True, 'usar_anti_humano': True, 'usar_rotacao_oculta': True,
    'repetir_entrada': True, 'repetir_acerto': True, 'max_repeticoes_acerto': 3
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

if "historico" not in st.session_state:
    st.session_state.historico = []
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f: st.session_state.historico = json.load(f)
        except: pass

if "telegram_token" not in st.session_state: st.session_state.telegram_token = ""
if "telegram_chat_id" not in st.session_state: st.session_state.telegram_chat_id = ""

# =============================
# SIDEBAR
# =============================
st.sidebar.title("⚙️ Configurações")

with st.sidebar.expander("🎯 Entrada", expanded=True):
    st.session_state.top_n_apostas = st.slider("🔢 Quantidade", 12, 15, st.session_state.top_n_apostas, key="sl_top_n")
    st.session_state.forca_minima_entrada = st.slider("🚫 Força Mínima", 25, 55, st.session_state.forca_minima_entrada, 5, key="sl_forca_min")

with st.sidebar.expander("🤖 19 Motores", expanded=False):
    st.write("**Clássicos (14):**")
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.usar_sniper = st.checkbox("🎯 Sniper", value=st.session_state.usar_sniper, key="cb_sniper")
        st.session_state.usar_mineracao = st.checkbox("🔬 Mineração", value=st.session_state.usar_mineracao, key="cb_mineracao")
        st.session_state.usar_giro = st.checkbox("🔄 Giro", value=st.session_state.usar_giro, key="cb_giro")
        st.session_state.usar_gap = st.checkbox("🔁 Gap", value=st.session_state.usar_gap, key="cb_gap")
        st.session_state.usar_sequencia = st.checkbox("📊 Sequência", value=st.session_state.usar_sequencia, key="cb_sequencia")
        st.session_state.usar_quadrantes = st.checkbox("🟩 Quadrantes", value=st.session_state.usar_quadrantes, key="cb_quadrantes")
        st.session_state.usar_terminais = st.checkbox("🔢 Terminais", value=st.session_state.usar_terminais, key="cb_terminais")
        st.session_state.usar_protecao_zero = st.checkbox("🎱 Zero-Hunt", value=st.session_state.usar_protecao_zero, key="cb_protecao_zero")
    with c2:
        st.session_state.usar_lightning_hunt = st.checkbox("⚡ Lightning", value=st.session_state.usar_lightning_hunt, key="cb_lightning_hunt")
        st.session_state.usar_salto_curto = st.checkbox("🎯 Salto Curto", value=st.session_state.usar_salto_curto, key="cb_salto_curto")
        st.session_state.usar_cadeias_markov = st.checkbox("⛓️ Cadeias Markov", value=st.session_state.usar_cadeias_markov, key="cb_cadeias_markov")
        st.session_state.usar_setores_franceses = st.checkbox("🇫🇷 Setores Franceses", value=st.session_state.usar_setores_franceses, key="cb_setores_franceses")
        st.session_state.usar_ritmo_repeticao = st.checkbox("🎵 Ritmo Repetição", value=st.session_state.usar_ritmo_repeticao, key="cb_ritmo_repeticao")
        st.session_state.usar_zero_vizinho = st.checkbox("🎯 Zero Vizinho", value=st.session_state.usar_zero_vizinho, key="cb_zero_vizinho")
    
    st.write("**🆕 IA (5):**")
    c3, c4 = st.columns(2)
    with c3:
        st.session_state.usar_ia_adaptativa = st.checkbox("🧠 IA Adaptativa", value=st.session_state.usar_ia_adaptativa, key="cb_ia_adaptativa")
        st.session_state.usar_cluster_hibrido = st.checkbox("🔀 Cluster Híbrido", value=st.session_state.usar_cluster_hibrido, key="cb_cluster_hibrido")
        st.session_state.usar_compressao = st.checkbox("🗜️ Compressão", value=st.session_state.usar_compressao, key="cb_compressao")
    with c4:
        st.session_state.usar_anti_humano = st.checkbox("🚫 Anti-Humano", value=st.session_state.usar_anti_humano, key="cb_anti_humano")
        st.session_state.usar_rotacao_oculta = st.checkbox("🔄 Rotação Oculta", value=st.session_state.usar_rotacao_oculta, key="cb_rotacao_oculta")

with st.sidebar.expander("🟢 Green / ⏳ Erro", expanded=True):
    st.session_state.repetir_acerto = st.checkbox("🟢 Repetir após ACERTO", value=st.session_state.repetir_acerto, key="cb_repetir_acerto")
    st.session_state.max_repeticoes_acerto = st.slider("Máx. green", 1, 5, st.session_state.max_repeticoes_acerto, key="sl_max_green")
    st.session_state.repetir_entrada = st.checkbox("⏳ Repetir após erro", value=st.session_state.repetir_entrada, key="cb_repetir_entrada")

with st.sidebar.expander("🔔 Telegram", expanded=False):
    st.session_state.telegram_token = st.text_input("🤖 Token:", value=st.session_state.telegram_token, type="password", key="ti_telegram_token")
    st.session_state.telegram_chat_id = st.text_input("💬 Chat ID:", value=st.session_state.telegram_chat_id, key="ti_telegram_chat_id")
    if st.button("🧪 Testar", use_container_width=True, key="btn_testar_telegram"):
        s, m = testar_telegram()
        st.success(m) if s else st.error(m)

st.session_state.modo_automatico = st.sidebar.checkbox("🔄 Modo Automático", value=st.session_state.modo_automatico, key="cb_modo_auto")
if st.sidebar.button("Atualizar Modo", use_container_width=True, key="btn_atualizar_modo"):
    st.session_state.sistema.estrategia_ativa_manual = not st.session_state.modo_automatico
    st.rerun()

with st.sidebar.expander("💾 Geral", expanded=False):
    if st.button("💾 Salvar", use_container_width=True, key="btn_salvar_dados"):
        salvar_resultado_em_arquivo(st.session_state.historico); salvar_sessao(); st.success("✅")
    if st.button("🗑️ Zerar", use_container_width=True, key="btn_zerar_tudo"):
        if st.checkbox("⚠️ Confirmar", key="cb_confirmar_zerar"):
            st.session_state.sistema.zerar_estatisticas(); st.rerun()

# =============================
# CONTEÚDO PRINCIPAL
# =============================
st.subheader("✍️ Inserir Sorteios")
c1, c2 = st.columns([3, 1])
with c1:
    entrada = st.text_input("Números (0-36):", key="ti_entrada_numeros")
with c2:
    def adicionar_numeros():
        ns = st.session_state.get('ti_entrada_numeros', '')
        if ns:
            try:
                nums = [int(n) for n in ns.split() if n.isdigit() and 0 <= int(n) <= 36]
                for n in nums:
                    item = {"number": n, "timestamp": f"manual_{len(st.session_state.historico)}_{time.time()}", "luckyNumbers": [], "luckyMultipliers": {}}
                    st.session_state.historico.append(item)
                    st.session_state.sistema.processar_novo_numero(item)
                salvar_resultado_em_arquivo(st.session_state.historico)
                salvar_sessao()
                st.session_state.msg_sucesso = f"✅ {len(nums)} adicionados!"
            except Exception as e:
                st.session_state.msg_erro = f"Erro: {e}"
    
    st.button("➕ Adicionar", use_container_width=True, key="btn_adicionar", on_click=adicionar_numeros)

if st.session_state.get('msg_sucesso'):
    st.success(st.session_state.msg_sucesso); st.session_state.msg_sucesso = None
if st.session_state.get('msg_erro'):
    st.error(st.session_state.msg_erro); st.session_state.msg_erro = None

st_autorefresh(interval=5000, key="autorefresh_main")

resultado = fetch_latest_result()
if resultado and resultado.get("timestamp"):
    if not st.session_state.historico or resultado.get("timestamp") != st.session_state.historico[-1].get("timestamp"):
        n = resultado.get("number")
        if n is not None:
            st.session_state.historico.append(resultado)
            st.session_state.sistema.processar_novo_numero(resultado)
            salvar_resultado_em_arquivo(st.session_state.historico)
            salvar_sessao()

st.subheader("🔁 Últimos Números")
if st.session_state.historico:
    ultimos = st.session_state.historico[-10:]; fmt = []
    for item in ultimos:
        n = item['number'] if isinstance(item, dict) else item
        if isinstance(item, dict) and n in item.get('luckyNumbers', []):
            mt = item.get('luckyMultipliers', {}).get(n, '')
            fmt.append(f"⚡**{n}**({mt}x)" if mt else f"⚡**{n}**")
        else: fmt.append(str(n))
    st.write(" ".join(fmt))

status = st.session_state.sistema.get_status()
c1, c2, c3, c4 = st.columns(4)
c1.metric("🟢 Acertos", status['acertos']); c2.metric("🔴 Erros", status['erros'])
c3.metric("📊 Total", status['total']); c4.metric("⏳ Sem Entrada", status['rodadas_sem_entrada'])

if status['total'] > 0:
    tx = status['acertos']/status['total']*100
    if tx >= 30: st.success(f"🎯 Taxa: {tx:.1f}%")
    elif tx >= 20: st.warning(f"🎯 Taxa: {tx:.1f}%")
    else: st.error(f"🎯 Taxa: {tx:.1f}%")

sis = st.session_state.sistema
if sis.repeticoes_acerto_consecutivas > 0 and not sis.previsao_ativa:
    st.success(f"🟢 Green: {sis.repeticoes_acerto_consecutivas}/{st.session_state.max_repeticoes_acerto}")
elif sis.giros_restantes_espera > 0:
    st.warning(f"⏳ Aguardando {sis.giros_restantes_espera} giro(s)")

st.subheader("🎯 Previsão Ativa")
if sis.estrategia_ativa_manual:
    st.warning("⚠️ MODO MANUAL")
elif sis.previsao_ativa:
    p = sis.previsao_ativa; f = p.get('forca_real', 0); motor = p.get('motor', '')
    qtd = p.get('qtd_motores', 1); green = p.get('green', False); rep = p.get('repeticao', False)
    
    if green: st.success(f"🟢 GREEN #{p.get('green_count', 0)}!")
    elif rep: st.success("⏳ REPETINDO!")
    elif f >= 65: st.success(f"🔥 FORÇA {f}% ({qtd} motores)")
    elif f >= 50: st.warning(f"🎯 FORÇA {f}% ({qtd} motores)")
    else: st.info(f"📊 FORÇA {f}% ({qtd} motores)")
    
    if not rep and not green: st.caption(f"🤖 Motor: {motor}")
    st.write(f"🔢 {len(p['numeros_apostar'])} números:")
    st.markdown(f"### {', '.join(map(str, sorted(p['numeros_apostar'])))}")
else:
    st.info("🎲 Aguardando...")

st.subheader("🏆 Performance Individual")
ranking = sis.bot.get_melhores_motores(10)
if ranking:
    cols = st.columns(5)
    for i, (nome, tx, ac_m, tot_m, _) in enumerate(ranking):
        with cols[i % 5]:
            em = "🟢" if tx >= 0.30 else "🟡" if tx >= 0.20 else "🔴" if tot_m >= 2 else "⚪"
            st.metric(f"{em} {nome}", f"{tx:.0%}", f"{ac_m}/{tot_m}")

st.subheader("📈 Performance Geral")
tx_bot = sis.bot.get_taxa_acerto(); tot_bot = sis.bot.get_total_tentativas()
if tot_bot > 0:
    em = "🟢" if tx_bot >= 0.30 else "🟡" if tx_bot >= 0.20 else "🔴"
    st.write(f"{em} Bot: {tx_bot:.0%} ({sis.bot.performance['acertos']}/{tot_bot})")

if sis.historico_desempenho:
    st.write("🔍 Últimas:")
    for r in sis.historico_desempenho[-5:]:
        e = "🎉" if r['acerto'] else "❌"; g = " 🟢" if r.get('green') else ""
        m = f" ⚡{r['multiplicador']}x" if r.get('multiplicador') and r['acerto'] else ""
        st.write(f"{e}{g} ({r.get('forca',0)}%) [{r.get('motor','')}]: {r['numero']}{m}")

st.subheader("📥 Download")
st.metric("📊 Registros", len(st.session_state.historico))
col_d1, col_d2 = st.columns(2)
with col_d1:
    st.download_button("📥 Baixar JSON", exportar_historico(st.session_state.historico, 'json'),
                       f"historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "application/json", key="btn_dl_json")
with col_d2:
    st.download_button("📥 Baixar CSV", exportar_historico(st.session_state.historico, 'csv'),
                       f"historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv", key="btn_dl_csv")

salvar_sessao()
