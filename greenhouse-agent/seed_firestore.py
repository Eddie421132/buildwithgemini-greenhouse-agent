#!/usr/bin/env python3
"""Seed Firestore with initial greenhouse plants."""
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-04-af9f0d7d2999"

PLANTS = [
    {
        "id": "monstera-deliciosa",
        "name": "Monstera Deliciosa",
        "species": "Monstera deliciosa",
        "category": "Foliage",
        "light": "Bright indirect light",
        "water": "Every 1-2 weeks, allow soil to dry between waterings",
        "care_level": "Easy",
        "description": "Known as the Swiss Cheese Plant, famous for its iconic split leaves.",
        "in_stock": True,
        "price": 28.0,
    },
    {
        "id": "snake-plant",
        "name": "Snake Plant",
        "species": "Sansevieria trifasciata",
        "category": "Succulent",
        "light": "Low to bright indirect light",
        "water": "Every 2-3 weeks, very drought tolerant",
        "care_level": "Beginner",
        "description": "Indestructible air-purifying plant with upright sword-like green leaves.",
        "in_stock": True,
        "price": 22.0,
    },
    {
        "id": "fiddle-leaf-fig",
        "name": "Fiddle Leaf Fig",
        "species": "Ficus lyrata",
        "category": "Tree",
        "light": "Bright filtered light",
        "water": "Weekly when top inch of soil feels dry",
        "care_level": "Moderate",
        "description": "Statement indoor plant with large, violin-shaped glossy leaves.",
        "in_stock": True,
        "price": 45.0,
    },
    {
        "id": "peace-lily",
        "name": "Peace Lily",
        "species": "Spathiphyllum",
        "category": "Flowering",
        "light": "Medium to low indirect light",
        "water": "Keep soil lightly moist, droops clearly when thirsty",
        "care_level": "Easy",
        "description": "Elegant indoor plant producing graceful white spathes.",
        "in_stock": True,
        "price": 18.0,
    },
]

def seed():
    print(f"Connecting to Firestore using project ID: '{PROJECT_ID}'...")
    db = firestore.Client(project=PROJECT_ID)
    plants_ref = db.collection("plants")
    
    for item in PLANTS:
        doc_id = item["id"]
        plants_ref.document(doc_id).set(item)
        print(f"✓ Seeded: {item['name']} ({doc_id})")
    
    print("\nFirestore seeding complete! Collection 'plants' is populated.")

if __name__ == "__main__":
    seed()
