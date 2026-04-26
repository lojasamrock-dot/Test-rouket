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
PADROES_PATH = "padroes_sequencia.json"

def salvar_sessao():
    try:
        if 'sistema' not in st.session_state or st.session_state.sistema is None:
            return False
        
        performance_data = {
            'acertos': st.session_state.sistema.bot.performance['acertos'],
            'erros': st.session_state.sistema.bot.performance['erros'],
            'historico': st.session_state.sistema.bot.performance['historico'],
            'estrategias': {
                k: {
                    'acertos': v['acertos'],
                    'erros': v['erros'],
                    'historico': list(v['historico'])
                } for k, v in st.session_state.sistema.bot.performance_estrategias.items()
            }
        }
        with open(PERFORMANCE_PATH, 'w') as f:
            json.dump(performance_data, f)
        
        if hasattr(st.session_state.sistema.bot, 'padroes_sequencia'):
            with open(PADROES_PATH, 'w') as f:
                json.dump(st.session_state.sistema.bot.padroes_sequencia, f)
        
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
            'usar_gap': st.session_state.get('usar_gap', True),
            'usar_sequencia': st.session_state.get('usar_sequencia', True),
            'usar_vizinhos_roda': st.session_state.get('usar_vizinhos_roda', True),
            'usar_terminais': st.session_state.get('usar_terminais', True),
            'usar_setor_quente': st.session_state.get('usar_setor_quente', True),
            'janela_analise': st.session_state.get('janela_analise', 50),
            'janela_leque': st.session_state.get('janela_leque', 20),
            'forca_minima_sinal': st.session_state.get('forca_minima_sinal', 40),
            'repetir_entrada': st.session_state.get('repetir_entrada', True),
            'repetir_acerto': st.session_state.get('repetir_acerto', True),
            'max_repeticoes_acerto': st.session_state.get('max_repeticoes_acerto', 3),
            'modo_repeticao_erro': st.session_state.sistema.modo_repeticao_erro,
            'modo_espera_pos_erro': st.session_state.sistema.modo_espera_pos_erro,
            'giros_espera_restantes': st.session_state.sistema.giros_espera_restantes,
            'repeticoes_acerto_consecutivas': st.session_state.sistema.repeticoes_acerto_consecutivas,
            'ultima_entrada_numeros': st.session_state.sistema.ultima_entrada_numeros,
            'ultima_entrada_forca': st.session_state.sistema.ultima_entrada_forca,
            'ultima_entrada_motor': st.session_state.sistema.ultima_entrada_motor,
            'ultima_entrada_green': st.session_state.sistema.ultima_entrada_green,
            'entrada_era_repeticao_erro': st.session_state.sistema.entrada_era_repeticao_erro
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
        for path in [SESSION_DATA_PATH, HISTORICO_PATH, PERFORMANCE_PATH, PADROES_PATH]:
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
        green = previsao.get('green', False)
        green_count = previsao.get('green_count', 0)
        
        if green:
            emoji = "🟢"
            tipo = f"GREEN #{green_count}"
        elif repeticao:
            emoji = "🔁"
            tipo = "REPETINDO (erro)"
        elif forca >= 60:
            emoji = "🔥"
            tipo = motor
        elif forca >= 40:
            emoji = "🎯"
            tipo = motor
        else:
            emoji = "📊"
            tipo = motor
        
        msg = f"{emoji} **ENTRADA** - Força: {forca}%\n"
        
        if green:
            msg += f"🟢 REPETINDO APÓS ACERTO! (Green #{green_count}/{st.session_state.get('max_repeticoes_acerto', 3)})\n"
        elif repeticao:
            msg += f"🔁 REPETINDO ENTRADA APÓS ERRO! (1ª repetição)\n"
        else:
            msg += f"📋 {previsao['gatilho']}\n"
            if motor:
                msg += f"🤖 Motor: {motor}\n"
            if estrategias:
                msg += f"🎯 {', '.join(estrategias[:3])}\n"
        
        msg += f"🔢 {len(numeros)} números: {numeros}"
        
        st.toast(f"{'🟢 Green' if green else '🔁 Repetindo' if repeticao else '🎯 ' + motor} - {forca}%", icon=emoji)
        st.success(f"🔔 {msg}")
        
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            tag = "[GREEN]" if green else "[REPETINDO]" if repeticao else ""
            enviar_telegram(f"🔔 ENTRADA {tag} {forca}%\n" + " ".join(map(str, numeros)))
        
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
    
    def get_terminacao(self, numero):
        return numero % 10

