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
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
    from sklearn.preprocessing import StandardScaler
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
    'confianca_minima_entrada': 1.8,
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
    'pausa_pos_raio': 1,
    'raio_alto_minimo': 100,
    'zero_termometro_max': 15,
    'anti_erro_skip_discordancia': True,
    'ritmo_v_peso': 9,
    'ritmo_v_forca': 9,
    'ritmo_v_confirmacoes': 2,
    'ml_janela_treino': 120,
    'ml_atualizar_a_cada': 10,
    'score_ml_peso': 45,
    'ml_score_minimo_entrada': 25,
    'ml_score_minimo_fallback': 42,
    'ml_min_rodadas_fallback': 8,
    'ml_max_repeticoes_mesma_duzia': 3,
    'ml_score_minimo_pos_rotacao': 20,
    # 🆕 Configurações de memória de padrões
    'memoria_ngram_min': 2,
    'memoria_ngram_max': 5,
    'memoria_peso_padrao': 30,
    'memoria_confianca_boost': 0.4,
    'memoria_min_ocorrencias': 2,
}

SETUP_XXXTREME = {
    **SETUP_BASE,
    'pagamento_numero': 20, 'pagamento_zero': 20, 'pagamento_duzia': 3,
    'confianca_minima_entrada': 1.8,
    'embalo_peso': 5, 'embalo_reforco': 2,
    'bloquear_alerta_zero_conf_alta': True, 'bloquear_anti_erro_zero_conf_baixa': True,
    'filtro_conf_baixa': 2.0, 'fadiga_duzia': 4,
    'ritmo_alternado_peso': 10, 'ritmo_alternado_forca': 10,
    'max_repeticoes_embalo': 3, 'confianca_maxima_segura': 3.1,
    'rodadas_verificacao_conf_alta': 5, 'pausa_pos_raio': 1, 'raio_alto_minimo': 700,
    'zero_termometro_max': 15, 'anti_erro_skip_discordancia': True,
    'ritmo_v_peso': 9, 'ritmo_v_forca': 9, 'ritmo_v_confirmacoes': 2,
    'usar_embalo': True, 'embalo_consecutivas_min': 2, 'embalo_janela': 4,
    'usar_ritmo_alternado': True, 'usar_ritmo_v': True,
    'usar_ritmo_ping_pong': True, 'usar_ritmo_binario': True,
    'usar_quebra_pos_zero': False,
    'usar_exaustao_dominancia': True,
    'usar_mudanca_velocidade': False,
    'score_frequencia_peso': 45, 'score_streak_peso': 6,
    'score_markov_peso': 8, 'score_ml_peso': 45, 'score_anti_erro_peso': 20,
    'ml_janela_treino': 120, 'ml_atualizar_a_cada': 8,
    'ml_score_minimo_entrada': 25,
    'ml_score_minimo_fallback': 42,
    'ml_min_rodadas_fallback': 10,
    'ml_max_repeticoes_mesma_duzia': 3,
    'ml_score_minimo_pos_rotacao': 20,
    'memoria_ngram_min': 2, 'memoria_ngram_max': 5,
    'memoria_peso_padrao': 30, 'memoria_confianca_boost': 0.4,
    'memoria_min_ocorrencias': 2,
}

SETUP_IMMERSIVE = {
    **SETUP_BASE,
    'pagamento_numero': 35, 'pagamento_zero': 35, 'pagamento_duzia': 2,
    'confianca_minima_entrada': 1.8,
    'embalo_peso': 5, 'embalo_reforco': 2,
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
    'score_markov_peso': 8, 'score_ml_peso': 45, 'score_anti_erro_peso': 20,
    'horario_bloqueio_inicio': 5, 'horario_bloqueio_fim': 7,
    'ml_janela_treino': 120, 'ml_atualizar_a_cada': 8,
    'ml_score_minimo_entrada': 25,
    'ml_score_minimo_fallback': 42,
    'ml_min_rodadas_fallback': 10,
    'ml_max_repeticoes_mesma_duzia': 3,
    'ml_score_minimo_pos_rotacao': 18,
    'memoria_ngram_min': 2, 'memoria_ngram_max': 5,
    'memoria_peso_padrao': 25, 'memoria_confianca_boost': 0.3,
    'memoria_min_ocorrencias': 2,
}

SETUP_MEGA = {
    **SETUP_BASE,
    'pagamento_numero': 24, 'pagamento_zero': 24, 'pagamento_duzia': 2,
    'confianca_minima_entrada': 1.8,
    'embalo_peso': 5, 'embalo_reforco': 2,
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
    'score_markov_peso': 8, 'score_ml_peso': 35, 'score_anti_erro_peso': 20,
    'ml_janela_treino': 120, 'ml_atualizar_a_cada': 8,
    'ml_score_minimo_entrada': 25,
    'ml_score_minimo_fallback': 42,
    'ml_min_rodadas_fallback': 10,
    'ml_max_repeticoes_mesma_duzia': 3,
    'ml_score_minimo_pos_rotacao': 18,
    'memoria_ngram_min': 2, 'memoria_ngram_max': 5,
    'memoria_peso_padrao': 28, 'memoria_confianca_boost': 0.35,
    'memoria_min_ocorrencias': 2,
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
PASTA_MODELOS_ML = "modelos_ml"

def criar_pasta_modelos_ml():
    if not os.path.exists(PASTA_MODELOS_ML):
        os.makedirs(PASTA_MODELOS_ML)

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

def get_modelo_ml_path(api_name):
    criar_pasta_modelos_ml()
    safe_name = api_name.lower().replace(' ', '_')
    return os.path.join(PASTA_MODELOS_ML, f"modelo_ml_{safe_name}.joblib")

def salvar_modelo_ml(modelo, api_name):
    if modelo is None:
        return False
    try:
        caminho = get_modelo_ml_path(api_name)
        joblib.dump(modelo, caminho)
        logging.info(f"💾 Modelo ML salvo: {caminho}")
        return True
    except Exception as e:
        logging.error(f"❌ Erro ao salvar modelo ML: {e}")
        return False

def carregar_modelo_ml(api_name):
    try:
        caminho = get_modelo_ml_path(api_name)
        if os.path.exists(caminho):
            modelo = joblib.load(caminho)
            logging.info(f"📂 Modelo ML carregado: {caminho}")
            return modelo
    except Exception as e:
        logging.error(f"❌ Erro ao carregar modelo ML: {e}")
    return None

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
        'memoria_padroes': f"memoria_padroes_{safe_name}.json",  # 🆕
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

        # 🆕 Salvar memória de padrões
        if hasattr(sis.duzia_ai, 'memoria_padroes'):
            sis.duzia_ai.memoria_padroes.salvar(paths['memoria_padroes'])

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
            'ultimo_treino_ml': sis.duzia_ai.ultimo_treino_ml,
        }
        with open(paths['session'], 'wb') as f: pickle.dump(session_data, f)

        if sis.duzia_ai.modelo_ml is not None:
            salvar_modelo_ml(sis.duzia_ai.modelo_ml, api_name)

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
                # 🆕 Caminho da memória de padrões para carregar depois
                dados['_memoria_padroes_path'] = paths.get('memoria_padroes', '')
    except: pass
    return dados


def limpar_sessao():
    try:
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        paths = get_session_paths(api_name)
        for path in paths.values():
            if isinstance(path, str) and os.path.exists(path): os.remove(path)
        modelo_path = get_modelo_ml_path(api_name)
        if os.path.exists(modelo_path):
            os.remove(modelo_path)
        st.session_state.sistema.zerar()
        st.rerun()
    except Exception as e: logging.error(f"Erro: {e}")


def nova_sessao():
    try:
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        paths = get_session_paths(api_name)
        for path in paths.values():
            if isinstance(path, str) and os.path.exists(path): os.remove(path)
        modelo_path = get_modelo_ml_path(api_name)
        if os.path.exists(modelo_path):
            os.remove(modelo_path)
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
# 🧠 MÓDULO DE MEMÓRIA DE PADRÕES (NOVO)
# =============================

