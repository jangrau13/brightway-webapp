# lca_model.py

import pandas as pd
import numpy as np
import bw2data as bd
import bw2calc as bc
from bw2data.errors import UnknownObject
import bw_graph_tools as bgt
from bw2data.backends.proxies import Activity
from utils import brightway_wasm_database_storage_workaround, create_sanitized_key
from constants import DATABASE_NAME
from sparql_queries import get_activity_labels, get_biosphere, get_technosphere

class PanelLCA:
    """
    This class stores all necessary information for the LCA calculation.
    """

    def __init__(self):
        brightway_wasm_database_storage_workaround()
        self.db_name = DATABASE_NAME
        self.db = None
        self.list_db_products = []
        self.dict_label_to_src = {}
        self.dict_db_methods = {}
        self.list_db_methods = []
        self.chosen_activity = ''
        self.chosen_method = ''
        self.chosen_method_unit = ''
        self.chosen_amount = 0
        self.lca = None
        self.scope_dict = {'Scope 1': 0, 'Scope 2': 0, 'Scope 3': 0}
        self.graph_traversal_cutoff = 1
        self.graph_traversal = {}
        self.df_graph_traversal_nodes = None
        self.df_graph_traversal_edges = None
        self.df_tabulator_from_traversal = None
        self.df_tabulator_from_user = None
        self.df_tabulator = None
        self.bool_user_provided_data = False

    def set_db(self):
        """
        Checks if the database exists, if not, creates it.
        """
        if self.db_name not in bd.projects:
            bd.projects.set_current(self.db_name)
            self.create_empty_db_with_co2_and_ipcc_sample()
        else:
            bd.projects.set_current(name=self.db_name)
        self.db = bd.Database(self.db_name)

    def create_empty_db_with_co2_and_ipcc_sample(self):
        """
        Creates a new Brightway database and registers it.
        """
        db = bd.Database(self.db_name)
        db.register()
        co2 = db.new_node(
            code='co2',
            name="Carbon Dioxide",
            categories=('air',),
            type='emission',
            unit='kg'
        )
        co2.save()
        ipcc = bd.Method(('IPCC',))
        ipcc.write([
            (co2.key, {'amount': 1, 'uncertainty_type': 3, 'loc': 1, 'scale': 0.05}),
        ])

    def set_list_db_products(self):
        """
        Sets `list_db_products` to a list of product names (srcLabels) from the database
        and creates a reverse dictionary `dict_label_to_src` mapping each srcLabel to its src.
        """
        labels = get_activity_labels()  # Get list of dicts with 'src' and 'srcLabel'
        
        # Extract only the srcLabel values for list_db_products
        self.list_db_products = [label['srcLabel'] for label in labels]
        
        # Create a dictionary mapping srcLabel to src for quick reverse lookup
        self.dict_label_to_src = {label['srcLabel']: label['src'] for label in labels}

    def get_src_and_get_technosphere_and_biosphere(self, srcValue):
        """
        Fetches and adds technosphere and biosphere information for the provided srcValue to the Brightway database,
        ensuring nodes and edges are only added if they do not already exist.

        Parameters
        ----------
        srcValue : str
            The srcLabel for the selected activity in the database.
        """
        # Step 1: Extract the `src` from `dict_label_to_src`
        selected_src = self.dict_label_to_src.get(srcValue)
        if not selected_src:
            raise ValueError(f"The src value for '{srcValue}' could not be found.")

        # Initialize database object
        database = bd.Database(self.db_name)
        
        # Step 2: Query technosphere and biosphere
        technosphere_data = get_technosphere(selected_src)
        biosphere_data = get_biosphere(selected_src)
        
        # Step 3: Add Technosphere nodes and edges to the Brightway database
        for entry in technosphere_data:
            # Sanitize codes for parent and child elements
            parent_code = create_sanitized_key(entry['parentElement'])
            child_code = create_sanitized_key(entry['childElement'])
            parent_name = entry['parent']
            child_name = entry['child']
            parent_location = entry.get('parentLocation', 'GLO')
            child_location = entry.get('location', 'GLO')
            parent_unit = entry.get('parentUnit', 'unitless')
            child_unit = entry.get('unit', 'unitless')
            
            # Check if parent node exists; if not, create and save it
            parent_node_search = database.search(parent_code)
            parent_node = parent_node_search[0] if parent_node_search else database.new_node(
                code=parent_code,
                name=parent_name,
                categories=('technosphere',),
                location=parent_location,
                unit=parent_unit,
                type='process'
            )
            if not parent_node_search:
                parent_node.save()

            # Check if child node exists; if not, create and save it
            child_node_search = database.search(child_code)
            child_node = child_node_search[0] if child_node_search else database.new_node(
                code=child_code,
                name=child_name,
                categories=('technosphere',),
                location=child_location,
                unit=child_unit,
                type='process'
            )
            if not child_node_search:
                child_node.save()
            
            # Add edge using `new_edge` if there is a defined exchange value
            if 'value' in entry and entry['value']:
                try:
                    parent_node.new_edge(
                        amount=float(entry['value']),
                        type='technosphere',
                        input=child_node.key
                    ).save()
                except UnknownObject:
                    print(f"Error adding edge between {parent_code} and {child_code}")

        # Step 4: Add Biosphere nodes and edges to the Brightway database
        for entry in biosphere_data:
            # Sanitize the code for the biosphere parent element
            parent_code = create_sanitized_key(entry['parentElement'])
            exchange_name = create_sanitized_key(entry['exchangeName'])
            exchange_unit = entry.get('unit', 'unitless')
            
            # Check if biosphere parent node exists; if not, create and save it
            parent_node_search = database.search(parent_code)
            parent_node = parent_node_search[0] if parent_node_search else database.new_node(
                code=parent_code,
                name=entry['srcLabel'],
                categories=('biosphere', entry.get('category', '')),
                unit=exchange_unit,
                type='emission'
            )
            if not parent_node_search:
                parent_node.save()

            # Check if exchange node exists; if not, create and save it
            exchange_node_search = database.search(exchange_name)
            exchange_node = exchange_node_search[0] if exchange_node_search else database.new_node(
                code=exchange_name,
                name=exchange_name,
                categories=('biosphere', entry.get('subCategory', '')),
                unit=exchange_unit,
                type='emission'
            )
            if not exchange_node_search:
                exchange_node.save()
            
            # Add edge using `new_edge` if value is present
            if 'value' in entry and entry['value']:
                try:
                    parent_node.new_edge(
                        amount=float(entry['value']),
                        type='biosphere',
                        input=exchange_node.key
                    ).save()
                except UnknownObject:
                    print(f"Error adding edge for biosphere {parent_code} and exchange {exchange_name}")

        santized_src = create_sanitized_key(selected_src)
        return database.search(santized_src)[0]


    def set_methods_objects(self):
        """
        Sets the methods available in the database.
        """
        dict_methods = {i[-1]: [i] for i in bd.methods}

        dict_methods_names = {
            "HRSP": "Human Health - Respiratory Effects",
            "OZON": "Ozone Depletion",
            "HNC": "Human Health Noncancer",
            "WATR": "Water",
            "METL": "Metals",
            "EUTR": "Eutrophication",
            "HTOX": "Human Health Cancer and Noncancer",
            "LAND": "Land",
            "NREN": "Nonrenewable Energy",
            "ETOX": "Freshwater Aquatic Ecotoxicity",
            "PEST": "Pesticides",
            "REN": "Renewable Energy",
            "MINE": "Minerals and Metals",
            "GCC": "Global Climate Change",
            "ACID": "Acid Rain",
            "HAPS": "Hazardous Air Pollutants",
            "HC": "Human Health Cancer",
            "SMOG": "Smog Formation",
            "ENRG": "Energy",
            "IPCC": "Sample IPCC Method"
        }

        dict_methods_units = {
            "HRSP": "[kg PM2.5 eq]",
            "OZON": "[kg O3 eq]",
            "HNC": "[CTUh]",
            "WATR": "[m3]",
            "METL": "[kg]",
            "EUTR": "[kg N eq]",
            "HTOX": "[CTUh]",
            "LAND": "[m2*yr]",
            "NREN": "[MJ]",
            "ETOX": "[CTUe]",
            "PEST": "[kg]",
            "REN": "[MJ]",
            "MINE": "[kg]",
            "GCC": "[kg CO2 eq]",
            "ACID": "[kg SO2 eq]",
            "HAPS": "[kg]",
            "HC": "[CTUh]",
            "SMOG": "[kg O3 eq]",
            "ENRG": "[MJ]",
            "IPCC": "[kg CO2eq]"
        }

        dict_methods_enriched = {
            key: [dict_methods[key][0], dict_methods_names[key], dict_methods_units[key]]
            for key in dict_methods
        }

        list_methods_for_autocomplete = [(key, value[1], value[2]) for key, value in dict_methods_enriched.items()]

        self.dict_db_methods = dict_methods_enriched
        self.list_db_methods = list_methods_for_autocomplete

    def set_chosen_activity(self, activity_name):
        """
        Sets `chosen_activity` to the Activity object of the chosen product.
        """
        self.chosen_activity: Activity = bd.get_node(
            database=self.db_name,
            name=activity_name,
        )

    def set_chosen_method_and_unit(self, method_value):
        """
        Sets `chosen_method` to the method tuple corresponding to the chosen method string.
        """
        if self.dict_db_methods:
            self.chosen_method = bd.Method(self.dict_db_methods[method_value[0]][0])
            self.chosen_method_unit = method_value[2]

    def set_chosen_amount(self, amount_value):
        """
        Sets `chosen_amount` to the float value from the amount input.
        """
        self.chosen_amount = amount_value

    def perform_lca(self):
        """
        Performs the LCA calculation using the chosen product, method, and amount.
        """
        self.lca = bc.LCA(
            demand={self.chosen_activity: self.chosen_amount},
            method=self.chosen_method.name
        )
        self.lca.lci()
        self.lca.lcia()

    def set_graph_traversal_cutoff(self, cutoff_value):
        """
        Sets the `graph_traversal_cutoff` attribute.
        """
        self.graph_traversal_cutoff = cutoff_value

    def perform_graph_traversal(self):
        """
        Performs graph traversal.
        """
        self.graph_traversal: dict = bgt.NewNodeEachVisitGraphTraversal.calculate(
            self.lca, cutoff=self.graph_traversal_cutoff
        )
        self.df_graph_traversal_nodes: pd.DataFrame = nodes_dict_to_dataframe(self.graph_traversal['nodes'])
        self.df_graph_traversal_edges: pd.DataFrame = edges_dict_to_dataframe(self.graph_traversal['edges'])
        if not self.df_graph_traversal_edges.empty:
            self.df_graph_traversal_edges = add_branch_information_to_edges_dataframe(self.df_graph_traversal_edges)
            self.df_tabulator_from_traversal = pd.merge(
                self.df_graph_traversal_nodes,
                self.df_graph_traversal_edges,
                left_on='UID',
                right_on='producer_unique_id',
                how='left'
            )
        else:
            self.df_tabulator_from_traversal = self.df_graph_traversal_nodes.copy()

    def update_data_based_on_user_input(self):
        """
        Updates the supply chain data based on user input.
        """
        self.df_tabulator_from_user = create_user_input_columns(
            df_original=self.df_tabulator_from_traversal,
            df_user_input=self.df_tabulator_from_user,
        )
        self.df_tabulator_from_user = determine_edited_rows(df=self.df_tabulator_from_user)
        self.df_tabulator_from_user = update_production_based_on_user_data(df=self.df_tabulator_from_user)
        self.df_tabulator_from_user = update_burden_intensity_based_on_user_data(df=self.df_tabulator_from_user)
        self.df_tabulator_from_user = update_burden_based_on_user_data(self.df_tabulator_from_user)
        self.df_tabulator = self.df_tabulator_from_user.copy()

