# -*- coding: utf-8 -*-
"""
gatilhos_numericos.py
======================
Módulo de gatilhos de entrada baseados em números/terminais da roleta europeia.

Implementa 10 gatilhos clássicos usados por jogadores que fazem "leitura de padrão":
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
    Avalia os 10 gatilhos numéricos a cada rodada e mantém um backtest
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
    }

    def __init__(self, janela_quente=15, janela_repeticao=8, fator_soma=5,
                 fator_mult=2, distancia_vizinho=2, min_amostras_confiaveis=15):
        self.janela_quente = janela_quente
        self.janela_repeticao = janela_repeticao
        self.fator_soma = fator_soma
        self.fator_mult = fator_mult
        self.distancia_vizinho = distancia_vizinho
        self.min_amostras_confiaveis = min_amostras_confiaveis

        # backtest[nome] = {'disparos': int, 'acertos': int}
        self.backtest = {nome: {'disparos': 0, 'acertos': 0} for nome in self.NOMES}
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
        return False, [], ''

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def avaliar_todos(self, historico_numeros, troca_crupie_flag=False):
        """
        Avalia os 10 gatilhos contra o histórico atual (lista/deque, mais
        recente por último). Retorna dict: nome -> {disparou, numeros, detalhe, taxa_acerto, amostras}
        """
        hist = list(historico_numeros)
        resultado = {}
        for nome in self.NOMES:
            disparou, numeros, detalhe = self._rodar_detector(nome, hist, troca_crupie_flag)
            bt = self.backtest[nome]
            taxa = (bt['acertos'] / bt['disparos'] * 100) if bt['disparos'] > 0 else None
            resultado[nome] = {
                'nome_exibicao': self.NOMES[nome],
                'disparou': disparou,
                'numeros_sugeridos': numeros,
                'detalhe': detalhe,
                'taxa_acerto_historica': taxa,
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
                if numero_saido in info['numeros_sugeridos']:
                    self.backtest[nome]['acertos'] += 1

    def escolher_automatico(self, resultado_avaliacao):
        """
        Modo automático: entre os gatilhos que dispararam nesta rodada,
        escolhe o de maior taxa de acerto histórica (exige amostra mínima).
        Se nenhum gatilho confiável disparou, retorna None (sem entrada).
        """
        candidatos = [
            (nome, info) for nome, info in resultado_avaliacao.items()
            if info['disparou'] and info['confiavel'] and info['taxa_acerto_historica'] is not None
        ]
        if not candidatos:
            return None
        candidatos.sort(key=lambda x: x[1]['taxa_acerto_historica'], reverse=True)
        nome_escolhido, info = candidatos[0]
        return nome_escolhido, info

    def resetar_backtest(self):
        self.backtest = {nome: {'disparos': 0, 'acertos': 0} for nome in self.NOMES}
        self._ultimo_resultado = {}