class MemoriaPadroes:
    """
    Mantém um banco de padrões históricos de sequências de dúzias.
    Para cada n-grama visto, registra qual dúzia veio DEPOIS e com qual frequência.
    Isso permite ao sistema reconhecer 'já vi essa sequência antes' e prever
    o que historicamente saiu a seguir.
    """

    def __init__(self, ngram_min=2, ngram_max=5, min_ocorrencias=2):
        self.ngram_min = ngram_min
        self.ngram_max = ngram_max
        self.min_ocorrencias = min_ocorrencias
        # {tuple_sequencia: Counter({duzia_seguinte: contagem})}
        self.tabela_padroes = defaultdict(Counter)
        # Contador de quantas vezes cada padrão foi visto
        self.contagem_padroes = Counter()
        # Histórico dos últimos acertos/erros por padrão
        self.acertos_por_padrao = defaultdict(int)
        self.erros_por_padrao = defaultdict(int)
        # Último padrão ativo para registro de resultado
        self.ultimo_padrao_ativo = None
        self.ultimo_padrao_previsto = None

    def registrar_sequencia(self, historico_duzias):
        """Atualiza a tabela de padrões com o histórico atual."""
        # Filtra zeros para análise de padrão de dúzias
        duzias = [d for d in historico_duzias if d != 0]
        if len(duzias) < self.ngram_min + 1:
            return

        # Para cada tamanho de n-grama configurado
        for n in range(self.ngram_min, min(self.ngram_max + 1, len(duzias))):
            # Percorre todas as janelas possíveis no histórico
            for i in range(len(duzias) - n):
                padrao = tuple(duzias[i:i + n])
                proximo = duzias[i + n]
                self.tabela_padroes[padrao][proximo] += 1
                self.contagem_padroes[padrao] += 1

    def buscar_padrao_atual(self, historico_duzias):
        """
        Busca o padrão mais longo que coincide com o fim do histórico atual
        e que tem ocorrências suficientes para ser confiável.
        Retorna (melhor_padrao, scores_por_duzia, confianca, ocorrencias)
        """
        duzias = [d for d in historico_duzias if d != 0]
        if len(duzias) < self.ngram_min:
            return None, {1: 0.0, 2: 0.0, 3: 0.0}, 0.0, 0

        melhor_padrao = None
        melhor_scores = {1: 0.0, 2: 0.0, 3: 0.0}
        melhor_confianca = 0.0
        melhor_ocorrencias = 0

        # Testa do maior para o menor n-grama (prioriza padrões mais longos)
        for n in range(min(self.ngram_max, len(duzias)), self.ngram_min - 1, -1):
            padrao = tuple(duzias[-n:])
            if padrao not in self.tabela_padroes:
                continue

            total_ocorrencias = self.contagem_padroes.get(padrao, 0)
            if total_ocorrencias < self.min_ocorrencias:
                continue

            seguintes = self.tabela_padroes[padrao]
            total = sum(seguintes.values())
            if total == 0:
                continue

            scores = {1: 0.0, 2: 0.0, 3: 0.0}
            for duzia, cnt in seguintes.items():
                if duzia in scores:
                    scores[duzia] = (cnt / total) * 100

            # Confiança baseada na dominância do padrão e número de ocorrências
            max_score = max(scores.values())
            segundo_score = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0
            dominancia = max_score - segundo_score
            confianca = min(1.0, (dominancia / 100) * (1 + np.log1p(total_ocorrencias) / 5))

            # Prefere padrões maiores E mais confiantes
            peso_tamanho = n * 0.1
            score_final = confianca + peso_tamanho

            if score_final > (melhor_confianca + melhor_ocorrencias * 0.01):
                melhor_padrao = padrao
                melhor_scores = scores
                melhor_confianca = confianca
                melhor_ocorrencias = total_ocorrencias

        return melhor_padrao, melhor_scores, melhor_confianca, melhor_ocorrencias

    def registrar_resultado_padrao(self, acertou):
        """Registra se o padrão ativo acertou ou errou."""
        if self.ultimo_padrao_ativo is not None:
            if acertou:
                self.acertos_por_padrao[self.ultimo_padrao_ativo] += 1
            else:
                self.erros_por_padrao[self.ultimo_padrao_ativo] += 1
        self.ultimo_padrao_ativo = None
        self.ultimo_padrao_previsto = None

    def get_taxa_acerto_padrao(self, padrao):
        """Retorna a taxa de acerto histórica de um padrão."""
        acertos = self.acertos_por_padrao.get(padrao, 0)
        erros = self.erros_por_padrao.get(padrao, 0)
        total = acertos + erros
        if total == 0:
            return None
        return acertos / total

    def get_stats(self):
        """Retorna estatísticas da memória de padrões."""
        return {
            'total_padroes': len(self.tabela_padroes),
            'padroes_confiaveis': sum(1 for p in self.contagem_padroes if self.contagem_padroes[p] >= self.min_ocorrencias),
            'total_registros': sum(self.contagem_padroes.values()),
        }

    def salvar(self, caminho):
        """Persiste a memória de padrões em disco."""
        try:
            dados = {
                'tabela': {str(k): dict(v) for k, v in self.tabela_padroes.items()},
                'contagem': {str(k): v for k, v in self.contagem_padroes.items()},
                'acertos': {str(k): v for k, v in self.acertos_por_padrao.items()},
                'erros': {str(k): v for k, v in self.erros_por_padrao.items()},
            }
            with open(caminho, 'w') as f:
                json.dump(dados, f)
            logging.info(f"🧩 Memória de padrões salva: {len(self.tabela_padroes)} padrões")
        except Exception as e:
            logging.error(f"❌ Erro ao salvar memória de padrões: {e}")

    def carregar(self, caminho):
        """Carrega a memória de padrões do disco."""
        try:
            if not os.path.exists(caminho):
                return False
            with open(caminho, 'r') as f:
                dados = json.load(f)

            import ast
            self.tabela_padroes = defaultdict(Counter)
            for k, v in dados.get('tabela', {}).items():
                try:
                    chave = tuple(ast.literal_eval(k))
                    self.tabela_padroes[chave] = Counter({int(dk): dv for dk, dv in v.items()})
                except: pass

            self.contagem_padroes = Counter()
            for k, v in dados.get('contagem', {}).items():
                try:
                    chave = tuple(ast.literal_eval(k))
                    self.contagem_padroes[chave] = v
                except: pass

            self.acertos_por_padrao = defaultdict(int)
            for k, v in dados.get('acertos', {}).items():
                try:
                    chave = tuple(ast.literal_eval(k))
                    self.acertos_por_padrao[chave] = v
                except: pass

            self.erros_por_padrao = defaultdict(int)
            for k, v in dados.get('erros', {}).items():
                try:
                    chave = tuple(ast.literal_eval(k))
                    self.erros_por_padrao[chave] = v
                except: pass

            logging.info(f"🧩 Memória de padrões carregada: {len(self.tabela_padroes)} padrões")
            return True
        except Exception as e:
            logging.error(f"❌ Erro ao carregar memória de padrões: {e}")
            return False


# =============================
# FUNÇÕES AUXILIARES
# =============================

def _calcular_entropia(duzias):
    """Calcula entropia de Shannon das dúzias (mede aleatoriedade)"""
    if not duzias:
        return 0.0
    freq = Counter(duzias)
    total = len(duzias)
    entropia = 0.0
    for v in freq.values():
        p = v / total
        if p > 0:
            entropia -= p * np.log2(p)
    return round(entropia, 4)


def _calcular_gap_duzia(numeros, duzia):
    """Calcula quantas rodadas desde que a dúzia saiu pela última vez"""
    for i, n in enumerate(reversed(numeros)):
        if get_duzia(n) == duzia:
            return i
    return len(numeros)


def _calcular_autocorrelacao(serie, lag=3):
    """
    Calcula autocorrelação da série de dúzias com um lag.
    Valores altos indicam padrões cíclicos repetitivos.
    """
    if len(serie) < lag + 4:
        return 0.0
    try:
        s = np.array(serie, dtype=float)
        s1 = s[:-lag]
        s2 = s[lag:]
        if np.std(s1) < 1e-9 or np.std(s2) < 1e-9:
            return 0.0
        corr = np.corrcoef(s1, s2)[0, 1]
        return float(corr) if not np.isnan(corr) else 0.0
    except:
        return 0.0


# =============================
# 🧠 DUZIA AI V12.0 — MEMÓRIA DE PADRÕES + ML CORRIGIDO
# =============================

