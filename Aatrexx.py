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
import plotly.graph_objects as go

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_roleta.json"
PERFORMANCE_PATH = "performance_bot.json"
ENTRADAS_PATH = "historico_entradas.json"
ML_MODEL_PATH = "modelo_xgboost.pkl"

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
            'modo_ml': st.session_state.get('modo_ml', False),
            'janela_duzia_ai': st.session_state.get('janela_duzia_ai', 30),
            'acertos_duzia': st.session_state.get('acertos_duzia', 0),
            'erros_duzia': st.session_state.get('erros_duzia', 0),
            'acertos_duzia_sec': st.session_state.get('acertos_duzia_sec', 0),
            'erros_duzia_sec': st.session_state.get('erros_duzia_sec', 0),
            'modo_agressivo': st.session_state.get('modo_agressivo', False),
            'confianca_minima': st.session_state.get('confianca_minima', 3.2),
            'agressividade': st.session_state.get('agressividade', 2),
            'confianca_ml': st.session_state.get('confianca_ml', 0.10),
            'giros_minimos_ml': st.session_state.get('giros_minimos_ml', 10),
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
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH, ENTRADAS_PATH, ML_MODEL_PATH]:
            if os.path.exists(path):
                os.remove(path)
        st.session_state.clear()
        st.rerun()
    except Exception as e:
        logging.error(f"Erro ao limpar sessão: {e}")

# =============================
# NOTIFICAÇÕES
# =============================
def enviar_previsao_auto(previsao):
    try:
        numeros = sorted(previsao.get('numeros_apostar', []))
        forca = previsao.get('forca_real', 0)
        motor = previsao.get('motor', '')
        gatilho = previsao.get('gatilho', '')
        
        emoji = "🔥" if forca >= 65 else "🎯" if forca >= 55 else "⚠️"
        st.toast(f"{emoji} {motor} - {forca}%")
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"🔔 F{forca}% | {motor}\n{gatilho}\n🔢 " + " ".join(map(str, numeros)))
        
        salvar_sessao()
    except:
        pass

def enviar_resultado_auto(numero_real, acerto, lucky=False):
    try:
        st.toast(f"{'✅' if acerto else '❌'} {numero_real}" + (" 🍀" if lucky else ""))
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"📢 {'✅' if acerto else '❌'} {numero_real}" + (" 🍀" if lucky else ""))
        salvar_sessao()
    except:
        pass

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

