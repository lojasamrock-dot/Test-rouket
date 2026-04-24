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
# CONFIGURAÇÕES DE PERSISTÊNCIA
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
            'top_n_apostas': st.session_state.get('top_n_apostas', 4),
            'forca_minima_sinal': st.session_state.get('forca_minima_sinal', 20),
            'intervalo_minimo_entradas': st.session_state.get('intervalo_minimo_entradas', 0),
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'modo_conservador': st.session_state.get('modo_conservador', True)
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
            
            st.session_state.top_n_apostas = session_data.get('top_n_apostas', 4)
            st.session_state.forca_minima_sinal = session_data.get('forca_minima_sinal', 20)
            st.session_state.intervalo_minimo_entradas = session_data.get('intervalo_minimo_entradas', 0)
            st.session_state.modo_automatico = session_data.get('modo_automatico', True)
            st.session_state.modo_conservador = session_data.get('modo_conservador', True)
            
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
            
            logging.info("✅ Sessão carregada")
            return True
    except Exception as e:
        logging.error(f"❌ Erro ao carregar: {e}")
    return False

def limpar_sessao():
    try:
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH]:
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
        confianca = previsao.get('confianca', 'Média')
        
        emoji = "🟢" if confianca == "Alta" else "🟡" if confianca == "Média" else "🔴"
        
        msg = f"{emoji} **ENTRADA** - Confiança: {confianca}\n"
        msg += f"📋 {previsao['gatilho']}\n"
        msg += f"🔢 {len(numeros)} números"
        
        st.toast(f"🎯 Entrada - {confianca}", icon=emoji)
        
        if confianca == "Alta":
            st.success(f"🔔 {msg}")
        else:
            st.warning(f"🔔 {msg}")
        
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            enviar_telegram(f"🔔 ENTRADA [{confianca}]\n{msg}\n" + " ".join(map(str, numeros)))
        
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar: {e}")

def enviar_resultado_auto(numero_real, acerto, multiplicador=None):
    try:
        if acerto:
            msg = f"✅ ACERTO! {numero_real}"
        else:
            msg = f"❌ ERRO! {numero_real}"
        if multiplicador and multiplicador > 0:
            msg += f" ⚡{multiplicador}x"
        
        st.toast(f"{'✅' if acerto else '❌'} {numero_real}", icon="✅" if acerto else "❌")
        
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            enviar_telegram(f"📢 {msg}")
        
        salvar_sessao()
    except:
        pass

def enviar_telegram(mensagem):
    try:
        token = st.session_state.telegram_token
        chat_id = st.session_state.telegram_chat_id
        if not token or not chat_id:
            return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
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
    
    def get_vizinhos(self, numero, raio=1):
        if numero not in self.race:
            return []
        posicao = self.race.index(numero)
        vizinhos = []
        for offset in range(-raio, raio + 1):
            if offset != 0:
                vizinhos.append(self.race[(posicao + offset) % 37])
        return vizinhos


