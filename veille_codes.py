"""Veille de titres d'annonces officielles Instant Gaming.

Signale de possibles codes en GitHub Issues (jamais dans Discord).
Pas une validation de code : vérification humaine indispensable.
"""
import json
import os
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

BASE = Path(__file__).resolve().parent
STATE = BASE / "veille_codes_state.json"
SOURCES = (
    "https://www.instant-gaming.com/fr/blog/",
    "https://news.instant-gaming.com/fr",
)
PATTERN = re.compile(
    r"\b(?:codes?\s+promos?|codes?\s+de\s+r[ée]duction|coupons?\s+de\s+r[ée]duction|coupon\s+codes?)\b",
    flags=re.IGNORECASE,
)


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "a" and self.current is None:
            data = dict(attrs)
            self.current = [data.get("href", ""), []]

    def handle_data(self, data):
        if self.current is not None:
            self.current[1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            href, segments = self.current
            title = " ".join(" ".join(segments).split())
            if href and title:
                self.links.append((href, title))
            self.current = None


def get_page(url):
    req = urllib.request.Request(url, headers={"User-Agent": "IGOfficialAnnouncementWatcher/1.0 (+GitHub Actions)", "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read(2_000_000).decode("utf-8", errors="replace")


def articles(source, html):
    p = Links()
    p.feed(html)
    found = {}
    for href, title in p.links:
        url, _ = urldefrag(urljoin(source, href))
        parsed = urlparse(url)
        is_news = parsed.hostname == "news.instant-gaming.com" and re.match(r"^/fr/articles/\d+", parsed.path)
        is_blog = parsed.hostname == "www.instant-gaming.com" and re.match(r"^/fr/blog/\d+", parsed.path)
        if parsed.scheme != "https" or not (is_news or is_blog):
            continue
        found.setdefault(url, title[:220])
    return found


def create_review_issue(title, url):
    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    payload = {
        "title": "🎟️ À vérifier : " + title[:95],
        "body": (
            "Une annonce publiée sur un site officiel Instant Gaming contient "
            "une référence possible à un code promo.\n\n"
            f"**Annonce :** {url}\n\n"
            "⚠️ **Ceci n'est pas un code vérifié.** Ne rien publier dans Discord "
            "avant d'avoir confirmé un vrai code, sa réduction, ses conditions et sa date de validité "
            "sur une annonce officielle. Ensuite seulement, complétez codes.json "
            "avec officially_confirmed: true."
        ),
    }
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "IGOfficialAnnouncementWatcher/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        result = json.load(response)
    print("Annonce à vérifier :", result.get("html_url", url))


def main():
    links = {}
    for source in SOURCES:
        found = articles(source, get_page(source))
        if not found:
            raise RuntimeError(f"Aucun article trouvé sur {source} : possible changement du site")
        links.update(found)
    existing = STATE.exists()
    seen = set(json.loads(STATE.read_text(encoding="utf-8"))) if existing else set()
    if not existing:
        # Initialiser avec les articles déjà en ligne, sans envoyer d'anciens signalements.
        STATE.write_text(json.dumps(sorted(links), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Veille initialisée : {len(links)} articles connus, aucun signalement historique.")
        return

    new_articles = [(url, title) for url, title in links.items() if url not in seen]
    for url, title in new_articles:
        if PATTERN.search(title):
            create_review_issue(title, url)
        seen.add(url)
    STATE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(new_articles)} nouvel(le)(s) article(s) analysé(s). Les codes ne sont jamais publiés directement.")


if __name__ == "__main__":
    main()
