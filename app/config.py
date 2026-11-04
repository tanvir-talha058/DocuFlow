from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    notifications_mailbox: str = "docuflow-notifications@yourorg.com"

    session_secret: str = "change-me-to-a-random-secret"
    database_url: str = "sqlite:///./app.db"
    upload_dir: str = "./uploads"
    base_url: str = "http://localhost:8000"

    use_fake_graph: bool = True

    # Employees sign up/log in with an email+password account, restricted to
    # this work-email domain, until real Azure AD/Entra SSO replaces it.
    allowed_email_domain: str = "upaybd.com"

    approval_token_ttl_hours: int = 72
    storage_quota_bytes: int = 5 * 1024**3  # 5 GB soft quota shown on the dashboard

    # Mail delivery: "fake" (writes dev_outbox.json, no network), "smtp", or
    # "graph" (Microsoft Graph sendMail, same as before). Independent of
    # use_fake_graph, which only controls the directory-search path.
    mail_provider: str = "fake"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_from_email: str = "docuflow-notifications@yourorg.com"
    smtp_from_name: str = "DocuFlow"


settings = Settings()
