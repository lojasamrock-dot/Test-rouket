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

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_roleta.json"
PERFORMANCE_PATH = "performance_bot.json"
ENTRADAS_PATH = "historico_entradas.json"
ML_MODEL_PATH = "modelo_xgboost.pkl"

def salvar_sessao():
    try:
        if 'sistema' not in st.session_state or st.session_state.sistema is None:
            return False
        sis = st.session_state.sistema
        
        performance_data = {
            'acertos': sis.acertos,
            'erros': sis.erros,
            'historico': sis.bot.performance['historico']
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
            'modo_ml': st.session_state.get('modo_ml', False),
            'acertos_duzia': st.session_state.get('acertos_duzia', 0),
            'erros_duzia': st.session_state.get('erros_duzia', 0),
            'modo_agressivo': st.session_state.get('modo_agressivo', False),
            'giros_minimos_ml': st.session_state.get('giros_minimos_ml', 10),
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
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH, ENTRADAS_PATH, ML_MODEL_PATH]:
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
            enviar_telegram(f"🔔 {motor} | F{forca}%\n{gatilho}\n🔢 " + " ".join(map(str, numeros)))
        
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

def get_coluna_real(n):
    if n == 0: return 0
    if n in set(range(1, 37, 3)): return 1
    if n in set(range(2, 37, 3)): return 2
    if n in set(range(3, 37, 3)): return 3
    return 0

# =============================
# ROLETA BASE
# =============================
class RoletaBase:
    def __init__(self):
        self.race = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        self.vermelhos = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        self.pretos = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
        self.duzia1 = set(range(1, 13))
        self.duzia2 = set(range(13, 25))
        self.duzia3 = set(range(25, 37))
        self.coluna1 = set(range(1, 37, 3))
        self.coluna2 = set(range(2, 37, 3))
        self.coluna3 = set(range(3, 37, 3))
        self.numeros_problematicos = {0, 32, 33, 34, 35}
        self.max_problematicos = 2
    
    def get_vizinhos(self, n, r=2):
        if n not in self.race: return []
        i = self.race.index(n)
        return [self.race[(i + j) % 37] for j in range(-r, r + 1)]
    
    def get_coluna(self, n):
        if n in self.coluna1: return 1
        elif n in self.coluna2: return 2
        elif n in self.coluna3: return 3
        return 0
    
    def get_duzia(self, n):
        if n in self.duzia1: return 1
        elif n in self.duzia2: return 2
        elif n in self.duzia3: return 3
        return 0
    
    def get_numeros_coluna(self, coluna):
        if coluna == 1: return self.coluna1
        elif coluna == 2: return self.coluna2
        elif coluna == 3: return self.coluna3
        return set()
    
    def get_numeros_duzia(self, duzia):
        if duzia == 1: return self.duzia1
        elif duzia == 2: return self.duzia2
        elif duzia == 3: return self.duzia3
        return set()

# =============================
# ESTRATÉGIAS ORIGINAIS (28)
# =============================
class EstrategiaSniperElite:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if len(h) < 6: return None
        termos = [n%10 for n in h[-8:]]
        contagem = Counter(termos)
        td, freq = contagem.most_common(1)[0]
        if freq < 3: return None
        aposta = set()
        aposta.update(self.roleta.get_vizinhos(h[-1], 1)[:2])
        for n in range(37):
            if n%10 == td: aposta.add(n)
            if len(aposta) >= 7: break
        return {'base': set(list(aposta)[:7]), 'forca': 50+freq*5, 'estrategias': [f'Terminal {td}'], 'gatilho': f'Terminal {td} ({freq}x)'}

class EstrategiaRepeticao:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        u, p = h[-1], h[-2]
        if u != p: return None
        b = set([u]); b.update(self.roleta.get_vizinhos(u, 1)[:3])
        return {'base': b, 'forca': 80, 'estrategias': [f'Repetição {u}'], 'gatilho': f'Repetição {u}'}

class EstrategiaGapCurto:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 3: return None
        u = h[-1]; b = set(); gap = None
        if len(h) >= 3 and h[-3] == u: b.add(u); b.add(h[-2]); gap = 2
        if len(h) >= 4 and h[-4] == u: b.update([u, h[-2], h[-3]]); gap = gap or 3
        if len(h) >= 5 and h[-5] == u: b.add(u); gap = gap or 4
        if not b: return None
        for n in list(b)[:2]: b.update(self.roleta.get_vizinhos(n, 1)[:1])
        return {'base': b, 'forca': 55+(gap or 0)*5, 'estrategias': [f'Gap {gap}'], 'gatilho': f'Gap {gap} giros: {u}'}

class EstrategiaMineracao:
    def analisar(self, h):
        if len(h) < 5: return None
        u = h[-1]; t = defaultdict(list)
        for i in range(len(h)-1): t[h[i]].append(h[i+1])
        seg = t.get(u, [])
        if len(seg) < 2: return None
        top = [(n, c) for n, c in Counter(seg).most_common(2) if c/len(seg) >= 0.15]
        if not top: return None
        return {'base': set([n for n, _ in top]), 'forca': 50, 'estrategias': [f'Markov {u}→{top[0][0]}'], 'gatilho': f'Após {u} → {top[0][0]}'}

