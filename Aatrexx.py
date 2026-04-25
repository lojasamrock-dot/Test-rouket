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
            'top_n_apostas': st.session_state.get('top_n_apostas', 5),
            'intervalo_minimo_entradas': st.session_state.get('intervalo_minimo_entradas', 0),
            'usar_sniper': st.session_state.get('usar_sniper', True),
            'usar_mineracao': st.session_state.get('usar_mineracao', True),
            'usar_leque': st.session_state.get('usar_leque', True),
            'usar_giro': st.session_state.get('usar_giro', True),
            'janela_analise': st.session_state.get('janela_analise', 50),
            'janela_leque': st.session_state.get('janela_leque', 20),
            'forca_minima_sinal': st.session_state.get('forca_minima_sinal', 40),
            'repetir_entrada': st.session_state.get('repetir_entrada', True),
            'giros_espera_repeticao': st.session_state.sistema.giros_espera_repeticao,
            'giros_restantes_espera': st.session_state.sistema.giros_restantes_espera,
            'ultima_entrada_numeros': st.session_state.sistema.ultima_entrada_numeros,
            'ultima_entrada_forca': st.session_state.sistema.ultima_entrada_forca,
            'ultima_entrada_motor': st.session_state.sistema.ultima_entrada_motor
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
        estrategias = previsao.get('estrategias_ativas', [])
        confianca = previsao.get('confianca', 'Média')
        motor = previsao.get('motor', '')
        repeticao = previsao.get('repeticao', False)
        giros_esperados = previsao.get('giros_esperados', 0)
        
        emoji = "⏳" if repeticao else "🔥" if forca >= 60 else "🎯" if forca >= 40 else "📊"
        
        msg = f"{emoji} **ENTRADA** - Força: {forca}%\n"
        
        if repeticao:
            msg += f"⏳ REPETINDO ENTRADA ANTERIOR! (após espera de {giros_esperados} giros)\n"
        else:
            msg += f"📋 {previsao['gatilho']}\n"
            if motor:
                msg += f"🤖 Motor: {motor}\n"
            if estrategias:
                msg += f"🎯 {', '.join(estrategias[:3])}\n"
        
        msg += f"🔢 {len(numeros)} números: {numeros}"
        
        st.toast(f"{'⏳ Repetindo' if repeticao else '🎯 ' + motor} - {forca}%", icon=emoji)
        st.success(f"🔔 {msg}")
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"🔔 ENTRADA {'[REPETINDO]' if repeticao else ''} {forca}%\n" + " ".join(map(str, numeros)))
        
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
# ESTRATÉGIA 1: SNIPER
# =============================
class EstrategiaSniper:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, historico, lucky_recentes):
        if len(historico) < 15:
            return None
        
        recentes = historico[-15:]
        ultimo = recentes[-1]
        
        duzias = Counter([self.roleta.get_setor(n) for n in recentes if n != 0])
        colunas = Counter([self.roleta.get_coluna(n) for n in recentes if n != 0])
        
        melhor_duzia = duzias.most_common(1)[0][0] if duzias else None
        melhor_coluna = colunas.most_common(1)[0][0] if colunas else None
        
        roda_hits = []
        for n in recentes:
            roda_hits.extend(self.roleta.get_vizinhos(n, raio=1))
        zona_quente = Counter(roda_hits).most_common(1)[0][0] if roda_hits else None
        vizinhos_zona = self.roleta.get_vizinhos(zona_quente, raio=2) if zona_quente else []
        
        forca = 0
        estrategia = []
        base = set()
        gatilho = ""
        
        if melhor_duzia and melhor_coluna:
            if duzias[melhor_duzia] >= 7 and colunas[melhor_coluna] >= 6:
                forca += 60
                estrategia.append("Interseção D/C")
                d, c = melhor_duzia, melhor_coluna
                numeros_duzia = range((d-1)*12 + 1, d*12 + 1)
                numeros_coluna = range(c, 37, 3)
                base.update(set(numeros_duzia).intersection(set(numeros_coluna)))
                gatilho = f"Interseção D{d} x C{c}"
        
        if zona_quente and vizinhos_zona:
            hits_zona = sum(1 for n in recentes if n in vizinhos_zona)
            if hits_zona >= 5:
                forca += 50
                estrategia.append("Cluster Físico")
                base.update(vizinhos_zona)
                if not gatilho:
                    gatilho = f"Zona: {zona_quente}"
        
        if lucky_recentes:
            lucky_quentes = [n for n, _ in Counter(lucky_recentes).most_common(3)]
            if any(l in recentes for l in lucky_quentes):
                forca += 15
                estrategia.append("Raios")
        
        if forca == 0:
            return None
        
        return {
            'base': base,
            'forca': min(100, forca),
            'estrategias': estrategia,
            'gatilho': gatilho
        }


