import streamlit as st
import json
import os
import requests
import logging
import numpy as np
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import pickle

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_roleta.json"

def salvar_sessao():
    """Salva todos os dados da sessão em arquivo"""
    try:
        session_data = {
            'historico': st.session_state.historico,
            'telegram_token': st.session_state.telegram_token,
            'telegram_chat_id': st.session_state.telegram_chat_id,
            'sistema_acertos': st.session_state.sistema.acertos,
            'sistema_erros': st.session_state.sistema.erros,
            'sistema_estrategias_contador': st.session_state.sistema.estrategias_contador,
            'sistema_historico_desempenho': st.session_state.sistema.historico_desempenho,
            'estrategia_selecionada': st.session_state.sistema.estrategia_selecionada,
            'cluster_historico': list(st.session_state.sistema.estrategia_cluster.historico),
            'nucleo_quente_historico': list(st.session_state.sistema.estrategia_nucleo.historico),
            'pos_sequencia_historico': list(st.session_state.sistema.estrategia_pos.historico),
            'bloco_historico': list(st.session_state.sistema.estrategia_bloco.historico),
            'multiplicador_historico': list(st.session_state.sistema.estrategia_multi.historico),
            'hibrida_historico': list(st.session_state.sistema.estrategia_hibrida.historico)
        }
        
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f)
        
        logging.info("✅ Sessão salva com sucesso")
        return True
    except Exception as e:
        logging.error(f"❌ Erro ao salvar sessão: {e}")
        return False

def carregar_sessao():
    """Carrega todos os dados da sessão do arquivo"""
    try:
        if os.path.exists(SESSION_DATA_PATH):
            with open(SESSION_DATA_PATH, 'rb') as f:
                session_data = pickle.load(f)
            
            st.session_state.historico = session_data.get('historico', [])
            st.session_state.telegram_token = session_data.get('telegram_token', '')
            st.session_state.telegram_chat_id = session_data.get('telegram_chat_id', '')
            
            if 'sistema' in st.session_state:
                st.session_state.sistema.acertos = session_data.get('sistema_acertos', 0)
                st.session_state.sistema.erros = session_data.get('sistema_erros', 0)
                st.session_state.sistema.estrategias_contador = session_data.get('sistema_estrategias_contador', {})
                st.session_state.sistema.historico_desempenho = session_data.get('sistema_historico_desempenho', [])
                st.session_state.sistema.estrategia_selecionada = session_data.get('estrategia_selecionada', 'Híbrida PRO')
                
                # Carrega históricos das novas estratégias
                if hasattr(st.session_state.sistema, 'estrategia_cluster'):
                    st.session_state.sistema.estrategia_cluster.historico = deque(session_data.get('cluster_historico', []), maxlen=50)
                if hasattr(st.session_state.sistema, 'estrategia_nucleo'):
                    st.session_state.sistema.estrategia_nucleo.historico = deque(session_data.get('nucleo_quente_historico', []), maxlen=50)
                if hasattr(st.session_state.sistema, 'estrategia_pos'):
                    st.session_state.sistema.estrategia_pos.historico = deque(session_data.get('pos_sequencia_historico', []), maxlen=30)
                if hasattr(st.session_state.sistema, 'estrategia_bloco'):
                    st.session_state.sistema.estrategia_bloco.historico = deque(session_data.get('bloco_historico', []), maxlen=50)
                if hasattr(st.session_state.sistema, 'estrategia_multi'):
                    st.session_state.sistema.estrategia_multi.historico = deque(session_data.get('multiplicador_historico', []), maxlen=30)
                if hasattr(st.session_state.sistema, 'estrategia_hibrida'):
                    st.session_state.sistema.estrategia_hibrida.historico = deque(session_data.get('hibrida_historico', []), maxlen=50)
            
            logging.info("✅ Sessão carregada com sucesso")
            return True
    except Exception as e:
        logging.error(f"❌ Erro ao carregar sessão: {e}")
    return False

def limpar_sessao():
    """Limpa todos os dados da sessão"""
    try:
        if os.path.exists(SESSION_DATA_PATH):
            os.remove(SESSION_DATA_PATH)
        if os.path.exists(HISTORICO_PATH):
            os.remove(HISTORICO_PATH)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
        logging.info("🗑️ Sessão limpa com sucesso")
    except Exception as e:
        logging.error(f"❌ Erro ao limpar sessão: {e}")

