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
    try:
        if 'sistema' not in st.session_state or st.session_state.sistema is None:
            return False
        
        sis = st.session_state.sistema
        session_data = {
            'historico': st.session_state.get('historico', []),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'sistema_acertos': sis.acertos,
            'sistema_erros': sis.erros,
            'historico_numeros': list(sis.historico_numeros),
            'historico_lucky': list(sis.historico_lucky),
            'historico_mults': list(sis.historico_mults),
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'max_n_apostas': st.session_state.get('max_n_apostas', 7),
            'min_n_apostas': st.session_state.get('min_n_apostas', 4),
            'forca_minima_entrada': st.session_state.get('forca_minima_entrada', 55),
            'limitar_numeros_altos': st.session_state.get('limitar_numeros_altos', True),
            'evitar_zero': st.session_state.get('evitar_zero', True),
            'max_gatilhos': st.session_state.get('max_gatilhos', 2),
            'modo_inversao_auto': st.session_state.get('modo_inversao_auto', False),
            'estado_inversao': sis.estado_inversao,
        }
        
        with open(SESSION_DATA_PATH, 'wb') as f: 
            pickle.dump(session_data, f)
            
        # Salva performance e entradas separadamente para redundância
        performance_data = {'acertos': sis.acertos, 'erros': sis.erros, 'historico': sis.bot.performance['historico']}
        with open(PERFORMANCE_PATH, 'w') as f: json.dump(performance_data, f)
        with open(ENTRADAS_PATH, 'w') as f: json.dump(sis.historico_entradas, f)
        
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar: {e}")
        return False

def carregar_dados_persistidos():
    try:
        if os.path.exists(SESSION_DATA_PATH):
            with open(SESSION_DATA_PATH, 'rb') as f: 
                return pickle.load(f)
    except Exception as e:
        logging.error(f"Erro ao carregar: {e}")
    return None

def limpar_sessao():
    try:
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH, ENTRADAS_PATH]:
            if os.path.exists(path): os.remove(path)
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
        emoji = "🔄" if invertido else ("🔥" if forca >= 65 else "🎯")
        
        st.toast(f"{emoji} {motor} - {forca}%")
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            tag = "[INVERTIDO]" if invertido else ""
            enviar_telegram(f"🔔 {tag} F{forca}% | {motor}\n{gatilho}\n🔢 " + " ".join(map(str, numeros)))
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
        self.voisins = {22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25}
        self.tiers = {27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33}
        self.orphelins = {1, 20, 14, 31, 9, 17, 34, 6}
        self.primos = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}
        self.baixos = set(range(1, 19)); self.altos = set(range(19, 37))
        self.numeros_problematicos = {0, 32, 33, 34, 35}
        self.max_problematicos = 2
    def get_vizinhos(self, n, r=2):
        if n not in self.race: return []
        i = self.race.index(n)
        return [self.race[(i + j) % 37] for j in range(-r, r + 1)]
    def get_setor_cilindro(self, n):
        if n in self.voisins: return "Voisins"
        if n in self.tiers: return "Tiers"
        if n in self.orphelins: return "Orphelins"
        return "Zero"
    def sao_vizinhos_fisicos(self, a, b, d=1):
        if a not in self.race or b not in self.race: return False
        ia, ib = self.race.index(a), self.race.index(b)
        diff = abs(ia - ib)
        return diff <= d or diff >= 37 - d

# =============================
# ESTRATÉGIAS (COMPACTADAS)
# =============================
class EstrategiaSniperElite:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if len(h) < 6: return None
        termos = [n%10 for n in h[-8:]]; contagem = Counter(termos)
        td, freq = contagem.most_common(1)[0]
        if freq < 3: return None
        aposta = set(); aposta.update(self.roleta.get_vizinhos(h[-1], 1)[:2])
        for n in range(37):
            if n%10 == td: aposta.add(n)
            if len(aposta) >= 7: break
        return {'base': set(list(aposta)[:7]), 'forca': 50+freq*5, 'estrategias': [f'Terminal {td}'], 'gatilho': f'Terminal {td} ({freq}x)'}

