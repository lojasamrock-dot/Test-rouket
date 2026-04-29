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
            'acertos': st.session_state.sistema.bot.performance['acertos'],
            'erros': st.session_state.sistema.bot.performance['erros'],
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
            'sistema_historico_desempenho': st.session_state.sistema.historico_desempenho,
            'historico_numeros': list(st.session_state.sistema.historico_numeros),
            'historico_lucky': list(st.session_state.sistema.historico_lucky),
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'max_n_apostas': st.session_state.get('max_n_apostas', 12),
            'min_n_apostas': st.session_state.get('min_n_apostas', 5),
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
            'green_repeticoes': st.session_state.sistema.green_repeticoes,
            'erro_aguardando': st.session_state.sistema.erro_aguardando,
            'ultima_entrada_numeros': st.session_state.sistema.ultima_entrada_numeros,
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
        estrategias = previsao.get('estrategias_ativas', [])
        motor = previsao.get('motor', '')
        qualidade = previsao.get('qualidade', '')
        qtd_motores = previsao.get('qtd_motores', 0)
        green = previsao.get('green', False)
        green_count = previsao.get('green_count', 0)
        
        if green:
            emoji = "🟢"
        elif forca >= 50:
            emoji = "🔥"
        elif forca >= 35:
            emoji = "🎯"
        else:
            emoji = "📊"
        
        st.toast(f"{emoji} {motor} - {forca}%", icon=emoji)
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            tag = "[GREEN]" if green else ""
            enviar_telegram(f"🔔 {tag} F{forca}% | {len(numeros)}n 🔢 " + " ".join(map(str, numeros)))
        
        salvar_sessao()
    except:
        pass

def enviar_resultado_auto(numero_real, acerto, multiplicador=None, lucky=False):
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
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                     json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}, timeout=10)
    except:
        pass

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
        self.voisins = {22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25}
        self.tiers = {27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33}
        self.orphelins = {1, 20, 14, 31, 9, 17, 34, 6}
        self.setores_ordem = {
            "Voisins": [22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25],
            "Tiers": [27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33],
            "Orphelins": [1, 20, 14, 31, 9, 17, 34, 6]
        }
    
    def get_vizinhos(self, numero, raio=2):
        if numero not in self.race: return []
        idx = self.race.index(numero)
        return [self.race[(idx + i) % 37] for i in range(-raio, raio + 1)]
    
    def get_setor(self, numero):
        return 0 if numero == 0 else (numero - 1) // 12 + 1
    
    def get_coluna(self, numero):
        return 0 if numero == 0 else (numero - 1) % 3 + 1
    
    def get_setor_cilindro(self, numero):
        if numero in self.voisins: return "Voisins"
        elif numero in self.tiers: return "Tiers"
        elif numero in self.orphelins: return "Orphelins"
        return "Zero"


# =============================
# SNIPER-ELITE V2
# =============================
class EstrategiaSniperElite:
    def __init__(self, roleta):
        self.roleta = roleta
        self.cobertura_alvo = 12
    
    def analisar(self, historico):
        if len(historico) < 5: return None
        ultimos_5 = historico[-5:]
        terminais = [n % 10 for n in ultimos_5]
        term_quentes = [t for t, _ in Counter(terminais).most_common()]
        setor = self.roleta.get_setor_cilindro(ultimos_5[-1])
        
        aposta = set()
        if setor in self.roleta.setores_ordem:
            aposta.update(self.roleta.setores_ordem[setor][:6])
        
        for t in term_quentes[:2]:
            for n in range(37):
                if n % 10 == t:
                    aposta.add(n)
                    if len(aposta) >= self.cobertura_alvo: break
            if len(aposta) >= self.cobertura_alvo: break
        
        if len(aposta) < 8:
            aposta.update(self.roleta.get_vizinhos(ultimos_5[-1], 1))
        
        forca = 30 + (10 if len(set(terminais)) < 5 else 0)
        return {'base': set(list(aposta)[:self.cobertura_alvo]), 'forca': min(100, forca), 'estrategias': [f'Terminais {term_quentes[:2]}']}


