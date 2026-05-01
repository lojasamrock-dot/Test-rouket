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
        
        performance_data = {
            'acertos': sis.acertos,
            'erros': sis.erros,
            'historico': sis.bot.performance['historico']
        }
        with open(PERFORMANCE_PATH, 'w') as f: json.dump(performance_data, f)
        with open(ENTRADAS_PATH, 'w') as f: json.dump(sis.historico_entradas, f)
        
        session_data = {
            'historico': st.session_state.get('historico', []),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'sistema_acertos': sis.acertos,
            'sistema_erros': sis.erros,
            'historico_numeros': list(sis.historico_numeros),
            'historico_lucky': list(sis.historico_lucky),
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
        
        if invertido: emoji = "🔄"
        elif forca >= 65: emoji = "🔥"
        elif forca >= 55: emoji = "🎯"
        else: emoji = "⚠️"
        
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
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage", 
            json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}, 
            timeout=10
        )
    except Exception as e:
        logging.error(f"Erro ao enviar Telegram: {e}")

# =============================
# API E ROLETA BASE
# =============================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

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
# ESTRATÉGIAS
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
        return {'base': set(list(b)[:7]), 'forca': 50+len(all_lucky)*2, 'estrategias': [f'Lucky {top[:2]}'], 'gatilho': f'Lucky {top[:2]}'}

class EstrategiaRepeticao:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        if h[-1] != h[-2]: return None
        b = {h[-1]}; b.update(self.roleta.get_vizinhos(h[-1], 1)[:3])
        return {'base': b, 'forca': 80, 'estrategias': [f'Repetição {h[-1]}'], 'gatilho': f'Repetição {h[-1]}'}

class EstrategiaGapCurto:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 3: return None
        u = h[-1]; b = set(); gap = None
        if len(h) >= 3 and h[-3] == u: b.add(u); gap = 2
        elif len(h) >= 4 and h[-4] == u: b.add(u); gap = 3
        if not b: return None
        b.update(self.roleta.get_vizinhos(u, 1)[:2])
        return {'base': b, 'forca': 55+(gap or 0)*5, 'estrategias': [f'Gap {gap}'], 'gatilho': f'Gap {gap} giros: {u}'}

class EstrategiaMineracao:
    def analisar(self, h):
        if len(h) < 5: return None
        u = h[-1]; t = defaultdict(list)
        for i in range(len(h)-1): t[h[i]].append(h[i+1])
        seg = t.get(u, [])
        if not seg: return None
        top = Counter(seg).most_common(2)
        return {'base': set([n for n, _ in top]), 'forca': 50, 'estrategias': [f'Markov {u}'], 'gatilho': f'Pós {u}'}

class EstrategiaDuziaDominante:
    def analisar(self, h):
        if len(h) < 10: return None
        cnt = Counter((n-1)//12+1 for n in h[-10:] if n != 0)
        if not cnt: return None
        d, freq = cnt.most_common(1)[0]
        if freq < 6: return None
        dz = {1: range(1,13), 2: range(13,25), 3: range(25,37)}
        return {'base': set(list(dz[d])[:6]), 'forca': 50+(freq-6)*5, 'estrategias': [f'Dúzia {d}'], 'gatilho': f'Dúzia {d} ({freq}/10)'}

class EstrategiaEspelho:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        u = h[-1]
        if u not in self.roleta.espelhos: return None
        esp = self.roleta.espelhos[u]; b = {u, esp}
        b.update(self.roleta.get_vizinhos(esp, 1)[:2])
        return {'base': b, 'forca': 50, 'estrategias': [f'Espelho {u}'], 'gatilho': f'Espelho {u}↔{esp}'}

class EstrategiaSomaCinco:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        u = h[-1]; prox = (u + 5) % 37; b = {u, prox}
        b.update(self.roleta.get_vizinhos(prox, 1)[:2])
        return {'base': b, 'forca': 50, 'estrategias': ['+5'], 'gatilho': f'Soma 5 de {u}'}

class EstrategiaLuckyAlto:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist, mult_hist):
        if not lucky_hist: return None
        b = set()
        for i in range(len(mult_hist)-1, max(-1, len(mult_hist)-10), -1):
            for n, m in mult_hist[i].items():
                if m >= 200: b.add(n)
        if not b: return None
        return {'base': b, 'forca': 60, 'estrategias': ['Lucky Alto'], 'gatilho': 'Multiplicador Alto'}

