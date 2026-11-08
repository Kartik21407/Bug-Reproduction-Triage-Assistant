"""Column types shared by more than one model module.

`Embedding` is a pgvector `vector(384)` on PostgreSQL and a JSON list of
floats on any other database. PostgreSQL is what runs in Docker and in
production, and is where cosine distance is computed (ADR-003, D11); the
JSON fallback exists only so the same models still create and round-trip
on the SQLite database the test suite uses (ADR-013).
"""

from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator, TypeEngine

# all-MiniLM-L6-v2 produces 384 dimensions. The migration that creates every
# embedding column repeats this number, so the two must change together.
EMBEDDING_DIMENSIONS = 384


class Embedding(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(EMBEDDING_DIMENSIONS))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: list[float] | None, dialect: Dialect) -> Any:
        if value is None:
            return None
        return [float(component) for component in value]

    def process_result_value(self, value: Any, dialect: Dialect) -> list[float] | None:
        if value is None:
            return None
        # pgvector returns a numpy array; JSON returns a list. Both become a
        # plain list so nothing above this layer depends on numpy.
        return [float(component) for component in value]