# =============================
# BOT V3 REFORMULADO
# =============================
class RoletaBotV3:
    """
    Bot V3 Reformulado - Mais Assertivo
    - Menos números (3-5)
    - Prioridade máxima para repetições e lucky
    - Força baseada em acerto real
    """
    
    def __init__(self):
        self.roleta = RoletaBase()
        self.historico = []
        self.lucky = []
        self.lucky_mult = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.ultimo_acerto = None
        
    def atualizar(self, numero, lucky_nums=None, lucky_mults=None):
        self.historico.append(numero)
        self.lucky.append(lucky_nums if lucky_nums else [])
        self.lucky_mult.append(lucky_mults if lucky_mults else {})
        if len(self.historico) > 50:
            self.historico = self.historico[-50:]
            self.lucky = self.lucky[-50:]
            self.lucky_mult = self.lucky_mult[-50:]
    
    def atualizar_resultado(self, acerto):
        self.ultimo_acerto = acerto
        self.performance['historico'].append(1 if acerto else 0)
        if len(self.performance['historico']) > 50:
            self.performance['historico'] = self.performance['historico'][-50:]
        if acerto:
            self.performance['acertos'] += 1
        else:
            self.performance['erros'] += 1
    
    def get_taxa_acerto(self):
        total = self.performance['acertos'] + self.performance['erros']
        return self.performance['acertos'] / total if total > 0 else 0
    
    def get_taxa_recente(self, n=5):
        hist = self.performance['historico']
        if len(hist) < n:
            return self.get_taxa_acerto()
        return sum(hist[-n:]) / n if hist[-n:] else 0
    
    def get_total_tentativas(self):
        return self.performance['acertos'] + self.performance['erros']
    
    def get_atraso(self, n):
        for i, val in enumerate(reversed(self.historico)):
            if val == n:
                return i
        return 50
    
    def sugerir_aposta(self, top_n=4, forca_minima=20, modo_conservador=True):
        """
        Estratégia reformulada:
        - Foco em REPETIÇÃO e LUCKY NUMBERS
        - Máximo 3-5 números
        - Só entra com confiança real
        """
        if len(self.historico) < 5:
            return None
        
        hist = self.historico
        ultimo = hist[-1]
        penultimo = hist[-2] if len(hist) >= 2 else None
        ultimos_5 = hist[-5:] if len(hist) >= 5 else hist
        ultimos_10 = hist[-10:] if len(hist) >= 10 else hist
        
        # Detecta repetição
        repeticao_direta = (ultimo == penultimo) if penultimo else False
        repeticoes_5 = [n for n in ultimos_5 if ultimos_5.count(n) >= 2]
        repeticoes_10 = [n for n in ultimos_10 if ultimos_10.count(n) >= 3]
        
        # Lucky numbers recentes com peso
        lucky_pesos = Counter()
        for i, (lucky_list, mult_dict) in enumerate(zip(self.lucky[-5:], self.lucky_mult[-5:])):
            peso_tempo = 1.5 - (i * 0.1)  # Mais recente = mais peso
            for n in lucky_list:
                mult = mult_dict.get(n, 0)
                peso_mult = 1.0
                if mult >= 1000:
                    peso_mult = 4.0
                elif mult >= 500:
                    peso_mult = 2.5
                elif mult >= 200:
                    peso_mult = 1.8
                elif mult >= 100:
                    peso_mult = 1.3
                lucky_pesos[n] += peso_tempo * peso_mult
        
        # Top lucky numbers
        top_lucky = [n for n, _ in lucky_pesos.most_common(5)]
        
        # Frequência recente
        freq_5 = Counter(ultimos_5)
        freq_10 = Counter(ultimos_10)
        
        # 🎯 CONSTRUÇÃO DA BASE (máximo 5 números)
        base = set()
        
        # 1. Número que repetiu (MÁXIMA prioridade)
        if repeticao_direta:
            base.add(ultimo)
        
        # 2. Números que repetiram nas últimas 5
        for n in repeticoes_5[:2]:
            base.add(n)
        
        # 3. Top lucky numbers
        for n in top_lucky[:3]:
            base.add(n)
        
        # 4. Último número (sempre)
        base.add(ultimo)
        
        # 5. Mais frequente nos últimos 5
        top_freq_5 = [n for n, _ in freq_5.most_common(2)]
        for n in top_freq_5:
            if n in top_lucky or n in repeticoes_5:
                base.add(n)
        
        # 6. Vizinho do último (apenas 1)
        vizinhos = self.roleta.get_vizinhos(ultimo, raio=1)
        if vizinhos and len(base) < 4:
            base.add(vizinhos[0])
        
        # Converte para lista
        base_list = list(base)
        
        # Ordena por prioridade: repetidos > lucky > frequentes
        prioridade = []
        if repeticao_direta:
            prioridade.append(ultimo)
        for n in repeticoes_5:
            if n not in prioridade:
                prioridade.append(n)
        for n in top_lucky:
            if n not in prioridade:
                prioridade.append(n)
        for n in base_list:
            if n not in prioridade:
                prioridade.append(n)
        
        # Limita ao máximo
        base_list = prioridade[:top_n]
        
        # Se tem menos de 3, completa com frequentes
        if len(base_list) < 3:
            for n, _ in freq_10.most_common(5):
                if n not in base_list:
                    base_list.append(n)
                    if len(base_list) >= 3:
                        break
        
        # 🎯 CÁLCULO DE CONFIANÇA REAL
        confianca = "Baixa"
        forca_real = 20
        
        # Fatores que aumentam confiança
        if repeticao_direta:
            forca_real += 40
        if len(repeticoes_5) >= 2:
            forca_real += 25
        elif len(repeticoes_5) >= 1:
            forca_real += 15
        
        # Lucky numbers fortes
        lucky_altos = sum(1 for n in base_list if lucky_pesos[n] >= 2.0)
        forca_real += lucky_altos * 10
        
        # Performance recente
        taxa_recente = self.get_taxa_recente(5)
        if taxa_recente >= 0.4:
            forca_real += 15
        elif taxa_recente <= 0.1:
            if modo_conservador:
                return None  # Não entra se performance muito ruim
        
        # Ajusta confiança
        if forca_real >= 60:
            confianca = "Alta"
        elif forca_real >= 35:
            confianca = "Média"
        else:
            confianca = "Baixa"
            if modo_conservador and len(base_list) > 3:
                base_list = base_list[:3]  # Reduz para 3 números
        
        # Gatilho descritivo
        partes = []
        if repeticao_direta:
            partes.append(f"REPETIU {ultimo}")
        if repeticoes_5:
            partes.append(f"rep={repeticoes_5[:2]}")
        if top_lucky:
            partes.append(f"lucky={top_lucky[:2]}")
        
        return {
            'nome': 'Bot V3 Reformulado',
            'numeros_apostar': sorted(base_list),
            'gatilho': ", ".join(partes) if partes else f"u={ultimo}",
            'forca_real': forca_real,
            'confianca': confianca,
            'modo': 'REPETICAO' if repeticao_direta else 'NORMAL'
        }
    
    def get_analise_completa(self):
        if len(self.historico) < 5:
            return "📊 Aguardando dados (mínimo 5)..."
        
        hist = self.historico
        ultimo = hist[-1]
        
        # Lucky recentes
        lucky_flat = []
        for sub in self.lucky[-5:]:
            lucky_flat.extend(sub)
        top_lucky = [n for n, _ in Counter(lucky_flat).most_common(5)]
        
        # Repetições
        ultimos_5 = hist[-5:]
        repeticoes = [n for n in ultimos_5 if ultimos_5.count(n) >= 2]
        
        taxa = self.get_taxa_acerto()
        taxa_rec = self.get_taxa_recente(5)
        total = self.get_total_tentativas()
        
        analise = "🎯 BOT V3 REFORMULADO\n" + "="*35 + "\n\n"
        analise += f"🎲 Último: {ultimo}\n"
        analise += f"📊 10 últimos: {hist[-10:]}\n\n"
        
        if hist[-1] == hist[-2] if len(hist) >= 2 else False:
            analise += f"🔥 REPETIU! {ultimo}→{ultimo}\n"
        
        analise += f"🔁 Repetições (5): {list(set(repeticoes))}\n"
        analise += f"🍀 Top Lucky (5): {top_lucky}\n"
        
        if total > 0:
            analise += f"\n📈 Perf: {taxa:.0%} ({self.performance['acertos']}/{total})\n"
            analise += f"📊 Rec(5): {taxa_rec:.0%}\n"
        
        return analise
    
    def zerar(self):
        self.historico = []
        self.lucky = []
        self.lucky_mult = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.ultimo_acerto = None


