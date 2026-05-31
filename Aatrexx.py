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
    from sklearn.linear_model import SGDClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
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
# MELHORIA #5: DETECÇÃO DE VIÉS DINÂMICO
# =============================
def detectar_vies_dinamico(historico_completo, janela=30, limiar_excesso=0.15):
    duzias = [d for d in historico_completo[-janela:] if d != 0]
    if len(duzias) < 15:
        return None, 0.0
    total = len(duzias)
    freq = Counter(duzias)
    esperado = total / 3.0
    max_excesso = 0.0
    duzia_viés = None
    for d in [1, 2, 3]:
        excesso = (freq.get(d, 0) / total) - (1 / 3.0)
        if excesso > limiar_excesso and excesso > max_excesso:
            max_excesso = excesso
            duzia_viés = d
    return duzia_viés, round(max_excesso, 4)


# =============================
# MELHORIA #12: DECAIMENTO DE PADRÕES
# =============================
def aplicar_decaimento_padroes(tabela, fator=0.97):
    chaves_remover = []
    for chave, counter in tabela.items():
        novas_contagens = {}
        for k, v in counter.items():
            novo_v = v * fator
            if novo_v >= 0.5:
                novas_contagens[k] = novo_v
        if novas_contagens:
            tabela[chave] = Counter(novas_contagens)
        else:
            chaves_remover.append(chave)
    for chave in chaves_remover:
        del tabela[chave]


# =============================
# MELHORIA #14: FEATURES DE STREAK
# Detecta sequências de 1, 2 ou 3+ na mesma dúzia e
# extrai estatísticas para uso como features do ML
# =============================
def extrair_features_streak(historico_duzias):
    """
    Extrai features de streak (sequência) de qualquer dúzia.
    Retorna dict com 14 features para o ML.
    """
    duzias = [d for d in historico_duzias if d != 0]

    resultado = {
        'streak_atual_duzia': 0,
        'streak_atual_len': 0,
        'streak_duzia1_len': 0,
        'streak_duzia2_len': 0,
        'streak_duzia3_len': 0,
        'prob_continua_streak2': 0.5,
        'prob_continua_streak3': 0.5,
        'prob_quebra_streak2': 0.5,
        'prob_quebra_streak3': 0.5,
        'streak_max_recente': 0,
        'entrada_streak_duzia': 0,
        'cobertura_streak_duzia': 0,
        'streak_quebra_iminente': 0,
        'streak_forca': 0.0,
    }

    if len(duzias) < 3:
        return resultado

    # --- Streak atual ---
    streak_atual_len = 1
    streak_atual_duzia = duzias[-1]
    for d in reversed(duzias[:-1]):
        if d == streak_atual_duzia:
            streak_atual_len += 1
        else:
            break

    resultado['streak_atual_duzia'] = streak_atual_duzia
    resultado['streak_atual_len'] = streak_atual_len

    # Streak por dúzia
    for alvo in [1, 2, 3]:
        comprimento = 0
        for d in reversed(duzias):
            if d == alvo:
                comprimento += 1
            else:
                break
        resultado[f'streak_duzia{alvo}_len'] = comprimento

    # --- Maior streak nas últimas 30 rodadas ---
    recentes = duzias[-30:]
    max_streak = 1
    cur_streak = 1
    for i in range(1, len(recentes)):
        if recentes[i] == recentes[i-1]:
            cur_streak += 1
            max_streak = max(max_streak, cur_streak)
        else:
            cur_streak = 1
    resultado['streak_max_recente'] = max_streak

    # --- Probabilidade histórica de continuar ou quebrar streak ---
    continua2 = 0
    quebra2 = 0
    continua3 = 0
    quebra3 = 0

    for i in range(len(duzias) - 3):
        if duzias[i] == duzias[i+1]:
            if duzias[i+2] == duzias[i]:
                continua2 += 1
            else:
                quebra2 += 1
        if i + 3 < len(duzias) and duzias[i] == duzias[i+1] == duzias[i+2]:
            if duzias[i+3] == duzias[i]:
                continua3 += 1
            else:
                quebra3 += 1

    total2 = continua2 + quebra2
    total3 = continua3 + quebra3

    if total2 > 0:
        resultado['prob_continua_streak2'] = round(continua2 / total2, 4)
        resultado['prob_quebra_streak2'] = round(quebra2 / total2, 4)
    if total3 > 0:
        resultado['prob_continua_streak3'] = round(continua3 / total3, 4)
        resultado['prob_quebra_streak3'] = round(quebra3 / total3, 4)

    # --- Força do streak atual ---
    forca = min(1.0, streak_atual_len / 5.0)
    resultado['streak_forca'] = round(forca, 4)

    # --- Quebra iminente ---
    if streak_atual_len >= 3 and resultado['prob_quebra_streak3'] > 0.60:
        resultado['streak_quebra_iminente'] = 1

    # --- Recomendação de entrada/cobertura (apenas informativo) ---
    if streak_atual_len >= 2:
        outras = [d for d in [1, 2, 3] if d != streak_atual_duzia]
        freq_outras = Counter(duzias[-10:])
        cobertura = max(outras, key=lambda d: freq_outras.get(d, 0))

        if streak_atual_len == 2:
            if resultado['prob_continua_streak2'] >= 0.45:
                resultado['entrada_streak_duzia'] = streak_atual_duzia
            else:
                resultado['entrada_streak_duzia'] = cobertura
        elif streak_atual_len >= 3:
            if resultado['prob_quebra_streak3'] > 0.55:
                resultado['entrada_streak_duzia'] = cobertura
                resultado['streak_quebra_iminente'] = 1
            else:
                resultado['entrada_streak_duzia'] = streak_atual_duzia
        resultado['cobertura_streak_duzia'] = cobertura

    return resultado


