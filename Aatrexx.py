import streamlit as st
import json
import os
import requests
import logging
from collections import Counter, deque, defaultdict
from streamlit_autorefresh import st_autorefresh
import pickle
from datetime import datetime
import numpy as np

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_roleta.json"
PERFORMANCE_PATH = "performance_bot.json"
PADROES_PATH = "padroes_sequencia.json"

def salvar_sessao():
    try:
        if 'sistema' not in st.session_state or st.session_state.sistema is None:
            return False
        
        performance_data = {
            'acertos': st.session_state.sistema.bot.performance['acertos'],
            'erros': st.session_state.sistema.bot.performance['erros'],
            'historico': st.session_state.sistema.bot.performance['historico']
        }
        with open(PERFORMANCE_PATH, 'w') as f:
            json.dump(performance_data, f)
        
        if hasattr(st.session_state.sistema.bot, 'padroes_sequencia'):
            with open(PADROES_PATH, 'w') as f:
                json.dump(st.session_state.sistema.bot.padroes_sequencia, f)
        
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
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'top_n_apostas': st.session_state.get('top_n_apostas', 5),
            'intervalo_minimo_entradas': st.session_state.get('intervalo_minimo_entradas', 0),
            'usar_sniper': st.session_state.get('usar_sniper', True),
            'usar_mineracao': st.session_state.get('usar_mineracao', True),
            'usar_leque': st.session_state.get('usar_leque', True),
            'usar_giro': st.session_state.get('usar_giro', True),
            'usar_gap': st.session_state.get('usar_gap', True),
            'usar_sequencia': st.session_state.get('usar_sequencia', True),
            'usar_quadrantes': st.session_state.get('usar_quadrantes', True),
            'usar_terminais': st.session_state.get('usar_terminais', True),
            'usar_simetria': st.session_state.get('usar_simetria', True),
            'usar_ia_adaptativa': st.session_state.get('usar_ia_adaptativa', True),
            'janela_analise': st.session_state.get('janela_analise', 50),
            'janela_leque': st.session_state.get('janela_leque', 20),
            'forca_minima_sinal': st.session_state.get('forca_minima_sinal', 40),
            'max_repeticoes_acerto': st.session_state.get('max_repeticoes_acerto', 3),
            'giros_espera_repeticao': st.session_state.sistema.giros_espera_repeticao,
            'giros_restantes_espera': st.session_state.sistema.giros_restantes_espera,
            'repeticoes_acerto_consecutivas': st.session_state.sistema.repeticoes_acerto_consecutivas,
            'ultima_entrada_numeros': st.session_state.sistema.ultima_entrada_numeros,
            'ultima_entrada_forca': st.session_state.sistema.ultima_entrada_forca,
            'ultima_entrada_motor': st.session_state.sistema.ultima_entrada_motor,
            'ultima_entrada_green': st.session_state.sistema.ultima_entrada_green,
            'modo_ia': st.session_state.sistema.modo_ia,
            'entropia_atual': st.session_state.sistema.entropia_atual,
            'bloqueado_ate_rodada': st.session_state.sistema.bloqueado_ate_rodada
        }
        
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f)
        
        return True
    except Exception as e:
        logging.error(f"❌ Erro ao salvar: {e}")
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
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH, PADROES_PATH]:
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
        forca = previsao.get('forca_real', 0)
        estrategias = previsao.get('estrategias_ativas', [])
        confianca = previsao.get('confianca', 'Média')
        motor = previsao.get('motor', '')
        repeticao = previsao.get('repeticao', False)
        green = previsao.get('green', False)
        giros_esperados = previsao.get('giros_esperados', 0)
        green_count = previsao.get('green_count', 0)
        modo_ia = previsao.get('modo_ia', '')
        
        if green:
            emoji = "🟢"
            tipo = f"GREEN #{green_count}"
        elif repeticao:
            emoji = "⏳"
            tipo = "REPETINDO"
        elif forca >= 60:
            emoji = "🔥"
            tipo = motor
        elif forca >= 40:
            emoji = "🎯"
            tipo = motor
        else:
            emoji = "📊"
            tipo = motor
        
        msg = f"{emoji} **ENTRADA** - Força: {forca}%\n"
        
        if green:
            msg += f"🟢 REPETINDO APÓS ACERTO! (Green #{green_count}/3)\n"
        elif repeticao:
            msg += f"⏳ REPETINDO ENTRADA ANTERIOR! (após espera de {giros_esperados} giros)\n"
        else:
            msg += f"📋 {previsao['gatilho']}\n"
            if motor:
                msg += f"🤖 Motor: {motor}\n"
            if modo_ia:
                msg += f"🧠 Modo IA: {modo_ia}\n"
            if estrategias:
                msg += f"🎯 {', '.join(estrategias[:3])}\n"
        
        msg += f"🔢 {len(numeros)} números: {numeros}"
        
        st.toast(f"{'🟢 Green' if green else '⏳ Repetindo' if repeticao else '🎯 ' + motor} - {forca}%", icon=emoji)
        st.success(f"🔔 {msg}")
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            tag = "[GREEN]" if green else "[REPETINDO]" if repeticao else ""
            enviar_telegram(f"🔔 ENTRADA {tag} {forca}%\n" + " ".join(map(str, numeros)))
        
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
# ROLETA BASE
# =============================
class RoletaBase:
    def __init__(self):
        self.race = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        self.vermelhos = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        self.pretos = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
    
    def get_vizinhos(self, numero, raio=2):
        if numero not in self.race:
            return []
        idx = self.race.index(numero)
        return [self.race[(idx + i) % 37] for i in range(-raio, raio + 1)]
    
    def get_setor(self, numero):
        if numero == 0:
            return 0
        return (numero - 1) // 12 + 1
    
    def get_coluna(self, numero):
        if numero == 0:
            return 0
        return (numero - 1) % 3 + 1


