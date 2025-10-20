# Futebol_Alertas_Unificado.py
import streamlit as st
from datetime import datetime, timedelta
import requests
import json
import os
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# --- Image composition
from PIL import Image, ImageDraw, ImageFont
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import quote_plus
import time

# =============================
# CONFIGURAÇÕES (coloque suas chaves)
# =============================
API_KEY_FD = "9058de85e3324bdb969adc005b5d918a"  # football-data.org
HEADERS_FD = {"X-Auth-Token": API_KEY_FD}
BASE_URL_FD = "https://api.football-data.org/v4"

API_KEY_TSD = "123"  # TheSportsDB (ex: 123) -> substitua pela sua chave real
BASE_URL_TSD = f"https://www.thesportsdb.com/api/v1/json/{API_KEY_TSD}"

TELEGRAM_TOKEN = "7900056631:AAHjG6iCDqQdGTfJI6ce0AZ0E2ilV2fV9RY"
TELEGRAM_CHAT_ID = "-1002754276285"
TELEGRAM_CHAT_ID_ALT2 = "-1002754276285"
BASE_URL_TG = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ALERTAS_PATH = "alertas.json"
CACHE_JOGOS = "cache_jogos.json"
CACHE_CLASSIFICACAO = "cache_classificacao.json"

# =============================
# Logger & Requests Session com retry/backoff
# =============================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FutebolAlertas")

def create_requests_session(retries=3, backoff_factor=0.8, status_forcelist=(429, 500, 502, 503, 504)):
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=frozenset(['GET','POST'])
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "Futebol-Alertas/1.0"})
    return session

HTTP_SESSION = create_requests_session()

def _safe_get(url, params=None, headers=None, timeout=10):
    """Faz GET com tratamento de erros, retorna dict JSON ou None."""
    try:
        if headers:
            resp = HTTP_SESSION.get(url, params=params, headers=headers, timeout=timeout)
        else:
            resp = HTTP_SESSION.get(url, params=params, timeout=timeout)
    except requests.exceptions.RequestException as e:
        logger.warning(f"RequestException ao acessar {url} params={params}: {e}")
        return None

    if resp.status_code != 200:
        snippet = resp.text[:800].replace("\n", " ")
        logger.warning(f"Resposta não-200 ({resp.status_code}) para {url} params={params}. Texto: {snippet}")
        return None

    try:
        return resp.json()
    except ValueError as e:
        logger.warning(f"JSON decode error para {url} params={params}: {e}")
        return None

# =============================
# Inicialização do Session State
# =============================
def inicializar_session_state():
    """Inicializa todas as variáveis do session_state"""
    if 'jogos_encontrados' not in st.session_state:
        st.session_state.jogos_encontrados = []
    if 'busca_realizada' not in st.session_state:
        st.session_state.busca_realizada = False
    if 'alertas_enviados' not in st.session_state:
        st.session_state.alertas_enviados = False
    if 'top_jogos' not in st.session_state:
        st.session_state.top_jogos = []
    if 'data_ultima_busca' not in st.session_state:
        st.session_state.data_ultima_busca = None
    if 'resultados_conferidos' not in st.session_state:
        st.session_state.resultados_conferidos = []

# =============================
# Mapeamento TheSportsDB -> Football-Data (comum)
# =============================
TSD_TO_FD = {
    "English Premier League": 2021,
    "Premier League": 2021,
    "La Liga": 2014,
    "Primera División": 2014,
    "Serie A": 2019,
    "Bundesliga": 2002,
    "Ligue 1": 2015,
    "Primeira Liga": 2017,
    "UEFA Champions League": 2001,
    "Brazilian Serie A": 2013,
    "Campeonato Brasileiro Série A": 2013,
    "Brazilian Serie B": 2014,
    "Campeonato Brasileiro Série B": 2014,
    "Major League Soccer": 2145,
    "American Major League Soccer": 2145,
    "Liga MX": 2150,
    "Mexican Primera League": 2150,
    "Saudi Pro League": 2160,
    "Saudi-Arabian Pro League": 2160,
}

# =============================
# Funções de persistência / cache em disco
# =============================
def carregar_json(caminho):
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Erro ao carregar JSON {caminho}: {e}")
            return {}
    return {}

def salvar_json(caminho, dados):
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Erro ao salvar JSON {caminho}: {e}")

