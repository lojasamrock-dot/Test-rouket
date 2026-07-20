import requests
import json
import random
from datetime import datetime
from collections import Counter
import os

class MegaSenaApp:
    def __init__(self):
        self.url_api = "https://loteriascaixa-api.herokuapp.com/api/megasena"
        self.colunas = {
            'C1': list(range(1, 11)),
            'C2': list(range(11, 21)),
            'C3': list(range(21, 31)),
            'C4': list(range(31, 41)),
            'C5': list(range(41, 51)),
            'C6': list(range(51, 61))
        }
        self.dados_historicos = []
        self.analise_colunas = {}
        self.jogos_gerados = []
        
    def buscar_concursos_recentes(self, quantidade=20):
        """Busca os últimos concursos da Mega-Sena"""
        try:
            response = requests.get(self.url_api)
            if response.status_code == 200:
                dados = response.json()
                
                # Pega os últimos 'quantidade' concursos
                if isinstance(dados, list):
                    self.dados_historicos = dados[-quantidade:] if len(dados) > quantidade else dados
                else:
                    self.dados_historicos = [dados]
                    
                print(f"✅ Buscados {len(self.dados_historicos)} concursos recentes")
                return True
            else:
                print(f"❌ Erro ao buscar dados: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Erro na requisição: {e}")
            return False
    
    def analisar_ultimos_resultados(self, quantidade=10):
        """Analisa os últimos resultados para identificar padrões"""
        if not self.dados_historicos:
            print("❌ Nenhum dado histórico disponível")
            return
        
        ultimos = self.dados_historicos[-quantidade:] if len(self.dados_historicos) > quantidade else self.dados_historicos
        
        # Análise de colunas
        contagem_colunas = {col: 0 for col in self.colunas}
        numeros_mais_frequentes = []
        
        for concurso in ultimos:
            if 'dezenas' in concurso:
                dezenas = concurso['dezenas']
                numeros_mais_frequentes.extend(dezenas)
                
                # Conta colunas
                for dezena in dezenas:
                    num = int(dezena)
                    for col, intervalo in self.colunas.items():
                        if num in intervalo:
                            contagem_colunas[col] += 1
        
        # Análise de frequência
        frequencia_numeros = Counter(numeros_mais_frequentes)
        numeros_ordenados = sorted(frequencia_numeros.items(), key=lambda x: x[1], reverse=True)
        
        self.analise_colunas = {
            'contagem_colunas': contagem_colunas,
            'numeros_mais_frequentes': numeros_ordenados[:15],
            'colunas_mais_fortes': sorted(contagem_colunas.items(), key=lambda x: x[1], reverse=True)
        }
        
        print("\n📊 ANÁLISE DOS ÚLTIMOS RESULTADOS:")
        print("=" * 40)
        print("Colunas com mais ocorrências:")
        for col, qtd in self.analise_colunas['colunas_mais_fortes']:
            print(f"  {col}: {qtd} vezes")
        
        print("\nNúmeros mais frequentes:")
        for num, freq in self.analise_colunas['numeros_mais_frequentes'][:10]:
            print(f"  {num}: {freq} vezes")
        
        return self.analise_colunas
    
    def get_dezenas_por_coluna(self, coluna, quantidade=3):
        """Retorna dezenas específicas de uma coluna"""
        if coluna not in self.colunas:
            return []
        
        numeros_coluna = self.colunas[coluna]
        
        # Tenta incluir números mais frequentes primeiro
        if self.analise_colunas and 'numeros_mais_frequentes' in self.analise_colunas:
            numeros_frequentes = [int(num[0]) for num in self.analise_colunas['numeros_mais_frequentes'] 
                                if int(num[0]) in numeros_coluna]
            
            # Pega alguns frequentes e completa com números aleatórios
            selecionados = numeros_frequentes[:min(quantidade, len(numeros_frequentes))]
            
            # Completa com números aleatórios
            disponiveis = [n for n in numeros_coluna if n not in selecionados]
            if len(selecionados) < quantidade and disponiveis:
                completar = random.sample(disponiveis, min(quantidade - len(selecionados), len(disponiveis)))
                selecionados.extend(completar)
        else:
            # Seleção aleatória
            selecionados = random.sample(numeros_coluna, min(quantidade, len(numeros_coluna)))
        
        return selecionados
    
    def gerar_jogos_versao4(self):
        """Gera os 15 jogos baseados na Versão 4"""
        print("\n🎯 GERANDO JOGOS - VERSÃO 4")
        print("=" * 50)
        
        # Pega colunas mais fortes da análise
        colunas_fortes = [col for col, qtd in self.analise_colunas['colunas_mais_fortes']]
        coluna_principal = colunas_fortes[0] if colunas_fortes else 'C3'
        coluna_apoio1 = colunas_fortes[1] if len(colunas_fortes) > 1 else 'C4'
        coluna_apoio2 = colunas_fortes[2] if len(colunas_fortes) > 2 else 'C6'
        
        print(f"📈 Colunas identificadas como principais: {coluna_principal}, {coluna_apoio1}, {coluna_apoio2}")
        
        # BLOCO A - 10 Jogos Principais
        jogos_principais = [
            # Jogo 1 - Base C3 + C6
            self._criar_jogo([
                ('C3', 2), ('C4', 1), ('C6', 2), ('C1', 1)
            ]),
            
            # Jogo 2 - Base C3 + C4
            self._criar_jogo([
                ('C1', 1), ('C4', 2), ('C3', 2), ('C5', 1)
            ]),
            
            # Jogo 3 - Base C3 + C4 + C6
            self._criar_jogo([
                ('C3', 2), ('C4', 2), ('C6', 1), ('C1', 1)
            ]),
            
            # Jogo 4 - Equilibrado
            self._criar_jogo([
                ('C1', 2), ('C6', 2), ('C3', 1), ('C4', 1)
            ]),
            
            # Jogo 5 - Reforço C3
            self._criar_jogo([
                ('C1', 1), ('C3', 2), ('C4', 1), ('C6', 1), ('C5', 1)
            ]),
            
            # Jogo 6 - Reforço C6
            self._criar_jogo([
                ('C3', 1), ('C6', 2), ('C1', 1), ('C4', 1), ('C5', 1)
            ]),
            
            # Jogo 7 - Miolo
            self._criar_jogo([
                ('C5', 1), ('C6', 1), ('C3', 2), ('C4', 1), ('C1', 1)
            ]),
            
            # Jogo 8 - C1 + C6
            self._criar_jogo([
                ('C6', 2), ('C1', 2), ('C4', 1), ('C3', 1)
            ]),
            
            # Jogo 9 - Diversificado
            self._criar_jogo([
                ('C5', 1), ('C4', 1), ('C3', 1), ('C6', 2), ('C1', 1)
            ]),
            
            # Jogo 10 - Fechamento
            self._criar_jogo([
                ('C6', 1), ('C5', 1), ('C1', 1), ('C3', 2), ('C4', 1)
            ])
        ]
        
        # BLOCO B - 5 Jogos de Proteção
        jogos_protecao = [
            # Proteção 1 - C2
            self._criar_jogo([
                ('C3', 2), ('C2', 1), ('C5', 1), ('C4', 1), ('C6', 1)
            ]),
            
            # Proteção 2 - C2 + C5
            self._criar_jogo([
                ('C2', 1), ('C3', 2), ('C4', 1), ('C5', 1), ('C6', 1)
            ]),
            
            # Proteção 3 - Cobertura total
            self._criar_jogo([
                ('C2', 1), ('C3', 1), ('C4', 1), ('C1', 1), ('C6', 1), ('C5', 1)
            ]),
            
            # Proteção 4 - Reforço C2
            self._criar_jogo([
                ('C4', 1), ('C6', 1), ('C5', 1), ('C2', 2), ('C3', 1)
            ]),
            
            # Proteção 5 - Cobertura ampla
            self._criar_jogo([
                ('C1', 1), ('C2', 1), ('C3', 1), ('C4', 1), ('C5', 1), ('C6', 1)
            ])
        ]
        
        self.jogos_gerados = {
            'principais': jogos_principais,
            'protecao': jogos_protecao
        }
        
        self._exibir_jogos()
        return self.jogos_gerados
    
    def _criar_jogo(self, configuracao_colunas):
        """Cria um jogo baseado na configuração de colunas"""
        dezenas = []
        
        for coluna, quantidade in configuracao_colunas:
            numeros = self.get_dezenas_por_coluna(coluna, quantidade)
            dezenas.extend(numeros)
        
        # Ordena as dezenas
        dezenas.sort()
        
        # Se tiver mais de 6, corta, se tiver menos, completa
        if len(dezenas) > 6:
            dezenas = dezenas[:6]
        elif len(dezenas) < 6:
            # Completa com números aleatórios
            todos_numeros = set(range(1, 61))
            usados = set(dezenas)
            disponiveis = list(todos_numeros - usados)
            if disponiveis:
                extras = random.sample(disponiveis, min(6 - len(dezenas), len(disponiveis)))
                dezenas.extend(extras)
                dezenas.sort()
        
        return dezenas
    
    def _exibir_jogos(self):
        """Exibe todos os jogos gerados"""
        print("\n📋 JOGOS GERADOS - VERSÃO 4")
        print("=" * 60)
        
        print("\n🔵 BLOCO A - 10 JOGOS PRINCIPAIS")
        print("-" * 40)
        for i, jogo in enumerate(self.jogos_gerados['principais'], 1):
            print(f"Jogo {i:2d}: {jogo}")
            
        print("\n🟢 BLOCO B - 5 JOGOS DE PROTEÇÃO")
        print("-" * 40)
        for i, jogo in enumerate(self.jogos_gerados['protecao'], 1):
            print(f"Proteção {i}: {jogo}")
    
    def salvar_jogos_em_arquivo(self, nome_arquivo="jogos_megasena.json"):
        """Salva os jogos gerados em um arquivo JSON"""
        dados = {
            'data_geracao': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'quantidade_jogos': 15,
            'jogos_principais': self.jogos_gerados.get('principais', []),
            'jogos_protecao': self.jogos_gerados.get('protecao', []),
            'analise': self.analise_colunas
        }
        
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Jogos salvos em '{nome_arquivo}'")
    
    def exibir_estatisticas_jogos(self):
        """Exibe estatísticas dos jogos gerados"""
        if not self.jogos_gerados:
            print("❌ Nenhum jogo gerado")
            return
        
        todos_jogos = self.jogos_gerados['principais'] + self.jogos_gerados['protecao']
        
        # Contagem de pares/ímpares
        print("\n📊 ESTATÍSTICAS DOS JOGOS")
        print("=" * 40)
        
        for i, jogo in enumerate(todos_jogos, 1):
            pares = sum(1 for n in jogo if n % 2 == 0)
            impares = 6 - pares
            
            # Contagem por coluna
            colunas_contagem = {col: 0 for col in self.colunas}
            for num in jogo:
                for col, intervalo in self.colunas.items():
                    if num in intervalo:
                        colunas_contagem[col] += 1
            
            colunas_ativas = [col for col, qtd in colunas_contagem.items() if qtd > 0]
            
            tipo = "Principal" if i <= 10 else "Proteção"
            print(f"{tipo} {i:2d}: {jogo} | Pares:{pares} Ímpares:{impares} | Colunas: {len(colunas_ativas)}")
    
    def recomendar_jogos_prioridade(self):
        """Recomenda jogos por nível de prioridade"""
        print("\n🎯 RECOMENDAÇÃO DE JOGOS POR PRIORIDADE")
        print("=" * 50)
        
        prioridade_maxima = [0, 1, 2, 3, 7, 9]  # Jogos 1,2,3,4,8,10
        prioridade_media = [4, 5, 6, 8]  # Jogos 5,6,7,9
        protecao = list(range(10, 15))  # Proteções 1-5
        
        print("\n🔥 PRIORIDADE MÁXIMA (6 jogos):")
        for idx in prioridade_maxima:
            if idx < len(self.jogos_gerados['principais']):
                print(f"  Jogo {idx+1}: {self.jogos_gerados['principais'][idx]}")
        
        print("\n📊 PRIORIDADE MÉDIA (4 jogos):")
        for idx in prioridade_media:
            if idx < len(self.jogos_gerados['principais']):
                print(f"  Jogo {idx+1}: {self.jogos_gerados['principais'][idx]}")
        
        print("\n🛡️ PROTEÇÃO (5 jogos):")
        for idx in protecao:
            pos = idx - 10
            if pos < len(self.jogos_gerados['protecao']):
                print(f"  Proteção {pos+1}: {self.jogos_gerados['protecao'][pos]}")
        
        print("\n💡 PLANOS DE JOGO:")
        print("  📌 Econômico (4 jogos): Jogos 1, 2, 3, 8")
        print("  📌 Intermediário (8 jogos): Jogos 1, 2, 3, 4, 5, 8, 10, Proteção 1")
        print("  📌 Completo (15 jogos): Todos os 15 jogos")

def main():
    """Função principal do aplicativo"""
    print("🚀 MEGA-SENA VERSÃO 4 - GERADOR INTELIGENTE")
    print("=" * 60)
    
    app = MegaSenaApp()
    
    # Busca dados da API
    print("\n📡 Buscando dados da API...")
    if not app.buscar_concursos_recentes(20):
        print("⚠️ Usando dados simulados para demonstração")
        # Dados simulados para demonstração
        app.dados_historicos = [
            {'dezenas': ['03', '15', '22', '34', '45', '57']},
            {'dezenas': ['08', '16', '21', '33', '42', '58']},
            {'dezenas': ['11', '19', '27', '35', '44', '59']},
        ]
    
    # Analisa resultados
    print("\n🔍 Analisando resultados...")
    app.analisar_ultimos_resultados(10)
    
    # Gera jogos
    app.gerar_jogos_versao4()
    
    # Exibe estatísticas
    app.exibir_estatisticas_jogos()
    
    # Recomendações
    app.recomendar_jogos_prioridade()
    
    # Salva em arquivo
    app.salvar_jogos_em_arquivo()
    
    print("\n✅ Processo concluído com sucesso!")

if __name__ == "__main__":
    main()