# =============================
# ESTRATÉGIAS
# =============================
class EstrategiaSniper:
    def __init__(self, roleta):
        self.roleta = roleta
    def analisar(self, historico, lucky_recentes):
        if len(historico) < 15: return None
        recentes = historico[-15:]
        duzias = Counter([self.roleta.get_setor(n) for n in recentes if n != 0])
        colunas = Counter([self.roleta.get_coluna(n) for n in recentes if n != 0])
        melhor_duzia = duzias.most_common(1)[0][0] if duzias else None
        melhor_coluna = colunas.most_common(1)[0][0] if colunas else None
        roda_hits = []
        for n in recentes: roda_hits.extend(self.roleta.get_vizinhos(n, raio=1))
        zona_quente = Counter(roda_hits).most_common(1)[0][0] if roda_hits else None
        vizinhos_zona = self.roleta.get_vizinhos(zona_quente, raio=2) if zona_quente else []
        forca, estrategia, base, gatilho = 0, [], set(), ""
        
        if melhor_duzia and melhor_coluna:
            if duzias[melhor_duzia] >= 7 and colunas[melhor_coluna] >= 6:
                forca += 60; estrategia.append("Interseção D/C"); d, c = melhor_duzia, melhor_coluna
                base.update(set(range((d-1)*12 + 1, d*12 + 1)).intersection(set(range(c, 37, 3))))
                gatilho = f"Interseção D{d} x C{c}"
        if zona_quente and vizinhos_zona:
            hits_zona = sum(1 for n in recentes if n in vizinhos_zona)
            if hits_zona >= 5:
                forca += 50; estrategia.append("Cluster Físico"); base.update(vizinhos_zona)
                if not gatilho: gatilho = f"Zona: {zona_quente}"
        if lucky_recentes:
            lucky_quentes = [n for n, _ in Counter(lucky_recentes).most_common(3)]
            if any(l in recentes for l in lucky_quentes):
                forca += 15; estrategia.append("Raios")
        if forca == 0: return None
        return {'base': base, 'forca': min(100, forca), 'estrategias': estrategia, 'gatilho': gatilho}

class EstrategiaMineracao:
    def __init__(self):
        self.transicoes = defaultdict(list)
    def atualizar(self, historico):
        self.transicoes.clear()
        for i in range(len(historico) - 1): self.transicoes[historico[i]].append(historico[i + 1])
    def analisar(self, historico, historico_lucky):
        if len(historico) < 10: return None
        self.atualizar(historico)
        ultimo = historico[-1]
        base, forca, estrategias = set(), 0, []
        seguidores = self.transicoes.get(ultimo, [])
        if seguidores:
            base.update([n for n, _ in Counter(seguidores).most_common(3)])
            forca += 30; estrategias.append("Markov")
        if len(historico_lucky) >= 2:
            total = min(len(historico)-1, len(historico_lucky)-1)
            acertos = sum(1 for i in range(total) if historico[i+1] in historico_lucky[i])
            taxa = acertos / total * 100 if total > 0 else 0
            if taxa > 18:
                forca += 35; estrategias.append(f"Lucky Cross {taxa:.0f}%")
        if forca == 0: return None
        return {'base': base, 'forca': min(100, forca), 'estrategias': estrategias}

class EstrategiaLeque:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico, janela=20):
        if len(historico) < 10: return None
        recentes = historico[-janela:]
        ultimo = recentes[-1]
        acertos = sum(1 for n in recentes if n in self.roleta.get_vizinhos(ultimo, 5))
        if acertos >= 6: leque, status, forca = 4, "🔥 MUITO QUENTE", 70
        elif acertos >= 3: leque, status, forca = 2, "🟡 MORNO", 50
        else: leque, status, forca = 1, "🧊 FRIO", 30
        return {'base': set(self.roleta.get_vizinhos(ultimo, leque)), 'forca': forca, 'estrategias': [f"Leque {leque} vizinhos"], 'status': status}

