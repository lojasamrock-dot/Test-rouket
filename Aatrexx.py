import streamlit as st
import json
import os
import requests
import logging
from collections import Counter, deque, defaultdict
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
        if 'sistema' not in st.session_state or st.session_state.sistema is None:
            return False
        
        performance_data = {
            'acertos': st.session_state.sistema.bot.performance['acertos'],
            'erros': st.session_state.sistema.bot.performance['erros'],
            'historico': st.session_state.sistema.bot.performance['historico']
        }
        with open(PERFORMANCE_PATH, 'w') as f:
            json.dump(performance_data, f)
        
        session_data = {
            'historico': st.session_state.get('historico', []),
            'telegram_token': st.session_state.get('telegram_token', ''),
            'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
            'sistema_acertos': st.session_state.sistema.acertos,
            'sistema_erros': st.session_state.sistema.erros,
            'sistema_historico_desempenho': st.session_state.sistema.historico_desempenho,
            'historico_numeros': list(st.session_state.sistema.historico_numeros),
            'historico_lucky': list(st.session_state.sistema.historico_lucky),
            'estrategia_ativa_manual': st.session_state.sistema.estrategia_ativa_manual,
            'modo_automatico': st.session_state.get('modo_automatico', True),
            'top_n_apostas': st.session_state.get('top_n_apostas', 12),
            'intervalo_minimo_entradas': st.session_state.get('intervalo_minimo_entradas', 0),
            'repetir_entrada': st.session_state.get('repetir_entrada', True),
            'usar_mineracao': st.session_state.get('usar_mineracao', True),
            'usar_leque': st.session_state.get('usar_leque', True),
            'usar_giro': st.session_state.get('usar_giro', True),
            'janela_leque': st.session_state.get('janela_leque', 20)
        }
        
        with open(SESSION_DATA_PATH, 'wb') as f:
            pickle.dump(session_data, f)
        
        return True
    except Exception as e:
        logging.error(f"❌ Erro ao salvar: {e}")
        return False

def carregar_dados_persistidos():
    try:
        if os.path.exists(SESSION_DATA_PATH):
            with open(SESSION_DATA_PATH, 'rb') as f:
                return pickle.load(f)
    except:
        pass
    return None

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
        forca = previsao.get('forca_real', 0)
        confianca = previsao.get('confianca', 'Média')
        estrategias = previsao.get('estrategias_ativas', [])
        motor = previsao.get('motor', '')
        repeticao = previsao.get('repeticao', False)
        rep_restantes = previsao.get('repeticoes_restantes', 0)
        
        emoji = "🔄" if repeticao else "🔥" if forca >= 60 else "🎯" if forca >= 40 else "📊"
        
        msg = f"{emoji} **ENTRADA** - Força: {forca}%\n"
        if repeticao:
            msg += f"🔄 REPETINDO! ({rep_restantes} giros)\n"
        else:
            msg += f"🤖 Motor: {motor}\n"
            if estrategias:
                msg += f"🎯 {', '.join(estrategias[:4])}\n"
        msg += f"🔢 {len(numeros)} números: {numeros}"
        
        st.toast(f"🎯 {'Repetindo' if repeticao else 'Entrada'} - {forca}%", icon=emoji)
        st.success(f"🔔 {msg}")
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"🔔 {'🔄 REPETINDO' if repeticao else '🎯 ENTRADA'} {forca}%\n" + " ".join(map(str, numeros)))
        
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
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"📢 {msg}")
        
        salvar_sessao()
    except:
        pass

def enviar_telegram(mensagem):
    try:
        token = st.session_state.get('telegram_token', '')
        chat_id = st.session_state.get('telegram_chat_id', '')
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
# ROLETA BASE
# =============================
class RoletaBase:
    def __init__(self):
        self.race = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        self.vermelhos = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        self.pretos = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
    
    def get_vizinhos(self, numero, raio=2):
        if numero not in self.race:
            return []
        idx = self.race.index(numero)
        return [self.race[(idx + i) % 37] for i in range(-raio, raio + 1)]
    
    def get_setor(self, numero):
        if numero == 0:
            return 0
        return (numero - 1) // 12 + 1
    
    def get_coluna(self, numero):
        if numero == 0:
            return 0
        return (numero - 1) % 3 + 1


