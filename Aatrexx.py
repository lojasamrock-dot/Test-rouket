import streamlit as st
import json
import os
import requests
import logging
import random
from collections import Counter, deque, defaultdict
from streamlit_autorefresh import st_autorefresh
import pickle
from datetime import datetime
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
        
        performance_data = {
            'acertos': sis.acertos,
            'erros': sis.erros
        }
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
            'modo_duzia_ai': st.session_state.get('modo_duzia_ai', True),
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

# =============================
# NOTIFICAÇÕES (SIMPLIFICADAS)
# =============================
def enviar_previsao_auto(previsao):
    try:
        numeros = sorted(previsao.get('numeros_apostar', []))
        
        duzia1_numeros = [n for n in numeros if 1 <= n <= 12]
        duzia2_numeros = [n for n in numeros if 13 <= n <= 24]
        duzia3_numeros = [n for n in numeros if 25 <= n <= 36]
        
        if duzia1_numeros and duzia2_numeros:
            mensagem = "🎯 Entrada: D1 (1-12) | Cobertura: D2 (13-24)"
            st.toast(mensagem)
        elif duzia1_numeros and duzia3_numeros:
            mensagem = "🎯 Entrada: D1 (1-12) | Cobertura: D3 (25-36)"
            st.toast(mensagem)
        elif duzia2_numeros and duzia3_numeros:
            mensagem = "🎯 Entrada: D2 (13-24) | Cobertura: D3 (25-36)"
            st.toast(mensagem)
        elif duzia1_numeros:
            mensagem = "🎯 Entrada: D1 (1-12)"
            st.toast(mensagem)
        elif duzia2_numeros:
            mensagem = "🎯 Entrada: D2 (13-24)"
            st.toast(mensagem)
        elif duzia3_numeros:
            mensagem = "🎯 Entrada: D3 (25-36)"
            st.toast(mensagem)
        else:
            mensagem = f"🎯 Entrada: {numeros}"
            st.toast(mensagem)
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"🔔 {mensagem}\n🔢 " + " ".join(map(str, numeros)))
        
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar previsão: {e}")

def enviar_resultado_auto(numero_real, acerto, lucky=False):
    try:
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
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"},
            timeout=10
        )
        response.raise_for_status()
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
    """Valida se é um número de roleta válido"""
    try:
        num = int(valor)
        return 0 <= num <= 36
    except (ValueError, TypeError):
        return False

