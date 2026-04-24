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
# CONFIGURAÇÕES DE PERSISTÊNCIA (CORRIGIDO)
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_roleta.json"
PERFORMANCE_PATH = "performance_bot.json"

# Força inicialização da sessão
if "sistema" not in st.session_state:
    # Tenta carregar dados salvos antes de criar novo sistema
    st.session_state.sistema = None  # Será inicializado depois

def salvar_sessao():
    """Salva TODOS os dados da sessão em arquivo - PERSISTÊNCIA GARANTIDA"""
    try:
        if 'sistema' not in st.session_state or st.session_state.sistema is None:
            return False
        
        # Salva performance
        performance_data = {
            'acertos': st.session_state.sistema.bot.performance['acertos'],
            'erros': st.session_state.sistema.bot.performance['erros'],
            'historico': st.session_state.sistema.bot.performance['historico']
        }
        with open(PERFORMANCE_PATH, 'w') as f:
            json.dump(performance_data, f)
        
        # Salva estado completo
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
            'top_n_apostas': st.session_state.get('top_n_apostas', 5),
            'forca_minima_sinal': st.session_state.get('forca_minima_sinal', 40),
            'intervalo_minimo_entradas': st.session_state.get('intervalo_minimo_entradas', 0),
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'modo_conservador': st.session_state.get('modo_conservador', True),
            'janela_analise': st.session_state.get('janela_analise', 50),
            'usar_mineracao': st.session_state.get('usar_mineracao', True),
            'usar_leque_dinamico': st.session_state.get('usar_leque_dinamico', True),
            'janela_leque': st.session_state.get('janela_leque', 20)
        }
        
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f)
        
        logging.info("✅ Sessão salva com sucesso")
        return True
    except Exception as e:
        logging.error(f"❌ Erro ao salvar sessão: {e}")
        return False

def carregar_dados_persistidos():
    """Carrega dados salvos ou retorna None se não existirem"""
    try:
        if os.path.exists(SESSION_DATA_PATH):
            with open(SESSION_DATA_PATH, 'rb') as f:
                session_data = pickle.load(f)
            logging.info("✅ Dados persistidos carregados")
            return session_data
    except Exception as e:
        logging.error(f"❌ Erro ao carregar dados: {e}")
    return None

def inicializar_sistema():
    """Inicializa o sistema com dados persistidos ou do zero"""
    from collections import deque
    
    # Tenta carregar dados salvos
    dados = carregar_dados_persistidos()
    
    # Cria novo sistema
    from types import SimpleNamespace
    sis = SimpleNamespace()
    sis.bot = None  # Será inicializado pelo SistemaBot
    sis.historico_numeros = deque(maxlen=200)
    sis.historico_lucky = deque(maxlen=100)
    sis.previsao_ativa = None
    sis.historico_desempenho = []
    sis.acertos = 0
    sis.erros = 0
    sis.rodadas_sem_entrada = 0
    sis.ultima_entrada_rodada = -10
    sis.estrategia_ativa_manual = False
    
    # Recupera dados persistidos
    if dados:
        st.session_state.historico = dados.get('historico', [])
        st.session_state.telegram_token = dados.get('telegram_token', '')
        st.session_state.telegram_chat_id = dados.get('telegram_chat_id', '')
        
        st.session_state.top_n_apostas = dados.get('top_n_apostas', 5)
        st.session_state.forca_minima_sinal = dados.get('forca_minima_sinal', 40)
        st.session_state.intervalo_minimo_entradas = dados.get('intervalo_minimo_entradas', 0)
        st.session_state.modo_automatico = dados.get('modo_automatico', True)
        st.session_state.modo_conservador = dados.get('modo_conservador', True)
        st.session_state.janela_analise = dados.get('janela_analise', 50)
        st.session_state.usar_mineracao = dados.get('usar_mineracao', True)
        st.session_state.usar_leque_dinamico = dados.get('usar_leque_dinamico', True)
        st.session_state.janela_leque = dados.get('janela_leque', 20)
        
        sis.acertos = dados.get('sistema_acertos', 0)
        sis.erros = dados.get('sistema_erros', 0)
        sis.historico_desempenho = dados.get('sistema_historico_desempenho', [])
        sis.historico_numeros = deque(dados.get('historico_numeros', []), maxlen=200)
        sis.historico_lucky = deque(dados.get('historico_lucky', []), maxlen=100)
        sis.estrategia_ativa_manual = dados.get('estrategia_ativa_manual', False)
    
    return sis