class EstrategiaLuckyVizinhos:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if len(h) < 3 or not lucky_hist: return None
        all_lucky = [n for sub in lucky_hist[-10:] for n in sub]
        if not all_lucky: return None
        freq = Counter(all_lucky); top = [n for n, _ in freq.most_common(3)]
        b = set(top)
        for n in top[:2]: b.update(self.roleta.get_vizinhos(n, 1)[:1])
        return {'base': set(list(b)[:7]), 'forca': 55, 'estrategias': [f'Lucky Viz'], 'gatilho': f'Lucky {top[:2]}'}

class EstrategiaRepeticao:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        if h[-1] == h[-2]:
            b = set([h[-1]]); b.update(self.roleta.get_vizinhos(h[-1], 2))
            return {'base': b, 'forca': 80, 'estrategias': ['Repetição'], 'gatilho': f'Repetição {h[-1]}'}
        return None

class EstrategiaGapCurto:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 5: return None
        u = h[-1]
        for g in [2, 3, 4]:
            if h[-(g+1)] == u:
                b = {u}; b.update(self.roleta.get_vizinhos(u, 1))
                return {'base': b, 'forca': 55+g*5, 'estrategias': [f'Gap {g}'], 'gatilho': f'Gap {g} em {u}'}
        return None

class EstrategiaMineracao:
    def analisar(self, h):
        if len(h) < 10: return None
        u = h[-1]; t = defaultdict(list)
        for i in range(len(h)-1): t[h[i]].append(h[i+1])
        seg = t.get(u, [])
        if not seg: return None
        top = Counter(seg).most_common(2)
        return {'base': {n for n, c in top}, 'forca': 50, 'estrategias': ['Markov'], 'gatilho': f'Padrão após {u}'}

class EstrategiaDuziaDominante:
    def analisar(self, h):
        if len(h) < 10: return None
        cnt = Counter((n-1)//12+1 for n in h[-10:] if n != 0)
        d, freq = cnt.most_common(1)[0]
        if freq >= 6:
            dz = {1: range(1,13), 2: range(13,25), 3: range(25,37)}
            return {'base': set(list(dz[d])[:6]), 'forca': 50+freq*5, 'estrategias': [f'Dúzia {d}'], 'gatilho': f'Dúzia {d} dominante'}
        return None

class EstrategiaEspelho:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 1: return None
        u = h[-1]
        if u in self.roleta.espelhos:
            esp = self.roleta.espelhos[u]
            b = {esp}; b.update(self.roleta.get_vizinhos(esp, 1))
            return {'base': b, 'forca': 60, 'estrategias': ['Espelho'], 'gatilho': f'Espelho {u}→{esp}'}
        return None

class EstrategiaSomaCinco:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        if (h[-2] + 5) % 37 == h[-1]:
            prox = (h[-1] + 5) % 37
            b = {prox}; b.update(self.roleta.get_vizinhos(prox, 1))
            return {'base': b, 'forca': 65, 'estrategias': ['Soma 5'], 'gatilho': 'Sequência +5'}
        return None

class EstrategiaLuckyAlto:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist, mult_hist):
        if not lucky_hist or not mult_hist: return None
        for i in range(1, min(5, len(lucky_hist))):
            for n in lucky_hist[-i]:
                if mult_hist[-i].get(n, 0) >= 200:
                    b = {n}; b.update(self.roleta.get_vizinhos(n, 1))
                    return {'base': b, 'forca': 70, 'estrategias': ['Lucky Alto'], 'gatilho': f'Multiplicador {mult_hist[-i][n]}x'}
        return None

class EstrategiaCicloOito:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 9: return None
        if h[-1] == h[-9]:
            b = {h[-1]}; b.update(self.roleta.get_vizinhos(h[-1], 1))
            return {'base': b, 'forca': 60, 'estrategias': ['Ciclo 8'], 'gatilho': 'Repetição Ciclo 8'}
        return None