# =============================
# 🧠 DUZIA AI V6.5 MELHORADA
# =============================
class DuziaAI:
    def __init__(self, window=30):
        self.historico = deque(maxlen=window)
        self.historico_completo = []
        self.numeros_completos = []
        self.sinais_entrada = []
        self.ultimas_previsoes = []
        self.ultimos_resultados = []
        # Sistema de aprendizado adaptativo
        self.performance_detectores = defaultdict(list)
        self.pesos_adaptativos = {
            'quebra_estados': 1.4,
            'terceira_intrusa': 1.5,
            'mudanca_abrupta': 1.3,
            'exaustao_ciclo': 1.8,
            'zigzag_d1_d2': 0.5,
            'bloco_d3': 0.7,
            'pos_zero_plus': 0.4,
            'repeticao_imediata': 1.0,
            'streak_longo': 1.0,
            'retorno_aba': 1.0,
            'duas_dominantes': 1.0,
            'progressao': 1.0,
            'troca_duas': 1.0,
            'bloco_dominante': 1.0,
        }
        self.ciclos_dominantes = []
        self.ultimo_gatilho = None
        self.sinal_mudanca_pendente = None
        self.streak_ativo = None
    
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
            'duzia': duzia_real,
            'acertou': acertou,
            'timestamp': datetime.now()
        })
        if len(self.ultimos_resultados) > 20:
            self.ultimos_resultados = self.ultimos_resultados[-20:]
    
    def registrar_performance_detector(self, detector, acertou):
        self.performance_detectores[detector].append(1 if acertou else 0)
        if len(self.performance_detectores[detector]) > 20:
            self.performance_detectores[detector] = self.performance_detectores[detector][-20:]
    
    def get_peso_adaptativo(self, detector, peso_base):
        recentes = self.performance_detectores[detector][-10:]
        if not recentes:
            return peso_base
        taxa_acerto = sum(recentes) / len(recentes)
        fator = 0.5 + taxa_acerto
        return peso_base * fator
    
    def balancear_previsoes(self, previsao):
        """
        ANTI-TEIMOSIA 2x ABSOLUTA (V6.5 MELHORADA)
        """
        if len(self.historico) < 2:
            return previsao
        
        u = list(self.historico)
        score = previsao.get('score', {})
        
        # STREAK 2x ABSOLUTO - IGNORA o score
        if len(u) >= 2:
            ultimas_2 = u[-2:]
            if len(set(ultimas_2)) == 1 and ultimas_2[0] != 0:
                dz_streak = ultimas_2[0]
                if previsao['duzia'] != dz_streak:
                    logging.info(f"🔄 STREAK D{dz_streak} 2x ABSOLUTO! Seguindo fluxo")
                    previsao['duzia'] = dz_streak
                    self.streak_ativo = dz_streak
                    outras = self._get_outras_duzias(dz_streak)
                    freq_outras = {d: u.count(d) for d in outras}
                    previsao['duzia_secundaria'] = max(freq_outras, key=freq_outras.get)
                    return previsao
        
        # STREAK 3x REFORÇO
        if len(u) >= 3:
            ultimas_3 = u[-3:]
            if len(set(ultimas_3)) == 1 and ultimas_3[0] != 0:
                dz_streak = ultimas_3[0]
                if previsao['duzia'] != dz_streak:
                    logging.info(f"🔄 STREAK D{dz_streak} 3x! Reforçando")
                    previsao['duzia'] = dz_streak
                    self.streak_ativo = dz_streak
                    outras = self._get_outras_duzias(dz_streak)
                    freq_outras = {d: u.count(d) for d in outras}
                    previsao['duzia_secundaria'] = max(freq_outras, key=freq_outras.get)
                    return previsao
        
        # SAÍDA DO STREAK
        if len(self.ultimas_previsoes) >= 2:
            ultimas_2_prev = self.ultimas_previsoes[-2:]
            if len(set(ultimas_2_prev)) == 1:
                dz_seguindo = ultimas_2_prev[0]
                
                if u[-1] != dz_seguindo and u[-1] != 0:
                    logging.info(f"🚪 SAÍDA: Streak D{dz_seguindo} QUEBROU!")
                    self.streak_ativo = None
                    previsao['duzia'] = u[-1]
                    return previsao
                
                if len(self.ultimos_resultados) >= 2:
                    ultimos_2_res = self.ultimos_resultados[-2:]
                    if not ultimos_2_res[0]['acertou'] and not ultimos_2_res[1]['acertou']:
                        logging.info(f"🚪 SAÍDA: 2 erros seguindo D{dz_seguindo}!")
                        self.streak_ativo = None
                        freq_recente = Counter(u[-5:])
                        outras = self._get_outras_duzias(dz_seguindo)
                        freq_outras = {d: freq_recente.get(d, 0) for d in outras}
                        previsao['duzia'] = max(freq_outras, key=freq_outras.get)
                        return previsao
        
        # NÃO REPETIR APÓS ERRO
        if self.ultimos_resultados and not self.ultimos_resultados[-1]['acertou']:
            duzia_errada = self.ultimos_resultados[-1]['duzia']
            if previsao['duzia'] == duzia_errada and previsao.get('duzia_secundaria'):
                previsao['duzia'] = previsao['duzia_secundaria']
                logging.info(f"Evitando repetir D{duzia_errada} após erro")
                return previsao
        
        # BALANCEAMENTO
        if len(self.ultimas_previsoes) >= 5:
            freq = Counter(self.ultimas_previsoes[-5:])
            if abs(score.get(1, 0) - score.get(2, 0)) < 5:
                if freq[1] >= 4 and score.get(2, 0) > 30:
                    previsao['duzia'] = 2
                    previsao['duzia_secundaria'] = 1
                    logging.info("D1/D2 equilibradas - Alternando para D2")
        
        return previsao
    
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
        matriz = {1: {1: 0, 2: 0, 3: 0},
                  2: {1: 0, 2: 0, 3: 0},
                  3: {1: 0, 2: 0, 3: 0}}
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
        if max_val <= 3 and max_val - min(valores) <= 2:
            return True
        return False
    
    # =============================================
    # 🎯 GATILHOS V6.5 ORIGINAIS + MELHORIAS
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
        count_dominante = ranking[0][1]
        
        # VERIFICA SINAL DE MUDANÇA PENDENTE
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
                logging.info(f"GATILHO CONFIRMADO: {resultado['descricao']}")
                return resultado
            else:
                self.sinal_mudanca_pendente = None
        
        # GATILHO 1: DOMINÂNCIA MUITO LONGA (7+ de 10)
        ultimas_10 = u[-10:]
        freq_10 = Counter([d for d in ultimas_10 if d != 0])
        
        if freq_10.get(dz_dominante, 0) >= 7:
            ultimas_3 = u[-3:]
            
            if dz_dominante not in ultimas_3[-2:]:
                outras = self._get_outras_duzias(dz_dominante)
                freq_emergentes = {d: freq.get(d, 0) for d in outras}
                dz_emergente = max(freq_emergentes, key=freq_emergentes.get)
                
                self.ultimo_gatilho = 'EXAUSTAO_DOMINANCIA'
                return {
                    'tipo': 'EXAUSTAO_DOMINANCIA',
                    'dz_quebra': dz_emergente,
                    'dz_exaurida': dz_dominante,
                    'forca': 9,
                    'descricao': f'D{dz_dominante} exaurida (7+/10) - Emergente D{dz_emergente}'
                }
            
            if len(ranking) >= 2:
                dz2 = ranking[1][0]
                terceira = self._get_terceira_duzia(dz_dominante, dz2)
                if terceira:
                    count_terceira_4 = sum(1 for d in ultimas_10[-4:] if d == terceira)
                    if count_terceira_4 >= 2:
                        self.ultimo_gatilho = 'INTRUSA_EMERGENTE'
                        return {
                            'tipo': 'INTRUSA_EMERGENTE',
                            'dz_quebra': terceira,
                            'dz_exaurida': dz_dominante,
                            'forca': 8,
                            'descricao': f'3ª Dúzia D{terceira} emergindo (2/4) - Quebra de D{dz_dominante}'
                        }
        
        # GATILHO 2: SEQUÊNCIA DE ERROS (MELHORADO - com tendência)
        if len(self.ultimos_resultados) >= 2:
            ultimos_2 = self.ultimos_resultados[-2:]
            if not ultimos_2[0]['acertou'] and not ultimos_2[1]['acertou']:
                # Verifica tendência nas últimas 5
                ultimas_5 = u[-5:]
                freq_5 = Counter([d for d in ultimas_5 if d != 0])
                
                if freq_5:
                    dz_tendencia = freq_5.most_common(1)[0]
                    if dz_tendencia[1] >= 3:
                        self.ultimo_gatilho = 'SEQUENCIA_ERROS'
                        return {
                            'tipo': 'SEQUENCIA_ERROS',
                            'dz_quebra': dz_tendencia[0],
                            'dz_exaurida': self.ultimos_resultados[-1]['duzia'],
                            'forca': 15,
                            'descricao': f'2 erros + Tendência D{dz_tendencia[0]} ({dz_tendencia[1]}/5)'
                        }
                
                # Sem tendência, ainda dispara mas com força menor
                dz_errada = ultimos_2[-1]['duzia'] if ultimos_2[-1]['duzia'] != 0 else dz_dominante
                outras = self._get_outras_duzias(dz_errada)
                freq_outras = {d: freq.get(d, 0) for d in outras}
                dz_escolhida = max(freq_outras, key=freq_outras.get)
                
                self.ultimo_gatilho = 'SEQUENCIA_ERROS'
                return {
                    'tipo': 'SEQUENCIA_ERROS',
                    'dz_quebra': dz_escolhida,
                    'dz_exaurida': dz_errada,
                    'forca': 10,
                    'descricao': f'2 erros seguidos - Forçando mudança de D{dz_errada}'
                }
        
        # GATILHO 3: PADRÃO DE ALTERNÂNCIA ESGOTANDO
        if len(freq) == 2 and count_dominante >= 6:
            dz1, dz2 = ranking[0][0], ranking[1][0]
            terceira = self._get_terceira_duzia(dz1, dz2)
            
            ultimas_5 = u[-5:]
            terceira_em_5 = sum(1 for d in ultimas_5 if d == terceira)
            
            if terceira_em_5 >= 1:
                self.ultimo_gatilho = 'QUEBRA_ALTERNANCIA'
                return {
                    'tipo': 'QUEBRA_ALTERNANCIA',
                    'dz_quebra': terceira,
                    'dz_exaurida': dz1,
                    'forca': 7,
                    'descricao': f'Ciclo D{dz1}/D{dz2} quebrando - D{terceira} apareceu'
                }
        
        # GATILHO 4: ZERO COMO INDICADOR DE QUEBRA
        if 0 in u[-5:]:
            pos_zero = len(u) - 1 - u[::-1].index(0)
            depois_zero = u[pos_zero+1:]
            
            if len(depois_zero) >= 2:
                if depois_zero[-1] != dz_dominante and depois_zero[-1] != 0:
                    self.ultimo_gatilho = 'QUEBRA_POS_ZERO'
                    return {
                        'tipo': 'QUEBRA_POS_ZERO',
                        'dz_quebra': depois_zero[-1],
                        'dz_exaurida': dz_dominante,
                        'forca': 7,
                        'descricao': f'Zero quebrou dominância D{dz_dominante} → D{depois_zero[-1]}'
                    }
        
        # GATILHO 5: MUDANÇA DE VELOCIDADE (CONFIRMADA)
        if len(u) >= 12:
            primeira_metade = u[:6]
            segunda_metade = u[-6:]
            
            freq_1 = Counter([d for d in primeira_metade if d != 0])
            freq_2 = Counter([d for d in segunda_metade if d != 0])
            
            if freq_1 and freq_2:
                dom_1 = freq_1.most_common(1)[0]
                dom_2 = freq_2.most_common(1)[0]
                
                if (dom_1[0] != dom_2[0] and 
                    dom_1[1] >= 5 and
                    dom_2[1] >= 4 and 
                    freq_2.get(dom_1[0], 0) <= 1 and
                    not self._eh_caos(freq_2)):
                    
                    self.sinal_mudanca_pendente = {
                        'dz_quebra': dom_2[0],
                        'dz_exaurida': dom_1[0],
                        'descricao': f'Possível mudança: D{dom_1[0]}({dom_1[1]}/6) → D{dom_2[0]}({dom_2[1]}/6)'
                    }
                    logging.info(f"SINAL PENDENTE: {self.sinal_mudanca_pendente['descricao']}")
                    return None
        
        return None
    
    # ========== DETECTORES UNIVERSAIS (70% PESO) ==========
    
    def detectar_quebra_estados(self):
        if len(self.historico) < 5:
            return None
        
        u = list(self.historico)
        resultado = {
            'quebra_prevista': None,
            'forca': 0,
            'estado_atual': None,
            'duzias_envolvidas': []
        }
        
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
        
        if len(alternancias) >= 1 and len(duzias_ativas) >= 2:
            par_principal = max(alternancias, key=alternancias.get)
            count_alt = alternancias[par_principal]
            
            if count_alt >= 4:
                dz1, dz2 = par_principal
                terceira = self._get_terceira_duzia(dz1, dz2)
                forca = min(8, 3 + (count_alt - 4) * 1.5)
                
                freq_terceira = freq.get(terceira, 0)
                if freq_terceira >= 1: forca += 1
                else: forca += 2
                
                resultado['quebra_prevista'] = terceira
                resultado['forca'] = forca
                resultado['estado_atual'] = 'ALTERNANCIA'
                resultado['duzias_envolvidas'] = [dz1, dz2, terceira]
                return resultado
        
        if len(duzias_ativas) == 3:
            if freq:
                menos_freq = min(freq, key=freq.get)
                mais_freq = max(freq, key=freq.get)
                diff = freq[mais_freq] - freq[menos_freq]
                
                if diff >= 3:
                    resultado['quebra_prevista'] = menos_freq
                    resultado['forca'] = 4
                    resultado['estado_atual'] = 'REBALANCEAMENTO'
                    resultado['duzias_envolvidas'] = duzias_ativas
                    return resultado
        
        if len(u) >= 4:
            if u[-3] == u[-1] and u[-3] != u[-2] and u[-3] != 0 and u[-2] != 0:
                if len(u) >= 6 and u[-5] == u[-3] == u[-1] and u[-4] == u[-2]:
                    terceira = self._get_terceira_duzia(u[-1], u[-2])
                    resultado['quebra_prevista'] = terceira
                    resultado['forca'] = 5
                    resultado['estado_atual'] = 'PADRAO_ABA_EXAUSTO'
                    resultado['duzias_envolvidas'] = [u[-1], u[-2], terceira]
                    return resultado
        
        if 0 in u[-4:]:
            idx_zero = len(u[-4:]) - 1 - u[-4:][::-1].index(0)
            antes = u[-4:][:idx_zero]
            depois = u[-4:][idx_zero+1:]
            
            if antes and depois:
                if depois[-1] != antes[-1] if antes else None:
                    resultado['quebra_prevista'] = depois[-1]
                    resultado['forca'] = 4
                    resultado['estado_atual'] = 'POS_ZERO'
                    resultado['duzias_envolvidas'] = [antes[-1] if antes else 0, depois[-1]]
                    return resultado
        
        return None
    
    def detectar_terceira_duzia_intrusa(self):
        if len(self.historico) < 8:
            return None
        
        u = list(self.historico)[-10:]
        freq = Counter([d for d in u if d != 0])
        
        if len(freq) < 2:
            return None
        
        ranking = freq.most_common()
        if len(ranking) < 2:
            return None
        
        dz1, count1 = ranking[0]
        dz2, count2 = ranking[1]
        
        terceira = self._get_terceira_duzia(dz1, dz2)
        if terceira is None:
            return None
        
        count_terceira = freq.get(terceira, 0)
        
        if (count1 + count2) >= 7 and count_terceira <= 1:
            forca = 3 + (8 - count_terceira) * 0.7
            forca = min(8, forca)
            
            if count_terceira == 0:
                forca += 2
            
            alt_d12 = self._contar_alternancias_entre(u, dz1, dz2)
            if alt_d12 >= 4:
                forca += 1.5
            
            return terceira, forca, dz1, dz2
        
        if count_terceira == 1 and (count1 + count2) >= 6:
            if terceira in u[-4:]:
                forca = 4
                return terceira, forca, dz1, dz2
        
        return None
    
    def detectar_retorno_aba(self):
        if len(self.historico) < 3:
            return None
        u = list(self.historico)[-3:]
        if u[0] == u[2] and u[0] != u[1] and u[0] != 0 and u[1] != 0:
            return u[0], 5
        return None
    
    def detectar_duas_dominantes(self):
        if len(self.historico) < 10:
            return None
        ultimos_10 = list(self.historico)[-10:]
        freq = Counter(ultimos_10)
        ranking = freq.most_common()
        if len(ranking) >= 2:
            top2_sum = ranking[0][1] + ranking[1][1]
            if top2_sum >= 8:
                return (ranking[0][0], ranking[1][0]), 3
        return None
    
    def detectar_progressao(self):
        if len(self.historico) < 4:
            return None
        u = list(self.historico)[-4:]
        if u[0] == u[1] and u[2] == u[3] and u[1] != u[2] and u[0] != 0 and u[2] != 0:
            return u[2], 4
        return None
    
    def detectar_streak_longo(self):
        streak_count, streak_d = self.streak()
        if streak_count >= 3 and streak_d != 0:
            forca = min(10, 4 + (streak_count - 3) * 2)
            return streak_d, forca
        return None
    
    def detectar_pos_zero(self):
        if len(self.historico) < 3:
            return None
        u = list(self.historico)[-3:]
        if u[-1] == 0 or u[-2] == 0:
            for d in reversed(u[:-1]):
                if d != 0:
                    return d, 5
        return None
    
    def detectar_vai_e_volta(self):
        u = list(self.historico)
        if len(u) >= 4 and u[-4] == u[-2] and u[-3] == u[-1] and u[-4] != u[-3] and u[-4] != 0 and u[-3] != 0:
            return u[-3], 6
        if len(u) >= 5 and u[-5] == u[-3] == u[-1] and u[-4] == u[-2] and u[-5] != u[-4] and u[-5] != 0 and u[-4] != 0:
            return u[-4], 8
        return None
    
    def detectar_repeticao_imediata(self):
        if len(self.historico) < 3:
            return None
        u = list(self.historico)[-3:]
        if u[0] != u[1] and u[1] == u[2] and u[1] != 0:
            return u[1], 6
        if len(self.historico) >= 2:
            u2 = list(self.historico)[-2:]
            if u2[0] == u2[1] and u2[0] != 0:
                return u2[0], 4
        return None
    
    def detectar_troca_entre_duas(self):
        if len(self.historico) < 6:
            return None
        u = list(self.historico)[-6:]
        pares = {}
        for i in range(1, len(u)):
            if u[i-1] != u[i] and u[i-1] != 0 and u[i] != 0:
                par = tuple(sorted([u[i-1], u[i]]))
                pares[par] = pares.get(par, 0) + 1
        if pares:
            par_principal = max(pares, key=pares.get)
            count = pares[par_principal]
            if count >= 3:
                dz1, dz2 = par_principal
                return dz2 if u[-1] == dz1 else dz1, 5
        return None
    
    def detectar_bloco_dominante(self):
        if len(self.historico) < 5:
            return None
        u = list(self.historico)[-5:]
        freq = Counter([d for d in u if d != 0])
        if freq:
            dz_dominante = freq.most_common(1)[0]
            if dz_dominante[1] >= 2:
                return dz_dominante[0], 5
        return None
    
    def detectar_ciclos(self):
        if len(self.historico) < 6:
            return None
        u = list(self.historico)
        if len(u) >= 4 and u[-4] == u[-2] and u[-3] == u[-1] and u[-4] != u[-3]:
            return u[-3]
        if len(u) >= 6 and u[-6:-3] == u[-3:]:
            return u[-6]
        return None
    
    def ausencia(self):
        aus = {1: 0, 2: 0, 3: 0}
        for d in reversed(self.historico):
            for dz in aus:
                if d != dz:
                    aus[dz] += 1
        dz = max(aus, key=aus.get)
        if aus[dz] >= 5:
            return dz, aus[dz]
        return None
    
    def terminais(self):
        if len(self.numeros_completos) < 10:
            return None
        nums = self.numeros_completos[-10:]
        terms = [n % 10 for n in nums if n != 0]
        top = [t[0] for t in Counter(terms).most_common(2)]
        score = {1: 0, 2: 0, 3: 0}
        for n in range(1, 37):
            dz = get_duzia(n)
            if n % 10 in top:
                score[dz] += 1
        best = max(score, key=score.get)
        if score[best] >= 3:
            return best, score[best]
        return None
    
    def detectar_zigzag_d1_d2(self):
        if len(self.historico) < 6:
            return None
        u = list(self.historico)[-6:]
        alternancias = 0
        for i in range(len(u)-1):
            if (u[i] == 1 and u[i+1] == 2) or (u[i] == 2 and u[i+1] == 1):
                alternancias += 1
        if alternancias >= 4:
            ultima = u[-1]
            return (2 if ultima == 1 else 1), 7
        if len(u) >= 4:
            u4 = u[-4:]
            alt4 = sum(1 for i in range(len(u4)-1) if (u4[i] == 1 and u4[i+1] == 2) or (u4[i] == 2 and u4[i+1] == 1))
            if alt4 >= 3:
                ultima = u4[-1]
                return (2 if ultima == 1 else 1), 5
        return None
    
    def detectar_bloco_d3(self):
        if len(self.historico) < 5:
            return None
        u = list(self.historico)[-5:]
        d3_count = u[-4:].count(3)
        if d3_count >= 2:
            return 3, 5
        if u[-1] == 3 and d3_count >= 1:
            return 3, 3
        return None
    
    def detectar_pos_zero_melhorado(self):
        if len(self.historico) < 4:
            return None
        u = list(self.historico)[-4:]
        for offset in [1, 2]:
            if len(u) > offset and u[-(offset+1)] == 0:
                if len(u) > offset + 1:
                    dz_anterior = u[-(offset+2)]
                    if dz_anterior != 0:
                        if u[-1] != 0 and u[-1] != dz_anterior:
                            return dz_anterior, 6
                        elif u[-1] == dz_anterior:
                            return dz_anterior, 4
        return None
    
    def detectar_mudanca_abrupta(self):
        if len(self.historico) < 8:
            return None
        u = list(self.historico)
        janela_antiga = u[-8:-4]
        janela_recente = u[-4:]
        freq_antiga = Counter([d for d in janela_antiga if d != 0])
        freq_recente = Counter([d for d in janela_recente if d != 0])
        if not freq_antiga or not freq_recente:
            return None
        dom_antiga = freq_antiga.most_common(1)[0]
        dom_recente = freq_recente.most_common(1)[0]
        if dom_antiga[0] != dom_recente[0]:
            if dom_recente[1] >= 2:
                diff = dom_recente[1] - dom_antiga[1]
                forca = min(8, 4 + abs(diff))
                return dom_recente[0], forca, dom_antiga[0]
        return None
    
    def detectar_regime(self):
        freq = self.frequencia()
        total = sum(freq.values())
        if total == 0:
            return "NEUTRO"
        razao = max(freq.values()) / total
        if razao > 0.5:
            return "DOMINANTE"
        elif razao > 0.4:
            return "TENDENCIA"
        elif len([d for d in freq if freq[d] > 0]) == 3:
            return "DISTRIBUIDO"
        else:
            return "TRANSICAO"
    
    # ========== CÁLCULO DE SCORE PRINCIPAL ==========
    
    def calcular_score(self):
        score = {1: 0, 2: 0, 3: 0}
        detalhes = {1: [], 2: [], 3: []}
        
        freq = self.frequencia_ponderada()
        freq_normal = self.frequencia()
        streak_count, streak_d = self.streak()
        trans = self.transicao()
        prob = self.matriz_transicao()
        regime = self.detectar_regime()
        
        for d in score:
            score[d] += freq[d] * 0.8
        
        total_normal = sum(freq_normal.values())
        if total_normal > 0:
            for d in score:
                score[d] += (freq_normal[d] / total_normal) * 10
        
        if streak_d and streak_d != 0:
            multiplicador = 3.0 if regime == "DOMINANTE" else 2.0 if regime == "TENDENCIA" else 1.5
            score[streak_d] += streak_count * multiplicador
        
        if trans and regime not in ["DOMINANTE", "TENDENCIA"]:
            ant, _ = trans
            if ant != 0:
                score[ant] += 2.5
        
        if streak_count >= 3 and streak_d and streak_d != 0:
            outras = self._get_outras_duzias(streak_d)
            for d in outras:
                score[d] += 5
        
        if self.historico:
            ultima = self.historico[-1]
            if ultima != 0 and ultima in prob:
                for d in score:
                    p = prob[ultima][d]
                    if p > 40:
                        score[d] += (p - 30) / 8
        
        # SEQUÊNCIA DE DERROTAS
        if len(self.ultimos_resultados) >= 3:
            ultimos_3_real = [r['duzia'] for r in self.ultimos_resultados[-3:]]
            ultimos_3_acerto = [r['acertou'] for r in self.ultimos_resultados[-3:]]
            
            if len(set(ultimos_3_real)) == 1 and ultimos_3_acerto.count(False) >= 2:
                dz_real = ultimos_3_real[0]
                if dz_real != 0:
                    score[dz_real] += 12
                    detalhes[dz_real].append(f"🚨 Sequência Derrotas: +12")
                    outras = self._get_outras_duzias(dz_real)
                    for d in outras:
                        score[d] *= 0.2
                        detalhes[d].append(f"⚠️ Bloqueio Total: -80%")
        
        # GATILHOS
        exaustao = self.detectar_exaustao_ciclo_dominante()
        if exaustao:
            dz_quebra = exaustao['dz_quebra']
            dz_exaurida = exaustao['dz_exaurida']
            forca_base = exaustao['forca']
            forca = self.get_peso_adaptativo('exaustao_ciclo', forca_base * 1.5)
            
            score[dz_quebra] += forca
            detalhes[dz_quebra].append(f"🎯 GATILHO: {exaustao['descricao']} (+{forca:.1f})")
            
            score[dz_exaurida] *= 0.3
            detalhes[dz_exaurida].append(f"⚠️ CICLO EXAURIDO: -70% (D{dz_exaurida})")
        
        # DETECTORES UNIVERSAIS
        quebra_estados = self.detectar_quebra_estados()
        if quebra_estados:
            dz = quebra_estados['quebra_prevista']
            forca_base = quebra_estados['forca'] * 1.4
            forca = self.get_peso_adaptativo('quebra_estados', forca_base)
            estado = quebra_estados['estado_atual']
            envolvidas = quebra_estados['duzias_envolvidas']
            
            if dz == 0:
                for d in score:
                    penalidade = forca * 0.3
                    score[d] -= penalidade
                    detalhes[d].append(f"⚠️ Risco Zero ({estado}): -{penalidade:.1f}")
            elif dz != 0:
                score[dz] += forca
                detalhes[dz].append(f"⚡ Quebra Estado ({estado}): +{forca:.1f}")
                for d in envolvidas:
                    if d != dz and d in score and d != 0:
                        penalidade = forca * 0.4
                        score[d] -= penalidade
                        detalhes[d].append(f"⚠️ Fim Padrão: -{penalidade:.1f}")
        
        intrusa = self.detectar_terceira_duzia_intrusa()
        if intrusa:
            dz_terceira, forca_intrusa_base, dz_dom1, dz_dom2 = intrusa
            forca_intrusa = self.get_peso_adaptativo('terceira_intrusa', forca_intrusa_base * 1.3)
            if dz_terceira != 0:
                score[dz_terceira] += forca_intrusa
                detalhes[dz_terceira].append(f"👻 Dúzia Intrusa: +{forca_intrusa:.1f}")
                for d in [dz_dom1, dz_dom2]:
                    if d in score:
                        score[d] -= forca_intrusa * 0.5
                        detalhes[d].append(f"⚠️ Saturação: -{forca_intrusa*0.5:.1f}")
        
        mudanca = self.detectar_mudanca_abrupta()
        if mudanca:
            dz_nova, forca_base, dz_antiga = mudanca
            forca = self.get_peso_adaptativo('mudanca_abrupta', forca_base * 1.2)
            if dz_nova != 0:
                score[dz_nova] += forca
                detalhes[dz_nova].append(f"🔄 Mudança Abrupta: +{forca:.1f}")
                if dz_antiga in score:
                    score[dz_antiga] -= forca * 1.5
                    detalhes[dz_antiga].append(f"⚠️ Perdeu Domínio: -{forca*1.5:.1f}")
        
        rep = self.detectar_repeticao_imediata()
        if rep:
            dz, forca_base = rep
            forca = self.get_peso_adaptativo('repeticao_imediata', forca_base)
            if dz != 0:
                score[dz] += forca
                detalhes[dz].append(f"Repetição: +{forca:.1f}")
        
        sl = self.detectar_streak_longo()
        if sl:
            dz, forca_base = sl
            forca = self.get_peso_adaptativo('streak_longo', forca_base)
            if dz != 0:
                score[dz] += forca
                detalhes[dz].append(f"Streak Longo: +{forca:.1f}")
        
        pz = self.detectar_pos_zero()
        if pz:
            dz, forca_base = pz
            forca = self.get_peso_adaptativo('pos_zero', forca_base)
            if dz != 0:
                score[dz] += forca
                detalhes[dz].append(f"Pós-Zero: +{forca:.1f}")
        
        vv = self.detectar_vai_e_volta()
        if vv:
            dz, forca_base = vv
            forca = self.get_peso_adaptativo('vai_e_volta', forca_base)
            if dz != 0:
                score[dz] += forca
                detalhes[dz].append(f"Vai-e-Volta: +{forca:.1f}")
        
        aba = self.detectar_retorno_aba()
        if aba:
            dz, forca_base = aba
            forca = self.get_peso_adaptativo('retorno_aba', forca_base)
            if dz != 0:
                score[dz] += forca
                detalhes[dz].append(f"Retorno ABA: +{forca:.1f}")
        
        duas = self.detectar_duas_dominantes()
        if duas:
            dominantes, forca_base = duas
            forca = self.get_peso_adaptativo('duas_dominantes', forca_base)
            for dz in dominantes:
                if dz != 0:
                    score[dz] += forca
                    detalhes[dz].append(f"Dominante: +{forca:.1f}")
            terceira = [d for d in [1,2,3] if d not in dominantes]
            for dz in terceira:
                score[dz] -= 2
                detalhes[dz].append(f"Desfavorecida: -2")
        
        prog = self.detectar_progressao()
        if prog:
            dz, forca_base = prog
            forca = self.get_peso_adaptativo('progressao', forca_base)
            if dz != 0:
                score[dz] += forca
                detalhes[dz].append(f"Progressão: +{forca:.1f}")
        
        troca = self.detectar_troca_entre_duas()
        if troca:
            dz, forca_base = troca
            forca = self.get_peso_adaptativo('troca_duas', forca_base)
            if dz != 0:
                score[dz] += forca
                detalhes[dz].append(f"Troca Duas: +{forca:.1f}")
        
        bloco = self.detectar_bloco_dominante()
        if bloco:
            dz, forca_base = bloco
            forca = self.get_peso_adaptativo('bloco_dominante', forca_base)
            if dz != 0:
                score[dz] += forca
                detalhes[dz].append(f"Bloco Dominante: +{forca:.1f}")
        
        zigzag = self.detectar_zigzag_d1_d2()
        if zigzag:
            dz, forca_base = zigzag
            forca = self.get_peso_adaptativo('zigzag_d1_d2', forca_base * 0.6)
            if dz != 0:
                score[dz] += forca
                detalhes[dz].append(f"🔷 Zig-Zag D1↔D2: +{forca:.1f}")
        
        bloco_d3 = self.detectar_bloco_d3()
        if bloco_d3:
            dz, forca_base = bloco_d3
            forca = self.get_peso_adaptativo('bloco_d3', forca_base * 0.6)
            if dz != 0:
                score[dz] += forca
                detalhes[dz].append(f"🔷 Bloco D3: +{forca:.1f}")
        
        pos_zero_m = self.detectar_pos_zero_melhorado()
        if pos_zero_m:
            dz, forca_base = pos_zero_m
            forca = self.get_peso_adaptativo('pos_zero_plus', forca_base * 0.6)
            if dz != 0:
                score[dz] += forca
                detalhes[dz].append(f"🔷 Pós-Zero+: +{forca:.1f}")
        
        # INÉRCIA ADAPTATIVA
        tem_quebra = False
        for dz in detalhes:
            for det in detalhes[dz]:
                if 'Quebra Estado' in det or 'Fim Padrão' in det or 'Mudança Abrupta' in det or 'Perdeu Domínio' in det or 'Dúzia Intrusa' in det or 'Sequência Derrotas' in det or 'GATILHO' in det or 'CICLO EXAURIDO' in det:
                    tem_quebra = True
                    break
        
        if tem_quebra:
            streak_count, streak_d = self.streak()
            if streak_d and streak_d != 0:
                fator_reducao = 0.3 + (streak_count * 0.12)
                fator_reducao = min(0.75, fator_reducao)
                score[streak_d] *= (1 - fator_reducao)
                detalhes[streak_d].append(f"🔄 Inércia Adaptativa: -{fator_reducao*100:.0f}%")
        
        if len(self.ultimas_previsoes) >= 3:
            ultimas_5 = self.ultimas_previsoes[-5:]
            if len(set(ultimas_5)) == 1 and len(ultimas_5) >= 3:
                dz_viciada = ultimas_5[0]
                fator_penalizacao = 0.4 + (len(ultimas_5) - 3) * 0.2
                fator_penalizacao = min(0.90, fator_penalizacao)
                erros_recentes = sum(1 for r in self.ultimos_resultados[-3:] if not r['acertou'])
                if erros_recentes >= 2:
                    fator_penalizacao = min(0.95, fator_penalizacao + 0.1)
                score[dz_viciada] *= (1 - fator_penalizacao)
                detalhes[dz_viciada].append(f"⚠️ Anti-Viés Previsão: -{fator_penalizacao*100:.0f}%")
                outras = self._get_outras_duzias(dz_viciada)
                for d in outras:
                    bonus = 1 + (fator_penalizacao * 0.6)
                    score[d] *= bonus
                    detalhes[d].append(f"🔄 Anti-Viés: +{(bonus-1)*100:.0f}%")
        
        ciclo = self.detectar_ciclos()
        if ciclo and ciclo != 0 and max(score.values()) > 3:
            score[ciclo] += 5
            detalhes[ciclo].append(f"Ciclo: +5")
        
        aus = self.ausencia()
        if aus:
            dz, g = aus
            if dz != 0:
                score[dz] += min(5, g * 0.5)
                detalhes[dz].append(f"Ausência: +{min(5, g * 0.5):.1f}")
        
        term = self.terminais()
        if term:
            dz, q = term
            if dz != 0:
                score[dz] += q * 0.3
                detalhes[dz].append(f"Terminais: +{q*0.3:.1f}")
        
        total = sum(score.values())
        if total > 0:
            for d in score:
                score[d] = (score[d] / total) * 100
        
        return score, regime, detalhes
    
    def prever(self, confianca_minima=3.2, agressividade=2):
        score, regime, detalhes = self.calcular_score()
        ranking = sorted(score.items(), key=lambda x: x[1], reverse=True)
        d1, s1 = ranking[0]
        d2, s2 = ranking[1]
        
        ratio = s1 / max(1, s2)
        vol = np.std(list(score.values()))
        confianca = (ratio * 2.2) + (1.5 / (1 + vol))
        
        confianca_ajustada = confianca_minima - (0.4 * (2 - agressividade))
        
        forca_detectores = 0
        detectores_ativos = []
        for dz in detalhes:
            for det in detalhes[dz]:
                if '+' in det:
                    try:
                        forca = float(det.split('+')[1].strip().split()[0])
                        forca_detectores += forca
                        detector_nome = det.split('(')[0].strip()
                        if detector_nome not in detectores_ativos:
                            detectores_ativos.append(detector_nome)
                    except:
                        pass
        
        if self.ultimo_gatilho:
            detectores_ativos.insert(0, f"GATILHO:{self.ultimo_gatilho}")
        if self.sinal_mudanca_pendente:
            detectores_ativos.insert(0, "SINAL_PENDENTE")
        if self.streak_ativo:
            detectores_ativos.insert(0, f"STREAK:D{self.streak_ativo}")
        
        streak_count, _ = self.streak()
        tem_streak_longo = streak_count >= 3
        tem_duas_dominantes = self.detectar_duas_dominantes() is not None
        tem_gatilho_quebra = self.ultimo_gatilho is not None
        
        pode_entrar = False
        motivo = ""
        
        if self.sinal_mudanca_pendente:
            pode_entrar = False
            motivo = f"⏳ Aguardando confirmação: {self.sinal_mudanca_pendente['descricao']}"
        elif tem_gatilho_quebra:
            pode_entrar = True
            confianca = max(2.0, confianca * 0.7)
        elif regime == "DISTRIBUIDO" and not tem_streak_longo and forca_detectores < 5 and not tem_duas_dominantes:
            motivo = "Mercado distribuído sem padrão claro"
        elif regime == "DISTRIBUIDO" and (tem_streak_longo or tem_duas_dominantes) and confianca < 2.0:
            motivo = f"Distribuído com padrão fraco (confiança {confianca:.2f})"
        elif confianca < confianca_ajustada and not tem_streak_longo and forca_detectores < 5:
            motivo = f"Confiança baixa ({confianca:.2f} < {confianca_ajustada})"
        elif regime == "TRANSICAO" and confianca < 2.8 and not tem_streak_longo and not tem_duas_dominantes:
            motivo = f"Transição sem padrão (confiança {confianca:.2f})"
        else:
            pode_entrar = True
        
        previsao = {
            "entrar": pode_entrar,
            "motivo": motivo if not pode_entrar else "",
            "score": score,
            "regime": regime,
            "confianca": round(confianca, 2),
            "duzia": d1,
            "duzia_secundaria": d2,
            "detalhes": detalhes,
            "detectores_ativos": detectores_ativos,
            "gatilho_ativo": self.ultimo_gatilho
        }
        
        if pode_entrar:
            previsao = self.balancear_previsoes(previsao)
        
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
            logging.error(f"Número inválido: {nr}")
            return
        
        self.numero_rodada += 1
        
        self.duzia_ai.adicionar(nr)
        self.historico_numeros.append(nr)
        self.ultimo_numero = nr
        
        if self.entrada_ativa:
            duzia_real = get_duzia(nr)
            duzia_prevista = self.entrada_ativa.get('duzia_prevista')
            duzia_sec_prevista = self.entrada_ativa.get('duzia_sec_prevista')
            
            acerto_primaria = (duzia_real == duzia_prevista) if duzia_prevista and nr != 0 else False
            acerto_secundaria = (duzia_real == duzia_sec_prevista) if duzia_sec_prevista and nr != 0 else False
            
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
            
            detectores_ativos = self.entrada_ativa.get('detectores_ativos', [])
            for detector in detectores_ativos:
                self.duzia_ai.registrar_performance_detector(detector, acerto_primaria or acerto_secundaria)
            
            entrada_info = {
                'rodada': self.numero_rodada,
                'hora': datetime.now().strftime('%H:%M:%S'),
                'numero': nr,
                'duzia_real': duzia_real if nr != 0 else 0,
                'duzia_prevista': duzia_prevista,
                'duzia_sec_prevista': duzia_sec_prevista,
                'acerto_primaria': acerto_primaria,
                'acerto_secundaria': acerto_secundaria,
                'confianca': self.entrada_ativa.get('confianca', 0),
                'regime': self.entrada_ativa.get('regime', 'NEUTRO'),
                'detectores_ativos': detectores_ativos,
                'modo': 'Agressivo' if st.session_state.get('modo_agressivo', False) else 'Conservador',
                'gatilho': self.entrada_ativa.get('gatilho_ativo', None)
            }
            self.historico_entradas.append(entrada_info)
            if len(self.historico_entradas) > 50:
                self.historico_entradas = self.historico_entradas[-50:]
            
            enviar_resultado_auto(nr, acerto_primaria or acerto_secundaria)
            self.entrada_ativa = None
        
        confianca_minima = st.session_state.get('confianca_minima', 3.2)
        agressividade = st.session_state.get('agressividade', 2)
        previsao = self.duzia_ai.prever(confianca_minima=confianca_minima, agressividade=agressividade)
        
        if previsao['entrar']:
            duzia_map = {
                1: list(range(1, 13)),
                2: list(range(13, 25)),
                3: list(range(25, 37))
            }
            
            numeros_principais = duzia_map.get(previsao['duzia'], [])
            numeros_secundarios = duzia_map.get(previsao.get('duzia_secundaria', previsao['duzia']), [])
            
            if st.session_state.get('modo_agressivo', False) and previsao.get('duzia_secundaria'):
                numeros_apostar = list(set(numeros_principais + numeros_secundarios))
            else:
                numeros_apostar = numeros_principais
            
            self.entrada_ativa = {
                'numeros_apostar': numeros_apostar,
                'duzia_prevista': previsao['duzia'],
                'duzia_sec_prevista': previsao.get('duzia_secundaria'),
                'confianca': previsao.get('confianca', 0),
                'regime': previsao.get('regime', 'NEUTRO'),
                'score': previsao.get('score', {}),
                'detalhes': previsao.get('detalhes', {}),
                'detectores_ativos': previsao.get('detectores_ativos', []),
                'gatilho_ativo': previsao.get('gatilho_ativo', None)
            }
            
            self.duzia_ai.registrar_previsao(previsao['duzia'])
            
            idx_atual = len(self.historico_numeros) - 1
            self.sinais_grafico.append((idx_atual, previsao['duzia']))
            self.duzia_ai.sinais_entrada.append((idx_atual, previsao['duzia']))
            
            enviar_previsao_auto({
                'numeros_apostar': numeros_apostar
            })
    
    def zerar(self):
        self.acertos = 0
        self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear()
        self.entrada_ativa = None
        self.ultimo_numero = None
        self.sinais_grafico = []
        self.numero_rodada = 0
        janela = st.session_state.get('janela_duzia_ai', 30)
        self.duzia_ai = DuziaAI(window=janela)
        st.session_state.acertos_duzia = 0
        st.session_state.erros_duzia = 0
        st.session_state.acertos_duzia_sec = 0
        st.session_state.erros_duzia_sec = 0
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
                if m is not None:
                    lm[n] = m
        return {"number": nm, "timestamp": ts, "luckyNumbers": ln, "luckyMultipliers": lm}
    except Exception as e:
        logging.warning(f"Erro ao buscar API: {e}")
        return None

