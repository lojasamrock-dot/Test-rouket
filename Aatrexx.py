import streamlit as st
import json
import os
import requests
import logging
import random
from collections import Counter, deque, defaultdict
from streamlit_autorefresh import st_autorefresh
import pickle
from datetime import datetime, timezone, timedelta
import numpy as np
import plotly.graph_objects as plt

# =============================
# CONFIGURAÇÕES DE LOGGING
# =============================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('roleta_bot.log'),
        logging.StreamHandler()
    ]
)

# =============================
# FUSO HORÁRIO BRASÍLIA (BRT = UTC-3)
# =============================
BRT = timezone(timedelta(hours=-3))

def hora_brasilia():
    return datetime.now(BRT)

def formatar_hora_brasilia(dt=None):
    if dt is None:
        dt = hora_brasilia()
    return dt.strftime('%H:%M:%S')

def timestamp_brasilia():
    return hora_brasilia().isoformat()

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
        performance_data = {'acertos': sis.acertos, 'erros': sis.erros}
        with open(PERFORMANCE_PATH, 'w') as f:
            json.dump(performance_data, f)
        with open(ENTRADAS_PATH, 'w') as f:
            json.dump(sis.historico_entradas, f)
        session_data = {
            'historico': st.session_state.get('historico', []),
            'historico_numeros': list(sis.historico_numeros),
            'entrada_ativa': sis.entrada_ativa,
            'sistema_acertos': sis.acertos,
            'sistema_erros': sis.erros,
            'numero_rodada': sis.numero_rodada,
            'janela_duzia_ai': st.session_state.get('janela_duzia_ai', 30),
            'acertos_duzia': st.session_state.get('acertos_duzia', 0),
            'erros_duzia': st.session_state.get('erros_duzia', 0),
            'acertos_duzia_sec': st.session_state.get('acertos_duzia_sec', 0),
            'erros_duzia_sec': st.session_state.get('erros_duzia_sec', 0),
            'modo_agressivo': st.session_state.get('modo_agressivo', False),
            'confianca_minima': st.session_state.get('confianca_minima', 3.2),
            'agressividade': st.session_state.get('agressividade', 2),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'modo_automatico': st.session_state.get('modo_automatico', True),
        }
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f)
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar: {e}")
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
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH, ENTRADAS_PATH]:
            if os.path.exists(path):
                os.remove(path)
        st.session_state.clear()
        st.rerun()
    except Exception as e:
        logging.error(f"Erro ao limpar sessão: {e}")

def nova_sessao():
    try:
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH, ENTRADAS_PATH]:
            if os.path.exists(path):
                os.remove(path)
        if 'sistema' in st.session_state:
            st.session_state.sistema.zerar()
        st.session_state.historico = []
        st.session_state.acertos_duzia = 0
        st.session_state.erros_duzia = 0
        st.session_state.acertos_duzia_sec = 0
        st.session_state.erros_duzia_sec = 0
        logging.info("🆕 NOVA SESSÃO INICIADA")
        return True
    except Exception as e:
        logging.error(f"Erro ao criar nova sessão: {e}")
        return False

# =============================
# NOTIFICAÇÕES
# =============================
def enviar_previsao_auto(previsao):
    try:
        numeros = sorted(previsao.get('numeros_apostar', []))
        incluir_zero = previsao.get('incluir_zero', False)
        duzia1_numeros = [n for n in numeros if 1 <= n <= 12]
        duzia2_numeros = [n for n in numeros if 13 <= n <= 24]
        duzia3_numeros = [n for n in numeros if 25 <= n <= 36]
        prefixo = "⚠️🎯 " if incluir_zero else "🎯 "
        if duzia1_numeros and duzia2_numeros:
            mensagem = f"{prefixo}Entrada: D1 (1-12) | Cobertura: D2 (13-24)"
        elif duzia1_numeros and duzia3_numeros:
            mensagem = f"{prefixo}Entrada: D1 (1-12) | Cobertura: D3 (25-36)"
        elif duzia2_numeros and duzia3_numeros:
            mensagem = f"{prefixo}Entrada: D2 (13-24) | Cobertura: D3 (25-36)"
        elif duzia1_numeros:
            mensagem = f"{prefixo}Entrada: D1 (1-12)"
        elif duzia2_numeros:
            mensagem = f"{prefixo}Entrada: D2 (13-24)"
        elif duzia3_numeros:
            mensagem = f"{prefixo}Entrada: D3 (25-36)"
        else:
            mensagem = f"{prefixo}Entrada: {numeros}"
        if incluir_zero:
            mensagem += " + 🟢 ZERO"
        st.toast(mensagem)
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"🔔 {mensagem}\n🔢 " + " ".join(map(str, numeros)))
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar previsão: {e}")

def enviar_resultado_auto(numero_real, acerto, lucky=False):
    try:
        if numero_real == 0:
            mensagem = "✅ ZERO! (ACERTO!)" if acerto else "🟢 ZERO! (Não apostado)"
        else:
            duzia_real = get_duzia(numero_real)
            mensagem = f"{'✅ ACERTO' if acerto else '❌ ERRO'} - Nº {numero_real} (D{duzia_real})"
        if lucky:
            mensagem += " 🍀"
        st.toast(mensagem)
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"📢 {mensagem}")
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar resultado: {e}")

def enviar_telegram(mensagem):
    try:
        token = st.session_state.get('telegram_token', '')
        chat_id = st.session_state.get('telegram_chat_id', '')
        if not token or not chat_id:
            return
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                     json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        logging.error(f"Erro ao enviar Telegram: {e}")

# =============================
# API
# =============================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# =============================
# FUNÇÕES DE MAPEAMENTO
# =============================
def get_duzia(numero):
    if numero == 0: return 0
    elif 1 <= numero <= 12: return 1
    elif 13 <= numero <= 24: return 2
    else: return 3

def validar_numero(valor):
    try:
        num = int(valor)
        return 0 <= num <= 36
    except (ValueError, TypeError):
        return False

