import json
import re
from collections import Counter
from datetime import date
from types import SimpleNamespace

import pytest

from tests.conftest import SCHEDULE, STREETS, UNKNOWN_STREET

DEFAULT_STREET = "Arheilger Straße 1-83, 2-94"

GERMAN_NAMES = {
    "PPK": "Papiermüll",
    "BIO": "Bioabfall",
    "WET": "Wertstoffe",
    "RM1": "Restmüll-1",
    "RM2": "Restmüll-2",
    "RM4": "Restmüll-4",
}

PICKUPS_PER_TYPE = {"PPK": 26, "BIO": 37, "WET": 27, "RM1": 52, "RM2": 26, "RM4": 13}
TOTAL_PICKUPS = sum(PICKUPS_PER_TYPE.values())
BUSY_DAY = "30.04.2026"


def parse_ead_date(text: str) -> date:
    d, m, y = map(int, text.split("."))
    return date(y, m, d)


def summaries(ics: str) -> list[str]:
    return [
        line.removeprefix("SUMMARY:")
        for line in ics.splitlines()
        if line.startswith("SUMMARY")
    ]


def event_dates(ics: str) -> list[date]:
    return [
        date(int(m[:4]), int(m[4:6]), int(m[6:]))
        for m in re.findall(r"^DTSTART;VALUE=DATE:(\d{8})$", ics, re.MULTILINE)
    ]


def event_count(ics: str) -> int:
    return ics.count("BEGIN:VEVENT")


def download(client, **params):
    return client.get(
        "/api/download", params={"year": 2026, "weekModulo": 1, "parties": 1, **params}
    )


def test_snapshot_sanity():
    assert Counter(c for codes in SCHEDULE.values() for c in codes) == PICKUPS_PER_TYPE
    assert {parse_ead_date(d).year for d in SCHEDULE} == {2026}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


