# ============================================================
#  FOREMAN — Dockerfile
#  Zweck: schlankes Laufzeit-Image für die FOREMAN-App (inkl. spaCy-de-Modell
#         für die NER-Maskierung der Werker-Freitexte).
#  Architektur-Einordnung: Betrieb (Schicht 2). Build via uv.
# ============================================================

# Beide Images sind auf ihren Digest festgelegt, in der Form `tag@sha256:...`.
# Der Tag steht dabei nicht zur Zierde: Er sagt, WAS gemeint ist, und er ist die
# Angabe, an der eine Aktualisierung ansetzen kann — ein nackter Digest waere
# reproduzierbar, aber niemand koennte ihm ansehen, wovon er die Fassung ist.
#
# Der Digest ist der Unterschied zwischen „irgendein Image, das damals unter
# diesem Tag lag" und „dieses Image". Ohne ihn baut derselbe Commit an zwei Tagen
# zwei verschiedene Ergebnisse, und ein Fehler, der beim einen auftritt, ist beim
# anderen nicht nachvollziehbar. Dieselbe Linie, die in der Prueferkette schon
# gilt: dort haengen die Actions an einem Commit, nicht an einer Marke.
#
# WAS DAS KOSTET, und das gehoert dazu: Ein festgelegtes Image altert. Solange
# die Routine-Vorschlaege von Dependabot abgeschaltet sind (.github/dependabot.yml
# nennt den Grund), wandert eine neuere Fassung nicht von selbst herein — die
# Aktualisierung bleibt eine bewusste Handlung. Die Wiedervorlage dafuer fuehrt
# security/findings.yaml unter F-009.
FROM python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17 AS base

# uv aus dem offiziellen Image kopieren (schneller, reproduzierbarer Resolver).
# Vorher stand hier `:latest` — das ist die eine Marke, die per Definition nie
# dieselbe bleibt.
COPY --from=ghcr.io/astral-sh/uv:0.12.6@sha256:88bc6eb1ccd4b82efd0e1b530caffabddf50dc2bf612e66c14ea25b8ee8a4d3d /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# 1) Abhängigkeiten zuerst (Layer-Cache): Manifest + README (für Package-Metadaten) kopieren, dann auflösen.
COPY pyproject.toml README.md ./

# torch ZUERST und ausdrücklich aus dem CPU-Index. Die Vorgabe von PyPI zieht die
# CUDA-Bibliotheken mit — mehrere Gigabyte, die auf einer Maschine ohne
# Grafikkarte nie benutzt werden. Der Schritt steht hier und nicht nur in
# [tool.uv.sources], weil die `uv pip`-Schnittstelle diesen Abschnitt NICHT
# liest; er gilt für `uv sync`/`uv lock`.
#
# Der zweite Aufruf lässt torch stehen: Die CPU-Variante erfüllt `torch>=2.2`
# bereits, und uv installiert nichts nach, was schon passt.
RUN uv pip install --system --no-cache torch --index-url https://download.pytorch.org/whl/cpu
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

# Geprueft wird /readyz, nicht /health: Der Container soll erst "gesund" melden, wenn
# er ARBEITEN kann, und dazu gehoert eine antwortende Datenbank. /health beantwortet
# nur, ob der Prozess lebt — als einzige Sonde waere das die falsche Frage, weil ein
# lebender Prozess ohne Datenbank jede Anfrage in einen Fehler laufen laesst und
# trotzdem gruen meldet.
#
# Auf Railway prueft die Plattform von aussen (healthcheckPath, ebenfalls /readyz);
# das hier traegt den lokalen docker-compose-Betrieb, wo ein "laeuft" ohne Antwort
# sonst nicht auffaellt.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=4)"

CMD ["uvicorn", "foreman.main:app", "--host", "0.0.0.0", "--port", "8000"]