# =============================
# SETUPS INDEPENDENTES POR ROLETA (CALIBRADOS)
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
    'ml_score_minimo_entrada': 30,
    'ml_score_minimo_fallback': 42,
    'ml_min_rodadas_fallback': 8,
    'ml_max_repeticoes_mesma_duzia': 3,
    'ml_score_minimo_pos_rotacao': 20,
    'padrao_min_ocorrencias': 3,
    'padrao_conf_minima_tam2': 2,
    'padrao_conf_minima_tam4': 6,
    'padrao_consenso_min_conf': 0.25,
    'anti_vies_ativo': False,
    'anti_vies_duzia': None,
    'anti_vies_penalidade': 1.0,
    'anti_vies_gatilho_p2': False,
    'anti_vies_p4_isolado_extra': 1.0,
    'peso_adaptativo_ativo': False,
    'peso_adaptativo_janela': 10,
    'peso_adaptativo_boost': 1.0,
    'vies_dinamico_ativo': True,
    'vies_dinamico_janela': 30,
    'vies_dinamico_limiar': 0.15,
    'vies_dinamico_penalidade': 0.80,
    'decaimento_padroes_ativo': True,
    'decaimento_fator': 0.97,
    'decaimento_a_cada': 5,
    'drift_janela': 15,
    'drift_taxa_minima': 0.35,
    'drift_alertar_apos': 5,
    # MELHORIA #14: streak settings
    'streak_ativo': True,
    'streak_min_len': 2,
    'streak_peso_feature': 1.0,
}

# 🟡 XXXTREME LIGHTNING
SETUP_XXXTREME = {
    **SETUP_BASE,
    'pagamento_numero': 20, 'pagamento_zero': 20, 'pagamento_duzia': 3,
    'confianca_minima_entrada': 2.2,
    'embalo_peso': 5, 'embalo_reforco': 2,
    'bloquear_alerta_zero_conf_alta': True, 'bloquear_anti_erro_zero_conf_baixa': True,
    'filtro_conf_baixa': 2.0, 'fadiga_duzia': 4,
    'ritmo_alternado_peso': 10, 'ritmo_alternado_forca': 10,
    'max_repeticoes_embalo': 3, 'confianca_maxima_segura': 3.1,
    'rodadas_verificacao_conf_alta': 5, 'pausa_pos_raio': 1, 'raio_alto_minimo': 100,
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
    'ml_score_minimo_entrada': 35,
    'ml_score_minimo_fallback': 42,
    'ml_min_rodadas_fallback': 10,
    'ml_max_repeticoes_mesma_duzia': 3,
    'ml_score_minimo_pos_rotacao': 20,
    'padrao_min_ocorrencias': 3,
    'padrao_peso_tam2': 15,
    'padrao_peso_tam3': 55,
    'padrao_peso_tam4': 30,
    'padrao_conf_minima_tam2': 2,
    'padrao_conf_minima_tam4': 8,
    'padrao_consenso_peso_extra': 15,
    'padrao_consenso_min_conf': 0.30,
    'ml_ignorar_consenso_conf_min': 3.0,
    'anti_vies_ativo': False,
    'peso_adaptativo_ativo': False,
    'vies_dinamico_ativo': True,
    'vies_dinamico_janela': 20,
    'vies_dinamico_limiar': 0.12,
    'vies_dinamico_penalidade': 0.75,
    'decaimento_padroes_ativo': True,
    'decaimento_fator': 0.97,
    'decaimento_a_cada': 5,
    'drift_janela': 15,
    'drift_taxa_minima': 0.35,
    'drift_alertar_apos': 5,
    # MELHORIA #14
    'streak_ativo': True,
    'streak_min_len': 2,
    'streak_peso_feature': 1.2,
}

