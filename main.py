from flask import Flask, request, Response
from flask_cors import CORS
import requests
import json
import subprocess
import google.auth
import google.auth.exceptions
from google.auth.transport.requests import Request
import logging


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


def create_app():
    app = Flask(__name__)
    CORS(app)

    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = app.logger

    @app.route("/<path:path>", methods=["GET", "POST", "OPTIONS"])
    def proxy(path):
        # Extract the first element of the path
        path_parts = path.split("/", 1)
        if path_parts[0] == "api":
            project_id = get_current_project()
            api_path = path
        else:
            project_id = path_parts[0]
            api_path = path_parts[1] if len(path_parts) > 1 else ""

        # Log the project ID
        logger.info(f"Using Project ID: {project_id}")

        GOOGLE_PROM_URL = f"https://monitoring.googleapis.com/v1/projects/{project_id}/location/global/prometheus"

        # Ensure the credentials are valid
        credentials, _ = google.auth.default()
        credentials.refresh(Request())

        headers = {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json",
        }

        # Filter out unsupported parameters
        params = {k: v for k, v in request.args.items() if k not in ["refresh"]}

        if request.method == "GET":
            resp = requests.get(
                f"{GOOGLE_PROM_URL}/{api_path}", headers=headers, params=params
            )
        elif request.method == "POST":
            # Parse the request body
            data = json.loads(request.data)
            # Remove unsupported fields
            if "refresh" in data:
                del data["refresh"]
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

        return Response(resp.content, resp.status_code, headers)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(port=8082)
