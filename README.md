# Procure-to-Pay (Mini)

A simplified Procure-to-Pay system built with Django + DRF, containerized with Docker, including multi-level approvals, document processing (proforma/PO/receipt), and a minimal frontend.

## Features
- Staff: create and update pending requests, upload proforma and receipts
- Approvers (L1/L2): view pending, approve/reject; final approval auto-generates a Purchase Order
- Finance: view all requests and PO documents
- JWT authentication and Swagger API docs
- Document processing via pdfplumber/pytesseract (naive extraction)
- Dockerized with Postgres

## Quick Start (Docker)
```bash
git clone <repo>
cd Procure-to-Pay
docker-compose up --build
```
Visit `http://localhost:8000/api/docs/` for Swagger, and `http://localhost:8000/` for the minimal UI.

### Build & Run with plain Docker
```bash
# Build image
docker build -t ist-africa-protopay:local .

# Run container (uses sqlite by default)
docker run --rm -p 8080:8000 \
  -e SECRET_KEY=change-me -e DEBUG=true \
  --name ptp-app ist-africa-protopay:local

# Open http://localhost:8080
```

## Local (without Docker)
```bash
python -m venv .venv && .venv/Scripts/activate  # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Authentication
- Obtain JWT: `POST /api/auth/token/` with `{ "username": "...", "password": "..." }`
- Use `Authorization: Bearer <token>` on subsequent requests

## API Endpoints
- `POST /api/requests/` – create (Staff)
- `GET /api/requests/` – list (filtered by role)
- `GET /api/requests/{id}/` – detail
- `PUT /api/requests/{id}/` – update pending (Staff only)
- `PATCH /api/requests/{id}/approve/` – approve (Approver L1/L2)
- `PATCH /api/requests/{id}/reject/` – reject (Approver L1/L2)
- `POST /api/requests/{id}/submit-receipt/` – upload receipt (Staff)
- Swagger: `GET /api/docs/`

## Roles
Custom user model adds `role` with one of: `staff`, `approver_l1`, `approver_l2`, `finance`.

Create superuser for admin:
```bash
python manage.py createsuperuser
```
Then set role via Django Admin.

## Document Processing
- Proforma: on create, if uploaded, tries to extract vendor/items/total and populate items
- PO: generated on final approval; stored as JSON under `media/purchase_orders/`
- Receipt validation: basic checks against PO (vendor and approximate total)

## Deployment
You can deploy on Render/Fly.io/Railway/AWS EC2.
- Build with Dockerfile; set env vars: `DB_*`, `SECRET_KEY`, `ALLOWED_HOSTS`.
- Run migrations on first start.
- Serve via `gunicorn` or `runserver` behind a reverse proxy.

Example `CMD` for production:
```Dockerfile
CMD ["bash", "-lc", "python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:8000"]
```

### CI: GitHub Actions + GHCR
This repo includes `.github/workflows/docker.yml` which builds and pushes image to GitHub Container Registry on pushes to `main`.
- Image: `ghcr.io/<owner>/<repo>:latest`
- Requires no extra secrets; uses `GITHUB_TOKEN` automatically.
- Pull and run:
```bash
docker pull ghcr.io/<owner>/<repo>:latest
docker run --rm -p 8080:8000 -e SECRET_KEY=change-me ghcr.io/<owner>/<repo>:latest
```

### Render (one-click)
- This repo includes `render.yaml` for Docker deploy.
- Steps:
  1) Create account on Render and click “New +” → “Web Service”.
  2) Connect your GitHub repo `Hiiduah/IST-Africa-Protopay`.
  3) Render will detect `render.yaml` and configure the service.
  4) Set `SECRET_KEY` in Environment Variables.
  5) Deploy (auto on push to `main`).
- The service will expose a public URL, e.g., `https://ist-africa-protopay.onrender.com/`.
- API docs: `https://<your-url>/api/docs/`.

## Notes
- For OCR to work, container installs `tesseract-ocr`.
- The extraction is heuristic; plug in an LLM/OpenAI for higher accuracy if desired.
- Add pagination/filtering via DRF if your dataset grows.

## License
For assessment/demo purposes.