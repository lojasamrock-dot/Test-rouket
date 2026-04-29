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
import pandas as pd

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
        
        performance_data = {
            'acertos': st.session_state.sistema.bot.performance['acertos'],
            'erros': st.session_state.sistema.bot.performance['erros'],
            'historico': st.session_state.sistema.bot.performance['historico']
        }
        with open(PERFORMANCE_PATH, 'w') as f:
            json.dump(performance_data, f)
        
        with open(ENTRADAS_PATH, 'w') as f:
            json.dump(st.session_state.sistema.historico_entradas, f)
        
        session_data = {
            'historico': st.session_state.get('historico', []),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'sistema_acertos': st.session_state.sistema.acertos,
            'sistema_erros': st.session_state.sistema.erros,
            'sistema_historico_desempenho': st.session_state.sistema.historico_desempenho,
            'historico_numeros': list(st.session_state.sistema.historico_numeros),
            'historico_lucky': list(st.session_state.sistema.historico_lucky),
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'max_n_apostas': st.session_state.get('max_n_apostas', 10),
            'min_n_apostas': st.session_state.get('min_n_apostas', 5),
            'usar_sniper': st.session_state.get('usar_sniper', True),
            'usar_mineracao': st.session_state.get('usar_mineracao', True),
            'usar_giro': st.session_state.get('usar_giro', True),
            'usar_gap': st.session_state.get('usar_gap', True),
            'usar_sequencia': st.session_state.get('usar_sequencia', True),
            'usar_terminais': st.session_state.get('usar_terminais', True),
            'usar_simetria': st.session_state.get('usar_simetria', True),
            'usar_repeticao': st.session_state.get('usar_repeticao', True),
            'usar_ciclo': st.session_state.get('usar_ciclo', True),
            'usar_par_impar': st.session_state.get('usar_par_impar', True),
            'usar_duzia_dom': st.session_state.get('usar_duzia_dom', True),
            'usar_gap3': st.session_state.get('usar_gap3', True),
            'usar_elite_master': st.session_state.get('usar_elite_master', True),
            'modo_ia': st.session_state.sistema.modo_ia,
            'entropia_atual': st.session_state.sistema.entropia_atual,
            'erros_consecutivos': st.session_state.sistema.erros_consecutivos,
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
        motor = previsao.get('motor', '')
        qualidade = previsao.get('qualidade', '')
        qtd_motores = previsao.get('qtd_motores', 0)
        
        emoji = "🔥" if forca >= 50 else "🎯" if forca >= 35 else "📊"
        
        msg = f"{emoji} **ENTRADA** - Força: {forca}% | {len(numeros)} núm.\n"
        msg += f"🤖 {motor} (+{qtd_motores-1}) | Q: {qualidade}\n"
        if estrategias:
            msg += f"🎯 {', '.join(estrategias[:3])}\n"
        msg += f"🔢 {numeros}"
        
        st.toast(f"{emoji} {motor} - {forca}%", icon=emoji)
        st.success(f"🔔 {msg}")
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"🔔 ENTRADA F{forca}% | {len(numeros)}núm.\n🤖 {motor}\n🔢 " + " ".join(map(str, numeros)))
        
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar: {e}")

def enviar_resultado_auto(numero_real, acerto, multiplicador=None, lucky=False):
    try:
        msg = f"{'✅ ACERTO!' if acerto else '❌ ERRO!'} {numero_real}"
        if multiplicador and multiplicador > 0:
            msg += f" ⚡{multiplicador}x"
        if lucky:
            msg += " 🍀"
        
        st.toast(f"{'✅' if acerto else '❌'} {numero_real}" + (" 🍀" if lucky else ""))
        
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
        requests.post(url, json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}, timeout=10)
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
        self.pares = {0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36}
        self.impares = {1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35}
        # Setores do cilindro (roleta francesa)
        self.voisins = {22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25}
        self.tiers = {27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33}
        self.orphelins = {1, 20, 14, 31, 9, 17, 34, 6}
    
    def get_vizinhos(self, numero, raio=2):
        if numero not in self.race:
            return []
        idx = self.race.index(numero)
        return [self.race[(idx + i) % 37] for i in range(-raio, raio + 1)]
    
    def get_setor(self, numero):
        return 0 if numero == 0 else (numero - 1) // 12 + 1
    
    def get_coluna(self, numero):
        return 0 if numero == 0 else (numero - 1) % 3 + 1
    
    def get_vizinhos_roleta(self, numero, distancia=1):
        if numero not in self.race:
            return []
        idx = self.race.index(numero)
        vizinhos = []
        for i in range(-distancia, distancia + 1):
            vizinhos.append(self.race[(idx + i) % 37])
        return vizinhos
    
    def get_setor_cilindro(self, numero):
        """Retorna o setor do cilindro (Voisins, Tiers, Orphelins)"""
        if numero in self.voisins:
            return "Voisins"
        elif numero in self.tiers:
            return "Tiers"
        elif numero in self.orphelins:
            return "Orphelins"
        return "Zero"


