from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from dotenv import find_dotenv, load_dotenv
from PIL import Image, UnidentifiedImageError

load_dotenv(find_dotenv())
logger = logging.getLogger(__name__)

try:
    from supabase import Client, create_client
    _SUPABASE_LIB = True
except ImportError:
    _SUPABASE_LIB = False
    logger.warning("supabase-py not installed — vector search disabled")

EMBEDDING_DIM = 512
_MAX_BYTES = 10 * 1024 * 1024
_VALID_FMTS = {"JPEG", "PNG", "WEBP", "BMP"}
_CLIP_MODEL = "openai/clip-vit-base-patch32"

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="clip_worker")


class CLIPEmbeddingService:

    _instance: Optional["CLIPEmbeddingService"] = None
    _init_lock: asyncio.Lock = asyncio.Lock()

    _model = None
    _processor = None
    _ready = False

    def __init__(self):
        raise RuntimeError("Use await CLIPEmbeddingService.get_instance()")

    @classmethod
    async def get_instance(cls) -> "CLIPEmbeddingService":
        if cls._instance is None:
            async with cls._init_lock:
                if cls._instance is None:
                    obj = object.__new__(cls)
                    await obj._async_load_model()
                    cls._instance = obj
        return cls._instance

    async def _async_load_model(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self._load_model_sync)

    @staticmethod
    def _load_model_sync():
        try:
            from transformers import CLIPModel, CLIPProcessor
            import torch

            logger.info("Loading CLIP model '%s' ...", _CLIP_MODEL)
            CLIPEmbeddingService._processor = CLIPProcessor.from_pretrained(_CLIP_MODEL)
            CLIPEmbeddingService._model = CLIPModel.from_pretrained(_CLIP_MODEL)
            CLIPEmbeddingService._model.eval()
            CLIPEmbeddingService._ready = True
            logger.info("CLIP model ready (dim=%d)", EMBEDDING_DIM)
        except ImportError as exc:
            logger.critical(
                "CLIP dependencies missing. Run: pip install transformers torch  (%s)", exc
            )
            raise
        except Exception as exc:
            logger.critical("CLIP model load failed: %s", exc)
            raise

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def embed_bytes(self, raw: bytes) -> Optional[List[float]]:
        self._validate(raw)
        img = self._decode(raw)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._run_clip_sync, img)

    async def embed_file(self, path: str) -> Optional[List[float]]:
        from pathlib import Path
        return await self.embed_bytes(Path(path).read_bytes())

    async def embed_batch(self, images: List[bytes]) -> List[Optional[List[float]]]:
        return list(await asyncio.gather(*(self.embed_bytes(b) for b in images)))

    @staticmethod
    def content_hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _validate(data: bytes):
        if not data:
            raise ValueError("Empty image data")
        if len(data) > _MAX_BYTES:
            raise ValueError(
                f"Image too large ({len(data) / 1_048_576:.1f} MB). "
                f"Max allowed: {_MAX_BYTES // 1_048_576} MB"
            )

    @staticmethod
    def _decode(data: bytes) -> Image.Image:
        try:
            img = Image.open(io.BytesIO(data))
            fmt = (img.format or "UNKNOWN").upper()
            if fmt not in _VALID_FMTS:
                raise ValueError(
                    f"Unsupported format '{fmt}'. Allowed: {', '.join(_VALID_FMTS)}"
                )
            return img.convert("RGB")
        except UnidentifiedImageError as exc:
            raise ValueError("Cannot decode image — file may be corrupt") from exc

    @staticmethod
    def _run_clip_sync(img: Image.Image) -> Optional[List[float]]:
        if not CLIPEmbeddingService._ready:
            raise RuntimeError("CLIP model not loaded")
        try:
            import torch

            inputs = CLIPEmbeddingService._processor(images=img, return_tensors="pt")
            with torch.no_grad():
                features = CLIPEmbeddingService._model.get_image_features(**inputs)
                normed = features / features.norm(dim=-1, keepdim=True)
            return normed.squeeze().cpu().numpy().tolist()
        except Exception as exc:
            logger.error("CLIP inference error: %s", exc)
            return None


async def get_embedding_service() -> CLIPEmbeddingService:
    return await CLIPEmbeddingService.get_instance()

_SETUP_HINT = """
Run the SQL in  backend/supabase_setup.sql  in your Supabase SQL Editor.
It creates:
  - property_embeddings table with vector(512) column
  - IVFFlat index for fast cosine similarity search
  - match_property_embeddings() RPC function
"""

