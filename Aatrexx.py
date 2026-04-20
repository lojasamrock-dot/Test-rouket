import streamlit as st
import json
import os
import requests
import logging
import numpy as np
import pandas as pd
from collections import Counter, deque
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
            # NOVA ESTRATÉGIA SCORE ENGINE
            'score_engine_historico': list(st.session_state.sistema.estrategia_score.historico) if hasattr(st.session_state.sistema, 'estrategia_score') else [],
            'score_engine_lucky_tracking': st.session_state.sistema.estrategia_score.lucky_tracking if hasattr(st.session_state.sistema, 'estrategia_score') else []
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
                
                # Carregar dados da estratégia Markov
                markov_historico = session_data.get('markov_historico', [])
                if hasattr(st.session_state.sistema, 'estrategia_markov'):
                    st.session_state.sistema.estrategia_markov.historico = deque(markov_historico, maxlen=200)
                    st.session_state.sistema.estrategia_markov.matriz_transicao = session_data.get('markov_matriz_transicao', {})
                    st.session_state.sistema.estrategia_markov.contador_sorteios = session_data.get('markov_contador_sorteios', 0)
                
                # NOVA ESTRATÉGIA SCORE ENGINE
                score_engine_historico = session_data.get('score_engine_historico', [])
                if hasattr(st.session_state.sistema, 'estrategia_score'):
                    st.session_state.sistema.estrategia_score.historico = deque(score_engine_historico, maxlen=200)
                    st.session_state.sistema.estrategia_score.lucky_tracking = session_data.get('score_engine_lucky_tracking', [])
            
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

# =============================
# NOVA ESTRATÉGIA: SCORE ENGINE PRO
# =============================
class EstrategiaScoreEngine:
    """
    Estratégia baseada em scoring dinâmico combinando:
    - Frequência (peso 25%)
    - Recência (peso 25%)
    - Cluster/Repetição (peso 20%)
    - Vizinhança física (peso 10%)
    - Delay (tempo sem sair) (peso 10%)
    - Lucky Numbers (peso 10%)
    """
    def __init__(self, top_k: int = 12):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=200)  # Armazena números puros
        self.lucky_tracking = deque(maxlen=50)  # Histórico de lucky numbers
        self.nome = "Score Engine Pro"
        self.top_k = top_k
        self.sistema_selecao = SistemaSelecaoInteligente()
        
        # Pesos configuráveis
        self.pesos = {
            'frequencia': 0.25,
            'recencia': 0.25,
            'cluster': 0.20,
            'vizinhanca': 0.10,
            'delay': 0.10,
            'lucky': 0.10
        }
        
        # Janelas de análise
        self.janela_recencia = 20
        self.janela_frequencia = 50
        self.janela_vizinhanca = 30
        
    def adicionar_numero(self, numero, lucky_numbers=None):
        """Adiciona um número ao histórico e registra lucky numbers"""
        self.historico.append(numero)
        if lucky_numbers:
            self.lucky_tracking.extend(lucky_numbers)
        if 'sistema' in st.session_state:
            salvar_sessao()
    
    def _calcular_frequencia(self):
        """Calcula frequência normalizada de cada número (0-1)"""
        if len(self.historico) < 5:
            return {i: 0.0 for i in range(37)}
        
        historico_lista = list(self.historico)
        janela = historico_lista[-self.janela_frequencia:] if len(historico_lista) >= self.janela_frequencia else historico_lista
        contagem = Counter(janela)
        max_freq = max(contagem.values()) if contagem else 1
        
        freq_score = {}
        for i in range(37):
            freq_score[i] = contagem.get(i, 0) / max_freq if max_freq > 0 else 0.0
        return freq_score
    
    def _calcular_recencia(self):
        """Números que apareceram recentemente têm maior score"""
        if len(self.historico) < 5:
            return {i: 0.0 for i in range(37)}
        
        historico_lista = list(self.historico)
        janela = historico_lista[-self.janela_recencia:] if len(historico_lista) >= self.janela_recencia else historico_lista
        contagem = Counter(janela)
        max_rec = max(contagem.values()) if contagem else 1
        
        recencia_score = {}
        for i in range(37):
            recencia_score[i] = contagem.get(i, 0) / max_rec if max_rec > 0 else 0.0
        return recencia_score
    
    def _calcular_cluster(self):
        """Detecta repetições consecutivas (cluster)"""
        if len(self.historico) < 2:
            return {i: 0.0 for i in range(37)}
        
        historico_lista = list(self.historico)
        cluster_count = Counter()
        
        # Conta repetições consecutivas
        for i in range(1, len(historico_lista)):
            if historico_lista[i] == historico_lista[i-1]:
                cluster_count[historico_lista[i]] += 1
        
        # Normaliza
        max_cluster = max(cluster_count.values()) if cluster_count else 1
        cluster_score = {}
        for i in range(37):
            cluster_score[i] = cluster_count.get(i, 0) / max_cluster if max_cluster > 0 else 0.0
        return cluster_score
    
    def _calcular_vizinhanca(self):
        """Números vizinhos aos que saíram recentemente ganham peso"""
        if len(self.historico) < 3:
            return {i: 0.0 for i in range(37)}
        
        historico_lista = list(self.historico)
        janela = historico_lista[-self.janela_vizinhanca:] if len(historico_lista) >= self.janela_vizinhanca else historico_lista
        
        neighbor_score = {i: 0.0 for i in range(37)}
        for num in janela:
            vizinhos = self.roleta.get_vizinhos_fisicos(num, raio=2)
            for v in vizinhos:
                neighbor_score[v] += 1
        
        max_score = max(neighbor_score.values()) if neighbor_score else 1
        for i in range(37):
            neighbor_score[i] = neighbor_score[i] / max_score if max_score > 0 else 0.0
        return neighbor_score
    
    def _calcular_delay(self):
        """Números que não saem há muito tempo (delay alto) recebem score inversamente proporcional"""
        if len(self.historico) == 0:
            return {i: 1.0 for i in range(37)}
        
        historico_lista = list(self.historico)
        delay_score = {}
        
        for n in range(37):
            if n in historico_lista:
                # Posição da última ocorrência
                ultima_pos = max(i for i, x in enumerate(historico_lista) if x == n)
                delay = len(historico_lista) - 1 - ultima_pos
            else:
                delay = len(historico_lista)  # nunca apareceu
        
            # Score inversamente proporcional ao delay (quanto maior delay, menor score)
            # Usamos 1/(delay+1) para normalizar entre 0 e 1
            delay_score[n] = 1.0 / (delay + 1)
        
        return delay_score
    
    def _calcular_lucky(self):
        """Números que aparecem como Lucky Numbers recentemente ganham peso"""
        if len(self.lucky_tracking) == 0:
            return {i: 0.0 for i in range(37)}
        
        lucky_list = list(self.lucky_tracking)
        contagem = Counter(lucky_list)
        max_lucky = max(contagem.values()) if contagem else 1
        
        lucky_score = {}
        for i in range(37):
            lucky_score[i] = contagem.get(i, 0) / max_lucky if max_lucky > 0 else 0.0
        return lucky_score
    
    def calcular_score_total(self):
        """Calcula o score combinado para todos os números"""
        freq = self._calcular_frequencia()
        rec = self._calcular_recencia()
        clust = self._calcular_cluster()
        viz = self._calcular_vizinhanca()
        delay = self._calcular_delay()
        lucky = self._calcular_lucky()
        
        scores = {}
        detalhes = {}
        
        for n in range(37):
            score = (
                freq[n] * self.pesos['frequencia'] +
                rec[n] * self.pesos['recencia'] +
                clust[n] * self.pesos['cluster'] +
                viz[n] * self.pesos['vizinhanca'] +
                delay[n] * self.pesos['delay'] +
                lucky[n] * self.pesos['lucky']
            )
            scores[n] = score
            detalhes[n] = {
                'freq': freq[n],
                'rec': rec[n],
                'cluster': clust[n],
                'viz': viz[n],
                'delay': delay[n],
                'lucky': lucky[n],
                'total': score
            }
        
        return scores, detalhes
    
    def analisar_score(self):
        """Analisa e retorna previsão baseada no score engine"""
        if len(self.historico) < 5:
            return None
        
        scores, detalhes = self.calcular_score_total()
        
        # Ordena por score decrescente
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Seleciona os top_k números
        top_numeros = [num for num, score in ranking[:self.top_k]]
        numeros_originais_qtd = len(top_numeros)
        
        # Aplica seleção inteligente se mais de 15 números
        if len(top_numeros) > 15:
            top_numeros = self.sistema_selecao.selecionar_melhores_15_numeros(
                top_numeros, self.historico, "ScoreEngine"
            )
        
        # Calcula confiança baseada no score médio dos top 3
        score_top3 = sum(scores[n] for n in top_numeros[:3]) / 3
        confianca = self._calcular_nivel_confianca(score_top3)
        
        # Gera gatilho descritivo
        top3_scores = [(n, scores[n]) for n in top_numeros[:3]]
        top3_str = ", ".join([f"{n}({s:.2f})" for n, s in top3_scores])
        gatilho = f"🧠 Score Engine | Top 3: {top3_str} | Confiança: {confianca}"
        
        # Identifica se há lucky numbers entre os top
        lucky_recentes = set(self.lucky_tracking)
        lucky_no_top = [n for n in top_numeros if n in lucky_recentes]
        if lucky_no_top:
            gatilho += f" | 🍀 Lucky: {lucky_no_top[:3]}"
        
        return {
            'nome': 'Score Engine Pro',
            'numeros_apostar': top_numeros,
            'gatilho': gatilho,
            'confianca': confianca,
            'tipo': 'score_engine',
            'selecao_inteligente': len(top_numeros) < self.top_k,
            'numeros_originais_qtd': numeros_originais_qtd,
            'scores_detalhados': {n: detalhes[n] for n in top_numeros},
            'ranking_completo': ranking[:20]
        }
    
    def _calcular_nivel_confianca(self, score_medio):
        """Converte score médio em nível de confiança"""
        if score_medio >= 0.7:
            return 'Muito Alta'
        elif score_medio >= 0.5:
            return 'Alta'
        elif score_medio >= 0.35:
            return 'Média'
        elif score_medio >= 0.2:
            return 'Baixa'
        else:
            return 'Muito Baixa'
    
    def get_analise_score(self):
        """Retorna análise detalhada do score engine"""
        if len(self.historico) < 5:
            return "🧠 Score Engine: Aguardando mais dados (mínimo 5 números)"
        
        scores, detalhes = self.calcular_score_total()
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:15]
        
        analise = "🧠 ANÁLISE SCORE ENGINE PRO\n"
        analise += "=" * 45 + "\n"
        analise += f"📊 Histórico: {len(self.historico)} números\n"
        analise += f"🍀 Lucky Numbers tracking: {len(self.lucky_tracking)} registros\n"
        analise += f"🎯 Pesos: F:{self.pesos['frequencia']:.0%} R:{self.pesos['recencia']:.0%} "
        analise += f"C:{self.pesos['cluster']:.0%} V:{self.pesos['vizinhanca']:.0%} "
        analise += f"D:{self.pesos['delay']:.0%} L:{self.pesos['lucky']:.0%}\n"
        analise += "=" * 45 + "\n"
        analise += "🏆 TOP 15 SCORES:\n"
        
        for i, (num, score) in enumerate(ranking, 1):
            det = detalhes[num]
            barra = "█" * int(score * 20)
            analise += f"{i:2d}. {num:2d}: {barra} {score:.3f} "
            analise += f"(F:{det['freq']:.2f} R:{det['rec']:.2f} C:{det['cluster']:.2f} "
            analise += f"V:{det['viz']:.2f} D:{det['delay']:.2f} L:{det['lucky']:.2f})\n"
        
        # Últimos lucky numbers
        if self.lucky_tracking:
            ultimos_lucky = list(self.lucky_tracking)[-10:]
            analise += f"\n🍀 Últimos Lucky Numbers: {ultimos_lucky}\n"
        
        # Detecção de cluster ativo
        if len(self.historico) >= 2:
            ultimo = self.historico[-1]
            penultimo = self.historico[-2] if len(self.historico) >= 2 else None
            if ultimo == penultimo:
                analise += f"\n🔥 CLUSTER ATIVO: Número {ultimo} repetiu!\n"
        
        return analise
    
    def zerar_estatisticas(self):
        """Zera histórico e tracking"""
        self.historico.clear()
        self.lucky_tracking.clear()
        logging.info("🧠 Estatísticas do Score Engine zeradas")

