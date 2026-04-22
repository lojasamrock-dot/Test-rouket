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
                'Cluster': True, 'PosSequencia': True, 'Markov': True,
                'Agrupamento': True, 'Compressao': True, 'Ciclo': True,
                'NucleoQuente': True, 'Bloco': True, 'Salto': True,
                'Entropia': True, 'Multiplicador': True
            }),
            'expandir_com_vizinhos': st.session_state.get('expandir_com_vizinhos', True),
            'max_numeros_entrada': st.session_state.get('max_numeros_entrada', 15)
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
            
            # Carrega estratégias ativas
            st.session_state.estrategias_ativas = session_data.get('estrategias_ativas', {
                'Cluster': True, 'PosSequencia': True, 'Markov': True,
                'Agrupamento': True, 'Compressao': True, 'Ciclo': True,
                'NucleoQuente': True, 'Bloco': True, 'Salto': True,
                'Entropia': True, 'Multiplicador': True
            })
            
            # Carrega configurações de expansão
            st.session_state.expandir_com_vizinhos = session_data.get('expandir_com_vizinhos', True)
            st.session_state.max_numeros_entrada = session_data.get('max_numeros_entrada', 15)
            
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
        
        emojis = {
            'Cluster': '🔥', 'Núcleo Quente': '🎯', 'Pós-Sequência': '💣',
            'Bloco': '📊', 'Multiplicador': '🚀', 'Markov': '🧠',
            'Salto': '⚡', 'Ciclo': '🌀', 'Agrupamento': '🎰',
            'Entropia': '📐', 'Compressão': '💥'
        }
        emoji = emojis.get(nome, '🎲')
        
        # Mostra se houve expansão
        if previsao.get('expandido'):
            msg = f"{emoji} **{nome.upper()}** ATIVADA (EXPANDIDA)!\n📋 {gatilho}\n📊 Expandido de {previsao.get('num_originais', 0)} → {len(numeros)} números"
        else:
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
    
    def get_vizinhos_amplo(self, numero, raio=4):
        """Retorna vizinhos com raio maior para agrupamento"""
        if numero not in self.race:
            return []
        posicao = self.race.index(numero)
        vizinhos = [numero]
        for offset in range(-raio, raio + 1):
            vizinhos.append(self.race[(posicao + offset) % 37])
        return list(set(vizinhos))
    
    def get_oposto(self, numero):
        if numero not in self.race:
            return None
        posicao = self.race.index(numero)
        return self.race[(posicao + 18) % 37]
    
    def get_distancia_roda(self, num1, num2):
        """Calcula distância entre dois números na roda"""
        if num1 not in self.race or num2 not in self.race:
            return 37
        p1 = self.race.index(num1)
        p2 = self.race.index(num2)
        dist = abs(p1 - p2)
        return min(dist, 37 - dist)
    
    def get_regiao(self, numeros):
        """Identifica se números estão agrupados na roda"""
        if len(numeros) < 3:
            return False, []
        
        agrupados = []
        for i, n1 in enumerate(numeros):
            grupo = [n1]
            for j, n2 in enumerate(numeros):
                if i != j and self.get_distancia_roda(n1, n2) <= 4:
                    grupo.append(n2)
            if len(grupo) >= 3:
                agrupados = list(set(grupo))
                break
        
        return len(agrupados) >= 3, agrupados

# =============================
# SELETOR INTELIGENTE DE NÚMEROS
# =============================
class SeletorInteligente:
    """Seleciona os melhores números quando há muitos candidatos"""
    
    def __init__(self):
        self.roleta = RoletaBase()
    
    def selecionar_melhores(self, numeros_candidatos, historico, max_numeros=15):
        """
        Seleciona os melhores números baseado em:
        - Frequência recente
        - Proximidade na roda com números quentes
        - Diversidade de regiões
        """
        if len(numeros_candidatos) <= max_numeros:
            return numeros_candidatos
        
        hist_list = list(historico)
        
        # Calcula score para cada número
        scores = {}
        for num in numeros_candidatos:
            score = 0
            
            # 1. Frequência recente (40%)
            if len(hist_list) >= 10:
                recentes = hist_list[-15:]
                freq = recentes.count(num) / len(recentes)
                score += freq * 0.4
            
            # 2. Proximidade com números que saíram recentemente (30%)
            if len(hist_list) >= 3:
                ultimos_3 = hist_list[-3:]
                for ult in ultimos_3:
                    dist = self.roleta.get_distancia_roda(num, ult)
                    if dist <= 3:
                        score += 0.3 * (1 - dist/4)
            
            # 3. É número quente do estudo? (20%)
            quentes_estudo = [33, 14, 17, 30, 25, 32, 8, 7]
            if num in quentes_estudo:
                score += 0.2
            
            # 4. Diversidade (número 0 tem bônus) (10%)
            if num == 0:
                score += 0.1
            
            scores[num] = score
        
        # Ordena por score e pega os melhores
        ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        selecionados = [num for num, _ in ordenados[:max_numeros]]
        
        return selecionados
    
    def expandir_com_vizinhos(self, numeros_base, historico, max_numeros=15, 
                              qtd_anteriores=2, qtd_posteriores=2):
        """
        Expande a lista de números adicionando vizinhos anteriores e posteriores
        e depois seleciona os melhores até o limite
        """
        if len(numeros_base) == 0:
            return []
        
        num_originais = len(numeros_base)
        
        # Se já tem 8 ou mais números, não expande (a menos que forçado)
        if num_originais >= 8 and not st.session_state.get('expandir_sempre', False):
            # Apenas seleciona os melhores se passou do limite
            if num_originais > max_numeros:
                return self.selecionar_melhores(numeros_base, historico, max_numeros)
            return numeros_base
        
        # Expande com vizinhos
        numeros_expandidos = set(numeros_base)
        
        for num in numeros_base:
            # Adiciona vizinhos anteriores (esquerda)
            anteriores = self.roleta.get_vizinhos_anteriores(num, qtd_anteriores)
            numeros_expandidos.update(anteriores)
            
            # Adiciona vizinhos posteriores (direita)
            posteriores = self.roleta.get_vizinhos_posteriores(num, qtd_posteriores)
            numeros_expandidos.update(posteriores)
        
        # Converte para lista
        lista_expandida = list(numeros_expandidos)
        
        # Se ainda tem menos que max_numeros, retorna todos
        if len(lista_expandida) <= max_numeros:
            return sorted(lista_expandida)
        
        # Seleciona os melhores até o limite
        return self.selecionar_melhores(lista_expandida, historico, max_numeros)

