from utils import sparql_query
from constants import SPARQL_ENDPOINT_URL

def get_activity_labels():
    query = """
    PREFIX ec1h: <http://www.EcoInvent.org/EcoSpold01#>
    PREFIX : <https://purl.org/wiser#>
    PREFIX wiser: <https://purl.org/wiser#>
    PREFIX process: <http://lca.jrc.it/ILCD/Process/>
    PREFIX pr: <http://lca.jrc.it/ILCD/Process#>
    PREFIX common: <http://lca.jrc.it/ILCD/Common/>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX flo: <http://lca.jrc.it/ILCD/Flow#>
    PREFIX ilcd: <http://lca.jrc.it/ILCD#>

    SELECT DISTINCT ?src ?srcLabel 
    WHERE {
        ?src a wiser:BActivity.
        ?src (wiser:pathToNameObject/wiser:name) ?srcLabel.
    }
    """
    data = sparql_query(query, SPARQL_ENDPOINT_URL)
    bindings = data['results']['bindings']
    results = [
        {'src': binding['src']['value'], 'srcLabel': binding['srcLabel']['value']}
        for binding in bindings
    ]
    return results

def get_technosphere(selected_src):
    print('selected src', selected_src)
    query = f"""
    PREFIX ec1h: <http://www.EcoInvent.org/EcoSpold01#>
    PREFIX : <https://purl.org/wiser#>
    PREFIX wiser: <https://purl.org/wiser#>
    PREFIX process: <http://lca.jrc.it/ILCD/Process/>
    PREFIX pr: <http://lca.jrc.it/ILCD/Process#>
    PREFIX common: <http://lca.jrc.it/ILCD/Common/>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX flo: <http://lca.jrc.it/ILCD/Flow#>
    PREFIX ilcd: <http://lca.jrc.it/ILCD#>
    SELECT DISTINCT ?src ?parentElement ?parent ?childElement ?child ?location ?value ?unit ?parentLocation ?parentUnit
    WHERE {{
        VALUES(?src){{( <{selected_src}> )}}
        ?src (wiser:hasChildActivitiy)* ?parentElement.
        ?parentElement (wiser:hasChildActivitiy) ?childElement.
        ?parentElement (wiser:pathToNameObject/wiser:name) ?parent.
        ?parentElement wiser:hasExchange ?exchange.
        ?exchange wiser:isReferenceExchangeOf ?childElement.
        OPTIONAL {{ ?exchange wiser:hasMeanValue ?value. }}
        OPTIONAL {{ ?childElement (wiser:pathToUnitObject/wiser:hasUnit) ?unit. }}
        OPTIONAL {{ ?childElement (wiser:pathToGeographyObject/wiser:hasGeography) ?location. }}
        ?childElement (wiser:pathToNameObject/wiser:name) ?child.
        OPTIONAL {{ ?parentElement (wiser:pathToGeographyObject/wiser:hasGeography) ?parentLocation. }}
        OPTIONAL {{ ?parentElement (wiser:pathToUnitObject/wiser:hasUnit) ?parentUnit. }}
        FILTER(?parentElement != ?childElement)
    }}
    """
    data = sparql_query(query, SPARQL_ENDPOINT_URL)
    bindings = data['results']['bindings']
    results = [
        {
            'src': binding.get('src', {}).get('value'),
            'parentElement': binding.get('parentElement', {}).get('value'),
            'parent': binding.get('parent', {}).get('value'),
            'childElement': binding.get('childElement', {}).get('value'),
            'child': binding.get('child', {}).get('value'),
            'location': binding.get('location', {}).get('value'),
            'value': binding.get('value', {}).get('value'),
            'unit': binding.get('unit', {}).get('value'),
            'parentLocation': binding.get('parentLocation', {}).get('value'),
            'parentUnit': binding.get('parentUnit', {}).get('value'),
        }
        for binding in bindings
    ]
    return results

def get_biosphere(selected_src):
    print('selected src', selected_src)
    query = f"""
    PREFIX ec1h: <http://www.EcoInvent.org/EcoSpold01#>
    PREFIX : <https://purl.org/wiser#>
    PREFIX wiser: <https://purl.org/wiser#>
    PREFIX process: <http://lca.jrc.it/ILCD/Process/>
    PREFIX pr: <http://lca.jrc.it/ILCD/Process#>
    PREFIX common: <http://lca.jrc.it/ILCD/Common/>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX flo: <http://lca.jrc.it/ILCD/Flow#>
    PREFIX ilcd: <http://lca.jrc.it/ILCD#>
    SELECT DISTINCT ?src ?parentElement ?srcLabel ?exchangeName ?unit ?value ?category ?subCategory ?isOutput ?isInput
    WHERE {{
        VALUES(?src){{( <{selected_src}> )}}
        ?src (wiser:hasChildActivitiy)* ?parentElement.
        ?parentElement (wiser:pathToNameObject/wiser:name) ?srcLabel.
        ?parentElement wiser:hasExchange ?exchange.
        ?exchange a :BBiosphereExchange.
        ?exchange (wiser:pathToExchangeNameObject/wiser:name) ?exchangeName.
        ?exchange (wiser:pathToExchangeUnitObject/wiser:hasUnit) ?unit.
        ?exchange wiser:hasMeanValue ?value.
        ?exchange wiser:category ?category.
        ?exchange wiser:subCategory ?subCategory.
        OPTIONAL {{ ?exchange a :BBiopshereInputExchange. BIND(true AS ?isInput) }}
        OPTIONAL {{ ?exchange a :BBiosphereOutputExchange. BIND(true AS ?isOutput) }}
        FILTER(CONTAINS(LCASE(STR(?exchangeName)), "carbon dioxide"))
    }}
    """
    data = sparql_query(query, SPARQL_ENDPOINT_URL)
    bindings = data['results']['bindings']
    results = [
        {
            'src': binding.get('src', {}).get('value'),
            'parentElement': binding.get('parentElement', {}).get('value'),
            'srcLabel': binding.get('srcLabel', {}).get('value'),
            'exchangeName': binding.get('exchangeName', {}).get('value'),
            'unit': binding.get('unit', {}).get('value'),
            'value': binding.get('value', {}).get('value'),
            'category': binding.get('category', {}).get('value'),
            'subCategory': binding.get('subCategory', {}).get('value'),
            'isOutput': binding.get('isOutput', {}).get('value'),
            'isInput': binding.get('isInput', {}).get('value'),
        }
        for binding in bindings
    ]
    return results
