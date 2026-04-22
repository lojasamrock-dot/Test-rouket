import streamlit as st
import json
import os
import requests
import logging
import numpy as np
import pandas as pd
from collections import Counter, deque, defaultdict
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
from sklearn.utils import resample
import joblib
from streamlit_autorefresh import st_autorefresh
import pickle

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_coluna_duzia.json"
ML_MODEL_PATH = "ml_roleta_model.pkl"
SCALER_PATH = "ml_scaler.pkl"
META_PATH = "ml_meta.pkl"

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
            'zonas_historico': list(st.session_state.sistema.estrategia_zonas.historico),
            'zonas_stats': st.session_state.sistema.estrategia_zonas.stats_zonas,
            'zonas_combinacoes_stats': st.session_state.sistema.estrategia_zonas.combinacoes_stats,
            'midas_historico': list(st.session_state.sistema.estrategia_midas.historico),
            'ml_historico': list(st.session_state.sistema.estrategia_ml.historico),
            'ml_contador_sorteios': st.session_state.sistema.estrategia_ml.contador_sorteios,
            'ml_sequencias_padroes': st.session_state.sistema.estrategia_ml.sequencias_padroes,
            'ml_metricas_padroes': st.session_state.sistema.estrategia_ml.metricas_padroes,
            'estrategia_selecionada': st.session_state.sistema.estrategia_selecionada,
            'zonas_ultima_combinacao_erro': st.session_state.sistema.estrategia_zonas.ultima_combinacao_erro,
            'zonas_combinacao_atual': st.session_state.sistema.estrategia_zonas.combinacao_atual,
            'markov_historico': list(st.session_state.sistema.estrategia_markov.historico) if hasattr(st.session_state.sistema, 'estrategia_markov') else [],
            'markov_matriz_transicao': st.session_state.sistema.estrategia_markov.matriz_transicao if hasattr(st.session_state.sistema, 'estrategia_markov') else {},
            'markov_contador_sorteios': st.session_state.sistema.estrategia_markov.contador_sorteios if hasattr(st.session_state.sistema, 'estrategia_markov') else 0,
            'score_engine_historico': list(st.session_state.sistema.estrategia_score.historico) if hasattr(st.session_state.sistema, 'estrategia_score') else [],
            'score_engine_lucky_tracking': st.session_state.sistema.estrategia_score.lucky_tracking if hasattr(st.session_state.sistema, 'estrategia_score') else [],
            'hedge_historico': list(st.session_state.sistema.estrategia_hedge.historico) if hasattr(st.session_state.sistema, 'estrategia_hedge') else [],
            'hedge_lucky_tracking': st.session_state.sistema.estrategia_hedge.lucky_tracking if hasattr(st.session_state.sistema, 'estrategia_hedge') else [],
            'hedge_transitions': dict(st.session_state.sistema.estrategia_hedge.transitions) if hasattr(st.session_state.sistema, 'estrategia_hedge') else {},
            'terminalum_historico': list(st.session_state.sistema.estrategia_terminalum.historico) if hasattr(st.session_state.sistema, 'estrategia_terminalum') else []
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
                estrategias_contador = session_data.get('sistema_estrategias_contador', {})
                if not isinstance(estrategias_contador, dict):
                    estrategias_contador = {}
                    
                st.session_state.sistema.acertos = session_data.get('sistema_acertos', 0)
                st.session_state.sistema.erros = session_data.get('sistema_erros', 0)
                st.session_state.sistema.estrategias_contador = estrategias_contador
                st.session_state.sistema.historico_desempenho = session_data.get('sistema_historico_desempenho', [])
                st.session_state.sistema.contador_sorteios_global = session_data.get('sistema_contador_sorteios_global', 0)
                st.session_state.sistema.sequencia_erros = session_data.get('sistema_sequencia_erros', 0)
                st.session_state.sistema.ultima_estrategia_erro = session_data.get('sistema_ultima_estrategia_erro', '')
                st.session_state.sistema.estrategia_selecionada = session_data.get('estrategia_selecionada', 'Zonas')
                
                zonas_historico = session_data.get('zonas_historico', [])
                st.session_state.sistema.estrategia_zonas.historico = deque(zonas_historico, maxlen=70)
                st.session_state.sistema.estrategia_zonas.stats_zonas = session_data.get('zonas_stats', {
                    'Vermelha': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0},
                    'Azul': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0},
                    'Amarela': {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0}
                })
                st.session_state.sistema.estrategia_zonas.combinacoes_stats = session_data.get('zonas_combinacoes_stats', {})
                st.session_state.sistema.estrategia_zonas.ultima_combinacao_erro = session_data.get('zonas_ultima_combinacao_erro', '')
                st.session_state.sistema.estrategia_zonas.combinacao_atual = session_data.get('zonas_combinacao_atual', '')
                
                midas_historico = session_data.get('midas_historico', [])
                st.session_state.sistema.estrategia_midas.historico = deque(midas_historico, maxlen=15)
                
                ml_historico = session_data.get('ml_historico', [])
                st.session_state.sistema.estrategia_ml.historico = deque(ml_historico, maxlen=30)
                st.session_state.sistema.estrategia_ml.contador_sorteios = session_data.get('ml_contador_sorteios', 0)
                st.session_state.sistema.estrategia_ml.sequencias_padroes = session_data.get('ml_sequencias_padroes', {
                    'sequencias_ativas': {},
                    'historico_sequencias': [],
                    'padroes_detectados': []
                })
                st.session_state.sistema.estrategia_ml.metricas_padroes = session_data.get('ml_metricas_padroes', {
                    'padroes_detectados_total': 0,
                    'padroes_acertados': 0,
                    'padroes_errados': 0,
                    'eficiencia_por_tipo': {},
                    'historico_validacao': []
                })
                
                markov_historico = session_data.get('markov_historico', [])
                if hasattr(st.session_state.sistema, 'estrategia_markov'):
                    st.session_state.sistema.estrategia_markov.historico = deque(markov_historico, maxlen=200)
                    st.session_state.sistema.estrategia_markov.matriz_transicao = session_data.get('markov_matriz_transicao', {})
                    st.session_state.sistema.estrategia_markov.contador_sorteios = session_data.get('markov_contador_sorteios', 0)
                
                score_engine_historico = session_data.get('score_engine_historico', [])
                if hasattr(st.session_state.sistema, 'estrategia_score'):
                    st.session_state.sistema.estrategia_score.historico = deque(score_engine_historico, maxlen=200)
                    st.session_state.sistema.estrategia_score.lucky_tracking = session_data.get('score_engine_lucky_tracking', [])
                
                hedge_historico = session_data.get('hedge_historico', [])
                if hasattr(st.session_state.sistema, 'estrategia_hedge'):
                    st.session_state.sistema.estrategia_hedge.historico = deque(hedge_historico, maxlen=200)
                    st.session_state.sistema.estrategia_hedge.lucky_tracking = session_data.get('hedge_lucky_tracking', [])
                    st.session_state.sistema.estrategia_hedge.transitions = defaultdict(Counter, session_data.get('hedge_transitions', {}))
                
                terminalum_historico = session_data.get('terminalum_historico', [])
                if hasattr(st.session_state.sistema, 'estrategia_terminalum'):
                    st.session_state.sistema.estrategia_terminalum.historico = deque(terminalum_historico, maxlen=200)
            
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
        
        if 'Zonas' in nome_estrategia:
            zonas_envolvidas = previsao.get('zonas_envolvidas', [])
            if len(zonas_envolvidas) > 1:
                zona1 = zonas_envolvidas[0]
                zona2 = zonas_envolvidas[1]
                nucleo1 = "7" if zona1 == 'Vermelha' else "10" if zona1 == 'Azul' else "2"
                nucleo2 = "7" if zona2 == 'Vermelha' else "10" if zona2 == 'Azul' else "2"
                mensagem = f"📍 Núcleos {nucleo1} + {nucleo2}"
            else:
                zona = previsao.get('zona', '')
                if zona == 'Vermelha':
                    mensagem = "📍 Núcleo 7"
                elif zona == 'Azul':
                    mensagem = "📍 Núcleo 10"
                elif zona == 'Amarela':
                    mensagem = "📍 Núcleo 2"
                else:
                    mensagem = f"📍 Núcleo {zona}"
        elif 'Machine Learning' in nome_estrategia or 'ML' in nome_estrategia or 'CatBoost' in nome_estrategia:
            zonas_envolvidas = previsao.get('zonas_envolvidas', [])
            if len(zonas_envolvidas) > 1:
                zona1 = zonas_envolvidas[0]
                zona2 = zonas_envolvidas[1]
                nucleo1 = "7" if zona1 == 'Vermelha' else "10" if zona1 == 'Azul' else "2"
                nucleo2 = "7" if zona2 == 'Vermelha' else "10" if zona2 == 'Azul' else "2"
                mensagem = f"🤖 Núcleos {nucleo1} + {nucleo2}"
            else:
                zona_ml = previsao.get('zona_ml', '')
                numeros_apostar = previsao.get('numeros_apostar', [])
                if 2 in numeros_apostar:
                    mensagem = "🤖 Zona 2"
                elif 7 in numeros_apostar:
                    mensagem = "🤖 Zona 7"
                elif 10 in numeros_apostar:
                    mensagem = "🤖 Zona 10"
                else:
                    if zona_ml == 'Vermelha':
                        mensagem = "🤖 Zona 7"
                    elif zona_ml == 'Azul':
                        mensagem = "🤖 Zona 10"  
                    elif zona_ml == 'Amarela':
                        mensagem = "🤖 Zona 2"
                    else:
                        mensagem = f"🤖 Zona {zona_ml}"
        elif 'Markov' in nome_estrategia:
            mensagem = f"🎲 Cadeia de Markov - {len(numeros_apostar)} números mais prováveis"
        elif 'Score Engine' in nome_estrategia:
            mensagem = f"🧠 Score Engine - Top {len(numeros_apostar)} números"
        elif 'Hedge Fund' in nome_estrategia:
            mensagem = f"🏦 Hedge Fund Pro - Sinal de alta confiança ({len(numeros_apostar)} números)"
        elif 'Terminal Um' in nome_estrategia:
            mensagem = f"🎯 Terminal Um - Gatilho ativado! ({len(numeros_apostar)} números)"
        else:
            mensagem = f"💰 {previsao['nome']}"
        
        st.toast(f"🎯 Nova Previsão", icon="🔥")
        st.warning(f"🔔 {mensagem}")
        
        if 'telegram_token' in st.session_state and 'telegram_chat_id' in st.session_state:
            if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                enviar_alerta_numeros_simplificado(previsao)
                enviar_telegram(f"🔔 PREVISÃO\n{mensagem}")
                
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar previsão: {e}")