class EstrategiaDuziaDominante:
    def analisar(self, h):
        if len(h) < 10: return None
        dz = {1: set(range(1,13)), 2: set(range(13,25)), 3: set(range(25,37))}
        cnt = Counter((n-1)//12+1 for n in h[-10:] if n != 0)
        if not cnt: return None
        d, freq = cnt.most_common(1)[0]
        if freq < 6: return None
        b = set()
        b.update(list(dz[d] - set(h[-5:]))[:3])
        b.update(list(dz[d].intersection(set(h[-5:])))[:2])
        return {'base': b, 'forca': 50+(freq-6)*5, 'estrategias': [f'Dúzia {d}'], 'gatilho': f'Dúzia {d} ({freq}/10)'}

class EstrategiaEspelho:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        u = h[-1]
        espelhos = {0:0, 12:21, 21:12, 13:31, 31:13, 23:32, 32:23, 1:10, 10:1, 2:20, 20:2, 3:30, 30:3, 4:19, 19:4, 5:24, 24:5, 6:27, 27:6, 7:28, 28:7, 8:23, 23:8, 9:22, 22:9, 11:36, 36:11, 14:31, 31:14, 15:32, 32:15, 16:33, 33:16, 17:34, 34:17, 18:29, 29:18, 25:26, 26:25}
        if u not in espelhos: return None
        esp = espelhos[u]
        b = set([esp, u]); b.update(self.roleta.get_vizinhos(esp, 1)[:2])
        return {'base': b, 'forca': 50, 'estrategias': [f'Espelho {u}↔{esp}'], 'gatilho': f'Espelho {u}↔{esp}'}

class EstrategiaSomaCinco:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        count = sum(1 for i in range(len(h)-1) if h[i]+5 == h[i+1] or (h[i]+5 > 36 and h[i]+5-37 == h[i+1]))
        if count < 2: return None
        u = h[-1]; b = set()
        for d in [5, 10]:
            prox = u + d
            if prox > 36: prox -= 37
            b.add(prox)
        b.add(u); b.update(self.roleta.get_vizinhos(u, 1)[:2])
        return {'base': b, 'forca': 45+count*5, 'estrategias': [f'+5'], 'gatilho': f'Padrão +5 ({count}x)'}

class EstrategiaCicloOito:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 7: return None
        u = h[-1]
        if len(h) >= 9 and h[-9] == u:
            b = set([u]); b.update(self.roleta.get_vizinhos(u, 1)[:3])
            return {'base': b, 'forca': 55, 'estrategias': ['Ciclo 8'], 'gatilho': f'Ciclo 8 giros: {u}'}
        if len(h) >= 7 and h[-7] == u:
            b = set([u]); b.update(self.roleta.get_vizinhos(u, 1)[:2])
            return {'base': b, 'forca': 45, 'estrategias': ['Ciclo 6'], 'gatilho': f'Ciclo 6 giros: {u}'}
        return None

class EstrategiaAlternanciaCor:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 6: return None
        cores = ['V' if n in self.roleta.vermelhos else 'P' if n in self.roleta.pretos else 'Z' for n in h[-10:]]
        alt = 0
        for i in range(1, len(cores)):
            if cores[i] != cores[i-1] and cores[i] != 'Z' and cores[i-1] != 'Z': alt += 1
            else: alt = 0
        if alt < 5: return None
        prox = 'P' if cores[-1] == 'V' else 'V'
        alvo = self.roleta.pretos if prox == 'P' else self.roleta.vermelhos
        b = alvo.intersection(set(h[-10:]))
        if len(b) < 4: b = set(list(alvo)[:6])
        return {'base': b, 'forca': 45+alt*2, 'estrategias': [f'Alternância →{prox}'], 'gatilho': f'Alternância {alt}x → {prox}'}

class EstrategiaSetorCilindro:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 5: return None
        voisins = {22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25}
        tiers = {27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33}
        orphelins = {1, 20, 14, 31, 9, 17, 34, 6}
        setores = []
        for n in h[-5:]:
            if n in voisins: setores.append("Voisins")
            elif n in tiers: setores.append("Tiers")
            elif n in orphelins: setores.append("Orphelins")
            else: setores.append("Zero")
        contagem = Counter(setores)
        setor_dom, freq = contagem.most_common(1)[0]
        if freq < 3 or setor_dom == "Zero": return None
        sn = {'Voisins': voisins, 'Tiers': tiers, 'Orphelins': orphelins}
        b = set()
        b.update(list(sn[setor_dom] - set(h[-5:]))[:4])
        b.update(list(sn[setor_dom].intersection(set(h[-5:])))[:2])
        return {'base': b, 'forca': 45+freq*5, 'estrategias': [f'Setor {setor_dom}'], 'gatilho': f'Setor {setor_dom} ({freq}/5)'}

class EstrategiaZeroVirada:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        if h[-1] == 0 or h[-2] == 0:
            b = set(list(self.roleta.duzia1)[:6] + list(self.roleta.duzia2)[:6])
            b.update(self.roleta.get_vizinhos(0, 2)[:2])
            return {'base': b, 'forca': 50, 'estrategias': ['Pós-Zero'], 'gatilho': 'Após Zero'}
        return None

class EstrategiaPrimos:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 6: return None
        primos = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}
        pr = [n for n in h[-6:] if n in primos]
        if len(pr) < 4: return None
        b = set(list(primos - set(h[-6:]))[:3])
        b.update(pr[-2:]); b.update(self.roleta.get_vizinhos(h[-1], 1)[:1])
        return {'base': b, 'forca': 45+len(pr)*3, 'estrategias': ['Primos'], 'gatilho': f'Primos ({len(pr)}/6)'}

class EstrategiaVizinhosFisicos:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        u, p = h[-1], h[-2]
        if u not in self.roleta.race or p not in self.roleta.race: return None
        ia, ib = self.roleta.race.index(u), self.roleta.race.index(p)
        diff = abs(ia - ib)
        if not (diff <= 1 or diff >= 36): return None
        b = set([u, p]); b.update(self.roleta.get_vizinhos(u, 1)[:2])
        return {'base': b, 'forca': 55, 'estrategias': ['Vizinhos Físicos'], 'gatilho': f'Vizinhos {p}↔{u}'}

class EstrategiaFaixaNumerica:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 5: return None
        faixas = ['B' if 1 <= n <= 18 else 'A' if 19 <= n <= 36 else 'Z' for n in h[-6:]]
        contagem = Counter([f for f in faixas if f != 'Z'])
        if not contagem: return None
        fd, freq = contagem.most_common(1)[0]
        if freq < 4: return None
        fo = self.roleta.duzia3 if fd == 'B' else self.roleta.duzia1
        b = fo.intersection(set(h[-10:]))
        if len(b) < 4: b = set(list(fo)[:5])
        return {'base': b, 'forca': 45+freq*3, 'estrategias': ['Faixa Oposta'], 'gatilho': f'Faixa {fd}→oposta'}