# =============================
# 🧠 MACHINE LEARNING PREDICTOR (XGBoost) - CORRIGIDO
# =============================
class MLPredictor:
    def __init__(self):
        self.model = None
        self.feature_names = []
        self.last_training = None
        self.training_samples = 0
        self.ready = False
        self.training_attempts = 0
    
    def extrair_features(self, historico_duzias, historico_numeros):
        features = {}
        
        for w in [5, 10, 15]:
            janela = historico_duzias[-w:] if len(historico_duzias) >= w else historico_duzias
            freq = Counter(janela)
            total = len(janela) if janela else 1
            for dz in [1, 2, 3]:
                features[f'freq_dz{dz}_{w}g'] = freq.get(dz, 0) / total
        
        if historico_duzias:
            last = historico_duzias[-1]
            count = 0
            for d in reversed(historico_duzias):
                if d == last: count += 1
                else: break
            features['streak_count'] = count
            features['streak_duzia'] = last if last != 0 else 0
        else:
            features['streak_count'] = 0
            features['streak_duzia'] = 0
        
        for i in range(1, 4):
            idx = -i
            if len(historico_duzias) >= abs(idx):
                features[f'duzia_t{i}'] = historico_duzias[idx] if historico_duzias[idx] != 0 else 0
            else:
                features[f'duzia_t{i}'] = 0
        
        for dz in [1, 2, 3]:
            ausencia = 0
            for d in reversed(historico_duzias):
                if d == dz: break
                ausencia += 1
            features[f'ausencia_dz{dz}'] = ausencia
        
        u = historico_duzias[-3:] if len(historico_duzias) >= 3 else []
        features['padrao_aba'] = 1 if len(u)==3 and u[0]==u[2] and u[0]!=u[1] else 0
        features['padrao_abb'] = 1 if len(u)==3 and u[0]!=u[1] and u[1]==u[2] else 0
        features['padrao_repeticao'] = 1 if len(u)>=2 and u[-1]==u[-2] else 0
        
        return features
    
    def treinar(self, historico_completo_duzias, historico_completo_numeros, giros_minimos=10):
        self.training_attempts += 1
        
        if len(historico_completo_duzias) < giros_minimos:
            return False
        
        X_data = []
        y_data = []
        
        for i in range(giros_minimos, len(historico_completo_duzias)):
            janela_duzias = historico_completo_duzias[max(0, i-giros_minimos):i]
            janela_numeros = historico_completo_numeros[max(0, i-giros_minimos):i]
            features = self.extrair_features(janela_duzias, janela_numeros)
            
            if i < len(historico_completo_duzias):
                target = historico_completo_duzias[i]
                if target != 0:
                    X_data.append(features)
                    y_data.append(target - 1)
        
        if len(X_data) < 5:
            return False
        
        try:
            from xgboost import XGBClassifier
            
            self.feature_names = list(X_data[0].keys())
            X_array = np.array([[d.get(f, 0) for f in self.feature_names] for d in X_data])
            y_array = np.array(y_data)
            
            self.model = XGBClassifier(
                n_estimators=50,
                max_depth=3,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                objective='multi:softprob',
                num_class=3,
                eval_metric='mlogloss',
                use_label_encoder=False,
                random_state=42,
                verbosity=0
            )
            self.model.fit(X_array, y_array)
            self.training_samples = len(X_data)
            self.last_training = datetime.now()
            self.ready = True
            
            self.salvar()
            return True
            
        except ImportError:
            self.ready = False
            return False
        except Exception as e:
            self.ready = False
            return False
    
    def prever(self, historico_duzias, historico_numeros):
        if not self.ready or self.model is None:
            return None
        
        features = self.extrair_features(historico_duzias, historico_numeros)
        
        try:
            X = np.array([[features.get(f, 0) for f in self.feature_names]])
            probs = self.model.predict_proba(X)[0]
            
            ranking = np.argsort(probs)[::-1]
            melhor_dz = ranking[0] + 1
            segunda_dz = ranking[1] + 1
            confianca = float(probs[ranking[0]] - probs[ranking[1]])
            
            return {
                'duzia': melhor_dz,
                'duzia_secundaria': segunda_dz,
                'confianca': confianca,
                'probabilidades': {1: float(probs[0]), 2: float(probs[1]), 3: float(probs[2])},
                'entrar': True  # 🆕 SEMPRE entra quando o ML está pronto
            }
        except Exception as e:
            return None
    
    def salvar(self):
        try:
            with open(ML_MODEL_PATH, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'feature_names': self.feature_names,
                    'training_samples': self.training_samples
                }, f)
        except:
            pass
    
    def carregar(self):
        try:
            if os.path.exists(ML_MODEL_PATH):
                with open(ML_MODEL_PATH, 'rb') as f:
                    data = pickle.load(f)
                    self.model = data.get('model')
                    self.feature_names = data.get('feature_names', [])
                    self.training_samples = data.get('training_samples', 0)
                    self.ready = self.model is not None
                return True
        except:
            pass
        return False