# =============================
# MÓDULO DE CADEIA DE MARKOV
# =============================
class EstrategiaMarkov:
    """
    Estratégia baseada em Cadeia de Markov para previsão de números da roleta.
    Analisa sequências de números e calcula probabilidades de transição.
    Retorna os 6 números mais prováveis baseados no último número sorteado.
    """
    
    def __init__(self, ordem: int = 2, top_k: int = 6):
        """
        Inicializa a estratégia de Markov.
        
        Args:
            ordem: Ordem da cadeia de Markov (1 = último número, 2 = últimos 2 números)
            top_k: Número de previsões a retornar (padrão = 6)
        """
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=200)  # Mantém até 200 números no histórico
        self.nome = "Cadeia de Markov"
        self.ordem = ordem
        self.top_k = top_k
        self.matriz_transicao = {}  # Dicionário para armazenar as probabilidades de transição
        self.contador_sorteios = 0
        self.sistema_selecao = SistemaSelecaoInteligente()
        
        # Inicializa a matriz de transição para todos os estados possíveis
        self._inicializar_matriz()
        
    def _inicializar_matriz(self):
        """Inicializa a estrutura da matriz de transição"""
        self.matriz_transicao = {}
        
        # Para cadeia de ordem 1: estados são números individuais (0-36)
        if self.ordem == 1:
            for i in range(37):
                self.matriz_transicao[i] = {j: 0 for j in range(37)}
        
        # Para cadeia de ordem 2: estados são tuplas de 2 números
        else:
            for i in range(37):
                for j in range(37):
                    self.matriz_transicao[(i, j)] = {k: 0 for k in range(37)}
    
    def adicionar_numero(self, numero):
        """Adiciona um número ao histórico e atualiza a matriz de transição"""
        self.historico.append(numero)
        self.contador_sorteios += 1
        
        # Atualiza a matriz de transição
        self._atualizar_matriz_transicao()
        
        # Retreinamento periódico da matriz
        if self.contador_sorteios >= 50:
            self.contador_sorteios = 0
            self._normalizar_matriz()
            
        if 'sistema' in st.session_state:
            salvar_sessao()
    
    def _atualizar_matriz_transicao(self):
        """Atualiza a matriz de transição baseada no histórico"""
        if len(self.historico) < self.ordem + 1:
            return
        
        historico_lista = list(self.historico)
        
        if self.ordem == 1:
            # Cadeia de Markov de ordem 1
            for i in range(len(historico_lista) - 1):
                estado_atual = historico_lista[i]
                proximo_estado = historico_lista[i + 1]
                
                if estado_atual in self.matriz_transicao:
                    if proximo_estado in self.matriz_transicao[estado_atual]:
                        self.matriz_transicao[estado_atual][proximo_estado] += 1
        
        else:
            # Cadeia de Markov de ordem 2
            for i in range(len(historico_lista) - 2):
                estado_atual = (historico_lista[i], historico_lista[i + 1])
                proximo_estado = historico_lista[i + 2]
                
                if estado_atual in self.matriz_transicao:
                    if proximo_estado in self.matriz_transicao[estado_atual]:
                        self.matriz_transicao[estado_atual][proximo_estado] += 1
    
    def _normalizar_matriz(self):
        """Normaliza as probabilidades na matriz de transição"""
        for estado in self.matriz_transicao:
            total = sum(self.matriz_transicao[estado].values())
            if total > 0:
                for proximo in self.matriz_transicao[estado]:
                    self.matriz_transicao[estado][proximo] = self.matriz_transicao[estado][proximo] / total
    
    def _obter_estado_atual(self):
        """Retorna o estado atual baseado no histórico mais recente"""
        if len(self.historico) < self.ordem:
            return None
        
        historico_lista = list(self.historico)
        
        if self.ordem == 1:
            return historico_lista[-1]
        else:
            return (historico_lista[-2], historico_lista[-1])
    
    def _prever_proximos_numeros(self):
        """
        Prevê os próximos números baseado no estado atual da cadeia.
        Retorna lista de tuplas (número, probabilidade) ordenada por probabilidade.
        """
        estado_atual = self._obter_estado_atual()
        
        if estado_atual is None or estado_atual not in self.matriz_transicao:
            return []
        
        probabilidades = self.matriz_transicao[estado_atual]
        
        # Filtra apenas números com probabilidade > 0
        previsoes = [(num, prob) for num, prob in probabilidades.items() if prob > 0]
        
        # Ordena por probabilidade decrescente
        previsoes.sort(key=lambda x: x[1], reverse=True)
        
        return previsoes[:self.top_k]
    
    def _ajustar_com_vizinhanca(self, previsoes):
        """
        Ajusta as previsões considerando a vizinhança física na roleta.
        Se um número previsto tem alta probabilidade, seus vizinhos também ganham peso.
        """
        if not previsoes:
            return previsoes
        
        scores = {}
        for num, prob in previsoes:
            scores[num] = prob
        
        # Adiciona peso aos vizinhos dos números mais prováveis
        for num in list(scores.keys())[:3]:  # Apenas top 3
            vizinhos = self.roleta.get_vizinhos_fisicos(num, raio=2)
            for vizinho in vizinhos:
                if vizinho in scores:
                    scores[vizinho] += scores[num] * 0.3
                else:
                    scores[vizinho] = scores[num] * 0.3
        
        # Reordena baseado nos novos scores
        previsoes_ajustadas = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        return previsoes_ajustadas[:self.top_k]
    
    def analisar_markov(self):
        """
        Analisa o histórico e retorna previsão baseada na Cadeia de Markov.
        Retorna os top_k números mais prováveis.
        """
        if len(self.historico) < self.ordem + 5:
            return None
        
        # Obtém previsões iniciais
        previsoes = self._prever_proximos_numeros()
        
        if not previsoes:
            # Fallback: usar frequência simples
            return self._fallback_frequencia()
        
        # Ajusta com vizinhança
        previsoes_ajustadas = self._ajustar_com_vizinhanca(previsoes)
        
        # Extrai apenas os números
        numeros_previstos = [num for num, prob in previsoes_ajustadas]
        
        # Aplica seleção inteligente se necessário
        numeros_originais_qtd = len(numeros_previstos)
        if len(numeros_previstos) > 15:
            numeros_previstos = self.sistema_selecao.selecionar_melhores_15_numeros(
                numeros_previstos, self.historico, "Markov"
            )
        
        # Calcula confiança baseada na soma das probabilidades
        confianca_valor = sum(prob for _, prob in previsoes_ajustadas[:3])
        confianca = self._calcular_nivel_confianca(confianca_valor)
        
        # Gera gatilho informativo
        estado_atual = self._obter_estado_atual()
        gatilho = self._gerar_gatilho(estado_atual, previsoes_ajustadas)
        
        return {
            'nome': f'Cadeia de Markov (Ordem {self.ordem})',
            'numeros_apostar': numeros_previstos,
            'gatilho': gatilho,
            'confianca': confianca,
            'tipo': 'markov',
            'selecao_inteligente': len(numeros_previstos) < numeros_originais_qtd,
            'numeros_originais_qtd': numeros_originais_qtd,
            'previsoes_detalhadas': previsoes_ajustadas,
            'estado_atual': estado_atual
        }
    
    def _fallback_frequencia(self):
        """Fallback baseado em frequência simples quando a matriz não tem dados suficientes"""
        if len(self.historico) < 10:
            return None
        
        historico_lista = list(self.historico)
        contagem = Counter(historico_lista[-30:])  # Últimos 30 números
        
        numeros_mais_frequentes = [num for num, _ in contagem.most_common(self.top_k)]
        
        return {
            'nome': 'Cadeia de Markov (Fallback - Frequência)',
            'numeros_apostar': numeros_mais_frequentes,
            'gatilho': f'Fallback: Baseado em frequência dos últimos 30 números',
            'confianca': 'Baixa',
            'tipo': 'markov_fallback',
            'selecao_inteligente': False,
            'numeros_originais_qtd': len(numeros_mais_frequentes)
        }
    
    def _calcular_nivel_confianca(self, valor_probabilidade):
        """Converte o valor de probabilidade em nível de confiança"""
        if valor_probabilidade >= 0.6:
            return 'Muito Alta'
        elif valor_probabilidade >= 0.45:
            return 'Alta'
        elif valor_probabilidade >= 0.3:
            return 'Média'
        elif valor_probabilidade >= 0.15:
            return 'Baixa'
        else:
            return 'Muito Baixa'
    
    def _gerar_gatilho(self, estado_atual, previsoes):
        """Gera texto descritivo do gatilho"""
        if estado_atual is None:
            return "Aguardando dados suficientes para Cadeia de Markov"
        
        if self.ordem == 1:
            estado_str = f"Último número: {estado_atual}"
        else:
            estado_str = f"Últimos números: {estado_atual[0]} → {estado_atual[1]}"
        
        top3_str = ", ".join([f"{num}({prob:.1%})" for num, prob in previsoes[:3]])
        
        return f"🎲 Markov (ordem {self.ordem}) | {estado_str} | Top 3: {top3_str}"
    
    def get_analise_markov(self):
        """Retorna análise detalhada do estado atual da cadeia de Markov"""
        if len(self.historico) < self.ordem + 2:
            return f"🎲 Cadeia de Markov: Aguardando mais dados (mínimo {self.ordem + 2} números)"
        
        analise = f"🎲 ANÁLISE DA CADEIA DE MARKOV (Ordem {self.ordem})\n"
        analise += "=" * 45 + "\n"
        analise += f"📊 Histórico: {len(self.historico)} números\n"
        analise += f"🎯 Top {self.top_k} previsões\n"
        
        estado_atual = self._obter_estado_atual()
        if estado_atual:
            if self.ordem == 1:
                analise += f"🔍 Estado atual: {estado_atual}\n"
            else:
                analise += f"🔍 Estado atual: {estado_atual[0]} → {estado_atual[1]}\n"
            
            previsoes = self._prever_proximos_numeros()
            if previsoes:
                analise += "\n📈 PROBABILIDADES:\n"
                for i, (num, prob) in enumerate(previsoes[:self.top_k], 1):
                    barra = "█" * int(prob * 20)
                    analise += f"  {i}. Número {num:2d}: {barra} {prob:.1%}\n"
        
        # Estatísticas da matriz
        total_transicoes = sum(len(trans) for trans in self.matriz_transicao.values())
        analise += f"\n📊 Matriz de transição: {len(self.matriz_transicao)} estados, {total_transicoes} transições registradas\n"
        
        return analise
    
    def get_estatisticas_matriz(self):
        """Retorna estatísticas da matriz de transição"""
        if not self.matriz_transicao:
            return "Matriz de transição vazia"
        
        total_estados = len(self.matriz_transicao)
        estados_com_dados = sum(1 for estado in self.matriz_transicao if sum(self.matriz_transicao[estado].values()) > 0)
        
        estatisticas = f"📊 ESTATÍSTICAS DA MATRIZ DE MARKOV\n"
        estatisticas += f"🎲 Ordem da cadeia: {self.ordem}\n"
        estatisticas += f"📈 Estados possíveis: {total_estados}\n"
        estatisticas += f"✅ Estados com dados: {estados_com_dados}\n"
        estatisticas += f"📊 Cobertura: {(estados_com_dados/total_estados)*100:.1f}%\n"
        
        if self.ordem == 1:
            estatisticas += f"🎯 Números possíveis: 37\n"
        else:
            estatisticas += f"🎯 Pares possíveis: 1369\n"
        
        return estatisticas
    
    def zerar_matriz(self):
        """Zera a matriz de transição e o histórico"""
        self.historico.clear()
        self._inicializar_matriz()
        self.contador_sorteios = 0
        logging.info("🔄 Matriz de Markov zerada")

