# ============================================================
#  FOREMAN — tests/unit/test_pre_push_walkthrough.py
#  Zweck: Der Push-Hook .claude/hooks/pre-push-walkthrough.py erkennt einen
#         echten Push je Teilbefehl — an seiner Form, hinter Variablen,
#         Schlüsselwörtern, Vorschaltern und Schalen, mit Trockenlauf-Semantik
#         wie git — und zählt nur, was den Rechner verlässt: Committetes auf dem
#         Ref, den der Push trägt, im Repo, in dem der Push läuft (cd, -C,
#         --git-dir/--work-tree). Jede Klasse hier ist ein belegter Angriff oder
#         eine belegte Überblockung (drei Skeptiker und Greptile, 07.09.2026).
#  Architektur-Einordnung: Quality Gate §10.3 (Unit, kein DB-Zugriff); git als
#         Subprozess gegen ein Wegwerf-Repository unter tmp_path.
# ============================================================
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / ".claude" / "hooks" / "pre-push-walkthrough.py"


@pytest.fixture(scope="module")
def hook() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pre_push_walkthrough", HOOK)
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout


def _schreibe(pfad: Path, text: str) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(text, encoding="utf-8")


@pytest.fixture
def zweig(tmp_path: Path) -> Path:
    """Ein Repo mit origin/main und einem Feature-Zweig, der Anwendungscode committet hat."""
    fern = tmp_path / "origin.git"
    _git("init", "--bare", "-b", "main", str(fern), cwd=tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    _schreibe(repo / "docs" / "WALKTHROUGH.md", "# WALKTHROUGH\n")
    _schreibe(repo / "src" / "foreman" / "kern.py", "WERT = 1\n")
    _git("add", ".", cwd=repo)
    _git("commit", "-q", "-m", "Grundstein", cwd=repo)
    _git("remote", "add", "origin", str(fern), cwd=repo)
    _git("push", "-q", "origin", "main", cwd=repo)
    _git("switch", "-q", "-c", "feature/x", cwd=repo)
    _schreibe(repo / "src" / "foreman" / "kern.py", "WERT = 2\n")
    _git("commit", "-q", "-am", "Kern geaendert", cwd=repo)
    return repo


@pytest.fixture
def fremd(tmp_path: Path) -> Path:
    """Ein Repo ohne WALKTHROUGH — den Hook geht es nichts an."""
    repo = tmp_path / "fremd"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    _schreibe(repo / "a.txt", "x\n")
    _git("add", ".", cwd=repo)
    _git("commit", "-q", "-m", "a", cwd=repo)
    return repo


def _lauf(
    hook: ModuleType,
    befehl: str,
    cwd: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str]:
    nutzlast = {"tool_name": "Bash", "tool_input": {"command": befehl}, "cwd": str(cwd)}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(nutzlast)))
    code = hook.main()
    return code, capsys.readouterr().err


# --- Was ein Push ist: je Teilbefehl, nicht als Zeichenkette ------------------


@pytest.mark.parametrize(
    "befehl",
    [
        "git push",
        "  git push origin feature/x",
        "git -C /irgendwo/foreman push",
        "git -c push.default=current push origin feature/x",
        "git push --dry-run && git push",
        "git push --dry-run; git push",
        "git pull --ff-only && git push",
        "echo x; git push origin feature/x",
        "sh -c 'git push origin feature/x'",
        "git.exe push",
        "/usr/bin/git push origin feature/x",
        '"C:\\Program Files\\Git\\bin\\git.exe" push origin feature/x',
        # Variablen vor dem Programm — das gängige Muster gegen Passwortabfragen.
        "GIT_TERMINAL_PROMPT=0 git push origin feature/x",
        'GIT_SSH_COMMAND="ssh -o BatchMode=yes" git push origin feature/x',
        # Zeilenfortsetzung zwischen git-Option und Unterbefehl.
        'git -C "$PWD" \\\n  push origin feature/x',
        # Schlüsselwörter, Gruppierung, Substitution, Verzeichniswechsel.
        "for b in feature/x; do git push origin $b; done",
        "if ! git push origin feature/x; then echo fehl; fi",
        "{ git push origin feature/x; }",
        '(cd "$PWD" && git push)',
        "cd /pfad/zum/foreman && git push origin feature/x",
        'OUT=$(git push origin feature/x 2>&1); echo "$OUT"',
        # Ein Kommentar hinter dem Push ist kein Argument.
        "git push origin feature/x # -n",
        "git push origin feature/x  # vorher --dry-run gemacht",
        # Wie bei git gewinnt die letzte Option.
        "git push --dry-run --no-dry-run origin feature/x",
        "git push -n --no-dry-run origin feature/x",
        # Vorschalter und Schalen.
        "timeout 30 git push origin feature/x",
        "command git push origin feature/x",
        "time git push origin feature/x",
        "winpty git push origin feature/x",
        "sudo bash -c 'git push origin feature/x'",
        'cmd /c "git push origin feature/x"',
        "cmd /c git push origin feature/x",
        # Escapte Anführungszeichen davor schliessen keinen Teilbefehl auf.
        "git commit --allow-empty -m 'Don'\\''t' && git push origin feature/x",
        "echo It\\'s done && git push origin feature/x",
        'git commit -m "Say \\"hi" && git push origin feature/x',
    ],
)
def test_ein_echter_push_wird_erkannt(hook: ModuleType, befehl: str) -> None:
    assert hook.enthaelt_echten_push(befehl)


