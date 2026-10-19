#!/usr/bin/env python3
"""Collect this week's Lidl Poland food promotions into promos.json for CoZjem.

Runs daily (GitHub Actions). Uses Lidl's public product search data for the
"Żywność i napoje" category. Biedronka, Aldi and Auchan publish their offers
as leaflet images or app-only content, so they are not collected here.
"""
import json, re, sys, time, urllib.request, datetime, pathlib

UA = "Mozilla/5.0"
UAS = ["Mozilla/5.0", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36", "Mozilla/5.0 (compatible; CoZjemPromos/1.0; +https://cozjem.com)"]
API = "https://www.lidl.pl/q/api/search?assortment=PL&locale=pl_PL&version=v2.0.0&fetchsize=200&offset={off}&category.id=10068374"
OUT = pathlib.Path(__file__).resolve().parent.parent / "promos.json"

# CoZjem ingredient key -> Polish words that identify it in a Lidl product title
MATCH = {
 "jajka": [r"\bjaja\b", r"\bjajka\b"], "maslo": [r"\bmasło\b(?! orzech)"], "mleko": [r"\bmleko\b(?! (kokos|zagęsz|w proszku))"],
 "twarog": [r"\btwaróg\b", r"\btwarożek\b"], "smietana": [r"\bśmietana\b"], "smietanka": [r"\bśmietanka\b"],
 "ser": [r"\bgouda\b", r"\bedamski\b", r"\bser żółty\b", r"\bmaasdam\b", r"\bser .*plastr"], "feta": [r"\bfeta\b", r"ser sałatkowy"],
 "mozzarella": [r"\bmozzarella\b"], "grana": [r"grana padano", r"parmezan", r"parmigiano"], "ricotta": [r"\bricotta\b"],
 "skyr": [r"\bskyr\b"], "jogurt": [r"jogurt naturalny"], "kefir": [r"\bkefir\b"],
 "kurczak": [r"filet z (piersi )?kurczaka", r"pierś z kurczaka", r"filet z piersi"], "udka": [r"\budka\b", r"\bpodudzia\b", r"udziec z kurczaka", r"ćwiartka"],
 "indyk": [r"\bindyk", r"z indyka"], "mielone": [r"mięso mielone", r"\bmielone\b"], "schab": [r"\bschab\b"], "boczek": [r"\bboczek\b"],
 "kielbasa": [r"\bkiełbas"], "szynka": [r"\bszynka\b"], "parowki": [r"\bparówki\b"], "wolowina": [r"\bwołow"], "watrobka": [r"wątróbk"],
 "chorizo": [r"\bchorizo\b"], "ryba": [r"\bmintaj"], "dorsz": [r"\bdorsz"], "losos": [r"\błoso"], "makrela": [r"\bmakrel"], "tunczyk": [r"\btuńczyk"],
 "krewetki": [r"\bkrewetk"],
 "ziemniaki": [r"\bziemniaki\b"], "cebula": [r"\bcebula\b"], "czosnek": [r"\bczosnek\b"], "marchew": [r"\bmarchew\b", r"\bmarchewka\b"],
 "pomidory": [r"\bpomidor"], "ogorek": [r"\bogórek\b(?! kisz)", r"\bogórki\b(?! kisz)"], "kiszone": [r"ogórki kiszone"], "papryka": [r"\bpapryka\b(?! (słodka|mielona|wędzona))"],
 "cukinia": [r"\bcukinia\b"], "pieczarki": [r"\bpieczark"], "kapusta": [r"\bkapusta biała\b", r"\bkapusta\b(?! kiszona)"], "kwaszona": [r"kapusta kiszona"],
 "brokul": [r"\bbrokuł"], "kalafior": [r"\bkalafior"], "buraki": [r"\bburak"], "por": [r"\bpor\b"], "dynia": [r"\bdynia\b(?!.*ozdob)"], "salata": [r"\bsałata\b"],
 "awokado": [r"\bawokado\b"], "bataty": [r"\bbatat"], "szpinak": [r"\bszpinak"], "jablka": [r"\bjabłk"], "banan": [r"\bbanan"], "cytryna": [r"\bcytryn"],
 "jagody": [r"owoce leśne", r"\bjagody\b"],
 "ryz": [r"\bryż\b"], "makaron": [r"\bmakaron\b", r"\bspaghetti\b", r"\bpenne\b"], "maka": [r"mąka pszenna"], "chleb": [r"\bchleb\b"],
 "platki": [r"płatki owsiane"], "kasza": [r"kasza jęczmienna"], "kaszag": [r"kasza gryczana"], "kuskus": [r"\bkuskus\b"], "tortille": [r"\btortill"],
 "gnocchi": [r"\bgnocchi\b"], "passata": [r"\bpassata\b", r"przecier pomidorowy"], "koncentrat": [r"koncentrat pomidorowy"],
 "kukurydza": [r"kukurydza konserwowa", r"\bkukurydza\b"], "kokos": [r"mleczko kokosowe", r"mleko kokosowe"], "fasola": [r"fasola biała", r"\bfasola\b"],
 "ciecierzyca": [r"\bciecierzyc"], "soczewica": [r"\bsoczewic"], "oliwki": [r"\boliwki\b"], "pesto": [r"\bpesto\b"], "miod": [r"\bmiód\b"],
 "cukier": [r"\bcukier\b"], "maslo_orz": [r"masło orzechowe"],
}
RX = {k: [re.compile(p, re.I) for p in v] for k, v in MATCH.items()}

def get(url):
    import subprocess, shutil
    for a in range(4):
        if shutil.which("curl"):
            ua = UAS[a % len(UAS)]
            r = subprocess.run(["curl", "-s", "-m", "30", "-A", ua, "-H", "Accept: application/json", "-w", "\n%{http_code}", url], capture_output=True)
            body, _, code = r.stdout.rpartition(b"\n")
            if code == b"200" and body: return json.loads(body)
            print("curl", code.decode(errors="ignore"), url[-40:], file=sys.stderr); time.sleep(4 * (a + 1)); continue
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=30) as r:
                return json.load(r)
        except Exception as e:
            print("retry", a, e, file=sys.stderr); time.sleep(5 * (a + 1))
    raise RuntimeError("Lidl data unavailable")

def match(title):
    t = title.lower()
    for k, rxs in RX.items():
        if any(r.search(t) for r in rxs): return k
    return None

def fetch_text(url, headers=None):
    import subprocess
    cmd = ["curl", "-s", "-L", "-m", "30", "-A", UA] + sum([["-H", f"{k}: {v}"] for k, v in (headers or {}).items()], []) + [url]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not r.stdout: raise RuntimeError("fetch failed " + url)
    return r.stdout.decode("utf-8", "ignore")

SKIP_B = re.compile(r"home|alko|pressadult|znicz|good-to-go|ebook|przemysl|dom-i|ogrod", re.I)
def biedronka_leaflets():
    import html as H
    s = fetch_text("https://www.biedronka.pl/pl/gazetki")
    out, seen, today = [], set(), datetime.date.today()
    for m in re.finditer(r'<a[^>]+href="(https://www\.biedronka\.pl/pl/press,id,[^"#]+)[^"]*"[^>]*>(.*?)</a>', s, re.S):
        url, inner = m.group(1), m.group(2)
        if url in seen or SKIP_B.search(url): continue
        seen.add(url)
        slug = url.split("title,")[-1]
        dm = re.search(r"(\d{1,2})-(\d{1,2})$", slug)
        if not dm: continue
        d, mo = int(dm.group(1)), int(dm.group(2)); yr = today.year - (1 if mo > today.month + 6 else 0)
        try: start = datetime.date(yr, mo, d)
        except ValueError: continue
        end = start + datetime.timedelta(days=6)
        if end < today: continue
        title = re.sub(r"-(od-)?\d{1,2}-\d{1,2}$", "", slug).replace("-p-", " ").replace("-", " ").strip().capitalize()
        img = re.search(r'(?:data-src|src)="(https://[^"]+\.(?:jpg|jpeg|png|webp))"', inner)
        out.append({"t": title, "from": int(datetime.datetime(start.year, start.month, start.day).timestamp() * 1000),
                    "until": int(datetime.datetime(end.year, end.month, end.day, 23, 59).timestamp() * 1000),
                    "url": url, "img": ""})  # Biedronka blocks its covers on other sites
    return out

AUCHAN_KEY = "8039b23d-30f2-456f-a9b9-4100344de25d"  # public key shipped in auchan.pl's own web app config
def auchan_leaflets():
    d = json.loads(fetch_text("https://api.ari.auchan.com/ari/digit/portal-cms/pl/template/tracts?lang=pl&national=true&groups=all&local=none", {"X-Gravitee-Api-Key": AUCHAN_KEY}))
    out, now = [], datetime.datetime.now(datetime.timezone.utc)
    for x in d if isinstance(d, list) else []:
        t = (x.get("title") or "").strip()
        if not t or re.search(r"wino|alkohol", t, re.I): continue
        try:
            st_ = datetime.datetime.fromisoformat(x["startDate"]); en = datetime.datetime.fromisoformat(x["endDate"]) + datetime.timedelta(hours=23, minutes=59)
        except Exception: continue
        if en < now: continue
        slug = ((x.get("urlFriendlyName") or {}).get("pl")) or x.get("slug")
        cov = (x.get("cover") or {}); img = ((cov.get("tablet") or cov.get("desktop") or {}).get("url")) or ""
        out.append({"t": t, "from": int(st_.timestamp() * 1000), "until": int(en.timestamp() * 1000), "url": "https://www.auchan.pl/pl/gazetka/" + slug, "img": img})
    return out

def lidl_items():
    items, off, total = [], 0, None
    while True:
        d = get(API.format(off=off)); total = d.get("numFound", 0)
        for it in d.get("items", []):
            g = (it.get("gridbox") or {}).get("data") or {}
            badges = ((g.get("stockAvailability") or {}).get("badgeInfoV2") or [{}])[0]
            frm, until = badges.get("validFrom"), badges.get("validUntil")
            if not until: continue
            title = re.sub(r"\s+", " ", g.get("fullTitle") or g.get("title") or "").strip().lstrip("- ").strip()
            if not title: continue
            p = g.get("price") or {}; lp = False; hl = ""
            if not isinstance(p.get("price"), (int, float)):
                lps = g.get("lidlPlus") or []
                if lps and isinstance((lps[0].get("price") or {}).get("price"), (int, float)):
                    p = lps[0]["price"]; lp = True; hl = (lps[0].get("highlightText") or "")[:40]
            price = p.get("price") if isinstance(p.get("price"), (int, float)) else None
            disc = p.get("discount") or {}
            base = ((p.get("basePrice") or {}).get("text") or "")
            old = p.get("oldPrice") or disc.get("deletedPrice")
            if not isinstance(old, (int, float)):
                m = re.search(r"(?:przed obniżką|poza promocją)[^0-9]*?(\d+,\d{2})", base, re.I)
                old = float(m.group(1).replace(",", ".")) if m else None
            pct = disc.get("percentageDiscount") if disc.get("showDiscount") else None
            if not pct and price and isinstance(old, (int, float)) and old > price: pct = round((1 - price / old) * 100)
            items.append({
                "t": title, "p": round(price, 2) if price else None,
                "op": round(old, 2) if price and isinstance(old, (int, float)) and old > price else None,
                "pct": int(pct) if pct else None, "hl": hl, "lp": lp,
                "unit": ((p.get("packaging") or {}).get("text") or "").strip()[:30],
                "from": int(frm) * 1000 if frm else None, "until": int(until) * 1000,
                "url": "https://www.lidl.pl" + (g.get("canonicalPath") or ""), "img": g.get("image") or "",
                "k": match(title),
            })
        off += 200
        if off >= total or off > 600: break
        time.sleep(1)
    items.sort(key=lambda x: (x["k"] is None, -(x["pct"] or 0)))
    return items

def previous(store):
    try:
        old = json.loads(OUT.read_text()); now = time.time() * 1000
        o = old.get("stores", {}).get(store, {})
        return [x for x in o.get("items", []) if x.get("until", 0) >= now], [x for x in o.get("leaflets", []) if x.get("until", 0) >= now]
    except Exception: return [], []

def main():
    try: items = lidl_items()
    except BaseException as e:
        print("Lidl failed, keeping previous offers:", e, file=sys.stderr); items = previous("Lidl")[0]
    stores = {"Lidl": {"source": "https://www.lidl.pl/c/zywnosc-i-napoje/s10068374", "items": items, "leaflets": []}}
    for name, fn in (("Biedronka", biedronka_leaflets), ("Auchan", auchan_leaflets)):
        try: stores[name] = {"items": [], "leaflets": fn()}
        except Exception as e:
            print(name, "leaflets failed, keeping previous:", e, file=sys.stderr); stores[name] = {"items": [], "leaflets": previous(name)[1]}
    stores["Aldi"] = {"items": [], "leaflets": [], "source": "https://www.aldi.pl/oferty.html"}
    out = {"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes"), "stores": stores}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"Lidl: {len(items)} food offers, {sum(1 for i in items if i['k'])} matched to CoZjem ingredients; leaflets: " + ", ".join(f"{k} {len(v['leaflets'])}" for k, v in stores.items()))

if __name__ == "__main__":
    main()