# =============================
# SISTEMA PRINCIPAL
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
            numero_real = numero_data['number']
            lucky = numero_data.get('luckyNumbers', [])
            lucky_mults = numero_data.get('luckyMultipliers', {})
            mult = lucky_mults.get(numero_real) if numero_real in lucky else None
        else:
            numero_real = numero_data
            lucky = []
            lucky_mults = {}
            mult = None
        
        self.bot.atualizar(numero_real, lucky, lucky_mults)
        self.historico_numeros.append(numero_real)
        self.historico_lucky.append(lucky)
        self.rodadas_sem_entrada += 1
        
        # Verifica resultado anterior
        if self.previsao_ativa:
            acerto = numero_real in self.previsao_ativa.get('numeros_apostar', [])
            self.bot.atualizar_resultado(acerto)
            
            if acerto:
                self.acertos += 1
            else:
                self.erros += 1
            
            enviar_resultado_auto(numero_real, acerto, mult)
            
            self.historico_desempenho.append({
                'numero': numero_real,
                'acerto': acerto,
                'multiplicador': mult,
                'forca': self.previsao_ativa.get('forca_real', 0),
                'confianca': self.previsao_ativa.get('confianca', 'Média')
            })
            
            self.previsao_ativa = None
            self.ultima_entrada_rodada = len(self.historico_numeros)
            self.rodadas_sem_entrada = 0
        
        if self.estrategia_ativa_manual:
            return
        
        intervalo = st.session_state.get('intervalo_minimo_entradas', 0)
        if len(self.historico_numeros) - self.ultima_entrada_rodada < intervalo:
            return
        
        if len(self.historico_numeros) >= 5:
            top_n = st.session_state.get('top_n_apostas', 4)
            forca_minima = st.session_state.get('forca_minima_sinal', 20)
            conservador = st.session_state.get('modo_conservador', True)
            
            nova = self.bot.sugerir_aposta(top_n, forca_minima, conservador)
            
            if nova and nova['forca_real'] >= forca_minima:
                self.previsao_ativa = nova
                enviar_previsao_auto(nova)
    
    def zerar_estatisticas(self):
        self.acertos = 0
        self.erros = 0
        self.historico_desempenho = []
        self.historico_numeros.clear()
        self.historico_lucky.clear()
        self.rodadas_sem_entrada = 0
        self.ultima_entrada_rodada = -10
        self.bot.zerar()
        salvar_sessao()
    
    def get_status(self):
        return {
            'acertos': self.acertos,
            'erros': self.erros,
            'total': self.acertos + self.erros,
            'rodadas_sem_entrada': self.rodadas_sem_entrada
        }


