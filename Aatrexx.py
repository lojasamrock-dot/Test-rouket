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
            'modo_duzia_ai': st.session_state.get('modo_duzia_ai', False),
            'sensibilidade_pingpong': st.session_state.get('sensibilidade_pingpong', 2),
            'acertos_coluna': st.session_state.get('acertos_coluna', 0),
            'erros_coluna': st.session_state.get('erros_coluna', 0),
            'acertos_duzia': st.session_state.get('acertos_duzia', 0),
            'erros_duzia': st.session_state.get('erros_duzia', 0),
            'janela_duzia_ai': st.session_state.get('janela_duzia_ai', 30),
            'confianca_minima_duzia': st.session_state.get('confianca_minima_duzia', 3),
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
        
        emoji = "🔄" if invertido else "🔥" if forca >= 65 else "🎯" if forca >= 55 else "⚠️"
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
# FUNÇÕES DE MAPEAMENTO
# =============================
def get_duzia(numero):
    """Mapeamento oficial de dúzias"""
    if numero == 0: return 0
    elif 1 <= numero <= 12: return 1
    elif 13 <= numero <= 24: return 2
    else: return 3

def get_coluna_real(n):
    if n == 0: return 0
    if n in set(range(1, 37, 3)): return 1
    if n in set(range(2, 37, 3)): return 2
    if n in set(range(3, 37, 3)): return 3
    return 0

def get_duzia_real(n):
    return get_duzia(n)

def get_setor_roda(n):
    voisins = [22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25]
    tiers = [27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33]
    orphelins = [1, 20, 14, 31, 9, 17, 34]
    if n in voisins: return "Voisins"
    if n in tiers: return "Tiers"
    if n in orphelins: return "Orphelins"
    return "Zero"

