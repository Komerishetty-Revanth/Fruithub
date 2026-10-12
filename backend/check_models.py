from app.core.database import Base
import app.models

print("Tables found:", sorted(Base.metadata.tables.keys()))