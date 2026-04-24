import streamlit as st
import json
import os
import requests
import logging
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import pickle
from datetime import datetime

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA (ORIGINAL)
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_roleta.json"
PERFORMANCE_PATH = "performance_bot.json"

def salvar_sessao():
    try:
        if 'sistema' in st.session_state:
            performance_data = {
                'acertos': st.session_state.sistema.bot.performance['acertos'],
                'erros': st.session_state.sistema.bot.performance['erros'],
                'historico': st.session_state.sistema.bot.performance['historico']
            }
            with open(PERFORMANCE_PATH, 'w') as f:
                json.dump(performance_data, f)
        
        session_data = {
            'historico': st.session_state.historico,
            'telegram_token': st.session_state.telegram_token,
            'telegram_chat_id': st.session_state.telegram_chat_id,
            'sistema_acertos': st.session_state.sistema.acertos,
            'sistema_erros': st.session_state.sistema.erros,
            'sistema_historico_desempenho': st.session_state.sistema.historico_desempenho,
            'historico_numeros': list(st.session_state.sistema.historico_numeros),
            'historico_lucky': list(st.session_state.sistema.historico_lucky),
            'estrategia_ativa_manual': st.session_state.sistema.estrategia_ativa_manual,
            'top_n_apostas': st.session_state.get('top_n_apostas', 5),
            'forca_minima_sinal': st.session_state.get('forca_minima_sinal', 40),
            'intervalo_minimo_entradas': st.session_state.get('intervalo_minimo_entradas', 0),
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'modo_conservador': st.session_state.get('modo_conservador', True),
            'janela_analise': st.session_state.get('janela_analise', 37)
        }
        
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f)
        
        logging.info("✅ Sessão salva")
        return True
    except Exception as e:
        logging.error(f"❌ Erro ao salvar: {e}")
        return False

def carregar_sessao():
    try:
        if os.path.exists(SESSION_DATA_PATH):
            with open(SESSION_DATA_PATH, 'rb') as f:
                session_data = pickle.load(f)
            
            st.session_state.historico = session_data.get('historico', [])
            st.session_state.telegram_token = session_data.get('telegram_token', '')
            st.session_state.telegram_chat_id = session_data.get('telegram_chat_id', '')
            
            st.session_state.top_n_apostas = session_data.get('top_n_apostas', 5)
            st.session_state.forca_minima_sinal = session_data.get('forca_minima_sinal', 40)
            st.session_state.intervalo_minimo_entradas = session_data.get('intervalo_minimo_entradas', 0)
            st.session_state.modo_automatico = session_data.get('modo_automatico', True)
            st.session_state.modo_conservador = session_data.get('modo_conservador', True)
            st.session_state.janela_analise = session_data.get('janela_analise', 37)
            
            if 'sistema' in st.session_state:
                st.session_state.sistema.acertos = session_data.get('sistema_acertos', 0)
                st.session_state.sistema.erros = session_data.get('sistema_erros', 0)
                st.session_state.sistema.historico_desempenho = session_data.get('sistema_historico_desempenho', [])
                st.session_state.sistema.historico_numeros = deque(session_data.get('historico_numeros', []), maxlen=200)
                st.session_state.sistema.historico_lucky = deque(session_data.get('historico_lucky', []), maxlen=100)
                st.session_state.sistema.estrategia_ativa_manual = session_data.get('estrategia_ativa_manual', False)
            
            if os.path.exists(PERFORMANCE_PATH) and 'sistema' in st.session_state:
                with open(PERFORMANCE_PATH, 'r') as f:
                    perf = json.load(f)
                    st.session_state.sistema.bot.performance = {
                        'acertos': perf.get('acertos', 0),
                        'erros': perf.get('erros', 0),
                        'historico': perf.get('historico', [])
                    }
            return True
    except Exception as e:
        logging.error(f"❌ Erro ao carregar: {e}")
    return False

