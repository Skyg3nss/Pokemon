import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps

from pokemon_card_recognizer.api.card_recognizer import CardRecognizer, OperatingMode


APP_NAME = "Chaos Chaser Scanner API"
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_SIDE = 1800

app = FastAPI(title=APP_NAME, version="1.0.0")

# For the test phase we allow the Netlify app + localhost.
# Once your final Netlify URL is known, we can tighten this.
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "*"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins != ["*"] else ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_recognizer: Optional[CardRecognizer] = None
_recognizer_error: Optional[str] = None


def get_recognizer() -> CardRecognizer:
    global _recognizer, _recognizer_error

    if _recognizer is not None:
        return _recognizer

    if _recognizer_error:
        raise RuntimeError(_recognizer_error)

    try:
        # "master" uses the package's bundled prebuilt references.
        _recognizer = CardRecognizer(
            mode=OperatingMode.SINGLE_IMAGE,
            set_name="master",
        )
        return _recognizer
    except Exception as exc:
        _recognizer_error = f"Recognizer init failed: {exc}"
        raise


def normalize_uploaded_image(raw_path: Path) -> Path:
    try:
        with Image.open(raw_path) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")

            width, height = img.size
            longest = max(width, height)

            if longest > MAX_SIDE:
                scale = MAX_SIDE / longest
                img = img.resize(
                    (max(1, int(width * scale)), max(1, int(height * scale))),
                    Image.Resampling.LANCZOS,
                )

            out = raw_path.with_suffix(".jpg")
            img.save(out, "JPEG", quality=92, optimize=True)
            return out
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image: {exc}")


@app.get("/")
def root():
    return {
        "ok": True,
        "service": APP_NAME,
        "message": "Scanner API is online.",
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": APP_NAME,
        "recognizer_loaded": _recognizer is not None,
        "recognizer_error": _recognizer_error,
    }


@app.post("/recognize")
async def recognize_card(image: UploadFile = File(...)):
    content_type = (image.content_type or "").lower()

    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Upload must be an image."
        )

    raw = await image.read()

    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload.")

    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Image is too large. Maximum is 8 MB."
        )

    suffix = Path(image.filename or "scan.jpg").suffix or ".jpg"

    with tempfile.TemporaryDirectory(prefix="chaos_scan_") as tmpdir:
        tmpdir = Path(tmpdir)
        raw_path = tmpdir / f"upload{suffix}"
        raw_path.write_bytes(raw)

        normalized_path = normalize_uploaded_image(raw_path)

        try:
            recognizer = get_recognizer()

            pred_result = recognizer.exec(str(normalized_path))

            if not pred_result:
                return JSONResponse(
                    status_code=404,
                    content={
                        "ok": False,
                        "error": "No card recognized.",
                    },
                )

            # The project docs use pred_result[0] for SINGLE_IMAGE.
            prediction = pred_result[0]

            detected = recognizer.classifier.reference.lookup_card_prediction(
                card_prediction=prediction
            )

            if detected is None:
                return JSONResponse(
                    status_code=404,
                    content={
                        "ok": False,
                        "error": "Prediction returned but no card metadata matched.",
                    },
                )

            result = {
                "ok": True,
                "card": {
                    "set": getattr(detected, "set", None),
                    "name": getattr(detected, "name", None),
                    "number": getattr(detected, "number", None),
                },
                "raw_prediction": str(prediction),
            }

            return result

        except HTTPException:
            raise
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "error": "Recognition failed.",
                    "detail": str(exc),
                },
            )


# Optional warmup endpoint.
# We intentionally do NOT auto-initialize on app startup because Render Free
# has limited RAM and cold starts. Hit /warmup manually if wanted.
@app.post("/warmup")
def warmup():
    try:
        get_recognizer()
        return {
            "ok": True,
            "recognizer_loaded": True,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
