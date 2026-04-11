import streamlit as st
import json
import os
import requests
import logging
import numpy as np
from collections import deque
import joblib
from streamlit_autorefresh import st_autorefresh
import pickle

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data_triangulo.pkl"
HISTORICO_PATH = "historico_triangulo.json"

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
            'triangulo_historico_multi': list(st.session_state.sistema.estrategia_triangulo.historico_multi),
            'triangulo_ultimos_triangulos_apostados': st.session_state.sistema.estrategia_triangulo.ultimos_triangulos_apostados,
            'triangulo_max_triangulos': st.session_state.sistema.estrategia_triangulo.max_triangulos_por_aposta,
            'triangulo_confianca_minima': st.session_state.sistema.estrategia_triangulo.confianca_minima_aposta
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
                logging.error("❌ Dados de sessão corrompidos - não é um dicionário")
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
                st.session_state.sistema.estrategia_triangulo.historico = deque(triangulo_historico, maxlen=70)
                st.session_state.sistema.estrategia_triangulo.stats_triangulos = session_data.get('triangulo_stats', {})
                st.session_state.sistema.estrategia_triangulo.historico_entradas = session_data.get('triangulo_historico_entradas', [])
                st.session_state.sistema.estrategia_triangulo.ultimo_gatilho = session_data.get('triangulo_ultimo_gatilho', None)
                st.session_state.sistema.estrategia_triangulo.historico_multi = deque(session_data.get('triangulo_historico_multi', []), maxlen=50)
                st.session_state.sistema.estrategia_triangulo.ultimos_triangulos_apostados = session_data.get('triangulo_ultimos_triangulos_apostados', [])
                
                if 'triangulo_max_triangulos' in session_data:
                    st.session_state.sistema.estrategia_triangulo.max_triangulos_por_aposta = session_data['triangulo_max_triangulos']
                if 'triangulo_confianca_minima' in session_data:
                    st.session_state.sistema.estrategia_triangulo.confianca_minima_aposta = session_data['triangulo_confianca_minima']
            
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
        nome_estrategia = previsao['nome']
        numeros_apostar = sorted(previsao['numeros_apostar'])
        
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
                enviar_telegram(f"🚨 PREVISÃO ATIVA\n{mensagem}\n💎 CONFIANÇA: {previsao.get('confianca_geral', 'ALTA')}")
                
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
        self.roleta = RoletaInteligente()
        
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
        
        score_posicao = self.calcular_score_posicao_roda(numero, historico)
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
    
    def calcular_score_posicao_roda(self, numero, historico):
        if len(historico) < 3:
            return 0.5
            
        ultimo_numero = historico[-1] if historico else 0
        penultimo_numero = historico[-2] if len(historico) >= 2 else ultimo_numero
        
        posicao_alvo = self.roleta.get_posicao_race(numero)
        posicao_ultimo = self.roleta.get_posicao_race(ultimo_numero)
        posicao_penultimo = self.roleta.get_posicao_race(penultimo_numero)
        
        dist_ultimo = self.calcular_distancia_roda(posicao_alvo, posicao_ultimo)
        score_dist_ultimo = max(0, 1 - (dist_ultimo / 18))
        
        dist_penultimo = self.calcular_distancia_roda(posicao_alvo, posicao_penultimo)
        score_dist_penultimo = max(0, 1 - (dist_penultimo / 18))
        
        score_final = (score_dist_ultimo * 0.7 + score_dist_penultimo * 0.3)
        return score_final
    
    def calcular_distancia_roda(self, pos1, pos2):
        total_posicoes = 37
        distancia_direta = abs(pos1 - pos2)
        distancia_inversa = total_posicoes - distancia_direta
        return min(distancia_direta, distancia_inversa)
    
    def calcular_score_vizinhos(self, numero, historico):
        if len(historico) < 5:
            return 0.5
            
        vizinhos = self.roleta.get_vizinhos_fisicos(numero, raio=3)
        
        ultimos_15 = list(historico)[-15:] if len(historico) >= 15 else list(historico)
        count_vizinhos_recentes = sum(1 for n in ultimos_15 if n in vizinhos)
        
        score = min(count_vizinhos_recentes / len(ultimos_15) * 2, 1.0)
        return score
    
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
# CLASSE PRINCIPAL DA ROLETA
# =============================
class RoletaInteligente:
    def __init__(self):
        self.race = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        
    def get_vizinhos_zona(self, numero_central, quantidade=6):
        if numero_central not in self.race:
            return []
        
        posicao = self.race.index(numero_central)
        vizinhos = []
        
        for offset in range(-quantidade, 0):
            vizinho = self.race[(posicao + offset) % len(self.race)]
            vizinhos.append(vizinho)
        
        vizinhos.append(numero_central)
        
        for offset in range(1, quantidade + 1):
            vizinho = self.race[(posicao + offset) % len(self.race)]
            vizinhos.append(vizinho)
        
        return vizinhos

    def get_posicao_race(self, numero):
        return self.race.index(numero) if numero in self.race else -1

    def get_vizinhos_fisicos(self, numero, raio=3):
        if numero not in self.race:
            return []
        
        posicao = self.race.index(numero)
        vizinhos = []
        
        for offset in range(-raio, raio + 1):
            if offset != 0:
                vizinho = self.race[(posicao + offset) % len(self.race)]
                vizinhos.append(vizinho)
        
        return vizinhos

