FROM python:3.12-slim

WORKDIR /app

# (opzionale) dipendenze di sistema minimali
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000

# DB su file: in container resta in /app/app.db (puoi montare un volume)
ENV DB_URL=sqlite:///./app.db

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
