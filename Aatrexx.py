import streamlit as st
import json
import os
import requests
import logging
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
    try:
        if 'sistema' not in st.session_state or st.session_state.sistema is None:
            return False
        performance_data = {
            'acertos': st.session_state.sistema.acertos,
            'erros': st.session_state.sistema.erros,
            'historico': st.session_state.sistema.bot.performance['historico']
        }
        with open(PERFORMANCE_PATH, 'w') as f: json.dump(performance_data, f)
        with open(ENTRADAS_PATH, 'w') as f: json.dump(st.session_state.sistema.historico_entradas, f)
        session_data = {
            'historico': st.session_state.get('historico', []),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'sistema_acertos': st.session_state.sistema.acertos,
            'sistema_erros': st.session_state.sistema.erros,
            'historico_numeros': list(st.session_state.sistema.historico_numeros),
            'historico_lucky': list(st.session_state.sistema.historico_lucky),
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'max_n_apostas': st.session_state.get('max_n_apostas', 8),
            'min_n_apostas': st.session_state.get('min_n_apostas', 5),
            'forca_minima_entrada': st.session_state.get('forca_minima_entrada', 50),
            'usar_sniper_elite': st.session_state.get('usar_sniper_elite', True),
            'usar_lucky_vizinhos': st.session_state.get('usar_lucky_vizinhos', True),
            'usar_repeticao': st.session_state.get('usar_repeticao', True),
            'usar_gap_curto': st.session_state.get('usar_gap_curto', True),
            'usar_mineracao': st.session_state.get('usar_mineracao', True),
            'usar_duzia_dom': st.session_state.get('usar_duzia_dom', True),
            'usar_espelho': st.session_state.get('usar_espelho', True),
            'usar_soma_cinco': st.session_state.get('usar_soma_cinco', True),
            'usar_lucky_alto': st.session_state.get('usar_lucky_alto', True),
            'usar_ciclo_oito': st.session_state.get('usar_ciclo_oito', True),
            'usar_alternancia_cor': st.session_state.get('usar_alternancia_cor', True),
            'green_repeticoes': st.session_state.sistema.green_repeticoes,
        }
        with open(SESSION_DATA_PATH, 'wb') as f: pickle.dump(session_data, f)
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar: {e}")
        return False

def carregar_dados_persistidos():
    try:
        if os.path.exists(SESSION_DATA_PATH):
            with open(SESSION_DATA_PATH, 'rb') as f: return pickle.load(f)
    except: pass
    return None

def limpar_sessao():
    try:
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH, ENTRADAS_PATH]:
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
        gatilho = previsao.get('gatilho', '')
        emoji = "🔥" if forca >= 65 else "🎯" if forca >= 50 else "📊"
        st.toast(f"{emoji} {motor} - {forca}%")
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"🔔 F{forca}% | {motor}\n{gatilho}\n🔢 " + " ".join(map(str, numeros)))
        salvar_sessao()
    except: pass

def enviar_resultado_auto(numero_real, acerto, lucky=False):
    try:
        st.toast(f"{'✅' if acerto else '❌'} {numero_real}" + (" 🍀" if lucky else ""))
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"📢 {'✅' if acerto else '❌'} {numero_real}" + (" 🍀" if lucky else ""))
        salvar_sessao()
    except: pass

def enviar_telegram(mensagem):
    try:
        token = st.session_state.get('telegram_token', '')
        chat_id = st.session_state.get('telegram_chat_id', '')
        if not token or not chat_id: return
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                     json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}, timeout=10)
    except: pass

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
    def get_vizinhos(self, n, r=2):
        if n not in self.race: return []
        i = self.race.index(n)
        return [self.race[(i + j) % 37] for j in range(-r, r + 1)]


# =============================
# ESTRATÉGIAS EXISTENTES
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
        if lucky_hist:
            all_lucky = []
            for sub in lucky_hist[-8:]: all_lucky.extend(sub)
            for n, _ in Counter(all_lucky).most_common(2): aposta.add(n)
        forca = 50 + freq * 5
        return {'base': set(list(aposta)[:8]), 'forca': min(100, forca), 'estrategias': [f'Terminal {td} ({freq}x)'], 'gatilho': f'Terminal {td} ({freq}x em 8 giros)'}