def limpar_sessao():
    """Limpa todos os dados da sessão"""
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
        gatilho = previsao.get('gatilho', '')
        leque_info = previsao.get('leque_dinamico', {})
        
        emoji = "🟢" if confianca == "Alta" else "🟡" if confianca == "Média" else "🔴"
        
        msg = f"{emoji} **ENTRADA** - Força: {forca}%\n"
        msg += f"📋 {gatilho}\n"
        if estrategias:
            msg += f"🎯 Estratégias: {', '.join(estrategias)}\n"
        if leque_info.get('status'):
            msg += f"🪭 Leque: {leque_info['status']} ({leque_info.get('leque', '?')} vizinhos)\n"
        msg += f"🔢 {len(numeros)} números: {numeros}"
        
        st.toast(f"🎯 Entrada - {confianca}", icon=emoji)
        st.success(f"🔔 {msg}")
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
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
# LEQUE DINÂMICO (NOVA ESTRATÉGIA)
# =============================
class RoletaLequeDinamico:
    """Estratégia de vizinhos com leque ajustável conforme calor da região"""
    
    def __init__(self):
        self.roda = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
    
    def obter_vizinhos(self, numero_alvo, tamanho_leque):
        """Busca os vizinhos físicos do número na roda"""
        if numero_alvo not in self.roda:
            return []
        
        idx = self.roda.index(numero_alvo)
        total_numeros = len(self.roda)
        vizinhos = []
        
        for i in range(-tamanho_leque, tamanho_leque + 1):
            indice_vizinho = (idx + i) % total_numeros
            vizinhos.append(self.roda[indice_vizinho])
        
        return vizinhos
    
    def analisar(self, historico_numeros, janela_tempo=20):
        """Ajusta o tamanho da aposta com base no calor da região"""
        if len(historico_numeros) < 10:
            return None
        
        recorte_recente = historico_numeros[-janela_tempo:]
        ultimo_sorteado = recorte_recente[-1]
        
        # Mede o "calor" da macro-região (5 vizinhos pra cada lado)
        macro_regiao = self.obter_vizinhos(ultimo_sorteado, 5)
        acertos_na_regiao = sum(1 for num in recorte_recente if num in macro_regiao)
        
        # Lógica do Leque Dinâmico
        if acertos_na_regiao >= 6:
            leque = 4
            status = "🔥 SETOR MUITO QUENTE"
            forca = 70
        elif acertos_na_regiao >= 3:
            leque = 2
            status = "🟡 SETOR MORNO"
            forca = 50
        else:
            leque = 1
            status = "🧊 SETOR FRIO"
            forca = 30
        
        alvos_apostas = self.obter_vizinhos(ultimo_sorteado, leque)
        
        return {
            'alvos': alvos_apostas,
            'leque': leque,
            'status': status,
            'forca': forca,
            'acertos_regiao': acertos_na_regiao,
            'ultimo': ultimo_sorteado,
            'vizinhos_leque': leque
        }


