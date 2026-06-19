"""Dispatches to the active profile's retrieve() function."""

import importlib

_VALID_PROFILES = {"baseline", "variant_embed", "variant_hybrid", "variant_llm"}


def get_profile(name: str):
    if name not in _VALID_PROFILES:
        raise ValueError(f"Unknown profile: {name}")
    return importlib.import_module(f"app.profiles.{name}")


def retrieve(profile_name: str, query: str, k: int = 5):
    return get_profile(profile_name).retrieve(query, k)
