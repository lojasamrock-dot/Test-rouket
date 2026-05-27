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

# =============================
# IMPORTAÇÃO SEGURA DE ML
# =============================
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import cross_val_score
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
# SETUPS POR ROLETA
# =============================
SETUP_BASE = {
    'pagamento_numero': 20, 'pagamento_zero': 20, 'pagamento_duzia': 3,
    'confianca_minima_entrada': 2.0, 'zero_termometro_max': 15,
    'pausa_pos_raio': 1, 'raio_alto_minimo': 100,
    'ml_janela_treino': 150, 'ml_atualizar_a_cada': 10,
    'score_minimo_entrada': 40,         # Score ML mínimo para entrar (0-100)
    'diferenca_minima_scores': 8,       # Diferença mínima entre 1º e 2º score
    'calibrar_probabilidades': True,    # Usar CalibratedClassifierCV
    'usar_ensemble': True,              # Usar ensemble RF+GB+LR
    'janela_features_curta': 50,        # Janela recente para features
    'janela_features_longa': 100,        # Janela histórica para features
    'gap_zero_alerta': 18,              # Rodadas sem zero para incluir zero
    'confianca_max_cap': 4.0,
}

SETUP_XXXTREME = {**SETUP_BASE, 'pagamento_numero': 20, 'pagamento_zero': 20, 'score_minimo_entrada': 38, 'diferenca_minima_scores': 6}
SETUP_IMMERSIVE = {**SETUP_BASE, 'pagamento_numero': 35, 'pagamento_zero': 35, 'score_minimo_entrada': 42, 'diferenca_minima_scores': 8}
SETUP_MEGA = {**SETUP_BASE, 'pagamento_numero': 24, 'pagamento_zero': 24, 'score_minimo_entrada': 40, 'diferenca_minima_scores': 7}

ROLETA_CONFIGS = {
    'XXXtreme Lightning': SETUP_XXXTREME,
    'Immersive Roulette': SETUP_IMMERSIVE,
    'Mega Roulette': SETUP_MEGA,
}

# =============================
# CONFIGURAÇÕES GLOBAIS
# =============================
CONFIG_GLOBAL_PATH = "config_global.json"
PASTA_SESSOES = "sessoes_salvas"

def criar_pasta_sessoes():
    if not os.path.exists(PASTA_SESSOES):
        os.makedirs(PASTA_SESSOES)
    for roleta in ['xxxtreme_lightning', 'immersive_roulette', 'mega_roulette']:
        pasta = os.path.join(PASTA_SESSOES, roleta)
        if not os.path.exists(pasta):
            os.makedirs(pasta)

def get_pasta_sessao(api_name):
    return os.path.join(PASTA_SESSOES, api_name.lower().replace(' ', '_'))

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
        'modelo_ml': f"modelo_ml_{safe}.pkl",  # 🆕 Persistência do modelo ML
    }

# =============================
# GERENCIADOR DE SESSÕES
# =============================
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
            (consolidado['resumo_geral']['total_acertos'] / max(1, total)) * 100, 1)
        nome_arquivo = f"consolidado_{data}_{self.api_name.lower().replace(' ', '_')}.json"
        caminho = os.path.join(self.pasta_sessao, nome_arquivo)
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(consolidado, f, indent=2, ensure_ascii=False)
        return caminho

    def gerar_csv_sessao(self, dados_sessao):
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Rodada', 'Hora', 'Número', 'Raio', 'Dúzia Real', 'Dúzia Prevista',
                         'Cobertura', 'Confiança', 'Zero', 'Anti-Erro',
                         'Acerto Dúzia', 'Acerto Número', 'Acerto Zero', 'Status'])
        for e in dados_sessao.get('entradas', []):
            real = f"D{e.get('duzia_real',0)}" if e.get('duzia_real', 0) != 0 else "0"
            prev = f"D{e.get('duzia_prevista', '?')}"
            cob = f"D{e.get('duzia_sec_prevista', '?')}" if e.get('duzia_sec_prevista') and e.get('duzia_sec_prevista') != e.get('duzia_prevista') else "-"
            zero = 'Sim' if e.get('incluir_zero') else 'Não'
            anti = 'Sim' if e.get('modo_anti_erro') else 'Não'
            writer.writerow([
                e.get('rodada'), e.get('hora'), e.get('numero', 0),
                f"{e.get('multiplicador', 0)}x" if e.get('eh_raio') else '-',
                real, prev, cob, f"{e.get('confianca', 0):.2f}",
                zero, anti,
                'Sim' if e.get('acerto_duzia') else 'Não',
                'Sim' if e.get('acerto_numero') else 'Não',
                'Sim' if e.get('acerto_zero') else 'Não',
                e.get('status', '?')
            ])
        return output.getvalue()

    def get_download_link(self, conteudo, nome_arquivo, tipo='json'):
        b64 = base64.b64encode(conteudo.encode()).decode()
        mime = 'text/csv' if tipo == 'csv' else 'application/json'
        return f'<a href="data:{mime};base64,{b64}" download="{nome_arquivo}">📥 Baixar {nome_arquivo}</a>'


# =============================
# UTILITÁRIOS
# =============================
def get_duzia(numero):
    if numero == 0: return 0
    elif 1 <= numero <= 12: return 1
    elif 13 <= numero <= 24: return 2
    else: return 3

def validar_numero(valor):
    try:
        num = int(valor); return 0 <= num <= 36
    except: return False

def enviar_telegram(mensagem, token, chat_id):
    try:
        if not token or not chat_id: return
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e: logging.error(f"Erro Telegram: {e}")

def _selecionar_melhores_numeros(duzia, numeros_completos, quantidade=6):
    if duzia == 1: numeros_da_duzia = list(range(1, 13))
    elif duzia == 2: numeros_da_duzia = list(range(13, 25))
    else: numeros_da_duzia = list(range(25, 37))
    recentes = numeros_completos[-20:] if len(numeros_completos) >= 20 else numeros_completos
    freq = Counter([n for n in recentes if n in numeros_da_duzia])
    terminais = [n % 10 for n in recentes[-15:] if n != 0]
    terminais_quentes = [t for t, f in Counter(terminais).most_common(3) if f >= 2]
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