# =============================
# MINERADOR DE PADRÕES OCULTOS
# =============================
class MineradorPadroesOcultos:
    def __init__(self):
        self.transicoes = defaultdict(list)
        self.ngramas_3 = Counter()
        
    def atualizar(self, historico_numeros):
        self.transicoes.clear()
        self.ngramas_3.clear()
        
        if len(historico_numeros) < 2:
            return
        
        for i in range(len(historico_numeros) - 1):
            self.transicoes[historico_numeros[i]].append(historico_numeros[i + 1])
        
        for i in range(len(historico_numeros) - 2):
            bloco = tuple(historico_numeros[i:i+3])
            self.ngramas_3[bloco] += 1
    
    def markov_primeira_ordem(self, ultimo_numero, top_n=3):
        se_ocorreu = self.transicoes.get(ultimo_numero, [])
        if not se_ocorreu:
            return []
        return Counter(se_ocorreu).most_common(top_n)
    
    def padrao_lucky_cross(self, historico_numeros, historico_lucky):
        if len(historico_numeros) < 2 or len(historico_lucky) < 2:
            return 0, 0, 0
        
        acertos = 0
        total = min(len(historico_numeros) - 1, len(historico_lucky) - 1)
        
        for i in range(total):
            lucky_anteriores = historico_lucky[i] if i < len(historico_lucky) else []
            numero_seguinte = historico_numeros[i+1] if i+1 < len(historico_numeros) else None
            
            if numero_seguinte and lucky_anteriores and numero_seguinte in lucky_anteriores:
                acertos += 1
        
        taxa = (acertos / total * 100) if total > 0 else 0
        return acertos, total, taxa
    
    def analisar_tudo(self, historico_numeros, historico_lucky):
        if len(historico_numeros) < 10:
            return None
        
        self.atualizar(historico_numeros)
        
        ultimo = historico_numeros[-1]
        
        resultado = {
            'markov': [],
            'lucky_cross': {'acertos': 0, 'total': 0, 'taxa': 0},
            'forca_mineracao': 0,
            'numeros_minerados': set()
        }
        
        resultado['markov'] = self.markov_primeira_ordem(ultimo, 3)
        if resultado['markov']:
            for num, _ in resultado['markov']:
                resultado['numeros_minerados'].add(num)
        
        acertos, total, taxa = self.padrao_lucky_cross(historico_numeros, historico_lucky)
        resultado['lucky_cross'] = {'acertos': acertos, 'total': total, 'taxa': taxa}
        
        forca = 0
        if resultado['markov'] and len(resultado['markov']) >= 2:
            forca += 30
        if taxa > 18:
            forca += 35
        
        resultado['forca_mineracao'] = min(100, forca)
        
        return resultado


