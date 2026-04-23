import streamlit as st
import json
import os
import requests
import logging
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
            'sistema_historico_desempenho': st.session_state.sistema.historico_desempenho,
            'historico_numeros': list(st.session_state.sistema.historico_numeros),
            'historico_multiplicadores': list(st.session_state.sistema.historico_multiplicadores),
            'estrategia_ativa_manual': st.session_state.sistema.estrategia_ativa_manual,
            'modo_sniper': st.session_state.get('modo_sniper', False),
            'modo_seguro': st.session_state.get('modo_seguro', True),
            'intervalo_minimo_entradas': st.session_state.get('intervalo_minimo_entradas', 1),
            'expandir_com_vizinhos': st.session_state.get('expandir_com_vizinhos', True),
            'max_numeros_entrada': st.session_state.get('max_numeros_entrada', 15),
            'forca_minima_sinal': st.session_state.get('forca_minima_sinal', 40),
            'qtd_vizinhos_antes': st.session_state.get('qtd_vizinhos_antes', 2),
            'qtd_vizinhos_depois': st.session_state.get('qtd_vizinhos_depois', 2)
        }
        
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f)
        
        # Salva performance
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
            
            st.session_state.modo_sniper = session_data.get('modo_sniper', False)
            st.session_state.modo_seguro = session_data.get('modo_seguro', True)
            st.session_state.intervalo_minimo_entradas = session_data.get('intervalo_minimo_entradas', 1)
            st.session_state.expandir_com_vizinhos = session_data.get('expandir_com_vizinhos', True)
            st.session_state.max_numeros_entrada = session_data.get('max_numeros_entrada', 15)
            st.session_state.forca_minima_sinal = session_data.get('forca_minima_sinal', 40)
            st.session_state.qtd_vizinhos_antes = session_data.get('qtd_vizinhos_antes', 2)
            st.session_state.qtd_vizinhos_depois = session_data.get('qtd_vizinhos_depois', 2)
            
            if 'sistema' in st.session_state:
                st.session_state.sistema.acertos = session_data.get('sistema_acertos', 0)
                st.session_state.sistema.erros = session_data.get('sistema_erros', 0)
                st.session_state.sistema.historico_desempenho = session_data.get('sistema_historico_desempenho', [])
                st.session_state.sistema.historico_numeros = deque(session_data.get('historico_numeros', []), maxlen=200)
                st.session_state.sistema.historico_multiplicadores = deque(session_data.get('historico_multiplicadores', []), maxlen=200)
                st.session_state.sistema.estrategia_ativa_manual = session_data.get('estrategia_ativa_manual', False)
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
        numeros = sorted(previsao['numeros_apostar'])
        gatilho = previsao['gatilho']
        forca = previsao.get('forca_sinal', 0)
        tipo_entrada = previsao.get('tipo_entrada', 'normal')
        num_originais = previsao.get('num_originais', len(numeros))
        
        emoji = "🎯" if tipo_entrada == 'sniper' else "🛡️" if tipo_entrada == 'seguro' else "🎲"
        
        barras = "█" * (forca // 10) + "░" * (10 - forca // 10)
        
        msg = f"{emoji} **ENTRADA DINÂMICA**\n"
        msg += f"📊 Força: {barras} {forca}%\n"
        msg += f"📈 Expandido: {num_originais} → {len(numeros)} números\n"
        msg += f"📋 {gatilho}"
        
        st.toast(f"🎯 Entrada - Força {forca}%", icon=emoji)
        
        if forca >= 70:
            st.success(f"🔔 **SINAL FORTE!** {msg}")
        elif forca >= 50:
            st.warning(f"🔔 {msg}")
        else:
            st.info(f"🔔 {msg}")
        
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            enviar_telegram(f"🔔 ENTRADA DINÂMICA\n{msg}")
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

def enviar_resultado_auto(numero_real, acerto, multiplicador=None):
    """Envia notificação de resultado"""
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
        # Roda europeia (ordem física real)
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
    
    def get_vizinhos_anteriores(self, numero, quantidade=2):
        """Retorna vizinhos anteriores (esquerda) na roda"""
        if numero not in self.race:
            return []
        posicao = self.race.index(numero)
        vizinhos = []
        for i in range(1, quantidade + 1):
            vizinhos.append(self.race[(posicao - i) % 37])
        return vizinhos
    
    def get_vizinhos_posteriores(self, numero, quantidade=2):
        """Retorna vizinhos posteriores (direita) na roda"""
        if numero not in self.race:
            return []
        posicao = self.race.index(numero)
        vizinhos = []
        for i in range(1, quantidade + 1):
            vizinhos.append(self.race[(posicao + i) % 37])
        return vizinhos
    
    def get_distancia_roda(self, num1, num2):
        """Calcula distância entre dois números na roda"""
        if num1 not in self.race or num2 not in self.race:
            return 37
        p1 = self.race.index(num1)
        p2 = self.race.index(num2)
        dist = abs(p1 - p2)
        return min(dist, 37 - dist)


# =============================
# SELETOR INTELIGENTE (EXPANSÃO COM VIZINHOS)
# =============================
class SeletorInteligente:
    """Expande e seleciona os melhores números"""
    
    def __init__(self):
        self.roleta = RoletaBase()
    
    def expandir_com_vizinhos(self, numeros_base, historico, max_numeros=15,
                              qtd_antes=2, qtd_depois=2):
        """Expande cada número com vizinhos antes e depois"""
        if len(numeros_base) == 0:
            return [], 0
        
        num_originais = len(numeros_base)
        numeros_expandidos = set(numeros_base)
        
        for num in numeros_base:
            # Adiciona vizinhos anteriores
            anteriores = self.roleta.get_vizinhos_anteriores(num, qtd_antes)
            numeros_expandidos.update(anteriores)
            
            # Adiciona vizinhos posteriores
            posteriores = self.roleta.get_vizinhos_posteriores(num, qtd_depois)
            numeros_expandidos.update(posteriores)
        
        lista_expandida = list(numeros_expandidos)
        
        if len(lista_expandida) <= max_numeros:
            return sorted(lista_expandida), num_originais
        
        # Seleciona os melhores
        selecionados = self.selecionar_melhores(lista_expandida, historico, max_numeros)
        return selecionados, num_originais
    
    def selecionar_melhores(self, numeros_candidatos, historico, max_numeros=15):
        """Seleciona os melhores números baseado em múltiplos critérios"""
        if len(numeros_candidatos) <= max_numeros:
            return sorted(numeros_candidatos)
        
        hist_list = list(historico)
        scores = {}
        
        # Peso dos critérios
        PESO_FREQ_RECENTE = 0.30      # Frequência nos últimos 20
        PESO_FREQ_CURTA = 0.20        # Frequência nos últimos 5
        PESO_REPETICAO = 0.20         # Repetiu recentemente?
        PESO_PROXIMIDADE = 0.15       # Proximidade com últimos números
        PESO_ATRASO = 0.10            # Não saiu há tempo?
        PESO_ZERO = 0.05              # Bônus para o 0
        
        ultimos_5 = hist_list[-5:] if len(hist_list) >= 5 else hist_list
        ultimos_20 = hist_list[-20:] if len(hist_list) >= 20 else hist_list
        ultimo = hist_list[-1] if hist_list else None
        
        for num in numeros_candidatos:
            score = 0
            
            # 1. Frequência recente (30%)
            freq_20 = ultimos_20.count(num) / len(ultimos_20) if ultimos_20 else 0
            score += freq_20 * PESO_FREQ_RECENTE * 100
            
            # 2. Frequência curta (20%)
            freq_5 = ultimos_5.count(num) / len(ultimos_5) if ultimos_5 else 0
            score += freq_5 * PESO_FREQ_CURTA * 100
            
            # 3. Repetição (20%)
            if len(hist_list) >= 2 and num == ultimo:
                score += PESO_REPETICAO * 100
            elif num in ultimos_5 and ultimos_5.count(num) >= 2:
                score += PESO_REPETICAO * 70
            
            # 4. Proximidade com últimos números (15%)
            if ultimos_5:
                for recente in ultimos_5[-3:]:
                    dist = self.roleta.get_distancia_roda(num, recente)
                    if dist <= 3:
                        score += PESO_PROXIMIDADE * 100 * (1 - dist/4)
            
            # 5. Atraso (10%) - números que não saem há tempo
            if num not in ultimos_20:
                score += PESO_ATRASO * 50
            
            # 6. Bônus para o 0 (5%)
            if num == 0:
                score += PESO_ZERO * 100
            
            scores[num] = score
        
        # Ordena por score
        ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        selecionados = [num for num, _ in ordenados[:max_numeros]]
        
        return sorted(selecionados)


# =============================
# MOTOR IA COM BASE 100% DINÂMICA
# =============================
class RoletaIA:
    """
    IA que calcula base dinâmica a cada rodada
    SEM LISTAS FIXAS - apenas leitura viva do comportamento atual
    """
    
    def __init__(self):
        self.roleta = RoletaBase()
        self.seletor = SeletorInteligente()
        self.historico = deque(maxlen=100)
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        
        # Cache de análise para evitar recalcular
        self.ultima_analise = None
        self.ultimo_numero = None
        
    def atualizar(self, numero):
        """Atualiza histórico com novo número"""
        self.historico.append(numero)
        self.ultimo_numero = numero
        self.ultima_analise = None  # Invalida cache
        
    def atualizar_resultado(self, acerto):
        """Atualiza performance"""
        self.performance['historico'].append(1 if acerto else 0)
        if len(self.performance['historico']) > 50:
            self.performance['historico'] = self.performance['historico'][-50:]
        
        if acerto:
            self.performance['acertos'] += 1
        else:
            self.performance['erros'] += 1
    
    def get_taxa_acerto(self):
        """Retorna taxa de acerto recente"""
        total = self.performance['acertos'] + self.performance['erros']
        if total == 0:
            return 0.5
        return self.performance['acertos'] / total
    
    def get_taxa_recente(self, ultimas=10):
        """Taxa de acerto nas últimas N tentativas"""
        if len(self.performance['historico']) < ultimas:
            return self.get_taxa_acerto()
        recentes = self.performance['historico'][-ultimas:]
        return sum(recentes) / len(recentes) if recentes else 0.5
    
    def analisar(self):
        """
        Analisa o estado atual da roleta
        Retorna: quentes, repetidos, bloco, forca_sinal, padroes
        """
        # Usa cache se disponível
        if self.ultima_analise is not None:
            return self.ultima_analise
        
        if len(self.historico) < 8:
            return None
        
        hist_list = list(self.historico)
        ultimos_15 = hist_list[-15:] if len(hist_list) >= 15 else hist_list
        ultimos_5 = hist_list[-5:] if len(hist_list) >= 5 else hist_list
        ultimos_3 = hist_list[-3:] if len(hist_list) >= 3 else hist_list
        ultimo = hist_list[-1]
        
        # 1. Frequência recente
        freq_15 = Counter(ultimos_15)
        quentes = [n for n, _ in freq_15.most_common(6)]
        
        # 2. Repetição (prioridade máxima)
        repetidos = [n for n in ultimos_5 if ultimos_5.count(n) >= 2]
        
        # 3. Padrão de sequência (números consecutivos iguais)
        sequencia_ativa = False
        numero_sequencia = None
        if len(hist_list) >= 3:
            if hist_list[-1] == hist_list[-2] == hist_list[-3]:
                sequencia_ativa = True
                numero_sequencia = ultimo
        
        # 4. Bloco (alto/baixo)
        altos_15 = sum(1 for n in ultimos_15 if n > 18)
        baixos_15 = len(ultimos_15) - altos_15
        
        altos_5 = sum(1 for n in ultimos_5 if n > 18)
        baixos_5 = len(ultimos_5) - altos_5
        
        bloco_15 = "alto" if altos_15 > baixos_15 else "baixo"
        bloco_5 = "alto" if altos_5 > baixos_5 else "baixo"
        
        # 5. Análise de vizinhança (cluster físico)
        cluster_fisico = False
        regiao_ativa = []
        if len(ultimos_5) >= 3:
            distancias = []
            for i in range(len(ultimos_5)):
                for j in range(i+1, len(ultimos_5)):
                    dist = self.roleta.get_distancia_roda(ultimos_5[i], ultimos_5[j])
                    distancias.append(dist)
            if distancias and min(distancias) <= 4:
                cluster_fisico = True
                # Encontra números da região
                for n in ultimos_5:
                    if any(self.roleta.get_distancia_roda(n, m) <= 4 for m in ultimos_5 if m != n):
                        regiao_ativa.append(n)
        
        # 6. Força do sinal (calculada dinamicamente)
        forca = 40  # Base
        
        # Repetição aumenta MUITO a força
        if sequencia_ativa:
            forca += 30
        elif len(repetidos) >= 2:
            forca += 20
        elif len(repetidos) >= 1:
            forca += 10
        
        # Frequência do último número
        freq_ultimo_15 = ultimos_15.count(ultimo)
        forca += freq_ultimo_15 * 5
        
        # Cluster físico aumenta força
        if cluster_fisico:
            forca += 15
        
        # Consistência do bloco
        if bloco_15 == bloco_5:
            forca += 10
        
        # Performance recente da IA
        taxa_recente = self.get_taxa_recente(5)
        if taxa_recente >= 0.4:
            forca += 10
        elif taxa_recente <= 0.2:
            forca -= 10
        
        forca = min(100, max(25, int(forca)))
        
        self.ultima_analise = {
            "quentes": quentes,
            "repetidos": list(set(repetidos)),
            "bloco_15": bloco_15,
            "bloco_5": bloco_5,
            "altos_15": altos_15,
            "baixos_15": baixos_15,
            "sequencia_ativa": sequencia_ativa,
            "numero_sequencia": numero_sequencia,
            "cluster_fisico": cluster_fisico,
            "regiao_ativa": list(set(regiao_ativa)),
            "forca_sinal": forca,
            "ultimo": ultimo,
            "ultimos_3": ultimos_3
        }
        
        return self.ultima_analise
    
    def prever(self, modo_sniper=False, modo_seguro=False, max_numeros=15,
               expandir_vizinhos=True, qtd_antes=2, qtd_depois=2):
        """
        Gera previsão com base 100% dinâmica
        """
        if len(self.historico) < 8:
            return None
        
        dados = self.analisar()
        if not dados:
            return None
        
        ultimo = dados["ultimo"]
        
        # BASE DINÂMICA (construída do zero a cada rodada)
        base = set()
        
        # 🔥 Último número (sempre inclui)
        base.add(ultimo)
        
        # 🔁 Repetição tem PRIORIDADE MÁXIMA
        for n in dados["repetidos"]:
            base.add(n)
        
        # 🔥 Número em sequência (máxima prioridade)
        if dados["sequencia_ativa"] and dados["numero_sequencia"]:
            base.add(dados["numero_sequencia"])
        
        # 🎰 Cluster físico - adiciona região ativa
        if dados["cluster_fisico"]:
            for n in dados["regiao_ativa"][:4]:
                base.add(n)
        
        # 🔥 Números quentes (frequência recente)
        for n in dados["quentes"][:4]:
            base.add(n)
        
        # Últimos 3 números
        for n in dados["ultimos_3"]:
            base.add(n)
        
        # Números base originais (antes da expansão)
        numeros_base = list(base)
        num_originais = len(numeros_base)
        
        # 🌊 EXPANSÃO COM VIZINHOS
        if expandir_vizinhos:
            numeros_final, _ = self.seletor.expandir_com_vizinhos(
                numeros_base, self.historico, max_numeros, qtd_antes, qtd_depois
            )
        else:
            if len(numeros_base) > max_numeros:
                numeros_final = self.seletor.selecionar_melhores(numeros_base, self.historico, max_numeros)
            else:
                numeros_final = sorted(numeros_base)
        
        # 🌊 Ajuste de bloco (filtrar por contexto)
        if dados["bloco_5"] == "alto" and dados["bloco_15"] == "alto":
            # Bloco forte de altos - favorece altos
            numeros_altos = [n for n in numeros_final if n > 18]
            if len(numeros_altos) >= 5:
                numeros_final = numeros_altos
        elif dados["bloco_5"] == "baixo" and dados["bloco_15"] == "baixo":
            # Bloco forte de baixos - favorece baixos
            numeros_baixos = [n for n in numeros_final if n <= 18]
            if len(numeros_baixos) >= 5:
                numeros_final = numeros_baixos
        
        # Aplica modos
        if modo_sniper:
            tipo_entrada = "sniper"
            max_final = 7
        elif modo_seguro:
            tipo_entrada = "seguro"
            max_final = 12
        else:
            tipo_entrada = "normal"
            max_final = 10
        
        # Limita ao máximo
        if len(numeros_final) > max_final:
            numeros_final = self.seletor.selecionar_melhores(numeros_final, self.historico, max_final)
        
        # Gera descrição do gatilho
        gatilho_parts = [f"último={ultimo}"]
        if dados["repetidos"]:
            gatilho_parts.append(f"repetidos={dados['repetidos']}")
        if dados["sequencia_ativa"]:
            gatilho_parts.append(f"sequência={dados['numero_sequencia']}")
        if dados["cluster_fisico"]:
            gatilho_parts.append("cluster físico")
        gatilho_parts.append(f"bloco={dados['bloco_5']}")
        
        return {
            'nome': 'IA Dinâmica',
            'numeros_apostar': sorted(numeros_final),
            'gatilho': f"🎯 " + ", ".join(gatilho_parts),
            'forca_sinal': dados['forca_sinal'],
            'confianca': 'Alta' if dados['forca_sinal'] >= 70 else 'Média',
            'tipo_entrada': tipo_entrada,
            'dados_analise': dados,
            'num_originais': num_originais,
            'expandido': expandir_vizinhos
        }
    
    def get_analise_completa(self):
        """Retorna análise detalhada"""
        if len(self.historico) < 5:
            return "📊 Aguardando dados..."
        
        dados = self.analisar()
        if not dados:
            return "📊 Analisando..."
        
        hist_list = list(self.historico)
        
        analise = "🎯 ANÁLISE IA DINÂMICA\n"
        analise += "=" * 40 + "\n\n"
        analise += f"🎲 Último: {dados['ultimo']}\n"
        analise += f"📊 Últimos 10: {hist_list[-10:]}\n\n"
        
        analise += f"🔥 Quentes (15): {dados['quentes'][:5]}\n"
        analise += f"🔁 Repetidos (5): {dados['repetidos']}\n"
        
        if dados['sequencia_ativa']:
            analise += f"💥 SEQUÊNCIA ATIVA: {dados['numero_sequencia']}\n"
        
        if dados['cluster_fisico']:
            analise += f"🎰 Cluster físico: {dados['regiao_ativa'][:4]}\n"
        
        analise += f"🌊 Bloco (15): {dados['bloco_15']} (A:{dados['altos_15']} B:{dados['baixos_15']})\n"
        analise += f"⚡ Força: {dados['forca_sinal']}%\n"
        
        taxa = self.get_taxa_acerto()
        taxa_rec = self.get_taxa_recente(5)
        total = self.performance['acertos'] + self.performance['erros']
        analise += f"\n📈 Performance: {taxa:.0%} ({self.performance['acertos']}/{total})"
        analise += f"\n📊 Recente (5): {taxa_rec:.0%}\n"
        
        return analise
    
    def zerar(self):
        """Zera estatísticas"""
        self.historico.clear()
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.ultima_analise = None
        self.ultimo_numero = None


# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaIA:
    def __init__(self):
        self.ia = RoletaIA()
        
        # Históricos
        self.historico_numeros = deque(maxlen=200)
        self.historico_multiplicadores = deque(maxlen=200)
        
        # Previsão e desempenho
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        
        # Controle de entrada
        self.rodadas_sem_entrada = 0
        self.ultima_entrada_rodada = -10
        
        # Controle manual
        self.estrategia_ativa_manual = False
        self.performance = self.ia.performance
        
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
        
        # Atualiza IA
        self.ia.atualizar(numero_real)
        self.historico_numeros.append(numero_real)
        self.historico_multiplicadores.append(mult if mult else 0)
        self.rodadas_sem_entrada += 1
        
        # Verifica resultado da previsão anterior
        if self.previsao_ativa:
            acerto = numero_real in self.previsao_ativa.get('numeros_apostar', [])
            
            # Atualiza performance da IA
            self.ia.atualizar_resultado(acerto)
            
            if acerto:
                self.acertos += 1
            else:
                self.erros += 1
            
            enviar_resultado_auto(numero_real, acerto, mult)
            
            self.historico_desempenho.append({
                'numero': numero_real,
                'acerto': acerto,
                'multiplicador': mult,
                'forca': self.previsao_ativa.get('forca_sinal', 0)
            })
            
            self.previsao_ativa = None
            self.ultima_entrada_rodada = len(self.historico_numeros)
            self.rodadas_sem_entrada = 0
        
        # Se modo manual, não gera previsão
        if self.estrategia_ativa_manual:
            return
        
        # Verifica intervalo mínimo
        intervalo = st.session_state.get('intervalo_minimo_entradas', 1)
        rodadas_desde_ultima = len(self.historico_numeros) - self.ultima_entrada_rodada
        if rodadas_desde_ultima < intervalo:
            return
        
        # Gera nova previsão com IA dinâmica
        if len(self.historico_numeros) >= 8:
            modo_sniper = st.session_state.get('modo_sniper', False)
            modo_seguro = st.session_state.get('modo_seguro', True)
            max_numeros = st.session_state.get('max_numeros_entrada', 15)
            expandir = st.session_state.get('expandir_com_vizinhos', True)
            qtd_antes = st.session_state.get('qtd_vizinhos_antes', 2)
            qtd_depois = st.session_state.get('qtd_vizinhos_depois', 2)
            
            nova = self.ia.prever(
                modo_sniper, modo_seguro, max_numeros,
                expandir, qtd_antes, qtd_depois
            )
            
            if nova:
                forca_minima = st.session_state.get('forca_minima_sinal', 40)
                if nova['forca_sinal'] >= forca_minima:
                    self.previsao_ativa = nova
                    enviar_previsao_auto(nova)
    
    def zerar_estatisticas(self):
        self.acertos = 0
        self.erros = 0
        self.historico_desempenho = []
        self.historico_numeros.clear()
        self.historico_multiplicadores.clear()
        self.rodadas_sem_entrada = 0
        self.ultima_entrada_rodada = -10
        self.ia.zerar()
        self.performance = self.ia.performance
        salvar_sessao()
    
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
st.set_page_config(page_title="🎯 IA Roleta — Base 100% Dinâmica", layout="centered")
st.title("🎯 IA Roleta — Motor com Expansão Inteligente")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaIA()

# Inicializa configurações
if "modo_sniper" not in st.session_state:
    st.session_state.modo_sniper = False
if "modo_seguro" not in st.session_state:
    st.session_state.modo_seguro = True
if "forca_minima_sinal" not in st.session_state:
    st.session_state.forca_minima_sinal = 40
if "intervalo_minimo_entradas" not in st.session_state:
    st.session_state.intervalo_minimo_entradas = 1
if "max_numeros_entrada" not in st.session_state:
    st.session_state.max_numeros_entrada = 15
if "expandir_com_vizinhos" not in st.session_state:
    st.session_state.expandir_com_vizinhos = True
if "qtd_vizinhos_antes" not in st.session_state:
    st.session_state.qtd_vizinhos_antes = 2
if "qtd_vizinhos_depois" not in st.session_state:
    st.session_state.qtd_vizinhos_depois = 2

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

# ===== MODO DE OPERAÇÃO =====
with st.sidebar.expander("🎯 Modo de Entrada", expanded=True):
    st.write("**Selecione o modo:**")
    
    modo_sniper = st.checkbox("🎯 Modo Sniper (5-7 números)", value=st.session_state.modo_sniper)
    modo_seguro = st.checkbox("🛡️ Modo Seguro (10-12 números)", value=st.session_state.modo_seguro)
    
    if modo_sniper and modo_seguro:
        st.warning("⚠️ Apenas um modo pode estar ativo")
    else:
        st.session_state.modo_sniper = modo_sniper
        st.session_state.modo_seguro = modo_seguro

# ===== EXPANSÃO COM VIZINHOS =====
with st.sidebar.expander("🔧 Expansão com Vizinhos", expanded=True):
    st.session_state.expandir_com_vizinhos = st.checkbox(
        "🔄 Expandir com vizinhos", 
        value=st.session_state.expandir_com_vizinhos,
        help="Adiciona vizinhos antes e depois de cada número"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.qtd_vizinhos_antes = st.number_input(
            "⬅️ Vizinhos antes", 
            min_value=1, max_value=4, value=st.session_state.qtd_vizinhos_antes
        )
    with col2:
        st.session_state.qtd_vizinhos_depois = st.number_input(
            "➡️ Vizinhos depois", 
            min_value=1, max_value=4, value=st.session_state.qtd_vizinhos_depois
        )
    
    st.session_state.max_numeros_entrada = st.slider(
        "📊 Máximo de números",
        min_value=5, max_value=18, value=st.session_state.max_numeros_entrada
    )
    
    st.caption(f"💡 Cada número gera +{st.session_state.qtd_vizinhos_antes} antes +{st.session_state.qtd_vizinhos_depois} depois")

# ===== FILTRO DE FORÇA =====
with st.sidebar.expander("⚡ Força do Sinal", expanded=True):
    st.session_state.forca_minima_sinal = st.slider(
        "Força mínima para entrar",
        min_value=30, max_value=70, value=st.session_state.forca_minima_sinal, step=5
    )
    
    forca = st.session_state.forca_minima_sinal
    if forca <= 40:
        st.success(f"🟢 PERMISSIVO ({forca}%)")
    elif forca <= 55:
        st.warning(f"🟡 EQUILIBRADO ({forca}%)")
    else:
        st.error(f"🔴 RESTRITIVO ({forca}%)")
    
    st.session_state.intervalo_minimo_entradas = st.slider(
        "⏱️ Intervalo entre entradas",
        min_value=0, max_value=3, value=st.session_state.intervalo_minimo_entradas, step=1
    )

# ===== ANÁLISE IA =====
with st.sidebar.expander("🧠 Análise IA", expanded=True):
    analise = st.session_state.sistema.ia.get_analise_completa()
    st.text(analise)

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
    if taxa >= 35:
        st.success(f"🎯 Taxa de Acerto: {taxa:.1f}% ✅")
    elif taxa >= 25:
        st.warning(f"🎯 Taxa de Acerto: {taxa:.1f}%")
    else:
        st.error(f"🎯 Taxa de Acerto: {taxa:.1f}%")

# Previsão Ativa
st.subheader("🎯 Previsão Ativa (Base 100% Dinâmica)")
sistema = st.session_state.sistema

if sistema.estrategia_ativa_manual:
    st.warning("⚠️ MODO MANUAL ATIVO")
elif sistema.previsao_ativa:
    p = sistema.previsao_ativa
    forca = p.get('forca_sinal', 0)
    tipo = p.get('tipo_entrada', 'normal')
    num_orig = p.get('num_originais', 0)
    
    emoji = "🎯" if tipo == 'sniper' else "🛡️" if tipo == 'seguro' else "🎲"
    barras = "█" * (forca // 10) + "░" * (10 - forca // 10)
    
    st.success(f"{emoji} **ENTRADA DINÂMICA** - FORÇA {forca}% {barras}")
    if p.get('expandido'):
        st.caption(f"📈 Expandido: {num_orig} → {len(p['numeros_apostar'])} números")
    st.info(f"📋 **Gatilho:** {p['gatilho']}")
    
    st.write(f"**🔢 Números ({len(p['numeros_apostar'])}):**")
    nums = sorted(p['numeros_apostar'])
    colunas = st.columns(5)
    for i, num in enumerate(nums):
        colunas[i % 5].write(f"**{num}**")
else:
    st.info(f"🎲 Aguardando sinal... ({status['rodadas_sem_entrada']} rodadas sem entrada)")

# Performance da IA
st.subheader("📈 Performance da IA")
taxa_ia = sistema.ia.get_taxa_acerto()
taxa_rec = sistema.ia.get_taxa_recente(5)
total_ia = sistema.ia.performance['acertos'] + sistema.ia.performance['erros']

col1, col2 = st.columns(2)
with col1:
    if total_ia > 0:
        if taxa_ia >= 0.40:
            st.success(f"🟢 **Geral**: {taxa_ia:.0%} ({sistema.ia.performance['acertos']}/{total_ia})")
        elif taxa_ia >= 0.25:
            st.warning(f"🟡 **Geral**: {taxa_ia:.0%} ({sistema.ia.performance['acertos']}/{total_ia})")
        else:
            st.error(f"🔴 **Geral**: {taxa_ia:.0%} ({sistema.ia.performance['acertos']}/{total_ia})")
    else:
        st.info("⚪ **Geral**: Coletando...")
with col2:
    if len(sistema.ia.performance['historico']) >= 5:
        if taxa_rec >= 0.40:
            st.success(f"🟢 **Recente (5)**: {taxa_rec:.0%}")
        elif taxa_rec >= 0.25:
            st.warning(f"🟡 **Recente (5)**: {taxa_rec:.0%}")
        else:
            st.error(f"🔴 **Recente (5)**: {taxa_rec:.0%}")
    else:
        st.info("⚪ **Recente**: Coletando...")

# Histórico recente
if sistema.historico_desempenho:
    st.write("**🔍 Últimas Conferências:**")
    for r in sistema.historico_desempenho[-5:]:
        emoji_result = "🎉" if r['acerto'] else "❌"
        mult = f" ⚡{r['multiplicador']}x" if r.get('multiplicador') and r['acerto'] else ""
        forca = r.get('forca', 0)
        st.write(f"{emoji_result} IA Dinâmica ({forca}%): {r['numero']}{mult}")

salvar_sessao()