# =============================
# 🧠 IA ADAPTATIVA V3
# =============================
class EstrategiaIAAdaptativa:
    def __init__(self, window=50):
        self.window = window
        self.buffer = deque(maxlen=window)
        self.transicoes = {}
        self.historico_completo = []
    
    def atualizar(self, numero):
        if self.historico_completo:
            ultimo = self.historico_completo[-1]
            if ultimo not in self.transicoes:
                self.transicoes[ultimo] = []
            self.transicoes[ultimo].append(numero)
        
        self.historico_completo.append(numero)
        self.buffer.append(numero)
    
    def freq_score(self):
        if len(self.buffer) == 0:
            return {n: 0 for n in range(37)}
        contagem = Counter(self.buffer)
        total = len(self.buffer)
        return {n: contagem.get(n, 0) / total for n in range(37)}
    
    def atraso_score(self):
        if len(self.historico_completo) == 0:
            return {n: 0 for n in range(37)}
        
        atraso = {}
        total = len(self.historico_completo)
        
        for n in range(37):
            aparicoes = [i for i, x in enumerate(self.historico_completo) if x == n]
            if not aparicoes:
                atraso[n] = 1.0
            else:
                gap = total - aparicoes[-1] - 1
                atraso[n] = min(1.0, gap / total)
        
        return atraso
    
    def transicao_score(self):
        if len(self.historico_completo) < 2:
            return {n: 0 for n in range(37)}
        
        ultimo = self.historico_completo[-1]
        
        if ultimo not in self.transicoes or len(self.transicoes[ultimo]) == 0:
            return {n: 0 for n in range(37)}
        
        contagem = Counter(self.transicoes[ultimo])
        total = sum(contagem.values())
        
        return {n: contagem.get(n, 0) / total for n in range(37)}
    
    def calcular_entropia(self):
        freq = self.freq_score()
        probs = np.array(list(freq.values()))
        probs = probs[probs > 0]
        
        if len(probs) == 0:
            return 5.0
        
        entropia = -np.sum(probs * np.log(probs))
        entropia_max = np.log(37)
        entropia_norm = (entropia / entropia_max) * 5
        
        return entropia_norm
    
    def analisar(self, historico):
        if len(historico) < 10:
            return None
        
        self.historico_completo = list(historico)
        self.buffer = deque(list(historico)[-self.window:], maxlen=self.window)
        
        self.transicoes = {}
        for i in range(len(self.historico_completo) - 1):
            atual = self.historico_completo[i]
            proximo = self.historico_completo[i + 1]
            if atual not in self.transicoes:
                self.transicoes[atual] = []
            self.transicoes[atual].append(proximo)
        
        freq = self.freq_score()
        atraso = self.atraso_score()
        trans = self.transicao_score()
        
        score = {}
        for n in range(37):
            score[n] = (
                0.4 * freq.get(n, 0) +
                0.4 * atraso.get(n, 0) +
                0.2 * trans.get(n, 0)
            )
        
        ranking = sorted(score.items(), key=lambda x: x[1], reverse=True)
        entropia = self.calcular_entropia()
        
        if entropia < 3.0:
            modo = "AGRESSIVO"
            top_n = 5
            forca = 65
        elif entropia < 3.3:
            modo = "MODERADO"
            top_n = 8
            forca = 50
        else:
            modo = "CONSERVADOR"
            top_n = 10
            forca = 35
        
        base = [n for n, _ in ranking[:top_n]]
        clusters = self._detectar_clusters(base)
        
        estrategias = [f"IA Adaptativa ({modo})"]
        if clusters:
            estrategias.append(f"Cluster: {clusters}")
        estrategias.append(f"Entropia: {entropia:.2f}")
        
        score_medio = np.mean([s for _, s in ranking[:top_n]])
        if score_medio > 0.05:
            forca += 10
        elif score_medio < 0.02:
            forca -= 10
        
        forca = min(100, max(20, forca))
        
        return {
            'base': set(base),
            'forca': forca,
            'estrategias': estrategias,
            'entropia': entropia,
            'modo': modo,
            'ranking': ranking[:15]
        }
    
    def _detectar_clusters(self, numeros):
        if len(numeros) < 2:
            return None
        
        duzias = Counter()
        for n in numeros:
            if n == 0:
                continue
            d = (n - 1) // 12 + 1
            duzias[d] += 1
        
        if duzias:
            dom = duzias.most_common(1)[0]
            if dom[1] >= len(numeros) * 0.5:
                return f"Dúzia {dom[0]} dominante"
        
        colunas = Counter()
        for n in numeros:
            if n == 0:
                continue
            c = (n - 1) % 3 + 1
            colunas[c] += 1
        
        if colunas:
            dom = colunas.most_common(1)[0]
            if dom[1] >= len(numeros) * 0.5:
                return f"Coluna {dom[0]} dominante"
        
        return None
    
    def get_entropia(self):
        return self.calcular_entropia()


# =============================
# ESTRATÉGIA 1: SNIPER
# =============================
class EstrategiaSniper:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, historico, lucky_recentes):
        if len(historico) < 15:
            return None
        
        recentes = historico[-15:]
        ultimo = recentes[-1]
        
        duzias = Counter([self.roleta.get_setor(n) for n in recentes if n != 0])
        colunas = Counter([self.roleta.get_coluna(n) for n in recentes if n != 0])
        
        melhor_duzia = duzias.most_common(1)[0][0] if duzias else None
        melhor_coluna = colunas.most_common(1)[0][0] if colunas else None
        
        roda_hits = []
        for n in recentes:
            roda_hits.extend(self.roleta.get_vizinhos(n, raio=1))
        zona_quente = Counter(roda_hits).most_common(1)[0][0] if roda_hits else None
        vizinhos_zona = self.roleta.get_vizinhos(zona_quente, raio=2) if zona_quente else []
        
        forca = 0
        estrategia = []
        base = set()
        gatilho = ""
        
        if melhor_duzia and melhor_coluna:
            if duzias[melhor_duzia] >= 7 and colunas[melhor_coluna] >= 6:
                forca += 60
                estrategia.append("Interseção D/C")
                d, c = melhor_duzia, melhor_coluna
                numeros_duzia = range((d-1)*12 + 1, d*12 + 1)
                numeros_coluna = range(c, 37, 3)
                base.update(set(numeros_duzia).intersection(set(numeros_coluna)))
                gatilho = f"Interseção D{d} x C{c}"
        
        if zona_quente and vizinhos_zona:
            hits_zona = sum(1 for n in recentes if n in vizinhos_zona)
            if hits_zona >= 5:
                forca += 50
                estrategia.append("Cluster Físico")
                base.update(vizinhos_zona)
                if not gatilho:
                    gatilho = f"Zona: {zona_quente}"
        
        if lucky_recentes:
            lucky_quentes = [n for n, _ in Counter(lucky_recentes).most_common(3)]
            if any(l in recentes for l in lucky_quentes):
                forca += 15
                estrategia.append("Raios")
        
        if forca == 0:
            return None
        
        return {
            'base': base,
            'forca': min(100, forca),
            'estrategias': estrategia,
            'gatilho': gatilho
        }