# =============================
# CONFIGURAÇÕES DE NOTIFICAÇÃO
# =============================
def enviar_previsao_simplificada(previsao):
    """Envia notificação de previsão simplificada"""
    try:
        nome = previsao['nome']
        numeros = sorted(previsao['numeros_apostar'])
        
        if 'Cluster' in nome:
            emoji = "🔥"
            msg = f"{emoji} REPETIÇÃO ATIVA!\nNúmero: {previsao.get('numero_gatilho')}"
        elif 'Núcleo Quente' in nome:
            emoji = "🎯"
            msg = f"{emoji} NÚCLEO QUENTE!\nBase: {previsao.get('nucleo', [])[:5]}"
        elif 'Pós-Sequência' in nome:
            emoji = "💣"
            msg = f"{emoji} PÓS-SEQUÊNCIA!\nQuebrou: {previsao.get('numero_quebra')}"
        elif 'Bloco' in nome:
            emoji = "📊"
            msg = f"{emoji} BLOCO {previsao.get('bloco_tipo', '')}!\nInvertendo para: {previsao.get('bloco_alvo', '')}"
        elif 'Multiplicador' in nome:
            emoji = "🚀"
            msg = f"{emoji} CAÇA EXPLOSÃO!\n{previsao.get('rodadas_sem_mult', 0)} rodadas sem spike"
        else:
            emoji = "🧠"
            msg = f"{emoji} HÍBRIDA PRO!\nGatilhos: {previsao.get('gatilhos_ativos', [])}"
        
        st.toast(f"🎯 Nova Previsão", icon="🔥")
        st.warning(f"🔔 {msg}")
        
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            enviar_telegram(f"🔔 PREVISÃO\n{msg}\n📋 Números: {len(numeros)}")
            # Envia números em formato compacto
            metade = len(numeros) // 2
            linha1 = " ".join(map(str, numeros[:metade]))
            linha2 = " ".join(map(str, numeros[metade:]))
            enviar_telegram(f"{emoji} APOSTAR\n{linha1}\n{linha2}")
                
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar previsão: {e}")

def enviar_resultado_simplificado(numero_real, acerto, nome_estrategia, multiplicador=None):
    """Envia notificação de resultado simplificado"""
    try:
        if acerto:
            msg = f"✅ ACERTO!\n🎲 Número: {numero_real}"
        else:
            msg = f"❌ ERRO!\n🎲 Número: {numero_real}"
        
        if multiplicador and multiplicador > 0:
            msg += f"\n⚡ RAIO! {multiplicador}x"
        
        st.toast(f"🎲 Resultado", icon="✅" if acerto else "❌")
        st.success(f"📢 {msg}") if acerto else st.error(f"📢 {msg}")
        
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            enviar_telegram(f"📢 RESULTADO\n{msg}")
            if acerto:
                enviar_telegram(f"🎉 ACERTOU! {numero_real}" + (f" ⚡{multiplicador}x" if multiplicador else ""))
            else:
                enviar_telegram(f"💥 ERROU! {numero_real}")
                
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar resultado: {e}")

def enviar_telegram(mensagem):
    """Envia mensagem para o Telegram"""
    try:
        token = st.session_state.telegram_token
        chat_id = st.session_state.telegram_chat_id
        
        if not token or not chat_id:
            return
            
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": mensagem,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logging.info("Mensagem enviada para Telegram com sucesso")
    except Exception as e:
        logging.error(f"Erro na conexão com Telegram: {e}")

# =============================
# CONFIGURAÇÕES DA API
# =============================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# =============================
# ROLETA BASE (APENAS PARA VIZINHOS)
# =============================
class RoletaBase:
    def __init__(self):
        # Roda europeia (ordem física)
        self.race = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        
    def get_vizinhos(self, numero, raio=2):
        """Retorna vizinhos físicos na roda"""
        if numero not in self.race:
            return []
        
        posicao = self.race.index(numero)
        vizinhos = []
        
        for offset in range(-raio, raio + 1):
            if offset != 0:
                vizinhos.append(self.race[(posicao + offset) % 37])
        
        return vizinhos
    
    def get_oposto(self, numero):
        """Retorna número oposto na roda (aproximado)"""
        if numero not in self.race:
            return None
        posicao = self.race.index(numero)
        return self.race[(posicao + 18) % 37]