# =============================
# ESTRATÉGIAS
# =============================

class EstrategiaMarkovTransicao:
    """Cadeia de Markov: o que mais sai depois de cada número"""
    
    def __init__(self):
        self.roleta = RoletaBase()
        self.nome = "Markov"
        self.min_ocorrencias = 5
        self.seletor = SeletorInteligente()
        
    def detectar(self, hist_list, ultimo, matriz_transicao, expandir_vizinhos=True, max_numeros=15):
        if len(hist_list) < 10:
            return None
        
        ocorrencias = sum(1 for n in hist_list if n == ultimo)
        
        if ocorrencias >= self.min_ocorrencias and ultimo in matriz_transicao:
            transicoes = matriz_transicao[ultimo]
            if transicoes:
                top3 = [num for num, _ in transicoes.most_common(3)]
                num_originais = len(top3)
                
                # Expande com vizinhos se necessário
                if expandir_vizinhos:
                    numeros_final = self.seletor.expandir_com_vizinhos(
                        top3, hist_list, max_numeros, qtd_anteriores=2, qtd_posteriores=2
                    )
                else:
                    numeros_final = self.seletor.selecionar_melhores(top3, hist_list, max_numeros)
                
                return {
                    'nome': self.nome,
                    'numeros_apostar': sorted(numeros_final),
                    'gatilho': f"🧠 Markov: após {ultimo} → {top3}",
                    'confianca': 'Alta',
                    'numero_gatilho': ultimo,
                    'tipo': 'markov',
                    'expandido': expandir_vizinhos and len(numeros_final) > num_originais,
                    'num_originais': num_originais
                }
        
        return None


class EstrategiaSalto:
    """Padrão de distância entre números consecutivos"""
    
    def __init__(self):
        self.roleta = RoletaBase()
        self.nome = "Salto"
        self.seletor = SeletorInteligente()
        
    def _classificar_salto(self, diff):
        abs_diff = abs(diff)
        if abs_diff <= 6:
            return 'curto'
        elif abs_diff <= 18:
            return 'medio'
        else:
            return 'extremo'
    
    def _get_saltos(self, hist_list):
        if len(hist_list) < 2:
            return []
        
        saltos = []
        for i in range(1, len(hist_list)):
            diff = hist_list[i] - hist_list[i-1]
            saltos.append((diff, self._classificar_salto(diff)))
        
        return saltos
    
    def detectar(self, hist_list, ultimo, expandir_vizinhos=True, max_numeros=15):
        if len(hist_list) < 5:
            return None
        
        saltos = self._get_saltos(hist_list)
        if len(saltos) < 4:
            return None
        
        ultimos_3 = saltos[-3:]
        tipos = [t for _, t in ultimos_3]
        
        if len(set(tipos)) == 1:
            tipo_atual = tipos[0]
            numeros = set()
            
            if tipo_atual == 'curto':
                for i in range(37):
                    if abs(i - ultimo) > 6:
                        numeros.add(i)
            elif tipo_atual == 'medio':
                for i in range(37):
                    diff = abs(i - ultimo)
                    if diff <= 6 or diff >= 19:
                        numeros.add(i)
            else:
                for i in range(37):
                    if abs(i - ultimo) <= 18:
                        numeros.add(i)
            
            numeros_base = list(numeros)[:8]  # Pega até 8 como base
            num_originais = len(numeros_base)
            
            # Expande com vizinhos se necessário
            if expandir_vizinhos:
                numeros_final = self.seletor.expandir_com_vizinhos(
                    numeros_base, hist_list, max_numeros, qtd_anteriores=2, qtd_posteriores=2
                )
            else:
                numeros_final = self.seletor.selecionar_melhores(numeros_base, hist_list, max_numeros)
            
            return {
                'nome': self.nome,
                'numeros_apostar': sorted(numeros_final),
                'gatilho': f"⚡ 3 saltos {tipo_atual}s seguidos - esperando quebra",
                'confianca': 'Média',
                'tipo_salto': tipo_atual,
                'tipo': 'salto',
                'expandido': expandir_vizinhos and len(numeros_final) > num_originais,
                'num_originais': num_originais
            }
        
        return None


