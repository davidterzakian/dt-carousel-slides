#!/usr/bin/env python3
"""David Terzakian carousel renderer.

Usage: python3 render.py spec.json OUTDIR [--assets ASSETS_DIR]

Renders each slide in spec.json to OUTDIR/slide-01.png ... at 1080x1350 (4:5, Instagram feed max).
ASSETS_DIR must contain dt_logo.png, headshot.jpg and fonts/*.woff2 (default: ./assets next to this file).

Spec format (JSON):
{
  "slides": [
    {"type": "cover", "theme": "blue", "kicker": "LAVAL BUYER GUIDE", "badge": "7 checks",
     "icons": ["dollar","clock"], "title": "Before you fall for a Laval home...", "sub": "...", "numeral": "7"},
    {"type": "point", "theme": "blue"|"white", "kicker": "CHECK 1 OF 7", "step": 1, "steps": 7,
     "title": "...", "numeral": "01",
     "cards":   [{"icon": "clock", "title": "How long?", "sub": "Months on the market"}],   # 2-3 cards
     "chips":   [{"icon": "home", "label": "Roof"}],                                         # 3-5 small tiles
     "bars":    {"icon": "trend-up", "label": "LAVAL PRICES",
                 "rows": [{"label": "Single-family · Q1 2026", "value": "$580K", "pct": 0.95}]},
     "list":    ["Auteuil", "Chomedey", ...],                                                 # two-column gold-dot list
     "banner":  {"icon": "search", "text": "Inspection condition"},
     "timeline": ["Year 1","Year 2","Year 3"],
     "photo":   {"file": "photos/c-123-ab12.jpg", "credit": "Photo: Name, CC BY-SA 4.0, via Wikimedia Commons",
                 "position": "center 40%"},                                                   # rounded photo panel
     "body": "Text with **bold** allowed.", "source": "Per courticonnect.ca, Q1 2026"},
    {"type": "cta", "kicker": "YOUR NEXT STEP", "title": "Eyeing a Laval listing? Send it to me.",
     "lines": [{"icon": "message", "text": "DM it here, or email"},
               {"icon": "mail", "text": "davidterzakian@gmail.com", "bold": true}],
     "tagline": "I'll give it to you straight.", "save": "Save this for your next showing"}
  ]
}
Every block is optional except type/title. Use only one or two blocks per point slide.
Photos: the cover takes "photo": {...} too (full-bleed background under a blue overlay). "file" is relative to the
repo root (photos/ bank). "position" is an optional CSS object-position to frame the subject. Always pass "credit".
"""
import base64, html, json, re, sys, pathlib

W, H = 1080, 1350
FOOTER = "David Terzakian · eXp Realty · Laval"
BLUE = "#1E90FF"
GOLD_CSS = "linear-gradient(135deg,#8A5A00 0%,#D4AF37 25%,#FFF4C2 50%,#D4AF37 75%,#8A5A00 100%)"