# =============================
# ESTRATÉGIA 2: MINERAÇÃO
# =============================
class EstrategiaMineracao:
    def __init__(self):
        self.transicoes = defaultdict(list)
    
    def atualizar(self, historico):
        self.transicoes.clear()
        for i in range(len(historico) - 1):
            self.transicoes[historico[i]].append(historico[i + 1])
    
    def analisar(self, historico, historico_lucky):
        if len(historico) < 10:
            return None
        
        self.atualizar(historico)
        ultimo = historico[-1]
        
        base = set()
        forca = 0
        estrategias = []
        
        seguidores = self.transicoes.get(ultimo, [])
        if seguidores:
            top = [n for n, _ in Counter(seguidores).most_common(3)]
            base.update(top)
            forca += 30
            estrategias.append("Markov")
        
        if len(historico_lucky) >= 2:
            acertos = sum(1 for i in range(min(len(historico)-1, len(historico_lucky)-1))
                         if historico[i+1] in historico_lucky[i])
            total = min(len(historico)-1, len(historico_lucky)-1)
            taxa = acertos / total * 100 if total > 0 else 0
            if taxa > 18:
                forca += 35
                estrategias.append(f"Lucky Cross {taxa:.0f}%")
        
        if forca == 0:
            return None
        
        return {
            'base': base,
            'forca': min(100, forca),
            'estrategias': estrategias
        }


# =============================
# ESTRATÉGIA 3: LEQUE DINÂMICO
# =============================
class EstrategiaLeque:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, historico, janela=20):
        if len(historico) < 10:
            return None
        
        recentes = historico[-janela:]
        ultimo = recentes[-1]
        
        macro_regiao = self.roleta.get_vizinhos(ultimo, 5)
        acertos = sum(1 for n in recentes if n in macro_regiao)
        
        if acertos >= 6:
            leque = 4
            status = "🔥 MUITO QUENTE"
            forca = 70
        elif acertos >= 3:
            leque = 2
            status = "🟡 MORNO"
            forca = 50
        else:
            leque = 1
            status = "🧊 FRIO"
            forca = 30
        
        alvos = self.roleta.get_vizinhos(ultimo, leque)
        
        return {
            'base': set(alvos),
            'forca': forca,
            'estrategias': [f"Leque {leque} vizinhos"],
            'status': status,
            'leque': leque,
            'acertos_regiao': acertos
        }


# =============================
# ESTRATÉGIA 4: ANÁLISE POR GIRO
# =============================
class EstrategiaPorGiro:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, historico, lucky_recentes):
        if len(historico) < 5:
            return None
        
        hist = historico
        ultimo = hist[-1]
        ultimos_5 = hist[-5:] if len(hist) >= 5 else hist
        ultimos_10 = hist[-10:] if len(hist) >= 10 else hist
        
        freq_5 = Counter(ultimos_5)
        freq_10 = Counter(ultimos_10)
        
        repetiu = (hist[-1] == hist[-2]) if len(hist) >= 2 else False
        repeticoes_5 = [n for n in ultimos_5 if ultimos_5.count(n) >= 2]
        
        quentes_5 = [n for n, _ in freq_5.most_common(3)]
        quentes_10 = [n for n, _ in freq_10.most_common(5)]
        
        lucky_count = Counter(lucky_recentes) if lucky_recentes else Counter()
        top_lucky = [n for n, _ in lucky_count.most_common(5)]
        
        vizinhos = self.roleta.get_vizinhos(ultimo, 2)
        
        setores = Counter([self.roleta.get_setor(n) for n in ultimos_10 if n != 0])
        setor_dom = setores.most_common(1)[0][0] if setores else None
        
        vermelhos = sum(1 for n in ultimos_10 if n in self.roleta.vermelhos)
        pretos = sum(1 for n in ultimos_10 if n in self.roleta.pretos)
        cor_dom = 'Vermelho' if vermelhos > pretos else 'Preto'
        
        base = set()
        estrategias = []
        forca = 20
        
        if repetiu:
            base.add(ultimo)
            forca += 35
            estrategias.append(f"Repetiu {ultimo}")
        
        for n in repeticoes_5[:2]:
            base.add(n)
            forca += 10
        
        for n in top_lucky[:3]:
            base.add(n)
        if top_lucky:
            forca += 15
            estrategias.append("Lucky")
        
        for n in quentes_5[:2]:
            base.add(n)
        for n in quentes_10[:3]:
            base.add(n)
        estrategias.append("Quentes")
        
        for n in vizinhos[:3]:
            base.add(n)
        estrategias.append("Vizinhos")
        
        base.add(ultimo)
        
        if setor_dom:
            inicio = (setor_dom - 1) * 12 + 1
            fim = setor_dom * 12
            numeros_setor = set(range(inicio, fim + 1))
            base_setor = base.intersection(numeros_setor)
            if len(base_setor) >= 3:
                base = base_setor
                forca += 15
                estrategias.append(f"Setor {setor_dom}")
        
        if cor_dom == 'Vermelho':
            base_cor = {n for n in base if n in self.roleta.vermelhos or n == 0}
        else:
            base_cor = {n for n in base if n in self.roleta.pretos or n == 0}
        if len(base_cor) >= 3:
            base = base_cor
            forca += 10
            estrategias.append(cor_dom)
        
        prioridade = []
        for n in repeticoes_5:
            if n in base and n not in prioridade:
                prioridade.append(n)
        for n in top_lucky:
            if n in base and n not in prioridade:
                prioridade.append(n)
        for n in quentes_5:
            if n in base and n not in prioridade:
                prioridade.append(n)
        for n in vizinhos:
            if n in base and n not in prioridade:
                prioridade.append(n)
        for n in base:
            if n not in prioridade:
                prioridade.append(n)
        
        base_list = prioridade[:6]
        
        if len(base_list) < 3:
            for n in quentes_10:
                if n not in base_list:
                    base_list.append(n)
                    if len(base_list) >= 3:
                        break
        
        forca = min(100, max(15, forca))
        
        return {
            'base': set(base_list),
            'forca': forca,
            'estrategias': estrategias,
            'repetiu': repetiu
        }