class EstrategiaPorGiro:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico, lucky_recentes):
        if len(historico) < 5: return None
        hist = historico; ultimo = hist[-1]; ultimos_10 = hist[-10:] if len(hist) >= 10 else hist
        repeticoes_5 = [n for n in hist[-5:] if hist[-5:].count(n) >= 2]
        base, estrategias, forca = set(), [], 20
        if len(hist) >= 2 and hist[-1] == hist[-2]:
            base.add(ultimo); forca += 35; estrategias.append(f"Repetiu {ultimo}")
        for n in repeticoes_5[:2]: base.add(n); forca += 10
        top_lucky = [n for n, _ in Counter(lucky_recentes).most_common(5)]
        for n in top_lucky[:3]: base.add(n)
        if top_lucky: forca += 15; estrategias.append("Lucky")
        for n in [n for n, _ in Counter(hist[-5:]).most_common(3)][:2]: base.add(n)
        for n in self.roleta.get_vizinhos(ultimo, 2)[:3]: base.add(n)
        estrategias.extend(["Quentes", "Vizinhos"]); base.add(ultimo)
        prioridade = list(base)
        return {'base': set(prioridade[:6]), 'forca': min(100, max(15, forca)), 'estrategias': estrategias}

class EstrategiaGap:
    def analisar(self, historico):
        if len(historico) < 5: return None
        ultimo = historico[-1]
        if len(historico) >= 3 and historico[-3] == ultimo:
            return {'base': {ultimo, historico[-2]}, 'forca': 55, 'estrategias': [f'Repetição Gap1']}
        if len(historico) >= 4 and historico[-4] == ultimo:
            return {'base': {ultimo, historico[-2], historico[-3]}, 'forca': 50, 'estrategias': [f'Repetição Gap2']}
        recentes = historico[-20:]; gaps = []
        for i in range(len(recentes) - 2):
            for gap in [1, 2, 3]:
                if i + gap + 1 < len(recentes) and recentes[i] == recentes[i + gap + 1]: gaps.append(recentes[i])
        if gaps:
            top_gap = [n for n, c in Counter(gaps).most_common(3)]
            return {'base': set(top_gap), 'forca': 40, 'estrategias': ['Gap Quente']}
        return None

class EstrategiaSequencia:
    def __init__(self): self.padroes = defaultdict(list)
    def treinar(self, historico):
        self.padroes.clear()
        for i in range(len(historico) - 1): self.padroes[historico[i]].append(historico[i + 1])
    def prever(self, numero, top_n=10):
        return [n for n, _ in Counter(self.padroes.get(numero, [])).most_common(top_n)]
    def analisar(self, historico):
        if len(historico) < 10: return None
        self.treinar(historico); ultimo = historico[-1]; previsao = self.prever(ultimo, 10)
        if len(previsao) < 3: return None
        forca = 60 if len(self.padroes.get(ultimo, [])) >= 10 else 45 if len(self.padroes.get(ultimo, [])) >= 5 else 30
        return {'base': set(previsao[:5]), 'forca': forca, 'estrategias': [f'Sequência após {ultimo}']}

class EstrategiaVizinhosRoda:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico):
        if len(historico) < 5: return None
        ultimo = historico[-1]; ultimos_10 = historico[-10:]
        vizinhos_proximos = self.roleta.get_vizinhos(ultimo, 3)
        vizinhos_que_sairam = [n for n in ultimos_10 if n in vizinhos_proximos]
        forca = 40 if len(vizinhos_que_sairam) >= 4 else 0
        if forca == 0: return None
        base = set(self.roleta.get_vizinhos(ultimo, 2))
        for n in historico[-3:]: base.update(self.roleta.get_vizinhos(n, 1))
        return {'base': base, 'forca': forca, 'estrategias': ['Cluster vizinhos']}

class EstrategiaTerminais:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico):
        if len(historico) < 5: return None
        ultimo = historico[-1]; term_ultimo = self.roleta.get_terminacao(ultimo)
        term_na_mesma = [n for n in historico[-15:] if self.roleta.get_terminacao(n) == term_ultimo]
        forca, base = 0, set()
        if len(term_na_mesma) >= 3:
            forca += 35; base.update([n for n in range(37) if self.roleta.get_terminacao(n) == term_ultimo][:6])
        if forca == 0: return None
        return {'base': base, 'forca': forca, 'estrategias': [f"Terminal {term_ultimo} quente"]}

class EstrategiaSetorQuente:
    def __init__(self, roleta): self.roleta = roleta
    def analisar(self, historico):
        if len(historico) < 10: return None
        setores_10 = Counter([self.roleta.get_setor(n) for n in historico[-10:] if n != 0])
        setor_dom_10 = setores_10.most_common(1)[0] if setores_10 else None
        forca, base = 0, set()
        if setor_dom_10 and setor_dom_10[1] >= 6:
            s = setor_dom_10[0]; forca += 50
            base.update(range((s - 1) * 12 + 1, s * 12 + 1))
        if forca == 0: return None
        return {'base': base - set(historico[-5:]), 'forca': forca, 'estrategias': [f"Setor {s} dominante"]}


