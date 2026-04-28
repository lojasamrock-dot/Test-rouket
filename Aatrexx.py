import streamlit as st
import json
import os
import requests
import logging
from collections import Counter, defaultdict
from streamlit_autorefresh import st_autorefresh
import pickle
from datetime import datetime
import time

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_roleta.json"
PERFORMANCE_PATH = "performance_bot.json"
PADROES_PATH = "padroes_sequencia.json"
PERFORMANCE_MOTORES_PATH = "performance_motores.json"

def salvar_sessao():
    try:
        if 'sistema' not in st.session_state or st.session_state.sistema is None:
            return False
        
        performance_data = {
            'acertos': st.session_state.sistema.bot.performance['acertos'],
            'erros': st.session_state.sistema.bot.performance['erros'],
            'historico': list(st.session_state.sistema.bot.performance['historico'])
        }
        with open(PERFORMANCE_PATH, 'w') as f:
            json.dump(performance_data, f)
        
        perf_motores_serializable = {}
        for motor, dados in st.session_state.sistema.bot.performance_motores.items():
            perf_motores_serializable[motor] = {
                'acertos': dados['acertos'],
                'erros': dados['erros'],
                'total': dados['total'],
                'historico': list(dados['historico']),
                'forca_media': dados['forca_media'],
                'ultima_forca': dados['ultima_forca']
            }
        with open(PERFORMANCE_MOTORES_PATH, 'w') as f:
            json.dump(perf_motores_serializable, f)
        
        session_data = {
            'historico': st.session_state.get('historico', []),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'sistema_acertos': st.session_state.sistema.acertos,
            'sistema_erros': st.session_state.sistema.erros,
            'historico_numeros': list(st.session_state.sistema.bot.historico),
            'historico_lucky': list(st.session_state.sistema.bot.lucky),
            'estrategia_ativa_manual': st.session_state.sistema.estrategia_ativa_manual,
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'top_n_apostas': st.session_state.get('top_n_apostas', 13),
            'intervalo_minimo_entradas': st.session_state.get('intervalo_minimo_entradas', 0),
            'usar_sniper': st.session_state.get('usar_sniper', True),
            'usar_mineracao': st.session_state.get('usar_mineracao', True),
            'usar_giro': st.session_state.get('usar_giro', True),
            'usar_gap': st.session_state.get('usar_gap', True),
            'usar_sequencia': st.session_state.get('usar_sequencia', True),
            'usar_quadrantes': st.session_state.get('usar_quadrantes', True),
            'usar_terminais': st.session_state.get('usar_terminais', True),
            'usar_protecao_zero': st.session_state.get('usar_protecao_zero', True),
            'usar_lightning_hunt': st.session_state.get('usar_lightning_hunt', True),
            'usar_salto_curto': st.session_state.get('usar_salto_curto', True),
            'usar_cadeias_markov': st.session_state.get('usar_cadeias_markov', True),
            'usar_setores_franceses': st.session_state.get('usar_setores_franceses', True),
            'usar_ritmo_repeticao': st.session_state.get('usar_ritmo_repeticao', True),
            'usar_zero_vizinho': st.session_state.get('usar_zero_vizinho', True),
            'forca_minima_entrada': st.session_state.get('forca_minima_entrada', 30),
            'repetir_entrada': st.session_state.get('repetir_entrada', True),
            'repetir_acerto': st.session_state.get('repetir_acerto', True),
            'max_repeticoes_acerto': st.session_state.get('max_repeticoes_acerto', 3),
            'giros_restantes_espera': st.session_state.sistema.giros_restantes_espera,
            'repeticoes_acerto_consecutivas': st.session_state.sistema.repeticoes_acerto_consecutivas,
            'ultima_entrada_numeros': st.session_state.sistema.ultima_entrada_numeros,
            'ultima_entrada_forca': st.session_state.sistema.ultima_entrada_forca,
            'ultima_entrada_motor': st.session_state.sistema.ultima_entrada_motor,
            'ultima_entrada_green': st.session_state.sistema.ultima_entrada_green
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
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH, PADROES_PATH, PERFORMANCE_MOTORES_PATH]:
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
        motor = previsao.get('motor', '')
        
        if previsao.get('green', False): emoji = "🟢"
        elif previsao.get('repeticao', False): emoji = "⏳"
        elif forca >= 65: emoji = "🔥"
        elif forca >= 50: emoji = "🎯"
        else: emoji = "📊"
        
        st.toast(f"{emoji} {motor} - {forca}%", icon=emoji)
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            msg = f"🔔 ENTRADA {forca}%\n🔢 {len(numeros)} números:\n" + " ".join(map(str, numeros))
            enviar_telegram(msg)
        
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar previsão: {e}")

def enviar_resultado_auto(numero_real, acerto, multiplicador=None):
    try:
        msg = f"✅ ACERTO! {numero_real}" if acerto else f"❌ ERRO! {numero_real}"
        if multiplicador and multiplicador > 0: msg += f" ⚡{multiplicador}x"
        
        st.toast(msg, icon="✅" if acerto else "❌")
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"📢 {msg}")
        
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar resultado: {e}")

def enviar_telegram(mensagem):
    try:
        token = st.session_state.get('telegram_token', '')
        chat_id = st.session_state.get('telegram_chat_id', '')
        if not token or not chat_id: return False
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}, timeout=10)
        return True
    except: return False

def testar_telegram():
    try:
        token = st.session_state.get('telegram_token', '')
        chat_id = st.session_state.get('telegram_chat_id', '')
        if not token or not chat_id: return False, "Token ou Chat ID não configurados"
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        response = requests.post(url, json={"chat_id": chat_id, "text": "✅ Teste - Bot 15 Motores", "parse_mode": "HTML"}, timeout=10)
        return (True, "✅ Conexão OK!") if response.status_code == 200 else (False, f"❌ Erro: {response.status_code}")
    except Exception as e: return False, f"❌ Erro: {str(e)}"

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
        self.vizinhos_zero = {0, 32, 26, 3, 35, 12, 28, 7, 29}
        self.voisins_du_zero = {22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25}
        self.orphelins = {1, 20, 14, 31, 9, 17, 34, 6}
        self.tiers_du_cylindre = {27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33}
        self.vizinhos_proximos = {n: set(self.get_vizinhos(n, 1)) for n in self.race}
    
    def get_vizinhos(self, numero, raio=2):
        if numero not in self.race: return []
        idx = self.race.index(numero)
        return [self.race[(idx + i) % 37] for i in range(-raio, raio + 1)]
    
    def get_setor_frances(self, numero):
        if numero in self.voisins_du_zero: return 'Voisins'
        if numero in self.orphelins: return 'Orphelins'
        if numero in self.tiers_du_cylindre: return 'Tiers'
        return 'Zero'
    
    def get_distancia_fisica(self, n1, n2):
        if n1 not in self.race or n2 not in self.race: return 99
        idx1, idx2 = self.race.index(n1), self.race.index(n2)
        return min(abs(idx1 - idx2), 37 - abs(idx1 - idx2))
    
    def get_setor(self, numero):
        return 0 if numero == 0 else (numero - 1) // 12 + 1
    
    def get_coluna(self, numero):
        return 0 if numero == 0 else (numero - 1) % 3 + 1
    
    def get_cor(self, numero):
        if numero == 0: return 'Verde'
        return 'Vermelho' if numero in self.vermelhos else 'Preto'