class EstrategiaCicloOito:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 8: return None
        if h[-8] == h[-1]:
            b = {h[-1]}; b.update(self.roleta.get_vizinhos(h[-1], 2))
            return {'base': b, 'forca': 55, 'estrategias': ['Ciclo 8'], 'gatilho': f'Ciclo 8: {h[-1]}'}
        return None

class EstrategiaAlternanciaCor:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 5: return None
        cores = ['V' if n in self.roleta.vermelhos else 'P' if n in self.roleta.pretos else 'Z' for n in h[-5:]]
        if all(cores[i] != cores[i-1] for i in range(1, 5)) and 'Z' not in cores:
            prox = self.roleta.pretos if cores[-1] == 'V' else self.roleta.vermelhos
            return {'base': set(list(prox)[:6]), 'forca': 55, 'estrategias': ['Alternância'], 'gatilho': 'Sequência Alternada'}
        return None

class EstrategiaSetorCilindro:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 5: return None
        setores = [self.roleta.get_setor_cilindro(n) for n in h[-5:]]
        dom, freq = Counter(setores).most_common(1)[0]
        if freq >= 3 and dom != "Zero":
            sn = {'Voisins': self.roleta.voisins, 'Tiers': self.roleta.tiers, 'Orphelins': self.roleta.orphelins}
            return {'base': set(list(sn[dom])[:6]), 'forca': 50, 'estrategias': [f'Setor {dom}'], 'gatilho': f'Setor {dom} Ativo'}
        return None

class EstrategiaZeroVirada:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 1: return None
        if h[-1] == 0:
            return {'base': {0, 32, 15, 26, 3}, 'forca': 60, 'estrategias': ['Pós-Zero'], 'gatilho': 'Zero Detectado'}
        return None

class EstrategiaPrimos:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 3: return None
        if sum(1 for n in h[-3:] if n in self.roleta.primos) >= 2:
            return {'base': set(list(self.roleta.primos)[:6]), 'forca': 50, 'estrategias': ['Primos'], 'gatilho': 'Sequência Primos'}
        return None

class EstrategiaVizinhosFisicos:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        if self.roleta.sao_vizinhos_fisicos(h[-1], h[-2]):
            b = {h[-1], h[-2]}; b.update(self.roleta.get_vizinhos(h[-1], 1))
            return {'base': b, 'forca': 55, 'estrategias': ['Vizinhos Físicos'], 'gatilho': f'Proximidade {h[-1]}'}
        return None

class EstrategiaLuckyTerminal:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if not lucky_hist or len(h) < 1: return None
        if h[-1] in lucky_hist[-1]:
            term = h[-1] % 10
            b = {n for n in range(37) if n % 10 == term}
            return {'base': b, 'forca': 55, 'estrategias': ['Lucky Terminal'], 'gatilho': f'Lucky Term {term}'}
        return None

class EstrategiaFaixaNumerica:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 5: return None
        baixos = sum(1 for n in h[-5:] if 1 <= n <= 18)
        if baixos >= 4: return {'base': set(list(self.roleta.altos)[:6]), 'forca': 50, 'estrategias': ['Faixa Alta'], 'gatilho': 'Tendência Baixa'}
        if baixos <= 1: return {'base': set(list(self.roleta.baixos)[:6]), 'forca': 50, 'estrategias': ['Faixa Baixa'], 'gatilho': 'Tendência Alta'}
        return None

class EstrategiaNumeroDoDia:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 20: return None
        top = Counter(h).most_common(2); b = {n for n, _ in top}
        for n, _ in top: b.update(self.roleta.get_vizinhos(n, 1))
        return {'base': b, 'forca': 50, 'estrategias': ['Nº do Dia'], 'gatilho': 'Números Quentes'}

