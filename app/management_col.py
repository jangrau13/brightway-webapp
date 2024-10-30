# col1.py

import panel as pn
import numpy as np
import pandas as pd
from constants import DATABASE_NAME
from utils import create_plotly_figure_piechart, determine_scope_emissions
from shared_ui import panel_lca_instance, widget_tabulator, widget_plotly_figure_piechart

# Widgets specific to col1
widget_button_load_db = pn.widgets.Button(
    name='Load ' + DATABASE_NAME + ' Database',
    icon='database-plus',
    button_type='primary',
    sizing_mode='stretch_width'
)

widget_autocomplete_product = pn.widgets.AutocompleteInput(
    name='Reference Product/Product/Service',
    options=[],
    case_sensitive=False,
    search_strategy='includes',
    placeholder='Start typing your product name here...',
    sizing_mode='stretch_width'
)

widget_select_method = pn.widgets.Select(
    name='Impact Assessment Method',
    options=[],
    sizing_mode='stretch_width',
)

widget_float_input_amount = pn.widgets.FloatInput(
    name='(Monetary) Amount of Reference Product [USD]',
    value=100,
    step=1,
    start=0,
    sizing_mode='stretch_width'
)

widget_button_lca = pn.widgets.Button(
    name='Compute LCA Score',
    icon='calculator',
    button_type='primary',
    sizing_mode='stretch_width'
)

widget_float_slider_cutoff = pn.widgets.EditableFloatSlider(
    name='Graph Traversal Cut-Off [%]',
    start=1,
    end=50,
    step=1,
    value=10,
    sizing_mode='stretch_width'
)

widget_button_graph = pn.widgets.Button(
    name='Update Data based on User Input',
    icon='chart-donut-3',
    button_type='primary',
    sizing_mode='stretch_width'
)

widget_number_lca_score = pn.indicators.Number(
    name='LCA Impact Score',
    font_size='30pt',
    title_size='20pt',
    value=0,
    format='{value:,.3f}',
    margin=0
)

# Event handlers for col1
def button_action_load_database(event):
    panel_lca_instance.set_db()
    panel_lca_instance.set_list_db_products()
    panel_lca_instance.set_methods_objects()
    widget_autocomplete_product.options = panel_lca_instance.list_db_products
    if panel_lca_instance.list_db_methods:
        widget_select_method.options = panel_lca_instance.list_db_methods
        # Select a default method containing 'IPCC'
        default_method = next((item for item in panel_lca_instance.list_db_methods if 'IPCC' in item[0]), None)
        if default_method:
            widget_select_method.value = default_method

def button_action_perform_lca(event):
    if widget_autocomplete_product.value == '':
        pn.state.notifications.error('Please select a reference product first!', duration=5000)
        return
    else:
        panel_lca_instance.df_graph_traversal_nodes = pd.DataFrame()
        widget_plotly_figure_piechart.object = create_plotly_figure_piechart({'null': 0})
        pn.state.notifications.info('Calculating LCA score...', duration=5000)

    # add chosen actvity to db
    src = panel_lca_instance.get_src_and_get_technosphere_and_biosphere(widget_autocomplete_product.value)
    panel_lca_instance.set_chosen_activity(src)
    panel_lca_instance.set_chosen_method_and_unit(widget_select_method.value)
    panel_lca_instance.set_chosen_amount(widget_float_input_amount.value)
    panel_lca_instance.perform_lca()
    pn.state.notifications.success('Completed LCA score calculation!', duration=5000)
    widget_number_lca_score.format = f'{{value:,.3f}} {panel_lca_instance.chosen_method_unit}'
    perform_graph_traversal()
    perform_scope_analysis()

def perform_graph_traversal():
    pn.state.notifications.info('Performing Graph Traversal...', duration=5000)
    panel_lca_instance.bool_user_provided_data = False
    panel_lca_instance.set_graph_traversal_cutoff(widget_float_slider_cutoff.value / 100)
    panel_lca_instance.perform_graph_traversal()
    panel_lca_instance.df_tabulator = panel_lca_instance.df_tabulator_from_traversal.copy()
    widget_tabulator.value = panel_lca_instance.df_tabulator
    # Set up column editors if needed
    column_editors = {
        colname: None
        for colname in panel_lca_instance.df_tabulator.columns
        if colname not in ['Scope', 'SupplyAmount', 'BurdenIntensity']
    }
    column_editors['Scope'] = {'type': 'list', 'values': [1, 2, 3]}
    widget_tabulator.editors = column_editors
    pn.state.notifications.success('Graph Traversal Complete!', duration=5000)

def perform_scope_analysis():
    pn.state.notifications.info('Performing Scope Analysis...', duration=5000)
    panel_lca_instance.scope_dict = determine_scope_emissions(df=widget_tabulator.value)
    widget_plotly_figure_piechart.object = create_plotly_figure_piechart(panel_lca_instance.scope_dict)
    widget_number_lca_score.value = panel_lca_instance.df_tabulator['Burden(Direct)'].sum()
    pn.state.notifications.success('Scope Analysis Complete!', duration=5000)

# Bind event handlers
widget_button_load_db.on_click(button_action_load_database)
widget_button_lca.on_click(button_action_perform_lca)

# Define col1 layout
management_col = pn.Column(
    '# LCA Settings',
    widget_button_load_db,
    widget_autocomplete_product,
    pn.pane.Markdown("Method documentation here."),
    widget_select_method,
    widget_float_input_amount,
    pn.pane.Markdown("Cutoff documentation here."),
    widget_float_slider_cutoff,
    widget_button_lca,
    widget_button_graph,
    pn.Spacer(height=10),
    widget_number_lca_score,
    widget_plotly_figure_piechart,
)