# =============================
# 🧠 DUZIA AI V7.0 - ANTI-ERROS + CILINDRO
# =============================
class DuziaAI:
    def __init__(self, window=30):
        self.historico = deque(maxlen=window)
        self.historico_completo = []
        self.numeros_completos = []
        self.sinais_entrada = []
        self.ultimas_previsoes = []
        self.ultimos_resultados = []
        self.performance_detectores = defaultdict(list)
        self.pesos_adaptativos = {
            'quebra_estados': 1.4, 'terceira_intrusa': 1.5, 'mudanca_abrupta': 1.3,
            'exaustao_ciclo': 1.8, 'zigzag_d1_d2': 0.5, 'bloco_d3': 0.7,
            'pos_zero_plus': 0.4, 'repeticao_imediata': 1.0, 'streak_longo': 1.0,
            'retorno_aba': 1.0, 'duas_dominantes': 1.0, 'progressao': 1.0,
            'troca_duas': 1.0, 'bloco_dominante': 1.0,
        }
        self.ciclos_dominantes = []
        self.ultimo_gatilho = None
        self.sinal_mudanca_pendente = None
        self.streak_ativo = None
        self.historico_confianca = []
        self.alerta_zero_ativo = False
        # 🆕 Histórico de erros para calibração imediata
        self.erros_consecutivos_mesma_duzia = 0
        self.ultima_duzia_errada = None
    
    def _garantir_cobertura_diferente(self, previsao):
        if previsao.get('duzia_secundaria') is None or previsao['duzia_secundaria'] == previsao['duzia']:
            outras = self._get_outras_duzias(previsao['duzia'])
            previsao['duzia_secundaria'] = outras[0] if outras else previsao['duzia']
        return previsao
    
    def adicionar(self, numero):
        d = get_duzia(numero)
        self.historico.append(d)
        self.historico_completo.append(d)
        self.numeros_completos.append(numero)
        if len(self.historico_completo) > 200:
            self.historico_completo = self.historico_completo[-200:]
        if len(self.numeros_completos) > 200:
            self.numeros_completos = self.numeros_completos[-200:]
    
    def registrar_previsao(self, duzia):
        self.ultimas_previsoes.append(duzia)
        if len(self.ultimas_previsoes) > 10:
            self.ultimas_previsoes = self.ultimas_previsoes[-10:]
    
    def registrar_resultado(self, duzia_real, acertou):
        self.ultimos_resultados.append({
            'duzia': duzia_real, 'acertou': acertou, 'timestamp': hora_brasilia()
        })
        if len(self.ultimos_resultados) > 20:
            self.ultimos_resultados = self.ultimos_resultados[-20:]
        
        # 🆕 RASTREAR ERROS CONSECUTIVOS NA MESMA DÚZIA
        if not acertou and duzia_real != 0:
            if duzia_real == self.ultima_duzia_errada:
                self.erros_consecutivos_mesma_duzia += 1
            else:
                self.erros_consecutivos_mesma_duzia = 1
                self.ultima_duzia_errada = duzia_real
        else:
            self.erros_consecutivos_mesma_duzia = 0
            self.ultima_duzia_errada = None
    
    def registrar_performance_detector(self, detector, acertou):
        self.performance_detectores[detector].append(1 if acertou else 0)
        if len(self.performance_detectores[detector]) > 20:
            self.performance_detectores[detector] = self.performance_detectores[detector][-20:]
    
    def get_peso_adaptativo(self, detector, peso_base):
        recentes = self.performance_detectores[detector][-10:]
        if not recentes:
            return peso_base
        taxa_acerto = sum(recentes) / len(recentes)
        return peso_base * (0.5 + taxa_acerto)
    
    def calibrar_confianca(self, confianca, acertou=None):
        if acertou is not None:
            self.historico_confianca.append({'confianca': confianca, 'acertou': acertou})
            if len(self.historico_confianca) > 30:
                self.historico_confianca = self.historico_confianca[-30:]
        
        # 🆕 CALIBRAÇÃO IMEDIATA: Erro com confiança > 5.0 reduz 60%
        if acertou is not None and not acertou and confianca > 5.0:
            confianca = confianca * 0.4
            logging.info(f"📉📉📉 CALIBRAÇÃO IMEDIATA: Confiança {confianca:.2f} (erro alta conf)")
            return confianca
        
        if len(self.historico_confianca) >= 3:
            ultimas_3 = self.historico_confianca[-3:]
            confiancas_altas = [h for h in ultimas_3 if h['confianca'] >= 3.5]
            if len(confiancas_altas) >= 2:
                erros_altas = sum(1 for h in confiancas_altas if not h['acertou'])
                if erros_altas >= 2:
                    confianca = confianca * 0.5
                    return confianca
        return confianca
    
    def detectar_alerta_zero(self):
        if len(self.historico) < 4:
            self.alerta_zero_ativo = False
            return False
        u = list(self.historico)[-5:]
        
        # Vizinhos do zero no cilindro
        if hasattr(self, 'numeros_completos') and len(self.numeros_completos) >= 3:
            nums_recentes = self.numeros_completos[-3:]
            if any(n in [26, 32, 15, 3, 35] for n in nums_recentes):
                self.alerta_zero_ativo = True
                return True
        
        if len(u) >= 3:
            ultimas_3 = u[-3:]
            if len(set(ultimas_3)) == 1 and ultimas_3[0] != 0:
                self.alerta_zero_ativo = True
                return True
        if len(u) >= 4:
            ultimas_4 = u[-4:]
            duzias_unicas = set([d for d in ultimas_4 if d != 0])
            if len(duzias_unicas) >= 3:
                self.alerta_zero_ativo = True
                return True
        if len(u) >= 1 and u[-1] == 0:
            self.alerta_zero_ativo = True
            return True
        if hasattr(self, 'ultima_confianca') and self.ultima_confianca > 8.0:
            self.alerta_zero_ativo = True
            return True
        self.alerta_zero_ativo = False
        return False
    
    # =============================================
    # 🆕 DETECTOR DE TROCA SÚBITA
    # =============================================
    def detectar_troca_subita(self):
        """Detecta quando o mercado muda de direção abruptamente"""
        if len(self.historico) < 4:
            return None
        u = list(self.historico)[-4:]
        
        # Se últimas 2 são diferentes das 2 anteriores
        if u[-2] != u[-1] and u[-3] != u[-1] and u[-4] != u[-1]:
            # A última dúzia é completamente nova em relação às 3 anteriores
            if u[-1] != 0:
                return u[-1], 6
        return None
    
    def balancear_previsoes(self, previsao):
        if len(self.historico) < 2:
            return previsao
        u = list(self.historico)
        score = previsao.get('score', {})
        
        if self.alerta_zero_ativo:
            previsao['incluir_zero'] = True
        
        # 🆕 ANTI-REPETIÇÃO: Se 2 erros seguidos na mesma dúzia, BLOQUEIA
        if self.erros_consecutivos_mesma_duzia >= 2 and self.ultima_duzia_errada:
            dz_bloqueada = self.ultima_duzia_errada
            if previsao['duzia'] == dz_bloqueada:
                outras = self._get_outras_duzias(dz_bloqueada)
                freq_outras = {d: u.count(d) for d in outras}
                previsao['duzia'] = max(freq_outras, key=freq_outras.get)
                logging.info(f"🚫 ANTI-REPETIÇÃO: Bloqueando D{dz_bloqueada} após 2 erros")
                return self._garantir_cobertura_diferente(previsao)
        
        # 🆕 MICRO-TENDÊNCIA: Seguir a última que saiu se houver indefinição
        if len(u) >= 3:
            ultimas_3 = u[-3:]
            if len(set(ultimas_3)) == 2 and ultimas_3[-1] != 0:
                # Se está alternando entre 2 dúzias, segue a última
                if previsao['duzia'] != ultimas_3[-1] and score.get(ultimas_3[-1], 0) > 20:
                    previsao['duzia'] = ultimas_3[-1]
                    logging.info(f"🎯 MICRO-TENDÊNCIA: Seguindo D{ultimas_3[-1]}")
                    return self._garantir_cobertura_diferente(previsao)
        
        # PING-PONG
        if len(u) >= 4:
            ultimas_4 = u[-4:]
            duzias_unicas = set([d for d in ultimas_4 if d != 0])
            if len(duzias_unicas) == 2:
                if ultimas_4[0] == ultimas_4[2] and ultimas_4[1] == ultimas_4[3] and ultimas_4[0] != 0 and ultimas_4[1] != 0:
                    previsao['duzia'] = ultimas_4[1]
                    self.streak_ativo = None
                    return self._garantir_cobertura_diferente(previsao)
        
        # SAÍDA DO STREAK
        if len(self.ultimas_previsoes) >= 2:
            ultimas_2_prev = self.ultimas_previsoes[-2:]
            if len(set(ultimas_2_prev)) == 1:
                dz_seguindo = ultimas_2_prev[0]
                if u[-1] != dz_seguindo and u[-1] != 0:
                    self.streak_ativo = None
                    previsao['duzia'] = u[-1]
                    return self._garantir_cobertura_diferente(previsao)
                if len(self.ultimos_resultados) >= 1:
                    if not self.ultimos_resultados[-1]['acertou'] and previsao.get('confianca', 3) < 2.5:
                        self.streak_ativo = None
                        freq_recente = Counter(u[-5:])
                        outras = self._get_outras_duzias(dz_seguindo)
                        freq_outras = {d: freq_recente.get(d, 0) for d in outras}
                        previsao['duzia'] = max(freq_outras, key=freq_outras.get)
                        return self._garantir_cobertura_diferente(previsao)
        
        # NÃO REPETIR APÓS ERRO
        if self.ultimos_resultados and not self.ultimos_resultados[-1]['acertou']:
            duzia_errada = self.ultimos_resultados[-1]['duzia']
            if previsao['duzia'] == duzia_errada and previsao.get('duzia_secundaria') and previsao['duzia_secundaria'] != previsao['duzia']:
                previsao['duzia'] = previsao['duzia_secundaria']
                return self._garantir_cobertura_diferente(previsao)
        
        # BALANCEAMENTO
        if len(self.ultimas_previsoes) >= 5:
            freq = Counter(self.ultimas_previsoes[-5:])
            if abs(score.get(1, 0) - score.get(2, 0)) < 5:
                if freq[1] >= 4 and score.get(2, 0) > 30:
                    previsao['duzia'] = 2
                    previsao['duzia_secundaria'] = 1
                    return self._garantir_cobertura_diferente(previsao)
        
        return self._garantir_cobertura_diferente(previsao)
    
    # ========== FUNÇÕES AUXILIARES ==========
    def frequencia_ponderada(self):
        freq = Counter()
        total = len(self.historico)
        for i, d in enumerate(self.historico):
            pos = i / max(1, total - 1)
            peso = 1 + (pos ** 1.5) * 7
            freq[d] += peso
        return freq
    
    def frequencia(self):
        return Counter(self.historico)
    
    def streak(self):
        if not self.historico:
            return 0, None
        last = self.historico[-1]
        count = 0
        for d in reversed(self.historico):
            if d == last:
                count += 1
            else:
                break
        return count, last
    
    def transicao(self):
        if len(self.historico) < 2:
            return None
        return self.historico[-2], self.historico[-1]
    
    def matriz_transicao(self):
        matriz = {1: {1: 0, 2: 0, 3: 0}, 2: {1: 0, 2: 0, 3: 0}, 3: {1: 0, 2: 0, 3: 0}}
        totais = {1: 0, 2: 0, 3: 0}
        for i in range(len(self.historico_completo) - 1):
            o = self.historico_completo[i]
            d = self.historico_completo[i + 1]
            if o != 0 and d != 0:
                peso = 1 + (i / max(1, len(self.historico_completo))) * 2
                matriz[o][d] += peso
                totais[o] += peso
        prob = {}
        for o in [1, 2, 3]:
            prob[o] = {}
            for d in [1, 2, 3]:
                prob[o][d] = (matriz[o][d] / totais[o] * 100) if totais[o] > 0 else 33.3
        return prob
    
    def _get_outras_duzias(self, duzia):
        return [d for d in [1, 2, 3] if d != duzia]
    
    def _get_terceira_duzia(self, dz1, dz2):
        for d in [1, 2, 3]:
            if d != dz1 and d != dz2:
                return d
        return None
    
    def _contar_alternancias_entre(self, u, dz_a, dz_b):
        count = 0
        for i in range(len(u)-1):
            if (u[i] == dz_a and u[i+1] == dz_b) or (u[i] == dz_b and u[i+1] == dz_a):
                count += 1
        return count
    
    def _eh_caos(self, frequencias):
        if len(frequencias) < 2:
            return True
        valores = list(frequencias.values())
        max_val = max(valores)
        return max_val <= 3 and max_val - min(valores) <= 2
    
    # =============================================
    # 🎯 GATILHOS
    # =============================================
    def detectar_exaustao_ciclo_dominante(self):
        if len(self.historico) < 10:
            return None
        u = list(self.historico)[-15:]
        freq = Counter([d for d in u if d != 0])
        if len(freq) < 2:
            return None
        ranking = freq.most_common()
        dz_dominante = ranking[0][0]
        
        if self.sinal_mudanca_pendente:
            if u[-1] == self.sinal_mudanca_pendente['dz_quebra'] and u[-1] != 0:
                resultado = {
                    'tipo': 'MUDANCA_VELOCIDADE',
                    'dz_quebra': self.sinal_mudanca_pendente['dz_quebra'],
                    'dz_exaurida': self.sinal_mudanca_pendente['dz_exaurida'],
                    'forca': 9,
                    'descricao': f"Mudança CONFIRMADA: D{self.sinal_mudanca_pendente['dz_exaurida']} → D{self.sinal_mudanca_pendente['dz_quebra']}"
                }
                self.ultimo_gatilho = 'MUDANCA_VELOCIDADE'
                self.sinal_mudanca_pendente = None
                return resultado
            else:
                self.sinal_mudanca_pendente = None
        
        ultimas_10 = u[-10:]
        freq_10 = Counter([d for d in ultimas_10 if d != 0])
        if freq_10.get(dz_dominante, 0) >= 7:
            ultimas_3 = u[-3:]
            if dz_dominante not in ultimas_3[-2:]:
                outras = self._get_outras_duzias(dz_dominante)
                freq_emergentes = {d: freq.get(d, 0) for d in outras}
                dz_emergente = max(freq_emergentes, key=freq_emergentes.get)
                self.ultimo_gatilho = 'EXAUSTAO_DOMINANCIA'
                return {'tipo': 'EXAUSTAO_DOMINANCIA', 'dz_quebra': dz_emergente, 'dz_exaurida': dz_dominante, 'forca': 9,
                       'descricao': f'D{dz_dominante} exaurida (7+/10) - Emergente D{dz_emergente}'}
            if len(ranking) >= 2:
                dz2 = ranking[1][0]
                terceira = self._get_terceira_duzia(dz_dominante, dz2)
                if terceira:
                    count_terceira_4 = sum(1 for d in ultimas_10[-4:] if d == terceira)
                    if count_terceira_4 >= 2:
                        self.ultimo_gatilho = 'INTRUSA_EMERGENTE'
                        return {'tipo': 'INTRUSA_EMERGENTE', 'dz_quebra': terceira, 'dz_exaurida': dz_dominante, 'forca': 8,
                               'descricao': f'3ª Dúzia D{terceira} emergindo (2/4)'}
        
        if len(self.ultimos_resultados) >= 2:
            ultimos_2 = self.ultimos_resultados[-2:]
            if not ultimos_2[0]['acertou'] and not ultimos_2[1]['acertou']:
                ultimas_5 = u[-5:]
                freq_5 = Counter([d for d in ultimas_5 if d != 0])
                if freq_5:
                    dz_tendencia = freq_5.most_common(1)[0]
                    if dz_tendencia[1] >= 3:
                        self.ultimo_gatilho = 'SEQUENCIA_ERROS'
                        return {'tipo': 'SEQUENCIA_ERROS', 'dz_quebra': dz_tendencia[0],
                               'dz_exaurida': self.ultimos_resultados[-1]['duzia'], 'forca': 15,
                               'descricao': f'2 erros + Tendência D{dz_tendencia[0]} ({dz_tendencia[1]}/5)'}
                dz_errada = self.ultimos_resultados[-1]['duzia'] if self.ultimos_resultados[-1]['duzia'] != 0 else dz_dominante
                outras = self._get_outras_duzias(dz_errada)
                freq_outras = {d: freq.get(d, 0) for d in outras}
                dz_escolhida = max(freq_outras, key=freq_outras.get)
                self.ultimo_gatilho = 'SEQUENCIA_ERROS'
                return {'tipo': 'SEQUENCIA_ERROS', 'dz_quebra': dz_escolhida, 'dz_exaurida': dz_errada, 'forca': 8,
                       'descricao': f'2 erros seguidos - Mudando de D{dz_errada}'}
        
        if len(freq) == 2 and freq.most_common(1)[0][1] >= 6:
            dz1, dz2 = ranking[0][0], ranking[1][0]
            terceira = self._get_terceira_duzia(dz1, dz2)
            ultimas_5 = u[-5:]
            terceira_em_5 = sum(1 for d in ultimas_5 if d == terceira)
            if terceira_em_5 >= 1:
                self.ultimo_gatilho = 'QUEBRA_ALTERNANCIA'
                return {'tipo': 'QUEBRA_ALTERNANCIA', 'dz_quebra': terceira, 'dz_exaurida': dz1, 'forca': 7,
                       'descricao': f'Ciclo D{dz1}/D{dz2} quebrando - D{terceira} apareceu'}
        
        if 0 in u[-5:]:
            pos_zero = len(u) - 1 - u[::-1].index(0)
            depois_zero = u[pos_zero+1:]
            if len(depois_zero) >= 2:
                if depois_zero[-1] != dz_dominante and depois_zero[-1] != 0:
                    self.ultimo_gatilho = 'QUEBRA_POS_ZERO'
                    return {'tipo': 'QUEBRA_POS_ZERO', 'dz_quebra': depois_zero[-1], 'dz_exaurida': dz_dominante, 'forca': 7,
                           'descricao': f'Zero quebrou dominância D{dz_dominante} → D{depois_zero[-1]}'}
        
        if len(u) >= 12:
            primeira_metade = u[:6]
            segunda_metade = u[-6:]
            freq_1 = Counter([d for d in primeira_metade if d != 0])
            freq_2 = Counter([d for d in segunda_metade if d != 0])
            if freq_1 and freq_2:
                dom_1 = freq_1.most_common(1)[0]
                dom_2 = freq_2.most_common(1)[0]
                if (dom_1[0] != dom_2[0] and dom_1[1] >= 5 and dom_2[1] >= 4 and 
                    freq_2.get(dom_1[0], 0) <= 1 and not self._eh_caos(freq_2)):
                    self.sinal_mudanca_pendente = {
                        'dz_quebra': dom_2[0], 'dz_exaurida': dom_1[0],
                        'descricao': f'Possível mudança: D{dom_1[0]}({dom_1[1]}/6) → D{dom_2[0]}({dom_2[1]}/6)'
                    }
                    return None
        return None
    
    # ========== DETECTORES UNIVERSAIS ==========
    def detectar_quebra_estados(self):
        if len(self.historico) < 5:
            return None
        u = list(self.historico)
        resultado = {'quebra_prevista': None, 'forca': 0, 'estado_atual': None, 'duzias_envolvidas': []}
        streak_count, streak_d = self.streak()
        u_recente = u[-8:] if len(u) >= 8 else u
        freq = Counter([d for d in u_recente if d != 0])
        duzias_ativas = [d for d in [1,2,3] if freq.get(d, 0) > 0]
        alternancias = {}
        for i in range(len(u_recente)-1):
            a, b = u_recente[i], u_recente[i+1]
            if a != 0 and b != 0 and a != b:
                par = tuple(sorted([a, b]))
                alternancias[par] = alternancias.get(par, 0) + 1
        
        if streak_count >= 3 and streak_d != 0:
            outras = self._get_outras_duzias(streak_d)
            forca = min(8, 2 + (streak_count - 3) * 2)
            freq_outras = {d: freq.get(d, 0) for d in outras}
            destinos_hist = {d: 0 for d in outras}
            for i in range(len(u) - 1):
                if u[i] == streak_d:
                    j = i + 1
                    while j < len(u) and u[j] == streak_d:
                        j += 1
                    if j < len(u) and u[j] != 0 and u[j] != streak_d:
                        destinos_hist[u[j]] += 1
            scores_quebra = {}
            for d in outras:
                score = 0
                if freq_outras[d] >= 2: score += 3
                elif freq_outras[d] >= 1: score += 1
                if destinos_hist[d] >= 2: score += 4
                elif destinos_hist[d] >= 1: score += 2
                if freq_outras[d] == 0 and len(u) >= 10: score += 2
                scores_quebra[d] = score
            if scores_quebra:
                dz_quebra = max(scores_quebra, key=scores_quebra.get)
                if scores_quebra[dz_quebra] >= 2:
                    resultado['quebra_prevista'] = dz_quebra
                    resultado['forca'] = forca + (scores_quebra[dz_quebra] * 0.5)
                    resultado['estado_atual'] = 'STREAK'
                    resultado['duzias_envolvidas'] = [streak_d, dz_quebra]
                    return resultado
        return None
    
    def detectar_terceira_duzia_intrusa(self):
        if len(self.historico) < 8: return None
        u = list(self.historico)[-10:]
        freq = Counter([d for d in u if d != 0])
        if len(freq) < 2: return None
        ranking = freq.most_common()
        if len(ranking) < 2: return None
        dz1, count1 = ranking[0]
        dz2, count2 = ranking[1]
        terceira = self._get_terceira_duzia(dz1, dz2)
        if terceira is None: return None
        count_terceira = freq.get(terceira, 0)
        if (count1 + count2) >= 7 and count_terceira <= 1:
            forca = 3 + (8 - count_terceira) * 0.7
            forca = min(8, forca)
            if count_terceira == 0: forca += 2
            return terceira, forca, dz1, dz2
        if count_terceira == 1 and (count1 + count2) >= 6:
            if terceira in u[-4:]:
                return terceira, 4, dz1, dz2
        return None
    
    def detectar_retorno_aba(self):
        if len(self.historico) < 3: return None
        u = list(self.historico)[-3:]
        if u[0] == u[2] and u[0] != u[1] and u[0] != 0 and u[1] != 0:
            return u[0], 5
        return None
    
    def detectar_duas_dominantes(self):
        if len(self.historico) < 10: return None
        ultimos_10 = list(self.historico)[-10:]
        freq = Counter(ultimos_10)
        ranking = freq.most_common()
        if len(ranking) >= 2:
            top2_sum = ranking[0][1] + ranking[1][1]
            if top2_sum >= 8: return (ranking[0][0], ranking[1][0]), 3
        return None
    
    def detectar_progressao(self):
        if len(self.historico) < 4: return None
        u = list(self.historico)[-4:]
        if u[0] == u[1] and u[2] == u[3] and u[1] != u[2] and u[0] != 0 and u[2] != 0:
            return u[2], 4
        return None
    
    def detectar_streak_longo(self):
        streak_count, streak_d = self.streak()
        if streak_count >= 3 and streak_d != 0:
            return streak_d, min(10, 4 + (streak_count - 3) * 2)
        return None
    
    def detectar_pos_zero(self):
        if len(self.historico) < 3: return None
        u = list(self.historico)[-3:]
        if u[-1] == 0 or u[-2] == 0:
            for d in reversed(u[:-1]):
                if d != 0: return d, 5
        return None
    
    def detectar_vai_e_volta(self):
        u = list(self.historico)
        if len(u) >= 4 and u[-4] == u[-2] and u[-3] == u[-1] and u[-4] != u[-3] and u[-4] != 0 and u[-3] != 0:
            return u[-3], 6
        if len(u) >= 5 and u[-5] == u[-3] == u[-1] and u[-4] == u[-2] and u[-5] != u[-4] and u[-5] != 0 and u[-4] != 0:
            return u[-4], 8
        return None
    
    def detectar_repeticao_imediata(self):
        if len(self.historico) < 3: return None
        u = list(self.historico)[-3:]
        if u[0] != u[1] and u[1] == u[2] and u[1] != 0: return u[1], 6
        if len(self.historico) >= 2:
            u2 = list(self.historico)[-2:]
            if u2[0] == u2[1] and u2[0] != 0: return u2[0], 4
        return None
    
    def detectar_regime(self):
        freq = self.frequencia()
        total = sum(freq.values())
        if total == 0: return "NEUTRO"
        razao = max(freq.values()) / total
        if razao > 0.5: return "DOMINANTE"
        elif razao > 0.4: return "TENDENCIA"
        elif len([d for d in freq if freq[d] > 0]) == 3: return "DISTRIBUIDO"
        else: return "TRANSICAO"
    
    # ========== CÁLCULO DE SCORE ==========
    def calcular_score(self):
        score = {1: 0, 2: 0, 3: 0}
        detalhes = {1: [], 2: [], 3: []}
        freq = self.frequencia_ponderada()
        freq_normal = self.frequencia()
        streak_count, streak_d = self.streak()
        trans = self.transicao()
        prob = self.matriz_transicao()
        regime = self.detectar_regime()
        
        for d in score: score[d] += freq[d] * 0.8
        total_normal = sum(freq_normal.values())
        if total_normal > 0:
            for d in score: score[d] += (freq_normal[d] / total_normal) * 10
        if streak_d and streak_d != 0:
            multiplicador = 3.0 if regime == "DOMINANTE" else 2.0 if regime == "TENDENCIA" else 1.5
            score[streak_d] += streak_count * multiplicador
        if trans and regime not in ["DOMINANTE", "TENDENCIA"]:
            ant, _ = trans
            if ant != 0: score[ant] += 2.5
        
        # STREAK 2x FORÇA O SCORE
        if len(self.historico) >= 2:
            u = list(self.historico)
            ultimas_2 = u[-2:]
            if len(set(ultimas_2)) == 1 and ultimas_2[0] != 0:
                dz_streak = ultimas_2[0]
                score[dz_streak] += 25
                detalhes[dz_streak].append(f"🔥 STREAK D{dz_streak} 2x: +25")
                outras = self._get_outras_duzias(dz_streak)
                for d in outras:
                    score[d] *= 0.5
                    detalhes[d].append(f"⚠️ Anti-Streak: -50%")
        
        # DÚZIAS DO MOMENTO
        if len(self.historico) >= 6:
            u = list(self.historico)
            ultimas_6 = u[-6:]
            freq_6 = Counter([d for d in ultimas_6 if d != 0])
            ranking_6 = freq_6.most_common()
            if len(ranking_6) >= 2:
                dz1, dz2 = ranking_6[0][0], ranking_6[1][0]
                if ranking_6[0][1] + ranking_6[1][1] >= 5:
                    terceira = self._get_terceira_duzia(dz1, dz2)
                    if terceira not in ultimas_6[-4:]:
                        score[terceira] *= 0.2
                        detalhes[terceira].append(f"🚫 FORA DO MOMENTO: -80%")
                        if u[-1] == dz1:
                            score[dz1] += 15
                            detalhes[dz1].append(f"🎯 MOMENTO D{dz1}/D{dz2}: +15")
                        elif u[-1] == dz2:
                            score[dz2] += 15
                            detalhes[dz2].append(f"🎯 MOMENTO D{dz1}/D{dz2}: +15")
        
        # GATILHOS
        exaustao = self.detectar_exaustao_ciclo_dominante()
        if exaustao:
            score[exaustao['dz_quebra']] += self.get_peso_adaptativo('exaustao_ciclo', exaustao['forca'] * 1.5)
            detalhes[exaustao['dz_quebra']].append(f"🎯 GATILHO: {exaustao['descricao']}")
            score[exaustao['dz_exaurida']] *= 0.3
        
        # 🆕 DETECTOR DE TROCA SÚBITA
        troca_subita = self.detectar_troca_subita()
        if troca_subita:
            dz, forca = troca_subita
            score[dz] += forca * 1.5
            detalhes[dz].append(f"⚡ TROCA SÚBITA: +{forca*1.5:.1f}")
        
        # CILINDRO FÍSICO
        if len(self.numeros_completos) >= 10:
            janela = self.historico.maxlen if self.historico.maxlen else 30
            nums_janela = self.numeros_completos[-janela:]
            voisins = [22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25]
            tiers = [27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33]
            orphelins = [1, 20, 14, 31, 9, 17, 34]
            v_count = sum(1 for n in nums_janela if n in voisins)
            t_count = sum(1 for n in nums_janela if n in tiers)
            o_count = sum(1 for n in nums_janela if n in orphelins)
            total_janela = len(nums_janela)
            if v_count > total_janela * 0.45:
                score[2] += 4; score[3] += 4
            elif t_count > total_janela * 0.40:
                score[2] += 2; score[3] += 3
            elif o_count > total_janela * 0.35:
                score[2] += 5
        
        # Normalização
        total = sum(score.values())
        if total > 0:
            for d in score: score[d] = (score[d] / total) * 100
        return score, regime, detalhes
    
    def prever(self, confianca_minima=3.2, agressividade=2):
        score, regime, detalhes = self.calcular_score()
        ranking = sorted(score.items(), key=lambda x: x[1], reverse=True)
        d1, s1 = ranking[0]
        d2, s2 = ranking[1]
        if d2 == d1:
            outras = self._get_outras_duzias(d1)
            d2 = ranking[2][0] if len(ranking) > 2 else (outras[0] if outras else d1)
        
        self.detectar_alerta_zero()
        
        ratio = min(5.0, s1 / max(1, s2))
        vol = np.std(list(score.values()))
        confianca = min(10.0, max(1.0, (ratio * 2.2) + (1.5 / (1 + vol))))
        self.ultima_confianca = confianca
        
        if self.alerta_zero_ativo:
            confianca = confianca * 0.6
        confianca = self.calibrar_confianca(confianca)
        
        forca_detectores = 0
        detectores_ativos = []
        for dz in detalhes:
            for det in detalhes[dz]:
                if '+' in det:
                    try:
                        forca_detectores += float(det.split('+')[1].strip().split()[0])
                        detector_nome = det.split('(')[0].strip()
                        if detector_nome not in detectores_ativos:
                            detectores_ativos.append(detector_nome)
                    except: pass
        
        if self.ultimo_gatilho: detectores_ativos.insert(0, f"GATILHO:{self.ultimo_gatilho}")
        if self.sinal_mudanca_pendente: detectores_ativos.insert(0, "SINAL_PENDENTE")
        if self.streak_ativo: detectores_ativos.insert(0, f"STREAK:D{self.streak_ativo}")
        if self.alerta_zero_ativo: detectores_ativos.insert(0, "⚠️ ALERTA ZERO")
        
        streak_count, _ = self.streak()
        tem_gatilho_quebra = self.ultimo_gatilho is not None
        pode_entrar = False
        motivo = ""
        
        if self.sinal_mudanca_pendente:
            pode_entrar = False
            motivo = f"⏳ Aguardando confirmação"
        elif tem_gatilho_quebra:
            pode_entrar = True
            confianca = max(2.0, confianca * 0.7)
        elif regime == "DISTRIBUIDO" and not streak_count >= 3 and forca_detectores < 5:
            motivo = "Mercado distribuído sem padrão claro"
        elif confianca < confianca_minima and forca_detectores < 5:
            motivo = f"Confiança baixa ({confianca:.2f})"
        else:
            pode_entrar = True
        
        previsao = {
            "entrar": pode_entrar, "motivo": motivo if not pode_entrar else "",
            "score": score, "regime": regime, "confianca": round(confianca, 2),
            "duzia": d1, "duzia_secundaria": d2, "detalhes": detalhes,
            "detectores_ativos": detectores_ativos, "gatilho_ativo": self.ultimo_gatilho,
            "incluir_zero": self.alerta_zero_ativo
        }
        
        if pode_entrar:
            previsao = self.balancear_previsoes(previsao)
        
        # 🔥🔥 FORÇA FINAL
        if len(self.historico) >= 2:
            u = list(self.historico)
            ultimas_2 = u[-2:]
            if len(set(ultimas_2)) == 1 and ultimas_2[0] != 0:
                if previsao['duzia'] != ultimas_2[0]:
                    previsao['duzia'] = ultimas_2[0]
                    self.streak_ativo = ultimas_2[0]
                    outras = self._get_outras_duzias(ultimas_2[0])
                    freq_outras = {d: u.count(d) for d in outras}
                    previsao['duzia_secundaria'] = max(freq_outras, key=freq_outras.get)
        
        previsao = self._garantir_cobertura_diferente(previsao)
        self.ultimo_gatilho = None
        return previsao

# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaBot:
    def __init__(self):
        janela = st.session_state.get('janela_duzia_ai', 30)
        self.duzia_ai = DuziaAI(window=janela)
        self.historico_numeros = deque(maxlen=200)
        self.entrada_ativa = None
        self.historico_entradas = []
        self.acertos = 0
        self.erros = 0
        self.ultimo_numero = None
        self.sinais_grafico = []
        self.numero_rodada = 0
    
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data['number']
        else:
            nr = int(numero_data)
        if not validar_numero(nr):
            return
        self.numero_rodada += 1
        self.duzia_ai.adicionar(nr)
        self.historico_numeros.append(nr)
        self.ultimo_numero = nr
        
        if self.entrada_ativa:
            duzia_real = get_duzia(nr)
            duzia_prevista = self.entrada_ativa.get('duzia_prevista')
            duzia_sec_prevista = self.entrada_ativa.get('duzia_sec_prevista')
            incluir_zero = self.entrada_ativa.get('incluir_zero', False)
            
            acerto_primaria = (duzia_real == duzia_prevista) if duzia_prevista and nr != 0 else False
            acerto_secundaria = (duzia_real == duzia_sec_prevista) if duzia_sec_prevista and nr != 0 else False
            acerto_zero = (nr == 0 and incluir_zero)
            if acerto_zero: acerto_primaria = True
            
            if acerto_primaria:
                self.acertos += 1
                st.session_state.acertos_duzia = st.session_state.get('acertos_duzia', 0) + 1
            elif acerto_secundaria:
                st.session_state.acertos_duzia_sec = st.session_state.get('acertos_duzia_sec', 0) + 1
                self.acertos += 0.5
            else:
                self.erros += 1
                st.session_state.erros_duzia = st.session_state.get('erros_duzia', 0) + 1
            
            self.duzia_ai.registrar_resultado(duzia_real, acerto_primaria or acerto_secundaria)
            if self.entrada_ativa.get('confianca'):
                self.duzia_ai.calibrar_confianca(self.entrada_ativa['confianca'], acerto_primaria or acerto_secundaria)
            
            entrada_info = {
                'rodada': self.numero_rodada, 'hora': formatar_hora_brasilia(),
                'numero': nr, 'duzia_real': duzia_real if nr != 0 else 0,
                'duzia_prevista': duzia_prevista, 'duzia_sec_prevista': duzia_sec_prevista,
                'acerto_primaria': acerto_primaria, 'acerto_secundaria': acerto_secundaria,
                'confianca': self.entrada_ativa.get('confianca', 0),
                'regime': self.entrada_ativa.get('regime', 'NEUTRO'),
                'modo': 'Agressivo' if st.session_state.get('modo_agressivo', False) else 'Conservador',
                'gatilho': self.entrada_ativa.get('gatilho_ativo', None),
                'incluir_zero': incluir_zero
            }
            self.historico_entradas.append(entrada_info)
            if len(self.historico_entradas) > 50:
                self.historico_entradas = self.historico_entradas[-50:]
            enviar_resultado_auto(nr, acerto_primaria or acerto_secundaria)
            self.entrada_ativa = None
        
        previsao = self.duzia_ai.prever(
            st.session_state.get('confianca_minima', 3.2),
            st.session_state.get('agressividade', 2)
        )
        if previsao['entrar']:
            duzia_map = {1: list(range(1,13)), 2: list(range(13,25)), 3: list(range(25,37))}
            numeros_principais = duzia_map.get(previsao['duzia'], [])
            numeros_secundarios = duzia_map.get(previsao.get('duzia_secundaria', previsao['duzia']), [])
            
            if st.session_state.get('modo_agressivo', False) and previsao.get('duzia_secundaria'):
                if previsao['duzia_secundaria'] != previsao['duzia']:
                    numeros_apostar = list(set(numeros_principais + numeros_secundarios))
                else:
                    numeros_apostar = numeros_principais
            else:
                numeros_apostar = numeros_principais
            
            if previsao.get('incluir_zero', False) and 0 not in numeros_apostar:
                numeros_apostar = [0] + numeros_apostar
            
            self.entrada_ativa = {
                'numeros_apostar': numeros_apostar,
                'duzia_prevista': previsao['duzia'],
                'duzia_sec_prevista': previsao.get('duzia_secundaria'),
                'confianca': previsao.get('confianca', 0),
                'regime': previsao.get('regime', 'NEUTRO'),
                'score': previsao.get('score', {}),
                'detalhes': previsao.get('detalhes', {}),
                'detectores_ativos': previsao.get('detectores_ativos', []),
                'gatilho_ativo': previsao.get('gatilho_ativo', None),
                'incluir_zero': previsao.get('incluir_zero', False)
            }
            self.duzia_ai.registrar_previsao(previsao['duzia'])
            idx_atual = len(self.historico_numeros) - 1
            self.sinais_grafico.append((idx_atual, previsao['duzia']))
            enviar_previsao_auto({'numeros_apostar': numeros_apostar, 'incluir_zero': previsao.get('incluir_zero', False)})
    
    def zerar(self):
        self.acertos = 0; self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear()
        self.entrada_ativa = None
        self.ultimo_numero = None
        self.sinais_grafico = []
        self.numero_rodada = 0
        janela = st.session_state.get('janela_duzia_ai', 30)
        self.duzia_ai = DuziaAI(window=janela)
        st.session_state.acertos_duzia = 0; st.session_state.erros_duzia = 0
        st.session_state.acertos_duzia_sec = 0; st.session_state.erros_duzia_sec = 0
        salvar_sessao()

