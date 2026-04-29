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
        with open(PERFORMANCE_PATH, 'w') as f:
            json.dump(performance_data, f)
        
        with open(ENTRADAS_PATH, 'w') as f:
            json.dump(st.session_state.sistema.historico_entradas, f)
        
        session_data = {
            'historico': st.session_state.get('historico', []),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'sistema_acertos': st.session_state.sistema.acertos,
            'sistema_erros': st.session_state.sistema.erros,
            'historico_numeros': list(st.session_state.sistema.historico_numeros),
            'historico_lucky': list(st.session_state.sistema.historico_lucky),
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'max_n_apostas': st.session_state.get('max_n_apostas', 7),
            'min_n_apostas': st.session_state.get('min_n_apostas', 5),
            'forca_minima_entrada': st.session_state.get('forca_minima_entrada', 42),
            'usar_sniper': st.session_state.get('usar_sniper', True),
            'usar_mineracao': st.session_state.get('usar_mineracao', True),
            'usar_giro': st.session_state.get('usar_giro', True),
            'usar_gap': st.session_state.get('usar_gap', True),
            'usar_sequencia': st.session_state.get('usar_sequencia', True),
            'usar_terminais': st.session_state.get('usar_terminais', True),
            'usar_simetria': st.session_state.get('usar_simetria', True),
            'usar_repeticao': st.session_state.get('usar_repeticao', True),
            'usar_ciclo': st.session_state.get('usar_ciclo', True),
            'usar_par_impar': st.session_state.get('usar_par_impar', True),
            'usar_duzia_dom': st.session_state.get('usar_duzia_dom', True),
            'usar_gap3': st.session_state.get('usar_gap3', True),
            'usar_elite_master': st.session_state.get('usar_elite_master', True),
            'usar_sniper_elite': st.session_state.get('usar_sniper_elite', True),
            'usar_ciclo_rapido': st.session_state.get('usar_ciclo_rapido', True),
            'usar_vizinhos_numericos': st.session_state.get('usar_vizinhos_numericos', True),
            'usar_lucky_vizinhos': st.session_state.get('usar_lucky_vizinhos', True),
            'usar_cor_setor': st.session_state.get('usar_cor_setor', True),
            'green_repeticoes': st.session_state.sistema.green_repeticoes,
            'erro_aguardando': st.session_state.sistema.erro_aguardando,
            'ultima_entrada_numeros': st.session_state.sistema.ultima_entrada_numeros,
            'erro_ja_repitido': st.session_state.sistema.erro_ja_repitido,
            'ultima_entrada_forca': st.session_state.sistema.ultima_entrada_forca,
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
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    except:
        pass

# =============================
# NOTIFICAÇÕES
# =============================
def enviar_previsao_auto(previsao):
    try:
        numeros = sorted(previsao['numeros_apostar'])
        forca = previsao.get('forca_real', 0)
        motor = previsao.get('motor', '')
        green = previsao.get('green', False)
        
        if green: emoji = "🟢"
        elif forca >= 55: emoji = "🔥"
        elif forca >= 45: emoji = "🎯"
        else: emoji = "📊"
        
        st.toast(f"{emoji} {motor} - {forca}%")
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"🔔 {'[GREEN]' if green else ''} F{forca}% | {len(numeros)}n\n🔢 " + " ".join(map(str, numeros)))
        
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
        self.pares = {0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36}
        self.impares = {1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35}
    
    def get_vizinhos(self, numero, raio=2):
        if numero not in self.race: return []
        idx = self.race.index(numero)
        return [self.race[(idx + i) % 37] for i in range(-raio, raio + 1)]
    
    def get_setor(self, numero): return 0 if numero == 0 else (numero - 1) // 12 + 1
    def get_coluna(self, numero): return 0 if numero == 0 else (numero - 1) % 3 + 1


# =============================
# ESTRATÉGIAS (FORÇAS AUMENTADAS, SAÍDAS REDUZIDAS)
# =============================

