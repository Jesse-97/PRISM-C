"""Dispatches to the active profile's synthesize() function."""

from app.services.retrieval_service import get_profile


def synthesize(profile_name: str, query: str, chunks):
    return get_profile(profile_name).synthesize(query, chunks)