# =============================
# FUNÇÕES AUXILIARES
# =============================
def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    try:
        with open(caminho, "w", encoding='utf-8') as f:
            json.dump(historico, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")

def fetch_latest_result():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=5)
        r.raise_for_status()
        d = r.json()
        gd = d.get("data", {})
        rs = gd.get("result", {})
        nm = rs.get("outcome", {}).get("number")
        ts = gd.get("startedAt")
        ln, lm = [], {}
        for item in rs.get('luckyNumbersList', []):
            n = item.get('number')
            if n is not None:
                ln.append(n)
                m = item.get('roundedMultiplier')
                if m is not None: lm[n] = m
        return {"number": nm, "timestamp": ts, "luckyNumbers": ln, "luckyMultipliers": lm}
    except Exception as e:
        logging.warning(f"Erro ao buscar API: {e}")
        return None

def exportar_historico_csv(historico_entradas, caminho="export_roleta.csv"):
    import csv
    try:
        with open(caminho, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Rodada', 'Hora', 'Número', 'Dúzia Real', 'Dúzia Prevista', 'Confiança', 'Gatilho', 'Resultado'])
            for entrada in historico_entradas:
                resultado = '✅' if entrada.get('acerto_primaria') else '🟡' if entrada.get('acerto_secundaria') else '❌'
                duzia_real = f"D{entrada.get('duzia_real', 0)}" if entrada.get('duzia_real', 0) != 0 else "0"
                gatilho = entrada.get('gatilho', '') if entrada.get('gatilho') else "-"
                writer.writerow([entrada.get('rodada', '-'), entrada.get('hora', '-'), entrada.get('numero', '-'),
                               duzia_real, f"D{entrada.get('duzia_prevista', '?')}",
                               f"{entrada.get('confianca', 0):.2f}", gatilho, resultado])
        return True
    except Exception as e:
        logging.error(f"Erro ao exportar CSV: {e}")
        return False

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎰 DuziaAI V7.0 - Anti-Erros + Cilindro", layout="wide")
st.title("🎰 DuziaAI V7.0 - Anti-Erros + Cilindro (BRT)")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    sis = st.session_state.sistema
    numeros = dados.get('historico_numeros', [])
    sis.numero_rodada = dados.get('numero_rodada', len(numeros))
    for n in numeros: sis.duzia_ai.adicionar(n); sis.historico_numeros.append(n)
    sis.acertos = dados.get('sistema_acertos', 0)
    sis.erros = dados.get('sistema_erros', 0)
    sis.entrada_ativa = dados.get('entrada_ativa', None)
    st.session_state.acertos_duzia = dados.get('acertos_duzia', 0)
    st.session_state.erros_duzia = dados.get('erros_duzia', 0)
    st.session_state.acertos_duzia_sec = dados.get('acertos_duzia_sec', 0)
    st.session_state.erros_duzia_sec = dados.get('erros_duzia_sec', 0)
    st.session_state.modo_agressivo = dados.get('modo_agressivo', False)
    st.session_state.confianca_minima = dados.get('confianca_minima', 3.2)
    st.session_state.agressividade = dados.get('agressividade', 2)
    if os.path.exists(ENTRADAS_PATH):
        try:
            with open(ENTRADAS_PATH, 'r') as f: sis.historico_entradas = json.load(f)
        except: pass

defaults = {'modo_automatico': True, 'modo_agressivo': False, 'janela_duzia_ai': 30,
            'confianca_minima': 3.2, 'agressividade': 2,
            'acertos_duzia': 0, 'erros_duzia': 0, 'acertos_duzia_sec': 0, 'erros_duzia_sec': 0}
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
    st.markdown("## ⚙️ Configurações")
    if st.button("🆕 NOVA SESSÃO", use_container_width=True, type="primary"):
        if nova_sessao(): st.success("✅ Nova sessão iniciada!"); st.rerun()
    st.markdown("---")
    st.session_state.janela_duzia_ai = st.slider("📏 Janela de Análise", 10, 50, st.session_state.janela_duzia_ai, 5)
    st.session_state.confianca_minima = st.slider("🎯 Confiança Mínima", 2.0, 5.0, st.session_state.confianca_minima, 0.2)
    st.session_state.agressividade = st.select_slider("🎚️ Agressividade", options=[1,2,3], value=st.session_state.agressividade)
    st.session_state.modo_agressivo = st.checkbox("🔥 Modo Agressivo (2 Dúzias)", value=st.session_state.modo_agressivo)
    st.session_state.modo_automatico = st.checkbox("🤖 Modo Automático", value=st.session_state.modo_automatico)
    st.markdown("---")
    st.markdown("### 📊 V7.0 - Anti-Erros")
    st.caption("🚫 ANTI-REPETIÇÃO: Bloqueia após 2 erros")
    st.caption("📉📉📉 CALIBRAÇÃO IMEDIATA: -60%")
    st.caption("🎯 MICRO-TENDÊNCIA: Segue última")
    st.caption("⚡ TROCA SÚBITA: Detecta mudanças")
    st.caption("🔥🔥 FORÇA FINAL Streak 2x")
    st.caption("🎡 CILINDRO FÍSICO: Voisins/Tiers/Orphelins")
    st.markdown("---")
    with st.expander("🔔 Telegram", expanded=False):
        st.session_state.telegram_token = st.text_input("Token", value=st.session_state.telegram_token, type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID", value=st.session_state.telegram_chat_id)
    col1, col2, col3 = st.columns(3)
    col1.button("💾 Salvar", on_click=lambda: [salvar_resultado_em_arquivo(st.session_state.historico), salvar_sessao(), st.success("✅ Salvo!")], use_container_width=True)
    col2.button("🗑️ Zerar", on_click=lambda: st.session_state.sistema.zerar() or st.rerun(), use_container_width=True)
    col3.button("📥 CSV", on_click=lambda: exportar_historico_csv(st.session_state.sistema.historico_entradas) and st.success("✅ CSV exportado!"), use_container_width=True)

# Conteúdo principal
st.subheader("🎲 Inserir Números")
c1, c2, c3 = st.columns([3,1,1])
with c1:
    entrada = st.text_input("Número (0-36):", placeholder="Digite o número sorteado", key="entrada_numero")
with c2:
    if st.button("🎯 Enviar", use_container_width=True, type="primary"):
        if validar_numero(entrada):
            nr = int(entrada)
            item = {"number": nr, "timestamp": timestamp_brasilia(), "luckyNumbers": [], "luckyMultipliers": {}}
            st.session_state.historico.append(item)
            st.session_state.sistema.processar_novo_numero(item)
            salvar_resultado_em_arquivo(st.session_state.historico)
            salvar_sessao()
            st.rerun()
        else:
            st.error("Digite um número válido (0-36)")
with c3:
    if st.button("🔄 Auto", use_container_width=True):
        st.session_state.modo_automatico = not st.session_state.modo_automatico
        st.rerun()

if st.session_state.modo_automatico:
    st_autorefresh(interval=3000, key="auto_refresh")
    resultado = fetch_latest_result()
    if resultado and resultado.get("number") is not None:
        if not st.session_state.historico or resultado["timestamp"] != st.session_state.historico[-1].get("timestamp"):
            st.session_state.historico.append(resultado)
            st.session_state.sistema.processar_novo_numero(resultado)
            salvar_resultado_em_arquivo(st.session_state.historico)
            salvar_sessao()
            st.rerun()

st.markdown("---")
sis = st.session_state.sistema

# Métricas
col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
total_entradas = int(sis.acertos + sis.erros)
tx_acerto = (sis.acertos / total_entradas * 100) if total_entradas > 0 else 0
col1.metric("✅ Acertos", int(sis.acertos))
col2.metric("❌ Erros", int(sis.erros))
col3.metric("📊 Win Rate", f"{tx_acerto:.1f}%")
col4.metric("🎯 Tx Primária", f"{(st.session_state.get('acertos_duzia',0)/(st.session_state.get('acertos_duzia',0)+st.session_state.get('erros_duzia',0))*100) if (st.session_state.get('acertos_duzia',0)+st.session_state.get('erros_duzia',0))>0 else 0:.1f}%")
col5.metric("📦 Entradas", total_entradas)
col6.metric("🔢 Rodada", sis.numero_rodada)
col7.metric("⚠️ Alerta Zero", "🟢" if sis.duzia_ai.alerta_zero_ativo else "⚪")

st.markdown("---")
st.caption(f"🤖 DuziaAI V7.0 | Anti-Erros + Cilindro + BRT | {formatar_hora_brasilia()}")
salvar_sessao()