# =============================
# 🧠 ENGENHARIA DE FEATURES V12
# =============================
def extrair_features_completas(historico_duzias, historico_numeros, janela_curta=50, janela_longa=100):
    """
    Features ricas para o modelo ML.
    Retorna vetor de 40+ features ou None se dados insuficientes.
    """
    if len(historico_duzias) < 8 or len(historico_numeros) < 8:
        return None

    nums = historico_numeros
    duzias = historico_duzias
    nums_j_longa = nums[-janela_longa:] if len(nums) >= janela_longa else nums
    duzias_j_longa = [d for d in duzias[-janela_longa:] if d != 0]
    nums_j_curta = nums[-janela_curta:] if len(nums) >= janela_curta else nums
    duzias_j_curta = [d for d in duzias[-janela_curta:] if d != 0]

    if not duzias_j_longa or not duzias_j_curta:
        return None

    # --- 1. Frequências relativas (janela longa e curta) ---
    freq_longa = Counter(duzias_j_longa)
    total_longa = max(1, len(duzias_j_longa))
    freq_curta = Counter(duzias_j_curta)
    total_curta = max(1, len(duzias_j_curta))
    f1_l, f2_l, f3_l = freq_longa.get(1, 0) / total_longa, freq_longa.get(2, 0) / total_longa, freq_longa.get(3, 0) / total_longa
    f1_c, f2_c, f3_c = freq_curta.get(1, 0) / total_curta, freq_curta.get(2, 0) / total_curta, freq_curta.get(3, 0) / total_curta

    # --- 2. Tendência: curta vs longa (crescimento recente) ---
    tend1 = f1_c - f1_l
    tend2 = f2_c - f2_l
    tend3 = f3_c - f3_l

    # --- 3. Gap (rodadas desde última aparição de cada dúzia) ---
    gap = {1: janela_longa, 2: janela_longa, 3: janela_longa}
    for i, d in enumerate(reversed(duzias[-janela_longa:])):
        if d in gap and gap[d] == janela_longa:
            gap[d] = i
    gap1, gap2, gap3 = gap[1] / janela_longa, gap[2] / janela_longa, gap[3] / janela_longa

    # --- 4. Streak atual ---
    streak_duzia, streak_count = duzias[-1] if duzias else 0, 0
    for d in reversed(duzias):
        if d == streak_duzia and d != 0:
            streak_count += 1
        else:
            break
    streak_norm = min(streak_count / 5, 1.0)

    # --- 5. Entropia de Shannon (aleatoriedade recente) ---
    if len(set(duzias_j_curta)) > 1:
        probs = [freq_curta.get(d, 0) / total_curta for d in [1, 2, 3]]
        entropia = -sum(p * np.log2(p + 1e-9) for p in probs if p > 0) / np.log2(3)
    else:
        entropia = 0.0

    # --- 6. Número de transições recentes (volatilidade) ---
    trans_curta = sum(
        1 for i in range(1, len(duzias_j_curta))
        if duzias_j_curta[i] != duzias_j_curta[i - 1]
    ) / max(1, len(duzias_j_curta) - 1)

    # --- 7. Padrão Markov de ordem 2 e 3 (últimas 2-3 duzias → próxima) ---
    ultimas_duzias = [d for d in duzias[-4:] if d != 0]
    m2_d1 = ultimas_duzias[-2] if len(ultimas_duzias) >= 2 else 0
    m2_d2 = ultimas_duzias[-1] if len(ultimas_duzias) >= 1 else 0
    m3_d1 = ultimas_duzias[-3] if len(ultimas_duzias) >= 3 else 0

    # --- 8. Análise de terminais (dígitos finais dos números) ---
    terminais = [n % 10 for n in nums_j_longa if n != 0]
    freq_term = Counter(terminais)
    t1_hot = freq_term.most_common(1)[0][0] if freq_term else 0
    t2_hot = freq_term.most_common(2)[1][0] if len(freq_term) >= 2 else 0

    # Terminal associado a cada dúzia
    term_d1 = sum(1 for n in nums_j_curta if 1 <= n <= 12 and n % 10 == t1_hot)
    term_d2 = sum(1 for n in nums_j_curta if 13 <= n <= 24 and n % 10 == t1_hot)
    term_d3 = sum(1 for n in nums_j_curta if 25 <= n <= 36 and n % 10 == t1_hot)

    # --- 9. Gap do zero (rodadas sem zero) ---
    try:
        gap_zero = list(reversed(nums[-janela_longa:])).index(0) / janela_longa
    except ValueError:
        gap_zero = 1.0

    # --- 10. Dominância: quão concentrada está a distribuição ---
    dominancia = max(f1_c, f2_c, f3_c) - min(f1_c, f2_c, f3_c)

    # --- 11. One-hot das últimas 4 dúzias ---
    ult4 = [d for d in duzias[-4:] if d != 0]
    while len(ult4) < 4: ult4.insert(0, 0)
    ult4_enc = []
    for d in ult4:
        ult4_enc.extend([1 if d == i else 0 for i in [1, 2, 3]])  # 12 features

    # --- 12. Hora do dia (padrão temporal) ---
    hora_atual = datetime.now().hour
    hora_norm = hora_atual / 23.0
    turno_manha = 1.0 if 6 <= hora_atual < 12 else 0.0
    turno_tarde = 1.0 if 12 <= hora_atual < 18 else 0.0
    turno_noite = 1.0 if hora_atual >= 18 or hora_atual < 6 else 0.0

    # Montar vetor final (40 features)
    features = [
        # Frequências (6)
        f1_l, f2_l, f3_l, f1_c, f2_c, f3_c,
        # Tendências (3)
        tend1, tend2, tend3,
        # Gaps (3)
        gap1, gap2, gap3,
        # Streak (1)
        streak_norm,
        # Entropia e volatilidade (2)
        entropia, trans_curta,
        # Markov (3)
        m2_d1 / 3.0, m2_d2 / 3.0, m3_d1 / 3.0,
        # Terminais (5)
        t1_hot / 9.0, t2_hot / 9.0,
        term_d1 / max(1, total_curta),
        term_d2 / max(1, total_curta),
        term_d3 / max(1, total_curta),
        # Zero (1)
        gap_zero,
        # Dominância (1)
        dominancia,
        # One-hot últimas 4 dúzias (12)
        *ult4_enc,
        # Temporal (3)
        hora_norm, turno_manha, turno_tarde,
    ]

    return features  # Total: 40 features