class EstrategiaLuckyVizinhos:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if len(h) < 3 or not lucky_hist: return None
        all_lucky = []
        for sub in lucky_hist[-10:]: all_lucky.extend(sub)
        if len(all_lucky) < 2: return None
        freq = Counter(all_lucky)
        recentes = set(h[-3:])
        lucky_rec = [n for n in freq if n in recentes]
        top = sorted(lucky_rec, key=lambda x: freq[x], reverse=True)[:3] if lucky_rec else [n for n, _ in freq.most_common(3)]
        b = set(top)
        for n in top[:2]: b.update(self.roleta.get_vizinhos(n, 1)[:1])
        for n, _ in Counter(h[-5:]).most_common(2): b.add(n)
        forca = 50 + len(all_lucky) * 2
        return {'base': set(list(b)[:8]), 'forca': min(100, forca), 'estrategias': [f'Lucky {top[:2]}'], 'gatilho': f'Lucky {" ".join(map(str, top[:2]))}'}

class EstrategiaRepeticao:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        u, p = h[-1], h[-2]
        if u != p: return None
        b = set([u]); b.update(self.roleta.get_vizinhos(u, 1)[:3])
        return {'base': b, 'forca': 75, 'estrategias': [f'Repetição {u}'], 'gatilho': f'Número {u} repetiu!'}

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
        return {'base': b, 'forca': 55 + (gap or 0) * 5, 'estrategias': [f'Gap {gap}'], 'gatilho': f'Gap {gap} giros: {u}'}

class EstrategiaMineracao:
    def analisar(self, h):
        if len(h) < 5: return None
        u = h[-1]; t = defaultdict(list)
        for i in range(len(h)-1): t[h[i]].append(h[i+1])
        seg = t.get(u, [])
        if len(seg) < 2: return None
        top = [(n, c) for n, c in Counter(seg).most_common(2) if c/len(seg) >= 0.15]
        if not top: return None
        b = set([n for n, _ in top])
        return {'base': b, 'forca': 50, 'estrategias': [f'Markov {u}→{top[0][0]}'], 'gatilho': f'Após {u} → {top[0][0]} ({top[0][1]}/{len(seg)})'}

