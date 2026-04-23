import streamlit as st
import json
import os
import requests
import logging
import numpy as np
from collections import Counter, deque, defaultdict
from streamlit_autorefresh import st_autorefresh
import pickle
import math
from datetime import datetime

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_roleta.json"
PERFORMANCE_PATH = "performance_estrategias.json"

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
            'historico_numeros': list(st.session_state.sistema.historico_numeros),
            'historico_multiplicadores': list(st.session_state.sistema.historico_multiplicadores),
            'estrategia_ativa_manual': st.session_state.sistema.estrategia_ativa_manual,
            'matriz_transicao': dict(st.session_state.sistema.matriz_transicao),
            'ciclos_numeros': st.session_state.sistema.ciclos_numeros,
            'estrategias_ativas': st.session_state.get('estrategias_ativas', {
                'Dominante': True, 'Ruptura': True, 'CicloReal': True
            }),
            'forca_minima_sinal': st.session_state.get('forca_minima_sinal', 50),
            'expandir_com_vizinhos': st.session_state.get('expandir_com_vizinhos', True),
            'max_numeros_entrada': st.session_state.get('max_numeros_entrada', 15),
            'qtd_vizinhos_antes': st.session_state.get('qtd_vizinhos_antes', 3),
            'qtd_vizinhos_depois': st.session_state.get('qtd_vizinhos_depois', 3),
            'modo_adaptativo': st.session_state.get('modo_adaptativo', True),
            'taxa_minima_estrategia': st.session_state.get('taxa_minima_estrategia', 25),
            'intervalo_minimo_entradas': st.session_state.get('intervalo_minimo_entradas', 1)
        }
        
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f)
        
        # Salva performance separadamente
        if 'sistema' in st.session_state:
            with open(PERFORMANCE_PATH, 'w') as f:
                json.dump(st.session_state.sistema.performance, f, indent=2)
        
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
            
            st.session_state.estrategias_ativas = session_data.get('estrategias_ativas', {
                'Dominante': True, 'Ruptura': True, 'CicloReal': True
            })
            
            st.session_state.forca_minima_sinal = session_data.get('forca_minima_sinal', 50)
            st.session_state.expandir_com_vizinhos = session_data.get('expandir_com_vizinhos', True)
            st.session_state.max_numeros_entrada = session_data.get('max_numeros_entrada', 15)
            st.session_state.qtd_vizinhos_antes = session_data.get('qtd_vizinhos_antes', 3)
            st.session_state.qtd_vizinhos_depois = session_data.get('qtd_vizinhos_depois', 3)
            st.session_state.modo_adaptativo = session_data.get('modo_adaptativo', True)
            st.session_state.taxa_minima_estrategia = session_data.get('taxa_minima_estrategia', 25)
            st.session_state.intervalo_minimo_entradas = session_data.get('intervalo_minimo_entradas', 1)
            
            if 'sistema' in st.session_state:
                st.session_state.sistema.acertos = session_data.get('sistema_acertos', 0)
                st.session_state.sistema.erros = session_data.get('sistema_erros', 0)
                st.session_state.sistema.estrategias_contador = session_data.get('sistema_estrategias_contador', {})
                st.session_state.sistema.historico_desempenho = session_data.get('sistema_historico_desempenho', [])
                st.session_state.sistema.historico_numeros = deque(session_data.get('historico_numeros', []), maxlen=200)
                st.session_state.sistema.historico_multiplicadores = deque(session_data.get('historico_multiplicadores', []), maxlen=200)
                st.session_state.sistema.estrategia_ativa_manual = session_data.get('estrategia_ativa_manual', False)
                st.session_state.sistema.matriz_transicao = defaultdict(Counter, session_data.get('matriz_transicao', {}))
                st.session_state.sistema.ciclos_numeros = session_data.get('ciclos_numeros', {})
                st.session_state.sistema.intervalo_minimo_entradas = session_data.get('intervalo_minimo_entradas', 1)
            
            # Carrega performance
            if os.path.exists(PERFORMANCE_PATH) and 'sistema' in st.session_state:
                with open(PERFORMANCE_PATH, 'r') as f:
                    performance_data = json.load(f)
                    st.session_state.sistema.performance = performance_data
            
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
        if os.path.exists(PERFORMANCE_PATH):
            os.remove(PERFORMANCE_PATH)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    except Exception as e:
        logging.error(f"❌ Erro ao limpar sessão: {e}")

