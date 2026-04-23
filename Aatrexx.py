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
PERFORMANCE_PATH = "performance_ia.json"

def salvar_sessao():
    """Salva todos os dados da sessão em arquivo"""
    try:
        # Salva performance da IA
        if 'sistema' in st.session_state:
            performance_data = {
                'acertos': st.session_state.sistema.ia.performance['acertos'],
                'erros': st.session_state.sistema.ia.performance['erros'],
                'historico': st.session_state.sistema.ia.performance['historico']
            }
            with open(PERFORMANCE_PATH, 'w') as f:
                json.dump(performance_data, f)
        
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
            'forca_minima_sinal': st.session_state.get('forca_minima_sinal', 45),
            'qtd_vizinhos_antes': st.session_state.get('qtd_vizinhos_antes', 2),
            'qtd_vizinhos_depois': st.session_state.get('qtd_vizinhos_depois', 2),
            'filtro_qualidade': st.session_state.get('filtro_qualidade', True)
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
            
            st.session_state.modo_sniper = session_data.get('modo_sniper', False)
            st.session_state.modo_seguro = session_data.get('modo_seguro', True)
            st.session_state.intervalo_minimo_entradas = session_data.get('intervalo_minimo_entradas', 1)
            st.session_state.expandir_com_vizinhos = session_data.get('expandir_com_vizinhos', True)
            st.session_state.max_numeros_entrada = session_data.get('max_numeros_entrada', 15)
            st.session_state.forca_minima_sinal = session_data.get('forca_minima_sinal', 45)
            st.session_state.qtd_vizinhos_antes = session_data.get('qtd_vizinhos_antes', 2)
            st.session_state.qtd_vizinhos_depois = session_data.get('qtd_vizinhos_depois', 2)
            st.session_state.filtro_qualidade = session_data.get('filtro_qualidade', True)
            
            if 'sistema' in st.session_state:
                st.session_state.sistema.acertos = session_data.get('sistema_acertos', 0)
                st.session_state.sistema.erros = session_data.get('sistema_erros', 0)
                st.session_state.sistema.historico_desempenho = session_data.get('sistema_historico_desempenho', [])
                st.session_state.sistema.historico_numeros = deque(session_data.get('historico_numeros', []), maxlen=200)
                st.session_state.sistema.historico_multiplicadores = deque(session_data.get('historico_multiplicadores', []), maxlen=200)
                st.session_state.sistema.estrategia_ativa_manual = session_data.get('estrategia_ativa_manual', False)
            
            # Carrega performance da IA
            if os.path.exists(PERFORMANCE_PATH) and 'sistema' in st.session_state:
                with open(PERFORMANCE_PATH, 'r') as f:
                    perf = json.load(f)
                    st.session_state.sistema.ia.performance = {
                        'acertos': perf.get('acertos', 0),
                        'erros': perf.get('erros', 0),
                        'historico': perf.get('historico', [])
                    }
            
            logging.info("✅ Sessão carregada com sucesso")
            return True
    except Exception as e:
        logging.error(f"❌ Erro ao carregar sessão: {e}")
    return False