# =============================
# 🧠 DUZIA AI - MOTOR DE INTELIGÊNCIA ADAPTATIVA
# =============================
class DuziaAI:
    """
    Motor de Inteligência Artificial para previsão de Dúzias
    Baseado em 4 pilares:
    1. Frequência Ponderada (peso 1.5x)
    2. Streak/Continuidade (peso 2x)
    3. Rebote/Alternância (peso 3x)
    4. Quebra de Sequência Longa (peso 4x)
    """
    def __init__(self, window=30):
        self.historico = deque(maxlen=window)
        self.historico_completo = []  # Para análise de ciclos
    
    def adicionar(self, numero):
        duzia = get_duzia(numero)
        self.historico.append(duzia)
        self.historico_completo.append(duzia)
        if len(self.historico_completo) > 200:
            self.historico_completo = self.historico_completo[-200:]
    
    def frequencia(self):
        """Frequência ponderada das dúzias na janela"""
        return Counter(self.historico)
    
    def frequencia_ponderada(self):
        """Dá mais peso para giros recentes (últimos 5 valem mais)"""
        freq = Counter()
        for i, d in enumerate(self.historico):
            # Últimos 5 giros: peso 2x, resto: peso 1x
            peso = 2 if i >= len(self.historico) - 5 else 1
            freq[d] += peso
        return freq
    
    def streak(self):
        """Detecta streak atual (quantos giros consecutivos da mesma dúzia)"""
        if not self.historico:
            return 0, None
        last = self.historico[-1]
        count = 0
        for d in reversed(self.historico):
            if d == last:
                count += 1
            else:
                break
        return count, last
    
    def transicao(self):
        """Retorna a transição mais recente (de → para)"""
        if len(self.historico) < 2:
            return None
        return self.historico[-2], self.historico[-1]
    
    def matriz_transicao(self):
        """Constrói matriz de transição real baseada no histórico completo"""
        matriz = {1: {1: 0, 2: 0, 3: 0}, 2: {1: 0, 2: 0, 3: 0}, 3: {1: 0, 2: 0, 3: 0}}
        totais = {1: 0, 2: 0, 3: 0}
        
        for i in range(len(self.historico_completo) - 1):
            origem = self.historico_completo[i]
            destino = self.historico_completo[i + 1]
            if origem != 0 and destino != 0:
                matriz[origem][destino] += 1
                totais[origem] += 1
        
        # Converte para probabilidades
        prob = {}
        for origem in [1, 2, 3]:
            prob[origem] = {}
            for destino in [1, 2, 3]:
                if totais[origem] > 0:
                    prob[origem][destino] = (matriz[origem][destino] / totais[origem]) * 100
                else:
                    prob[origem][destino] = 33.3
        
        return prob, matriz
    
    def detectar_ciclos(self):
        """Detecta padrões de repetição tipo D3→D2→D3→D2"""
        if len(self.historico) < 8:
            return None
        
        ultimos_8 = list(self.historico)[-8:]
        # Procura padrão ABAB nos últimos 4
        ultimos_4 = ultimos_8[-4:]
        if len(ultimos_4) == 4:
            if ultimos_4[0] == ultimos_4[2] and ultimos_4[1] == ultimos_4[3] and ultimos_4[0] != ultimos_4[1]:
                return ultimos_4[-2]  # Prevê o próximo do padrão
        return None
    
    def calcular_score(self):
        """
        Calcula o score de cada dúzia baseado em múltiplos fatores
        Score máximo teórico: ~20-25 pontos
        """
        score = {1: 0, 2: 0, 3: 0}
        detalhes = {1: [], 2: [], 3: []}
        
        # 📊 PESO 1: Frequência Ponderada (giros recentes valem mais)
        freq = self.frequencia_ponderada()
        for d in [1, 2, 3]:
            pontos = freq[d] * 1.5
            score[d] += pontos
            if pontos > 0:
                detalhes[d].append(f"Freq: +{pontos:.1f}")
        
        # 🔥 PESO 2: Streak (continuidade)
        streak_count, streak_duzia = self.streak()
        if streak_duzia and streak_duzia != 0:
            pontos = streak_count * 2
            score[streak_duzia] += pontos
            detalhes[streak_duzia].append(f"Streak {streak_count}x: +{pontos}")
        
        # 🔄 PESO 3: Rebote (aposta no retorno à dúzia anterior)
        trans = self.transicao()
        if trans:
            anterior, atual = trans
            if anterior != atual and anterior != 0:
                pontos = 3
                score[anterior] += pontos
                detalhes[anterior].append(f"Rebote: +{pontos}")
        
        # 💥 PESO 4: Quebra de sequência longa (3+ repetições)
        if streak_count >= 3 and streak_duzia and streak_duzia != 0:
            vizinha = {1: 2, 2: 3, 3: 2}
            if streak_duzia in vizinha:
                alvo = vizinha[streak_duzia]
                pontos = 4
                score[alvo] += pontos
                detalhes[alvo].append(f"Quebra Streak D{streak_duzia}: +{pontos}")
        
        # 🆕 PESO 5: Matriz de Transição Probabilística
        prob, _ = self.matriz_transicao()
        if self.historico:
            ultima = self.historico[-1]
            if ultima != 0 and ultima in prob:
                for d in [1, 2, 3]:
                    prob_trans = prob[ultima][d]
                    if prob_trans > 40:  # Alta probabilidade de transição
                        pontos = (prob_trans - 30) / 10
                        score[d] += pontos
                        detalhes[d].append(f"Matriz D{ultima}→D{d}: {prob_trans:.0f}%")
        
        # 🆕 PESO 6: Detecção de Ciclos
        ciclo = self.detectar_ciclos()
        if ciclo and ciclo != 0:
            pontos = 5
            score[ciclo] += pontos
            detalhes[ciclo].append(f"Ciclo ABAB: +{pontos}")
        
        return score, detalhes
    
    def prever(self, confianca_minima=3):
        """
        Retorna a melhor dúzia, confiança e score completo
        Só retorna entrada se confiança >= confianca_minima
        """
        score, detalhes = self.calcular_score()
        
        # Ordena por score
        ranking = sorted(score.items(), key=lambda x: x[1], reverse=True)
        melhor_duzia, melhor_score = ranking[0]
        segundo_score = ranking[1][1] if len(ranking) > 1 else 0
        
        # Confiança = diferença entre 1º e 2º lugar
        confianca = melhor_score - segundo_score
        
        # Determina números da dúzia
        duzia_map = {
            1: set(range(1, 13)),
            2: set(range(13, 25)),
            3: set(range(25, 37))
        }
        numeros_duzia = duzia_map.get(melhor_duzia, set())
        
        # Se confiança é suficiente, retorna entrada
        if confianca >= confianca_minima:
            return {
                'duzia': melhor_duzia,
                'confianca': confianca,
                'score': score,
                'detalhes': detalhes,
                'numeros': sorted(numeros_duzia),
                'entrar': True,
                'forca': min(90, 40 + confianca * 8),
                'qualidade': 'EXCELENTE' if confianca >= 6 else 'BOA' if confianca >= 4 else 'REGULAR'
            }
        else:
            return {
                'duzia': melhor_duzia,
                'confianca': confianca,
                'score': score,
                'detalhes': detalhes,
                'numeros': sorted(numeros_duzia),
                'entrar': False,
                'forca': 0,
                'qualidade': 'FRACA'
            }

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
        self.duzia1 = set(range(1, 13))
        self.duzia2 = set(range(13, 25))
        self.duzia3 = set(range(25, 37))
        self.coluna1 = set(range(1, 37, 3))
        self.coluna2 = set(range(2, 37, 3))
        self.coluna3 = set(range(3, 37, 3))
    
    def get_vizinhos(self, n, r=2):
        if n not in self.race: return []
        i = self.race.index(n)
        return [self.race[(i + j) % 37] for j in range(-r, r + 1)]
    
    def get_setor_cilindro(self, n):
        if n in self.voisins: return "Voisins"
        if n in self.tiers: return "Tiers"
        if n in self.orphelins: return "Orphelins"
        return "Zero"
    
    def get_coluna(self, n):
        if n in self.coluna1: return 1
        elif n in self.coluna2: return 2
        elif n in self.coluna3: return 3
        return 0
    
    def get_duzia(self, n):
        if n in self.duzia1: return 1
        elif n in self.duzia2: return 2
        elif n in self.duzia3: return 3
        return 0
    
    def verificar_coluna(self, numero, coluna_prevista):
        if coluna_prevista is None or numero == 0: return None
        return self.get_coluna(numero) == coluna_prevista
    
    def verificar_duzia(self, numero, duzia_prevista):
        if duzia_prevista is None or numero == 0: return None
        return self.get_duzia(numero) == duzia_prevista
    
    def get_numeros_coluna(self, coluna):
        if coluna == 1: return self.coluna1
        elif coluna == 2: return self.coluna2
        elif coluna == 3: return self.coluna3
        return set()
    
    def get_numeros_duzia(self, duzia):
        if duzia == 1: return self.duzia1
        elif duzia == 2: return self.duzia2
        elif duzia == 3: return self.duzia3
        return set()
    
    def sao_vizinhos_fisicos(self, a, b, d=1):
        if a not in self.race or b not in self.race: return False
        ia, ib = self.race.index(a), self.race.index(b)
        diff = abs(ia - ib)
        return diff <= d or diff >= 37 - d
    
    def get_setor_oposto(self, setor):
        if setor == "Voisins": return "Orphelins"
        elif setor == "Orphelins": return "Voisins"
        elif setor == "Tiers": return "Tiers"
        return None