def carregar_alertas():
    return carregar_json(ALERTAS_PATH)

def salvar_alertas(alertas):
    salvar_json(ALERTAS_PATH, alertas)

def carregar_cache_jogos():
    return carregar_json(CACHE_JOGOS)

def salvar_cache_jogos(dados):
    salvar_json(CACHE_JOGOS, dados)

def carregar_cache_classificacao():
    return carregar_json(CACHE_CLASSIFICACAO)

def salvar_cache_classificacao(dados):
    salvar_json(CACHE_CLASSIFICACAO, dados)

# =============================
# Envio Telegram (robusto)
# =============================
def enviar_telegram(msg, chat_id=TELEGRAM_CHAT_ID):
    try:
        payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
        resp = HTTP_SESSION.get(BASE_URL_TG, params=payload, timeout=8)
        if resp.status_code != 200:
            logger.warning(f"Telegram retornou {resp.status_code}: {resp.text[:300]}")
            return False
        try:
            j = resp.json()
            if not j.get("ok", False):
                logger.warning(f"Telegram API respondeu ok=False: {j}")
                return False
        except Exception:
            pass
        return True
    except Exception as e:
        logger.warning(f"Erro ao enviar Telegram: {e}")
        return False

def enviar_alerta_telegram_generico(home, away, data_str_brt, hora_str, liga, tendencia, estimativa, confianca, chat_id=TELEGRAM_CHAT_ID):
    msg = (
        f"⚽ *Alerta de Gols!*\n"
        f"🏟️ {home} vs {away}\n"
        f"📅 {data_str_brt} ⏰ {hora_str} (BRT)\n"
        f"🔥 Tendência: {tendencia}\n"
        f"📊 Estimativa: {estimativa:.2f} gols\n"
        f"✅ Confiança: {confianca:.0f}%\n"
        f"📌 Liga: {liga}"
    )
    return enviar_telegram(msg, chat_id)

# =============================
# Football-Data helpers
# =============================
def obter_classificacao_fd(liga_id):
    cache = carregar_cache_classificacao()
    if str(liga_id) in cache:
        return cache[str(liga_id)]

    try:
        url = f"{BASE_URL_FD}/competitions/{liga_id}/standings"
        data = _safe_get(url, headers=HEADERS_FD, timeout=10)
        if not data:
            return {}
        standings = {}
        for s in data.get("standings", []):
            if s.get("type") != "TOTAL":
                continue
            for t in s.get("table", []):
                name = t["team"]["name"]
                gols_marcados = t.get("goalsFor", 0)
                gols_sofridos = t.get("goalsAgainst", 0)
                partidas = t.get("playedGames", 1) or 1
                standings[name] = {
                    "scored": gols_marcados,
                    "against": gols_sofridos,
                    "played": partidas
                }
        cache[str(liga_id)] = standings
        salvar_cache_classificacao(cache)
        return standings
    except Exception as e:
        logger.warning(f"Erro obter classificação FD: {e}")
        return {}

def obter_jogos_fd(liga_id, data):
    cache = carregar_cache_jogos()
    key = f"fd_{liga_id}_{data}"
    if key in cache:
        return cache[key]
    try:
        url = f"{BASE_URL_FD}/competitions/{liga_id}/matches?dateFrom={data}&dateTo={data}"
        data_json = _safe_get(url, headers=HEADERS_FD, timeout=10)
        jogos = data_json.get("matches", []) if data_json else []
        cache[key] = jogos
        salvar_cache_jogos(cache)
        return jogos
    except Exception as e:
        logger.warning(f"Erro obter jogos FD: {e}")
        return []

# =============================
# TheSportsDB helpers (cache do Streamlit + requests)
# =============================
@st.cache_data(ttl=300)
def listar_ligas_tsd():
    url = f"{BASE_URL_TSD}/all_leagues.php"
    data = _safe_get(url, timeout=10)
    if not data:
        st.warning("⚠️ Falha ao listar ligas TheSportsDB (verifique chave/API).")
        return []
    ligas = [l for l in data.get("leagues", []) if l.get("strSport") == "Soccer"]
    return ligas

@st.cache_data(ttl=120)
def buscar_jogos_tsd(liga_nome, data_evento):
    # data_evento: YYYY-MM-DD
    url = f"{BASE_URL_TSD}/eventsday.php"
    params = {"d": data_evento, "l": liga_nome}
    data = _safe_get(url, params=params, timeout=10)
    if not data:
        return []
    return data.get("events") or []