# =============================
# ANALISADOR ROLETA VERSÁTIL
# =============================
class AnalisadorRoletaVersatil:
    def __init__(self, janela_analise=50):
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
        vizinhos_da_zona = self.get_vizinhos_roda(zona_quente, raio=2) if zona_quente else []
        
        forca = 0
        gatilho_principal = ""
        estrategia = []
        
        if melhor_duzia and melhor_coluna:
            hits_duzia = duzias[melhor_duzia]
            hits_coluna = colunas[melhor_coluna]
            if hits_duzia >= 7 and hits_coluna >= 6:
                forca += 60
                gatilho_principal = f"Cruzamento D{melhor_duzia} x C{melhor_coluna}"
                estrategia.append("Interseção D/C")
        
        if zona_quente and vizinhos_da_zona:
            hits_na_zona = sum(1 for n in recentes_curto if n in vizinhos_da_zona)
            if hits_na_zona >= 5:
                forca += 50
                if not gatilho_principal:
                    gatilho_principal = f"Zona da Roda: {zona_quente}"
                estrategia.append("Cluster Físico")
        
        lucky_quentes = []
        if lucky_recentes:
            lucky_quentes = [n for n, _ in Counter(lucky_recentes).most_common(3)]
            if any(l in recentes_curto for l in lucky_quentes):
                forca += 15
                estrategia.append("Raios Quentes")
        
        if forca == 0:
            return None
        
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
# BOT V3 SNIPER + LEQUE DINÂMICO + MINERADOR
# =============================
class RoletaBotV3:
    def __init__(self, janela_analise=50):
        self.analisador = AnalisadorRoletaVersatil(janela_analise)
        self.minerador = MineradorPadroesOcultos()
        self.leque = RoletaLequeDinamico()
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
    
    def sugerir_aposta(self, top_n=5, forca_minima=40, modo_conservador=True, 
                       usar_mineracao=True, usar_leque=True, janela_leque=20):
        if len(self.historico) < 15:
            return None
        
        lucky_recentes = []
        for sub in self.lucky[-15:]:
            lucky_recentes.extend(sub)
        
        # Análise versátil
        analise = self.analisador.analisar(list(self.historico), lucky_recentes)
        
        # Mineração
        mineracao = None
        if usar_mineracao:
            mineracao = self.minerador.analisar_tudo(list(self.historico), list(self.lucky))
        
        # Leque Dinâmico
        leque_resultado = None
        if usar_leque:
            leque_resultado = self.leque.analisar(list(self.historico), janela_leque)
        
        # Combina forças
        forca_versatil = analise['forca_sinal'] if analise else 0
        forca_mineracao = mineracao['forca_mineracao'] if mineracao else 0
        forca_leque = leque_resultado['forca'] if leque_resultado else 0
        
        forca_total = max(forca_versatil, forca_mineracao, forca_leque)
        if forca_versatil > 0 and forca_mineracao > 0 and forca_leque > 0:
            forca_total = int(forca_versatil * 0.4 + forca_mineracao * 0.3 + forca_leque * 0.3)
        elif forca_versatil > 0 and forca_leque > 0:
            forca_total = int(forca_versatil * 0.5 + forca_leque * 0.5)
        
        if forca_total < forca_minima:
            return None
        
        base = set()
        estrategias_ativas = []
        info_leque = {}
        
        # Estratégias Versáteis
        if analise:
            if "Interseção D/C" in analise['estrategia']:
                d = analise['melhor_duzia']
                c = analise['melhor_coluna']
                numeros_duzia = range((d-1)*12 + 1, d*12 + 1)
                numeros_coluna = range(c, 37, 3)
                intersecao = set(numeros_duzia).intersection(set(numeros_coluna))
                base.update(intersecao)
                estrategias_ativas.append("Interseção D/C")
            
            if "Cluster Físico" in analise['estrategia']:
                base.update(analise['vizinhos_zona'])
                estrategias_ativas.append("Cluster Físico")
            
            for n in analise['quentes'][:3]:
                base.add(n)
            for n in analise['lucky_quentes'][:2]:
                base.add(n)
        
        # Leque Dinâmico
        if leque_resultado:
            base.update(leque_resultado['alvos'])
            estrategias_ativas.append("Leque Dinâmico")
            info_leque = {
                'status': leque_resultado['status'],
                'leque': leque_resultado['leque'],
                'acertos_regiao': leque_resultado['acertos_regiao']
            }
        
        # Mineração
        info_mineracao = {}
        if mineracao:
            if mineracao['markov']:
                for num, _ in mineracao['markov'][:2]:
                    base.add(num)
                estrategias_ativas.append("Markov")
            
            if mineracao['lucky_cross']['taxa'] > 18:
                info_mineracao['lucky_cross'] = f"Taxa {mineracao['lucky_cross']['taxa']:.1f}%"
                estrategias_ativas.append("Lucky Cross")
            
            for n in mineracao['numeros_minerados']:
                base.add(n)
        
        prioridade = list(base)
        if analise:
            for n in analise['quentes']:
                if n not in prioridade:
                    prioridade.append(n)
        
        base_list = prioridade[:top_n]
        
        confianca = "Alta" if forca_total >= 70 else "Média"
        
        if modo_conservador and len(self.performance['historico']) >= 10:
            taxa_recente = sum(self.performance['historico'][-10:]) / 10
            if taxa_recente <= 0.10:
                return None
        
        gatilho = ""
        if leque_resultado:
            gatilho = f"Leque: {leque_resultado['status']}"
        if analise and analise['gatilho']:
            gatilho = f"{gatilho} | {analise['gatilho']}" if gatilho else analise['gatilho']
        
        return {
            'nome': 'Bot V3 Completo',
            'numeros_apostar': sorted(base_list),
            'gatilho': gatilho or "Sinais combinados",
            'forca_real': forca_total,
            'confianca': confianca,
            'estrategias_ativas': estrategias_ativas,
            'leque_dinamico': info_leque,
            'mineracao': info_mineracao
        }
    
    def get_analise_completa(self, janela_leque=20):
        if len(self.historico) < 10:
            return "📊 Aguardando dados (mínimo 10)..."
        
        lucky_recentes = []
        for sub in self.lucky[-15:]:
            lucky_recentes.extend(sub)
        
        analise = self.analisador.analisar(list(self.historico), lucky_recentes)
        mineracao = self.minerador.analisar_tudo(list(self.historico), list(self.lucky))
        leque_resultado = self.leque.analisar(list(self.historico), janela_leque)
        
        taxa = self.get_taxa_acerto()
        total = self.get_total_tentativas()
        
        txt = "🎯 BOT V3 COMPLETO\n" + "="*40 + "\n\n"
        
        # Leque Dinâmico
        if leque_resultado:
            txt += f"🪭 LEQUE DINÂMICO:\n"
            txt += f"   Status: {leque_resultado['status']}\n"
            txt += f"   Leque: {leque_resultado['leque']} vizinhos ({len(leque_resultado['alvos'])} números)\n"
            txt += f"   Acertos na região: {leque_resultado['acertos_regiao']}\n"
            txt += f"   Força: {leque_resultado['forca']}%\n\n"
        
        if analise:
            txt += f"🎲 Último: {analise['ultimo']}\n"
            txt += f"⚡ Força Versátil: {analise['forca_sinal']}%\n"
            if analise['estrategia']:
                txt += f"🎯 Estratégias: {', '.join(analise['estrategia'])}\n"
        
        if mineracao:
            txt += f"\n🤖 MINERAÇÃO:\n"
            txt += f"⚡ Força: {mineracao['forca_mineracao']}%\n"
            if mineracao['markov']:
                txt += f"🔗 Markov: {mineracao['markov']}\n"
            lc = mineracao['lucky_cross']
            txt += f"⚡ Lucky Cross: {lc['acertos']}/{lc['total']} ({lc['taxa']:.1f}%)"
            if lc['taxa'] > 18:
                txt += " ⚠️"
            txt += "\n"
        
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
        janela = st.session_state.get('janela_analise', 50) if 'janela_analise' in st.session_state else 50
        self.bot = RoletaBotV3(janela_analise=janela)
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
            usar_mineracao = st.session_state.get('usar_mineracao', True)
            usar_leque = st.session_state.get('usar_leque_dinamico', True)
            janela_leque = st.session_state.get('janela_leque', 20)
            
            nova = self.bot.sugerir_aposta(
                top_n, forca_minima, conservador, 
                usar_mineracao, usar_leque, janela_leque
            )
            
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
st.set_page_config(page_title="🎯 Bot Completo — Leque Dinâmico", layout="centered")
st.title("🎯 Bot V3 — Leque Dinâmico + Mineração")

