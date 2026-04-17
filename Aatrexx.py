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
            'estrategia_selecionada': st.session_state.sistema.estrategia_selecionada
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
        return False

# =============================
# CLASSE PRINCIPAL DA ROLETA
# =============================
class RoletaInteligente:
    def __init__(self):
        self.race = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        
    def get_vizinhos_roleta(self, numero_central, quantidade=4):
        """Retorna os vizinhos físicos na roleta (antes e depois)"""
        if numero_central not in self.race:
            return [numero_central]
        
        posicao = self.race.index(numero_central)
        vizinhos = []
        
        # Adiciona vizinhos antes
        for offset in range(-quantidade, 0):
            vizinho = self.race[(posicao + offset) % len(self.race)]
            vizinhos.append(vizinho)
        
        # Adiciona o número central
        vizinhos.append(numero_central)
        
        # Adiciona vizinhos depois
        for offset in range(1, quantidade + 1):
            vizinho = self.race[(posicao + offset) % len(self.race)]
            vizinhos.append(vizinho)
        
        return vizinhos
    
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
# FUNÇÃO PARA FORMATAR NÚMERO COM ESTILO
# =============================
def format_number_with_lightning(numero, is_lightning, multiplier=None):
    """Retorna HTML formatado para o número com estilo diferenciado se for raio"""
    if is_lightning:
        multiplier_text = f" x{multiplier}" if multiplier else ""
        return f'<span style="background: linear-gradient(135deg, #FFD700, #FFA500); color: #000; font-weight: bold; padding: 4px 8px; border-radius: 50%; display: inline-block; box-shadow: 0 0 10px #FFD700;" title="Número Raio!{multiplier_text}">⚡{numero}⚡</span>'
    else:
        return f'<span style="background: #2c3e50; color: white; padding: 4px 8px; border-radius: 50%; display: inline-block;">{numero}</span>'