class EstrategiaSniperElite:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 5: return None
        u5 = h[-5:]; termos = [n%10 for n in u5]
        tq = [t for t, _ in Counter(termos).most_common()]
        aposta = set()
        aposta.update(self.roleta.get_vizinhos(u5[-1], 1)[:3])
        for t in tq[:2]:
            for n in range(37):
                if n%10 == t: aposta.add(n)
                if len(aposta) >= 7: break
            if len(aposta) >= 7: break
        f = 45 + (15 if len(set(termos)) <= 3 else 0)
        return {'base': set(list(aposta)[:7]), 'forca': min(100, f), 'estrategias': [f'Terminais {tq[:2]}']}

class AnalisadorEliteMaster:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 5: return None
        cores = ['V' if n in self.roleta.vermelhos else 'P' if n in self.roleta.pretos else 'Z' for n in h[-5:]]
        base = set(); f = 0
        if cores.count("V") >= 4: base.update(list(self.roleta.vermelhos)[:5]); f += 45
        elif cores.count("P") >= 4: base.update(list(self.roleta.pretos)[:5]); f += 45
        elif cores.count("V") >= 3: base.update(list(self.roleta.vermelhos)[:4]); f += 35
        elif cores.count("P") >= 3: base.update(list(self.roleta.pretos)[:4]); f += 35
        if not base: return None
        return {'base': base, 'forca': min(100,f), 'estrategias': ['Elite Master']}

class EstrategiaSniper:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 5: return None
        r = h[-15:] if len(h) >= 15 else h
        dz = Counter([self.roleta.get_setor(n) for n in r if n != 0])
        cl = Counter([self.roleta.get_coluna(n) for n in r if n != 0])
        b = set(); f = 0
        if dz and cl and dz.most_common(1)[0][1] >= 5 and cl.most_common(1)[0][1] >= 4:
            d, c = dz.most_common(1)[0][0], cl.most_common(1)[0][0]
            b.update(set(range((d-1)*12+1,d*12+1)).intersection(set(range(c,37,3)))); f += 50
        return {'base': b, 'forca': f, 'estrategias': ['Sniper']} if f > 0 else None

class EstrategiaMineracao:
    def analisar(self, h):
        if len(h) < 3: return None
        t = defaultdict(list)
        for i in range(len(h)-1): t[h[i]].append(h[i+1])
        s = t.get(h[-1], [])
        if s:
            top = [n for n, c in Counter(s).most_common(4) if c/len(s) >= 0.12]
            if top: return {'base': set(top[:3]), 'forca': 40, 'estrategias': ['Mineração']}
        return None

class EstrategiaPorGiro:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        freq = Counter(h[-5:])
        b = set([h[-1]])
        b.update([n for n, c in freq.most_common(2) if c >= 2])
        b.update(self.roleta.get_vizinhos(h[-1], 1)[:2])
        return {'base': b, 'forca': 35 if len(b) <= 5 else 30, 'estrategias': ['Giro']}

class EstrategiaGap:
    def analisar(self, h):
        if len(h) < 3: return None
        u = h[-1]
        if len(h) >= 3 and h[-3] == u: return {'base': {u, h[-2]}, 'forca': 50, 'estrategias': ['Gap1']}
        if len(h) >= 4 and h[-4] == u: return {'base': {u, h[-2], h[-3]}, 'forca': 40, 'estrategias': ['Gap2']}
        return None

class EstrategiaSequencia:
    def analisar(self, h):
        if len(h) < 3: return None
        p = defaultdict(list)
        for i in range(len(h)-1): p[h[i]].append(h[i+1])
        prev = [n for n,_ in Counter(p.get(h[-1],[])).most_common(3)]
        return {'base': set(prev), 'forca': 35, 'estrategias': ['Sequência']} if len(prev) >= 2 else None

class EstrategiaTerminais:
    def analisar(self, h, jan=10):
        if len(h) < jan: return None
        f, freq = Counter([n%10 for n in h[-jan:]]).most_common(1)[0]
        if freq >= 3: return {'base': set([n for n in range(37) if n%10==f][:4]), 'forca': 35+freq*5, 'estrategias': [f'Terminal {f}']}
        return None

