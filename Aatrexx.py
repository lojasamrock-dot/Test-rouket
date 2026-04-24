import streamlit as st
import json
import os
import requests
import logging
from collections import Counter, deque
from streamlit_autorefresh import st_autorefresh
import pickle
from datetime import datetime

# =============================
# CONFIGURAÇÕES DE PERSISTÊNCIA
# =============================
SESSION_DATA_PATH = "session_data.pkl"
HISTORICO_PATH = "historico_roleta.json"
PERFORMANCE_PATH = "performance_bot.json"

def salvar_sessao():
    try:
        if 'sistema' in st.session_state:
            performance_data = {
                'acertos': st.session_state.sistema.bot.performance['acertos'],
                'erros': st.session_state.sistema.bot.performance['erros'],
                'historico': st.session_state.sistema.bot.performance['historico']
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
            'historico_lucky': list(st.session_state.sistema.historico_lucky),
            'estrategia_ativa_manual': st.session_state.sistema.estrategia_ativa_manual,
            'top_n_apostas': st.session_state.get('top_n_apostas', 5),
            'forca_minima_sinal': st.session_state.get('forca_minima_sinal', 20),
            'intervalo_minimo_entradas': st.session_state.get('intervalo_minimo_entradas', 0),
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'modo_conservador': st.session_state.get('modo_conservador', True),
            'janela_analise': st.session_state.get('janela_analise', 20)
        }
        
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f)
        
        logging.info("✅ Sessão salva")
        return True
    except Exception as e:
        logging.error(f"❌ Erro ao salvar: {e}")
        return False

def carregar_sessao():
    try:
        if os.path.exists(SESSION_DATA_PATH):
            with open(SESSION_DATA_PATH, 'rb') as f:
                session_data = pickle.load(f)
            
            st.session_state.historico = session_data.get('historico', [])
            st.session_state.telegram_token = session_data.get('telegram_token', '')
            st.session_state.telegram_chat_id = session_data.get('telegram_chat_id', '')
            
            st.session_state.top_n_apostas = session_data.get('top_n_apostas', 5)
            st.session_state.forca_minima_sinal = session_data.get('forca_minima_sinal', 20)
            st.session_state.intervalo_minimo_entradas = session_data.get('intervalo_minimo_entradas', 0)
            st.session_state.modo_automatico = session_data.get('modo_automatico', True)
            st.session_state.modo_conservador = session_data.get('modo_conservador', True)
            st.session_state.janela_analise = session_data.get('janela_analise', 20)
            
            if 'sistema' in st.session_state:
                st.session_state.sistema.acertos = session_data.get('sistema_acertos', 0)
                st.session_state.sistema.erros = session_data.get('sistema_erros', 0)
                st.session_state.sistema.historico_desempenho = session_data.get('sistema_historico_desempenho', [])
                st.session_state.sistema.historico_numeros = deque(session_data.get('historico_numeros', []), maxlen=200)
                st.session_state.sistema.historico_lucky = deque(session_data.get('historico_lucky', []), maxlen=100)
                st.session_state.sistema.estrategia_ativa_manual = session_data.get('estrategia_ativa_manual', False)
            
            if os.path.exists(PERFORMANCE_PATH) and 'sistema' in st.session_state:
                with open(PERFORMANCE_PATH, 'r') as f:
                    perf = json.load(f)
                    st.session_state.sistema.bot.performance = {
                        'acertos': perf.get('acertos', 0),
                        'erros': perf.get('erros', 0),
                        'historico': perf.get('historico', [])
                    }
            
            logging.info("✅ Sessão carregada")
            return True
    except Exception as e:
        logging.error(f"❌ Erro ao carregar: {e}")
    return False

def limpar_sessao():
    try:
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH]:
            if os.path.exists(path):
                os.remove(path)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    except:
        pass

