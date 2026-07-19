# -*- coding: utf-8 -*-
"""
gatilhos_numericos.py
======================
Módulo de gatilhos de entrada baseados em números/terminais da roleta europeia.

Implementa 20 gatilhos usados por jogadores que fazem "leitura de padrão":

Grupo 1 - terminais e proximidade na roda:
  1. Repetição de número          -> repete_numero
  2. Soma de terminal              -> soma_terminal
  3. Subtração de terminal         -> subtracao_terminal
  4. Vizinho de 0/10/20/30         -> vizinho_multiplos_dez
  5. Troca de crupiê (Voisins)     -> troca_crupie
  6. Sequência numérica            -> sequencia_numerica
  7. Multiplicação de terminal     -> multiplicacao_terminal
  8. Número quente em streak       -> numero_quente
  9. Setor da roda (Tiers/Orph.)   -> setor_roda
 10. Vizinho físico na roda        -> vizinho_fisico

Grupo 2 - relação entre números, layout da mesa e streaks de cor/paridade:
 11. Número espelho (dígitos invertidos) -> espelho_numero
 12. Fichas estáticas (conjunto fixo)     -> fichas_estaticas
 13. Número atrasado ("dormindo")         -> numero_atrasado
 14. Cavalo/split entre números recentes -> cavalo_numeros_recentes
 15. Quebra de sequência de cor           -> quebra_sequencia_cor
 16. Coluna ausente                       -> coluna_ausente
 17. Drift do rotor/bola                  -> drift_rotor
 18. Sequência par/ímpar                  -> sequencia_par_impar
 19. Assinatura de seção da roda (sessão) -> assinatura_secao_crupie
 20. Six line (linha dupla) do último nº  -> six_line_ultimo_numero

IMPORTANTE (deixa isso visível na UI, não só no código):
Em roleta com RNG cada rodada é matematicamente independente da anterior.
Estes gatilhos NÃO alteram a probabilidade real do próximo número. O que este
módulo faz é (a) detectar quando cada padrão ocorre e (b) medir, via backtest
contra o histórico real da sessão, qual gatilho teria acertado com que
frequência -- para dar ao usuário uma métrica honesta, não uma promessa.
"""

from collections import deque

# Ordem física dos números na roda europeia (37 casas, zero único)
RODA_EUROPEIA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8,
                 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]

_IDX_RODA = {n: i for i, n in enumerate(RODA_EUROPEIA)}

# Setores clássicos da roleta francesa/europeia
VOISINS_DU_ZERO = [22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25]
TIERS_DU_CYLINDRE = [27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33]
ORPHELINS = [17, 34, 6, 1, 20, 14, 31, 9]

# Cores padrão da mesa europeia
VERMELHOS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
PRETOS = {n for n in range(1, 37) if n not in VERMELHOS}

# As 3 arcadas físicas da roda (dividindo os 37 números em 3 blocos contíguos
# de ~12 na ordem física, para aproximar uma "seção" da roda por sessão)
_TERCO = len(RODA_EUROPEIA) // 3
ARCOS_RODA = [
    set(RODA_EUROPEIA[0:_TERCO + 1]),
    set(RODA_EUROPEIA[_TERCO + 1:2 * _TERCO + 1]),
    set(RODA_EUROPEIA[2 * _TERCO + 1:]),
]


def cor_numero(n):
    if n == 0:
        return None
    return 'vermelho' if n in VERMELHOS else 'preto'


def coluna_numero(n):
    """Coluna da mesa (1, 2 ou 3). 0 não pertence a nenhuma coluna."""
    if n == 0:
        return None
    resto = n % 3
    return 3 if resto == 0 else resto


def numeros_da_coluna(c):
    return [n for n in range(1, 37) if coluna_numero(n) == c]


def linha_numero(n):
    """Linha (1 a 12) da mesa: 1-2-3 é linha 1, 4-5-6 é linha 2, etc."""
    if n == 0:
        return None
    return (n - 1) // 3 + 1


