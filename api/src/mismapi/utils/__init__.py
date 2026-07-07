from mismapi.utils.dict_utils import get_string_or_empty_from_dict
from mismapi.utils.url_utils import merge_query_params


def upload_dir(resource_id: str, version: str) -> str:
    """Deterministic storage dir for a resource's uploaded files: ``<resource_id>/<version>``.

    The mount already namespaces models and datasets, so the resource id alone is
    enough — no ``models/`` prefix. Single source of truth for the upload
    destination: used at token mint, in the tus pre-create hook, and when
    reconciling ``location_uri`` on completion. A blank version degrades to
    ``<resource_id>`` (no trailing version segment).
    """
    version = (version or "").strip()
    parts = [resource_id] + ([version] if version else [])
    return "/".join(parts)


__all__ = ["upload_dir", "get_string_or_empty_from_dict", "merge_query_params"]
