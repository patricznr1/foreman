# ============================================================
#  FOREMAN — core/sanitize.py
#  Zweck: Output-Sanitisierung untrusted Freitexts (LLM05, Output-Smuggling).
#  Architektur-Einordnung: Querschnitt (Schicht 0) — von der Reasoner- UND der
#         Archiv-Seite genutzt, ohne dass eine die andere importiert.
#  Herkunft: die Regeln lagen bis 20.08.2026 allein in
#         reasoners/event_chain/recall.py. Mit der Substrat-Veredelung fliesst
#         derselbe untrusted Inhalt auch in die Archiv-Trefferliste; eine zweite
#         Kopie waere die Stelle, an der die beiden Fassungen auseinanderlaufen.
#         `event_chain.recall` re-exportiert `clean_excerpt` unveraendert
#         (Vorbild: realtime/authz.py re-exportiert die ROLE_*-Namen).
# ============================================================
from __future__ import annotations

import re

# HTML-Tags, Markdown-Links und rohe URLs. `javascript:`/`data:`/`vbscript:`
# stehen bewusst mit in der Schema-Liste: sie sind der Weg, auf dem ein Auszug
# im Browser vom Text zur Handlung wird.
_TAG_RE = re.compile(r"<[^>]*>")
# Das Ziel darf EINE Ebene Klammern enthalten. Mit dem einfacheren `[^)]*`
# endete der Treffer an der ersten schliessenden Klammer: aus
# `[Klick](javascript:steal())` wurde `Klick)` — die Zieladresse verschwand,
# aber ein Klammer-Rest blieb im Auszug stehen. Betrifft jeden Link mit
# Klammern im Ziel, also auch harmlose (`..._(Begriffsklaerung)`).
_MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\((?:[^()]|\([^()]*\))*\)")
_URL_RE = re.compile(r"(?:https?|ftp|file|data|javascript|vbscript):(?://)?\S+", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")

EXCERPT_MAX_LEN = 200


def clean_excerpt(text: str, *, max_len: int = EXCERPT_MAX_LEN) -> str:
    """Sanitisiert + kuerzt untrusted Freitext fuer die reine Anzeige.

    Entfernt HTML/Markdown-Links/rohe URLs (Output-Smuggling, LLM05), normalisiert
    Whitespace und kuerzt auf `max_len` (mit Ellipsis). Der Auszug ist NIE eine
    Instruktion — er wird im FE nur dargestellt.

    Reihenfolge ist tragend: erst Markdown-Links auf ihren Linktext reduzieren,
    dann Tags entfernen, dann verbliebene rohe URLs ersetzen. Umgekehrt bliebe
    aus `[text](javascript:...)` die Ziel-Adresse als Klartext stehen.
    """
    cleaned = _MD_LINK_RE.sub(r"\1", text)
    cleaned = _TAG_RE.sub("", cleaned)
    cleaned = _URL_RE.sub("[link entfernt]", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1].rstrip() + "…"
    return cleaned
