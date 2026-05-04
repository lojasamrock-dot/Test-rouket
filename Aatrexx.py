import streamlit as st
import json
import os
import requests
import logging
import random
from collections import Counter, deque
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
ENTRADAS_PATH = "historico_entradas.json"
ML_MODEL_PATH = "modelo_xgboost.pkl"

def salvar_sessao():
    try:
        if 'sistema' not in st.session_state or st.session_state.sistema is None:
            return False
        sis = st.session_state.sistema
        
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
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, ENTRADAS_PATH, ML_MODEL_PATH]:
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
# 🧠 ANALISADOR DE DÚZIAS (SIMPLES E FUNCIONAL)
# =============================
class AnalisadorDuzias:
    def __init__(self, window=20):
        self.historico_duzias = deque(maxlen=window)
        self.historico_numeros = deque(maxlen=200)
    
    def adicionar(self, numero):
        d = get_duzia(numero)
        self.historico_duzias.append(d)
        self.historico_numeros.append(numero)
    
    def analisar(self):
        if len(self.historico_duzias) < 3:
            return None
        
        score = {1: 0, 2: 0, 3: 0}
        
        # Frequência recente
        freq = Counter(self.historico_duzias)
        total = len(self.historico_duzias)
        for d in [1, 2, 3]:
            score[d] += (freq.get(d, 0) / total) * 40
        
        # Streak
        ultima = self.historico_duzias[-1]
        streak = 0
        for d in reversed(self.historico_duzias):
            if d == ultima: streak += 1
            else: break
        
        if streak >= 2 and ultima != 0:
            score[ultima] += streak * 8
        elif streak == 1 and ultima != 0:
            score[ultima] += 3
        
        # Padrão ABA (ex: D1→D2→D1)
        u = list(self.historico_duzias)
        if len(u) >= 3 and u[-1] == u[-3] and u[-1] != u[-2] and u[-1] != 0:
            score[u[-1]] += 10
        
        # Padrão ABAB (ex: D1→D2→D1→D2)
        if len(u) >= 4 and u[-1] == u[-3] and u[-2] == u[-4] and u[-1] != u[-2] and u[-1] != 0:
            score[u[-2]] += 12
        
        # Ausência
        for d in [1, 2, 3]:
            ausencia = 0
            for dz in reversed(self.historico_duzias):
                if dz == d: break
                ausencia += 1
            if ausencia >= 6:
                score[d] += min(8, ausencia)
        
        # Ranking
        ranking = sorted(score.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'duzia_principal': ranking[0][0],
            'duzia_secundaria': ranking[1][0],
            'score': {1: round(score[1], 1), 2: round(score[2], 1), 3: round(score[3], 1)},
            'confianca': round(ranking[0][1] - ranking[1][1], 1)
        }

# =============================
# 🤖 ML PREDICTOR (SIMPLIFICADO)
# =============================
class MLPredictor:
    def __init__(self):
        self.model = None
        self.ready = False
        self.training_samples = 0
    
    def treinar(self, historico_duzias, historico_numeros):
        if len(historico_duzias) < 10:
            return False
        
        try:
            from xgboost import XGBClassifier
            
            X, y = [], []
            for i in range(5, len(historico_duzias)):
                janela = list(historico_duzias)[i-5:i]
                if len(janela) < 5: continue
                
                features = []
                freq = Counter(janela)
                for d in [1, 2, 3]:
                    features.append(freq.get(d, 0) / 5)
                
                ultima = janela[-1]
                streak = 0
                for d in reversed(janela):
                    if d == ultima: streak += 1
                    else: break
                features.append(streak)
                features.append(ultima)
                
                target = historico_duzias[i]
                if target != 0:
                    X.append(features)
                    y.append(target - 1)
            
            if len(X) < 5:
                return False
            
            self.model = XGBClassifier(
                n_estimators=30, max_depth=2, learning_rate=0.1,
                objective='multi:softprob', num_class=3,
                use_label_encoder=False, eval_metric='mlogloss',
                verbosity=0, random_state=42
            )
            self.model.fit(np.array(X), np.array(y))
            self.training_samples = len(X)
            self.ready = True
            
            with open(ML_MODEL_PATH, 'wb') as f:
                pickle.dump({'model': self.model, 'samples': self.training_samples}, f)
            
            return True
        except ImportError:
            return False
        except Exception:
            return False
    
    def carregar(self):
        try:
            if os.path.exists(ML_MODEL_PATH):
                with open(ML_MODEL_PATH, 'rb') as f:
                    data = pickle.load(f)
                    self.model = data.get('model')
                    self.training_samples = data.get('samples', 0)
                    self.ready = self.model is not None
                return True
        except:
            pass
        return False
    
    def prever(self, historico_duzias):
        if not self.ready or len(historico_duzias) < 5:
            return None
        
        try:
            janela = list(historico_duzias)[-5:]
            features = []
            freq = Counter(janela)
            for d in [1, 2, 3]:
                features.append(freq.get(d, 0) / 5)
            
            ultima = janela[-1]
            streak = 0
            for d in reversed(janela):
                if d == ultima: streak += 1
                else: break
            features.append(streak)
            features.append(ultima)
            
            X = np.array([features])
            probs = self.model.predict_proba(X)[0]
            
            ranking = np.argsort(probs)[::-1]
            return {
                'duzia_principal': int(ranking[0]) + 1,
                'duzia_secundaria': int(ranking[1]) + 1,
                'confianca': round(float(probs[ranking[0]] - probs[ranking[1]]), 2),
                'probabilidades': {
                    1: round(float(probs[0]) * 100, 1),
                    2: round(float(probs[1]) * 100, 1),
                    3: round(float(probs[2]) * 100, 1)
                }
            }
        except Exception:
            return None

# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaBot:
    def __init__(self):
        self.analisador = AnalisadorDuzias(window=20)
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
        
        self.analisador.adicionar(nr)
        self.historico_numeros.append(nr)
        self.ultimo_numero = nr
        
        # Verifica acerto
        if self.entrada_ativa:
            duzia_real = get_duzia(nr)
            duzia_prevista = self.entrada_ativa.get('duzia_prevista')
            duzia_sec = self.entrada_ativa.get('duzia_secundaria')
            
            acertou = (duzia_real == duzia_prevista or duzia_real == duzia_sec) if nr != 0 else False
            acerto_primario = (duzia_real == duzia_prevista) if nr != 0 else False
            
            if acerto_primario:
                self.acertos += 1
                st.session_state.acertos_duzia = st.session_state.get('acertos_duzia', 0) + 1
            elif acertou:
                self.acertos += 0.5
            else:
                self.erros += 1
                st.session_state.erros_duzia = st.session_state.get('erros_duzia', 0) + 1
            
            self.historico_entradas.append({
                'rodada': len(self.historico_numeros),
                'hora': datetime.now().strftime('%H:%M:%S'),
                'resultado': nr,
                'duzia_real': f"D{duzia_real}" if duzia_real != 0 else "Z",
                'duzia_prevista': f"D{duzia_prevista}",
                'acerto': acertou,
                'modo': self.entrada_ativa.get('modo', 'regras')
            })
            
            if len(self.historico_entradas) > 50:
                self.historico_entradas = self.historico_entradas[-50:]
            
            enviar_resultado_auto(nr, acertou)
            self.entrada_ativa = None
        
        # Treina ML
        if st.session_state.get('modo_ml', False) and not self.ml.ready:
            if len(self.historico_numeros) >= st.session_state.get('giros_minimos_ml', 10):
                self.ml.treinar(
                    [get_duzia(n) for n in self.historico_numeros],
                    list(self.historico_numeros)
                )
        
        # 🆕 GERA PREVISÃO SEMPRE
        duzia_map = {1: list(range(1, 13)), 2: list(range(13, 25)), 3: list(range(25, 37))}
        
        # Tenta ML
        previsao_ml = None
        if st.session_state.get('modo_ml', False) and self.ml.ready:
            previsao_ml = self.ml.prever([get_duzia(n) for n in self.historico_numeros])
        
        # Analisador de regras
        analise = self.analisador.analisar()
        
        if previsao_ml:
            dz1 = previsao_ml['duzia_principal']
            dz2 = previsao_ml['duzia_secundaria']
            conf = previsao_ml['confianca'] * 50
            modo = 'ml'
        else:
            dz1 = analise['duzia_principal']
            dz2 = analise['duzia_secundaria']
            conf = analise['confianca'] * 3
            modo = 'regras'
        
        # Monta números
        if st.session_state.get('modo_agressivo', False):
            numeros = sorted(set(duzia_map.get(dz1, []) + duzia_map.get(dz2, [])))
        else:
            numeros = sorted(duzia_map.get(dz1, []))
        
        self.entrada_ativa = {
            'numeros_apostar': numeros,
            'duzia_prevista': dz1,
            'duzia_secundaria': dz2,
            'confianca': float(conf),
            'modo': modo
        }
        
        # Registra sinal no gráfico
        self.sinais_grafico.append((len(self.historico_numeros) - 1, dz1))
        
        # Toast
        st.toast(f"{'🤖' if modo == 'ml' else '📊'} D{dz1} | Conf: {conf:.0f}%")
        salvar_sessao()
    
    def zerar(self):
        self.acertos = 0
        self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear()
        self.entrada_ativa = None
        self.ultimo_numero = None
        self.sinais_grafico = []
        self.analisador = AnalisadorDuzias(window=20)
        self.ml = MLPredictor()
        st.session_state.acertos_duzia = 0
        st.session_state.erros_duzia = 0
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
        rs = d.get("data", {}).get("result", {})
        nm = rs.get("outcome", {}).get("number")
        ts = d.get("data", {}).get("startedAt")
        return {"number": nm, "timestamp": ts}
    except:
        return None

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎰 DuziaAI V7 - Funcional", layout="wide")
st.title("🎰 DuziaAI V7 - Análise em Tempo Real")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    sis = st.session_state.sistema
    for n in dados.get('historico_numeros', []):
        sis.analisador.adicionar(n)
        sis.historico_numeros.append(n)
    sis.acertos = dados.get('sistema_acertos', 0)
    sis.erros = dados.get('sistema_erros', 0)
    sis.entrada_ativa = dados.get('entrada_ativa', None)
    st.session_state.acertos_duzia = dados.get('acertos_duzia', 0)
    st.session_state.erros_duzia = dados.get('erros_duzia', 0)
    st.session_state.modo_agressivo = dados.get('modo_agressivo', False)
    st.session_state.modo_ml = dados.get('modo_ml', False)
    if os.path.exists(ENTRADAS_PATH):
        try:
            with open(ENTRADAS_PATH, 'r') as f:
                sis.historico_entradas = json.load(f)
        except:
            pass