class EstrategiaDuziaDominante:
    def analisar(self, h):
        if len(h) < 10: return None
        dz = {1: set(range(1,13)), 2: set(range(13,25)), 3: set(range(25,37))}
        cnt = Counter((n-1)//12+1 for n in h[-10:] if n != 0)
        if not cnt: return None
        d, freq = cnt.most_common(1)[0]
        if freq < 6: return None
        b = set(); b.update(list(dz[d] - set(h[-5:]))[:3]); b.update(list(dz[d].intersection(set(h[-5:])))[:2])
        return {'base': b, 'forca': 50 + (freq-6)*5, 'estrategias': [f'Dúzia {d}'], 'gatilho': f'Dúzia {d} ({freq}/10 giros)'}


# =============================
# 🆕 5 NOVAS ESTRATÉGIAS
# =============================

class EstrategiaEspelho:
    """
    🪞 NOVO: Inversão de dígitos (12↔21, 13↔31, 23↔32, etc.)
    Encontrado 8x nos 220 giros
    """
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        u = h[-1]
        if u not in self.roleta.espelhos: return None
        
        espelhado = self.roleta.espelhos[u]
        b = set([espelhado, u])
        b.update(self.roleta.get_vizinhos(espelhado, 1)[:2])
        
        # Verifica se o padrão espelho já aconteceu antes
        count_espelho = 0
        for i in range(len(h)-1):
            if h[i] in self.roleta.espelhos and h[i+1] == self.roleta.espelhos[h[i]]:
                count_espelho += 1
        
        forca = 45 + (count_espelho * 10)
        gatilho = f'Espelho {u}↔{espelhado}'
        return {'base': b, 'forca': min(100, forca), 'estrategias': [gatilho], 'gatilho': gatilho}


class EstrategiaSomaCinco:
    """
    ➕5 NOVO: Número + 5 na roleta (2→7, 5→10, 15→20, 25→30, 30→35)
    Encontrado 6x nos 220 giros
    """
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        
        # Verifica se o padrão +5 ocorreu nos últimos giros
        count_mais5 = 0
        for i in range(len(h)-1):
            if h[i] + 5 == h[i+1] or (h[i] + 5 > 36 and h[i] + 5 - 37 == h[i+1]):
                count_mais5 += 1
        
        if count_mais5 < 2: return None
        
        u = h[-1]
        b = set()
        # Próximo número +5
        prox = u + 5
        if prox > 36: prox -= 37
        b.add(prox)
        
        # Também +10 e -5
        prox10 = u + 10
        if prox10 > 36: prox10 -= 37
        b.add(prox10)
        
        b.add(u)
        b.update(self.roleta.get_vizinhos(u, 1)[:2])
        
        forca = 45 + count_mais5 * 5
        gatilho = f'Padrão +5 ({count_mais5}x)'
        return {'base': b, 'forca': min(100, forca), 'estrategias': [gatilho], 'gatilho': gatilho}


class EstrategiaLuckyAlto:
    """
    💎 NOVO: Lucky Number com multiplicador ALTO (≥200x)
    33(1000x), 23(600x), 9(700x), 12(200x), 6(600x)
    """
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist, mult_hist):
        if len(h) < 3 or not lucky_hist or not mult_hist: return None
        
        # Procura Lucky Numbers com multiplicador ≥ 200x nos últimos 30 giros
        lucky_alto = []
        for i, (lucky_list, mult_dict) in enumerate(zip(lucky_hist[-30:], mult_hist[-30:])):
            for n in lucky_list:
                mult = mult_dict.get(n, 0) if mult_dict else 0
                if mult and mult >= 200:
                    lucky_alto.append((n, mult))
        
        if len(lucky_alto) < 2: return None
        
        # Pega os 2 Lucky Numbers mais recentes com multiplicador alto
        lucky_alto_recentes = lucky_alto[-3:]
        b = set()
        for n, mult in lucky_alto_recentes:
            b.add(n)
            b.update(self.roleta.get_vizinhos(n, 1)[:2])
        
        b.update(self.roleta.get_vizinhos(h[-1], 1)[:2])
        
        forca = 55
        nums_str = ', '.join([f'{n}({m}x)' for n, m in lucky_alto_recentes[-2:]])
        gatilho = f'Lucky Alto: {nums_str}'
        return {'base': set(list(b)[:7]), 'forca': min(100, forca), 'estrategias': [gatilho], 'gatilho': gatilho}


class EstrategiaCicloOito:
    """
    8️⃣ NOVO: Número retorna após exatamente 8 giros
    Encontrado 4x nos 220 giros
    """
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 9: return None
        u = h[-1]
        
        # Verifica se h[-9] == h[-1] (ciclo de 8)
        if len(h) >= 9 and h[-9] == u:
            b = set([u])
            b.update(self.roleta.get_vizinhos(u, 1)[:3])
            
            # Verifica outros ciclos de 8
            count_ciclo8 = 0
            for i in range(len(h) - 9):
                if h[i] == h[i+8]:
                    count_ciclo8 += 1
            
            forca = 50 + count_ciclo8 * 5
            gatilho = f'Ciclo 8 giros: {u}'
            return {'base': b, 'forca': min(100, forca), 'estrategias': [gatilho], 'gatilho': gatilho}
        
        # Verifica ciclo de 6
        if len(h) >= 7 and h[-7] == u:
            b = set([u])
            b.update(self.roleta.get_vizinhos(u, 1)[:2])
            return {'base': b, 'forca': 45, 'estrategias': [f'Ciclo 6: {u}'], 'gatilho': f'Ciclo 6 giros: {u}'}
        
        return None