# =============================
# 15 ESTRATÉGIAS OTIMIZADAS
# =============================

class EstrategiaSniper:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico, lucky_recentes):
        if len(historico) < 15: return None
        recentes = historico[-15:]
        duzias = Counter([self.roleta.get_setor(n) for n in recentes if n != 0])
        colunas = Counter([self.roleta.get_coluna(n) for n in recentes if n != 0])
        melhor_duzia = duzias.most_common(1)[0][0] if duzias else None
        melhor_coluna = colunas.most_common(1)[0][0] if colunas else None
        roda_hits = [n for r in recentes for n in self.roleta.get_vizinhos(r, 1)]
        zona_quente = Counter(roda_hits).most_common(1)[0][0] if roda_hits else None
        vizinhos_zona = self.roleta.get_vizinhos(zona_quente, 2) if zona_quente else []
        forca, base, estrategias = 0, set(), []
        if melhor_duzia and melhor_coluna and duzias[melhor_duzia] >= 7 and colunas[melhor_coluna] >= 6:
            forca += 60; d, c = melhor_duzia, melhor_coluna
            base.update(set(range((d-1)*12+1, d*12+1)).intersection(set(range(c, 37, 3))))
            estrategias.append("Interseção D/C")
        if zona_quente and vizinhos_zona and sum(1 for n in recentes if n in vizinhos_zona) >= 5:
            forca += 50; base.update(vizinhos_zona); estrategias.append("Cluster Físico")
        return {'base': base, 'forca': min(100, forca), 'estrategias': estrategias} if forca > 0 and base else None


class EstrategiaMineracao:
    def __init__(self): self.transicoes = defaultdict(list)
    def analisar(self, historico):
        if len(historico) < 10: return None
        self.transicoes.clear()
        for i in range(len(historico)-1): self.transicoes[historico[i]].append(historico[i+1])
        ultimo = historico[-1]; base, forca = set(), 0
        seguidores = self.transicoes.get(ultimo, [])
        if seguidores:
            top = [n for n, c in Counter(seguidores).most_common(5) if c >= 2]
            if top: base.update(top[:3]); forca += 35
        return {'base': base, 'forca': forca, 'estrategias': ['Markov']} if base else None


class EstrategiaPorGiro:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico, lucky_recentes):
        if len(historico) < 5: return None
        ultimos_10 = historico[-10:] if len(historico) >= 10 else historico
        quentes = [n for n, _ in Counter(ultimos_10).most_common(8)]
        return {'base': set(quentes[:6]), 'forca': 40, 'estrategias': ['Quentes']} if quentes else None


class EstrategiaGap:
    def analisar(self, historico):
        if len(historico) < 5: return None
        ultimo = historico[-1]
        if len(historico) >= 3 and historico[-3] == ultimo: return {'base': {ultimo, historico[-2]}, 'forca': 60, 'estrategias': ['Gap1']}
        if len(historico) >= 4 and historico[-4] == ultimo: return {'base': {ultimo, historico[-2], historico[-3]}, 'forca': 50, 'estrategias': ['Gap2']}
        return None


class EstrategiaSequencia:
    def __init__(self): self.padroes = defaultdict(list)
    def treinar(self, historico):
        self.padroes.clear()
        for i in range(len(historico)-1): self.padroes[historico[i]].append(historico[i+1])
    def prever(self, numero, top_n=10):
        if numero not in self.padroes: return []
        return [n for n, _ in Counter(self.padroes[numero]).most_common(top_n)]
    def analisar(self, historico):
        if len(historico) < 10: return None
        self.treinar(historico); ultimo = historico[-1]; previsao = self.prever(ultimo, 10)
        return {'base': set(previsao[:6]), 'forca': 50, 'estrategias': ['Sequência']} if len(previsao) >= 3 else None


class EstrategiaCiclosQuadrantes:
    def __init__(self): self.quadrantes = {1: set(range(1,10)), 2: set(range(10,19)), 3: set(range(19,28)), 4: set(range(28,37))}
    def analisar(self, historico, janela=8):
        if len(historico) < janela: return None
        vistos = set()
        for n in list(historico)[-janela:]:
            for q_id, nums in self.quadrantes.items():
                if n in nums: vistos.add(q_id); break
        ausentes = set(self.quadrantes.keys()) - vistos
        if ausentes:
            base = set()
            for q_id in ausentes: base.update(self.quadrantes[q_id])
            return {'base': base, 'forca': 50 + len(ausentes)*10, 'estrategias': [f"Quadrantes {ausentes}"]}
        return None


class EstrategiaTerminais:
    def __init__(self): self.terminais = {i: [n for n in range(37) if n%10==i] for i in range(10)}
    def analisar(self, historico, janela=12):
        if len(historico) < janela: return None
        finais = Counter([n%10 for n in historico[-janela:]])
        base, forca, estrategias = set(), 0, []
        for t, f in finais.most_common(3):
            if f >= 2:
                base.update(self.terminais[t]); forca += 30 + f*5
                estrategias.append(f"Terminal {t} ({f}x)")
                if historico[-1] % 10 == t: forca += 15
        termos_ultimos = [n%10 for n in historico[-5:]]
        if any(t in [1,2,4] for t in termos_ultimos):
            for t in [1,2,4]: base.update(self.terminais[t]); forca += 20
            estrategias.append("Conexão T1-2-4")
        if any(t in [3,6,9] for t in termos_ultimos):
            for t in [3,6,9]: base.update(self.terminais[t]); forca += 20
            estrategias.append("Conexão T3-6-9")
        return {'base': base, 'forca': min(100, forca), 'estrategias': estrategias} if base else None


