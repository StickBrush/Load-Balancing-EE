# How to execute the formulation

## Requirements

To run this formulation, you need Python 3.7.5 or higher, including the PIP package manager (should be installed by default in *NIX systems).

## Getting your input data ready

This formulation uses the [NetworkX](https://networkx.org/) library for topology representation. This library is compatible with the following formats:

- NetworkX graph exported through Pickle (`.pkl`).
- GML (`.gml`).
- GraphML (`.graphml`).
- LEDA (`.leda`).
- YAML (`.yaml`).
- Pajek (`.pjk`).
- GIS Shapefile (`.gis`).

The formulation will infer the format of your data from the file extensions shown.

Within the graph, the formulation will look for the following information **in each of the links**:

- _power_: represents the power consumption of the link. `double` type. Any unit works as long as it is the same for all the topology.
- _capacity_: represents the capacity of the link. `double` type. It must be in the same unit as traffic.

Moreover, it wil look for the following information **in each of the nodes**:

- _sdn_: represents whether the node is IP or SDN. `bool` type. True means SDN, False means IP.
- _traffic_: represents the traffic that the node must send to other given nodes. `dict[str, double]` type, where the key is the target node and the double is the amount of traffic. It must be in the same unit as link capacity.

If your graph is in another format, you will need to convert it. Refer to [the NetworkX documentation on formats](https://networkx.org/documentation/stable/reference/readwrite/index.html) for more information on the allowed formats.

### A note about undirected graphs

The formulation will also accept undirected graphs as input. Undirected graphs will be treated as directed graphs, each of the links becoming two (outgoing and ingoing), and each of the two sub-links having half the capacity of the full link.

## Environment preparation

Simply doing the following command will install all the required libraries:

```bash
# For Windows
pip install -r requirements.txt

# For GNU/Linux or macOS
pip3 install -r requirements.txt
```

It is also recommended to install the [Gurobi solver](http://gurobi.com) for a faster solving. If you cannot, or do not want to install the Gurobi solver, you can use the built-in solver CBC with the `--cbc` flag.

## Launching the formulation

Executing `python formulation.py -h` (Windows) or `python3 formulation.py -h` (GNU/Linux, macOS) will provide a description that should look like this:

```
usage: formulation.py [-h] -i topology -o output -wmax w_max [-alpha alpha]
                      [-r report] [--cbc]

Load Balancing and Energy Efficiency optimizer

optional arguments:
  -h, --help    show this help message and exit
  -i topology   Topology to optimize in a compatible format.
  -o output     File to output the solution to in CSV format.
  -wmax w_max   Value of wmax in the formulation.
  -alpha alpha  Parameter to balance the objectives. Multiplied by load
                balancing.
  -r report     File to output the report to in CSV format.
  --cbc         Use Coin-Or Branch (built-in) instead of Gurobi
```