# =============================
# ESTRATÉGIA 1: REPETIÇÃO (CLUSTER)
# =============================
class EstrategiaCluster:
    """
    Gatilho: número repetido OU apareceu 2x em até 5 rodadas
    Entrada: mesmo número + vizinhos
    Stop: 2 perdas seguidas
    """
    
    def __init__(self):
        self.roleta = RoletaBase()
        self.historico = deque(maxlen=50)
        self.nome = "🔥 Cluster (Repetição)"
        self.perdas_consecutivas = 0
        
    def adicionar_numero(self, numero):
        self.historico.append(numero)
        
    def analisar(self):
        if len(self.historico) < 3:
            return None
            
        hist_list = list(self.historico)
        ultimo = hist_list[-1]
        
        # Verifica repetição direta
        if len(hist_list) >= 2 and hist_list[-1] == hist_list[-2]:
            return self._gerar_entrada(ultimo, "Repetição direta")
        
        # Verifica 2x em 5 rodadas
        ultimos_5 = hist_list[-5:] if len(hist_list) >= 5 else hist_list
        contagem = Counter(ultimos_5)
        for num, count in contagem.items():
            if count >= 2 and num == ultimo:
                return self._gerar_entrada(num, f"2x em 5 rodadas")
        
        return None
    
    def _gerar_entrada(self, numero, gatilho):
        vizinhos = self.roleta.get_vizinhos(numero, raio=2)
        numeros = list(set([numero] + vizinhos))
        
        return {
            'nome': self.nome,
            'numeros_apostar': sorted(numeros),
            'gatilho': f"🔥 {gatilho}: {numero}",
            'confianca': 'Alta',
            'numero_gatilho': numero,
            'tipo': 'cluster'
        }
    
    def get_analise(self):
        if len(self.historico) < 3:
            return "🔥 Cluster: Aguardando dados..."
        
        hist_list = list(self.historico)
        ultimos_10 = hist_list[-10:] if len(hist_list) >= 10 else hist_list
        
        analise = "🔥 ANÁLISE CLUSTER\n" + "="*40 + "\n"
        analise += f"Últimos: {ultimos_10}\n"
        
        # Detecta repetições
        repeticoes = []
        for i in range(1, len(hist_list)):
            if hist_list[i] == hist_list[i-1]:
                repeticoes.append(hist_list[i])
        
        if repeticoes:
            analise += f"\n📊 Repetições recentes: {repeticoes[-5:]}\n"
        else:
            analise += "\n📊 Nenhuma repetição recente\n"
        
        return analise
    
    def zerar(self):
        self.historico.clear()
        self.perdas_consecutivas = 0

# =============================
# ESTRATÉGIA 2: NÚCLEO QUENTE
# =============================
class EstrategiaNucleoQuente:
    """
    Gatilho: 2 ou mais números quentes aparecem em 5 rodadas
    Entrada: base de números quentes (top 5-7 frequentes)
    Stop: 3 rodadas sem acerto
    """
    
    def __init__(self):
        self.historico = deque(maxlen=50)
        self.nome = "🎯 Núcleo Quente"
        self.numeros_quentes = [33, 14, 17, 30, 25, 32, 8, 7]  # Do seu estudo
        self.perdas_consecutivas = 0
        
    def adicionar_numero(self, numero):
        self.historico.append(numero)
        
    def analisar(self):
        if len(self.historico) < 5:
            return None
            
        hist_list = list(self.historico)
        ultimos_5 = hist_list[-5:]
        
        # Conta quantos números quentes apareceram nas últimas 5 rodadas
        quentes_recentes = [n for n in ultimos_5 if n in self.numeros_quentes]
        
        if len(quentes_recentes) >= 2:
            # Atualiza dinamicamente os mais frequentes do histórico completo
            frequencias = Counter(hist_list)
            top_frequentes = [num for num, _ in frequencias.most_common(7)]
            
            # Combina com os quentes fixos
            base = list(set(self.numeros_quentes + top_frequentes))[:8]
            
            return {
                'nome': self.nome,
                'numeros_apostar': sorted(base),
                'gatilho': f"🎯 {len(quentes_recentes)} quentes em 5 rodadas: {quentes_recentes}",
                'confianca': 'Alta',
                'nucleo': base,
                'tipo': 'nucleo_quente'
            }
        
        return None
    
    def get_analise(self):
        if len(self.historico) < 5:
            return "🎯 Núcleo Quente: Aguardando dados..."
        
        hist_list = list(self.historico)
        frequencias = Counter(hist_list)
        
        analise = "🎯 ANÁLISE NÚCLEO QUENTE\n" + "="*40 + "\n"
        analise += "Top 10 frequências:\n"
        for num, freq in frequencias.most_common(10):
            barra = "█" * min(freq, 20)
            analise += f"  {num:2d}: {barra} {freq}x\n"
        
        ultimos_5 = hist_list[-5:]
        quentes = [n for n in ultimos_5 if n in self.numeros_quentes]
        analise += f"\n🔥 Quentes nas últimas 5: {quentes} ({len(quentes)})\n"
        
        return analise
    
    def zerar(self):
        self.historico.clear()
        self.perdas_consecutivas = 0