class EstrategiaProtecaoZero:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico):
        if len(historico) < 10: return None
        zeros_15 = historico[-15:].count(0) if len(historico) >= 15 else historico.count(0)
        if zeros_15 >= 2: return {'base': self.roleta.vizinhos_zero.copy(), 'forca': 65, 'estrategias': ['Zero Agressivo']}
        if len(historico) >= 20 and 0 not in historico[-20:]: return {'base': self.roleta.vizinhos_zero.copy(), 'forca': 45, 'estrategias': ['Zero Atrasado']}
        return None


class EstrategiaLightningHunt:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico, historico_lucky):
        if not historico_lucky or len(historico) < 3: return None
        lucky_recentes = [n for sub in list(historico_lucky)[-3:] for n in sub]
        if not lucky_recentes: return None
        base = set(list(set(lucky_recentes))[:6])
        estrategias, forca = ['👻 Sombra Lucky'], 35
        lucky_10 = [n for sub in (list(historico_lucky)[-10:] if historico_lucky else []) for n in sub]
        if lucky_10:
            repetidos = [n for n, c in Counter(lucky_10).items() if c >= 2][:3]
            for n in repetidos: base.add(n); base.update(self.roleta.get_vizinhos(n, 1)[:2])
            if repetidos: forca += 20; estrategias = [f"⚡ Lucky Repetido"]
        return {'base': base, 'forca': min(100, forca), 'estrategias': estrategias} if base else None


class EstrategiaSaltoCurto:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico):
        if len(historico) < 5: return None
        recentes = historico[-10:]
        saltos_curtos = sum(1 for i in range(len(recentes)-1) if 1 <= self.roleta.get_distancia_fisica(recentes[i], recentes[i+1]) <= 3)
        taxa = saltos_curtos / (len(recentes)-1) * 100 if len(recentes) > 1 else 0
        base, estrategias, forca = set(), [], 0
        if taxa >= 50:
            base.update(self.roleta.get_vizinhos(historico[-1], 3))
            forca += 45 + int(taxa/2); estrategias.append(f"🎯 Salto Curto ({taxa:.0f}%)")
        ultimos_5 = historico[-5:]
        clusters = sum(1 for i in range(len(ultimos_5)-1) if ultimos_5[i+1] in self.roleta.vizinhos_proximos.get(ultimos_5[i], set()))
        if clusters >= 2:
            base.update(self.roleta.get_vizinhos(historico[-1], 2))
            forca += 45 + clusters*10; estrategias.append(f"🔗 Micro-Clusters ({clusters})")
        return {'base': base, 'forca': min(100, forca), 'estrategias': estrategias} if base and forca >= 40 else None


class EstrategiaCadeiasMarkov:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico):
        if len(historico) < 3: return None
        cadeias = {19: [23, 27], 23: [27], 30: [20], 6: [33], 27: [13, 36], 20: [14, 31], 33: [1, 20]}
        ultimo = historico[-1]
        if ultimo not in cadeias: return None
        base = set(cadeias[ultimo])
        for n in cadeias[ultimo]: base.update(self.roleta.get_vizinhos(n, 1)[:1])
        forca = 55
        if len(historico) >= 4 and historico[-3] == 19 and historico[-2] == 23 and historico[-1] == 27:
            base.update([13, 36]); forca += 20
        return {'base': base, 'forca': min(100, forca), 'estrategias': [f"⛓️ Cadeia: {ultimo}→{cadeias[ultimo]}"]}


class EstrategiaSetoresFranceses:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico):
        if len(historico) < 3: return None
        ultimo = historico[-1]; setor_ultimo = self.roleta.get_setor_frances(ultimo)
        base, estrategias, forca = set(), [], 0
        if setor_ultimo == 'Orphelins': base.update(self.roleta.voisins_du_zero); forca += 55; estrategias.append("🌉 Orphelins→Voisins")
        if setor_ultimo == 'Voisins':
            base.update(self.roleta.voisins_du_zero)
            if len(historico) >= 2 and self.roleta.get_setor_frances(historico[-2]) == 'Voisins': forca += 60; estrategias.append("🔄 Auto-Retenção Voisins")
            else: forca += 45; estrategias.append("📍 Voisins Recente")
        if setor_ultimo == 'Tiers': base.update(self.roleta.voisins_du_zero); forca += 40; estrategias.append("🔀 Tiers→Voisins")
        if len(historico) >= 30:
            janela = min(50, len(historico))
            setores_recentes = [self.roleta.get_setor_frances(n) for n in historico[-janela:]]
            freq_recentes = Counter(setores_recentes)
            todos_setores = [self.roleta.get_setor_frances(n) for n in historico]
            freq_total = Counter(todos_setores)
            for setor_nome, nums in [('Voisins', self.roleta.voisins_du_zero), ('Orphelins', self.roleta.orphelins), ('Tiers', self.roleta.tiers_du_cylindre)]:
                freq_rec = freq_recentes.get(setor_nome, 0) / janela * 100
                freq_tot = freq_total.get(setor_nome, 0) / len(historico) * 100
                if freq_rec >= freq_tot * 1.2 and freq_rec >= 30: base.update(nums); forca += 40; estrategias.append(f"📈 Momentum {setor_nome} ({freq_rec:.0f}%)")
        return {'base': base, 'forca': min(100, forca), 'estrategias': estrategias} if base and forca >= 40 else None


class EstrategiaRitmoRepeticao:
    def analisar(self, historico):
        if len(historico) < 12: return None
        recentes_20 = historico[-20:]; ciclos = defaultdict(list)
        for i, n in enumerate(recentes_20): ciclos[n].append(i)
        base, estrategias, forca = set(), [], 0
        for num, pos in ciclos.items():
            if len(pos) >= 3:
                gaps = [pos[i+1]-pos[i] for i in range(len(pos)-1)]
                if len([g for g in gaps if 3<=g<=4]) >= 2: base.add(num); forca += 40; estrategias.append(f"🔄 Espelho: {num}")
        gaps_curtos = [recentes_20[i] for i in range(len(recentes_20)-3) if recentes_20[i] == recentes_20[i+3]]
        if len(gaps_curtos) >= 2:
            top = [n for n, c in Counter(gaps_curtos).most_common(4) if c >= 1]
            base.update(top); forca += 45; estrategias.append(f"⚡ Gap Curto: {top[:3]}")
        freq_15 = Counter(historico[-15:])
        repetidos = [n for n, c in freq_15.items() if c >= 2]
        if len(repetidos) >= 3: base.update(repetidos[:5]); forca += 50; estrategias.append(f"🎵 Ritmo: {repetidos[:3]}")
        return {'base': base, 'forca': min(100, forca), 'estrategias': estrategias} if base and forca >= 40 else None