def enviar_alerta_numeros_simplificado(previsao):
    """Envia alerta alternativo super simplificado com os números para apostar"""
    try:
        nome_estrategia = previsao['nome']
        numeros_apostar = sorted(previsao['numeros_apostar'])
        
        metade = len(numeros_apostar) // 2
        linha1 = " ".join(map(str, numeros_apostar[:metade]))
        linha2 = " ".join(map(str, numeros_apostar[metade:]))
        
        if 'Zonas' in nome_estrategia:
            emoji = "📍"
        elif 'ML' in nome_estrategia:
            emoji = "🤖"
        elif 'Markov' in nome_estrategia:
            emoji = "🎲"
        elif 'Score Engine' in nome_estrategia:
            emoji = "🧠"
        elif 'Hedge Fund' in nome_estrategia:
            emoji = "🏦"
        elif 'Terminal Um' in nome_estrategia:
            emoji = "🎯"
        else:
            emoji = "💰"
            
        mensagem_simplificada = f"{emoji} APOSTAR AGORA\n{linha1}\n{linha2}"
        
        enviar_telegram(mensagem_simplificada)
        logging.info("🔔 Alerta simplificado enviado para Telegram")
        
    except Exception as e:
        logging.error(f"Erro ao enviar alerta simplificado: {e}")

def enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada=None, multiplicador=None):
    """Envia notificação de resultado super simplificado com multiplicador se for raio"""
    try:
        if acerto:
            if 'Zonas' in nome_estrategia and zona_acertada:
                if '+' in zona_acertada:
                    zonas = zona_acertada.split('+')
                    nucleos = []
                    for zona in zonas:
                        if zona == 'Vermelha':
                            nucleos.append("7")
                        elif zona == 'Azul':
                            nucleos.append("10")
                        elif zona == 'Amarela':
                            nucleos.append("2")
                        else:
                            nucleos.append(zona)
                    nucleo_str = "+".join(nucleos)
                    mensagem = f"✅ Acerto Núcleos {nucleo_str}\n🎲 Número: {numero_real}"
                else:
                    if zona_acertada == 'Vermelha':
                        nucleo = "7"
                    elif zona_acertada == 'Azul':
                        nucleo = "10"
                    elif zona_acertada == 'Amarela':
                        nucleo = "2"
                    else:
                        nucleo = zona_acertada
                    mensagem = f"✅ Acerto Núcleo {nucleo}\n🎲 Número: {numero_real}"
            elif 'ML' in nome_estrategia and zona_acertada:
                if '+' in zona_acertada:
                    zonas = zona_acertada.split('+')
                    nucleos = []
                    for zona in zonas:
                        if zona == 'Vermelha':
                            nucleos.append("7")
                        elif zona == 'Azul':
                            nucleos.append("10")
                        elif zona == 'Amarela':
                            nucleos.append("2")
                        else:
                            nucleos.append(zona)
                    nucleo_str = "+".join(nucleos)
                    mensagem = f"✅ Acerto Núcleos {nucleo_str}\n🎲 Número: {numero_real}"
                else:
                    if zona_acertada == 'Vermelha':
                        nucleo = "7"
                    elif zona_acertada == 'Azul':
                        nucleo = "10"
                    elif zona_acertada == 'Amarela':
                        nucleo = "2"
                    else:
                        nucleo = zona_acertada
                    mensagem = f"✅ Acerto Núcleo {nucleo}\n🎲 Número: {numero_real}"
            else:
                mensagem = f"✅ Acerto\n🎲 Número: {numero_real}"
        else:
            mensagem = f"❌ Erro\n🎲 Número: {numero_real}"
        
        if multiplicador and multiplicador > 0:
            mensagem += f"\n⚡ RAIO! Multiplicador: {multiplicador}x"
        
        st.toast(f"🎲 Resultado", icon="✅" if acerto else "❌")
        st.success(f"📢 {mensagem}") if acerto else st.error(f"📢 {mensagem}")
        
        if 'telegram_token' in st.session_state and 'telegram_chat_id' in st.session_state:
            if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                enviar_telegram(f"📢 RESULTADO\n{mensagem}")
                enviar_alerta_conferencia_simplificado(numero_real, acerto, nome_estrategia, multiplicador)
                
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar resultado: {e}")

def enviar_alerta_conferencia_simplificado(numero_real, acerto, nome_estrategia, multiplicador=None):
    """Envia alerta de conferência super simplificado com multiplicador se for raio"""
    try:
        if acerto:
            mensagem = f"🎉 ACERTOU! {numero_real}"
        else:
            mensagem = f"💥 ERROU! {numero_real}"
        
        if multiplicador and multiplicador > 0:
            mensagem += f" ⚡{multiplicador}x"
            
        enviar_telegram(mensagem)
        logging.info("🔔 Alerta de conferência enviado para Telegram")
        
    except Exception as e:
        logging.error(f"Erro ao enviar alerta de conferência: {e}")

def enviar_rotacao_automatica(estrategia_anterior, estrategia_nova, motivo=None):
    """Envia notificação de rotação automática"""
    try:
        if motivo:
            mensagem = f"🔄 ROTAÇÃO AUTOMÁTICA\n{estrategia_anterior} → {estrategia_nova}\n📋 Motivo: {motivo}"
        else:
            mensagem = f"🔄 ROTAÇÃO AUTOMÁTICA\n{estrategia_anterior} → {estrategia_nova}"
        
        st.toast("🔄 Rotação Automática", icon="🔄")
        st.warning(f"🔄 {mensagem}")
        
        if 'telegram_token' in st.session_state and 'telegram_chat_id' in st.session_state:
            if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                enviar_telegram(f"🔄 ROTAÇÃO\n{mensagem}")
                
    except Exception as e:
        logging.error(f"Erro ao enviar rotação: {e}")

def enviar_troca_combinacao_zonas(combinacao_antiga, combinacao_nova):
    """Envia notificação de troca de combinação dentro da estratégia Zonas"""
    try:
        mensagem = f"🔄 TROCA DE COMBINAÇÃO ZONAS\n{combinacao_antiga} → {combinacao_nova}\n📋 Motivo: Erro na combinação anterior"
        
        st.info(f"🔄 {mensagem}")
        
        if 'telegram_token' in st.session_state and 'telegram_chat_id' in st.session_state:
            if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                enviar_telegram(f"🔄 TROCA ZONAS\n{mensagem}")
                
    except Exception as e:
        logging.error(f"Erro ao enviar troca de combinação: {e}")

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
        
    def selecionar_melhores_15_numeros(self, numeros_candidatos, historico, estrategia_tipo="Zonas"):
        if len(numeros_candidatos) <= 15:
            return numeros_candidatos
            
        scores = {}
        for numero in numeros_candidatos:
            scores[numero] = self.calcular_score_numero(numero, historico, estrategia_tipo)
        
        numeros_ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        melhores_15 = [num for num, score in numeros_ordenados[:15]]
        
        logging.info(f"🎯 Seleção Inteligente: {len(numeros_candidatos)} → 15 números")
        return melhores_15
    
    def calcular_score_numero(self, numero, historico, estrategia_tipo):
        score_total = 0
        
        score_frequencia = self.calcular_score_frequencia(numero, historico)
        score_total += score_frequencia * 0.35
        
        score_posicao = self.calcular_score_posicao_roda(numero, historico)
        score_total += score_posicao * 0.25
        
        score_vizinhos = self.calcular_score_vizinhos(numero, historico)
        score_total += score_vizinhos * 0.20
        
        score_tendencia = self.calcular_score_tendencia(numero, historico)
        score_total += score_tendencia * 0.20
        
        return score_total
    
    def calcular_score_frequencia(self, numero, historico):
        if len(historico) < 5:
            return 0.5
            
        historico_lista = list(historico)
        
        janela_curta = historico_lista[-10:] if len(historico_lista) >= 10 else historico_lista
        freq_curta = sum(1 for n in janela_curta if n == numero) / len(janela_curta)
        
        janela_media = historico_lista[-25:] if len(historico_lista) >= 25 else historico_lista
        freq_media = sum(1 for n in janela_media if n == numero) / len(janela_media)
        
        janela_longa = historico_lista[-50:] if len(historico_lista) >= 50 else historico_lista
        freq_longa = sum(1 for n in janela_longa if n == numero) / len(janela_longa)
        
        score = (freq_curta * 0.5 + freq_media * 0.3 + freq_longa * 0.2)
        return min(score * 3, 1.0)
    
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

    def get_analise_selecao(self, numeros_originais, numeros_selecionados, historico):
        analise = f"🎯 ANÁLISE DA SELEÇÃO INTELIGENTE\n"
        analise += f"📊 Redução: {len(numeros_originais)} → {len(numeros_selecionados)} números\n"
        analise += f"🎲 Números selecionados: {sorted(numeros_selecionados)}\n"
        
        if historico:
            ultimos_20 = list(historico)[-20:] if len(historico) >= 20 else list(historico)
            acertos_potenciais = sum(1 for n in ultimos_20 if n in numeros_selecionados)
            analise += f"📈 Eficiência teórica: {acertos_potenciais}/20 ({acertos_potenciais/20*100:.1f}%)\n"
        
        return analise

