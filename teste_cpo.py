#só que tem que ser a versão 3.10 do Python
#pip install docplex

#importando as bibliotecas do CPLEX
from docplex.cp.model import CpoModel
import docplex.cp.solver.solver as solver

#CP Optimizer

#criar o modelo do CTSP
modelo = CpoModel()

#quantidade de tarefas (ler da instância)
qtdTasks = 15

#vamos criar as tarefas
tasks = [0]*(qtdTasks*2)
for i in range(qtdTasks):
    #parte A de cada tarefa
    tasks[i] = modelo.interval_var(length = i*2+1, name = f"A{i}")
    #parte B de cada tarefa
    tasks[i+qtdTasks] = modelo.interval_var(length = i*4+1, name = f"B{i}")
    #a parte B deve começar após o encerramento de A e depois de um intervalo
    modelo.add(modelo.end_before_start(tasks[i], tasks[i+qtdTasks], delay=i*10))

#as tarefas não podem se sobrepor
modelo.add(modelo.no_overlap(tasks))

#o makespan é o maior valor de encerramento de qualquer parte B
makespan = modelo.max([modelo.end_of(tasks[i+qtdTasks]) for i in range(qtdTasks)])
modelo.minimize(makespan)

#vamos resolver o modelo e pegar os resultados
resp = modelo.solve(TimeLimit=1800, LogVerbosity="Terse")
if resp:
    print(f"Obj:{resp.get_objective_value()} Bound:{resp.get_objective_bound()}")
    for s in resp.get_all_var_solutions():
        print(f"{s.get_name()}:{s.get_start()}->{s.get_end()}")
else:
    print("No solution found")
