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
            'historico_numeros': list(st.session_state.sistema.historico_numeros),
            'historico_multiplicadores': list(st.session_state.sistema.historico_multiplicadores),
            'estrategia_ativa_manual': st.session_state.sistema.estrategia_ativa_manual,
            'matriz_transicao': dict(st.session_state.sistema.matriz_transicao),
            'ciclos_numeros': st.session_state.sistema.ciclos_numeros,
            'estrategias_ativas': st.session_state.get('estrategias_ativas', {
                'Dominante': True, 'Ruptura': True, 'CicloReal': True
            }),
            'forca_minima_sinal': st.session_state.get('forca_minima_sinal', 70),
            'expandir_com_vizinhos': st.session_state.get('expandir_com_vizinhos', True),
            'max_numeros_entrada': st.session_state.get('max_numeros_entrada', 6)
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
            
            # Carrega estratégias ativas (apenas as 3 de elite)
            st.session_state.estrategias_ativas = session_data.get('estrategias_ativas', {
                'Dominante': True, 'Ruptura': True, 'CicloReal': True
            })
            
            # Carrega configurações
            st.session_state.forca_minima_sinal = session_data.get('forca_minima_sinal', 70)
            st.session_state.expandir_com_vizinhos = session_data.get('expandir_com_vizinhos', True)
            st.session_state.max_numeros_entrada = session_data.get('max_numeros_entrada', 6)
            
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
        forca = previsao.get('forca_sinal', 0)
        
        emojis = {
            'Dominante': '⚡',
            'Ruptura': '💣',
            'Ciclo Real': '🌀'
        }
        emoji = emojis.get(nome, '🎲')
        
        # Barra de força visual
        barras = "█" * (forca // 10) + "░" * (10 - forca // 10)
        
        msg = f"{emoji} **{nome.upper()}** ATIVADA!\n"
        msg += f"📊 Força: {barras} {forca}%\n"
        msg += f"📋 {gatilho}"
        
        st.toast(f"🎯 {nome} - Força {forca}%", icon=emoji)
        
        # Só mostra em destaque se força alta
        if forca >= 70:
            st.success(f"🔔 **SINAL FORTE!** {msg}")
        elif forca >= 50:
            st.warning(f"🔔 {msg}")
        else:
            st.info(f"🔔 {msg}")
        
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
    
    def get_vizinhos_anteriores(self, numero, quantidade=2):
        """Retorna os vizinhos anteriores (esquerda) na roda"""
        if numero not in self.race:
            return []
        posicao = self.race.index(numero)
        vizinhos = []
        for i in range(1, quantidade + 1):
            vizinhos.append(self.race[(posicao - i) % 37])
        return vizinhos
    
    def get_vizinhos_posteriores(self, numero, quantidade=2):
        """Retorna os vizinhos posteriores (direita) na roda"""
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
        """Retorna números opostos na roda (região oposta)"""
        if numero not in self.race:
            return []
        posicao = self.race.index(numero)
        opostos = []
        for offset in range(-1, quantidade - 1):
            opostos.append(self.race[(posicao + 18 + offset) % 37])
        return opostos
    
    def get_distancia_roda(self, num1, num2):
        """Calcula distância entre dois números na roda"""
        if num1 not in self.race or num2 not in self.race:
            return 37
        p1 = self.race.index(num1)
        p2 = self.race.index(num2)
        dist = abs(p1 - p2)
        return min(dist, 37 - dist)

# =============================
# ESTRATÉGIA 1: DOMINANTE (TRANSIÇÃO + CONFIRMAÇÃO)
# =============================
class EstrategiaDominante:
    """
    Só entra quando existe comportamento repetível confirmado
    Gatilho DUPLO:
    1. Número atual tem histórico de transição forte
    2. E esse número apareceu 2x nas últimas 6 rodadas
    """
    
    def __init__(self):
        self.roleta = RoletaBase()
        self.nome = "Dominante"
        self.min_ocorrencias = 3  # Precisa ter aparecido pelo menos 3x no histórico
        
    def _calcular_forca_sinal(self, numero, hist_list, transicoes, ocorrencias_6):
        """Calcula força do sinal de 0-100%"""
        forca = 0
        
        # 1. Frequência nas últimas 6 rodadas (40%)
        freq_6 = ocorrencias_6 / 6
        forca += freq_6 * 40
        
        # 2. Força das transições (40%)
        if numero in transicoes:
            trans = transicoes[numero]
            if trans:
                total_trans = sum(trans.values())
                top1_count = trans.most_common(1)[0][1] if trans else 0
                if total_trans > 0:
                    confianca_trans = top1_count / total_trans
                    forca += confianca_trans * 40
        
        # 3. Recência (20%)
        if len(hist_list) > 0 and hist_list[-1] == numero:
            forca += 20
        
        return min(100, int(forca))
    
    def detectar(self, hist_list, ultimo, matriz_transicao, forca_minima=70):
        if len(hist_list) < 10:
            return None
        
        # Verifica ocorrências nas últimas 6 rodadas
        ultimas_6 = hist_list[-6:] if len(hist_list) >= 6 else hist_list
        ocorrencias_6 = ultimas_6.count(ultimo)
        
        # Precisa de pelo menos 2x nas últimas 6
        if ocorrencias_6 < 2:
            return None
        
        # Verifica transições fortes
        if ultimo not in matriz_transicao:
            return None
        
        transicoes = matriz_transicao[ultimo]
        if not transicoes:
            return None
        
        # Pega top 2 transições
        top_transicoes = [num for num, _ in transicoes.most_common(2)]
        
        if len(top_transicoes) == 0:
            return None
        
        # Calcula força do sinal
        forca = self._calcular_forca_sinal(ultimo, hist_list, matriz_transicao, ocorrencias_6)
        
        # Só entra se força >= mínima
        if forca < forca_minima:
            return None
        
        # Monta números: TOP 2 transições + 1 vizinho
        numeros = set(top_transicoes[:2])
        
        # Adiciona 1 vizinho do número dominante
        vizinhos = self.roleta.get_vizinhos(ultimo, raio=1)
        if vizinhos:
            numeros.add(vizinhos[0])
        
        # Garante que o próprio número está incluído
        numeros.add(ultimo)
        
        return {
            'nome': self.nome,
            'numeros_apostar': sorted(list(numeros)),
            'gatilho': f"⚡ Dominante: {ultimo} (2x em 6 rodadas) → {top_transicoes[:2]}",
            'confianca': 'Muito Alta' if forca >= 80 else 'Alta',
            'forca_sinal': forca,
            'numero_dominante': ultimo,
            'transicoes': top_transicoes[:2],
            'tipo': 'dominante'
        }


# =============================
# ESTRATÉGIA 2: RUPTURA (ANTI-PADRÃO)
# =============================
class EstrategiaRuptura:
    """
    Quando o sistema entra em sequência → ele quebra forte
    Gatilho FORTE:
    - 3 números próximos OU repetição (tipo: 15 → 18 → 15)
    - E salto pequeno dominante
    Entrada: OPOSTOS no wheel (ou salto longo)
    """
    
    def __init__(self):
        self.roleta = RoletaBase()
        self.nome = "Ruptura"
        
    def _detectar_sequencia_proxima(self, hist_list):
        """Detecta se há 3 números próximos ou com repetição"""
        if len(hist_list) < 3:
            return False, []
        
        ultimos_3 = hist_list[-3:]
        
        # Verifica repetição
        if len(set(ultimos_3)) <= 2:
            return True, ultimos_3
        
        # Verifica proximidade numérica
        ordenados = sorted(ultimos_3)
        if ordenados[-1] - ordenados[0] <= 6:
            return True, ultimos_3
        
        # Verifica proximidade na roda
        distancias = []
        for i in range(len(ultimos_3)):
            for j in range(i+1, len(ultimos_3)):
                dist = self.roleta.get_distancia_roda(ultimos_3[i], ultimos_3[j])
                distancias.append(dist)
        
        if distancias and min(distancias) <= 4:
            return True, ultimos_3
        
        return False, []
    
    def _calcular_forca_sinal(self, hist_list, sequencia):
        """Calcula força do sinal de ruptura"""
        forca = 0
        
        # 1. Tamanho da sequência (40%)
        if len(hist_list) >= 4:
            ultimos_4 = hist_list[-4:]
            if len(set(ultimos_4)) <= 3:
                forca += 40
            else:
                forca += 20
        else:
            forca += 20
        
        # 2. Proximidade dos números (40%)
        if len(sequencia) >= 3:
            ordenados = sorted(sequencia)
            amplitude = ordenados[-1] - ordenados[0]
            if amplitude <= 4:
                forca += 40
            elif amplitude <= 8:
                forca += 30
            else:
                forca += 20
        
        # 3. Salto pequeno dominante (20%)
        if len(hist_list) >= 5:
            saltos = []
            for i in range(1, min(5, len(hist_list))):
                saltos.append(abs(hist_list[-i] - hist_list[-i-1]))
            if saltos:
                saltos_curtos = sum(1 for s in saltos if s <= 6)
                forca += (saltos_curtos / len(saltos)) * 20
        
        return min(100, int(forca))
    
    def detectar(self, hist_list, ultimo, forca_minima=70):
        if len(hist_list) < 5:
            return None
        
        # Detecta sequência próxima
        tem_sequencia, sequencia = self._detectar_sequencia_proxima(hist_list)
        
        if not tem_sequencia:
            return None
        
        # Calcula força do sinal
        forca = self._calcular_forca_sinal(hist_list, sequencia)
        
        if forca < forca_minima:
            return None
        
        # Gera números opostos (ruptura)
        numeros = set()
        
        # Pega opostos de cada número da sequência
        for num in sequencia[-2:]:  # Últimos 2 números
            opostos = self.roleta.get_opostos_regiao(num, quantidade=2)
            numeros.update(opostos)
        
        # Adiciona alguns números de salto longo
        if ultimo:
            for i in range(37):
                if abs(i - ultimo) >= 19:
                    numeros.add(i)
                    if len(numeros) >= 6:
                        break
        
        # Limita a 6 números
        numeros_final = list(numeros)[:6]
        
        return {
            'nome': self.nome,
            'numeros_apostar': sorted(numeros_final),
            'gatilho': f"💣 Ruptura: sequência {sequencia} → esperando QUEBRA",
            'confianca': 'Muito Alta' if forca >= 80 else 'Alta',
            'forca_sinal': forca,
            'sequencia': sequencia,
            'tipo': 'ruptura'
        }


# =============================
# ESTRATÉGIA 3: CICLO REAL
# =============================
class EstrategiaCicloReal:
    """
    Não é número atrasado... É número que sempre volta em janela fixa
    Gatilho: Número apareceu 2x com intervalo parecido
    Entrada: Esperar mesma janela
    """
    
    def __init__(self):
        self.roleta = RoletaBase()
        self.nome = "Ciclo Real"
        self.tolerancia_janela = 2  # ±2 rodadas de tolerância
        
    def _encontrar_ciclos(self, hist_list):
        """Encontra números que aparecem em intervalos regulares"""
        ciclos = {}
        
        for num in range(37):
            posicoes = [i for i, n in enumerate(hist_list) if n == num]
            
            if len(posicoes) >= 3:
                intervalos = []
                for i in range(1, len(posicoes)):
                    intervalos.append(posicoes[i] - posicoes[i-1])
                
                # Verifica se os intervalos são consistentes
                if len(intervalos) >= 2:
                    media = sum(intervalos) / len(intervalos)
                    # Calcula variância
                    variancia = sum((i - media) ** 2 for i in intervalos) / len(intervalos)
                    
                    # Se variância baixa = ciclo consistente
                    if variancia <= 4 and media >= 4:
                        ciclos[num] = {
                            'media': media,
                            'ultimo_intervalo': intervalos[-1],
                            'posicao_ultimo': posicoes[-1],
                            'consistencia': 100 - min(100, variancia * 10)
                        }
        
        return ciclos
    
    def _calcular_forca_sinal(self, ciclo_info, hist_list):
        """Calcula força do sinal do ciclo"""
        forca = 0
        
        # 1. Consistência do ciclo (50%)
        forca += ciclo_info['consistencia'] * 0.5
        
        # 2. Proximidade da janela esperada (30%)
        rodadas_desde_ultimo = len(hist_list) - 1 - ciclo_info['posicao_ultimo']
        media = ciclo_info['media']
        
        if rodadas_desde_ultimo >= media - 2:
            proximidade = 1 - abs(rodadas_desde_ultimo - media) / media
            forca += proximidade * 30
        
        # 3. Número apareceu recentemente? (20%)
        if len(hist_list) > 0:
            ultimos_10 = hist_list[-10:]
            freq_recente = ultimos_10.count(list(ciclo_info.keys())[0] if isinstance(ciclo_info, dict) else 0) / 10
            forca += freq_recente * 20
        
        return min(100, int(forca))
    
    def detectar(self, hist_list, ultimo, forca_minima=70):
        if len(hist_list) < 15:
            return None
        
        ciclos = self._encontrar_ciclos(hist_list)
        
        if not ciclos:
            return None
        
        # Ordena por consistência
        ciclos_ordenados = sorted(ciclos.items(), key=lambda x: x[1]['consistencia'], reverse=True)
        
        for num, info in ciclos_ordenados[:3]:  # Avalia top 3
            rodadas_desde_ultimo = len(hist_list) - 1 - info['posicao_ultimo']
            media = info['media']
            
            # Verifica se está na janela esperada
            if abs(rodadas_desde_ultimo - media) <= self.tolerancia_janela:
                
                forca = self._calcular_forca_sinal({'info': info, 'numero': num}, hist_list)
                
                if forca < forca_minima:
                    continue
                
                # Monta entrada: número do ciclo + vizinhos
                numeros = {num}
                vizinhos = self.roleta.get_vizinhos(num, raio=2)
                numeros.update(vizinhos[:3])
                
                return {
                    'nome': self.nome,
                    'numeros_apostar': sorted(list(numeros)),
                    'gatilho': f"🌀 Ciclo: {num} volta a cada ~{media:.0f} rodadas (agora: {rodadas_desde_ultimo})",
                    'confianca': 'Muito Alta' if forca >= 80 else 'Alta',
                    'forca_sinal': forca,
                    'numero_ciclo': num,
                    'media_ciclo': media,
                    'tipo': 'ciclo_real'
                }
        
        return None


# =============================
# DETECTOR DE GATILHOS UNIFICADO (APENAS 3 ESTRATÉGIAS)
# =============================
class DetectorGatilhosUnificado:
    """Avalia apenas as 3 estratégias de elite"""
    
    def __init__(self):
        self.roleta = RoletaBase()
        
        # Apenas 3 estratégias de elite
        self.estrategias_map = {
            'Dominante': EstrategiaDominante(),
            'Ruptura': EstrategiaRuptura(),
            'CicloReal': EstrategiaCicloReal()
        }
        
        # Ordem de prioridade
        self.ordem_prioridade = ['Dominante', 'Ruptura', 'CicloReal']
        
    def detectar(self, hist_list, hist_mult, ultimo, matriz_transicao, ciclos_numeros,
                 estrategias_ativas=None, forca_minima=70):
        """
        Avalia as estratégias ATIVAS e retorna a primeira com força suficiente
        """
        if len(hist_list) < 10:
            return None
        
        if estrategias_ativas is None:
            estrategias_ativas = {nome: True for nome in self.ordem_prioridade}
        
        melhor_resultado = None
        maior_forca = 0
        
        for nome in self.ordem_prioridade:
            # Pula se estratégia não estiver ativa
            if not estrategias_ativas.get(nome, True):
                continue
            
            estrategia = self.estrategias_map[nome]
            resultado = None
            
            if nome == 'Dominante':
                resultado = estrategia.detectar(hist_list, ultimo, matriz_transicao, forca_minima)
            elif nome == 'Ruptura':
                resultado = estrategia.detectar(hist_list, ultimo, forca_minima)
            elif nome == 'CicloReal':
                resultado = estrategia.detectar(hist_list, ultimo, forca_minima)
            
            if resultado:
                forca = resultado.get('forca_sinal', 0)
                if forca > maior_forca:
                    maior_forca = forca
                    melhor_resultado = resultado
        
        return melhor_resultado


# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaAutoAdaptativo:
    def __init__(self):
        self.detector = DetectorGatilhosUnificado()
        self.roleta = RoletaBase()
        
        # Históricos
        self.historico_numeros = deque(maxlen=200)
        self.historico_multiplicadores = deque(maxlen=200)
        
        # Matriz de transição
        self.matriz_transicao = defaultdict(Counter)
        self.ciclos_numeros = {}
        
        # Previsão e desempenho
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        
        # Controle de entrada (evitar entrar toda hora)
        self.rodadas_sem_entrada = 0
        self.ultima_entrada_rodada = -10
        self.intervalo_minimo_entradas = 2  # Mínimo 2 rodadas entre entradas
        
        # Controle manual
        self.estrategia_ativa_manual = False
        
    def _atualizar_matriz_transicao(self, hist_list):
        """Atualiza matriz de transição"""
        if len(hist_list) < 2:
            return
        
        for i in range(len(hist_list) - 1):
            atual = hist_list[i]
            proximo = hist_list[i + 1]
            self.matriz_transicao[atual][proximo] += 1
    
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
        
        # Adiciona aos históricos
        self.historico_numeros.append(numero_real)
        self.historico_multiplicadores.append(mult if mult else 0)
        
        # Atualiza matriz de transição
        self._atualizar_matriz_transicao(list(self.historico_numeros))
        
        # Incrementa contador de rodadas sem entrada
        self.rodadas_sem_entrada += 1
        
        # Verifica resultado da previsão anterior
        if self.previsao_ativa:
            acerto = numero_real in self.previsao_ativa.get('numeros_apostar', [])
            nome = self.previsao_ativa['nome']
            
            if nome not in self.estrategias_contador:
                self.estrategias_contador[nome] = {'acertos': 0, 'total': 0, 'forca_media': 0}
            self.estrategias_contador[nome]['total'] += 1
            
            if acerto:
                self.estrategias_contador[nome]['acertos'] += 1
                self.acertos += 1
            else:
                self.erros += 1
            
            # Atualiza força média
            forca = self.previsao_ativa.get('forca_sinal', 0)
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
        
        # Se modo manual ativado, não gera previsão automática
        if self.estrategia_ativa_manual:
            return
        
        # VERIFICA SE PODE ENTRAR (evitar entrada excessiva)
        rodadas_desde_ultima = len(self.historico_numeros) - self.ultima_entrada_rodada
        if rodadas_desde_ultima < self.intervalo_minimo_entradas:
            return
        
        # DETECTA GATILHOS AUTOMATICAMENTE
        hist_list = list(self.historico_numeros)
        if len(hist_list) > 0:
            ultimo = hist_list[-1]
            
            # Obtém configurações
            estrategias_ativas = st.session_state.get('estrategias_ativas', {
                'Dominante': True, 'Ruptura': True, 'CicloReal': True
            })
            
            forca_minima = st.session_state.get('forca_minima_sinal', 70)
            
            nova = self.detector.detectar(
                hist_list,
                self.historico_multiplicadores,
                ultimo,
                self.matriz_transicao,
                self.ciclos_numeros,
                estrategias_ativas,
                forca_minima
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
        salvar_sessao()
    
    def get_analise_completa(self):
        """Retorna análise completa"""
        if len(self.historico_numeros) < 5:
            return "📊 Aguardando dados para análise..."
        
        hist_list = list(self.historico_numeros)
        ultimo = hist_list[-1]
        
        analise = "🎯 ANÁLISE DE ELITE (APENAS 3 ESTRATÉGIAS)\n"
        analise += "=" * 50 + "\n\n"
        analise += f"🎲 Último: {ultimo}\n"
        analise += f"📊 Últimos 10: {hist_list[-10:]}\n\n"
        
        analise += "📈 STATUS DAS ESTRATÉGIAS:\n"
        analise += "-" * 30 + "\n"
        
        estrategias_ativas = st.session_state.get('estrategias_ativas', {})
        for nome in ['Dominante', 'Ruptura', 'CicloReal']:
            status = "✅ ATIVA" if estrategias_ativas.get(nome, True) else "❌ INATIVA"
            emoji = {'Dominante': '⚡', 'Ruptura': '💣', 'CicloReal': '🌀'}.get(nome, '🎲')
            analise += f"{emoji} {nome}: {status}\n"
        
        forca_minima = st.session_state.get('forca_minima_sinal', 70)
        analise += f"\n⚙️ Força mínima: {forca_minima}%\n"
        analise += f"📊 Rodadas desde última entrada: {self.rodadas_sem_entrada}\n"
        
        analise += "\n" + "=" * 50 + "\n"
        
        # Mostra transições do último número
        if ultimo in self.matriz_transicao and self.matriz_transicao[ultimo]:
            analise += f"\n⚡ Transições após {ultimo}:\n"
            for prox, count in self.matriz_transicao[ultimo].most_common(3):
                analise += f"  → {prox}: {count}x\n"
        
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
st.set_page_config(page_title="🎯 IA Roleta — 3 Estratégias de Elite", layout="centered")
st.title("🎯 IA Roleta — Sistema de Elite (Qualidade > Quantidade)")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaAutoAdaptativo()

# Inicializa configurações
if "estrategias_ativas" not in st.session_state:
    st.session_state.estrategias_ativas = {
        'Dominante': True, 'Ruptura': True, 'CicloReal': True
    }

if "forca_minima_sinal" not in st.session_state:
    st.session_state.forca_minima_sinal = 70

if "expandir_com_vizinhos" not in st.session_state:
    st.session_state.expandir_com_vizinhos = True

if "max_numeros_entrada" not in st.session_state:
    st.session_state.max_numeros_entrada = 6

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

# ===== FILTRO DE FORÇA =====
with st.sidebar.expander("🎚️ Filtro de Força", expanded=True):
    st.write("**Força Mínima do Sinal:**")
    
    st.session_state.forca_minima_sinal = st.slider(
        "Só entrar com força ≥",
        min_value=50,
        max_value=90,
        value=st.session_state.forca_minima_sinal,
        step=5,
        help="Quanto maior, menos entradas (mais qualidade)"
    )
    
    # Indicador visual
    forca = st.session_state.forca_minima_sinal
    if forca >= 80:
        st.success(f"🔒 MUITO RESTRITIVO ({forca}%) - Poucas entradas, alta precisão")
    elif forca >= 70:
        st.warning(f"⚖️ EQUILIBRADO ({forca}%) - Bom balanço")
    else:
        st.error(f"⚠️ PERMISSIVO ({forca}%) - Mais entradas, menos precisão")
    
    st.caption("💡 70% é o recomendado")

# ===== ESTRATÉGIAS DE ELITE =====
with st.sidebar.expander("⚡ Estratégias de Elite", expanded=True):
    st.write("**Apenas 3 estratégias com filtro pesado:**")
    
    st.session_state.estrategias_ativas['Dominante'] = st.checkbox(
        "⚡ DOMINANTE (Transição + Confirmação)", 
        value=st.session_state.estrategias_ativas['Dominante'],
        help="Gatilho DUPLO: 2x em 6 rodadas + transição forte"
    )
    
    st.session_state.estrategias_ativas['Ruptura'] = st.checkbox(
        "💣 RUPTURA (Anti-Padrão)", 
        value=st.session_state.estrategias_ativas['Ruptura'],
        help="Sequência próxima → espera QUEBRA (pega explosão)"
    )
    
    st.session_state.estrategias_ativas['CicloReal'] = st.checkbox(
        "🌀 CICLO REAL", 
        value=st.session_state.estrategias_ativas['CicloReal'],
        help="Número que volta em janela fixa (não é atraso comum)"
    )
    
    ativas = sum(1 for v in st.session_state.estrategias_ativas.values() if v)
    st.caption(f"📊 {ativas}/3 estratégias ativas")
    
    if st.button("💾 Salvar Configurações", use_container_width=True):
        salvar_sessao()
        st.success("✅ Configurações salvas!")

# ===== ESTRATÉGIAS REMOVIDAS (AVISO) =====
with st.sidebar.expander("🚫 Estratégias Removidas", expanded=False):
    st.warning("""
    **REMOVIDAS POR BAIXA PERFORMANCE:**
    
    ❌ Entropia (ruim no curto prazo)
    ❌ Núcleo Quente puro
    ❌ Cluster fraco
    ❌ Bloco simples
    ❌ Salto
    ❌ Agrupamento
    ❌ Compressão
    ❌ Markov puro
    
    **MOTIVO:** Muito ruído → baixa assertividade
    """)

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

# Controle Manual/Automático
st.sidebar.subheader("🎮 Modo de Operação")
modo_auto = st.sidebar.checkbox("🔄 Modo Automático", value=not st.session_state.sistema.estrategia_ativa_manual)
if st.sidebar.button("Atualizar Modo"):
    st.session_state.sistema.estrategia_ativa_manual = not modo_auto
    st.rerun()

if st.session_state.sistema.estrategia_ativa_manual:
    st.sidebar.warning("⚠️ Modo MANUAL")
else:
    st.sidebar.success("✅ Modo AUTOMÁTICO")

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

# Taxa de acerto
if status['total'] > 0:
    taxa = status['acertos'] / status['total'] * 100
    st.caption(f"🎯 Taxa de Acerto: {taxa:.1f}%")
    
    if taxa >= 35:
        st.success(f"✅ PERFORMANCE EXCELENTE! {taxa:.1f}% está acima da meta de 35%")
    elif taxa >= 25:
        st.warning(f"📊 PERFORMANCE DENTRO DO ESPERADO: {taxa:.1f}%")
    else:
        st.error(f"⚠️ ABAIXO DO ESPERADO: {taxa:.1f}% - Aumente a força mínima")

# Previsão Ativa
st.subheader("🎯 Previsão Ativa")
sistema = st.session_state.sistema

if sistema.estrategia_ativa_manual:
    st.warning("⚠️ MODO MANUAL ATIVO")
elif sistema.previsao_ativa:
    p = sistema.previsao_ativa
    emoji = {'Dominante': '⚡', 'Ruptura': '💣', 'Ciclo Real': '🌀'}.get(p['nome'], '🎲')
    forca = p.get('forca_sinal', 0)
    
    # Barra de força
    barras = "█" * (forca // 10) + "░" * (10 - forca // 10)
    
    if forca >= 80:
        st.success(f"{emoji} **{p['nome'].upper()}** - FORÇA {forca}% {barras}")
    elif forca >= 70:
        st.warning(f"{emoji} **{p['nome'].upper()}** - FORÇA {forca}% {barras}")
    else:
        st.info(f"{emoji} **{p['nome'].upper()}** - FORÇA {forca}% {barras}")
    
    st.info(f"📋 **Gatilho:** {p['gatilho']}")
    st.write(f"**🔢 Números ({len(p['numeros_apostar'])}):**")
    
    nums = sorted(p['numeros_apostar'])
    colunas = st.columns(6)
    for i, num in enumerate(nums):
        colunas[i % 6].write(f"**{num}**")
else:
    ativas = sum(1 for v in st.session_state.estrategias_ativas.values() if v)
    if ativas == 0:
        st.warning("⚠️ Nenhuma estratégia ativa!")
    else:
        rodadas = status['rodadas_sem_entrada']
        if rodadas > 5:
            st.info(f"🎲 Aguardando gatilho forte... ({rodadas} rodadas sem entrada)")
        else:
            st.info("🎲 Analisando padrões...")

# Desempenho por Estratégia
st.subheader("📈 Desempenho por Estratégia")

if sistema.estrategias_contador:
    desempenho_ordenado = []
    for nome, dados in sistema.estrategias_contador.items():
        if dados['total'] > 0:
            tx = dados['acertos'] / dados['total'] * 100
            forca_media = dados.get('forca_media', 0)
            desempenho_ordenado.append((nome, dados, tx, forca_media))
    
    desempenho_ordenado.sort(key=lambda x: x[2], reverse=True)
    
    for nome, dados, tx, forca_media in desempenho_ordenado:
        if tx >= 35:
            cor = "🟢"
        elif tx >= 25:
            cor = "🟡"
        else:
            cor = "🔴"
        
        emoji = {'Dominante': '⚡', 'Ruptura': '💣', 'Ciclo Real': '🌀'}.get(nome, '🎲')
        st.write(f"{cor} {emoji} {nome}: {dados['acertos']}/{dados['total']} ({tx:.1f}%) | Força média: {forca_media:.0f}%")

# Histórico recente
if sistema.historico_desempenho:
    st.write("**🔍 Últimas Conferências:**")
    for r in sistema.historico_desempenho[-5:]:
        emoji_result = "🎉" if r['acerto'] else "❌"
        mult = f" ⚡{r['multiplicador']}x" if r.get('multiplicador') and r['acerto'] else ""
        forca = r.get('forca', 0)
        st.write(f"{emoji_result} {r['estrategia']} ({forca}%): {r['numero']}{mult}")

# Download
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        st.download_button("📥 Baixar histórico", data=f.read(), file_name="historico_roleta.json")

salvar_sessao()
