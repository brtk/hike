import argparse
"""Parsing of the --dN flags shared by create_trip.py and update_trip.py.

argparse has no native "any --dN" flag, so the days are declared up front.
Nine is the practical maximum for a trip, but --d99 is allowed: no day order
is enforced anywhere.
"""

from pathlib import Path

MAX_DAY = 99


def add_day_arguments(parser):
    parser.add_argument(
        "--force",
        action="store_true",
        help="reprocess photos already present, for a changed source or "
             "changed resize settings",
    )
    for day in range(1, MAX_DAY + 1):
        parser.add_argument(
            f"--d{day}",
            metavar="FOLDER",
            help=f"source folder for day {day}" if day <= 3 else argparse.SUPPRESS,
        )


def day_sources(args):
    """{day number: source Path} for every --dN given."""
    return {
        day: Path(getattr(args, f"d{day}"))
        for day in range(1, MAX_DAY + 1)
        if getattr(args, f"d{day}", None)
    }