# Simple 24x24 stroke icons (lucide-style)
ICONS = {
    "dollar": '<line x1="12" y1="2" x2="12" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "pin": '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "drop": '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>',
    "home": '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
    "file": '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
    "trend-down": '<polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/>',
    "trend-up": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "message": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><line x1="8" y1="9" x2="16" y2="9"/><line x1="8" y1="13" x2="13" y2="13"/>',
    "mail": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 7L2 7"/>',
    "car": '<path d="M19 17h2v-4l-2-5H5L3 13v4h2"/><circle cx="7.5" cy="17" r="2"/><circle cx="16.5" cy="17" r="2"/><line x1="9.5" y1="17" x2="14.5" y2="17"/>',
    "tree": '<path d="m17 14 3 3H4l3-3"/><path d="m16 9 3 3H5l3-3"/><path d="M12 2 8 7h8z"/><line x1="12" y1="17" x2="12" y2="22"/>',
    "train": '<rect x="4" y="3" width="16" height="13" rx="2"/><line x1="4" y1="11" x2="20" y2="11"/><line x1="12" y1="3" x2="12" y2="11"/><path d="m8 19-2 3"/><path d="m18 22-2-3"/><circle cx="8" cy="14" r=".5"/><circle cx="16" cy="14" r=".5"/>',
    "expand": '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>',
    "wallet": '<rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/><line x1="16" y1="15" x2="18" y2="15"/>',
    "alert": '<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "search": '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    "zap": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    "flame": '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.4-.5-2-1-3-1.1-2.1-.2-4 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.2.4-2.3 1-3.2.3 1.6 1.5 2.7 2.5 2.7z"/>',
    "key": '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/>',
    "school": '<path d="M22 10 12 5 2 10l10 5 10-5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/>',
    "bag": '<path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/>',
    "waves": '<path d="M2 6c.6.5 1.2 1 2.5 1C7 7 7 5 9.5 5c2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M2 12c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M2 18c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4"/>',
    "percent": '<line x1="19" y1="5" x2="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
    "chart": '<line x1="3" y1="21" x2="21" y2="21"/><rect x="5" y="12" width="3" height="7"/><rect x="10.5" y="7" width="3" height="12"/><rect x="16" y="3" width="3" height="16"/>',
    "building": '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01M16 6h.01M12 6h.01M12 10h.01M12 14h.01M16 10h.01M16 14h.01M8 10h.01M8 14h.01"/>',
    "bookmark": '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "ruler": '<path d="M21.3 15.3a2.4 2.4 0 0 1 0 3.4l-2.6 2.6a2.4 2.4 0 0 1-3.4 0L2.7 8.7a2.4 2.4 0 0 1 0-3.4l2.6-2.6a2.4 2.4 0 0 1 3.4 0Z"/><path d="m14.5 12.5 2-2M11.5 9.5l2-2M8.5 6.5l2-2M17.5 15.5l2-2"/>',
    "leaf": '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.5 19 2c1 2 2 4.2 2 8 0 5.5-4.8 10-10 10Z"/><path d="M2 21c0-3 1.9-5.4 5.1-6"/>',
    "hammer": '<path d="m15 12-8.5 8.5a2.1 2.1 0 0 1-3-3L12 9"/><path d="M17.6 15 22 10.6"/><path d="m20.9 11.7-1.3-1.3c-.6-.6-.9-1.3-.9-2.1v-.9l-2.3-2.2A5.5 5.5 0 0 0 12.6 4H9l.9.8A6.2 6.2 0 0 1 12 9.4V11l2 2h.9c.8 0 1.6.3 2.1.9l1.3 1.3"/>',
    "landmark": '<line x1="3" y1="22" x2="21" y2="22"/><line x1="6" y1="18" x2="6" y2="11"/><line x1="10" y1="18" x2="10" y2="11"/><line x1="14" y1="18" x2="14" y2="11"/><line x1="18" y1="18" x2="18" y2="11"/><polygon points="12 2 20 7 4 7"/>',
    "handshake": '<path d="m11 17 2 2a1 1 0 1 0 3-3"/><path d="m14 14 2.5 2.5a1 1 0 1 0 3-3l-3.9-3.9a3 3 0 0 0-4.2 0l-.9.9a1 1 0 1 1-3-3l2.8-2.8a5.8 5.8 0 0 1 7.1-.9l.5.3a2 2 0 0 0 1.4.2L21 4"/><path d="m21 3 1 11h-2"/><path d="M3 3 2 14l6.5 6.5a1 1 0 1 0 3-3"/><path d="M3 4h8"/>',
    "boat": '<path d="M2 21c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1s1.2 1 2.5 1c2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M19.4 18 21 12H3l1.6 6"/><path d="M12 12V3l6 6"/>',
    "star": '<polygon points="12 2 15.1 8.3 22 9.3 17 14.1 18.2 21 12 17.8 5.8 21 7 14.1 2 9.3 8.9 8.3 12 2"/>',
    "coffee": '<path d="M17 8h1a4 4 0 1 1 0 8h-1"/><path d="M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4Z"/><line x1="6" y1="2" x2="6" y2="4"/><line x1="10" y1="2" x2="10" y2="4"/><line x1="14" y1="2" x2="14" y2="4"/>',
    "arrows": '<path d="m16 3 4 4-4 4"/><path d="M20 7H4"/><path d="m8 21-4-4 4-4"/><path d="M4 17h16"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
}