class EstrategiaAlternanciaCor:
    """
    🎨 NOVO: 5+ alternâncias de cor seguidas → mantém padrão
    Encontrado 15x nos 220 giros
    """
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 6: return None
        
        # Classifica cores
        cores = []
        for n in h[-10:]:
            if n == 0: cores.append('Z')
            elif n in self.roleta.vermelhos: cores.append('V')
            else: cores.append('P')
        
        # Conta alternâncias consecutivas
        alternancias = 0
        for i in range(1, len(cores)):
            if cores[i] != cores[i-1] and cores[i] != 'Z' and cores[i-1] != 'Z':
                alternancias += 1
            else:
                alternancias = 0
        
        if alternancias < 5: return None
        
        # Próxima cor deve ser a oposta da última
        ultima = cores[-1]
        prox_cor = 'P' if ultima == 'V' else 'V'
        
        alvo = self.roleta.pretos if prox_cor == 'P' else self.roleta.vermelhos
        b = alvo.intersection(set(h[-10:]))
        if len(b) < 4: b = set(list(alvo)[:6])
        
        forca = 45 + alternancias * 2
        gatilho = f'Alternância {alternancias}x → {prox_cor}'
        return {'base': b, 'forca': min(100, forca), 'estrategias': [gatilho], 'gatilho': gatilho}