class EstrategiaCiclo:
    """Ciclo invisível: tempo médio de reaparição de cada número"""
    
    def __init__(self):
        self.roleta = RoletaBase()
        self.nome = "Ciclo"
        self.seletor = SeletorInteligente()
        
    def _calcular_ciclos(self, hist_list):
        ciclos = {}
        
        for num in range(37):
            posicoes = [i for i, n in enumerate(hist_list) if n == num]
            if len(posicoes) >= 2:
                distancias = [posicoes[i+1] - posicoes[i] for i in range(len(posicoes)-1)]
                ciclos[num] = {
                    'media': sum(distancias) / len(distancias),
                    'max': max(distancias),
                    'ultimo': len(hist_list) - 1 - posicoes[-1] if posicoes else 0
                }
            else:
                ciclos[num] = {'media': 37, 'max': 37, 'ultimo': len(hist_list)}
        
        return ciclos
    
    def detectar(self, hist_list, ciclos_numeros, expandir_vizinhos=True, max_numeros=15):
        if len(hist_list) < 20:
            return None
        
        ciclos = self._calcular_ciclos(hist_list)
        atrasados = []
        for num, dados in ciclos.items():
            if dados['ultimo'] > dados['media'] * 1.2 and dados['ultimo'] >= 8:
                atrasados.append((num, dados['ultimo'] / dados['media']))
        
        if atrasados:
            atrasados.sort(key=lambda x: x[1], reverse=True)
            numero = atrasados[0][0]
            
            numeros_base = [numero]
            num_originais = 1
            
            # Expande com vizinhos
            if expandir_vizinhos:
                numeros_final = self.seletor.expandir_com_vizinhos(
                    numeros_base, hist_list, max_numeros, qtd_anteriores=3, qtd_posteriores=3
                )
            else:
                vizinhos = self.roleta.get_vizinhos(numero, raio=2)
                numeros_base.extend(vizinhos)
                numeros_final = self.seletor.selecionar_melhores(numeros_base, hist_list, max_numeros)
            
            return {
                'nome': self.nome,
                'numeros_apostar': sorted(numeros_final),
                'gatilho': f"🌀 Regressão: {numero} atrasado ({ciclos[numero]['ultimo']} rodadas)",
                'confianca': 'Média-Alta',
                'numero_gatilho': numero,
                'tipo': 'ciclo',
                'expandido': expandir_vizinhos and len(numeros_final) > num_originais,
                'num_originais': num_originais
            }
        
        return None


class EstrategiaAgrupamento:
    """Agrupamento dinâmico: detecta zonas ativas na roda"""
    
    def __init__(self):
        self.roleta = RoletaBase()
        self.nome = "Agrupamento"
        self.seletor = SeletorInteligente()
        
    def detectar(self, hist_list, expandir_vizinhos=True, max_numeros=15):
        if len(hist_list) < 5:
            return None
        
        ultimos_5 = hist_list[-5:]
        agrupado, grupo = self.roleta.get_regiao(ultimos_5)
        
        if agrupado and len(grupo) >= 3:
            num_originais = len(grupo)
            
            # Expande a região
            if expandir_vizinhos:
                regiao_completa = set(grupo)
                for num in grupo:
                    anteriores = self.roleta.get_vizinhos_anteriores(num, 2)
                    posteriores = self.roleta.get_vizinhos_posteriores(num, 2)
                    regiao_completa.update(anteriores)
                    regiao_completa.update(posteriores)
                
                numeros_final = self.seletor.selecionar_melhores(
                    list(regiao_completa), hist_list, max_numeros
                )
            else:
                numeros_final = self.seletor.selecionar_melhores(grupo, hist_list, max_numeros)
            
            return {
                'nome': self.nome,
                'numeros_apostar': sorted(numeros_final),
                'gatilho': f"🎰 Agrupamento na roda: {grupo[:3]}...",
                'confianca': 'Alta',
                'grupo': grupo,
                'tipo': 'agrupamento',
                'expandido': expandir_vizinhos and len(numeros_final) > num_originais,
                'num_originais': num_originais
            }
        
        return None


class EstrategiaEntropia:
    """Mede a "bagunça" da sequência"""
    
    def __init__(self):
        self.nome = "Entropia"
        self.seletor = SeletorInteligente()
        
    def _calcular_entropia(self, sequencia):
        if len(sequencia) < 5:
            return 1.0
        
        contagem = Counter(sequencia)
        total = len(sequencia)
        
        entropia = 0
        for count in contagem.values():
            prob = count / total
            entropia -= prob * math.log2(prob)
        
        entropia_max = math.log2(min(37, total))
        if entropia_max > 0:
            return entropia / entropia_max
        
        return 1.0
    
    def detectar(self, hist_list, ultimo, expandir_vizinhos=True, max_numeros=15):
        if len(hist_list) < 15:
            return None
        
        janela = hist_list[-15:]
        entropia = self._calcular_entropia(janela)
        
        if entropia < 0.35:
            frequencias = Counter(janela)
            numeros_base = [num for num, _ in frequencias.most_common(5)]
            num_originais = len(numeros_base)
            
            if expandir_vizinhos:
                numeros_final = self.seletor.expandir_com_vizinhos(
                    numeros_base, hist_list, max_numeros, qtd_anteriores=2, qtd_posteriores=2
                )
            else:
                numeros_final = self.seletor.selecionar_melhores(numeros_base, hist_list, max_numeros)
            
            return {
                'nome': self.nome,
                'numeros_apostar': sorted(numeros_final),
                'gatilho': f"📐 Entropia BAIXA ({entropia:.2f}) - continuidade",
                'confianca': 'Alta',
                'entropia': entropia,
                'tipo': 'entropia_baixa',
                'expandido': expandir_vizinhos and len(numeros_final) > num_originais,
                'num_originais': num_originais
            }
        
        elif entropia > 0.75:
            numeros_base = set()
            numeros_base.add(0)
            numeros_base.add(ultimo)
            
            for i in [9, 18, 27]:
                numeros_base.add(i)
            
            frequencias = Counter(hist_list)
            for num, _ in frequencias.most_common(3):
                numeros_base.add(num)
            
            numeros_base_list = list(numeros_base)
            num_originais = len(numeros_base_list)
            
            if expandir_vizinhos:
                numeros_final = self.seletor.expandir_com_vizinhos(
                    numeros_base_list, hist_list, max_numeros, qtd_anteriores=1, qtd_posteriores=1
                )
            else:
                numeros_final = self.seletor.selecionar_melhores(numeros_base_list, hist_list, max_numeros)
            
            return {
                'nome': self.nome,
                'numeros_apostar': sorted(numeros_final),
                'gatilho': f"📐 Entropia ALTA ({entropia:.2f}) - espalhado",
                'confianca': 'Média',
                'entropia': entropia,
                'tipo': 'entropia_alta',
                'expandido': expandir_vizinhos and len(numeros_final) > num_originais,
                'num_originais': num_originais
            }
        
        return None


