import logging
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pypdf.errors import PyPdfError
from starlette.background import BackgroundTask

from a6_booklet import INPUT_FORMATS, ISO_A_MM, make_booklet

app = FastAPI(title="PDF Booklet Imposer", version="1.0.0")
logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "95")) * 1024 * 1024


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/formats")
def formats():
    return {
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "formats": [
            {"input": name, "input_mm": ISO_A_MM[name],
             "sheet": f"A{int(name[1:]) - 1}",
             "sheet_mm": list(reversed(ISO_A_MM[f"A{int(name[1:]) - 1}"]))}
            for name in INPUT_FORMATS
        ],
    }


@app.post("/api/booklet", response_class=FileResponse)
def convert(file: UploadFile, page_format: str = Query("A6")):
    if page_format not in INPUT_FORMATS:
        raise HTTPException(422, "Choose a page format from A1 to A10.")

    temporary = TemporaryDirectory(prefix="booklet-")
    try:
        source = Path(temporary.name) / "source.pdf"
        output = Path(temporary.name) / "booklet.pdf"
        size = 0
        with source.open("wb") as target:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, f"Choose a PDF smaller than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
                target.write(chunk)
        with source.open("rb") as uploaded:
            if b"%PDF-" not in uploaded.read(1024):
                raise HTTPException(422, "Choose a valid PDF file.")
        try:
            sheets, blanks = make_booklet(source, output, page_format)
        except (ValueError, PyPdfError) as error:
            raise HTTPException(422, str(error) or "This PDF could not be read. Try exporting it again.") from error
        except Exception as error:
            logger.exception("PDF conversion failed")
            raise HTTPException(422, "This PDF could not be converted. Try exporting it again.") from error

        original = (file.filename or "document.pdf").replace("\\", "/").split("/")[-1]
        stem = re.sub(r"[\x00-\x1f\x7f]", "", Path(original).stem)[:120] or "document"
        sheet_format = f"A{int(page_format[1:]) - 1}"
        filename = f"{stem}-booklet-{sheet_format}.pdf"
        return FileResponse(
            output, media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
                "X-Booklet-Sheets": str(sheets), "X-Booklet-Blanks": str(blanks),
                "X-Booklet-Pages": str(sheets * 4 - blanks),
                "Cache-Control": "no-store",
            },
            background=BackgroundTask(temporary.cleanup),
        )
    except BaseException:
        temporary.cleanup()
        raise
    finally:
        file.file.close()
