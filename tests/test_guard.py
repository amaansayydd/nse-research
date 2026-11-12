from datetime import date, timedelta

import pytest

from nsr import config, parse
from nsr.download import raw_path


def test_holdout_dates_are_refused(monkeypatch):
    monkeypatch.delenv(config.PRODUCTION_ENV, raising=False)
    for d in (config.HOLDOUT_START, config.HOLDOUT_END, date(2026, 6, 1)):
        with pytest.raises(config.HoldoutViolation):
            config.assert_readable(d)
        with pytest.raises(config.HoldoutViolation):
            parse.open_pr(d)
        with pytest.raises(config.HoldoutViolation):
            parse.parse_mto(d)


def test_research_and_forward_dates_are_allowed(monkeypatch):
    monkeypatch.delenv(config.PRODUCTION_ENV, raising=False)
    config.assert_readable(config.HOLDOUT_START - timedelta(days=1))
    config.assert_readable(config.HOLDOUT_END + timedelta(days=1))


def test_production_flag_is_the_only_way_in(monkeypatch):
    monkeypatch.setenv(config.PRODUCTION_ENV, "1")
    config.assert_readable(config.HOLDOUT_START)


def test_holdout_files_live_outside_the_project():
    p = raw_path("pr", date(2026, 3, 2))
    assert config.PROJECT not in p.parents
    assert config.HOLDOUT_DIR in p.parents
    assert config.PROJECT in raw_path("pr", date(2025, 11, 11)).parents


def test_misfiled_bundle_is_detected():
    # NSE serves 02-Jan-2019 data under PR020118.zip
    assert parse.inner_date_matches("Pd020118.csv", date(2018, 1, 2))
    assert parse.inner_date_matches("nupr100113/Pd100113.csv", date(2013, 1, 10))
    assert parse.inner_date_matches("pd03112025.csv", date(2025, 11, 3))
    assert not parse.inner_date_matches("Pd020119.csv", date(2018, 1, 2))
    assert not parse.inner_date_matches("Pd040624.csv", date(2024, 4, 6))
