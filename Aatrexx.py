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
            'erros': sis.erros,
            'historico': sis.bot.performance['historico']
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
            'acertos_duzia': st.session_state.get('acertos_duzia', 0),
            'erros_duzia': st.session_state.get('erros_duzia', 0),
            'modo_agressivo': st.session_state.get('modo_agressivo', False),
            'giros_minimos_ml': st.session_state.get('giros_minimos_ml', 10),
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
        st.toast(f"🎯 {motor} - {forca}%")
        salvar_sessao()
    except:
        pass

def enviar_resultado_auto(numero_real, acerto):
    try:
        st.toast(f"{'✅' if acerto else '❌'} {numero_real}")
        salvar_sessao()
    except:
        pass

def enviar_telegram(mensagem):
    try:
        token = st.session_state.get('telegram_token', '')
        chat_id = st.session_state.get('telegram_chat_id', '')
        if not token or not chat_id: return
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}, timeout=10)
    except: pass

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

# =============================
# 🧠 DUZIA AI V4 (SISTEMA DE REGRAS)
# =============================
class DuziaAI:
    def __init__(self, window=30):
        self.historico = deque(maxlen=window)
        self.historico_completo = []
        self.numeros_completos = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
    
    def adicionar(self, numero):
        d = get_duzia(numero)
        self.historico.append(d)
        self.historico_completo.append(d)
        self.numeros_completos.append(numero)
        if len(self.historico_completo) > 200: self.historico_completo = self.historico_completo[-200:]
        if len(self.numeros_completos) > 200: self.numeros_completos = self.numeros_completos[-200:]
    
    def frequencia_ponderada(self):
        freq = Counter()
        total = len(self.historico)
        for i, d in enumerate(self.historico):
            pos = i / max(1, total - 1)
            freq[d] += 1 + (pos ** 1.5) * 7
        return freq
    
    def frequencia(self): return Counter(self.historico)
    
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
    
    def matriz_transicao(self):
        matriz = {1:{1:0,2:0,3:0}, 2:{1:0,2:0,3:0}, 3:{1:0,2:0,3:0}}
        totais = {1:0,2:0,3:0}
        for i in range(len(self.historico_completo)-1):
            o, d = self.historico_completo[i], self.historico_completo[i+1]
            if o!=0 and d!=0:
                peso = 1 + (i/max(1,len(self.historico_completo)))*2
                matriz[o][d] += peso; totais[o] += peso
        prob = {}
        for o in [1,2,3]:
            prob[o] = {d: (matriz[o][d]/totais[o]*100) if totais[o]>0 else 33.3 for d in [1,2,3]}
        return prob
    
    def detectar_repeticao_imediata(self):
        if len(self.historico)<3: return None
        u = list(self.historico)[-3:]
        if u[0]!=u[1] and u[1]==u[2] and u[1]!=0: return u[1], 6
        if len(self.historico)>=2:
            u2 = list(self.historico)[-2:]
            if u2[0]==u2[1] and u2[0]!=0: return u2[0], 4
        return None
    
    def detectar_streak_longo(self):
        c, d = self.streak()
        if c>=3 and d!=0: return d, min(10, 4+(c-3)*2)
        return None
    
    def detectar_retorno_aba(self):
        if len(self.historico) < 3: return None
        u = list(self.historico)[-3:]
        if u[0]==u[2] and u[0]!=u[1] and u[0]!=0 and u[1]!=0: return u[0], 5
        return None
    
    def detectar_vai_e_volta(self):
        u = list(self.historico)
        if len(u)>=4 and u[-4]==u[-2] and u[-3]==u[-1] and u[-4]!=u[-3] and u[-4]!=0 and u[-3]!=0: return u[-3], 6
        if len(u)>=5 and u[-5]==u[-3]==u[-1] and u[-4]==u[-2] and u[-5]!=u[-4] and u[-5]!=0 and u[-4]!=0: return u[-4], 8
        return None
    
    def detectar_duas_dominantes(self):
        if len(self.historico) < 10: return None
        u = list(self.historico)[-10:]
        freq = Counter(u)
        ranking = freq.most_common()
        if len(ranking)>=2 and ranking[0][1]+ranking[1][1]>=8:
            return (ranking[0][0], ranking[1][0]), 3
        return None
    
    def detectar_pos_zero(self):
        if len(self.historico)<3: return None
        u = list(self.historico)[-3:]
        if u[-1]==0 or u[-2]==0:
            for d in reversed(u[:-1]):
                if d!=0: return d, 5
        return None
    
    def detectar_bloco_d3(self):
        if len(self.historico)<5: return None
        u = list(self.historico)[-5:]
        d3c = u[-4:].count(3)
        if d3c>=2: return 3, 5
        if u[-1]==3 and d3c>=1: return 3, 3
        return None
    
    def ausencia(self):
        aus = {1:0,2:0,3:0}
        for d in reversed(self.historico):
            for dz in aus:
                if d!=dz: aus[dz]+=1
        dz = max(aus, key=aus.get)
        if aus[dz]>=5: return dz, aus[dz]
        return None
    
    def detectar_regime(self):
        freq = self.frequencia()
        total = sum(freq.values())
        if total==0: return "NEUTRO"
        razao = max(freq.values())/total
        if razao>0.5: return "DOMINANTE"
        elif razao>0.4: return "TENDENCIA"
        elif len([d for d in freq if freq[d]>0])==3: return "DISTRIBUIDO"
        else: return "TRANSICAO"
    
    def calcular_score(self):
        score = {1:0,2:0,3:0}
        detalhes = {1:[],2:[],3:[]}
        freq = self.frequencia_ponderada()
        freq_normal = self.frequencia()
        streak_count, streak_d = self.streak()
        trans = self.transicao()
        prob = self.matriz_transicao()
        regime = self.detectar_regime()
        
        for d in score: score[d] += freq[d]*0.8
        total_normal = sum(freq_normal.values())
        if total_normal>0:
            for d in score: score[d] += (freq_normal[d]/total_normal)*10
        
        if streak_d and streak_d!=0:
            mult = 3.0 if regime=="DOMINANTE" else 2.0 if regime=="TENDENCIA" else 1.5
            score[streak_d] += streak_count*mult
        
        if trans and regime not in ["DOMINANTE","TENDENCIA"]:
            ant, _ = trans
            if ant!=0: score[ant] += 2.5
        
        if streak_count>=3 and streak_d and streak_d!=0:
            viz = {1:2,2:3,3:2}
            if streak_d in viz: score[viz[streak_d]] += 5
        
        if self.historico:
            ultima = self.historico[-1]
            if ultima!=0 and ultima in prob:
                for d in score:
                    p = prob[ultima][d]
                    if p>40: score[d] += (p-30)/8
        
        rep = self.detectar_repeticao_imediata()
        if rep: dz, fc = rep; 
        if rep and dz!=0: score[dz]+=fc; detalhes[dz].append(f"Repetição:+{fc}")
        
        sl = self.detectar_streak_longo()
        if sl: dz, fc = sl
        if sl and dz!=0: score[dz]+=fc; detalhes[dz].append(f"Streak:+{fc}")
        
        pz = self.detectar_pos_zero()
        if pz: dz, fc = pz
        if pz and dz!=0: score[dz]+=fc; detalhes[dz].append(f"Pós-Zero:+{fc}")
        
        vv = self.detectar_vai_e_volta()
        if vv: dz, fc = vv
        if vv and dz!=0: score[dz]+=fc; detalhes[dz].append(f"Vai-e-Volta:+{fc}")
        
        aba = self.detectar_retorno_aba()
        if aba: dz, fc = aba
        if aba and dz!=0: score[dz]+=fc; detalhes[dz].append(f"ABA:+{fc}")
        
        duas = self.detectar_duas_dominantes()
        if duas:
            doms, fc = duas
            for dz in doms:
                if dz!=0: score[dz]+=fc; detalhes[dz].append(f"Dominante:+{fc}")
        
        bloco = self.detectar_bloco_d3()
        if bloco: dz, fc = bloco
        if bloco and dz!=0: score[dz]+=fc; detalhes[dz].append(f"Bloco D3:+{fc}")
        
        aus = self.ausencia()
        if aus: dz, g = aus
        if aus and dz!=0: score[dz]+=min(5,g*0.5)
        
        total = sum(score.values())
        if total>0:
            for d in score: score[d] = (score[d]/total)*100
        
        return score, regime, detalhes
    
    def prever(self):
        score, regime, detalhes = self.calcular_score()
        ranking = sorted(score.items(), key=lambda x: x[1], reverse=True)
        d1 = ranking[0][0]
        d2 = ranking[1][0]
        conf = ranking[0][1] - ranking[1][1]
        return {"duzia": d1, "duzia_secundaria": d2, "confianca": max(0, conf), "score": score, "regime": regime, "detalhes": detalhes}

