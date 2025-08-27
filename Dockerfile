# ----- Base image με πλήρες apt -----
FROM python:3.12-bullseye

# Απενεργοποίηση .pyc & unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ----- Βασικά system deps + unixODBC -----
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg2 apt-transport-https ca-certificates \
    unixodbc unixodbc-dev \
 && rm -rf /var/lib/apt/lists/*

# ----- Microsoft ODBC Driver 17 (σωστό GPG setup) -----
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
    | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg \
 && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
    > /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 \
 && rm -rf /var/lib/apt/lists/*

# ----- Εγκατάσταση Python deps -----
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Αντιγραφή κώδικα
COPY . .

# ----- Εκκίνηση με gunicorn -----
ENV PORT=8080
EXPOSE 8080
# Αν το module σου δεν είναι app.py ή το αντικείμενο δεν είναι app, άλλαξέ το εδώ
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--timeout", "120"]