# =============================
# BOT UNIFICADO (11 ESTRATÉGIAS)
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        self.sniper_elite = EstrategiaSniperElite(self.roleta)
        self.lucky_vizinhos = EstrategiaLuckyVizinhos(self.roleta)
        self.repeticao = EstrategiaRepeticao(self.roleta)
        self.gap_curto = EstrategiaGapCurto(self.roleta)
        self.mineracao = EstrategiaMineracao()
        self.duzia_dom = EstrategiaDuziaDominante()
        # 🆕 Novas estratégias
        self.espelho = EstrategiaEspelho(self.roleta)
        self.soma_cinco = EstrategiaSomaCinco(self.roleta)
        self.lucky_alto = EstrategiaLuckyAlto(self.roleta)
        self.ciclo_oito = EstrategiaCicloOito(self.roleta)
        self.alternancia_cor = EstrategiaAlternanciaCor(self.roleta)
        
        self.historico = []; self.lucky = []; self.mults = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        
    def atualizar(self, n, lucky_nums=None, lucky_mults=None):
        if isinstance(n, dict): n = n.get('number', 0)
        self.historico.append(int(n))
        self.lucky.append(lucky_nums if lucky_nums else [])
        self.mults.append(lucky_mults if lucky_mults else {})
        if len(self.historico) > 200: self.historico = self.historico[-200:]
        if len(self.lucky) > 200: self.lucky = self.lucky[-200:]
        if len(self.mults) > 200: self.mults = self.mults[-200:]
    
    def gerar_entrada(self, motores=None):
        if motores is None:
            motores = {k: True for k in [
                'sniper_elite','lucky_vizinhos','repeticao','gap_curto','mineracao','duzia_dom',
                'espelho','soma_cinco','lucky_alto','ciclo_oito','alternancia_cor'
            ]}
        
        resultados = []
        forca_min = st.session_state.get('forca_minima_entrada', 50)
        
        ests = [
            (self.sniper_elite, 'Sniper Elite', 2, [list(self.historico), self.lucky]),
            (self.lucky_vizinhos, 'Lucky Vizinhos', 3, [list(self.historico), self.lucky]),
            (self.repeticao, 'Repetição', 3, [list(self.historico)]),
            (self.gap_curto, 'Gap Curto', 2, [list(self.historico)]),
            (self.mineracao, 'Mineração', 1, [list(self.historico)]),
            (self.duzia_dom, 'Dúzia Dom.', 1, [list(self.historico)]),
            (self.espelho, '🪞 Espelho', 2, [list(self.historico)]),
            (self.soma_cinco, '➕5 Soma Cinco', 1, [list(self.historico)]),
            (self.lucky_alto, '💎 Lucky Alto', 2, [list(self.historico), self.lucky, self.mults]),
            (self.ciclo_oito, '8️⃣ Ciclo Oito', 1, [list(self.historico)]),
            (self.alternancia_cor, '🎨 Alternância', 1, [list(self.historico)]),
        ]
        
        for est, nome, peso, args in ests:
            try:
                key = nome.lower().replace(' ','_').replace('🪞','').replace('➕5','').replace('💎','').replace('8️⃣','').replace('🎨','').strip('_')
                key_map = {
                    'sniper_elite':'sniper_elite','lucky_vizinhos':'lucky_vizinhos','repeticao':'repeticao',
                    'gap_curto':'gap_curto','mineracao':'mineracao','duzia_dom':'duzia_dom',
                    'espelho':'espelho','soma_cinco':'soma_cinco','lucky_alto':'lucky_alto',
                    'ciclo_oito':'ciclo_oito','alternancia_cor':'alternancia_cor'
                }
                key = key_map.get(key, key)
                if motores.get(key, True) and len(self.historico) >= 1:
                    r = est.analisar(*args)
                    if r and len(r.get('base', set())) >= 1 and r['forca'] >= forca_min:
                        resultados.append((nome, r, peso))
            except: pass
        
        if not resultados: return None
        
        base = set(); ests_ativas = []; gatilhos = []
        ft, mp, mf = 0, resultados[0][0], 0
        for nome, r, peso in resultados:
            for _ in range(peso): base.update(r['base'])
            ests_ativas.extend(r.get('estrategias', []))
            if 'gatilho' in r: gatilhos.append(r['gatilho'])
            ft += r['forca'] * peso
            if r['forca'] > mf: mf, mp = r['forca'], nome
        
        fm = int(ft / sum(p for _, _, p in resultados))
        mx = st.session_state.get('max_n_apostas', 8)
        mn = st.session_state.get('min_n_apostas', 5)
        
        consenso = Counter()
        for nome, r, peso in resultados:
            for n in r['base']: consenso[n] += peso
        
        lst = [n for n, _ in consenso.most_common(mx)]
        while len(lst) < mn and len(lst) < 37:
            for n in range(37):
                if n not in lst: lst.append(n); break
        
        qs = fm / max(1, len(lst))
        q = "EXCELENTE" if qs >= 12 else "BOA" if qs >= 8 else "REGULAR"
        
        return {
            'numeros_apostar': sorted(lst),
            'forca_real': min(100, max(30, fm)),
            'motor': mp,
            'estrategias_ativas': list(set(ests_ativas))[:5],
            'qtd_motores': len(resultados),
            'qualidade': q,
            'gatilho': ' | '.join(gatilhos[:3])
        }


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
        self.acertos = 0; self.erros = 0
        
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data['number']
            lucky = numero_data.get('luckyNumbers', [])
            lucky_mults = numero_data.get('luckyMultipliers', {})
            mult = lucky_mults.get(nr) if nr in lucky else None
            is_lucky = nr in lucky
        else:
            nr = int(numero_data); lucky, lucky_mults, mult, is_lucky = [], {}, None, False
        
        self.bot.atualizar(nr, lucky, lucky_mults)
        self.historico_numeros.append(nr)
        self.historico_lucky.append(lucky)
        self.historico_mults.append(lucky_mults)
        
        if self.entrada_ativa:
            acerto = nr in self.entrada_ativa.get('numeros_apostar', [])
            if acerto: self.acertos += 1; self.bot.performance['acertos'] += 1
            else: self.erros += 1; self.bot.performance['erros'] += 1
            self.bot.performance['historico'].append(1 if acerto else 0)
            
            self.historico_entradas.append({
                'rodada': len(self.historico_numeros)-1,
                'hora': datetime.now().strftime('%H:%M:%S'),
                'numeros': self.entrada_ativa.get('numeros_apostar', []),
                'resultado': nr, 'acerto': acerto,
                'forca': self.entrada_ativa.get('forca_real', 0),
                'motor': self.entrada_ativa.get('motor', ''),
                'gatilho': self.entrada_ativa.get('gatilho', ''),
                'estrategias': self.entrada_ativa.get('estrategias_ativas', []),
                'qualidade': self.entrada_ativa.get('qualidade', ''),
                'lucky': is_lucky, 'multiplicador': mult,
            })
            if len(self.historico_entradas) > 50: self.historico_entradas = self.historico_entradas[-50:]
            
            enviar_resultado_auto(nr, acerto, is_lucky)
            self.entrada_ativa = None
        
        mot = {k: st.session_state.get(f'usar_{k}', True) for k in [
            'sniper_elite','lucky_vizinhos','repeticao','gap_curto','mineracao','duzia_dom',
            'espelho','soma_cinco','lucky_alto','ciclo_oito','alternancia_cor'
        ]}
        self.entrada_ativa = self.bot.gerar_entrada(mot)
        if self.entrada_ativa: enviar_previsao_auto(self.entrada_ativa)
    
    def zerar(self):
        self.acertos = 0; self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear(); self.historico_lucky.clear(); self.historico_mults.clear()
        self.entrada_ativa = None
        self.bot.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.bot.historico = []; self.bot.lucky = []; self.bot.mults = []
        salvar_sessao()


