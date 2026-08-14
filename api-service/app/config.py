"""Cấu hình đọc từ biến môi trường — bản thay `application.yml`.

Hai luật giữ nguyên từ bên Spring:

1. **Không hardcode giá trị nào** (ràng buộc #6). Mọi mục có mặc định, và mặc định trong
   file này CHÍNH LÀ cấu hình chạy local. Thêm config mới thì phải thêm vào `.env.example`
   và bảng "Biến môi trường" trong `README.md`.
2. **Giữ nguyên TÊN biến môi trường.** `.env` ở thư mục gốc repo đang phục vụ backend
   Spring; api-service đọc đúng bộ biến đó nên hai backend chạy song song không cần hai file
   cấu hình. Đổi tên biến ở đây là bắt người dùng bảo trì hai bản `.env` lệch nhau.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
API_SERVICE_ROOT = Path(__file__).resolve().parent.parent

#: Múi giờ mặc định. Là hằng số vì cả `Field(default=...)` lẫn nhánh bỏ qua giá trị rác của
#: nền tảng (xem `_bo_qua_tz_cua_nen_tang`) đều phải rơi về đúng một giá trị.
TZ_MAC_DINH = "Asia/Ho_Chi_Minh"


class Settings(BaseSettings):
    # Hai ứng viên `.env` vì working directory khác nhau tuỳ cách chạy — giống hệt
    # `spring.config.import` bên Java:
    #   thư mục gốc repo -> chạy `uvicorn` từ gốc, hoặc pytest từ gốc
    #   api-service/     -> chạy từ trong thư mục service
    # Trong container thì không có file nào, biến đến thẳng từ compose — nên không lỗi.
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", API_SERVICE_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- HTTP server ---
    server_address: str = Field(default="127.0.0.1", alias="SERVER_ADDRESS")
    server_port: int = Field(default=8080, alias="SERVER_PORT")

    # --- Database ---
    # Ghép phẳng từ mảnh, không lồng placeholder — y như bên Java. docker compose set
    # DB_HOST=db và DB_PORT=5432 (toạ độ trong mạng nội bộ). Chạy ngoài container thì mặc
    # định localhost + DB_PORT của .env, tức cổng publish trên host.
    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str = Field(default="ielts", alias="DB_NAME")
    db_user: str = Field(default="ielts", alias="DB_USER")
    db_password: str = Field(default="ielts", alias="DB_PASSWORD")

    # Bổ sung so với application.yml, và là bổ sung bắt buộc: Supabase/Vercel phát một
    # chuỗi kết nối duy nhất chứ không phát năm mảnh rời. Để rỗng thì ghép từ DB_* như cũ,
    # nên đường chạy local không đổi hành vi.
    database_url: str = Field(default="", alias="DATABASE_URL")

    # --- Gemini ---
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com", alias="GEMINI_BASE_URL"
    )
    # Ba mức vì độ dài output khác nhau một bậc. Dịch một từ vài trăm token; sinh một lô
    # 10 câu quiz vài nghìn.
    gemini_timeout_seconds: int = Field(default=15, alias="GEMINI_TIMEOUT_SECONDS")
    gemini_quiz_generate_timeout_seconds: int = Field(
        default=30, alias="GEMINI_QUIZ_GENERATE_TIMEOUT_SECONDS"
    )
    gemini_quiz_grade_timeout_seconds: int = Field(
        default=20, alias="GEMINI_QUIZ_GRADE_TIMEOUT_SECONDS"
    )
    gemini_retry_backoff_millis: int = Field(default=1000, alias="GEMINI_RETRY_BACKOFF_MS")

    # --- Extension ---
    extension_id: str = Field(default="", alias="EXTENSION_ID")

    # --- Web app (cùng origin với backend) ---
    # Thư mục chứa SPA đã build, tương đối so với `api-service/`.
    #
    # VẮNG MẶT LÀ BÌNH THƯỜNG: chạy backend-only, hoặc chạy test, thì không ai build web cả.
    # `app/web_static.py` bỏ qua và ghi một dòng log thay vì ném — ném ở đây là biến một bộ
    # test đang xanh thành FileNotFoundError ở một file trông chẳng liên quan gì.
    web_static_dir: str = Field(default="static", alias="WEB_STATIC_DIR")
    # Origin công khai của web, dùng để DỰNG redirect_uri phía server. Không bao giờ lấy từ
    # `request.base_url` hay header `Host` — đó là đường Host header injection.
    web_base_url: str = Field(default="http://127.0.0.1:8080", alias="WEB_BASE_URL")

    # --- Auth ---
    auth_google_client_id: str = Field(default="", alias="AUTH_GOOGLE_CLIENT_ID")
    # CHỈ sống ở backend. Không bao giờ được xuất hiện trong bundle extension.
    auth_google_client_secret: str = Field(default="", alias="AUTH_GOOGLE_CLIENT_SECRET")
    auth_google_token_url: str = Field(
        default="https://oauth2.googleapis.com", alias="AUTH_GOOGLE_TOKEN_URL"
    )
    # Rỗng = KHÓA HẾT, cố ý: cấu hình thiếu phải làm hệ thống đóng lại chứ không mở toang
    # cho mọi tài khoản Google trên đời.
    auth_allowed_emails: str = Field(default="", alias="AUTH_ALLOWED_EMAILS")
    auth_session_days: int = Field(default=60, alias="AUTH_SESSION_DAYS")
    # Authorization endpoint của Google. KHÔNG tái dùng `auth_google_token_url` được: cái đó
    # là base_url của httpx client và code POST vào path `/token`, còn đây là một URL đầy đủ
    # để redirect trình duyệt tới.
    auth_google_auth_url: str = Field(
        default="https://accounts.google.com/o/oauth2/v2/auth", alias="AUTH_GOOGLE_AUTH_URL"
    )
    # `auto` | `true` | `false`. Kiểu `str` chứ KHÔNG `bool | None`: pydantic không coi chuỗi
    # rỗng là None, nên `AUTH_COOKIE_SECURE=` trong .env sẽ ném lỗi parse lúc khởi động.
    #
    # KHÔNG suy cờ này từ `request.url.scheme`: Dockerfile chạy uvicorn không có
    # `--proxy-headers` và không dòng nào đọc `X-Forwarded-Proto`, nên sau Caddy (terminate
    # TLS) app luôn thấy `http`. Suy từ đó là lặng lẽ phát cookie phiên KHÔNG Secure trên
    # production HTTPS — không lỗi, không cảnh báo.
    auth_cookie_secure: str = Field(default="auto", alias="AUTH_COOKIE_SECURE")
    # 0 = tắt hạn mức (chỉ dùng ở máy dev).
    auth_daily_gemini_calls: int = Field(default=300, alias="AUTH_DAILY_GEMINI_CALLS")
    # Email chủ sở hữu dữ liệu cũ — V6 dùng nó để backfill vocab_entry.user_id.
    # KHÔNG đặt default: chạy migration với một email đoán bừa sẽ gán toàn bộ sổ từ cho một
    # tài khoản không ai đăng nhập được, mà migration thì không chạy lại.
    auth_bootstrap_email: str = Field(default="", alias="AUTH_BOOTSTRAP_EMAIL")

    # Lịch ôn tính "hôm nay" theo giờ hệ thống. Không có biến này thì container chạy UTC và
    # ngày ôn đổi lúc 07:00 sáng giờ VN thay vì nửa đêm — hạn mức từ mới/ngày và due_date
    # lệch theo.
    #
    # HAI tên, thứ tự có ý nghĩa. `TZ` là tên chuẩn POSIX nên Docker cần đúng nó (compose
    # truyền vào để chỉnh cả đồng hồ container), nhưng trên Vercel chính vì thế mà nó là tên
    # BỊ GIỮ CHỖ: dashboard từ chối tạo biến `TZ`, còn AWS Lambda bên dưới thì tự đặt sẵn
    # `TZ=:UTC`. `APP_TZ` là lối thoát duy nhất ở đó, nên nó phải đứng trước.
    tz: str = Field(default=TZ_MAC_DINH, validation_alias=AliasChoices("APP_TZ", "TZ"))

    @field_validator("tz")
    @classmethod
    def _bo_qua_tz_cua_nen_tang(cls, gia_tri: str) -> str:
        """Giá trị bắt đầu bằng `:` là của Lambda, không phải của người dùng.

        `:UTC` là dạng POSIX ("đọc file zoneinfo tên UTC"), không phải key IANA — `ZoneInfo`
        ném `ZoneInfoNotFoundError` và `/api/stats` trả 500.

        Cố ý KHÔNG cắt dấu `:` để lấy `UTC`: chuỗi đó hợp lệ nên app sẽ chạy tiếp mà "hôm nay"
        lệch 7 tiếng so với giờ VN — heatmap trỏ sai ô và streak đứt sai ngày trong 7 giờ mỗi
        ngày, không có lỗi nào bật lên. Quay về mặc định là hành vi hỏng-thì-thấy-ngay.
        """
        sach = gia_tri.strip()
        return TZ_MAC_DINH if not sach or sach.startswith(":") else sach

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            # Supabase phát `postgresql://` (hoặc `postgres://`); SQLAlchemy cần biết dùng
            # driver nào, mặc định của nó là psycopg2 vốn không được cài.
            url = self.database_url
            for tien_to in ("postgresql+psycopg://", "postgresql+psycopg2://"):
                if url.startswith(tien_to):
                    return url
            for tien_to in ("postgresql://", "postgres://"):
                if url.startswith(tien_to):
                    return "postgresql+psycopg://" + url[len(tien_to) :]
            return url
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    #: Vercel tự đặt `VERCEL=1` trong mọi function. Không phải thứ người dùng khai trong
    #: `.env` — nó là cách duy nhất code biết mình đang chạy serverless hay không.
    vercel: str = Field(default="", alias="VERCEL")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_serverless(self) -> bool:
        return bool(self.vercel.strip())

    @computed_field  # type: ignore[prop-decorator]
    @property
    def qua_pooler_transaction(self) -> bool:
        """Có đang nói chuyện qua connection pooler ở chế độ transaction không.

        Quan trọng vì chế độ đó GHÉP LUỒNG nhiều client lên chung một backend Postgres, nên
        prepared statement tạo ở lượt này có thể không tồn tại ở lượt sau — psycopg mặc
        định tự tạo prepared statement sau 5 lần chạy cùng một câu, và triệu chứng là
        `prepared statement "_pg3_N" does not exist` nổ rời rạc DƯỚI TẢI, không bao giờ
        thấy khi test.

        Hai dấu hiệu: đang chạy serverless, hoặc URL trỏ vào cổng 6543 của Supavisor
        (Supabase dùng 5432 cho session mode, 6543 cho transaction mode).
        """
        return self.is_serverless or ":6543" in self.sqlalchemy_url

    @computed_field  # type: ignore[prop-decorator]
    @property
    def gemini_configured(self) -> bool:
        """/api/health trả cờ này. Khoá rỗng = chưa cấu hình, không phải lỗi."""
        return bool(self.gemini_api_key.strip())

    @computed_field  # type: ignore[prop-decorator]
    @property
    def allowed_email_set(self) -> frozenset[str]:
        """Allowlist đã chuẩn hoá chữ thường.

        Hạ chữ thường ở ĐÚNG MỘT chỗ. Đây là lớp lỗi có thật: AUTH_ALLOWED_EMAILS gõ tay
        trong .env lệch hoa thường so với email Google trả về → người dùng hợp lệ bị chặn,
        và thông điệp lỗi thì nói "email không nằm trong allowlist" nên trông như đúng.
        """
        return frozenset(
            phan.strip().lower() for phan in self.auth_allowed_emails.split(",") if phan.strip()
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin(self) -> str:
        """CORS chỉ mở cho đúng extension này (ràng buộc #7).

        Web app chạy CÙNG origin với backend nên không cần — và không được — thêm vào đây:
        trình duyệt không áp CORS cho request same-origin, còn thêm một origin nữa là mở
        thật một cửa mà không đổi lại được gì.
        """
        return f"chrome-extension://{self.extension_id}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cookie_secure(self) -> bool:
        """Cờ `Secure` cho cookie phiên, đã phân giải xong `auto`.

        `auto` = True trừ khi web chạy trên loopback. Đó là chỗ DUY NHẤT mà HTTP thường là
        hợp lệ; mọi nơi khác thiếu `Secure` là phát phiên qua đường không mã hoá.
        """
        chon = self.auth_cookie_secure.strip().lower()
        if chon == "true":
            return True
        if chon == "false":
            return False
        return not self.web_base_url.lower().startswith(
            ("http://localhost", "http://127.0.0.1", "http://[::1]")
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def web_redirect_uri(self) -> str:
        """Redirect URI của luồng web. Dựng từ config, KHÔNG nhận từ client.

        Tách hẳn khỏi `AuthService.extension_redirect_uri()` chứ không gộp thành một tập:
        gộp lại thì `POST /api/auth/google` — endpoint trả token phiên THÔ trong JSON body —
        sẽ chấp nhận luôn redirect_uri của web, và hai luồng mượn được của nhau.
        """
        return f"{self.web_base_url.rstrip('/')}/api/auth/google/callback"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
