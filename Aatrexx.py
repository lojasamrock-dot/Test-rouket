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
            'confianca_minima': st.session_state.get('confianca_minima', 2.5),
            'agressividade': st.session_state.get('agressividade', 2),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'meta_modelo_ativo': st.session_state.get('meta_modelo_ativo', True),
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
        prefixo = "💎 " if previsao.get('elite', False) else "🎯 "
        if duzia1_numeros and duzia2_numeros:
            mensagem = f"{prefixo}Entrada: D1 (1-12) | Cob: D2 (13-24)"
        elif duzia1_numeros and duzia3_numeros:
            mensagem = f"{prefixo}Entrada: D1 (1-12) | Cob: D3 (25-36)"
        elif duzia2_numeros and duzia3_numeros:
            mensagem = f"{prefixo}Entrada: D2 (13-24) | Cob: D3 (25-36)"
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
    try:
        num = int(valor)
        return 0 <= num <= 36
    except (ValueError, TypeError):
        return False

# =============================
# 🧠 META-MODELO V9.1.1 - COMITÊ + FILTROS ELITE (CORRIGIDO)
# =============================
class MetaModelo:
    """
    Comitê de 3 especialistas + Filtros de Elite (bônus, não veto).
    V9.1.1: Corrigido para evitar KeyError com detectores que retornam dict.
    """
    def __init__(self):
        self.historico_votacoes = []
        self.performance_especialistas = {
            'Tendência': {'acertos': 0, 'erros': 0},
            'Quebra': {'acertos': 0, 'erros': 0},
            'Qualidade': {'acertos': 0, 'erros': 0},
            'Elite': {'acertos': 0, 'erros': 0}
        }
        self.ultima_decisao = None
    
    def analisar_filtros_elite(self, duzia_ai):
        """V9.1 - Filtros Elite calibrados (mais flexíveis)"""
        detalhes = {}
        bonus = 0
        
        # 1. FILTRO PÓS-ZERO (Lockout de 2 rodadas)
        if len(duzia_ai.numeros_completos) >= 2:
            ultimos_2 = duzia_ai.numeros_completos[-2:]
            if 0 in ultimos_2:
                return False, "🚫 Pós-Zero: Aguardando estabilização (2 rodadas)", detalhes, 0
        
        # 2. IVD (threshold 0.7)
        if len(duzia_ai.historico_duzias) >= 10:
            ultimas_10 = list(duzia_ai.historico_duzias)[-10:]
            ultimas_10_filtrado = [d for d in ultimas_10 if d != 0]
            if len(ultimas_10_filtrado) >= 8:
                trocas = sum(1 for i in range(1, len(ultimas_10_filtrado)) if ultimas_10_filtrado[i] != ultimas_10_filtrado[i-1])
                ivd = trocas / max(1, len(ultimas_10_filtrado) - 1)
                detalhes['ivd'] = round(ivd, 2)
                if ivd > 0.7:
                    return False, f"🌪️ Volatilidade Alta (IVD: {ivd:.2f})", detalhes, 0
                elif ivd < 0.4:
                    bonus += 1
        
        # 3. TERMINAIS (2+ aparições)
        if len(duzia_ai.numeros_completos) >= 15:
            terminais = [n % 10 for n in duzia_ai.numeros_completos[-15:] if n != 0]
            if terminais:
                contagem = Counter(terminais)
                quentes = [t for t, f in contagem.items() if f >= 2]
                detalhes['quentes'] = quentes
                detalhes['contagem'] = dict(contagem.most_common(5))
                
                ultimo_numero = duzia_ai.numeros_completos[-1]
                if ultimo_numero != 0:
                    ultimo_terminal = ultimo_numero % 10
                    detalhes['ultimo_terminal'] = ultimo_terminal
                    if quentes and ultimo_terminal in quentes:
                        bonus += 1
        
        return True, "💎 Filtros Elite OK", detalhes, bonus
    
    def especialista_tendencia(self, duzia_ai, previsao):
        score = 0
        streak_count, streak_d = duzia_ai.streak()
        if streak_count >= 2 and streak_d == previsao['duzia']:
            score += 2
        u = list(duzia_ai.historico)[-10:]
        freq = Counter([d for d in u if d != 0])
        total = sum(freq.values())
        if total > 0:
            pct = freq.get(previsao['duzia'], 0) / total
            if pct > 0.35: score += 2
            elif pct > 0.25: score += 1
        markov = duzia_ai._prever_markov()
        if markov and markov[0] == previsao['duzia']:
            score += 1
        s1 = previsao['score'].get(previsao['duzia'], 0)
        if s1 > 35: score += 1
        return score >= 2, score
    
    def especialista_quebra(self, duzia_ai, previsao):
        score = 0
        tem_exaustao = duzia_ai.detectar_exaustao_ciclo_dominante() is not None
        tem_intrusa = duzia_ai.detectar_terceira_duzia_intrusa() is not None
        tem_ciclo = duzia_ai._detectar_ciclo() is not None
        streak_count, streak_d = duzia_ai.streak()
        tem_falsa_tendencia = duzia_ai._detectar_falsa_tendencia(streak_d, streak_count) if streak_d else False
        if tem_exaustao: score += 2
        if tem_intrusa: score += 2
        if tem_ciclo: score += 2
        if tem_falsa_tendencia: score += 1
        if previsao.get('gatilho_ativo'): score += 2
        return score >= 2, score
    
    def especialista_qualidade(self, duzia_ai, previsao):
        score = 0
        qualidade = duzia_ai._calcular_qualidade_entrada(previsao)
        mercado_ruidoso = duzia_ai._mercado_ruidoso()
        if qualidade >= 40: score += 2
        elif qualidade >= 30: score += 1
        if not mercado_ruidoso: score += 1
        confianca = previsao.get('confianca', 0)
        if confianca >= 2.5: score += 2
        elif confianca >= 1.5: score += 1
        erros_recentes = sum(1 for r in duzia_ai.ultimos_resultados[-5:] if not r.get('acertou', True))
        if erros_recentes <= 2: score += 1
        regime = previsao.get('regime', 'NEUTRO')
        if regime in ['DOMINANTE', 'TENDENCIA']: score += 1
        return score >= 2, score
    
    def votar(self, duzia_ai, previsao):
        votos = []
        scores = {}
        
        aprovado_t, score_t = self.especialista_tendencia(duzia_ai, previsao)
        votos.append(('Tendência', aprovado_t))
        scores['Tendência'] = score_t
        
        aprovado_qb, score_qb = self.especialista_quebra(duzia_ai, previsao)
        votos.append(('Quebra', aprovado_qb))
        scores['Quebra'] = score_qb
        
        aprovado_ql, score_ql = self.especialista_qualidade(duzia_ai, previsao)
        votos.append(('Qualidade', aprovado_ql))
        scores['Qualidade'] = score_ql
        
        # Elite como bônus
        elite_ok, elite_motivo, elite_detalhes, elite_bonus = self.analisar_filtros_elite(duzia_ai)
        if elite_ok:
            votos.append(('💎 Elite', True))
            scores['Elite'] = 3 + elite_bonus
        else:
            votos.append(('💎 Elite', False))
            scores['Elite'] = 0
        
        aprovacoes_base = sum(1 for _, v in votos[:3] if v)
        elite_aprova = votos[3][1] if len(votos) > 3 else False
        
        aprovacoes_total = aprovacoes_base
        if elite_aprova:
            aprovacoes_total += 1
        
        aprovado = aprovacoes_total >= 2
        
        votos_str = []
        for nome, voto in votos:
            icon = "✅" if voto else "❌"
            votos_str.append(f"{icon} {nome} ({scores.get(nome, 0)}pts)")
        
        decisao = {
            'votos': votos,
            'scores': scores,
            'aprovacoes': aprovacoes_total,
            'aprovado': aprovado,
            'votos_str': votos_str,
            'elite_aprovado': elite_ok,
            'elite_motivo': elite_motivo,
            'elite_detalhes': elite_detalhes,
            'elite_bonus': elite_bonus,
            'timestamp': hora_brasilia()
        }
        
        self.historico_votacoes.append(decisao)
        self.ultima_decisao = decisao
        
        if len(self.historico_votacoes) > 50:
            self.historico_votacoes = self.historico_votacoes[-50:]
        
        return aprovado, votos, scores, votos_str, elite_ok, elite_motivo if not elite_ok else ""
    
    def registrar_resultado(self, acertou):
        if self.ultima_decisao:
            for nome, voto in self.ultima_decisao['votos']:
                if voto and nome in self.performance_especialistas:
                    if acertou:
                        self.performance_especialistas[nome]['acertos'] += 1
                    else:
                        self.performance_especialistas[nome]['erros'] += 1
    
    def get_taxa_acerto(self, nome):
        perf = self.performance_especialistas[nome]
        total = perf['acertos'] + perf['erros']
        if total == 0:
            return 0
        return (perf['acertos'] / total) * 100