class EstrategiaNumeroDoDia:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 20: return None
        ft = Counter(h[-50:])
        nq = [n for n, c in ft.most_common(3) if c >= 5]
        if not nq: return None
        b = set(nq)
        for n in nq[:2]: b.update(self.roleta.get_vizinhos(n, 1)[:1])
        return {'base': b, 'forca': 50+ft[nq[0]], 'estrategias': ['Nº do Dia'], 'gatilho': f'Nº do dia: {nq[:2]}'}

class EstrategiaConfirmacaoLucky:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if len(h) < 3 or not lucky_hist: return None
        recent_lucky = []
        for i in range(max(0, len(lucky_hist)-5), len(lucky_hist)): recent_lucky.extend(lucky_hist[i])
        if not recent_lucky: return None
        lucky_freq = Counter(recent_lucky)
        nao_saiu = [n for n in lucky_freq if n not in h[-3:]]
        if not nao_saiu: return None
        top_lucky = sorted(nao_saiu, key=lambda x: lucky_freq[x], reverse=True)[:3]
        b = set(top_lucky)
        for n in top_lucky[:2]: b.update(self.roleta.get_vizinhos(n, 1)[:2])
        return {'base': set(list(b)[:7]), 'forca': 55, 'estrategias': ['Confirmação Lucky'], 'gatilho': f'Lucky pendente: {top_lucky[:2]}'}

class EstrategiaPendulo:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 8: return None
        ultimos = h[-8:]
        altos = sum(1 for n in ultimos if n >= 19)
        baixos = len(ultimos) - altos
        if altos >= 6: alvo = set(range(1, 19)); tendencia = "Baixos"
        elif baixos >= 6: alvo = set(range(19, 37)); tendencia = "Altos"
        else: return None
        b = alvo.intersection(set(h[-15:])) if len(h) >= 15 else alvo
        b.update(self.roleta.get_vizinhos(h[-1], 1)[:3])
        return {'base': set(list(b)[:8]), 'forca': 50, 'estrategias': [f'Pêndulo →{tendencia}'], 'gatilho': f'Pêndulo {altos}A/{baixos}B → {tendencia}'}

class EstrategiaQuenteFrio:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if len(h) < 15: return None
        recentes = set(h[-15:]); todos = set(range(37))
        frios = list(todos - recentes - {0})
        if not frios: return None
        b = set()
        frios_restantes = [n for n in frios if n not in b]
        random.shuffle(frios_restantes); b.update(frios_restantes[:7])
        return {'base': set(list(b)[:7]), 'forca': 45, 'estrategias': ['Quente/Frio'], 'gatilho': f'Frios ({len(frios)})'}

class EstrategiaColunasAlternadas:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 6: return None
        colunas = [self.roleta.get_coluna(n) for n in h[-6:] if n != 0]
        if len(colunas) < 4: return None
        padrao = []
        for i in range(1, len(colunas)):
            if colunas[i] != colunas[i-1]: padrao.append(colunas[i])
        if len(padrao) < 3: return None
        ultima_col = colunas[-1]
        colunas_alvo = [1, 2, 3]; colunas_alvo.remove(ultima_col)
        coluna_provavel = colunas_alvo[0]
        col_map = {1: self.roleta.coluna1, 2: self.roleta.coluna2, 3: self.roleta.coluna3}
        alvo_numeros = col_map[coluna_provavel]
        b = alvo_numeros.intersection(set(h[-10:]))
        if len(b) < 3: b = set(list(alvo_numeros)[:5])
        return {'base': b, 'forca': 45, 'estrategias': ['Colunas Alternadas'], 'gatilho': f'Coluna {ultima_col}→{coluna_provavel}'}

class EstrategiaLuckySetor:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if len(h) < 3 or not lucky_hist: return None
        setores_lucky = defaultdict(int)
        for i in range(max(0, len(lucky_hist)-8), len(lucky_hist)):
            for n in lucky_hist[i]:
                if n in self.roleta.duzia1: setores_lucky[1] += 1
                elif n in self.roleta.duzia2: setores_lucky[2] += 1
                elif n in self.roleta.duzia3: setores_lucky[3] += 1
        if not setores_lucky: return None
        setor_dom = max(setores_lucky, key=setores_lucky.get)
        sn = {1: self.roleta.duzia1, 2: self.roleta.duzia2, 3: self.roleta.duzia3}
        numeros_setor = sn.get(setor_dom, set())
        b = set(list(numeros_setor)[:7])
        return {'base': b, 'forca': 50, 'estrategias': [f'Lucky Setor D{setor_dom}'], 'gatilho': f'Lucky Setor D{setor_dom}'}

class EstrategiaLuckyCascata:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if len(h) < 6 or not lucky_hist: return None
        persistentes = []
        for n in range(37):
            count = 0
            for ls in lucky_hist[-5:]:
                if n in ls: count += 1
                else: count = 0
                if count >= 3: persistentes.append(n); break
        if not persistentes: return None
        b = set(persistentes[:7])
        return {'base': b, 'forca': 55, 'estrategias': ['Lucky Cascata'], 'gatilho': f'Cascata: {persistentes[:3]}'}

class EstrategiaEspelhoTemporal:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if len(h) < 12 or not lucky_hist: return None
        resultados_antigos = h[-12:-8] if len(h) >= 12 else h[:-8]
        lucky_recentes = []
        for i in range(max(0, len(lucky_hist)-3), len(lucky_hist)): lucky_recentes.extend(lucky_hist[i])
        intersecao = set(resultados_antigos).intersection(set(lucky_recentes))
        if len(intersecao) < 2: return None
        b = set(list(intersecao)[:7])
        return {'base': b, 'forca': 50, 'estrategias': ['Espelho Temporal'], 'gatilho': f'Temp: {list(intersecao)[:3]}'}

class EstrategiaMicroCiclo3:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 6: return None
        if len(h) >= 6 and h[-3] == h[-6]:
            b = set([h[-3]]); b.update(self.roleta.get_vizinhos(h[-3], 1)[:2])
            return {'base': b, 'forca': 65, 'estrategias': ['Micro Ciclo 3'], 'gatilho': f'Ciclo 3g: {h[-3]} repete'}
        return None

