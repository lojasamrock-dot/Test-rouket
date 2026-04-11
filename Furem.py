import streamlit as st
import json
import os
import requests
import logging
import numpy as np
from collections import deque, Counter
import joblib
from streamlit_autorefresh import st_autorefresh
import pickle

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data_triangulo_mesa.pkl"
HISTORICO_PATH = "historico_triangulo_mesa.json"

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
            'sistema_contador_sorteios_global': st.session_state.sistema.contador_sorteios_global,
            'sistema_sequencia_erros': st.session_state.sistema.sequencia_erros,
            'sistema_ultima_estrategia_erro': st.session_state.sistema.ultima_estrategia_erro,
            'sistema_sequencia_acertos': st.session_state.sistema.sequencia_acertos,
            'triangulo_historico': list(st.session_state.sistema.estrategia_triangulo.historico),
            'triangulo_stats': st.session_state.sistema.estrategia_triangulo.stats_triangulos,
            'triangulo_historico_entradas': st.session_state.sistema.estrategia_triangulo.historico_entradas,
            'triangulo_ultimo_gatilho': st.session_state.sistema.estrategia_triangulo.ultimo_gatilho,
            'triangulo_sequencia': list(st.session_state.sistema.estrategia_triangulo.sequencia_triangulos),
            'triangulo_padroes': st.session_state.sistema.estrategia_triangulo.padroes_detectados,
            'triangulo_max_triangulos': st.session_state.sistema.estrategia_triangulo.max_triangulos_por_aposta,
            'triangulo_erros_por_triangulo': st.session_state.sistema.estrategia_triangulo.erros_por_triangulo,
            'triangulo_ultimo_erro': st.session_state.sistema.estrategia_triangulo.ultimo_erro
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
            
            if not isinstance(session_data, dict):
                logging.error("❌ Dados de sessão corrompidos")
                return False
                
            chaves_essenciais = ['historico', 'sistema_acertos', 'sistema_erros']
            if not all(chave in session_data for chave in chaves_essenciais):
                logging.error("❌ Dados de sessão incompletos")
                return False
                
            st.session_state.historico = session_data.get('historico', [])
            st.session_state.telegram_token = session_data.get('telegram_token', '')
            st.session_state.telegram_chat_id = session_data.get('telegram_chat_id', '')
            
            if 'sistema' in st.session_state:
                st.session_state.sistema.acertos = session_data.get('sistema_acertos', 0)
                st.session_state.sistema.erros = session_data.get('sistema_erros', 0)
                st.session_state.sistema.estrategias_contador = session_data.get('sistema_estrategias_contador', {})
                st.session_state.sistema.historico_desempenho = session_data.get('sistema_historico_desempenho', [])
                st.session_state.sistema.contador_sorteios_global = session_data.get('sistema_contador_sorteios_global', 0)
                st.session_state.sistema.sequencia_erros = session_data.get('sistema_sequencia_erros', 0)
                st.session_state.sistema.ultima_estrategia_erro = session_data.get('sistema_ultima_estrategia_erro', '')
                st.session_state.sistema.sequencia_acertos = session_data.get('sistema_sequencia_acertos', 0)
                
                triangulo_historico = session_data.get('triangulo_historico', [])
                st.session_state.sistema.estrategia_triangulo.historico = deque(triangulo_historico, maxlen=50)
                
                triangulo_stats = session_data.get('triangulo_stats', {})
                
                for triangulo in st.session_state.sistema.estrategia_triangulo.triangulo_para_numeros.keys():
                    if triangulo not in triangulo_stats:
                        triangulo_stats[triangulo] = {
                            'acertos': 0, 'tentativas': 0,
                            'ultimo_sorteio': -1, 'ultimos_10': deque(maxlen=10),
                            'repeticoes': 0, 'sequencia_atual': 0,
                            'erros_consecutivos': 0, 'atraso': 0
                        }
                    else:
                        if 'repeticoes' not in triangulo_stats[triangulo]:
                            triangulo_stats[triangulo]['repeticoes'] = 0
                        if 'sequencia_atual' not in triangulo_stats[triangulo]:
                            triangulo_stats[triangulo]['sequencia_atual'] = 0
                        if 'erros_consecutivos' not in triangulo_stats[triangulo]:
                            triangulo_stats[triangulo]['erros_consecutivos'] = 0
                        if 'atraso' not in triangulo_stats[triangulo]:
                            triangulo_stats[triangulo]['atraso'] = 0
                        if 'ultimos_10' not in triangulo_stats[triangulo]:
                            triangulo_stats[triangulo]['ultimos_10'] = deque(maxlen=10)
                        elif isinstance(triangulo_stats[triangulo]['ultimos_10'], list):
                            triangulo_stats[triangulo]['ultimos_10'] = deque(triangulo_stats[triangulo]['ultimos_10'], maxlen=10)
                
                st.session_state.sistema.estrategia_triangulo.stats_triangulos = triangulo_stats
                st.session_state.sistema.estrategia_triangulo.historico_entradas = session_data.get('triangulo_historico_entradas', [])
                st.session_state.sistema.estrategia_triangulo.ultimo_gatilho = session_data.get('triangulo_ultimo_gatilho', None)
                st.session_state.sistema.estrategia_triangulo.sequencia_triangulos = deque(session_data.get('triangulo_sequencia', []), maxlen=10)
                st.session_state.sistema.estrategia_triangulo.padroes_detectados = session_data.get('triangulo_padroes', [])
                st.session_state.sistema.estrategia_triangulo.erros_por_triangulo = session_data.get('triangulo_erros_por_triangulo', {})
                st.session_state.sistema.estrategia_triangulo.ultimo_erro = session_data.get('triangulo_ultimo_erro', None)
                
                if 'triangulo_max_triangulos' in session_data:
                    st.session_state.sistema.estrategia_triangulo.max_triangulos_por_aposta = session_data['triangulo_max_triangulos']
            
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
def enviar_previsao_super_simplificada(previsao):
    """Envia notificação de previsão super simplificada"""
    try:
        triangulos_info = previsao.get('triangulos', [])
        confianca = previsao.get('confianca_geral', 'Média')
        
        if len(triangulos_info) == 1:
            mensagem = f"🔺 TRIÂNGULO {triangulos_info[0]} - CONFIANÇA {confianca.upper()}"
        else:
            triangulos_str = ", ".join(triangulos_info)
            mensagem = f"🔺 TRIÂNGULOS [{triangulos_str}] - {len(triangulos_info)} ativos - CONFIANÇA {confianca.upper()}"
        
        if previsao.get('gatilho'):
            mensagem += f"\n📊 {previsao['gatilho']}"
        
        st.toast(f"🎯 PREVISÃO CONFIRMADA", icon="🔥")
        st.warning(f"🔔 {mensagem}")
        
        if 'telegram_token' in st.session_state and 'telegram_chat_id' in st.session_state:
            if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                enviar_alerta_numeros_simplificado(previsao)
                enviar_telegram(f"🚨 PREVISÃO ATIVA\n{mensagem}")
                
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar previsão: {e}")