# =============================
# ML PREDICTOR (OBSERVADOR)
# =============================
class MLPredictor:
    def __init__(self):
        self.model = None
        self.ready = False
        self.training_samples = 0
    
    def treinar(self, historico_duzias):
        if len(historico_duzias) < 10: return False
        try:
            from xgboost import XGBClassifier
            X, y = [], []
            for i in range(5, len(historico_duzias)):
                janela = list(historico_duzias)[i-5:i]
                if len(janela) < 5: continue
                features = []
                freq = Counter(janela)
                for d in [1,2,3]: features.append(freq.get(d,0)/5)
                ultima = janela[-1]
                streak = 0
                for d in reversed(janela):
                    if d == ultima: streak += 1
                    else: break
                features.append(streak); features.append(ultima)
                target = historico_duzias[i]
                if target != 0: X.append(features); y.append(target-1)
            if len(X) < 5: return False
            self.model = XGBClassifier(n_estimators=50, max_depth=3, learning_rate=0.1, objective='multi:softprob', num_class=3, use_label_encoder=False, eval_metric='mlogloss', verbosity=0, random_state=42)
            self.model.fit(np.array(X), np.array(y))
            self.training_samples = len(X)
            self.ready = True
            with open(ML_MODEL_PATH, 'wb') as f: pickle.dump({'model':self.model,'samples':self.training_samples}, f)
            return True
        except: return False
    
    def carregar(self):
        try:
            if os.path.exists(ML_MODEL_PATH):
                with open(ML_MODEL_PATH, 'rb') as f:
                    data = pickle.load(f)
                    self.model = data.get('model')
                    self.training_samples = data.get('samples',0)
                    self.ready = (self.model is not None) and (self.training_samples > 0)
                return self.ready
        except: pass
        return False
    
    def prever(self, historico_duzias):
        if not self.ready or len(historico_duzias) < 5: return None
        try:
            janela = list(historico_duzias)[-5:]
            features = []
            freq = Counter(janela)
            for d in [1,2,3]: features.append(freq.get(d,0)/5)
            ultima = janela[-1]; streak = 0
            for d in reversed(janela):
                if d == ultima: streak += 1
                else: break
            features.append(streak); features.append(ultima)
            X = np.array([features])
            probs = self.model.predict_proba(X)[0]
            ranking = np.argsort(probs)[::-1]
            return {'duzia_principal': int(ranking[0])+1, 'duzia_secundaria': int(ranking[1])+1, 'confianca': round(float(probs[ranking[0]]-probs[ranking[1]]),2),
                    'probabilidades': {1:round(float(probs[0])*100,1), 2:round(float(probs[1])*100,1), 3:round(float(probs[2])*100,1)}}
        except: return None

