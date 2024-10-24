from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import requests
import json
import google.auth
import google.auth.exceptions
from google.auth.transport.requests import Request as GoogleRequest
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn")


def get_current_project():
    try:
        _, project_id = google.auth.default()
        if not project_id:
            raise Exception(
                "Failed to get current project from Google Cloud credentials"
            )
        return project_id
    except google.auth.exceptions.DefaultCredentialsError as ex:
        raise Exception(f"Error obtaining default credentials: {str(ex)}")


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.api_route("/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def proxy(path: str, request: Request):
    path_parts = path.split("/", 1)
    if path_parts[0] == "api":
        project_id = get_current_project()
        api_path = path
    else:
        project_id = path_parts[0]
        api_path = path_parts[1] if len(path_parts) > 1 else ""

    logger.info(f"Using Project ID: {project_id}")

    GOOGLE_PROM_URL = f"https://monitoring.googleapis.com/v1/projects/{project_id}/location/global/prometheus"

    credentials, _ = google.auth.default()
    credentials.refresh(GoogleRequest())

    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
    }

    params = {k: v for k, v in request.query_params.items() if k != "refresh"}

    if request.method == "GET":
        resp = requests.get(
            f"{GOOGLE_PROM_URL}/{api_path}", headers=headers, params=params
        )
    elif request.method == "POST":
        data = await request.json()
        data.pop("refresh", None)
        resp = requests.post(
            f"{GOOGLE_PROM_URL}/{api_path}", headers=headers, json=data
        )

    excluded_headers = [
        "content-encoding",
        "content-length",
        "transfer-encoding",
        "connection",
    ]
    headers = [
        (name, value)
        for (name, value) in resp.raw.headers.items()
        if name.lower() not in excluded_headers
    ]

    return Response(
        content=resp.content, status_code=resp.status_code, headers=dict(headers)
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8082)