class EstrategiaSimetria:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 1: return None
        esp = {1:10,10:1,2:20,20:2,3:30,30:3,12:21,21:12,13:31,31:13,23:32,32:23}
        u = h[-1]; b = set()
        if u in esp: b.update([esp[u], u]); b.update(self.roleta.get_vizinhos(u,1)[:1])
        elif u in {0,11,22,33}: b.add(u)
        elif 0 <= u <= 9: b.update([n for n in range(37) if n%10==u][:2])
        if not b: return None
        return {'base': b, 'forca': 30, 'estrategias': ['Simetria']}

class EstrategiaRepeticao:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        u, p = h[-1], h[-2]; b = set()
        if u == p: b.add(u); b.update(self.roleta.get_vizinhos(u,1)[:2])
        if len(b) == 0: return None
        return {'base': b, 'forca': 60, 'estrategias': ['Repetição']}

class EstrategiaCicloRetorno:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 15: return None
        reps = [n for n, c in Counter(h).items() if c >= 3]
        if not reps: return None
        rec = [n for n in reps if n in h[-8:]]
        if not rec: return None
        b = set(rec[:3])
        for n in rec[:2]: b.update(self.roleta.get_vizinhos(n,1)[:1])
        return {'base': b, 'forca': 45, 'estrategias': ['Ciclo']}

class EstrategiaParImpar:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 4: return None
        tipos = ['zero' if n==0 else 'par' if n%2==0 else 'impar' for n in h[-10:]]
        seq, ta = 0, tipos[-1]
        for t in reversed(tipos):
            if t == ta and t != 'zero': seq += 1
            else: break
        if seq >= 4 and ta in ['par','impar']:
            alvo = self.roleta.pares if ta == 'impar' else self.roleta.impares
            b = alvo.intersection(set(h[-10:]))
            if len(b) < 4: b = set(list(alvo)[:5])
            return {'base': b, 'forca': 40+seq*5, 'estrategias': [f'Inversão {ta}']}
        return None

