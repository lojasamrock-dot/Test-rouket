import streamlit as st
import json
import os
import requests
import logging
from collections import Counter, deque, defaultdict
from streamlit_autorefresh import st_autorefresh
import pickle
from datetime import datetime
import time

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA (MANTIDAS)
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
                'historico': list(dados['historico']) if isinstance(dados['historico'], (list, deque)) else dados['historico'],
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
            'usar_leque': st.session_state.get('usar_leque', True),
            'usar_giro': st.session_state.get('usar_giro', True),
            'usar_gap': st.session_state.get('usar_gap', True),
            'usar_sequencia': st.session_state.get('usar_sequencia', True),
            'usar_quadrantes': st.session_state.get('usar_quadrantes', True),
            'usar_terminais': st.session_state.get('usar_terminais', True),
            'usar_simetria': st.session_state.get('usar_simetria', True),
            'usar_protecao_zero': st.session_state.get('usar_protecao_zero', True),
            'usar_duzias_colunas': st.session_state.get('usar_duzias_colunas', True),
            'usar_lightning_hunt': st.session_state.get('usar_lightning_hunt', True),
            'usar_tendencia_cor': st.session_state.get('usar_tendencia_cor', True),
            'usar_sombra': st.session_state.get('usar_sombra', True),
            'usar_loop_terminal': st.session_state.get('usar_loop_terminal', True),
            'usar_gap_curto': st.session_state.get('usar_gap_curto', True),
            'usar_zero_vizinho': st.session_state.get('usar_zero_vizinho', True),
            'usar_espelho_temporal': st.session_state.get('usar_espelho_temporal', True),
            'usar_micro_clusters': st.session_state.get('usar_micro_clusters', True),
            'usar_ritmo_repeticao': st.session_state.get('usar_ritmo_repeticao', True),
            'usar_terminal_369': st.session_state.get('usar_terminal_369', True),
            'usar_ponte_setores': st.session_state.get('usar_ponte_setores', True),
            'usar_momentum_setor': st.session_state.get('usar_momentum_setor', True),
            'usar_salto_curto': st.session_state.get('usar_salto_curto', True),
            'usar_cadeias_markov': st.session_state.get('usar_cadeias_markov', True),
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
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH, PADROES_PATH, PERFORMANCE_MOTORES_PATH]:
            if os.path.exists(path):
                os.remove(path)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    except:
        pass