# Data processing functions

def nodes_dict_to_dataframe(nodes: dict, uid_electricity: int = 53) -> pd.DataFrame:
    """
    Returns a dataframe with human-readable descriptions and emissions values of the nodes in the graph traversal.

    Parameters
    ----------
    nodes : dict
        A dictionary of nodes in the graph traversal.

    Returns
    -------
    pd.DataFrame
        A dataframe with human-readable descriptions and emissions values of the nodes in the graph traversal.
    """
    list_of_row_dicts = []
    for current_node in nodes.values():
        scope: int = 3
        if current_node.unique_id == -1:
            continue
        elif current_node.unique_id == 0:
            scope = 1
        elif current_node.activity_datapackage_id == uid_electricity:
            scope = 2
        list_of_row_dicts.append(
            {
                'UID': current_node.unique_id,
                'Scope': scope,
                'Name': bd.get_node(id=current_node.activity_datapackage_id)['name'],
                'SupplyAmount': current_node.supply_amount,
                'BurdenIntensity': current_node.direct_emissions_score / current_node.supply_amount if current_node.supply_amount else 0,
                'Burden(Direct)': current_node.direct_emissions_score + current_node.direct_emissions_score_outside_specific_flows,
                'Depth': current_node.depth,
                'activity_datapackage_id': current_node.activity_datapackage_id,
            }
        )
    return pd.DataFrame(list_of_row_dicts)

