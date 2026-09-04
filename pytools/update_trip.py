#!/usr/bin/env python3
"""Add or refresh photos for some days of an existing trip.

    python3 pytools/update_trip.py 2024-jamtland --d1 local-pics/day-one --d5 ...

Each --dN makes photos/day-N match its source folder: photos new to the source
are added, ones that have vanished from it are removed. --force also reprocesses
photos already present, for when a source photo was replaced or the resize
settings changed.

Only the days named are touched, and only photos/ and data/photos.json are
written. captions.json, trip-text.json and index.html are never modified.
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
    if not T.is_trip(path):
        sys.exit(f"{path} is not a trip folder; create it with create_trip.py")

    sources = day_sources(args)
    if not sources:
        sys.exit("nothing to do: pass at least one --dN FOLDER")

    for day, source in sorted(sources.items()):
        result = T.sync_day(path, day, source, force=args.force)
        if result["skipped"]:
            print(f"day-{day}: nothing in {source}, left alone")
        else:
            print(
                f"day-{day}: +{result['added']} added, "
                f"{result['replaced']} replaced, -{result['removed']} removed"
            )

    # Every day is rescanned, so days not named keep their existing entries.
    by_day = {day: T.images_in(source) for day, source in sources.items()}
    entries = T.write_photos_json(path, by_day)
    print(f"photos.json: {len(entries)} photos")


if __name__ == "__main__":
    main()
