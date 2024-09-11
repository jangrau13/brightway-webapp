# %%
import panel as pn
pn.extension(notifications=True)
pn.extension(design='material')
pn.extension('plotly')
pn.extension('tabulator')

# plotting
import plotly

# data science
import pandas as pd

# system
import os

# brightway
import bw_graph_tools as bgt
import bw2io as bi
import bw2data as bd
import bw2calc as bc

# type hints
from bw2data.backends.proxies import Activity
from bw_graph_tools.graph_traversal import Node


def brightway_wasm_database_storage_workaround() -> None:
    """
    Sets the Brightway project directory to `/tmp/.
    
    The JupyterLite file system currently does not support storage of SQL database files
    in directories other than `/tmp/`. This function sets the Brightway environment variable
    `BRIGHTWAY_DIR` to `/tmp/` to work around this limitation.
    
    Notes
    -----
    - https://docs.brightway.dev/en/latest/content/faq/data_management.html#how-do-i-change-my-data-directory
    - https://github.com/brightway-lca/brightway-live/issues/10
    """
    os.environ["BRIGHTWAY_DIR"] = "/tmp/"


def check_for_useeio_brightway_project(event):
    """
    Checks if the USEEIO-1.1 Brightway project is installed.
    If not, installs it. Shows Panel notifications for the user.

    Returns
    -------
    SQLiteBackend
        bw2data.backends.base.SQLiteBackend of the USEEIO-1.1 database
    """
    if 'USEEIO-1.1' not in bd.projects:
        notification_load = pn.state.notifications.info('Loading USEEIO database...')
        bi.install_project(project_key="USEEIO-1.1", overwrite_existing=True)
        notification_load.destroy()
        pn.state.notifications.success('USEEIO database loaded!', duration=7000)
    else:
        pn.state.notifications.success('USEEIO database already loaded!', duration=7000)
        pass
    bd.projects.set_current(name='USEEIO-1.1')


def determine_scope_emissions(df: pd.DataFrame, uid_electricity: int = 53) -> float:
    """
    Given a dataframe of graph nodes and the uid of the electricity production process,
    returns the scope 2 emissions.

    | UID   | Scope 1 | Depth | Cumulative |
    |-------|---------|-------|------------|
    | 0     | True    | 1     | 100        |
    | 1     | True    | 2     | 27         | # known to be scope 1 emissions
    | 2     | False   | 2     | 12         | 
    | (...) | (...)   | 2     | (...)      |
    | 53    | False   | 2     | 6          | # scope 2 emissions
    | (...) | (...)   | (...) | (...)      |

    Since there is only a single electricity production process in the USEEIO database,
    the default value of `uid_electricity` is set to 53:

    ```
    electricity_process: Activity = bd.utils.get_node(
        database = 'USEEIO-1.1',
        name = 'Electricity; at consumer',
        location = 'United States',
        type = 'process'
    )
    uid_electricity_process: int = electricity_process.as_dict()['id']
    ```
    
    Parameters
    ----------
    df : pd.DataFrame
       A dataframe of graph edges.
       Must contain integer-type columns `activity_datapackage_id`, `depth`, `cumulative_score`.

    Returns
    -------
    float
        Scope 2 emissions value.
    """
    dict_scope = {
        'Scope 1': 0,
        'Scope 2': 0,
        'Scope 3': 0
    }

    dict_scope['Scope 1'] = df.loc[
        (df['Depth'] == 1)
        &
        (df['UID'] == 0)
    ]['Cumulative'].values[0]

    dict_scope

    dict_scope['Scope 2'] = df.loc[
        (df['Depth'] == 2)
        &
        (df['UID'] == uid)
    ]['Cumulative'].values[0]

    return dict_scope


def nodes_dict_to_dataframe(nodes: dict) -> pd.DataFrame:
    """
    Returns a dataframe with human-readable descriptions and emissions values of the nodes in the graph traversal.

    Parameters
    ----------
    nodes : dict
        A dictionary of nodes in the graph traversal.
        Can be created by selecting the 'nodes' key from the dictionary
        returned by the function `bw_graph_tools.NewNodeEachVisitGraphTraversal.calculate()`.

    Returns
    -------
    pd.DataFrame
        A dataframe with human-readable descriptions and emissions values of the nodes in the graph traversal.
    """
    list_of_row_dicts = []
    for i in range(0, len(nodes)-1):
        current_node: Node = nodes[i]
        scope_1: bool = False
        if current_node.unique_id == 0:
            scope_1 = True
        else:
            pass
        list_of_row_dicts.append(
            {
                'UID': current_node.unique_id,
                'Scope 1?': scope_1,
                'Name': bd.get_node(id=current_node.activity_datapackage_id)['name'],
                'Cumulative': current_node.cumulative_score,
                'Direct': current_node.direct_emissions_score,
                'Depth': current_node.depth,
            }
        )
    return pd.DataFrame(list_of_row_dicts)


