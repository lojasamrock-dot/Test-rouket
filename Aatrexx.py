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

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_roleta.json"
PERFORMANCE_PATH = "performance_bot.json"
ENTRADAS_PATH = "historico_entradas.json"

def salvar_sessao():
    """Salva estado completo incluindo mults e entrada_ativa"""
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
            'historico_lucky': list(sis.historico_lucky),
            'historico_mults': list(sis.historico_mults),
            'entrada_ativa': sis.entrada_ativa,
            'sistema_acertos': sis.acertos,
            'sistema_erros': sis.erros,
            'estado_inversao': sis.estado_inversao,
            'modo_duzias_colunas': st.session_state.get('modo_duzias_colunas', False),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'max_n_apostas': st.session_state.get('max_n_apostas', 7),
            'min_n_apostas': st.session_state.get('min_n_apostas', 4),
            'forca_minima_entrada': st.session_state.get('forca_minima_entrada', 55),
            'limitar_numeros_altos': st.session_state.get('limitar_numeros_altos', True),
            'evitar_zero': st.session_state.get('evitar_zero', True),
            'max_gatilhos': st.session_state.get('max_gatilhos', 2),
            'modo_inversao_auto': st.session_state.get('modo_inversao_auto', False),
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
        numeros = sorted(previsao['numeros_apostar'])
        forca = previsao.get('forca_real', 0)
        motor = previsao.get('motor', '')
        gatilho = previsao.get('gatilho', '')
        invertido = previsao.get('invertido', False)
        
        if invertido:
            emoji = "🔄"
        elif forca >= 65:
            emoji = "🔥"
        elif forca >= 55:
            emoji = "🎯"
        else:
            emoji = "⚠️"
        
        st.toast(f"{emoji} {motor} - {forca}%")
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            tag = "[INVERTIDO]" if invertido else ""
            enviar_telegram(f"🔔 {tag} F{forca}% | {motor}\n{gatilho}\n🔢 " + " ".join(map(str, numeros)))
        
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
# ROLETA BASE
# =============================
class RoletaBase:
    def __init__(self):
        self.race = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        self.vermelhos = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        self.pretos = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
        self.espelhos = {0:0, 12:21, 21:12, 13:31, 31:13, 23:32, 32:23, 1:10, 10:1, 2:20, 20:2, 3:30, 30:3, 4:19, 19:4, 5:24, 24:5, 6:27, 27:6, 7:28, 28:7, 8:23, 23:8, 9:22, 22:9, 11:36, 36:11, 14:31, 31:14, 15:32, 32:15, 16:33, 33:16, 17:34, 34:17, 18:29, 29:18, 25:26, 26:25}
        self.voisins = {22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25}
        self.tiers = {27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33}
        self.orphelins = {1, 20, 14, 31, 9, 17, 34, 6}
        self.primos = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}
        self.baixos = set(range(1, 19))
        self.altos = set(range(19, 37))
        self.numeros_problematicos = {0, 32, 33, 34, 35}
        self.max_problematicos = 2
        
        self.coluna1 = set(range(1, 13))
        self.coluna2 = set(range(13, 25))
        self.coluna3 = set(range(25, 37))
    
    def get_vizinhos(self, n, r=2):
        if n not in self.race:
            return []
        i = self.race.index(n)
        return [self.race[(i + j) % 37] for j in range(-r, r + 1)]
    
    def get_setor_cilindro(self, n):
        if n in self.voisins:
            return "Voisins"
        if n in self.tiers:
            return "Tiers"
        if n in self.orphelins:
            return "Orphelins"
        return "Zero"
    
    def get_coluna(self, n):
        if n in self.coluna1:
            return 1
        elif n in self.coluna2:
            return 2
        elif n in self.coluna3:
            return 3
        return 0
    
    def get_duzia(self, n):
        if 1 <= n <= 12:
            return 1
        elif 13 <= n <= 24:
            return 2
        elif 25 <= n <= 36:
            return 3
        return 0
    
    def sao_vizinhos_fisicos(self, a, b, d=1):
        if a not in self.race or b not in self.race:
            return False
        ia, ib = self.race.index(a), self.race.index(b)
        diff = abs(ia - ib)
        return diff <= d or diff >= 37 - d
    
    def get_setor_oposto(self, setor):
        if setor == "Voisins":
            return "Orphelins"
        elif setor == "Orphelins":
            return "Voisins"
        elif setor == "Tiers":
            return "Tiers"
        return None

# =============================
# FUNÇÕES DE MAPEAMENTO REAL (MATEMÁTICA PURA)
# =============================
def get_coluna_real(n):
    """Retorna a coluna real baseada na matemática da roleta: 3,6,9..."""
    if n == 0: return 0
    return 3 if n % 3 == 0 else n % 3

def get_duzia_real(n):
    """Retorna a dúzia real: 1-12=1, 13-24=2, 25-36=3"""
    if n == 0: return 0
    return (n - 1) // 12 + 1

def get_setor_roda(n):
    """Retorna o setor físico do cilindro"""
    voisins = [22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25]
    tiers = [27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33]
    orphelins = [1, 20, 14, 31, 9, 17, 34]
    if n in voisins: return "Voisins (Vizinhos do Zero)"
    if n in tiers: return "Tiers (Terço)"
    if n in orphelins: return "Orphelins (Órfãos)"
    return "Zero"

# =============================
# ESTRATÉGIAS ORIGINAIS (18)
# =============================

class EstrategiaSniperElite:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h, lucky_hist):
        if len(h) < 6:
            return None
        termos = [n%10 for n in h[-8:]]
        contagem = Counter(termos)
        td, freq = contagem.most_common(1)[0]
        if freq < 3:
            return None
        aposta = set()
        aposta.update(self.roleta.get_vizinhos(h[-1], 1)[:2])
        for n in range(37):
            if n%10 == td:
                aposta.add(n)
            if len(aposta) >= 7:
                break
        if lucky_hist:
            all_lucky = [n for sub in lucky_hist[-8:] for n in sub]
            for n, _ in Counter(all_lucky).most_common(2):
                aposta.add(n)
        return {
            'base': set(list(aposta)[:7]),
            'forca': 50+freq*5,
            'estrategias': [f'Terminal {td}'],
            'gatilho': f'Terminal {td} ({freq}x)'
        }

class EstrategiaLuckyVizinhos:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h, lucky_hist):
        if len(h) < 3 or not lucky_hist:
            return None
        all_lucky = [n for sub in lucky_hist[-10:] for n in sub]
        if len(all_lucky) < 2:
            return None
        freq = Counter(all_lucky)
        recentes = set(h[-3:])
        lucky_rec = [n for n in freq if n in recentes]
        top = sorted(lucky_rec, key=lambda x: freq[x], reverse=True)[:3] if lucky_rec else [n for n, _ in freq.most_common(3)]
        b = set(top)
        for n in top[:2]:
            b.update(self.roleta.get_vizinhos(n, 1)[:1])
        for n, _ in Counter(h[-5:]).most_common(2):
            b.add(n)
        return {
            'base': set(list(b)[:7]),
            'forca': 50+len(all_lucky)*2,
            'estrategias': [f'Lucky {top[:2]}'],
            'gatilho': f'Lucky {top[:2]}'
        }

class EstrategiaRepeticao:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 2:
            return None
        u, p = h[-1], h[-2]
        if u != p:
            return None
        b = set([u])
        b.update(self.roleta.get_vizinhos(u, 1)[:3])
        return {
            'base': b,
            'forca': 80,
            'estrategias': [f'Repetição {u}'],
            'gatilho': f'Repetição {u}'
        }

class EstrategiaGapCurto:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 3:
            return None
        u = h[-1]
        b = set()
        gap = None
        
        if len(h) >= 3 and h[-3] == u:
            b.add(u)
            b.add(h[-2])
            gap = 2
        if len(h) >= 4 and h[-4] == u:
            b.update([u, h[-2], h[-3]])
            gap = gap or 3
        if len(h) >= 5 and h[-5] == u:
            b.add(u)
            gap = gap or 4
        
        if not b:
            return None
        
        for n in list(b)[:2]:
            b.update(self.roleta.get_vizinhos(n, 1)[:1])
        
        return {
            'base': b,
            'forca': 55+(gap or 0)*5,
            'estrategias': [f'Gap {gap}'],
            'gatilho': f'Gap {gap} giros: {u}'
        }

class EstrategiaMineracao:
    def analisar(self, h):
        if len(h) < 5:
            return None
        u = h[-1]
        t = defaultdict(list)
        for i in range(len(h)-1):
            t[h[i]].append(h[i+1])
        seg = t.get(u, [])
        if len(seg) < 2:
            return None
        top = [(n, c) for n, c in Counter(seg).most_common(2) if c/len(seg) >= 0.15]
        if not top:
            return None
        return {
            'base': set([n for n, _ in top]),
            'forca': 50,
            'estrategias': [f'Markov {u}→{top[0][0]}'],
            'gatilho': f'Após {u} → {top[0][0]}'
        }

class EstrategiaDuziaDominante:
    def analisar(self, h):
        if len(h) < 10:
            return None
        dz = {1: set(range(1,13)), 2: set(range(13,25)), 3: set(range(25,37))}
        cnt = Counter((n-1)//12+1 for n in h[-10:] if n != 0)
        if not cnt:
            return None
        d, freq = cnt.most_common(1)[0]
        if freq < 6:
            return None
        b = set()
        b.update(list(dz[d] - set(h[-5:]))[:3])
        b.update(list(dz[d].intersection(set(h[-5:])))[:2])
        return {
            'base': b,
            'forca': 50+(freq-6)*5,
            'estrategias': [f'Dúzia {d}'],
            'gatilho': f'Dúzia {d} ({freq}/10)'
        }

class EstrategiaEspelho:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 2:
            return None
        u = h[-1]
        if u not in self.roleta.espelhos:
            return None
        esp = self.roleta.espelhos[u]
        b = set([esp, u])
        b.update(self.roleta.get_vizinhos(esp, 1)[:2])
        return {
            'base': b,
            'forca': 50,
            'estrategias': [f'Espelho {u}↔{esp}'],
            'gatilho': f'Espelho {u}↔{esp}'
        }

class EstrategiaSomaCinco:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 2:
            return None
        count = sum(1 for i in range(len(h)-1) if h[i]+5 == h[i+1] or (h[i]+5 > 36 and h[i]+5-37 == h[i+1]))
        if count < 2:
            return None
        u = h[-1]
        b = set()
        for d in [5, 10]:
            prox = u + d
            if prox > 36:
                prox -= 37
            b.add(prox)
        b.add(u)
        b.update(self.roleta.get_vizinhos(u, 1)[:2])
        return {
            'base': b,
            'forca': 45+count*5,
            'estrategias': [f'+5'],
            'gatilho': f'Padrão +5 ({count}x)'
        }

class EstrategiaLuckyAlto:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h, lucky_hist, mult_hist):
        if len(h) < 3 or not lucky_hist:
            return None
        lucky_alto = []
        for lucky_list, mult_dict in zip(lucky_hist[-30:], mult_hist[-30:]):
            for n in lucky_list:
                m = mult_dict.get(n, 0) if mult_dict else 0
                if m and m >= 200:
                    lucky_alto.append((n, m))
        if len(lucky_alto) < 2:
            return None
        recentes = lucky_alto[-3:]
        b = set()
        for n, _ in recentes:
            b.add(n)
            b.update(self.roleta.get_vizinhos(n, 1)[:1])
        b.update(self.roleta.get_vizinhos(h[-1], 1)[:2])
        return {
            'base': set(list(b)[:6]),
            'forca': 55,
            'estrategias': ['Lucky Alto'],
            'gatilho': f'Lucky Alto'
        }

