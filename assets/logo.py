"""Draw Glass's logo: a crystal you can see straight through.

    python assets/logo.py        (writes the SVGs next to this file)

The crystal keeps the shape of the first mark, a hexagon with six spokes and the two triangles
of a star, redrawn in line art and read as a glass cube seen corner on. The edges and face
diagonals in front are drawn firmly; the ones behind are drawn finely, still visible through
the glass, because nothing in Glass is hidden. The crystal is ice: each face takes a cool hue
(pale ice on top, sky on the left, deeper blue on the right), the centre fills with a soft ice
gradient, a faint glow sits behind it on dark backgrounds, and a glint crosses it once. The
wordmark keeps the monochrome ink of the house style of github.com/EgorKhaklin, so the crystal
is the one accent; it is set in Cinzel capitals, kept as outlines
(cinzel-caps.json, SIL Open Font License 1.1) so it renders the same everywhere.

GitHub serves these through an img tag, so the animation lives inside each SVG: it plays once,
uses opacity, transforms and stroke drawing only, and a reduced-motion rule shows the finished
frame.

Writes: glass-light.svg and glass-dark.svg (the lockup for the README header), and
glass-mark-light.svg and glass-mark-dark.svg (the crystal alone, square).
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPS = json.loads((HERE / "cinzel-caps.json").read_text())
THEMES = {"light": ("#1F2328", "#59636E"), "dark": ("#E6EDF3", "#9198A1")}

# the crystal, in its own 240 x 240 box: a hexagon standing on a corner
C, R = 120.0, 104.0
V = [(C + R * math.cos(math.radians(60 * k - 90)), C + R * math.sin(math.radians(60 * k - 90)))
     for k in range(6)]                      # top, upper right, lower right, bottom, lower left, upper left
STAR = [(C + R / math.sqrt(3) * math.cos(math.radians(60 * k - 60)),
         C + R / math.sqrt(3) * math.sin(math.radians(60 * k - 60))) for k in range(6)]  # between V[k], V[k+1]
NEAR, FAR = (5, 1, 3), (0, 2, 4)             # the corners the near (front) and far (hidden) vertex reach
# The faces' tint, by the hexagon edges each face owns: top, right, left. Ink darkens on light and
# lightens on dark, so the order flips to keep the top face the brightest in both themes.
FACES = {"top": (5, 0), "right": (1, 2), "left": (3, 4)}
SUBTITLE = "VERIFIABLE FUNCTIONAL LANGUAGE"
# The ice: per theme, the crystal's line colour, the diamond, and each face's hue and opacity
# (the first triangle of a face a little stronger than the second, so the facets read as cut).
ICE = {
    "light": {"line": "#0B4A6F", "gem": "#0EA5E9", "core": ("#E0F7FF", .9), "glow": 0,
              "face": {"top": ("#9EE7FF", .62, .44), "left": ("#38BDF8", .40, .28), "right": ("#2B7FFF", .34, .24)}},
    "dark": {"line": "#CFF3FF", "gem": "#5EE6FF", "core": ("#E0F7FF", .22), "glow": .32,
             "face": {"top": ("#9EE7FF", .40, .28), "left": ("#38BDF8", .32, .22), "right": ("#2B7FFF", .38, .26)}},
}


def f(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def poly(pts):
    return "M" + "L".join("%s %s" % (f(x), f(y)) for x, y in pts) + "Z"


def line(a, b):
    return "M%s %sL%s %s" % (f(a[0]), f(a[1]), f(b[0]), f(b[1]))


def diamond(cx, cy, r):
    return ('<rect x="%s" y="%s" width="%s" height="%s" transform="rotate(45 %s %s)"/>'
            % (f(cx - r), f(cy - r), f(2 * r), f(2 * r), f(cx), f(cy)))


def text_run(label, cap, track_em, x0, base):
    """Cinzel capitals from x0 on a baseline: (svg, width)."""
    s = cap / CAPS["cap"]
    track = track_em * CAPS["upm"] * s
    out, x = [], 0.0
    for ch in label:
        if ch == " ":
            x += CAPS["space"] * s + track
            continue
        g = CAPS["glyphs"][ch]
        out.append('<path transform="translate(%s %s) scale(%s)" d="%s"/>'
                   % (f(x0 + x), f(base), ("%.5f" % s).rstrip("0"), g["d"]))
        x += g["advance"] * s + track
    return "".join(out), x - track


STYLE = (".draw{stroke-dasharray:1 2;stroke-dashoffset:1.01;animation:draw 1.1s cubic-bezier(.45,0,.2,1) .1s 1 both}"
         ".edge{stroke-dasharray:1 2;stroke-dashoffset:1.01;animation:draw .7s cubic-bezier(.3,0,.2,1) .7s 1 both}"
         ".far{opacity:0;animation:far .9s ease-out 1.25s 1 both}"
         ".tint{opacity:0;animation:fade 1.1s ease-out 1.1s 1 both}"
         ".gem{opacity:0;animation:fade .5s ease-out 1.75s 1 both}"
         ".word{opacity:0;animation:fade 1s ease-out 1.2s 1 both}"
         ".glint{opacity:0;animation:glint 1.3s cubic-bezier(.4,0,.2,1) 2s 1 both}"
         "@keyframes draw{from{stroke-dashoffset:1.01}to{stroke-dashoffset:0}}"
         "@keyframes fade{from{opacity:0}to{opacity:1}}"
         "@keyframes far{from{opacity:0}to{opacity:.5}}"
         "@keyframes glint{0%{opacity:0;transform:translateX(0px) skewX(-20deg)}20%{opacity:1}80%{opacity:1}"
         "100%{opacity:0;transform:translateX(400px) skewX(-20deg)}}"
         "@media (prefers-reduced-motion: reduce){.draw,.edge{animation:none;stroke-dashoffset:0}"
         ".tint,.gem,.word{animation:none;opacity:1}.far{animation:none;opacity:.5}.glint{animation:none;opacity:0}}")


def crystal(ink, theme, ox, oy, k, uid):
    """The crystal at (ox, oy), scale k. uid keeps ids unique when several are inlined."""
    ice = ICE[theme]
    ink = ice["line"]
    tint = "".join('<path fill="%s" fill-opacity="%s" d="%s"/>'
                   % (ice["face"][face][0], f(ice["face"][face][1 + i]), poly([V[e], V[(e + 1) % 6], STAR[e]]))
                   for face, edges in FACES.items() for i, e in enumerate(edges))
    core = '<path fill="url(#core%s)" d="%s"/>' % (uid, poly(STAR))
    glow = ('<path class="tint" filter="url(#glow%s)" fill="#38BDF8" fill-opacity="%s" d="%s"/>'
            % (uid, f(ice["glow"]), poly(V))) if ice["glow"] else ""
    near = "".join('<path class="edge" pathLength="1" style="animation-delay:%ss" d="%s"/>'
                   % (f(.7 + .1 * i), line((C, C), V[j])) for i, j in enumerate(NEAR))
    far = "".join(line((C, C), V[j]) for j in FAR)
    return f"""<g transform="translate({f(ox)} {f(oy)}) scale({f(k)})">
