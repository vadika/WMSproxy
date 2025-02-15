 # WMS Proxy Service

 A reverse proxy for WMS services that rewrites XML responses to point through the
 proxy. Handles Capabilities documents and GetMap requests while maintaining client
 compatibility.

 ## Features

 - 🔄 Transparent WMS request proxying
 - ✏️ URL rewriting in XML responses (Capabilities documents)
 - 🔀 Merges path and query parameters
 - ⚙️ Configurable via environment variables
 - 🐳 Docker-ready deployment
 - 📊 Detailed request logging

 ## Quick Start

 ### Prerequisites
 - Python 3.8+
 - Docker (optional)

 ### Running with Docker
 1. Create `.env` file:
    ```ini
    UPSTREAM_WMS=https://mapantee.gokartor.se/ogc/wms.php
    PROXY_ADDRESS=http://your-domain.com:5555
    PORT=5555
    ```

 2. Start container:
```
    docker-compose up -d
```

 ###  Without Docker

 1. Install requirements:
```
    pip install -r requirements.txt
```
 2. Run service:
```
    UPSTREAM_WMS=https://mapantee.gokartor.se/ogc/wms.php \
    PROXY_ADDRESS=http://localhost:5555 \
    PORT=5555 \
    python wms_proxy.py
```


   ###                                  Configuration


  Environment Variable   Required   Default   Description
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  UPSTREAM_WMS           Yes                  Upstream WMS service URL
  PROXY_ADDRESS          Yes                  External URL to access this proxy
  PORT                   No         5555      Port to listen on



   ###                                    Usage

Proxy URL structure:
```
http://{PROXY_ADDRESS}/path/from/upstream?parameters
```
Example request:
```
 curl "http://localhost:5555/ogc/wms.php?\
 service=WMS&\
 request=GetCapabilities"
```


   ###                                  Verification

Check logs after making a request:

```
 [INFO] Proxying upstream request to: https://upstream-service/wms.php?service=WMS...
 [INFO] 127.0.0.1 - - [timestamp] "GET /wms.php?service=WMS" 200 -
```


   ###                                 Troubleshooting

 1. Missing Parameters
   Verify:
    - Both path-based (/wms.php?param=value) and query params (?param=value) are
      supported
    - Check proxy logs for complete parameter list
 2. XML URLs Not Rewriting
   Ensure:
    - PROXY_ADDRESS matches your external access URL
    - UPSTREAM_WMS exactly matches the backend service URL
    - Response contains valid XML with xlink:href attributes
 3. Connection Issues
   Confirm:
    - Upstream service is reachable from proxy
    - Required ports are open
    - No CORS restrictions on backend service


