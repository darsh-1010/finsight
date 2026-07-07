from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Broker(Base):
    __tablename__ = "brokers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    redirect_url = Column(String, nullable=False)

    clicks = relationship(
        "BrokerClick",
        back_populates="broker",
        cascade="all, delete-orphan",
    )


class BrokerClick(Base):
    __tablename__ = "broker_clicks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )
    broker_id = Column(
        Integer,
        ForeignKey("brokers.id"),
        nullable=False,
    )

    clicked_at = Column(
        DateTime,
        server_default=func.now(),
    )

    user = relationship("User")
    broker = relationship(
        "Broker",
        back_populates="clicks",
    )