# =============================
# 🆕 ANALISADOR ELITE MASTER
# =============================
class AnalisadorEliteMaster:
    """
    Motor de análise baseado em frequência observada no histórico real.
    Identifica padrões de inércia, vácuo, setores e terminais.
    """
    def __init__(self, roleta):
        self.roleta = roleta
        self.vermelhos_list = list(roleta.vermelhos)
    
    def get_info(self, n):
        """Extrai propriedades de um número."""
        if n == 0:
            return {"cor": "Verde", "par": "Zero", "duzia": 0, "col": 0, "setor": "Voisins", "term": 0}
        
        info = {
            "cor": "Vermelho" if n in self.roleta.vermelhos else "Preto",
            "par": "Par" if n % 2 == 0 else "Ímpar",
            "duzia": (n - 1) // 12 + 1,
            "col": (n - 1) % 3 + 1,
            "term": n % 10
        }
        
        info["setor"] = self.roleta.get_setor_cilindro(n)
        return info
    
    def analisar(self, historico, janela=5):
        """
        Recebe o histórico completo e analisa os últimos 'janela' números.
        Retorna base de apostas baseada nos gatilhos encontrados.
        """
        if len(historico) < janela:
            return None
        
        numeros_janela = historico[-janela:]
        dados = [self.get_info(n) for n in numeros_janela]
        gatilhos = []
        base = set()
        forca = 0
        
        # 1. GATILHO DE MOMENTUM (Cores)
        cores = [d['cor'] for d in dados]
        for item in ["Vermelho", "Preto"]:
            if cores.count(item) >= 4:
                gatilhos.append(f"🔥 MOMENTUM: {item}")
                # Aposta na cor dominante
                if item == "Vermelho":
                    base.update(list(self.roleta.vermelhos)[:8])
                else:
                    base.update(list(self.roleta.pretos)[:8])
                forca += 40
        
        # 2. GATILHO DE ONDA DE PARIDADE
        pares = [d['par'] for d in dados]
        for item in ["Par", "Ímpar"]:
            if pares.count(item) >= 4:
                gatilhos.append(f"📊 ONDA: {item}")
                if item == "Par":
                    base.update(list(self.roleta.pares)[:8])
                else:
                    base.update(list(self.roleta.impares)[:8])
                forca += 35
        
        # 3. GATILHO DE VÁCUO (Dúzias)
        duzias_presentes = set(d['duzia'] for d in dados if d['duzia'] != 0)
        for d in [1, 2, 3]:
            if d not in duzias_presentes:
                inicio = (d - 1) * 12 + 1
                fim = d * 12
                numeros_duzia = set(range(inicio, fim + 1))
                # Pega os números da dúzia que não saíram
                nao_sairam = numeros_duzia - set(historico[-10:])
                if nao_sairam:
                    base.update(list(nao_sairam)[:6])
                else:
                    base.update(list(numeros_duzia)[:6])
                gatilhos.append(f"🕳️ VÁCUO: Dúzia {d}")
                forca += 35
        
        # 4. GATILHO DE SETORES (Cilindro)
        setores = [d['setor'] for d in dados]
        if setores.count("Voisins") >= 3:
            gatilhos.append("🎡 SETOR: Voisins")
            base.update(list(self.roleta.voisins)[:8])
            forca += 35
        elif setores.count("Tiers") >= 3:
            gatilhos.append("⚡ SETOR: Tiers")
            base.update(list(self.roleta.tiers)[:8])
            forca += 35
        
        # 5. GATILHO DE TERMINAIS
        terminais = [d['term'] for d in dados]
        term_count = Counter(terminais)
        term_dom, freq = term_count.most_common(1)[0]
        if freq >= 2:
            numeros_terminal = [n for n in range(37) if n % 10 == term_dom]
            base.update(numeros_terminal[:5])
            gatilhos.append(f"🔢 TERMINAL: {term_dom}")
            forca += 25
        
        # 6. GATILHO DE INVERSÃO (Contra-tendência)
        if len(set(cores)) == 1 and len(dados) >= 4:
            # Todos da mesma cor - apostar na inversão
            cor_oposta = "Preto" if cores[0] == "Vermelho" else "Vermelho"
            if cor_oposta == "Vermelho":
                recentes_opostos = [n for n in historico[-20:] if n in self.roleta.vermelhos]
            else:
                recentes_opostos = [n for n in historico[-20:] if n in self.roleta.pretos]
            if recentes_opostos:
                base.update(recentes_opostos[-6:])
                gatilhos.append(f"🔄 INVERSÃO: {cor_oposta}")
                forca += 30
        
        if len(base) == 0:
            return None
        
        return {
            'base': base,
            'forca': min(100, forca),
            'estrategias': gatilhos[:4]
        }


# =============================
# ESTRATÉGIA 1: SNIPER
# =============================
class EstrategiaSniper:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, historico):
        if len(historico) < 5:
            return None
        
        recentes = historico[-15:] if len(historico) >= 15 else historico
        duzias = Counter([self.roleta.get_setor(n) for n in recentes if n != 0])
        colunas = Counter([self.roleta.get_coluna(n) for n in recentes if n != 0])
        
        base = set()
        forca = 0
        
        if duzias and colunas and duzias.most_common(1)[0][1] >= 4 and colunas.most_common(1)[0][1] >= 3:
            d, c = duzias.most_common(1)[0][0], colunas.most_common(1)[0][0]
            intersecao = set(range((d-1)*12+1, d*12+1)).intersection(set(range(c, 37, 3)))
            if len(intersecao) >= 2:
                base.update(intersecao)
                forca += 40
        
        roda_hits = []
        for n in recentes:
            roda_hits.extend(self.roleta.get_vizinhos(n, 1))
        if roda_hits:
            zona = Counter(roda_hits).most_common(1)[0]
            vizinhos = self.roleta.get_vizinhos(zona[0], 2)
            if sum(1 for n in recentes if n in vizinhos) >= 2:
                base.update(vizinhos)
                forca += 30
        
        return {'base': base, 'forca': min(100, forca), 'estrategias': ['Sniper']} if forca > 0 else None