# =============================
# CLASSE PRINCIPAL DA ROLETA ATUALIZADA
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

# ===== NOVO: ESTRATÉGIA TERMINAL UM =====
class EstrategiaTerminalUm:
    """Estratégia Terminal Um: Gatilho após 14 sorteios sem Terminal 1 e 15º número específico"""
    
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=200)
        self.nome = "Terminal Um Pro"
        self.sistema_selecao = SistemaSelecaoInteligente()
        
        # Definição dos terminais
        self.terminal_1 = [1, 11, 21, 31]
        self.terminal_2 = [2, 12, 22, 32]
        
        # Lista de números gatilho (fornecida pelo usuário)
        self.numeros_gatilho = [4, 0, 10, 27, 9, 14, 25, 19, 1, 2, 32, 16]
        
        # Janela de análise
        self.janela_analise = 14
        self.raio_vizinhos = 2  # 2 vizinhos antes e 2 depois
        
    def adicionar_numero(self, numero):
        """Adiciona número ao histórico"""
        self.historico.append(numero)
        if 'sistema' in st.session_state:
            salvar_sessao()
    
    def _verificar_ausencia_terminal1(self, sequencia):
        """Verifica se nenhum número do Terminal 1 está presente na sequência"""
        return not any(n in self.terminal_1 for n in sequencia)
    
    def _get_vizinhos_numero(self, numero, raio=2):
        """Retorna os vizinhos físicos de um número na roda"""
        if numero not in self.roleta.race:
            return []
        
        posicao = self.roleta.race.index(numero)
        vizinhos = []
        
        # Vizinhos anteriores
        for offset in range(-raio, 0):
            vizinho = self.roleta.race[(posicao + offset) % 37]
            vizinhos.append(vizinho)
        
        # Vizinhos posteriores
        for offset in range(1, raio + 1):
            vizinho = self.roleta.race[(posicao + offset) % 37]
            vizinhos.append(vizinho)
        
        return vizinhos
    
    def _gerar_numeros_aposta(self):
        """Gera o conjunto completo de números para apostar"""
        numeros_aposta = set()
        
        # Adiciona Terminal 1 e Terminal 2
        numeros_aposta.update(self.terminal_1)
        numeros_aposta.update(self.terminal_2)
        
        # Adiciona vizinhos de cada número do Terminal 1
        for num in self.terminal_1:
            vizinhos = self._get_vizinhos_numero(num, self.raio_vizinhos)
            numeros_aposta.update(vizinhos)
        
        return sorted(list(numeros_aposta))
    
    def analisar(self):
        """Analisa se as condições de gatilho foram atendidas"""
        if len(self.historico) < self.janela_analise + 1:
            return None
        
        hist_list = list(self.historico)
        
        # Últimos 14 números (índices -15 até -2)
        ultimos_14 = hist_list[-15:-1] if len(hist_list) >= 15 else hist_list[:-1]
        
        # 15º número (o mais recente)
        numero_gatilho = hist_list[-1]
        
        # Verifica condições
        ausencia_terminal1 = self._verificar_ausencia_terminal1(ultimos_14)
        gatilho_ativado = numero_gatilho in self.numeros_gatilho
        
        if ausencia_terminal1 and gatilho_ativado:
            numeros_apostar = self._gerar_numeros_aposta()
            
            # Aplica seleção inteligente se houver muitos números
            numeros_originais_qtd = len(numeros_apostar)
            if len(numeros_apostar) > 15:
                numeros_apostar = self.sistema_selecao.selecionar_melhores_15_numeros(
                    numeros_apostar, self.historico, "TerminalUm"
                )
            
            # Gera mensagem de gatilho detalhada
            terminais_ausentes = [n for n in self.terminal_1]
            gatilho = (f"🎯 TERMINAL UM ATIVADO!\n"
                      f"📊 14 sorteios sem: {terminais_ausentes}\n"
                      f"🔥 Gatilho no 15º: {numero_gatilho}")
            
            return {
                'nome': 'Terminal Um Pro',
                'numeros_apostar': numeros_apostar,
                'gatilho': gatilho,
                'confianca': 'Alta',
                'tipo': 'terminal_um',
                'selecao_inteligente': len(numeros_apostar) < numeros_originais_qtd,
                'numeros_originais_qtd': numeros_originais_qtd,
                'numero_gatilho': numero_gatilho,
                'terminais_ausentes': terminais_ausentes,
                'janela_14': ultimos_14[-5:] if len(ultimos_14) > 5 else ultimos_14  # últimos 5 da janela
            }
        
        return None
    
    def get_analise(self):
        """Retorna análise detalhada do estado atual"""
        if len(self.historico) < 5:
            return "🎯 Terminal Um: Aguardando mais dados (mínimo 5 números)"
        
        hist_list = list(self.historico)
        ultimos = hist_list[-min(20, len(hist_list)):]
        
        analise = "🎯 ANÁLISE TERMINAL UM PRO\n"
        analise += "=" * 45 + "\n"
        analise += f"📊 Total histórico: {len(self.historico)} números\n"
        analise += f"🎲 Últimos 10: {ultimos[-10:]}\n\n"
        
        # Status atual da janela de 14
        if len(hist_list) >= 14:
            janela_14 = hist_list[-15:-1] if len(hist_list) >= 15 else hist_list[-14:]
            ausentes = not self._verificar_ausencia_terminal1(janela_14)
            tem_terminal1 = any(n in self.terminal_1 for n in janela_14)
            
            analise += f"📈 Janela 14 sorteios: {len(janela_14)} números\n"
            analise += f"❌ Terminal 1 presente? {'SIM' if tem_terminal1 else 'NÃO'}\n"
            
            if tem_terminal1:
                terminais_encontrados = [n for n in janela_14 if n in self.terminal_1]
                analise += f"   Números: {terminais_encontrados}\n"
            else:
                analise += f"   ✅ JANELA LIMPA! Aguardando gatilho...\n"
        
        # Status do último número
        if len(hist_list) >= 1:
            ultimo = hist_list[-1]
            analise += f"\n🎲 Último número: {ultimo}\n"
            if ultimo in self.numeros_gatilho:
                analise += f"   ⚡ Número GATILHO! ({ultimo})\n"
            else:
                analise += f"   ⏳ Aguardando número gatilho...\n"
        
        # Lista de números gatilho
        analise += f"\n🎯 Números Gatilho: {sorted(self.numeros_gatilho)}\n"
        analise += f"💎 Terminal 1: {self.terminal_1}\n"
        analise += f"💎 Terminal 2: {self.terminal_2}\n"
        
        # Números que seriam apostados se ativasse agora
        numeros_aposta = self._gerar_numeros_aposta()
        analise += f"\n📋 Aposta potencial ({len(numeros_aposta)} números):\n"
        analise += f"{numeros_aposta[:10]}..." if len(numeros_aposta) > 10 else f"{numeros_aposta}"
        
        return analise
    
    def zerar_estatisticas(self):
        """Zera o histórico"""
        self.historico.clear()
        logging.info("🎯 Estatísticas do Terminal Um zeradas")

# ===== ANALISADOR DE ESTADO DA ROLETA =====
class AnalisadorEstadoRoleta:
    """Classifica o momento atual da roleta e calcula entropia"""
    
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.estados = ['RANDOM', 'HOT_CLUSTER', 'SECTOR_RUN', 'DELAY_BREAK']
        
    def calcular_entropia(self, numeros, janela=15):
        """Calcula entropia de Shannon para medir aleatoriedade"""
        if isinstance(numeros, deque):
            numeros = list(numeros)
        if len(numeros) < janela:
            return 5.0
        
        seq = numeros[-janela:]
        counts = np.bincount(seq, minlength=37)
        probs = counts / len(seq)
        probs = probs[probs > 0]
        
        if len(probs) <= 1:
            return 0.0
        
        entropia = -np.sum(probs * np.log2(probs))
        entropia_normalizada = entropia / np.log2(37)
        return entropia_normalizada
    
    def classificar_estado(self, historico):
        """Classifica o estado atual baseado nos últimos giros"""
        if isinstance(historico, deque):
            hist = list(historico)
        else:
            hist = historico
        if len(hist) < 10:
            return 'RANDOM', 0.0
        
        ultimos_10 = hist[-10:]
        
        repeticoes = sum(1 for i in range(1, len(ultimos_10)) if ultimos_10[i] == ultimos_10[i-1])
        if repeticoes >= 2:
            return 'HOT_CLUSTER', 0.8
        
        vizinhos_sequencia = 0
        for i in range(1, len(ultimos_10)):
            atual = ultimos_10[i]
            anterior = ultimos_10[i-1]
            vizinhos_ant = self.roleta.get_vizinhos_fisicos(anterior, raio=2)
            if atual in vizinhos_ant:
                vizinhos_sequencia += 1
        
        if vizinhos_sequencia >= 4:
            return 'SECTOR_RUN', 0.7
        
        if len(hist) > 30:
            for num in range(37):
                if num not in hist[-20:] and num in hist[-5:]:
                    return 'DELAY_BREAK', 0.6
        
        return 'RANDOM', 0.0
    
    def momento_favoravel(self, historico, threshold_entropia=0.5):
        """Decide se o momento é favorável para apostar"""
        estado, confianca = self.classificar_estado(historico)
        entropia = self.calcular_entropia(historico)
        
        favoravel = (estado != 'RANDOM') and (entropia < threshold_entropia) and (confianca >= 0.6)
        
        return favoravel, estado, entropia, confianca

# ===== FILTRO DE ENTRADA =====
class FiltroEntrada:
    """Decide se deve apostar com base no estado e força do sinal"""
    
    def __init__(self):
        self.analisador = AnalisadorEstadoRoleta()
        self.threshold_entropia = 0.45
        self.threshold_score = 0.4
        
    def deve_apostar(self, historico, scores_numeros):
        """Retorna True se as condições forem favoráveis"""
        if len(historico) < 15:
            return False, "Histórico insuficiente"
        
        favoravel, estado, entropia, confianca = self.analisador.momento_favoravel(
            historico, self.threshold_entropia
        )
        
        if not favoravel:
            return False, f"Estado {estado} | Entropia {entropia:.2f} (alta)"
        
        max_score = max(scores_numeros.values()) if scores_numeros else 0
        if max_score < self.threshold_score:
            return False, f"Sinal fraco (max score {max_score:.2f})"
        
        return True, f"✅ SINAL FORTE | {estado} | Entropia {entropia:.2f}"

