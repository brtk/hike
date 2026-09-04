#!/usr/bin/env python3
"""Dump GPS/EXIF data for a trip's photos as JSON on stdout.

Expects a photos folder holding day-N subfolders, and writes a JSON list to
stdout ordered by day then filename, one object per photo:

    [
      {
        "file": "day-1/IMG_0001.JPEG",
        "day": 1,
        "lat": 68.4091,
        "lon": 18.1286,
        "alt": 638.5,
        "bearing": 201.95,
        "timestamp": "2026-07-30T10:31:11Z"
      }
    ]

With --stub, writes a captions file instead: a filename -> caption map with
every caption empty, ready to be filled in by hand. Existing captions in the
file are preserved, so it is safe to re-run after adding photos.

Superseded by create_trip.py / update_trip.py, which resize and read metadata
in one step. Kept as a standalone EXIF dump.

NOTE: point this at a folder of ORIGINALS laid out as day-N subfolders. The
committed copies in trips/*/photos/ have had their metadata stripped, so run
against those it emits all-null coordinates -- redirecting that over
data/photos.json would erase the GPS record.

Requires the `exiftool` binary on PATH.
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif", ".dng"}

# Originals live in photos/local/day-N/ and are deliberately not published.
LOCAL_DIR = "local"
DAY_PREFIX = "day-"

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


def day_number(folder):
    """Day index from a "day-N" folder name, or None if it is not one."""
    if not folder.name.startswith(DAY_PREFIX):
        return None
    suffix = folder.name[len(DAY_PREFIX):]
    return int(suffix) if suffix.isdigit() else None


def day_folders(photos_root):
    """The day-N subfolders, in day order. Skips local/ and anything else."""
    days = [
        (day_number(child), child)
        for child in photos_root.iterdir()
        if child.is_dir() and child.name != LOCAL_DIR
    ]
    return [(n, folder) for n, folder in sorted(days) if n is not None]


def images_in(folder):
    """Image files directly inside folder, sorted by name."""
    return sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS),
        key=lambda p: p.name,
    )


def photos_in(photos_root):
    """(day, path) for every image across the day folders, in day order."""
    return [
        (day, path)
        for day, folder in day_folders(photos_root)
        for path in images_in(folder)
    ]


def run_exiftool(paths):
    """Return exiftool's parsed JSON for the given files.

    -n gives numeric values, so latitude and longitude already carry their
    hemisphere sign and the GPS*Ref tags don't need to be applied by hand.
    """
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
    DateTimeOriginal, which is local time and needs OffsetTimeOriginal
    to be converted; without an offset it is returned as-is.
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
        delta = timedelta(hours=hours, minutes=minutes) * sign
        stamp = stamp.replace(tzinfo=timezone(delta)).astimezone(timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def round_or_none(value, digits):
    return round(value, digits) if isinstance(value, (int, float)) else None


def caption_stub(keys, existing_path):
    """Filename -> caption map, keeping any captions already written.

    An empty string means "no caption"; the gallery renders nothing for it.
    """
    existing = {}
    if existing_path.is_file():
        try:
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as error:
            sys.exit(f"could not read {existing_path}: {error}")

    return {key: existing.get(key, "") for key in keys}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", help="a trip's photos folder, holding day-N subfolders")
    parser.add_argument(
        "--stub",
        metavar="FILE",
        help="emit a captions file keyed by filename instead of EXIF data, "
             "preserving captions already present in FILE",
    )
    args = parser.parse_args()

    if shutil.which("exiftool") is None:
        sys.exit("exiftool not found on PATH")

    folder = Path(args.folder)
    if not folder.is_dir():
        sys.exit(f"not a directory: {folder}")

    entries = photos_in(folder)
    keys = {path: f"{path.parent.name}/{path.name}" for _, path in entries}

    if args.stub:
        json.dump(
            caption_stub(list(keys.values()), Path(args.stub)), sys.stdout, indent=2
        )
        print()
        return

    if not entries:
        json.dump([], sys.stdout, indent=2)
        print()
        return

    days = {str(path): day for day, path in entries}
    photos = [
        {
            "file": keys[Path(entry["SourceFile"])],
            "day": days[str(Path(entry["SourceFile"]))],
            "lat": round_or_none(entry.get("GPSLatitude"), 6),
            "lon": round_or_none(entry.get("GPSLongitude"), 6),
            "alt": round_or_none(entry.get("GPSAltitude"), 1),
            "bearing": round_or_none(entry.get("GPSImgDirection"), 2),
            "timestamp": to_utc(entry),
        }
        for entry in run_exiftool([path for _, path in entries])
    ]

    json.dump(photos, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
