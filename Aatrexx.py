import streamlit as st
import json
import os
import requests
import logging
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
    handlers=[logging.FileHandler('roleta_bot.log'), logging.StreamHandler()]
)

# =============================
# FUSO HORÁRIO BRASÍLIA
# =============================
BRT = timezone(timedelta(hours=-3))

def hora_brasilia():
    return datetime.now(BRT)

def formatar_hora_brasilia(dt=None):
    if dt is None: dt = hora_brasilia()
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
        if 'sistema' not in st.session_state or st.session_state.sistema is None: return False
        sis = st.session_state.sistema
        performance_data = {
            'acertos_duzia': sis.acertos_duzia,
            'erros_duzia': sis.erros_duzia,
            'acertos_numero': sis.acertos_numero,
            'erros_numero': sis.erros_numero,
            'acertos_zero': sis.acertos_zero,
            'erros_zero': sis.erros_zero
        }
        with open(PERFORMANCE_PATH, 'w') as f: json.dump(performance_data, f)
        with open(ENTRADAS_PATH, 'w') as f: json.dump(sis.historico_entradas, f)
        session_data = {
            'historico_numeros': list(sis.historico_numeros),
            'historico_entradas': sis.historico_entradas,
            'entrada_ativa': sis.entrada_ativa,
            'acertos_duzia': sis.acertos_duzia,
            'erros_duzia': sis.erros_duzia,
            'acertos_numero': sis.acertos_numero,
            'erros_numero': sis.erros_numero,
            'acertos_zero': sis.acertos_zero,
            'erros_zero': sis.erros_zero,
            'numero_rodada': sis.numero_rodada,
            'janela_duzia_ai': st.session_state.get('janela_duzia_ai', 30),
            'modo_agressivo': st.session_state.get('modo_agressivo', False),
            'modo_automatico': st.session_state.get('modo_automatico', True),
        }
        with open(SESSION_DATA_PATH, 'wb') as f: pickle.dump(session_data, f)
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar: {e}")
        return False

def carregar_dados_persistidos():
    try:
        if os.path.exists(SESSION_DATA_PATH):
            with open(SESSION_DATA_PATH, 'rb') as f: return pickle.load(f)
    except: pass
    return None

def limpar_sessao():
    try:
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH, ENTRADAS_PATH]:
            if os.path.exists(path): os.remove(path)
        st.session_state.clear(); st.rerun()
    except Exception as e: logging.error(f"Erro: {e}")

def nova_sessao():
    try:
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH, ENTRADAS_PATH]:
            if os.path.exists(path): os.remove(path)
        if 'sistema' in st.session_state: st.session_state.sistema.zerar()
        st.session_state.historico = []
        logging.info("🆕 NOVA SESSÃO INICIADA"); return True
    except Exception as e: logging.error(f"Erro: {e}"); return False

# =============================
# NOTIFICAÇÕES
# =============================
def enviar_previsao_auto(previsao):
    try:
        numeros = sorted(previsao.get('numeros_apostar', []))
        incluir_zero = previsao.get('incluir_zero', False)
        d1n = [n for n in numeros if 1 <= n <= 12]
        d2n = [n for n in numeros if 13 <= n <= 24]
        d3n = [n for n in numeros if 25 <= n <= 36]
        
        prefixo = "⚠️🎯 " if incluir_zero else "🎯 "
        
        if d1n and d2n: msg = f"{prefixo}D1 (1-12) | Cob: D2 (13-24)"
        elif d1n and d3n: msg = f"{prefixo}D1 (1-12) | Cob: D3 (25-36)"
        elif d2n and d3n: msg = f"{prefixo}D2 (13-24) | Cob: D3 (25-36)"
        elif d1n: msg = f"{prefixo}D1 (1-12)"
        elif d2n: msg = f"{prefixo}D2 (13-24)"
        elif d3n: msg = f"{prefixo}D3 (25-36)"
        else: msg = f"{prefixo}{numeros}"
        
        if incluir_zero: msg += " + 🟢 ZERO"
        st.toast(msg)
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"🔔 {msg}\n🔢 " + " ".join(map(str, numeros)))
        salvar_sessao()
    except Exception as e: logging.error(f"Erro: {e}")

def enviar_resultado_auto(numero_real, acerto_duzia, acerto_numero, acerto_zero, lucky_multiplier=None):
    try:
        partes = []
        if acerto_zero:
            partes.append("✅ ZERO!")
        elif numero_real == 0:
            partes.append("🟢 ZERO (não apostado)")
        else:
            duzia_real = get_duzia(numero_real)
            if acerto_numero:
                if lucky_multiplier:
                    partes.append(f"⚡ Nº {numero_real} RAIO {lucky_multiplier}X!")
                else:
                    partes.append(f"🎯 Nº EXATO {numero_real}!")
            elif acerto_duzia:
                partes.append(f"✅ D{duzia_real}")
            else:
                partes.append(f"❌ Nº {numero_real} (D{duzia_real})")
        
        msg = " | ".join(partes)
        st.toast(msg)
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"📢 {msg}")
        salvar_sessao()
    except Exception as e: logging.error(f"Erro: {e}")

def enviar_telegram(mensagem):
    try:
        token = st.session_state.get('telegram_token', '')
        chat_id = st.session_state.get('telegram_chat_id', '')
        if not token or not chat_id: return
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                     json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}, timeout=10)
    except Exception as e: logging.error(f"Erro Telegram: {e}")

