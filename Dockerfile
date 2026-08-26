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

# 1) Abhängigkeiten zuerst (Layer-Cache): Manifest + README (für Package-Metadaten) kopieren, dann auflösen.
COPY pyproject.toml README.md ./
RUN uv pip install --system --no-cache .

# 2) NER-Modell für die Freitext-Maskierung (Research §5.3 b).
#    ~560 MB — bewusst im Image, damit der heiße Pfad ohne Laufzeit-Download startet.
RUN python -m spacy download de_core_news_lg

# 2b) System-Laufzeitbibliothek: libgomp1 (OpenMP) wird von LightGBM (Ausfallvorhersage-
#     Reasoner) zur Laufzeit dynamisch geladen — im slim-Image nicht enthalten.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 3) Anwendungscode + Migrationen
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

ENV PYTHONPATH=/app/src

# 4) Unprivilegiert laufen (wie das Frontend-Image, das den mitgelieferten Nutzer
#    'node' verwendet). Ohne diesen Schritt liefe uvicorn als root, und jede
#    Codeausführungs-Lücke wäre unmittelbar root im Container.
#    Feste UID, damit ein gemountetes Volume berechenbare Eigentumsverhältnisse hat.
#    Es wird nichts umgeschrieben: Der Code unter /app, die Pakete unter
#    site-packages und das spaCy-Modell sind welt-lesbar, und geschrieben wird zur
#    Laufzeit nichts — Protokolle gehen nach stdout, der Zustand in die Datenbank.
RUN useradd --create-home --uid 10001 foreman
USER foreman

EXPOSE 8000

# Der Container meldet erst „gesund", wenn die Anwendung antwortet — nicht schon,
# wenn der Prozess gestartet ist. Auf Railway prüft die Plattform ohnehin von außen
# (healthcheckPath); das hier trägt den lokalen docker-compose-Betrieb, wo ein
# „läuft" ohne Antwort sonst nicht auffällt.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["uvicorn", "foreman.main:app", "--host", "0.0.0.0", "--port", "8000"]
