import os
import random
import logging

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

from pulp import (
    LpProblem,
    LpMinimize,
    LpVariable,
    lpSum,
    value,
    LpStatus
)

logging.basicConfig(level=logging.INFO)


def load_data():

    base_dir = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    data_path = os.path.join(base_dir, "data")

    factories = pd.read_csv(
        os.path.join(data_path, "factories.csv")
    )

    warehouses = pd.read_csv(
        os.path.join(data_path, "warehouse.csv")
    )

    dealers = pd.read_csv(
        os.path.join(data_path, "dealers.csv")
    )

    fw = pd.read_csv(
        os.path.join(
            data_path,
            "factory_to_warehouse.csv"
        )
    )

    wd = pd.read_csv(
        os.path.join(
            data_path,
            "warehouse_to_dealer.csv"
        )
    )

    return factories, warehouses, dealers, fw, wd


def solve_model():

    factories, warehouses, dealers, fw, wd = load_data()

    supply = dict(
        zip(
            factories["factory_id"],
            factories["supply"]
        )
    )

    capacity = dict(
        zip(
            warehouses["warehouse_id"],
            warehouses["capacity"]
        )
    )

    demand = {}

    for _, row in dealers.iterrows():

        demand[
            row["dealer_id"]
        ] = int(
            row["demand"]
            *
            random.uniform(0.9, 1.1)
        )

    fw_cost = {}
    fw_delay = {}

    for _, row in fw.iterrows():

        key = (
            row["from_factory"],
            row["to_warehouse"]
        )

        fw_cost[key] = row["transport_cost"]
        fw_delay[key] = row["delay_hours"]

    wd_cost = {}
    wd_delay = {}

    for _, row in wd.iterrows():

        key = (
            row["from_warehouse"],
            row["to_dealer"]
        )

        wd_cost[key] = row["transport_cost"]
        wd_delay[key] = row["delay_hours"]

    model = LpProblem(
        "Smart_Transshipment_System",
        LpMinimize
    )

    x = LpVariable.dicts(
        "FW",
        fw_cost.keys(),
        lowBound=0
    )

    y = LpVariable.dicts(
        "WD",
        wd_cost.keys(),
        lowBound=0
    )

    ALPHA = 0.8
    BETA = 0.2

    model += (

        ALPHA *

        (
            lpSum(
                fw_cost[i] * x[i]
                for i in fw_cost
            )

            +

            lpSum(
                wd_cost[i] * y[i]
                for i in wd_cost
            )
        )

        +

        BETA *

        (
            lpSum(
                fw_delay[i] * x[i]
                for i in fw_delay
            )

            +

            lpSum(
                wd_delay[i] * y[i]
                for i in wd_delay
            )
        )

    )

    # Supply constraints

    for f in factories["factory_id"]:

        model += (

            lpSum(
                x[(f, w)]
                for w in warehouses["warehouse_id"]
            )

            <= supply[f]

        )

    # Demand constraints

    for d in dealers["dealer_id"]:

        model += (

            lpSum(
                y[(w, d)]
                for w in warehouses["warehouse_id"]
            )

            >= demand[d]

        )

    # Capacity constraints

    for w in warehouses["warehouse_id"]:

        model += (

            lpSum(
                x[(f, w)]
                for f in factories["factory_id"]
            )

            <= capacity[w]

        )

    # Flow balance

    for w in warehouses["warehouse_id"]:

        model += (

            lpSum(
                x[(f, w)]
                for f in factories["factory_id"]
            )

            ==

            lpSum(
                y[(w, d)]
                for d in dealers["dealer_id"]
            )

        )

    logging.info("Solving model")

    model.solve()

    routes_fw = []
    routes_wd = []

    total_delay = 0

    for key, var in x.items():

        if var.varValue and var.varValue > 0:

            f, w = key

            routes_fw.append({

                "route": f"{f} → {w}",

                "quantity": round(
                    var.varValue,
                    2
                ),

                "delay": fw_delay[key]

            })

            total_delay += fw_delay[key]

    for key, var in y.items():

        if var.varValue and var.varValue > 0:

            w, d = key

            routes_wd.append({

                "route": f"{w} → {d}",

                "quantity": round(
                    var.varValue,
                    2
                ),

                "delay": wd_delay[key]

            })

            total_delay += wd_delay[key]

    create_graph(
        routes_fw,
        routes_wd
    )

    result = {

        "status":
        LpStatus[model.status],

        "minimum_cost":
        round(
            value(model.objective),
            2
        ),

        "total_delay":
        round(
            total_delay,
            2
        ),

        "factory_routes":
        routes_fw,

        "warehouse_routes":
        routes_wd,

        "total_factories":
        len(factories),

        "total_warehouses":
        len(warehouses),

        "total_dealers":
        len(dealers),

        "total_routes":
        len(routes_fw)
        +
        len(routes_wd)

    }

    return result


def create_graph(
    routes_fw,
    routes_wd
):

    G = nx.DiGraph()

    edge_labels = {}

    for route in routes_fw:

        source, target = route[
            "route"
        ].split("→")

        source = source.strip()
        target = target.strip()

        G.add_edge(
            source,
            target
        )

        edge_labels[
            (source, target)
        ] = route["quantity"]

    for route in routes_wd:

        source, target = route[
            "route"
        ].split("→")

        source = source.strip()
        target = target.strip()

        G.add_edge(
            source,
            target
        )

        edge_labels[
            (source, target)
        ] = route["quantity"]

    pos = {
        'F1': (-2, 3),
        'F2': (-2, 0),
        'F3': (-2, -3),

        'W1': (0, 4),
        'W2': (0, 1),
        'W3': (0, -2),
        'W4': (0, -5),

        'D1': (3, 5),
        'D2': (3, 3),
        'D3': (3, 1),
        'D4': (3, -1),
        'D5': (3, -3),
        'D6': (3, -3),
        'D7': (3, -5),
    }

    colors = []

    for node in G.nodes():

        if node.startswith("F"):
            colors.append(
                "skyblue"
            )

        elif node.startswith("W"):
            colors.append(
                "orange"
            )

        else:
            colors.append(
                "lightgreen"
            )

    plt.figure(
        figsize=(12, 8)
    )

    nx.draw(
        G,
        pos,
        with_labels=True,
        node_color=colors,
        node_size=2500,
        font_weight="bold",
        arrows=True
    )

    nx.draw_networkx_edge_labels(
        G,
        pos,
        edge_labels=edge_labels
    )

    os.makedirs(
        "../static",
        exist_ok=True
    )

    plt.title(
        "Smart Transshipment Network"
    )

    BASE_DIR = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    STATIC_DIR = os.path.join(
        BASE_DIR, "static"
    )

    os.makedirs(STATIC_DIR, exist_ok=True)

    plt.savefig(
        os.path.join(
            STATIC_DIR,
            "network.png"
        ),
        bbox_inches="tight"
    )

    plt.close()