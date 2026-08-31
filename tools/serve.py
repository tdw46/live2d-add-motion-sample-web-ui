#!/usr/bin/env python3
"""Serve the WebUI and its local-only avatar generation API."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 17342
PROJECT_ROOT = Path(__file__).resolve().parent.parent
HALLWAY_ENV = Path(
    os.environ.get(
        "LIVE2D_HALLWAY_ENV",
        "/Users/tylerwalker/dev/Hallway/hallway-anime-facial-landmark-classifier/.env",
    )
)
REGISTRY_PATH = PROJECT_ROOT / "local-assets" / "avatar-registry.json"
GENERATED_ROOT = PROJECT_ROOT / "local-assets" / "generated-avatars"
PIPELINE_PYTHON = PROJECT_ROOT / ".venv-avatar" / "bin" / "python"
SEE_THROUGH = PROJECT_ROOT / "vendor" / "see-through"
IMAGE2LIVE2D = PROJECT_ROOT / "vendor" / "image2live2d"
MAX_BODY_BYTES = 32_768

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
REGISTRY_LOCK = threading.Lock()
EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="avatar-generation")


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def hallway_settings() -> dict[str, str]:
    values = load_dotenv(HALLWAY_ENV)
    for key in ("GEMINI_API_KEY", "GEMINI_IMAGE_MODEL", "GEMINI_IMAGE_FALLBACK_MODEL"):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def default_avatar() -> dict:
    config_path = PROJECT_ROOT / "model.config.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        model3 = config["model3"]
    else:
        model3 = "models/hiyori_pro_t11/hiyori_pro_t11.model3.json"
    return {
        "id": "hiyori",
        "name": "Hiyori",
        "model3": model3,
        "default": True,
        "generated": False,
    }


def read_generated_avatars() -> list[dict]:
    if not REGISTRY_PATH.is_file():
        return []
    try:
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    avatars = payload.get("avatars", []) if isinstance(payload, dict) else []
    clean = []
    for avatar in avatars:
        if not isinstance(avatar, dict):
            continue
        model3 = str(avatar.get("model3", ""))
        if model3 and (PROJECT_ROOT / model3).is_file():
            clean.append(avatar)
    clean.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return clean


def avatar_catalog() -> list[dict]:
    return [default_avatar(), *read_generated_avatars()]


def register_avatar(avatar: dict) -> None:
    with REGISTRY_LOCK:
        existing = [item for item in read_generated_avatars() if item.get("id") != avatar.get("id")]
        payload = {"version": 1, "avatars": [avatar, *existing]}
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp_path = REGISTRY_PATH.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temp_path.replace(REGISTRY_PATH)


def pipeline_status() -> dict:
    settings = hallway_settings()
    return {
        "gemini_configured": bool(settings.get("GEMINI_API_KEY")),
        "environment_ready": PIPELINE_PYTHON.is_file(),
        "see_through_ready": (SEE_THROUGH / "inference" / "scripts" / "inference_psd.py").is_file(),
        "rig_bridge_ready": (IMAGE2LIVE2D / "src" / "image2live2d").is_dir(),
        "profile": os.environ.get("SEE_THROUGH_PROFILE", "mps-smoke"),
    }


def update_job(job_id: str, **changes) -> None:
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(changes)
            JOBS[job_id]["updated_at"] = datetime.now(timezone.utc).isoformat()


def public_job(job: dict) -> dict:
    return {key: value for key, value in job.items() if key not in {"description", "work_dir"}}


def _gemini_models(settings: dict[str, str]) -> list[str]:
    candidates = [
        settings.get("GEMINI_IMAGE_MODEL", ""),
        settings.get("GEMINI_IMAGE_FALLBACK_MODEL", ""),
        "gemini-3.1-flash-image-preview",
        "gemini-3-pro-image-preview",
        "gemini-2.5-flash-image",
    ]
    result = []
    for model in candidates:
        model = model.strip()
        if model and model not in result:
            result.append(model)
    return result


def _extract_gemini_image(response: dict) -> tuple[bytes, str] | None:
    for candidate in response.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if not isinstance(inline, dict) or not inline.get("data"):
                continue
            return base64.b64decode(inline["data"]), str(
                inline.get("mimeType") or inline.get("mime_type") or "image/png"
            )
    return None


def _gemini_request(url: str, payload: dict) -> dict:
    request = urllib_request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=240) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        detail = ""
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            detail = str(body.get("error", {}).get("message", ""))
        except Exception:
            pass
        raise RuntimeError(f"Gemini request failed with HTTP {exc.code}: {detail or exc.reason}") from None
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Gemini connection failed: {exc.reason}") from None


def generate_character_image(description: str, settings: dict[str, str]) -> tuple[bytes, str, str]:
    api_key = settings.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in the Hallway .env file.")
    prompt = (
        "Create one polished anime character concept intended for automatic Live2D rigging. "
        "Show the complete body from the top of the hair to the soles of both shoes, centered with generous "
        "empty margin on a plain flat light-gray background. Use a straight-on orthographic view, neutral "
        "upright standing pose, arms relaxed slightly away from the torso, hands visible, legs separated, both "
        "eyes open, and a closed neutral mouth. Keep the silhouette, facial features, hair sections, clothing, "
        "hands, and feet clean and unobstructed. Use crisp professional anime key art, flat even lighting, clean "
        "edges, and no cast shadows, props, text, scenery, extra people, cropped limbs, foreshortening, side view, "
        "or dramatic pose. Character description: " + description.strip()
    )
    attempts = [
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": "3:4", "imageSize": "1K"},
            },
        },
        {
            "contents": [{"parts": [{"text": prompt + " Return only one image."}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        },
    ]
    errors = []
    for model in _gemini_models(settings):
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{urllib_parse.quote(model, safe='')}:generateContent?key={urllib_parse.quote(api_key)}"
        )
        for payload in attempts:
            try:
                result = _gemini_request(url, payload)
                image = _extract_gemini_image(result)
                if image:
                    return image[0], image[1], model
                errors.append(f"{model}: no image returned")
            except RuntimeError as exc:
                errors.append(f"{model}: {exc}")
    raise RuntimeError(errors[-1] if errors else "Gemini did not return an image.")


def _friendly_name(description: str, fallback: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", description)
    if words:
        return " ".join(words[:4]).title()
    return " ".join(description.split())[:28] or fallback


def _run_checked(command: list[str], *, cwd: Path) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        tail = "\n".join(result.stdout.splitlines()[-30:])
        raise RuntimeError(tail or f"Command exited with status {result.returncode}")
    return result.stdout


def select_semantic_psd(output_root: Path, source_stem: str) -> Path:
    """Return See-through's color-layer PSD, never its depth/debug PSDs."""
    psd_files = sorted(output_root.rglob("*.psd"))
    semantic_psds = [
        path
        for path in psd_files
        if not path.stem.casefold().endswith(("_depth", "_wdepth"))
    ]
    exact_matches = [path for path in semantic_psds if path.stem == source_stem]
    if len(exact_matches) == 1:
        return exact_matches[0]

    metadata_matches = [
        path for path in semantic_psds if Path(f"{path}.json").is_file()
    ]
    if len(metadata_matches) == 1:
        return metadata_matches[0]

    if not semantic_psds:
        raise RuntimeError(
            "See-through completed without producing a semantic color-layer PSD."
        )
    choices = ", ".join(path.relative_to(output_root).as_posix() for path in semantic_psds)
    raise RuntimeError(f"See-through produced ambiguous semantic PSD outputs: {choices}")