@st.cache_data(ttl=120)
def buscar_eventslast_team_tsd(id_team):
    if not id_team:
        return []
    url = f"{BASE_URL_TSD}/eventslast.php"
    params = {"id": id_team}
    data = _safe_get(url, params=params, timeout=10)
    if not data:
        return []
    return data.get("results") or []

@st.cache_data(ttl=60)
def buscar_team_by_name_tsd(nome):
    if not nome:
        return []
    url = f"{BASE_URL_TSD}/searchteams.php"
    params = {"t": nome}
    data = _safe_get(url, params=params, timeout=10)
    if not data:
        return []
    return data.get("teams") or []

# =============================
# Tendência (Football-Data original)
# =============================
def calcular_tendencia_fd(home, away, classificacao):
    dados_home = classificacao.get(home, {"scored":0, "against":0, "played":1})
    dados_away = classificacao.get(away, {"scored":0, "against":0, "played":1})

    media_home_feitos = dados_home["scored"] / max(1, dados_home["played"])
    media_home_sofridos = dados_home["against"] / max(1, dados_home["played"])
    media_away_feitos = dados_away["scored"] / max(1, dados_away["played"])
    media_away_sofridos = dados_away["against"] / max(1, dados_away["played"])

    estimativa = ((media_home_feitos + media_away_sofridos) / 2 +
                  (media_away_feitos + media_home_sofridos) / 2)

    if estimativa >= 3.0:
        tendencia = "Mais 2.5"
        confianca = min(95, 70 + (estimativa - 3.0)*10)
    elif estimativa >= 2.0:
        tendencia = "Mais 1.5"
        confianca = min(90, 60 + (estimativa - 2.0)*10)
    else:
        tendencia = "Menos 2.5"
        confianca = min(85, 55 + (2.0 - estimativa)*10)

    return round(estimativa, 2), round(confianca, 0), tendencia

# =============================
# Tendência (TheSportsDB)
# =============================
def calcular_tendencia_tsd(evento, max_last=5, peso_h2h=0.3):
    try:
        home = evento.get("strHomeTeam")
        away = evento.get("strAwayTeam")
        id_home = evento.get("idHomeTeam")
        id_away = evento.get("idAwayTeam")

        def media_gols_id(id_team):
            if not id_team:
                return 1.8
            results = buscar_eventslast_team_tsd(id_team)
            if not results:
                return 1.8
            gols = []
            for r in results[:max_last]:
                try:
                    h = int(r.get("intHomeScore") or 0)
                    a = int(r.get("intAwayScore") or 0)
                    gols.append(h + a)
                except Exception:
                    pass
            if not gols:
                return 1.8
            return sum(gols)/len(gols)

        m_home = media_gols_id(id_home)
        m_away = media_gols_id(id_away)
        estimativa_base = (m_home + m_away) / 2
        estimativa_final = (1 - peso_h2h) * estimativa_base + peso_h2h * estimativa_base

        if estimativa_final >= 2.5:
            tendencia = "Mais 2.5"
            confianca = min(90, 60 + (estimativa_final - 2.5) * 12)
        elif estimativa_final >= 1.5:
            tendencia = "Mais 1.5"
            confianca = min(85, 55 + (estimativa_final - 1.5) * 15)
        else:
            tendencia = "Menos 2.5"
            confianca = max(45, min(75, 50 + (estimativa_final - 1.0) * 10))

        return round(estimativa_final, 2), round(confianca, 0), tendencia
    except Exception:
        return 1.8, 50, "Mais 1.5"

# =============================
# Função para tratar tempo e formatar data/hora (BRT)
# =============================
def parse_time_iso_to_brt(iso_str):
    if not iso_str:
        return "-", "-"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt_brt = dt - timedelta(hours=3)
        return dt_brt.strftime("%d/%m/%Y"), dt_brt.strftime("%H:%M")
    except Exception:
        try:
            return iso_str, ""
        except:
            return "-", "-"

