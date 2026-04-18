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
from datetime import datetime

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
            'midas_historico': list(st.session_state.sistema.estrategia_midas.historico),
            'ml_historico': list(st.session_state.sistema.estrategia_ml.historico),
            'ml_contador_sorteios': st.session_state.sistema.estrategia_ml.contador_sorteios,
            'ml_sequencias_padroes': st.session_state.sistema.estrategia_ml.sequencias_padroes,
            'ml_metricas_padroes': st.session_state.sistema.estrategia_ml.metricas_padroes,
            'estrategia_selecionada': st.session_state.sistema.estrategia_selecionada,
            'historico_combinacoes': st.session_state.sistema.estrategia_zonas.historico_combinacoes,
            'ultima_combinacao': st.session_state.sistema.estrategia_zonas.ultima_combinacao,
            'erros_consecutivos_combinacao': st.session_state.sistema.estrategia_zonas.erros_consecutivos_combinacao
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
                st.session_state.sistema.estrategia_zonas.historico_combinacoes = session_data.get('historico_combinacoes', deque(maxlen=20))
                st.session_state.sistema.estrategia_zonas.ultima_combinacao = session_data.get('ultima_combinacao', None)
                st.session_state.sistema.estrategia_zonas.erros_consecutivos_combinacao = session_data.get('erros_consecutivos_combinacao', 0)
                
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
# FUNÇÃO PARA FORMATAR NÚMERO COM ESTILO
# =============================
def format_number_with_lightning(numero, is_lightning, multiplier=None):
    """Retorna HTML formatado para o número com estilo diferenciado se for raio"""
    if is_lightning:
        multiplier_text = f" x{multiplier}" if multiplier else ""
        return f'<span style="background: linear-gradient(135deg, #FFD700, #FFA500); color: #000; font-weight: bold; padding: 4px 8px; border-radius: 50%; display: inline-block; box-shadow: 0 0 10px #FFD700;" title="Número Raio!{multiplier_text}">⚡{numero}⚡</span>'
    else:
        if hasattr(st.session_state, 'hot_numbers') and numero in st.session_state.hot_numbers:
            return f'<span style="background: linear-gradient(135deg, #FF4444, #CC0000); color: white; font-weight: bold; padding: 4px 8px; border-radius: 50%; display: inline-block;" title="Número Quente">🔥{numero}🔥</span>'
        return f'<span style="background: #2c3e50; color: white; padding: 4px 8px; border-radius: 50%; display: inline-block;">{numero}</span>'

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
        elif 'Hot Numbers' in nome_estrategia:
            mensagem = f"🔥 Hot Numbers: {', '.join(map(str, sorted(numeros_apostar)[:5]))}..."
        elif 'Raios' in nome_estrategia:
            mensagem = f"⚡ Possíveis Raios: {', '.join(map(str, sorted(numeros_apostar)))}"
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
        elif 'Hot Numbers' in nome_estrategia:
            emoji = "🔥"
        elif 'Raios' in nome_estrategia:
            emoji = "⚡"
        else:
            emoji = "💰"
            
        mensagem_simplificada = f"{linha1}\n{linha2}"
        
        enviar_telegram(mensagem_simplificada)
        logging.info("🔔 Alerta simplificado enviado para Telegram")
        
    except Exception as e:
        logging.error(f"Erro ao enviar alerta simplificado: {e}")

def enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada=None, is_lightning=False, multiplier=None):
    """Envia notificação de resultado super simplificado com info de raio"""
    try:
        raio_emoji = "⚡ " if is_lightning else ""
        raio_texto = f" (RAIO! x{multiplier})" if is_lightning and multiplier else " (RAIO!)" if is_lightning else ""
        
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
                    mensagem = f"{raio_emoji}✅ Acerto Núcleos {nucleo_str}\n🎲 Número: {numero_real}{raio_texto}"
                else:
                    if zona_acertada == 'Vermelha':
                        nucleo = "7"
                    elif zona_acertada == 'Azul':
                        nucleo = "10"
                    elif zona_acertada == 'Amarela':
                        nucleo = "2"
                    else:
                        nucleo = zona_acertada
                    mensagem = f"{raio_emoji}✅ Acerto Núcleo {nucleo}\n🎲 Número: {numero_real}{raio_texto}"
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
                    mensagem = f"{raio_emoji}✅ Acerto Núcleos {nucleo_str}\n🎲 Número: {numero_real}{raio_texto}"
                else:
                    if zona_acertada == 'Vermelha':
                        nucleo = "7"
                    elif zona_acertada == 'Azul':
                        nucleo = "10"
                    elif zona_acertada == 'Amarela':
                        nucleo = "2"
                    else:
                        nucleo = zona_acertada
                    mensagem = f"{raio_emoji}✅ Acerto Núcleo {nucleo}\n🎲 Número: {numero_real}{raio_texto}"
            elif 'Hot Numbers' in nome_estrategia:
                mensagem = f"🔥✅ Acerto Hot Number!\n🎲 Número: {numero_real}{raio_texto}"
            elif 'Raios' in nome_estrategia and is_lightning:
                mensagem = f"⚡✅ ACERTOU O RAIO! x{multiplier}\n🎲 Número: {numero_real}"
            else:
                mensagem = f"{raio_emoji}✅ Acerto\n🎲 Número: {numero_real}{raio_texto}"
        else:
            mensagem = f"{raio_emoji}❌ Erro\n🎲 Número: {numero_real}{raio_texto}"
        
        if is_lightning:
            st.toast(f"⚡⚡⚡ NÚMERO RAIO! x{multiplier} ⚡⚡⚡" if multiplier else "⚡⚡⚡ NÚMERO RAIO! ⚡⚡⚡", icon="⚡")
        
        st.toast(f"🎲 Resultado", icon="✅" if acerto else "❌")
        
        if acerto:
            if is_lightning:
                st.success(f"⚡⚡⚡ {mensagem} ⚡⚡⚡")
            elif 'Hot Numbers' in nome_estrategia:
                st.success(f"🔥 {mensagem}")
            else:
                st.success(f"📢 {mensagem}")
        else:
            if is_lightning:
                st.error(f"⚡ {mensagem}")
            else:
                st.error(f"📢 {mensagem}")
        
        if 'telegram_token' in st.session_state and 'telegram_chat_id' in st.session_state:
            if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                enviar_telegram(f"📢 RESULTADO\n{mensagem}")
                enviar_alerta_conferencia_simplificado(numero_real, acerto, nome_estrategia, is_lightning, multiplier)
                
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar resultado: {e}")

def enviar_alerta_conferencia_simplificado(numero_real, acerto, nome_estrategia, is_lightning=False, multiplier=None):
    """Envia alerta de conferência super simplificado com info de raio"""
    try:
        raio_emoji = "⚡" if is_lightning else ""
        raio_texto = f" x{multiplier}" if is_lightning and multiplier else ""
        if acerto:
            mensagem = f"🎉 ACERTOU! {numero_real}{raio_emoji}{raio_texto}"
        else:
            mensagem = f"💥 ERROU! {numero_real}{raio_emoji}{raio_texto}"
            
        enviar_telegram(mensagem)
        logging.info("🔔 Alerta de conferência enviado para Telegram")
        
    except Exception as e:
        logging.error(f"Erro ao enviar alerta de conferência: {e}")