# =============================
# SISTEMA PRINCIPAL (CORRIGIDO)
# =============================
class SistemaBot:
    def __init__(self):
        self.bot = DuziaAI(window=20)
        self.ml = MLPredictor()
        self.historico_numeros = deque(maxlen=200)
        self.entrada_ativa = None
        self.historico_entradas = []
        self.acertos = 0
        self.erros = 0
        self.ultimo_numero = None
        self.sinais_grafico = []
        self.ml.carregar()
    
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data['number']
        else:
            nr = int(numero_data)
        
        self.bot.adicionar(nr)
        self.historico_numeros.append(nr)
        self.ultimo_numero = nr
        
        # Verifica acerto
        if self.entrada_ativa:
            duzia_real = get_duzia(nr)
            duzia_prevista = self.entrada_ativa.get('duzia_prevista')
            duzia_sec = self.entrada_ativa.get('duzia_secundaria')
            
            acertou = False
            acerto_primario = False
            
            if duzia_prevista is not None and nr != 0:
                acerto_primario = (duzia_real == duzia_prevista)
                acertou = acerto_primario or (duzia_sec is not None and duzia_real == duzia_sec)
            
            if acerto_primario:
                self.acertos += 1
                self.bot.performance['acertos'] += 1
                st.session_state.acertos_duzia = st.session_state.get('acertos_duzia', 0) + 1
            elif acertou:
                self.acertos += 0.5
            elif nr != 0:
                self.erros += 1
                self.bot.performance['erros'] += 1
                st.session_state.erros_duzia = st.session_state.get('erros_duzia', 0) + 1
            
            self.bot.performance['historico'].append(1 if acerto_primario else 0)
            
            self.historico_entradas.append({
                'rodada': len(self.historico_numeros),
                'hora': datetime.now().strftime('%H:%M:%S'),
                'resultado': nr,
                'duzia_real': f"D{duzia_real}" if duzia_real != 0 else "Z",
                'duzia_prevista': f"D{duzia_prevista}" if duzia_prevista else "-",
                'acerto': acertou,
                'acerto_primaria': acerto_primario
            })
            
            if len(self.historico_entradas) > 50: self.historico_entradas = self.historico_entradas[-50:]
            enviar_resultado_auto(nr, acertou)
            self.entrada_ativa = None
        
        # ML em background
        if st.session_state.get('modo_ml', False):
            if len(self.historico_numeros) >= st.session_state.get('giros_minimos_ml', 10) and not self.ml.ready:
                self.ml.treinar([get_duzia(n) for n in self.historico_numeros])
        
        # GERA PREVISÃO (SEMPRE)
        previsao = self.bot.prever()
        dz1 = previsao['duzia']
        dz2 = previsao.get('duzia_secundaria', (dz1 % 3) + 1)
        conf = previsao.get('confianca', 0)
        
        duzia_map = {1: list(range(1,13)), 2: list(range(13,25)), 3: list(range(25,37))}
        
        if st.session_state.get('modo_agressivo', False):
            numeros = sorted(set(duzia_map.get(dz1, []) + duzia_map.get(dz2, [])))
        else:
            numeros = sorted(duzia_map.get(dz1, []))
        
        self.entrada_ativa = {
            'numeros_apostar': numeros,
            'duzia_prevista': dz1,
            'duzia_secundaria': dz2,
            'confianca': float(conf),
            'modo': 'v4'
        }
        
        self.sinais_grafico.append((len(self.historico_numeros) - 1, dz1))
        
        enviar_previsao_auto({
            'numeros_apostar': numeros,
            'forca_real': float(min(95, conf * 3)) if conf else 25.0,
            'motor': f"D{dz1}",
            'gatilho': f"D{dz1}+D{dz2}"
        })
        
        salvar_sessao()
    
    def zerar(self):
        self.acertos = 0; self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear()
        self.entrada_ativa = None
        self.ultimo_numero = None
        self.sinais_grafico = []
        self.bot = DuziaAI(window=20)
        self.ml = MLPredictor()
        st.session_state.acertos_duzia = 0
        st.session_state.erros_duzia = 0
        salvar_sessao()