def icon(name, size=46, sw=1.8):
    body = ICONS.get(name, ICONS["check"])
    return (f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="url(#gold)" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')

def md(text):
    t = html.escape(text or "")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)

def b64(path, mime):
    return f"data:{mime};base64," + base64.b64encode(pathlib.Path(path).read_bytes()).decode()

def css(assets):
    f = assets / "fonts"
    def face(fam, file, weight, style="normal"):
        return (f"@font-face{{font-family:'{fam}';src:url('{b64(f/file,'font/woff2')}') format('woff2');"
                f"font-weight:{weight};font-style:{style};}}")
    faces = "".join([
        face("Playfair Display", "playfair-display-latin-700-normal.woff2", 700),
        face("Playfair Display", "playfair-display-latin-ext-700-normal.woff2", 700),
        face("Playfair Display", "playfair-display-latin-700-italic.woff2", 700, "italic"),
        face("Playfair Display", "playfair-display-latin-400-italic.woff2", 400, "italic"),
        face("Work Sans", "work-sans-latin-400-normal.woff2", 400),
        face("Work Sans", "work-sans-latin-ext-400-normal.woff2", 400),
        face("Work Sans", "work-sans-latin-500-normal.woff2", 500),
        face("Work Sans", "work-sans-latin-600-normal.woff2", 600),
        face("Work Sans", "work-sans-latin-ext-600-normal.woff2", 600),
        face("Work Sans", "work-sans-latin-700-normal.woff2", 700),
    ])
    return faces + f"""
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;overflow:hidden}}
body{{font-family:'Work Sans',sans-serif;-webkit-font-smoothing:antialiased}}
.s{{position:relative;width:{W}px;height:{H}px;padding:96px 96px 0;display:flex;flex-direction:column}}
.blue{{background:{BLUE};color:#fff}} .white{{background:#fff;color:#000}}
.top{{display:flex;align-items:center;gap:28px;height:56px}}
.kicker{{font-weight:700;font-size:25px;letter-spacing:.24em;text-transform:uppercase;white-space:nowrap}}
.rule{{flex:1;height:3px;background:{GOLD_CSS};border-radius:2px}}
.dashes{{display:flex;gap:8px}} .dashes i{{display:block;width:36px;height:5px;border-radius:3px}}
.blue .dashes i{{background:rgba(255,255,255,.35)}} .white .dashes i{{background:#E3E3E3}}
.dashes i.on{{background:{GOLD_CSS} !important}}
.badge{{border:2.5px solid #D4AF37;border-radius:40px;padding:10px 26px;font-weight:700;font-size:25px;letter-spacing:.12em}}
.main{{flex:1;display:flex;flex-direction:column;justify-content:center;padding-bottom:20px}}
.hrow{{display:flex;align-items:flex-end;justify-content:space-between;gap:48px;margin-bottom:44px}} .hrow h1{{flex:1;min-width:0}}
h1{{font-family:'Playfair Display',serif;font-weight:700;font-size:76px;line-height:1.06;letter-spacing:-.01em}}
.cover h1{{font-size:92px;line-height:1.04}}
.num{{font-family:'Playfair Display',serif;font-style:italic;font-weight:700;font-size:170px;line-height:.9;
  background:{GOLD_CSS};-webkit-background-clip:text;background-clip:text;color:transparent;padding:0 6px 10px 0;flex-shrink:0}}
.cover .num{{font-size:300px;position:absolute;right:70px;top:190px}}
.body{{font-size:36px;line-height:1.45;margin-top:40px}} .body b{{font-weight:700}}
.src{{font-size:23px;opacity:.9;margin-top:22px}}
.swipe{{font-weight:700;font-size:33px;text-align:right;margin-top:28px}}
.cover .swipe{{text-align:left}}
.white .swipe{{color:{BLUE}}}
.cards{{display:flex;gap:22px}}
.card{{flex:1;border-radius:22px;padding:30px 26px 30px}}
.blue .card{{background:rgba(255,255,255,.09);border:1.5px solid rgba(255,255,255,.45)}}
.white .card{{background:#fff;border:1.5px solid #E2E2E2}}
.card .ic{{margin-bottom:22px}}
.card h3{{font-weight:700;font-size:31px;line-height:1.15}}
.card p{{font-size:26px;line-height:1.3;margin-top:8px;opacity:.95}}
.chips{{display:flex;gap:16px}}
.chip{{flex:1;border-radius:18px;padding:26px 8px;text-align:center;font-weight:600;font-size:25px}}
.blue .chip{{background:rgba(255,255,255,.09);border:1.5px solid rgba(255,255,255,.45)}}
.white .chip{{border:1.5px solid #E2E2E2}}
.chip .ic{{display:block;margin:0 auto 16px}}
.banner{{display:flex;align-items:center;gap:22px;border-radius:18px;padding:24px 32px;font-weight:700;font-size:31px;margin-top:22px}}
.white .banner{{background:{BLUE};color:#fff}} .blue .banner{{background:#fff;color:{BLUE}}}
.bars{{border-radius:22px;padding:32px 34px}}
.blue .bars{{background:rgba(255,255,255,.09);border:1.5px solid rgba(255,255,255,.45)}}
.white .bars{{border:1.5px solid #E2E2E2}}
.bars .lab{{display:flex;align-items:center;gap:16px;font-weight:700;font-size:25px;letter-spacing:.16em;margin-bottom:26px}}
.bar{{display:grid;grid-template-columns:250px 1fr 150px;align-items:center;gap:20px;margin-top:22px}}
.bar span{{font-size:25px;line-height:1.2}}
.track{{height:38px;border-radius:9px}} .blue .track{{background:rgba(255,255,255,.22)}} .white .track{{background:#EEF5FF}}
.fill{{height:100%;border-radius:9px;background:{GOLD_CSS}}}
.bar b{{font-size:34px;text-align:right}}
.list{{display:grid;grid-template-columns:1fr 1fr;gap:14px 40px;font-size:30px;font-weight:500}}
.list div{{display:flex;align-items:center;gap:16px}}
.list i{{width:12px;height:12px;border-radius:50%;background:{GOLD_CSS};flex-shrink:0}}
.tl{{display:flex;justify-content:space-between;position:relative;border-radius:22px;padding:28px 24px 24px;margin-top:22px}}
.blue .tl{{background:rgba(255,255,255,.09);border:1.5px solid rgba(255,255,255,.45)}}
.white .tl{{border:1.5px solid #E2E2E2}}
.tl:before{{content:'';position:absolute;left:60px;right:60px;top:47px;height:3px;background:{GOLD_CSS}}}
.tl div{{position:relative;text-align:center;font-weight:700;font-size:24px;width:110px}}
.tl div:before{{content:'';display:block;width:34px;height:34px;border-radius:50%;margin:0 auto 14px;background:{GOLD_CSS};box-shadow:0 0 0 4px {BLUE}}}
.white .tl div:before{{box-shadow:0 0 0 4px #fff}}
.icons{{display:flex;gap:16px;margin-bottom:46px}}
.icons span{{width:78px;height:78px;border-radius:50%;border:2.5px solid #D4AF37;display:flex;align-items:center;justify-content:center}}
.sub{{font-size:37px;line-height:1.42;margin-top:38px;max-width:780px}}
.foot{{height:150px;border-top:1.5px solid rgba(255,255,255,.35);display:flex;align-items:center;justify-content:space-between}}
.white .foot{{border-top-color:#E2E2E2}}
.foot span{{font-weight:600;font-size:27px}}
.foot img{{height:64px}}
.ph{{position:relative;border-radius:22px;overflow:hidden;height:390px;box-shadow:0 0 0 3px rgba(212,175,55,.85)}}
.ph img{{width:100%;height:100%;object-fit:cover;display:block}}
.ph .cr{{position:absolute;right:12px;bottom:10px;max-width:80%;font-size:15px;line-height:1.25;color:#fff;
  background:rgba(0,0,0,.45);padding:5px 10px;border-radius:8px;text-align:right}}
.withphoto .num{{font-size:150px}}
.bg{{position:absolute;inset:0;z-index:0}} .bg img{{width:100%;height:100%;object-fit:cover}}
.bg:after{{content:'';position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,40,90,.35) 0%,rgba(30,144,255,.05) 18%,rgba(30,144,255,.12) 34%,rgba(30,144,255,.82) 50%,{BLUE} 60%)}}
.bg .cr{{position:absolute;right:24px;top:178px;z-index:2;font-size:15px;color:#fff;background:rgba(0,0,0,.4);padding:4px 10px;border-radius:8px}}
.cover.hasbg > *:not(.bg):not(.num){{position:relative;z-index:1}} .cover.hasbg .num{{z-index:1;top:auto;bottom:640px;text-shadow:none}} .cover.hasbg .main{{justify-content:flex-end;padding-bottom:40px}} .cover.hasbg .icons{{display:none}} .cover.hasbg h1{{font-size:84px}}
.cta{{background:#fff;color:#000;padding:0}}
.cta .inner{{padding:90px 96px 0;position:relative;z-index:2}} .cta .copy{{max-width:600px}}
.cta h1{{color:{BLUE};font-size:88px;line-height:1.04;margin-top:44px}}
.cta .ln{{display:flex;align-items:center;gap:26px;font-size:36px;margin-top:24px}}
.cta .ln b{{font-weight:700}}
.cta .tag{{font-family:'Playfair Display',serif;font-style:italic;font-weight:700;font-size:46px;margin-top:40px}}
.cta .hs{{position:absolute;right:30px;bottom:120px;height:540px;z-index:1}}
.cta .band{{position:absolute;left:0;right:0;bottom:0;height:120px;background:{BLUE};color:#fff;display:flex;align-items:center;
  justify-content:space-between;padding:0 96px;font-weight:600;font-size:26px;z-index:3}}
.cta .band:before{{content:'';position:absolute;left:0;right:0;top:0;height:5px;background:{GOLD_CSS}}}
.cta .band .sv{{display:flex;align-items:center;gap:14px;font-weight:700}}
.cta .logo{{height:84px}}
"""