# =============================
# NOTIFICAÇÕES
# =============================
def enviar_previsao_auto(previsao):
    try:
        numeros = sorted(previsao['numeros_apostar'])
        confianca = previsao.get('confianca', 'Média')
        estrategias = previsao.get('estrategias_ativas', [])
        
        emoji = "🟢" if confianca == "Alta" else "🟡" if confianca == "Média" else "🔴"
        
        msg = f"{emoji} **ENTRADA** - Confiança: {confianca}\n"
        msg += f"📋 {previsao['gatilho']}\n"
        if estrategias:
            msg += f"🎯 Estratégias: {', '.join(estrategias)}\n"
        msg += f"🔢 {len(numeros)} números"
        
        st.toast(f"🎯 Entrada - {confianca}", icon=emoji)
        
        if confianca == "Alta":
            st.success(f"🔔 {msg}")
        else:
            st.warning(f"🔔 {msg}")
        
        if st.session_state.telegram_token and st.session_state.telegram_chat_id:
            enviar_telegram(f"🔔 ENTRADA [{confianca}]\n{msg}\n" + " ".join(map(str, numeros)))
        
        salvar_sessao()
    except Exception as e:
        logging.error(f"Erro ao enviar: {e}")

def enviar_resultado_auto(numero_real, acerto, multiplicador=None):
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
        
        salvar_sessao()
    except:
        pass