class EstrategiaAlternanciaCor:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 6: return None
        cores = [1 if n in self.roleta.vermelhos else 0 for n in h[-6:] if n != 0]
        if len(cores) < 5: return None
        if all(cores[i] != cores[i-1] for i in range(1, len(cores))):
            alvo = self.roleta.pretos if cores[-1] == 1 else self.roleta.vermelhos
            return {'base': set(list(alvo)[:6]), 'forca': 55, 'estrategias': ['Alternância'], 'gatilho': 'Troca de Cor'}
        return None

class EstrategiaSetorCilindro:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 5: return None
        setores = [self.roleta.get_setor_cilindro(n) for n in h[-5:]]
        dom, freq = Counter(setores).most_common(1)[0]
        if freq >= 4 and dom != "Zero":
            sets = {"Voisins": self.roleta.voisins, "Tiers": self.roleta.tiers, "Orphelins": self.roleta.orphelins}
            return {'base': set(list(sets[dom])[:6]), 'forca': 50, 'estrategias': [f'Setor {dom}'], 'gatilho': f'Dominância {dom}'}
        return None

class EstrategiaZeroVirada:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 1: return None
        if h[-1] == 0:
            return {'base': {0, 32, 15, 26, 3, 35}, 'forca': 60, 'estrategias': ['Pós-Zero'], 'gatilho': 'Zero saiu'}
        return None

class EstrategiaPrimos:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 4: return None
        if all(n in self.roleta.primos for n in h[-3:]):
            return {'base': self.roleta.primos, 'forca': 50, 'estrategias': ['Primos'], 'gatilho': 'Sequência Primos'}
        return None

class EstrategiaVizinhosFisicos:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        if self.roleta.sao_vizinhos_fisicos(h[-1], h[-2]):
            b = {h[-1], h[-2]}; b.update(self.roleta.get_vizinhos(h[-1], 1))
            return {'base': b, 'forca': 60, 'estrategias': ['Viz. Físicos'], 'gatilho': f'Vizinhos {h[-2]} e {h[-1]}'}
        return None

class EstrategiaLuckyTerminal:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if not h or not lucky_hist: return None
        lucky_recente = [n for sub in lucky_hist[-3:] for n in sub]
        for n in lucky_recente:
            t = n % 10
            if h[-1] % 10 == t:
                return {'base': {x for x in range(37) if x % 10 == t}, 'forca': 55, 'estrategias': ['Lucky Term'], 'gatilho': f'Terminal {t} Ativo'}
        return None

class EstrategiaFaixaNumerica:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 6: return None
        baixos = sum(1 for n in h[-6:] if 1 <= n <= 18)
        if baixos >= 5: return {'base': set(list(self.roleta.altos)[:6]), 'forca': 50, 'estrategias': ['Faixa'], 'gatilho': 'Tendência Baixos'}
        if baixos <= 1: return {'base': set(list(self.roleta.baixos)[:6]), 'forca': 50, 'estrategias': ['Faixa'], 'gatilho': 'Tendência Altos'}
        return None

class EstrategiaNumeroDoDia:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 30: return None
        top = Counter(h[-50:]).most_common(1)[0]
        if top[1] >= 4:
            b = {top[0]}; b.update(self.roleta.get_vizinhos(top[0], 2))
            return {'base': b, 'forca': 50, 'estrategias': ['Nº Dia'], 'gatilho': f'Frequência de {top[0]}'}
        return None

