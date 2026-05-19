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

# Importação Segura do Módulo de Machine Learning
try:
    from sklearn.ensemble import RandomForestClassifier
    ML_DISPONIVEL = True
except ImportError:
    ML_DISPONIVEL = False

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
            'api_selecionada': st.session_state.get('api_selecionada', 'XXXtreme Lightning'),
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

def _selecionar_melhores_numeros(duzia, numeros_completos, quantidade=6):
    """Seleciona dinamicamente os melhores números com base nos terminais quentes recentes."""
    if duzia == 1:
        numeros_da_duzia = list(range(1, 13))
    elif duzia == 2:
        numeros_da_duzia = list(range(13, 25))
    else:
        numeros_da_duzia = list(range(25, 37))
    
    recentes = numeros_completos[-20:] if len(numeros_completos) >= 20 else numeros_completos
    freq = Counter([n for n in recentes if n in numeros_da_duzia])
    termos = [n % 10 for n in recentes[-15:] if n != 0]
    terminais_quentes = [t for t, f in Counter(termos).most_common(3) if f >= 2]
    
    pontuacao = {}
    for num in numeros_da_duzia:
        score = freq.get(num, 0) * 3
        if num % 10 in terminais_quentes:
            score += 2
        if num in recentes[-5:]:
            score += 1
        pontuacao[num] = score
    
    melhores = sorted(pontuacao.items(), key=lambda x: x[1], reverse=True)
    selecionados = [n for n, s in melhores[:quantidade] if s > 0]
    
    if len(selecionados) < quantidade:
        for num in numeros_da_duzia:
            if num not in selecionados:
                selecionados.append(num)
                if len(selecionados) >= quantidade:
                    break
    
    return sorted(selecionados[:quantidade])


def enviar_previsao_auto(previsao):
    try:
        numeros = sorted(previsao.get('numeros_apostar', []))
        incluir_zero = previsao.get('incluir_zero', False)
        duzia_principal = previsao.get('duzia', 0)
        duzia_secundaria = previsao.get('duzia_secundaria', 0)
        
        d1n = [n for n in numeros if 1 <= n <= 12]
        d2n = [n for n in numeros if 13 <= n <= 24]
        d3n = [n for n in numeros if 25 <= n <= 36]
        
        prefixo = "⚠️🎯 " if incluir_zero else "🎯 "
        
        if d1n and d2n: msg = f"{prefixo}Entrada: D1 (1-12) | Cob: D2 (13-24)"
        elif d1n and d3n: msg = f"{prefixo}Entrada: D1 (1-12) | Cob: D3 (25-36)"
        elif d2n and d3n: msg = f"{prefixo}Entrada: D2 (13-24) | Cob: D3 (25-36)"
        elif d1n: msg = f"{prefixo}Entrada: D1 (1-12)"
        elif d2n: msg = f"{prefixo}Entrada: D2 (13-24)"
        elif d3n: msg = f"{prefixo}Entrada: D3 (25-36)"
        else: msg = f"{prefixo}Entrada: {numeros}"
        
        if incluir_zero: msg += " + 🟢 ZERO"
        
        numeros_completos = previsao.get('numeros_completos', [])
        
        melhores_principal = _selecionar_melhores_numeros(duzia_principal, numeros_completos, 6)
        
        if duzia_secundaria and duzia_secundaria != duzia_principal:
            melhores_secundaria = _selecionar_melhores_numeros(duzia_secundaria, numeros_completos, 6)
            melhores_str = " ".join(map(str, sorted(set(melhores_principal + melhores_secundaria))))
        else:
            melhores_str = " ".join(map(str, melhores_principal))
        
        st.toast(msg)
        
        # Telegram Principal
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(
                f"🔔 {msg}\n🔢 {melhores_str}",
                st.session_state.telegram_token,
                st.session_state.telegram_chat_id
            )
        
        # Telegram Alternativo
        if st.session_state.get('telegram_token_alt') and st.session_state.get('telegram_chat_id_alt'):
            msg_alt = f"🎯 Entrada: {melhores_str}"
            if incluir_zero:
                msg_alt += " + 🟢 ZERO"
            enviar_telegram(
                msg_alt,
                st.session_state.telegram_token_alt,
                st.session_state.telegram_chat_id_alt
            )
        
        salvar_sessao()
    except Exception as e: logging.error(f"Erro: {e}")