<defs>
<clipPath id="in{uid}"><path d="{poly(V)}"/></clipPath>
<linearGradient id="sheen{uid}" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0"/><stop offset=".5" stop-color="#FFFFFF" stop-opacity=".45"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>
<radialGradient id="core{uid}" cx="{f(C)}" cy="{f(C)}" r="{f(R * .62)}" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="{ice["core"][0]}" stop-opacity="{f(ice["core"][1])}"/><stop offset="1" stop-color="{ice["core"][0]}" stop-opacity="0"/></radialGradient>
<filter id="glow{uid}" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="16"/></filter>
</defs>
{glow}
<g class="tint">{tint}{core}</g>
<g class="far" fill="none" stroke="{ink}" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round">
<path d="{far}"/>
<path d="{poly([V[j] for j in FAR])}"/>
</g>
<g fill="none" stroke="{ink}" stroke-linecap="round" stroke-linejoin="round">
<path class="draw" pathLength="1" stroke-width="2.1" d="{poly(V)}"/>
<path class="edge" pathLength="1" stroke-width="1.3" style="animation-delay:1s" d="{poly([V[j] for j in NEAR])}"/>
<g stroke-width="1.6">{near}</g>
</g>
<g class="gem" fill="{ice["gem"]}">{diamond(C, C, 4.6)}</g>
<g clip-path="url(#in{uid})"><rect class="glint" x="-90" y="0" width="60" height="240" fill="url(#sheen{uid})"/></g>
</g>"""


def lockup(theme):
    ink, muted = THEMES[theme]
    W, H = 1200, 360
    k = 1.1
    name_cap, name_track = 74, .26
    sub_cap, sub_track = 14, .3
    _, nw = text_run("GLASS", name_cap, name_track, 0, 0)
    _, sw = text_run(SUBTITLE, sub_cap, sub_track, 0, 0)
    bw = max(nw, sw)
    hw = 2 * R * math.sin(math.radians(60)) * k   # the hexagon's own width, for optical centring
    gap = 60
    hx = (W - (hw + gap + bw)) / 2
    tx = hx + hw + gap
    name, _ = text_run("GLASS", name_cap, name_track, tx + (bw - nw) / 2, 192)
    sub, _ = text_run(SUBTITLE, sub_cap, sub_track, tx + (bw - sw) / 2, 242)
    rule_y = 216
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t">
<title id="t">Glass: a verifiable functional language</title>
<style>{STYLE}</style>
{crystal(ink, theme, hx - (C - hw / k / 2) * k, H / 2 - C * k, k, theme)}
<g class="word" fill="{ink}">{name}</g>
<g class="word" fill="{muted}">{sub}</g>
<g class="word" stroke="{muted}" stroke-width="1.1"><path d="M{f(tx)} {rule_y}H{f(tx + bw / 2 - 12)}M{f(tx + bw / 2 + 12)} {rule_y}H{f(tx + bw)}"/></g>
<g class="word" fill="{muted}">{diamond(tx + bw / 2, rule_y, 3.2)}</g>
</svg>
""", nw, sw


def mark(theme):
    ink, _ = THEMES[theme]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 280" width="280" height="280" role="img" aria-labelledby="t">
<title id="t">Glass</title>
<style>{STYLE}</style>
{crystal(ink, theme, 20, 20, 1.0, "m" + theme)}
</svg>
"""


def main():
    for theme in THEMES:
        svg, nw, sw = lockup(theme)
        (HERE / f"glass-{theme}.svg").write_text(svg)
        (HERE / f"glass-mark-{theme}.svg").write_text(mark(theme))
        print("%s: name %.0f px, subtitle %.0f px" % (theme, nw, sw))


if __name__ == "__main__":
    main()