# =============================
# ESTRATÉGIA HOT NUMBERS APRIMORADA COM VIZINHOS
# =============================
class EstrategiaHotNumbersAprimorada:
    def __init__(self, roleta_obj):
        self.roleta = roleta_obj
        self.historico = deque(maxlen=100)
        self.numeros_hot = []
        self.numeros_cold = []
        self.janela_analise = 30
        self.quantidade_vizinhos = 4  # 4 vizinhos antes e 4 depois
        self.max_numeros_aposta = 15
        
    def adicionar_numero(self, numero):
        self.historico.append(numero)
        self.atualizar_hot_numbers()
        
    def atualizar_hot_numbers(self):
        if len(self.historico) < self.janela_analise:
            return
            
        historico_lista = list(self.historico)[-self.janela_analise:]
        contagem = Counter(historico_lista)
        
        # Hot numbers: números que apareceram mais de 3 vezes nos últimos 30
        # Ordena por frequência
        self.numeros_hot = sorted([num for num, count in contagem.items() if count >= 3], 
                                  key=lambda x: contagem[x], reverse=True)
        
        # Cold numbers: números que não apareceram nos últimos 30
        todos_numeros = set(range(37))
        self.numeros_cold = list(todos_numeros - set(historico_lista))
    
    def expandir_com_vizinhos(self, numeros_base):
        """Expande uma lista de números incluindo seus vizinhos na roleta"""
        numeros_expandidos = set()
        
        for numero in numeros_base:
            # Adiciona o número base
            numeros_expandidos.add(numero)
            
            # Adiciona os vizinhos na roleta (4 antes e 4 depois)
            vizinhos = self.roleta.get_vizinhos_roleta(numero, self.quantidade_vizinhos)
            for vizinho in vizinhos:
                numeros_expandidos.add(vizinho)
        
        return list(numeros_expandidos)
    
    def calcular_peso_numero(self, numero, frequencia_dict):
        """Calcula o peso de um número baseado em sua frequência e posição"""
        peso_base = frequencia_dict.get(numero, 1)
        
        # Se for um hot number, aumenta o peso
        if numero in self.numeros_hot:
            peso_base *= 1.5
        
        # Verifica se o número é vizinho de algum hot number
        for hot in self.numeros_hot:
            vizinhos_hot = self.roleta.get_vizinhos_roleta(hot, self.quantidade_vizinhos)
            if numero in vizinhos_hot:
                peso_base *= 1.2
                break
        
        return peso_base
    
    def analisar_hot_numbers(self):
        if len(self.historico) < 15:
            return None
            
        if not self.numeros_hot:
            return None
        
        # Pega os top hot numbers (até 5)
        top_hot = self.numeros_hot[:5]
        
        # Expande com vizinhos
        numeros_expandidos = self.expandir_com_vizinhos(top_hot)
        
        # Calcula frequência para peso
        historico_lista = list(self.historico)[-self.janela_analise:]
        frequencia = Counter(historico_lista)
        
        # Calcula peso para cada número
        numeros_com_peso = [(num, self.calcular_peso_numero(num, frequencia)) for num in numeros_expandidos]
        
        # Ordena por peso
        numeros_com_peso.sort(key=lambda x: x[1], reverse=True)
        
        # Seleciona até 15 números
        numeros_finais = [num for num, peso in numeros_com_peso[:self.max_numeros_aposta]]
        numeros_finais = sorted(set(numeros_finais))
        
        # Estatísticas da seleção
        total_numeros_base = len(top_hot)
        total_vizinhos = len(numeros_expandidos) - total_numeros_base
        reducao = len(numeros_expandidos) - len(numeros_finais)
        
        # Calcula confiança
        confianca = 'Muito Alta' if len(self.numeros_hot) <= 6 else 'Alta'
        
        # Gera gatilho explicativo
        gatilho = f'🔥 HOT NUMBERS: {", ".join(map(str, top_hot))} | +{total_vizinhos} vizinhos (4 antes/depois) | FINAL: {len(numeros_finais)}/{self.max_numeros_aposta} números'
        
        return {
            'nome': 'Hot Numbers com Vizinhos',
            'numeros_apostar': numeros_finais,
            'gatilho': gatilho,
            'confianca': confianca,
            'tipo': 'hot_numbers_expandido',
            'hot_numbers_base': top_hot,
            'total_vizinhos': total_vizinhos,
            'reducao_aplicada': reducao > 0,
            'numeros_originais_qtd': len(numeros_expandidos)
        }
    
    def analisar_cold_numbers(self):
        if len(self.historico) < 30:
            return None
            
        if not self.numeros_cold:
            return None
            
        # Seleciona cold numbers que são historicamente frequentes
        cold_frequentes_historicos = [30, 21, 18, 25, 8, 29, 15, 5, 10, 23]
        cold_candidatos = [n for n in self.numeros_cold if n in cold_frequentes_historicos]
        
        if not cold_candidatos:
            cold_candidatos = self.numeros_cold[:4]
        
        # Expande com vizinhos
        numeros_expandidos = self.expandir_com_vizinhos(cold_candidatos)
        
        # Seleciona até 15 números
        numeros_finais = sorted(set(numeros_expandidos[:self.max_numeros_aposta]))
        
        if numeros_finais:
            return {
                'nome': 'Cold Numbers (Atrasados) com Vizinhos',
                'numeros_apostar': numeros_finais,
                'gatilho': f'❄️ COLD NUMBERS: {", ".join(map(str, cold_candidatos[:3]))}... + vizinhos | FINAL: {len(numeros_finais)} números',
                'confianca': 'Média',
                'tipo': 'cold_numbers_expandido'
            }
        return None
    
    def get_analise_completa(self):
        if len(self.historico) < self.janela_analise:
            return f"Coletando dados... ({len(self.historico)}/{self.janela_analise})"
        
        analise = "🔥 HOT NUMBERS APRIMORADO COM VIZINHOS 🔥\n"
        analise += "=" * 50 + "\n"
        analise += f"📊 Janela de análise: {self.janela_analise} sorteios\n"
        analise += f"📍 Vizinhos por número: {self.quantidade_vizinhos} antes + {self.quantidade_vizinhos} depois\n"
        analise += f"🎯 Máximo de números por aposta: {self.max_numeros_aposta}\n"
        analise += "=" * 50 + "\n\n"
        
        analise += "📈 TOP HOT NUMBERS:\n"
        for i, num in enumerate(self.numeros_hot[:10], 1):
            historico_lista = list(self.historico)[-self.janela_analise:]
            freq = historico_lista.count(num)
            analise += f"  {i}. Número {num} - {freq} ocorrências\n"
        
        analise += "\n📍 EXPANSÃO COM VIZINHOS:\n"
        if self.numeros_hot:
            for hot in self.numeros_hot[:5]:
                vizinhos = self.roleta.get_vizinhos_roleta(hot, self.quantidade_vizinhos)
                analise += f"  🔥 Número {hot} → Vizinhos: {vizinhos}\n"
        
        analise += f"\n❄️ COLD NUMBERS (atrasados): {len(self.numeros_cold)} números\n"
        if self.numeros_cold:
            analise += f"  Principais candidatos: {self.numeros_cold[:10]}\n"
        
        return analise

