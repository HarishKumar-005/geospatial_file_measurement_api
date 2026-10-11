from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import Polygon
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import FeatureResult, UploadedFile  # noqa: F401
from app.db.session import Base, get_db
from app.main import app


def build_kml_bytes(names: list[str]) -> bytes:
    """Build simple, valid KML Polygon features near San Francisco."""
    placemarks = []

    for index, name in enumerate(names):
        west = -122.420 + index * 0.003
        east = west + 0.001
        south = 37.770
        north = 37.771
        coordinates = (
            f"{west:.6f},{south:.6f},0 "
            f"{east:.6f},{south:.6f},0 "
            f"{east:.6f},{north:.6f},0 "
            f"{west:.6f},{north:.6f},0 "
            f"{west:.6f},{south:.6f},0"
        )
        placemarks.append(
            "<Placemark>"
            f"<name>{name}</name>"
            "<Polygon><outerBoundaryIs><LinearRing>"
            f"<coordinates>{coordinates}</coordinates>"
            "</LinearRing></outerBoundaryIs></Polygon>"
            "</Placemark>"
        )

    document = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
        "<Document>\n"
        + "\n".join(placemarks)
        + "\n</Document>\n</kml>\n"
    )
    return document.encode("utf-8")


def build_shapefile_zip_bytes(
    directory: Path,
    include_prj: bool = True,
) -> bytes:
    """Create a genuine one-feature Shapefile archive for tests."""
    shape_dir = directory / "shapefile_components"
    shape_dir.mkdir(parents=True, exist_ok=True)

    polygon = Polygon(
        [
            (-122.420, 37.770),
            (-122.419, 37.770),
            (-122.419, 37.771),
            (-122.420, 37.771),
            (-122.420, 37.770),
        ]
    )
    gdf = gpd.GeoDataFrame(
        {"Name": ["Demo Parcel"]},
        geometry=[polygon],
        crs="EPSG:4326",
    )
    shp_path = shape_dir / "demo.shp"
    gdf.to_file(
        shp_path,
        driver="ESRI Shapefile",
        engine="pyogrio",
        index=False,
    )

    allowed_extensions = {".shp", ".shx", ".dbf", ".prj", ".cpg"}
    zip_path = directory / (
        "demo_with_prj.zip" if include_prj else "demo_without_prj.zip"
    )
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for component in shape_dir.iterdir():
            suffix = component.suffix.lower()
            if suffix in allowed_extensions and (include_prj or suffix != ".prj"):
                archive.write(component, arcname=component.name)

    return zip_path.read_bytes()


@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session_factory(test_engine):
    return sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )


@pytest.fixture
def client(db_session_factory):
    def override_get_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def kml_bytes() -> bytes:
    return build_kml_bytes(["Demo Parcel"])


@pytest.fixture
def multi_feature_kml_bytes() -> bytes:
    return build_kml_bytes(["Parcel A", "Parcel B", "Parcel C"])


@pytest.fixture
def shapefile_zip_bytes(tmp_path) -> bytes:
    return build_shapefile_zip_bytes(tmp_path, include_prj=True)


@pytest.fixture
def shapefile_zip_without_prj_bytes(tmp_path) -> bytes:
    return build_shapefile_zip_bytes(tmp_path, include_prj=False)


@pytest.fixture
def bytes_io():
    return BytesIO
