"""World locations repository — the same 45k-city system as DOMY Watch.

Hierarchy: Continent -> Subregion -> Country -> [Admin ->] City, with
MIXED depth — children are classified by shape ("latitude" in value =
city leaf), never by depth. Picking a city fills latitude, longitude and
IANA timezone automatically; the user NEVER types a timezone by hand.
"""

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "world_locations.json"

# Single-codepoint letters NFKD cannot decompose (same table as DOMY).
_TRANSLITERATIONS = {
    "ø": "o", "đ": "d", "ł": "l", "æ": "ae",
    "œ": "oe", "ß": "ss", "þ": "th", "ð": "d",
}


@dataclass(frozen=True)
class CityRecord:
    path: tuple[str, ...]           # (continent, subregion, country[, admin], city)
    name: str
    latitude: float
    longitude: float
    timezone: str                   # IANA name


@dataclass(frozen=True)
class LocationNode:
    """One child at some level: a navigable group or a selectable city."""

    name: str
    record: CityRecord | None       # set only for city leaves

    @property
    def is_city(self) -> bool:
        return self.record is not None


def _is_city_leaf(value: dict) -> bool:
    return "latitude" in value


def fold_name(text: str) -> str:
    """Search folding: bundled names are ASCII transliterations, so
    native spellings must match them ("Niš" finds "Nis")."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return "".join(_TRANSLITERATIONS.get(ch, ch) for ch in stripped.casefold())


class LocationRepository:
    def __init__(self, path: Path = DB_PATH):
        self._path = path
        self._tree: dict | None = None
        self._cities_cache: list[tuple[str, str, tuple[str, ...]]] | None = None

    def load(self) -> None:
        if self._tree is None:
            self._tree = json.loads(self._path.read_text(encoding="utf-8"))

    def children(self, node_path: tuple[str, ...] = ()) -> list[LocationNode]:
        """Children of the node at `node_path` (empty tuple = continents)."""
        self.load()
        node = self._tree
        for depth, segment in enumerate(node_path):
            try:
                node = node[segment]
            except KeyError:
                raise KeyError(
                    f"unknown location path segment {segment!r} "
                    f"at depth {depth} of {node_path!r}") from None
        return [
            LocationNode(
                name=name,
                record=(self._make_record(node_path + (name,), value)
                        if _is_city_leaf(value) else None),
            )
            for name, value in node.items()
        ]

    def all_cities(self) -> list[tuple[str, str, tuple[str, ...]]]:
        """(folded name, display name, path) of EVERY city — cached full
        walk, used by the live search filter."""
        if self._cities_cache is not None:
            return self._cities_cache
        self.load()
        cities: list[tuple[str, str, tuple[str, ...]]] = []
        stack: list[tuple[tuple[str, ...], dict]] = [((), self._tree)]
        while stack:
            node_path, node = stack.pop()
            for child_name, value in node.items():
                child_path = node_path + (child_name,)
                if _is_city_leaf(value):
                    cities.append((fold_name(child_name), child_name, child_path))
                else:
                    stack.append((child_path, value))
        self._cities_cache = cities
        return cities

    def record_at(self, path: tuple[str, ...]) -> CityRecord | None:
        """The CityRecord for a full city path, or None if not a city."""
        try:
            for child in self.children(path[:-1]):
                if child.is_city and child.name == path[-1]:
                    return child.record
        except KeyError:
            pass
        return None

    @staticmethod
    def _make_record(node_path: tuple[str, ...], leaf: dict) -> CityRecord:
        return CityRecord(
            path=node_path,
            name=node_path[-1],
            latitude=float(leaf["latitude"]),
            longitude=float(leaf["longitude"]),
            timezone=leaf["timezone"],
        )