# =============================
# ESTRATÉGIA TRIÂNGULO MÚLTIPLO
# =============================
class EstrategiaTrianguloMultiplo:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=70)
        self.nome = "Triângulo Múltiplo v2"
        
        # Mapeamento completo: número -> triângulo
        self.numero_para_triangulo = self._criar_mapeamento_triangulos()
        
        # Mapeamento reverso: triângulo -> números
        self.triangulo_para_numeros = {}
        for num, triangulo in self.numero_para_triangulo.items():
            if triangulo not in self.triangulo_para_numeros:
                self.triangulo_para_numeros[triangulo] = []
            self.triangulo_para_numeros[triangulo].append(num)
        
        # Ordenar números de cada triângulo
        for triangulo in self.triangulo_para_numeros:
            self.triangulo_para_numeros[triangulo] = sorted(self.triangulo_para_numeros[triangulo])
        
        # Estatísticas por triângulo
        self.stats_triangulos = {}
        for triangulo in self.triangulo_para_numeros.keys():
            self.stats_triangulos[triangulo] = {
                'acertos': 0,
                'tentativas': 0,
                'sequencia_atual': 0,
                'sequencia_maxima': 0,
                'performance_media': 0,
                'ultimo_sorteio': -1,
                'atraso_atual': 0,
                'max_atraso': 0,
                'vizinhos_quentes': 0
            }
        
        # Controle de entradas
        self.historico_entradas = []
        self.ultimo_gatilho = None
        self.contador_giros_sem_entrada = 0
        self.entrada_ativa = False
        self.entrada_atual = None
        
        # Configurações multi-triângulo
        self.historico_multi = deque(maxlen=50)
        self.ultimos_triangulos_apostados = []
        
        # Configurações ajustáveis
        self.janela_atraso = 10
        self.janela_vizinhos = 8
        self.max_vizinhos_por_numero = 2
        self.max_triangulos_por_aposta = 3
        self.confianca_minima_aposta = "Média"
        
        self.sistema_selecao = SistemaSelecaoInteligente()
        self.cache_vizinhos = {}
    
    def _criar_mapeamento_triangulos(self):
        """Cria mapeamento número -> triângulo baseado na disposição do cilindro"""
        race = self.roleta.race
        
        triangulos = {}
        
        # Criar triângulos de 3 números consecutivos
        for i in range(0, len(race), 3):
            if i + 2 < len(race):
                triangulo_nome = f"T{i//3 + 1}"
                for j in range(3):
                    triangulos[race[i + j]] = triangulo_nome
        
        # Para números que não foram mapeados
        numeros_restantes = set(range(37)) - set(triangulos.keys())
        ultimo_triangulo = f"T{len(triangulos)//3 + 1}"
        for num in numeros_restantes:
            triangulos[num] = ultimo_triangulo
        
        return triangulos
    
    def get_triangulo_do_numero(self, numero):
        return self.numero_para_triangulo.get(numero, "Desconhecido")
    
    def get_numeros_do_triangulo(self, triangulo):
        return self.triangulo_para_numeros.get(triangulo, [])
    
    def get_vizinhos_cilindro(self, numero, raio=2):
        if numero in self.cache_vizinhos:
            return self.cache_vizinhos[numero]
        
        vizinhos = self.roleta.get_vizinhos_fisicos(numero, raio)
        self.cache_vizinhos[numero] = vizinhos
        return vizinhos
    
    def get_todos_vizinhos_do_triangulo(self, triangulo):
        numeros = self.get_numeros_do_triangulo(triangulo)
        todos_vizinhos = set()
        
        for num in numeros:
            vizinhos = self.get_vizinhos_cilindro(num, self.max_vizinhos_por_numero)
            todos_vizinhos.update(vizinhos)
        
        todos_vizinhos -= set(numeros)
        return sorted(list(todos_vizinhos))
    
    def get_numeros_aposta_para_triangulos(self, triangulos):
        todos_numeros = set()
        
        for triangulo in triangulos:
            numeros_triangulo = self.get_numeros_do_triangulo(triangulo)
            vizinhos = self.get_todos_vizinhos_do_triangulo(triangulo)
            todos_numeros.update(numeros_triangulo)
            todos_numeros.update(vizinhos)
        
        numeros_aposta = sorted(list(todos_numeros))
        
        if len(numeros_aposta) > 15:
            numeros_aposta = self.sistema_selecao.selecionar_melhores_15_numeros(
                numeros_aposta, self.historico
            )
        
        return numeros_aposta
    
    def adicionar_numero(self, numero):
        self.historico.append(numero)
        self.atualizar_stats_triangulos(numero)
        
        if self.entrada_ativa and self.entrada_atual:
            self.entrada_ativa = False
            self.contador_giros_sem_entrada = 0
            
            triangulo_sorteado = self.get_triangulo_do_numero(numero)
            triangulos_apostados = self.entrada_atual.get('triangulos', [])
            acertou = triangulo_sorteado in triangulos_apostados
            
            if acertou:
                self.stats_triangulos[triangulo_sorteado]['acertos'] += 1
                self.stats_triangulos[triangulo_sorteado]['sequencia_atual'] += 1
                self.registrar_entrada(acertou=True, triangulo_acertado=triangulo_sorteado)
            else:
                for t in triangulos_apostados:
                    self.stats_triangulos[t]['sequencia_atual'] = 0
                self.registrar_entrada(acertou=False)
            
            self.entrada_atual = None
        
        if 'sistema' in st.session_state:
            salvar_sessao()
    
    def atualizar_stats_triangulos(self, numero):
        triangulo = self.get_triangulo_do_numero(numero)
        
        if triangulo in self.stats_triangulos:
            for t in self.stats_triangulos:
                if t != triangulo:
                    self.stats_triangulos[t]['atraso_atual'] += 1
                    if self.stats_triangulos[t]['atraso_atual'] > self.stats_triangulos[t]['max_atraso']:
                        self.stats_triangulos[t]['max_atraso'] = self.stats_triangulos[t]['atraso_atual']
            
            self.stats_triangulos[triangulo]['atraso_atual'] = 0
            self.stats_triangulos[triangulo]['ultimo_sorteio'] = len(self.historico)
            
            tentativas = self.stats_triangulos[triangulo]['tentativas']
            if tentativas > 0:
                self.stats_triangulos[triangulo]['performance_media'] = (
                    self.stats_triangulos[triangulo]['acertos'] / tentativas * 100
                )
    
    def verificar_vizinhos_quentes(self, triangulo):
        vizinhos = self.get_todos_vizinhos_do_triangulo(triangulo)
        
        if len(self.historico) < self.janela_vizinhos:
            return False
        
        historico_recente = list(self.historico)[-self.janela_vizinhos:]
        count_vizinhos = sum(1 for num in historico_recente if num in vizinhos)
        
        self.stats_triangulos[triangulo]['vizinhos_quentes'] = count_vizinhos
        return count_vizinhos >= 2
    
    def verificar_atraso(self, triangulo):
        atraso = self.stats_triangulos[triangulo]['atraso_atual']
        return atraso >= self.janela_atraso
    
    def verificar_sem_acerto_recente(self, triangulo):
        ultimo_sorteio = self.stats_triangulos[triangulo]['ultimo_sorteio']
        
        if ultimo_sorteio == -1:
            return True
        
        distancia = len(self.historico) - ultimo_sorteio
        return distancia >= 5
    
    def calcular_score_triangulo(self, triangulo):
        stats = self.stats_triangulos[triangulo]
        score = 0
        
        # Fator 1: Atraso (0-40 pontos)
        atraso = stats['atraso_atual']
        score += min(atraso * 2, 40)
        
        # Fator 2: Vizinhos quentes (0-30 pontos)
        score += min(stats['vizinhos_quentes'] * 10, 30)
        
        # Fator 3: Performance histórica (0-20 pontos)
        score += stats['performance_media'] * 0.5
        
        # Fator 4: Bônus por não ter acertado recentemente (0-10)
        if self.verificar_sem_acerto_recente(triangulo):
            score += 10
        
        return min(score, 100)
    
    def calcular_confianca_por_score(self, score):
        if score >= 70:
            return "Excelente"
        elif score >= 55:
            return "Muito Alta"
        elif score >= 40:
            return "Alta"
        elif score >= 25:
            return "Média"
        else:
            return "Baixa"
    
    def get_nivel_confianca_numero(self, confianca_texto):
        niveis = {
            'Excelente': 4,
            'Muito Alta': 3,
            'Alta': 2,
            'Média': 1,
            'Baixa': 0
        }
        return niveis.get(confianca_texto, 0)
    
    def analisar_triangulos_multi(self):
        if len(self.historico) < 5:
            return None
        
        # Calcular score para todos os triângulos
        scores = {}
        for triangulo in self.triangulo_para_numeros.keys():
            score = self.calcular_score_triangulo(triangulo)
            scores[triangulo] = score
        
        # Ordenar por score
        triangulos_ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Selecionar triângulos com base na confiança mínima
        triangulos_selecionados = []
        niveis_confianca = []
        
        for triangulo, score in triangulos_ordenados:
            confianca = self.calcular_confianca_por_score(score)
            nivel = self.get_nivel_confianca_numero(confianca)
            nivel_minimo = self.get_nivel_confianca_numero(self.confianca_minima_aposta)
            
            # Evitar repetir triângulos apostados recentemente
            if triangulo in self.ultimos_triangulos_apostados[-3:]:
                continue
            
            if nivel >= nivel_minimo and len(triangulos_selecionados) < self.max_triangulos_por_aposta:
                triangulos_selecionados.append(triangulo)
                niveis_confianca.append(confianca)
        
        # Se nenhum triângulo atingiu a confiança mínima, pega o top 1
        if not triangulos_selecionados and triangulos_ordenados:
            triangulos_selecionados = [triangulos_ordenados[0][0]]
            niveis_confianca = [self.calcular_confianca_por_score(triangulos_ordenados[0][1])]
        
        if not triangulos_selecionados:
            self.contador_giros_sem_entrada += 1
            return None
        
        self.contador_giros_sem_entrada = 0
        
        # Gerar números para apostar
        numeros_aposta = self.get_numeros_aposta_para_triangulos(triangulos_selecionados)
        
        # Calcular confiança geral
        niveis_valores = [self.get_nivel_confianca_numero(c) for c in niveis_confianca]
        nivel_medio = sum(niveis_valores) / len(niveis_valores)
        
        if nivel_medio >= 3.5:
            confianca_geral = "Excelente"
        elif nivel_medio >= 2.5:
            confianca_geral = "Muito Alta"
        elif nivel_medio >= 1.5:
            confianca_geral = "Alta"
        elif nivel_medio >= 0.5:
            confianca_geral = "Média"
        else:
            confianca_geral = "Baixa"
        
        # Construir gatilho descritivo
        detalhes_triangulos = []
        for t in triangulos_selecionados:
            score_t = scores[t]
            atraso = self.stats_triangulos[t]['atraso_atual']
            vizinhos = self.stats_triangulos[t]['vizinhos_quentes']
            detalhes_triangulos.append(f"{t}(S:{score_t:.0f}|A:{atraso}|V:{vizinhos})")
        
        gatilho = f"Múltiplos: {' + '.join(triangulos_selecionados)} | {', '.join(detalhes_triangulos)}"
        
        # Atualizar lista de últimos triângulos apostados
        self.ultimos_triangulos_apostados.extend(triangulos_selecionados)
        if len(self.ultimos_triangulos_apostados) > 10:
            self.ultimos_triangulos_apostados = self.ultimos_triangulos_apostados[-10:]
        
        previsao = {
            'nome': f'Triângulo Múltiplo ({len(triangulos_selecionados)} ativos)',
            'numeros_apostar': numeros_aposta,
            'gatilho': gatilho,
            'confianca_geral': confianca_geral,
            'triangulos': triangulos_selecionados,
            'scores': {t: scores[t] for t in triangulos_selecionados},
            'confiancas': dict(zip(triangulos_selecionados, niveis_confianca)),
            'total_numeros': len(numeros_aposta),
            'selecao_inteligente': len(numeros_aposta) < 15
        }
        
        self.entrada_ativa = True
        self.entrada_atual = previsao
        self.ultimo_gatilho = previsao
        
        for triangulo in triangulos_selecionados:
            self.stats_triangulos[triangulo]['tentativas'] += 1
        
        return previsao
    
    def registrar_entrada(self, acertou=False, triangulo_acertado=None):
        if self.entrada_atual:
            registro = {
                'timestamp': len(self.historico),
                'triangulos': self.entrada_atual['triangulos'],
                'numeros_apostados': self.entrada_atual['numeros_apostar'],
                'acertou': acertou,
                'confianca_geral': self.entrada_atual['confianca_geral'],
                'triangulo_acertado': triangulo_acertado if acertou else None
            }
            self.historico_entradas.append(registro)
            self.historico_multi.append(registro)
            
            if len(self.historico_entradas) > 50:
                self.historico_entradas = self.historico_entradas[-50:]
    
    def get_analise_detalhada(self):
        if len(self.historico) == 0:
            return "🔺 Estratégia Triângulo Múltiplo - Aguardando dados..."
        
        analise = "🔺 ANÁLISE TRIÂNGULO MÚLTIPLO v2\n"
        analise += "=" * 55 + "\n"
        analise += f"📊 Histórico: {len(self.historico)} números\n"
        analise += f"🎯 Último número: {self.historico[-1] if self.historico else 'N/A'}\n"
        analise += f"🎲 Máx triângulos por aposta: {self.max_triangulos_por_aposta}\n"
        analise += f"📈 Confiança mínima: {self.confianca_minima_aposta}\n"
        analise += f"🔄 Giro sem entrada: {self.contador_giros_sem_entrada}\n"
        analise += "=" * 55 + "\n\n"
        
        scores_atuais = {}
        for triangulo in self.triangulo_para_numeros.keys():
            scores_atuais[triangulo] = self.calcular_score_triangulo(triangulo)
        
        triangulos_ordenados = sorted(scores_atuais.items(), key=lambda x: x[1], reverse=True)
        
        analise += "📊 RANKING DE TRIÂNGULOS (Score 0-100):\n"
        
        for triangulo, score in triangulos_ordenados[:10]:
            stats = self.stats_triangulos[triangulo]
            confianca = self.calcular_confianca_por_score(score)
            
            if confianca == "Excelente":
                icone = "💎"
            elif confianca == "Muito Alta":
                icone = "🔥"
            elif confianca == "Alta":
                icone = "📈"
            elif confianca == "Média":
                icone = "⚪"
            else:
                icone = "❄️"
            
            atraso = stats['atraso_atual']
            vizinhos = stats['vizinhos_quentes']
            perf = stats['performance_media']
            
            analise += f"{icone} {triangulo}: Score {score:.0f} ({confianca})\n"
            analise += f"   📍 Atraso: {atraso} | Vizinhos: {vizinhos}x | Perf: {perf:.1f}%\n"
            analise += f"   🔢 Números: {self.get_numeros_do_triangulo(triangulo)}\n\n"
        
        if self.entrada_ativa and self.entrada_atual:
            triangulos_ativos = self.entrada_atual.get('triangulos', [])
            analise += "\n" + "=" * 55 + "\n"
            analise += "🎯 ENTRADA ATIVA (MÚLTIPLA):\n"
            for t in triangulos_ativos:
                conf = self.entrada_atual['confiancas'].get(t, 'N/A')
                score = self.entrada_atual['scores'].get(t, 0)
                analise += f"   🔺 {t}: Confiança {conf} (Score {score:.0f})\n"
            analise += f"📊 Confiança Geral: {self.entrada_atual['confianca_geral']}\n"
            analise += f"🔢 Total de números: {len(self.entrada_atual['numeros_apostar'])}\n"
            if self.entrada_atual.get('selecao_inteligente', False):
                analise += "🎯 Seleção inteligente ativa (≤15 números)\n"
        
        if self.historico_multi:
            analise += "\n📋 ÚLTIMAS ENTRADAS MÚLTIPLAS:\n"
            for entrada in list(self.historico_multi)[-5:]:
                resultado = "✅ ACERTOU" if entrada['acertou'] else "❌ ERROU"
                triangulos_str = ", ".join(entrada['triangulos'])
                if entrada['acertou'] and entrada.get('triangulo_acertado'):
                    resultado += f" ({entrada['triangulo_acertado']})"
                analise += f"🎯 [{triangulos_str}]: {resultado} (Conf: {entrada['confianca_geral']})\n"
        
        return analise
    
    def get_info_triangulos(self):
        info = {}
        for triangulo in self.triangulo_para_numeros.keys():
            info[triangulo] = {
                'numeros': self.get_numeros_do_triangulo(triangulo),
                'quantidade': len(self.get_numeros_do_triangulo(triangulo)),
                'vizinhos': self.get_todos_vizinhos_do_triangulo(triangulo),
                'stats': self.stats_triangulos.get(triangulo, {})
            }
        return info
    
    def zerar_estatisticas(self):
        for triangulo in self.stats_triangulos:
            self.stats_triangulos[triangulo] = {
                'acertos': 0,
                'tentativas': 0,
                'sequencia_atual': 0,
                'sequencia_maxima': 0,
                'performance_media': 0,
                'ultimo_sorteio': -1,
                'atraso_atual': 0,
                'max_atraso': 0,
                'vizinhos_quentes': 0
            }
        self.historico_entradas = []
        self.historico_multi = []
        self.ultimo_gatilho = None
        self.contador_giros_sem_entrada = 0
        self.entrada_ativa = False
        self.entrada_atual = None
        self.ultimos_triangulos_apostados = []
        logging.info("📊 Estatísticas do Triângulo Múltiplo zeradas")