class EstrategiaZeroVizinho:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico_lucky_mult):
        if not historico_lucky_mult: return None
        for mult_dict in reversed(list(historico_lucky_mult)[-5:]):
            if isinstance(mult_dict, dict):
                for num, mult in mult_dict.items():
                    if mult and mult >= 200:
                        return {'base': self.roleta.voisins_du_zero.copy(), 'forca': 50, 'estrategias': [f"Voisins após ⚡{num} ({mult}x)"]}
        return None


# =============================
# BOT UNIFICADO (15 MOTORES)
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        self.sniper = EstrategiaSniper(self.roleta)
        self.mineracao = EstrategiaMineracao()
        self.giro = EstrategiaPorGiro(self.roleta)
        self.gap = EstrategiaGap()
        self.sequencia = EstrategiaSequencia()
        self.quadrantes_strat = EstrategiaCiclosQuadrantes()
        self.terminais_strat = EstrategiaTerminais()
        self.protecao_zero = EstrategiaProtecaoZero(self.roleta)
        self.lightning_hunt = EstrategiaLightningHunt(self.roleta)
        self.salto_curto = EstrategiaSaltoCurto(self.roleta)
        self.cadeias_markov = EstrategiaCadeiasMarkov(self.roleta)
        self.setores_franceses = EstrategiaSetoresFranceses(self.roleta)
        self.ritmo_repeticao = EstrategiaRitmoRepeticao()
        self.zero_vizinho = EstrategiaZeroVizinho(self.roleta)
        
        self.historico = []
        self.lucky = []
        self.lucky_mult = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.performance_motores = {}
        self._init_performance_motores()
        self._ultimo_timestamp = None
    
    def _init_performance_motores(self):
        motores = ['Sniper','Mineração','Análise Giro','Gap','Sequência','CicloQuadrantes','Terminais',
                   'ProtecaoZero','LightningHunt','SaltoCurto','CadeiasMarkov','SetoresFranceses',
                   'RitmoRepeticao','ZeroVizinho','Green_Repeat','Erro_Repeat']
        for m in motores:
            self.performance_motores[m] = {'acertos': 0, 'erros': 0, 'total': 0, 'historico': [], 'forca_media': 0, 'ultima_forca': 0}
    
    def atualizar(self, numero, timestamp=None, lucky_nums=None, lucky_mults=None):
        if timestamp and self._ultimo_timestamp == timestamp: return False
        self._ultimo_timestamp = timestamp
        self.historico.append(numero)
        self.lucky.append(lucky_nums if lucky_nums else [])
        self.lucky_mult.append(lucky_mults if lucky_mults else {})
        if len(self.historico) > 200: self.historico = self.historico[-200:]; self.lucky = self.lucky[-200:]; self.lucky_mult = self.lucky_mult[-200:]
        if len(self.historico) >= 2: self.sequencia.treinar(list(self.historico))
        return True
    
    def atualizar_resultado(self, acerto):
        self.performance['historico'].append(1 if acerto else 0)
        if len(self.performance['historico']) > 50: self.performance['historico'] = self.performance['historico'][-50:]
        if acerto: self.performance['acertos'] += 1
        else: self.performance['erros'] += 1
    
    def atualizar_performance_motor(self, motor_nome, acerto, forca=0):
        if motor_nome not in self.performance_motores: return
        perf = self.performance_motores[motor_nome]
        perf['total'] += 1
        if acerto: perf['acertos'] += 1
        else: perf['erros'] += 1
        perf['historico'].append(acerto)
        if len(perf['historico']) > 20: perf['historico'] = perf['historico'][-20:]
        perf['ultima_forca'] = forca
        if perf['total'] > 0: perf['forca_media'] = (perf['forca_media']*(perf['total']-1)+forca)/perf['total']
    
    def get_taxa_motor(self, motor_nome):
        if motor_nome not in self.performance_motores: return 0, 0, 0
        p = self.performance_motores[motor_nome]
        return (p['acertos']/p['total'], p['acertos'], p['total']) if p['total']>0 else (0,0,0)
    
    def get_melhores_motores(self, top_n=5):
        ranking = [(nome, p['acertos']/p['total'], p['acertos'], p['total'], p['forca_media'])
                   for nome, p in self.performance_motores.items() if p['total'] >= 2 and p['total'] > 0]
        ranking.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return ranking[:top_n]
    
    def get_taxa_acerto(self):
        total = self.performance['acertos'] + self.performance['erros']
        return self.performance['acertos']/total if total > 0 else 0
    
    def get_total_tentativas(self): return self.performance['acertos'] + self.performance['erros']
    
    def analisar_e_prever(self, top_n=13, motores_ativos=None, forca_minima=30):
        hist_list = list(self.historico)
        if len(hist_list) < 5: return None
        if motores_ativos is None: motores_ativos = {k: True for k in ['sniper','mineracao','giro','gap','sequencia','quadrantes','terminais','protecao_zero','lightning_hunt','salto_curto','cadeias_markov','setores_franceses','ritmo_repeticao','zero_vizinho']}
        
        lucky_recentes = [n for sub in list(self.lucky)[-10:] for n in sub]
        resultados = []
        nome_motor_map = {'sniper':'Sniper','mineracao':'Mineração','giro':'Análise Giro','gap':'Gap','sequencia':'Sequência','quadrantes':'CicloQuadrantes','terminais':'Terminais','protecao_zero':'ProtecaoZero','lightning_hunt':'LightningHunt','salto_curto':'SaltoCurto','cadeias_markov':'CadeiasMarkov','setores_franceses':'SetoresFranceses','ritmo_repeticao':'RitmoRepeticao','zero_vizinho':'ZeroVizinho'}
        
        estrategias = [
            ('sniper', lambda: self.sniper.analisar(hist_list, lucky_recentes), 15),
            ('mineracao', lambda: self.mineracao.analisar(hist_list), 10),
            ('giro', lambda: self.giro.analisar(hist_list, lucky_recentes), 5),
            ('gap', lambda: self.gap.analisar(hist_list), 5),
            ('sequencia', lambda: self.sequencia.analisar(hist_list), 10),
            ('quadrantes', lambda: self.quadrantes_strat.analisar(hist_list), 8),
            ('terminais', lambda: self.terminais_strat.analisar(hist_list), 8),
            ('protecao_zero', lambda: self.protecao_zero.analisar(hist_list), 10),
            ('lightning_hunt', lambda: self.lightning_hunt.analisar(hist_list, list(self.lucky)), 3),
            ('salto_curto', lambda: self.salto_curto.analisar(hist_list), 5),
            ('cadeias_markov', lambda: self.cadeias_markov.analisar(hist_list), 3),
            ('setores_franceses', lambda: self.setores_franceses.analisar(hist_list), 3),
            ('ritmo_repeticao', lambda: self.ritmo_repeticao.analisar(hist_list), 12),
            ('zero_vizinho', lambda: self.zero_vizinho.analisar(list(self.lucky_mult)), 3),
        ]
        
        for key, func, min_len in estrategias:
            if motores_ativos.get(key, True) and len(hist_list) >= min_len:
                try:
                    r = func()
                    if r and r.get('forca', 0) >= forca_minima: resultados.append((nome_motor_map.get(key, key), r))
                except: pass
        
        if not resultados: return None
        
        freq_base = Counter()
        for motor, r in resultados:
            peso = r['forca'] / 100
            for n in r['base']: freq_base[n] += peso
        
        ultimos_10 = hist_list[-10:]; freq_recentes = Counter(ultimos_10)
        for n in freq_base:
            fc = freq_recentes.get(n, 0)
            if fc >= 2: freq_base[n] *= 1.5
            elif fc >= 1: freq_base[n] *= 1.2
        
        prioridade = [n for n, _ in freq_base.most_common()]
        if len(prioridade) < 12:
            for n, _ in freq_recentes.most_common(20):
                if n not in prioridade: prioridade.append(n)
                if len(prioridade) >= 12: break
        if len(prioridade) < 12:
            todos = set(); 
            for _, r in resultados: todos.update(r['base'])
            for n in todos:
                if n not in prioridade: prioridade.append(n)
                if len(prioridade) >= 12: break
        
        base_list = prioridade[:15]
        if len(base_list) < 12:
            for n in range(37):
                if n not in base_list: base_list.append(n)
                if len(base_list) >= 12: break
        
        todas_estrategias, forca_total, motor_principal, maior_forca = [], 0, "", 0
        for motor, r in resultados:
            todas_estrategias.extend(r.get('estrategias', []))
            forca_total += r['forca']
            if r['forca'] > maior_forca: maior_forca = r['forca']; motor_principal = motor
        
        forca_media = int(forca_total / len(resultados)) if resultados else 20
        forca_media = min(100, max(20, forca_media))
        
        return {
            'nome': 'Bot Unificado', 'numeros_apostar': sorted(base_list),
            'gatilho': f"u={hist_list[-1]}", 'forca_real': forca_media,
            'confianca': 'Alta' if forca_media >= 65 else 'Média' if forca_media >= 45 else 'Baixa',
            'motor': motor_principal, 'estrategias_ativas': list(set(todas_estrategias))[:5],
            'qtd_motores': len(resultados), 'repeticao': False, 'green': False, 'green_count': 0, 'giros_esperados': 0
        }
    
    def zerar(self):
        self.historico = []; self.lucky = []; self.lucky_mult = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self._init_performance_motores(); self._ultimo_timestamp = None


# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaBot:
    def __init__(self):
        self.bot = RoletaBotUnificado()
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.rodadas_sem_entrada = 0
        self.ultima_entrada_rodada = -10
        self.estrategia_ativa_manual = False
        self.giros_restantes_espera = 0
        self.repeticoes_acerto_consecutivas = 0
        self.ultima_entrada_green = False
        self.ultima_entrada_numeros = []
        self.ultima_entrada_forca = 0
        self.ultima_entrada_motor = ""
    
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            numero_real = numero_data['number']
            lucky = numero_data.get('luckyNumbers', [])
            lucky_mults = numero_data.get('luckyMultipliers', {})
            mult = lucky_mults.get(numero_real) if numero_real in lucky else None
            timestamp = numero_data.get('timestamp', str(time.time()))
        else:
            numero_real = numero_data; lucky = []; lucky_mults = {}; mult = None
            timestamp = str(time.time())
        
        if not self.bot.atualizar(numero_real, timestamp, lucky, lucky_mults): return
        
        self.rodadas_sem_entrada += 1
        if self.giros_restantes_espera > 0: self.giros_restantes_espera -= 1
        
        if self.previsao_ativa:
            acerto = numero_real in self.previsao_ativa.get('numeros_apostar', [])
            self.bot.atualizar_resultado(acerto)
            
            motor_principal = self.previsao_ativa.get('motor', '')
            forca = self.previsao_ativa.get('forca_real', 0)
            motor_perf = 'Green_Repeat' if self.previsao_ativa.get('green') else 'Erro_Repeat' if self.previsao_ativa.get('repeticao') else motor_principal
            
            self.bot.atualizar_performance_motor(motor_perf, acerto, forca)
            
            if acerto:
                self.acertos += 1
                if st.session_state.get('repetir_acerto', True):
                    if self.repeticoes_acerto_consecutivas < st.session_state.get('max_repeticoes_acerto', 3):
                        self.repeticoes_acerto_consecutivas += 1
                        self.ultima_entrada_green = True
                        self.ultima_entrada_numeros = self.previsao_ativa.get('numeros_apostar', [])
                        self.ultima_entrada_forca = forca + 10
                        self.ultima_entrada_motor = motor_principal
                    else: self.repeticoes_acerto_consecutivas = 0; self.ultima_entrada_green = False
                self.giros_restantes_espera = 0
            else:
                self.erros += 1; self.repeticoes_acerto_consecutivas = 0; self.ultima_entrada_green = False
                if (st.session_state.get('repetir_entrada', True) and not self.previsao_ativa.get('repeticao') and not self.previsao_ativa.get('green') and forca >= 45):
                    self.giros_restantes_espera = 1
                    self.ultima_entrada_numeros = self.previsao_ativa.get('numeros_apostar', [])
                    self.ultima_entrada_forca = forca; self.ultima_entrada_motor = motor_principal
            
            enviar_resultado_auto(numero_real, acerto, mult)
            self.historico_desempenho.append({'numero': numero_real, 'acerto': acerto, 'multiplicador': mult, 'forca': forca, 'green': self.previsao_ativa.get('green', False), 'motor': motor_perf})
            self.previsao_ativa = None
            self.ultima_entrada_rodada = len(self.bot.historico)
            self.rodadas_sem_entrada = 0
        
        if self.estrategia_ativa_manual: return
        
        if len(self.bot.historico) >= 5 and len(self.bot.historico) - self.ultima_entrada_rodada >= st.session_state.get('intervalo_minimo_entradas', 0):
            
            if self.ultima_entrada_green and self.ultima_entrada_numeros and self.repeticoes_acerto_consecutivas > 0:
                self.previsao_ativa = {'nome': 'Bot Unificado', 'numeros_apostar': sorted(self.ultima_entrada_numeros), 'gatilho': f'🟢 GREEN #{self.repeticoes_acerto_consecutivas}!', 'forca_real': min(100, self.ultima_entrada_forca + 15), 'confianca': 'Green', 'motor': self.ultima_entrada_motor, 'estrategias_ativas': [f'Green #{self.repeticoes_acerto_consecutivas}'], 'qtd_motores': 1, 'repeticao': False, 'green': True, 'green_count': self.repeticoes_acerto_consecutivas, 'giros_esperados': 0}
                self.ultima_entrada_green = False
                enviar_previsao_auto(self.previsao_ativa)
            elif self.giros_restantes_espera == 0 and self.ultima_entrada_numeros and not self.ultima_entrada_green:
                self.previsao_ativa = {'nome': 'Bot Unificado', 'numeros_apostar': sorted(self.ultima_entrada_numeros), 'gatilho': '⏳ REPETINDO', 'forca_real': self.ultima_entrada_forca, 'confianca': 'Repetição', 'motor': self.ultima_entrada_motor, 'estrategias_ativas': ['Repetição pós-erro'], 'qtd_motores': 1, 'repeticao': True, 'green': False, 'green_count': 0, 'giros_esperados': 1}
                self.ultima_entrada_numeros = []
                enviar_previsao_auto(self.previsao_ativa)
            elif self.giros_restantes_espera <= 0:
                top_n = st.session_state.get('top_n_apostas', 13)
                forca_minima = st.session_state.get('forca_minima_entrada', 30)
                motores_ativos = {k: st.session_state.get(f'usar_{k}', True) for k in ['sniper','mineracao','giro','gap','sequencia','quadrantes','terminais','protecao_zero','lightning_hunt','salto_curto','cadeias_markov','setores_franceses','ritmo_repeticao','zero_vizinho']}
                
                nova = self.bot.analisar_e_prever(top_n, motores_ativos, forca_minima)
                if nova is not None:
                    self.previsao_ativa = nova
                    enviar_previsao_auto(nova)
    
    def zerar_estatisticas(self):
        self.acertos = 0; self.erros = 0; self.historico_desempenho = []
        self.rodadas_sem_entrada = 0; self.ultima_entrada_rodada = -10
        self.giros_restantes_espera = 0; self.repeticoes_acerto_consecutivas = 0
        self.ultima_entrada_green = False; self.ultima_entrada_numeros = []
        self.bot.zerar(); salvar_sessao()
    
    def get_status(self):
        return {'acertos': self.acertos, 'erros': self.erros, 'total': self.acertos + self.erros, 'rodadas_sem_entrada': self.rodadas_sem_entrada}