def enviar_alerta_numeros_simplificado(previsao):
    """Envia alerta alternativo super simplificado com os números para apostar"""
    try:
        numeros_apostar = sorted(previsao['numeros_apostar'])
        
        metade = len(numeros_apostar) // 2
        linha1 = " ".join(map(str, numeros_apostar[:metade]))
        linha2 = " ".join(map(str, numeros_apostar[metade:]))
            
        mensagem_simplificada = f"🔺 APOSTAR AGORA\n{linha1}\n{linha2}"
        
        enviar_telegram(mensagem_simplificada)
        logging.info("🔔 Alerta simplificado enviado para Telegram")
        
    except Exception as e:
        logging.error(f"Erro ao enviar alerta simplificado: {e}")

def enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada=None):
    """Envia notificação de resultado super simplificado"""
    try:
        if acerto:
            mensagem = f"✅ ACERTO TRIÂNGULO!\n🎲 Número: {numero_real}"
            if zona_acertada:
                mensagem += f"\n🔺 Triângulo: {zona_acertada}"
        else:
            mensagem = f"❌ Erro\n🎲 Número: {numero_real}"
        
        st.toast(f"🎲 Resultado", icon="✅" if acerto else "❌")
        st.success(f"📢 {mensagem}") if acerto else st.error(f"📢 {mensagem}")
        
        if 'telegram_token' in st.session_state and 'telegram_chat_id' in st.session_state:
            if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                enviar_telegram(f"📢 RESULTADO\n{mensagem}")
                enviar_alerta_conferencia_simplificado(numero_real, acerto, nome_estrategia)
                
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar resultado: {e}")

def enviar_alerta_conferencia_simplificado(numero_real, acerto, nome_estrategia):
    """Envia alerta de conferência super simplificado"""
    try:
        if acerto:
            mensagem = f"🎉 ACERTOU! {numero_real}"
        else:
            mensagem = f"💥 ERROU! {numero_real}"
            
        enviar_telegram(mensagem)
        logging.info("🔔 Alerta de conferência enviado para Telegram")
        
    except Exception as e:
        logging.error(f"Erro ao enviar alerta de conferência: {e}")

def enviar_telegram(mensagem):
    """Envia mensagem para o Telegram"""
    try:
        token = st.session_state.telegram_token
        chat_id = st.session_state.telegram_chat_id
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": mensagem,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logging.info("Mensagem enviada para Telegram com sucesso")
        else:
            logging.error(f"Erro ao enviar para Telegram: {response.status_code}")
    except Exception as e:
        logging.error(f"Erro na conexão com Telegram: {e}")