# =============================
# ESTRATÉGIA 2: MINERAÇÃO
# =============================
class EstrategiaMineracao:
    def __init__(self):
        self.transicoes = defaultdict(list)
    
    def analisar(self, historico):
        if len(historico) < 3:
            return None
        
        self.transicoes.clear()
        for i in range(len(historico) - 1):
            self.transicoes[historico[i]].append(historico[i + 1])
        
        seguidores = self.transicoes.get(historico[-1], [])
        if seguidores:
            top = [n for n, c in Counter(seguidores).most_common(6) if c/len(seguidores) >= 0.1]
            if top:
                return {'base': set(top[:5]), 'forca': 35, 'estrategias': ['Mineração']}
        return None


# =============================
# ESTRATÉGIA 3: ANÁLISE POR GIRO
# =============================
class EstrategiaPorGiro:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, historico):
        if len(historico) < 2:
            return None
        
        ultimo = historico[-1]
        ultimos_5 = historico[-5:] if len(historico) >= 5 else historico
        ultimos_10 = historico[-10:] if len(historico) >= 10 else historico
        
        base = set([ultimo])
        base.update([n for n, _ in Counter(ultimos_5).most_common(3)])
        base.update([n for n, _ in Counter(ultimos_10).most_common(5)])
        base.update(self.roleta.get_vizinhos(ultimo, 2)[:3])
        
        return {'base': base, 'forca': 30, 'estrategias': ['Análise Giro']}


# =============================
# ESTRATÉGIA 4: GAP
# =============================
class EstrategiaGap:
    def analisar(self, historico):
        if len(historico) < 3:
            return None
        
        ultimo = historico[-1]
        if len(historico) >= 3 and historico[-3] == ultimo:
            return {'base': {ultimo, historico[-2]}, 'forca': 35, 'estrategias': ['Gap1']}
        if len(historico) >= 4 and historico[-4] == ultimo:
            return {'base': {ultimo, historico[-2], historico[-3]}, 'forca': 25, 'estrategias': ['Gap2']}
        
        recentes = historico[-15:]
        gaps = []
        for i in range(len(recentes) - 2):
            if recentes[i] == recentes[i + 2]:
                gaps.append(recentes[i])
        if gaps:
            return {'base': set([n for n, _ in Counter(gaps).most_common(4)]), 'forca': 25, 'estrategias': ['Gap Padrão']}
        
        return None


# =============================
# ESTRATÉGIA 5: SEQUÊNCIA
# =============================
class EstrategiaSequencia:
    def __init__(self):
        self.padroes = defaultdict(list)
    
    def analisar(self, historico):
        if len(historico) < 3:
            return None
        
        self.padroes.clear()
        for i in range(len(historico) - 1):
            self.padroes[historico[i]].append(historico[i + 1])
        
        previsao = [n for n, _ in Counter(self.padroes.get(historico[-1], [])).most_common(5)]
        return {'base': set(previsao), 'forca': 30, 'estrategias': ['Sequência']} if len(previsao) >= 2 else None


# =============================
# ESTRATÉGIA 6: TERMINAIS
# =============================
class EstrategiaTerminais:
    def __init__(self):
        self.terminais = {i: [n for n in range(37) if n % 10 == i] for i in range(10)}
    
    def analisar(self, historico, janela=8):
        if len(historico) < janela:
            return None
        
        final, freq = Counter([n % 10 for n in historico[-janela:]]).most_common(1)[0]
        if freq >= 2:
            return {'base': set(self.terminais[final][:5]), 'forca': 25 + freq*5, 'estrategias': [f'Terminal {final}']}
        return None


# =============================
# ESTRATÉGIA 7: SIMETRIA
# =============================
class EstrategiaSimetria:
    def __init__(self, roleta):
        self.roleta = roleta
        self.espelhos = {
            1: 10, 10: 1, 2: 20, 20: 2, 3: 30, 30: 3,
            12: 21, 21: 12, 13: 31, 31: 13, 23: 32, 32: 23,
        }
        self.palindromos = {0, 11, 22, 33}
    
    def analisar(self, historico):
        if len(historico) < 1:
            return None
        
        ultimo = historico[-1]
        base = set()
        estrategias = []
        
        if ultimo in self.espelhos:
            espelhado = self.espelhos[ultimo]
            base.add(espelhado)
            base.add(ultimo)
            estrategias.append(f"Simetria {ultimo}↔{espelhado}")
        
        elif ultimo in self.palindromos:
            base.add(ultimo)
            vizinhos = self.roleta.get_vizinhos(ultimo, 1)
            base.update(vizinhos[:3])
            estrategias.append(f"Palíndromo {ultimo}")
        
        elif 0 <= ultimo <= 9:
            mesma_terminacao = [n for n in range(37) if n % 10 == ultimo]
            base.update(mesma_terminacao[:4])
            estrategias.append(f"Simetria dígito {ultimo}")
        
        if 10 <= ultimo <= 36:
            dezena, unidade = ultimo // 10, ultimo % 10
            if 0 <= unidade <= 3 and 0 <= dezena <= 3:
                invertido = unidade * 10 + dezena
                if 0 <= invertido <= 36:
                    base.add(invertido)
                    estrategias.append(f"Inversão {ultimo}→{invertido}")
        
        if len(base) == 0:
            return None
        
        forca = 25 if len(base) <= 3 else 20
        return {'base': base, 'forca': min(100, forca), 'estrategias': estrategias}


