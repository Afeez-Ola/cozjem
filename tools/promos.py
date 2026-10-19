#!/usr/bin/env python3
"""Collect this week's Lidl Poland food promotions into promos.json for CoZjem.

Runs daily (GitHub Actions). Uses Lidl's public product search data for the
"Żywność i napoje" category. Biedronka, Aldi and Auchan publish their offers
as leaflet images or app-only content, so they are not collected here.
"""
import json, re, sys, time, urllib.request, datetime, pathlib

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
API = "https://www.lidl.pl/q/api/search?assortment=PL&locale=pl_PL&version=v2.0.0&fetchsize=48&offset={off}&category.id=10068374"
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
    for a in range(3):
        if shutil.which("curl"):
            r = subprocess.run(["curl", "-s", "-m", "30", "-A", UA, "-H", "Accept: application/json", "-w", "\n%{http_code}", url], capture_output=True)
            body, _, code = r.stdout.rpartition(b"\n")
            if code == b"200" and body: return json.loads(body)
            print("curl", code.decode(errors="ignore"), url[-40:], file=sys.stderr); time.sleep(5 * (a + 1)); continue
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=30) as r:
                return json.load(r)
        except Exception as e:
            print("retry", a, e, file=sys.stderr); time.sleep(5 * (a + 1))
    raise SystemExit("Lidl data unavailable")

def match(title):
    t = title.lower()
    for k, rxs in RX.items():
        if any(r.search(t) for r in rxs): return k
    return None

def main():
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
        off += 48
        if off >= total or off > 600: break
        time.sleep(1)
    items.sort(key=lambda x: (x["k"] is None, -(x["pct"] or 0)))
    out = {"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes"),
           "stores": {"Lidl": {"source": "https://www.lidl.pl/c/zywnosc-i-napoje/s10068374", "items": items}}}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"Lidl: {len(items)} food offers, {sum(1 for i in items if i['k'])} matched to CoZjem ingredients")

if __name__ == "__main__":
    main()