# =============================
# ESTRATÉGIA 2: MINERAÇÃO
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
        
        seguidores = self.transicoes.get(ultimo, [])
        if seguidores:
            top = [n for n, _ in Counter(seguidores).most_common(3)]
            base.update(top)
            forca += 30
            estrategias.append("Markov")
        
        if len(historico_lucky) >= 2:
            acertos = sum(1 for i in range(min(len(historico)-1, len(historico_lucky)-1))
                         if historico[i+1] in historico_lucky[i])
            total = min(len(historico)-1, len(historico_lucky)-1)
            taxa = acertos / total * 100 if total > 0 else 0
            if taxa > 18:
                forca += 35
                estrategias.append(f"Lucky Cross {taxa:.0f}%")
        
        if forca == 0:
            return None
        
        return {
            'base': base,
            'forca': min(100, forca),
            'estrategias': estrategias
        }


# =============================
# ESTRATÉGIA 3: LEQUE DINÂMICO
# =============================
class EstrategiaLeque:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, historico, janela=20):
        if len(historico) < 10:
            return None
        
        recentes = historico[-janela:]
        ultimo = recentes[-1]
        
        macro_regiao = self.roleta.get_vizinhos(ultimo, 5)
        acertos = sum(1 for n in recentes if n in macro_regiao)
        
        if acertos >= 6:
            leque = 4
            status = "🔥 MUITO QUENTE"
            forca = 70
        elif acertos >= 3:
            leque = 2
            status = "🟡 MORNO"
            forca = 50
        else:
            leque = 1
            status = "🧊 FRIO"
            forca = 30
        
        alvos = self.roleta.get_vizinhos(ultimo, leque)
        
        return {
            'base': set(alvos),
            'forca': forca,
            'estrategias': [f"Leque {leque} vizinhos"],
            'status': status,
            'leque': leque,
            'acertos_regiao': acertos
        }


