# Hike Log

A static travel/hiking journal hosted on GitHub Pages. No backend, no database,
no build step — just HTML, CSS, JavaScript and a few Python helper scripts.

## Goals

- Landing page listing all trips.
- One page per trip: intro, map, notes, photo gallery.
- Photo markers on an interactive map, placed from EXIF GPS.
- Approximate camera direction shown from EXIF bearing.
- Garmin GPX tracks drawn on the same map. *(not yet implemented)*
- Easy to migrate away from GitHub Pages.

---

## Structure

```text
hike/
├── index.html                  # landing page, links to trips (placeholder)
├── .gitignore
├── local-pics/                 # temp photo import; contents gitignored
│   └── <any-name>/             # one folder per day's source photos
├── css/style.css               # shared by every trip
├── js/                         # shared by every trip
│   ├── text.js                 # renders intro/notes/day text
│   ├── map.js                  # Leaflet map, tile layers, photo markers
│   ├── gallery.js              # photo gallery grouped by day
│   └── journal.js              # empty, unused
├── pytools/
│   ├── trip.py                 # shared module: resize, EXIF, sync
│   ├── create_trip.py          # make a new trip
│   ├── update_trip.py          # add or refresh a day's photos
│   └── photo_exif.py           # standalone EXIF dump, superseded
└── trips/<year>-<destination>/
    ├── index.html              # generated; identical across trips but the title
    ├── data/
    │   ├── photos.json         # GENERATED — do not hand-edit
    │   ├── captions.json       # hand-edited
    │   └── trip-text.json      # hand-edited
    ├── photos/day-N/           # resized, metadata stripped, committed
    └── tracks/                 # GPX exports (not yet used)
```

Trip folders are named `<year>-<destination>`, e.g. `2026-abisko`. The page
title is derived from that (`Abisko 2026`), so it needs no separate config.

Days are `day-N` folders. No day order is enforced — `--d5` without a day 4 is
fine, and `day-10` sorts after `day-9` because the number is parsed, not
compared as a string.

---

## Workflow

```text
Copy photos off the phone into local-pics/<name>/, one folder per day
↓
python3 pytools/create_trip.py 2026-abisko --d1 local-pics/<name>
↓
Edit trips/2026-abisko/data/trip-text.json      (intro, notes, day titles)
Edit trips/2026-abisko/data/captions.json       (per-photo captions, optional)
↓
python3 -m http.server 8000     and check http://localhost:8000/trips/2026-abisko/
↓
git add . && git commit && git push
↓
Empty local-pics/ by hand when the trip is done
```

### Creating a trip

```sh
python3 pytools/create_trip.py 2026-abisko --d1 local-pics/day-one --d2 local-pics/day-two
```

Writes the whole structure: `index.html`, the three data files, and a
`photos/day-N` folder per `--dN`. With no `--dN` the trip is created empty
(`photos.json` is `[]`, no day folders), ready for `update_trip.py` later.

Refuses to run if the trip folder already exists.

### Adding or refreshing photos

```sh
python3 pytools/update_trip.py 2026-abisko --d1 local-pics/day-one --d5 local-pics/day-five
```

Touches only `photos/day-N/` for the days named, and `data/photos.json`.
Never modifies `captions.json`, `trip-text.json` or `index.html`.

**The source folder is the authority.** Each `--dN` makes `photos/day-N` match
its source folder in both directions:

| source photo | in `day-N/` | default | `--force` |
| --- | --- | --- | --- |
| present | absent | added | added |
| present | present | skipped | reprocessed |
| absent | present | deleted | deleted |

`--force` differs in one row only: it redoes photos already present, for when a
source photo was replaced or the resize settings changed. It is about
staleness, not deletion.

Two consequences:

- Deleting a photo from `photos/day-N/` by hand does not stick — the next run
  restores it from the source. To drop a photo, remove it from the source folder.
- **An empty or missing source folder is a noop**, in both modes. A run pointed
  at an emptied `local-pics/` can never wipe a day.

Photos are matched by filename **stem**, not full name, because resizing changes
the extension (`IMG_01.HEIC` becomes `IMG_01.JPEG`).

---

## Photos

Camera originals are never committed. `local-pics/` is a temporary import
folder whose contents are gitignored, emptied by hand once a trip is finished —
the originals remain in iCloud. The folder itself is kept in the repo (via
`local-pics/.gitkeep`) so it never has to be recreated. Only the resized copies
in `trips/*/photos/day-N/` go into git.

Each committed copy is:

- **1600px on its long edge** — the content column is 800px CSS, so this is the
  2× copy for retina displays. Capping the long edge rather than the width keeps
  a portrait photo from towering over the page (1200×1600, not 1600×2133).
- **JPEG quality 85**, roughly 300–500KB. The first trip went 22MB → 4.3MB.
- **Stripped of all metadata.** Rotation is baked into the pixels during resize,
  so no Orientation tag is needed. Publishing EXIF would leak the camera serial
  and any owner name.

