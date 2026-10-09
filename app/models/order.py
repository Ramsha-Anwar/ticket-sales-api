from sqlalchemy import Column, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    seat_id = Column(
        Integer,
        ForeignKey("seats.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    seat = relationship("Seat", back_populates="order")
    