# =============================
# NOTIFICAÇÕES (MANTIDAS)
# =============================
def enviar_previsao_auto(previsao):
    try:
        numeros = sorted(previsao['numeros_apostar'])
        forca = previsao.get('forca_real', 0)
        motor = previsao.get('motor', '')
        green = previsao.get('green', False)
        repeticao = previsao.get('repeticao', False)
        
        if green: emoji = "🟢"
        elif repeticao: emoji = "⏳"
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
        if acerto: msg = f"✅ ACERTO! {numero_real}"
        else: msg = f"❌ ERRO! {numero_real}"
        if multiplicador and multiplicador > 0: msg += f" ⚡{multiplicador}x"
        
        st.toast(f"{'✅' if acerto else '❌'} {numero_real}", icon="✅" if acerto else "❌")
        
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
        payload = {"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
        return True
    except: return False

def testar_telegram():
    try:
        token = st.session_state.get('telegram_token', '')
        chat_id = st.session_state.get('telegram_chat_id', '')
        if not token or not chat_id: return False, "Token ou Chat ID não configurados"
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": "✅ Teste de conexão - Bot Elite Master", "parse_mode": "HTML"}
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200: return True, "✅ Conexão OK!"
        return False, f"❌ Erro: {response.status_code}"
    except Exception as e: return False, f"❌ Erro: {str(e)}"

API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# =============================
# ROLETA BASE (MANTIDA)
# =============================
class RoletaBase:
    def __init__(self):
        self.race = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        self.vermelhos = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        self.pretos = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
        self.voisins_du_zero = {22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25}
        self.orphelins = {1, 20, 14, 31, 9, 17, 34, 6}
        self.tiers_du_cylindre = {27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33}
        self.vizinhos_zero = {0, 32, 26, 3, 35, 12, 28, 7, 29}
    
    def get_vizinhos(self, numero, raio=2):
        if numero not in self.race: return []
        idx = self.race.index(numero)
        return [self.race[(idx + i) % 37] for i in range(-raio, raio + 1)]
    
    def get_setor_frances(self, numero):
        if numero in self.voisins_du_zero: return 'Voisins'
        if numero in self.orphelins: return 'Orphelins'
        if numero in self.tiers_du_cylindre: return 'Tiers'
        return 'Zero' if numero == 0 else 'Outro'

    def get_distancia_fisica(self, n1, n2):
        if n1 not in self.race or n2 not in self.race: return 99
        idx1, idx2 = self.race.index(n1), self.race.index(n2)
        dist = abs(idx1 - idx2)
        return min(dist, 37 - dist)

    def get_setor(self, n): return (n-1)//12+1 if n!=0 else 0
    def get_coluna(self, n): return (n-1)%3+1 if n!=0 else 0
    def get_cor(self, n): return 'Verde' if n==0 else 'Vermelho' if n in self.vermelhos else 'Preto'

# =============================
# 🚀 ESTRATÉGIAS OTIMIZADAS (REFATORADO)
# =============================

class MotorPadroes:
    """Unifica Mineração, Sequência, Markov e Cadeias."""
    def __init__(self, roleta):
        self.roleta = roleta
        self.transicoes = defaultdict(list)
    
    def analisar(self, historico):
        if len(historico) < 10: return None
        self.transicoes.clear()
        for i in range(len(historico)-1):
            self.transicoes[historico[i]].append(historico[i+1])
        
        ultimo = historico[-1]
        seguidores = self.transicoes.get(ultimo, [])
        if not seguidores: return None
        
        top = [n for n, c in Counter(seguidores).most_common(5) if c >= 1]
        base = set(top[:4])
        # Adiciona vizinhos físicos dos seguidores mais prováveis
        for n in list(base):
            base.update(self.roleta.get_vizinhos(n, 1)[:2])
            
        return {'base': base, 'forca': 45 + len(top)*5, 'estrategias': ['Cadeia de Markov']}

class MotorFrequencia:
    """Unifica Análise de Giro, Ritmo de Repetição e Quentes."""
    def analisar(self, historico):
        if len(historico) < 15: return None
        freq = Counter(historico[-20:])
        repetidos = [n for n, c in freq.items() if c >= 2]
        if not repetidos: return None
        return {'base': set(repetidos[:6]), 'forca': 40 + len(repetidos)*5, 'estrategias': ['Ritmo/Frequência']}

class MotorTerminais:
    """Unifica Terminais, Loop Terminal e Terminal 369."""
    def __init__(self):
        self.term_map = {i: [n for n in range(37) if n%10==i] for i in range(10)}
    
    def analisar(self, historico):
        if len(historico) < 10: return None
        recentes = [n%10 for n in historico[-12:]]
        finais = Counter(recentes)
        base, forca = set(), 0
        
        # Detecta terminais quentes
        for t, f in finais.most_common(2):
            if f >= 3: 
                base.update(self.term_map[t])
                forca += 30 + f*5
        
        # Filtro 3-6-9
        if any(recentes.count(t) >= 2 for t in [3,6,9]):
            for t in [3,6,9]: base.update(self.term_map[t])
            forca += 15
            
        if base: return {'base': base, 'forca': min(95, forca), 'estrategias': ['Terminais Elite']}
        return None

class MotorFisico:
    """Unifica Leque, Micro-Clusters e Salto Curto (Wheel Physics)."""
    def __init__(self, roleta):
        self.roleta = roleta
        
    def analisar(self, historico):
        if len(historico) < 10: return None
        ultimo = historico[-1]
        
        # Verifica se houve salto curto recentemente
        dist_recente = self.roleta.get_distancia_fisica(historico[-2], historico[-1])
        if 1 <= dist_recente <= 3:
            # Tendência de "cluster" físico detectada
            base = set(self.roleta.get_vizinhos(ultimo, 3))
            return {'base': base, 'forca': 60, 'estrategias': ['Wheel Physics']}
            
        # Padrão Leque padrão
        return {'base': set(self.roleta.get_vizinhos(ultimo, 2)), 'forca': 40, 'estrategias': ['Leque Otimizado']}

class MotorAtrasos:
    """Unifica Quadrantes, Dúzias e Colunas."""
    def __init__(self):
        self.quads = {1: set(range(1,10)), 2: set(range(10,19)), 3: set(range(19,28)), 4: set(range(28,37))}
        self.duzias = {1: set(range(1,13)), 2: set(range(13,25)), 3: set(range(25,37))}
        self.colunas = {1: set(range(1,37,3)), 2: set(range(2,37,3)), 3: set(range(3,37,3))}

    def analisar(self, historico):
        if len(historico) < 12: return None
        base, forca = set(), 0
        
        # Checa Quadrante atrasado (8 giros)
        vistos_q = {q for q, nums in self.quads.items() if any(n in nums for n in historico[-8:])}
        ausentes_q = set(self.quads.keys()) - vistos_q
        if ausentes_q:
            for q in ausentes_q: base.update(self.quads[q])
            forca += 35
            
        # Checa Dúzia/Coluna atrasada
        vistos_d = {d for d, nums in self.duzias.items() if any(n in nums for n in historico[-6:])}
        if len(vistos_d) < 3:
            for d in (set(self.duzias.keys()) - vistos_d): base.update(self.duzias[d])
            forca += 25
            
        if base: return {'base': base, 'forca': min(90, forca), 'estrategias': ['Atrasos Setoriais']}
        return None

class MotorMultiplicadores:
    """Unifica Lightning Hunt e Sombra."""
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico_lucky):
        if not historico_lucky: return None
        lucky_recentes = [n for sub in list(historico_lucky)[-10:] for n in sub]
        if not lucky_recentes: return None
        
        top = [n for n, c in Counter(lucky_recentes).most_common(5)]
        base = set(top)
        for n in top: base.update(self.roleta.get_vizinhos(n, 1)[:1])
        
        return {'base': base, 'forca': 50, 'estrategias': ['⚡ Multiplier Hunt']}