# =============================
# SISTEMA DE GESTÃO (APENAS TRIÂNGULO)
# =============================
class SistemaRoletaCompleto:
    def __init__(self):
        self.estrategia_triangulo = EstrategiaTrianguloMultiplo()
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
            triangulo_sorteado = self.estrategia_triangulo.get_triangulo_do_numero(numero_real)
            acerto = triangulo_sorteado in triangulos_previsao
            if acerto:
                zonas_acertadas = [triangulo_sorteado]
            
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
        
        nova_previsao = self.estrategia_triangulo.analisar_triangulos_multi()
        
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
            
            logging.info("🔄 Estatísticas recentes resetadas (mantidos últimos 10 resultados)")
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
st.set_page_config(page_title="🔺 Triângulo Múltiplo - Roleta", layout="centered")
st.title("🔺 Estratégia Triângulo Múltiplo")

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

# Configurações do Triângulo
with st.sidebar.expander("🔺 Configurações Triângulo Múltiplo", expanded=True):
    st.write("**Configurações da Estratégia:**")
    
    max_triangulos = st.slider(
        "Máximo de triângulos por aposta:",
        min_value=1, max_value=5, value=st.session_state.sistema.estrategia_triangulo.max_triangulos_por_aposta,
        help="Quantos triângulos podem ser apostados simultaneamente"
    )
    
    confianca_minima = st.select_slider(
        "Confiança mínima para apostar:",
        options=["Baixa", "Média", "Alta", "Muito Alta", "Excelente"],
        value=st.session_state.sistema.estrategia_triangulo.confianca_minima_aposta,
        help="Apenas triângulos com confiança igual ou superior serão considerados"
    )
    
    if st.button("Aplicar Configurações"):
        st.session_state.sistema.estrategia_triangulo.max_triangulos_por_aposta = max_triangulos
        st.session_state.sistema.estrategia_triangulo.confianca_minima_aposta = confianca_minima
        salvar_sessao()
        st.success(f"✅ Configurações aplicadas!")

