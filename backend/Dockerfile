FROM python:3.11-slim [cite: 4]
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/* 
WORKDIR /app 

# Copy from the backend subdirectory
COPY backend/requirements.txt . 
RUN pip install --no-cache-dir -r requirements.txt [cite: 5]
COPY backend/ . [cite: 5]

EXPOSE 8000 [cite: 5]
CMD ["python", "main.py"] [cite: 5]