# =============================
# BOT UNIFICADO COM PERFORMANCE DE ESTRATÉGIAS
# =============================
class RoletaBotUnificado:
    def __init__(self):
        self.roleta = RoletaBase()
        self.sniper = EstrategiaSniper(self.roleta)
        self.mineracao = EstrategiaMineracao()
        self.leque = EstrategiaLeque(self.roleta)
        self.giro = EstrategiaPorGiro(self.roleta)
        self.gap = EstrategiaGap()
        self.sequencia = EstrategiaSequencia()
        self.vizinhos_roda = EstrategiaVizinhosRoda(self.roleta)
        self.terminais = EstrategiaTerminais(self.roleta)
        self.setor_quente = EstrategiaSetorQuente(self.roleta)
        
        self.historico = []
        self.lucky = []
        self.lucky_mult = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        
        # MONITORAMENTO INDIVIDUAL DE ESTRATÉGIAS
        self.nomes_motores = ['Sniper', 'Mineração', 'Leque', 'Análise Giro', 'Gap', 'Sequência', 'Vizinhos Roda', 'Terminais', 'Setor Quente']
        self.performance_estrategias = {
            motor: {'acertos': 0, 'erros': 0, 'historico': deque(maxlen=50)} for motor in self.nomes_motores
        }
        self.ultima_analise = [] # Guarda resultados para avaliação no próximo giro
        
    def atualizar(self, numero, lucky_nums=None, lucky_mults=None):
        self.historico.append(numero)
        self.lucky.append(lucky_nums if lucky_nums else [])
        self.lucky_mult.append(lucky_mults if lucky_mults else {})
        if len(self.historico) > 200:
            self.historico = self.historico[-200:]
            self.lucky = self.lucky[-200:]
            self.lucky_mult = self.lucky_mult[-200:]
        
        if len(self.historico) >= 2:
            self.sequencia.treinar(self.historico)
    
    def atualizar_resultado(self, acerto):
        self.performance['historico'].append(1 if acerto else 0)
        if len(self.performance['historico']) > 50:
            self.performance['historico'] = self.performance['historico'][-50:]
        if acerto:
            self.performance['acertos'] += 1
        else:
            self.performance['erros'] += 1
            
    def avaliar_motores(self, numero_real):
        # Avalia quem acertou na última rodada com base na análise prévia
        if self.ultima_analise:
            for motor, r in self.ultima_analise:
                if numero_real in r['base']:
                    self.performance_estrategias[motor]['acertos'] += 1
                    self.performance_estrategias[motor]['historico'].append(1)
                else:
                    self.performance_estrategias[motor]['erros'] += 1
                    self.performance_estrategias[motor]['historico'].append(0)
            self.ultima_analise = [] # Reseta após avaliação
    
    def get_taxa_acerto(self):
        total = self.performance['acertos'] + self.performance['erros']
        return self.performance['acertos'] / total if total > 0 else 0
    
    def get_total_tentativas(self):
        return self.performance['acertos'] + self.performance['erros']
    
    def analisar_e_prever(self, top_n=5, motores_ativos=None):
        if len(self.historico) < 5: return None
        
        if motores_ativos is None:
            motores_ativos = {m: True for m in ['sniper', 'mineracao', 'leque', 'giro', 'gap', 'sequencia', 'vizinhos_roda', 'terminais', 'setor_quente']}
        
        lucky_recentes = []
        for sub in self.lucky[-10:]: lucky_recentes.extend(sub)
        
        resultados = []
        
        if motores_ativos.get('sniper', True) and len(self.historico) >= 15:
            r = self.sniper.analisar(list(self.historico), lucky_recentes)
            if r: resultados.append(('Sniper', r))
        
        if motores_ativos.get('mineracao', True) and len(self.historico) >= 10:
            r = self.mineracao.analisar(list(self.historico), list(self.lucky))
            if r: resultados.append(('Mineração', r))
        
        if motores_ativos.get('leque', True):
            r = self.leque.analisar(list(self.historico), st.session_state.get('janela_leque', 20))
            if r: resultados.append(('Leque', r))
        
        if motores_ativos.get('giro', True):
            r = self.giro.analisar(list(self.historico), lucky_recentes)
            if r: resultados.append(('Análise Giro', r))
        
        if motores_ativos.get('gap', True):
            r = self.gap.analisar(list(self.historico))
            if r: resultados.append(('Gap', r))
        
        if motores_ativos.get('sequencia', True):
            r = self.sequencia.analisar(list(self.historico))
            if r: resultados.append(('Sequência', r))
        
        if motores_ativos.get('vizinhos_roda', True) and len(self.historico) >= 5:
            r = self.vizinhos_roda.analisar(list(self.historico))
            if r: resultados.append(('Vizinhos Roda', r))
        
        if motores_ativos.get('terminais', True) and len(self.historico) >= 5:
            r = self.terminais.analisar(list(self.historico))
            if r: resultados.append(('Terminais', r))
        
        if motores_ativos.get('setor_quente', True) and len(self.historico) >= 10:
            r = self.setor_quente.analisar(list(self.historico))
            if r: resultados.append(('Setor Quente', r))
        
        # Salva para avaliar se acertam no próximo giro
        self.ultima_analise = resultados
        
        if not resultados: return None
        
        base_final = set()
        todas_estrategias = []
        forca_total = 0
        motor_principal = ""
        maior_forca = 0
        freq_base = Counter()
        
        # CÁLCULO DE PESOS BASEADO NA PERFORMANCE
        for motor, r in resultados:
            perf = self.performance_estrategias[motor]
            total_motor = perf['acertos'] + perf['erros']
            peso = 1.0 # Peso padrão
            
            # Ajusta peso se tiver histórico suficiente (>5 entradas)
            if total_motor >= 5:
                taxa = sum(perf['historico']) / len(perf['historico']) if len(perf['historico']) > 0 else 0
                if taxa >= 0.40: peso = 2.0  # Bonifica estratégias que estão acertando muito
                elif taxa >= 0.25: peso = 1.5
                elif taxa < 0.10: peso = 0.5   # Penaliza estratégias ruins
            
            forca_ponderada = r['forca'] * peso
            forca_total += forca_ponderada
            
            if forca_ponderada > maior_forca:
                maior_forca = forca_ponderada
                motor_principal = motor
            
            base_final.update(r['base'])
            todas_estrategias.extend(r['estrategias'])
            
            # Soma a frequência com o peso do motor (MÚLTIPLOS VOTOS PARA MOTORES BONS)
            for n in r['base']:
                freq_base[n] += peso
        
        forca_media = forca_total / len(resultados) if resultados else 20
        forca_media = min(100, max(15, int(forca_media)))
        
        confianca = "Alta" if forca_media >= 55 else "Média" if forca_media >= 35 else "Baixa"
        
        # Pega os Top N baseado no peso/votos
        prioridade = [n for n, _ in freq_base.most_common()]
        base_list = prioridade[:top_n]
        
        gatilho = f"u={self.historico[-1]}"
        if len(self.historico) >= 2 and self.historico[-1] == self.historico[-2]:
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
            'green': False,
            'green_count': 0
        }
    
    def zerar(self):
        self.historico = []
        self.lucky = []
        self.lucky_mult = []
        self.performance = {'acertos': 0, 'erros': 0, 'historico': []}
        self.performance_estrategias = {motor: {'acertos': 0, 'erros': 0, 'historico': deque(maxlen=50)} for motor in self.nomes_motores}
        self.ultima_analise = []

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
        self.modo_repeticao_erro = False
        self.modo_espera_pos_erro = False
        self.giros_espera_restantes = 0
        self.repeticoes_acerto_consecutivas = 0
        self.ultima_entrada_green = False
        self.entrada_era_repeticao_erro = False
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
        
        # AVALIAÇÃO DE PERFORMANCE DAS ESTRATÉGIAS INDIVIDUAIS
        self.bot.avaliar_motores(numero_real)
        
        if self.modo_espera_pos_erro and self.giros_espera_restantes > 0:
            self.giros_espera_restantes -= 1
            if self.giros_espera_restantes <= 0:
                self.modo_espera_pos_erro = False
                self.modo_repeticao_erro = False
                self.ultima_entrada_numeros = []
                self.entrada_era_repeticao_erro = False
        
        if self.previsao_ativa:
            acerto = numero_real in self.previsao_ativa.get('numeros_apostar', [])
            self.bot.atualizar_resultado(acerto)
            era_repeticao = self.entrada_era_repeticao_erro
            
            if acerto:
                self.acertos += 1
                self.modo_repeticao_erro = False
                self.modo_espera_pos_erro = False
                self.giros_espera_restantes = 0
                self.entrada_era_repeticao_erro = False
                
                if not era_repeticao and st.session_state.get('repetir_acerto', True):
                    max_rep = st.session_state.get('max_repeticoes_acerto', 3)
                    if self.repeticoes_acerto_consecutivas < max_rep:
                        self.repeticoes_acerto_consecutivas += 1
                        self.ultima_entrada_green = True
                        self.ultima_entrada_numeros = self.previsao_ativa.get('numeros_apostar', [])
                        self.ultima_entrada_forca = self.previsao_ativa.get('forca_real', 0)
                        self.ultima_entrada_motor = self.previsao_ativa.get('motor', '')
                    else:
                        self.repeticoes_acerto_consecutivas = 0
                        self.ultima_entrada_green = False
                        self.ultima_entrada_numeros = []
                else:
                    self.repeticoes_acerto_consecutivas = 0
                    self.ultima_entrada_green = False
                    self.ultima_entrada_numeros = []
                
            else:
                self.erros += 1
                if era_repeticao:
                    self.modo_repeticao_erro = False
                    self.modo_espera_pos_erro = True
                    self.giros_espera_restantes = 2
                    self.entrada_era_repeticao_erro = False
                    self.ultima_entrada_numeros = []
                    self.repeticoes_acerto_consecutivas = 0
                    self.ultima_entrada_green = False
                elif self.previsao_ativa.get('green', False):
                    self.repeticoes_acerto_consecutivas = 0
                    self.ultima_entrada_green = False
                    self.ultima_entrada_numeros = []
                    self.modo_repeticao_erro = False
                    self.modo_espera_pos_erro = False
                    self.entrada_era_repeticao_erro = False
                else:
                    if st.session_state.get('repetir_entrada', True):
                        self.modo_repeticao_erro = True
                        self.modo_espera_pos_erro = False
                        self.giros_espera_restantes = 0
                        self.entrada_era_repeticao_erro = False
                        self.ultima_entrada_numeros = self.previsao_ativa.get('numeros_apostar', [])
                        self.ultima_entrada_forca = self.previsao_ativa.get('forca_real', 0)
                        self.ultima_entrada_motor = self.previsao_ativa.get('motor', '')
                        self.repeticoes_acerto_consecutivas = 0
                        self.ultima_entrada_green = False
            
            enviar_resultado_auto(numero_real, acerto, mult)
            self.historico_desempenho.append({
                'numero': numero_real, 'acerto': acerto, 'multiplicador': mult,
                'forca': self.previsao_ativa.get('forca_real', 0),
                'green': self.previsao_ativa.get('green', False),
                'repeticao_erro': self.previsao_ativa.get('repeticao', False)
            })
            self.previsao_ativa = None
            self.ultima_entrada_rodada = len(self.historico_numeros)
            self.rodadas_sem_entrada = 0
        
        if self.estrategia_ativa_manual: return
        
        # GERA PREVISÃO
        if len(self.historico_numeros) >= 5:
            intervalo = st.session_state.get('intervalo_minimo_entradas', 0)
            if len(self.historico_numeros) - self.ultima_entrada_rodada >= intervalo:
                if self.ultima_entrada_green and self.ultima_entrada_numeros and self.repeticoes_acerto_consecutivas > 0:
                    previsao = {
                        'nome': 'Bot Unificado', 'numeros_apostar': sorted(self.ultima_entrada_numeros),
                        'gatilho': f'🟢 GREEN! ({self.repeticoes_acerto_consecutivas}/{st.session_state.get("max_repeticoes_acerto", 3)})',
                        'forca_real': min(100, self.ultima_entrada_forca + 10), 'confianca': 'Green',
                        'motor': self.ultima_entrada_motor, 'estrategias_ativas': [f'Green #{self.repeticoes_acerto_consecutivas}'],
                        'qtd_motores': 1, 'repeticao': False, 'green': True, 'green_count': self.repeticoes_acerto_consecutivas
                    }
                    self.previsao_ativa = previsao
                    self.ultima_entrada_green = False; self.entrada_era_repeticao_erro = False
                    enviar_previsao_auto(previsao)
                elif self.modo_repeticao_erro and self.ultima_entrada_numeros:
                    previsao = {
                        'nome': 'Bot Unificado', 'numeros_apostar': sorted(self.ultima_entrada_numeros),
                        'gatilho': '🔁 REPETINDO APÓS ERRO! (1x)', 'forca_real': self.ultima_entrada_forca,
                        'confianca': 'Repetição Erro', 'motor': self.ultima_entrada_motor,
                        'estrategias_ativas': ['Repetição pós-erro (1x)'], 'qtd_motores': 1,
                        'repeticao': True, 'green': False, 'green_count': 0
                    }
                    self.previsao_ativa = previsao
                    self.modo_repeticao_erro = False; self.entrada_era_repeticao_erro = True
                    enviar_previsao_auto(previsao)
                elif not self.modo_espera_pos_erro and not self.ultima_entrada_green:
                    motores_ativos = {
                        'sniper': st.session_state.get('usar_sniper', True), 'mineracao': st.session_state.get('usar_mineracao', True),
                        'leque': st.session_state.get('usar_leque', True), 'giro': st.session_state.get('usar_giro', True),
                        'gap': st.session_state.get('usar_gap', True), 'sequencia': st.session_state.get('usar_sequencia', True),
                        'vizinhos_roda': st.session_state.get('usar_vizinhos_roda', True), 'terminais': st.session_state.get('usar_terminais', True),
                        'setor_quente': st.session_state.get('usar_setor_quente', True)
                    }
                    nova = self.bot.analisar_e_prever(st.session_state.get('top_n_apostas', 5), motores_ativos)
                    if nova:
                        self.previsao_ativa = nova; self.entrada_era_repeticao_erro = False
                        enviar_previsao_auto(nova)
    
    def zerar_estatisticas(self):
        self.acertos = 0; self.erros = 0; self.historico_desempenho = []; self.historico_numeros.clear(); self.historico_lucky.clear()
        self.rodadas_sem_entrada = 0; self.ultima_entrada_rodada = -10
        self.modo_repeticao_erro = False; self.modo_espera_pos_erro = False; self.giros_espera_restantes = 0
        self.repeticoes_acerto_consecutivas = 0; self.ultima_entrada_green = False; self.entrada_era_repeticao_erro = False
        self.ultima_entrada_numeros = []; self.bot.zerar(); salvar_sessao()
    
    def get_status(self):
        return {'acertos': self.acertos, 'erros': self.erros, 'total': self.acertos + self.erros, 'rodadas_sem_entrada': self.rodadas_sem_entrada}