# =============================
# FUNÇÕES AUXILIARES
# =============================
def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    try:
        with open(caminho, "w") as f: json.dump(historico, f, indent=2)
    except: pass

def extrair_numeros_raio(resultado_api):
    numeros_raio, multiplicadores = [], {}
    try:
        if resultado_api and isinstance(resultado_api, dict):
            for item in resultado_api.get('data', {}).get('result', {}).get('luckyNumbersList', []):
                n = item.get('number')
                if n is not None:
                    numeros_raio.append(n)
                    m = item.get('roundedMultiplier')
                    if m is not None: multiplicadores[n] = m
    except: pass
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
        timestamp = game_data.get("startedAt", str(time.time()))
        numeros_raio, multiplicadores = extrair_numeros_raio(data)
        return {"number": number, "timestamp": timestamp, "luckyNumbers": numeros_raio, "luckyMultipliers": multiplicadores}
    except: return None

def exportar_historico(historico, formato='json'):
    if formato == 'json': return json.dumps(historico, indent=2, ensure_ascii=False)
    linhas = ["numero,timestamp,multiplicador"]
    for item in historico:
        if isinstance(item, dict):
            n = item.get('number', ''); ts = item.get('timestamp', '')
            mult = item.get('luckyMultipliers', {}).get(n, '')
            linhas.append(f"{n},{ts},{mult}")
        else: linhas.append(f"{item},,")
    return "\n".join(linhas)


# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎯 Bot 15 Motores", layout="centered")
st.title("🎯 Bot Unificado — 15 Motores Otimizados")

if "sistema" not in st.session_state or st.session_state.sistema is None:
    st.session_state.sistema = SistemaBot()

# Carrega dados
dados = carregar_dados_persistidos()
if dados:
    sis = st.session_state.sistema
    sis.acertos = dados.get('sistema_acertos', 0); sis.erros = dados.get('sistema_erros', 0)
    sis.historico_desempenho = dados.get('sistema_historico_desempenho', [])
    sis.estrategia_ativa_manual = dados.get('estrategia_ativa_manual', False)
    sis.giros_restantes_espera = dados.get('giros_restantes_espera', 0)
    sis.repeticoes_acerto_consecutivas = dados.get('repeticoes_acerto_consecutivas', 0)
    sis.ultima_entrada_numeros = dados.get('ultima_entrada_numeros', [])
    sis.ultima_entrada_forca = dados.get('ultima_entrada_forca', 0)
    sis.ultima_entrada_motor = dados.get('ultima_entrada_motor', '')
    sis.ultima_entrada_green = dados.get('ultima_entrada_green', False)
    for num in dados.get('historico_numeros', []): sis.bot.historico.append(num)
    for lucky in dados.get('historico_lucky', []): sis.bot.lucky.append(lucky)
    if os.path.exists(PERFORMANCE_PATH):
        try:
            with open(PERFORMANCE_PATH, 'r') as f:
                perf = json.load(f)
                sis.bot.performance = {'acertos': perf.get('acertos', 0), 'erros': perf.get('erros', 0), 'historico': perf.get('historico', [])}
        except: pass
    if os.path.exists(PERFORMANCE_MOTORES_PATH):
        try:
            with open(PERFORMANCE_MOTORES_PATH, 'r') as f:
                for motor, dados_motor in json.load(f).items(): sis.bot.performance_motores[motor] = dados_motor
        except: pass
    if not st.session_state.get('historico'): st.session_state.historico = dados.get('historico', [])