def enviar_rotacao_automatica(estrategia_anterior, estrategia_nova):
    """Envia notificação de rotação automática"""
    try:
        mensagem = f"🔄 ROTAÇÃO AUTOMÁTICA\n{estrategia_anterior} → {estrategia_nova}"
        
        st.toast("🔄 Rotação Automática", icon="🔄")
        st.warning(f"🔄 {mensagem}")
        
        if 'telegram_token' in st.session_state and 'telegram_chat_id' in st.session_state:
            if st.session_state.telegram_token and st.session_state.telegram_chat_id:
                enviar_telegram(f"🔄 ROTAÇÃO\n{mensagem}")
                
    except Exception as e:
        logging.error(f"Erro ao enviar rotação: {e}")

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
# ESTRATÉGIA DAS ZONAS CORRIGIDA - SEM PRIORIDADES, COM ROTAÇÃO POR ERROS
# =============================
class EstrategiaZonasOtimizada:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=70)
        self.nome = "Zonas Ultra Otimizada v7"
        
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
        
        # Threshold base neutro
        self.threshold_base = 22
        
        self.sistema_selecao = SistemaSelecaoInteligente()
        
        # NOVO: Sistema de rotação por combinação
        self.historico_combinacoes = deque(maxlen=20)
        self.ultima_combinacao = None
        self.erros_consecutivos_combinacao = 0

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

    def get_threshold_dinamico(self, zona):
        if zona not in self.stats_zonas:
            return self.threshold_base
        
        perf = self.stats_zonas[zona]['performance_media']
        
        # Threshold baseado na performance real da zona
        if perf > 35:
            return self.threshold_base - 2
        elif perf < 15:
            return self.threshold_base + 3
        else:
            return self.threshold_base

    def get_zonas_rankeadas(self):
        """Rankeia as zonas baseado no histórico REAL - sem prioridades"""
        if len(self.historico) < 10:
            return None
            
        zonas_score = {}
        
        for zona in self.zonas.keys():
            score = 0
            total_numeros = len(self.historico)
            
            # Frequência geral (últimos 70)
            freq_geral = sum(1 for n in self.historico if n in self.numeros_zonas[zona])
            percentual_geral = freq_geral / total_numeros if total_numeros > 0 else 0
            score += percentual_geral * 25
            
            # Curto prazo (últimos 12 - MAIS PESO)
            tamanho_curto = min(self.janelas_analise['curto_prazo'], len(self.historico))
            ultimos_curto = list(self.historico)[-tamanho_curto:]
            freq_curto = sum(1 for n in ultimos_curto if n in self.numeros_zonas[zona])
            percentual_curto = freq_curto / len(ultimos_curto) if len(ultimos_curto) > 0 else 0
            score += percentual_curto * 35
            
            # Médio prazo (últimos 24)
            tamanho_medio = min(self.janelas_analise['medio_prazo'], len(self.historico))
            ultimos_medio = list(self.historico)[-tamanho_medio:]
            freq_medio = sum(1 for n in ultimos_medio if n in self.numeros_zonas[zona])
            percentual_medio = freq_medio / len(ultimos_medio) if len(ultimos_medio) > 0 else 0
            score += percentual_medio * 15
            
            # Performance histórica da zona
            if self.stats_zonas[zona]['tentativas'] > 5:
                taxa_acerto = self.stats_zonas[zona]['performance_media']
                if taxa_acerto > 35:
                    score += 30
                elif taxa_acerto > 25:
                    score += 20
                elif taxa_acerto > 15:
                    score += 15
                else:
                    score += 8
            else:
                score += 12
            
            # Bônus para sequência atual
            sequencia = self.stats_zonas[zona]['sequencia_atual']
            if sequencia >= 2:
                score += min(sequencia * 3, 10)
            
            # Penalidade para zona que errou recentemente (evita repetição de erro)
            if hasattr(self, 'ultima_combinacao') and self.ultima_combinacao:
                if zona in self.ultima_combinacao and self.erros_consecutivos_combinacao >= 1:
                    score -= 8  # Penalidade para não repetir combinação que errou
            
            zonas_score[zona] = score
            
            logging.info(f"📊 Score {zona}: {score:.1f} (curto: {percentual_curto*100:.1f}%, perf: {self.stats_zonas[zona]['performance_media']:.1f}%)")
        
        zonas_rankeadas = sorted(zonas_score.items(), key=lambda x: x[1], reverse=True)
        return zonas_rankeadas

    def get_proxima_combinacao_diferente(self, zona_primaria, zonas_disponiveis):
        """Evita repetir a mesma combinação que errou 2 vezes"""
        if not self.ultima_combinacao or self.erros_consecutivos_combinacao < 2:
            return zona_primaria, zonas_disponiveis[1] if len(zonas_disponiveis) > 1 else None
        
        # Se a última combinação errou 2 vezes, força troca
        combinacao_anterior = sorted(self.ultima_combinacao)
        
        for i in range(len(zonas_disponiveis)):
            for j in range(i+1, len(zonas_disponiveis)):
                nova_combinacao = sorted([zonas_disponiveis[i], zonas_disponiveis[j]])
                if nova_combinacao != combinacao_anterior:
                    logging.info(f"🔄 Evitando repetição: {combinacao_anterior} → {nova_combinacao}")
                    return zonas_disponiveis[i], zonas_disponiveis[j]
        
        return zona_primaria, zonas_disponiveis[1] if len(zonas_disponiveis) > 1 else None

    def analisar_zonas_com_inversao(self):
        """Analisa zonas baseado APENAS no histórico real - sem prioridades"""
        if len(self.historico) < 10:
            return None
            
        zonas_rankeadas = self.get_zonas_rankeadas()
        if not zonas_rankeadas:
            return None
        
        zona_primaria, score_primario = zonas_rankeadas[0]
        threshold_primario = self.get_threshold_dinamico(zona_primaria)
        
        # Log para debug
        logging.info(f"🏆 Zona primária: {zona_primaria} (Score: {score_primario:.1f} >= {threshold_primario})")
        
        if score_primario < threshold_primario:
            logging.info(f"⚠️ Nenhuma zona atingiu o threshold")
            return None
        
        numeros_originais_qtd = 0
        
        # Verifica se deve usar combinação dupla
        usar_dupla = False
        zona_secundaria = None
        
        if len(zonas_rankeadas) > 1:
            zona_secundaria_candidata, score_secundario = zonas_rankeadas[1]
            threshold_secundario = threshold_primario - 6
            
            # Evita repetir combinação que errou 2 vezes
            if self.ultima_combinacao and self.erros_consecutivos_combinacao >= 2:
                # Força troca de combinação
                todas_zonas = list(self.zonas.keys())
                for i in range(len(todas_zonas)):
                    for j in range(i+1, len(todas_zonas)):
                        nova_combinacao = sorted([todas_zonas[i], todas_zonas[j]])
                        combinacao_anterior = sorted(self.ultima_combinacao)
                        if nova_combinacao != combinacao_anterior:
                            zona_primaria = todas_zonas[i]
                            zona_secundaria = todas_zonas[j]
                            usar_dupla = True
                            logging.info(f"🔄 Rotação forçada: {combinacao_anterior} → {nova_combinacao}")
                            break
                    if usar_dupla:
                        break
            else:
                # Decisão normal baseada no score
                if score_secundario >= threshold_secundario:
                    usar_dupla = True
                    zona_secundaria = zona_secundaria_candidata
                    logging.info(f"🎯 Usando combinação dupla: {zona_primaria} + {zona_secundaria}")
        
        if usar_dupla and zona_secundaria:
            numeros_primarios = self.numeros_zonas[zona_primaria]
            numeros_secundarios = self.numeros_zonas[zona_secundaria]
            
            numeros_combinados = list(set(numeros_primarios + numeros_secundarios))
            numeros_originais_qtd = len(numeros_combinados)
            
            if len(numeros_combinados) > 15:
                numeros_combinados = self.sistema_selecao.selecionar_melhores_15_numeros(
                    numeros_combinados, self.historico, "Zonas"
                )
            
            confianca_primaria = self.calcular_confianca_ultra(zona_primaria)
            confianca_secundaria = self.calcular_confianca_ultra(zona_secundaria)
            
            # Registra a combinação usada
            combinacao_atual = [zona_primaria, zona_secundaria]
            self.historico_combinacoes.append({
                'combinacao': combinacao_atual,
                'timestamp': datetime.now()
            })
            
            gatilho = f'Zona {zona_primaria} (Score: {score_primario:.1f}) + Zona {zona_secundaria} (Score: {score_secundario:.1f}) | Perf: {self.stats_zonas[zona_primaria]["performance_media"]:.1f}% | FINAL: {len(numeros_combinados)} números'
            
            return {
                'nome': f'Zonas Duplas - {zona_primaria} + {zona_secundaria}',
                'numeros_apostar': numeros_combinados,
                'gatilho': gatilho,
                'confianca': f'{confianca_primaria}+{confianca_secundaria}',
                'zona': f'{zona_primaria}+{zona_secundaria}',
                'zonas_envolvidas': [zona_primaria, zona_secundaria],
                'tipo': 'dupla',
                'selecao_inteligente': True,
                'numeros_originais_qtd': numeros_originais_qtd,
                'combinacao': combinacao_atual
            }
        
        # Aposta simples (apenas uma zona)
        numeros_apostar = self.numeros_zonas[zona_primaria]
        numeros_originais_qtd = len(numeros_apostar)
        
        if len(numeros_apostar) > 15:
            numeros_apostar = self.sistema_selecao.selecionar_melhores_15_numeros(
                numeros_apostar, self.historico, "Zonas"
            )
        
        confianca = self.calcular_confianca_ultra(zona_primaria)
        score = self.get_zona_score(zona_primaria)
        
        gatilho = f'Zona {zona_primaria} - Score: {score:.1f} | Perf: {self.stats_zonas[zona_primaria]["performance_media"]:.1f}% | Thr: {self.get_threshold_dinamico(zona_primaria)} | FINAL: {len(numeros_apostar)} números'
        
        return {
            'nome': f'Zona {zona_primaria}',
            'numeros_apostar': numeros_apostar,
            'gatilho': gatilho,
            'confianca': confianca,
            'zona': zona_primaria,
            'zonas_envolvidas': [zona_primaria],
            'tipo': 'unica',
            'selecao_inteligente': len(numeros_apostar) < len(self.numeros_zonas[zona_primaria]),
            'numeros_originais_qtd': numeros_originais_qtd,
            'combinacao': [zona_primaria]
        }

    def registrar_resultado_combinacao(self, acertou, combinacao):
        """Registra se a combinação acertou ou errou para controle de rotação"""
        if acertou:
            self.erros_consecutivos_combinacao = 0
            self.ultima_combinacao = None
        else:
            if self.ultima_combinacao == combinacao:
                self.erros_consecutivos_combinacao += 1
            else:
                self.ultima_combinacao = combinacao
                self.erros_consecutivos_combinacao = 1
            
            logging.info(f"❌ Erro na combinação {combinacao} - {self.erros_consecutivos_combinacao}/2")
        
        salvar_sessao()

    def analisar_zonas(self):
        return self.analisar_zonas_com_inversao()

    def calcular_confianca_ultra(self, zona):
        if len(self.historico) < 10:
            return 'Baixa'
            
        fatores = []
        pesos = []
        
        perf_historica = self.stats_zonas[zona]['performance_media']
        if perf_historica > 40: 
            fatores.append(3)
            pesos.append(4)
        elif perf_historica > 30: 
            fatores.append(2)
            pesos.append(4)
        elif perf_historica > 20: 
            fatores.append(2)
            pesos.append(3)
        else: 
            fatores.append(1)
            pesos.append(4)
        
        for janela_nome, tamanho in self.janelas_analise.items():
            if janela_nome != 'performance':
                historico_janela = list(self.historico)[-tamanho:] if len(self.historico) >= tamanho else list(self.historico)
                freq_janela = sum(1 for n in historico_janela if n in self.numeros_zonas[zona])
                perc_janela = (freq_janela / len(historico_janela)) * 100
                
                if perc_janela > 40: 
                    fatores.append(3)
                elif perc_janela > 25: 
                    fatores.append(2)
                else: 
                    fatores.append(1)
                pesos.append(2)
        
        sequencia = self.stats_zonas[zona]['sequencia_atual']
        if sequencia >= 3: 
            fatores.append(3)
            pesos.append(2)
        elif sequencia >= 2: 
            fatores.append(2)
            pesos.append(2)
        else: 
            fatores.append(1)
            pesos.append(2)
        
        if len(self.historico) >= 10:
            ultimos_5 = list(self.historico)[-5:]
            anteriores_5 = list(self.historico)[-10:-5]
            
            freq_ultimos = sum(1 for n in ultimos_5 if n in self.numeros_zonas[zona])
            freq_anteriores = sum(1 for n in anteriores_5 if n in self.numeros_zonas[zona]) if anteriores_5 else 0
            
            if freq_ultimos > freq_anteriores: 
                fatores.append(3)
                pesos.append(2)
            elif freq_ultimos == freq_anteriores: 
                fatores.append(2)
                pesos.append(2)
            else: 
                fatores.append(1)
                pesos.append(2)
        
        total_pontos = sum(f * p for f, p in zip(fatores, pesos))
        total_pesos = sum(pesos)
        score_confianca = total_pontos / total_pesos
        
        if score_confianca >= 2.5: 
            return 'Excelente'
        elif score_confianca >= 2.2: 
            return 'Muito Alta'
        elif score_confianca >= 1.8: 
            return 'Alta'
        elif score_confianca >= 1.5: 
            return 'Média'
        else: 
            return 'Baixa'

    def get_zona_score(self, zona):
        if len(self.historico) < 10:
            return 0
            
        score = 0
        total_numeros = len(self.historico)
        
        freq_geral = sum(1 for n in self.historico if n in self.numeros_zonas[zona])
        percentual_geral = freq_geral / total_numeros
        score += percentual_geral * 25
        
        for janela_nome, tamanho in self.janelas_analise.items():
            if janela_nome != 'performance':
                historico_janela = list(self.historico)[-tamanho:] if total_numeros >= tamanho else list(self.historico)
                freq_janela = sum(1 for n in historico_janela if n in self.numeros_zonas[zona])
                percentual_janela = freq_janela / len(historico_janela)
                peso = 35 if janela_nome == 'curto_prazo' else 15
                score += percentual_janela * peso
        
        if self.stats_zonas[zona]['tentativas'] > 5:
            taxa_acerto = self.stats_zonas[zona]['performance_media']
            if taxa_acerto > 35: 
                score += 30
            elif taxa_acerto > 25: 
                score += 20
            elif taxa_acerto > 15: 
                score += 15
            else: 
                score += 8
        else:
            score += 12
        
        sequencia = self.stats_zonas[zona]['sequencia_atual']
        if sequencia >= 2:
            score += min(sequencia * 3, 10)
            
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
        
        analise = "🎯 ANÁLISE EM TEMPO REAL - ZONAS v7\n"
        analise += "=" * 55 + "\n"
        analise += "🔧 CONFIGURAÇÃO: 6 antes + 6 depois (13 números/zona)\n"
        analise += "📊 LEITURA DO HISTÓRICO REAL - SEM PRIORIDADES\n"
        analise += "🔄 ROTAÇÃO: 2 erros seguidos na mesma combinação\n"
        analise += f"📊 JANELAS: Curto({self.janelas_analise['curto_prazo']}) Médio({self.janelas_analise['medio_prazo']}) Longo({self.janelas_analise['longo_prazo']})\n"
        analise += "=" * 55 + "\n"
        
        analise += "📊 PERFORMANCE ATUAL:\n"
        for zona in self.zonas.keys():
            tentativas = self.stats_zonas[zona]['tentativas']
            acertos = self.stats_zonas[zona]['acertos']
            taxa = self.stats_zonas[zona]['performance_media']
            sequencia = self.stats_zonas[zona]['sequencia_atual']
            seq_maxima = self.stats_zonas[zona]['sequencia_maxima']
            threshold = self.get_threshold_dinamico(zona)
            
            analise += f"📍 {zona}: {acertos}/{tentativas} → {taxa:.1f}% | Seq: {sequencia} | Máx: {seq_maxima} | Thr: {threshold}\n"
        
        analise += "\n📈 FREQUÊNCIA ATUAL:\n"
        for zona in self.zonas.keys():
            freq_total = sum(1 for n in self.historico if isinstance(n, (int, float)) and n in self.numeros_zonas[zona])
            perc_total = (freq_total / len(self.historico)) * 100
            
            freq_curto = sum(1 for n in list(self.historico)[-self.janelas_analise['curto_prazo']:] if n in self.numeros_zonas[zona])
            perc_curto = (freq_curto / min(self.janelas_analise['curto_prazo'], len(self.historico))) * 100
            
            score = self.get_zona_score(zona)
            analise += f"📍 {zona}: Total:{freq_total}/{len(self.historico)}({perc_total:.1f}%) | Curto:{freq_curto}/{self.janelas_analise['curto_prazo']}({perc_curto:.1f}%) | Score: {score:.1f}\n"
        
        # Mostra status da rotação
        if self.ultima_combinacao and self.erros_consecutivos_combinacao > 0:
            analise += f"\n🔄 STATUS ROTAÇÃO:\n"
            analise += f"   Última combinação: {' + '.join(self.ultima_combinacao)}\n"
            analise += f"   Erros seguidos: {self.erros_consecutivos_combinacao}/2\n"
            if self.erros_consecutivos_combinacao >= 2:
                analise += f"   ⚠️ PRÓXIMA APOSTA SERÁ EM COMBINAÇÃO DIFERENTE!\n"
        
        zona_recomendada = None
        zonas_rankeadas = self.get_zonas_rankeadas()
        if zonas_rankeadas:
            zona_recomendada = zonas_rankeadas[0][0]
            
        if zona_recomendada:
            analise += f"\n💡 ZONA MAIS FORTE NO MOMENTO: {zona_recomendada}\n"
            analise += f"🎯 Números: {sorted(self.numeros_zonas[zona_recomendada])}\n"
            analise += f"📈 Confiança: {self.calcular_confianca_ultra(zona_recomendada)}\n"
            analise += f"🔥 Score: {self.get_zona_score(zona_recomendada):.1f}\n"
            analise += f"🎯 Threshold: {self.get_threshold_dinamico(zona_recomendada)}\n"
            
            if len(zonas_rankeadas) > 1:
                segunda_zona = zonas_rankeadas[1][0]
                analise += f"\n💡 SEGUNDA ZONA: {segunda_zona} (Score: {zonas_rankeadas[1][1]:.1f})\n"
                if self.erros_consecutivos_combinacao < 2:
                    analise += f"🎯 COMBINAÇÃO SUGERIDA: {zona_recomendada} + {segunda_zona}\n"
                else:
                    analise += f"⚠️ EVITAR combinação anterior: {' + '.join(self.ultima_combinacao)}\n"
        else:
            analise += "\n⚠️ AGUARDAR: Nenhuma zona com confiança suficiente\n"
        
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
        self.historico_combinacoes = deque(maxlen=20)
        self.ultima_combinacao = None
        self.erros_consecutivos_combinacao = 0
        logging.info("📊 Estatísticas das Zonas zeradas")

