# main.py

import panel as pn
from table_col import table_col
from management_col import management_col
from constants import DATABASE_NAME

pn.extension(notifications=True)
pn.extension(design='material')
pn.extension('plotly')
pn.extension('tabulator')
pn.extension('terminal')

code_open_window = """
window.open("https://github.com/brightway-lca/brightway-webapp/blob/main/README.md")
"""
button_about = pn.widgets.Button(name="Learn more about this prototype...", button_type="success")
button_about.js_on_click(code=code_open_window)

header = pn.Row(
    button_about,
    pn.Spacer(),
    pn.pane.SVG(
        'https://raw.githubusercontent.com/brightway-lca/brightway-webapp/main/app/_media/logo_PSI-ETHZ-WISER_white.svg',
        margin=0,
        align="center",
        height=50
    ),
    sizing_mode="stretch_width",
)

template = pn.template.MaterialTemplate(
    header=header,
    title='Brightway WebApp (Carbon Accounting)',
    header_background='#2d853a',  # green
    logo='https://raw.githubusercontent.com/brightway-lca/brightway-webapp/main/app/_media/logo_brightway_white.svg',
    favicon='https://raw.githubusercontent.com/brightway-lca/brightway-webapp/main/app/_media/favicon.png',
)

gspec = pn.GridSpec(ncols=3, sizing_mode='stretch_both')
gspec[:, 0:1] = management_col
gspec[:, 1:3] = table_col

template.main.append(gspec)
template.servable()