def exportar_historico_csv(historico_entradas, caminho="export_roleta.csv"):
    """Exporta histórico de entradas para CSV sem BOM"""
    import csv
    try:
        with open(caminho, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Rodada', 'Hora', 'Número', 'Dúzia Real', 'Dúzia Prevista', 
                           'Confiança', 'Gatilho', 'Resultado'])
            
            for entrada in historico_entradas:
                resultado = '✅' if entrada.get('acerto_primaria') else '🟡' if entrada.get('acerto_secundaria') else '❌'
                duzia_real = f"D{entrada.get('duzia_real', 0)}" if entrada.get('duzia_real', 0) != 0 else "-"
                gatilho = entrada.get('gatilho', '') if entrada.get('gatilho') else "-"
                
                writer.writerow([
                    entrada.get('rodada', '-'),
                    entrada.get('hora', '-'),
                    entrada.get('numero', '-'),
                    duzia_real,
                    f"D{entrada.get('duzia_prevista', '?')}",
                    f"{entrada.get('confianca', 0):.2f}",
                    gatilho,
                    resultado
                ])
        logging.info(f"CSV exportado com sucesso para {caminho}")
        return True
    except Exception as e:
        logging.error(f"Erro ao exportar CSV: {e}")
        return False

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎰 DuziaAI V6.5 MELHORADA", layout="wide")
st.title("🎰 DuziaAI V6.5 MELHORADA - Anti-Teimosia + SEQUENCIA_ERROS")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    sis = st.session_state.sistema
    numeros = dados.get('historico_numeros', [])
    sis.numero_rodada = dados.get('numero_rodada', len(numeros))
    for n in numeros:
        sis.duzia_ai.adicionar(n)
        sis.historico_numeros.append(n)
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
            with open(ENTRADAS_PATH, 'r') as f:
                sis.historico_entradas = json.load(f)
        except:
            pass

