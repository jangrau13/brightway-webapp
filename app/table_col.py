# col2.py

import panel as pn
import pandas as pd
from shared_ui import widget_tabulator

# Download components for the Tabulator
filename_download, button_download = widget_tabulator.download_menu(
    text_kwargs={'name': 'Filename', 'value': 'data.csv'},
    button_kwargs={'name': 'Download Table'}
)
filename_download.sizing_mode = 'stretch_width'
button_download.align = 'center'
button_download.icon = 'download'

# Event handler for Tabulator edits (if needed)
def on_tabulator_edit(event):
    # Handle Tabulator edits here
    # For example, you might want to update calculations based on user edits
    pass

# Bind the event handler to the Tabulator
widget_tabulator.on_edit(on_tabulator_edit)

# Define col2 layout
table_col = pn.Column(
    pn.Row('# Table of Upstream Processes', filename_download, button_download),
    widget_tabulator,
)