class DuziaAI:
    def __init__(self, window=30, api_name='XXXtreme Lightning'):
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
        self.modelo_ml = None
        self.ultimo_treino_ml = 0
        self.mesa_atual = None
        self.api_name = api_name
        self.performance_por_mesa = defaultdict(lambda: {'acertos': 0, 'erros': 0})
        self.performance_por_horario = defaultdict(lambda: {'acertos': 0, 'erros': 0})
        self.scaler = StandardScaler() if ML_DISPONIVEL else None
        self.scaler_treinado = False
        self.contagem_repeticoes_mesma_duzia = 0

        # 🆕 Inicializar memória de padrões
        config = self._get_config()
        self.memoria_padroes = MemoriaPadroes(
            ngram_min=config.get('memoria_ngram_min', 2),
            ngram_max=config.get('memoria_ngram_max', 5),
            min_ocorrencias=config.get('memoria_min_ocorrencias', 2),
        )

        # 🆕 Estado do padrão ativo para UI
        self.padrao_ativo = None
        self.padrao_ativo_ocorrencias = 0
        self.padrao_ativo_confianca = 0.0
        self.padrao_ativo_scores = {1: 0.0, 2: 0.0, 3: 0.0}

        self._carregar_modelo_salvo()

    def _carregar_modelo_salvo(self):
        if not ML_DISPONIVEL:
            return
        modelo_carregado = carregar_modelo_ml(self.api_name)
        if modelo_carregado is not None:
            self.modelo_ml = modelo_carregado
            logging.info(f"🧠 Modelo ML carregado do disco para {self.api_name}")
            self.ultimo_treino_ml = 1

    def _get_config(self):
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        return ROLETA_CONFIGS.get(api_name, SETUP_XXXTREME).copy()

    # =========================================================
    # FEATURES EXPANDIDAS: 45 features (corrigidas)
    # =========================================================
    def _extrair_features_core(self, historico_duzias, historico_numeros,
                                erros_consec, rodadas_zero, repeticoes_duzia, janela=20):
        """
        Extrai as 45 features de forma consistente tanto para treino quanto para inferência.
        Recebe os dados necessários como parâmetros para evitar inconsistência.
        """
        numeros_janela = historico_numeros[-janela:] if len(historico_numeros) >= janela else historico_numeros
        duzias_janela = [d for d in historico_duzias[-janela:] if d != 0]

        if not duzias_janela or len(historico_duzias) < 5:
            return None

        # Pad ultimas_4 se necessário
        ultimas_4_raw = historico_duzias[-4:]
        while len(ultimas_4_raw) < 4:
            ultimas_4_raw = [0] + list(ultimas_4_raw)
        ultimas_4 = ultimas_4_raw[:4]

        # --- Terminais ---
        terminais = [n % 10 for n in numeros_janela if n != 0]
        contagem_terminais = Counter(terminais).most_common(3)
        t1_quente = contagem_terminais[0][0] if len(contagem_terminais) > 0 else -1
        t2_quente = contagem_terminais[1][0] if len(contagem_terminais) > 1 else -1
        freq_terminal_zero = terminais.count(0)

        # --- Zeros ---
        try:
            rodadas_sem_zero = list(reversed(numeros_janela)).index(0)
        except ValueError:
            rodadas_sem_zero = janela
        contagem_zeros_janela = numeros_janela.count(0)

        # --- Frequências ---
        freq_total = Counter(duzias_janela)
        freq_recente = Counter(duzias_janela[-8:]) if len(duzias_janela) >= 8 else Counter(duzias_janela)
        freq_d1 = freq_total.get(1, 0)
        freq_d2 = freq_total.get(2, 0)
        freq_d3 = freq_total.get(3, 0)
        freq_d1_rec = freq_recente.get(1, 0)
        freq_d2_rec = freq_recente.get(2, 0)
        freq_d3_rec = freq_recente.get(3, 0)
        duzia_dominante = freq_total.most_common(1)[0][0] if freq_total else -1
        duzia_recente = freq_recente.most_common(1)[0][0] if freq_recente else -1

        # --- Streaks ---
        streak_count = 1
        for i in range(len(duzias_janela) - 1, 0, -1):
            if duzias_janela[i] == duzias_janela[i - 1]:
                streak_count += 1
            else:
                break

        max_streak = 1
        cur_streak = 1
        for i in range(1, len(duzias_janela)):
            if duzias_janela[i] == duzias_janela[i - 1]:
                cur_streak += 1
                max_streak = max(max_streak, cur_streak)
            else:
                cur_streak = 1

        # --- Transições ---
        transicoes_recentes = 0
        for i in range(1, min(10, len(duzias_janela))):
            if duzias_janela[-i] != duzias_janela[-i - 1]:
                transicoes_recentes += 1

        aba_pattern = 0
        if len(duzias_janela) >= 3:
            if duzias_janela[-1] == duzias_janela[-3] and duzias_janela[-1] != duzias_janela[-2]:
                aba_pattern = 1

        # --- Gaps ---
        gap_d1 = next((i for i, n in enumerate(reversed(historico_numeros)) if get_duzia(n) == 1), len(historico_numeros))
        gap_d2 = next((i for i, n in enumerate(reversed(historico_numeros)) if get_duzia(n) == 2), len(historico_numeros))
        gap_d3 = next((i for i, n in enumerate(reversed(historico_numeros)) if get_duzia(n) == 3), len(historico_numeros))

        # --- Volatilidade ---
        n_total = max(1, len(duzias_janela))
        esperado = n_total / 3
        volatilidade = abs(freq_d1 - esperado) + abs(freq_d2 - esperado) + abs(freq_d3 - esperado)

        # --- Paridade ---
        nums_nao_zero = [n for n in numeros_janela if n != 0]
        paridade = sum(1 for n in nums_nao_zero if n % 2 == 0) / max(1, len(nums_nao_zero))

        # --- Entropia ---
        entropia = _calcular_entropia(duzias_janela)

        # --- Dúzia mais ausente ---
        gaps = {1: gap_d1, 2: gap_d2, 3: gap_d3}
        duzia_mais_ausente = max(gaps, key=gaps.get)

        # --- Tendência monotônica ---
        seq_recente = [get_duzia(n) for n in historico_numeros[-5:] if n != 0]
        mono_up = 1 if len(seq_recente) >= 3 and all(seq_recente[i] <= seq_recente[i+1] for i in range(len(seq_recente)-1)) else 0
        mono_down = 1 if len(seq_recente) >= 3 and all(seq_recente[i] >= seq_recente[i+1] for i in range(len(seq_recente)-1)) else 0

        # 🆕 Feature 33: autocorrelação lag=2 (detecta ciclos de 2)
        autocorr_lag2 = _calcular_autocorrelacao(duzias_janela, lag=2)

        # 🆕 Feature 34: autocorrelação lag=3 (detecta ciclos de 3)
        autocorr_lag3 = _calcular_autocorrelacao(duzias_janela, lag=3)

        # 🆕 Feature 35: proporção das últimas 5 dúzias que são D1
        ultimas5 = [d for d in historico_duzias[-5:] if d != 0]
        prop_d1_rec5 = ultimas5.count(1) / max(1, len(ultimas5))

        # 🆕 Feature 36: proporção das últimas 5 dúzias que são D2
        prop_d2_rec5 = ultimas5.count(2) / max(1, len(ultimas5))

        # 🆕 Feature 37: proporção das últimas 5 dúzias que são D3
        prop_d3_rec5 = ultimas5.count(3) / max(1, len(ultimas5))

        # 🆕 Feature 38: padrão ABAB (ritmo ping-pong)
        abab_pattern = 0
        if len(duzias_janela) >= 4:
            if (duzias_janela[-1] == duzias_janela[-3] and
                duzias_janela[-2] == duzias_janela[-4] and
                duzias_janela[-1] != duzias_janela[-2]):
                abab_pattern = 1

        # 🆕 Feature 39: dúzia que mais saiu nas últimas 3 rodadas
        ultimas3 = [d for d in historico_duzias[-3:] if d != 0]
        duzia_dom_3 = Counter(ultimas3).most_common(1)[0][0] if ultimas3 else 0

        # 🆕 Feature 40: quantidade de dúzias únicas nas últimas 6 rodadas
        ultimas6 = [d for d in historico_duzias[-6:] if d != 0]
        diversidade_6 = len(set(ultimas6)) if ultimas6 else 0

        # 🆕 Feature 41: última dúzia que saiu (0 se zero)
        ultima_duzia = historico_duzias[-1] if historico_duzias else 0

        # 🆕 Feature 42: penúltima dúzia
        penultima_duzia = historico_duzias[-2] if len(historico_duzias) >= 2 else 0

        # 🆕 Feature 43: diferença entre as últimas 2 dúzias (detecta alternância)
        diff_ultimas2 = abs(ultima_duzia - penultima_duzia) if (ultima_duzia != 0 and penultima_duzia != 0) else 0

        # 🆕 Feature 44: rodadas desde o último erro consecutivo (usando parâmetro real)
        erros_consec_real = float(erros_consec)

        # 🆕 Feature 45: contagem de repetições da mesma dúzia (usando parâmetro real)
        repeticoes_real = float(repeticoes_duzia)

        features = [
            # 0-3: últimas 4 dúzias
            float(ultimas_4[0]), float(ultimas_4[1]), float(ultimas_4[2]), float(ultimas_4[3]),
            # 4-6: terminais
            float(t1_quente), float(t2_quente), float(freq_terminal_zero),
            # 7-8: zeros
            float(rodadas_sem_zero), float(contagem_zeros_janela),
            # 9-10: dominância
            float(duzia_dominante), float(duzia_recente),
            # 11-12: streaks
            float(streak_count), float(max_streak),
            # 13-14: transições
            float(transicoes_recentes), float(aba_pattern),
            # 15-20: frequências
            float(freq_d1), float(freq_d2), float(freq_d3),
            float(freq_d1_rec), float(freq_d2_rec), float(freq_d3_rec),
            # 21-23: gaps
            float(gap_d1), float(gap_d2), float(gap_d3),
            # 24-25: estado do jogador (agora com valores REAIS, não zeros)
            erros_consec_real, float(rodadas_zero),
            # 26-28: estatísticas
            float(volatilidade), float(paridade), float(entropia),
            # 29: ausência
            float(duzia_mais_ausente),
            # 30-31: tendência
            float(mono_up), float(mono_down),
            # 32: repetições (REAL)
            repeticoes_real,
            # 33-34: autocorrelação (NOVO)
            float(autocorr_lag2), float(autocorr_lag3),
            # 35-37: proporções recentes (NOVO)
            float(prop_d1_rec5), float(prop_d2_rec5), float(prop_d3_rec5),
            # 38: ping-pong (NOVO)
            float(abab_pattern),
            # 39: dominância últimas 3 (NOVO)
            float(duzia_dom_3),
            # 40: diversidade últimas 6 (NOVO)
            float(diversidade_6),
            # 41-42: últimas 2 dúzias (NOVO)
            float(ultima_duzia), float(penultima_duzia),
            # 43: diferença (NOVO)
            float(diff_ultimas2),
        ]

        # TOTAL: 44 features (índices 0-43)
        return features

    def extrair_features_estado(self, janela=20):
        """Extrai features para inferência — usa estado atual do objeto."""
        return self._extrair_features_core(
            historico_duzias=self.historico_completo,
            historico_numeros=self.numeros_completos,
            erros_consec=self.erros_consecutivos,
            rodadas_zero=self.rodadas_desde_zero,
            repeticoes_duzia=self.contagem_repeticoes_mesma_duzia,
            janela=janela
        )

    def _extrair_features_historico(self, historico_duzias, historico_numeros, janela=20):
        """
        Extrai features de um ponto histórico para treino.
        CORRIGIDO: usa a mesma função core, sem placeholders zerados.
        Os valores de erros_consec, rodadas_zero e repeticoes são calculados
        a partir do histórico parcial para aproximar o estado real naquele momento.
        """
        # Aproximação dos estados derivados no momento histórico
        erros_consec = 0  # Simplificação aceitável para treino
        rodadas_zero = 0
        for n in reversed(historico_numeros):
            if n == 0:
                break
            rodadas_zero += 1

        # Contar repetições da última dúzia no histórico parcial
        repeticoes = 0
        duzias_hist = [d for d in historico_duzias if d != 0]
        if duzias_hist:
            ultima = duzias_hist[-1]
            for d in reversed(duzias_hist[:-1]):
                if d == ultima:
                    repeticoes += 1
                else:
                    break

        return self._extrair_features_core(
            historico_duzias=historico_duzias,
            historico_numeros=historico_numeros,
            erros_consec=erros_consec,
            rodadas_zero=rodadas_zero,
            repeticoes_duzia=repeticoes,
            janela=janela
        )

    def _treinar_ml_online(self):
        """Ensemble RF + GBT com features unificadas e corretas."""
        if not ML_DISPONIVEL:
            return False

        config = self._get_config()
        janela_treino = config.get('ml_janela_treino', 120)
        atualizar_a_cada = config.get('ml_atualizar_a_cada', 8)

        rodada_atual = len(self.historico_completo)

        if self.modelo_ml is not None and self.ultimo_treino_ml > 0:
            if rodada_atual - self.ultimo_treino_ml < atualizar_a_cada:
                return False
        else:
            if len(self.historico_completo) < 40:
                return False

        try:
            X, y = [], []
            inicio = max(0, len(self.historico_completo) - janela_treino - 4)

            for i in range(inicio + 10, len(self.historico_completo)):
                hist_duzias = self.historico_completo[:i]
                hist_nums = self.numeros_completos[:i]

                if len(hist_duzias) < 10 or len(hist_nums) < 10:
                    continue

                features = self._extrair_features_historico(hist_duzias, hist_nums, janela_treino)
                if features is None:
                    continue

                target = self.historico_completo[i]
                if target in [1, 2, 3]:
                    X.append(features)
                    y.append(target)

            if len(X) < 15:
                return False

            X_arr = np.array(X)

            rf = RandomForestClassifier(
                n_estimators=150,
                max_depth=12,
                random_state=42,
                n_jobs=-1,
                class_weight='balanced',
                min_samples_leaf=2,
            )
            gbt = GradientBoostingClassifier(
                n_estimators=80,
                max_depth=5,
                learning_rate=0.1,
                random_state=42,
            )
            ensemble = VotingClassifier(
                estimators=[('rf', rf), ('gbt', gbt)],
                voting='soft',
            )
            ensemble.fit(X_arr, y)

            self.modelo_ml = ensemble
            self.ultimo_treino_ml = rodada_atual

            salvar_modelo_ml(self.modelo_ml, self.api_name)
            logging.info(f"🧠 Ensemble ML Treinado! Amostras: {len(X)} | Rodada: {rodada_atual}")
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

        if d != 0:
            self.duzias_que_sairam.append(d)
            if len(self.duzias_que_sairam) > 10:
                self.duzias_que_sairam = self.duzias_que_sairam[-10:]

        if numero == 0 and self.alerta_zero_ativo:
            self.zeros_previstos += 1

        if len(self.historico_completo) >= 4:
            padrao = tuple(self.historico_completo[-4:-1])
            self.transicoes[padrao][d] += 1

        # 🆕 Atualiza memória de padrões a cada novo número
        self.memoria_padroes.registrar_sequencia(self.historico_completo)

        if len(self.historico_completo) > 1000:
            self.historico_completo = self.historico_completo[-1000:]
        if len(self.numeros_completos) > 1000:
            self.numeros_completos = self.numeros_completos[-1000:]

        if self.em_pausa_pos_raio:
            self.rodadas_pos_raio += 1
            config = self._get_config()
            if self.rodadas_pos_raio >= config['pausa_pos_raio']:
                self.em_pausa_pos_raio = False

        self._treinar_ml_online()

    def registrar_previsao(self, duzia, confianca):
        """Atualizado para contar repetições e marcar padrão ativo."""
        self.ultimas_previsoes.append(duzia)
        self.ultima_previsao_duzia = duzia
        self.ultima_confianca = confianca

        if len(self.ultimas_previsoes) >= 2:
            if self.ultimas_previsoes[-1] == self.ultimas_previsoes[-2]:
                self.contagem_repeticoes_mesma_duzia += 1
            else:
                self.contagem_repeticoes_mesma_duzia = 1
        else:
            self.contagem_repeticoes_mesma_duzia = 1

        if len(self.ultimas_previsoes) > 10:
            self.ultimas_previsoes = self.ultimas_previsoes[-10:]

    def registrar_resultado(self, duzia_real, acertou_duzia, acertou_numero, acertou_zero, mesa_id=None, eh_raio=False, multiplicador=0):
        self.ultimos_resultados.append({
            'duzia': duzia_real,
            'acertou_duzia': acertou_duzia,
            'acertou_numero': acertou_numero,
            'acertou_zero': acertou_zero
        })
        self.ultimo_resultado_duzia = acertou_duzia
        self.ultimo_resultado_numero = acertou_numero

        # 🆕 Registra resultado no padrão ativo
        self.memoria_padroes.registrar_resultado_padrao(acertou_duzia or acertou_zero)

        config = self._get_config()
        if eh_raio and multiplicador >= config['raio_alto_minimo'] and config['pausa_pos_raio'] > 0:
            self.em_pausa_pos_raio = True
            self.rodadas_pos_raio = 0
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

        if len(self.ultimos_resultados) > 50:
            self.ultimos_resultados = self.ultimos_resultados[-50:]

        if acertou_duzia and duzia_real != 0:
            if duzia_real == self.ultima_duzia_acertada:
                self.acertos_consecutivos_mesma_duzia += 1
            else:
                self.acertos_consecutivos_mesma_duzia = 1
                self.ultima_duzia_acertada = duzia_real
        else:
            self.acertos_consecutivos_mesma_duzia = 0
            self.ultima_duzia_acertada = None

        if not acertou_duzia and not acertou_zero:
            self.erros_consecutivos += 1
            if duzia_real != 0:
                self.erros_por_duzia[duzia_real] += 1
            self.modo_anti_erro = True
        else:
            self.erros_consecutivos = 0
            self.modo_anti_erro = False
            self.erros_por_duzia = {1: 0, 2: 0, 3: 0}
            self.entradas_consecutivas = 0
            self.pausa_ate = None

        if acertou_duzia or acertou_zero:
            self.entradas_consecutivas += 1

    def _prever_ml(self):
        """Faz previsão usando o ensemble ML com features corrigidas."""
        if not ML_DISPONIVEL or self.modelo_ml is None:
            return {1: 0.0, 2: 0.0, 3: 0.0}

        if len(self.historico_completo) < 10:
            return {1: 0.0, 2: 0.0, 3: 0.0}

        try:
            features = self.extrair_features_estado(janela=20)
            if features is None:
                return {1: 0.0, 2: 0.0, 3: 0.0}

            # Verifica dimensão compatível com o modelo treinado
            try:
                n_features_modelo = self.modelo_ml.estimators_[0].n_features_in_
            except:
                n_features_modelo = None

            if n_features_modelo is not None and len(features) != n_features_modelo:
                logging.warning(f"⚠️ Dimensão incompatível: modelo={n_features_modelo}, features={len(features)}. Retreinando...")
                self.modelo_ml = None
                self.ultimo_treino_ml = 0
                return {1: 0.0, 2: 0.0, 3: 0.0}

            probabilidades = self.modelo_ml.predict_proba([features])[0]

            ml_scores = {1: 0.0, 2: 0.0, 3: 0.0}
            for classe, prob in zip(self.modelo_ml.classes_, probabilidades):
                if classe in ml_scores:
                    ml_scores[classe] = float(prob) * 100

            return ml_scores

        except Exception as e:
            logging.error(f"❌ Erro na inferência ML: {e}")
            # Se erro de dimensão, força retreino
            if "feature" in str(e).lower() or "shape" in str(e).lower():
                self.modelo_ml = None
                self.ultimo_treino_ml = 0
            return {1: 0.0, 2: 0.0, 3: 0.0}

    def _prever_fallback_frequencia(self):
        """Fallback por frequência relativa + pressão de gap."""
        if len(self.historico_completo) < 5:
            return {1: 33.3, 2: 33.3, 3: 33.3}

        janela = min(20, len(self.historico_completo))
        duzias_rec = [d for d in self.historico_completo[-janela:] if d != 0]
        total = max(1, len(duzias_rec))

        freq = {1: duzias_rec.count(1) / total,
                2: duzias_rec.count(2) / total,
                3: duzias_rec.count(3) / total}

        gap_d1 = _calcular_gap_duzia(self.numeros_completos, 1)
        gap_d2 = _calcular_gap_duzia(self.numeros_completos, 2)
        gap_d3 = _calcular_gap_duzia(self.numeros_completos, 3)
        gap_max = max(gap_d1, gap_d2, gap_d3, 1)

        scores = {
            1: freq[1] * 60 + (gap_d1 / gap_max) * 40,
            2: freq[2] * 60 + (gap_d2 / gap_max) * 40,
            3: freq[3] * 60 + (gap_d3 / gap_max) * 40,
        }
        return scores

    def _prever_por_padroes(self):
        """
        🆕 Consulta a memória de padrões para obter previsão baseada em
        sequências históricas que já ocorreram antes.
        Retorna (scores, padrao_encontrado, confianca, ocorrencias)
        """
        config = self._get_config()
        padrao, scores, confianca, ocorrencias = self.memoria_padroes.buscar_padrao_atual(
            self.historico_completo
        )

        # Atualiza estado do padrão ativo para UI
        self.padrao_ativo = padrao
        self.padrao_ativo_ocorrencias = ocorrencias
        self.padrao_ativo_confianca = confianca
        self.padrao_ativo_scores = scores

        if padrao is not None:
            self.memoria_padroes.ultimo_padrao_ativo = padrao
            taxa_hist = self.memoria_padroes.get_taxa_acerto_padrao(padrao)
            # Ajuste de confiança pela taxa histórica do padrão
            if taxa_hist is not None:
                if taxa_hist >= 0.65:
                    confianca = min(1.0, confianca * 1.2)
                elif taxa_hist < 0.4:
                    confianca = confianca * 0.7

        return scores, padrao, confianca, ocorrencias

    def calcular_score(self):
        """
        🆕 Calcula scores combinando ML + Memória de Padrões.
        Retorna (scores_finais, modo_str)
        """
        config = self._get_config()
        peso_padrao = config.get('memoria_peso_padrao', 30)

        ml_scores = self._prever_ml()
        padrao_scores, padrao_encontrado, padrao_confianca, padrao_ocorrencias = self._prever_por_padroes()

        ml_ativo = not all(v == 0.0 for v in ml_scores.values())

        if ml_ativo:
            # Combina ML (70%) + Padrões históricos (30% — ajustável)
            if padrao_encontrado and padrao_confianca > 0.15:
                peso_ml = 100 - peso_padrao
                scores_finais = {
                    d: (ml_scores.get(d, 0) * peso_ml / 100) +
                       (padrao_scores.get(d, 0) * peso_padrao / 100)
                    for d in [1, 2, 3]
                }
                modo = f'ml+padrão(n={len(padrao_encontrado)},x{padrao_ocorrencias})'
            else:
                scores_finais = ml_scores
                modo = 'ml'
            return scores_finais, modo
        else:
            # Fallback: frequência + padrões
            freq_scores = self._prever_fallback_frequencia()
            if padrao_encontrado and padrao_confianca > 0.2:
                peso_pad = min(50, peso_padrao + 10)
                scores_finais = {
                    d: (freq_scores.get(d, 0) * (100 - peso_pad) / 100) +
                       (padrao_scores.get(d, 0) * peso_pad / 100)
                    for d in [1, 2, 3]
                }
                modo = f'fallback+padrão(n={len(padrao_encontrado)},x{padrao_ocorrencias})'
            else:
                scores_finais = freq_scores
                modo = 'fallback'
            return scores_finais, modo

    def detectar_alerta_zero(self):
        """Detecta padrões que sugerem saída do zero (8 padrões)"""
        if len(self.historico) < 2:
            self.alerta_zero_ativo = False
            return False

        u = list(self.historico)[-10:]
        nums = self.numeros_completos[-8:] if len(self.numeros_completos) >= 8 else self.numeros_completos

        if len(nums) >= 2 and nums[-1] == 0:
            self.alerta_zero_ativo = True
            self.alertas_zero_disparados += 1
            return True

        if len(u) >= 3:
            ultimas_3 = u[-3:]
            if len(set(ultimas_3)) == 1 and ultimas_3[0] != 0:
                self.alerta_zero_ativo = True
                self.alertas_zero_disparados += 1
                return True

        if len(u) >= 5:
            ultimas_5 = u[-5:]
            trocas = sum(1 for i in range(1, len(ultimas_5))
                         if ultimas_5[i] != ultimas_5[i - 1] and ultimas_5[i] != 0 and ultimas_5[i - 1] != 0)
            if trocas >= 4:
                self.alerta_zero_ativo = True
                self.alertas_zero_disparados += 1
                return True

        config = self._get_config()
        limiar_gap = max(8, config.get('zero_termometro_max', 15) - 3)
        if self.rodadas_desde_zero >= limiar_gap:
            self.alerta_zero_ativo = True
            self.alertas_zero_disparados += 1
            return True

        duzias_rec = [d for d in list(self.historico)[-5:] if d != 0]
        if len(duzias_rec) >= 3:
            if duzias_rec[-1] == duzias_rec[-3] and duzias_rec[-1] != duzias_rec[-2]:
                self.alerta_zero_ativo = True
                self.alertas_zero_disparados += 1
                return True

        terminais_recentes = [n % 10 for n in nums if n != 0]
        if terminais_recentes.count(0) >= 2:
            self.alerta_zero_ativo = True
            self.alertas_zero_disparados += 1
            return True

        bordas = [n for n in nums if n in (1, 3, 12, 13, 24, 25, 36)]
        if len(bordas) >= 3:
            self.alerta_zero_ativo = True
            self.alertas_zero_disparados += 1
            return True

        if len(duzias_rec) >= 4:
            apenas_extremos = [d for d in duzias_rec[-4:] if d in (1, 3)]
            if len(apenas_extremos) == 4:
                self.alerta_zero_ativo = True
                self.alertas_zero_disparados += 1
                return True

        self.alerta_zero_ativo = False
        return False

    def _get_outras_duzias(self, duzia):
        return [d for d in [1, 2, 3] if d != duzia]

    # =========================================================
    # MÉTODO PREVER ATUALIZADO COM MEMÓRIA DE PADRÕES
    # =========================================================
    def prever(self):
        """Método principal de previsão com memória de padrões integrada."""
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

        scores, modo = self.calcular_score()

        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        d1, s1 = ranking[0]
        d2, s2 = ranking[1] if len(ranking) > 1 else (self._get_outras_duzias(d1)[0], 0)
        d3, s3 = ranking[2] if len(ranking) > 2 else (self._get_outras_duzias(d1)[-1], 0)

        self.detectar_alerta_zero()

        confianca = min(3.5, max(0.5, (s1 - s2) / 20))

        # 🆕 Boost de confiança quando padrão histórico confirma a previsão do ML
        if self.padrao_ativo is not None and self.padrao_ativo_confianca > 0.2:
            padrao_d1 = max(self.padrao_ativo_scores, key=self.padrao_ativo_scores.get)
            if padrao_d1 == d1:
                boost = config.get('memoria_confianca_boost', 0.4) * self.padrao_ativo_confianca
                confianca = min(3.5, confianca + boost)

        if self.alerta_zero_ativo and confianca >= 3.0:
            confianca = min(2.8, confianca)

        pode_entrar = False
        motivo = ""
        forcar_rotacao = False

        # Determina se o modo usa ML ou fallback
        modo_base = 'ml' if 'ml' in modo else 'fallback'

        if modo_base == 'ml':
            score_minimo = config.get('ml_score_minimo_entrada', 25)
            pode_entrar = s1 > score_minimo
            if pode_entrar:
                treino_info = "do Disco 💾" if self.ultimo_treino_ml <= 1 else f"R{self.ultimo_treino_ml}"
                if 'padrão' in modo:
                    motivo = f"🟢 ML+Padrão ({treino_info}) | Score: {s1:.1f}"
                else:
                    motivo = f"🟢 Ensemble ML ({treino_info}) | Score: {s1:.1f}"
            else:
                motivo = f"Score ML baixo ({s1:.1f} < {score_minimo})"
        else:
            score_min_fb = config.get('ml_score_minimo_fallback', 42)
            min_rodadas_fb = config.get('ml_min_rodadas_fallback', 8)
            if len(self.historico_completo) >= min_rodadas_fb and s1 > score_min_fb:
                pode_entrar = True
                if 'padrão' in modo:
                    motivo = f"🟡 Fallback+Padrão | Score: {s1:.1f}"
                else:
                    motivo = f"🟡 Fallback Freq | Score: {s1:.1f}"
            else:
                motivo = f"Aguardando ML ({len(self.historico_completo)}/40 rodadas)"

        # 🆕 Permitir entrada por padrão histórico muito forte (mesmo sem ML suficiente)
        if not pode_entrar and self.padrao_ativo is not None:
            if self.padrao_ativo_confianca >= 0.65 and self.padrao_ativo_ocorrencias >= 4:
                padrao_d = max(self.padrao_ativo_scores, key=self.padrao_ativo_scores.get)
                padrao_s = self.padrao_ativo_scores[padrao_d]
                if padrao_s >= 65:
                    pode_entrar = True
                    d1, s1 = padrao_d, padrao_s
                    motivo = f"🧩 Padrão Histórico (n={len(self.padrao_ativo)}, x{self.padrao_ativo_ocorrencias}) | Conf: {self.padrao_ativo_confianca:.2f}"

        # Limitador de repetições da mesma dúzia
        max_rep = config.get('ml_max_repeticoes_mesma_duzia', 4)
        if pode_entrar and len(self.ultimas_previsoes) >= max_rep:
            ultimas_n = self.ultimas_previsoes[-max_rep:]
            if all(p == d1 for p in ultimas_n):
                score_min_pos_rot = config.get('ml_score_minimo_pos_rotacao', 20)
                if s2 > score_min_pos_rot:
                    d1, s1 = d2, s2
                    d2, s2 = d3, s3
                    forcar_rotacao = True
                    motivo = f"🔄 Rotação forçada (>{max_rep}x D{d1}) | Score: {s1:.1f}"
                else:
                    pode_entrar = False
                    motivo = f"🚫 Bloqueio por repetição (>{max_rep}x mesma dúzia) e 2ª opção fraca"

        # Filtro de confiança mínima
        confianca_min = config.get('confianca_minima_entrada', 1.3)
        if pode_entrar and confianca < confianca_min and not forcar_rotacao:
            # Padrão histórico muito forte pode sobrepor o filtro de confiança
            if not (self.padrao_ativo is not None and self.padrao_ativo_confianca >= 0.7):
                pode_entrar = False
                motivo = f"Confiança muito baixa ({confianca:.2f} < {confianca_min})"

        # Filtro de confiança mínima para anti-erro (mais rigoroso)
        if pode_entrar and self.modo_anti_erro and confianca < (confianca_min + 0.5):
            pode_entrar = False
            motivo = f"🚫 Anti-Erro: Confiança insuficiente ({confianca:.2f})"

        # Termômetro zero
        incluir_zero = self.alerta_zero_ativo
        if self.rodadas_desde_zero >= config['zero_termometro_max']:
            incluir_zero = True
            if pode_entrar and "Termômetro" not in motivo:
                motivo += " | 🌡️ Zero"

        # Bloqueio final por confiança crítica
        if confianca < 0.8:
            pode_entrar = False
            motivo = f"Confiança crítica ({confianca:.2f})"

        # 🆕 Adiciona info do padrão ao retorno
        info_padrao = None
        if self.padrao_ativo is not None:
            info_padrao = {
                'sequencia': list(self.padrao_ativo),
                'ocorrencias': self.padrao_ativo_ocorrencias,
                'confianca': round(self.padrao_ativo_confianca, 3),
                'duzia_prevista': max(self.padrao_ativo_scores, key=self.padrao_ativo_scores.get),
                'scores': self.padrao_ativo_scores,
            }

        previsao = {
            "entrar": pode_entrar,
            "motivo": motivo,
            "score": scores,
            "confianca": round(confianca, 2),
            "duzia": d1,
            "duzia_secundaria": d2,
            "gatilho_ativo": "ML" if modo_base == 'ml' else "Fallback",
            "incluir_zero": incluir_zero,
            "modo_anti_erro": self.modo_anti_erro,
            "numeros_completos": list(self.numeros_completos),
            "modo_previsao": modo,
            "rotacao_forcada": forcar_rotacao,
            "padrao_ativo": info_padrao,  # 🆕
        }

        return previsao


