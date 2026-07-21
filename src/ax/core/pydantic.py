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

    for field_name in model.model_fields:
        value = getattr(model, field_name)
        if is_list_of_structured_data(value):
            list_fields[field_name] = value
        else:
            # Scalars, None, or empty lists go to metadata
            metadata[field_name] = value

    return metadata, list_fields


def _is_oneof_wrapper(model: BaseModel) -> bool:
    """Return True if model is an openapi-generator oneOf discriminated union wrapper.

    These wrappers expose ``actual_instance``, ``one_of_schemas``, and
    ``discriminator_value_class_map`` as their fields instead of the real
    domain fields, which produces unusable column names in tables.
    """
    fields = set(model.model_fields.keys())
    return "actual_instance" in fields and "one_of_schemas" in fields


def basemodel_to_dataframe(models: list[BaseModel | dict]) -> pd.DataFrame:
    """Convert a list of BaseModel instances or dicts to a DataFrame.

    Args:
        models: List of BaseModel instances or dicts

    Returns:
        DataFrame with flattened data
    """
    if not models:
        return pd.DataFrame()

    data: list[dict] = []
    for model in models:
        if isinstance(model, BaseModel):
            # Unwrap oneOf discriminated union wrappers to their actual instance
            # so we display real domain fields instead of generator internals
            # (oneof_schema_1_validator, discriminator_value_class_map, etc.)
            if _is_oneof_wrapper(model):
                actual = getattr(model, "actual_instance", None)
                if isinstance(actual, BaseModel):
                    data.append(actual.model_dump(mode="json"))
                    continue
                if isinstance(actual, dict):
                    data.append(actual)
                    continue
            data.append(model.model_dump(mode="json"))
        else:
            data.append(model)  # type: ignore[arg-type]

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
    """Check if BaseModel is a list response that can be rendered as a table.

    Returns True for models that expose a ``to_df()`` method — the convention
    used by list-response types across the SDK (e.g. ``ListUsersResponse``,
    ``BulkDeleteResponse``).  Pagination metadata is handled separately by
    :class:`~ax.core.output.TableFormatter`, which checks for a ``pagination``
    attribute independently.

    Args:
        model: Pydantic BaseModel instance

    Returns:
        True if the model has a callable ``to_df`` method
    """
    return callable(getattr(model, "to_df", None))
