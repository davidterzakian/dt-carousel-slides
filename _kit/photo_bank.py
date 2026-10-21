#!/usr/bin/env python3
"""Build / grow David's Laval photo bank from free, commercial-use-licensed sources.

Runs on GitHub Actions (which has open internet). Sources:
  - Wikimedia Commons: files in "Category:Laval, Quebec" and its subcategories, plus targeted searches.
  - Openverse (openverse.org): CC-licensed images (mostly Flickr) allowing commercial use.
Only licenses that allow commercial use are kept: CC0, Public domain, CC BY, CC BY-SA (no NC, no ND).
Each kept photo is saved as photos/<id>.jpg (max 1600 px) and described in photos/manifest.json
with title, author, license, source page and a credit line to put in the caption.

Usage: python3 _kit/photo_bank.py [--max-new 150] [--query "Extra search"]...
"""
import argparse, hashlib, html, io, json, pathlib, re, sys, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
PHOTOS = ROOT / "photos"
MANIFEST = PHOTOS / "manifest.json"
UA = "DT-Laval-PhotoBank/1.0 (https://github.com/davidterzakian/dt-carousel-slides; davidterzakian@gmail.com)"

SECTORS = ["Auteuil", "Chomedey", "Duvernay", "Fabreville", "Îles-Laval", "Laval-des-Rapides", "Laval-Ouest",
           "Laval-sur-le-Lac", "Pont-Viau", "Saint-François", "Saint-Vincent-de-Paul", "Sainte-Dorothée",
           "Sainte-Rose", "Vimont"]
LANDMARKS = ["Centropolis", "Place Bell", "Cosmodôme", "Centre de la nature", "Carrefour Laval", "Montmorency",
             "Rivière des Mille Îles", "Rivière-des-Mille-Îles", "Rivière des Prairies", "Berge des Baigneurs",
             "Bois de l'Équerre", "Quartier Laval", "Pont Viau", "Papineau-Leblanc", "Médéric-Martin",
             "Cartier", "De la Concorde", "Îles-Laval", "Île Bigras", "Île Jésus", "Armand-Frappier",
             "Collège Montmorency", "Parc de la Rivière-des-Mille-Îles", "Marcel-Dutil"]
SEARCHES = [f"{s} Laval Quebec" for s in SECTORS] + [f"{l} Laval" for l in LANDMARKS] + \
           ["Laval Quebec park", "Laval Quebec river", "Laval Quebec autumn", "Laval Quebec winter", "Laval Quebec street",
            "Laval Quebec houses", "Laval Quebec skyline", "Laval Quebec aerial", "Vieux Sainte-Rose", "Laval Quebec bridge",
            "Laval Québec parc", "Laval Québec rivière", "Laval Quebec", "Laval Québec", "Île Jésus Laval"]
OK_LICENSE = re.compile(r"^(cc0|public domain|pd|cc[- ]by(-sa)?[ -]?\d|cc[- ]by(-sa)?$|cc-by(-sa)?-\d)", re.I)
BAD_LICENSE = re.compile(r"\b(nc|nd|non-?commercial|no ?deriv|fair use)\b", re.I)
SKIP_WORDS = re.compile(r"\b(map|carte|logo|plan|blason|coat of arms|armoiries|diagram|flag|drapeau|chart|graph|"
                        r"signature|seal|sceau|location|localisation|svg|screenshot|document|scan|poster|affiche|"
                        r"france|mayenne|p[ée]nitenci\w*|prison|d[ée]tention|federal|f[ée]d[ée]ral|[ée]cran|screen|accident|fire|incendie|"
                        r"funeral|fun[ée]raire|cemetery|cimeti[èe]re|police|crash|protest|manif\w*)\b", re.I)
QC_HINT = re.compile(r"(qu[ée]bec|\bqc\b|canada|île j[ée]sus|ile jesus|montr[ée]al|mille[- ][iî]les|"
                     + "|".join(re.escape(x) for x in SECTORS + LANDMARKS) + r")", re.I)


def get_json(url, tries=2):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except Exception as e:  # noqa
            if k == tries - 1:
                print("  fetch failed:", url[:120], e, file=sys.stderr)
                return None
            time.sleep(3 * (k + 1))