# =============================
# ESTRATÉGIA DE RAIOS APRIMORADA COM VIZINHOS
# =============================
class EstrategiaRaiosAprimorada:
    def __init__(self, roleta_obj):
        self.roleta = roleta_obj
        self.historico_raios = deque(maxlen=50)
        self.multipliers = []
        self.quantidade_vizinhos = 4
        self.max_numeros_aposta = 15
        
    def adicionar_raio(self, numero, multiplier):
        self.historico_raios.append({
            'numero': numero,
            'multiplier': multiplier,
            'timestamp': datetime.now()
        })
        self.multipliers.append(multiplier)
    
    def expandir_com_vizinhos(self, numeros_base):
        """Expande uma lista de números incluindo seus vizinhos na roleta"""
        numeros_expandidos = set()
        
        for numero in numeros_base:
            numeros_expandidos.add(numero)
            vizinhos = self.roleta.get_vizinhos_roleta(numero, self.quantidade_vizinhos)
            for vizinho in vizinhos:
                numeros_expandidos.add(vizinho)
        
        return list(numeros_expandidos)
    
    def analisar_raios(self):
        if len(self.historico_raios) < 3:
            return None
            
        # Números que mais foram raio
        numeros_raios = [r['numero'] for r in self.historico_raios]
        contagem_raios = Counter(numeros_raios)
        
        # Números comuns de raio (baseado nos dados reais)
        numeros_comuns_raios = [20, 24, 8, 10, 12, 29]
        
        # Seleciona números que ainda não saíram como raio recentemente
        ultimos_raios_numeros = [r['numero'] for r in list(self.historico_raios)[-10:]]
        
        # Combina números comuns com os mais frequentes
        candidatos_base = []
        for num, count in contagem_raios.most_common(3):
            if num not in ultimos_raios_numeros[-3:]:
                candidatos_base.append(num)
        
        for num in numeros_comuns_raios:
            if num not in ultimos_raios_numeros[-3:] and num not in candidatos_base:
                candidatos_base.append(num)
        
        if not candidatos_base:
            candidatos_base = numeros_comuns_raios[:3]
        
        # Expande com vizinhos
        numeros_expandidos = self.expandir_com_vizinhos(candidatos_base[:4])
        
        # Seleciona até 15 números
        numeros_finais = sorted(set(numeros_expandidos[:self.max_numeros_aposta]))
        
        if numeros_finais:
            return {
                'nome': 'Raios com Vizinhos',
                'numeros_apostar': numeros_finais,
                'gatilho': f'⚡ RAIOS: {", ".join(map(str, candidatos_base[:3]))}... + {self.quantidade_vizinhos} vizinhos | Multiplicadores recentes: {self.multipliers[-3:]}',
                'confianca': 'Média-Alta',
                'tipo': 'raios_expandido',
                'numeros_originais_qtd': len(numeros_expandidos)
            }
        return None
    
    def get_analise_raios(self):
        if not self.historico_raios:
            return "Aguardando ocorrência de raios..."
        
        analise = "⚡ ESTRATÉGIA DE RAIOS APRIMORADA ⚡\n"
        analise += "=" * 45 + "\n"
        analise += f"📍 Vizinhos por número: {self.quantidade_vizinhos} antes + {self.quantidade_vizinhos} depois\n"
        analise += f"🎯 Máximo de números por aposta: {self.max_numeros_aposta}\n\n"
        
        analise += "📊 ESTATÍSTICAS DOS RAIOS:\n"
        numeros_raios = [r['numero'] for r in self.historico_raios]
        contagem = Counter(numeros_raios)
        for num, count in contagem.most_common(5):
            analise += f"  ⚡ Número {num}: {count} vezes\n"
        
        analise += f"\n💰 Média multiplicadores: {sum(self.multipliers[-10:])/len(self.multipliers[-10:]):.0f}x" if self.multipliers else ""
        
        return analise