# =============================
# ELITE MASTER
# =============================
class AnalisadorEliteMaster:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def get_info(self, n):
        if n == 0: return {"cor": "Verde", "par": "Zero", "duzia": 0, "term": 0, "setor": "Voisins"}
        return {
            "cor": "Vermelho" if n in self.roleta.vermelhos else "Preto",
            "par": "Par" if n % 2 == 0 else "Ímpar",
            "duzia": (n-1)//12+1, "term": n%10,
            "setor": self.roleta.get_setor_cilindro(n)
        }
    
    def analisar(self, historico):
        if len(historico) < 5: return None
        dados = [self.get_info(n) for n in historico[-5:]]
        base = set()
        forca = 0
        
        cores = [d['cor'] for d in dados]
        if cores.count("Vermelho") >= 4:
            base.update(list(self.roleta.vermelhos)[:8]); forca += 40
        elif cores.count("Preto") >= 4:
            base.update(list(self.roleta.pretos)[:8]); forca += 40
        
        if not base: return None
        return {'base': base, 'forca': min(100, forca), 'estrategias': ['Elite Master']}


# =============================
# DEMAIS ESTRATÉGIAS (COMPACTADAS)
# =============================
class EstrategiaSniper:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 5: return None
        r = h[-15:] if len(h) >= 15 else h
        dz = Counter([self.roleta.get_setor(n) for n in r if n != 0])
        cl = Counter([self.roleta.get_coluna(n) for n in r if n != 0])
        b = set(); f = 0
        if dz and cl and dz.most_common(1)[0][1] >= 4 and cl.most_common(1)[0][1] >= 3:
            d, c = dz.most_common(1)[0][0], cl.most_common(1)[0][0]
            b.update(set(range((d-1)*12+1,d*12+1)).intersection(set(range(c,37,3)))); f += 40
        return {'base': b, 'forca': f, 'estrategias': ['Sniper']} if f > 0 else None

class EstrategiaMineracao:
    def analisar(self, h):
        if len(h) < 3: return None
        t = defaultdict(list)
        for i in range(len(h)-1): t[h[i]].append(h[i+1])
        s = t.get(h[-1], [])
        if s:
            top = [n for n, c in Counter(s).most_common(6) if c/len(s) >= 0.1]
            if top: return {'base': set(top[:5]), 'forca': 35, 'estrategias': ['Mineração']}
        return None

class EstrategiaPorGiro:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        b = set([h[-1]])
        b.update([n for n, _ in Counter(h[-5:]).most_common(3)])
        b.update(self.roleta.get_vizinhos(h[-1], 2)[:3])
        return {'base': b, 'forca': 30, 'estrategias': ['Giro']}

class EstrategiaGap:
    def analisar(self, h):
        if len(h) < 3: return None
        u = h[-1]
        if len(h) >= 3 and h[-3] == u: return {'base': {u, h[-2]}, 'forca': 35, 'estrategias': ['Gap1']}
        if len(h) >= 4 and h[-4] == u: return {'base': {u, h[-2], h[-3]}, 'forca': 25, 'estrategias': ['Gap2']}
        return None

class EstrategiaSequencia:
    def analisar(self, h):
        if len(h) < 3: return None
        p = defaultdict(list)
        for i in range(len(h)-1): p[h[i]].append(h[i+1])
        prev = [n for n, _ in Counter(p.get(h[-1], [])).most_common(5)]
        return {'base': set(prev), 'forca': 30, 'estrategias': ['Sequência']} if len(prev) >= 2 else None

class EstrategiaTerminais:
    def analisar(self, h, jan=8):
        if len(h) < jan: return None
        f, freq = Counter([n%10 for n in h[-jan:]]).most_common(1)[0]
        if freq >= 2: return {'base': set([n for n in range(37) if n%10==f][:5]), 'forca': 25+freq*5, 'estrategias': [f'Terminal {f}']}
        return None

class EstrategiaSimetria:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 1: return None
        esp = {1:10,10:1,2:20,20:2,3:30,30:3,12:21,21:12,13:31,31:13,23:32,32:23}
        u = h[-1]; b = set()
        if u in esp: b.update([esp[u], u])
        elif u in {0,11,22,33}: b.add(u); b.update(self.roleta.get_vizinhos(u,1)[:3])
        elif 0 <= u <= 9: b.update([n for n in range(37) if n%10==u][:4])
        if not b: return None
        return {'base': b, 'forca': 25, 'estrategias': ['Simetria']}

