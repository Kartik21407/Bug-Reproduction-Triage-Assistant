"""Sentence embeddings: all-MiniLM-L6-v2 through fastembed (D11).

The model is loaded on the first call, not at import, so importing the
application never downloads or loads it. Every caller reaches it through
this module's `embed` function by attribute (`embedding.embed(...)`), which
is what lets the test suite replace it with a deterministic stand-in and
never load the real model.
"""

from typing import Any

from app.config import get_settings

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# The longest text embedded, in characters. The model reads at most a few
# hundred tokens anyway, so a longer text only costs time without changing
# the result.
MAX_EMBEDDED_CHARACTERS = 2000

_model: Any = None


class EmbeddingUnavailableError(RuntimeError):
    """The model could not be loaded or run, most often because its one-time
    download failed. Callers turn this into a clear message rather than a
    crash; nothing is half written when it is raised."""


def _load_model() -> Any:
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(
            model_name=EMBEDDING_MODEL, cache_dir=get_settings().embedding_cache_dir
        )
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    """One unit-length vector per text, in order. Cosine similarity between
    two of them is their dot product."""
    if not texts:
        return []
    trimmed = [text[:MAX_EMBEDDED_CHARACTERS] for text in texts]
    try:
        return [vector.tolist() for vector in _load_model().embed(trimmed)]
    except Exception as error:
        raise EmbeddingUnavailableError(
            f"The similarity model could not be loaded or run ({type(error).__name__})"
        ) from error
