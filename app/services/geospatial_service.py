import ntpath
import stat
import zlib

from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

import geopandas as gpd


class GeospatialParseError(Exception):
    """Raised when a geographic file cannot be parsed."""


def validate_geodataframe(
    gdf: gpd.GeoDataFrame,
    format_name: str,
) -> gpd.GeoDataFrame:
    """Check that a parsed dataset has usable structure."""

    if not isinstance(gdf, gpd.GeoDataFrame):
        raise GeospatialParseError(
            f"The {format_name} parser did not return a GeoDataFrame."
        )

    try:
        geometry_column = gdf.geometry
    except (AttributeError, KeyError, ValueError) as exc:
        raise GeospatialParseError(
            f"The {format_name} dataset has no usable geometry column."
        ) from exc

    if gdf.empty:
        raise GeospatialParseError(
            f"The {format_name} dataset contains no features."
        )

    if geometry_column is None:
        raise GeospatialParseError(
            f"The {format_name} dataset has no geometry column."
        )

    return gdf



def read_kml(file_path: str | Path) -> gpd.GeoDataFrame:
    """
    Read a local KML file and return its geographic features.

    Args:
        file_path: Path to the KML file.

    Returns:
        A GeoDataFrame containing feature attributes and geometry.

    Raises:
        GeospatialParseError: If the file is missing or cannot be read.
    """
    path = Path(file_path)

    if not path.is_file():
        raise GeospatialParseError("The KML file does not exist.")

    if path.suffix.lower() != ".kml":
        raise GeospatialParseError("Expected a file with a .kml extension.")

    try:
        geodataframe = gpd.read_file(
            path,
            engine="pyogrio"
        )
    except Exception as exc:
        raise GeospatialParseError(
            "Could not parse the KML file. Check that its contents are valid."
        ) from exc

    return validate_geodataframe(geodataframe, "KML")



MAX_ZIP_ENTRIES = 1000
MAX_ZIP_TOTAL_SIZE = 100 * 1024 * 1024
MAX_ZIP_MEMBER_SIZE = 50 * 1024 * 1024
MAX_ZIP_COMPRESSION_RATIO = 100


def read_shapefile_zip(
    file_path: str | Path,
) -> gpd.GeoDataFrame:
    """
    Read one Shapefile from a ZIP archive without extracting it.

    Returns a GeoDataFrame containing the feature attributes
    and geometries.
    """
    path = Path(file_path)

    if not path.is_file():
        raise GeospatialParseError("The ZIP file does not exist.")

    if path.suffix.lower() != ".zip":
        raise GeospatialParseError("Expected a .zip file.")

    try:
        with ZipFile(path, "r") as archive:
            members = archive.infolist()

            if not members:
                raise GeospatialParseError("The ZIP archive is empty.")

            if len(members) > MAX_ZIP_ENTRIES:
                raise GeospatialParseError(
                    "The ZIP contains too many entries."
                )

            groups = {}
            seen_paths = set()
            total_size = 0

            for member in members:
                original_name = member.filename

                if "\\" in original_name or "\x00" in original_name:
                    raise GeospatialParseError(
                        "The ZIP contains an invalid path."
                    )

                drive, _ = ntpath.splitdrive(original_name)

                if drive or original_name.startswith("/"):
                    raise GeospatialParseError(
                        "The ZIP contains an absolute path."
                    )

                name = original_name.rstrip("/")
                parts = name.split("/")

                if not name or any(
                    part in {"", ".", ".."} for part in parts
                ):
                    raise GeospatialParseError(
                        "The ZIP contains an unsafe path."
                    )

                canonical_path = name.casefold()

                if canonical_path in seen_paths:
                    raise GeospatialParseError(
                        "The ZIP contains duplicate paths."
                    )

                seen_paths.add(canonical_path)

                mode = (member.external_attr >> 16) & 0xFFFF

                if stat.S_ISLNK(mode):
                    raise GeospatialParseError(
                        "The ZIP contains a symbolic link."
                    )

                if member.flag_bits & 0x1:
                    raise GeospatialParseError(
                        "Encrypted ZIP entries are not supported."
                    )

                if member.is_dir():
                    continue

                if member.file_size > MAX_ZIP_MEMBER_SIZE:
                    raise GeospatialParseError(
                        "A ZIP entry exceeds the size limit."
                    )

                total_size += member.file_size

                if total_size > MAX_ZIP_TOTAL_SIZE:
                    raise GeospatialParseError(
                        "The ZIP exceeds the expanded size limit."
                    )

                if member.file_size > 0:
                    if member.compress_size == 0:
                        raise GeospatialParseError(
                            "The ZIP contains a suspicious entry."
                        )

                    ratio = member.file_size / member.compress_size

                    if ratio > MAX_ZIP_COMPRESSION_RATIO:
                        raise GeospatialParseError(
                            "The ZIP compression ratio is too high."
                        )

                archive_path = PurePosixPath(name)
                extension = archive_path.suffix.casefold()

                if extension in {".shp", ".shx", ".dbf"}:
                    key = (
                        str(archive_path.parent).casefold(),
                        archive_path.stem.casefold(),
                    )

                    groups.setdefault(key, {})[extension] = name

            required = {".shp", ".shx", ".dbf"}

            candidates = [
                components
                for components in groups.values()
                if required.issubset(components)
            ]

            if not candidates:
                raise GeospatialParseError(
                    "No complete Shapefile was found. "
                    "Matching .shp, .shx, and .dbf files are required."
                )

            if len(candidates) > 1:
                raise GeospatialParseError(
                    "The ZIP contains multiple Shapefiles. "
                    "Version 1 requires one dataset per archive."
                )

            try:
                corrupt_member = archive.testzip()
            except (
                BadZipFile,
                OSError,
                RuntimeError,
                NotImplementedError,
                EOFError,
                zlib.error,
            ) as exc:
                raise GeospatialParseError(
                    "The ZIP contains corrupt or unreadable data."
                ) from exc

            if corrupt_member is not None:
                raise GeospatialParseError(
                    "The ZIP failed its integrity check."
                )

            shapefile_member = candidates[0][".shp"]

    except GeospatialParseError:
        raise
    except (BadZipFile, OSError, RuntimeError, ValueError, EOFError) as exc:
        raise GeospatialParseError(
            "Could not read the ZIP archive."
        ) from exc

    # Read the selected Shapefile directly inside the archive.
    archive_path = path.resolve().as_posix()
    virtual_path = (
        f"/vsizip/{archive_path}/{shapefile_member}"
    )

    try:
        geodataframe = gpd.read_file(
            virtual_path,
            engine="pyogrio"
        )
    except Exception as exc:
        raise GeospatialParseError(
            "Could not parse the Shapefile inside the ZIP archive. "
            "Check that its components contain valid Shapefile data."
        ) from exc

    return validate_geodataframe(
        geodataframe,
        "Shapefile ZIP",)