class MotorFrances:
    """Unifica Voisins, Orphelins, Tiers, Ponte e Momentum."""
    def __init__(self, roleta):
        self.roleta = roleta
        
    def analisar(self, historico):
        if len(historico) < 15: return None
        ultimo = historico[-1]
        setor = self.roleta.get_setor_frances(ultimo)
        
        # Análise de Momentum (Tendência de Setor)
        setores_recentes = [self.roleta.get_setor_frances(n) for n in historico[-20:]]
        freq = Counter(setores_recentes)
        setor_dominante = freq.most_common(1)[0][0]
        
        base, forca, label = set(), 0, ""
        
        if setor == 'Orphelins': # Ponte Orphelins -> Voisins
            base.update(self.roleta.voisins_du_zero)
            forca, label = 55, "Ponte O->V"
        elif freq[setor_dominante] / 20 >= 0.5: # Momentum detectado
            if setor_dominante == 'Voisins': base.update(self.roleta.voisins_du_zero)
            elif setor_dominante == 'Tiers': base.update(self.roleta.tiers_du_cylindre)
            elif setor_dominante == 'Orphelins': base.update(self.roleta.orphelins)
            forca, label = 65, f"Momentum {setor_dominante}"
        
        if base: return {'base': base, 'forca': forca, 'estrategias': [label]}
        return None

class MotorVies:
    """Unifica Simetria, Espelho Temporal e Gap."""
    def __init__(self):
        self.espelhos = {12:21, 21:12, 13:31, 31:13, 23:32, 32:23, 1:10, 10:1, 2:20, 20:2, 3:30, 30:3}
        
    def analisar(self, historico):
        ultimo = historico[-1]
        base = set()
        
        # Simetria Direta
        if ultimo in self.espelhos: base.add(self.espelhos[ultimo])
        
        # Gap/Repetição Temporal
        if len(historico) >= 4 and historico[-4] == ultimo: base.add(ultimo)
        
        if base: return {'base': base, 'forca': 50, 'estrategias': ['Viés Numérico']}
        return None