# =============================
# MÓDULO DE MACHINE LEARNING
# =============================
class MLRoletaOtimizada:
    def __init__(
        self,
        roleta_obj,
        min_training_samples: int = 200,
        max_history: int = 1000,
        retrain_every_n: int = 15,
        seed: int = 42
    ):
        self.roleta = roleta_obj
        self.min_training_samples = min_training_samples
        self.max_history = max_history
        self.retrain_every_n = retrain_every_n
        self.seed = seed

        self.models = []
        self.scaler = StandardScaler()
        self.feature_names = []
        self.is_trained = False
        self.contador_treinamento = 0
        self.meta = {}

        self.window_for_features = [3, 8, 15, 30, 60, 120]
        self.k_vizinhos = 2
        self.numeros = list(range(37))
        
        self.ensemble_size = 3

    def get_neighbors(self, numero, k=None):
        if k is None:
            k = self.k_vizinhos
        try:
            race = list(self.roleta.race)
            n = len(race)
            idx = race.index(numero)
            neighbors = []
            for offset in range(-k, k+1):
                neighbors.append(race[(idx + offset) % n])
            return neighbors
        except Exception:
            return [numero]

    def extrair_features(self, historico, numero_alvo=None):
        try:
            historico = list(historico)
            N = len(historico)
            
            if N < 10:
                return None, None

            features = []
            names = []

            K_seq = 10
            ultimos = historico[-K_seq:]
            for i in range(K_seq):
                val = ultimos[i] if i < len(ultimos) else -1
                features.append(val)
                names.append(f"ultimo_{i+1}")

            for w in self.window_for_features:
                janela = historico[-w:] if N >= w else historico[:]
                arr = np.array(janela, dtype=float)
                features.append(arr.mean() if len(arr) > 0 else 0.0); names.append(f"media_{w}")
                features.append(arr.std() if len(arr) > 1 else 0.0); names.append(f"std_{w}")
                features.append(np.median(arr) if len(arr) > 0 else 0.0); names.append(f"mediana_{w}")

            counter_full = Counter(historico)
            for w in self.window_for_features:
                janela = historico[-w:] if N >= w else historico[:]
                c = Counter(janela)
                features.append(len(c) / (w if w>0 else 1)); names.append(f"diversidade_{w}")
                top1_count = c.most_common(1)[0][1] if len(c)>0 else 0
                features.append(top1_count / (w if w>0 else 1)); names.append(f"top1_prop_{w}")

            for num in self.numeros:
                try:
                    rev_idx = historico[::-1].index(num)
                    tempo = rev_idx
                except ValueError:
                    tempo = N + 1
                features.append(tempo)
                names.append(f"tempo_desde_{num}")

            janela50 = historico[-50:] if N >= 50 else historico[:]
            vermelhos = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
            pretos = set(self.numeros[1:]) - vermelhos
            count_verm = sum(1 for x in janela50 if x in vermelhos)
            count_pret = sum(1 for x in janela50 if x in pretos)
            count_zero = sum(1 for x in janela50 if x == 0)
            features.extend([count_verm/len(janela50), count_pret/len(janela50), count_zero/len(janela50)])
            names.extend(["prop_vermelhos_50", "prop_pretos_50", "prop_zero_50"])

            def duzia_of(x):
                if x == 0: return 0
                if 1 <= x <= 12: return 1
                if 13 <= x <= 24: return 2
                return 3
            for d in [1,2,3]:
                features.append(sum(1 for x in janela50 if duzia_of(x)==d)/len(janela50))
                names.append(f"prop_duzia_{d}_50")

            ultimo_num = historico[-1]
            vizinhos_k = self.get_neighbors(ultimo_num, k=6)
            count_in_vizinhos = sum(1 for x in ultimos if x in vizinhos_k) / len(ultimos)
            features.append(count_in_vizinhos); names.append("prop_ultimos_em_vizinhos_6")

            features.append(1 if N>=2 and historico[-1] == historico[-2] else 0); names.append("repetiu_ultimo")
            features.append(1 if N>=2 and (historico[-1] % 2) == (historico[-2] % 2) else 0); names.append("repetiu_paridade")
            features.append(1 if N>=2 and duzia_of(historico[-1]) == duzia_of(historico[-2]) else 0); names.append("repetiu_duzia")

            if N >= max(self.window_for_features):
                small = np.mean(historico[-self.window_for_features[0]:])
                large = np.mean(historico[-self.window_for_features[-1]:])
                features.append(small - large); names.append("delta_media_small_large")
            else:
                features.append(0.0); names.append("delta_media_small_large")

            diffs = [abs(historico[i] - historico[i-1]) for i in range(1, len(historico))]
            features.append(np.mean(diffs) if len(diffs)>0 else 0.0); names.append("media_transicoes")
            features.append(np.std(diffs) if len(diffs)>1 else 0.0); names.append("std_transicoes")

            self.feature_names = names
            return features, names

        except Exception as e:
            logging.error(f"[extrair_features] Erro: {e}")
            return None, None

    def preparar_dados_treinamento(self, historico_completo):
        historico_completo = list(historico_completo)
        if len(historico_completo) > self.max_history:
            historico_completo = historico_completo[-self.max_history:]

        X = []
        y = []
        
        start_index = max(50, len(historico_completo) // 10)
        
        for i in range(start_index, len(historico_completo)):
            janela = historico_completo[:i]
            feats, _ = self.extrair_features(janela)
            if feats is None:
                continue
            X.append(feats)
            y.append(historico_completo[i])
        
        if len(X) == 0:
            return np.array([]), np.array([])
        
        class_counts = Counter(y)
        if len(class_counts) < 10:
            logging.warning(f"Pouca variedade de classes: apenas {len(class_counts)} números únicos")
            return np.array([]), np.array([])
        
        return np.array(X), np.array(y)

    def _build_and_train_model(self, X_train, y_train, X_val=None, y_val=None, seed=0):
        try:
            try:
                from catboost import CatBoostClassifier
                model = CatBoostClassifier(
                    iterations=1500,
                    learning_rate=0.05,
                    depth=10,
                    l2_leaf_reg=5,
                    bagging_temperature=0.8,
                    random_strength=1.0,
                    loss_function='MultiClass',
                    eval_metric='MultiClass',
                    random_seed=seed,
                    use_best_model=True,
                    early_stopping_rounds=100,
                    verbose=False
                )
                if X_val is not None and y_val is not None:
                    model.fit(X_train, y_train, eval_set=(X_val, y_val), verbose=False)
                else:
                    model.fit(X_train, y_train, verbose=False)
                return model, "CatBoost"
            except ImportError:
                raise Exception("CatBoost não disponível")
                
        except Exception as e:
            logging.warning(f"CatBoost não disponível ou falha ({e}). Usando RandomForest como fallback.")
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(
                n_estimators=400,
                max_depth=20,
                min_samples_split=3,
                min_samples_leaf=2,
                random_state=seed,
                n_jobs=-1
            )
            model.fit(X_train, y_train)
            return model, "RandomForest"

    def treinar_modelo(self, historico_completo, force_retrain: bool = False, balance: bool = True):
        try:
            if len(historico_completo) < self.min_training_samples and not force_retrain:
                return False, f"Necessário mínimo de {self.min_training_samples} amostras. Atual: {len(historico_completo)}"

            X, y = self.preparar_dados_treinamento(historico_completo)
            if X.size == 0 or len(X) < 50:
                return False, f"Dados insuficientes para treino: {len(X)} amostras"

            X_scaled = self.scaler.fit_transform(X)

            try:
                class_counts = Counter(y)
                min_samples_per_class = min(class_counts.values())
                
                can_stratify = min_samples_per_class >= 2 and len(class_counts) > 1
                
                X_train, X_val, y_train, y_val = train_test_split(
                    X_scaled, y, 
                    test_size=0.2, 
                    random_state=self.seed, 
                    stratify=y if can_stratify else None
                )
                
                logging.info(f"Split realizado: estratificação = {can_stratify}, classes = {len(class_counts)}, min_amostras = {min_samples_per_class}")
                
            except Exception as e:
                logging.warning(f"Erro no split estratificado: {e}. Usando split sem estratificação.")
                X_train, X_val, y_train, y_val = train_test_split(
                    X_scaled, y, test_size=0.2, random_state=self.seed
                )

            if balance and len(X_train) > 0:
                try:
                    df_train = pd.DataFrame(X_train, columns=[f"f{i}" for i in range(X_train.shape[1])])
                    df_train['y'] = y_train
                    
                    value_counts = df_train['y'].value_counts()
                    if len(value_counts) == 0:
                        raise ValueError("Nenhuma classe encontrada")
                    
                    max_count = value_counts.max()
                    
                    if len(value_counts) < 2:
                        logging.warning("Apenas uma classe disponível, pulando balanceamento")
                        balance = False
                    else:
                        frames = []
                        for cls, grp in df_train.groupby('y'):
                            if len(grp) < max_count:
                                if len(grp) >= 1:
                                    min_samples = max(5, max_count // 3)
                                    n_samples = min(max_count, min_samples)
                                    grp_up = resample(grp, replace=True, n_samples=n_samples, random_state=self.seed)
                                    frames.append(grp_up)
                                else:
                                    frames.append(grp)
                            else:
                                frames.append(grp)
                        
                        if frames:
                            df_bal = pd.concat(frames)
                            y_train = df_bal['y'].values
                            X_train = df_bal.drop(columns=['y']).values
                        else:
                            balance = False
                            
                except Exception as e:
                    logging.warning(f"Erro no balanceamento: {e}. Continuando sem balanceamento.")
                    balance = False

            models = []
            model_names = []
            
            for s in [self.seed, self.seed + 7, self.seed + 13]:
                try:
                    model, name = self._build_and_train_model(X_train, y_train, X_val, y_val, seed=s)
                    models.append(model)
                    model_names.append(name)
                except Exception as e:
                    logging.error(f"Erro ao treinar modelo {s}: {e}")

            if not models:
                return False, "Todos os modelos falharam no treinamento"

            try:
                probs = []
                for m in models:
                    if hasattr(m, 'predict_proba'):
                        probs.append(m.predict_proba(X_val))
                    else:
                        preds = m.predict(X_val)
                        prob = np.zeros((len(preds), len(self.numeros)))
                        for i, p in enumerate(preds):
                            prob[i, p] = 1.0
                        probs.append(prob)
                
                if probs:
                    avg_prob = np.mean(probs, axis=0)
                    y_pred = np.argmax(avg_prob, axis=1)
                    acc = accuracy_score(y_val, y_pred)
                else:
                    acc = 0.0
                    
            except Exception as e:
                logging.warning(f"Erro na avaliação: {e}")
                acc = 0.0

            self.models = models
            self.is_trained = True
            self.contador_treinamento += 1
            self.meta['last_accuracy'] = acc
            self.meta['trained_on'] = len(historico_completo)
            self.meta['last_training_size'] = len(X)

            try:
                joblib.dump({'models': self.models}, ML_MODEL_PATH)
                joblib.dump(self.scaler, SCALER_PATH)
                joblib.dump(self.meta, META_PATH)
                logging.info(f"Modelos salvos em disco: {ML_MODEL_PATH}")
            except Exception as e:
                logging.warning(f"Falha ao salvar modelos: {e}")

            return True, f"Ensemble treinado ({', '.join(model_names)}) com {len(X)} amostras. Acurácia validação: {acc:.2%}"

        except Exception as e:
            logging.error(f"[treinar_modelo] Erro: {e}", exc_info=True)
            return False, f"Erro no treinamento: {str(e)}"

    def carregar_modelo(self):
        try:
            if os.path.exists(ML_MODEL_PATH) and os.path.exists(SCALER_PATH):
                data = joblib.load(ML_MODEL_PATH)
                self.models = data.get('models', [])
                self.scaler = joblib.load(SCALER_PATH)
                if os.path.exists(META_PATH):
                    self.meta = joblib.load(META_PATH)
                self.is_trained = len(self.models) > 0
                return True
            return False
        except Exception as e:
            logging.error(f"[carregar_modelo] Erro: {e}")
            return False

    def _ensemble_predict_proba(self, X_scaled):
        if not self.models:
            return np.ones((len(X_scaled), len(self.numeros))) / len(self.numeros)

        probs = []
        for m in self.models:
            if hasattr(m, 'predict_proba'):
                probs.append(m.predict_proba(X_scaled))
            else:
                preds = m.predict(X_scaled)
                prob = np.zeros((len(preds), len(self.numeros)))
                for i, p in enumerate(preds):
                    prob[i, p] = 1.0
                probs.append(prob)
        return np.mean(probs, axis=0)

    def prever_proximo_numero(self, historico, top_k: int = 25):
        if not self.is_trained:
            return None, "Modelo não treinado"

        feats, _ = self.extrair_features(historico)
        if feats is None:
            return None, "Features insuficientes"

        Xs = np.array([feats])
        Xs_scaled = self.scaler.transform(Xs)
        try:
            probs = self._ensemble_predict_proba(Xs_scaled)[0]
            top_idx = np.argsort(probs)[-top_k:][::-1]
            top = [(int(idx), float(probs[idx])) for idx in top_idx]
            return top, "Previsão ML realizada"
        except Exception as e:
            return None, f"Erro na previsão: {str(e)}"

    def prever_blocos_vizinhos(self, historico, k_neighbors: int = 2, top_blocks: int = 5):
        pred, msg = self.prever_proximo_numero(historico, top_k=37)
        if pred is None:
            return None, msg
        prob = {num: p for num, p in pred}
        blocks = []
        for num in range(37):
            neigh = self.get_neighbors(num, k=k_neighbors)
            agg_prob = sum(prob.get(n, 0.0) for n in neigh)
            blocks.append((num, tuple(neigh), agg_prob))
        blocks_sorted = sorted(blocks, key=lambda x: x[2], reverse=True)[:top_blocks]
        formatted = [{"central": b[0], "vizinhos": list(b[1]), "prob": float(b[2])} for b in blocks_sorted]
        return formatted, "Previsão de blocos realizada"

    def registrar_resultado(self, historico, previsao_top, resultado_real):
        try:
            hit = resultado_real in [p for p,_ in previsao_top] if isinstance(previsao_top[0], tuple) else resultado_real in previsao_top
            log_entry = {
                'prev_top': previsao_top,
                'resultado': resultado_real,
                'hit': bool(hit)
            }
            self.meta.setdefault('history_feedback', []).append(log_entry)
            recent = self.meta['history_feedback'][-10:]
            hits = sum(1 for r in recent if r['hit'])
            if len(recent) >= 5 and hits / len(recent) < 0.25:
                logging.info("[feedback] Baixa performance detectada — forçando retreinamento incremental")
                self.treinar_modelo(historico, force_retrain=True, balance=True)
            return True
        except Exception as e:
            logging.error(f"[registrar_resultado] Erro: {e}")
            return False

    def verificar_treinamento_automatico(self, historico_completo):
        try:
            n = len(historico_completo)
            if n >= self.min_training_samples:
                if n % self.retrain_every_n == 0:
                    return self.treinar_modelo(historico_completo)
            return False, "Aguardando próximo ciclo de treinamento"
        except Exception as e:
            return False, f"Erro ao verificar retrain: {e}"

    def resumo_meta(self):
        return {
            "is_trained": self.is_trained,
            "contador_treinamento": self.contador_treinamento,
            "meta": self.meta
        }

# =============================
# ESTRATÉGIA DAS ZONAS COM ROTAÇÃO CÍCLICA (SEM BLOQUEIO)
# =============================
class EstrategiaZonasOtimizada:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=70)
        self.nome = "Zonas Ondas v9"
        
        self.zonas = {
            'Vermelha': 7,
            'Azul': 10,  
            'Amarela': 2
        }
        
        self.quantidade_zonas = {
            'Vermelha': 6,
            'Azul': 6,
            'Amarela': 6
        }
        
        # Lista de todas as combinações possíveis de zonas duplas (ordem cíclica)
        self.combinacoes_possiveis = [
            "Vermelha+Azul",
            "Vermelha+Amarela",
            "Azul+Amarela"
        ]
        
        # Índice da combinação atual (para rotação cíclica)
        self.indice_combinacao_atual = 0
        self.combinacao_atual = self.combinacoes_possiveis[0]
        self.ultima_combinacao_erro = ""
        
        self.stats_zonas = {zona: {
            'acertos': 0, 
            'tentativas': 0, 
            'sequencia_atual': 0,
            'sequencia_maxima': 0,
            'performance_media': 0
        } for zona in self.zonas.keys()}
        
        self.numeros_zonas = {}
        for nome, central in self.zonas.items():
            qtd = self.quantidade_zonas.get(nome, 6)
            self.numeros_zonas[nome] = self.roleta.get_vizinhos_zona(central, qtd)

        self.janelas_analise = {
            'curto_prazo': 12,
            'medio_prazo': 24,
            'longo_prazo': 48,
            'performance': 100
        }
        
        self.threshold_base = 25
        self.sistema_selecao = SistemaSelecaoInteligente()
        
        # Estatísticas de combinações
        self.combinacoes_stats = {}
        self.janela_dinamica = 50
        
        # Inicializar todas as combinações possíveis
        for comb_nome in self.combinacoes_possiveis:
            self.combinacoes_stats[comb_nome] = {
                'acertos': 0,
                'tentativas': 0,
                'ultimo_uso': 0,
                'sequencia_atual': 0,
                'melhor_taxa': 0,
                'historico_recente': deque(maxlen=self.janela_dinamica)
            }

    def adicionar_numero(self, numero):
        self.historico.append(numero)
        resultado = self.atualizar_stats(numero)
        if 'sistema' in st.session_state:
            salvar_sessao()
        return resultado

    def atualizar_stats(self, ultimo_numero):
        acertou_zona = None
        for zona, numeros in self.numeros_zonas.items():
            if ultimo_numero in numeros:
                self.stats_zonas[zona]['acertos'] += 1
                self.stats_zonas[zona]['sequencia_atual'] += 1
                if self.stats_zonas[zona]['sequencia_atual'] > self.stats_zonas[zona]['sequencia_maxima']:
                    self.stats_zonas[zona]['sequencia_maxima'] = self.stats_zonas[zona]['sequencia_atual']
                acertou_zona = zona
            else:
                self.stats_zonas[zona]['sequencia_atual'] = 0
            self.stats_zonas[zona]['tentativas'] += 1
            
            if self.stats_zonas[zona]['tentativas'] > 0:
                self.stats_zonas[zona]['performance_media'] = (
                    self.stats_zonas[zona]['acertos'] / self.stats_zonas[zona]['tentativas'] * 100
                )
        
        return acertou_zona

    def atualizar_combinacoes_stats(self, combinacao_usada, acertou):
        """Atualiza estatísticas da combinação usada e controla rotação"""
        if combinacao_usada in self.combinacoes_stats:
            self.combinacoes_stats[combinacao_usada]['tentativas'] += 1
            self.combinacoes_stats[combinacao_usada]['historico_recente'].append(1 if acertou else 0)
            
            if acertou:
                self.combinacoes_stats[combinacao_usada]['acertos'] += 1
                self.combinacoes_stats[combinacao_usada]['sequencia_atual'] += 1
                # Se acertou, reseta o registro de erro
                self.ultima_combinacao_erro = ""
            else:
                self.combinacoes_stats[combinacao_usada]['sequencia_atual'] = 0
                # Registra que esta combinação errou
                self.ultima_combinacao_erro = combinacao_usada
                # Roda para a próxima combinação
                self.proxima_combinacao()
                logging.info(f"🔄 Combinação {combinacao_usada} errou! Trocando para {self.combinacao_atual}")
            
            hist_recente = list(self.combinacoes_stats[combinacao_usada]['historico_recente'])
            if len(hist_recente) > 0:
                taxa_recente = sum(hist_recente) / len(hist_recente) * 100
                if taxa_recente > self.combinacoes_stats[combinacao_usada]['melhor_taxa']:
                    self.combinacoes_stats[combinacao_usada]['melhor_taxa'] = taxa_recente

    def proxima_combinacao(self):
        """Avança para a próxima combinação na ordem cíclica"""
        self.indice_combinacao_atual = (self.indice_combinacao_atual + 1) % len(self.combinacoes_possiveis)
        combinacao_antiga = self.combinacao_atual
        self.combinacao_atual = self.combinacoes_possiveis[self.indice_combinacao_atual]
        
        # Envia notificação de troca
        enviar_troca_combinacao_zonas(combinacao_antiga, self.combinacao_atual)
        
        return self.combinacao_atual

    def get_melhor_combinacao(self):
        """
        Retorna a combinação atual (rotação cíclica)
        SEM bloqueio, apenas alterna quando erra
        """
        if len(self.historico) < 20:
            return None
        
        # Retorna a combinação atual (configurada pela rotação)
        return self.combinacao_atual

    def get_zona_mais_quente(self):
        """Identifica a zona mais frequente (para fallback)"""
        if len(self.historico) < 15:
            return None
            
        zonas_score = {}
        
        for zona in self.zonas.keys():
            score = 0
            
            ultimos_curto = list(self.historico)[-self.janelas_analise['curto_prazo']:] if len(self.historico) >= self.janelas_analise['curto_prazo'] else list(self.historico)
            freq_curto = sum(1 for n in ultimos_curto if n in self.numeros_zonas[zona])
            percentual_curto = (freq_curto / len(ultimos_curto)) * 100 if len(ultimos_curto) > 0 else 0
            score += percentual_curto * 0.6
            
            sequencia = self.stats_zonas[zona]['sequencia_atual']
            if sequencia >= 2:
                score += sequencia * 8
            
            ultimos_medio = list(self.historico)[-self.janelas_analise['medio_prazo']:] if len(self.historico) >= self.janelas_analise['medio_prazo'] else list(self.historico)
            freq_medio = sum(1 for n in ultimos_medio if n in self.numeros_zonas[zona])
            percentual_medio = (freq_medio / len(ultimos_medio)) * 100 if len(ultimos_medio) > 0 else 0
            score += percentual_medio * 0.2
            
            zonas_score[zona] = score
        
        zona_vencedora = max(zonas_score, key=zonas_score.get) if zonas_score else None
        
        if zona_vencedora:
            ultimos_12 = list(self.historico)[-12:] if len(self.historico) >= 12 else list(self.historico)
            freq_zona = sum(1 for n in ultimos_12 if n in self.numeros_zonas[zona_vencedora])
            if freq_zona >= 2:
                return zona_vencedora
        
        return None

    def get_zonas_rankeadas(self):
        """Retorna zonas rankeadas por frequência recente"""
        if len(self.historico) < 15:
            return None
            
        zonas_score = {}
        
        for zona in self.zonas.keys():
            ultimos_12 = list(self.historico)[-12:] if len(self.historico) >= 12 else list(self.historico)
            freq_12 = sum(1 for n in ultimos_12 if n in self.numeros_zonas[zona])
            percentual_12 = (freq_12 / len(ultimos_12)) * 100
            
            ultimos_24 = list(self.historico)[-24:] if len(self.historico) >= 24 else list(self.historico)
            freq_24 = sum(1 for n in ultimos_24 if n in self.numeros_zonas[zona])
            percentual_24 = (freq_24 / len(ultimos_24)) * 100
            
            score = (percentual_12 * 0.7) + (percentual_24 * 0.3)
            
            sequencia = self.stats_zonas[zona]['sequencia_atual']
            if sequencia >= 2:
                score += sequencia * 5
            
            zonas_score[zona] = score
        
        zonas_rankeadas = sorted(zonas_score.items(), key=lambda x: x[1], reverse=True)
        return zonas_rankeadas

    def analisar_zonas_com_inversao(self):
        """
        Lógica SIMPLIFICADA:
        1. Usa a combinação atual (rotação cíclica)
        2. Se errar, avança para a próxima combinação
        3. Se não houver combinação disponível, usa zona simples
        """
        if len(self.historico) < 15:
            return None
        
        # Obtém a combinação atual
        melhor_combinacao = self.get_melhor_combinacao()
        
        if melhor_combinacao:
            zonas = melhor_combinacao.split('+')
            if len(zonas) == 2:
                zona_primaria = zonas[0]
                zona_secundaria = zonas[1]
                
                numeros_primarios = self.numeros_zonas[zona_primaria]
                numeros_secundarios = self.numeros_zonas[zona_secundaria]
                
                numeros_combinados = list(set(numeros_primarios + numeros_secundarios))
                numeros_originais_qtd = len(numeros_combinados)
                
                if len(numeros_combinados) > 15:
                    numeros_combinados = self.sistema_selecao.selecionar_melhores_15_numeros(
                        numeros_combinados, self.historico, "Zonas"
                    )
                
                confianca_primaria = self.calcular_confianca_onda(zona_primaria)
                confianca_secundaria = self.calcular_confianca_onda(zona_secundaria)
                
                stats_comb = self.combinacoes_stats.get(melhor_combinacao, {})
                hist_recente = list(stats_comb.get('historico_recente', []))
                taxa_recente = sum(hist_recente) / len(hist_recente) * 100 if hist_recente else 0
                
                # Mostrar última combinação que errou
                ultimo_erro_str = ""
                if self.ultima_combinacao_erro:
                    ultimo_erro_str = f" | Último erro: {self.ultima_combinacao_erro}"
                
                gatilho = f'🌊 ONDA: {melhor_combinacao} (Taxa: {taxa_recente:.1f}%) | SEL: {len(numeros_combinados)} números{ultimo_erro_str}'
                
                return {
                    'nome': f'Zonas Duplas - {melhor_combinacao}',
                    'numeros_apostar': numeros_combinados,
                    'gatilho': gatilho,
                    'confianca': f'{confianca_primaria}+{confianca_secundaria}',
                    'zona': melhor_combinacao,
                    'zonas_envolvidas': [zona_primaria, zona_secundaria],
                    'tipo': 'dupla',
                    'selecao_inteligente': True,
                    'combinacao_usada': melhor_combinacao,
                    'numeros_originais_qtd': numeros_originais_qtd
                }
        
        # Fallback: aposta simples na zona mais quente
        zona_primaria = self.get_zona_mais_quente()
        
        if not zona_primaria:
            return None
        
        numeros_apostar = self.numeros_zonas[zona_primaria]
        numeros_originais_qtd = len(numeros_apostar)
        
        if len(numeros_apostar) > 15:
            numeros_apostar = self.sistema_selecao.selecionar_melhores_15_numeros(
                numeros_apostar, self.historico, "Zonas"
            )
        
        confianca = self.calcular_confianca_onda(zona_primaria)
        
        ultimos_12 = list(self.historico)[-12:] if len(self.historico) >= 12 else list(self.historico)
        freq_zona = sum(1 for n in ultimos_12 if n in self.numeros_zonas[zona_primaria])
        percentual = (freq_zona / len(ultimos_12)) * 100
        
        sequencia = self.stats_zonas[zona_primaria]['sequencia_atual']
        sequencia_str = f" | 🔥 Seq: {sequencia}" if sequencia >= 2 else ""
        
        gatilho = f'🌊 ONDA SIMPLES: {zona_primaria} ({freq_zona}/{len(ultimos_12)} = {percentual:.0f}%){sequencia_str} | FINAL: {len(numeros_apostar)} números'
        
        return {
            'nome': f'Zona {zona_primaria}',
            'numeros_apostar': numeros_apostar,
            'gatilho': gatilho,
            'confianca': confianca,
            'zona': zona_primaria,
            'zonas_envolvidas': [zona_primaria],
            'tipo': 'unica',
            'selecao_inteligente': len(numeros_apostar) < len(self.numeros_zonas[zona_primaria]),
            'combinacao_usada': zona_primaria,
            'numeros_originais_qtd': numeros_originais_qtd
        }

    def analisar_zonas(self):
        return self.analisar_zonas_com_inversao()

    def calcular_confianca_onda(self, zona):
        """Calcula confiança baseada na INTENSIDADE DA ONDA"""
        if len(self.historico) < 10:
            return 'Baixa'
        
        ultimos_12 = list(self.historico)[-12:] if len(self.historico) >= 12 else list(self.historico)
        freq_recente = sum(1 for n in ultimos_12 if n in self.numeros_zonas[zona])
        percentual_recente = (freq_recente / len(ultimos_12)) * 100
        
        sequencia = self.stats_zonas[zona]['sequencia_atual']
        
        if percentual_recente >= 50 and sequencia >= 2:
            return 'Excelente'
        elif percentual_recente >= 40:
            return 'Muito Alta'
        elif percentual_recente >= 30:
            return 'Alta'
        elif percentual_recente >= 20:
            return 'Média'
        elif percentual_recente >= 10:
            return 'Baixa'
        else:
            return 'Muito Baixa'

    def get_zona_score(self, zona):
        """Score baseado em frequência recente"""
        if len(self.historico) < 10:
            return 0
        
        ultimos_12 = list(self.historico)[-12:] if len(self.historico) >= 12 else list(self.historico)
        freq_12 = sum(1 for n in ultimos_12 if n in self.numeros_zonas[zona])
        percentual_12 = (freq_12 / len(ultimos_12)) * 100
        
        ultimos_24 = list(self.historico)[-24:] if len(self.historico) >= 24 else list(self.historico)
        freq_24 = sum(1 for n in ultimos_24 if n in self.numeros_zonas[zona])
        percentual_24 = (freq_24 / len(ultimos_24)) * 100
        
        score = (percentual_12 * 0.7) + (percentual_24 * 0.3)
        
        sequencia = self.stats_zonas[zona]['sequencia_atual']
        if sequencia >= 2:
            score += sequencia * 5
            
        return score

    def get_info_zonas(self):
        info = {}
        for zona, numeros in self.numeros_zonas.items():
            info[zona] = {
                'numeros': sorted(numeros),
                'quantidade': len(numeros),
                'central': self.zonas[zona],
                'descricao': f"6 antes + 6 depois do {self.zonas[zona]}"
            }
        return info

    def get_analise_detalhada(self):
        if len(self.historico) == 0:
            return "Aguardando dados..."
        
        analise = "🎯 ANÁLISE DE ONDAS - ZONAS v9 (ROTAÇÃO CÍCLICA)\n"
        analise += "=" * 55 + "\n"
        analise += "🔧 ESTRATÉGIA: Apostar nas ZONAS MAIS FREQUENTES (ONDAS)\n"
        analise += "🔄 ROTAÇÃO: Troca de combinação a cada erro (ordem cíclica)\n"
        analise += f"📊 JANELA PRINCIPAL: Últimos {self.janelas_analise['curto_prazo']} sorteios\n"
        analise += "=" * 55 + "\n"
        
        analise += "🌊 RANKING DE ONDAS (Frequência nos últimos 12 sorteios):\n"
        
        ultimos_12 = list(self.historico)[-12:] if len(self.historico) >= 12 else list(self.historico)
        
        ranking_ondas = []
        for zona in self.zonas.keys():
            freq = sum(1 for n in ultimos_12 if n in self.numeros_zonas[zona])
            percentual = (freq / len(ultimos_12)) * 100
            sequencia = self.stats_zonas[zona]['sequencia_atual']
            ranking_ondas.append((zona, freq, percentual, sequencia))
        
        ranking_ondas.sort(key=lambda x: x[1], reverse=True)
        
        for zona, freq, perc, seq in ranking_ondas:
            seq_str = f" 🔥 Seq: {seq}" if seq >= 2 else ""
            analise += f"  📍 {zona}: {freq}/{len(ultimos_12)} ({perc:.1f}%){seq_str}\n"
        
        analise += f"\n🔄 COMBINAÇÃO ATUAL: {self.combinacao_atual}\n"
        
        if self.ultima_combinacao_erro:
            analise += f"⚠️ Última combinação que errou: {self.ultima_combinacao_erro}\n"
        
        analise += "\n📊 PERFORMANCE POR COMBINAÇÃO:\n"
        for comb_nome in self.combinacoes_possiveis:
            stats = self.combinacoes_stats.get(comb_nome, {})
            tentativas = stats.get('tentativas', 0)
            acertos = stats.get('acertos', 0)
            seq = stats.get('sequencia_atual', 0)
            if tentativas > 0:
                taxa = (acertos / tentativas) * 100
                atual_str = " 🔄 ATUAL" if comb_nome == self.combinacao_atual else ""
                seq_str = f" 🔥{seq}" if seq >= 2 else ""
                analise += f"  📊 {comb_nome}: {acertos}/{tentativas} ({taxa:.1f}%){seq_str}{atual_str}\n"
        
        zona_recomendada = self.get_zona_mais_quente()
        if zona_recomendada:
            freq = sum(1 for n in ultimos_12 if n in self.numeros_zonas[zona_recomendada])
            perc = (freq / len(ultimos_12)) * 100
            analise += f"\n💡 ONDA RECOMENDADA: {zona_recomendada}\n"
            analise += f"📈 Frequência: {freq}/{len(ultimos_12)} ({perc:.1f}%)\n"
        else:
            analise += "\n⚠️ AGUARDAR: Nenhuma onda forte identificada\n"
        
        return analise

    def get_analise_atual(self):
        return self.get_analise_detalhada()

    def zerar_estatisticas(self):
        for zona in self.stats_zonas.keys():
            self.stats_zonas[zona] = {
                'acertos': 0, 
                'tentativas': 0, 
                'sequencia_atual': 0,
                'sequencia_maxima': 0,
                'performance_media': 0
            }
        for comb in self.combinacoes_stats.keys():
            self.combinacoes_stats[comb] = {
                'acertos': 0,
                'tentativas': 0,
                'ultimo_uso': 0,
                'sequencia_atual': 0,
                'melhor_taxa': 0,
                'historico_recente': deque(maxlen=self.janela_dinamica)
            }
        self.indice_combinacao_atual = 0
        self.combinacao_atual = self.combinacoes_possiveis[0]
        self.ultima_combinacao_erro = ""
        logging.info("📊 Estatísticas das Zonas zeradas")

# =============================
# ESTRATÉGIA MIDAS (MANTIDA)
# =============================
class EstrategiaMidas:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=15)
        self.terminais = {
            '0': [0, 10, 20, 30], '1': [1, 11, 21, 31], '2': [2, 12, 22, 32],
            '3': [3, 13, 23, 33], '4': [4, 14, 24, 34], '5': [5, 15, 25, 35],
            '6': [6, 16, 26, 36], '7': [7, 17, 27], '8': [8, 18, 28], '9': [9, 19, 29]
        }

    def adicionar_numero(self, numero):
        self.historico.append(numero)
        if 'sistema' in st.session_state:
            salvar_sessao()

    def analisar_midas(self):
        if len(self.historico) < 5:
            return None
            
        ultimo_numero = self.historico[-1]
        historico_recente = self.historico[-5:]

        if ultimo_numero in [0, 10, 20, 30]:
            count_zero = sum(1 for n in historico_recente if n in [0, 10, 20, 30])
            if count_zero >= 1:
                return {
                    'nome': 'Padrão do Zero',
                    'numeros_apostar': [0, 10, 20, 30],
                    'gatilho': f'Terminal 0 ativado ({count_zero}x)',
                    'confianca': 'Média'
                }

        if ultimo_numero in [7, 17, 27]:
            count_sete = sum(1 for n in historico_recente if n in [7, 17, 27])
            if count_sete >= 1:
                return {
                    'nome': 'Padrão do Sete',
                    'numeros_apostar': [7, 17, 27],
                    'gatilho': f'Terminal 7 ativado ({count_sete}x)',
                    'confianca': 'Média'
                }

        if ultimo_numero in [5, 15, 25, 35]:
            count_cinco = sum(1 for n in historico_recente if n in [5, 15, 25, 35])
            if count_cinco >= 1:
                return {
                    'nome': 'Padrão do Cinco',
                    'numeros_apostar': [5, 15, 25, 35],
                    'gatilho': f'Terminal 5 ativado ({count_cinco}x)',
                    'confianca': 'Média'
                }

        return None

