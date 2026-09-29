"""Allowlisted public APIs that require no API key.

These are read-only integrations. Endpoints are intentionally allowlisted so the
agent cannot turn this helper into an arbitrary outbound HTTP client.
"""
import json
import urllib.parse
import urllib.request


PUBLIC_APIS = {
    "jina_reader": "https://r.jina.ai/http://{url}",
    "hackernews_top": "https://hacker-news.firebaseio.com/v0/topstories.json",
    "hackernews_item": "https://hacker-news.firebaseio.com/v0/item/{id}.json",
    "nominatim_search": "https://nominatim.openstreetmap.org/search?format=jsonv2&q={query}",
    "ip_api": "http://ip-api.com/json/{ip}",
    "open_meteo": "https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,wind_speed_10m&forecast_days=1",
    "rest_countries": "https://restcountries.com/v3.1/name/{name}",
    "dictionary": "https://api.dictionaryapi.dev/api/v2/entries/en/{word}",
    "qr_code": "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={data}",
    "random_user": "https://randomuser.me/api/?results={results}",
    "jsonplaceholder": "https://jsonplaceholder.typicode.com/{resource}",
    "pokeapi": "https://pokeapi.co/api/v2/{resource}",
    "joke": "https://v2.jokeapi.dev/joke/Any?safe-mode",
    "open_library": "https://openlibrary.org/search.json?q={query}",
    "iss_location": "http://api.open-notify.org/iss-now.json",
    "clearbit_logo": "https://logo.clearbit.com/{domain}",
}


class PublicAPIs:
    """Small, read-only client for verified no-key public APIs."""

    def __init__(self, activity=None, timeout=20):
        self.activity = activity
        self.timeout = int(timeout)

    def call(self, api, **params):
        if api not in PUBLIC_APIS:
            raise ValueError("Unsupported public API: " + str(api))
        template = PUBLIC_APIS[api]
        try:
            url = template.format(**{k: urllib.parse.quote(str(v), safe="") for k, v in params.items()})
        except KeyError as exc:
            raise ValueError("Missing parameter: " + str(exc.args[0]))
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "HariomAI/1.0 public-api-client"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
        if self.activity:
            self.activity.emit("PUBLIC API -> " + api)
        if "image/" in content_type:
            return {"api": api, "content_type": content_type, "bytes": len(body), "data": body}
        try:
            return {"api": api, "content_type": content_type, "data": json.loads(body.decode("utf-8"))}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"api": api, "content_type": content_type, "data": body.decode("utf-8", errors="replace")}