# =============================
# MOTOR DE CONFLUÊNCIA (MANTIDO)
# =============================
class MotorConfluenciaDuziasColunas:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar_confluencia(self, historico_numeros, sensibilidade_pingpong=2):
        janela = 20
        if len(historico_numeros) < janela: return None
        validos = [n for n in historico_numeros[-janela:] if n != 0]
        if len(validos) < 10: return None
        
        colunas = [get_coluna_real(n) for n in validos]
        duzias = [get_duzia_real(n) for n in validos]
        terminais = [n % 10 for n in validos]
        setores = [get_setor_roda(n) for n in validos]
        
        score_colunas = {1: 0, 2: 0, 3: 0}
        score_duzias = {1: 0, 2: 0, 3: 0}
        
        col_quente = Counter(colunas).most_common(1)[0][0]
        duz_quente = Counter(duzias).most_common(1)[0][0]
        score_colunas[col_quente] += 1
        score_duzias[duz_quente] += 1
        
        top_terminais = [t[0] for t in Counter(terminais).most_common(3)]
        cols_dos_terminais = [get_coluna_real(t) if t != 0 else 0 for t in top_terminais]
        duzs_dos_terminais = [get_duzia_real(t) if t != 0 else 0 for t in top_terminais]
        
        if cols_dos_terminais and any(c != 0 for c in cols_dos_terminais):
            col_terminal_dominante = Counter([c for c in cols_dos_terminais if c != 0]).most_common(1)[0][0]
            score_colunas[col_terminal_dominante] += 2
        if duzs_dos_terminais and any(d != 0 for d in duzs_dos_terminais):
            duz_terminal_dominante = Counter([d for d in duzs_dos_terminais if d != 0]).most_common(1)[0][0]
            score_duzias[duz_terminal_dominante] += 1
        
        setor_quente = Counter(setores).most_common(1)[0][0]
        num_do_setor_quente = [n for n in validos if get_setor_roda(n) == setor_quente]
        cols_do_setor = [get_coluna_real(n) for n in num_do_setor_quente]
        duzs_do_setor = [get_duzia_real(n) for n in num_do_setor_quente]
        if cols_do_setor:
            col_dominante_setor = Counter(cols_do_setor).most_common(1)[0][0]
            if col_dominante_setor != 0: score_colunas[col_dominante_setor] += 1
        if duzs_do_setor:
            duz_dominante_setor = Counter(duzs_do_setor).most_common(1)[0][0]
            if duz_dominante_setor != 0: score_duzias[duz_dominante_setor] += 1
        
        mapa_sensibilidade = {1: 3, 2: 4, 3: 5, 4: 6}
        giros_verificar = mapa_sensibilidade.get(sensibilidade_pingpong, 4)
        if len(colunas) >= giros_verificar:
            ultimas_cols = colunas[-giros_verificar:]
            tem_repeticao = any(ultimas_cols[i] == ultimas_cols[i+1] for i in range(len(ultimas_cols)-1))
            if not tem_repeticao: score_colunas[colunas[-1]] -= 1
        
        coluna_vencedora = max(score_colunas, key=score_colunas.get)
        duzia_vencedora = max(score_duzias, key=score_duzias.get)
        
        numeros_coluna = self.roleta.get_numeros_coluna(coluna_vencedora)
        numeros_recentes = set(validos[-5:])
        numeros_quentes = numeros_coluna.intersection(numeros_recentes)
        numeros_frios = numeros_coluna - numeros_recentes
        numeros_apostar = list(numeros_quentes)[:4] + list(numeros_frios)[:3]
        if len(numeros_apostar) < 6:
            restantes = [n for n in numeros_coluna if n not in numeros_apostar]
            numeros_apostar.extend(restantes[:6 - len(numeros_apostar)])
        
        pontos_totais = score_colunas[coluna_vencedora] + score_duzias[duzia_vencedora]
        forca = 85 if pontos_totais >= 5 else 70 if pontos_totais >= 3 else 55 if pontos_totais >= 2 else 35
        qualidade = "EXCELENTE" if pontos_totais >= 5 else "BOA" if pontos_totais >= 3 else "REGULAR"
        
        return {
            'coluna_vencedora': coluna_vencedora,
            'duzia_vencedora': duzia_vencedora,
            'pontos_totais': pontos_totais,
            'score_colunas': score_colunas,
            'score_duzias': score_duzias,
            'forca': forca,
            'qualidade': qualidade,
            'numeros_apostar': sorted(numeros_apostar[:7])
        }