# =============================
# ESTRATÉGIA 8: REPETIÇÃO IMEDIATA
# =============================
class EstrategiaRepeticao:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, historico):
        if len(historico) < 2:
            return None
        
        ultimo = historico[-1]
        penultimo = historico[-2]
        
        base = set()
        forca = 0
        estrategias = []
        
        if ultimo == penultimo:
            base.add(ultimo)
            vizinhos = self.roleta.get_vizinhos_roleta(ultimo, 1)
            base.update(vizinhos[:2])
            forca += 55
            estrategias.append(f"Repetição {ultimo}")
        
        if len(historico) >= 3 and historico[-3] == ultimo:
            base.add(ultimo)
            base.add(historico[-2])
            forca += 45
            estrategias.append(f"Gap1 {ultimo}")
        
        if len(historico) >= 5:
            repeticoes = sum(1 for i in range(len(historico) - 1) if historico[i] == historico[i+1])
            if repeticoes >= 2:
                base.add(ultimo)
                forca += 30
                estrategias.append("Padrão Repetição")
        
        if len(base) == 0:
            return None
        
        return {'base': base, 'forca': min(100, forca), 'estrategias': estrategias}


# =============================
# ESTRATÉGIA 9: CICLO DE RETORNO
# =============================
class EstrategiaCicloRetorno:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, historico):
        if len(historico) < 20:
            return None
        
        freq_total = Counter(historico)
        numeros_repetidos = [n for n, c in freq_total.items() if c >= 3]
        
        if not numeros_repetidos:
            return None
        
        recentes = historico[-10:]
        freq_recentes = Counter(recentes)
        quentes_repetidos = [n for n in numeros_repetidos if freq_recentes.get(n, 0) >= 1]
        
        if not quentes_repetidos:
            return None
        
        base = set(quentes_repetidos[:4])
        estrategias = [f"Ciclo {n}" for n in quentes_repetidos[:3]]
        
        for n in quentes_repetidos[:2]:
            vizinhos = self.roleta.get_vizinhos(n, 1)
            base.update(vizinhos[:2])
        
        forca = 40 if len(quentes_repetidos) >= 3 else 30
        
        return {'base': base, 'forca': min(100, forca), 'estrategias': estrategias}


# =============================
# ESTRATÉGIA 10: PAR/ÍMPAR
# =============================
class EstrategiaParImpar:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, historico):
        if len(historico) < 4:
            return None
        
        ultimos_tipos = []
        for n in historico[-10:]:
            if n == 0:
                ultimos_tipos.append('zero')
            elif n % 2 == 0:
                ultimos_tipos.append('par')
            else:
                ultimos_tipos.append('impar')
        
        seq_atual = 0
        tipo_atual = ultimos_tipos[-1]
        for t in reversed(ultimos_tipos):
            if t == tipo_atual and t != 'zero':
                seq_atual += 1
            else:
                break
        
        if seq_atual >= 3 and tipo_atual in ['par', 'impar']:
            tipo_alvo = 'par' if tipo_atual == 'impar' else 'impar'
            alvo_set = self.roleta.pares if tipo_alvo == 'par' else self.roleta.impares
            recentes = set(historico[-15:])
            base = alvo_set.intersection(recentes)
            
            if len(base) < 4:
                base = set(list(alvo_set)[:8])
            
            forca = 35 + (seq_atual * 5)
            estrategias = [f"Inversão {tipo_atual}→{tipo_alvo} ({seq_atual}x)"]
            
            return {'base': base, 'forca': min(100, forca), 'estrategias': estrategias}
        
        return None


# =============================
# ESTRATÉGIA 11: DÚZIA DOMINANTE
# =============================
class EstrategiaDuziaDominante:
    def __init__(self):
        self.duzias = {
            1: set(range(1, 13)),
            2: set(range(13, 25)),
            3: set(range(25, 37))
        }
    
    def analisar(self, historico):
        if len(historico) < 10:
            return None
        
        recentes = historico[-10:]
        contagem = Counter()
        for n in recentes:
            if n != 0:
                d = (n - 1) // 12 + 1
                contagem[d] += 1
        
        if not contagem:
            return None
        
        duzia_dom, freq = contagem.most_common(1)[0]
        
        if freq >= 4:
            numeros_duzia = self.duzias[duzia_dom]
            nao_sairam = numeros_duzia - set(historico[-5:])
            
            base = set()
            if nao_sairam:
                base.update(list(nao_sairam)[:5])
            
            quentes_duzia = numeros_duzia.intersection(set(historico[-5:]))
            base.update(list(quentes_duzia)[:3])
            
            forca = 35 + (freq * 3)
            estrategias = [f"Dúzia {duzia_dom} ({freq}/10)"]
            
            return {'base': base, 'forca': min(100, forca), 'estrategias': estrategias}
        
        return None


