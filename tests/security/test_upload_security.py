from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile


def upload(client, filename, content, content_type="application/octet-stream"):
    return client.post(
        "/api/files/",
        files={"file": (filename, content, content_type)},
    )


def make_zip(entries):
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return buffer.getvalue()


def test_unsupported_extension_is_rejected(client):
    response = upload(client, "notes.txt", b"hello")
    assert response.status_code == 415


def test_fake_zip_is_rejected(client):
    response = upload(client, "fake.zip", b"not a zip file", "application/zip")
    assert response.status_code == 422


def test_malformed_kml_is_rejected(client):
    response = upload(
        client,
        "broken.kml",
        b"<html><body>not KML</body></html>",
        "application/vnd.google-earth.kml+xml",
    )
    assert response.status_code == 422


def test_empty_kml_is_rejected(client):
    response = upload(client, "empty.kml", b"")
    assert response.status_code == 422


def test_path_traversal_zip_is_rejected(client):
    content = make_zip(
        [
            ("../outside.txt", b"unsafe"),
            ("demo.shp", b"placeholder"),
            ("demo.shx", b"placeholder"),
            ("demo.dbf", b"placeholder"),
        ]
    )
    response = upload(client, "unsafe.zip", content, "application/zip")
    assert response.status_code == 422
    assert "unsafe path" in response.json()["detail"].lower()


def test_excessive_compression_ratio_is_rejected(client):
    # Highly repetitive content should exceed the project's ratio threshold.
    content = make_zip([("repetitive.txt", b"A" * 100_000)])
    response = upload(client, "bomb.zip", content, "application/zip")
    assert response.status_code == 422
    assert "compression ratio" in response.json()["detail"].lower()


def test_oversized_upload_is_rejected(client):
    # The project's current configured upload limit is 10 MiB.
    content = b"x" * (10 * 1024 * 1024 + 1)
    response = upload(client, "oversized.kml", content)
    assert response.status_code == 413


def test_valid_content_is_checked_not_just_client_mime_type(client, kml_bytes):
    # A MIME type supplied by a client is not proof of actual file content.
    response = upload(client, "demo.kml", kml_bytes, "text/plain")
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "completed"