# 🟢 IMMERSIVE ROULETTE
SETUP_IMMERSIVE = {
    **SETUP_BASE,
    'pagamento_numero': 35, 'pagamento_zero': 35, 'pagamento_duzia': 2,
    'confianca_minima_entrada': 1.9,
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
    'ml_score_minimo_entrada': 34,
    'ml_score_minimo_fallback': 42,
    'ml_min_rodadas_fallback': 10,
    'ml_max_repeticoes_mesma_duzia': 2,
    'ml_score_minimo_pos_rotacao': 18,
    'padrao_min_ocorrencias': 3,
    'padrao_peso_tam2': 32,
    'padrao_peso_tam3': 38,
    'padrao_peso_tam4': 30,
    'padrao_conf_minima_tam2': 2,
    'padrao_conf_minima_tam4': 8,
    'padrao_consenso_peso_extra': 8,
    'padrao_consenso_min_conf': 0.25,
    'ml_ignorar_consenso_conf_min': 3.5,
    'anti_vies_ativo': True,
    'anti_vies_duzia': 3,
    'anti_vies_penalidade': 0.78,
    'anti_vies_gatilho_p2': True,
    'anti_vies_p4_isolado_extra': 0.70,
    'peso_adaptativo_ativo': True,
    'peso_adaptativo_janela': 10,
    'peso_adaptativo_boost': 1.3,
    'vies_dinamico_ativo': True,
    'vies_dinamico_janela': 25,
    'vies_dinamico_limiar': 0.13,
    'vies_dinamico_penalidade': 0.76,
    'decaimento_padroes_ativo': True,
    'decaimento_fator': 0.96,
    'decaimento_a_cada': 5,
    'drift_janela': 12,
    'drift_taxa_minima': 0.38,
    'drift_alertar_apos': 4,
    # MELHORIA #14
    'streak_ativo': True,
    'streak_min_len': 2,
    'streak_peso_feature': 1.0,
}

