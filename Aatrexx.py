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
            'historico_lucky': list(sis.historico_lucky),
            'historico_mults': list(sis.historico_mults),
            'entrada_ativa': sis.entrada_ativa,
            'sistema_acertos': sis.acertos,
            'sistema_erros': sis.erros,
            'estado_inversao': sis.estado_inversao,
            'modo_duzias_colunas': st.session_state.get('modo_duzias_colunas', False),
            'sensibilidade_pingpong': st.session_state.get('sensibilidade_pingpong', 2),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'max_n_apostas': st.session_state.get('max_n_apostas', 7),
            'min_n_apostas': st.session_state.get('min_n_apostas', 4),
            'forca_minima_entrada': st.session_state.get('forca_minima_entrada', 55),
            'limitar_numeros_altos': st.session_state.get('limitar_numeros_altos', True),
            'evitar_zero': st.session_state.get('evitar_zero', True),
            'max_gatilhos': st.session_state.get('max_gatilhos', 2),
            'modo_inversao_auto': st.session_state.get('modo_inversao_auto', False),
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

# =============================
# NOTIFICAÇÕES
# =============================
def enviar_previsao_auto(previsao):
    try:
        numeros = sorted(previsao['numeros_apostar'])
        forca = previsao.get('forca_real', 0)
        motor = previsao.get('motor', '')
        gatilho = previsao.get('gatilho', '')
        invertido = previsao.get('invertido', False)
        
        if invertido:
            emoji = "🔄"
        elif forca >= 65:
            emoji = "🔥"
        elif forca >= 55:
            emoji = "🎯"
        else:
            emoji = "⚠️"
        
        st.toast(f"{emoji} {motor} - {forca}%")
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            tag = "[INVERTIDO]" if invertido else ""
            enviar_telegram(f"🔔 {tag} F{forca}% | {motor}\n{gatilho}\n🔢 " + " ".join(map(str, numeros)))
        
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
# ROLETA BASE
# =============================
class RoletaBase:
    def __init__(self):
        self.race = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        self.vermelhos = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        self.pretos = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
        self.espelhos = {0:0, 12:21, 21:12, 13:31, 31:13, 23:32, 32:23, 1:10, 10:1, 2:20, 20:2, 3:30, 30:3, 4:19, 19:4, 5:24, 24:5, 6:27, 27:6, 7:28, 28:7, 8:23, 23:8, 9:22, 22:9, 11:36, 36:11, 14:31, 31:14, 15:32, 32:15, 16:33, 33:16, 17:34, 34:17, 18:29, 29:18, 25:26, 26:25}
        self.voisins = {22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25}
        self.tiers = {27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33}
        self.orphelins = {1, 20, 14, 31, 9, 17, 34, 6}
        self.primos = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}
        self.baixos = set(range(1, 19))
        self.altos = set(range(19, 37))
        self.numeros_problematicos = {0, 32, 33, 34, 35}
        self.max_problematicos = 2
        
        # 🎯 CONJUNTOS REAIS DE CADA COLUNA (matemática pura da roleta)
        self.coluna1 = set(range(1, 37, 3))  # 1,4,7,10,13,16,19,22,25,28,31,34
        self.coluna2 = set(range(2, 37, 3))  # 2,5,8,11,14,17,20,23,26,29,32,35
        self.coluna3 = set(range(3, 37, 3))  # 3,6,9,12,15,18,21,24,27,30,33,36
        
        # 🎯 CONJUNTOS REAIS DE CADA DÚZIA
        self.duzia1 = set(range(1, 13))   # 1-12
        self.duzia2 = set(range(13, 25))  # 13-24
        self.duzia3 = set(range(25, 37))  # 25-36
    
    def get_vizinhos(self, n, r=2):
        if n not in self.race:
            return []
        i = self.race.index(n)
        return [self.race[(i + j) % 37] for j in range(-r, r + 1)]
    
    def get_setor_cilindro(self, n):
        if n in self.voisins:
            return "Voisins"
        if n in self.tiers:
            return "Tiers"
        if n in self.orphelins:
            return "Orphelins"
        return "Zero"
    
    def get_coluna(self, n):
        """Retorna a coluna real: 1, 2 ou 3 baseado nos conjuntos reais"""
        if n in self.coluna1: return 1
        if n in self.coluna2: return 2
        if n in self.coluna3: return 3
        return 0
    
    def get_duzia(self, n):
        """Retorna a dúzia real: 1 (1-12), 2 (13-24), 3 (25-36)"""
        if n in self.duzia1: return 1
        if n in self.duzia2: return 2
        if n in self.duzia3: return 3
        return 0
    
    def get_conjunto_coluna(self, coluna_num):
        """Retorna o conjunto completo de números de uma coluna"""
        if coluna_num == 1: return self.coluna1
        if coluna_num == 2: return self.coluna2
        if coluna_num == 3: return self.coluna3
        return set()
    
    def get_conjunto_duzia(self, duzia_num):
        """Retorna o conjunto completo de números de uma dúzia"""
        if duzia_num == 1: return self.duzia1
        if duzia_num == 2: return self.duzia2
        if duzia_num == 3: return self.duzia3
        return set()
    
    def verificar_acerto_coluna(self, numero_sorteado, coluna_prevista):
        """✅ Verifica se o número sorteado pertence à coluna prevista"""
        conjunto_coluna = self.get_conjunto_coluna(coluna_prevista)
        return numero_sorteado in conjunto_coluna
    
    def verificar_acerto_duzia(self, numero_sorteado, duzia_prevista):
        """✅ Verifica se o número sorteado pertence à dúzia prevista"""
        conjunto_duzia = self.get_conjunto_duzia(duzia_prevista)
        return numero_sorteado in conjunto_duzia
    
    def sao_vizinhos_fisicos(self, a, b, d=1):
        if a not in self.race or b not in self.race:
            return False
        ia, ib = self.race.index(a), self.race.index(b)
        diff = abs(ia - ib)
        return diff <= d or diff >= 37 - d
    
    def get_setor_oposto(self, setor):
        if setor == "Voisins":
            return "Orphelins"
        elif setor == "Orphelins":
            return "Voisins"
        elif setor == "Tiers":
            return "Tiers"
        return None

