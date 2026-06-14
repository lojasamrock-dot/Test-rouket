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

try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    import joblib
    ML_DISPONIVEL = True
except ImportError:
    ML_DISPONIVEL = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('roleta_bot.log'), logging.StreamHandler()]
)

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
# VIÉS DINÂMICO
# =============================
def detectar_vies_dinamico(historico_completo, janela=30, limiar_excesso=0.15):
    duzias = [d for d in historico_completo[-janela:] if d != 0]
    if len(duzias) < 15:
        return None, 0.0
    total = len(duzias)
    freq = Counter(duzias)
    max_excesso = 0.0
    duzia_vies = None
    for d in [1, 2, 3]:
        excesso = (freq.get(d, 0) / total) - (1 / 3.0)
        if excesso > limiar_excesso and excesso > max_excesso:
            max_excesso = excesso
            duzia_vies = d
    return duzia_vies, round(max_excesso, 4)

# =============================
# DECAIMENTO DE PADRÕES
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
# FEATURES DE STREAK
# =============================
def extrair_features_streak(historico_duzias):
    duzias = [d for d in historico_duzias if d != 0]
    resultado = {
        'streak_atual_duzia': 0, 'streak_atual_len': 0,
        'streak_duzia1_len': 0, 'streak_duzia2_len': 0, 'streak_duzia3_len': 0,
        'prob_continua_streak2': 0.5, 'prob_continua_streak3': 0.5,
        'prob_quebra_streak2': 0.5, 'prob_quebra_streak3': 0.5,
        'streak_max_recente': 0, 'entrada_streak_duzia': 0, 'cobertura_streak_duzia': 0,
        'streak_quebra_iminente': 0, 'streak_forca': 0.0,
        'streak_saturado': 0, 'streak_taxa_quebra_real': 0.0,
    }
    if len(duzias) < 3:
        return resultado

    streak_atual_len = 1
    streak_atual_duzia = duzias[-1]
    for d in reversed(duzias[:-1]):
        if d == streak_atual_duzia: streak_atual_len += 1
        else: break

    resultado['streak_atual_duzia'] = streak_atual_duzia
    resultado['streak_atual_len'] = streak_atual_len

    for alvo in [1, 2, 3]:
        comprimento = 0
        for d in reversed(duzias):
            if d == alvo: comprimento += 1
            else: break
        resultado[f'streak_duzia{alvo}_len'] = comprimento

    recentes = duzias[-30:]
    max_streak = 1; cur_streak = 1
    for i in range(1, len(recentes)):
        if recentes[i] == recentes[i-1]: cur_streak += 1; max_streak = max(max_streak, cur_streak)
        else: cur_streak = 1
    resultado['streak_max_recente'] = max_streak

    continua2 = quebra2 = continua3 = quebra3 = 0
    for i in range(len(duzias) - 3):
        if duzias[i] == duzias[i+1]:
            if duzias[i+2] == duzias[i]: continua2 += 1
            else: quebra2 += 1
        if i + 3 < len(duzias) and duzias[i] == duzias[i+1] == duzias[i+2]:
            if duzias[i+3] == duzias[i]: continua3 += 1
            else: quebra3 += 1

    if continua2 + quebra2 > 0:
        resultado['prob_continua_streak2'] = round(continua2 / (continua2 + quebra2), 4)
        resultado['prob_quebra_streak2'] = round(quebra2 / (continua2 + quebra2), 4)
    if continua3 + quebra3 > 0:
        resultado['prob_continua_streak3'] = round(continua3 / (continua3 + quebra3), 4)
        resultado['prob_quebra_streak3'] = round(quebra3 / (continua3 + quebra3), 4)

    resultado['streak_forca'] = round(min(1.0, streak_atual_len / 5.0), 4)

    if streak_atual_len >= 3:
        sl = sb = 0
        for i in range(len(duzias) - 4):
            if duzias[i] == duzias[i+1] == duzias[i+2]:
                sl += 1
                if duzias[i+3] != duzias[i]: sb += 1
        if sl > 0:
            taxa = sb / sl
            resultado['streak_taxa_quebra_real'] = round(taxa, 4)
            if taxa > 0.65:
                resultado['streak_quebra_iminente'] = 1
                resultado['streak_forca'] = 0.2
                resultado['streak_saturado'] = 1

    if streak_atual_len >= 3 and resultado['prob_quebra_streak3'] > 0.60:
        if resultado['streak_quebra_iminente'] == 0:
            resultado['streak_quebra_iminente'] = 1

    if streak_atual_len >= 2:
        outras = [d for d in [1, 2, 3] if d != streak_atual_duzia]
        freq_outras = Counter(duzias[-10:])
        cobertura = max(outras, key=lambda d: freq_outras.get(d, 0))
        if streak_atual_len == 2:
            resultado['entrada_streak_duzia'] = streak_atual_duzia if resultado['prob_continua_streak2'] >= 0.45 else cobertura
        elif streak_atual_len >= 3:
            taxa = resultado.get('streak_taxa_quebra_real', resultado['prob_quebra_streak3'])
            resultado['entrada_streak_duzia'] = cobertura if taxa > 0.55 else streak_atual_duzia
            if taxa > 0.55: resultado['streak_quebra_iminente'] = 1
        resultado['cobertura_streak_duzia'] = cobertura

    return resultado


# =============================
# SETUPS — V13.3 CORRIGIDO
# BUG #2 FIX: padrao_min_ocorrencias compatível com janela de treino
# BUG #3 FIX: ml_max_repeticoes_mesma_duzia mínimo 2
# BUG #5 FIX: ml_score_minimo_fallback calibrado para score real do fallback
# BUG #6 FIX: confianca_minima_entrada compatível com escala de confiança
# BUG #10 FIX: padrao_qualidade_min dinâmico (não fixo alto)
# =============================
SETUP_BASE = {
    'pagamento_numero': 20, 'pagamento_zero': 20, 'pagamento_duzia': 3,
    'confianca_minima_entrada': 1.8,       # FIX #6: era muito alto
    'embalo_peso': 9, 'embalo_reforco': 5,
    'bloquear_alerta_zero_conf_alta': True, 'bloquear_anti_erro_zero_conf_baixa': True,
    'filtro_conf_baixa': 1.5,
    'fadiga_duzia': 4, 'ritmo_alternado_peso': 10, 'ritmo_alternado_forca': 10,
    'max_repeticoes_embalo': 4, 'confianca_maxima_segura': 3.3,
    'rodadas_verificacao_conf_alta': 5, 'pausa_pos_raio': 1, 'raio_alto_minimo': 100,
    'zero_termometro_max': 15, 'anti_erro_skip_discordancia': True,
    'ritmo_v_peso': 9, 'ritmo_v_forca': 9, 'ritmo_v_confirmacoes': 2,
    'ml_janela_treino': 80,
    'ml_atualizar_a_cada': 10,
    'score_ml_peso': 45,
    'ml_score_minimo_entrada': 30,
    'ml_score_minimo_fallback': 38,        # FIX #5: era 42, alto demais
    'ml_min_rodadas_fallback': 8,
    'ml_max_repeticoes_mesma_duzia': 2,    # FIX #3: era 3, agora 2
    'ml_score_minimo_pos_rotacao': 18,
    'padrao_min_ocorrencias': 3,           # FIX #2: compatível com janela
    'padrao_conf_minima_tam2': 2,
    'padrao_conf_minima_tam4': 4,          # FIX: era 6, difícil atingir
    'padrao_consenso_min_conf': 0.20,      # FIX: era 0.25
    'anti_vies_ativo': False, 'anti_vies_duzia': None,
    'anti_vies_penalidade': 1.0, 'anti_vies_gatilho_p2': False, 'anti_vies_p4_isolado_extra': 1.0,
    'peso_adaptativo_ativo': False, 'peso_adaptativo_janela': 10, 'peso_adaptativo_boost': 1.0,
    'vies_dinamico_ativo': True, 'vies_dinamico_janela': 30,
    'vies_dinamico_limiar': 0.15, 'vies_dinamico_penalidade': 0.80,
    'decaimento_padroes_ativo': True, 'decaimento_fator': 0.97, 'decaimento_a_cada': 5,
    'drift_janela': 15, 'drift_taxa_minima': 0.30,  # FIX #9: era 0.35, mais tolerante
    'drift_alertar_apos': 5,
    'drift_rodadas_auto_reset': 20,        # FIX #9: reset automático do drift
    'streak_ativo': True, 'streak_min_len': 2, 'streak_peso_feature': 1.0,
    # FIX #10: qualidade mínima dinâmica — valores menores
    'padrao_qualidade_min_p2': 15,
    'padrao_qualidade_min_p3': 10,
    'padrao_qualidade_min_p4': 8,
}

# 🟡 XXXTREME LIGHTNING — V13.3
SETUP_XXXTREME = {
    **SETUP_BASE,
    'pagamento_numero': 20, 'pagamento_zero': 20, 'pagamento_duzia': 3,
    'confianca_minima_entrada': 1.8,       # FIX #6: era 2.2
    'embalo_peso': 5, 'embalo_reforco': 2,
    'bloquear_alerta_zero_conf_alta': True, 'bloquear_anti_erro_zero_conf_baixa': True,
    'filtro_conf_baixa': 1.5, 'fadiga_duzia': 4,
    'ritmo_alternado_peso': 10, 'ritmo_alternado_forca': 10,
    'max_repeticoes_embalo': 3, 'confianca_maxima_segura': 3.1,
    'rodadas_verificacao_conf_alta': 5, 'pausa_pos_raio': 1, 'raio_alto_minimo': 100,
    'zero_termometro_max': 15, 'anti_erro_skip_discordancia': True,
    'ritmo_v_peso': 9, 'ritmo_v_forca': 9, 'ritmo_v_confirmacoes': 2,
    'usar_embalo': True, 'embalo_consecutivas_min': 2, 'embalo_janela': 4,
    'usar_ritmo_alternado': True, 'usar_ritmo_v': True,
    'usar_ritmo_ping_pong': True, 'usar_ritmo_binario': True,
    'usar_quebra_pos_zero': False, 'usar_exaustao_dominancia': True,
    'usar_mudanca_velocidade': False,
    'score_frequencia_peso': 45, 'score_streak_peso': 6,
    'score_markov_peso': 8, 'score_ml_peso': 45, 'score_anti_erro_peso': 20,
    'ml_janela_treino': 80,                # FIX #1: era 120, reduzido para evitar trava
    'ml_atualizar_a_cada': 10,
    'ml_score_minimo_entrada': 25,         # FIX: era 35
    'ml_score_minimo_fallback': 38,        # FIX #5: era 40
    'ml_min_rodadas_fallback': 8,          # FIX: era 10
    'ml_max_repeticoes_mesma_duzia': 2,    # FIX #3: era 3→2
    'ml_score_minimo_pos_rotacao': 18,
    'padrao_min_ocorrencias': 3,           # FIX #2: compatível com janela 80
    'padrao_peso_tam2': 15, 'padrao_peso_tam3': 55, 'padrao_peso_tam4': 30,
    'padrao_conf_minima_tam2': 2, 'padrao_conf_minima_tam4': 4,
    'padrao_consenso_peso_extra': 15, 'padrao_consenso_min_conf': 0.20,
    'ml_ignorar_consenso_conf_min': 2.0,
    'anti_vies_ativo': False,
    'peso_adaptativo_ativo': False,
    'vies_dinamico_ativo': True, 'vies_dinamico_janela': 20,
    'vies_dinamico_limiar': 0.12, 'vies_dinamico_penalidade': 0.75,
    'decaimento_padroes_ativo': True, 'decaimento_fator': 0.97, 'decaimento_a_cada': 5,
    'drift_janela': 15, 'drift_taxa_minima': 0.30, 'drift_alertar_apos': 5,
    'drift_rodadas_auto_reset': 20,
    'streak_ativo': True, 'streak_min_len': 2, 'streak_peso_feature': 1.2,
    'padrao_qualidade_min_p2': 15, 'padrao_qualidade_min_p3': 10, 'padrao_qualidade_min_p4': 8,
}

# 🟢 IMMERSIVE ROULETTE — V13.3 (era o mais travado)
SETUP_IMMERSIVE = {
    **SETUP_BASE,
    'pagamento_numero': 35, 'pagamento_zero': 35, 'pagamento_duzia': 2,
    'confianca_minima_entrada': 1.5,       # FIX #6: era 2.1 — impossível com fallback
    'filtro_conf_baixa': 1.4,
    'confianca_maxima_segura': 3.0,
    'rodadas_verificacao_conf_alta': 5,
    'embalo_peso': 6, 'embalo_reforco': 1,
    'embalo_consecutivas_min': 2, 'embalo_janela': 4,
    'max_repeticoes_embalo': 3,
    'ritmo_alternado_peso': 6, 'ritmo_alternado_forca': 8,
    'ritmo_v_peso': 6, 'ritmo_v_forca': 8, 'ritmo_v_confirmacoes': 2,
    'bloquear_alerta_zero_conf_alta': True, 'bloquear_anti_erro_zero_conf_baixa': True,
    'anti_erro_skip_discordancia': True,
    'zero_termometro_max': 12, 'fadiga_duzia': 3,
    'pausa_pos_raio': 0, 'raio_alto_minimo': 0,
    'usar_embalo': True, 'usar_ritmo_alternado': True, 'usar_ritmo_v': True,
    'usar_ritmo_ping_pong': False, 'usar_ritmo_binario': True,
    'usar_quebra_pos_zero': True, 'usar_exaustao_dominancia': False,
    'usar_mudanca_velocidade': False,
    'score_frequencia_peso': 45, 'score_streak_peso': 6,
    'score_markov_peso': 8, 'score_ml_peso': 45, 'score_anti_erro_peso': 20,
    'ml_janela_treino': 60,                # FIX #1: era 30 (muito curto) → 60
    'ml_atualizar_a_cada': 5,
    'ml_score_minimo_entrada': 25,         # FIX: era 30
    'ml_score_minimo_fallback': 36,        # FIX #5: era 45 — impossível!
    'ml_min_rodadas_fallback': 8,          # FIX: era 10
    'ml_max_repeticoes_mesma_duzia': 2,    # FIX #3: era 1 — causava bloqueio total!
    'ml_score_minimo_pos_rotacao': 16,
    'ml_ignorar_consenso_conf_min': 2.5,
    'padrao_min_ocorrencias': 4,           # FIX #2: era 8 — impossível com janela 60!
    'padrao_peso_tam2': 42, 'padrao_peso_tam3': 25, 'padrao_peso_tam4': 33,
    'padrao_conf_minima_tam2': 2,
    'padrao_conf_minima_tam4': 4,          # FIX: era 6
    'padrao_consenso_peso_extra': 12,
    'padrao_consenso_min_conf': 0.18,      # FIX: era 0.25 — muito restritivo
    'anti_vies_ativo': False, 'anti_vies_duzia': None,
    'anti_vies_penalidade': 1.0, 'anti_vies_gatilho_p2': False, 'anti_vies_p4_isolado_extra': 1.0,
    'peso_adaptativo_ativo': True, 'peso_adaptativo_janela': 10, 'peso_adaptativo_boost': 1.3,
    'vies_dinamico_ativo': True, 'vies_dinamico_janela': 15,
    'vies_dinamico_limiar': 0.10, 'vies_dinamico_penalidade': 0.70,
    'decaimento_padroes_ativo': True, 'decaimento_fator': 0.94, 'decaimento_a_cada': 4,
    'drift_janela': 10, 'drift_taxa_minima': 0.28,  # FIX #9: era 0.42 — bloqueava tudo
    'drift_alertar_apos': 4,
    'drift_rodadas_auto_reset': 15,
    'streak_ativo': True, 'streak_min_len': 2, 'streak_peso_feature': 0.9,
    'padrao_qualidade_min_p2': 12,         # FIX #10: era 50 — impossível!
    'padrao_qualidade_min_p3': 8,          # FIX #10: era 30
    'padrao_qualidade_min_p4': 6,          # FIX #10: era 20
}