# =============================
# API
# =============================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_duzia(numero):
    if numero == 0: return 0
    elif 1 <= numero <= 12: return 1
    elif 13 <= numero <= 24: return 2
    else: return 3

def validar_numero(valor):
    try:
        num = int(valor); return 0 <= num <= 36
    except: return False

# =============================
# 🧠 DUZIA AI V10.9 - MANTIDO
# =============================
class DuziaAI:
    def __init__(self, window=30):
        self.historico = deque(maxlen=window)
        self.historico_completo = []
        self.numeros_completos = []
        self.ultimas_previsoes = []
        self.ultimos_resultados = []
        
        self.transicoes = defaultdict(Counter)
        
        self.erros_por_duzia = {1: 0, 2: 0, 3: 0}
        self.erros_consecutivos = 0
        self.ultima_duzia_errada = None
        self.entradas_consecutivas = 0
        self.ultimo_gatilho = None
        self.streak_ativo = None
        self.alerta_zero_ativo = False
        self.pausa_ate = None
        
        self.modo_anti_erro = False
        self.duzias_que_sairam = []

        self.consecutivos_amarelos = 0
        self.ultimo_resultado_duzia = None
        self.ultimo_resultado_numero = None
        self.ultima_confianca = 0
        self.ultima_previsao_duzia = None
        
        self.alertas_zero_disparados = 0
        self.zeros_previstos = 0
        
    def adicionar(self, numero):
        d = get_duzia(numero)
        self.historico.append(d)
        self.historico_completo.append(d)
        self.numeros_completos.append(numero)
        
        if d != 0:
            self.duzias_que_sairam.append(d)
            if len(self.duzias_que_sairam) > 10:
                self.duzias_que_sairam = self.duzias_que_sairam[-10:]
        
        if numero == 0 and self.alerta_zero_ativo:
            self.zeros_previstos += 1
        
        if len(self.historico_completo) >= 4:
            padrao = tuple(self.historico_completo[-4:-1])
            self.transicoes[padrao][d] += 1
        if len(self.historico_completo) > 200: self.historico_completo = self.historico_completo[-200:]
        if len(self.numeros_completos) > 200: self.numeros_completos = self.numeros_completos[-200:]
    
    def registrar_previsao(self, duzia, confianca):
        self.ultimas_previsoes.append(duzia)
        self.ultima_previsao_duzia = duzia
        self.ultima_confianca = confianca
        if len(self.ultimas_previsoes) > 10: self.ultimas_previsoes = self.ultimas_previsoes[-10:]
    
    def registrar_resultado(self, duzia_real, acertou_duzia, acertou_numero, acertou_zero):
        self.ultimos_resultados.append({
            'duzia': duzia_real, 
            'acertou_duzia': acertou_duzia,
            'acertou_numero': acertou_numero,
            'acertou_zero': acertou_zero
        })
        self.ultimo_resultado_duzia = acertou_duzia
        self.ultimo_resultado_numero = acertou_numero
        
        if len(self.ultimos_resultados) > 20: self.ultimos_resultados = self.ultimos_resultados[-20:]
        
        if acertou_duzia and not acertou_numero and not acertou_zero:
            self.consecutivos_amarelos += 1
        else:
            self.consecutivos_amarelos = 0

        if not acertou_duzia and not acertou_zero:
            self.erros_consecutivos += 1
            if duzia_real != 0:
                self.erros_por_duzia[duzia_real] += 1
            self.modo_anti_erro = True
            if self.erros_consecutivos >= 3:
                self.pausa_ate = hora_brasilia() + timedelta(minutes=5)
                self.modo_anti_erro = False
        else:
            self.erros_consecutivos = 0
            self.modo_anti_erro = False
            self.erros_por_duzia = {1: 0, 2: 0, 3: 0}
            self.entradas_consecutivas = 0
            self.pausa_ate = None
        
        if acertou_duzia or acertou_zero: 
            self.entradas_consecutivas += 1
    
    def streak(self):
        if not self.historico: return 0, None
        last = self.historico[-1]; count = 0
        for d in reversed(self.historico):
            if d == last: count += 1
            else: break
        return count, last
    
    def frequencia(self):
        return Counter(self.historico)
    
    def _prever_markov(self):
        if len(self.historico_completo) < 3: return None
        padrao = tuple(self.historico_completo[-3:])
        if padrao in self.transicoes and self.transicoes[padrao]:
            return self.transicoes[padrao].most_common(1)[0]
        return None
    
    def _get_outras_duzias(self, duzia):
        return [d for d in [1, 2, 3] if d != duzia]
    
    def _get_duzia_ausente(self):
        freq = self.frequencia()
        u = list(self.historico)[-6:]
        freq_recente = Counter([d for d in u if d != 0])
        for dz in [1, 2, 3]:
            if freq_recente.get(dz, 0) <= 1:
                return dz
        return min(freq, key=freq.get)
    
    def _garantir_cobertura_diferente(self, previsao):
        if previsao.get('duzia_secundaria') is None or previsao['duzia_secundaria'] == previsao['duzia']:
            outras = self._get_outras_duzias(previsao['duzia'])
            previsao['duzia_secundaria'] = outras[0] if outras else previsao['duzia']
        return previsao
    
    def detectar_alerta_zero(self):
        if len(self.historico) < 2:
            self.alerta_zero_ativo = False
            return False
        
        u = list(self.historico)[-10:]
        nums = self.numeros_completos[-5:] if len(self.numeros_completos) >= 5 else self.numeros_completos
        
        if len(nums) >= 2 and nums[-1] == 0:
            self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        if len(nums) >= 3 and 0 in nums[-3:-1]:
            self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        
        if len(u) >= 3:
            ultimas_3 = u[-3:]
            if len(set(ultimas_3)) == 1 and ultimas_3[0] != 0:
                self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        
        if len(u) >= 5:
            ultimas_5 = u[-5:]
            trocas = sum(1 for i in range(1, len(ultimas_5)) 
                        if ultimas_5[i] != ultimas_5[i-1] and ultimas_5[i] != 0 and ultimas_5[i-1] != 0)
            if trocas >= 4:
                self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        
        if len(u) >= 3:
            ultimas_3 = u[-3:]
            duzias_presentes = set(d for d in ultimas_3 if d != 0)
            if len(duzias_presentes) == 3:
                self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        
        if len(u) >= 2:
            if u[-1] == u[-2] and u[-1] != 0:
                if 0 in u[-6:]:
                    self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        
        if len(u) >= 2:
            if u[-1] == u[-2] and u[-1] != 0:
                self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        
        self.alerta_zero_ativo = False
        return False
    
    def detectar_gatilhos(self):
        u = list(self.historico)
        freq = Counter([d for d in u if d != 0])
        
        if len(u) >= 4:
            ult_4 = [u[-1], u[-2], u[-3], u[-4]]
            if 0 not in ult_4:
                if ult_4[0] == ult_4[2] and ult_4[1] == ult_4[3] and ult_4[0] != ult_4[1]:
                    self.ultimo_gatilho = 'RITMO_BINARIO'
                    return {'tipo': 'RITMO_BINARIO', 'duzia': ult_4[1], 'forca': 9}

        if 0 in u[-6:]:
            pos_zero = len(u) - 1 - u[::-1].index(0)
            depois_zero = u[pos_zero+1:]
            if len(depois_zero) >= 1 and depois_zero[-1] != 0:
                self.ultimo_gatilho = 'QUEBRA_POS_ZERO'
                return {'tipo': 'QUEBRA_POS_ZERO', 'duzia': depois_zero[-1], 'forca': 8}
        
        if len(u) >= 10:
            ultimas_10 = u[-10:]
            freq_10 = Counter([d for d in ultimas_10 if d != 0])
            if freq_10:
                dom = freq_10.most_common(1)[0]
                if dom[1] >= 7 and dom[0] != 0:
                    outras = self._get_outras_duzias(dom[0])
                    freq_outras = {d: freq.get(d, 0) for d in outras}
                    dz_emergente = max(freq_outras, key=freq_outras.get)
                    if dz_emergente != 0:
                        self.ultimo_gatilho = 'EXAUSTAO_DOMINANCIA'
                        return {'tipo': 'EXAUSTAO_DOMINANCIA', 'duzia': dz_emergente, 'forca': 7}
        
        if len(u) >= 8:
            freq_1 = Counter([d for d in u[-8:-4] if d != 0])
            freq_2 = Counter([d for d in u[-4:] if d != 0])
            if freq_1 and freq_2:
                dom_1 = freq_1.most_common(1)[0]
                dom_2 = freq_2.most_common(1)[0]
                if dom_1[0] != dom_2[0] and dom_2[1] >= 3 and dom_2[0] != 0:
                    self.ultimo_gatilho = 'MUDANCA_VELOCIDADE'
                    return {'tipo': 'MUDANCA_VELOCIDADE', 'duzia': dom_2[0], 'forca': 6}
        
        return None
    
    def calcular_score(self):
        score = {1: 0, 2: 0, 3: 0}
        
        freq = self.frequencia()
        total = sum(freq.values())
        if total > 0:
            for d in score: score[d] = (freq.get(d, 0) / total) * 40
        
        streak_count, streak_d = self.streak()
        if streak_d and streak_d != 0:
            score[streak_d] += streak_count * 8
        
        markov = self._prever_markov()
        if markov and markov[0] != 0:
            score[markov[0]] += 10
        
        gatilho = self.detectar_gatilhos()
        if gatilho and gatilho['duzia'] != 0:
            score[gatilho['duzia']] += gatilho['forca'] * 2
        
        u = list(self.historico)
        if len(u) >= 2 and u[-1] == u[-2] and u[-1] != 0:
            score[u[-1]] += 30
        
        if self.modo_anti_erro and self.erros_consecutivos >= 1:
            if self.duzias_que_sairam:
                dz_real = self.duzias_que_sairam[-1]
                if dz_real != 0:
                    score[dz_real] += 25
                    if self.ultimas_previsoes:
                        dz_errada = self.ultimas_previsoes[-1]
                        if dz_errada in score:
                            score[dz_errada] *= 0.3
        
        if self.erros_consecutivos >= 2:
            dz_ausente = self._get_duzia_ausente()
            if dz_ausente != 0:
                score[dz_ausente] += 35
                for d in score:
                    if d != dz_ausente:
                        score[d] *= 0.2
        
        if 0 in u[-4:]:
            pos_zero = len(u) - 1 - u[::-1].index(0)
            depois_zero = u[pos_zero+1:]
            if depois_zero and depois_zero[-1] != 0:
                score[depois_zero[-1]] += 15
        
        total_score = sum(score.values())
        if total_score > 0:
            for d in score: score[d] = (score[d] / total_score) * 100
        
        return score, gatilho
    
    def prever(self):
        if self.pausa_ate and hora_brasilia() < self.pausa_ate:
            return {"entrar": False, "motivo": "⏸️ Pausa"}
        
        score, gatilho = self.calcular_score()
        ranking = sorted(score.items(), key=lambda x: x[1], reverse=True)
        d1, s1 = ranking[0]
        d2, s2 = ranking[1]
        
        if d2 == d1:
            outras = self._get_outras_duzias(d1)
            d2 = ranking[2][0] if len(ranking) > 2 else outras[0]
        
        self.detectar_alerta_zero()
        
        confianca = min(3.5, max(1.0, s1 / max(1, s2) * 1.5))

        u_list = list(self.historico)
        if 0 in u_list[-3:]:
            confianca *= 0.5
        
        pode_entrar = s1 > 35 or gatilho is not None or self.modo_anti_erro
        
        if self.ultimo_resultado_duzia == False and self.ultima_confianca >= 3.4:
            if d1 == self.ultima_previsao_duzia:
                d1 = d2
                s1 = s2
        
        if self.modo_anti_erro:
            if self.erros_consecutivos == 1:
                motivo = f"🔄 ANTI-ERRO: Seguindo última real"
            else:
                motivo = f"🔄 ANTI-ERRO x{self.erros_consecutivos}: Apostando na ausente"
        else:
            motivo = "" if pode_entrar else f"Score baixo ({s1:.1f})"
        
        previsao = {
            "entrar": pode_entrar,
            "motivo": motivo,
            "score": score,
            "confianca": round(confianca, 2),
            "duzia": d1,
            "duzia_secundaria": d2,
            "gatilho_ativo": gatilho['tipo'] if gatilho else None,
            "incluir_zero": self.alerta_zero_ativo,
            "modo_anti_erro": self.modo_anti_erro
        }
        
        if pode_entrar:
            previsao = self._balancear(previsao)
        
        self.ultimo_gatilho = None
        return previsao
    
    def _balancear(self, previsao):
        u = list(self.historico)
        
        if self.alerta_zero_ativo: 
            previsao['incluir_zero'] = True

        if self.consecutivos_amarelos >= 2:
            d_prim = previsao['duzia']
            d_sec = previsao['duzia_secundaria']
            previsao['duzia'] = d_sec
            previsao['duzia_secundaria'] = d_prim
        
        conf = previsao.get('confianca', 0)
        gat = previsao.get('gatilho_ativo')
        if conf >= 3.4 and not gat and not self.modo_anti_erro:
            if self.duzias_que_sairam:
                ultima_real = self.duzias_que_sairam[-1]
                if ultima_real != 0 and ultima_real != previsao['duzia']:
                    previsao['duzia'] = ultima_real
        
        for dz, erros in self.erros_por_duzia.items():
            if erros >= 3 and previsao['duzia'] == dz:
                outras = self._get_outras_duzias(dz)
                freq_outras = {d: u.count(d) for d in outras}
                previsao['duzia'] = max(freq_outras, key=freq_outras.get)
                return self._garantir_cobertura_diferente(previsao)
        
        if self.modo_anti_erro and self.ultimas_previsoes:
            dz_errada = self.ultimas_previsoes[-1]
            if previsao['duzia'] == dz_errada:
                outras = self._get_outras_duzias(dz_errada)
                freq_outras = {d: u.count(d) for d in outras}
                previsao['duzia'] = max(freq_outras, key=freq_outras.get)
        
        if len(u) >= 2 and u[-1] == u[-2] and u[-1] != 0:
            if previsao['duzia'] != u[-1]:
                previsao['duzia'] = u[-1]
        
        return self._garantir_cobertura_diferente(previsao)

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
        
        self.acertos_duzia = 0
        self.erros_duzia = 0
        self.acertos_numero = 0
        self.erros_numero = 0
        self.acertos_zero = 0
        self.erros_zero = 0
        
        self.ultimo_numero = None
        self.sinais_grafico = []
        self.numero_rodada = 0
        
        self.lucky_numbers = {}
    
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data.get('number')
            lucky_list = numero_data.get('luckyNumbers', [])
            lucky_multipliers = numero_data.get('luckyMultipliers', {})
            for ln in lucky_list:
                if ln in lucky_multipliers:
                    self.lucky_numbers[ln] = lucky_multipliers[ln]
        else:
            nr = int(numero_data)
        
        if not validar_numero(nr): return
        
        self.numero_rodada += 1
        self.duzia_ai.adicionar(nr)
        self.historico_numeros.append(nr)
        self.ultimo_numero = nr
        
        lucky_multiplier = self.lucky_numbers.get(nr, None)
        
        if self.entrada_ativa:
            duzia_real = get_duzia(nr)
            duzia_prevista = self.entrada_ativa.get('duzia_prevista')
            duzia_sec_prevista = self.entrada_ativa.get('duzia_sec_prevista')
            numeros_apostados = self.entrada_ativa.get('numeros_apostar', [])
            incluir_zero = self.entrada_ativa.get('incluir_zero', False)
            
            acerto_primaria = (duzia_real == duzia_prevista) if duzia_prevista and nr != 0 else False
            acerto_secundaria = (duzia_real == duzia_sec_prevista) if duzia_sec_prevista and nr != 0 else False
            acerto_numero_exato = nr in numeros_apostados if nr != 0 else False
            acerto_zero = (nr == 0 and incluir_zero)
            
            if acerto_zero:
                acerto_primaria = True
            
            if acerto_numero_exato:
                self.acertos_numero += 1
            elif nr != 0:
                self.erros_numero += 1
            
            if acerto_zero:
                self.acertos_zero += 1
            elif nr == 0:
                self.erros_zero += 1
            
            if acerto_primaria:
                self.acertos_duzia += 1
            elif acerto_secundaria:
                self.acertos_duzia += 0.5
            elif nr != 0:
                self.erros_duzia += 1
            
            acertou_duzia = acerto_primaria or acerto_secundaria
            self.duzia_ai.registrar_resultado(duzia_real, acertou_duzia, acerto_numero_exato, acerto_zero)
            
            if acerto_zero:
                status_visual = '🟢'
            elif acerto_numero_exato and lucky_multiplier:
                status_visual = '⚡'
            elif acerto_numero_exato:
                status_visual = '🎯'
            elif acerto_primaria:
                status_visual = '✅'
            elif acerto_secundaria:
                status_visual = '🟡'
            else:
                status_visual = '❌'
            
            self.historico_entradas.append({
                'rodada': self.numero_rodada,
                'hora': formatar_hora_brasilia(),
                'numero': nr,
                'duzia_real': duzia_real if nr != 0 else 0,
                'duzia_prevista': duzia_prevista,
                'duzia_sec_prevista': duzia_sec_prevista,
                'acerto_duzia': acertou_duzia,
                'acerto_numero': acerto_numero_exato,
                'acerto_zero': acerto_zero,
                'status': status_visual,
                'lucky_multiplier': lucky_multiplier,
                'confianca': self.entrada_ativa.get('confianca', 0),
                'gatilho': self.entrada_ativa.get('gatilho_ativo', None),
                'modo_anti_erro': self.entrada_ativa.get('modo_anti_erro', False),
                'incluir_zero': incluir_zero
            })
            if len(self.historico_entradas) > 50: self.historico_entradas = self.historico_entradas[-50:]
            enviar_resultado_auto(nr, acertou_duzia, acerto_numero_exato, acerto_zero, lucky_multiplier)
            self.entrada_ativa = None
        
        previsao = self.duzia_ai.prever()
        
        if previsao['entrar']:
            duzia_map = {1: list(range(1,13)), 2: list(range(13,25)), 3: list(range(25,37))}
            numeros_principais = duzia_map.get(previsao['duzia'], [])
            numeros_secundarios = duzia_map.get(previsao.get('duzia_secundaria', previsao['duzia']), [])
            
            if st.session_state.get('modo_agressivo', False) and previsao.get('duzia_secundaria') and previsao['duzia_secundaria'] != previsao['duzia']:
                numeros_apostar = list(set(numeros_principais + numeros_secundarios))
            else:
                numeros_apostar = numeros_principais
            
            if previsao.get('incluir_zero', False) and 0 not in numeros_apostar:
                numeros_apostar = [0] + numeros_apostar
            
            self.entrada_ativa = {
                'numeros_apostar': numeros_apostar,
                'duzia_prevista': previsao['duzia'],
                'duzia_sec_prevista': previsao.get('duzia_secundaria'),
                'confianca': previsao.get('confianca', 0),
                'gatilho_ativo': previsao.get('gatilho_ativo'),
                'modo_anti_erro': previsao.get('modo_anti_erro', False),
                'incluir_zero': previsao.get('incluir_zero', False)
            }
            
            self.duzia_ai.registrar_previsao(previsao['duzia'], previsao['confianca'])
            idx_atual = len(self.historico_numeros) - 1
            self.sinais_grafico.append((idx_atual, previsao['duzia']))
            enviar_previsao_auto({
                'numeros_apostar': numeros_apostar, 
                'incluir_zero': previsao.get('incluir_zero', False)
            })
    
    def zerar(self):
        self.acertos_duzia = 0; self.erros_duzia = 0
        self.acertos_numero = 0; self.erros_numero = 0
        self.acertos_zero = 0; self.erros_zero = 0
        self.historico_entradas = []; self.historico_numeros.clear()
        self.entrada_ativa = None; self.ultimo_numero = None
        self.sinais_grafico = []; self.numero_rodada = 0
        self.lucky_numbers = {}
        janela = st.session_state.get('janela_duzia_ai', 30)
        self.duzia_ai = DuziaAI(window=janela)
        salvar_sessao()

