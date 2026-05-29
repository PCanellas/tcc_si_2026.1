from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

# importando as bibliotecas do CPLEX
from docplex.cp.model import CpoModel
from docplex.cp.solver.cpo_callback import CpoCallback
import time
import sys
import random

Task = Tuple[int, int, int, int, int]

tempo_inicio=0
tempo_incumbente = 0

class MyCallback(CpoCallback):
    def invoke(self, solver, event, sres):
        global tempo_incumbente,tempo_inicio
        if event == 'Solution':
            tempo_incumbente = time.time()
            #print(tempo_incumbente-tempo_inicio)

def ler_tarefas(caminho_arquivo: str | Path) -> List[Task]:
    """Ler tarefas em formato: tempo1 intervalo tempo2."""

    tarefas: List[Task] = []
    caminho = Path(caminho_arquivo)

    print(f"Lendo arquivo: {caminho}")

    with caminho.open("r", encoding="utf-8") as arquivo:
        for indice, linha in enumerate(arquivo, start=0):
            linha = linha.strip()
            if not linha:
                continue

            partes = linha.split()
            if len(partes) != 3:
                raise ValueError(
                    f"Linha {indice} invalida em {caminho}: esperado 3 numeros, recebido {len(partes)}"
                )

            tempo1, intervalo, tempo2 = map(int, partes)
            tempo_total = tempo1 + intervalo + tempo2
            tarefas.append((indice, tempo1, intervalo, tempo2, tempo_total))
            print(
                f"Tarefa {indice}: tempo1={tempo1}, intervalo={intervalo}, tempo2={tempo2}, tempo_total={tempo_total}"
            )

    print(f"Total de tarefas lidas: {len(tarefas)}")
    return tarefas


def ordenar_por_tempo_total(tarefas: List[Task]) -> List[Task]:
    return sorted(tarefas, key=lambda tarefa: tarefa[4], reverse=True)


def ordenar_por_intervalo(tarefas: List[Task]) -> List[Task]:
    return sorted(tarefas, key=lambda tarefa: tarefa[2], reverse=True)


def extrair_indices(tarefas: List[Task]) -> List[int]:
    return [tarefa[0] for tarefa in tarefas]


def montar_lista_encadeada(tarefas: List[Task]) -> List[int]:
    if not tarefas:
        return []

    restantes = tarefas.copy()
    primeira = max(restantes, key=lambda tarefa: (tarefa[2], tarefa[4]))
    cadeia = [primeira[0]]
    restantes.remove(primeira)

    intervalo_atual = primeira[2]
    print(
        f"\nInicio da cadeia: tarefa {primeira[0]} com intervalo={primeira[2]} e tempo_total={primeira[4]}"
    )

    while True:
        candidatos = [
            tarefa for tarefa in restantes if tarefa[4] <= intervalo_atual]
        print(
            f"Procurando tarefa que caiba no intervalo {intervalo_atual}: {[tarefa[0] for tarefa in candidatos]}"
        )

        if not candidatos:
            break

        proxima = max(candidatos, key=lambda tarefa: (tarefa[4], tarefa[2]))
        cadeia.append(proxima[0])
        restantes.remove(proxima)

        print(
            f"Escolhida tarefa {proxima[0]} com tempo_total={proxima[4]} e intervalo={proxima[2]}"
        )

        intervalo_atual = proxima[2]

    print(f"Cadeia final de indices: {cadeia}")
    return cadeia


def melhor_subconjunto(candidatos: List[Task], capacidade: int, limite_qtd: int) -> List[Task]:
    """Escolhe o conjunto de tarefas que melhor preenche um intervalo.

    Procura o subconjunto de 'candidatos' cuja soma dos tempos totais chega o
    mais perto possivel de 'capacidade' sem ultrapassa-la, usando no maximo
    'limite_qtd' tarefas. Aproximar a soma da capacidade e o mesmo que deixar o
    menor gap (sobra). E um subset-sum resolvido por programacao dinamica."""

    # so interessam tarefas que cabem sozinhas dentro do intervalo
    candidatos = [tarefa for tarefa in candidatos if 0 < tarefa[4] <= capacidade]
    if not candidatos or limite_qtd <= 0:
        return []

    # somas[k] guarda, para cada soma alcancavel usando k tarefas,
    # a lista de tarefas que produz aquela soma
    somas = [dict() for _ in range(limite_qtd + 1)]
    somas[0][0] = []

    for tarefa in candidatos:
        tempo_total = tarefa[4]
        # percorre k de tras para frente para nao reutilizar a mesma tarefa
        for k in range(limite_qtd - 1, -1, -1):
            for soma_atual, escolhidas in list(somas[k].items()):
                nova_soma = soma_atual + tempo_total
                if nova_soma <= capacidade and nova_soma not in somas[k + 1]:
                    somas[k + 1][nova_soma] = escolhidas + [tarefa]

    # entre todas as somas possiveis, pega a maior (menor gap);
    # em caso de empate, prefere usar menos tarefas
    melhor_lista: List[Task] = []
    melhor_soma = -1
    for k in range(limite_qtd + 1):
        for soma, escolhidas in somas[k].items():
            if soma > melhor_soma or (soma == melhor_soma and len(escolhidas) < len(melhor_lista)):
                melhor_soma = soma
                melhor_lista = escolhidas
    return melhor_lista