# ===== ESTRATÉGIA HEDGE FUND PRO =====
class EstrategiaHedgeFund:
    def __init__(self, top_k: int = 8):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=200)
        self.lucky_tracking = deque(maxlen=50)
        self.nome = "Hedge Fund Pro"
        self.top_k = top_k
        self.sistema_selecao = SistemaSelecaoInteligente()
        self.filtro = FiltroEntrada()
        self.transitions = defaultdict(Counter)
        self.pesos = {
            'markov': 0.40,
            'recencia': 0.20,
            'cluster': 0.15,
            'vizinhanca': 0.15,
            'lucky': 0.10
        }
        
    def adicionar_numero(self, numero, lucky_numbers=None):
        self.historico.append(numero)
        if lucky_numbers:
            self.lucky_tracking.extend(lucky_numbers)
        
        hist_list = list(self.historico)
        if len(hist_list) >= 2:
            atual = hist_list[-2]
            prox = hist_list[-1]
            self.transitions[atual][prox] += 1
            
        if 'sistema' in st.session_state:
            salvar_sessao()
    
    def _prob_markov(self, numero, ultimo_numero):
        if ultimo_numero not in self.transitions:
            return 0.0
        total = sum(self.transitions[ultimo_numero].values())
        if total == 0:
            return 0.0
        count = self.transitions[ultimo_numero].get(numero, 0)
        return count / total
    
    def _score_recencia(self):
        if len(self.historico) < 5:
            return {i: 0.0 for i in range(37)}
        recentes = list(self.historico)[-15:]
        contagem = Counter(recentes)
        max_count = max(contagem.values()) if contagem else 1
        return {i: contagem.get(i, 0) / max_count for i in range(37)}
    
    def _score_cluster(self):
        if len(self.historico) < 3:
            return {i: 0.0 for i in range(37)}
        hist_list = list(self.historico)
        cluster = Counter()
        for i in range(1, len(hist_list)):
            if hist_list[i] == hist_list[i-1]:
                cluster[hist_list[i]] += 1
        max_cluster = max(cluster.values()) if cluster else 1
        return {i: cluster.get(i, 0) / max_cluster for i in range(37)}
    
    def _score_vizinhanca(self):
        if len(self.historico) < 5:
            return {i: 0.0 for i in range(37)}
        recentes = list(self.historico)[-10:]
        vizinhanca_score = {i: 0.0 for i in range(37)}
        for num in recentes:
            vizinhos = self.roleta.get_vizinhos_fisicos(num, raio=2)
            for v in vizinhos:
                vizinhanca_score[v] += 1
        max_score = max(vizinhanca_score.values()) if vizinhanca_score else 1
        return {i: vizinhanca_score[i] / max_score for i in range(37)}
    
    def _score_lucky(self):
        if len(self.lucky_tracking) == 0:
            return {i: 0.0 for i in range(37)}
        contagem = Counter(self.lucky_tracking)
        max_lucky = max(contagem.values()) if contagem else 1
        return {i: contagem.get(i, 0) / max_lucky for i in range(37)}
    
    def calcular_score_total(self):
        if len(self.historico) < 5:
            return {}, {}
        ultimo = self.historico[-1]
        markov = {i: self._prob_markov(i, ultimo) for i in range(37)}
        recencia = self._score_recencia()
        cluster = self._score_cluster()
        vizinhanca = self._score_vizinhanca()
        lucky = self._score_lucky()
        
        scores = {}
        detalhes = {}
        for n in range(37):
            score = (
                markov[n] * self.pesos['markov'] +
                recencia[n] * self.pesos['recencia'] +
                cluster[n] * self.pesos['cluster'] +
                vizinhanca[n] * self.pesos['vizinhanca'] +
                lucky[n] * self.pesos['lucky']
            )
            scores[n] = score
            detalhes[n] = {
                'markov': markov[n],
                'recencia': recencia[n],
                'cluster': cluster[n],
                'vizinhanca': vizinhanca[n],
                'lucky': lucky[n],
                'total': score
            }
        return scores, detalhes
    
    def analisar(self):
        if len(self.historico) < 5:
            return None
        scores, detalhes = self.calcular_score_total()
        pode_apostar, motivo = self.filtro.deve_apostar(self.historico, scores)
        
        if not pode_apostar:
            logging.info(f"🚫 Hedge Fund: {motivo}")
            return None
        
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_numeros = [num for num, score in ranking[:self.top_k]]
        numeros_originais_qtd = len(top_numeros)
        if len(top_numeros) > 12:
            top_numeros = self.sistema_selecao.selecionar_melhores_15_numeros(
                top_numeros, self.historico, "HedgeFund"
            )
        
        max_score = scores[top_numeros[0]]
        if max_score >= 0.6:
            confianca = "Muito Alta"
        elif max_score >= 0.45:
            confianca = "Alta"
        elif max_score >= 0.35:
            confianca = "Média"
        else:
            confianca = "Baixa"
        
        estado, _ = self.filtro.analisador.classificar_estado(self.historico)
        entropia_val = self.filtro.analisador.calcular_entropia(self.historico)
        
        gatilho = f"🏦 Hedge Fund | {estado} | Entropia {entropia_val:.2f} | Max Score {max_score:.3f}"
        
        return {
            'nome': 'Hedge Fund Pro',
            'numeros_apostar': top_numeros,
            'gatilho': gatilho,
            'confianca': confianca,
            'tipo': 'hedge_fund',
            'selecao_inteligente': len(top_numeros) < self.top_k,
            'numeros_originais_qtd': numeros_originais_qtd,
            'estado': estado,
            'entropia': entropia_val,
            'max_score': max_score
        }
    
    def get_analise(self):
        if len(self.historico) < 5:
            return "🏦 Hedge Fund: Aguardando mais dados..."
        
        scores, detalhes = self.calcular_score_total()
        estado, _ = self.filtro.analisador.classificar_estado(self.historico)
        entropia = self.filtro.analisador.calcular_entropia(self.historico)
        pode_apostar, motivo = self.filtro.deve_apostar(self.historico, scores)
        
        analise = f"🏦 ANÁLISE HEDGE FUND PRO\n"
        analise += "=" * 45 + "\n"
        analise += f"📊 Estado: {estado}\n"
        analise += f"📉 Entropia: {entropia:.3f} "
        analise += f"({'✅ Baixa' if entropia < 0.45 else '⚠️ Alta'})\n"
        analise += f"🎯 Sinal: {'🟢 ENTRAR' if pode_apostar else '🔴 AGUARDAR'} - {motivo}\n"
        analise += "=" * 45 + "\n"
        
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
        analise += "🏆 Top 10 Scores:\n"
        for i, (num, score) in enumerate(ranking, 1):
            det = detalhes[num]
            barra = "█" * int(score * 20)
            analise += f"{i:2d}. {num:2d}: {barra} {score:.3f} "
            analise += f"(M:{det['markov']:.2f} R:{det['recencia']:.2f} C:{det['cluster']:.2f})\n"
        
        return analise
    
    def zerar_estatisticas(self):
        self.historico.clear()
        self.lucky_tracking.clear()
        self.transitions.clear()
        logging.info("🏦 Estatísticas do Hedge Fund zeradas")