class EstrategiaRepeticao:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        u, p = h[-1], h[-2]; b = set(); f = 0
        if u == p: b.add(u); b.update(self.roleta.get_vizinhos(u,1)[:2]); f += 55
        if len(b) == 0: return None
        return {'base': b, 'forca': min(100, f), 'estrategias': ['Repetição']}

class EstrategiaCicloRetorno:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 20: return None
        freq = Counter(h)
        reps = [n for n, c in freq.items() if c >= 3]
        if not reps: return None
        rec = [n for n in reps if n in h[-10:]]
        if not rec: return None
        b = set(rec[:4])
        for n in rec[:2]: b.update(self.roleta.get_vizinhos(n,1)[:2])
        return {'base': b, 'forca': 40, 'estrategias': ['Ciclo']}

class EstrategiaParImpar:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 4: return None
        tipos = ['zero' if n==0 else 'par' if n%2==0 else 'impar' for n in h[-10:]]
        seq, ta = 0, tipos[-1]
        for t in reversed(tipos):
            if t == ta and t != 'zero': seq += 1
            else: break
        if seq >= 3 and ta in ['par','impar']:
            alvo = self.roleta.pares if ta == 'impar' else self.roleta.impares
            b = alvo.intersection(set(h[-15:]))
            if len(b) < 4: b = set(list(alvo)[:8])
            return {'base': b, 'forca': 35+seq*5, 'estrategias': [f'Inversão {ta}']}
        return None

