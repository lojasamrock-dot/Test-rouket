import streamlit as st
import json
import os
import requests
import logging
from collections import Counter, deque, defaultdict
from streamlit_autorefresh import st_autorefresh
import pickle
from datetime import datetime, timezone, timedelta
import numpy as np
import plotly.graph_objects as plt
import csv
import base64
from io import StringIO, BytesIO

# Importação Segura do Módulo de Machine Learning
try:
    from sklearn.ensemble import RandomForestClassifier
    import joblib
    ML_DISPONIVEL = True
except ImportError:
    ML_DISPONIVEL = False

# =============================
# CONFIGURAÇÕES DE LOGGING
# =============================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('roleta_bot.log'), logging.StreamHandler()]
)

# =============================
# FUSO HORÁRIO BRASÍLIA
# =============================
BRT = timezone(timedelta(hours=-3))

def hora_brasilia():
    return datetime.now(BRT)

def formatar_hora_brasilia(dt=None):
    if dt is None: dt = hora_brasilia()
    return dt.strftime('%H:%M:%S')

def timestamp_brasilia():
    return hora_brasilia().isoformat()

def data_brasilia():
    return hora_brasilia().strftime('%Y-%m-%d')

# =============================
# SETUPS INDEPENDENTES POR ROLETA
# =============================

SETUP_BASE = {
    'pagamento_numero': 20,
    'pagamento_zero': 20,
    'pagamento_duzia': 3,
    'confianca_minima_entrada': 2.0,
    'embalo_peso': 9,
    'embalo_reforco': 5,
    'bloquear_alerta_zero_conf_alta': True,
    'bloquear_anti_erro_zero_conf_baixa': True,
    'filtro_conf_baixa': 2.0,
    'fadiga_duzia': 4,
    'ritmo_alternado_peso': 10,
    'ritmo_alternado_forca': 10,
    'max_repeticoes_embalo': 4,
    'confianca_maxima_segura': 3.3,
    'rodadas_verificacao_conf_alta': 5,
    'pausa_pos_raio': 2,
    'raio_alto_minimo': 100,
    'zero_termometro_max': 15,
    'anti_erro_skip_discordancia': True,
    'ritmo_v_peso': 9,
    'ritmo_v_forca': 9,
    'ritmo_v_confirmacoes': 2,
    'ml_janela_treino': 20,
    'ml_atualizar_a_cada': 5,
    'score_ml_peso': 35,
}

SETUP_XXXTREME = {
    **SETUP_BASE,
    'pagamento_numero': 20, 'pagamento_zero': 20, 'pagamento_duzia': 3,
    'confianca_minima_entrada': 2.0, 'embalo_peso': 9, 'embalo_reforco': 5,
    'bloquear_alerta_zero_conf_alta': True, 'bloquear_anti_erro_zero_conf_baixa': True,
    'filtro_conf_baixa': 2.0, 'fadiga_duzia': 4,
    'ritmo_alternado_peso': 10, 'ritmo_alternado_forca': 10,
    'max_repeticoes_embalo': 4, 'confianca_maxima_segura': 3.3,
    'rodadas_verificacao_conf_alta': 5, 'pausa_pos_raio': 2, 'raio_alto_minimo': 100,
    'zero_termometro_max': 15, 'anti_erro_skip_discordancia': True,
    'ritmo_v_peso': 9, 'ritmo_v_forca': 9, 'ritmo_v_confirmacoes': 2,
    'usar_embalo': True, 'embalo_consecutivas_min': 3, 'embalo_janela': 6,
    'usar_ritmo_alternado': True, 'usar_ritmo_v': True,
    'usar_ritmo_ping_pong': True, 'usar_ritmo_binario': True,
    'usar_quebra_pos_zero': True, 'usar_exaustao_dominancia': True,
    'usar_mudanca_velocidade': True,
    'score_frequencia_peso': 40, 'score_streak_peso': 8,
    'score_markov_peso': 10, 'score_ml_peso': 35, 'score_anti_erro_peso': 25,
    'ml_janela_treino': 20, 'ml_atualizar_a_cada': 5,
}

SETUP_IMMERSIVE = {
    **SETUP_BASE,
    'pagamento_numero': 35, 'pagamento_zero': 35, 'pagamento_duzia': 2,
    'confianca_minima_entrada': 2.2, 'embalo_peso': 5, 'embalo_reforco': 2,
    'bloquear_alerta_zero_conf_alta': True, 'bloquear_anti_erro_zero_conf_baixa': True,
    'filtro_conf_baixa': 2.2, 'fadiga_duzia': 3,
    'ritmo_alternado_peso': 8, 'ritmo_alternado_forca': 8,
    'max_repeticoes_embalo': 3, 'confianca_maxima_segura': 3.1,
    'rodadas_verificacao_conf_alta': 5, 'pausa_pos_raio': 0, 'raio_alto_minimo': 0,
    'zero_termometro_max': 12, 'anti_erro_skip_discordancia': True,
    'ritmo_v_peso': 8, 'ritmo_v_forca': 8, 'ritmo_v_confirmacoes': 2,
    'usar_embalo': True, 'embalo_consecutivas_min': 2, 'embalo_janela': 4,
    'usar_ritmo_alternado': True, 'usar_ritmo_v': True,
    'usar_ritmo_ping_pong': False, 'usar_ritmo_binario': True,
    'usar_quebra_pos_zero': True, 'usar_exaustao_dominancia': False,
    'usar_mudanca_velocidade': False,
    'score_frequencia_peso': 45, 'score_streak_peso': 6,
    'score_markov_peso': 8, 'score_ml_peso': 30, 'score_anti_erro_peso': 20,
    'horario_bloqueio_inicio': 0, 'horario_bloqueio_fim': 12,
    'ml_janela_treino': 20, 'ml_atualizar_a_cada': 5,
}

SETUP_MEGA = {
    **SETUP_BASE,
    'pagamento_numero': 24, 'pagamento_zero': 24, 'pagamento_duzia': 2,
    'confianca_minima_entrada': 2.5, 'embalo_peso': 5, 'embalo_reforco': 2,
    'bloquear_alerta_zero_conf_alta': True, 'bloquear_anti_erro_zero_conf_baixa': True,
    'filtro_conf_baixa': 2.5, 'fadiga_duzia': 3,
    'ritmo_alternado_peso': 8, 'ritmo_alternado_forca': 8,
    'max_repeticoes_embalo': 3, 'confianca_maxima_segura': 3.1,
    'rodadas_verificacao_conf_alta': 5, 'pausa_pos_raio': 2, 'raio_alto_minimo': 150,
    'zero_termometro_max': 12, 'anti_erro_skip_discordancia': True,
    'ritmo_v_peso': 7, 'ritmo_v_forca': 7, 'ritmo_v_confirmacoes': 2,
    'usar_embalo': True, 'embalo_consecutivas_min': 2, 'embalo_janela': 4,
    'usar_ritmo_alternado': True, 'usar_ritmo_v': True,
    'usar_ritmo_ping_pong': False, 'usar_ritmo_binario': True,
    'usar_quebra_pos_zero': False, 'usar_exaustao_dominancia': False,
    'usar_mudanca_velocidade': False,
    'score_frequencia_peso': 45, 'score_streak_peso': 6,
    'score_markov_peso': 8, 'score_ml_peso': 30, 'score_anti_erro_peso': 20,
    'ml_janela_treino': 20, 'ml_atualizar_a_cada': 5,
}

ROLETA_CONFIGS = {
    'XXXtreme Lightning': SETUP_XXXTREME,
    'Immersive Roulette': SETUP_IMMERSIVE,
    'Mega Roulette': SETUP_MEGA,
}

# =============================
# CONFIGURAÇÕES GLOBAIS PERSISTENTES
# =============================
CONFIG_GLOBAL_PATH = "config_global.json"
PASTA_SESSOES = "sessoes_salvas"

def criar_pasta_sessoes():
    if not os.path.exists(PASTA_SESSOES):
        os.makedirs(PASTA_SESSOES)
    for roleta in ['xxxtreme_lightning', 'immersive_roulette', 'mega_roulette']:
        pasta_roleta = os.path.join(PASTA_SESSOES, roleta)
        if not os.path.exists(pasta_roleta):
            os.makedirs(pasta_roleta)

def get_pasta_sessao(api_name):
    safe_name = api_name.lower().replace(' ', '_')
    return os.path.join(PASTA_SESSOES, safe_name)

def salvar_config_global():
    config = {
        'telegram_token': st.session_state.get('telegram_token', ''),
        'telegram_chat_id': st.session_state.get('telegram_chat_id', ''),
        'telegram_token_alt': st.session_state.get('telegram_token_alt', ''),
        'telegram_chat_id_alt': st.session_state.get('telegram_chat_id_alt', ''),
        'modo_automatico': st.session_state.get('modo_automatico', True),
        'modo_agressivo': st.session_state.get('modo_agressivo', False),
        'janela_duzia_ai': st.session_state.get('janela_duzia_ai', 30),
        'api_selecionada': st.session_state.get('api_selecionada', 'XXXtreme Lightning'),
        'rodadas_por_sessao': st.session_state.get('rodadas_por_sessao', 10),
        'pausa_entre_sessoes': st.session_state.get('pausa_entre_sessoes', 5),
        'salvar_sessoes_auto': st.session_state.get('salvar_sessoes_auto', True),
    }
    try:
        with open(CONFIG_GLOBAL_PATH, 'w') as f: json.dump(config, f)
    except Exception as e: logging.error(f"Erro ao salvar config global: {e}")

def carregar_config_global():
    try:
        if os.path.exists(CONFIG_GLOBAL_PATH):
            with open(CONFIG_GLOBAL_PATH, 'r') as f: return json.load(f)
    except: pass
    return {}

def get_session_paths(api_name):
    safe_name = api_name.lower().replace(' ', '_')
    return {
        'session': f"session_data_{safe_name}.pkl",
        'historico': f"historico_roleta_{safe_name}.json",
        'performance': f"performance_bot_{safe_name}.json",
        'entradas': f"historico_entradas_{safe_name}.json",
        'performance_mesa': f"performance_mesa_{safe_name}.json",
        'performance_horario': f"performance_horario_{safe_name}.json",
        'sessao_controle': f"sessao_controle_{safe_name}.json",
        'historico_sessoes': f"historico_sessoes_{safe_name}.json",
    }