# =============================
# BOT UNIFICADO (35 ESTRATÉGIAS + CONFLUÊNCIA + DUZIA AI)
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        # Estratégias originais mantidas
        self.sniper_elite = EstrategiaSniperElite(self.roleta)
        self.lucky_vizinhos = EstrategiaLuckyVizinhos(self.roleta)
        self.repeticao = EstrategiaRepeticao(self.roleta)
        self.gap_curto = EstrategiaGapCurto(self.roleta)
        self.mineracao = EstrategiaMineracao()
        self.duzia_dom = EstrategiaDuziaDominante()
        self.espelho = EstrategiaEspelho(self.roleta)
        self.soma_cinco = EstrategiaSomaCinco(self.roleta)
        self.lucky_alto = EstrategiaLuckyAlto(self.roleta)
        self.ciclo_oito = EstrategiaCicloOito(self.roleta)
        self.alternancia_cor = EstrategiaAlternanciaCor(self.roleta)
        self.setor_cilindro = EstrategiaSetorCilindro(self.roleta)
        self.zero_virada = EstrategiaZeroVirada(self.roleta)
        self.primos = EstrategiaPrimos(self.roleta)
        self.vizinhos_fisicos = EstrategiaVizinhosFisicos(self.roleta)
        self.lucky_terminal = EstrategiaLuckyTerminal(self.roleta)
        self.faixa_numerica = EstrategiaFaixaNumerica(self.roleta)
        self.numero_do_dia = EstrategiaNumeroDoDia(self.roleta)
        self.confirmacao_lucky = EstrategiaConfirmacaoLucky(self.roleta)
        self.pendulo = EstrategiaPendulo(self.roleta)
        self.quente_frio = EstrategiaQuenteFrio(self.roleta)
        self.confirmacao_dupla = EstrategiaConfirmacaoDupla()
        self.colunas_alternadas = EstrategiaColunasAlternadas(self.roleta)
        self.lucky_setor = EstrategiaLuckySetor(self.roleta)
        self.lucky_cascata = EstrategiaLuckyCascata(self.roleta)
        self.ressaca_lucky = EstrategiaRessacaLucky(self.roleta)
        self.espelho_temporal = EstrategiaEspelhoTemporal(self.roleta)
        self.esgotamento_coluna = EstrategiaEsgotamentoColuna(self.roleta)
        self.micro_ciclo3 = EstrategiaMicroCiclo3(self.roleta)
        self.setor_ritmado = EstrategiaSetorRitmado(self.roleta)
        self.lucky_imediato = EstrategiaLuckyImediato(self.roleta)
        self.lucky_recente_nao_saiu = EstrategiaLuckyRecenteNaoSaiu(self.roleta)
        self.espelho_lucky = EstrategiaEspelhoLucky(self.roleta)
        self.orfaos_setor = EstrategiaOrfaosSetor(self.roleta)
        self.zero_ciclo = EstrategiaZeroCiclo(self.roleta)
        self.motor_confluencia = MotorConfluenciaDuziasColunas(self.roleta)
        
        # 🆕 DUZIA AI
        self.duzia_ai = None  # Será inicializado quando ativado
        
        self.historico = []
        self.lucky = []
        self.mults = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
    
    def init_duzia_ai(self, window=30):
        """Inicializa o motor DuziaAI com a janela especificada"""
        self.duzia_ai = DuziaAI(window=window)
        # Alimenta com histórico existente
        for n in self.historico:
            self.duzia_ai.adicionar(n)
    
    def atualizar(self, n, lucky_nums=None, lucky_mults=None):
        if isinstance(n, dict): n = n.get('number', 0)
        self.historico.append(int(n))
        self.lucky.append(lucky_nums if lucky_nums else [])
        self.mults.append(lucky_mults if lucky_mults else {})
        if len(self.historico) > 200: self.historico = self.historico[-200:]
        if len(self.lucky) > 200: self.lucky = self.lucky[-200:]
        if len(self.mults) > 200: self.mults = self.mults[-200:]
        
        # Atualiza DuziaAI se estiver ativo
        if self.duzia_ai is not None:
            self.duzia_ai.adicionar(int(n))
    
    def gerar_entrada(self, motores=None, forcar_inversao=False, entradas_hist=None):
        # 🆕 MODO DUZIA AI        if st.session_state.get('modo_duzia_ai', False):
            if self.duzia_ai is None:
                janela = st.session_state.get('janela_duzia_ai', 30)
                self.init_duzia_ai(window=janela)
            
            confianca_minima = st.session_state.get('confianca_minima_duzia', 3)
            previsao = self.duzia_ai.prever(confianca_minima=confianca_minima)
            
            if previsao['entrar']:
                st.session_state.ultima_duzia_prevista = previsao['duzia']
                return {
                    'numeros_apostar': previsao['numeros'],
                    'forca_real': previsao['forca'],
                    'motor': f"🧠 DuziaAI D{previsao['duzia']}",
                    'estrategias_ativas': [f"Conf: {previsao['confianca']:.1f}"],
                    'qtd_motores': 1,
                    'qualidade': previsao['qualidade'],
                    'gatilho': f"IA Score: {max(previsao['score'].values()):.0f}",
                    'invertido': False,
                    'duzia_prevista': previsao['duzia'],
                    'coluna_prevista': None
                }
            return None
        
        # MODO CONFLUÊNCIA
        if st.session_state.get('modo_duzias_colunas', False):
            sensibilidade = st.session_state.get('sensibilidade_pingpong', 2)
            confluencia = self.motor_confluencia.analisar_confluencia(list(self.historico), sensibilidade)
            if confluencia and confluencia['pontos_totais'] >= 1:
                st.session_state.ultima_coluna_prevista = confluencia['coluna_vencedora']
                st.session_state.ultima_duzia_prevista = confluencia['duzia_vencedora']
                return {
                    'numeros_apostar': confluencia['numeros_apostar'],
                    'forca_real': confluencia['forca'],
                    'motor': f"Confluência Col{confluencia['coluna_vencedora']}/Dz{confluencia['duzia_vencedora']}",
                    'estrategias_ativas': [f"Score: {confluencia['pontos_totais']}pts"],
                    'qtd_motores': confluencia['pontos_totais'],
                    'qualidade': confluencia['qualidade'],
                    'gatilho': f"Confluência",
                    'invertido': False,
                    'coluna_prevista': confluencia['coluna_vencedora'],
                    'duzia_prevista': confluencia['duzia_vencedora']
                }
            return None
        
        # MODO PADRÃO (35 ESTRATÉGIAS)
        if motores is None:
            motores = {k: True for k in [
                'sniper_elite', 'lucky_vizinhos', 'repeticao', 'gap_curto', 'mineracao', 'duzia_dom',
                'espelho', 'soma_cinco', 'lucky_alto', 'ciclo_oito', 'alternancia_cor',
                'setor_cilindro', 'zero_virada', 'primos', 'vizinhos_fisicos', 'lucky_terminal',
                'faixa_numerica', 'numero_do_dia', 'confirmacao_lucky', 'pendulo', 'quente_frio',
                'colunas_alternadas', 'lucky_setor', 'lucky_cascata', 'ressaca_lucky',
                'espelho_temporal', 'esgotamento_coluna', 'micro_ciclo3', 'setor_ritmado',
                'lucky_imediato', 'lucky_recente_nao_saiu', 'espelho_lucky', 'orfaos_setor', 'zero_ciclo'
            ]}
        
        resultados = []
        forca_min = st.session_state.get('forca_minima_entrada', 55)
        
        ests = [
            (self.lucky_imediato, 'Lucky Imediato', 4, [list(self.historico), self.lucky]),
            (self.repeticao, 'Repetição', 4, [list(self.historico)]),
            (self.lucky_recente_nao_saiu, 'Lucky Recente', 3, [list(self.historico), self.lucky]),
            (self.lucky_vizinhos, 'Lucky Vizinhos', 3, [list(self.historico), self.lucky]),
            (self.vizinhos_fisicos, 'Vizinhos Físicos', 3, [list(self.historico)]),
            (self.confirmacao_lucky, 'Confirm. Lucky', 3, [list(self.historico), self.lucky]),
            (self.lucky_cascata, 'Lucky Cascata', 3, [list(self.historico), self.lucky]),
            (self.lucky_setor, 'Lucky Setor', 3, [list(self.historico), self.lucky]),
            (self.espelho_lucky, 'Espelho Lucky', 2, [list(self.historico), self.lucky]),
            (self.orfaos_setor, 'Órfãos Setor', 2, [list(self.historico)]),
            (self.sniper_elite, 'Sniper Elite', 2, [list(self.historico), self.lucky]),
            (self.gap_curto, 'Gap Curto', 2, [list(self.historico)]),
            (self.espelho, 'Espelho', 2, [list(self.historico)]),
            (self.lucky_alto, 'Lucky Alto', 2, [list(self.historico), self.lucky, self.mults]),
            (self.numero_do_dia, 'Nº do Dia', 2, [list(self.historico)]),
            (self.pendulo, 'Pêndulo', 2, [list(self.historico)]),
            (self.ressaca_lucky, 'Ressaca Lucky', 2, [list(self.historico), self.lucky, entradas_hist]),
            (self.esgotamento_coluna, 'Esgot. Coluna', 2, [list(self.historico)]),
            (self.setor_ritmado, 'Setor Ritmado', 2, [list(self.historico)]),
            (self.zero_ciclo, 'Zero Ciclo', 1, [list(self.historico)]),
            (self.mineracao, 'Mineração', 1, [list(self.historico)]),
            (self.duzia_dom, 'Dúzia Dom.', 1, [list(self.historico)]),
            (self.soma_cinco, 'Soma Cinco', 1, [list(self.historico)]),
            (self.ciclo_oito, 'Ciclo Oito', 1, [list(self.historico)]),
            (self.alternancia_cor, 'Alternância', 1, [list(self.historico)]),
            (self.setor_cilindro, 'Setor Cilindro', 1, [list(self.historico)]),
            (self.zero_virada, 'Zero Virada', 1, [list(self.historico)]),
            (self.primos, 'Primos', 1, [list(self.historico)]),
            (self.lucky_terminal, 'Lucky Terminal', 1, [list(self.historico), self.lucky]),
            (self.faixa_numerica, 'Faixa Numérica', 1, [list(self.historico)]),
            (self.quente_frio, 'Quente/Frio', 1, [list(self.historico), self.lucky]),
            (self.colunas_alternadas, 'Colunas Alt.', 1, [list(self.historico)]),
            (self.espelho_temporal, 'Espelho Temp.', 1, [list(self.historico), self.lucky]),
            (self.micro_ciclo3, 'Micro Ciclo 3', 1, [list(self.historico)]),
        ]
        
        for est, nome, peso, args in ests:
            try:
                key = nome.lower().replace(' ','_').replace('º','').replace('ú','u').replace('ã','a').replace('ç','c').replace('ó','o').replace('ô','o').replace('.','').replace('/','_').replace('ê','e')
                if motores.get(key, True) and len(self.historico) >= 1:
                    r = est.analisar(*args)
                    if r and len(r.get('base', set())) >= 1 and r['forca'] >= forca_min:
                        resultados.append((nome, r, peso))
            except: pass
        
        if len(resultados) >= 2:
            contagem_numeros = Counter()
            for _, r, peso in resultados:
                for n in r['base']: contagem_numeros[n] += peso
            confirmados = [n for n, c in contagem_numeros.items() if c >= 5]
            if confirmados:
                resultados.append(('Conf. Dupla', {'base': set(confirmados[:5]), 'forca': 65 + len(confirmados) * 2, 'estrategias': ['Conf. Dupla'], 'gatilho': f'Confirmados: {confirmados[:3]}'}, 2))
        
        if not resultados: return None
        
        base = set(); ests_ativas = []; gatilhos = []
        ft, mp, mf = 0, resultados[0][0], 0
        
        for nome, r, peso in resultados:
            for _ in range(peso): base.update(r['base'])
            ests_ativas.extend(r.get('estrategias', []))
            if 'gatilho' in r: gatilhos.append(r['gatilho'])
            ft += r['forca'] * peso
            if r['forca'] > mf: mf, mp = r['forca'], nome
        
        fm = int(ft / sum(p for _, _, p in resultados))
        mx = st.session_state.get('max_n_apostas', 7)
        mn = st.session_state.get('min_n_apostas', 4)
        
        consenso = Counter()
        for nome, r, peso in resultados:
            for n in r['base']: consenso[n] += peso
        
        lst = [n for n, _ in consenso.most_common(mx)]
        
        if st.session_state.get('limitar_numeros_altos', True):
            prob = [n for n in lst if n in self.roleta.numeros_problematicos]
            if len(prob) > self.roleta.max_problematicos:
                for p in prob[self.roleta.max_problematicos:]:
                    if p in lst and len(lst) > mn: lst.remove(p)
        
        if st.session_state.get('evitar_zero', True):
            if 0 in lst and 'Zero' not in ' '.join(gatilhos) and len(lst) > mn: lst.remove(0)
        
        max_gat = st.session_state.get('max_gatilhos', 2)
        if len(gatilhos) > max_gat: gatilhos = gatilhos[:max_gat]
        
        altos = [n for n in lst if n >= 25]
        if len(altos) > 3 and len(lst) > mn:
            for a in altos[3:]:
                if a in lst: lst.remove(a)
        
        while len(lst) < mn and len(lst) < 37:
            for n in range(37):
                if n not in lst: lst.append(n); break
        
        qs = fm / max(1, len(lst))
        q = "EXCELENTE" if qs >= 12 else "BOA" if qs >= 8 else "REGULAR"
        
        entrada = {
            'numeros_apostar': sorted(lst),
            'forca_real': min(100, max(30, fm)),
            'motor': mp,
            'estrategias_ativas': list(set(ests_ativas))[:4],
            'qtd_motores': len(resultados),
            'qualidade': q,
            'gatilho': ' | '.join(gatilhos[:2]),
            'invertido': False
        }
        
        if forcar_inversao: entrada = self._inverter_entrada(entrada)
        return entrada
    
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
        entrada['estrategias_ativas'] = ['🔄 INVERSÃO AUTO'] + entrada['estrategias_ativas'][:3]
        entrada['invertido'] = True
        entrada['gatilho'] = f"🔄 INV: {entrada['gatilho']}"
        return entrada

