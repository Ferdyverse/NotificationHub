from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text
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
    default_route_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("routes.id"), nullable=True
    )
    default_template_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("templates.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    default_route = relationship("Route")
    default_template = relationship("Template")
    routes = relationship("Route", secondary=ingress_routes)
    rules = relationship("Rule", back_populates="ingress")


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


class Rule(Base):
    __tablename__ = "rules"
    __allow_unmapped__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ingress_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ingresses.id"), nullable=True
    )
    route_id: Mapped[int] = mapped_column(Integer, ForeignKey("routes.id"))
    template_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("templates.id"), nullable=True
    )
    conditions: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    ingress = relationship("Ingress", back_populates="rules")
    route = relationship("Route")
    template = relationship("Template")


class EventLog(Base):
    __tablename__ = "event_logs"
    __allow_unmapped__ = True

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

    delivery_status: Mapped[str] = mapped_column(String(20), nullable=False)
    delivery_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ingress = relationship("Ingress")
