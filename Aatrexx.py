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
        self.espelhos = {12:21, 21:12, 13:31, 31:13, 23:32, 32:23, 1:10, 10:1, 2:20, 20:2, 3:30, 30:3}
        self.voisins = {22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25}
        self.tiers = {27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33}
        self.orphelins = {1, 20, 14, 31, 9, 17, 34, 6}
        self.primos = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}
        self.baixos = set(range(1, 19))
        self.altos = set(range(19, 37))
        self.numeros_problematicos = {0, 32, 33, 34, 35}
        self.max_problematicos = 2
        
        # Colunas para nova estratégia
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
    
    def sao_vizinhos_fisicos(self, a, b, d=1):
        if a not in self.race or b not in self.race:
            return False
        ia, ib = self.race.index(a), self.race.index(b)
        diff = abs(ia - ib)
        return diff <= d or diff >= 37 - d

# =============================
# 24 ESTRATÉGIAS (18 ORIGINAIS + 6 NOVAS)
# =============================

# --- 18 ESTRATÉGIAS ORIGINAIS (MANTIDAS INTACTAS) ---

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
# 🆕 6 NOVAS ESTRATÉGIAS
# =============================

class EstrategiaConfirmacaoLucky:
    """✅ NOVA: Lucky numbers tendem a repetir em 2-3 giros"""
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h, lucky_hist):
        if len(h) < 3 or not lucky_hist:
            return None
        
        # Pega lucky numbers dos últimos 5 giros
        recent_lucky = []
        for i in range(max(0, len(lucky_hist)-5), len(lucky_hist)):
            recent_lucky.extend(lucky_hist[i])
        
        if not recent_lucky:
            return None
        
        # Verifica se algum lucky recente ainda não saiu
        lucky_freq = Counter(recent_lucky)
        nao_saiu = [n for n in lucky_freq if n not in h[-3:]]
        
        if not nao_saiu:
            return None
        
        # Prioriza lucky com maior frequência
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
    """✅ NOVA: Balanço entre números altos e baixos"""
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 8:
            return None
        
        ultimos = h[-8:]
        altos = sum(1 for n in ultimos if n >= 19)
        baixos = len(ultimos) - altos
        
        # Se desbalanceou muito (6+ de um lado)
        if altos >= 6:
            alvo = self.roleta.baixos
            tendencia = "Baixos"
        elif baixos >= 6:
            alvo = self.roleta.altos
            tendencia = "Altos"
        else:
            return None
        
        # Pega números do lado oposto que saíram recentemente
        b = alvo.intersection(set(h[-15:])) if len(h) >= 15 else alvo
        
        # Adiciona vizinhos do último número
        b.update(self.roleta.get_vizinhos(h[-1], 1)[:3])
        
        forca = 50 + abs(altos - baixos) * 5
        return {
            'base': set(list(b)[:8]),
            'forca': min(80, forca),
            'estrategias': [f'Pêndulo →{tendencia}'],
            'gatilho': f'Pêndulo {altos}A/{baixos}B → {tendencia}'
        }

class EstrategiaQuenteFrio:
    """✅ NOVA: Números frios (ausentes 15+ giros) combinados com lucky"""
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h, lucky_hist):
        if len(h) < 15:
            return None
        
        # Encontra números que não saíram nos últimos 15 giros
        recentes = set(h[-15:])
        todos = set(range(37))
        frios = list(todos - recentes - {0})  # Exclui zero inicialmente
        
        if not frios:
            return None
        
        # Se tem lucky recente, prioriza frios próximos aos lucky
        b = set()
        if lucky_hist:
            recent_lucky = [n for sub in lucky_hist[-5:] for n in sub]
            for lucky_num in recent_lucky[:3]:
                vizinhos = set(self.roleta.get_vizinhos(lucky_num, 2))
                frios_proximos = vizinhos.intersection(frios)
                b.update(list(frios_proximos)[:3])
        
        # Adiciona alguns frios aleatórios
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
    """✅ NOVA: Duas estratégias apontando mesmo número aumenta precisão"""
    def analisar(self, h):
        # Esta é uma meta-estratégia que será processada diferentemente
        # Ela identifica números que aparecem em múltiplas estratégias
        return None  # Será implementada via lógica no gerar_entrada

