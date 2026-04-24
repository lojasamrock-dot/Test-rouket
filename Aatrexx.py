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
            'forca_minima_sinal': st.session_state.get('forca_minima_sinal', 30),
            'intervalo_minimo_entradas': st.session_state.get('intervalo_minimo_entradas', 0),
            'modo_automatico': st.session_state.get('modo_automatico', True)
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
            st.session_state.forca_minima_sinal = session_data.get('forca_minima_sinal', 30)
            st.session_state.intervalo_minimo_entradas = session_data.get('intervalo_minimo_entradas', 0)
            st.session_state.modo_automatico = session_data.get('modo_automatico', True)
            
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
        modo = previsao.get('modo', 'NORMAL')
        forca = previsao.get('forca_sinal', 0)
        
        emoji_modo = {'REPETICAO': '🔥', 'DISPERSAO': '❄️', 'NORMAL': '🎯'}
        emoji = emoji_modo.get(modo, '🎲')
        
        msg = f"{emoji} **MODO {modo}** - Força {forca}%\n"
        msg += f"📋 {previsao['gatilho']}\n"
        msg += f"🔢 {len(numeros)} números"
        
        st.toast(f"🎯 {modo} - F{forca}%", icon=emoji)
        st.success(f"🔔 {msg}")
        
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            enviar_telegram(f"🔔 BOT V3 - MODO {modo}\n{msg}\n" + " ".join(map(str, numeros)))
        
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
# BOT V3 ADAPTATIVO
# =============================
class RoletaBotV3:
    def __init__(self):
        self.roleta = RoletaBase()
        self.historico = []
        self.lucky = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        
    def atualizar(self, numero, lucky_nums=None):
        self.historico.append(numero)
        self.lucky.append(lucky_nums if lucky_nums else [])
        if len(self.historico) > 50:
            self.historico = self.historico[-50:]
            self.lucky = self.lucky[-50:]
    
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
        return self.performance['acertos'] / total if total > 0 else 0.5
    
    def get_taxa_recente(self, ultimas=5):
        hist = self.performance['historico']
        if len(hist) < ultimas:
            return self.get_taxa_acerto()
        recentes = hist[-ultimas:]
        return sum(recentes) / len(recentes) if recentes else 0.5
    
    def get_total_tentativas(self):
        return self.performance['acertos'] + self.performance['erros']
    
    def get_atraso(self, n):
        for i, val in enumerate(reversed(self.historico)):
            if val == n:
                return i
        return 50
    
    def cluster_bonus(self, n):
        if len(self.historico) < 10:
            return 0
        ultimos = self.historico[-10:]
        dezenas = [x // 10 for x in ultimos]
        dezena_dominante = Counter(dezenas).most_common(1)[0][0]
        return 1 if n // 10 == dezena_dominante else 0
    
    def detectar_modo(self):
        if len(self.historico) < 10:
            return "NORMAL"
        
        repeticoes = sum(1 for i in range(1, len(self.historico)) if self.historico[i] == self.historico[i-1])
        variedade = len(set(self.historico[-10:]))
        
        if repeticoes >= 2:
            return "REPETICAO"
        elif variedade >= 9:
            return "DISPERSAO"
        else:
            return "NORMAL"
    
    def ajustar_pesos(self, modo):
        if modo == "REPETICAO":
            return {
                'freq_10': 2.5, 'freq_20': 1.5, 'lucky': 1.8,
                'repeticao': 5.0, 'atraso': 0.3, 'cluster': 1.5
            }
        elif modo == "DISPERSAO":
            return {
                'freq_10': 1.5, 'freq_20': 2.0, 'lucky': 2.0,
                'repeticao': 1.5, 'atraso': 1.5, 'cluster': 1.0
            }
        else:
            return {
                'freq_10': 2.0, 'freq_20': 1.5, 'lucky': 1.8,
                'repeticao': 3.0, 'atraso': 0.7, 'cluster': 1.2
            }
    
    def calcular_score(self):
        """Retorna scores, detalhes, modo, pesos"""
        if len(self.historico) < 5:
            # Retorna valores vazios mas com a estrutura correta
            return {}, {}, "NORMAL", self.ajustar_pesos("NORMAL")
        
        scores = {}
        detalhes = {}
        
        ult_10 = self.historico[-10:]
        ult_20 = self.historico[-20:] if len(self.historico) >= 20 else self.historico
        
        freq10 = Counter(ult_10)
        freq20 = Counter(ult_20)
        
        # Lucky numbers recentes
        lucky_flat = []
        for sub in self.lucky[-10:]:
            if sub:
                lucky_flat.extend(sub)
        lucky_count = Counter(lucky_flat)
        
        modo = self.detectar_modo()
        pesos = self.ajustar_pesos(modo)
        
        for n in range(37):
            atraso = self.get_atraso(n)
            repeticao = 1 if len(self.historico) > 1 and self.historico[-1] == n else 0
            cluster = self.cluster_bonus(n)
            
            score = (
                freq10[n] * pesos['freq_10'] +
                freq20[n] * pesos['freq_20'] +
                lucky_count[n] * pesos['lucky'] +
                repeticao * pesos['repeticao'] -
                atraso * pesos['atraso'] +
                cluster * pesos['cluster']
            )
            
            scores[n] = score
            detalhes[n] = {
                'freq10': freq10[n],
                'freq20': freq20[n],
                'lucky': lucky_count[n],
                'repeticao': repeticao,
                'atraso': atraso,
                'cluster': cluster,
                'score': score
            }
        
        return scores, detalhes, modo, pesos
    
    def sugerir_aposta(self, top_n=5, forca_minima=30):
        if len(self.historico) < 5:
            return None
        
        scores, detalhes, modo, pesos = self.calcular_score()
        
        if not scores:
            return None
        
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        picks = [n for n, s in top[:top_n]]
        
        # Expansão com vizinhos
        numeros_final = set(picks)
        for pick in picks[:3]:
            vizinhos = self.roleta.get_vizinhos(pick, raio=1)
            numeros_final.update(vizinhos[:1])
        
        numeros_final = list(numeros_final)[:top_n + 2]
        
        # Força do sinal
        if picks and scores:
            score_max = max(scores.values())
            score_medio = sum(scores[n] for n in picks[:3]) / min(3, len(picks))
            forca = min(100, max(20, int(score_medio / (score_max + 1) * 100) if score_max > 0 else 40))
        else:
            forca = 20
        
        # Gatilho
        gatilho = f"Modo: {modo}"
        if len(self.historico) >= 2 and self.historico[-1] == self.historico[-2]:
            gatilho += f" | REPETIU {self.historico[-1]}"
        
        return {
            'nome': f'Bot V3 ({modo})',
            'numeros_apostar': sorted(numeros_final),
            'gatilho': gatilho,
            'forca_sinal': forca,
            'modo': modo,
            'pesos': pesos,
            'scores': top[:10],
            'detalhes': {n: detalhes[n] for n in picks if n in detalhes}
        }
    
    def get_analise_completa(self):
        if len(self.historico) < 5:
            return "📊 Aguardando dados (mínimo 5 números)..."
        
        scores, detalhes, modo, pesos = self.calcular_score()
        
        if not scores:
            return "📊 Calculando scores..."
        
        taxa = self.get_taxa_acerto()
        total = self.get_total_tentativas()
        
        analise = "🎯 BOT V3 ADAPTATIVO\n" + "="*40 + "\n\n"
        analise += f"🎲 Último: {self.historico[-1] if self.historico else '?'}\n"
        analise += f"📊 10 últimos: {self.historico[-10:] if len(self.historico) >= 10 else self.historico}\n\n"
        
        analise += f"🔍 MODO: {modo}\n"
        analise += f"⚖️ Pesos: R={pesos['repeticao']:.1f} A={pesos['atraso']:.1f} F10={pesos['freq_10']:.1f}\n\n"
        
        analise += "🏆 TOP 5 Scores:\n"
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
        for i, (n, s) in enumerate(top, 1):
            det = detalhes.get(n, {})
            analise += f"  {i}. {n:2d}: {s:.1f} (F10:{det.get('freq10',0)} F20:{det.get('freq20',0)} L:{det.get('lucky',0)} R:{det.get('repeticao',0)} A:{det.get('atraso',0)})\n"
        
        if total > 0:
            analise += f"\n📈 Perf: {taxa:.0%} ({self.performance['acertos']}/{total})\n"
        
        return analise
    
    def zerar(self):
        self.historico = []
        self.lucky = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}


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
            mult = numero_data.get('luckyMultipliers', {}).get(numero_real) if numero_real in lucky else None
        else:
            numero_real = numero_data
            lucky = []
            mult = None
        
        self.bot.atualizar(numero_real, lucky)
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
                'forca': self.previsao_ativa.get('forca_sinal', 0),
                'modo': self.previsao_ativa.get('modo', 'NORMAL')
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
            top_n = st.session_state.get('top_n_apostas', 5)
            forca_minima = st.session_state.get('forca_minima_sinal', 30)
            
            nova = self.bot.sugerir_aposta(top_n, forca_minima)
            
            if nova and nova['forca_sinal'] >= forca_minima:
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
st.set_page_config(page_title="🤖 Bot V3 — Roleta Adaptativo", layout="centered")
st.title("🤖 Bot V3 — Motor Adaptativo")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()