# 🔴 MEGA ROULETTE — V13.3
SETUP_MEGA = {
    **SETUP_BASE,
    'pagamento_numero': 24, 'pagamento_zero': 24, 'pagamento_duzia': 2,
    'confianca_minima_entrada': 1.8,       # FIX #6: era 2.0
    'embalo_peso': 5, 'embalo_reforco': 2,
    'bloquear_alerta_zero_conf_alta': True, 'bloquear_anti_erro_zero_conf_baixa': True,
    'filtro_conf_baixa': 1.5, 'fadiga_duzia': 3,
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
    'ml_janela_treino': 80,                # FIX #1: era 120
    'ml_atualizar_a_cada': 8,
    'ml_score_minimo_entrada': 28,
    'ml_score_minimo_fallback': 38,        # FIX #5: era 45
    'ml_min_rodadas_fallback': 10,         # FIX: era 15
    'ml_max_repeticoes_mesma_duzia': 2,    # FIX #3: era 3→2
    'ml_score_minimo_pos_rotacao': 16,
    'padrao_min_ocorrencias': 3,
    'padrao_peso_tam2': 20, 'padrao_peso_tam3': 50, 'padrao_peso_tam4': 30,
    'padrao_conf_minima_tam2': 2, 'padrao_conf_minima_tam4': 4,
    'padrao_consenso_peso_extra': 15, 'padrao_consenso_min_conf': 0.20,
    'ml_ignorar_consenso_conf_min': 2.5,
    'anti_vies_ativo': True, 'anti_vies_duzia': None,
    'anti_vies_penalidade': 0.82, 'anti_vies_gatilho_p2': True, 'anti_vies_p4_isolado_extra': 0.75,
    'peso_adaptativo_ativo': True, 'peso_adaptativo_janela': 10, 'peso_adaptativo_boost': 1.2,
    'vies_dinamico_ativo': True, 'vies_dinamico_janela': 20,
    'vies_dinamico_limiar': 0.12, 'vies_dinamico_penalidade': 0.70,
    'decaimento_padroes_ativo': True, 'decaimento_fator': 0.94, 'decaimento_a_cada': 3,
    'drift_janela': 15, 'drift_taxa_minima': 0.28, 'drift_alertar_apos': 5,
    'drift_rodadas_auto_reset': 20,
    'streak_ativo': True, 'streak_min_len': 2, 'streak_peso_feature': 1.0,
    'padrao_qualidade_min_p2': 12, 'padrao_qualidade_min_p3': 8, 'padrao_qualidade_min_p4': 6,
}

ROLETA_CONFIGS = {
    'XXXtreme Lightning': SETUP_XXXTREME,
    'Immersive Roulette': SETUP_IMMERSIVE,
    'Mega Roulette': SETUP_MEGA,
}

CONFIG_GLOBAL_PATH = "config_global.json"
PASTA_SESSOES = "sessoes_salvas"
PASTA_MODELOS_ML = "modelos_ml"

def criar_pasta_modelos_ml():
    if not os.path.exists(PASTA_MODELOS_ML): os.makedirs(PASTA_MODELOS_ML)

def criar_pasta_sessoes():
    if not os.path.exists(PASTA_SESSOES): os.makedirs(PASTA_SESSOES)
    for roleta in ['xxxtreme_lightning', 'immersive_roulette', 'mega_roulette']:
        pasta = os.path.join(PASTA_SESSOES, roleta)
        if not os.path.exists(pasta): os.makedirs(pasta)

def get_pasta_sessao(api_name):
    return os.path.join(PASTA_SESSOES, api_name.lower().replace(' ', '_'))

def get_modelo_ml_path(api_name):
    criar_pasta_modelos_ml()
    return os.path.join(PASTA_MODELOS_ML, f"modelo_ml_{api_name.lower().replace(' ', '_')}.joblib")

def salvar_modelo_ml(modelo, api_name):
    if modelo is None: return False
    try:
        joblib.dump(modelo, get_modelo_ml_path(api_name))
        return True
    except Exception as e:
        logging.error(f"❌ Erro ao salvar modelo ML: {e}")
        return False

def carregar_modelo_ml(api_name):
    try:
        caminho = get_modelo_ml_path(api_name)
        if os.path.exists(caminho): return joblib.load(caminho)
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
    safe = api_name.lower().replace(' ', '_')
    return {
        'session': f"session_data_{safe}.pkl",
        'historico': f"historico_roleta_{safe}.json",
        'performance': f"performance_bot_{safe}.json",
        'entradas': f"historico_entradas_{safe}.json",
        'performance_mesa': f"performance_mesa_{safe}.json",
        'performance_horario': f"performance_horario_{safe}.json",
        'sessao_controle': f"sessao_controle_{safe}.json",
        'historico_sessoes': f"historico_sessoes_{safe}.json",
        'padroes_hibridos': f"padroes_hibridos_{safe}.json",
    }

class GerenciadorSessoes:
    def __init__(self, api_name):
        self.api_name = api_name
        self.pasta_sessao = get_pasta_sessao(api_name)
        criar_pasta_sessoes()

    def salvar_sessao_encerrada(self, numero_sessao, dados_sessao, historico_entradas):
        try:
            data = data_brasilia(); hora = formatar_hora_brasilia()
            nome = f"sessao_{numero_sessao:03d}_{data}_{hora.replace(':', '-')}.json"
            caminho = os.path.join(self.pasta_sessao, nome)
            with open(caminho, 'w', encoding='utf-8') as f:
                json.dump({'numero_sessao': numero_sessao, 'data': data, 'hora_encerramento': hora,
                           'roleta': self.api_name, 'estatisticas': dados_sessao,
                           'entradas': historico_entradas, 'timestamp': timestamp_brasilia()}, f, indent=2, ensure_ascii=False)
            self._atualizar_historico_sessoes(numero_sessao, dados_sessao, nome)
            return caminho
        except Exception as e:
            logging.error(f"Erro ao salvar sessão: {e}"); return None

    def _atualizar_historico_sessoes(self, numero_sessao, dados_sessao, nome_arquivo):
        paths = get_session_paths(self.api_name)
        historico = []
        if os.path.exists(paths['historico_sessoes']):
            try:
                with open(paths['historico_sessoes'], 'r') as f: historico = json.load(f)
            except: pass
        historico.append({'numero_sessao': numero_sessao, 'data': data_brasilia(),
                          'hora': formatar_hora_brasilia(), 'arquivo': nome_arquivo,
                          'acertos': dados_sessao.get('acertos', 0), 'erros': dados_sessao.get('erros', 0),
                          'taxa_acerto': dados_sessao.get('taxa_acerto', 0),
                          'total_rodadas': dados_sessao.get('total_rodadas', 0)})
        if len(historico) > 100: historico = historico[-100:]
        try:
            with open(paths['historico_sessoes'], 'w') as f: json.dump(historico, f, indent=2)
        except: pass

    def listar_sessoes(self):
        sessoes = []
        if os.path.exists(self.pasta_sessao):
            for arquivo in sorted(os.listdir(self.pasta_sessao), reverse=True):
                if arquivo.endswith('.json') and arquivo.startswith('sessao_'):
                    caminho = os.path.join(self.pasta_sessao, arquivo)
                    try:
                        with open(caminho, 'r') as f:
                            dados = json.load(f); dados['arquivo'] = arquivo; dados['caminho'] = caminho
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
        consolidado = {'data': data, 'roleta': self.api_name, 'total_sessoes': len(sessoes_dia),
                       'sessoes': [], 'resumo_geral': {'total_acertos': 0, 'total_erros': 0, 'total_rodadas': 0}}
        for sessao in sessoes_dia:
            stats = sessao.get('estatisticas', {})
            consolidado['sessoes'].append({'numero': sessao.get('numero_sessao'), 'hora': sessao.get('hora_encerramento'),
                                           'acertos': stats.get('acertos', 0), 'erros': stats.get('erros', 0),
                                           'taxa': stats.get('taxa_acerto', 0), 'entradas': sessao.get('entradas', [])})
            consolidado['resumo_geral']['total_acertos'] += stats.get('acertos', 0)
            consolidado['resumo_geral']['total_erros'] += stats.get('erros', 0)
            consolidado['resumo_geral']['total_rodadas'] += stats.get('total_rodadas', 0)
        total = consolidado['resumo_geral']['total_acertos'] + consolidado['resumo_geral']['total_erros']
        consolidado['resumo_geral']['taxa_geral'] = round((consolidado['resumo_geral']['total_acertos'] / max(1, total)) * 100, 1)
        nome = f"consolidado_{data}_{self.api_name.lower().replace(' ', '_')}.json"
        caminho = os.path.join(self.pasta_sessao, nome)
        with open(caminho, 'w', encoding='utf-8') as f: json.dump(consolidado, f, indent=2, ensure_ascii=False)
        return caminho

    def gerar_csv_sessao(self, dados_sessao):
        output = StringIO(); writer = csv.writer(output)
        writer.writerow(['Rodada','Hora','Número','Raio','Dúzia Real','Dúzia Prevista','Cobertura',
                         'Confiança','Gatilho','Zero','Anti-Erro','Acerto Dúzia','Acerto Número','Acerto Zero','Status','Streak'])
        for e in dados_sessao.get('entradas', []):
            real = f"D{e.get('duzia_real',0)}" if e.get('duzia_real',0) != 0 else "0"
            writer.writerow([e.get('rodada'), e.get('hora'), e.get('numero', 0),
                             f"{e.get('multiplicador',0)}x" if e.get('eh_raio') else '-',
                             real, f"D{e.get('duzia_prevista','?')}",
                             f"D{e.get('duzia_sec_prevista','?')}" if e.get('duzia_sec_prevista') else '-',
                             f"{e.get('confianca',0):.1f}", e.get('gatilho','-'),
                             'Sim' if e.get('incluir_zero') else 'Não',
                             'Sim' if e.get('modo_anti_erro') else 'Não',
                             'Sim' if e.get('acerto_duzia') else 'Não',
                             'Sim' if e.get('acerto_numero') else 'Não',
                             'Sim' if e.get('acerto_zero') else 'Não',
                             e.get('status','?'), str(e.get('streak_info', '-'))])
        return output.getvalue()

    def get_download_link(self, conteudo, nome_arquivo, tipo='json'):
        b64 = base64.b64encode(conteudo.encode()).decode()
        mime = 'text/csv' if tipo == 'csv' else 'application/json'
        return f'<a href="data:{mime};base64,{b64}" download="{nome_arquivo}">📥 Baixar {nome_arquivo}</a>'


def salvar_sessao():
    try:
        if 'sistema' not in st.session_state or st.session_state.sistema is None: return False
        sis = st.session_state.sistema
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        paths = get_session_paths(api_name)
        with open(paths['performance'], 'w') as f:
            json.dump({'acertos_duzia': sis.acertos_duzia, 'erros_duzia': sis.erros_duzia,
                       'acertos_numero': sis.acertos_numero, 'erros_numero': sis.erros_numero,
                       'acertos_zero': sis.acertos_zero, 'erros_zero': sis.erros_zero}, f)
        with open(paths['entradas'], 'w') as f: json.dump(sis.historico_entradas, f)
        with open(paths['performance_mesa'], 'w') as f: json.dump(dict(sis.performance_por_mesa), f)
        with open(paths['performance_horario'], 'w') as f: json.dump(dict(sis.performance_por_horario), f)
        sis.duzia_ai._salvar_padroes_hibridos()
        with open(paths['sessao_controle'], 'w') as f:
            json.dump({'rodadas_na_sessao': sis.rodadas_na_sessao, 'sessao_ativa': sis.sessao_ativa,
                       'sessao_pausa_ate': sis.sessao_pausa_ate.isoformat() if sis.sessao_pausa_ate else None,
                       'total_sessoes': sis.total_sessoes, 'acertos_sessao': sis.acertos_sessao,
                       'erros_sessao': sis.erros_sessao}, f)
        with open(paths['session'], 'wb') as f:
            pickle.dump({'historico_numeros': list(sis.historico_numeros),
                         'entrada_ativa': sis.entrada_ativa,
                         'acertos_duzia': sis.acertos_duzia, 'erros_duzia': sis.erros_duzia,
                         'acertos_numero': sis.acertos_numero, 'erros_numero': sis.erros_numero,
                         'acertos_zero': sis.acertos_zero, 'erros_zero': sis.erros_zero,
                         'numero_rodada': sis.numero_rodada,
                         'rodadas_na_sessao': sis.rodadas_na_sessao, 'sessao_ativa': sis.sessao_ativa,
                         'sessao_pausa_ate': sis.sessao_pausa_ate.isoformat() if sis.sessao_pausa_ate else None,
                         'total_sessoes': sis.total_sessoes,
                         'acertos_sessao': sis.acertos_sessao, 'erros_sessao': sis.erros_sessao,
                         'ultimo_treino_ml': sis.duzia_ai.ultimo_treino_ml,
                         'acertos_primaria': sis.acertos_primaria, 'acertos_secundaria': sis.acertos_secundaria}, f)
        if sis.duzia_ai.modelo_ml is not None: salvar_modelo_ml(sis.duzia_ai.modelo_ml, api_name)
        salvar_config_global()
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar: {e}"); return False

def carregar_dados_persistidos(api_name):
    paths = get_session_paths(api_name)
    dados = {}
    try:
        if os.path.exists(paths['session']):
            with open(paths['session'], 'rb') as f: dados = pickle.load(f)
            if os.path.exists(paths['entradas']):
                with open(paths['entradas'], 'r') as f2: dados['historico_entradas'] = json.load(f2)
            if os.path.exists(paths['performance_mesa']):
                with open(paths['performance_mesa'], 'r') as f3: dados['performance_por_mesa'] = json.load(f3)
            if os.path.exists(paths['performance_horario']):
                with open(paths['performance_horario'], 'r') as f4: dados['performance_por_horario'] = json.load(f4)
            if os.path.exists(paths['sessao_controle']):
                with open(paths['sessao_controle'], 'r') as f5: dados.update(json.load(f5))
    except: pass
    return dados

def nova_sessao():
    try:
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        paths = get_session_paths(api_name)
        for path in paths.values():
            if isinstance(path, str) and os.path.exists(path): os.remove(path)
        modelo_path = get_modelo_ml_path(api_name)
        if os.path.exists(modelo_path): os.remove(modelo_path)
        if 'sistema' in st.session_state: st.session_state.sistema.zerar()
        st.session_state.historico = []
        return True
    except Exception as e:
        logging.error(f"Erro: {e}"); return False

def _selecionar_melhores_numeros(duzia, numeros_completos, quantidade=6):
    if duzia == 1: nums = list(range(1, 13))
    elif duzia == 2: nums = list(range(13, 25))
    else: nums = list(range(25, 37))
    recentes = numeros_completos[-20:] if len(numeros_completos) >= 20 else numeros_completos
    freq = Counter([n for n in recentes if n in nums])
    termos = [n % 10 for n in recentes[-15:] if n != 0]
    terminais_quentes = [t for t, f in Counter(termos).most_common(3) if f >= 2]
    pontuacao = {}
    for num in nums:
        score = freq.get(num, 0) * 3
        if num % 10 in terminais_quentes: score += 2
        if num in recentes[-5:]: score += 1
        pontuacao[num] = score
    melhores = [n for n, s in sorted(pontuacao.items(), key=lambda x: x[1], reverse=True)[:quantidade] if s > 0]
    if len(melhores) < quantidade:
        for num in nums:
            if num not in melhores: melhores.append(num)
            if len(melhores) >= quantidade: break
    return sorted(melhores[:quantidade])

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
        if streak_info: msg += f" | 🔥 Streak: {streak_info}"
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
            enviar_telegram(f"🎯: {melhores_str}" + (" + 🟢 ZERO" if incluir_zero else ""),
                           st.session_state.telegram_token_alt, st.session_state.telegram_chat_id_alt)
        salvar_sessao()
    except Exception as e: logging.error(f"Erro enviar previsão: {e}")