class EstrategiaCicloOito:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 7:
            return None
        u = h[-1]
        if len(h) >= 9 and h[-9] == u:
            b = set([u])
            b.update(self.roleta.get_vizinhos(u, 1)[:3])
            return {
                'base': b,
                'forca': 55,
                'estrategias': ['Ciclo 8'],
                'gatilho': f'Ciclo 8 giros: {u}'
            }
        if len(h) >= 7 and h[-7] == u:
            b = set([u])
            b.update(self.roleta.get_vizinhos(u, 1)[:2])
            return {
                'base': b,
                'forca': 45,
                'estrategias': ['Ciclo 6'],
                'gatilho': f'Ciclo 6 giros: {u}'
            }
        return None

class EstrategiaAlternanciaCor:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 6:
            return None
        cores = ['V' if n in self.roleta.vermelhos else 'P' if n in self.roleta.pretos else 'Z' for n in h[-10:]]
        alt = 0
        for i in range(1, len(cores)):
            if cores[i] != cores[i-1] and cores[i] != 'Z' and cores[i-1] != 'Z':
                alt += 1
            else:
                alt = 0
        if alt < 5:
            return None
        prox = 'P' if cores[-1] == 'V' else 'V'
        alvo = self.roleta.pretos if prox == 'P' else self.roleta.vermelhos
        b = alvo.intersection(set(h[-10:]))
        if len(b) < 4:
            b = set(list(alvo)[:6])
        return {
            'base': b,
            'forca': 45+alt*2,
            'estrategias': [f'Alternância →{prox}'],
            'gatilho': f'Alternância {alt}x → {prox}'
        }

class EstrategiaSetorCilindro:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 5:
            return None
        setores = [self.roleta.get_setor_cilindro(n) for n in h[-5:]]
        contagem = Counter(setores)
        setor_dom, freq = contagem.most_common(1)[0]
        if freq < 3 or setor_dom == "Zero":
            return None
        sn = {
            'Voisins': self.roleta.voisins,
            'Tiers': self.roleta.tiers,
            'Orphelins': self.roleta.orphelins
        }
        b = set()
        b.update(list(sn[setor_dom] - set(h[-5:]))[:4])
        b.update(list(sn[setor_dom].intersection(set(h[-5:])))[:2])
        return {
            'base': b,
            'forca': 45+freq*5,
            'estrategias': [f'Setor {setor_dom}'],
            'gatilho': f'Setor {setor_dom} ({freq}/5)'
        }

class EstrategiaZeroVirada:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 2:
            return None
        if h[-1] == 0 or h[-2] == 0:
            b = set(list(self.roleta.voisins)[:6])
            b.update(self.roleta.get_vizinhos(0, 2)[:2])
            return {
                'base': b,
                'forca': 50,
                'estrategias': ['Pós-Zero'],
                'gatilho': 'Após Zero → Voisins'
            }
        return None

class EstrategiaPrimos:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 6:
            return None
        pr = [n for n in h[-6:] if n in self.roleta.primos]
        if len(pr) < 4:
            return None
        b = set(list(self.roleta.primos - set(h[-6:]))[:3])
        b.update(pr[-2:])
        b.update(self.roleta.get_vizinhos(h[-1], 1)[:1])
        return {
            'base': b,
            'forca': 45+len(pr)*3,
            'estrategias': ['Primos'],
            'gatilho': f'Primos ({len(pr)}/6)'
        }

class EstrategiaVizinhosFisicos:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 2:
            return None
        u, p = h[-1], h[-2]
        if not self.roleta.sao_vizinhos_fisicos(u, p):
            return None
        b = set([u, p])
        b.update(self.roleta.get_vizinhos(u, 1)[:2])
        return {
            'base': b,
            'forca': 55,
            'estrategias': ['Vizinhos Físicos'],
            'gatilho': f'Vizinhos {p}↔{u}'
        }

class EstrategiaLuckyTerminal:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h, lucky_hist):
        if len(h) < 2 or not lucky_hist:
            return None
        for i in range(len(h)-1, -1, -1):
            if i < len(lucky_hist) and h[i] in lucky_hist[i]:
                ln = h[i]
                t = ln%10
                b = set([n for n in range(37) if n%10==t][:5])
                b.update(self.roleta.get_vizinhos(ln, 1)[:2])
                return {
                    'base': b,
                    'forca': 50,
                    'estrategias': [f'Lucky Term {t}'],
                    'gatilho': f'Lucky {ln} → Term {t}'
                }
        return None

class EstrategiaFaixaNumerica:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 5:
            return None
        faixas = ['B' if 1 <= n <= 18 else 'A' if 19 <= n <= 36 else 'Z' for n in h[-6:]]
        contagem = Counter([f for f in faixas if f != 'Z'])
        if not contagem:
            return None
        fd, freq = contagem.most_common(1)[0]
        if freq < 4:
            return None
        fo = self.roleta.altos if fd == 'B' else self.roleta.baixos
        b = fo.intersection(set(h[-10:]))
        if len(b) < 4:
            b = set(list(fo)[:5])
        return {
            'base': b,
            'forca': 45+freq*3,
            'estrategias': ['Faixa Oposta'],
            'gatilho': f'Faixa {fd}→oposta'
        }

class EstrategiaNumeroDoDia:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 20:
            return None
        ft = Counter(h[-50:])
        nq = [n for n, c in ft.most_common(3) if c >= 5]
        if not nq:
            return None
        b = set(nq)
        for n in nq[:2]:
            b.update(self.roleta.get_vizinhos(n, 1)[:1])
        return {
            'base': b,
            'forca': 50+ft[nq[0]],
            'estrategias': ['Nº do Dia'],
            'gatilho': f'Nº do dia: {nq[:2]}'
        }

# =============================
# ESTRATÉGIAS DA PRIMEIRA ANÁLISE (6)
# =============================

class EstrategiaConfirmacaoLucky:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h, lucky_hist):
        if len(h) < 3 or not lucky_hist:
            return None
        
        recent_lucky = []
        for i in range(max(0, len(lucky_hist)-5), len(lucky_hist)):
            recent_lucky.extend(lucky_hist[i])
        
        if not recent_lucky:
            return None
        
        lucky_freq = Counter(recent_lucky)
        nao_saiu = [n for n in lucky_freq if n not in h[-3:]]
        
        if not nao_saiu:
            return None
        
        top_lucky = sorted(nao_saiu, key=lambda x: lucky_freq[x], reverse=True)[:3]
        
        b = set(top_lucky)
        for n in top_lucky[:2]:
            b.update(self.roleta.get_vizinhos(n, 1)[:2])
        
        forca = 55 + len(nao_saiu) * 3
        return {
            'base': set(list(b)[:7]),
            'forca': min(85, forca),
            'estrategias': ['Confirmação Lucky'],
            'gatilho': f'Lucky pendente: {top_lucky[:2]}'
        }

class EstrategiaPendulo:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 8:
            return None
        
        ultimos = h[-8:]
        altos = sum(1 for n in ultimos if n >= 19)
        baixos = len(ultimos) - altos
        
        if altos >= 6:
            alvo = self.roleta.baixos
            tendencia = "Baixos"
        elif baixos >= 6:
            alvo = self.roleta.altos
            tendencia = "Altos"
        else:
            return None
        
        b = alvo.intersection(set(h[-15:])) if len(h) >= 15 else alvo
        b.update(self.roleta.get_vizinhos(h[-1], 1)[:3])
        
        forca = 50 + abs(altos - baixos) * 5
        return {
            'base': set(list(b)[:8]),
            'forca': min(80, forca),
            'estrategias': [f'Pêndulo →{tendencia}'],
            'gatilho': f'Pêndulo {altos}A/{baixos}B → {tendencia}'
        }

class EstrategiaQuenteFrio:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h, lucky_hist):
        if len(h) < 15:
            return None
        
        recentes = set(h[-15:])
        todos = set(range(37))
        frios = list(todos - recentes - {0})
        
        if not frios:
            return None
        
        b = set()
        if lucky_hist:
            recent_lucky = [n for sub in lucky_hist[-5:] for n in sub]
            for lucky_num in recent_lucky[:3]:
                vizinhos = set(self.roleta.get_vizinhos(lucky_num, 2))
                frios_proximos = vizinhos.intersection(frios)
                b.update(list(frios_proximos)[:3])
        
        frios_restantes = [n for n in frios if n not in b]
        random.shuffle(frios_restantes)
        b.update(frios_restantes[:4])
        
        forca = 45 + len(frios) * 2
        return {
            'base': set(list(b)[:7]),
            'forca': min(75, forca),
            'estrategias': ['Quente/Frio'],
            'gatilho': f'Frios ({len(frios)}): {list(b)[:3]}'
        }

class EstrategiaConfirmacaoDupla:
    def analisar(self, h):
        return None

class EstrategiaColunasAlternadas:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 6:
            return None
        
        colunas = [self.roleta.get_coluna(n) for n in h[-6:] if n != 0]
        if len(colunas) < 4:
            return None
        
        padrao = []
        for i in range(1, len(colunas)):
            if colunas[i] != colunas[i-1]:
                padrao.append(colunas[i])
        
        if len(padrao) < 3:
            return None
        
        ultima_col = colunas[-1]
        colunas_alvo = [1, 2, 3]
        colunas_alvo.remove(ultima_col)
        coluna_provavel = colunas_alvo[0]
        
        col_map = {1: self.roleta.coluna1, 2: self.roleta.coluna2, 3: self.roleta.coluna3}
        alvo_numeros = col_map[coluna_provavel]
        
        b = alvo_numeros.intersection(set(h[-10:]))
        if len(b) < 3:
            b = set(list(alvo_numeros)[:5])
        
        return {
            'base': b,
            'forca': 45,
            'estrategias': ['Colunas Alternadas'],
            'gatilho': f'Coluna {ultima_col}→{coluna_provavel}'
        }