# ===== ESTRATÉGIA SCORE ENGINE =====
class EstrategiaScoreEngine:
    def __init__(self, top_k: int = 12):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=200)
        self.lucky_tracking = deque(maxlen=50)
        self.nome = "Score Engine Pro"
        self.top_k = top_k
        self.sistema_selecao = SistemaSelecaoInteligente()
        self.pesos = {'frequencia': 0.25, 'recencia': 0.25, 'cluster': 0.20, 'vizinhanca': 0.10, 'delay': 0.10, 'lucky': 0.10}
        self.janela_recencia = 20
        self.janela_frequencia = 50
        self.janela_vizinhanca = 30
        
    def adicionar_numero(self, numero, lucky_numbers=None):
        self.historico.append(numero)
        if lucky_numbers:
            self.lucky_tracking.extend(lucky_numbers)
        if 'sistema' in st.session_state:
            salvar_sessao()
    
    def _calcular_frequencia(self):
        if len(self.historico) < 5: return {i: 0.0 for i in range(37)}
        hist_list = list(self.historico)
        janela = hist_list[-self.janela_frequencia:] if len(hist_list) >= self.janela_frequencia else hist_list
        contagem = Counter(janela)
        max_freq = max(contagem.values()) if contagem else 1
        return {i: contagem.get(i, 0) / max_freq for i in range(37)}
    
    def _calcular_recencia(self):
        if len(self.historico) < 5: return {i: 0.0 for i in range(37)}
        hist_list = list(self.historico)
        janela = hist_list[-self.janela_recencia:] if len(hist_list) >= self.janela_recencia else hist_list
        contagem = Counter(janela)
        max_rec = max(contagem.values()) if contagem else 1
        return {i: contagem.get(i, 0) / max_rec for i in range(37)}
    
    def _calcular_cluster(self):
        if len(self.historico) < 2: return {i: 0.0 for i in range(37)}
        hist_list = list(self.historico)
        cluster_count = Counter()
        for i in range(1, len(hist_list)):
            if hist_list[i] == hist_list[i-1]:
                cluster_count[hist_list[i]] += 1
        max_cluster = max(cluster_count.values()) if cluster_count else 1
        return {i: cluster_count.get(i, 0) / max_cluster for i in range(37)}
    
    def _calcular_vizinhanca(self):
        if len(self.historico) < 3: return {i: 0.0 for i in range(37)}
        hist_list = list(self.historico)
        janela = hist_list[-self.janela_vizinhanca:] if len(hist_list) >= self.janela_vizinhanca else hist_list
        neighbor_score = {i: 0.0 for i in range(37)}
        for num in janela:
            vizinhos = self.roleta.get_vizinhos_fisicos(num, raio=2)
            for v in vizinhos:
                neighbor_score[v] += 1
        max_score = max(neighbor_score.values()) if neighbor_score else 1
        return {i: neighbor_score[i] / max_score for i in range(37)}
    
    def _calcular_delay(self):
        if len(self.historico) == 0: return {i: 1.0 for i in range(37)}
        hist_list = list(self.historico)
        delay_score = {}
        for n in range(37):
            if n in hist_list:
                ultima_pos = max(i for i, x in enumerate(hist_list) if x == n)
                delay = len(hist_list) - 1 - ultima_pos
            else:
                delay = len(hist_list)
            delay_score[n] = 1.0 / (delay + 1)
        return delay_score
    
    def _calcular_lucky(self):
        if len(self.lucky_tracking) == 0: return {i: 0.0 for i in range(37)}
        contagem = Counter(self.lucky_tracking)
        max_lucky = max(contagem.values()) if contagem else 1
        return {i: contagem.get(i, 0) / max_lucky for i in range(37)}
    
    def calcular_score_total(self):
        freq = self._calcular_frequencia()
        rec = self._calcular_recencia()
        clust = self._calcular_cluster()
        viz = self._calcular_vizinhanca()
        delay = self._calcular_delay()
        lucky = self._calcular_lucky()
        scores = {}
        detalhes = {}
        for n in range(37):
            score = (freq[n] * self.pesos['frequencia'] + rec[n] * self.pesos['recencia'] +
                     clust[n] * self.pesos['cluster'] + viz[n] * self.pesos['vizinhanca'] +
                     delay[n] * self.pesos['delay'] + lucky[n] * self.pesos['lucky'])
            scores[n] = score
            detalhes[n] = {'freq': freq[n], 'rec': rec[n], 'cluster': clust[n], 'viz': viz[n], 'delay': delay[n], 'lucky': lucky[n], 'total': score}
        return scores, detalhes
    
    def analisar_score(self):
        if len(self.historico) < 5: return None
        scores, detalhes = self.calcular_score_total()
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_numeros = [num for num, score in ranking[:self.top_k]]
        numeros_originais_qtd = len(top_numeros)
        if len(top_numeros) > 15:
            top_numeros = self.sistema_selecao.selecionar_melhores_15_numeros(top_numeros, self.historico, "ScoreEngine")
        score_top3 = sum(scores[n] for n in top_numeros[:3]) / 3
        confianca = self._calcular_nivel_confianca(score_top3)
        top3_scores = [(n, scores[n]) for n in top_numeros[:3]]
        top3_str = ", ".join([f"{n}({s:.2f})" for n, s in top3_scores])
        gatilho = f"🧠 Score Engine | Top 3: {top3_str} | Confiança: {confianca}"
        lucky_recentes = set(self.lucky_tracking)
        lucky_no_top = [n for n in top_numeros if n in lucky_recentes]
        if lucky_no_top: gatilho += f" | 🍀 Lucky: {lucky_no_top[:3]}"
        return {'nome': 'Score Engine Pro', 'numeros_apostar': top_numeros, 'gatilho': gatilho, 'confianca': confianca,
                'tipo': 'score_engine', 'selecao_inteligente': len(top_numeros) < self.top_k,
                'numeros_originais_qtd': numeros_originais_qtd, 'scores_detalhados': {n: detalhes[n] for n in top_numeros},
                'ranking_completo': ranking[:20]}
    
    def _calcular_nivel_confianca(self, score_medio):
        if score_medio >= 0.7: return 'Muito Alta'
        elif score_medio >= 0.5: return 'Alta'
        elif score_medio >= 0.35: return 'Média'
        elif score_medio >= 0.2: return 'Baixa'
        else: return 'Muito Baixa'
    
    def get_analise_score(self):
        if len(self.historico) < 5: return "🧠 Score Engine: Aguardando mais dados (mínimo 5 números)"
        scores, detalhes = self.calcular_score_total()
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:15]
        analise = "🧠 ANÁLISE SCORE ENGINE PRO\n" + "=" * 45 + "\n"
        analise += f"📊 Histórico: {len(self.historico)} números\n"
        analise += f"🍀 Lucky Numbers tracking: {len(self.lucky_tracking)} registros\n"
        analise += f"🎯 Pesos: F:{self.pesos['frequencia']:.0%} R:{self.pesos['recencia']:.0%} C:{self.pesos['cluster']:.0%} V:{self.pesos['vizinhanca']:.0%} D:{self.pesos['delay']:.0%} L:{self.pesos['lucky']:.0%}\n"
        analise += "=" * 45 + "\n🏆 TOP 15 SCORES:\n"
        for i, (num, score) in enumerate(ranking, 1):
            det = detalhes[num]
            barra = "█" * int(score * 20)
            analise += f"{i:2d}. {num:2d}: {barra} {score:.3f} (F:{det['freq']:.2f} R:{det['rec']:.2f} C:{det['cluster']:.2f} V:{det['viz']:.2f} D:{det['delay']:.2f} L:{det['lucky']:.2f})\n"
        if self.lucky_tracking:
            analise += f"\n🍀 Últimos Lucky Numbers: {list(self.lucky_tracking)[-10:]}\n"
        if len(self.historico) >= 2 and self.historico[-1] == self.historico[-2]:
            analise += f"\n🔥 CLUSTER ATIVO: Número {self.historico[-1]} repetiu!\n"
        return analise
    
    def zerar_estatisticas(self):
        self.historico.clear()
        self.lucky_tracking.clear()
        logging.info("🧠 Estatísticas do Score Engine zeradas")

# ===== ESTRATÉGIA MARKOV =====
class EstrategiaMarkov:
    def __init__(self, ordem: int = 2, top_k: int = 6):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=200)
        self.nome = "Cadeia de Markov"
        self.ordem = ordem
        self.top_k = top_k
        self.matriz_transicao = {}
        self.contador_sorteios = 0
        self.sistema_selecao = SistemaSelecaoInteligente()
        self._inicializar_matriz()
        
    def _inicializar_matriz(self):
        self.matriz_transicao = {}
        if self.ordem == 1:
            for i in range(37):
                self.matriz_transicao[i] = {j: 0 for j in range(37)}
        else:
            for i in range(37):
                for j in range(37):
                    self.matriz_transicao[(i, j)] = {k: 0 for k in range(37)}
    
    def adicionar_numero(self, numero):
        self.historico.append(numero)
        self.contador_sorteios += 1
        self._atualizar_matriz_transicao()
        if self.contador_sorteios >= 50:
            self.contador_sorteios = 0
            self._normalizar_matriz()
        if 'sistema' in st.session_state:
            salvar_sessao()
    
    def _atualizar_matriz_transicao(self):
        if len(self.historico) < self.ordem + 1: return
        hist_list = list(self.historico)
        if self.ordem == 1:
            for i in range(len(hist_list) - 1):
                estado_atual = hist_list[i]
                proximo_estado = hist_list[i + 1]
                if estado_atual in self.matriz_transicao and proximo_estado in self.matriz_transicao[estado_atual]:
                    self.matriz_transicao[estado_atual][proximo_estado] += 1
        else:
            for i in range(len(hist_list) - 2):
                estado_atual = (hist_list[i], hist_list[i + 1])
                proximo_estado = hist_list[i + 2]
                if estado_atual in self.matriz_transicao and proximo_estado in self.matriz_transicao[estado_atual]:
                    self.matriz_transicao[estado_atual][proximo_estado] += 1
    
    def _normalizar_matriz(self):
        for estado in self.matriz_transicao:
            total = sum(self.matriz_transicao[estado].values())
            if total > 0:
                for prox in self.matriz_transicao[estado]:
                    self.matriz_transicao[estado][prox] /= total
    
    def _obter_estado_atual(self):
        if len(self.historico) < self.ordem: return None
        hist_list = list(self.historico)
        return hist_list[-1] if self.ordem == 1 else (hist_list[-2], hist_list[-1])
    
    def _prever_proximos_numeros(self):
        estado_atual = self._obter_estado_atual()
        if estado_atual is None or estado_atual not in self.matriz_transicao:
            return []
        probs = self.matriz_transicao[estado_atual]
        previsoes = [(num, prob) for num, prob in probs.items() if prob > 0]
        previsoes.sort(key=lambda x: x[1], reverse=True)
        return previsoes[:self.top_k]
    
    def _ajustar_com_vizinhanca(self, previsoes):
        if not previsoes: return previsoes
        scores = {num: prob for num, prob in previsoes}
        for num in list(scores.keys())[:3]:
            vizinhos = self.roleta.get_vizinhos_fisicos(num, raio=2)
            for v in vizinhos:
                scores[v] = scores.get(v, 0) + scores[num] * 0.3
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:self.top_k]
    
    def analisar_markov(self):
        if len(self.historico) < self.ordem + 5: return None
        previsoes = self._prever_proximos_numeros()
        if not previsoes:
            return self._fallback_frequencia()
        previsoes_ajustadas = self._ajustar_com_vizinhanca(previsoes)
        numeros_previstos = [num for num, prob in previsoes_ajustadas]
        numeros_originais_qtd = len(numeros_previstos)
        if len(numeros_previstos) > 15:
            numeros_previstos = self.sistema_selecao.selecionar_melhores_15_numeros(numeros_previstos, self.historico, "Markov")
        confianca_val = sum(prob for _, prob in previsoes_ajustadas[:3])
        confianca = self._calcular_nivel_confianca(confianca_val)
        estado_atual = self._obter_estado_atual()
        gatilho = self._gerar_gatilho(estado_atual, previsoes_ajustadas)
        return {'nome': f'Cadeia de Markov (Ordem {self.ordem})', 'numeros_apostar': numeros_previstos, 'gatilho': gatilho,
                'confianca': confianca, 'tipo': 'markov', 'selecao_inteligente': len(numeros_previstos) < numeros_originais_qtd,
                'numeros_originais_qtd': numeros_originais_qtd, 'previsoes_detalhadas': previsoes_ajustadas, 'estado_atual': estado_atual}
    
    def _fallback_frequencia(self):
        if len(self.historico) < 10: return None
        contagem = Counter(list(self.historico)[-30:])
        numeros = [num for num, _ in contagem.most_common(self.top_k)]
        return {'nome': 'Cadeia de Markov (Fallback)', 'numeros_apostar': numeros,
                'gatilho': 'Fallback: Frequência últimos 30', 'confianca': 'Baixa', 'tipo': 'markov_fallback'}
    
    def _calcular_nivel_confianca(self, val):
        if val >= 0.6: return 'Muito Alta'
        elif val >= 0.45: return 'Alta'
        elif val >= 0.3: return 'Média'
        elif val >= 0.15: return 'Baixa'
        else: return 'Muito Baixa'
    
    def _gerar_gatilho(self, estado_atual, previsoes):
        if estado_atual is None: return "Aguardando dados..."
        if self.ordem == 1: estado_str = f"Último: {estado_atual}"
        else: estado_str = f"Últimos: {estado_atual[0]}→{estado_atual[1]}"
        top3 = ", ".join([f"{n}({p:.1%})" for n, p in previsoes[:3]])
        return f"🎲 Markov (ordem {self.ordem}) | {estado_str} | Top3: {top3}"
    
    def get_analise_markov(self):
        if len(self.historico) < self.ordem + 2:
            return f"🎲 Markov: Aguardando mais dados (mínimo {self.ordem + 2})"
        analise = f"🎲 ANÁLISE MARKOV (Ordem {self.ordem})\n" + "="*45 + "\n"
        analise += f"📊 Histórico: {len(self.historico)} números\n🎯 Top {self.top_k} previsões\n"
        estado = self._obter_estado_atual()
        if estado:
            analise += f"🔍 Estado: {estado}\n"
            previsoes = self._prever_proximos_numeros()
            if previsoes:
                analise += "\n📈 PROBABILIDADES:\n"
                for i, (n, p) in enumerate(previsoes[:self.top_k], 1):
                    analise += f"  {i}. {n:2d}: {'█'*int(p*20)} {p:.1%}\n"
        return analise
    
    def get_estatisticas_matriz(self):
        if not self.matriz_transicao: return "Matriz vazia"
        total_estados = len(self.matriz_transicao)
        com_dados = sum(1 for e in self.matriz_transicao if sum(self.matriz_transicao[e].values()) > 0)
        return f"📊 MATRIZ MARKOV\n🎲 Ordem: {self.ordem}\n📈 Estados: {total_estados}\n✅ Com dados: {com_dados}\n📊 Cobertura: {(com_dados/total_estados)*100:.1f}%"
    
    def zerar_matriz(self):
        self.historico.clear()
        self._inicializar_matriz()
        self.contador_sorteios = 0
        logging.info("🔄 Matriz Markov zerada")