def enviar_resultado_auto(numero_real, acerto_duzia, acerto_numero, acerto_zero, eh_raio=False, multiplicador=0):
    try:
        partes = []
        if acerto_zero: partes.append("✅ ZERO!")
        elif numero_real == 0: partes.append("🟢 ZERO (não apostado)")
        else:
            duzia_real = get_duzia(numero_real)
            if acerto_numero:
                partes.append(f"⚡ RAIO {multiplicador}X! Nº {numero_real}" if eh_raio else f"🎯 Nº EXATO {numero_real}!")
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
    except Exception as e: logging.error(f"Erro resultado: {e}")

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
    try: num = int(valor); return 0 <= num <= 36
    except: return False

def fetch_XXXtreme_Lightning():
    try:
        r = requests.get(API_URLS['XXXtreme Lightning'], headers=HEADERS, timeout=5); r.raise_for_status()
        d = r.json(); gd = d.get("data", {}); rs = gd.get("result", {})
        nm = rs.get("outcome", {}).get("number"); ts = gd.get("startedAt")
        ti = gd.get("table", {}); ln = []; lm = {}
        for item in rs.get('luckyNumbersList', []):
            n = item.get('number')
            if n is not None:
                ln.append(n)
                m = item.get('roundedMultiplier')
                if m is not None: lm[n] = m
        return {"number": nm, "timestamp": ts, "luckyNumbers": ln, "luckyMultipliers": lm,
                "table_id": ti.get("id", "unknown"), "table_name": ti.get("name", "Desconhecida")}
    except Exception as e: logging.warning(f"❌ Erro XXXtreme: {e}"); return None

def fetch_Immersive_Roulette():
    try:
        r = requests.get(API_URLS['Immersive Roulette'], headers=HEADERS, timeout=5); r.raise_for_status()
        d = r.json(); data = d.get("data", {}); outcome = data.get("result", {}).get("outcome", {})
        ti = data.get("table", {})
        return {"number": outcome.get("number"), "timestamp": data.get("startedAt"),
                "luckyNumbers": [], "luckyMultipliers": {},
                "table_id": ti.get("id", "unknown"), "table_name": ti.get("name", "Desconhecida")}
    except Exception as e: logging.warning(f"❌ Erro Immersive: {e}"); return None

def fetch_Mega_Roulette():
    try:
        r = requests.get(API_URLS['Mega Roulette'], headers=HEADERS, timeout=5); r.raise_for_status()
        d = r.json(); gd = d.get("data", {}); rs = gd.get("result", {})
        nm = rs.get("outcome", {}).get("number"); ts = gd.get("startedAt")
        ti = gd.get("table", {}); ln = []; lm = {}
        for item in rs.get('luckyNumbersList', []):
            n = item.get('number')
            if n is not None:
                ln.append(n)
                m = item.get('roundedMultiplier')
                if m is not None: lm[n] = m
        return {"number": nm, "timestamp": ts, "luckyNumbers": ln, "luckyMultipliers": lm,
                "table_id": ti.get("id", "unknown"), "table_name": ti.get("name", "Desconhecida")}
    except Exception as e: logging.warning(f"❌ Erro Mega: {e}"); return None

FETCH_FUNCTIONS = {
    'XXXtreme Lightning': fetch_XXXtreme_Lightning,
    'Immersive Roulette': fetch_Immersive_Roulette,
    'Mega Roulette': fetch_Mega_Roulette,
}

def fetch_latest_result():
    api = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
    return FETCH_FUNCTIONS.get(api, fetch_XXXtreme_Lightning)()


# =============================
# FUNÇÕES AUXILIARES
# =============================
def _calcular_entropia(duzias):
    if not duzias: return 0.0
    freq = Counter(duzias); total = len(duzias); entropia = 0.0
    for v in freq.values():
        p = v / total
        if p > 0: entropia -= p * np.log2(p)
    return round(entropia, 4)

def _calcular_gap_duzia(numeros, duzia):
    for i, n in enumerate(reversed(numeros)):
        if get_duzia(n) == duzia: return i
    return len(numeros)

def _calcular_autocorrelacao(serie, lag=3):
    if len(serie) < lag + 4: return 0.0
    try:
        s = np.array(serie, dtype=float); s1 = s[:-lag]; s2 = s[lag:]
        if np.std(s1) < 1e-9 or np.std(s2) < 1e-9: return 0.0
        corr = np.corrcoef(s1, s2)[0, 1]
        return float(corr) if not np.isnan(corr) else 0.0
    except: return 0.0


