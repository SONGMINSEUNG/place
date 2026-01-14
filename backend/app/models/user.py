from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base


class MembershipType(str, enum.Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    membership_type = Column(
        Enum(MembershipType),
        default=MembershipType.FREE
    )
    membership_expires_at = Column(DateTime, nullable=True)
    daily_search_count = Column(Integer, default=0)
    last_search_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    saved_keywords = relationship("SavedKeyword", back_populates="user")
    search_history = relationship("PlaceSearch", back_populates="user")
    input_data = relationship("UserInputData", back_populates="user")
    activity_logs = relationship("UserActivityLog", back_populates="user")

    @property
    def daily_limit(self) -> int:
        limits = {
            MembershipType.FREE: 10,
            MembershipType.BASIC: 50,
            MembershipType.PRO: 200,
            MembershipType.ENTERPRISE: 1000
        }
        return limits.get(self.membership_type, 10)