# ===== ESTRATÉGIA ZONAS =====
class EstrategiaZonasOtimizada:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=70)
        self.nome = "Zonas Ondas v9"
        self.zonas = {'Vermelha': 7, 'Azul': 10, 'Amarela': 2}
        self.quantidade_zonas = {'Vermelha': 6, 'Azul': 6, 'Amarela': 6}
        self.combinacoes_possiveis = ["Vermelha+Azul", "Vermelha+Amarela", "Azul+Amarela"]
        self.indice_combinacao_atual = 0
        self.combinacao_atual = self.combinacoes_possiveis[0]
        self.ultima_combinacao_erro = ""
        self.stats_zonas = {z: {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0} for z in self.zonas}
        self.numeros_zonas = {n: self.roleta.get_vizinhos_zona(c, q) for n, c in self.zonas.items() for q in [self.quantidade_zonas[n]]}
        self.janelas_analise = {'curto_prazo': 12, 'medio_prazo': 24, 'longo_prazo': 48, 'performance': 100}
        self.sistema_selecao = SistemaSelecaoInteligente()
        self.combinacoes_stats = {}
        self.janela_dinamica = 50
        for comb in self.combinacoes_possiveis:
            self.combinacoes_stats[comb] = {'acertos': 0, 'tentativas': 0, 'ultimo_uso': 0, 'sequencia_atual': 0,
                                            'melhor_taxa': 0, 'historico_recente': deque(maxlen=self.janela_dinamica)}

    def adicionar_numero(self, numero):
        self.historico.append(numero)
        self.atualizar_stats(numero)
        if 'sistema' in st.session_state: salvar_sessao()

    def atualizar_stats(self, ultimo):
        for zona, nums in self.numeros_zonas.items():
            if ultimo in nums:
                self.stats_zonas[zona]['acertos'] += 1
                self.stats_zonas[zona]['sequencia_atual'] += 1
                if self.stats_zonas[zona]['sequencia_atual'] > self.stats_zonas[zona]['sequencia_maxima']:
                    self.stats_zonas[zona]['sequencia_maxima'] = self.stats_zonas[zona]['sequencia_atual']
            else:
                self.stats_zonas[zona]['sequencia_atual'] = 0
            self.stats_zonas[zona]['tentativas'] += 1
            if self.stats_zonas[zona]['tentativas'] > 0:
                self.stats_zonas[zona]['performance_media'] = self.stats_zonas[zona]['acertos'] / self.stats_zonas[zona]['tentativas'] * 100

    def atualizar_combinacoes_stats(self, comb_usada, acertou):
        if comb_usada in self.combinacoes_stats:
            self.combinacoes_stats[comb_usada]['tentativas'] += 1
            self.combinacoes_stats[comb_usada]['historico_recente'].append(1 if acertou else 0)
            if acertou:
                self.combinacoes_stats[comb_usada]['acertos'] += 1
                self.combinacoes_stats[comb_usada]['sequencia_atual'] += 1
                self.ultima_combinacao_erro = ""
            else:
                self.combinacoes_stats[comb_usada]['sequencia_atual'] = 0
                self.ultima_combinacao_erro = comb_usada
                self.proxima_combinacao()
            hist = list(self.combinacoes_stats[comb_usada]['historico_recente'])
            if hist:
                taxa = sum(hist) / len(hist) * 100
                if taxa > self.combinacoes_stats[comb_usada]['melhor_taxa']:
                    self.combinacoes_stats[comb_usada]['melhor_taxa'] = taxa

    def proxima_combinacao(self):
        antiga = self.combinacao_atual
        self.indice_combinacao_atual = (self.indice_combinacao_atual + 1) % len(self.combinacoes_possiveis)
        self.combinacao_atual = self.combinacoes_possiveis[self.indice_combinacao_atual]
        enviar_troca_combinacao_zonas(antiga, self.combinacao_atual)
        return self.combinacao_atual

    def get_melhor_combinacao(self):
        return self.combinacao_atual if len(self.historico) >= 20 else None

    def get_zona_mais_quente(self):
        if len(self.historico) < 15: return None
        scores = {}
        ult_curto = list(self.historico)[-self.janelas_analise['curto_prazo']:]
        for z in self.zonas:
            freq = sum(1 for n in ult_curto if n in self.numeros_zonas[z])
            perc = freq / len(ult_curto) * 100
            score = perc * 0.6 + self.stats_zonas[z]['sequencia_atual'] * 8
            scores[z] = score
        vencedora = max(scores, key=scores.get) if scores else None
        if vencedora:
            freq_check = sum(1 for n in ult_curto[-12:] if n in self.numeros_zonas[vencedora])
            if freq_check >= 2: return vencedora
        return None

    def analisar_zonas(self):
        if len(self.historico) < 15: return None
        comb = self.get_melhor_combinacao()
        if comb:
            zonas = comb.split('+')
            nums = list(set(self.numeros_zonas[zonas[0]] + self.numeros_zonas[zonas[1]]))
            if len(nums) > 15: nums = self.sistema_selecao.selecionar_melhores_15_numeros(nums, self.historico, "Zonas")
            conf1 = self.calcular_confianca_onda(zonas[0])
            conf2 = self.calcular_confianca_onda(zonas[1])
            return {'nome': f'Zonas Duplas - {comb}', 'numeros_apostar': nums, 'gatilho': f'🌊 ONDA: {comb}',
                    'confianca': f'{conf1}+{conf2}', 'zonas_envolvidas': zonas, 'tipo': 'dupla', 'combinacao_usada': comb}
        zona = self.get_zona_mais_quente()
        if not zona: return None
        nums = self.numeros_zonas[zona]
        if len(nums) > 15: nums = self.sistema_selecao.selecionar_melhores_15_numeros(nums, self.historico, "Zonas")
        return {'nome': f'Zona {zona}', 'numeros_apostar': nums, 'gatilho': f'🌊 ONDA SIMPLES: {zona}',
                'confianca': self.calcular_confianca_onda(zona), 'zona': zona, 'tipo': 'unica', 'combinacao_usada': zona}

    def calcular_confianca_onda(self, zona):
        if len(self.historico) < 10: return 'Baixa'
        ult_12 = list(self.historico)[-12:]
        freq = sum(1 for n in ult_12 if n in self.numeros_zonas[zona])
        perc = freq / len(ult_12) * 100
        seq = self.stats_zonas[zona]['sequencia_atual']
        if perc >= 50 and seq >= 2: return 'Excelente'
        elif perc >= 40: return 'Muito Alta'
        elif perc >= 30: return 'Alta'
        elif perc >= 20: return 'Média'
        else: return 'Baixa'

    def get_analise_detalhada(self):
        if not self.historico: return "Aguardando dados..."
        analise = "🎯 ANÁLISE ZONAS v9\n" + "="*45 + "\n"
        ult_12 = list(self.historico)[-12:]
        for z in self.zonas:
            freq = sum(1 for n in ult_12 if n in self.numeros_zonas[z])
            perc = freq / len(ult_12) * 100
            seq = self.stats_zonas[z]['sequencia_atual']
            analise += f"📍 {z}: {freq}/{len(ult_12)} ({perc:.1f}%)"
            if seq >= 2: analise += f" 🔥 Seq:{seq}"
            analise += "\n"
        analise += f"\n🔄 Combinação atual: {self.combinacao_atual}\n"
        return analise

    def zerar_estatisticas(self):
        for z in self.stats_zonas:
            self.stats_zonas[z] = {'acertos': 0, 'tentativas': 0, 'sequencia_atual': 0, 'sequencia_maxima': 0, 'performance_media': 0}
        for c in self.combinacoes_stats:
            self.combinacoes_stats[c] = {'acertos': 0, 'tentativas': 0, 'ultimo_uso': 0, 'sequencia_atual': 0, 'melhor_taxa': 0, 'historico_recente': deque(maxlen=self.janela_dinamica)}
        self.indice_combinacao_atual = 0
        self.combinacao_atual = self.combinacoes_possiveis[0]
        self.ultima_combinacao_erro = ""