class EstrategiaSniperOriginal: # Mantida pois é a assinatura do Elite Master
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico):
        if len(historico) < 15: return None
        recentes = historico[-15:]
        duzias = Counter([self.roleta.get_setor(n) for n in recentes if n != 0])
        colunas = Counter([self.roleta.get_coluna(n) for n in recentes if n != 0])
        m_d = duzias.most_common(1)[0][0] if duzias else None
        m_c = colunas.most_common(1)[0][0] if colunas else None
        base = set()
        if m_d and m_c and duzias[m_d] >= 6:
            base.update(set(range((m_d-1)*12+1, m_d*12+1)).intersection(set(range(m_c, 37, 3))))
            return {'base': base, 'forca': 70, 'estrategias': ['Sniper Elite']}
        return None

# =============================
# BOT UNIFICADO (COM MOTORES LIMPOS)
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        # Motores Consolidados
        self.m_padroes = MotorPadroes(self.roleta)
        self.m_frequencia = MotorFrequencia()
        self.m_terminais = MotorTerminais()
        self.m_fisico = MotorFisico(self.roleta)
        self.m_atrasos = MotorAtrasos()
        self.m_multiplicadores = MotorMultiplicadores(self.roleta)
        self.m_frances = MotorFrances(self.roleta)
        self.m_vies = MotorVies()
        self.m_sniper = EstrategiaSniperOriginal(self.roleta)
        self.m_cor = EstrategiaTendenciaCor(self.roleta) # Reutilizando a original
        
        self.historico = []
        self.lucky = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.performance_motores = {}
        self._init_performance_motores()
        self._ultimo_timestamp = None

    def _init_performance_motores(self):
        nomes = ['Sniper','Padrões','Frequência','Terminais','Físico','Atrasos','Multiplicadores','Francês','Viés','Cor']
        for m in nomes:
            self.performance_motores[m] = {'acertos': 0, 'erros': 0, 'total': 0, 'historico': [], 'forca_media': 0, 'ultima_forca': 0}

    def atualizar(self, numero, timestamp=None, lucky_nums=None, lucky_mults=None):
        if timestamp and self._ultimo_timestamp == timestamp: return False
        self._ultimo_timestamp = timestamp
        self.historico.append(numero)
        self.lucky.append(lucky_nums if lucky_nums else [])
        if len(self.historico) > 200: self.historico = self.historico[-200:]; self.lucky = self.lucky[-200:]
        return True

    def atualizar_resultado(self, acerto):
        self.performance['historico'].append(1 if acerto else 0)
        if acerto: self.performance['acertos'] += 1
        else: self.performance['erros'] += 1

    def analisar_e_prever(self, top_n=13, motores_ativos=None, forca_minima=30):
        h = list(self.historico)
        if len(h) < 5: return None
        
        res = []
        # Mapeamento para manter compatibilidade com as checkboxes da UI antiga
        if motores_ativos.get('usar_sniper', True):
            r = self.m_sniper.analisar(h)
            if r: res.append(('Sniper', r))
            
        if motores_ativos.get('usar_mineracao', True) or motores_ativos.get('usar_sequencia', True):
            r = self.m_padroes.analisar(h)
            if r: res.append(('Padrões', r))

        if motores_ativos.get('usar_terminais', True) or motores_ativos.get('usar_loop_terminal', True):
            r = self.m_terminais.analisar(h)
            if r: res.append(('Terminais', r))

        if motores_ativos.get('usar_leque', True) or motores_ativos.get('usar_salto_curto', True):
            r = self.m_fisico.analisar(h)
            if r: res.append(('Físico', r))

        if motores_ativos.get('usar_quadrantes', True) or motores_ativos.get('usar_duzias_colunas', True):
            r = self.m_atrasos.analisar(h)
            if r: res.append(('Atrasos', r))

        if motores_ativos.get('usar_lightning_hunt', True) or motores_ativos.get('usar_sombra', True):
            r = self.m_multiplicadores.analisar(list(self.lucky))
            if r: res.append(('Multiplicadores', r))

        if motores_ativos.get('usar_ponte_setores', True) or motores_ativos.get('usar_momentum_setor', True):
            r = self.m_frances.analisar(h)
            if r: res.append(('Francês', r))

        if not res: return None
        
        # Peso inteligente: Números que aparecem em múltiplos motores ganham prioridade
        contagem = Counter()
        for _, r in res:
            peso = r['forca'] / 100
            for n in r['base']: contagem[n] += peso
            
        prioridade = [n for n, _ in contagem.most_common(top_n)]
        
        # Preenchimento de segurança se houver poucos números
        if len(prioridade) < 12:
            for n in self.roleta.get_vizinhos(h[-1], 2):
                if n not in prioridade: prioridade.append(n)
                if len(prioridade) >= 12: break

        motor_princ, maior_f = res[0][0], res[0][1]['forca']
        for m, r in res:
            if r['forca'] > maior_f: maior_f, motor_princ = r['forca'], m

        return {
            'nome': 'Elite Master Bot',
            'numeros_apostar': sorted(prioridade[:15]),
            'forca_real': int(sum(r[1]['forca'] for r in res)/len(res)),
            'motor': motor_princ,
            'estrategias_ativas': [m for m, _ in res[:3]],
            'qtd_motores': len(res)
        }

    # Funções de performance (MANTIDAS)
    def atualizar_performance_motor(self, motor, acerto, forca=0):
        if motor not in self.performance_motores: return
        p = self.performance_motores[motor]
        p['total'] += 1
        if acerto: p['acertos'] += 1
        else: p['erros'] += 1
        p['ultima_forca'] = forca

    def get_melhores_motores(self, top_n=5):
        ranking = []
        for nome, perf in self.performance_motores.items():
            if perf['total'] > 0:
                taxa = perf['acertos']/perf['total']
                ranking.append((nome, taxa, perf['acertos'], perf['total'], perf['forca_media']))
        return sorted(ranking, key=lambda x: x[1], reverse=True)[:top_n]

    def get_taxa_acerto(self):
        t = self.performance['acertos'] + self.performance['erros']
        return self.performance['acertos']/t if t > 0 else 0

    def get_total_tentativas(self): return self.performance['acertos'] + self.performance['erros']
    def zerar(self): self.historico = []; self.lucky = []; self.performance = {'acertos': 0, 'erros': 0, 'historico': []}; self._init_performance_motores()