class GerenciadorSessoes:
    def __init__(self, api_name):
        self.api_name = api_name
        self.pasta_sessao = get_pasta_sessao(api_name)
        criar_pasta_sessoes()
    
    def salvar_sessao_encerrada(self, numero_sessao, dados_sessao, historico_entradas):
        try:
            data = data_brasilia()
            hora = formatar_hora_brasilia()
            nome_arquivo = f"sessao_{numero_sessao:03d}_{data}_{hora.replace(':', '-')}.json"
            caminho = os.path.join(self.pasta_sessao, nome_arquivo)
            sessao_completa = {
                'numero_sessao': numero_sessao, 'data': data,
                'hora_encerramento': hora, 'roleta': self.api_name,
                'estatisticas': dados_sessao, 'entradas': historico_entradas,
                'timestamp': timestamp_brasilia()
            }
            with open(caminho, 'w', encoding='utf-8') as f:
                json.dump(sessao_completa, f, indent=2, ensure_ascii=False)
            logging.info(f"💾 Sessão #{numero_sessao} salva em: {caminho}")
            self._atualizar_historico_sessoes(numero_sessao, dados_sessao, nome_arquivo)
            return caminho
        except Exception as e:
            logging.error(f"Erro ao salvar sessão: {e}")
            return None
    
    def _atualizar_historico_sessoes(self, numero_sessao, dados_sessao, nome_arquivo):
        paths = get_session_paths(self.api_name)
        historico_path = paths['historico_sessoes']
        historico = []
        if os.path.exists(historico_path):
            try:
                with open(historico_path, 'r') as f: historico = json.load(f)
            except: pass
        historico.append({
            'numero_sessao': numero_sessao, 'data': data_brasilia(),
            'hora': formatar_hora_brasilia(), 'arquivo': nome_arquivo,
            'acertos': dados_sessao.get('acertos', 0),
            'erros': dados_sessao.get('erros', 0),
            'taxa_acerto': dados_sessao.get('taxa_acerto', 0),
            'total_rodadas': dados_sessao.get('total_rodadas', 0),
        })
        if len(historico) > 100: historico = historico[-100:]
        try:
            with open(historico_path, 'w') as f: json.dump(historico, f, indent=2)
        except Exception as e: logging.error(f"Erro ao salvar histórico de sessões: {e}")
    
    def listar_sessoes(self):
        sessoes = []
        if os.path.exists(self.pasta_sessao):
            for arquivo in sorted(os.listdir(self.pasta_sessao), reverse=True):
                if arquivo.endswith('.json') and arquivo.startswith('sessao_'):
                    caminho = os.path.join(self.pasta_sessao, arquivo)
                    try:
                        with open(caminho, 'r') as f:
                            dados = json.load(f)
                            dados['arquivo'] = arquivo
                            dados['caminho'] = caminho
                            sessoes.append(dados)
                    except: pass
        return sessoes
    
    def listar_sessoes_do_dia(self, data=None):
        if data is None: data = data_brasilia()
        return [s for s in self.listar_sessoes() if s.get('data') == data]
    
    def consolidar_sessoes_dia(self, data=None):
        if data is None: data = data_brasilia()
        sessoes_dia = self.listar_sessoes_do_dia(data)
        if not sessoes_dia: return None
        consolidado = {
            'data': data, 'roleta': self.api_name,
            'total_sessoes': len(sessoes_dia), 'sessoes': [],
            'resumo_geral': {'total_acertos': 0, 'total_erros': 0, 'total_rodadas': 0}
        }
        for sessao in sessoes_dia:
            stats = sessao.get('estatisticas', {})
            consolidado['sessoes'].append({
                'numero': sessao.get('numero_sessao'),
                'hora': sessao.get('hora_encerramento'),
                'acertos': stats.get('acertos', 0),
                'erros': stats.get('erros', 0),
                'taxa': stats.get('taxa_acerto', 0),
                'entradas': sessao.get('entradas', [])
            })
            consolidado['resumo_geral']['total_acertos'] += stats.get('acertos', 0)
            consolidado['resumo_geral']['total_erros'] += stats.get('erros', 0)
            consolidado['resumo_geral']['total_rodadas'] += stats.get('total_rodadas', 0)
        total = consolidado['resumo_geral']['total_acertos'] + consolidado['resumo_geral']['total_erros']
        consolidado['resumo_geral']['taxa_geral'] = round(
            (consolidado['resumo_geral']['total_acertos'] / max(1, total)) * 100, 1
        )
        nome_arquivo = f"consolidado_{data}_{self.api_name.lower().replace(' ', '_')}.json"
        caminho = os.path.join(self.pasta_sessao, nome_arquivo)
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(consolidado, f, indent=2, ensure_ascii=False)
        return caminho
    
    def gerar_csv_sessao(self, dados_sessao):
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Rodada', 'Hora', 'Número', 'Raio', 'Dúzia Real', 'Dúzia Prevista', 
                         'Cobertura', 'Confiança', 'Gatilho', 'Zero', 'Anti-Erro', 
                         'Acerto Dúzia', 'Acerto Número', 'Acerto Zero', 'Status'])
        for e in dados_sessao.get('entradas', []):
            real = f"D{e.get('duzia_real',0)}" if e.get('duzia_real',0)!=0 else "0"
            prev = f"D{e.get('duzia_prevista','?')}"
            cob = f"D{e.get('duzia_sec_prevista','?')}" if e.get('duzia_sec_prevista') and e.get('duzia_sec_prevista') != e.get('duzia_prevista') else "-"
            zero = 'Sim' if e.get('incluir_zero') else 'Não'
            anti = 'Sim' if e.get('modo_anti_erro') else 'Não'
            duz = 'Sim' if e.get('acerto_duzia') else 'Não'
            num = 'Sim' if e.get('acerto_numero') else 'Não'
            zer = 'Sim' if e.get('acerto_zero') else 'Não'
            numero = e.get('numero', 0)
            raio = f"{e.get('multiplicador',0)}x" if e.get('eh_raio') else '-'
            writer.writerow([
                e.get('rodada'), e.get('hora'), numero, raio, real, prev, cob,
                f"{e.get('confianca',0):.1f}", e.get('gatilho','-') if e.get('gatilho') else '-',
                zero, anti, duz, num, zer, e.get('status','?')
            ])
        return output.getvalue()
    
    def get_download_link(self, conteudo, nome_arquivo, tipo='json'):
        if tipo == 'csv':
            b64 = base64.b64encode(conteudo.encode()).decode()
            mime = 'text/csv'
        else:
            b64 = base64.b64encode(conteudo.encode()).decode()
            mime = 'application/json'
        return f'<a href="data:{mime};base64,{b64}" download="{nome_arquivo}">📥 Baixar {nome_arquivo}</a>'

def salvar_sessao():
    try:
        if 'sistema' not in st.session_state or st.session_state.sistema is None: return False
        sis = st.session_state.sistema
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        paths = get_session_paths(api_name)
        performance_data = {
            'acertos_duzia': sis.acertos_duzia, 'erros_duzia': sis.erros_duzia,
            'acertos_numero': sis.acertos_numero, 'erros_numero': sis.erros_numero,
            'acertos_zero': sis.acertos_zero, 'erros_zero': sis.erros_zero
        }
        with open(paths['performance'], 'w') as f: json.dump(performance_data, f)
        with open(paths['entradas'], 'w') as f: json.dump(sis.historico_entradas, f)
        with open(paths['performance_mesa'], 'w') as f: json.dump(dict(sis.performance_por_mesa), f)
        with open(paths['performance_horario'], 'w') as f: json.dump(dict(sis.performance_por_horario), f)
        sessao_data = {
            'rodadas_na_sessao': sis.rodadas_na_sessao,
            'sessao_ativa': sis.sessao_ativa,
            'sessao_pausa_ate': sis.sessao_pausa_ate.isoformat() if sis.sessao_pausa_ate else None,
            'total_sessoes': sis.total_sessoes,
            'acertos_sessao': sis.acertos_sessao, 'erros_sessao': sis.erros_sessao,
        }
        with open(paths['sessao_controle'], 'w') as f: json.dump(sessao_data, f)
        session_data = {
            'historico_numeros': list(sis.historico_numeros),
            'entrada_ativa': sis.entrada_ativa,
            'acertos_duzia': sis.acertos_duzia, 'erros_duzia': sis.erros_duzia,
            'acertos_numero': sis.acertos_numero, 'erros_numero': sis.erros_numero,
            'acertos_zero': sis.acertos_zero, 'erros_zero': sis.erros_zero,
            'numero_rodada': sis.numero_rodada,
            'rodadas_na_sessao': sis.rodadas_na_sessao,
            'sessao_ativa': sis.sessao_ativa,
            'sessao_pausa_ate': sis.sessao_pausa_ate.isoformat() if sis.sessao_pausa_ate else None,
            'total_sessoes': sis.total_sessoes,
            'acertos_sessao': sis.acertos_sessao, 'erros_sessao': sis.erros_sessao,
        }
        with open(paths['session'], 'wb') as f: pickle.dump(session_data, f)
        salvar_config_global()
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar: {e}")
        return False

def carregar_dados_persistidos(api_name):
    paths = get_session_paths(api_name)
    dados = {}
    try:
        if os.path.exists(paths['session']):
            with open(paths['session'], 'rb') as f: 
                dados = pickle.load(f)
                if os.path.exists(paths['entradas']):
                    with open(paths['entradas'], 'r') as f2: dados['historico_entradas'] = json.load(f2)
                if os.path.exists(paths['performance_mesa']):
                    with open(paths['performance_mesa'], 'r') as f3: dados['performance_por_mesa'] = json.load(f3)
                if os.path.exists(paths['performance_horario']):
                    with open(paths['performance_horario'], 'r') as f4: dados['performance_por_horario'] = json.load(f4)
                if os.path.exists(paths['sessao_controle']):
                    with open(paths['sessao_controle'], 'r') as f5:
                        sessao_data = json.load(f5)
                        dados.update(sessao_data)
    except: pass
    return dados

def limpar_sessao():
    try:
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        paths = get_session_paths(api_name)
        for path in paths.values():
            if os.path.exists(path): os.remove(path)
        st.session_state.sistema.zerar()
        st.rerun()
    except Exception as e: logging.error(f"Erro: {e}")

def nova_sessao():
    try:
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        paths = get_session_paths(api_name)
        for path in paths.values():
            if os.path.exists(path): os.remove(path)
        if 'sistema' in st.session_state: st.session_state.sistema.zerar()
        st.session_state.historico = []
        logging.info(f"🆕 NOVA SESSÃO INICIADA - {api_name}"); return True
    except Exception as e: logging.error(f"Erro: {e}"); return False

def _selecionar_melhores_numeros(duzia, numeros_completos, quantidade=6):
    if duzia == 1: numeros_da_duzia = list(range(1, 13))
    elif duzia == 2: numeros_da_duzia = list(range(13, 25))
    else: numeros_da_duzia = list(range(25, 37))
    recentes = numeros_completos[-20:] if len(numeros_completos) >= 20 else numeros_completos
    freq = Counter([n for n in recentes if n in numeros_da_duzia])
    termos = [n % 10 for n in recentes[-15:] if n != 0]
    terminais_quentes = [t for t, f in Counter(termos).most_common(3) if f >= 2]
    pontuacao = {}
    for num in numeros_da_duzia:
        score = freq.get(num, 0) * 3
        if num % 10 in terminais_quentes: score += 2
        if num in recentes[-5:]: score += 1
        pontuacao[num] = score
    melhores = sorted(pontuacao.items(), key=lambda x: x[1], reverse=True)
    selecionados = [n for n, s in melhores[:quantidade] if s > 0]
    if len(selecionados) < quantidade:
        for num in numeros_da_duzia:
            if num not in selecionados:
                selecionados.append(num)
                if len(selecionados) >= quantidade: break
    return sorted(selecionados[:quantidade])

def enviar_previsao_auto(previsao):
    try:
        numeros = sorted(previsao.get('numeros_apostar', []))
        incluir_zero = previsao.get('incluir_zero', False)
        duzia_principal = previsao.get('duzia', 0)
        duzia_secundaria = previsao.get('duzia_secundaria', 0)
        d1n = [n for n in numeros if 1 <= n <= 12]
        d2n = [n for n in numeros if 13 <= n <= 24]
        d3n = [n for n in numeros if 25 <= n <= 36]
        prefixo = "⚠️🎯 " if incluir_zero else "🎯 "
        if d1n and d2n: msg = f"{prefixo}Entrada: D1 (1-12) | Cob: D2 (13-24)"
        elif d1n and d3n: msg = f"{prefixo}Entrada: D1 (1-12) | Cob: D3 (25-36)"
        elif d2n and d3n: msg = f"{prefixo}Entrada: D2 (13-24) | Cob: D3 (25-36)"
        elif d1n: msg = f"{prefixo}Entrada: D1 (1-12)"
        elif d2n: msg = f"{prefixo}Entrada: D2 (13-24)"
        elif d3n: msg = f"{prefixo}Entrada: D3 (25-36)"
        else: msg = f"{prefixo}Entrada: {numeros}"
        if incluir_zero: msg += " + 🟢 ZERO"
        numeros_completos = previsao.get('numeros_completos', [])
        melhores_principal = _selecionar_melhores_numeros(duzia_principal, numeros_completos, 6)
        if duzia_secundaria and duzia_secundaria != duzia_principal:
            melhores_secundaria = _selecionar_melhores_numeros(duzia_secundaria, numeros_completos, 6)
            melhores_str = " ".join(map(str, sorted(set(melhores_principal + melhores_secundaria))))
        else:
            melhores_str = " ".join(map(str, melhores_principal))
        st.toast(msg)
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"🔔 {msg}\n🔢 {melhores_str}", st.session_state.telegram_token, st.session_state.telegram_chat_id)
        if st.session_state.get('telegram_token_alt') and st.session_state.get('telegram_chat_id_alt'):
            msg_alt = f"🎯: {melhores_str}"
            if incluir_zero: msg_alt += " + 🟢 ZERO"
            enviar_telegram(msg_alt, st.session_state.telegram_token_alt, st.session_state.telegram_chat_id_alt)
        salvar_sessao()
    except Exception as e: logging.error(f"Erro: {e}")

def enviar_resultado_auto(numero_real, acerto_duzia, acerto_numero, acerto_zero, eh_raio=False, multiplicador=0):
    try:
        partes = []
        if acerto_zero: partes.append("✅ ZERO!")
        elif numero_real == 0: partes.append("🟢 ZERO (não apostado)")
        else:
            duzia_real = get_duzia(numero_real)
            if acerto_numero:
                if eh_raio: partes.append(f"⚡ RAIO {multiplicador}X! Nº {numero_real}")
                else: partes.append(f"🎯 Nº EXATO {numero_real}!")
            elif acerto_duzia: partes.append(f"✅ Green - D{duzia_real}")
            else: partes.append(f"❌ Nº {numero_real} (D{duzia_real})")
        msg = " | ".join(partes)
        st.toast(msg)
        if st.session_state.get('telegram_token') and st.session_state.get('telegram_chat_id'):
            enviar_telegram(f"📢 Resultado: {msg}", st.session_state.telegram_token, st.session_state.telegram_chat_id)
        if st.session_state.get('telegram_token_alt') and st.session_state.get('telegram_chat_id_alt'):
            if acerto_duzia or acerto_zero:
                if acerto_numero and eh_raio: msg_alt = f"⚡ GREEN RAIO {multiplicador}X! Nº {numero_real}"
                elif acerto_numero: msg_alt = f"🎯 GREEN! Nº {numero_real}"
                elif acerto_zero: msg_alt = "🟢 GREEN ZERO!"
                else: msg_alt = f"✅ GREEN - D{get_duzia(numero_real)}"
            else: msg_alt = f"❌ RED - Nº {numero_real}"
            enviar_telegram(msg_alt, st.session_state.telegram_token_alt, st.session_state.telegram_chat_id_alt)
        salvar_sessao()
    except Exception as e: logging.error(f"Erro: {e}")