# INICIALIZAÇÃO COM PERSISTÊNCIA
if "sistema" not in st.session_state or st.session_state.sistema is None:
    st.session_state.sistema = SistemaBot()

# Carrega dados persistidos se disponíveis
dados_persistidos = carregar_dados_persistidos()
if dados_persistidos:
    # Recupera histórico
    if not st.session_state.get('historico'):
        st.session_state.historico = dados_persistidos.get('historico', [])
    
    # Recupera configurações
    for key in ['telegram_token', 'telegram_chat_id', 'top_n_apostas', 'forca_minima_sinal',
                'intervalo_minimo_entradas', 'modo_automatico', 'modo_conservador',
                'janela_analise', 'usar_mineracao', 'usar_leque_dinamico', 'janela_leque']:
        if key not in st.session_state:
            st.session_state[key] = dados_persistidos.get(key, 
                {'top_n_apostas': 5, 'forca_minima_sinal': 40, 'intervalo_minimo_entradas': 0,
                 'modo_automatico': True, 'modo_conservador': True, 'janela_analise': 50,
                 'usar_mineracao': True, 'usar_leque_dinamico': True, 'janela_leque': 20}.get(key))
    
    # Recupera estado do sistema
    sis = st.session_state.sistema
    sis.acertos = dados_persistidos.get('sistema_acertos', 0)
    sis.erros = dados_persistidos.get('sistema_erros', 0)
    sis.historico_desempenho = dados_persistidos.get('sistema_historico_desempenho', [])
    sis.estrategia_ativa_manual = dados_persistidos.get('estrategia_ativa_manual', False)
    
    # Recupera históricos da IA
    for num in dados_persistidos.get('historico_numeros', []):
        sis.historico_numeros.append(num)
    for lucky in dados_persistidos.get('historico_lucky', []):
        sis.historico_lucky.append(lucky)
    
    # Recupera performance
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
    
    # Reconstrói histórico do bot
    for num, lucky in zip(
        dados_persistidos.get('historico_numeros', []),
        dados_persistidos.get('historico_lucky', [])
    ):
        sis.bot.atualizar(num, lucky)