DEFS = ('<svg width="0" height="0" style="position:absolute"><defs><linearGradient id="gold" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#8A5A00"/><stop offset=".25" stop-color="#D4AF37"/><stop offset=".5" stop-color="#FFF4C2"/>'
        '<stop offset=".75" stop-color="#D4AF37"/><stop offset="1" stop-color="#8A5A00"/></linearGradient></defs></svg>')

PHOTO_ROOT = pathlib.Path(__file__).resolve().parent.parent

def photo_src(ph):
    f = pathlib.Path(ph["file"])
    f = f if f.is_absolute() else PHOTO_ROOT / f
    mime = "image/png" if f.suffix.lower() == ".png" else "image/jpeg"
    return b64(f, mime)

def photo_panel(ph):
    pos = html.escape(ph.get("position", "center"))
    cr = f'<div class="cr">{html.escape(ph["credit"])}</div>' if ph.get("credit") else ""
    return f'<div class="ph"><img src="{photo_src(ph)}" style="object-position:{pos}">{cr}</div>'

def foot(logo):
    return f'<div class="foot"><span>{FOOTER}</span><img src="{logo}"></div>'

def slide_cover(s, logo):
    icons = "".join(f"<span>{icon(i, 38)}</span>" for i in s.get("icons", []))
    badge = f'<div class="badge">{html.escape(s["badge"])}</div>' if s.get("badge") else ""
    bg = ""
    if s.get("photo"):
        ph = s["photo"]
        cr = f'<div class="cr">{html.escape(ph["credit"])}</div>' if ph.get("credit") else ""
        bg = f'<div class="bg"><img src="{photo_src(ph)}" style="object-position:{html.escape(ph.get("position","center"))}">{cr}</div>'
    return f'''<div class="s cover {s.get("theme","blue")}{" hasbg" if bg else ""}">{bg}
<div class="top"><div class="kicker">{html.escape(s.get("kicker",""))}</div><div class="rule"></div>{badge}</div>
{f'<div class="num">{html.escape(s["numeral"])}</div>' if s.get("numeral") else ""}
<div class="main">{f'<div class="icons">{icons}</div>' if icons else ""}
<h1 style="max-width:{'700px' if s.get('numeral') else '890px'}">{md(s["title"])}</h1>
{f'<div class="sub">{md(s["sub"])}</div>' if s.get("sub") else ""}
<div class="swipe">Swipe →</div></div>{foot(logo)}</div>'''