class EstrategiaColunasAlternadas:
    """✅ NOVA: Ciclos de colunas (1-12, 13-24, 25-36)"""
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h):
        if len(h) < 6:
            return None
        
        colunas = [self.roleta.get_coluna(n) for n in h[-6:] if n != 0]
        if len(colunas) < 4:
            return None
        
        # Detecta padrão de alternância entre colunas
        padrao = []
        for i in range(1, len(colunas)):
            if colunas[i] != colunas[i-1]:
                padrao.append(colunas[i])
        
        if len(padrao) < 3:
            return None
        
        # Última coluna que apareceu
        ultima_col = colunas[-1]
        
        # Próxima coluna provável (diferente da última)
        colunas_alvo = [1, 2, 3]
        colunas_alvo.remove(ultima_col)
        coluna_provavel = colunas_alvo[0]  # Simplificação: pega a primeira disponível
        
        # Mapeia coluna para números
        col_map = {1: self.roleta.coluna1, 2: self.roleta.coluna2, 3: self.roleta.coluna3}
        alvo_numeros = col_map[coluna_provavel]
        
        # Filtra números que já saíram recentemente nessa coluna
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
    """✅ NOVA: Lucky em setor específico atrai números do mesmo setor"""
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, h, lucky_hist):
        if len(h) < 3 or not lucky_hist:
            return None
        
        # Encontra últimos lucky numbers e seus setores
        setores_lucky = defaultdict(int)
        for i in range(max(0, len(lucky_hist)-8), len(lucky_hist)):
            for n in lucky_hist[i]:
                setor = self.roleta.get_setor_cilindro(n)
                if setor != "Zero":
                    setores_lucky[setor] += 1
        
        if not setores_lucky:
            return None
        
        # Setor dominante nos lucky
        setor_dom = max(setores_lucky, key=setores_lucky.get)
        
        # Mapeia setor para números
        sn = {
            'Voisins': self.roleta.voisins,
            'Tiers': self.roleta.tiers,
            'Orphelins': self.roleta.orphelins
        }
        
        if setor_dom not in sn:
            return None
        
        numeros_setor = sn[setor_dom]
        
        # Números do setor que não saíram recentemente
        nao_sairam = numeros_setor - set(h[-5:])
        b = set(list(nao_sairam)[:4])
        
        # Adiciona alguns que já saíram também
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
# BOT UNIFICADO (ATUALIZADO COM 24 ESTRATÉGIAS)
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
        
        # 6 novas
        self.confirmacao_lucky = EstrategiaConfirmacaoLucky(self.roleta)
        self.pendulo = EstrategiaPendulo(self.roleta)
        self.quente_frio = EstrategiaQuenteFrio(self.roleta)
        self.confirmacao_dupla = EstrategiaConfirmacaoDupla()
        self.colunas_alternadas = EstrategiaColunasAlternadas(self.roleta)
        self.lucky_setor = EstrategiaLuckySetor(self.roleta)
        
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
    
    def gerar_entrada(self, motores=None, forcar_inversao=False):
        if motores is None:
            motores = {k: True for k in [
                'sniper_elite', 'lucky_vizinhos', 'repeticao', 'gap_curto', 'mineracao', 'duzia_dom',
                'espelho', 'soma_cinco', 'lucky_alto', 'ciclo_oito', 'alternancia_cor',
                'setor_cilindro', 'zero_virada', 'primos', 'vizinhos_fisicos', 'lucky_terminal',
                'faixa_numerica', 'numero_do_dia',
                # Novas estratégias
                'confirmacao_lucky', 'pendulo', 'quente_frio', 'colunas_alternadas', 'lucky_setor'
            ]}
        
        resultados = []
        forca_min = st.session_state.get('forca_minima_entrada', 55)
        
        # Lista de estratégias (nome, instância, peso, argumentos)
        ests = [
            # Originais (peso 4)
            (self.repeticao, 'Repetição', 4, [list(self.historico)]),
            # Originais (peso 3)
            (self.lucky_vizinhos, 'Lucky Vizinhos', 3, [list(self.historico), self.lucky]),
            (self.vizinhos_fisicos, 'Vizinhos Físicos', 3, [list(self.historico)]),
            # Novas (peso 3 - alta prioridade baseada na análise)
            (self.confirmacao_lucky, 'Confirm. Lucky', 3, [list(self.historico), self.lucky]),
            (self.lucky_setor, 'Lucky Setor', 3, [list(self.historico), self.lucky]),
            # Originais (peso 2)
            (self.sniper_elite, 'Sniper Elite', 2, [list(self.historico), self.lucky]),
            (self.gap_curto, 'Gap Curto', 2, [list(self.historico)]),
            (self.espelho, 'Espelho', 2, [list(self.historico)]),
            (self.lucky_alto, 'Lucky Alto', 2, [list(self.historico), self.lucky, self.mults]),
            (self.numero_do_dia, 'Nº do Dia', 2, [list(self.historico)]),
            # Novas (peso 2)
            (self.pendulo, 'Pêndulo', 2, [list(self.historico)]),
            # Originais (peso 1)
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
            # Novas (peso 1)
            (self.quente_frio, 'Quente/Frio', 1, [list(self.historico), self.lucky]),
            (self.colunas_alternadas, 'Colunas Alt.', 1, [list(self.historico)]),
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
        
        # ✅ Meta-estratégia: Confirmação Dupla
        # Aumenta peso de números que aparecem em múltiplas estratégias
        if len(resultados) >= 2:
            contagem_numeros = Counter()
            for _, r, peso in resultados:
                for n in r['base']:
                    contagem_numeros[n] += peso
            
            # Números com confirmação dupla (aparecem em 2+ estratégias)
            confirmados = [n for n, c in contagem_numeros.items() if c >= 5]
            if confirmados:
                # Cria entrada virtual para confirmação dupla
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
        
        # 🔄 INVERSÃO
        if forcar_inversao:
            entrada = self._inverter_entrada(entrada)
        
        return entrada
    
    def _inverter_entrada(self, entrada):
        """Inverte os números, escolhendo aleatoriamente entre os não selecionados"""
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
# SISTEMA PRINCIPAL (MANTIDO INTACTO)
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
            # Novas estratégias
            'confirmacao_lucky', 'pendulo', 'quente_frio', 'colunas_alternadas', 'lucky_setor'
        ]}
        
        forcar_inversao = st.session_state.get('modo_inversao_auto', False) and self.estado_inversao
        
        self.entrada_ativa = self.bot.gerar_entrada(mot, forcar_inversao)
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
# FUNÇÕES AUXILIARES (MANTIDAS INTACTAS)
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
# APLICAÇÃO STREAMLIT (MANTIDA INTACTA)
# =============================
st.set_page_config(page_title="🎯 Roleta Bot Pro v17 - 24 Estratégias", layout="centered")
st.title("🎯 Roleta Bot Pro v17 - Análise Avançada")

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

