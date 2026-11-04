"""All settings and tunable knobs, read from environment variables / .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://rag:rag@localhost:5432/rag"

    # Voyage AI (embeddings + rerank)
    voyage_api_key: str = ""
    embed_model: str = "voyage-4-lite"
    embed_dim: int = 1024
    embed_batch_size: int = 128
    rerank_model: str = "rerank-2.5"

    # Gemini (generation)
    gemini_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 500

    # Chunking (phase 1)
    chunk_tokens: int = 350
    chunk_overlap: int = 50

    # Retrieval (phase 2)
    k_vec: int = 20
    k_bm25: int = 20              # candidates per BM25 keyword search (pg_textsearch)
    rrf_k: int = 60
    rerank_candidates: int = 30
    rerank_min_score: float = 0.50  # rerank-2.5: off-topic hits scored up to ~0.45, relevant ones 0.50+
    final_top_n: int = 6


settings = Settings()
