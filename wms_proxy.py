from flask import Flask, request, Response
import requests
from lxml import etree
import logging
import os
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from pyproj import Transformer

app = Flask(__name__)

# Configuration from environment variables
UPSTREAM_WMS = os.getenv('UPSTREAM_WMS', 'http://default-upstream.org/wms')
PROXY_ADDRESS = os.getenv('PROXY_ADDRESS', 'http://localhost:5555')
PORT = int(os.getenv('PORT', 5555))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

@app.route('/', methods=['GET'], defaults={'path': ''})
@app.route('/<path:path>', methods=['GET'])
def wms_proxy(path):
    # Split path from potential inline parameters
    path_parts = path.split('?', 1)  # Split at first ?
    script_path = path_parts[0]
    path_params = parse_qs(path_parts[1]) if len(path_parts) > 1 else {}
    
    # Merge parameters from both path and query string
    query_params = request.args.to_dict()
    merged_params = {**path_params, **query_params}
    
    # Properly flatten parameters while preserving multiple values
    final_params = {}
    for k, v in merged_params.items():
        if isinstance(v, list) and len(v) == 1:
            final_params[k] = v[0]
        else:
            final_params[k] = v
            
    # Find CRS/SRS parameter name case-insensitively
    crs_param = next((k for k in final_params if k.upper() in ['SRS', 'CRS']), None)

    if crs_param and final_params[crs_param].upper() == 'EPSG:4326' and 'BBOX' in final_params:
        try:
            # Parse coordinates considering WMS version axis order
            bbox_parts = list(map(float, final_params['BBOX'].split(',')))
            
            # Handle WMS 1.3+ axis order for EPSG:4326 (y, x)
            if final_params.get('VERSION', '') >= '1.3.0' and final_params[crs_param].upper() == 'EPSG:4326':
                miny, minx, maxy, maxx = bbox_parts
            else:  # WMS <1.3.0 or non-geographic CRS
                minx, miny, maxx, maxy = bbox_parts
                
            # Transform coordinates
            transformer = Transformer.from_crs("EPSG:4326", "EPSG:3301", always_xy=True)
            minx_t, miny_t = transformer.transform(minx, miny)
            maxx_t, maxy_t = transformer.transform(maxx, maxy)
            
            # Update parameters
            final_params['BBOX'] = f"{minx_t},{miny_t},{maxx_t},{maxy_t}"
            final_params[crs_param] = 'EPSG:3301'
            
        except Exception as e:
            app.logger.error(f"BBOX transformation failed: {str(e)}")
            raise
    
    app.logger.info(f"Proxying to {UPSTREAM_WMS} with params: {final_params}")
    
    # Build upstream URL
    upstream_url = urljoin(UPSTREAM_WMS, script_path)
    
    # Prepare the outgoing request
    req = requests.Request(
        method='GET',
        url=upstream_url,
        params=final_params,
        headers={k: v for k, v in request.headers.items() if k.lower() != 'host'}
    )
    prepared = req.prepare()
    
    # Log full upstream request URL with parameters
    app.logger.info(f"Proxying upstream request to: {prepared.url}")
    
    # Send the prepared request
    with requests.Session() as s:
        upstream_response = s.send(prepared, stream=True)
    
    # Process XML responses
    if 'xml' in upstream_response.headers.get('Content-Type', ''):
        xml_content = upstream_response.content
        modified_xml = rewrite_xml_urls(xml_content)
        return Response(modified_xml, content_type=upstream_response.headers['Content-Type'])
    
    # Return unmodified response for non-XML
    return Response(upstream_response.iter_content(chunk_size=2048),
                   content_type=upstream_response.headers['Content-Type'])

def rewrite_xml_urls(xml_content):
    # Parse configured URLs
    upstream = urlparse(UPSTREAM_WMS)
    proxy = urlparse(PROXY_ADDRESS)
    
    # XML processing setup
    ns = {'xlink': 'http://www.w3.org/1999/xlink'}
    root = etree.fromstring(xml_content)
    
    for elem in root.xpath('//*[@xlink:href]', namespaces=ns):
        href = elem.attrib['{http://www.w3.org/1999/xlink}href']
        original = urlparse(href)
        
        # Match upstream service's network location
        if original.netloc == upstream.netloc:
            # Preserve path/query/fragment and combine with proxy URL
            new_url = urlunparse((
                proxy.scheme,
                proxy.netloc,
                original.path,
                original.params,
                original.query,
                original.fragment
            ))
            elem.attrib['{http://www.w3.org/1999/xlink}href'] = new_url
    
    return etree.tostring(root, encoding='utf-8', xml_declaration=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