# =============================
# ESTRATÉGIA HOT NUMBERS
# =============================
class EstrategiaHotNumbers:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico = deque(maxlen=200)
        self.numeros_hot = []
        self.numeros_cold = []
        self.janela_analise = 30
        self.frequencias = {}
        
    def adicionar_numero(self, numero):
        self.historico.append(numero)
        self.atualizar_hot_numbers()
        
    def atualizar_hot_numbers(self):
        if len(self.historico) < self.janela_analise:
            return
            
        historico_lista = list(self.historico)[-self.janela_analise:]
        self.frequencias = Counter(historico_lista)
        
        total_sorteios = len(historico_lista)
        media_esperada = total_sorteios / 37
        
        limiar_hot = max(2, int(media_esperada + 1))
        
        self.numeros_hot = [num for num, count in self.frequencias.items() if count >= limiar_hot]
        self.numeros_hot.sort(key=lambda x: self.frequencias.get(x, 0), reverse=True)
        
        todos_numeros = set(range(37))
        numeros_sorteados = set(historico_lista)
        self.numeros_cold = list(todos_numeros - numeros_sorteados)
    
    def get_vizinhos_completos(self, numero, quantidade=4):
        if numero not in self.roleta.race:
            return [numero]
        
        posicao = self.roleta.race.index(numero)
        vizinhos = []
        
        for offset in range(-quantidade, 0):
            vizinho = self.roleta.race[(posicao + offset) % len(self.roleta.race)]
            vizinhos.append(vizinho)
        
        vizinhos.append(numero)
        
        for offset in range(1, quantidade + 1):
            vizinho = self.roleta.race[(posicao + offset) % len(self.roleta.race)]
            vizinhos.append(vizinho)
        
        return vizinhos
    
    def analisar_hot_numbers(self):
        if len(self.historico) < 15:
            return None
            
        if not self.numeros_hot:
            return None
        
        top_hot = self.numeros_hot[:5]
        
        numeros_com_vizinhos = set()
        numeros_originais = []
        
        for hot_num in top_hot:
            vizinhos = self.get_vizinhos_completos(hot_num, quantidade=4)
            for v in vizinhos:
                numeros_com_vizinhos.add(v)
            numeros_originais.append({
                'numero': hot_num,
                'frequencia': self.frequencias.get(hot_num, 0),
                'vizinhos': vizinhos
            })
        
        numeros_apostar = sorted(list(numeros_com_vizinhos))
        
        numeros_originais_qtd = len(numeros_apostar)
        if len(numeros_apostar) > 15:
            numeros_apostar = sorted(numeros_apostar, key=lambda x: self.frequencias.get(x, 0), reverse=True)[:15]
        
        info_hot = []
        for hot in numeros_originais[:3]:
            info_hot.append(f"{hot['numero']} ({hot['frequencia']}x nos últimos {self.janela_analise})")
        
        confianca = self.calcular_confianca(top_hot)
        
        gatilho = f'🔥 {len(self.numeros_hot)} Hot Numbers | Top: {", ".join(map(str, top_hot[:3]))}'
        
        return {
            'nome': 'Hot Numbers',
            'numeros_apostar': numeros_apostar,
            'gatilho': gatilho,
            'confianca': confianca,
            'tipo': 'hot_numbers',
            'selecao_inteligente': len(numeros_apostar) < numeros_originais_qtd,
            'numeros_originais_qtd': numeros_originais_qtd,
            'hot_numbers': top_hot,
            'info_hot': info_hot
        }
    
    def calcular_confianca(self, top_hot):
        if not top_hot:
            return 'Baixa'
        
        maior_freq = self.frequencias.get(top_hot[0], 0)
        total_sorteios = len(self.historico[-self.janela_analise:])
        media_esperada = total_sorteios / 37
        
        ratio = maior_freq / media_esperada if media_esperada > 0 else 0
        
        if ratio >= 4:
            return 'Excelente'
        elif ratio >= 3:
            return 'Muito Alta'
        elif ratio >= 2:
            return 'Alta'
        elif ratio >= 1.5:
            return 'Média'
        else:
            return 'Baixa'
    
    def analisar_cold_numbers(self):
        if len(self.historico) < 30:
            return None
            
        if not self.numeros_cold:
            return None
        
        historico_total = list(self.historico)
        freq_total = Counter(historico_total)
        
        cold_priorizados = sorted(self.numeros_cold, key=lambda x: freq_total.get(x, 0), reverse=True)
        top_cold = cold_priorizados[:3]
        
        if top_cold:
            numeros_com_vizinhos = set()
            for cold_num in top_cold:
                vizinhos = self.get_vizinhos_completos(cold_num, quantidade=3)
                for v in vizinhos:
                    numeros_com_vizinhos.add(v)
            
            numeros_apostar = sorted(list(numeros_com_vizinhos))[:12]
            
            return {
                'nome': 'Cold Numbers (Atrasados)',
                'numeros_apostar': numeros_apostar,
                'gatilho': f'❄️ {len(self.numeros_cold)} números atrasados | Top: {", ".join(map(str, top_cold))}',
                'confianca': 'Média',
                'tipo': 'cold_numbers'
            }
        return None