# Garante valores padrão
defaults = {
    'top_n_apostas': 5, 'forca_minima_sinal': 40,
    'intervalo_minimo_entradas': 0, 'modo_automatico': True,
    'modo_conservador': True, 'janela_analise': 50,
    'usar_mineracao': True, 'usar_leque_dinamico': True,
    'janela_leque': 20
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Garante histórico
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

with st.sidebar.expander("🪭 Leque Dinâmico", expanded=True):
    st.session_state.usar_leque_dinamico = st.checkbox("🪭 Ativar Leque Dinâmico", value=st.session_state.usar_leque_dinamico)
    st.session_state.janela_leque = st.slider("Janela do Leque (giros)", 10, 50, st.session_state.janela_leque, 5,
        help="Quantos giros analisar para medir o calor da região")
    st.info("""
    **Leque Dinâmico:**
    - 🔥 Setor Quente → 4 vizinhos (9 números)
    - 🟡 Setor Morno → 2 vizinhos (5 números)
    - 🧊 Setor Frio → 1 vizinho (3 números)
    """)

with st.sidebar.expander("🤖 Mineração", expanded=True):
    st.session_state.usar_mineracao = st.checkbox("🔬 Mineração de Padrões", value=st.session_state.usar_mineracao)

with st.sidebar.expander("🎯 Sniper", expanded=True):
    st.session_state.janela_analise = st.slider("🪟 Janela longa", 20, 100, st.session_state.janela_analise, 10)
    st.session_state.modo_conservador = st.checkbox("🛡️ Conservador", value=st.session_state.modo_conservador)
    st.session_state.top_n_apostas = st.slider("📊 Números", 3, 7, st.session_state.top_n_apostas)
    st.session_state.forca_minima_sinal = st.slider("⚡ Força mínima", 30, 70, st.session_state.forca_minima_sinal, 5)
    st.session_state.intervalo_minimo_entradas = st.slider("⏱️ Intervalo", 0, 3, st.session_state.intervalo_minimo_entradas)

st.session_state.modo_automatico = st.sidebar.checkbox("🔄 Automático", value=st.session_state.modo_automatico)
if st.sidebar.button("Atualizar"):
    st.session_state.sistema.estrategia_ativa_manual = not st.session_state.modo_automatico
    st.rerun()

with st.sidebar.expander("🧠 Análise Completa", expanded=True):
    st.text(st.session_state.sistema.bot.get_analise_completa(st.session_state.janela_leque))

with st.sidebar.expander("💾 Geral", expanded=False):
    if st.button("💾 Salvar Agora", use_container_width=True):
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()
        st.success("✅ Dados salvos!")
    if st.button("🗑️ Zerar Tudo", use_container_width=True):
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
    if taxa >= 35:
        st.success(f"🎯 Taxa: {taxa:.1f}% ✅")
    elif taxa >= 25:
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
    estrategias = p.get('estrategias_ativas', [])
    leque_info = p.get('leque_dinamico', {})
    
    if f >= 70:
        st.success(f"🟢 **ALTA CONFIANÇA** ({f}%)")
    elif f >= 50:
        st.warning(f"🟡 **MÉDIA CONFIANÇA** ({f}%)")
    else:
        st.info(f"🔵 **CONFIANÇA** ({f}%)")
    
    st.caption(f"📋 {p['gatilho']}")
    if leque_info:
        st.caption(f"🪭 {leque_info.get('status', '')} - {leque_info.get('leque', '?')} vizinhos")
    if estrategias:
        st.caption(f"🎯 Estratégias: {', '.join(estrategias)}")
    
    st.write(f"**🔢 {len(p['numeros_apostar'])} números:**")
    nums = sorted(p['numeros_apostar'])
    cols = st.columns(len(nums))
    for i, num in enumerate(nums):
        cols[i].write(f"**{num}**")
else:
    st.info(f"🎲 Aguardando sinais... ({status['rodadas_sem_entrada']} rodadas)")

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

# Salva automaticamente ao final
salvar_sessao()