# Defaults
defaults = {
    'modo_automatico': True, 'top_n_apostas': 13, 'intervalo_minimo_entradas': 0, 'forca_minima_entrada': 30,
    'usar_sniper': True, 'usar_mineracao': True, 'usar_giro': True, 'usar_gap': True,
    'usar_sequencia': True, 'usar_quadrantes': True, 'usar_terminais': True,
    'usar_protecao_zero': True, 'usar_lightning_hunt': True, 'usar_salto_curto': True,
    'usar_cadeias_markov': True, 'usar_setores_franceses': True, 'usar_ritmo_repeticao': True,
    'usar_zero_vizinho': True, 'repetir_entrada': True, 'repetir_acerto': True, 'max_repeticoes_acerto': 3
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
st.sidebar.title("⚙️ Configurações")

with st.sidebar.expander("🎯 Entrada", expanded=True):
    st.session_state.top_n_apostas = st.slider("🔢 Quantidade", 12, 15, st.session_state.top_n_apostas, key="sl_top_n")
    st.session_state.forca_minima_entrada = st.slider("🚫 Força Mínima", 25, 55, st.session_state.forca_minima_entrada, 5, key="sl_forca_min")

with st.sidebar.expander("🤖 15 Motores", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.usar_sniper = st.checkbox("🎯 Sniper", value=st.session_state.usar_sniper, key="cb_sniper")
        st.session_state.usar_mineracao = st.checkbox("🔬 Mineração", value=st.session_state.usar_mineracao, key="cb_mineracao")
        st.session_state.usar_giro = st.checkbox("🔄 Giro", value=st.session_state.usar_giro, key="cb_giro")
        st.session_state.usar_gap = st.checkbox("🔁 Gap", value=st.session_state.usar_gap, key="cb_gap")
        st.session_state.usar_sequencia = st.checkbox("📊 Sequência", value=st.session_state.usar_sequencia, key="cb_sequencia")
        st.session_state.usar_quadrantes = st.checkbox("🟩 Quadrantes", value=st.session_state.usar_quadrantes, key="cb_quadrantes")
        st.session_state.usar_terminais = st.checkbox("🔢 Terminais", value=st.session_state.usar_terminais, key="cb_terminais")
        st.session_state.usar_protecao_zero = st.checkbox("🎱 Zero-Hunt", value=st.session_state.usar_protecao_zero, key="cb_protecao_zero")
    with c2:
        st.session_state.usar_lightning_hunt = st.checkbox("⚡ Lightning", value=st.session_state.usar_lightning_hunt, key="cb_lightning_hunt")
        st.session_state.usar_salto_curto = st.checkbox("🎯 Salto Curto", value=st.session_state.usar_salto_curto, key="cb_salto_curto")
        st.session_state.usar_cadeias_markov = st.checkbox("⛓️ Cadeias Markov", value=st.session_state.usar_cadeias_markov, key="cb_cadeias_markov")
        st.session_state.usar_setores_franceses = st.checkbox("🇫🇷 Setores Franceses", value=st.session_state.usar_setores_franceses, key="cb_setores_franceses")
        st.session_state.usar_ritmo_repeticao = st.checkbox("🎵 Ritmo Repetição", value=st.session_state.usar_ritmo_repeticao, key="cb_ritmo_repeticao")
        st.session_state.usar_zero_vizinho = st.checkbox("🎯 Zero Vizinho", value=st.session_state.usar_zero_vizinho, key="cb_zero_vizinho")

with st.sidebar.expander("🟢 Green / ⏳ Erro", expanded=True):
    st.session_state.repetir_acerto = st.checkbox("🟢 Repetir após ACERTO", value=st.session_state.repetir_acerto, key="cb_repetir_acerto")
    st.session_state.max_repeticoes_acerto = st.slider("Máx. green", 1, 5, st.session_state.max_repeticoes_acerto, key="sl_max_green")
    st.session_state.repetir_entrada = st.checkbox("⏳ Repetir após erro", value=st.session_state.repetir_entrada, key="cb_repetir_entrada")

with st.sidebar.expander("🔔 Telegram", expanded=False):
    st.session_state.telegram_token = st.text_input("🤖 Token:", value=st.session_state.telegram_token, type="password", key="ti_telegram_token")
    st.session_state.telegram_chat_id = st.text_input("💬 Chat ID:", value=st.session_state.telegram_chat_id, key="ti_telegram_chat_id")
    if st.button("🧪 Testar", use_container_width=True, key="btn_testar_telegram"):
        sucesso, msg = testar_telegram()
        st.success(msg) if sucesso else st.error(msg)

st.session_state.modo_automatico = st.sidebar.checkbox("🔄 Modo Automático", value=st.session_state.modo_automatico, key="cb_modo_auto")
if st.sidebar.button("Atualizar Modo", use_container_width=True, key="btn_atualizar_modo"):
    st.session_state.sistema.estrategia_ativa_manual = not st.session_state.modo_automatico
    st.rerun()

with st.sidebar.expander("💾 Geral", expanded=False):
    if st.button("💾 Salvar", use_container_width=True, key="btn_salvar_dados"):
        salvar_resultado_em_arquivo(st.session_state.historico); salvar_sessao(); st.success("✅")
    if st.button("🗑️ Zerar", use_container_width=True, key="btn_zerar_tudo"):
        if st.checkbox("⚠️ Confirmar", key="cb_confirmar_zerar"):
            st.session_state.sistema.zerar_estatisticas(); st.rerun()

# =============================
# CONTEÚDO PRINCIPAL (CORRIGIDO)
# =============================
st.subheader("✍️ Inserir Sorteios")
c1, c2 = st.columns([3, 1])
with c1:
    entrada = st.text_input("Números (0-36):", key="ti_entrada_numeros")
with c2:
    def adicionar_numeros():
        nums_str = st.session_state.get('ti_entrada_numeros', '')
        if nums_str:
            try:
                nums = [int(n) for n in nums_str.split() if n.isdigit() and 0 <= int(n) <= 36]
                for n in nums:
                    item = {"number": n, "timestamp": f"manual_{len(st.session_state.historico)}_{time.time()}", "luckyNumbers": [], "luckyMultipliers": {}}
                    st.session_state.historico.append(item)
                    st.session_state.sistema.processar_novo_numero(item)
                salvar_resultado_em_arquivo(st.session_state.historico)
                salvar_sessao()
                st.session_state.msg_sucesso = f"✅ {len(nums)} adicionados!"
            except Exception as e:
                st.session_state.msg_erro = f"Erro: {e}"
    
    st.button("➕ Adicionar", use_container_width=True, key="btn_adicionar", on_click=adicionar_numeros)

if st.session_state.get('msg_sucesso'):
    st.success(st.session_state.msg_sucesso)
    st.session_state.msg_sucesso = None
if st.session_state.get('msg_erro'):
    st.error(st.session_state.msg_erro)
    st.session_state.msg_erro = None

st_autorefresh(interval=5000, key="autorefresh_main")

resultado = fetch_latest_result()
if resultado and resultado.get("timestamp"):
    if not st.session_state.historico or resultado.get("timestamp") != st.session_state.historico[-1].get("timestamp"):
        n = resultado.get("number")
        if n is not None:
            st.session_state.historico.append(resultado)
            st.session_state.sistema.processar_novo_numero(resultado)
            salvar_resultado_em_arquivo(st.session_state.historico)
            salvar_sessao()

st.subheader("🔁 Últimos Números")
if st.session_state.historico:
    ultimos = st.session_state.historico[-10:]; fmt = []
    for item in ultimos:
        n = item['number'] if isinstance(item, dict) else item
        if isinstance(item, dict) and n in item.get('luckyNumbers', []):
            mult = item.get('luckyMultipliers', {}).get(n, '')
            fmt.append(f"⚡**{n}**({mult}x)" if mult else f"⚡**{n}**")
        else: fmt.append(str(n))
    st.write(" ".join(fmt))

status = st.session_state.sistema.get_status()
c1, c2, c3, c4 = st.columns(4)
c1.metric("🟢 Acertos", status['acertos']); c2.metric("🔴 Erros", status['erros'])
c3.metric("📊 Total", status['total']); c4.metric("⏳ Sem Entrada", status['rodadas_sem_entrada'])

if status['total'] > 0:
    taxa = status['acertos'] / status['total'] * 100
    if taxa >= 30: st.success(f"🎯 Taxa: {taxa:.1f}%")
    elif taxa >= 20: st.warning(f"🎯 Taxa: {taxa:.1f}%")
    else: st.error(f"🎯 Taxa: {taxa:.1f}%")

sis = st.session_state.sistema
if sis.repeticoes_acerto_consecutivas > 0 and not sis.previsao_ativa:
    st.success(f"🟢 Green: {sis.repeticoes_acerto_consecutivas}/{st.session_state.max_repeticoes_acerto}")
elif sis.giros_restantes_espera > 0:
    st.warning(f"⏳ Aguardando {sis.giros_restantes_espera} giro(s)")

st.subheader("🎯 Previsão Ativa")
if sis.estrategia_ativa_manual:
    st.warning("⚠️ MODO MANUAL")
elif sis.previsao_ativa:
    p = sis.previsao_ativa; f = p.get('forca_real', 0); motor = p.get('motor', '')
    qtd = p.get('qtd_motores', 1); green = p.get('green', False); repeticao = p.get('repeticao', False)
    
    if green: st.success(f"🟢 GREEN #{p.get('green_count', 0)}!")
    elif repeticao: st.success("⏳ REPETINDO!")
    elif f >= 65: st.success(f"🔥 FORÇA {f}% ({qtd} motores)")
    elif f >= 50: st.warning(f"🎯 FORÇA {f}% ({qtd} motores)")
    else: st.info(f"📊 FORÇA {f}% ({qtd} motores)")
    
    if not repeticao and not green: st.caption(f"🤖 Motor: {motor}")
    st.write(f"🔢 {len(p['numeros_apostar'])} números:")
    st.markdown(f"### {', '.join(map(str, sorted(p['numeros_apostar'])))}")
else:
    st.info("🎲 Aguardando...")

st.subheader("🏆 Performance Individual")
ranking = sis.bot.get_melhores_motores(10)
if ranking:
    cols = st.columns(5)
    for i, (nome, taxa, acertos_m, total_m, _) in enumerate(ranking):
        with cols[i % 5]:
            emoji = "🟢" if taxa >= 0.30 else "🟡" if taxa >= 0.20 else "🔴" if total_m >= 2 else "⚪"
            st.metric(f"{emoji} {nome}", f"{taxa:.0%}", f"{acertos_m}/{total_m}")

st.subheader("📈 Performance Geral")
taxa_bot = sis.bot.get_taxa_acerto(); total_bot = sis.bot.get_total_tentativas()
if total_bot > 0:
    emoji = "🟢" if taxa_bot >= 0.30 else "🟡" if taxa_bot >= 0.20 else "🔴"
    st.write(f"{emoji} Bot: {taxa_bot:.0%} ({sis.bot.performance['acertos']}/{total_bot})")

if sis.historico_desempenho:
    st.write("🔍 Últimas:")
    for r in sis.historico_desempenho[-5:]:
        e = "🎉" if r['acerto'] else "❌"; g = " 🟢" if r.get('green') else ""
        m = f" ⚡{r['multiplicador']}x" if r.get('multiplicador') and r['acerto'] else ""
        st.write(f"{e}{g} ({r.get('forca',0)}%) [{r.get('motor','')}]: {r['numero']}{m}")

#st.subheader("📥 Download")
st.subheader("📥 Download")
st.metric("📊 Registros", len(st.session_state.historico))
col_d1, col_d2 = st.columns(2)
with col_d1:
    # 🆕 Download direto (sem botão aninhado)
    st.download_button(
        label="📥 Baixar JSON",
        data=exportar_historico(st.session_state.historico, 'json'),
        file_name=f"historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        key="btn_download_json"
    )
with col_d2:
    # 🆕 Download direto (sem botão aninhado)
    st.download_button(
        label="📥 Baixar CSV",
        data=exportar_historico(st.session_state.historico, 'csv'),
        file_name=f"historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        key="btn_download_csv"
    )
salvar_sessao()