# ===== ESTRATÉGIA MIDAS =====
class EstrategiaMidas:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=15)
        self.terminais = {'0': [0,10,20,30], '7': [7,17,27], '5': [5,15,25,35]}
    def adicionar_numero(self, numero):
        self.historico.append(numero)
        if 'sistema' in st.session_state: salvar_sessao()
    def analisar_midas(self):
        if len(self.historico) < 5: return None
        ult = self.historico[-1]
        rec = list(self.historico)[-5:]
        if ult in [0,10,20,30] and any(n in [0,10,20,30] for n in rec):
            return {'nome': 'Padrão do Zero', 'numeros_apostar': [0,10,20,30], 'gatilho': 'Terminal 0', 'confianca': 'Média'}
        if ult in [7,17,27] and any(n in [7,17,27] for n in rec):
            return {'nome': 'Padrão do Sete', 'numeros_apostar': [7,17,27], 'gatilho': 'Terminal 7', 'confianca': 'Média'}
        if ult in [5,15,25,35] and any(n in [5,15,25,35] for n in rec):
            return {'nome': 'Padrão do Cinco', 'numeros_apostar': [5,15,25,35], 'gatilho': 'Terminal 5', 'confianca': 'Média'}
        return None

# ===== ESTRATÉGIA ML (simplificada) =====
class MLRoletaOtimizada:
    def __init__(self, roleta_obj, min_training_samples=200, max_history=1000, retrain_every_n=15, seed=42):
        self.roleta = roleta_obj
        self.min_training_samples = min_training_samples
        self.max_history = max_history
        self.retrain_every_n = retrain_every_n
        self.seed = seed
        self.models = []
        self.scaler = StandardScaler()
        self.is_trained = False
        self.contador_treinamento = 0
        self.meta = {}
        self.window_for_features = [3,8,15,30,60,120]
        self.numeros = list(range(37))
        self.k_vizinhos = 2

    def get_neighbors(self, numero, k=None):
        if k is None: k = self.k_vizinhos
        try:
            race = self.roleta.race
            idx = race.index(numero)
            return [race[(idx + off) % 37] for off in range(-k, k+1)]
        except: return [numero]

    def extrair_features(self, historico, numero_alvo=None):
        hist = list(historico)
        N = len(hist)
        if N < 10: return None, None
        return [], []

    def preparar_dados_treinamento(self, historico):
        return np.array([]), np.array([])

    def treinar_modelo(self, historico, force_retrain=False, balance=True):
        return False, "Não treinado"

    def carregar_modelo(self):
        return False

    def prever_proximo_numero(self, historico, top_k=25):
        return None, "Modelo não treinado"

class EstrategiaML:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.ml = MLRoletaOtimizada(self.roleta)
        self.historico = deque(maxlen=30)
        self.contador_sorteios = 0
        self.zonas_ml = {'Vermelha': 7, 'Azul': 10, 'Amarela': 2}
        self.numeros_zonas_ml = {z: self.roleta.get_vizinhos_zona(c, 6) for z, c in self.zonas_ml.items()}
        self.sequencias_padroes = {'sequencias_ativas': {}, 'historico_sequencias': [], 'padroes_detectados': []}
        self.sistema_selecao = SistemaSelecaoInteligente()
        self.ml.carregar_modelo()

    def adicionar_numero(self, numero):
        self.historico.append(numero)
        self.contador_sorteios += 1
        if self.contador_sorteios >= 15:
            self.contador_sorteios = 0
        if 'sistema' in st.session_state: salvar_sessao()

    def analisar_ml(self):
        if len(self.historico) < 10 or not self.ml.is_trained: return None
        return None

    def treinar_modelo_ml(self, historico=None):
        return False, "Não treinado"

    def get_analise_ml(self):
        return "🤖 ML: Modelo não treinado"

# ===== SISTEMA PRINCIPAL =====
class SistemaRoletaCompleto:
    def __init__(self):
        self.estrategia_zonas = EstrategiaZonasOtimizada()
        self.estrategia_midas = EstrategiaMidas()
        self.estrategia_ml = EstrategiaML()
        self.estrategia_markov = EstrategiaMarkov(ordem=2, top_k=6)
        self.estrategia_score = EstrategiaScoreEngine(top_k=12)
        self.estrategia_hedge = EstrategiaHedgeFund(top_k=8)
        self.estrategia_terminalum = EstrategiaTerminalUm()  # NOVA ESTRATÉGIA
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.estrategia_selecionada = "TerminalUm"  # Default para a nova estratégia
        self.contador_sorteios_global = 0
        self.sequencia_erros = 0
        self.ultima_estrategia_erro = ""

    def set_estrategia(self, estrategia):
        self.estrategia_selecionada = estrategia
        salvar_sessao()

    def treinar_modelo_ml(self, historico=None):
        return self.estrategia_ml.treinar_modelo_ml(historico)

    def rotacionar_estrategia_automaticamente(self, acerto, nome_estrategia):
        if acerto:
            self.sequencia_erros = 0
            self.ultima_estrategia_erro = ""
            return False
        else:
            self.sequencia_erros += 1
            self.ultima_estrategia_erro = nome_estrategia
            if self.sequencia_erros >= 2:
                atual = self.estrategia_selecionada
                # Ordem de rotação incluindo TerminalUm
                ordem = ["TerminalUm", "Zonas", "ML", "Markov", "ScoreEngine", "HedgeFund"]
                try:
                    idx = ordem.index(atual)
                    nova = ordem[(idx + 1) % len(ordem)]
                except ValueError:
                    nova = "TerminalUm"
                self.estrategia_selecionada = nova
                self.sequencia_erros = 0
                enviar_rotacao_automatica(atual, nova, f"2 erros consecutivos em {atual}")
                return True
            return False

    def processar_novo_numero(self, numero):
        if isinstance(numero, dict):
            numero_real = numero['number']
            lucky = numero.get('luckyNumbers', [])
            mult = numero.get('luckyMultipliers', {}).get(numero_real) if numero_real in lucky else None
        else:
            numero_real = numero
            lucky = []
            mult = None

        self.contador_sorteios_global += 1

        if self.previsao_ativa:
            acerto = numero_real in self.previsao_ativa.get('numeros_apostar', [])
            zonas_acertadas = []
            nome = self.previsao_ativa['nome']

            if acerto:
                if 'Zonas' in nome:
                    for z, nums in self.estrategia_zonas.numeros_zonas.items():
                        if numero_real in nums: zonas_acertadas.append(z)
                elif 'ML' in nome:
                    for z, nums in self.estrategia_ml.numeros_zonas_ml.items():
                        if numero_real in nums: zonas_acertadas.append(z)

            if 'Zonas' in nome and 'combinacao_usada' in self.previsao_ativa:
                self.estrategia_zonas.atualizar_combinacoes_stats(self.previsao_ativa['combinacao_usada'], acerto)

            rotacionou = self.rotacionar_estrategia_automaticamente(acerto, nome)

            if nome not in self.estrategias_contador:
                self.estrategias_contador[nome] = {'acertos': 0, 'total': 0}
            self.estrategias_contador[nome]['total'] += 1
            if acerto:
                self.estrategias_contador[nome]['acertos'] += 1
                self.acertos += 1
            else:
                self.erros += 1

            zona_str = "+".join(zonas_acertadas) if zonas_acertadas else None
            enviar_resultado_super_simplificado(numero_real, acerto, nome, zona_str, mult)

            self.historico_desempenho.append({
                'numero': numero_real, 'acerto': acerto, 'estrategia': nome,
                'previsao': self.previsao_ativa.get('numeros_apostar', []),
                'rotacionou': rotacionou, 'zona_acertada': zona_str,
                'tipo_aposta': self.previsao_ativa.get('tipo', 'unica'),
                'multiplicador': mult
            })
            self.previsao_ativa = None

        # Adiciona número a TODAS as estratégias
        self.estrategia_zonas.adicionar_numero(numero_real)
        self.estrategia_midas.adicionar_numero(numero_real)
        self.estrategia_ml.adicionar_numero(numero_real)
        self.estrategia_markov.adicionar_numero(numero_real)
        self.estrategia_score.adicionar_numero(numero_real, lucky)
        self.estrategia_hedge.adicionar_numero(numero_real, lucky)
        self.estrategia_terminalum.adicionar_numero(numero_real)  # NOVA ESTRATÉGIA

        nova = None
        if self.estrategia_selecionada == "Zonas":
            nova = self.estrategia_zonas.analisar_zonas()
        elif self.estrategia_selecionada == "Midas":
            nova = self.estrategia_midas.analisar_midas()
        elif self.estrategia_selecionada == "ML":
            nova = self.estrategia_ml.analisar_ml()
        elif self.estrategia_selecionada == "Markov":
            nova = self.estrategia_markov.analisar_markov()
        elif self.estrategia_selecionada == "ScoreEngine":
            nova = self.estrategia_score.analisar_score()
        elif self.estrategia_selecionada == "HedgeFund":
            nova = self.estrategia_hedge.analisar()
        elif self.estrategia_selecionada == "TerminalUm":  # NOVA ESTRATÉGIA
            nova = self.estrategia_terminalum.analisar()

        if nova:
            self.previsao_ativa = nova
            enviar_previsao_super_simplificada(nova)

    def zerar_estatisticas_desempenho(self):
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.historico_desempenho = []
        self.contador_sorteios_global = 0
        self.sequencia_erros = 0
        self.ultima_estrategia_erro = ""
        self.estrategia_zonas.zerar_estatisticas()
        self.estrategia_markov.zerar_matriz()
        self.estrategia_score.zerar_estatisticas()
        self.estrategia_hedge.zerar_estatisticas()
        self.estrategia_terminalum.zerar_estatisticas()  # NOVA ESTRATÉGIA
        salvar_sessao()

    def reset_recente_estatisticas(self):
        if len(self.historico_desempenho) > 10:
            self.historico_desempenho = self.historico_desempenho[-10:]
            self.acertos = sum(1 for r in self.historico_desempenho if r['acerto'])
            self.erros = len(self.historico_desempenho) - self.acertos
            self.estrategias_contador = {}
            for r in self.historico_desempenho:
                e = r['estrategia']
                if e not in self.estrategias_contador:
                    self.estrategias_contador[e] = {'acertos': 0, 'total': 0}
                self.estrategias_contador[e]['total'] += 1
                if r['acerto']: self.estrategias_contador[e]['acertos'] += 1
            self.sequencia_erros = 0
            for r in reversed(self.historico_desempenho[-5:]):
                if not r['acerto']: self.sequencia_erros += 1
                else: break
        salvar_sessao()

    def get_status_rotacao(self):
        return {
            'estrategia_atual': self.estrategia_selecionada,
            'sequencia_erros': self.sequencia_erros,
            'ultima_estrategia_erro': self.ultima_estrategia_erro,
            'proxima_rotacao_em': max(0, 2 - self.sequencia_erros)
        }