class EstrategiaLuckyImediato:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if len(h) < 1 or not lucky_hist: return None
        ultimo_lucky = lucky_hist[-1] if lucky_hist else []
        if len(ultimo_lucky) < 2: return None
        b = set(ultimo_lucky[:7])
        return {'base': b, 'forca': 65, 'estrategias': ['Lucky Imediato'], 'gatilho': f'Lucky atual: {ultimo_lucky[:3]}'}

class EstrategiaLuckyRecenteNaoSaiu:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if len(h) < 3 or not lucky_hist: return None
        lucky_recentes = []
        for i in range(max(0, len(lucky_hist)-3), len(lucky_hist)): lucky_recentes.extend(lucky_hist[i])
        if not lucky_recentes: return None
        lucky_set = set(lucky_recentes); resultados_recentes = set(h[-5:])
        nao_sairam = lucky_set - resultados_recentes
        if len(nao_sairam) < 2: return None
        return {'base': set(list(nao_sairam)[:7]), 'forca': 60, 'estrategias': ['Lucky Recente'], 'gatilho': f'Lucky ñ saiu: {list(nao_sairam)[:2]}'}

class EstrategiaEspelhoLucky:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if len(h) < 2 or not lucky_hist: return None
        espelhos = {0:0, 12:21, 21:12, 13:31, 31:13, 23:32, 32:23, 1:10, 10:1, 2:20, 20:2, 3:30, 30:3, 4:19, 19:4, 5:24, 24:5, 6:27, 27:6, 7:28, 28:7, 8:23, 23:8, 9:22, 22:9, 11:36, 36:11, 14:31, 31:14, 15:32, 32:15, 16:33, 33:16, 17:34, 34:17, 18:29, 29:18, 25:26, 26:25}
        lucky_recentes = []
        for i in range(max(0, len(lucky_hist)-2), len(lucky_hist)): lucky_recentes.extend(lucky_hist[i])
        b = set()
        for n in lucky_recentes:
            if n in espelhos: b.add(espelhos[n])
        if len(b) < 2: return None
        return {'base': set(list(b)[:7]), 'forca': 55, 'estrategias': ['Espelho Lucky'], 'gatilho': f'Espelho Lucky'}

class EstrategiaOrfaosSetor:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 6: return None
        voisins = {22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25}
        tiers = {27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33}
        orphelins = {1, 20, 14, 31, 9, 17, 34}
        setores = []
        for n in h[-6:]:
            if n in voisins: setores.append("V")
            elif n in tiers: setores.append("T")
            elif n in orphelins: setores.append("O")
        contagem = Counter(setores)
        if len(contagem) >= 2: return None
        b = set(list(orphelins)[:7])
        return {'base': b, 'forca': 50, 'estrategias': ['Órfãos Setor'], 'gatilho': 'Setor órfão'}

class EstrategiaZeroCiclo:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 15: return None
        giros_sem_zero = 0
        for n in reversed(h):
            if n == 0: break
            giros_sem_zero += 1
        if giros_sem_zero < 20: return None
        b = set([0]); b.update(self.roleta.get_vizinhos(0, 2)[:6])
        return {'base': set(list(b)[:7]), 'forca': 50, 'estrategias': ['Zero Ciclo'], 'gatilho': f'Zero ausente {giros_sem_zero}g'}

# =============================
# ANALISADOR DE DÚZIAS
# =============================
class AnalisadorDuzias:
    def __init__(self, window=20):
        self.historico_duzias = deque(maxlen=window)
        self.historico_numeros = deque(maxlen=200)
    
    def adicionar(self, numero):
        d = get_duzia(numero)
        self.historico_duzias.append(d)
        self.historico_numeros.append(numero)
    
    def analisar(self):
        if len(self.historico_duzias) < 3:
            return None
        
        score = {1: 0, 2: 0, 3: 0}
        
        freq = Counter(self.historico_duzias)
        total = len(self.historico_duzias)
        for d in [1, 2, 3]:
            score[d] += (freq.get(d, 0) / total) * 40
        
        ultima = self.historico_duzias[-1]
        streak = 0
        for d in reversed(self.historico_duzias):
            if d == ultima: streak += 1
            else: break
        
        if streak >= 2 and ultima != 0:
            score[ultima] += streak * 8
        elif streak == 1 and ultima != 0:
            score[ultima] += 3
        
        u = list(self.historico_duzias)
        if len(u) >= 3 and u[-1] == u[-3] and u[-1] != u[-2] and u[-1] != 0:
            score[u[-1]] += 10
        if len(u) >= 4 and u[-1] == u[-3] and u[-2] == u[-4] and u[-1] != u[-2] and u[-1] != 0:
            score[u[-2]] += 12
        
        for d in [1, 2, 3]:
            ausencia = 0
            for dz in reversed(self.historico_duzias):
                if dz == d: break
                ausencia += 1
            if ausencia >= 6:
                score[d] += min(8, ausencia)
        
        ranking = sorted(score.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'duzia_principal': ranking[0][0],
            'duzia_secundaria': ranking[1][0],
            'score': {1: round(score[1], 1), 2: round(score[2], 1), 3: round(score[3], 1)},
            'confianca': round(ranking[0][1] - ranking[1][1], 1)
        }