# =============================
# ESTRATÉGIA ML (MANTIDA)
# =============================
class EstrategiaML:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.ml = MLRoletaOtimizada(self.roleta)
        self.historico = deque(maxlen=30)
        self.nome = "Machine Learning (CatBoost)"
        self.ml.carregar_modelo()
        self.contador_sorteios = 0
        
        self.zonas_ml = {
            'Vermelha': 7,
            'Azul': 10,  
            'Amarela': 2
        }
        
        self.quantidade_zonas_ml = {
            'Vermelha': 6,
            'Azul': 6,
            'Amarela': 6
        }
        
        self.numeros_zonas_ml = {}
        for nome, central in self.zonas_ml.items():
            qtd = self.quantidade_zonas_ml.get(nome, 6)
            self.numeros_zonas_ml[nome] = self.roleta.get_vizinhos_zona(central, qtd)

        self.sequencias_padroes = {
            'sequencias_ativas': {},
            'historico_sequencias': [],
            'padroes_detectados': []
        }
        
        self.adicionar_metricas_padroes()
        
        self.sistema_selecao = SistemaSelecaoInteligente()

    def adicionar_metricas_padroes(self):
        self.metricas_padroes = {
            'padroes_detectados_total': 0,
            'padroes_acertados': 0,
            'padroes_errados': 0,
            'eficiencia_por_tipo': {},
            'historico_validacao': []
        }

    def adicionar_numero(self, numero):
        self.historico.append(numero)
        self.contador_sorteios += 1
        
        if len(self.historico) > 1:
            numero_anterior = list(self.historico)[-2]
            self.validar_padrao_acerto(numero, self.get_previsao_atual())
        
        self.analisar_padroes_sequenciais(numero)
        
        if self.contador_sorteios >= 15:
            self.contador_sorteios = 0
            self.treinar_automatico()
            
        if 'sistema' in st.session_state:
            salvar_sessao()

    def get_previsao_atual(self):
        try:
            resultado = self.analisar_ml()
            return resultado
        except:
            return None

    def validar_padrao_acerto(self, numero_sorteado, previsao_ml):
        zona_sorteada = None
        for zona, numeros in self.numeros_zonas_ml.items():
            if numero_sorteado in numeros:
                zona_sorteada = zona
                break
        
        if not zona_sorteada:
            return
        
        padroes_recentes = [p for p in self.sequencias_padroes['padroes_detectados'] 
                           if len(self.historico) - p['detectado_em'] <= 3]
        
        for padrao in padroes_recentes:
            self.metricas_padroes['padroes_detectados_total'] += 1
            
            if padrao['zona'] == zona_sorteada:
                self.metricas_padroes['padroes_acertados'] += 1
                tipo = padrao['tipo']
                if tipo not in self.metricas_padroes['eficiencia_por_tipo']:
                    self.metricas_padroes['eficiencia_por_tipo'][tipo] = {'acertos': 0, 'total': 0}
                self.metricas_padroes['eficiencia_por_tipo'][tipo]['acertos'] += 1
                self.metricas_padroes['eficiencia_por_tipo'][tipo]['total'] += 1
            else:
                self.metricas_padroes['padroes_errados'] += 1
                tipo = padrao['tipo']
                if tipo in self.metricas_padroes['eficiencia_por_tipo']:
                    self.metricas_padroes['eficiencia_por_tipo'][tipo]['total'] += 1

    def analisar_padroes_sequenciais(self, numero):
        if len(self.historico) < 6:
            return
            
        historico_recente = list(self.historico)[-8:]
        
        zona_atual = None
        for zona, numeros in self.numeros_zonas_ml.items():
            if numero in numeros:
                zona_atual = zona
                break
        
        if not zona_atual:
            return
        
        self.atualizar_sequencias_ativas(zona_atual, historico_recente)
        self.otimizar_deteccao_padroes(historico_recente)
        self.limpar_padroes_antigos()

    def otimizar_deteccao_padroes(self, historico_recente):
        if len(historico_recente) < 6:
            return
        
        zonas_recentes = []
        for num in historico_recente:
            zona_num = None
            for zona, numeros in self.numeros_zonas_ml.items():
                if num in numeros:
                    zona_num = zona
                    break
            zonas_recentes.append(zona_num)
        
        for i in range(len(zonas_recentes) - 5):
            janela = zonas_recentes[i:i+6]
            if (janela[0] and janela[1] and janela[2] and janela[4] and janela[5] and
                janela[0] == janela[1] == janela[2] == janela[4] == janela[5] and
                janela[3] != janela[0]):
                
                self.registrar_padrao_sequencia_interrompida(janela[0], i)

        for i in range(len(zonas_recentes) - 4):
            janela = zonas_recentes[i:i+5]
            if (janela[0] and janela[1] and janela[3] and janela[4] and
                janela[0] == janela[1] == janela[3] == janela[4] and
                janela[2] != janela[0]):
                
                self.registrar_padrao_retorno_rapido(janela[0], i)

    def registrar_padrao_sequencia_interrompida(self, zona, posicao):
        padrao = {
            'tipo': 'sequencia_interrompida_forte',
            'zona': zona,
            'padrao': 'AAA_B_AA',
            'forca': 0.85,
            'duracao': 6,
            'detectado_em': len(self.historico) - 1,
            'posicao_historico': posicao
        }
        
        if not self.padrao_recente_similar(padrao):
            self.sequencias_padroes['padroes_detectados'].append(padrao)
            logging.info(f"🎯 PADRÃO FORTE: {zona} - {padrao['padrao']}")

    def registrar_padrao_retorno_rapido(self, zona, posicao):
        padrao = {
            'tipo': 'retorno_rapido',
            'zona': zona,
            'padrao': 'AA_B_AA',
            'forca': 0.75,
            'duracao': 5,
            'detectado_em': len(self.historico) - 1,
            'posicao_historico': posicao
        }
        
        if not self.padrao_recente_similar(padrao):
            self.sequencias_padroes['padroes_detectados'].append(padrao)
            logging.info(f"🎯 PADRÃO RÁPIDO: {zona} - {padrao['padrao']}")

    def padrao_recente_similar(self, novo_padrao, janela=12):
        for padrao in self.sequencias_padroes['padroes_detectados'][-10:]:
            if (padrao['zona'] == novo_padrao['zona'] and 
                padrao['tipo'] == novo_padrao['tipo'] and
                len(self.historico) - padrao['detectado_em'] < janela):
                return True
        return False

    def limpar_padroes_antigos(self, limite=20):
        padroes_validos = []
        for padrao in self.sequencias_padroes['padroes_detectados']:
            if len(self.historico) - padrao['detectado_em'] <= limite:
                padroes_validos.append(padrao)
        self.sequencias_padroes['padroes_detectados'] = padroes_validos

    def atualizar_sequencias_ativas(self, zona_atual, historico_recente):
        if zona_atual in self.sequencias_padroes['sequencias_ativas']:
            sequencia = self.sequencias_padroes['sequencias_ativas'][zona_atual]
            sequencia['contagem'] += 1
            sequencia['ultimo_numero'] = historico_recente[-1]
        else:
            self.sequencias_padroes['sequencias_ativas'][zona_atual] = {
                'contagem': 1,
                'inicio': len(self.historico) - 1,
                'ultimo_numero': historico_recente[-1],
                'quebras': 0
            }
        
        zonas_ativas = list(self.sequencias_padroes['sequencias_ativas'].keys())
        for zona in zonas_ativas:
            if zona != zona_atual:
                self.sequencias_padroes['sequencias_ativas'][zona]['quebras'] += 1
                
                if self.sequencias_padroes['sequencias_ativas'][zona]['quebras'] >= 3:
                    sequencia_final = self.sequencias_padroes['sequencias_ativas'][zona]
                    if sequencia_final['contagem'] >= 3:
                        self.sequencias_padroes['historico_sequencias'].append({
                            'zona': zona,
                            'tamanho': sequencia_final['contagem'],
                            'finalizado_em': len(self.historico) - 1
                        })
                    del self.sequencias_padroes['sequencias_ativas'][zona]

    def aplicar_padroes_na_previsao(self, distribuicao_zonas):
        if not self.sequencias_padroes['padroes_detectados']:
            return distribuicao_zonas
        
        distribuicao_ajustada = distribuicao_zonas.copy()
        
        padroes_recentes = [p for p in self.sequencias_padroes['padroes_detectados'] 
                           if len(self.historico) - p['detectado_em'] <= 15]
        
        for padrao in padroes_recentes:
            zona = padrao['zona']
            forca = padrao['forca']
            
            if zona in distribuicao_ajustada:
                aumento = max(1, int(distribuicao_ajustada[zona] * forca * 0.3))
                distribuicao_ajustada[zona] += aumento
                logging.info(f"🎯 Aplicando padrão {padrao['tipo']} à zona {zona}: +{aumento}")
        
        return distribuicao_ajustada

    def calcular_confianca_com_padroes(self, distribuicao, zona_alvo):
        confianca_base = self.calcular_confianca_zona_ml({
            'contagem': distribuicao[zona_alvo],
            'total_zonas': 25
        })
        
        padroes_recentes = [p for p in self.sequencias_padroes['padroes_detectados'] 
                           if p['zona'] == zona_alvo and 
                           len(self.historico) - p['detectado_em'] <= 15]
        
        bonus_confianca = len(padroes_recentes) * 0.15
        confianca_final = min(1.0, self.confianca_para_valor(confianca_base) + bonus_confianca)
        
        return self.valor_para_confianca(confianca_final)

    def confianca_para_valor(self, confianca_texto):
        mapa_confianca = {
            'Muito Baixa': 0.3,
            'Baixa': 0.5,
            'Média': 0.65,
            'Alta': 0.8,
            'Muito Alta': 0.9
        }
        return mapa_confianca.get(confianca_texto, 0.5)

    def valor_para_confianca(self, valor):
        if valor >= 0.85: return 'Muito Alta'
        elif valor >= 0.7: return 'Alta'
        elif valor >= 0.6: return 'Média'
        elif valor >= 0.45: return 'Baixa'
        else: return 'Muito Baixa'

    def analisar_distribuicao_zonas_rankeadas(self, top_25_numeros):
        contagem_zonas = {}
        
        for zona, numeros in self.numeros_zonas_ml.items():
            count = sum(1 for num in top_25_numeros if num in numeros)
            contagem_zonas[zona] = count
        
        if not contagem_zonas:
            return None
            
        zonas_rankeadas = sorted(contagem_zonas.items(), key=lambda x: x[1], reverse=True)
        return zonas_rankeadas

    def analisar_ml_com_inversao(self):
        if len(self.historico) < 10:
            return None

        if not self.ml.is_trained:
            return None

        historico_numeros = self.extrair_numeros_historico()

        if len(historico_numeros) < 10:
            return None

        previsao_ml, msg_ml = self.ml.prever_proximo_numero(historico_numeros, top_k=25)
        
        if previsao_ml:
            top_25_numeros = [num for num, prob in previsao_ml[:25]]
            
            distribuicao_zonas = self.analisar_distribuicao_zonas_rankeadas(top_25_numeros)
            
            if not distribuicao_zonas:
                return None
                
            distribuicao_dict = dict(distribuicao_zonas)
            distribuicao_ajustada = self.aplicar_padroes_na_previsao(distribuicao_dict)
            
            zonas_rankeadas_ajustadas = sorted(distribuicao_ajustada.items(), key=lambda x: x[1], reverse=True)
            
            zona_primaria, contagem_primaria = zonas_rankeadas_ajustadas[0]
            
            if contagem_primaria < 7:
                return None
            
            numeros_originais_qtd = 0
            
            if len(zonas_rankeadas_ajustadas) > 1:
                zona_secundaria, contagem_secundaria = zonas_rankeadas_ajustadas[1]
                
                if contagem_secundaria >= 5:
                    numeros_primarios = self.numeros_zonas_ml[zona_primaria]
                    numeros_secundarios = self.numeros_zonas_ml[zona_secundaria]
                    
                    numeros_combinados = list(set(numeros_primarios + numeros_secundarios))
                    numeros_originais_qtd = len(numeros_combinados)
                    
                    if len(numeros_combinados) > 15:
                        numeros_combinados = self.sistema_selecao.selecionar_melhores_15_numeros(
                            numeros_combinados, self.historico, "ML"
                        )
                    
                    confianca = self.calcular_confianca_com_padroes(distribuicao_ajustada, zona_primaria)
                    
                    padroes_aplicados = [p for p in self.sequencias_padroes['padroes_detectados'] 
                                       if p['zona'] in [zona_primaria, zona_secundaria] and 
                                       len(self.historico) - p['detectado_em'] <= 15]
                    
                    gatilho_extra = ""
                    if padroes_aplicados:
                        gatilho_extra = f" | Padrões: {len(padroes_aplicados)}"
                    
                    contagem_original_primaria = distribuicao_dict[zona_primaria]
                    contagem_original_secundaria = distribuicao_dict.get(zona_secundaria, 0)
                    
                    gatilho = f'ML CatBoost - Zona {zona_primaria} ({contagem_original_primaria}→{contagem_primaria}/25) + Zona {zona_secundaria} ({contagem_original_secundaria}→{contagem_secundaria}/25) | FINAL: {len(numeros_combinados)} números{gatilho_extra}'
                    
                    return {
                        'nome': 'Machine Learning - CatBoost (Duplo)',
                        'numeros_apostar': numeros_combinados,
                        'gatilho': gatilho,
                        'confianca': confianca,
                        'previsao_ml': previsao_ml,
                        'zona_ml': f'{zona_primaria}+{zona_secundaria}',
                        'distribuicao': distribuicao_ajustada,
                        'padroes_aplicados': len(padroes_aplicados),
                        'zonas_envolvidas': [zona_primaria, zona_secundaria],
                        'tipo': 'dupla',
                        'selecao_inteligente': True,
                        'numeros_originais_qtd': numeros_originais_qtd
                    }
            
            numeros_zona = self.numeros_zonas_ml[zona_primaria]
            numeros_originais_qtd = len(numeros_zona)
            
            if len(numeros_zona) > 15:
                numeros_zona = self.sistema_selecao.selecionar_melhores_15_numeros(
                    numeros_zona, self.historico, "ML"
                )
            
            contagem_original = distribuicao_dict[zona_primaria]
            contagem_ajustada = contagem_primaria
            
            confianca = self.calcular_confianca_com_padroes(distribuicao_ajustada, zona_primaria)
            
            padroes_aplicados = [p for p in self.sequencias_padroes['padroes_detectados'] 
                               if p['zona'] == zona_primaria and 
                               len(self.historico) - p['detectado_em'] <= 15]
            
            gatilho_extra = ""
            if padroes_aplicados:
                gatilho_extra = f" | Padrões: {len(padroes_aplicados)}"
            
            return {
                'nome': 'Machine Learning - CatBoost',
                'numeros_apostar': numeros_zona,
                'gatilho': f'ML CatBoost - Zona {zona_primaria} ({contagem_original}→{contagem_ajustada}/25) | FINAL: {len(numeros_zona)} números{gatilho_extra}',
                'confianca': confianca,
                'previsao_ml': previsao_ml,
                'zona_ml': zona_primaria,
                'distribuicao': distribuicao_ajustada,
                'padroes_aplicados': len(padroes_aplicados),
                'zonas_envolvidas': [zona_primaria],
                'tipo': 'unica',
                'selecao_inteligente': len(numeros_zona) < len(self.numeros_zonas_ml[zona_primaria]),
                'numeros_originais_qtd': numeros_originais_qtd
            }
        
        return None

    def analisar_ml(self):
        return self.analisar_ml_com_inversao()

    def treinar_automatico(self):
        historico_numeros = self.extrair_numeros_historico()
        
        if len(historico_numeros) >= self.ml.min_training_samples:
            try:
                success, message = self.ml.treinar_modelo(historico_numeros)
                if success:
                    logging.info(f"✅ Treinamento automático ML: {message}")
                else:
                    logging.warning(f"⚠️ Treinamento automático falhou: {message}")
            except Exception as e:
                logging.error(f"❌ Erro no treinamento automático: {e}")

    def extrair_numeros_historico(self):
        historico_numeros = []
        for item in list(self.historico):
            if isinstance(item, dict) and 'number' in item:
                historico_numeros.append(item['number'])
            elif isinstance(item, (int, float)):
                historico_numeros.append(int(item))
        return historico_numeros

    def analisar_distribuicao_zonas(self, top_25_numeros):
        contagem_zonas = {}
        
        for zona, numeros in self.numeros_zonas_ml.items():
            count = sum(1 for num in top_25_numeros if num in numeros)
            contagem_zonas[zona] = count
        
        return contagem_zonas if contagem_zonas else None

    def calcular_confianca_zona_ml(self, distribuicao):
        contagem = distribuicao['contagem']
        total = distribuicao['total_zonas']
        percentual = (contagem / total) * 100
        
        if percentual >= 50:
            return 'Muito Alta'
        elif percentual >= 40:
            return 'Alta'
        elif percentual >= 30:
            return 'Média'
        elif percentual >= 25:
            return 'Baixa'
        else:
            return 'Muito Baixa'

    def treinar_modelo_ml(self, historico_completo=None):
        if historico_completo is not None:
            historico_numeros = historico_completo
        else:
            historico_numeros = self.extrair_numeros_historico()
        
        if len(historico_numeros) >= self.ml.min_training_samples:
            success, message = self.ml.treinar_modelo(historico_numeros)
            return success, message
        else:
            return False, f"Histórico insuficiente: {len(historico_numeros)}/{self.ml.min_training_samples} números"

    def get_analise_ml(self):
        if not self.ml.is_trained:
            return "🤖 ML: Modelo não treinado"
        
        if len(self.historico) < 10:
            return "🤖 ML: Aguardando mais dados para análise"
        
        historico_numeros = self.extrair_numeros_historico()
        previsao_ml, msg = self.ml.prever_proximo_numero(historico_numeros, top_k=25)
        
        if previsao_ml:
            if self.ml.models:
                primeiro_modelo = self.ml.models[0]
                modelo_tipo = "CatBoost" if hasattr(primeiro_modelo, 'iterations') else "RandomForest"
            else:
                modelo_tipo = "Não treinado"
            
            analise = f"🤖 ANÁLISE ML - {modelo_tipo.upper()} (TOP 25):\n"
            analise += f"🔄 Treinamentos realizados: {self.ml.contador_treinamento}\n"
            analise += f"📊 Próximo treinamento: {15 - self.contador_sorteios} sorteios\n"
            analise += f"📈 Ensemble: {len(self.ml.models)} modelos\n"
            
            padroes_recentes = [p for p in self.sequencias_padroes['padroes_detectados'] 
                              if len(self.historico) - p['detectado_em'] <= 20]
            
            if padroes_recentes:
                analise += f"🔍 Padrões ativos: {len(padroes_recentes)}\n"
                for padrao in padroes_recentes[-3:]:
                    idade = len(self.historico) - padrao['detectado_em']
                    analise += f"   📈 {padrao['zona']}: {padrao['tipo']} (há {idade} jogos)\n"
            
            analise += "🎯 Previsões (Top 10):\n"
            for i, (num, prob) in enumerate(previsao_ml[:10]):
                analise += f"  {i+1}. Número {num}: {prob:.2%}\n"
            
            top_25_numeros = [num for num, prob in previsao_ml[:25]]
            distribuicao = self.analisar_distribuicao_zonas(top_25_numeros)
            
            if distribuicao:
                distribuicao_ajustada = self.aplicar_padroes_na_previsao(distribuicao)
                
                analise += f"\n🎯 DISTRIBUIÇÃO POR ZONAS (25 números):\n"
                for zona, count in distribuicao_ajustada.items():
                    count_original = distribuicao[zona]
                    ajuste = count - count_original
                    simbolo_ajuste = f" (+{ajuste})" if ajuste > 0 else ""
                    analise += f"  📍 {zona}: {count_original}→{count}/25{simbolo_ajuste}\n"
                
                zona_vencedora = max(distribuicao_ajustada, key=distribuicao_ajustada.get)
                analise += f"\n💡 ZONA RECOMENDADA: {zona_vencedora}\n"
                analise += f"🎯 Confiança: {self.calcular_confianca_com_padroes(distribuicao_ajustada, zona_vencedora)}\n"
                analise += f"🔢 Números da zona: {sorted(self.numeros_zonas_ml[zona_vencedora])}\n"
                analise += f"📈 Percentual: {(distribuicao_ajustada[zona_vencedora]/25)*100:.1f}%\n"
            else:
                analise += "\n⚠️  Nenhuma zona com predominância suficiente (mínimo 7 números)\n"
            
            return analise
        else:
            return "🤖 ML: Erro na previsão"

    def get_estatisticas_padroes(self):
        if not hasattr(self, 'metricas_padroes'):
            return "📊 Métricas de padrões: Não disponível"
        
        total = self.metricas_padroes['padroes_detectados_total']
        if total == 0:
            return "📊 Métricas de padrões: Nenhum padrão validado ainda"
        
        acertos = self.metricas_padroes['padroes_acertados']
        eficiencia = (acertos / total) * 100 if total > 0 else 0
        
        estatisticas = f"📊 EFICIÊNCIA DOS PADRÕES:\n"
        estatisticas += f"✅ Padrões que acertaram: {acertos}/{total} ({eficiencia:.1f}%)\n"
        
        for tipo, dados in self.metricas_padroes['eficiencia_por_tipo'].items():
            if dados['total'] > 0:
                eff_tipo = (dados['acertos'] / dados['total']) * 100
                estatisticas += f"   🎯 {tipo}: {dados['acertos']}/{dados['total']} ({eff_tipo:.1f}%)\n"
        
        padroes_ativos = [p for p in self.sequencias_padroes['padroes_detectados'] 
                         if len(self.historico) - p['detectado_em'] <= 10]
        
        estatisticas += f"🔍 Padrões ativos: {len(padroes_ativos)}\n"
        for padrao in padroes_ativos[-3:]:
            idade = len(self.historico) - padrao['detectado_em']
            estatisticas += f"   📈 {padrao['zona']}: {padrao['tipo']} (há {idade} jogos)\n"
        
        return estatisticas

    def get_info_zonas_ml(self):
        info = {}
        for zona, numeros in self.numeros_zonas_ml.items():
            info[zona] = {
                'numeros': sorted(numeros),
                'quantidade': len(numeros),
                'central': self.zonas_ml[zona],
                'descricao': f"6 antes + 6 depois do {self.zonas_ml[zona]}"
            }
        return info

    def zerar_padroes(self):
        self.sequencias_padroes = {
            'sequencias_ativas': {},
            'historico_sequencias': [],
            'padroes_detectados': []
        }
        self.metricas_padroes = {
            'padroes_detectados_total': 0,
            'padroes_acertados': 0,
            'padroes_errados': 0,
            'eficiencia_por_tipo': {},
            'historico_validacao': []
        }
        logging.info("🔄 Padrões sequenciais e métricas zerados")