# =============================
# ESTRATÉGIA COR (AUXILIAR MANTIDA)
# =============================
class EstrategiaTendenciaCor:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 6: return None
        cores = [self.roleta.get_cor(n) for n in h[-6:]]
        if len(set(cores)) == 1 and cores[0] != 'Verde':
            oposta = 'Vermelho' if cores[0] == 'Preto' else 'Preto'
            return {'base': self.roleta.vermelhos if oposta=='Vermelho' else self.roleta.pretos, 'forca': 50, 'estrategias': ['Reversão']}
        return None

# =============================
# SISTEMA PRINCIPAL (MANTIDO)
# =============================
class SistemaBot:
    def __init__(self):
        self.bot = RoletaBotUnificado()
        self.previsao_ativa = None
        self.acertos = 0; self.erros = 0
        self.rodadas_sem_entrada = 0
        self.ultima_entrada_rodada = -10
        self.estrategia_ativa_manual = False
        self.giros_restantes_espera = 0
        self.repeticoes_acerto_consecutivas = 0
        self.ultima_entrada_green = False
        self.ultima_entrada_numeros = []
        self.ultima_entrada_forca = 0
        self.ultima_entrada_motor = ""
        self.historico_desempenho = []

    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            n_real = numero_data['number']
            lucky = numero_data.get('luckyNumbers', [])
            ts = numero_data.get('timestamp', str(time.time()))
        else: n_real = numero_data; lucky = []; ts = str(time.time())
        
        if not self.bot.atualizar(n_real, ts, lucky): return
        
        self.rodadas_sem_entrada += 1
        if self.giros_restantes_espera > 0: self.giros_restantes_espera -= 1
        
        if self.previsao_ativa:
            acerto = n_real in self.previsao_ativa['numeros_apostar']
            self.bot.atualizar_resultado(acerto)
            self.bot.atualizar_performance_motor(self.previsao_ativa['motor'], acerto, self.previsao_ativa['forca_real'])
            
            if acerto:
                self.acertos += 1
                if st.session_state.get('repetir_acerto', True):
                    if self.repeticoes_acerto_consecutivas < st.session_state.get('max_repeticoes_acerto', 3):
                        self.repeticoes_acerto_consecutivas += 1
                        self.ultima_entrada_green = True
                        self.ultima_entrada_numeros = self.previsao_ativa['numeros_apostar']
                        self.ultima_entrada_forca = self.previsao_ativa['forca_real']
                        self.ultima_entrada_motor = self.previsao_ativa['motor']
                self.giros_restantes_espera = 0
            else:
                self.erros += 1
                self.repeticoes_acerto_consecutivas = 0
                self.ultima_entrada_green = False
                if st.session_state.get('repetir_entrada', True) and self.previsao_ativa['forca_real'] >= 45:
                    self.giros_restantes_espera = 1
                    self.ultima_entrada_numeros = self.previsao_ativa['numeros_apostar']
                    self.ultima_entrada_motor = self.previsao_ativa['motor']

            enviar_resultado_auto(n_real, acerto)
            self.historico_desempenho.append({'numero': n_real, 'acerto': acerto, 'motor': self.previsao_ativa['motor']})
            self.previsao_ativa = None
            self.ultima_entrada_rodada = len(self.bot.historico)
            self.rodadas_sem_entrada = 0
        
        if self.estrategia_ativa_manual: return
        
        # Lógica de Gatilho
        if len(self.bot.historico) >= 5:
            if len(self.bot.historico) - self.ultima_entrada_rodada >= st.session_state.get('intervalo_minimo_entradas', 0):
                if self.ultima_entrada_green:
                    self.previsao_ativa = {
                        'numeros_apostar': self.ultima_entrada_numeros,
                        'forca_real': self.ultima_entrada_forca,
                        'motor': self.ultima_entrada_motor,
                        'green': True, 'green_count': self.repeticoes_acerto_consecutivas
                    }
                    self.ultima_entrada_green = False
                    enviar_previsao_auto(self.previsao_ativa)
                elif self.giros_restantes_espera == 1:
                    self.previsao_ativa = {
                        'numeros_apostar': self.ultima_entrada_numeros,
                        'forca_real': 40, 'motor': self.ultima_entrada_motor, 'repeticao': True
                    }
                    enviar_previsao_auto(self.previsao_ativa)
                else:
                    motores = {
                        'usar_sniper': st.session_state.get('usar_sniper', True),
                        'usar_mineracao': st.session_state.get('usar_mineracao', True),
                        'usar_sequencia': st.session_state.get('usar_sequencia', True),
                        'usar_terminais': st.session_state.get('usar_terminais', True),
                        'usar_leque': st.session_state.get('usar_leque', True),
                        'usar_quadrantes': st.session_state.get('usar_quadrantes', True),
                        'usar_lightning_hunt': st.session_state.get('usar_lightning_hunt', True),
                        'usar_ponte_setores': st.session_state.get('usar_ponte_setores', True),
                        'usar_momentum_setor': st.session_state.get('usar_momentum_setor', True)
                    }
                    nova = self.bot.analisar_e_prever(st.session_state.get('top_n_apostas', 13), motores)
                    if nova:
                        self.previsao_ativa = nova
                        enviar_previsao_auto(nova)

    def zerar_estatisticas(self): self.acertos = 0; self.erros = 0; self.bot.zerar(); salvar_sessao()
    def get_status(self): return {'acertos': self.acertos, 'erros': self.erros, 'total': self.acertos + self.erros, 'rodadas_sem_entrada': self.rodadas_sem_entrada}

