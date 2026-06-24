from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from carbot.storage.configs import Config


@dataclass
class Listing:
    source: str          # "autoru" | "avito"
    listing_id: str
    title: str
    price: Optional[int]
    year: Optional[int]
    mileage: Optional[int]
    url: str
    transmission: Optional[str] = None
    engine_type: Optional[str] = None
    displacement: Optional[float] = None  # litres
    color: Optional[str] = None
    owners_count: Optional[int] = None
    gear_type: Optional[str] = None
    location: Optional[str] = None
    photo_url: Optional[str] = None
    extra: dict = field(default_factory=dict)


class Scraper(ABC):
    source: str

    @abstractmethod
    async def search(self, config: Config) -> list[Listing]:
        ...