# =============================
# ESTRATÉGIA DE RAIOS
# =============================
class EstrategiaRaios:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.historico_raios = deque(maxlen=200)
        self.multipliers = []
        self.estatisticas_raios = {}
        self.historico_completo = deque(maxlen=200)
        
    def adicionar_numero_normal(self, numero):
        self.historico_completo.append({
            'numero': numero,
            'is_lightning': False,
            'timestamp': datetime.now()
        })
        
    def adicionar_raio(self, numero, multiplier):
        self.historico_raios.append({
            'numero': numero,
            'multiplier': multiplier,
            'timestamp': datetime.now()
        })
        self.historico_completo.append({
            'numero': numero,
            'is_lightning': True,
            'multiplier': multiplier,
            'timestamp': datetime.now()
        })
        self.multipliers.append(multiplier)
        
        if numero not in self.estatisticas_raios:
            self.estatisticas_raios[numero] = {'total': 0, 'multipliers': [], 'ultima_vez': None}
        self.estatisticas_raios[numero]['total'] += 1
        self.estatisticas_raios[numero]['multipliers'].append(multiplier)
        self.estatisticas_raios[numero]['ultima_vez'] = datetime.now()
    
    def get_vizinhos_completos(self, numero, quantidade=2):
        if numero not in self.roleta.race:
            return [numero]
        
        posicao = self.roleta.race.index(numero)
        vizinhos = []
        
        for offset in range(-quantidade, 0):
            vizinho = self.roleta.race[(posicao + offset) % len(self.roleta.race)]
            vizinhos.append(vizinho)
        
        vizinhos.append(numero)
        
        for offset in range(1, quantidade + 1):
            vizinho = self.roleta.race[(posicao + offset) % len(self.roleta.race)]
            vizinhos.append(vizinho)
        
        return vizinhos
    
    def calcular_atraso_medio(self):
        if len(self.historico_raios) < 5:
            return 0
        
        total_sorteios = len(self.historico_completo)
        total_raios = len(self.historico_raios)
        
        if total_raios > 0:
            return total_sorteios / total_raios
        return 0
    
    def analisar_raios(self):
        if len(self.historico_raios) < 5:
            return None
        
        todos_numeros = set(range(37))
        numeros_que_foram_raio = set([r['numero'] for r in self.historico_raios])
        numeros_nunca_raio = list(todos_numeros - numeros_que_foram_raio)
        
        atraso_por_numero = {}
        for num in range(37):
            ultimo_raio = None
            for r in reversed(self.historico_raios):
                if r['numero'] == num:
                    ultimo_raio = r['timestamp']
                    break
            
            if ultimo_raio:
                sorteios_desde_ultimo = 0
                for evento in reversed(self.historico_completo):
                    if evento.get('timestamp') and ultimo_raio and evento['timestamp'] > ultimo_raio:
                        sorteios_desde_ultimo += 1
                    elif evento.get('timestamp') and ultimo_raio and evento['timestamp'] <= ultimo_raio:
                        break
                atraso_por_numero[num] = sorteios_desde_ultimo
            else:
                atraso_por_numero[num] = len(self.historico_completo)
        
        atraso_medio = self.calcular_atraso_medio()
        limiar_atraso = max(atraso_medio * 1.5, 10)
        
        numeros_atrasados = [num for num, atraso in atraso_por_numero.items() if atraso >= limiar_atraso]
        
        ultimos_10_raios = [r['numero'] for r in list(self.historico_raios)[-10:]]
        contagem_recente = Counter(ultimos_10_raios)
        numeros_repetidos = [num for num, count in contagem_recente.items() if count >= 2]
        
        medias_multipliers = {}
        for num, dados in self.estatisticas_raios.items():
            if dados['multipliers']:
                medias_multipliers[num] = sum(dados['multipliers']) / len(dados['multipliers'])
        
        top_multipliers = sorted(medias_multipliers.items(), key=lambda x: x[1], reverse=True)[:3]
        
        candidatos = []
        
        if numeros_nunca_raio:
            candidatos.extend(numeros_nunca_raio[:3])
        
        if numeros_atrasados and len(candidatos) < 5:
            candidatos.extend(numeros_atrasados[:2])
        
        if numeros_repetidos and len(candidatos) < 5:
            candidatos.extend(numeros_repetidos[:1])
        
        candidatos = list(dict.fromkeys(candidatos))[:5]
        
        if candidatos:
            numeros_com_vizinhos = set()
            for candidato in candidatos:
                vizinhos = self.get_vizinhos_completos(candidato, quantidade=2)
                for v in vizinhos:
                    numeros_com_vizinhos.add(v)
            
            numeros_apostar = sorted(list(numeros_com_vizinhos))[:12]
            
            confianca = self.calcular_confianca(candidatos, numeros_atrasados, numeros_nunca_raio)
            
            return {
                'nome': 'Estratégia de Raios',
                'numeros_apostar': numeros_apostar,
                'gatilho': self.gerar_gatilho(candidatos, numeros_atrasados, numeros_nunca_raio, atraso_medio),
                'confianca': confianca,
                'tipo': 'raios',
                'candidatos': candidatos
            }
        return None
    
    def calcular_confianca(self, candidatos, atrasados, nunca_raio):
        score = 0
        
        nunca_em_candidatos = sum(1 for c in candidatos if c in nunca_raio)
        if nunca_em_candidatos >= 2:
            score += 50
        elif nunca_em_candidatos >= 1:
            score += 30
        
        atrasados_em_candidatos = sum(1 for c in candidatos if c in atrasados)
        if atrasados_em_candidatos >= 2:
            score += 30
        elif atrasados_em_candidatos >= 1:
            score += 15
        
        if len(candidatos) <= 3:
            score += 20
        elif len(candidatos) <= 4:
            score += 10
        
        if score >= 80:
            return 'Excelente'
        elif score >= 60:
            return 'Muito Alta'
        elif score >= 40:
            return 'Alta'
        elif score >= 25:
            return 'Média'
        else:
            return 'Baixa'
    
    def gerar_gatilho(self, candidatos, atrasados, nunca_raio, atraso_medio):
        partes = []
        
        nunca_sel = [c for c in candidatos if c in nunca_raio]
        if nunca_sel:
            partes.append(f"🚨 {len(nunca_sel)} números NUNCA foram raio")
        
        atrasados_sel = [c for c in candidatos if c in atrasados]
        if atrasados_sel:
            partes.append(f"⏰ {len(atrasados_sel)} números atrasados")
        
        if not partes:
            partes.append(f"🎲 {len(candidatos)} candidatos")
        
        return f"⚡ {' | '.join(partes)}"

