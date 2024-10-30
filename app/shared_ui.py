# shared.py

import panel as pn
import pandas as pd
from lca_model import PanelLCA
from utils import create_plotly_figure_piechart

# Shared LCA model instance
panel_lca_instance = PanelLCA()

# Shared Tabulator widget
widget_tabulator = pn.widgets.Tabulator(
    pd.DataFrame([['']], columns=['Data will appear here after calculations...']),
    theme='site',
    show_index=False,
    hidden_columns=['activity_datapackage_id', 'producer_unique_id'],
    layout='fit_data_stretch',
    sizing_mode='stretch_width'
)

# Shared Plotly figure
widget_plotly_figure_piechart = pn.pane.Plotly(
    create_plotly_figure_piechart({'Scope 1': 0})
)