# =============================
# FUNÇÕES AUXILIARES
# =============================
def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    try:
        with open(caminho, "w", encoding='utf-8') as f: json.dump(historico, f, indent=2)
    except Exception as e: logging.error(f"Erro: {e}")

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
        logging.warning(f"Erro API: {e}")
        return None

def exportar_historico_csv(historico_entradas, caminho="export_roleta.csv"):
    import csv
    try:
        with open(caminho, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Rod','Hora','Nº','Tipo','Real','Prev','Cob','Conf','Gat','Z','🔄','Duz','Num','Zero','Res'])
            for e in historico_entradas:
                nr = e.get('numero', '-')
                lucky = e.get('lucky_multiplier')
                if nr == 0:
                    tipo = '0'
                elif lucky:
                    tipo = f'RAIO {lucky}X'
                else:
                    tipo = 'Normal'
                real = f"D{e.get('duzia_real',0)}" if e.get('duzia_real',0)!=0 else "0"
                prev = f"D{e.get('duzia_prevista','?')}"
                cob = f"D{e.get('duzia_sec_prevista','?')}" if e.get('duzia_sec_prevista') and e.get('duzia_sec_prevista') != e.get('duzia_prevista') else "-"
                zero = 'S' if e.get('incluir_zero') else 'N'
                anti = 'S' if e.get('modo_anti_erro') else 'N'
                duz = 'S' if e.get('acerto_duzia') else 'N'
                num = 'S' if e.get('acerto_numero') else 'N'
                zer = 'S' if e.get('acerto_zero') else 'N'
                writer.writerow([
                    e.get('rodada'), e.get('hora'), nr, tipo, real,
                    prev, cob, f"{e.get('confianca',0):.1f}",
                    e.get('gatilho','-') if e.get('gatilho') else '-', zero, anti,
                    duz, num, zer, e.get('status','?')
                ])
        return True
    except Exception as e: logging.error(f"Erro CSV: {e}"); return False

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎰 DuziaAI V10.9 - Raio X", layout="wide")
st.title("🎰 DuziaAI V10.9 - CONFERÊNCIA DUPLA + RAIO X")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    sis = st.session_state.sistema
    for n in dados.get('historico_numeros', []):
        sis.duzia_ai.adicionar(n); sis.historico_numeros.append(n)
    sis.historico_entradas = dados.get('historico_entradas', [])
    sis.numero_rodada = dados.get('numero_rodada', len(dados.get('historico_numeros', [])))
    sis.acertos_duzia = dados.get('acertos_duzia', 0)
    sis.erros_duzia = dados.get('erros_duzia', 0)
    sis.acertos_numero = dados.get('acertos_numero', 0)
    sis.erros_numero = dados.get('erros_numero', 0)
    sis.acertos_zero = dados.get('acertos_zero', 0)
    sis.erros_zero = dados.get('erros_zero', 0)
    sis.entrada_ativa = dados.get('entrada_ativa', None)
    st.session_state.modo_agressivo = dados.get('modo_agressivo', False)
    if os.path.exists(ENTRADAS_PATH):
        try:
            with open(ENTRADAS_PATH, 'r') as f: sis.historico_entradas = json.load(f)
        except: pass

defaults = {'modo_automatico': True, 'modo_agressivo': False, 'janela_duzia_ai': 30}
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
    st.markdown("## ⚙️ V10.9 - RAIO X")
    if st.button("🆕 NOVA SESSÃO", use_container_width=True, type="primary"):
        if nova_sessao(): st.success("✅ Nova sessão!"); st.rerun()
    st.markdown("---")
    st.session_state.janela_duzia_ai = st.slider("📏 Janela", 10, 50, st.session_state.janela_duzia_ai, 5)
    st.session_state.modo_agressivo = st.checkbox("🔥 Modo Agressivo (2 Dúzias)", value=st.session_state.modo_agressivo)
    st.session_state.modo_automatico = st.checkbox("🤖 Auto", value=st.session_state.modo_automatico)
    st.markdown("---")
    st.caption("📊 LEGENDA:")
    st.caption("  ⚡ Número RAIO (com multiplicador)")
    st.caption("  🎯 Nº Exato Normal")
    st.caption("  ✅ Dúzia principal")
    st.caption("  🟡 Cobertura")
    st.caption("  🟢 Zero")
    st.caption("  ❌ Erro")
    st.markdown("---")
    with st.expander("🔔 Telegram"):
        st.session_state.telegram_token = st.text_input("Token", value=st.session_state.telegram_token, type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID", value=st.session_state.telegram_chat_id)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("💾 Salvar", use_container_width=True): 
            salvar_resultado_em_arquivo(st.session_state.historico); salvar_sessao(); st.success("✅")
    with c2:
        if st.button("🗑️ Zerar", use_container_width=True): 
            st.session_state.sistema.zerar(); st.rerun()
    with c3:
        if st.button("📥 CSV", use_container_width=True):
            if exportar_historico_csv(st.session_state.sistema.historico_entradas): st.success("✅")

# Conteúdo principal
st.subheader("🎲 Inserir Números")
c1, c2, c3 = st.columns([3,1,1])
with c1:
    entrada = st.text_input("Número (0-36):", key="entrada_numero")
with c2:
    if st.button("🎯 Enviar", use_container_width=True, type="primary"):
        if validar_numero(entrada):
            nr = int(entrada)
            st.session_state.historico.append({"number": nr, "timestamp": timestamp_brasilia(), "luckyNumbers": [], "luckyMultipliers": {}})
            st.session_state.sistema.processar_novo_numero(nr)
            salvar_resultado_em_arquivo(st.session_state.historico); salvar_sessao(); st.rerun()
        else: st.error("0-36")
with c3:
    if st.button("🔄 Auto", use_container_width=True):
        st.session_state.modo_automatico = not st.session_state.modo_automatico; st.rerun()

if st.session_state.modo_automatico:
    st_autorefresh(interval=3000, key="auto")
    r = fetch_latest_result()
    if r and r.get("number") is not None:
        if not st.session_state.historico or r["timestamp"] != st.session_state.historico[-1].get("timestamp"):
            st.session_state.historico.append(r)
            st.session_state.sistema.processar_novo_numero(r)
            salvar_resultado_em_arquivo(st.session_state.historico); salvar_sessao(); st.rerun()

st.markdown("---")
sis = st.session_state.sistema

# Métricas
st.subheader("📊 CONFERÊNCIA DUPLA")
c1, c2, c3, c4, c5, c6 = st.columns(6)
total_duzias = int(sis.acertos_duzia + sis.erros_duzia)
tx_duzias = (sis.acertos_duzia / total_duzias * 100) if total_duzias > 0 else 0
total_numeros = sis.acertos_numero + sis.erros_numero
tx_numeros = (sis.acertos_numero / total_numeros * 100) if total_numeros > 0 else 0

c1.metric("🎯 Nº Exato", sis.acertos_numero, f"{tx_numeros:.0f}%")
c2.metric("✅ Acertos Dúzia", int(sis.acertos_duzia), f"{tx_duzias:.0f}%")
c3.metric("❌ Erros Dúzia", sis.erros_duzia)
c4.metric("🟢 Zeros", f"{sis.acertos_zero}/{sis.acertos_zero + sis.erros_zero}")
c5.metric("📦 Total", total_duzias)
pausado = sis.duzia_ai.pausa_ate and hora_brasilia() < sis.duzia_ai.pausa_ate
c6.metric("⏸️", "⏸️" if pausado else "▶️")

if pausado: 
    st.error(f"⏸️ Pausa até {formatar_hora_brasilia(sis.duzia_ai.pausa_ate)}")

st.markdown("---")
cg, ce = st.columns([3,2])

with cg:
    st.subheader("📈 Scores")
    if len(sis.historico_numeros) >= 3:
        score, gatilho = sis.duzia_ai.calcular_score()
        fig = plt.Figure(data=[plt.Bar(
            x=['D1', 'D2', 'D3'], 
            y=[score[1], score[2], score[3]],
            marker_color=['#FF6B6B' if score[1]==max(score.values()) else '#4ECDC4',
                          '#FF6B6B' if score[2]==max(score.values()) else '#4ECDC4',
                          '#FF6B6B' if score[3]==max(score.values()) else '#4ECDC4'],
            text=[f'{score[1]:.0f}', f'{score[2]:.0f}', f'{score[3]:.0f}'], 
            textposition='auto'
        )])
        titulo = f"🎯 {'⚠️ GATILHO: '+gatilho['tipo'] if gatilho else 'Sem gatilho'}"
        if sis.duzia_ai.alerta_zero_ativo: titulo += " | 🟢 ALERTA ZERO!"
        fig.update_layout(title=titulo, height=250, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        if len(sis.historico_numeros) >= 8:
            ult = list(sis.historico_numeros)[-20:]
            dz_hist = [get_duzia(n) for n in ult]
            fig2 = plt.Figure()
            fig2.add_trace(plt.Scatter(
                x=list(range(len(dz_hist))), y=dz_hist, 
                mode='lines+markers', line=dict(color='#FFD700', width=2),
                marker=dict(size=10)
            ))
            if sis.sinais_grafico:
                sx, sy = [], []
                off = len(dz_hist) - 20
                for idx, dz in sis.sinais_grafico:
                    pos = idx - off
                    if 0 <= pos < 20: sx.append(pos); sy.append(dz)
                if sx: 
                    fig2.add_trace(plt.Scatter(
                        x=sx, y=sy, mode='markers', name='Sinal', 
                        marker=dict(symbol='star', size=15, color='red')
                    ))
            fig2.update_layout(
                title="📉 Histórico", 
                yaxis=dict(tickvals=[0,1,2,3], ticktext=['0','D1','D2','D3'], range=[-0.5, 3.5]), 
                height=250
            )
            st.plotly_chart(fig2, use_container_width=True)

with ce:
    st.subheader("🎰 Entrada Atual")
    if sis.duzia_ai.alerta_zero_ativo:
        st.warning("⚠️ ALERTA ZERO! 🟢")
    
    if sis.entrada_ativa:
        e = sis.entrada_ativa
        conf = e.get('confianca', 0)
        dz_princ = e.get('duzia_prevista', 0)
        dz_sec = e.get('duzia_sec_prevista')
        gat = e.get('gatilho_ativo')
        nums = e.get('numeros_apostar', [])
        
        cor = "#FF6347" if e.get('modo_anti_erro') else "#FFD700"
        
        st.markdown(f"""
        <div style="background-color:{cor}15; border:2px solid {cor}; border-radius:15px; padding:15px;">
            <h2 style="color:{cor}; text-align:center;">🎯 D{dz_princ}</h2>
            <p style="text-align:center; font-size:1.1em;">Confiança: {conf:.2f} {'| 🎯 '+gat if gat else ''}</p>
            {f'<p style="text-align:center; color:#FFA500;">🛡️ Cobertura: D{dz_sec}</p>' if dz_sec != dz_princ else ''}
        </div>""", unsafe_allow_html=True)
        
        if nums:
            st.write("**🎲 Apostar em:**")
            cols = st.columns(7)
            for i, n in enumerate(sorted(nums)):
                label = "🟢0" if n==0 else str(n)
                cols[i%7].button(label, key=f"n{n}", use_container_width=True)
        st.progress(min(1.0, max(0.0, conf/5.0)))
    else:
        st.info("🔍 Aguardando sinal...")
    
    if sis.ultimo_numero is not None:
        st.markdown("---")
        lucky = sis.lucky_numbers.get(sis.ultimo_numero)
        if sis.ultimo_numero == 0:
            st.write(f"**🔄 Último:** 🟢 ZERO")
        elif lucky:
            st.markdown(f"**🔄 Último:** ⚡ **#{sis.ultimo_numero}** (D{get_duzia(sis.ultimo_numero)}) **RAIO {lucky}X!**")
        else:
            st.write(f"**🔄 Último:** #{sis.ultimo_numero} (D{get_duzia(sis.ultimo_numero)})")

st.markdown("---")
st.subheader("📝 Histórico")
if sis.historico_entradas:
    # 🆕 TABELA HTML PERSONALIZADA COM INFORMAÇÕES DE RAIO
    html = """
    <style>
    .hist-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .hist-table th { background-color: #1a1a2e; color: #FFD700; padding: 8px; text-align: center; border-bottom: 2px solid #FFD700; }
    .hist-table td { padding: 6px; text-align: center; border-bottom: 1px solid #333; }
    .hist-table tr:hover { background-color: #2a2a4e; }
    .raio-row { background-color: #FFD70015; }
    .zero-row { background-color: #00FF0015; }
    .acerto-num { color: #00FF00; font-weight: bold; }
    .acerto-duz { color: #FFD700; }
    .erro { color: #FF4444; }
    .raio-num { color: #FFD700; font-weight: bold; font-size: 15px; }
    .normal-num { color: #CCCCCC; }
    </style>
    <table class="hist-table">
    <tr>
        <th>Rod</th><th>Hora</th><th>Nº Sorteado</th><th>Tipo</th>
        <th>Prev</th><th>Cob</th><th>Conf</th><th>Gat</th>
        <th>Z</th><th>🔄</th><th>Dúzia</th><th>Nº</th><th>Zero</th><th>Res</th>
    </tr>
    """
    
    for e in reversed(sis.historico_entradas[-20:]):
        nr = e.get('numero', '-')
        lucky = e.get('lucky_multiplier')
        
        # Determinar classe da linha
        row_class = ""
        if nr == 0:
            row_class = "zero-row"
            num_display = "0"
            tipo_display = "ZERO"
        elif lucky:
            row_class = "raio-row"
            num_display = f"<span class='raio-num'>⚡ {nr}</span>"
            tipo_display = f"<span class='raio-num'>RAIO {lucky}X</span>"
        else:
            num_display = f"<span class='normal-num'>{nr}</span>"
            tipo_display = "Normal"
        
        real = f"D{e.get('duzia_real',0)}" if e.get('duzia_real',0)!=0 else "0"
        prev = f"D{e.get('duzia_prevista','?')}"
        cob = f"D{e.get('duzia_sec_prevista','?')}" if e.get('duzia_sec_prevista') and e.get('duzia_sec_prevista') != e.get('duzia_prevista') else "-"
        zero = '🟢' if e.get('incluir_zero') else '-'
        anti = '🔄' if e.get('modo_anti_erro') else '-'
        
        duz_class = "acerto-duz" if e.get('acerto_duzia') else "erro"
        duz = '✅' if e.get('acerto_duzia') else '❌'
        
        num_class = "acerto-num" if e.get('acerto_numero') else ""
        num_ok = '🎯' if e.get('acerto_numero') else '-'
        
        zer_ok = '🟢' if e.get('acerto_zero') else '-'
        
        status = e.get('status','?')
        status_class = "acerto-num" if status in ['🎯','⚡'] else "acerto-duz" if status in ['✅','🟡'] else "erro"
        
        html += f"""
        <tr class="{row_class}">
            <td>{e.get('rodada','-')}</td>
            <td>{e.get('hora','-')}</td>
            <td>{num_display}</td>
            <td>{tipo_display}</td>
            <td>{prev}</td>
            <td>{cob}</td>
            <td>{e.get('confianca',0):.1f}</td>
            <td>{e.get('gatilho','-') if e.get('gatilho') else '-'}</td>
            <td>{zero}</td>
            <td>{anti}</td>
            <td class="{duz_class}">{duz}</td>
            <td class="{num_class}">{num_ok}</td>
            <td>{zer_ok}</td>
            <td class="{status_class}">{status}</td>
        </tr>
        """
    
    html += "</table>"
    st.markdown(html, unsafe_allow_html=True)
    
    if st.button("📥 Exportar CSV", use_container_width=True):
        if exportar_historico_csv(sis.historico_entradas): st.success("✅")
else: 
    st.info("Nenhuma entrada.")

st.caption(f"🤖 DuziaAI V10.9 | Conferência Dupla + Raio X | {formatar_hora_brasilia()}")
salvar_sessao()