class EstrategiaCompressao:
    """Compressão: números "apertando" """
    
    def __init__(self):
        self.roleta = RoletaBase()
        self.nome = "Compressão"
        self.seletor = SeletorInteligente()
        
    def detectar(self, hist_list, expandir_vizinhos=True, max_numeros=15):
        if len(hist_list) < 6:
            return None
        
        ultimos_6 = hist_list[-6:]
        ordenados = sorted(ultimos_6)
        
        for i in range(len(ordenados) - 3):
            if ordenados[i+3] - ordenados[i] <= 8:
                zona_comprimida = set(ordenados[i:i+4])
                numeros_fora = set()
                for num in range(37):
                    distancias = [abs(num - z) for z in zona_comprimida]
                    if min(distancias) > 10:
                        numeros_fora.add(num)
                
                if len(numeros_fora) > 5:
                    numeros_base = list(numeros_fora)[:10]
                    num_originais = len(numeros_base)
                    
                    if expandir_vizinhos:
                        numeros_final = self.seletor.expandir_com_vizinhos(
                            numeros_base, hist_list, max_numeros, qtd_anteriores=2, qtd_posteriores=2
                        )
                    else:
                        numeros_final = self.seletor.selecionar_melhores(numeros_base, hist_list, max_numeros)
                    
                    return {
                        'nome': self.nome,
                        'numeros_apostar': sorted(numeros_final),
                        'gatilho': f"💥 Compressão detectada - esperando EXPANSÃO",
                        'confianca': 'Alta',
                        'zona_comprimida': list(zona_comprimida),
                        'tipo': 'compressao',
                        'expandido': expandir_vizinhos and len(numeros_final) > num_originais,
                        'num_originais': num_originais
                    }
        
        return None


class EstrategiaCluster:
    """Cluster original"""
    
    def __init__(self):
        self.roleta = RoletaBase()
        self.nome = "Cluster"
        self.seletor = SeletorInteligente()
        
    def detectar(self, hist_list, ultimo, expandir_vizinhos=True, max_numeros=15):
        if len(hist_list) < 3:
            return None
        
        if len(hist_list) >= 2 and hist_list[-1] == hist_list[-2]:
            return self._gerar_cluster(ultimo, "Repetição direta", hist_list, expandir_vizinhos, max_numeros)
        
        if len(hist_list) >= 5:
            ultimos_5 = hist_list[-5:]
            contagem = Counter(ultimos_5)
            for num, count in contagem.items():
                if count >= 2 and num == ultimo:
                    return self._gerar_cluster(num, f"2x em 5 rodadas", hist_list, expandir_vizinhos, max_numeros)
        
        return None
    
    def _gerar_cluster(self, numero, motivo, hist_list, expandir_vizinhos, max_numeros):
        numeros_base = [numero]
        num_originais = 1
        
        if expandir_vizinhos:
            numeros_final = self.seletor.expandir_com_vizinhos(
                numeros_base, hist_list, max_numeros, qtd_anteriores=2, qtd_posteriores=2
            )
        else:
            vizinhos = self.roleta.get_vizinhos(numero, raio=2)
            numeros_base.extend(vizinhos)
            numeros_final = self.seletor.selecionar_melhores(numeros_base, hist_list, max_numeros)
        
        return {
            'nome': self.nome,
            'numeros_apostar': sorted(numeros_final),
            'gatilho': f"🔥 {motivo}: {numero}",
            'confianca': 'Alta',
            'numero_gatilho': numero,
            'tipo': 'cluster',
            'expandido': expandir_vizinhos and len(numeros_final) > num_originais,
            'num_originais': num_originais
        }


class EstrategiaNucleoQuente:
    """Núcleo Quente original"""
    
    def __init__(self):
        self.nome = "Núcleo Quente"
        self.numeros_quentes = [33, 14, 17, 30, 25, 32, 8, 7]
        self.seletor = SeletorInteligente()
        
    def detectar(self, hist_list, expandir_vizinhos=True, max_numeros=15):
        if len(hist_list) < 5:
            return None
        
        ultimos_5 = hist_list[-5:]
        quentes_recentes = [n for n in ultimos_5 if n in self.numeros_quentes]
        
        if len(quentes_recentes) >= 2:
            frequencias = Counter(hist_list)
            top_frequentes = [num for num, _ in frequencias.most_common(5)]
            numeros_base = list(set(self.numeros_quentes + top_frequentes))[:8]
            num_originais = len(numeros_base)
            
            if expandir_vizinhos:
                numeros_final = self.seletor.expandir_com_vizinhos(
                    numeros_base, hist_list, max_numeros, qtd_anteriores=2, qtd_posteriores=2
                )
            else:
                numeros_final = self.seletor.selecionar_melhores(numeros_base, hist_list, max_numeros)
            
            return {
                'nome': self.nome,
                'numeros_apostar': sorted(numeros_final),
                'gatilho': f"🎯 {len(quentes_recentes)} quentes: {quentes_recentes}",
                'confianca': 'Alta',
                'tipo': 'nucleo_quente',
                'expandido': expandir_vizinhos and len(numeros_final) > num_originais,
                'num_originais': num_originais
            }
        
        return None