# =============================
# FUNÇÕES DE MAPEAMENTO REAL
# =============================
def get_coluna_real(n):
    """Retorna a coluna real: 1, 2 ou 3 baseado nos conjuntos reais"""
    if n == 0: return 0
    if n in {1,4,7,10,13,16,19,22,25,28,31,34}: return 1
    if n in {2,5,8,11,14,17,20,23,26,29,32,35}: return 2
    if n in {3,6,9,12,15,18,21,24,27,30,33,36}: return 3
    return 0

def get_duzia_real(n):
    """Retorna a dúzia real: 1-12=1, 13-24=2, 25-36=3"""
    if n == 0: return 0
    return (n - 1) // 12 + 1

def get_setor_roda(n):
    """Retorna o setor físico do cilindro"""
    voisins = [22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25]
    tiers = [27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33]
    orphelins = [1, 20, 14, 31, 9, 17, 34]
    if n in voisins: return "Voisins (Vizinhos do Zero)"
    if n in tiers: return "Tiers (Terço)"
    if n in orphelins: return "Orphelins (Órfãos)"
    return "Zero"

# =============================
# MOTOR DE CONFLUÊNCIA
# =============================
class MotorConfluenciaDuziasColunas:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar_confluencia(self, historico_numeros, sensibilidade_pingpong=2):
        janela = 20
        if len(historico_numeros) < janela:
            return None
        
        validos = [n for n in historico_numeros[-janela:] if n != 0]
        if len(validos) < 10:
            return None
        
        colunas = [get_coluna_real(n) for n in validos]
        duzias = [get_duzia_real(n) for n in validos]
        terminais = [n % 10 for n in validos]
        setores = [get_setor_roda(n) for n in validos]
        
        score_colunas = {1: 0, 2: 0, 3: 0}
        
        # ESTRATÉGIA 1: Interseção (+1)
        col_quente = Counter(colunas).most_common(1)[0][0]
        duz_quente = Counter(duzias).most_common(1)[0][0]
        score_colunas[col_quente] += 1
        
        # ESTRATÉGIA 2: Terminais (+2 PESO DUPLO)
        top_terminais = [t[0] for t in Counter(terminais).most_common(3)]
        cols_dos_terminais = [get_coluna_real(t) if t != 0 else 0 for t in top_terminais]
        if cols_dos_terminais and any(c != 0 for c in cols_dos_terminais):
            col_terminal_dominante = Counter([c for c in cols_dos_terminais if c != 0]).most_common(1)[0][0]
            score_colunas[col_terminal_dominante] += 2
        
        # ESTRATÉGIA 3: Cilindro (+1)
        setor_quente = Counter(setores).most_common(1)[0][0]
        num_do_setor_quente = [n for n in validos if get_setor_roda(n) == setor_quente]
        cols_do_setor = [get_coluna_real(n) for n in num_do_setor_quente]
        if cols_do_setor:
            col_dominante_setor = Counter(cols_do_setor).most_common(1)[0][0]
            if col_dominante_setor != 0:
                score_colunas[col_dominante_setor] += 1
        
        # ESTRATÉGIA 4: Ping-Pong (-1)
        mapa_sensibilidade = {1: 3, 2: 4, 3: 5, 4: 6}
        giros_verificar = mapa_sensibilidade.get(sensibilidade_pingpong, 4)
        
        if len(colunas) >= giros_verificar:
            ultimas_cols = colunas[-giros_verificar:]
            tem_repeticao = any(ultimas_cols[i] == ultimas_cols[i+1] for i in range(len(ultimas_cols)-1))
            if not tem_repeticao:
                ultima_col = colunas[-1]
                score_colunas[ultima_col] -= 1
        
        coluna_vencedora = max(score_colunas, key=score_colunas.get)
        pontos = score_colunas[coluna_vencedora]
        
        # Números da coluna vencedora
        numeros_coluna = self.roleta.get_conjunto_coluna(coluna_vencedora)
        numeros_recentes = set(validos[-5:])
        numeros_quentes = numeros_coluna.intersection(numeros_recentes)
        numeros_frios = numeros_coluna - numeros_recentes
        
        numeros_apostar = list(numeros_quentes)[:4] + list(numeros_frios)[:3]
        if len(numeros_apostar) < 6:
            restantes = [n for n in numeros_coluna if n not in numeros_apostar]
            numeros_apostar.extend(restantes[:6 - len(numeros_apostar)])
        
        if pontos >= 3: forca = 80; qualidade = "EXCELENTE"; mensagem = "ENTRADA FORTE"
        elif pontos == 2: forca = 65; qualidade = "BOA"; mensagem = "ENTRADA MODERADA"
        elif pontos == 1: forca = 50; qualidade = "REGULAR"; mensagem = "ENTRADA FRACA"
        else: forca = 30; qualidade = "RUIM"; mensagem = "SEM PADRÃO CLARO"
        
        return {
            'coluna_vencedora': coluna_vencedora,
            'pontos': pontos,
            'forca': forca,
            'qualidade': qualidade,
            'mensagem': mensagem,
            'numeros_apostar': sorted(numeros_apostar[:7]),
            'score_colunas': score_colunas
        }

