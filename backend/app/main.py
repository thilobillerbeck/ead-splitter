from ics import Calendar
from requests import get
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import json

app = FastAPI()

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
        "name": "Wertsto[ffe",
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


@app.get("/api/meta")
async def meta(request: Request, response_class=JSONResponse):
    return {
        "streets": json.loads(
            get(
                "https://ead.darmstadt.de/unser-angebot/privathaushalte/abfallkalender/getStreets/?type=742394"
            ).text
        ),
        "disposal_types": disposal_types,
    }


@app.get("/api/download")
async def download(
    street: str = "Arheilger Straße 1-83, 2-94",
    chosenTypes: str = "PPK,BIO,WET,RM1,RM2,RM4",
    weekModulo: int = 9,
    parties: int = 12,
):
    print(
        f"street: {street}, chosenTypes: {chosenTypes}, weekModulo: {weekModulo}, parties: {parties}"
    )

    def get_week_number(date):
        return date.isocalendar()[1]

    chosenTypesQuery = "&".join([f"chosenTypes[]={t}" for t in chosenTypes.split(",")])

    url = f"https://ead.darmstadt.de/unser-angebot/privathaushalte/abfallkalender/downloadIcs/?type=742394&street={street}&{chosenTypesQuery}"

    c = Calendar(get(url).text)

    c_res = Calendar()

    c_res.extra.name = f"Abfall {street} {weekModulo}_{parties}"
    for event in c.events:
        print(
            f"a: {get_week_number(event.begin) % parties}, b: {weekModulo}, c: {get_week_number(event.begin)}"
        )
        if get_week_number(event.begin) % parties == (weekModulo % parties):
            c_res.events.add(event)

    serial = [
        line for line in c_res.serialize().split("\n") if not line.startswith("UID")
    ]

    for i, line in enumerate(serial):
        if "SUMMARY" in line:
            line = line.replace("\\", "")
            line = line.split(" ")[0]
            if "PPK" in line:
                line = line.replace("PPK", "Papiermüll")
            if "BIO" in line:
                line = line.replace("BIO", "Bioabfall")
            if "WET" in line:
                line = line.replace("WET", "Wertstoffe")
            if "RM1" in line:
                line = line.replace("RM1", "Restmüll-1")
            if "RM2" in line:
                line = line.replace("RM2", "Restmüll-2")
            if "RM4" in line:
                line = line.replace("RM4", "Restmüll-4")
        line = line.replace(",", ", ")
        serial[i] = line

    streetNameSnake = (
        street.replace(" ", "_")
        .replace(",", "")
        .replace("-", "_")
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )

    return PlainTextResponse(
        content="\n".join(serial),
        media_type="text/calendar",
        headers={
            "Content-Disposition": f"attachment; filename=eadsplitter-{streetNameSnake}-{weekModulo}_{parties}-cal.ics"
        },
    )