class EstrategiaPosSequencia:
    """Pós-Sequência original"""
    
    def __init__(self):
        self.roleta = RoletaBase()
        self.nome = "Pós-Sequência"
        self.seletor = SeletorInteligente()
        
    def detectar(self, hist_list, expandir_vizinhos=True, max_numeros=15):
        if len(hist_list) < 4:
            return None
        
        for i in range(len(hist_list) - 3, len(hist_list) - 1):
            if i >= 2:
                if hist_list[i-2] == hist_list[i-1] == hist_list[i]:
                    numero_rep = hist_list[i]
                    numero_quebra = hist_list[i+1]
                    
                    if numero_quebra != numero_rep:
                        numeros_base = [numero_rep]
                        oposto = self.roleta.get_oposto(numero_rep)
                        if oposto:
                            numeros_base.append(oposto)
                        
                        num_originais = len(numeros_base)
                        
                        if expandir_vizinhos:
                            numeros_final = self.seletor.expandir_com_vizinhos(
                                numeros_base, hist_list, max_numeros, qtd_anteriores=3, qtd_posteriores=3
                            )
                        else:
                            vizinhos = self.roleta.get_vizinhos(numero_rep, raio=2)
                            numeros_base.extend(vizinhos)
                            numeros_final = self.seletor.selecionar_melhores(numeros_base, hist_list, max_numeros)
                        
                        return {
                            'nome': self.nome,
                            'numeros_apostar': sorted(numeros_final),
                            'gatilho': f"💣 Quebra após {numero_rep}→{numero_rep}→{numero_rep}",
                            'confianca': 'Média-Alta',
                            'tipo': 'pos_sequencia',
                            'expandido': expandir_vizinhos and len(numeros_final) > num_originais,
                            'num_originais': num_originais
                        }
        
        return None


class EstrategiaBloco:
    """Bloco original"""
    
    def __init__(self):
        self.nome = "Bloco"
        
    def detectar(self, hist_list, expandir_vizinhos=True, max_numeros=15):
        if len(hist_list) < 5:
            return None
        
        ultimos = hist_list[-6:]
        
        altos = 0
        for n in reversed(ultimos):
            if n > 19:
                altos += 1
            else:
                break
        
        baixos = 0
        for n in reversed(ultimos):
            if n <= 18:
                baixos += 1
            else:
                break
        
        if altos >= 4:
            numeros = list(range(0, 19))
            if len(numeros) > max_numeros:
                numeros = numeros[:max_numeros]
            return {
                'nome': self.nome,
                'numeros_apostar': sorted(numeros),
                'gatilho': f"📊 {altos} altos seguidos → BAIXOS",
                'confianca': 'Média',
                'tipo': 'bloco',
                'expandido': False,
                'num_originais': 19
            }
        
        if baixos >= 4:
            numeros = list(range(19, 37))
            if len(numeros) > max_numeros:
                numeros = numeros[:max_numeros]
            return {
                'nome': self.nome,
                'numeros_apostar': sorted(numeros),
                'gatilho': f"📊 {baixos} baixos seguidos → ALTOS",
                'confianca': 'Média',
                'tipo': 'bloco',
                'expandido': False,
                'num_originais': 18
            }
        
        return None


class EstrategiaMultiplicador:
    """Multiplicador original"""
    
    def __init__(self):
        self.nome = "Multiplicador"
        self.numeros_quentes = [33, 14, 17, 30, 25, 32, 8, 7]
        self.seletor = SeletorInteligente()
        
    def detectar(self, hist_list, hist_mult, expandir_vizinhos=True, max_numeros=15):
        if len(hist_list) < 8:
            return None
        
        mult_list = list(hist_mult)
        
        rodadas_sem = 0
        for m in reversed(mult_list):
            if m and m >= 500:
                break
            rodadas_sem += 1
        
        if 5 <= rodadas_sem <= 12:
            numeros_base = set()
            numeros_base.add(0)
            
            for n in self.numeros_quentes[:4]:
                numeros_base.add(n)
            
            for n in hist_list[-3:]:
                numeros_base.add(n)
            
            frequencias = Counter(hist_list)
            for num, _ in frequencias.most_common(5):
                numeros_base.add(num)
            
            numeros_base_list = list(numeros_base)
            num_originais = len(numeros_base_list)
            
            if expandir_vizinhos:
                numeros_final = self.seletor.expandir_com_vizinhos(
                    numeros_base_list, hist_list, max_numeros, qtd_anteriores=2, qtd_posteriores=2
                )
            else:
                numeros_final = self.seletor.selecionar_melhores(numeros_base_list, hist_list, max_numeros)
            
            return {
                'nome': self.nome,
                'numeros_apostar': sorted(numeros_final),
                'gatilho': f"🚀 {rodadas_sem} rodadas sem spike",
                'confianca': 'Alta',
                'tipo': 'multiplicador',
                'expandido': expandir_vizinhos and len(numeros_final) > num_originais,
                'num_originais': num_originais
            }
        
        return None


