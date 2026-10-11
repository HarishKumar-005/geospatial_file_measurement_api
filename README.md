# Geospatial File Measurement API

A Python backend API that accepts KML files and ZIP archives containing Shapefiles, extracts geographic features, transforms coordinates into a suitable projected coordinate system, and calculates polygon areas and line lengths.

## Features

- Upload KML files and ZIP archives containing Shapefiles.
- Extract feature geometry, properties, and source CRS.
- Validate coordinate reference systems.
- Select a suitable projected CRS for supported local datasets.
- Calculate polygon area in square metres.
- Calculate line length in metres.
- Handle Point features without producing inappropriate measurements.
- Track invalid, empty, and unsupported geometries.
- Persist file metadata and feature measurements in SQLite.
- Retrieve results through REST API endpoints.
- Paginate measurement results.
- Validate uploaded file formats, size limits, and ZIP archive contents.
- Run automated unit, integration, API, and security tests.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend programming language |
| FastAPI | REST API framework |
| GeoPandas | Geospatial data processing |
| Pyogrio and GDAL | Reading geospatial files |
| Shapely | Geometry operations and measurements |
| PyProj | Coordinate reference system handling |
| SQLAlchemy | Database access and ORM |
| SQLite | Persistent metadata and measurement storage |
| Pydantic | Request and response validation |
| Pytest | Automated testing |
| Ruff | Code quality checks |

## Architecture

The application follows a modular backend architecture.

1. **API layer:** Receives upload and retrieval requests.
2. **Validation layer:** Checks file extensions, size limits, and ZIP archive contents.
3. **Geospatial parsing service:** Reads KML and Shapefile datasets.
4. **Feature normalization service:** Converts parsed features into a consistent structure.
5. **CRS service:** Validates source CRS, selects a measurement CRS, and transforms geometries.
6. **Measurement service:** Calculates area and length and handles unsupported geometries.
7. **Repository layer:** Saves and retrieves data using SQLAlchemy.
8. **SQLite database:** Stores uploaded-file metadata and individual feature results.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/files/` | Upload and process a KML or Shapefile ZIP |
| GET | `/api/files/{file_id}/` | Retrieve uploaded-file metadata |
| GET | `/api/files/{file_id}/measurements/` | Retrieve feature measurements |

The measurements endpoint supports `limit` and `offset` query parameters.

Interactive documentation is provided through FastAPI's Swagger UI at `/docs`.

## Measurement Rules

| Geometry | Measurement |
|---|---|
| Polygon | Area in square metres |
| MultiPolygon | Combined area in square metres |
| LineString | Length in metres |
| MultiLineString | Combined length in metres |
| Point | No area or line-length measurement |
| MultiPoint | No area or line-length measurement |
| Unsupported geometry | Explicit unsupported status |

Measurements use transformed geometries and an appropriate projected CRS. The source CRS and measurement CRS are stored separately.

Missing or invalid source CRS information is not silently guessed. The initial UTM selection strategy rejects unsupported geographic extents rather than applying an unsuitable projection automatically.

Numeric results are rounded to two decimal places for API presentation. The database retains the unrounded measurement values.

## Database Design

The SQLite database contains two main tables:

- `uploaded_files`: Stores filename, format, feature count, source CRS, measurement CRS, processing status, creation time, and error information.
- `feature_results`: Stores feature index, source ID when available, geometry type, properties, geometry representation, area, length, and measurement status.

Each feature result belongs to an uploaded-file record.

## Installation and Development

### Requirements

- Python 3.14
- Git
- Windows, Linux, or macOS with compatible geospatial library distributions

### Create a virtual environment

On Windows PowerShell:

```powershell
py -V:3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Install project dependencies

Install the dependencies listed in the project's `requirements.txt`:

```powershell
python -m pip install -r requirements.txt
```

### Run the API

```powershell
python -m uvicorn app.main:app --reload
```

Open these URLs in your browser:

- Health check: `http://127.0.0.1:8000/health`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Testing

Run all automated tests:

```powershell
python -m pytest
```

Run Ruff against the application and tests:

```powershell
python -m ruff check app tests
```

The test suite covers measurement calculations, CRS selection and transformation, API endpoints, geospatial processing, and upload security.

## Security Considerations

- Restrict uploads to supported file extensions and inspect file contents.
- Limit uploaded file sizes.
- Inspect ZIP paths, entry counts, expanded sizes, and archive integrity.
- Use generated temporary paths instead of trusting client-supplied filenames as filesystem paths.
- Do not automatically infer missing CRS information.
- Return controlled error responses for invalid files and processing failures.

For production deployment, enforce HTTP request-body limits at the server or reverse-proxy level as well.

## Current Scope and Limitations

- Version 1 focuses on KML and ZIP archives containing one Shapefile dataset.
- CRS selection uses a conservative UTM strategy for supported local datasets.
- Global, polar, or overly broad datasets may be rejected and require a different projection strategy.
- Unsupported geometry types do not receive area or line-length measurements.
- The initial version uses SQLite and synchronous file processing.

## Future Enhancements

- Support alternative projection strategies for regional and global datasets.
- Add database migrations.
- Introduce a production deployment configuration.
- Add support for more geographic file formats.
- Improve processing limits, observability, and scalability.

## Project Status

The initial API, geospatial parsing, CRS handling, measurement engine, SQLite persistence, pagination, and automated tests have been implemented and manually verified.

The project is being prepared for documentation, packaging, and public GitHub submission.
