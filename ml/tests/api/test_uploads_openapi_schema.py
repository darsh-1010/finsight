"""OpenAPI schema tests for upload route."""

from src.api.main import create_app


def test_upload_openapi_schema_uses_binary_file_items():
    """Upload request body should expose binary file items for Swagger UI."""
    app = create_app()
    spec = app.openapi()
    schema_ref = spec["paths"]["/api/v1/upload"]["post"]["requestBody"]["content"]["multipart/form-data"]["schema"]["$ref"]
    schema_name = schema_ref.split("/")[-1]
    upload_schema = spec["components"]["schemas"][schema_name]
    files_items = upload_schema["properties"]["files"]["items"]

    assert files_items["type"] == "string"
    assert files_items["format"] == "binary"