# =============================
# NOTIFICAÇÕES (ORIGINAL)
# =============================
def enviar_previsao_auto(previsao):
    try:
        numeros = sorted(previsao['numeros_apostar'])
        confianca = previsao.get('confianca', 'Média')
        estrategias = previsao.get('estrategias_ativas', [])
        forca = previsao.get('forca_real', 0)
        emoji = "🟢" if confianca == "Alta" else "🟡" if confianca == "Média" else "🔴"
        
        msg = f"{emoji} **ENTRADA** - Força: {forca}%\n📋 {previsao['gatilho']}\n"
        if estrategias: msg += f"🎯 Estratégias: {', '.join(estrategias)}\n"
        msg += f"🔢 {len(numeros)} números: {numeros}"
        
        st.toast(f"🎯 Entrada - {confianca}", icon=emoji)
        st.success(f"🔔 {msg}")
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            enviar_telegram(f"🔔 ENTRADA [{confianca}]\n{msg}")
        salvar_sessao()
    except Exception as e: logging.error(f"Erro ao enviar: {e}")

def enviar_resultado_auto(numero_real, acerto, multiplicador=None):
    try:
        msg = f"{'✅ ACERTO!' if acerto else '❌ ERRO!'} {numero_real}"
        if multiplicador and multiplicador > 0: msg += f" ⚡{multiplicador}x"
        st.toast(f"{'✅' if acerto else '❌'} {numero_real}", icon="✅" if acerto else "❌")
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            enviar_telegram(f"📢 {msg}")
        salvar_sessao()
    except: pass

def enviar_telegram(mensagem):
    try:
        token = st.session_state.telegram_token
        chat_id = st.session_state.telegram_chat_id
        if not token or not chat_id: return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}, timeout=10)
    except: pass