def slide_point(s, logo):
    steps, step = s.get("steps"), s.get("step")
    dashes = ""
    if steps:
        dashes = '<div class="dashes">' + "".join(f'<i class="{"on" if k < step else ""}"></i>' for k in range(steps)) + "</div>"
    blocks = ""
    if s.get("photo"):
        blocks += photo_panel(s["photo"])
        if any(s.get(k) for k in ("cards","chips","bars","list","timeline")):
            blocks += '<div style="height:22px"></div>'
    if s.get("bars"):
        b = s["bars"]
        rows = "".join(f'<div class="bar"><span>{html.escape(r["label"])}</span><div class="track"><div class="fill" style="width:{max(4,min(100,r["pct"]*100)):.0f}%"></div></div><b>{html.escape(r["value"])}</b></div>' for r in b["rows"])
        blocks += f'<div class="bars"><div class="lab">{icon(b.get("icon","trend-up"),34)}{html.escape(b.get("label",""))}</div>{rows}</div>'
    if s.get("cards"):
        blocks += '<div class="cards">' + "".join(
            f'<div class="card">{icon(c.get("icon","check"),48)}<h3>{html.escape(c["title"])}</h3>{f"<p>{html.escape(c["sub"])}</p>" if c.get("sub") else ""}</div>'
            for c in s["cards"]) + "</div>"
    if s.get("chips"):
        blocks += '<div class="chips">' + "".join(f'<div class="chip">{icon(c.get("icon","check"),46)}{html.escape(c["label"])}</div>' for c in s["chips"]) + "</div>"
    if s.get("list"):
        blocks += '<div class="list">' + "".join(f"<div><i></i>{html.escape(x)}</div>" for x in s["list"]) + "</div>"
    if s.get("banner"):
        blocks += f'<div class="banner">{icon(s["banner"].get("icon","search"),40)}{html.escape(s["banner"]["text"])}</div>'
    if s.get("timeline"):
        blocks += '<div class="tl">' + "".join(f"<div>{html.escape(x)}</div>" for x in s["timeline"]) + "</div>"
    num = f'<div class="num">{html.escape(s["numeral"])}</div>' if s.get("numeral") else ""
    return f'''<div class="s {s.get("theme","blue")}{" withphoto" if s.get("photo") else ""}">
<div class="top"><div class="kicker">{html.escape(s.get("kicker",""))}</div><div class="rule"></div>{dashes}</div>
<div class="main"><div class="hrow"><h1>{md(s["title"])}</h1>{num}</div>{blocks}
{f'<div class="body">{md(s["body"])}</div>' if s.get("body") else ""}
<div style="display:flex;justify-content:space-between;align-items:flex-end">
<div class="src">{html.escape(s.get("source",""))}</div><div class="swipe">{"Swipe →" if not s.get("last") else ""}</div></div>
</div>{foot(logo)}</div>'''

