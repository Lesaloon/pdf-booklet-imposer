# PDF Booklet Imposer

Turn a portrait PDF into a print-ready, left-bound folded booklet. Select an ISO A-series page size, upload a PDF in reading order, and download the imposed sheets.

Built with **FastAPI**, **Angular**, and **Spartan UI**. Separate Docker containers serve the frontend and backend; Cloudflare Tunnel can publish the app at **booklet.lesaloon.net**. No accounts, database, or authentication.

## Features

- ISO A1–A10 input sizes, printed on the next larger A-series sheet.
- Live paper-size summary and folding diagram.
- Proportional fitting without cropping; portrait pages only, including rotated portrait content.
- Automatic blank-page padding to a multiple of four.
- PDF download with original page, duplex sheet, and blank-page counts.
- Temporary processing; uploaded and generated files are deleted after the response completes.
- 95 MB upload limit, configurable in the backend and Nginx.

| Finished page | Print sheet, landscape |
| --- | --- |
| A1 | A0 |
| A2 | A1 |
| A3 | A2 |
| A4 | A3 |
| A5 | A4 |
| A6 (default) | A5 |
| A7 | A6 |
| A8 | A7 |
| A9 | A8 |
| A10 | A9 |

The chosen format controls the output size; input pages are fitted into it, rather than required to have exactly matching dimensions. Parent sheets use exact ISO dimensions, so minor rounding differences at the fold are expected. A0 input is excluded because it would need a larger-than-A0 sheet. Password-protected, empty, and landscape PDFs are rejected.

## Run with Docker

Requires Docker Engine and Docker Compose.

```sh
docker compose up -d --build
```

Open **http://localhost:8080**. Only the frontend is published on the host, bound to loopback. The backend is reachable within the Compose network.

```sh
docker compose logs -f
docker compose down
```

Set `PORT` in a local `.env` file to change the local port. To change the upload limit, update `MAX_UPLOAD_MB` in `compose.yaml` and `client_max_body_size` in `frontend/nginx.conf` (allow a little extra room for multipart overhead).

## Publish with Cloudflare Tunnel

1. Make sure `lesaloon.net` is managed by your Cloudflare account.
2. In the Cloudflare dashboard, go to **Networking → Tunnels** and create a remotely managed tunnel, such as `pdf-booklet-imposer`.
3. Copy the tunnel **token** from its connector installation command into a local `.env` file:

   ```dotenv
   TUNNEL_TOKEN=your-tunnel-token
   PORT=8080
   ```

   `.env.example` is provided as a template. `.env` is ignored by Git; never commit the token.

4. Add a **Published application** route:

   | Setting | Value |
   | --- | --- |
   | Subdomain | `booklet` |
   | Domain | `lesaloon.net` |
   | Service type | `HTTP` |
   | Service URL | `frontend:80` |

   The connector runs inside Compose, so use the frontend service name, not localhost. Route all paths through this service; Nginx forwards `/api/*` to FastAPI.

5. Start the hosting profile:

   ```sh
   docker compose --profile hosting up -d --build
   docker compose logs -f cloudflared
   ```

6. Once the tunnel is healthy, open **https://booklet.lesaloon.net**.

No inbound router ports are required. The host must be able to reach Cloudflare for the outbound tunnel. No Cloudflare Access application is needed for this public app.

See [Cloudflare’s tunnel setup guide](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/).

## Printing

1. Choose the sheet size shown in the app, in **landscape** orientation.
2. Set scaling to **actual size / 100%**.
3. Print **double-sided, flip on the short edge**.
4. Select **one page per sheet** and disable the printer’s booklet mode—the PDF is already imposed.
5. Print every page in order, stack the sheets, then fold and staple at the spine.

Try a small booklet first to check your printer’s duplex orientation. Printable margins depend on the printer.

## Local development

Use Python 3.13+ and a supported Node.js version (24.15+ LTS recommended).

Backend, from the repository root:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
uvicorn backend.app:app --reload
```

Frontend, in another terminal:

```sh
cd frontend
npm ci
npm start
```

Open **http://localhost:4200**. The Angular development server proxies `/api` to `127.0.0.1:8000`.

### Checks

```sh
python -m pytest -q
```

From `frontend/`:

```sh
npm run build
```

CI runs backend tests, an Angular production build, and both container builds. Tests generate synthetic PDF fixtures; no user documents are included in the repository.

### API

- `GET /api/health` — health status.
- `GET /api/formats` — supported input sizes, output sheet dimensions, and upload limit.
- `POST /api/booklet?page_format=A4` — multipart `file`; returns an A3 landscape PDF.

```sh
curl -f -F 'file=@document.pdf' \
  'http://localhost:8080/api/booklet?page_format=A4' \
  -o document-booklet-A3.pdf
```

Response headers include `X-Booklet-Pages`, `X-Booklet-Sheets`, and `X-Booklet-Blanks`. API documentation is available at `http://localhost:8000/docs` when running the backend directly.

### Command line

The original script remains available:

```sh
python a6_booklet.py document.pdf booklet.pdf --format A4
```

The default is A6 → A5. Output filenames must be new; existing files are never overwritten.

## License

[MIT](LICENSE). Generated Spartan Helm components retain the attribution in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Made with ❤️ by [lesaloon](https://github.com/Lesaloon).
