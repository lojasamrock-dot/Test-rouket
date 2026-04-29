
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
            'modo_ia': st.session_state.sistema.modo_ia,
            'entropia_atual': st.session_state.sistema.entropia_atual,
            'erros_consecutivos': st.session_state.sistema.erros_consecutivos,
            'ultima_entrada_numeros': st.session_state.sistema.ultima_entrada_numeros,
            'ultima_entrada_forca': st.session_state.sistema.ultima_entrada_forca,
            'ultima_entrada_motor': st.session_state.sistema.ultima_entrada_motor,
            'repeticoes_acerto_consecutivas': st.session_state.sistema.repeticoes_acerto_consecutivas,
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
    
    def get_vizinhos(self, numero, raio=2):
        if numero not in self.race:
            return []
        idx = self.race.index(numero)
        return [self.race[(idx + i) % 37] for i in range(-raio, raio + 1)]
    
    def get_setor(self, numero):
        return 0 if numero == 0 else (numero - 1) // 12 + 1
    
    def get_coluna(self, numero):
        return 0 if numero == 0 else (numero - 1) % 3 + 1


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
# ESTRATÉGIA 7: SIMETRIA (CORRIGIDA E COMPLETA)
# =============================
class EstrategiaSimetria:
    def __init__(self, roleta):
        self.roleta = roleta
        # Simetria de espelhamento de dígitos (COMPLETO)
        # Ex: 12 inverte para 21, 13 inverte para 31, etc.
        self.espelhos = {
            1: 10, 10: 1,
            2: 20, 20: 2,
            3: 30, 30: 3,
            12: 21, 21: 12,
            13: 31, 31: 13,
            23: 32, 32: 23,
        }
        
        # Números que são simétricos de si mesmos (palíndromos)
        self.palindromos = {0, 11, 22, 33}
    
    def analisar(self, historico):
        if len(historico) < 1:
            return None
        
        ultimo = historico[-1]
        base = set()
        estrategias = []
        
        # 1. Simetria de espelhamento (a mais importante)
        if ultimo in self.espelhos:
            espelhado = self.espelhos[ultimo]
            base.add(espelhado)
            base.add(ultimo)  # Inclui também o próprio número
            estrategias.append(f"Simetria {ultimo}↔{espelhado}")
        
        # 2. Se for palíndromo, aposta no próprio número e vizinhos
        elif ultimo in self.palindromos:
            base.add(ultimo)
            # Adiciona vizinhos na roleta
            vizinhos = self.roleta.get_vizinhos(ultimo, 1)
            base.update(vizinhos[:3])
            estrategias.append(f"Palíndromo {ultimo}+vizinhos")
        
        # 3. Simetria por inversão de dígitos para números de 1 dígito
        # Ex: 5 → aposta em números terminados em 5 (5,15,25,35)
        elif 0 <= ultimo <= 9:
            # Números que terminam com o mesmo dígito
            mesma_terminacao = [n for n in range(37) if n % 10 == ultimo]
            base.update(mesma_terminacao[:4])
            estrategias.append(f"Simetria dígito {ultimo}")
        
        # 4. Simetria de dezenas (números na mesma faixa)
        # Ex: 14 → aposta em 4, 24, 34 (mesmo final)
        if 10 <= ultimo <= 36:
            dezena = ultimo // 10
            unidade = ultimo % 10
            # Inverte dezena e unidade
            if 0 <= unidade <= 3 and 0 <= dezena <= 3:
                invertido = unidade * 10 + dezena
                if 0 <= invertido <= 36:
                    base.add(invertido)
                    estrategias.append(f"Inversão {ultimo}→{invertido}")
        
        if len(base) == 0:
            return None
        
        # Força baseada na quantidade de números gerados
        forca = 25 if len(base) <= 3 else 20
        
        return {
            'base': base,
            'forca': min(100, forca),
            'estrategias': estrategias
        }