# =============================
# ESTRATÉGIA 5: REPETIÇÃO COM GAP
# =============================
class EstrategiaGap:
    def __init__(self):
        pass
    
    def analisar(self, historico):
        if len(historico) < 5:
            return None
        
        ultimo = historico[-1]
        
        if len(historico) >= 3:
            if historico[-3] == ultimo:
                return {
                    'base': {ultimo, historico[-2]},
                    'forca': 55,
                    'estrategias': [f'Repetição Gap1: {historico[-3]}→{historico[-2]}→{ultimo}'],
                    'gap': 1
                }
        
        if len(historico) >= 4:
            if historico[-4] == ultimo:
                return {
                    'base': {ultimo, historico[-2], historico[-3]},
                    'forca': 45,
                    'estrategias': [f'Repetição Gap2: {historico[-4]}→...→{ultimo}'],
                    'gap': 2
                }
        
        if len(historico) >= 5:
            if historico[-5] == ultimo:
                return {
                    'base': {ultimo, historico[-2], historico[-3], historico[-4]},
                    'forca': 35,
                    'estrategias': [f'Repetição Gap3: {historico[-5]}→...→{ultimo}'],
                    'gap': 3
                }
        
        recentes = historico[-20:]
        gaps_encontrados = []
        for i in range(len(recentes) - 2):
            for gap in [1, 2, 3]:
                if i + gap + 1 < len(recentes) and recentes[i] == recentes[i + gap + 1]:
                    gaps_encontrados.append(recentes[i])
        
        if gaps_encontrados:
            top_gap = [n for n, c in Counter(gaps_encontrados).most_common(3)]
            return {
                'base': set(top_gap),
                'forca': 40,
                'estrategias': ['Gap Quente: ' + ', '.join(map(str, top_gap))],
                'gap': 0
            }
        
        return None


# =============================
# ESTRATÉGIA 6: SEQUÊNCIA PADRÃO
# =============================
class EstrategiaSequencia:
    def __init__(self):
        self.padroes = defaultdict(list)
        self.atualizado = False
    
    def treinar(self, historico):
        self.padroes.clear()
        for i in range(len(historico) - 1):
            atual = historico[i]
            proximo = historico[i + 1]
            self.padroes[atual].append(proximo)
        self.atualizado = True
    
    def prever(self, numero, top_n=10):
        if numero not in self.padroes or not self.padroes[numero]:
            return []
        contagem = Counter(self.padroes[numero])
        return [n for n, _ in contagem.most_common(top_n)]
    
    def analisar(self, historico):
        if len(historico) < 10:
            return None
        
        self.treinar(historico)
        
        ultimo = historico[-1]
        previsao = self.prever(ultimo, 10)
        
        if len(previsao) < 3:
            return None
        
        total_ocorrencias = len(self.padroes.get(ultimo, []))
        if total_ocorrencias >= 10:
            forca = 60
        elif total_ocorrencias >= 5:
            forca = 45
        else:
            forca = 30
        
        return {
            'base': set(previsao[:5]),
            'forca': forca,
            'estrategias': [f'Sequência após {ultimo} ({total_ocorrencias} ocorrências)'],
            'top10': previsao
        }


# =============================
# ESTRATÉGIA 7: CICLOS DE QUADRANTES
# =============================
class EstrategiaCiclosQuadrantes:
    def __init__(self):
        self.quadrantes = {
            1: set([1, 2, 3, 4, 5, 6, 7, 8, 9]),
            2: set([10, 11, 12, 13, 14, 15, 16, 17, 18]),
            3: set([19, 20, 21, 22, 23, 24, 25, 26, 27]),
            4: set([28, 29, 30, 31, 32, 33, 34, 35, 36])
        }

    def analisar(self, historico, janela=8):
        if len(historico) < janela:
            return None
        
        recentes = list(historico)[-janela:]
        vistos = set()
        
        for n in recentes:
            for q_id, nums in self.quadrantes.items():
                if n in nums:
                    vistos.add(q_id)
                    break
        
        ausentes = set(self.quadrantes.keys()) - vistos
        
        if len(ausentes) >= 1:
            q_alvo = list(ausentes)[0]
            return {
                'base': self.quadrantes[q_alvo],
                'forca': 55 + (janela * 2),
                'estrategias': [f"Atraso no Quadrante {q_alvo} ({janela} giros)"]
            }
        return None


# =============================
# ESTRATÉGIA 8: TERMINAIS (FINAIS)
# =============================
class EstrategiaTerminais:
    def __init__(self):
        self.terminais = {i: [n for n in range(37) if n % 10 == i] for i in range(10)}

    def analisar(self, historico, janela=15):
        if len(historico) < janela:
            return None
        
        recentes = historico[-janela:]
        finais_contagem = Counter([n % 10 for n in recentes])
        
        final_quente, freq = finais_contagem.most_common(1)[0]
        
        if freq >= 3:
            return {
                'base': set(self.terminais[final_quente]),
                'forca': 40 + (freq * 5),
                'estrategias': [f"Terminal {final_quente} Quente ({freq}x)"]
            }
        return None


# =============================
# ESTRATÉGIA 9: SIMETRIA (ESPELHAMENTO)
# =============================
class EstrategiaSimetria:
    def __init__(self):
        self.espelhos = {
            12: 21, 21: 12, 13: 31, 31: 13, 23: 32, 32: 23,
            1: 10, 10: 1, 2: 20, 20: 2, 3: 30, 30: 3
        }

    def analisar(self, historico):
        ultimo = historico[-1]
        base = set()
        
        if ultimo in self.espelhos:
            base.add(self.espelhos[ultimo])
            return {
                'base': base,
                'forca': 45,
                'estrategias': [f"Simetria de {ultimo} -> {self.espelhos[ultimo]}"]
            }
        return None