# =============================
# FUNÇÕES AUXILIARES
# =============================
def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    try:
        with open(caminho, "w") as f: json.dump(historico, f, indent=2)
    except: pass

def fetch_latest_result():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=5)
        r.raise_for_status()
        d = r.json()
        gd = d.get("data", {})
        rs = gd.get("result", {})
        nm = rs.get("outcome", {}).get("number")
        ts = gd.get("startedAt")
        ln = []
        for item in rs.get('luckyNumbersList', []):
            n = item.get('number')
            if n is not None: ln.append(n)
        return {"number": nm, "timestamp": ts, "luckyNumbers": ln}
    except: return None

# =============================
# APLICAÇÃO STREAMLIT (CORRIGIDA)
# =============================
st.set_page_config(page_title="🎰 DuziaAI V4 - Funcional", layout="wide")
st.title("🎰 DuziaAI V4 - Sistema de Regras")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    sis = st.session_state.sistema
    for n in dados.get('historico_numeros', []):
        sis.bot.adicionar(n)
        sis.historico_numeros.append(n)
    sis.acertos = dados.get('sistema_acertos', 0)
    sis.erros = dados.get('sistema_erros', 0)
    sis.entrada_ativa = dados.get('entrada_ativa', None)
    st.session_state.acertos_duzia = dados.get('acertos_duzia', 0)
    st.session_state.erros_duzia = dados.get('erros_duzia', 0)
    st.session_state.modo_agressivo = dados.get('modo_agressivo', False)
    st.session_state.modo_ml = dados.get('modo_ml', False)
    st.session_state.giros_minimos_ml = dados.get('giros_minimos_ml', 10)
    st.session_state.confianca_minima = dados.get('confianca_minima', 3.2)
    st.session_state.agressividade = dados.get('agressividade', 2)
    st.session_state.telegram_token = dados.get('telegram_token', '')
    st.session_state.telegram_chat_id = dados.get('telegram_chat_id', '')
    if os.path.exists(ENTRADAS_PATH):
        try:
            with open(ENTRADAS_PATH, 'r') as f: sis.historico_entradas = json.load(f)
        except: pass

