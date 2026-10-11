from app.db.models import UploadedFile


def upload_file(client, filename, content, content_type="application/octet-stream"):
    return client.post(
        "/api/files/",
        files={"file": (filename, content, content_type)},
    )


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_kml_metadata_and_measurements(client, kml_bytes):
    response = upload_file(
        client,
        "demo.kml",
        kml_bytes,
        "application/vnd.google-earth.kml+xml",
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["filename"] == "demo.kml"
    assert body["file_format"] == "kml"
    assert body["feature_count"] == 1
    assert body["source_crs"] == "EPSG:4326"
    assert body["measurement_crs"] == "EPSG:32610"
    assert body["status"] == "completed"

    file_id = body["id"]
    metadata = client.get(f"/api/files/{file_id}/")
    assert metadata.status_code == 200
    assert metadata.json()["feature_count"] == 1

    measurements = client.get(f"/api/files/{file_id}/measurements/")
    assert measurements.status_code == 200
    payload = measurements.json()
    assert payload["returned_count"] == 1
    feature = payload["features"][0]
    assert feature["geometry_type"] == "Polygon"
    assert feature["properties"]["Name"] == "Demo Parcel"
    assert feature["area_m2"] > 0
    assert feature["length_m"] is None
    assert feature["measurement_status"] == "measured"


def test_upload_shapefile_zip(client, shapefile_zip_bytes):
    response = upload_file(client, "demo.zip", shapefile_zip_bytes, "application/zip")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["file_format"] == "zip"
    assert body["feature_count"] == 1
    assert body["source_crs"] == "EPSG:4326"
    assert body["status"] == "completed"

    measurements = client.get(f"/api/files/{body['id']}/measurements/")
    assert measurements.status_code == 200
    assert measurements.json()["features"][0]["area_m2"] > 0


def test_multi_feature_pagination(client, multi_feature_kml_bytes):
    response = upload_file(client, "multi.kml", multi_feature_kml_bytes)
    assert response.status_code == 201, response.text
    file_id = response.json()["id"]

    first = client.get(
        f"/api/files/{file_id}/measurements/",
        params={"limit": 2, "offset": 0},
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["feature_count"] == 3
    assert first_body["returned_count"] == 2
    assert [f["properties"]["Name"] for f in first_body["features"]] == [
        "Parcel A", "Parcel B"
    ]

    second = client.get(
        f"/api/files/{file_id}/measurements/",
        params={"limit": 2, "offset": 2},
    )
    assert second.status_code == 200
    assert second.json()["returned_count"] == 1
    assert second.json()["features"][0]["properties"]["Name"] == "Parcel C"

    past_end = client.get(
        f"/api/files/{file_id}/measurements/",
        params={"limit": 2, "offset": 3},
    )
    assert past_end.status_code == 200
    assert past_end.json()["returned_count"] == 0
    assert past_end.json()["features"] == []


def test_unknown_file_ids_return_404(client):
    assert client.get("/api/files/999999/").status_code == 404
    assert client.get("/api/files/999999/measurements/").status_code == 404


def test_metadata_only_file_returns_empty_measurement_page(
    client, db_session_factory
):
    with db_session_factory() as db:
        record = UploadedFile(
            filename="metadata-only.kml",
            file_format="kml",
            feature_count=0,
            status="received",
            source_crs=None,
            measurement_crs=None,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        file_id = record.id

    response = client.get(f"/api/files/{file_id}/measurements/")
    assert response.status_code == 200
    assert response.json()["feature_count"] == 0
    assert response.json()["features"] == []


def test_invalid_pagination_parameters_return_422(client, kml_bytes):
    upload = upload_file(client, "demo.kml", kml_bytes)
    assert upload.status_code == 201, upload.text
    file_id = upload.json()["id"]

    assert client.get(
        f"/api/files/{file_id}/measurements/", params={"limit": 0}
    ).status_code == 422
    assert client.get(
        f"/api/files/{file_id}/measurements/", params={"offset": -1}
    ).status_code == 422
    assert client.get(
        f"/api/files/{file_id}/measurements/", params={"limit": 501}
    ).status_code == 422