def test_root_serves_index(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "index" in r.text


def test_static_mount(client):
    assert client.get("/static/hello.txt").text == "static ok"


def test_meta(client, fake_ead):
    r = client.get("/api/meta")
    assert r.status_code == 200
    body = r.json()
    assert body["streets"] == STREETS
    assert [t["short"] for t in body["disposal_types"]] == list(GERMAN_NAMES)
    assert [t["name"] for t in body["disposal_types"]] == list(GERMAN_NAMES.values())
    assert fake_ead.get_calls[0]["timeout"]


def test_meta_years_come_from_the_published_data(client, fake_ead):
    assert client.get("/api/meta").json()["years"] == ["2026"]
    assert fake_ead.post_calls[0]["data"] == {"street": DEFAULT_STREET}


def test_meta_reports_upstream_outage(client, fake_ead):
    fake_ead.is_down = True
    assert client.get("/api/meta").status_code == 502


def test_download_headers_and_framing(client):
    r = download(client, weekModulo=1, parties=3)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    assert r.headers["content-disposition"] == (
        "attachment; filename=eadsplitter-Arheilger_Strasse_1-83_2-94-1_3-cal.ics"
    )
    assert r.text.startswith("BEGIN:VCALENDAR")
    assert r.text.endswith("END:VCALENDAR\n")


def test_download_asks_ead_for_the_street_schedule(client, fake_ead):
    download(client, street="Müllerweg 5")
    call = fake_ead.post_calls[-1]
    assert call["url"].endswith("/singleStreet/?type=742394")
    assert call["data"] == {"street": "Müllerweg 5"}
    assert call["timeout"]


def test_download_filename_transliterates_umlauts(client):
    r = download(client, street="Müllerweg 5")
    assert "eadsplitter-Muellerweg_5-" in r.headers["content-disposition"]


def test_default_includes_every_pickup_with_german_names(client):
    r = download(client)
    assert event_count(r.text) == TOTAL_PICKUPS
    assert Counter(summaries(r.text)) == Counter(
        {GERMAN_NAMES[c]: n for c, n in PICKUPS_PER_TYPE.items()}
    )


def test_event_fields(client):
    r = download(client, chosenTypes="PPK").text
    assert "DESCRIPTION:Abholung Papiermüll" in r
    assert "LOCATION:Arheilger Straße 1-83\\, 2-94" in r
    uids = [line for line in r.splitlines() if line.startswith("UID")]
    assert len(uids) == len(set(uids)) == PICKUPS_PER_TYPE["PPK"]


def test_events_fall_on_the_dates_ead_published(client):
    r = download(client, chosenTypes="PPK")
    expected = sorted(
        parse_ead_date(d) for d, codes in SCHEDULE.items() if "PPK" in codes
    )
    assert sorted(event_dates(r.text)) == expected


@pytest.mark.parametrize(("code", "name"), GERMAN_NAMES.items())
def test_single_disposal_type_only_keeps_that_type(client, code, name):
    r = download(client, chosenTypes=code)
    assert summaries(r.text) == [name] * PICKUPS_PER_TYPE[code]


def test_multiple_disposal_types(client):
    r = download(client, chosenTypes="PPK,WET")
    assert Counter(summaries(r.text)) == Counter(
        {"Papiermüll": PICKUPS_PER_TYPE["PPK"], "Wertstoffe": PICKUPS_PER_TYPE["WET"]}
    )


def test_combined_pickup_days_become_one_event_per_type(client):
    types_on_busy_day = SCHEDULE[BUSY_DAY]
    assert len(types_on_busy_day) > 1

    r = download(client)
    names_on_busy_day = [
        name
        for name, day in zip(summaries(r.text), event_dates(r.text), strict=True)
        if day == parse_ead_date(BUSY_DAY)
    ]
    assert sorted(names_on_busy_day) == sorted(
        GERMAN_NAMES[code] for code in types_on_busy_day
    )


def test_unknown_disposal_type_yields_valid_empty_calendar(client):
    r = download(client, chosenTypes="XYZ")
    assert r.status_code == 200
    assert event_count(r.text) == 0
    assert r.text.startswith("BEGIN:VCALENDAR")
    assert r.text.endswith("END:VCALENDAR\n")


@pytest.mark.parametrize("parties", [2, 3, 12])
def test_week_modulo_splits_pickups_between_parties(client, parties):
    per_party = [
        download(client, weekModulo=m, parties=parties) for m in range(1, parties + 1)
    ]
    events_across_all_parties = sum(event_count(r.text) for r in per_party)
    assert events_across_all_parties == TOTAL_PICKUPS
    for m, r in enumerate(per_party, start=1):
        weeks = {d.isocalendar()[1] % parties for d in event_dates(r.text)}
        assert weeks <= {m % parties}


def test_week_modulo_wraps_around_parties(client):
    a = download(client, weekModulo=1, parties=3)
    b = download(client, weekModulo=4, parties=3)
    assert sorted(event_dates(a.text)) == sorted(event_dates(b.text))


def test_disposal_types_combine_with_week_modulo(client):
    parties = 4
    results = [
        download(client, chosenTypes="PPK", weekModulo=m, parties=parties)
        for m in range(1, parties + 1)
    ]
    assert sum(event_count(r.text) for r in results) == PICKUPS_PER_TYPE["PPK"]
    assert all(set(summaries(r.text)) <= {"Papiermüll"} for r in results)


def test_year_without_data_is_not_found(client):
    for year in (2025, 2027):
        r = download(client, year=year)
        assert r.status_code == 404
        assert str(year) in r.json()["detail"]


def test_unknown_street_is_not_found(client):
    assert download(client, street=UNKNOWN_STREET).status_code == 404


def test_upstream_outage_is_reported(client, fake_ead):
    fake_ead.is_down = True
    assert download(client).status_code == 502


def test_real_street_list_shape():
    assert len(STREETS) > 1000
    assert all(isinstance(s, str) for s in STREETS)
    assert DEFAULT_STREET in STREETS


def test_filename_is_safe_for_every_real_street(app_module):
    unsafe = {
        street: name
        for street in STREETS
        if not re.fullmatch(
            r"[A-Za-z0-9_-]+", name := app_module.to_safe_filename(street)
        )
    }
    assert unsafe == {}


@pytest.mark.parametrize(
    "street",
    ["Kekuléstraße", "Ödenburger Straße", "Adelungstraße 1-41, 2-38", "Achatweg"],
)
def test_download_works_for_real_streets(client, fake_ead, street):
    r = download(client, street=street)
    assert r.status_code == 200
    r.headers["content-disposition"].encode("ascii")
    assert fake_ead.post_calls[-1]["data"] == {"street": street}


@pytest.mark.parametrize(
    ("text", "commas_only", "expected"),
    [
        ("Arheilger Straße 1-83, 2-94", False, "Arheilger_Strasse_1-83_2-94"),
        ("Über Größe", False, "Ueber_Groesse"),
        ("Hügel Öl", False, "Huegel_Oel"),
        ("Kekuléstraße", False, "Kekulestrasse"),
        ("a, b", True, "a b"),
        ("Müll  weg", True, "Müll  weg"),
    ],
)
def test_to_safe_filename(app_module, text, commas_only, expected):
    assert app_module.to_safe_filename(text, commas_only) == expected


def test_download_only_contains_the_requested_year(client, app_module, monkeypatch):
    two_years = {"30.12.2025": ["PPK"], "05.01.2026": ["PPK"], "04.01.2027": ["PPK"]}
    monkeypatch.setattr(
        app_module,
        "post",
        lambda url, **kwargs: SimpleNamespace(text=json.dumps(two_years)),
    )
    for year, expected in {
        2025: [date(2025, 12, 30)],
        2026: [date(2026, 1, 5)],
        2027: [date(2027, 1, 4)],
    }.items():
        assert event_dates(download(client, year=year).text) == expected
    assert client.get("/api/meta").json()["years"] == ["2025", "2026", "2027"]