# =============================
# 🧠 DUZIA AI V9.1.1 - CORRIGIDO (KeyError nos detectores)
# =============================
class DuziaAI:
    def __init__(self, window=30):
        self.historico = deque(maxlen=window)
        self.historico_completo = []
        self.historico_duzias = []
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
        self.erros_consecutivos_mesma_duzia = 0
        self.ultima_duzia_errada = None
        self.transicoes = defaultdict(Counter)
        self.streaks_historicos = {1: [], 2: [], 3: []}
        self.media_streaks = {1: 2.0, 2: 2.0, 3: 2.0}
        self.volatilidade_historica = []
        self.erros_por_duzia = {1: 0, 2: 0, 3: 0}
        self.max_erros_por_duzia = 3
        self.entradas_consecutivas = 0
        self.max_entradas_consecutivas = 8
        self.meta_modelo = MetaModelo()
        self.pausa_ate = None
        
    def _garantir_cobertura_diferente(self, previsao):
        if previsao.get('duzia_secundaria') is None or previsao['duzia_secundaria'] == previsao['duzia']:
            outras = self._get_outras_duzias(previsao['duzia'])
            previsao['duzia_secundaria'] = outras[0] if outras else previsao['duzia']
        return previsao
    
    def adicionar(self, numero):
        d = get_duzia(numero)
        self.historico.append(d)
        self.historico_completo.append(d)
        self.historico_duzias.append(d)
        self.numeros_completos.append(numero)
        if len(self.historico_completo) >= 4:
            padrao = tuple(self.historico_completo[-4:-1])
            self.transicoes[padrao][d] += 1
        self._atualizar_streaks()
        if len(self.historico_completo) > 200:
            self.historico_completo = self.historico_completo[-200:]
        if len(self.numeros_completos) > 200:
            self.numeros_completos = self.numeros_completos[-200:]
        if len(self.historico_duzias) > 200:
            self.historico_duzias = self.historico_duzias[-200:]
    
    def _atualizar_streaks(self):
        if len(self.historico_completo) < 3:
            return
        streaks_temp = {1: [], 2: [], 3: []}
        current_d = self.historico_completo[0]
        current_count = 1
        for d in self.historico_completo[1:]:
            if d == current_d:
                current_count += 1
            else:
                if current_d != 0 and current_count >= 2:
                    streaks_temp[current_d].append(current_count)
                current_d = d
                current_count = 1
        for dz in [1, 2, 3]:
            if streaks_temp[dz]:
                self.streaks_historicos[dz].extend(streaks_temp[dz])
                if len(self.streaks_historicos[dz]) > 50:
                    self.streaks_historicos[dz] = self.streaks_historicos[dz][-50:]
                if self.streaks_historicos[dz]:
                    self.media_streaks[dz] = sum(self.streaks_historicos[dz]) / len(self.streaks_historicos[dz])
    
    def _consenso_detectores(self, sinais):
        if not sinais:
            return None, 0
        direcoes = []
        for sinal in sinais:
            if isinstance(sinal, tuple) and len(sinal) >= 1:
                direcoes.append(sinal[0])
            elif isinstance(sinal, dict):
                dz = sinal.get('quebra_prevista') or sinal.get('dz_quebra')
                if dz and dz != 0:
                    direcoes.append(dz)
        if not direcoes:
            return None, 0
        contagem = Counter(direcoes)
        duzia, votos = contagem.most_common(1)[0]
        if votos >= 4: return duzia, 2.5
        elif votos >= 3: return duzia, 2.0
        elif votos >= 2: return duzia, 1.2
        return None, 0
    
    def _mercado_ruidoso(self):
        if len(self.historico) < 10:
            return False
        ultimos = list(self.historico)[-10:]
        trocas = sum(1 for i in range(1, len(ultimos)) if ultimos[i] != ultimos[i-1] and ultimos[i] != 0 and ultimos[i-1] != 0)
        taxa = trocas / 9
        return taxa > 0.75
    
    def _prever_markov(self):
        if len(self.historico_completo) < 3:
            return None
        padrao = tuple(self.historico_completo[-3:])
        if padrao in self.transicoes and self.transicoes[padrao]:
            mais_provavel = self.transicoes[padrao].most_common(1)[0]
            return mais_provavel[0], mais_provavel[1]
        return None
    
    def _detectar_falsa_tendencia(self, duzia, streak_count):
        if duzia == 0: return False
        if streak_count >= 3 and duzia in self.media_streaks:
            if streak_count > self.media_streaks[duzia] * 1.3:
                return True
        return False
    
    def _detectar_ciclo(self):
        if len(self.historico) < 6: return None
        u = list(self.historico)
        ultimos_6 = u[-6:]
        ciclo1, ciclo2, ciclo3 = [1,2,3,1,2,3], [2,3,1,2,3,1], [3,1,2,3,1,2]
        if ultimos_6 == ciclo1: return 1
        elif ultimos_6 == ciclo2: return 2
        elif ultimos_6 == ciclo3: return 3
        if len(u) >= 4 and u[-4] == u[-2] and u[-3] == u[-1] and u[-4] != u[-3] and u[-4] != 0 and u[-3] != 0:
            return u[-3]
        return None
    
    def _calcular_qualidade_entrada(self, previsao):
        qualidade = 0
        sinais = []
        for dz in previsao.get('detalhes', {}):
            if dz == 0: continue
            for det in previsao['detalhes'][dz]:
                if '+' in det:
                    try:
                        forca = float(det.split('+')[1].strip().split()[0])
                        if forca > 2: sinais.append(dz)
                    except: pass
        contagem = Counter(sinais)
        if contagem:
            dz_consenso, votos = contagem.most_common(1)[0]
            if dz_consenso == previsao['duzia']:
                qualidade += min(40, votos * 15)
        score_duzia = previsao['score'].get(previsao['duzia'], 0)
        qualidade += min(30, score_duzia * 0.4)
        regime = previsao.get('regime', 'NEUTRO')
        if regime == 'DOMINANTE': qualidade += 20
        elif regime == 'TENDENCIA': qualidade += 15
        elif regime == 'DISTRIBUIDO': qualidade += 5
        if not self._mercado_ruidoso(): qualidade += 10
        return qualidade
    
    def registrar_previsao(self, duzia):
        self.ultimas_previsoes.append(duzia)
        if len(self.ultimas_previsoes) > 10:
            self.ultimas_previsoes = self.ultimas_previsoes[-10:]
    
    def registrar_resultado(self, duzia_real, acertou):
        self.ultimos_resultados.append({'duzia': duzia_real, 'acertou': acertou, 'timestamp': hora_brasilia()})
        if len(self.ultimos_resultados) > 20:
            self.ultimos_resultados = self.ultimos_resultados[-20:]
        self.meta_modelo.registrar_resultado(acertou)
        if not acertou:
            erros_seguidos = sum(1 for r in reversed(self.ultimos_resultados) if not r.get('acertou', True))
            if erros_seguidos >= 3:
                self.pausa_ate = hora_brasilia() + timedelta(minutes=5)
                logging.info(f"⏸️ PAUSA 5min: {erros_seguidos} erros consecutivos")
        if not acertou and duzia_real != 0:
            self.erros_por_duzia[duzia_real] += 1
            if duzia_real == self.ultima_duzia_errada:
                self.erros_consecutivos_mesma_duzia += 1
            else:
                self.erros_consecutivos_mesma_duzia = 1
                self.ultima_duzia_errada = duzia_real
        else:
            self.erros_consecutivos_mesma_duzia = 0
            self.ultima_duzia_errada = None
            if acertou:
                self.erros_por_duzia = {1: 0, 2: 0, 3: 0}
                self.entradas_consecutivas = 0
                self.pausa_ate = None
        if acertou: self.entradas_consecutivas += 1
    
    def registrar_performance_detector(self, detector, acertou):
        self.performance_detectores[detector].append(1 if acertou else 0)
        if len(self.performance_detectores[detector]) > 20:
            self.performance_detectores[detector] = self.performance_detectores[detector][-20:]
    
    def get_peso_adaptativo(self, detector, peso_base):
        recentes = self.performance_detectores[detector][-10:]
        if not recentes: return peso_base
        taxa_acerto = sum(recentes) / len(recentes)
        if taxa_acerto > 0.75: fator = 1.8
        elif taxa_acerto > 0.65: fator = 1.3
        elif taxa_acerto < 0.45: fator = 0.5
        else: fator = 0.5 + taxa_acerto
        return peso_base * fator
    
    def calibrar_confianca(self, confianca, acertou=None):
        if acertou is not None:
            self.historico_confianca.append({'confianca': confianca, 'acertou': acertou})
            if len(self.historico_confianca) > 30:
                self.historico_confianca = self.historico_confianca[-30:]
        if confianca > 5.0:
            if len(self.historico_confianca) >= 5:
                acertos_recentes = sum(1 for h in self.historico_confianca[-5:] if h.get('acertou'))
                if acertos_recentes < 3:
                    confianca = min(5.0, confianca)
            else: confianca = min(5.0, confianca)
        if len(self.historico_confianca) >= 3:
            ultimos_3 = self.historico_confianca[-3:]
            erros_seguidos = sum(1 for h in ultimos_3 if not h.get('acertou', True))
            if erros_seguidos >= 3: confianca *= 0.3
            elif erros_seguidos >= 2: confianca *= 0.5
        if acertou is not None and not acertou and confianca > 5.0:
            confianca *= 0.4
            return confianca
        return confianca
    
    def detectar_alerta_zero(self):
        if len(self.historico) < 4:
            self.alerta_zero_ativo = False
            return False
        u = list(self.historico)[-5:]
        if len(self.numeros_completos) >= 3:
            if any(n in [26,32,15,3,35] for n in self.numeros_completos[-3:]):
                self.alerta_zero_ativo = True; return True
        if len(u) >= 3 and len(set(u[-3:])) == 1 and u[-1] != 0:
            self.alerta_zero_ativo = True; return True
        if len(u) >= 4 and len(set(d for d in u[-4:] if d != 0)) >= 3:
            self.alerta_zero_ativo = True; return True
        if u and u[-1] == 0:
            self.alerta_zero_ativo = True; return True
        self.alerta_zero_ativo = False; return False
    
    # ========== GATILHOS E DETECTORES ==========
    def detectar_exaustao_ciclo_dominante(self):
        if len(self.historico) < 10: return None
        u = list(self.historico)[-15:]
        freq = Counter([d for d in u if d != 0])
        if len(freq) < 2: return None
        ranking = freq.most_common()
        dz_dominante = ranking[0][0]
        if self.sinal_mudanca_pendente:
            if u[-1] == self.sinal_mudanca_pendente['dz_quebra'] and u[-1] != 0:
                r = {'tipo':'MUDANCA_VELOCIDADE','dz_quebra':self.sinal_mudanca_pendente['dz_quebra'],'dz_exaurida':self.sinal_mudanca_pendente['dz_exaurida'],'forca':9,'descricao':f"Mudança CONFIRMADA"}
                self.ultimo_gatilho = 'MUDANCA_VELOCIDADE'; self.sinal_mudanca_pendente = None; return r
            else: self.sinal_mudanca_pendente = None
        ultimas_10 = u[-10:]
        freq_10 = Counter([d for d in ultimas_10 if d != 0])
        if freq_10.get(dz_dominante,0) >= 7:
            if dz_dominante not in u[-3:-1]:
                outras = self._get_outras_duzias(dz_dominante)
                freq_emergentes = {d: freq.get(d,0) for d in outras}
                dz_emergente = max(freq_emergentes, key=freq_emergentes.get)
                if dz_emergente != 0:
                    self.ultimo_gatilho = 'EXAUSTAO_DOMINANCIA'
                    return {'tipo':'EXAUSTAO_DOMINANCIA','dz_quebra':dz_emergente,'dz_exaurida':dz_dominante,'forca':9,'descricao':f'D{dz_dominante} exaurida'}
        if len(self.ultimos_resultados) >= 2 and not self.ultimos_resultados[-1]['acertou'] and not self.ultimos_resultados[-2]['acertou']:
            dz_errada = self.ultimos_resultados[-1]['duzia'] if self.ultimos_resultados[-1]['duzia'] != 0 else dz_dominante
            outras = self._get_outras_duzias(dz_errada)
            freq_outras = {d: freq.get(d,0) for d in outras}
            dz_escolhida = max(freq_outras, key=freq_outras.get)
            if dz_escolhida != 0:
                self.ultimo_gatilho = 'SEQUENCIA_ERROS'
                return {'tipo':'SEQUENCIA_ERROS','dz_quebra':dz_escolhida,'dz_exaurida':dz_errada,'forca':8,'descricao':f'2 erros seguidos'}
        if 0 in u[-5:]:
            pos_zero = len(u) - 1 - u[::-1].index(0)
            depois_zero = u[pos_zero+1:]
            if len(depois_zero) >= 2 and depois_zero[-1] != dz_dominante and depois_zero[-1] != 0:
                self.ultimo_gatilho = 'QUEBRA_POS_ZERO'
                return {'tipo':'QUEBRA_POS_ZERO','dz_quebra':depois_zero[-1],'dz_exaurida':dz_dominante,'forca':7,'descricao':f'Zero quebrou dominância'}
        return None
    
    def detectar_quebra_estados(self):
        if len(self.historico) < 5: return None
        u = list(self.historico)
        resultado = {'quebra_prevista':None,'forca':0,'estado_atual':None,'duzias_envolvidas':[]}
        streak_count, streak_d = self.streak()
        if streak_count >= 3 and streak_d != 0:
            outras = self._get_outras_duzias(streak_d)
            forca = min(8, 2 + (streak_count-3)*2)
            freq_outras = {d: sum(1 for x in u[-8:] if x==d) for d in outras}
            scores_quebra = {}
            for d in outras:
                score = 0
                if freq_outras[d] >= 2: score += 3
                elif freq_outras[d] >= 1: score += 1
                scores_quebra[d] = score
            if scores_quebra:
                dz_quebra = max(scores_quebra, key=scores_quebra.get)
                if scores_quebra[dz_quebra] >= 2 and dz_quebra != 0:
                    resultado['quebra_prevista'] = dz_quebra
                    resultado['forca'] = forca
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
        dz1, dz2 = ranking[0][0], ranking[1][0]
        terceira = self._get_terceira_duzia(dz1, dz2)
        if terceira is None or terceira == 0: return None
        count_terceira = freq.get(terceira, 0)
        if (freq[dz1] + freq[dz2]) >= 7 and count_terceira <= 1:
            forca = min(8, 3 + count_terceira)
            return terceira, forca, dz1, dz2
        return None
    
    def detectar_streak_longo(self):
        streak_count, streak_d = self.streak()
        if streak_count >= 3 and streak_d != 0:
            return streak_d, min(10, 4+(streak_count-3)*2)
        return None
    
    def detectar_retorno_aba(self):
        if len(self.historico) < 3: return None
        u = list(self.historico)[-3:]
        if u[0] == u[2] and u[0] != u[1] and u[0] != 0 and u[1] != 0:
            return u[0], 5
        return None
    
    def detectar_duas_dominantes(self):
        if len(self.historico) < 10: return None
        freq = Counter(list(self.historico)[-10:])
        ranking = freq.most_common()
        if len(ranking) >= 2 and ranking[0][1] + ranking[1][1] >= 8:
            return (ranking[0][0], ranking[1][0]), 3
        return None
    
    def detectar_progressao(self):
        if len(self.historico) < 4: return None
        u = list(self.historico)[-4:]
        if u[0] == u[1] and u[2] == u[3] and u[1] != u[2] and u[0] != 0 and u[2] != 0:
            return u[2], 4
        return None
    
    def detectar_repeticao_imediata(self):
        if len(self.historico) < 2: return None
        u = list(self.historico)[-2:]
        if u[0] == u[1] and u[0] != 0: return u[0], 4
        return None
    
    def detectar_vai_e_volta(self):
        u = list(self.historico)
        if len(u) >= 4 and u[-4] == u[-2] and u[-3] == u[-1] and u[-4] != u[-3] and u[-4] != 0 and u[-3] != 0:
            return u[-3], 6
        return None
    
    def detectar_mudanca_abrupta(self):
        if len(self.historico) < 8: return None
        u = list(self.historico)
        freq_antiga = Counter([d for d in u[-8:-4] if d != 0])
        freq_recente = Counter([d for d in u[-4:] if d != 0])
        if not freq_antiga or not freq_recente: return None
        dom_antiga = freq_antiga.most_common(1)[0]
        dom_recente = freq_recente.most_common(1)[0]
        if dom_antiga[0] != dom_recente[0] and dom_recente[0] != 0 and dom_recente[1] >= 2:
            return dom_recente[0], min(8, 4+abs(dom_recente[1]-dom_antiga[1])), dom_antiga[0]
        return None
    
    def detectar_troca_subita(self):
        if len(self.historico) < 4: return None
        u = list(self.historico)[-4:]
        if u[-2] != u[-1] and u[-3] != u[-1] and u[-4] != u[-1] and u[-1] != 0:
            return u[-1], 6
        return None
    
    def streak(self):
        if not self.historico: return 0, None
        last = self.historico[-1]
        count = 0
        for d in reversed(self.historico):
            if d == last: count += 1
            else: break
        return count, last
    
    def frequencia(self):
        return Counter(self.historico)
    
    def frequencia_ponderada(self):
        freq = Counter()
        total = len(self.historico)
        for i, d in enumerate(self.historico):
            pos = i / max(1, total-1)
            peso = 1 + (pos**1.5)*7
            freq[d] += peso
        return freq
    
    def transicao(self):
        if len(self.historico) < 2: return None
        return self.historico[-2], self.historico[-1]
    
    def matriz_transicao(self):
        matriz = {1:{1:0,2:0,3:0}, 2:{1:0,2:0,3:0}, 3:{1:0,2:0,3:0}}
        totais = {1:0,2:0,3:0}
        for i in range(len(self.historico_completo)-1):
            o, d = self.historico_completo[i], self.historico_completo[i+1]
            if o != 0 and d != 0:
                peso = 1 + (i/max(1,len(self.historico_completo)))*2
                matriz[o][d] += peso
                totais[o] += peso
        prob = {}
        for o in [1,2,3]:
            prob[o] = {}
            for d in [1,2,3]:
                prob[o][d] = (matriz[o][d]/totais[o]*100) if totais[o] > 0 else 33.3
        return prob
    
    def detectar_regime(self):
        freq = self.frequencia()
        total = sum(freq.values())
        if total == 0: return "NEUTRO"
        razao = max(freq.values()) / total
        if razao > 0.5: return "DOMINANTE"
        elif razao > 0.4: return "TENDENCIA"
        elif len([d for d in freq if freq[d] > 0]) == 3: return "DISTRIBUIDO"
        else: return "TRANSICAO"
    
    def _get_outras_duzias(self, duzia):
        return [d for d in [1,2,3] if d != duzia]
    
    def _get_terceira_duzia(self, dz1, dz2):
        for d in [1,2,3]:
            if d != dz1 and d != dz2: return d
        return None
    
    def balancear_previsoes(self, previsao):
        if len(self.historico) < 2: return previsao
        u = list(self.historico)
        if self.alerta_zero_ativo: previsao['incluir_zero'] = True
        for dz, erros in self.erros_por_duzia.items():
            if erros >= self.max_erros_por_duzia and previsao['duzia'] == dz:
                outras = self._get_outras_duzias(dz)
                freq_outras = {d: u.count(d) for d in outras}
                previsao['duzia'] = max(freq_outras, key=freq_outras.get)
                return self._garantir_cobertura_diferente(previsao)
        if self.erros_consecutivos_mesma_duzia >= 2 and self.ultima_duzia_errada:
            if previsao['duzia'] == self.ultima_duzia_errada:
                outras = self._get_outras_duzias(self.ultima_duzia_errada)
                freq_outras = {d: u.count(d) for d in outras}
                previsao['duzia'] = max(freq_outras, key=freq_outras.get)
                return self._garantir_cobertura_diferente(previsao)
        return self._garantir_cobertura_diferente(previsao)
    
    # ========== CÁLCULO DE SCORE (V9.1.1 - CORRIGIDO) ==========
    def calcular_score(self):
        score = {1: 0, 2: 0, 3: 0}
        detalhes = {1: [], 2: [], 3: []}
        freq = self.frequencia_ponderada()
        freq_normal = self.frequencia()
        streak_count, streak_d = self.streak()
        regime = self.detectar_regime()
        
        for d in score: score[d] += freq[d] * 0.8
        total_normal = sum(freq_normal.values())
        if total_normal > 0:
            for d in score: score[d] += (freq_normal[d] / total_normal) * 10
        
        if self._mercado_ruidoso():
            for d in score: score[d] *= 0.5
        
        markov_pred = self._prever_markov()
        if markov_pred and markov_pred[0] != 0 and markov_pred[0] in score:
            score[markov_pred[0]] += 8
        
        if streak_d and streak_d != 0 and streak_d in score:
            multiplicador = 3.0 if regime == "DOMINANTE" else 2.0 if regime == "TENDENCIA" else 1.5
            score[streak_d] += streak_count * multiplicador
        
        if len(self.historico) >= 2:
            u = list(self.historico)
            if u[-1] == u[-2] and u[-1] != 0 and u[-1] in score:
                score[u[-1]] += 20
        
        # 🆕 CORRIGIDO: Detectores com proteção de tipo
        for detector_func, nome in [
            (self.detectar_quebra_estados, 'quebra_estados'),
            (self.detectar_streak_longo, 'streak_longo'),
            (self.detectar_retorno_aba, 'retorno_aba'),
            (self.detectar_repeticao_imediata, 'repeticao_imediata'),
            (self.detectar_vai_e_volta, 'vai_e_volta'),
            (self.detectar_progressao, 'progressao'),
        ]:
            result = detector_func()
            if result:
                # 🆕 Proteção: verifica tipo do resultado
                if isinstance(result, dict):
                    dz = result.get('quebra_prevista', 0)
                    forca = result.get('forca', 3)
                elif isinstance(result, tuple):
                    dz = result[0] if len(result) > 0 else 0
                    forca = result[1] if len(result) > 1 else 3
                else:
                    dz = result
                    forca = 3
                
                # Só aplica se dz for válido (1, 2 ou 3)
                if dz in [1, 2, 3] and dz in score:
                    score[dz] += self.get_peso_adaptativo(nome, forca)
        
        # Exaustão
        exaustao = self.detectar_exaustao_ciclo_dominante()
        if exaustao and isinstance(exaustao, dict):
            dz_quebra = exaustao.get('dz_quebra', 0)
            if dz_quebra in [1, 2, 3] and dz_quebra in score:
                score[dz_quebra] += self.get_peso_adaptativo('exaustao_ciclo', exaustao.get('forca', 9) * 1.5)
        
        # Mudança abrupta
        mudanca = self.detectar_mudanca_abrupta()
        if mudanca and isinstance(mudanca, tuple) and len(mudanca) >= 1:
            dz = mudanca[0]
            if dz in [1, 2, 3] and dz in score:
                score[dz] += self.get_peso_adaptativo('mudanca_abrupta', mudanca[1] if len(mudanca) > 1 else 4)
        
        total = sum(score.values())
        if total > 0:
            for d in score: score[d] = (score[d] / total) * 100
        
        return score, regime, detalhes
    
    def prever(self, confianca_minima=2.5, agressividade=2):
        # Verificar pausa
        if self.pausa_ate and hora_brasilia() < self.pausa_ate:
            return {"entrar":False,"motivo":f"⏸️ Pausa até {formatar_hora_brasilia(self.pausa_ate)}","score":{1:0,2:0,3:0},"regime":"PAUSADO","confianca":0,"duzia":1,"duzia_secundaria":2,"detalhes":{},"detectores_ativos":[],"gatilho_ativo":None,"incluir_zero":False}
        
        score, regime, detalhes = self.calcular_score()
        ranking = sorted(score.items(), key=lambda x: x[1], reverse=True)
        d1, s1 = ranking[0]
        d2, s2 = ranking[1]
        if d2 == d1:
            outras = self._get_outras_duzias(d1)
            d2 = ranking[2][0] if len(ranking) > 2 else outras[0]
        
        self.detectar_alerta_zero()
        ratio = min(5.0, s1 / max(1, s2))
        vol = np.std(list(score.values()))
        confianca = (ratio * 2.2) + (1.5 / (1 + vol))
        confianca = min(10.0, max(1.0, confianca))
        
        if self.alerta_zero_ativo: confianca *= 0.6
        if self._mercado_ruidoso(): confianca *= 0.5
        
        confianca = self.calibrar_confianca(confianca)
        
        tem_gatilho_quebra = self.ultimo_gatilho is not None
        pode_entrar = True
        motivo = ""
        
        if self.sinal_mudanca_pendente:
            pode_entrar = False
            motivo = f"⏳ Aguardando confirmação"
        elif confianca < confianca_minima and not tem_gatilho_quebra:
            pode_entrar = False
            motivo = f"Confiança baixa ({confianca:.2f} < {confianca_minima})"
        
        previsao = {
            "entrar": pode_entrar,
            "motivo": motivo,
            "score": score,
            "regime": regime,
            "confianca": round(confianca, 2),
            "duzia": d1,
            "duzia_secundaria": d2,
            "detalhes": detalhes,
            "detectores_ativos": [],
            "gatilho_ativo": self.ultimo_gatilho,
            "incluir_zero": self.alerta_zero_ativo
        }
        
        # Meta-Modelo
        meta_modelo_ativo = st.session_state.get('meta_modelo_ativo', True)
        if pode_entrar and meta_modelo_ativo:
            aprovado, votos, scores, votos_str, elite_ok, elite_motivo = self.meta_modelo.votar(self, previsao)
            
            if not aprovado:
                pode_entrar = False
                previsao['entrar'] = False
                previsao['motivo'] = f"🧠 Meta-Modelo: {' | '.join(votos_str)}"
                if not elite_ok:
                    previsao['motivo'] += f" [{elite_motivo}]"
                previsao['meta_modelo'] = {'aprovado': False, 'votos': votos, 'scores': scores, 'elite_ok': elite_ok}
            else:
                previsao['meta_modelo'] = {'aprovado': True, 'votos': votos, 'scores': scores, 'elite_ok': elite_ok}
                previsao['elite'] = elite_ok
        
        if pode_entrar and self.entradas_consecutivas >= self.max_entradas_consecutivas:
            pode_entrar = False
            previsao['entrar'] = False
            previsao['motivo'] = f"🚫 Limite de {self.max_entradas_consecutivas} entradas consecutivas"
        
        if pode_entrar:
            previsao = self.balancear_previsoes(previsao)
        
        if len(self.historico) >= 2:
            u = list(self.historico)
            if u[-1] == u[-2] and u[-1] != 0 and previsao['duzia'] != u[-1]:
                previsao['duzia'] = u[-1]
                self.streak_ativo = u[-1]
        
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
        if not validar_numero(nr): return
        
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
            
            entrada_info = {
                'rodada': self.numero_rodada, 'hora': formatar_hora_brasilia(),
                'numero': nr, 'duzia_real': duzia_real if nr != 0 else 0,
                'duzia_prevista': duzia_prevista, 'duzia_sec_prevista': duzia_sec_prevista,
                'acerto_primaria': acerto_primaria, 'acerto_secundaria': acerto_secundaria,
                'confianca': self.entrada_ativa.get('confianca', 0),
                'regime': self.entrada_ativa.get('regime', 'NEUTRO'),
                'gatilho': self.entrada_ativa.get('gatilho_ativo', None),
                'incluir_zero': incluir_zero,
                'meta_modelo': self.entrada_ativa.get('meta_modelo', None),
                'elite': self.entrada_ativa.get('elite', False)
            }
            self.historico_entradas.append(entrada_info)
            if len(self.historico_entradas) > 50: self.historico_entradas = self.historico_entradas[-50:]
            
            enviar_resultado_auto(nr, acerto_primaria or acerto_secundaria)
            self.entrada_ativa = None
        
        confianca_minima = st.session_state.get('confianca_minima', 2.5)
        agressividade = st.session_state.get('agressividade', 2)
        previsao = self.duzia_ai.prever(confianca_minima=confianca_minima, agressividade=agressividade)
        
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
                'incluir_zero': previsao.get('incluir_zero', False),
                'meta_modelo': previsao.get('meta_modelo', None),
                'elite': previsao.get('elite', False)
            }
            
            self.duzia_ai.registrar_previsao(previsao['duzia'])
            idx_atual = len(self.historico_numeros) - 1
            self.sinais_grafico.append((idx_atual, previsao['duzia']))
            enviar_previsao_auto({'numeros_apostar': numeros_apostar, 'incluir_zero': previsao.get('incluir_zero', False), 'elite': previsao.get('elite', False)})
    
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
            writer.writerow(['Rodada','Hora','Número','Dúzia Real','Dúzia Prevista','Confiança','Gatilho','Meta','Elite','Resultado'])
            for entrada in historico_entradas:
                resultado = '✅' if entrada.get('acerto_primaria') else '🟡' if entrada.get('acerto_secundaria') else '❌'
                duzia_real = f"D{entrada.get('duzia_real',0)}" if entrada.get('duzia_real',0) != 0 else "0"
                gatilho = entrada.get('gatilho','') if entrada.get('gatilho') else "-"
                meta = entrada.get('meta_modelo',{})
                meta_str = '✅' if meta and meta.get('aprovado') else '❌' if meta else '-'
                elite_str = '💎' if entrada.get('elite') else '-'
                writer.writerow([
                    entrada.get('rodada','-'), entrada.get('hora','-'), entrada.get('numero','-'),
                    duzia_real, f"D{entrada.get('duzia_prevista','?')}",
                    f"{entrada.get('confianca',0):.2f}", gatilho, meta_str, elite_str, resultado
                ])
        return True
    except Exception as e:
        logging.error(f"Erro ao exportar CSV: {e}")
        return False

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎰 DuziaAI V9.1.1 - Corrigido", layout="wide")
st.title("🎰 DuziaAI V9.1.1 - KEYERROR CORRIGIDO (BRT)")

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
    st.session_state.confianca_minima = dados.get('confianca_minima', 2.5)
    st.session_state.agressividade = dados.get('agressividade', 2)
    st.session_state.meta_modelo_ativo = dados.get('meta_modelo_ativo', True)
    if os.path.exists(ENTRADAS_PATH):
        try:
            with open(ENTRADAS_PATH, 'r') as f:
                sis.historico_entradas = json.load(f)
        except: pass