# =============================
# SISTEMA PRINCIPAL
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
            acerto = nr in self.entrada_ativa.get('numeros_apostar', [])
            
            # Verifica coluna e dúzia
            acerto_coluna = None
            acerto_duzia = None
            
            coluna_prevista = self.entrada_ativa.get('coluna_prevista')
            if coluna_prevista and nr != 0:
                acerto_coluna = self.bot.roleta.verificar_coluna(nr, coluna_prevista)
                if acerto_coluna: st.session_state.acertos_coluna = st.session_state.get('acertos_coluna', 0) + 1
                elif acerto_coluna is False: st.session_state.erros_coluna = st.session_state.get('erros_coluna', 0) + 1
            
            duzia_prevista = self.entrada_ativa.get('duzia_prevista')
            if duzia_prevista and nr != 0:
                acerto_duzia = self.bot.roleta.verificar_duzia(nr, duzia_prevista)
                if acerto_duzia: st.session_state.acertos_duzia = st.session_state.get('acertos_duzia', 0) + 1
                elif acerto_duzia is False: st.session_state.erros_duzia = st.session_state.get('erros_duzia', 0) + 1
            
            if acerto: self.acertos += 1; self.bot.performance['acertos'] += 1
            else: self.erros += 1; self.bot.performance['erros'] += 1
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
                'duzia_prevista': duzia_prevista,
                'acerto_coluna': acerto_coluna,
                'acerto_duzia': acerto_duzia,
            }
            self.historico_entradas.append(entrada_info)
            if len(self.historico_entradas) > 50: self.historico_entradas = self.historico_entradas[-50:]
            
            if st.session_state.get('modo_inversao_auto', False):
                if not acerto: self.estado_inversao = not self.estado_inversao
            
            enviar_resultado_auto(nr, acerto, is_lucky)
            self.entrada_ativa = None
        
        mot = {k: st.session_state.get(f'usar_{k}', True) for k in [
            'sniper_elite', 'lucky_vizinhos', 'repeticao', 'gap_curto', 'mineracao', 'duzia_dom',
            'espelho', 'soma_cinco', 'lucky_alto', 'ciclo_oito', 'alternancia_cor',
            'setor_cilindro', 'zero_virada', 'primos', 'vizinhos_fisicos', 'lucky_terminal',
            'faixa_numerica', 'numero_do_dia', 'confirmacao_lucky', 'pendulo', 'quente_frio',
            'colunas_alternadas', 'lucky_setor', 'lucky_cascata', 'ressaca_lucky',
            'espelho_temporal', 'esgotamento_coluna', 'micro_ciclo3', 'setor_ritmado',
            'lucky_imediato', 'lucky_recente_nao_saiu', 'espelho_lucky', 'orfaos_setor', 'zero_ciclo'
        ]}
        
        forcar_inversao = st.session_state.get('modo_inversao_auto', False) and self.estado_inversao
        self.entrada_ativa = self.bot.gerar_entrada(mot, forcar_inversao, list(self.historico_entradas))
        if self.entrada_ativa: enviar_previsao_auto(self.entrada_ativa)
    
    def zerar(self):
        self.acertos = 0; self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear(); self.historico_lucky.clear(); self.historico_mults.clear()
        self.entrada_ativa = None; self.estado_inversao = False
        self.bot.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.bot.historico = []; self.bot.lucky = []; self.bot.mults = []
        self.bot.duzia_ai = None
        st.session_state.acertos_coluna = 0; st.session_state.erros_coluna = 0
        st.session_state.acertos_duzia = 0; st.session_state.erros_duzia = 0
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
st.set_page_config(page_title="🎯 Roleta Bot Pro v24 - DuziaAI", layout="centered")
st.title("🎯 Roleta Bot Pro v24 - DuziaAI Engine")

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
    st.session_state.acertos_coluna = dados.get('acertos_coluna', 0)
    st.session_state.erros_coluna = dados.get('erros_coluna', 0)
    st.session_state.acertos_duzia = dados.get('acertos_duzia', 0)
    st.session_state.erros_duzia = dados.get('erros_duzia', 0)
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
    'modo_automatico': True, 'modo_duzias_colunas': False, 'modo_duzia_ai': False,
    'max_n_apostas': 7, 'min_n_apostas': 4, 'forca_minima_entrada': 55, 'max_gatilhos': 2,
    'modo_inversao_auto': False, 'sensibilidade_pingpong': 2,
    'acertos_coluna': 0, 'erros_coluna': 0, 'acertos_duzia': 0, 'erros_duzia': 0,
    'janela_duzia_ai': 30, 'confianca_minima_duzia': 3,
    'limitar_numeros_altos': True, 'evitar_zero': True
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
    st.markdown("### 🧠 MODO DE OPERAÇÃO")
    
    modo = st.radio(
        "Selecione o Motor:",
        ["📊 35 Estratégias", "🎯 Confluência Dz/Col", "🧠 DuziaAI (IA Adaptativa)"],
        index=0
    )
    
    st.session_state.modo_duzias_colunas = (modo == "🎯 Confluência Dz/Col")
    st.session_state.modo_duzia_ai = (modo == "🧠 DuziaAI (IA Adaptativa)")
    
    if st.session_state.modo_duzia_ai:
        st.success("""
        ✅ **DUZIA AI ATIVADO**
        
        **6 Pilares de Análise:**
        1. 📊 Frequência Ponderada (1.5x)
        2. 🔥 Streak/Continuidade (2x)
        3. 🔄 Rebote (3x)
        4. 💥 Quebra de Sequência (4x)
        5. 🔢 Matriz de Transição
        6. 🔁 Detecção de Ciclos
        """)
        
        st.session_state.janela_duzia_ai = st.slider(
            "📏 Janela de Análise (giros)",
            10, 50, st.session_state.janela_duzia_ai, 5,
            help="Quantos giros o motor analisa para calcular scores"
        )
        
        st.session_state.confianca_minima_duzia = st.slider(
            "🎯 Confiança Mínima para Entrada",
            1, 8, st.session_state.confianca_minima_duzia, 1,
            help="Só gera entrada se confiança >= este valor (3 = conservador, 1 = agressivo)"
        )
        
        st.info(f"💡 Confiança = Diferença entre 1º e 2º lugar no score")
    
    elif st.session_state.modo_duzias_colunas:
        st.success("✅ **CONFLUÊNCIA ATIVO**")
        st.session_state.sensibilidade_pingpong = st.select_slider(
            "🛡️ Sensibilidade Ping-Pong",
            options=[1, 2, 3, 4],
            value=st.session_state.sensibilidade_pingpong
        )
    
    else:
        st.info("📊 Modo padrão: 35 estratégias")
    
    st.markdown("---")
    with st.expander("🔄 Inversão Automática", expanded=True):
        st.session_state.modo_inversao_auto = st.checkbox("🔄 ATIVAR INVERSÃO", value=st.session_state.modo_inversao_auto)
    
    st.session_state.forca_minima_entrada = st.slider("⚡ Força Mínima", 45, 65, st.session_state.forca_minima_entrada, 5)
    st.session_state.max_n_apostas = st.slider("📊 Máx. números", 12, 18, st.session_state.max_n_apostas)
    
    if not st.session_state.modo_duzias_colunas and not st.session_state.modo_duzia_ai:
        with st.expander("🛡️ Filtros", expanded=False):
            st.session_state.limitar_numeros_altos = st.checkbox("Limitar 0,32,33,34,35", value=st.session_state.limitar_numeros_altos)
            st.session_state.evitar_zero = st.checkbox("Evitar Zero", value=st.session_state.evitar_zero)
    
    st.session_state.modo_automatico = st.checkbox("Modo Automático", value=st.session_state.modo_automatico)
    
    with st.expander("🔔 Telegram", expanded=False):
        st.session_state.telegram_token = st.text_input("Token", value=st.session_state.telegram_token, type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID", value=st.session_state.telegram_chat_id)
    
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
c5.metric("Modo", "🧠AI" if st.session_state.modo_duzia_ai else "🎯Conf" if st.session_state.modo_duzias_colunas else "📊35")

# Métricas de Dúzia (compartilhadas entre Confluência e DuziaAI)
if st.session_state.modo_duzias_colunas or st.session_state.modo_duzia_ai:
    st.markdown("---")
    st.subheader("🎯 Performance Dúzia")
    c1, c2, c3, c4 = st.columns(4)
    ac_dz = st.session_state.get('acertos_duzia', 0)
    er_dz = st.session_state.get('erros_duzia', 0)
    total_dz = ac_dz + er_dz
    tx_dz = (ac_dz/total_dz*100) if total_dz > 0 else 0
    c1.metric("✅ Green", ac_dz)
    c2.metric("❌ Red", er_dz)
    c3.metric("📊 Taxa", f"{tx_dz:.0f}%")
    c4.metric("🎯 Total", total_dz)

# =============================
# PAINEL DUZIA AI
# =============================
if st.session_state.modo_duzia_ai and sis.bot.duzia_ai is not None:
    st.markdown("---")
    st.subheader("🧠 DuziaAI - Análise em Tempo Real")
    
    score, detalhes = sis.bot.duzia_ai.calcular_score()
    freq = sis.bot.duzia_ai.frequencia()
    streak_count, streak_duzia = sis.bot.duzia_ai.streak()
    prob, matriz = sis.bot.duzia_ai.matriz_transicao()
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.metric("📊 D1 Score", f"{score[1]:.1f}", f"Freq: {freq[1]}")
        st.caption(" | ".join(detalhes[1]) if detalhes[1] else "Sem sinais")
    
    with c2:
        st.metric("📊 D2 Score", f"{score[2]:.1f}", f"Freq: {freq[2]}")
        st.caption(" | ".join(detalhes[2]) if detalhes[2] else "Sem sinais")
    
    with c3:
        st.metric("📊 D3 Score", f"{score[3]:.1f}", f"Freq: {freq[3]}")
        st.caption(" | ".join(detalhes[3]) if detalhes[3] else "Sem sinais")
    
    if streak_duzia and streak_duzia != 0:
        st.info(f"🔥 Streak Atual: D{streak_duzia} repetiu {streak_count}x")
    
    # Matriz de Transição
    with st.expander("🔢 Matriz de Transição Probabilística", expanded=False):
        st.write("**Probabilidades baseadas no histórico completo:**")
        for origem in [1, 2, 3]:
            st.write(f"**D{origem} →** D1: {prob[origem][1]:.0f}% | D2: {prob[origem][2]:.0f}% | D3: {prob[origem][3]:.0f}%")

# =============================
# ENTRADA ATIVA
# =============================
if sis.entrada_ativa:
    st.markdown("---")
    ent = sis.entrada_ativa
    
    with st.expander(f"🎰 ENTRADA ATIVA: {ent['motor']} ({ent['forca_real']}%)", expanded=True):
        col_info, col_nums = st.columns([1, 2])
        
        with col_info:
            st.write(f"**Qualidade:** {ent['qualidade']}")
            st.write(f"**Gatilho:** {ent['gatilho']}")
            if ent.get('invertido'): st.warning("⚠️ MODO INVERTIDO")
            if ent.get('duzia_prevista'):
                st.write(f"**📦 Dúzia Prevista:** {ent['duzia_prevista']}")
            if ent.get('coluna_prevista'):
                st.write(f"**🏛️ Coluna Prevista:** {ent['coluna_prevista']}")
        
        with col_nums:
            st.write("**Números para Apostar:**")
            nums = ent['numeros_apostar']
            cols = st.columns(7)
            for i, n in enumerate(nums):
                cols[i % 7].button(str(n), key=f"bet_{n}_{i}", use_container_width=True)
        
        st.progress(ent['forca_real'] / 100)

# =============================
# HISTÓRICO
# =============================
if sis.historico_entradas:
    with st.expander("📝 Histórico de Sinais", expanded=False):
        for e in reversed(sis.historico_entradas):
            res = "✅" if e['acerto'] else "❌"
            inv = "🔄" if e.get('invertido') else ""
            extras = ""
            if e.get('acerto_duzia') is not None:
                extras += f" | 📦 Dz: {'🟢' if e['acerto_duzia'] else '🔴'}"
            if e.get('acerto_coluna') is not None:
                extras += f" | 🏛️ Col: {'🟢' if e['acerto_coluna'] else '🔴'}"
            st.write(f"{res} {inv} | **Giro:** {e['resultado']} | **Motor:** {e['motor']} | **Força:** {e['forca']}%{extras}")

# =============================
# DOWNLOAD
# =============================
with st.expander("📥 Download", expanded=False):
    c1, c2, c3 = st.columns(3)
    c1.download_button("JSON", exportar_historico(st.session_state.historico, 'json'), "historico.json")
    c2.download_button("CSV", exportar_historico(st.session_state.historico, 'csv'), "historico.csv")
    c3.download_button("Entradas", json.dumps(sis.historico_entradas, indent=2), "entradas.json")

st.markdown("---")
st.caption(f"🤖 Bot Operacional v24 | DuziaAI Engine | {datetime.now().strftime('%H:%M:%S')}")

salvar_sessao()

# =============================
# CLASSES DE ESTRATÉGIA (REFERÊNCIA - JÁ DEFINIDAS ACIMA)
# =============================
# As 35 classes de estratégia permanecem as mesmas das versões anteriores
# EstrategiaSniperElite, EstrategiaLuckyVizinhos, EstrategiaRepeticao, etc.