# =============================
# BOT UNIFICADO
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        self.historico = []; self.lucky = []; self.mults = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        
    def atualizar(self, n, lucky_nums=None, lucky_mults=None):
        self.historico.append(int(n))
        self.lucky.append(lucky_nums if lucky_nums else [])
        self.mults.append(lucky_mults if lucky_mults else {})
        if len(self.historico) > 200: self.historico = self.historico[-200:]
        if len(self.lucky) > 200: self.lucky = self.lucky[-200:]
        if len(self.mults) > 200: self.mults = self.mults[-200:]
    
    def gerar_entrada(self, motores=None, forcar_inversao=False):
        if not self.historico: return None
        h = self.historico
        l = self.lucky
        m = self.mults
        
        # Instanciar e analisar
        resultados = []
        ests = [
            (EstrategiaRepeticao(self.roleta), 'repeticao', 4, [h]),
            (EstrategiaLuckyVizinhos(self.roleta), 'lucky_vizinhos', 3, [h, l]),
            (EstrategiaVizinhosFisicos(self.roleta), 'vizinhos_fisicos', 3, [h]),
            (EstrategiaSniperElite(self.roleta), 'sniper_elite', 2, [h, l]),
            (EstrategiaGapCurto(self.roleta), 'gap_curto', 2, [h]),
            (EstrategiaEspelho(self.roleta), 'espelho', 2, [h]),
            (EstrategiaLuckyAlto(self.roleta), 'lucky_alto', 2, [h, l, m]),
            (EstrategiaNumeroDoDia(self.roleta), 'numero_do_dia', 2, [h]),
            (EstrategiaMineracao(), 'mineracao', 1, [h]),
            (EstrategiaDuziaDominante(), 'duzia_dom', 1, [h]),
            (EstrategiaSomaCinco(self.roleta), 'soma_cinco', 1, [h]),
            (EstrategiaCicloOito(self.roleta), 'ciclo_oito', 1, [h]),
            (EstrategiaAlternanciaCor(self.roleta), 'alternancia_cor', 1, [h]),
            (EstrategiaSetorCilindro(self.roleta), 'setor_cilindro', 1, [h]),
            (EstrategiaZeroVirada(self.roleta), 'zero_virada', 1, [h]),
            (EstrategiaPrimos(self.roleta), 'primos', 1, [h]),
            (EstrategiaLuckyTerminal(self.roleta), 'lucky_terminal', 1, [h, l]),
            (EstrategiaFaixaNumerica(self.roleta), 'faixa_numerica', 1, [h]),
        ]
        
        for est_obj, key, peso, args in ests:
            if motores.get(f"usar_{key}", True):
                res = est_obj.analisar(*args)
                if res and res['base']:
                    resultados.append((key, res, peso))
        
        if not resultados: return None
        
        # Consenso
        consenso = Counter()
        total_forca = 0
        total_peso = 0
        gatilhos = []
        
        for key, res, peso in resultados:
            for n in res['base']: consenso[n] += peso
            total_forca += res['forca'] * peso
            total_peso += peso
            if 'gatilho' in res: gatilhos.append(res['gatilho'])
            
        mx = st.session_state.get('max_n_apostas', 7)
        final_nums = [n for n, _ in consenso.most_common(mx)]
        
        entrada = {
            'numeros_apostar': sorted(final_nums),
            'forca_real': int(total_forca / total_peso),
            'motor': resultados[0][0].replace('_', ' ').title(),
            'gatilho': " | ".join(gatilhos[:2]),
            'invertido': False
        }
        
        if forcar_inversao:
            todos = set(range(37))
            fora = list(todos - set(final_nums))
            random.shuffle(fora)
            entrada['numeros_apostar'] = sorted(fora[:len(final_nums)])
            entrada['invertido'] = True
            entrada['motor'] = f"🔄 {entrada['motor']} (Inv)"
            
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
        self.acertos = 0; self.erros = 0
        self.estado_inversao = False
        
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data['number']
            lucky = numero_data.get('luckyNumbers', [])
            lucky_mults = numero_data.get('luckyMultipliers', {})
            is_lucky = nr in lucky
        else:
            nr = int(numero_data); lucky, lucky_mults, is_lucky = [], {}, False
        
        # Validar duplicata de timestamp para evitar persistência infinita no refresh
        self.bot.atualizar(nr, lucky, lucky_mults)
        self.historico_numeros.append(nr)
        self.historico_lucky.append(lucky)
        self.historico_mults.append(lucky_mults)
        
        if self.entrada_ativa:
            acerto = nr in self.entrada_ativa['numeros_apostar']
            if acerto: self.acertos += 1
            else: self.erros += 1
            
            # Lógica Inversão
            if st.session_state.get('modo_inversao_auto', False):
                if not acerto: self.estado_inversao = not self.estado_inversao
            
            self.historico_entradas.append({
                'rodada': len(self.historico_numeros),
                'resultado': nr, 'acerto': acerto,
                'motor': self.entrada_ativa['motor'],
                'invertido': self.entrada_ativa['invertido'],
                'gatilho': self.entrada_ativa['gatilho']
            })
            enviar_resultado_auto(nr, acerto, is_lucky)
            self.entrada_ativa = None
            
        mot = {k: st.session_state.get(k, True) for k in st.session_state if k.startswith('usar_')}
        forcar = st.session_state.get('modo_inversao_auto', False) and self.estado_inversao
        self.entrada_ativa = self.bot.gerar_entrada(mot, forcar)
        if self.entrada_ativa: enviar_previsao_auto(self.entrada_ativa)
        salvar_sessao()

    def zerar(self):
        self.acertos = 0; self.erros = 0
        self.historico_entradas = []; self.historico_numeros.clear()
        self.estado_inversao = False; self.entrada_ativa = None
        limpar_sessao()