defaults = {
    'modo_automatico': True, 'modo_agressivo': False, 'janela_duzia_ai': 30,
    'confianca_minima': 2.5, 'agressividade': 2,
    'acertos_duzia': 0, 'erros_duzia': 0, 'acertos_duzia_sec': 0, 'erros_duzia_sec': 0,
    'meta_modelo_ativo': True,
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
    st.markdown("## ⚙️ Configurações")
    if st.button("🆕 NOVA SESSÃO", use_container_width=True, type="primary"):
        if nova_sessao():
            st.success("✅ Nova sessão iniciada!")
            st.rerun()
    st.markdown("---")
    st.session_state.janela_duzia_ai = st.slider("📏 Janela de Análise", 10, 50, st.session_state.janela_duzia_ai, 5)
    st.session_state.confianca_minima = st.slider("🎯 Confiança Mínima", 1.5, 5.0, st.session_state.confianca_minima, 0.1)
    st.session_state.agressividade = st.select_slider("🎚️ Agressividade", options=[1,2,3], value=st.session_state.agressividade)
    st.session_state.modo_agressivo = st.checkbox("🔥 Modo Agressivo (2 Dúzias)", value=st.session_state.modo_agressivo)
    st.session_state.modo_automatico = st.checkbox("🤖 Modo Automático", value=st.session_state.modo_automatico)
    st.session_state.meta_modelo_ativo = st.checkbox("🧠 Meta-Modelo + 💎 Elite", value=st.session_state.get('meta_modelo_ativo', True))
    st.markdown("---")
    st.markdown("### 🛡️ V9.1.1 - CORRIGIDO")
    st.caption("🔧 KeyError nos detectores resolvido")
    st.caption("🛡️ Verificação isinstance() em resultados")
    st.caption("✅ dz in [1,2,3] antes de acessar score")
    st.caption("💎 Elite: BÔNUS (+1 aprovação)")
    st.caption("🎯 Confiança: 2.5")
    st.caption("🕐 Horário BRASÍLIA (BRT)")
    st.markdown("---")
    with st.expander("🔔 Telegram", expanded=False):
        st.session_state.telegram_token = st.text_input("Token", value=st.session_state.telegram_token, type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID", value=st.session_state.telegram_chat_id)
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💾 Salvar", use_container_width=True): 
            salvar_resultado_em_arquivo(st.session_state.historico); salvar_sessao(); st.success("✅ Salvo!")
    with col2:
        if st.button("🗑️ Zerar", use_container_width=True): st.session_state.sistema.zerar(); st.rerun()
    with col3:
        if st.button("📥 CSV", use_container_width=True):
            if exportar_historico_csv(st.session_state.sistema.historico_entradas): st.success("✅ CSV exportado!")

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
        else: st.error("Digite um número válido (0-36)")
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
col1, col2, col3, col4, col5, col6, col7, col8, col9 = st.columns(9)
total_entradas = int(sis.acertos + sis.erros)
tx_acerto = (sis.acertos / total_entradas * 100) if total_entradas > 0 else 0
ac_dz = st.session_state.get('acertos_duzia', 0)
er_dz = st.session_state.get('erros_duzia', 0)
total_dz = ac_dz + er_dz
tx_dz = (ac_dz / total_dz * 100) if total_dz > 0 else 0
mercado_ruidoso = sis.duzia_ai._mercado_ruidoso()
pausado = sis.duzia_ai.pausa_ate and hora_brasilia() < sis.duzia_ai.pausa_ate
col1.metric("✅ Acertos", int(sis.acertos))
col2.metric("❌ Erros", int(sis.erros))
col3.metric("📊 Win Rate", f"{tx_acerto:.1f}%")
col4.metric("🎯 Tx Primária", f"{tx_dz:.1f}%")
col5.metric("📦 Entradas", total_entradas)
col6.metric("🔢 Rodada", sis.numero_rodada)
col7.metric("⚠️ Zero", "🟢" if sis.duzia_ai.alerta_zero_ativo else "⚪")
col8.metric("🌪️ Ruído", "🌪️" if mercado_ruidoso else "✅")
col9.metric("⏸️", "⏸️" if pausado else "▶️")

if pausado:
    st.warning(f"⏸️ Pausado até {formatar_hora_brasilia(sis.duzia_ai.pausa_ate)} - 3 erros consecutivos")

st.markdown("---")

col_grafico, col_entrada = st.columns([3,2])
with col_grafico:
    st.subheader("📈 Análise em Tempo Real")
    if len(sis.historico_numeros) >= 5:
        score, regime, detalhes = sis.duzia_ai.calcular_score()
        fig = plt.Figure(data=[plt.Bar(
            x=['D1','D2','D3'], y=[score[1],score[2],score[3]],
            marker_color=['#FF6B6B' if score[1]==max(score.values()) else '#4ECDC4',
                          '#FF6B6B' if score[2]==max(score.values()) else '#4ECDC4',
                          '#FF6B6B' if score[3]==max(score.values()) else '#4ECDC4'],
            text=[f'{score[1]:.1f}',f'{score[2]:.1f}',f'{score[3]:.1f}'], textposition='auto'
        )])
        fig.update_layout(title=f"🎯 Scores | Regime: {regime}", height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        if len(sis.historico_numeros) >= 10:
            ultimos_20 = list(sis.historico_numeros)[-20:]
            duzias_hist = [get_duzia(n) for n in ultimos_20]
            fig2 = plt.Figure()
            fig2.add_trace(plt.Scatter(x=list(range(len(duzias_hist))), y=duzias_hist, mode='lines+markers', line=dict(color='#FFD700',width=2)))
            if sis.sinais_grafico:
                sx, sy = [], []
                offset = len(duzias_hist) - 20
                for idx, dz in sis.sinais_grafico:
                    pos = idx - offset
                    if 0 <= pos < 20: sx.append(pos); sy.append(dz)
                if sx: fig2.add_trace(plt.Scatter(x=sx, y=sy, mode='markers', name='Sinal', marker=dict(symbol='diamond',size=15,color='#00FFFF')))
            fig2.update_layout(title="📉 Histórico", yaxis=dict(tickvals=[1,2,3],ticktext=['D1','D2','D3'],range=[0.5,3.5]), height=300)
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info(f"⏳ Aguardando dados... ({len(sis.historico_numeros)}/5 giros)")

with col_entrada:
    st.subheader("🎰 Entrada Atual")
    if sis.entrada_ativa:
        ent = sis.entrada_ativa
        confianca = ent.get('confianca', 0)
        duzia_prevista = ent.get('duzia_prevista', 0)
        limite = "1-12" if duzia_prevista==1 else "13-24" if duzia_prevista==2 else "25-36"
        elite = ent.get('elite', False)
        cor_borda = "#00FFFF" if elite else "#FFD700"
        titulo = "💎 SINAL ELITE" if elite else "🎯 ENTRADA"
        
        st.markdown(f"""
        <div style="background-color:{cor_borda}15; border:2px solid {cor_borda}; border-radius:15px; padding:20px; margin:10px 0;">
            <h2 style="color:{cor_borda}; text-align:center;">{titulo}</h2>
            <h3 style="text-align:center;">D{duzia_prevista} ({limite})</h3>
            <p style="text-align:center; font-size:1.2em;">Confiança: {confianca:.2f} | Regime: {ent.get('regime','?')}</p>
        </div>""", unsafe_allow_html=True)
        
        numeros_apostar = ent.get('numeros_apostar', [])
        if numeros_apostar:
            st.write("**🎲 Números:**")
            cols = st.columns(7)
            for i, n in enumerate(sorted(numeros_apostar)):
                cols[i%7].button("🟢0" if n==0 else str(n), key=f"num_{n}", use_container_width=True)
        st.progress(min(1.0, max(0.0, confianca/10.0)))
    else:
        st.info("🔍 Analisando padrões...")
    if sis.ultimo_numero is not None:
        st.write(f"**🔄 Último Giro:** {'🟢 ZERO' if sis.ultimo_numero==0 else f'#{sis.ultimo_numero} → D{get_duzia(sis.ultimo_numero)}'}")

st.markdown("---")
st.subheader("📝 Histórico")
if sis.historico_entradas:
    dados_tabela = []
    for e in reversed(sis.historico_entradas[-20:]):
        duzia_real_str = f"D{e.get('duzia_real','?')}" if e.get('duzia_real',0)!=0 else "0"
        resultado_str = '✅' if e.get('acerto_primaria') else '🟡' if e.get('acerto_secundaria') else '❌'
        meta = e.get('meta_modelo',{})
        meta_str = '✅' if meta and meta.get('aprovado') else '❌' if meta else '-'
        elite_str = '💎' if e.get('elite') else '-'
        dados_tabela.append({
            "Rod": e.get('rodada','-'), "Hora": e.get('hora','-'), "Nº": e.get('numero','-'),
            "Real": duzia_real_str, "Prev": f"D{e.get('duzia_prevista','?')}" if e.get('duzia_prevista') else "-",
            "Conf": f"{e.get('confianca',0):.1f}", "Gat": e.get('gatilho','-') if e.get('gatilho') else "-",
            "Meta": meta_str, "Elite": elite_str, "Res": resultado_str
        })
    st.dataframe(dados_tabela, use_container_width=True, height=300)
    if st.button("📥 Exportar CSV", use_container_width=True):
        if exportar_historico_csv(sis.historico_entradas): st.success("✅ CSV exportado!")
else:
    st.info("Nenhuma entrada ainda.")

st.markdown("---")
st.caption(f"🤖 DuziaAI V9.1.1 | KeyError Corrigido | {formatar_hora_brasilia()}")
salvar_sessao()
