# só que tem que ser a versão 3.10 do Python
# pip install docplex

# importando as bibliotecas do CPLEX
from docplex.cp.model import CpoModel
import docplex.cp.solver.solver as solver
import os
import glob
import time
import argparse


def ler_instancia(caminho_arquivo):
    """Lê uma instância do arquivo e retorna os dados das tarefas"""
    tarefas = []
    with open(caminho_arquivo, 'r') as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if linha:
                partes = linha.split()
                if len(partes) == 3:
                    duracao_a = int(partes[0])
                    duracao_b = int(partes[1])
                    delay = int(partes[2])
                    tarefas.append((duracao_a, duracao_b, delay))
    return tarefas


def greedy_schedule(dados_tarefas):
    """Gera uma solução factível rápida (heurística greedy) e retorna o makespan.
    Agenda cada parte A no menor instante possível e a parte B no menor instante
    >= end(A)+delay que não cause sobreposição. Usa buscas discretas (inteiros).
    """
    if not dados_tarefas:
        return 0

    occupied = []  # lista de (start, end) ocupados

    def overlaps(s, e):
        for (os, oe) in occupied:
            if not (e <= os or s >= oe):
                return True
        return False

    def find_earliest(length, earliest):
        t = earliest
        # procura incremento por 1 (durations são inteiros)
        while True:
            if not overlaps(t, t + length):
                return t
            # avançar para além do próximo intervalo que começa antes de t+length
            next_t = t + 1
            for (os, oe) in occupied:
                if os < t + length and oe > t:
                    next_t = max(next_t, oe)
            t = next_t

    makespan = 0
    for (dur_a, dur_b, delay) in dados_tarefas:
        start_a = find_earliest(dur_a, 0)
        end_a = start_a + dur_a
        occupied.append((start_a, end_a))

        earliest_b = end_a + delay
        start_b = find_earliest(dur_b, earliest_b)
        end_b = start_b + dur_b
        occupied.append((start_b, end_b))

        makespan = max(makespan, end_b)

    return makespan


def span_total(tarefa):
    """Retorna o 'tamanho da boneca' da tarefa: A + delay + B."""
    duracao_a, duracao_b, delay = tarefa
    return duracao_a + delay + duracao_b


def construir_fases_de_busca(modelo, tasks, dados_tarefas):
    """Prioriza tarefas com maior span para a busca do CP Optimizer.

    A ideia é fazer o solver fixar primeiro as tarefas mais 'externas'
    (maiores L = A + delay + B), deixando as menores serem encaixadas nos
    intervalos livres remanescentes, em um comportamento de 'boneca russa'.
    """
    qtdTasks = len(dados_tarefas)
    ordem = sorted(
        range(qtdTasks),
        key=lambda i: (span_total(
            dados_tarefas[i]), dados_tarefas[i][0] + dados_tarefas[i][1], dados_tarefas[i][2]),
        reverse=True,
    )

    fases = [modelo.search_phase(
        [tasks[i], tasks[i + qtdTasks]]) for i in ordem]
    modelo.set_search_phases(fases)


def aplicar_encaixe(modelo, tasks, dados_tarefas):
    """Tenta encaixar a maior tarefa possível dentro do maior intervalo.

    Seleciona a tarefa com maior span (A+delay+B) e procura outra tarefa
    (diferente) com maior span que caiba dentro desse intervalo. Se
    encontrada, adiciona restrições para forçar que a tarefa menor
    comece após o início da maior e termine antes do fim da maior (ou seja,
    seja "encaixada").
    """
    qtdTasks = len(dados_tarefas)
    if qtdTasks < 2:
        return

    spans = [span_total(t) for t in dados_tarefas]
    # índice da tarefa com maior intervalo
    idx_maior = max(range(qtdTasks), key=lambda k: (
        spans[k], dados_tarefas[k][0] + dados_tarefas[k][1]))

    # procurar a maior tarefa diferente que caiba dentro do span da maior
    candidatos = [j for j in range(
        qtdTasks) if j != idx_maior and spans[j] <= spans[idx_maior]]
    if not candidatos:
        return

    idx_encaixe = max(candidatos, key=lambda k: (
        spans[k], dados_tarefas[k][0] + dados_tarefas[k][1]))

    # variáveis A/B para as tarefas selecionadas
    A_i = tasks[idx_maior]
    B_i = tasks[idx_maior + qtdTasks]
    A_j = tasks[idx_encaixe]
    B_j = tasks[idx_encaixe + qtdTasks]

    # forçar Aj começar após o início de Ai e Bj terminar antes do fim de Bi
    try:
        modelo.add(modelo.start_of(A_j) >= modelo.start_of(A_i))
        modelo.add(modelo.end_of(B_j) <= modelo.end_of(B_i))
    except Exception:
        # se a API não aceitar as operações, ignoramos o encaixe
        pass