def get_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


def strip(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def tag_sectors(text):
    t = text.lower().replace("-", " ")
    found = [s for s in SECTORS if s.lower().replace("-", " ") in t]
    marks = [l for l in LANDMARKS if l.lower().replace("-", " ") in t]
    return found, marks


# ---------------- Wikimedia Commons ----------------
API = "https://commons.wikimedia.org/w/api.php"
II = "url|extmetadata|size|mime"


def commons_files_from(params):
    out, cont = [], {}
    while True:
        q = dict({k: v for k, v in params.items() if not k.startswith("_")}, action="query", format="json", prop="imageinfo|categories", iiprop=II, iiurlwidth=1600,
                 cllimit="max", clshow="!hidden", **cont)
        d = get_json(API + "?" + urllib.parse.urlencode(q))
        if not d:
            break
        out += list((d.get("query") or {}).get("pages", {}).values())
        if "continue" in d and len(out) < params.get("_cap", 100):
            cont = {k: v for k, v in d["continue"].items()}
        else:
            break
    return out


def commons_subcats(root, depth=2, cap=60):
    seen, frontier = {root}, [root]
    for _ in range(depth):
        nxt = []
        for c in frontier:
            d = get_json(API + "?" + urllib.parse.urlencode(dict(action="query", format="json", list="categorymembers",
                                                                 cmtitle=c, cmtype="subcat", cmlimit=500)))
            for m in ((d or {}).get("query") or {}).get("categorymembers", []):
                t = m["title"]
                if t not in seen and not SKIP_WORDS.search(t) and len(seen) < cap:
                    seen.add(t); nxt.append(t)
        frontier = nxt
    return list(seen)


def commons_candidates():
    pages = []
    for s in SEARCHES:
        pages += commons_files_from(dict(generator="search", gsrsearch=s, gsrnamespace=6, gsrlimit=25, _cap=25))
    print(f"commons: {len(pages)} pages from searches", flush=True)
    cats = commons_subcats("Category:Laval, Quebec")
    print(f"commons: {len(cats)} categories", flush=True)
    for i, cat in enumerate(cats):
        pages += commons_files_from(dict(generator="categorymembers", gcmtitle=cat, gcmtype="file", gcmlimit=50, _cap=50))
        if i % 10 == 0: print(f"  cat {i}/{len(cats)} pages so far {len(pages)}", flush=True)
    print(f"commons: {len(pages)} raw pages", flush=True)
    res = {}
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        if not ii or ii.get("mime") not in ("image/jpeg", "image/png"):
            continue
        m = ii.get("extmetadata", {})
        lic = strip(m.get("LicenseShortName", {}).get("value"))
        cats = " ".join(c["title"] for c in p.get("categories", []))
        title = p.get("title", "")
        desc = strip(m.get("ImageDescription", {}).get("value"))[:300]
        text = f"{title} {desc} {cats}"
        if not lic or BAD_LICENSE.search(lic) or not OK_LICENSE.search(lic):
            continue
        if SKIP_WORDS.search(title) or not QC_HINT.search(text):
            continue
        if ii.get("width", 0) < 1200 or ii.get("height", 0) < 700:
            continue
        res["c-" + str(p["pageid"])] = dict(
            source="Wikimedia Commons", title=re.sub(r"^File:|\.\w+$", "", title), description=desc,
            author=strip(m.get("Artist", {}).get("value"))[:120] or "Unknown", license=lic,
            license_url=strip(m.get("LicenseUrl", {}).get("value")),
            source_page=ii.get("descriptionurl", ""), download=ii.get("thumburl") or ii.get("url"),
            width=ii.get("width"), height=ii.get("height"), context=text)
    return res


# ---------------- Openverse ----------------
def openverse_candidates():
    res = {}
    for s in ["Laval Quebec", "Laval Québec"] + [f"{x} Laval" for x in SECTORS + LANDMARKS[:12]]:
        q = urllib.parse.urlencode(dict(q=s, license_type="commercial", page_size=50, mature="false"))
        d = get_json("https://api.openverse.org/v1/images/?" + q)
        for r in (d or {}).get("results", []):
            lic = (r.get("license") or "").lower()
            if lic not in ("cc0", "pdm", "by", "by-sa"):
                continue
            tags = " ".join(t.get("name", "") for t in (r.get("tags") or []))
            text = f"{r.get('title','')} {tags}"
            if SKIP_WORDS.search(r.get("title") or "") or not QC_HINT.search(text):
                continue
            if (r.get("width") or 0) and r["width"] < 1200:
                continue
            name = {"cc0": "CC0", "pdm": "Public domain"}.get(lic, f"CC {lic.upper()} {r.get('license_version','')}".strip())
            res["o-" + r["id"][:12]] = dict(
                source=f"Openverse ({r.get('source','')})", title=strip(r.get("title"))[:120], description="",
                author=strip(r.get("creator"))[:120] or "Unknown", license=name, license_url=r.get("license_url", ""),
                source_page=r.get("foreign_landing_url", ""), download=r.get("url"),
                width=r.get("width"), height=r.get("height"), context=text)
        time.sleep(1)
    print(f"openverse: {len(res)} candidates", flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-new", type=int, default=150)
    ap.add_argument("--query", action="append", default=[])
    a = ap.parse_args()
    SEARCHES.extend(a.query)
    PHOTOS.mkdir(exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"photos": []}
    have = {p["id"] for p in manifest["photos"]}
    have_src = {p["source_page"] for p in manifest["photos"]} | set(manifest.get("blocked", []))
    from PIL import Image
    cands = {**commons_candidates(), **openverse_candidates()}
    print(f"{len(cands)} candidates, {len(have)} already in bank", flush=True)
    # diversity: group near-duplicates (same series/stem), max 3 per group, max 12 per sector/landmark,
    # then round-robin across groups so one big series can't take over the bank
    def stem(t):
        return re.sub(r"[\d_()\-–.,]+|panoramio|img|dsc|jpe?g", " ", t.lower()).split()[:4].__str__()
    per_tag = {}
    for p0 in manifest["photos"]:
        for t0 in p0["sectors"] + p0["landmarks"]:
            per_tag[t0] = per_tag.get(t0, 0) + 1
    groups = {}
    for pid, c in cands.items():
        groups.setdefault(stem(c["title"]), []).append((pid, c))
    order, rnd = [], 0
    while any(len(g) > rnd for g in groups.values()) and rnd < 3:
        for g in groups.values():
            if len(g) > rnd:
                order.append(g[rnd])
        rnd += 1
    added = 0
    for pid, c in order:
        tags = sum(tag_sectors(c["context"]), [])
        if tags and all(per_tag.get(t, 0) >= 12 for t in tags):
            continue
        if added >= a.max_new:
            break
        if pid in have or c["source_page"] in have_src:
            continue
        try:
            raw = get_bytes(c["download"])
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            im.thumbnail((1600, 1600))
            if im.width < 1000:
                continue
            buf = io.BytesIO(); im.save(buf, "JPEG", quality=82, optimize=True)
            digest = hashlib.sha1(buf.getvalue()).hexdigest()[:10]
            fname = f"{pid}-{digest}.jpg"
            (PHOTOS / fname).write_bytes(buf.getvalue())
        except Exception as e:  # noqa
            print("  skip", pid, e, file=sys.stderr); continue
        sectors, marks = tag_sectors(c["context"])
        for t0 in sectors + marks:
            per_tag[t0] = per_tag.get(t0, 0) + 1
        credit = f"Photo: {c['author']}, {c['license']}, via {c['source'].split(' (')[0]}"
        manifest["photos"].append(dict(id=pid, file=f"photos/{fname}", title=c["title"], description=c["description"],
                                       sectors=sectors, landmarks=marks, orientation="landscape" if im.width >= im.height else "portrait",
                                       width=im.width, height=im.height, author=c["author"], license=c["license"],
                                       license_url=c["license_url"], source=c["source"], source_page=c["source_page"],
                                       credit=credit, attribution_required=c["license"] not in ("CC0", "Public domain"),
                                       reviewed=False, use=True, used_on=[]))
        added += 1
        time.sleep(0.5)
    manifest["updated"] = time.strftime("%Y-%m-%d")
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f"added {added}; bank now {len(manifest['photos'])} photos")


if __name__ == "__main__":
    main()
