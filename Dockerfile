FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY wms_proxy.py .

EXPOSE 5000

CMD ["python", "wms_proxy.py"]