def create_plotly_figure_piechart(data_dict: dict) -> plotly.graph_objects.Figure:
    plotly_figure = plotly.graph_objects.Figure(
        data=[
            plotly.graph_objects.Pie(
                labels=[label for label in data_dict.keys()],
                values=[value for value in data_dict.values()]
            )
        ]
    )
    plotly_figure.update_traces(
        marker=dict(
            line=dict(color='#000000', width=2)
        )
    )
    plotly_figure.update_layout(
        autosize=True,
        height=300,
        legend=dict(
            orientation="v",
            yanchor="auto",
            y=1,
            xanchor="right",
            x=-0.3
        ),
        margin=dict(
            l=50,
            r=50,
            b=0,
            t=0,
            pad=0
        ),
    )
    return plotly_figure


class panel_lca_class:
    """
    This class is used to store all the necessary information for the LCA calculation.
    It provides methods to populate the database and perform Brightway LCA calculations.
    All methods can be bound to a button click event.

    Notes
    -----
    https://discourse.holoviz.org/t/update-global-variable-through-function-bound-with-on-click/
    """
    brightway_wasm_database_storage_workaround()
    def __init__(self):
        self.db_name = 'USEEIO-1.1'
        self.db = None
        self.list_db_products = []
        self.dict_db_methods = {}
        self.chosen_activity = ''
        self.chosen_method = ''
        self.chosen_amount = 0
        self.lca = None
        self.scope_dict = {'Scope 1':0, 'Scope 2':0, 'Scope 3':0}
        self.graph_traversal_cutoff = 0.01
        self.graph_traversal = {}
        self.df_graph_traversal_nodes = None

    def set_db(self, event):
        """
        Checks if the USEEIO-1.1 Brightway project is installed.
        If not, installs it and sets is as current project.
        Else just sets the current project to USEEIO-1.1.
        """
        check_for_useeio_brightway_project(event)
        self.db = bd.Database(self.db_name)

    def set_list_db_products(self, event):
        """
        Sets `list_db_products` to a list of product names from the database for use in the autocomplete widget.
        """
        self.list_db_products = [node['name'] for node in self.db if 'product' in node['type']]
    
    def set_dict_db_methods(self, event):
        """
        Sets `dict_db_methods` to a dictionary of 'method names': (method, tuples) from the database for use in the select widget.
        """
        self.dict_db_methods = {', '.join(i):i for i in bd.methods}
    
    def set_chosen_activity(self, event):
        """
        Sets `chosen_activity` to the `bw2data.backends.proxies.Activity` object of the chosen product from the autocomplete widget.
        """
        self.chosen_activity: Activity = bd.utils.get_node(
            database = self.db_name,
            name = widget_autocomplete_product.value,
            type = 'product',
            location = 'United States'
        )

    def set_chosen_method(self, event):
        """
        Sets `chosen_method` to the (tuple) corresponding to the chosen method string from the select widget.
        """
        self.chosen_method = bd.Method(self.dict_db_methods[widget_select_method.value])

    def set_chosen_amount(self, event):
        """
        Sets `chosen_amount` to the float value from the float input widget.
        """
        self.chosen_amount = widget_float_input_amount.value

    def perform_lca(self, event):
        """
        Performs the LCA calculation using the chosen product, method, and amount.
        Sets the `lca` attribute to an instance of the `bw2calc.LCA` object.
        """
        self.lca = bc.LCA( 
            demand={self.chosen_activity: self.chosen_amount}, 
            method = self.chosen_method.name
        )
        self.lca.lci()
        self.lca.lcia()

    def set_graph_traversal_cutoff(self, event):
        """
        Sets the `graph_traversal_cutoff` attribute to the float value from the float slider widget.
        Note that the value is divided by 100 to convert from percentage to decimal.
        """
        self.graph_traversal_cutoff = widget_float_slider_cutoff.value / 100

    def perform_graph_traversal(self, event):
        self.graph_traversal: dict = bgt.NewNodeEachVisitGraphTraversal.calculate(self.lca, cutoff=self.graph_traversal_cutoff)
        self.df_graph_traversal_nodes: pd.DataFrame = nodes_dict_to_dataframe(self.graph_traversal['nodes'])


    def determine_scope_1_and_2_emissions(self, event):
        """
        Determines the scope 1 and 2 emissions from the graph traversal nodes dataframe.
        """
        dict_scope = {
            'Scope 1': 0,
            'Scope 2': 0,
            'Scope 3': 0
        }
        df = self.df_graph_traversal_nodes
        dict_scope['Scope 1'] = df.loc[(df['Scope 1?'] == True)]['Direct'].values.sum()

        try:
            dict_scope['Scope 2'] = df.loc[
                (df['Depth'] == 2)
                &
                (df['UID'] == uid_scope_2)
            ]['Cumulative'].values[0]
        except:
            pass

        self.scope_dict = dict_scope

    def determine_scope_3_emissions(self, event):
        self.scope_dict['Scope 3'] = self.lca.score - self.scope_dict['Scope 1'] - self.scope_dict['Scope 2']


