"""City configuration loader (spec 4).

Each `config/cities/{slug}.yaml` declares bbox, tz, per-city UTM zone, ward source
and id field, the data.gov.in -> OpenAQ station map, a verified OpenAQ location
seed, languages, and inventory references. This module is the single typed reader.
"""

from __future__ import annotations

import yaml
from pydantic import BaseModel, Field

from vayu.grid import BBox
from vayu.settings import repo_root

CITIES_DIR = repo_root() / "config" / "cities"
SUPPORTED = ("delhi", "mumbai", "bengaluru")


class WardsCfg(BaseModel):
    source: str
    url: str | None = None
    local_path: str | None = None
    ward_id_field: str
    ward_id_numeric: bool = True
    name_field: str | None = None
    layer: str | None = None
    note: str | None = None


class LanguagesCfg(BaseModel):
    primary: list[str] = Field(default_factory=lambda: ["en", "hi"])
    regional: str | None = None


class InventoryRef(BaseModel):
    name: str
    url: str | None = None
    note: str | None = None


class CityConfig(BaseModel):
    name: str
    slug: str
    tier: str = "standard"  # deep | standard | config_only
    tz: str = "Asia/Kolkata"
    utm_epsg: int
    bbox: list[float]  # [min_lon, min_lat, max_lon, max_lat]
    centroid: list[float]  # [lat, lon]
    wards: WardsCfg
    firms_country: str = "IND"
    station_match: dict[str, int] = Field(default_factory=dict)
    openaq_location_ids: list[int] = Field(default_factory=list)
    # US Diplomatic Post / other independent reference stations. Models must NEVER
    # train on these; they are a blind validation set (spec 15.3).
    independent_holdout: list[int] = Field(default_factory=list)
    languages: LanguagesCfg = Field(default_factory=LanguagesCfg)
    inventory_refs: list[InventoryRef] = Field(default_factory=list)

    @property
    def bbox_tuple(self) -> BBox:
        return (self.bbox[0], self.bbox[1], self.bbox[2], self.bbox[3])

    @property
    def centroid_latlon(self) -> tuple[float, float]:
        return (self.centroid[0], self.centroid[1])


def load_city(slug: str) -> CityConfig:
    path = CITIES_DIR / f"{slug}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No city config at {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return CityConfig(**data)


def all_slugs() -> list[str]:
    if not CITIES_DIR.exists():
        return []
    return sorted(p.stem for p in CITIES_DIR.glob("*.yaml"))


def resolve_cities(arg: str) -> list[str]:
    """Expand a ``--city`` argument to a list of slugs. 'all' => every config."""
    if arg.strip().lower() == "all":
        slugs = all_slugs()
        if not slugs:
            raise ValueError("No city configs found in config/cities/")
        return slugs
    slug = arg.strip().lower()
    if not (CITIES_DIR / f"{slug}.yaml").exists():
        raise ValueError(f"Unknown city '{slug}'. Known: {', '.join(all_slugs())}")
    return [slug]
