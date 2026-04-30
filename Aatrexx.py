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
            'max_n_apostas': st.session_state.get('max_n_apostas', 7),
            'min_n_apostas': st.session_state.get('min_n_apostas', 5),
            'forca_minima_entrada': st.session_state.get('forca_minima_entrada', 55),
            'usar_sniper_elite': st.session_state.get('usar_sniper_elite', True),
            'usar_repeticao': st.session_state.get('usar_repeticao', True),
            'usar_gap3': st.session_state.get('usar_gap3', True),
            'usar_lucky_vizinhos': st.session_state.get('usar_lucky_vizinhos', True),
            'usar_mineracao': st.session_state.get('usar_mineracao', True),
            'usar_duzia_dom': st.session_state.get('usar_duzia_dom', True),
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
        green = previsao.get('green', False)
        gatilho = previsao.get('gatilho', '')
        emoji = "🟢" if green else "🔥" if forca >= 60 else "🎯"
        st.toast(f"{emoji} {motor} - {forca}%")
        
        msg = f"🔔 **{emoji} ENTRADA** - Força: {forca}% | {len(numeros)} núm.\n"
        msg += f"🤖 {motor}\n"
        if gatilho: msg += f"🎯 Gatilho: {gatilho}\n"
        msg += f"🔢 {numeros}"
        st.success(msg)
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"🔔 {'[GREEN]' if green else ''} F{forca}% | {motor}\n{gatilho}\n🔢 " + " ".join(map(str, numeros)))
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
    def get_vizinhos(self, n, r=2):
        if n not in self.race: return []
        i = self.race.index(n)
        return [self.race[(i + j) % 37] for j in range(-r, r + 1)]


# =============================
# 6 ESTRATÉGIAS COM GATILHOS DINÂMICOS
# =============================

class EstrategiaSniperElite:
    """
    🎯 GATILHO DINÂMICO: Terminal mais frequente nos últimos 8 giros
    - Calcula em tempo real qual dígito final (0-9) está dominando
    - Se um terminal aparece 3+ vezes em 8 giros → ATIVA
    - Ex: 3, 13, 23, 33 nos últimos 8 giros → Terminal 3 ativado
    """
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 8: return None
        
        # Gatilho dinâmico: frequência de terminais nos últimos 8 giros
        termos_8 = [n%10 for n in h[-8:]]
        contagem = Counter(termos_8)
        terminal_dom, freq = contagem.most_common(1)[0]
        
        # Só ativa se 3+ ocorrências do mesmo terminal
        if freq < 3: return None
        
        # Busca nos últimos 5 giros também
        termos_5 = [n%10 for n in h[-5:]]
        contagem_5 = Counter(termos_5)
        terminal_5, freq_5 = contagem_5.most_common(1)[0]
        
        # Se o terminal dominante mudou nos últimos 5, usa o mais recente
        if freq_5 >= 2 and terminal_5 != terminal_dom:
            terminal_dom = terminal_5
            freq = freq_5
        
        aposta = set()
        # Vizinhos do último número na roleta
        aposta.update(self.roleta.get_vizinhos(h[-1], 1)[:3])
        
        # Números com o terminal dominante
        for n in range(37):
            if n%10 == terminal_dom:
                aposta.add(n)
                if len(aposta) >= 6: break
        
        forca = 50 + (freq * 5)  # Força baseada na frequência real
        gatilho = f"Terminal {terminal_dom} ({freq}x em 8 giros)"
        
        return {
            'base': set(list(aposta)[:6]),
            'forca': min(100, forca),
            'estrategias': [gatilho],
            'gatilho': gatilho
        }


class EstrategiaRepeticao:
    """
    🔄 GATILHO DINÂMICO: Número repetiu no giro anterior
    - Se último == penúltimo → ATIVA IMEDIATAMENTE
    - Ex: 23 → 23 → Aposta no 23 + vizinhos
    """
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        u, p = h[-1], h[-2]
        
        if u != p: return None
        
        b = set([u])
        b.update(self.roleta.get_vizinhos(u, 1)[:2])
        
        gatilho = f"Número {u} repetiu! ({p}→{u})"
        return {
            'base': b,
            'forca': 75,
            'estrategias': [gatilho],
            'gatilho': gatilho
        }