# Configurações padrão (incluindo novas estratégias)
defaults = {k: True for k in [
    'modo_automatico', 'usar_sniper_elite', 'usar_lucky_vizinhos', 'usar_repeticao',
    'usar_gap_curto', 'usar_mineracao', 'usar_duzia_dom', 'usar_espelho', 'usar_soma_cinco',
    'usar_lucky_alto', 'usar_ciclo_oito', 'usar_alternancia_cor', 'usar_setor_cilindro',
    'usar_zero_virada', 'usar_primos', 'usar_vizinhos_fisicos', 'usar_lucky_terminal',
    'usar_faixa_numerica', 'usar_numero_do_dia', 'limitar_numeros_altos', 'evitar_zero',
    # Novas estratégias (ativadas por padrão)
    'usar_confirmacao_lucky', 'usar_pendulo', 'usar_quente_frio', 
    'usar_colunas_alternadas', 'usar_lucky_setor'
]}
defaults.update({
    'max_n_apostas': 7,
    'min_n_apostas': 4,
    'forca_minima_entrada': 55,
    'max_gatilhos': 2,
    'modo_inversao_auto': False
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
        25, 95,
        st.session_state.forca_minima_entrada,
        5
    )
    st.session_state.max_n_apostas = st.slider(
        "📊 Máx. números",
        12, 18,
        st.session_state.max_n_apostas
    )
    
    with st.expander("🛡️ Filtros", expanded=False):
        st.session_state.limitar_numeros_altos = st.checkbox(
            "Limitar 0,32,33,34,35",
            value=st.session_state.limitar_numeros_altos
        )
        st.session_state.evitar_zero = st.checkbox(
            "Evitar Zero",
            value=st.session_state.evitar_zero
        )
    
    with st.expander("🤖 24 Estratégias", expanded=False):
        st.markdown("**🆕 NOVAS (Análise de Padrões)**")
        st.session_state.usar_confirmacao_lucky = st.checkbox(
            "🍀 Confirmação Lucky (3x)", 
            value=st.session_state.usar_confirmacao_lucky,
            help="Lucky numbers tendem a repetir em 2-3 giros"
        )
        st.session_state.usar_lucky_setor = st.checkbox(
            "🎯 Lucky Setor (3x)", 
            value=st.session_state.usar_lucky_setor,
            help="Lucky em setor atrai números do mesmo setor"
        )
        st.session_state.usar_pendulo = st.checkbox(
            "⏳ Pêndulo (2x)", 
            value=st.session_state.usar_pendulo,
            help="Balanço entre números altos e baixos"
        )
        st.session_state.usar_quente_frio = st.checkbox(
            "🌡️ Quente/Frio", 
            value=st.session_state.usar_quente_frio,
            help="Números frios (15+ giros) com lucky"
        )
        st.session_state.usar_colunas_alternadas = st.checkbox(
            "📊 Colunas Alt.", 
            value=st.session_state.usar_colunas_alternadas,
            help="Alternância entre colunas 1-12, 13-24, 25-36"
        )
        
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
c4.metric("🔄 Inv", "ON" if st.session_state.get('modo_inversao_auto', False) else "OFF")
c5.metric("Estado", "🔄INV" if sis.estado_inversao else "📊NOR")

# Entrada atual
st.subheader("🎯 Entrada Atual")
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