# =============================
# BOT UNIFICADO
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        self.sniper = EstrategiaSniper(self.roleta)
        self.mineracao = EstrategiaMineracao()
        self.leque = EstrategiaLeque(self.roleta)
        self.giro = EstrategiaPorGiro(self.roleta)
        self.gap = EstrategiaGap()
        self.sequencia = EstrategiaSequencia()
        
        self.quadrantes_strat = EstrategiaCiclosQuadrantes()
        self.terminais_strat = EstrategiaTerminais()
        self.simetria_strat = EstrategiaSimetria()
        
        self.ia_adaptativa = EstrategiaIAAdaptativa(window=50)
        
        self.historico = []
        self.lucky = []
        self.lucky_mult = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.padroes_sequencia = {}
        
    def atualizar(self, numero, lucky_nums=None, lucky_mults=None):
        if isinstance(numero, dict):
            numero = numero.get('number', 0)
        elif not isinstance(numero, int):
            numero = int(numero)
        
        self.historico.append(numero)
        self.lucky.append(lucky_nums if lucky_nums else [])
        self.lucky_mult.append(lucky_mults if lucky_mults else {})
        
        if len(self.historico) > 200:
            self.historico = self.historico[-200:]
            self.lucky = self.lucky[-200:]
            self.lucky_mult = self.lucky_mult[-200:]
        
        if len(self.historico) >= 2:
            self.sequencia.treinar(self.historico)
        
        self.ia_adaptativa.atualizar(numero)
    
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
    
    def get_entropia(self):
        return self.ia_adaptativa.get_entropia()
    
    def analisar_e_prever(self, top_n=5, motores_ativos=None):
        if len(self.historico) < 5:
            return None
        
        if motores_ativos is None:
            motores_ativos = {
                'sniper': True, 'mineracao': True, 'leque': True, 
                'giro': True, 'gap': True, 'sequencia': True,
                'quadrantes': True, 'terminais': True, 'simetria': True,
                'ia_adaptativa': True
            }
        
        lucky_recentes = []
        for sub in self.lucky[-10:]:
            lucky_recentes.extend(sub)
        
        resultados = []
        
        if motores_ativos.get('ia_adaptativa', True) and len(self.historico) >= 10:
            r = self.ia_adaptativa.analisar(list(self.historico))
            if r:
                resultados.append(('IA Adaptativa', r))
        
        if motores_ativos.get('sniper', True) and len(self.historico) >= 15:
            r = self.sniper.analisar(list(self.historico), lucky_recentes)
            if r:
                resultados.append(('Sniper', r))
        
        if motores_ativos.get('mineracao', True) and len(self.historico) >= 10:
            r = self.mineracao.analisar(list(self.historico), list(self.lucky))
            if r:
                resultados.append(('Mineração', r))
        
        if motores_ativos.get('leque', True):
            janela = st.session_state.get('janela_leque', 20)
            r = self.leque.analisar(list(self.historico), janela)
            if r:
                resultados.append(('Leque', r))
        
        if motores_ativos.get('giro', True):
            r = self.giro.analisar(list(self.historico), lucky_recentes)
            if r:
                resultados.append(('Análise Giro', r))
        
        if motores_ativos.get('gap', True):
            r = self.gap.analisar(list(self.historico))
            if r:
                resultados.append(('Gap', r))
        
        if motores_ativos.get('sequencia', True):
            r = self.sequencia.analisar(list(self.historico))
            if r:
                resultados.append(('Sequência', r))
        
        if motores_ativos.get('quadrantes', True):
            r = self.quadrantes_strat.analisar(self.historico)
            if r:
                resultados.append(('CicloQuadrantes', r))
        
        if motores_ativos.get('terminais', True):
            r = self.terminais_strat.analisar(list(self.historico))
            if r:
                resultados.append(('Terminais', r))
        
        if motores_ativos.get('simetria', True):
            r = self.simetria_strat.analisar(list(self.historico))
            if r:
                resultados.append(('Simetria', r))
        
        if not resultados:
            return None
        
        base_final = set()
        todas_estrategias = []
        forca_total = 0
        motor_principal = ""
        maior_forca = 0
        modo_ia = ""
        
        for motor, r in resultados:
            peso = 2 if motor == 'IA Adaptativa' else 1
            for _ in range(peso):
                base_final.update(r['base'])
            
            todas_estrategias.extend(r['estrategias'])
            forca_total += r['forca'] * peso
            
            if r['forca'] > maior_forca:
                maior_forca = r['forca']
                motor_principal = motor
            
            if motor == 'IA Adaptativa' and 'modo' in r:
                modo_ia = r['modo']
        
        pesos_total = sum(2 if m == 'IA Adaptativa' else 1 for m, _ in resultados)
        forca_media = forca_total / pesos_total if pesos_total > 0 else 20
        
        if len(self.performance['historico']) >= 5:
            taxa_recente = sum(self.performance['historico'][-5:]) / 5
            if taxa_recente >= 0.4:
                forca_media += 10
            elif taxa_recente <= 0.15:
                forca_media -= 10
        
        forca_media = min(100, max(15, int(forca_media)))
        
        if forca_media >= 55:
            confianca = "Alta"
        elif forca_media >= 35:
            confianca = "Média"
        else:
            confianca = "Baixa"
        
        freq_base = Counter()
        for motor, r in resultados:
            peso = 2 if motor == 'IA Adaptativa' else 1
            for n in r['base']:
                freq_base[n] += peso
        
        prioridade = [n for n, _ in freq_base.most_common()]
        base_list = prioridade[:top_n]
        
        ultimo_numero = self.historico[-1] if self.historico else 0
        gatilho = f"u={ultimo_numero}"
        
        if len(self.historico) >= 2 and self.historico[-1] == self.historico[-2]:
            gatilho = f"REPETIU {self.historico[-1]}!"
        elif len(self.historico) >= 3 and self.historico[-1] == self.historico[-3]:
            gatilho = f"REPETIU COM GAP! {self.historico[-3]}→{self.historico[-2]}→{self.historico[-1]}"
        
        if modo_ia:
            gatilho += f" [{modo_ia}]"
        
        return {
            'nome': 'Bot Unificado',
            'numeros_apostar': sorted(base_list),
            'gatilho': gatilho,
            'forca_real': forca_media,
            'confianca': confianca,
            'motor': motor_principal,
            'estrategias_ativas': list(set(todas_estrategias))[:5],
            'qtd_motores': len(resultados),
            'repeticao': False,
            'green': False,
            'green_count': 0,
            'giros_esperados': 0,
            'modo_ia': modo_ia
        }
    
    def get_analise_completa(self):
        if len(self.historico) < 5:
            return "📊 Aguardando dados (mínimo 5)..."
        
        hist = self.historico
        ultimo = hist[-1]
        ultimos_10 = hist[-10:] if len(hist) >= 10 else hist
        
        freq_10 = Counter(ultimos_10)
        quentes = [n for n, _ in freq_10.most_common(5)]
        
        lucky_flat = []
        for sub in self.lucky[-5:]:
            lucky_flat.extend(sub)
        top_lucky = [n for n, _ in Counter(lucky_flat).most_common(5)]
        
        taxa = self.get_taxa_acerto()
        total = self.get_total_tentativas()
        entropia = self.get_entropia()
        
        txt = "🎯 BOT UNIFICADO + IA ADAPTATIVA V3\n" + "="*45 + "\n\n"
        txt += f"🎲 Último: {ultimo}\n"
        txt += f"📊 10 últimos: {ultimos_10}\n\n"
        txt += f"🔥 Quentes: {quentes}\n"
        txt += f"🍀 Lucky: {top_lucky}\n"
        txt += f"\n🧠 IA: Entropia {entropia:.2f}/5.0\n"
        
        if total > 0:
            txt += f"\n📈 Perf: {taxa:.0%} ({self.performance['acertos']}/{total})\n"
        
        return txt
    
    def zerar(self):
        self.historico = []
        self.lucky = []
        self.lucky_mult = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.padroes_sequencia = {}
        self.ia_adaptativa = EstrategiaIAAdaptativa(window=50)