def edges_dict_to_dataframe(edges: list) -> pd.DataFrame:
    """
    Converts a list of edges into a dataframe.

    Parameters
    ----------
    edges : list
        A list of Edge objects.

    Returns
    -------
    pd.DataFrame
        A dataframe representing the edges.
    """
    if len(edges) < 2:
        return pd.DataFrame()
    else:
        list_of_row_dicts = []
        for current_edge in edges:
            list_of_row_dicts.append(
                {
                    'consumer_unique_id': current_edge.consumer_unique_id,
                    'producer_unique_id': current_edge.producer_unique_id
                }
            )
        return pd.DataFrame(list_of_row_dicts).drop(0)

def trace_branch(df: pd.DataFrame, start_node: int) -> list:
    """
    Given a dataframe of graph edges and a "starting node", returns the branch of nodes that lead to the starting node.

    Parameters
    ----------
    df : pd.DataFrame
        Dataframe of graph edges. Must contain integer-type columns 'consumer_unique_id' and 'producer_unique_id'.
    start_node : int
        The integer indicating the producer_unique_id starting node to trace back from.

    Returns
    -------
    list
        A list of integers indicating the branch of nodes that lead to the starting node.
    """

    branch: list = [start_node]

    while True:
        previous_node_series = df[df['producer_unique_id'] == start_node]['consumer_unique_id']
        if previous_node_series.empty:
            break
        start_node = previous_node_series.values[0]
        branch.insert(0, start_node)

    return branch

