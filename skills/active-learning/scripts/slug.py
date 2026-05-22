#!/usr/bin/env python3
"""Slugify de tópico de estudo. Uso: ``slug.py "<texto livre>"``."""

from __future__ import annotations

import sys

from prumo_assist.core.note_paths import slugify


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("uso: slug.py <texto>")
    print(slugify(sys.argv[1]))


if __name__ == "__main__":
    main()