# =============================
# BOT UNIFICADO
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        # ... (todas as 35 estratégias mantidas)
        self.repeticao = EstrategiaRepeticao(self.roleta)
        self.motor_confluencia = MotorConfluenciaDuziasColunas(self.roleta)
        self.historico = []
        self.lucky = []
        self.mults = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
    
    def atualizar(self, n, lucky_nums=None, lucky_mults=None):
        if isinstance(n, dict): n = n.get('number', 0)
        self.historico.append(int(n))
        self.lucky.append(lucky_nums if lucky_nums else [])
        self.mults.append(lucky_mults if lucky_mults else {})
        if len(self.historico) > 200: self.historico = self.historico[-200:]
        if len(self.lucky) > 200: self.lucky = self.lucky[-200:]
        if len(self.mults) > 200: self.mults = self.mults[-200:]
    
    def gerar_entrada(self, motores=None, forcar_inversao=False, entradas_hist=None):
        if st.session_state.get('modo_duzias_colunas', False):
            sensibilidade = st.session_state.get('sensibilidade_pingpong', 2)
            confluencia = self.motor_confluencia.analisar_confluencia(list(self.historico), sensibilidade)
            if confluencia and confluencia['pontos'] >= 1:
                return {
                    'numeros_apostar': confluencia['numeros_apostar'],
                    'forca_real': confluencia['forca'],
                    'motor': f"Confluência Col{confluencia['coluna_vencedora']}",
                    'estrategias_ativas': [f"Score: {confluencia['pontos']}/4"],
                    'qtd_motores': confluencia['pontos'],
                    'qualidade': confluencia['qualidade'],
                    'gatilho': confluencia['mensagem'],
                    'invertido': False,
                    'coluna_prevista': confluencia['coluna_vencedora']  # 🎯 Guarda a coluna prevista
                }
            return None
        
        # Modo padrão com 35 estratégias
        if motores is None:
            motores = {k: True for k in ['repeticao']}
        
        # Lógica simplificada para o exemplo
        if len(self.historico) >= 2:
            r = self.repeticao.analisar(list(self.historico))
            if r and len(r.get('base', set())) >= 1 and r['forca'] >= st.session_state.get('forca_minima_entrada', 55):
                entrada = {
                    'numeros_apostar': sorted(list(r['base'])[:7]),
                    'forca_real': r['forca'],
                    'motor': 'Repetição',
                    'estrategias_ativas': r.get('estrategias', []),
                    'qtd_motores': 1,
                    'qualidade': 'BOA',
                    'gatilho': r.get('gatilho', ''),
                    'invertido': False,
                    'coluna_prevista': None
                }
                if forcar_inversao: entrada = self._inverter_entrada(entrada)
                return entrada
        return None
    
    def _inverter_entrada(self, entrada):
        numeros_originais = set(entrada['numeros_apostar'])
        todos_numeros = set(range(37))
        numeros_invertidos = list(todos_numeros - numeros_originais)
        qtd = len(entrada['numeros_apostar'])
        nao_problematicos = [n for n in numeros_invertidos if n not in {0, 32, 33, 34, 35}]
        problematicos = [n for n in numeros_invertidos if n in {0, 32, 33, 34, 35}]
        random.shuffle(nao_problematicos); random.shuffle(problematicos)
        final = nao_problematicos[:qtd]
        if len(final) < qtd: final.extend(problematicos[:qtd - len(final)])
        entrada['numeros_apostar'] = sorted(final[:qtd])
        entrada['motor'] = f"🔄 {entrada['motor']} (Inv)"
        entrada['invertido'] = True
        return entrada