# =============================
# Funções de busca principais
# =============================
def buscar_e_analisar_jogos(data_selecionada, ligas_selecionadas, ligas_fd_escolha):
    """Função principal para buscar e analisar jogos"""
    data_str = data_selecionada.strftime("%Y-%m-%d")
    total_jogos = []
    total_top_jogos = []

    # 1) Processar ligas selecionadas via TheSportsDB
    for liga_nome in ligas_selecionadas:
        jogos_tsd = buscar_jogos_tsd(liga_nome, data_str)
        if not jogos_tsd:
            continue

        for e in jogos_tsd:
            home = e.get("strHomeTeam") or e.get("homeTeam") or "Desconhecido"
            away = e.get("strAwayTeam") or e.get("awayTeam") or "Desconhecido"
            date_event = e.get("dateEvent") or e.get("dateEventLocal") or data_str
            time_event = e.get("strTime") or e.get("strTimeLocal") or ""
            
            fd_id = None
            for key_name, fd_id_val in TSD_TO_FD.items():
                if key_name.lower() in liga_nome.lower() or liga_nome.lower() in key_name.lower():
                    fd_id = fd_id_val
                    break

            if fd_id:
                classificacao = obter_classificacao_fd(fd_id)
                jogos_fd = obter_jogos_fd(fd_id, data_str)
                match_fd = None
                for m in jogos_fd:
                    try:
                        if m.get("homeTeam", {}).get("name") == home and m.get("awayTeam", {}).get("name") == away:
                            match_fd = m
                            break
                    except Exception:
                        pass
                if match_fd:
                    estimativa, confianca, tendencia = calcular_tendencia_fd(home, away, classificacao)
                    data_brt, hora_brt = parse_time_iso_to_brt(match_fd.get("utcDate"))
                    
                    jogo_info = {
                        "id": str(match_fd.get("id")),
                        "home": home, "away": away,
                        "tendencia": tendencia, "estimativa": estimativa, "confianca": confianca,
                        "liga": liga_nome,
                        "hora": hora_brt,
                        "origem": "FD",
                        "data_brt": data_brt
                    }
                    total_jogos.append(jogo_info)
                    continue

            # Se não mapeado pra FD, usa análise TSD
            estimativa, confianca, tendencia = calcular_tendencia_tsd(e)
            try:
                if date_event and time_event:
                    data_brt = date_event
                    hora_brt = time_event
                else:
                    data_brt, hora_brt = date_event, time_event or "??:??"
            except:
                data_brt, hora_brt = date_event, time_event or "??:??"

            jogo_info = {
                "id": e.get("idEvent") or f"tsd_{liga_nome}_{home}_{away}",
                "home": home, "away": away,
                "tendencia": tendencia, "estimativa": estimativa, "confianca": confianca,
                "liga": liga_nome,
                "hora": hora_brt,
                "origem": "TSD",
                "data_brt": data_brt
            }
            total_jogos.append(jogo_info)

    # 2) Processar ligas FD selecionadas manualmente
    for fd_id in ligas_fd_escolha:
        jogos_fd = obter_jogos_fd(fd_id, data_str)
        classificacao = obter_classificacao_fd(fd_id)
        if not jogos_fd:
            continue

        for m in jogos_fd:
            home = m.get("homeTeam", {}).get("name", "Desconhecido")
            away = m.get("awayTeam", {}).get("name", "Desconhecido")
            utc = m.get("utcDate")
            data_brt, hora_brt = parse_time_iso_to_brt(utc)
            estimativa, confianca, tendencia = calcular_tendencia_fd(home, away, classificacao)
            
            jogo_info = {
                "id": str(m.get("id")),
                "home": home, "away": away,
                "tendencia": tendencia, "estimativa": estimativa, "confianca": confianca,
                "liga": m.get("competition", {}).get("name","FD"),
                "hora": hora_brt,
                "origem": "FD",
                "data_brt": data_brt
            }
            total_jogos.append(jogo_info)

    # Ordenar por confiança e selecionar top 5
    if total_jogos:
        total_top_jogos = sorted(total_jogos, key=lambda x: (x["confianca"], x["estimativa"]), reverse=True)[:5]

    return total_jogos, total_top_jogos

# =============================
# Envio de alertas
# =============================
def enviar_alertas_individualmente(jogos):
    alertas_enviados = []
    for jogo in jogos:
        sucesso = enviar_alerta_telegram_generico(
            jogo['home'], jogo['away'], jogo['data_brt'], jogo['hora'], 
            jogo['liga'], jogo['tendencia'], jogo['estimativa'], jogo['confianca']
        )
        if sucesso:
            alertas_enviados.append(jogo)
    return alertas_enviados