def add_branch_information_to_edges_dataframe(df_edges: pd.DataFrame) -> pd.DataFrame:
    """
    Adds 'Branch' information to terminal nodes in a dataframe of graph edges.

    Parameters
    ----------
    df_edges : pd.DataFrame
        A dataframe of graph edges.

    Returns
    -------
    pd.DataFrame
        A dataframe with 'Branch' column added.
    """
    branches: list = []

    for _, row in df_edges.iterrows():
        branch: list = trace_branch(df_edges, int(row['producer_unique_id']))
        branches.append({
            'producer_unique_id': int(row['producer_unique_id']),
            'Branch': branch
        })

    return pd.DataFrame(branches)

def create_user_input_columns(
        df_original: pd.DataFrame,
        df_user_input: pd.DataFrame,
    ) -> pd.DataFrame:
    """
    Creates new columns in the 'original' DataFrame where only the
    user-supplied values are kept. The other values are replaced by NaN.

    Parameters
    ----------
    df_original : pd.DataFrame
        Original DataFrame.

    df_user_input : pd.DataFrame
        User input DataFrame.

    Returns
    -------
    pd.DataFrame
        A dataframe with user input columns.
    """

    df_merged = pd.merge(
        df_original,
        df_user_input[['UID', 'SupplyAmount', 'BurdenIntensity']],
        on='UID',
        how='left',
        suffixes=('', '_USER')
    )

    for column_name in ['SupplyAmount', 'BurdenIntensity']:
        df_merged[f'{column_name}_USER'] = np.where(
            df_merged[f'{column_name}_USER'] != df_merged[f'{column_name}'],
            df_merged[f'{column_name}_USER'],
            np.nan
        )

    return df_merged

def update_burden_intensity_based_on_user_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Updates the burden intensity when user data is provided.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe.

    Returns
    -------
    pd.DataFrame
        Output dataframe with updated burden intensity.
    """

    df['BurdenIntensity'] = df['BurdenIntensity_USER'].combine_first(df['BurdenIntensity'])
    df = df.drop(columns=['BurdenIntensity_USER'])

    return df

def update_production_based_on_user_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Updates the production amount of all nodes which are upstream
    of a node with user-supplied production amount.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame. Must have the columns 'SupplyAmount', 'SupplyAmount_USER', and 'Branch'.

    Returns
    -------
    pd.DataFrame
        Output DataFrame with updated production amounts.
    """

    df_filtered = df[~df['SupplyAmount_USER'].isna()]
    dict_user_input = df_filtered.set_index('UID')['SupplyAmount_USER'].to_dict()

    df = df.copy(deep=True)

    def adjust_supply_amount(row):
        if not isinstance(row['Branch'], list):
            return row['SupplyAmount']
        elif row['UID'] == row['Branch'][-1] and not np.isnan(row['SupplyAmount_USER']):
            return row['SupplyAmount_USER']
        else:
            for branch_UID in reversed(row['Branch']):
                if branch_UID in dict_user_input:
                    user_supply = dict_user_input[branch_UID]
                    original_supply = df.loc[df['UID'] == branch_UID, 'SupplyAmount'].values[0]
                    if original_supply != 0:
                        ratio = user_supply / original_supply
                        return row['SupplyAmount'] * ratio
            return row['SupplyAmount']

    df['SupplyAmount'] = df.apply(adjust_supply_amount, axis=1)
    df.drop(columns=['SupplyAmount_USER'], inplace=True)

    return df

def update_burden_based_on_user_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Updates the environmental burden of nodes by multiplying the burden intensity and the supply amount.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe.

    Returns
    -------
    pd.DataFrame
        Output dataframe with updated burdens.
    """

    df['Burden(Direct)'] = df['SupplyAmount'] * df['BurdenIntensity']
    return df

def determine_edited_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Determines which rows have been edited by the user.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe.

    Returns
    -------
    pd.DataFrame
        Dataframe with 'Edited?' column indicating if the row has been edited.
    """
    df['Edited?'] = df[['SupplyAmount_USER', 'BurdenIntensity_USER']].notnull().any(axis=1)
    return df