# =============================
# CONFIGURAÇÕES DE NOTIFICAÇÃO
# =============================
def enviar_previsao_auto(previsao):
    """Envia notificação de previsão automática"""
    try:
        nome = previsao['nome']
        numeros = sorted(previsao['numeros_apostar'])
        gatilho = previsao['gatilho']
        forca_real = previsao.get('forca_real', 0)
        forca_condicao = previsao.get('forca_condicao', 0)
        taxa_real = previsao.get('taxa_real', 0)
        
        emojis = {'Dominante': '⚡', 'Ruptura': '💣', 'Ciclo Real': '🌀'}
        emoji = emojis.get(nome, '🎲')
        
        barras = "█" * (int(forca_real) // 10) + "░" * (10 - int(forca_real) // 10)
        
        msg = f"{emoji} **{nome.upper()}** ATIVADA!\n"
        msg += f"📊 Força: {barras} {forca_real:.0f}%\n"
        msg += f"📈 Taxa: {taxa_real:.0f}% | Cond: {forca_condicao:.0f}%\n"
        msg += f"📋 {gatilho}"
        
        if previsao.get('expandido'):
            msg += f"\n📈 Expandido: {previsao.get('num_originais', 0)} → {len(numeros)} números"
        
        st.toast(f"🎯 {nome} - Força {forca_real:.0f}%", icon=emoji)
        
        if forca_real >= 60:
            st.success(f"🔔 **SINAL!** {msg}")
        else:
            st.warning(f"🔔 {msg}")
        
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            enviar_telegram(f"🔔 GATILHO DETECTADO\n{msg}")
            metade = len(numeros) // 2
            if metade > 0:
                linha1 = " ".join(map(str, numeros[:metade]))
                linha2 = " ".join(map(str, numeros[metade:]))
                enviar_telegram(f"{emoji} APOSTAR AGORA\n{linha1}\n{linha2}")
            else:
                enviar_telegram(f"{emoji} APOSTAR AGORA\n" + " ".join(map(str, numeros)))
                
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar previsão: {e}")

def enviar_resultado_auto(numero_real, acerto, nome_estrategia, multiplicador=None):
    """Envia notificação de resultado"""
    try:
        if acerto:
            msg = f"✅ ACERTO!\n🎲 Número: {numero_real}\n🎯 Estratégia: {nome_estrategia}"
        else:
            msg = f"❌ ERRO!\n🎲 Número: {numero_real}\n🎯 Estratégia: {nome_estrategia}"
        
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
        payload = {"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Erro na conexão com Telegram: {e}")

# =============================
# CONFIGURAÇÕES DA API
# =============================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# =============================
# ROLETA BASE
# =============================
class RoletaBase:
    def __init__(self):
        self.race = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        
    def get_vizinhos(self, numero, raio=2):
        if numero not in self.race:
            return []
        posicao = self.race.index(numero)
        vizinhos = []
        for offset in range(-raio, raio + 1):
            if offset != 0:
                vizinhos.append(self.race[(posicao + offset) % 37])
        return vizinhos
    
    def get_vizinhos_anteriores(self, numero, quantidade=3):
        if numero not in self.race:
            return []
        posicao = self.race.index(numero)
        vizinhos = []
        for i in range(1, quantidade + 1):
            vizinhos.append(self.race[(posicao - i) % 37])
        return vizinhos
    
    def get_vizinhos_posteriores(self, numero, quantidade=3):
        if numero not in self.race:
            return []
        posicao = self.race.index(numero)
        vizinhos = []
        for i in range(1, quantidade + 1):
            vizinhos.append(self.race[(posicao + i) % 37])
        return vizinhos
    
    def get_oposto(self, numero):
        if numero not in self.race:
            return None
        posicao = self.race.index(numero)
        return self.race[(posicao + 18) % 37]
    
    def get_opostos_regiao(self, numero, quantidade=3):
        if numero not in self.race:
            return []
        posicao = self.race.index(numero)
        opostos = []
        for offset in range(-1, quantidade - 1):
            opostos.append(self.race[(posicao + 18 + offset) % 37])
        return opostos
    
    def get_distancia_roda(self, num1, num2):
        if num1 not in self.race or num2 not in self.race:
            return 37
        p1 = self.race.index(num1)
        p2 = self.race.index(num2)
        dist = abs(p1 - p2)
        return min(dist, 37 - dist)


# =============================
# SELETOR INTELIGENTE DE NÚMEROS
# =============================
class SeletorInteligente:
    def __init__(self):
        self.roleta = RoletaBase()
    
    def expandir_com_vizinhos(self, numeros_base, historico, max_numeros=15, 
                              qtd_anteriores=3, qtd_posteriores=3):
        if len(numeros_base) == 0:
            return [], 0
        
        num_originais = len(numeros_base)
        numeros_expandidos = set(numeros_base)
        
        for num in numeros_base:
            anteriores = self.roleta.get_vizinhos_anteriores(num, qtd_anteriores)
            numeros_expandidos.update(anteriores)
            
            posteriores = self.roleta.get_vizinhos_posteriores(num, qtd_posteriores)
            numeros_expandidos.update(posteriores)
        
        lista_expandida = list(numeros_expandidos)
        
        if len(lista_expandida) <= max_numeros:
            return sorted(lista_expandida), num_originais
        
        selecionados = self.selecionar_melhores(lista_expandida, historico, max_numeros)
        return selecionados, num_originais
    
    def selecionar_melhores(self, numeros_candidatos, historico, max_numeros=15):
        if len(numeros_candidatos) <= max_numeros:
            return sorted(numeros_candidatos)
        
        hist_list = list(historico)
        scores = {}
        
        for num in numeros_candidatos:
            score = 0
            
            if len(hist_list) >= 10:
                recentes = hist_list[-20:]
                freq = recentes.count(num) / len(recentes)
                score += freq * 40
            
            if len(hist_list) >= 5:
                ultimos_5 = hist_list[-5:]
                for ult in ultimos_5:
                    dist = self.roleta.get_distancia_roda(num, ult)
                    if dist <= 4:
                        score += 5 * (1 - dist/5)
            
            quentes_estudo = [33, 14, 17, 30, 25, 32, 8, 7]
            if num in quentes_estudo:
                score += 20
            
            score += 10
            
            if num == 0:
                score += 5
            
            scores[num] = score
        
        ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        selecionados = [num for num, _ in ordenados[:max_numeros]]
        return sorted(selecionados)


# =============================
# MOTOR DE PERFORMANCE (CORRIGIDO - MENOS RESTRITIVO)
# =============================
class MotorPerformance:
    """Gerencia a performance real de cada estratégia"""
    
    def __init__(self):
        self.performance = {
            'Dominante': {'wins': 0, 'losses': 0, 'historico': [], 'ultima_atualizacao': None},
            'Ruptura': {'wins': 0, 'losses': 0, 'historico': [], 'ultima_atualizacao': None},
            'Ciclo Real': {'wins': 0, 'losses': 0, 'historico': [], 'ultima_atualizacao': None}
        }
        self.peso_performance = 0.50  # 50% peso da taxa histórica
        self.peso_condicao = 0.50     # 50% peso das condições atuais
    
    def get_taxa_real(self, estrategia):
        """Retorna a taxa de acerto real da estratégia"""
        if estrategia not in self.performance:
            return 0.5  # Neutro
        
        data = self.performance[estrategia]
        total = data['wins'] + data['losses']
        
        if total == 0:
            return 0.5  # Sem dados = neutro (50%)
        
        return data['wins'] / total
    
    def get_total_tentativas(self, estrategia):
        """Retorna o total de tentativas da estratégia"""
        if estrategia not in self.performance:
            return 0
        data = self.performance[estrategia]
        return data['wins'] + data['losses']
    
    def is_estrategia_valida(self, estrategia, taxa_minima=0.25):
        """
        Verifica se a estratégia tem performance mínima para ser usada
        CORRIGIDO: Mais permissivo com poucos dados
        """
        total = self.get_total_tentativas(estrategia)
        
        # FASE DE COLETA: Se tem menos de 5 tentativas, é válida
        if total < 5:
            return True
        
        # FASE DE AVALIAÇÃO: Precisa ter taxa mínima
        taxa = self.get_taxa_real(estrategia)
        return taxa >= taxa_minima
    
    def atualizar_resultado(self, estrategia, acerto):
        """Atualiza a performance após cada resultado"""
        if estrategia not in self.performance:
            return
        
        if acerto:
            self.performance[estrategia]['wins'] += 1
            self.performance[estrategia]['historico'].append(1)
        else:
            self.performance[estrategia]['losses'] += 1
            self.performance[estrategia]['historico'].append(0)
        
        if len(self.performance[estrategia]['historico']) > 50:
            self.performance[estrategia]['historico'] = self.performance[estrategia]['historico'][-50:]
        
        self.performance[estrategia]['ultima_atualizacao'] = datetime.now().isoformat()
    
    def get_taxa_recente(self, estrategia, ultimas_n=5):
        """Taxa de acerto nas últimas N tentativas"""
        if estrategia not in self.performance:
            return 0.5
        
        historico = self.performance[estrategia]['historico']
        if len(historico) < ultimas_n:
            return self.get_taxa_real(estrategia)
        
        recentes = historico[-ultimas_n:]
        return sum(recentes) / len(recentes)
    
    def get_tendencia(self, estrategia):
        """Analisa se a estratégia está em tendência de alta ou baixa"""
        total = self.get_total_tentativas(estrategia)
        if total < 3:
            return 'neutra'
        
        taxa_geral = self.get_taxa_real(estrategia)
        taxa_recente = self.get_taxa_recente(estrategia, 3)
        
        if taxa_recente > taxa_geral + 0.15:
            return 'subindo'
        elif taxa_recente < taxa_geral - 0.15:
            return 'caindo'
        else:
            return 'estavel'
    
    def calcular_forca_real(self, estrategia, forca_condicao):
        """
        Calcula a força real combinando:
        - Taxa histórica (50%)
        - Condições atuais (50%)
        CORRIGIDO: Mais peso na condição quando há poucos dados
        """
        taxa_real = self.get_taxa_real(estrategia)
        total = self.get_total_tentativas(estrategia)
        
        # Ajusta pesos baseado na quantidade de dados
        if total < 3:
            # Poucos dados: confia mais na condição
            peso_perf = 0.2
            peso_cond = 0.8
        elif total < 8:
            # Dados moderados: equilibrado
            peso_perf = 0.4
            peso_cond = 0.6
        else:
            # Muitos dados: confia mais na performance
            peso_perf = self.peso_performance
            peso_cond = self.peso_condicao
        
        # Ajusta pela tendência
        tendencia = self.get_tendencia(estrategia)
        fator_tendencia = 1.0
        if tendencia == 'subindo':
            fator_tendencia = 1.15
        elif tendencia == 'caindo':
            fator_tendencia = 0.85
        
        forca_real = (taxa_real * 100 * peso_perf) + (forca_condicao * peso_cond)
        forca_real = forca_real * fator_tendencia
        
        return min(100, max(0, forca_real))
    
    def get_status_formatado(self, estrategia):
        """Retorna status formatado para exibição"""
        taxa = self.get_taxa_real(estrategia)
        total = self.get_total_tentativas(estrategia)
        tendencia = self.get_tendencia(estrategia)
        
        if total < 3:
            return f"⚪ COLETANDO ({total} tentativas)"
        
        if taxa >= 0.40:
            cor = "🟢"
            status = "QUENTE"
        elif taxa >= 0.25:
            cor = "🟡"
            status = "MORNA"
        else:
            cor = "🔴"
            status = "FRIA"
        
        tendencia_emoji = {'subindo': '📈', 'caindo': '📉', 'estavel': '➡️', 'neutra': '⚪'}.get(tendencia, '')
        
        return f"{cor} {status} {tendencia_emoji} ({taxa:.0%} | {total} tentativas)"


# =============================
# ESTRATÉGIA 1: DOMINANTE
# =============================
class EstrategiaDominante:
    def __init__(self):
        self.roleta = RoletaBase()
        self.nome = "Dominante"
        self.seletor = SeletorInteligente()
        
    def _calcular_forca_condicao(self, numero, hist_list, transicoes, ocorrencias_6):
        forca = 0
        
        freq_6 = ocorrencias_6 / 6
        forca += freq_6 * 40
        
        if numero in transicoes:
            trans = transicoes[numero]
            if trans:
                total_trans = sum(trans.values())
                top1_count = trans.most_common(1)[0][1] if trans else 0
                if total_trans > 0:
                    confianca_trans = top1_count / total_trans
                    forca += confianca_trans * 40
        
        if len(hist_list) > 0 and hist_list[-1] == numero:
            forca += 20
        
        return min(100, int(forca))
    
    def detectar(self, hist_list, ultimo, matriz_transicao, expandir_vizinhos=True, 
                 max_numeros=15, qtd_antes=3, qtd_depois=3):
        if len(hist_list) < 8:  # Reduzido de 10 para 8
            return None, 0
        
        ultimas_6 = hist_list[-6:] if len(hist_list) >= 6 else hist_list
        ocorrencias_6 = ultimas_6.count(ultimo)
        
        # Reduzido de 2 para 1 ocorrência (mais permissivo)
        if ocorrencias_6 < 1:
            return None, 0
        
        if ultimo not in matriz_transicao:
            return None, 0
        
        transicoes = matriz_transicao[ultimo]
        if not transicoes:
            return None, 0
        
        top_transicoes = [num for num, _ in transicoes.most_common(2)]
        if len(top_transicoes) == 0:
            return None, 0
        
        forca_condicao = self._calcular_forca_condicao(ultimo, hist_list, matriz_transicao, ocorrencias_6)
        
        numeros_base = set(top_transicoes[:2])
        numeros_base.add(ultimo)
        num_originais = len(numeros_base)
        
        if expandir_vizinhos:
            numeros_final, _ = self.seletor.expandir_com_vizinhos(
                list(numeros_base), hist_list, max_numeros, qtd_antes, qtd_depois
            )
            expandido = len(numeros_final) > num_originais
        else:
            numeros_final = self.seletor.selecionar_melhores(list(numeros_base), hist_list, max_numeros)
            expandido = False
        
        resultado = {
            'nome': self.nome,
            'numeros_apostar': sorted(numeros_final),
            'gatilho': f"⚡ Dominante: {ultimo} ({ocorrencias_6}x em 6 rodadas) → {top_transicoes[:2]}",
            'forca_condicao': forca_condicao,
            'numero_dominante': ultimo,
            'transicoes': top_transicoes[:2],
            'tipo': 'dominante',
            'expandido': expandido,
            'num_originais': num_originais
        }
        
        return resultado, forca_condicao


# =============================
# ESTRATÉGIA 2: RUPTURA
# =============================
class EstrategiaRuptura:
    def __init__(self):
        self.roleta = RoletaBase()
        self.nome = "Ruptura"
        self.seletor = SeletorInteligente()
        
    def _detectar_sequencia_proxima(self, hist_list):
        if len(hist_list) < 3:
            return False, []
        
        ultimos_3 = hist_list[-3:]
        
        # Repetição (mais permissivo)
        if len(set(ultimos_3)) <= 2:
            return True, ultimos_3
        
        # Proximidade numérica (ampliado)
        ordenados = sorted(ultimos_3)
        if ordenados[-1] - ordenados[0] <= 10:  # Aumentado de 6 para 10
            return True, ultimos_3
        
        # Proximidade na roda
        distancias = []
        for i in range(len(ultimos_3)):
            for j in range(i+1, len(ultimos_3)):
                dist = self.roleta.get_distancia_roda(ultimos_3[i], ultimos_3[j])
                distancias.append(dist)
        
        if distancias and min(distancias) <= 6:  # Aumentado de 4 para 6
            return True, ultimos_3
        
        return False, []
    
    def _calcular_forca_condicao(self, hist_list, sequencia):
        forca = 0
        
        if len(hist_list) >= 4:
            ultimos_4 = hist_list[-4:]
            if len(set(ultimos_4)) <= 3:
                forca += 40
            else:
                forca += 25
        else:
            forca += 25
        
        if len(sequencia) >= 3:
            ordenados = sorted(sequencia)
            amplitude = ordenados[-1] - ordenados[0]
            if amplitude <= 6:
                forca += 40
            elif amplitude <= 10:
                forca += 30
            else:
                forca += 20
        
        if len(hist_list) >= 5:
            saltos = []
            for i in range(1, min(5, len(hist_list))):
                saltos.append(abs(hist_list[-i] - hist_list[-i-1]))
            if saltos:
                saltos_curtos = sum(1 for s in saltos if s <= 8)  # Aumentado de 6 para 8
                forca += (saltos_curtos / len(saltos)) * 20
        
        return min(100, int(forca))
    
    def detectar(self, hist_list, ultimo, expandir_vizinhos=True, 
                 max_numeros=15, qtd_antes=3, qtd_depois=3):
        if len(hist_list) < 4:  # Reduzido de 5 para 4
            return None, 0
        
        tem_sequencia, sequencia = self._detectar_sequencia_proxima(hist_list)
        
        if not tem_sequencia:
            return None, 0
        
        forca_condicao = self._calcular_forca_condicao(hist_list, sequencia)
        
        numeros_base = set()
        
        for num in sequencia[-2:]:
            opostos = self.roleta.get_opostos_regiao(num, quantidade=3)
            numeros_base.update(opostos)
        
        if ultimo:
            for i in range(37):
                if abs(i - ultimo) >= 15:  # Reduzido de 19 para 15
                    numeros_base.add(i)
                    if len(numeros_base) >= 8:
                        break
        
        numeros_base_list = list(numeros_base)
        num_originais = len(numeros_base_list)
        
        if expandir_vizinhos:
            numeros_final, _ = self.seletor.expandir_com_vizinhos(
                numeros_base_list, hist_list, max_numeros, qtd_antes, qtd_depois
            )
            expandido = len(numeros_final) > num_originais
        else:
            numeros_final = self.seletor.selecionar_melhores(numeros_base_list, hist_list, max_numeros)
            expandido = False
        
        resultado = {
            'nome': self.nome,
            'numeros_apostar': sorted(numeros_final),
            'gatilho': f"💣 Ruptura: sequência {sequencia} → esperando QUEBRA",
            'forca_condicao': forca_condicao,
            'sequencia': sequencia,
            'tipo': 'ruptura',
            'expandido': expandido,
            'num_originais': num_originais
        }
        
        return resultado, forca_condicao


# =============================
# ESTRATÉGIA 3: CICLO REAL
# =============================
class EstrategiaCicloReal:
    def __init__(self):
        self.roleta = RoletaBase()
        self.nome = "Ciclo Real"
        self.tolerancia_janela = 3  # Aumentado de 2 para 3
        self.seletor = SeletorInteligente()
        
    def _encontrar_ciclos(self, hist_list):
        ciclos = {}
        
        for num in range(37):
            posicoes = [i for i, n in enumerate(hist_list) if n == num]
            
            if len(posicoes) >= 2:  # Reduzido de 3 para 2
                intervalos = []
                for i in range(1, len(posicoes)):
                    intervalos.append(posicoes[i] - posicoes[i-1])
                
                if len(intervalos) >= 1:  # Reduzido de 2 para 1
                    media = sum(intervalos) / len(intervalos)
                    variancia = sum((i - media) ** 2 for i in intervalos) / len(intervalos) if len(intervalos) > 1 else 2
                    
                    if variancia <= 6 and media >= 3:  # Mais permissivo
                        ciclos[num] = {
                            'media': media,
                            'ultimo_intervalo': intervalos[-1] if intervalos else media,
                            'posicao_ultimo': posicoes[-1],
                            'consistencia': 100 - min(100, variancia * 8)
                        }
        
        return ciclos
    
    def _calcular_forca_condicao(self, num, ciclo_info, hist_list):
        forca = 0
        
        forca += ciclo_info['consistencia'] * 0.5
        
        rodadas_desde_ultimo = len(hist_list) - 1 - ciclo_info['posicao_ultimo']
        media = ciclo_info['media']
        
        if rodadas_desde_ultimo >= media - 3:  # Mais permissivo            proximidade = 1 - abs(rodadas_desde_ultimo - media) / media
            forca += proximidade * 30
        
        if len(hist_list) > 0:
            ultimos_10 = hist_list[-10:]
            freq_recente = ultimos_10.count(num) / 10
            forca += freq_recente * 20
        
        return min(100, int(forca))
    
    def detectar(self, hist_list, ultimo, expandir_vizinhos=True, 
                 max_numeros=15, qtd_antes=3, qtd_depois=3):
        if len(hist_list) < 10:  # Reduzido de 15 para 10
            return None, 0
        
        ciclos = self._encontrar_ciclos(hist_list)
        
        if not ciclos:
            return None, 0
        
        ciclos_ordenados = sorted(ciclos.items(), key=lambda x: x[1]['consistencia'], reverse=True)
        
        for num, info in ciclos_ordenados[:5]:  # Aumentado de 3 para 5
            rodadas_desde_ultimo = len(hist_list) - 1 - info['posicao_ultimo']
            media = info['media']
            
            if abs(rodadas_desde_ultimo - media) <= self.tolerancia_janela:
                forca_condicao = self._calcular_forca_condicao(num, info, hist_list)
                
                numeros_base = [num]
                num_originais = 1
                
                if expandir_vizinhos:
                    numeros_final, _ = self.seletor.expandir_com_vizinhos(
                        numeros_base, hist_list, max_numeros, qtd_antes, qtd_depois
                    )
                    expandido = len(numeros_final) > num_originais
                else:
                    vizinhos = self.roleta.get_vizinhos(num, raio=2)
                    numeros_base.extend(vizinhos)
                    numeros_final = self.seletor.selecionar_melhores(numeros_base, hist_list, max_numeros)
                    expandido = False
                
                resultado = {
                    'nome': self.nome,
                    'numeros_apostar': sorted(numeros_final),
                    'gatilho': f"🌀 Ciclo: {num} volta a cada ~{media:.0f} rodadas (agora: {rodadas_desde_ultimo})",
                    'forca_condicao': forca_condicao,
                    'numero_ciclo': num,
                    'media_ciclo': media,
                    'tipo': 'ciclo_real',
                    'expandido': expandido,
                    'num_originais': num_originais
                }
                
                return resultado, forca_condicao
        
        return None, 0


# =============================
# DETECTOR DE GATILHOS UNIFICADO
# =============================
class DetectorGatilhosUnificado:
    def __init__(self, motor_performance):
        self.roleta = RoletaBase()
        self.motor = motor_performance
        
        self.estrategias_map = {
            'Dominante': EstrategiaDominante(),
            'Ruptura': EstrategiaRuptura(),
            'CicloReal': EstrategiaCicloReal()
        }
        
        self.ordem_prioridade = ['Dominante', 'Ruptura', 'CicloReal']
        
    def detectar(self, hist_list, hist_mult, ultimo, matriz_transicao, ciclos_numeros,
                 estrategias_ativas=None, forca_minima=45, taxa_minima=20,
                 expandir_vizinhos=True, max_numeros=15, qtd_antes=3, qtd_depois=3):
        
        if len(hist_list) < 4:
            return None
        
        if estrategias_ativas is None:
            estrategias_ativas = {nome: True for nome in self.ordem_prioridade}
        
        melhor_resultado = None
        maior_forca = 0
        
        for nome in self.ordem_prioridade:
            if not estrategias_ativas.get(nome, True):
                continue
            
            # VERIFICA SE ESTRATÉGIA É VÁLIDA
            if not self.motor.is_estrategia_valida(nome, taxa_minima / 100):
                continue
            
            estrategia = self.estrategias_map[nome]
            resultado = None
            forca_condicao = 0
            
            if nome == 'Dominante':
                resultado, forca_condicao = estrategia.detectar(
                    hist_list, ultimo, matriz_transicao,
                    expandir_vizinhos, max_numeros, qtd_antes, qtd_depois
                )
            elif nome == 'Ruptura':
                resultado, forca_condicao = estrategia.detectar(
                    hist_list, ultimo,
                    expandir_vizinhos, max_numeros, qtd_antes, qtd_depois
                )
            elif nome == 'CicloReal':
                resultado, forca_condicao = estrategia.detectar(
                    hist_list, ultimo,
                    expandir_vizinhos, max_numeros, qtd_antes, qtd_depois
                )
            
            if resultado:
                forca_real = self.motor.calcular_forca_real(nome, forca_condicao)
                taxa_real = self.motor.get_taxa_real(nome)
                
                resultado['forca_real'] = forca_real
                resultado['forca_condicao'] = forca_condicao
                resultado['taxa_real'] = taxa_real * 100
                resultado['confianca'] = 'Alta' if forca_real >= 55 else 'Média'
                
                if forca_real >= forca_minima:
                    if forca_real > maior_forca:
                        maior_forca = forca_real
                        melhor_resultado = resultado
        
        return melhor_resultado


# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaAutoAdaptativo:
    def __init__(self):
        self.motor_performance = MotorPerformance()
        self.detector = DetectorGatilhosUnificado(self.motor_performance)
        self.roleta = RoletaBase()
        
        self.historico_numeros = deque(maxlen=200)
        self.historico_multiplicadores = deque(maxlen=200)
        
        self.matriz_transicao = defaultdict(Counter)
        self.ciclos_numeros = {}
        
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        
        self.rodadas_sem_entrada = 0
        self.ultima_entrada_rodada = -10
        self.intervalo_minimo_entradas = 1  # Reduzido para 1
        
        self.estrategia_ativa_manual = False
        self.performance = self.motor_performance.performance
        
    def _atualizar_matriz_transicao(self, hist_list):
        if len(hist_list) < 2:
            return
        
        for i in range(len(hist_list) - 1):
            atual = hist_list[i]
            proximo = hist_list[i + 1]
            self.matriz_transicao[atual][proximo] += 1
    
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            numero_real = numero_data['number']
            lucky = numero_data.get('luckyNumbers', [])
            mult = numero_data.get('luckyMultipliers', {}).get(numero_real) if numero_real in lucky else None
        else:
            numero_real = numero_data
            lucky = []
            mult = None
        
        self.historico_numeros.append(numero_real)
        self.historico_multiplicadores.append(mult if mult else 0)
        self._atualizar_matriz_transicao(list(self.historico_numeros))
        self.rodadas_sem_entrada += 1
        
        # Verifica resultado da previsão anterior
        if self.previsao_ativa:
            acerto = numero_real in self.previsao_ativa.get('numeros_apostar', [])
            nome = self.previsao_ativa['nome']
            
            self.motor_performance.atualizar_resultado(nome, acerto)
            
            if nome not in self.estrategias_contador:
                self.estrategias_contador[nome] = {'acertos': 0, 'total': 0, 'forca_media': 0}
            self.estrategias_contador[nome]['total'] += 1
            
            if acerto:
                self.estrategias_contador[nome]['acertos'] += 1
                self.acertos += 1
            else:
                self.erros += 1
            
            forca = self.previsao_ativa.get('forca_real', 0)
            if self.estrategias_contador[nome]['total'] > 0:
                self.estrategias_contador[nome]['forca_media'] = (
                    (self.estrategias_contador[nome]['forca_media'] * (self.estrategias_contador[nome]['total'] - 1) + forca)
                    / self.estrategias_contador[nome]['total']
                )
            
            enviar_resultado_auto(numero_real, acerto, nome, mult)
            
            self.historico_desempenho.append({
                'numero': numero_real,
                'acerto': acerto,
                'estrategia': nome,
                'multiplicador': mult,
                'forca': forca
            })
            
            self.previsao_ativa = None
            self.ultima_entrada_rodada = len(self.historico_numeros)
            self.rodadas_sem_entrada = 0
        
        if self.estrategia_ativa_manual:
            return
        
        # Usa intervalo configurável
        intervalo = st.session_state.get('intervalo_minimo_entradas', 1)
        rodadas_desde_ultima = len(self.historico_numeros) - self.ultima_entrada_rodada
        if rodadas_desde_ultima < intervalo:
            return
        
        hist_list = list(self.historico_numeros)
        if len(hist_list) > 0:
            ultimo = hist_list[-1]
            
            estrategias_ativas = st.session_state.get('estrategias_ativas', {
                'Dominante': True, 'Ruptura': True, 'CicloReal': True
            })
            
            forca_minima = st.session_state.get('forca_minima_sinal', 45)
            taxa_minima = st.session_state.get('taxa_minima_estrategia', 20)
            expandir_vizinhos = st.session_state.get('expandir_com_vizinhos', True)
            max_numeros = st.session_state.get('max_numeros_entrada', 15)
            qtd_antes = st.session_state.get('qtd_vizinhos_antes', 3)
            qtd_depois = st.session_state.get('qtd_vizinhos_depois', 3)
            
            nova = self.detector.detectar(
                hist_list,
                self.historico_multiplicadores,
                ultimo,
                self.matriz_transicao,
                self.ciclos_numeros,
                estrategias_ativas,
                forca_minima,
                taxa_minima,
                expandir_vizinhos,
                max_numeros,
                qtd_antes,
                qtd_depois
            )
            
            if nova:
                self.previsao_ativa = nova
                enviar_previsao_auto(nova)
    
    def zerar_estatisticas(self):
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.historico_desempenho = []
        self.historico_numeros.clear()
        self.historico_multiplicadores.clear()
        self.matriz_transicao.clear()
        self.ciclos_numeros.clear()
        self.rodadas_sem_entrada = 0
        self.ultima_entrada_rodada = -10
        
        self.motor_performance = MotorPerformance()
        self.performance = self.motor_performance.performance
        self.detector = DetectorGatilhosUnificado(self.motor_performance)
        
        salvar_sessao()
    
    def get_analise_completa(self):
        if len(self.historico_numeros) < 3:
            return "📊 Aguardando dados..."
        
        hist_list = list(self.historico_numeros)
        ultimo = hist_list[-1]
        
        analise = "🎯 ANÁLISE DE PERFORMANCE\n"
        analise += "=" * 40 + "\n\n"
        analise += f"🎲 Último: {ultimo}\n"
        analise += f"📊 Últimos 8: {hist_list[-8:]}\n\n"
        
        for nome in ['Dominante', 'Ruptura', 'CicloReal']:
            status = self.motor_performance.get_status_formatado(nome)
            emoji = {'Dominante': '⚡', 'Ruptura': '💣', 'CicloReal': '🌀'}.get(nome, '🎲')
            analise += f"{emoji} {nome}: {status}\n"
        
        forca_min = st.session_state.get('forca_minima_sinal', 45)
        analise += f"\n⚙️ Força mín: {forca_min}%\n"
        analise += f"📊 Rodadas sem entrada: {self.rodadas_sem_entrada}\n"
        
        return analise
    
    def get_status(self):
        return {
            'acertos': self.acertos,
            'erros': self.erros,
            'total': self.acertos + self.erros,
            'rodadas_sem_entrada': self.rodadas_sem_entrada
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
st.set_page_config(page_title="🎯 IA Roleta — Motor Adaptativo", layout="centered")
st.title("🎯 IA Roleta — Motor com Aprendizado Real")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaAutoAdaptativo()

# Inicializa configurações com valores MAIS PERMISSIVOS
if "estrategias_ativas" not in st.session_state:
    st.session_state.estrategias_ativas = {'Dominante': True, 'Ruptura': True, 'CicloReal': True}

if "forca_minima_sinal" not in st.session_state:
    st.session_state.forca_minima_sinal = 45  # Reduzido de 65 para 45

if "taxa_minima_estrategia" not in st.session_state:
    st.session_state.taxa_minima_estrategia = 20  # Reduzido de 40 para 20

if "expandir_com_vizinhos" not in st.session_state:
    st.session_state.expandir_com_vizinhos = True

if "max_numeros_entrada" not in st.session_state:
    st.session_state.max_numeros_entrada = 15

if "qtd_vizinhos_antes" not in st.session_state:
    st.session_state.qtd_vizinhos_antes = 3

if "qtd_vizinhos_depois" not in st.session_state:
    st.session_state.qtd_vizinhos_depois = 3

if "modo_adaptativo" not in st.session_state:
    st.session_state.modo_adaptativo = True

if "intervalo_minimo_entradas" not in st.session_state:
    st.session_state.intervalo_minimo_entradas = 1  # Reduzido para 1

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

# ===== MODO ADAPTATIVO =====
with st.sidebar.expander("🧠 Motor Adaptativo", expanded=True):
    st.session_state.modo_adaptativo = st.checkbox(
        "🔄 Modo Adaptativo", value=st.session_state.modo_adaptativo
    )
    
    st.session_state.taxa_minima_estrategia = st.slider(
        "📊 Taxa mínima p/ bloquear",
        min_value=10, max_value=40, value=st.session_state.taxa_minima_estrategia, step=5,
        help="Estratégia com taxa abaixo disso é BLOQUEADA (após 5+ tentativas)"
    )
    
    st.session_state.intervalo_minimo_entradas = st.slider(
        "⏱️ Intervalo entre entradas",
        min_value=0, max_value=5, value=st.session_state.intervalo_minimo_entradas, step=1,
        help="0 = pode entrar toda rodada"
    )

# ===== FILTRO DE FORÇA =====
with st.sidebar.expander("🎚️ Filtro de Força", expanded=True):
    st.session_state.forca_minima_sinal = st.slider(
        "Força mínima para entrar",
        min_value=35, max_value=70, value=st.session_state.forca_minima_sinal, step=5
    )
    
    forca = st.session_state.forca_minima_sinal
    if forca <= 45:
        st.success(f"🟢 PERMISSIVO ({forca}%) - Mais entradas")
    elif forca <= 55:
        st.warning(f"🟡 EQUILIBRADO ({forca}%)")
    else:
        st.error(f"🔴 RESTRITIVO ({forca}%) - Menos entradas")

# ===== CONFIGURAÇÕES DE EXPANSÃO =====
with st.sidebar.expander("🔧 Expansão com Vizinhos", expanded=False):
    st.session_state.expandir_com_vizinhos = st.checkbox(
        "🔄 Expandir com vizinhos", value=st.session_state.expandir_com_vizinhos
    )
    
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.qtd_vizinhos_antes = st.number_input(
            "⬅️ Antes", min_value=1, max_value=5, value=st.session_state.qtd_vizinhos_antes
        )
    with col2:
        st.session_state.qtd_vizinhos_depois = st.number_input(
            "➡️ Depois", min_value=1, max_value=5, value=st.session_state.qtd_vizinhos_depois
        )
    
    st.session_state.max_numeros_entrada = st.slider(
        "📊 Máx números", min_value=5, max_value=20, value=st.session_state.max_numeros_entrada
    )

# ===== ESTRATÉGIAS =====
with st.sidebar.expander("⚡ Estratégias", expanded=True):
    st.session_state.estrategias_ativas['Dominante'] = st.checkbox(
        "⚡ DOMINANTE", value=st.session_state.estrategias_ativas['Dominante']
    )
    st.session_state.estrategias_ativas['Ruptura'] = st.checkbox(
        "💣 RUPTURA", value=st.session_state.estrategias_ativas['Ruptura']
    )
    st.session_state.estrategias_ativas['CicloReal'] = st.checkbox(
        "🌀 CICLO REAL", value=st.session_state.estrategias_ativas['CicloReal']
    )
    
    ativas = sum(1 for v in st.session_state.estrategias_ativas.values() if v)
    st.caption(f"📊 {ativas}/3 ativas")

with st.sidebar.expander("💾 Gerenciamento", expanded=False):
    if st.button("💾 Salvar Sessão", use_container_width=True):
        salvar_sessao()
        st.success("✅ Sessão salva!")
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

# Controle Manual/Automático
st.sidebar.subheader("🎮 Modo")
modo_auto = st.sidebar.checkbox("🔄 Automático", value=not st.session_state.sistema.estrategia_ativa_manual)
if st.sidebar.button("Atualizar Modo"):
    st.session_state.sistema.estrategia_ativa_manual = not modo_auto
    st.rerun()

# Análise
with st.sidebar.expander("🔍 Análise", expanded=True):
    analise = st.session_state.sistema.get_analise_completa()
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

# Auto-refresh
st_autorefresh(interval=3000, key="refresh")

# Busca API
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
col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 Acertos", status['acertos'])
col2.metric("🔴 Erros", status['erros'])
col3.metric("📊 Total", status['total'])
col4.metric("⏳ Sem Entrada", status['rodadas_sem_entrada'])

if status['total'] > 0:
    taxa = status['acertos'] / status['total'] * 100
    st.caption(f"🎯 Taxa de Acerto: {taxa:.1f}%")

# Previsão Ativa
st.subheader("🎯 Previsão Ativa")
sistema = st.session_state.sistema

if sistema.estrategia_ativa_manual:
    st.warning("⚠️ MODO MANUAL ATIVO")
elif sistema.previsao_ativa:
    p = sistema.previsao_ativa
    emoji = {'Dominante': '⚡', 'Ruptura': '💣', 'Ciclo Real': '🌀'}.get(p['nome'], '🎲')
    forca_real = p.get('forca_real', 0)
    forca_cond = p.get('forca_condicao', 0)
    taxa_real = p.get('taxa_real', 0)
    
    barras = "█" * (int(forca_real) // 10) + "░" * (10 - int(forca_real) // 10)
    
    st.success(f"{emoji} **{p['nome'].upper()}** - FORÇA {forca_real:.0f}% {barras}")
    st.caption(f"📊 Taxa: {taxa_real:.0f}% | Cond: {forca_cond:.0f}%")
    st.info(f"📋 **Gatilho:** {p['gatilho']}")
    
    st.write(f"**🔢 Números ({len(p['numeros_apostar'])}):**")
    nums = sorted(p['numeros_apostar'])
    colunas = st.columns(5)
    for i, num in enumerate(nums):
        colunas[i % 5].write(f"**{num}**")
else:
    st.info(f"🎲 Aguardando gatilho... ({status['rodadas_sem_entrada']} rodadas sem entrada)")

# Performance das Estratégias
st.subheader("📈 Performance por Estratégia")

for nome in ['Dominante', 'Ruptura', 'CicloReal']:
    taxa = sistema.motor_performance.get_taxa_real(nome)
    total = sistema.motor_performance.get_total_tentativas(nome)
    tendencia = sistema.motor_performance.get_tendencia(nome)
    valida = sistema.motor_performance.is_estrategia_valida(nome, st.session_state.taxa_minima_estrategia / 100)
    
    emoji = {'Dominante': '⚡', 'Ruptura': '💣', 'CicloReal': '🌀'}.get(nome, '🎲')
    tendencia_emoji = {'subindo': '📈', 'caindo': '📉', 'estavel': '➡️', 'neutra': '⚪'}.get(tendencia, '')
    
    if total < 3:
        cor = "⚪"
        status_str = f"{cor} {emoji} **{nome}**: COLETANDO ({total} tentativas)"
    elif taxa >= 0.40:
        cor = "🟢"
        status_str = f"{cor} {emoji} **{nome}**: {taxa:.0%} ({total} tentativas) {tendencia_emoji}"
    elif taxa >= 0.25:
        cor = "🟡"
        status_str = f"{cor} {emoji} **{nome}**: {taxa:.0%} ({total} tentativas) {tendencia_emoji}"
    else:
        cor = "🔴"
        status_str = f"{cor} {emoji} **{nome}**: {taxa:.0%} ({total} tentativas) {tendencia_emoji}"
    
    if not valida and total >= 5:
        status_str += f" 🚫"
    
    st.write(status_str)

# Histórico recente
if sistema.historico_desempenho:
    st.write("**🔍 Últimas Conferências:**")
    for r in sistema.historico_desempenho[-5:]:
        emoji_result = "🎉" if r['acerto'] else "❌"
        mult = f" ⚡{r['multiplicador']}x" if r.get('multiplicador') and r['acerto'] else ""
        forca = r.get('forca', 0)
        st.write(f"{emoji_result} {r['estrategia']} ({forca:.0f}%): {r['numero']}{mult}")

salvar_sessao()