def limpar_sessao():
    """Limpa todos os dados da sessão"""
    try:
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH]:
            if os.path.exists(path):
                os.remove(path)
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
        qualidade = previsao.get('score_qualidade', 0)
        criterios_ativos = previsao.get('criterios_ativos', [])
        
        emoji = "🎯" if tipo_entrada == 'sniper' else "🛡️" if tipo_entrada == 'seguro' else "🎲"
        barras = "█" * (forca // 10) + "░" * (10 - forca // 10)
        
        msg = f"{emoji} **ENTRADA**\n"
        msg += f"⚡ Força: {barras} {forca}%\n"
        msg += f"📊 Qualidade: {qualidade:.0f}%\n"
        if criterios_ativos:
            msg += f"🔍 Critérios: {', '.join(criterios_ativos)}\n"
        msg += f"📈 {num_originais} → {len(numeros)} números\n"
        msg += f"📋 {gatilho}"
        
        st.toast(f"🎯 Entrada - F{forca}% Q{qualidade:.0f}%", icon=emoji)
        
        if forca >= 65:
            st.success(f"🔔 **SINAL!** {msg}")
        else:
            st.warning(f"🔔 {msg}")
        
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            enviar_telegram(f"🔔 ENTRADA\n{msg}")
            metade = len(numeros) // 2
            if metade > 0:
                linha1 = " ".join(map(str, numeros[:metade]))
                linha2 = " ".join(map(str, numeros[metade:]))
                enviar_telegram(f"{emoji} APOSTAR\n{linha1}\n{linha2}")
            else:
                enviar_telegram(f"{emoji} APOSTAR\n" + " ".join(map(str, numeros)))
                
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar previsão: {e}")

def enviar_resultado_auto(numero_real, acerto, multiplicador=None):
    """Envia notificação de resultado"""
    try:
        if acerto:
            msg = f"✅ ACERTO! {numero_real}"
        else:
            msg = f"❌ ERRO! {numero_real}"
        
        if multiplicador and multiplicador > 0:
            msg += f" ⚡{multiplicador}x"
        
        st.toast(f"{'✅' if acerto else '❌'} {numero_real}", icon="✅" if acerto else "❌")
        
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            enviar_telegram(f"📢 {msg}")
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
    except:
        pass

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
        if numero not in self.race:
            return []
        posicao = self.race.index(numero)
        vizinhos = []
        for i in range(1, quantidade + 1):
            vizinhos.append(self.race[(posicao - i) % 37])
        return vizinhos
    
    def get_vizinhos_posteriores(self, numero, quantidade=2):
        if numero not in self.race:
            return []
        posicao = self.race.index(numero)
        vizinhos = []
        for i in range(1, quantidade + 1):
            vizinhos.append(self.race[(posicao + i) % 37])
        return vizinhos
    
    def get_distancia_roda(self, num1, num2):
        if num1 not in self.race or num2 not in self.race:
            return 37
        p1 = self.race.index(num1)
        p2 = self.race.index(num2)
        dist = abs(p1 - p2)
        return min(dist, 37 - dist)


# =============================
# SELETOR INTELIGENTE
# =============================
class SeletorInteligente:
    def __init__(self):
        self.roleta = RoletaBase()
    
    def expandir_com_vizinhos(self, numeros_base, historico, max_numeros=15,
                              qtd_antes=2, qtd_depois=2):
        if len(numeros_base) == 0:
            return [], 0
        
        num_originais = len(numeros_base)
        numeros_expandidos = set(numeros_base)
        
        for num in numeros_base:
            anteriores = self.roleta.get_vizinhos_anteriores(num, qtd_antes)
            numeros_expandidos.update(anteriores)
            posteriores = self.roleta.get_vizinhos_posteriores(num, qtd_depois)
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
        ultimos_5 = hist_list[-5:] if len(hist_list) >= 5 else hist_list
        ultimos_20 = hist_list[-20:] if len(hist_list) >= 20 else hist_list
        ultimo = hist_list[-1] if hist_list else None
        
        scores = {}
        for num in numeros_candidatos:
            score = 0
            
            # Frequência recente
            freq_20 = ultimos_20.count(num) / len(ultimos_20) if ultimos_20 else 0
            score += freq_20 * 30
            
            # Frequência curta
            freq_5 = ultimos_5.count(num) / len(ultimos_5) if ultimos_5 else 0
            score += freq_5 * 20
            
            # Repetição
            if num == ultimo:
                score += 20
            elif num in ultimos_5 and ultimos_5.count(num) >= 2:
                score += 15
            
            # Proximidade com últimos
            for recente in ultimos_5[-3:]:
                dist = self.roleta.get_distancia_roda(num, recente)
                if dist <= 3:
                    score += 10 * (1 - dist/4)
            
            # Atraso
            if num not in ultimos_20:
                score += 5
            
            if num == 0:
                score += 5
            
            scores[num] = score
        
        ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted([num for num, _ in ordenados[:max_numeros]])


# =============================
# ANALISADOR AVANÇADO (NOVOS CRITÉRIOS)
# =============================
class AnalisadorAvancado:
    """Analisa múltiplos critérios avançados da roleta"""
    
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar_transicoes(self, hist_list):
        """O que mais sai DEPOIS de cada número (Markov)"""
        if len(hist_list) < 10:
            return None
        
        ultimo = hist_list[-1]
        transicoes = defaultdict(Counter)
        
        for i in range(len(hist_list) - 1):
            transicoes[hist_list[i]][hist_list[i+1]] += 1
        
        if ultimo in transicoes and transicoes[ultimo]:
            top_seguidores = [n for n, _ in transicoes[ultimo].most_common(3)]
            total_trans = sum(transicoes[ultimo].values())
            confianca = min(100, total_trans * 15)
            
            return {
                'seguidores': top_seguidores,
                'confianca': confianca,
                'total_transicoes': total_trans
            }
        return None
    
    def calcular_entropia(self, hist_list, janela=15):
        """Mede o nível de aleatoriedade da sequência"""
        if len(hist_list) < janela:
            return None
        
        sequencia = hist_list[-janela:]
        contagem = Counter(sequencia)
        total = len(sequencia)
        
        entropia = 0
        for count in contagem.values():
            prob = count / total
            entropia -= prob * math.log2(prob)
        
        entropia_max = math.log2(min(37, total))
        entropia_norm = entropia / entropia_max if entropia_max > 0 else 1.0
        
        return {
            'valor': entropia_norm,
            'status': 'previsivel' if entropia_norm < 0.35 else 'normal' if entropia_norm < 0.60 else 'aleatorio'
        }
    
    def analisar_ciclos_temporais(self, hist_list):
        """Tempo médio entre aparições de cada número"""
        if len(hist_list) < 15:
            return None
        
        ciclos = {}
        for num in range(37):
            posicoes = [i for i, n in enumerate(hist_list) if n == num]
            if len(posicoes) >= 3:
                intervalos = [posicoes[i+1] - posicoes[i] for i in range(len(posicoes)-1)]
                media = sum(intervalos) / len(intervalos)
                desvio = (sum((i - media)**2 for i in intervalos) / len(intervalos)) ** 0.5
                
                if desvio < media * 0.3 and media >= 4:
                    ciclos[num] = {
                        'media': media,
                        'desvio': desvio,
                        'consistencia': 100 - min(100, (desvio/media)*100),
                        'ultimo': len(hist_list) - 1 - posicoes[-1]
                    }
        
        if ciclos:
            melhor = max(ciclos.items(), key=lambda x: x[1]['consistencia'])
            return {
                'numero': melhor[0],
                'info': melhor[1],
                'total_ciclos': len(ciclos)
            }
        return None
    
    def analisar_terminais(self, hist_list):
        """Agrupa números pelo último dígito"""
        if len(hist_list) < 10:
            return None
        
        terminais = defaultdict(list)
        for n in hist_list[-15:]:
            terminais[n % 10].append(n)
        
        quentes = []
        for terminal, numeros in terminais.items():
            if len(numeros) >= 2:
                quentes.append({
                    'terminal': terminal,
                    'numeros': list(set(numeros)),
                    'frequencia': len(numeros)
                })
        
        if quentes:
            quentes.sort(key=lambda x: x['frequencia'], reverse=True)
            return quentes[:3]
        return None
    
    def analisar_ondas(self, hist_list):
        """Detecta padrões de alternância alto/baixo"""
        if len(hist_list) < 10:
            return None
        
        onda = ['A' if n > 18 else 'B' for n in hist_list[-20:]]
        
        alternancias = sum(1 for i in range(len(onda)-1) if onda[i] != onda[i+1])
        sequencias = len(onda) - 1 - alternancias
        total = alternancias + sequencias
        
        if total > 0:
            tendencia = 'alternancia' if alternancias > sequencias else 'sequencia'
            forca = max(alternancias, sequencias) / total
            
            return {
                'tendencia': tendencia,
                'forca': forca * 100,
                'ultimos_5': onda[-5:]
            }
        return None
    
    def analisar_setores(self, hist_list):
        """Divide a roda em setores e analisa atividade"""
        if len(hist_list) < 10:
            return None
        
        setores = {'C1 (1-12)': [], 'C2 (13-24)': [], 'C3 (25-36)': []}
        
        for n in hist_list[-15:]:
            if n == 0:
                continue
            elif n <= 12:
                setores['C1 (1-12)'].append(n)
            elif n <= 24:
                setores['C2 (13-24)'].append(n)
            else:
                setores['C3 (25-36)'].append(n)
        
        ativo = max(setores, key=lambda s: len(setores[s]))
        
        return {
            'setor_ativo': ativo,
            'distribuicao': {s: len(nums) for s, nums in setores.items()},
            'numeros_setor': list(set(setores[ativo]))
        }
    
    def analisar_paridade(self, hist_list):
        """Analisa distribuição de pares e ímpares"""
        if len(hist_list) < 10:
            return None
        
        ultimos_20 = hist_list[-20:] if len(hist_list) >= 20 else hist_list
        
        pares = sum(1 for n in ultimos_20 if n % 2 == 0 and n != 0)
        impares = sum(1 for n in ultimos_20 if n % 2 == 1)
        zeros = sum(1 for n in ultimos_20 if n == 0)
        total = len(ultimos_20)
        
        return {
            'tendencia': 'par' if pares > impares else 'impar',
            'forca': abs(pares - impares) / total * 100,
            'pares_pct': pares/total * 100,
            'impares_pct': impares/total * 100
        }
    
    def detectar_gaps(self, hist_list):
        """Encontra números que não saem há muito tempo"""
        if len(hist_list) < 20:
            return None
        
        gaps = {}
        for num in range(37):
            if num in hist_list:
                ultima_pos = max(i for i, n in enumerate(hist_list) if n == num)
                gaps[num] = len(hist_list) - 1 - ultima_pos
            else:
                gaps[num] = len(hist_list)
        
        mais_atrasados = sorted(gaps.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'atrasados': mais_atrasados,
            'maior_gap': max(gaps.values()),
            'sugestao': [n for n, _ in mais_atrasados[:3]]
        }
    
    def analisar_tudo(self, hist_list):
        """Executa todas as análises e retorna resultados combinados"""
        return {
            'transicoes': self.analisar_transicoes(hist_list),
            'entropia': self.calcular_entropia(hist_list),
            'ciclos': self.analisar_ciclos_temporais(hist_list),
            'terminais': self.analisar_terminais(hist_list),
            'ondas': self.analisar_ondas(hist_list),
            'setores': self.analisar_setores(hist_list),
            'paridade': self.analisar_paridade(hist_list),
            'gaps': self.detectar_gaps(hist_list)
        }
    
    def calcular_forca_avancada(self, hist_list, forca_base=40):
        """Combina todos os critérios em uma força ajustada"""
        analise = self.analisar_tudo(hist_list)
        forca = forca_base
        criterios_ativos = []
        
        # Entropia baixa = mais previsível
        if analise['entropia'] and analise['entropia']['status'] == 'previsivel':
            forca += 15
            criterios_ativos.append('entropia↓')
        
        # Transições fortes
        if analise['transicoes'] and analise['transicoes']['confianca'] > 40:
            forca += 12
            criterios_ativos.append('markov')
        
        # Ciclos consistentes
        if analise['ciclos'] and analise['ciclos']['info']['consistencia'] > 60:
            forca += 10
            criterios_ativos.append('ciclo')
        
        # Terminais concentrados
        if analise['terminais'] and len(analise['terminais']) >= 2:
            forca += 8
            criterios_ativos.append('terminais')
        
        # Ondas fortes
        if analise['ondas'] and analise['ondas']['forca'] > 65:
            forca += 7
            criterios_ativos.append('ondas')
        
        # Setor concentrado
        if analise['setores']:
            max_dist = max(analise['setores']['distribuicao'].values())
            if max_dist >= 8:
                forca += 6
                criterios_ativos.append('setor')
        
        # Paridade definida
        if analise['paridade'] and analise['paridade']['forca'] > 20:
            forca += 5
            criterios_ativos.append('paridade')
        
        # Gaps grandes = cautela
        if analise['gaps'] and analise['gaps']['maior_gap'] > 35:
            forca -= 8
        
        forca = min(100, max(20, int(forca)))
        
        return forca, criterios_ativos


# =============================
# MOTOR IA COM BASE 100% DINÂMICA
# =============================
class RoletaIA:
    def __init__(self):
        self.roleta = RoletaBase()
        self.seletor = SeletorInteligente()
        self.analisador = AnalisadorAvancado(self.roleta)
        self.historico = deque(maxlen=100)
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.ultima_analise = None
        
    def atualizar(self, numero):
        self.historico.append(numero)
        self.ultima_analise = None
        
    def atualizar_resultado(self, acerto):
        self.performance['historico'].append(1 if acerto else 0)
        if len(self.performance['historico']) > 50:
            self.performance['historico'] = self.performance['historico'][-50:]
        if acerto:
            self.performance['acertos'] += 1
        else:
            self.performance['erros'] += 1
    
    def get_taxa_acerto(self):
        total = self.performance['acertos'] + self.performance['erros']
        if total == 0:
            return 0.5
        return self.performance['acertos'] / total
    
    def get_taxa_recente(self, ultimas=10):
        hist = self.performance['historico']
        if len(hist) < ultimas:
            return self.get_taxa_acerto()
        recentes = hist[-ultimas:]
        return sum(recentes) / len(recentes) if recentes else 0.5
    
    def get_total_tentativas(self):
        return self.performance['acertos'] + self.performance['erros']
    
    def analisar(self):
        if len(self.historico) < 8:
            return None
        
        if self.ultima_analise is not None:
            return self.ultima_analise
        
        hist_list = list(self.historico)
        ultimos_15 = hist_list[-15:] if len(hist_list) >= 15 else hist_list
        ultimos_5 = hist_list[-5:] if len(hist_list) >= 5 else hist_list
        ultimos_3 = hist_list[-3:] if len(hist_list) >= 3 else hist_list
        ultimo = hist_list[-1]
        
        # Frequência
        freq_15 = Counter(ultimos_15)
        quentes = [n for n, _ in freq_15.most_common(6)]
        
        # Repetição
        repetidos = [n for n in ultimos_5 if ultimos_5.count(n) >= 2]
        
        # Sequência
        sequencia_ativa = len(hist_list) >= 3 and hist_list[-1] == hist_list[-2] == hist_list[-3]
        numero_sequencia = ultimo if sequencia_ativa else None
        
        # Bloco
        altos_15 = sum(1 for n in ultimos_15 if n > 18)
        baixos_15 = len(ultimos_15) - altos_15
        altos_5 = sum(1 for n in ultimos_5 if n > 18)
        bloco_15 = "alto" if altos_15 > baixos_15 else "baixo"
        bloco_5 = "alto" if altos_5 > len(ultimos_5)//2 else "baixo"
        
        # Cluster físico
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
                for n in ultimos_5:
                    if any(self.roleta.get_distancia_roda(n, m) <= 4 for m in ultimos_5 if m != n):
                        regiao_ativa.append(n)
                regiao_ativa = list(set(regiao_ativa))
        
        # Análise avançada
        analise_avancada = self.analisador.analisar_tudo(hist_list)
        
        # Força base
        forca = 40
        if sequencia_ativa:
            forca += 30
        elif len(repetidos) >= 2:
            forca += 20
        elif len(repetidos) >= 1:
            forca += 10
        
        freq_ultimo = ultimos_15.count(ultimo)
        forca += freq_ultimo * 5
        
        if cluster_fisico:
            forca += 15
        
        if bloco_15 == bloco_5:
            forca += 10
        
        # Ajuste pela análise avançada
        forca_avancada, criterios_ativos = self.analisador.calcular_forca_avancada(hist_list, forca)
        
        # Ajuste pela performance recente
        taxa_rec = self.get_taxa_recente(5)
        if taxa_rec >= 0.4:
            forca_avancada += 10
        elif taxa_rec <= 0.15:
            forca_avancada -= 15
        
        forca_final = min(100, max(25, forca_avancada))
        
        # Score de qualidade
        qualidade = 50
        if sequencia_ativa:
            qualidade += 25
        if len(repetidos) >= 2:
            qualidade += 15
        if cluster_fisico:
            qualidade += 10
        if criterios_ativos:
            qualidade += len(criterios_ativos) * 5
        qualidade = min(100, qualidade)
        
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
            "regiao_ativa": regiao_ativa,
            "forca_sinal": forca_final,
            "score_qualidade": qualidade,
            "criterios_ativos": criterios_ativos,
            "ultimo": ultimo,
            "ultimos_3": ultimos_3,
            "analise_avancada": analise_avancada
        }
        
        return self.ultima_analise
    
    def prever(self, modo_sniper=False, modo_seguro=False, max_numeros=15,
               expandir_vizinhos=True, qtd_antes=2, qtd_depois=2, filtro_qualidade=True):
        if len(self.historico) < 8:
            return None
        
        dados = self.analisar()
        if not dados:
            return None
        
        ultimo = dados["ultimo"]
        analise_avancada = dados.get("analise_avancada", {})
        
        # BASE DINÂMICA
        base = set()
        base.add(ultimo)
        
        # Repetição (PRIORIDADE MÁXIMA)
        for n in dados["repetidos"]:
            base.add(n)
        
        # Sequência ativa
        if dados["sequencia_ativa"] and dados["numero_sequencia"]:
            base.add(dados["numero_sequencia"])
        
        # Cluster físico
        if dados["cluster_fisico"]:
            for n in dados["regiao_ativa"][:4]:
                base.add(n)
        
        # Transições Markov
        if analise_avancada.get('transicoes') and analise_avancada['transicoes']['confianca'] > 40:
            for n in analise_avancada['transicoes']['seguidores'][:2]:
                base.add(n)
        
        # Ciclos consistentes
        if analise_avancada.get('ciclos') and analise_avancada['ciclos']['info']['consistencia'] > 60:
            base.add(analise_avancada['ciclos']['numero'])
        
        # Quentes
        for n in dados["quentes"][:4]:
            base.add(n)
        
        # Últimos 3
        for n in dados["ultimos_3"]:
            base.add(n)
        
        # Gaps (números atrasados)
        if analise_avancada.get('gaps'):
            for n in analise_avancada['gaps']['sugestao'][:2]:
                base.add(n)
        
        numeros_base = list(base)
        num_originais = len(numeros_base)
        
        # Expansão com vizinhos
        if expandir_vizinhos:
            numeros_final, _ = self.seletor.expandir_com_vizinhos(
                numeros_base, self.historico, max_numeros, qtd_antes, qtd_depois
            )
        else:
            numeros_final = sorted(numeros_base)[:max_numeros]
        
        # Ajuste de bloco
        if dados["bloco_5"] == "alto" and dados["bloco_15"] == "alto":
            numeros_altos = [n for n in numeros_final if n > 18]
            if len(numeros_altos) >= 5:
                numeros_final = numeros_altos
        elif dados["bloco_5"] == "baixo" and dados["bloco_15"] == "baixo":
            numeros_baixos = [n for n in numeros_final if n <= 18]
            if len(numeros_baixos) >= 5:
                numeros_final = numeros_baixos
        
        # Ajuste por setor ativo
        if analise_avancada.get('setores'):
            setor = analise_avancada['setores']['setor_ativo']
            if 'C1' in setor:
                numeros_final = [n for n in numeros_final if n <= 12 or n == 0]
            elif 'C2' in setor:
                numeros_final = [n for n in numeros_final if 13 <= n <= 24]
            elif 'C3' in setor:
                numeros_final = [n for n in numeros_final if n >= 25]
        
        # Filtro de qualidade
        if filtro_qualidade and dados['score_qualidade'] < 50:
            numeros_final = self.seletor.selecionar_melhores(
                numeros_final, self.historico, min(len(numeros_final), 8)
            )
        
        # Aplica modos
        if modo_sniper:
            tipo_entrada = "sniper"
            max_final = 7
        elif modo_seguro:
            tipo_entrada = "seguro"
            max_final = 12
        else:
            tipo_entrada = "normal"
            max_final = max_numeros
        
        if len(numeros_final) > max_final:
            numeros_final = self.seletor.selecionar_melhores(
                numeros_final, self.historico, max_final
            )
        
        # Gatilho
        parts = [f"u={ultimo}"]
        if dados["repetidos"]:
            parts.append(f"r={dados['repetidos']}")
        if dados["sequencia_ativa"]:
            parts.append(f"seq={dados['numero_sequencia']}")
        if dados["cluster_fisico"]:
            parts.append("cluster")
        if dados.get("criterios_ativos"):
            parts.append(f"crit={len(dados['criterios_ativos'])}")
        parts.append(f"b={dados['bloco_5']}")
        
        return {
            'nome': 'IA Dinâmica Avançada',
            'numeros_apostar': sorted(numeros_final),
            'gatilho': ", ".join(parts),
            'forca_sinal': dados['forca_sinal'],
            'score_qualidade': dados['score_qualidade'],
            'criterios_ativos': dados.get('criterios_ativos', []),
            'confianca': 'Alta' if dados['forca_sinal'] >= 65 else 'Média',
            'tipo_entrada': tipo_entrada,
            'num_originais': num_originais,
            'expandido': expandir_vizinhos
        }
    
    def get_analise_completa(self):
        if len(self.historico) < 5:
            return "📊 Aguardando dados..."
        
        dados = self.analisar()
        if not dados:
            return "📊 Analisando..."
        
        hist_list = list(self.historico)
        taxa = self.get_taxa_acerto()
        taxa_rec = self.get_taxa_recente(5)
        total = self.get_total_tentativas()
        avancada = dados.get('analise_avancada', {})
        
        analise = "🎯 ANÁLISE IA AVANÇADA\n" + "="*40 + "\n\n"
        analise += f"🎲 Último: {dados['ultimo']}\n"
        analise += f"📊 10 últimos: {hist_list[-10:]}\n\n"
        
        analise += f"🔥 Quentes: {dados['quentes'][:5]}\n"
        analise += f"🔁 Repetidos: {dados['repetidos']}\n"
        
        if dados['sequencia_ativa']:
            analise += f"💥 SEQUÊNCIA: {dados['numero_sequencia']}\n"
        if dados['cluster_fisico']:
            analise += f"🎰 Cluster: {dados['regiao_ativa'][:4]}\n"
        
        # Critérios avançados
        if dados.get('criterios_ativos'):
            analise += f"\n🔍 Critérios ativos: {', '.join(dados['criterios_ativos'])}\n"
        
        if avancada.get('entropia'):
            analise += f"📐 Entropia: {avancada['entropia']['valor']:.2f} ({avancada['entropia']['status']})\n"
        
        if avancada.get('transicoes') and avancada['transicoes']['confianca'] > 40:
            analise += f"🧠 Markov: {avancada['transicoes']['seguidores']}\n"
        
        if avancada.get('ciclos'):
            analise += f"🌀 Ciclo: {avancada['ciclos']['numero']} ({avancada['ciclos']['info']['consistencia']:.0f}%)\n"
        
        if avancada.get('ondas'):
            analise += f"🌊 Ondas: {avancada['ondas']['tendencia']} ({avancada['ondas']['forca']:.0f}%)\n"
        
        if avancada.get('setores'):
            analise += f"📊 Setor: {avancada['setores']['setor_ativo']}\n"
        
        analise += f"\n🌊 Bloco: {dados['bloco_15']} (A:{dados['altos_15']} B:{dados['baixos_15']})\n"
        analise += f"⚡ Força: {dados['forca_sinal']}%\n"
        analise += f"📊 Qualidade: {dados['score_qualidade']}%\n"
        
        if total > 0:
            analise += f"\n📈 Perf: {taxa:.0%} ({self.performance['acertos']}/{total})\n"
            analise += f"📊 Rec(5): {taxa_rec:.0%}\n"
        
        return analise
    
    def zerar(self):
        self.historico.clear()
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.ultima_analise = None


# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaIA:
    def __init__(self):
        self.ia = RoletaIA()
        self.historico_numeros = deque(maxlen=200)
        self.historico_multiplicadores = deque(maxlen=200)
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.rodadas_sem_entrada = 0
        self.ultima_entrada_rodada = -10
        self.estrategia_ativa_manual = False
        
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            numero_real = numero_data['number']
            lucky = numero_data.get('luckyNumbers', [])
            mult = numero_data.get('luckyMultipliers', {}).get(numero_real) if numero_real in lucky else None
        else:
            numero_real = numero_data
            lucky = []
            mult = None
        
        self.ia.atualizar(numero_real)
        self.historico_numeros.append(numero_real)
        self.historico_multiplicadores.append(mult if mult else 0)
        self.rodadas_sem_entrada += 1
        
        # Verifica resultado anterior
        if self.previsao_ativa:
            acerto = numero_real in self.previsao_ativa.get('numeros_apostar', [])
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
        
        if self.estrategia_ativa_manual:
            return
        
        # Intervalo mínimo
        intervalo = st.session_state.get('intervalo_minimo_entradas', 1)
        if len(self.historico_numeros) - self.ultima_entrada_rodada < intervalo:
            return
        
        # Gera previsão
        if len(self.historico_numeros) >= 8:
            nova = self.ia.prever(
                st.session_state.get('modo_sniper', False),
                st.session_state.get('modo_seguro', True),
                st.session_state.get('max_numeros_entrada', 15),
                st.session_state.get('expandir_com_vizinhos', True),
                st.session_state.get('qtd_vizinhos_antes', 2),
                st.session_state.get('qtd_vizinhos_depois', 2),
                st.session_state.get('filtro_qualidade', True)
            )
            
            if nova:
                forca_minima = st.session_state.get('forca_minima_sinal', 45)
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
    except:
        pass

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
    except:
        pass
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
    except:
        return None

