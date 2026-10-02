# Deferred Work

Technical debt and improvements deferred from code reviews and implementation.

## Deferred from: code review of MSCL-5 (2026-10-02)

- **N+1 query problem** — query_relationships called once per resource instead of batching [manager.py:789, 892]. Performance optimization: batch query all relationships upfront.
- **Sequential resource processing** — Lambda and S3 resources processed serially, should use asyncio.gather for concurrency [manager.py:728-748]. Performance optimization: process resources concurrently.