# =============================
# FUNÇÕES DE API E EXPORT (MANTIDAS)
# =============================
def fetch_latest_result():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=5)
        data = response.json()
        res = data.get("data", {}).get("result", {})
        num = res.get("outcome", {}).get("number")
        ts = data.get("data", {}).get("startedAt")
        lucky = [item.get('number') for item in res.get('luckyNumbersList', [])]
        return {"number": num, "timestamp": ts, "luckyNumbers": lucky}
    except: return None

def salvar_resultado_em_arquivo(hist):
    with open(HISTORICO_PATH, "w") as f: json.dump(hist, f, indent=2)

def exportar_historico(hist, formato='json'):
    if formato == 'json': return json.dumps(hist, indent=2)
    return "numero,timestamp\n" + "\n".join([f"{i['number']},{i['timestamp']}" for i in hist])

# =============================
# INTERFACE STREAMLIT (MANTIDA)
# =============================
st.set_page_config(page_title="Elite Master — Bot Unificado", layout="centered")
st.title("🎯 Bot Elite Master — Motores Consolidados")

if "sistema" not in st.session_state: st.session_state.sistema = SistemaBot()

# Carregamento de Sessão
dados = carregar_dados_persistidos()
if dados and not st.session_state.get('carregado'):
    s = st.session_state.sistema
    s.acertos, s.erros = dados.get('sistema_acertos', 0), dados.get('sistema_erros', 0)
    for n in dados.get('historico_numeros', []): s.bot.historico.append(n)
    st.session_state.historico = dados.get('historico', [])
    st.session_state.carregado = True