class EstrategiaDuziaDominante:
    def analisar(self, h):
        if len(h) < 10: return None
        dz = {1:set(range(1,13)),2:set(range(13,25)),3:set(range(25,37))}
        cnt = Counter((n-1)//12+1 for n in h[-10:] if n != 0)
        if not cnt: return None
        d, freq = cnt.most_common(1)[0]
        if freq >= 5:
            b = set()
            b.update(list(dz[d] - set(h[-5:]))[:3])
            b.update(list(dz[d].intersection(set(h[-5:])))[:2])
            return {'base': b, 'forca': 40+freq*3, 'estrategias': [f'Dúzia {d}']}
        return None

class EstrategiaGap3:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 4: return None
        u = h[-1]; b = set()
        if len(h) >= 4 and h[-4] == u: b.update([u, h[-2], h[-3]])
        if len(b) == 0: return None
        for n in list(b)[:1]: b.update(self.roleta.get_vizinhos(n,1)[:1])
        return {'base': b, 'forca': 50, 'estrategias': ['Gap3']}

class EstrategiaCicloRapido:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 12: return None
        freq = Counter(h[-15:])
        reps = [n for n, c in freq.items() if c >= 2]
        if not reps: return None
        b = set(reps[:4])
        for n in list(b)[:2]: b.update(self.roleta.get_vizinhos(n, 1)[:1])
        return {'base': b, 'forca': 50, 'estrategias': ['Ciclo Rápido']}

class EstrategiaVizinhosNumericos:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 1: return None
        u = h[-1]; b = set()
        for d in [-2, -1, 1, 2]:
            v = u + d
            if 0 <= v <= 36: b.add(v)
        b.add(u)
        return {'base': b, 'forca': 35, 'estrategias': [f'Vizinhos ±2']}

class EstrategiaLuckyVizinhos:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if len(h) < 2 or not lucky_hist: return None
        all_lucky = []
        for sub in lucky_hist[-6:]: all_lucky.extend(sub)
        if not all_lucky: return None
        freq_lucky = Counter(all_lucky)
        top_lucky = [n for n, _ in freq_lucky.most_common(3)]
        b = set(top_lucky)
        for n in top_lucky[:1]: b.update(self.roleta.get_vizinhos(n, 1)[:1])
        return {'base': b, 'forca': 45, 'estrategias': ['Lucky Vizinhos']}

class EstrategiaCorSetor:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 4: return None
        cores = ['V' if n in self.roleta.vermelhos else 'P' if n in self.roleta.pretos else 'Z' for n in h[-8:]]
        ult_cor = cores[-1]; seq = 0
        for c in reversed(cores):
            if c == ult_cor and c != 'Z': seq += 1
            else: break
        if seq >= 4:
            alvo = self.roleta.pretos if ult_cor == 'V' else self.roleta.vermelhos
            b = alvo.intersection(set(h[-10:]))
            if len(b) < 4: b = set(list(alvo)[:5])
            return {'base': b, 'forca': 45+seq*5, 'estrategias': [f'Cor Oposta ({seq}x {ult_cor})']}
        return None


# =============================
# BOT UNIFICADO (17 ESTRATÉGIAS - OTIMIZADO)
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        self.sniper_elite = EstrategiaSniperElite(self.roleta)
        self.elite_master = AnalisadorEliteMaster(self.roleta)
        self.sniper = EstrategiaSniper(self.roleta)
        self.mineracao = EstrategiaMineracao()
        self.giro = EstrategiaPorGiro(self.roleta)
        self.gap = EstrategiaGap()
        self.sequencia = EstrategiaSequencia()
        self.terminais = EstrategiaTerminais()
        self.simetria = EstrategiaSimetria(self.roleta)
        self.repeticao = EstrategiaRepeticao(self.roleta)
        self.ciclo = EstrategiaCicloRetorno(self.roleta)
        self.par_impar = EstrategiaParImpar(self.roleta)
        self.duzia_dom = EstrategiaDuziaDominante()
        self.gap3 = EstrategiaGap3(self.roleta)
        self.ciclo_rapido = EstrategiaCicloRapido(self.roleta)
        self.vizinhos_num = EstrategiaVizinhosNumericos(self.roleta)
        self.lucky_vizinhos = EstrategiaLuckyVizinhos(self.roleta)
        self.cor_setor = EstrategiaCorSetor(self.roleta)
        
        self.historico = []; self.lucky = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        
    def atualizar(self, n, lucky_nums=None):
        if isinstance(n, dict): n = n.get('number', 0)
        self.historico.append(int(n))
        self.lucky.append(lucky_nums if lucky_nums else [])
        if len(self.historico) > 200: self.historico = self.historico[-200:]
        if len(self.lucky) > 200: self.lucky = self.lucky[-200:]
    
    def gerar_entrada(self, motores=None):
        if motores is None:
            motores = {k: True for k in [
                'sniper_elite','elite_master','sniper','mineracao','giro','gap',
                'sequencia','terminais','simetria','repeticao','ciclo','par_impar',
                'duzia_dom','gap3','ciclo_rapido','vizinhos_num','lucky_vizinhos','cor_setor'
            ]}
        
        resultados = []
        forca_min = st.session_state.get('forca_minima_entrada', 42)
        
        ests = [
            (self.sniper_elite, 'sniper_elite', 4, [list(self.historico)]),
            (self.elite_master, 'elite_master', 3, [list(self.historico)]),
            (self.repeticao, 'repeticao', 3, [list(self.historico)]),
            (self.gap3, 'gap3', 2, [list(self.historico)]),
            (self.ciclo_rapido, 'ciclo_rapido', 2, [list(self.historico)]),
            (self.lucky_vizinhos, 'lucky_vizinhos', 2, [list(self.historico), self.lucky]),
            (self.cor_setor, 'cor_setor', 2, [list(self.historico)]),
            (self.ciclo, 'ciclo', 1, [list(self.historico)]),
            (self.vizinhos_num, 'vizinhos_num', 1, [list(self.historico)]),
            (self.par_impar, 'par_impar', 1, [list(self.historico)]),
            (self.duzia_dom, 'duzia_dom', 1, [list(self.historico)]),
            (self.sniper, 'sniper', 1, [list(self.historico)]),
            (self.mineracao, 'mineracao', 1, [list(self.historico)]),
            (self.giro, 'giro', 1, [list(self.historico)]),
            (self.gap, 'gap', 1, [list(self.historico)]),
            (self.sequencia, 'sequencia', 1, [list(self.historico)]),
            (self.terminais, 'terminais', 1, [list(self.historico)]),
            (self.simetria, 'simetria', 1, [list(self.historico)]),
        ]
        
        for est, key, peso, args in ests:
            try:
                if motores.get(key, True) and len(self.historico) >= 1:
                    if key == 'lucky_vizinhos' and not self.lucky: continue
                    r = est.analisar(*args)
                    if r and len(r.get('base', set())) >= 1 and r['forca'] >= forca_min:
                        resultados.append((key.replace('_',' ').title(), r, peso))
            except: pass
        
        if not resultados:
            freq = Counter(self.historico[-8:])
            quentes = [n for n, _ in freq.most_common(7)]
            return {'numeros_apostar': sorted(quentes[:7]), 'forca_real': 25, 'motor': 'Frequência', 'estrategias_ativas': ['Quentes 8g'], 'qtd_motores': 1, 'qualidade': 'BÁSICA', 'green': False, 'green_count': 0}
        
        base = set(); ests_ativas = []
        ft, mp, mf = 0, resultados[0][0], 0
        
        for nome, r, peso in resultados:
            for _ in range(peso): base.update(r['base'])
            ests_ativas.extend(r.get('estrategias', []))
            ft += r['forca'] * peso
            if r['forca'] > mf: mf, mp = r['forca'], nome
        
        fm = int(ft / sum(p for _, _, p in resultados))
        mx = st.session_state.get('max_n_apostas', 7)
        mn = st.session_state.get('min_n_apostas', 5)
        
        consenso = Counter()
        for nome, r, peso in resultados:
            for n in r['base']: consenso[n] += peso
        
        lst = [n for n, _ in consenso.most_common(mx)]
        while len(lst) < mn and len(lst) < 37:
            for n in range(37):
                if n not in lst: lst.append(n); break
        
        qs = fm / max(1, len(lst))
        q = "EXCELENTE" if qs >= 10 else "BOA" if qs >= 7 else "REGULAR"
        
        return {'numeros_apostar': sorted(lst), 'forca_real': min(100, max(25, fm)), 'motor': mp, 'estrategias_ativas': list(set(ests_ativas))[:5], 'qtd_motores': len(resultados), 'qualidade': q, 'green': False, 'green_count': 0}


# =============================
# SISTEMA PRINCIPAL (OTIMIZADO)
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
        self.green_repeticoes = 0
        self.erro_aguardando = False
        self.erro_ja_repitido = False
        self.ultima_entrada_numeros = []
        self.ultima_entrada_forca = 0
        
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data['number']
            lucky = numero_data.get('luckyNumbers', [])
            lucky_mults = numero_data.get('luckyMultipliers', {})
            mult = lucky_mults.get(nr) if nr in lucky else None
            is_lucky = nr in lucky
        else:
            nr = int(numero_data); lucky, lucky_mults, mult, is_lucky = [], {}, None, False
        
        self.bot.atualizar(nr, lucky)
        self.historico_numeros.append(nr)
        self.historico_lucky.append(lucky)
        self.historico_mults.append(mult)
        
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
                'estrategias': self.entrada_ativa.get('estrategias_ativas', []),
                'qualidade': self.entrada_ativa.get('qualidade', ''),
                'lucky': is_lucky, 'multiplicador': mult,
                'green': self.entrada_ativa.get('green', False),
            })
            if len(self.historico_entradas) > 50: self.historico_entradas = self.historico_entradas[-50:]
            
            entrada_forca = self.entrada_ativa.get('forca_real', 0)
            era_green = self.entrada_ativa.get('green', False)
            forca_min = st.session_state.get('forca_minima_entrada', 42)
            
            if acerto:
                # ✅ ACERTOU
                if not era_green and self.green_repeticoes < 2:
                    if entrada_forca >= forca_min:
                        self.green_repeticoes += 1
                        self.ultima_entrada_numeros = list(self.entrada_ativa.get('numeros_apostar', []))
                        self.ultima_entrada_forca = entrada_forca
                    else:
                        self.green_repeticoes = 0; self.ultima_entrada_numeros = []
                elif era_green and self.green_repeticoes < 2:
                    self.green_repeticoes += 1
                    self.ultima_entrada_numeros = list(self.entrada_ativa.get('numeros_apostar', []))
                    self.ultima_entrada_forca = entrada_forca
                else:
                    self.green_repeticoes = 0; self.ultima_entrada_numeros = []
                
                self.erro_aguardando = False; self.erro_ja_repitido = False
            else:
                # ❌ ERROU
                if era_green:
                    self.green_repeticoes = 0; self.ultima_entrada_numeros = []
                    self.erro_aguardando = False; self.erro_ja_repitido = False
                else:
                    if entrada_forca >= forca_min and not self.erro_ja_repitido:
                        self.erro_aguardando = True
                        self.ultima_entrada_numeros = list(self.entrada_ativa.get('numeros_apostar', []))
                        self.ultima_entrada_forca = entrada_forca
                    else:
                        self.erro_aguardando = False; self.erro_ja_repitido = False
                        self.ultima_entrada_numeros = []
                    self.green_repeticoes = 0
            
            enviar_resultado_auto(nr, acerto, is_lucky)
            self.entrada_ativa = None
        
        # 🟢 Green Repeat
        if self.green_repeticoes > 0 and self.ultima_entrada_numeros:
            self.entrada_ativa = {
                'numeros_apostar': sorted(self.ultima_entrada_numeros),
                'forca_real': min(80, self.ultima_entrada_forca + 10),
                'motor': 'Green Repeat', 'estrategias_ativas': [f'🟢 Green #{self.green_repeticoes}/2'],
                'qtd_motores': 1, 'qualidade': 'GREEN', 'green': True,
                'green_count': self.green_repeticoes,
            }
            enviar_previsao_auto(self.entrada_ativa)
            return
        
        # ⏳ Erro Repeat
        if self.erro_aguardando and self.ultima_entrada_numeros:
            self.erro_aguardando = False; self.erro_ja_repitido = True
            self.entrada_ativa = {
                'numeros_apostar': sorted(self.ultima_entrada_numeros),
                'forca_real': self.ultima_entrada_forca,
                'motor': 'Erro Repeat', 'estrategias_ativas': ['⏳ Repetindo'],
                'qtd_motores': 1, 'qualidade': 'REPEAT', 'green': False, 'green_count': 0,
            }
            enviar_previsao_auto(self.entrada_ativa)
            return
        
        if self.erro_ja_repitido and self.green_repeticoes == 0: self.erro_ja_repitido = False
        
        # 🧠 Nova análise
        mot = {k: st.session_state.get(f'usar_{k}', True) for k in [
            'sniper_elite','elite_master','sniper','mineracao','giro','gap','sequencia','terminais',
            'simetria','repeticao','ciclo','par_impar','duzia_dom','gap3',
            'ciclo_rapido','vizinhos_num','lucky_vizinhos','cor_setor'
        ]}
        self.entrada_ativa = self.bot.gerar_entrada(mot)
        if self.entrada_ativa: enviar_previsao_auto(self.entrada_ativa)
    
    def zerar(self):
        self.acertos = 0; self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear(); self.historico_lucky.clear(); self.historico_mults.clear()
        self.entrada_ativa = None
        self.green_repeticoes = 0; self.erro_aguardando = False; self.erro_ja_repitido = False
        self.ultima_entrada_numeros = []; self.ultima_entrada_forca = 0
        self.bot.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.bot.historico = []; self.bot.lucky = []
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
st.set_page_config(page_title="🎯 Roleta Bot Pro v3", layout="centered")
st.title("🎯 Roleta Bot Pro v3")