# =============================
# INTERFACE STREAMLIT
# =============================
st.set_page_config(page_title="Roleta Bot Elite", layout="centered")

# 1. Inicialização do Sistema
if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()
    # Tenta carregar dados persistidos imediatamente
    dados = carregar_dados_persistidos()
    if dados:
        sis = st.session_state.sistema
        sis.acertos = dados.get('sistema_acertos', 0)
        sis.erros = dados.get('sistema_erros', 0)
        sis.estado_inversao = dados.get('estado_inversao', False)
        sis.historico_entradas = dados.get('historico_entradas', [])
        for n, l, m in zip(dados.get('historico_numeros', []), dados.get('historico_lucky', []), dados.get('historico_mults', [])):
            sis.bot.atualizar(n, l, m)
            sis.historico_numeros.append(n)
            sis.historico_lucky.append(l)
            sis.historico_mults.append(m)
        st.session_state.historico = dados.get('historico', [])

# 2. Configurações e Sidebar
with st.sidebar:
    st.title("⚙️ Painel")
    st.session_state.modo_inversao_auto = st.checkbox("🔄 Inversão Automática", value=st.session_state.get('modo_inversao_auto', False))
    st.session_state.max_n_apostas = st.slider("Números", 4, 18, st.session_state.get('max_n_apostas', 7))
    
    with st.expander("🤖 Motores"):
        chks = ['repeticao', 'lucky_vizinhos', 'vizinhos_fisicos', 'sniper_elite', 'gap_curto', 'espelho', 'lucky_alto']
        for c in chks:
            key = f"usar_{c}"
            st.session_state[key] = st.checkbox(c.replace('_',' ').title(), value=st.session_state.get(key, True))
            
    if st.button("🗑️ Reset Total"):
        st.session_state.sistema.zerar()

# 3. Lógica de Refresh e API
st_autorefresh(interval=5000, key="bot_refresh")

res = fetch_latest_result()
if res:
    # Persistência de Janela: Só processa se o timestamp for novo
    last_ts = st.session_state.get('last_api_ts')
    if res['timestamp'] != last_ts:
        st.session_state.last_api_ts = res['timestamp']
        if "historico" not in st.session_state: st.session_state.historico = []
        st.session_state.historico.append(res)
        st.session_state.sistema.processar_novo_numero(res)

# 4. Display Principal
sis = st.session_state.sistema
c1, c2, c3 = st.columns(3)
c1.metric("Acertos", sis.acertos)
c2.metric("Erros", sis.erros)
c3.metric("Modo", "🔄 Invertido" if sis.estado_inversao else "📊 Normal")

if sis.entrada_ativa:
    e = sis.entrada_ativa
    st.info(f"### {e['motor']} | {e['forca_real']}%")
    st.markdown(f"## {', '.join(map(str, e['numeros_apostar']))}")
    st.caption(f"🎯 {e['gatilho']}")

st.write("---")
if sis.historico_entradas:
    for ent in reversed(sis.historico_entradas[-5:]):
        st.write(f"{'✅' if ent['acerto'] else '❌'} | Nº {ent['resultado']} | {ent['motor']}")

salvar_sessao()