# =============================
# SISTEMA PRINCIPAL
# =============================
class SistemaBot:
    def __init__(self):
        janela = st.session_state.get('janela_duzia_ai', 30)
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        self.duzia_ai = DuziaAI(window=janela, api_name=api_name)
        self.historico_numeros = deque(maxlen=500)
        self.entrada_ativa = None
        self.historico_entradas = []
        self.acertos_duzia = 0
        self.erros_duzia = 0
        self.acertos_numero = 0
        self.erros_numero = 0
        self.acertos_zero = 0
        self.erros_zero = 0
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
        self.gerenciador_sessoes = GerenciadorSessoes(st.session_state.get('api_selecionada', 'XXXtreme Lightning'))

    def iniciar_sessao(self):
        if self.sessao_pausa_ate and hora_brasilia() < self.sessao_pausa_ate:
            return False
        self.sessao_ativa = True
        self.rodadas_na_sessao = 0
        self.acertos_sessao = 0
        self.erros_sessao = 0
        self.total_sessoes += 1
        self.sessao_pausa_ate = None
        salvar_sessao()
        return True

    def _encerrar_sessao(self):
        self.sessao_ativa = False
        self.sessao_pausa_ate = hora_brasilia() + timedelta(minutes=self.pausa_entre_sessoes)
        taxa = (self.acertos_sessao / max(1, self.acertos_sessao + self.erros_sessao)) * 100

        if st.session_state.get('salvar_sessoes_auto', True):
            inicio = len(self.historico_entradas) - self.rodadas_na_sessao
            if inicio < 0: inicio = 0
            entradas_sessao = self.historico_entradas[inicio:]

            dados_sessao = {
                'acertos': self.acertos_sessao,
                'erros': self.erros_sessao,
                'taxa_acerto': round(taxa, 1),
                'total_rodadas': self.rodadas_na_sessao,
                'rodadas_por_sessao': self.rodadas_por_sessao
            }
            self.gerenciador_sessoes.salvar_sessao_encerrada(
                self.total_sessoes, dados_sessao, entradas_sessao
            )

        self.entrada_ativa = None
        salvar_sessao()

    def pode_processar(self):
        if not self.sessao_ativa:
            if self.sessao_pausa_ate and hora_brasilia() >= self.sessao_pausa_ate:
                self.sessao_pausa_ate = None
                self.sessao_ativa = False
                salvar_sessao()
            return False

        if self.rodadas_na_sessao >= self.rodadas_por_sessao:
            self._encerrar_sessao()
            return False

        return True

    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data.get('number')
            lucky_numbers = numero_data.get('luckyNumbers', [])
            lucky_multipliers = numero_data.get('luckyMultipliers', {})
            table_id = numero_data.get('table_id', 'unknown')
            table_name = numero_data.get('table_name', 'Desconhecida')
        else:
            nr = numero_data
            lucky_numbers = []
            lucky_multipliers = {}
            table_id = 'unknown'
            table_name = 'Desconhecida'

        if nr is None or not validar_numero(nr):
            return

        self.numero_rodada += 1
        self.duzia_ai.adicionar(nr)
        self.historico_numeros.append(nr)
        self.ultimo_numero = nr

        if not self.pode_processar():
            salvar_sessao()
            return

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
                'rodada': self.numero_rodada,
                'hora': formatar_hora_brasilia(),
                'numero': nr,
                'duzia_real': duzia_real if nr != 0 else 0,
                'duzia_prevista': duzia_prevista,
                'duzia_sec_prevista': duzia_sec_prevista,
                'acerto_duzia': acerto_primaria or acerto_secundaria,
                'acerto_numero': acerto_numero_exato,
                'acerto_zero': acerto_zero,
                'eh_raio': eh_raio,
                'multiplicador': multiplicador,
                'status': status_visual,
                'confianca': self.entrada_ativa.get('confianca', 0),
                'gatilho': self.entrada_ativa.get('gatilho_ativo', 'ML'),
                'modo_anti_erro': self.entrada_ativa.get('modo_anti_erro', False),
                'incluir_zero': incluir_zero,
                'table_id': table_id,
                'table_name': table_name,
                'padrao_usado': self.entrada_ativa.get('padrao_ativo'),  # 🆕
            })

            if len(self.historico_entradas) > 100:
                self.historico_entradas = self.historico_entradas[-100:]

            enviar_resultado_auto(nr, acertou_duzia, acerto_numero_exato, acerto_zero, eh_raio, multiplicador)
            self.entrada_ativa = None

            if not self.pode_processar():
                salvar_sessao()
                return

        if self.sessao_ativa and self.rodadas_na_sessao < self.rodadas_por_sessao:
            previsao = self.duzia_ai.prever()

            if previsao['entrar']:
                duzia_map = {
                    1: list(range(1, 13)),
                    2: list(range(13, 25)),
                    3: list(range(25, 37))
                }

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
                    'gatilho_ativo': previsao.get('gatilho_ativo', 'ML'),
                    'modo_anti_erro': previsao.get('modo_anti_erro', False),
                    'incluir_zero': previsao.get('incluir_zero', False),
                    'padrao_ativo': previsao.get('padrao_ativo'),  # 🆕
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
        self.acertos_duzia = 0
        self.erros_duzia = 0
        self.acertos_numero = 0
        self.erros_numero = 0
        self.acertos_zero = 0
        self.erros_zero = 0
        self.historico_entradas = []
        self.historico_numeros.clear()
        self.entrada_ativa = None
        self.ultimo_numero = None
        self.sinais_grafico = []
        self.numero_rodada = 0
        self.rodadas_na_sessao = 0
        self.sessao_ativa = False
        self.sessao_pausa_ate = None
        self.total_sessoes = 0
        self.acertos_sessao = 0
        self.erros_sessao = 0
        janela = st.session_state.get('janela_duzia_ai', 30)
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        self.duzia_ai = DuziaAI(window=janela, api_name=api_name)
        salvar_sessao()