# =============================
# FUNÇÕES AUXILIARES E API
# =============================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def salvar_resultado_em_arquivo(historico, caminho=HISTORICO_PATH):
    try:
        with open(caminho, "w") as f: json.dump(historico, f, indent=2)
    except: pass

def extrair_numeros_raio(resultado_api):
    nums, mults = [], {}
    try:
        for item in resultado_api.get('data', {}).get('result', {}).get('luckyNumbersList', []):
            if item.get('number') is not None:
                nums.append(item['number'])
                if item.get('roundedMultiplier') is not None: mults[item['number']] = item['roundedMultiplier']
    except: pass
    return nums, mults

def fetch_latest_result():
    try:
        data = requests.get(API_URL, headers=HEADERS, timeout=5).json()
        nums, mults = extrair_numeros_raio(data)
        return {"number": data.get("data", {}).get("result", {}).get("outcome", {}).get("number"),
                "timestamp": data.get("data", {}).get("startedAt"), "luckyNumbers": nums, "luckyMultipliers": mults}
    except: return None

def exportar_historico(historico, formato='json'):
    if formato == 'json': return json.dumps(historico, indent=2, ensure_ascii=False)
    linhas = ["numero,timestamp,multiplicador"]
    for item in historico:
        if isinstance(item, dict): linhas.append(f"{item.get('number', '')},{item.get('timestamp', '')},{item.get('luckyMultipliers', {}).get(item.get('number', ''), '')}")
        else: linhas.append(f"{item},,")
    return "\n".join(linhas)

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎯 Bot Unificado — 9 Motores", layout="centered")
st.title("🎯 Bot Unificado — 9 Motores (Com Pesos)")

