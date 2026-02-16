from dataclasses import dataclass


@dataclass
class Listing:
    title: str
    price: str
    sqft: str
    address: str
    link: str
    source: str
    lat: float | None = None
    lng: float | None = None
    full_text: str = ""

    @property
    def unique_key(self) -> str:
        return self.link
