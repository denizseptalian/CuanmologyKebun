FROM python:3.11-slim

WORKDIR /app

# Install system deps untuk curl_cffi dan pyarrow
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh project
COPY . .

# Expose port Streamlit
EXPOSE 8501

# Jalankan Streamlit
CMD ["python", "-m", "streamlit", "run", "web/streamlit_app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