# =============================
# ML PREDICTOR (CORRIGIDO)
# =============================
class MLPredictor:
    def __init__(self):
        self.model = None
        self.ready = False
        self.training_samples = 0
    
    def treinar(self, historico_duzias, historico_numeros):
        if len(historico_duzias) < 10:
            return False
        try:
            from xgboost import XGBClassifier
            
            X, y = [], []
            for i in range(5, len(historico_duzias)):
                janela = list(historico_duzias)[i-5:i]
                if len(janela) < 5: continue
                
                features = []
                freq = Counter(janela)
                for d in [1, 2, 3]:
                    features.append(freq.get(d, 0) / 5)
                
                ultima = janela[-1]
                streak = 0
                for d in reversed(janela):
                    if d == ultima: streak += 1
                    else: break
                features.append(streak)
                features.append(ultima)
                
                target = historico_duzias[i]
                if target != 0:
                    X.append(features)
                    y.append(target - 1)
            
            if len(X) < 5:
                return False
            
            self.model = XGBClassifier(
                n_estimators=50,
                max_depth=3,
                learning_rate=0.1,
                objective='multi:softprob',
                num_class=3,
                use_label_encoder=False,
                eval_metric='mlogloss',
                verbosity=0,
                random_state=42
            )
            self.model.fit(np.array(X), np.array(y))
            self.training_samples = len(X)
            self.ready = True
            
            with open(ML_MODEL_PATH, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'samples': self.training_samples
                }, f)
            
            return True
            
        except ImportError:
            return False
        except Exception:
            return False
    
    def carregar(self):
        try:
            if os.path.exists(ML_MODEL_PATH):
                with open(ML_MODEL_PATH, 'rb') as f:
                    data = pickle.load(f)
                    self.model = data.get('model')
                    self.training_samples = data.get('samples', 0)
                    self.ready = (self.model is not None) and (self.training_samples > 0)
                    if not self.ready and self.model is not None:
                        st.warning("⚠️ Modelo ML carregado mas inválido (0 amostras). Será retreinado.")
                return self.ready
        except Exception as e:
            st.error(f"Erro ao carregar ML: {e}")
        return False
    
    def prever(self, historico_duzias):
        if not self.ready or len(historico_duzias) < 5:
            return None
        try:
            janela = list(historico_duzias)[-5:]
            features = []
            freq = Counter(janela)
            for d in [1, 2, 3]: features.append(freq.get(d, 0) / 5)
            ultima = janela[-1]
            streak = 0
            for d in reversed(janela):
                if d == ultima: streak += 1
                else: break
            features.append(streak)
            features.append(ultima)
            X = np.array([features])
            probs = self.model.predict_proba(X)[0]
            ranking = np.argsort(probs)[::-1]
            return {
                'duzia_principal': int(ranking[0]) + 1,
                'duzia_secundaria': int(ranking[1]) + 1,
                'confianca': round(float(probs[ranking[0]] - probs[ranking[1]]), 2),
                'probabilidades': {1: round(float(probs[0]) * 100, 1), 2: round(float(probs[1]) * 100, 1), 3: round(float(probs[2]) * 100, 1)}
            }
        except Exception:
            return None

# =============================
# BOT UNIFICADO
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        self.sniper_elite = EstrategiaSniperElite(self.roleta)
        self.repeticao = EstrategiaRepeticao(self.roleta)
        self.gap_curto = EstrategiaGapCurto(self.roleta)
        self.mineracao = EstrategiaMineracao()
        self.duzia_dom = EstrategiaDuziaDominante()
        self.espelho = EstrategiaEspelho(self.roleta)
        self.soma_cinco = EstrategiaSomaCinco(self.roleta)
        self.ciclo_oito = EstrategiaCicloOito(self.roleta)
        self.alternancia_cor = EstrategiaAlternanciaCor(self.roleta)
        self.setor_cilindro = EstrategiaSetorCilindro(self.roleta)
        self.zero_virada = EstrategiaZeroVirada(self.roleta)
        self.primos = EstrategiaPrimos(self.roleta)
        self.vizinhos_fisicos = EstrategiaVizinhosFisicos(self.roleta)
        self.faixa_numerica = EstrategiaFaixaNumerica(self.roleta)
        self.numero_do_dia = EstrategiaNumeroDoDia(self.roleta)
        self.confirmacao_lucky = EstrategiaConfirmacaoLucky(self.roleta)
        self.pendulo = EstrategiaPendulo(self.roleta)
        self.quente_frio = EstrategiaQuenteFrio(self.roleta)
        self.colunas_alternadas = EstrategiaColunasAlternadas(self.roleta)
        self.lucky_setor = EstrategiaLuckySetor(self.roleta)
        self.lucky_cascata = EstrategiaLuckyCascata(self.roleta)
        self.espelho_temporal = EstrategiaEspelhoTemporal(self.roleta)
        self.micro_ciclo3 = EstrategiaMicroCiclo3(self.roleta)
        self.lucky_imediato = EstrategiaLuckyImediato(self.roleta)
        self.lucky_recente_nao_saiu = EstrategiaLuckyRecenteNaoSaiu(self.roleta)
        self.espelho_lucky = EstrategiaEspelhoLucky(self.roleta)
        self.orfaos_setor = EstrategiaOrfaosSetor(self.roleta)
        self.zero_ciclo = EstrategiaZeroCiclo(self.roleta)
        self.historico = []
        self.lucky = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
    
    def atualizar(self, n, lucky_nums=None):
        self.historico.append(int(n))
        self.lucky.append(lucky_nums if lucky_nums else [])
        if len(self.historico) > 200: self.historico = self.historico[-200:]
        if len(self.lucky) > 200: self.lucky = self.lucky[-200:]
    
    def gerar_entrada(self):
        resultados = []
        ests = [
            (self.lucky_imediato, 'Lucky Imediato', 4, [list(self.historico), self.lucky]),
            (self.repeticao, 'Repetição', 4, [list(self.historico)]),
            (self.lucky_recente_nao_saiu, 'Lucky Recente', 3, [list(self.historico), self.lucky]),
            (self.vizinhos_fisicos, 'Vizinhos Físicos', 3, [list(self.historico)]),
            (self.confirmacao_lucky, 'Confirm. Lucky', 3, [list(self.historico), self.lucky]),
            (self.lucky_cascata, 'Lucky Cascata', 3, [list(self.historico), self.lucky]),
            (self.sniper_elite, 'Sniper Elite', 2, [list(self.historico), self.lucky]),
            (self.gap_curto, 'Gap Curto', 2, [list(self.historico)]),
            (self.espelho, 'Espelho', 2, [list(self.historico)]),
            (self.numero_do_dia, 'Nº do Dia', 2, [list(self.historico)]),
            (self.pendulo, 'Pêndulo', 2, [list(self.historico)]),
            (self.zero_ciclo, 'Zero Ciclo', 1, [list(self.historico)]),
            (self.mineracao, 'Mineração', 1, [list(self.historico)]),
            (self.duzia_dom, 'Dúzia Dom.', 1, [list(self.historico)]),
            (self.soma_cinco, 'Soma Cinco', 1, [list(self.historico)]),
            (self.ciclo_oito, 'Ciclo Oito', 1, [list(self.historico)]),
            (self.alternancia_cor, 'Alternância', 1, [list(self.historico)]),
            (self.setor_cilindro, 'Setor Cilindro', 1, [list(self.historico)]),
            (self.zero_virada, 'Zero Virada', 1, [list(self.historico)]),
            (self.primos, 'Primos', 1, [list(self.historico)]),
            (self.faixa_numerica, 'Faixa Numérica', 1, [list(self.historico)]),
            (self.quente_frio, 'Quente/Frio', 1, [list(self.historico), self.lucky]),
            (self.colunas_alternadas, 'Colunas Alt.', 1, [list(self.historico)]),
            (self.espelho_temporal, 'Espelho Temp.', 1, [list(self.historico), self.lucky]),
            (self.micro_ciclo3, 'Micro Ciclo 3', 1, [list(self.historico)]),
        ]
        
        for est, nome, peso, args in ests:
            try:
                r = est.analisar(*args)
                if r and len(r.get('base', set())) >= 1 and r['forca'] >= 50:
                    resultados.append((nome, r, peso))
            except: pass
        
        if not resultados: return None
        
        base = set()
        for _, r, peso in resultados:
            for _ in range(peso): base.update(r['base'])
        
        lst = [n for n, _ in Counter(base).most_common(7)]
        fm = sum(r['forca'] * p for _, r, p in resultados) / max(1, sum(p for _, _, p in resultados))
        
        return {
            'numeros_apostar': sorted(lst),
            'forca_real': min(95, max(30, int(fm))),
            'motor': resultados[0][0],
            'gatilho': ' | '.join(r.get('gatilho', '') for _, r, _ in resultados[:2])
        }

# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaBot:
    def __init__(self):
        self.bot = RoletaBotUnificado()
        self.analisador = AnalisadorDuzias(window=20)
        self.ml = MLPredictor()
        self.historico_numeros = deque(maxlen=200)
        self.historico_lucky = deque(maxlen=100)
        self.entrada_ativa = None
        self.historico_entradas = []
        self.acertos = 0
        self.erros = 0
        self.ultimo_numero = None
        self.sinais_grafico = []
        self.ml.carregar()
    
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data['number']
            lucky = numero_data.get('luckyNumbers', [])
        else:
            nr = int(numero_data)
            lucky = []
        
        self.bot.atualizar(nr, lucky)
        self.analisador.adicionar(nr)
        self.historico_numeros.append(nr)
        self.historico_lucky.append(lucky)
        self.ultimo_numero = nr
        
        # Verifica acerto
        if self.entrada_ativa:
            duzia_real = get_duzia(nr)
            duzia_prevista = self.entrada_ativa.get('duzia_prevista')
            duzia_sec = self.entrada_ativa.get('duzia_secundaria')
            
            acertou = False
            acerto_primario = False
            
            if duzia_prevista and nr != 0:
                acerto_primario = (duzia_real == duzia_prevista)
                acertou = acerto_primario or (duzia_sec and duzia_real == duzia_sec)
            
            if acerto_primario:
                self.acertos += 1
                self.bot.performance['acertos'] += 1
                st.session_state.acertos_duzia = st.session_state.get('acertos_duzia', 0) + 1
            elif acertou:
                self.acertos += 0.5
            elif nr != 0:
                self.erros += 1
                self.bot.performance['erros'] += 1
                st.session_state.erros_duzia = st.session_state.get('erros_duzia', 0) + 1
            
            self.bot.performance['historico'].append(1 if acerto_primario else 0)
            
            self.historico_entradas.append({
                'rodada': len(self.historico_numeros),
                'hora': datetime.now().strftime('%H:%M:%S'),
                'resultado': nr,
                'duzia_real': f"D{duzia_real}" if duzia_real != 0 else "Z",
                'duzia_prevista': f"D{duzia_prevista}",
                'acerto': acertou,
                'acerto_primaria': acerto_primario,
                'modo': self.entrada_ativa.get('modo', 'regras')
            })
            
            if len(self.historico_entradas) > 50:
                self.historico_entradas = self.historico_entradas[-50:]
            
            enviar_resultado_auto(nr, acertou, nr in lucky)
            self.entrada_ativa = None
        
        # FORÇA treino ML se necessário
        if st.session_state.get('modo_ml', False):
            giros_minimos = st.session_state.get('giros_minimos_ml', 10)
            total_giros = len(self.historico_numeros)
            
            precisa_treinar = (not self.ml.ready) or (self.ml.training_samples == 0)
            
            if precisa_treinar and total_giros >= giros_minimos:
                sucesso = self.ml.treinar(
                    [get_duzia(n) for n in self.historico_numeros],
                    list(self.historico_numeros)
                )
                if sucesso:
                    st.toast(f"✅ ML treinado! {self.ml.training_samples} amostras")
            
            # Re-treino periódico
            if self.ml.ready and total_giros % 30 == 0 and total_giros > 0:
                self.ml.treinar(
                    [get_duzia(n) for n in self.historico_numeros],
                    list(self.historico_numeros)
                )
        
        # GERA PREVISÃO
        duzia_map = {1: list(range(1, 13)), 2: list(range(13, 25)), 3: list(range(25, 37))}
        
        previsao_ml = None
        if st.session_state.get('modo_ml', False) and self.ml.ready:
            previsao_ml = self.ml.prever([get_duzia(n) for n in self.historico_numeros])
        
        analise = self.analisador.analisar()
        
        if previsao_ml:
            dz1 = previsao_ml['duzia_principal']
            dz2 = previsao_ml['duzia_secundaria']
            conf = previsao_ml['confianca'] * 50
            modo = 'ml'
        elif analise:
            dz1 = analise['duzia_principal']
            dz2 = analise['duzia_secundaria']
            conf = analise['confianca'] * 3
            modo = 'regras'
        else:
            dz1 = 1
            dz2 = 2
            conf = 0
            modo = 'regras'
        
        if st.session_state.get('modo_agressivo', False):
            numeros = sorted(set(duzia_map.get(dz1, []) + duzia_map.get(dz2, [])))
        else:
            numeros = sorted(duzia_map.get(dz1, []))
        
        self.entrada_ativa = {
            'numeros_apostar': numeros,
            'duzia_prevista': dz1,
            'duzia_secundaria': dz2,
            'confianca': float(conf),
            'modo': modo
        }
        
        self.sinais_grafico.append((len(self.historico_numeros) - 1, dz1))
        
        enviar_previsao_auto({
            'numeros_apostar': numeros,
            'forca_real': float(min(95, conf)),
            'motor': f"{'🤖ML' if modo == 'ml' else '📊'} D{dz1}",
            'gatilho': f"D{dz1}+D{dz2} | Conf: {conf:.0f}%"
        })
        
        salvar_sessao()
    
    def zerar(self):
        self.acertos = 0
        self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear()
        self.historico_lucky.clear()
        self.entrada_ativa = None
        self.ultimo_numero = None
        self.sinais_grafico = []
        self.bot = RoletaBotUnificado()
        self.analisador = AnalisadorDuzias(window=20)
        self.ml = MLPredictor()
        st.session_state.acertos_duzia = 0
        st.session_state.erros_duzia = 0
        salvar_sessao()