# =============================
# 🧠 DUZIA AI V13.3 — 10 BUGS CORRIGIDOS
# BUG #1  FIX: _treinar_ml_online não atualiza mais padrao_stats_ui durante treino
# BUG #2  FIX: padrao_min_ocorrencias compatível com janela de treino
# BUG #3  FIX: ml_max_repeticoes_mesma_duzia mínimo 2
# BUG #4  FIX: _extrair_features_padroes_hibridos tem modo 'treino' que não atualiza UI
# BUG #5  FIX: ml_score_minimo_fallback calibrado para score real do fallback
# BUG #6  FIX: confiança calibrada por modo (ML usa /20, fallback usa /15)
# BUG #7  FIX: modo_anti_erro verificado com erros_consecutivos, não flag isolada
# BUG #8  FIX: pode_processar verificado ANTES de incrementar rodadas
# BUG #9  FIX: drift reseta automaticamente após N rodadas sem entradas
# BUG #10 FIX: padrao_qualidade_min dinâmico baseado no histórico disponível
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
        self.streak_ativo = None
        self.alerta_zero_ativo = False
        self.pausa_ate = None
        self.modo_anti_erro = False
        self.duzias_que_sairam = []
        self.ultimo_resultado_duzia = None
        self.ultimo_resultado_numero = None
        self.ultima_confianca = 0
        self.ultima_previsao_duzia = None
        self.alertas_zero_disparados = 0
        self.zeros_previstos = 0
        self.acertos_consecutivos_mesma_duzia = 0
        self.ultima_duzia_acertada = None
        self.rodadas_desde_zero = 0
        self.ultimo_raio_alto = 0
        self.rodadas_pos_raio = 0
        self.em_pausa_pos_raio = False
        self.modelo_ml = None
        self.ultimo_treino_ml = 0
        self.mesa_atual = None
        self.api_name = api_name
        self.performance_por_mesa = defaultdict(lambda: {'acertos': 0, 'erros': 0})
        self.performance_por_horario = defaultdict(lambda: {'acertos': 0, 'erros': 0})
        self.contagem_repeticoes_mesma_duzia = 0
        self.padroes_tam2 = defaultdict(Counter)
        self.padroes_tam3 = defaultdict(Counter)
        self.padroes_tam4 = defaultdict(Counter)
        self._rodadas_desde_decaimento = 0
        self._streak_info_atual = {}
        # BUG #9 FIX: contador de rodadas sem entrada para reset do drift
        self._rodadas_sem_entrada = 0

        config = self._get_config()
        self.padrao_min_ocorrencias = config.get('padrao_min_ocorrencias', 3)
        self.peso_tam2 = config.get('padrao_peso_tam2', 20)
        self.peso_tam3 = config.get('padrao_peso_tam3', 50)
        self.peso_tam4 = config.get('padrao_peso_tam4', 30)
        self.conf_min_tam2 = config.get('padrao_conf_minima_tam2', 2)
        self.conf_min_tam4 = config.get('padrao_conf_minima_tam4', 4)
        self.consenso_peso_extra = config.get('padrao_consenso_peso_extra', 15)
        self.consenso_min_conf = config.get('padrao_consenso_min_conf', 0.20)
        self.ml_ignorar_consenso_conf_min = config.get('ml_ignorar_consenso_conf_min', 2.5)
        self.padrao_qualidade_min_p2 = config.get('padrao_qualidade_min_p2', 15)
        self.padrao_qualidade_min_p3 = config.get('padrao_qualidade_min_p3', 10)
        self.padrao_qualidade_min_p4 = config.get('padrao_qualidade_min_p4', 8)
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
        self.drift_taxa_minima = config.get('drift_taxa_minima', 0.30)
        self.drift_alertar_apos = config.get('drift_alertar_apos', 5)
        self.drift_rodadas_auto_reset = config.get('drift_rodadas_auto_reset', 20)
        self._drift_ativo = False
        self._drift_erros_consecutivos_entrada = 0
        self.streak_config_ativo = config.get('streak_ativo', True)
        self.streak_min_len = config.get('streak_min_len', 2)
        self.streak_peso_feature = config.get('streak_peso_feature', 1.0)

        # BUG #4 FIX: padrao_stats_ui só atualizado pelo estado atual, nunca pelo treino
        self.padrao_ativo_ui = {'tam2': None, 'tam3': None, 'tam4': None}
        self.padrao_stats_ui = {'tam2': None, 'tam3': None, 'tam4': None}
        self.consenso_info = {'tipo': 'nenhum', 'duzia': None, 'conf': 0.0}

        self._carregar_modelo_salvo()
        self._carregar_padroes_hibridos()

    def _carregar_modelo_salvo(self):
        if not ML_DISPONIVEL: return
        modelo = carregar_modelo_ml(self.api_name)
        if modelo is not None:
            self.modelo_ml = modelo
            self.ultimo_treino_ml = 1
            logging.info(f"🧠 Modelo ML carregado do disco para {self.api_name}")

    def _salvar_padroes_hibridos(self):
        paths = get_session_paths(self.api_name)
        caminho = paths.get('padroes_hibridos', '')
        if not caminho: return
        try:
            dados = {
                'tam2': {str(k): dict(v) for k, v in self.padroes_tam2.items()},
                'tam3': {str(k): dict(v) for k, v in self.padroes_tam3.items()},
                'tam4': {str(k): dict(v) for k, v in self.padroes_tam4.items()},
            }
            with open(caminho, 'w') as f: json.dump(dados, f)
        except Exception as e: logging.error(f"❌ Erro ao salvar padrões: {e}")

    def _carregar_padroes_hibridos(self):
        paths = get_session_paths(self.api_name)
        caminho = paths.get('padroes_hibridos', '')
        if caminho and os.path.exists(caminho):
            try:
                import ast
                with open(caminho, 'r') as f: dados = json.load(f)
                for k, v in dados.get('tam2', {}).items():
                    try: self.padroes_tam2[int(k)] = Counter({int(dk): dv for dk, dv in v.items()})
                    except: pass
                for k, v in dados.get('tam3', {}).items():
                    try: self.padroes_tam3[tuple(ast.literal_eval(k))] = Counter({int(dk): dv for dk, dv in v.items()})
                    except: pass
                for k, v in dados.get('tam4', {}).items():
                    try: self.padroes_tam4[tuple(ast.literal_eval(k))] = Counter({int(dk): dv for dk, dv in v.items()})
                    except: pass
            except Exception as e: logging.error(f"❌ Erro ao carregar padrões: {e}")

    def _atualizar_padroes_hibridos(self, historico_duzias):
        duzias = [d for d in historico_duzias if d != 0]
        if len(duzias) >= 2:
            for i in range(len(duzias) - 1): self.padroes_tam2[duzias[i]][duzias[i+1]] += 1
        if len(duzias) >= 3:
            for i in range(len(duzias) - 2): self.padroes_tam3[(duzias[i], duzias[i+1])][duzias[i+2]] += 1
        if len(duzias) >= 4:
            for i in range(len(duzias) - 3): self.padroes_tam4[(duzias[i], duzias[i+1], duzias[i+2])][duzias[i+3]] += 1
        if self.decaimento_padroes_ativo:
            self._rodadas_desde_decaimento += 1
            if self._rodadas_desde_decaimento >= self.decaimento_a_cada:
                self._rodadas_desde_decaimento = 0
                aplicar_decaimento_padroes(self.padroes_tam2, self.decaimento_fator)
                aplicar_decaimento_padroes(self.padroes_tam3, self.decaimento_fator)
                aplicar_decaimento_padroes(self.padroes_tam4, self.decaimento_fator)

    # BUG #10 FIX: qualidade mínima dinâmica baseada no histórico real
    def _get_qualidade_min_dinamica(self):
        n = len(self.historico_completo)
        # Escala: começa em 5, cresce gradualmente até o valor configurado
        fator = min(1.0, n / 80.0)
        q_p2 = max(5, int(self.padrao_qualidade_min_p2 * fator))
        q_p3 = max(4, int(self.padrao_qualidade_min_p3 * fator))
        q_p4 = max(3, int(self.padrao_qualidade_min_p4 * fator))
        return q_p2, q_p3, q_p4

    def _verificar_qualidade_padroes(self):
        q_p2, q_p3, q_p4 = self._get_qualidade_min_dinamica()
        p2_stats = self.padrao_stats_ui.get('tam2')
        p3_stats = self.padrao_stats_ui.get('tam3')
        p4_stats = self.padrao_stats_ui.get('tam4')
        p2_total = p2_stats.get('total', 0) if p2_stats else 0
        p3_total = p3_stats.get('total', 0) if p3_stats else 0
        p4_total = p4_stats.get('total', 0) if p4_stats else 0
        p2_ok = p2_total > q_p2
        p3_ok = p3_total > q_p3
        p4_ok = p4_total > q_p4
        return sum([p2_ok, p3_ok, p4_ok]), {'p2': p2_ok, 'p3': p3_ok, 'p4': p4_ok}

    def _detectar_consenso(self, scores_p2, scores_p3, scores_p4, conf_p2, conf_p3, conf_p4):
        padroes_validos, qualidade = self._verificar_qualidade_padroes()
        # BUG #10 FIX: consenso funciona com 1+ padrão válido (era 2)
        if padroes_validos < 1:
            return 'nenhum', None, 0.0
        preferencias = []; confs = []
        if scores_p2 and conf_p2 >= self.consenso_min_conf and qualidade['p2']:
            preferencias.append(max(scores_p2, key=scores_p2.get)); confs.append(conf_p2)
        if scores_p3 and conf_p3 >= self.consenso_min_conf and qualidade['p3']:
            preferencias.append(max(scores_p3, key=scores_p3.get)); confs.append(conf_p3)
        if scores_p4 and conf_p4 >= self.consenso_min_conf and qualidade['p4']:
            preferencias.append(max(scores_p4, key=scores_p4.get)); confs.append(conf_p4)
        if len(preferencias) < 1: return 'nenhum', None, 0.0
        contagem = Counter(preferencias); mais_comum = contagem.most_common(1)[0]
        if mais_comum[1] >= 3: return 'triplo', mais_comum[0], sum(confs) / len(confs)
        elif mais_comum[1] >= 2: return 'duplo', mais_comum[0], sum(confs) / len(confs)
        elif len(preferencias) == 1: return 'simples', preferencias[0], confs[0]
        return 'nenhum', None, 0.0

    def _get_config(self):
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        return ROLETA_CONFIGS.get(api_name, SETUP_XXXTREME).copy()

    def _aplicar_peso_adaptativo(self, scores):
        if not self.peso_adaptativo_ativo: return scores
        duzias_reais = [d for d in self.historico_completo[-self.peso_adaptativo_janela:] if d != 0]
        if len(duzias_reais) < 5: return scores
        freq = Counter(duzias_reais); total = len(duzias_reais)
        scores_ajustados = scores.copy()
        for duzia in [1, 2, 3]:
            freq_pct = freq.get(duzia, 0) / total
            if freq_pct >= 0.40:
                boost = 1.0 + (freq_pct - 0.40) * (self.peso_adaptativo_boost - 1.0) / 0.60
                scores_ajustados[duzia] *= boost
        return scores_ajustados

    def _extrair_features_temporais(self, historico_duzias):
        agora = hora_brasilia(); hora = agora.hour; minuto = agora.minute
        turno = 0 if 6 <= hora < 12 else (1 if 12 <= hora < 18 else 2)
        duzias = [d for d in historico_duzias if d != 0]
        tendencia = {1: 0.0, 2: 0.0, 3: 0.0}
        if len(duzias) >= 15:
            rec5 = Counter(duzias[-5:]); rec15 = Counter(duzias[-15:])
            for d in [1, 2, 3]: tendencia[d] = round((rec5.get(d, 0) / 5.0) - (rec15.get(d, 0) / 15.0), 4)
        return [hora / 23.0, minuto / 59.0, float(turno) / 2.0, tendencia[1], tendencia[2], tendencia[3]]

    # BUG #4 FIX: parâmetro 'modo_treino' para não atualizar padrao_stats_ui durante treino
    def _extrair_features_padroes_hibridos(self, historico_duzias, modo_treino=False):
        duzias = [d for d in historico_duzias if d != 0]
        features = {}
        for prefixo in ['p2', 'p3', 'p4']:
            for k in ['d1', 'd2', 'd3', 'conf', 'total', 'dom']: features[f'{prefixo}_{k}'] = 0.0
        features.update({'combo_d1': 0.0, 'combo_d2': 0.0, 'combo_d3': 0.0, 'combo_conf': 0.0})
        if len(duzias) < 1: return features

        combo_scores = {1: 0.0, 2: 0.0, 3: 0.0}; combo_conf_total = 0.0; soma_pesos = 0.0
        scores_p2 = scores_p3 = scores_p4 = None
        conf_p2 = conf_p3 = conf_p4 = 0.0
        q_p2, q_p3, q_p4 = self._get_qualidade_min_dinamica()  # BUG #10 FIX

        # --- Padrão 2 ---
        if len(duzias) >= 1:
            d1 = duzias[-1]
            if d1 in self.padroes_tam2:
                dist = self.padroes_tam2[d1]; total = sum(dist.values())
                if total >= self.conf_min_tam2:
                    scores = {k: dist.get(k, 0)/total for k in [1,2,3]}
                    max_s = max(scores.values()); seg_s = sorted(scores.values(), reverse=True)[1]
                    features['p2_d1'] = scores.get(1, 0.0); features['p2_d2'] = scores.get(2, 0.0)
                    features['p2_d3'] = scores.get(3, 0.0)
                    features['p2_conf'] = round((max_s - seg_s) * min(1.0, total/20), 4)
                    features['p2_total'] = float(total); features['p2_dom'] = round(max_s - seg_s, 4)
                    if total > q_p2:  # BUG #10 FIX: usa qualidade dinâmica
                        peso = self.peso_tam2 / 100.0
                        for k in [1,2,3]: combo_scores[k] += scores[k] * features['p2_conf'] * peso
                        combo_conf_total += features['p2_conf'] * peso; soma_pesos += peso
                    scores_p2 = scores; conf_p2 = features['p2_conf']
                    # BUG #4 FIX: só atualiza UI se não for modo treino
                    if not modo_treino:
                        self.padrao_stats_ui['tam2'] = {'gatilho': f"D{d1}", 'total': total, 'scores': scores, 'conf': features['p2_conf']}
                        self.padrao_ativo_ui['tam2'] = d1
                else:
                    if not modo_treino: self.padrao_stats_ui['tam2'] = None; self.padrao_ativo_ui['tam2'] = None

        # --- Padrão 3 ---
        if len(duzias) >= 2:
            d1, d2 = duzias[-2], duzias[-1]; par = (d1, d2)
            if par in self.padroes_tam3:
                dist = self.padroes_tam3[par]; total = sum(dist.values())
                if total >= self.padrao_min_ocorrencias:
                    scores = {k: dist.get(k, 0)/total for k in [1,2,3]}
                    max_s = max(scores.values()); seg_s = sorted(scores.values(), reverse=True)[1]
                    features['p3_d1'] = scores.get(1, 0.0); features['p3_d2'] = scores.get(2, 0.0)
                    features['p3_d3'] = scores.get(3, 0.0)
                    features['p3_conf'] = round((max_s - seg_s) * (1 + np.log1p(total)/5), 4)
                    features['p3_total'] = float(total); features['p3_dom'] = round(max_s - seg_s, 4)
                    if total > q_p3:  # BUG #10 FIX
                        peso = self.peso_tam3 / 100.0
                        for k in [1,2,3]: combo_scores[k] += scores[k] * features['p3_conf'] * peso
                        combo_conf_total += features['p3_conf'] * peso; soma_pesos += peso
                    scores_p3 = scores; conf_p3 = features['p3_conf']
                    if not modo_treino:
                        self.padrao_stats_ui['tam3'] = {'gatilho': f"D{d1}→D{d2}", 'total': total, 'scores': scores, 'conf': features['p3_conf']}
                        self.padrao_ativo_ui['tam3'] = par
                else:
                    if not modo_treino: self.padrao_stats_ui['tam3'] = None; self.padrao_ativo_ui['tam3'] = None

        # --- Padrão 4 ---
        if len(duzias) >= 3:
            d1, d2, d3 = duzias[-3], duzias[-2], duzias[-1]; trio = (d1, d2, d3)
            if trio in self.padroes_tam4:
                dist = self.padroes_tam4[trio]; total = sum(dist.values())
                if total >= self.conf_min_tam4:
                    scores = {k: dist.get(k, 0)/total for k in [1,2,3]}
                    max_s = max(scores.values()); seg_s = sorted(scores.values(), reverse=True)[1]
                    features['p4_d1'] = scores.get(1, 0.0); features['p4_d2'] = scores.get(2, 0.0)
                    features['p4_d3'] = scores.get(3, 0.0)
                    features['p4_conf'] = round((max_s - seg_s) * (1 + np.log1p(total)/3), 4)
                    features['p4_total'] = float(total); features['p4_dom'] = round(max_s - seg_s, 4)
                    if total > q_p4:  # BUG #10 FIX
                        peso = self.peso_tam4 / 100.0
                        for k in [1,2,3]: combo_scores[k] += scores[k] * features['p4_conf'] * peso
                        combo_conf_total += features['p4_conf'] * peso; soma_pesos += peso
                    scores_p4 = scores; conf_p4 = features['p4_conf']
                    if not modo_treino:
                        self.padrao_stats_ui['tam4'] = {'gatilho': f"D{d1}→D{d2}→D{d3}", 'total': total, 'scores': scores, 'conf': features['p4_conf']}
                        self.padrao_ativo_ui['tam4'] = trio
                else:
                    if not modo_treino: self.padrao_stats_ui['tam4'] = None; self.padrao_ativo_ui['tam4'] = None

        if soma_pesos > 0:
            for k in [1,2,3]: features[f'combo_d{k}'] = round(combo_scores[k] / soma_pesos, 4)
            features['combo_conf'] = round(combo_conf_total / soma_pesos, 4)

        if not modo_treino:  # BUG #4 FIX: consenso só atualizado fora do treino
            tipo, duzia, conf = self._detectar_consenso(scores_p2, scores_p3, scores_p4, conf_p2, conf_p3, conf_p4)
            self.consenso_info = {'tipo': tipo, 'duzia': duzia, 'conf': conf}

        return features

    def _extrair_features_streak_ml(self, historico_duzias):
        st_info = extrair_features_streak(historico_duzias)
        self._streak_info_atual = st_info
        return [
            float(st_info['streak_atual_duzia']), float(st_info['streak_atual_len']),
            float(st_info['streak_duzia1_len']), float(st_info['streak_duzia2_len']), float(st_info['streak_duzia3_len']),
            float(st_info['prob_continua_streak2']), float(st_info['prob_continua_streak3']),
            float(st_info['prob_quebra_streak2']), float(st_info['prob_quebra_streak3']),
            float(st_info['streak_max_recente']), float(st_info['entrada_streak_duzia']),
            float(st_info['cobertura_streak_duzia']), float(st_info['streak_quebra_iminente']),
            float(st_info['streak_forca']), float(st_info.get('streak_saturado', 0)),
            float(st_info.get('streak_taxa_quebra_real', 0.0)),
        ]

    # BUG #4 FIX: parâmetro modo_treino propagado para _extrair_features_padroes_hibridos
    def _extrair_features_core(self, historico_duzias, historico_numeros,
                                erros_consec, rodadas_zero, repeticoes_duzia, janela=20, modo_treino=False):
        numeros_janela = historico_numeros[-janela:] if len(historico_numeros) >= janela else historico_numeros
        duzias_janela = [d for d in historico_duzias[-janela:] if d != 0]
        if not duzias_janela or len(historico_duzias) < 5: return None

        ultimas_4_raw = list(historico_duzias[-4:])
        while len(ultimas_4_raw) < 4: ultimas_4_raw = [0] + ultimas_4_raw
        ultimas_4 = ultimas_4_raw[:4]

        terminais = [n % 10 for n in numeros_janela if n != 0]
        contagem_terminais = Counter(terminais).most_common(3)
        t1_quente = contagem_terminais[0][0] if contagem_terminais else -1
        t2_quente = contagem_terminais[1][0] if len(contagem_terminais) > 1 else -1
        freq_terminal_zero = terminais.count(0)

        try: rodadas_sem_zero = list(reversed(numeros_janela)).index(0)
        except ValueError: rodadas_sem_zero = janela
        contagem_zeros_janela = numeros_janela.count(0)

        freq_total = Counter(duzias_janela)
        freq_recente = Counter(duzias_janela[-8:]) if len(duzias_janela) >= 8 else Counter(duzias_janela)
        freq_d1 = freq_total.get(1, 0); freq_d2 = freq_total.get(2, 0); freq_d3 = freq_total.get(3, 0)
        freq_d1_rec = freq_recente.get(1, 0); freq_d2_rec = freq_recente.get(2, 0); freq_d3_rec = freq_recente.get(3, 0)
        duzia_dominante = freq_total.most_common(1)[0][0] if freq_total else -1
        duzia_recente = freq_recente.most_common(1)[0][0] if freq_recente else -1

        streak_count = 1
        for i in range(len(duzias_janela) - 1, 0, -1):
            if duzias_janela[i] == duzias_janela[i - 1]: streak_count += 1
            else: break

        max_streak = 1; cur_streak = 1
        for i in range(1, len(duzias_janela)):
            if duzias_janela[i] == duzias_janela[i - 1]: cur_streak += 1; max_streak = max(max_streak, cur_streak)
            else: cur_streak = 1

        transicoes_recentes = sum(1 for i in range(1, min(10, len(duzias_janela))) if duzias_janela[-i] != duzias_janela[-i-1])

        aba_pattern = 0
        if len(duzias_janela) >= 3 and duzias_janela[-1] == duzias_janela[-3] and duzias_janela[-1] != duzias_janela[-2]:
            aba_pattern = 1

        gap_d1 = next((i for i, n in enumerate(reversed(historico_numeros)) if get_duzia(n) == 1), len(historico_numeros))
        gap_d2 = next((i for i, n in enumerate(reversed(historico_numeros)) if get_duzia(n) == 2), len(historico_numeros))
        gap_d3 = next((i for i, n in enumerate(reversed(historico_numeros)) if get_duzia(n) == 3), len(historico_numeros))

        n_total = max(1, len(duzias_janela)); esperado = n_total / 3
        volatilidade = abs(freq_d1 - esperado) + abs(freq_d2 - esperado) + abs(freq_d3 - esperado)
        nums_nao_zero = [n for n in numeros_janela if n != 0]
        paridade = sum(1 for n in nums_nao_zero if n % 2 == 0) / max(1, len(nums_nao_zero))
        entropia = _calcular_entropia(duzias_janela)
        gaps = {1: gap_d1, 2: gap_d2, 3: gap_d3}; duzia_mais_ausente = max(gaps, key=gaps.get)

        seq_recente = [get_duzia(n) for n in historico_numeros[-5:] if n != 0]
        mono_up = 1 if len(seq_recente) >= 3 and all(seq_recente[i] <= seq_recente[i+1] for i in range(len(seq_recente)-1)) else 0
        mono_down = 1 if len(seq_recente) >= 3 and all(seq_recente[i] >= seq_recente[i+1] for i in range(len(seq_recente)-1)) else 0

        autocorr_lag2 = _calcular_autocorrelacao(duzias_janela, lag=2)
        autocorr_lag3 = _calcular_autocorrelacao(duzias_janela, lag=3)

        ultimas5 = [d for d in historico_duzias[-5:] if d != 0]
        prop_d1_rec5 = ultimas5.count(1) / max(1, len(ultimas5))
        prop_d2_rec5 = ultimas5.count(2) / max(1, len(ultimas5))
        prop_d3_rec5 = ultimas5.count(3) / max(1, len(ultimas5))

        abab_pattern = 0
        if len(duzias_janela) >= 4 and duzias_janela[-1] == duzias_janela[-3] and duzias_janela[-2] == duzias_janela[-4] and duzias_janela[-1] != duzias_janela[-2]:
            abab_pattern = 1

        ultimas3 = [d for d in historico_duzias[-3:] if d != 0]
        duzia_dom_3 = Counter(ultimas3).most_common(1)[0][0] if ultimas3 else 0
        ultimas6 = [d for d in historico_duzias[-6:] if d != 0]
        diversidade_6 = len(set(ultimas6)) if ultimas6 else 0
        ultima_duzia = historico_duzias[-1] if historico_duzias else 0
        penultima_duzia = historico_duzias[-2] if len(historico_duzias) >= 2 else 0
        diff_ultimas2 = abs(ultima_duzia - penultima_duzia) if (ultima_duzia != 0 and penultima_duzia != 0) else 0

        features_base = [
            float(ultimas_4[0]), float(ultimas_4[1]), float(ultimas_4[2]), float(ultimas_4[3]),
            float(t1_quente), float(t2_quente), float(freq_terminal_zero),
            float(rodadas_sem_zero), float(contagem_zeros_janela),
            float(duzia_dominante), float(duzia_recente), float(streak_count), float(max_streak),
            float(transicoes_recentes), float(aba_pattern),
            float(freq_d1), float(freq_d2), float(freq_d3),
            float(freq_d1_rec), float(freq_d2_rec), float(freq_d3_rec),
            float(gap_d1), float(gap_d2), float(gap_d3),
            float(erros_consec), float(rodadas_zero), float(volatilidade),
            float(paridade), float(entropia), float(duzia_mais_ausente),
            float(mono_up), float(mono_down), float(repeticoes_duzia),
            float(autocorr_lag2), float(autocorr_lag3),
            float(prop_d1_rec5), float(prop_d2_rec5), float(prop_d3_rec5),
            float(abab_pattern), float(duzia_dom_3), float(diversidade_6),
            float(ultima_duzia), float(penultima_duzia), float(diff_ultimas2),
        ]

        # BUG #4 FIX: passa modo_treino para não sujar padrao_stats_ui
        pf = self._extrair_features_padroes_hibridos(historico_duzias, modo_treino=modo_treino)
        features_padroes = [
            pf['p2_d1'], pf['p2_d2'], pf['p2_d3'], pf['p2_conf'], pf['p2_total'], pf['p2_dom'],
            pf['p3_d1'], pf['p3_d2'], pf['p3_d3'], pf['p3_conf'], pf['p3_total'], pf['p3_dom'],
            pf['p4_d1'], pf['p4_d2'], pf['p4_d3'], pf['p4_conf'], pf['p4_total'], pf['p4_dom'],
            pf['combo_d1'], pf['combo_d2'], pf['combo_d3'], pf['combo_conf'],
        ]

        features_temporais = self._extrair_features_temporais(historico_duzias)
        features_streak = self._extrair_features_streak_ml(historico_duzias)

        return features_base + features_padroes + features_temporais + features_streak

    def extrair_features_estado(self, janela=20):
        return self._extrair_features_core(
            historico_duzias=self.historico_completo, historico_numeros=self.numeros_completos,
            erros_consec=self.erros_consecutivos, rodadas_zero=self.rodadas_desde_zero,
            repeticoes_duzia=self.contagem_repeticoes_mesma_duzia, janela=janela,
            modo_treino=False  # Estado atual: ATUALIZA a UI
        )

    def _extrair_features_historico(self, historico_duzias, historico_numeros, janela=20):
        erros_consec = 0; rodadas_zero = 0
        for n in reversed(historico_numeros):
            if n == 0: break
            rodadas_zero += 1
        repeticoes = 0
        duzias_hist = [d for d in historico_duzias if d != 0]
        if duzias_hist:
            ultima = duzias_hist[-1]
            for d in reversed(duzias_hist[:-1]):
                if d == ultima: repeticoes += 1
                else: break
        return self._extrair_features_core(
            historico_duzias=historico_duzias, historico_numeros=historico_numeros,
            erros_consec=erros_consec, rodadas_zero=rodadas_zero,
            repeticoes_duzia=repeticoes, janela=janela,
            modo_treino=True  # BUG #4 FIX: treino NÃO ATUALIZA a UI
        )

    def _calcular_pesos_treino(self, n_amostras, fator_decaimento=0.985):
        indices = np.arange(n_amostras)
        pesos = fator_decaimento ** (n_amostras - 1 - indices)
        return pesos / pesos.mean()

    def _treinar_ml_online(self):
        if not ML_DISPONIVEL: return False
        config = self._get_config()
        janela_treino = config.get('ml_janela_treino', 80)  # BUG #1 FIX: janela menor
        atualizar_a_cada = config.get('ml_atualizar_a_cada', 10)
        rodada_atual = len(self.historico_completo)

        if self.modelo_ml is not None and self.ultimo_treino_ml > 0:
            if rodada_atual - self.ultimo_treino_ml < atualizar_a_cada: return False
        else:
            if len(self.historico_completo) < 30: return False  # BUG #1 FIX: era 40, reduzido

        try:
            X, y = [], []
            # BUG #1 FIX: limitar janela de treino para evitar loop lento
            inicio = max(0, len(self.historico_completo) - janela_treino)
            limite_amostras = min(len(self.historico_completo), inicio + janela_treino)

            for i in range(inicio + 8, limite_amostras):  # BUG #1 FIX: era inicio+10
                hist_duzias = self.historico_completo[max(0, i-janela_treino):i]
                hist_nums = self.numeros_completos[max(0, i-janela_treino):i]
                if len(hist_duzias) < 8: continue  # BUG #1 FIX: era 10
                # BUG #4 FIX: modo_treino=True → não atualiza padrao_stats_ui
                features = self._extrair_features_historico(hist_duzias, hist_nums, min(janela_treino, 20))
                if features is None: continue
                target = self.historico_completo[i]
                if target in [1, 2, 3]: X.append(features); y.append(target)

            if len(X) < 12: return False  # BUG #1 FIX: era 15

            X_arr = np.array(X)
            sample_weights = self._calcular_pesos_treino(len(X))

            rf = RandomForestClassifier(n_estimators=120, max_depth=10, random_state=42,
                                         n_jobs=-1, class_weight='balanced', min_samples_leaf=2)
            gbt = GradientBoostingClassifier(n_estimators=60, max_depth=5, learning_rate=0.10, random_state=42)

            rf.fit(X_arr, y, sample_weight=sample_weights)
            gbt.fit(X_arr, y, sample_weight=sample_weights)

            self.modelo_ml = _EnsembleManual(rf, gbt)
            self.ultimo_treino_ml = rodada_atual
            salvar_modelo_ml(self.modelo_ml, self.api_name)
            logging.info(f"🧠 ML V13.3 Treinado! Amostras: {len(X)} | Rodada: {rodada_atual} | Features: {X_arr.shape[1]}")
            return True
        except Exception as e:
            logging.error(f"❌ Erro no treino ML: {e}"); return False

    def adicionar(self, numero):
        d = get_duzia(numero)
        self.historico.append(d)
        self.historico_completo.append(d)
        self.numeros_completos.append(numero)
        if numero == 0: self.rodadas_desde_zero = 0
        else: self.rodadas_desde_zero += 1
        if d != 0:
            self.duzias_que_sairam.append(d)
            if len(self.duzias_que_sairam) > 10: self.duzias_que_sairam = self.duzias_que_sairam[-10:]
        if numero == 0 and self.alerta_zero_ativo: self.zeros_previstos += 1
        if len(self.historico_completo) >= 4:
            padrao = tuple(self.historico_completo[-4:-1])
            self.transicoes[padrao][d] += 1
        self._atualizar_padroes_hibridos(self.historico_completo)
        if len(self.historico_completo) > 1000: self.historico_completo = self.historico_completo[-1000:]
        if len(self.numeros_completos) > 1000: self.numeros_completos = self.numeros_completos[-1000:]
        if self.em_pausa_pos_raio:
            self.rodadas_pos_raio += 1
            if self.rodadas_pos_raio >= self._get_config().get('pausa_pos_raio', 1): self.em_pausa_pos_raio = False
        if self.vies_dinamico_ativo:
            self._vies_dinamico_atual, self._vies_dinamico_intensidade = detectar_vies_dinamico(
                self.historico_completo, janela=self.vies_dinamico_janela, limiar_excesso=self.vies_dinamico_limiar)
        if self.streak_config_ativo and len(self.historico_completo) >= 3:
            self._streak_info_atual = extrair_features_streak(self.historico_completo)
        # BUG #9 FIX: contar rodadas sem entrada para reset automático do drift
        self._rodadas_sem_entrada += 1
        if self._drift_ativo and self._rodadas_sem_entrada >= self.drift_rodadas_auto_reset:
            self._drift_ativo = False
            self._rodadas_sem_entrada = 0
            logging.info("🔄 Drift resetado automaticamente após rodadas sem entrada")
        self._treinar_ml_online()

    def registrar_previsao(self, duzia, confianca):
        self.ultimas_previsoes.append(duzia)
        self.ultima_previsao_duzia = duzia
        self.ultima_confianca = confianca
        if len(self.ultimas_previsoes) >= 2:
            self.contagem_repeticoes_mesma_duzia = (self.contagem_repeticoes_mesma_duzia + 1
                                                     if self.ultimas_previsoes[-1] == self.ultimas_previsoes[-2] else 1)
        else: self.contagem_repeticoes_mesma_duzia = 1
        if len(self.ultimas_previsoes) > 10: self.ultimas_previsoes = self.ultimas_previsoes[-10:]
        # BUG #9 FIX: resetar contador de rodadas sem entrada quando faz previsão
        self._rodadas_sem_entrada = 0

    def registrar_resultado(self, duzia_real, acertou_duzia, acertou_numero, acertou_zero, mesa_id=None, eh_raio=False, multiplicador=0):
        self.ultimos_resultados.append({'duzia': duzia_real, 'acertou_duzia': acertou_duzia,
                                        'acertou_numero': acertou_numero, 'acertou_zero': acertou_zero})
        self.ultimo_resultado_duzia = acertou_duzia
        self.ultimo_resultado_numero = acertou_numero
        config = self._get_config()
        if eh_raio and multiplicador >= config['raio_alto_minimo'] and config['pausa_pos_raio'] > 0:
            self.em_pausa_pos_raio = True; self.rodadas_pos_raio = 0; self.ultimo_raio_alto = multiplicador
        if mesa_id:
            self.mesa_atual = mesa_id
            if acertou_duzia or acertou_zero: self.performance_por_mesa[mesa_id]['acertos'] += 1
            else: self.performance_por_mesa[mesa_id]['erros'] += 1
        hora = datetime.now().hour
        turno = "manhã" if 6 <= hora < 12 else "tarde" if 12 <= hora < 18 else "noite"
        if acertou_duzia or acertou_zero: self.performance_por_horario[turno]['acertos'] += 1
        else: self.performance_por_horario[turno]['erros'] += 1
        if len(self.ultimos_resultados) > 50: self.ultimos_resultados = self.ultimos_resultados[-50:]

        if acertou_duzia and duzia_real != 0:
            if duzia_real == self.ultima_duzia_acertada: self.acertos_consecutivos_mesma_duzia += 1
            else: self.acertos_consecutivos_mesma_duzia = 1; self.ultima_duzia_acertada = duzia_real
        else: self.acertos_consecutivos_mesma_duzia = 0; self.ultima_duzia_acertada = None

        if not acertou_duzia and not acertou_zero:
            self.erros_consecutivos += 1
            if duzia_real != 0: self.erros_por_duzia[duzia_real] += 1
            self.modo_anti_erro = True
            self._drift_erros_consecutivos_entrada += 1
        else:
            self.erros_consecutivos = 0
            self.modo_anti_erro = False  # BUG #7 FIX: reseta corretamente
            self.erros_por_duzia = {1: 0, 2: 0, 3: 0}
            self.entradas_consecutivas += 1
            self.pausa_ate = None
            self._drift_erros_consecutivos_entrada = 0

        # BUG #9 FIX: drift avaliado com critério mais tolerante
        if len(self.ultimos_resultados) >= self.drift_alertar_apos:
            recentes = self.ultimos_resultados[-self.drift_janela:]
            acertos_rec = sum(1 for r in recentes if r['acertou_duzia'] or r['acertou_zero'])
            taxa_rec = acertos_rec / len(recentes)
            self._drift_ativo = taxa_rec < self.drift_taxa_minima and len(recentes) >= self.drift_alertar_apos
        else:
            self._drift_ativo = False

    def _prever_ml(self):
        if not ML_DISPONIVEL or self.modelo_ml is None: return {1: 0.0, 2: 0.0, 3: 0.0}
        if len(self.historico_completo) < 8: return {1: 0.0, 2: 0.0, 3: 0.0}
        try:
            features = self.extrair_features_estado(janela=20)
            if features is None: return {1: 0.0, 2: 0.0, 3: 0.0}
            try: n_features_modelo = self.modelo_ml.n_features_in_
            except: n_features_modelo = None
            if n_features_modelo is not None and len(features) != n_features_modelo:
                logging.warning(f"⚠️ Dimensão incompatível ({len(features)} vs {n_features_modelo}). Retreinando...")
                self.modelo_ml = None; self.ultimo_treino_ml = 0
                return {1: 0.0, 2: 0.0, 3: 0.0}
            probabilidades, classes = self.modelo_ml.predict_proba([features])
            ml_scores = {1: 0.0, 2: 0.0, 3: 0.0}
            for classe, prob in zip(classes, probabilidades[0]):
                if classe in ml_scores: ml_scores[classe] = float(prob) * 100
            return ml_scores
        except Exception as e:
            logging.error(f"❌ Erro na inferência ML: {e}")
            if "feature" in str(e).lower() or "shape" in str(e).lower():
                self.modelo_ml = None; self.ultimo_treino_ml = 0
            return {1: 0.0, 2: 0.0, 3: 0.0}

    def _prever_fallback_frequencia(self):
        if len(self.historico_completo) < 5: return {1: 33.3, 2: 33.3, 3: 33.3}
        janela = min(20, len(self.historico_completo))
        duzias_rec = [d for d in self.historico_completo[-janela:] if d != 0]
        total = max(1, len(duzias_rec))
        freq = {1: duzias_rec.count(1)/total, 2: duzias_rec.count(2)/total, 3: duzias_rec.count(3)/total}
        gap_d1 = _calcular_gap_duzia(self.numeros_completos, 1)
        gap_d2 = _calcular_gap_duzia(self.numeros_completos, 2)
        gap_d3 = _calcular_gap_duzia(self.numeros_completos, 3)
        gap_max = max(gap_d1, gap_d2, gap_d3, 1)
        return {1: freq[1]*60 + (gap_d1/gap_max)*40, 2: freq[2]*60 + (gap_d2/gap_max)*40, 3: freq[3]*60 + (gap_d3/gap_max)*40}

    def _aplicar_anti_vies(self, scores):
        if not self.anti_vies_ativo: return scores
        duzia_alvo = self.anti_vies_duzia
        if duzia_alvo is None and self.vies_dinamico_ativo: duzia_alvo = self._vies_dinamico_atual
        if duzia_alvo is None: return scores
        scores_ajustados = scores.copy()
        if self.anti_vies_gatilho_p2:
            p2_stats = self.padrao_stats_ui.get('tam2')
            if p2_stats and p2_stats.get('scores'):
                if max(p2_stats['scores'], key=p2_stats['scores'].get) != duzia_alvo: return scores
        p4_isolado = False
        if self.anti_vies_p4_isolado_extra < 1.0:
            p3_stats = self.padrao_stats_ui.get('tam3'); p4_stats = self.padrao_stats_ui.get('tam4')
            if p4_stats and p4_stats.get('scores') and p3_stats and p3_stats.get('scores'):
                if max(p4_stats['scores'], key=p4_stats['scores'].get) == duzia_alvo and \
                   max(p3_stats['scores'], key=p3_stats['scores'].get) != duzia_alvo: p4_isolado = True
        penalidade = self.anti_vies_penalidade * (self.anti_vies_p4_isolado_extra if p4_isolado else 1.0)
        scores_ajustados[duzia_alvo] *= penalidade
        score_removido = scores[duzia_alvo] - scores_ajustados[duzia_alvo]
        outras = [d for d in [1,2,3] if d != duzia_alvo]
        total_outras = sum(scores[d] for d in outras)
        if total_outras > 0:
            for d in outras: scores_ajustados[d] += score_removido * (scores[d] / total_outras)
        else:
            for d in outras: scores_ajustados[d] += score_removido / 2
        return scores_ajustados

    def _aplicar_vies_dinamico(self, scores):
        if not self.vies_dinamico_ativo or self._vies_dinamico_atual is None: return scores
        if self.anti_vies_ativo and self.anti_vies_duzia == self._vies_dinamico_atual: return scores
        scores_ajustados = scores.copy()
        duzia_viesada = self._vies_dinamico_atual
        intensidade = min(1.0, self._vies_dinamico_intensidade / 0.30)
        penalidade_efetiva = 1.0 - (1.0 - self.vies_dinamico_penalidade) * intensidade
        scores_ajustados[duzia_viesada] *= penalidade_efetiva
        score_removido = scores[duzia_viesada] - scores_ajustados[duzia_viesada]
        outras = [d for d in [1, 2, 3] if d != duzia_viesada]
        total_outras = sum(scores[d] for d in outras)
        if total_outras > 0:
            for d in outras: scores_ajustados[d] += score_removido * (scores[d] / total_outras)
        return scores_ajustados

    def calcular_score(self):
        ml_scores = self._prever_ml()
        ml_ativo = not all(v == 0.0 for v in ml_scores.values())
        if ml_ativo:
            modo = 'ml_disco' if self.ultimo_treino_ml <= 1 else 'ml'
            scores = self._aplicar_reforco_consenso(ml_scores)
            scores = self._aplicar_anti_vies(scores)
            scores = self._aplicar_vies_dinamico(scores)
            scores = self._aplicar_peso_adaptativo(scores)
            return scores, modo
        else:
            scores = self._prever_fallback_frequencia()
            scores = self._aplicar_anti_vies(scores)
            scores = self._aplicar_vies_dinamico(scores)
            scores = self._aplicar_peso_adaptativo(scores)
            return scores, 'fallback'

    def _aplicar_reforco_consenso(self, ml_scores):
        scores = ml_scores.copy()
        if self.consenso_info['tipo'] in ('duplo', 'triplo', 'simples'):
            duzia_consenso = self.consenso_info['duzia']
            conf_consenso = self.consenso_info['conf']
            melhor_ml = max(scores, key=scores.get)
            if melhor_ml == duzia_consenso:
                peso_extra = self.consenso_peso_extra / 100.0
                if self.consenso_info['tipo'] == 'triplo': peso_extra *= 1.5
                boost = scores[duzia_consenso] * peso_extra * conf_consenso
                scores[duzia_consenso] = min(100, scores[duzia_consenso] + boost)
            else:
                ml_conf = (max(scores.values()) - sorted(scores.values(), reverse=True)[1]) / 20
                if ml_conf < self.ml_ignorar_consenso_conf_min:
                    fator = 0.3 * conf_consenso
                    scores[duzia_consenso] += (100 - scores[duzia_consenso]) * fator
                    scores[melhor_ml] *= (1 - fator * 0.5)
        return scores

    def detectar_alerta_zero(self):
        if len(self.historico) < 2: self.alerta_zero_ativo = False; return False
        u = list(self.historico)[-10:]
        nums = self.numeros_completos[-8:] if len(self.numeros_completos) >= 8 else self.numeros_completos
        if len(nums) >= 2 and nums[-1] == 0: self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        if len(u) >= 3:
            u3 = u[-3:]
            if len(set(u3)) == 1 and u3[0] != 0: self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        if len(u) >= 5:
            u5 = u[-5:]
            trocas = sum(1 for i in range(1, len(u5)) if u5[i] != u5[i-1] and u5[i] != 0 and u5[i-1] != 0)
            if trocas >= 4: self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        config = self._get_config()
        limiar_gap = max(8, config.get('zero_termometro_max', 15) - 3)
        if self.rodadas_desde_zero >= limiar_gap: self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        duzias_rec = [d for d in list(self.historico)[-5:] if d != 0]
        if len(duzias_rec) >= 3 and duzias_rec[-1] == duzias_rec[-3] and duzias_rec[-1] != duzias_rec[-2]:
            self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        terminais_recentes = [n % 10 for n in nums if n != 0]
        if terminais_recentes.count(0) >= 2: self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        bordas = [n for n in nums if n in (1, 3, 12, 13, 24, 25, 36)]
        if len(bordas) >= 3: self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        if len(duzias_rec) >= 4 and len([d for d in duzias_rec[-4:] if d in (1, 3)]) == 4:
            self.alerta_zero_ativo = True; self.alertas_zero_disparados += 1; return True
        self.alerta_zero_ativo = False; return False

    def _get_outras_duzias(self, duzia):
        return [d for d in [1, 2, 3] if d != duzia]

    def prever(self):
        if self.pausa_ate and hora_brasilia() < self.pausa_ate:
            return {"entrar": False, "motivo": "⏸️ Pausa"}
        config = self._get_config()
        hora_atual = datetime.now().hour
        if 'horario_bloqueio_inicio' in config and 'horario_bloqueio_fim' in config:
            if config['horario_bloqueio_inicio'] <= hora_atual < config['horario_bloqueio_fim']:
                return {"entrar": False, "motivo": f"⏸️ Horário bloqueado"}
        if self.em_pausa_pos_raio:
            return {"entrar": False, "motivo": f"⏸️ Pausa pós-raio ({self.ultimo_raio_alto}x)"}
        if self._drift_ativo:
            return {"entrar": False, "motivo": f"⚠️ DRIFT — Aguardando recuperação. ({self._rodadas_sem_entrada}/{self.drift_rodadas_auto_reset} rod)"}

        scores, modo = self.calcular_score()
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        d1, s1 = ranking[0]
        d2, s2 = ranking[1] if len(ranking) > 1 else (self._get_outras_duzias(d1)[0], 0)
        d3, s3 = ranking[2] if len(ranking) > 2 else (self._get_outras_duzias(d1)[-1], 0)

        self.detectar_alerta_zero()

        # BUG #6 FIX: escala de confiança calibrada por modo
        modo_base = 'ml' if 'ml' in modo else 'fallback'
        divisor = 20 if modo_base == 'ml' else 15  # fallback usa escala menor → confiança maior
        confianca = min(3.5, max(0.5, (s1 - s2) / divisor))

        if self.alerta_zero_ativo and confianca >= 3.0: confianca = min(2.8, confianca)

        pode_entrar = False; motivo = ""; forcar_rotacao = False

        streak_info = self._streak_info_atual
        streak_len = streak_info.get('streak_atual_len', 0)
        streak_duzia = streak_info.get('streak_atual_duzia', 0)
        streak_cobertura = streak_info.get('cobertura_streak_duzia', 0)

        streak_sinal = ""
        if self.streak_config_ativo and streak_len >= self.streak_min_len and streak_duzia != 0:
            streak_sinal = f"🔥 STK D{streak_duzia}({streak_len}x)"

        if modo_base == 'ml':
            score_minimo = config.get('ml_score_minimo_entrada', 30)
            pode_entrar = s1 > score_minimo
            if pode_entrar:
                treino_info = "do Disco 💾" if self.ultimo_treino_ml <= 1 else f"R{self.ultimo_treino_ml}"
                partes = []
                for t, nome in [('tam2','P2'),('tam3','P3'),('tam4','P4')]:
                    if self.padrao_stats_ui.get(t): partes.append(f"{nome}:{self.padrao_stats_ui[t]['gatilho']}")
                info_consenso = ""
                if self.consenso_info['tipo'] in ('duplo', 'triplo', 'simples'):
                    icones = {'triplo': '🔒', 'duplo': '🔗', 'simples': '💡'}
                    info_consenso = f" | {icones[self.consenso_info['tipo']]} D{self.consenso_info['duzia']}"
                motivo = f"🟢 ML ({treino_info}) | Score: {s1:.1f}"
                if partes: motivo += f" | 🧩 {' | '.join(partes)}"
                if info_consenso: motivo += info_consenso
                if self.vies_dinamico_ativo and self._vies_dinamico_atual:
                    motivo += f" | 🔍 VD-D{self._vies_dinamico_atual}({self._vies_dinamico_intensidade*100:.0f}%)"
                if streak_sinal: motivo += f" | {streak_sinal}"
            else:
                motivo = f"Score ML baixo ({s1:.1f} < {score_minimo})"
        else:
            score_min_fb = config.get('ml_score_minimo_fallback', 38)
            min_rodadas_fb = config.get('ml_min_rodadas_fallback', 8)
            if len(self.historico_completo) >= min_rodadas_fb and s1 > score_min_fb:
                pode_entrar = True
                motivo = f"🟡 Fallback | Score: {s1:.1f}"
                if streak_sinal: motivo += f" | {streak_sinal}"
            else:
                motivo = f"Aguardando ML ({len(self.historico_completo)}/{max(30, min_rodadas_fb)} rod)"

        # LIMITADOR DE REPETIÇÕES
        max_rep = config.get('ml_max_repeticoes_mesma_duzia', 2)
        if pode_entrar and len(self.ultimas_previsoes) >= max_rep:
            ultimas_n = self.ultimas_previsoes[-max_rep:]
            if all(p == d1 for p in ultimas_n):
                if s2 > config.get('ml_score_minimo_pos_rotacao', 18):
                    d1, s1 = d2, s2; d2, s2 = d3, s3
                    forcar_rotacao = True
                    motivo = f"🔄 Rotação (>{max_rep}x D{d1}) | Score: {s1:.1f}"
                else:
                    pode_entrar = False
                    motivo = f"🚫 Bloqueio repetição (>{max_rep}x)"

        # FILTROS DE CONFIANÇA
        confianca_min = config.get('confianca_minima_entrada', 1.8)
        if pode_entrar and confianca < confianca_min and not forcar_rotacao:
            if self.consenso_info['tipo'] in ('triplo',) and confianca >= 1.2:
                motivo += " | 🔒 Exceção tripla"
            else:
                pode_entrar = False
                motivo = f"Confiança baixa ({confianca:.2f} < {confianca_min})"

        # BUG #7 FIX: modo_anti_erro verificado com erros_consecutivos
        if pode_entrar and self.erros_consecutivos >= 1 and confianca < (confianca_min + 0.4):
            pode_entrar = False
            motivo = f"🚫 Anti-Erro: conf {confianca:.2f} insuficiente (erros: {self.erros_consecutivos})"

        # TERMÔMETRO ZERO
        incluir_zero = self.alerta_zero_ativo
        if self.rodadas_desde_zero >= config['zero_termometro_max']:
            incluir_zero = True
            if pode_entrar: motivo += " | 🌡️ Zero"

        if confianca < 0.8: pode_entrar = False; motivo = f"Confiança crítica ({confianca:.2f})"

        # STREAK COMO ALIADO
        duzia_secundaria_final = d2
        streak_aplicado = False
        if pode_entrar and self.streak_config_ativo and streak_len >= self.streak_min_len and streak_duzia != 0:
            streak_aplicado = True
            if streak_duzia == d1:
                duzia_secundaria_final = streak_cobertura if streak_cobertura != 0 else d2
            elif streak_duzia == d2:
                duzia_secundaria_final = streak_duzia
            else:
                duzia_secundaria_final = streak_duzia if streak_duzia != 0 else d2

        # INFO DOS PADRÕES PARA UI
        info_padrao = {
            'tam2': self.padrao_stats_ui.get('tam2'), 'tam3': self.padrao_stats_ui.get('tam3'),
            'tam4': self.padrao_stats_ui.get('tam4'), 'consenso': self.consenso_info,
            'anti_vies': self.anti_vies_ativo, 'peso_adaptativo': self.peso_adaptativo_ativo,
            'vies_dinamico': self._vies_dinamico_atual, 'drift_ativo': self._drift_ativo,
            'streak': streak_info, 'streak_sinal': streak_sinal, 'streak_aplicado': streak_aplicado, 'resumo': []
        }
        for t, nome in [('tam2','P2'),('tam3','P3'),('tam4','P4')]:
            if info_padrao[t]: info_padrao['resumo'].append(f"{nome}:{info_padrao[t]['gatilho']}")
        if self.consenso_info['tipo'] in ('duplo','triplo','simples'):
            info_padrao['resumo'].append(f"{'🔒' if self.consenso_info['tipo']=='triplo' else '🔗'}D{self.consenso_info['duzia']}")
        if self.vies_dinamico_ativo and self._vies_dinamico_atual:
            info_padrao['resumo'].append(f"🔍VD-D{self._vies_dinamico_atual}")
        if streak_sinal: info_padrao['resumo'].append(streak_sinal)
        info_padrao['resumo'] = " | ".join(info_padrao['resumo']) if info_padrao['resumo'] else "-"

        return {
            "entrar": pode_entrar, "motivo": motivo, "score": scores,
            "confianca": round(confianca, 2), "duzia": d1, "duzia_secundaria": duzia_secundaria_final,
            "gatilho_ativo": "ML" if modo_base == 'ml' else "Fallback",
            "incluir_zero": incluir_zero, "modo_anti_erro": self.erros_consecutivos > 0,
            "numeros_completos": list(self.numeros_completos), "modo_previsao": modo,
            "rotacao_forcada": forcar_rotacao, "padrao_ativo": info_padrao,
            "streak_info": streak_sinal if streak_sinal else None,
        }


