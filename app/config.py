import os


class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./taxi_ops.db")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 720
    refresh_token_ttl_days: int = 30
    bcrypt_rounds: int = 12

    bank_name: str = os.getenv("BANK_NAME", "FNB (First National Bank)")
    bank_account_holder: str = os.getenv("BANK_ACCOUNT_HOLDER", "Justice Ndou")
    bank_account_number: str = os.getenv("BANK_ACCOUNT_NUMBER", "63168230563")
    bank_branch_code: str = os.getenv("BANK_BRANCH_CODE", "255005")


settings = Settings()