# =============================
# ESTRATÉGIA: MINERAÇÃO (Markov + Lucky Cross)
# =============================
class EstrategiaMineracao:
    def __init__(self):
        self.transicoes = defaultdict(list)
    
    def atualizar(self, historico):
        self.transicoes.clear()
        for i in range(len(historico) - 1):
            self.transicoes[historico[i]].append(historico[i + 1])
    
    def analisar(self, historico, historico_lucky):
        if len(historico) < 10:
            return None
        
        self.atualizar(historico)
        ultimo = historico[-1]
        
        base = set()
        forca = 0
        estrategias = []
        
        # Markov
        seguidores = self.transicoes.get(ultimo, [])
        if seguidores:
            top = [n for n, _ in Counter(seguidores).most_common(5)]
            base.update(top)
            forca += 30
            estrategias.append("Markov")
        
        # Lucky Cross
        if len(historico_lucky) >= 2:
            acertos = sum(1 for i in range(min(len(historico)-1, len(historico_lucky)-1))
                         if historico[i+1] in historico_lucky[i])
            total = min(len(historico)-1, len(historico_lucky)-1)
            taxa = acertos / total * 100 if total > 0 else 0
            if taxa > 15:
                forca += 25
                estrategias.append(f"Lucky Cross {taxa:.0f}%")
        
        if forca == 0:
            return None
        
        return {
            'base': base,
            'forca': min(100, forca),
            'estrategias': estrategias
        }


# =============================
# ESTRATÉGIA: LEQUE DINÂMICO
# =============================
class EstrategiaLeque:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, historico, janela=20):
        if len(historico) < 8:
            return None
        
        recentes = historico[-janela:]
        ultimo = recentes[-1]
        
        # Leque baseado no calor da região
        macro_regiao = self.roleta.get_vizinhos(ultimo, 5)
        acertos = sum(1 for n in recentes if n in macro_regiao)
        
        if acertos >= 5:
            leque = 3
            status = "🔥 QUENTE"
            forca = 65
        elif acertos >= 2:
            leque = 2
            status = "🟡 MORNO"
            forca = 45
        else:
            leque = 1
            status = "🧊 FRIO"
            forca = 30
        
        alvos = self.roleta.get_vizinhos(ultimo, leque)
        
        return {
            'base': set(alvos),
            'forca': forca,
            'estrategias': [f"Leque {leque} vizinhos"],
            'status': status
        }