for k, v in {
    'modo_automatico': True, 'modo_agressivo': False, 'modo_ml': False,
    'giros_minimos_ml': 10, 'acertos_duzia': 0, 'erros_duzia': 0,
    'confianca_minima': 3.2, 'agressividade': 2,
    'telegram_token': '', 'telegram_chat_id': ''
}.items():
    if k not in st.session_state: st.session_state[k] = v

if "historico" not in st.session_state:
    st.session_state.historico = []
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f: st.session_state.historico = json.load(f)
        except: pass

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.markdown("## ⚙️ Configurações")
    st.session_state.modo_agressivo = st.checkbox("🔥 2 Dúzias", value=st.session_state.modo_agressivo)
    st.session_state.modo_automatico = st.checkbox("🤖 Auto", value=st.session_state.modo_automatico)
    st.session_state.modo_ml = st.checkbox("🔬 ML Observador", value=st.session_state.modo_ml)
    
    st.markdown("---")
    with st.expander("🔔 Telegram", expanded=False):
        st.session_state.telegram_token = st.text_input("Token", value=st.session_state.telegram_token, type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID", value=st.session_state.telegram_chat_id)
    
    c1, c2 = st.columns(2)
    c1.button("💾 Salvar", on_click=lambda: [salvar_resultado_em_arquivo(st.session_state.historico), salvar_sessao()], use_container_width=True)
    c2.button("🗑️ Zerar", on_click=lambda: st.session_state.sistema.zerar() or st.rerun(), use_container_width=True)

# =============================
# INPUT
# =============================
sis = st.session_state.sistema

c1, c2 = st.columns([3, 1])
with c1:
    entrada = st.text_input("Número (0-36):", key="num", placeholder="Digite e Enter")
with c2:
    if st.button("🎯 Enviar", use_container_width=True, type="primary"):
        if entrada and entrada.isdigit() and 0 <= int(entrada) <= 36:
            nr = int(entrada)
            st.session_state.historico.append({"number": nr, "timestamp": datetime.now().isoformat(), "luckyNumbers": []})
            sis.processar_novo_numero(nr)
            salvar_resultado_em_arquivo(st.session_state.historico)
            st.rerun()

if st.session_state.modo_automatico:
    st_autorefresh(interval=3000, key="refresh")
    res = fetch_latest_result()
    if res and res.get("number") is not None:
        if not st.session_state.historico or res["timestamp"] != st.session_state.historico[-1].get("timestamp"):
            st.session_state.historico.append(res)
            sis.processar_novo_numero(res)
            salvar_resultado_em_arquivo(st.session_state.historico)
            st.rerun()

# =============================
# MÉTRICAS
# =============================
st.markdown("---")
c1, c2, c3, c4, c5 = st.columns(5)
total = int(sis.acertos + sis.erros)
tx = (sis.acertos / total * 100) if total > 0 else 0
c1.metric("✅", int(sis.acertos))
c2.metric("❌", int(sis.erros))
c3.metric("📊", f"{tx:.0f}%")
c4.metric("🎯", f"D{sis.entrada_ativa['duzia_prevista']}" if sis.entrada_ativa else "-")
c5.metric("🧠", "V4")

# =============================
# GRÁFICOS + ENTRADA
# =============================
st.markdown("---")
col_graf, col_ent = st.columns([3, 2])

with col_graf:
    st.subheader("📈 Análise")
    
    if len(sis.historico_numeros) >= 5:
        score, regime, detalhes = sis.bot.calcular_score()
        
        fig = go.Figure(data=[go.Bar(
            x=['D1', 'D2', 'D3'],
            y=[score[1], score[2], score[3]],
            marker_color=['#FF6B6B' if score[1]==max(score.values()) else '#4ECDC4',
                         '#FF6B6B' if score[2]==max(score.values()) else '#4ECDC4',
                         '#FF6B6B' if score[3]==max(score.values()) else '#4ECDC4'],
            text=[f'{score[1]:.0f}', f'{score[2]:.0f}', f'{score[3]:.0f}'],
            textposition='auto'
        )])
        fig.update_layout(title=f"Scores | {regime}", height=250, showlegend=False)
        st.plotly_chart(fig, use_container_width=True, key="chart_scores")
        
        if len(sis.historico_numeros) >= 5:
            ultimos = list(sis.historico_numeros)[-20:]
            duzias = [get_duzia(n) for n in ultimos]
            
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                y=duzias, mode='lines+markers',
                line=dict(color='#FFD700', width=2),
                marker=dict(size=8), name='Dúzia'
            ))
            
            if sis.sinais_grafico:
                sx, sy = [], []
                offset = len(duzias) - 20
                for idx, dz in sis.sinais_grafico[-10:]:
                    pos = idx - offset
                    if 0 <= pos < 20:
                        sx.append(pos); sy.append(dz)
                if sx:
                    fig2.add_trace(go.Scatter(
                        x=sx, y=sy, mode='markers',
                        marker=dict(symbol='star', size=12, color='red'),
                        name='Entrada'
                    ))
            
            fig2.update_layout(
                title="Histórico de Dúzias",
                yaxis=dict(tickvals=[1,2,3], ticktext=['D1','D2','D3'], range=[0.5,3.5]),
                height=250, showlegend=True
            )
            st.plotly_chart(fig2, use_container_width=True, key="chart_history")
    else:
        st.info(f"⏳ {len(sis.historico_numeros)}/5 giros")