# =============================
# MÓDULO DE MACHINE LEARNING (RESUMIDO)
# =============================
class MLRoletaOtimizada:
    def __init__(self, roleta_obj, min_training_samples=200, max_history=1000, retrain_every_n=15, seed=42):
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

    def treinar_modelo(self, historico_completo, force_retrain=False, balance=True):
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
                    X_scaled, y, test_size=0.2, random_state=self.seed, stratify=y if can_stratify else None
                )
            except Exception as e:
                logging.warning(f"Erro no split: {e}")
                X_train, X_val, y_train, y_val = train_test_split(X_scaled, y, test_size=0.2, random_state=self.seed)

            if balance and len(X_train) > 0:
                try:
                    df_train = pd.DataFrame(X_train, columns=[f"f{i}" for i in range(X_train.shape[1])])
                    df_train['y'] = y_train
                    value_counts = df_train['y'].value_counts()
                    max_count = value_counts.max()
                    if len(value_counts) >= 2:
                        frames = []
                        for cls, grp in df_train.groupby('y'):
                            if len(grp) < max_count:
                                min_samples = max(5, max_count // 3)
                                n_samples = min(max_count, min_samples)
                                grp_up = resample(grp, replace=True, n_samples=n_samples, random_state=self.seed)
                                frames.append(grp_up)
                            else:
                                frames.append(grp)
                        if frames:
                            df_bal = pd.concat(frames)
                            y_train = df_bal['y'].values
                            X_train = df_bal.drop(columns=['y']).values
                except Exception as e:
                    logging.warning(f"Erro no balanceamento: {e}")

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
            except Exception as e:
                logging.warning(f"Falha ao salvar modelos: {e}")

            return True, f"Ensemble treinado ({', '.join(model_names)}) com {len(X)} amostras. Acurácia: {acc:.2%}"
        except Exception as e:
            logging.error(f"[treinar_modelo] Erro: {e}")
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

    def prever_proximo_numero(self, historico, top_k=25):
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

    def registrar_resultado(self, historico, previsao_top, resultado_real):
        try:
            hit = resultado_real in [p for p,_ in previsao_top] if isinstance(previsao_top[0], tuple) else resultado_real in previsao_top
            log_entry = {'prev_top': previsao_top, 'resultado': resultado_real, 'hit': bool(hit)}
            self.meta.setdefault('history_feedback', []).append(log_entry)
            recent = self.meta['history_feedback'][-10:]
            hits = sum(1 for r in recent if r['hit'])
            if len(recent) >= 5 and hits / len(recent) < 0.25:
                self.treinar_modelo(historico, force_retrain=True, balance=True)
            return True
        except Exception as e:
            logging.error(f"[registrar_resultado] Erro: {e}")
            return False

    def verificar_treinamento_automatico(self, historico_completo):
        try:
            n = len(historico_completo)
            if n >= self.min_training_samples and n % self.retrain_every_n == 0:
                return self.treinar_modelo(historico_completo)
            return False, "Aguardando próximo ciclo de treinamento"
        except Exception as e:
            return False, f"Erro ao verificar retrain: {e}"

    def resumo_meta(self):
        return {"is_trained": self.is_trained, "contador_treinamento": self.contador_treinamento, "meta": self.meta}

# =============================
# ESTRATÉGIA MIDAS
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
# ESTRATÉGIA ML
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
            self.validar_padrao_acerto(numero, self.get_previsao_atual())
        
        self.analisar_padroes_sequenciais(numero)
        
        if self.contador_sorteios >= 15:
            self.contador_sorteios = 0
            self.treinar_automatico()
            
        if 'sistema' in st.session_state:
            salvar_sessao()

    def get_previsao_atual(self):
        try:
            return self.analisar_ml()
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
        mapa_confianca = {'Muito Baixa': 0.3, 'Baixa': 0.5, 'Média': 0.65, 'Alta': 0.8, 'Muito Alta': 0.9}
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
        return sorted(contagem_zonas.items(), key=lambda x: x[1], reverse=True)

    def analisar_ml_com_inversao(self):
        if len(self.historico) < 10 or not self.ml.is_trained:
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
            
            if len(zonas_rankeadas_ajustadas) > 1:
                zona_secundaria, contagem_secundaria = zonas_rankeadas_ajustadas[1]
                if contagem_secundaria >= 5:
                    numeros_primarios = self.numeros_zonas_ml[zona_primaria]
                    numeros_secundarios = self.numeros_zonas_ml[zona_secundaria]
                    numeros_combinados = list(set(numeros_primarios + numeros_secundarios))
                    if len(numeros_combinados) > 15:
                        numeros_combinados = self.sistema_selecao.selecionar_melhores_15_numeros(
                            numeros_combinados, self.historico, "ML"
                        )
                    confianca = self.calcular_confianca_com_padroes(distribuicao_ajustada, zona_primaria)
                    return {
                        'nome': 'Machine Learning - CatBoost (Duplo)',
                        'numeros_apostar': numeros_combinados,
                        'gatilho': f'ML CatBoost - Zona {zona_primaria} + {zona_secundaria}',
                        'confianca': confianca,
                        'zona_ml': f'{zona_primaria}+{zona_secundaria}',
                        'zonas_envolvidas': [zona_primaria, zona_secundaria],
                        'tipo': 'dupla'
                    }
            
            numeros_zona = self.numeros_zonas_ml[zona_primaria]
            if len(numeros_zona) > 15:
                numeros_zona = self.sistema_selecao.selecionar_melhores_15_numeros(
                    numeros_zona, self.historico, "ML"
                )
            confianca = self.calcular_confianca_com_padroes(distribuicao_ajustada, zona_primaria)
            return {
                'nome': 'Machine Learning - CatBoost',
                'numeros_apostar': numeros_zona,
                'gatilho': f'ML CatBoost - Zona {zona_primaria}',
                'confianca': confianca,
                'zona_ml': zona_primaria,
                'zonas_envolvidas': [zona_primaria],
                'tipo': 'unica'
            }
        return None

    def analisar_ml(self):
        return self.analisar_ml_com_inversao()

    def treinar_automatico(self):
        historico_numeros = self.extrair_numeros_historico()
        if len(historico_numeros) >= self.ml.min_training_samples:
            try:
                self.ml.treinar_modelo(historico_numeros)
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

    def calcular_confianca_zona_ml(self, distribuicao):
        percentual = (distribuicao['contagem'] / distribuicao['total_zonas']) * 100
        if percentual >= 50: return 'Muito Alta'
        elif percentual >= 40: return 'Alta'
        elif percentual >= 30: return 'Média'
        elif percentual >= 25: return 'Baixa'
        else: return 'Muito Baixa'

    def treinar_modelo_ml(self, historico_completo=None):
        if historico_completo is not None:
            historico_numeros = historico_completo
        else:
            historico_numeros = self.extrair_numeros_historico()
        if len(historico_numeros) >= self.ml.min_training_samples:
            return self.ml.treinar_modelo(historico_numeros)
        return False, f"Histórico insuficiente: {len(historico_numeros)}/{self.ml.min_training_samples}"

    def get_analise_ml(self):
        if not self.ml.is_trained:
            return "🤖 ML: Modelo não treinado"
        if len(self.historico) < 10:
            return "🤖 ML: Aguardando mais dados"
        return "🤖 ML: Análise disponível na previsão"

    def get_estatisticas_padroes(self):
        total = self.metricas_padroes['padroes_detectados_total']
        if total == 0:
            return "📊 Nenhum padrão validado ainda"
        acertos = self.metricas_padroes['padroes_acertados']
        eficiencia = (acertos / total) * 100
        return f"📊 Padrões: {acertos}/{total} ({eficiencia:.1f}%)"

    def get_info_zonas_ml(self):
        info = {}
        for zona, numeros in self.numeros_zonas_ml.items():
            info[zona] = {'numeros': sorted(numeros), 'quantidade': len(numeros), 'central': self.zonas_ml[zona]}
        return info

    def zerar_padroes(self):
        self.sequencias_padroes = {'sequencias_ativas': {}, 'historico_sequencias': [], 'padroes_detectados': []}
        self.metricas_padroes = {'padroes_detectados_total': 0, 'padroes_acertados': 0, 'padroes_errados': 0, 'eficiencia_por_tipo': {}, 'historico_validacao': []}

# =============================
# SISTEMA DE GESTÃO COM ROTAÇÃO AUTOMÁTICA
# =============================
class SistemaRoletaCompleto:
    def __init__(self):
        self.estrategia_zonas = EstrategiaZonasOtimizada()
        self.estrategia_midas = EstrategiaMidas()
        self.estrategia_ml = EstrategiaML()
        self.estrategia_hot = EstrategiaHotNumbers()
        self.estrategia_raios = EstrategiaRaios()
        
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
        if acerto:
            self.sequencia_erros = 0
            self.ultima_estrategia_erro = ""
            return False
        else:
            self.sequencia_erros += 1
            self.ultima_estrategia_erro = nome_estrategia
            
            if self.sequencia_erros >= 2:
                estrategia_atual = self.estrategia_selecionada
                if estrategia_atual == "Zonas":
                    nova_estrategia = "ML"
                elif estrategia_atual == "ML":
                    nova_estrategia = "Hot Numbers"
                elif estrategia_atual == "Hot Numbers":
                    nova_estrategia = "Raios"
                elif estrategia_atual == "Raios":
                    nova_estrategia = "Zonas"
                else:
                    nova_estrategia = "Zonas"
                
                self.estrategia_selecionada = nova_estrategia
                self.sequencia_erros = 0
                enviar_rotacao_automatica(estrategia_atual, nova_estrategia)
                return True
            return False

    def processar_novo_numero(self, numero, is_lightning=False, multiplier=None):
        if isinstance(numero, dict) and 'number' in numero:
            numero_real = numero['number']
        else:
            numero_real = numero
            
        self.contador_sorteios_global += 1
            
        if is_lightning and multiplier:
            self.estrategia_raios.adicionar_raio(numero_real, multiplier)
        else:
            self.estrategia_raios.adicionar_numero_normal(numero_real)
        
        self.estrategia_hot.adicionar_numero(numero_real)
        
        if self.previsao_ativa:
            acerto = False
            zonas_acertadas = []
            nome_estrategia = self.previsao_ativa['nome']
            numeros_apostados = self.previsao_ativa.get('numeros_apostar', [])
            combinacao_atual = self.previsao_ativa.get('combinacao', None)
            
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
            
            # Registra resultado da combinação para rotação
            if 'Zonas' in nome_estrategia and combinacao_atual:
                self.estrategia_zonas.registrar_resultado_combinacao(acerto, combinacao_atual)
            
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
            enviar_resultado_super_simplificado(numero_real, acerto, nome_estrategia, zona_acertada_str, is_lightning, multiplier)
            
            self.historico_desempenho.append({
                'numero': numero_real,
                'acerto': acerto,
                'estrategia': nome_estrategia,
                'previsao': numeros_apostados,
                'rotacionou': rotacionou,
                'zona_acertada': zona_acertada_str,
                'tipo_aposta': self.previsao_ativa.get('tipo', 'unica'),
                'is_lightning': is_lightning,
                'multiplier': multiplier,
                'combinacao': combinacao_atual
            })
            
            self.previsao_ativa = None
        
        self.estrategia_zonas.adicionar_numero(numero_real)
        self.estrategia_midas.adicionar_numero(numero_real)
        self.estrategia_ml.adicionar_numero(numero_real)
        
        nova_estrategia = None
        
        if self.estrategia_selecionada == "Zonas":
            nova_estrategia = self.estrategia_zonas.analisar_zonas()
        elif self.estrategia_selecionada == "Midas":
            nova_estrategia = self.estrategia_midas.analisar_midas()
        elif self.estrategia_selecionada == "ML":
            nova_estrategia = self.estrategia_ml.analisar_ml()
        elif self.estrategia_selecionada == "Hot Numbers":
            nova_estrategia = self.estrategia_hot.analisar_hot_numbers()
            if not nova_estrategia:
                nova_estrategia = self.estrategia_hot.analisar_cold_numbers()
        elif self.estrategia_selecionada == "Raios":
            nova_estrategia = self.estrategia_raios.analisar_raios()
        
        if not nova_estrategia and self.estrategia_selecionada not in ["Hot Numbers", "Raios"]:
            nova_estrategia = self.estrategia_hot.analisar_hot_numbers()
        
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
        salvar_sessao()

    def reset_recente_estatisticas(self):
        if len(self.historico_desempenho) > 10:
            self.historico_desempenho = self.historico_desempenho[-10:]
            self.acertos = sum(1 for r in self.historico_desempenho if r['acerto'])
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
        lucky_numbers_list = result.get("luckyNumbersList", [])
        lightning_multiplier = result.get("lightningMultiplier", 100)
        lightning_dict = {}
        for item in lucky_numbers_list:
            num = item.get("number")
            multiplier = item.get("roundedMultiplier", lightning_multiplier)
            if num is not None:
                lightning_dict[num] = multiplier
        is_lightning = number in lightning_dict if number is not None else False
        multiplier = lightning_dict.get(number) if is_lightning else None
        return {
            "number": number, "timestamp": timestamp, "lightning_numbers": list(lightning_dict.keys()),
            "lightning_multipliers": lightning_dict, "is_lightning": is_lightning, "multiplier": multiplier
        }
    except Exception as e:
        logging.error(f"Erro ao buscar resultado: {e}")
        return None

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="IA Roleta — Multi-Estratégias", layout="centered")
st.title("🔥⚡🎯 IA Roleta — Sistema Multi-Estratégias 🔥⚡🎯")

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
        if st.button("🗑️ Zerar Tudo", type="secondary", use_container_width=True):
            if st.checkbox("Confirmar zerar TODAS as estatísticas"):
                st.session_state.sistema.zerar_estatisticas_desempenho()
                st.error("🗑️ Todas as estatísticas foram zeradas!")
                st.rerun()
    st.write("---")
    if st.button("🗑️ Limpar TODOS os Dados", type="secondary", use_container_width=True):
        if st.checkbox("Confirmar limpeza total"):
            limpar_sessao()
            st.stop()

