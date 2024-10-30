# utils.py

import os
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import panel as pn

import re

def create_sanitized_key(url: str) -> str:
    """
    Creates a sanitized key from a URL or string by removing special characters but keeping alphanumeric characters
    and underscores. The protocol and slashes are replaced for a simplified identifier.

    Parameters
    ----------
    url : str
        The URL or string to be sanitized.

    Returns
    -------
    str
        A sanitized string suitable for use as a unique key.
    """
    # Replace protocol and slashes with underscores, then remove other special characters
    sanitized_url = re.sub(r'[:/]+', '_', url)  # Replaces "://" or "/" with "_"
    sanitized_url = re.sub(r'[^A-Za-z0-9_]', '', sanitized_url)  # Remove remaining special characters
    #print('sanitized', sanitized_url)
    return sanitized_url


def brightway_wasm_database_storage_workaround() -> None:
    """
    Sets the Brightway project directory to `/bw_tmp/`.
    """
    os.environ["BRIGHTWAY_DIR"] = "/bw_tmp/"

def sparql_query(query, endpoint_url):
    headers = {'Accept': 'application/sparql-results+json'}
    params = {'query': query}
    response = requests.get(endpoint_url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def create_plotly_figure_piechart(data_dict: dict) -> go.Figure:
    marker_colors = []
    for label in data_dict.keys():
        if label == 'Scope 1':
            marker_colors.append('#33cc33')
        elif label == 'Scope 2':
            marker_colors.append('#ffcc00')
        elif label == 'Scope 3':
            marker_colors.append('#3366ff')
        else:
            marker_colors.append('#000000')
    plotly_figure = go.Figure(
        data=[
            go.Pie(
                labels=list(data_dict.keys()),
                values=list(data_dict.values()),
                marker=dict(colors=marker_colors)
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

def determine_scope_emissions(df: pd.DataFrame):
    """
    Determines the scope 1/2/3 emissions from the graph traversal nodes dataframe.
    """
    dict_scope = {
        'Scope 1': df.loc[df['Scope'] == 1]['Burden(Direct)'].sum(),
        'Scope 2': df.loc[df['Scope'] == 2]['Burden(Direct)'].sum(),
        'Scope 3': df['Burden(Direct)'].sum() - df.loc[df['Scope'] == 1]['Burden(Direct)'].sum() - df.loc[df['Scope'] == 2]['Burden(Direct)'].sum()
    }
    return dict_scope