# =============================
# 🧠 MOTOR ML V12 - ENSEMBLE + CALIBRAÇÃO
# =============================
class MotorML:
    """
    Ensemble calibrado: RandomForest + GradientBoosting + LogisticRegression.
    Treinamento em background, persistência em disco, calibração de probabilidades.
    """

    def __init__(self, api_name='XXXtreme Lightning'):
        self.api_name = api_name
        self.modelo = None          # Modelo ensemble calibrado
        self.scaler = StandardScaler()
        self.scaler_fitted = False
        self.ultimo_treino = 0      # Rodada do último treino
        self.n_amostras_treino = 0
        self.score_cv = None        # Score de validação cruzada
        self.classes_ = [1, 2, 3]
        self._buffer_X = []         # Buffer de features para treino incremental
        self._buffer_y = []

    def _get_config(self):
        return ROLETA_CONFIGS.get(self.api_name, SETUP_BASE)

    def construir_dataset(self, historico_duzias, historico_numeros):
        """Constrói dataset de treino eficientemente (sem loop de features completas)."""
        config = self._get_config()
        jc = config.get('janela_features_curta', 10)
        jl = config.get('janela_features_longa', 30)
        min_hist = jl + 4

        if len(historico_duzias) < min_hist:
            return [], []

        X, y = [], []
        # Usar os últimos N pontos para treino (eficiente)
        janela_treino = config.get('ml_janela_treino', 150)
        inicio = max(min_hist, len(historico_duzias) - janela_treino)

        for i in range(inicio, len(historico_duzias)):
            target = historico_duzias[i]
            if target not in [1, 2, 3]:
                continue
            feats = extrair_features_completas(
                historico_duzias[:i],
                historico_numeros[:i],
                jc, jl
            )
            if feats is not None:
                X.append(feats)
                y.append(target)

        return X, y

    def treinar(self, historico_duzias, historico_numeros, rodada_atual):
        """Treina o ensemble calibrado. Retorna True se bem-sucedido."""
        if not ML_DISPONIVEL:
            return False

        config = self._get_config()
        atualizar_a_cada = config.get('ml_atualizar_a_cada', 5)

        # Treinar apenas a cada N rodadas
        if rodada_atual - self.ultimo_treino < atualizar_a_cada:
            return False

        X, y = self.construir_dataset(historico_duzias, historico_numeros)
        if len(X) < 30:
            return False

        try:
            X_arr = np.array(X, dtype=np.float32)
            y_arr = np.array(y)

            # Normalizar features
            X_scaled = self.scaler.fit_transform(X_arr)
            self.scaler_fitted = True

            # Definir base learners
            rf = RandomForestClassifier(
                n_estimators=150, max_depth=12, min_samples_leaf=3,
                random_state=42, n_jobs=-1, class_weight='balanced'
            )
            gb = GradientBoostingClassifier(
                n_estimators=100, max_depth=4, learning_rate=0.05,
                subsample=0.8, random_state=42
            )
            lr = LogisticRegression(
                C=1.0, max_iter=500, random_state=42,
                class_weight='balanced', multi_class='multinomial'
            )

            # Ensemble por votação suave
            ensemble = VotingClassifier(
                estimators=[('rf', rf), ('gb', gb), ('lr', lr)],
                voting='soft',
                weights=[3, 3, 1]   # RF e GB têm mais peso
            )

            # Calibrar probabilidades com Platt scaling
            if config.get('calibrar_probabilidades', True) and len(X) >= 60:
                modelo_calibrado = CalibratedClassifierCV(
                    ensemble, method='sigmoid', cv=3
                )
            else:
                modelo_calibrado = ensemble

            modelo_calibrado.fit(X_scaled, y_arr)

            # Validação cruzada para monitorar qualidade
            if len(X) >= 60:
                scores_cv = cross_val_score(
                    modelo_calibrado, X_scaled, y_arr,
                    cv=min(3, len(X) // 20), scoring='accuracy'
                )
                self.score_cv = float(np.mean(scores_cv))
            else:
                self.score_cv = None

            self.modelo = modelo_calibrado
            self.ultimo_treino = rodada_atual
            self.n_amostras_treino = len(X)

            # Persistir modelo em disco
            paths = get_session_paths(self.api_name)
            try:
                joblib.dump({
                    'modelo': self.modelo,
                    'scaler': self.scaler,
                    'rodada': rodada_atual,
                    'n_amostras': len(X),
                    'score_cv': self.score_cv
                }, paths['modelo_ml'])
            except Exception as e:
                logging.warning(f"Não foi possível persistir modelo: {e}")

            logging.info(
                f"🧠 ML V12 Treinado | Amostras: {len(X)} | "
                f"CV Accuracy: {self.score_cv:.3f if self.score_cv else 'N/A'} | "
                f"Rodada: {rodada_atual}"
            )
            return True

        except Exception as e:
            logging.error(f"❌ Erro no treinamento ML V12: {e}")
            return False

    def carregar_modelo_disco(self):
        """Carrega modelo persistido do disco."""
        if not ML_DISPONIVEL:
            return False
        paths = get_session_paths(self.api_name)
        if os.path.exists(paths['modelo_ml']):
            try:
                dados = joblib.load(paths['modelo_ml'])
                self.modelo = dados['modelo']
                self.scaler = dados['scaler']
                self.scaler_fitted = True
                self.ultimo_treino = dados.get('rodada', 0)
                self.n_amostras_treino = dados.get('n_amostras', 0)
                self.score_cv = dados.get('score_cv')
                logging.info(f"🧠 Modelo ML carregado do disco | Rodada: {self.ultimo_treino}")
                return True
            except Exception as e:
                logging.warning(f"Não foi possível carregar modelo do disco: {e}")
        return False

    def prever(self, historico_duzias, historico_numeros):
        """
        Retorna dict {1: prob, 2: prob, 3: prob} com probabilidades calibradas.
        Fallback para frequência bayesiana se modelo não disponível.
        """
        config = self._get_config()
        jc = config.get('janela_features_curta', 10)
        jl = config.get('janela_features_longa', 30)

        if self.modelo is not None and self.scaler_fitted:
            try:
                feats = extrair_features_completas(historico_duzias, historico_numeros, jc, jl)
                if feats is not None:
                    X = np.array([feats], dtype=np.float32)
                    X_scaled = self.scaler.transform(X)
                    probs = self.modelo.predict_proba(X_scaled)[0]
                    classes = self.modelo.classes_ if hasattr(self.modelo, 'classes_') else [1, 2, 3]
                    resultado = {1: 0.0, 2: 0.0, 3: 0.0}
                    for cls, prob in zip(classes, probs):
                        if cls in resultado:
                            resultado[cls] = float(prob) * 100
                    return resultado, 'ensemble'
            except Exception as e:
                logging.error(f"❌ Erro na inferência ML V12: {e}")

        # Fallback Bayesiano: frequência com suavização de Laplace
        duzias_validas = [d for d in historico_duzias[-30:] if d != 0]
        freq = Counter(duzias_validas)
        total = len(duzias_validas) + 3  # Laplace smoothing
        return {
            1: ((freq.get(1, 0) + 1) / total) * 100,
            2: ((freq.get(2, 0) + 1) / total) * 100,
            3: ((freq.get(3, 0) + 1) / total) * 100,
        }, 'fallback'


# =============================
# 🧠 DUZIA AI V12
# =============================
class DuziaAI:
    def __init__(self, window=30, api_name='XXXtreme Lightning'):
        self.api_name = api_name
        self.historico = deque(maxlen=window)
        self.historico_completo = []
        self.numeros_completos = []
        self.motor_ml = MotorML(api_name)
        self.motor_ml.carregar_modelo_disco()

        # Estado de controle
        self.rodadas_desde_zero = 0
        self.erros_consecutivos = 0
        self.modo_anti_erro = False
        self.alerta_zero_ativo = False
        self.em_pausa_pos_raio = False
        self.ultimo_raio_alto = 0
        self.rodadas_pos_raio = 0
        self.pausa_ate = None

        # Tracking de resultados
        self.ultima_previsao_duzia = None
        self.ultima_confianca = 0.0
        self.ultimo_resultado_duzia = None
        self.ultimo_resultado_numero = None
        self.alertas_zero_disparados = 0
        self.zeros_previstos = 0
        self.acertos_consecutivos = 0
        self.erros_por_duzia = {1: 0, 2: 0, 3: 0}

        # Performance
        self.performance_por_mesa = defaultdict(lambda: {'acertos': 0, 'erros': 0})
        self.performance_por_horario = defaultdict(lambda: {'acertos': 0, 'erros': 0})
        self.mesa_atual = None

        # Rastreio de confiança histórica para calibração dinâmica
        self._historico_confiancas = []
        self._historico_acertos_conf = []   # 1 = acertou, 0 = errou (para análise de calibração)

    def _get_config(self):
        return ROLETA_CONFIGS.get(self.api_name, SETUP_BASE).copy()

    def adicionar(self, numero):
        """Adiciona número ao histórico e dispara treino ML."""
        d = get_duzia(numero)
        self.historico.append(d)
        self.historico_completo.append(d)
        self.numeros_completos.append(numero)

        if numero == 0:
            self.rodadas_desde_zero = 0
            if self.alerta_zero_ativo:
                self.zeros_previstos += 1
        else:
            self.rodadas_desde_zero += 1

        # Controle pós-raio
        if self.em_pausa_pos_raio:
            self.rodadas_pos_raio += 1
            config = self._get_config()
            if self.rodadas_pos_raio >= config.get('pausa_pos_raio', 1):
                self.em_pausa_pos_raio = False

        # Limitar histórico em memória
        if len(self.historico_completo) > 1000:
            self.historico_completo = self.historico_completo[-800:]
            self.numeros_completos = self.numeros_completos[-800:]

        # Treinar ML (somente a cada N rodadas - controlado pelo MotorML)
        rodada_atual = len(self.historico_completo)
        self.motor_ml.treinar(self.historico_completo, self.numeros_completos, rodada_atual)

    def registrar_previsao(self, duzia, confianca):
        self.ultima_previsao_duzia = duzia
        self.ultima_confianca = confianca

    def registrar_resultado(self, duzia_real, acertou_duzia, acertou_numero, acertou_zero,
                            mesa_id=None, eh_raio=False, multiplicador=0):
        config = self._get_config()
        self.ultimo_resultado_duzia = acertou_duzia
        self.ultimo_resultado_numero = acertou_numero

        # Raio alto → pausa
        if eh_raio and multiplicador >= config.get('raio_alto_minimo', 100) and config.get('pausa_pos_raio', 0) > 0:
            self.em_pausa_pos_raio = True
            self.rodadas_pos_raio = 0
            self.ultimo_raio_alto = multiplicador

        # Performance por mesa
        if mesa_id:
            self.mesa_atual = mesa_id
            chave = 'acertos' if (acertou_duzia or acertou_zero) else 'erros'
            self.performance_por_mesa[mesa_id][chave] += 1

        # Performance por horário
        hora = datetime.now().hour
        turno = "manhã" if 6 <= hora < 12 else "tarde" if 12 <= hora < 18 else "noite"
        chave = 'acertos' if (acertou_duzia or acertou_zero) else 'erros'
        self.performance_por_horario[turno][chave] += 1

        # Calibração dinâmica de confiança
        self._historico_confiancas.append(self.ultima_confianca)
        self._historico_acertos_conf.append(1 if (acertou_duzia or acertou_zero) else 0)
        if len(self._historico_confiancas) > 100:
            self._historico_confiancas = self._historico_confiancas[-100:]
            self._historico_acertos_conf = self._historico_acertos_conf[-100:]

        # Controle de erros
        if not acertou_duzia and not acertou_zero:
            self.erros_consecutivos += 1
            if duzia_real in [1, 2, 3]:
                self.erros_por_duzia[duzia_real] += 1
            self.modo_anti_erro = True
            self.acertos_consecutivos = 0
        else:
            self.erros_consecutivos = 0
            self.modo_anti_erro = False
            self.erros_por_duzia = {1: 0, 2: 0, 3: 0}
            self.acertos_consecutivos += 1

    def _calcular_confianca_calibrada(self, prob_max, prob_2o, fonte):
        """
        Converte probabilidades do modelo em score de confiança interpretável.
        Usa a diferença relativa entre 1º e 2º lugar + calibração histórica.
        """
        # Diferença relativa (quanto a 1ª dúzia se destaca)
        diff_relativa = (prob_max - prob_2o) / max(prob_max, 1e-6)

        # Score base de 0 a 5
        confianca_base = diff_relativa * 5.0

        # Ajuste baseado no nível absoluto de confiança do modelo
        if prob_max > 50:
            confianca_base *= 1.1
        elif prob_max < 38:
            confianca_base *= 0.7

        # Fallback tem confiança reduzida
        if fonte == 'fallback':
            confianca_base *= 0.75

        # Calibração baseada em histórico recente (últimos 20 resultados)
        if len(self._historico_acertos_conf) >= 10:
            taxa_recente = sum(self._historico_acertos_conf[-20:]) / min(20, len(self._historico_acertos_conf))
            if taxa_recente < 0.45:      # Taxa ruim → reduz confiança
                confianca_base *= 0.85
            elif taxa_recente > 0.70:    # Taxa ótima → aumenta levemente
                confianca_base *= 1.05

        config = self._get_config()
        return round(min(config.get('confianca_max_cap', 4.0), max(0.0, confianca_base)), 2)

    def detectar_alerta_zero(self):
        """Detecção de zero mais precisa, baseada em gap e padrões."""
        config = self._get_config()
        gap_zero_alerta = config.get('gap_zero_alerta', 18)
        nums = self.numeros_completos

        # Critério 1: Gap elevado (principal)
        if self.rodadas_desde_zero >= gap_zero_alerta:
            self.alerta_zero_ativo = True
            self.alertas_zero_disparados += 1
            return True

        # Critério 2: Zero recente (momentum)
        if len(nums) >= 2 and nums[-1] == 0:
            self.alerta_zero_ativo = True
            return True

        # Critério 3: Alta repetição de mesma dúzia (desequilíbrio)
        duzias_recentes = [get_duzia(n) for n in nums[-6:] if n != 0]
        if len(duzias_recentes) >= 5:
            contagem = Counter(duzias_recentes)
            if contagem.most_common(1)[0][1] >= 5:
                self.alerta_zero_ativo = True
                return True

        self.alerta_zero_ativo = False
        return False

    def prever(self):
        """Previsão principal usando ML Ensemble V12."""
        config = self._get_config()

        # --- Verificações de bloqueio ---
        if self.pausa_ate and hora_brasilia() < self.pausa_ate:
            return {"entrar": False, "motivo": "⏸️ Pausa ativa"}

        hora_atual = datetime.now().hour
        if 'horario_bloqueio_inicio' in config and 'horario_bloqueio_fim' in config:
            if config['horario_bloqueio_inicio'] <= hora_atual < config['horario_bloqueio_fim']:
                return {"entrar": False, "motivo": f"⏸️ Horário bloqueado"}

        if self.em_pausa_pos_raio:
            return {"entrar": False, "motivo": f"⏸️ Pausa pós-raio ({self.ultimo_raio_alto}x)"}

        # --- Obter probabilidades do ML ---
        scores, fonte = self.motor_ml.prever(self.historico_completo, self.numeros_completos)

        # --- Ranking das dúzias ---
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        d1, s1 = ranking[0]
        d2, s2 = ranking[1] if len(ranking) > 1 else (([x for x in [1, 2, 3] if x != d1][0]), 0.0)

        # --- Detectar alerta zero ---
        self.detectar_alerta_zero()

        # --- Calcular confiança calibrada ---
        confianca = self._calcular_confianca_calibrada(s1, s2, fonte)

        # --- Critérios de entrada ---
        score_minimo = config.get('score_minimo_entrada', 40)
        diferenca_minima = config.get('diferenca_minima_scores', 8)

        pode_entrar = (
            s1 >= score_minimo
            and (s1 - s2) >= diferenca_minima
            and confianca >= 0.5
        )

        # Anti-erro: reduz confiança em erros consecutivos
        if self.erros_consecutivos >= 2:
            confianca = round(confianca * (0.9 ** (self.erros_consecutivos - 1)), 2)
            if confianca < 0.4:
                pode_entrar = False

        motivo = f"ML Ensemble ({fonte}) | Score: {s1:.1f} | Diff: {s1-s2:.1f}"
        if not pode_entrar:
            motivo = f"Score insuficiente ({s1:.1f}) ou diff baixa ({s1-s2:.1f})"

        # --- Zero ---
        incluir_zero = self.alerta_zero_ativo or (self.rodadas_desde_zero >= config.get('zero_termometro_max', 15))

        return {
            "entrar": pode_entrar,
            "motivo": motivo,
            "score": scores,
            "confianca": confianca,
            "duzia": d1,
            "duzia_secundaria": d2,
            "fonte_ml": fonte,
            "incluir_zero": incluir_zero,
            "modo_anti_erro": self.modo_anti_erro,
            "numeros_completos": list(self.numeros_completos),
            "score_cv": self.motor_ml.score_cv,
        }

    def get_status_ml(self):
        """Retorna informações de status do modelo ML."""
        ml = self.motor_ml
        return {
            'ativo': ml.modelo is not None,
            'amostras': ml.n_amostras_treino,
            'ultimo_treino': ml.ultimo_treino,
            'score_cv': ml.score_cv,
            'taxa_recente': (
                round(sum(self._historico_acertos_conf[-20:]) / min(20, len(self._historico_acertos_conf)) * 100, 1)
                if self._historico_acertos_conf else None
            )
        }


# =============================
# APIS
# =============================
API_URLS = {
    'XXXtreme Lightning': "https://api.casinoscores.com/svc-evolution-game-events/api/xxxtremelightningroulette/latest",
    'Immersive Roulette': "https://api.casinoscores.com/svc-evolution-game-events/api/immersiveroulette/latest",
    'Mega Roulette': "https://api.casinoscores.com/svc-evolution-game-events/api/megaroulette/latest",
}
HEADERS = {"User-Agent": "Mozilla/5.0"}

def _parse_resultado_api(d, api_key):
    gd = d.get("data", {})
    rs = gd.get("result", {})
    nm = rs.get("outcome", {}).get("number")
    ts = gd.get("startedAt")
    table_info = gd.get("table", {})
    ln, lm = [], {}
    for item in rs.get('luckyNumbersList', []):
        n = item.get('number')
        if n is not None:
            ln.append(n)
            m = item.get('roundedMultiplier')
            if m is not None: lm[n] = m
    return {"number": nm, "timestamp": ts, "luckyNumbers": ln, "luckyMultipliers": lm,
            "table_id": table_info.get("id", "unknown"), "table_name": table_info.get("name", "Desconhecida")}

def fetch_resultado(api_name):
    try:
        url = API_URLS[api_name]
        r = requests.get(url, headers=HEADERS, timeout=5)
        r.raise_for_status()
        return _parse_resultado_api(r.json(), api_name)
    except Exception as e:
        logging.warning(f"❌ Erro {api_name}: {e}")
        return None

def fetch_latest_result():
    api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
    return fetch_resultado(api_name)


# =============================
# PERSISTÊNCIA
# =============================
def salvar_sessao():
    try:
        if 'sistema' not in st.session_state or st.session_state.sistema is None: return False
        sis = st.session_state.sistema
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        paths = get_session_paths(api_name)
        session_data = {
            'historico_numeros': list(sis.historico_numeros),
            'entrada_ativa': sis.entrada_ativa,
            'acertos_duzia': sis.acertos_duzia,
            'erros_duzia': sis.erros_duzia,
            'acertos_numero': sis.acertos_numero,
            'erros_numero': sis.erros_numero,
            'acertos_zero': sis.acertos_zero,
            'erros_zero': sis.erros_zero,
            'numero_rodada': sis.numero_rodada,
            'rodadas_na_sessao': sis.rodadas_na_sessao,
            'sessao_ativa': sis.sessao_ativa,
            'sessao_pausa_ate': sis.sessao_pausa_ate.isoformat() if sis.sessao_pausa_ate else None,
            'total_sessoes': sis.total_sessoes,
            'acertos_sessao': sis.acertos_sessao,
            'erros_sessao': sis.erros_sessao,
        }
        with open(paths['session'], 'wb') as f: pickle.dump(session_data, f)
        with open(paths['entradas'], 'w') as f: json.dump(sis.historico_entradas, f)
        with open(paths['performance_mesa'], 'w') as f: json.dump(dict(sis.performance_por_mesa), f)
        with open(paths['performance_horario'], 'w') as f: json.dump(dict(sis.performance_por_horario), f)
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
            with open(paths['session'], 'rb') as f: dados = pickle.load(f)
        if os.path.exists(paths['entradas']):
            with open(paths['entradas'], 'r') as f: dados['historico_entradas'] = json.load(f)
        if os.path.exists(paths['performance_mesa']):
            with open(paths['performance_mesa'], 'r') as f: dados['performance_por_mesa'] = json.load(f)
        if os.path.exists(paths['performance_horario']):
            with open(paths['performance_horario'], 'r') as f: dados['performance_por_horario'] = json.load(f)
    except: pass
    return dados

def nova_sessao():
    try:
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        paths = get_session_paths(api_name)
        for key, path in paths.items():
            if key != 'modelo_ml' and os.path.exists(path):  # Preserva modelo ML!
                os.remove(path)
        if 'sistema' in st.session_state: st.session_state.sistema.zerar()
        st.session_state.historico = []
        logging.info(f"🆕 NOVA SESSÃO - {api_name}")
        return True
    except Exception as e:
        logging.error(f"Erro: {e}")
        return False

def salvar_resultado_em_arquivo(historico, caminho):
    try:
        with open(caminho, "w", encoding='utf-8') as f: json.dump(historico, f, indent=2)
    except Exception as e: logging.error(f"Erro: {e}")

def exportar_historico_csv(historico_entradas, caminho="export_roleta.csv"):
    try:
        with open(caminho, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Rod', 'Hora', 'Nº', 'Raio', 'Real', 'Prev', 'Cob', 'Conf', 'Fonte ML', 'Z', '🔄', 'Duz', 'Num', 'Zer', 'St'])
            for e in historico_entradas:
                real = f"D{e.get('duzia_real', 0)}" if e.get('duzia_real', 0) != 0 else "0"
                prev = f"D{e.get('duzia_prevista', '?')}"
                cob = f"D{e.get('duzia_sec_prevista', '?')}" if e.get('duzia_sec_prevista') and e.get('duzia_sec_prevista') != e.get('duzia_prevista') else "-"
                writer.writerow([
                    e.get('rodada'), e.get('hora'), e.get('numero'),
                    f"⚡{e.get('multiplicador', 0)}x" if e.get('eh_raio') else '-',
                    real, prev, cob, f"{e.get('confianca', 0):.2f}",
                    e.get('fonte_ml', 'ML'),
                    '🟢' if e.get('incluir_zero') else '-',
                    '🔄' if e.get('modo_anti_erro') else '-',
                    '✅' if e.get('acerto_duzia') else '❌',
                    '✅' if e.get('acerto_numero') else '-',
                    '✅' if e.get('acerto_zero') else '-',
                    e.get('status', '?')
                ])
        return True
    except Exception as e:
        logging.error(f"Erro CSV: {e}")
        return False


# =============================
# SISTEMA PRINCIPAL
# =============================
def _enviar_previsao_auto(previsao, historico_numeros):
    try:
        numeros = sorted(previsao.get('numeros_apostar', []))
        incluir_zero = previsao.get('incluir_zero', False)
        duzia_principal = previsao.get('duzia', 0)
        duzia_secundaria = previsao.get('duzia_secundaria', 0)
        d1n = [n for n in numeros if 1 <= n <= 12]
        d2n = [n for n in numeros if 13 <= n <= 24]
        d3n = [n for n in numeros if 25 <= n <= 36]
        prefixo = "⚠️🎯 " if incluir_zero else "🎯 "
        if d1n and d2n: msg = f"{prefixo}Entrada: D1 | Cob: D2"
        elif d1n and d3n: msg = f"{prefixo}Entrada: D1 | Cob: D3"
        elif d2n and d3n: msg = f"{prefixo}Entrada: D2 | Cob: D3"
        elif d1n: msg = f"{prefixo}Entrada: D1 (1-12)"
        elif d2n: msg = f"{prefixo}Entrada: D2 (13-24)"
        elif d3n: msg = f"{prefixo}Entrada: D3 (25-36)"
        else: msg = f"{prefixo}Entrada: {numeros}"
        if incluir_zero: msg += " + 🟢 ZERO"
        fonte = previsao.get('fonte_ml', 'ML')
        conf = previsao.get('confianca', 0)
        msg += f" | Conf: {conf:.2f} ({fonte})"
        melhores_principal = _selecionar_melhores_numeros(duzia_principal, list(historico_numeros), 6)
        if duzia_secundaria and duzia_secundaria != duzia_principal:
            melhores_secundaria = _selecionar_melhores_numeros(duzia_secundaria, list(historico_numeros), 6)
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
    except Exception as e: logging.error(f"Erro enviar_previsao_auto: {e}")

def _enviar_resultado_auto(numero_real, acerto_duzia, acerto_numero, acerto_zero, eh_raio=False, multiplicador=0):
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
    except Exception as e: logging.error(f"Erro enviar_resultado_auto: {e}")


class SistemaBot:
    def __init__(self):
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        janela = st.session_state.get('janela_duzia_ai', 30)
        self.duzia_ai = DuziaAI(window=janela, api_name=api_name)
        self.historico_numeros = deque(maxlen=200)
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
        self.gerenciador_sessoes = GerenciadorSessoes(api_name)

    def iniciar_sessao(self):
        if self.sessao_pausa_ate and hora_brasilia() < self.sessao_pausa_ate: return False
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
            inicio = max(0, len(self.historico_entradas) - self.rodadas_na_sessao)
            dados_sessao = {
                'acertos': self.acertos_sessao, 'erros': self.erros_sessao,
                'taxa_acerto': round(taxa, 1), 'total_rodadas': self.rodadas_na_sessao,
                'rodadas_por_sessao': self.rodadas_por_sessao
            }
            self.gerenciador_sessoes.salvar_sessao_encerrada(
                self.total_sessoes, dados_sessao, self.historico_entradas[inicio:]
            )
        self.entrada_ativa = None
        salvar_sessao()

    def pode_processar(self):
        if not self.sessao_ativa:
            if self.sessao_pausa_ate and hora_brasilia() >= self.sessao_pausa_ate:
                self.sessao_pausa_ate = None
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
            lucky_numbers, lucky_multipliers = [], {}
            table_id, table_name = 'unknown', 'Manual'

        if nr is None or not validar_numero(nr): return

        self.numero_rodada += 1
        self.duzia_ai.adicionar(nr)
        self.historico_numeros.append(nr)
        self.ultimo_numero = nr

        if not self.pode_processar():
            salvar_sessao()
            return

        eh_raio = nr in lucky_numbers
        multiplicador = lucky_multipliers.get(nr, 0) if eh_raio else 0

        # Processar resultado da entrada ativa
        if self.entrada_ativa:
            duzia_real = get_duzia(nr)
            duzia_prevista = self.entrada_ativa.get('duzia_prevista')
            duzia_sec = self.entrada_ativa.get('duzia_sec_prevista')
            numeros_apostados = self.entrada_ativa.get('numeros_apostar', [])
            incluir_zero = self.entrada_ativa.get('incluir_zero', False)

            acerto_primaria = (duzia_real == duzia_prevista) if duzia_prevista and nr != 0 else False
            acerto_secundaria = (duzia_real == duzia_sec) if duzia_sec and nr != 0 else False
            acerto_numero_exato = nr in numeros_apostados if nr != 0 else False
            acerto_zero = nr == 0 and incluir_zero
            if acerto_zero: acerto_primaria = True

            if acerto_numero_exato: self.acertos_numero += 1
            elif nr != 0: self.erros_numero += 1
            if acerto_zero: self.acertos_zero += 1
            elif nr == 0: self.erros_zero += 1
            if acerto_primaria: self.acertos_duzia += 1
            elif acerto_secundaria: self.acertos_duzia += 0.5
            elif nr != 0: self.erros_duzia += 1

            acertou = acerto_primaria or acerto_secundaria
            self.rodadas_na_sessao += 1
            if acertou or acerto_zero: self.acertos_sessao += 1
            else: self.erros_sessao += 1

            self.duzia_ai.registrar_resultado(
                duzia_real, acertou, acerto_numero_exato, acerto_zero,
                table_id, eh_raio, multiplicador
            )
            for d in [self.performance_por_mesa, self.duzia_ai.performance_por_mesa]:
                d[table_id]['acertos' if (acertou or acerto_zero) else 'erros'] += 1
            hora = datetime.now().hour
            turno = "manhã" if 6 <= hora < 12 else "tarde" if 12 <= hora < 18 else "noite"
            for d in [self.performance_por_horario, self.duzia_ai.performance_por_horario]:
                d[turno]['acertos' if (acertou or acerto_zero) else 'erros'] += 1

            if acerto_zero: status = '🟢'
            elif acerto_numero_exato and eh_raio: status = '⚡'
            elif acerto_numero_exato: status = '🎯'
            elif acerto_primaria: status = '✅'
            elif acerto_secundaria: status = '🟡'
            else: status = '❌'

            self.historico_entradas.append({
                'rodada': self.numero_rodada,
                'hora': formatar_hora_brasilia(),
                'numero': nr,
                'duzia_real': duzia_real if nr != 0 else 0,
                'duzia_prevista': duzia_prevista,
                'duzia_sec_prevista': duzia_sec,
                'acerto_duzia': acertou,
                'acerto_numero': acerto_numero_exato,
                'acerto_zero': acerto_zero,
                'eh_raio': eh_raio,
                'multiplicador': multiplicador,
                'status': status,
                'confianca': self.entrada_ativa.get('confianca', 0),
                'fonte_ml': self.entrada_ativa.get('fonte_ml', 'ML'),
                'modo_anti_erro': self.entrada_ativa.get('modo_anti_erro', False),
                'incluir_zero': incluir_zero,
                'table_id': table_id,
                'table_name': table_name
            })
            if len(self.historico_entradas) > 50:
                self.historico_entradas = self.historico_entradas[-50:]

            _enviar_resultado_auto(nr, acertou, acerto_numero_exato, acerto_zero, eh_raio, multiplicador)
            self.entrada_ativa = None
            if not self.pode_processar():
                salvar_sessao()
                return

        # Nova previsão
        if self.sessao_ativa and self.rodadas_na_sessao < self.rodadas_por_sessao:
            previsao = self.duzia_ai.prever()
            if previsao['entrar']:
                duzia_map = {1: list(range(1, 13)), 2: list(range(13, 25)), 3: list(range(25, 37))}
                numeros_principais = duzia_map.get(previsao['duzia'], [])
                numeros_secundarios = duzia_map.get(previsao.get('duzia_secundaria', previsao['duzia']), [])
                if st.session_state.get('modo_agressivo', False) and previsao.get('duzia_secundaria') and previsao['duzia_secundaria'] != previsao['duzia']:
                    numeros_apostar = list(set(numeros_principais + numeros_secundarios))
                else:
                    numeros_apostar = numeros_principais
                if previsao.get('incluir_zero') and 0 not in numeros_apostar:
                    numeros_apostar = [0] + numeros_apostar

                self.entrada_ativa = {
                    'numeros_apostar': numeros_apostar,
                    'duzia_prevista': previsao['duzia'],
                    'duzia_sec_prevista': previsao.get('duzia_secundaria'),
                    'confianca': previsao.get('confianca', 0),
                    'fonte_ml': previsao.get('fonte_ml', 'ML'),
                    'modo_anti_erro': previsao.get('modo_anti_erro', False),
                    'incluir_zero': previsao.get('incluir_zero', False)
                }
                self.duzia_ai.registrar_previsao(previsao['duzia'], previsao['confianca'])
                self.sinais_grafico.append((len(self.historico_numeros) - 1, previsao['duzia']))
                _enviar_previsao_auto(previsao, self.historico_numeros)

    def zerar(self):
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        self.acertos_duzia = self.erros_duzia = 0
        self.acertos_numero = self.erros_numero = 0
        self.acertos_zero = self.erros_zero = 0
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
        self.acertos_sessao = self.erros_sessao = 0
        janela = st.session_state.get('janela_duzia_ai', 30)
        self.duzia_ai = DuziaAI(window=janela, api_name=api_name)
        salvar_sessao()


# =============================
# INICIALIZAÇÃO DO APP STREAMLIT
# =============================
st.set_page_config(page_title="🎰 DuziaAI V12 - ML Ensemble", layout="wide")
st.title("🎰 DuziaAI V12 — Ensemble ML + Calibração (BRT)")

config_global = carregar_config_global()

def _init_session_state():
    defaults = {
        'api_selecionada': config_global.get('api_selecionada', 'XXXtreme Lightning'),
        'ultima_api': config_global.get('api_selecionada', 'XXXtreme Lightning'),
        'telegram_token': config_global.get('telegram_token', ''),
        'telegram_chat_id': config_global.get('telegram_chat_id', ''),
        'telegram_token_alt': config_global.get('telegram_token_alt', ''),
        'telegram_chat_id_alt': config_global.get('telegram_chat_id_alt', ''),
        'rodadas_por_sessao': config_global.get('rodadas_por_sessao', 10),
        'pausa_entre_sessoes': config_global.get('pausa_entre_sessoes', 5),
        'salvar_sessoes_auto': config_global.get('salvar_sessoes_auto', True),
        'modo_automatico': config_global.get('modo_automatico', True),
        'modo_agressivo': config_global.get('modo_agressivo', False),
        'janela_duzia_ai': config_global.get('janela_duzia_ai', 30),
        'historico': [],
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

_init_session_state()

def _carregar_sistema(api_name):
    """Cria e carrega sistema para a API selecionada."""
    sis = SistemaBot()
    dados = carregar_dados_persistidos(api_name)
    if dados:
        for n in dados.get('historico_numeros', []):
            sis.duzia_ai.adicionar(n)
            sis.historico_numeros.append(n)
        sis.numero_rodada = dados.get('numero_rodada', len(dados.get('historico_numeros', [])))
        for attr in ['acertos_duzia', 'erros_duzia', 'acertos_numero', 'erros_numero',
                     'acertos_zero', 'erros_zero', 'rodadas_na_sessao', 'sessao_ativa',
                     'total_sessoes', 'acertos_sessao', 'erros_sessao']:
            setattr(sis, attr, dados.get(attr, 0 if attr != 'sessao_ativa' else False))
        sis.entrada_ativa = dados.get('entrada_ativa')
        sis.historico_entradas = dados.get('historico_entradas', [])
        if dados.get('sessao_pausa_ate'):
            sis.sessao_pausa_ate = datetime.fromisoformat(dados['sessao_pausa_ate'])
        for key in ['performance_por_mesa', 'performance_por_horario']:
            if key in dados:
                dest = getattr(sis, key)
                ai_dest = getattr(sis.duzia_ai, key)
                for k, v in dados[key].items():
                    dest[k] = v
                    ai_dest[k] = v
        paths = get_session_paths(api_name)
        if os.path.exists(paths['historico']):
            with open(paths['historico'], 'r') as f:
                st.session_state.historico = json.load(f)
    return sis

# Gerenciar troca de API
if st.session_state.api_selecionada != st.session_state.ultima_api:
    st.session_state.ultima_api = st.session_state.api_selecionada
    st.session_state.sistema = _carregar_sistema(st.session_state.api_selecionada)
    st.rerun()

if "sistema" not in st.session_state:
    st.session_state.sistema = _carregar_sistema(st.session_state.api_selecionada)


# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.markdown("## ⚙️ V12 — ML Ensemble")
    sis = st.session_state.sistema

    # Status de sessão
    st.markdown("### 📊 Status da Sessão")
    if sis.sessao_ativa:
        st.success(f"🟢 Sessão #{sis.total_sessoes} ATIVA")
        st.progress(sis.rodadas_na_sessao / max(1, sis.rodadas_por_sessao))
        st.caption(f"Rodadas: {sis.rodadas_na_sessao}/{sis.rodadas_por_sessao} | ✅{sis.acertos_sessao} ❌{sis.erros_sessao}")
        if sis.acertos_sessao + sis.erros_sessao > 0:
            taxa = sis.acertos_sessao / (sis.acertos_sessao + sis.erros_sessao) * 100
            st.caption(f"Taxa sessão: {taxa:.0f}%")
    elif sis.sessao_pausa_ate and hora_brasilia() < sis.sessao_pausa_ate:
        t = (sis.sessao_pausa_ate - hora_brasilia()).seconds
        st.warning(f"⏸️ Pausa: {t//60:02d}:{t%60:02d}")
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
    st.markdown("### ⏱️ Configurações")
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

    # Status do ML V12
    ml_status = sis.duzia_ai.get_status_ml()
    st.markdown("### 🧠 Status ML V12")
    if ml_status['ativo']:
        st.success(f"✅ Ensemble ATIVO | {ml_status['amostras']} amostras")
        if ml_status['score_cv'] is not None:
            cv_pct = ml_status['score_cv'] * 100
            cor = "🟢" if cv_pct >= 50 else "🟡" if cv_pct >= 40 else "🔴"
            st.caption(f"{cor} CV Accuracy: {cv_pct:.1f}%")
        if ml_status['taxa_recente'] is not None:
            cor2 = "🟢" if ml_status['taxa_recente'] >= 60 else "🟡" if ml_status['taxa_recente'] >= 45 else "🔴"
            st.caption(f"{cor2} Taxa Recente (20): {ml_status['taxa_recente']}%")
        st.caption(f"Último treino: rodada {ml_status['ultimo_treino']}")
    else:
        rodada_atual = len(sis.duzia_ai.historico_completo)
        config = ROLETA_CONFIGS.get(st.session_state.api_selecionada, SETUP_BASE)
        min_para_treino = config.get('ml_janela_treino', 200) + config.get('janela_features_longa', 30) + 4
        faltam = max(0, min_para_treino - rodada_atual)
        if faltam > 0:
            st.info(f"🧠 Aguardando dados... ({rodada_atual}/{min_para_treino} rodadas)")
        else:
            st.warning(f"🧠 Treinando... ({rodada_atual} rodadas)")

    st.markdown("---")

    # Download sessões
    st.session_state.salvar_sessoes_auto = st.checkbox("💾 Salvar sessões automaticamente", value=st.session_state.salvar_sessoes_auto)
    with st.expander("📥 BAIXAR SESSÕES", expanded=False):
        api_name = st.session_state.get('api_selecionada', 'XXXtreme Lightning')
        gerenciador = GerenciadorSessoes(api_name)
        sessoes = gerenciador.listar_sessoes()
        if sessoes:
            st.caption(f"📂 {len(sessoes)} sessões")
            opcoes = [f"Sessão #{s.get('numero_sessao', '?')} - {s.get('data', '')} {s.get('hora_encerramento', '')}" for s in sessoes[:20]]
            sel = st.selectbox("Sessão:", opcoes, key="select_sessao")
            if sel:
                idx = opcoes.index(sel)
                if idx < len(sessoes):
                    s = sessoes[idx]
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(gerenciador.get_download_link(json.dumps(s, indent=2, ensure_ascii=False), f"sessao_{s.get('numero_sessao', '?')}.json"), unsafe_allow_html=True)
                    with c2:
                        st.markdown(gerenciador.get_download_link(gerenciador.gerar_csv_sessao(s), f"sessao_{s.get('numero_sessao', '?')}.csv", 'csv'), unsafe_allow_html=True)
                    stats = s.get('estatisticas', {})
                    st.caption(f"✅{stats.get('acertos', 0)} ❌{stats.get('erros', 0)} 📊{stats.get('taxa_acerto', 0)}%")
        else:
            st.info("Nenhuma sessão salva ainda.")

    st.markdown("---")
    st.markdown("### 🎰 Roleta")
    api_opcoes = list(API_URLS.keys())
    idx = api_opcoes.index(st.session_state.api_selecionada) if st.session_state.api_selecionada in api_opcoes else 0
    st.session_state.api_selecionada = st.radio("Roleta:", api_opcoes, index=idx)

    st.markdown("---")
    st.session_state.janela_duzia_ai = st.slider("📏 Janela de Análise", 10, 50, st.session_state.janela_duzia_ai, 5)
    st.session_state.modo_agressivo = st.checkbox("🔥 Modo Agressivo (2 Dúzias)", value=st.session_state.modo_agressivo)
    st.session_state.modo_automatico = st.checkbox("🤖 Modo Automático", value=st.session_state.modo_automatico)

    with st.expander("🔔 Telegram", expanded=False):
        st.session_state.telegram_token = st.text_input("Token Principal", value=st.session_state.telegram_token, type="password")
        st.session_state.telegram_chat_id = st.text_input("Chat ID Principal", value=st.session_state.telegram_chat_id)
        st.session_state.telegram_token_alt = st.text_input("Token Alternativo", value=st.session_state.telegram_token_alt, type="password")
        st.session_state.telegram_chat_id_alt = st.text_input("Chat ID Alternativo", value=st.session_state.telegram_chat_id_alt)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Salvar", use_container_width=True):
            paths = get_session_paths(st.session_state.api_selecionada)
            salvar_resultado_em_arquivo(st.session_state.historico, paths['historico'])
            salvar_sessao()
            st.success("✅ Salvos!")
    with c2:
        if st.button("📥 CSV", use_container_width=True):
            if exportar_historico_csv(st.session_state.sistema.historico_entradas):
                st.success("✅ CSV!")


# =============================
# CONTEÚDO PRINCIPAL
# =============================
st.subheader("🎲 Inserir Número")
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
                "table_id": "manual", "table_name": "Manual"
            })
            st.session_state.sistema.processar_novo_numero(nr)
            paths = get_session_paths(st.session_state.api_selecionada)
            salvar_resultado_em_arquivo(st.session_state.historico, paths['historico'])
            salvar_sessao()
            st.rerun()
        else:
            st.error("Número inválido (0-36)")
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

# Estatísticas
st.subheader(f"📊 ESTATÍSTICAS — {api_name}")
c1, c2, c3, c4, c5, c6 = st.columns(6)
total_duzias = int(sis.acertos_duzia + sis.erros_duzia)
tx_duzias = sis.acertos_duzia / total_duzias * 100 if total_duzias > 0 else 0
total_numeros = sis.acertos_numero + sis.erros_numero
tx_numeros = sis.acertos_numero / total_numeros * 100 if total_numeros > 0 else 0
c1.metric("🎯 Nº Exato", sis.acertos_numero, f"{tx_numeros:.0f}%")
c2.metric("✅ Acertos Dúzia", int(sis.acertos_duzia), f"{tx_duzias:.0f}%")
c3.metric("❌ Erros Dúzia", sis.erros_duzia)
c4.metric("🟢 Zeros", f"{sis.acertos_zero}/{sis.acertos_zero + sis.erros_zero}")
c5.metric("📦 Total", total_duzias)
c6.metric("🔴 Erros Cons.", sis.duzia_ai.erros_consecutivos)

if sis.total_sessoes > 0:
    st.markdown("---")
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("🔄 Rodadas", f"{sis.rodadas_na_sessao}/{sis.rodadas_por_sessao}")
    sc2.metric("✅ Acertos", sis.acertos_sessao)
    sc3.metric("❌ Erros", sis.erros_sessao)
    taxa_sessao = sis.acertos_sessao / max(1, sis.acertos_sessao + sis.erros_sessao) * 100
    sc4.metric("📊 Taxa", f"{taxa_sessao:.0f}%")
    if sis.sessao_ativa:
        st.progress(sis.rodadas_na_sessao / max(1, sis.rodadas_por_sessao))

st.markdown("---")
cg, ce = st.columns([3, 2])

with cg:
    st.subheader("📈 Análise ML V12")
    if len(sis.historico_numeros) >= 5:
        score, fonte = sis.duzia_ai.motor_ml.prever(sis.duzia_ai.historico_completo, sis.duzia_ai.numeros_completos)
        max_score = max(score.values())

        fig = plt.Figure(data=[plt.Bar(
            x=['D1 (1-12)', 'D2 (13-24)', 'D3 (25-36)'],
            y=[score[1], score[2], score[3]],
            marker_color=[
                '#FF6B6B' if score[d] == max_score else '#4ECDC4'
                for d in [1, 2, 3]
            ],
            text=[f'{score[d]:.1f}%' for d in [1, 2, 3]],
            textposition='auto'
        )])
        ml_status = sis.duzia_ai.get_status_ml()
        titulo = f"🎯 Ensemble ML ({fonte})"
        if ml_status['score_cv']:
            titulo += f" | CV: {ml_status['score_cv']*100:.1f}%"
        if sis.duzia_ai.alerta_zero_ativo:
            titulo += " | 🟢 ALERTA ZERO!"
        fig.update_layout(title=titulo, height=300, showlegend=False, yaxis_title="Probabilidade (%)", yaxis_range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

        # Gráfico de histórico de dúzias
        if len(sis.historico_numeros) >= 8:
            ult = list(sis.historico_numeros)[-20:]
            dz_hist = [get_duzia(n) for n in ult]
            fig2 = plt.Figure()
            fig2.add_trace(plt.Scatter(
                x=list(range(len(dz_hist))), y=dz_hist,
                mode='lines+markers', line=dict(color='#FFD700', width=2),
                marker=dict(size=10, color=['#FF6B6B' if d == 0 else '#FFD700' for d in dz_hist])
            ))
            if sis.sinais_grafico:
                sx, sy = [], []
                off = len(dz_hist) - 20
                for idx_s, dz in sis.sinais_grafico:
                    pos = idx_s - off
                    if 0 <= pos < 20:
                        sx.append(pos); sy.append(dz)
                if sx:
                    fig2.add_trace(plt.Scatter(
                        x=sx, y=sy, mode='markers', name='Sinal ML',
                        marker=dict(symbol='star', size=15, color='red')
                    ))
            fig2.update_layout(
                title="📉 Histórico de Dúzias (⭐ = sinal ML)",
                yaxis=dict(tickvals=[0, 1, 2, 3], ticktext=['Zero', 'D1', 'D2', 'D3'], range=[-0.5, 3.5]),
                height=280
            )
            st.plotly_chart(fig2, use_container_width=True)

        # 🆕 Calibração: gráfico de taxa de acerto por confiança
        hist_conf = sis.duzia_ai._historico_confiancas
        hist_acertos = sis.duzia_ai._historico_acertos_conf
        if len(hist_conf) >= 10:
            bins = [(0, 1), (1, 2), (2, 3), (3, 4)]
            labels, taxas = [], []
            for lo, hi in bins:
                idxs = [i for i, c in enumerate(hist_conf) if lo <= c < hi]
                if idxs:
                    taxa_bin = sum(hist_acertos[i] for i in idxs) / len(idxs) * 100
                    labels.append(f"{lo}-{hi}")
                    taxas.append(taxa_bin)
            if labels:
                fig3 = plt.Figure(data=[plt.Bar(
                    x=labels, y=taxas,
                    marker_color=['#00C851' if t >= 55 else '#FF4444' if t < 45 else '#FFD700' for t in taxas],
                    text=[f'{t:.0f}%' for t in taxas], textposition='auto'
                )])
                fig3.update_layout(
                    title="📊 Taxa Acerto por Faixa de Confiança",
                    yaxis_title="%", yaxis_range=[0, 100],
                    height=220, showlegend=False
                )
                st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Aguardando dados para análise ML... (mínimo 5 números)")

with ce:
    st.subheader("🎰 Entrada Atual")

    if sis.duzia_ai.alerta_zero_ativo:
        st.warning(f"⚠️ ALERTA ZERO! 🟢 ({sis.duzia_ai.rodadas_desde_zero} rodadas sem zero)")
    if sis.duzia_ai.em_pausa_pos_raio:
        st.warning(f"⏸️ Pausa pós-raio ({sis.duzia_ai.ultimo_raio_alto}x)")
    if sis.duzia_ai.erros_consecutivos >= 2:
        st.error(f"⚠️ {sis.duzia_ai.erros_consecutivos} erros consecutivos — confiança reduzida")

    if not sis.sessao_ativa:
        if sis.sessao_pausa_ate and hora_brasilia() < sis.sessao_pausa_ate:
            t = (sis.sessao_pausa_ate - hora_brasilia()).seconds
            st.info(f"⏸️ Próxima sessão em: {t//60:02d}:{t%60:02d}")
        else:
            st.info("🔴 Clique 'INICIAR SESSÃO' para começar")

    if sis.entrada_ativa and sis.sessao_ativa:
        e = sis.entrada_ativa
        conf = e.get('confianca', 0)
        dz_princ = e.get('duzia_prevista', 0)
        dz_sec = e.get('duzia_sec_prevista')
        fonte = e.get('fonte_ml', 'ML')
        cor = "#FF6347" if e.get('modo_anti_erro') else "#00CED1"
        badge_fonte = "🧠 Ensemble" if fonte == 'ensemble' else "📊 Freq.Bayesiana"
        st.markdown(f"""
        <div style="background:{cor}18; border:2px solid {cor}; border-radius:15px; padding:15px; text-align:center;">
            <h2 style="color:{cor};">🎯 Dúzia {dz_princ}</h2>
            <p style="font-size:1.1em;">Confiança: <b>{conf:.2f}</b></p>
            <p style="font-size:0.9em;">{badge_fonte}</p>
            {f'<p style="color:#FFA500;">🛡️ Cobertura: Dúzia {dz_sec}</p>' if dz_sec and dz_sec != dz_princ else ''}
        </div>
        """, unsafe_allow_html=True)
        melhores = _selecionar_melhores_numeros(dz_princ, list(sis.historico_numeros), 6)
        st.write(f"**🎲 6 melhores D{dz_princ}:** {', '.join(map(str, melhores))}")
        if dz_sec and dz_sec != dz_princ:
            mel2 = _selecionar_melhores_numeros(dz_sec, list(sis.historico_numeros), 6)
            st.write(f"**🛡️ 6 melhores D{dz_sec}:** {', '.join(map(str, mel2))}")
        st.progress(min(1.0, max(0.0, conf / 4.0)))
    else:
        st.info("🔍 Aguardando sinal do ML Ensemble...")

    if sis.ultimo_numero is not None:
        st.markdown("---")
        num_str = '🟢 ZERO' if sis.ultimo_numero == 0 else f'#{sis.ultimo_numero} (D{get_duzia(sis.ultimo_numero)})'
        st.write(f"**🔄 Último:** {num_str}")

    # Mini tabela de últimos números
    if len(sis.historico_numeros) >= 5:
        ultimos = list(sis.historico_numeros)[-10:]
        nums_fmt = []
        for n in reversed(ultimos):
            if n == 0: nums_fmt.append("🟢")
            elif 1 <= n <= 12: nums_fmt.append(f"**{n}**(D1)")
            elif 13 <= n <= 24: nums_fmt.append(f"**{n}**(D2)")
            else: nums_fmt.append(f"**{n}**(D3)")
        st.markdown("**📋 Recentes:** " + " · ".join(nums_fmt))

st.markdown("---")
st.subheader("📝 Histórico de Entradas")
if sis.historico_entradas:
    dados_tabela = []
    for e in reversed(sis.historico_entradas[-15:]):
        real = f"D{e.get('duzia_real', 0)}" if e.get('duzia_real', 0) != 0 else "Zero"
        prev = f"D{e.get('duzia_prevista', '?')}"
        cob = f"D{e.get('duzia_sec_prevista', '?')}" if e.get('duzia_sec_prevista') and e.get('duzia_sec_prevista') != e.get('duzia_prevista') else "-"
        num = e.get('numero', 0)
        num_str = f"⚡{num}({e.get('multiplicador', 0)}x)" if e.get('eh_raio') else ("🟢" if num == 0 else str(num))
        dados_tabela.append({
            "Rod": e.get('rodada'), "Hora": e.get('hora'),
            "🎲": num_str, "Real": real, "Prev": prev, "Cob": cob,
            "Conf": f"{e.get('confianca', 0):.2f}",
            "Fonte": e.get('fonte_ml', 'ML')[:8],
            "Z": '🟢' if e.get('incluir_zero') else '-',
            "Duz": '✅' if e.get('acerto_duzia') else '❌',
            "Nº": '🎯' if e.get('acerto_numero') else '-',
            "Zer": '🟢' if e.get('acerto_zero') else '-',
        })
    st.dataframe(dados_tabela, use_container_width=True, height=300)
    if st.button("📥 Exportar CSV completo", use_container_width=True):
        if exportar_historico_csv(sis.historico_entradas):
            st.success("✅ CSV exportado!")
else:
    st.info("Nenhuma entrada registrada ainda.")

st.markdown("---")
col_t1, col_t2 = st.columns(2)
with col_t1:
    if st.session_state.telegram_token and st.session_state.telegram_chat_id:
        st.success("🔔 Telegram Principal: ATIVO")
    else:
        st.warning("🔔 Telegram Principal: não configurado")
with col_t2:
    if st.session_state.telegram_token_alt and st.session_state.telegram_chat_id_alt:
        st.success("📢 Telegram Alt.: ATIVO")
    else:
        st.warning("📢 Telegram Alt.: não configurado")

st.caption(f"🤖 DuziaAI V12 | Ensemble: RF + GBoost + LR | Calibrado | 40 Features | {api_name} | {formatar_hora_brasilia()}")
salvar_sessao()