def enviar_telegram(mensagem):
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
# API
# =============================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# =============================
# ANALISADOR ROLETA VERSÁTIL (JANELA DESLIZANTE)
# =============================
class AnalisadorRoletaVersatil:
    """
    Analisador com janela deslizante que se adapta ao momento atual da mesa.
    Estratégias: Frequência, Setores, Vizinhos, Cores, Lucky Numbers
    """
    
    def __init__(self, janela_analise=20):
        self.janela_analise = janela_analise
        # Layout da Roleta Europeia (ordem física na roda)
        self.layout_roda = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 
                           11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 
                           9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        
        # Propriedades dos números
        self.vermelhos = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        self.pretos = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
        
    def mapear_propriedades(self, n):
        """Mapeia todas as propriedades de um número"""
        if n == 0:
            return {
                'cor': 'Verde', 'duzia': 0, 'coluna': 0, 
                'paridade': 'Zero', 'alto_baixo': 'Zero'
            }
        
        return {
            'cor': 'Vermelho' if n in self.vermelhos else 'Preto',
            'duzia': (n-1)//12 + 1,  # 1, 2 ou 3
            'coluna': (n-1)%3 + 1,   # 1, 2 ou 3
            'paridade': 'Par' if n % 2 == 0 else 'Ímpar',
            'alto_baixo': 'Alto' if n >= 19 else 'Baixo'
        }
    
    def get_vizinhos_roda(self, numero, raio=2):
        """Retorna vizinhos físicos na roda (raio para cada lado)"""
        if numero not in self.layout_roda:
            return []
        idx = self.layout_roda.index(numero)
        vizinhos = []
        for i in range(-raio, raio + 1):
            vizinhos.append(self.layout_roda[(idx + i) % 37])
        return vizinhos
    
    def get_setor_dominante(self, numeros):
        """Identifica qual setor da roda está mais ativo"""
        if len(numeros) < 5:
            return None, []
        
        # Divide a roda em 3 setores
        setores = {
            'Setor 1 (0-12)': range(0, 13),
            'Setor 2 (13-24)': range(13, 25),
            'Setor 3 (25-36)': range(25, 37)
        }
        
        contagem = {}
        for nome, numeros_setor in setores.items():
            contagem[nome] = sum(1 for n in numeros if n in numeros_setor)
        
        setor_dominante = max(contagem, key=contagem.get)
        numeros_setor = [n for n in setores[setor_dominante]]
        
        return setor_dominante, numeros_setor
    
    def analisar(self, historico_numeros, lucky_recentes=None):
        """
        Análise completa usando janela deslizante
        """
        if len(historico_numeros) < 5:
            return None
        
        # Aplica janela deslizante (últimos N giros)
        recentes = historico_numeros[-self.janela_analise:]
        dados_recentes = [self.mapear_propriedades(n) for n in recentes]
        
        ultimo = recentes[-1] if recentes else None
        
        # 1. FREQUÊNCIA - Números Quentes do Momento
        frequencia = Counter(recentes)
        quentes = [num for num, _ in frequencia.most_common(5)]
        
        # 2. SETOR DOMINANTE (Dúzias e Colunas)
        duzias = Counter([d['duzia'] for d in dados_recentes if d['duzia'] != 0])
        colunas = Counter([c['coluna'] for c in dados_recentes if c['coluna'] != 0])
        melhor_duzia = duzias.most_common(1)[0][0] if duzias else None
        melhor_coluna = colunas.most_common(1)[0][0] if colunas else None
        
        # 3. SETOR DA RODA
        setor_nome, numeros_setor = self.get_setor_dominante(recentes)
        
        # 4. VIZINHOS DO ÚLTIMO GIRO
        vizinhos = self.get_vizinhos_roda(ultimo, raio=2) if ultimo else []
        
        # 5. TENDÊNCIA DE COR
        cores = Counter([d['cor'] for d in dados_recentes])
        cor_dominante = cores.most_common(1)[0][0] if cores else 'Verde'
        
        # 6. TENDÊNCIA ALTO/BAIXO
        altos = sum(1 for d in dados_recentes if d['alto_baixo'] == 'Alto')
        baixos = sum(1 for d in dados_recentes if d['alto_baixo'] == 'Baixo')
        tendencia_altura = 'Alto' if altos > baixos else 'Baixo'
        
        # 7. TENDÊNCIA PAR/ÍMPAR
        pares = sum(1 for d in dados_recentes if d['paridade'] == 'Par')
        impares = sum(1 for d in dados_recentes if d['paridade'] == 'Ímpar')
        tendencia_paridade = 'Par' if pares > impares else 'Ímpar'
        
        # 8. REPETIÇÕES
        repeticoes = []
        for i in range(1, len(recentes)):
            if recentes[i] == recentes[i-1]:
                repeticoes.append(recentes[i])
        
        # 9. LUCKY NUMBERS (se fornecidos)
        lucky_quentes = []
        if lucky_recentes:
            lucky_contagem = Counter(lucky_recentes)
            lucky_quentes = [n for n, _ in lucky_contagem.most_common(5)]
        
        # 10. FORÇA DO SINAL
        forca = 30
        if repeticoes:
            forca += 25
        if len(set(recentes[-5:])) <= 3:
            forca += 15
        if cor_dominante != 'Verde' and cores[cor_dominante] >= len(recentes) * 0.6:
            forca += 10
        if duzias and duzias[melhor_duzia] >= len(recentes) * 0.5:
            forca += 10
        
        forca = min(100, max(15, forca))
        
        return {
            'quentes': quentes,
            'melhor_duzia': melhor_duzia,
            'melhor_coluna': melhor_coluna,
            'setor_roda': setor_nome,
            'numeros_setor': numeros_setor[:6],
            'vizinhos_ultimo': vizinhos,
            'cor_dominante': cor_dominante,
            'tendencia_altura': tendencia_altura,
            'tendencia_paridade': tendencia_paridade,
            'repeticoes': list(set(repeticoes)),
            'lucky_quentes': lucky_quentes,
            'forca_sinal': forca,
            'ultimo': ultimo
        }


