# Copyright 2026 Google LLC
"""Firestore backend tools for the Greenhouse plant collection."""
from typing import Dict, List, Optional
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-04-af9f0d7d2999"

_db = None


def get_firestore_client() -> firestore.Client:
    """Returns a singleton Firestore client with the hardcoded Project ID."""
    global _db
    if _db is None:
        _db = firestore.Client(project=PROJECT_ID)
    return _db


def list_plants(category: Optional[str] = None) -> List[Dict]:
    """List available plants in the greenhouse catalog, optionally filtered by category.

    Args:
        category: Optional category filter, e.g. 'Foliage', 'Succulent', 'Tree', 'Flowering'.

    Returns:
        A list of plant items with their details.
    """
    db = get_firestore_client()
    collection_ref = db.collection("plants")
    if category:
        query = collection_ref.where("category", "==", category)
        docs = query.stream()
    else:
        docs = collection_ref.stream()

    results = []
    for doc in docs:
        item = doc.to_dict()
        item["id"] = doc.id
        results.append(item)
    return results


def get_plant_details(plant_name_or_id: str) -> Dict:
    """Get detailed information and care requirements for a specific plant.

    Args:
        plant_name_or_id: The ID or name of the plant (e.g. 'monstera-deliciosa' or 'Monstera').

    Returns:
        Plant details including light, water, care level, price, and description.
    """
    db = get_firestore_client()
    target = plant_name_or_id.strip().lower()

    # Direct document ID lookup
    doc = db.collection("plants").document(target).get()
    if doc.exists:
        data = doc.to_dict()
        data["id"] = doc.id
        return data

    # Search by plant name
    for d in db.collection("plants").stream():
        item = d.to_dict()
        if target in item.get("name", "").lower() or target in d.id.lower():
            item["id"] = d.id
            return item

    return {"error": f"Plant '{plant_name_or_id}' not found in greenhouse catalog."}


def add_or_update_plant(
    id: str,
    name: str,
    species: str,
    category: str,
    light: str,
    water: str,
    care_level: str,
    description: str,
    price: float,
    in_stock: bool = True,
) -> Dict:
    """Add a new plant or update an existing plant in the catalog.

    Args:
        id: Unique identifier for the plant, e.g. 'snake-plant'.
        name: Common name of the plant, e.g. 'Snake Plant'.
        species: Botanical/scientific name, e.g. 'Sansevieria trifasciata'.
        category: Plant category, e.g. 'Succulent', 'Foliage', 'Tree'.
        light: Lighting requirements.
        water: Watering frequency and needs.
        care_level: Ease of care, e.g. 'Beginner', 'Easy', 'Moderate'.
        description: Brief overview of the plant.
        price: Price in USD.
        in_stock: Whether the plant is currently available.

    Returns:
        Status result of the operation.
    """
    db = get_firestore_client()
    data = {
        "id": id,
        "name": name,
        "species": species,
        "category": category,
        "light": light,
        "water": water,
        "care_level": care_level,
        "description": description,
        "price": price,
        "in_stock": in_stock,
    }
    db.collection("plants").document(id).set(data)
    return {"status": "success", "message": f"Successfully recorded plant '{name}' with ID '{id}'."}