# =============================
# ESTRATÉGIA: ANÁLISE POR GIRO (SEMPRE ATIVA)
# =============================
class EstrategiaPorGiro:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, historico, lucky_recentes):
        if len(historico) < 3:
            return None
        
        hist = historico
        ultimo = hist[-1]
        penultimo = hist[-2] if len(hist) >= 2 else None
        ultimos_5 = hist[-5:] if len(hist) >= 5 else hist
        ultimos_10 = hist[-10:] if len(hist) >= 10 else hist
        ultimos_20 = hist[-20:] if len(hist) >= 20 else hist
        
        # Repetição
        repetiu = (ultimo == penultimo) if penultimo else False
        repeticoes_5 = [n for n in ultimos_5 if ultimos_5.count(n) >= 2]
        
        # Frequências
        freq_5 = Counter(ultimos_5)
        freq_10 = Counter(ultimos_10)
        freq_20 = Counter(ultimos_20)
        
        quentes_5 = [n for n, _ in freq_5.most_common(4)]
        quentes_10 = [n for n, _ in freq_10.most_common(6)]
        quentes_20 = [n for n, _ in freq_20.most_common(8)]
        
        # Lucky com peso
        lucky_pesos = Counter()
        if lucky_recentes:
            for n in lucky_recentes:
                lucky_pesos[n] += 1
        
        top_lucky = [n for n, _ in lucky_pesos.most_common(5)]
        
        # Vizinhos
        vizinhos_1 = self.roleta.get_vizinhos(ultimo, 1)
        vizinhos_2 = self.roleta.get_vizinhos(ultimo, 2)
        
        # Setor e cor
        setores_10 = Counter([self.roleta.get_setor(n) for n in ultimos_10 if n != 0])
        setor_dom = setores_10.most_common(1)[0][0] if setores_10 else None
        
        vermelhos_10 = sum(1 for n in ultimos_10 if n in self.roleta.vermelhos)
        pretos_10 = sum(1 for n in ultimos_10 if n in self.roleta.pretos)
        cor_dom = 'Vermelho' if vermelhos_10 > pretos_10 else 'Preto'
        
        # 🎯 CONSTRUÇÃO DA BASE (10-12 NÚMEROS)
        base = set()
        estrategias = []
        forca = 25
        
        # 1. REPETIÇÃO (MÁXIMA PRIORIDADE)
        if repetiu:
            base.add(ultimo)
            forca += 30
            estrategias.append(f"Repetiu {ultimo}")
        
        for n in repeticoes_5:
            base.add(n)
            forca += 10
        
        # 2. LUCKY NUMBERS
        for n in top_lucky[:4]:
            base.add(n)
        if top_lucky:
            forca += 15
            estrategias.append("Lucky")
        
        # 3. QUENTES (múltiplas janelas)
        for n in quentes_5[:3]:
            base.add(n)
        for n in quentes_10[:4]:
            base.add(n)
        for n in quentes_20[:3]:
            base.add(n)
        estrategias.append("Quentes")
        
        # 4. VIZINHOS
        for n in vizinhos_1:
            base.add(n)
        for n in vizinhos_2[:3]:
            base.add(n)
        estrategias.append("Vizinhos")
        
        # 5. ÚLTIMO NÚMERO
        base.add(ultimo)
        
        # 6. NÚMEROS DO SETOR DOMINANTE
        if setor_dom:
            inicio = (setor_dom - 1) * 12 + 1
            fim = setor_dom * 12
            numeros_setor = list(range(inicio, fim + 1))
            # Pega os mais frequentes do setor
            freq_setor = Counter([n for n in ultimos_20 if n in numeros_setor])
            top_setor = [n for n, _ in freq_setor.most_common(5)]
            for n in top_setor[:3]:
                base.add(n)
            forca += 10
            estrategias.append(f"Setor {setor_dom}")
        
        # 7. FILTRO POR COR (expande o leque)
        if cor_dom == 'Vermelho':
            numeros_cor = [n for n in range(37) if n in self.roleta.vermelhos or n == 0]
        else:
            numeros_cor = [n for n in range(37) if n in self.roleta.pretos or n == 0]
        
        # Adiciona mais números da cor dominante se precisar
        freq_cor = Counter([n for n in ultimos_20 if n in numeros_cor])
        top_cor = [n for n, _ in freq_cor.most_common(5)]
        for n in top_cor[:3]:
            base.add(n)
        
        # Ordena por score combinado
        scores = {}
        for n in base:
            score = 0
            score += freq_5.get(n, 0) * 3
            score += freq_10.get(n, 0) * 2
            score += freq_20.get(n, 0) * 1
            if n in top_lucky:
                score += lucky_pesos.get(n, 0) * 2
            if n in repeticoes_5:
                score += 5
            if n == ultimo:
                score += 4
            scores[n] = score
        
        # Ordena por score
        ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        base_list = [n for n, _ in ordenados[:12]]
        
        if len(base_list) < 8:
            for n in quentes_20:
                if n not in base_list:
                    base_list.append(n)
                    if len(base_list) >= 8:
                        break
        
        forca = min(100, max(20, int(forca)))
        
        return {
            'base': set(base_list),
            'forca': forca,
            'estrategias': estrategias,
            'repetiu': repetiu
        }