# =============================
# ESTRATÉGIA 3: PÓS-SEQUÊNCIA
# =============================
class EstrategiaPosSequencia:
    """
    Gatilho: sequência de repetição termina (ex: 14→14→14 → quebra)
    Entrada: vizinhos do número que repetiu + oposto
    """
    
    def __init__(self):
        self.roleta = RoletaBase()
        self.historico = deque(maxlen=30)
        self.nome = "💣 Pós-Sequência"
        
    def adicionar_numero(self, numero):
        self.historico.append(numero)
        
    def analisar(self):
        if len(self.historico) < 4:
            return None
            
        hist_list = list(self.historico)
        
        # Procura por sequência de repetição que quebrou
        # Ex: 14, 14, 14, X (onde X ≠ 14)
        for i in range(len(hist_list) - 3, len(hist_list) - 1):
            if i >= 2:
                if hist_list[i-2] == hist_list[i-1] == hist_list[i]:
                    numero_rep = hist_list[i]
                    numero_quebra = hist_list[i+1]
                    
                    if numero_quebra != numero_rep:
                        # Sequência quebrou! Gerar entrada
                        vizinhos = self.roleta.get_vizinhos(numero_rep, raio=2)
                        oposto = self.roleta.get_oposto(numero_rep)
                        
                        numeros = list(set(vizinhos))
                        if oposto:
                            numeros.append(oposto)
                        
                        return {
                            'nome': self.nome,
                            'numeros_apostar': sorted(numeros),
                            'gatilho': f"💣 Quebra após {numero_rep}→{numero_rep}→{numero_rep}",
                            'confianca': 'Média-Alta',
                            'numero_quebra': numero_quebra,
                            'numero_repetido': numero_rep,
                            'tipo': 'pos_sequencia'
                        }
        
        return None
    
    def get_analise(self):
        if len(self.historico) < 3:
            return "💣 Pós-Sequência: Aguardando dados..."
        
        hist_list = list(self.historico)
        
        analise = "💣 ANÁLISE PÓS-SEQUÊNCIA\n" + "="*40 + "\n"
        analise += f"Últimos: {hist_list[-10:]}\n"
        
        # Detecta sequências ativas
        if len(hist_list) >= 2:
            ultimo = hist_list[-1]
            penultimo = hist_list[-2]
            if ultimo == penultimo:
                # Conta tamanho da sequência
                seq = 2
                for i in range(len(hist_list)-3, -1, -1):
                    if hist_list[i] == ultimo:
                        seq += 1
                    else:
                        break
                analise += f"\n🔥 Sequência ativa: {ultimo} repetiu {seq}x\n"
        
        return analise
    
    def zerar(self):
        self.historico.clear()

# =============================
# ESTRATÉGIA 4: BLOCO (ALTOS VS BAIXOS)
# =============================
class EstrategiaBloco:
    """
    Gatilho: 4+ números seguidos acima de 19 (ou abaixo)
    Entrada: inverter lado
    Stop: 2 tentativas
    """
    
    def __init__(self):
        self.historico = deque(maxlen=50)
        self.nome = "📊 Bloco (Altos/Baixos)"
        self.perdas_consecutivas = 0
        
    def adicionar_numero(self, numero):
        self.historico.append(numero)
        
    def analisar(self):
        if len(self.historico) < 5:
            return None
            
        hist_list = list(self.historico)
        ultimos = hist_list[-6:]  # Olha 6 para ter margem
        
        # Verifica bloco de altos (>19)
        altos_seguidos = 0
        for n in reversed(ultimos):
            if n > 19:
                altos_seguidos += 1
            else:
                break
        
        # Verifica bloco de baixos (≤18)
        baixos_seguidos = 0
        for n in reversed(ultimos):
            if n <= 18:
                baixos_seguidos += 1
            else:
                break
        
        if altos_seguidos >= 4:
            # Bloco de altos - apostar em baixos
            numeros = list(range(0, 19))  # 0-18
            return {
                'nome': self.nome,
                'numeros_apostar': numeros,
                'gatilho': f"📊 {altos_seguidos} altos seguidos - invertendo para BAIXOS (0-18)",
                'confianca': 'Média',
                'bloco_tipo': 'Altos',
                'bloco_alvo': 'Baixos (0-18)',
                'tipo': 'bloco'
            }
        
        if baixos_seguidos >= 4:
            # Bloco de baixos - apostar em altos
            numeros = list(range(19, 37))  # 19-36
            return {
                'nome': self.nome,
                'numeros_apostar': numeros,
                'gatilho': f"📊 {baixos_seguidos} baixos seguidos - invertendo para ALTOS (19-36)",
                'confianca': 'Média',
                'bloco_tipo': 'Baixos',
                'bloco_alvo': 'Altos (19-36)',
                'tipo': 'bloco'
            }
        
        return None
    
    def get_analise(self):
        if len(self.historico) < 5:
            return "📊 Bloco: Aguardando dados..."
        
        hist_list = list(self.historico)
        
        analise = "📊 ANÁLISE BLOCO\n" + "="*40 + "\n"
        analise += f"Últimos: {hist_list[-10:]}\n"
        
        # Classifica últimos
        altos = sum(1 for n in hist_list[-10:] if n > 19)
        baixos = sum(1 for n in hist_list[-10:] if n <= 18)
        
        analise += f"\nÚltimas 10 rodadas:\n"
        analise += f"  Altos (19-36): {altos}\n"
        analise += f"  Baixos (0-18): {baixos}\n"
        
        # Detecta bloco atual
        bloco_atual = "Altos" if hist_list[-1] > 19 else "Baixos"
        tamanho = 1
        for i in range(len(hist_list)-2, -1, -1):
            if (bloco_atual == "Altos" and hist_list[i] > 19) or (bloco_atual == "Baixos" and hist_list[i] <= 18):
                tamanho += 1
            else:
                break
        
        analise += f"\n📈 Bloco atual: {bloco_atual} ({tamanho} seguidos)\n"
        
        return analise
    
    def zerar(self):
        self.historico.clear()
        self.perdas_consecutivas = 0