def enviar_resultado_auto(numero_real, acerto_duzia, acerto_numero, acerto_zero, eh_raio=False, multiplicador=0):
    try:
        partes = []
        if acerto_zero:
            partes.append("✅ ZERO!")
        elif numero_real == 0:
            partes.append("🟢 ZERO (não apostado)")
        else:
            duzia_real = get_duzia(numero_real)
            if acerto_numero:
                if eh_raio:
                    partes.append(f"⚡ RAIO {multiplicador}X! Nº {numero_real}")
                else:
                    partes.append(f"🎯 Nº EXATO {numero_real}!")
            elif acerto_duzia:
                partes.append(f"✅ Green - D{duzia_real}")
            else:
                partes.append(f"❌ Nº {numero_real} (D{duzia_real})")
        
        msg = " | ".join(partes)
        st.toast(msg)
        
        # Telegram Principal
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(
                f"📢 Resultado: {msg}",
                st.session_state.telegram_token,
                st.session_state.telegram_chat_id
            )
        
        # Telegram Alternativo
        if st.session_state.get('telegram_token_alt') and st.session_state.get('telegram_chat_id_alt'):
            if acerto_duzia or acerto_zero:
                if acerto_numero and eh_raio:
                    msg_alt = f"⚡ GREEN RAIO {multiplicador}X! Nº {numero_real}"
                elif acerto_numero:
                    msg_alt = f"🎯 GREEN! Nº {numero_real}"
                elif acerto_zero:
                    msg_alt = "🟢 GREEN ZERO!"
                else:
                    msg_alt = f"✅ GREEN - D{get_duzia(numero_real)}"
            else:
                msg_alt = f"❌ RED - Nº {numero_real}"
            
            enviar_telegram(
                msg_alt,
                st.session_state.telegram_token_alt,
                st.session_state.telegram_chat_id_alt
            )
        
        salvar_sessao()
    except Exception as e: logging.error(f"Erro: {e}")

def enviar_telegram(mensagem, token, chat_id):
    try:
        if not token or not chat_id: return
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e: logging.error(f"Erro Telegram: {e}")

# =============================
# API - 3 ROULETES
# =============================

API_URLS = {
    'XXXtreme Lightning': "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest",
    'Immersive Roulette': "https://api.casinoscores.com/svc-evolution-game-events/api/immersiveroulette/latest",
    'Mega Roulette': "https://api.casinoscores.com/svc-evolution-game-events/api/megaroulette/latest",
}

