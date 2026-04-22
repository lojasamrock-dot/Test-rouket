import streamlit as st
import json
import os
import requests
import logging
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
            'historico_numeros': list(st.session_state.sistema.historico_numeros),
            'historico_multiplicadores': list(st.session_state.sistema.historico_multiplicadores),
            'estrategia_ativa_manual': st.session_state.sistema.estrategia_ativa_manual
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
                st.session_state.sistema.historico_numeros = deque(session_data.get('historico_numeros', []), maxlen=100)
                st.session_state.sistema.historico_multiplicadores = deque(session_data.get('historico_multiplicadores', []), maxlen=100)
                st.session_state.sistema.estrategia_ativa_manual = session_data.get('estrategia_ativa_manual', False)
            
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
        
        emojis = {
            'Cluster': '🔥',
            'Núcleo Quente': '🎯',
            'Pós-Sequência': '💣',
            'Bloco': '📊',
            'Multiplicador': '🚀'
        }
        emoji = emojis.get(nome, '🎲')
        
        msg = f"{emoji} **{nome.upper()}** ATIVADA!\n📋 {gatilho}"
        
        st.toast(f"🎯 {nome} Ativada!", icon=emoji)
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
        payload = {
            "chat_id": chat_id,
            "text": mensagem,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
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
    
    def get_vizinho_esquerda(self, numero):
        """Retorna apenas o vizinho da esquerda"""
        if numero not in self.race:
            return None
        posicao = self.race.index(numero)
        return self.race[(posicao - 1) % 37]
    
    def get_vizinho_direita(self, numero):
        """Retorna apenas o vizinho da direita"""
        if numero not in self.race:
            return None
        posicao = self.race.index(numero)
        return self.race[(posicao + 1) % 37]
    
    def get_oposto(self, numero):
        if numero not in self.race:
            return None
        posicao = self.race.index(numero)
        return self.race[(posicao + 18) % 37]

# =============================
# SISTEMA DE DETECÇÃO AUTOMÁTICA DE GATILHOS (SEM HÍBRIDA)
# =============================
class DetectorGatilhos:
    """
    Avalia TODOS os gatilhos a cada rodada e retorna a estratégia ativada
    HÍBRIDA REMOVIDA - Só ativa quando há gatilho REAL
    """
    
    def __init__(self):
        self.roleta = RoletaBase()
        self.numeros_quentes = [33, 14, 17, 30, 25, 32, 8, 7]
        
    def detectar(self, historico_numeros, historico_multiplicadores, perdas_cluster=0, perdas_bloco=0):
        """
        Avalia todos os gatilhos e retorna a melhor estratégia ativada
        Ordem de prioridade:
        1. Cluster (Repetição) - MAIS FORTE
        2. Pós-Sequência
        3. Núcleo Quente
        4. Bloco
        5. Multiplicador
        6. NENHUM - Aguarda próximo sorteio (NÃO USA HÍBRIDA)
        """
        if len(historico_numeros) < 3:
            return None
            
        hist_list = list(historico_numeros)
        ultimo = hist_list[-1]
        
        # ===== GATILHO 1: CLUSTER (REPETIÇÃO) =====
        if perdas_cluster < 2:  # Só ativa se não estourou stop
            cluster = self._detectar_cluster(hist_list, ultimo)
            if cluster:
                return cluster
        
        # ===== GATILHO 2: PÓS-SEQUÊNCIA =====
        pos_seq = self._detectar_pos_sequencia(hist_list)
        if pos_seq:
            return pos_seq
        
        # ===== GATILHO 3: NÚCLEO QUENTE =====
        nucleo = self._detectar_nucleo_quente(hist_list)
        if nucleo:
            return nucleo
        
        # ===== GATILHO 4: BLOCO (ALTOS/BAIXOS) =====
        if perdas_bloco < 2:  # Só ativa se não estourou stop
            bloco = self._detectar_bloco(hist_list)
            if bloco:
                return bloco
        
        # ===== GATILHO 5: MULTIPLICADOR =====
        multi = self._detectar_multiplicador(hist_list, historico_multiplicadores)
        if multi:
            return multi
        
        # ===== NENHUM GATILHO ATIVO =====
        return None
    
    def _detectar_cluster(self, hist_list, ultimo):
        """Detecta repetição: número repetido OU 2x em 5 rodadas"""
        # Repetição direta
        if len(hist_list) >= 2 and hist_list[-1] == hist_list[-2]:
            return self._gerar_cluster(ultimo, "Repetição direta")
        
        # 2x em 5 rodadas
        if len(hist_list) >= 5:
            ultimos_5 = hist_list[-5:]
            contagem = Counter(ultimos_5)
            for num, count in contagem.items():
                if count >= 2 and num == ultimo:
                    return self._gerar_cluster(num, f"2x em 5 rodadas")
        
        return None
    
    def _gerar_cluster(self, numero, motivo):
        vizinhos = self.roleta.get_vizinhos(numero, raio=2)
        numeros = list(set([numero] + vizinhos))
        
        return {
            'nome': 'Cluster',
            'numeros_apostar': sorted(numeros),
            'gatilho': f"🔥 {motivo}: {numero}",
            'confianca': 'Alta',
            'numero_gatilho': numero,
            'tipo': 'cluster'
        }
    
    def _detectar_pos_sequencia(self, hist_list):
        """Detecta quebra de sequência de repetição"""
        if len(hist_list) < 4:
            return None
        
        # Procura padrão X, X, X, Y (Y ≠ X)
        for i in range(len(hist_list) - 3, len(hist_list) - 1):
            if i >= 2:
                if hist_list[i-2] == hist_list[i-1] == hist_list[i]:
                    numero_rep = hist_list[i]
                    numero_quebra = hist_list[i+1]
                    
                    if numero_quebra != numero_rep:
                        vizinhos = self.roleta.get_vizinhos(numero_rep, raio=2)
                        oposto = self.roleta.get_oposto(numero_rep)
                        
                        numeros = list(set(vizinhos))
                        if oposto:
                            numeros.append(oposto)
                        
                        return {
                            'nome': 'Pós-Sequência',
                            'numeros_apostar': sorted(numeros),
                            'gatilho': f"💣 Quebra após {numero_rep}→{numero_rep}→{numero_rep}",
                            'confianca': 'Média-Alta',
                            'numero_repetido': numero_rep,
                            'tipo': 'pos_sequencia'
                        }
        
        return None
    
    def _detectar_nucleo_quente(self, hist_list):
        """Detecta 2+ números quentes em 5 rodadas"""
        if len(hist_list) < 5:
            return None
        
        ultimos_5 = hist_list[-5:]
        quentes_recentes = [n for n in ultimos_5 if n in self.numeros_quentes]
        
        if len(quentes_recentes) >= 2:
            frequencias = Counter(hist_list)
            top_frequentes = [num for num, _ in frequencias.most_common(5)]
            base = list(set(self.numeros_quentes + top_frequentes))[:8]
            
            return {
                'nome': 'Núcleo Quente',
                'numeros_apostar': sorted(base),
                'gatilho': f"🎯 {len(quentes_recentes)} quentes em 5 rodadas: {quentes_recentes}",
                'confianca': 'Alta',
                'nucleo': base,
                'tipo': 'nucleo_quente'
            }
        
        return None
    
    def _detectar_bloco(self, hist_list):
        """Detecta 4+ altos ou baixos seguidos"""
        if len(hist_list) < 5:
            return None
        
        ultimos = hist_list[-6:]
        
        # Conta altos seguidos (>19)
        altos = 0
        for n in reversed(ultimos):
            if n > 19:
                altos += 1
            else:
                break
        
        # Conta baixos seguidos (≤18)
        baixos = 0
        for n in reversed(ultimos):
            if n <= 18:
                baixos += 1
            else:
                break
        
        if altos >= 4:
            return {
                'nome': 'Bloco',
                'numeros_apostar': list(range(0, 19)),
                'gatilho': f"📊 {altos} altos seguidos - invertendo para BAIXOS (0-18)",
                'confianca': 'Média',
                'bloco_tipo': 'Altos',
                'tipo': 'bloco'
            }
        
        if baixos >= 4:
            return {
                'nome': 'Bloco',
                'numeros_apostar': list(range(19, 37)),
                'gatilho': f"📊 {baixos} baixos seguidos - invertendo para ALTOS (19-36)",
                'confianca': 'Média',
                'bloco_tipo': 'Baixos',
                'tipo': 'bloco'
            }
        
        return None
    
    def _detectar_multiplicador(self, hist_list, hist_mult):
        """Detecta 5-8 rodadas sem multiplicador >500x"""
        if len(hist_list) < 8:
            return None
        
        mult_list = list(hist_mult)
        
        rodadas_sem = 0
        for m in reversed(mult_list):
            if m and m >= 500:
                break
            rodadas_sem += 1
        
        if 5 <= rodadas_sem <= 12:
            numeros = set()
            numeros.add(0)
            
            for n in self.numeros_quentes[:4]:
                numeros.add(n)
            
            for n in hist_list[-3:]:
                numeros.add(n)
            
            frequencias = Counter(hist_list)
            for num, _ in frequencias.most_common(5):
                numeros.add(num)
                if len(numeros) >= 12:
                    break
            
            return {
                'nome': 'Multiplicador',
                'numeros_apostar': sorted(list(numeros))[:12],
                'gatilho': f"🚀 {rodadas_sem} rodadas sem spike >500x",
                'confianca': 'Alta',
                'rodadas_sem': rodadas_sem,
                'tipo': 'multiplicador'
            }
        
        return None

# =============================
# SISTEMA PRINCIPAL AUTO-ADAPTATIVO (SEM HÍBRIDA)
# =============================
class SistemaAutoAdaptativo:
    def __init__(self):
        self.detector = DetectorGatilhos()
        self.roleta = RoletaBase()
        
        # Históricos
        self.historico_numeros = deque(maxlen=100)
        self.historico_multiplicadores = deque(maxlen=100)
        
        # Previsão e desempenho
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        
        # Controle de stop loss
        self.perdas_cluster = 0
        self.perdas_bloco = 0
        
        # Controle manual
        self.estrategia_ativa_manual = False
        
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
        
        # Verifica resultado da previsão anterior
        if self.previsao_ativa:
            acerto = numero_real in self.previsao_ativa.get('numeros_apostar', [])
            nome = self.previsao_ativa['nome']
            
            # Atualiza contadores
            if nome not in self.estrategias_contador:
                self.estrategias_contador[nome] = {'acertos': 0, 'total': 0}
            self.estrategias_contador[nome]['total'] += 1
            
            if acerto:
                self.estrategias_contador[nome]['acertos'] += 1
                self.acertos += 1
                # Reseta perdas da estratégia
                if nome == 'Cluster':
                    self.perdas_cluster = 0
                elif nome == 'Bloco':
                    self.perdas_bloco = 0
            else:
                self.erros += 1
                # Incrementa perdas da estratégia
                if nome == 'Cluster':
                    self.perdas_cluster += 1
                elif nome == 'Bloco':
                    self.perdas_bloco += 1
            
            enviar_resultado_auto(numero_real, acerto, nome, mult)
            
            self.historico_desempenho.append({
                'numero': numero_real,
                'acerto': acerto,
                'estrategia': nome,
                'multiplicador': mult
            })
            
            self.previsao_ativa = None
        
        # Se modo manual ativado, não gera previsão automática
        if self.estrategia_ativa_manual:
            return
        
        # DETECTA GATILHOS AUTOMATICAMENTE
        nova = self.detector.detectar(
            self.historico_numeros, 
            self.historico_multiplicadores,
            self.perdas_cluster,
            self.perdas_bloco
        )
        
        if nova:
            self.previsao_ativa = nova
            enviar_previsao_auto(nova)
        # Se não houver gatilho, NÃO gera previsão (sem Híbrida)
    
    def zerar_estatisticas(self):
        self.acertos = 0
        self.erros = 0
        self.estrategias_contador = {}
        self.historico_desempenho = []
        self.historico_numeros.clear()
        self.historico_multiplicadores.clear()
        self.perdas_cluster = 0
        self.perdas_bloco = 0
        salvar_sessao()
    
    def get_analise_completa(self):
        """Retorna análise completa de todos os gatilhos"""
        if len(self.historico_numeros) < 5:
            return "📊 Aguardando dados para análise..."
        
        hist_list = list(self.historico_numeros)
        mult_list = list(self.historico_multiplicadores)
        ultimo = hist_list[-1]
        
        analise = "🎯 ANÁLISE DE GATILHOS (Auto-Detecção)\n"
        analise += "=" * 50 + "\n\n"
        
        # 1. Cluster
        analise += "🔥 CLUSTER (Repetição):\n"
        if self.perdas_cluster >= 2:
            analise += f"   ⚠️ PAUSADO! ({self.perdas_cluster}/2 perdas)\n"
        elif len(hist_list) >= 2 and hist_list[-1] == hist_list[-2]:
            analise += f"   ✅ ATIVO! Repetição direta: {ultimo}→{ultimo}\n"
        else:
            ultimos_5 = hist_list[-5:] if len(hist_list) >= 5 else hist_list
            contagem = Counter(ultimos_5)
            repeticoes = [f"{n}({c}x)" for n, c in contagem.items() if c >= 2]
            if repeticoes:
                analise += f"   🟡 Parcial: {', '.join(repeticoes)}\n"
            else:
                analise += "   ❌ Inativo\n"
        analise += f"   Perdas: {self.perdas_cluster}/2\n\n"
        
        # 2. Pós-Sequência
        analise += "💣 PÓS-SEQUÊNCIA:\n"
        seq_ativa = None
        for i in range(len(hist_list)-1, 1, -1):
            if hist_list[i] == hist_list[i-1] == hist_list[i-2]:
                seq_ativa = hist_list[i]
                break
        if seq_ativa:
            analise += f"   🟡 Sequência ativa: {seq_ativa} (3x+)\n"
        else:
            analise += "   ❌ Inativo\n\n"
        
        # 3. Núcleo Quente
        analise += "🎯 NÚCLEO QUENTE:\n"
        quentes_fixos = [33, 14, 17, 30, 25, 32, 8, 7]
        ultimos_5 = hist_list[-5:]
        quentes_5 = [n for n in ultimos_5 if n in quentes_fixos]
        if len(quentes_5) >= 2:
            analise += f"   ✅ ATIVO! {len(quentes_5)} quentes: {quentes_5}\n"
        else:
            analise += f"   ❌ Inativo ({len(quentes_5)}/2 quentes)\n"
        
        frequencias = Counter(hist_list)
        analise += f"   Top 5: {frequencias.most_common(5)}\n\n"
        
        # 4. Bloco
        analise += "📊 BLOCO (Altos/Baixos):\n"
        if self.perdas_bloco >= 2:
            analise += f"   ⚠️ PAUSADO! ({self.perdas_bloco}/2 perdas)\n"
        else:
            altos = 0
            for n in reversed(hist_list):
                if n > 19:
                    altos += 1
                else:
                    break
            baixos = 0
            for n in reversed(hist_list):
                if n <= 18:
                    baixos += 1
                else:
                    break
            
            if altos >= 4:
                analise += f"   ✅ ATIVO! {altos} altos seguidos → BAIXOS\n"
            elif baixos >= 4:
                analise += f"   ✅ ATIVO! {baixos} baixos seguidos → ALTOS\n"
            else:
                analise += f"   ❌ Inativo (Altos: {altos}, Baixos: {baixos})\n"
        analise += f"   Perdas: {self.perdas_bloco}/2\n\n"
        
        # 5. Multiplicador
        analise += "🚀 MULTIPLICADOR:\n"
        rodadas_sem = 0
        for m in reversed(mult_list):
            if m and m >= 500:
                break
            rodadas_sem += 1
        if 5 <= rodadas_sem <= 12:
            analise += f"   ✅ ATIVO! {rodadas_sem} rodadas sem spike\n"
        else:
            analise += f"   ❌ Inativo ({rodadas_sem} rodadas)\n"
        
        analise += "\n" + "=" * 50 + "\n"
        analise += f"🎲 Último: {ultimo}\n"
        analise += f"📊 Últimos 10: {hist_list[-10:]}\n"
        
        return analise
    
    def get_status(self):
        return {
            'acertos': self.acertos,
            'erros': self.erros,
            'total': self.acertos + self.erros,
            'perdas_cluster': self.perdas_cluster,
            'perdas_bloco': self.perdas_bloco
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
st.set_page_config(page_title="🎯 IA Roleta — Auto-Detecção de Gatilhos", layout="centered")
st.title("🎯 IA Roleta — Sistema Auto-Adaptativo")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaAutoAdaptativo()

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

# Controle Manual/Automático
st.sidebar.subheader("🎮 Modo de Operação")
modo_auto = st.sidebar.checkbox("🔄 Modo Automático", value=not st.session_state.sistema.estrategia_ativa_manual)
if st.sidebar.button("Atualizar Modo"):
    st.session_state.sistema.estrategia_ativa_manual = not modo_auto
    st.rerun()

if st.session_state.sistema.estrategia_ativa_manual:
    st.sidebar.warning("⚠️ Modo MANUAL - Sem previsões automáticas")
else:
    st.sidebar.success("✅ Modo AUTOMÁTICO - Detectando gatilhos")

# Análise de Gatilhos
with st.sidebar.expander("🔍 Análise de Gatilhos", expanded=True):
    analise = st.session_state.sistema.get_analise_completa()
    st.text(analise)

st.sidebar.info("""
**🎯 GATILHOS ATIVOS:**
- 🔥 Cluster (Repetição)
- 💣 Pós-Sequência  
- 🎯 Núcleo Quente
- 📊 Bloco (Altos/Baixos)
- 🚀 Multiplicador

**⛔ STOP LOSS:**
- Cluster: 2 perdas → pausa
- Bloco: 2 perdas → pausa

**🚫 HÍBRIDA REMOVIDA**
(Não gera entrada sem gatilho real)
""")

# Botão para resetar stops
if st.sidebar.button("🔄 Resetar Stops", use_container_width=True):
    st.session_state.sistema.perdas_cluster = 0
    st.session_state.sistema.perdas_bloco = 0
    st.success("✅ Stops resetados!")
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
col3.metric("🔥 Cluster", f"{status['perdas_cluster']}/2")
col4.metric("📊 Bloco", f"{status['perdas_bloco']}/2")

# Previsão Ativa
st.subheader("🎯 Previsão Ativa")
sistema = st.session_state.sistema

if sistema.estrategia_ativa_manual:
    st.warning("⚠️ MODO MANUAL ATIVO - Sem previsões automáticas")
elif sistema.previsao_ativa:
    p = sistema.previsao_ativa
    emoji = {'Cluster': '🔥', 'Núcleo Quente': '🎯', 'Pós-Sequência': '💣', 
             'Bloco': '📊', 'Multiplicador': '🚀'}.get(p['nome'], '🎲')
    st.success(f"{emoji} **{p['nome'].upper()}**")
    st.info(f"📋 **Gatilho:** {p['gatilho']}")
    st.write(f"**🔢 Números ({len(p['numeros_apostar'])}):**")
    
    nums = sorted(p['numeros_apostar'])
    colunas = st.columns(6)
    for i, num in enumerate(nums):
        colunas[i % 6].write(f"**{num}**")
else:
    st.info("🎲 Aguardando gatilhos... (Nenhum ativo no momento)")

# Desempenho por Estratégia
st.subheader("📈 Desempenho por Estratégia")
total = sistema.acertos + sistema.erros
taxa = (sistema.acertos / total * 100) if total > 0 else 0.0
st.caption(f"Taxa geral: {taxa:.1f}% ({sistema.acertos}/{total})")

if sistema.estrategias_contador:
    # Ordena por taxa de acerto
    desempenho_ordenado = []
    for nome, dados in sistema.estrategias_contador.items():
        if dados['total'] > 0:
            tx = dados['acertos'] / dados['total'] * 100
            desempenho_ordenado.append((nome, dados, tx))
    
    desempenho_ordenado.sort(key=lambda x: x[2], reverse=True)
    
    for nome, dados, tx in desempenho_ordenado:
        cor = "🟢" if tx >= 50 else "🟡" if tx >= 30 else "🔴"
        emoji = {'Cluster': '🔥', 'Núcleo Quente': '🎯', 'Pós-Sequência': '💣',
                'Bloco': '📊', 'Multiplicador': '🚀'}.get(nome, '🎲')
        st.write(f"{cor} {emoji} {nome}: {dados['acertos']}/{dados['total']} ({tx:.1f}%)")

# Histórico recente
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