# =============================
# SISTEMA DE GESTÃO ATUALIZADO COM ROTAÇÃO AUTOMÁTICA (Zonas ↔ ML ↔ Markov ↔ Score Engine)
# =============================
class SistemaRoletaCompleto:
    def __init__(self):
        self.estrategia_zonas = EstrategiaZonasOtimizada()
        self.estrategia_midas = EstrategiaMidas()
        self.estrategia_ml = EstrategiaML()
        self.estrategia_markov = EstrategiaMarkov(ordem=2, top_k=6)
        self.estrategia_score = EstrategiaScoreEngine(top_k=12)  # NOVA ESTRATÉGIA
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.estrategia_selecionada = "Zonas"
        self.contador_sorteios_global = 0
        
        self.sequencia_erros = 0
        self.ultima_estrategia_erro = ""

    def set_estrategia(self, estrategia):
        self.estrategia_selecionada = estrategia
        salvar_sessao()

    def treinar_modelo_ml(self, historico_completo=None):
        return self.estrategia_ml.treinar_modelo_ml(historico_completo)

    def rotacionar_estrategia_automaticamente(self, acerto, nome_estrategia):
        """
        Rotação entre Zonas, ML, Markov e Score Engine:
        - Só rotaciona se a estratégia atual errar 2 vezes seguidas
        - Ordem de rotação: Zonas → ML → Markov → Score Engine → Zonas
        """
        if acerto:
            self.sequencia_erros = 0
            self.ultima_estrategia_erro = ""
            return False
        else:
            self.sequencia_erros += 1
            self.ultima_estrategia_erro = nome_estrategia
            
            if self.sequencia_erros >= 2:
                estrategia_atual = self.estrategia_selecionada
                
                # Define a ordem de rotação (incluindo Score Engine)
                if estrategia_atual == "Zonas":
                    nova_estrategia = "ML"
                    motivo = "2 erros consecutivos nas Zonas"
                elif estrategia_atual == "ML":
                    nova_estrategia = "Markov"
                    motivo = "2 erros consecutivos no ML"
                elif estrategia_atual == "Markov":
                    nova_estrategia = "ScoreEngine"
                    motivo = "2 erros consecutivos no Markov"
                elif estrategia_atual == "ScoreEngine":
                    nova_estrategia = "Zonas"
                    motivo = "2 erros consecutivos no Score Engine"
                else:
                    nova_estrategia = "Zonas"
                    motivo = "Estratégia não reconhecida, voltando para Zonas"
                
                self.estrategia_selecionada = nova_estrategia
                self.sequencia_erros = 0
                
                enviar_rotacao_automatica(estrategia_atual, nova_estrategia, motivo)
                logging.info(f"🔄 ROTAÇÃO: {estrategia_atual} → {nova_estrategia} - {motivo}")
                
                return True
            return False

    def processar_novo_numero(self, numero):
        if isinstance(numero, dict) and 'number' in numero:
            numero_real = numero['number']
            multiplicador = None
            lucky_numbers = numero.get('luckyNumbers', [])
            lucky_multipliers = numero.get('luckyMultipliers', {})
            
            if numero_real in lucky_numbers:
                multiplicador = lucky_multipliers.get(numero_real)
        else:
            numero_real = numero
            multiplicador = None
            lucky_numbers = []
            
        self.contador_sorteios_global += 1
            
        if self.previsao_ativa:
            acerto = False
            zonas_acertadas = []
            nome_estrategia = self.previsao_ativa['nome']
            numeros_apostados = self.previsao_ativa.get('numeros_apostar', [])
            
            if numero_real in numeros_apostados:
                acerto = True
                if 'Zonas' in nome_estrategia:
                    for zona, numeros in self.estrategia_zonas.numeros_zonas.items():
                        if numero_real in numeros:
                            zonas_acertadas.append(zona)
                            break
                elif 'ML' in nome_estrategia:
                    for zona, numeros in self.estrategia_ml.numeros_zonas_ml.items():
                        if numero_real in numeros:
                            zonas_acertadas.append(zona)
                            break
            
            # Atualizar estatísticas da combinação usada (apenas para estratégia Zonas)
            if 'Zonas' in nome_estrategia and 'combinacao_usada' in self.previsao_ativa:
                combinacao_usada = self.previsao_ativa['combinacao_usada']
                self.estrategia_zonas.atualizar_combinacoes_stats(combinacao_usada, acerto)
            
            # Rotação entre estratégias
            rotacionou = self.rotacionar_estrategia_automaticamente(acerto, nome_estrategia)
            
            if nome_estrategia not in self.estrategias_contador:
                self.estrategias_contador[nome_estrategia] = {'acertos': 0, 'total': 0}
            
            self.estrategias_contador[nome_estrategia]['total'] += 1
            if acerto:
                self.estrategias_contador[nome_estrategia]['acertos'] += 1
                self.acertos += 1
            else:
                self.erros += 1
            
            zona_acertada_str = "+".join(zonas_acertadas) if zonas_acertadas else None
            enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada_str, multiplicador)
            
            self.historico_desempenho.append({
                'numero': numero_real,
                'acerto': acerto,
                'estrategia': nome_estrategia,
                'previsao': numeros_apostados,
                'rotacionou': rotacionou,
                'zona_acertada': zona_acertada_str,
                'tipo_aposta': self.previsao_ativa.get('tipo', 'unica'),
                'multiplicador': multiplicador if multiplicador else None
            })
            
            self.previsao_ativa = None
        
        # Atualiza todas as estratégias com o novo número
        self.estrategia_zonas.adicionar_numero(numero_real)
        self.estrategia_midas.adicionar_numero(numero_real)
        self.estrategia_ml.adicionar_numero(numero_real)
        self.estrategia_markov.adicionar_numero(numero_real)
        self.estrategia_score.adicionar_numero(numero_real, lucky_numbers)  # NOVA
        
        nova_estrategia = None
        
        if self.estrategia_selecionada == "Zonas":
            nova_estrategia = self.estrategia_zonas.analisar_zonas()
        elif self.estrategia_selecionada == "Midas":
            nova_estrategia = self.estrategia_midas.analisar_midas()
        elif self.estrategia_selecionada == "ML":
            nova_estrategia = self.estrategia_ml.analisar_ml()
        elif self.estrategia_selecionada == "Markov":
            nova_estrategia = self.estrategia_markov.analisar_markov()
        elif self.estrategia_selecionada == "ScoreEngine":  # NOVA
            nova_estrategia = self.estrategia_score.analisar_score()
        
        if nova_estrategia:
            self.previsao_ativa = nova_estrategia
            enviar_previsao_super_simplificada(nova_estrategia)

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
        self.estrategia_score.zerar_estatisticas()  # NOVA
        
        logging.info("📊 Todas as estatísticas de desempenho foram zeradas")
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
            for resultado in reversed(ultimos_resultados):
                if not resultado['acerto']:
                    self.sequencia_erros += 1
                else:
                    break
            
            logging.info("🔄 Estatísticas recentes resetadas (mantidos últimos 10 resultados)")
        else:
            logging.info("ℹ️  Histórico muito pequeno para reset recente")
        
        salvar_sessao()

    def get_status_rotacao(self):
        return {
            'estrategia_atual': self.estrategia_selecionada,
            'sequencia_erros': self.sequencia_erros,
            'ultima_estrategia_erro': self.ultima_estrategia_erro,
            'proxima_rotacao_em': max(0, 2 - self.sequencia_erros)
        }

