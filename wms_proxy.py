from flask import Flask, request, Response
import requests
from lxml import etree
import logging
import os

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

@app.route('/wms', methods=['GET'])
def wms_proxy():
    # Log parameters
    params = request.args.to_dict()
    app.logger.info(f"WMS request: {params}")
    
    # Forward request to upstream WMS
    upstream_response = requests.get(UPSTREAM_WMS, params=params, stream=True)
    
    # Process XML responses
    if 'xml' in upstream_response.headers.get('Content-Type', ''):
        xml_content = upstream_response.content
        modified_xml = rewrite_xml_urls(xml_content)
        return Response(modified_xml, content_type=upstream_response.headers['Content-Type'])
    
    # Return unmodified response for non-XML
    return Response(upstream_response.iter_content(chunk_size=2048),
                   content_type=upstream_response.headers['Content-Type'])

def rewrite_xml_urls(xml_content):
    # XML processing logic
    ns = {'xlink': 'http://www.w3.org/1999/xlink'}
    root = etree.fromstring(xml_content)
    
    # Find and replace URLs in common WMS elements
    for elem in root.xpath('//OnlineResource[@xlink:href]', namespaces=ns):
        original_url = elem.attrib['{http://www.w3.org/1999/xlink}href']
        if UPSTREAM_WMS in original_url:
            new_url = original_url.replace(UPSTREAM_WMS, PROXY_ADDRESS + '/wms')
            elem.attrib['{http://www.w3.org/1999/xlink}href'] = new_url
    
    return etree.tostring(root, encoding='utf-8', xml_declaration=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
