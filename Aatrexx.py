import streamlit as st
import json
import os
import requests
import logging
from collections import Counter, deque, defaultdict
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
        if 'sistema' not in st.session_state or st.session_state.sistema is None:
            return False
        
        performance_data = {
            'acertos': st.session_state.sistema.bot.performance['acertos'],
            'erros': st.session_state.sistema.bot.performance['erros'],
            'historico': st.session_state.sistema.bot.performance['historico']
        }
        with open(PERFORMANCE_PATH, 'w') as f:
            json.dump(performance_data, f)
        
        session_data = {
            'historico': st.session_state.get('historico', []),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'sistema_acertos': st.session_state.sistema.acertos,
            'sistema_erros': st.session_state.sistema.erros,
            'sistema_historico_desempenho': st.session_state.sistema.historico_desempenho,
            'historico_numeros': list(st.session_state.sistema.historico_numeros),
            'historico_lucky': list(st.session_state.sistema.historico_lucky),
            'estrategia_ativa_manual': st.session_state.sistema.estrategia_ativa_manual,
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'modo_agressivo': st.session_state.get('modo_agressivo', True),
            'top_n_apostas': st.session_state.get('top_n_apostas', 5),
            'intervalo_minimo_entradas': st.session_state.get('intervalo_minimo_entradas', 0)
        }
        
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f)
        
        return True
    except Exception as e:
        logging.error(f"❌ Erro ao salvar: {e}")
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
        estrategia = previsao.get('estrategia_principal', '')
        confianca = previsao.get('confianca', '')
        
        emoji = "🔥" if forca >= 60 else "🎯" if forca >= 40 else "📊"
        
        msg = f"{emoji} **ENTRADA** - Força: {forca}%\n"
        msg += f"📋 {previsao['gatilho']}\n"
        if estrategia:
            msg += f"🎯 {estrategia}\n"
        msg += f"🔢 {len(numeros)} números: {numeros}"
        
        st.toast(f"🎯 Entrada - {forca}%", icon=emoji)
        st.success(f"🔔 {msg}")
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"🔔 ENTRADA [{forca}%]\n{msg}")
        
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
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"📢 {msg}")
        
        salvar_sessao()
    except:
        pass

def enviar_telegram(mensagem):
    try:
        token = st.session_state.get('telegram_token', '')
        chat_id = st.session_state.get('telegram_chat_id', '')
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
        self.vermelhos = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        self.pretos = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
    
    def get_vizinhos(self, numero, raio=2):
        if numero not in self.race:
            return []
        idx = self.race.index(numero)
        return [self.race[(idx + i) % 37] for i in range(-raio, raio + 1)]
    
    def get_setor(self, numero):
        """Retorna o setor: 0-12, 13-24, 25-36"""
        if numero == 0:
            return 0
        return (numero - 1) // 12 + 1
    
    def get_coluna(self, numero):
        """Retorna a coluna: 1, 2, 3"""
        if numero == 0:
            return 0
        return (numero - 1) % 3 + 1


