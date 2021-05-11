from mip.constants import BINARY, CBC, CONTINUOUS, GUROBI, INTEGER, MINIMIZE
import networkx as nx
from mip.model import *
from time import time
import csv
import os
import argparse

from networkx.classes.function import is_directed

class LoadBalancingEE:

    def __init__(self, topo: nx.Graph, use_cbc: bool, w_max: float):
        self.__topo = topo
        self.__w_max = w_max
        self.__vars = {}
        self.__report_info = {}
        if use_cbc:
            self.__model = Model(sense=MINIMIZE, solver_name=CBC)
        else:
            self.__model = Model(sense=MINIMIZE, solver_name=GUROBI)
    
    def __create_vars(self) -> None:
        x_vars = {}
        f_vars = {}
        n_vars = {}
        p_vars = {}
        w_vars = {}
        for link in self.__topo.edges:
            x_vars[(link[0], link[1])] = self.__model.add_var("x_{}_{}".format(link[0], link[1]), var_type=BINARY)
            w_vars[(link[0], link[1])] = self.__model.add_var("w_{}_{}".format(link[0], link[1]), var_type=INTEGER, lb=1, ub=self.__w_max)
            if not self.__topo.is_directed():
                x_vars[(link[1], link[0])] = self.__model.add_var("x_{}_{}".format(link[1], link[0]), var_type=BINARY)
                w_vars[(link[1], link[0])] = self.__model.add_var("w_{}_{}".format(link[1], link[0]), var_type=INTEGER, lb=1, ub=self.__w_max)
            for node in self.__topo.nodes:
                n_vars[(node, link[0], link[1])] = self.__model.add_var("n_{}_{}_{}".format(node, link[0], link[1]), var_type=BINARY)
                if not self.__topo.is_directed():
                    n_vars[(node, link[1], link[0])] = self.__model.add_var("n_{}_{}_{}".format(node, link[1], link[0]), var_type=BINARY)
                for node_2 in self.__topo.nodes:
                    f_vars[(link[0], link[1], node, node_2)] = self.__model.add_var("f_{}_{}_{}_{}".format(link[0], link[1], node, node_2), var_type=INTEGER)
                    if not self.__topo.is_directed():
                        f_vars[(link[1], link[0], node, node_2)] = self.__model.add_var("f_{}_{}_{}_{}".format(link[1], link[0], node, node_2), var_type=INTEGER)
        for node in self.__topo.nodes:
            for node_2 in self.__topo.nodes:
                if node != node_2:
                    p_vars[(node, node_2)] = self.__model.add_var("p_{}_{}".format(node, node_2), var_type=INTEGER)
        mlu_var = self.__model.add_var("mlu", var_type=CONTINUOUS)        
        self.__vars["x"] = x_vars
        self.__vars["f"] = f_vars
        self.__vars["w"] = w_vars
        self.__vars["n"] = n_vars
        self.__vars["p"] = p_vars
        self.__vars["mlu"] = mlu_var
    
    def __create_constraints(self) -> None:
        # Flow constraints
        for source in self.__topo.nodes:
            for destination in self.__topo.nodes:
                if source != destination:
                    for node in self.__topo.nodes:
                        sum_linexpr = xsum(self.__vars["f"][(node, j, source, destination)] for j in self.__topo[node])-xsum(
                            self.__vars["f"][(j, node, source, destination)] for j in self.__topo[node])
                        if node == source:
                            self.__model.add_constr(sum_linexpr == self.__topo.nodes[source]["traffic"].get(destination, 0))
                        elif node == destination:
                            self.__model.add_constr(sum_linexpr == -self.__topo.nodes[source]["traffic"].get(destination, 0))
                        else:
                            self.__model.add_constr(sum_linexpr == 0)
        # Capacity constraints, MLU and IP flows
        for link in self.__topo.edges:
            capacity = self.__topo.edges[link].get("capacity", 0)/(1 if self.__topo.is_directed() else 2)
            f_sum = xsum(self.__vars["f"][(link[0], link[1], source, destination)] for source in self.__topo.nodes for destination in self.__topo.nodes if source != destination)
            self.__model.add_constr(f_sum <= self.__vars["x"][(link[0], link[1])]*capacity)
            self.__model.add_constr(f_sum*(1/capacity) <= self.__vars["mlu"])
            if not self.__topo.is_directed():
                f_sum_2 = xsum(self.__vars["f"][(link[1], link[0], source, destination)] for source in self.__topo.nodes for destination in self.__topo.nodes if source != destination)
                self.__model.add_constr(f_sum_2 <= self.__vars["x"][(link[1], link[0])]*capacity)
                self.__model.add_constr(f_sum_2*(1/capacity) <= self.__vars["mlu"])
            if not self.__topo.nodes[link[0]]["sdn"]:
                for source in self.__topo.nodes:
                    for destination in self.__topo.nodes:
                        if source != destination:
                            self.__model.add_constr(self.__vars["f"][(link[0], link[1], source, destination)] <= self.__vars["n"][(destination, link[0], link[1])]*self.__topo.nodes[source]["traffic"].get(destination, 0))
            if not self.__topo.is_directed():
                if not self.__topo.nodes[link[1]]["sdn"]:
                    for source in self.__topo.nodes:
                        for destination in self.__topo.nodes:
                            if source != destination:
                                self.__model.add_constr(self.__vars["f"][(link[1], link[0], source, destination)] <= self.__vars["n"][(destination, link[1], link[0])]*self.__topo.nodes[source]["traffic"].get(destination, 0))
            for destination in self.__topo.nodes:
                self.__model.add_constr(0 <= self.__vars["p"][(destination, link[1])]-self.__vars["p"][(destination, link[0])]+self.__vars["w"][(link[0], link[1])])
                self.__model.add_constr(self.__vars["p"][(destination, link[1])]-self.__vars["p"][(destination, link[0])]+self.__vars["w"][(link[0], link[1])] <= (1-self.__vars["n"][(destination, link[0], link[1])])*len(self.__topo.nodes)*3)
                self.__model.add_constr(1-self.__vars["n"][(destination, link[0], link[1])] <= self.__vars["p"][(destination, link[1])]-self.__vars["p"][(destination, link[0])]+self.__vars["w"][(link[0], link[1])])
                if not self.__topo.is_directed():
                    self.__model.add_constr(0 <= self.__vars["p"][(destination, link[0])]-self.__vars["p"][(destination, link[1])]+self.__vars["w"][(link[1], link[0])])
                    self.__model.add_constr(self.__vars["p"][(destination, link[0])]-self.__vars["p"][(destination, link[1])]+self.__vars["w"][(link[1], link[0])] <= (1-self.__vars["n"][(destination, link[1], link[0])])*len(self.__topo.nodes)*3)
                    self.__model.add_constr(1-self.__vars["n"][(destination, link[1], link[0])] <= self.__vars["p"][(destination, link[0])]-self.__vars["p"][(destination, link[1])]+self.__vars["w"][(link[1], link[0])])
        # Next hop constraints
        for i in self.__topo.nodes:
            for d in self.__topo.nodes:
                if i != d:
                    self.__model.add_constr(xsum(self.__vars["n"][(d, i, j)] for j in self.__topo[i]) == 1)
        
    def __create_objective(self, balance_param: float = 0.5):
        # Max energy, used to normalize the value of the second objective between 0 and 1 (like MLU)
        total_energy = sum([self.__topo.edges[e]["power"] for e in self.__topo.edges])
        load_bal = self.__vars["mlu"]
        energy_eff = xsum(self.__vars["x"][e]*self.__topo.edges[e]["power"] for e in self.__topo.edges)/total_energy
        if not self.__topo.is_directed():
            energy_eff = energy_eff + xsum(self.__vars["x"][(e[1], e[0])]*self.__topo.edges[(e[1], e[0])]["power"] for e in self.__topo.edges)/total_energy
        self.__model.objective = minimize(balance_param*load_bal + (1-balance_param)*energy_eff)
    
    def solve_and_export(self, export_file: str, report_file: str = None, balance_param: float = 0.5) -> None:
        self.__report_info["initial_time"] = time()*1000
        self.__create_vars()
        self.__create_constraints()
        self.__create_objective(balance_param)
        opt_status = self.__model.optimize()
        if opt_status == OptimizationStatus.NO_SOLUTION_FOUND or opt_status == OptimizationStatus.INFEASIBLE:
            raise RuntimeError('Infeasible problem')
        else:
            self.__report_info["final_time"] = time()*1000
            with open(export_file, 'w', newline='') as out_csv:
                writer = csv.writer(out_csv)
                writer.writerow(("Variable", "Value"))
                for var in self.__model.vars:
                    writer.writerow((var.name, var.x))
            if report_file is not None:
                with open(report_file, 'w', newline='') as out_rep:
                    writer = csv.writer(out_rep)
                    writer.writerow(("Info", "Value"))
                    for info in self.__report_info:
                        writer.writerow((info, self.__report_info[info]))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Load Balancing and Energy Efficiency optimizer')
    parser.add_argument('-i', required=True, metavar='topology', help='Topology to optimize in a compatible format.')
    parser.add_argument('-o', required=True, metavar='output', help='File to output the solution to in CSV format.')
    parser.add_argument('-wmax', required=True, metavar='w_max', help='Value of wmax in the formulation.', type=float)
    parser.add_argument('-alpha', required=False, default=0.5, metavar='alpha', help="Parameter to balance the objectives. Multiplied by load balancing.", type=float)
    parser.add_argument('-r', required=False, default=None, metavar='report', help='File to output the report to in CSV format.')
    parser.add_argument('--cbc', action='store_true', help='Use Coin-Or Branch (built-in) instead of Gurobi')

    parsed_args = parser.parse_args()

    input_ext = os.path.splitext(parsed_args.i)[1]
    if input_ext == ".pkl":
        topo = nx.read_gpickle(parsed_args.i)
    elif input_ext == '.graphml':
        topo = nx.read_graphml(parsed_args.i)
    elif input_ext == '.leda':
        topo = nx.read_leda(parsed_args.i)
    elif input_ext == '.yaml':
        topo = nx.read_yaml(parsed_args.i)
    elif input_ext == '.pjk':
        topo = nx.read_pajek(parsed_args.i)
    elif input_ext == '.gis':
        topo = nx.read_shp(parsed_args.i)
    else:
        raise RuntimeError("Unsupported format (Wrong extension?)")

    b_par = parsed_args.alpha
    if b_par < 0:
        b_par = 0
    if b_par > 1:
        b_par = 1

    out_file = parsed_args.o
    if os.path.splitext(out_file)[1] != '.csv':
        out_file += '.csv'
    
    rep_file = parsed_args.r
    if rep_file is not None:
        if os.path.splitext(rep_file)[1] != '.csv':
            rep_file += '.csv'
    
    lbee = LoadBalancingEE(topo, parsed_args.cbc, parsed_args.wmax)

    lbee.solve_and_export(out_file, rep_file, b_par)