# ===== FUNÇÕES AUXILIARES =====
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
                    if m is not None: multiplicadores[n] = m
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

# ===== APLICAÇÃO STREAMLIT =====
st.set_page_config(page_title="IA Roleta — Terminal Um Pro", layout="centered")
st.title("🎯 IA Roleta — Sistema Multi-Estratégias PRO")

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

with st.sidebar.expander("💾 Gerenciamento de Sessão", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Salvar Sessão", use_container_width=True):
            salvar_sessao()
            st.success("✅ Sessão salva!")
    with col2:
        if st.button("🔄 Carregar Sessão", use_container_width=True):
            if carregar_sessao():
                st.success("✅ Sessão carregada!")
                st.rerun()
            else:
                st.error("❌ Nenhuma sessão salva")
    col3, col4 = st.columns(2)
    with col3:
        if st.button("🔄 Reset Recente", use_container_width=True):
            st.session_state.sistema.reset_recente_estatisticas()
            st.success("✅ Reset recente!")
            st.rerun()
    with col4:
        if st.button("🗑️ Zerar Tudo", type="secondary", use_container_width=True):
            if st.checkbox("Confirmar"):
                st.session_state.sistema.zerar_estatisticas_desempenho()
                st.error("🗑️ Zerado!")
                st.rerun()
    if st.button("🗑️ Limpar TODOS os Dados", type="secondary", use_container_width=True):
        if st.checkbox("Confirmar limpeza total"):
            limpar_sessao()
            st.stop()

with st.sidebar.expander("🔔 Telegram", expanded=False):
    token = st.text_input("Token:", value=st.session_state.telegram_token, type="password")
    chat = st.text_input("Chat ID:", value=st.session_state.telegram_chat_id)
    if st.button("Salvar Telegram"):
        st.session_state.telegram_token = token
        st.session_state.telegram_chat_id = chat
        salvar_sessao()
        st.success("✅ Salvo!")

estrategia = st.sidebar.selectbox(
    "🎯 Estratégia:",
    ["TerminalUm", "Zonas", "Midas", "ML", "Markov", "ScoreEngine", "HedgeFund"],  # TerminalUm adicionado
    key="estrategia_selecionada"
)
if estrategia != st.session_state.sistema.estrategia_selecionada:
    st.session_state.sistema.set_estrategia(estrategia)

with st.sidebar.expander("🔄 Rotação Automática", expanded=True):
    status = st.session_state.sistema.get_status_rotacao()
    st.write(f"🎯 **Atual:** {status['estrategia_atual']}")
    st.write(f"❌ **Erros:** {status['sequencia_erros']}/2")
    st.write(f"🔄 **Próx. rot. em:** {status['proxima_rotacao_em']} erro(s)")
    st.write("**Ordem:** TerminalUm → Zonas → ML → Markov → ScoreEngine → HedgeFund → TerminalUm")
    if st.button("🔄 Forçar Rotação", use_container_width=True):
        atual = st.session_state.sistema.estrategia_selecionada
        ordem = ["TerminalUm", "Zonas", "ML", "Markov", "ScoreEngine", "HedgeFund"]
        try:
            idx = ordem.index(atual)
            nova = ordem[(idx + 1) % len(ordem)]
        except ValueError:
            nova = "TerminalUm"
        st.session_state.sistema.estrategia_selecionada = nova
        st.session_state.sistema.sequencia_erros = 0
        st.success(f"🔄 {atual} → {nova}")
        st.rerun()

with st.sidebar.expander("🎯 Terminal Um Config", expanded=False):
    st.write("**Estratégia Terminal Um**")
    st.write("- Analisa 14 sorteios sem Terminal 1")
    st.write("- Gatilho no 15º com número específico")
    st.write("- Aposta: Terminal 1 + Terminal 2 + Vizinhos")
    st.write(f"**Terminal 1:** 1, 11, 21, 31")
    st.write(f"**Terminal 2:** 2, 12, 22, 32")
    st.write(f"**Gatilhos:** 4, 0, 10, 27, 9, 14, 25, 19, 1, 2, 32, 16")
    if st.button("🧹 Zerar Terminal Um", use_container_width=True):
        st.session_state.sistema.estrategia_terminalum.zerar_estatisticas()
        st.success("✅ Zerado!")

with st.sidebar.expander("🏦 Hedge Fund Config", expanded=False):
    st.write("**Filtro de Entrada**")
    st.write("Só gera sinal quando:")
    st.write("- Estado ≠ RANDOM")
    st.write("- Entropia < 0.45")
    st.write("- Score máximo > 0.4")
    if st.button("🧹 Zerar Hedge Fund", use_container_width=True):
        st.session_state.sistema.estrategia_hedge.zerar_estatisticas()
        st.success("✅ Zerado!")

with st.sidebar.expander(f"🔍 Análise - {estrategia}", expanded=False):
    if estrategia == "Zonas":
        analise = st.session_state.sistema.estrategia_zonas.get_analise_detalhada()
    elif estrategia == "ML":
        analise = st.session_state.sistema.estrategia_ml.get_analise_ml()
    elif estrategia == "Markov":
        analise = st.session_state.sistema.estrategia_markov.get_analise_markov()
    elif estrategia == "ScoreEngine":
        analise = st.session_state.sistema.estrategia_score.get_analise_score()
    elif estrategia == "HedgeFund":
        analise = st.session_state.sistema.estrategia_hedge.get_analise()
    elif estrategia == "TerminalUm":
        analise = st.session_state.sistema.estrategia_terminalum.get_analise()
    else:
        analise = "Estratégia Midas ativa"
    st.text(analise)

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

status = st.session_state.sistema.get_status_rotacao()
col1, col2, col3 = st.columns(3)
col1.metric("🎯 Estratégia", status['estrategia_atual'])
col2.metric("❌ Erros", f"{status['sequencia_erros']}/2")
col3.metric("🔄 Próx. Rotação", f"Em {status['proxima_rotacao_em']} erro(s)")

st.subheader("🎯 Previsão Ativa")
sistema = st.session_state.sistema

if sistema.previsao_ativa:
    p = sistema.previsao_ativa
    st.success(f"**{p['nome']}**")
    if p.get('selecao_inteligente'):
        st.info("🎯 Seleção Inteligente ativa")
    if 'Hedge Fund' in p['nome']:
        st.info(f"🏦 **Estado:** {p.get('estado', 'N/A')} | **Entropia:** {p.get('entropia', 0):.3f}")
    if 'Terminal Um' in p['nome']:
        st.info(f"🎯 **Gatilho:** {p.get('numero_gatilho')} | **Terminais ausentes:** {p.get('terminais_ausentes')}")
    st.write(f"**🔢 Números ({len(p['numeros_apostar'])}):**")
    st.write(", ".join(map(str, sorted(p['numeros_apostar']))))
else:
    if sistema.estrategia_selecionada == "HedgeFund":
        st.info("🏦 **Hedge Fund Pro:** Aguardando momento oportuno (baixa entropia / sinal forte)...")
    elif sistema.estrategia_selecionada == "TerminalUm":
        st.info("🎯 **Terminal Um:** Aguardando 14 sorteios sem Terminal 1 + gatilho específico...")
    else:
        st.info(f"🎲 Analisando padrões ({estrategia})...")

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
    st.write("**🔍 Últimas 5 Conferências:**")
    for r in sistema.historico_desempenho[-5:]:
        emoji = "🎉" if r['acerto'] else "❌"
        rot = " 🔄" if r.get('rotacionou') else ""
        mult = f" ⚡{r['multiplicador']}x" if r.get('multiplicador') and r['acerto'] else ""
        zona = ""
        if r['acerto'] and r.get('zona_acertada'):
            zona = f" (Núcleo {r['zona_acertada']})"
        st.write(f"{emoji}{rot} {r['estrategia']}: {r['numero']}{mult}{zona}")

if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        st.download_button("📥 Baixar histórico", data=f.read(), file_name="historico_roleta.json")

salvar_sessao()
