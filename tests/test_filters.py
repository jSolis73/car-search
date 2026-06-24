import pytest

from carbot.core.filters import apply_optional_filters
from carbot.scrapers.base import Listing
from carbot.storage.configs import Config


def _config(**opts) -> Config:
    return Config(
        id=1, brand="BMW", model="3ER",
        year_from=2018, year_to=2023,
        mileage_from=0, mileage_to=100_000,
        status="active", created_at="",
        optional_filters=opts,
    )


def _listing(**kwargs) -> Listing:
    defaults = dict(
        source="autoru", listing_id="1", title="BMW 3", url="https://example.com",
        price=1_000_000, year=2020, mileage=50_000,
        transmission="AUTOMATIC", engine_type="GASOLINE",
        displacement=2.0, owners_count=1, gear_type="REAR_DRIVE",
        location="Москва",
    )
    defaults.update(kwargs)
    return Listing(**defaults)


def test_no_filters_passes_all():
    cfg = _config()
    listings = [_listing(), _listing(listing_id="2")]
    assert apply_optional_filters(listings, cfg) == listings


def test_price_from_filter():
    cfg = _config(price_from=1_500_000)
    assert apply_optional_filters([_listing(price=1_000_000)], cfg) == []
    assert len(apply_optional_filters([_listing(price=1_600_000)], cfg)) == 1


def test_price_to_filter():
    cfg = _config(price_to=900_000)
    assert apply_optional_filters([_listing(price=1_000_000)], cfg) == []
    assert len(apply_optional_filters([_listing(price=800_000)], cfg)) == 1


def test_owners_count_filter():
    cfg = _config(owners_count=1)
    assert apply_optional_filters([_listing(owners_count=2)], cfg) == []
    assert len(apply_optional_filters([_listing(owners_count=1)], cfg)) == 1


def test_displacement_filter():
    cfg = _config(displacement_from=1.5, displacement_to=2.0)
    assert apply_optional_filters([_listing(displacement=1.2)], cfg) == []
    assert apply_optional_filters([_listing(displacement=2.5)], cfg) == []
    assert len(apply_optional_filters([_listing(displacement=1.8)], cfg)) == 1


def test_region_filter():
    cfg = _config(region="Москва")
    assert apply_optional_filters([_listing(location="Санкт-Петербург")], cfg) == []
    assert len(apply_optional_filters([_listing(location="Москва, ЦАО")], cfg)) == 1


def test_none_values_skip_filter():
    cfg = _config(price_from=500_000, owners_count=1)
    # price=None → not filtered out (we can't compare)
    result = apply_optional_filters([_listing(price=None)], cfg)
    assert len(result) == 1