class EstrategiaGap3:
    """
    ⏭️ GATILHO DINÂMICO: Padrão de ciclo curto (gap 3-5 giros)
    - Verifica se o número atual já apareceu 3, 4 ou 5 giros atrás
    - Ex: 13 → X → Y → 13 → Aposta no 13 + vizinhos
    - Também detecta padrões de gap nos últimos 20 giros
    """
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 4: return None
        u = h[-1]
        b = set()
        gap_encontrado = None
        
        # Gap 3: N[i] == N[i+3]
        if len(h) >= 4 and h[-4] == u:
            b.update([u, h[-2], h[-3]])
            gap_encontrado = 3
        
        # Gap 4: N[i] == N[i+4]
        if len(h) >= 5 and h[-5] == u:
            b.add(u)
            gap_encontrado = gap_encontrado or 4
        
        # Gap 5: N[i] == N[i+5]
        if len(h) >= 6 and h[-6] == u:
            b.add(u)
            gap_encontrado = gap_encontrado or 5
        
        # Detecta padrão de gap nos últimos 20 giros
        if not b:
            gaps = []
            for i in range(len(h) - 3):
                for g in [3, 4, 5]:
                    if i + g < len(h) and h[i] == h[i + g]:
                        gaps.append((h[i], g))
            if gaps:
                # Pega o gap mais recente
                num, g = gaps[-1]
                b.add(num)
                b.update(self.roleta.get_vizinhos(num, 1)[:2])
                gap_encontrado = g
        
        if not b: return None
        
        for n in list(b)[:2]: b.update(self.roleta.get_vizinhos(n, 1)[:1])
        
        gatilho = f"Ciclo de {gap_encontrado} giros: {u}"
        return {
            'base': b,
            'forca': 55 + (gap_encontrado or 0) * 3,
            'estrategias': [gatilho],
            'gatilho': gatilho
        }


class EstrategiaLuckyVizinhos:
    """
    🍀 GATILHO DINÂMICO: Lucky Numbers recentes no histórico
    - Rastreia quais Lucky Numbers saíram nos últimos 10 giros
    - Se houver 2+ Lucky Numbers recentes → ATIVA
    - Aposta nos Lucky Numbers + seus vizinhos na roleta
    """
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h, lucky_hist):
        if len(h) < 3 or not lucky_hist: return None
        
        # Coleta Lucky Numbers das últimas 8 rodadas
        all_lucky = []
        for sub in lucky_hist[-8:]:
            all_lucky.extend(sub)
        
        if len(all_lucky) < 2: return None
        
        # Frequência dos Lucky Numbers
        freq_lucky = Counter(all_lucky)
        
        # Verifica se algum Lucky Number saiu nos últimos 3 giros
        recentes = set(h[-3:])
        lucky_recentes = [n for n in freq_lucky if n in recentes]
        
        if lucky_recentes:
            # Lucky Number acabou de sair → aposta nele + vizinhos
            top = lucky_recentes[:2]
        else:
            # Pega os mais frequentes
            top = [n for n, _ in freq_lucky.most_common(2)]
        
        b = set(top)
        for n in top[:1]: b.update(self.roleta.get_vizinhos(n, 1)[:1])
        
        gatilho = f"Lucky {' e '.join(map(str, top))}"
        return {
            'base': b,
            'forca': 50 + len(all_lucky) * 2,
            'estrategias': [gatilho],
            'gatilho': gatilho
        }