# =============================
# ESTRATÉGIA 12: GAP 3 GIROS
# =============================
class EstrategiaGap3:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, historico):
        if len(historico) < 4:
            return None
        
        ultimo = historico[-1]
        base = set()
        estrategias = []
        forca = 0
        
        if len(historico) >= 4 and historico[-4] == ultimo:
            base.add(ultimo)
            base.add(historico[-2])
            base.add(historico[-3])
            forca += 45
            estrategias.append(f"Gap3: {ultimo}")
        
        if len(historico) >= 5 and historico[-5] == ultimo:
            base.add(ultimo)
            forca += 35
            estrategias.append(f"Gap4: {ultimo}")
        
        if len(historico) >= 6 and historico[-6] == ultimo:
            base.add(ultimo)
            base.add(historico[-3])
            forca += 25
            estrategias.append(f"Gap5: {ultimo}")
        
        if len(base) == 0:
            return None
        
        for n in list(base)[:2]:
            base.update(self.roleta.get_vizinhos(n, 1)[:2])
        
        return {'base': base, 'forca': min(100, forca), 'estrategias': estrategias}


# =============================
# BOT UNIFICADO (13 ESTRATÉGIAS)
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        self.elite_master = AnalisadorEliteMaster(self.roleta)
        self.sniper = EstrategiaSniper(self.roleta)
        self.mineracao = EstrategiaMineracao()
        self.giro = EstrategiaPorGiro(self.roleta)
        self.gap = EstrategiaGap()
        self.sequencia = EstrategiaSequencia()
        self.terminais = EstrategiaTerminais()
        self.simetria = EstrategiaSimetria(self.roleta)
        self.repeticao = EstrategiaRepeticao(self.roleta)
        self.ciclo = EstrategiaCicloRetorno(self.roleta)
        self.par_impar = EstrategiaParImpar(self.roleta)
        self.duzia_dom = EstrategiaDuziaDominante()
        self.gap3 = EstrategiaGap3(self.roleta)
        
        self.historico = []
        self.lucky = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        
    def atualizar(self, numero, lucky_nums=None, lucky_mults=None):
        if isinstance(numero, dict):
            numero = numero.get('number', 0)
        numero = int(numero)
        
        self.historico.append(numero)
        self.lucky.append(lucky_nums if lucky_nums else [])
        
        if len(self.historico) > 200:
            self.historico = self.historico[-200:]
            self.lucky = self.lucky[-200:]
    
    def atualizar_resultado(self, acerto):
        self.performance['historico'].append(1 if acerto else 0)
        if acerto:
            self.performance['acertos'] += 1
        else:
            self.performance['erros'] += 1
    
    def get_taxa(self):
        total = self.performance['acertos'] + self.performance['erros']
        return self.performance['acertos'] / total if total > 0 else 0
    
    def gerar_entrada(self, motores_ativos=None):
        if motores_ativos is None:
            motores_ativos = {k: True for k in [
                'elite_master', 'sniper', 'mineracao', 'giro', 'gap', 'sequencia', 'terminais', 'simetria',
                'repeticao', 'ciclo', 'par_impar', 'duzia_dom', 'gap3'
            ]}
        
        resultados = []
        
        # Ordem de prioridade: Elite Master primeiro (maior peso)
        estrategias = [
            ('Elite Master', self.elite_master, [list(self.historico)], 'elite_master'),
            ('Repetição', self.repeticao, [list(self.historico)], 'repeticao'),
            ('Ciclo Retorno', self.ciclo, [list(self.historico)], 'ciclo'),
            ('Par/Ímpar', self.par_impar, [list(self.historico)], 'par_impar'),
            ('Dúzia Dominante', self.duzia_dom, [list(self.historico)], 'duzia_dom'),
            ('Gap 3', self.gap3, [list(self.historico)], 'gap3'),
            ('Sniper', self.sniper, [list(self.historico)], 'sniper'),
            ('Mineração', self.mineracao, [list(self.historico)], 'mineracao'),
            ('Giro', self.giro, [list(self.historico)], 'giro'),
            ('Gap', self.gap, [list(self.historico)], 'gap'),
            ('Sequência', self.sequencia, [list(self.historico)], 'sequencia'),
            ('Terminais', self.terminais, [list(self.historico)], 'terminais'),
            ('Simetria', self.simetria, [list(self.historico)], 'simetria'),
        ]
        
        for nome, estrategia, args, key in estrategias:
            try:
                if motores_ativos.get(key, True) and len(self.historico) >= 1:
                    r = estrategia.analisar(*args)
                    if r and len(r.get('base', set())) >= 1:
                        # Elite Master tem peso 2x
                        peso = 2 if key == 'elite_master' else 1
                        resultados.append((nome, r, peso))
            except:
                pass
        
        if not resultados:
            freq = Counter(self.historico[-20:]) if len(self.historico) >= 5 else Counter(self.historico)
            quentes = [n for n, _ in freq.most_common(8)]
            atrasados = [n for n in range(37) if n not in self.historico[-10:]][:4]
            
            base = set(quentes[:6] + atrasados[:2])
            return {
                'numeros_apostar': sorted(list(base)[:10]),
                'forca_real': 20,
                'motor': 'Frequência Básica',
                'estrategias_ativas': ['Quentes + Atrasados'],
                'qtd_motores': 1,
                'qualidade': 'BÁSICA',
                'green': False,
                'repeticao': False,
            }
        
        # Fusão com pesos
        base_final = set()
        todas_estrategias = []
        forca_total = 0
        motor_principal = resultados[0][0]
        maior_forca = 0
        
        for nome, r, peso in resultados:
            for _ in range(peso):
                base_final.update(r['base'])
            todas_estrategias.extend(r.get('estrategias', []))
            forca_total += r['forca'] * peso
            if r['forca'] > maior_forca:
                maior_forca = r['forca']
                motor_principal = nome
        
        pesos_total = sum(p for _, _, p in resultados)
        forca_media = int(forca_total / pesos_total) if pesos_total > 0 else 25
        
        max_n = st.session_state.get('max_n_apostas', 10)
        min_n = st.session_state.get('min_n_apostas', 5)
        
        prioridade = [n for n, _ in Counter({n: 1 for n in base_final}).most_common()]
        base_list = prioridade[:max_n]
        
        while len(base_list) < min_n and len(base_list) < 37:
            for n in range(37):
                if n not in base_list:
                    base_list.append(n)
                    break
        
        qualidade_score = forca_media / max(1, len(base_list))
        qualidade = "EXCELENTE" if qualidade_score >= 8 else "BOA" if qualidade_score >= 5 else "REGULAR" if qualidade_score >= 3 else "BÁSICA"
        
        return {
            'numeros_apostar': sorted(base_list),
            'forca_real': min(100, max(15, forca_media)),
            'motor': motor_principal,
            'estrategias_ativas': list(set(todas_estrategias))[:5],
            'qtd_motores': len(resultados),
            'qualidade': qualidade,
            'green': False,
            'repeticao': False,
        }


# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaBot:
    def __init__(self):
        self.bot = RoletaBotUnificado()
        self.historico_numeros = deque(maxlen=200)
        self.historico_lucky = deque(maxlen=100)
        self.entrada_ativa = None
        self.historico_entradas = []
        self.acertos = 0
        self.erros = 0
        self.modo_ia = "ATIVO"
        self.entropia_atual = 0
        self.erros_consecutivos = 0
        
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            numero_real = numero_data['number']
            lucky = numero_data.get('luckyNumbers', [])
            lucky_mults = numero_data.get('luckyMultipliers', {})
            mult = lucky_mults.get(numero_real) if numero_real in lucky else None
            is_lucky = numero_real in lucky
        else:
            numero_real = int(numero_data)
            lucky, lucky_mults, mult, is_lucky = [], {}, None, False
        
        self.bot.atualizar(numero_real, lucky, lucky_mults)
        self.historico_numeros.append(numero_real)
        self.historico_lucky.append(lucky)
        
        if self.entrada_ativa:
            acerto = numero_real in self.entrada_ativa.get('numeros_apostar', [])
            self.bot.atualizar_resultado(acerto)
            
            entrada_info = {
                'rodada': len(self.historico_numeros) - 1,
                'hora': datetime.now().strftime('%H:%M:%S'),
                'numeros': self.entrada_ativa.get('numeros_apostar', []),
                'resultado': numero_real,
                'acerto': acerto,
                'forca': self.entrada_ativa.get('forca_real', 0),
                'motor': self.entrada_ativa.get('motor', ''),
                'estrategias': self.entrada_ativa.get('estrategias_ativas', []),
                'qualidade': self.entrada_ativa.get('qualidade', ''),
                'lucky': is_lucky,
                'multiplicador': mult,
            }
            self.historico_entradas.append(entrada_info)
            if len(self.historico_entradas) > 50:
                self.historico_entradas = self.historico_entradas[-50:]
            
            if acerto:
                self.acertos += 1
                self.erros_consecutivos = 0
            else:
                self.erros += 1
                self.erros_consecutivos += 1
            
            enviar_resultado_auto(numero_real, acerto, mult, is_lucky)
            self.entrada_ativa = None
        
        # Gera nova entrada
        motores_ativos = {
            'sniper': st.session_state.get('usar_sniper', True),
            'mineracao': st.session_state.get('usar_mineracao', True),
            'giro': st.session_state.get('usar_giro', True),
            'gap': st.session_state.get('usar_gap', True),
            'sequencia': st.session_state.get('usar_sequencia', True),
            'terminais': st.session_state.get('usar_terminais', True),
            'simetria': st.session_state.get('usar_simetria', True),
            'repeticao': st.session_state.get('usar_repeticao', True),
            'ciclo': st.session_state.get('usar_ciclo', True),
            'par_impar': st.session_state.get('usar_par_impar', True),
            'duzia_dom': st.session_state.get('usar_duzia_dom', True),
            'gap3': st.session_state.get('usar_gap3', True),
            'elite_master': st.session_state.get('usar_elite_master', True),
        }
        
        self.entrada_ativa = self.bot.gerar_entrada(motores_ativos)
        
        if self.entrada_ativa:
            enviar_previsao_auto(self.entrada_ativa)
    
    def zerar(self):
        self.acertos = 0
        self.erros = 0
        self.historico_entradas = []
        self.historico_numeros.clear()
        self.historico_lucky.clear()
        self.entrada_ativa = None
        self.erros_consecutivos = 0
        self.bot.zerar()
        salvar_sessao()


