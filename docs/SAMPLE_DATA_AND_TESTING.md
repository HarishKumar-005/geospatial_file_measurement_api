# Sample Data and Testing Guide

This guide explains how to use the included sample datasets to verify the Geospatial File Measurement API. These files supplement the application; they do not replace its source code or the project's main `README.md`.

## 1. Included datasets

| File | Format | What it demonstrates | Expected behavior |
|---|---|---|---|
| `sample_data/polygon_area_demo.kml` | KML | Three polygon parcels | Polygon areas are calculated in square metres after appropriate CRS transformation. |
| `sample_data/line_length_demo.kml` | KML | Line features | Line lengths are calculated in metres after appropriate CRS transformation. |
| `sample_data/point_features_demo.kml` | KML | Point features | Points are parsed without calculating area or length. |
| `sample_data/mixed_geometry_demo.kml` | KML | Polygon, line, and point features | Each feature is processed according to its geometry type. |
| `sample_data/shapefile_parcels.zip` | ZIP containing a Shapefile | Shapefile upload | The complete archive is uploaded and polygon features are measured. |

All sample geometries are fictional and located near Chennai, India. The KML and Shapefile declare WGS 84 (`EPSG:4326`). The datasets are intentionally small for development, testing, and demonstrations.

## 2. Start the API

Open PowerShell in the project root and activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

If the FastAPI application entry point is `app.main:app`, start it with:

```powershell
python -m uvicorn app.main:app --reload
```

If the project's entry point differs, use the module path configured in the existing application. Open Swagger UI at `http://127.0.0.1:8000/docs`.

## 3. Test uploads in Swagger UI

1. Open `http://127.0.0.1:8000/docs`.
2. Expand `POST /api/files/` and select **Try it out**.
3. Select a sample file using the upload field shown in the API schema, then execute the request.
4. Check the response for the file identifier and processing summary according to the implemented response schema.
5. Use the returned identifier with `GET /api/files/{id}/` to inspect saved file metadata.
6. Use `GET /api/files/{id}/measurements/` to inspect feature results. If pagination parameters are available, vary `limit` and `offset` to verify that different slices are returned.
7. Repeat with the other sample files. Upload `shapefile_parcels.zip` as a ZIP archive; do not upload only the `.shp` file without its sidecar files.

## 4. Verification checklist

- [ ] Polygon KML is accepted and polygon area values are expressed in square metres.
- [ ] Line KML is accepted and line length values are expressed in metres.
- [ ] Point features are parsed without an area or length calculation.
- [ ] Mixed-geometry KML gives geometry-appropriate results.
- [ ] The zipped Shapefile is accepted and its polygon features are processed.
- [ ] Source CRS is identified as WGS 84 / `EPSG:4326` where CRS metadata is returned.
- [ ] Measurements use a suitable projected CRS rather than treating longitude/latitude degrees as metres, where measurement CRS metadata is returned.
- [ ] Metadata and measurements can be retrieved using the returned file identifier.
- [ ] Pagination returns distinct results when `limit` and `offset` are changed.
- [ ] Malformed or unsupported uploads are handled safely.

Exact JSON keys and status strings depend on the schemas implemented by the project. Confirm them in Swagger UI rather than assuming particular field names.

## 5. Run automated checks

Run these commands from the project root with the virtual environment activated:

```powershell
python -m pytest
python -m ruff check tests
python -m pip check
```

`pytest` runs the automated tests. Ruff checks the test code for lint issues if it is installed, and `pip check` checks for installed-package dependency conflicts.

## 6. Keep generated and local files out of version control

Keep reproducible source samples in `sample_data/`. Do not commit the virtual environment, secrets, generated uploads, temporary extraction folders, or local database files. A typical `.gitignore` includes:

```gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.env
data/*.db
```

Review the actual `.gitignore` and repository contents before submission.

## 7. Troubleshooting

- **Swagger UI does not load:** confirm the startup command and inspect the terminal for import errors.
- **Upload validation fails:** confirm the endpoint's expected multipart field and accepted file format in Swagger UI.
- **Shapefile ZIP is rejected:** ensure the ZIP contains `.shp`, `.shx`, `.dbf`, and `.prj` companion files at the archive root; upload the entire ZIP.
- **CRS validation fails:** inspect the declared CRS. The included samples use WGS 84 / `EPSG:4326`.
- **Area or length looks incorrect:** check the source and measurement CRS reported by the API; geographic coordinates are in degrees and must not be treated as metres.
- **A test fails:** rerun the failing test with `python -m pytest path\to\test_file.py -vv` and inspect the traceback before changing code.
