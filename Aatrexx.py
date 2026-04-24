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
        confianca = previsao.get('confianca', 'Média')
        estrategias = previsao.get('estrategias_ativas', [])
        forca = previsao.get('forca_real', 0)
        
        emoji = "🟢" if confianca == "Alta" else "🟡" if confianca == "Média" else "🔴"
        
        msg = f"{emoji} **ENTRADA** - Força: {forca}%\n"
        msg += f"📋 {previsao['gatilho']}\n"
        if estrategias:
            msg += f"🎯 Estratégias: {', '.join(estrategias)}\n"
        msg += f"🔢 {len(numeros)} números: {numeros}"
        
        st.toast(f"🎯 Entrada - {confianca}", icon=emoji)
        st.success(f"🔔 {msg}")
        
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            enviar_telegram(f"🔔 ENTRADA [{confianca}]\n{msg}")
        
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
# ANALISADOR ROLETA VERSÁTIL (SNIPER)
# =============================
class AnalisadorRoletaVersatil:
    def __init__(self, janela_analise=37):
        self.janela_analise = janela_analise
        self.layout_roda = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 
                           11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 
                           9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        self.vermelhos = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        self.pretos = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
        
    def mapear_propriedades(self, n):
        if n == 0:
            return {'cor': 'Verde', 'duzia': 0, 'coluna': 0, 'paridade': 'Zero', 'alto_baixo': 'Zero'}
        return {
            'cor': 'Vermelho' if n in self.vermelhos else 'Preto',
            'duzia': (n-1)//12 + 1,
            'coluna': (n-1)%3 + 1,
            'paridade': 'Par' if n % 2 == 0 else 'Ímpar',
            'alto_baixo': 'Alto' if n >= 19 else 'Baixo'
        }
    
    def get_vizinhos_roda(self, numero, raio=2):
        if numero not in self.layout_roda:
            return []
        idx = self.layout_roda.index(numero)
        return [self.layout_roda[(idx + i) % 37] for i in range(-raio, raio + 1)]
    
    def analisar(self, historico_numeros, lucky_recentes=None):
        if len(historico_numeros) < 15: 
            return None
        
        recentes_curto = historico_numeros[-15:]
        recentes_longo = historico_numeros[-self.janela_analise:]
        
        dados_curto = [self.mapear_propriedades(n) for n in recentes_curto]
        ultimo = recentes_curto[-1]
        
        frequencia = Counter(recentes_longo)
        quentes = [num for num, _ in frequencia.most_common(5)]
        
        duzias = Counter([d['duzia'] for d in dados_curto if d['duzia'] != 0])
        colunas = Counter([c['coluna'] for c in dados_curto if c['coluna'] != 0])
        
        melhor_duzia = duzias.most_common(1)[0][0] if duzias else None
        melhor_coluna = colunas.most_common(1)[0][0] if colunas else None
        
        roda_hits = []
        for n in recentes_curto:
            roda_hits.extend(self.get_vizinhos_roda(n, raio=1))
        zona_quente = Counter(roda_hits).most_common(1)[0][0] if roda_hits else None
        
        forca = 0
        gatilho_principal = ""
        estrategia = []
        
        if melhor_duzia and melhor_coluna:
            hits_duzia = duzias.get(melhor_duzia, 0)
            hits_coluna = colunas.get(melhor_coluna, 0)
            if hits_duzia >= 7 and hits_coluna >= 6: 
                forca += 60
                gatilho_principal = f"Cruzamento D{melhor_duzia} x C{melhor_coluna}"
                estrategia.append("Interseção D/C")
        
        vizinhos_da_zona = self.get_vizinhos_roda(zona_quente, raio=2) if zona_quente is not None else []
        hits_na_zona = sum(1 for n in recentes_curto if n in vizinhos_da_zona)
        if hits_na_zona >= 5: 
            forca += 50
            gatilho_principal = f"Zona da Roda: {zona_quente}"
            estrategia.append("Cluster Físico")

        lucky_quentes = []
        if lucky_recentes:
            lucky_quentes = [n for n, _ in Counter(lucky_recentes).most_common(3)]
            if any(l in recentes_curto for l in lucky_quentes):
                forca += 15
                estrategia.append("Raios Quentes")

        return {
            'quentes': quentes,
            'melhor_duzia': melhor_duzia,
            'melhor_coluna': melhor_coluna,
            'zona_quente': zona_quente,
            'vizinhos_zona': vizinhos_da_zona,
            'lucky_quentes': lucky_quentes,
            'forca_sinal': min(100, forca),
            'gatilho': gatilho_principal,
            'estrategia': estrategia,
            'ultimo': ultimo
        }


