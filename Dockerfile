FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlite3-0 \
    libtiff5 \
    libcurl4 \
    && rm -rf /var/lib/apt/lists/*

ENV PROJ_NETWORK=OFF

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY wms_proxy.py .

EXPOSE 5000

CMD ["python", "wms_proxy.py"]