# =============================
# FUNÇÕES AUXILIARES
# =============================
def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    try:
        with open(caminho, "w") as f:
            json.dump(historico, f, indent=2)
    except:
        pass

def extrair_numeros_raio(resultado_api):
    numeros_raio = []
    multiplicadores = {}
    try:
        if resultado_api and isinstance(resultado_api, dict):
            data = resultado_api.get('data', {})
            result = data.get('result', {})
            for item in result.get('luckyNumbersList', []):
                n = item.get('number')
                if n is not None:
                    numeros_raio.append(n)
                    m = item.get('roundedMultiplier')
                    if m is not None:
                        multiplicadores[n] = m
    except:
        pass
    return numeros_raio, multiplicadores

def fetch_latest_result():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=5)
        response.raise_for_status()
        data = response.json()
        game_data = data.get("data", {})
        result = game_data.get("result", {})
        outcome = result.get("outcome", {})
        number = outcome.get("number")
        timestamp = game_data.get("startedAt")
        numeros_raio, multiplicadores = extrair_numeros_raio(data)
        return {"number": number, "timestamp": timestamp, "luckyNumbers": numeros_raio, "luckyMultipliers": multiplicadores}
    except:
        return None

def exportar_historico(historico, formato='json'):
    if formato == 'json':
        return json.dumps(historico, indent=2, ensure_ascii=False)
    else:
        linhas = ["numero,timestamp,multiplicador"]
        for item in historico:
            if isinstance(item, dict):
                n = item.get('number', '')
                ts = item.get('timestamp', '')
                mult = item.get('luckyMultipliers', {}).get(n, '')
                linhas.append(f"{n},{ts},{mult}")
            else:
                linhas.append(f"{item},,")
        return "\n".join(linhas)


# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🤖 Bot V3 — Assertivo", layout="centered")
st.title("🤖 Bot V3 — Reformulado")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()