# =============================
# 🧠 DUZIA AI (REGRA FIXA - SIMPLIFICADA PARA PERFORMANCE)
# =============================
class DuziaAI:
    def __init__(self, window=30):
        self.historico = deque(maxlen=window)
        self.historico_completo = []
        self.numeros_completos = []
    
    def adicionar(self, numero):
        d = get_duzia(numero)
        self.historico.append(d)
        self.historico_completo.append(d)
        self.numeros_completos.append(numero)
        if len(self.historico_completo) > 200:
            self.historico_completo = self.historico_completo[-200:]
        if len(self.numeros_completos) > 200:
            self.numeros_completos = self.numeros_completos[-200:]
    
    def frequencia(self):
        return Counter(self.historico)
    
    def streak(self):
        if not self.historico: return 0, None
        last = self.historico[-1]
        count = 0
        for d in reversed(self.historico):
            if d == last: count += 1
            else: break
        return count, last
    
    def transicao(self):
        if len(self.historico) < 2: return None
        return self.historico[-2], self.historico[-1]
    
    def detectar_regime(self):
        freq = self.frequencia()
        total = sum(freq.values())
        if total == 0: return "NEUTRO"
        razao = max(freq.values()) / total
        if razao > 0.5: return "DOMINANTE"
        elif razao > 0.4: return "TENDENCIA"
        elif len([d for d in freq if freq[d] > 0]) == 3: return "DISTRIBUIDO"
        else: return "TRANSICAO"
    
    def calcular_score(self):
        score = {1: 0, 2: 0, 3: 0}
        detalhes = {1: [], 2: [], 3: []}
        
        freq = self.frequencia()
        total = sum(freq.values()) if sum(freq.values()) > 0 else 1
        
        for d in score:
            score[d] += (freq[d] / total) * 50
        
        streak_count, streak_d = self.streak()
        if streak_d and streak_d != 0:
            score[streak_d] += streak_count * 5
            detalhes[streak_d].append(f"Streak {streak_count}x")
        
        trans = self.transicao()
        if trans:
            ant, atual = trans
            if ant != atual and ant != 0:
                score[ant] += 8
                detalhes[ant].append("Rebote")
        
        # Padrão ABA
        u = list(self.historico)
        if len(u) >= 3 and u[-3] == u[-1] and u[-3] != u[-2] and u[-3] != 0:
            score[u[-3]] += 6
            detalhes[u[-3]].append("ABA")
        
        # Padrão ABAB
        if len(u) >= 4 and u[-4] == u[-2] and u[-3] == u[-1] and u[-4] != u[-3] and u[-4] != 0:
            score[u[-3]] += 8
            detalhes[u[-3]].append("ABAB")
        
        regime = self.detectar_regime()
        
        return score, regime, detalhes
    
    def prever(self):
        score, regime, detalhes = self.calcular_score()
        ranking = sorted(score.items(), key=lambda x: x[1], reverse=True)
        d1 = ranking[0][0]
        d2 = ranking[1][0]
        
        return {
            "entrar": True,  # 🆕 SEMPRE entra no modo regras
            "duzia": d1,
            "duzia_secundaria": d2,
            "confianca": float(score[d1] - score[d2]),
            "score": score,
            "regime": regime,
            "detalhes": detalhes
        }

# =============================
# SISTEMA PRINCIPAL (CORRIGIDO)
# =============================
class SistemaBot:
    def __init__(self):
        janela = st.session_state.get('janela_duzia_ai', 30)
        self.duzia_ai = DuziaAI(window=janela)
        self.ml_predictor = MLPredictor()
        self.historico_numeros = deque(maxlen=200)
        self.entrada_ativa = None
        self.historico_entradas = []
        self.acertos = 0
        self.erros = 0
        self.ultimo_numero = None
        self.sinais_grafico = []
        self.ml_entradas_count = 0
        self.ml_acertos = 0
        
        # 🆕 Sempre tenta carregar modelo salvo
        self.ml_predictor.carregar()
    
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data['number']
        else:
            nr = int(numero_data)
        
        self.duzia_ai.adicionar(nr)
        self.historico_numeros.append(nr)
        self.ultimo_numero = nr
        
        # Verifica acerto da entrada anterior
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
            
            entrada_info = {
                'rodada': len(self.historico_numeros) - 1,
                'hora': datetime.now().strftime('%H:%M:%S'),
                'resultado': nr,
                'acerto': acerto_primaria or acerto_secundaria,
                'duzia_prevista': duzia_prevista,
                'duzia_sec_prevista': duzia_sec_prevista,
                'duzia_real': duzia_real,
                'acerto_primaria': acerto_primaria,
                'acerto_secundaria': acerto_secundaria,
                'modo': self.entrada_ativa.get('modo', 'regras')
            }
            self.historico_entradas.append(entrada_info)
            if len(self.historico_entradas) > 50:
                self.historico_entradas = self.historico_entradas[-50:]
            
            enviar_resultado_auto(nr, acerto_primaria or acerto_secundaria)
            self.entrada_ativa = None
        
        # 🆕 TREINAMENTO FORÇADO a cada giro se necessário
        if st.session_state.get('modo_ml', False):
            total_giros = len(self.historico_numeros)
            giros_minimos = st.session_state.get('giros_minimos_ml', 10)
            
            # Tenta treinar se ainda não está pronto
            if not self.ml_predictor.ready and total_giros >= giros_minimos:
                self.ml_predictor.treinar(
                    list(self.duzia_ai.historico_completo),
                    list(self.duzia_ai.numeros_completos),
                    giros_minimos=giros_minimos
                )
            
            # Re-treina a cada 20 giros
            if self.ml_predictor.ready and total_giros % 20 == 0:
                self.ml_predictor.treinar(
                    list(self.duzia_ai.historico_completo),
                    list(self.duzia_ai.numeros_completos),
                    giros_minimos=giros_minimos
                )
        
        # 🆕 GERA PREVISÃO SEMPRE (ML ou Regras)
        previsao = None
        modo_entrada = 'regras'
        
        # Tenta ML primeiro
        if st.session_state.get('modo_ml', False) and self.ml_predictor.ready:
            previsao_ml = self.ml_predictor.prever(
                list(self.duzia_ai.historico),
                list(self.duzia_ai.numeros_completos[-30:])
            )
            if previsao_ml:
                previsao = previsao_ml
                modo_entrada = 'ml'
        
        # Fallback para regras
        if previsao is None:
            previsao = self.duzia_ai.prever()
            modo_entrada = 'regras'
        
        # Monta entrada
        duzia_map = {1: list(range(1, 13)), 2: list(range(13, 25)), 3: list(range(25, 37))}
        numeros = duzia_map.get(previsao['duzia'], [])
        
        if st.session_state.get('modo_agressivo', False) and previsao.get('duzia_secundaria'):
            numeros = list(set(numeros + duzia_map.get(previsao['duzia_secundaria'], [])))
        
        confianca = previsao.get('confianca', 0) or 0.0
        
        self.entrada_ativa = {
            'numeros_apostar': numeros,
            'duzia_prevista': previsao['duzia'],
            'duzia_sec_prevista': previsao.get('duzia_secundaria'),
            'confianca': float(confianca),
            'regime': previsao.get('regime', '?'),
            'score': previsao.get('score', {}),
            'detalhes': previsao.get('detalhes', {}),
            'modo': modo_entrada
        }
        
        self.sinais_grafico.append((len(self.historico_numeros) - 1, previsao['duzia']))
        
        motor = f"🤖 ML D{previsao['duzia']}" if modo_entrada == 'ml' else f"📊 D{previsao['duzia']}"
        gatilho = f"Conf: {confianca:.1f}" if modo_entrada == 'ml' else f"Regime: {previsao.get('regime', '?')}"
        
        enviar_previsao_auto({
            'numeros_apostar': numeros,
            'forca_real': float(min(95, confianca * 8 if modo_entrada == 'regras' else confianca * 50)),
            'motor': motor,
            'gatilho': gatilho
        })
    
    def zerar(self):
        self.acertos = 0
        self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear()
        self.entrada_ativa = None
        self.ultimo_numero = None
        self.sinais_grafico = []
        janela = st.session_state.get('janela_duzia_ai', 30)
        self.duzia_ai = DuziaAI(window=janela)
        self.ml_predictor = MLPredictor()
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
        with open(caminho, "w") as f:
            json.dump(historico, f, indent=2)
    except:
        pass

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