Because the committed copies carry no EXIF, **`data/photos.json` is the only
surviving record of where each photo was taken.** It must be committed. If a
source photo is no longer available, `update_trip.py` keeps that photo's
existing entry rather than blanking it.

`pytools/photo_exif.py` predates this and is kept as a standalone EXIF dump.
Point it at *originals*; run against the stripped copies it returns all-nulls,
and redirecting that over `photos.json` would erase the GPS record.

---

## Text content

All prose for a trip lives in `data/trip-text.json`. `index.html` is a fixed
template — the browser fetches the text at load, so editing prose never means
editing markup, and every trip's `index.html` is byte-identical but the title.

```json
{
  "intro": "A few lines above the map.",
  "notes": "Longer text below the map.\n\nBlank lines start a new paragraph.\n\nSee [my packlist](https://lighterpack.com/r/12sdq) for gear.",
  "days": {
    "1": { "title": "Into the valley", "blurb": "Walked in from the station." }
  }
}
```

- Links are written `[label](https://example.com)`. Everything else is
  HTML-escaped, so a stray `<` or `&` in the prose cannot break the page.
- Any empty value is omitted rather than rendered as an empty box: no `intro`
  means no intro paragraph, no day `title` means a plain `Day 3` heading.

JSON has no multi-line strings, so any value may instead be a **list of
strings**, purely to wrap long prose across source lines. The entries are
concatenated with nothing between them, so spacing is explicit — mind the
trailing space:

```json
"intro": [
  "A long sentence that would otherwise sit on one very long line, ",
  "continued here without any implicit space being added."
]
```

`["a ", "b"]` is `"a b"`; `["a", "b"]` is `"ab"`. Paragraph breaks still come
from blank lines, written as a `"\n\n"` entry or inside one. This works for
`intro`, `notes`, and each day's `title` and `blurb`.

### Captions

`data/captions.json` maps a photo to a caption, keyed by the same `"day-N/file"`
path that `photos.json` uses:

```json
{
  "day-1/IMG_4894.JPEG": "Crossing the river"
}
```

Hand-maintained; no script ever writes to it after the trip is created. Copy the
filenames from `photos.json` rather than typing them. A key with no matching
photo is ignored, which is how the `_example` line in a fresh trip works.

Note that **moving a photo between days changes its key** and silently orphans
its caption.

---

## Map

Leaflet 1.9.4, pinned. Three base layers, switchable top-right:

| Layer | Source | Contours | Max zoom |
| --- | --- | --- | --- |
| OpenStreetMap *(default)* | tile.openstreetmap.org | no | 19 |
| Topographic | OpenTopoMap | **yes** | 17 |
| Satellite | Esri World Imagery | no | 19 |

Photo markers are an arrow in a circle, rotated to the EXIF bearing snapped to
one of 8 compass points (N, NE, E, …). A photo with no bearing gets the default
pin; a photo with no coordinates is left off the map but still appears in the
gallery. `fitBounds` frames all markers, and a ↺ control returns to that view.

Tile usage is within both servers' policies: personal, low traffic,
non-commercial, no automated fetching, attribution present on every layer. **The
attribution control must stay visible.** OpenTopoMap is a small volunteer
server, which is why OSM is the default rather than the topo layer.

When GPX lands, push the track layer into `extraLayers` in `js/map.js`; the home
view is already the **union** of every layer's bounds, so whichever is larger —
photos or track — decides the zoom.

---

## Conventions

- `data/photos.json` is generated. Everything else in `data/` is hand-edited.
- Output is deterministic — sorted by day then filename, fixed key order, fixed
  rounding — so re-running a script leaves untouched days byte-identical and the
  git diff shows only what actually changed.
- Error handling is deliberately thin. These are personal tools; the assumption
  is that the user knows what they are doing.
- `css/style.css` and `js/*` are shared by every trip. Trip folders hold content
  only. `--content-width` in `style.css` sets the column width for map, text and
  photos together.

## Setup

Two dependencies, both system packages:

```sh
sudo apt install libimage-exiftool-perl python3-pil
```

`exiftool` reads the photo metadata; Pillow (`python3-pil`) does the resizing.
Installing Pillow through apt rather than pip avoids the PEP 668 "externally
managed environment" error on Debian/Ubuntu, and needs no virtualenv.

Viewing the site locally requires a web server — `fetch` is blocked under
`file://`, so opening the HTML by double-click gives an empty map and gallery:

```sh
python3 -m http.server 8000
```

---

## Not yet done

- **Landing page** — `index.html` at the root is still a placeholder.
- **GPX tracks** — `tracks/` is empty, `js/journal.js` unwritten, and the
  leaflet-gpx script tag in the trip template is commented out.
- **Marker-to-photo navigation** — clicking a marker should jump to that photo
  in the gallery.