class EstrategiaMineracao:
    """
    ⛏️ GATILHO DINÂMICO: Cadeia de Markov em tempo real
    - Após o número X, quais números mais saíram?
    - Se há um seguidor com 15%+ de frequência → ATIVA
    - Ex: Após 13, o 25 saiu 3x → Aposta 25
    """
    def analisar(self, h):
        if len(h) < 5: return None
        u = h[-1]
        
        # Constrói matriz de transição com todo histórico
        t = defaultdict(list)
        for i in range(len(h) - 1):
            t[h[i]].append(h[i + 1])
        
        seguidores = t.get(u, [])
        if len(seguidores) < 2: return None
        
        contagem = Counter(seguidores)
        # Pega números com frequência ≥ 15%
        top = [(n, c) for n, c in contagem.most_common(3) if c/len(seguidores) >= 0.15]
        
        if not top: return None
        
        b = set([n for n, _ in top[:2]])
        
        gatilho = f"Após {u} → {top[0][0]} ({top[0][1]}/{len(seguidores)})"
        return {
            'base': b,
            'forca': 45 + len(seguidores),
            'estrategias': [gatilho],
            'gatilho': gatilho
        }


class EstrategiaDuziaDominante:
    """
    📐 GATILHO DINÂMICO: Concentração em dúzia/zona
    - Analisa os últimos 12 giros em tempo real
    - Se 6+ números estão na mesma dúzia → ATIVA
    - Aposta nos números faltantes da dúzia + quentes
    """
    def analisar(self, h):
        if len(h) < 12: return None
        
        dz = {1: set(range(1, 13)), 2: set(range(13, 25)), 3: set(range(25, 37))}
        
        # Contagem dinâmica nos últimos 12 giros
        recentes = h[-12:]
        cnt = Counter()
        for n in recentes:
            if n != 0:
                d = (n - 1) // 12 + 1
                cnt[d] += 1
        
        if not cnt: return None
        
        duzia_dom, freq = cnt.most_common(1)[0]
        
        # Gatilho: 50%+ dos últimos 12 giros na mesma dúzia
        if freq < 6: return None
        
        b = set()
        # Números da dúzia que NÃO saíram nos últimos 5 giros
        nao_sairam = dz[duzia_dom] - set(h[-5:])
        b.update(list(nao_sairam)[:3])
        
        # Números quentes da dúzia (saíram nos últimos 5)
        quentes = dz[duzia_dom].intersection(set(h[-5:]))
        b.update(list(quentes)[:2])
        
        # Adiciona vizinhos do último número
        b.update(RoletaBase().get_vizinhos(h[-1], 1)[:2])
        
        forca = 50 + (freq - 6) * 5
        gatilho = f"Dúzia {duzia_dom} concentrada ({freq}/12 giros)"
        
        return {
            'base': b,
            'forca': min(100, forca),
            'estrategias': [gatilho],
            'gatilho': gatilho
        }