# =============================
# FUNÇÕES AUXILIARES
# =============================
def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    try:
        with open(caminho, "w") as f:
            json.dump(historico, f, indent=2)
    except: pass

def fetch_latest_result():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=5)
        r.raise_for_status()
        d = r.json()
        gd = d.get("data", {})
        rs = gd.get("result", {})
        nm = rs.get("outcome", {}).get("number")
        ts = gd.get("startedAt")
        ln = []
        for item in rs.get('luckyNumbersList', []):
            n = item.get('number')
            if n is not None: ln.append(n)
        return {"number": nm, "timestamp": ts, "luckyNumbers": ln}
    except: return None

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎰 Roleta Bot Pro - Completo", layout="wide")
st.title("🎰 Roleta Bot Pro - Estratégias + ML + Telegram")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    sis = st.session_state.sistema
    for n in dados.get('historico_numeros', []):
        sis.bot.atualizar(n)
        sis.analisador.adicionar(n)
        sis.historico_numeros.append(n)
    sis.acertos = dados.get('sistema_acertos', 0)
    sis.erros = dados.get('sistema_erros', 0)
    sis.entrada_ativa = dados.get('entrada_ativa', None)
    st.session_state.acertos_duzia = dados.get('acertos_duzia', 0)
    st.session_state.erros_duzia = dados.get('erros_duzia', 0)
    st.session_state.modo_agressivo = dados.get('modo_agressivo', False)
    st.session_state.modo_ml = dados.get('modo_ml', False)
    st.session_state.giros_minimos_ml = dados.get('giros_minimos_ml', 10)
    st.session_state.telegram_token = dados.get('telegram_token', '')
    st.session_state.telegram_chat_id = dados.get('telegram_chat_id', '')
    if os.path.exists(ENTRADAS_PATH):
        try:
            with open(ENTRADAS_PATH, 'r') as f:
                sis.historico_entradas = json.load(f)
        except: pass

for k, v in {
    'modo_automatico': True, 'modo_agressivo': False, 'modo_ml': False,
    'giros_minimos_ml': 10, 'acertos_duzia': 0, 'erros_duzia': 0,
    'telegram_token': '', 'telegram_chat_id': ''
}.items():
    if k not in st.session_state: st.session_state[k] = v