@pytest.mark.parametrize(
    "befehl",
    [
        "git push --dry-run",
        "git push -n origin feature/x",
        "git push -nv origin feature/x",
        "git push --dry-run origin feature/x && echo fertig",
        "git push --dry-run; echo ok",
        "git push --no-dry-run --dry-run origin feature/x",
        "git push -h",
        "git push --help",
        "echo 'git push'",
        "git commit -m 'vor dem git push'",
        "grep -rn 'git push' docs/",
        "git status | grep push",
        "gh pr create --fill",
        "git pushd",
        "git log --oneline origin/main..HEAD",
        # Ein Heredoc-Rumpf ist Text — auch wenn eine Zeile mit git push beginnt.
        "cat > docs/DEPLOY.md <<'EOF'\n## Veroeffentlichen\ngit push origin main\nEOF",
        "git commit -F - <<'EOF'\nUmbau\n\ngit push wurde umgestellt\nEOF",
        # Escaptes Semikolon trennt nicht; eine Commit-Message hinter einem
        # Vorschalter ist kein Befehl.
        "echo a\\; git push",
        'timeout 30 git commit -m "git push later"',
        "# git push",
    ],
)
def test_kein_echter_push(hook: ModuleType, befehl: str) -> None:
    assert not hook.enthaelt_echten_push(befehl)


@pytest.mark.parametrize(
    ("befehl", "quellen"),
    [
        ("git push", ["HEAD"]),
        ("git push origin", ["HEAD"]),
        ("git push -u origin feature/x", ["feature/x"]),
        ("git push origin +feature/x", ["feature/x"]),
        ("git push origin feature/x:refs/heads/x", ["feature/x"]),
        ("git push origin HEAD~1:refs/heads/nur-basis", ["HEAD~1"]),
        ("git push origin --delete feature/x", []),
        ("git push origin :feature/x", []),
        ("git push origin --tags", []),
        ("git push --all origin", ["*"]),
        ("git push -o ci.skip origin feature/x", ["feature/x"]),
        # Mit --repo ist die erste Position eine Refspec, kein Remote.
        ("git push --repo=origin feature/x", ["feature/x"]),
        ("git push --repo origin feature/x", ["feature/x"]),
    ],
)
def test_die_quellen_eines_pushes(hook: ModuleType, befehl: str, quellen: list[str]) -> None:
    (push,) = hook.echte_pushes(befehl)
    assert hook._quellen(push.argumente) == quellen


@pytest.mark.parametrize(
    ("befehl", "verzeichnis", "optionen"),
    [
        ("git push", None, ()),
        ('git -C "C:\\foreman" push origin feature/x', None, ("-C", "C:\\foreman")),
        (
            "git --work-tree=/w --git-dir=/w/.git push",
            None,
            ("--work-tree=/w", "--git-dir=/w/.git"),
        ),
        ("cd /pfad/zum/foreman && git push origin feature/x", "/pfad/zum/foreman", ()),
        ("cd frontend; git push", "frontend", ()),
        ("pushd x && git push", "x", ()),
        ("cd x && git -C y push", "x", ("-C", "y")),
        ("cd a && cd b && git push", str(Path("a") / "b"), ()),
        ("cd a && cd /abs && git push", "/abs", ()),
        ("bash -c 'cd /w && git push'", "/w", ()),
    ],
)
def test_wo_der_push_laeuft(
    hook: ModuleType, befehl: str, verzeichnis: str | None, optionen: tuple[str, ...]
) -> None:
    (push,) = hook.echte_pushes(befehl)
    assert push.verzeichnis == verzeichnis
    assert push.optionen == optionen


# --- Das Gate: nur Committetes verlaesst das Haus -----------------------------