if "sistema" not in st.session_state or st.session_state.sistema is None: st.session_state.sistema = SistemaBot()

dados = carregar_dados_persistidos()
if dados:
    if not st.session_state.get('historico'): st.session_state.historico = dados.get('historico', [])
    sis = st.session_state.sistema
    sis.acertos = dados.get('sistema_acertos', 0); sis.erros = dados.get('sistema_erros', 0)
    sis.historico_desempenho = dados.get('sistema_historico_desempenho', [])
    for n in dados.get('historico_numeros', []): sis.historico_numeros.append(n)
    for l in dados.get('historico_lucky', []): sis.historico_lucky.append(l)
    for n, l in zip(dados.get('historico_numeros', []), dados.get('historico_lucky', [])):
        sis.bot.historico.append(n); sis.bot.lucky.append(l)
    
    if os.path.exists(PERFORMANCE_PATH):
        try:
            with open(PERFORMANCE_PATH, 'r') as f:
                perf = json.load(f)
                sis.bot.performance = {'acertos': perf.get('acertos', 0), 'erros': perf.get('erros', 0), 'historico': perf.get('historico', [])}
                if 'estrategias' in perf:
                    for k, v in perf['estrategias'].items():
                        if k in sis.bot.performance_estrategias:
                            sis.bot.performance_estrategias[k]['acertos'] = v.get('acertos', 0)
                            sis.bot.performance_estrategias[k]['erros'] = v.get('erros', 0)
                            sis.bot.performance_estrategias[k]['historico'] = deque(v.get('historico', []), maxlen=50)
        except: pass