# =============================
# SISTEMA DE GESTÃO ATUALIZADO
# =============================
class SistemaRoletaCompleto:
    def __init__(self):
        self.roleta = RoletaInteligente()
        self.estrategia_hot = EstrategiaHotNumbersAprimorada(self.roleta)
        self.estrategia_raios = EstrategiaRaiosAprimorada(self.roleta)
        
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.estrategia_selecionada = "Hot Numbers"
        self.contador_sorteios_global = 0
        
        self.sequencia_erros = 0
        self.ultima_estrategia_erro = ""

    def set_estrategia(self, estrategia):
        self.estrategia_selecionada = estrategia
        salvar_sessao()

    def processar_novo_numero(self, numero, is_lightning=False, multiplier=None):
        if isinstance(numero, dict) and 'number' in numero:
            numero_real = numero['number']
        else:
            numero_real = numero
            
        self.contador_sorteios_global += 1
            
        if is_lightning and multiplier:
            self.estrategia_raios.adicionar_raio(numero_real, multiplier)
        
        self.estrategia_hot.adicionar_numero(numero_real)
        
        if self.previsao_ativa:
            acerto = False
            nome_estrategia = self.previsao_ativa['nome']
            numeros_apostados = self.previsao_ativa.get('numeros_apostar', [])
            
            if numero_real in numeros_apostados:
                acerto = True
            
            # Rotação automática
            if acerto:
                self.sequencia_erros = 0
                self.ultima_estrategia_erro = ""
            else:
                self.sequencia_erros += 1
                self.ultima_estrategia_erro = nome_estrategia
                
                if self.sequencia_erros >= 2:
                    if self.estrategia_selecionada == "Hot Numbers":
                        self.estrategia_selecionada = "Raios"
                    elif self.estrategia_selecionada == "Raios":
                        self.estrategia_selecionada = "Hot Numbers"
                    self.sequencia_erros = 0
            
            if nome_estrategia not in self.estrategias_contador:
                self.estrategias_contador[nome_estrategia] = {'acertos': 0, 'total': 0}
            
            self.estrategias_contador[nome_estrategia]['total'] += 1
            if acerto:
                self.estrategias_contador[nome_estrategia]['acertos'] += 1
                self.acertos += 1
            else:
                self.erros += 1
            
            self.historico_desempenho.append({
                'numero': numero_real,
                'acerto': acerto,
                'estrategia': nome_estrategia,
                'previsao': numeros_apostados,
                'is_lightning': is_lightning,
                'multiplier': multiplier
            })
            
            self.previsao_ativa = None
        
        # Gera nova previsão
        nova_estrategia = None
        
        if self.estrategia_selecionada == "Hot Numbers":
            nova_estrategia = self.estrategia_hot.analisar_hot_numbers()
            if not nova_estrategia:
                nova_estrategia = self.estrategia_hot.analisar_cold_numbers()
        elif self.estrategia_selecionada == "Raios":
            nova_estrategia = self.estrategia_raios.analisar_raios()
            if not nova_estrategia:
                nova_estrategia = self.estrategia_hot.analisar_hot_numbers()
        
        if nova_estrategia:
            self.previsao_ativa = nova_estrategia
            self.enviar_previsao_simplificada(nova_estrategia)

    def enviar_previsao_simplificada(self, previsao):
        """Envia notificação de previsão simplificada"""
        try:
            numeros_apostar = sorted(previsao['numeros_apostar'])
            
            if 'Hot Numbers' in previsao['nome']:
                emoji = "🔥"
                titulo = "HOT NUMBERS COM VIZINHOS"
            elif 'Raios' in previsao['nome']:
                emoji = "⚡"
                titulo = "RAIOS COM VIZINHOS"
            else:
                emoji = "🎯"
                titulo = previsao['nome']
            
            st.toast(f"{emoji} Nova Previsão - {titulo}", icon=emoji)
            st.warning(f"🔔 {emoji} {titulo}\n📊 {previsao['gatilho']}")
            
            if previsao.get('reducao_aplicada', False):
                st.info(f"🎯 Seleção inteligente: {previsao['numeros_originais_qtd']} → {len(numeros_apostar)} números")
            
            salvar_sessao()
        except Exception as e:
            logging.error(f"Erro ao enviar previsão: {e}")

    def zerar_estatisticas_desempenho(self):
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.historico_desempenho = []
        self.contador_sorteios_global = 0
        self.sequencia_erros = 0
        self.ultima_estrategia_erro = ""
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
            
            logging.info("🔄 Estatísticas recentes resetadas")
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
def enviar_telegram(mensagem):
    """Envia mensagem para o Telegram"""
    try:
        if 'telegram_token' in st.session_state and 'telegram_chat_id' in st.session_state:
            token = st.session_state.telegram_token
            chat_id = st.session_state.telegram_chat_id
            if token and chat_id:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": mensagem,
                    "parse_mode": "HTML"
                }
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    logging.info("Mensagem enviada para Telegram")
    except Exception as e:
        logging.error(f"Erro Telegram: {e}")