# =============================
# BOT UNIFICADO
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        self.repeticao = EstrategiaRepeticao(self.roleta)
        self.lucky_vizinhos = EstrategiaLuckyVizinhos(self.roleta)
        self.vizinhos_fisicos = EstrategiaVizinhosFisicos(self.roleta)
        self.sniper_elite = EstrategiaSniperElite(self.roleta)
        self.gap_curto = EstrategiaGapCurto(self.roleta)
        self.espelho = EstrategiaEspelho(self.roleta)
        self.lucky_alto = EstrategiaLuckyAlto(self.roleta)
        self.numero_do_dia = EstrategiaNumeroDoDia(self.roleta)
        self.mineracao = EstrategiaMineracao()
        self.duzia_dom = EstrategiaDuziaDominante()
        self.soma_cinco = EstrategiaSomaCinco(self.roleta)
        self.ciclo_oito = EstrategiaCicloOito(self.roleta)
        self.alternancia_cor = EstrategiaAlternanciaCor(self.roleta)
        self.setor_cilindro = EstrategiaSetorCilindro(self.roleta)
        self.zero_virada = EstrategiaZeroVirada(self.roleta)
        self.primos = EstrategiaPrimos(self.roleta)
        self.lucky_terminal = EstrategiaLuckyTerminal(self.roleta)
        self.faixa_numerica = EstrategiaFaixaNumerica(self.roleta)
        
        self.historico = []; self.lucky = []; self.mults = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        
    def atualizar(self, n, lucky_nums=None, lucky_mults=None):
        self.historico.append(int(n))
        self.lucky.append(lucky_nums or [])
        self.mults.append(lucky_mults or {})
        if len(self.historico) > 200: self.historico = self.historico[-200:]
        if len(self.lucky) > 200: self.lucky = self.lucky[-200:]
        if len(self.mults) > 200: self.mults = self.mults[-200:]
    
    def gerar_entrada(self, motores, forcar_inversao=False):
        resultados = []
        forca_min = st.session_state.get('forca_minima_entrada', 55)
        
        ests = [
            (self.repeticao, 'Repetição', 4, [self.historico]),
            (self.lucky_vizinhos, 'Lucky Vizinhos', 3, [self.historico, self.lucky]),
            (self.vizinhos_fisicos, 'Vizinhos Físicos', 3, [self.historico]),
            (self.sniper_elite, 'Sniper Elite', 2, [self.historico, self.lucky]),
            (self.gap_curto, 'Gap Curto', 2, [self.historico]),
            (self.espelho, 'Espelho', 2, [self.historico]),
            (self.lucky_alto, 'Lucky Alto', 2, [self.historico, self.lucky, self.mults]),
            (self.numero_do_dia, 'Nº do Dia', 2, [self.historico]),
            (self.mineracao, 'Mineração', 1, [self.historico]),
            (self.duzia_dom, 'Dúzia Dom.', 1, [self.historico]),
            (self.soma_cinco, 'Soma Cinco', 1, [self.historico]),
            (self.ciclo_oito, 'Ciclo Oito', 1, [self.historico]),
            (self.alternancia_cor, 'Alternância', 1, [self.historico]),
            (self.setor_cilindro, 'Setor Cilindro', 1, [self.historico]),
            (self.zero_virada, 'Zero Virada', 1, [self.historico]),
            (self.primos, 'Primos', 1, [self.historico]),
            (self.lucky_terminal, 'Lucky Terminal', 1, [self.historico, self.lucky]),
            (self.faixa_numerica, 'Faixa Numérica', 1, [self.historico]),
        ]
        
        for est, nome, peso, args in ests:
            key = f"usar_{nome.lower().replace(' ', '_').replace('º', '').replace('ú', 'u').replace('ã', 'a').replace('ç', 'c').replace('ó', 'o').replace('ô', 'o').replace('.', '')}"
            if motores.get(key, True):
                try:
                    r = est.analisar(*args)
                    if r and r['base'] and r['forca'] >= forca_min:
                        resultados.append((nome, r, peso))
                except: pass

        if not resultados: return None
        
        mx = st.session_state.get('max_n_apostas', 7)
        consenso = Counter()
        for _, r, peso in resultados:
            for n in r['base']: consenso[n] += peso
        
        lst = [n for n, _ in consenso.most_common(mx)]
        fm = int(sum(r['forca']*p for _, r, p in resultados) / sum(p for _, _, p in resultados))
        
        entrada = {
            'numeros_apostar': sorted(lst),
            'forca_real': min(100, fm),
            'motor': resultados[0][0],
            'estrategias_ativas': [r[0] for r in resultados[:3]],
            'gatilho': resultados[0][1]['gatilho'],
            'invertido': False
        }
        
        if forcar_inversao:
            entrada = self._inverter_entrada(entrada)
        return entrada

    def _inverter_entrada(self, entrada):
        originais = set(entrada['numeros_apostar'])
        disponiveis = list(set(range(37)) - originais)
        random.shuffle(disponiveis)
        entrada['numeros_apostar'] = sorted(disponiveis[:len(originais)])
        entrada['motor'] = f"🔄 {entrada['motor']} (Inv)"
        entrada['invertido'] = True
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
        else:
            nr = int(numero_data); lucky, lucky_mults = [], {}
        
        if self.entrada_ativa:
            acerto = nr in self.entrada_ativa['numeros_apostar']
            if acerto: 
                self.acertos += 1
                self.bot.performance['acertos'] += 1
            else: 
                self.erros += 1
                self.bot.performance['erros'] += 1
                if st.session_state.get('modo_inversao_auto', False):
                    self.estado_inversao = not self.estado_inversao
            
            self.historico_entradas.append({
                'rodada': len(self.historico_numeros),
                'resultado': nr, 'acerto': acerto,
                'motor': self.entrada_ativa['motor'],
                'invertido': self.entrada_ativa['invertido'],
                'gatilho': self.entrada_ativa['gatilho']
            })
            enviar_resultado_auto(nr, acerto)

        self.bot.atualizar(nr, lucky, lucky_mults)
        self.historico_numeros.append(nr)
        self.historico_lucky.append(lucky)
        self.historico_mults.append(lucky_mults)
        
        mot = {k: st.session_state.get(k, True) for k in st.session_state if k.startswith('usar_')}
        forcar = st.session_state.get('modo_inversao_auto', False) and self.estado_inversao
        self.entrada_ativa = self.bot.gerar_entrada(mot, forcar)
        if self.entrada_ativa: enviar_previsao_auto(self.entrada_ativa)
        salvar_sessao()

    def zerar(self):
        self.acertos = 0; self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear()
        self.estado_inversao = False
        self.entrada_ativa = None
        limpar_sessao()

