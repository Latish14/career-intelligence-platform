from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Mapped, relationship
from backend.database.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    resumes = relationship(
    "Resume",
    back_populates="user",
    cascade="all, delete-orphan",
    )

    reports = relationship(
        "Report",
        back_populates="user",
        cascade="all, delete-orphan",
    )