# 🔴 MEGA ROULETTE - CORRIGIDO COM BASE NA ANÁLISE
SETUP_MEGA = {
    **SETUP_BASE,
    'pagamento_numero': 24, 'pagamento_zero': 24, 'pagamento_duzia': 2,
    'confianca_minima_entrada': 2.5,          # era 2.0 → mais exigente
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
    'ml_score_minimo_entrada': 35,            # era 28 → mais seletivo
    'ml_score_minimo_fallback': 42,
    'ml_min_rodadas_fallback': 10,
    'ml_max_repeticoes_mesma_duzia': 2,       # era 3 → reduzir repetições
    'ml_score_minimo_pos_rotacao': 18,
    'padrao_min_ocorrencias': 3,
    'padrao_peso_tam2': 35,                   # era 20 → dar mais peso ao P2
    'padrao_peso_tam3': 40,                   # era 50 → reduzir P3
    'padrao_peso_tam4': 25,                   # era 30 → reduzir P4
    'padrao_conf_minima_tam2': 4,             # era 2 → mais exigente
    'padrao_conf_minima_tam4': 10,            # era 6 → mais exigente
    'padrao_consenso_peso_extra': 15,
    'padrao_consenso_min_conf': 0.35,         # era 0.25 → reduzir falsos consensos
    'ml_ignorar_consenso_conf_min': 3.0,
    'anti_vies_ativo': False,
    'peso_adaptativo_ativo': False,
    'vies_dinamico_ativo': True,
    'vies_dinamico_janela': 20,               # era 30 → mais sensível
    'vies_dinamico_limiar': 0.12,             # era 0.15 → mais sensível
    'vies_dinamico_penalidade': 0.70,         # era 0.80 → penalidade mais forte
    'decaimento_padroes_ativo': True,
    'decaimento_fator': 0.97,
    'decaimento_a_cada': 5,
    'drift_janela': 15,
    'drift_taxa_minima': 0.40,                # era 0.35 → mais tolerante
    'drift_alertar_apos': 3,                  # era 5 → alertar mais cedo
    # MELHORIA #14 - peso reduzido para streak
    'streak_ativo': True,
    'streak_min_len': 2,
    'streak_peso_feature': 0.8,               # era 1.0 → reduzir peso do streak
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
        'padroes_hibridos': f"padroes_hibridos_{safe_name}.json",
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
                         'Acerto Dúzia', 'Acerto Número', 'Acerto Zero', 'Status', 'Padrão', 'Streak'])
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
            padrao = str(e.get('padrao_info', {}).get('resumo', '-')) if e.get('padrao_info') else '-'
            streak = str(e.get('streak_info', '-'))
            writer.writerow([
                e.get('rodada'), e.get('hora'), numero, raio, real, prev, cob,
                f"{e.get('confianca',0):.1f}", e.get('gatilho','-') if e.get('gatilho') else '-',
                zero, anti, duz, num, zer, e.get('status','?'), padrao, streak
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
        sis.duzia_ai._salvar_padroes_hibridos()

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
            'acertos_primaria': sis.acertos_primaria,
            'acertos_secundaria': sis.acertos_secundaria,
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
        streak_info = previsao.get('streak_info', None)
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
        if streak_info:
            msg += f" | 🔥 Streak: {streak_info}"
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
# FUNÇÕES AUXILIARES
# =============================

def _calcular_entropia(duzias):
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
    for i, n in enumerate(reversed(numeros)):
        if get_duzia(n) == duzia:
            return i
    return len(numeros)


def _calcular_autocorrelacao(serie, lag=3):
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
# 🧠 DUZIA AI V13.1 - CORRIGIDO
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

        # Tabelas de padrões híbridos
        self.padroes_tam2 = defaultdict(Counter)
        self.padroes_tam3 = defaultdict(Counter)
        self.padroes_tam4 = defaultdict(Counter)
        self._rodadas_desde_decaimento = 0

        # Cache streak para UI
        self._streak_info_atual = {}

        config = self._get_config()
        self.padrao_min_ocorrencias = config.get('padrao_min_ocorrencias', 3)
        self.peso_tam2 = config.get('padrao_peso_tam2', 20)
        self.peso_tam3 = config.get('padrao_peso_tam3', 50)
        self.peso_tam4 = config.get('padrao_peso_tam4', 30)
        self.conf_min_tam2 = config.get('padrao_conf_minima_tam2', 2)
        self.conf_min_tam4 = config.get('padrao_conf_minima_tam4', 6)
        self.consenso_peso_extra = config.get('padrao_consenso_peso_extra', 15)
        self.consenso_min_conf = config.get('padrao_consenso_min_conf', 0.25)
        self.ml_ignorar_consenso_conf_min = config.get('ml_ignorar_consenso_conf_min', 3.0)

        self.anti_vies_ativo = config.get('anti_vies_ativo', False)
        self.anti_vies_duzia = config.get('anti_vies_duzia', None)
        self.anti_vies_penalidade = config.get('anti_vies_penalidade', 1.0)
        self.anti_vies_gatilho_p2 = config.get('anti_vies_gatilho_p2', False)
        self.anti_vies_p4_isolado_extra = config.get('anti_vies_p4_isolado_extra', 1.0)

        self.peso_adaptativo_ativo = config.get('peso_adaptativo_ativo', False)
        self.peso_adaptativo_janela = config.get('peso_adaptativo_janela', 10)
        self.peso_adaptativo_boost = config.get('peso_adaptativo_boost', 1.0)

        self.vies_dinamico_ativo = config.get('vies_dinamico_ativo', True)
        self.vies_dinamico_janela = config.get('vies_dinamico_janela', 30)
        self.vies_dinamico_limiar = config.get('vies_dinamico_limiar', 0.15)
        self.vies_dinamico_penalidade = config.get('vies_dinamico_penalidade', 0.80)
        self._vies_dinamico_atual = None
        self._vies_dinamico_intensidade = 0.0

        self.decaimento_padroes_ativo = config.get('decaimento_padroes_ativo', True)
        self.decaimento_fator = config.get('decaimento_fator', 0.97)
        self.decaimento_a_cada = config.get('decaimento_a_cada', 5)

        self.drift_janela = config.get('drift_janela', 15)
        self.drift_taxa_minima = config.get('drift_taxa_minima', 0.35)
        self.drift_alertar_apos = config.get('drift_alertar_apos', 5)
        self._drift_ativo = False
        self._drift_erros_consecutivos_entrada = 0

        self.streak_config_ativo = config.get('streak_ativo', True)
        self.streak_min_len = config.get('streak_min_len', 2)
        self.streak_peso_feature = config.get('streak_peso_feature', 1.0)

        # Para UI
        self.padrao_ativo_ui = {'tam2': None, 'tam3': None, 'tam4': None}
        self.padrao_stats_ui = {'tam2': None, 'tam3': None, 'tam4': None}
        self.consenso_info = {'tipo': 'nenhum', 'duzia': None, 'conf': 0.0}

        self._carregar_modelo_salvo()
        self._carregar_padroes_hibridos()

    # ... (todos os métodos internos permanecem iguais ao código original até o método prever) ...

    # ===================================================
    # MÉTODO PREVER CORRIGIDO
    # CORREÇÃO: Streak é feature do ML, NÃO sobrepõe decisão
    # ===================================================
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

        if self._drift_ativo:
            return {"entrar": False, "motivo": f"⚠️ DRIFT detectado — taxa baixa. Aguardando recuperação."}

        scores, modo = self.calcular_score()

        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        d1, s1 = ranking[0]
        d2, s2 = ranking[1] if len(ranking) > 1 else (self._get_outras_duzias(d1)[0], 0)
        d3, s3 = ranking[2] if len(ranking) > 2 else (self._get_outras_duzias(d1)[-1], 0)

        self.detectar_alerta_zero()

        confianca = min(3.5, max(0.5, (s1 - s2) / 20))

        if self.alerta_zero_ativo and confianca >= 3.0:
            confianca = min(2.8, confianca)

        pode_entrar = False
        motivo = ""
        forcar_rotacao = False

        modo_base = 'ml' if 'ml' in modo else 'fallback'

        # Streak info (apenas para UI/Telegram)
        streak_info = self._streak_info_atual
        streak_len = streak_info.get('streak_atual_len', 0)
        streak_duzia = streak_info.get('streak_atual_duzia', 0)
        streak_quebra_iminente = streak_info.get('streak_quebra_iminente', 0)

        streak_sinal = ""
        if self.streak_config_ativo and streak_len >= self.streak_min_len and streak_duzia != 0:
            if streak_quebra_iminente:
                streak_sinal = f"⚡ STK-QUEBRA D{streak_duzia}({streak_len}x)"
            else:
                streak_sinal = f"🔥 STK D{streak_duzia}({streak_len}x)"

        if modo_base == 'ml':
            score_minimo = config.get('ml_score_minimo_entrada', 30)
            pode_entrar = s1 > score_minimo
            if pode_entrar:
                treino_info = "do Disco 💾" if self.ultimo_treino_ml <= 1 else f"R{self.ultimo_treino_ml}"

                partes_padrao = []
                if self.padrao_stats_ui.get('tam2'):
                    partes_padrao.append(f"P2:{self.padrao_stats_ui['tam2']['gatilho']}")
                if self.padrao_stats_ui.get('tam3'):
                    partes_padrao.append(f"P3:{self.padrao_stats_ui['tam3']['gatilho']}")
                if self.padrao_stats_ui.get('tam4'):
                    partes_padrao.append(f"P4:{self.padrao_stats_ui['tam4']['gatilho']}")

                info_padroes = " | ".join(partes_padrao) if partes_padrao else ""

                info_consenso = ""
                if self.consenso_info['tipo'] in ('duplo', 'triplo'):
                    icone = "🔒" if self.consenso_info['tipo'] == 'triplo' else "🔗"
                    info_consenso = f" | {icone} D{self.consenso_info['duzia']}"

                info_anti_vies = ""
                if self.anti_vies_ativo:
                    info_anti_vies = f" | 🛡️ AV-D{self.anti_vies_duzia}"

                info_vies_din = ""
                if self.vies_dinamico_ativo and self._vies_dinamico_atual:
                    info_vies_din = f" | 🔍 VD-D{self._vies_dinamico_atual}({self._vies_dinamico_intensidade*100:.0f}%)"

                info_adapt = ""
                if self.peso_adaptativo_ativo:
                    info_adapt = " | 🔥 Adapt"

                info_streak = f" | {streak_sinal}" if streak_sinal else ""

                motivo = f"🟢 ML Híbrido ({treino_info}) | Score: {s1:.1f}"
                if info_padroes:
                    motivo += f" | 🧩 {info_padroes}"
                if info_consenso:
                    motivo += info_consenso
                if info_anti_vies:
                    motivo += info_anti_vies
                if info_vies_din:
                    motivo += info_vies_din
                if info_adapt:
                    motivo += info_adapt
                if info_streak:
                    motivo += info_streak
            else:
                motivo = f"Score ML baixo ({s1:.1f} < {score_minimo})"
        else:
            score_min_fb = config.get('ml_score_minimo_fallback', 42)
            min_rodadas_fb = config.get('ml_min_rodadas_fallback', 8)
            if len(self.historico_completo) >= min_rodadas_fb and s1 > score_min_fb:
                pode_entrar = True
                motivo = f"🟡 Fallback Freq | Score: {s1:.1f}"
                if streak_sinal:
                    motivo += f" | {streak_sinal}"
            else:
                motivo = f"Aguardando ML ({len(self.historico_completo)}/40 rodadas)"

        # Limitador de repetições
        max_rep = config.get('ml_max_repeticoes_mesma_duzia', 3)
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
                    motivo = f"🚫 Bloqueio por repetição (>{max_rep}x mesma dúzia)"

        # Filtros de confiança
        confianca_min = config.get('confianca_minima_entrada', 2.0)
        if pode_entrar and confianca < confianca_min and not forcar_rotacao:
            if self.consenso_info['tipo'] == 'triplo' and confianca >= 1.5:
                motivo += " | 🔒 Exceção tripla"
            else:
                pode_entrar = False
                motivo = f"Confiança muito baixa ({confianca:.2f} < {confianca_min})"

        if pode_entrar and self.modo_anti_erro and confianca < (confianca_min + 0.5):
            pode_entrar = False
            motivo = f"🚫 Anti-Erro: Confiança insuficiente ({confianca:.2f})"

        # Termômetro zero
        incluir_zero = self.alerta_zero_ativo
        if self.rodadas_desde_zero >= config['zero_termometro_max']:
            incluir_zero = True
            if pode_entrar and "Termômetro" not in motivo:
                motivo += " | 🌡️ Zero"

        if confianca < 0.8:
            pode_entrar = False
            motivo = f"Confiança crítica ({confianca:.2f})"

        # =====================================================
        # CORRIGIDO: Streak NÃO sobrepõe decisão do ML
        # O ML já recebeu 14 features de streak no treinamento.
        # A decisão final (d1, d2) é 100% do ML.
        # Streak info é apenas visual para UI/Telegram.
        # =====================================================
        duzia_secundaria_final = d2
        streak_aplicado = (streak_len >= self.streak_min_len and streak_duzia != 0)

        if streak_aplicado:
            logging.info(f"🔥 Streak visual (ML já processou): D{streak_duzia}×{streak_len}")

        # Info dos padrões para UI
        info_padrao = {
            'tam2': self.padrao_stats_ui.get('tam2'),
            'tam3': self.padrao_stats_ui.get('tam3'),
            'tam4': self.padrao_stats_ui.get('tam4'),
            'consenso': self.consenso_info,
            'anti_vies': self.anti_vies_ativo,
            'peso_adaptativo': self.peso_adaptativo_ativo,
            'vies_dinamico': self._vies_dinamico_atual,
            'drift_ativo': self._drift_ativo,
            'streak': streak_info,
            'streak_sinal': streak_sinal,
            'streak_aplicado': streak_aplicado,
            'resumo': []
        }
        for t, nome in [('tam2', 'P2'), ('tam3', 'P3'), ('tam4', 'P4')]:
            if info_padrao[t]:
                info_padrao['resumo'].append(f"{nome}:{info_padrao[t]['gatilho']}")
        if self.consenso_info['tipo'] in ('duplo', 'triplo'):
            icone = "🔒" if self.consenso_info['tipo'] == 'triplo' else "🔗"
            info_padrao['resumo'].append(f"{icone}D{self.consenso_info['duzia']}")
        if self.anti_vies_ativo:
            info_padrao['resumo'].append(f"🛡️AV-D{self.anti_vies_duzia}")
        if self.vies_dinamico_ativo and self._vies_dinamico_atual:
            info_padrao['resumo'].append(f"🔍VD-D{self._vies_dinamico_atual}")
        if self.peso_adaptativo_ativo:
            info_padrao['resumo'].append("🔥Adapt")
        if streak_sinal:
            info_padrao['resumo'].append(streak_sinal)
        info_padrao['resumo'] = " | ".join(info_padrao['resumo']) if info_padrao['resumo'] else "-"

        previsao = {
            "entrar": pode_entrar,
            "motivo": motivo,
            "score": scores,
            "confianca": round(confianca, 2),
            "duzia": d1,
            "duzia_secundaria": duzia_secundaria_final,
            "gatilho_ativo": "ML" if modo_base == 'ml' else "Fallback",
            "incluir_zero": incluir_zero,
            "modo_anti_erro": self.modo_anti_erro,
            "numeros_completos": list(self.numeros_completos),
            "modo_previsao": modo,
            "rotacao_forcada": forcar_rotacao,
            "padrao_ativo": info_padrao,
            "streak_info": streak_sinal if streak_sinal else None,
        }

        return previsao


# ===================================================
# Ensemble Manual
# ===================================================
class _EnsembleManual:
    def __init__(self, rf, gbt):
        self.rf = rf
        self.gbt = gbt
        self.classes_ = rf.classes_
        try:
            self.n_features_in_ = rf.n_features_in_
        except:
            self.n_features_in_ = None

    def predict_proba(self, X):
        p_rf = self.rf.predict_proba(X)
        p_gbt = self.gbt.predict_proba(X)
        media = (p_rf + p_gbt) / 2.0
        return media, self.classes_

    def predict(self, X):
        proba, classes = self.predict_proba(X)
        idx = np.argmax(proba, axis=1)
        return classes[idx]


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
        self.acertos_primaria = 0
        self.acertos_secundaria = 0
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

            if acerto_primaria or acerto_zero:
                self.acertos_primaria += 1
                self.acertos_duzia += 1
            elif acerto_secundaria:
                self.acertos_secundaria += 1
                self.acertos_duzia += 1
            elif nr != 0:
                self.erros_duzia += 1

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

            streak_entrada_info = self.entrada_ativa.get('streak_info', None)

            self.historico_entradas.append({
                'rodada': self.numero_rodada,
                'hora': formatar_hora_brasilia(),
                'numero': nr,
                'duzia_real': duzia_real if nr != 0 else 0,
                'duzia_prevista': duzia_prevista,
                'duzia_sec_prevista': duzia_sec_prevista,
                'acerto_duzia': acerto_primaria or acerto_secundaria,
                'acerto_primaria': acerto_primaria,
                'acerto_secundaria': acerto_secundaria,
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
                'padrao_info': self.entrada_ativa.get('padrao_ativo'),
                'streak_info': streak_entrada_info,
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
                    'padrao_ativo': previsao.get('padrao_ativo'),
                    'streak_info': previsao.get('streak_info'),
                }

                self.duzia_ai.registrar_previsao(previsao['duzia'], previsao['confianca'])
                idx_atual = len(self.historico_numeros) - 1
                self.sinais_grafico.append((idx_atual, previsao['duzia']))

                enviar_previsao_auto({
                    'numeros_apostar': numeros_apostar,
                    'incluir_zero': previsao.get('incluir_zero', False),
                    'duzia': previsao['duzia'],
                    'duzia_secundaria': previsao.get('duzia_secundaria', previsao['duzia']),
                    'numeros_completos': list(self.historico_numeros),
                    'streak_info': previsao.get('streak_info'),
                })

    def zerar(self):
        self.acertos_duzia = 0
        self.erros_duzia = 0
        self.acertos_numero = 0
        self.erros_numero = 0
        self.acertos_zero = 0
        self.erros_zero = 0
        self.acertos_primaria = 0
        self.acertos_secundaria = 0
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
            writer.writerow(['Rod','Hora','Nº','Raio','Real','Prev','Cob','Conf','Gat','Z','🔄','Mesa','Duz','P1','P2s','Num','Zer','St','Padrões','Streak'])
            for e in historico_entradas:
                real = f"D{e.get('duzia_real',0)}" if e.get('duzia_real',0)!=0 else "0"
                prev = f"D{e.get('duzia_prevista','?')}"
                cob = f"D{e.get('duzia_sec_prevista','?')}" if e.get('duzia_sec_prevista') and e.get('duzia_sec_prevista') != e.get('duzia_prevista') else "-"
                zero = '🟢' if e.get('incluir_zero') else '-'
                anti = '🔄' if e.get('modo_anti_erro') else '-'
                duz = '✅' if e.get('acerto_duzia') else '❌'
                p1 = '✅' if e.get('acerto_primaria') else '-'
                p2s = '✅' if e.get('acerto_secundaria') else '-'
                num = '✅' if e.get('acerto_numero') else '-'
                zer = '✅' if e.get('acerto_zero') else '-'
                ns = e.get('numero', 0)
                if e.get('eh_raio'): nd = f"⚡{ns} ({e.get('multiplicador',0)}x)"
                elif ns == 0: nd = "0"
                else: nd = str(ns)
                padrao = str(e.get('padrao_info', {}).get('resumo', '-')) if e.get('padrao_info') else '-'
                streak = str(e.get('streak_info', '-')) if e.get('streak_info') else '-'
                mesa = e.get('table_name', '?')[:15] if e.get('table_name') else '?'
                writer.writerow([e.get('rodada'), e.get('hora'), nd, f"⚡{e.get('multiplicador',0)}x" if e.get('eh_raio') else '-',
                                  real, prev, cob, f"{e.get('confianca',0):.1f}", e.get('gatilho','ML'),
                                  zero, anti, mesa, duz, p1, p2s, num, zer, e.get('status','?'), padrao, streak])
        return True
    except Exception as e:
        logging.error(f"Erro CSV: {e}")
        return False


# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎰 DuziaAI V13.1 - Corrigido Streak ML", layout="wide")
st.title("🎰 DuziaAI V13.1 — Streak é Feature do ML 🔥 (BRT)")

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

# Inicialização do sistema (mesma lógica do original)
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
        sis.acertos_primaria = dados.get('acertos_primaria', 0)
        sis.acertos_secundaria = dados.get('acertos_secundaria', 0)
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
        sis.duzia_ai._carregar_padroes_hibridos()
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
        sis.acertos_primaria = dados.get('acertos_primaria', 0)
        sis.acertos_secundaria = dados.get('acertos_secundaria', 0)
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
        sis.duzia_ai._carregar_padroes_hibridos()
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
    st.markdown("## ⚙️ V13.1 — Streak é Feature ML")
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
    st.markdown("### 🎰 Selecione a Roleta")
    api_opcoes = list(API_URLS.keys())
    api_atual = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
    api_index = api_opcoes.index(api_atual) if api_atual in api_opcoes else 0
    st.session_state.api_selecionada = st.radio("Roleta:", api_opcoes, index=api_index)
    api_name = st.session_state.api_selecionada

    config_ativa = ROLETA_CONFIGS.get(api_name, SETUP_XXXTREME)

    if hasattr(sis.duzia_ai, 'modelo_ml') and sis.duzia_ai.modelo_ml is not None:
        if sis.duzia_ai.ultimo_treino_ml <= 1:
            st.success("🧠 Ensemble ML CARREGADO 💾")
        else:
            st.success(f"🧠 Ensemble ML ATIVO | R{sis.duzia_ai.ultimo_treino_ml}")
    else:
        rodadas_atual = len(sis.historico_numeros)
        if rodadas_atual >= 8:
            st.warning(f"🟡 Fallback ({rodadas_atual}/40)")
        else:
            st.info(f"🧠 Aguardando... ({rodadas_atual}/8)")

    if sis.duzia_ai._drift_ativo:
        st.error("⚠️ DRIFT DETECTADO — Entradas suspensas!")

    if sis.duzia_ai._vies_dinamico_atual:
        st.warning(f"🔍 Viés dinâmico: D{sis.duzia_ai._vies_dinamico_atual} ({sis.duzia_ai._vies_dinamico_intensidade*100:.0f}% acima)")

    # Streak info na sidebar
    stk = sis.duzia_ai._streak_info_atual
    if stk and stk.get('streak_atual_len', 0) >= 2:
        stk_len = stk['streak_atual_len']
        stk_duzia = stk['streak_atual_duzia']
        st.info(f"🔥 Streak detectado: D{stk_duzia} × {stk_len} (feature do ML)")

    st.markdown("---")
    st.session_state.janela_duzia_ai = st.slider("📏 Janela de Análise", 10, 50, st.session_state.janela_duzia_ai, 5)
    st.session_state.modo_agressivo = st.checkbox("🔥 Modo Agressivo (2 Dúzias)", value=st.session_state.modo_agressivo)
    st.session_state.modo_automatico = st.checkbox("🤖 Modo Automático", value=st.session_state.modo_automatico)

    st.markdown("---")
    with st.expander("🔔 Configurações Telegram", expanded=False):
        st.session_state.telegram_token = st.text_input("Token Principal", value=st.session_state.telegram_token, type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID Principal", value=st.session_state.telegram_chat_id)
        st.session_state.telegram_token_alt = st.text_input("Token Alternativo", value=st.session_state.telegram_token_alt, type="password")
        st.session_state.telegram_chat_id_alt = st.text_input("Chat ID Alternativo", value=st.session_state.telegram_chat_id_alt)

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
                "number": nr, "timestamp": timestamp_brasilia(),
                "luckyNumbers": [], "luckyMultipliers": {},
                "table_id": "manual", "table_name": "Entrada Manual"
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

# Banner de streak (apenas informativo)
stk = sis.duzia_ai._streak_info_atual
if stk and stk.get('streak_atual_len', 0) >= 2:
    stk_len = stk['streak_atual_len']
    stk_duzia = stk['streak_atual_duzia']
    st.info(f"🔥 **Streak detectado:** D{stk_duzia} × {stk_len} — ML já processou como feature de entrada")

st.subheader(f"📊 ESTATÍSTICAS — {api_name}")
c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
total_duzias = int(sis.acertos_duzia + sis.erros_duzia)
tx_duzias = (sis.acertos_duzia / total_duzias * 100) if total_duzias > 0 else 0
c1.metric("🎯 Nº Exato", sis.acertos_numero)
c2.metric("✅ Acertos", int(sis.acertos_duzia), f"{tx_duzias:.0f}%")
c3.metric("🎯 Primária", sis.acertos_primaria)
c4.metric("🟡 Secundária", sis.acertos_secundaria)
c5.metric("❌ Erros", sis.erros_duzia)
c6.metric("🟢 Zeros", f"{sis.acertos_zero}/{sis.acertos_zero + sis.erros_zero}")
c7.metric("📦 Total", total_duzias)

st.markdown("---")
st.subheader("📝 Histórico")
if sis.historico_entradas:
    dados = []
    for e in reversed(sis.historico_entradas[-15:]):
        real = f"D{e.get('duzia_real',0)}" if e.get('duzia_real',0)!=0 else "0"
        prev = f"D{e.get('duzia_prevista','?')}"
        cob = f"D{e.get('duzia_sec_prevista','?')}" if e.get('duzia_sec_prevista') and e.get('duzia_sec_prevista') != e.get('duzia_prevista') else "-"
        duz = '✅' if e.get('acerto_duzia') else '❌'
        p1 = '✅' if e.get('acerto_primaria') else '-'
        p2s = '🟡' if e.get('acerto_secundaria') else '-'
        ns = e.get('numero', 0)
        if e.get('eh_raio'): nd = f"⚡{ns} ({e.get('multiplicador',0)}x)"
        elif ns == 0: nd = "0"
        else: nd = str(ns)
        stk_col = str(e.get('streak_info', '-')) if e.get('streak_info') else '-'
        dados.append({"Rod":e.get('rodada'),"Hora":e.get('hora'),"🎲":nd,"Real":real,"Prev":prev,"Cob":cob,
                      "Conf":f"{e.get('confianca',0):.1f}","Duz":duz,"P1":p1,"P2s":p2s,"STK":stk_col})
    st.dataframe(dados, use_container_width=True, height=300)
else:
    st.info("Nenhuma entrada ainda.")

st.markdown("---")
st.caption(f"🤖 DuziaAI V13.1 Corrigido | Streak = Feature ML | {api_name} | {formatar_hora_brasilia()}")

salvar_sessao()