def test_committeter_code_ohne_walkthrough_sperrt(
    hook: ModuleType,
    zweig: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, err = _lauf(hook, "git push origin feature/x", zweig, monkeypatch, capsys)
    assert code == 2
    assert "src/foreman/kern.py" in err
    assert "feature/x" in err


def test_walkthrough_im_zweig_committet_laesst_durch(
    hook: ModuleType,
    zweig: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _schreibe(zweig / "docs" / "WALKTHROUGH.md", "# WALKTHROUGH\n\n## Kern\nWERT ist jetzt 2.\n")
    _git("commit", "-q", "-am", "Walkthrough nachgezogen", cwd=zweig)
    code, _ = _lauf(hook, "git push origin feature/x", zweig, monkeypatch, capsys)
    assert code == 0


def test_ein_nur_lokal_geaenderter_walkthrough_ist_kein_nachtrag(
    hook: ModuleType,
    zweig: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Die offene Aenderung verlaesst den Rechner nicht.
    _schreibe(zweig / "docs" / "WALKTHROUGH.md", "# WALKTHROUGH\n\n## Kern\nnoch nicht committet\n")
    code, err = _lauf(hook, "git push origin feature/x", zweig, monkeypatch, capsys)
    assert code == 2
    assert "nicht committet" in err


def test_trockenlauf_vor_echtem_push_schuetzt_nicht(
    hook: ModuleType,
    zweig: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, _ = _lauf(
        hook, "git push --dry-run && git push origin feature/x", zweig, monkeypatch, capsys
    )
    assert code == 2


def test_git_option_vor_dem_unterbefehl_wird_gesehen(
    hook: ModuleType,
    zweig: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, _ = _lauf(hook, f'git -C "{zweig}" push origin feature/x', zweig, monkeypatch, capsys)
    assert code == 2


def test_fuehrender_leerraum_wird_gesehen(
    hook: ModuleType,
    zweig: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, _ = _lauf(hook, "  git push origin feature/x", zweig, monkeypatch, capsys)
    assert code == 2


def test_trockenlauf_allein_laeuft_durch(
    hook: ModuleType,
    zweig: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, _ = _lauf(hook, "git push --dry-run origin feature/x", zweig, monkeypatch, capsys)
    assert code == 0


def test_ausnahme_mit_grund_laeuft_durch(
    hook: ModuleType,
    zweig: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, _ = _lauf(
        hook,
        "git push origin feature/x  # Walkthrough-Ausnahme: nur ein Tippfehler im Wording",
        zweig,
        monkeypatch,
        capsys,
    )
    assert code == 0


def test_ausnahme_ohne_grund_sperrt(
    hook: ModuleType,
    zweig: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Der Zwilling: das Kuerzel ist eine Entscheidung, und eine Entscheidung hat einen Grund.
    code, _ = _lauf(
        hook, "git push origin feature/x  # Walkthrough-Ausnahme:", zweig, monkeypatch, capsys
    )
    assert code == 2


def test_nur_lokal_geaenderter_code_verlaesst_das_haus_nicht(
    hook: ModuleType,
    zweig: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _git("switch", "-q", "-c", "feature/leer", "main", cwd=zweig)
    _schreibe(zweig / "src" / "foreman" / "kern.py", "WERT = 3\n")
    code, _ = _lauf(hook, "git push origin feature/leer", zweig, monkeypatch, capsys)
    assert code == 0


def test_ein_repo_ohne_walkthrough_ist_nicht_betroffen(
    hook: ModuleType,
    fremd: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, _ = _lauf(hook, "git push origin main", fremd, monkeypatch, capsys)
    assert code == 0


# --- Gepusht wird der Ref aus dem Befehl, nicht HEAD --------------------------


def test_der_gepushte_zweig_zaehlt_auch_wenn_head_woanders_steht(
    hook: ModuleType,
    zweig: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _git("switch", "-q", "main", cwd=zweig)
    code, err = _lauf(hook, "git push origin feature/x", zweig, monkeypatch, capsys)
    assert code == 2
    assert "feature/x" in err


def test_mit_repo_option_ist_die_erste_position_die_refspec(
    hook: ModuleType,
    zweig: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _git("switch", "-q", "main", cwd=zweig)
    code, _ = _lauf(hook, "git push --repo=origin feature/x", zweig, monkeypatch, capsys)
    assert code == 2


def test_alle_zweige_pushen_zaehlt_jeden(
    hook: ModuleType,
    zweig: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _git("switch", "-q", "main", cwd=zweig)
    code, _ = _lauf(hook, "git push --all origin", zweig, monkeypatch, capsys)
    assert code == 2


@pytest.mark.parametrize(
    "befehl",
    [
        "git push origin main",
        "git push origin --delete feature/x",
        "git push origin HEAD~1:refs/heads/nur-basis",
        "git push origin --tags",
    ],
)
def test_ein_push_der_den_code_nicht_traegt_laeuft_durch(
    hook: ModuleType,
    zweig: Path,
    befehl: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # HEAD steht auf feature/x mit Code ohne Nachtrag — aber dieser Push nimmt ihn nicht mit.
    code, _ = _lauf(hook, befehl, zweig, monkeypatch, capsys)
    assert code == 0


# --- Das Repo ist das, in dem der Push laeuft ---------------------------------


def test_das_repo_kommt_aus_der_git_option_nicht_nur_aus_cwd(
    hook: ModuleType,
    zweig: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    aussen = tmp_path / "aussen"
    aussen.mkdir()
    code, _ = _lauf(hook, f'git -C "{zweig}" push origin feature/x', aussen, monkeypatch, capsys)
    assert code == 2


def test_ein_cd_im_befehl_fuehrt_ins_repo(
    hook: ModuleType,
    zweig: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    aussen = tmp_path / "aussen"
    aussen.mkdir()
    code, _ = _lauf(hook, f'cd "{zweig}" && git push origin feature/x', aussen, monkeypatch, capsys)
    assert code == 2


def test_ein_cd_aus_dem_repo_heraus_prueft_nicht_foreman(
    hook: ModuleType,
    zweig: Path,
    fremd: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # cwd ist FOREMAN mit Code ohne Nachtrag — aber der Push laeuft woanders.
    code, _ = _lauf(hook, f'cd "{fremd}" && git push origin feature/x', zweig, monkeypatch, capsys)
    assert code == 0


def test_getrennter_git_dir_und_work_tree(
    hook: ModuleType,
    zweig: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Der Arbeitsbaum liegt woanders als das Repo — was zaehlt, sind die Refs im Repo.
    aussen = tmp_path / "aussen"
    aussen.mkdir()
    export = tmp_path / "export"
    export.mkdir()
    befehl = f'git --git-dir="{zweig / ".git"}" --work-tree="{export}" push origin feature/x'
    code, _ = _lauf(hook, befehl, aussen, monkeypatch, capsys)
    assert code == 2


# --- Dateinamen und Pfade -----------------------------------------------------


def test_ein_dateiname_mit_leerzeichen_bleibt_ganz(
    hook: ModuleType,
    zweig: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _schreibe(zweig / "src" / "foreman" / "mein modul.py", "X = 1\n")
    _git("add", ".", cwd=zweig)
    _git("commit", "-q", "-m", "Modul mit Leerzeichen", cwd=zweig)
    code, err = _lauf(hook, "git push origin feature/x", zweig, monkeypatch, capsys)
    assert code == 2
    assert "src/foreman/mein modul.py" in err


def test_ein_dateiname_mit_umlaut_wird_gesehen(
    hook: ModuleType,
    zweig: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # git quotet Nicht-ASCII in --name-only (core.quotepath); -z laesst den Namen ganz.
    _git("switch", "-q", "-c", "feature/umlaut", "main", cwd=zweig)
    _schreibe(zweig / "src" / "foreman" / "größe.py", "X = 1\n")
    _git("add", ".", cwd=zweig)
    _git("commit", "-q", "-m", "Umlaut", cwd=zweig)
    code, err = _lauf(hook, "git push origin feature/umlaut", zweig, monkeypatch, capsys)
    assert code == 2
    assert "größe.py" in err


def test_eine_verschiebung_aus_dem_anwendungscode_heraus_zaehlt(
    hook: ModuleType,
    zweig: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _git("switch", "-q", "-c", "feature/mv", "main", cwd=zweig)
    _git("mv", "src/foreman/kern.py", "kern.py", cwd=zweig)
    _git("commit", "-q", "-m", "Verschoben", cwd=zweig)
    code, err = _lauf(hook, "git push origin feature/mv", zweig, monkeypatch, capsys)
    assert code == 2
    assert "src/foreman/kern.py" in err


@pytest.mark.parametrize(
    "pfad",
    ["frontend/app/__tests__/page.tsx", "src/foreman/conftest.py", "src/foreman/tests/test_k.py"],
)
def test_testdateien_erklaeren_nichts(
    hook: ModuleType,
    zweig: Path,
    pfad: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _git("switch", "-q", "-c", "feature/t", "main", cwd=zweig)
    _schreibe(zweig / pfad, "x\n")
    _git("add", ".", cwd=zweig)
    _git("commit", "-q", "-m", "Test", cwd=zweig)
    code, _ = _lauf(hook, "git push origin feature/t", zweig, monkeypatch, capsys)
    assert code == 0