# =============================
# ESTRATÉGIA 4: ANÁLISE POR GIRO
# =============================
class EstrategiaPorGiro:
    def __init__(self, roleta):
        self.roleta = roleta
    
    def analisar(self, historico, lucky_recentes):
        if len(historico) < 5:
            return None
        
        hist = historico
        ultimo = hist[-1]
        ultimos_5 = hist[-5:] if len(hist) >= 5 else hist
        ultimos_10 = hist[-10:] if len(hist) >= 10 else hist
        
        freq_5 = Counter(ultimos_5)
        freq_10 = Counter(ultimos_10)
        
        repetiu = (hist[-1] == hist[-2]) if len(hist) >= 2 else False
        repeticoes_5 = [n for n in ultimos_5 if ultimos_5.count(n) >= 2]
        
        quentes_5 = [n for n, _ in freq_5.most_common(3)]
        quentes_10 = [n for n, _ in freq_10.most_common(5)]
        
        lucky_count = Counter(lucky_recentes) if lucky_recentes else Counter()
        top_lucky = [n for n, _ in lucky_count.most_common(5)]
        
        vizinhos = self.roleta.get_vizinhos(ultimo, 2)
        
        setores = Counter([self.roleta.get_setor(n) for n in ultimos_10 if n != 0])
        setor_dom = setores.most_common(1)[0][0] if setores else None
        
        vermelhos = sum(1 for n in ultimos_10 if n in self.roleta.vermelhos)
        pretos = sum(1 for n in ultimos_10 if n in self.roleta.pretos)
        cor_dom = 'Vermelho' if vermelhos > pretos else 'Preto'
        
        base = set()
        estrategias = []
        forca = 20
        
        if repetiu:
            base.add(ultimo)
            forca += 35
            estrategias.append(f"Repetiu {ultimo}")
        
        for n in repeticoes_5[:2]:
            base.add(n)
            forca += 10
        
        for n in top_lucky[:3]:
            base.add(n)
        if top_lucky:
            forca += 15
            estrategias.append("Lucky")
        
        for n in quentes_5[:2]:
            base.add(n)
        for n in quentes_10[:3]:
            base.add(n)
        estrategias.append("Quentes")
        
        for n in vizinhos[:3]:
            base.add(n)
        estrategias.append("Vizinhos")
        
        base.add(ultimo)
        
        if setor_dom:
            inicio = (setor_dom - 1) * 12 + 1
            fim = setor_dom * 12
            numeros_setor = set(range(inicio, fim + 1))
            base_setor = base.intersection(numeros_setor)
            if len(base_setor) >= 3:
                base = base_setor
                forca += 15
                estrategias.append(f"Setor {setor_dom}")
        
        if cor_dom == 'Vermelho':
            base_cor = {n for n in base if n in self.roleta.vermelhos or n == 0}
        else:
            base_cor = {n for n in base if n in self.roleta.pretos or n == 0}
        if len(base_cor) >= 3:
            base = base_cor
            forca += 10
            estrategias.append(cor_dom)
        
        prioridade = []
        for n in repeticoes_5:
            if n in base and n not in prioridade:
                prioridade.append(n)
        for n in top_lucky:
            if n in base and n not in prioridade:
                prioridade.append(n)
        for n in quentes_5:
            if n in base and n not in prioridade:
                prioridade.append(n)
        for n in vizinhos:
            if n in base and n not in prioridade:
                prioridade.append(n)
        for n in base:
            if n not in prioridade:
                prioridade.append(n)
        
        base_list = prioridade[:6]
        
        if len(base_list) < 3:
            for n in quentes_10:
                if n not in base_list:
                    base_list.append(n)
                    if len(base_list) >= 3:
                        break
        
        forca = min(100, max(15, forca))
        
        return {
            'base': set(base_list),
            'forca': forca,
            'estrategias': estrategias,
            'repetiu': repetiu
        }