# =============================
# SISTEMA PRINCIPAL (TOTALMENTE AUTOMÁTICO)
# =============================
class SistemaBot:
    def __init__(self):
        self.bot = RoletaBotUnificado()
        self.historico_numeros = deque(maxlen=200)
        self.historico_lucky = deque(maxlen=100)
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.rodadas_sem_entrada = 0
        self.ultima_entrada_rodada = -10
        self.estrategia_ativa_manual = False
        
        # Sistema automático de repetição
        self.giros_espera_repeticao = 0
        self.giros_restantes_espera = 0
        self.repeticoes_acerto_consecutivas = 0
        self.ultima_entrada_green = False
        self.ultima_entrada_numeros = []
        self.ultima_entrada_forca = 0
        self.ultima_entrada_motor = ""
        self.bloqueado_ate_rodada = 0  # Nova: bloqueia novas análises até certa rodada
        
        # IA
        self.modo_ia = "MODERADO"
        self.entropia_atual = 3.5
        
    def processar_novo_numero(self, numero_data):
        """Processa um novo número do sorteio - totalmente automático"""
        # Extrai número real
        if isinstance(numero_data, dict):
            numero_real = numero_data['number']
            lucky = numero_data.get('luckyNumbers', [])
            lucky_mults = numero_data.get('luckyMultipliers', {})
            mult = lucky_mults.get(numero_real) if numero_real in lucky else None
        else:
            numero_real = int(numero_data)
            lucky = []
            lucky_mults = {}
            mult = None
        
        # Atualiza bot
        self.bot.atualizar(numero_real, lucky, lucky_mults)
        self.historico_numeros.append(numero_real)
        self.historico_lucky.append(lucky)
        self.rodadas_sem_entrada += 1
        
        # Atualiza IA
        self.entropia_atual = self.bot.get_entropia()
        if self.entropia_atual < 3.0:
            self.modo_ia = "AGRESSIVO"
        elif self.entropia_atual < 3.3:
            self.modo_ia = "MODERADO"
        else:
            self.modo_ia = "CONSERVADOR"
        
        # Decrementa espera
        if self.giros_restantes_espera > 0:
            self.giros_restantes_espera -= 1
        
        rodada_atual = len(self.historico_numeros)
        
        # Verifica resultado da previsão anterior
        if self.previsao_ativa:
            acerto = numero_real in self.previsao_ativa.get('numeros_apostar', [])
            self.bot.atualizar_resultado(acerto)
            
            if acerto:
                self.acertos += 1
                self.erros = 0  # Reseta contagem de erros consecutivos
                
                # 🟢 AUTOMÁTICO: Green Repeat
                if self.repeticoes_acerto_consecutivas < 3:
                    self.repeticoes_acerto_consecutivas += 1
                    self.ultima_entrada_green = True
                    self.ultima_entrada_numeros = self.previsao_ativa.get('numeros_apostar', [])
                    self.ultima_entrada_forca = self.previsao_ativa.get('forca_real', 0)
                    self.ultima_entrada_motor = self.previsao_ativa.get('motor', '')
                    self.bloqueado_ate_rodada = rodada_atual
                else:
                    # Máximo de greens atingido, reseta
                    self.repeticoes_acerto_consecutivas = 0
                    self.ultima_entrada_green = False
                    self.ultima_entrada_numeros = []
                    self.bloqueado_ate_rodada = 0
                
                self.giros_restantes_espera = 0
                self.giros_espera_repeticao = 0
                
                enviar_resultado_auto(numero_real, True, mult)
                
            else:
                self.erros += 1
                
                # ❌ AUTOMÁTICO: Erro - ativa repetição após 2 giros
                if not self.previsao_ativa.get('green', False):
                    # Só ativa se não era green
                    self.giros_restantes_espera = 2
                    self.giros_espera_repeticao = 2
                    self.ultima_entrada_numeros = self.previsao_ativa.get('numeros_apostar', [])
                    self.ultima_entrada_forca = self.previsao_ativa.get('forca_real', 0)
                    self.ultima_entrada_motor = self.previsao_ativa.get('motor', '')
                    self.bloqueado_ate_rodada = rodada_atual + 2
                else:
                    # Era green e errou, reseta tudo
                    self.ultima_entrada_numeros = []
                    self.bloqueado_ate_rodada = 0
                
                self.repeticoes_acerto_consecutivas = 0
                self.ultima_entrada_green = False
                
                enviar_resultado_auto(numero_real, False, mult)
            
            self.historico_desempenho.append({
                'numero': numero_real,
                'acerto': acerto,
                'multiplicador': mult,
                'forca': self.previsao_ativa.get('forca_real', 0),
                'green': self.previsao_ativa.get('green', False)
            })
            
            self.previsao_ativa = None
            self.ultima_entrada_rodada = rodada_atual
            self.rodadas_sem_entrada = 0
        
        if self.estrategia_ativa_manual:
            return
        
        # ==========================================
        # GERA PREVISÃO AUTOMÁTICA CONFORME O FLUXO
        # ==========================================
        if len(self.historico_numeros) >= 5:
            # Verifica se está bloqueado
            if rodada_atual < self.bloqueado_ate_rodada:
                return
            
            intervalo = st.session_state.get('intervalo_minimo_entradas', 0)
            
            if rodada_atual - self.ultima_entrada_rodada >= intervalo:
                
                # 🟢 FLUXO 1: Green automático
                if self.ultima_entrada_green and self.ultima_entrada_numeros and self.repeticoes_acerto_consecutivas > 0:
                    previsao_green = {
                        'nome': 'Bot Unificado',
                        'numeros_apostar': sorted(self.ultima_entrada_numeros),
                        'gatilho': f'🟢 GREEN #{self.repeticoes_acerto_consecutivas}/3 - Repetindo após acerto',
                        'forca_real': self.ultima_entrada_forca + 10,
                        'confianca': 'Green',
                        'motor': self.ultima_entrada_motor,
                        'estrategias_ativas': [f'Green Repeat #{self.repeticoes_acerto_consecutivas}'],
                        'qtd_motores': 1,
                        'repeticao': False,
                        'green': True,
                        'green_count': self.repeticoes_acerto_consecutivas,
                        'giros_esperados': 0,
                        'modo_ia': self.modo_ia
                    }
                    
                    self.previsao_ativa = previsao_green
                    self.ultima_entrada_green = False
                    enviar_previsao_auto(previsao_green)
                    return
                
                # ⏳ FLUXO 2: Repetição após erro (espera concluída)
                if self.giros_restantes_espera == 0 and self.giros_espera_repeticao > 0 and self.ultima_entrada_numeros:
                    self.giros_espera_repeticao = 0
                    
                    previsao_repetida = {
                        'nome': 'Bot Unificado',
                        'numeros_apostar': sorted(self.ultima_entrada_numeros),
                        'gatilho': '⏳ REPETINDO ENTRADA ANTERIOR (após 2 giros de espera)',
                        'forca_real': self.ultima_entrada_forca,
                        'confianca': 'Repetição',
                        'motor': self.ultima_entrada_motor,
                        'estrategias_ativas': ['Repetição Automática pós-erro (2 giros)'],
                        'qtd_motores': 1,
                        'repeticao': True,
                        'green': False,
                        'green_count': 0,
                        'giros_esperados': 2,
                        'modo_ia': self.modo_ia
                    }
                    
                    self.previsao_ativa = previsao_repetida
                    self.ultima_entrada_numeros = []
                    enviar_previsao_auto(previsao_repetida)
                    return
                
                # 🧠 FLUXO 3: Nova análise normal
                top_n = st.session_state.get('top_n_apostas', 5)
                
                motores_ativos = {
                    'sniper': st.session_state.get('usar_sniper', True),
                    'mineracao': st.session_state.get('usar_mineracao', True),
                    'leque': st.session_state.get('usar_leque', True),
                    'giro': st.session_state.get('usar_giro', True),
                    'gap': st.session_state.get('usar_gap', True),
                    'sequencia': st.session_state.get('usar_sequencia', True),
                    'quadrantes': st.session_state.get('usar_quadrantes', True),
                    'terminais': st.session_state.get('usar_terminais', True),
                    'simetria': st.session_state.get('usar_simetria', True),
                    'ia_adaptativa': st.session_state.get('usar_ia_adaptativa', True)
                }
                
                nova = self.bot.analisar_e_prever(top_n, motores_ativos)
                
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
        self.giros_restantes_espera = 0
        self.giros_espera_repeticao = 0
        self.repeticoes_acerto_consecutivas = 0
        self.ultima_entrada_green = False
        self.ultima_entrada_numeros = []
        self.modo_ia = "MODERADO"
        self.entropia_atual = 3.5
        self.bloqueado_ate_rodada = 0
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
st.set_page_config(page_title="🎯 Bot Unificado — 10 Motores + IA + Auto Repeat", layout="centered")
st.title("🎯 Bot Unificado — 10 Motores + IA + Auto Repeat")

