from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple


Task = Tuple[int, int, int, int, int]


def ler_tarefas(caminho_arquivo: str | Path) -> List[Task]:
    """Ler tarefas em formato: tempo1 intervalo tempo2."""

    tarefas: List[Task] = []
    caminho = Path(caminho_arquivo)

    print(f"Lendo arquivo: {caminho}")

    with caminho.open("r", encoding="utf-8") as arquivo:
        for indice, linha in enumerate(arquivo, start=1):
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera listas de tarefas ordenadas por tempo total e por intervalo."
    )
    parser.add_argument(
        "arquivo",
        nargs="?",
        default=r"d:\\UFF\\tcc_si\\Coupled task scheduling benchmark\\Coupled task scheduling benchmark\\Single machine\\General set\\20_1_M_gen.txt",
        help="Caminho do arquivo .txt com as tarefas",
    )
    args = parser.parse_args()

    tarefas = ler_tarefas(args.arquivo)

    print("\nTarefas carregadas (indice, tempo1, intervalo, tempo2, tempo_total):")
    print(tarefas)

    tarefas_por_tempo_total = ordenar_por_tempo_total(tarefas)
    tarefas_por_intervalo = ordenar_por_intervalo(tarefas)

    print("\nOrdenacao por tempo total (detalhada):")
    print(tarefas_por_tempo_total)
    print("\nOrdenacao por intervalo (detalhada):")
    print(tarefas_por_intervalo)

    por_tempo_total = extrair_indices(tarefas_por_tempo_total)
    por_intervalo = extrair_indices(tarefas_por_intervalo)
    lista_encadeada = montar_lista_encadeada(tarefas)

    print("Lista por maior tempo total:")
    print(por_tempo_total)
    print()
    print("Lista por maior intervalo:")
    print(por_intervalo)
    print()
    print("Lista encadeada por intervalo e tempo total:")
    print(lista_encadeada)


if __name__ == "__main__":
    main()
