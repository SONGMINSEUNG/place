"""
Custom Exceptions
서비스 전용 예외 클래스 정의
"""
from typing import Optional, Dict, Any


class PlaceAnalyticsException(Exception):
    """Base exception for Place Analytics service"""

    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details
            }
        }


# ===========================================
# Validation Errors (2000)
# ===========================================
class ValidationError(PlaceAnalyticsException):
    """Input validation error"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="2001-001",
            status_code=400,
            details=details
        )


class KeywordNotFoundError(PlaceAnalyticsException):
    """Keyword search returned no results"""

    def __init__(self, keyword: str):
        super().__init__(
            message=f"검색 결과가 없습니다: '{keyword}'",
            code="2001-002",
            status_code=404,
            details={"keyword": keyword}
        )


class PlaceNotFoundError(PlaceAnalyticsException):
    """Place not found in search results"""

    def __init__(self, place_name: str, keyword: str):
        super().__init__(
            message=f"'{keyword}' 검색 결과에서 '{place_name}'을(를) 찾을 수 없습니다.",
            code="2001-003",
            status_code=404,
            details={"place_name": place_name, "keyword": keyword}
        )


# ===========================================
# External API Errors (3000)
# ===========================================
class ExternalAPIError(PlaceAnalyticsException):
    """External API call failed"""

    def __init__(self, message: str = "외부 서비스 연결에 실패했습니다.", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="3001-001",
            status_code=502,
            details=details
        )


class AdlogAPIError(ExternalAPIError):
    """ADLOG API specific error"""

    def __init__(self, message: str = "분석 서비스가 일시적으로 지연됩니다.", details: Optional[Dict] = None):
        super().__init__(message=message, details=details)
        self.code = "3001-002"


class AdlogAPITimeoutError(ExternalAPIError):
    """ADLOG API timeout"""

    def __init__(self):
        super().__init__(
            message="분석 서비스 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.",
            details={"retry_after": 60}
        )
        self.code = "3001-003"


# ===========================================
# Database Errors (4000)
# ===========================================
class DatabaseError(PlaceAnalyticsException):
    """Database operation failed"""

    def __init__(self, message: str = "데이터베이스 오류가 발생했습니다.", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="4001-001",
            status_code=500,
            details=details
        )


class DatabaseConnectionError(DatabaseError):
    """Database connection failed"""

    def __init__(self):
        super().__init__(message="서비스 점검 중입니다. 잠시 후 다시 시도해주세요.")
        self.code = "4001-002"


# ===========================================
# ML/Model Errors (5000)
# ===========================================
class ModelError(PlaceAnalyticsException):
    """ML model error"""

    def __init__(self, message: str = "예측 모델 오류가 발생했습니다.", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="5001-001",
            status_code=500,
            details=details
        )


class ModelNotTrainedError(ModelError):
    """Model not trained yet"""

    def __init__(self):
        super().__init__(
            message="예측 모델이 아직 학습되지 않았습니다. 데이터를 더 수집 중입니다.",
            details={"status": "training_in_progress"}
        )
        self.code = "5001-002"


class InsufficientDataError(ModelError):
    """Not enough data for training"""

    def __init__(self, current_count: int, required_count: int):
        super().__init__(
            message=f"학습에 필요한 데이터가 부족합니다. (현재: {current_count}개, 필요: {required_count}개)",
            details={"current_count": current_count, "required_count": required_count}
        )
        self.code = "5001-003"


# ===========================================
# Rate Limit Errors (6000)
# ===========================================
class RateLimitError(PlaceAnalyticsException):
    """Rate limit exceeded"""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            message=f"요청이 너무 많습니다. {retry_after}초 후 다시 시도해주세요.",
            code="6001-001",
            status_code=429,
            details={"retry_after": retry_after}
        )


# ===========================================
# Authentication Errors (1000)
# ===========================================
class AuthenticationError(PlaceAnalyticsException):
    """Authentication failed"""

    def __init__(self, message: str = "인증에 실패했습니다."):
        super().__init__(
            message=message,
            code="1001-001",
            status_code=401
        )


class TokenExpiredError(AuthenticationError):
    """Token expired"""

    def __init__(self):
        super().__init__(message="토큰이 만료되었습니다. 다시 로그인해주세요.")
        self.code = "1001-002"


class InvalidTokenError(AuthenticationError):
    """Invalid token"""

    def __init__(self):
        super().__init__(message="유효하지 않은 토큰입니다.")
        self.code = "1001-003"