if "sistema" not in st.session_state or st.session_state.sistema is None:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    if not st.session_state.get('historico'):
        st.session_state.historico = dados.get('historico', [])
    
    sis = st.session_state.sistema
    sis.acertos = dados.get('sistema_acertos', 0)
    sis.erros = dados.get('sistema_erros', 0)
    sis.historico_desempenho = dados.get('sistema_historico_desempenho', [])
    sis.estrategia_ativa_manual = dados.get('estrategia_ativa_manual', False)
    sis.giros_espera_repeticao = dados.get('giros_espera_repeticao', 0)
    sis.giros_restantes_espera = dados.get('giros_restantes_espera', 0)
    sis.repeticoes_acerto_consecutivas = dados.get('repeticoes_acerto_consecutivas', 0)
    sis.ultima_entrada_numeros = dados.get('ultima_entrada_numeros', [])
    sis.ultima_entrada_forca = dados.get('ultima_entrada_forca', 0)
    sis.ultima_entrada_motor = dados.get('ultima_entrada_motor', '')
    sis.ultima_entrada_green = dados.get('ultima_entrada_green', False)
    sis.modo_ia = dados.get('modo_ia', 'MODERADO')
    sis.entropia_atual = dados.get('entropia_atual', 3.5)
    sis.bloqueado_ate_rodada = dados.get('bloqueado_ate_rodada', 0)
    
    historico_numeros = dados.get('historico_numeros', [])
    historico_lucky = dados.get('historico_lucky', [])
    
    for i, num in enumerate(historico_numeros):
        lucky = historico_lucky[i] if i < len(historico_lucky) else []
        sis.bot.atualizar(num, lucky)
        sis.historico_numeros.append(num)
        sis.historico_lucky.append(lucky)
    
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
    
    if os.path.exists(PADROES_PATH):
        try:
            with open(PADROES_PATH, 'r') as f:
                padroes = json.load(f)
                sis.bot.sequencia.padroes = defaultdict(list, {int(k): v for k, v in padroes.items()})
                sis.bot.sequencia.atualizado = True
        except:
            pass