with st.sidebar.expander("🔔 Configurações do Telegram", expanded=False):
    st.write("Configure as notificações do Telegram")
    telegram_token = st.text_input("Bot Token:", value=st.session_state.telegram_token, type="password")
    telegram_chat_id = st.text_input("Chat ID:", value=st.session_state.telegram_chat_id)
    if st.button("Salvar"):
        st.session_state.telegram_token = telegram_token
        st.session_state.telegram_chat_id = telegram_chat_id
        salvar_sessao()
        st.success("✅ Salvo!")
    if st.button("Testar"):
        if telegram_token and telegram_chat_id:
            enviar_telegram("🔔 Teste de conexão!")
            st.success("✅ Teste enviado!")

with st.sidebar.expander("🔔 Alertas", expanded=False):
    if st.button("Testar Alertas"):
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            previsao_teste = {'nome': 'Zonas Teste', 'numeros_apostar': [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15], 'zonas_envolvidas': ['Vermelha']}
            enviar_alerta_numeros_simplificado(previsao_teste)
            st.success("✅ Teste enviado!")

estrategia = st.sidebar.selectbox("🎯 Estratégia:", ["Zonas", "Midas", "ML", "Hot Numbers", "Raios"], key="estrategia_selecionada")
if estrategia != st.session_state.sistema.estrategia_selecionada:
    st.session_state.sistema.set_estrategia(estrategia)
    st.toast(f"🔄 Estratégia: {estrategia}")