# Gerenciamento de Sessão
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
                st.error("❌ Nenhum save encontrado")
    
    st.write("---")
    
    col3, col4 = st.columns(2)
    
    with col3:
        if st.button("🔄 Reset Recente", use_container_width=True):
            st.session_state.sistema.reset_recente_estatisticas()
            st.success("✅ Reset recente!")
            st.rerun()
            
    with col4:
        if st.button("🗑️ Zerar Tudo", type="secondary", use_container_width=True):
            if st.checkbox("Confirmar zerar TUDO"):
                st.session_state.sistema.zerar_estatisticas_desempenho()
                st.error("🗑️ Todas estatísticas zeradas!")
                st.rerun()
    
    st.write("---")
    
    if st.button("🗑️ Limpar Sessão", type="secondary", use_container_width=True):
        if st.checkbox("Confirmar limpeza total"):
            limpar_sessao()
            st.error("🗑️ Sessão limpa!")
            st.stop()

# Telegram
with st.sidebar.expander("🔔 Telegram", expanded=False):
    telegram_token = st.text_input(
        "Bot Token:",
        value=st.session_state.telegram_token,
        type="password"
    )
    
    telegram_chat_id = st.text_input(
        "Chat ID:",
        value=st.session_state.telegram_chat_id
    )
    
    if st.button("Salvar Telegram"):
        st.session_state.telegram_token = telegram_token
        st.session_state.telegram_chat_id = telegram_chat_id
        salvar_sessao()
        st.success("✅ Salvo!")
        
    if st.button("Testar"):
        if telegram_token and telegram_chat_id:
            try:
                enviar_telegram("🔔 Teste - Triângulo Múltiplo funcionando!")
                st.success("✅ Enviado!")
            except Exception as e:
                st.error(f"Erro: {e}")
        else:
            st.error("Configure token e chat ID")