for k, v in {'modo_automatico': True, 'top_n_apostas': 5, 'usar_sniper': True, 'usar_mineracao': True, 'usar_leque': True, 'usar_giro': True, 'usar_gap': True, 'usar_sequencia': True, 'usar_vizinhos_roda': True, 'usar_terminais': True, 'usar_setor_quente': True, 'repetir_entrada': True, 'repetir_acerto': True, 'max_repeticoes_acerto': 3}.items():
    if k not in st.session_state: st.session_state[k] = v

if "historico" not in st.session_state:
    try:
        with open(HISTORICO_PATH, "r") as f: st.session_state.historico = json.load(f)
    except: st.session_state.historico = []

st.sidebar.title("⚙️ Configurações")
st.session_state.modo_automatico = st.sidebar.checkbox("🔄 Auto", value=st.session_state.modo_automatico)

# Exibição de Performance dos Motores na Sidebar
with st.sidebar.expander("🏆 Ranking dos Motores", expanded=True):
    ranking = []
    for motor, perf in st.session_state.sistema.bot.performance_estrategias.items():
        total = perf['acertos'] + perf['erros']
        taxa = (perf['acertos'] / total) * 100 if total > 0 else 0
        ranking.append({'motor': motor, 'taxa': taxa, 'acertos': perf['acertos'], 'erros': perf['erros']})
    
    ranking.sort(key=lambda x: x['taxa'], reverse=True)
    for r in ranking:
        icone = "🟢" if r['taxa'] >= 30 else "🟡" if r['taxa'] >= 15 else "🔴"
        st.write(f"{icone} **{r['motor']}**: {r['taxa']:.1f}% ({r['acertos']}/{r['acertos']+r['erros']})")