# =============================
# ANALISADOR ATUALIZADO (LÓGICA SNIPER PRO)
# =============================
class AnalisadorRoletaVersatil:
    def __init__(self, janela_analise=37):
        self.janela_analise = janela_analise
        self.layout_roda = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        
    def get_vizinhos_roda(self, numero, raio=2):
        if numero not in self.layout_roda: return []
        idx = self.layout_roda.index(numero)
        return [self.layout_roda[(idx + i) % 37] for i in range(-raio, raio + 1)]
    
    def analisar(self, historico_numeros, lucky_recentes=None):
        if len(historico_numeros) < 15: return None
        
        curto = historico_numeros[-15:]
        longo = historico_numeros[-self.janela_analise:]
        
        duzias = Counter([(n-1)//12 + 1 for n in curto if n != 0])
        colunas = Counter([(n-1)%3 + 1 for n in curto if n != 0])
        melhor_duzia = duzias.most_common(1)[0][0] if duzias else None
        melhor_coluna = colunas.most_common(1)[0][0] if colunas else None
        
        roda_hits = []
        for n in curto: roda_hits.extend(self.get_vizinhos_roda(n, raio=1))
        zona_quente = Counter(roda_hits).most_common(1)[0][0] if roda_hits else None
        
        forca = 0
        gatilho = ""
        estrategia = []
        
        # Confluência 1: Cruzamento Setorial (Sniper)
        if melhor_duzia and melhor_coluna:
            if duzias.get(melhor_duzia, 0) >= 6 and colunas.get(melhor_coluna, 0) >= 5:
                forca += 50
                gatilho = f"Sniper: Cruzamento D{melhor_duzia} x C{melhor_coluna}"
                estrategia.append("Interseção D/C")
        
        # Confluência 2: Cluster Físico
        vizinhos_zona = self.get_vizinhos_roda(zona_quente, raio=2) if zona_quente is not None else []
        hits_zona = sum(1 for n in curto if n in vizinhos_zona)
        if hits_zona >= 5:
            forca += 40
            if not gatilho: gatilho = f"Cluster: Zona {zona_quente}"
            estrategia.append("Cluster Físico")

        # Confluência 3: Lucky Numbers (Raios)
        lucky_quentes = []
        if lucky_recentes:
            lucky_quentes = [n for n, _ in Counter(lucky_recentes).most_common(5)]
            if any(l in curto for l in lucky_quentes):
                forca += 10
                estrategia.append("Raios Quentes")

        return {
            'quentes': [n[0] for n in Counter(longo).most_common(5)],
            'melhor_duzia': melhor_duzia,
            'melhor_coluna': melhor_coluna,
            'zona_quente': zona_quente,
            'vizinhos_zona': vizinhos_zona,
            'lucky_quentes': lucky_quentes,
            'forca_sinal': min(100, forca),
            'gatilho': gatilho,
            'estrategia': estrategia,
            'ultimo': historico_numeros[-1]
        }

# =============================
# BOT V3 SNIPER (ORIGINAL)
# =============================
class RoletaBotV3:
    def __init__(self, janela_analise=37):
        self.analisador = AnalisadorRoletaVersatil(janela_analise)
        self.historico = []
        self.lucky = []
        self.lucky_mult = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        
    def atualizar(self, numero, lucky_nums=None, lucky_mults=None):
        self.historico.append(numero)
        self.lucky.append(lucky_nums if lucky_nums else [])
        self.lucky_mult.append(lucky_mults if lucky_mults else {})
        if len(self.historico) > 100:
            self.historico = self.historico[-100:]
            self.lucky = self.lucky[-100:]
    
    def atualizar_resultado(self, acerto):
        self.performance['historico'].append(1 if acerto else 0)
        if len(self.performance['historico']) > 50: self.performance['historico'] = self.performance['historico'][-50:]
        if acerto: self.performance['acertos'] += 1
        else: self.performance['erros'] += 1
    
    def get_taxa_acerto(self):
        total = self.performance['acertos'] + self.performance['erros']
        return self.performance['acertos'] / total if total > 0 else 0

    def get_total_tentativas(self): return self.performance['acertos'] + self.performance['erros']
    
    def sugerir_aposta(self, top_n=5, forca_minima=40, modo_conservador=True):
        if len(self.historico) < 15: return None
        lucky_recentes = [n for sub in self.lucky[-15:] for n in sub]
        analise = self.analisador.analisar(list(self.historico), lucky_recentes)
        
        if not analise or analise['forca_sinal'] < forca_minima: return None 
            
        base = set()
        # Regra Sniper: Expansão Dinâmica se força for alta
        raio_extra = 3 if analise['forca_sinal'] >= 80 else 2
        
        if "Interseção D/C" in analise['estrategia']:
            d, c = analise['melhor_duzia'], analise['melhor_coluna']
            inter = set(range((d-1)*12 + 1, d*12 + 1)).intersection(set(range(c, 37, 3)))
            base.update(inter)
            
        if "Cluster Físico" in analise['estrategia']:
            base.update(self.analisador.get_vizinhos_roda(analise['zona_quente'], raio=raio_extra))
            
        final_list = sorted(list(base))[:top_n]
        confianca = "Alta" if analise['forca_sinal'] >= 75 else "Média"
        
        if modo_conservador and len(self.performance['historico']) >= 10:
            if sum(self.performance['historico'][-10:]) / 10 <= 0.10: return None
                
        return {
            'nome': 'Bot V3 Sniper',
            'numeros_apostar': final_list,
            'gatilho': analise['gatilho'],
            'forca_real': analise['forca_sinal'],
            'confianca': confianca,
            'estrategias_ativas': analise['estrategia']
        }
    
    def get_analise_completa(self):
        lucky_recentes = [n for sub in self.lucky[-15:] for n in sub]
        analise = self.analisador.analisar(list(self.historico), lucky_recentes)
        if not analise: return "📊 Coletando dados..."
        return f"🎯 SNIPER: {analise['forca_sinal']}%\n🔥 Zona: {analise['zona_quente']}\n📍 D{analise['melhor_duzia']} C{analise['melhor_coluna']}\n📈 Taxa: {self.get_taxa_acerto():.0%}"

    def zerar(self):
        self.historico = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}

# =============================
# RESTANTE DO CÓDIGO (ESTRUTURA ORIGINAL INTACTA)
# =============================
class SistemaBot:
    def __init__(self):
        self.bot = RoletaBotV3()
        self.historico_numeros = deque(maxlen=200)
        self.historico_lucky = deque(maxlen=100)
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.rodadas_sem_entrada = 0
        self.ultima_entrada_rodada = -10
        self.estrategia_ativa_manual = False
        
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            n = numero_data['number']
            l = numero_data.get('luckyNumbers', [])
            m = numero_data.get('luckyMultipliers', {}).get(n)
        else:
            n, l, m = numero_data, [], None
        
        self.bot.atualizar(n, l, {})
        self.historico_numeros.append(n)
        self.historico_lucky.append(l)
        self.rodadas_sem_entrada += 1
        
        if self.previsao_ativa:
            acerto = n in self.previsao_ativa['numeros_apostar']
            self.bot.atualizar_resultado(acerto)
            if acerto: self.acertos += 1
            else: self.erros += 1
            enviar_resultado_auto(n, acerto, m)
            self.historico_desempenho.append({'numero': n, 'acerto': acerto, 'multiplicador': m, 'forca': self.previsao_ativa.get('forca_real', 0)})
            self.previsao_ativa = None
            self.ultima_entrada_rodada = len(self.historico_numeros)
            self.rodadas_sem_entrada = 0
        
        if not self.estrategia_ativa_manual and len(self.historico_numeros) >= 15:
            if len(self.historico_numeros) - self.ultima_entrada_rodada >= st.session_state.get('intervalo_minimo_entradas', 0):
                nova = self.bot.sugerir_aposta(st.session_state.get('top_n_apostas', 5), st.session_state.get('forca_minima_sinal', 40), st.session_state.get('modo_conservador', True))
                if nova:
                    self.previsao_ativa = nova
                    enviar_previsao_auto(nova)

    def get_status(self):
        return {'acertos': self.acertos, 'erros': self.erros, 'total': self.acertos + self.erros, 'rodadas_sem_entrada': self.rodadas_sem_entrada}

    def zerar_estatisticas(self):
        self.acertos = 0; self.erros = 0; self.historico_desempenho = []; self.bot.zerar(); salvar_sessao()

# --- STREAMLIT UI (CONTINUAÇÃO IGUAL AO SEU) ---
st.set_page_config(page_title="🤖 Bot V3 — Sniper Pro", layout="centered")
if "sistema" not in st.session_state: st.session_state.sistema = SistemaBot()
if "historico" not in st.session_state: st.session_state.historico = []

carregar_sessao()

# Sidebar
st.sidebar.title("⚙️ Configurações")
st.session_state.janela_analise = st.sidebar.slider("Janela Longa", 15, 100, st.session_state.get('janela_analise', 37))
st.session_state.top_n_apostas = st.sidebar.slider("📊 Máx. Números", 3, 8, st.session_state.get('top_n_apostas', 5))
st.session_state.forca_minima_sinal = st.sidebar.slider("⚡ Força mínima", 10, 85, st.session_state.get('forca_minima_sinal', 60))
st.session_state.intervalo_minimo_entradas = st.sidebar.slider("⏱️ Intervalo", 0, 5, st.session_state.get('intervalo_minimo_entradas', 1))
st.session_state.modo_conservador = st.sidebar.checkbox("🛡️ Drawdown Control", value=st.session_state.get('modo_conservador', True))

st.sidebar.text(st.session_state.sistema.bot.get_analise_completa())

st_autorefresh(interval=3000, key="refresh")

def fetch_latest():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=5).json()
        d = r['data']; res = d['result']; out = res['outcome']
        ln = [x['number'] for x in res.get('luckyNumbersList', [])]
        lm = {x['number']: x['roundedMultiplier'] for x in res.get('luckyNumbersList', [])}
        return {"number": out['number'], "timestamp": d['startedAt'], "luckyNumbers": ln, "luckyMultipliers": lm}
    except: return None

resultado = fetch_latest()
if resultado and (not st.session_state.historico or resultado['timestamp'] != st.session_state.historico[-1].get("timestamp")):
    st.session_state.historico.append(resultado)
    st.session_state.sistema.processar_novo_numero(resultado)
    with open(HISTORICO_PATH, "w") as f: json.dump(st.session_state.historico, f)
    salvar_sessao()

# PAINEL CENTRAL
st.title("🎯 Sniper Pro V3")
status = st.session_state.sistema.get_status()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Greens", status['acertos'])
c2.metric("Reds", status['erros'])
c3.metric("Apostas", status['total'])
c4.metric("Espera", f"{status['rodadas_sem_entrada']} giros")

if st.session_state.sistema.previsao_ativa:
    p = st.session_state.sistema.previsao_ativa
    st.success(f"🎯 ENTRADA: {sorted(p['numeros_apostar'])} (Força {p['forca_real']}%)")
    st.caption(f"🧠 Gatilho: {p['gatilho']}")

st.write("**Recentes:**", [str(x['number']) for x in st.session_state.historico[-15:]][::-1])

# Inserção manual e logs (Igual ao seu)
if st.button("🗑️ Limpar Banco"):
    st.session_state.sistema.zerar_estatisticas()
    st.rerun()
