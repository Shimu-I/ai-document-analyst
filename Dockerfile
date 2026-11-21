FROM python:3.12-slim

# tesseract = OCR for scanned PDFs and images.  Add libreoffice-writer, libreoffice-calc and libreoffice-impress to also open old .doc/.xls/.ppt files.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 8000 = API, 8501 = web page
EXPOSE 8000 8501

# Default: the API. The web page:  docker compose up ui
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
