"""
Fuentes de temas en tiempo real para alimentar al TrendAgent.

Todo con endpoints públicos/gratuitos, sin APIs de pago:
  - RSS de noticias financieras (Yahoo Finance, CNBC, MarketWatch…)
  - Reddit (subreddits de finanzas) vía su JSON público
  - Google Trends vía pytrends (opcional; scraping no oficial)

Devuelve una lista de "señales" (titulares/preguntas que están calientes hoy),
que el TrendAgent usa como materia prima en vez de inventar temas evergreen.

Diseño defensivo: si una fuente falla o no hay red, se ignora y se sigue con
las demás. El pipeline nunca se cae por una fuente caída.
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error
import re
from html import unescape

from pipeline.common import get_logger

log = get_logger("TopicSources")

UA = "Mozilla/5.0 (compatible; yt-finance-agents/1.0)"
TIMEOUT = 15

# RSS gratuitos de finanzas (sin API key)
RSS_FEEDS = [
    "https://finance.yahoo.com/news/rssindex",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",  # Top News
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://www.investing.com/rss/news_25.rss",              # Personal finance
]

# Subreddits de finanzas (JSON público: /r/<sub>/hot.json)
SUBREDDITS = ["personalfinance", "investing", "financialindependence", "stocks"]


def _http_get(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        log.warning("Fuente inaccesible %s: %s", url, e)
        return None
    except Exception as e:
        log.warning("Error leyendo %s: %s", url, e)
        return None


def _parse_rss_titles(xml: str, limit: int = 8) -> list[str]:
    """Extrae <title> de un RSS sin dependencias externas."""
    titles = re.findall(r"<title>(.*?)</title>", xml, re.DOTALL | re.IGNORECASE)
    cleaned = []
    for t in titles:
        t = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", t, flags=re.DOTALL)
        t = unescape(t).strip()
        if t and t.lower() not in ("rss", "yahoo finance", "cnbc", "marketwatch"):
            cleaned.append(t)
    return cleaned[1:limit + 1]  # el primer <title> suele ser el nombre del feed


def from_rss(limit_per_feed: int = 6) -> list[dict]:
    signals = []
    for url in RSS_FEEDS:
        xml = _http_get(url)
        if not xml:
            continue
        for title in _parse_rss_titles(xml, limit_per_feed):
            signals.append({"source": "rss", "origin": url, "text": title})
    log.info("RSS: %d titulares recolectados", len(signals))
    return signals


def from_reddit(limit_per_sub: int = 8) -> list[dict]:
    signals = []
    for sub in SUBREDDITS:
        raw = _http_get(f"https://www.reddit.com/r/{sub}/hot.json?limit={limit_per_sub}")
        if not raw:
            continue
        try:
            data = json.loads(raw)
            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                title = post.get("title", "").strip()
                score = post.get("score", 0)
                if title and not post.get("stickied"):
                    signals.append({"source": "reddit", "origin": f"r/{sub}",
                                    "text": title, "score": score})
        except json.JSONDecodeError:
            continue
    log.info("Reddit: %d posts recolectados", len(signals))
    return signals


def from_trends(keywords: list[str] | None = None) -> list[dict]:
    """Google Trends vía pytrends (opcional). Si no está instalado, se omite."""
    try:
        from pytrends.request import TrendReq
    except ImportError:
        log.info("pytrends no instalado; omito Google Trends.")
        return []
    try:
        kw = keywords or ["investing", "personal finance", "stock market"]
        pt = TrendReq(hl="en-US", tz=0)
        pt.build_payload(kw[:5], timeframe="now 7-d")
        related = pt.related_queries()
        signals = []
        for base, blocks in related.items():
            rising = blocks.get("rising")
            if rising is not None:
                for q in rising["query"].tolist()[:5]:
                    signals.append({"source": "trends", "origin": base, "text": q})
        log.info("Trends: %d queries en alza", len(signals))
        return signals
    except Exception as e:
        log.warning("Google Trends falló: %s", e)
        return []


def gather(use_trends: bool = True) -> list[dict]:
    """Junta señales de todas las fuentes disponibles. Nunca lanza excepción."""
    signals: list[dict] = []
    signals += from_rss()
    signals += from_reddit()
    if use_trends:
        signals += from_trends()

    # dedup por texto normalizado
    seen, unique = set(), []
    for s in signals:
        key = re.sub(r"[^a-z0-9]+", "", s["text"].lower())[:80]
        if key and key not in seen:
            seen.add(key)
            unique.append(s)

    log.info("Total señales únicas de tendencias: %d", len(unique))
    return unique
