import pandas as pd
from pymongo import MongoClient
from datetime import datetime
import os
import argparse
from typing import Optional
import time

class MumbaiHousingLoader:

    def __init__(
        self,
        MONGODB_URL: str = "mongodb://localhost:27017",
        db_name: str = "geoinsight_ai"
    ):
        self.client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
        self.db = self.client[db_name]
        self.collection = self.db["properties"]

    def clean_price_with_unit(self, price_value, price_unit) -> Optional[float]:
        if pd.isna(price_value):
            return None
        try:
            price = float(price_value)
            if pd.isna(price_unit):
                return price
            unit = str(price_unit).strip().upper()
            if unit == 'CR' or unit == 'CRORE':
                return price * 10000000
            elif unit == 'L' or unit == 'LAC' or unit == 'LAKH':
                return price * 100000
            elif unit == 'K' or unit == 'THOUSAND':
                return price * 1000
            else:
                return price
        except:
            return None

    def extract_bedrooms(self, bhk_value) -> int:
        if pd.isna(bhk_value):
            return 2
        try:
            return int(bhk_value)
        except:
            return 2

    def load_mumbai_housing(
        self,
        csv_path: str = "data/Mumbai House Prices.csv",
        clear_existing: bool = True,
        max_rows: Optional[int] = None,
        verbose: bool = True
    ) -> bool:

        if not os.path.exists(csv_path):
            print(f"File not found: {csv_path}")
            return False

        if verbose:
            print(f"Reading {csv_path}")

        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return False

        if verbose:
            print(f"Found {len(df)} rows")
            print(f"Columns: {', '.join(df.columns.tolist())}")

        if max_rows:
            df = df.head(max_rows)
            if verbose:
                print(f"Limited to {max_rows} rows")

        if clear_existing:
            deleted = self.collection.delete_many({})
            if verbose:
                print(f"Deleted {deleted.deleted_count} existing properties")

        properties_added = 0
        errors = 0

        if verbose:
            print("Processing Mumbai housing data")

        for idx, row in df.iterrows():
            try:
                locality = row.get('locality', 'Mumbai')
                property_type = row.get('type', 'Apartment')
                bhk = row.get('bhk', 2)
                area_sqft = row.get('area', 0)
                price_value = row.get('price', 0)
                price_unit = row.get('price_unit', 'L')
                price_inr = row.get('price_inr', 0)
                region = row.get('region', locality)
                status = row.get('status', 'Ready to move')
                age = row.get('age', 'New')
                price_per_sqft_orig = row.get('price_per_sqft', 0)

                city = 'Mumbai'
                state = 'Maharashtra'

                if pd.notna(price_inr) and price_inr > 0:
                    price = float(price_inr)
                else:
                    price = self.clean_price_with_unit(price_value, price_unit)

                if price is None or price <= 0:
                    price = 5000000

                bedrooms = self.extract_bedrooms(bhk)
                bathrooms = max(1.0, bedrooms * 0.75)

                try:
                    square_feet = int(float(area_sqft)) if pd.notna(area_sqft) and area_sqft > 0 else int(price / 15000)
                except:
                    square_feet = int(price / 15000)

                if square_feet > 0:
                    price_per_sqft = price / square_feet
                else:
                    price_per_sqft = price_per_sqft_orig if pd.notna(price_per_sqft_orig) else 0

                address_parts = []
                if pd.notna(locality) and str(locality).strip():
                    address_parts.append(str(locality))
                if pd.notna(region) and str(region).strip() and region != locality:
                    address_parts.append(str(region))
                address = ', '.join(address_parts) + ', Mumbai' if address_parts else 'Mumbai'

                property_doc = {
                    "address": address,
                    "city": city,
                    "state": state,
                    "zip_code": "400001",
                    "price": float(price),
                    "bedrooms": int(bedrooms),
                    "bathrooms": float(bathrooms),
                    "square_feet": int(square_feet),
                    "property_type": str(property_type),
                    "locality": str(locality),
                    "region": str(region) if pd.notna(region) else str(locality),
                    "status": str(status) if pd.notna(status) else "Ready to move",
                    "age": str(age) if pd.notna(age) else "New",
                    "price_per_sqft": float(price_per_sqft),
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                }

                self.collection.insert_one(property_doc)
                properties_added += 1

                if verbose and properties_added % 100 == 0:
                    print(f"Loaded {properties_added} properties")

            except:
                errors += 1
                continue

        if verbose:
            print(f"Successfully loaded {properties_added} properties")
            print(f"Errors: {errors}")
            print(f"Total in database: {self.collection.count_documents({})}")
            self.show_stats()

        return True

    def show_stats(self):
        total = self.collection.count_documents({})
        print(f"Total properties: {total}")

        pipeline = [
            {"$group": {"_id": "$locality", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        for doc in self.collection.aggregate(pipeline):
            print(f"{doc['_id']}: {doc['count']} properties")

        pipeline = [
            {"$group": {
                "_id": None,
                "avg_price": {"$avg": "$price"},
                "min_price": {"$min": "$price"},
                "max_price": {"$max": "$price"}
            }}
        ]
        stats = list(self.collection.aggregate(pipeline))
        if stats:
            stat = stats[0]
            print(f"Average: {stat['avg_price']}")
            print(f"Minimum: {stat['min_price']}")
            print(f"Maximum: {stat['max_price']}")

        pipeline = [
            {"$group": {"_id": "$bedrooms", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        for doc in self.collection.aggregate(pipeline):
            print(f"{doc['_id']} BHK: {doc['count']} properties")

    def close(self):
        self.client.close()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--csv-path',
        type=str,
        default='data/Mumbai House Prices.csv'
    )

    parser.add_argument(
        '--mongodb-url',
        type=str,
        default='mongodb://localhost:27017'
    )

    parser.add_argument(
        '--db-name',
        type=str,
        default='geoinsight_ai'
    )

    parser.add_argument(
        '--keep-existing',
        action='store_true'
    )

    parser.add_argument(
        '--max-rows',
        type=int,
        default=None
    )

    args = parser.parse_args()

    loader = MumbaiHousingLoader(
        MONGODB_URL=args.MONGODB_URL,
        db_name=args.db_name
    )

    success = loader.load_mumbai_housing(
        csv_path=args.csv_path,
        clear_existing=not args.keep_existing,
        max_rows=args.max_rows,
        verbose=True
    )

    if success:
        print("Data loaded successfully")
    else:
        print("Data loading failed")

    loader.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Cancelled")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()