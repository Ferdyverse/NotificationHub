"""Pydantic schemas for form validation and type safety."""

from typing import Optional

from pydantic import BaseModel, Field, validator


class MatrixRouteConfig(BaseModel):
    """Matrix delivery route configuration."""

    homeserver: str = Field(..., min_length=1, description="Matrix homeserver URL")
    room_id: str = Field(..., min_length=1, description="Matrix room ID")
    username: Optional[str] = Field(None, description="Matrix username for login")
    password: Optional[str] = Field(None, description="Matrix password for login")
    markdown: Optional[bool] = Field(False, description="Use markdown formatting")
    auto_join: Optional[bool] = Field(False, description="Auto-join room if not member")
    bearer_token: Optional[str] = Field(None, description="Matrix bearer token")

    @validator("homeserver")
    def validate_homeserver_url(cls, v):
        """Ensure homeserver is a valid URL."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Homeserver must start with http:// or https://")
        return v

    class Config:
        title = "Matrix Route Configuration"


class DiscordRouteConfig(BaseModel):
    """Discord delivery route configuration."""

    webhook_url: str = Field(..., min_length=1, description="Discord webhook URL")
    bearer_token: Optional[str] = Field(None, description="Discord bearer token")
    use_embed: Optional[bool] = Field(False, description="Use embedded messages")
    embed_color: Optional[str] = Field(None, description="Embed color (hex)")

    @validator("webhook_url")
    def validate_webhook_url(cls, v):
        """Ensure webhook URL starts with https."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Webhook URL must start with http:// or https://")
        return v

    @validator("embed_color")
    def validate_embed_color(cls, v):
        """Validate hex color format."""
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        # Allow #RRGGBB, 0xRRGGBB, or RRGGBB
        if v.startswith("#"):
            v = v[1:]
        if v.lower().startswith("0x"):
            v = v[2:]
        if len(v) != 6 or not all(c in "0123456789abcdefABCDEF" for c in v):
            raise ValueError("Embed color must be a valid hex color (e.g., #FF5733)")
        return v

    class Config:
        title = "Discord Route Configuration"


class EmailRouteConfig(BaseModel):
    """Email delivery route configuration."""

    smtp_host: str = Field(..., min_length=1, description="SMTP server hostname")
    smtp_port: int = Field(..., ge=1, le=65535, description="SMTP server port")
    smtp_tls: Optional[bool] = Field(False, description="Use TLS (implicit)")
    smtp_starttls: Optional[bool] = Field(False, description="Use STARTTLS")
    smtp_username: Optional[str] = Field(None, description="SMTP username")
    smtp_password: Optional[str] = Field(None, description="SMTP password")
    from_addr: str = Field(..., min_length=1, description="From email address")
    to_addrs: str = Field(..., min_length=1, description="To email addresses (comma-separated)")
    subject_prefix: Optional[str] = Field(None, description="Subject prefix")

    @validator("from_addr")
    def validate_email(cls, v):
        """Basic email validation."""
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email address format")
        return v

    @validator("to_addrs")
    def validate_to_addrs(cls, v):
        """Validate comma-separated email addresses."""
        if not v.strip():
            raise ValueError("At least one destination email required")
        return v

    class Config:
        title = "Email Route Configuration"


class RouteCreateRequest(BaseModel):
    """Request schema for creating/updating a route."""

    name: str = Field(..., min_length=1, max_length=120, description="Route name")
    route_type: str = Field(..., description="Route type (matrix, discord, email)")
    template_id: Optional[int] = Field(None, description="Template ID for this route")
    matrix_homeserver: Optional[str] = Field(None)
    matrix_room_id: Optional[str] = Field(None)
    matrix_username: Optional[str] = Field(None)
    matrix_password: Optional[str] = Field(None)
    matrix_markdown: Optional[bool] = Field(None)
    matrix_auto_join: Optional[bool] = Field(None)
    matrix_bearer_token: Optional[str] = Field(None)
    discord_webhook_url: Optional[str] = Field(None)
    discord_bearer_token: Optional[str] = Field(None)
    discord_use_embed: Optional[bool] = Field(None)
    discord_embed_color: Optional[str] = Field(None)
    email_smtp_host: Optional[str] = Field(None)
    email_smtp_port: Optional[str] = Field(None)
    email_smtp_tls: Optional[bool] = Field(None)
    email_smtp_starttls: Optional[bool] = Field(None)
    email_smtp_username: Optional[str] = Field(None)
    email_smtp_password: Optional[str] = Field(None)
    email_from_addr: Optional[str] = Field(None)
    email_to_addrs: Optional[str] = Field(None)
    email_subject_prefix: Optional[str] = Field(None)

    @validator("route_type")
    def validate_route_type(cls, v):
        """Ensure route type is valid."""
        if v not in ("matrix", "discord", "email"):
            raise ValueError("route_type must be one of: matrix, discord, email")
        return v

    def get_config_for_type(self) -> dict:
        """Extract configuration dict for the specified route type."""
        if self.route_type == "matrix":
            return {
                "homeserver": self.matrix_homeserver,
                "room_id": self.matrix_room_id,
                "username": self.matrix_username,
                "password": self.matrix_password,
                "markdown": self.matrix_markdown or False,
                "auto_join": self.matrix_auto_join or False,
                "bearer_token": self.matrix_bearer_token,
            }
        elif self.route_type == "discord":
            return {
                "webhook_url": self.discord_webhook_url,
                "bearer_token": self.discord_bearer_token,
                "use_embed": self.discord_use_embed or False,
                "embed_color": self.discord_embed_color,
            }
        elif self.route_type == "email":
            port_val = int(self.email_smtp_port) if self.email_smtp_port else 0
            return {
                "smtp_host": self.email_smtp_host,
                "smtp_port": port_val,
                "smtp_tls": self.email_smtp_tls or False,
                "smtp_starttls": self.email_smtp_starttls or False,
                "smtp_username": self.email_smtp_username,
                "smtp_password": self.email_smtp_password,
                "from_addr": self.email_from_addr,
                "to_addrs": self.email_to_addrs,
                "subject_prefix": self.email_subject_prefix,
            }
        return {}

    class Config:
        title = "Route Create/Update Request"