# =============================
# DETECTOR DE GATILHOS UNIFICADO
# =============================
class DetectorGatilhosUnificado:
    """Avalia TODAS as estratégias e retorna a melhor ativada"""
    
    def __init__(self):
        self.roleta = RoletaBase()
        
        # Mapeamento de estratégias
        self.estrategias_map = {
            'Cluster': EstrategiaCluster(),
            'PosSequencia': EstrategiaPosSequencia(),
            'Markov': EstrategiaMarkovTransicao(),
            'Agrupamento': EstrategiaAgrupamento(),
            'Compressao': EstrategiaCompressao(),
            'Ciclo': EstrategiaCiclo(),
            'NucleoQuente': EstrategiaNucleoQuente(),
            'Bloco': EstrategiaBloco(),
            'Salto': EstrategiaSalto(),
            'Entropia': EstrategiaEntropia(),
            'Multiplicador': EstrategiaMultiplicador()
        }
        
        # Ordem de prioridade
        self.ordem_prioridade = [
            'Cluster', 'PosSequencia', 'Markov', 'Agrupamento', 
            'Compressao', 'Ciclo', 'NucleoQuente', 'Bloco', 
            'Salto', 'Entropia', 'Multiplicador'
        ]
        
    def detectar(self, hist_list, hist_mult, ultimo, matriz_transicao, ciclos_numeros, 
                 perdas_cluster=0, perdas_bloco=0, estrategias_ativas=None,
                 expandir_vizinhos=True, max_numeros=15):
        """
        Avalia todas as estratégias ATIVAS e retorna a primeira ativada
        """
        if len(hist_list) < 3:
            return None
        
        if estrategias_ativas is None:
            estrategias_ativas = {nome: True for nome in self.ordem_prioridade}
        
        for nome in self.ordem_prioridade:
            # Pula se estratégia não estiver ativa
            if not estrategias_ativas.get(nome, True):
                continue
            
            # Verifica stops
            if nome == 'Cluster' and perdas_cluster >= 2:
                continue
            if nome == 'Bloco' and perdas_bloco >= 2:
                continue
            
            estrategia = self.estrategias_map[nome]
            
            # Chama o método detectar apropriado para cada estratégia
            resultado = None
            
            if nome == 'Cluster':
                resultado = estrategia.detectar(hist_list, ultimo, expandir_vizinhos, max_numeros)
            elif nome == 'PosSequencia':
                resultado = estrategia.detectar(hist_list, expandir_vizinhos, max_numeros)
            elif nome == 'Markov':
                resultado = estrategia.detectar(hist_list, ultimo, matriz_transicao, expandir_vizinhos, max_numeros)
            elif nome == 'Agrupamento':
                resultado = estrategia.detectar(hist_list, expandir_vizinhos, max_numeros)
            elif nome == 'Compressao':
                resultado = estrategia.detectar(hist_list, expandir_vizinhos, max_numeros)
            elif nome == 'Ciclo':
                resultado = estrategia.detectar(hist_list, ciclos_numeros, expandir_vizinhos, max_numeros)
            elif nome == 'NucleoQuente':
                resultado = estrategia.detectar(hist_list, expandir_vizinhos, max_numeros)
            elif nome == 'Bloco':
                resultado = estrategia.detectar(hist_list, expandir_vizinhos, max_numeros)
            elif nome == 'Salto':
                resultado = estrategia.detectar(hist_list, ultimo, expandir_vizinhos, max_numeros)
            elif nome == 'Entropia':
                resultado = estrategia.detectar(hist_list, ultimo, expandir_vizinhos, max_numeros)
            elif nome == 'Multiplicador':
                resultado = estrategia.detectar(hist_list, hist_mult, expandir_vizinhos, max_numeros)
            
            if resultado:
                return resultado
        
        return None


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
        
        # Matriz de transição (Markov)
        self.matriz_transicao = defaultdict(Counter)
        self.ciclos_numeros = {}
        
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
        
    def _atualizar_matriz_transicao(self, hist_list):
        """Atualiza matriz de transição Markov"""
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
        
        # Verifica resultado da previsão anterior
        if self.previsao_ativa:
            acerto = numero_real in self.previsao_ativa.get('numeros_apostar', [])
            nome = self.previsao_ativa['nome']
            
            if nome not in self.estrategias_contador:
                self.estrategias_contador[nome] = {'acertos': 0, 'total': 0}
            self.estrategias_contador[nome]['total'] += 1
            
            if acerto:
                self.estrategias_contador[nome]['acertos'] += 1
                self.acertos += 1
                if nome == 'Cluster':
                    self.perdas_cluster = 0
                elif nome == 'Bloco':
                    self.perdas_bloco = 0
            else:
                self.erros += 1
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
        hist_list = list(self.historico_numeros)
        if len(hist_list) > 0:
            ultimo = hist_list[-1]
            
            # Obtém configurações da sessão
            estrategias_ativas = st.session_state.get('estrategias_ativas', {
                'Cluster': True, 'PosSequencia': True, 'Markov': True,
                'Agrupamento': True, 'Compressao': True, 'Ciclo': True,
                'NucleoQuente': True, 'Bloco': True, 'Salto': True,
                'Entropia': True, 'Multiplicador': True
            })
            
            expandir_vizinhos = st.session_state.get('expandir_com_vizinhos', True)
            max_numeros = st.session_state.get('max_numeros_entrada', 15)
            
            nova = self.detector.detectar(
                hist_list,
                self.historico_multiplicadores,
                ultimo,
                self.matriz_transicao,
                self.ciclos_numeros,
                self.perdas_cluster,
                self.perdas_bloco,
                estrategias_ativas,
                expandir_vizinhos,
                max_numeros
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
        self.perdas_cluster = 0
        self.perdas_bloco = 0
        salvar_sessao()
    
    def get_analise_completa(self):
        """Retorna análise completa"""
        if len(self.historico_numeros) < 5:
            return "📊 Aguardando dados para análise..."
        
        hist_list = list(self.historico_numeros)
        ultimo = hist_list[-1]
        
        analise = "🎯 ANÁLISE COMPLETA DE GATILHOS\n"
        analise += "=" * 50 + "\n\n"
        analise += f"🎲 Último: {ultimo}\n"
        analise += f"📊 Últimos 10: {hist_list[-10:]}\n\n"
        
        analise += "📈 STATUS DAS ESTRATÉGIAS:\n"
        analise += "-" * 30 + "\n"
        
        estrategias_ativas = st.session_state.get('estrategias_ativas', {})
        for nome in ['Cluster', 'PosSequencia', 'Markov', 'Agrupamento', 'Compressao', 
                     'Ciclo', 'NucleoQuente', 'Bloco', 'Salto', 'Entropia', 'Multiplicador']:
            status = "✅ ATIVA" if estrategias_ativas.get(nome, True) else "❌ INATIVA"
            emoji = {
                'Cluster': '🔥', 'PosSequencia': '💣', 'Markov': '🧠',
                'Agrupamento': '🎰', 'Compressao': '💥', 'Ciclo': '🌀',
                'NucleoQuente': '🎯', 'Bloco': '📊', 'Salto': '⚡',
                'Entropia': '📐', 'Multiplicador': '🚀'
            }.get(nome, '🎲')
            analise += f"{emoji} {nome}: {status}\n"
        
        # Mostra configuração de expansão
        expandir = st.session_state.get('expandir_com_vizinhos', True)
        max_num = st.session_state.get('max_numeros_entrada', 15)
        analise += f"\n⚙️ Expansão: {'✅ ATIVA' if expandir else '❌ INATIVA'} | Máx: {max_num} números\n"
        
        analise += "\n" + "=" * 50 + "\n"
        
        if ultimo in self.matriz_transicao and self.matriz_transicao[ultimo]:
            analise += f"\n🧠 Markov - após {ultimo}:\n"
            for prox, count in self.matriz_transicao[ultimo].most_common(3):
                analise += f"  → {prox}: {count}x\n"
        
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
st.set_page_config(page_title="🎯 IA Roleta — 11 Estratégias", layout="centered")
st.title("🎯 IA Roleta — Sistema Multi-Estratégias PRO")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaAutoAdaptativo()

# Inicializa configurações se não existirem
if "estrategias_ativas" not in st.session_state:
    st.session_state.estrategias_ativas = {
        'Cluster': True, 'PosSequencia': True, 'Markov': True,
        'Agrupamento': True, 'Compressao': True, 'Ciclo': True,
        'NucleoQuente': True, 'Bloco': True, 'Salto': True,
        'Entropia': True, 'Multiplicador': True
    }

if "expandir_com_vizinhos" not in st.session_state:
    st.session_state.expandir_com_vizinhos = True

if "max_numeros_entrada" not in st.session_state:
    st.session_state.max_numeros_entrada = 15

if "expandir_sempre" not in st.session_state:
    st.session_state.expandir_sempre = False

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

# ===== CONFIGURAÇÕES DE EXPANSÃO =====
with st.sidebar.expander("🔧 Expansão de Entrada", expanded=True):
    st.write("**Configurações de Vizinhos:**")
    
    st.session_state.expandir_com_vizinhos = st.checkbox(
        "🔄 Expandir com vizinhos", 
        value=st.session_state.expandir_com_vizinhos,
        help="Adiciona 2 vizinhos anteriores e 2 posteriores quando há menos de 8 números"
    )
    
    st.session_state.expandir_sempre = st.checkbox(
        "⚡ Expandir sempre", 
        value=st.session_state.expandir_sempre,
        help="Expande mesmo quando já tem 8+ números"
    )
    
    st.session_state.max_numeros_entrada = st.slider(
        "📊 Máximo de números por entrada",
        min_value=5,
        max_value=20,
        value=st.session_state.max_numeros_entrada,
        step=1,
        help="Limite máximo de números para apostar"
    )
    
    st.caption("💡 Expansão adiciona 2 vizinhos anteriores + 2 posteriores de cada número base")
    
    if st.button("💾 Salvar Configurações", use_container_width=True):
        salvar_sessao()
        st.success("✅ Configurações salvas!")

# ===== SELEÇÃO DE ESTRATÉGIAS =====
with st.sidebar.expander("🎯 Estratégias Ativas", expanded=True):
    st.write("**Selecione quais estratégias usar:**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.session_state.estrategias_ativas['Cluster'] = st.checkbox("🔥 Cluster", value=st.session_state.estrategias_ativas['Cluster'])
        st.session_state.estrategias_ativas['PosSequencia'] = st.checkbox("💣 Pós-Sequência", value=st.session_state.estrategias_ativas['PosSequencia'])
        st.session_state.estrategias_ativas['Markov'] = st.checkbox("🧠 Markov", value=st.session_state.estrategias_ativas['Markov'])
        st.session_state.estrategias_ativas['Agrupamento'] = st.checkbox("🎰 Agrupamento", value=st.session_state.estrategias_ativas['Agrupamento'])
        st.session_state.estrategias_ativas['Compressao'] = st.checkbox("💥 Compressão", value=st.session_state.estrategias_ativas['Compressao'])
        st.session_state.estrategias_ativas['Ciclo'] = st.checkbox("🌀 Ciclo", value=st.session_state.estrategias_ativas['Ciclo'])
    
    with col2:
        st.session_state.estrategias_ativas['NucleoQuente'] = st.checkbox("🎯 Núcleo Quente", value=st.session_state.estrategias_ativas['NucleoQuente'])
        st.session_state.estrategias_ativas['Bloco'] = st.checkbox("📊 Bloco", value=st.session_state.estrategias_ativas['Bloco'])
        st.session_state.estrategias_ativas['Salto'] = st.checkbox("⚡ Salto", value=st.session_state.estrategias_ativas['Salto'])
        st.session_state.estrategias_ativas['Entropia'] = st.checkbox("📐 Entropia", value=st.session_state.estrategias_ativas['Entropia'])
        st.session_state.estrategias_ativas['Multiplicador'] = st.checkbox("🚀 Multiplicador", value=st.session_state.estrategias_ativas['Multiplicador'])
    
    # Botões rápidos
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("✅ Todos", use_container_width=True):
            for k in st.session_state.estrategias_ativas:
                st.session_state.estrategias_ativas[k] = True
            salvar_sessao()
            st.rerun()
    with c2:
        if st.button("❌ Nenhum", use_container_width=True):
            for k in st.session_state.estrategias_ativas:
                st.session_state.estrategias_ativas[k] = False
            salvar_sessao()
            st.rerun()
    with c3:
        if st.button("⭐ Básicas", use_container_width=True):
            for k in st.session_state.estrategias_ativas:
                st.session_state.estrategias_ativas[k] = False
            st.session_state.estrategias_ativas['Cluster'] = True
            st.session_state.estrategias_ativas['NucleoQuente'] = True
            st.session_state.estrategias_ativas['Bloco'] = True
            st.session_state.estrategias_ativas['Multiplicador'] = True
            salvar_sessao()
            st.rerun()
    
    ativas = sum(1 for v in st.session_state.estrategias_ativas.values() if v)
    st.caption(f"📊 {ativas}/11 estratégias ativas")

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

# Resetar stops
if st.sidebar.button("🔄 Resetar Stops", use_container_width=True):
    st.session_state.sistema.perdas_cluster = 0
    st.session_state.sistema.perdas_bloco = 0
    st.success("✅ Stops resetados!")

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
col3.metric("🔥 Cluster", f"{status['perdas_cluster']}/2")
col4.metric("📊 Bloco", f"{status['perdas_bloco']}/2")

# Previsão Ativa
st.subheader("🎯 Previsão Ativa")
sistema = st.session_state.sistema

if sistema.estrategia_ativa_manual:
    st.warning("⚠️ MODO MANUAL ATIVO")
elif sistema.previsao_ativa:
    p = sistema.previsao_ativa
    emoji = {
        'Cluster': '🔥', 'Núcleo Quente': '🎯', 'Pós-Sequência': '💣',
        'Bloco': '📊', 'Multiplicador': '🚀', 'Markov': '🧠',
        'Salto': '⚡', 'Ciclo': '🌀', 'Agrupamento': '🎰',
        'Entropia': '📐', 'Compressão': '💥'
    }.get(p['nome'], '🎲')
    
    if p.get('expandido'):
        st.success(f"{emoji} **{p['nome'].upper()}** (EXPANDIDA)")
        st.caption(f"📊 Expandido de {p.get('num_originais', '?')} → {len(p['numeros_apostar'])} números")
    else:
        st.success(f"{emoji} **{p['nome'].upper()}**")
    
    st.info(f"📋 **Gatilho:** {p['gatilho']}")
    st.write(f"**🔢 Números ({len(p['numeros_apostar'])}):**")
    
    nums = sorted(p['numeros_apostar'])
    colunas = st.columns(6)
    for i, num in enumerate(nums):
        colunas[i % 6].write(f"**{num}**")
else:
    ativas = sum(1 for v in st.session_state.estrategias_ativas.values() if v)
    if ativas == 0:
        st.warning("⚠️ Nenhuma estratégia ativa! Ative pelo menos uma na sidebar.")
    else:
        st.info("🎲 Aguardando gatilhos...")

# Desempenho
st.subheader("📈 Desempenho por Estratégia")
total = sistema.acertos + sistema.erros
taxa = (sistema.acertos / total * 100) if total > 0 else 0.0
st.caption(f"Taxa geral: {taxa:.1f}% ({sistema.acertos}/{total})")

if sistema.estrategias_contador:
    desempenho_ordenado = []
    for nome, dados in sistema.estrategias_contador.items():
        if dados['total'] > 0:
            tx = dados['acertos'] / dados['total'] * 100
            desempenho_ordenado.append((nome, dados, tx))
    
    desempenho_ordenado.sort(key=lambda x: x[2], reverse=True)
    
    for nome, dados, tx in desempenho_ordenado:
        cor = "🟢" if tx >= 50 else "🟡" if tx >= 30 else "🔴"
        emoji = {
            'Cluster': '🔥', 'Núcleo Quente': '🎯', 'Pós-Sequência': '💣',
            'Bloco': '📊', 'Multiplicador': '🚀', 'Markov': '🧠',
            'Salto': '⚡', 'Ciclo': '🌀', 'Agrupamento': '🎰',
            'Entropia': '📐', 'Compressão': '💥'
        }.get(nome, '🎲')
        st.write(f"{cor} {emoji} {nome}: {dados['acertos']}/{dados['total']} ({tx:.1f}%)")

# Histórico recente
if sistema.historico_desempenho:
    st.write("**🔍 Últimas Conferências:**")
    for r in sistema.historico_desempenho[-5:]:
        emoji_result = "🎉" if r['acerto'] else "❌"
        mult = f" ⚡{r['multiplicador']}x" if r.get('multiplicador') and r['acerto'] else ""
        st.write(f"{emoji_result} {r['estrategia']}: {r['numero']}{mult}")

# Download
if os.path.exists(HISTORICO_PATH):
    with open(HISTORICO_PATH, "r") as f:
        st.download_button("📥 Baixar histórico", data=f.read(), file_name="historico_roleta.json")

salvar_sessao()
