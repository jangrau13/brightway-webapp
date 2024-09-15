importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.js");

function sendPatch(patch, buffers, msg_id) {
  self.postMessage({
    type: 'patch',
    patch: patch,
    buffers: buffers
  })
}

async function startApplication() {
  console.log("Loading pyodide!");
  self.postMessage({type: 'status', msg: 'Loading pyodide'})
  self.pyodide = await loadPyodide();
  self.pyodide.globals.set("sendPatch", sendPatch);
  console.log("Loaded!");
  await self.pyodide.loadPackage("micropip");
  const env_spec = ['https://cdn.holoviz.org/panel/wheels/bokeh-3.5.2-py3-none-any.whl', 'https://cdn.holoviz.org/panel/1.5.0-rc.2/dist/wheels/panel-1.5.0rc2-py3-none-any.whl', 'pyodide-http==0.2.1', 'bw2data==4.0.dev52', 'bw2io==0.9.dev37', 'bw2calc==2.0.dev20', 'bw-graph-tools==0.4.1', 'plotly==5.24.0', 'lzma']
  for (const pkg of env_spec) {
    let pkg_name;
    if (pkg.endsWith('.whl')) {
      pkg_name = pkg.split('/').slice(-1)[0].split('-')[0]
    } else {
      pkg_name = pkg
    }
    self.postMessage({type: 'status', msg: `Installing ${pkg_name}`})
    try {
      await self.pyodide.runPythonAsync(`
        import micropip
        await micropip.install('${pkg}');
      `);
    } catch(e) {
      console.log(e)
      self.postMessage({
	type: 'status',
	msg: `Error while installing ${pkg_name}`
      });
    }
  }
  console.log("Packages loaded!");
  self.postMessage({type: 'status', msg: 'Executing code'})
  const code = `
  \nimport asyncio\n\nfrom panel.io.pyodide import init_doc, write_doc\n\ninit_doc()\n\n# %%\nimport panel as pn\npn.extension(notifications=True)\npn.extension(design='material')\npn.extension('plotly')\npn.extension('tabulator')\n\n# plotting\nimport plotly\n\n# data science\nimport pandas as pd\n\n# system\nimport os\n\n# brightway\nimport bw_graph_tools as bgt\nimport bw2io as bi\nimport bw2data as bd\nimport bw2calc as bc\n\n# type hints\nfrom bw2data.backends.proxies import Activity\nfrom bw_graph_tools.graph_traversal import Node\nfrom bw_graph_tools.graph_traversal import Edge\n\n\ndef brightway_wasm_database_storage_workaround() -> None:\n    """\n    Sets the Brightway project directory to \`/tmp/.\n    \n    The JupyterLite file system currently does not support storage of SQL database files\n    in directories other than \`/tmp/\`. This function sets the Brightway environment variable\n    \`BRIGHTWAY_DIR\` to \`/tmp/\` to work around this limitation.\n    \n    Notes\n    -----\n    - https://docs.brightway.dev/en/latest/content/faq/data_management.html#how-do-i-change-my-data-directory\n    - https://github.com/brightway-lca/brightway-live/issues/10\n    """\n    os.environ["BRIGHTWAY_DIR"] = "/tmp/"\n\n\ndef check_for_useeio_brightway_project(event):\n    """\n    Checks if the USEEIO-1.1 Brightway project is installed.\n    If not, installs it. Shows Panel notifications for the user.\n\n    Returns\n    -------\n    SQLiteBackend\n        bw2data.backends.base.SQLiteBackend of the USEEIO-1.1 database\n    """\n    if 'USEEIO-1.1' not in bd.projects:\n        notification_load = pn.state.notifications.info('Loading USEEIO database...')\n        bi.install_project(project_key="USEEIO-1.1", overwrite_existing=True)\n        notification_load.destroy()\n        pn.state.notifications.success('USEEIO database loaded!', duration=7000)\n    else:\n        pn.state.notifications.success('USEEIO database already loaded!', duration=7000)\n        pass\n    bd.projects.set_current(name='USEEIO-1.1')\n\n\ndef nodes_dict_to_dataframe(nodes: dict) -> pd.DataFrame:\n    """\n    Returns a dataframe with human-readable descriptions and emissions values of the nodes in the graph traversal.\n\n    Parameters\n    ----------\n    nodes : dict\n        A dictionary of nodes in the graph traversal.\n        Can be created by selecting the 'nodes' key from the dictionary\n        returned by the function \`bw_graph_tools.NewNodeEachVisitGraphTraversal.calculate()\`.\n\n    Returns\n    -------\n    pd.DataFrame\n        A dataframe with human-readable descriptions and emissions values of the nodes in the graph traversal.\n    """\n    list_of_row_dicts = []\n    for i in range(0, len(nodes)-1):\n        current_node: Node = nodes[i]\n        scope_1: bool = False\n        if current_node.unique_id == 0:\n            scope_1 = True\n        else:\n            pass\n        list_of_row_dicts.append(\n            {\n                'UID': current_node.unique_id,\n                'Scope 1?': scope_1,\n                'Name': bd.get_node(id=current_node.activity_datapackage_id)['name'],\n                'Cumulative': current_node.cumulative_score,\n                'Direct': current_node.direct_emissions_score,\n                'Depth': current_node.depth,\n                'activity_datapackage_id': current_node.activity_datapackage_id,\n            }\n        )\n    return pd.DataFrame(list_of_row_dicts)\n\n\ndef edges_dict_to_dataframe(edges: dict) -> pd.DataFrame:\n    """\n    To be added...\n    """\n    if len(edges) < 2:\n        return pd.DataFrame()\n    else:\n        list_of_row_dicts = []\n        for i in range(0, len(edges)-1):\n            current_edge: Edge = edges[i]\n            list_of_row_dicts.append(\n                {\n                    'consumer_unique_id': current_edge.consumer_unique_id,\n                    'producer_unique_id': current_edge.producer_unique_id\n                }\n            )\n        return pd.DataFrame(list_of_row_dicts).drop(0)\n\n\ndef trace_branch(df: pd.DataFrame, start_node: int) -> list:\n    """\n    Given a dataframe of graph edges and a starting node, returns the branch of nodes that lead to the starting node.\n\n    For example:\n\n    | consumer_unique_id | producer_unique_id |\n    |--------------------|--------------------|\n    | 0                  | 1                  | # 1 is terminal producer node\n    | 0                  | 2                  |\n    | 0                  | 3                  |\n    | 2                  | 4                  | # 4 is terminal producer node\n    | 3                  | 5                  |\n    | 5                  | 6                  | # 6 is terminal producer node\n\n    For start_node = 6, the function returns [0, 3, 5, 6]\n\n    Parameters\n    ----------\n    df : pd.DataFrame\n        Dataframe of graph edges. Must contain integer-type columns 'consumer_unique_id' and 'producer_unique_id'.\n    start_node : int\n        The integer indicating the starting node to trace back from.\n\n    Returns\n    -------\n    list\n        A list of integers indicating the branch of nodes that lead to the starting node.\n    """\n\n    branch: list = [start_node]\n\n    while True:\n        previous_node: int = df[df['producer_unique_id'] == start_node]['consumer_unique_id']\n        if previous_node.empty:\n            break\n        start_node: int = previous_node.values[0]\n        branch.insert(0, start_node)\n\n    return branch\n\n\ndef add_branch_information_to_dataframe(df: pd.DataFrame) -> pd.DataFrame:\n    """\n    Adds 'branch' information to terminal nodes in a dataframe of graph edges.\n\n    For example:\n\n    | consumer_unique_id | producer_unique_id |\n    |--------------------|--------------------|\n    | 0                  | 1                  | # 1 is terminal producer node\n    | 0                  | 2                  |\n    | 0                  | 3                  |\n    | 2                  | 4                  | # 4 is terminal producer node\n    | 3                  | 5                  |\n    | 5                  | 6                  | # 6 is terminal producer node\n\n    | consumer_unique_id | producer_unique_id | branch       |\n    |--------------------|--------------------|--------------|\n    | 0                  | 1                  | [0, 1]       |\n    | 0                  | 2                  | [0, 2]       |\n    | 0                  | 3                  | [0, 3]       |\n    | 2                  | 4                  | [0, 2, 4]    |\n    | 3                  | 5                  | [0, 3, 5]    |\n    | 5                  | 6                  | [0, 3, 5, 6] |\n\n    Parameters\n    ----------\n    df_edges : pd.DataFrame\n        A dataframe of graph edges.\n        Must contain integer-type columns 'consumer_unique_id' and 'producer_unique_id'.\n\n    Returns\n    -------\n    pd.DataFrame\n        A dataframe of graph nodes with a column 'branch' that contains the branch of nodes that lead to the terminal producer node.\n    """\n    # initialize empty list to store branches\n    branches: list = []\n\n    for _, row in df.iterrows():\n        branch: list = trace_branch(df, int(row['producer_unique_id']))\n        branches.append({\n            'producer_unique_id': int(row['producer_unique_id']),\n            'Branch': branch\n        })\n\n    return pd.DataFrame(branches)\n\n\ndef create_plotly_figure_piechart(data_dict: dict) -> plotly.graph_objects.Figure:\n    plotly_figure = plotly.graph_objects.Figure(\n        data=[\n            plotly.graph_objects.Pie(\n                labels=[label for label in data_dict.keys()],\n                values=[value for value in data_dict.values()]\n            )\n        ]\n    )\n    plotly_figure.update_traces(\n        marker=dict(\n            line=dict(color='#000000', width=2)\n        )\n    )\n    plotly_figure.update_layout(\n        autosize=True,\n        height=300,\n        legend=dict(\n            orientation="v",\n            yanchor="auto",\n            y=1,\n            xanchor="right",\n            x=-0.3\n        ),\n        margin=dict(\n            l=50,\n            r=50,\n            b=0,\n            t=0,\n            pad=0\n        ),\n    )\n    return plotly_figure\n\n\nclass panel_lca_class:\n    """\n    This class is used to store all the necessary information for the LCA calculation.\n    It provides methods to populate the database and perform Brightway LCA calculations.\n    All methods can be bound to a button click event.\n\n    Notes\n    -----\n    https://discourse.holoviz.org/t/update-global-variable-through-function-bound-with-on-click/\n    """\n    brightway_wasm_database_storage_workaround()\n    def __init__(self):\n        self.db_name = 'USEEIO-1.1'\n        self.db = None\n        self.list_db_products = []\n        self.dict_db_methods = {}\n        self.list_db_methods = []\n        self.chosen_activity = ''\n        self.chosen_method = ''\n        self.chosen_method_unit = ''\n        self.chosen_amount = 0\n        self.lca = None\n        self.scope_dict = {'Scope 1':0, 'Scope 2':0, 'Scope 3':0}\n        self.graph_traversal_cutoff = 1\n        self.graph_traversal = {}\n        self.df_graph_traversal_nodes = None\n        self.df_graph_traversal_edges = None\n\n\n    def set_db(self, event):\n        """\n        Checks if the USEEIO-1.1 Brightway project is installed.\n        If not, installs it and sets is as current project.\n        Else just sets the current project to USEEIO-1.1.\n        """\n        check_for_useeio_brightway_project(event)\n        self.db = bd.Database(self.db_name)\n\n\n    def set_list_db_products(self, event):\n        """\n        Sets \`list_db_products\` to a list of product names from the database for use in the autocomplete widget.\n        """\n        self.list_db_products = [node['name'] for node in self.db if 'product' in node['type']]\n    \n\n    def set_methods_objects(self, event):\n        """\n        dict_methods = {\n            'HRSP': ('Impact Potential', 'HRSP'),\n            'OZON': ('Impact Potential', 'OZON'),\n            ...\n        }\n        """\n        dict_methods = {i[-1]:[i] for i in bd.methods}\n\n        """\n        dict_method_names = {\n            'HRSP': 'Human Health: Respiratory effects',\n            'OZON': 'Ozone Depletion',\n            ...\n        }\n        """\n        # hardcoded for better Pyodide performance\n        dict_methods_names = {\n            "HRSP": "Human Health - Respiratory Effects",\n            "OZON": "Ozone Depletion",\n            "HNC": "Human Health Noncancer",\n            "WATR": "Water",\n            "METL": "Metals",\n            "EUTR": "Eutrophication",\n            "HTOX": "Human Health Cancer and Noncancer",\n            "LAND": "Land",\n            "NREN": "Nonrenewable Energy",\n            "ETOX": "Freshwater Aquatic Ecotoxicity",\n            "PEST": "Pesticides",\n            "REN": "Renewable Energy",\n            "MINE": "Minerals and Metals",\n            "GCC": "Global Climate Change",\n            "ACID": "Acid Rain",\n            "HAPS": "Hazardous Air Pollutants",\n            "HC": "Human Health Cancer",\n            "SMOG": "Smog Formation",\n            "ENRG": "Energy"\n        }\n        # path_impact_categories_names: str = '../app/_data/USEEIO_impact_categories_names.csv'\n        # dict_methods_names = {}\n        # with open(path_impact_categories_names, mode='r', newline='', encoding='utf-8-sig') as file:\n        #    reader = csv.reader(file)\n        #    dict_methods_names = {rows[0]: rows[1] for rows in reader}\n\n        """\n        dict_methods_units = {\n            'HRSP': '[kg PM2.5 eq]',\n            'OZON': '[kg O3 eq]',\n            ...\n        }\n        """\n        # hardcoded for better Pyodide performance\n        dict_methods_units = {\n            "HRSP": "[kg PM2.5 eq]",\n            "OZON": "[kg O3 eq]",\n            "HNC": "[CTUh]",\n            "WATR": "[m3]",\n            "METL": "[kg]",\n            "EUTR": "[kg N eq]",\n            "HTOX": "[CTUh]",\n            "LAND": "[m2*yr]",\n            "NREN": "[MJ]",\n            "ETOX": "[CTUe]",\n            "PEST": "[kg]",\n            "REN": "[MJ]",\n            "MINE": "[kg]",\n            "GCC": "[kg CO2 eq]",\n            "ACID": "[kg SO2 eq]",\n            "HAPS": "[kg]",\n            "HC": "[CTUh]",\n            "SMOG": "[kg O3 eq]",\n            "ENRG": "[MJ]"\n        }\n        # path_impact_categories_units: str = '../app/_data/USEEIO_impact_categories_units.csv'\n        # dict_methods_units = {}\n        # with open(path_impact_categories_units, mode='r', newline='', encoding='utf-8-sig') as file:\n        #    reader = csv.reader(file)\n        #    dict_methods_units = {rows[0]: str('[')+rows[1]+str(']') for rows in reader}\n\n        """\n        dict_methods_enriched = {\n            'HRSP': [('Impact Potential', 'HRSP'), 'Human Health - Respiratory effects', '[kg PM2.5 eq]'],\n            'OZON': [('Impact Potential', 'OZON'), 'Ozone Depletion', '[kg O3 eq]'],\n            ...\n        }\n        """\n        dict_methods_enriched = {\n            key: [dict_methods[key][0], dict_methods_names[key], dict_methods_units[key]]\n            for key in dict_methods\n        }\n\n        """\n        list_methods_for_autocomplete = [\n            ('HRSP', 'Human Health: Respiratory effects', '[kg PM2.5 eq]'),\n            ('OZON', 'Ozone Depletion', '[kg O3 eq]'),\n            ...\n        ]\n        """\n        list_methods_for_autocomplete = [(key, value[1], value[2]) for key, value in dict_methods_enriched.items()]\n\n        self.dict_db_methods = dict_methods_enriched\n        self.list_db_methods = list_methods_for_autocomplete\n\n\n    def set_chosen_activity(self, event):\n        """\n        Sets \`chosen_activity\` to the \`bw2data.backends.proxies.Activity\` object of the chosen product from the autocomplete widget.\n        """\n        self.chosen_activity: Activity = bd.utils.get_node(\n            database = self.db_name,\n            name = widget_autocomplete_product.value,\n            type = 'product',\n            location = 'United States'\n        )\n\n\n    def set_chosen_method_and_unit(self, event):\n        """\n        Sets \`chosen_method\` to the (tuple) corresponding to the chosen method string from the select widget.\n\n        Example:\n        --------\n        widget_select_method.value = ('HRSP', 'Human Health: Respiratory effects', '[kg PM2.5 eq]')\n        widget_select_method.value[0] = 'HRSP'\n        dict_db_methods = {'HRSP': [('Impact Potential', 'HRSP'), 'Human Health - Respiratory effects', '[kg PM2.5 eq]']}\n        dict_db_methods['HRSP'][0] = ('Impact Potential', 'HRSP') # which is the tuple that bd.Method needs\n        """\n        self.chosen_method = bd.Method(self.dict_db_methods[widget_select_method.value[0]][0])\n        self.chosen_method_unit = widget_select_method.value[2]\n\n\n    def set_chosen_amount(self, event):\n        """\n        Sets \`chosen_amount\` to the float value from the float input widget.\n        """\n        self.chosen_amount = widget_float_input_amount.value\n\n\n    def perform_lca(self, event):\n        """\n        Performs the LCA calculation using the chosen product, method, and amount.\n        Sets the \`lca\` attribute to an instance of the \`bw2calc.LCA\` object.\n        """\n        self.lca = bc.LCA( \n            demand={self.chosen_activity: self.chosen_amount}, \n            method = self.chosen_method.name\n        )\n        self.lca.lci()\n        self.lca.lcia()\n\n\n    def set_graph_traversal_cutoff(self, event):\n        """\n        Sets the \`graph_traversal_cutoff\` attribute to the float value from the float slider widget.\n        Note that the value is divided by 100 to convert from percentage to decimal.\n        """\n        self.graph_traversal_cutoff = widget_float_slider_cutoff.value / 100\n\n\n    def perform_graph_traversal(self, event):\n        widget_cutoff_indicator_statictext.value = self.graph_traversal_cutoff * 100\n        self.graph_traversal: dict = bgt.NewNodeEachVisitGraphTraversal.calculate(self.lca, cutoff=self.graph_traversal_cutoff)\n        self.df_graph_traversal_nodes: pd.DataFrame = nodes_dict_to_dataframe(self.graph_traversal['nodes'])\n        self.df_graph_traversal_edges: pd.DataFrame = edges_dict_to_dataframe(self.graph_traversal['edges'])\n        if self.df_graph_traversal_edges.empty:\n            return\n        else:\n            self.df_graph_traversal_edges = add_branch_information_to_dataframe(self.df_graph_traversal_edges)\n            self.df_graph_traversal_nodes = pd.merge(\n                self.df_graph_traversal_nodes,\n                self.df_graph_traversal_edges,\n                left_on='UID',\n                right_on='producer_unique_id',\n                how='left')\n\n\n    def determine_scope_1_and_2_emissions(self, event,  uid_electricity: int = 53,):\n        """\n        Determines the scope 1 and 2 emissions from the graph traversal nodes dataframe.\n        """\n        dict_scope = {\n            'Scope 1': 0,\n            'Scope 2': 0,\n            'Scope 3': 0\n        }\n        df = self.df_graph_traversal_nodes\n        dict_scope['Scope 1'] = df.loc[(df['Scope 1?'] == True)]['Direct'].values.sum()\n\n        try:\n            dict_scope['Scope 2'] = df.loc[\n                (df['Depth'] == 2)\n                &\n                (df['activity_datapackage_id'] == uid_electricity)\n            ]['Direct'].values[0]\n        except:\n            pass\n\n        self.scope_dict = dict_scope\n\n\n    def determine_scope_3_emissions(self, event):\n        self.scope_dict['Scope 3'] = self.lca.score - self.scope_dict['Scope 1'] - self.scope_dict['Scope 2']\n\n\nbrightway_wasm_database_storage_workaround()\npanel_lca_class_instance = panel_lca_class()\n\n# COLUMN 1 ####################################################################\n\ndef button_action_load_database(event):\n    panel_lca_class_instance.set_db(event)\n    panel_lca_class_instance.set_list_db_products(event)\n    panel_lca_class_instance.set_methods_objects(event)\n    widget_autocomplete_product.options = panel_lca_class_instance.list_db_products\n    widget_select_method.options = panel_lca_class_instance.list_db_methods\n    widget_select_method.value = [item for item in panel_lca_class_instance.list_db_methods if 'GCC' in item[0]][0] # global warming as default value\n\n\ndef button_action_perform_lca(event):\n    if widget_autocomplete_product.value == '':\n        pn.state.notifications.error('Please select a reference product first!', duration=5000)\n        return\n    else:\n        panel_lca_class_instance.df_graph_traversal_nodes = pd.DataFrame()\n        widget_tabulator.value = panel_lca_class_instance.df_graph_traversal_nodes\n        widget_plotly_figure_piechart.object = create_plotly_figure_piechart({'null':0})\n        pn.state.notifications.info('Calculating LCA score...', duration=5000)\n        pass\n    panel_lca_class_instance.set_chosen_activity(event)\n    panel_lca_class_instance.set_chosen_method_and_unit(event)\n    panel_lca_class_instance.set_chosen_amount(event)\n    panel_lca_class_instance.perform_lca(event)\n    pn.state.notifications.success('Completed LCA score calculation!', duration=5000)\n    widget_number_lca_score.value = panel_lca_class_instance.lca.score\n    widget_number_lca_score.format = f'{{value:,.3f}} {panel_lca_class_instance.chosen_method_unit}'\n\n\ndef perform_graph_traversal(event):\n    panel_lca_class_instance.set_graph_traversal_cutoff(event)\n    panel_lca_class_instance.perform_graph_traversal(event)\n    widget_tabulator.value = panel_lca_class_instance.df_graph_traversal_nodes\n    column_editors = {\n        colname : {'type': 'editable', 'value': True}\n        for colname in panel_lca_class_instance.df_graph_traversal_nodes.columns\n        if colname != 'Scope 1?'\n    }\n    widget_tabulator.editors = column_editors\n\n\ndef perform_scope_analysis(event):\n    panel_lca_class_instance.determine_scope_1_and_2_emissions(event)\n    panel_lca_class_instance.determine_scope_3_emissions(event)\n    widget_plotly_figure_piechart.object = create_plotly_figure_piechart(panel_lca_class_instance.scope_dict)\n\n\ndef button_action_scope_analysis(event):\n    if panel_lca_class_instance.lca is None:\n        pn.state.notifications.error('Please perform an LCA Calculation first!', duration=5000)\n        return\n    else:\n        if panel_lca_class_instance.df_graph_traversal_nodes.empty:\n            pn.state.notifications.info('Performing Graph Traversal...', duration=5000)\n            pn.state.notifications.info('Performing Scope Analysis...', duration=5000)\n            perform_graph_traversal(event)\n            perform_scope_analysis(event)\n            pn.state.notifications.success('Graph Traversal Complete!', duration=5000)\n            pn.state.notifications.success('Scope Analysis Complete!', duration=5000)\n        else:\n            if widget_float_slider_cutoff.value / 100 != panel_lca_class_instance.graph_traversal_cutoff:\n                pn.state.notifications.info('Re-Performing Graph Traversal...', duration=5000)\n                perform_graph_traversal(event)\n            else:\n                panel_lca_class_instance.df_graph_traversal_nodes = widget_tabulator.value\n                pn.state.notifications.info('Re-Performing Scope Analysis...', duration=5000)\n                perform_scope_analysis(event)\n                pn.state.notifications.success('Scope Analysis Complete!', duration=5000)\n                \n\n# https://panel.holoviz.org/reference/widgets/Button.html\nwidget_button_load_db = pn.widgets.Button( \n    name='Load USEEIO Database',\n    icon='database-plus',\n    button_type='primary',\n    sizing_mode='stretch_width'\n)\nwidget_button_load_db.on_click(button_action_load_database)\n\n# https://panel.holoviz.org/reference/widgets/AutocompleteInput.html\nwidget_autocomplete_product = pn.widgets.AutocompleteInput( \n    name='Reference Product',\n    options=[],\n    case_sensitive=False,\n    search_strategy='includes',\n    placeholder='Start typing your product name here...',\n    sizing_mode='stretch_width'\n)\n\n# https://panel.holoviz.org/reference/widgets/Select.html\nwidget_select_method = pn.widgets.Select( \n    name='Impact Assessment Method',\n    options=[],\n    sizing_mode='stretch_width',\n\n)\n\n# https://panel.holoviz.org/reference/widgets/FloatInput.html\nwidget_float_input_amount = pn.widgets.FloatInput( \n    name='(Monetary) Amount of Reference Product [USD]',\n    value=1,\n    step=1,\n    start=0,\n    sizing_mode='stretch_width'\n)\n\n# https://panel.holoviz.org/reference/widgets/Button.html\nwidget_button_lca = pn.widgets.Button( \n    name='Compute LCA Score',\n    icon='calculator',\n    button_type='primary',\n    sizing_mode='stretch_width'\n)\nwidget_button_lca.on_click(button_action_perform_lca)\n\n # https://panel.holoviz.org/reference/widgets/EditableFloatSlider.html\nwidget_float_slider_cutoff = pn.widgets.EditableFloatSlider(\n    name='Graph Traversal Cut-Off [%]',\n    start=1,\n    end=50,\n    step=1,\n    value=10,\n    sizing_mode='stretch_width'\n)\n\n# https://panel.holoviz.org/reference/panes/Markdown.html\nmarkdown_cutoff_documentation = pn.pane.Markdown("""\nA cut-off of 10% means that only those processes responsible or 90% of impact will be computed. A lower cut-off therefore results in a longer calculation, which yields a larger amount of processes.\n""")\n        \n# https://panel.holoviz.org/reference/widgets/Button.html\nwidget_button_graph = pn.widgets.Button(\n    name='Perform Scope Analysis',\n    icon='chart-donut-3',\n    button_type='primary',\n    sizing_mode='stretch_width'\n)\nwidget_button_graph.on_click(button_action_scope_analysis)\n\n# https://panel.holoviz.org/reference/indicators/Number.html\nwidget_number_lca_score = pn.indicators.Number(\n    name='LCA Impact Score',\n    font_size='30pt',\n    title_size='20pt',\n    value=0,\n    format='{value:,.3f}',\n    margin=0\n)\n\nwidget_plotly_figure_piechart = pn.pane.Plotly(\n    create_plotly_figure_piechart(\n        {'Scope 1': 0}\n    )\n)\n\ncol1 = pn.Column(\n    '## USEEIO Database Query',\n    widget_button_load_db,\n    widget_autocomplete_product,\n    widget_select_method,\n    widget_float_input_amount,\n    widget_button_lca,\n    widget_float_slider_cutoff,\n    markdown_cutoff_documentation,\n    widget_button_graph,\n    pn.Spacer(height=10),\n    widget_number_lca_score,\n    widget_plotly_figure_piechart,\n)\n\n# COLUMN 2 ####################################################################\n\n# https://panel.holoviz.org/reference/widgets/Tabulator.html#formatters\nfrom bokeh.models.widgets.tables import BooleanFormatter\nwidget_tabulator = pn.widgets.Tabulator(\n    None,\n    theme='site',\n    show_index=False,\n    selectable=False,\n    formatters={'Scope 1?': BooleanFormatter()}, # tick/cross for boolean values\n    editors={}, # is set later such that only a single column can be edited\n    hidden_columns=['activity_datapackage_id', 'producer_unique_id'],\n)\n\n# https://panel.holoviz.org/reference/widgets/StaticText.html\nwidget_cutoff_indicator_statictext = pn.widgets.StaticText(\n    name='Includes processes responsible for amount of emissions [%]',\n    value=None\n)\n\ncol2 = pn.Column(\n    '## Table of Upstream Processes',\n    widget_cutoff_indicator_statictext,\n    widget_tabulator\n)\n\n# SITE ######################################################################\n\n# https://discourse.holoviz.org/t/is-there-a-way-to-click-button-and-open-a-new-link-in-a-new-tab\ncode_open_window = """\nwindow.open("https://github.com/brightway-lca/brightway-webapp/blob/main/README.md")\n"""\nbutton_about = pn.widgets.Button(name="Learn more about this prototype...", button_type="success")\nbutton_about.js_on_click(code=code_open_window)\n\nheader = pn.Row(\n    button_about,\n    pn.HSpacer(),\n    pn.pane.SVG(\n        'https://raw.githubusercontent.com/brightway-lca/brightway-webapp/main/app/_media/logo_PSI-ETHZ-WISER_white.svg',\n        #height=50,\n        margin=0,\n        align="center"\n    ),\n    sizing_mode="stretch_width",\n)\n\n# https://panel.holoviz.org/tutorials/basic/templates.html\ntemplate = pn.template.MaterialTemplate(\n    header=header,\n    title='Brightway WebApp (Carbon Accounting)',\n    header_background='#2d853a', # green\n    logo='https://raw.githubusercontent.com/brightway-lca/brightway-webapp/main/app/_media/logo_brightway_white.svg',\n)\n\n# https://panel.holoviz.org/reference/layouts/GridSpec.html\ngspec = pn.GridSpec(ncols=3, sizing_mode='stretch_both')\ngspec[:,0:1] = col1 # 1/3rd of the width\ngspec[:,1:3] = col2 # 2/3rds of the width\n\ntemplate.main.append(gspec)\ntemplate.servable()\n\nawait write_doc()
  `

  try {
    const [docs_json, render_items, root_ids] = await self.pyodide.runPythonAsync(code)
    self.postMessage({
      type: 'render',
      docs_json: docs_json,
      render_items: render_items,
      root_ids: root_ids
    })
  } catch(e) {
    const traceback = `${e}`
    const tblines = traceback.split('\n')
    self.postMessage({
      type: 'status',
      msg: tblines[tblines.length-2]
    });
    throw e
  }
}

self.onmessage = async (event) => {
  const msg = event.data
  if (msg.type === 'rendered') {
    self.pyodide.runPythonAsync(`
    from panel.io.state import state
    from panel.io.pyodide import _link_docs_worker

    _link_docs_worker(state.curdoc, sendPatch, setter='js')
    `)
  } else if (msg.type === 'patch') {
    self.pyodide.globals.set('patch', msg.patch)
    self.pyodide.runPythonAsync(`
    from panel.io.pyodide import _convert_json_patch
    state.curdoc.apply_json_patch(_convert_json_patch(patch), setter='js')
    `)
    self.postMessage({type: 'idle'})
  } else if (msg.type === 'location') {
    self.pyodide.globals.set('location', msg.location)
    self.pyodide.runPythonAsync(`
    import json
    from panel.io.state import state
    from panel.util import edit_readonly
    if state.location:
        loc_data = json.loads(location)
        with edit_readonly(state.location):
            state.location.param.update({
                k: v for k, v in loc_data.items() if k in state.location.param
            })
    `)
  }
}

startApplication()