def six_line_do_numero(n):
    """Bloco de 6 números (linha dupla) da mesa que contém `n`."""
    if n == 0:
        return []
    linha = linha_numero(n)
    linha_inicio = linha if linha % 2 == 1 else linha - 1
    inicio = (linha_inicio - 1) * 3 + 1
    return list(range(inicio, inicio + 6))


def _duzia_numero(n):
    if n == 0:
        return None
    if n <= 12:
        return 1
    if n <= 24:
        return 2
    return 3


def derivar_situacao_prevista(numeros_sugeridos, limiar_predominancia=0.7):
    """
    Resume uma lista de números sugeridos por um gatilho numa "situação"
    legível (dúzia, cor, coluna, paridade ou terminal predominante), para
    exibir e enviar como a previsão real da PRÓXIMA rodada -- não a lista
    crua de números. Só aponta uma característica quando ela é dominante
    o bastante no conjunto (>= limiar_predominancia); senão descreve como
    "números específicos".
    """
    nums = [n for n in numeros_sugeridos if 0 <= n <= 36]
    if not nums:
        return 'sem previsão'
    total = len(nums)
    partes = []

    duzias = [d for d in (_duzia_numero(n) for n in nums) if d is not None]
    if duzias:
        d_predom, contagem = max(((d, duzias.count(d)) for d in set(duzias)), key=lambda x: x[1])
        if contagem / total >= limiar_predominancia:
            partes.append(f'Dúzia {d_predom}')

    cores = [cor_numero(n) for n in nums if cor_numero(n)]
    if cores:
        c_predom, contagem = max(((c, cores.count(c)) for c in set(cores)), key=lambda x: x[1])
        if contagem / len(cores) >= limiar_predominancia:
            partes.append(c_predom.capitalize())

    colunas = [coluna_numero(n) for n in nums if coluna_numero(n)]
    if colunas:
        c_predom, contagem = max(((c, colunas.count(c)) for c in set(colunas)), key=lambda x: x[1])
        if contagem / len(colunas) >= limiar_predominancia:
            partes.append(f'Coluna {c_predom}')

    terminais = [terminal(n) for n in nums]
    t_predom, contagem = max(((t, terminais.count(t)) for t in set(terminais)), key=lambda x: x[1])
    if contagem / total >= limiar_predominancia:
        partes.append(f'Terminal {t_predom}')

    if not partes:
        if total <= 6:
            return f'números específicos: {sorted(nums)}'
        return f'{total} números (sem padrão único dominante)'
    return ' + '.join(partes)


def terminal(n):
    """Terminal (último dígito) de um número da roleta. 0 -> terminal 0."""
    return n % 10


def numeros_do_terminal(t, incluir_zero=False):
    """Todos os números da mesa que terminam no dígito t."""
    nums = [n for n in range(1, 37) if n % 10 == t]
    if t == 0 and incluir_zero:
        nums = [0] + nums
    return nums


def vizinhos_na_roda(numero, distancia=2):
    """Números fisicamente vizinhos na roda europeia, até `distancia` casas de cada lado."""
    if numero not in _IDX_RODA:
        return []
    i = _IDX_RODA[numero]
    total = len(RODA_EUROPEIA)
    viz = []
    for d in range(-distancia, distancia + 1):
        if d == 0:
            continue
        viz.append(RODA_EUROPEIA[(i + d) % total])
    return viz


