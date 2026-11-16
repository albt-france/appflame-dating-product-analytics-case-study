"""Shared paths, colours, polite HTTP helper and small formatters."""
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
PUB = DATA / "public"
SIM = DATA / "simulated"
OUT = DATA / "output"
DOCS = ROOT / "docs"
SQL = ROOT / "sql"
TODAY = date.today().isoformat()

# light grey-beige theme shared with the earlier case studies
INK, INK2, MUTED = "#0B0B0B", "#52514E", "#898781"
BG, CARD, BORDER = "#F4F4F2", "#FCFCFB", "#E1E0D9"
BLUE, BLUE_LIGHT, BLUE_DARK = "#2A78D6", "#86B6EF", "#104281"
GREY, GREY_LIGHT = "#A8A69E", "#D6D4CC"
RED, RED_LIGHT = "#D03B3B", "#F4C7C6"
ORANGE, AQUA, YELLOW = "#EB6834", "#1BAF7A", "#EDA100"

DISCLAIMER = "Independent case study based on public data · not affiliated with or endorsed by appflame"

HEADERS = {"User-Agent": "Mozilla/5.0 (independent case-study research; low-frequency)"}
MIN_DELAY_S = 2.0
_last_call = [0.0]


def utf8():
    sys.stdout.reconfigure(encoding="utf-8")


def polite_get(url, timeout=60, retries=2, **kw):
    """GET a public URL: one request at a time, >= 2 s apart, neutral User-Agent, back off on 429/503."""
    import requests
    for attempt in range(retries + 1):
        wait = MIN_DELAY_S - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout, **kw)
            if r.status_code in (429, 503) and attempt < retries:
                time.sleep(20 * (attempt + 1))
                continue
            r.encoding = r.encoding or "utf-8"
            return r
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(30 * (attempt + 1))


def save_json(obj, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def ai_note() -> str:
    """The workflow sentence lives in one place, the README's Methods section; the PDF quotes it from there."""
    text = (ROOT / "README.md").read_text(encoding="utf-8").split("AI-assisted workflow:", 1)[1]
    return "AI-assisted workflow:" + text.split("\n")[0].rstrip()


def sim_con():
    """In-memory DuckDB with one view per simulated table (data/simulated/*.parquet)."""
    import duckdb
    con = duckdb.connect()
    for p in sorted(SIM.glob("*.parquet")):
        con.sql(f"create or replace view {p.stem} as select * from read_parquet('{p.as_posix()}')")
    return con


def fmt_int(x) -> str:
    return f"{x:,.0f}"


def fmt_pct(x, digits=0) -> str:
    return f"{100 * x:.{digits}f}%"


def fmt_usd(x, digits=2) -> str:
    if abs(x) >= 1e9:
        return f"${x / 1e9:.1f}bn"
    if abs(x) >= 1e6:
        return f"${x / 1e6:.1f}M"
    if abs(x) >= 1e4:
        return f"${x / 1e3:.0f}K"
    return f"${x:,.{digits}f}"