def enviar_telegram(mensagem, token, chat_id):
    try:
        if not token or not chat_id: return
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                     json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}, timeout=10)
    except Exception as e: logging.error(f"Erro Telegram: {e}")

API_URLS = {
    'XXXtreme Lightning': "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest",
    'Immersive Roulette': "https://api.casinoscores.com/svc-evolution-game-events/api/immersiveroulette/latest",
    'Mega Roulette': "https://api.casinoscores.com/svc-evolution-game-events/api/megaroulette/latest",
}

HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_duzia(numero):
    if numero == 0: return 0
    elif 1 <= numero <= 12: return 1
    elif 13 <= numero <= 24: return 2
    else: return 3

def validar_numero(valor):
    try:
        num = int(valor); return 0 <= num <= 36
    except: return False

def fetch_XXXtreme_Lightning():
    try:
        url = API_URLS['XXXtreme Lightning']
        r = requests.get(url, headers=HEADERS, timeout=5)
        r.raise_for_status()
        d = r.json()
        gd = d.get("data", {})
        rs = gd.get("result", {})
        nm = rs.get("outcome", {}).get("number")
        ts = gd.get("startedAt")
        table_info = gd.get("table", {})
        table_id = table_info.get("id", "unknown")
        table_name = table_info.get("name", "Desconhecida")
        ln, lm = [], {}
        for item in rs.get('luckyNumbersList', []):
            n = item.get('number')
            if n is not None:
                ln.append(n)
                m = item.get('roundedMultiplier')
                if m is not None: lm[n] = m
        return {"number": nm, "timestamp": ts, "luckyNumbers": ln, "luckyMultipliers": lm, "table_id": table_id, "table_name": table_name}
    except Exception as e:
        logging.warning(f"❌ Erro XXXtreme: {e}")
        return None

def fetch_Immersive_Roulette():
    try:
        url = API_URLS['Immersive Roulette']
        r = requests.get(url, headers=HEADERS, timeout=5)
        r.raise_for_status()
        d = r.json()
        data = d.get("data", {})
        result = data.get("result", {})
        outcome = result.get("outcome", {})
        nm = outcome.get("number")
        ts = data.get("startedAt")
        table_info = data.get("table", {})
        table_id = table_info.get("id", "unknown")
        table_name = table_info.get("name", "Desconhecida")
        return {"number": nm, "timestamp": ts, "luckyNumbers": [], "luckyMultipliers": {}, "table_id": table_id, "table_name": table_name}
    except Exception as e:
        logging.warning(f"❌ Erro Immersive: {e}")
        return None

def fetch_Mega_Roulette():
    try:
        url = API_URLS['Mega Roulette']
        r = requests.get(url, headers=HEADERS, timeout=5)
        r.raise_for_status()
        d = r.json()
        gd = d.get("data", {})
        rs = gd.get("result", {})
        nm = rs.get("outcome", {}).get("number")
        ts = gd.get("startedAt")
        table_info = gd.get("table", {})
        table_id = table_info.get("id", "unknown")
        table_name = table_info.get("name", "Desconhecida")
        ln, lm = [], {}
        for item in rs.get('luckyNumbersList', []):
            n = item.get('number')
            if n is not None:
                ln.append(n)
                m = item.get('roundedMultiplier')
                if m is not None: lm[n] = m
        return {"number": nm, "timestamp": ts, "luckyNumbers": ln, "luckyMultipliers": lm, "table_id": table_id, "table_name": table_name}
    except Exception as e:
        logging.warning(f"❌ Erro Mega: {e}")
        return None

FETCH_FUNCTIONS = {
    'XXXtreme Lightning': fetch_XXXtreme_Lightning,
    'Immersive Roulette': fetch_Immersive_Roulette,
    'Mega Roulette': fetch_Mega_Roulette,
}

def fetch_latest_result():
    api_selecionada = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
    fetch_func = FETCH_FUNCTIONS.get(api_selecionada, fetch_XXXtreme_Lightning)
    return fetch_func()