class EstrategiaLuckySetor:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h, lucky_hist):
        if len(h) < 3 or not lucky_hist:
            return None
        
        setores_lucky = defaultdict(int)
        for i in range(max(0, len(lucky_hist)-8), len(lucky_hist)):
            for n in lucky_hist[i]:
                setor = self.roleta.get_setor_cilindro(n)
                if setor != "Zero":
                    setores_lucky[setor] += 1
        
        if not setores_lucky:
            return None
        
        setor_dom = max(setores_lucky, key=setores_lucky.get)
        
        sn = {
            'Voisins': self.roleta.voisins,
            'Tiers': self.roleta.tiers,
            'Orphelins': self.roleta.orphelins
        }
        
        if setor_dom not in sn:
            return None
        
        numeros_setor = sn[setor_dom]
        nao_sairam = numeros_setor - set(h[-5:])
        b = set(list(nao_sairam)[:4])
        ja_sairam = numeros_setor.intersection(set(h[-5:]))
        b.update(list(ja_sairam)[:3])
        
        forca = 50 + setores_lucky[setor_dom] * 5
        return {
            'base': b,
            'forca': min(80, forca),
            'estrategias': [f'Lucky Setor {setor_dom}'],
            'gatilho': f'Lucky Setor {setor_dom} ({setores_lucky[setor_dom]}x)'
        }

# =============================
# ESTRATÉGIAS DA SEGUNDA ANÁLISE (6)
# =============================

class EstrategiaLuckyCascata:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h, lucky_hist):
        if len(h) < 6 or not lucky_hist:
            return None
        
        lucky_sequence = []
        for i in range(max(0, len(lucky_hist)-8), len(lucky_hist)):
            lucky_sequence.append(set(lucky_hist[i]))
        
        persistentes = []
        for n in range(37):
            count = 0
            for ls in lucky_sequence[-5:]:
                if n in ls:
                    count += 1
                else:
                    count = 0
                if count >= 3:
                    persistentes.append(n)
                    break
        
        if not persistentes:
            return None
        
        b = set()
        for n in persistentes[:3]:
            b.add(n)
            b.update(self.roleta.get_vizinhos(n, 2)[:3])
        
        b.update(self.roleta.get_vizinhos(h[-1], 1)[:2])
        
        forca = 55 + len(persistentes) * 8
        return {
            'base': set(list(b)[:7]),
            'forca': min(85, forca),
            'estrategias': ['Lucky Cascata'],
            'gatilho': f'Cascata: {persistentes[:3]}'
        }

class EstrategiaRessacaLucky:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h, lucky_hist, entradas_hist=None):
        if len(h) < 8 or not lucky_hist:
            return None
        
        erros_recentes = 0
        if entradas_hist:
            for entrada in entradas_hist[-5:]:
                if not entrada.get('acerto', True):
                    erros_recentes += 1
        else:
            erros_recentes = 2
        
        if erros_recentes < 3:
            return None
        
        lucky_antigos = []
        for i in range(max(0, len(lucky_hist)-8), max(0, len(lucky_hist)-4)):
            lucky_antigos.extend(lucky_hist[i])
        
        if not lucky_antigos:
            return None
        
        lucky_freq = Counter(lucky_antigos)
        nao_sairam = [n for n in lucky_freq if n not in h[-5:]]
        
        if not nao_sairam:
            return None
        
        top = sorted(nao_sairam, key=lambda x: lucky_freq[x], reverse=True)[:4]
        
        b = set(top)
        for n in top[:2]:
            b.update(self.roleta.get_vizinhos(n, 1)[:2])
        
        forca = 55 + erros_recentes * 5
        return {
            'base': set(list(b)[:7]),
            'forca': min(80, forca),
            'estrategias': ['Ressaca Lucky'],
            'gatilho': f'Ressaca ({erros_recentes}❌): {top[:2]}'
        }

class EstrategiaEspelhoTemporal:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h, lucky_hist):
        if len(h) < 12 or not lucky_hist:
            return None
        
        resultados_antigos = h[-12:-8] if len(h) >= 12 else h[:-8]
        
        lucky_recentes = []
        for i in range(max(0, len(lucky_hist)-3), len(lucky_hist)):
            lucky_recentes.extend(lucky_hist[i])
        
        intersecao = set(resultados_antigos).intersection(set(lucky_recentes))
        
        if len(intersecao) < 2:
            return None
        
        b = set()
        for n in intersecao:
            b.update(self.roleta.get_vizinhos(n, 1)[:2])
            if n in self.roleta.espelhos:
                b.add(self.roleta.espelhos[n])
        
        forca = 50 + len(intersecao) * 8
        return {
            'base': set(list(b)[:7]),
            'forca': min(75, forca),
            'estrategias': ['Espelho Temporal'],
            'gatilho': f'Temp: {list(intersecao)[:3]}'
        }

class EstrategiaEsgotamentoColuna:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 8:
            return None
        
        colunas_vistas = {'col1': 0, 'col2': 0, 'col3': 0}
        ultima_aparicao = {'col1': -1, 'col2': -1, 'col3': -1}
        
        for i in range(len(h)-1, max(0, len(h)-20)-1, -1):
            n = h[i]
            if n == 0:
                continue
            col = self.roleta.get_coluna(n)
            colunas_vistas[f'col{col}'] += 1
            if ultima_aparicao[f'col{col}'] == -1:
                ultima_aparicao[f'col{col}'] = len(h) - 1 - i
        
        ausencias = {}
        for col in ['col1', 'col2', 'col3']:
            if ultima_aparicao[col] >= 4:
                ausencias[col] = ultima_aparicao[col]
        
        if not ausencias:
            return None
        
        coluna_esgotada = max(ausencias, key=ausencias.get)
        col_num = int(coluna_esgotada[-1])
        
        col_map = {1: self.roleta.coluna1, 2: self.roleta.coluna2, 3: self.roleta.coluna3}
        alvo = col_map[col_num]
        
        b = alvo.intersection(set(h[-15:]))
        if len(b) < 4:
            b.update(list(alvo)[:5])
        
        forca = 50 + ausencias[coluna_esgotada] * 5
        return {
            'base': set(list(b)[:7]),
            'forca': min(80, forca),
            'estrategias': ['Esgotamento Coluna'],
            'gatilho': f'Col {col_num} ausente {ausencias[coluna_esgotada]}g'
        }

class EstrategiaMicroCiclo3:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 6:
            return None
        
        if len(h) >= 6 and h[-3] == h[-6]:
            b = set([h[-3]])
            b.update(self.roleta.get_vizinhos(h[-3], 1)[:2])
            
            if len(h) >= 4:
                b.add(h[-4])
            
            return {
                'base': b,
                'forca': 65,
                'estrategias': ['Micro Ciclo 3'],
                'gatilho': f'Ciclo 3g: {h[-3]} repete'
            }
        
        if len(h) >= 7:
            ciclo1 = [h[-7], h[-6], h[-5]]
            ciclo2 = [h[-4], h[-3], h[-2]]
            
            dif1 = ciclo1[1] - ciclo1[0] if ciclo1[0] != 0 else 0
            dif2 = ciclo2[1] - ciclo2[0] if ciclo2[0] != 0 else 0
            
            if abs(dif1 - dif2) <= 2 and dif1 != 0:
                previsao = h[-2] + dif1
                if previsao > 36:
                    previsao -= 37
                elif previsao < 0:
                    previsao += 37
                
                b = set([previsao])
                b.update(self.roleta.get_vizinhos(previsao, 1)[:3])
                b.update(self.roleta.get_vizinhos(h[-1], 1)[:2])
                
                return {
                    'base': b,
                    'forca': 55,
                    'estrategias': ['Micro Ciclo 3'],
                    'gatilho': f'Ciclo 3g: Δ{dif1}→{previsao}'
                }
        
        return None

class EstrategiaSetorRitmado:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 8:
            return None
        
        setores = [self.roleta.get_setor_cilindro(n) for n in h[-8:] if n != 0]
        if len(setores) < 6:
            return None
        
        contagem = Counter(setores)
        setor_dom, freq = contagem.most_common(1)[0]
        
        if freq < 3 or setor_dom == "Zero":
            return None
        
        if setores[-1] == setor_dom:
            sn = {
                'Voisins': self.roleta.voisins,
                'Tiers': self.roleta.tiers,
                'Orphelins': self.roleta.orphelins
            }
            b = sn[setor_dom] - set(h[-3:])
            if len(b) < 4:
                b = sn[setor_dom]
            b = set(list(b)[:6])
        else:
            setor_oposto = self.roleta.get_setor_oposto(setor_dom)
            if setor_oposto:
                sn = {
                    'Voisins': self.roleta.voisins,
                    'Tiers': self.roleta.tiers,
                    'Orphelins': self.roleta.orphelins
                }
                b = sn[setor_oposto]
                b = set(list(b)[:6])
            else:
                return None
        
        forca = 45 + freq * 5
        return {
            'base': b,
            'forca': min(75, forca),
            'estrategias': ['Setor Ritmado'],
            'gatilho': f'Ritmo {setor_dom} ({freq}x)'
        }

# =============================
# 🆕 5 NOVAS ESTRATÉGIAS CORRETIVAS (BASEADAS NOS ERROS)
# =============================

class EstrategiaLuckyImediato:
    """✅ CORREÇÃO ERRO TIPO 1: Lucky numbers do giro ATUAL têm 35% de chance de sair"""
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h, lucky_hist):
        if len(h) < 1 or not lucky_hist:
            return None
        
        ultimo_lucky = lucky_hist[-1] if lucky_hist else []
        
        if len(ultimo_lucky) < 2:
            return None
        
        b = set(ultimo_lucky[:5])
        
        for n in ultimo_lucky[:2]:
            b.update(self.roleta.get_vizinhos(n, 1)[:2])
        
        forca = 65 + len(ultimo_lucky) * 3
        return {
            'base': set(list(b)[:7]),
            'forca': min(90, forca),
            'estrategias': ['Lucky Imediato'],
            'gatilho': f'Lucky atual: {ultimo_lucky[:3]}'
        }

class EstrategiaLuckyRecenteNaoSaiu:
    """✅ CORREÇÃO ERRO TIPO 2: Lucky dos últimos 3 giros que ainda não saíram como resultado"""
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h, lucky_hist):
        if len(h) < 3 or not lucky_hist:
            return None
        
        lucky_recentes = []
        for i in range(max(0, len(lucky_hist)-3), len(lucky_hist)):
            lucky_recentes.extend(lucky_hist[i])
        
        if not lucky_recentes:
            return None
        
        lucky_set = set(lucky_recentes)
        resultados_recentes = set(h[-5:])
        nao_sairam = lucky_set - resultados_recentes
        
        if len(nao_sairam) < 2:
            return None
        
        freq = Counter(lucky_recentes)
        top = sorted(nao_sairam, key=lambda x: freq[x], reverse=True)[:4]
        
        b = set(top)
        for n in top[:2]:
            b.update(self.roleta.get_vizinhos(n, 1)[:2])
        
        forca = 60 + len(nao_sairam) * 4
        return {
            'base': set(list(b)[:7]),
            'forca': min(85, forca),
            'estrategias': ['Lucky Recente'],
            'gatilho': f'Lucky ñ saiu: {top[:2]}'
        }