if "sistema" not in st.session_state or st.session_state.sistema is None:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    if not st.session_state.get('historico'): st.session_state.historico = dados.get('historico', [])
    sis = st.session_state.sistema
    sis.acertos = dados.get('sistema_acertos', 0); sis.erros = dados.get('sistema_erros', 0)
    sis.green_repeticoes = dados.get('green_repeticoes', 0)
    sis.erro_aguardando = dados.get('erro_aguardando', False)
    sis.erro_ja_repitido = dados.get('erro_ja_repitido', False)
    sis.ultima_entrada_numeros = dados.get('ultima_entrada_numeros', [])
    sis.ultima_entrada_forca = dados.get('ultima_entrada_forca', 0)
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
    'modo_automatico': True, 'max_n_apostas': 7, 'min_n_apostas': 5,
    'forca_minima_entrada': 42,
    'usar_sniper_elite': True, 'usar_elite_master': True,
    'usar_sniper': True, 'usar_mineracao': True, 'usar_giro': True,
    'usar_gap': True, 'usar_sequencia': True, 'usar_terminais': True,
    'usar_simetria': True, 'usar_repeticao': True, 'usar_ciclo': True,
    'usar_par_impar': True, 'usar_duzia_dom': True, 'usar_gap3': True,
    'usar_ciclo_rapido': True, 'usar_vizinhos_numericos': True,
    'usar_lucky_vizinhos': True, 'usar_cor_setor': True,
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
    st.session_state.forca_minima_entrada = st.slider("⚡ Força Mínima", 30, 60, st.session_state.forca_minima_entrada, 2,
        help="Força mínima para ativar motores e Green/Erro Repeat")
    st.session_state.max_n_apostas = st.slider("📊 Máx. números", 4, 10, st.session_state.max_n_apostas)
    st.session_state.min_n_apostas = st.slider("📊 Mín. números", 3, 7, st.session_state.min_n_apostas)
    
    with st.expander("🤖 Motores (17)", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.session_state.usar_sniper_elite = st.checkbox("Sniper-Elite", value=st.session_state.usar_sniper_elite)
            st.session_state.usar_elite_master = st.checkbox("Elite Master", value=st.session_state.usar_elite_master)
            st.session_state.usar_ciclo_rapido = st.checkbox("Ciclo Rápido", value=st.session_state.usar_ciclo_rapido)
            st.session_state.usar_lucky_vizinhos = st.checkbox("Lucky Vizinhos", value=st.session_state.usar_lucky_vizinhos)
            st.session_state.usar_cor_setor = st.checkbox("Cor Setor", value=st.session_state.usar_cor_setor)
            st.session_state.usar_vizinhos_numericos = st.checkbox("Vizinhos ±2", value=st.session_state.usar_vizinhos_numericos)
            st.session_state.usar_sniper = st.checkbox("Sniper", value=st.session_state.usar_sniper)
            st.session_state.usar_mineracao = st.checkbox("Mineração", value=st.session_state.usar_mineracao)
            st.session_state.usar_giro = st.checkbox("Giro", value=st.session_state.usar_giro)
        with c2:
            st.session_state.usar_gap = st.checkbox("Gap", value=st.session_state.usar_gap)
            st.session_state.usar_sequencia = st.checkbox("Sequência", value=st.session_state.usar_sequencia)
            st.session_state.usar_terminais = st.checkbox("Terminais", value=st.session_state.usar_terminais)
            st.session_state.usar_simetria = st.checkbox("Simetria", value=st.session_state.usar_simetria)
            st.session_state.usar_repeticao = st.checkbox("Repetição", value=st.session_state.usar_repeticao)
            st.session_state.usar_ciclo = st.checkbox("Ciclo", value=st.session_state.usar_ciclo)
            st.session_state.usar_par_impar = st.checkbox("Par/Ímpar", value=st.session_state.usar_par_impar)
            st.session_state.usar_duzia_dom = st.checkbox("Dúzia Dom.", value=st.session_state.usar_duzia_dom)
            st.session_state.usar_gap3 = st.checkbox("Gap 3", value=st.session_state.usar_gap3)
    
    st.session_state.modo_automatico = st.checkbox("Modo Automático", value=st.session_state.modo_automatico)
    
    with st.expander("🔔 Telegram", expanded=False):
        st.session_state.telegram_token = st.text_input("Token", value=st.session_state.telegram_token, type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID", value=st.session_state.telegram_chat_id)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Salvar", use_container_width=True):
            salvar_resultado_em_arquivo(st.session_state.historico); salvar_sessao(); st.success("✅")
    with c2:
        if st.button("🗑️ Zerar", use_container_width=True):
            st.session_state.sistema.zerar(); st.rerun()

# Conteúdo
st.subheader("✍️ Inserir Números")
c1, c2 = st.columns([4, 1])
with c1:
    entrada = st.text_input("Números (0-36):", placeholder="Ex: 12 21 14", key="entrada")
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

# Últimos números com raios
st.subheader("🔁 Últimos Números")
if st.session_state.historico:
    ultimos = st.session_state.historico[-12:]
    cols = st.columns(6)
    for i, item in enumerate(reversed(ultimos)):
        with cols[i % 6]:
            n = item['number'] if isinstance(item, dict) else item
            is_lucky = False; mult_val = None
            if isinstance(item, dict):
                lucky_nums = item.get('luckyNumbers', [])
                lucky_mults = item.get('luckyMultipliers', {})
                if n in lucky_nums: is_lucky = True; mult_val = lucky_mults.get(n)
            if is_lucky:
                mult_str = f"{mult_val}x" if mult_val else ""
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #1a1a2e, #2d2d44); border: 2px solid #f0c040;
                border-radius: 12px; padding: 8px 4px; text-align: center; margin: 2px 0;
                box-shadow: 0 0 10px rgba(240, 192, 64, 0.3);">
                <div style="font-size: 0.65rem; color: #f0c040;">⚡ LUCKY</div>
                <div style="font-size: 1.5rem; font-weight: 700; color: #f0c040;">{n}</div>
                <div style="font-size: 0.8rem; color: #f0c040; font-weight: 600;">{mult_str}</div></div>""", unsafe_allow_html=True)
            else:
                cor = "#4fc3f7" if n == 0 else "#66bb6a" if n in {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36} else "#ef5350"
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #1a1a2e, #252540); border: 2px solid {cor};
                border-radius: 12px; padding: 12px 4px; text-align: center; margin: 2px 0;">
                <div style="font-size: 1.4rem; font-weight: 700; color: {cor};">{n}</div></div>""", unsafe_allow_html=True)

