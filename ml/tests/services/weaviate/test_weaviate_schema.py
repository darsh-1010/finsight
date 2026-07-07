"""Regression tests for Weaviate schema compatibility."""

from src.services.schema.weaviate_schema import WeaviateSchema


TEXT_TYPES = {"text", "text[]"}
RANGE_TYPES = {"int", "number", "date"}


def test_non_text_properties_are_not_marked_searchable():
    """Weaviate only allows searchable indexing on text and text arrays."""
    invalid_properties = []

    for prop in WeaviateSchema.get_schema():
        data_type = getattr(prop.dataType, "value", None)
        if data_type not in TEXT_TYPES and getattr(prop, "indexSearchable", None):
            invalid_properties.append(prop.name)

    assert invalid_properties == []


def test_range_filtering_is_only_enabled_for_supported_types():
    """Range filters should only be enabled on numeric and date properties."""
    invalid_properties = []

    for prop in WeaviateSchema.get_schema():
        data_type = getattr(prop.dataType, "value", None)
        if getattr(prop, "indexRangeFilters", None) and data_type not in RANGE_TYPES:
            invalid_properties.append(prop.name)

    assert invalid_properties == []