class EstrategiaEspelhoLucky:
    """✅ CORREÇÃO ERRO TIPO 3: Espelhos dos lucky numbers recentes"""
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h, lucky_hist):
        if len(h) < 2 or not lucky_hist:
            return None
        
        lucky_recentes = []
        for i in range(max(0, len(lucky_hist)-2), len(lucky_hist)):
            lucky_recentes.extend(lucky_hist[i])
        
        if not lucky_recentes:
            return None
        
        b = set()
        for n in lucky_recentes:
            if n in self.roleta.espelhos:
                esp = self.roleta.espelhos[n]
                b.add(esp)
                b.update(self.roleta.get_vizinhos(esp, 1)[:2])
        
        if len(b) < 2:
            return None
        
        b.update(lucky_recentes[:3])
        
        forca = 55 + len(b) * 3
        return {
            'base': set(list(b)[:7]),
            'forca': min(75, forca),
            'estrategias': ['Espelho Lucky'],
            'gatilho': f'Espelho Lucky: {list(b)[:3]}'
        }

class EstrategiaOrfaosSetor:
    """✅ CORREÇÃO ERRO TIPO 4: Quando setor domina 4+ giros, apostar no setor órfão"""
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 6:
            return None
        
        setores = [self.roleta.get_setor_cilindro(n) for n in h[-6:] if n != 0]
        if len(setores) < 5:
            return None
        
        contagem = Counter(setores)
        
        todos_setores = {'Voisins', 'Tiers', 'Orphelins'}
        setores_presentes = set(contagem.keys())
        setores_orfãos = todos_setores - setores_presentes
        
        if not setores_orfãos:
            return None
        
        setor_dom, freq = contagem.most_common(1)[0]
        if freq < 4:
            return None
        
        sn = {
            'Voisins': self.roleta.voisins,
            'Tiers': self.roleta.tiers,
            'Orphelins': self.roleta.orphelins
        }
        
        b = set()
        for setor in setores_orfãos:
            if setor in sn:
                b.update(list(sn[setor])[:5])
        
        if not b:
            return None
        
        forca = 55 + freq * 3
        return {
            'base': set(list(b)[:7]),
            'forca': min(75, forca),
            'estrategias': ['Órfãos Setor'],
            'gatilho': f'Setor órfão: {setores_orfãos}'
        }

class EstrategiaZeroCiclo:
    """✅ CORREÇÃO ERRO TIPO 5: Zero aparece a cada 20-30 giros"""
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 15:
            return None
        
        giros_sem_zero = 0
        for n in reversed(h):
            if n == 0:
                break
            giros_sem_zero += 1
        
        if giros_sem_zero < 20:
            return None
        
        b = set([0])
        b.update(self.roleta.get_vizinhos(0, 2)[:4])
        b.update(list(self.roleta.voisins)[:4])
        
        forca = 50 + min(30, (giros_sem_zero - 20) * 2)
        return {
            'base': set(list(b)[:7]),
            'forca': min(80, forca),
            'estrategias': ['Zero Ciclo'],
            'gatilho': f'Zero ausente {giros_sem_zero}g'
        }

# =============================
# 🆕 MOTOR DE CONFLUÊNCIA - DÚZIAS & COLUNAS
# =============================

class MotorConfluenciaDuziasColunas:
    """
    Motor de Confluência para Dúzias e Colunas
    Avalia 4 estratégias simultâneas e gera um Score System
    Estratégia 1: Interseção Quente (Coluna + Dúzia) = +1 ponto
    Estratégia 2: Força de Terminais Dinâmicos = +1 ponto
    Estratégia 3: Leitura do Cilindro (Setor da Roda) = +1 ponto
    Estratégia 4: Detector de Alternância (Ping-Pong) = -1 ponto
    """
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar_confluencia(self, historico_numeros):
        """
        Analisa os últimos 20 giros e retorna a confluência de sinais
        """
        janela = 20
        if len(historico_numeros) < janela:
            return None
        
        validos = [n for n in historico_numeros[-janela:] if n != 0]
        if len(validos) < 10:
            return None
        
        # Arrays base
        colunas = [get_coluna_real(n) for n in validos]
        duzias = [get_duzia_real(n) for n in validos]
        terminais = [n % 10 for n in validos]
        setores = [get_setor_roda(n) for n in validos]
        
        # Placar de pontuação para as Colunas (1, 2 e 3)
        score_colunas = {1: 0, 2: 0, 3: 0}
        sinais_detectados = []
        detalhes_estrategias = {}
        
        # ---------------------------------------------------------
        # ESTRATÉGIA 1: Interseção Quente (Coluna + Dúzia)
        # ---------------------------------------------------------
        col_quente = Counter(colunas).most_common(1)[0][0]
        duz_quente = Counter(duzias).most_common(1)[0][0]
        
        score_colunas[col_quente] += 1
        detalhes_estrategias['intersecao'] = {
            'coluna': col_quente,
            'duzia': duz_quente,
            'pontos': 1
        }
        
        # ---------------------------------------------------------
        # ESTRATÉGIA 2: Terminais Dinâmicos da Janela
        # ---------------------------------------------------------
        top_terminais = [t[0] for t in Counter(terminais).most_common(3)]
        cols_dos_terminais = [get_coluna_real(t) if t != 0 else 0 for t in top_terminais]
        
        if cols_dos_terminais and any(c != 0 for c in cols_dos_terminais):
            col_terminal_dominante = Counter([c for c in cols_dos_terminais if c != 0]).most_common(1)[0][0]
            score_colunas[col_terminal_dominante] += 1
            sinais_detectados.append(f"Terminais puxam a Coluna {col_terminal_dominante}")
            detalhes_estrategias['terminais'] = {
                'coluna': col_terminal_dominante,
                'terminais': top_terminais,
                'pontos': 1
            }
        
        # ---------------------------------------------------------
        # ESTRATÉGIA 3: Ciclo Físico de Quadrantes (Roda)
        # ---------------------------------------------------------
        setor_quente = Counter(setores).most_common(1)[0][0]
        num_do_setor_quente = [n for n in validos if get_setor_roda(n) == setor_quente]
        cols_do_setor = [get_coluna_real(n) for n in num_do_setor_quente]
        
        if cols_do_setor:
            col_dominante_setor = Counter(cols_do_setor).most_common(1)[0][0]
            if col_dominante_setor != 0:
                score_colunas[col_dominante_setor] += 1
                detalhes_estrategias['cilindro'] = {
                    'coluna': col_dominante_setor,
                    'setor': setor_quente,
                    'pontos': 1
                }
        
        # ---------------------------------------------------------
        # ESTRATÉGIA 4: Detector de Alternância (Ping-Pong)
        # ---------------------------------------------------------
        ultimas_5_cols = colunas[-5:]
        tem_repeticao = any(ultimas_5_cols[i] == ultimas_5_cols[i+1] for i in range(len(ultimas_5_cols)-1))
        
        if not tem_repeticao and len(ultimas_5_cols) >= 5:
            # Padrão Ping-Pong: penaliza a última coluna que saiu
            ultima_col = colunas[-1]
            score_colunas[ultima_col] -= 1
            detalhes_estrategias['pingpong'] = {
                'penalizada': ultima_col,
                'pontos': -1,
                'padrao': 'Ping-Pong Detectado'
            }
        else:
            detalhes_estrategias['pingpong'] = {
                'pontos': 0,
                'padrao': 'Fluxo Normal'
            }
        
        # Encontra a coluna vencedora
        coluna_vencedora = max(score_colunas, key=score_colunas.get)
        pontos = score_colunas[coluna_vencedora]
        
        # Determina os números da coluna vencedora
        coluna_map = {
            1: self.roleta.coluna1,
            2: self.roleta.coluna2,
            3: self.roleta.coluna3
        }
        
        numeros_coluna = coluna_map.get(coluna_vencedora, set())
        
        # Filtra números que saíram recentemente (quentes) e não saíram (frios)
        numeros_recentes = set(validos[-5:])
        numeros_quentes = numeros_coluna.intersection(numeros_recentes)
        numeros_frios = numeros_coluna - numeros_recentes
        
        # Combina: prioridade para quentes, completa com frios
        numeros_apostar = list(numeros_quentes)[:4] + list(numeros_frios)[:3]
        
        # Se ainda tem espaço, completa com mais números da coluna
        if len(numeros_apostar) < 6:
            restantes = [n for n in numeros_coluna if n not in numeros_apostar]
            numeros_apostar.extend(restantes[:6 - len(numeros_apostar)])
        
        # Determina força baseada nos pontos
        if pontos >= 3:
            forca = 75
            qualidade = "EXCELENTE"
            mensagem = "ENTRADA FORTE"
        elif pontos == 2:
            forca = 60
            qualidade = "BOA"
            mensagem = "ENTRADA MODERADA"
        elif pontos == 1:
            forca = 45
            qualidade = "REGULAR"
            mensagem = "ENTRADA FRACA"
        else:
            forca = 30
            qualidade = "RUIM"
            mensagem = "SEM PADRÃO CLARO"
        
        return {
            'coluna_vencedora': coluna_vencedora,
            'pontos': pontos,
            'score_colunas': score_colunas,
            'forca': forca,
            'qualidade': qualidade,
            'mensagem': mensagem,
            'numeros_apostar': sorted(numeros_apostar[:7]),
            'detalhes': detalhes_estrategias,
            'sinais': sinais_detectados
        }