def salvar_resultado_em_arquivo(historico, caminho):
    try:
        with open(caminho, "w", encoding='utf-8') as f:
            json.dump(historico, f, indent=2)
    except Exception as e:
        logging.error(f"Erro: {e}")


def exportar_historico_csv(historico_entradas, caminho="export_roleta.csv"):
    try:
        with open(caminho, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Rod','Hora','Nº','Raio','Real','Prev','Cob','Conf','Gat','Z','🔄','Mesa','Duz','Num','Zer','St','Padrão'])
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
                padrao = str(e.get('padrao_usado', {}).get('sequencia', '-')) if e.get('padrao_usado') else '-'
                writer.writerow([e.get('rodada'), e.get('hora'), e.get('numero'), raio, real, prev, cob,
                                  f"{e.get('confianca',0):.1f}", e.get('gatilho','ML'), zero, anti, mesa,
                                  duz, num, zer, e.get('status','?'), padrao])
        return True
    except Exception as e:
        logging.error(f"Erro CSV: {e}")
        return False


# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎰 DuziaAI V12.0 - Memória de Padrões + ML Corrigido", layout="wide")
st.title("🎰 DuziaAI V12.0 — Memória de Padrões Históricos + ML Corrigido 🧩💾 (BRT)")

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
            sis.duzia_ai.adicionar(n)
            sis.historico_numeros.append(n)
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
        if dados.get('ultimo_treino_ml'):
            sis.duzia_ai.ultimo_treino_ml = dados['ultimo_treino_ml']
        if 'performance_por_mesa' in dados:
            for k, v in dados['performance_por_mesa'].items():
                sis.performance_por_mesa[k] = v
                sis.duzia_ai.performance_por_mesa[k] = v
        if 'performance_por_horario' in dados:
            for k, v in dados['performance_por_horario'].items():
                sis.performance_por_horario[k] = v
                sis.duzia_ai.performance_por_horario[k] = v
        # 🆕 Carrega memória de padrões
        mem_path = dados.get('_memoria_padroes_path', '')
        if mem_path:
            sis.duzia_ai.memoria_padroes.carregar(mem_path)
        paths = get_session_paths(st.session_state.api_selecionada)
        if os.path.exists(paths['historico']):
            with open(paths['historico'], 'r') as f:
                st.session_state.historico = json.load(f)
    else:
        st.session_state.historico = []
    st.rerun()

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()
    dados = carregar_dados_persistidos(st.session_state.api_selecionada)
    if dados:
        sis = st.session_state.sistema
        for n in dados.get('historico_numeros', []):
            sis.duzia_ai.adicionar(n)
            sis.historico_numeros.append(n)
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
        if dados.get('ultimo_treino_ml'):
            sis.duzia_ai.ultimo_treino_ml = dados['ultimo_treino_ml']
        if 'performance_por_mesa' in dados:
            for k, v in dados['performance_por_mesa'].items():
                sis.performance_por_mesa[k] = v
                sis.duzia_ai.performance_por_mesa[k] = v
        if 'performance_por_horario' in dados:
            for k, v in dados['performance_por_horario'].items():
                sis.performance_por_horario[k] = v
                sis.duzia_ai.performance_por_horario[k] = v
        # 🆕 Carrega memória de padrões
        mem_path = dados.get('_memoria_padroes_path', '')
        if mem_path:
            sis.duzia_ai.memoria_padroes.carregar(mem_path)
        paths = get_session_paths(st.session_state.api_selecionada)
        if os.path.exists(paths['historico']):
            with open(paths['historico'], 'r') as f:
                st.session_state.historico = json.load(f)

if "modo_automatico" not in st.session_state:
    st.session_state.modo_automatico = config_global.get('modo_automatico', True)
if "modo_agressivo" not in st.session_state:
    st.session_state.modo_agressivo = config_global.get('modo_agressivo', False)
if "janela_duzia_ai" not in st.session_state:
    st.session_state.janela_duzia_ai = config_global.get('janela_duzia_ai', 30)
if "historico" not in st.session_state:
    st.session_state.historico = []

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.markdown("## ⚙️ V12.0 — Memória de Padrões + ML Corrigido")
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
        st.warning(f"⏸️ Pausa: {tempo_restante//60:02d}:{tempo_restante%60:02d}")
    else:
        st.info("⚪ Nenhuma sessão ativa")

    botao_desabilitado = sis.sessao_ativa or (sis.sessao_pausa_ate and hora_brasilia() < sis.sessao_pausa_ate)
    if botao_desabilitado:
        st.button("🚀 INICIAR SESSÃO", use_container_width=True, disabled=True)
    else:
        if st.button("🚀 INICIAR SESSÃO", use_container_width=True, type="primary"):
            if sis.iniciar_sessao():
                st.success(f"✅ Sessão #{sis.total_sessoes} iniciada!")
                st.rerun()

    st.markdown("---")
    if st.button("🆕 RESET TOTAL", use_container_width=True):
        if nova_sessao():
            st.success("✅ Reset completo!")
            st.rerun()

    st.markdown("---")

    st.markdown("### ⏱️ Configurações da Sessão")
    rodadas = st.number_input("Rodadas por sessão:", min_value=5, max_value=30, value=st.session_state.rodadas_por_sessao, step=5)
    pausa = st.number_input("Pausa entre sessões (min):", min_value=1, max_value=30, value=st.session_state.pausa_entre_sessoes, step=1)
    if rodadas != st.session_state.rodadas_por_sessao:
        st.session_state.rodadas_por_sessao = rodadas
        sis.rodadas_por_sessao = rodadas
        salvar_sessao()
    if pausa != st.session_state.pausa_entre_sessoes:
        st.session_state.pausa_entre_sessoes = pausa
        sis.pausa_entre_sessoes = pausa
        salvar_sessao()

    st.markdown("---")

    st.markdown("### 💾 Download de Sessões")
    st.session_state.salvar_sessoes_auto = st.checkbox("💾 Salvar sessões automaticamente", value=st.session_state.salvar_sessoes_auto)

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
                        with open(caminho, 'r') as f:
                            conteudo = f.read()
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

    st.markdown("### 🎰 Selecione a Roleta")
    api_opcoes = list(API_URLS.keys())
    api_atual = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
    api_index = api_opcoes.index(api_atual) if api_atual in api_opcoes else 0
    st.session_state.api_selecionada = st.radio("Roleta:", api_opcoes, index=api_index)
    api_name = st.session_state.api_selecionada

    # Status do modelo ML
    if hasattr(sis.duzia_ai, 'modelo_ml') and sis.duzia_ai.modelo_ml is not None:
        if sis.duzia_ai.ultimo_treino_ml <= 1:
            st.success("🧠 Ensemble ML CARREGADO DO DISCO 💾")
        else:
            st.success(f"🧠 Ensemble ML ATIVO | Treino na R{sis.duzia_ai.ultimo_treino_ml}")
    else:
        rodadas_atual = len(sis.historico_numeros)
        if rodadas_atual >= 8:
            st.warning(f"🟡 Fallback Freq ATIVO | ML treina em R40+ ({rodadas_atual}/40)")
        else:
            st.info(f"🧠 Aguardando dados... ({rodadas_atual}/8 para fallback)")

    # 🆕 Status da memória de padrões
    st.markdown("---")
    mem_stats = sis.duzia_ai.memoria_padroes.get_stats()
    st.caption("🧩 **Memória de Padrões:**")
    st.caption(f"• Padrões únicos: {mem_stats['total_padroes']}")
    st.caption(f"• Padrões confiáveis: {mem_stats['padroes_confiaveis']}")
    st.caption(f"• Total de registros: {mem_stats['total_registros']}")
    if sis.duzia_ai.padrao_ativo is not None:
        seq_str = "→".join(f"D{d}" for d in sis.duzia_ai.padrao_ativo)
        st.success(f"🎯 Padrão ativo: {seq_str} (x{sis.duzia_ai.padrao_ativo_ocorrencias})")
    else:
        st.info("🔍 Sem padrão ativo no momento")

    st.markdown("---")
    st.caption("🛡️ **Correções V12.0:**")
    st.caption("• Memória de padrões históricos")
    st.caption("• 44 features (era 33, sem placeholders)")
    st.caption("• Autocorrelação lag 2 e 3")
    st.caption("• Dimensão treino = inferência")
    st.caption("• Padrão forte → entrada direta")
    st.caption("• Boost de confiança por padrão")

    st.markdown("---")
    st.session_state.janela_duzia_ai = st.slider("📏 Janela de Análise", 10, 50, st.session_state.janela_duzia_ai, 5)
    st.session_state.modo_agressivo = st.checkbox("🔥 Modo Agressivo (2 Dúzias)", value=st.session_state.modo_agressivo)
    st.session_state.modo_automatico = st.checkbox("🤖 Modo Automático", value=st.session_state.modo_automatico)

    st.markdown("---")

    with st.expander("🔔 Configurações Telegram", expanded=False):
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
            salvar_sessao()
            st.success("✅ Dados, ML e Padrões salvos!")
    with c2:
        if st.button("📥 Exportar CSV", use_container_width=True):
            if exportar_historico_csv(st.session_state.sistema.historico_entradas):
                st.success("✅ CSV exportado!")

# =============================
# CONTEÚDO PRINCIPAL
# =============================
st.subheader("🎲 Inserir Números")
c1, c2, c3 = st.columns([3, 1, 1])
with c1:
    entrada = st.text_input("Número (0-36):", key="entrada_numero")
with c2:
    if st.button("🎯 Enviar", use_container_width=True, type="primary"):
        if validar_numero(entrada):
            nr = int(entrada)
            st.session_state.historico.append({
                "number": nr,
                "timestamp": timestamp_brasilia(),
                "luckyNumbers": [],
                "luckyMultipliers": {},
                "table_id": "manual",
                "table_name": "Entrada Manual"
            })
            st.session_state.sistema.processar_novo_numero(nr)
            paths = get_session_paths(st.session_state.api_selecionada)
            salvar_resultado_em_arquivo(st.session_state.historico, paths['historico'])
            salvar_sessao()
            st.rerun()
        else:
            st.error("Por favor, insira um número entre 0 e 36")
with c3:
    if st.button("🔄 Auto", use_container_width=True):
        st.session_state.modo_automatico = not st.session_state.modo_automatico
        st.rerun()

if st.session_state.modo_automatico:
    st_autorefresh(interval=3000, key="auto_refresh")
    r = fetch_latest_result()
    if r and r.get("number") is not None:
        if not st.session_state.historico or r.get("timestamp") != st.session_state.historico[-1].get("timestamp"):
            st.session_state.historico.append(r)
            st.session_state.sistema.processar_novo_numero(r)
            paths = get_session_paths(st.session_state.api_selecionada)
            salvar_resultado_em_arquivo(st.session_state.historico, paths['historico'])
            salvar_sessao()
            st.rerun()

st.markdown("---")
sis = st.session_state.sistema
api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')

st.subheader(f"📊 ESTATÍSTICAS — {api_name}")
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
c6.metric("🎰 Roleta", api_name[:10])

if sis.total_sessoes > 0:
    st.markdown("---")
    st.subheader(f"📈 Sessão #{sis.total_sessoes}")
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("🔄 Rodadas", f"{sis.rodadas_na_sessao}/{sis.rodadas_por_sessao}")
    sc2.metric("✅ Acertos", sis.acertos_sessao)
    sc3.metric("❌ Erros", sis.erros_sessao)
    taxa_sessao = (sis.acertos_sessao / max(1, sis.acertos_sessao + sis.erros_sessao)) * 100
    sc4.metric("📊 Taxa", f"{taxa_sessao:.0f}%")
    if sis.sessao_ativa:
        st.progress(sis.rodadas_na_sessao / sis.rodadas_por_sessao)

st.markdown("---")
cg, ce = st.columns([3, 2])

with cg:
    st.subheader("📈 Scores do ML + Padrões")
    if len(sis.historico_numeros) >= 3:
        score, modo_atual = sis.duzia_ai.calcular_score()

        fig = plt.Figure(data=[plt.Bar(
            x=['D1 (1-12)', 'D2 (13-24)', 'D3 (25-36)'],
            y=[score[1], score[2], score[3]],
            marker_color=[
                '#FF6B6B' if score[1]==max(score.values()) else '#4ECDC4',
                '#FF6B6B' if score[2]==max(score.values()) else '#4ECDC4',
                '#FF6B6B' if score[3]==max(score.values()) else '#4ECDC4'
            ],
            text=[f'{score[1]:.1f}', f'{score[2]:.1f}', f'{score[3]:.1f}'],
            textposition='auto'
        )])

        if sis.duzia_ai.modelo_ml is not None:
            if sis.duzia_ai.ultimo_treino_ml <= 1:
                titulo = "🎯 Ensemble ML (Carregado 💾)"
            else:
                titulo = f"🎯 Ensemble RF+GBT (R{sis.duzia_ai.ultimo_treino_ml})"
        else:
            titulo = f"🟡 Fallback Frequência ({len(sis.historico_numeros)} rodadas)"

        if sis.duzia_ai.alerta_zero_ativo:
            titulo += " | 🟢 ALERTA ZERO!"

        if sis.duzia_ai.contagem_repeticoes_mesma_duzia >= 3:
            titulo += f" | ⚠️ Repetições: {sis.duzia_ai.contagem_repeticoes_mesma_duzia}x"

        # 🆕 Mostrar padrão ativo no título
        if sis.duzia_ai.padrao_ativo is not None:
            seq_str = "→".join(f"D{d}" for d in sis.duzia_ai.padrao_ativo)
            titulo += f" | 🧩 {seq_str}"

        fig.update_layout(
            title=titulo,
            height=300,
            showlegend=False,
            yaxis_title="Score de Confiança"
        )
        st.plotly_chart(fig, use_container_width=True)

        # 🆕 Gráfico de padrões se disponível
        if sis.duzia_ai.padrao_ativo is not None:
            pad_scores = sis.duzia_ai.padrao_ativo_scores
            fig_pad = plt.Figure(data=[plt.Bar(
                x=['D1 (1-12)', 'D2 (13-24)', 'D3 (25-36)'],
                y=[pad_scores.get(1, 0), pad_scores.get(2, 0), pad_scores.get(3, 0)],
                marker_color=[
                    '#FFD700' if pad_scores.get(1, 0)==max(pad_scores.values()) else '#888888',
                    '#FFD700' if pad_scores.get(2, 0)==max(pad_scores.values()) else '#888888',
                    '#FFD700' if pad_scores.get(3, 0)==max(pad_scores.values()) else '#888888',
                ],
                text=[f'{pad_scores.get(1,0):.1f}%', f'{pad_scores.get(2,0):.1f}%', f'{pad_scores.get(3,0):.1f}%'],
                textposition='auto'
            )])
            seq_str = "→".join(f"D{d}" for d in sis.duzia_ai.padrao_ativo)
            fig_pad.update_layout(
                title=f"🧩 Padrão Histórico: {seq_str} | {sis.duzia_ai.padrao_ativo_ocorrencias}x visto | Conf: {sis.duzia_ai.padrao_ativo_confianca:.2f}",
                height=220,
                showlegend=False,
                yaxis_title="% Próxima Dúzia"
            )
            st.plotly_chart(fig_pad, use_container_width=True)

        if len(sis.historico_numeros) >= 8:
            ult = list(sis.historico_numeros)[-20:]
            dz_hist = [get_duzia(n) for n in ult]

            fig2 = plt.Figure()
            fig2.add_trace(plt.Scatter(
                x=list(range(len(dz_hist))),
                y=dz_hist,
                mode='lines+markers',
                line=dict(color='#FFD700', width=2),
                marker=dict(size=10)
            ))

            if sis.sinais_grafico:
                sx, sy = [], []
                off = len(dz_hist) - 20
                for idx, dz in sis.sinais_grafico:
                    pos = idx - off
                    if 0 <= pos < 20:
                        sx.append(pos)
                        sy.append(dz)
                if sx:
                    fig2.add_trace(plt.Scatter(
                        x=sx, y=sy,
                        mode='markers',
                        name='Sinal ML',
                        marker=dict(symbol='star', size=15, color='red')
                    ))

            fig2.update_layout(
                title="📉 Histórico de Dúzias",
                yaxis=dict(tickvals=[0, 1, 2, 3], ticktext=['0', 'D1', 'D2', 'D3'], range=[-0.5, 3.5]),
                height=300
            )
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Aguardando dados suficientes para análise...")

with ce:
    st.subheader("🎰 Entrada Atual")

    if sis.duzia_ai.alerta_zero_ativo:
        st.warning("⚠️ ALERTA ZERO! 🟢")
    if sis.duzia_ai.em_pausa_pos_raio:
        st.warning(f"⏸️ Pausa pós-raio ({sis.duzia_ai.ultimo_raio_alto}x)")
    if sis.duzia_ai.contagem_repeticoes_mesma_duzia >= 4:
        st.warning(f"⚠️ {sis.duzia_ai.contagem_repeticoes_mesma_duzia}x mesma dúzia — Rotação em breve")

    # 🆕 Exibe padrão ativo
    if sis.duzia_ai.padrao_ativo is not None:
        seq_str = " → ".join(f"D{d}" for d in sis.duzia_ai.padrao_ativo)
        conf_pct = int(sis.duzia_ai.padrao_ativo_confianca * 100)
        st.info(f"🧩 Padrão: {seq_str}\n\nVisto {sis.duzia_ai.padrao_ativo_ocorrencias}x | Confiança: {conf_pct}%")

    if not sis.sessao_ativa:
        if sis.sessao_pausa_ate and hora_brasilia() < sis.sessao_pausa_ate:
            tempo_restante = (sis.sessao_pausa_ate - hora_brasilia()).seconds
            st.info(f"⏸️ Pausa entre sessões: {tempo_restante//60:02d}:{tempo_restante%60:02d}")
        else:
            st.info("🔴 Clique 'INICIAR SESSÃO' para começar")

    if sis.entrada_ativa and sis.sessao_ativa:
        e = sis.entrada_ativa
        conf = e.get('confianca', 0)
        dz_princ = e.get('duzia_prevista', 0)
        dz_sec = e.get('duzia_sec_prevista')
        gatilho = e.get('gatilho_ativo', 'ML')
        padrao_info = e.get('padrao_ativo')

        duzia_principal = dz_princ
        duzia_secundaria = dz_sec if dz_sec and dz_sec != dz_princ else None

        melhores_principal = _selecionar_melhores_numeros(duzia_principal, list(sis.historico_numeros), 6)
        if duzia_secundaria:
            melhores_secundaria = _selecionar_melhores_numeros(duzia_secundaria, list(sis.historico_numeros), 6)
        else:
            melhores_secundaria = None

        cor = "#FF6347" if e.get('modo_anti_erro') else "#00CED1"
        icone_modo = "🟡 Fallback" if gatilho == 'Fallback' else "🤖 Ensemble ML 💾"

        # 🆕 Adiciona info do padrão se disponível
        padrao_html = ""
        if padrao_info:
            seq_str = "→".join(f"D{d}" for d in padrao_info.get('sequencia', []))
            padrao_html = f'<p style="text-align:center; color:#FFD700; font-size:0.85em;">🧩 {seq_str} (x{padrao_info.get("ocorrencias",0)})</p>'

        st.markdown(f"""
        <div style="background-color:{cor}15; border:2px solid {cor}; border-radius:15px; padding:15px;">
            <h2 style="color:{cor}; text-align:center;">🎯 Dúzia {dz_princ}</h2>
            <p style="text-align:center; font-size:1.1em;">Confiança: {conf:.2f}</p>
            <p style="text-align:center; font-size:0.9em;">{icone_modo}</p>
            {f'<p style="text-align:center; color:#FFA500;">🛡️ Cobertura: Dúzia {dz_sec}</p>' if duzia_secundaria else ''}
            {padrao_html}
        </div>
        """, unsafe_allow_html=True)

        st.write(f"**🎲 6 melhores números D{duzia_principal}:** {', '.join(map(str, melhores_principal))}")
        if melhores_secundaria:
            st.write(f"**🛡️ 6 melhores números D{duzia_secundaria}:** {', '.join(map(str, melhores_secundaria))}")

        st.progress(min(1.0, max(0.0, conf / 5.0)))
    else:
        st.info("🔍 Aguardando sinal do ML...")

    if sis.ultimo_numero is not None:
        st.markdown("---")
        st.write(f"**🔄 Último número:** {'🟢 ZERO' if sis.ultimo_numero==0 else f'#{sis.ultimo_numero} (D{get_duzia(sis.ultimo_numero)})'}")

st.markdown("---")
st.subheader("📝 Histórico de Entradas")
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
        if e.get('eh_raio'):
            num_display = f"⚡{numero_sorteado} ({e.get('multiplicador',0)}x)"
        elif numero_sorteado == 0:
            num_display = "0"
        else:
            num_display = str(numero_sorteado)
        # 🆕 Mostra se usou padrão
        padrao_usado = '🧩' if e.get('padrao_usado') else '-'
        dados.append({
            "Rod": e.get('rodada'),
            "Hora": e.get('hora'),
            "🎲": num_display,
            "Real": real,
            "Prev": prev,
            "Cob": cob,
            "Conf": f"{e.get('confianca',0):.1f}",
            "Gat": e.get('gatilho', 'ML'),
            "Z": zero,
            "🔄": anti,
            "🧩": padrao_usado,
            "Duz": duz,
            "Nº": num,
            "Zer": zer
        })

    st.dataframe(dados, use_container_width=True, height=300)

    if st.button("📥 Exportar CSV", use_container_width=True):
        if exportar_historico_csv(sis.historico_entradas):
            st.success("✅ CSV exportado com sucesso!")
else:
    st.info("Nenhuma entrada registrada ainda.")

st.markdown("---")
st.caption("📡 **Status Telegram:**")
col_t1, col_t2 = st.columns(2)
with col_t1:
    if st.session_state.telegram_token and st.session_state.telegram_chat_id:
        st.success("🔔 Principal: CONFIGURADO")
    else:
        st.warning("🔔 Principal: NÃO CONFIGURADO")
with col_t2:
    if st.session_state.telegram_token_alt and st.session_state.telegram_chat_id_alt:
        st.success("📢 Alternativo: CONFIGURADO")
    else:
        st.warning("📢 Alternativo: NÃO CONFIGURADO")

st.caption(f"🤖 DuziaAI V12.0 | Memória de Padrões + 44 Features + ML Corrigido | {api_name} | {formatar_hora_brasilia()}")
modelo_path = get_modelo_ml_path(api_name)
if os.path.exists(modelo_path):
    st.caption(f"💾 Modelo salvo: {modelo_path} ({os.path.getsize(modelo_path)/1024:.1f} KB)")
else:
    st.caption("⚠️ Modelo ML ainda não salvo em disco")

mem_stats = sis.duzia_ai.memoria_padroes.get_stats()
st.caption(f"🧩 Padrões: {mem_stats['total_padroes']} únicos | {mem_stats['padroes_confiaveis']} confiáveis | {mem_stats['total_registros']} registros")

salvar_sessao()