def exportar_historico(historico, formato='json'):
    if formato == 'json':
        return json.dumps(historico, indent=2, ensure_ascii=False)
    linhas = ["numero,timestamp,multiplicador"]
    for item in historico:
        if isinstance(item, dict):
            n = item.get('number', '')
            linhas.append(f"{n},{item.get('timestamp','')},{item.get('luckyMultipliers',{}).get(n,'')}")
        else:
            linhas.append(f"{item},,")
    return "\n".join(linhas)

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎰 DuziaAI V6.0 - SEMPRE ATIVO", layout="wide")
st.title("🎰 DuziaAI V6.0 - Análise a Cada Giro")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    sis = st.session_state.sistema
    numeros = dados.get('historico_numeros', [])
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
    st.session_state.modo_ml = dados.get('modo_ml', False)
    st.session_state.confianca_ml = dados.get('confianca_ml', 0.10)
    st.session_state.giros_minimos_ml = dados.get('giros_minimos_ml', 10)
    if os.path.exists(ENTRADAS_PATH):
        try:
            with open(ENTRADAS_PATH, 'r') as f:
                sis.historico_entradas = json.load(f)
        except:
            pass

defaults = {
    'modo_automatico': True, 'modo_agressivo': False, 'modo_ml': False,
    'janela_duzia_ai': 30, 'confianca_minima': 3.2, 'agressividade': 2,
    'confianca_ml': 0.10, 'giros_minimos_ml': 10,
    'acertos_duzia': 0, 'erros_duzia': 0,
    'acertos_duzia_sec': 0, 'erros_duzia_sec': 0,
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

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.markdown("## ⚙️ Configurações")
    
    st.markdown("### 🧠 Modo de Inteligência")
    st.session_state.modo_ml = st.checkbox(
        "🤖 ATIVAR MACHINE LEARNING (XGBoost)",
        value=st.session_state.modo_ml,
        help="Ativa IA que aprende com os dados"
    )
    
    if st.session_state.modo_ml:
        st.success("🤖 **MODO ML ATIVO**")
        
        st.session_state.giros_minimos_ml = st.slider(
            "📏 Giros para Treinar", 5, 30, st.session_state.giros_minimos_ml, 5
        )
        
        sis = st.session_state.sistema
        if sis.ml_predictor.ready:
            st.success(f"✅ ML treinado: {sis.ml_predictor.training_samples} amostras")
        else:
            giros_atuais = len(sis.historico_numeros)
            st.warning(f"⏳ ML aguardando {st.session_state.giros_minimos_ml} giros ({giros_atuais} atuais)")
            
            if giros_atuais >= st.session_state.giros_minimos_ml:
                if st.button("🧠 FORÇAR TREINAMENTO", use_container_width=True, type="primary"):
                    with st.spinner("Treinando..."):
                        sucesso = sis.ml_predictor.treinar(
                            list(sis.duzia_ai.historico_completo),
                            list(sis.duzia_ai.numeros_completos),
                            st.session_state.giros_minimos_ml
                        )
                        if sucesso:
                            st.success(f"✅ Treinado! {sis.ml_predictor.training_samples} amostras")
                            st.rerun()
                        else:
                            st.error("❌ pip install xgboost scikit-learn")
    else:
        st.info("📊 **MODO REGRAS FIXAS**")
    
    st.markdown("---")
    st.session_state.modo_agressivo = st.checkbox("🔥 Modo Agressivo (2 Dúzias)", value=st.session_state.modo_agressivo)
    st.session_state.modo_automatico = st.checkbox("🤖 Modo Automático", value=st.session_state.modo_automatico)
    
    st.markdown("---")
    with st.expander("🔔 Telegram", expanded=False):
        st.session_state.telegram_token = st.text_input("Token", value=st.session_state.telegram_token, type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID", value=st.session_state.telegram_chat_id)
    
    c1, c2 = st.columns(2)
    c1.button("💾 Salvar", on_click=lambda: [salvar_resultado_em_arquivo(st.session_state.historico), salvar_sessao(), st.success("✅")], use_container_width=True)
    c2.button("🗑️ Zerar", on_click=lambda: st.session_state.sistema.zerar() or st.rerun(), use_container_width=True)

# =============================
# CONTEÚDO PRINCIPAL
# =============================
sis = st.session_state.sistema

st.subheader("🎲 Inserir Números")
c1, c2, c3 = st.columns([3, 1, 1])
with c1:
    entrada = st.text_input("Número (0-36):", placeholder="Digite o número sorteado", key="entrada_numero")
with c2:
    if st.button("🎯 Enviar", use_container_width=True, type="primary"):
        if entrada and entrada.isdigit() and 0 <= int(entrada) <= 36:
            nr = int(entrada)
            item = {"number": nr, "timestamp": datetime.now().isoformat(), "luckyNumbers": [], "luckyMultipliers": {}}
            st.session_state.historico.append(item)
            sis.processar_novo_numero(item)
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
            sis.processar_novo_numero(resultado)
            salvar_resultado_em_arquivo(st.session_state.historico)
            salvar_sessao()
            st.rerun()

st.markdown("---")

# Métricas
c1, c2, c3, c4, c5, c6 = st.columns(6)
total_entradas = int(sis.acertos + sis.erros)
tx_acerto = (sis.acertos / total_entradas * 100) if total_entradas > 0 else 0

c1.metric("✅ Acertos", int(sis.acertos))
c2.metric("❌ Erros", int(sis.erros))
c3.metric("📊 Win Rate", f"{tx_acerto:.1f}%")
c4.metric("🎯 Tx Dúzia", f"{st.session_state.get('acertos_duzia', 0)}/{st.session_state.get('erros_duzia', 0)}")
c5.metric("📦 Total", total_entradas)
c6.metric("🧠 Modo", "🤖 ML" if st.session_state.modo_ml else "📊 Regras")

st.markdown("---")
col_grafico, col_entrada = st.columns([3, 2])

with col_grafico:
    st.subheader("📈 Análise em Tempo Real")
    if len(sis.historico_numeros) >= 5:
        score, regime, detalhes = sis.duzia_ai.calcular_score()
        
        fig = go.Figure(data=[go.Bar(
            x=['D1', 'D2', 'D3'],
            y=[score[1], score[2], score[3]],
            marker_color=['#FF6B6B' if score[1] == max(score.values()) else '#4ECDC4',
                         '#FF6B6B' if score[2] == max(score.values()) else '#4ECDC4',
                         '#FF6B6B' if score[3] == max(score.values()) else '#4ECDC4'],
            text=[f'{score[1]:.1f}', f'{score[2]:.1f}', f'{score[3]:.1f}'],
            textposition='auto'
        )])
        fig.update_layout(title=f"🎯 Scores | Regime: {regime}", height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        if len(sis.historico_numeros) >= 10:
            ultimos = list(sis.historico_numeros)[-20:]
            duzias = [get_duzia(n) for n in ultimos]
            x_vals = list(range(len(duzias)))
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=x_vals, y=duzias, mode='lines+markers', line=dict(color='#FFD700', width=2), marker=dict(size=8)))
            if sis.sinais_grafico:
                sx, sy, stxt = [], [], []
                offset = len(duzias) - 20
                for idx, dz in sis.sinais_grafico:
                    pos = idx - offset
                    if 0 <= pos < 20:
                        sx.append(pos)
                        sy.append(dz)
                        stxt.append(f"Entrada D{dz}")
                if sx:
                    fig2.add_trace(go.Scatter(x=sx, y=sy, mode='markers', name='Sinal', marker=dict(symbol='star', size=15, color='red')))
            fig2.update_layout(title="📉 Histórico c/ Sinais", yaxis=dict(tickvals=[1, 2, 3], ticktext=['D1', 'D2', 'D3'], range=[0.5, 3.5]), height=300)
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info(f"⏳ Aguardando dados... ({len(sis.historico_numeros)}/5 giros)")

with col_entrada:
    st.subheader("🎰 Entrada Atual")
    if sis.entrada_ativa:
        ent = sis.entrada_ativa
        confianca = ent.get('confianca', 0) or 0.0
        dz_prev = ent.get('duzia_prevista', 0)
        modo_entrada = ent.get('modo', 'regras')
        
        cor = "#8A2BE2" if modo_entrada == 'ml' else "#00CC00"
        emoji = "🤖" if modo_entrada == 'ml' else "📊"
        limite = "1-12" if dz_prev == 1 else "13-24" if dz_prev == 2 else "25-36"
        
        st.markdown(f"""
        <div style="background-color:{cor}22; border:2px solid {cor}; border-radius:15px; padding:20px;">
            <h2 style="color:{cor}; text-align:center;">{emoji} D{dz_prev} ({limite})</h2>
            <p style="text-align:center;">Confiança: {confianca:.2f} | Modo: {'🤖 ML' if modo_entrada=='ml' else '📊 Regras'}</p>
        </div>""", unsafe_allow_html=True)
        
        nums = ent.get('numeros_apostar', [])
        if nums:
            st.write("**🎲 Números:**")
            cols = st.columns(6)
            for i, n in enumerate(sorted(nums)):
                cols[i % 6].button(str(n), key=f"num_{n}", use_container_width=True)
        
        progresso = float(min(1.0, confianca / 15.0)) if confianca else 0.0
        st.progress(progresso)
    else:
        st.info("🔍 Aguardando primeiro giro...")
    
    if sis.ultimo_numero is not None:
        st.markdown("---")
        st.write(f"**🔄 Último Giro:** #{sis.ultimo_numero} → D{get_duzia(sis.ultimo_numero)}")

st.markdown("---")
st.subheader("📝 Histórico de Entradas")
if sis.historico_entradas:
    dados_tabela = []
    for e in reversed(sis.historico_entradas[-20:]):
        dados_tabela.append({
            "Rodada": e.get('rodada', '-'),
            "Hora": e.get('hora', '-'),
            "Número": e.get('resultado', '-'),
            "Dúzia Real": f"D{e.get('duzia_real', '?')}" if e.get('duzia_real') else "-",
            "Dúzia Prevista": f"D{e.get('duzia_prevista', '?')}" if e.get('duzia_prevista') else "-",
            "Resultado": "✅" if e.get('acerto_primaria') else "🟡" if e.get('acerto_secundaria') else "❌",
            "Modo": "🤖" if e.get('modo') == 'ml' else "📊"
        })
    st.dataframe(dados_tabela, use_container_width=True, height=300)
else:
    st.info("Nenhuma entrada registrada ainda.")

st.markdown("---")
st.caption(f"🤖 DuziaAI V6.0 | Análise a cada giro | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
salvar_sessao()