class EstrategiaDuziaDominante:
    def analisar(self, h):
        if len(h) < 10: return None
        dz = {1:set(range(1,13)), 2:set(range(13,25)), 3:set(range(25,37))}
        cnt = Counter((n-1)//12+1 for n in h[-10:] if n != 0)
        if not cnt: return None
        d, freq = cnt.most_common(1)[0]
        if freq >= 4:
            b = set()
            b.update(list(dz[d] - set(h[-5:]))[:5])
            b.update(list(dz[d].intersection(set(h[-5:])))[:3])
            return {'base': b, 'forca': 35+freq*3, 'estrategias': [f'Dúzia {d}']}
        return None

class EstrategiaGap3:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 4: return None
        u = h[-1]; b = set(); f = 0
        if len(h) >= 4 and h[-4] == u: b.update([u, h[-2], h[-3]]); f += 45
        if len(h) >= 5 and h[-5] == u: b.add(u); f += 35
        if not b: return None
        for n in list(b)[:2]: b.update(self.roleta.get_vizinhos(n,1)[:2])
        return {'base': b, 'forca': min(100,f), 'estrategias': ['Gap3']}


# =============================
# BOT UNIFICADO
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
        self.historico = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        
    def atualizar(self, n):
        if isinstance(n, dict): n = n.get('number', 0)
        self.historico.append(int(n))
        if len(self.historico) > 200: self.historico = self.historico[-200:]
    
    def gerar_entrada(self, motores=None):
        if motores is None: motores = {k: True for k in ['sniper_elite','elite_master','sniper','mineracao','giro','gap','sequencia','terminais','simetria','repeticao','ciclo','par_impar','duzia_dom','gap3']}
        
        resultados = []
        ests = [
            (self.sniper_elite, 'sniper_elite', 3), (self.elite_master, 'elite_master', 2),
            (self.repeticao, 'repeticao', 1), (self.ciclo, 'ciclo', 1),
            (self.par_impar, 'par_impar', 1), (self.duzia_dom, 'duzia_dom', 1),
            (self.gap3, 'gap3', 1), (self.sniper, 'sniper', 1),
            (self.mineracao, 'mineracao', 1), (self.giro, 'giro', 1),
            (self.gap, 'gap', 1), (self.sequencia, 'sequencia', 1),
            (self.terminais, 'terminais', 1), (self.simetria, 'simetria', 1),
        ]
        
        for est, key, peso in ests:
            try:
                if motores.get(key, True) and len(self.historico) >= 2:
                    r = est.analisar(list(self.historico))
                    if r and len(r.get('base', set())) >= 1:
                        resultados.append((key.replace('_',' ').title(), r, peso))
            except: pass
        
        if not resultados:
            freq = Counter(self.historico[-20:])
            quentes = [n for n, _ in freq.most_common(8)]
            return {'numeros_apostar': sorted(quentes[:12]), 'forca_real': 20, 'motor': 'Básico', 'estrategias_ativas': ['Quentes'], 'qtd_motores': 1, 'qualidade': 'BÁSICA', 'green': False, 'green_count': 0}
        
        base = set()
        ests_ativas = []
        ft, mp, mf = 0, resultados[0][0], 0
        
        for nome, r, peso in resultados:
            for _ in range(peso): base.update(r['base'])
            ests_ativas.extend(r.get('estrategias', []))
            ft += r['forca'] * peso
            if r['forca'] > mf: mf, mp = r['forca'], nome
        
        fm = int(ft / sum(p for _, _, p in resultados))
        mx = st.session_state.get('max_n_apostas', 12)
        mn = st.session_state.get('min_n_apostas', 5)
        lst = list(base)[:mx]
        while len(lst) < mn and len(lst) < 37:
            for n in range(37):
                if n not in lst: lst.append(n); break
        
        qs = fm / max(1, len(lst))
        q = "EXCELENTE" if qs >= 8 else "BOA" if qs >= 5 else "REGULAR" if qs >= 3 else "BÁSICA"
        
        return {'numeros_apostar': sorted(lst), 'forca_real': min(100, max(15, fm)), 'motor': mp, 'estrategias_ativas': list(set(ests_ativas))[:5], 'qtd_motores': len(resultados), 'qualidade': q, 'green': False, 'green_count': 0}


# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaBot:
    def __init__(self):
        self.bot = RoletaBotUnificado()
        self.historico_numeros = deque(maxlen=200)
        self.entrada_ativa = None
        self.historico_entradas = []
        self.acertos = 0
        self.erros = 0
        self.green_repeticoes = 0
        self.erro_aguardando = False
        self.ultima_entrada_numeros = []
        
    def processar_novo_numero(self, numero_data):
        nr = numero_data['number'] if isinstance(numero_data, dict) else int(numero_data)
        lucky = numero_data.get('luckyNumbers', []) if isinstance(numero_data, dict) else []
        mult = None
        is_lucky = nr in lucky if lucky else False
        
        self.bot.atualizar(nr)
        self.historico_numeros.append(nr)
        
        if self.entrada_ativa:
            acerto = nr in self.entrada_ativa.get('numeros_apostar', [])
            self.bot.performance['historico'].append(1 if acerto else 0)
            if acerto: self.bot.performance['acertos'] += 1
            else: self.bot.performance['erros'] += 1
            
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
            
            if acerto:
                self.acertos += 1
                if self.green_repeticoes < 2:
                    self.green_repeticoes += 1
                    self.ultima_entrada_numeros = list(self.entrada_ativa.get('numeros_apostar', []))
                    self.erro_aguardando = False
                else:
                    self.green_repeticoes = 0
                    self.ultima_entrada_numeros = []
            else:
                self.erros += 1
                if self.entrada_ativa.get('green', False):
                    self.green_repeticoes = 0
                    self.ultima_entrada_numeros = []
                    self.erro_aguardando = False
                else:
                    self.erro_aguardando = True
                    self.ultima_entrada_numeros = list(self.entrada_ativa.get('numeros_apostar', []))
                    self.green_repeticoes = 0
            
            enviar_resultado_auto(nr, acerto, mult, is_lucky)
            self.entrada_ativa = None
        
        # Green repeat
        if self.green_repeticoes > 0 and self.ultima_entrada_numeros:
            self.entrada_ativa = {
                'numeros_apostar': sorted(self.ultima_entrada_numeros),
                'forca_real': 65, 'motor': 'Green Repeat',
                'estrategias_ativas': [f'🟢 Green #{self.green_repeticoes}/2'],
                'qtd_motores': 1, 'qualidade': 'GREEN', 'green': True,
                'green_count': self.green_repeticoes,
            }
            enviar_previsao_auto(self.entrada_ativa)
            return
        
        # Erro repeat
        if self.erro_aguardando and self.ultima_entrada_numeros:
            self.erro_aguardando = False
            self.entrada_ativa = {
                'numeros_apostar': sorted(self.ultima_entrada_numeros),
                'forca_real': 40, 'motor': 'Erro Repeat',
                'estrategias_ativas': ['⏳ Repetindo'],
                'qtd_motores': 1, 'qualidade': 'REPEAT', 'green': False, 'green_count': 0,
            }
            self.ultima_entrada_numeros = []
            enviar_previsao_auto(self.entrada_ativa)
            return
        
        # Nova análise
        mot = {k: st.session_state.get(f'usar_{k}', True) for k in ['sniper_elite','elite_master','sniper','mineracao','giro','gap','sequencia','terminais','simetria','repeticao','ciclo','par_impar','duzia_dom','gap3']}
        self.entrada_ativa = self.bot.gerar_entrada(mot)
        if self.entrada_ativa: enviar_previsao_auto(self.entrada_ativa)
    
    def zerar(self):
        self.acertos = 0; self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear()
        self.entrada_ativa = None
        self.green_repeticoes = 0
        self.erro_aguardando = False
        self.ultima_entrada_numeros = []
        self.bot.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.bot.historico = []
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
        r = requests.get(API_URL, headers=HEADERS, timeout=5)
        r.raise_for_status()
        d = r.json()
        gd = d.get("data", {}); rs = gd.get("result", {})
        nm = rs.get("outcome", {}).get("number")
        ts = gd.get("startedAt")
        ln, lm = [], {}
        for item in rs.get('luckyNumbersList', []):
            n = item.get('number')
            if n is not None:
                ln.append(n)
                m = item.get('roundedMultiplier')
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
# APLICAÇÃO STREAMLIT - VISUAL COMPACTO
# =============================
st.set_page_config(page_title="🎯 Roleta Bot Pro", layout="wide")
st.markdown("""
<style>
    .main-header { font-size: 1.5rem; font-weight: 700; margin-bottom: 0.5rem; }
    .metric-container { background: #1a1a2e; border-radius: 10px; padding: 12px 8px; text-align: center; }
    .metric-value { font-size: 1.8rem; font-weight: 700; }
    .metric-label { font-size: 0.7rem; color: #aaa; text-transform: uppercase; }
    .numero-badge { display: inline-block; background: #16213e; color: #fff; padding: 4px 10px; border-radius: 6px; margin: 2px; font-weight: 600; font-size: 1.1rem; }
    .numero-lucky { background: #1a1a2e; border: 1px solid #f0c040; color: #f0c040; }
    .entrada-card { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 12px; padding: 15px; margin: 8px 0; border-left: 4px solid #4fc3f7; }
    .entrada-green { border-left: 4px solid #66bb6a; }
    .stButton button { border-radius: 8px; font-weight: 600; }
    hr { margin: 0.5rem 0; }
    .section-title { font-size: 0.9rem; font-weight: 600; color: #aaa; text-transform: uppercase; letter-spacing: 1px; margin: 0.5rem 0; }
</style>
""", unsafe_allow_html=True)

if "sistema" not in st.session_state or st.session_state.sistema is None:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    if not st.session_state.get('historico'): st.session_state.historico = dados.get('historico', [])
    sis = st.session_state.sistema
    sis.acertos = dados.get('sistema_acertos', 0)
    sis.erros = dados.get('sistema_erros', 0)
    sis.green_repeticoes = dados.get('green_repeticoes', 0)
    sis.erro_aguardando = dados.get('erro_aguardando', False)
    sis.ultima_entrada_numeros = dados.get('ultima_entrada_numeros', [])
    for num in dados.get('historico_numeros', []): sis.bot.atualizar(num); sis.historico_numeros.append(num)
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
    'modo_automatico': True, 'max_n_apostas': 12, 'min_n_apostas': 5,
    'usar_sniper_elite': True, 'usar_elite_master': True,
    'usar_sniper': True, 'usar_mineracao': True, 'usar_giro': True,
    'usar_gap': True, 'usar_sequencia': True, 'usar_terminais': True,
    'usar_simetria': True, 'usar_repeticao': True, 'usar_ciclo': True,
    'usar_par_impar': True, 'usar_duzia_dom': True, 'usar_gap3': True,
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

# ==========================================
# SIDEBAR COMPACTA
# ==========================================
with st.sidebar:
    st.markdown("### ⚙️ Config")
    
    with st.expander("🤖 Motores", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.session_state.usar_sniper_elite = st.checkbox("Sniper-Elite", value=st.session_state.usar_sniper_elite)
            st.session_state.usar_elite_master = st.checkbox("Elite Master", value=st.session_state.usar_elite_master)
            st.session_state.usar_sniper = st.checkbox("Sniper", value=st.session_state.usar_sniper)
            st.session_state.usar_mineracao = st.checkbox("Mineração", value=st.session_state.usar_mineracao)
            st.session_state.usar_giro = st.checkbox("Giro", value=st.session_state.usar_giro)
            st.session_state.usar_gap = st.checkbox("Gap", value=st.session_state.usar_gap)
            st.session_state.usar_sequencia = st.checkbox("Sequência", value=st.session_state.usar_sequencia)
        with c2:
            st.session_state.usar_terminais = st.checkbox("Terminais", value=st.session_state.usar_terminais)
            st.session_state.usar_simetria = st.checkbox("Simetria", value=st.session_state.usar_simetria)
            st.session_state.usar_repeticao = st.checkbox("Repetição", value=st.session_state.usar_repeticao)
            st.session_state.usar_ciclo = st.checkbox("Ciclo", value=st.session_state.usar_ciclo)
            st.session_state.usar_par_impar = st.checkbox("Par/Ímpar", value=st.session_state.usar_par_impar)
            st.session_state.usar_duzia_dom = st.checkbox("Dúzia Dom.", value=st.session_state.usar_duzia_dom)
            st.session_state.usar_gap3 = st.checkbox("Gap 3", value=st.session_state.usar_gap3)
    
    st.session_state.max_n_apostas = st.slider("Máx. números", 5, 18, st.session_state.max_n_apostas)
    st.session_state.min_n_apostas = st.slider("Mín. números", 3, 8, st.session_state.min_n_apostas)
    st.session_state.modo_automatico = st.checkbox("Modo Automático", value=st.session_state.modo_automatico)
    
    with st.expander("🔔 Telegram", expanded=False):
        st.session_state.telegram_token = st.text_input("Token", value=st.session_state.telegram_token, type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID", value=st.session_state.telegram_chat_id)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Salvar", use_container_width=True):
            salvar_resultado_em_arquivo(st.session_state.historico)
            salvar_sessao()
    with c2:
        if st.button("🗑️ Zerar", use_container_width=True):
            if st.checkbox("✓"):
                st.session_state.sistema.zerar()
                st.rerun()

# ==========================================
# CONTEÚDO PRINCIPAL COMPACTO
# ==========================================
st.markdown('<div class="main-header">🎯 Roleta Bot Pro</div>', unsafe_allow_html=True)

# Input + API
col_in, col_api = st.columns([3, 1])
with col_in:
    c1, c2 = st.columns([4, 1])
    with c1:
        entrada = st.text_input("Números (0-36):", placeholder="Ex: 12 21 14 5 22", label_visibility="collapsed", key="entrada")
    with c2:
        if st.button("➕", use_container_width=True) and entrada:
            try:
                nums = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
                for n in nums:
                    item = {"number": n, "timestamp": f"m{len(st.session_state.historico)}", "luckyNumbers": [], "luckyMultipliers": {}}
                    st.session_state.historico.append(item)
                    st.session_state.sistema.processar_novo_numero(item)
                salvar_resultado_em_arquivo(st.session_state.historico)
                salvar_sessao()
                st.rerun()
            except: pass
with col_api:
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

# Linha 1: Últimos números + Status
st.markdown('<div class="section-title">🔁 Últimos Números</div>', unsafe_allow_html=True)
if st.session_state.historico:
    ultimos = st.session_state.historico[-8:]
    nums_html = ""
    for item in ultimos:
        n = item['number'] if isinstance(item, dict) else item
        is_l = isinstance(item, dict) and n in item.get('luckyNumbers', [])
        cls = "numero-badge numero-lucky" if is_l else "numero-badge"
        nums_html += f'<span class="{cls}">{n}</span> '
    st.markdown(nums_html, unsafe_allow_html=True)

# Linha 2: Métricas compactas
sis = st.session_state.sistema
m1, m2, m3, m4, m5, m6 = st.columns(6)
tx = sis.acertos/(sis.acertos+sis.erros)*100 if (sis.acertos+sis.erros) > 0 else 0
with m1:
    st.markdown(f'<div class="metric-container"><div class="metric-value" style="color:#66bb6a">{sis.acertos}</div><div class="metric-label">Acertos</div></div>', unsafe_allow_html=True)
with m2:
    st.markdown(f'<div class="metric-container"><div class="metric-value" style="color:#ef5350">{sis.erros}</div><div class="metric-label">Erros</div></div>', unsafe_allow_html=True)
with m3:
    st.markdown(f'<div class="metric-container"><div class="metric-value">{tx:.0f}%</div><div class="metric-label">Taxa</div></div>', unsafe_allow_html=True)
with m4:
    c = "#66bb6a" if sis.green_repeticoes > 0 else "#aaa"
    st.markdown(f'<div class="metric-container"><div class="metric-value" style="color:{c}">{sis.green_repeticoes}/2</div><div class="metric-label">🟢 Green</div></div>', unsafe_allow_html=True)
with m5:
    c = "#ffa726" if sis.erro_aguardando else "#aaa"
    st.markdown(f'<div class="metric-container"><div class="metric-value" style="color:{c}">{"⏳" if sis.erro_aguardando else "✓"}</div><div class="metric-label">Erro R.</div></div>', unsafe_allow_html=True)
with m6:
    st.markdown(f'<div class="metric-container"><div class="metric-value">14</div><div class="metric-label">Motores</div></div>', unsafe_allow_html=True)

# Linha 3: Entrada Atual
st.markdown('<div class="section-title">🎯 Entrada Atual</div>', unsafe_allow_html=True)
if sis.entrada_ativa:
    e = sis.entrada_ativa
    card_class = "entrada-card entrada-green" if e.get('green') else "entrada-card"
    st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
    
    c1, c2 = st.columns([3, 1])
    with c1:
        if e.get('green'):
            st.markdown(f"### 🟢 GREEN #{e.get('green_count',0)}/2")
        else:
            emoji = "🔥" if e['forca_real'] >= 50 else "🎯" if e['forca_real'] >= 35 else "📊"
            st.markdown(f"### {emoji} {e['motor']} | {e['forca_real']}% | {e['qualidade']}")
        st.caption(f"{', '.join(e.get('estrategias_ativas', [])[:4])}")
    with c2:
        st.markdown(f"**{len(e['numeros_apostar'])} números**")
    
    st.markdown("### " + " ".join([f'<span class="numero-badge">{n}</span>' for n in sorted(e['numeros_apostar'])]), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("Aguardando próximo giro...")

# Linha 4: Histórico de entradas
st.markdown('<div class="section-title">📋 Últimas Entradas</div>', unsafe_allow_html=True)
if sis.historico_entradas:
    # Cabeçalho compacto
    col_r, col_n, col_f, col_m, col_q = st.columns([0.5, 2, 1, 1.5, 1])
    col_r.markdown("**#**")
    col_n.markdown("**Números**")
    col_f.markdown("**Res.**")
    col_m.markdown("**Motor**")
    col_q.markdown("**Q**")
    
    for entrada in reversed(sis.historico_entradas[-8:]):
        col_r, col_n, col_f, col_m, col_q = st.columns([0.5, 2, 1, 1.5, 1])
        col_r.write(entrada['rodada'])
        col_n.write(", ".join(map(str, entrada['numeros'][:4])))
        if entrada['acerto']:
            col_f.success(f"✅ {entrada['resultado']}")
        else:
            col_f.error(f"❌ {entrada['resultado']}")
        if entrada.get('green'):
            col_m.write("🟢 GREEN")
        else:
            col_m.write(entrada['motor'][:12])
        col_q.write(entrada.get('qualidade', '-'))

# Performance compacta
if sis.historico_entradas:
    with st.expander("📊 Performance por Motor", expanded=False):
        motor_stats = defaultdict(lambda: {'acertos': 0, 'total': 0})
        for e in sis.historico_entradas:
            m = e.get('motor', 'Desconhecido')
            motor_stats[m]['total'] += 1
            if e['acerto']: motor_stats[m]['acertos'] += 1
        
        cols = st.columns(min(5, len(motor_stats)))
        for i, (motor, stats) in enumerate(sorted(motor_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:5]):
            taxa = stats['acertos']/stats['total']*100 if stats['total']>0 else 0
            with cols[i]:
                st.metric(motor[:10], f"{taxa:.0f}%", f"{stats['acertos']}/{stats['total']}")

# Download
with st.expander("📥 Download", expanded=False):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("📥 JSON", exportar_historico(st.session_state.historico, 'json'), "historico.json", "application/json")
    with c2:
        st.download_button("📥 CSV", exportar_historico(st.session_state.historico, 'csv'), "historico.csv", "text/csv")
    with c3:
        st.download_button("📥 Entradas", json.dumps(sis.historico_entradas, indent=2), "entradas.json", "application/json")

salvar_sessao()