# =============================
# 🧠 DUZIA AI V11.0.0 - ML ONLINE COM JANELA DE 20
# =============================
class DuziaAI:
    def __init__(self, window=30):
        self.historico = deque(maxlen=window)
        self.historico_completo = []
        self.numeros_completos = []
        self.ultimas_previsoes = []
        self.ultimos_resultados = []
        
        self.transicoes = defaultdict(Counter)
        
        self.erros_por_duzia = {1: 0, 2: 0, 3: 0}
        self.erros_consecutivos = 0
        self.ultima_duzia_errada = None
        self.entradas_consecutivas = 0
        self.ultimo_gatilho = None
        self.streak_ativo = None
        self.alerta_zero_ativo = False
        self.pausa_ate = None
        
        self.modo_anti_erro = False
        self.duzias_que_sairam = []
        self.consecutivos_amarelos = 0
        self.ultimo_resultado_duzia = None
        self.ultimo_resultado_numero = None
        self.ultima_confianca = 0
        self.ultima_previsao_duzia = None
        
        self.alertas_zero_disparados = 0
        self.zeros_previstos = 0
        self.acertos_consecutivos_mesma_duzia = 0
        self.ultima_duzia_acertada = None
        
        self.ritmo_alternado_par = None
        self.ritmo_alternado_contagem = 0
        self.ultimo_ritmo_alternado = None
        
        self.ritmo_v_padrao = None
        self.ritmo_v_contagem = 0
        self.ultimo_ritmo_v = None
        
        self.rodadas_desde_zero = 0
        self.ultimo_raio_alto = 0
        self.rodadas_pos_raio = 0
        self.em_pausa_pos_raio = False
        self.contagem_embalo_atual = 0
        self.duzia_embalo_atual = None
        
        # 🆕 ML Online
        self.modelo_ml = None
        self.ultimo_treino_ml = 0
        
        self.mesa_atual = None
        self.performance_por_mesa = defaultdict(lambda: {'acertos': 0, 'erros': 0})
        self.performance_por_horario = defaultdict(lambda: {'acertos': 0, 'erros': 0})
    
    def _get_config(self):
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        return ROLETA_CONFIGS.get(api_name, SETUP_XXXTREME).copy()
    
    def extrair_features_estado(self, janela=20):
        if len(self.historico_completo) < 4 or len(self.numeros_completos) < 4:
            return None
        
        numeros_janela = self.numeros_completos[-janela:]
        duzias_janela = [d for d in self.historico_completo[-janela:] if d != 0]
        ultimas_4 = self.historico_completo[-4:]
        
        terminais = [n % 10 for n in numeros_janela if n != 0]
        contagem_terminais = Counter(terminais).most_common(2)
        t1_quente = contagem_terminais[0][0] if len(contagem_terminais) > 0 else -1
        t2_quente = contagem_terminais[1][0] if len(contagem_terminais) > 1 else -1
        
        try:
            rodadas_sem_zero = numeros_janela[::-1].index(0)
        except ValueError:
            rodadas_sem_zero = janela
        
        duzia_dominante = Counter(duzias_janela).most_common(1)[0][0] if duzias_janela else -1
        
        gatilho_atual = self.detectar_gatilhos()
        tipo_gatilho = 0
        if gatilho_atual:
            mapa_gatilhos = {
                'RITMO_V': 1, 'RITMO_ALTERNADO': 2, 'EMBALO': 3,
                'RITMO_PING_PONG': 4, 'RITMO_BINARIO': 5,
                'QUEBRA_POS_ZERO': 6, 'EXAUSTAO_DOMINANCIA': 7, 'MUDANCA_VELOCIDADE': 8
            }
            tipo_gatilho = mapa_gatilhos.get(gatilho_atual['tipo'], 0)
        
        return [
            ultimas_4[0], ultimas_4[1], ultimas_4[2], ultimas_4[3],
            t1_quente, t2_quente, rodadas_sem_zero, duzia_dominante, tipo_gatilho
        ]
    
    def _treinar_ml_online(self):
        config = self._get_config()
        janela_treino = config.get('ml_janela_treino', 20)
        atualizar_a_cada = config.get('ml_atualizar_a_cada', 5)
        
        rodada_atual = len(self.historico_completo)
        if rodada_atual - self.ultimo_treino_ml < atualizar_a_cada:
            return False
        
        if len(self.historico_completo) < janela_treino + 4:
            return False
        
        try:
            X, y = [], []
            inicio = max(0, len(self.historico_completo) - janela_treino - 4)
            
            for i in range(inicio + 4, len(self.historico_completo)):
                hist_duzias_temp = self.historico_completo[:i]
                hist_numeros_temp = self.numeros_completos[:i]
                
                if len(hist_duzias_temp) < 4 or len(hist_numeros_temp) < 4:
                    continue
                
                numeros_janela = hist_numeros_temp[-janela_treino:]
                duzias_janela = [d for d in hist_duzias_temp[-janela_treino:] if d != 0]
                ultimas_4 = hist_duzias_temp[-4:]
                
                terminais = [n % 10 for n in numeros_janela if n != 0]
                contagem_terminais = Counter(terminais).most_common(2)
                t1 = contagem_terminais[0][0] if len(contagem_terminais) > 0 else -1
                t2 = contagem_terminais[1][0] if len(contagem_terminais) > 1 else -1
                
                try:
                    rodadas_sem_zero = numeros_janela[::-1].index(0)
                except ValueError:
                    rodadas_sem_zero = janela_treino
                
                duzia_dominante = Counter(duzias_janela).most_common(1)[0][0] if duzias_janela else -1
                
                features = [
                    ultimas_4[0], ultimas_4[1], ultimas_4[2], ultimas_4[3],
                    t1, t2, rodadas_sem_zero, duzia_dominante, 0
                ]
                
                target = self.historico_completo[i]
                if target in [1, 2, 3]:
                    X.append(features)
                    y.append(target)
            
            if len(X) < 10:
                return False
            
            self.modelo_ml = RandomForestClassifier(
                n_estimators=50, max_depth=5, random_state=42, n_jobs=-1
            )
            self.modelo_ml.fit(X, y)
            self.ultimo_treino_ml = rodada_atual
            
            logging.info(f"🧠 ML Treinado! Amostras: {len(X)} | Rodada: {rodada_atual}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Erro no treinamento ML: {e}")
            return False
    
    def adicionar(self, numero):
        d = get_duzia(numero)
        self.historico.append(d)
        self.historico_completo.append(d)
        self.numeros_completos.append(numero)
        
        if numero == 0:
            self.rodadas_desde_zero = 0
        else:
            self.rodadas_desde_zero += 1
        
        self._atualizar_ritmo_alternado(d)
        self._atualizar_ritmo_v(d)
        
        if d != 0:
            if d == self.duzia_embalo_atual:
                self.contagem_embalo_atual += 1
            else:
                self.duzia_embalo_atual = d
                self.contagem_embalo_atual = 1
        
        if d != 0:
            self.duzias_que_sairam.append(d)
            if len(self.duzias_que_sairam) > 10: self.duzias_que_sairam = self.duzias_que_sairam[-10:]
        
        if numero == 0 and self.alerta_zero_ativo: self.zeros_previstos += 1
        
        if len(self.historico_completo) >= 4:
            padrao = tuple(self.historico_completo[-4:-1])
            self.transicoes[padrao][d] += 1
        if len(self.historico_completo) > 200: self.historico_completo = self.historico_completo[-200:]
        if len(self.numeros_completos) > 200: self.numeros_completos = self.numeros_completos[-200:]
        
        if self.em_pausa_pos_raio:
            self.rodadas_pos_raio += 1
            if self.rodadas_pos_raio >= self._get_config()['pausa_pos_raio']:
                self.em_pausa_pos_raio = False
        
        self._treinar_ml_online()
    
    def _atualizar_ritmo_alternado(self, nova_duzia):
        if nova_duzia == 0: return
        u = list(self.historico)
        if len(u) < 3: return
        recentes = [d for d in u[-8:] if d != 0]
        if len(recentes) < 4:
            self.ritmo_alternado_par = None; self.ritmo_alternado_contagem = 0; return
        for inicio in range(len(recentes) - 3):
            seq = recentes[inicio:inicio+4]
            if seq[0] != seq[1] and seq[0] == seq[2] and seq[1] == seq[3]:
                par = tuple(sorted([seq[0], seq[1]]))
                if self.ritmo_alternado_par == par:
                    self.ritmo_alternado_contagem += 1
                else:
                    self.ritmo_alternado_par = par; self.ritmo_alternado_contagem = 1
                if self.ritmo_alternado_contagem >= 2: self.ultimo_ritmo_alternado = par
                return
        self.ritmo_alternado_par = None; self.ritmo_alternado_contagem = 0
    
    def _atualizar_ritmo_v(self, nova_duzia):
        if nova_duzia == 0: return
        u = list(self.historico)
        recentes = [d for d in u[-10:] if d != 0]
        if len(recentes) < 3: return
        ultimas_3 = recentes[-3:]
        if ultimas_3[0] == ultimas_3[2] and ultimas_3[0] != ultimas_3[1]:
            padrao_v = (ultimas_3[0], ultimas_3[1])
            if self.ritmo_v_padrao == padrao_v:
                self.ritmo_v_contagem += 1
            else:
                self.ritmo_v_padrao = padrao_v; self.ritmo_v_contagem = 1
            if self.ritmo_v_contagem >= 1: self.ultimo_ritmo_v = padrao_v
        else:
            if self.ritmo_v_padrao is not None:
                self.ritmo_v_padrao = None; self.ritmo_v_contagem = 0
    
    def registrar_previsao(self, duzia, confianca):
        self.ultimas_previsoes.append(duzia)
        self.ultima_previsao_duzia = duzia
        self.ultima_confianca = confianca
        if len(self.ultimas_previsoes) > 10: self.ultimas_previsoes = self.ultimas_previsoes[-10:]
    
    def registrar_resultado(self, duzia_real, acertou_duzia, acertou_numero, acertou_zero, mesa_id=None, eh_raio=False, multiplicador=0):
        self.ultimos_resultados.append({
            'duzia': duzia_real, 'acertou_duzia': acertou_duzia,
            'acertou_numero': acertou_numero, 'acertou_zero': acertou_zero
        })
        self.ultimo_resultado_duzia = acertou_duzia
        self.ultimo_resultado_numero = acertou_numero
        
        config = self._get_config()
        if eh_raio and multiplicador >= config['raio_alto_minimo'] and config['pausa_pos_raio'] > 0:
            self.em_pausa_pos_raio = True; self.rodadas_pos_raio = 0
            self.ultimo_raio_alto = multiplicador
        
        if mesa_id:
            self.mesa_atual = mesa_id
            if acertou_duzia or acertou_zero:
                self.performance_por_mesa[mesa_id]['acertos'] += 1
            else:
                self.performance_por_mesa[mesa_id]['erros'] += 1
        
        hora = datetime.now().hour
        turno = "manhã" if 6 <= hora < 12 else "tarde" if 12 <= hora < 18 else "noite"
        if acertou_duzia or acertou_zero:
            self.performance_por_horario[turno]['acertos'] += 1
        else:
            self.performance_por_horario[turno]['erros'] += 1
        
        if len(self.ultimos_resultados) > 20: self.ultimos_resultados = self.ultimos_resultados[-20:]
        
        if acertou_duzia and duzia_real != 0:
            if duzia_real == self.ultima_duzia_acertada: self.acertos_consecutivos_mesma_duzia += 1
            else: self.acertos_consecutivos_mesma_duzia = 1; self.ultima_duzia_acertada = duzia_real
        else: self.acertos_consecutivos_mesma_duzia = 0; self.ultima_duzia_acertada = None
        
        if acertou_duzia and not acertou_numero and not acertou_zero: self.consecutivos_amarelos += 1
        else: self.consecutivos_amarelos = 0

        if not acertou_duzia and not acertou_zero:
            self.erros_consecutivos += 1
            if duzia_real != 0: self.erros_por_duzia[duzia_real] += 1
            self.modo_anti_erro = True
            if self.erros_consecutivos >= 3:
                self.pausa_ate = hora_brasilia() + timedelta(minutes=5)
                self.modo_anti_erro = False
        else:
            self.erros_consecutivos = 0; self.modo_anti_erro = False
            self.erros_por_duzia = {1: 0, 2: 0, 3: 0}
            self.entradas_consecutivas = 0; self.pausa_ate = None
        
        if acertou_duzia or acertou_zero: self.entradas_consecutivas += 1
    
    def streak(self):
        if not self.historico: return 0, None
        last = self.historico[-1]; count = 0
        for d in reversed(self.historico):
            if d == last: count += 1
            else: break
        return count, last
    
    def frequencia(self): return Counter(self.historico)
    
    def _prever_markov(self):
        if len(self.historico_completo) < 3: return None
        padrao = tuple(self.historico_completo[-3:])
        if padrao in self.transicoes and self.transicoes[padrao]:
            return self.transicoes[padrao].most_common(1)[0]
        return None

    def _prever_ml(self):
        if not ML_DISPONIVEL or self.modelo_ml is None:
            return {1: 0.0, 2: 0.0, 3: 0.0}
        
        if len(self.historico_completo) < 4:
            return {1: 0.0, 2: 0.0, 3: 0.0}
        
        try:
            features = self.extrair_features_estado(janela=20)
            if not features:
                return {1: 0.0, 2: 0.0, 3: 0.0}
            
            probabilidades = self.modelo_ml.predict_proba([features])[0]
            
            config = self._get_config()
            ml_scores = {1: 0.0, 2: 0.0, 3: 0.0}
            for classe, prob in zip(self.modelo_ml.classes_, probabilidades):
                if classe in ml_scores:
                    ml_scores[classe] = float(prob) * config['score_ml_peso']
            
            return ml_scores
            
        except Exception as e:
            logging.error(f"❌ Erro na inferência ML: {e}")
            return {1: 0.0, 2: 0.0, 3: 0.0}
    
    def _get_outras_duzias(self, duzia): return [d for d in [1, 2, 3] if d != duzia]
    
    def _get_duzia_ausente(self):
        freq = self.frequencia()
        u = list(self.historico)[-6:]
        freq_recente = Counter([d for d in u if d != 0])
        for dz in [1, 2, 3]:
            if freq_recente.get(dz, 0) <= 1: return dz
        return min(freq, key=freq.get)
    
    def _garantir_cobertura_diferente(self, previsao):
        if previsao.get('duzia_secundaria') is None or previsao['duzia_secundaria'] == previsao['duzia']:
            outras = self._get_outras_duzias(previsao['duzia'])
            previsao['duzia_secundaria'] = outras[0] if outras else previsao['duzia']
        return previsao
    
    def detectar_alerta_zero(self):
        if len(self.historico) < 2: self.alerta_zero_ativo = False; return False
        u = list(self.historico)[-10:]
        nums = self.numeros_completos[-5:] if len(self.numeros_completos) >= 5 else self.numeros_completos
        if len(nums) >= 2 and nums[-1] == 0: self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        if len(nums) >= 3 and 0 in nums[-3:-1]: self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        if len(u) >= 3:
            ultimas_3 = u[-3:]
            if len(set(ultimas_3)) == 1 and ultimas_3[0] != 0: self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        if len(u) >= 5:
            ultimas_5 = u[-5:]
            trocas = sum(1 for i in range(1, len(ultimas_5)) if ultimas_5[i] != ultimas_5[i-1] and ultimas_5[i] != 0 and ultimas_5[i-1] != 0)
            if trocas >= 4: self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        if len(u) >= 3:
            ultimas_3 = u[-3:]
            duzias_presentes = set(d for d in ultimas_3 if d != 0)
            if len(duzias_presentes) == 3: self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        if len(u) >= 2:
            if u[-1] == u[-2] and u[-1] != 0:
                if 0 in u[-6:]: self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        if len(u) >= 2:
            if u[-1] == u[-2] and u[-1] != 0: self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        self.alerta_zero_ativo = False; return False
    
    def detectar_embalo(self):
        config = self._get_config()
        if not config.get('usar_embalo', True): return None
        u = list(self.historico)
        if len(u) < 3: return None
        janela = config.get('embalo_janela', 6)
        recentes = [d for d in u[-janela:] if d != 0]
        if len(recentes) < 2: return None
        ultima = recentes[-1]
        consecutivas = 0
        for d in reversed(recentes):
            if d == ultima: consecutivas += 1
            else: break
        consecutivas_min = config.get('embalo_consecutivas_min', 3)
        max_rep = config.get('max_repeticoes_embalo', 4)
        if consecutivas >= max_rep: return None
        if consecutivas >= consecutivas_min and ultima != 0:
            return {'tipo': 'EMBALO', 'duzia': ultima, 'forca': config['embalo_peso']}
        return None
    
    def detectar_ritmo_ping_pong(self):
        config = self._get_config()
        if not config.get('usar_ritmo_ping_pong', True): return None
        u = list(self.historico)[-6:]
        if len(u) < 4: return None
        pares = {}
        for i in range(1, len(u)):
            if u[i] != u[i-1] and u[i] != 0 and u[i-1] != 0:
                par = tuple(sorted([u[i], u[i-1]]))
                pares[par] = pares.get(par, 0) + 1
        if pares:
            par_principal = max(pares, key=pares.get)
            if pares[par_principal] >= 4:
                dz1, dz2 = par_principal
                proxima = dz2 if u[-1] == dz1 else dz1
                if proxima != 0: return {'tipo': 'RITMO_PING_PONG', 'duzia': proxima, 'forca': 9}
        return None
    
    def detectar_ritmo_alternado(self):
        config = self._get_config()
        if not config.get('usar_ritmo_alternado', True): return None
        u = list(self.historico)
        recentes = [d for d in u[-10:] if d != 0]
        if len(recentes) < 8: return None
        if 0 in u[-3:]: return None
        ultimas_8 = recentes[-8:]
        if len(ultimas_8) >= 8:
            if (ultimas_8[0] == ultimas_8[2] == ultimas_8[4] == ultimas_8[6] and 
                ultimas_8[1] == ultimas_8[3] == ultimas_8[5] == ultimas_8[7] and
                ultimas_8[0] != ultimas_8[1] and ultimas_8[0] != 0 and ultimas_8[1] != 0):
                return {'tipo': 'RITMO_ALTERNADO', 'duzia': ultimas_8[0],
                        'forca': config['ritmo_alternado_forca'], 'par': (ultimas_8[0], ultimas_8[1])}
        ultimas_6 = recentes[-6:]
        if len(ultimas_6) >= 6:
            if (ultimas_6[0] == ultimas_6[2] == ultimas_6[4] and 
                ultimas_6[1] == ultimas_6[3] == ultimas_6[5] and
                ultimas_6[0] != ultimas_6[1] and ultimas_6[0] != 0 and ultimas_6[1] != 0):
                return {'tipo': 'RITMO_ALTERNADO', 'duzia': ultimas_6[0],
                        'forca': config['ritmo_alternado_forca'] - 1, 'par': (ultimas_6[0], ultimas_6[1])}
        return None
    
    def detectar_ritmo_v(self):
        config = self._get_config()
        if not config.get('usar_ritmo_v', True): return None
        u = list(self.historico)
        recentes = [d for d in u[-10:] if d != 0]
        if len(recentes) < 3: return None
        if 0 in u[-2:]: return None
        ultimas_3 = recentes[-3:]
        if ultimas_3[0] == ultimas_3[2] and ultimas_3[0] != ultimas_3[1]:
            return {'tipo': 'RITMO_V', 'duzia': ultimas_3[0],
                    'forca': config['ritmo_v_forca'], 'padrao': (ultimas_3[0], ultimas_3[1])}
        if len(recentes) >= 5:
            ultimas_5 = recentes[-5:]
            if (ultimas_5[0] == ultimas_5[2] == ultimas_5[4] and 
                ultimas_5[1] == ultimas_5[3] and ultimas_5[0] != ultimas_5[1]):
                return {'tipo': 'RITMO_V', 'duzia': ultimas_5[1],
                        'forca': config['ritmo_v_forca'] + 1, 'padrao': (ultimas_5[0], ultimas_5[1])}
        if self.ritmo_v_contagem >= config['ritmo_v_confirmacoes'] and self.ultimo_ritmo_v is not None:
            duzia_base, duzia_meio = self.ultimo_ritmo_v
            ultima = recentes[-1]
            proxima = duzia_meio if ultima == duzia_base else (duzia_base if ultima == duzia_meio else None)
            if proxima:
                return {'tipo': 'RITMO_V', 'duzia': proxima,
                        'forca': config['ritmo_v_forca'], 'padrao': (duzia_base, duzia_meio)}
        return None
    
    def detectar_gatilhos(self):
        u = list(self.historico)
        config = self._get_config()
        
        if config.get('usar_ritmo_v', True):
            ritmo_v = self.detectar_ritmo_v()
            if ritmo_v: self.ultimo_gatilho = 'RITMO_V'; return ritmo_v
        
        if config.get('usar_ritmo_alternado', True):
            ritmo_alternado = self.detectar_ritmo_alternado()
            if ritmo_alternado: self.ultimo_gatilho = 'RITMO_ALTERNADO'; return ritmo_alternado
        
        if config.get('usar_embalo', True):
            embalo = self.detectar_embalo()
            if embalo: self.ultimo_gatilho = 'EMBALO'; return embalo
        
        if config.get('usar_ritmo_ping_pong', True):
            ping_pong = self.detectar_ritmo_ping_pong()
            if ping_pong: self.ultimo_gatilho = 'RITMO_PING_PONG'; return ping_pong
        
        if config.get('usar_ritmo_binario', True):
            if len(u) >= 4:
                ult_4 = [u[-1], u[-2], u[-3], u[-4]]
                if 0 not in ult_4:
                    if ult_4[0] == ult_4[2] and ult_4[1] == ult_4[3] and ult_4[0] != ult_4[1]:
                        self.ultimo_gatilho = 'RITMO_BINARIO'
                        return {'tipo': 'RITMO_BINARIO', 'duzia': ult_4[1], 'forca': 9}

        if config.get('usar_quebra_pos_zero', True):
            if 0 in u[-6:]:
                pos_zero = len(u) - 1 - u[::-1].index(0)
                depois_zero = u[pos_zero+1:]
                if len(depois_zero) >= 1 and depois_zero[-1] != 0:
                    self.ultimo_gatilho = 'QUEBRA_POS_ZERO'
                    return {'tipo': 'QUEBRA_POS_ZERO', 'duzia': depois_zero[-1], 'forca': 8}
        
        if config.get('usar_exaustao_dominancia', True):
            if len(u) >= 10:
                ultimas_10 = u[-10:]
                freq_10 = Counter([d for d in ultimas_10 if d != 0])
                if freq_10:
                    dom = freq_10.most_common(1)[0]
                    if dom[1] >= 7 and dom[0] != 0:
                        outras = self._get_outras_duzias(dom[0])
                        freq_outras = {d: self.frequencia().get(d, 0) for d in outras}
                        dz_emergente = max(freq_outras, key=freq_outras.get)
                        if dz_emergente != 0:
                            self.ultimo_gatilho = 'EXAUSTAO_DOMINANCIA'
                            return {'tipo': 'EXAUSTAO_DOMINANCIA', 'duzia': dz_emergente, 'forca': 7}
        
        if config.get('usar_mudanca_velocidade', True):
            if len(u) >= 8:
                freq_1 = Counter([d for d in u[-8:-4] if d != 0])
                freq_2 = Counter([d for d in u[-4:] if d != 0])
                if freq_1 and freq_2:
                    dom_1 = freq_1.most_common(1)[0]
                    dom_2 = freq_2.most_common(1)[0]
                    if dom_1[0] != dom_2[0] and dom_2[1] >= 3 and dom_2[0] != 0:
                        self.ultimo_gatilho = 'MUDANCA_VELOCIDADE'
                        return {'tipo': 'MUDANCA_VELOCIDADE', 'duzia': dom_2[0], 'forca': 6}
        
        return None
    
    def calcular_score(self):
        config = self._get_config()
        score = {1: 0, 2: 0, 3: 0}
        
        freq = self.frequencia()
        total = sum(freq.values())
        if total > 0:
            for d in score: score[d] = (freq.get(d, 0) / total) * config['score_frequencia_peso']
        
        streak_count, streak_d = self.streak()
        if streak_d and streak_d != 0: score[streak_d] += streak_count * config['score_streak_peso']
        
        markov = self._prever_markov()
        if markov and markov[0] != 0: score[markov[0]] += config['score_markov_peso']
        
        ml_scores = self._prever_ml()
        for d in score: score[d] += ml_scores.get(d, 0.0)
        
        gatilho = self.detectar_gatilhos()
        if gatilho and gatilho['duzia'] != 0: score[gatilho['duzia']] += gatilho['forca'] * 2
        
        if gatilho and gatilho['tipo'] == 'RITMO_V':
            score[gatilho['duzia']] += config['ritmo_v_peso']
            if 'padrao' in gatilho:
                for d in [1, 2, 3]:
                    if d not in gatilho['padrao']: score[d] *= 0.4
        
        if gatilho and gatilho['tipo'] == 'RITMO_ALTERNADO':
            score[gatilho['duzia']] += config['ritmo_alternado_peso']
            if 'par' in gatilho:
                for d in [1, 2, 3]:
                    if d not in gatilho['par']: score[d] *= 0.3
        
        if gatilho and gatilho['tipo'] in ('RITMO_PING_PONG', 'EMBALO'):
            score[gatilho['duzia']] += config['embalo_reforco']
        
        u = list(self.historico)
        if len(u) >= 2 and u[-1] == u[-2] and u[-1] != 0: score[u[-1]] += 30
        
        if self.modo_anti_erro and self.erros_consecutivos >= 1:
            if self.duzias_que_sairam:
                dz_real = self.duzias_que_sairam[-1]
                if dz_real != 0:
                    score[dz_real] += config['score_anti_erro_peso']
                    if self.ultimas_previsoes:
                        dz_errada = self.ultimas_previsoes[-1]
                        if dz_errada in score: score[dz_errada] *= 0.3
        
        if self.erros_consecutivos >= 2:
            dz_ausente = self._get_duzia_ausente()
            if dz_ausente != 0:
                score[dz_ausente] += 35
                for d in score:
                    if d != dz_ausente: score[d] *= 0.2
        
        if 0 in u[-4:]:
            pos_zero = len(u) - 1 - u[::-1].index(0)
            depois_zero = u[pos_zero+1:]
            if depois_zero and depois_zero[-1] != 0: score[depois_zero[-1]] += 15
        
        total_score = sum(score.values())
        if total_score > 0:
            for d in score: score[d] = (score[d] / total_score) * 100
        
        return score, gatilho
    
    def prever(self):
        if self.pausa_ate and hora_brasilia() < self.pausa_ate: 
            return {"entrar": False, "motivo": "⏸️ Pausa"}
        
        config = self._get_config()
        
        hora_atual = datetime.now().hour
        if 'horario_bloqueio_inicio' in config and 'horario_bloqueio_fim' in config:
            inicio = config['horario_bloqueio_inicio']
            fim = config['horario_bloqueio_fim']
            if inicio <= hora_atual < fim:
                return {"entrar": False, "motivo": f"⏸️ Horário bloqueado ({inicio:02d}:00-{fim:02d}:00)"}
        
        if self.em_pausa_pos_raio:
            return {"entrar": False, "motivo": f"⏸️ Pausa pós-raio ({self.ultimo_raio_alto}x)"}
        
        score, gatilho = self.calcular_score()
        ranking = sorted(score.items(), key=lambda x: x[1], reverse=True)
        d1, s1 = ranking[0]; d2, s2 = ranking[1]
        
        if d2 == d1:
            outras = self._get_outras_duzias(d1)
            d2 = ranking[2][0] if len(ranking) > 2 else outras[0]
        
        self.detectar_alerta_zero()
        confianca = min(3.5, max(1.0, s1 / max(1, s2) * 1.5))
        if self.alerta_zero_ativo and confianca >= 3.4: confianca = min(3.3, confianca)
        
        u_list = list(self.historico)
        if 0 in u_list[-3:]: confianca *= 0.5
        
        pode_entrar = s1 > 35 or gatilho is not None or self.modo_anti_erro
        
        if gatilho and gatilho['tipo'] in ('RITMO_V', 'RITMO_ALTERNADO'):
            pode_entrar = True
            confianca = min(3.5, confianca * 1.15)
        
        if confianca >= config['confianca_maxima_segura'] and not gatilho:
            recentes = [d for d in u_list[-config['rodadas_verificacao_conf_alta']:] if d != 0]
            if len(recentes) >= 5:
                freq_recente = Counter(recentes)
                if freq_recente.most_common(1)[0][0] != d1: confianca *= 0.7
        
        motivo = ""
        
        if self.modo_anti_erro and config['anti_erro_skip_discordancia']:
            if self.duzias_que_sairam:
                dz_real = self.duzias_que_sairam[-1]
                if dz_real != 0 and dz_real != d1 and dz_real != d2:
                    pode_entrar = False
                    motivo = "🚫 Anti-Erro: discordância"
        
        if self.ultimo_resultado_duzia == False and self.ultima_confianca >= 3.4:
            if d1 == self.ultima_previsao_duzia: d1 = d2; s1 = s2
        
        if config['bloquear_alerta_zero_conf_alta']:
            if gatilho and gatilho['tipo'] == 'EMBALO' and confianca >= 3.3 and self.alerta_zero_ativo:
                if gatilho['tipo'] not in ('RITMO_ALTERNADO', 'RITMO_V'):
                    pode_entrar = False; motivo = "🚫 EMBALO + Conf Alta + Zero"
        
        if config['bloquear_anti_erro_zero_conf_baixa']:
            if self.modo_anti_erro and self.alerta_zero_ativo and confianca < config['filtro_conf_baixa']:
                pode_entrar = False; motivo = f"🚫 Anti-Erro + Zero + Conf < {config['filtro_conf_baixa']}"
        
        if self.modo_anti_erro:
            if self.erros_consecutivos == 1: motivo = f"🔄 ANTI-ERRO" if not motivo else motivo
            else: motivo = f"🔄 ANTI-ERRO x{self.erros_consecutivos}" if not motivo else motivo
        else:
            if not motivo: motivo = "" if pode_entrar else f"Score baixo ({s1:.1f})"
        
        incluir_zero = self.alerta_zero_ativo
        if self.rodadas_desde_zero >= config['zero_termometro_max']:
            incluir_zero = True
            if not motivo: motivo = "🟢 Termômetro Zero"
        
        previsao = {
            "entrar": pode_entrar, "motivo": motivo, "score": score,
            "confianca": round(confianca, 2), "duzia": d1, "duzia_secundaria": d2,
            "gatilho_ativo": gatilho['tipo'] if gatilho else None,
            "incluir_zero": incluir_zero, "modo_anti_erro": self.modo_anti_erro,
            "numeros_completos": list(self.numeros_completos)
        }
        
        if pode_entrar: previsao = self._balancear(previsao)
        self.ultimo_gatilho = None
        return previsao
    
    def _balancear(self, previsao):
        config = self._get_config()
        u = list(self.historico)
        if self.alerta_zero_ativo: previsao['incluir_zero'] = True

        if self.acertos_consecutivos_mesma_duzia >= config['fadiga_duzia'] and self.ultima_duzia_acertada is not None:
            duzia_fadigada = self.ultima_duzia_acertada
            if previsao['duzia'] == duzia_fadigada:
                outras = self._get_outras_duzias(duzia_fadigada)
                freq_outras = {d: u.count(d) for d in outras}
                duzia_mudanca = max(freq_outras, key=freq_outras.get)
                previsao['duzia'] = duzia_mudanca
        
        if self.consecutivos_amarelos >= 2:
            d_prim = previsao['duzia']; d_sec = previsao['duzia_secundaria']
            previsao['duzia'] = d_sec; previsao['duzia_secundaria'] = d_prim
        
        conf = previsao.get('confianca', 0); gat = previsao.get('gatilho_ativo')
        if conf >= 3.4 and not gat and not self.modo_anti_erro:
            if self.duzias_que_sairam:
                ultima_real = self.duzias_que_sairam[-1]
                if ultima_real != 0 and ultima_real != previsao['duzia']: previsao['duzia'] = ultima_real
        
        for dz, erros in self.erros_por_duzia.items():
            if erros >= 3 and previsao['duzia'] == dz:
                outras = self._get_outras_duzias(dz)
                freq_outras = {d: u.count(d) for d in outras}
                previsao['duzia'] = max(freq_outras, key=freq_outras.get)
                return self._garantir_cobertura_diferente(previsao)
        
        if self.modo_anti_erro and self.ultimas_previsoes:
            dz_errada = self.ultimas_previsoes[-1]
            if previsao['duzia'] == dz_errada:
                outras = self._get_outras_duzias(dz_errada)
                freq_outras = {d: u.count(d) for d in outras}
                previsao['duzia'] = max(freq_outras, key=freq_outras.get)
        
        if len(u) >= 2 and u[-1] == u[-2] and u[-1] != 0:
            if previsao['duzia'] != u[-1]: previsao['duzia'] = u[-1]
        
        return self._garantir_cobertura_diferente(previsao)

# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaBot:
    def __init__(self):
        janela = st.session_state.get('janela_duzia_ai', 30)
        self.duzia_ai = DuziaAI(window=janela)
        self.historico_numeros = deque(maxlen=200)
        self.entrada_ativa = None
        self.historico_entradas = []
        
        self.acertos_duzia = 0; self.erros_duzia = 0
        self.acertos_numero = 0; self.erros_numero = 0
        self.acertos_zero = 0; self.erros_zero = 0
        
        self.ultimo_numero = None
        self.sinais_grafico = []
        self.numero_rodada = 0
        
        self.performance_por_mesa = defaultdict(lambda: {'acertos': 0, 'erros': 0})
        self.performance_por_horario = defaultdict(lambda: {'acertos': 0, 'erros': 0})
        
        self.rodadas_por_sessao = st.session_state.get('rodadas_por_sessao', 10)
        self.pausa_entre_sessoes = st.session_state.get('pausa_entre_sessoes', 5)
        self.rodadas_na_sessao = 0
        self.sessao_ativa = False
        self.sessao_pausa_ate = None
        self.total_sessoes = 0
        self.acertos_sessao = 0
        self.erros_sessao = 0
        
        self.gerenciador_sessoes = GerenciadorSessoes(
            st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        )
    
    def iniciar_sessao(self):
        if self.sessao_pausa_ate and hora_brasilia() < self.sessao_pausa_ate: return False
        self.sessao_ativa = True
        self.rodadas_na_sessao = 0
        self.acertos_sessao = 0; self.erros_sessao = 0
        self.total_sessoes += 1
        self.sessao_pausa_ate = None
        salvar_sessao()
        return True
    
    def _encerrar_sessao(self):
        self.sessao_ativa = False
        self.sessao_pausa_ate = hora_brasilia() + timedelta(minutes=self.pausa_entre_sessoes)
        taxa = (self.acertos_sessao / max(1, self.acertos_sessao + self.erros_sessao)) * 100
        
        if st.session_state.get('salvar_sessoes_auto', True):
            entradas_sessao = []
            inicio = len(self.historico_entradas) - self.rodadas_na_sessao
            if inicio < 0: inicio = 0
            entradas_sessao = self.historico_entradas[inicio:]
            dados_sessao = {
                'acertos': self.acertos_sessao, 'erros': self.erros_sessao,
                'taxa_acerto': round(taxa, 1), 'total_rodadas': self.rodadas_na_sessao,
                'rodadas_por_sessao': self.rodadas_por_sessao,
            }
            self.gerenciador_sessoes.salvar_sessao_encerrada(self.total_sessoes, dados_sessao, entradas_sessao)
        
        self.entrada_ativa = None
        salvar_sessao()
    
    def pode_processar(self):
        if not self.sessao_ativa:
            if self.sessao_pausa_ate and hora_brasilia() >= self.sessao_pausa_ate:
                self.sessao_pausa_ate = None; self.sessao_ativa = False
                salvar_sessao()
            return False
        if self.rodadas_na_sessao >= self.rodadas_por_sessao:
            self._encerrar_sessao(); return False
        return True
    
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data.get('number')
            lucky_numbers = numero_data.get('luckyNumbers', [])
            lucky_multipliers = numero_data.get('luckyMultipliers', {})
            table_id = numero_data.get('table_id', 'unknown')
            table_name = numero_data.get('table_name', 'Desconhecida')
        else:
            nr = numero_data; lucky_numbers = []; lucky_multipliers = {}
            table_id = 'unknown'; table_name = 'Desconhecida'
        
        if nr is None or not validar_numero(nr): return
        
        self.numero_rodada += 1
        self.duzia_ai.adicionar(nr)
        self.historico_numeros.append(nr)
        self.ultimo_numero = nr
        
        if not self.pode_processar():
            salvar_sessao(); return
        
        eh_raio = nr in lucky_numbers
        multiplicador = lucky_multipliers.get(nr, 0) if eh_raio else 0
        
        if self.entrada_ativa:
            duzia_real = get_duzia(nr)
            duzia_prevista = self.entrada_ativa.get('duzia_prevista')
            duzia_sec_prevista = self.entrada_ativa.get('duzia_sec_prevista')
            numeros_apostados = self.entrada_ativa.get('numeros_apostar', [])
            incluir_zero = self.entrada_ativa.get('incluir_zero', False)
            
            acerto_primaria = (duzia_real == duzia_prevista) if duzia_prevista and nr != 0 else False
            acerto_secundaria = (duzia_real == duzia_sec_prevista) if duzia_sec_prevista and nr != 0 else False
            acerto_numero_exato = nr in numeros_apostados if nr != 0 else False
            acerto_zero = (nr == 0 and incluir_zero)
            
            if acerto_zero: acerto_primaria = True
            
            if acerto_numero_exato: self.acertos_numero += 1
            elif nr != 0: self.erros_numero += 1
            
            if acerto_zero: self.acertos_zero += 1
            elif nr == 0: self.erros_zero += 1
            
            if acerto_primaria: self.acertos_duzia += 1
            elif acerto_secundaria: self.acertos_duzia += 0.5
            elif nr != 0: self.erros_duzia += 1
            
            acertou_duzia = acerto_primaria or acerto_secundaria
            
            self.rodadas_na_sessao += 1
            if acertou_duzia or acerto_zero: self.acertos_sessao += 1
            else: self.erros_sessao += 1
            
            self.duzia_ai.registrar_resultado(duzia_real, acertou_duzia, acerto_numero_exato, acerto_zero, table_id, eh_raio, multiplicador)
            
            if acertou_duzia or acerto_zero: self.performance_por_mesa[table_id]['acertos'] += 1
            else: self.performance_por_mesa[table_id]['erros'] += 1
            
            hora = datetime.now().hour
            turno = "manhã" if 6 <= hora < 12 else "tarde" if 12 <= hora < 18 else "noite"
            if acertou_duzia or acerto_zero: self.performance_por_horario[turno]['acertos'] += 1
            else: self.performance_por_horario[turno]['erros'] += 1
            
            if acerto_zero: status_visual = '🟢'
            elif acerto_numero_exato and eh_raio: status_visual = '⚡'
            elif acerto_numero_exato: status_visual = '🎯'
            elif acerto_primaria: status_visual = '✅'
            elif acerto_secundaria: status_visual = '🟡'
            else: status_visual = '❌'
            
            self.historico_entradas.append({
                'rodada': self.numero_rodada, 'hora': formatar_hora_brasilia(),
                'numero': nr, 'duzia_real': duzia_real if nr != 0 else 0,
                'duzia_prevista': duzia_prevista, 'duzia_sec_prevista': duzia_sec_prevista,
                'acerto_duzia': acerto_primaria or acerto_secundaria,
                'acerto_numero': acerto_numero_exato, 'acerto_zero': acerto_zero,
                'eh_raio': eh_raio, 'multiplicador': multiplicador,
                'status': status_visual,
                'confianca': self.entrada_ativa.get('confianca', 0),
                'gatilho': self.entrada_ativa.get('gatilho_ativo', None),
                'modo_anti_erro': self.entrada_ativa.get('modo_anti_erro', False),
                'incluir_zero': incluir_zero,
                'table_id': table_id, 'table_name': table_name
            })
            if len(self.historico_entradas) > 50: self.historico_entradas = self.historico_entradas[-50:]
            enviar_resultado_auto(nr, acertou_duzia, acerto_numero_exato, acerto_zero, eh_raio, multiplicador)
            self.entrada_ativa = None
            
            if not self.pode_processar():
                salvar_sessao(); return
        
        if self.sessao_ativa and self.rodadas_na_sessao < self.rodadas_por_sessao:
            previsao = self.duzia_ai.prever()
            
            if previsao['entrar']:
                duzia_map = {1: list(range(1,13)), 2: list(range(13,25)), 3: list(range(25,37))}
                numeros_principais = duzia_map.get(previsao['duzia'], [])
                numeros_secundarios = duzia_map.get(previsao.get('duzia_secundaria', previsao['duzia']), [])
                
                if st.session_state.get('modo_agressivo', False) and previsao.get('duzia_secundaria') and previsao['duzia_secundaria'] != previsao['duzia']:
                    numeros_apostar = list(set(numeros_principais + numeros_secundarios))
                else:
                    numeros_apostar = numeros_principais
                
                if previsao.get('incluir_zero', False) and 0 not in numeros_apostar:
                    numeros_apostar = [0] + numeros_apostar
                
                self.entrada_ativa = {
                    'numeros_apostar': numeros_apostar,
                    'duzia_prevista': previsao['duzia'],
                    'duzia_sec_prevista': previsao.get('duzia_secundaria'),
                    'confianca': previsao.get('confianca', 0),
                    'gatilho_ativo': previsao.get('gatilho_ativo'),
                    'modo_anti_erro': previsao.get('modo_anti_erro', False),
                    'incluir_zero': previsao.get('incluir_zero', False)
                }
                
                self.duzia_ai.registrar_previsao(previsao['duzia'], previsao['confianca'])
                idx_atual = len(self.historico_numeros) - 1
                self.sinais_grafico.append((idx_atual, previsao['duzia']))
                enviar_previsao_auto({
                    'numeros_apostar': numeros_apostar,
                    'incluir_zero': previsao.get('incluir_zero', False),
                    'duzia': previsao['duzia'],
                    'duzia_secundaria': previsao.get('duzia_secundaria', previsao['duzia']),
                    'numeros_completos': list(self.historico_numeros)
                })
    
    def zerar(self):
        self.acertos_duzia = 0; self.erros_duzia = 0
        self.acertos_numero = 0; self.erros_numero = 0
        self.acertos_zero = 0; self.erros_zero = 0
        self.historico_entradas = []; self.historico_numeros.clear()
        self.entrada_ativa = None; self.ultimo_numero = None
        self.sinais_grafico = []; self.numero_rodada = 0
        self.rodadas_na_sessao = 0; self.sessao_ativa = False
        self.sessao_pausa_ate = None; self.total_sessoes = 0
        self.acertos_sessao = 0; self.erros_sessao = 0
        janela = st.session_state.get('janela_duzia_ai', 30)
        self.duzia_ai = DuziaAI(window=janela)
        salvar_sessao()