# =============================
# BOT V4 - ANÁLISE A CADA GIRO
# =============================
class RoletaBotV4:
    """
    Bot V4: Analisa a cada giro e gera entrada quando há sinais reais.
    Foco em: Repetição, Lucky Numbers, Vizinhos, Setores Quentes.
    """
    
    def __init__(self):
        self.roleta = RoletaBase()
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
    
    def analisar_e_prever(self, top_n=5):
        """
        Análise a cada giro - SEMPRE gera uma sugestão
        A qualidade da sugestão varia conforme os sinais detectados
        """
        if len(self.historico) < 5:
            return None
        
        hist = self.historico
        ultimo = hist[-1]
        penultimo = hist[-2] if len(hist) >= 2 else None
        ultimos_5 = hist[-5:] if len(hist) >= 5 else hist
        ultimos_10 = hist[-10:] if len(hist) >= 10 else hist
        ultimos_20 = hist[-20:] if len(hist) >= 20 else hist
        
        # ===== DETECÇÃO DE PADRÕES =====
        
        # 1. Repetição direta
        repetiu = (ultimo == penultimo) if penultimo else False
        
        # 2. Repetições nas últimas 5 e 10
        freq_5 = Counter(ultimos_5)
        freq_10 = Counter(ultimos_10)
        freq_20 = Counter(ultimos_20)
        
        repeticoes_5 = [n for n in ultimos_5 if ultimos_5.count(n) >= 2]
        repeticoes_10 = [n for n in ultimos_10 if ultimos_10.count(n) >= 3]
        
        # 3. Quentes (frequência)
        quentes_5 = [n for n, _ in freq_5.most_common(3)]
        quentes_10 = [n for n, _ in freq_10.most_common(5)]
        quentes_20 = [n for n, _ in freq_20.most_common(6)]
        
        # 4. Lucky Numbers
        lucky_recentes = []
        for sub in self.lucky[-5:]:
            lucky_recentes.extend(sub)
        lucky_count = Counter(lucky_recentes)
        top_lucky = [n for n, _ in lucky_count.most_common(5)]
        
        # 5. Lucky que acertaram (cross)
        lucky_acertos = []
        for i in range(len(hist) - 1):
            if i < len(self.lucky) and hist[i+1] in self.lucky[i]:
                lucky_acertos.append(hist[i+1])
        
        # 6. Setor dominante
        setores_10 = Counter([self.roleta.get_setor(n) for n in ultimos_10 if n != 0])
        setor_dominante = setores_10.most_common(1)[0][0] if setores_10 else None
        
        # 7. Coluna dominante
        colunas_10 = Counter([self.roleta.get_coluna(n) for n in ultimos_10 if n != 0])
        coluna_dominante = colunas_10.most_common(1)[0][0] if colunas_10 else None
        
        # 8. Vizinhos do último
        vizinhos = self.roleta.get_vizinhos(ultimo, raio=2)
        
        # 9. Cor dominante
        vermelhos_10 = sum(1 for n in ultimos_10 if n in self.roleta.vermelhos)
        pretos_10 = sum(1 for n in ultimos_10 if n in self.roleta.pretos)
        cor_dominante = 'Vermelho' if vermelhos_10 > pretos_10 else 'Preto'
        
        # ===== CONSTRUÇÃO DA BASE =====
        base = set()
        estrategias = []
        forca = 20  # Base
        
        # 🔥 REPETIÇÃO (maior peso)
        if repetiu:
            base.add(ultimo)
            forca += 35
            estrategias.append(f"Repetiu {ultimo}")
        
        for n in repeticoes_5[:2]:
            base.add(n)
            forca += 10
        
        # 🔥 LUCKY NUMBERS
        for n in top_lucky[:3]:
            base.add(n)
        if top_lucky:
            forca += 15
            estrategias.append("Lucky Numbers")
        
        # Lucky que acertaram recentemente
        if lucky_acertos:
            for n in lucky_acertos[-3:]:
                base.add(n)
            forca += 10
        
        # 🔥 QUENTES
        for n in quentes_5[:2]:
            base.add(n)
        for n in quentes_10[:3]:
            base.add(n)
        estrategias.append("Quentes")
        
        # 🔥 VIZINHOS
        for n in vizinhos[:3]:
            base.add(n)
        estrategias.append("Vizinhos")
        
        # Último número sempre
        base.add(ultimo)
        
        # Filtro por setor
        if setor_dominante:
            inicio = (setor_dominante - 1) * 12 + 1
            fim = setor_dominante * 12
            numeros_setor = set(range(inicio, fim + 1))
            base_setor = base.intersection(numeros_setor)
            if len(base_setor) >= 3:
                base = base_setor
                forca += 15
                estrategias.append(f"Setor {setor_dominante}")
        
        # Filtro por cor
        if cor_dominante:
            if cor_dominante == 'Vermelho':
                base_cor = {n for n in base if n in self.roleta.vermelhos or n == 0}
            else:
                base_cor = {n for n in base if n in self.roleta.pretos or n == 0}
            if len(base_cor) >= 3:
                base = base_cor
                forca += 10
                estrategias.append(cor_dominante)
        
        # Prioriza: repetidos > lucky > quentes > vizinhos
        prioridade = []
        for n in repeticoes_5:
            if n in base and n not in prioridade:
                prioridade.append(n)
        for n in top_lucky:
            if n in base and n not in prioridade:
                prioridade.append(n)
        for n in quentes_5:
            if n in base and n not in prioridade:
                prioridade.append(n)
        for n in vizinhos:
            if n in base and n not in prioridade:
                prioridade.append(n)
        for n in base:
            if n not in prioridade:
                prioridade.append(n)
        
        # Limita ao top_n
        base_list = prioridade[:top_n]
        
        # Se muito poucos, completa
        if len(base_list) < 3:
            for n in quentes_10:
                if n not in base_list:
                    base_list.append(n)
                    if len(base_list) >= 3:
                        break
        
        # Ajuste de força pela performance recente
        if len(self.performance['historico']) >= 5:
            taxa_recente = sum(self.performance['historico'][-5:]) / 5
            if taxa_recente >= 0.4:
                forca += 10
            elif taxa_recente <= 0.15:
                forca -= 10
        
        forca = min(100, max(15, forca))
        
        # Confiança
        if forca >= 55:
            confianca = "Alta"
        elif forca >= 35:
            confianca = "Média"
        else:
            confianca = "Baixa"
        
        # Gatilho descritivo
        gatilho = f"u={ultimo}"
        if repetiu:
            gatilho = f"REPETIU {ultimo}!"
        elif repeticoes_5:
            gatilho += f" rep={repeticoes_5[:2]}"
        if top_lucky:
            gatilho += f" lucky={top_lucky[:2]}"
        
        return {
            'nome': 'Bot V4',
            'numeros_apostar': sorted(base_list),
            'gatilho': gatilho,
            'forca_real': forca,
            'confianca': confianca,
            'estrategia_principal': ' + '.join(estrategias[:3]) if estrategias else 'Análise geral'
        }
    
    def get_analise_completa(self):
        if len(self.historico) < 5:
            return "📊 Aguardando dados (mínimo 5)..."
        
        hist = self.historico
        ultimo = hist[-1]
        ultimos_10 = hist[-10:] if len(hist) >= 10 else hist
        
        freq_10 = Counter(ultimos_10)
        quentes = [n for n, _ in freq_10.most_common(5)]
        
        # Lucky recentes
        lucky_flat = []
        for sub in self.lucky[-5:]:
            lucky_flat.extend(sub)
        top_lucky = [n for n, _ in Counter(lucky_flat).most_common(5)]
        
        # Repetições
        repeticoes = [n for n in hist[-5:] if hist[-5:].count(n) >= 2] if len(hist) >= 5 else []
        
        # Setor
        setores = Counter([self.roleta.get_setor(n) for n in ultimos_10 if n != 0])
        setor_dom = setores.most_common(1)[0] if setores else (0, 0)
        
        taxa = self.get_taxa_acerto()
        total = self.get_total_tentativas()
        
        txt = "🎯 ANÁLISE BOT V4\n" + "="*35 + "\n\n"
        txt += f"🎲 Último: {ultimo}\n"
        txt += f"📊 10 últimos: {hist[-10:]}\n\n"
        
        if hist[-1] == hist[-2] if len(hist) >= 2 else False:
            txt += f"🔥 REPETIU! {ultimo}\n"
        
        txt += f"🔁 Repetições (5): {list(set(repeticoes))}\n"
        txt += f"🔥 Quentes: {quentes}\n"
        txt += f"🍀 Lucky: {top_lucky}\n"
        txt += f"📊 Setor: {setor_dom[0]} ({setor_dom[1]}/10)\n"
        
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
        self.bot = RoletaBotV4()
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
                'forca': self.previsao_ativa.get('forca_real', 0)
            })
            
            self.previsao_ativa = None
            self.ultima_entrada_rodada = len(self.historico_numeros)
            self.rodadas_sem_entrada = 0
        
        if self.estrategia_ativa_manual:
            return
        
        # GERA PREVISÃO A CADA GIRO
        if len(self.historico_numeros) >= 5:
            top_n = st.session_state.get('top_n_apostas', 5)
            intervalo = st.session_state.get('intervalo_minimo_entradas', 0)
            
            # Respeita intervalo se configurado
            if len(self.historico_numeros) - self.ultima_entrada_rodada >= intervalo:
                nova = self.bot.analisar_e_prever(top_n)
                
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
st.set_page_config(page_title="🎯 Bot V4 — Análise por Giro", layout="centered")
st.title("🎯 Bot V4 — Análise a Cada Giro")