def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    try:
        with open(caminho, "w") as f:
            json.dump(historico, f, indent=2)
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")

def fetch_latest_result():
    """Busca o último resultado da API"""
    try:
        API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
        HEADERS = {"User-Agent": "Mozilla/5.0"}
        
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
            "number": number,
            "timestamp": timestamp,
            "lightning_numbers": list(lightning_dict.keys()),
            "is_lightning": is_lightning,
            "multiplier": multiplier
        }
    except Exception as e:
        logging.error(f"Erro ao buscar resultado: {e}")
        return None

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="Hot Numbers com Vizinhos - Roleta", layout="centered")
st.title("🔥 Hot Numbers com Vizinhos - Estratégia Aprimorada 🔥")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaRoletaCompleto()

sessao_carregada = carregar_sessao()

if "historico" not in st.session_state:
    if not sessao_carregada and os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                st.session_state.historico = json.load(f)
                # Atualiza o sistema com o histórico existente
                for item in st.session_state.historico:
                    if isinstance(item, dict):
                        num = item.get('number')
                        if num is not None:
                            st.session_state.sistema.processar_novo_numero(num)
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
    if st.button("💾 Salvar Sessão", use_container_width=True):
        salvar_sessao()
        st.success("✅ Sessão salva!")
    
    if st.button("🔄 Carregar Sessão", use_container_width=True):
        if carregar_sessao():
            st.success("✅ Sessão carregada!")
            st.rerun()
        else:
            st.error("❌ Nenhuma sessão salva encontrada")
    
    st.write("---")
    
    if st.button("🔄 Reset Recente", help="Mantém apenas os últimos 10 resultados", use_container_width=True):
        st.session_state.sistema.reset_recente_estatisticas()
        st.success("✅ Estatísticas recentes resetadas!")
        st.rerun()
    
    if st.button("🗑️ Zerar Tudo", type="secondary", help="Zera TODAS as estatísticas", use_container_width=True):
        st.session_state.sistema.zerar_estatisticas_desempenho()
        st.error("🗑️ Todas as estatísticas foram zeradas!")
        st.rerun()

with st.sidebar.expander("🔔 Configurações do Telegram", expanded=False):
    telegram_token = st.text_input(
        "Bot Token:",
        value=st.session_state.telegram_token,
        type="password"
    )
    telegram_chat_id = st.text_input(
        "Chat ID:",
        value=st.session_state.telegram_chat_id
    )
    
    if st.button("Salvar"):
        st.session_state.telegram_token = telegram_token
        st.session_state.telegram_chat_id = telegram_chat_id
        salvar_sessao()
        st.success("✅ Configurações salvas!")

with st.sidebar.expander("🎯 Configurações da Estratégia", expanded=True):
    st.write("**Hot Numbers com Vizinhos:**")
    st.write("• 📊 Janela de análise: 30 sorteios")
    st.write("• 🔥 Hot numbers: números com 3+ ocorrências")
    st.write("• 📍 Vizinhos: 4 antes + 4 depois na roleta")
    st.write("• 🎯 Máximo: 15 números por aposta")
    st.write("")
    st.write("**⚡ Raios com Vizinhos:**")
    st.write("• 📍 Vizinhos: 4 antes + 4 depois")
    st.write("• 🎯 Máximo: 15 números por aposta")
    st.write("• 🔄 Rotação após 2 erros seguidos")

with st.sidebar.expander("📊 Informações da Estratégia", expanded=False):
    st.write("**🎯 Como funciona:**")
    st.write("1. Identifica os números mais frequentes (hot numbers)")
    st.write("2. Para cada hot number, adiciona 4 vizinhos antes e 4 depois")
    st.write("3. Seleciona os 15 melhores números baseado em peso")
    st.write("")
    st.write("**📈 Vantagens:**")
    st.write("- Maior cobertura (até 15 números)")
    st.write("- Aproveita a física da roleta")
    st.write("- Reduz risco de perder por poucos números")

with st.sidebar.expander(f"🔍 Análise Detalhada", expanded=False):
    if st.session_state.sistema.estrategia_selecionada == "Hot Numbers":
        analise = st.session_state.sistema.estrategia_hot.get_analise_completa()
    else:
        analise = st.session_state.sistema.estrategia_raios.get_analise_raios()
    st.text(analise)

# Interface principal
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

