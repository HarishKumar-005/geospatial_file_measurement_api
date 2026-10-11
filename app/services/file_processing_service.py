
from pathlib import Path

from app.schemas.feature import ParsedFile
from app.schemas.measurement import MeasurementResult
from app.services.geospatial_service import (
    GeospatialParseError,
    read_kml,
    read_shapefile_zip,
)
from app.services.crs_service import transform_to_measurement_crs
from app.services.feature_normalization import normalize_geodataframe
from app.services.measurement_service import (
    MeasurementError,
    measure_geometry,
)


class FileProcessingError(Exception):
    """Raised when a file cannot be fully processed."""


def process_geospatial_file(
    file_path: str | Path,
    filename: str,
) -> tuple[ParsedFile, list[MeasurementResult], str]:
    """Parse a file, transform its geometries, and measure its features."""

    extension = Path(filename).suffix.lower()

    try:
        if extension == ".kml":
            gdf = read_kml(file_path)
        elif extension == ".zip":
            gdf = read_shapefile_zip(file_path)
        else:
            raise FileProcessingError(
                "Only KML and ZIP files are supported."
            )

        # Select the measurement CRS and transform geometries.
        transformed_gdf, measurement_crs = (
            transform_to_measurement_crs(gdf)
        )

        measurement_crs_text = measurement_crs.to_string()

        # Normalize the original geometries and their attributes.
        parsed_file = normalize_geodataframe(
            gdf,
            filename,
            measurement_crs=measurement_crs_text,
        )

        measurements = []

        # Preserve feature ordering when associating measurements
        # with the corresponding original features.
        for index in range(len(parsed_file.features)):
            geometry = transformed_gdf.geometry.iloc[index]

            result = measure_geometry(
                geometry,
                measurement_crs,
            )

            measurements.append(result)

        return parsed_file, measurements, measurement_crs_text

    except FileProcessingError:
        raise
    except (GeospatialParseError, MeasurementError, ValueError, OSError) as exc:
        raise FileProcessingError(str(exc)) from exc
    except Exception as exc:
        # Keep unexpected internal details out of API error messages.
        raise FileProcessingError(
            "The file could not be parsed and measured."
        ) from exc