class _EnsembleManual:
    def __init__(self, rf, gbt):
        self.rf = rf; self.gbt = gbt; self.classes_ = rf.classes_
        try: self.n_features_in_ = rf.n_features_in_
        except: self.n_features_in_ = None

    def predict_proba(self, X):
        p_rf = self.rf.predict_proba(X); p_gbt = self.gbt.predict_proba(X)
        return (p_rf + p_gbt) / 2.0, self.classes_

    def predict(self, X):
        proba, classes = self.predict_proba(X)
        return classes[np.argmax(proba, axis=1)]


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
        self.acertos_duzia = 0; self.erros_duzia = 0
        self.acertos_numero = 0; self.erros_numero = 0
        self.acertos_zero = 0; self.erros_zero = 0
        self.acertos_primaria = 0; self.acertos_secundaria = 0
        self.ultimo_numero = None; self.sinais_grafico = []; self.numero_rodada = 0
        self.performance_por_mesa = defaultdict(lambda: {'acertos': 0, 'erros': 0})
        self.performance_por_horario = defaultdict(lambda: {'acertos': 0, 'erros': 0})
        self.rodadas_por_sessao = st.session_state.get('rodadas_por_sessao', 10)
        self.pausa_entre_sessoes = st.session_state.get('pausa_entre_sessoes', 5)
        self.rodadas_na_sessao = 0; self.sessao_ativa = False
        self.sessao_pausa_ate = None; self.total_sessoes = 0
        self.acertos_sessao = 0; self.erros_sessao = 0
        self.gerenciador_sessoes = GerenciadorSessoes(api_name)

    def iniciar_sessao(self):
        if self.sessao_pausa_ate and hora_brasilia() < self.sessao_pausa_ate: return False
        self.sessao_ativa = True; self.rodadas_na_sessao = 0
        self.acertos_sessao = 0; self.erros_sessao = 0
        self.total_sessoes += 1; self.sessao_pausa_ate = None
        salvar_sessao(); return True

    def _encerrar_sessao(self):
        self.sessao_ativa = False
        self.sessao_pausa_ate = hora_brasilia() + timedelta(minutes=self.pausa_entre_sessoes)
        taxa = (self.acertos_sessao / max(1, self.acertos_sessao + self.erros_sessao)) * 100
        if st.session_state.get('salvar_sessoes_auto', True):
            inicio = max(0, len(self.historico_entradas) - self.rodadas_na_sessao)
            self.gerenciador_sessoes.salvar_sessao_encerrada(
                self.total_sessoes,
                {'acertos': self.acertos_sessao, 'erros': self.erros_sessao,
                 'taxa_acerto': round(taxa, 1), 'total_rodadas': self.rodadas_na_sessao,
                 'rodadas_por_sessao': self.rodadas_por_sessao},
                self.historico_entradas[inicio:])
        self.entrada_ativa = None; salvar_sessao()

    def pode_processar(self):
        if not self.sessao_ativa:
            if self.sessao_pausa_ate and hora_brasilia() >= self.sessao_pausa_ate:
                self.sessao_pausa_ate = None; self.sessao_ativa = False; salvar_sessao()
            return False
        if self.rodadas_na_sessao >= self.rodadas_por_sessao:
            self._encerrar_sessao(); return False
        return True

    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data.get('number'); lucky_numbers = numero_data.get('luckyNumbers', [])
            lucky_multipliers = numero_data.get('luckyMultipliers', {}); table_id = numero_data.get('table_id', 'unknown')
            table_name = numero_data.get('table_name', 'Desconhecida')
        else:
            nr = numero_data; lucky_numbers = []; lucky_multipliers = {}
            table_id = 'unknown'; table_name = 'Desconhecida'

        if nr is None or not validar_numero(nr): return

        self.numero_rodada += 1
        self.duzia_ai.adicionar(nr)
        self.historico_numeros.append(nr)
        self.ultimo_numero = nr

        if not self.pode_processar(): salvar_sessao(); return

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

            if acerto_primaria or acerto_zero: self.acertos_primaria += 1; self.acertos_duzia += 1
            elif acerto_secundaria: self.acertos_secundaria += 1; self.acertos_duzia += 1
            elif nr != 0: self.erros_duzia += 1

            acertou_duzia = acerto_primaria or acerto_secundaria

            # BUG #8 FIX: incrementar rodadas APÓS verificar resultado
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
                'rodada': self.numero_rodada, 'hora': formatar_hora_brasilia(), 'numero': nr,
                'duzia_real': duzia_real if nr != 0 else 0,
                'duzia_prevista': duzia_prevista, 'duzia_sec_prevista': duzia_sec_prevista,
                'acerto_duzia': acertou_duzia, 'acerto_primaria': acerto_primaria,
                'acerto_secundaria': acerto_secundaria, 'acerto_numero': acerto_numero_exato,
                'acerto_zero': acerto_zero, 'eh_raio': eh_raio, 'multiplicador': multiplicador,
                'status': status_visual, 'confianca': self.entrada_ativa.get('confianca', 0),
                'gatilho': self.entrada_ativa.get('gatilho_ativo', 'ML'),
                'modo_anti_erro': self.entrada_ativa.get('modo_anti_erro', False),
                'incluir_zero': incluir_zero, 'table_id': table_id, 'table_name': table_name,
                'padrao_info': self.entrada_ativa.get('padrao_ativo'),
                'streak_info': self.entrada_ativa.get('streak_info'),
            })
            if len(self.historico_entradas) > 100: self.historico_entradas = self.historico_entradas[-100:]

            enviar_resultado_auto(nr, acertou_duzia, acerto_numero_exato, acerto_zero, eh_raio, multiplicador)
            self.entrada_ativa = None

            # BUG #8 FIX: verificar pode_processar DEPOIS de registrar resultado
            if not self.pode_processar(): salvar_sessao(); return

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
                    'gatilho_ativo': previsao.get('gatilho_ativo', 'ML'),
                    'modo_anti_erro': previsao.get('modo_anti_erro', False),
                    'incluir_zero': previsao.get('incluir_zero', False),
                    'padrao_ativo': previsao.get('padrao_ativo'),
                    'streak_info': previsao.get('streak_info'),
                }
                self.duzia_ai.registrar_previsao(previsao['duzia'], previsao['confianca'])
                self.sinais_grafico.append((len(self.historico_numeros) - 1, previsao['duzia']))
                enviar_previsao_auto({
                    'numeros_apostar': numeros_apostar,
                    'incluir_zero': previsao.get('incluir_zero', False),
                    'duzia': previsao['duzia'],
                    'duzia_secundaria': previsao.get('duzia_secundaria', previsao['duzia']),
                    'numeros_completos': list(self.historico_numeros),
                    'streak_info': previsao.get('streak_info'),
                })

    def zerar(self):
        self.acertos_duzia = self.erros_duzia = 0
        self.acertos_numero = self.erros_numero = 0
        self.acertos_zero = self.erros_zero = 0
        self.acertos_primaria = self.acertos_secundaria = 0
        self.historico_entradas = []; self.historico_numeros.clear()
        self.entrada_ativa = None; self.ultimo_numero = None
        self.sinais_grafico = []; self.numero_rodada = 0
        self.rodadas_na_sessao = 0; self.sessao_ativa = False
        self.sessao_pausa_ate = None; self.total_sessoes = 0
        self.acertos_sessao = self.erros_sessao = 0
        self.duzia_ai = DuziaAI(window=st.session_state.get('janela_duzia_ai', 30),
                                api_name=st.session_state.get('api_selecionada', 'XXXtreme Lightning'))
        salvar_sessao()


