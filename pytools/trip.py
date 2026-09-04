"""Shared logic for creating and updating trips.

A trip lives in trips/<year>-<destination>/ and holds:

    index.html              generated, identical across trips
    data/photos.json        generated from the source photos' EXIF
    data/captions.json      hand-edited, created once and never touched again
    data/trip-text.json     hand-edited, created once and never touched again
    photos/day-N/           resized, metadata-stripped copies, committed
    tracks/                 GPX exports

Source photos are imported from local-pics/<any-name>/, a temporary folder that
is gitignored and deleted by hand once a trip is finished. Only the resized
copies are committed, so data/photos.json is the surviving record of where each
photo was taken.

Requires the `exiftool` binary on PATH and Pillow.
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageOps

EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif", ".dng"}

DAY_PREFIX = "day-"

# Long edge, not width, so a portrait photo does not tower over the page.
MAX_EDGE = 1600
QUALITY = 85

TAGS = [
    "-GPSLatitude",
    "-GPSLongitude",
    "-GPSAltitude",
    "-GPSImgDirection",
    "-GPSDateStamp",
    "-GPSTimeStamp",
    "-DateTimeOriginal",
    "-OffsetTimeOriginal",
]


# --- Folders ---------------------------------------------------------------

def day_number(folder):
    """Day index from a "day-N" folder name, or None if it is not one."""
    if not folder.name.startswith(DAY_PREFIX):
        return None
    suffix = folder.name[len(DAY_PREFIX):]
    return int(suffix) if suffix.isdigit() else None


def day_folders(photos_root):
    """The day-N subfolders, in day order. Anything else is ignored."""
    if not photos_root.is_dir():
        return []
    days = [
        (day_number(child), child)
        for child in photos_root.iterdir()
        if child.is_dir()
    ]
    return [(n, folder) for n, folder in sorted(days) if n is not None]


def images_in(folder):
    """Image files directly inside folder, sorted by name."""
    if not folder.is_dir():
        return []
    return sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS),
        key=lambda p: p.name,
    )


# --- Resizing --------------------------------------------------------------

def resize(source, dest):
    """Write a web-sized copy of source to dest, without metadata.

    exif_transpose bakes the rotation into the pixels, so the copy needs no
    Orientation tag to display upright. Saving without an `exif` argument drops
    the metadata: the page reads coordinates from photos.json, and publishing
    EXIF would leak the camera serial and any owner name.
    """
    with Image.open(source) as image:
        upright = ImageOps.exif_transpose(image)
        upright.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
        upright.convert("RGB").save(dest, "JPEG", quality=QUALITY)


# --- Metadata --------------------------------------------------------------

def run_exiftool(paths):
    """exiftool's parsed JSON for the given files, or [] for none.

    -n gives numeric values, so latitude and longitude already carry their
    hemisphere sign and the GPS*Ref tags need no handling here.
    """
    if not paths:
        return []
    result = subprocess.run(
        ["exiftool", "-j", "-n", *TAGS, *[str(p) for p in paths]],
        capture_output=True,
        text=True,
    )
    # exiftool exits non-zero when some files lack tags; that is not fatal.
    if not result.stdout.strip():
        sys.exit(f"exiftool returned no data: {result.stderr.strip()}")
    return json.loads(result.stdout)


def to_utc(entry):
    """Best-effort UTC timestamp as ISO-8601 with a trailing Z.

    Prefers the GPS date/time, which is already UTC. Falls back to
    DateTimeOriginal, which is local time and needs OffsetTimeOriginal to be
    converted; without an offset it is returned as-is.
    """
    date, time = entry.get("GPSDateStamp"), entry.get("GPSTimeStamp")
    if date and time:
        try:
            stamp = datetime.strptime(f"{date} {time}", "%Y:%m:%d %H:%M:%S")
            return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass

    local = entry.get("DateTimeOriginal")
    if not local:
        return None
    try:
        stamp = datetime.strptime(local.split(".")[0], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None

    offset = entry.get("OffsetTimeOriginal")
    if offset and len(offset) == 6:
        sign = -1 if offset[0] == "-" else 1
        hours, minutes = int(offset[1:3]), int(offset[4:6])
        stamp = stamp.replace(
            tzinfo=timezone(timedelta(hours=hours, minutes=minutes) * sign)
        ).astimezone(timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def round_or_none(value, digits):
    return round(value, digits) if isinstance(value, (int, float)) else None


# --- Trip paths ------------------------------------------------------------

def photos_root(trip):
    return trip / "photos"


def day_folder(trip, day):
    return photos_root(trip) / f"{DAY_PREFIX}{day}"


def data_folder(trip):
    return trip / "data"


def is_trip(trip):
    """A trip must at least have the folders the scripts write into."""
    return trip.is_dir() and data_folder(trip).is_dir() and photos_root(trip).is_dir()


# --- Syncing a day ---------------------------------------------------------

def sync_day(trip, day, source, force=False):
    """Make photos/day-N/ match the source folder. Returns a summary dict.

    Identity is the filename stem, not the full name, because resizing changes
    the extension (IMG_01.HEIC becomes IMG_01.JPEG). Both modes add photos new
    to the source and remove ones that have vanished from it; --force differs
    only in redoing photos that are already present, for when a source photo
    was replaced or the resize settings changed.

    An empty or missing source folder is a noop in both modes, so pointing a
    run at a deleted local-pics/ can never wipe a day.
    """
    sources = images_in(source)
    if not sources:
        return {"day": day, "skipped": True, "added": 0, "replaced": 0, "removed": 0}

    dest = day_folder(trip, day)
    dest.mkdir(parents=True, exist_ok=True)

    existing = {p.stem: p for p in images_in(dest)}
    wanted = {p.stem for p in sources}

    removed = 0
    for stem, path in existing.items():
        if stem not in wanted:
            path.unlink()
            removed += 1

    added = replaced = 0
    for path in sources:
        already = existing.get(path.stem)
        if already is not None and not force:
            continue
        if already is not None:
            already.unlink()
            replaced += 1
        else:
            added += 1
        resize(path, dest / f"{path.stem}.JPEG")

    return {
        "day": day,
        "skipped": False,
        "added": added,
        "replaced": replaced,
        "removed": removed,
    }


# --- photos.json -----------------------------------------------------------

def photo_entries(trip, sources_by_day):
    """One entry per photo in photos/day-N/, ordered by day then filename.

    EXIF is read from the source photos, since the committed copies have had
    their metadata stripped. A photo whose source is no longer available (the
    usual case once local-pics/ is deleted) keeps its entry from the existing
    photos.json, so re-running after an import folder is gone does not erase
    coordinates.
    """
    previous = {}
    existing_file = data_folder(trip) / "photos.json"
    if existing_file.is_file():
        previous = {
            entry["file"]: entry
            for entry in json.loads(existing_file.read_text(encoding="utf-8"))
        }

    entries = []
    for day, folder in day_folders(photos_root(trip)):
        by_stem = {p.stem: p for p in sources_by_day.get(day, [])}
        fresh = [by_stem[p.stem] for p in images_in(folder) if p.stem in by_stem]
        metadata = {
            Path(item["SourceFile"]).stem: item for item in run_exiftool(fresh)
        }

        for photo in images_in(folder):
            key = f"{folder.name}/{photo.name}"
            item = metadata.get(photo.stem)
            if item is None:
                # No source to read: keep what photos.json already recorded.
                if key in previous:
                    entries.append(previous[key])
                    continue
                item = {}
            entries.append(
                {
                    "file": key,
                    "day": day,
                    "lat": round_or_none(item.get("GPSLatitude"), 6),
                    "lon": round_or_none(item.get("GPSLongitude"), 6),
                    "alt": round_or_none(item.get("GPSAltitude"), 1),
                    "bearing": round_or_none(item.get("GPSImgDirection"), 2),
                    "timestamp": to_utc(item),
                }
            )
    return entries


def write_json(path, data):
    """Write JSON deterministically, so untouched content stays byte-identical."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_photos_json(trip, sources_by_day):
    entries = photo_entries(trip, sources_by_day)
    write_json(data_folder(trip) / "photos.json", entries)
    return entries