def run_avatar_job(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id].copy()
    description = job["description"]
    work_dir = Path(job["work_dir"])
    try:
        ready = pipeline_status()
        missing = [key for key, value in ready.items() if key.endswith("_ready") and not value]
        if missing:
            raise RuntimeError("Avatar environment is not ready. Run python3 tools/setup_avatar_pipeline.py first.")

        work_dir.mkdir(parents=True, exist_ok=False)
        settings = hallway_settings()
        update_job(job_id, phase="gemini", message="Creating a front-facing full-body concept with Gemini…")
        image_bytes, image_mime, gemini_model = generate_character_image(description, settings)
        extension = mimetypes.guess_extension(image_mime.split(";", 1)[0]) or ".png"
        if extension == ".jpe":
            extension = ".jpg"
        source_path = work_dir / f"source{extension}"
        source_path.write_bytes(image_bytes)
        source_url = f"/local-assets/generated-avatars/{job_id}/{source_path.name}"
        update_job(
            job_id,
            source_url=source_url,
            gemini_model=gemini_model,
            phase="seethrough",
            message="Separating the artwork into semantic layers with See-through on Metal…",
        )

        profile = os.environ.get("SEE_THROUGH_PROFILE", "mps-smoke")
        see_output = work_dir / "see-through"
        _run_checked(
            [
                str(PIPELINE_PYTHON),
                str(PROJECT_ROOT / "tools" / "run_seethrough.py"),
                str(source_path),
                "--profile",
                profile,
                "--output",
                str(see_output),
            ],
            cwd=PROJECT_ROOT,
        )
        psd_path = select_semantic_psd(see_output, source_path.stem)

        update_job(
            job_id,
            phase="rigging",
            message="Building meshes, deformations, physics, motions, and the Live2D bundle…",
        )
        model_name = f"avatar_{job_id.replace('-', '_')}"
        live2d_dir = work_dir / "live2d"
        output = _run_checked(
            [
                str(PIPELINE_PYTHON),
                str(PROJECT_ROOT / "tools" / "rig_avatar.py"),
                str(psd_path),
                "--output",
                str(live2d_dir),
                "--name",
                model_name,
            ],
            cwd=PROJECT_ROOT,
        )
        result_line = next((line for line in reversed(output.splitlines()) if line.startswith("{")), "{}")
        rig_result = json.loads(result_line)
        model3_path = Path(rig_result.get("model3", ""))
        if not model3_path.is_file():
            raise RuntimeError("The rigging bridge did not produce a loadable .model3.json bundle.")
        relative_model3 = model3_path.resolve().relative_to(PROJECT_ROOT).as_posix()
        avatar = {
            "id": job_id,
            "name": _friendly_name(description, f"Generated {job_id[-6:]}"),
            "model3": relative_model3,
            "preview": source_url,
            "default": False,
            "generated": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "gemini_model": gemini_model,
            "see_through_profile": profile,
            "qa_passed": bool(rig_result.get("qa_passed")),
        }
        register_avatar(avatar)
        update_job(
            job_id,
            phase="complete",
            message="Avatar ready — loading the new Live2D model…",
            avatar=avatar,
        )
    except Exception as exc:
        update_job(job_id, phase="failed", message="Avatar generation stopped.", error=str(exc))


