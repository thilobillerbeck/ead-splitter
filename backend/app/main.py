import json
import unicodedata
import uuid
from datetime import date

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from ics import Calendar, Event
from requests import RequestException, get, post

app = FastAPI()

REQUEST_TIMEOUT = 10
API_BASE_URL = "https://ead.darmstadt.de/unser-angebot/privathaushalte/abfallkalender"
DEFAULT_STREET = "Arheilger Straße 1-83, 2-94"

disposal_types = [
    {
        "name": "Papiermüll",
        "color": "#41b06b",
        "short": "PPK",
    },
    {
        "name": "Bioabfall",
        "color": "#bb635d",
        "short": "BIO",
    },
    {
        "name": "Wertstoffe",
        "color": "#f4e834",
        "short": "WET",
    },
    {
        "name": "Restmüll-1",
        "color": "#ffffff",
        "short": "RM1",
    },
    {
        "name": "Restmüll-2",
        "color": "#f28c00",
        "short": "RM2",
    },
    {
        "name": "Restmüll-4",
        "color": "#e3000f",
        "short": "RM4",
    },
]

app.mount("/static", StaticFiles(directory="app/frontend/static"), name="static")


@app.get("/")
async def root():
    return FileResponse("app/frontend/index.html")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


def fetch_schedule(street: str) -> dict[date, list[str]]:
    """Pickup dates of a street as {date: [type codes]}, from EAD's singleStreet API.

    EAD answers with {"02.01.2026": ["WET"], ...} and with [] for unknown streets.
    """
    try:
        response = post(
            f"{API_BASE_URL}/singleStreet/?type=742394",
            data={"street": street},
            timeout=REQUEST_TIMEOUT,
        )
        raw = json.loads(response.text)
    except (RequestException, ValueError) as e:
        raise HTTPException(status_code=502, detail="EAD API unavailable") from e
    if not isinstance(raw, dict):
        return {}
    return {
        date(*map(int, reversed(day.split(".")))): codes for day, codes in raw.items()
    }


@app.get("/api/meta")
def meta(request: Request, response_class=JSONResponse):
    try:
        streets = json.loads(
            get(f"{API_BASE_URL}/getStreets/?type=742394", timeout=REQUEST_TIMEOUT).text
        )
    except (RequestException, ValueError) as e:
        raise HTTPException(status_code=502, detail="EAD service unavailable") from e
    available_years = sorted({str(day.year) for day in fetch_schedule(DEFAULT_STREET)})
    return {
        "streets": streets,
        "disposal_types": disposal_types,
        "years": available_years,
    }


GERMAN_TRANSLITERATION = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }
)


def to_safe_filename(text: str, commas_only: bool = False) -> str:
    """Make `text` usable in a filename, e.g. "Müllerweg 1-5, 2-8" -> "Muellerweg_1-5_2-8".

    With `commas_only=True` the text is kept as is, except that commas are removed.
    """
    text_without_commas = text.replace(",", "")
    if commas_only:
        return text_without_commas

    with_underscores = "_".join(text_without_commas.split())
    transliterated = with_underscores.translate(GERMAN_TRANSLITERATION)
    pure_ascii = unicodedata.normalize("NFKD", transliterated)
    return pure_ascii.encode("ascii", "ignore").decode()


@app.get("/api/download")
def download(
    street: str = DEFAULT_STREET,
    chosenTypes: str = "PPK,BIO,WET,RM1,RM2,RM4",
    weekModulo: int = 9,
    parties: int = 12,
    year: int = 2025,
):
    street_filename = to_safe_filename(street)
    disposal_names = {t["short"]: t["name"] for t in disposal_types}
    disposal_chosen = set(chosenTypes.split(","))

    schedule = fetch_schedule(street)
    if not any(day.year == year for day in schedule):
        raise HTTPException(
            status_code=404, detail=f"No schedule for '{street}' in {year}"
        )

    calendar = Calendar()
    for day, codes in sorted(schedule.items()):
        if day.year != year or day.isocalendar()[1] % parties != weekModulo % parties:
            continue
        for code in codes:
            if code not in disposal_chosen or code not in disposal_names:
                continue
            event = Event(name=disposal_names[code], begin=day)
            event.make_all_day()
            event.description = f"Abholung {disposal_names[code]}"
            event.location = street
            event.uid = str(uuid.uuid4())
            calendar.events.add(event)

    return PlainTextResponse(
        content=calendar.serialize().replace("\r\n", "\n").rstrip("\n") + "\n",
        media_type="text/calendar",
        headers={
            "Content-Disposition": f"attachment; filename=eadsplitter-{street_filename}-{weekModulo}_{parties}-cal.ics"
        },
    )
