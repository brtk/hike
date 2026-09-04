#!/usr/bin/env python3
"""Create a new trip, optionally importing photos for some days.

    python3 pytools/create_trip.py 2024-jamtland --d1 local-pics/day-one

Writes the whole trip structure: index.html, the three data files, and a
photos/day-N folder per --dN given. With no --dN the trip is created empty,
with photos.json as [] and no day folders.

captions.json and trip-text.json are written once here and never touched by
update_trip.py, so hand-written text is safe.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import trip as T
from day_args import day_sources, add_day_arguments


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", help="trip folder name, e.g. 2024-jamtland")
    add_day_arguments(parser)
    args = parser.parse_args()

    path = Path("trips") / args.name
    if path.exists():
        sys.exit(f"{path} already exists; use update_trip.py to add photos")

    sources = day_sources(args)

    T.data_folder(path).mkdir(parents=True)
    T.photos_root(path).mkdir(parents=True)
    (path / "tracks").mkdir(parents=True)

    title = T.title_from_name(args.name)
    (path / "index.html").write_text(
        T.INDEX_HTML.format(title=title), encoding="utf-8"
    )
    T.write_json(T.data_folder(path) / "captions.json", T.CAPTIONS_EXAMPLE)
    T.write_json(
        T.data_folder(path) / "trip-text.json", T.default_trip_text(sources)
    )

    by_day = {}
    for day, source in sorted(sources.items()):
        result = T.sync_day(path, day, source)
        by_day[day] = T.images_in(source)
        if result["skipped"]:
            print(f"day-{day}: no photos in {source}")
        else:
            print(f"day-{day}: {result['added']} photos")

    entries = T.write_photos_json(path, by_day)
    print(f"created {path} ({len(entries)} photos)")
    print(f"next: edit {T.data_folder(path) / 'trip-text.json'}")


if __name__ == "__main__":
    main()