# =============================
# BOT V3 COM ANALISADOR VERSÁTIL
# =============================
class RoletaBotV3:
    def __init__(self, janela_analise=20):
        self.analisador = AnalisadorRoletaVersatil(janela_analise)
        self.historico = []
        self.lucky = []
        self.lucky_mult = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        
    def atualizar(self, numero, lucky_nums=None, lucky_mults=None):
        self.historico.append(numero)
        self.lucky.append(lucky_nums if lucky_nums else [])
        self.lucky_mult.append(lucky_mults if lucky_mults else {})
        if len(self.historico) > 100:
            self.historico = self.historico[-100:]
            self.lucky = self.lucky[-100:]
            self.lucky_mult = self.lucky_mult[-100:]
    
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
        return self.performance['acertos'] / total if total > 0 else 0
    
    def get_taxa_recente(self, n=5):
        hist = self.performance['historico']
        if len(hist) < n:
            return self.get_taxa_acerto()
        return sum(hist[-n:]) / n if hist[-n:] else 0
    
    def get_total_tentativas(self):
        return self.performance['acertos'] + self.performance['erros']
    
    def sugerir_aposta(self, top_n=5, forca_minima=20, modo_conservador=True):
        if len(self.historico) < 5:
            return None
        
        # Prepara lucky numbers recentes
        lucky_recentes = []
        for sub in self.lucky[-10:]:
            lucky_recentes.extend(sub)
        
        # Análise versátil com janela deslizante
        analise = self.analisador.analisar(list(self.historico), lucky_recentes)
        
        if not analise:
            return None
        
        # 🎯 CONSTRUÇÃO DA BASE (múltiplas estratégias combinadas)
        base = set()
        estrategias_ativas = []
        
        # 1. Números quentes (frequência recente)
        for n in analise['quentes'][:3]:
            base.add(n)
        if analise['quentes']:
            estrategias_ativas.append('Quentes')
        
        # 2. Repetições (máxima prioridade)
        for n in analise['repeticoes']:
            base.add(n)
        if analise['repeticoes']:
            estrategias_ativas.append('Repetição')
        
        # 3. Vizinhos do último (setor físico)
        for n in analise['vizinhos_ultimo'][:3]:
            base.add(n)
        estrategias_ativas.append('Vizinhos')
        
        # 4. Lucky numbers
        for n in analise['lucky_quentes'][:3]:
            base.add(n)
        if analise['lucky_quentes']:
            estrategias_ativas.append('Lucky')
        
        # 5. Último número
        if analise['ultimo'] is not None:
            base.add(analise['ultimo'])
        
        # 6. Números do setor dominante
        for n in analise['numeros_setor'][:3]:
            base.add(n)
        
        # 7. Filtro por cor dominante
        if analise['cor_dominante'] == 'Vermelho':
            base = {n for n in base if n in self.analisador.vermelhos or n == 0}
            estrategias_ativas.append('Cor')
        elif analise['cor_dominante'] == 'Preto':
            base = {n for n in base if n in self.analisador.pretos or n == 0}
            estrategias_ativas.append('Cor')
        
        # 8. Filtro por altura
        if analise['tendencia_altura'] == 'Alto':
            numeros_altos = {n for n in base if n >= 19}
            if len(numeros_altos) >= 3:
                base = numeros_altos
                estrategias_ativas.append('Alto')
        else:
            numeros_baixos = {n for n in base if n <= 18}
            if len(numeros_baixos) >= 3:
                base = numeros_baixos
                estrategias_ativas.append('Baixo')
        
        # Ordena por prioridade: repetidos > quentes > lucky > vizinhos
        prioridade = []
        for n in analise['repeticoes']:
            if n in base and n not in prioridade:
                prioridade.append(n)
        for n in analise['quentes']:
            if n in base and n not in prioridade:
                prioridade.append(n)
        for n in analise['lucky_quentes']:
            if n in base and n not in prioridade:
                prioridade.append(n)
        for n in analise['vizinhos_ultimo']:
            if n in base and n not in prioridade:
                prioridade.append(n)
        for n in base:
            if n not in prioridade:
                prioridade.append(n)
        
        # Limita ao máximo
        base_list = prioridade[:top_n]
        
        # Se menos de 3, completa com quentes
        if len(base_list) < 3:
            for n in analise['quentes']:
                if n not in base_list:
                    base_list.append(n)
                    if len(base_list) >= 3:
                        break
        
        # 🎯 CONFIANÇA
        forca = analise['forca_sinal']
        
        # Performance recente ajusta força
        taxa_recente = self.get_taxa_recente(5)
        if taxa_recente >= 0.4:
            forca += 15
        elif taxa_recente <= 0.1:
            forca -= 15
            if modo_conservador:
                return None
        
        if forca >= 60:
            confianca = "Alta"
        elif forca >= 35:
            confianca = "Média"
        else:
            confianca = "Baixa"
            if modo_conservador and len(base_list) > 3:
                base_list = base_list[:3]
        
        # Gatilho descritivo
        partes = [f"u={analise['ultimo']}"]
        if analise['repeticoes']:
            partes.append(f"rep={analise['repeticoes']}")
        if analise['cor_dominante'] != 'Verde':
            partes.append(analise['cor_dominante'])
        partes.append(analise['tendencia_altura'])
        
        return {
            'nome': 'Bot V3 Versátil',
            'numeros_apostar': sorted(base_list),
            'gatilho': ", ".join(partes),
            'forca_real': forca,
            'confianca': confianca,
            'estrategias_ativas': estrategias_ativas,
            'analise': analise
        }
    
    def get_analise_completa(self):
        if len(self.historico) < 5:
            return "📊 Aguardando dados (mínimo 5)..."
        
        lucky_recentes = []
        for sub in self.lucky[-10:]:
            lucky_recentes.extend(sub)
        
        analise = self.analisador.analisar(list(self.historico), lucky_recentes)
        
        if not analise:
            return "📊 Analisando..."
        
        taxa = self.get_taxa_acerto()
        total = self.get_total_tentativas()
        
        txt = "🎯 ANÁLISE VERSÁTIL\n" + "="*35 + "\n\n"
        txt += f"🎲 Último: {analise['ultimo']}\n"
        txt += f"📊 Janela: {self.analisador.janela_analise} giros\n\n"
        
        txt += f"🔥 Quentes: {analise['quentes'][:5]}\n"
        txt += f"🔁 Repetições: {analise['repeticoes']}\n"
        txt += f"📍 Vizinhos: {analise['vizinhos_ultimo'][:5]}\n"
        txt += f"🍀 Lucky: {analise['lucky_quentes'][:5]}\n\n"
        
        txt += f"📊 Dúzia: {analise['melhor_duzia']} | Coluna: {analise['melhor_coluna']}\n"
        txt += f"🎨 Cor: {analise['cor_dominante']}\n"
        txt += f"📏 Altura: {analise['tendencia_altura']}\n"
        txt += f"🔢 Paridade: {analise['tendencia_paridade']}\n"
        txt += f"⚡ Força: {analise['forca_sinal']}%\n"
        
        if total > 0:
            txt += f"\n📈 Perf: {taxa:.0%} ({self.performance['acertos']}/{total})\n"
        
        return txt
    
    def zerar(self):
        self.historico = []
        self.lucky = []
        self.lucky_mult = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}


# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaBot:
    def __init__(self):
        self.bot = RoletaBotV3(janela_analise=20)
        self.historico_numeros = deque(maxlen=200)
        self.historico_lucky = deque(maxlen=100)
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
            lucky_mults = numero_data.get('luckyMultipliers', {})
            mult = lucky_mults.get(numero_real) if numero_real in lucky else None
        else:
            numero_real = numero_data
            lucky = []
            lucky_mults = {}
            mult = None
        
        self.bot.atualizar(numero_real, lucky, lucky_mults)
        self.historico_numeros.append(numero_real)
        self.historico_lucky.append(lucky)
        self.rodadas_sem_entrada += 1
        
        # Verifica resultado anterior
        if self.previsao_ativa:
            acerto = numero_real in self.previsao_ativa.get('numeros_apostar', [])
            self.bot.atualizar_resultado(acerto)
            
            if acerto:
                self.acertos += 1
            else:
                self.erros += 1
            
            enviar_resultado_auto(numero_real, acerto, mult)
            
            self.historico_desempenho.append({
                'numero': numero_real,
                'acerto': acerto,
                'multiplicador': mult,
                'forca': self.previsao_ativa.get('forca_real', 0),
                'confianca': self.previsao_ativa.get('confianca', 'Média')
            })
            
            self.previsao_ativa = None
            self.ultima_entrada_rodada = len(self.historico_numeros)
            self.rodadas_sem_entrada = 0
        
        if self.estrategia_ativa_manual:
            return
        
        intervalo = st.session_state.get('intervalo_minimo_entradas', 0)
        if len(self.historico_numeros) - self.ultima_entrada_rodada < intervalo:
            return
        
        if len(self.historico_numeros) >= 5:
            top_n = st.session_state.get('top_n_apostas', 5)
            forca_minima = st.session_state.get('forca_minima_sinal', 20)
            conservador = st.session_state.get('modo_conservador', True)
            
            nova = self.bot.sugerir_aposta(top_n, forca_minima, conservador)
            
            if nova and nova['forca_real'] >= forca_minima:
                self.previsao_ativa = nova
                enviar_previsao_auto(nova)
    
    def zerar_estatisticas(self):
        self.acertos = 0
        self.erros = 0
        self.historico_desempenho = []
        self.historico_numeros.clear()
        self.historico_lucky.clear()
        self.rodadas_sem_entrada = 0
        self.ultima_entrada_rodada = -10
        self.bot.zerar()
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

