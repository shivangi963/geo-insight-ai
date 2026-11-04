import pandas as pd
from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError, ServerSelectionTimeoutError
from datetime import datetime
import os
import argparse
from typing import Optional
import certifi
import logging
import traceback
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

class MumbaiHousingLoader:

    def __init__(
        self,
        MONGODB_URL: Optional[str] = None,
        db_name: str = "geoinsight_ai"
    ):
        MONGODB_URL = MONGODB_URL or os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        
        if "mongodb+srv" in MONGODB_URL:
            self.client = MongoClient(
                MONGODB_URL, 
                tlsCAFile=certifi.where(), 
                serverSelectionTimeoutMS=5000
            )
        else:
            self.client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
            
        self.db = self.client[db_name]
        self.collection = self.db["properties"]

    def check_connection(self) -> bool:
        """Fail fast: verify the URL and credentials once, before touching any data."""
        try:
            self.client.admin.command("ping")
            return True
        except OperationFailure as e:
            logger.error(f"MongoDB rejected the username/password ({e.code}). Fix MONGODB_URL in .env.")
        except PyMongoError as e:
            logger.error(f"Cannot reach MongoDB: {str(e)[:200]}")
        return False

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
        except ValueError:
            return None

    def extract_bedrooms(self, bhk_value) -> int:
        if pd.isna(bhk_value):
            return 2
        try:
            return int(bhk_value)
        except ValueError:
            return 2

    def load_mumbai_housing(
        self,
        csv_path: str = "data/Mumbai House Prices.csv",
        clear_existing: bool = False,  # Changed default to False
        max_rows: Optional[int] = None,
        verbose: bool = True
    ) -> bool:

        if not self.check_connection():
            return False

        if not os.path.exists(csv_path):
            logger.error(f"File not found: {csv_path}")
            return False

        if verbose:
            logger.info(f"Reading {csv_path}")

        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            return False

        if verbose:
            logger.info(f"Found {len(df)} rows")
            logger.info(f"Columns: {', '.join(df.columns.tolist())}")

        if max_rows:
            df = df.head(max_rows)
            if verbose:
                logger.info(f"Limited to {max_rows} rows")

        if clear_existing:
            try:
                deleted = self.collection.delete_many({})
                if verbose:
                    logger.info(f"Deleted {deleted.deleted_count} existing properties")
            except PyMongoError as e:
                logger.error(f"Database error while clearing collection: {e}")
                return False

        properties_added = 0
        errors = 0

        if verbose:
            logger.info("Processing Mumbai housing data")

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
                
                # Removed fabricated bathroom generation

                try:
                    square_feet = int(float(area_sqft)) if pd.notna(area_sqft) and area_sqft > 0 else int(price / 15000)
                except ValueError:
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
                    # zip_code omitted to rely on nullable field
                    "price": float(price),
                    "bedrooms": int(bedrooms),
                    # bathrooms omitted to rely on nullable field
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
                    logger.info(f"Loaded {properties_added} properties")

            except (OperationFailure, ServerSelectionTimeoutError) as fatal:
                logger.error(f"Stopping at row {idx}: MongoDB is not accepting writes ({fatal})")
                return False
            except PyMongoError as db_err:
                errors += 1
                logger.error(f"Database error inserting property at row {idx}: {db_err}")
                continue
            except Exception as e:
                errors += 1
                logger.error(f"Data processing error at row {idx}: {e}")
                continue

        if verbose:
            logger.info(f"Successfully loaded {properties_added} properties")
            if errors > 0:
                logger.warning(f"Errors encountered: {errors}")
            logger.info(f"Total in database: {self.collection.count_documents({})}")
            self.show_stats()

        return True

    def show_stats(self):
        total = self.collection.count_documents({})
        logger.info(f"Total properties: {total}")

        pipeline = [
            {"$group": {"_id": "$locality", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        logger.info("Top 10 localities by count:")
        for doc in self.collection.aggregate(pipeline):
            logger.info(f"  {doc['_id']}: {doc['count']} properties")

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
            logger.info(f"Average Price: {stat['avg_price']:,.2f}")
            logger.info(f"Minimum Price: {stat['min_price']:,.2f}")
            logger.info(f"Maximum Price: {stat['max_price']:,.2f}")

        pipeline = [
            {"$group": {"_id": "$bedrooms", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        logger.info("Properties by BHK:")
        for doc in self.collection.aggregate(pipeline):
            logger.info(f"  {doc['_id']} BHK: {doc['count']} properties")

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
        default=os.getenv('MONGODB_URL', 'mongodb://localhost:27017')
    )

    parser.add_argument(
        '--db-name',
        type=str,
        default=os.getenv('DATABASE_NAME', 'geoinsight_ai')
    )

    # Changed from --keep-existing to --clear-existing
    parser.add_argument(
        '--clear-existing',
        action='store_true',
        help="Clear all existing documents in the collection before loading"
    )

    parser.add_argument(
        '--max-rows',
        type=int,
        default=None
    )

    args = parser.parse_args()

    loader = MumbaiHousingLoader(
        MONGODB_URL=args.mongodb_url,
        db_name=args.db_name
    )

    success = loader.load_mumbai_housing(
        csv_path=args.csv_path,
        clear_existing=args.clear_existing,
        max_rows=args.max_rows,
        verbose=True
    )

    if success:
        logger.info("Data loaded successfully")
    else:
        logger.error("Data loading failed")

    loader.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("Process cancelled by user")
    except Exception as e:
        logger.error(f"Unexpected Fatal Error: {e}")
        traceback.print_exc()