with st.sidebar.expander("🔄 Rotação", expanded=True):
    status = st.session_state.sistema.get_status_rotacao()
    st.write(f"🎯 Estratégia: {status['estrategia_atual']}")
    st.write(f"❌ Erros: {status['sequencia_erros']}/2")
    st.write(f"🔄 Próxima rotação em: {status['proxima_rotacao_em']} erro(s)")

with st.sidebar.expander("🧠 Treinamento ML", expanded=False):
    numeros_lista = [item['number'] if isinstance(item, dict) else item for item in st.session_state.historico if item is not None]
    st.write(f"📊 Números: {len(numeros_lista)}/200")
    if len(numeros_lista) >= 200 and st.button("🚀 Treinar ML"):
        with st.spinner("Treinando..."):
            success, msg = st.session_state.sistema.treinar_modelo_ml(numeros_lista)
            st.success(msg) if success else st.error(msg)

with st.sidebar.expander(f"🔍 Análise", expanded=False):
    if estrategia == "Zonas":
        st.text(st.session_state.sistema.estrategia_zonas.get_analise_detalhada())
    elif estrategia == "ML":
        st.text(st.session_state.sistema.estrategia_ml.get_analise_ml())
    elif estrategia == "Hot Numbers":
        hot = st.session_state.sistema.estrategia_hot
        if hot.numeros_hot:
            st.write(f"🔥 Hot: {', '.join(map(str, hot.numeros_hot[:10]))}")
            st.write(f"❄️ Cold: {', '.join(map(str, hot.numeros_cold[:10]))}")
        else:
            st.write("Coletando dados...")
    elif estrategia == "Raios":
        raios = st.session_state.sistema.estrategia_raios
        st.write(f"⚡ Raios registrados: {len(raios.historico_raios)}")