def exportar_historico(historico, formato='json'):
    if formato == 'json':
        return json.dumps(historico, indent=2, ensure_ascii=False)
    else:
        linhas = ["numero,timestamp,multiplicador"]
        for item in historico:
            if isinstance(item, dict):
                n = item.get('number', '')
                ts = item.get('timestamp', '')
                mult = item.get('luckyMultipliers', {}).get(n, '')
                linhas.append(f"{n},{ts},{mult}")
            else:
                linhas.append(f"{item},,")
        return "\n".join(linhas)


# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🤖 Bot V3 — Analisador Versátil", layout="centered")
st.title("🤖 Bot V3 — Analisador Versátil (Janela Deslizante)")

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()

defaults = {
    'top_n_apostas': 5, 'forca_minima_sinal': 20,
    'intervalo_minimo_entradas': 0, 'modo_automatico': True,
    'modo_conservador': True, 'janela_analise': 20
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

carregar_sessao()

if "historico" not in st.session_state:
    if os.path.exists(HISTORICO_PATH):
        try:
            with open(HISTORICO_PATH, "r") as f:
                st.session_state.historico = json.load(f)
        except:
            st.session_state.historico = []
    else:
        st.session_state.historico = []

if "telegram_token" not in st.session_state:
    st.session_state.telegram_token = ""
if "telegram_chat_id" not in st.session_state:
    st.session_state.telegram_chat_id = ""

# Sidebar
st.sidebar.title("⚙️ Configurações")

with st.sidebar.expander("🤖 Bot V3", expanded=True):
    st.session_state.janela_analise = st.slider("🪟 Janela de Análise (giros)", 5, 50, st.session_state.janela_analise, 5,
        help="Quantos giros recentes analisar. Menor = mais reativo, Maior = mais estável")
    st.session_state.modo_conservador = st.checkbox("🛡️ Modo Conservador", value=st.session_state.modo_conservador)
    st.session_state.top_n_apostas = st.slider("📊 Números por aposta", 3, 8, st.session_state.top_n_apostas)
    st.session_state.forca_minima_sinal = st.slider("⚡ Força mínima", 10, 50, st.session_state.forca_minima_sinal, 5)
    st.session_state.intervalo_minimo_entradas = st.slider("⏱️ Intervalo", 0, 3, st.session_state.intervalo_minimo_entradas)

st.session_state.modo_automatico = st.sidebar.checkbox("🔄 Automático", value=st.session_state.modo_automatico)
if st.sidebar.button("Atualizar"):
    st.session_state.sistema.estrategia_ativa_manual = not st.session_state.modo_automatico
    st.rerun()

with st.sidebar.expander("🧠 Análise Versátil", expanded=True):
    st.text(st.session_state.sistema.bot.get_analise_completa())

with st.sidebar.expander("💾 Geral", expanded=False):
    if st.button("💾 Salvar", use_container_width=True):
        salvar_sessao()
        st.success("✅")
    if st.button("🗑️ Zerar", use_container_width=True):
        if st.checkbox("Confirmar"):
            st.session_state.sistema.zerar_estatisticas()
            st.rerun()

with st.sidebar.expander("🔔 Telegram", expanded=False):
    st.session_state.telegram_token = st.text_input("Token:", value=st.session_state.telegram_token, type="password")
    st.session_state.telegram_chat_id = st.text_input("Chat ID:", value=st.session_state.telegram_chat_id)
    if st.button("Salvar"):
        salvar_sessao()
        st.success("✅")

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
    if taxa >= 30:
        st.success(f"🎯 Taxa: {taxa:.1f}%")
    elif taxa >= 20:
        st.warning(f"🎯 Taxa: {taxa:.1f}%")
    else:
        st.error(f"🎯 Taxa: {taxa:.1f}%")

# Previsão
st.subheader("🎯 Previsão Ativa")
sis = st.session_state.sistema

if sis.estrategia_ativa_manual:
    st.warning("⚠️ MANUAL")
elif sis.previsao_ativa:
    p = sis.previsao_ativa
    f = p.get('forca_real', 0)
    c = p.get('confianca', 'Média')
    estrategias = p.get('estrategias_ativas', [])
    
    if c == "Alta":
        st.success(f"🟢 **CONFIANÇA ALTA** - {p['gatilho']}")
    elif c == "Média":
        st.warning(f"🟡 **CONFIANÇA MÉDIA** - {p['gatilho']}")
    else:
        st.error(f"🔴 **CONFIANÇA BAIXA** - {p['gatilho']}")
    
    if estrategias:
        st.caption(f"🎯 Estratégias: {', '.join(estrategias)}")
    
    st.write(f"**🔢 {len(p['numeros_apostar'])} números:**")
    nums = sorted(p['numeros_apostar'])
    cols = st.columns(len(nums))
    for i, num in enumerate(nums):
        cols[i].write(f"**{num}**")
else:
    st.info(f"🎲 Aguardando... ({status['rodadas_sem_entrada']} rodadas)")

# Performance
st.subheader("📈 Performance")
taxa_bot = sis.bot.get_taxa_acerto()
total_bot = sis.bot.get_total_tentativas()
if total_bot > 0:
    emoji = "🟢" if taxa_bot >= 0.30 else "🟡" if taxa_bot >= 0.20 else "🔴"
    st.write(f"{emoji} **Bot**: {taxa_bot:.0%} ({sis.bot.performance['acertos']}/{total_bot})")

# Histórico
if sis.historico_desempenho:
    st.write("**🔍 Últimas:**")
    for r in sis.historico_desempenho[-5:]:
        e = "🎉" if r['acerto'] else "❌"
        m = f" ⚡{r['multiplicador']}x" if r.get('multiplicador') and r['acerto'] else ""
        st.write(f"{e} ({r.get('forca',0)}%): {r['numero']}{m}")

# Download
st.subheader("📥 Download")
st.metric("📊 Registros", len(st.session_state.historico))
col_d1, col_d2 = st.columns(2)
with col_d1:
    if st.button("📥 JSON", use_container_width=True):
        st.download_button("⬇️ Baixar", exportar_historico(st.session_state.historico, 'json'),
                          f"historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "application/json")
with col_d2:
    if st.button("📥 CSV", use_container_width=True):
        st.download_button("⬇️ Baixar", exportar_historico(st.session_state.historico, 'csv'),
                          f"historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv")

salvar_sessao()
