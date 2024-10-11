import json
from pathlib import Path

"""
Export the CVs to JSON-schema.
"""


facets = [
    "activity_id",
    "experiment_id",
    "frequency",
    "grid_label",
    "institution_id",
    "nominal_resolution",
    "realm",
    "source_id",
    "source_type",
    "sub_experiment_id",
    "table_id",
]


def read_cv(key: str) -> dict:
    """Read a CV file and return it as a dictionary."""
    path = Path(__file__).parent.parent / f"CMIP6_{key}.json"
    with open(path) as f:
        return json.load(f)


def cv_to_property(cv: dict) -> dict:
    """Convert a CV to a JSON schema property."""
    cv.pop("version_metadata")
    if len(cv) > 1:
        raise ValueError("CV has more than one key.")

    field = {"source_id": "label",
             "experiment_id": "description"
             }

    out = {}
    for fid, keys in cv.items():
        items = []
        if isinstance(keys, dict):
            for key, value in keys.items():
                if isinstance(value, str):
                    items.append({"const": key, "title": value})
                elif isinstance(value, dict):
                    items.append(
                        {
                            "const": key,
                            "title": value[field[fid]]
                        }
                    )
            out[fid] = {"oneOf": items}
        elif isinstance(keys, list):
            out[fid] = {"enum": keys}
    return out


def make_global_attrs_schema() -> dict:
    """Create a JSON schema for netCDF global attributes from the JSON CVs.

    Example
    -------
    Open a netCDF file, read the global attributes and validate them agaist the schema.

    >>> import jsonschema
    >>> import xarray as xr
    >>> ds = xr.open_dataset("<path to netCDF file>")
    >>> schema = make_global_attrs_schema()
    >>> jsonschema.validate(ds.attrs, schema)
    """

    # Read required global attributes
    reqs = read_cv("required_global_attributes")["required_global_attributes"]

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "CMIP6 metadata schema",
        "description": "JSON schema for global attributes metadata",
        "type": "object",
        "properties": {},
        "required": reqs
    }

    ints = ["initialization_index",
            "physics_index",
            "realization_index",
            "forcing_index"
            ]

    formats = {"creation_date": "date-time",
               "further_info_url": "uri"}

    props = {}
    for fid in reqs:
        if fid in facets:
            cv = read_cv(fid)
            props.update(cv_to_property(cv))
        elif fid in ints:
            # Could be replaced by patternProperties, but at the expense of readability
            props[fid] = {"type": "integer"}
        elif fid == "mip_era":
            props["mip_era"] = {"const": "CMIP6"}
        else:
            props[fid] = {"type": "string"}

        if fid in formats:
            props[fid]["format"] = formats[fid]

    schema["properties"].update(props)

    return schema


def make_drs_schema() -> dict:
    """Create schema for netCDF file names and directories.

    TODO: Include regex for directories and files
    TODO: Write a function to extract facets from the path and validate them against the schema
    """

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "CMIP6 DRS schema",
        "description": "JSON schema for directory and file names",
        "type": "object",
        "properties": {
            "directory_path": {"type": "string",
                                "pattern": "/CMIP6/"}, # TODO
            "filename": {"type": "string",
                         "pattern": ".nc"}  # TODO
        },
    }

    for fid in facets:
        cv = read_cv(fid)
        schema["properties"].update(cv_to_property(cv))

    return schema


def test_make_global_attrs_schema():
    schema = make_global_attrs_schema()
    # TODO: Get a dict of global attrs to check against.


def test_make_drs_schema():
    import jsonschema
    schema = make_drs_schema()

    # Check that a valid entry is validated by the schema validator
    valid_entry = {
        "activity_id": "CMIP",
        "experiment_id": "historical",
        "frequency": "mon",
        "grid_label": "gn",
        "institution_id": "NCAR",
        "nominal_resolution": "100 km",
        "realm": "atmos",
        "source_id": "CESM2",
        "source_type": "AOGCM",
        "sub_experiment_id": "none",
        "table_id": "Amon"
    }
    jsonschema.validate(instance=valid_entry, schema=schema)

    # Check that errors are raised for each invalid entry
    invalid_entry = {
        "activity_id": "CBIP",
        "experiment_id": "hysterical",
        "frequency": "weekly",
        "grid_label": "gnan",
        "institution_id": "ACME",
        "nominal_resolution": "100 parsec",
        "realm": "disco",
        "source_id": "ABBA",
        "source_type": "ESM",
        "sub_experiment_id": "None",
        "table_id": "Tobin"
    }
    validator = jsonschema.Draft7Validator(schema)
    if not validator.is_valid(invalid_entry):
        errors = list(validator.iter_errors(invalid_entry))
        assert len(errors) == len(invalid_entry)
