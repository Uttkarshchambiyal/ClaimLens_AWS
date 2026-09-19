from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP
import os


@dataclass(frozen=True)
class Settings:
    app_mode: str = os.getenv("APP_MODE", "production")
    aws_region: str = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-south-1"))
    records_table: str = os.getenv("RECORDS_TABLE", "")
    documents_bucket: str = os.getenv("DOCUMENTS_BUCKET", "")
    state_machine_arn: str = os.getenv("STATE_MACHINE_ARN", "")
    bedrock_model_id: str = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
    tenant_claim: str = os.getenv("TENANT_CLAIM", "custom:tenant_id")
    money_tolerance_paise: int = int(os.getenv("MONEY_TOLERANCE_PAISE", "100"))
    stay_day_allowance: int = int(os.getenv("STAY_DAY_ALLOWANCE", "1"))
    rounding_mode: str = os.getenv("ROUNDING_MODE", "HALF_UP")
    date_order: str = os.getenv("DATE_ORDER", "ISO_ONLY")
    upload_expiry_seconds: int = int(os.getenv("UPLOAD_EXPIRY_SECONDS", "900"))
    retention_days: int = int(os.getenv("RETENTION_DAYS", "90"))
    min_field_confidence: float = float(os.getenv("MIN_FIELD_CONFIDENCE", "80"))
    use_bedrock: bool = os.getenv("USE_BEDROCK", "true").lower() == "true"

    @property
    def decimal_rounding(self):
        return ROUND_HALF_EVEN if self.rounding_mode == "HALF_EVEN" else ROUND_HALF_UP


def require_production(settings: Settings) -> None:
    if settings.app_mode == "mock":
        raise RuntimeError("Mock adapter cannot be used from the production Lambda entry point")
    missing = [name for name, value in {
        "RECORDS_TABLE": settings.records_table,
        "DOCUMENTS_BUCKET": settings.documents_bucket,
        "STATE_MACHINE_ARN": settings.state_machine_arn,
    }.items() if not value]
    if missing:
        raise RuntimeError(f"Missing production configuration: {', '.join(missing)}")
