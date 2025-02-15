from flask import Flask, request, Response
import requests
from lxml import etree
import logging
import os
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from pyproj import Transformer, CRS

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
    for original_key, value in merged_params.items():
        key = original_key.upper()
        if isinstance(value, list): 
            # Filter out any empty values first
            non_empty = [v for v in value if v is not None and str(v).strip() != '']
            if len(non_empty) == 1:
                final_params[key] = non_empty[0]
            elif len(non_empty) > 1:
                final_params[key] = non_empty
            # Else: don't add empty lists
        elif value:  # Handle scalar values that are not in list form
            final_params[key] = value
            
    # Find CRS/SRS parameter name case-insensitively
    crs_param = next((k for k in ['SRS', 'CRS'] if k in final_params), None)

    if crs_param and final_params[crs_param].upper() == 'EPSG:4326' and 'BBOX' in final_params:
        try:
            version = final_params.get('VERSION', '1.1.1')
            source_crs = "EPSG:4326"
            target_crs = "EPSG:3301"
            
            target_crs_proj = (
                "+proj=lcc "
                "+lat_1=59.33333333333334 "
                "+lat_2=58 "
                "+lat_0=57.51755393055556 "
                "+lon_0=24 "
                "+x_0=500000 "
                "+y_0=6375000 "
                "+ellps=GRS80 "
                "+towgs84=0,0,0,0,0,0,0 "
                "+units=m "
                "+no_defs"
            )

            transformer = Transformer.from_crs(
                {"proj": "longlat", "ellps": "WGS84", "datum": "WGS84"},  # WGS84 definition
                target_crs_proj,  # Your custom LCC projection
                always_xy=True
            )
            


            # Parse coordinates with scientific notation handling
            bbox_parts = [float(x) for x in final_params['BBOX'].replace(' ', '').split(',')]
            
            # Handle WMS version-specific axis order
            if version >= '1.3.0' and final_params[crs_param].upper() == 'EPSG:4326':
                # WMS 1.3+ uses (Lat, Lon) order for EPSG:4326
                min_y, min_x, max_y, max_x = bbox_parts
            else:
                # WMS <1.3.0 uses (Lon, Lat) order
                min_x, min_y, max_x, max_y = bbox_parts

            # Transform with high precision
            min_x_t, min_y_t = transformer.transform(min_x, min_y)
            max_x_t, max_y_t = transformer.transform(max_x, max_y)

            # Format coordinates with adequate precision (6 decimal places = ~0.1m)
            if version >= '1.3.0':
                # For WMS 1.3+, flip coordinates back to Y,X order
                transformed_bbox = f"{min_y_t:.6f},{min_x_t:.6f},{max_y_t:.6f},{max_x_t:.6f}"
            else:
                # Keep X,Y order for older versions
                transformed_bbox = f"{min_x_t:.6f},{min_y_t:.6f},{max_x_t:.6f},{max_y_t:.6f}"
            
            # Update parameters
            final_params['BBOX'] = transformed_bbox
            final_params[crs_param] = target_crs
            
            app.logger.debug(f"Transformed BBOX: {transformed_bbox}")

        except Exception as e:
            app.logger.error(f"Coordinate transformation failed: {str(e)}")
            return f"BBOX transformation error: {str(e)}", 400
    
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