def resolver_instancia(dados_tarefas, nome_instancia, tempo_limite=900):
    """Resolve uma instância do CTSP e retorna os resultados"""

    # criar o modelo do CTSP
    modelo = CpoModel()

    # quantidade de tarefas
    qtdTasks = len(dados_tarefas)

    # vamos criar as tarefas
    tasks = [0]*(qtdTasks*2)
    for i in range(qtdTasks):
        duracao_a, duracao_b, delay = dados_tarefas[i]

        # parte A de cada tarefa
        tasks[i] = modelo.interval_var(length=duracao_a, name=f"A{i}")
        # parte B de cada tarefa
        tasks[i+qtdTasks] = modelo.interval_var(length=duracao_b, name=f"B{i}")
        # a parte B deve começar após o encerramento de A e depois de um intervalo
        modelo.add(modelo.end_before_start(
            tasks[i], tasks[i+qtdTasks], delay=delay))

    # as tarefas não podem se sobrepor
    modelo.add(modelo.no_overlap(tasks))

    # o makespan é o maior valor de encerramento de qualquer parte B
    makespan = modelo.max([modelo.end_of(tasks[i+qtdTasks])
                          for i in range(qtdTasks)])
    modelo.minimize(makespan)

    # Busca guiada: tarefas maiores primeiro, menores depois.
    construir_fases_de_busca(modelo, tasks, dados_tarefas)
    # Tentativa de encaixe: encaixar a maior tarefa possível dentro do maior intervalo
    aplicar_encaixe(modelo, tasks, dados_tarefas)

    # Heurística rápida para obter um upper bound inicial (faz pruning)
    try:
        ub = greedy_schedule(dados_tarefas)
        if ub is not None:
            modelo.add(makespan <= ub)
    except Exception:
        # se heurística falhar por algum motivo, continuamos sem UB
        pass

    # marcar o tempo de início
    tempo_inicio = time.time()

    # vamos resolver o modelo
    resp = modelo.solve(TimeLimit=tempo_limite, LogVerbosity="Quiet")

    # marcar o tempo de fim
    tempo_fim = time.time()
    tempo_execucao = tempo_fim - tempo_inicio

    resultado = {
        'instancia': nome_instancia,
        'num_tarefas': qtdTasks,
        'tempo_execucao': tempo_execucao,
        'solucao_encontrada': resp is not None
    }

    if resp:
        resultado['valor_objetivo'] = resp.get_objective_value()
        resultado['melhor_bound'] = resp.get_objective_bound()
        resultado['gap'] = abs(resultado['valor_objetivo'] - resultado['melhor_bound']) / \
            resultado['valor_objetivo'] * \
            100 if resultado['valor_objetivo'] > 0 else 0
    else:
        resultado['valor_objetivo'] = None
        resultado['melhor_bound'] = None
        resultado['gap'] = None

    return resultado


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark CTSP com CP Optimizer")
    parser.add_argument('--input-dir', '-i', default=r"d:\UFF\tcc_si\Coupled task scheduling benchmark\Coupled task scheduling benchmark\Single machine\General set",
                        help='Diretório com instâncias (.txt)')
    parser.add_argument('--patterns', '-p', nargs='+', default=['20_*.txt', '25_*.txt', '40_*.txt'],
                        help='Padrões de arquivos (ex: 5_*.txt)')
    parser.add_argument('--time-limit', '-t', type=int,
                        default=900, help='Tempo limite por instância (s)')
    parser.add_argument(
        '--out', '-o', default='resultados_benchmark.txt', help='Arquivo de saída')
    args = parser.parse_args()

    # Caminho para a pasta das instâncias
    caminho_base = args.input_dir
    # Padrões para buscar arquivos
    padroes = args.patterns

    resultados = []

    print("Iniciando execução dos testes...")

    for padrao in padroes:
        arquivos = glob.glob(os.path.join(caminho_base, padrao))
        arquivos.sort()  # Ordenar para ter uma ordem consistente

        for arquivo in arquivos:
            nome_arquivo = os.path.basename(arquivo)
            print(f"Processando: {nome_arquivo}")

            try:
                # Ler a instância
                dados_tarefas = ler_instancia(arquivo)

                # Resolver a instância
                resultado = resolver_instancia(
                    dados_tarefas, nome_arquivo, tempo_limite=args.time_limit)
                resultados.append(resultado)

                # Mostrar progresso
                if resultado['solucao_encontrada']:
                    print(
                        f"  ✓ Resolvido - Obj: {resultado['valor_objetivo']}, Bound: {resultado['melhor_bound']}, Tempo: {resultado['tempo_execucao']:.2f}s")
                else:
                    print(
                        f"  ✗ Sem solução - Tempo: {resultado['tempo_execucao']:.2f}s")

            except Exception as e:
                print(f"  ✗ Erro ao processar {nome_arquivo}: {str(e)}")
                resultado = {
                    'instancia': nome_arquivo,
                    'num_tarefas': 0,
                    'tempo_execucao': 0,
                    'solucao_encontrada': False,
                    'valor_objetivo': None,
                    'melhor_bound': None,
                    'gap': None,
                    'erro': str(e)
                }
                resultados.append(resultado)

    # Salvar resultados em arquivo
    nome_arquivo_resultado = args.out
    with open(nome_arquivo_resultado, 'w') as arquivo:
        arquivo.write("RESULTADOS DO BENCHMARK - COUPLED TASK SCHEDULING\n")
        arquivo.write("=" * 60 + "\n")
        arquivo.write(
            f"Tempo limite por instancia: {args.time_limit} segundos\n")
        arquivo.write(
            f"Total de instancias processadas: {len(resultados)}\n\n")

        # Cabeçalho da tabela
        arquivo.write(
            f"{'Instancia':<20} {'Tarefas':<8} {'Tempo(s)':<10} {'Objetivo':<12} {'Bound':<12} {'Gap(%)':<8} {'Status':<10}\n")
        arquivo.write("-" * 90 + "\n")

        for resultado in resultados:
            instancia = resultado['instancia']
            num_tarefas = resultado['num_tarefas']
            tempo = f"{resultado['tempo_execucao']:.2f}"

            if resultado['solucao_encontrada']:
                objetivo = str(resultado['valor_objetivo'])
                bound = str(resultado['melhor_bound'])
                gap = f"{resultado['gap']:.2f}" if resultado['gap'] is not None else "N/A"
                status = "RESOLVIDO"
            else:
                objetivo = "N/A"
                bound = "N/A"
                gap = "N/A"
                status = "SEM SOL"

            arquivo.write(
                f"{instancia:<20} {num_tarefas:<8} {tempo:<10} {objetivo:<12} {bound:<12} {gap:<8} {status:<10}\n")

        # Estatísticas resumidas
        arquivo.write("\n" + "=" * 60 + "\n")
        arquivo.write("ESTATISTICAS RESUMIDAS\n")
        arquivo.write("=" * 60 + "\n")

        resolvidos = [r for r in resultados if r['solucao_encontrada']]
        nao_resolvidos = [r for r in resultados if not r['solucao_encontrada']]

        arquivo.write(
            f"Instancias resolvidas: {len(resolvidos)}/{len(resultados)} ({len(resolvidos)/len(resultados)*100:.1f}%)\n")
        arquivo.write(f"Instancias nao resolvidas: {len(nao_resolvidos)}\n")

        if resolvidos:
            tempo_medio = sum(r['tempo_execucao']
                              for r in resolvidos) / len(resolvidos)
            arquivo.write(f"Tempo medio (resolvidas): {tempo_medio:.2f}s\n")

            gaps = [r['gap'] for r in resolvidos if r['gap'] is not None]
            if gaps:
                gap_medio = sum(gaps) / len(gaps)
                arquivo.write(f"Gap medio: {gap_medio:.2f}%\n")

            arquivo.write(
                f"\nTempo total de execucao: {sum(r['tempo_execucao'] for r in resultados):.2f}s\n")

    print(f"\nResultados salvos em: {nome_arquivo_resultado}")
    print(f"Total de instancias processadas: {len(resultados)}")
    print(f"Instancias resolvidas: {len(resolvidos)}/{len(resultados)}")


if __name__ == "__main__":
    main()
