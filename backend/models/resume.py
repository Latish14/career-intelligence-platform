from sqlalchemy import Column, Integer, String, Text
from backend.database.base import Base

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True)
    filename = Column(String(255))
    raw_text = Column(Text)