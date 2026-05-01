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
            'max_n_apostas': st.session_state.get('max_n_apostas', 9),
            'min_n_apostas': st.session_state.get('min_n_apostas', 5),
            'forca_minima_entrada': st.session_state.get('forca_minima_entrada', 55),
            'limitar_numeros_altos': st.session_state.get('limitar_numeros_altos', True),
            'evitar_zero': st.session_state.get('evitar_zero', True),
            'modo_inversao_auto': st.session_state.get('modo_inversao_auto', False),
            'estado_inversao': st.session_state.sistema.estado_inversao,
            'evitar_terminal_zero': st.session_state.get('evitar_terminal_zero', True),
            'pausa_apos_erros': st.session_state.get('pausa_apos_erros', True),
            'erros_consecutivos': st.session_state.sistema.erros_consecutivos,
            'rodadas_pausa': st.session_state.sistema.rodadas_pausa,
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
        invertido = previsao.get('invertido', False)
        if invertido: emoji = "🔄"
        elif forca >= 70: emoji = "🔥"
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
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}, timeout=10)
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
    def get_vizinhos(self, n, r=1):
        if n not in self.race: return []
        i = self.race.index(n)
        return [self.race[(i + j) % 37] for j in range(-r, r + 1)]
    def get_setor_cilindro(self, n):
        if n in self.voisins: return "Voisins"
        if n in self.tiers: return "Tiers"
        if n in self.orphelins: return "Orphelins"
        return "Zero"


# =============================
# BOT UNIFICADO
# =============================
class EstrategiaLuckyVizinhos:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if len(h) < 3 or not lucky_hist: return None
        all_lucky = [n for sub in lucky_hist[-10:] for n in sub]
        if len(all_lucky) < 2: return None
        freq = Counter(all_lucky); recentes = set(h[-3:])
        lucky_rec = [n for n in freq if n in recentes]
        top = sorted(lucky_rec, key=lambda x: freq[x], reverse=True)[:3] if lucky_rec else [n for n, _ in freq.most_common(3)]
        b = set(top)
        for n in top[:2]: b.update(self.roleta.get_vizinhos(n, 1)[:1])
        for n, _ in Counter(h[-5:]).most_common(2): b.add(n)
        return {'base': set(list(b)[:9]), 'forca': 50+len(all_lucky)*2, 'estrategias': [f'Lucky {top[:2]}'], 'gatilho': f'Lucky {top[:2]}'}

class EstrategiaSniperElite:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if len(h) < 6: return None
        termos = [n%10 for n in h[-8:]]; contagem = Counter(termos)
        td, freq = contagem.most_common(1)[0]
        # Evita Terminal 0 se configurado
        if st.session_state.get('evitar_terminal_zero', True) and td == 0:
            # Pega o segundo terminal mais frequente
            if len(contagem) > 1:
                td, freq = contagem.most_common(2)[1]
            else:
                return None
        if freq < 3: return None
        aposta = set(); aposta.update(self.roleta.get_vizinhos(h[-1], 1)[:2])
        for n in range(37):
            if n%10 == td: aposta.add(n)
            if len(aposta) >= 7: break
        if lucky_hist:
            all_lucky = [n for sub in lucky_hist[-8:] for n in sub]
            for n, _ in Counter(all_lucky).most_common(2): aposta.add(n)
        return {'base': set(list(aposta)[:9]), 'forca': 50+freq*5, 'estrategias': [f'Terminal {td}'], 'gatilho': f'Terminal {td} ({freq}x)'}

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