# =============================
# SISTEMA PRINCIPAL (COM VERIFICAÇÃO POR CONJUNTO)
# =============================
class SistemaBot:
    def __init__(self):
        self.bot = RoletaBotUnificado()
        self.historico_numeros = deque(maxlen=200)
        self.historico_lucky = deque(maxlen=100)
        self.historico_mults = deque(maxlen=100)
        self.entrada_ativa = None
        self.historico_entradas = []
        self.acertos = 0
        self.erros = 0
        self.estado_inversao = False
    
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data['number']
            lucky = numero_data.get('luckyNumbers', [])
            lucky_mults = numero_data.get('luckyMultipliers', {})
            mult = lucky_mults.get(nr) if nr in lucky else None
            is_lucky = nr in lucky
        else:
            nr = int(numero_data); lucky, lucky_mults, mult, is_lucky = [], {}, None, False
        
        self.bot.atualizar(nr, lucky, lucky_mults)
        self.historico_numeros.append(nr)
        self.historico_lucky.append(lucky)
        self.historico_mults.append(lucky_mults)
        
        if self.entrada_ativa:
            # 🎯 VERIFICAÇÃO DE ACERTO POR CONJUNTO (COLUNA OU DÚZIA)
            coluna_prevista = self.entrada_ativa.get('coluna_prevista', None)
            
            if coluna_prevista is not None:
                # Se tem coluna prevista (modo confluência), verifica pelo CONJUNTO
                acerto = self.bot.roleta.verificar_acerto_coluna(nr, coluna_prevista)
            else:
                # Modo padrão: verifica se o número está na lista de apostas
                acerto = nr in self.entrada_ativa.get('numeros_apostar', [])
            
            if acerto:
                self.acertos += 1
                self.bot.performance['acertos'] += 1
            else:
                self.erros += 1
                self.bot.performance['erros'] += 1
            self.bot.performance['historico'].append(1 if acerto else 0)
            
            entrada_info = {
                'rodada': len(self.historico_numeros)-1,
                'hora': datetime.now().strftime('%H:%M:%S'),
                'numeros': self.entrada_ativa.get('numeros_apostar', []),
                'resultado': nr,
                'acerto': acerto,
                'forca': self.entrada_ativa.get('forca_real', 0),
                'motor': self.entrada_ativa.get('motor', ''),
                'gatilho': self.entrada_ativa.get('gatilho', ''),
                'estrategias': self.entrada_ativa.get('estrategias_ativas', []),
                'qualidade': self.entrada_ativa.get('qualidade', ''),
                'lucky': is_lucky,
                'multiplicador': mult,
                'invertido': self.entrada_ativa.get('invertido', False),
                'coluna_prevista': coluna_prevista,
                'tipo_verificacao': 'CONJUNTO' if coluna_prevista else 'NUMEROS'
            }
            self.historico_entradas.append(entrada_info)
            if len(self.historico_entradas) > 50:
                self.historico_entradas = self.historico_entradas[-50:]
            
            if st.session_state.get('modo_inversao_auto', False):
                if not acerto:
                    self.estado_inversao = not self.estado_inversao
            
            enviar_resultado_auto(nr, acerto, is_lucky)
            self.entrada_ativa = None
        
        # Gera nova entrada
        mot = {}
        forcar_inversao = st.session_state.get('modo_inversao_auto', False) and self.estado_inversao
        self.entrada_ativa = self.bot.gerar_entrada(mot, forcar_inversao, list(self.historico_entradas))
        if self.entrada_ativa:
            enviar_previsao_auto(self.entrada_ativa)
    
    def zerar(self):
        self.acertos = 0; self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear(); self.historico_lucky.clear(); self.historico_mults.clear()
        self.entrada_ativa = None; self.estado_inversao = False
        self.bot.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.bot.historico = []; self.bot.lucky = []; self.bot.mults = []
        salvar_sessao()