# =============================
# ESTRATÉGIA 5: MULTIPLICADOR (CAÇA EXPLOSÃO)
# =============================
class EstrategiaMultiplicador:
    """
    Gatilho: 5-8 rodadas sem multiplicador alto (>500x)
    Entrada: apostar aberto (8-12 números incluindo 0, quentes, últimos)
    """
    
    def __init__(self):
        self.historico = deque(maxlen=30)
        self.historico_mult = deque(maxlen=30)  # Guarda multiplicadores
        self.nome = "🚀 Caça Explosão"
        self.numeros_quentes = [33, 14, 17, 30, 25, 32, 8, 7]
        
    def adicionar_numero(self, numero, multiplicador=None):
        self.historico.append(numero)
        self.historico_mult.append(multiplicador if multiplicador else 0)
        
    def analisar(self):
        if len(self.historico) < 8:
            return None
            
        hist_list = list(self.historico)
        mult_list = list(self.historico_mult)
        
        # Conta rodadas sem multiplicador alto (>500x)
        rodadas_sem = 0
        for m in reversed(mult_list):
            if m and m >= 500:
                break
            rodadas_sem += 1
        
        if 5 <= rodadas_sem <= 12:
            # Gera conjunto aberto
            numeros = set()
            numeros.add(0)  # Sempre inclui 0
            
            # Adiciona números quentes
            for n in self.numeros_quentes[:4]:
                numeros.add(n)
            
            # Adiciona últimos números
            for n in hist_list[-3:]:
                numeros.add(n)
            
            # Completa até 10-12 números
            frequencias = Counter(hist_list)
            for num, _ in frequencias.most_common(5):
                numeros.add(num)
                if len(numeros) >= 12:
                    break
            
            return {
                'nome': self.nome,
                'numeros_apostar': sorted(list(numeros))[:12],
                'gatilho': f"🚀 {rodadas_sem} rodadas sem multiplicador >500x",
                'confianca': 'Alta para Spike',
                'rodadas_sem_mult': rodadas_sem,
                'tipo': 'multiplicador'
            }
        
        return None
    
    def get_analise(self):
        if len(self.historico) < 5:
            return "🚀 Multiplicador: Aguardando dados..."
        
        mult_list = list(self.historico_mult)
        
        analise = "🚀 ANÁLISE MULTIPLICADOR\n" + "="*40 + "\n"
        
        # Conta rodadas sem spike
        rodadas_sem = 0
        for m in reversed(mult_list):
            if m and m >= 500:
                break
            rodadas_sem += 1
        
        analise += f"📊 Rodadas sem spike (>500x): {rodadas_sem}\n"
        
        # Mostra últimos multiplicadores
        if any(mult_list):
            ultimos_mult = [m for m in mult_list[-10:] if m]
            if ultimos_mult:
                analise += f"⚡ Últimos multiplicadores: {ultimos_mult}\n"
        
        if 5 <= rodadas_sem <= 12:
            analise += "\n🟢 GATILHO ATIVO! Probabilidade de spike elevada!\n"
        elif rodadas_sem > 12:
            analise += "\n🔴 Muitas rodadas sem spike - cautela!\n"
        
        return analise
    
    def zerar(self):
        self.historico.clear()
        self.historico_mult.clear()

