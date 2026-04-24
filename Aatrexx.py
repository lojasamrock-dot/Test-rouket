import streamlit as st
import json
import os
import requests
import logging
from collections import Counter, deque, defaultdict
from streamlit_autorefresh import st_autorefresh
import pickle
import math
from datetime import datetime

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_roleta.json"
PERFORMANCE_PATH = "performance_ia.json"

def salvar_sessao():
    try:
        if 'sistema' in st.session_state:
            performance_data = {
                'acertos': st.session_state.sistema.ia.performance['acertos'],
                'erros': st.session_state.sistema.ia.performance['erros'],
                'historico': st.session_state.sistema.ia.performance['historico']
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
            'historico_multiplicadores': list(st.session_state.sistema.historico_multiplicadores),
            'historico_lucky_numbers': st.session_state.sistema.historico_lucky_numbers,
            'estrategia_ativa_manual': st.session_state.sistema.estrategia_ativa_manual,
            'modo_sniper': st.session_state.get('modo_sniper', True),
            'modo_seguro': st.session_state.get('modo_seguro', False),
            'intervalo_minimo_entradas': st.session_state.get('intervalo_minimo_entradas', 0),
            'max_numeros_entrada': st.session_state.get('max_numeros_entrada', 8),
            'forca_minima_sinal': st.session_state.get('forca_minima_sinal', 35),
            'priorizar_repeticao': st.session_state.get('priorizar_repeticao', True),
            'usar_lucky_numbers': st.session_state.get('usar_lucky_numbers', True),
            'modo_agressivo': st.session_state.get('modo_agressivo', True)
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
            
            st.session_state.modo_sniper = session_data.get('modo_sniper', True)
            st.session_state.modo_seguro = session_data.get('modo_seguro', False)
            st.session_state.intervalo_minimo_entradas = session_data.get('intervalo_minimo_entradas', 0)
            st.session_state.max_numeros_entrada = session_data.get('max_numeros_entrada', 8)
            st.session_state.forca_minima_sinal = session_data.get('forca_minima_sinal', 35)
            st.session_state.priorizar_repeticao = session_data.get('priorizar_repeticao', True)
            st.session_state.usar_lucky_numbers = session_data.get('usar_lucky_numbers', True)
            st.session_state.modo_agressivo = session_data.get('modo_agressivo', True)
            
            if 'sistema' in st.session_state:
                st.session_state.sistema.acertos = session_data.get('sistema_acertos', 0)
                st.session_state.sistema.erros = session_data.get('sistema_erros', 0)
                st.session_state.sistema.historico_desempenho = session_data.get('sistema_historico_desempenho', [])
                st.session_state.sistema.historico_numeros = deque(session_data.get('historico_numeros', []), maxlen=200)
                st.session_state.sistema.historico_multiplicadores = deque(session_data.get('historico_multiplicadores', []), maxlen=200)
                st.session_state.sistema.historico_lucky_numbers = session_data.get('historico_lucky_numbers', [])
                st.session_state.sistema.estrategia_ativa_manual = session_data.get('estrategia_ativa_manual', False)
            
            if os.path.exists(PERFORMANCE_PATH) and 'sistema' in st.session_state:
                with open(PERFORMANCE_PATH, 'r') as f:
                    perf = json.load(f)
                    st.session_state.sistema.ia.performance = {
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
    except Exception as e:
        logging.error(f"❌ Erro ao limpar: {e}")

# =============================
# NOTIFICAÇÕES
# =============================
def enviar_previsao_auto(previsao):
    try:
        numeros = sorted(previsao['numeros_apostar'])
        forca = previsao.get('forca_sinal', 0)
        emoji = "🔥" if forca >= 60 else "🎯"
        
        msg = f"{emoji} **ENTRADA** - Força {forca}%\n"
        msg += f"📋 {previsao['gatilho']}\n"
        msg += f"🔢 {len(numeros)} números"
        
        st.toast(f"🎯 Entrada - F{forca}%", icon=emoji)
        st.success(f"🔔 {msg}")
        
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            enviar_telegram(f"🔔 ENTRADA\n{msg}\n" + " ".join(map(str, numeros)))
        
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
    except Exception as e:
        logging.error(f"Erro ao enviar: {e}")

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
    
    def get_vizinhos_proximos(self, numero, quantidade=1):
        """Retorna apenas os vizinhos mais próximos (1 de cada lado)"""
        if numero not in self.race:
            return []
        posicao = self.race.index(numero)
        return [
            self.race[(posicao - 1) % 37],
            self.race[(posicao + 1) % 37]
        ]


# =============================
# IA OTIMIZADA (BASEADA NO HISTÓRICO REAL)
# =============================
class RoletaIA:
    def __init__(self):
        self.roleta = RoletaBase()
        self.historico = deque(maxlen=100)
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        
    def atualizar(self, numero):
        self.historico.append(numero)
        
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
    
    def analisar(self, lucky_numbers_recentes=None):
        """
        Análise otimizada baseada nos padrões reais do histórico
        """
        if len(self.historico) < 5:
            return None
        
        hist_list = list(self.historico)
        ultimos_15 = hist_list[-15:] if len(hist_list) >= 15 else hist_list
        ultimos_5 = hist_list[-5:] if len(hist_list) >= 5 else hist_list
        ultimos_3 = hist_list[-3:] if len(hist_list) >= 3 else hist_list
        ultimo = hist_list[-1]
        penultimo = hist_list[-2] if len(hist_list) >= 2 else None
        
        # 🔥 REPETIÇÃO - PADRÃO MAIS FORTE DO HISTÓRICO
        repeticao_direta = (ultimo == penultimo) if penultimo else False
        repeticoes_5 = [n for n in ultimos_5 if ultimos_5.count(n) >= 2]
        repeticoes_15 = [n for n in ultimos_15 if ultimos_15.count(n) >= 3]
        
        # Sequência ativa (3x+)
        sequencia_ativa = len(hist_list) >= 3 and hist_list[-1] == hist_list[-2] == hist_list[-3]
        
        # 🔥 FREQUÊNCIA RECENTE
        freq_5 = Counter(ultimos_5)
        freq_15 = Counter(ultimos_15)
        quentes_5 = [n for n, _ in freq_5.most_common(4)]
        quentes_15 = [n for n, _ in freq_15.most_common(6)]
        
        # Cálculo de força
        forca = 35
        
        # Repetição direta = MÁXIMA prioridade
        if repeticao_direta:
            forca += 30
        if sequencia_ativa:
            forca += 25
        if len(repeticoes_5) >= 2:
            forca += 20
        elif len(repeticoes_5) >= 1:
            forca += 10
        
        # Frequência do último número
        freq_ultimo_5 = ultimos_5.count(ultimo)
        forca += freq_ultimo_5 * 8
        
        # Lucky numbers recentes aumentam força
        if lucky_numbers_recentes and ultimo in lucky_numbers_recentes:
            forca += 10
        
        # Performance recente
        taxa_rec = self.get_taxa_recente(3)
        if taxa_rec >= 0.5:
            forca += 10
        elif taxa_rec <= 0.2:
            forca -= 10
        
        forca = min(100, max(25, int(forca)))
        
        return {
            "ultimo": ultimo,
            "penultimo": penultimo,
            "repeticao_direta": repeticao_direta,
            "sequencia_ativa": sequencia_ativa,
            "repeticoes_5": list(set(repeticoes_5)),
            "repeticoes_15": list(set(repeticoes_15)),
            "quentes_5": quentes_5,
            "quentes_15": quentes_15,
            "forca_sinal": forca,
            "ultimos_3": ultimos_3,
            "freq_ultimo_5": freq_ultimo_5
        }
    
    def prever(self, usar_lucky=True, lucky_numbers=None, max_numeros=8):
        """
        Previsão otimizada: POUCOS números, ALTA precisão
        Baseado nos padrões reais do histórico
        """
        if len(self.historico) < 5:
            return None
        
        dados = self.analisar(lucky_numbers)
        if not dados:
            return None
        
        ultimo = dados["ultimo"]
        
        # 🎯 BASE OTIMIZADA (máximo 8 números)
        base = set()
        
        # 1. Último número (SEMPRE)
        base.add(ultimo)
        
        # 2. Números que repetiram (PRIORIDADE MÁXIMA)
        for n in dados["repeticoes_5"]:
            base.add(n)
        
        # 3. Se sequência ativa, reforça
        if dados["sequencia_ativa"]:
            base.add(ultimo)
        
        # 4. Quentes dos últimos 5
        for n in dados["quentes_5"][:3]:
            base.add(n)
        
        # 5. Quentes dos últimos 15
        for n in dados["quentes_15"][:2]:
            base.add(n)
        
        # 6. Últimos 3 números (contexto imediato)
        for n in dados["ultimos_3"]:
            base.add(n)
        
        # 7. Lucky numbers (ALTÍSSIMA prioridade)
        if usar_lucky and lucky_numbers:
            for n in lucky_numbers[:3]:
                base.add(n)
        
        # 8. Vizinhos próximos (apenas 1 de cada lado)
        vizinhos = self.roleta.get_vizinhos_proximos(ultimo)
        for v in vizinhos[:1]:  # Apenas 1 vizinho
            base.add(v)
        
        # Converte e limita ao máximo
        base_list = list(base)
        if len(base_list) > max_numeros:
            # Prioriza: último, repetidos, quentes, lucky
            prioridade = [ultimo] + dados["repeticoes_5"] + dados["quentes_5"]
            if lucky_numbers:
                prioridade += lucky_numbers[:3]
            base_list = [n for n in base_list if n in prioridade][:max_numeros]
        
        # Se ainda tem pouco, completa com quentes
        if len(base_list) < 4:
            for n in dados["quentes_15"]:
                if n not in base_list:
                    base_list.append(n)
                    if len(base_list) >= 5:
                        break
        
        # Monta gatilho descritivo
        partes = []
        if dados["repeticao_direta"]:
            partes.append(f"REPETIU {ultimo}")
        if dados["sequencia_ativa"]:
            partes.append(f"SEQUÊNCIA {ultimo}")
        if dados["repeticoes_5"]:
            partes.append(f"rep={dados['repeticoes_5']}")
        
        return {
            'nome': 'IA Otimizada',
            'numeros_apostar': sorted(base_list[:max_numeros]),
            'gatilho': ", ".join(partes) if partes else f"u={ultimo}",
            'forca_sinal': dados['forca_sinal'],
            'confianca': 'Alta' if dados['forca_sinal'] >= 50 else 'Média'
        }
    
    def get_analise_completa(self):
        if len(self.historico) < 5:
            return "📊 Aguardando dados..."
        
        dados = self.analisar()
        if not dados:
            return "📊 Analisando..."
        
        hist_list = list(self.historico)
        taxa = self.get_taxa_acerto()
        total = self.get_total_tentativas()
        
        analise = "🎯 ANÁLISE OTIMIZADA\n" + "="*35 + "\n\n"
        analise += f"🎲 Último: {dados['ultimo']}\n"
        analise += f"📊 10 últimos: {hist_list[-10:]}\n\n"
        
        if dados['repeticao_direta']:
            analise += f"🔥 REPETIU! {dados['ultimo']}→{dados['ultimo']}\n"
        if dados['sequencia_ativa']:
            analise += f"💥 SEQUÊNCIA! {dados['ultimo']} (3x+)\n"
        
        analise += f"🔁 Repetições (5): {dados['repeticoes_5']}\n"
        analise += f"🔁 Repetições (15): {dados['repeticoes_15']}\n"
        analise += f"🔥 Quentes (5): {dados['quentes_5']}\n"
        analise += f"⚡ Força: {dados['forca_sinal']}%\n"
        
        if total > 0:
            analise += f"\n📈 Perf: {taxa:.0%} ({self.performance['acertos']}/{total})\n"
        
        return analise
    
    def zerar(self):
        self.historico.clear()
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}


# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaIA:
    def __init__(self):
        self.ia = RoletaIA()
        self.historico_numeros = deque(maxlen=200)
        self.historico_multiplicadores = deque(maxlen=200)
        self.historico_lucky_numbers = []  # Acumula lucky numbers recentes
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
        
        # Atualiza IA
        self.ia.atualizar(numero_real)
        self.historico_numeros.append(numero_real)
        self.historico_multiplicadores.append(mult if mult else 0)
        
        # Acumula lucky numbers recentes
        if lucky:
            self.historico_lucky_numbers.extend(lucky)
            # Mantém apenas os últimos 30
            if len(self.historico_lucky_numbers) > 30:
                self.historico_lucky_numbers = self.historico_lucky_numbers[-30:]
        
        self.rodadas_sem_entrada += 1
        
        # Verifica resultado anterior
        if self.previsao_ativa:
            acerto = numero_real in self.previsao_ativa.get('numeros_apostar', [])
            self.ia.atualizar_resultado(acerto)
            
            if acerto:
                self.acertos += 1
            else:
                self.erros += 1
            
            enviar_resultado_auto(numero_real, acerto, mult)
            
            self.historico_desempenho.append({
                'numero': numero_real,
                'acerto': acerto,
                'multiplicador': mult,
                'forca': self.previsao_ativa.get('forca_sinal', 0)
            })
            
            self.previsao_ativa = None
            self.ultima_entrada_rodada = len(self.historico_numeros)
            self.rodadas_sem_entrada = 0
        
        if self.estrategia_ativa_manual:
            return
        
        # Intervalo mínimo
        intervalo = st.session_state.get('intervalo_minimo_entradas', 0)
        if len(self.historico_numeros) - self.ultima_entrada_rodada < intervalo:
            return
        
        # Gera previsão
        if len(self.historico_numeros) >= 5:
            usar_lucky = st.session_state.get('usar_lucky_numbers', True)
            max_numeros = st.session_state.get('max_numeros_entrada', 8)
            
            # Prepara lucky numbers mais frequentes
            lucky_freq = Counter(self.historico_lucky_numbers)
            top_lucky = [n for n, _ in lucky_freq.most_common(5)] if self.historico_lucky_numbers else None
            
            nova = self.ia.prever(usar_lucky, top_lucky, max_numeros)
            
            if nova:
                forca_minima = st.session_state.get('forca_minima_sinal', 35)
                if nova['forca_sinal'] >= forca_minima:
                    self.previsao_ativa = nova
                    enviar_previsao_auto(nova)
    
    def zerar_estatisticas(self):
        self.acertos = 0
        self.erros = 0
        self.historico_desempenho = []
        self.historico_numeros.clear()
        self.historico_multiplicadores.clear()
        self.historico_lucky_numbers.clear()
        self.rodadas_sem_entrada = 0
        self.ultima_entrada_rodada = -10
        self.ia.zerar()
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

def exportar_historico_json(historico):
    return json.dumps(historico, indent=2, ensure_ascii=False)


# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎯 IA Roleta — Otimizada", layout="centered")
st.title("🎯 IA Roleta — Motor Otimizado")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaIA()

# Valores padrão OTIMIZADOS
defaults = {
    'modo_sniper': True, 'modo_seguro': False, 'forca_minima_sinal': 35,
    'intervalo_minimo_entradas': 0, 'max_numeros_entrada': 8,
    'priorizar_repeticao': True, 'usar_lucky_numbers': True,
    'modo_agressivo': True
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

with st.sidebar.expander("🎯 Modo", expanded=True):
    st.session_state.modo_sniper = st.checkbox("🔥 Modo Agressivo (3-8 números)", value=st.session_state.modo_sniper)
    st.session_state.usar_lucky_numbers = st.checkbox("🍀 Usar Lucky Numbers", value=st.session_state.usar_lucky_numbers,
        help="Inclui lucky numbers recentes na previsão")
    st.session_state.max_numeros_entrada = st.slider("📊 Máx números", 3, 12, st.session_state.max_numeros_entrada)

with st.sidebar.expander("⚡ Força", expanded=True):
    st.session_state.forca_minima_sinal = st.slider("Força mínima", 25, 60, st.session_state.forca_minima_sinal, 5)
    st.session_state.intervalo_minimo_entradas = st.slider("⏱️ Intervalo", 0, 3, st.session_state.intervalo_minimo_entradas)

with st.sidebar.expander("🧠 Análise", expanded=True):
    st.text(st.session_state.sistema.ia.get_analise_completa())

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

# Modo
modo_auto = st.sidebar.checkbox("🔄 Automático", value=not st.session_state.sistema.estrategia_ativa_manual)
if st.sidebar.button("Atualizar"):
    st.session_state.sistema.estrategia_ativa_manual = not modo_auto
    st.rerun()

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

# Previsão
st.subheader("🎯 Previsão Ativa")
sis = st.session_state.sistema

if sis.estrategia_ativa_manual:
    st.warning("⚠️ MANUAL")
elif sis.previsao_ativa:
    p = sis.previsao_ativa
    f = p.get('forca_sinal', 0)
    barras = "█"*(f//10) + "░"*(10-f//10)
    
    st.success(f"🔥 **ENTRADA** - F:{f}% {barras}")
    st.caption(f"📋 {p['gatilho']}")
    st.write(f"**🔢 {len(p['numeros_apostar'])} números:**")
    
    nums = sorted(p['numeros_apostar'])
    cols = st.columns(4)
    for i, num in enumerate(nums):
        cols[i%4].write(f"**{num}**")
else:
    st.info(f"🎲 Aguardando... ({status['rodadas_sem_entrada']} rodadas)")

# Performance
st.subheader("📈 Performance IA")
taxa_ia = sis.ia.get_taxa_acerto()
total_ia = sis.ia.get_total_tentativas()

if total_ia > 0:
    emoji = "🟢" if taxa_ia >= 0.30 else "🟡" if taxa_ia >= 0.20 else "🔴"
    st.write(f"{emoji} **IA**: {taxa_ia:.0%} ({sis.ia.performance['acertos']}/{total_ia})")
else:
    st.write("⚪ Coletando dados...")

# Histórico
if sis.historico_desempenho:
    st.write("**🔍 Últimas:**")
    for r in sis.historico_desempenho[-5:]:
        e = "🎉" if r['acerto'] else "❌"
        m = f" ⚡{r['multiplicador']}x" if r.get('multiplicador') and r['acerto'] else ""
        st.write(f"{e} IA ({r.get('forca',0)}%): {r['numero']}{m}")

# ===== DOWNLOAD =====
st.subheader("📥 Download do Histórico")
total_registros = len(st.session_state.historico)
st.metric("📊 Registros", total_registros)

col_d1, col_d2 = st.columns(2)
with col_d1:
    if st.button("📥 Baixar JSON", use_container_width=True):
        json_data = exportar_historico_json(st.session_state.historico)
        st.download_button(
            label="⬇️ Clique para baixar",
            data=json_data,
            file_name=f"historico_roleta_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

with col_d2:
    if st.button("📥 Baixar CSV", use_container_width=True):
        linhas = ["numero,timestamp,multiplicador"]
        for item in st.session_state.historico:
            if isinstance(item, dict):
                n = item.get('number', '')
                ts = item.get('timestamp', '')
                mult = item.get('luckyMultipliers', {}).get(n, '')
                linhas.append(f"{n},{ts},{mult}")
            else:
                linhas.append(f"{item},,")
        csv_data = "\n".join(linhas)
        st.download_button(
            label="⬇️ Clique para baixar",
            data=csv_data,
            file_name=f"historico_roleta_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

salvar_sessao()