# =============================
# BOT UNIFICADO (35 ESTRATÉGIAS + MOTOR DE CONFLUÊNCIA)
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        
        # 18 originais
        self.sniper_elite = EstrategiaSniperElite(self.roleta)
        self.lucky_vizinhos = EstrategiaLuckyVizinhos(self.roleta)
        self.repeticao = EstrategiaRepeticao(self.roleta)
        self.gap_curto = EstrategiaGapCurto(self.roleta)
        self.mineracao = EstrategiaMineracao()
        self.duzia_dom = EstrategiaDuziaDominante()
        self.espelho = EstrategiaEspelho(self.roleta)
        self.soma_cinco = EstrategiaSomaCinco(self.roleta)
        self.lucky_alto = EstrategiaLuckyAlto(self.roleta)
        self.ciclo_oito = EstrategiaCicloOito(self.roleta)
        self.alternancia_cor = EstrategiaAlternanciaCor(self.roleta)
        self.setor_cilindro = EstrategiaSetorCilindro(self.roleta)
        self.zero_virada = EstrategiaZeroVirada(self.roleta)
        self.primos = EstrategiaPrimos(self.roleta)
        self.vizinhos_fisicos = EstrategiaVizinhosFisicos(self.roleta)
        self.lucky_terminal = EstrategiaLuckyTerminal(self.roleta)
        self.faixa_numerica = EstrategiaFaixaNumerica(self.roleta)
        self.numero_do_dia = EstrategiaNumeroDoDia(self.roleta)
        
        # 6 da primeira análise
        self.confirmacao_lucky = EstrategiaConfirmacaoLucky(self.roleta)
        self.pendulo = EstrategiaPendulo(self.roleta)
        self.quente_frio = EstrategiaQuenteFrio(self.roleta)
        self.confirmacao_dupla = EstrategiaConfirmacaoDupla()
        self.colunas_alternadas = EstrategiaColunasAlternadas(self.roleta)
        self.lucky_setor = EstrategiaLuckySetor(self.roleta)
        
        # 6 da segunda análise
        self.lucky_cascata = EstrategiaLuckyCascata(self.roleta)
        self.ressaca_lucky = EstrategiaRessacaLucky(self.roleta)
        self.espelho_temporal = EstrategiaEspelhoTemporal(self.roleta)
        self.esgotamento_coluna = EstrategiaEsgotamentoColuna(self.roleta)
        self.micro_ciclo3 = EstrategiaMicroCiclo3(self.roleta)
        self.setor_ritmado = EstrategiaSetorRitmado(self.roleta)
        
        # 5 novas corretivas
        self.lucky_imediato = EstrategiaLuckyImediato(self.roleta)
        self.lucky_recente_nao_saiu = EstrategiaLuckyRecenteNaoSaiu(self.roleta)
        self.espelho_lucky = EstrategiaEspelhoLucky(self.roleta)
        self.orfaos_setor = EstrategiaOrfaosSetor(self.roleta)
        self.zero_ciclo = EstrategiaZeroCiclo(self.roleta)
        
        # 🆕 Motor de Confluência para Dúzias e Colunas
        self.motor_confluencia = MotorConfluenciaDuziasColunas(self.roleta)
        
        self.historico = []
        self.lucky = []
        self.mults = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
    
    def atualizar(self, n, lucky_nums=None, lucky_mults=None):
        if isinstance(n, dict):
            n = n.get('number', 0)
        self.historico.append(int(n))
        self.lucky.append(lucky_nums if lucky_nums else [])
        self.mults.append(lucky_mults if lucky_mults else {})
        if len(self.historico) > 200:
            self.historico = self.historico[-200:]
        if len(self.lucky) > 200:
            self.lucky = self.lucky[-200:]
        if len(self.mults) > 200:
            self.mults = self.mults[-200:]
    
    def gerar_entrada(self, motores=None, forcar_inversao=False, entradas_hist=None):
        # Verifica se está no modo dúzias e colunas
        if st.session_state.get('modo_duzias_colunas', False):
            confluencia = self.motor_confluencia.analisar_confluencia(list(self.historico))
            if confluencia and confluencia['pontos'] >= 1:
                return {
                    'numeros_apostar': confluencia['numeros_apostar'],
                    'forca_real': confluencia['forca'],
                    'motor': f"Confluência Col{confluencia['coluna_vencedora']}",
                    'estrategias_ativas': [f"Score: {confluencia['pontos']}/4"],
                    'qtd_motores': confluencia['pontos'],
                    'qualidade': confluencia['qualidade'],
                    'gatilho': confluencia['mensagem'],
                    'invertido': False
                }
            return None
        
        # Código original de geração de entrada
        if motores is None:
            motores = {k: True for k in [
                'sniper_elite', 'lucky_vizinhos', 'repeticao', 'gap_curto', 'mineracao', 'duzia_dom',
                'espelho', 'soma_cinco', 'lucky_alto', 'ciclo_oito', 'alternancia_cor',
                'setor_cilindro', 'zero_virada', 'primos', 'vizinhos_fisicos', 'lucky_terminal',
                'faixa_numerica', 'numero_do_dia',
                'confirmacao_lucky', 'pendulo', 'quente_frio', 'colunas_alternadas', 'lucky_setor',
                'lucky_cascata', 'ressaca_lucky', 'espelho_temporal', 'esgotamento_coluna',
                'micro_ciclo3', 'setor_ritmado',
                'lucky_imediato', 'lucky_recente_nao_saiu', 'espelho_lucky', 'orfaos_setor', 'zero_ciclo'
            ]}
        
        resultados = []
        forca_min = st.session_state.get('forca_minima_entrada', 55)
        
        ests = [
            # PESO 4 - Estratégias de altíssima confiabilidade
            (self.lucky_imediato, 'Lucky Imediato', 4, [list(self.historico), self.lucky]),
            (self.repeticao, 'Repetição', 4, [list(self.historico)]),
            
            # PESO 3 - Estratégias de alta confiabilidade
            (self.lucky_recente_nao_saiu, 'Lucky Recente', 3, [list(self.historico), self.lucky]),
            (self.lucky_vizinhos, 'Lucky Vizinhos', 3, [list(self.historico), self.lucky]),
            (self.vizinhos_fisicos, 'Vizinhos Físicos', 3, [list(self.historico)]),
            (self.confirmacao_lucky, 'Confirm. Lucky', 3, [list(self.historico), self.lucky]),
            (self.lucky_cascata, 'Lucky Cascata', 3, [list(self.historico), self.lucky]),
            (self.lucky_setor, 'Lucky Setor', 3, [list(self.historico), self.lucky]),
            
            # PESO 2 - Estratégias de média-alta confiabilidade
            (self.espelho_lucky, 'Espelho Lucky', 2, [list(self.historico), self.lucky]),
            (self.orfaos_setor, 'Órfãos Setor', 2, [list(self.historico)]),
            (self.sniper_elite, 'Sniper Elite', 2, [list(self.historico), self.lucky]),
            (self.gap_curto, 'Gap Curto', 2, [list(self.historico)]),
            (self.espelho, 'Espelho', 2, [list(self.historico)]),
            (self.lucky_alto, 'Lucky Alto', 2, [list(self.historico), self.lucky, self.mults]),
            (self.numero_do_dia, 'Nº do Dia', 2, [list(self.historico)]),
            (self.pendulo, 'Pêndulo', 2, [list(self.historico)]),
            (self.ressaca_lucky, 'Ressaca Lucky', 2, [list(self.historico), self.lucky, entradas_hist]),
            (self.esgotamento_coluna, 'Esgot. Coluna', 2, [list(self.historico)]),
            (self.setor_ritmado, 'Setor Ritmado', 2, [list(self.historico)]),
            
            # PESO 1 - Estratégias complementares
            (self.zero_ciclo, 'Zero Ciclo', 1, [list(self.historico)]),
            (self.mineracao, 'Mineração', 1, [list(self.historico)]),
            (self.duzia_dom, 'Dúzia Dom.', 1, [list(self.historico)]),
            (self.soma_cinco, 'Soma Cinco', 1, [list(self.historico)]),
            (self.ciclo_oito, 'Ciclo Oito', 1, [list(self.historico)]),
            (self.alternancia_cor, 'Alternância', 1, [list(self.historico)]),
            (self.setor_cilindro, 'Setor Cilindro', 1, [list(self.historico)]),
            (self.zero_virada, 'Zero Virada', 1, [list(self.historico)]),
            (self.primos, 'Primos', 1, [list(self.historico)]),
            (self.lucky_terminal, 'Lucky Terminal', 1, [list(self.historico), self.lucky]),
            (self.faixa_numerica, 'Faixa Numérica', 1, [list(self.historico)]),
            (self.quente_frio, 'Quente/Frio', 1, [list(self.historico), self.lucky]),
            (self.colunas_alternadas, 'Colunas Alt.', 1, [list(self.historico)]),
            (self.espelho_temporal, 'Espelho Temp.', 1, [list(self.historico), self.lucky]),
            (self.micro_ciclo3, 'Micro Ciclo 3', 1, [list(self.historico)]),
        ]
        
        for est, nome, peso, args in ests:
            try:
                key = nome.lower().replace(' ','_').replace('º','').replace('ú','u').replace('ã','a').replace('ç','c').replace('ó','o').replace('ô','o').replace('.','').replace('/','_').replace('ê','e')
                if motores.get(key, True) and len(self.historico) >= 1:
                    r = est.analisar(*args)
                    if r and len(r.get('base', set())) >= 1 and r['forca'] >= forca_min:
                        resultados.append((nome, r, peso))
            except:
                pass
        
        # Meta-estratégia: Confirmação Dupla
        if len(resultados) >= 2:
            contagem_numeros = Counter()
            for _, r, peso in resultados:
                for n in r['base']:
                    contagem_numeros[n] += peso
            
            confirmados = [n for n, c in contagem_numeros.items() if c >= 5]
            if confirmados:
                resultados.append(('Conf. Dupla', {
                    'base': set(confirmados[:5]),
                    'forca': 65 + len(confirmados) * 2,
                    'estrategias': ['Conf. Dupla'],
                    'gatilho': f'Confirmados: {confirmados[:3]}'
                }, 2))
        
        if not resultados:
            return None
        
        base = set()
        ests_ativas = []
        gatilhos = []
        ft, mp, mf = 0, resultados[0][0], 0
        
        for nome, r, peso in resultados:
            for _ in range(peso):
                base.update(r['base'])
            ests_ativas.extend(r.get('estrategias', []))
            if 'gatilho' in r:
                gatilhos.append(r['gatilho'])
            ft += r['forca'] * peso
            if r['forca'] > mf:
                mf, mp = r['forca'], nome
        
        fm = int(ft / sum(p for _, _, p in resultados))
        mx = st.session_state.get('max_n_apostas', 7)
        mn = st.session_state.get('min_n_apostas', 4)
        
        consenso = Counter()
        for nome, r, peso in resultados:
            for n in r['base']:
                consenso[n] += peso
        
        lst = [n for n, _ in consenso.most_common(mx)]
        
        # Filtros anti-erro
        if st.session_state.get('limitar_numeros_altos', True):
            prob = [n for n in lst if n in self.roleta.numeros_problematicos]
            if len(prob) > self.roleta.max_problematicos:
                for p in prob[self.roleta.max_problematicos:]:
                    if p in lst and len(lst) > mn:
                        lst.remove(p)
        
        if st.session_state.get('evitar_zero', True):
            if 0 in lst and 'Zero' not in ' '.join(gatilhos) and len(lst) > mn:
                lst.remove(0)
        
        max_gat = st.session_state.get('max_gatilhos', 2)
        if len(gatilhos) > max_gat:
            gatilhos = gatilhos[:max_gat]
        
        altos = [n for n in lst if n >= 25]
        if len(altos) > 3 and len(lst) > mn:
            for a in altos[3:]:
                if a in lst:
                    lst.remove(a)
        
        while len(lst) < mn and len(lst) < 37:
            for n in range(37):
                if n not in lst:
                    lst.append(n)
                    break
        
        qs = fm / max(1, len(lst))
        q = "EXCELENTE" if qs >= 12 else "BOA" if qs >= 8 else "REGULAR"
        
        entrada = {
            'numeros_apostar': sorted(lst),
            'forca_real': min(100, max(30, fm)),
            'motor': mp,
            'estrategias_ativas': list(set(ests_ativas))[:4],
            'qtd_motores': len(resultados),
            'qualidade': q,
            'gatilho': ' | '.join(gatilhos[:2]),
            'invertido': False
        }
        
        if forcar_inversao:
            entrada = self._inverter_entrada(entrada)
        
        return entrada
    
    def _inverter_entrada(self, entrada):
        numeros_originais = set(entrada['numeros_apostar'])
        todos_numeros = set(range(37))
        numeros_invertidos = list(todos_numeros - numeros_originais)
        
        qtd = len(entrada['numeros_apostar'])
        
        nao_problematicos = [n for n in numeros_invertidos if n not in {0, 32, 33, 34, 35}]
        problematicos = [n for n in numeros_invertidos if n in {0, 32, 33, 34, 35}]
        
        random.shuffle(nao_problematicos)
        random.shuffle(problematicos)
        
        final = nao_problematicos[:qtd]
        if len(final) < qtd:
            final.extend(problematicos[:qtd - len(final)])
        
        entrada['numeros_apostar'] = sorted(final[:qtd])
        entrada['motor'] = f"🔄 {entrada['motor']} (Inv)"
        entrada['estrategias_ativas'] = ['🔄 INVERSÃO AUTO'] + entrada['estrategias_ativas'][:3]
        entrada['invertido'] = True
        entrada['gatilho'] = f"🔄 INV: {entrada['gatilho']}"
        
        return entrada

# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaBot:
    def __init__(self):
        self.bot = RoletaBotUnificado()
        self.historico_numeros = deque(maxlen=200)
        self.historico_lucky = deque(maxlen=100)
        self.historico_mults = deque(maxlen=100)
        self.entrada_ativa = None
        self.historico_entradas = []
        self.acertos = 0
        self.erros = 0
        self.estado_inversao = False
    
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data['number']
            lucky = numero_data.get('luckyNumbers', [])
            lucky_mults = numero_data.get('luckyMultipliers', {})
            mult = lucky_mults.get(nr) if nr in lucky else None
            is_lucky = nr in lucky
        else:
            nr = int(numero_data)
            lucky, lucky_mults, mult, is_lucky = [], {}, None, False
        
        self.bot.atualizar(nr, lucky, lucky_mults)
        self.historico_numeros.append(nr)
        self.historico_lucky.append(lucky)
        self.historico_mults.append(lucky_mults)
        
        if self.entrada_ativa:
            acerto = nr in self.entrada_ativa.get('numeros_apostar', [])
            if acerto:
                self.acertos += 1
                self.bot.performance['acertos'] += 1
            else:
                self.erros += 1
                self.bot.performance['erros'] += 1
            self.bot.performance['historico'].append(1 if acerto else 0)
            
            entrada_info = {
                'rodada': len(self.historico_numeros)-1,
                'hora': datetime.now().strftime('%H:%M:%S'),
                'numeros': self.entrada_ativa.get('numeros_apostar', []),
                'resultado': nr,
                'acerto': acerto,
                'forca': self.entrada_ativa.get('forca_real', 0),
                'motor': self.entrada_ativa.get('motor', ''),
                'gatilho': self.entrada_ativa.get('gatilho', ''),
                'estrategias': self.entrada_ativa.get('estrategias_ativas', []),
                'qualidade': self.entrada_ativa.get('qualidade', ''),
                'lucky': is_lucky,
                'multiplicador': mult,
                'invertido': self.entrada_ativa.get('invertido', False),
            }
            self.historico_entradas.append(entrada_info)
            if len(self.historico_entradas) > 50:
                self.historico_entradas = self.historico_entradas[-50:]
            
            if st.session_state.get('modo_inversao_auto', False):
                if not acerto:
                    self.estado_inversao = not self.estado_inversao
            
            enviar_resultado_auto(nr, acerto, is_lucky)
            self.entrada_ativa = None
        
        mot = {k: st.session_state.get(f'usar_{k}', True) for k in [
            'sniper_elite', 'lucky_vizinhos', 'repeticao', 'gap_curto', 'mineracao', 'duzia_dom',
            'espelho', 'soma_cinco', 'lucky_alto', 'ciclo_oito', 'alternancia_cor',
            'setor_cilindro', 'zero_virada', 'primos', 'vizinhos_fisicos', 'lucky_terminal',
            'faixa_numerica', 'numero_do_dia',
            'confirmacao_lucky', 'pendulo', 'quente_frio', 'colunas_alternadas', 'lucky_setor',
            'lucky_cascata', 'ressaca_lucky', 'espelho_temporal', 'esgotamento_coluna',
            'micro_ciclo3', 'setor_ritmado',
            'lucky_imediato', 'lucky_recente_nao_saiu', 'espelho_lucky', 'orfaos_setor', 'zero_ciclo'
        ]}
        
        forcar_inversao = st.session_state.get('modo_inversao_auto', False) and self.estado_inversao
        
        self.entrada_ativa = self.bot.gerar_entrada(mot, forcar_inversao, list(self.historico_entradas))
        if self.entrada_ativa:
            enviar_previsao_auto(self.entrada_ativa)
    
    def zerar(self):
        self.acertos = 0
        self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear()
        self.historico_lucky.clear()
        self.historico_mults.clear()
        self.entrada_ativa = None
        self.estado_inversao = False
        self.bot.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.bot.historico = []
        self.bot.lucky = []
        self.bot.mults = []
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
        
        return {
            "number": nm,
            "timestamp": ts,
            "luckyNumbers": ln,
            "luckyMultipliers": lm
        }
    except Exception as e:
        logging.warning(f"Erro ao buscar API da Roleta: {e}")
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
st.set_page_config(page_title="🎯 Roleta Bot Pro v20 - Motor de Confluência", layout="centered")
st.title("🎯 Roleta Bot Pro v20 - Motor de Confluência Dúzias & Colunas")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    if not st.session_state.get('historico'):
        st.session_state.historico = dados.get('historico', [])
    
    sis = st.session_state.sistema
    sis.bot = RoletaBotUnificado()
    sis.historico_numeros.clear()
    sis.historico_lucky.clear()
    sis.historico_mults.clear()
    
    numeros = dados.get('historico_numeros', [])
    lucky = dados.get('historico_lucky', [])
    mults = dados.get('historico_mults', [])
    
    for i in range(len(numeros)):
        n = numeros[i]
        l = lucky[i] if i < len(lucky) else []
        m = mults[i] if i < len(mults) else {}
        sis.bot.atualizar(n, l, m)
        sis.historico_numeros.append(n)
        sis.historico_lucky.append(l)
        sis.historico_mults.append(m)
    
    sis.acertos = dados.get('sistema_acertos', 0)
    sis.erros = dados.get('sistema_erros', 0)
    sis.estado_inversao = dados.get('estado_inversao', False)
    sis.entrada_ativa = dados.get('entrada_ativa', None)
    
    if os.path.exists(PERFORMANCE_PATH):
        try:
            with open(PERFORMANCE_PATH, 'r') as f:
                p = json.load(f)
                sis.bot.performance = {
                    'acertos': p.get('acertos', 0),
                    'erros': p.get('erros', 0),
                    'historico': p.get('historico', [])
                }
        except:
            pass
    
    if os.path.exists(ENTRADAS_PATH):
        try:
            with open(ENTRADAS_PATH, 'r') as f:
                sis.historico_entradas = json.load(f)
        except:
            pass

# Configurações padrão
defaults = {k: True for k in [
    'modo_automatico', 'usar_sniper_elite', 'usar_lucky_vizinhos', 'usar_repeticao',
    'usar_gap_curto', 'usar_mineracao', 'usar_duzia_dom', 'usar_espelho', 'usar_soma_cinco',
    'usar_lucky_alto', 'usar_ciclo_oito', 'usar_alternancia_cor', 'usar_setor_cilindro',
    'usar_zero_virada', 'usar_primos', 'usar_vizinhos_fisicos', 'usar_lucky_terminal',
    'usar_faixa_numerica', 'usar_numero_do_dia', 'limitar_numeros_altos', 'evitar_zero',
    'usar_confirmacao_lucky', 'usar_pendulo', 'usar_quente_frio',
    'usar_colunas_alternadas', 'usar_lucky_setor',
    'usar_lucky_cascata', 'usar_ressaca_lucky', 'usar_espelho_temporal',
    'usar_esgotamento_coluna', 'usar_micro_ciclo3', 'usar_setor_ritmado',
    'usar_lucky_imediato', 'usar_lucky_recente_nao_saiu', 'usar_espelho_lucky',
    'usar_orfaos_setor', 'usar_zero_ciclo'
]}
defaults.update({
    'max_n_apostas': 7,
    'min_n_apostas': 4,
    'forca_minima_entrada': 55,
    'max_gatilhos': 2,
    'modo_inversao_auto': False,
    'modo_duzias_colunas': False
})

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

