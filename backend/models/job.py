from sqlalchemy import Column, Integer, String, Text
from backend.database.base import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    title = Column(String(255))
    company = Column(String(255))
    description = Column(Text)