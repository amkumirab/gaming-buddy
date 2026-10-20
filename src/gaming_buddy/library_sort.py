"""Stable library sort keys shared by storage and the control panel."""

from enum import StrEnum


class LibrarySort(StrEnum):
    DEFAULT = "default"
    NEWEST = "newest"
    OLDEST = "oldest"
    TITLE = "title"


LIBRARY_SORT_OPTIONS = (
    (LibrarySort.DEFAULT, "Default"),
    (LibrarySort.NEWEST, "Newest first"),
    (LibrarySort.OLDEST, "Oldest first"),
    (LibrarySort.TITLE, "Title A–Z"),
)


def normalize_library_sort(value: object) -> LibrarySort:
    """Treat unknown or malformed preferences as the existing default order."""
    try:
        return LibrarySort(value)
    except (ValueError, TypeError):
        return LibrarySort.DEFAULT