def montar_agrupamentos_menor_gap(tarefas: List[Task], percentual: float = 0.15) -> List[List[int]]:
    """Versao paralela a montar_lista_encadeada.

    Em montar_lista_encadeada, dentro do intervalo da ancora encaixamos a maior
    tarefa total. Aqui, encaixamos o conjunto de tarefas que melhor preenche o
    intervalo (menor desperdicio de tempo). Cada agrupamento e uma lista
    [ancora, encaixe1, encaixe2, ...]. Somando todos os agrupamentos, no maximo
    'percentual' das tarefas (em quantidade) sao utilizadas."""
    if not tarefas:
        return []

    orcamento = int(len(tarefas) * percentual)
    print(f"\nOrcamento de tarefas para os agrupamentos: {orcamento} ({percentual * 100:.0f}% de {len(tarefas)})")
    if orcamento < 2:
        print("Orcamento insuficiente para formar agrupamentos.")
        return []

    restantes = tarefas.copy()
    agrupamentos = []
    tarefas_usadas = 0

    while tarefas_usadas < orcamento and restantes:
        ancora = max(restantes, key=lambda tarefa: (tarefa[2], tarefa[4]))
        capacidade = ancora[2]
        # o -1 reserva a propria ancora dentro do orcamento de tarefas
        limite_qtd = orcamento - tarefas_usadas - 1
        if limite_qtd < 1:
            break

        print(f"\nAncora: tarefa {ancora[0]} com intervalo={capacidade}")
        candidatos = [tarefa for tarefa in restantes if tarefa is not ancora]
        encaixes = melhor_subconjunto(candidatos, capacidade, limite_qtd)
        if not encaixes:
            print("Nenhuma tarefa cabe no intervalo da ancora. Encerrando.")
            break

        restantes.remove(ancora)
        for tarefa in encaixes:
            restantes.remove(tarefa)
        tarefas_usadas += 1 + len(encaixes)

        soma = sum(tarefa[4] for tarefa in encaixes)
        gap = capacidade - soma
        cadeia = [ancora[0]] + [tarefa[0] for tarefa in encaixes]
        agrupamentos.append(cadeia)
        print(f"Encaixadas {[tarefa[0] for tarefa in encaixes]} com soma={soma} e gap={gap}")

    print(f"Agrupamentos finais de indices: {agrupamentos}")
    return agrupamentos


def criaModelo(tarefas:List[Task]):
    # criar o modelo do CTSP
    modelo = CpoModel()

    # quantidade de tarefas
    qtdTasks = len(tarefas)

    # vamos criar as tarefas
    tasks = [0]*(qtdTasks*2)
    for i in range(qtdTasks):
        duracao_a = tarefas[i][1]
        delay = tarefas[i][2]
        duracao_b = tarefas[i][3]

        # parte A de cada tarefa
        tasks[i] = modelo.interval_var(length=duracao_a, name=f"A{i}")
        # parte B de cada tarefa
        tasks[i+qtdTasks] = modelo.interval_var(length=duracao_b, name=f"B{i}")
        # a parte B deve começar após o encerramento de A e depois de um intervalo
        modelo.add(modelo.start_of(
            tasks[i+qtdTasks]) == modelo.end_of(tasks[i])+delay)

    # as tarefas não podem se sobrepor
    modelo.add(modelo.no_overlap(tasks))

    # o makespan é o maior valor de encerramento de qualquer parte B
    makespan = modelo.max([modelo.end_of(tasks[i+qtdTasks])
                          for i in range(qtdTasks)])
    modelo.minimize(makespan)

    #callback serve para anotarmos o tempo da melhor solução encontrada
    modelo.add_solver_callback(MyCallback())

    return modelo,tasks