def slide_cta(s, logo, head):
    lines = "".join(f'<div class="ln">{icon(l.get("icon","message"),42)}{"<b>" if l.get("bold") else "<span>"}{html.escape(l["text"])}{"</b>" if l.get("bold") else "</span>"}</div>' for l in s.get("lines", []))
    return f'''<div class="s cta"><div class="inner">
<div class="top"><div class="kicker">{html.escape(s.get("kicker","YOUR NEXT STEP"))}</div><div class="rule"></div><img class="logo" src="{logo}"></div>
<h1 style="max-width:760px">{md(s["title"])}</h1><div class="copy"><div style="margin-top:30px">{lines}</div>
{f'<div class="tag">{md(s["tagline"])}</div>' if s.get("tagline") else ""}</div></div>
<img class="hs" src="{head}">
<div class="band"><span>{FOOTER}</span>{f'<span class="sv">{icon("bookmark",30)}{html.escape(s["save"])}</span>' if s.get("save") else ""}</div></div>'''

def main():
    args = sys.argv[1:]
    assets = pathlib.Path(__file__).parent / "assets"
    if "--assets" in args:
        i = args.index("--assets"); assets = pathlib.Path(args[i + 1]); del args[i:i + 2]
    spec = json.loads(pathlib.Path(args[0]).read_text())
    out = pathlib.Path(args[1]); out.mkdir(parents=True, exist_ok=True)
    logo = b64(assets / "dt_logo.png", "image/png")
    head = b64(assets / "headshot_cut.png", "image/png") if (assets / "headshot_cut.png").exists() else b64(assets / "headshot.jpg", "image/jpeg")
    style = css(assets)
    from playwright.sync_api import sync_playwright
    files = []
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for n, s in enumerate(spec["slides"], 1):
            t = s.get("type", "point")
            body = slide_cover(s, logo) if t == "cover" else slide_cta(s, logo, head) if t == "cta" else slide_point(s, logo)
            pg.set_content(f"<!doctype html><html><head><meta charset='utf-8'><style>{style}</style></head><body>{DEFS}{body}</body></html>")
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(150)
            # overflow guard: report if content is taller than the slide
            over = pg.evaluate("""(()=>{
              const issues=[]; const r=e=>e&&e.getBoundingClientRect();
              const m=document.querySelector('.main'); if(m && m.scrollHeight>m.clientHeight+2) issues.push('content overflows the slide');
              const h=document.querySelector('.hrow h1'), n=document.querySelector('.hrow .num');
              if(h&&n&&r(h).right>r(n).left-24) issues.push('headline touches the gold numeral');
              const t=document.querySelector('.cta .inner'), hs=document.querySelector('.cta .hs'), c=document.querySelector('.cta .copy');
              if(c&&hs){const hb=r(hs),w=document.createTreeWalker(c,NodeFilter.SHOW_TEXT);let x;while((x=w.nextNode())){const g=document.createRange();g.selectNodeContents(x);for(const q of g.getClientRects()){if(q.width&&q.bottom>hb.top+30&&q.right>hb.left+hb.width*0.22){issues.push('CTA text runs into the headshot');break}}}}
              if(t&&t.scrollHeight>1230) issues.push('CTA text too long');
              document.querySelectorAll('h3,.chip,.bar span').forEach(e=>{if(e.scrollWidth>e.clientWidth+2) issues.push('text clipped: '+e.textContent.slice(0,30))});
              return issues.join('; ');
            })()""")
            words = len(re.sub(r"\*\*", "", s.get("body", "")).split())
            if t == "point" and words > 20:
                over = (over + "; " if over else "") + f"body is {words} words (max 20)"
            f = out / f"slide-{n:02d}.png"
            pg.screenshot(path=str(f), clip={"x": 0, "y": 0, "width": W, "height": H})
            files.append(str(f))
            if over:
                print(f"WARNING: slide {n}: {over}. Shorten the text and re-render.", file=sys.stderr)
        br.close()
    print("\n".join(files))

if __name__ == "__main__":
    main()