# =============================
# BOT UNIFICADO (SEM SNIPER)
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        self.mineracao = EstrategiaMineracao()
        self.leque = EstrategiaLeque(self.roleta)
        self.giro = EstrategiaPorGiro(self.roleta)
        
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
    
    def get_total_tentativas(self):
        return self.performance['acertos'] + self.performance['erros']
    
    def analisar_e_prever(self, top_n=12, motores_ativos=None):
        if len(self.historico) < 3:
            return None
        
        if motores_ativos is None:
            motores_ativos = {'mineracao': True, 'leque': True, 'giro': True}
        
        lucky_recentes = []
        for sub in self.lucky[-10:]:
            lucky_recentes.extend(sub)
        
        resultados = []
        
        # Motor 1: Mineração
        if motores_ativos.get('mineracao', True) and len(self.historico) >= 10:
            r = self.mineracao.analisar(list(self.historico), list(self.lucky))
            if r:
                resultados.append(('Mineração', r))
        
        # Motor 2: Leque Dinâmico
        if motores_ativos.get('leque', True):
            janela = st.session_state.get('janela_leque', 20)
            r = self.leque.analisar(list(self.historico), janela)
            if r:
                resultados.append(('Leque', r))
        
        # Motor 3: Análise por Giro (SEMPRE)
        if motores_ativos.get('giro', True):
            r = self.giro.analisar(list(self.historico), lucky_recentes)
            if r:
                resultados.append(('Análise Giro', r))
        
        if not resultados:
            return None
        
        # Combina resultados
        base_final = set()
        todas_estrategias = []
        forca_total = 0
        motor_principal = ""
        maior_forca = 0
        
        for motor, r in resultados:
            base_final.update(r['base'])
            todas_estrategias.extend(r['estrategias'])
            forca_total += r['forca']
            if r['forca'] > maior_forca:
                maior_forca = r['forca']
                motor_principal = motor
        
        forca_media = forca_total / len(resultados) if resultados else 25
        
        # Performance recente
        if len(self.performance['historico']) >= 5:
            taxa_recente = sum(self.performance['historico'][-5:]) / 5
            if taxa_recente >= 0.4:
                forca_media += 10
            elif taxa_recente <= 0.1:
                forca_media -= 10
        
        forca_media = min(100, max(20, int(forca_media)))
        
        # Confiança
        if forca_media >= 60:
            confianca = "Alta"
        elif forca_media >= 40:
            confianca = "Média"
        else:
            confianca = "Baixa"
        
        # Ordena por frequência nos resultados
        freq_base = Counter()
        for _, r in resultados:
            for n in r['base']:
                freq_base[n] += 1
        
        prioridade = [n for n, _ in freq_base.most_common()]
        base_list = prioridade[:top_n]
        
        # Completa até 10-12 se necessário
        if len(base_list) < 10:
            for n in prioridade:
                if n not in base_list:
                    base_list.append(n)
                    if len(base_list) >= 10:
                        break
        
        gatilho = f"u={self.historico[-1]}"
        if len(self.historico) >= 2 and self.historico[-1] == self.historico[-2]:
            gatilho = f"REPETIU {self.historico[-1]}!"
        
        return {
            'nome': 'Bot Unificado',
            'numeros_apostar': sorted(base_list[:top_n]),
            'gatilho': gatilho,
            'forca_real': forca_media,
            'confianca': confianca,
            'motor': motor_principal,
            'estrategias_ativas': list(set(todas_estrategias))[:5],
            'qtd_motores': len(resultados),
            'repeticao': False,
            'repeticoes_restantes': 0
        }
    
    def get_analise_completa(self):
        if len(self.historico) < 3:
            return "📊 Aguardando dados..."
        
        hist = self.historico
        ultimo = hist[-1]
        ultimos_10 = hist[-10:] if len(hist) >= 10 else hist
        
        freq_10 = Counter(ultimos_10)
        quentes = [n for n, _ in freq_10.most_common(8)]
        
        lucky_flat = []
        for sub in self.lucky[-5:]:
            lucky_flat.extend(sub)
        top_lucky = [n for n, _ in Counter(lucky_flat).most_common(5)]
        
        taxa = self.get_taxa_acerto()
        total = self.get_total_tentativas()
        
        txt = "🎯 BOT UNIFICADO (10-12 números)\n" + "="*40 + "\n\n"
        txt += f"🎲 Último: {ultimo}\n"
        txt += f"📊 10 últimos: {hist[-10:]}\n\n"
        
        txt += f"🔥 Quentes: {quentes}\n"
        txt += f"🍀 Lucky: {top_lucky}\n"
        
        txt += f"\n🤖 MOTORES:\n"
        txt += f"  🔬 Mineração: {'✅' if st.session_state.get('usar_mineracao', True) else '❌'}\n"
        txt += f"  🪭 Leque: {'✅' if st.session_state.get('usar_leque', True) else '❌'}\n"
        txt += f"  🔄 Giro: {'✅' if st.session_state.get('usar_giro', True) else '❌'}\n"
        
        if st.session_state.get('repetir_entrada', True):
            txt += f"\n🔄 Repetição após erro: ATIVADA\n"
        
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
        self.bot = RoletaBotUnificado()
        self.historico_numeros = deque(maxlen=200)
        self.historico_lucky = deque(maxlen=100)
        self.previsao_ativa = None
        self.historico_desempenho = []
        self.acertos = 0
        self.erros = 0
        self.rodadas_sem_entrada = 0
        self.ultima_entrada_rodada = -10
        self.estrategia_ativa_manual = False
        
        self.repeticoes_restantes = 0
        self.ultima_entrada_numeros = []
        self.ultima_entrada_forca = 0
        
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
        
        if self.previsao_ativa:
            acerto = numero_real in self.previsao_ativa.get('numeros_apostar', [])
            self.bot.atualizar_resultado(acerto)
            
            if acerto:
                self.acertos += 1
                self.repeticoes_restantes = 0
                self.ultima_entrada_numeros = []
            else:
                self.erros += 1
                if st.session_state.get('repetir_entrada', True) and not self.previsao_ativa.get('repeticao', False):
                    self.repeticoes_restantes = 2
                    self.ultima_entrada_numeros = self.previsao_ativa.get('numeros_apostar', [])
                    self.ultima_entrada_forca = self.previsao_ativa.get('forca_real', 0)
            
            enviar_resultado_auto(numero_real, acerto, mult)
            
            self.historico_desempenho.append({
                'numero': numero_real,
                'acerto': acerto,
                'multiplicador': mult,
                'forca': self.previsao_ativa.get('forca_real', 0)
            })
            
            self.previsao_ativa = None
            self.ultima_entrada_rodada = len(self.historico_numeros)
            self.rodadas_sem_entrada = 0
        
        if self.estrategia_ativa_manual:
            return
        
        if len(self.historico_numeros) >= 3:
            intervalo = st.session_state.get('intervalo_minimo_entradas', 0)
            
            if len(self.historico_numeros) - self.ultima_entrada_rodada >= intervalo:
                
                if self.repeticoes_restantes > 0 and self.ultima_entrada_numeros:
                    self.repeticoes_restantes -= 1
                    
                    previsao_repetida = {
                        'nome': 'Bot Unificado',
                        'numeros_apostar': sorted(self.ultima_entrada_numeros),
                        'gatilho': 'REPETINDO ENTRADA ANTERIOR',
                        'forca_real': self.ultima_entrada_forca,
                        'confianca': 'Repetição',
                        'motor': 'Repetição',
                        'estrategias_ativas': ['Repetição pós-erro'],
                        'qtd_motores': 1,
                        'repeticao': True,
                        'repeticoes_restantes': self.repeticoes_restantes
                    }
                    
                    self.previsao_ativa = previsao_repetida
                    enviar_previsao_auto(previsao_repetida)
                else:
                    top_n = st.session_state.get('top_n_apostas', 12)
                    
                    motores_ativos = {
                        'mineracao': st.session_state.get('usar_mineracao', True),
                        'leque': st.session_state.get('usar_leque', True),
                        'giro': st.session_state.get('usar_giro', True)
                    }
                    
                    nova = self.bot.analisar_e_prever(top_n, motores_ativos)
                    
                    if nova is not None:
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
        self.repeticoes_restantes = 0
        self.ultima_entrada_numeros = []
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
st.set_page_config(page_title="🎯 Bot Unificado — 10-12 Números", layout="centered")
st.title("🎯 Bot Unificado — Leque Amplo (10-12 números)")