defaults = {
    'top_n_apostas': 4, 'forca_minima_sinal': 20,
    'intervalo_minimo_entradas': 0, 'modo_automatico': True,
    'modo_conservador': True
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

carregar_sessao()

if "historico" not in st.session_state:
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                st.session_state.historico = json.load(f)
        except:
            st.session_state.historico = []
    else:
        st.session_state.historico = []

if "telegram_token" not in st.session_state:
    st.session_state.telegram_token = ""
if "telegram_chat_id" not in st.session_state:
    st.session_state.telegram_chat_id = ""

# Sidebar
st.sidebar.title("⚙️ Configurações")

with st.sidebar.expander("🤖 Bot V3", expanded=True):
    st.session_state.modo_conservador = st.checkbox("🛡️ Modo Conservador", value=st.session_state.modo_conservador,
        help="Não entra quando performance está ruim")
    st.session_state.top_n_apostas = st.slider("📊 Números por aposta", 3, 6, st.session_state.top_n_apostas)
    st.session_state.forca_minima_sinal = st.slider("⚡ Força mínima", 10, 40, st.session_state.forca_minima_sinal, 5)
    st.session_state.intervalo_minimo_entradas = st.slider("⏱️ Intervalo", 0, 2, st.session_state.intervalo_minimo_entradas)

st.session_state.modo_automatico = st.sidebar.checkbox("🔄 Automático", value=st.session_state.modo_automatico)
if st.sidebar.button("Atualizar"):
    st.session_state.sistema.estrategia_ativa_manual = not st.session_state.modo_automatico
    st.rerun()

with st.sidebar.expander("🧠 Análise", expanded=True):
    st.text(st.session_state.sistema.bot.get_analise_completa())

with st.sidebar.expander("💾 Geral", expanded=False):
    if st.button("💾 Salvar", use_container_width=True):
        salvar_sessao()
        st.success("✅")
    if st.button("🗑️ Zerar", use_container_width=True):
        if st.checkbox("Confirmar"):
            st.session_state.sistema.zerar_estatisticas()
            st.rerun()

with st.sidebar.expander("🔔 Telegram", expanded=False):
    st.session_state.telegram_token = st.text_input("Token:", value=st.session_state.telegram_token, type="password")
    st.session_state.telegram_chat_id = st.text_input("Chat ID:", value=st.session_state.telegram_chat_id)
    if st.button("Salvar"):
        salvar_sessao()
        st.success("✅")

# Inserção manual
st.subheader("✍️ Inserir Sorteios")
c1, c2 = st.columns([3, 1])
with c1:
    entrada = st.text_input("Números (0-36):", key="entrada_numeros")
with c2:
    if st.button("Adicionar", use_container_width=True) and entrada:
        try:
            nums = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
            for n in nums:
                item = {"number": n, "timestamp": f"m{len(st.session_state.historico)}", "luckyNumbers": [], "luckyMultipliers": {}}
                st.session_state.historico.append(item)
                st.session_state.sistema.processar_novo_numero(item)
            salvar_resultado_em_arquivo(st.session_state.historico)
            salvar_sessao()
            st.success(f"{len(nums)} adicionados!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro: {e}")

# Auto-refresh
st_autorefresh(interval=3000, key="refresh")

# API
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
    st.write(" ".join(fmt))

# Status
status = st.session_state.sistema.get_status()
c1, c2, c3, c4 = st.columns(4)
c1.metric("🟢 Acertos", status['acertos'])
c2.metric("🔴 Erros", status['erros'])
c3.metric("📊 Total", status['total'])
c4.metric("⏳ Sem Entrada", status['rodadas_sem_entrada'])

if status['total'] > 0:
    taxa = status['acertos'] / status['total'] * 100
    if taxa >= 30:
        st.success(f"🎯 Taxa: {taxa:.1f}%")
    elif taxa >= 20:
        st.warning(f"🎯 Taxa: {taxa:.1f}%")
    else:
        st.error(f"🎯 Taxa: {taxa:.1f}%")

# Previsão
st.subheader("🎯 Previsão Ativa")
sis = st.session_state.sistema

if sis.estrategia_ativa_manual:
    st.warning("⚠️ MANUAL")
elif sis.previsao_ativa:
    p = sis.previsao_ativa
    f = p.get('forca_real', 0)
    c = p.get('confianca', 'Média')
    
    if c == "Alta":
        st.success(f"🟢 **CONFIANÇA ALTA** - {p['gatilho']}")
    elif c == "Média":
        st.warning(f"🟡 **CONFIANÇA MÉDIA** - {p['gatilho']}")
    else:
        st.error(f"🔴 **CONFIANÇA BAIXA** - {p['gatilho']}")
    
    st.write(f"**🔢 {len(p['numeros_apostar'])} números:**")
    nums = sorted(p['numeros_apostar'])
    cols = st.columns(len(nums))
    for i, num in enumerate(nums):
        cols[i].write(f"**{num}**")
else:
    st.info(f"🎲 Aguardando... ({status['rodadas_sem_entrada']} rodadas)")

# Performance
st.subheader("📈 Performance")
taxa_bot = sis.bot.get_taxa_acerto()
total_bot = sis.bot.get_total_tentativas()

if total_bot > 0:
    emoji = "🟢" if taxa_bot >= 0.30 else "🟡" if taxa_bot >= 0.20 else "🔴"
    st.write(f"{emoji} **Bot**: {taxa_bot:.0%} ({sis.bot.performance['acertos']}/{total_bot})")

# Histórico
if sis.historico_desempenho:
    st.write("**🔍 Últimas:**")
    for r in sis.historico_desempenho[-5:]:
        e = "🎉" if r['acerto'] else "❌"
        m = f" ⚡{r['multiplicador']}x" if r.get('multiplicador') and r['acerto'] else ""
        c = r.get('confianca', '')[0] if r.get('confianca') else ''
        st.write(f"{e} [{c}] ({r.get('forca',0)}%): {r['numero']}{m}")

# Download
st.subheader("📥 Download")
total_registros = len(st.session_state.historico)
st.metric("📊 Registros", total_registros)

col_d1, col_d2 = st.columns(2)
with col_d1:
    if st.button("📥 JSON", use_container_width=True):
        json_data = exportar_historico(st.session_state.historico, 'json')
        st.download_button("⬇️ Baixar", json_data, f"historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "application/json")
with col_d2:
    if st.button("📥 CSV", use_container_width=True):
        csv_data = exportar_historico(st.session_state.historico, 'csv')
        st.download_button("⬇️ Baixar", csv_data, f"historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv")

salvar_sessao()