# =============================
# CONFIGURAÇÕES
# =============================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# =============================
# SISTEMA DE SELEÇÃO INTELIGENTE DE NÚMEROS
# =============================
class SistemaSelecaoInteligente:
    def __init__(self):
        self.mesa_layout = self._criar_layout_mesa()
        
    def _criar_layout_mesa(self):
        """Cria o layout da mesa para referência de vizinhança"""
        # Coluna 1: números que terminam com 1,4,7,0 (mas 0 é especial)
        col1 = [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34]
        col2 = [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35]
        col3 = [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]
        
        return {'col1': col1, 'col2': col2, 'col3': col3}
    
    def selecionar_melhores_15_numeros(self, numeros_candidatos, historico):
        if len(numeros_candidatos) <= 15:
            return numeros_candidatos
            
        scores = {}
        for numero in numeros_candidatos:
            scores[numero] = self.calcular_score_numero(numero, historico)
        
        numeros_ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        melhores_15 = [num for num, score in numeros_ordenados[:15]]
        
        logging.info(f"🎯 Seleção Inteligente: {len(numeros_candidatos)} → 15 números")
        return melhores_15
    
    def calcular_score_numero(self, numero, historico):
        score_total = 0
        
        score_frequencia = self.calcular_score_frequencia(numero, historico)
        score_total += score_frequencia * 0.45
        
        score_posicao = self.calcular_score_posicao_mesa(numero, historico)
        score_total += score_posicao * 0.20
        
        score_vizinhos = self.calcular_score_vizinhos(numero, historico)
        score_total += score_vizinhos * 0.25
        
        score_tendencia = self.calcular_score_tendencia(numero, historico)
        score_total += score_tendencia * 0.10
        
        return score_total
    
    def calcular_score_frequencia(self, numero, historico):
        if len(historico) < 3:
            return 0.7
            
        historico_lista = list(historico)
        
        janela_curta = historico_lista[-8:] if len(historico_lista) >= 8 else historico_lista
        freq_curta = sum(1 for n in janela_curta if n == numero) / len(janela_curta)
        
        janela_media = historico_lista[-20:] if len(historico_lista) >= 20 else historico_lista
        freq_media = sum(1 for n in janela_media if n == numero) / len(janela_media)
        
        janela_longa = historico_lista[-40:] if len(historico_lista) >= 40 else historico_lista
        freq_longa = sum(1 for n in janela_longa if n == numero) / len(janela_longa)
        
        score = (freq_curta * 0.7 + freq_media * 0.2 + freq_longa * 0.1)
        return min(score * 4, 1.0)
    
    def calcular_score_posicao_mesa(self, numero, historico):
        """Calcula score baseado na posição na mesa"""
        if len(historico) < 3:
            return 0.5
        
        # Verifica se o número está em uma coluna quente
        if numero == 0:
            return 0.5
            
        if numero in self.mesa_layout['col1']:
            coluna = 'col1'
        elif numero in self.mesa_layout['col2']:
            coluna = 'col2'
        else:
            coluna = 'col3'
        
        # Conta frequência da coluna nos últimos 10 giros
        ultimos_10 = list(historico)[-10:]
        count_coluna = 0
        for n in ultimos_10:
            if n in self.mesa_layout[coluna]:
                count_coluna += 1
        
        return min(count_coluna / 10, 1.0)
    
    def calcular_score_vizinhos(self, numero, historico):
        if len(historico) < 5:
            return 0.5
            
        # Vizinhos na mesa (acima, abaixo, laterais)
        vizinhos = self.get_vizinhos_mesa(numero)
        
        ultimos_15 = list(historico)[-15:] if len(historico) >= 15 else list(historico)
        count_vizinhos_recentes = sum(1 for n in ultimos_15 if n in vizinhos)
        
        score = min(count_vizinhos_recentes / len(ultimos_15) * 2, 1.0)
        return score
    
    def get_vizinhos_mesa(self, numero):
        """Retorna vizinhos na mesa (acima, abaixo, esquerda, direita)"""
        if numero == 0:
            return [1, 2, 3]
        
        # Encontra a linha e coluna do número
        linha = (numero - 1) // 3 if numero > 0 else 0
        coluna = (numero - 1) % 3 if numero > 0 else 0
        
        vizinhos = []
        
        # Acima
        if linha > 0:
            vizinhos.append(linha * 3 + coluna + 1)
        
        # Abaixo
        if linha < 11:
            vizinhos.append((linha + 1) * 3 + coluna + 1)
        
        # Esquerda
        if coluna > 0:
            vizinhos.append(linha * 3 + coluna)
        
        # Direita
        if coluna < 2:
            vizinhos.append(linha * 3 + coluna + 2)
        
        return vizinhos
    
    def calcular_score_tendencia(self, numero, historico):
        if len(historico) < 10:
            return 0.5
            
        historico_lista = list(historico)
        
        segmento_recente = historico_lista[-5:]
        segmento_anterior = historico_lista[-10:-5] if len(historico_lista) >= 10 else historico_lista[:5]
        
        freq_recente = sum(1 for n in segmento_recente if n == numero) / len(segmento_recente)
        freq_anterior = sum(1 for n in segmento_anterior if n == numero) / len(segmento_anterior) if segmento_anterior else 0
        
        if freq_anterior == 0:
            tendencia = 1.0 if freq_recente > 0 else 0.5
        else:
            tendencia = min(freq_recente / freq_anterior, 2.0)
            
        return tendencia * 0.5

# =============================
# CLASSE PRINCIPAL DA ROLETA (APENAS PARA VIZINHOS NA MESA)
# =============================
class RoletaInteligente:
    def __init__(self):
        # Layout da mesa para referência
        self.col1 = [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34]
        self.col2 = [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35]
        self.col3 = [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]
        self.zero = 0
        
    def get_vizinhos_mesa(self, numero, raio=1):
        """Retorna vizinhos na mesa (acima, abaixo, esquerda, direita)"""
        if numero == 0:
            return [1, 2, 3]
        
        linha = (numero - 1) // 3
        coluna = (numero - 1) % 3
        
        vizinhos = []
        
        # Vizinhos na mesma linha
        if coluna > 0:
            vizinhos.append(linha * 3 + coluna)
        if coluna < 2:
            vizinhos.append(linha * 3 + coluna + 2)
        
        # Vizinhos acima e abaixo
        if linha > 0:
            vizinhos.append((linha - 1) * 3 + coluna + 1)
        if linha < 11:
            vizinhos.append((linha + 1) * 3 + coluna + 1)
        
        return vizinhos

