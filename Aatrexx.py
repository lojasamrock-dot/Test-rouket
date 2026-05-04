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
ML_DATA_PATH = "ml_training_data.json"

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
            'modo_duzia_ai': st.session_state.get('modo_duzia_ai', True),
            'modo_ml': st.session_state.get('modo_ml', False),
            'janela_duzia_ai': st.session_state.get('janela_duzia_ai', 30),
            'acertos_duzia': st.session_state.get('acertos_duzia', 0),
            'erros_duzia': st.session_state.get('erros_duzia', 0),
            'acertos_duzia_sec': st.session_state.get('acertos_duzia_sec', 0),
            'erros_duzia_sec': st.session_state.get('erros_duzia_sec', 0),
            'modo_agressivo': st.session_state.get('modo_agressivo', False),
            'confianca_minima': st.session_state.get('confianca_minima', 3.2),
            'agressividade': st.session_state.get('agressividade', 2),
            'confianca_ml': st.session_state.get('confianca_ml', 0.15),
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
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH, ENTRADAS_PATH, ML_MODEL_PATH, ML_DATA_PATH]:
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
# 🧠 MACHINE LEARNING PREDICTOR (XGBoost)
# =============================
class MLPredictor:
    """
    Modelo de Machine Learning com XGBoost para previsão de dúzias.
    Aprende com o histórico acumulado e se adapta ao mercado.
    """
    def __init__(self):
        self.model = None
        self.feature_names = []
        self.accuracy_history = []
        self.last_training = None
        self.training_samples = 0
        self.ready = False
    
    def extrair_features(self, historico_duzias, historico_numeros):
        """Extrai features dos últimos giros para alimentar o modelo"""
        features = {}
        
        # Frequências das dúzias nos últimos 5, 10, 15, 20 giros
        for w in [5, 10, 15, 20]:
            janela = historico_duzias[-w:] if len(historico_duzias) >= w else historico_duzias
            freq = Counter(janela)
            total = len(janela) if janela else 1
            for dz in [1, 2, 3]:
                features[f'freq_dz{dz}_{w}g'] = freq.get(dz, 0) / total
        
        # Streak atual
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
        
        # Dúzias nos últimos giros
        for i in range(1, 6):
            idx = -i
            if len(historico_duzias) >= abs(idx):
                features[f'duzia_t{i}'] = historico_duzias[idx] if historico_duzias[idx] != 0 else 0
            else:
                features[f'duzia_t{i}'] = 0
        
        # Ausência
        for dz in [1, 2, 3]:
            ausencia = 0
            for d in reversed(historico_duzias):
                if d == dz: break
                ausencia += 1
            features[f'ausencia_dz{dz}'] = ausencia
        
        # Terminais
        if historico_numeros:
            ultimos = historico_numeros[-10:]
            terms = [n % 10 for n in ultimos if n != 0]
            if terms:
                top_terminal = Counter(terms).most_common(1)[0][0]
                features['terminal_quente'] = top_terminal
                duzia_map = {1: range(1,13), 2: range(13,25), 3: range(25,37)}
                for dz in [1, 2, 3]:
                    count = sum(1 for n in duzia_map[dz] if n % 10 == top_terminal)
                    features[f'terminal_dz{dz}'] = count
        
        # Padrões
        u = historico_duzias[-3:] if len(historico_duzias) >= 3 else []
        features['padrao_aba'] = 1 if len(u)==3 and u[0]==u[2] and u[0]!=u[1] else 0
        features['padrao_abb'] = 1 if len(u)==3 and u[0]!=u[1] and u[1]==u[2] else 0
        features['padrao_repeticao'] = 1 if len(u)>=2 and u[-1]==u[-2] else 0
        
        return features
    
    def treinar(self, historico_completo_duzias, historico_completo_numeros):
        """Treina o modelo com todo o histórico disponível"""
        if len(historico_completo_duzias) < 50:
            return False
        
        X_data = []
        y_data = []
        
        for i in range(20, len(historico_completo_duzias)):
            janela_duzias = historico_completo_duzias[i-20:i]
            janela_numeros = historico_completo_numeros[i-20:i] if i-20 >= 0 else []
            features = self.extrair_features(janela_duzias, janela_numeros)
            
            if i < len(historico_completo_duzias):
                target = historico_completo_duzias[i]
                if target != 0:
                    X_data.append(features)
                    y_data.append(target - 1)  # 0=D1, 1=D2, 2=D3
        
        if len(X_data) < 30:
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
            
            # Salva modelo
            self.salvar()
            return True
        except ImportError:
            logging.warning("XGBoost não instalado. Usando fallback simples.")
            self.ready = False
            return False
    
    def prever(self, historico_duzias, historico_numeros):
        """Faz a previsão da próxima dúzia"""
        if not self.ready or self.model is None:
            return None
        
        features = self.extrair_features(historico_duzias, historico_numeros)
        
        try:
            X = np.array([[features.get(f, 0) for f in self.feature_names]])
            probs = self.model.predict_proba(X)[0]
            
            ranking = np.argsort(probs)[::-1]
            melhor_dz = ranking[0] + 1
            segunda_dz = ranking[1] + 1
            confianca = probs[ranking[0]] - probs[ranking[1]]
            
            return {
                'duzia': melhor_dz,
                'duzia_secundaria': segunda_dz,
                'confianca': confianca,
                'probabilidades': {1: probs[0], 2: probs[1], 3: probs[2]},
                'entrar': confianca >= st.session_state.get('confianca_ml', 0.15)
            }
        except Exception as e:
            logging.error(f"Erro na previsão ML: {e}")
            return None
    
    def salvar(self):
        try:
            with open(ML_MODEL_PATH, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'feature_names': self.feature_names,
                    'training_samples': self.training_samples,
                    'accuracy_history': self.accuracy_history
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
                    self.accuracy_history = data.get('accuracy_history', [])
                    self.ready = self.model is not None
                return True
        except:
            pass
        return False

# =============================
# 🧠 DUZIA AI V4.3 (REGRA FIXA - MANTIDA)
# =============================
class DuziaAI:
    def __init__(self, window=30):
        self.historico = deque(maxlen=window)
        self.historico_completo = []
        self.numeros_completos = []
        self.sinais_entrada = []
    
    def adicionar(self, numero):
        d = get_duzia(numero)
        self.historico.append(d)
        self.historico_completo.append(d)
        self.numeros_completos.append(numero)
        if len(self.historico_completo) > 200:
            self.historico_completo = self.historico_completo[-200:]
        if len(self.numeros_completos) > 200:
            self.numeros_completos = self.numeros_completos[-200:]
    
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
        totais = {1:0, 2:0, 3:0}
        for i in range(len(self.historico_completo)-1):
            o, d = self.historico_completo[i], self.historico_completo[i+1]
            if o!=0 and d!=0:
                peso = 1 + (i/max(1,len(self.historico_completo)))*2
                matriz[o][d] += peso
                totais[o] += peso
        prob = {}
        for o in [1,2,3]:
            prob[o] = {d: (matriz[o][d]/totais[o]*100) if totais[o]>0 else 33.3 for d in [1,2,3]}
        return prob
    
    def detectar_retorno_aba(self):
        if len(self.historico) < 3: return None
        u = list(self.historico)[-3:]
        if u[0]==u[2] and u[0]!=u[1] and u[0]!=0 and u[1]!=0:
            return u[0], 5
        return None
    
    def detectar_duas_dominantes(self):
        if len(self.historico) < 10: return None
        u = list(self.historico)[-10:]
        freq = Counter(u)
        ranking = freq.most_common()
        if len(ranking)>=2 and ranking[0][1]+ranking[1][1]>=8:
            return (ranking[0][0], ranking[1][0]), 3
        return None
    
    def detectar_progressao(self):
        if len(self.historico) < 4: return None
        u = list(self.historico)[-4:]
        if u[0]==u[1] and u[2]==u[3] and u[1]!=u[2] and u[0]!=0 and u[2]!=0:
            return u[2], 4
        return None
    
    def detectar_streak_longo(self):
        c, d = self.streak()
        if c>=3 and d!=0: return d, min(10, 4+(c-3)*2)
        return None
    
    def detectar_pos_zero(self):
        if len(self.historico)<3: return None
        u = list(self.historico)[-3:]
        if u[-1]==0 or u[-2]==0:
            for d in reversed(u[:-1]):
                if d!=0: return d, 5
        return None
    
    def detectar_vai_e_volta(self):
        u = list(self.historico)
        if len(u)>=4 and u[-4]==u[-2] and u[-3]==u[-1] and u[-4]!=u[-3] and u[-4]!=0 and u[-3]!=0:
            return u[-3], 6
        if len(u)>=5 and u[-5]==u[-3]==u[-1] and u[-4]==u[-2] and u[-5]!=u[-4] and u[-5]!=0 and u[-4]!=0:
            return u[-4], 8
        return None
    
    def detectar_repeticao_imediata(self):
        if len(self.historico)<3: return None
        u = list(self.historico)[-3:]
        if u[0]!=u[1] and u[1]==u[2] and u[1]!=0: return u[1], 6
        if len(self.historico)>=2:
            u2 = list(self.historico)[-2:]
            if u2[0]==u2[1] and u2[0]!=0: return u2[0], 4
        return None
    
    def detectar_troca_d1_d2(self):
        if len(self.historico)<6: return None
        u = list(self.historico)[-6:]
        trocas = sum(1 for i in range(1,len(u)) if (u[i-1]==1 and u[i]==2) or (u[i-1]==2 and u[i]==1))
        if trocas>=3: return 2 if u[-1]==1 else 1, 5
        return None
    
    def detectar_bloco_d3(self):
        if len(self.historico)<5: return None
        u = list(self.historico)[-5:]
        d3c = u[-4:].count(3)
        if d3c>=2: return 3, 5
        if u[-1]==3 and d3c>=1: return 3, 3
        return None
    
    def detectar_ciclos(self):
        if len(self.historico)<6: return None
        u = list(self.historico)
        if len(u)>=4 and u[-4]==u[-2] and u[-3]==u[-1] and u[-4]!=u[-3]: return u[-3]
        if len(u)>=6 and u[-6:-3]==u[-3:]: return u[-6]
        return None
    
    def ausencia(self):
        aus = {1:0,2:0,3:0}
        for d in reversed(self.historico):
            for dz in aus:
                if d!=dz: aus[dz]+=1
        dz = max(aus, key=aus.get)
        if aus[dz]>=5: return dz, aus[dz]
        return None
    
    def terminais(self):
        if len(self.numeros_completos)<10: return None
        nums = self.numeros_completos[-10:]
        terms = [n%10 for n in nums if n!=0]
        top = [t[0] for t in Counter(terms).most_common(2)]
        score = {1:0,2:0,3:0}
        for n in range(1,37):
            dz = get_duzia(n)
            if n%10 in top: score[dz]+=1
        best = max(score, key=score.get)
        if score[best]>=3: return best, score[best]
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
        if rep:
            dz, fc = rep
            if dz!=0: score[dz]+=fc; detalhes[dz].append(f"Repetição:+{fc}")
        
        sl = self.detectar_streak_longo()
        if sl:
            dz, fc = sl
            if dz!=0: score[dz]+=fc; detalhes[dz].append(f"Streak:+{fc}")
        
        pz = self.detectar_pos_zero()
        if pz:
            dz, fc = pz
            if dz!=0: score[dz]+=fc; detalhes[dz].append(f"Pós-Zero:+{fc}")
        
        vv = self.detectar_vai_e_volta()
        if vv:
            dz, fc = vv
            if dz!=0: score[dz]+=fc; detalhes[dz].append(f"Vai-e-Volta:+{fc}")
        
        aba = self.detectar_retorno_aba()
        if aba:
            dz, fc = aba
            if dz!=0: score[dz]+=fc; detalhes[dz].append(f"ABA:+{fc}")
        
        duas = self.detectar_duas_dominantes()
        if duas:
            doms, fc = duas
            for dz in doms:
                if dz!=0: score[dz]+=fc; detalhes[dz].append(f"Dominante:+{fc}")
            terceira = [d for d in [1,2,3] if d not in doms]
            for dz in terceira: score[dz]-=2
        
        prog = self.detectar_progressao()
        if prog:
            dz, fc = prog
            if dz!=0: score[dz]+=fc; detalhes[dz].append(f"Progressão:+{fc}")
        
        troca = self.detectar_troca_d1_d2()
        if troca:
            dz, fc = troca
            if dz!=0: score[dz]+=fc; detalhes[dz].append(f"Troca:+{fc}")
        
        bloco = self.detectar_bloco_d3()
        if bloco:
            dz, fc = bloco
            if dz!=0: score[dz]+=fc; detalhes[dz].append(f"Bloco D3:+{fc}")
        
        ciclo = self.detectar_ciclos()
        if ciclo and ciclo!=0 and max(score.values())>3: score[ciclo]+=5
        
        aus = self.ausencia()
        if aus:
            dz, g = aus
            if dz!=0: score[dz]+=min(5,g*0.5)
        
        term = self.terminais()
        if term:
            dz, q = term
            if dz!=0: score[dz]+=q*0.3
        
        total = sum(score.values())
        if total>0:
            for d in score: score[d] = (score[d]/total)*100
        
        return score, regime, detalhes
    
    def prever(self, confianca_minima=3.2, agressividade=2):
        score, regime, detalhes = self.calcular_score()
        ranking = sorted(score.items(), key=lambda x: x[1], reverse=True)
        d1, s1 = ranking[0]
        d2, s2 = ranking[1]
        
        ratio = s1/max(1,s2)
        vol = np.std(list(score.values()))
        confianca = (ratio*2.2)+(1.5/(1+vol))
        confianca_ajustada = confianca_minima-(0.4*(2-agressividade))
        
        forca_detectores = 0
        for dz in detalhes:
            for det in detalhes[dz]:
                if '+' in det:
                    try: forca_detectores += float(det.split('+')[1].strip())
                    except: pass
        
        c, _ = self.streak()
        tem_streak = c>=3
        tem_duas = self.detectar_duas_dominantes() is not None
        pode_entrar = False
        motivo = ""
        
        if regime=="DISTRIBUIDO" and not tem_streak and forca_detectores<5 and not tem_duas:
            motivo = "Mercado distribuído sem padrão claro"
        elif regime=="DISTRIBUIDO" and (tem_streak or tem_duas) and confianca<2.0:
            motivo = f"Distribuído com padrão fraco ({confianca:.2f})"
        elif confianca<confianca_ajustada and not tem_streak and forca_detectores<5:
            motivo = f"Confiança baixa ({confianca:.2f}<{confianca_ajustada})"
        elif regime=="TRANSICAO" and confianca<2.8 and not tem_streak and not tem_duas:
            motivo = f"Transição sem padrão ({confianca:.2f})"
        else:
            pode_entrar = True
        
        if not pode_entrar:
            return {"entrar":False,"motivo":motivo,"score":score,"regime":regime,"confianca":round(confianca,2),"duzia":d1,"duzia_secundaria":d2,"detalhes":detalhes}
        
        return {"entrar":True,"duzia":d1,"duzia_secundaria":d2,"confianca":round(confianca,2),"score":score,"regime":regime,"detalhes":detalhes}

# =============================
# SISTEMA PRINCIPAL (COM MODO ML INTEGRADO)
# =============================
class SistemaBot:
    def __init__(self):
        janela = st.session_state.get('janela_duzia_ai', 30)
        self.duzia_ai = DuziaAI(window=janela)
        self.ml_predictor = MLPredictor()
        self.ml_accuracy_recente = []
        self.historico_numeros = deque(maxlen=200)
        self.entrada_ativa = None
        self.historico_entradas = []
        self.acertos = 0
        self.erros = 0
        self.ultimo_numero = None
        self.sinais_grafico = []
        self.ml_entradas_count = 0
        self.ml_acertos = 0
        
        # Tenta carregar modelo ML salvo
        if st.session_state.get('modo_ml', False):
            self.ml_predictor.carregar()
    
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data['number']
        else:
            nr = int(numero_data)
        
        self.duzia_ai.adicionar(nr)
        self.historico_numeros.append(nr)
        self.ultimo_numero = nr
        
        if self.entrada_ativa:
            duzia_real = get_duzia(nr)
            duzia_prevista = self.entrada_ativa.get('duzia_prevista')
            duzia_sec_prevista = self.entrada_ativa.get('duzia_sec_prevista')
            
            acerto_primaria = (duzia_real==duzia_prevista) if duzia_prevista and nr!=0 else False
            acerto_secundaria = (duzia_real==duzia_sec_prevista) if duzia_sec_prevista and nr!=0 else False
            
            if acerto_primaria:
                self.acertos += 1
                st.session_state.acertos_duzia = st.session_state.get('acertos_duzia', 0)+1
                if self.entrada_ativa.get('modo') == 'ml':
                    self.ml_acertos += 1
            elif acerto_secundaria:
                st.session_state.acertos_duzia_sec = st.session_state.get('acertos_duzia_sec', 0)+1
                self.acertos += 0.5
                if self.entrada_ativa.get('modo') == 'ml':
                    self.ml_acertos += 0.5
            else:
                self.erros += 1
                st.session_state.erros_duzia = st.session_state.get('erros_duzia', 0)+1
            
            entrada_info = {
                'rodada': len(self.historico_numeros)-1,
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
            if len(self.historico_entradas)>50:
                self.historico_entradas = self.historico_entradas[-50:]
            
            # Atualiza métricas do ML
            if self.entrada_ativa.get('modo') == 'ml':
                self.ml_entradas_count += 1
                self.ml_accuracy_recente.append(1 if acerto_primaria else 0.5 if acerto_secundaria else 0)
                if len(self.ml_accuracy_recente) > 20:
                    self.ml_accuracy_recente = self.ml_accuracy_recente[-20:]
            
            enviar_resultado_auto(nr, acerto_primaria or acerto_secundaria)
            self.entrada_ativa = None
        
        # 🆕 TENTA TREINAR/ATUALIZAR ML A CADA 30 GIROS
        if st.session_state.get('modo_ml', False) and len(self.historico_numeros) >= 50 and len(self.historico_numeros) % 30 == 0:
            self.ml_predictor.treinar(
                list(self.duzia_ai.historico_completo),
                list(self.duzia_ai.numeros_completos)
            )
        
        # GERA PREVISÃO
        confianca_minima = st.session_state.get('confianca_minima', 3.2)
        agressividade = st.session_state.get('agressividade', 2)
        
        # 🆕 MODO MACHINE LEARNING
        if st.session_state.get('modo_ml', False) and self.ml_predictor.ready:
            previsao_ml = self.ml_predictor.prever(
                list(self.duzia_ai.historico),
                list(self.duzia_ai.numeros_completos[-30:])
            )
            
            if previsao_ml and previsao_ml['entrar']:
                duzia_map = {1: list(range(1,13)), 2: list(range(13,25)), 3: list(range(25,37))}
                numeros = duzia_map.get(previsao_ml['duzia'], [])
                
                # Modo agressivo: adiciona segunda dúzia
                if st.session_state.get('modo_agressivo', False) and previsao_ml.get('duzia_secundaria'):
                    numeros = list(set(numeros + duzia_map.get(previsao_ml['duzia_secundaria'], [])))
                
                self.entrada_ativa = {
                    'numeros_apostar': numeros,
                    'duzia_prevista': previsao_ml['duzia'],
                    'duzia_sec_prevista': previsao_ml.get('duzia_secundaria'),
                    'confianca': previsao_ml['confianca'] * 10,
                    'regime': 'ML',
                    'score': {},
                    'detalhes': {previsao_ml['duzia']: [f"ML: {previsao_ml['confianca']:.1%}"]},
                    'modo': 'ml'
                }
                
                self.sinais_grafico.append((len(self.historico_numeros)-1, previsao_ml['duzia']))
                
                enviar_previsao_auto({
                    'numeros_apostar': numeros,
                    'forca_real': min(95, previsao_ml['confianca']*100),
                    'motor': f"🤖 ML D{previsao_ml['duzia']}",
                    'gatilho': f"ML Conf: {previsao_ml['confianca']:.1%}"
                })
                return
        
        # MODO REGRAS FIXAS (FALLBACK/PADRÃO)
        previsao = self.duzia_ai.prever(confianca_minima=confianca_minima, agressividade=agressividade)
        
        if previsao['entrar']:
            duzia_map = {1: list(range(1,13)), 2: list(range(13,25)), 3: list(range(25,37))}
            numeros = duzia_map.get(previsao['duzia'], [])
            
            if st.session_state.get('modo_agressivo', False) and previsao.get('duzia_secundaria'):
                numeros = list(set(numeros + duzia_map.get(previsao['duzia_secundaria'], [])))
            
            self.entrada_ativa = {
                'numeros_apostar': numeros,
                'duzia_prevista': previsao['duzia'],
                'duzia_sec_prevista': previsao.get('duzia_secundaria'),
                'confianca': previsao.get('confianca', 0),
                'regime': previsao.get('regime', 'NEUTRO'),
                'score': previsao.get('score', {}),
                'detalhes': previsao.get('detalhes', {}),
                'modo': 'regras'
            }
            
            self.sinais_grafico.append((len(self.historico_numeros)-1, previsao['duzia']))
            
            enviar_previsao_auto({
                'numeros_apostar': numeros,
                'forca_real': min(95, previsao.get('confianca', 0)*8),
                'motor': f"DuziaAI D{previsao['duzia']}",
                'gatilho': f"Regime: {previsao.get('regime','?')} | Conf: {previsao.get('confianca',0):.1f}"
            })
    
    def zerar(self):
        self.acertos = 0; self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear()
        self.entrada_ativa = None
        self.ultimo_numero = None
        self.sinais_grafico = []
        self.ml_entradas_count = 0
        self.ml_acertos = 0
        self.ml_accuracy_recente = []
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
        with open(caminho, "w") as f: json.dump(historico, f, indent=2)
    except: pass

def fetch_latest_result():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=5)
        r.raise_for_status()
        d = r.json()
        gd = d.get("data", {}); rs = gd.get("result", {})
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

def exportar_historico(historico, formato='json'):
    if formato == 'json': return json.dumps(historico, indent=2, ensure_ascii=False)
    linhas = ["numero,timestamp,multiplicador"]
    for item in historico:
        if isinstance(item, dict):
            n = item.get('number', '')
            linhas.append(f"{n},{item.get('timestamp','')},{item.get('luckyMultipliers',{}).get(n,'')}")
        else: linhas.append(f"{item},,")
    return "\n".join(linhas)

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎰 DuziaAI V5.0 - ML + Regras", layout="wide")
st.title("🎰 DuziaAI V5.0 - Machine Learning + Regras")

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
    st.session_state.confianca_ml = dados.get('confianca_ml', 0.15)
    if os.path.exists(ENTRADAS_PATH):
        try:
            with open(ENTRADAS_PATH, 'r') as f: sis.historico_entradas = json.load(f)
        except: pass

defaults = {
    'modo_automatico': True, 'modo_agressivo': False, 'modo_ml': False,
    'janela_duzia_ai': 30, 'confianca_minima': 3.2, 'agressividade': 2,
    'confianca_ml': 0.15, 'acertos_duzia': 0, 'erros_duzia': 0,
    'acertos_duzia_sec': 0, 'erros_duzia_sec': 0,
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

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.markdown("## ⚙️ Configurações")
    
    st.markdown("### 🧠 Modo de Inteligência")
    st.session_state.modo_ml = st.checkbox(
        "🤖 ATIVAR MACHINE LEARNING (XGBoost)",
        value=st.session_state.modo_ml,
        help="Quando ativado, usa IA treinada com histórico. Desativado = regras fixas."
    )
    
    if st.session_state.modo_ml:
        st.success("🤖 **MODO ML ATIVO** - O bot aprende com os dados!")
        st.session_state.confianca_ml = st.slider(
            "🎯 Confiança Mínima ML",
            0.05, 0.35, st.session_state.confianca_ml, 0.05,
            help="Menor = mais entradas | 0.15 recomendado"
        )
        
        # Status do modelo
        if sis.ml_predictor.ready:
            st.info(f"✅ Modelo treinado com {sis.ml_predictor.training_samples} amostras")
        else:
            st.warning(f"⏳ Modelo em aquecimento... ({len(sis.historico_numeros)}/50 giros)")
            st.caption("O ML precisa de 50+ giros para começar. Usando regras fixas enquanto isso.")
    else:
        st.info("📊 **MODO REGRAS FIXAS** - Detectores programados")
    
    st.markdown("---")
    
    st.session_state.janela_duzia_ai = st.slider("📏 Janela de Análise", 10, 50, st.session_state.janela_duzia_ai, 5)
    st.session_state.confianca_minima = st.slider("🎯 Confiança Mínima (Regras)", 2.0, 5.0, st.session_state.confianca_minima, 0.2)
    st.session_state.agressividade = st.select_slider("🎚️ Agressividade", options=[1,2,3], value=st.session_state.agressividade)
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
c1, c2, c3 = st.columns([3,1,1])
with c1:
    entrada = st.text_input("Número (0-36):", placeholder="Digite o número sorteado", key="entrada_numero")
with c2:
    if st.button("🎯 Enviar", use_container_width=True, type="primary"):
        if entrada and entrada.isdigit() and 0<=int(entrada)<=36:
            nr = int(entrada)
            item = {"number": nr, "timestamp": datetime.now().isoformat(), "luckyNumbers": [], "luckyMultipliers": {}}
            st.session_state.historico.append(item)
            sis.processar_novo_numero(item)
            salvar_resultado_em_arquivo(st.session_state.historico); salvar_sessao()
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
            salvar_resultado_em_arquivo(st.session_state.historico); salvar_sessao()
            st.rerun()

st.markdown("---")

# Métricas
c1,c2,c3,c4,c5,c6 = st.columns(6)
total_entradas = int(sis.acertos+sis.erros)
tx_acerto = (sis.acertos/total_entradas*100) if total_entradas>0 else 0
ac_dz = st.session_state.get('acertos_duzia',0)
er_dz = st.session_state.get('erros_duzia',0)
total_dz = ac_dz+er_dz
tx_dz = (ac_dz/total_dz*100) if total_dz>0 else 0

c1.metric("✅ Acertos", int(sis.acertos))
c2.metric("❌ Erros", int(sis.erros))
c3.metric("📊 Win Rate", f"{tx_acerto:.1f}%")
c4.metric("🎯 Tx Dúzia Primária", f"{tx_dz:.1f}%")
c5.metric("📦 Total Entradas", total_entradas)
c6.metric("🧠 Modo", "🤖 ML" if st.session_state.modo_ml else "📊 Regras")

# Métricas ML
if st.session_state.modo_ml and sis.ml_predictor.ready:
    st.metric("🤖 Amostras ML", sis.ml_predictor.training_samples)

st.markdown("---")
col_grafico, col_entrada = st.columns([3,2])

with col_grafico:
    st.subheader("📈 Análise em Tempo Real")
    if len(sis.historico_numeros)>=5:
        score, regime, detalhes = sis.duzia_ai.calcular_score()
        
        fig = go.Figure(data=[go.Bar(
            x=['D1','D2','D3'],
            y=[score[1],score[2],score[3]],
            marker_color=['#FF6B6B' if score[1]==max(score.values()) else '#4ECDC4',
                         '#FF6B6B' if score[2]==max(score.values()) else '#4ECDC4',
                         '#FF6B6B' if score[3]==max(score.values()) else '#4ECDC4'],
            text=[f'{score[1]:.1f}',f'{score[2]:.1f}',f'{score[3]:.1f}'],
            textposition='auto'
        )])
        fig.update_layout(title=f"🎯 Scores | Regime: {regime}", height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        st.caption("**🔍 Detectores:**")
        for dz in [1,2,3]:
            if detalhes.get(dz): st.caption(f"D{dz}: " + " | ".join(detalhes[dz]))
        
        if len(sis.historico_numeros)>=10:
            ultimos = list(sis.historico_numeros)[-20:]
            duzias = [get_duzia(n) for n in ultimos]
            x_vals = list(range(len(duzias)))
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=x_vals, y=duzias, mode='lines+markers', name='Dúzia', line=dict(color='#FFD700',width=2), marker=dict(size=8)))
            if sis.sinais_grafico:
                sx, sy, stxt = [], [], []
                offset = len(duzias)-20
                for idx, dz in sis.sinais_grafico:
                    pos = idx-offset
                    if 0<=pos<20: sx.append(pos); sy.append(dz); stxt.append(f"Entrada D{dz}")
                if sx: fig2.add_trace(go.Scatter(x=sx, y=sy, mode='markers', name='Sinal', marker=dict(symbol='star',size=15,color='red',line=dict(width=2,color='darkred')), text=stxt, hoverinfo='text'))
            fig2.update_layout(title="📉 Histórico de Dúzias c/ Sinais", yaxis=dict(tickvals=[1,2,3],ticktext=['D1','D2','D3'],range=[0.5,3.5]), height=300, showlegend=True)
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info(f"⏳ Aguardando dados... ({len(sis.historico_numeros)}/5 giros)")

with col_entrada:
    st.subheader("🎰 Entrada Atual")
    if sis.entrada_ativa:
        ent = sis.entrada_ativa
        confianca = ent.get('confianca',0)
        dz_prev = ent.get('duzia_prevista',0)
        dz_sec = ent.get('duzia_sec_prevista')
        regime = ent.get('regime','NEUTRO')
        nums = ent.get('numeros_apostar',[])
        detalhes_ent = ent.get('detalhes',{})
        modo_entrada = ent.get('modo','regras')
        
        cor = "#8A2BE2" if modo_entrada=='ml' else "#00CC00" if confianca>=5 else "#FFA500" if confianca>=3.5 else "#FF4444"
        emoji = "🤖" if modo_entrada=='ml' else "🎯"
        limite = "1-12" if dz_prev==1 else "13-24" if dz_prev==2 else "25-36"
        
        st.markdown(f"""
        <div style="background-color:{cor}22; border:2px solid {cor}; border-radius:15px; padding:20px; margin:10px 0;">
            <h2 style="color:{cor}; text-align:center;">{emoji} D{dz_prev} ({limite})</h2>
            <p style="text-align:center; font-size:1.2em;">Confiança: {confianca:.2f} | Regime: {regime} | Modo: {'🤖 ML' if modo_entrada=='ml' else '📊 Regras'}</p>
            {f'<p style="text-align:center; color:#FFA500;">🛡️ Cobertura: D{dz_sec}</p>' if st.session_state.modo_agressivo and dz_sec else ''}
        </div>""", unsafe_allow_html=True)
        
        if detalhes_ent.get(dz_prev): st.caption("🔍 " + " | ".join(detalhes_ent[dz_prev]))
        if nums:
            st.write("**🎲 Números:**")
            cols = st.columns(6)
            for i, n in enumerate(sorted(nums)): cols[i%6].button(str(n), key=f"num_{n}", use_container_width=True)
        else: st.warning("Nenhum número disponível.")
        st.progress(min(1.0, confianca/10.0))
    else:
        st.info("🔍 Analisando padrões...")
        if len(sis.historico_numeros)>=5:
            previsao = sis.duzia_ai.prever()
            if previsao and not previsao.get('entrar',False):
                st.warning(f"⚠️ {previsao.get('motivo','Sem sinal')}")
                st.caption(f"Regime: {previsao.get('regime','?')} | Conf: {previsao.get('confianca',0)}")
    if sis.ultimo_numero is not None:
        st.markdown("---")
        st.write(f"**🔄 Último Giro:** #{sis.ultimo_numero} → D{get_duzia(sis.ultimo_numero)}")

st.markdown("---")
st.subheader("📝 Histórico de Entradas")
if sis.historico_entradas:
    dados_tabela = []
    for e in reversed(sis.historico_entradas[-20:]):
        dados_tabela.append({
            "Rodada": e.get('rodada','-'),
            "Hora": e.get('hora','-'),
            "Número": e.get('resultado','-'),
            "Dúzia Real": f"D{e.get('duzia_real','?')}" if e.get('duzia_real') else "-",
            "Dúzia Prevista": f"D{e.get('duzia_prevista','?')}" if e.get('duzia_prevista') else "-",
            "Resultado": "✅" if e.get('acerto_primaria') else "🟡" if e.get('acerto_secundaria') else "❌",
            "Modo": "🤖" if e.get('modo')=='ml' else "📊"
        })
    st.dataframe(dados_tabela, use_container_width=True, height=300)
else:
    st.info("Nenhuma entrada registrada ainda.")

st.markdown("---")
st.caption(f"🤖 DuziaAI V5.0 | ML + Regras | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
salvar_sessao()