# Defaults
for k, v in {
    'modo_automatico': True, 'modo_agressivo': False, 'modo_ml': False,
    'giros_minimos_ml': 10, 'acertos_duzia': 0, 'erros_duzia': 0
}.items():
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

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.markdown("## ⚙️ Config")
    
    st.session_state.modo_ml = st.checkbox("🤖 Ativar Machine Learning", value=st.session_state.modo_ml)
    
    if st.session_state.modo_ml:
        st.session_state.giros_minimos_ml = st.slider("Giros para treinar ML", 5, 30, st.session_state.giros_minimos_ml, 5)
        sis = st.session_state.sistema
        if sis.ml.ready:
            st.success(f"✅ ML treinado ({sis.ml.training_samples} amostras)")
        else:
            st.warning(f"⏳ Aguardando {st.session_state.giros_minimos_ml} giros")
            if len(sis.historico_numeros) >= st.session_state.giros_minimos_ml:
                if st.button("🧠 FORÇAR TREINO", use_container_width=True):
                    sis.ml.treinar([get_duzia(n) for n in sis.historico_numeros], list(sis.historico_numeros))
                    st.rerun()
    
    st.session_state.modo_agressivo = st.checkbox("🔥 2 Dúzias", value=st.session_state.modo_agressivo)
    st.session_state.modo_automatico = st.checkbox("🤖 Auto", value=st.session_state.modo_automatico)
    
    c1, c2 = st.columns(2)
    c1.button("💾 Salvar", on_click=lambda: [salvar_resultado_em_arquivo(st.session_state.historico), salvar_sessao()])
    c2.button("🗑️ Zerar", on_click=lambda: st.session_state.sistema.zerar() or st.rerun())

# =============================
# INPUT
# =============================
sis = st.session_state.sistema

c1, c2 = st.columns([3, 1])
with c1:
    entrada = st.text_input("Número (0-36):", key="num_input", placeholder="Digite e Enter")
with c2:
    if st.button("🎯 Enviar", use_container_width=True):
        if entrada and entrada.isdigit() and 0 <= int(entrada) <= 36:
            nr = int(entrada)
            st.session_state.historico.append({"number": nr, "timestamp": datetime.now().isoformat()})
            sis.processar_novo_numero(nr)
            salvar_resultado_em_arquivo(st.session_state.historico)
            st.rerun()