# =============================
# BOT UNIFICADO (6 ESTRATÉGIAS COM GATILHOS)
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        self.sniper_elite = EstrategiaSniperElite(self.roleta)
        self.repeticao = EstrategiaRepeticao(self.roleta)
        self.gap3 = EstrategiaGap3(self.roleta)
        self.lucky_vizinhos = EstrategiaLuckyVizinhos(self.roleta)
        self.mineracao = EstrategiaMineracao()
        self.duzia_dom = EstrategiaDuziaDominante()
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
            motores = {k: True for k in ['sniper_elite','repeticao','gap3','lucky_vizinhos','mineracao','duzia_dom']}
        
        resultados = []
        forca_min = st.session_state.get('forca_minima_entrada', 55)
        
        ests = [
            (self.sniper_elite, 'Sniper Elite', 4, [list(self.historico)]),
            (self.repeticao, 'Repetição', 3, [list(self.historico)]),
            (self.gap3, 'Gap 3-4', 3, [list(self.historico)]),
            (self.lucky_vizinhos, 'Lucky Vizinhos', 2, [list(self.historico), self.lucky]),
            (self.mineracao, 'Mineração', 1, [list(self.historico)]),
            (self.duzia_dom, 'Dúzia Dom.', 1, [list(self.historico)]),
        ]
        
        for est, nome, peso, args in ests:
            try:
                if motores.get(nome.lower().replace(' ','_').replace('.','').replace('ú','u').replace('ã','a').replace('ç','c'), True) and len(self.historico) >= 1:
                    if nome == 'Lucky Vizinhos' and not self.lucky: continue
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
        q = "EXCELENTE" if qs >= 12 else "BOA" if qs >= 8 else "REGULAR"
        
        return {
            'numeros_apostar': sorted(lst),
            'forca_real': min(100, max(35, fm)),
            'motor': mp,
            'estrategias_ativas': list(set(ests_ativas))[:4],
            'qtd_motores': len(resultados),
            'qualidade': q,
            'green': False,
            'green_count': 0,
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
        self.green_repeticoes = 0
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
                'gatilho': self.entrada_ativa.get('gatilho', ''),
                'estrategias': self.entrada_ativa.get('estrategias_ativas', []),
                'qualidade': self.entrada_ativa.get('qualidade', ''),
                'lucky': is_lucky, 'multiplicador': mult,
                'green': self.entrada_ativa.get('green', False),
            })
            if len(self.historico_entradas) > 50: self.historico_entradas = self.historico_entradas[-50:]
            
            entrada_forca = self.entrada_ativa.get('forca_real', 0)
            
            if acerto:
                if self.green_repeticoes < 2:
                    self.green_repeticoes += 1
                    self.ultima_entrada_numeros = list(self.entrada_ativa.get('numeros_apostar', []))
                    self.ultima_entrada_forca = entrada_forca
                else:
                    self.green_repeticoes = 0; self.ultima_entrada_numeros = []
            else:
                self.green_repeticoes = 0; self.ultima_entrada_numeros = []
            
            enviar_resultado_auto(nr, acerto, is_lucky)
            self.entrada_ativa = None
        
        # Green Repeat
        if self.green_repeticoes > 0 and self.ultima_entrada_numeros:
            self.entrada_ativa = {
                'numeros_apostar': sorted(self.ultima_entrada_numeros),
                'forca_real': min(90, self.ultima_entrada_forca + 15),
                'motor': 'Green Repeat',
                'estrategias_ativas': [f'🟢 Green #{self.green_repeticoes}/2'],
                'qtd_motores': 1, 'qualidade': 'GREEN', 'green': True,
                'green_count': self.green_repeticoes,
                'gatilho': f'Repetindo entrada que acertou ({self.green_repeticoes}/2)'
            }
            enviar_previsao_auto(self.entrada_ativa)
            return
        
        # Nova análise
        mot = {k: st.session_state.get(f'usar_{k}', True) for k in ['sniper_elite','repeticao','gap3','lucky_vizinhos','mineracao','duzia_dom']}
        self.entrada_ativa = self.bot.gerar_entrada(mot)
        if self.entrada_ativa: enviar_previsao_auto(self.entrada_ativa)
    
    def zerar(self):
        self.acertos = 0; self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear(); self.historico_lucky.clear(); self.historico_mults.clear()
        self.entrada_ativa = None
        self.green_repeticoes = 0
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
st.set_page_config(page_title="🎯 Roleta Bot Pro v7 - Gatilhos Dinâmicos", layout="centered")
st.title("🎯 Roleta Bot Pro v7 - Gatilhos Dinâmicos")

