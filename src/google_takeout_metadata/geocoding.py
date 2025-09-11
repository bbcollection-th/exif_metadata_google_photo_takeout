"""Utilitaires de géocodage inverse avec cache disque simple."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)

# Chemin vers le fichier de cache JSON
CACHE_FILE = Path(__file__).with_name("geocode_cache.json")


def _load_cache() -> Dict[str, Any]:
    """Charger le contenu du cache depuis le disque."""
    if CACHE_FILE.exists():
        try:
            with CACHE_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Impossible de lire le cache de géocodage: %s", exc)
            return {}
    return {}


def _save_cache(cache: Dict[str, Any]) -> None:
    """Sauvegarder le cache sur le disque."""
    try:
        with CACHE_FILE.open("w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        logger.warning("Impossible d'écrire le cache de géocodage: %s", exc)


def reverse_geocode(lat: float, lon: float) -> List[Dict[str, Any]]:
    """Obtenir les informations d'adresse pour une latitude/longitude.

    Un cache JSON sur disque est utilisé pour éviter les appels répétés à
    l'API Google Geocoding. L'API key doit être fournie via la variable
    d'environnement ``GOOGLE_MAPS_API_KEY``.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        La liste des résultats de géocodage (champ ``results`` de la réponse).

    Raises:
        RuntimeError: En cas de problème réseau, d'erreur API ou si le quota est
        dépassé.
    """
    key = f"{lat},{lon}"
    cache = _load_cache()
    if key in cache:
        return cache[key]

    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("API key manquante (GOOGLE_MAPS_API_KEY)")

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"latlng": key, "key": api_key}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.Timeout as exc:
        raise RuntimeError("Requête de géocodage expirée") from exc
    except requests.RequestException as exc:
        raise RuntimeError("Erreur de requête de géocodage") from exc

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError("Réponse JSON invalide") from exc

    status = data.get("status")
    if status == "OVER_QUERY_LIMIT":
        raise RuntimeError("Quota de géocodage dépassé")
    if status != "OK":
        raise RuntimeError(f"Erreur de l'API de géocodage: {status}")

    results = data.get("results", [])
    cache[key] = results
    _save_cache(cache)
    return results