# Auto-refresh para buscar novos resultados
st_autorefresh(interval=3000, key="refresh")

resultado = fetch_latest_result()
if st.session_state.historico:
    ultimo_ts = st.session_state.historico[-1].get("timestamp") if st.session_state.historico else None
else:
    ultimo_ts = None

if resultado and resultado.get("timestamp") and resultado["timestamp"] != ultimo_ts:
    numero_atual = resultado.get("number")
    if numero_atual is not None:
        resultado_completo = {
            "number": numero_atual,
            "timestamp": resultado["timestamp"],
            "is_lightning": resultado["is_lightning"],
            "multiplier": resultado["multiplier"],
            "lightning_numbers": resultado["lightning_numbers"]
        }
        st.session_state.historico.append(resultado_completo)
        st.session_state.sistema.processar_novo_numero(
            resultado_completo, 
            resultado["is_lightning"], 
            resultado["multiplier"]
        )
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()

# Exibe últimos números
st.subheader("🔁 Últimos Números")
if st.session_state.historico:
    ultimos_10 = st.session_state.historico[-10:]
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
    
    # Estatísticas rápidas
    col1, col2, col3 = st.columns(3)
    with col1:
        hot_count = len(st.session_state.sistema.estrategia_hot.numeros_hot)
        st.metric("🔥 Hot Numbers", hot_count)
    with col2:
        raios_count = len(st.session_state.sistema.estrategia_raios.historico_raios)
        st.metric("⚡ Total Raios", raios_count)
    with col3:
        total = st.session_state.sistema.acertos + st.session_state.sistema.erros
        taxa = (st.session_state.sistema.acertos / total * 100) if total > 0 else 0
        st.metric("✅ Taxa Acerto", f"{taxa:.1f}%")
else:
    st.write("Nenhum número registrado")

# Status da rotação
status_rotacao = st.session_state.sistema.get_status_rotacao()
col_status1, col_status2, col_status3 = st.columns(3)
with col_status1:
    st.metric("🎯 Estratégia Atual", status_rotacao['estrategia_atual'])
with col_status2:
    st.metric("❌ Erros Seguidos", f"{status_rotacao['sequencia_erros']}/2")
with col_status3:
    st.metric("🔄 Rotação", f"Em {status_rotacao['proxima_rotacao_em']} erro(s)")

# Previsão ativa
st.subheader("🎯 Previsão Ativa")
sistema = st.session_state.sistema

if sistema.previsao_ativa:
    previsao = sistema.previsao_ativa
    st.success(f"**{previsao['nome']}**")
    
    if 'Hot Numbers' in previsao['nome']:
        st.write(f"**🔥 Hot numbers base:** {', '.join(map(str, previsao.get('hot_numbers_base', [])))}")
        st.write(f"**📍 Vizinhos adicionados:** 4 antes + 4 depois para cada hot number")
    
    if previsao.get('reducao_aplicada', False):
        st.info(f"🎯 **Seleção inteligente:** {previsao['numeros_originais_qtd']} números originais → {len(previsao['numeros_apostar'])} números finais")
    
    st.write(f"**🔢 Números para apostar ({len(previsao['numeros_apostar'])}):**")
    
    # Mostra números em linhas para melhor visualização
    numeros = sorted(previsao['numeros_apostar'])
    colunas = st.columns(5)
    for i, num in enumerate(numeros):
        colunas[i % 5].write(f"**{num}**")
    
    st.info(f"📊 **Gatilho:** {previsao['gatilho']}")
    st.info(f"🎯 **Confiança:** {previsao['confianca']}")
else:
    st.info(f"🎲 Aguardando dados suficientes para análise... (mínimo 15 sorteios)")

# Histórico de desempenho
st.subheader("📈 Histórico de Conferências")
if sistema.historico_desempenho:
    for resultado in sistema.historico_desempenho[-10:]:
        emoji = "🎉" if resultado['acerto'] else "❌"
        raio = "⚡" if resultado.get('is_lightning', False) else ""
        st.write(f"{emoji}{raio} {resultado['estrategia']}: Número {resultado['numero']} - {'Acertou!' if resultado['acerto'] else 'Errou!'}")
else:
    st.write("Nenhum resultado registrado ainda")

# Botão para limpar histórico
if st.button("🗑️ Limpar Histórico", type="secondary"):
    st.session_state.historico = []
    salvar_resultado_em_arquivo(st.session_state.historico)
    st.success("✅ Histórico limpo!")
    st.rerun()

salvar_sessao()