# =============================
# BOT UNIFICADO
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        self.sniper = EstrategiaSniper(self.roleta)
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
    
    def analisar_e_prever(self, top_n=5, motores_ativos=None):
        if len(self.historico) < 5:
            return None
        
        if motores_ativos is None:
            motores_ativos = {'sniper': True, 'mineracao': True, 'leque': True, 'giro': True}
        
        lucky_recentes = []
        for sub in self.lucky[-10:]:
            lucky_recentes.extend(sub)
        
        resultados = []
        
        if motores_ativos.get('sniper', True) and len(self.historico) >= 15:
            r = self.sniper.analisar(list(self.historico), lucky_recentes)
            if r:
                resultados.append(('Sniper', r))
        
        if motores_ativos.get('mineracao', True) and len(self.historico) >= 10:
            r = self.mineracao.analisar(list(self.historico), list(self.lucky))
            if r:
                resultados.append(('Mineração', r))
        
        if motores_ativos.get('leque', True):
            janela = st.session_state.get('janela_leque', 20)
            r = self.leque.analisar(list(self.historico), janela)
            if r:
                resultados.append(('Leque', r))
        
        if motores_ativos.get('giro', True):
            r = self.giro.analisar(list(self.historico), lucky_recentes)
            if r:
                resultados.append(('Análise Giro', r))
        
        if not resultados:
            return None
        
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
        
        forca_media = forca_total / len(resultados) if resultados else 20
        
        if len(self.performance['historico']) >= 5:
            taxa_recente = sum(self.performance['historico'][-5:]) / 5
            if taxa_recente >= 0.4:
                forca_media += 10
            elif taxa_recente <= 0.15:
                forca_media -= 10
        
        forca_media = min(100, max(15, int(forca_media)))
        
        if forca_media >= 55:
            confianca = "Alta"
        elif forca_media >= 35:
            confianca = "Média"
        else:
            confianca = "Baixa"
        
        freq_base = Counter()
        for _, r in resultados:
            for n in r['base']:
                freq_base[n] += 1
        
        prioridade = [n for n, _ in freq_base.most_common()]
        base_list = prioridade[:top_n]
        
        gatilho = f"u={self.historico[-1]}"
        if self.historico[-1] == self.historico[-2] if len(self.historico) >= 2 else False:
            gatilho = f"REPETIU {self.historico[-1]}!"
        
        return {
            'nome': 'Bot Unificado',
            'numeros_apostar': sorted(base_list),
            'gatilho': gatilho,
            'forca_real': forca_media,
            'confianca': confianca,
            'motor': motor_principal,
            'estrategias_ativas': list(set(todas_estrategias))[:5],
            'qtd_motores': len(resultados),
            'repeticao': False,
            'giros_esperados': 0
        }
    
    def get_analise_completa(self):
        if len(self.historico) < 5:
            return "📊 Aguardando dados (mínimo 5)..."
        
        hist = self.historico
        ultimo = hist[-1]
        ultimos_10 = hist[-10:] if len(hist) >= 10 else hist
        
        freq_10 = Counter(ultimos_10)
        quentes = [n for n, _ in freq_10.most_common(5)]
        
        lucky_flat = []
        for sub in self.lucky[-5:]:
            lucky_flat.extend(sub)
        top_lucky = [n for n, _ in Counter(lucky_flat).most_common(5)]
        
        taxa = self.get_taxa_acerto()
        total = self.get_total_tentativas()
        
        txt = "🎯 BOT UNIFICADO\n" + "="*35 + "\n\n"
        txt += f"🎲 Último: {ultimo}\n"
        txt += f"📊 10 últimos: {hist[-10:]}\n\n"
        
        txt += f"🔥 Quentes: {quentes}\n"
        txt += f"🍀 Lucky: {top_lucky}\n"
        
        txt += f"\n🤖 MOTORES ATIVOS:\n"
        txt += f"  🎯 Sniper: {'✅' if st.session_state.get('usar_sniper', True) else '❌'}\n"
        txt += f"  🔬 Mineração: {'✅' if st.session_state.get('usar_mineracao', True) else '❌'}\n"
        txt += f"  🪭 Leque: {'✅' if st.session_state.get('usar_leque', True) else '❌'}\n"
        txt += f"  🔄 Giro: {'✅' if st.session_state.get('usar_giro', True) else '❌'}\n"
        
        if st.session_state.get('repetir_entrada', True):
            txt += f"\n⏳ Repetição após erro: ATIVADA (espera 2 giros, depois repete)\n"
        
        if total > 0:
            txt += f"\n📈 Perf: {taxa:.0%} ({self.performance['acertos']}/{total})\n"
        
        return txt
    
    def zerar(self):
        self.historico = []
        self.lucky = []
        self.lucky_mult = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}


