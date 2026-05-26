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
    from sklearn.ensemble import GradientBoostingClassifier
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
# 🆕 SETUPS INDEPENDENTES POR ROLETA
# =============================

SETUP_BASE = {
    'pagamento_numero': 20,
    'pagamento_zero': 20,
    'pagamento_duzia': 3,
    'confianca_minima_entrada': 2.0,
    'embalo_peso': 5,
    'embalo_reforco': 2,
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
    'ml_janela_treino': 100,
    'ml_atualizar_a_cada': 5,
    'score_ml_peso': 30,
    'pausa_erros_minutos': 1.5,
    'pausa_hibernacao_minutos': 1.5,
}

SETUP_XXXTREME = {
    **SETUP_BASE,
    'pagamento_numero': 20, 'pagamento_zero': 20, 'pagamento_duzia': 3,
    'confianca_minima_entrada': 2.0, 'embalo_peso': 5, 'embalo_reforco': 2,
    'bloquear_alerta_zero_conf_alta': True, 'bloquear_anti_erro_zero_conf_baixa': True,
    'filtro_conf_baixa': 3.5, 'fadiga_duzia': 4,
    'ritmo_alternado_peso': 10, 'ritmo_alternado_forca': 10,
    'max_repeticoes_embalo': 3, 'confianca_maxima_segura': 3.5,
    'rodadas_verificacao_conf_alta': 5, 'pausa_pos_raio': 1, 'raio_alto_minimo': 100,
    'zero_termometro_max': 15, 'anti_erro_skip_discordancia': True,
    'ritmo_v_peso': 10, 'ritmo_v_forca': 10, 'ritmo_v_confirmacoes': 2,
    'usar_embalo': True, 'embalo_consecutivas_min': 2, 'embalo_janela': 4,
    'usar_ritmo_alternado': True, 'usar_ritmo_v': True,
    'usar_ritmo_ping_pong': True, 'usar_ritmo_binario': True,
    'usar_quebra_pos_zero': False,
    'usar_exaustao_dominancia': True,
    'usar_mudanca_velocidade': False,
    'score_frequencia_peso': 20, 'score_streak_peso': 4,
    'score_markov_peso': 18, 'score_ml_peso': 40, 'score_anti_erro_peso': 18,
    'score_convergencia_peso': 25, 'score_gap_peso': 15,
    'ml_janela_treino': 100, 'ml_atualizar_a_cada': 5,
    'pausa_erros_minutos': 2.5,
    'pausa_hibernacao_minutos': 1.5,
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
    'score_frequencia_peso': 20, 'score_streak_peso': 4,
    'score_markov_peso': 18, 'score_ml_peso': 40, 'score_anti_erro_peso': 18,
    'score_convergencia_peso': 25, 'score_gap_peso': 15,
    'horario_bloqueio_inicio': 5, 'horario_bloqueio_fim': 7,
    'ml_janela_treino': 50, 'ml_atualizar_a_cada': 5,
    'pausa_erros_minutos': 1.5,
    'pausa_hibernacao_minutos': 1.5,
    'ml_janela_fixa': 50,
    'ml_janela_dinamica': False,
}

