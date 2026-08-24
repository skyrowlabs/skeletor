# Deliberately boring. Every generated app uses this exact file, so it is
# debugged once rather than once per prototype.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv

# Deps first so an app-code change does not invalidate the layer. The repair
# loop rebuilds often; this is the difference between 4s and 90s per attempt.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