# =============================
# CLASSES DE ESTRATÉGIA (MANTIDAS - APENAS REPETIÇÃO COMO EXEMPLO)
# =============================
class EstrategiaRepeticao:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, h):
        if len(h) < 2: return None
        u, p = h[-1], h[-2]
        if u != p: return None
        b = set([u])
        b.update(self.roleta.get_vizinhos(u, 1)[:3])
        return {'base': b, 'forca': 80, 'estrategias': [f'Repetição {u}'], 'gatilho': f'Repetição {u}'}

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
        logging.warning(f"Erro ao buscar API da Roleta: {e}")
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
st.set_page_config(page_title="🎯 Roleta Bot Pro v23 - Verificação por Conjunto", layout="centered")
st.title("🎯 Roleta Bot Pro v23 - Elite Master")

if "sistema" not in st.session_state: st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    if not st.session_state.get('historico'): st.session_state.historico = dados.get('historico', [])
    sis = st.session_state.sistema
    sis.bot = RoletaBotUnificado()
    sis.historico_numeros.clear(); sis.historico_lucky.clear(); sis.historico_mults.clear()
    numeros = dados.get('historico_numeros', [])
    lucky = dados.get('historico_lucky', [])
    mults = dados.get('historico_mults', [])
    for i in range(len(numeros)):
        n = numeros[i]; l = lucky[i] if i < len(lucky) else []; m = mults[i] if i < len(mults) else {}
        sis.bot.atualizar(n, l, m)
        sis.historico_numeros.append(n); sis.historico_lucky.append(l); sis.historico_mults.append(m)
    sis.acertos = dados.get('sistema_acertos', 0); sis.erros = dados.get('sistema_erros', 0)
    sis.estado_inversao = dados.get('estado_inversao', False)
    sis.entrada_ativa = dados.get('entrada_ativa', None)
    if os.path.exists(PERFORMANCE_PATH):
        try:
            with open(PERFORMANCE_PATH, 'r') as f:
                p = json.load(f)
                sis.bot.performance = {'acertos': p.get('acertos', 0), 'erros': p.get('erros', 0), 'historico': p.get('historico', [])}
        except: pass
    if os.path.exists(ENTRADAS_PATH):
        try:
            with open(ENTRADAS_PATH, 'r') as f: sis.historico_entradas = json.load(f)
        except: pass

