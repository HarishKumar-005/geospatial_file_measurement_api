# Geospatial File Measurement API

A REST API built with **Python and FastAPI** that accepts KML files or ZIP archives containing an ESRI Shapefile, processes their geographic features, calculates polygon areas and line lengths in metric units, and stores the results for later retrieval.

The main engineering concern is measurement correctness: longitude and latitude are angular coordinates, not metres. The API validates the source Coordinate Reference System (CRS), chooses a suitable projected CRS for supported local datasets, transforms geometries before measuring them, and records the CRS used for the measurement.

## Contents

- [Problem and solution](#problem-and-solution)
- [Features](#features)
- [Technology stack](#technology-stack)
- [Architecture](#architecture)
- [Supported inputs and measurement rules](#supported-inputs-and-measurement-rules)
- [Getting started](#getting-started)
- [Using the API](#using-the-api)
- [Response and error behaviour](#response-and-error-behaviour)
- [Sample datasets](#sample-datasets)
- [Testing and code quality](#testing-and-code-quality)
- [Security and data handling](#security-and-data-handling)
- [Known limitations](#known-limitations)
- [Future improvements](#future-improvements)

## Problem and solution

Geospatial datasets can contain many land parcels, road segments, buildings, and locations. Measuring every feature manually in desktop GIS software is repetitive and difficult to integrate into an application workflow.

This service exposes that workflow through a REST API:

1. A client uploads a supported geospatial file.
2. The application validates the upload and reads its features and attributes.
3. The application checks the source CRS and selects a suitable projected CRS for measurement.
4. Each feature is measured according to its geometry type.
5. File metadata and feature measurement outcomes are persisted in SQLite.
6. The client retrieves file metadata and paginated measurement results as JSON.

**Intended users:** developers, GIS analysts, and applications that need structured measurements from existing geospatial files.

## Features

- **KML upload:** accepts `.kml` files.
- **Shapefile upload:** accepts a `.zip` archive containing the Shapefile and its companion files.
- **Feature processing:** reads geometry types and feature properties.
- **Metric measurements:** calculates polygon area in square metres and line length in metres.
- **CRS-aware processing:** keeps source CRS information separate from the projected measurement CRS.
- **Explicit geometry outcomes:** points, invalid or empty geometries, and unsupported geometry types do not silently receive misleading measurements.
- **Persistent results:** stores file metadata and feature measurement results in SQLite through SQLAlchemy.
- **REST endpoints:** provides upload, health, metadata retrieval, and paginated measurement retrieval.
- **Interactive API documentation:** FastAPI provides Swagger UI and an OpenAPI schema.
- **Automated checks:** includes unit, integration, API, and upload-security tests.

## Technology stack

| Component | Purpose |
|---|---|
| Python | Application language |
| FastAPI | REST API and request handling |
| Uvicorn | Local ASGI development server |
| Pydantic | Response and data validation |
| GeoPandas | Reading and working with geospatial feature datasets |
| Pyogrio / GDAL | Geospatial file I/O and format drivers |
| Shapely | Geometry inspection and planar geometry operations |
| PyProj / PROJ | CRS interpretation and coordinate transformations |
| SQLAlchemy | Database models and persistence layer |
| SQLite | Local relational database |
| Pytest | Automated tests |
| Ruff | Python lint checks |

The working dependency versions are recorded in `requirements.txt`. The project was developed and tested in a local Windows environment; geospatial library and GDAL driver availability can vary by platform.

## Architecture

The application follows a **modular monolith** design: one FastAPI application with separate responsibilities rather than a distributed microservice system.

```text
Client / Swagger UI
        |
        v
FastAPI routes
        |
        v
Upload validation and file processing
        |
        v
Geospatial reader (KML / zipped Shapefile)
        |
        v
Source CRS validation
        |
        v
Measurement CRS selection and transformation
        |
        v
Geometry measurement and result formatting
        |
        v
SQLAlchemy repository / SQLite
        |
        v
JSON response
```

Main application modules include:

- `app/main.py` — creates the FastAPI application and registers routes.
- `app/api/files.py` — exposes the upload, metadata, and measurements endpoints.
- `app/services/geospatial_service.py` — reads KML and Shapefile ZIP input and extracts features.
- `app/services/crs_service.py` — inspects the source CRS, selects a measurement CRS, and transforms geometries.
- `app/services/measurement_service.py` — classifies geometry types and calculates measurements.
- `app/services/file_processing_service.py` — coordinates geospatial parsing, CRS handling, and measurements.
- `app/db/` and `app/repositories/` — database session, models, and data access.
- `app/schemas/` — typed request/response structures.
- `tests/` — unit, integration, API, and security tests.

A typical repository layout is:

```text
.
├── app/
│   ├── main.py
│   ├── api/
│   ├── db/
│   ├── repositories/
│   ├── schemas/
│   └── services/
├── tests/
│   ├── api/
│   ├── integration/
│   ├── security/
│   └── unit/
├── sample_data/
├── docs/
├── data/                  # local SQLite database; do not commit
├── requirements.txt
├── pytest.ini
├── .gitignore
└── README.md
```

The exact file layout in the repository is the source of truth if additional modules have been added during development.

## Supported inputs and measurement rules

### Input formats

| Input | Requirements | Behaviour |
|---|---|---|
| KML (`.kml`) | A readable KML document with usable CRS information | Reads features, properties, and geometries |
| Shapefile ZIP (`.zip`) | A valid ZIP containing a readable Shapefile and its companion files, including `.shp`, `.shx`, `.dbf`, and CRS information such as `.prj` | Reads features and processes them using the same measurement workflow |

A `.shp` file by itself is not a complete Shapefile upload. Upload the complete ZIP archive. A missing or invalid source CRS is not silently assumed to be WGS 84.

### Geometry handling

| Geometry | Measurement behaviour | Output units/status |
|---|---|---|
| `Polygon` / `MultiPolygon` | Calculates area | `area_m2` in square metres; `length_m` is not applicable |
| `LineString` / `MultiLineString` | Calculates length | `length_m` in metres; `area_m2` is not applicable |
| `Point` / `MultiPoint` | Retains the feature without area/length calculation | `measurement_status: not_applicable` |
| Empty geometry | Does not calculate a measurement | `measurement_status: empty_geometry` |
| Invalid geometry | Does not return a misleading measurement | `measurement_status: invalid_geometry` |
| Unsupported geometry, such as `GeometryCollection` | Reports an explicit unsupported outcome | `measurement_status: unsupported_geometry` |

### Coordinate reference systems and measurement accuracy

- The **source CRS** identifies the coordinate system of the uploaded dataset.
- The **measurement CRS** is the projected CRS used for area/length calculations.
- For supported local datasets, the service selects a suitable UTM projection from the dataset extent and records the selected CRS.
- Area and length are not calculated directly from geographic longitude/latitude coordinates and labelled as square metres/metres.
- Missing or invalid CRS metadata and geographic extents that are unsuitable for the initial UTM-based strategy are rejected with a controlled error instead of being silently guessed.

Measurements are intended for application workflows and depend on the dataset quality and projection suitability. This initial version does **not** claim survey-grade accuracy for every location or globally spanning datasets.

## Getting started

### Prerequisites

- Python version compatible with the installed dependencies. The development environment used Python 3.14.8.
- The project source code.
- `requirements.txt` from the project root.
- A geospatial environment in which the required GeoPandas, Pyogrio/GDAL, Shapely, and PyProj dependencies install and their file drivers are available.

### 1. Create and activate a virtual environment

From the project root, run these commands in **Windows PowerShell**. Use the same Python minor version used to validate the project's dependencies when possible.

```powershell
py -V:3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
```

If `.venv` already exists and is working, activate it instead of recreating it:

```powershell
.\.venv\Scripts\Activate.ps1
```

For macOS or Linux, use an installed compatible Python interpreter and activate the environment with `source .venv/bin/activate`.

### 2. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

`pip check` should finish without reporting dependency conflicts. If installation fails on the geospatial packages, confirm the Python version and wheel availability for your operating system before changing package versions.

### 3. Start the API

Run from the project root with the virtual environment active:

```powershell
python -m uvicorn app.main:app --reload
```

The development server listens on `http://127.0.0.1:8000` by default.

### 4. Open the API documentation

- **Swagger UI:** <http://127.0.0.1:8000/docs>
- **ReDoc:** <http://127.0.0.1:8000/redoc>
- **OpenAPI JSON:** <http://127.0.0.1:8000/openapi.json>
- **Health check:** <http://127.0.0.1:8000/health>

Swagger UI is the easiest way to try file uploads and inspect the exact request and response schemas implemented by the running application.

## Using the API

### 1. Check application health

```http
GET /health
```

A healthy application returns HTTP `200` with a response equivalent to:

```json
{
  "status": "ok"
}
```

### 2. Upload a geospatial file

```http
POST /api/files/
Content-Type: multipart/form-data
```

The multipart file field is named `file`. The endpoint accepts a `.kml` file or a `.zip` file containing a readable Shapefile.

Example using `curl.exe` in PowerShell (run from the project root):

```powershell
curl.exe -X POST `
  -F "file=@sample_data/polygon_area_demo.kml" `
  http://127.0.0.1:8000/api/files/
```

A successful upload is expected to return HTTP `201 Created`. The following is an **illustrative** response; the generated ID and selected measurement CRS depend on the data and database:

```json
{
  "id": 1,
  "filename": "polygon_area_demo.kml",
  "file_format": "kml",
  "feature_count": 3,
  "source_crs": "EPSG:4326",
  "measurement_crs": "<selected projected CRS>",
  "status": "completed"
}
```

Copy the actual `id` returned by your upload. It is used by the retrieval endpoints below.

### 3. Retrieve file metadata

```http
GET /api/files/{id}/
```

Replace `{id}` with the ID returned by the upload request. The response contains persisted metadata for that file, including its filename, format, feature count, CRS information, and processing status.

Example:

```powershell
curl.exe http://127.0.0.1:8000/api/files/1/
```

### 4. Retrieve measurement results

```http
GET /api/files/{id}/measurements/?limit=100&offset=0
```

The measurements endpoint returns per-feature outcomes and supports pagination through `limit` and `offset`. For example:

```powershell
curl.exe "http://127.0.0.1:8000/api/files/1/measurements/?limit=2&offset=0"
```

The response includes the total feature count, the count returned on the requested page, and a `features` array. A measured polygon contains an area value; a measured line contains a length value; fields that do not apply are `null`.

Illustrative response shape:

```json
{
  "feature_count": 3,
  "returned_count": 2,
  "features": [
    {
      "geometry_type": "Polygon",
      "properties": {
        "Name": "Parcel A"
      },
      "area_m2": 123.45,
      "length_m": null,
      "measurement_status": "measured"
    }
  ]
}
```

Measurement values shown above are examples only, not expected values for every dataset. Refer to Swagger UI for the complete active response schema and use the actual values returned by the API.

To view the next page, increase `offset`, for example `offset=2`. An offset beyond the last feature returns an empty `features` array. Pagination values must be valid and within the configured limits.

## Response and error behaviour

The API uses HTTP status codes to distinguish successful processing from unsupported or invalid input. The following behaviours are covered by the project's tests:

| Situation | HTTP status |
|---|---:|
| Health check succeeds | `200` |
| Upload and processing succeed | `201` |
| Requested file ID does not exist | `404` |
| Unsupported file extension | `415` |
| Empty or malformed KML, a fake ZIP, or rejected unsafe archive input | `422` for the tested cases |
| Uploaded file exceeds the configured 10 MiB limit | `413` |
| Invalid pagination parameters | `422` |

The response body includes an error detail for rejected requests. Do not rely on the examples in this README instead of the live OpenAPI schema; use Swagger UI to verify the exact shape for your current build.

## Sample datasets

If the `sample_data/` directory is included in your submission, it should contain small, fictional datasets for repeatable demonstrations:

| File | Demonstrates |
|---|---|
| `polygon_area_demo.kml` | Polygon area measurement |
| `line_length_demo.kml` | Line length measurement |
| `point_features_demo.kml` | Point handling without area/length calculations |
| `mixed_geometry_demo.kml` | Different geometry types in a single KML file |
| `shapefile_parcels.zip` | Upload and measurement of a zipped Shapefile |

All example files are intended for development and demonstration, not as real survey data. For the Shapefile example, upload the ZIP archive as supplied; do not upload only the `.shp` component.

See [`docs/SAMPLE_DATA_AND_TESTING.md`](docs/SAMPLE_DATA_AND_TESTING.md) for a practical sample upload and verification guide, when that file is included. If the sample files are stored elsewhere or have different filenames in the submitted repository, update this table to match the actual files before publishing.

## Testing and code quality

Activate the project's virtual environment, change to the project root, and run:

```powershell
python -m pytest
```

Run the individual groups when debugging:

```powershell
python -m pytest tests/unit -v
python -m pytest tests/integration -v
python -m pytest tests/api -v
python -m pytest tests/security -v
```

Run the test-code lint check and dependency consistency check:

```powershell
python -m ruff check tests
python -m pip check
```

Test coverage includes geometry classification and measurement; CRS validation, selection, and transformation; KML and Shapefile ZIP parsing; upload and retrieval endpoints; pagination; unknown file IDs; and upload validation cases such as malformed input, unsafe archive paths, compression-ratio checks, and size limits.

A test passing in one environment is not a substitute for rerunning the suite against the submitted source and dependency file. Investigate failures rather than deleting tests or changing expected results simply to obtain a green run.

## Security and data handling

- The upload endpoint validates file type and content rather than trusting a client-supplied MIME type alone.
- The current tested upload size limit is **10 MiB**.
- ZIP input is inspected, and unsafe archive paths and excessive compression ratios are rejected by the tested security checks.
- Missing or unusable CRS information is not silently replaced with a guessed CRS.
- The project should not contain secrets, private survey data, generated upload copies, or local-only credentials.
- The SQLite database is local application state. Keep `data/*.db` and other generated files out of version control.

Before public submission, check `.gitignore` includes at least:

```gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.env
data/*.db
```

Review the final repository for accidentally committed virtual environments, local databases, temporary extraction folders, and private files.

## Known limitations

- The first release supports KML and ZIP archives containing Shapefiles; it is not a general-purpose GIS file conversion service.
- The initial CRS strategy is intended for suitable local datasets and uses a projected measurement CRS. Broad, polar, or otherwise unsuitable extents may be rejected.
- It does not promise survey-grade accuracy for every CRS, area of the world, or source dataset.
- There is no web frontend, interactive map, authentication, role management, or multi-tenant access control in this release.
- Unsupported geometry types receive an explicit status rather than a measurement; this is safer than silently returning an incorrect value.
- The local SQLite setup is suitable for a small demonstration or single-instance workflow, not a high-concurrency production deployment.

## Future improvements

Possible follow-up work includes stronger benchmarking with documented datasets, configurable file and feature limits, expanded CRS strategies for broader extents, background processing for large files, a PostgreSQL/PostGIS storage option, authentication and authorization, and deployment packaging if required by the target environment.

## Project status

This is a local-first, testable API project intended to demonstrate geospatial processing, CRS-aware measurements, REST API design, persistence, validation, and automated testing. Run the installation and verification steps above against the final submitted repository to reproduce the result.
