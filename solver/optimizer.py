import os
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

# ---------------------------------------------------
# LOGGING
# ---------------------------------------------------

logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------
# LOAD DATA
# ---------------------------------------------------

def load_data():

    BASE_DIR = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    data_path = os.path.join(BASE_DIR, 'data')

    factories = pd.read_csv(
        os.path.join(data_path, 'factories.csv')
    )

    warehouses = pd.read_csv(
        os.path.join(data_path, 'warehouses.csv')
    )

    dealers = pd.read_csv(
        os.path.join(data_path, 'dealers.csv')
    )

    fw = pd.read_csv(
        os.path.join(data_path, 'factory_to_warehouse.csv')
    )

    wd = pd.read_csv(
        os.path.join(data_path, 'warehouse_to_dealer.csv')
    )

    return factories, warehouses, dealers, fw, wd


# ---------------------------------------------------
# SOLVE MODEL
# ---------------------------------------------------

def solve_model():

    logging.info("Loading datasets...")

    factories, warehouses, dealers, fw, wd = load_data()

    # ---------------------------------------------------
    # SUPPLY & DEMAND
    # ---------------------------------------------------

    supply = dict(
        zip(
            factories.factory_id,
            factories.supply
        )
    )

    demand = dict(
        zip(
            dealers.dealer_id,
            dealers.demand
        )
    )

    # ---------------------------------------------------
    # COST DICTIONARIES
    # ---------------------------------------------------

    fw_cost = {}

    for _, row in fw.iterrows():

        fw_cost[
            (row['from_factory'], row['to_warehouse'])
        ] = row['transport_cost']

    wd_cost = {}

    for _, row in wd.iterrows():

        wd_cost[
            (row['from_warehouse'], row['to_dealer'])
        ] = row['transport_cost']

    # ---------------------------------------------------
    # MODEL
    # ---------------------------------------------------

    model = LpProblem(
        "Smart_Transshipment_System",
        LpMinimize
    )

    # ---------------------------------------------------
    # DECISION VARIABLES
    # ---------------------------------------------------

    x = LpVariable.dicts(
        "FW",
        fw_cost.keys(),
        lowBound=0,
        cat='Continuous'
    )

    y = LpVariable.dicts(
        "WD",
        wd_cost.keys(),
        lowBound=0,
        cat='Continuous'
    )

    # ---------------------------------------------------
    # OBJECTIVE FUNCTION
    # ---------------------------------------------------

    model += (

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

    # ---------------------------------------------------
    # FACTORY SUPPLY CONSTRAINTS
    # ---------------------------------------------------

    for f in factories.factory_id:

        model += (

            lpSum(
                x[(f, w)]
                for w in warehouses.warehouse_id
            )

            <= supply[f]

        )

    # ---------------------------------------------------
    # DEALER DEMAND CONSTRAINTS
    # ---------------------------------------------------

    for d in dealers.dealer_id:

        model += (

            lpSum(
                y[(w, d)]
                for w in warehouses.warehouse_id
            )

            >= demand[d]

        )

    # ---------------------------------------------------
    # WAREHOUSE FLOW BALANCE
    # ---------------------------------------------------

    for w in warehouses.warehouse_id:

        model += (

            lpSum(
                x[(f, w)]
                for f in factories.factory_id
            )

            ==

            lpSum(
                y[(w, d)]
                for d in dealers.dealer_id
            )

        )

    # ---------------------------------------------------
    # SOLVE
    # ---------------------------------------------------

    logging.info("Solving optimization model...")

    model.solve()

    logging.info("Optimization completed")

    # ---------------------------------------------------
    # ROUTE EXTRACTION
    # ---------------------------------------------------

    routes_fw = []
    routes_wd = []

    for v in model.variables():

        if v.varValue > 0:

            name = v.name

            # -------------------------------------------
            # FACTORY -> WAREHOUSE
            # -------------------------------------------

            if "FW" in name:

                clean_name = (
                    name
                    .replace("FW_", "")
                    .replace("_", " ")
                    .replace("(", "")
                    .replace(")", "")
                    .replace("'", "")
                    .replace(",", " → ")
                )

                routes_fw.append({

                    'route': f"Factory {clean_name}",

                    'quantity': round(
                        v.varValue,
                        2
                    )

                })

            # -------------------------------------------
            # WAREHOUSE -> DEALER
            # -------------------------------------------

            elif "WD" in name:

                clean_name = (
                    name
                    .replace("WD_", "")
                    .replace("_", " ")
                    .replace("(", "")
                    .replace(")", "")
                    .replace("'", "")
                    .replace(",", " → ")
                )

                routes_wd.append({

                    'route': f"Warehouse {clean_name}",

                    'quantity': round(
                        v.varValue,
                        2
                    )

                })

    # ---------------------------------------------------
    # CREATE GRAPH
    # ---------------------------------------------------

    create_graph(
        routes_fw,
        routes_wd
    )

    # ---------------------------------------------------
    # RESULT DICTIONARY
    # ---------------------------------------------------

    result = {

        'status': LpStatus[model.status],

        'minimum_cost': round(
            value(model.objective),
            2
        ),

        'factory_routes': routes_fw,

        'warehouse_routes': routes_wd,

        'total_factories': len(factories),

        'total_warehouses': len(warehouses),

        'total_dealers': len(dealers),

        'total_routes': (
            len(routes_fw)
            +
            len(routes_wd)
        )

    }

    return result


# ---------------------------------------------------
# GRAPH CREATION
# ---------------------------------------------------

def create_graph(routes_fw, routes_wd):

    logging.info("Generating network graph...")

    G = nx.DiGraph()

    edge_labels = {}

    # ---------------------------------------------------
    # FACTORY -> WAREHOUSE
    # ---------------------------------------------------

    for r in routes_fw:

        text = r['route']

        text = text.replace(
            "Factory ",
            ""
        )

        parts = text.split("→")

        source = parts[0].strip()

        target = parts[1].strip()

        quantity = r['quantity']

        G.add_edge(
            source,
            target
        )

        edge_labels[
            (source, target)
        ] = quantity

    # ---------------------------------------------------
    # WAREHOUSE -> DEALER
    # ---------------------------------------------------

    for r in routes_wd:

        text = r['route']

        text = text.replace(
            "Warehouse ",
            ""
        )

        parts = text.split("→")

        source = parts[0].strip()

        target = parts[1].strip()

        quantity = r['quantity']

        G.add_edge(
            source,
            target
        )

        edge_labels[
            (source, target)
        ] = quantity

    # ---------------------------------------------------
    # GRAPH LAYOUT
    # ---------------------------------------------------

    pos = {

        # FACTORIES

        'F1': (-2, 3),
        'F2': (-2, 0),
        'F3': (-2, -3),

        # WAREHOUSES

        'W1': (0, 4),
        'W2': (0, 1),
        'W3': (0, -2),
        'W4': (0, -5),

        # DEALERS

        'D1': (3, 5),
        'D2': (3, 3),
        'D3': (3, 1),
        'D4': (3, -1),
        'D5': (3, -3),
        'D6': (3, -5)

    }

    # ---------------------------------------------------
    # NODE COLORS
    # ---------------------------------------------------

    node_colors = []

    for node in G.nodes():

        if node.startswith("F"):

            node_colors.append(
                "skyblue"
            )

        elif node.startswith("W"):

            node_colors.append(
                "orange"
            )

        else:

            node_colors.append(
                "lightgreen"
            )

    # ---------------------------------------------------
    # DRAW GRAPH
    # ---------------------------------------------------

    plt.figure(figsize=(14, 9))

    nx.draw(

        G,
        pos,

        with_labels=True,

        node_size=3500,

        node_color=node_colors,

        font_size=10,

        font_weight='bold',

        arrows=True

    )

    # ---------------------------------------------------
    # EDGE LABELS
    # ---------------------------------------------------

    nx.draw_networkx_edge_labels(

        G,
        pos,

        edge_labels=edge_labels,

        font_size=9

    )

    plt.title(
        "Smart Transshipment Network",
        fontsize=18
    )

    # ---------------------------------------------------
    # SAVE GRAPH
    # ---------------------------------------------------

    os.makedirs(
        "static",
        exist_ok=True
    )

    plt.savefig(

        os.path.join(
            "static",
            "network.png"
        ),

        bbox_inches='tight'

    )

    plt.close()

    logging.info(
        "Network graph saved successfully"
    )

    return G