class GatilhosNumericos:
    """
    Avalia os 20 gatilhos numéricos a cada rodada e mantém um backtest
    (taxa de acerto real, contra o histórico já observado) por gatilho.
    """

    NOMES = {
        'repete_numero': 'Repetição de número',
        'soma_terminal': 'Soma de terminal',
        'subtracao_terminal': 'Subtração de terminal',
        'vizinho_multiplos_dez': 'Vizinho de 0/10/20/30',
        'troca_crupie': 'Troca de crupiê (Voisins)',
        'sequencia_numerica': 'Sequência numérica',
        'multiplicacao_terminal': 'Multiplicação de terminal',
        'numero_quente': 'Número quente (streak)',
        'setor_roda': 'Setor da roda',
        'vizinho_fisico': 'Vizinho físico na roda',
        'espelho_numero': 'Número espelho',
        'fichas_estaticas': 'Fichas estáticas (conjunto fixo)',
        'numero_atrasado': 'Número atrasado ("dormindo")',
        'cavalo_numeros_recentes': 'Cavalo/split entre números recentes',
        'quebra_sequencia_cor': 'Quebra de sequência de cor',
        'coluna_ausente': 'Coluna ausente',
        'drift_rotor': 'Drift do rotor/bola',
        'sequencia_par_impar': 'Sequência par/ímpar',
        'assinatura_secao_crupie': 'Assinatura de seção da roda (sessão)',
        'six_line_ultimo_numero': 'Six line do último número',
    }

    def __init__(self, janela_quente=15, janela_repeticao=8, fator_soma=5,
                 fator_mult=2, distancia_vizinho=2, min_amostras_confiaveis=15,
                 fichas_estaticas_numeros=None, janela_atraso=26, top_atrasados=5,
                 janela_cor=4, janela_paridade=4, janela_coluna=6,
                 janela_cavalo=5, janela_assinatura=40, limiar_assinatura=0.45):
        self.janela_quente = janela_quente
        self.janela_repeticao = janela_repeticao
        self.fator_soma = fator_soma
        self.fator_mult = fator_mult
        self.distancia_vizinho = distancia_vizinho
        self.min_amostras_confiaveis = min_amostras_confiaveis

        # Grupo 2 - parâmetros configuráveis
        self.fichas_estaticas_numeros = list(fichas_estaticas_numeros) if fichas_estaticas_numeros else \
            [7, 10, 13, 17, 20, 23, 27, 30, 33, 36, 1, 4]
        self.janela_atraso = janela_atraso
        self.top_atrasados = top_atrasados
        self.janela_cor = janela_cor
        self.janela_paridade = janela_paridade
        self.janela_coluna = janela_coluna
        self.janela_cavalo = janela_cavalo
        self.janela_assinatura = janela_assinatura
        self.limiar_assinatura = limiar_assinatura

        # backtest[nome] = {'disparos': int, 'acertos': int, 'cobertura_soma': int}
        # cobertura_soma acumula quantos números foram apostados a cada disparo,
        # para calcular o "lift" (edge real) em vez de só a taxa de acerto bruta.
        self.backtest = {nome: {'disparos': 0, 'acertos': 0, 'cobertura_soma': 0} for nome in self.NOMES}
        self._ultimo_resultado = {}  # cache da última avaliação, p/ conferir acerto na próxima rodada

    # ------------------------------------------------------------------
    # Detectores individuais. Cada um recebe o histórico (mais recente por
    # último) e devolve (disparou: bool, numeros_sugeridos: list[int], detalhe: str)
    # ------------------------------------------------------------------

    def _repete_numero(self, hist):
        if len(hist) < self.janela_repeticao + 1:
            return False, [], ''
        ultimo = hist[-1]
        janela_anterior = hist[-(self.janela_repeticao + 1):-1]
        if ultimo in janela_anterior:
            nums = numeros_do_terminal(terminal(ultimo))
            return True, nums, f'{ultimo} repetiu -> terminal {terminal(ultimo)}'
        return False, [], ''

    def _soma_terminal(self, hist):
        if not hist:
            return False, [], ''
        ultimo = hist[-1]
        t = (ultimo + self.fator_soma) % 10
        nums = numeros_do_terminal(t)
        return True, nums, f'{ultimo}+{self.fator_soma} -> terminal {t}'

    def _subtracao_terminal(self, hist):
        if not hist:
            return False, [], ''
        ultimo = hist[-1]
        t = (ultimo - self.fator_soma) % 10
        nums = numeros_do_terminal(t)
        return True, nums, f'{ultimo}-{self.fator_soma} -> terminal {t}'

    def _vizinho_multiplos_dez(self, hist):
        if not hist:
            return False, [], ''
        ultimo = hist[-1]
        alvos = [0, 10, 20, 30]
        for alvo in alvos:
            if ultimo in vizinhos_na_roda(alvo, self.distancia_vizinho) or ultimo == alvo:
                nums = numeros_do_terminal(0, incluir_zero=True)
                return True, nums, f'{ultimo} é vizinho de {alvo} -> terminal 0'
        return False, [], ''

    def _troca_crupie(self, hist, troca_crupie_flag=False):
        if not troca_crupie_flag:
            return False, [], ''
        return True, list(VOISINS_DU_ZERO), 'Troca de crupiê -> Voisins du Zéro'

    def _sequencia_numerica(self, hist):
        if len(hist) < 3:
            return False, [], ''
        a, b, c = hist[-3], hist[-2], hist[-1]
        passo = b - a
        if passo != 0 and (c - b) == passo:
            proximo = (c + passo) % 37
            nums = [proximo] + vizinhos_na_roda(proximo, 1)
            return True, nums, f'sequência {a}->{b}->{c} (passo {passo}) -> projeta {proximo}'
        return False, [], ''

    def _multiplicacao_terminal(self, hist):
        if not hist:
            return False, [], ''
        ultimo = hist[-1]
        t = (ultimo * self.fator_mult) % 10
        nums = numeros_do_terminal(t)
        return True, nums, f'{ultimo}x{self.fator_mult} -> terminal {t}'

    def _numero_quente(self, hist):
        if len(hist) < self.janela_quente:
            return False, [], ''
        recentes = hist[-self.janela_quente:]
        contagem = {}
        for n in recentes:
            contagem[n] = contagem.get(n, 0) + 1
        quentes = [n for n, c in contagem.items() if c >= 2]
        if quentes:
            nums = list(quentes)
            for n in quentes:
                nums.extend(numeros_do_terminal(terminal(n)))
            nums = list(dict.fromkeys(nums))
            return True, nums, f'quentes nas últimas {self.janela_quente}: {quentes}'
        return False, [], ''

    def _setor_roda(self, hist):
        if not hist:
            return False, [], ''
        ultimo = hist[-1]
        if ultimo in VOISINS_DU_ZERO:
            return True, list(VOISINS_DU_ZERO), f'{ultimo} no setor Voisins du Zéro'
        if ultimo in TIERS_DU_CYLINDRE:
            return True, list(TIERS_DU_CYLINDRE), f'{ultimo} no setor Tiers du Cylindre'
        if ultimo in ORPHELINS:
            return True, list(ORPHELINS), f'{ultimo} no setor Orphelins'
        return False, [], ''

    def _vizinho_fisico(self, hist):
        if not hist:
            return False, [], ''
        ultimo = hist[-1]
        viz = vizinhos_na_roda(ultimo, self.distancia_vizinho)
        return True, [ultimo] + viz, f'vizinhos físicos de {ultimo} (±{self.distancia_vizinho})'

    # ---- Grupo 2 ----

    def _espelho_numero(self, hist):
        if not hist:
            return False, [], ''
        ultimo = hist[-1]
        if ultimo < 10:
            return False, [], ''
        espelho = int(str(ultimo)[::-1])
        if espelho > 36 or espelho == ultimo:
            return False, [], ''
        return True, [espelho], f'espelho de {ultimo} -> {espelho}'

    def _fichas_estaticas(self, hist):
        if not self.fichas_estaticas_numeros:
            return False, [], ''
        return True, list(self.fichas_estaticas_numeros), f'conjunto fixo ({len(self.fichas_estaticas_numeros)} números)'

    def _numero_atrasado(self, hist):
        if len(hist) < self.janela_atraso:
            return False, [], ''
        # ausência real de cada número = quantas rodadas atrás ele saiu pela
        # última vez (não apenas "saiu ou não dentro da janela")
        ausencia = {n: None for n in range(37)}
        for i, n in enumerate(reversed(hist)):
            if ausencia[n] is None:
                ausencia[n] = i
        for n in range(37):
            if ausencia[n] is None:
                ausencia[n] = len(hist)  # nunca saiu no histórico observado

        candidatos = [(n, a) for n, a in ausencia.items() if a >= self.janela_atraso]
        if not candidatos:
            return False, [], ''
        candidatos.sort(key=lambda x: -x[1])
        top = candidatos[:self.top_atrasados]
        nums = [n for n, _ in top]
        detalhe = f'top {len(nums)} mais atrasados (>={self.janela_atraso} rodadas): ' + \
                  ', '.join(f'{n}({a}r)' for n, a in top)
        return True, nums, detalhe

    def _cavalo_numeros_recentes(self, hist):
        if len(hist) < self.janela_cavalo:
            return False, [], ''
        recentes = hist[-self.janela_cavalo:]
        for i in range(len(recentes) - 1):
            a, b = recentes[i], recentes[i + 1]
            if a == 0 or b == 0 or a == b:
                continue
            if abs(a - b) in (1, 3):
                return True, [a, b], f'split válido entre {a} e {b}'
        return False, [], ''

    def _quebra_sequencia_cor(self, hist):
        if len(hist) < self.janela_cor:
            return False, [], ''
        recentes = hist[-self.janela_cor:]
        cores = [cor_numero(n) for n in recentes]
        if None in cores:
            return False, [], ''
        if len(set(cores)) == 1:
            cor_oposta = 'preto' if cores[0] == 'vermelho' else 'vermelho'
            nums = sorted(PRETOS) if cor_oposta == 'preto' else sorted(VERMELHOS)
            return True, nums, f'{self.janela_cor}x {cores[0]} seguidos -> aposta {cor_oposta}'
        return False, [], ''

    def _coluna_ausente(self, hist):
        if len(hist) < self.janela_coluna:
            return False, [], ''
        recentes = hist[-self.janela_coluna:]
        colunas_vistas = {coluna_numero(n) for n in recentes if n != 0}
        ausentes = {1, 2, 3} - colunas_vistas
        if len(ausentes) == 1:
            c = next(iter(ausentes))
            return True, numeros_da_coluna(c), f'coluna {c} ausente nas últimas {self.janela_coluna}'
        return False, [], ''

    def _drift_rotor(self, hist):
        if len(hist) < 4:
            return False, [], ''
        recentes = hist[-4:]
        posicoes = [_IDX_RODA[n] for n in recentes if n in _IDX_RODA]
        if len(posicoes) < 4:
            return False, [], ''
        total = len(RODA_EUROPEIA)
        passos = []
        for i in range(len(posicoes) - 1):
            d = (posicoes[i + 1] - posicoes[i]) % total
            # normaliza para o menor caminho (-18..+18)
            if d > total / 2:
                d -= total
            passos.append(d)
        if len(set(1 if p > 0 else -1 if p < 0 else 0 for p in passos)) == 1 and passos[0] != 0:
            passo_medio = round(sum(passos) / len(passos))
            proxima_pos = (posicoes[-1] + passo_medio) % total
            proximo_num = RODA_EUROPEIA[proxima_pos]
            nums = [proximo_num] + vizinhos_na_roda(proximo_num, 2)
            return True, nums, f'drift consistente (passo médio {passo_medio}) -> projeta {proximo_num}'
        return False, [], ''

    def _sequencia_par_impar(self, hist):
        if len(hist) < self.janela_paridade:
            return False, [], ''
        recentes = [n for n in hist[-self.janela_paridade:] if n != 0]
        if len(recentes) < self.janela_paridade:
            return False, [], ''
        paridades = [n % 2 for n in recentes]
        if len(set(paridades)) == 1:
            se_impar_agora = paridades[0] == 1
            nums = [n for n in range(1, 37) if (n % 2 == 0) == se_impar_agora]
            rotulo_atual = 'ímpares' if se_impar_agora else 'pares'
            rotulo_alvo = 'pares' if se_impar_agora else 'ímpares'
            return True, nums, f'{self.janela_paridade}x {rotulo_atual} seguidos -> aposta {rotulo_alvo}'
        return False, [], ''

    def _assinatura_secao_crupie(self, hist):
        if len(hist) < self.janela_assinatura:
            return False, [], ''
        recentes = hist[-self.janela_assinatura:]
        contagens = [sum(1 for n in recentes if n in arco) for arco in ARCOS_RODA]
        total = len(recentes)
        idx_max = contagens.index(max(contagens))
        proporcao = contagens[idx_max] / total
        if proporcao >= self.limiar_assinatura:
            nums = sorted(ARCOS_RODA[idx_max])
            return True, nums, f'seção {idx_max+1} concentrou {proporcao*100:.0f}% das últimas {total} rodadas'
        return False, [], ''

    def _six_line_ultimo_numero(self, hist):
        if not hist:
            return False, [], ''
        ultimo = hist[-1]
        if ultimo == 0:
            return False, [], ''
        nums = six_line_do_numero(ultimo)
        return True, nums, f'six line de {ultimo}: {nums}'

    def _rodar_detector(self, nome, hist, troca_crupie_flag=False):
        if nome == 'repete_numero':
            return self._repete_numero(hist)
        if nome == 'soma_terminal':
            return self._soma_terminal(hist)
        if nome == 'subtracao_terminal':
            return self._subtracao_terminal(hist)
        if nome == 'vizinho_multiplos_dez':
            return self._vizinho_multiplos_dez(hist)
        if nome == 'troca_crupie':
            return self._troca_crupie(hist, troca_crupie_flag)
        if nome == 'sequencia_numerica':
            return self._sequencia_numerica(hist)
        if nome == 'multiplicacao_terminal':
            return self._multiplicacao_terminal(hist)
        if nome == 'numero_quente':
            return self._numero_quente(hist)
        if nome == 'setor_roda':
            return self._setor_roda(hist)
        if nome == 'vizinho_fisico':
            return self._vizinho_fisico(hist)
        if nome == 'espelho_numero':
            return self._espelho_numero(hist)
        if nome == 'fichas_estaticas':
            return self._fichas_estaticas(hist)
        if nome == 'numero_atrasado':
            return self._numero_atrasado(hist)
        if nome == 'cavalo_numeros_recentes':
            return self._cavalo_numeros_recentes(hist)
        if nome == 'quebra_sequencia_cor':
            return self._quebra_sequencia_cor(hist)
        if nome == 'coluna_ausente':
            return self._coluna_ausente(hist)
        if nome == 'drift_rotor':
            return self._drift_rotor(hist)
        if nome == 'sequencia_par_impar':
            return self._sequencia_par_impar(hist)
        if nome == 'assinatura_secao_crupie':
            return self._assinatura_secao_crupie(hist)
        if nome == 'six_line_ultimo_numero':
            return self._six_line_ultimo_numero(hist)
        return False, [], ''

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def avaliar_todos(self, historico_numeros, troca_crupie_flag=False):
        """
        Avalia os 20 gatilhos contra o histórico atual (lista/deque, mais
        recente por último). Retorna dict: nome -> {disparou, numeros, detalhe,
        taxa_acerto, amostras, cobertura_media, lift, ev_por_unidade}

        `lift` = taxa_acerto_historica / cobertura_esperada_pelo_acaso.
        Um gatilho que cobre metade da mesa vai naturalmente acertar perto de
        50% das vezes SEM ISSO SER EDGE NENHUM -- lift=1.0 é exatamente o
        esperado pelo acaso. Só lift > 1 de forma consistente (com amostra
        mínima) indicaria algo além do óbvio; por isso a escolha automática
        ranqueia por lift, não pela taxa bruta.
        """
        hist = list(historico_numeros)
        resultado = {}
        for nome in self.NOMES:
            disparou, numeros, detalhe = self._rodar_detector(nome, hist, troca_crupie_flag)
            bt = self.backtest[nome]
            taxa = (bt['acertos'] / bt['disparos'] * 100) if bt['disparos'] > 0 else None
            cobertura_media = (bt['cobertura_soma'] / bt['disparos']) if bt['disparos'] > 0 else None

            lift = None
            ev_por_unidade = None
            if taxa is not None and cobertura_media and cobertura_media > 0:
                baseline_pct = (cobertura_media / 37) * 100
                lift = taxa / baseline_pct if baseline_pct > 0 else None
                # EV por unidade apostada, payout europeu padrão 35:1 (retorno 36x)
                p = taxa / 100
                ev_total = p * 36 - cobertura_media
                ev_por_unidade = (ev_total / cobertura_media) * 100

            resultado[nome] = {
                'nome_exibicao': self.NOMES[nome],
                'disparou': disparou,
                'numeros_sugeridos': numeros,
                'situacao_prevista': derivar_situacao_prevista(numeros) if disparou else None,
                'detalhe': detalhe,
                'taxa_acerto_historica': taxa,
                'cobertura_media': cobertura_media,
                'lift': lift,
                'ev_por_unidade': ev_por_unidade,
                'amostras': bt['disparos'],
                'confiavel': bt['disparos'] >= self.min_amostras_confiaveis,
            }
        self._ultimo_resultado = resultado
        return resultado

    def conferir_resultado(self, numero_saido):
        """
        ORDEM CORRETA DE USO (importante p/ o backtest não ficar viesado):
          1) res = avaliar_todos(historico_ATE_A_RODADA_ANTERIOR)
          2) espera sair o próximo número `nr`
          3) gatilhos.conferir_resultado(nr)   <- compara nr contra o `res` do passo 1
          4) historico.append(nr)
          5) volta ao passo 1 com o histórico já atualizado

        Chamar conferir_resultado ANTES de dar append no número novo (ou seja,
        conferir com o mesmo número que já foi usado pra gerar a sugestão)
        infla artificialmente a taxa de acerto -- o vizinho_fisico e o
        setor_roda, por exemplo, sempre "acertariam" a si mesmos.
        """
        for nome, info in self._ultimo_resultado.items():
            if info['disparou']:
                self.backtest[nome]['disparos'] += 1
                self.backtest[nome]['cobertura_soma'] += len(info['numeros_sugeridos'])
                if numero_saido in info['numeros_sugeridos']:
                    self.backtest[nome]['acertos'] += 1

    def escolher_automatico(self, resultado_avaliacao):
        """
        Modo automático: entre os gatilhos que dispararam nesta rodada,
        escolhe o de maior LIFT histórico (não a maior taxa de acerto bruta --
        um gatilho que cobre metade da mesa sempre teria taxa bruta alta sem
        isso significar nada). Exige amostra mínima e lift calculável.
        Se nenhum gatilho confiável disparou, retorna None (sem entrada).
        """
        candidatos = [
            (nome, info) for nome, info in resultado_avaliacao.items()
            if info['disparou'] and info['confiavel'] and info['lift'] is not None
        ]
        if not candidatos:
            return None
        candidatos.sort(key=lambda x: x[1]['lift'], reverse=True)
        nome_escolhido, info = candidatos[0]
        return nome_escolhido, info

    def resetar_backtest(self):
        self.backtest = {nome: {'disparos': 0, 'acertos': 0, 'cobertura_soma': 0} for nome in self.NOMES}
        self._ultimo_resultado = {}