# =============================
# BOT V3 (SNIPER)
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
            self.lucky_mult = self.lucky_mult[-100:]
    
    def atualizar_resultado(self, acerto):
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
    
    def get_total_tentativas(self):
        return self.performance['acertos'] + self.performance['erros']
    
    def sugerir_aposta(self, top_n=5, forca_minima=40, modo_conservador=True):
        if len(self.historico) < 15:
            logging.info("Histórico insuficiente (< 15)")
            return None
            
        lucky_recentes = []
        for sub in self.lucky[-15:]:
            lucky_recentes.extend(sub)
            
        analise = self.analisador.analisar(list(self.historico), lucky_recentes)
        
        if not analise or analise['forca_sinal'] < forca_minima:
            logging.info(f"Sinal fraco ou sem análise. Força: {analise['forca_sinal'] if analise else 0}")
            return None 
            
        base = set()
        
        if "Interseção D/C" in analise['estrategia']:
            d = analise['melhor_duzia']
            c = analise['melhor_coluna']
            if d and c:
                numeros_duzia = range((d-1)*12 + 1, d*12 + 1)
                numeros_coluna = range(c, 37, 3)
                intersecao = set(numeros_duzia).intersection(set(numeros_coluna))
                base.update(intersecao)
            
        if "Cluster Físico" in analise['estrategia']:
            base.update(analise['vizinhos_zona'])
            
        prioridade = list(base)
        for n in analise['quentes']:
            if n not in prioridade:
                prioridade.append(n)
                
        base_list = prioridade[:top_n]
        
        confianca = "Alta" if analise['forca_sinal'] >= 70 else "Média"
        
        if modo_conservador and len(self.performance['historico']) >= 10:
            taxa_recente = sum(self.performance['historico'][-10:]) / 10
            if taxa_recente <= 0.10:
                logging.info(f"Bloqueado por taxa recente baixa: {taxa_recente}")
                return None
                
        return {
            'nome': 'Bot V3 Sniper',
            'numeros_apostar': sorted(base_list),
            'gatilho': analise['gatilho'] or "Tendência Global",
            'forca_real': analise['forca_sinal'],
            'confianca': confianca,
            'estrategias_ativas': analise['estrategia'],
            'analise': analise
        }
    
    def get_analise_completa(self):
        if len(self.historico) < 15:
            return "📊 Aguardando dados (mínimo 15)..."
        
        lucky_recentes = []
        for sub in self.lucky[-15:]:
            lucky_recentes.extend(sub)
        
        analise = self.analisador.analisar(list(self.historico), lucky_recentes)
        
        if not analise:
            return "📊 Analisando..."
        
        taxa = self.get_taxa_acerto()
        total = self.get_total_tentativas()
        
        txt = "🎯 ANÁLISE SNIPER\n" + "="*35 + "\n\n"
        txt += f"🎲 Último: {analise['ultimo']}\n"
        txt += f"📊 Janela: {self.analisador.janela_analise} giros\n"
        txt += f"⚡ Força: {analise['forca_sinal']}%\n\n"
        
        txt += f"🔥 Quentes: {analise['quentes']}\n"
        txt += f"🎯 Dúzia Quente: {analise.get('melhor_duzia', 'N/A')}\n"
        txt += f"🎯 Coluna Quente: {analise.get('melhor_coluna', 'N/A')}\n"
        txt += f"📍 Zona Roda: {analise.get('zona_quente', 'N/A')}\n"
        txt += f"🍀 Lucky Quentes: {analise['lucky_quentes'][:3]}\n"
        
        if analise.get('gatilho'):
            txt += f"\n🧠 Gatilho: {analise['gatilho']}\n"
        
        if total > 0:
            txt += f"\n📈 Perf: {taxa:.0%} ({self.performance['acertos']}/{total})\n"
        
        return txt
    
    def zerar(self):
        self.historico = []
        self.lucky = []
        self.lucky_mult = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}


# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaBot:
    def __init__(self):
        self.bot = RoletaBotV3(janela_analise=37)
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
        
        if len(self.historico_numeros) >= 15:
            top_n = st.session_state.get('top_n_apostas', 5)
            forca_minima = st.session_state.get('forca_minima_sinal', 40)
            conservador = st.session_state.get('modo_conservador', True)
            
            nova = self.bot.sugerir_aposta(top_n, forca_minima, conservador)
            
            if nova is not None:
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
st.set_page_config(page_title="🤖 Bot V3 — Sniper", layout="centered")
st.title("🤖 Bot V3 — Estratégia Sniper")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()

# Valores padrão ajustados para a nova estratégia
defaults = {
    'top_n_apostas': 5, 'forca_minima_sinal': 40,
    'intervalo_minimo_entradas': 0, 'modo_automatico': True,
    'modo_conservador': True, 'janela_analise': 37
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

with st.sidebar.expander("🤖 Bot V3 (Sniper)", expanded=True):
    st.session_state.janela_analise = st.slider("🪟 Janela Longa", 15, 100, st.session_state.janela_analise, 5)
    st.session_state.modo_conservador = st.checkbox("🛡️ Drawdown Control", value=st.session_state.modo_conservador,
        help="Pausa se a taxa de acerto cair abaixo de 10% nas últimas 10 entradas")
    st.session_state.top_n_apostas = st.slider("📊 Máx. Números", 3, 8, st.session_state.top_n_apostas)
    st.session_state.forca_minima_sinal = st.slider("⚡ Força mínima", 10, 80, st.session_state.forca_minima_sinal, 5)
    st.session_state.intervalo_minimo_entradas = st.slider("⏱️ Intervalo", 0, 5, st.session_state.intervalo_minimo_entradas)

st.session_state.modo_automatico = st.sidebar.checkbox("🔄 Automático", value=st.session_state.modo_automatico)
if st.sidebar.button("Atualizar Configs"):
    st.session_state.sistema.bot.analisador.janela_analise = st.session_state.janela_analise
    st.session_state.sistema.estrategia_ativa_manual = not st.session_state.modo_automatico
    st.rerun()

with st.sidebar.expander("🧠 Visão da IA", expanded=True):
    st.text(st.session_state.sistema.bot.get_analise_completa())

with st.sidebar.expander("💾 Geral", expanded=False):
    if st.button("💾 Salvar Estado", use_container_width=True):
        salvar_sessao()
        st.success("Sessão salva com sucesso!")
    if st.button("🗑️ Zerar Tudo", use_container_width=True):
        if st.checkbox("Confirmo que desejo apagar os dados"):
            st.session_state.sistema.zerar_estatisticas()
            st.rerun()

with st.sidebar.expander("🔔 Telegram", expanded=False):
    st.session_state.telegram_token = st.text_input("Bot Token:", value=st.session_state.telegram_token, type="password")
    st.session_state.telegram_chat_id = st.text_input("ID do Chat/Canal:", value=st.session_state.telegram_chat_id)
    if st.button("Salvar API"):
        salvar_sessao()
        st.success("API salva!")

# Inserção manual
st.subheader("✍️ Inserção Manual")
c1, c2 = st.columns([3, 1])
with c1:
    entrada = st.text_input("Digite os números (ex: 0 15 32):")
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

# Integração API Externa
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

# Mesa dos Últimos números
st.subheader("🔁 Painel Recentes")
if st.session_state.historico:
    ultimos = st.session_state.historico[-15:]
    fmt = []
    for item in ultimos:
        n = item['number'] if isinstance(item, dict) else item
        if isinstance(item, dict) and n in item.get('luckyNumbers', []):
            mult = item.get('luckyMultipliers', {}).get(n, '')
            fmt.append(f"⚡**{n}**({mult}x)" if mult else f"⚡**{n}**")
        else:
            fmt.append(str(n))
    st.write(" ".join(fmt))
else:
    st.write("Aguardando giros da roleta...")

# Quadro de Status
status = st.session_state.sistema.get_status()
c1, c2, c3, c4 = st.columns(4)
c1.metric("🟢 Greens", status['acertos'])
c2.metric("🔴 Reds", status['erros'])
c3.metric("📊 Apostas", status['total'])
c4.metric("⏳ Espera", f"{status['rodadas_sem_entrada']} rodadas")

if status['total'] > 0:
    taxa = status['acertos'] / status['total'] * 100
    if taxa >= 30:
        st.success(f"🎯 Win Rate: {taxa:.1f}%")
    elif taxa >= 15:
        st.warning(f"🎯 Win Rate: {taxa:.1f}%")
    else:
        st.error(f"🎯 Win Rate: {taxa:.1f}%")

# Alerta de Previsão Ativa
st.subheader("🎯 Sinal Ativo")
sis = st.session_state.sistema

if sis.estrategia_ativa_manual:
    st.warning("⚠️ BOT EM MODO MANUAL")
elif sis.previsao_ativa:
    p = sis.previsao_ativa
    f = p.get('forca_real', 0)
    c = p.get('confianca', 'Média')
    estrategias = p.get('estrategias_ativas', [])
    
    if c == "Alta":
        st.success(f"🟢 **CONFIANÇA ALTA** - Força do Sinal: {f}%\n\nMotivo: {p['gatilho']}")
    elif c == "Média":
        st.warning(f"🟡 **CONFIANÇA MÉDIA** - Força do Sinal: {f}%\n\nMotivo: {p['gatilho']}")
    else:
        st.info(f"🔵 **BAIXA CONFIANÇA** - Força do Sinal: {f}%\n\nMotivo: {p['gatilho']}")
    
    if estrategias:
        st.caption(f"⚙️ Abordagem Técnica: {', '.join(estrategias)}")
    
    st.write(f"**🔢 Apostar nestes {len(p['numeros_apostar'])} números:**")
    nums = sorted(p['numeros_apostar'])
    cols = st.columns(len(nums))
    for i, num in enumerate(nums):
        cols[i].write(f"**{num}**")
else:
    if len(sis.historico_numeros) < 15:
         st.info(f"⚙️ Coletando amostras iniciais... ({len(sis.historico_numeros)}/15)")
    else:
         st.info(f"🎲 Aguardando alinhamento estratégico do mercado... (Espera atual: {status['rodadas_sem_entrada']} giros)")

# Painel de Desempenho
st.subheader("📈 Controle de Banca (Bot)")
taxa_bot = sis.bot.get_taxa_acerto()
total_bot = sis.bot.get_total_tentativas()
if total_bot > 0:
    emoji = "🟢" if taxa_bot >= 0.20 else "🟡" if taxa_bot >= 0.10 else "🔴"
    st.write(f"{emoji} **Desempenho Geral**: {taxa_bot:.0%} ({sis.bot.performance['acertos']}/{total_bot})")
else:
    st.write("⚪ Histórico limpo")

# Últimos Resultados
if sis.historico_desempenho:
    st.write("**🔍 Backtest Imediato:**")
    for r in sis.historico_desempenho[-5:]:
        e = "🎉 Win" if r['acerto'] else "❌ Loss"
        m = f" ⚡{r['multiplicador']}x" if r.get('multiplicador') and r['acerto'] else ""
        st.write(f"{e} (Força {r.get('forca',0)}%): Aposta bateu no número {r['numero']}{m}")

# Download e Exportação
st.subheader("📥 Exportar Logs")
st.metric("📊 Total de Lançamentos Gravados", len(st.session_state.historico))
col_d1, col_d2 = st.columns(2)
with col_d1:
    if st.button("📥 Baixar JSON", use_container_width=True):
        st.download_button("⬇️ Download DB", exportar_historico(st.session_state.historico, 'json'),
                          f"log_roleta_{datetime.now().strftime('%Y%m%d_%H%M')}.json", "application/json")
with col_d2:
    if st.button("📥 Baixar CSV", use_container_width=True):
        st.download_button("⬇️ Download Tabela", exportar_historico(st.session_state.historico, 'csv'),
                          f"log_roleta_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv")

salvar_sessao()