st.subheader("✍️ Inserir Sorteios")
entrada = st.text_input("Digite números (0-36):")
if st.button("Adicionar") and entrada:
    try:
        nums = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
        for n in nums:
            st.session_state.historico.append({"number": n, "timestamp": f"manual_{len(st.session_state.historico)}"})
            st.session_state.sistema.processar_novo_numero(n)
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()
        st.success(f"{len(nums)} números adicionados!")
        st.rerun()
    except Exception as e:
        st.error(f"Erro: {e}")

st_autorefresh(interval=3000, key="refresh")
resultado = fetch_latest_result()
if resultado and resultado.get("timestamp"):
    ultimo_ts = st.session_state.historico[-1].get("timestamp") if st.session_state.historico else None
    if resultado["timestamp"] != ultimo_ts and resultado.get("number") is not None:
        st.session_state.historico.append(resultado)
        st.session_state.sistema.processar_novo_numero(resultado, resultado["is_lightning"], resultado["multiplier"])
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()

st.subheader("🔁 Últimos Números")
if st.session_state.historico:
    ultimos_10 = st.session_state.historico[-10:]
    hot_numbers = st.session_state.sistema.estrategia_hot.numeros_hot
    st.session_state.hot_numbers = hot_numbers
    numeros_html = []
    for item in ultimos_10:
        if isinstance(item, dict):
            num = item.get('number')
            is_lightning = item.get('is_lightning', False)
            multiplier = item.get('multiplier')
            numeros_html.append(format_number_with_lightning(num, is_lightning, multiplier))
        else:
            numeros_html.append(format_number_with_lightning(item, False))
    st.markdown(" ".join(numeros_html), unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    lightning_count = sum(1 for item in st.session_state.historico[-50:] if isinstance(item, dict) and item.get('is_lightning', False))
    col1.metric("⚡ Raios", f"{lightning_count}")
    col2.metric("🔥 Hot", len(st.session_state.sistema.estrategia_hot.numeros_hot))
    col3.metric("❄️ Cold", len(st.session_state.sistema.estrategia_hot.numeros_cold))
else:
    st.write("Nenhum número")

status = st.session_state.sistema.get_status_rotacao()
col1, col2, col3 = st.columns(3)
col1.metric("🎯 Estratégia", status['estrategia_atual'])
col2.metric("❌ Erros", f"{status['sequencia_erros']}/2")
col3.metric("🔄 Rotação", f"Em {status['proxima_rotacao_em']}")

st.subheader("🎯 Previsão Ativa")
if st.session_state.sistema.previsao_ativa:
    p = st.session_state.sistema.previsao_ativa
    st.success(f"**{p['nome']}**")
    if p.get('combinacao'):
        st.info(f"🎲 Combinação: {' + '.join(p['combinacao'])}")
    if p.get('erros_consecutivos', 0) >= 2:
        st.warning("⚠️ PRÓXIMA APOSTA SERÁ EM COMBINAÇÃO DIFERENTE!")
    st.write(f"**🔢 Números ({len(p['numeros_apostar'])}):**")
    st.write(", ".join(map(str, sorted(p['numeros_apostar']))))
else:
    st.info(f"Analisando {estrategia}...")

st.subheader("📈 Desempenho")
total = st.session_state.sistema.acertos + st.session_state.sistema.erros
taxa = (st.session_state.sistema.acertos / total * 100) if total > 0 else 0
c1, c2, c3, c4 = st.columns(4)
c1.metric("🟢 Acertos", st.session_state.sistema.acertos)
c2.metric("🔴 Erros", st.session_state.sistema.erros)
c3.metric("📊 Total", total)
c4.metric("✅ Taxa", f"{taxa:.1f}%")

if st.session_state.sistema.estrategias_contador:
    st.write("**📊 Performance por Estratégia:**")
    for nome, dados in st.session_state.sistema.estrategias_contador.items():
        if dados['total'] > 0:
            taxa_est = (dados['acertos'] / dados['total'] * 100)
            cor = "🟢" if taxa_est >= 50 else "🟡" if taxa_est >= 30 else "🔴"
            st.write(f"{cor} {nome}: {dados['acertos']}/{dados['total']} ({taxa_est:.1f}%)")

if st.session_state.sistema.historico_desempenho:
    st.write("**🔍 Últimas 5:**")
    for r in st.session_state.sistema.historico_desempenho[-5:]:
        emoji = "🎉" if r['acerto'] else "❌"
        raio = "⚡" if r.get('is_lightning', False) else ""
        st.write(f"{emoji}{raio} {r['estrategia']}: {r['numero']}")

if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        st.download_button("📥 Baixar histórico", f.read(), "historico_roleta.json")

salvar_sessao()
