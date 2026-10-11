
# Database Design

## Database

SQLite is used for the initial version.
SQLAlchemy provides the Python database models and queries.

## Table: uploaded_files

Stores one record per uploaded file.

- id: integer primary key
- filename: sanitized filename
- file_format: kml or zip
- feature_count: number of parsed features
- source_crs: original CRS, nullable
- measurement_crs: selected measurement CRS, nullable
- status: processing, completed, or failed
- created_at: UTC timestamp
- error_message: nullable error description

## Table: feature_results

Stores one record per parsed feature.

- id: integer primary key
- file_id: foreign key to uploaded_files.id
- feature_index: zero-based index within the file
- source_fid: original feature ID, nullable
- geometry_type: geometry type
- geometry_json: original geometry, nullable
- properties_json: feature attributes
- area_m2: calculated area, nullable
- length_m: calculated line length, nullable
- measurement_status: measurement outcome
- measurement_crs: CRS used for measurement, nullable
- message: explanatory message, nullable

## Relationships

One uploaded file has many feature results.

Each feature result belongs to exactly one uploaded file.
Deleting a file record should delete its associated feature results.

## Design Decisions

- SQLite keeps local development simple.
- SQLAlchemy separates database operations from API routes.
- Geometry and properties are stored as JSON-compatible data.
- Source CRS and measurement CRS are separate.
- Area and length are nullable because not every geometry
  supports both measurements.
- A unique constraint on (file_id, feature_index) prevents
  duplicate feature indexes within one uploaded file.
- The original uploaded file is processed temporarily.
  The database stores metadata and feature results, not
  the entire uploaded file binary.