# =============================
# FUNÇÕES AUXILIARES
# =============================
def tocar_som_moeda():
    st.markdown("""<audio autoplay><source src="" type="audio/mp3"></audio>""", unsafe_allow_html=True)

def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    try:
        with open(caminho, "w") as f:
            json.dump(historico, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")

def extrair_numeros_raio(resultado_api):
    """Extrai os números que foram raios e seus multiplicadores"""
    numeros_raio = []
    multiplicadores = {}
    try:
        if resultado_api and isinstance(resultado_api, dict):
            data = resultado_api.get('data', {})
            result = data.get('result', {})
            lucky_numbers_list = result.get('luckyNumbersList', [])
            
            for item in lucky_numbers_list:
                numero = item.get('number')
                multiplicador = item.get('roundedMultiplier')
                if numero is not None:
                    numeros_raio.append(numero)
                    if multiplicador is not None:
                        multiplicadores[numero] = multiplicador
                    
    except Exception as e:
        logging.error(f"Erro ao extrair números de raio: {e}")
        
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
        
        return {
            "number": number, 
            "timestamp": timestamp, 
            "luckyNumbers": numeros_raio,
            "luckyMultipliers": multiplicadores
        }
    except Exception as e:
        logging.error(f"Erro ao buscar resultado: {e}")
        return None

# =============================
# APLICAÇÃO STREAMLIT ATUALIZADA
# =============================
st.set_page_config(page_title="IA Roleta — Multi-Estratégias PRO", layout="centered")
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

# Sidebar - Configurações Avançadas
st.sidebar.title("⚙️ Configurações")

with st.sidebar.expander("💾 Gerenciamento de Sessão", expanded=False):
    st.write("**Persistência de Dados**")
    
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
                st.error("❌ Nenhuma sessão salva encontrada")
    
    st.write("---")
    
    st.write("**📊 Gerenciar Estatísticas**")
    
    col3, col4 = st.columns(2)
    
    with col3:
        if st.button("🔄 Reset Recente", help="Mantém apenas os últimos 10 resultados", use_container_width=True):
            st.session_state.sistema.reset_recente_estatisticas()
            st.success("✅ Estatísticas recentes resetadas!")
            st.rerun()
            
    with col4:
        if st.button("🗑️ Zerar Tudo", type="secondary", help="Zera TODAS as estatísticas", use_container_width=True):
            if st.checkbox("Confirmar zerar TODAS as estatísticas"):
                st.session_state.sistema.zerar_estatisticas_desempenho()
                st.error("🗑️ Todas as estatísticas foram zeradas!")
                st.rerun()
    
    st.write("---")
    
    if st.button("🗑️ Limpar TODOS os Dados", type="secondary", use_container_width=True):
        if st.checkbox("Confirmar limpeza total de todos os dados"):
            limpar_sessao()
            st.error("🗑️ Todos os dados foram limpos!")
            st.stop()

with st.sidebar.expander("🔔 Configurações do Telegram", expanded=False):
    st.write("Configure as notificações do Telegram")
    
    telegram_token = st.text_input(
        "Bot Token do Telegram:",
        value=st.session_state.telegram_token,
        type="password",
        help="Obtenha com @BotFather no Telegram"
    )
    
    telegram_chat_id = st.text_input(
        "Chat ID do Telegram:",
        value=st.session_state.telegram_chat_id,
        help="Obtenha com @userinfobot no Telegram"
    )
    
    if st.button("Salvar Configurações Telegram"):
        st.session_state.telegram_token = telegram_token
        st.session_state.telegram_chat_id = telegram_chat_id
        salvar_sessao()
        st.success("✅ Configurações do Telegram salvas!")
        
    if st.button("Testar Conexão Telegram"):
        if telegram_token and telegram_chat_id:
            try:
                enviar_telegram("🔔 Teste de conexão - IA Roleta funcionando!")
                st.success("✅ Mensagem de teste enviada para Telegram!")
            except Exception as e:
                st.error(f"❌ Erro ao enviar mensagem: {e}")
        else:
            st.error("❌ Preencha token e chat ID primeiro")

with st.sidebar.expander("🔔 Alertas Alternativos", expanded=False):
    st.write("**Alertas Simplificados do Telegram**")
    
    st.info("""
    **📱 Alertas Ativados:**
    - 🔔 **Alerta de Aposta:** Números em 2 linhas
    - 📢 **Alerta de Resultado:** Confirmação simples
    - 🎯 **Previsão Detalhada:** Mensagem completa
    """)
    
    alertas_alternativos = st.checkbox(
        "Ativar Alertas Simplificados", 
        value=True,
        help="Envia alertas super simples junto com os detalhados"
    )
    
    if not alertas_alternativos:
        st.warning("⚠️ Alertas simplificados desativados")
    
    if st.button("Testar Alertas Simplificados"):
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            previsao_teste = {
                'nome': 'Zonas Teste',
                'numeros_apostar': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
                'zonas_envolvidas': ['Vermelha']
            }
            
            try:
                enviar_alerta_numeros_simplificado(previsao_teste)
                st.success("✅ Alerta simplificado de teste enviado!")
            except Exception as e:
                st.error(f"❌ Erro: {e}")
        else:
            st.error("❌ Configure o Telegram primeiro")

# Atualização do seletor de estratégias para incluir Score Engine
estrategia = st.sidebar.selectbox(
    "🎯 Selecione a Estratégia:",
    ["Zonas", "Midas", "ML", "Markov", "ScoreEngine"],
    key="estrategia_selecionada"
)

if estrategia != st.session_state.sistema.estrategia_selecionada:
    st.session_state.sistema.set_estrategia(estrategia)
    st.toast(f"🔄 Estratégia alterada para: {estrategia}")

with st.sidebar.expander("🔄 Rotação Automática", expanded=True):
    status_rotacao = st.session_state.sistema.get_status_rotacao()
    
    st.write("**Sistema de Rotação:**")
    st.write(f"🎯 **Estratégia Atual:** {status_rotacao['estrategia_atual']}")
    st.write(f"❌ **Erros Seguidos:** {status_rotacao['sequencia_erros']}/2")
    st.write(f"🔄 **Próxima Rotação em:** {status_rotacao['proxima_rotacao_em']} erro(s)")
    
    if status_rotacao['ultima_estrategia_erro']:
        st.write(f"📊 **Última Estratégia com Erro:** {status_rotacao['ultima_estrategia_erro']}")
    
    st.write("---")
    st.write("**Regras de Rotação:**")
    st.write("• ✅ **Acerto:** Continua na mesma estratégia")
    st.write("• ❌ **1 Erro:** Continua na estratégia") 
    st.write("• ❌❌ **2 Erros Seguidos:** Rotação automática")
    st.write("• 🔄 **Ordem:** Zonas → ML → Markov → ScoreEngine → Zonas")
    
    st.write("---")
    st.write("**🔄 Rotação de Combinações nas Zonas:**")
    st.write("• A cada erro, troca para a próxima combinação (ordem cíclica)")
    st.write("• Ordem: Vermelha+Azul → Vermelha+Amarela → Azul+Amarela → Volta")
    
    if st.button("🔄 Forçar Rotação Estratégia", use_container_width=True):
        estrategia_atual = st.session_state.sistema.estrategia_selecionada
        # Define a ordem de rotação (atualizada)
        if estrategia_atual == "Zonas":
            nova_estrategia = "ML"
        elif estrategia_atual == "ML":
            nova_estrategia = "Markov"
        elif estrategia_atual == "Markov":
            nova_estrategia = "ScoreEngine"
        elif estrategia_atual == "ScoreEngine":
            nova_estrategia = "Zonas"
        else:
            nova_estrategia = "Zonas"
        
        st.session_state.sistema.estrategia_selecionada = nova_estrategia
        st.session_state.sistema.sequencia_erros = 0
        st.success(f"🔄 Rotação forçada: {estrategia_atual} → {nova_estrategia}")
        st.rerun()
    
    if st.button("🔄 Reset Combinação Zonas", use_container_width=True):
        st.session_state.sistema.estrategia_zonas.indice_combinacao_atual = 0
        st.session_state.sistema.estrategia_zonas.combinacao_atual = st.session_state.sistema.estrategia_zonas.combinacoes_possiveis[0]
        st.session_state.sistema.estrategia_zonas.ultima_combinacao_erro = ""
        st.success("✅ Combinação das Zonas resetada para a primeira da lista!")
        st.rerun()

# Nova seção para configurações do Score Engine
with st.sidebar.expander("🧠 Configurações Score Engine", expanded=False):
    st.write("**Score Engine Pro**")
    st.write("Combinação ponderada de 6 fatores:")
    st.write("• 📊 Frequência (25%)")
    st.write("• 🔁 Recência (25%)")
    st.write("• 🔥 Cluster/Repetição (20%)")
    st.write("• 🎯 Vizinhança (10%)")
    st.write("• ⏳ Delay (10%)")
    st.write("• 🍀 Lucky Numbers (10%)")
    
    top_k_score = st.slider(
        "Número de previsões:",
        min_value=6,
        max_value=20,
        value=12,
        help="Quantos números com maior score retornar"
    )
    
    if st.button("Aplicar Configurações Score"):
        st.session_state.sistema.estrategia_score.top_k = top_k_score
        st.success(f"✅ Configurações Score aplicadas! (Top {top_k_score} números)")
        st.rerun()
    
    if st.button("🧹 Zerar Tracking Score", use_container_width=True):
        st.session_state.sistema.estrategia_score.zerar_estatisticas()
        st.success("✅ Histórico e tracking do Score Engine zerados!")
        st.rerun()

with st.sidebar.expander("🎲 Configurações Markov", expanded=False):
    st.write("**🎲 Cadeia de Markov**")
    
    ordem = st.selectbox(
        "Ordem da Cadeia:",
        [1, 2],
        index=1,
        help="Ordem 1: baseado no último número | Ordem 2: baseado nos últimos 2 números"
    )
    
    top_k = st.slider(
        "Número de previsões:",
        min_value=3,
        max_value=15,
        value=6,
        help="Quantos números mais prováveis retornar"
    )
    
    if st.button("Aplicar Configurações Markov"):
        st.session_state.sistema.estrategia_markov.ordem = ordem
        st.session_state.sistema.estrategia_markov.top_k = top_k
        st.session_state.sistema.estrategia_markov._inicializar_matriz()
        st.success(f"✅ Configurações Markov aplicadas! (Ordem {ordem}, Top {top_k})")
        st.rerun()
    
    st.write("---")
    st.write("**📊 Status da Matriz:**")
    estatisticas_markov = st.session_state.sistema.estrategia_markov.get_estatisticas_matriz()
    st.text(estatisticas_markov)
    
    if st.button("🔄 Zerar Matriz Markov", use_container_width=True):
        st.session_state.sistema.estrategia_markov.zerar_matriz()
        st.success("✅ Matriz de Markov zerada!")
        st.rerun()

with st.sidebar.expander("🧠 Treinamento ML", expanded=False):
    numeros_disponiveis = 0
    numeros_lista = []
    
    for item in st.session_state.historico:
        if isinstance(item, dict) and 'number' in item and item['number'] is not None:
            numeros_disponiveis += 1
            numeros_lista.append(item['number'])
        elif isinstance(item, (int, float)) and item is not None:
            numeros_disponiveis += 1
            numeros_lista.append(int(item))
            
    st.write(f"📊 **Números disponíveis:** {numeros_disponiveis}")
    st.write(f"🎯 **Mínimo necessário:** 200 números")
    st.write(f"🔄 **Treinamento automático:** A cada 15 sorteios")
    st.write(f"🤖 **Modelo:** CatBoost (mais preciso)")
    st.write(f"🎯 **Ensemble:** 3 modelos")
    
    if numeros_disponiveis > 0:
        numeros_unicos = len(set(numeros_lista))
        st.write(f"🎲 **Números únicos:** {numeros_unicos}/37")
        
        if numeros_unicos < 10:
            st.warning(f"⚠️ **Pouca variedade:** Necessário pelo menos 10 números diferentes")
        else:
            st.success(f"✅ **Variedade adequada:** {numeros_unicos} números diferentes")
    
    st.write(f"✅ **Status:** {'Dados suficientes' if numeros_disponiveis >= 200 else 'Coletando dados...'}")
    
    if numeros_disponiveis >= 200:
        st.success("✨ **Pronto para treinar!**")
        
        if st.button("🚀 Treinar Modelo ML", type="primary", use_container_width=True):
            with st.spinner("Treinando modelo ML com CatBoost... Isso pode levar alguns segundos"):
                try:
                    success, message = st.session_state.sistema.treinar_modelo_ml(numeros_lista)
                    if success:
                        st.success(f"✅ {message}")
                        st.balloons()
                    else:
                        st.error(f"❌ {message}")
                except Exception as e:
                    st.error(f"💥 Erro no treinamento: {str(e)}")
    
    else:
        st.warning(f"📥 Colete mais {200 - numeros_disponiveis} números para treinar o ML")
        
    st.write("---")
    st.write("**Status do ML:**")
    if st.session_state.sistema.estrategia_ml.ml.is_trained:
        if st.session_state.sistema.estrategia_ml.ml.models:
            primeiro_modelo = st.session_state.sistema.estrategia_ml.ml.models[0]
            modelo_tipo = "CatBoost" if hasattr(primeiro_modelo, 'iterations') else "RandomForest"
        else:
            modelo_tipo = "Não treinado"
            
        st.success(f"✅ Modelo {modelo_tipo} treinado ({st.session_state.sistema.estrategia_ml.ml.contador_treinamento} vezes)")
        if 'last_accuracy' in st.session_state.sistema.estrategia_ml.ml.meta:
            acc = st.session_state.sistema.estrategia_ml.ml.meta['last_accuracy']
            st.info(f"📊 Última acurácia: {acc:.2%}")
        st.info(f"🔄 Próximo treinamento automático em: {15 - st.session_state.sistema.estrategia_ml.contador_sorteios} sorteios")
        st.info(f"🎯 Ensemble: {len(st.session_state.sistema.estrategia_ml.ml.models)} modelos ativos")
    else:
        st.info("🤖 ML aguardando treinamento")

with st.sidebar.expander("🔍 Estatísticas de Padrões ML", expanded=False):
    if st.session_state.sistema.estrategia_selecionada == "ML":
        estatisticas_padroes = st.session_state.sistema.estrategia_ml.get_estatisticas_padroes()
        st.text(estatisticas_padroes)
        
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            if st.button("🔄 Zerar Padrões", use_container_width=True):
                st.session_state.sistema.estrategia_ml.zerar_padroes()
                st.success("✅ Padrões zerados!")
                st.rerun()
                
        with col_p2:
            if st.button("📊 Atualizar Métricas", use_container_width=True):
                st.rerun()
    else:
        st.info("🔍 Ative a estratégia ML para ver estatísticas de padrões")

with st.sidebar.expander("📊 Informações das Estratégias"):
    if estrategia == "Zonas":
        info_zonas = st.session_state.sistema.estrategia_zonas.get_info_zonas()
        st.write("**🎯 Estratégia Zonas v9 (ROTAÇÃO CÍCLICA):**")
        st.write("**CONFIGURAÇÃO:** 6 antes + 6 depois (13 números/zona)")
        st.write("**LÓGICA ATUALIZADA:**")
        st.write("- 🌊 **APOSTA NAS ONDAS:** Zonas mais frequentes nos últimos 12 sorteios")
        st.write("- 🔄 **ROTAÇÃO CÍCLICA:** Troca de combinação a cada erro (sem bloqueio)")
        st.write("- 📋 **ORDEM:** Vermelha+Azul → Vermelha+Amarela → Azul+Amarela → Volta")
        st.write("- 📊 **PESO 70% para taxa recente** (últimos 12 números)")
        st.write("- 🔥 **BÔNUS para sequências ativas** (acertos consecutivos)")
        st.write("- 🎯 **SELEÇÃO INTELIGENTE:** Máximo 15 números selecionados automaticamente")
        for zona, dados in info_zonas.items():
            st.write(f"**Zona {zona}** (Núcleo: {dados['central']})")
            st.write(f"Descrição: {dados['descricao']}")
            st.write(f"Números: {', '.join(map(str, dados['numeros']))}")
            st.write(f"Total: {dados['quantidade']} números")
            st.write("---")
    
    elif estrategia == "Midas":
        st.write("**🎯 Estratégia Midas:**")
        st.write("Padrões baseados em terminais:")
        st.write("- **Terminal 0**: 0, 10, 20, 30")
        st.write("- **Terminal 7**: 7, 17, 27") 
        st.write("- **Terminal 5**: 5, 15, 25, 35")
        st.write("---")
    
    elif estrategia == "ML":
        st.write("**🤖 Estratégia Machine Learning - CATBOOST OTIMIZADO:**")
        st.write("- **Modelo**: CatBoost (Gradient Boosting)")
        st.write("- **Ensemble**: 3 modelos (2 → 3)")
        st.write("- **Amostras mínimas**: 200 (100 → 200)")
        st.write("- **Histórico máximo**: 1000 números (500 → 1000)")
        st.write("- **Treinamento**: A cada 15 sorteios (10 → 15)")
        st.write("- **Janelas**: [3, 8, 15, 30, 60, 120] (otimizadas)")
        st.write("- **Zonas**: 6 antes + 6 depois (13 números/zona)")
        st.write("- **Threshold**: Mínimo 7 números na mesma zona")
        st.write("- **Saída**: Zona com maior concentração")
        st.write("- 🔄 **INVERSÃO AUTOMÁTICA:** Combina as 2 melhores zonas quando possível")
        st.write("- 🎯 **SELEÇÃO INTELIGENTE:** Máximo 15 números selecionados automaticamente")
        
        info_zonas_ml = st.session_state.sistema.estrategia_ml.get_info_zonas_ml()
        for zona, dados in info_zonas_ml.items():
            st.write(f"**Zona {zona}** (Núcleo: {dados['central']})")
            st.write(f"Descrição: {dados['descricao']}")
            st.write(f"Números: {', '.join(map(str, dados['numeros']))}")
            st.write(f"Total: {dados['quantidade']} números")
            st.write("---")
    
    elif estrategia == "Markov":
        st.write("**🎲 Estratégia Cadeia de Markov:**")
        st.write("- **Modelo**: Cadeia de Markov de ordem configurável")
        st.write("- **Previsão**: Top 6 números mais prováveis")
        st.write("- **Matriz de transição**: Atualizada a cada número")
        st.write("- **Vizinhança**: Ajuste por proximidade na roleta")
        st.write("- **Fallback**: Frequência quando dados insuficientes")
        st.write("- **Histórico máximo**: 200 números")
        st.write("- 🎯 **SAÍDA:** Lista dos números mais prováveis")
        st.write("- 🔄 **ROTAÇÃO:** Entra na rotação automática com Zonas, ML e Score Engine")
        
        info_markov = f"""
        **🎯 Como funciona:**
        1. Analisa sequências de números anteriores
        2. Calcula probabilidades de transição
        3. Identifica os números mais prováveis baseado no último resultado
        4. Ajusta pela vizinhança física na roleta
        """
        st.write(info_markov)
    
    elif estrategia == "ScoreEngine":
        st.write("**🧠 Estratégia Score Engine Pro:**")
        st.write("- **Modelo**: Scoring dinâmico com 6 fatores")
        st.write("- **Pesos configuráveis:**")
        st.write("  - 📊 Frequência: 25%")
        st.write("  - 🔁 Recência (últ. 20): 25%")
        st.write("  - 🔥 Cluster/Repetição: 20%")
        st.write("  - 🎯 Vizinhança física: 10%")
        st.write("  - ⏳ Delay (tempo sem sair): 10%")
        st.write("  - 🍀 Lucky Numbers: 10%")
        st.write("- **Janelas de análise:**")
        st.write("  - Recência: 20 números")
        st.write("  - Frequência: 50 números")
        st.write("  - Vizinhança: 30 números")
        st.write("- **Tracking de Lucky Numbers:** 50 registros")
        st.write("- 🎯 **SAÍDA:** Top números ranqueados por score")
        st.write("- 🔄 **ROTAÇÃO:** Entra na rotação automática")

with st.sidebar.expander(f"🔍 Análise - {estrategia}", expanded=False):
    if estrategia == "Zonas":
        analise = st.session_state.sistema.estrategia_zonas.get_analise_detalhada()
    elif estrategia == "ML":
        analise = st.session_state.sistema.estrategia_ml.get_analise_ml()
    elif estrategia == "Markov":
        analise = st.session_state.sistema.estrategia_markov.get_analise_markov()
    elif estrategia == "ScoreEngine":
        analise = st.session_state.sistema.estrategia_score.get_analise_score()
    else:
        analise = "🎯 Estratégia Midas ativa\nAnalisando padrões de terminais..."
    
    st.text(analise)

st.subheader("✍️ Inserir Sorteios")
entrada = st.text_input("Digite números (0-36) separados por espaço:")
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
        resultado_completo = resultado
        st.session_state.historico.append(resultado_completo)
        st.session_state.sistema.processar_novo_numero(resultado_completo)
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()

st.subheader("🔁 Últimos Números")
if st.session_state.historico:
    ultimos_10 = st.session_state.historico[-10:]
    numeros_formatados = []
    for item in ultimos_10:
        numero = item['number'] if isinstance(item, dict) else item
        numeros_raio = item.get('luckyNumbers', []) if isinstance(item, dict) else []
        multiplicadores = item.get('luckyMultipliers', {}) if isinstance(item, dict) else []
        
        if numero in numeros_raio:
            mult = multiplicadores.get(numero, '')
            if mult:
                numeros_formatados.append(f"⚡ **{numero}** ({mult}x)")
            else:
                numeros_formatados.append(f"⚡ **{numero}**")
        else:
            numeros_formatados.append(str(numero))
            
    st.write(" ".join(numeros_formatados))
else:
    st.write("Nenhum número registrado")

status_rotacao = st.session_state.sistema.get_status_rotacao()
col_status1, col_status2, col_status3 = st.columns(3)
with col_status1:
    st.metric("🎯 Estratégia Atual", status_rotacao['estrategia_atual'])
with col_status2:
    st.metric("❌ Erros Seguidos", f"{status_rotacao['sequencia_erros']}/2")
with col_status3:
    st.metric("🔄 Próxima Rotação", f"Em {status_rotacao['proxima_rotacao_em']} erro(s)")

st.subheader("🎯 Previsão Ativa")
sistema = st.session_state.sistema

if sistema.previsao_ativa:
    previsao = sistema.previsao_ativa
    st.success(f"**{previsao['nome']}**")
    
    if previsao.get('selecao_inteligente', False):
        st.success("🎯 **SELEÇÃO INTELIGENTE ATIVA** - 15 melhores números selecionados")
        st.info("📊 **Critérios:** Frequência + Posição + Vizinhança + Tendência")
    
    if '🌊' in previsao.get('gatilho', ''):
        st.info("🌊 **ESTRATÉGIA DE ONDAS ATIVA:** Apostando nas zonas mais frequentes")
    
    if 'Score Engine' in previsao['nome']:
        st.info("🧠 **SCORE ENGINE ATIVO:** Combinação ponderada de 6 fatores")
        if 'scores_detalhados' in previsao:
            st.write("**📊 Scores dos principais números:**")
            for num, det in list(previsao['scores_detalhados'].items())[:5]:
                st.write(f"  Nº {num}: {det['total']:.3f} (F:{det['freq']:.2f} R:{det['rec']:.2f} C:{det['cluster']:.2f})")
    
    numeros_originais = previsao.get('numeros_originais_qtd', len(previsao['numeros_apostar']))
    if numeros_originais > len(previsao['numeros_apostar']):
        st.info(f"📊 **Redução final:** {numeros_originais} → {len(previsao['numeros_apostar'])} números")
    
    if 'Zonas' in previsao['nome']:
        zonas_envolvidas = previsao.get('zonas_envolvidas', [])
        if len(zonas_envolvidas) > 1:
            zona1 = zonas_envolvidas[0]
            zona2 = zonas_envolvidas[1]
            nucleo1 = "7" if zona1 == 'Vermelha' else "10" if zona1 == 'Azul' else "2"
            nucleo2 = "7" if zona2 == 'Vermelha' else "10" if zona2 == 'Azul' else "2"
            st.write(f"**📍 Núcleos Combinados:** {nucleo1} + {nucleo2}")
            st.info("🌊 **ESTRATÉGIA DUPLA:** Investindo nas 2 zonas mais quentes")
        else:
            zona = previsao.get('zona', '')
            if zona == 'Vermelha':
                nucleo = "7"
            elif zona == 'Azul':
                nucleo = "10"
            elif zona == 'Amarela':
                nucleo = "2"
            else:
                nucleo = zona
            st.write(f"**📍 Núcleo:** {nucleo}")
            
    elif 'ML' in previsao['nome']:
        zonas_envolvidas = previsao.get('zonas_envolvidas', [])
        if len(zonas_envolvidas) > 1:
            zona1 = zonas_envolvidas[0]
            zona2 = zonas_envolvidas[1]
            nucleo1 = "7" if zona1 == 'Vermelha' else "10" if zona1 == 'Azul' else "2"
            nucleo2 = "7" if zona2 == 'Vermelha' else "10" if zona2 == 'Azul' else "2"
            st.write(f"**🤖 Núcleos Combinados:** {nucleo1} + {nucleo2}")
            st.info("🔄 **ESTRATÉGIA DUPLA:** Investindo nas 2 melhores zonas")
        else:
            zona_ml = previsao.get('zona_ml', '')
            if zona_ml == 'Vermelha':
                nucleo = "7"
            elif zona_ml == 'Azul':
                nucleo = "10"
            elif zona_ml == 'Amarela':
                nucleo = "2"
            else:
                nucleo = zona_ml
            st.write(f"**🤖 Núcleo:** {nucleo}")
    
    elif 'Markov' in previsao['nome']:
        st.write("**🎲 Cadeia de Markov - Previsão Baseada em Sequências**")
        if 'previsoes_detalhadas' in previsao:
            st.write("**📊 Probabilidades calculadas:**")
            for i, (num, prob) in enumerate(previsao['previsoes_detalhadas'][:6], 1):
                barra = "█" * int(prob * 20)
                st.write(f"  {i}. Número {num:2d}: {barra} {prob:.1%}")
        if 'estado_atual' in previsao and previsao['estado_atual']:
            if isinstance(previsao['estado_atual'], tuple):
                st.write(f"**🔍 Estado atual:** {previsao['estado_atual'][0]} → {previsao['estado_atual'][1]}")
            else:
                st.write(f"**🔍 Último número:** {previsao['estado_atual']}")
    
    elif 'Score Engine' in previsao['nome']:
        st.write("**🧠 Score Engine - Ranqueamento Inteligente**")
        if 'ranking_completo' in previsao:
            st.write("**📊 Top Scores:**")
            for i, (num, score) in enumerate(previsao['ranking_completo'][:10], 1):
                barra = "█" * int(score * 20)
                st.write(f"  {i}. Número {num:2d}: {barra} {score:.3f}")
    
    st.write(f"**🔢 Números para apostar ({len(previsao['numeros_apostar'])}):**")
    
    numeros_raio_ativos = set()
    if st.session_state.historico:
        ultimo_item = st.session_state.historico[-1]
        if isinstance(ultimo_item, dict) and 'luckyNumbers' in ultimo_item:
            numeros_raio_ativos = set(ultimo_item['luckyNumbers'])
    
    numeros_apostar_str = []
    for num in sorted(previsao['numeros_apostar']):
        if num in numeros_raio_ativos:
            numeros_apostar_str.append(f"⚡ **{num}**")
        else:
            numeros_apostar_str.append(str(num))
    
    st.write(", ".join(numeros_apostar_str))
    
    if 'ML' in previsao['nome'] and previsao.get('padroes_aplicados', 0) > 0:
        st.info(f"🔍 **Padrões aplicados:** {previsao['padroes_aplicados']} padrões sequenciais detectados")
    
    tipo_aposta = previsao.get('tipo', 'unica')
    if tipo_aposta == 'dupla':
        st.success("🎯 **APOSTA DUPLA:** Maior cobertura com 2 zonas combinadas")
    elif tipo_aposta == 'markov':
        st.success("🎲 **PREVISÃO MARKOV:** Baseada em cadeias de probabilidade")
    elif tipo_aposta == 'score_engine':
        st.success("🧠 **SCORE ENGINE:** Baseado em 6 fatores ponderados")
    else:
        st.info("🎯 **APOSTA SIMPLES:** Foco em uma zona principal")
    
    st.info("⏳ Aguardando próximo sorteio para conferência...")
else:
    st.info(f"🎲 Analisando padrões ({estrategia})...")

st.subheader("📈 Desempenho")

total = sistema.acertos + sistema.erros
taxa = (sistema.acertos / total * 100) if total > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 Acertos", sistema.acertos)
col2.metric("🔴 Erros", sistema.erros)
col3.metric("📊 Total", total)
col4.metric("✅ Taxa", f"{taxa:.1f}%")

st.write("**Gerenciar Estatísticas:**")
col5, col6 = st.columns(2)

with col5:
    if st.button("🔄 Reset Recente", help="Mantém apenas os últimos 10 resultados", use_container_width=True):
        st.session_state.sistema.reset_recente_estatisticas()
        st.success("✅ Estatísticas recentes resetadas!")
        st.rerun()

with col6:
    if st.button("🗑️ Zerar Tudo", type="secondary", help="Zera TODAS as estatísticas", use_container_width=True):
        if st.checkbox("Confirmar zerar TODAS as estatísticas"):
            st.session_state.sistema.zerar_estatisticas_desempenho()
            st.error("🗑️ Todas as estatísticas foram zeradas!")
            st.rerun()

if sistema.estrategias_contador:
    st.write("**📊 Performance por Estratégia:**")
    for nome, dados in sistema.estrategias_contador.items():
        if isinstance(dados, dict) and 'total' in dados and dados['total'] > 0:
            taxa_estrategia = (dados['acertos'] / dados['total'] * 100)
            cor = "🟢" if taxa_estrategia >= 50 else "🟡" if taxa_estrategia >= 30 else "🔴"
            st.write(f"{cor} {nome}: {dados['acertos']}/{dados['total']} ({taxa_estrategia:.1f}%)")
        else:
            st.write(f"⚠️ {nome}: Dados de performance não disponíveis")

if sistema.historico_desempenho:
    st.write("**🔍 Últimas 5 Conferências:**")
    for i, resultado in enumerate(sistema.historico_desempenho[-5:]):
        emoji = "🎉" if resultado['acerto'] else "❌"
        rotacao_emoji = " 🔄" if resultado.get('rotacionou', False) else ""
        
        mult_info = ""
        if resultado.get('multiplicador') and resultado['acerto']:
            mult_info = f" ⚡{resultado['multiplicador']}x"
        
        zona_info = ""
        if resultado['acerto'] and resultado.get('zona_acertada'):
            if '+' in resultado['zona_acertada']:
                zonas = resultado['zona_acertada'].split('+')
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
                zona_info = f" (Núcleos {nucleo_str})"
            else:
                if resultado['zona_acertada'] == 'Vermelha':
                    nucleo = "7"
                elif resultado['zona_acertada'] == 'Azul':
                    nucleo = "10"
                elif resultado['zona_acertada'] == 'Amarela':
                    nucleo = "2"
                else:
                    nucleo = resultado['zona_acertada']
                zona_info = f" (Núcleo {nucleo})"
                
        tipo_aposta_info = ""
        if resultado.get('tipo_aposta') == 'dupla':
            tipo_aposta_info = " [DUPLA]"
        elif resultado.get('tipo_aposta') == 'markov':
            tipo_aposta_info = " [MARKOV]"
        elif resultado.get('tipo_aposta') == 'score_engine':
            tipo_aposta_info = " [SCORE]"
        
        st.write(f"{emoji}{rotacao_emoji} {resultado['estrategia']}{tipo_aposta_info}: Número {resultado['numero']}{mult_info}{zona_info}")

if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        conteudo = f.read()
    st.download_button("📥 Baixar histórico", data=conteudo, file_name="historico_roleta.json")

salvar_sessao()
