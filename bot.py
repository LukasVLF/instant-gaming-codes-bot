import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'codes.json'
STATE = ROOT / 'sent_codes.json'
OFFICIAL_HOSTS = {'instant-gaming.com', 'www.instant-gaming.com'}

def official_url(value):
    from urllib.parse import urlparse
    try:
        parsed = urlparse(value)
        return parsed.scheme == 'https' and (parsed.hostname or '').lower() in OFFICIAL_HOSTS
    except Exception:
        return False

def main():
    webhook = os.environ.get('DISCORD_WEBHOOK_URL', '')
    if not webhook.startswith('https://discord.com/api/webhooks/') and not webhook.startswith('https://discordapp.com/api/webhooks/'):
        raise ValueError('Secret DISCORD_WEBHOOK_URL absent ou incorrect')
    codes = json.loads(DATA.read_text(encoding='utf-8'))
    sent = set(json.loads(STATE.read_text(encoding='utf-8'))) if STATE.exists() else set()
    now = datetime.now(timezone.utc)
    count = 0
    for item in codes:
        code = str(item.get('code', '')).strip()
        url = str(item.get('official_source_url', '')).strip()
        confirmed = item.get('officially_confirmed') is True
        expires = item.get('expires_at_utc', '')
        if not code or not official_url(url) or not confirmed or not expires:
            continue
        try:
            expires_at = datetime.fromisoformat(expires.replace('Z', '+00:00'))
            if expires_at.tzinfo is None or expires_at <= now:
                continue
        except ValueError:
            continue
        key = code.casefold() + '|' + url
        if key in sent:
            continue
        offer = str(item.get('offer', 'Conditions à consulter sur la source officielle'))[:180]
        content = (f'🎟️ **CODE PROMO INSTANT GAMING**\n'
                   f'**Code :** `{code[:100]}`\n'
                   f'**Offre :** {offer}\n'
                   f'**Expiration annoncée :** <t:{int(expires_at.timestamp())}:F>\n'
                   f'**Source officielle :** {url}\n'
                   f'⚠️ Vérifiez les conditions et la validité au moment de votre achat.')
        payload = json.dumps({'content': content, 'allowed_mentions': {'parse': []}}).encode('utf-8')
        req = urllib.request.Request(webhook, data=payload, headers={'Content-Type':'application/json', 'User-Agent':'IGPromoDiscordBot/1.0'}, method='POST')
        with urllib.request.urlopen(req, timeout=20) as response:
            if response.status not in (200, 204):
                raise RuntimeError(f'Webhook Discord : statut {response.status}')
        sent.add(key)
        STATE.write_text(json.dumps(sorted(sent), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        count += 1
    print(f'Publication terminée : {count} nouveau(x) code(s) confirmé(s).')
    if not codes:
        print('Aucun code renseigné : aucune publication. Comportement normal et sécurisé.')

if __name__ == '__main__':
    main()