# =============================
# FUNÇÕES AUXILIARES
# =============================
def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    try:
        with open(caminho, "w") as f: json.dump(historico, f, indent=2)
    except: pass

def fetch_latest_result():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=5); r.raise_for_status()
        d = r.json(); gd = d.get("data", {}); rs = gd.get("result", {})
        nm = rs.get("outcome", {}).get("number"); ts = gd.get("startedAt")
        ln, lm = [], {}
        for item in rs.get('luckyNumbersList', []):
            n = item.get('number')
            if n is not None: ln.append(n); m = item.get('roundedMultiplier')
            if m is not None: lm[n] = m
        return {"number": nm, "timestamp": ts, "luckyNumbers": ln, "luckyMultipliers": lm}
    except: return None

def exportar_historico(historico, formato='json'):
    if formato == 'json': return json.dumps(historico, indent=2, ensure_ascii=False)
    linhas = ["numero,timestamp,multiplicador"]
    for item in historico:
        if isinstance(item, dict):
            n = item.get('number', '')
            linhas.append(f"{n},{item.get('timestamp','')},{item.get('luckyMultipliers',{}).get(n,'')}")
        else: linhas.append(f"{item},,")
    return "\n".join(linhas)


# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎯 Roleta Bot Pro v10 - 11 Estratégias", layout="centered")
st.title("🎯 Roleta Bot Pro v10 - 11 Estratégias")

if "sistema" not in st.session_state or st.session_state.sistema is None:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    if not st.session_state.get('historico'): st.session_state.historico = dados.get('historico', [])
    sis = st.session_state.sistema
    sis.acertos = dados.get('sistema_acertos', 0); sis.erros = dados.get('sistema_erros', 0)
    for num, lucky in zip(dados.get('historico_numeros', []), dados.get('historico_lucky', [])):
        sis.bot.atualizar(num, lucky); sis.historico_numeros.append(num); sis.historico_lucky.append(lucky)
    if os.path.exists(PERFORMANCE_PATH):
        try:
            with open(PERFORMANCE_PATH, 'r') as f:
                p = json.load(f)
                sis.bot.performance = {'acertos': p.get('acertos',0), 'erros': p.get('erros',0), 'historico': p.get('historico',[])}
        except: pass
    if os.path.exists(ENTRADAS_PATH):
        try:
            with open(ENTRADAS_PATH, 'r') as f: sis.historico_entradas = json.load(f)
        except: pass