# --- Templates -------------------------------------------------------------

# Identical for every trip: the prose comes from data/trip-text.json at load,
# and the gallery from data/photos.json, so nothing here is trip-specific
# except the title.
INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>

    <link rel="stylesheet" href="../../css/style.css">

    <link
        rel="stylesheet"
        href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    >
</head>
<body>

    <main class="page">

        <h1>{title}</h1>

        <p class="intro"></p>

        <div id="map"></div>

        <div class="notes"></div>

        <h2>Photos</h2>

        <div id="gallery"></div>

    </main>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

    <!-- GPX support
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet-gpx/2.2.0/gpx.min.js"></script>
    -->

    <script src="../../js/text.js"></script>
    <script src="../../js/map.js"></script>
    <script src="../../js/gallery.js"></script>

</body>
</html>
"""

# JSON has no comments, so the example is a key. js/gallery.js looks photos up
# by their exact "day-N/filename" path, so this key never matches one.
CAPTIONS_EXAMPLE = {
    "_example": (
        "Copy a \"file\" value from photos.json as the key, caption as the "
        "value, e.g. \"day-1/IMG_0001.JPEG\": \"Crossing the river\". "
        "Delete this line once you add one."
    )
}


def title_from_name(name):
    """"2024-jamtland" -> "Jamtland 2024", falling back to the raw name."""
    year, _, rest = name.partition("-")
    if not year.isdigit() or not rest:
        return name
    return f"{rest.replace('-', ' ').title()} {year}"


def default_trip_text(days):
    """Starting point for a trip's prose.

    Any value may be a plain string or a list of strings. A list is
    concatenated with nothing between the entries, so long prose can be
    wrapped across source lines with the spacing written explicitly:
    ["a ", "b"] is "a b". Blank lines start a new paragraph either way.
    """
    return {
        "intro": [
            "Short intro, a few lines. Links are written as ",
            "[label](https://example.com).",
        ],
        "notes": [
            "Longer notes below the map. This value is a list only so long ",
            "text can be wrapped in the source; the entries are joined as ",
            "written.",
            "\n\n",
            "A blank line starts a new paragraph.",
        ],
        "days": {str(day): {"title": "", "blurb": ""} for day in sorted(days)},
    }