# Informações
with st.sidebar.expander("📊 Informações", expanded=False):
    st.write("**🔺 Estratégia Triângulo Múltiplo v2:**")
    st.write("**Como funciona:**")
    st.write("1. Cada número pertence a um triângulo (3 números consecutivos)")
    st.write("2. Calcula SCORE para cada triângulo:")
    st.write("   - Atraso (40%): tempo sem sair")
    st.write("   - Vizinhos quentes (30%): frequência de vizinhos")
    st.write("   - Performance (20%): taxa de acertos")
    st.write("   - Bônus (10%): sem acerto recente")
    st.write("3. Seleciona TOP N triângulos com confiança ≥ mínima")
    st.write("4. Aposta na UNIÃO dos triângulos + vizinhos")
    st.write("5. **Máximo de 3 triângulos por aposta**")
    st.write("---")
    st.write("**Níveis de Confiança:**")
    st.write("- 💎 Excelente (≥70 pts)")
    st.write("- 🔥 Muito Alta (55-69 pts)")
    st.write("- 📈 Alta (40-54 pts)")
    st.write("- ⚪ Média (25-39 pts)")
    st.write("- ❄️ Baixa (<25 pts)")

# Análise detalhada
with st.sidebar.expander("🔍 Análise Detalhada", expanded=False):
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