# =============================
# ESTRATÉGIA TRIÂNGULO GEOMÉTRICO DA MESA v10
# =============================
class EstrategiaTrianguloGeometrico:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=50)
        self.nome = "Triângulo Geométrico Mesa v10"
        
        # Mapeamento: cada número pertence a triângulos geométricos na mesa
        self.numero_para_triangulos = self._criar_triangulos_mesa()
        
        # Mapeamento reverso: triângulo -> lista de números
        self.triangulo_para_numeros = {}
        for num, triangulos in self.numero_para_triangulos.items():
            for triangulo_key in triangulos:
                if triangulo_key not in self.triangulo_para_numeros:
                    self.triangulo_para_numeros[triangulo_key] = []
                if num not in self.triangulo_para_numeros[triangulo_key]:
                    self.triangulo_para_numeros[triangulo_key].append(num)
        
        # Ordenar números de cada triângulo
        for triangulo in self.triangulo_para_numeros:
            self.triangulo_para_numeros[triangulo] = sorted(self.triangulo_para_numeros[triangulo])
        
        # Estatísticas
        self.stats_triangulos = {}
        for triangulo in self.triangulo_para_numeros.keys():
            self.stats_triangulos[triangulo] = {
                'acertos': 0, 'tentativas': 0,
                'ultimo_sorteio': -1, 'ultimos_10': deque(maxlen=10),
                'repeticoes': 0, 'sequencia_atual': 0,
                'erros_consecutivos': 0, 'atraso': 0
            }
        
        # Controle
        self.historico_entradas = []
        self.ultimo_gatilho = None
        self.entrada_ativa = False
        self.entrada_atual = None
        
        # Configurações
        self.max_triangulos_por_aposta = 2
        self.limite_erros_consecutivos = 3
        self.limite_atraso_para_considerar = 8
        
        self.sistema_selecao = SistemaSelecaoInteligente()
        self.cache_vizinhos = {}
        
        # Rastreamento
        self.sequencia_triangulos = deque(maxlen=10)
        self.padroes_detectados = []
    
    def _criar_triangulos_mesa(self):
        """
        Cria triângulos geométricos baseados na disposição dos números na MESA.
        Cada triângulo é formado por 3 números que formam um triângulo visual na mesa.
        
        Tipos de triângulos na mesa:
        1. Triângulo retângulo (ex: 1,2,4)
        2. Triângulo invertido (ex: 4,5,2)
        3. Triângulo grande (ex: 1,3,7)
        """
        triangulos = {}
        
        # Função auxiliar para adicionar triângulo
        def add_triangulo(num, vertices):
            if num not in triangulos:
                triangulos[num] = []
            triangulos[num].append(f"T_{'_'.join(map(str, sorted(vertices)))}")
        
        # Triângulos por toda a mesa
        for linha in range(12):
            for coluna in range(3):
                num_base = linha * 3 + coluna + 1
                if num_base > 36:
                    continue
                
                # Triângulo para baixo (vértice superior, base inferior)
                if linha < 11:
                    # Triângulo retângulo para baixo
                    if coluna < 2:
                        num_dir = linha * 3 + coluna + 2
                        num_baixo = (linha + 1) * 3 + coluna + 1
                        add_triangulo(num_base, [num_base, num_dir, num_baixo])
                        add_triangulo(num_dir, [num_base, num_dir, num_baixo])
                        add_triangulo(num_baixo, [num_base, num_dir, num_baixo])
                    
                    # Triângulo retângulo para baixo (esquerda)
                    if coluna > 0:
                        num_esq = linha * 3 + coluna
                        num_baixo = (linha + 1) * 3 + coluna + 1
                        add_triangulo(num_base, [num_base, num_esq, num_baixo])
                        add_triangulo(num_esq, [num_base, num_esq, num_baixo])
                        add_triangulo(num_baixo, [num_base, num_esq, num_baixo])
                
                # Triângulo para cima (vértice inferior, base superior)
                if linha > 0:
                    # Triângulo retângulo para cima
                    if coluna < 2:
                        num_dir = linha * 3 + coluna + 2
                        num_cima = (linha - 1) * 3 + coluna + 1
                        add_triangulo(num_base, [num_base, num_dir, num_cima])
                        add_triangulo(num_dir, [num_base, num_dir, num_cima])
                        add_triangulo(num_cima, [num_base, num_dir, num_cima])
                    
                    # Triângulo retângulo para cima (esquerda)
                    if coluna > 0:
                        num_esq = linha * 3 + coluna
                        num_cima = (linha - 1) * 3 + coluna + 1
                        add_triangulo(num_base, [num_base, num_esq, num_cima])
                        add_triangulo(num_esq, [num_base, num_esq, num_cima])
                        add_triangulo(num_cima, [num_base, num_esq, num_cima])
        
        # Triângulos especiais com o zero
        zero_triangulos = [
            [0, 1, 2], [0, 1, 3], [0, 2, 3],
            [0, 1, 4], [0, 2, 5], [0, 3, 6]
        ]
        
        for vertices in zero_triangulos:
            key = f"T0_{'_'.join(map(str, sorted(vertices)))}"
            for v in vertices:
                if v not in triangulos:
                    triangulos[v] = []
                if key not in triangulos[v]:
                    triangulos[v].append(key)
        
        return triangulos
    
    def get_triangulos_do_numero(self, numero):
        """Retorna todos os triângulos que contêm o número"""
        return self.numero_para_triangulos.get(numero, [])
    
    def get_numeros_do_triangulo(self, triangulo_key):
        """Retorna os 3 números do triângulo"""
        return self.triangulo_para_numeros.get(triangulo_key, [])
    
    def get_vizinhos_mesa_completos(self, numero):
        """Retorna vizinhos na mesa (acima, abaixo, esquerda, direita)"""
        if numero in self.cache_vizinhos:
            return self.cache_vizinhos[numero]
        
        vizinhos = self.roleta.get_vizinhos_mesa(numero, raio=1)
        self.cache_vizinhos[numero] = vizinhos
        return vizinhos
    
    def get_numeros_aposta(self, triangulos_keys):
        """Gera números para aposta: 3 números do triângulo + vizinhos na mesa de cada"""
        todos_numeros = set()
        
        for triangulo_key in triangulos_keys:
            numeros_triangulo = self.get_numeros_do_triangulo(triangulo_key)
            
            for num in numeros_triangulo:
                todos_numeros.add(num)
                vizinhos = self.get_vizinhos_mesa_completos(num)
                for vizinho in vizinhos:
                    todos_numeros.add(vizinho)
        
        numeros_aposta = sorted(list(todos_numeros))
        
        if len(numeros_aposta) > 15:
            numeros_aposta = self.sistema_selecao.selecionar_melhores_15_numeros(
                numeros_aposta, self.historico
            )
        
        return numeros_aposta
    
    def atualizar_atraso(self, triangulos_sorteado):
        """Atualiza o atraso de todos os triângulos"""
        for t in self.stats_triangulos:
            if t == triangulos_sorteado:
                self.stats_triangulos[t]['atraso'] = 0
            else:
                self.stats_triangulos[t]['atraso'] += 1
    
    def adicionar_numero(self, numero):
        triangulos_do_numero = self.get_triangulos_do_numero(numero)
        
        self.historico.append(numero)
        
        # Atualiza estatísticas para todos os triângulos que contêm o número
        for triangulo_key in triangulos_do_numero:
            self.sequencia_triangulos.append(triangulo_key)
            self.atualizar_atraso(triangulo_key)
            
            if triangulo_key in self.stats_triangulos:
                self.stats_triangulos[triangulo_key]['ultimos_10'].append(numero)
                self.stats_triangulos[triangulo_key]['ultimo_sorteio'] = len(self.historico)
        
        # Verifica repetição
        if len(self.sequencia_triangulos) >= 2:
            ultimo = self.sequencia_triangulos[-1]
            penultimo = self.sequencia_triangulos[-2]
            if ultimo == penultimo:
                self.stats_triangulos[ultimo]['repeticoes'] += 1
                self.stats_triangulos[ultimo]['sequencia_atual'] += 1
            else:
                for t in self.stats_triangulos:
                    self.stats_triangulos[t]['sequencia_atual'] = 0
        
        self.detectar_padroes()
        
        if self.entrada_ativa and self.entrada_atual:
            self.entrada_ativa = False
            
            triangulos_apostados = self.entrada_atual.get('triangulos', [])
            
            # Verifica se algum triângulo apostado acertou
            acertou = False
            triangulo_acertado = None
            for t_apostado in triangulos_apostados:
                if t_apostado in triangulos_do_numero:
                    acertou = True
                    triangulo_acertado = t_apostado
                    break
            
            if acertou:
                self.stats_triangulos[triangulo_acertado]['acertos'] += 1
                self.stats_triangulos[triangulo_acertado]['tentativas'] += 1
                self.stats_triangulos[triangulo_acertado]['erros_consecutivos'] = 0
                self.registrar_entrada(acertou=True, triangulo_acertado=triangulo_acertado)
            else:
                for t in triangulos_apostados:
                    self.stats_triangulos[t]['tentativas'] += 1
                    self.stats_triangulos[t]['erros_consecutivos'] += 1
                self.registrar_entrada(acertou=False)
            
            self.entrada_atual = None
        
        if 'sistema' in st.session_state:
            salvar_sessao()
    
    def detectar_padroes(self):
        if len(self.sequencia_triangulos) < 3:
            return
        
        if (self.sequencia_triangulos[-1] == self.sequencia_triangulos[-2] and
            self.sequencia_triangulos[-2] == self.sequencia_triangulos[-3]):
            self.padroes_detectados.append({
                'tipo': 'TRIPLA_REPETICAO',
                'triangulo': self.sequencia_triangulos[-1],
                'forca': 0.9
            })
        
        elif len(self.sequencia_triangulos) >= 4:
            ultimos_4 = list(self.sequencia_triangulos)[-4:]
            if ultimos_4[0] == ultimos_4[2] and ultimos_4[1] == ultimos_4[3]:
                self.padroes_detectados.append({
                    'tipo': 'ALTERNANCIA',
                    'triangulos': [ultimos_4[0], ultimos_4[1]],
                    'forca': 0.75
                })
        
        if len(self.padroes_detectados) > 10:
            self.padroes_detectados = self.padroes_detectados[-10:]
    
    def get_triangulos_quentes(self):
        quentes = []
        
        for triangulo, stats in self.stats_triangulos.items():
            if stats.get('sequencia_atual', 0) >= 1:
                quentes.append((triangulo, 70 + stats.get('sequencia_atual', 0) * 10, '🔥 SEQUÊNCIA'))
            elif stats.get('repeticoes', 0) >= 1:
                quentes.append((triangulo, 60, '🔁 REPETIÇÃO'))
            elif stats.get('tentativas', 0) > 0:
                taxa = (stats.get('acertos', 0) / stats.get('tentativas', 1)) * 100
                if taxa > 30:
                    quentes.append((triangulo, 40 + taxa * 0.5, '📈 PERFORMANCE'))
        
        return sorted(quentes, key=lambda x: x[1], reverse=True)
    
    def get_triangulos_frios(self):
        frios = []
        
        for triangulo, stats in self.stats_triangulos.items():
            erros_cons = stats.get('erros_consecutivos', 0)
            atraso = stats.get('atraso', 0)
            acertos = stats.get('acertos', 0)
            tentativas = stats.get('tentativas', 0)
            
            if erros_cons >= self.limite_erros_consecutivos:
                frios.append((triangulo, erros_cons * 5, '❌ ERROS CONSECUTIVOS'))
            elif atraso >= self.limite_atraso_para_considerar:
                frios.append((triangulo, atraso * 2, '⏰ ATRASADO'))
            elif acertos == 0 and tentativas >= 3:
                frios.append((triangulo, 30, '🆕 NUNCA ACERTOU'))
        
        return sorted(frios, key=lambda x: x[1], reverse=True)
    
    def get_triangulos_por_padrao(self):
        resultado = []
        
        for padrao in self.padroes_detectados[-3:]:
            if padrao['tipo'] == 'TRIPLA_REPETICAO':
                resultado.append((padrao['triangulo'], 85, '🔺 TRIPLA REPETIÇÃO'))
            elif padrao['tipo'] == 'ALTERNANCIA':
                for t in padrao['triangulos']:
                    resultado.append((t, 70, '🔄 ALTERNÂNCIA'))
        
        return resultado
    
    def analisar_previsao(self):
        if len(self.historico) < 10:
            return None
        
        triangulos_candidatos = []
        
        for triangulo, peso, motivo in self.get_triangulos_quentes()[:3]:
            triangulos_candidatos.append((triangulo, peso, motivo))
        
        for triangulo, peso, motivo in self.get_triangulos_frios()[:2]:
            if triangulo not in [t for t, _, _ in triangulos_candidatos]:
                triangulos_candidatos.append((triangulo, peso, motivo))
        
        for triangulo, peso, motivo in self.get_triangulos_por_padrao():
            if triangulo not in [t for t, _, _ in triangulos_candidatos]:
                triangulos_candidatos.append((triangulo, peso, motivo))
        
        if not triangulos_candidatos:
            return None
        
        triangulos_candidatos.sort(key=lambda x: x[1], reverse=True)
        triangulos_selecionados = []
        motivos_selecionados = []
        
        for t, peso, motivo in triangulos_candidatos[:self.max_triangulos_por_aposta]:
            triangulos_selecionados.append(t)
            motivos_selecionados.append(motivo)
        
        numeros_aposta = self.get_numeros_aposta(triangulos_selecionados)
        
        maior_peso = triangulos_candidatos[0][1]
        if maior_peso >= 75:
            confianca = "Excelente"
        elif maior_peso >= 60:
            confianca = "Muito Alta"
        elif maior_peso >= 45:
            confianca = "Alta"
        elif maior_peso >= 30:
            confianca = "Média"
        else:
            confianca = "Baixa"
        
        detalhes = []
        for i, t in enumerate(triangulos_selecionados):
            motivo = motivos_selecionados[i] if i < len(motivos_selecionados) else ''
            numeros_tri = self.get_numeros_do_triangulo(t)
            detalhes.append(f"{t}({numeros_tri}){motivo}")
        
        qtd_numeros = len(numeros_aposta)
        gatilho = f"🎯 MESA GEOMÉTRICA: {' + '.join(detalhes)} | {qtd_numeros} números"
        
        previsao = {
            'nome': f'Triângulo Geométrico Mesa v10 ({len(triangulos_selecionados)} ativos)',
            'numeros_apostar': numeros_aposta,
            'gatilho': gatilho,
            'confianca_geral': confianca,
            'triangulos': triangulos_selecionados,
            'total_numeros': qtd_numeros,
            'motivos': motivos_selecionados
        }
        
        self.entrada_ativa = True
        self.entrada_atual = previsao
        self.ultimo_gatilho = previsao
        
        return previsao
    
    def registrar_entrada(self, acertou=False, triangulo_acertado=None):
        if self.entrada_atual:
            registro = {
                'timestamp': len(self.historico),
                'triangulos': self.entrada_atual['triangulos'],
                'acertou': acertou,
                'confianca': self.entrada_atual['confianca_geral'],
                'triangulo_acertado': triangulo_acertado if acertou else None,
                'motivos': self.entrada_atual.get('motivos', [])
            }
            self.historico_entradas.append(registro)
            
            if len(self.historico_entradas) > 50:
                self.historico_entradas = self.historico_entradas[-50:]
    
    def get_analise_detalhada(self):
        if len(self.historico) == 0:
            return "🔺 Aguardando dados..."
        
        analise = "🔺 ANÁLISE TRIÂNGULO GEOMÉTRICO MESA v10\n"
        analise += "=" * 55 + "\n"
        analise += f"📊 Histórico: {len(self.historico)} números\n"
        analise += f"🎯 Último número: {self.historico[-1]}\n"
        analise += f"🎲 Estratégia: TRIÂNGULOS GEOMÉTRICOS NA MESA\n"
        analise += "=" * 55 + "\n\n"
        
        analise += "📐 DEFINIÇÃO DOS TRIÂNGULOS:\n"
        analise += "Cada triângulo é formado por 3 números que formam um triângulo visual na mesa.\n"
        analise += "Exemplo: 1,2,4 formam um triângulo retângulo.\n\n"
        
        analise += "🔥 TRIÂNGULOS QUENTES (ACERTANDO):\n"
        for triangulo, peso, motivo in self.get_triangulos_quentes()[:5]:
            stats = self.stats_triangulos[triangulo]
            numeros = self.get_numeros_do_triangulo(triangulo)
            analise += f"   🔥 {triangulo}: {motivo} (peso {peso:.0f})\n"
            analise += f"      📍 Vértices: {numeros}\n"
            analise += f"      📊 Acertos: {stats.get('acertos', 0)}/{stats.get('tentativas', 0)}\n"
        
        analise += "\n❄️ TRIÂNGULOS FRIOS (ERRANDO/ATRASADOS):\n"
        for triangulo, peso, motivo in self.get_triangulos_frios()[:5]:
            stats = self.stats_triangulos[triangulo]
            numeros = self.get_numeros_do_triangulo(triangulo)
            analise += f"   ❄️ {triangulo}: {motivo} (peso {peso:.0f})\n"
            analise += f"      📍 Vértices: {numeros}\n"
            analise += f"      ⏰ Atraso: {stats.get('atraso', 0)} | Erros: {stats.get('erros_consecutivos', 0)}\n"
        
        if self.padroes_detectados:
            analise += "\n📊 PADRÕES DETECTADOS:\n"
            for padrao in self.padroes_detectados[-3:]:
                if padrao['tipo'] == 'TRIPLA_REPETICAO':
                    analise += f"   🔁 TRIPLA REPETIÇÃO: {padrao['triangulo']}\n"
                elif padrao['tipo'] == 'ALTERNANCIA':
                    analise += f"   🔄 ALTERNÂNCIA: {padrao['triangulos'][0]} ↔ {padrao['triangulos'][1]}\n"
        
        if self.entrada_ativa and self.entrada_atual:
            analise += "\n" + "=" * 55 + "\n"
            analise += "🎯 PREVISÃO ATIVA:\n"
            for i, t in enumerate(self.entrada_atual['triangulos']):
                motivo = self.entrada_atual.get('motivos', [''])[i] if i < len(self.entrada_atual.get('motivos', [])) else ''
                numeros = self.get_numeros_do_triangulo(t)
                analise += f"   🔺 {t}: {motivo}\n"
                analise += f"      📍 Vértices: {numeros}\n"
            analise += f"📊 Confiança: {self.entrada_atual['confianca_geral']}\n"
            analise += f"🔢 Total de números: {self.entrada_atual['total_numeros']}\n"
        
        return analise
    
    def get_info_triangulos(self):
        info = {}
        for triangulo in self.triangulo_para_numeros.keys():
            info[triangulo] = {
                'numeros': self.get_numeros_do_triangulo(triangulo),
                'quantidade': len(self.get_numeros_do_triangulo(triangulo)),
                'stats': self.stats_triangulos.get(triangulo, {})
            }
        return info
    
    def zerar_estatisticas(self):
        for triangulo in self.stats_triangulos:
            self.stats_triangulos[triangulo] = {
                'acertos': 0, 'tentativas': 0,
                'ultimo_sorteio': -1, 'ultimos_10': deque(maxlen=10),
                'repeticoes': 0, 'sequencia_atual': 0,
                'erros_consecutivos': 0, 'atraso': 0
            }
        self.historico_entradas = []
        self.sequencia_triangulos.clear()
        self.padroes_detectados = []
        self.entrada_ativa = False
        self.entrada_atual = None
        self.cache_vizinhos.clear()
        logging.info("📊 Estatísticas zeradas")