class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        self.lucky_vizinhos = EstrategiaLuckyVizinhos(self.roleta)
        self.sniper_elite = EstrategiaSniperElite(self.roleta)
        self.repeticao = EstrategiaRepeticao(self.roleta)
        self.gap_curto = EstrategiaGapCurto(self.roleta)
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
    
    def gerar_entrada(self, motores=None, forcar_inversao=False):
        resultados = []
        forca_min = st.session_state.get('forca_minima_entrada', 55)
        
        ests = [
            (self.repeticao, 'Repetição', 4, [list(self.historico)]),
            (self.lucky_vizinhos, 'Lucky Vizinhos', 3, [list(self.historico), self.lucky]),
            (self.sniper_elite, 'Sniper Elite', 2, [list(self.historico), self.lucky]),
            (self.gap_curto, 'Gap Curto', 2, [list(self.historico)]),
        ]
        
        for est, nome, peso, args in ests:
            try:
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
        mx = st.session_state.get('max_n_apostas', 9)
        mn = st.session_state.get('min_n_apostas', 5)
        
        consenso = Counter()
        for nome, r, peso in resultados:
            for n in r['base']: consenso[n] += peso
        
        lst = [n for n, _ in consenso.most_common(mx)]
        
        if st.session_state.get('evitar_zero', True):
            if 0 in lst and 'Zero' not in ' '.join(gatilhos) and len(lst) > mn: lst.remove(0)
        
        while len(lst) < mn and len(lst) < 37:
            for n in range(37):
                if n not in lst and n not in {0, 32, 33, 34, 35}: lst.append(n); break
        
        qs = fm / max(1, len(lst))
        q = "EXCELENTE" if qs >= 12 else "BOA" if qs >= 8 else "REGULAR"
        
        entrada = {
            'numeros_apostar': sorted(lst),
            'forca_real': min(100, max(35, fm)),
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
        numeros_invertidos = todos_numeros - numeros_originais
        qtd = len(entrada['numeros_apostar'])
        invertidos_list = sorted(list(numeros_invertidos))
        nao_problematicos = [n for n in invertidos_list if n not in {0, 32, 33, 34, 35}]
        problematicos = [n for n in invertidos_list if n in {0, 32, 33, 34, 35}]
        final = nao_problematicos[:qtd]
        if len(final) < qtd: final.extend(problematicos[:qtd - len(final)])
        entrada['numeros_apostar'] = sorted(final[:qtd])
        entrada['motor'] = f"🔄 {entrada['motor']} (Inv)"
        entrada['invertido'] = True
        entrada['gatilho'] = f"🔄 INV: {entrada['gatilho']}"
        return entrada
    
    def get_analise(self):
        """Retorna análise completa do histórico para a interface"""
        if len(self.historico) < 3:
            return None
        
        h = self.historico
        ultimo = h[-1]
        ultimos_5 = h[-5:] if len(h) >= 5 else h
        ultimos_10 = h[-10:] if len(h) >= 10 else h
        ultimos_20 = h[-20:] if len(h) >= 20 else h
        
        # Frequências
        freq_5 = Counter(ultimos_5)
        freq_10 = Counter(ultimos_10)
        freq_20 = Counter(ultimos_20)
        
        # Terminais
        termos_6 = [n%10 for n in h[-6:]]
        term_freq = Counter(termos_6)
        term_dom, term_count = term_freq.most_common(1)[0]
        
        # Cores
        cores_10 = ['V' if n in self.roleta.vermelhos else 'P' if n in self.roleta.pretos else 'Z' for n in ultimos_10]
        count_V = cores_10.count('V')
        count_P = cores_10.count('P')
        
        # Par/Ímpar
        pares_10 = sum(1 for n in ultimos_10 if n%2==0 and n!=0)
        impares_10 = sum(1 for n in ultimos_10 if n%2==1)
        
        # Dúzias
        duzias_10 = Counter((n-1)//12+1 for n in ultimos_10 if n!=0)
        
        # Setores
        setores_10 = Counter(self.roleta.get_setor_cilindro(n) for n in ultimos_10)
        
        # Lucky Numbers recentes
        lucky_rec = []
        for sub in self.lucky[-10:]: lucky_rec.extend(sub)
        lucky_freq = Counter(lucky_rec)
        
        # Quentes
        quentes_5 = [n for n, _ in freq_5.most_common(5)]
        quentes_10 = [n for n, _ in freq_10.most_common(8)]
        
        # Atrasados
        atrasados = [n for n in range(37) if n not in ultimos_20][:5]
        
        return {
            'ultimo': ultimo,
            'ultimos_10': ultimos_10,
            'freq_10': freq_10,
            'quentes_5': quentes_5,
            'quentes_10': quentes_10,
            'atrasados': atrasados,
            'term_dom': term_dom,
            'term_count': term_count,
            'count_V': count_V,
            'count_P': count_P,
            'pares_10': pares_10,
            'impares_10': impares_10,
            'duzias_10': duzias_10,
            'setores_10': setores_10,
            'lucky_freq': lucky_freq,
            'taxa_acerto': self.performance['acertos']/(self.performance['acertos']+self.performance['erros'])*100 if (self.performance['acertos']+self.performance['erros'])>0 else 0,
            'total_tentativas': self.performance['acertos']+self.performance['erros'],
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
        self.estado_inversao = False
        self.erros_consecutivos = 0
        self.rodadas_pausa = 0
        
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
        
        # Decrementa pausa
        if self.rodadas_pausa > 0:
            self.rodadas_pausa -= 1
        
        if self.entrada_ativa:
            acerto = nr in self.entrada_ativa.get('numeros_apostar', [])
            if acerto:
                self.acertos += 1; self.bot.performance['acertos'] += 1
                self.erros_consecutivos = 0
            else:
                self.erros += 1; self.bot.performance['erros'] += 1
                self.erros_consecutivos += 1
            
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
                'invertido': self.entrada_ativa.get('invertido', False),
            })
            if len(self.historico_entradas) > 50: self.historico_entradas = self.historico_entradas[-50:]
            
            if st.session_state.get('modo_inversao_auto', False):
                if not acerto:
                    self.estado_inversao = not self.estado_inversao
            
            # Pausa após 3 erros consecutivos
            if st.session_state.get('pausa_apos_erros', True) and self.erros_consecutivos >= 3:
                self.rodadas_pausa = 3
                self.erros_consecutivos = 0
            
            enviar_resultado_auto(nr, acerto, is_lucky)
            self.entrada_ativa = None
        
        # Verifica pausa
        if self.rodadas_pausa > 0:
            return
        
        forcar_inversao = st.session_state.get('modo_inversao_auto', False) and self.estado_inversao
        self.entrada_ativa = self.bot.gerar_entrada(None, forcar_inversao)
        if self.entrada_ativa: enviar_previsao_auto(self.entrada_ativa)
    
    def zerar(self):
        self.acertos = 0; self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear(); self.historico_lucky.clear(); self.historico_mults.clear()
        self.entrada_ativa = None
        self.estado_inversao = False
        self.erros_consecutivos = 0
        self.rodadas_pausa = 0
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
st.set_page_config(page_title="🎯 Roleta Bot Pro v18", layout="centered")
st.title("🎯 Roleta Bot Pro v18")

if "sistema" not in st.session_state or st.session_state.sistema is None:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    if not st.session_state.get('historico'): st.session_state.historico = dados.get('historico', [])
    sis = st.session_state.sistema
    sis.acertos = dados.get('sistema_acertos', 0); sis.erros = dados.get('sistema_erros', 0)
    sis.estado_inversao = dados.get('estado_inversao', False)
    sis.erros_consecutivos = dados.get('erros_consecutivos', 0)
    sis.rodadas_pausa = dados.get('rodadas_pausa', 0)
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
    'modo_automatico': True, 'max_n_apostas': 18, 'min_n_apostas': 12,
    'forca_minima_entrada': 55, 'modo_inversao_auto': False,
    'evitar_zero': True, 'evitar_terminal_zero': True, 'pausa_apos_erros': True,
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
    
    with st.expander("🔄 Inversão Automática", expanded=False):
        st.session_state.modo_inversao_auto = st.checkbox("🔄 Inversão Automática", value=st.session_state.modo_inversao_auto)
        if st.session_state.modo_inversao_auto:
            estado = "🔄 INVERTIDO" if st.session_state.sistema.estado_inversao else "📊 NORMAL"
            st.info(f"Estado: {estado} | Errou → Inverte")
    
    st.session_state.forca_minima_entrada = st.slider("⚡ Força Mínima", 45, 70, st.session_state.forca_minima_entrada, 5)
    st.session_state.max_n_apostas = st.slider("📊 Máx. números", 12, 18, st.session_state.max_n_apostas)
    st.session_state.evitar_zero = st.checkbox("🚫 Evitar Zero", value=st.session_state.evitar_zero)
    st.session_state.evitar_terminal_zero = st.checkbox("🚫 Evitar Terminal 0", value=st.session_state.evitar_terminal_zero)
    st.session_state.pausa_apos_erros = st.checkbox("⏸️ Pausa após 3 erros", value=st.session_state.pausa_apos_erros)
    
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
    ultimos = st.session_state.historico[-10:]
    fmt = []
    for item in ultimos:
        n = item['number'] if isinstance(item, dict) else item
        if isinstance(item, dict) and n in item.get('luckyNumbers', []):
            mult = item.get('luckyMultipliers', {}).get(n, '')
            fmt.append(f"⚡**{n}**({mult}x)" if mult else f"⚡**{n}**")
        else: fmt.append(str(n))
    st.write(" | ".join(fmt))

# Status
sis = st.session_state.sistema
st.subheader("📊 Status")
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("🟢", sis.acertos)
c2.metric("🔴", sis.erros)
tx = sis.acertos/(sis.acertos+sis.erros)*100 if (sis.acertos+sis.erros)>0 else 0
c3.metric("📊", f"{tx:.0f}%")
c4.metric("🔄", "INV" if sis.estado_inversao else "NOR")
c5.metric("⚠️Er", sis.erros_consecutivos)
c6.metric("⏸️", f"{sis.rodadas_pausa}g" if sis.rodadas_pausa > 0 else "Livre")

# Pausa
if sis.rodadas_pausa > 0:
    st.warning(f"⏸️ **PAUSA**: {sis.rodadas_pausa} giros restantes (após 3 erros consecutivos)")

# Entrada
st.subheader("🎯 Entrada Atual")
if sis.entrada_ativa:
    e = sis.entrada_ativa
    if e.get('invertido'):
        st.warning(f"### 🔄 INVERTIDA | {e['motor']} | {e['forca_real']}% | {len(e['numeros_apostar'])}n")
    else:
        emoji = "🔥" if e['forca_real'] >= 70 else "🎯" if e['forca_real'] >= 55 else "📊"
        st.info(f"### {emoji} {e['motor']} | {e['forca_real']}% | {len(e['numeros_apostar'])}n")
    if e.get('gatilho'): st.caption(f"🎯 {e['gatilho']}")
    st.markdown(f"## {', '.join(map(str, sorted(e['numeros_apostar'])))}")
else:
    if sis.rodadas_pausa > 0:
        st.warning(f"⏸️ Aguardando... ({sis.rodadas_pausa} giros)")
    else:
        st.info("🔍 Analisando...")

# Histórico
st.subheader("📋 Últimas")
if sis.historico_entradas:
    for entrada in reversed(sis.historico_entradas[-5:]):
        c1, c2, c3 = st.columns([1, 2, 2])
        c1.write(f"#{entrada['rodada']}")
        if entrada['acerto']: c2.success(f"✅ {entrada['resultado']}")
        else: c2.error(f"❌ {entrada['resultado']}")
        inv = "🔄" if entrada.get('invertido') else ""
        c3.write(f"{inv} {entrada['motor'][:14]} | {entrada.get('gatilho','')[:25]}")

# ==========================================
# 🆕 ANÁLISE DO BOT (INTERFACE)
# ==========================================
st.subheader("🧠 Análise do Bot")
analise = st.session_state.sistema.bot.get_analise()
if analise:
    tab1, tab2, tab3 = st.tabs(["📊 Classificação", "🔥 Quentes/Frios", "📈 Estatísticas"])
    
    with tab1:
        # Últimos 10 números com classificação
        st.write("**Últimos 10 números:**")
        for i, n in enumerate(reversed(analise['ultimos_10'])):
            col1, col2, col3 = st.columns([0.5, 1, 2])
            col1.write(f"**#{len(analise['ultimos_10'])-i}**")
            cor = "#66bb6a" if n in {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36} else "#ef5350" if n != 0 else "#4fc3f7"
            col2.markdown(f"<span style='font-size:1.3rem;font-weight:700;color:{cor}'>{n}</span>", unsafe_allow_html=True)
            # Classificação
            info = []
            if n == 0: info.append("Zero")
            else:
                info.append("Vermelho" if n in {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36} else "Preto")
                info.append("Par" if n%2==0 else "Ímpar")
                info.append(f"D{(n-1)//12+1}")
                info.append(f"T{n%10}")
            col3.write(" | ".join(info))
    
    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            st.write("**🔥 Quentes (5g):**")
            st.write(", ".join(map(str, analise['quentes_5'])))
            st.write("**🔥 Quentes (10g):**")
            st.write(", ".join(map(str, analise['quentes_10'])))
        with c2:
            st.write("**❄️ Atrasados (20g):**")
            st.write(", ".join(map(str, analise['atrasados'])))
            st.write(f"**🔢 Terminal dom:** {analise['term_dom']} ({analise['term_count']}x)")
    
    with tab3:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Vermelhos", f"{analise['count_V']}/10")
            st.metric("Pretos", f"{analise['count_P']}/10")
        with c2:
            st.metric("Pares", str(analise['pares_10']))
            st.metric("Ímpares", str(analise['impares_10']))
        with c3:
            st.metric("🎯 Taxa", f"{analise['taxa_acerto']:.0f}%")
            st.metric("📊 Total", str(analise['total_tentativas']))
        
        # Dúzias
        st.write("**📐 Dúzias (10g):**")
        for d, c in sorted(analise['duzias_10'].items()):
            st.progress(c/10, text=f"Dúzia {d}: {c}/10")
        
        # Setores
        st.write("**🎡 Setores (10g):**")
        for s, c in analise['setores_10'].most_common():
            st.write(f"- {s}: {c}")
        
        # Lucky
        if analise['lucky_freq']:
            st.write("**🍀 Lucky Numbers:**")
            st.write(", ".join([f"{n}({c}x)" for n, c in analise['lucky_freq'].most_common(5)]))

with st.expander("📥 Download", expanded=False):
    c1, c2, c3 = st.columns(3)
    c1.download_button("JSON", exportar_historico(st.session_state.historico,'json'), "historico.json")
    c2.download_button("CSV", exportar_historico(st.session_state.historico,'csv'), "historico.csv")
    c3.download_button("Entradas", json.dumps(sis.historico_entradas, indent=2), "entradas.json")

salvar_sessao()