class AppHandler(SimpleHTTPRequestHandler):
    server_version = "Live2DLocal/1.0"

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urllib_parse.urlsplit(self.path).path
        if path == "/api/avatars":
            self.send_json({"avatars": avatar_catalog(), "pipeline": pipeline_status()})
            return
        match = re.fullmatch(r"/api/avatar-jobs/([A-Za-z0-9_-]+)", path)
        if match:
            with JOBS_LOCK:
                job = JOBS.get(match.group(1))
                payload = public_job(job.copy()) if job else None
            if payload is None:
                self.send_json({"error": "Avatar job not found."}, status=404)
            else:
                self.send_json(payload)
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urllib_parse.urlsplit(self.path).path
        if path != "/api/avatars/generate":
            self.send_json({"error": "Not found."}, status=404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            self.send_json({"error": "Request body is empty or too large."}, status=400)
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json({"error": "Request body must be valid JSON."}, status=400)
            return
        description = str(payload.get("description", "")).strip()
        if len(description) < 3:
            self.send_json({"error": "Please provide a fuller character description."}, status=400)
            return
        if len(description) > 1200:
            self.send_json({"error": "Character description is too long."}, status=400)
            return
        readiness = pipeline_status()
        if not readiness["gemini_configured"]:
            self.send_json({"error": "Gemini is not configured in the Hallway .env file."}, status=503)
            return
        if not all(readiness[key] for key in ("environment_ready", "see_through_ready", "rig_bridge_ready")):
            self.send_json(
                {"error": "Avatar environment is not ready. Run python3 tools/setup_avatar_pipeline.py."},
                status=503,
            )
            return

        job_id = f"gen-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc).isoformat()
        job = {
            "id": job_id,
            "phase": "queued",
            "message": "Avatar generation queued…",
            "description": description,
            "work_dir": str(GENERATED_ROOT / job_id),
            "created_at": now,
            "updated_at": now,
        }
        with JOBS_LOCK:
            JOBS[job_id] = job
        EXECUTOR.submit(run_avatar_job, job_id)
        self.send_json({"job_id": job_id, "phase": "queued"}, status=202)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Live2D motion WebUI")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    os.chdir(PROJECT_ROOT)
    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f"Live2D WebUI: http://localhost:{args.port}", flush=True)
    print("Avatar pipeline: " + json.dumps(pipeline_status(), sort_keys=True), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        EXECUTOR.shutdown(wait=False, cancel_futures=True)
        server.server_close()


if __name__ == "__main__":
    main()