# =============================
# FUNÇÕES AUXILIARES
# =============================
def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    try:
        with open(caminho, "w") as f:
            json.dump(historico, f, indent=2)
    except: pass

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
        
        numeros_raio, multiplicadores = [], {}
        for item in result.get('luckyNumbersList', []):
            n = item.get('number')
            if n is not None:
                numeros_raio.append(n)
                m = item.get('roundedMultiplier')
                if m is not None:
                    multiplicadores[n] = m
        
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
                linhas.append(f"{n},{item.get('timestamp','')},{item.get('luckyMultipliers',{}).get(n,'')}")
            else:
                linhas.append(f"{item},,")
        return "\n".join(linhas)


# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎯 Bot Unificado — 13 Estratégias + Elite Master", layout="centered")
st.title("🎯 Bot Unificado — 13 Estratégias + Elite Master")

if "sistema" not in st.session_state or st.session_state.sistema is None:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    if not st.session_state.get('historico'):
        st.session_state.historico = dados.get('historico', [])
    
    sis = st.session_state.sistema
    sis.acertos = dados.get('sistema_acertos', 0)
    sis.erros = dados.get('sistema_erros', 0)
    sis.erros_consecutivos = dados.get('erros_consecutivos', 0)
    
    for num, lucky in zip(dados.get('historico_numeros', []), dados.get('historico_lucky', [])):
        sis.bot.atualizar(num, lucky)
        sis.historico_numeros.append(num)
        sis.historico_lucky.append(lucky)
    
    if os.path.exists(PERFORMANCE_PATH):
        try:
            with open(PERFORMANCE_PATH, 'r') as f:
                perf = json.load(f)
                sis.bot.performance = {'acertos': perf.get('acertos', 0), 'erros': perf.get('erros', 0), 'historico': perf.get('historico', [])}
        except: pass
    
    if os.path.exists(ENTRADAS_PATH):
        try:
            with open(ENTRADAS_PATH, 'r') as f:
                sis.historico_entradas = json.load(f)
        except: pass

