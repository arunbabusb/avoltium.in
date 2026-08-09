"""
Token optimization layer for Avoltium.in
- Caches AI generation results to reduce redundant API calls
- Implements content batching for efficient token usage
- Provides cost analysis and monitoring
"""

import sqlite3
import json
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("token_cache")


class TokenCache:
    """SQLite-based cache for generated content and API responses."""

    def __init__(self, db_path: str = "token_cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database with schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS content_cache (
                    id INTEGER PRIMARY KEY,
                    hash TEXT UNIQUE NOT NULL,
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSON,
                    tokens_saved INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_calls (
                    id INTEGER PRIMARY KEY,
                    endpoint TEXT NOT NULL,
                    request_hash TEXT UNIQUE,
                    response TEXT,
                    tokens_used INTEGER,
                    cost_usd REAL,
                    cached BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS generation_batches (
                    id INTEGER PRIMARY KEY,
                    batch_name TEXT UNIQUE,
                    topic TEXT,
                    count INTEGER,
                    total_tokens INTEGER,
                    total_cost REAL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def get_content_hash(self, topic: str, params: Dict[str, Any]) -> str:
        """Generate unique hash for content request."""
        key = f"{topic}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(key.encode()).hexdigest()

    def get_cached_content(self, topic: str, params: Dict[str, Any]) -> Optional[str]:
        """Retrieve cached content if available and not expired."""
        content_hash = self.get_content_hash(topic, params)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT content, tokens_saved FROM content_cache
                WHERE hash = ? AND (expires_at IS NULL OR expires_at > datetime('now'))
                LIMIT 1
            """, (content_hash,))

            result = cursor.fetchone()
            if result:
                logger.info(f"✓ Cache hit for {topic}: {result[1]} tokens saved")
                return result[0]

        return None

    def cache_content(
        self,
        topic: str,
        content: str,
        params: Dict[str, Any],
        tokens_saved: int = 0,
        ttl_days: int = 90
    ):
        """Store generated content in cache."""
        content_hash = self.get_content_hash(topic, params)
        expires_at = datetime.utcnow() + timedelta(days=ttl_days)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO content_cache
                (hash, topic, content, tokens_saved, expires_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                content_hash,
                topic,
                content,
                tokens_saved,
                expires_at.isoformat(),
                json.dumps({"cached": True})
            ))
            conn.commit()

        logger.info(f"✓ Cached content for {topic}")

    def log_api_call(
        self,
        endpoint: str,
        tokens_used: int,
        cached: bool = False,
        cost_usd: float = 0.0
    ):
        """Log API call metrics for cost tracking."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO api_calls (endpoint, tokens_used, cost_usd, cached)
                VALUES (?, ?, ?, ?)
            """, (endpoint, tokens_used, cost_usd, cached))
            conn.commit()

    def get_cost_analysis(self, days: int = 30) -> Dict[str, Any]:
        """Analyze token usage and costs over time period."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_calls,
                    SUM(tokens_used) as total_tokens,
                    SUM(cost_usd) as total_cost,
                    SUM(CASE WHEN cached THEN 1 ELSE 0 END) as cached_calls,
                    endpoint
                FROM api_calls
                WHERE created_at > datetime('now', '-' || ? || ' days')
                GROUP BY endpoint
                ORDER BY total_tokens DESC
            """, (days,))

            results = cursor.fetchall()

        analysis = {
            "period_days": days,
            "summary": {
                "total_api_calls": sum(r[0] for r in results),
                "total_tokens": sum(r[1] for r in results) if results else 0,
                "total_cost_usd": sum(r[2] for r in results) if results else 0.0,
                "cached_hits": sum(r[3] for r in results) if results else 0,
            },
            "by_endpoint": [
                {
                    "endpoint": r[4],
                    "calls": r[0],
                    "tokens": r[1],
                    "cost": r[2],
                    "cached": r[3]
                }
                for r in results
            ]
        }

        return analysis

    def create_batch(
        self,
        batch_name: str,
        topic: str,
        count: int
    ) -> int:
        """Create a new generation batch for tracking."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO generation_batches (batch_name, topic, count, status)
                VALUES (?, ?, ?, 'pending')
            """, (batch_name, topic, count))
            conn.commit()
            return cursor.lastrowid

    def batch_status(self, batch_name: str) -> Optional[Dict[str, Any]]:
        """Get status of a generation batch."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, batch_name, topic, count, total_tokens,
                       total_cost, status, created_at
                FROM generation_batches
                WHERE batch_name = ?
            """, (batch_name,))

            result = cursor.fetchone()
            if result:
                return {
                    "id": result[0],
                    "batch_name": result[1],
                    "topic": result[2],
                    "count": result[3],
                    "total_tokens": result[4],
                    "total_cost": result[5],
                    "status": result[6],
                    "created_at": result[7]
                }

        return None

    def update_batch(
        self,
        batch_name: str,
        tokens: int = 0,
        cost: float = 0.0,
        status: str = None
    ):
        """Update batch metrics."""
        with sqlite3.connect(self.db_path) as conn:
            if status:
                conn.execute("""
                    UPDATE generation_batches
                    SET total_tokens = total_tokens + ?,
                        total_cost = total_cost + ?,
                        status = ?
                    WHERE batch_name = ?
                """, (tokens, cost, status, batch_name))
            else:
                conn.execute("""
                    UPDATE generation_batches
                    SET total_tokens = total_tokens + ?,
                        total_cost = total_cost + ?
                    WHERE batch_name = ?
                """, (tokens, cost, batch_name))
            conn.commit()

    def clear_expired(self) -> int:
        """Remove expired cache entries."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM content_cache
                WHERE expires_at IS NOT NULL AND expires_at < datetime('now')
            """)
            conn.commit()
            return cursor.rowcount


# Singleton instance
_cache = None


def get_cache(db_path: str = "token_cache.db") -> TokenCache:
    """Get or create cache instance."""
    global _cache
    if _cache is None:
        _cache = TokenCache(db_path)
    return _cache


if __name__ == "__main__":
    # Example usage
    cache = get_cache()

    # Simulate API call
    cache.log_api_call("gemini", tokens_used=1250, cost_usd=0.025)
    cache.log_api_call("gemini", tokens_used=800, cost_usd=0.016, cached=True)

    # Create and track batch
    batch_id = cache.create_batch("article_batch_001", "technology", 10)
    cache.update_batch("article_batch_001", tokens=5000, cost=0.10, status="in_progress")

    # Cache content
    cache.cache_content("python_tips", "Article about Python...", {"length": "1500"}, tokens_saved=800)

    # Get analysis
    analysis = cache.get_cost_analysis(days=30)
    print(json.dumps(analysis, indent=2))