# Sidebar
with st.sidebar:
    st.subheader("⚙️ Config")
    
    # 🆕 CHECKBOX DO MODO DÚZIAS E COLUNAS
    st.markdown("---")
    st.markdown("### 📐 MODO DE OPERAÇÃO")
    st.session_state.modo_duzias_colunas = st.checkbox(
        "🎯 ATIVAR MODO CONFLUÊNCIA (Dúzias & Colunas)",
        value=st.session_state.modo_duzias_colunas,
        help="Quando ativado, o bot usa o Motor de Confluência com 4 estratégias simultâneas para Dúzias e Colunas"
    )
    
    if st.session_state.modo_duzias_colunas:
        st.success("""
        ✅ **MOTOR DE CONFLUÊNCIA ATIVO**
        
        **4 Estratégias Simultâneas:**
        1. 🔥 Interseção Quente (Coluna + Dúzia)
        2. 🎯 Força de Terminais Dinâmicos
        3. 🎡 Leitura do Cilindro (Setor da Roda)
        4. 🏓 Detector de Ping-Pong
        
        **Score System:**
        - 3-4 pontos = ENTRADA FORTE 🔥
        - 2 pontos = ENTRADA MODERADA ⚠️
        - 0-1 pontos = SEM PADRÃO 🛑
        """)
        st.info("💡 As 35 estratégias estão temporariamente desativadas.")
    else:
        st.info("📊 Modo padrão: 35 estratégias ativas")
    
    st.markdown("---")
    
    with st.expander("🔄 Inversão Automática", expanded=True):
        st.session_state.modo_inversao_auto = st.checkbox(
            "🔄 ATIVAR INVERSÃO AUTOMÁTICA",
            value=st.session_state.modo_inversao_auto,
            help="✅ Acertou → Mantém | ❌ Errou → Inverte (Normal↔Invertido)"
        )
        if st.session_state.modo_inversao_auto:
            estado = "🔄 INVERTIDO" if st.session_state.sistema.estado_inversao else "📊 NORMAL"
            st.warning(f"""
            **INVERSÃO ATIVA | Estado: {estado}**
            
            ✅ Acertou → Mantém estado
            ❌ Errou → Inverte (Normal↔Invertido)
            """)
        else:
            st.info("🔄 Inversão DESATIVADA")
    
    st.session_state.forca_minima_entrada = st.slider(
        "⚡ Força Mínima",
        45, 65,
        st.session_state.forca_minima_entrada,
        5
    )
    st.session_state.max_n_apostas = st.slider(
        "📊 Máx. números",
        12, 18,
        st.session_state.max_n_apostas
    )
    
    # Só mostra as estratégias quando NÃO está no modo confluência
    if not st.session_state.modo_duzias_colunas:
        with st.expander("🛡️ Filtros", expanded=False):
            st.session_state.limitar_numeros_altos = st.checkbox(
                "Limitar 0,32,33,34,35",
                value=st.session_state.limitar_numeros_altos
            )
            st.session_state.evitar_zero = st.checkbox(
                "Evitar Zero",
                value=st.session_state.evitar_zero
            )
        
        with st.expander("🤖 35 Estratégias", expanded=False):
            st.markdown("**🆕 CORRETIVAS (Análise de Erros)**")
            st.session_state.usar_lucky_imediato = st.checkbox(
                "⚡ Lucky Imediato (4x)", 
                value=st.session_state.usar_lucky_imediato,
                help="Lucky do giro atual - 35% dos erros"
            )
            st.session_state.usar_lucky_recente_nao_saiu = st.checkbox(
                "🍀 Lucky Recente (3x)", 
                value=st.session_state.usar_lucky_recente_nao_saiu,
                help="Lucky 3 giros que não saiu - 25% dos erros"
            )
            st.session_state.usar_espelho_lucky = st.checkbox(
                "🪞 Espelho Lucky (2x)", 
                value=st.session_state.usar_espelho_lucky,
                help="Espelhos de lucky - 20% dos erros"
            )
            st.session_state.usar_orfaos_setor = st.checkbox(
                "🎯 Órfãos Setor (2x)", 
                value=st.session_state.usar_orfaos_setor,
                help="Setor órfão quando domina 4+ giros - 15% dos erros"
            )
            st.session_state.usar_zero_ciclo = st.checkbox(
                "0️⃣ Zero Ciclo", 
                value=st.session_state.usar_zero_ciclo,
                help="Zero a cada 20-30 giros - 5% dos erros"
            )
            
            st.markdown("---")
            st.markdown("**2ª Análise (6 estratégias)**")
            st.session_state.usar_lucky_cascata = st.checkbox("🌊 Lucky Cascata (3x)", value=st.session_state.usar_lucky_cascata)
            st.session_state.usar_ressaca_lucky = st.checkbox("🍀🔄 Ressaca Lucky (2x)", value=st.session_state.usar_ressaca_lucky)
            st.session_state.usar_espelho_temporal = st.checkbox("⏰ Espelho Temporal", value=st.session_state.usar_espelho_temporal)
            st.session_state.usar_esgotamento_coluna = st.checkbox("📊 Esgot. Coluna (2x)", value=st.session_state.usar_esgotamento_coluna)
            st.session_state.usar_micro_ciclo3 = st.checkbox("🔄 Micro Ciclo 3", value=st.session_state.usar_micro_ciclo3)
            st.session_state.usar_setor_ritmado = st.checkbox("🎯 Setor Ritmado (2x)", value=st.session_state.usar_setor_ritmado)
            
            st.markdown("---")
            st.markdown("**1ª Análise (6 estratégias)**")
            st.session_state.usar_confirmacao_lucky = st.checkbox("🍀 Confirm. Lucky (3x)", value=st.session_state.usar_confirmacao_lucky)
            st.session_state.usar_lucky_setor = st.checkbox("🎯 Lucky Setor (3x)", value=st.session_state.usar_lucky_setor)
            st.session_state.usar_pendulo = st.checkbox("⏳ Pêndulo (2x)", value=st.session_state.usar_pendulo)
            st.session_state.usar_quente_frio = st.checkbox("🌡️ Quente/Frio", value=st.session_state.usar_quente_frio)
            st.session_state.usar_colunas_alternadas = st.checkbox("📊 Colunas Alt.", value=st.session_state.usar_colunas_alternadas)
            
            st.markdown("---")
            st.markdown("**Originais (18)**")
            st.session_state.usar_repeticao = st.checkbox("🔄 Repetição (4x)", value=st.session_state.usar_repeticao)
            st.session_state.usar_lucky_vizinhos = st.checkbox("🍀 Lucky Vizinhos (3x)", value=st.session_state.usar_lucky_vizinhos)
            st.session_state.usar_vizinhos_fisicos = st.checkbox("🎰 Vizinhos Físicos (3x)", value=st.session_state.usar_vizinhos_fisicos)
            st.session_state.usar_sniper_elite = st.checkbox("🎯 Sniper Elite", value=st.session_state.usar_sniper_elite)
            st.session_state.usar_gap_curto = st.checkbox("⏭️ Gap Curto", value=st.session_state.usar_gap_curto)
            st.session_state.usar_espelho = st.checkbox("🪞 Espelho", value=st.session_state.usar_espelho)
            st.session_state.usar_lucky_alto = st.checkbox("💎 Lucky Alto", value=st.session_state.usar_lucky_alto)
            st.session_state.usar_numero_do_dia = st.checkbox("🌟 Nº do Dia", value=st.session_state.usar_numero_do_dia)
            st.session_state.usar_mineracao = st.checkbox("⛏️ Mineração", value=st.session_state.usar_mineracao)
            st.session_state.usar_duzia_dom = st.checkbox("📐 Dúzia Dom.", value=st.session_state.usar_duzia_dom)
            st.session_state.usar_soma_cinco = st.checkbox("➕5 Soma Cinco", value=st.session_state.usar_soma_cinco)
            st.session_state.usar_ciclo_oito = st.checkbox("8️⃣ Ciclo Oito", value=st.session_state.usar_ciclo_oito)
            st.session_state.usar_alternancia_cor = st.checkbox("🎨 Alternância", value=st.session_state.usar_alternancia_cor)
            st.session_state.usar_setor_cilindro = st.checkbox("🎡 Setor Cilindro", value=st.session_state.usar_setor_cilindro)
            st.session_state.usar_zero_virada = st.checkbox("0️⃣ Zero Virada", value=st.session_state.usar_zero_virada)
            st.session_state.usar_primos = st.checkbox("🔢 Primos", value=st.session_state.usar_primos)
            st.session_state.usar_lucky_terminal = st.checkbox("🍀🔢 Lucky Terminal", value=st.session_state.usar_lucky_terminal)
            st.session_state.usar_faixa_numerica = st.checkbox("📏 Faixa Numérica", value=st.session_state.usar_faixa_numerica)
    
    st.session_state.modo_automatico = st.checkbox(
        "Modo Automático",
        value=st.session_state.modo_automatico
    )
    
    with st.expander("🔔 Telegram", expanded=False):
        st.session_state.telegram_token = st.text_input(
            "Token",
            value=st.session_state.telegram_token,
            type="password"
        )
        st.session_state.telegram_chat_id = st.text_input(
            "Chat ID",
            value=st.session_state.telegram_chat_id
        )
    
    c1, c2 = st.columns(2)
    c1.button(
        "💾 Salvar",
        on_click=lambda: [salvar_resultado_em_arquivo(st.session_state.historico), salvar_sessao(), st.success("✅")],
        use_container_width=True
    )
    c2.button(
        "🗑️ Zerar",
        on_click=lambda: st.session_state.sistema.zerar() or st.rerun(),
        use_container_width=True
    )

# Conteúdo principal
st.subheader("✍️ Inserir Números")
c1, c2 = st.columns([4, 1])
with c1:
    entrada = st.text_input("Números (0-36):", placeholder="Ex: 12 21 14", key="entrada")
with c2:
    if st.button("➕", use_container_width=True) and entrada:
        try:
            nums = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
            for n in nums:
                item = {
                    "number": n,
                    "timestamp": f"m{len(st.session_state.historico)}",
                    "luckyNumbers": [],
                    "luckyMultipliers": {}
                }
                st.session_state.historico.append(item)
                st.session_state.sistema.processar_novo_numero(item)
            salvar_resultado_em_arquivo(st.session_state.historico)
            salvar_sessao()
            st.success(f"{len(nums)} adicionados!")
            st.rerun()
        except:
            pass

st_autorefresh(interval=3000, key="refresh")

resultado = fetch_latest_result()
if st.session_state.historico:
    ultimo_ts = st.session_state.historico[-1].get("timestamp") if st.session_state.historico else None
else:
    ultimo_ts = None

if resultado and resultado.get("timestamp") and resultado["timestamp"] != ultimo_ts:
    n = resultado.get("number")
    if n is not None:
        st.session_state.historico.append(resultado)
        st.session_state.sistema.processar_novo_numero(resultado)
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()

# Últimos números
st.subheader("🔁 Últimos Números")
if st.session_state.historico:
    ultimos = st.session_state.historico[-10:]
    fmt = []
    for item in ultimos:
        n = item['number'] if isinstance(item, dict) else item
        if isinstance(item, dict) and n in item.get('luckyNumbers', []):
            mult = item.get('luckyMultipliers', {}).get(n, '')
            fmt.append(f"⚡**{n}**({mult}x)" if mult else f"⚡**{n}**")
        else:
            fmt.append(str(n))
    st.write(" | ".join(fmt))

# Status
sis = st.session_state.sistema
st.subheader("📊 Status")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("🟢 Acertos", sis.acertos)
c2.metric("🔴 Erros", sis.erros)
tx = sis.acertos/(sis.acertos+sis.erros)*100 if (sis.acertos+sis.erros) > 0 else 0
c3.metric("📊 Taxa", f"{tx:.0f}%")
c4.metric("Modo", "Confluência" if st.session_state.get('modo_duzias_colunas', False) else "35 Est")
c5.metric("Est Inv", "🔄INV" if sis.estado_inversao else "📊NOR")

# ==========================================
# 🆕 PAINEL DE ANÁLISE COM MOTOR DE CONFLUÊNCIA
# ==========================================
st.subheader("🎯 Painel de Análise")