def exportar_historico_csv(historico):
    """Exporta histórico em formato CSV"""
    linhas = ["numero,timestamp,multiplicador"]
    for item in historico:
        if isinstance(item, dict):
            n = item.get('number', '')
            ts = item.get('timestamp', '')
            mult = item.get('luckyMultipliers', {}).get(n, '') if isinstance(item.get('luckyMultipliers'), dict) else ''
            linhas.append(f"{n},{ts},{mult}")
        else:
            linhas.append(f"{item},,")
    return "\n".join(linhas)

def exportar_historico_json(historico):
    """Exporta histórico em JSON formatado"""
    return json.dumps(historico, indent=2, ensure_ascii=False)


# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎯 IA Roleta — Análise Avançada", layout="centered")
st.title("🎯 IA Roleta — Motor IA com Análise Avançada")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaIA()

# Valores padrão
defaults = {
    'modo_sniper': False, 'modo_seguro': True, 'forca_minima_sinal': 45,
    'intervalo_minimo_entradas': 1, 'max_numeros_entrada': 15,
    'expandir_com_vizinhos': True, 'qtd_vizinhos_antes': 2,
    'qtd_vizinhos_depois': 2, 'filtro_qualidade': True
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

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

with st.sidebar.expander("🎯 Modo", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.modo_sniper = st.checkbox("🎯 Sniper (5-7)", value=st.session_state.modo_sniper)
    with col2:
        st.session_state.modo_seguro = st.checkbox("🛡️ Seguro (10-12)", value=st.session_state.modo_seguro)
    
    st.session_state.filtro_qualidade = st.checkbox("✅ Filtro Qualidade", value=st.session_state.filtro_qualidade,
        help="Reduz números quando qualidade < 50%")

with st.sidebar.expander("🔧 Expansão", expanded=True):
    st.session_state.expandir_com_vizinhos = st.checkbox("🔄 Expandir vizinhos", value=st.session_state.expandir_com_vizinhos)
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.qtd_vizinhos_antes = st.number_input("⬅️ Antes", 1, 4, st.session_state.qtd_vizinhos_antes)
    with c2:
        st.session_state.qtd_vizinhos_depois = st.number_input("➡️ Depois", 1, 4, st.session_state.qtd_vizinhos_depois)
    st.session_state.max_numeros_entrada = st.slider("📊 Máx números", 5, 18, st.session_state.max_numeros_entrada)

with st.sidebar.expander("⚡ Força", expanded=True):
    st.session_state.forca_minima_sinal = st.slider("Força mínima", 30, 70, st.session_state.forca_minima_sinal, 5)
    st.session_state.intervalo_minimo_entradas = st.slider("⏱️ Intervalo", 0, 3, st.session_state.intervalo_minimo_entradas)

with st.sidebar.expander("🧠 Análise IA Avançada", expanded=True):
    st.text(st.session_state.sistema.ia.get_analise_completa())

with st.sidebar.expander("💾 Geral", expanded=False):
    if st.button("💾 Salvar", use_container_width=True):
        salvar_sessao()
        st.success("✅ Salvo!")
    if st.button("🗑️ Zerar", use_container_width=True):
        if st.checkbox("Confirmar"):
            st.session_state.sistema.zerar_estatisticas()
            st.rerun()

with st.sidebar.expander("🔔 Telegram", expanded=False):
    st.session_state.telegram_token = st.text_input("Token:", value=st.session_state.telegram_token, type="password")
    st.session_state.telegram_chat_id = st.text_input("Chat ID:", value=st.session_state.telegram_chat_id)
    if st.button("Salvar Telegram"):
        salvar_sessao()
        st.success("✅")

# Modo
modo_auto = st.sidebar.checkbox("🔄 Automático", value=not st.session_state.sistema.estrategia_ativa_manual)
if st.sidebar.button("Atualizar"):
    st.session_state.sistema.estrategia_ativa_manual = not modo_auto
    st.rerun()

# Inserção manual
st.subheader("✍️ Inserir Sorteios")
entrada = st.text_input("Números (0-36):")
if st.button("Adicionar") and entrada:
    try:
        nums = [int(n) for n in entrada.split() if n.isdigit() and 0 <= int(n) <= 36]
        for n in nums:
            item = {"number": n, "timestamp": f"m{len(st.session_state.historico)}", "luckyNumbers": [], "luckyMultipliers": {}}
            st.session_state.historico.append(item)
            st.session_state.sistema.processar_novo_numero(item)
        salvar_resultado_em_arquivo(st.session_state.historico)
        salvar_sessao()
        st.success(f"{len(nums)} adicionados!")
        st.rerun()
    except Exception as e:
        st.error(f"Erro: {e}")

# Auto-refresh
st_autorefresh(interval=3000, key="refresh")

# API
resultado = fetch_latest_result()
if st.session_state.historico:
    ultimo_ts = st.session_state.historico[-1].get("timestamp") if st.session_state.historico else None
else:
    ultimo_ts = None

if resultado and resultado.get("timestamp") and resultado["timestamp"] != ultimo_ts:
    n = resultado.get("number")
    if n is not None:
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
            fmt.append(f"⚡**{n}**({mult}x)" if mult else f"⚡**{n}**")
        else:
            fmt.append(str(n))
    st.write(" ".join(fmt))

# Status
status = st.session_state.sistema.get_status()
c1, c2, c3, c4 = st.columns(4)
c1.metric("🟢 Acertos", status['acertos'])
c2.metric("🔴 Erros", status['erros'])
c3.metric("📊 Total", status['total'])
c4.metric("⏳ Sem Entrada", status['rodadas_sem_entrada'])

if status['total'] > 0:
    taxa = status['acertos'] / status['total'] * 100
    st.caption(f"🎯 Taxa: {taxa:.1f}%")

# Previsão
st.subheader("🎯 Previsão Ativa")
sis = st.session_state.sistema

if sis.estrategia_ativa_manual:
    st.warning("⚠️ MANUAL")
elif sis.previsao_ativa:
    p = sis.previsao_ativa
    f = p.get('forca_sinal', 0)
    q = p.get('score_qualidade', 0)
    crit = p.get('criterios_ativos', [])
    barras = "█"*(f//10) + "░"*(10-f//10)
    
    st.success(f"🎯 **ENTRADA** - F:{f}% Q:{q:.0f}% {barras}")
    if crit:
        st.caption(f"🔍 Critérios: {', '.join(crit)}")
    st.caption(f"📋 {p['gatilho']}")
    st.write(f"**🔢 {len(p['numeros_apostar'])} números:**")
    
    nums = sorted(p['numeros_apostar'])
    cols = st.columns(5)
    for i, num in enumerate(nums):
        cols[i%5].write(f"**{num}**")
else:
    st.info(f"🎲 Aguardando... ({status['rodadas_sem_entrada']} rodadas)")

# Performance
st.subheader("📈 Performance IA")
taxa_ia = sis.ia.get_taxa_acerto()
taxa_rec = sis.ia.get_taxa_recente(5)
total_ia = sis.ia.get_total_tentativas()

if total_ia > 0:
    c1, c2 = st.columns(2)
    with c1:
        emoji = "🟢" if taxa_ia >= 0.35 else "🟡" if taxa_ia >= 0.25 else "🔴"
        st.write(f"{emoji} **Geral**: {taxa_ia:.0%} ({sis.ia.performance['acertos']}/{total_ia})")
    with c2:
        if len(sis.ia.performance['historico']) >= 5:
            emoji = "🟢" if taxa_rec >= 0.35 else "🟡" if taxa_rec >= 0.25 else "🔴"
            st.write(f"{emoji} **Recente(5)**: {taxa_rec:.0%}")
        else:
            st.write("⚪ **Recente**: coletando...")
else:
    st.write("⚪ Coletando dados...")

# Histórico
if sis.historico_desempenho:
    st.write("**🔍 Últimas:**")
    for r in sis.historico_desempenho[-5:]:
        e = "🎉" if r['acerto'] else "❌"
        m = f" ⚡{r['multiplicador']}x" if r.get('multiplicador') and r['acerto'] else ""
        st.write(f"{e} IA ({r.get('forca',0)}%): {r['numero']}{m}")

# ===== BOTÃO DE DOWNLOAD DO HISTÓRICO =====
st.subheader("📥 Download do Histórico")

col_d1, col_d2, col_d3 = st.columns(3)

with col_d1:
    if st.button("📥 Baixar JSON", use_container_width=True):
        if st.session_state.historico:
            json_data = exportar_historico_json(st.session_state.historico)
            st.download_button(
                label="⬇️ Clique para baixar",
                data=json_data,
                file_name=f"historico_roleta_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        else:
            st.warning("Sem dados")

with col_d2:
    if st.button("📥 Baixar CSV", use_container_width=True):
        if st.session_state.historico:
            csv_data = exportar_historico_csv(st.session_state.historico)
            st.download_button(
                label="⬇️ Clique para baixar",
                data=csv_data,
                file_name=f"historico_roleta_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.warning("Sem dados")

with col_d3:
    # Mostra total de registros
    total_registros = len(st.session_state.historico)
    st.metric("📊 Registros", total_registros)

# Informações adicionais
with st.expander("ℹ️ Sobre o Histórico"):
    st.write(f"""
    **Total de números capturados:** {total_registros}
    
    **Formatos disponíveis:**
    - **JSON**: Formato completo com todos os campos (number, timestamp, luckyNumbers, luckyMultipliers)
    - **CSV**: Formato tabular (numero, timestamp, multiplicador)
    
    **Dica:** Use o JSON para análise completa ou o CSV para importar em Excel/Google Sheets.
    """)

salvar_sessao()