defaults = {
    'modo_automatico': True, 'max_n_apostas': 8, 'min_n_apostas': 5,
    'forca_minima_entrada': 50,
    'usar_sniper_elite': True, 'usar_lucky_vizinhos': True, 'usar_repeticao': True,
    'usar_gap_curto': True, 'usar_mineracao': True, 'usar_duzia_dom': True,
    'usar_espelho': True, 'usar_soma_cinco': True, 'usar_lucky_alto': True,
    'usar_ciclo_oito': True, 'usar_alternancia_cor': True,
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

# Sidebar
with st.sidebar:
    st.subheader("⚙️ Config")
    st.session_state.forca_minima_entrada = st.slider("⚡ Força Mínima", 40, 65, st.session_state.forca_minima_entrada, 5)
    st.session_state.max_n_apostas = st.slider("📊 Máx. números", 10, 15, st.session_state.max_n_apostas)
    
    with st.expander("🤖 11 Estratégias", expanded=False):
        tab1, tab2 = st.tabs(["Originais (6)", "Novas (5)"])
        with tab1:
            st.session_state.usar_sniper_elite = st.checkbox("🎯 Sniper Elite (2x)", value=st.session_state.usar_sniper_elite)
            st.session_state.usar_lucky_vizinhos = st.checkbox("🍀 Lucky Vizinhos (3x)", value=st.session_state.usar_lucky_vizinhos)
            st.session_state.usar_repeticao = st.checkbox("🔄 Repetição (3x)", value=st.session_state.usar_repeticao)
            st.session_state.usar_gap_curto = st.checkbox("⏭️ Gap Curto (2x)", value=st.session_state.usar_gap_curto)
            st.session_state.usar_mineracao = st.checkbox("⛏️ Mineração (1x)", value=st.session_state.usar_mineracao)
            st.session_state.usar_duzia_dom = st.checkbox("📐 Dúzia Dom. (1x)", value=st.session_state.usar_duzia_dom)
        with tab2:
            st.session_state.usar_espelho = st.checkbox("🪞 Espelho (2x) - 12↔21", value=st.session_state.usar_espelho)
            st.session_state.usar_soma_cinco = st.checkbox("➕5 Soma Cinco (1x) - 2→7", value=st.session_state.usar_soma_cinco)
            st.session_state.usar_lucky_alto = st.checkbox("💎 Lucky Alto (2x) - ≥200x", value=st.session_state.usar_lucky_alto)
            st.session_state.usar_ciclo_oito = st.checkbox("8️⃣ Ciclo Oito (1x) - 8 giros", value=st.session_state.usar_ciclo_oito)
            st.session_state.usar_alternancia_cor = st.checkbox("🎨 Alternância Cor (1x)", value=st.session_state.usar_alternancia_cor)
    
    st.session_state.modo_automatico = st.checkbox("Modo Automático", value=st.session_state.modo_automatico)
    
    with st.expander("🔔 Telegram", expanded=False):
        st.session_state.telegram_token = st.text_input("Token", value=st.session_state.telegram_token, type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID", value=st.session_state.telegram_chat_id)
    
    c1, c2 = st.columns(2)
    c1.button("💾 Salvar", on_click=lambda: [salvar_resultado_em_arquivo(st.session_state.historico), salvar_sessao(), st.success("✅")], use_container_width=True)
    c2.button("🗑️ Zerar", on_click=lambda: st.session_state.sistema.zerar() or st.rerun(), use_container_width=True)

# Conteúdo
st.subheader("✍️ Inserir Números")
c1, c2 = st.columns([4, 1])
with c1: entrada = st.text_input("Números (0-36):", placeholder="Ex: 12 21 14", key="entrada")
with c2:
    if st.button("➕", use_container_width=True) and entrada:
        try:
            nums = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
            for n in nums:
                item = {"number": n, "timestamp": f"m{len(st.session_state.historico)}", "luckyNumbers": [], "luckyMultipliers": {}}
                st.session_state.historico.append(item)
                st.session_state.sistema.processar_novo_numero(item)
            salvar_resultado_em_arquivo(st.session_state.historico); salvar_sessao()
            st.success(f"{len(nums)} adicionados!"); st.rerun()
        except: pass

st_autorefresh(interval=3000, key="refresh")

resultado = fetch_latest_result()
if st.session_state.historico:
    ultimo_ts = st.session_state.historico[-1].get("timestamp") if st.session_state.historico else None
else: ultimo_ts = None
if resultado and resultado.get("timestamp") and resultado["timestamp"] != ultimo_ts:
    n = resultado.get("number")
    if n is not None:
        st.session_state.historico.append(resultado)
        st.session_state.sistema.processar_novo_numero(resultado)
        salvar_resultado_em_arquivo(st.session_state.historico); salvar_sessao()

# Últimos números
st.subheader("🔁 Últimos Números")
if st.session_state.historico:
    ultimos = st.session_state.historico[-12:]
    cols = st.columns(6)
    for i, item in enumerate(reversed(ultimos)):
        with cols[i % 6]:
            n = item['number'] if isinstance(item, dict) else item
            is_lucky = False; mult_val = None
            if isinstance(item, dict):
                if n in item.get('luckyNumbers', []): is_lucky = True; mult_val = item.get('luckyMultipliers', {}).get(n)
            if is_lucky:
                st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #2d2d44); border: 2px solid #f0c040;
                border-radius: 12px; padding: 8px 4px; text-align: center; margin: 2px 0;
                box-shadow: 0 0 10px rgba(240, 192, 64, 0.3);">
                <div style="font-size: 0.65rem; color: #f0c040;">⚡ LUCKY</div>
                <div style="font-size: 1.5rem; font-weight: 700; color: #f0c040;">{n}</div>
                <div style="font-size: 0.8rem; color: #f0c040; font-weight: 600;">{f'{mult_val}x' if mult_val else ''}</div></div>""", unsafe_allow_html=True)
            else:
                cor = "#4fc3f7" if n == 0 else "#66bb6a" if n in {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36} else "#ef5350"
                st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #252540); border: 2px solid {cor};
                border-radius: 12px; padding: 12px 4px; text-align: center; margin: 2px 0;">
                <div style="font-size: 1.4rem; font-weight: 700; color: {cor};">{n}</div></div>""", unsafe_allow_html=True)

# Status
sis = st.session_state.sistema
st.subheader("📊 Status")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("🟢", sis.acertos); c2.metric("🔴", sis.erros)
tx = sis.acertos/(sis.acertos+sis.erros)*100 if (sis.acertos+sis.erros)>0 else 0
c3.metric("📊", f"{tx:.0f}%"); c4.metric("⚡Min", st.session_state.get('forca_minima_entrada', 50))
c5.metric("🤖", "11")

# Entrada
st.subheader("🎯 Entrada Atual")
if sis.entrada_ativa:
    e = sis.entrada_ativa
    emoji = "🔥" if e['forca_real'] >= 65 else "🎯" if e['forca_real'] >= 50 else "📊"
    st.info(f"### {emoji} {e['motor']} | {e['forca_real']}% | {e['qualidade']} | {len(e['numeros_apostar'])}n")
    if e.get('gatilho'): st.warning(f"🎯 **Gatilho**: {e['gatilho']}")
    st.markdown(f"## {', '.join(map(str, sorted(e['numeros_apostar'])))}")
else: st.info("🔍 Analisando...")

# Histórico
st.subheader("📋 Últimas Entradas")
if sis.historico_entradas:
    for entrada in reversed(sis.historico_entradas[-6:]):
        c1, c2, c3, c4 = st.columns([0.5, 2, 1.5, 2])
        c1.write(f"**#{entrada['rodada']}**"); c2.write(", ".join(map(str, entrada['numeros'][:5])))
        if entrada['acerto']: c3.success(f"✅ {entrada['resultado']}" + ("🍀" if entrada.get('lucky') else ""))
        else: c3.error(f"❌ {entrada['resultado']}")
        g_str = f" | {entrada.get('gatilho','')[:40]}" if entrada.get('gatilho') else ""
        c4.write(f"{entrada['motor'][:14]}{g_str}")
else: st.info("Nenhuma entrada.")

if sis.historico_entradas:
    with st.expander("📊 Performance", expanded=False):
        ms = defaultdict(lambda: {'a':0,'t':0})
        for e in sis.historico_entradas:
            m = e.get('motor','?'); ms[m]['t']+=1
            if e['acerto']: ms[m]['a']+=1
        cols = st.columns(min(5, len(ms)))
        for i, (m, s) in enumerate(sorted(ms.items(), key=lambda x: x[1]['t'], reverse=True)[:5]):
            with cols[i]: st.metric(m[:12], f"{s['a']/s['t']*100:.0f}%" if s['t']>0 else "0%", f"{s['a']}/{s['t']}")

with st.expander("📥 Download", expanded=False):
    c1, c2, c3 = st.columns(3)
    c1.download_button("JSON", exportar_historico(st.session_state.historico,'json'), "historico.json")
    c2.download_button("CSV", exportar_historico(st.session_state.historico,'csv'), "historico.csv")
    c3.download_button("Entradas", json.dumps(sis.historico_entradas, indent=2), "entradas.json")

salvar_sessao()