# =============================
# ESTRATÉGIA 6: HÍBRIDA PRO (RECOMENDADA)
# =============================
class EstrategiaHibrida:
    """
    Combina todos os gatilhos:
    - Repetição OU núcleo ativo
    - Base: último número + 2 vizinhos + 3 quentes + 1 atrasado
    """
    
    def __init__(self):
        self.roleta = RoletaBase()
        self.historico = deque(maxlen=50)
        self.nome = "🧠 Híbrida PRO"
        self.numeros_quentes = [33, 14, 17, 30, 25, 32, 8, 7]
        
    def adicionar_numero(self, numero):
        self.historico.append(numero)
        
    def analisar(self):
        if len(self.historico) < 5:
            return None
            
        hist_list = list(self.historico)
        ultimo = hist_list[-1]
        
        # Verifica gatilhos
        gatilhos = []
        
        # Gatilho 1: Repetição
        if len(hist_list) >= 2 and hist_list[-1] == hist_list[-2]:
            gatilhos.append("Repetição")
        
        # Gatilho 2: Núcleo ativo (2+ quentes em 5 rodadas)
        ultimos_5 = hist_list[-5:]
        quentes_5 = [n for n in ultimos_5 if n in self.numeros_quentes]
        if len(quentes_5) >= 2:
            gatilhos.append(f"Núcleo ({len(quentes_5)} quentes)")
        
        # Se não tem gatilho, não gera entrada
        if not gatilhos:
            return None
        
        # Monta base híbrida
        numeros = set()
        
        # 1. Último número
        numeros.add(ultimo)
        
        # 2. Vizinhos do último
        vizinhos = self.roleta.get_vizinhos(ultimo, raio=2)
        numeros.update(vizinhos[:2])
        
        # 3. Números quentes (top 3)
        frequencias = Counter(hist_list)
        quentes_dinamicos = [num for num, _ in frequencias.most_common(3)]
        numeros.update(quentes_dinamicos)
        
        # 4. Número atrasado (não saiu há mais tempo)
        todos = set(range(37))
        presentes = set(hist_list)
        ausentes = todos - presentes
        if ausentes:
            # Pega o que não saiu há mais tempo (considerando ordem)
            for num in range(37):
                if num not in hist_list[-30:]:
                    numeros.add(num)
                    break
        
        # Limita a 12 números
        numeros_final = sorted(list(numeros))[:12]
        
        return {
            'nome': self.nome,
            'numeros_apostar': numeros_final,
            'gatilho': f"🧠 Gatilhos: {', '.join(gatilhos)}",
            'confianca': 'Alta',
            'gatilhos_ativos': gatilhos,
            'tipo': 'hibrida'
        }
    
    def get_analise(self):
        if len(self.historico) < 5:
            return "🧠 Híbrida: Aguardando dados..."
        
        hist_list = list(self.historico)
        
        analise = "🧠 ANÁLISE HÍBRIDA PRO\n" + "="*40 + "\n"
        analise += f"Último: {hist_list[-1]}\n"
        
        # Verifica gatilhos ativos
        gatilhos = []
        
        if len(hist_list) >= 2 and hist_list[-1] == hist_list[-2]:
            gatilhos.append("✅ Repetição ativa")
        
        ultimos_5 = hist_list[-5:]
        quentes_5 = [n for n in ultimos_5 if n in self.numeros_quentes]
        if len(quentes_5) >= 2:
            gatilhos.append(f"✅ Núcleo ativo ({len(quentes_5)} quentes)")
        
        analise += "\n🎯 Status dos Gatilhos:\n"
        if gatilhos:
            for g in gatilhos:
                analise += f"  {g}\n"
            analise += "\n🟢 CONDIÇÕES ATENDIDAS - ENTRADA ATIVA!\n"
        else:
            analise += "  ❌ Nenhum gatilho ativo\n"
            analise += "\n🔴 Aguardando condições...\n"
        
        # Mostra frequências
        frequencias = Counter(hist_list)
        analise += f"\n📊 Top 5 frequências: {frequencias.most_common(5)}\n"
        
        return analise
    
    def zerar(self):
        self.historico.clear()

# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaRoletaPro:
    def __init__(self):
        # NOVAS ESTRATÉGIAS (baseadas no seu estudo)
        self.estrategia_cluster = EstrategiaCluster()
        self.estrategia_nucleo = EstrategiaNucleoQuente()
        self.estrategia_pos = EstrategiaPosSequencia()
        self.estrategia_bloco = EstrategiaBloco()
        self.estrategia_multi = EstrategiaMultiplicador()
        self.estrategia_hibrida = EstrategiaHibrida()
        
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.estrategia_selecionada = "Híbrida PRO"  # Default recomendada
        
    def set_estrategia(self, estrategia):
        self.estrategia_selecionada = estrategia
        salvar_sessao()
    
    def processar_novo_numero(self, numero_data):
        """Processa novo número da API"""
        if isinstance(numero_data, dict):
            numero_real = numero_data['number']
            lucky = numero_data.get('luckyNumbers', [])
            mult = numero_data.get('luckyMultipliers', {}).get(numero_real) if numero_real in lucky else None
        else:
            numero_real = numero_data
            lucky = []
            mult = None
        
        # Verifica resultado da previsão anterior
        if self.previsao_ativa:
            acerto = numero_real in self.previsao_ativa.get('numeros_apostar', [])
            nome = self.previsao_ativa['nome']
            
            if nome not in self.estrategias_contador:
                self.estrategias_contador[nome] = {'acertos': 0, 'total': 0}
            self.estrategias_contador[nome]['total'] += 1
            
            if acerto:
                self.estrategias_contador[nome]['acertos'] += 1
                self.acertos += 1
            else:
                self.erros += 1
            
            enviar_resultado_simplificado(numero_real, acerto, nome, mult)
            
            self.historico_desempenho.append({
                'numero': numero_real,
                'acerto': acerto,
                'estrategia': nome,
                'multiplicador': mult
            })
            
            self.previsao_ativa = None
        
        # Adiciona número a todas as estratégias
        self.estrategia_cluster.adicionar_numero(numero_real)
        self.estrategia_nucleo.adicionar_numero(numero_real)
        self.estrategia_pos.adicionar_numero(numero_real)
        self.estrategia_bloco.adicionar_numero(numero_real)
        self.estrategia_multi.adicionar_numero(numero_real, mult)
        self.estrategia_hibrida.adicionar_numero(numero_real)
        
        # Gera nova previsão baseada na estratégia selecionada
        nova = None
        if self.estrategia_selecionada == "Cluster":
            nova = self.estrategia_cluster.analisar()
        elif self.estrategia_selecionada == "Núcleo Quente":
            nova = self.estrategia_nucleo.analisar()
        elif self.estrategia_selecionada == "Pós-Sequência":
            nova = self.estrategia_pos.analisar()
        elif self.estrategia_selecionada == "Bloco":
            nova = self.estrategia_bloco.analisar()
        elif self.estrategia_selecionada == "Multiplicador":
            nova = self.estrategia_multi.analisar()
        elif self.estrategia_selecionada == "Híbrida PRO":
            nova = self.estrategia_hibrida.analisar()
        
        if nova:
            self.previsao_ativa = nova
            enviar_previsao_simplificada(nova)
    
    def zerar_estatisticas(self):
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.historico_desempenho = []
        self.estrategia_cluster.zerar()
        self.estrategia_nucleo.zerar()
        self.estrategia_pos.zerar()
        self.estrategia_bloco.zerar()
        self.estrategia_multi.zerar()
        self.estrategia_hibrida.zerar()
        salvar_sessao()
    
    def get_status(self):
        return {
            'estrategia_atual': self.estrategia_selecionada,
            'acertos': self.acertos,
            'erros': self.erros,
            'total': self.acertos + self.erros
        }

# =============================
# FUNÇÕES AUXILIARES
# =============================
def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    try:
        with open(caminho, "w") as f:
            json.dump(historico, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")

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
    except Exception as e:
        logging.error(f"Erro ao extrair raios: {e}")
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
    except Exception as e:
        logging.error(f"Erro ao buscar resultado: {e}")
        return None

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="IA Roleta — Estratégias PRO", layout="centered")
st.title("🎯 IA Roleta — Sistema Multi-Estratégias PRO")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaRoletaPro()

sessao_carregada = carregar_sessao()

if "historico" not in st.session_state:
    if not sessao_carregada and os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                st.session_state.historico = json.load(f)
        except:
            st.session_state.historico = []
    elif not sessao_carregada:
        st.session_state.historico = []

if "telegram_token" not in st.session_state and not sessao_carregada:
    st.session_state.telegram_token = ""
if "telegram_chat_id" not in st.session_state and not sessao_carregada:
    st.session_state.telegram_chat_id = ""

# Sidebar
st.sidebar.title("⚙️ Configurações")

with st.sidebar.expander("💾 Gerenciamento", expanded=False):
    if st.button("💾 Salvar Sessão", use_container_width=True):
        salvar_sessao()
        st.success("✅ Sessão salva!")
    if st.button("🔄 Carregar Sessão", use_container_width=True):
        if carregar_sessao():
            st.success("✅ Sessão carregada!")
            st.rerun()
    if st.button("🗑️ Zerar Tudo", type="secondary", use_container_width=True):
        if st.checkbox("Confirmar"):
            st.session_state.sistema.zerar_estatisticas()
            st.error("🗑️ Zerado!")
            st.rerun()

with st.sidebar.expander("🔔 Telegram", expanded=False):
    token = st.text_input("Token:", value=st.session_state.telegram_token, type="password")
    chat = st.text_input("Chat ID:", value=st.session_state.telegram_chat_id)
    if st.button("Salvar Telegram"):
        st.session_state.telegram_token = token
        st.session_state.telegram_chat_id = chat
        salvar_sessao()
        st.success("✅ Salvo!")