if "sistema" not in st.session_state or st.session_state.sistema is None:
    st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    if not st.session_state.get('historico'):
        st.session_state.historico = dados.get('historico', [])
    
    sis = st.session_state.sistema
    sis.acertos = dados.get('sistema_acertos', 0)
    sis.erros = dados.get('sistema_erros', 0)
    sis.historico_desempenho = dados.get('sistema_historico_desempenho', [])
    sis.estrategia_ativa_manual = dados.get('estrategia_ativa_manual', False)
    sis.repeticoes_restantes = dados.get('repeticoes_restantes', 0)
    sis.ultima_entrada_numeros = dados.get('ultima_entrada_numeros', [])
    
    for num in dados.get('historico_numeros', []):
        sis.historico_numeros.append(num)
    for lucky in dados.get('historico_lucky', []):
        sis.historico_lucky.append(lucky)
    
    for num, lucky in zip(dados.get('historico_numeros', []), dados.get('historico_lucky', [])):
        sis.bot.historico.append(num)
        sis.bot.lucky.append(lucky)
    
    if os.path.exists(PERFORMANCE_PATH):
        try:
            with open(PERFORMANCE_PATH, 'r') as f:
                perf = json.load(f)
                sis.bot.performance = {
                    'acertos': perf.get('acertos', 0),
                    'erros': perf.get('erros', 0),
                    'historico': perf.get('historico', [])
                }
        except:
            pass