# Sidebar Configs
st.sidebar.title("⚙️ Painel de Controle")
st.session_state.top_n_apostas = st.sidebar.slider("🔢 Qtd Números", 10, 15, 13)
st.session_state.max_repeticoes_acerto = st.sidebar.slider("🟢 Repetir Green", 1, 5, 3)

with st.sidebar.expander("🤖 Motores Ativos", expanded=True):
    st.session_state.usar_sniper = st.checkbox("🎯 Sniper Original", True)
    st.session_state.usar_mineracao = st.checkbox("⛓️ Cadeias/Markov", True)
    st.session_state.usar_terminais = st.checkbox("🔢 Terminais Elite", True)
    st.session_state.usar_leque = st.checkbox("🪭 Wheel Physics", True)
    st.session_state.usar_quadrantes = st.checkbox("📐 Atrasos (Q/D/C)", True)
    st.session_state.usar_lightning_hunt = st.checkbox("⚡ Multiplicadores", True)
    st.session_state.usar_ponte_setores = st.checkbox("🌉 Setores Franceses", True)

if st.sidebar.button("🗑️ Limpar Tudo"):
    limpar_sessao()

# App Principal
st_autorefresh(interval=5000, key="refresh")

res_api = fetch_latest_result()
if res_api and (not st.session_state.get('historico') or res_api['timestamp'] != st.session_state.historico[-1]['timestamp']):
    st.session_state.historico.append(res_api)
    st.session_state.sistema.processar_novo_numero(res_api)
    salvar_sessao()

# Display
status = st.session_state.sistema.get_status()
c1, c2, c3 = st.columns(3)
c1.metric("🟢 Acertos", status['acertos'])
c2.metric("🔴 Erros", status['erros'])
c3.metric("⏳ Sem Entrada", status['rodadas_sem_entrada'])

st.subheader("🎯 Previsão Atual")
sis = st.session_state.sistema
if sis.previsao_ativa:
    p = sis.previsao_ativa
    cor = "green" if p.get('green') else "orange"
    st.markdown(f"### <span style='color:{cor}'>{p['motor']} | {p.get('forca_real', 50)}%</span>", unsafe_allow_html=True)
    st.write(f"**Apostar em {len(p['numeros_apostar'])} números:**")
    st.code(", ".join(map(str, p['numeros_apostar'])))
else:
    st.info("Aguardando gatilho dos motores...")

st.subheader("🔁 Últimos Sorteios")
if st.session_state.get('historico'):
    ultimos = [str(i['number']) for i in st.session_state.historico[-12:]]
    st.write(" ← ".join(ultimos[::-1]))

# Download
if st.button("📥 Exportar Histórico"):
    st.download_button("Baixar JSON", exportar_historico(st.session_state.historico), "historico.json")

salvar_sessao()
