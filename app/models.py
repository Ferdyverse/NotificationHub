from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.utcnow()


ingress_routes = Table(
    "ingress_routes",
    Base.metadata,
    Column("ingress_id", Integer, ForeignKey("ingresses.id"), primary_key=True),
    Column("route_id", Integer, ForeignKey("routes.id"), primary_key=True),
)


class Ingress(Base):
    __tablename__ = "ingresses"
    __allow_unmapped__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    secret_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    default_template_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("templates.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    default_template = relationship("Template")
    routes = relationship("Route", secondary=ingress_routes)


class Route(Base):
    __tablename__ = "routes"
    __allow_unmapped__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    route_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        MutableDict.as_mutable(JSON), nullable=True
    )
    template_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("templates.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    template = relationship("Template")


class Template(Base):
    __tablename__ = "templates"
    __allow_unmapped__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    title_template: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    discord_embed_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    show_raw: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class EventLog(Base):
    __tablename__ = "event_logs"
    __allow_unmapped__ = True
    __table_args__ = (
        Index("ix_event_logs_created_at", "created_at"),
        Index("ix_event_logs_ingress_id", "ingress_id"),
        Index("ix_event_logs_delivery_status", "delivery_status"),
        Index("ix_event_logs_source", "source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingress_id: Mapped[int] = mapped_column(Integer, ForeignKey("ingresses.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    source: Mapped[str] = mapped_column(String(120), nullable=False)
    event: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    entities: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    raw: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    request_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    delivery_status: Mapped[str] = mapped_column(String(20), nullable=False)
    delivery_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ingress = relationship("Ingress")


class RuntimeConfig(Base):
    __tablename__ = "runtime_config"
    __allow_unmapped__ = True

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