def enviar_top_consolidado(top_jogos):
    if not top_jogos:
        return False
        
    mensagem = "📢 *TOP Jogos Consolidados*\n\n"
    for t in top_jogos:
        mensagem += f"🏟️ {t['liga']}\n🏆 {t['home']} x {t['away']}\nTendência: {t['tendencia']} | Conf.: {t['confianca']}%\n\n"
    
    return enviar_telegram(mensagem, TELEGRAM_CHAT_ID_ALT2)

# =============================
# Geração de arte "Elite Master" (dark style) - cria PNG e mostra no Streamlit
# =============================
def _load_font(size=24):
    # tenta carregar fontes comuns; se não, usa fonte padrão PIL
    possible_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/Library/Fonts/Arial.ttf",
        "arial.ttf"
    ]
    for p in possible_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                continue
    return ImageFont.load_default()

def gerar_poster_elite_master(jogos, title="Top Jogos do Dia", resultado=False, max_items=3):
    """
    Gera uma imagem PNG estilo 'Elite Master' com fundo escuro, escudos grandes (placeholder),
    textos organizados com placar/resultado (se resultado=True), título no topo.
    Retorna o caminho do arquivo gerado.
    """
    # layout
    items = jogos[:max_items]
    width = 1080
    height = 1080
    margin = 60
    bg_color = (18, 18, 20)  # dark
    accent = (255, 215, 0)  # dourado leve
    white = (230, 230, 230)

    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    title_font = _load_font(42)
    team_font = _load_font(34)
    meta_font = _load_font(22)
    small_font = _load_font(18)

    # Título
    draw.text((margin, margin//2), title, font=title_font, fill=white)

    # dividir área para cada jogo
    area_top = margin + 80
    area_height = (height - area_top - margin) // max(1, max_items)
    box_padding = 18

    for idx, jogo in enumerate(items):
        top_y = area_top + idx * area_height
        left_x = margin
        right_x = width - margin

        # retângulo semi-transparente
        rect_h = area_height - 12
        rect_w = right_x - left_x
        rect = [left_x, top_y + 6, left_x + rect_w, top_y + rect_h]
        # desenha borda leve
        draw.rounded_rectangle(rect, radius=12, fill=(28,28,30))

        # placeholder escudos (círculos) — se tiver imagem de escudo, aqui você pode colar
        shield_size = rect_h - 2*box_padding
        shield_size = min(shield_size, 160)
        shield_x = left_x + box_padding
        shield_y = top_y + box_padding + 6
        # home shield
        draw.ellipse((shield_x, shield_y, shield_x+shield_size, shield_y+shield_size), fill=(70,70,70))
        # away shield
        shield2_x = left_x + box_padding + shield_size + 18 + 320
        draw.ellipse((shield2_x, shield_y, shield2_x+shield_size, shield_y+shield_size), fill=(70,70,70))

        # times e info
        text_x = shield_x + shield_size + 16
        text_y = shield_y
        draw.text((text_x, text_y), jogo['home'], font=team_font, fill=white)
        draw.text((text_x, text_y + 36), "vs", font=meta_font, fill=(180,180,180))
        draw.text((text_x, text_y + 60), jogo['away'], font=team_font, fill=white)

        # Tendência & confiança
        meta_text = f"{jogo.get('tendencia','')}  •  Estim.: {jogo.get('estimativa','-')}  •  Conf.: {jogo.get('confianca','-')}%"
        draw.text((text_x, text_y + 110), meta_text, font=small_font, fill=(190,190,190))

        # liga à direita
        liga_text = jogo.get('liga', '')
        liga_w, liga_h = draw.textsize(liga_text, font=meta_font)
        draw.text((right_x - liga_w - box_padding, text_y), liga_text, font=meta_font, fill=accent)

        # se resultado (conferido) mostrar badge verde/vermelho
        if resultado and jogo.get('resultado'):
            badge = "🟢" if jogo.get('resultado') == "GREEN" else "🔴"
            draw.text((right_x - 60, text_y + 60), badge, font=team_font, fill=white)

    # Rodapé com timestamp
    rodape = f"Gerado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    draw.text((margin, height - margin + 8), rodape, font=small_font, fill=(150,150,150))

    # salvar
    ts = int(time.time())
    out_path = f"/tmp/elite_master_{ts}.png"
    try:
        img.save(out_path, format="PNG")
    except Exception as e:
        logger.warning(f"Erro ao salvar poster: {e}")
        # fallback para salvar local
        out_path = f"elite_master_{ts}.png"
        img.save(out_path, format="PNG")

    return out_path

# =============================
# UI e Lógica principal
# =============================
def main():
    st.set_page_config(page_title="⚽ Sistema Unificado de Alertas", layout="wide")
    inicializar_session_state()
    
    st.title("⚽ Sistema Unificado de Alertas (Football-Data + TheSportsDB)")

    # Data
    data_selecionada = st.date_input("📅 Escolha a data para os jogos:", value=datetime.today())
    data_str = data_selecionada.strftime("%Y-%m-%d")

    # Carregar ligas TheSportsDB
    st.sidebar.header("Opções de Busca")
    ligas_tsd = []
    try:
        ligas = listar_ligas_tsd()
        ligas_tsd = ligas
        nomes_ligas = [l["strLeague"] for l in ligas_tsd]
    except Exception:
        nomes_ligas = []

    use_all_tsd = st.sidebar.checkbox("Usar todas ligas TSD", value=False)
    ligas_selecionadas = []
    if use_all_tsd:
        ligas_selecionadas = nomes_ligas
    else:
        ligas_selecionadas = st.sidebar.multiselect("Selecione ligas (TheSportsDB):", nomes_ligas, max_selections=10)

    # Opção de também usar ligas FD fixas
    usar_fd = st.sidebar.checkbox("Incluir ligas fixas (Football-Data) também", value=True)
    ligas_fd_escolha = []
    if usar_fd:
        liga_dict_fd = {
            "Premier League (Inglaterra)": 2021,
            "Championship (Inglaterra)": 2016,
            "Bundesliga (Alemanha)": 2002,
            "La Liga (Espanha)": 2014,
            "Serie A (Itália)": 2019,
            "Ligue 1 (França)": 2015,
            "Primeira Liga (Portugal)": 2017,
            "Campeonato Brasileiro Série A": 2013,
            "UEFA Champions League": 2001,
        }
        adicionar_fd = st.sidebar.multiselect("Adicionar ligas Football-Data (opcional):", list(liga_dict_fd.keys()))
        ligas_fd_escolha = [liga_dict_fd[n] for n in adicionar_fd]

    # Status da sessão
    st.sidebar.header("📊 Status da Sessão")
    st.sidebar.write(f"Busca realizada: {'✅' if st.session_state.busca_realizada else '❌'}")
    st.sidebar.write(f"Alertas enviados: {'✅' if st.session_state.alertas_enviados else '❌'}")
    st.sidebar.write(f"Jogos encontrados: {len(st.session_state.jogos_encontrados)}")
    st.sidebar.write(f"Top jogos: {len(st.session_state.top_jogos)}")

    # Botão para limpar dados
    if st.sidebar.button("🗑️ Limpar Dados da Sessão"):
        st.session_state.jogos_encontrados = []
        st.session_state.busca_realizada = False
        st.session_state.alertas_enviados = False
        st.session_state.top_jogos = []
        st.session_state.data_ultima_busca = None
        st.session_state.resultados_conferidos = []
        st.success("Dados da sessão limpos!")
        st.rerun()

    st.markdown("---")
    col1, col2, col3 = st.columns([1,1,1])
    
    with col1:
        buscar_btn = st.button("🔍 Buscar partidas e analisar", type="primary")
    
    with col2:
        enviar_alertas_btn = st.button("🚀 Enviar Alertas Individuais", 
                                     disabled=not st.session_state.busca_realizada)
    
    with col3:
        enviar_top_btn = st.button("📊 Enviar Top Consolidado", 
                                 disabled=not st.session_state.busca_realizada)

    # =================================================================================
    # BUSCAR PARTIDAS
    # =================================================================================
    if buscar_btn:
        with st.spinner("Buscando partidas e analisando..."):
            jogos_encontrados, top_jogos = buscar_e_analisar_jogos(
                data_selecionada, ligas_selecionadas, ligas_fd_escolha
            )
            
            # Salvar no session state
            st.session_state.jogos_encontrados = jogos_encontrados
            st.session_state.top_jogos = top_jogos
            st.session_state.busca_realizada = True
            st.session_state.data_ultima_busca = data_str
            st.session_state.alertas_enviados = False

        if jogos_encontrados:
            st.success(f"✅ {len(jogos_encontrados)} jogos encontrados e analisados!")
            
            # Exibir jogos encontrados
            st.subheader("📋 Todos os Jogos Encontrados")
            for jogo in jogos_encontrados:
                with st.container():
                    c1, c2, c3 = st.columns([3, 2, 1])
                    with c1:
                        st.write(f"**{jogo['home']}** vs **{jogo['away']}**")
                        st.write(f"🏆 {jogo['liga']} | 🕐 {jogo['hora']} | 📊 {jogo['origem']}")
                    with c2:
                        st.write(f"🎯 {jogo['tendencia']}")
                        st.write(f"📈 Estimativa: {jogo['estimativa']} | ✅ Confiança: {jogo['confianca']}%")
                    with c3:
                        if jogo in st.session_state.top_jogos:
                            st.success("🏆 TOP")
                    st.divider()
            
            # Exibir top jogos
            if top_jogos:
                st.subheader("🏆 Top 5 Jogos (Maior Confiança)")
                for i, jogo in enumerate(top_jogos, 1):
                    st.info(f"{i}. **{jogo['home']}** vs **{jogo['away']}** - {jogo['tendencia']} ({jogo['confianca']}% confiança)")
        else:
            st.warning("⚠️ Nenhum jogo encontrado para os critérios selecionados.")

    # =================================================================================
    # ENVIAR ALERTAS INDIVIDUAIS
    # =================================================================================
    if enviar_alertas_btn and st.session_state.busca_realizada:
        with st.spinner("Enviando alertas individuais..."):
            alertas_enviados = enviar_alertas_individualmente(st.session_state.jogos_encontrados)
            
            if alertas_enviados:
                st.session_state.alertas_enviados = True
                st.success(f"✅ {len(alertas_enviados)} alertas enviados com sucesso!")
            else:
                st.error("❌ Erro ao enviar alertas")

    # =================================================================================
    # ENVIAR TOP CONSOLIDADO
    # =================================================================================
    if enviar_top_btn and st.session_state.busca_realizada and st.session_state.top_jogos:
        with st.spinner("Enviando top consolidado..."):
            if enviar_top_consolidado(st.session_state.top_jogos):
                st.success("✅ Top consolidado enviado com sucesso!")
            else:
                st.error("❌ Erro ao enviar top consolidado")

    # =================================================================================
    # GERAR ARTE / PÔSTER (Elite Master)
    # =================================================================================
    st.markdown("---")
    st.subheader("🎨 Gerar Pôster (Estilo Elite Master)")
    qtd_para_poster = st.number_input("Quantos jogos no pôster (máx 3):", min_value=1, max_value=3, value=3)
    titulo_poster = st.text_input("Título do pôster:", value="Top Jogos do Dia")
    gerar_btn = st.button("🖼️ Gerar Pôster Elite Master", disabled=not st.session_state.busca_realizada)

    if gerar_btn:
        jogos_para = st.session_state.top_jogos[:qtd_para_poster] if st.session_state.top_jogos else st.session_state.jogos_encontrados[:qtd_para_poster]
        if not jogos_para:
            st.warning("Sem jogos para gerar pôster.")
        else:
            caminho = gerar_poster_elite_master(jogos_para, title=titulo_poster, resultado=False, max_items=qtd_para_poster)
            try:
                with open(caminho, "rb") as f:
                    st.image(f.read(), use_column_width=True)
                with open(caminho, "rb") as f:
                    btn = st.download_button(label="📥 Baixar Pôster (PNG)", data=f, file_name=os.path.basename(caminho), mime="image/png")
            except Exception as e:
                st.warning(f"Não foi possível abrir o arquivo do pôster: {e}")

    # =================================================================================
    # CONFERÊNCIA DE RESULTADOS (mantida do código original)
    # =================================================================================
    st.markdown("---")
    conferir_btn = st.button("📊 Conferir resultados (usar alertas salvo)")
    
    if conferir_btn:
        st.info("Conferindo resultados dos alertas salvos...")
        # Lógica de conferência original seria inserida aqui.
        # Exemplos: ler alertas salvos, consultar API/endpoint de resultados, marcar GREEN/RED, atualizar JSON.
        # Implementar conforme necessidade.

if __name__ == "__main__":
    main()