SETUP_MEGA = {
    **SETUP_BASE,
    'pagamento_numero': 24, 'pagamento_zero': 24, 'pagamento_duzia': 2,
    'confianca_minima_entrada': 1.5, 'embalo_peso': 5, 'embalo_reforco': 2,
    'bloquear_alerta_zero_conf_alta': True, 'bloquear_anti_erro_zero_conf_baixa': True,
    'filtro_conf_baixa': 2.5, 'fadiga_duzia': 3,
    'ritmo_alternado_peso': 8, 'ritmo_alternado_forca': 8,
    'max_repeticoes_embalo': 3, 'confianca_maxima_segura': 3.0,
    'rodadas_verificacao_conf_alta': 5, 'pausa_pos_raio': 2, 'raio_alto_minimo': 100,
    'zero_termometro_max': 12, 'anti_erro_skip_discordancia': True,
    'ritmo_v_peso': 4, 'ritmo_v_forca': 4, 'ritmo_v_confirmacoes': 2,
    'usar_ritmo_v': False,
    'usar_embalo': True, 'embalo_consecutivas_min': 2, 'embalo_janela': 4,
    'usar_ritmo_alternado': True,
    'usar_ritmo_ping_pong': False, 'usar_ritmo_binario': False,
    'usar_quebra_pos_zero': False, 'usar_exaustao_dominancia': False,
    'usar_mudanca_velocidade': False,
    'score_frequencia_peso': 20, 'score_streak_peso': 4,
    'score_markov_peso': 18, 'score_ml_peso': 45, 'score_anti_erro_peso': 25,
    'score_convergencia_peso': 25, 'score_gap_peso': 15,
    'ml_janela_treino': 120, 'ml_atualizar_a_cada': 5,
    'entropia_threshold': 0.85,
    'pausa_erros_minutos': 1.5,
    'pausa_hibernacao_minutos': 1.5,
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
                         'Confiança', 'Gatilho', 'Zero', 'Anti-Erro', 
                         'Acerto Dúzia', 'Acerto Número', 'Acerto Zero', 'Status'])
        for e in dados_sessao.get('entradas', []):
            real = f"D{e.get('duzia_real',0)}" if e.get('duzia_real',0)!=0 else "0"
            prev = f"D{e.get('duzia_prevista','?')}"
            zero = 'Sim' if e.get('incluir_zero') else 'Não'
            anti = 'Sim' if e.get('modo_anti_erro') else 'Não'
            duz = 'Sim' if e.get('acerto_duzia') else 'Não'
            num = 'Sim' if e.get('acerto_numero') else 'Não'
            zer = 'Sim' if e.get('acerto_zero') else 'Não'
            numero = e.get('numero', 0)
            raio = f"{e.get('multiplicador',0)}x" if e.get('eh_raio') else '-'
            writer.writerow([
                e.get('rodada'), e.get('hora'), numero, raio, real, prev,
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
        
        prefixo = "⚠️🎯 " if incluir_zero else "🎯 "
        if 1 <= duzia_principal <= 3:
            msg = f"{prefixo}Entrada: D{duzia_principal}"
            if incluir_zero:
                msg += " + 🟢 ZERO"
        else:
            msg = f"{prefixo}Entrada: {numeros}"
        
        melhores_principal = _selecionar_melhores_numeros(duzia_principal, previsao.get('numeros_completos', []), 6)
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
# 🆕 MÓDULO V13 - CLASSES AUXILIARES
# =============================

class MarkovMultiOrdem:
    def __init__(self):
        self.tabelas = {2: defaultdict(Counter), 3: defaultdict(Counter), 4: defaultdict(Counter)}

    def adicionar(self, sequencia_completa):
        for ordem, tabela in self.tabelas.items():
            for i in range(ordem, len(sequencia_completa)):
                padrao = tuple(sequencia_completa[i - ordem:i])
                resultado = sequencia_completa[i]
                if resultado in (1, 2, 3):
                    tabela[padrao][resultado] += 1

    def prever(self, historico_recente):
        scores = {1: 0.0, 2: 0.0, 3: 0.0}
        pesos_ordem = {2: 0.25, 3: 0.40, 4: 0.35}
        for ordem, peso in pesos_ordem.items():
            if len(historico_recente) < ordem:
                continue
            padrao = tuple(historico_recente[-ordem:])
            tabela = self.tabelas[ordem]
            if padrao not in tabela:
                continue
            total = sum(tabela[padrao].values())
            if total < 3:
                continue
            for duzia, contagem in tabela[padrao].items():
                prob = contagem / total
                if prob > 0.33:
                    scores[duzia] += prob * peso * 100
        return scores

class FiltroBollinger:
    def __init__(self, janela=20, desvios=1.0):
        self.janela = janela
        self.desvios = desvios
        self._historico_acertos = deque(maxlen=50)

    def registrar(self, acertou: bool):
        self._historico_acertos.append(1 if acertou else 0)

    def threshold_atual(self, confianca_base=2.0):
        if len(self._historico_acertos) < 10:
            return confianca_base
        taxa = np.mean(list(self._historico_acertos)[-self.janela:])
        desvio = np.std(list(self._historico_acertos)[-self.janela:])
        ajuste = (0.60 - taxa) * 1.5
        threshold = confianca_base + ajuste + desvio * self.desvios
        return round(max(1.2, min(3.0, threshold)), 2)

    def taxa_recente(self):
        if not self._historico_acertos:
            return 0.0
        return np.mean(list(self._historico_acertos)[-20:])

class DetectorConvergencia:
    def votar(self, sinais: dict) -> dict:
        votos = Counter()
        for fonte, duzia in sinais.items():
            if duzia in (1, 2, 3):
                votos[duzia] += 1
        if not votos:
            return {'duzia': None, 'votos': 0, 'convergiu': False}
        melhor_duzia, melhor_votos = votos.most_common(1)[0]
        return {
            'duzia': melhor_duzia,
            'votos': melhor_votos,
            'convergiu': melhor_votos >= 2,
            'distribuicao': dict(votos)
        }

class CooldownInteligente:
    def __init__(self):
        self._em_cooldown = False
        self._padrao_erro = None
        self._rodadas_cooldown = 0
        self._min_rodadas = 1

    def ativar(self, padrao_atual):
        self._em_cooldown = True
        self._padrao_erro = padrao_atual
        self._rodadas_cooldown = 0

    def verificar(self, padrao_atual) -> bool:
        if not self._em_cooldown:
            return True
        self._rodadas_cooldown += 1
        if self._rodadas_cooldown < self._min_rodadas:
            return False
        if padrao_atual != self._padrao_erro:
            self._em_cooldown = False
            return True
        return False

    @property
    def ativo(self):
        return self._em_cooldown

def detectar_streak_perigoso(historico_duzias, limite=6) -> bool:
    if len(historico_duzias) < limite:
        return False
    recentes = [d for d in historico_duzias[-limite-1:] if d != 0]
    if len(recentes) < limite:
        return False
    return len(set(recentes[-limite:])) == 1

def extrair_features_v13(historico_duzias, historico_numeros):
    if len(historico_duzias) < 10:
        return None
    d = [x for x in historico_duzias[-20:] if x != 0]
    n = [x for x in historico_numeros[-20:] if x != 0]
    if len(d) < 6:
        return None
    f1, f2, f3 = d[-1], d[-2], d[-3]
    trocas = sum(1 for i in range(1, min(8, len(d))) if d[-i] != d[-i-1])
    alternado = int(len(d) >= 4 and d[-1] == d[-3] and d[-2] == d[-4] and d[-1] != d[-2])
    gap1 = next((i for i, x in enumerate(reversed(d)) if x == 1), len(d))
    gap2 = next((i for i, x in enumerate(reversed(d)) if x == 2), len(d))
    gap3 = next((i for i, x in enumerate(reversed(d)) if x == 3), len(d))
    streak = 1
    for i in range(1, len(d)):
        if d[-i] == d[-1]:
            streak += 1
        else:
            break
    ultimas_12 = d[-12:] if len(d) >= 12 else d
    prop1 = ultimas_12.count(1) / len(ultimas_12)
    prop2 = ultimas_12.count(2) / len(ultimas_12)
    prop3 = ultimas_12.count(3) / len(ultimas_12)
    ultimas_8 = d[-8:] if len(d) >= 8 else d
    cnt = Counter(ultimas_8)
    probs = [c / len(ultimas_8) for c in cnt.values()]
    entropia_local = -sum(p * np.log2(p) for p in probs if p > 0) / 1.585
    dom_recente = int(len(d) >= 4 and len(set(d[-4:])) == 1)
    zeros_recentes = historico_duzias[-5:].count(0) if len(historico_duzias) >= 5 else 0
    hora_atual = datetime.now().hour
    return [f1, f2, f3, trocas, alternado, gap1, gap2, gap3,
            streak, prop1, prop2, prop3, entropia_local,
            dom_recente, zeros_recentes, hora_atual]

# =============================
# 🧠 DUZIA AI V13 - COMPLETO (UMA DÚZIA)
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
        self.modelo_ml = None
        self.scaler = StandardScaler() if ML_DISPONIVEL else None
        self.ultimo_treino_ml = 0
        self.mesa_atual = None
        self.performance_por_mesa = defaultdict(lambda: {'acertos': 0, 'erros': 0})
        self.performance_por_horario = defaultdict(lambda: {'acertos': 0, 'erros': 0})
        self.entropia_mesa = 0.0
        self.janela_ml_atual = 100
        
        self.markov = MarkovMultiOrdem()
        self.filtro_bollinger = FiltroBollinger(janela=20, desvios=0.8)
        self.convergencia = DetectorConvergencia()
        self.cooldown = CooldownInteligente()
        self._X_buffer = []
        self._y_buffer = []
    
    def _get_config(self):
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        return ROLETA_CONFIGS.get(api_name, SETUP_XXXTREME).copy()
    
    def atualizar_janela_ml(self):
        config = self._get_config()
        if config.get('ml_janela_fixa') is not None and not config.get('ml_janela_dinamica', True):
            self.janela_ml_atual = config['ml_janela_fixa']
            return self.janela_ml_atual
        ultimos = list(self.historico)[-50:]
        if len(ultimos) < 30:
            self.janela_ml_atual = 100
            return self.janela_ml_atual
        counts = Counter(ultimos)
        variancia = np.var(list(counts.values()))
        if variancia < 2.0:
            self.janela_ml_atual = 50
        elif variancia < 5.0:
            self.janela_ml_atual = 100
        else:
            self.janela_ml_atual = 200
        return self.janela_ml_atual
    
    def _adicionar_amostra_ml(self, duzia_atual):
        features = extrair_features_v13(self.historico_completo[:-1], self.numeros_completos[:-1])
        if features and duzia_atual in (1, 2, 3):
            self._X_buffer.append(features)
            self._y_buffer.append(duzia_atual)
            if len(self._X_buffer) > 300:
                self._X_buffer = self._X_buffer[-300:]
                self._y_buffer = self._y_buffer[-300:]
    
    def _treinar_ml_online(self):
        if not ML_DISPONIVEL:
            return False
        config = self._get_config()
        atualizar_a_cada = config.get('ml_atualizar_a_cada', 5)
        rodada_atual = len(self.historico_completo)
        if rodada_atual - self.ultimo_treino_ml < atualizar_a_cada:
            return False
        if len(self._X_buffer) < 30:
            return False
        try:
            X = np.array(self._X_buffer)
            y = np.array(self._y_buffer)
            X_scaled = self.scaler.fit_transform(X)
            self.modelo_ml = GradientBoostingClassifier(
                n_estimators=60, max_depth=3, learning_rate=0.1,
                subsample=0.8, random_state=42
            )
            self.modelo_ml.fit(X_scaled, y)
            self.ultimo_treino_ml = rodada_atual
            logging.info(f"🧠 ML V13 Treinado! Amostras: {len(X)} | Rodada: {rodada_atual}")
            return True
        except Exception as e:
            logging.error(f"❌ Erro treino ML V13: {e}")
            return False
    
    def _prever_ml(self):
        if not ML_DISPONIVEL or self.modelo_ml is None:
            return {1: 0.0, 2: 0.0, 3: 0.0}
        try:
            features = extrair_features_v13(self.historico_completo, self.numeros_completos)
            if not features:
                return {1: 0.0, 2: 0.0, 3: 0.0}
            config = self._get_config()
            X_scaled = self.scaler.transform([features])
            probs = self.modelo_ml.predict_proba(X_scaled)[0]
            ml_scores = {1: 0.0, 2: 0.0, 3: 0.0}
            for classe, prob in zip(self.modelo_ml.classes_, probs):
                if classe in ml_scores:
                    ml_scores[classe] = float(prob) * config['score_ml_peso']
            return ml_scores
        except Exception as e:
            return {1: 0.0, 2: 0.0, 3: 0.0}
    
    def calcular_entropia(self):
        if len(self.historico) < 20:
            return 0.5
        ultimos = list(self.historico)[-20:]
        counts = Counter(ultimos)
        probs = [c / len(ultimos) for c in counts.values()]
        entropia = -sum(p * np.log2(p) for p in probs if p > 0)
        self.entropia_mesa = min(1.0, entropia / 1.585)
        return self.entropia_mesa
    
    def adicionar(self, numero):
        d = get_duzia(numero)
        self.historico.append(d); self.historico_completo.append(d); self.numeros_completos.append(numero)
        if numero == 0: self.rodadas_desde_zero = 0
        else: self.rodadas_desde_zero += 1
        self._atualizar_ritmo_alternado(d); self._atualizar_ritmo_v(d)
        if d != 0:
            if d == self.duzia_embalo_atual: self.contagem_embalo_atual += 1
            else: self.duzia_embalo_atual = d; self.contagem_embalo_atual = 1
        if d != 0:
            self.duzias_que_sairam.append(d)
            if len(self.duzias_que_sairam) > 10: self.duzias_que_sairam = self.duzias_que_sairam[-10:]
        if numero == 0 and self.alerta_zero_ativo: self.zeros_previstos += 1
        if len(self.historico_completo) >= 4:
            padrao = tuple(self.historico_completo[-4:-1])
            self.transicoes[padrao][d] += 1
        self.markov.adicionar(self.historico_completo)
        if len(self.historico_completo) > 300: self.historico_completo = self.historico_completo[-300:]
        if len(self.numeros_completos) > 300: self.numeros_completos = self.numeros_completos[-300:]
        if self.em_pausa_pos_raio:
            self.rodadas_pos_raio += 1
            if self.rodadas_pos_raio >= self._get_config()['pausa_pos_raio']: self.em_pausa_pos_raio = False
        self._adicionar_amostra_ml(d)
        self._treinar_ml_online()
    
    def _atualizar_ritmo_alternado(self, nova_duzia):
        if nova_duzia == 0: return
        u = list(self.historico)
        if len(u) < 3: return
        recentes = [d for d in u[-8:] if d != 0]
        if len(recentes) < 4: self.ritmo_alternado_par = None; self.ritmo_alternado_contagem = 0; return
        for inicio in range(len(recentes) - 3):
            seq = recentes[inicio:inicio+4]
            if seq[0] != seq[1] and seq[0] == seq[2] and seq[1] == seq[3]:
                par = tuple(sorted([seq[0], seq[1]]))
                if self.ritmo_alternado_par == par: self.ritmo_alternado_contagem += 1
                else: self.ritmo_alternado_par = par; self.ritmo_alternado_contagem = 1
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
            if self.ritmo_v_padrao == padrao_v: self.ritmo_v_contagem += 1
            else: self.ritmo_v_padrao = padrao_v; self.ritmo_v_contagem = 1
            if self.ritmo_v_contagem >= 1: self.ultimo_ritmo_v = padrao_v
        else:
            if self.ritmo_v_padrao is not None: self.ritmo_v_padrao = None; self.ritmo_v_contagem = 0
    
    def registrar_previsao(self, duzia, confianca):
        self.ultimas_previsoes.append(duzia); self.ultima_previsao_duzia = duzia; self.ultima_confianca = confianca
        if len(self.ultimas_previsoes) > 10: self.ultimas_previsoes = self.ultimas_previsoes[-10:]
    
    def registrar_resultado(self, duzia_real, acertou_duzia, acertou_numero, acertou_zero, mesa_id=None, eh_raio=False, multiplicador=0):
        self.ultimos_resultados.append({'duzia': duzia_real, 'acertou_duzia': acertou_duzia, 'acertou_numero': acertou_numero, 'acertou_zero': acertou_zero})
        self.ultimo_resultado_duzia = acertou_duzia; self.ultimo_resultado_numero = acertou_numero
        
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
        
        self.filtro_bollinger.registrar(acertou_duzia or acertou_zero)
        
        if len(self.ultimos_resultados) > 20: self.ultimos_resultados = self.ultimos_resultados[-20:]
        
        if acertou_duzia and duzia_real != 0:
            if duzia_real == self.ultima_duzia_acertada: self.acertos_consecutivos_mesma_duzia += 1
            else: self.acertos_consecutivos_mesma_duzia = 1; self.ultima_duzia_acertada = duzia_real
        else: 
            self.acertos_consecutivos_mesma_duzia = 0; self.ultima_duzia_acertada = None
            
        if acertou_duzia and not acertou_numero and not acertou_zero: self.consecutivos_amarelos += 1
        else: self.consecutivos_amarelos = 0
        
        if not acertou_duzia and not acertou_zero:
            self.erros_consecutivos += 1
            if duzia_real != 0: self.erros_por_duzia[duzia_real] += 1
            self.modo_anti_erro = True
            
            padrao_erro = tuple(self.historico_completo[-3:]) if len(self.historico_completo) >= 3 else None
            self.cooldown.ativar(padrao_erro)
            
            if self.erros_consecutivos >= 2: 
                minutos_pausa = config.get('pausa_erros_minutos', 2.5)
                self.pausa_ate = hora_brasilia() + timedelta(minutes=minutos_pausa)
                self.modo_anti_erro = False
                logging.info(f"⏸️ TRAVA ATIVADA: 2 Erros seguidos. Pausando por {minutos_pausa} minutos.")
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
    
    def _calcular_gaps(self):
        gaps = {1: 99, 2: 99, 3: 99}
        for i, d in enumerate(reversed(self.historico_completo)):
            if d in gaps and gaps[d] == 99:
                gaps[d] = i
            if all(v != 99 for v in gaps.values()):
                break
        return gaps
    
    def _duzia_com_maior_gap(self):
        gaps = self._calcular_gaps()
        return max(gaps, key=gaps.get)
    
    def _prever_markov(self):
        if len(self.historico_completo) < 3: return None
        padrao = tuple(self.historico_completo[-3:])
        if padrao in self.transicoes and self.transicoes[padrao]: return self.transicoes[padrao].most_common(1)[0]
        return None
    
    def _get_outras_duzias(self, duzia): return [d for d in [1, 2, 3] if d != duzia]
    
    def _get_duzia_ausente(self):
        freq = self.frequencia()
        u = list(self.historico)[-6:]
        freq_recente = Counter([d for d in u if d != 0])
        for dz in [1, 2, 3]:
            if freq_recente.get(dz, 0) <= 1: return dz
        return min(freq, key=freq.get)
    
    def detectar_alerta_zero(self):
        if len(self.historico) < 2: self.alerta_zero_ativo = False; return False
        u = list(self.historico)[-10:]
        nums = self.numeros_completos[-5:] if len(self.numeros_completos) >= 5 else self.numeros_completos
        if len(nums) >= 2 and nums[-1] == 0: self.alerta_zero_ativo = True; return True
        if len(nums) >= 3 and 0 in nums[-3:-1]: self.alerta_zero_ativo = True; return True
        if len(u) >= 3:
            ultimas_3 = u[-3:]
            if len(set(ultimas_3)) == 1 and ultimas_3[0] != 0: self.alerta_zero_ativo = True; return True
        if len(u) >= 3:
            duzias_presentes = set(d for d in u[-3:] if d != 0)
            if len(duzias_presentes) == 3: self.alerta_zero_ativo = True; return True
        self.alerta_zero_ativo = False; return False
    
    def detectar_embalo(self):
        config = self._get_config()
        if not config.get('usar_embalo', True): return None
        u = list(self.historico)
        if len(u) < 3: return None
        janela = config.get('embalo_janela', 6)
        recentes = [d for d in u[-janela:] if d != 0]
        if len(recentes) < 2: return None
        ultima = recentes[-1]; consecutivas = 0
        for d in reversed(recentes):
            if d == ultima: consecutivas += 1
            else: break
        consecutivas_min = config.get('embalo_consecutivas_min', 3)
        max_rep = config.get('max_repeticoes_embalo', 4)
        if consecutivas >= max_rep: return None
        if detectar_streak_perigoso(self.historico_completo, limite=4): return None
        if consecutivas >= consecutivas_min and ultima != 0:
            return {'tipo': 'EMBALO', 'duzia': ultima, 'forca': config.get('embalo_peso', 5)}
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
                return {'tipo': 'RITMO_ALTERNADO', 'duzia': ultimas_8[0], 'forca': config['ritmo_alternado_forca'], 'par': (ultimas_8[0], ultimas_8[1])}
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
            return {'tipo': 'RITMO_V', 'duzia': ultimas_3[0], 'forca': config['ritmo_v_forca'], 'padrao': (ultimas_3[0], ultimas_3[1])}
        return None
    
    def detectar_gatilhos(self):
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
        return None
    
    def _avaliar_convergencia(self, score):
        markov_scores = self.markov.prever(self.historico_completo)
        s_markov = max(markov_scores, key=markov_scores.get) if any(v > 0 for v in markov_scores.values()) else None
        ml_scores = self._prever_ml()
        s_ml = max(ml_scores, key=ml_scores.get) if any(v > 0 for v in ml_scores.values()) else None
        gatilho = self.detectar_gatilhos()
        s_ritmo = gatilho['duzia'] if gatilho else None
        s_gap = self._duzia_com_maior_gap() if len(self.historico_completo) >= 10 else None
        s_score = max(score, key=score.get) if score else None
        return self.convergencia.votar({
            'markov': s_markov, 'ml': s_ml, 'ritmo': s_ritmo,
            'gap': s_gap, 'score': s_score
        })
    
    def calcular_score(self):
        config = self._get_config()
        score = {1: 0.0, 2: 0.0, 3: 0.0}
        freq = self.frequencia(); total = sum(freq.values())
        if total > 0:
            for d in score: score[d] += (freq.get(d, 0) / total) * config['score_frequencia_peso']
        streak_count, streak_d = self.streak()
        if streak_d and streak_d != 0: score[streak_d] += streak_count * config['score_streak_peso']
        
        markov_scores = self.markov.prever(self.historico_completo)
        for d in score: score[d] += markov_scores.get(d, 0) * config['score_markov_peso'] / 100
        
        ml_scores = self._prever_ml()
        for d in score: score[d] += ml_scores.get(d, 0.0)
        
        gaps = self._calcular_gaps()
        for d, gap in gaps.items():
            if gap >= 6: score[d] += min(gap, 15) * (config['score_gap_peso'] / 15)
        
        gatilho = self.detectar_gatilhos()
        if gatilho and gatilho['duzia'] != 0:
            score[gatilho['duzia']] += gatilho['forca'] * 2
            if gatilho['tipo'] in ('RITMO_V', 'RITMO_ALTERNADO'):
                score[gatilho['duzia']] += config.get('ritmo_v_peso', 9)
                padrao_chave = gatilho.get('padrao') or gatilho.get('par')
                if padrao_chave:
                    for d in [1, 2, 3]:
                        if d not in padrao_chave: score[d] *= 0.3
        
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
                return {"entrar": False, "motivo": f"⏸️ Horário bloqueado"}
        
        if self.em_pausa_pos_raio:
            return {"entrar": False, "motivo": f"⏸️ Pausa pós-raio ({self.ultimo_raio_alto}x)"}
        
        entropia = self.calcular_entropia()
        api_name = st.session_state.get('api_selecionada', '')
        
        if 'Mega' in api_name:
            threshold_entropia = config.get('entropia_threshold', 0.95)
        else:
            threshold_entropia = 1.00
        
        if entropia > threshold_entropia:
            return {"entrar": False, "motivo": f"🌪️ Mesa Caótica (Entropia: {entropia:.2f})"}
        
        score, gatilho = self.calcular_score()
        
        # V13: Convergência
        conv = self._avaliar_convergencia(score)
        if conv['convergiu']:
            d1 = conv['duzia']
        else:
            ranking = sorted(score.items(), key=lambda x: x[1], reverse=True)
            d1 = ranking[0][0]
        
        ranking = sorted(score.items(), key=lambda x: x[1], reverse=True)
        s1 = ranking[0][1]
        
        self.detectar_alerta_zero()
        confianca = min(3.5, max(1.0, s1 / max(1, ranking[1][1]) * 1.5))
        if conv['convergiu']: confianca = min(3.5, confianca * 1.1)
        
        u_list = list(self.historico)
        if 0 in u_list[-3:]: confianca *= 0.5
        if self.alerta_zero_ativo and confianca >= 3.4: confianca = min(3.3, confianca)
        
        # V13: Threshold dinâmico
        threshold_minimo = self.filtro_bollinger.threshold_atual(config.get('confianca_minima_entrada', 2.0))
        
        # V13: Anti-streak
        if detectar_streak_perigoso(self.historico_completo, limite=4):
            streak_count, streak_d = self.streak()
            if d1 == streak_d:
                outras = [d for d in [1, 2, 3] if d != streak_d]
                gaps = self._calcular_gaps()
                d1 = max(outras, key=lambda d: gaps.get(d, 0))
        
        # V13: Cooldown
        padrao_atual = tuple(self.historico_completo[-3:]) if len(self.historico_completo) >= 3 else None
        if self.cooldown.ativo and not self.cooldown.verificar(padrao_atual):
            return {"entrar": False, "motivo": "🔴 Cooldown: padrão do erro ainda ativo"}
        
        pode_entrar = (s1 > 35 or gatilho is not None) and confianca >= threshold_minimo
        
        if confianca < 2.0 and not conv['convergiu']:
            pode_entrar = False
        
        if gatilho and gatilho['tipo'] in ('RITMO_V', 'RITMO_ALTERNADO'): 
            pode_entrar = True; confianca = min(3.5, confianca * 1.15)
        
        motivo = ""
        if self.modo_anti_erro and confianca < 2.8:
            pode_entrar = False
            motivo = "🚫 Anti-Erro: Score estatístico baixo"
        else:
            if not motivo: motivo = "" if pode_entrar else f"Score baixo ({s1:.1f})"
        
        incluir_zero = self.alerta_zero_ativo
        if self.rodadas_desde_zero >= config['zero_termometro_max']:
            incluir_zero = True
        
        previsao = {
            "entrar": pode_entrar, "motivo": motivo, "score": score,
            "confianca": round(confianca, 2), "duzia": d1,
            "gatilho_ativo": gatilho['tipo'] if gatilho else None,
            "incluir_zero": incluir_zero,
            "modo_anti_erro": self.modo_anti_erro,
            "numeros_completos": list(self.numeros_completos),
            "convergencia_votos": conv['votos'],
            "threshold_usado": threshold_minimo,
            "taxa_recente": round(self.filtro_bollinger.taxa_recente() * 100, 1),
        }
        
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
                return previsao
        if self.modo_anti_erro and self.ultimas_previsoes:
            dz_errada = self.ultimas_previsoes[-1]
            if previsao['duzia'] == dz_errada:
                outras = self._get_outras_duzias(dz_errada)
                freq_outras = {d: u.count(d) for d in outras}
                previsao['duzia'] = max(freq_outras, key=freq_outras.get)
        if len(u) >= 2 and u[-1] == u[-2] and u[-1] != 0:
            if previsao['duzia'] != u[-1]: previsao['duzia'] = u[-1]
        return previsao

# =============================
# SISTEMA PRINCIPAL (UMA DÚZIA)
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
        self.acertos_sessao = 0; self.erros_sessao = 0
        self.gerenciador_sessoes = GerenciadorSessoes(st.session_state.get('api_selecionada', 'XXXtreme Lightning'))
    
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
            entradas_sessao = []
            inicio = len(self.historico_entradas) - self.rodadas_na_sessao
            if inicio < 0: inicio = 0
            entradas_sessao = self.historico_entradas[inicio:]
            dados_sessao = {'acertos': self.acertos_sessao, 'erros': self.erros_sessao, 'taxa_acerto': round(taxa, 1), 'total_rodadas': self.rodadas_na_sessao, 'rodadas_por_sessao': self.rodadas_por_sessao}
            self.gerenciador_sessoes.salvar_sessao_encerrada(self.total_sessoes, dados_sessao, entradas_sessao)
        self.entrada_ativa = None; salvar_sessao()
    
    def pode_processar(self):
        if not self.sessao_ativa:
            if self.sessao_pausa_ate and hora_brasilia() >= self.sessao_pausa_ate:
                self.sessao_pausa_ate = None; self.sessao_ativa = False; salvar_sessao()
            return False
        if self.rodadas_na_sessao >= self.rodadas_por_sessao: self._encerrar_sessao(); return False
        return True
    
    def processar_novo_numero(self, numero_data):
        if isinstance(numero_data, dict):
            nr = numero_data.get('number'); lucky_numbers = numero_data.get('luckyNumbers', [])
            lucky_multipliers = numero_data.get('luckyMultipliers', {})
            table_id = numero_data.get('table_id', 'unknown'); table_name = numero_data.get('table_name', 'Desconhecida')
        else: nr = numero_data; lucky_numbers = []; lucky_multipliers = {}; table_id = 'unknown'; table_name = 'Desconhecida'
        if nr is None or not validar_numero(nr): return
        self.numero_rodada += 1; self.duzia_ai.adicionar(nr); self.historico_numeros.append(nr); self.ultimo_numero = nr
        if not self.pode_processar(): salvar_sessao(); return
        eh_raio = nr in lucky_numbers; multiplicador = lucky_multipliers.get(nr, 0) if eh_raio else 0
        if self.entrada_ativa:
            duzia_real = get_duzia(nr)
            duzia_prevista = self.entrada_ativa.get('duzia_prevista')
            numeros_apostados = self.entrada_ativa.get('numeros_apostar', [])
            incluir_zero = self.entrada_ativa.get('incluir_zero', False)
            acerto_primaria = (duzia_real == duzia_prevista) if duzia_prevista and nr != 0 else False
            acerto_numero_exato = nr in numeros_apostados if nr != 0 else False
            acerto_zero = (nr == 0 and incluir_zero)
            if acerto_zero: acerto_primaria = True
            if acerto_numero_exato: self.acertos_numero += 1
            elif nr != 0: self.erros_numero += 1
            if acerto_zero: self.acertos_zero += 1
            elif nr == 0: self.erros_zero += 1
            if acerto_primaria: self.acertos_duzia += 1
            elif nr != 0: self.erros_duzia += 1
            acertou_duzia = acerto_primaria
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
            else: status_visual = '❌'
            self.historico_entradas.append({'rodada': self.numero_rodada, 'hora': formatar_hora_brasilia(), 'numero': nr, 'duzia_real': duzia_real if nr != 0 else 0, 'duzia_prevista': duzia_prevista, 'acerto_duzia': acerto_primaria, 'acerto_numero': acerto_numero_exato, 'acerto_zero': acerto_zero, 'eh_raio': eh_raio, 'multiplicador': multiplicador, 'status': status_visual, 'confianca': self.entrada_ativa.get('confianca', 0), 'gatilho': self.entrada_ativa.get('gatilho_ativo', None), 'modo_anti_erro': self.entrada_ativa.get('modo_anti_erro', False), 'incluir_zero': incluir_zero, 'table_id': table_id, 'table_name': table_name})
            if len(self.historico_entradas) > 50: self.historico_entradas = self.historico_entradas[-50:]
            enviar_resultado_auto(nr, acertou_duzia, acerto_numero_exato, acerto_zero, eh_raio, multiplicador)
            self.entrada_ativa = None
            if not self.pode_processar(): salvar_sessao(); return
        if self.sessao_ativa and self.rodadas_na_sessao < self.rodadas_por_sessao:
            previsao = self.duzia_ai.prever()
            if previsao['entrar']:
                duzia_map = {1: list(range(1,13)), 2: list(range(13,25)), 3: list(range(25,37))}
                numeros_principais = duzia_map.get(previsao['duzia'], [])
                numeros_apostar = numeros_principais
                if previsao.get('incluir_zero', False) and 0 not in numeros_apostar: numeros_apostar = [0] + numeros_apostar
                self.entrada_ativa = {'numeros_apostar': numeros_apostar, 'duzia_prevista': previsao['duzia'], 'confianca': previsao.get('confianca', 0), 'gatilho_ativo': previsao.get('gatilho_ativo'), 'modo_anti_erro': previsao.get('modo_anti_erro', False), 'incluir_zero': previsao.get('incluir_zero', False)}
                self.duzia_ai.registrar_previsao(previsao['duzia'], previsao['confianca'])
                idx_atual = len(self.historico_numeros) - 1
                self.sinais_grafico.append((idx_atual, previsao['duzia']))
                enviar_previsao_auto({'numeros_apostar': numeros_apostar, 'incluir_zero': previsao.get('incluir_zero', False), 'duzia': previsao['duzia'], 'numeros_completos': list(self.historico_numeros)})
    
    def zerar(self):
        self.acertos_duzia = 0; self.erros_duzia = 0; self.acertos_numero = 0; self.erros_numero = 0
        self.acertos_zero = 0; self.erros_zero = 0; self.historico_entradas = []; self.historico_numeros.clear()
        self.entrada_ativa = None; self.ultimo_numero = None; self.sinais_grafico = []; self.numero_rodada = 0
        self.rodadas_na_sessao = 0; self.sessao_ativa = False; self.sessao_pausa_ate = None
        self.total_sessoes = 0; self.acertos_sessao = 0; self.erros_sessao = 0
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
            writer.writerow(['Rod','Hora','Nº','Raio','Real','Prev','Conf','Gat','Z','🔄','Mesa','Duz','Num','Zer','St'])
            for e in historico_entradas:
                real = f"D{e.get('duzia_real',0)}" if e.get('duzia_real',0)!=0 else "0"
                prev = f"D{e.get('duzia_prevista','?')}"
                zero = '🟢' if e.get('incluir_zero') else '-'
                anti = '🔄' if e.get('modo_anti_erro') else '-'
                duz = '✅' if e.get('acerto_duzia') else '❌'
                num = '✅' if e.get('acerto_numero') else '-'
                zer = '✅' if e.get('acerto_zero') else '-'
                raio = f"⚡{e.get('multiplicador',0)}x" if e.get('eh_raio') else '-'
                mesa = e.get('table_name', '?')[:15] if e.get('table_name') else '?'
                writer.writerow([e.get('rodada'), e.get('hora'), e.get('numero'), raio, real, prev, f"{e.get('confianca',0):.1f}", e.get('gatilho','-') if e.get('gatilho') else '-', zero, anti, mesa, duz, num, zer, e.get('status','?')])
        return True
    except Exception as e: logging.error(f"Erro CSV: {e}"); return False

# =============================
# APLICAÇÃO STREAMLIT
# =============================
st.set_page_config(page_title="🎰 DuziaAI V13 - UMA DÚZIA", layout="wide")
st.title("🎰 DuziaAI V13 - FOCO EM UMA DÚZIA (BRT)")

config_global = carregar_config_global()

if "api_selecionada" not in st.session_state:
    st.session_state.api_selecionada = config_global.get('api_selecionada', 'XXXtreme Lightning')
if "ultima_api" not in st.session_state: st.session_state.ultima_api = st.session_state.api_selecionada
if "telegram_token" not in st.session_state: st.session_state.telegram_token = config_global.get('telegram_token', '')
if "telegram_chat_id" not in st.session_state: st.session_state.telegram_chat_id = config_global.get('telegram_chat_id', '')
if "telegram_token_alt" not in st.session_state: st.session_state.telegram_token_alt = config_global.get('telegram_token_alt', '')
if "telegram_chat_id_alt" not in st.session_state: st.session_state.telegram_chat_id_alt = config_global.get('telegram_chat_id_alt', '')
if "rodadas_por_sessao" not in st.session_state: st.session_state.rodadas_por_sessao = config_global.get('rodadas_por_sessao', 10)
if "pausa_entre_sessoes" not in st.session_state: st.session_state.pausa_entre_sessoes = config_global.get('pausa_entre_sessoes', 5)
if "salvar_sessoes_auto" not in st.session_state: st.session_state.salvar_sessoes_auto = config_global.get('salvar_sessoes_auto', True)

if st.session_state.api_selecionada != st.session_state.ultima_api:
    st.session_state.ultima_api = st.session_state.api_selecionada
    st.session_state.sistema = SistemaBot()
    dados = carregar_dados_persistidos(st.session_state.api_selecionada)
    if dados:
        sis = st.session_state.sistema
        for n in dados.get('historico_numeros', []): sis.duzia_ai.adicionar(n); sis.historico_numeros.append(n)
        sis.numero_rodada = dados.get('numero_rodada', len(dados.get('historico_numeros', [])))
        sis.acertos_duzia = dados.get('acertos_duzia', 0); sis.erros_duzia = dados.get('erros_duzia', 0)
        sis.acertos_numero = dados.get('acertos_numero', 0); sis.erros_numero = dados.get('erros_numero', 0)
        sis.acertos_zero = dados.get('acertos_zero', 0); sis.erros_zero = dados.get('erros_zero', 0)
        sis.entrada_ativa = dados.get('entrada_ativa', None); sis.historico_entradas = dados.get('historico_entradas', [])
        sis.rodadas_na_sessao = dados.get('rodadas_na_sessao', 0); sis.sessao_ativa = dados.get('sessao_ativa', False)
        sis.total_sessoes = dados.get('total_sessoes', 0); sis.acertos_sessao = dados.get('acertos_sessao', 0)
        sis.erros_sessao = dados.get('erros_sessao', 0)
        if dados.get('sessao_pausa_ate'): sis.sessao_pausa_ate = datetime.fromisoformat(dados['sessao_pausa_ate'])
        if 'performance_por_mesa' in dados:
            for k, v in dados['performance_por_mesa'].items(): sis.performance_por_mesa[k] = v; sis.duzia_ai.performance_por_mesa[k] = v
        if 'performance_por_horario' in dados:
            for k, v in dados['performance_por_horario'].items(): sis.performance_por_horario[k] = v; sis.duzia_ai.performance_por_horario[k] = v
        paths = get_session_paths(st.session_state.api_selecionada)
        if os.path.exists(paths['historico']):
            with open(paths['historico'], 'r') as f: st.session_state.historico = json.load(f)
    else: st.session_state.historico = []
    st.rerun()

if "sistema" not in st.session_state:
    st.session_state.sistema = SistemaBot()
    dados = carregar_dados_persistidos(st.session_state.api_selecionada)
    if dados:
        sis = st.session_state.sistema
        for n in dados.get('historico_numeros', []): sis.duzia_ai.adicionar(n); sis.historico_numeros.append(n)
        sis.numero_rodada = dados.get('numero_rodada'); sis.acertos_duzia = dados.get('acertos_duzia', 0)
        sis.erros_duzia = dados.get('erros_duzia', 0); sis.acertos_numero = dados.get('acertos_numero', 0)
        sis.erros_numero = dados.get('erros_numero', 0); sis.acertos_zero = dados.get('acertos_zero', 0)
        sis.erros_zero = dados.get('erros_zero', 0); sis.entrada_ativa = dados.get('entrada_ativa')
        sis.historico_entradas = dados.get('historico_entradas', []); sis.rodadas_na_sessao = dados.get('rodadas_na_sessao', 0)
        sis.sessao_ativa = dados.get('sessao_ativa', False); sis.total_sessoes = dados.get('total_sessoes', 0)
        sis.acertos_sessao = dados.get('acertos_sessao', 0); sis.erros_sessao = dados.get('erros_sessao', 0)
        if dados.get('sessao_pausa_ate'): sis.sessao_pausa_ate = datetime.fromisoformat(dados['sessao_pausa_ate'])
        if 'performance_por_mesa' in dados:
            for k, v in dados['performance_por_mesa'].items(): sis.performance_por_mesa[k] = v; sis.duzia_ai.performance_por_mesa[k] = v
        if 'performance_por_horario' in dados:
            for k, v in dados['performance_por_horario'].items(): sis.performance_por_horario[k] = v; sis.duzia_ai.performance_por_horario[k] = v
        paths = get_session_paths(st.session_state.api_selecionada)
        if os.path.exists(paths['historico']):
            with open(paths['historico'], 'r') as f: st.session_state.historico = json.load(f)

if "modo_automatico" not in st.session_state: st.session_state.modo_automatico = config_global.get('modo_automatico', True)
if "modo_agressivo" not in st.session_state: st.session_state.modo_agressivo = False
if "janela_duzia_ai" not in st.session_state: st.session_state.janela_duzia_ai = config_global.get('janela_duzia_ai', 30)
if "historico" not in st.session_state: st.session_state.historico = []

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.markdown("## ⚙️ V13 - UMA DÚZIA")
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
    
    if len(sis.duzia_ai.historico) >= 10:
        st.markdown("---")
        st.markdown("### 🧠 Inteligência V13")
        entropia_atual = sis.duzia_ai.entropia_mesa
        janela_ml = sis.duzia_ai.janela_ml_atual
        taxa_recente = sis.duzia_ai.filtro_bollinger.taxa_recente() * 100
        
        col_e, col_j, col_t = st.columns(3)
        with col_e:
            if entropia_atual > 0.85: st.error(f"🌪️ {entropia_atual:.2f}")
            elif entropia_atual > 0.6: st.warning(f"🌤️ {entropia_atual:.2f}")
            else: st.success(f"✨ {entropia_atual:.2f}")
            st.caption("Entropia")
        with col_j:
            if janela_ml <= 50: st.success(f"🎯 {janela_ml}")
            elif janela_ml <= 100: st.info(f"📊 {janela_ml}")
            else: st.warning(f"🔍 {janela_ml}")
            st.caption("Janela ML")
        with col_t:
            if taxa_recente >= 70: st.success(f"📈 {taxa_recente:.0f}%")
            elif taxa_recente >= 50: st.warning(f"📊 {taxa_recente:.0f}%")
            else: st.error(f"📉 {taxa_recente:.0f}%")
            st.caption("Taxa Recente")
    
    botao_desabilitado = sis.sessao_ativa or (sis.sessao_pausa_ate and hora_brasilia() < sis.sessao_pausa_ate)
    if botao_desabilitado: st.button("🚀 INICIAR SESSÃO", use_container_width=True, disabled=True)
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
    if rodadas != st.session_state.rodadas_por_sessao: st.session_state.rodadas_por_sessao = rodadas; sis.rodadas_por_sessao = rodadas; salvar_sessao()
    if pausa != st.session_state.pausa_entre_sessoes: st.session_state.pausa_entre_sessoes = pausa; sis.pausa_entre_sessoes = pausa; salvar_sessao()
    
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
                        with open(caminho, 'r') as f: conteudo = f.read()
                        st.markdown(gerenciador.get_download_link(conteudo, f"consolidado_{data_hoje}.json", 'json'), unsafe_allow_html=True)
                        st.success("✅ Consolidado gerado!")
            if st.button("📦 Baixar Todas as Sessões (JSON)", use_container_width=True):
                todas_sessoes = gerenciador.listar_sessoes()
                if todas_sessoes:
                    conteudo = json.dumps({'total_sessoes': len(todas_sessoes), 'sessoes': todas_sessoes}, indent=2, ensure_ascii=False)
                    st.markdown(gerenciador.get_download_link(conteudo, f"todas_sessoes_{api_name.lower().replace(' ', '_')}.json", 'json'), unsafe_allow_html=True)
        else: st.info("Nenhuma sessão salva ainda.")
    
    st.markdown("---")
    
    st.markdown("### 🎰 Selecione a Roleta")
    api_opcoes = list(API_URLS.keys())
    api_atual = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
    api_index = api_opcoes.index(api_atual) if api_atual in api_opcoes else 0
    st.session_state.api_selecionada = st.radio("Roleta:", api_opcoes, index=api_index)
    api_name = st.session_state.api_selecionada
    
    if api_name == 'XXXtreme Lightning':
        st.success(f"⚡ V13 | UMA DÚZIA | Gradient Boosting")
    elif api_name == 'Immersive Roulette':
        st.info(f"🎯 V13 | UMA DÚZIA | Janela Fixa 50")
    elif api_name == 'Mega Roulette':
        st.warning(f"⚡ V13 | UMA DÚZIA | ML Reforçado")
    
    if hasattr(sis.duzia_ai, 'modelo_ml') and sis.duzia_ai.modelo_ml is not None:
        st.success(f"🧠 ML V13 ATIVO | Gradient Boosting")
        st.caption(f"📏 Janela: {sis.duzia_ai.janela_ml_atual} rodadas")
    else: st.info("🧠 ML V13 Aguardando dados...")
    
    st.markdown("---")
    st.session_state.janela_duzia_ai = st.slider("📏 Janela", 10, 50, st.session_state.janela_duzia_ai, 5)
    st.session_state.modo_automatico = st.checkbox("🤖 Auto", value=st.session_state.modo_automatico)
    
    st.markdown("---")
    
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
with c1: entrada = st.text_input("Número (0-36):", key="entrada_numero")
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
    if st.button("🔄 Auto", use_container_width=True): st.session_state.modo_automatico = not st.session_state.modo_automatico; st.rerun()

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

st.subheader(f"📊 CONFERÊNCIA - {api_name} (UMA DÚZIA)")
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
    st.subheader("📈 Scores - UMA DÚZIA")
    if len(sis.historico_numeros) >= 3:
        score, gatilho = sis.duzia_ai.calcular_score()
        max_score_val = max(score.values())
        fig = plt.Figure(data=[plt.Bar(
            x=['D1', 'D2', 'D3'], y=[score[1], score[2], score[3]],
            marker_color=['#FF6B6B' if score[1]==max_score_val else '#4ECDC4',
                          '#FF6B6B' if score[2]==max_score_val else '#4ECDC4',
                          '#FF6B6B' if score[3]==max_score_val else '#4ECDC4'],
            text=[f'{score[1]:.0f}', f'{score[2]:.0f}', f'{score[3]:.0f}'], textposition='auto'
        )])
        titulo = f"🎯 {'⚠️ GATILHO: '+gatilho['tipo'] if gatilho else 'Sem gatilho'}"
        if sis.duzia_ai.modelo_ml is not None: titulo += f" | 🧠 V13 (J:{sis.duzia_ai.janela_ml_atual})"
        if sis.duzia_ai.alerta_zero_ativo: titulo += " | 🟢 ZERO!"
        if len(sis.duzia_ai.historico) >= 10:
            entropia = sis.duzia_ai.entropia_mesa
            if entropia > 0.85: titulo += f" | 🌪️ E:{entropia:.2f}"
            elif entropia < 0.5: titulo += f" | ✨ E:{entropia:.2f}"
            else: titulo += f" | E:{entropia:.2f}"
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
    if len(sis.duzia_ai.historico) >= 10:
        entropia = sis.duzia_ai.entropia_mesa
        if entropia > 1.00:
            st.error(f"🌪️ MESA CAÓTICA - Entropia: {entropia:.2f}")
    if sis.duzia_ai.alerta_zero_ativo: st.warning("⚠️ ALERTA ZERO! 🟢")
    if sis.duzia_ai.em_pausa_pos_raio: st.warning(f"⏸️ Pausa pós-raio ({sis.duzia_ai.ultimo_raio_alto}x)")
    if not sis.sessao_ativa:
        if sis.sessao_pausa_ate and hora_brasilia() < sis.sessao_pausa_ate:
            tempo_restante = (sis.sessao_pausa_ate - hora_brasilia()).seconds
            st.info(f"⏸️ Pausa: {tempo_restante//60:02d}:{tempo_restante%60:02d}")
        else: st.info("🔴 Clique 'INICIAR SESSÃO' para começar")
    if sis.entrada_ativa and sis.sessao_ativa:
        e = sis.entrada_ativa
        conf = e.get('confianca', 0); dz_princ = e.get('duzia_prevista', 0)
        gat = e.get('gatilho_ativo')
        melhores_principal = _selecionar_melhores_numeros(dz_princ, list(sis.historico_numeros), 6)
        cor = "#FF6347" if e.get('modo_anti_erro') else "#FFD700"
        st.markdown(f"""
        <div style="background-color:{cor}15; border:2px solid {cor}; border-radius:15px; padding:15px;">
            <h2 style="color:{cor}; text-align:center;">🎯 D{dz_princ}</h2>
            <p style="text-align:center; font-size:1.1em;">Confiança: {conf:.2f} {'| 🎯 '+gat if gat else ''}</p>
        </div>""", unsafe_allow_html=True)
        st.write(f"**🎲 6 melhores D{dz_princ}:** {', '.join(map(str, melhores_principal))}")
        st.progress(min(1.0, max(0.0, conf/5.0)))
    else: st.info("🔍 Aguardando sinal...")
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
        zero = '🟢' if e.get('incluir_zero') else '-'
        anti = '🔄' if e.get('modo_anti_erro') else '-'
        duz = '✅' if e.get('acerto_duzia') else '❌'
        num = '🎯' if e.get('acerto_numero') else '-'
        zer = '🟢' if e.get('acerto_zero') else '-'
        numero_sorteado = e.get('numero', 0)
        if e.get('eh_raio'): num_display = f"⚡{numero_sorteado} ({e.get('multiplicador',0)}x)"
        elif numero_sorteado == 0: num_display = "0"
        else: num_display = str(numero_sorteado)
        dados.append({"Rod": e.get('rodada'), "Hora": e.get('hora'), "🎲": num_display, "Real": real, "Prev": prev, "Conf": f"{e.get('confianca',0):.1f}", "Gat": e.get('gatilho','-') if e.get('gatilho') else '-', "Z": zero, "🔄": anti, "Duz": duz, "Nº": num, "Zer": zer})
    st.dataframe(dados, use_container_width=True, height=300)
    if st.button("📥 Exportar CSV", use_container_width=True):
        if exportar_historico_csv(sis.historico_entradas): st.success("✅")
else: st.info("Nenhuma entrada.")

st.markdown("---")
st.caption("📡 **Status Telegram:**")
col_t1, col_t2 = st.columns(2)
with col_t1:
    if st.session_state.telegram_token and st.session_state.telegram_chat_id: st.success("🔔 Principal: CONFIGURADO")
    else: st.warning("🔔 Principal: NÃO CONFIGURADO")
with col_t2:
    if st.session_state.telegram_token_alt and st.session_state.telegram_chat_id_alt: st.success("📢 Alternativo: CONFIGURADO")
    else: st.warning("📢 Alternativo: NÃO CONFIGURADO")

st.caption(f"🤖 DuziaAI V13 | FOCO UMA DÚZIA | Gradient Boosting + Convergência | {api_name} | {formatar_hora_brasilia()}")
salvar_sessao()