# Valores padrão
defaults = {
    'top_n_apostas': 5, 'forca_minima_sinal': 30,
    'intervalo_minimo_entradas': 0, 'modo_automatico': True
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
    st.session_state.top_n_apostas = st.slider("📊 Números por aposta", 3, 8, st.session_state.top_n_apostas)
    st.session_state.forca_minima_sinal = st.slider("⚡ Força mínima", 20, 50, st.session_state.forca_minima_sinal, 5)
    st.session_state.intervalo_minimo_entradas = st.slider("⏱️ Intervalo entre entradas", 0, 3, st.session_state.intervalo_minimo_entradas)

# Modo automático
st.session_state.modo_automatico = st.sidebar.checkbox("🔄 Modo Automático", value=st.session_state.modo_automatico)
if st.sidebar.button("Atualizar Modo"):
    st.session_state.sistema.estrategia_ativa_manual = not st.session_state.modo_automatico
    st.rerun()

if st.session_state.sistema.estrategia_ativa_manual:
    st.sidebar.warning("⚠️ MANUAL")
else:
    st.sidebar.success("✅ AUTO")

with st.sidebar.expander("🧠 Análise V3", expanded=True):
    st.text(st.session_state.sistema.bot.get_analise_completa())

with st.sidebar.expander("💾 Geral", expanded=False):
    if st.button("💾 Salvar", use_container_width=True):
        salvar_sessao()
        st.success("✅ Salvo!")
    if st.button("🗑️ Zerar", use_container_width=True):
        if st.checkbox("Confirmar"):
            st.session_state.sistema.zerar_estatisticas()
            st.rerun()

with st.sidebar.expander("🔔 Telegram", expanded=False):
    st.session_state.telegram_token = st.text_input("Token:", value=st.session_state.telegram_token, type="password")
    st.session_state.telegram_chat_id = st.text_input("Chat ID:", value=st.session_state.telegram_chat_id)
    if st.button("Salvar Telegram"):
        salvar_sessao()
        st.success("✅")

# Inserção manual
st.subheader("✍️ Inserir Sorteios")
entrada = st.text_input("Números (0-36):")
if st.button("Adicionar") and entrada:
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
else:
    st.write("Nenhum número")

# Status
status = st.session_state.sistema.get_status()
c1, c2, c3, c4 = st.columns(4)
c1.metric("🟢 Acertos", status['acertos'])
c2.metric("🔴 Erros", status['erros'])
c3.metric("📊 Total", status['total'])
c4.metric("⏳ Sem Entrada", status['rodadas_sem_entrada'])

if status['total'] > 0:
    taxa = status['acertos'] / status['total'] * 100
    st.caption(f"🎯 Taxa: {taxa:.1f}%")

# Detecção de modo
if len(st.session_state.sistema.historico_numeros) >= 10:
    modo = st.session_state.sistema.bot.detectar_modo()
    emoji_modo = {'REPETICAO': '🔥', 'DISPERSAO': '❄️', 'NORMAL': '🎯'}
    st.info(f"{emoji_modo.get(modo, '🎲')} **Modo detectado: {modo}**")

# Previsão
st.subheader("🎯 Previsão Ativa")
sis = st.session_state.sistema

if sis.estrategia_ativa_manual:
    st.warning("⚠️ MANUAL")
elif sis.previsao_ativa:
    p = sis.previsao_ativa
    f = p.get('forca_sinal', 0)
    m = p.get('modo', 'NORMAL')
    emoji = {'REPETICAO': '🔥', 'DISPERSAO': '❄️', 'NORMAL': '🎯'}.get(m, '🎲')
    barras = "█"*(f//10) + "░"*(10-f//10)
    
    st.success(f"{emoji} **BOT V3 [{m}]** - F:{f}% {barras}")
    st.caption(f"📋 {p['gatilho']}")
    st.write(f"**🔢 {len(p['numeros_apostar'])} números:**")
    
    nums = sorted(p['numeros_apostar'])
    cols = st.columns(5)
    for i, num in enumerate(nums):
        cols[i%5].write(f"**{num}**")
else:
    st.info(f"🎲 Aguardando... ({status['rodadas_sem_entrada']} rodadas)")

# Performance
st.subheader("📈 Performance Bot V3")
taxa_bot = sis.bot.get_taxa_acerto()
total_bot = sis.bot.get_total_tentativas()

if total_bot > 0:
    emoji = "🟢" if taxa_bot >= 0.30 else "🟡" if taxa_bot >= 0.20 else "🔴"
    st.write(f"{emoji} **Bot V3**: {taxa_bot:.0%} ({sis.bot.performance['acertos']}/{total_bot})")
else:
    st.write("⚪ Coletando dados...")

# Histórico
if sis.historico_desempenho:
    st.write("**🔍 Últimas:**")
    for r in sis.historico_desempenho[-5:]:
        e = "🎉" if r['acerto'] else "❌"
        m = f" ⚡{r['multiplicador']}x" if r.get('multiplicador') and r['acerto'] else ""
        mod = r.get('modo', '')
        st.write(f"{e} Bot V3 [{mod}] ({r.get('forca',0)}%): {r['numero']}{m}")

# Download
st.subheader("📥 Download do Histórico")
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