# INICIALIZAÇÃO
if "sistema" not in st.session_state or st.session_state.sistema is None:
    st.session_state.sistema = SistemaBot()

# Carrega dados persistidos
dados = carregar_dados_persistidos()
if dados:
    if not st.session_state.get('historico'):
        st.session_state.historico = dados.get('historico', [])
    
    sis = st.session_state.sistema
    sis.acertos = dados.get('sistema_acertos', 0)
    sis.erros = dados.get('sistema_erros', 0)
    sis.historico_desempenho = dados.get('sistema_historico_desempenho', [])
    sis.estrategia_ativa_manual = dados.get('estrategia_ativa_manual', False)
    
    # Reconstrói históricos
    for num in dados.get('historico_numeros', []):
        sis.historico_numeros.append(num)
    for lucky in dados.get('historico_lucky', []):
        sis.historico_lucky.append(lucky)
    
    # Reconstrói bot
    for num, lucky in zip(
        dados.get('historico_numeros', []),
        dados.get('historico_lucky', [])
    ):
        sis.bot.historico.append(num)
        sis.bot.lucky.append(lucky)
    
    # Performance
    if os.path.exists(PERFORMANCE_PATH):
        try:
            with open(PERFORMANCE_PATH, 'r') as f:
                perf = json.load(f)
                sis.bot.performance = {
                    'acertos': perf.get('acertos', 0),
                    'erros': perf.get('erros', 0),
                    'historico': perf.get('historico', [])
                }
        except:
            pass