brightway_wasm_database_storage_workaround()
panel_lca_class_instance = panel_lca_class()

# COLUMN 1 ####################################################################

def button_action_load_database(event):
    panel_lca_class_instance.set_db(event)
    panel_lca_class_instance.set_list_db_products(event)
    panel_lca_class_instance.set_dict_db_methods(event)
    widget_autocomplete_product.options = panel_lca_class_instance.list_db_products
    widget_select_method.options = list(panel_lca_class_instance.dict_db_methods.keys())


def button_action_perform_lca(event):
    if widget_autocomplete_product.value == '':
        pn.state.notifications.error('Please select a reference product first!', duration=5000)
        return
    else:
        pn.state.notifications.info('Calculating LCA score...', duration=5000)
        pass
    panel_lca_class_instance.set_chosen_activity(event)
    panel_lca_class_instance.set_chosen_method(event)
    panel_lca_class_instance.set_chosen_amount(event)
    panel_lca_class_instance.perform_lca(event)
    pn.state.notifications.success('Completed LCA score calculation!', duration=5000)
    widget_number_lca_score.value = panel_lca_class_instance.lca.score


def perform_graph_traversal(event):
    panel_lca_class_instance.perform_graph_traversal(event)
    widget_tabulator.value = panel_lca_class_instance.df_graph_traversal_nodes
    column_editors = {
        colname : {'type': 'editable', 'value': True}
        for colname in panel_lca_class_instance.df_graph_traversal_nodes.columns
        if colname != 'Scope 1?'
    }
    widget_tabulator.editors = column_editors


def perform_scope_analysis(event):
    panel_lca_class_instance.determine_scope_1_and_2_emissions(event)
    panel_lca_class_instance.determine_scope_3_emissions(event)
    widget_plotly_figure_piechart.object = create_plotly_figure_piechart(panel_lca_class_instance.scope_dict)


def button_action_scope_analysis(event):
    if panel_lca_class_instance.lca is None:
        pn.state.notifications.error('Please perform an LCA Calculation first!', duration=5000)
        return
    else:
        if panel_lca_class_instance.df_graph_traversal_nodes is None:
            pn.state.notifications.info('Performing Graph Traversal...', duration=5000)
            pn.state.notifications.info('Performing Scope Analysis...', duration=5000)
            perform_graph_traversal(event)
            perform_scope_analysis(event)
            pn.state.notifications.success('Graph Traversal Complete!', duration=5000)
            pn.state.notifications.success('Scope Analysis Complete!', duration=5000)
        else:
            panel_lca_class_instance.df_graph_traversal_nodes = widget_tabulator.value
            pn.state.notifications.info('Re-Performing Scope Analysis...', duration=5000)
            perform_scope_analysis(event)
            pn.state.notifications.success('Scope Analysis Complete!', duration=5000)


# https://panel.holoviz.org/reference/widgets/Button.html
widget_button_load_db = pn.widgets.Button( 
    name='Load USEEIO Database',
    icon='database-plus',
    button_type='primary',
    sizing_mode='stretch_width'
)
widget_button_load_db.on_click(button_action_load_database)