def get_api_url():
    api_selecionada = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
    return API_URLS.get(api_selecionada, API_URLS['XXXtreme Lightning'])

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
# 🧠 DUZIA AI V10.9.8 - COM ML + FILTROS DE ERRO + RAIOS
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
        
        # Controle de fadiga de dúzia
        self.acertos_consecutivos_mesma_duzia = 0
        self.ultima_duzia_acertada = None
        
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
        
        # Controle de fadiga
        if acertou_duzia and duzia_real != 0:
            if duzia_real == self.ultima_duzia_acertada:
                self.acertos_consecutivos_mesma_duzia += 1
            else:
                self.acertos_consecutivos_mesma_duzia = 1
                self.ultima_duzia_acertada = duzia_real
        else:
            self.acertos_consecutivos_mesma_duzia = 0
            self.ultima_duzia_acertada = None
        
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

    # MACHINE LEARNING
    def _prever_ml(self):
        if not ML_DISPONIVEL or len(self.historico_completo) < 25:
            return {1: 0.0, 2: 0.0, 3: 0.0}
        try:
            X, y = [], []
            hist = list(self.historico_completo)
            for i in range(4, len(hist)):
                if hist[i] in [1, 2, 3]:
                    X.append([hist[i-1], hist[i-2], hist[i-3], hist[i-4]])
                    y.append(hist[i])
            if len(set(y)) < 2:
                return {1: 0.0, 2: 0.0, 3: 0.0}
            clf = RandomForestClassifier(n_estimators=40, max_depth=4, random_state=42)
            clf.fit(X, y)
            estado_atual = [[hist[-1], hist[-2], hist[-3], hist[-4]]]
            probabilidades = clf.predict_proba(estado_atual)[0]
            ml_scores = {1: 0.0, 2: 0.0, 3: 0.0}
            for classe, prob in zip(clf.classes_, probabilidades):
                if classe in ml_scores:
                    ml_scores[classe] = float(prob) * 35
            return ml_scores
        except Exception as e:
            logging.warning(f"Erro ML: {e}")
            return {1: 0.0, 2: 0.0, 3: 0.0}
    
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
    
    # ALERTA ZERO - 7 REGRAS
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
    
    def detectar_embalo(self):
        u = list(self.historico)[-4:]
        if len(u) < 3:
            return None
        freq = Counter([d for d in u if d != 0])
        if freq:
            dom = freq.most_common(1)[0]
            if dom[1] >= 3 and dom[0] != 0:
                return {'tipo': 'EMBALO', 'duzia': dom[0], 'forca': 9}
        return None
    
    def detectar_ritmo_ping_pong(self):
        u = list(self.historico)[-6:]
        if len(u) < 4:
            return None
        pares = {}
        for i in range(1, len(u)):
            if u[i] != u[i-1] and u[i] != 0 and u[i-1] != 0:
                par = tuple(sorted([u[i], u[i-1]]))
                pares[par] = pares.get(par, 0) + 1
        if pares:
            par_principal = max(pares, key=pares.get)
            count = pares[par_principal]
            if count >= 4:
                dz1, dz2 = par_principal
                ultima = u[-1]
                proxima = dz2 if ultima == dz1 else dz1
                if proxima != 0:
                    return {'tipo': 'RITMO_PING_PONG', 'duzia': proxima, 'forca': 9}
        return None
    
    # ========== GATILHOS ==========
    def detectar_gatilhos(self):
        u = list(self.historico)
        freq = Counter([d for d in u if d != 0])
        
        embalo = self.detectar_embalo()
        if embalo:
            self.ultimo_gatilho = 'EMBALO'
            return embalo
        
        ping_pong = self.detectar_ritmo_ping_pong()
        if ping_pong:
            self.ultimo_gatilho = 'RITMO_PING_PONG'
            return ping_pong
        
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
            
        ml_scores = self._prever_ml()
        for d in score:
            score[d] += ml_scores.get(d, 0.0)
        
        gatilho = self.detectar_gatilhos()
        if gatilho and gatilho['duzia'] != 0:
            score[gatilho['duzia']] += gatilho['forca'] * 2
        
        if gatilho and gatilho['tipo'] in ('RITMO_PING_PONG', 'EMBALO'):
            score[gatilho['duzia']] += 5
        
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

        if self.alerta_zero_ativo and confianca >= 3.4:
            confianca = min(3.3, confianca)
        
        u_list = list(self.historico)
        if 0 in u_list[-3:]:
            confianca *= 0.5
        
        pode_entrar = s1 > 35 or gatilho is not None or self.modo_anti_erro
        motivo = ""
        
        # Kill Switch de Teimosia
        if self.ultimo_resultado_duzia == False and self.ultima_confianca >= 3.4:
            if d1 == self.ultima_previsao_duzia:
                d1 = d2
                s1 = s2
        
        # 🆕 FILTRO 1: EMBALO + Confiança Alta + Alerta Zero = BLOQUEAR
        if gatilho and gatilho['tipo'] == 'EMBALO' and confianca >= 3.3 and self.alerta_zero_ativo:
            pode_entrar = False
            motivo = "🚫 EMBALO + Conf Alta + Zero: Alto risco de erro"
        
        # 🆕 FILTRO 2: Anti-Erro + Alerta Zero + Confiança Baixa = BLOQUEAR
        if self.modo_anti_erro and self.alerta_zero_ativo and confianca < 2.5:
            pode_entrar = False
            motivo = "🚫 Anti-Erro + Zero + Conf Baixa: Aguardar próximo giro"
        
        # Filtro: EXAUSTAO + Alerta Zero (sem anti-erro)
        if gatilho and gatilho['tipo'] == 'EXAUSTAO_DOMINANCIA' and self.alerta_zero_ativo and not self.modo_anti_erro:
            pode_entrar = False
            motivo = "🚫 EXAUSTAO + Zero: Padrão de alto risco"
        
        if self.modo_anti_erro:
            if self.erros_consecutivos == 1:
                motivo = f"🔄 ANTI-ERRO: Seguindo última real" if not motivo else motivo
            else:
                motivo = f"🔄 ANTI-ERRO x{self.erros_consecutivos}: Apostando na ausente" if not motivo else motivo
        else:
            if not motivo:
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
            "modo_anti_erro": self.modo_anti_erro,
            "numeros_completos": list(self.numeros_completos)
        }
        
        if pode_entrar:
            previsao = self._balancear(previsao)
        
        self.ultimo_gatilho = None
        return previsao
    
    def _balancear(self, previsao):
        u = list(self.historico)
        
        if self.alerta_zero_ativo: 
            previsao['incluir_zero'] = True

        if self.acertos_consecutivos_mesma_duzia >= 4 and self.ultima_duzia_acertada is not None:
            duzia_fadigada = self.ultima_duzia_acertada
            if previsao['duzia'] == duzia_fadigada:
                outras = self._get_outras_duzias(duzia_fadigada)
                freq_outras = {d: u.count(d) for d in outras}
                duzia_mudanca = max(freq_outras, key=freq_outras.get)
                logging.info(f"🔄 FADIGA D{duzia_fadigada}: Mudando para D{duzia_mudanca}")
                previsao['duzia'] = duzia_mudanca
        
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
    
    def processar_novo_numero(self, numero_data):
        # 🆕 Extrair número E raios do dicionário
        if isinstance(numero_data, dict):
            nr = numero_data.get('number')
            lucky_numbers = numero_data.get('luckyNumbers', [])
            lucky_multipliers = numero_data.get('luckyMultipliers', {})
        else:
            nr = numero_data
            lucky_numbers = []
            lucky_multipliers = {}
        
        if nr is None or not validar_numero(nr): return
        
        # 🆕 Verificar se é raio
        eh_raio = nr in lucky_numbers
        multiplicador = lucky_multipliers.get(nr, 0) if eh_raio else 0
        
        self.numero_rodada += 1
        self.duzia_ai.adicionar(nr)
        self.historico_numeros.append(nr)
        self.ultimo_numero = nr
        
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
            elif acerto_numero_exato and eh_raio:
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
                'rodada': self.numero_rodada, 'hora': formatar_hora_brasilia(),
                'numero': nr, 'duzia_real': duzia_real if nr != 0 else 0,
                'duzia_prevista': duzia_prevista, 'duzia_sec_prevista': duzia_sec_prevista,
                'acerto_duzia': acerto_primaria or acerto_secundaria,
                'acerto_numero': acerto_numero_exato,
                'acerto_zero': acerto_zero,
                'eh_raio': eh_raio,
                'multiplicador': multiplicador,
                'status': status_visual,
                'confianca': self.entrada_ativa.get('confianca', 0),
                'gatilho': self.entrada_ativa.get('gatilho_ativo', None),
                'modo_anti_erro': self.entrada_ativa.get('modo_anti_erro', False),
                'incluir_zero': incluir_zero
            })
            if len(self.historico_entradas) > 50: self.historico_entradas = self.historico_entradas[-50:]
            enviar_resultado_auto(nr, acertou_duzia, acerto_numero_exato, acerto_zero, eh_raio, multiplicador)
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
                'incluir_zero': previsao.get('incluir_zero', False),
                'duzia': previsao['duzia'],
                'duzia_secundaria': previsao.get('duzia_secundaria', previsao['duzia']),
                'numeros_completos': list(self.historico_numeros)
            })
    
    def zerar(self):
        self.acertos_duzia = 0; self.erros_duzia = 0
        self.acertos_numero = 0; self.erros_numero = 0
        self.acertos_zero = 0; self.erros_zero = 0
        self.historico_entradas = []; self.historico_numeros.clear()
        self.entrada_ativa = None; self.ultimo_numero = None
        self.sinais_grafico = []; self.numero_rodada = 0
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
        url = get_api_url()
        r = requests.get(url, headers=HEADERS, timeout=5)
        r.raise_for_status()
        d = r.json()
        
        api_selecionada = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        
        # 🆕 Tratamento separado para cada API
        if api_selecionada in ('XXXtreme Lightning', 'Mega Roulette'):
            # Formato com raios (XXXtreme Lightning e Mega Roulette)
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
        else:
            # Formato Immersive Roulette (sem raios)
            data = d.get("data", {})
            result = data.get("result", {})
            outcome = result.get("outcome", {})
            nm = outcome.get("number")
            ts = data.get("startedAt")
            return {"number": nm, "timestamp": ts, "luckyNumbers": [], "luckyMultipliers": {}}
    except Exception as e:
        logging.warning(f"Erro API: {e}")
        return None