defaults = {
    'modo_automatico': True, 'top_n_apostas': 5,
    'intervalo_minimo_entradas': 0, 'janela_analise': 50,
    'janela_leque': 20, 'forca_minima_sinal': 40,
    'usar_sniper': True, 'usar_mineracao': True,
    'usar_leque': True, 'usar_giro': True,
    'usar_gap': True, 'usar_sequencia': True,
    'usar_quadrantes': True, 'usar_terminais': True, 'usar_simetria': True,
    'usar_ia_adaptativa': True,
    'max_repeticoes_acerto': 3
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

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

# Sidebar simplificado
st.sidebar.title("⚙️ Configurações")

with st.sidebar.expander("🤖 Motores Ativos", expanded=True):
    st.session_state.usar_ia_adaptativa = st.checkbox("🧠 IA Adaptativa V3 (PRIORITÁRIO)", value=st.session_state.usar_ia_adaptativa)
    st.session_state.usar_sniper = st.checkbox("🎯 Sniper", value=st.session_state.usar_sniper)
    st.session_state.usar_mineracao = st.checkbox("🔬 Mineração", value=st.session_state.usar_mineracao)
    st.session_state.usar_leque = st.checkbox("🪭 Leque Dinâmico", value=st.session_state.usar_leque)
    st.session_state.usar_giro = st.checkbox("🔄 Análise por Giro", value=st.session_state.usar_giro)
    st.session_state.usar_gap = st.checkbox("🔁 Gap", value=st.session_state.usar_gap)
    st.session_state.usar_sequencia = st.checkbox("📊 Sequência", value=st.session_state.usar_sequencia)
    st.session_state.usar_quadrantes = st.checkbox("🟩 Quadrantes", value=st.session_state.usar_quadrantes)
    st.session_state.usar_terminais = st.checkbox("🔢 Terminais", value=st.session_state.usar_terminais)
    st.session_state.usar_simetria = st.checkbox("🔄 Simetria", value=st.session_state.usar_simetria)

# Sistema automático (informativo)
with st.sidebar.expander("🔄 Auto Repeat (Automático)", expanded=True):
    st.success("✅ **Sistema 100% Automático**")
    st.info("""
    **Fluxo automático:**
    
    🟢 **Green Repeat:**
    - Acertou → repete mesma entrada
    - Até 3x consecutivas
    - Errou → reseta
    
    ⏳ **Erro Repeat:**
    - Errou → espera 2 giros
    - Repete a entrada
    - Acerto → reseta
    
    🧠 **Análise Normal:**
    - Quando não há green/repeat ativo
    """)

with st.sidebar.expander("⚙️ Ajustes", expanded=True):
    st.session_state.top_n_apostas = st.slider("📊 Números por aposta", 3, 15, st.session_state.top_n_apostas)
    st.session_state.intervalo_minimo_entradas = st.slider("⏱️ Intervalo entre entradas", 0, 3, st.session_state.intervalo_minimo_entradas)
    st.session_state.janela_leque = st.slider("🪭 Janela do Leque", 10, 50, st.session_state.janela_leque, 5)

st.session_state.modo_automatico = st.sidebar.checkbox("🔄 Modo Automático", value=st.session_state.modo_automatico)
if st.sidebar.button("Atualizar"):
    st.session_state.sistema.estrategia_ativa_manual = not st.session_state.modo_automatico
    st.rerun()

with st.sidebar.expander("💾 Geral", expanded=False):
    if st.button("💾 Salvar", use_container_width=True):
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()
        st.success("✅")
    if st.button("🗑️ Zerar", use_container_width=True):
        if st.checkbox("Confirmar"):
            st.session_state.sistema.zerar_estatisticas()
            st.rerun()

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
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("🟢 Acertos", status['acertos'])
c2.metric("🔴 Erros", status['erros'])
c3.metric("📊 Total", status['total'])
c4.metric("⏳ Sem Entrada", status['rodadas_sem_entrada'])
c5.metric("🟢 Green #", st.session_state.sistema.repeticoes_acerto_consecutivas)

if status['total'] > 0:
    taxa = status['acertos'] / status['total'] * 100
    if taxa >= 30:
        st.success(f"🎯 Taxa: {taxa:.1f}%")
    elif taxa >= 20:
        st.warning(f"🎯 Taxa: {taxa:.1f}%")
    else:
        st.error(f"🎯 Taxa: {taxa:.1f}%")

# Estado do sistema
sis = st.session_state.sistema

st.subheader("🧠 Estado do Sistema")
ec1, ec2, ec3 = st.columns(3)
with ec1:
    if sis.modo_ia == "AGRESSIVO":
        st.success(f"🟢 IA: {sis.modo_ia}")
    elif sis.modo_ia == "MODERADO":
        st.warning(f"🟡 IA: {sis.modo_ia}")
    else:
        st.error(f"🔴 IA: {sis.modo_ia}")
with ec2:
    if sis.repeticoes_acerto_consecutivas > 0:
        st.success(f"🟢 Green: {sis.repeticoes_acerto_consecutivas}/3")
    else:
        st.info("🟢 Green: Inativo")
with ec3:
    if sis.giros_restantes_espera > 0:
        st.warning(f"⏳ Espera: {sis.giros_restantes_espera} giros")
    else:
        st.info("⏳ Espera: Livre")

# Previsão
st.subheader("🎯 Previsão Ativa")

if sis.estrategia_ativa_manual:
    st.warning("⚠️ MANUAL")
elif sis.previsao_ativa:
    p = sis.previsao_ativa
    f = p.get('forca_real', 0)
    motor = p.get('motor', '')
    estrategias = p.get('estrategias_ativas', [])
    repeticao = p.get('repeticao', False)
    green = p.get('green', False)
    green_count = p.get('green_count', 0)
    
    if green:
        st.success(f"🟢 **GREEN #{green_count}!** Repetindo após acerto")
    elif repeticao:
        st.success(f"⏳ **REPETINDO ENTRADA!** (após erro)")
    elif f >= 55:
        st.success(f"🔥 **FORÇA {f}%** - {motor}")
    elif f >= 35:
        st.warning(f"🎯 **FORÇA {f}%** - {motor}")
    else:
        st.info(f"📊 **FORÇA {f}%** - {motor}")
    
    st.caption(f"📋 {p['gatilho']}")
    if estrategias:
        st.caption(f"🎯 {', '.join(estrategias[:4])}")
    
    nums = sorted(p['numeros_apostar'])
    st.markdown(f"### {', '.join(map(str, nums))}")
else:
    st.info("🎲 Aguardando próxima análise...")

# Performance
st.subheader("📈 Performance")
taxa_bot = sis.bot.get_taxa_acerto()
total_bot = sis.bot.get_total_tentativas()
if total_bot > 0:
    emoji = "🟢" if taxa_bot >= 0.30 else "🟡" if taxa_bot >= 0.20 else "🔴"
    st.write(f"{emoji} **Bot**: {taxa_bot:.0%} ({sis.bot.performance['acertos']}/{total_bot})")

if sis.historico_desempenho:
    st.write("**🔍 Últimas:**")
    for r in sis.historico_desempenho[-5:]:
        e = "🎉" if r['acerto'] else "❌"
        g = " 🟢" if r.get('green') else ""
        m = f" ⚡{r['multiplicador']}x" if r.get('multiplicador') and r['acerto'] else ""
        st.write(f"{e}{g} ({r.get('forca',0)}%): {r['numero']}{m}")

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

salvar_sessao()