# Auto-refresh
st_autorefresh(interval=3000, key="refresh")

# Buscar resultado da API
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
    ultimos_10 = st.session_state.historico[-10:]
    numeros_str = " ".join(str(item['number'] if isinstance(item, dict) else item) for item in ultimos_10)
    st.write(numeros_str)
else:
    st.write("Nenhum número registrado")

# Status
status = st.session_state.sistema.get_status_rotacao()
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("🎯 Estratégia", status['estrategia_atual'])
with col2:
    st.metric("✅ Acertos Seguidos", status['sequencia_acertos'])
with col3:
    st.metric("❌ Erros Seguidos", status['sequencia_erros'])

# Previsão Ativa
st.subheader("🎯 Previsão Ativa")
sistema = st.session_state.sistema

if sistema.previsao_ativa:
    previsao = sistema.previsao_ativa
    st.success(f"**{previsao['nome']}**")
    
    if previsao.get('selecao_inteligente', False):
        st.success("🎯 **SELEÇÃO INTELIGENTE ATIVA** - 15 melhores números")
    
    triangulos_ativos = previsao.get('triangulos', [])
    confiancas = previsao.get('confiancas', {})
    scores = previsao.get('scores', {})
    
    st.write(f"**🔺 Triângulos Ativos ({len(triangulos_ativos)}):**")
    for t in triangulos_ativos:
        conf = confiancas.get(t, 'N/A')
        score = scores.get(t, 0)
        
        if conf == "Excelente":
            icon = "💎"
        elif conf == "Muito Alta":
            icon = "🔥"
        elif conf == "Alta":
            icon = "📈"
        elif conf == "Média":
            icon = "⚪"
        else:
            icon = "❄️"
        
        st.write(f"   {icon} **{t}**: {conf} (Score {score:.0f})")
    
    st.write(f"**📊 Confiança Geral:** {previsao.get('confianca_geral', 'Média')}")
    st.write(f"**📋 Gatilho:** {previsao['gatilho']}")
    
    st.write(f"**🔢 Números para apostar ({len(previsao['numeros_apostar'])}):**")
    
    # Mostrar números em grupos de 5 para melhor visualização
    numeros = sorted(previsao['numeros_apostar'])
    for i in range(0, len(numeros), 5):
        st.write(" ".join(map(str, numeros[i:i+5])))
    
    st.info("⏳ Aguardando próximo sorteio...")
else:
    st.info(f"🔺 Analisando padrões dos triângulos...")

# Desempenho
st.subheader("📈 Desempenho")

total = sistema.acertos + sistema.erros
taxa = (sistema.acertos / total * 100) if total > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 Acertos", sistema.acertos)
col2.metric("🔴 Erros", sistema.erros)
col3.metric("📊 Total", total)
col4.metric("✅ Taxa", f"{taxa:.1f}%")

# Últimas conferências
if sistema.historico_desempenho:
    st.write("**🔍 Últimas 5 Conferências:**")
    for resultado in sistema.historico_desempenho[-5:]:
        emoji = "🎉" if resultado['acerto'] else "❌"
        triangulos_str = ", ".join(resultado['zonas_envolvidas']) if resultado['zonas_envolvidas'] else "N/A"
        st.write(f"{emoji} {resultado['estrategia']}: Número {resultado['numero']} | Triângulos: {triangulos_str}")

# Download histórico
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        conteudo = f.read()
    st.download_button("📥 Baixar histórico", data=conteudo, file_name="historico_triangulo.json")

# Salvar sessão
salvar_sessao()