with col_ent:
    st.subheader("🎰 Entrada")
    
    if sis.entrada_ativa:
        ent = sis.entrada_ativa
        dz1 = ent.get('duzia_prevista', 0)
        dz2 = ent.get('duzia_secundaria', 0)
        conf = ent.get('confianca', 0) or 0.0
        
        limite1 = "1-12" if dz1==1 else "13-24" if dz1==2 else "25-36"
        limite2 = "1-12" if dz2==1 else "13-24" if dz2==2 else "25-36"
        
        st.markdown(f"""
        <div style="background-color:#00CC0022; border:2px solid #00CC00; border-radius:15px; padding:15px;">
            <h3 style="color:#00CC00; text-align:center;">📊 D{dz1} ({limite1})</h3>
            <p style="text-align:center;">🛡️ D{dz2} ({limite2})</p>
        </div>
        """, unsafe_allow_html=True)
        
        nums = ent.get('numeros_apostar', [])
        if nums:
            st.write("**🎲 Números:**")
            cols = st.columns(6)
            for i, n in enumerate(sorted(nums)):
                cols[i%6].button(str(n), key=f"btn_{n}", use_container_width=True)
        
        st.progress(float(min(1.0, conf/100)))
    
    if sis.ultimo_numero is not None:
        st.markdown("---")
        st.write(f"🔄 Último: #{sis.ultimo_numero} → D{get_duzia(sis.ultimo_numero)}")

# =============================
# HISTÓRICO
# =============================
st.markdown("---")
st.subheader("📝 Histórico")

if sis.historico_entradas:
    tabela = []
    for e in reversed(sis.historico_entradas[-15:]):
        tabela.append({
            "Rod": e.get('rodada', '-'),
            "Nº": e.get('resultado', '-'),
            "Real": e.get('duzia_real', '-'),
            "Prev": e.get('duzia_prevista', '-'),
            "Res": "✅" if e.get('acerto_primaria') else "🟡" if e.get('acerto') else "❌"
        })
    st.dataframe(tabela, use_container_width=True, height=250)
else:
    st.info("Nenhuma entrada ainda. Digite números para começar.")

st.caption(f"🎯 DuziaAI V4 | {datetime.now().strftime('%H:%M:%S')}")
salvar_sessao()