# Valores padrão
defaults = {
    'modo_automatico': True, 'modo_agressivo': True,
    'top_n_apostas': 5, 'intervalo_minimo_entradas': 0
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

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

with st.sidebar.expander("🎯 Bot V4", expanded=True):
    st.session_state.modo_agressivo = st.checkbox("🔥 Modo Agressivo (mais entradas)", value=st.session_state.modo_agressivo)
    st.session_state.top_n_apostas = st.slider("📊 Números por aposta", 3, 7, st.session_state.top_n_apostas)
    st.session_state.intervalo_minimo_entradas = st.slider("⏱️ Intervalo entre entradas", 0, 3, st.session_state.intervalo_minimo_entradas,
        help="0 = pode entrar todo giro")
    st.info("""
    **Bot V4: Análise por Giro**
    - ✅ Sempre gera entrada
    - 🔥 Prioriza repetições
    - 🍀 Usa Lucky Numbers
    - 📊 Filtra por setor/cor
    - ⚡ Força indica qualidade
    """)

st.session_state.modo_automatico = st.sidebar.checkbox("🔄 Automático", value=st.session_state.modo_automatico)
if st.sidebar.button("Atualizar"):
    st.session_state.sistema.estrategia_ativa_manual = not st.session_state.modo_automatico
    st.rerun()

with st.sidebar.expander("🧠 Análise", expanded=True):
    st.text(st.session_state.sistema.bot.get_analise_completa())

with st.sidebar.expander("💾 Geral", expanded=False):
    if st.button("💾 Salvar", use_container_width=True):
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()
        st.success("✅ Salvo!")
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
    entrada = st.text_input("Números (0-36):")
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
    estrategia = p.get('estrategia_principal', '')
    
    if f >= 55:
        st.success(f"🔥 **FORÇA {f}%** - {c}")
    elif f >= 35:
        st.warning(f"🎯 **FORÇA {f}%** - {c}")
    else:
        st.info(f"📊 **FORÇA {f}%** - {c}")
    
    st.caption(f"📋 {p['gatilho']}")
    st.caption(f"🎯 {estrategia}")
    
    st.write(f"**🔢 {len(p['numeros_apostar'])} números:**")
    nums = sorted(p['numeros_apostar'])
    cols = st.columns(len(nums))
    for i, num in enumerate(nums):
        cols[i].write(f"**{num}**")
else:
    st.info(f"🎲 Iniciando análise... ({status['rodadas_sem_entrada']} rodadas)")

# Performance
st.subheader("📈 Performance")
taxa_bot = sis.bot.get_taxa_acerto()
total_bot = sis.bot.get_total_tentativas()
if total_bot > 0:
    emoji = "🟢" if taxa_bot >= 0.30 else "🟡" if taxa_bot >= 0.20 else "🔴"
    st.write(f"{emoji} **Bot V4**: {taxa_bot:.0%} ({sis.bot.performance['acertos']}/{total_bot})")

# Histórico
if sis.historico_desempenho:
    st.write("**🔍 Últimas:**")
    for r in sis.historico_desempenho[-5:]:
        e = "🎉" if r['acerto'] else "❌"
        m = f" ⚡{r['multiplicador']}x" if r.get('multiplicador') and r['acerto'] else ""
        st.write(f"{e} ({r.get('forca',0)}%): {r['numero']}{m}")

# Download
st.subheader("📥 Download")
st.metric("📊 Registros", len(st.session_state.historico))
col_d1, col_d2 = st.columns(2)
with col_d1:
    if st.button("📥 JSON", use_container_width=True):
        st.download_button("⬇️ Baixar", exportar_historico(st.session_state.historico, 'json'),
                          f"historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "application/json")
with col_d2:
    if st.button("📥 CSV", use_container_width=True):
        st.download_button("⬇️ Baixar", exportar_historico(st.session_state.historico, 'csv'),
                          f"historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv")

salvar_sessao()