with st.sidebar.expander("💾 Geral", expanded=False):
    if st.button("💾 Salvar"): salvar_resultado_em_arquivo(st.session_state.historico); salvar_sessao(); st.success("✅")
    if st.button("🗑️ Zerar") and st.checkbox("Confirmar"): st.session_state.sistema.zerar_estatisticas(); st.rerun()

st_autorefresh(interval=3000, key="refresh")
resultado = fetch_latest_result()
if resultado and resultado.get("timestamp") and resultado["timestamp"] != (st.session_state.historico[-1].get("timestamp") if st.session_state.historico else None):
    if resultado.get("number") is not None:
        st.session_state.historico.append(resultado); st.session_state.sistema.processar_novo_numero(resultado)
        salvar_resultado_em_arquivo(st.session_state.historico); salvar_sessao()

st.subheader("🔁 Últimos Números")
if st.session_state.historico:
    st.write(" ".join([f"**{i['number'] if isinstance(i, dict) else i}**" for i in st.session_state.historico[-10:]]))

sis = st.session_state.sistema; status = sis.get_status()
c1, c2, c3 = st.columns(3)
c1.metric("🟢 Acertos", status['acertos']); c2.metric("🔴 Erros", status['erros']); c3.metric("📊 Total", status['total'])

if sis.modo_espera_pos_erro: st.warning(f"⏳ **Aguardando {sis.giros_espera_restantes} giro(s) após erro**")
elif sis.entrada_era_repeticao_erro and sis.previsao_ativa: st.warning("🔁 **Entrada REPETIÇÃO pós-erro**")

st.subheader("🎯 Previsão Ativa")
if sis.previsao_ativa:
    p = sis.previsao_ativa; f = p.get('forca_real', 0)
    st.success(f"**FORÇA {f}%** - Motor Principal: {p['motor']}")
    st.write(f"**🔢 {len(p['numeros_apostar'])} números:**")
    st.markdown(f"### {', '.join(map(str, sorted(p['numeros_apostar'])))}")
else: st.info(f"🎲 Aguardando...")