class SupabaseVectorDB:

    TABLE = "property_embeddings"
    DIM = 512

    def __init__(self):
        self.enabled = False
        self.client: Optional[Client] = None

        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_KEY", "").strip()

        if not url or not key or url.startswith("your_") or key.startswith("your_"):
            logger.warning(
                "Supabase credentials missing or placeholder. "
                "Set SUPABASE_URL and SUPABASE_KEY in .env"
            )
            return

        if not _SUPABASE_LIB:
            logger.error("supabase-py not installed — run: pip install supabase")
            return

        try:
            self.client = create_client(url, key)
            self.client.table(self.TABLE).select("id").limit(1).execute()
            self.enabled = True
            logger.info("Supabase connected — table '%s' OK", self.TABLE)
        except Exception as exc:
            logger.error("Supabase init failed: %s\n%s", exc, _SETUP_HINT)

    def upsert_property(
        self,
        property_id: str,
        address: str,
        embedding: List[float],
        image_url: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not self._guard():
            return False

        if len(embedding) != self.DIM:
            logger.error(
                "Embedding dimension mismatch: expected %d, got %d",
                self.DIM, len(embedding),
            )
            return False

        row = {
            "property_id": property_id,
            "address": address,
            "embedding": embedding,
            "image_url": image_url or "",
            "metadata": metadata or {},
        }
        try:
            self.client.table(self.TABLE).upsert(row, on_conflict="property_id").execute()
            logger.info("Upserted embedding — property_id='%s'", property_id)
            return True
        except Exception as exc:
            logger.error("upsert_property failed for '%s': %s", property_id, exc)
            return False

    def similarity_search(
        self,
        query_embedding: List[float],
        limit: int = 5,
        threshold: float = 0.70,
    ) -> List[Dict[str, Any]]:
        if not self._guard():
            return []

        try:
            resp = self.client.rpc(
                "match_property_embeddings",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": threshold,
                    "match_count": limit,
                },
            ).execute()
            logger.info(
                "RPC search returned %d results (threshold=%.2f)",
                len(resp.data or []), threshold,
            )
            return resp.data or []
        except Exception as exc:
            logger.warning(
                "RPC 'match_property_embeddings' unavailable (%s). "
                "Run supabase_setup.sql to create it. "
                "Falling back to Python linear scan (NOT production-ready).",
                exc,
            )

        return self._python_scan(query_embedding, limit, threshold)

    def get_by_property_id(self, property_id: str) -> Optional[Dict[str, Any]]:
        if not self._guard():
            return None
        try:
            resp = (
                self.client.table(self.TABLE)
                .select("property_id, address, image_url, metadata, created_at, updated_at")
                .eq("property_id", property_id)
                .limit(1)
                .execute()
            )
            return resp.data[0] if resp.data else None
        except Exception as exc:
            logger.error("get_by_property_id('%s') failed: %s", property_id, exc)
            return None

    def delete_property(self, property_id: str) -> bool:
        if not self._guard():
            return False
        try:
            self.client.table(self.TABLE).delete().eq("property_id", property_id).execute()
            logger.info("Deleted embedding — property_id='%s'", property_id)
            return True
        except Exception as exc:
            logger.error("delete_property('%s') failed: %s", property_id, exc)
            return False

    def get_stats(self) -> Dict[str, Any]:
        base = {
            "enabled": self.enabled,
            "table": self.TABLE,
            "embedding_dimension": self.DIM,
        }
        if not self._guard():
            return {**base, "total_embeddings": 0}
        try:
            resp = self.client.table(self.TABLE).select("id", count="exact").execute()
            return {**base, "total_embeddings": resp.count or 0}
        except Exception as exc:
            return {**base, "error": str(exc)}

    def _guard(self) -> bool:
        if not self.enabled or self.client is None:
            logger.debug("Supabase not enabled — operation skipped")
            return False
        return True

    def _python_scan(
        self,
        query_vec: List[float],
        limit: int,
        threshold: float,
    ) -> List[Dict[str, Any]]:
        import numpy as np

        try:
            resp = (
                self.client.table(self.TABLE)
                .select("property_id, address, image_url, metadata, embedding")
                .execute()
            )
            rows = resp.data or []
        except Exception as exc:
            logger.error("Python scan fetch failed: %s", exc)
            return []

        q = np.array(query_vec, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm < 1e-8:
            return []

        scored = []
        for row in rows:
            emb = row.get("embedding")
            if not emb:
                continue
            v = np.array(emb, dtype=np.float32)
            v_norm = np.linalg.norm(v)
            if v_norm < 1e-8:
                continue
            sim = float(np.dot(q, v) / (q_norm * v_norm))
            if sim >= threshold:
                scored.append({
                    "property_id": row["property_id"],
                    "address": row["address"],
                    "image_url": row.get("image_url", ""),
                    "metadata": row.get("metadata", {}),
                    "similarity": round(sim, 4),
                })

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:limit]


vector_db = SupabaseVectorDB()