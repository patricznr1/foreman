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

# 2a) Einbettungs-Modell (Snowflake Arctic v2.0, ~2,3 GB) — dieselbe Überlegung wie
#     beim spaCy-Modell darüber: im Image, nicht zur Laufzeit.
#
#     Der Grund, warum es hier steht und nicht auf einem Volume liegt: Railway
#     hängt Volumes so ein, dass ein Abbild mit nicht-privilegiertem Nutzer nicht
#     hineinschreiben kann (Railway-Doku, „Caveats"). Der dort vorgeschlagene
#     Ausweg wäre RAILWAY_RUN_UID=0 — also der Dienst als root, und damit genau
#     die Härtung zurückgenommen, die weiter unten begründet steht.
#
#     Was passiert, wenn das Modell FEHLT, ist der eigentliche Anlass: Der
#     Ladefehler wird zu `ProviderUnavailable`, und `embed_and_search_hybrid`
#     fängt den ab und sucht still nur noch im Volltext weiter. Kein Fehler beim
#     Werker, nur eine Warnung im Protokoll — die Suche sieht funktionsfähig aus
#     und hat ihren semantischen Zweig verloren.
#
#     ALLES IN EINER SCHICHT, und das ist kein Schönheitsgrund: Ein nachgelagertes
#     `chown -R` schriebe alle 2,3 GB ein zweites Mal ins Abbild. Deshalb wird der
#     Nutzer schon hier angelegt statt erst unten bei USER.
#
#     Der Modellname steht hier wörtlich, damit die Schicht zwischenspeicherbar
#     bleibt. Dass er nicht von `EmbeddingSettings.st_model` abdriften kann, hält
#     tests/unit/test_modell_im_image.py fest.
RUN useradd --create-home --uid 10001 foreman \
    && mkdir -p /opt/hf-cache \
    && HF_HOME=/opt/hf-cache python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('Snowflake/snowflake-arctic-embed-l-v2.0', device='cpu')" \
    && chown -R foreman:foreman /opt/hf-cache

# Zur Laufzeit dieselbe Stelle. Eine Dienst-Variable gleichen Namens würde das hier
# überstimmen — dann läge der Zwischenspeicher woanders und das Modell im Abbild
# wäre unerreichbar.
ENV HF_HOME=/opt/hf-cache

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
#    Einzige Ausnahme ist /opt/hf-cache: Der Zwischenspeicher gehört diesem Nutzer,
#    damit die Einbettungs-Bibliothek dort ihre Sperrdateien anlegen kann.
#    Der Nutzer selbst entsteht schon weiter oben (Schritt 2a) — siehe die
#    Begründung dort, warum das nicht erst hier passiert.
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