defaults = {
    'modo_automatico': True, 'forca_minima_entrada': 55, 'max_n_apostas': 7,
    'modo_inversao_auto': False, 'modo_duzias_colunas': False, 'sensibilidade_pingpong': 2
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
    st.subheader("⚙️ Config")
    st.markdown("---")
    st.markdown("### 📐 MODO DE OPERAÇÃO")
    st.session_state.modo_duzias_colunas = st.checkbox(
        "🎯 ATIVAR MODO CONFLUÊNCIA",
        value=st.session_state.modo_duzias_colunas,
        help="Verificação por CONJUNTO: acerta se o número cair na coluna prevista"
    )
    
    if st.session_state.modo_duzias_colunas:
        st.success("✅ **VERIFICAÇÃO POR CONJUNTO ATIVA**")
        st.info("""
        🎯 **Como funciona:**
        Se o motor prevê **Coluna 1** e sai **7**:
        - 7 pertence à Coluna 1 → ✅ GREEN
        
        Se o motor prevê **Coluna 1** e sai **8**:
        - 8 pertence à Coluna 2 → ❌ RED
        """)
        
        st.session_state.sensibilidade_pingpong = st.select_slider(
            "🛡️ Sensibilidade Ping-Pong",
            options=[1, 2, 3, 4],
            value=st.session_state.sensibilidade_pingpong
        )
    else:
        st.info("📊 Modo padrão: verificação por números exatos")
    
    st.session_state.forca_minima_entrada = st.slider("⚡ Força Mínima", 45, 65, st.session_state.forca_minima_entrada, 5)
    
    c1, c2 = st.columns(2)
    c1.button("💾 Salvar", on_click=lambda: [salvar_resultado_em_arquivo(st.session_state.historico), salvar_sessao(), st.success("✅")], use_container_width=True)
    c2.button("🗑️ Zerar", on_click=lambda: st.session_state.sistema.zerar() or st.rerun(), use_container_width=True)

# =============================
# CONTEÚDO PRINCIPAL
# =============================
st.subheader("✍️ Inserir Números")
c1, c2 = st.columns([4, 1])
with c1:
    entrada = st.text_input("Números (0-36):", placeholder="Ex: 12 21 14", key="entrada")
with c2:
    if st.button("➕", use_container_width=True) and entrada:
        try:
            nums = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
            for n in nums:
                item = {"number": n, "timestamp": f"m{len(st.session_state.historico)}", "luckyNumbers": [], "luckyMultipliers": {}}
                st.session_state.historico.append(item)
                st.session_state.sistema.processar_novo_numero(item)
            salvar_resultado_em_arquivo(st.session_state.historico); salvar_sessao()
            st.success(f"{len(nums)} adicionados!"); st.rerun()
        except: pass

st_autorefresh(interval=3000, key="refresh")

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
        salvar_resultado_em_arquivo(st.session_state.historico); salvar_sessao()

st.subheader("🔁 Últimos Números")
if st.session_state.historico:
    ultimos = st.session_state.historico[-10:]
    fmt = []
    for item in ultimos:
        n = item['number'] if isinstance(item, dict) else item
        if isinstance(item, dict) and n in item.get('luckyNumbers', []):
            mult = item.get('luckyMultipliers', {}).get(n, '')
            fmt.append(f"⚡**{n}**({mult}x)" if mult else f"⚡**{n}**")
        else: fmt.append(str(n))
    st.write(" | ".join(fmt))

# =============================
# MÉTRICAS
# =============================
sis = st.session_state.sistema
st.subheader("📊 Status")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("🟢 Acertos", sis.acertos)
c2.metric("🔴 Erros", sis.erros)
tx = sis.acertos/(sis.acertos+sis.erros)*100 if (sis.acertos+sis.erros) > 0 else 0
c3.metric("🎯 Win Rate", f"{tx:.1f}%")
c4.metric("📊 Total", sis.acertos + sis.erros)
c5.metric("🔄 Estado", "Inv" if sis.estado_inversao else "Normal")

# =============================
# PAINEL DE PREVISÃO ATIVA
# =============================
if sis.entrada_ativa:
    st.markdown("---")
    ent = sis.entrada_ativa
    
    with st.expander(f"🎰 ENTRADA ATIVA: {ent['motor']} ({ent['forca_real']}%)", expanded=True):
        col_info, col_nums = st.columns([1, 2])
        
        with col_info:
            st.write(f"**Qualidade:** {ent['qualidade']}")
            st.write(f"**Gatilho:** {ent['gatilho']}")
            if ent.get('coluna_prevista'):
                conjunto = sis.bot.roleta.get_conjunto_coluna(ent['coluna_prevista'])
                st.info(f"🎯 **Coluna Prevista: {ent['coluna_prevista']}**\n\nConjunto: {sorted(conjunto)}")
                st.caption("✅ GREEN se o número sorteado estiver neste conjunto")
            if ent.get('invertido'): st.warning("⚠️ MODO INVERTIDO")
        
        with col_nums:
            st.write("**Números Sugeridos:**")
            nums = ent['numeros_apostar']
            cols = st.columns(7)
            for i, n in enumerate(nums):
                cols[i % 7].button(str(n), key=f"bet_{n}_{i}", use_container_width=True)
        
        st.progress(ent['forca_real'] / 100)

# =============================
# HISTÓRICO DE ENTRADAS
# =============================
if sis.historico_entradas:
    with st.expander("📝 Histórico de Sinais", expanded=False):
        for e in reversed(sis.historico_entradas):
            res = "✅" if e['acerto'] else "❌"
            inv = "🔄" if e.get('invertido') else ""
            tipo = e.get('tipo_verificacao', 'NUMEROS')
            col_prev = e.get('coluna_prevista', None)
            
            if col_prev:
                st.write(f"{res} {inv} | **Giro:** {e['resultado']} | **Coluna {col_prev}** | **Motor:** {e['motor']} | **Verificação:** {tipo}")
            else:
                st.write(f"{res} {inv} | **Giro:** {e['resultado']} | **Motor:** {e['motor']} | **Força:** {e['forca']}%")

# =============================
# DOWNLOAD
# =============================
with st.expander("📥 Download", expanded=False):
    c1, c2, c3 = st.columns(3)
    c1.download_button("JSON", exportar_historico(st.session_state.historico, 'json'), "historico.json")
    c2.download_button("CSV", exportar_historico(st.session_state.historico, 'csv'), "historico.csv")
    c3.download_button("Entradas", json.dumps(sis.historico_entradas, indent=2), "entradas.json")

st.markdown("---")
st.caption(f"🤖 Bot Operacional v23 | Verificação por Conjunto | {datetime.now().strftime('%H:%M:%S')}")

salvar_sessao()