# =============================
# SISTEMA DE GESTÃO
# =============================
class SistemaRoletaCompleto:
    def __init__(self):
        self.estrategia_triangulo = EstrategiaTrianguloGeometrico()
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.estrategia_selecionada = "Triângulo"
        self.contador_sorteios_global = 0
        
        self.sequencia_erros = 0
        self.ultima_estrategia_erro = ""
        self.sequencia_acertos = 0

    def set_estrategia(self, estrategia):
        self.estrategia_selecionada = estrategia
        salvar_sessao()

    def processar_novo_numero(self, numero):
        if isinstance(numero, dict) and 'number' in numero:
            numero_real = numero['number']
        else:
            numero_real = numero
            
        self.contador_sorteios_global += 1
            
        if self.previsao_ativa:
            acerto = False
            zonas_acertadas = []
            nome_estrategia = self.previsao_ativa['nome']
            
            triangulos_previsao = self.previsao_ativa.get('triangulos', [])
            triangulos_do_numero = self.estrategia_triangulo.get_triangulos_do_numero(numero_real)
            
            # Verifica se algum triângulo apostado está entre os triângulos do número
            for t_apostado in triangulos_previsao:
                if t_apostado in triangulos_do_numero:
                    acerto = True
                    zonas_acertadas = [t_apostado]
                    break
            
            if nome_estrategia not in self.estrategias_contador:
                self.estrategias_contador[nome_estrategia] = {'acertos': 0, 'total': 0}
            
            self.estrategias_contador[nome_estrategia]['total'] += 1
            if acerto:
                self.estrategias_contador[nome_estrategia]['acertos'] += 1
                self.acertos += 1
                self.sequencia_acertos += 1
                self.sequencia_erros = 0
            else:
                self.erros += 1
                self.sequencia_erros += 1
                self.sequencia_acertos = 0
                self.ultima_estrategia_erro = nome_estrategia
            
            zona_acertada_str = "+".join(zonas_acertadas) if zonas_acertadas else None
            enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada_str)
            
            self.historico_desempenho.append({
                'numero': numero_real,
                'acerto': acerto,
                'estrategia': nome_estrategia,
                'previsao': self.previsao_ativa['numeros_apostar'],
                'rotacionou': False,
                'zona_acertada': zona_acertada_str,
                'zonas_envolvidas': self.previsao_ativa.get('triangulos', []),
                'tipo_aposta': 'multi',
                'sequencia_acertos': self.sequencia_acertos,
                'sequencia_erros': self.sequencia_erros
            })
            
            self.previsao_ativa = None
        
        self.estrategia_triangulo.adicionar_numero(numero_real)
        
        nova_previsao = self.estrategia_triangulo.analisar_previsao()
        
        if nova_previsao:
            self.previsao_ativa = nova_previsao
            enviar_previsao_super_simplificada(nova_previsao)

    def zerar_estatisticas_desempenho(self):
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.historico_desempenho = []
        self.contador_sorteios_global = 0
        self.sequencia_erros = 0
        self.ultima_estrategia_erro = ""
        self.sequencia_acertos = 0
        
        self.estrategia_triangulo.zerar_estatisticas()
        
        logging.info("📊 Todas as estatísticas foram zeradas")
        salvar_sessao()

    def reset_recente_estatisticas(self):
        if len(self.historico_desempenho) > 10:
            self.historico_desempenho = self.historico_desempenho[-10:]
            self.acertos = sum(1 for resultado in self.historico_desempenho if resultado['acerto'])
            self.erros = len(self.historico_desempenho) - self.acertos
            
            self.estrategias_contador = {}
            for resultado in self.historico_desempenho:
                estrategia = resultado['estrategia']
                if estrategia not in self.estrategias_contador:
                    self.estrategias_contador[estrategia] = {'acertos': 0, 'total': 0}
                
                self.estrategias_contador[estrategia]['total'] += 1
                if resultado['acerto']:
                    self.estrategias_contador[estrategia]['acertos'] += 1
            
            ultimos_resultados = self.historico_desempenho[-5:]
            self.sequencia_erros = 0
            self.sequencia_acertos = 0
            
            for resultado in reversed(ultimos_resultados):
                if resultado['acerto']:
                    self.sequencia_acertos += 1
                else:
                    break
                    
            for resultado in reversed(ultimos_resultados):
                if not resultado['acerto']:
                    self.sequencia_erros += 1
                else:
                    break
            
            logging.info("🔄 Estatísticas recentes resetadas")
        else:
            logging.info("ℹ️ Histórico muito pequeno para reset recente")
        
        salvar_sessao()

    def get_status_rotacao(self):
        return {
            'estrategia_atual': self.estrategia_selecionada,
            'sequencia_erros': self.sequencia_erros,
            'sequencia_acertos': self.sequencia_acertos,
            'ultima_estrategia_erro': self.ultima_estrategia_erro
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
        return {"number": number, "timestamp": timestamp}
    except Exception as e:
        logging.error(f"Erro ao buscar resultado: {e}")
        return None

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🔺 Triângulo Geométrico Mesa - Roleta", layout="centered")
st.title("🔺 Estratégia Triângulo Geométrico da Mesa v10")

# Inicialização
if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaRoletaCompleto()

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

with st.sidebar.expander("🔺 Configurações v10", expanded=True):
    st.write("**Estratégia Triângulo Geométrico da Mesa v10**")
    st.write("**Definição:** Triângulos formados por 3 números que formam um triângulo visual na mesa")
    st.write("**Exemplo:** 1,2,4 formam um triângulo retângulo")
    st.write("**Vizinhos:** Acima, abaixo, esquerda, direita na mesa")
    
    max_triangulos = st.slider(
        "Máximo de triângulos por aposta:",
        min_value=1, max_value=3, 
        value=st.session_state.sistema.estrategia_triangulo.max_triangulos_por_aposta,
        help="Quantos triângulos serão apostados"
    )
    
    limite_erros = st.slider(
        "Limite de erros consecutivos para excluir:",
        min_value=2, max_value=5, 
        value=st.session_state.sistema.estrategia_triangulo.limite_erros_consecutivos,
        help="Após este número de erros, o triângulo é temporariamente excluído"
    )
    
    if st.button("Aplicar"):
        st.session_state.sistema.estrategia_triangulo.max_triangulos_por_aposta = max_triangulos
        st.session_state.sistema.estrategia_triangulo.limite_erros_consecutivos = limite_erros
        salvar_sessao()
        st.success("✅ Aplicado!")

with st.sidebar.expander("💾 Gerenciamento", expanded=False):
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Salvar", use_container_width=True):
            salvar_sessao()
            st.success("✅ Salvo!")
            
    with col2:
        if st.button("🔄 Carregar", use_container_width=True):
            if carregar_sessao():
                st.success("✅ Carregado!")
                st.rerun()
            else:
                st.error("❌ Nenhum save")
    
    st.write("---")
    
    col3, col4 = st.columns(2)
    
    with col3:
        if st.button("🔄 Reset Recente", use_container_width=True):
            st.session_state.sistema.reset_recente_estatisticas()
            st.success("✅ Reset!")
            st.rerun()
            
    with col4:
        if st.button("🗑️ Zerar Tudo", type="secondary", use_container_width=True):
            if st.checkbox("Confirmar"):
                st.session_state.sistema.zerar_estatisticas_desempenho()
                st.error("🗑️ Zerado!")
                st.rerun()
    
    if st.button("🗑️ Limpar Sessão", type="secondary", use_container_width=True):
        if st.checkbox("Confirmar"):
            limpar_sessao()
            st.stop()

with st.sidebar.expander("🔔 Telegram", expanded=False):
    telegram_token = st.text_input("Bot Token:", value=st.session_state.telegram_token, type="password")
    telegram_chat_id = st.text_input("Chat ID:", value=st.session_state.telegram_chat_id)
    
    if st.button("Salvar"):
        st.session_state.telegram_token = telegram_token
        st.session_state.telegram_chat_id = telegram_chat_id
        salvar_sessao()
        st.success("✅ Salvo!")
        
    if st.button("Testar"):
        if telegram_token and telegram_chat_id:
            try:
                enviar_telegram("🔔 Triângulo Geométrico Mesa v10 funcionando!")
                st.success("✅ Enviado!")
            except Exception as e:
                st.error(f"Erro: {e}")

with st.sidebar.expander("📊 Sobre v10", expanded=False):
    st.write("**🔺 Triângulo Geométrico da Mesa v10**")
    st.write("**Nova definição de triângulo:**")
    st.write("Baseado na disposição geométrica dos números na MESA da roleta")
    st.write("")
    st.write("**Exemplos de triângulos:**")
    st.write("- 1,2,4 formam triângulo retângulo")
    st.write("- 4,5,2 formam triângulo invertido")
    st.write("- 1,3,7 formam triângulo grande")
    st.write("- 0,1,2 formam triângulo com zero")
    st.write("")
    st.write("**Lógica:**")
    st.write("1. 🔥 TRIÂNGULOS QUENTES (estão acertando)")
    st.write("2. ❄️ TRIÂNGULOS FRIOS (atrasados/errando)")
    st.write("3. 🔁 PADRÕES (tripla repetição/alternância)")
    st.write("4. 📍 Vizinhos na mesa (acima/abaixo/esquerda/direita)")
    st.write("5. 🎯 Máximo 15 números por aposta")

with st.sidebar.expander("🔍 Análise", expanded=False):
    analise = st.session_state.sistema.estrategia_triangulo.get_analise_detalhada()
    st.text(analise)

# Interface Principal
st.subheader("✍️ Inserir Sorteios")
entrada = st.text_input("Digite números (0-36) separados por espaço:")
if st.button("Adicionar") and entrada:
    try:
        nums = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
        for n in nums:
            item = {"number": n, "timestamp": f"manual_{len(st.session_state.historico)}"}
            st.session_state.historico.append(item)
            st.session_state.sistema.processar_novo_numero(n)
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()
        st.success(f"{len(nums)} números adicionados!")
        st.rerun()
    except Exception as e:
        st.error(f"Erro: {e}")

st_autorefresh(interval=3000, key="refresh")

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

st.subheader("🔁 Últimos Números")
if st.session_state.historico:
    ultimos_10 = st.session_state.historico[-10:]
    numeros_str = " ".join(str(item['number'] if isinstance(item, dict) else item) for item in ultimos_10)
    st.write(numeros_str)
else:
    st.write("Nenhum número")

status = st.session_state.sistema.get_status_rotacao()
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("🎯 Estratégia", status['estrategia_atual'])
with col2:
    st.metric("✅ Acertos Seguidos", status['sequencia_acertos'])
with col3:
    st.metric("❌ Erros Seguidos", status['sequencia_erros'])

st.subheader("🎯 Previsão Ativa")
sistema = st.session_state.sistema

if sistema.previsao_ativa:
    previsao = sistema.previsao_ativa
    st.success(f"**{previsao['nome']}**")
    
    triangulos_ativos = previsao.get('triangulos', [])
    motivos = previsao.get('motivos', [])
    
    st.write(f"**🔺 Triângulos ({len(triangulos_ativos)}):**")
    for i, t in enumerate(triangulos_ativos):
        motivo = motivos[i] if i < len(motivos) else ''
        numeros_tri = sistema.estrategia_triangulo.get_numeros_do_triangulo(t)
        st.write(f"   🔺 **{t}** - {motivo}")
        st.write(f"      📍 Vértices: {numeros_tri}")
    
    st.write(f"**📊 Confiança:** {previsao.get('confianca_geral', 'Média')}")
    st.write(f"**📋 Gatilho:** {previsao['gatilho']}")
    
    st.write(f"**🔢 Números para apostar ({len(previsao['numeros_apostar'])}):**")
    numeros = sorted(previsao['numeros_apostar'])
    for i in range(0, len(numeros), 5):
        st.write(" ".join(map(str, numeros[i:i+5])))
    
    st.info("⏳ Aguardando próximo sorteio...")
else:
    st.info("🔺 Aguardando análise geométrica dos triângulos na mesa...")

st.subheader("📈 Desempenho")
total = sistema.acertos + sistema.erros
taxa = (sistema.acertos / total * 100) if total > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 Acertos", sistema.acertos)
col2.metric("🔴 Erros", sistema.erros)
col3.metric("📊 Total", total)
col4.metric("✅ Taxa", f"{taxa:.1f}%")

if sistema.historico_desempenho:
    st.write("**🔍 Últimas 5 Conferências:**")
    for resultado in sistema.historico_desempenho[-5:]:
        emoji = "🎉" if resultado['acerto'] else "❌"
        triangulos_str = ", ".join(resultado['zonas_envolvidas']) if resultado['zonas_envolvidas'] else "N/A"
        st.write(f"{emoji} {resultado['estrategia']}: Número {resultado['numero']} | Triângulos: {triangulos_str}")

if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        conteudo = f.read()
    st.download_button("📥 Baixar histórico", data=conteudo, file_name="historico_triangulo_mesa.json")

salvar_sessao()