if "historico" not in st.session_state:
    st.session_state.historico = []
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f: st.session_state.historico = json.load(f)
        except: pass

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.markdown("## ⚙️ Configurações")
    
    st.markdown("### 🧠 Inteligência")
    st.session_state.modo_ml = st.checkbox("🤖 Machine Learning (XGBoost)", value=st.session_state.modo_ml)
    
    if st.session_state.modo_ml:
        st.session_state.giros_minimos_ml = st.slider("Giros para treinar ML", 5, 30, st.session_state.giros_minimos_ml, 5)
        sis = st.session_state.sistema
        if sis.ml.ready and sis.ml.training_samples > 0:
            st.success(f"✅ ML treinado ({sis.ml.training_samples} amostras)")
        else:
            giros = len(sis.historico_numeros)
            st.warning(f"⏳ {giros}/{st.session_state.giros_minimos_ml} giros | ML não treinado")
            if giros >= st.session_state.giros_minimos_ml:
                if st.button("🧠 FORÇAR TREINO ML", use_container_width=True, type="primary"):
                    with st.spinner("Treinando XGBoost..."):
                        sucesso = sis.ml.treinar(
                            [get_duzia(n) for n in sis.historico_numeros],
                            list(sis.historico_numeros)
                        )
                        if sucesso:
                            st.success(f"✅ ML treinado! {sis.ml.training_samples} amostras")
                            salvar_sessao()
                            st.rerun()
                        else:
                            st.error("❌ Erro! Execute: pip install xgboost scikit-learn")
    
    st.markdown("---")
    st.session_state.modo_agressivo = st.checkbox("🔥 Modo Agressivo (2 Dúzias)", value=st.session_state.modo_agressivo)
    st.session_state.modo_automatico = st.checkbox("🤖 Modo Automático", value=st.session_state.modo_automatico)
    
    st.markdown("---")
    with st.expander("🔔 Telegram", expanded=False):
        st.session_state.telegram_token = st.text_input("Token", value=st.session_state.telegram_token, type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID", value=st.session_state.telegram_chat_id)
    
    c1, c2 = st.columns(2)
    c1.button("💾 Salvar", on_click=lambda: [salvar_resultado_em_arquivo(st.session_state.historico), salvar_sessao()], use_container_width=True)
    c2.button("🗑️ Zerar", on_click=lambda: st.session_state.sistema.zerar() or st.rerun(), use_container_width=True)

# =============================
# INPUT
# =============================
sis = st.session_state.sistema

st.subheader("🎲 Inserir Números")
c1, c2 = st.columns([3, 1])
with c1:
    entrada = st.text_input("Número (0-36):", key="num", placeholder="Digite e Enter")
with c2:
    if st.button("🎯 Enviar", use_container_width=True, type="primary"):
        if entrada and entrada.isdigit() and 0 <= int(entrada) <= 36:
            nr = int(entrada)
            st.session_state.historico.append({"number": nr, "timestamp": datetime.now().isoformat(), "luckyNumbers": []})
            sis.processar_novo_numero(nr)
            salvar_resultado_em_arquivo(st.session_state.historico)
            st.rerun()

if st.session_state.modo_automatico:
    st_autorefresh(interval=3000, key="refresh")
    res = fetch_latest_result()
    if res and res.get("number") is not None:
        if not st.session_state.historico or res["timestamp"] != st.session_state.historico[-1].get("timestamp"):
            st.session_state.historico.append(res)
            sis.processar_novo_numero(res)
            salvar_resultado_em_arquivo(st.session_state.historico)
            st.rerun()

# =============================
# MÉTRICAS
# =============================
st.markdown("---")
c1, c2, c3, c4, c5 = st.columns(5)
total = int(sis.acertos + sis.erros)
tx = (sis.acertos / total * 100) if total > 0 else 0
c1.metric("✅ Acertos", int(sis.acertos))
c2.metric("❌ Erros", int(sis.erros))
c3.metric("📊 Win Rate", f"{tx:.0f}%")
c4.metric("🎯 Dúzia", f"D{sis.entrada_ativa['duzia_prevista']}" if sis.entrada_ativa else "-")
c5.metric("🧠 Modo", "🤖ML" if st.session_state.modo_ml else "📊Regras")

# =============================
# GRÁFICOS + ENTRADA
# =============================
col_graf, col_ent = st.columns([3, 2])

with col_graf:
    st.subheader("📈 Análise em Tempo Real")
    
    if len(sis.historico_numeros) >= 5:
        analise = sis.analisador.analisar()
        
        if analise:
            score = analise['score']
            
            fig = go.Figure(data=[go.Bar(
                x=['D1 (1-12)', 'D2 (13-24)', 'D3 (25-36)'],
                y=[score[1], score[2], score[3]],
                marker_color=['#FF6B6B' if score[1] == max(score.values()) else '#4ECDC4',
                             '#FF6B6B' if score[2] == max(score.values()) else '#4ECDC4',
                             '#FF6B6B' if score[3] == max(score.values()) else '#4ECDC4'],
                text=[f'{score[1]}', f'{score[2]}', f'{score[3]}'],
                textposition='auto'
            )])
            fig.update_layout(title="🎯 Scores das Dúzias", height=250, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        if len(sis.historico_numeros) >= 5:
            ultimos = list(sis.historico_numeros)[-20:]
            duzias = [get_duzia(n) for n in ultimos]
            
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                y=duzias, mode='lines+markers',
                line=dict(color='#FFD700', width=2),
                marker=dict(size=8), name='Dúzia'
            ))
            
            if sis.sinais_grafico:
                sx, sy = [], []
                offset = len(duzias) - 20
                for idx, dz in sis.sinais_grafico[-10:]:
                    pos = idx - offset
                    if 0 <= pos < 20:
                        sx.append(pos)
                        sy.append(dz)
                if sx:
                    fig2.add_trace(go.Scatter(
                        x=sx, y=sy, mode='markers',
                        marker=dict(symbol='star', size=12, color='red'),
                        name='Entrada'
                    ))
            
            fig2.update_layout(
                title="📉 Histórico de Dúzias c/ Sinais",
                yaxis=dict(tickvals=[1, 2, 3], ticktext=['D1', 'D2', 'D3'], range=[0.5, 3.5]),
                height=250, showlegend=True
            )
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info(f"⏳ {len(sis.historico_numeros)}/5 giros")

with col_ent:
    st.subheader("🎰 Entrada Atual")
    
    if sis.entrada_ativa:
        ent = sis.entrada_ativa
        dz1 = ent.get('duzia_prevista', 0)
        dz2 = ent.get('duzia_secundaria', 0)
        conf = ent.get('confianca', 0) or 0.0
        modo = ent.get('modo', 'regras')
        
        cor = "#8A2BE2" if modo == 'ml' else "#00CC00"
        emoji = "🤖" if modo == 'ml' else "📊"
        
        limite1 = "1-12" if dz1 == 1 else "13-24" if dz1 == 2 else "25-36"
        limite2 = "1-12" if dz2 == 1 else "13-24" if dz2 == 2 else "25-36"
        
        st.markdown(f"""
        <div style="background-color:{cor}22; border:2px solid {cor}; border-radius:15px; padding:15px;">
            <h3 style="color:{cor}; text-align:center;">{emoji} D{dz1} ({limite1})</h3>
            <p style="text-align:center;">Confiança: {conf:.0f}%</p>
            <p style="text-align:center; color:#FFA500;">🛡️ D{dz2} ({limite2})</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("**🎲 Apostar em:**")
        nums = ent.get('numeros_apostar', [])
        cols = st.columns(6)
        for i, n in enumerate(sorted(nums)):
            cols[i % 6].button(str(n), key=f"n{n}", use_container_width=True)
        
        st.progress(float(min(1.0, conf / 100)))
    else:
        st.info("🔍 Aguardando primeiro giro...")
    
    if sis.ultimo_numero is not None:
        st.markdown("---")
        st.write(f"🔄 Último: #{sis.ultimo_numero} → D{get_duzia(sis.ultimo_numero)}")

# =============================
# HISTÓRICO
# =============================
st.markdown("---")
st.subheader("📝 Histórico de Entradas")
if sis.historico_entradas:
    tabela = []
    for e in reversed(sis.historico_entradas[-15:]):
        tabela.append({
            "Rod": e.get('rodada', '-'),
            "Nº": e.get('resultado', '-'),
            "Real": e.get('duzia_real', '-'),
            "Prev": e.get('duzia_prevista', '-'),
            "Res": "✅" if e.get('acerto_primaria') else "🟡" if e.get('acerto') else "❌"
        })
    st.dataframe(tabela, use_container_width=True, height=250)
else:
    st.info("Nenhuma entrada ainda.")

st.markdown("---")
st.caption(f"🤖 Roleta Bot Pro | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
salvar_sessao()
