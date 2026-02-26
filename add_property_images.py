
import os
import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
import random



PROPERTY_IMAGES = {
    "Apartment": [
        "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=600",
        "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=600",
        "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600",
        "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600",
        "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=600",
    ],
    "Villa": [
        "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?w=600",
        "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=600",
        "https://images.unsplash.com/photo-1583608205776-bfd35f0d9f83?w=600",
    ],
    "Studio": [
        "https://images.unsplash.com/photo-1536376072261-38c75010e6c9?w=600",
        "https://images.unsplash.com/photo-1554995207-c18c203602cb?w=600",
    ],
    "Penthouse": [
        "https://images.unsplash.com/photo-1567767292278-a4f21aa2d36e?w=600",
        "https://images.unsplash.com/photo-1622866306950-81d17097d458?w=600",
    ],
}

DEFAULT_IMAGES = [
    "https://images.unsplash.com/photo-1560184897-ae75f418493e?w=600",
    "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=600",
    "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600",
]

def add_images_to_properties():

    load_dotenv()
    mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
   
    if "mongodb+srv" in mongodb_url:
        print("Connecting to Atlas with SSL...")
        client = MongoClient(mongodb_url, tlsCAFile=certifi.where())
    else:
        print("Connecting to Localhost...")
        client = MongoClient(mongodb_url)
    
    db = client["geoinsight_ai"]
    
    properties = list(db.properties.find({"image_url": {"$exists": False}}))
    
    if not properties:
        properties = list(db.properties.find({}))
        print(f"Updating all {len(properties)} properties...")
    else:
        print(f"Found {len(properties)} properties without images")
    
    updated = 0
    for prop in properties:
        ptype = prop.get("property_type", "Apartment")
        
        images = None
        for key in PROPERTY_IMAGES:
            if key.lower() in str(ptype).lower():
                images = PROPERTY_IMAGES[key]
                break
        
        if not images:
            images = DEFAULT_IMAGES
        
        db.properties.update_one(
            {"_id": prop["_id"]},
            {"$set": {"image_url": random.choice(images)}}
        )
        updated += 1
        
        if updated % 100 == 0:
            print(f"Updated {updated}/{len(properties)}...")
    
    print(f"\nDone Added image URLs to {updated} properties")
    print("Now run the batch embed from the Vector Search tab")
    client.close()

if __name__ == "__main__":
    add_images_to_properties()