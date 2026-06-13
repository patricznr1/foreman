# ============================================================
#  FOREMAN — Dockerfile
#  Zweck: schlankes Laufzeit-Image für die FOREMAN-App (inkl. spaCy-de-Modell
#         für die NER-Maskierung der Werker-Freitexte).
#  Architektur-Einordnung: Betrieb (Schicht 2). Build via uv.
# ============================================================

FROM python:3.12-slim AS base

# uv aus dem offiziellen Image kopieren (schneller, reproduzierbarer Resolver)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# 1) Abhängigkeiten zuerst (Layer-Cache): nur Manifest kopieren, dann auflösen.
COPY pyproject.toml ./
RUN uv pip install --system --no-cache .

# 2) NER-Modell für die Freitext-Maskierung (Research §5.3 b).
#    ~560 MB — bewusst im Image, damit der heiße Pfad ohne Laufzeit-Download startet.
RUN python -m spacy download de_core_news_lg

# 3) Anwendungscode + Migrationen
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uvicorn", "foreman.main:app", "--host", "0.0.0.0", "--port", "8000"]
