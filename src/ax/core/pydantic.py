"""Utilities for inspecting and converting Pydantic BaseModel objects."""

from typing import Any

import pandas as pd
from pydantic import BaseModel


def is_list_of_structured_data(value: object) -> bool:
    """Check if value is a non-empty list of BaseModel or dict objects.

    Args:
        value: Value to check

    Returns:
        True if value is a non-empty list of structured objects
    """
    if not isinstance(value, list) or len(value) == 0:
        return False

    # Check if first item is structured data (BaseModel or dict with multiple keys)
    first_item = value[0]
    if isinstance(first_item, BaseModel):
        return True
    return isinstance(first_item, dict) and len(first_item) > 0


def categorize_basemodel_fields(
    model: BaseModel,
) -> tuple[dict[str, Any], dict[str, list]]:
    """Split BaseModel fields into metadata (scalars) and list_fields (structured lists).

    Args:
        model: Pydantic BaseModel instance

    Returns:
        Tuple of (metadata_dict, list_fields_dict)
        - metadata_dict: Scalar fields and their values
        - list_fields_dict: List fields containing structured data
    """
    metadata: dict[str, Any] = {}
    list_fields: dict[str, list] = {}

    for field_name, value in model.model_dump().items():
        if is_list_of_structured_data(value):
            list_fields[field_name] = value
        else:
            # Scalars, None, or empty lists go to metadata
            metadata[field_name] = value

    return metadata, list_fields


def basemodel_to_dataframe(models: list[BaseModel | dict]) -> pd.DataFrame:
    """Convert a list of BaseModel instances or dicts to a DataFrame.

    Args:
        models: List of BaseModel instances or dicts

    Returns:
        DataFrame with flattened data
    """
    if not models:
        return pd.DataFrame()

    # Convert BaseModels to dicts if needed
    data = (
        [model.model_dump() for model in models]  # type: ignore[union-attr]
        if isinstance(models[0], BaseModel)
        else models
    )

    return pd.DataFrame(data)


def flatten_basemodel_for_export(model: BaseModel) -> dict[str, Any]:
    """Flatten a BaseModel for CSV/Parquet export.

    List fields are converted to `num_{field_name}` count fields.
    Nested BaseModels are flattened to their dict representation.

    Args:
        model: Pydantic BaseModel instance

    Returns:
        Flattened dictionary suitable for export
    """
    flattened: dict[str, Any] = {}
    metadata, list_fields = categorize_basemodel_fields(model)

    # Add all metadata fields
    flattened.update(metadata)

    # Convert list fields to counts
    for field_name, value in list_fields.items():
        flattened[f"num_{field_name}"] = len(value)

    return flattened


def is_list_response_model(model: BaseModel) -> bool:
    """Check if BaseModel is a list response with pagination.

    Returns True for *List200Response objects from SDK which have
    a pagination field containing PaginationMetadata.

    Args:
        model: Pydantic BaseModel instance

    Returns:
        True if model has pagination field (is a list response)
    """
    return hasattr(model, "pagination")