def salvar_resultado_em_arquivo(historico, caminho):
    try:
        with open(caminho, "w", encoding='utf-8') as f: json.dump(historico, f, indent=2)
    except Exception as e: logging.error(f"Erro: {e}")

def exportar_historico_csv(historico_entradas, caminho="export_roleta.csv"):
    try:
        with open(caminho, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Rod','Hora','Nº','Raio','Real','Prev','Cob','Conf','Gat','Z','🔄','Mesa','Duz','P1','P2s','Num','Zer','St','Padrões','Streak'])
            for e in historico_entradas:
                real = f"D{e.get('duzia_real',0)}" if e.get('duzia_real',0) != 0 else "0"
                ns = e.get('numero', 0)
                nd = f"⚡{ns} ({e.get('multiplicador',0)}x)" if e.get('eh_raio') else ("0" if ns == 0 else str(ns))
                writer.writerow([e.get('rodada'), e.get('hora'), nd,
                                  f"⚡{e.get('multiplicador',0)}x" if e.get('eh_raio') else '-',
                                  real, f"D{e.get('duzia_prevista','?')}",
                                  f"D{e.get('duzia_sec_prevista','?')}" if e.get('duzia_sec_prevista') and e.get('duzia_sec_prevista') != e.get('duzia_prevista') else '-',
                                  f"{e.get('confianca',0):.1f}", e.get('gatilho','ML'),
                                  '🟢' if e.get('incluir_zero') else '-', '🔄' if e.get('modo_anti_erro') else '-',
                                  e.get('table_name', '?')[:15] if e.get('table_name') else '?',
                                  '✅' if e.get('acerto_duzia') else '❌', '✅' if e.get('acerto_primaria') else '-',
                                  '✅' if e.get('acerto_secundaria') else '-', '✅' if e.get('acerto_numero') else '-',
                                  '✅' if e.get('acerto_zero') else '-', e.get('status','?'),
                                  str(e.get('padrao_info', {}).get('resumo', '-')) if e.get('padrao_info') else '-',
                                  str(e.get('streak_info', '-')) if e.get('streak_info') else '-'])
        return True
    except Exception as e:
        logging.error(f"Erro CSV: {e}"); return False


# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎰 DuziaAI V13.3 - 10 Bugs Corrigidos", layout="wide")
st.title("🎰 DuziaAI V13.3 — 10 Bugs Corrigidos ✅ | Sem Loops Silenciosos | Entradas Funcionando (BRT)")

config_global = carregar_config_global()

for key, default in [
    ("api_selecionada", config_global.get('api_selecionada', 'XXXtreme Lightning')),
    ("ultima_api", config_global.get('api_selecionada', 'XXXtreme Lightning')),
    ("telegram_token", config_global.get('telegram_token', '')),
    ("telegram_chat_id", config_global.get('telegram_chat_id', '')),
    ("telegram_token_alt", config_global.get('telegram_token_alt', '')),
    ("telegram_chat_id_alt", config_global.get('telegram_chat_id_alt', '')),
    ("rodadas_por_sessao", config_global.get('rodadas_por_sessao', 10)),
    ("pausa_entre_sessoes", config_global.get('pausa_entre_sessoes', 5)),
    ("salvar_sessoes_auto", config_global.get('salvar_sessoes_auto', True)),
    ("modo_automatico", config_global.get('modo_automatico', True)),
    ("modo_agressivo", config_global.get('modo_agressivo', False)),
    ("janela_duzia_ai", config_global.get('janela_duzia_ai', 30)),
    ("historico", []),
]:
    if key not in st.session_state: st.session_state[key] = default

def _carregar_sistema(api_name):
    sis = st.session_state.sistema
    dados = carregar_dados_persistidos(api_name)
    if dados:
        for n in dados.get('historico_numeros', []):
            sis.duzia_ai.adicionar(n); sis.historico_numeros.append(n)
        sis.numero_rodada = dados.get('numero_rodada', len(dados.get('historico_numeros', [])))
        for campo in ['acertos_duzia','erros_duzia','acertos_numero','erros_numero','acertos_zero','erros_zero','acertos_primaria','acertos_secundaria']:
            setattr(sis, campo, dados.get(campo, 0))
        sis.entrada_ativa = dados.get('entrada_ativa', None)
        sis.historico_entradas = dados.get('historico_entradas', [])
        sis.rodadas_na_sessao = dados.get('rodadas_na_sessao', 0)
        sis.sessao_ativa = dados.get('sessao_ativa', False)
        sis.total_sessoes = dados.get('total_sessoes', 0)
        sis.acertos_sessao = dados.get('acertos_sessao', 0)
        sis.erros_sessao = dados.get('erros_sessao', 0)
        if dados.get('sessao_pausa_ate'): sis.sessao_pausa_ate = datetime.fromisoformat(dados['sessao_pausa_ate'])
        if dados.get('ultimo_treino_ml'): sis.duzia_ai.ultimo_treino_ml = dados['ultimo_treino_ml']
        for campo in ['performance_por_mesa', 'performance_por_horario']:
            if campo in dados:
                for k, v in dados[campo].items(): getattr(sis, campo)[k] = v; getattr(sis.duzia_ai, campo)[k] = v
        sis.duzia_ai._carregar_padroes_hibridos()
        paths = get_session_paths(api_name)
        if os.path.exists(paths['historico']):
            with open(paths['historico'], 'r') as f: st.session_state.historico = json.load(f)

if st.session_state.api_selecionada != st.session_state.ultima_api:
    st.session_state.ultima_api = st.session_state.api_selecionada
    st.session_state.sistema = SistemaBot()
    _carregar_sistema(st.session_state.api_selecionada)
    st.rerun()

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()
    _carregar_sistema(st.session_state.api_selecionada)

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.markdown("## ⚙️ V13.3 — 10 Bugs Corrigidos ✅")
    sis = st.session_state.sistema

    st.markdown("### 📊 Status da Sessão")
    if sis.sessao_ativa:
        st.success(f"🟢 Sessão #{sis.total_sessoes} ATIVA")
        st.progress(sis.rodadas_na_sessao / max(1, sis.rodadas_por_sessao))
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
            if sis.iniciar_sessao(): st.success(f"✅ Sessão #{sis.total_sessoes} iniciada!"); st.rerun()

    st.markdown("---")
    if st.button("🆕 RESET TOTAL", use_container_width=True):
        if nova_sessao(): st.success("✅ Reset completo!"); st.rerun()

    st.markdown("---")
    st.markdown("### ⏱️ Configurações da Sessão")
    rodadas = st.number_input("Rodadas por sessão:", min_value=5, max_value=30, value=st.session_state.rodadas_por_sessao, step=5)
    pausa = st.number_input("Pausa entre sessões (min):", min_value=1, max_value=30, value=st.session_state.pausa_entre_sessoes, step=1)
    if rodadas != st.session_state.rodadas_por_sessao:
        st.session_state.rodadas_por_sessao = rodadas; sis.rodadas_por_sessao = rodadas; salvar_sessao()
    if pausa != st.session_state.pausa_entre_sessoes:
        st.session_state.pausa_entre_sessoes = pausa; sis.pausa_entre_sessoes = pausa; salvar_sessao()

    st.markdown("---")
    st.session_state.salvar_sessoes_auto = st.checkbox("💾 Salvar sessões automaticamente", value=st.session_state.salvar_sessoes_auto)
    with st.expander("📥 BAIXAR SESSÕES", expanded=False):
        api_name_dl = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        ger = GerenciadorSessoes(api_name_dl)
        sessoes = ger.listar_sessoes()
        if sessoes:
            st.caption(f"📂 {len(sessoes)} sessões disponíveis")
            sessao_opcoes = [f"Sessão #{s.get('numero_sessao', '?')} - {s.get('data', '?')} {s.get('hora_encerramento', '?')}" for s in sessoes[:20]]
            if sessao_opcoes:
                sel = st.selectbox("Selecionar sessão:", sessao_opcoes, key="select_sessao")
                if sel:
                    idx = sessao_opcoes.index(sel)
                    if idx < len(sessoes):
                        s = sessoes[idx]; col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(ger.get_download_link(json.dumps(s, indent=2, ensure_ascii=False), f"sessao_{s.get('numero_sessao','?')}.json", 'json'), unsafe_allow_html=True)
                        with col2:
                            st.markdown(ger.get_download_link(ger.gerar_csv_sessao(s), f"sessao_{s.get('numero_sessao','?')}.csv", 'csv'), unsafe_allow_html=True)
                        stats = s.get('estatisticas', {})
                        st.caption(f"✅ {stats.get('acertos', 0)} | ❌ {stats.get('erros', 0)} | 📊 {stats.get('taxa_acerto', 0)}%")
            if st.button("📦 Baixar Todas (JSON)", use_container_width=True):
                todas = ger.listar_sessoes()
                if todas:
                    conteudo = json.dumps({'total_sessoes': len(todas), 'sessoes': todas}, indent=2, ensure_ascii=False)
                    st.markdown(ger.get_download_link(conteudo, f"todas_sessoes_{api_name_dl.lower().replace(' ','_')}.json", 'json'), unsafe_allow_html=True)
        else:
            st.info("Nenhuma sessão salva ainda.")

    st.markdown("---")
    st.markdown("### 🎰 Selecione a Roleta")
    api_opcoes = list(API_URLS.keys())
    api_index = api_opcoes.index(st.session_state.api_selecionada) if st.session_state.api_selecionada in api_opcoes else 0
    st.session_state.api_selecionada = st.radio("Roleta:", api_opcoes, index=api_index)
    api_name = st.session_state.api_selecionada
    config_ativa = ROLETA_CONFIGS.get(api_name, SETUP_XXXTREME)

    if hasattr(sis.duzia_ai, 'modelo_ml') and sis.duzia_ai.modelo_ml is not None:
        st.success(f"🧠 ML ATIVO | R{sis.duzia_ai.ultimo_treino_ml}" if sis.duzia_ai.ultimo_treino_ml > 1 else "🧠 ML CARREGADO 💾")
    else:
        n = len(sis.historico_numeros)
        st.info(f"🧠 Aguardando... ({n}/30 rod)")

    if sis.duzia_ai._drift_ativo:
        reset_em = sis.duzia_ai.drift_rodadas_auto_reset - sis.duzia_ai._rodadas_sem_entrada
        st.error(f"⚠️ DRIFT! Reset em {max(0,reset_em)} rodadas sem entrada.")
    if sis.duzia_ai._vies_dinamico_atual:
        st.warning(f"🔍 Viés: D{sis.duzia_ai._vies_dinamico_atual} ({sis.duzia_ai._vies_dinamico_intensidade*100:.0f}%)")

    stk = sis.duzia_ai._streak_info_atual
    if stk and stk.get('streak_atual_len', 0) >= 2:
        stk_len = stk['streak_atual_len']; stk_duzia = stk['streak_atual_duzia']
        stk_cont = stk.get('prob_continua_streak2' if stk_len == 2 else 'prob_continua_streak3', 0.5)
        if stk.get('streak_saturado'): st.error(f"⚠️ STK SATURADO D{stk_duzia}×{stk_len} | Quebra: {stk.get('streak_taxa_quebra_real', 0)*100:.0f}%")
        elif stk.get('streak_quebra_iminente'): st.warning(f"⚡ Quebra iminente D{stk_duzia}!")
        else: st.info(f"🔥 STK D{stk_duzia}×{stk_len} | P(cont)={stk_cont*100:.0f}%")

    padroes_validos, qualidade = sis.duzia_ai._verificar_qualidade_padroes()
    if padroes_validos < 1:
        st.warning(f"⚠️ Padrões: P2:{'✅' if qualidade['p2'] else '❌'} P3:{'✅' if qualidade['p3'] else '❌'} P4:{'✅' if qualidade['p4'] else '❌'}")

    consenso = sis.duzia_ai.consenso_info
    if consenso['tipo'] == 'triplo': st.success(f"🔒 CONSENSO TRIPLO: D{consenso['duzia']}")
    elif consenso['tipo'] == 'duplo': st.info(f"🔗 CONSENSO DUPLO: D{consenso['duzia']}")
    elif consenso['tipo'] == 'simples': st.info(f"💡 Sinal: D{consenso['duzia']}")

    st.markdown("---")
    st.caption(f"🔧 **{api_name} V13.3**")
    st.caption(f"• Conf mín: {config_ativa.get('confianca_minima_entrada', 1.8)}")
    st.caption(f"• Score mín ML: {config_ativa.get('ml_score_minimo_entrada', 30)}")
    st.caption(f"• Score mín Fallback: {config_ativa.get('ml_score_minimo_fallback', 38)}")
    st.caption(f"• Janela ML: {config_ativa.get('ml_janela_treino', 80)} | Fallback min: {config_ativa.get('ml_min_rodadas_fallback', 8)} rod")
    st.caption(f"• P2/P3/P4: {config_ativa.get('padrao_peso_tam2',20)}/{config_ativa.get('padrao_peso_tam3',50)}/{config_ativa.get('padrao_peso_tam4',30)}%")
    st.caption(f"• Drift reset auto: {config_ativa.get('drift_rodadas_auto_reset', 20)} rod")
    st.caption(f"• Max rep dúzia: {config_ativa.get('ml_max_repeticoes_mesma_duzia', 2)}")

    st.markdown("---")
    st.session_state.janela_duzia_ai = st.slider("📏 Janela de Análise", 10, 50, st.session_state.janela_duzia_ai, 5)
    st.session_state.modo_agressivo = st.checkbox("🔥 Modo Agressivo (2 Dúzias)", value=st.session_state.modo_agressivo)
    st.session_state.modo_automatico = st.checkbox("🤖 Modo Automático", value=st.session_state.modo_automatico)

    st.markdown("---")
    with st.expander("🔔 Telegram", expanded=False):
        st.session_state.telegram_token = st.text_input("Token Principal", value=st.session_state.telegram_token, type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID Principal", value=st.session_state.telegram_chat_id)
        st.session_state.telegram_token_alt = st.text_input("Token Alternativo", value=st.session_state.telegram_token_alt, type="password")
        st.session_state.telegram_chat_id_alt = st.text_input("Chat ID Alternativo", value=st.session_state.telegram_chat_id_alt)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Salvar", use_container_width=True):
            salvar_resultado_em_arquivo(st.session_state.historico, get_session_paths(st.session_state.api_selecionada)['historico'])
            salvar_sessao(); st.success("✅ Salvo!")
    with c2:
        if st.button("📥 CSV", use_container_width=True):
            if exportar_historico_csv(st.session_state.sistema.historico_entradas): st.success("✅ CSV!")

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
            st.session_state.historico.append({"number": nr, "timestamp": timestamp_brasilia(),
                                                "luckyNumbers": [], "luckyMultipliers": {},
                                                "table_id": "manual", "table_name": "Entrada Manual"})
            st.session_state.sistema.processar_novo_numero(nr)
            salvar_resultado_em_arquivo(st.session_state.historico, get_session_paths(st.session_state.api_selecionada)['historico'])
            salvar_sessao(); st.rerun()
        else: st.error("Número entre 0 e 36")
with c3:
    if st.button("🔄 Auto", use_container_width=True):
        st.session_state.modo_automatico = not st.session_state.modo_automatico; st.rerun()

if st.session_state.modo_automatico:
    st_autorefresh(interval=3000, key="auto_refresh")
    r = fetch_latest_result()
    if r and r.get("number") is not None:
        if not st.session_state.historico or r.get("timestamp") != st.session_state.historico[-1].get("timestamp"):
            st.session_state.historico.append(r)
            st.session_state.sistema.processar_novo_numero(r)
            salvar_resultado_em_arquivo(st.session_state.historico, get_session_paths(st.session_state.api_selecionada)['historico'])
            salvar_sessao(); st.rerun()

st.markdown("---")
sis = st.session_state.sistema
api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')

# Banners de status
if sis.duzia_ai._drift_ativo:
    reset_em = sis.duzia_ai.drift_rodadas_auto_reset - sis.duzia_ai._rodadas_sem_entrada
    st.error(f"⚠️ **DRIFT DETECTADO** — Entradas suspensas. Reset automático em {max(0,reset_em)} rodadas.")
if sis.duzia_ai._vies_dinamico_atual:
    st.warning(f"🔍 **Viés dinâmico:** D{sis.duzia_ai._vies_dinamico_atual} — {sis.duzia_ai._vies_dinamico_intensidade*100:.0f}% acima do esperado.")

stk = sis.duzia_ai._streak_info_atual
if stk and stk.get('streak_atual_len', 0) >= 2:
    stk_len = stk['streak_atual_len']; stk_duzia = stk['streak_atual_duzia']
    if stk.get('streak_saturado'): st.error(f"⚠️ **Streak D{stk_duzia}×{stk_len} SATURADO**")
    elif stk.get('streak_quebra_iminente'): st.error(f"⚡ **Streak D{stk_duzia}×{stk_len}** — Quebra iminente!")
    else: st.info(f"🔥 **Streak: D{stk_duzia}×{stk_len}**")

padroes_validos, qualidade = sis.duzia_ai._verificar_qualidade_padroes()

st.subheader(f"📊 ESTATÍSTICAS — {api_name}")
c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
total_duzias = int(sis.acertos_duzia + sis.erros_duzia)
tx_duzias = (sis.acertos_duzia / total_duzias * 100) if total_duzias > 0 else 0
total_numeros = sis.acertos_numero + sis.erros_numero
tx_numeros = (sis.acertos_numero / total_numeros * 100) if total_numeros > 0 else 0
c1.metric("🎯 Nº Exato", sis.acertos_numero, f"{tx_numeros:.0f}%")
c2.metric("✅ Acertos", int(sis.acertos_duzia), f"{tx_duzias:.0f}%")
c3.metric("🎯 Primária", sis.acertos_primaria)
c4.metric("🟡 Secundária", sis.acertos_secundaria)
c5.metric("❌ Erros", sis.erros_duzia)
c6.metric("🟢 Zeros", f"{sis.acertos_zero}/{sis.acertos_zero + sis.erros_zero}")
c7.metric("📦 Total", total_duzias)

if sis.total_sessoes > 0:
    st.markdown("---")
    st.subheader(f"📈 Sessão #{sis.total_sessoes}")
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("🔄 Rodadas", f"{sis.rodadas_na_sessao}/{sis.rodadas_por_sessao}")
    sc2.metric("✅ Acertos", sis.acertos_sessao)
    sc3.metric("❌ Erros", sis.erros_sessao)
    taxa_sessao = (sis.acertos_sessao / max(1, sis.acertos_sessao + sis.erros_sessao)) * 100
    sc4.metric("📊 Taxa", f"{taxa_sessao:.0f}%")
    if sis.sessao_ativa: st.progress(sis.rodadas_na_sessao / max(1, sis.rodadas_por_sessao))

st.markdown("---")
cg, ce = st.columns([3, 2])

with cg:
    st.subheader("📈 Scores do ML")
    if len(sis.historico_numeros) >= 3:
        score, modo_atual = sis.duzia_ai.calcular_score()
        max_score = max(score.values())
        fig = plt.Figure(data=[plt.Bar(
            x=['D1 (1-12)', 'D2 (13-24)', 'D3 (25-36)'],
            y=[score[1], score[2], score[3]],
            marker_color=['#FF6B6B' if score[d]==max_score else '#4ECDC4' for d in [1,2,3]],
            text=[f'{score[d]:.1f}' for d in [1,2,3]], textposition='auto'
        )])
        titulo = f"🎯 ML V13.3 ({api_name}) | {modo_atual.upper()}"
        if sis.duzia_ai.alerta_zero_ativo: titulo += " | 🟢 ZERO"
        if sis.duzia_ai._drift_ativo: titulo += " | ⚠️ DRIFT"
        stk = sis.duzia_ai._streak_info_atual
        if stk and stk.get('streak_atual_len', 0) >= 2:
            titulo += f" | 🔥STK D{stk['streak_atual_duzia']}×{stk['streak_atual_len']}"
        fig.update_layout(title=titulo, height=300, showlegend=False, yaxis_title="Score")
        st.plotly_chart(fig, use_container_width=True)

        if len(sis.historico_numeros) >= 8:
            ult = list(sis.historico_numeros)[-20:]
            dz_hist = [get_duzia(n) for n in ult]
            fig2 = plt.Figure()
            fig2.add_trace(plt.Scatter(x=list(range(len(dz_hist))), y=dz_hist,
                                        mode='lines+markers', line=dict(color='#FFD700', width=2), marker=dict(size=10)))
            if sis.sinais_grafico:
                sx, sy = [], []; off = len(dz_hist) - 20
                for idx, dz in sis.sinais_grafico:
                    pos = idx - off
                    if 0 <= pos < 20: sx.append(pos); sy.append(dz)
                if sx:
                    fig2.add_trace(plt.Scatter(x=sx, y=sy, mode='markers', name='Sinal',
                                                marker=dict(symbol='star', size=15, color='red')))
            fig2.update_layout(title="📉 Histórico", yaxis=dict(tickvals=[0,1,2,3], ticktext=['0','D1','D2','D3'], range=[-0.5,3.5]), height=300)
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info(f"Aguardando dados... ({len(sis.historico_numeros)}/3 números)")

with ce:
    st.subheader("🎰 Entrada Atual")
    if sis.duzia_ai._drift_ativo:
        reset_em = sis.duzia_ai.drift_rodadas_auto_reset - sis.duzia_ai._rodadas_sem_entrada
        st.error(f"⚠️ DRIFT — Reset em {max(0,reset_em)} rodadas")
    if sis.duzia_ai.alerta_zero_ativo: st.warning("⚠️ ALERTA ZERO! 🟢")
    if sis.duzia_ai.em_pausa_pos_raio: st.warning(f"⏸️ Pausa pós-raio ({sis.duzia_ai.ultimo_raio_alto}x)")
    if sis.duzia_ai.anti_vies_ativo:
        duzia_av = sis.duzia_ai.anti_vies_duzia or sis.duzia_ai._vies_dinamico_atual
        if duzia_av: st.info(f"🛡️ Anti-viés D{duzia_av} ({sis.duzia_ai.anti_vies_penalidade*100:.0f}%)")
    if sis.duzia_ai._vies_dinamico_atual:
        st.info(f"🔍 Viés dinâmico: D{sis.duzia_ai._vies_dinamico_atual} ({sis.duzia_ai._vies_dinamico_intensidade*100:.0f}%)")
    if sis.duzia_ai.peso_adaptativo_ativo: st.info("🔥 Peso adaptativo ativo")

    stk = sis.duzia_ai._streak_info_atual
    if stk and stk.get('streak_atual_len', 0) >= 2:
        stk_len = stk['streak_atual_len']; stk_duzia = stk['streak_atual_duzia']; stk_cob = stk.get('cobertura_streak_duzia', '?')
        if stk.get('streak_saturado'): st.error(f"⚠️ STK SATURADO D{stk_duzia}×{stk_len}")
        elif stk.get('streak_quebra_iminente'): st.error(f"⚡ STK D{stk_duzia}×{stk_len} → QUEBRA | Cob: D{stk_cob}")
        else: st.success(f"🔥 STK D{stk_duzia}×{stk_len} | Cob: D{stk_cob}")

    consenso = sis.duzia_ai.consenso_info
    if consenso['tipo'] == 'triplo': st.success(f"🔒 CONSENSO TRIPLO: D{consenso['duzia']}")
    elif consenso['tipo'] == 'duplo': st.info(f"🔗 CONSENSO DUPLO: D{consenso['duzia']}")
    elif consenso['tipo'] == 'simples': st.info(f"💡 Sinal único: D{consenso['duzia']}")

    for t, nome in [('tam2','P2'),('tam3','P3'),('tam4','P4')]:
        if sis.duzia_ai.padrao_stats_ui.get(t):
            s = sis.duzia_ai.padrao_stats_ui[t]; melhor = max(s['scores'], key=s['scores'].get)
            qual_ok = qualidade.get(t, False)
            st.caption(f"{'✅' if qual_ok else '⚠️'} 🧩 {nome}: {s['gatilho']} → D{melhor} ({s['total']:.0f}x)")

    if not sis.sessao_ativa:
        if sis.sessao_pausa_ate and hora_brasilia() < sis.sessao_pausa_ate:
            tempo_restante = (sis.sessao_pausa_ate - hora_brasilia()).seconds
            st.info(f"⏸️ Próxima sessão em: {tempo_restante//60:02d}:{tempo_restante%60:02d}")
        else:
            st.info("🔴 Clique 'INICIAR SESSÃO' para começar")

    if sis.entrada_ativa and sis.sessao_ativa:
        e = sis.entrada_ativa
        conf = e.get('confianca', 0); dz_princ = e.get('duzia_prevista', 0)
        dz_sec = e.get('duzia_sec_prevista'); gatilho = e.get('gatilho_ativo', 'ML')
        padrao_info = e.get('padrao_ativo', {}); streak_ent = e.get('streak_info', None)
        duzia_secundaria = dz_sec if dz_sec and dz_sec != dz_princ else None
        melhores_principal = _selecionar_melhores_numeros(dz_princ, list(sis.historico_numeros), 6)
        melhores_secundaria = _selecionar_melhores_numeros(duzia_secundaria, list(sis.historico_numeros), 6) if duzia_secundaria else None
        cor = "#FF6347" if e.get('modo_anti_erro') else "#00CED1"
        icone_modo = "🟡 Fallback" if gatilho == 'Fallback' else "🤖 ML V13.3 ✅"
        padrao_html = f'<p style="text-align:center; color:#FFD700; font-size:0.8em;">🧩 {padrao_info["resumo"]}</p>' if padrao_info.get('resumo') else ""
        streak_html = f'<p style="text-align:center; color:#FF8C00; font-size:0.85em;">{streak_ent}</p>' if streak_ent else ""
        st.markdown(f"""
        <div style="background-color:{cor}15; border:2px solid {cor}; border-radius:15px; padding:15px;">
            <h2 style="color:{cor}; text-align:center;">🎯 Dúzia {dz_princ}</h2>
            <p style="text-align:center;">Confiança: {conf:.2f}</p>
            <p style="text-align:center;">{icone_modo}</p>
            {f'<p style="text-align:center; color:#FFA500;">🛡️ Cob: D{dz_sec}</p>' if duzia_secundaria else ''}
            {padrao_html}{streak_html}
        </div>""", unsafe_allow_html=True)
        st.write(f"**🎲 D{dz_princ}:** {', '.join(map(str, melhores_principal))}")
        if melhores_secundaria: st.write(f"**🛡️ D{duzia_secundaria}:** {', '.join(map(str, melhores_secundaria))}")
        st.progress(min(1.0, max(0.0, conf / 5.0)))
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
        real = f"D{e.get('duzia_real',0)}" if e.get('duzia_real',0) != 0 else "0"
        ns = e.get('numero', 0)
        nd = f"⚡{ns} ({e.get('multiplicador',0)}x)" if e.get('eh_raio') else ("0" if ns == 0 else str(ns))
        dados.append({
            "Rod": e.get('rodada'), "Hora": e.get('hora'), "🎲": nd, "Real": real,
            "Prev": f"D{e.get('duzia_prevista','?')}",
            "Cob": f"D{e.get('duzia_sec_prevista','?')}" if e.get('duzia_sec_prevista') and e.get('duzia_sec_prevista') != e.get('duzia_prevista') else "-",
            "Conf": f"{e.get('confianca',0):.1f}", "Gat": e.get('gatilho','ML'),
            "Z": '🟢' if e.get('incluir_zero') else '-', "🔄": '🔄' if e.get('modo_anti_erro') else '-',
            "🧩": str(e.get('padrao_info', {}).get('resumo', '-')) if e.get('padrao_info') else '-',
            "STK": str(e.get('streak_info', '-')) if e.get('streak_info') else '-',
            "Duz": '✅' if e.get('acerto_duzia') else '❌',
            "P1": '✅' if e.get('acerto_primaria') else '-',
            "P2s": '🟡' if e.get('acerto_secundaria') else '-',
            "Nº": '🎯' if e.get('acerto_numero') else '-',
            "Zer": '🟢' if e.get('acerto_zero') else '-',
        })
    st.dataframe(dados, use_container_width=True, height=300)
    if st.button("📥 Exportar CSV", use_container_width=True):
        if exportar_historico_csv(sis.historico_entradas): st.success("✅ CSV exportado!")
else:
    st.info("Nenhuma entrada ainda.")

st.markdown("---")
col_t1, col_t2 = st.columns(2)
with col_t1:
    st.success("🔔 Telegram Principal OK") if st.session_state.telegram_token and st.session_state.telegram_chat_id else st.warning("🔔 Telegram Principal NÃO")
with col_t2:
    st.success("📢 Telegram Alt OK") if st.session_state.telegram_token_alt and st.session_state.telegram_chat_id_alt else st.warning("📢 Telegram Alt NÃO")

config_ativa = ROLETA_CONFIGS.get(api_name, SETUP_XXXTREME)
st.caption(f"🤖 DuziaAI V13.3 | {api_name} | ✅ 10 Bugs Corrigidos | P2:{config_ativa['padrao_peso_tam2']}% P3:{config_ativa['padrao_peso_tam3']}% P4:{config_ativa['padrao_peso_tam4']}% | {formatar_hora_brasilia()}")
modelo_path = get_modelo_ml_path(api_name)
st.caption(f"💾 Modelo: {modelo_path} ({os.path.getsize(modelo_path)/1024:.1f} KB)" if os.path.exists(modelo_path) else "⚠️ Modelo não salvo ainda")

salvar_sessao()