if st.session_state.get('modo_duzias_colunas', False):
    # Modo Confluência: Motor de 4 estratégias simultâneas
    hist_num = list(sis.historico_numeros)
    janela_analise = 20
    
    st.markdown("### 🧠 Motor Analítico de Confluência")
    
    if len(hist_num) >= janela_analise:
        validos = [n for n in hist_num[-janela_analise:] if n != 0]
        
        if validos:
            # Arrays base
            colunas = [get_coluna_real(n) for n in validos]
            duzias = [get_duzia_real(n) for n in validos]
            terminais = [n % 10 for n in validos]
            setores = [get_setor_roda(n) for n in validos]
            
            # Placar de pontuação para as Colunas (1, 2 e 3)
            score_colunas = {1: 0, 2: 0, 3: 0}
            sinais_detectados = []

            c1, c2 = st.columns(2)

            with c1:
                # ---------------------------------------------------------
                # ESTRATÉGIA 1: Interseção Quente (Coluna + Dúzia)
                # ---------------------------------------------------------
                col_quente = Counter(colunas).most_common(1)[0][0]
                duz_quente = Counter(duzias).most_common(1)[0][0]
                
                st.write("**1. Interseção Básica:**")
                st.info(f"🔥 Coluna {col_quente} + Dúzia {duz_quente}")
                score_colunas[col_quente] += 1
                
                # ---------------------------------------------------------
                # ESTRATÉGIA 2: Terminais Dinâmicos da Janela
                # ---------------------------------------------------------
                top_terminais = [t[0] for t in Counter(terminais).most_common(3)]
                cols_dos_terminais = [get_coluna_real(t) if t != 0 else 0 for t in top_terminais]
                
                if cols_dos_terminais and any(c != 0 for c in cols_dos_terminais):
                    col_terminal_dominante = Counter([c for c in cols_dos_terminais if c != 0]).most_common(1)[0][0]
                    score_colunas[col_terminal_dominante] += 1
                    sinais_detectados.append(f"Terminais puxam a Coluna {col_terminal_dominante}")
                
                st.write("**2. Força de Terminais:**")
                st.success(f"🎯 Terminais Quentes: {top_terminais}")
                if col_terminal_dominante != 0:
                    st.caption(f"→ Puxando Coluna {col_terminal_dominante}")

            with c2:
                # ---------------------------------------------------------
                # ESTRATÉGIA 3: Ciclo Físico de Quadrantes (Roda)
                # ---------------------------------------------------------
                setor_quente = Counter(setores).most_common(1)[0][0]
                num_do_setor_quente = [n for n in validos if get_setor_roda(n) == setor_quente]
                cols_do_setor = [get_coluna_real(n) for n in num_do_setor_quente]
                
                if cols_do_setor:
                    col_dominante_setor = Counter(cols_do_setor).most_common(1)[0][0]
                    if col_dominante_setor != 0:
                        score_colunas[col_dominante_setor] += 1
                
                st.write("**3. Leitura do Cilindro:**")
                st.warning(f"🎡 Setor dominando: {setor_quente}")
                if col_dominante_setor != 0:
                    st.caption(f"→ Coluna {col_dominante_setor} domina este setor")

                # ---------------------------------------------------------
                # ESTRATÉGIA 4: Detector de Alternância (Ping-Pong)
                # ---------------------------------------------------------
                ultimas_5_cols = colunas[-5:]
                tem_repeticao = any(ultimas_5_cols[i] == ultimas_5_cols[i+1] for i in range(len(ultimas_5_cols)-1))
                
                st.write("**4. Comportamento da Mesa:**")
                if not tem_repeticao and len(ultimas_5_cols) >= 5:
                    st.error("🏓 Padrão Ping-Pong Detectado! (Evite repetições)")
                    ultima_col = colunas[-1]
                    score_colunas[ultima_col] -= 1
                    st.caption(f"→ Penalizando Coluna {ultima_col}")
                else:
                    st.write("🌊 Fluxo Normal (Aceita repetições)")

            # ==========================================
            # VEREDITO FINAL DO BOT
            # ==========================================
            st.markdown("---")
            st.markdown("### 🤖 Veredito do Algoritmo")
            
            coluna_vencedora = max(score_colunas, key=score_colunas.get)
            pontos = score_colunas[coluna_vencedora]
            
            if pontos >= 3:
                st.success(f"### 🎯 ENTRADA FORTE: Coluna {coluna_vencedora} ({pontos}/4 confirmações)")
            elif pontos == 2:
                st.warning(f"### ⚠️ ENTRADA MODERADA: Coluna {coluna_vencedora} ({pontos}/4 confirmações)")
            elif pontos == 1:
                st.info(f"### 💡 ENTRADA FRACA: Coluna {coluna_vencedora} ({pontos}/4 confirmações)")
            else:
                st.error("### 🛑 SEM PADRÃO CLARO: Fique de fora. Mercado confuso.")
            
            st.caption(f"Placar Interno: Col 1 ({score_colunas[1]} pts) | Col 2 ({score_colunas[2]} pts) | Col 3 ({score_colunas[3]} pts)")
            
            # Mostra números sugeridos da coluna vencedora
            if pontos >= 1:
                coluna_map = {
                    1: sis.bot.roleta.coluna1,
                    2: sis.bot.roleta.coluna2,
                    3: sis.bot.roleta.coluna3
                }
                numeros_coluna = coluna_map.get(coluna_vencedora, set())
                numeros_recentes = set(validos[-5:])
                numeros_quentes = numeros_coluna.intersection(numeros_recentes)
                numeros_frios = numeros_coluna - numeros_recentes
                
                st.markdown("**🎲 Números da Coluna:**")
                if numeros_quentes:
                    st.success(f"🔥 Quentes: {sorted(numeros_quentes)}")
                if numeros_frios:
                    st.info(f"❄️ Frios: {sorted(list(numeros_frios)[:5])}")
    else:
        st.info(f"⏳ Coletando dados... ({len(hist_num)}/{janela_analise} giros na janela de análise).")
    
    # Mostra a entrada ativa do motor de confluência
    st.markdown("---")
    st.subheader("🎯 Entrada Atual (Modo Confluência)")
    if sis.entrada_ativa:
        e = sis.entrada_ativa
        if e.get('invertido'):
            st.warning(f"### 🔄 INVERTIDA | {e['motor']} | {e['forca_real']}% | {len(e['numeros_apostar'])}n")
        else:
            emoji = "🔥" if e['forca_real'] >= 65 else "🎯" if e['forca_real'] >= 55 else "📊"
            st.info(f"### {emoji} {e['motor']} | {e['forca_real']}% | {len(e['numeros_apostar'])}n")
        if e.get('gatilho'):
            st.caption(f"🎯 {e['gatilho']}")
        st.markdown(f"## {', '.join(map(str, sorted(e['numeros_apostar'])))}")
    else:
        st.info("🔍 Analisando padrões de confluência...")

else:
    # Modo padrão com duas abas
    tab_geral, tab_duz_col = st.tabs(["📊 Visão Geral", "📐 Dúzias & Colunas"])
    
    with tab_geral:
        if sis.entrada_ativa:
            e = sis.entrada_ativa
            if e.get('invertido'):
                st.warning(f"### 🔄 INVERTIDA | {e['motor']} | {e['forca_real']}% | {len(e['numeros_apostar'])}n")
            else:
                emoji = "🔥" if e['forca_real'] >= 65 else "🎯" if e['forca_real'] >= 55 else "📊"
                st.info(f"### {emoji} {e['motor']} | {e['forca_real']}% | {len(e['numeros_apostar'])}n")
            if e.get('gatilho'):
                st.caption(f"🎯 {e['gatilho']}")
            st.markdown(f"## {', '.join(map(str, sorted(e['numeros_apostar'])))}")
        else:
            st.info("🔍 Analisando...")
    
    with tab_duz_col:
        hist_num = list(sis.historico_numeros)
        janela_analise = 20
        
        st.markdown("### 🧠 Motor Analítico de Sinais")
        
        if len(hist_num) >= janela_analise:
            validos = [n for n in hist_num[-janela_analise:] if n != 0]
            
            if validos:
                colunas = [get_coluna_real(n) for n in validos]
                duzias = [get_duzia_real(n) for n in validos]
                terminais = [n % 10 for n in validos]
                setores = [get_setor_roda(n) for n in validos]
                
                score_colunas = {1: 0, 2: 0, 3: 0}
                sinais_detectados = []

                c1, c2 = st.columns(2)

                with c1:
                    col_quente = Counter(colunas).most_common(1)[0][0]
                    duz_quente = Counter(duzias).most_common(1)[0][0]
                    
                    st.write("**1. Interseção Básica:**")
                    st.info(f"🔥 Coluna {col_quente} + Dúzia {duz_quente}")
                    score_colunas[col_quente] += 1
                    
                    top_terminais = [t[0] for t in Counter(terminais).most_common(3)]
                    cols_dos_terminais = [get_coluna_real(t) if t != 0 else 0 for t in top_terminais]
                    col_terminal_dominante = Counter([c for c in cols_dos_terminais if c != 0]).most_common(1)[0][0] if any(c != 0 for c in cols_dos_terminais) else 0
                    
                    if col_terminal_dominante != 0:
                        score_colunas[col_terminal_dominante] += 1
                        sinais_detectados.append(f"Terminais puxam a Coluna {col_terminal_dominante}")
                    
                    st.write("**2. Força de Terminais:**")
                    st.success(f"🎯 Terminais Quentes: {top_terminais}")
                    if col_terminal_dominante != 0:
                        st.caption(f"→ Puxando Coluna {col_terminal_dominante}")

                with c2:
                    setor_quente = Counter(setores).most_common(1)[0][0]
                    num_do_setor_quente = [n for n in validos if get_setor_roda(n) == setor_quente]
                    cols_do_setor = [get_coluna_real(n) for n in num_do_setor_quente]
                    col_dominante_setor = Counter(cols_do_setor).most_common(1)[0][0] if cols_do_setor else 0
                    
                    if col_dominante_setor != 0:
                        score_colunas[col_dominante_setor] += 1
                    
                    st.write("**3. Leitura do Cilindro:**")
                    st.warning(f"🎡 Setor dominando: {setor_quente}")
                    if col_dominante_setor != 0:
                        st.caption(f"→ Coluna {col_dominante_setor} domina este setor")
                    
                    ultimas_5_cols = colunas[-5:]
                    tem_repeticao = any(ultimas_5_cols[i] == ultimas_5_cols[i+1] for i in range(len(ultimas_5_cols)-1))
                    
                    st.write("**4. Comportamento da Mesa:**")
                    if not tem_repeticao and len(ultimas_5_cols) >= 5:
                        st.error("🏓 Padrão Ping-Pong Detectado! (Evite repetições)")
                        ultima_col = colunas[-1]
                        score_colunas[ultima_col] -= 1
                        st.caption(f"→ Penalizando Coluna {ultima_col}")
                    else:
                        st.write("🌊 Fluxo Normal (Aceita repetições)")

                st.markdown("---")
                st.markdown("### 🤖 Veredito do Algoritmo")
                
                coluna_vencedora = max(score_colunas, key=score_colunas.get)
                pontos = score_colunas[coluna_vencedora]
                
                if pontos >= 3:
                    st.success(f"### 🎯 ENTRADA FORTE: Coluna {coluna_vencedora} ({pontos}/4 confirmações)")
                elif pontos == 2:
                    st.warning(f"### ⚠️ ENTRADA MODERADA: Coluna {coluna_vencedora} ({pontos}/4 confirmações)")
                elif pontos == 1:
                    st.info(f"### 💡 ENTRADA FRACA: Coluna {coluna_vencedora} ({pontos}/4 confirmações)")
                else:
                    st.error("### 🛑 SEM PADRÃO CLARO: Fique de fora. Mercado confuso.")
                
                st.caption(f"Placar Interno: Col 1 ({score_colunas[1]} pts) | Col 2 ({score_colunas[2]} pts) | Col 3 ({score_colunas[3]} pts)")
        else:
            st.info(f"⏳ Coletando dados... ({len(hist_num)}/{janela_analise} giros na janela de análise).")

# Histórico de entradas
st.subheader("📋 Últimas")
if sis.historico_entradas:
    for entrada in reversed(sis.historico_entradas[-5:]):
        c1, c2, c3 = st.columns([1, 2, 2])
        c1.write(f"#{entrada['rodada']}")
        if entrada['acerto']:
            c2.success(f"✅ {entrada['resultado']}")
        else:
            c2.error(f"❌ {entrada['resultado']}")
        inv = "🔄" if entrada.get('invertido') else ""
        c3.write(f"{inv} {entrada['motor'][:14]} | {entrada.get('gatilho','')[:25]}")

with st.expander("📥 Download", expanded=False):
    c1, c2, c3 = st.columns(3)
    c1.download_button("JSON", exportar_historico(st.session_state.historico, 'json'), "historico.json")
    c2.download_button("CSV", exportar_historico(st.session_state.historico, 'csv'), "historico.csv")
    c3.download_button("Entradas", json.dumps(sis.historico_entradas, indent=2), "entradas.json")

salvar_sessao()