def adicionaEncaixes(modelo,tasks,lista_encaixe):
    #qauntidade de tarefas da instância
    qtdTarefas = len(tasks)//2
    
    #adicionando os encaixes
    for i in range(len(lista_encaixe)-1):
        indice1 = lista_encaixe[i]
        indice2 = lista_encaixe[i+1]
        print(f"Tarefa {indice2} será colocada dentro da tarefa {indice1}")
        A1 = tasks[indice1]
        B1 = tasks[indice1+qtdTarefas]
        A2 = tasks[indice2]
        B2 = tasks[indice2+qtdTarefas]
        modelo.add(modelo.start_of(A2) >= modelo.end_of(A1))
        modelo.add(modelo.end_of(B2) <= modelo.start_of(B1))

    return modelo

def executaModelo(modelo,tempo_limite):
    global tempo_inicio
    # marcar o tempo de início
    tempo_inicio = time.time()

    # vamos resolver o modelo
    #modelo.export_model(f"{nome_instancia}.cpo")
    resp = modelo.solve(TimeLimit=tempo_limite, LogVerbosity="Terse")

    # marcar o tempo de fim
    tempo_fim = time.time()
    tempo_execucao = tempo_fim - tempo_inicio
    status_resposta = resp.get_solve_status() if resp is not None else None
    solucao_encontrada = bool(resp and resp.is_solution())

    resultado = {
        'tempo_solucao': tempo_incumbente-tempo_inicio,
        'tempo_execucao': tempo_execucao,
        'solucao_encontrada': solucao_encontrada,
        'status': str(status_resposta) if status_resposta is not None else 'Sem resposta'
    }

    if solucao_encontrada:
        resultado['valor_objetivo'] = resp.get_objective_value()
        resultado['melhor_bound'] = resp.get_objective_bound()
        resultado['gap'] = abs(resultado['valor_objetivo'] - resultado['melhor_bound']) / \
            resultado['melhor_bound']
    else:
        resultado['valor_objetivo'] = None
        resultado['melhor_bound'] = resp.get_objective_bound(
        ) if resp is not None else None
        resultado['gap'] = None

    return resultado


def main() -> None:
    if len(sys.argv)<2:
        print("Deve ser informado o nome da instância")
        exit(-1)
        
    filename = "inst\\Single machine\\General set\\"+sys.argv[1]
    
    print("\nTarefas carregadas (indice, duracaoA, intervalo, duracaoB, tempoTotal):")
    tarefas = ler_tarefas(filename)
    print(tarefas)

    print("\nOrdenacao por tempo total (detalhada):")
    tarefas_por_tempo_total = ordenar_por_tempo_total(tarefas)
    print(tarefas_por_tempo_total)

    print("\nOrdenacao por intervalo (detalhada):")
    tarefas_por_intervalo = ordenar_por_intervalo(tarefas)
    print(tarefas_por_intervalo)

    print("Lista por maior tempo total:")
    por_tempo_total = extrair_indices(tarefas_por_tempo_total)
    print(por_tempo_total)

    print("Lista por maior intervalo:")
    por_intervalo = extrair_indices(tarefas_por_intervalo)
    print(por_intervalo)

    print("Lista encadeada por intervalo e tempo total:")
    lista_encadeada = montar_lista_encadeada(tarefas)
    print(lista_encadeada)

    #cria o modelo contendo as tasks
    modelo,tasks = criaModelo(tarefas)

    #adiciona os encaixes a partir da lista encadeada (completa)
    modelo = adicionaEncaixes(modelo,tasks,lista_encadeada)

    #executa o modelo por 600 segundos
    resultado = executaModelo(modelo,600)

    melhorSolucao = resultado['valor_objetivo']
    melhorBound = resultado['melhor_bound']
    tempoTotal = resultado['tempo_execucao']
    tempoSolucao = resultado['tempo_solucao']
    
    # Mostrar progresso
    if resultado['solucao_encontrada']:
        print(f"  ✓ Resolvido - Obj: {melhorSolucao}, Bound: {melhorBound}, Tempo Total: {tempoTotal:.2f}, Tempo Solução: {tempoSolucao:.2f}s")
    else:
        print(f"  ✗ Sem solução - Tempo: {tempoTotal:.2f}s")
        
    #escreve os resultados no arquivo "resuktadosPython.txt"
    with open("resultadosPython.txt","a") as arq:
        print(f"{sys.argv[1]} {melhorSolucao} {melhorBound} {tempoTotal:.2f} {tempoSolucao:.2f}",file=arq)

if __name__ == "__main__":
    main()