# https://panel.holoviz.org/reference/widgets/AutocompleteInput.html
widget_autocomplete_product = pn.widgets.AutocompleteInput( 
    name='Reference Product',
    options=[],
    case_sensitive=False,
    search_strategy='includes',
    placeholder='Start typing your product name here...',
    sizing_mode='stretch_width'
)

# https://panel.holoviz.org/reference/widgets/Select.html
widget_select_method = pn.widgets.Select( 
    name='Impact Assessment Method',
    options=[],
    sizing_mode='stretch_width'
)

# https://panel.holoviz.org/reference/widgets/FloatInput.html
widget_float_input_amount = pn.widgets.FloatInput( 
    name='Amount of Reference Product',
    value=1,
    step=1,
    start=0,
    sizing_mode='stretch_width'
)

# https://panel.holoviz.org/reference/widgets/Button.html
widget_button_lca = pn.widgets.Button( 
    name='Compute LCA Score',
    icon='calculator',
    button_type='primary',
    sizing_mode='stretch_width'
)
widget_button_lca.on_click(button_action_perform_lca)

 # https://panel.holoviz.org/reference/widgets/EditableFloatSlider.html
widget_float_slider_cutoff = pn.widgets.EditableFloatSlider(
    name='Graph Traversal Cut-Off [%]',
    start=1,
    end=99,
    step=1,
    value=10,
    sizing_mode='stretch_width'
)

# https://panel.holoviz.org/reference/panes/Markdown.html
markdown_cutoff_documentation = pn.pane.Markdown("""
A cut-off of 10% means that only those processes responsible or 90% of impact will be computed. A lower cut-off therefore results in a longer calculation, which yields a larger amount of processes.
""")
        
# https://panel.holoviz.org/reference/widgets/Button.html
widget_button_graph = pn.widgets.Button(
    name='Perform Scope Analysis',
    icon='chart-donut-3',
    button_type='primary',
    sizing_mode='stretch_width'
)
widget_button_graph.on_click(button_action_scope_analysis)

# https://panel.holoviz.org/reference/indicators/Number.html
widget_number_lca_score = pn.indicators.Number(
    name='LCA Score',
    font_size='30pt',
    title_size='20pt',
    value=0,
    format='{value:,.5f}',
    margin=0
)

widget_plotly_figure_piechart = pn.pane.Plotly(
    create_plotly_figure_piechart(
        {'Scope 1': 0}
    )
)

col1 = pn.Column(
    '## USEEIO Database Query',
    widget_button_load_db,
    widget_autocomplete_product,
    widget_select_method,
    widget_float_input_amount,
    widget_button_lca,
    widget_float_slider_cutoff,
    markdown_cutoff_documentation,
    widget_button_graph,
    pn.Spacer(height=10),
    widget_number_lca_score,
    widget_plotly_figure_piechart,
)

# COLUMN 2 ####################################################################

# https://panel.holoviz.org/reference/widgets/Tabulator.html#formatters
from bokeh.models.widgets.tables import BooleanFormatter
widget_tabulator = pn.widgets.Tabulator(
    None,
    theme='site',
    show_index=False,
    selectable=False,
    formatters={'Scope 1?': BooleanFormatter()}, # tick/cross for boolean values
    editors={}, # is set later such that only a single column can be edited
)

col2 = pn.Column(
    '## Table of Upstream Processes',
    widget_tabulator
)

# SITE ######################################################################

header = pn.Row(
    pn.HSpacer(),
    pn.pane.SVG(
        'https://raw.githubusercontent.com/brightway-lca/brightway-webapp/main/app/_media/PSI%2BETHZ%2BWISER_white.svg',
        height=50,
        margin=0,
        align="center"
    ),
    sizing_mode="stretch_width",
)

# https://panel.holoviz.org/tutorials/basic/templates.html
template = pn.template.MaterialTemplate(
    header=header,
    title='Brightway WebApp (Carbon Accounting)',
    header_background='#2d853a', # green
    logo='https://raw.githubusercontent.com/brightway-lca/brightway-webapp/main/app/_media/BW_white.svg',
)

# https://panel.holoviz.org/reference/layouts/GridSpec.html
gspec = pn.GridSpec(ncols=3, sizing_mode='stretch_both')
gspec[:,0:1] = col1 # 1/3rd of the width
gspec[:,1:3] = col2 # 2/3rds of the width

template.main.append(gspec)
template.servable()