if "sistema" not in st.session_state or st.session_state.sistema is None:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    if not st.session_state.get('historico'): st.session_state.historico = dados.get('historico', [])
    sis = st.session_state.sistema
    sis.acertos = dados.get('sistema_acertos', 0); sis.erros = dados.get('sistema_erros', 0)
    sis.green_repeticoes = dados.get('green_repeticoes', 0)
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
    'forca_minima_entrada': 55,
    'usar_sniper_elite': True, 'usar_repeticao': True,
    'usar_gap3': True, 'usar_lucky_vizinhos': True,
    'usar_mineracao': True, 'usar_duzia_dom': True,
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
    st.session_state.forca_minima_entrada = st.slider("⚡ Força Mínima", 45, 70, st.session_state.forca_minima_entrada, 5)
    st.session_state.max_n_apostas = st.slider("📊 Máx. números", 12, 15, st.session_state.max_n_apostas)
    st.session_state.min_n_apostas = st.slider("📊 Mín. números", 3, 12, st.session_state.min_n_apostas)
    
    with st.expander("🤖 6 Estratégias com Gatilhos", expanded=False):
        st.markdown("""
        | Estratégia | Gatilho Dinâmico |
        |-----------|-----------------|
        | 🎯 Sniper Elite | Terminal 3+ em 8 giros |
        | 🔄 Repetição | Número repetiu agora |
        | ⏭️ Gap 3-4 | Ciclo de 3-5 giros |
        | 🍀 Lucky Vizinhos | Lucky Numbers recentes |
        | ⛏️ Mineração | Cadeia Markov 15%+ |
        | 📐 Dúzia Dom. | 6+/12 na mesma dúzia |
        """)
        st.session_state.usar_sniper_elite = st.checkbox("🎯 Sniper Elite (4x)", value=st.session_state.usar_sniper_elite)
        st.session_state.usar_repeticao = st.checkbox("🔄 Repetição (3x)", value=st.session_state.usar_repeticao)
        st.session_state.usar_gap3 = st.checkbox("⏭️ Gap 3-4 (3x)", value=st.session_state.usar_gap3)
        st.session_state.usar_lucky_vizinhos = st.checkbox("🍀 Lucky Vizinhos (2x)", value=st.session_state.usar_lucky_vizinhos)
        st.session_state.usar_mineracao = st.checkbox("⛏️ Mineração (1x)", value=st.session_state.usar_mineracao)
        st.session_state.usar_duzia_dom = st.checkbox("📐 Dúzia Dom. (1x)", value=st.session_state.usar_duzia_dom)
    
    st.success("🟢 **Green Repeat**: 50% acerto\n🎯 **Força mínima**: " + str(st.session_state.forca_minima_entrada) + "%\n📊 **Máx**: " + str(st.session_state.max_n_apostas) + " números")
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
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("🟢", sis.acertos); c2.metric("🔴", sis.erros)
tx = sis.acertos/(sis.acertos+sis.erros)*100 if (sis.acertos+sis.erros)>0 else 0
c3.metric("📊", f"{tx:.0f}%"); c4.metric("🟢G", f"{sis.green_repeticoes}/2")
c5.metric("⚡Min", st.session_state.get('forca_minima_entrada', 55))
c6.metric("🎯N", st.session_state.get('max_n_apostas', 7))

# Entrada
st.subheader("🎯 Entrada Atual")
if sis.entrada_ativa:
    e = sis.entrada_ativa
    if e.get('green'): st.success(f"### 🟢 GREEN #{e.get('green_count',0)}/2")
    else:
        emoji = "🔥" if e['forca_real'] >= 60 else "🎯"
        st.info(f"### {emoji} {e['motor']} | {e['forca_real']}% | {e['qualidade']} | {len(e['numeros_apostar'])}n")
    
    # 🆕 Exibe o gatilho
    if e.get('gatilho'):
        st.warning(f"🎯 **Gatilho**: {e['gatilho']}")
    st.caption(f"🎯 {', '.join(e.get('estrategias_ativas', [])[:3])}")
    st.markdown(f"## {', '.join(map(str, sorted(e['numeros_apostar'])))}")
else: st.info("🔍 Analisando...")

# Histórico com gatilhos
st.subheader("📋 Últimas Entradas")
if sis.historico_entradas:
    for entrada in reversed(sis.historico_entradas[-6:]):
        c1, c2, c3, c4 = st.columns([0.5, 2, 1.5, 2])
        c1.write(f"**#{entrada['rodada']}**"); c2.write(", ".join(map(str, entrada['numeros'][:5])))
        if entrada['acerto']: c3.success(f"✅ {entrada['resultado']}" + ("🍀" if entrada.get('lucky') else ""))
        else: c3.error(f"❌ {entrada['resultado']}")
        g_str = f" | {entrada.get('gatilho','')[:30]}" if entrada.get('gatilho') else ""
        c4.write(f"{'🟢' if entrada.get('green') else ''} {entrada['motor'][:10]}{g_str}")
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
    c1.download_button("JSON", exportar_historico(st.session_state.historico,'json'), "historico.json")
    c2.download_button("CSV", exportar_historico(st.session_state.historico,'csv'), "historico.csv")
    c3.download_button("Entradas", json.dumps(sis.historico_entradas, indent=2), "entradas.json")

salvar_sessao()