defaults = {
    'modo_automatico': True, 'top_n_apostas': 12,
    'intervalo_minimo_entradas': 0, 'repetir_entrada': True,
    'usar_mineracao': True, 'usar_leque': True, 'usar_giro': True,
    'janela_leque': 20
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

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

with st.sidebar.expander("🤖 Motores Ativos", expanded=True):
    st.session_state.usar_mineracao = st.checkbox("🔬 Mineração (Markov + Lucky Cross)", value=st.session_state.usar_mineracao)
    st.session_state.usar_leque = st.checkbox("🪭 Leque Dinâmico", value=st.session_state.usar_leque)
    st.session_state.usar_giro = st.checkbox("🔄 Análise por Giro (SEMPRE)", value=st.session_state.usar_giro)
    
    ativos = sum([st.session_state.usar_mineracao, st.session_state.usar_leque, st.session_state.usar_giro])
    st.caption(f"📊 {ativos}/3 motores ativos")

with st.sidebar.expander("⚙️ Ajustes", expanded=True):
    st.session_state.top_n_apostas = st.slider("📊 Números por aposta", 8, 15, st.session_state.top_n_apostas)
    st.session_state.intervalo_minimo_entradas = st.slider("⏱️ Intervalo", 0, 2, st.session_state.intervalo_minimo_entradas)
    st.session_state.repetir_entrada = st.checkbox("🔄 Repetir após erro (2 giros)", value=st.session_state.repetir_entrada)
    st.session_state.janela_leque = st.slider("🪭 Janela do Leque", 10, 50, st.session_state.janela_leque, 5)

st.session_state.modo_automatico = st.sidebar.checkbox("🔄 Automático", value=st.session_state.modo_automatico)
if st.sidebar.button("Atualizar"):
    st.session_state.sistema.estrategia_ativa_manual = not st.session_state.modo_automatico
    st.rerun()

with st.sidebar.expander("🧠 Análise", expanded=True):
    st.text(st.session_state.sistema.bot.get_analise_completa())

with st.sidebar.expander("💾 Geral", expanded=False):
    if st.button("💾 Salvar", use_container_width=True):
        salvar_resultado_em_arquivo(st.session_state.historico)
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
c1, c2 = st.columns([3, 1])
with c1:
    entrada = st.text_input("Números (0-36):")
with c2:
    if st.button("Adicionar", use_container_width=True) and entrada:
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
    if taxa >= 35:
        st.success(f"🎯 Taxa: {taxa:.1f}%")
    elif taxa >= 25:
        st.warning(f"🎯 Taxa: {taxa:.1f}%")
    else:
        st.error(f"🎯 Taxa: {taxa:.1f}%")

if st.session_state.sistema.repeticoes_restantes > 0:
    st.warning(f"🔄 Repetindo! Faltam {st.session_state.sistema.repeticoes_restantes} giros")

# Previsão
st.subheader("🎯 Previsão Ativa")
sis = st.session_state.sistema

if sis.estrategia_ativa_manual:
    st.warning("⚠️ MANUAL")
elif sis.previsao_ativa:
    p = sis.previsao_ativa
    f = p.get('forca_real', 0)
    c = p.get('confianca', 'Média')
    motor = p.get('motor', '')
    estrategias = p.get('estrategias_ativas', [])
    qtd = p.get('qtd_motores', 1)
    repeticao = p.get('repeticao', False)
    
    if repeticao:
        st.success(f"🔄 **REPETINDO!**")
    elif f >= 60:
        st.success(f"🔥 **FORÇA {f}%** - {c} ({qtd} motores)")
    elif f >= 40:
        st.warning(f"🎯 **FORÇA {f}%** - {c} ({qtd} motores)")
    else:
        st.info(f"📊 **FORÇA {f}%** - {c} ({qtd} motores)")
    
    st.caption(f"🤖 Motor: {motor}")
    if estrategias:
        st.caption(f"🎯 {', '.join(estrategias[:4])}")
    
    st.write(f"**🔢 {len(p['numeros_apostar'])} números:**")
    nums = sorted(p['numeros_apostar'])
    cols = st.columns(6)
    for i, num in enumerate(nums):
        cols[i % 6].write(f"**{num}**")
else:
    st.info("🎲 Aguardando próximo giro...")

# Performance
st.subheader("📈 Performance")
taxa_bot = sis.bot.get_taxa_acerto()
total_bot = sis.bot.get_total_tentativas()
if total_bot > 0:
    emoji = "🟢" if taxa_bot >= 0.35 else "🟡" if taxa_bot >= 0.25 else "🔴"
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