defaults = {
    'modo_automatico': True, 'max_n_apostas': 10, 'min_n_apostas': 5,
    'usar_sniper': True, 'usar_mineracao': True, 'usar_giro': True,
    'usar_gap': True, 'usar_sequencia': True, 'usar_terminais': True,
    'usar_simetria': True, 'usar_repeticao': True, 'usar_ciclo': True,
    'usar_par_impar': True, 'usar_duzia_dom': True, 'usar_gap3': True,
    'usar_elite_master': True,
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
        except: pass

if "telegram_token" not in st.session_state:
    st.session_state.telegram_token = ""
if "telegram_chat_id" not in st.session_state:
    st.session_state.telegram_chat_id = ""

# Sidebar
st.sidebar.title("⚙️ Configurações")
st.sidebar.success("✅ **13 ESTRATÉGIAS + ELITE MASTER**")

with st.sidebar.expander("🧠 Elite Master (Prioritário)", expanded=True):
    st.session_state.usar_elite_master = st.checkbox("👑 Elite Master", value=st.session_state.usar_elite_master, help="🔥 MOMENTUM | 🕳️ VÁCUO | 🎡 SETORES | 🔢 TERMINAIS")
    st.caption("Análise de inércia, vácuo, setores do cilindro e terminais")

with st.sidebar.expander("🆕 Estratégias do Histórico", expanded=False):
    st.session_state.usar_repeticao = st.checkbox("🔄 Repetição Imediata", value=st.session_state.usar_repeticao)
    st.session_state.usar_ciclo = st.checkbox("🔁 Ciclo de Retorno", value=st.session_state.usar_ciclo)
    st.session_state.usar_par_impar = st.checkbox("⚖️ Par/Ímpar", value=st.session_state.usar_par_impar)
    st.session_state.usar_duzia_dom = st.checkbox("📐 Dúzia Dominante", value=st.session_state.usar_duzia_dom)
    st.session_state.usar_gap3 = st.checkbox("⏭️ Gap 3 Giros", value=st.session_state.usar_gap3)

with st.sidebar.expander("🎯 Estratégias Originais", expanded=False):
    st.session_state.usar_sniper = st.checkbox("🎯 Sniper", value=st.session_state.usar_sniper)
    st.session_state.usar_mineracao = st.checkbox("🔬 Mineração", value=st.session_state.usar_mineracao)
    st.session_state.usar_giro = st.checkbox("🔄 Giro", value=st.session_state.usar_giro)
    st.session_state.usar_gap = st.checkbox("🔁 Gap", value=st.session_state.usar_gap)
    st.session_state.usar_sequencia = st.checkbox("📊 Sequência", value=st.session_state.usar_sequencia)
    st.session_state.usar_terminais = st.checkbox("🔢 Terminais", value=st.session_state.usar_terminais)
    st.session_state.usar_simetria = st.checkbox("🔄 Simetria", value=st.session_state.usar_simetria)

with st.sidebar.expander("⚙️ Ajustes", expanded=True):
    st.session_state.max_n_apostas = st.slider("📊 Máx. números", 5, 18, st.session_state.max_n_apostas)
    st.session_state.min_n_apostas = st.slider("📊 Mín. números", 3, 8, st.session_state.min_n_apostas)

st.session_state.modo_automatico = st.sidebar.checkbox("🔄 Modo Automático", value=st.session_state.modo_automatico)

with st.sidebar.expander("🔔 Telegram", expanded=False):
    st.session_state.telegram_token = st.text_input("Token:", value=st.session_state.telegram_token, type="password")
    st.session_state.telegram_chat_id = st.text_input("Chat ID:", value=st.session_state.telegram_chat_id)
    if st.button("💾 Salvar Telegram"):
        salvar_sessao()
        st.success("✅")

with st.sidebar.expander("💾 Geral", expanded=False):
    if st.button("💾 Salvar", use_container_width=True):
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()
        st.success("✅")
    if st.button("🗑️ Zerar", use_container_width=True):
        if st.checkbox("Confirmar"):
            st.session_state.sistema.zerar()
            st.rerun()

# Conteúdo principal
st.subheader("✍️ Inserir Números")
c1, c2 = st.columns([3, 1])
with c1:
    entrada = st.text_input("Números (0-36):", key="entrada")
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
sis = st.session_state.sistema
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("🟢 Acertos", sis.acertos)
c2.metric("🔴 Erros", sis.erros)
c3.metric("📊 Total", sis.acertos + sis.erros)
c4.metric("⚠️ Erros seg.", sis.erros_consecutivos)
c5.metric("🤖 Estrat.", "13")

if sis.acertos + sis.erros > 0:
    taxa = sis.acertos / (sis.acertos + sis.erros) * 100
    emoji = "🟢" if taxa >= 30 else "🟡" if taxa >= 20 else "🔴"
    st.write(f"{emoji} **Taxa de acerto: {taxa:.1f}%**")

# Entrada atual
st.subheader("🎯 Entrada Atual")
if sis.entrada_ativa:
    e = sis.entrada_ativa
    emoji = "🔥" if e['forca_real'] >= 50 else "🎯" if e['forca_real'] >= 35 else "📊"
    st.info(f"{emoji} **{e['qualidade']}** | Força {e['forca_real']}% | {len(e['numeros_apostar'])} núm. | {e['motor']}")
    st.caption(f"🎯 {', '.join(e.get('estrategias_ativas', [])[:5])}")
    st.markdown(f"## {', '.join(map(str, sorted(e['numeros_apostar'])))}")

# Histórico de entradas
st.subheader("📋 Histórico de Entradas")
if sis.historico_entradas:
    col_h1, col_h2, col_h3, col_h4, col_h5, col_h6 = st.columns([1, 1.5, 1, 1, 1.5, 2])
    col_h1.write("**Rod.**")
    col_h2.write("**Números**")
    col_h3.write("**Res.**")
    col_h4.write("**Força**")
    col_h5.write("**Motor**")
    col_h6.write("**Qualidade**")
    st.divider()
    
    for entrada in reversed(sis.historico_entradas[-15:]):
        c1, c2, c3, c4, c5, c6 = st.columns([1, 1.5, 1, 1, 1.5, 2])
        c1.write(f"#{entrada['rodada']}")
        nums = entrada['numeros'][:5]
        c2.write(", ".join(map(str, nums)) + (f" +{len(entrada['numeros'])-5}" if len(entrada['numeros']) > 5 else ""))
        if entrada['acerto']:
            c3.success(f"✅ {entrada['resultado']}" + (" 🍀" if entrada.get('lucky') else ""))
        else:
            c3.error(f"❌ {entrada['resultado']}")
        c4.write(f"{entrada['forca']}%")
        c5.write(entrada['motor'][:14])
        c6.write(entrada.get('qualidade', '-'))
else:
    st.info("Nenhuma entrada ainda.")

# Performance por motor
if sis.historico_entradas:
    st.subheader("📊 Performance por Motor")
    motor_stats = defaultdict(lambda: {'acertos': 0, 'total': 0})
    for e in sis.historico_entradas:
        motor = e.get('motor', 'Desconhecido')
        motor_stats[motor]['total'] += 1
        if e['acerto']:
            motor_stats[motor]['acertos'] += 1
    
    cols = st.columns(min(5, len(motor_stats)))
    for i, (motor, stats) in enumerate(sorted(motor_stats.items(), key=lambda x: x[1]['total'], reverse=True)[:5]):
        taxa = stats['acertos'] / stats['total'] * 100 if stats['total'] > 0 else 0
        emoji = "🟢" if taxa >= 30 else "🟡" if taxa >= 20 else "🔴"
        with cols[i]:
            st.metric(f"{emoji} {motor[:10]}", f"{taxa:.0f}%", f"{stats['acertos']}/{stats['total']}")

st.subheader("📥 Download")
st.metric("📊 Registros", len(st.session_state.historico))
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("📥 JSON", use_container_width=True):
        st.download_button("⬇️ Baixar", exportar_historico(st.session_state.historico, 'json'), "historico.json", "application/json")
with c2:
    if st.button("📥 CSV", use_container_width=True):
        st.download_button("⬇️ Baixar", exportar_historico(st.session_state.historico, 'csv'), "historico.csv", "text/csv")
with c3:
    if st.button("📥 Entradas", use_container_width=True):
        st.download_button("⬇️ Baixar", json.dumps(sis.historico_entradas, indent=2), "entradas.json", "application/json")

salvar_sessao()