# =============================
# SISTEMA PRINCIPAL (COM REPETIÇÃO APÓS ERRO - AGUARDA 2 GIROS)
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
        
        # NOVO: Controle de repetição após erro com espera de 2 giros
        self.giros_espera_repeticao = 0  # Contador de giros de espera (0, 1, 2)
        self.giros_restantes_espera = 0  # Quantos giros ainda faltam esperar
        self.ultima_entrada_numeros = []
        self.ultima_entrada_forca = 0
        self.ultima_entrada_motor = ""
        
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
        
        # Se está em modo de espera, decrementa o contador
        if self.giros_restantes_espera > 0:
            self.giros_restantes_espera -= 1
        
        if self.previsao_ativa:
            acerto = numero_real in self.previsao_ativa.get('numeros_apostar', [])
            self.bot.atualizar_resultado(acerto)
            
            if acerto:
                self.acertos += 1
                # ACERTOU! Reseta repetições e espera
                self.giros_restantes_espera = 0
                self.giros_espera_repeticao = 0
                self.ultima_entrada_numeros = []
            else:
                self.erros += 1
                # ERROU! Ativa espera de 2 giros se configurado
                if st.session_state.get('repetir_entrada', True) and not self.previsao_ativa.get('repeticao', False):
                    # Só ativa espera se NÃO for já uma entrada repetida
                    self.giros_restantes_espera = 2  # Esperar 2 giros
                    self.giros_espera_repeticao = 2
                    self.ultima_entrada_numeros = self.previsao_ativa.get('numeros_apostar', [])
                    self.ultima_entrada_forca = self.previsao_ativa.get('forca_real', 0)
                    self.ultima_entrada_motor = self.previsao_ativa.get('motor', '')
            
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
        
        # GERA PREVISÃO A CADA GIRO
        if len(self.historico_numeros) >= 5:
            intervalo = st.session_state.get('intervalo_minimo_entradas', 0)
            
            if len(self.historico_numeros) - self.ultima_entrada_rodada >= intervalo:
                
                # VERIFICA SE DEVE REPETIR ENTRADA ANTERIOR (após espera de 2 giros)
                if self.giros_restantes_espera == 0 and self.ultima_entrada_numeros:
                    # Passaram os 2 giros de espera, agora repete a entrada
                    self.giros_espera_repeticao = 0
                    
                    previsao_repetida = {
                        'nome': 'Bot Unificado',
                        'numeros_apostar': sorted(self.ultima_entrada_numeros),
                        'gatilho': 'REPETINDO ENTRADA ANTERIOR (após 2 giros)',
                        'forca_real': self.ultima_entrada_forca,
                        'confianca': 'Repetição',
                        'motor': self.ultima_entrada_motor,
                        'estrategias_ativas': ['Repetição pós-erro (2 giros)'],
                        'qtd_motores': 1,
                        'repeticao': True,
                        'giros_esperados': 2
                    }
                    
                    self.previsao_ativa = previsao_repetida
                    # Limpa para não repetir de novo
                    self.ultima_entrada_numeros = []
                    enviar_previsao_auto(previsao_repetida)
                elif self.giros_restantes_espera > 0:
                    # Ainda está esperando, não gera previsão
                    pass
                else:
                    # Gera nova análise normalmente
                    top_n = st.session_state.get('top_n_apostas', 5)
                    
                    motores_ativos = {
                        'sniper': st.session_state.get('usar_sniper', True),
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
        self.giros_restantes_espera = 0
        self.giros_espera_repeticao = 0
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
st.set_page_config(page_title="🎯 Bot Unificado — Todos os Motores", layout="centered")
st.title("🎯 Bot Unificado — Sniper + Mineração + Leque + Giro")

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
    sis.giros_espera_repeticao = dados.get('giros_espera_repeticao', 0)
    sis.giros_restantes_espera = dados.get('giros_restantes_espera', 0)
    sis.ultima_entrada_numeros = dados.get('ultima_entrada_numeros', [])
    sis.ultima_entrada_forca = dados.get('ultima_entrada_forca', 0)
    sis.ultima_entrada_motor = dados.get('ultima_entrada_motor', '')
    
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
    'modo_automatico': True, 'top_n_apostas': 5,
    'intervalo_minimo_entradas': 0, 'janela_analise': 50,
    'janela_leque': 20, 'forca_minima_sinal': 40,
    'usar_sniper': True, 'usar_mineracao': True,
    'usar_leque': True, 'usar_giro': True,
    'repetir_entrada': True
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
    st.write("**Selecione os motores:**")
    st.session_state.usar_sniper = st.checkbox("🎯 Sniper (Interseção D/C + Cluster)", value=st.session_state.usar_sniper)
    st.session_state.usar_mineracao = st.checkbox("🔬 Mineração (Markov + Lucky Cross)", value=st.session_state.usar_mineracao)
    st.session_state.usar_leque = st.checkbox("🪭 Leque Dinâmico", value=st.session_state.usar_leque)
    st.session_state.usar_giro = st.checkbox("🔄 Análise por Giro (SEMPRE ativo)", value=st.session_state.usar_giro)
    
    ativos = sum([st.session_state.usar_sniper, st.session_state.usar_mineracao, 
                  st.session_state.usar_leque, st.session_state.usar_giro])
    st.caption(f"📊 {ativos}/4 motores ativos")

with st.sidebar.expander("⏳ Repetição pós-Erro", expanded=True):
    st.session_state.repetir_entrada = st.checkbox("⏳ Repetir entrada após erro (espera 2 giros)", value=st.session_state.repetir_entrada,
        help="Quando errar, ESPERA 2 giros e depois repete a mesma entrada")
    st.info("""
    **Como funciona:**
    - ❌ Erro → espera 2 giros
    - ⏳ Após 2 giros → repete a entrada
    - ✅ Acerto → reseta e volta análise normal
    - ⏳ Entradas repetidas mostram emoji especial
    """)

with st.sidebar.expander("⚙️ Ajustes", expanded=True):
    st.session_state.top_n_apostas = st.slider("📊 Números por aposta", 3, 15, st.session_state.top_n_apostas)
    st.session_state.intervalo_minimo_entradas = st.slider("⏱️ Intervalo entre entradas", 0, 3, st.session_state.intervalo_minimo_entradas,
        help="0 = entrada todo giro")
    st.session_state.janela_leque = st.slider("🪭 Janela do Leque", 10, 50, st.session_state.janela_leque, 5)

st.session_state.modo_automatico = st.sidebar.checkbox("🔄 Modo Automático", value=st.session_state.modo_automatico)
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
    if taxa >= 30:
        st.success(f"🎯 Taxa: {taxa:.1f}%")
    elif taxa >= 20:
        st.warning(f"🎯 Taxa: {taxa:.1f}%")
    else:
        st.error(f"🎯 Taxa: {taxa:.1f}%")

# Indicador de espera/repetição ativa
if st.session_state.sistema.giros_restantes_espera > 0:
    st.warning(f"⏳ **Aguardando {st.session_state.sistema.giros_restantes_espera} giro(s) para repetir entrada anterior**")
elif st.session_state.sistema.ultima_entrada_numeros and st.session_state.sistema.giros_restantes_espera == 0 and st.session_state.sistema.giros_espera_repeticao > 0:
    st.info(f"⏳ **Pronto para repetir entrada no próximo giro!** (espera de 2 giros concluída)")

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
    giros_esperados = p.get('giros_esperados', 0)
    
    if repeticao:
        st.success(f"⏳ **REPETINDO ENTRADA!** (após espera de {giros_esperados} giros)")
    elif f >= 55:
        st.success(f"🔥 **FORÇA {f}%** - {c} ({qtd} motores)")
    elif f >= 35:
        st.warning(f"🎯 **FORÇA {f}%** - {c} ({qtd} motores)")
    else:
        st.info(f"📊 **FORÇA {f}%** - {c} ({qtd} motores)")
    
    st.caption(f"📋 {p['gatilho']}")
    if not repeticao:
        st.caption(f"🤖 Motor principal: {motor}")
        if estrategias:
            st.caption(f"🎯 {', '.join(estrategias[:4])}")
    
    st.write(f"**🔢 {len(p['numeros_apostar'])} números:**")
    nums = sorted(p['numeros_apostar'])
    # Exibe números lado a lado separados por vírgula
    st.markdown(f"### {', '.join(map(str, nums))}")
else:
    st.info(f"🎲 Iniciando análise...")

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