# Seleção de estratégia
estrategias_disponiveis = ["Híbrida PRO", "Cluster", "Núcleo Quente", "Pós-Sequência", "Bloco", "Multiplicador"]
estrategia = st.sidebar.selectbox(
    "🎯 Estratégia:",
    estrategias_disponiveis,
    key="estrategia_selecionada"
)
if estrategia != st.session_state.sistema.estrategia_selecionada:
    st.session_state.sistema.set_estrategia(estrategia)

# Análise da estratégia selecionada
with st.sidebar.expander(f"🔍 Análise - {estrategia}", expanded=True):
    if estrategia == "Cluster":
        analise = st.session_state.sistema.estrategia_cluster.get_analise()
    elif estrategia == "Núcleo Quente":
        analise = st.session_state.sistema.estrategia_nucleo.get_analise()
    elif estrategia == "Pós-Sequência":
        analise = st.session_state.sistema.estrategia_pos.get_analise()
    elif estrategia == "Bloco":
        analise = st.session_state.sistema.estrategia_bloco.get_analise()
    elif estrategia == "Multiplicador":
        analise = st.session_state.sistema.estrategia_multi.get_analise()
    else:
        analise = st.session_state.sistema.estrategia_hibrida.get_analise()
    st.text(analise)

# Inserção manual
st.subheader("✍️ Inserir Sorteios")
entrada = st.text_input("Números (0-36) separados por espaço:")
if st.button("Adicionar") and entrada:
    try:
        nums = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
        for n in nums:
            item = {"number": n, "timestamp": f"manual_{len(st.session_state.historico)}", "luckyNumbers": [], "luckyMultipliers": {}}
            st.session_state.historico.append(item)
            st.session_state.sistema.processar_novo_numero(item)
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()
        st.success(f"{len(nums)} números adicionados!")
        st.rerun()
    except Exception as e:
        st.error(f"Erro: {e}")

# Auto-refresh para buscar API
st_autorefresh(interval=3000, key="refresh")

# Busca resultado da API
resultado = fetch_latest_result()
if st.session_state.historico:
    ultimo_ts = st.session_state.historico[-1].get("timestamp") if st.session_state.historico else None
else:
    ultimo_ts = None

if resultado and resultado.get("timestamp") and resultado["timestamp"] != ultimo_ts:
    numero_atual = resultado.get("number")
    if numero_atual is not None:
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
            fmt.append(f"⚡ **{n}** ({mult}x)" if mult else f"⚡ **{n}**")
        else:
            fmt.append(str(n))
    st.write(" ".join(fmt))
else:
    st.write("Nenhum número")

# Status
status = st.session_state.sistema.get_status()
col1, col2, col3 = st.columns(3)
col1.metric("🎯 Estratégia", status['estrategia_atual'])
col2.metric("🟢 Acertos", status['acertos'])
col3.metric("🔴 Erros", status['erros'])

# Previsão Ativa
st.subheader("🎯 Previsão Ativa")
sistema = st.session_state.sistema

if sistema.previsao_ativa:
    p = sistema.previsao_ativa
    st.success(f"**{p['nome']}**")
    st.info(f"📋 **Gatilho:** {p['gatilho']}")
    st.write(f"**🔢 Números ({len(p['numeros_apostar'])}):**")
    
    # Mostra números em formato amigável
    nums = sorted(p['numeros_apostar'])
    colunas = st.columns(4)
    for i, num in enumerate(nums):
        colunas[i % 4].write(f"**{num}**")
else:
    st.info(f"🎲 Aguardando condições para **{estrategia}**...")

# Desempenho
st.subheader("📈 Desempenho")
total = sistema.acertos + sistema.erros
taxa = (sistema.acertos / total * 100) if total > 0 else 0.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("🟢 Acertos", sistema.acertos)
c2.metric("🔴 Erros", sistema.erros)
c3.metric("📊 Total", total)
c4.metric("✅ Taxa", f"{taxa:.1f}%")

if sistema.estrategias_contador:
    st.write("**📊 Performance por Estratégia:**")
    for nome, dados in sistema.estrategias_contador.items():
        if dados['total'] > 0:
            tx = dados['acertos'] / dados['total'] * 100
            cor = "🟢" if tx >= 50 else "🟡" if tx >= 30 else "🔴"
            st.write(f"{cor} {nome}: {dados['acertos']}/{dados['total']} ({tx:.1f}%)")

if sistema.historico_desempenho:
    st.write("**🔍 Últimas Conferências:**")
    for r in sistema.historico_desempenho[-5:]:
        emoji = "🎉" if r['acerto'] else "❌"
        mult = f" ⚡{r['multiplicador']}x" if r.get('multiplicador') and r['acerto'] else ""
        st.write(f"{emoji} {r['estrategia']}: {r['numero']}{mult}")

# Download
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        st.download_button("📥 Baixar histórico", data=f.read(), file_name="historico_roleta.json")

salvar_sessao()