defaults = {
    'modo_automatico': True,
    'modo_agressivo': False,
    'janela_duzia_ai': 30,
    'confianca_minima': 3.2,
    'agressividade': 2,
    'acertos_duzia': 0,
    'erros_duzia': 0,
    'acertos_duzia_sec': 0,
    'erros_duzia_sec': 0,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "historico" not in st.session_state:
    st.session_state.historico = []
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                st.session_state.historico = json.load(f)
        except:
            pass

if "telegram_token" not in st.session_state:
    st.session_state.telegram_token = ""
if "telegram_chat_id" not in st.session_state:
    st.session_state.telegram_chat_id = ""

# Sidebar
with st.sidebar:
    st.markdown("## ⚙️ Configurações")
    st.session_state.janela_duzia_ai = st.slider("📏 Janela de Análise", 10, 50, st.session_state.janela_duzia_ai, 5)
    st.session_state.confianca_minima = st.slider("🎯 Confiança Mínima", 2.0, 5.0, st.session_state.confianca_minima, 0.2)
    st.session_state.agressividade = st.select_slider("🎚️ Agressividade", options=[1,2,3], value=st.session_state.agressividade)
    st.session_state.modo_agressivo = st.checkbox("🔥 Modo Agressivo (2 Dúzias)", value=st.session_state.modo_agressivo)
    st.session_state.modo_automatico = st.checkbox("🤖 Modo Automático", value=st.session_state.modo_automatico)
    st.markdown("---")
    st.markdown("### 📊 V6.5 MELHORADA")
    st.caption("🔄 STREAK 2x ABSOLUTO: Segue fluxo")
    st.caption("🔄 STREAK 3x: Reforço")
    st.caption("🚪 SAÍDA: Streak quebrou")
    st.caption("🎯 SEQUENCIA_ERROS: 2 erros + Tendência")
    st.caption("🎯 EXAUSTAO_DOMINANCIA: 7+/10")
    st.caption("🎯 QUEBRA_POS_ZERO")
    st.caption("🎯 MUDANCA_VELOCIDADE: Confirmada")
    st.markdown("---")
    with st.expander("🔔 Telegram", expanded=False):
        st.session_state.telegram_token = st.text_input("Token", value=st.session_state.telegram_token, type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID", value=st.session_state.telegram_chat_id)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💾 Salvar", use_container_width=True):
            salvar_resultado_em_arquivo(st.session_state.historico)
            salvar_sessao()
            st.success("✅ Salvo!")
    with col2:
        if st.button("🗑️ Zerar", use_container_width=True):
            st.session_state.sistema.zerar()
            st.rerun()
    with col3:
        if st.button("📥 CSV", use_container_width=True):
            if exportar_historico_csv(st.session_state.sistema.historico_entradas):
                st.success("✅ CSV exportado!")

# Conteúdo principal
st.subheader("🎲 Inserir Números")
c1, c2, c3 = st.columns([3,1,1])
with c1:
    entrada = st.text_input("Número (0-36):", placeholder="Digite o número sorteado e pressione Enter", key="entrada_numero")
with c2:
    if st.button("🎯 Enviar", use_container_width=True, type="primary"):
        if validar_numero(entrada):
            nr = int(entrada)
            item = {"number": nr, "timestamp": datetime.now().isoformat(), "luckyNumbers": [], "luckyMultipliers": {}}
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
ac_dz = st.session_state.get('acertos_duzia', 0)
er_dz = st.session_state.get('erros_duzia', 0)
total_dz = ac_dz + er_dz
tx_dz = (ac_dz / total_dz * 100) if total_dz > 0 else 0
col1.metric("✅ Acertos", int(sis.acertos))
col2.metric("❌ Erros", int(sis.erros))
col3.metric("📊 Win Rate", f"{tx_acerto:.1f}%")
col4.metric("🎯 Tx Primária", f"{tx_dz:.1f}%")
col5.metric("📦 Entradas", total_entradas)
col6.metric("🔢 Rodada", sis.numero_rodada)
col7.metric("🔄 Streak", f"D{sis.duzia_ai.streak_ativo}" if sis.duzia_ai.streak_ativo else "-")

st.markdown("---")
col_grafico, col_entrada = st.columns([3,2])

with col_grafico:
    st.subheader("📈 Análise em Tempo Real")
    if len(sis.historico_numeros) >= 5:
        score, regime, detalhes = sis.duzia_ai.calcular_score()
        fig = plt.Figure(data=[plt.Bar(
            x=['D1 (1-12)', 'D2 (13-24)', 'D3 (25-36)'],
            y=[score[1], score[2], score[3]],
            marker_color=['#FF6B6B' if score[1] == max(score.values()) else '#4ECDC4',
                          '#FF6B6B' if score[2] == max(score.values()) else '#4ECDC4',
                          '#FF6B6B' if score[3] == max(score.values()) else '#4ECDC4'],
            text=[f'{score[1]:.1f}', f'{score[2]:.1f}', f'{score[3]:.1f}'],
            textposition='auto'
        )])
        fig.update_layout(title=f"🎯 Scores das Dúzias | Regime: {regime}", yaxis_title="Score Normalizado", height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("**🔍 Detectores Ativos:**")
        for dz in [1,2,3]:
            if detalhes.get(dz):
                st.caption(f"D{dz}: " + " | ".join(detalhes[dz]))
        
        if sis.duzia_ai.sinal_mudanca_pendente:
            st.warning(f"⏳ Sinal Pendente: {sis.duzia_ai.sinal_mudanca_pendente['descricao']}")
        if sis.duzia_ai.streak_ativo:
            st.info(f"🔄 Streak Ativo: D{sis.duzia_ai.streak_ativo}")
        
        if len(sis.historico_numeros) >= 10:
            ultimos_20 = list(sis.historico_numeros)[-20:]
            duzias_hist = [get_duzia(n) for n in ultimos_20]
            x_vals = list(range(len(duzias_hist)))
            fig2 = plt.Figure()
            fig2.add_trace(plt.Scatter(x=x_vals, y=duzias_hist, mode='lines+markers', name='Dúzia', line=dict(color='#FFD700', width=2), marker=dict(size=8)))
            if sis.sinais_grafico:
                sinal_x, sinal_y, sinal_text = [], [], []
                offset = len(duzias_hist) - 20
                for idx, dz in sis.sinais_grafico:
                    pos = idx - offset
                    if 0 <= pos < 20:
                        sinal_x.append(pos)
                        sinal_y.append(dz)
                        sinal_text.append(f"Entrada D{dz}")
                if sinal_x:
                    fig2.add_trace(plt.Scatter(x=sinal_x, y=sinal_y, mode='markers', name='Sinal', marker=dict(symbol='star', size=15, color='red', line=dict(width=2, color='darkred')), text=sinal_text, hoverinfo='text'))
            fig2.update_layout(title="📉 Histórico de Dúzias c/ Sinais", yaxis=dict(tickvals=[1,2,3], ticktext=['D1','D2','D3'], range=[0.5,3.5]), height=300, showlegend=True)
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info(f"⏳ Aguardando dados... ({len(sis.historico_numeros)}/5 giros)")

with col_entrada:
    st.subheader("🎰 Entrada Atual")
    if sis.duzia_ai.sinal_mudanca_pendente:
        sinal = sis.duzia_ai.sinal_mudanca_pendente
        st.warning(f"⏳ AGUARDANDO CONFIRMAÇÃO\n\n{sinal['descricao']}\n\nPróxima rodada confirmará ou cancelará.")
    elif sis.entrada_ativa:
        ent = sis.entrada_ativa
        confianca = ent.get('confianca', 0)
        duzia_prevista = ent.get('duzia_prevista', 0)
        duzia_sec_prevista = ent.get('duzia_sec_prevista')
        regime = ent.get('regime', 'NEUTRO')
        numeros_apostar = ent.get('numeros_apostar', [])
        detalhes_entrada = ent.get('detalhes', {})
        detectores = ent.get('detectores_ativos', [])
        gatilho = ent.get('gatilho_ativo', None)
        
        cor = "#FF6347" if gatilho else "#00CC00" if confianca >= 5 else "#FFA500" if confianca >= 3.5 else "#FF4444"
        limite = "1-12" if duzia_prevista == 1 else "13-24" if duzia_prevista == 2 else "25-36" if duzia_prevista == 3 else "?"
        
        if gatilho:
            st.markdown(f"""
            <div style="background-color: #FF634722; border: 2px solid #FF6347; border-radius: 15px; padding: 20px; margin: 10px 0;">
                <h2 style="color: #FF6347; text-align: center;">🎯 GATILHO ATIVO!</h2>
                <h3 style="text-align: center;">D{duzia_prevista} ({limite})</h3>
                <p style="text-align: center; font-size: 1.2em;">Confiança: {confianca:.2f} | Regime: {regime}</p>
                <p style="text-align: center; color: #FF6347;">⚠️ Gatilho: {gatilho}</p>
                {f'<p style="text-align: center; color: #FFA500;">🛡️ Cobertura: D{duzia_sec_prevista}</p>' if st.session_state.modo_agressivo and duzia_sec_prevista else ''}
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background-color: {cor}22; border: 2px solid {cor}; border-radius: 15px; padding: 20px; margin: 10px 0;">
                <h2 style="color: {cor}; text-align: center;">🎯 D{duzia_prevista} ({limite})</h2>
                <p style="text-align: center; font-size: 1.2em;">Confiança: {confianca:.2f} | Regime: {regime}</p>
                {f'<p style="text-align: center; color: #FFA500;">🛡️ Cobertura: D{duzia_sec_prevista}</p>' if st.session_state.modo_agressivo and duzia_sec_prevista else ''}
            </div>""", unsafe_allow_html=True)
        
        if detalhes_entrada.get(duzia_prevista):
            st.caption("🔍 " + " | ".join(detalhes_entrada[duzia_prevista]))
        if detectores:
            st.caption(f"🎯 Detectores: {', '.join(detectores)}")
        if numeros_apostar:
            st.write("**🎲 Números:**")
            cols = st.columns(6)
            for i, n in enumerate(sorted(numeros_apostar)):
                cols[i % 6].button(str(n), key=f"num_{n}", use_container_width=True)
        else:
            st.warning("Nenhum número disponível.")
        valor_progresso = min(1.0, max(0.0, confianca / 10.0))
        st.progress(valor_progresso)
    else:
        st.info("🔍 Analisando padrões...")
        if len(sis.historico_numeros) >= 5:
            previsao = sis.duzia_ai.prever()
            if previsao and not previsao.get('entrar', False):
                st.warning(f"⚠️ {previsao.get('motivo', 'Sem sinal claro')}")
                st.caption(f"Regime: {previsao.get('regime', '?')} | Confiança: {previsao.get('confianca', 0)}")
    if sis.ultimo_numero is not None:
        st.markdown("---")
        st.write(f"**🔄 Último Giro:** #{sis.ultimo_numero} → D{get_duzia(sis.ultimo_numero)}")

st.markdown("---")
st.subheader("📝 Histórico de Entradas")
if sis.historico_entradas:
    dados_tabela = []
    for e in reversed(sis.historico_entradas[-20:]):
        duzia_real_str = f"D{e.get('duzia_real', '?')}" if e.get('duzia_real', 0) != 0 else "-"
        gatilho_str = e.get('gatilho', '') if e.get('gatilho') else "-"
        
        dados_tabela.append({
            "Rodada": e.get('rodada', '-'),
            "Hora": e.get('hora', '-'),
            "Número": e.get('numero', '-'),
            "Dúzia Real": duzia_real_str,
            "Dúzia Prevista": f"D{e.get('duzia_prevista', '?')}" if e.get('duzia_prevista') else "-",
            "Confiança": f"{e.get('confianca', 0):.2f}",
            "Gatilho": gatilho_str,
            "Resultado": "✅" if e.get('acerto_primaria') else "🟡" if e.get('acerto_secundaria') else "❌"
        })
    st.dataframe(dados_tabela, use_container_width=True, height=300)
    
    if st.button("📥 Exportar Histórico CSV", use_container_width=True):
        if exportar_historico_csv(sis.historico_entradas):
            st.success("✅ Histórico exportado como 'export_roleta.csv'")
else:
    st.info("Nenhuma entrada registrada ainda.")

st.markdown("---")
st.caption(f"🤖 DuziaAI V6.5 MELHORADA | Anti-Teimosia 2x + SEQUENCIA_ERROS com Tendência | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
salvar_sessao()