# =============================
# Streamlit UI
# =============================
st.set_page_config(page_title="🎯 Roleta Bot Pro v16", layout="centered")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()
    dados = carregar_dados_persistidos()
    if dados:
        sis = st.session_state.sistema
        sis.acertos = dados.get('sistema_acertos', 0)
        sis.erros = dados.get('sistema_erros', 0)
        sis.estado_inversao = dados.get('estado_inversao', False)
        for n, l in zip(dados.get('historico_numeros', []), dados.get('historico_lucky', [])):
            sis.bot.atualizar(n, l)
            sis.historico_numeros.append(n)
            sis.historico_lucky.append(l)
        st.session_state.historico = dados.get('historico', [])

st_autorefresh(interval=5000, key="bot_refresh")

with st.sidebar:
    st.subheader("⚙️ Configurações")
    st.session_state.modo_inversao_auto = st.checkbox("🔄 Inversão Auto", value=st.session_state.get('modo_inversao_auto', False))
    st.session_state.forca_minima_entrada = st.slider("⚡ Força", 45, 65, st.session_state.get('forca_minima_entrada', 55))
    st.session_state.max_n_apostas = st.slider("📊 Máx Números", 5, 18, st.session_state.get('max_n_apostas', 7))
    if st.button("🗑️ Limpar Tudo"):
        st.session_state.sistema.zerar()
        st.rerun()

def fetch_latest_result():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=5).json()
        data = r.get("data", {}).get("result", {})
        num = data.get("outcome", {}).get("number")
        ts = r.get("data", {}).get("startedAt")
        lucky = [item.get('number') for item in data.get('luckyNumbersList', [])]
        return {"number": num, "timestamp": ts, "luckyNumbers": lucky}
    except: return None

res = fetch_latest_result()
if res and (not st.session_state.get('historico') or res['timestamp'] != st.session_state.historico[-1].get('timestamp')):
    if "historico" not in st.session_state: st.session_state.historico = []
    st.session_state.historico.append(res)
    st.session_state.sistema.processar_novo_numero(res)

st.title("🎯 Roleta Bot Pro v16")
sis = st.session_state.sistema

c1, c2, c3, c4 = st.columns(4)
c1.metric("🟢 Acertos", sis.acertos)
c2.metric("🔴 Erros", sis.erros)
c3.metric("🔄 Inversão", "Ativa" if sis.estado_inversao else "Normal")
c4.metric("Último", sis.historico_numeros[-1] if sis.historico_numeros else "-")

if sis.entrada_ativa:
    e = sis.entrada_ativa
    color = "#FF4B4B" if e['invertido'] else "#00CC96"
    st.markdown(f"""
    <div style="background-color:rgba(0,0,0,0.05);padding:20px;border-radius:10px;border-left:8px solid {color}">
        <h3>🎯 Sugestão: {e['motor']} ({e['forca_real']}%)</h3>
        <h1 style="letter-spacing: 5px; color: {color};">{', '.join(map(str, e['numeros_apostar']))}</h1>
        <p>Gatilho: {e['gatilho']}</p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.info("Aguardando nova rodada...")

if sis.historico_entradas:
    st.subheader("📋 Últimas Entradas")
    for ent in reversed(sis.historico_entradas[-5:]):
        st.write(f"{'✅' if ent['acerto'] else '❌'} Num: {ent['resultado']} | {ent['motor']} {'(Invertido)' if ent['invertido'] else ''}")

salvar_sessao()