def salvar_resultado_em_arquivo(historico, caminho):
    try:
        with open(caminho, "w", encoding='utf-8') as f: json.dump(historico, f, indent=2)
    except Exception as e: logging.error(f"Erro: {e}")

def exportar_historico_csv(historico_entradas, caminho="export_roleta.csv"):
    import csv
    try:
        with open(caminho, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Rod','Hora','Nº','Raio','Real','Prev','Cob','Conf','Gat','Z','🔄','Mesa','Duz','Num','Zer','St'])
            for e in historico_entradas:
                real = f"D{e.get('duzia_real',0)}" if e.get('duzia_real',0)!=0 else "0"
                prev = f"D{e.get('duzia_prevista','?')}"
                cob = f"D{e.get('duzia_sec_prevista','?')}" if e.get('duzia_sec_prevista') and e.get('duzia_sec_prevista') != e.get('duzia_prevista') else "-"
                zero = '🟢' if e.get('incluir_zero') else '-'
                anti = '🔄' if e.get('modo_anti_erro') else '-'
                duz = '✅' if e.get('acerto_duzia') else '❌'
                num = '✅' if e.get('acerto_numero') else '-'
                zer = '✅' if e.get('acerto_zero') else '-'
                raio = f"⚡{e.get('multiplicador',0)}x" if e.get('eh_raio') else '-'
                mesa = e.get('table_name', '?')[:15] if e.get('table_name') else '?'
                writer.writerow([e.get('rodada'), e.get('hora'), e.get('numero'), raio, real, prev, cob, f"{e.get('confianca',0):.1f}", e.get('gatilho','-') if e.get('gatilho') else '-', zero, anti, mesa, duz, num, zer, e.get('status','?')])
        return True
    except Exception as e: logging.error(f"Erro CSV: {e}"); return False

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎰 DuziaAI V11.0.0 - ML Online", layout="wide")
st.title("🎰 DuziaAI V11.0.0 - ML ONLINE COM JANELA DE 20 (BRT)")

config_global = carregar_config_global()

if "api_selecionada" not in st.session_state:
    st.session_state.api_selecionada = config_global.get('api_selecionada', 'XXXtreme Lightning')
if "ultima_api" not in st.session_state:
    st.session_state.ultima_api = st.session_state.api_selecionada
if "telegram_token" not in st.session_state:
    st.session_state.telegram_token = config_global.get('telegram_token', '')
if "telegram_chat_id" not in st.session_state:
    st.session_state.telegram_chat_id = config_global.get('telegram_chat_id', '')
if "telegram_token_alt" not in st.session_state:
    st.session_state.telegram_token_alt = config_global.get('telegram_token_alt', '')
if "telegram_chat_id_alt" not in st.session_state:
    st.session_state.telegram_chat_id_alt = config_global.get('telegram_chat_id_alt', '')
if "rodadas_por_sessao" not in st.session_state:
    st.session_state.rodadas_por_sessao = config_global.get('rodadas_por_sessao', 10)
if "pausa_entre_sessoes" not in st.session_state:
    st.session_state.pausa_entre_sessoes = config_global.get('pausa_entre_sessoes', 5)
if "salvar_sessoes_auto" not in st.session_state:
    st.session_state.salvar_sessoes_auto = config_global.get('salvar_sessoes_auto', True)

if st.session_state.api_selecionada != st.session_state.ultima_api:
    st.session_state.ultima_api = st.session_state.api_selecionada
    st.session_state.sistema = SistemaBot()
    dados = carregar_dados_persistidos(st.session_state.api_selecionada)
    if dados:
        sis = st.session_state.sistema
        for n in dados.get('historico_numeros', []):
            sis.duzia_ai.adicionar(n); sis.historico_numeros.append(n)
        sis.numero_rodada = dados.get('numero_rodada', len(dados.get('historico_numeros', [])))
        sis.acertos_duzia = dados.get('acertos_duzia', 0)
        sis.erros_duzia = dados.get('erros_duzia', 0)
        sis.acertos_numero = dados.get('acertos_numero', 0)
        sis.erros_numero = dados.get('erros_numero', 0)
        sis.acertos_zero = dados.get('acertos_zero', 0)
        sis.erros_zero = dados.get('erros_zero', 0)
        sis.entrada_ativa = dados.get('entrada_ativa', None)
        sis.historico_entradas = dados.get('historico_entradas', [])
        sis.rodadas_na_sessao = dados.get('rodadas_na_sessao', 0)
        sis.sessao_ativa = dados.get('sessao_ativa', False)
        sis.total_sessoes = dados.get('total_sessoes', 0)
        sis.acertos_sessao = dados.get('acertos_sessao', 0)
        sis.erros_sessao = dados.get('erros_sessao', 0)
        if dados.get('sessao_pausa_ate'):
            sis.sessao_pausa_ate = datetime.fromisoformat(dados['sessao_pausa_ate'])
        if 'performance_por_mesa' in dados:
            for k, v in dados['performance_por_mesa'].items():
                sis.performance_por_mesa[k] = v
                sis.duzia_ai.performance_por_mesa[k] = v
        if 'performance_por_horario' in dados:
            for k, v in dados['performance_por_horario'].items():
                sis.performance_por_horario[k] = v
                sis.duzia_ai.performance_por_horario[k] = v
        paths = get_session_paths(st.session_state.api_selecionada)
        if os.path.exists(paths['historico']):
            with open(paths['historico'], 'r') as f: st.session_state.historico = json.load(f)
    else:
        st.session_state.historico = []
    st.rerun()

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()
    dados = carregar_dados_persistidos(st.session_state.api_selecionada)
    if dados:
        sis = st.session_state.sistema
        for n in dados.get('historico_numeros', []):
            sis.duzia_ai.adicionar(n); sis.historico_numeros.append(n)
        sis.numero_rodada = dados.get('numero_rodada')
        sis.acertos_duzia = dados.get('acertos_duzia', 0)
        sis.erros_duzia = dados.get('erros_duzia', 0)
        sis.acertos_numero = dados.get('acertos_numero', 0)
        sis.erros_numero = dados.get('erros_numero', 0)
        sis.acertos_zero = dados.get('acertos_zero', 0)
        sis.erros_zero = dados.get('erros_zero', 0)
        sis.entrada_ativa = dados.get('entrada_ativa')
        sis.historico_entradas = dados.get('historico_entradas', [])
        sis.rodadas_na_sessao = dados.get('rodadas_na_sessao', 0)
        sis.sessao_ativa = dados.get('sessao_ativa', False)
        sis.total_sessoes = dados.get('total_sessoes', 0)
        sis.acertos_sessao = dados.get('acertos_sessao', 0)
        sis.erros_sessao = dados.get('erros_sessao', 0)
        if dados.get('sessao_pausa_ate'):
            sis.sessao_pausa_ate = datetime.fromisoformat(dados['sessao_pausa_ate'])
        if 'performance_por_mesa' in dados:
            for k, v in dados['performance_por_mesa'].items():
                sis.performance_por_mesa[k] = v
                sis.duzia_ai.performance_por_mesa[k] = v
        if 'performance_por_horario' in dados:
            for k, v in dados['performance_por_horario'].items():
                sis.performance_por_horario[k] = v
                sis.duzia_ai.performance_por_horario[k] = v
        paths = get_session_paths(st.session_state.api_selecionada)
        if os.path.exists(paths['historico']):
            with open(paths['historico'], 'r') as f: st.session_state.historico = json.load(f)

if "modo_automatico" not in st.session_state:
    st.session_state.modo_automatico = config_global.get('modo_automatico', True)
if "modo_agressivo" not in st.session_state:
    st.session_state.modo_agressivo = config_global.get('modo_agressivo', False)
if "janela_duzia_ai" not in st.session_state:
    st.session_state.janela_duzia_ai = config_global.get('janela_duzia_ai', 30)
if "historico" not in st.session_state: st.session_state.historico = []

# =============================
# SIDEBAR COMPLETA
# =============================
with st.sidebar:
    st.markdown("## ⚙️ V11.0.0 - ML ONLINE")
    sis = st.session_state.sistema
    
    st.markdown("### 📊 Status da Sessão")
    if sis.sessao_ativa:
        st.success(f"🟢 Sessão #{sis.total_sessoes} ATIVA")
        st.progress(sis.rodadas_na_sessao / sis.rodadas_por_sessao)
        st.caption(f"Rodadas: {sis.rodadas_na_sessao}/{sis.rodadas_por_sessao}")
        st.caption(f"Acertos: {sis.acertos_sessao} | Erros: {sis.erros_sessao}")
        if sis.acertos_sessao + sis.erros_sessao > 0:
            taxa = (sis.acertos_sessao / (sis.acertos_sessao + sis.erros_sessao)) * 100
            st.caption(f"Taxa: {taxa:.0f}%")
    elif sis.sessao_pausa_ate and hora_brasilia() < sis.sessao_pausa_ate:
        tempo_restante = (sis.sessao_pausa_ate - hora_brasilia()).seconds
        minutos = tempo_restante // 60
        segundos = tempo_restante % 60
        st.warning(f"⏸️ Pausa: {minutos:02d}:{segundos:02d}")
        if sis.total_sessoes > 0:
            st.caption(f"Sessão #{sis.total_sessoes} encerrada")
            if sis.acertos_sessao + sis.erros_sessao > 0:
                taxa = (sis.acertos_sessao / (sis.acertos_sessao + sis.erros_sessao)) * 100
                st.caption(f"Resultado: {sis.acertos_sessao}✅ / {sis.erros_sessao}❌ ({taxa:.0f}%)")
    else:
        st.info("⚪ Nenhuma sessão ativa")
        if sis.total_sessoes > 0:
            st.caption(f"Total de sessões: {sis.total_sessoes}")
    
    botao_desabilitado = sis.sessao_ativa or (sis.sessao_pausa_ate and hora_brasilia() < sis.sessao_pausa_ate)
    if botao_desabilitado:
        st.button("🚀 INICIAR SESSÃO", use_container_width=True, disabled=True)
    else:
        if st.button("🚀 INICIAR SESSÃO", use_container_width=True, type="primary"):
            if sis.iniciar_sessao(): st.success(f"✅ Sessão #{sis.total_sessoes} iniciada!"); st.rerun()
    
    st.markdown("---")
    if st.button("🆕 RESET TOTAL", use_container_width=True):
        if nova_sessao(): st.success("✅ Reset completo!"); st.rerun()
    
    st.markdown("---")
    
    # ⏱️ CONFIGURAÇÕES DE SESSÃO
    st.markdown("### ⏱️ Configurações da Sessão")
    rodadas = st.number_input("Rodadas por sessão:", min_value=5, max_value=30, 
                               value=st.session_state.rodadas_por_sessao, step=5)
    pausa = st.number_input("Pausa entre sessões (min):", min_value=1, max_value=30,
                            value=st.session_state.pausa_entre_sessoes, step=1)
    
    if rodadas != st.session_state.rodadas_por_sessao:
        st.session_state.rodadas_por_sessao = rodadas
        sis.rodadas_por_sessao = rodadas
        salvar_sessao()
    if pausa != st.session_state.pausa_entre_sessoes:
        st.session_state.pausa_entre_sessoes = pausa
        sis.pausa_entre_sessoes = pausa
        salvar_sessao()
    
    st.markdown("---")
    
    # 💾 DOWNLOAD DE SESSÕES
    st.markdown("### 💾 Download de Sessões")
    st.session_state.salvar_sessoes_auto = st.checkbox(
        "💾 Salvar sessões automaticamente", 
        value=st.session_state.salvar_sessoes_auto
    )
    
    with st.expander("📥 BAIXAR SESSÕES", expanded=False):
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        gerenciador = GerenciadorSessoes(api_name)
        sessoes = gerenciador.listar_sessoes()
        
        if sessoes:
            st.caption(f"📂 {len(sessoes)} sessões disponíveis")
            st.markdown("#### 📥 Sessão Específica")
            sessao_opcoes = [f"Sessão #{s.get('numero_sessao', '?')} - {s.get('data', '?')} {s.get('hora_encerramento', '?')}" for s in sessoes[:20]]
            if sessao_opcoes:
                sessao_selecionada = st.selectbox("Selecionar sessão:", sessao_opcoes, key="select_sessao")
                if sessao_selecionada:
                    idx = sessao_opcoes.index(sessao_selecionada)
                    if idx < len(sessoes):
                        sessao = sessoes[idx]
                        col1, col2 = st.columns(2)
                        with col1:
                            conteudo_json = json.dumps(sessao, indent=2, ensure_ascii=False)
                            st.markdown(gerenciador.get_download_link(conteudo_json, f"sessao_{sessao.get('numero_sessao', '?')}.json", 'json'), unsafe_allow_html=True)
                        with col2:
                            conteudo_csv = gerenciador.gerar_csv_sessao(sessao)
                            st.markdown(gerenciador.get_download_link(conteudo_csv, f"sessao_{sessao.get('numero_sessao', '?')}.csv", 'csv'), unsafe_allow_html=True)
                        stats = sessao.get('estatisticas', {})
                        st.caption(f"✅ {stats.get('acertos', 0)} | ❌ {stats.get('erros', 0)} | 📊 {stats.get('taxa_acerto', 0)}%")
            
            st.markdown("---")
            st.markdown("#### 📊 Consolidado do Dia")
            data_hoje = data_brasilia()
            sessoes_hoje = gerenciador.listar_sessoes_do_dia(data_hoje)
            if sessoes_hoje:
                st.caption(f"📅 {data_hoje}: {len(sessoes_hoje)} sessões")
                if st.button("📊 Gerar Consolidado Hoje", use_container_width=True):
                    caminho = gerenciador.consolidar_sessoes_dia(data_hoje)
                    if caminho:
                        with open(caminho, 'r') as f: conteudo = f.read()
                        st.markdown(gerenciador.get_download_link(conteudo, f"consolidado_{data_hoje}.json", 'json'), unsafe_allow_html=True)
                        st.success("✅ Consolidado gerado!")
            
            if st.button("📦 Baixar Todas as Sessões (JSON)", use_container_width=True):
                todas_sessoes = gerenciador.listar_sessoes()
                if todas_sessoes:
                    conteudo = json.dumps({'total_sessoes': len(todas_sessoes), 'sessoes': todas_sessoes}, indent=2, ensure_ascii=False)
                    st.markdown(gerenciador.get_download_link(conteudo, f"todas_sessoes_{api_name.lower().replace(' ', '_')}.json", 'json'), unsafe_allow_html=True)
        else:
            st.info("Nenhuma sessão salva ainda.")
    
    st.markdown("---")
    
    # 🎰 SELEÇÃO DE ROLETA
    st.markdown("### 🎰 Selecione a Roleta")
    api_opcoes = list(API_URLS.keys())
    api_atual = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
    api_index = api_opcoes.index(api_atual) if api_atual in api_opcoes else 0
    st.session_state.api_selecionada = st.radio("Roleta:", api_opcoes, index=api_index)
    api_name = st.session_state.api_selecionada
    config = ROLETA_CONFIGS.get(api_name, SETUP_XXXTREME)
    
    if api_name == 'XXXtreme Lightning':
        st.success(f"⚡ AGRESSIVO | EMBALO: 3 consecutivas | ~68%")
    elif api_name == 'Immersive Roulette':
        st.info(f"🎯 CONSERVADOR | EMBALO: 2 consecutivas | ~75%")
    elif api_name == 'Mega Roulette':
        st.warning(f"⚡ CORRIGIDO | EMBALO: 2 consecutivas | ~73%")
    
    # 🧠 Status do ML
    if hasattr(sis.duzia_ai, 'modelo_ml') and sis.duzia_ai.modelo_ml is not None:
        st.success(f"🧠 ML ATIVO | Treinado na rodada {sis.duzia_ai.ultimo_treino_ml}")
    else:
        st.info("🧠 ML Aguardando dados... (precisa de ~24 rodadas)")
    
    st.markdown("---")
    st.session_state.janela_duzia_ai = st.slider("📏 Janela", 10, 50, st.session_state.janela_duzia_ai, 5)
    st.session_state.modo_agressivo = st.checkbox("🔥 Modo Agressivo (2 Dúzias)", value=st.session_state.modo_agressivo)
    st.session_state.modo_automatico = st.checkbox("🤖 Auto", value=st.session_state.modo_automatico)
    
    st.markdown("---")
    
    # 🔔 TELEGRAM
    with st.expander("🔔 Telegram", expanded=False):
        st.markdown("#### Telegram PRINCIPAL")
        st.session_state.telegram_token = st.text_input("Token Principal", value=st.session_state.telegram_token, type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID Principal", value=st.session_state.telegram_chat_id)
        st.markdown("#### Telegram ALTERNATIVO")
        st.session_state.telegram_token_alt = st.text_input("Token Alternativo", value=st.session_state.telegram_token_alt, type="password")
        st.session_state.telegram_chat_id_alt = st.text_input("Chat ID Alternativo", value=st.session_state.telegram_chat_id_alt)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Salvar", use_container_width=True): 
            paths = get_session_paths(st.session_state.api_selecionada)
            salvar_resultado_em_arquivo(st.session_state.historico, paths['historico'])
            salvar_sessao(); st.success("✅")
    with c2:
        if st.button("📥 CSV", use_container_width=True):
            if exportar_historico_csv(st.session_state.sistema.historico_entradas): st.success("✅")

# =============================
# CONTEÚDO PRINCIPAL
# =============================
st.subheader("🎲 Inserir Números")
c1, c2, c3 = st.columns([3,1,1])
with c1:
    entrada = st.text_input("Número (0-36):", key="entrada_numero")
with c2:
    if st.button("🎯 Enviar", use_container_width=True, type="primary"):
        if validar_numero(entrada):
            nr = int(entrada)
            st.session_state.historico.append({"number": nr, "timestamp": timestamp_brasilia(), "luckyNumbers": [], "luckyMultipliers": {}, "table_id": "manual", "table_name": "Entrada Manual"})
            st.session_state.sistema.processar_novo_numero(nr)
            paths = get_session_paths(st.session_state.api_selecionada)
            salvar_resultado_em_arquivo(st.session_state.historico, paths['historico'])
            salvar_sessao(); st.rerun()
        else: st.error("0-36")
with c3:
    if st.button("🔄 Auto", use_container_width=True):
        st.session_state.modo_automatico = not st.session_state.modo_automatico; st.rerun()

if st.session_state.modo_automatico:
    st_autorefresh(interval=3000, key="auto")
    r = fetch_latest_result()
    if r and r.get("number") is not None:
        if not st.session_state.historico or r.get("timestamp") != st.session_state.historico[-1].get("timestamp"):
            st.session_state.historico.append(r)
            st.session_state.sistema.processar_novo_numero(r)
            paths = get_session_paths(st.session_state.api_selecionada)
            salvar_resultado_em_arquivo(st.session_state.historico, paths['historico'])
            salvar_sessao(); st.rerun()

st.markdown("---")
sis = st.session_state.sistema
api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')

st.subheader(f"📊 CONFERÊNCIA - {api_name}")
c1, c2, c3, c4, c5, c6 = st.columns(6)
total_duzias = int(sis.acertos_duzia + sis.erros_duzia)
tx_duzias = (sis.acertos_duzia / total_duzias * 100) if total_duzias > 0 else 0
total_numeros = sis.acertos_numero + sis.erros_numero
tx_numeros = (sis.acertos_numero / total_numeros * 100) if total_numeros > 0 else 0
c1.metric("🎯 Nº Exato", sis.acertos_numero, f"{tx_numeros:.0f}%")
c2.metric("✅ Acertos Dúzia", int(sis.acertos_duzia), f"{tx_duzias:.0f}%")
c3.metric("❌ Erros Dúzia", sis.erros_duzia)
c4.metric("🟢 Zeros", f"{sis.acertos_zero}/{sis.acertos_zero + sis.erros_zero}")
c5.metric("📦 Total", total_duzias)
c6.metric("🎰", api_name[:10])

if sis.total_sessoes > 0:
    st.markdown("---")
    st.subheader(f"📈 Sessão #{sis.total_sessoes}")
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("🔄 Rodadas", f"{sis.rodadas_na_sessao}/{sis.rodadas_por_sessao}")
    sc2.metric("✅ Acertos", sis.acertos_sessao)
    sc3.metric("❌ Erros", sis.erros_sessao)
    taxa_sessao = (sis.acertos_sessao / max(1, sis.acertos_sessao + sis.erros_sessao)) * 100
    sc4.metric("📊 Taxa", f"{taxa_sessao:.0f}%")
    if sis.sessao_ativa: st.progress(sis.rodadas_na_sessao / sis.rodadas_por_sessao)

st.markdown("---")
cg, ce = st.columns([3,2])
with cg:
    st.subheader("📈 Scores")
    if len(sis.historico_numeros) >= 3:
        score, gatilho = sis.duzia_ai.calcular_score()
        fig = plt.Figure(data=[plt.Bar(
            x=['D1', 'D2', 'D3'], y=[score[1], score[2], score[3]],
            marker_color=['#FF6B6B' if score[1]==max(score.values()) else '#4ECDC4',
                          '#FF6B6B' if score[2]==max(score.values()) else '#4ECDC4',
                          '#FF6B6B' if score[3]==max(score.values()) else '#4ECDC4'],
            text=[f'{score[1]:.0f}', f'{score[2]:.0f}', f'{score[3]:.0f}'], textposition='auto'
        )])
        titulo = f"🎯 {'⚠️ GATILHO: '+gatilho['tipo'] if gatilho else 'Sem gatilho'}"
        if sis.duzia_ai.modelo_ml is not None: titulo += " | 🧠 ML"
        if sis.duzia_ai.alerta_zero_ativo: titulo += " | 🟢 ZERO!"
        fig.update_layout(title=titulo, height=250, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        if len(sis.historico_numeros) >= 8:
            ult = list(sis.historico_numeros)[-20:]
            dz_hist = [get_duzia(n) for n in ult]
            fig2 = plt.Figure()
            fig2.add_trace(plt.Scatter(x=list(range(len(dz_hist))), y=dz_hist, mode='lines+markers', line=dict(color='#FFD700', width=2), marker=dict(size=10)))
            if sis.sinais_grafico:
                sx, sy = [], []
                off = len(dz_hist) - 20
                for idx, dz in sis.sinais_grafico:
                    pos = idx - off
                    if 0 <= pos < 20: sx.append(pos); sy.append(dz)
                if sx: fig2.add_trace(plt.Scatter(x=sx, y=sy, mode='markers', name='Sinal', marker=dict(symbol='star', size=15, color='red')))
            fig2.update_layout(title="📉 Histórico", yaxis=dict(tickvals=[0,1,2,3], ticktext=['0','D1','D2','D3'], range=[-0.5, 3.5]), height=250)
            st.plotly_chart(fig2, use_container_width=True)

with ce:
    st.subheader("🎰 Entrada Atual")
    if sis.duzia_ai.alerta_zero_ativo: st.warning("⚠️ ALERTA ZERO! 🟢")
    if sis.duzia_ai.em_pausa_pos_raio: st.warning(f"⏸️ Pausa pós-raio ({sis.duzia_ai.ultimo_raio_alto}x)")
    
    if not sis.sessao_ativa:
        if sis.sessao_pausa_ate and hora_brasilia() < sis.sessao_pausa_ate:
            tempo_restante = (sis.sessao_pausa_ate - hora_brasilia()).seconds
            st.info(f"⏸️ Pausa: {tempo_restante//60:02d}:{tempo_restante%60:02d}")
        else:
            st.info("🔴 Clique 'INICIAR SESSÃO' para começar")
    
    if sis.entrada_ativa and sis.sessao_ativa:
        e = sis.entrada_ativa
        conf = e.get('confianca', 0)
        dz_princ = e.get('duzia_prevista', 0); dz_sec = e.get('duzia_sec_prevista')
        gat = e.get('gatilho_ativo')
        duzia_principal = dz_princ
        duzia_secundaria = dz_sec if dz_sec and dz_sec != dz_princ else None
        melhores_principal = _selecionar_melhores_numeros(duzia_principal, list(sis.historico_numeros), 6)
        if duzia_secundaria: melhores_secundaria = _selecionar_melhores_numeros(duzia_secundaria, list(sis.historico_numeros), 6)
        else: melhores_secundaria = None
        cor = "#FF6347" if e.get('modo_anti_erro') else "#FFD700"
        st.markdown(f"""
        <div style="background-color:{cor}15; border:2px solid {cor}; border-radius:15px; padding:15px;">
            <h2 style="color:{cor}; text-align:center;">🎯 D{dz_princ}</h2>
            <p style="text-align:center; font-size:1.1em;">Confiança: {conf:.2f} {'| 🎯 '+gat if gat else ''}</p>
            {f'<p style="text-align:center; color:#FFA500;">🛡️ Cobertura: D{dz_sec}</p>' if duzia_secundaria else ''}
        </div>""", unsafe_allow_html=True)
        st.write(f"**🎲 6 melhores D{duzia_principal}:** {', '.join(map(str, melhores_principal))}")
        if melhores_secundaria: st.write(f"**🛡️ 6 melhores D{duzia_secundaria}:** {', '.join(map(str, melhores_secundaria))}")
        st.progress(min(1.0, max(0.0, conf/5.0)))
    else:
        st.info("🔍 Aguardando sinal...")
    
    if sis.ultimo_numero is not None:
        st.markdown("---")
        st.write(f"**🔄 Último:** {'🟢 ZERO' if sis.ultimo_numero==0 else f'#{sis.ultimo_numero} (D{get_duzia(sis.ultimo_numero)})'}")

st.markdown("---")
st.subheader("📝 Histórico")

if sis.historico_entradas:
    dados = []
    for e in reversed(sis.historico_entradas[-15:]):
        real = f"D{e.get('duzia_real',0)}" if e.get('duzia_real',0)!=0 else "0"
        prev = f"D{e.get('duzia_prevista','?')}"
        cob = f"D{e.get('duzia_sec_prevista','?')}" if e.get('duzia_sec_prevista') and e.get('duzia_sec_prevista') != e.get('duzia_prevista') else "-"
        zero = '🟢' if e.get('incluir_zero') else '-'
        anti = '🔄' if e.get('modo_anti_erro') else '-'
        duz = '✅' if e.get('acerto_duzia') else '❌'
        num = '🎯' if e.get('acerto_numero') else '-'
        zer = '🟢' if e.get('acerto_zero') else '-'
        numero_sorteado = e.get('numero', 0)
        if e.get('eh_raio'): num_display = f"⚡{numero_sorteado} ({e.get('multiplicador',0)}x)"
        elif numero_sorteado == 0: num_display = "0"
        else: num_display = str(numero_sorteado)
        dados.append({
            "Rod": e.get('rodada'), "Hora": e.get('hora'), "🎲": num_display,
            "Real": real, "Prev": prev, "Cob": cob,
            "Conf": f"{e.get('confianca',0):.1f}", "Gat": e.get('gatilho','-') if e.get('gatilho') else '-',
            "Z": zero, "🔄": anti, "Duz": duz, "Nº": num, "Zer": zer,
        })
    st.dataframe(dados, use_container_width=True, height=300)
    
    if st.button("📥 Exportar CSV", use_container_width=True):
        if exportar_historico_csv(sis.historico_entradas): st.success("✅")
else: 
    st.info("Nenhuma entrada.")

st.markdown("---")
st.caption("📡 **Status Telegram:**")
col_t1, col_t2 = st.columns(2)
with col_t1:
    if st.session_state.telegram_token and st.session_state.telegram_chat_id: st.success("🔔 Principal: CONFIGURADO")
    else: st.warning("🔔 Principal: NÃO CONFIGURADO")
with col_t2:
    if st.session_state.telegram_token_alt and st.session_state.telegram_chat_id_alt: st.success("📢 Alternativo: CONFIGURADO")
    else: st.warning("📢 Alternativo: NÃO CONFIGURADO")

st.caption(f"🤖 DuziaAI V11.0.0 | ML Online Janela 20 | {api_name} | {formatar_hora_brasilia()}")
salvar_sessao()