# Auto refresh
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
c5.metric("🧠", "🤖ML" if st.session_state.modo_ml else "📊Regras")

# =============================
# GRÁFICOS + ENTRADA
# =============================
col_graf, col_ent = st.columns([3, 2])

with col_graf:
    st.subheader("📈 Análise")
    
    if len(sis.historico_numeros) >= 5:
        analise = sis.analisador.analisar()
        
        if analise:
            score = analise['score']
            
            # Gráfico de barras
            fig = go.Figure(data=[go.Bar(
                x=['D1 (1-12)', 'D2 (13-24)', 'D3 (25-36)'],
                y=[score[1], score[2], score[3]],
                marker_color=['#FF6B6B' if score[1] == max(score.values()) else '#4ECDC4',
                             '#FF6B6B' if score[2] == max(score.values()) else '#4ECDC4',
                             '#FF6B6B' if score[3] == max(score.values()) else '#4ECDC4'],
                text=[f'{score[1]}', f'{score[2]}', f'{score[3]}'],
                textposition='auto'
            )])
            fig.update_layout(title="Scores das Dúzias", height=250, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        # Gráfico de linha
        if len(sis.historico_numeros) >= 5:
            ultimos = list(sis.historico_numeros)[-20:]
            duzias = [get_duzia(n) for n in ultimos]
            
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                y=duzias, mode='lines+markers',
                line=dict(color='#FFD700', width=2),
                marker=dict(size=8)
            ))
            
            # Sinais no gráfico
            if sis.sinais_grafico:
                sx, sy = [], []
                offset = len(duzias) - 20
                for idx, dz in sis.sinais_grafico[-10:]:
                    pos = idx - offset
                    if 0 <= pos < 20:
                        sx.append(pos)
                        sy.append(dz)
                if sx:
                    fig2.add_trace(go.Scatter(
                        x=sx, y=sy, mode='markers',
                        marker=dict(symbol='star', size=12, color='red'),
                        name='Entrada'
                    ))
            
            fig2.update_layout(
                title="Histórico de Dúzias",
                yaxis=dict(tickvals=[1, 2, 3], ticktext=['D1', 'D2', 'D3'], range=[0.5, 3.5]),
                height=250, showlegend=True
            )
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info(f"⏳ {len(sis.historico_numeros)}/5 giros")

with col_ent:
    st.subheader("🎰 Entrada Atual")
    
    if sis.entrada_ativa:
        ent = sis.entrada_ativa
        dz1 = ent.get('duzia_prevista', 0)
        dz2 = ent.get('duzia_secundaria', 0)
        conf = ent.get('confianca', 0) or 0.0
        modo = ent.get('modo', 'regras')
        
        cor = "#8A2BE2" if modo == 'ml' else "#00CC00"
        emoji = "🤖" if modo == 'ml' else "📊"
        
        limite1 = "1-12" if dz1 == 1 else "13-24" if dz1 == 2 else "25-36"
        limite2 = "1-12" if dz2 == 1 else "13-24" if dz2 == 2 else "25-36"
        
        st.markdown(f"""
        <div style="background-color:{cor}22; border:2px solid {cor}; border-radius:15px; padding:15px;">
            <h3 style="color:{cor}; text-align:center;">{emoji} D{dz1} ({limite1})</h3>
            <p style="text-align:center;">Confiança: {conf:.0f}%</p>
            <p style="text-align:center; color:#FFA500;">🛡️ D{dz2} ({limite2})</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("**🎲 Apostar em:**")
        nums = ent.get('numeros_apostar', [])
        cols = st.columns(6)
        for i, n in enumerate(sorted(nums)):
            cols[i % 6].button(str(n), key=f"n{n}", use_container_width=True)
        
        st.progress(float(min(1.0, conf / 100)))
    
    if sis.ultimo_numero is not None:
        st.markdown("---")
        st.write(f"🔄 #{sis.ultimo_numero} → D{get_duzia(sis.ultimo_numero)}")

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
            "Res": "✅" if e.get('acerto') else "❌"
        })
    st.dataframe(tabela, use_container_width=True, height=250)

st.caption(f"🤖 DuziaAI V7 | {datetime.now().strftime('%H:%M:%S')}")
salvar_sessao()