# =============================
# BOT UNIFICADO (7 ESTRATÉGIAS)
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        self.sniper = EstrategiaSniper(self.roleta)
        self.mineracao = EstrategiaMineracao()
        self.giro = EstrategiaPorGiro(self.roleta)
        self.gap = EstrategiaGap()
        self.sequencia = EstrategiaSequencia()
        self.terminais = EstrategiaTerminais()
        self.simetria = EstrategiaSimetria(self.roleta)
        
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
        """
        GERA UMA ENTRADA A CADA CHAMADA - SEMPRE RETORNA ALGO
        """
        if motores_ativos is None:
            motores_ativos = {k: True for k in ['sniper', 'mineracao', 'giro', 'gap', 'sequencia', 'terminais', 'simetria']}
        
        resultados = []
        
        # Executa todos os motores ativos
        estrategias = [
            ('Sniper', self.sniper, [list(self.historico)]),
            ('Mineração', self.mineracao, [list(self.historico)]),
            ('Giro', self.giro, [list(self.historico)]),
            ('Gap', self.gap, [list(self.historico)]),
            ('Sequência', self.sequencia, [list(self.historico)]),
            ('Terminais', self.terminais, [list(self.historico)]),
            ('Simetria', self.simetria, [list(self.historico)]),
        ]
        
        for nome, estrategia, args in estrategias:
            try:
                key = nome.lower().replace(' ', '_').replace('ã', 'a').replace('ê', 'e').replace('ó', 'o').replace('ú', 'u').replace('ç', 'c')
                key_map = {
                    'sniper': 'sniper', 'mineracao': 'mineracao', 'giro': 'giro',
                    'gap': 'gap', 'sequencia': 'sequencia', 'terminais': 'terminais', 'simetria': 'simetria'
                }
                key = key_map.get(key, key)
                
                if motores_ativos.get(key, True) and len(self.historico) >= 1:
                    r = estrategia.analisar(*args)
                    if r and len(r.get('base', set())) >= 1:
                        resultados.append((nome, r))
            except Exception as e:
                pass
        
        # Se nenhum motor ativou, cria entrada básica
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
        
        # Fusão dos resultados
        base_final = set()
        todas_estrategias = []
        forca_total = 0
        motor_principal = resultados[0][0]
        maior_forca = 0
        
        for nome, r in resultados:
            peso = 1
            for _ in range(peso):
                base_final.update(r['base'])
            todas_estrategias.extend(r.get('estrategias', []))
            forca_total += r['forca'] * peso
            if r['forca'] > maior_forca:
                maior_forca = r['forca']
                motor_principal = nome
        
        forca_media = int(forca_total / len(resultados)) if resultados else 25
        
        max_n = st.session_state.get('max_n_apostas', 10)
        min_n = st.session_state.get('min_n_apostas', 5)
        
        prioridade = [n for n, _ in Counter({n: 1 for n in base_final}).most_common()]
        base_list = prioridade[:max_n]
        
        # Garante mínimo de números
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
        self.repeticoes_acerto_consecutivas = 0
        self.ultima_entrada_numeros = []
        self.ultima_entrada_forca = 0
        self.ultima_entrada_motor = ""
        
    def processar_novo_numero(self, numero_data):
        # Extrai dados
        if isinstance(numero_data, dict):
            numero_real = numero_data['number']
            lucky = numero_data.get('luckyNumbers', [])
            lucky_mults = numero_data.get('luckyMultipliers', {})
            mult = lucky_mults.get(numero_real) if numero_real in lucky else None
            is_lucky = numero_real in lucky
        else:
            numero_real = int(numero_data)
            lucky, lucky_mults, mult, is_lucky = [], {}, None, False
        
        # Atualiza bot
        self.bot.atualizar(numero_real, lucky, lucky_mults)
        self.historico_numeros.append(numero_real)
        self.historico_lucky.append(lucky)
        
        # Verifica resultado da entrada anterior
        if self.entrada_ativa:
            acerto = numero_real in self.entrada_ativa.get('numeros_apostar', [])
            self.bot.atualizar_resultado(acerto)
            
            # Registra no histórico
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
                self.ultima_entrada_numeros = self.entrada_ativa.get('numeros_apostar', [])
                self.ultima_entrada_forca = self.entrada_ativa.get('forca_real', 0)
                self.ultima_entrada_motor = self.entrada_ativa.get('motor', '')
            else:
                self.erros += 1
                self.erros_consecutivos += 1
            
            enviar_resultado_auto(numero_real, acerto, mult, is_lucky)
            self.entrada_ativa = None
        
        # ==========================================
        # GERA NOVA ENTRADA (SEMPRE!)
        # ==========================================
        motores_ativos = {
            'sniper': st.session_state.get('usar_sniper', True),
            'mineracao': st.session_state.get('usar_mineracao', True),
            'giro': st.session_state.get('usar_giro', True),
            'gap': st.session_state.get('usar_gap', True),
            'sequencia': st.session_state.get('usar_sequencia', True),
            'terminais': st.session_state.get('usar_terminais', True),
            'simetria': st.session_state.get('usar_simetria', True),
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
st.set_page_config(page_title="🎯 Bot Unificado — 7 Estratégias", layout="centered")
st.title("🎯 Bot Unificado — 7 Estratégias")

# Inicializa sistema
if "sistema" not in st.session_state or st.session_state.sistema is None:
    st.session_state.sistema = SistemaBot()

# Carrega dados
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

# Valores padrão
defaults = {
    'modo_automatico': True,
    'max_n_apostas': 10,
    'min_n_apostas': 5,
    'usar_sniper': True, 'usar_mineracao': True,
    'usar_giro': True, 'usar_gap': True, 'usar_sequencia': True,
    'usar_terminais': True, 'usar_simetria': True,
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

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.title("⚙️ Configurações")

st.sidebar.success("✅ **MODO: ENTRADA TODO GIRO**")

with st.sidebar.expander("🤖 Motores (7 ativos)", expanded=True):
    st.session_state.usar_sniper = st.checkbox("🎯 Sniper", value=st.session_state.usar_sniper)
    st.session_state.usar_mineracao = st.checkbox("🔬 Mineração", value=st.session_state.usar_mineracao)
    st.session_state.usar_giro = st.checkbox("🔄 Giro", value=st.session_state.usar_giro)
    st.session_state.usar_gap = st.checkbox("🔁 Gap", value=st.session_state.usar_gap)
    st.session_state.usar_sequencia = st.checkbox("📊 Sequência", value=st.session_state.usar_sequencia)
    st.session_state.usar_terminais = st.checkbox("🔢 Terminais", value=st.session_state.usar_terminais)
    st.session_state.usar_simetria = st.checkbox("🔄 Simetria", value=st.session_state.usar_simetria)

with st.sidebar.expander("📋 Tabela de Simetrias", expanded=False):
    st.markdown("""
    | Número | Espelho |
    |--------|---------|
    | 1 | 10 |
    | 10 | 1 |
    | 2 | 20 |
    | 20 | 2 |
    | 3 | 30 |
    | 30 | 3 |
    | 12 | 21 |
    | 21 | 12 |
    | 13 | 31 |
    | 31 | 13 |
    | 23 | 32 |
    | 32 | 23 |
    | 0,11,22,33 | Palíndromos |
    """)

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

# ==========================================
# CONTEÚDO PRINCIPAL
# ==========================================

# Inserção manual
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
c5.metric("🤖 Motores", "7")

if sis.acertos + sis.erros > 0:
    taxa = sis.acertos / (sis.acertos + sis.erros) * 100
    emoji = "🟢" if taxa >= 30 else "🟡" if taxa >= 20 else "🔴"
    st.write(f"{emoji} **Taxa de acerto: {taxa:.1f}%**")

# Entrada atual
st.subheader("🎯 Entrada Atual")
if sis.entrada_ativa:
    e = sis.entrada_ativa
    emoji = "🔥" if e['forca_real'] >= 50 else "🎯" if e['forca_real'] >= 35 else "📊"
    st.info(f"{emoji} **{e['qualidade']}** | Força {e['forca_real']}% | {len(e['numeros_apostar'])} núm. | {e['motor']} (+{e['qtd_motores']-1})")
    st.caption(f"🎯 {', '.join(e.get('estrategias_ativas', [])[:4])}")
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