def exportar_historico_csv(historico_entradas, caminho="export_roleta.csv"):
    import csv
    try:
        with open(caminho, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Rod','Hora','Nº','Raio','Real','Prev','Cob','Conf','Gat','Z','🔄','Duz','Num','Zer','St'])
            for e in historico_entradas:
                real = f"D{e.get('duzia_real',0)}" if e.get('duzia_real',0)!=0 else "0"
                prev = f"D{e.get('duzia_prevista','?')}"
                cob = f"D{e.get('duzia_sec_prevista','?')}" if e.get('duzia_sec_prevista') and e.get('duzia_sec_prevista') != e.get('duzia_prevista') else "-"
                zero = '🟢' if e.get('incluir_zero') else '-'
                anti = '🔄' if e.get('modo_anti_erro') else '-'
                duz = '✅' if e.get('acerto_duzia') else '❌'
                num = '✅' if e.get('acerto_numero') else '-'
                zer = '✅' if e.get('acerto_zero') else '-'
                raio = f"⚡{e.get('multiplicador',0)}x" if e.get('eh_raio') else '-'
                writer.writerow([
                    e.get('rodada'), e.get('hora'), e.get('numero'), raio, real,
                    prev, cob, f"{e.get('confianca',0):.1f}",
                    e.get('gatilho','-') if e.get('gatilho') else '-', zero, anti,
                    duz, num, zer, e.get('status','?')
                ])
        return True
    except Exception as e: logging.error(f"Erro CSV: {e}"); return False

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎰 DuziaAI V10.9.8 - Raios + Filtros", layout="wide")
st.title("🎰 DuziaAI V10.9.8 - RAIOS + FILTROS DE ERRO (BRT)")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    sis = st.session_state.sistema
    for n in dados.get('historico_numeros', []):
        sis.duzia_ai.adicionar(n); sis.historico_numeros.append(n)
    sis.numero_rodada = dados.get('numero_rodada', len(dados.get('historico_numeros', [])))
    sis.acertos_duzia = dados.get('acertos_duzia', 0)
    sis.erros_duzia = dados.get('erros_duzia', 0)
    sis.acertos_numero = dados.get('acertos_numero', 0)
    sis.erros_numero = dados.get('erros_numero', 0)
    sis.acertos_zero = dados.get('acertos_zero', 0)
    sis.erros_zero = dados.get('erros_zero', 0)
    sis.entrada_ativa = dados.get('entrada_ativa', None)
    st.session_state.modo_agressivo = dados.get('modo_agressivo', False)
    st.session_state.api_selecionada = dados.get('api_selecionada', 'XXXtreme Lightning')
    if os.path.exists(ENTRADAS_PATH):
        try:
            with open(ENTRADAS_PATH, 'r') as f: sis.historico_entradas = json.load(f)
        except: pass

defaults = {'modo_automatico': True, 'modo_agressivo': False, 'janela_duzia_ai': 30, 'api_selecionada': 'XXXtreme Lightning'}
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
if "telegram_token_alt" not in st.session_state: st.session_state.telegram_token_alt = ""
if "telegram_chat_id_alt" not in st.session_state: st.session_state.telegram_chat_id_alt = ""

# Sidebar
with st.sidebar:
    st.markdown("## ⚙️ V10.9.8 - RAIOS + FILTROS")
    if st.button("🆕 NOVA SESSÃO", use_container_width=True, type="primary"):
        if nova_sessao(): st.success("✅ Nova sessão!"); st.rerun()
    st.markdown("---")
    
    st.markdown("### 🎰 Selecione a Roleta")
    api_opcoes = list(API_URLS.keys())
    api_atual = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
    api_index = api_opcoes.index(api_atual) if api_atual in api_opcoes else 0
    st.session_state.api_selecionada = st.radio("Roleta:", api_opcoes, index=api_index)
    
    if st.session_state.api_selecionada == 'XXXtreme Lightning':
        st.success("⚡ Raios: 50x-2000x | Nº: 36x | Zero: 36x | Dúzia: 3x")
    elif st.session_state.api_selecionada == 'Mega Roulette':
        st.warning("⚡ Raios: 50x-500x | Nº: 24x | Zero: 24x | Dúzia: 2x")
    else:
        st.info("🎯 Sem raios | Nº: 35x | Zero: 35x | Dúzia: 2x")
    
    st.markdown("---")
    st.session_state.janela_duzia_ai = st.slider("📏 Janela", 10, 50, st.session_state.janela_duzia_ai, 5)
    st.session_state.modo_agressivo = st.checkbox("🔥 Modo Agressivo (2 Dúzias)", value=st.session_state.modo_agressivo)
    st.session_state.modo_automatico = st.checkbox("🤖 Auto", value=st.session_state.modo_automatico)
    st.markdown("---")
    st.caption("🤖 ML ADAPTATIVO: RandomForest ativo")
    st.caption("⚡ RAIOS: Captura corrigida!")
    st.caption("🚫 FILTRO: EMBALO + Conf Alta + Zero")
    st.caption("🚫 FILTRO: Anti-Erro + Zero + Conf Baixa")
    st.caption("🔥 EMBALO: 3+ mesma dúzia em 4 giros")
    st.caption("🔄 FADIGA DE DÚZIA: 4+ acertos = muda")
    st.caption("🏓 RITMO_PING_PONG")
    st.caption("🎯 RITMO_BINARIO")
    st.caption("💥 QUEBRA_POS_ZERO")
    st.caption("🔥 EXAUSTAO_DOMINANCIA")
    st.caption("⚡ MUDANCA_VELOCIDADE")
    st.caption("🟢 7 regras de Alerta Zero")
    st.markdown("---")
    with st.expander("🔔 Telegram PRINCIPAL", expanded=False):
        st.session_state.telegram_token = st.text_input("Token Principal", value=st.session_state.telegram_token, type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID Principal", value=st.session_state.telegram_chat_id)
    with st.expander("📢 Telegram ALTERNATIVO", expanded=False):
        st.session_state.telegram_token_alt = st.text_input("Token Alternativo", value=st.session_state.telegram_token_alt, type="password")
        st.session_state.telegram_chat_id_alt = st.text_input("Chat ID Alternativo", value=st.session_state.telegram_chat_id_alt)
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
        if not st.session_state.historico or r.get("timestamp") != st.session_state.historico[-1].get("timestamp"):
            st.session_state.historico.append(r)
            st.session_state.sistema.processar_novo_numero(r)
            salvar_resultado_em_arquivo(st.session_state.historico); salvar_sessao(); st.rerun()

st.markdown("---")
sis = st.session_state.sistema

# Métricas
st.subheader(f"📊 CONFERÊNCIA - {st.session_state.get('api_selecionada', 'XXXtreme Lightning')}")
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
c6.metric("🎰 Roleta", st.session_state.get('api_selecionada', 'XXXtreme')[:10])

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
        if ML_DISPONIVEL and len(sis.historico_numeros) >= 25: titulo += " | 🤖 ML"
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
        
        duzia_principal = dz_princ
        duzia_secundaria = dz_sec if dz_sec and dz_sec != dz_princ else None
        
        melhores_principal = _selecionar_melhores_numeros(duzia_principal, list(sis.historico_numeros), 6)
        
        if duzia_secundaria:
            melhores_secundaria = _selecionar_melhores_numeros(duzia_secundaria, list(sis.historico_numeros), 6)
        else:
            melhores_secundaria = None
        
        cor = "#FF6347" if e.get('modo_anti_erro') else "#FFD700"
        
        st.markdown(f"""
        <div style="background-color:{cor}15; border:2px solid {cor}; border-radius:15px; padding:15px;">
            <h2 style="color:{cor}; text-align:center;">🎯 D{dz_princ}</h2>
            <p style="text-align:center; font-size:1.1em;">Confiança: {conf:.2f} {'| 🎯 '+gat if gat else ''}</p>
            {f'<p style="text-align:center; color:#FFA500;">🛡️ Cobertura: D{dz_sec}</p>' if duzia_secundaria else ''}
        </div>""", unsafe_allow_html=True)
        
        st.write(f"**🎲 6 melhores D{duzia_principal}:** {', '.join(map(str, melhores_principal))}")
        if melhores_secundaria:
            st.write(f"**🛡️ 6 melhores D{duzia_secundaria}:** {', '.join(map(str, melhores_secundaria))}")
        
        if nums:
            st.write("**Todos os números:**")
            cols = st.columns(7)
            for i, n in enumerate(sorted(nums)):
                label = "🟢0" if n==0 else str(n)
                cols[i%7].button(label, key=f"n{n}", use_container_width=True)
        st.progress(min(1.0, max(0.0, conf/5.0)))
    else:
        st.info("🔍 Aguardando sinal...")
    
    if sis.ultimo_numero is not None:
        st.markdown("---")
        st.write(f"**🔄 Último:** {'🟢 ZERO' if sis.ultimo_numero==0 else f'#{sis.ultimo_numero} (D{get_duzia(sis.ultimo_numero)})'}")

st.markdown("---")
st.subheader("📝 Histórico")

if sis.historico_entradas:
    dados = []
    for e in reversed(sis.historico_entradas[-15:]):
        real = f"D{e.get('duzia_real',0)}" if e.get('duzia_real',0)!=0 else "0"
        prev = f"D{e.get('duzia_prevista','?')}"
        cob = f"D{e.get('duzia_sec_prevista','?')}" if e.get('duzia_sec_prevista') and e.get('duzia_sec_prevista') != e.get('duzia_prevista') else "-"
        zero = '🟢' if e.get('incluir_zero') else '-'
        anti = '🔄' if e.get('modo_anti_erro') else '-'
        duz = '✅' if e.get('acerto_duzia') else '❌'
        num = '🎯' if e.get('acerto_numero') else '-'
        zer = '🟢' if e.get('acerto_zero') else '-'
        
        numero_sorteado = e.get('numero', 0)
        if e.get('eh_raio'):
            num_display = f"⚡{numero_sorteado} ({e.get('multiplicador',0)}x)"
        elif numero_sorteado == 0:
            num_display = "0"
        else:
            num_display = str(numero_sorteado)
        
        dados.append({
            "Rod": e.get('rodada'),
            "Hora": e.get('hora'),
            "🎲": num_display,
            "Real": real,
            "Prev": prev,
            "Cob": cob,
            "Conf": f"{e.get('confianca',0):.1f}",
            "Gat": e.get('gatilho','-') if e.get('gatilho') else '-',
            "Z": zero,
            "🔄": anti,
            "Duz": duz,
            "Nº": num,
            "Zer": zer,
        })
    st.dataframe(dados, use_container_width=True, height=300,
                column_config={
                    "🎲": st.column_config.TextColumn("🎲 Sorteado", width="small"),
                    "Rod": st.column_config.NumberColumn("Rod", width="small"),
                })
    
    if st.button("📥 Exportar CSV", use_container_width=True):
        if exportar_historico_csv(sis.historico_entradas): st.success("✅")
else: 
    st.info("Nenhuma entrada.")

# Status dos Telegrams
st.markdown("---")
st.caption("📡 **Status Telegram:**")
col_t1, col_t2 = st.columns(2)
with col_t1:
    if st.session_state.telegram_token and st.session_state.telegram_chat_id:
        st.success("🔔 Principal: CONFIGURADO")
    else:
        st.warning("🔔 Principal: NÃO CONFIGURADO")
with col_t2:
    if st.session_state.telegram_token_alt and st.session_state.telegram_chat_id_alt:
        st.success("📢 Alternativo: CONFIGURADO")
    else:
        st.warning("📢 Alternativo: NÃO CONFIGURADO")

st.caption(f"🤖 DuziaAI V10.9.8 | Raios + Filtros | {st.session_state.get('api_selecionada', 'XXXtreme Lightning')} | {formatar_hora_brasilia()}")
salvar_sessao()
