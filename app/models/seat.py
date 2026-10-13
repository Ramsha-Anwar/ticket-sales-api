from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class Seat(Base):
    __tablename__ = "seats"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seat_number = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, server_default="free")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    event = relationship("Event", back_populates="seats")
    order = relationship("Order", back_populates="seat", uselist=False)

    __table_args__ = (
        UniqueConstraint("event_id", "seat_number", name="uq_seats_event_seat_number"),
        CheckConstraint("status IN ('free', 'reserved')", name="ck_seats_status"),
        Index("ix_seats_event_id_status", "event_id", "status"),
    )