# Status
sis = st.session_state.sistema
st.subheader("📊 Status")
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("🟢", sis.acertos)
c2.metric("🔴", sis.erros)
tx = sis.acertos/(sis.acertos+sis.erros)*100 if (sis.acertos+sis.erros)>0 else 0
c3.metric("📊", f"{tx:.0f}%")
c4.metric("🟢G", f"{sis.green_repeticoes}/2")
c5.metric("⏳E", "Sim" if sis.erro_aguardando else "Não")
c6.metric("⚡Min", st.session_state.get('forca_minima_entrada', 42))

# Entrada
st.subheader("🎯 Entrada Atual")
if sis.entrada_ativa:
    e = sis.entrada_ativa
    if e.get('green'): st.success(f"### 🟢 GREEN #{e.get('green_count',0)}/2")
    else:
        emoji = "🔥" if e['forca_real'] >= 55 else "🎯" if e['forca_real'] >= 45 else "📊"
        st.info(f"### {emoji} {e['motor']} | {e['forca_real']}% | {e['qualidade']} | {len(e['numeros_apostar'])}n")
    st.caption(f"🎯 {', '.join(e.get('estrategias_ativas', [])[:4])}")
    st.markdown(f"## {', '.join(map(str, sorted(e['numeros_apostar'])))}")
else: st.info("Aguardando...")

# Histórico
st.subheader("📋 Últimas Entradas")
if sis.historico_entradas:
    for entrada in reversed(sis.historico_entradas[-6:]):
        c1, c2, c3, c4 = st.columns([0.5, 2, 1.5, 2])
        c1.write(f"**#{entrada['rodada']}**")
        c2.write(", ".join(map(str, entrada['numeros'][:5])))
        if entrada['acerto']: c3.success(f"✅ {entrada['resultado']}" + ("🍀" if entrada.get('lucky') else ""))
        else: c3.error(f"❌ {entrada['resultado']}")
        c4.write(f"{'🟢' if entrada.get('green') else ''} {entrada['motor'][:12]} | {entrada['forca']}%")
else: st.info("Nenhuma entrada.")

# Performance
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
    with c1: st.download_button("JSON", exportar_historico(st.session_state.historico,'json'), "historico.json")
    with c2: st.download_button("CSV", exportar_historico(st.session_state.historico,'csv'), "historico.csv")
    with c3: st.download_button("Entradas", json.dumps(sis.historico_entradas, indent=2), "entradas.json")

salvar_sessao()
