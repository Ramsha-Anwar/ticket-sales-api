from app.db.database import Base
import app.models  # noqa: F401 — import triggers model registration

print("Tables registered in metadata:")
for table_name in sorted(Base.metadata.tables.keys()):
    print(f"  - {table_name}")