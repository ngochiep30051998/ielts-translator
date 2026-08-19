"""Bản port của `GeminiWiringIT`.

Bên Java, test này tồn tại vì một lý do rất cụ thể của Spring: `Map<GeminiTimeout,
RestClient>` chỉ được inject như một bean thường khi khoá KHÔNG phải `String` — đổi khoá
sang `String` thì Spring gom mọi bean theo tên và cả ba mức timeout im lặng biến mất.

Python không có cơ chế đó, nên test này giữ lại phần khẳng định còn có nghĩa: mỗi mức
timeout đọc đúng biến cấu hình của nó, và không mức nào dùng nhầm giá trị của mức khác.
Sai chỗ này thì một lượt sinh quiz chạy ở mức 15 giây — không có gì đỏ, chỉ hỏng trên máy
người dùng khi Gemini chậm thật.
"""

from __future__ import annotations

from app.common.gemini import CONNECT_TIMEOUT_SECONDS, GeminiClient, GeminiTimeout, _read_timeout
from app.config import Settings


def test_all_three_timeout_tiers_present_and_none_missing() -> None:
    """Nếu ai đó thêm một mức thứ tư mà quên nhánh trong `_read_timeout`, `assert_never` của
    mypy bắt lúc kiểm kiểu và vòng lặp này bắt lúc chạy."""
    settings = Settings(
        GEMINI_TIMEOUT_SECONDS=15,
        GEMINI_QUIZ_GENERATE_TIMEOUT_SECONDS=30,
        GEMINI_QUIZ_GRADE_TIMEOUT_SECONDS=20,
    )

    for tier in GeminiTimeout:
        assert _read_timeout(settings, tier) > 0


def test_each_tier_reads_its_own_config_variable() -> None:
    """Ba giá trị cố ý khác nhau và khác mặc định: nếu code lỡ đọc nhầm biến, con số trả về
    sẽ là của mức khác chứ không phải một giá trị vô lý dễ thấy."""
    settings = Settings(
        GEMINI_TIMEOUT_SECONDS=11,
        GEMINI_QUIZ_GENERATE_TIMEOUT_SECONDS=22,
        GEMINI_QUIZ_GRADE_TIMEOUT_SECONDS=33,
    )

    assert _read_timeout(settings, GeminiTimeout.TRANSLATE) == 11
    assert _read_timeout(settings, GeminiTimeout.QUIZ_GENERATE) == 22
    assert _read_timeout(settings, GeminiTimeout.QUIZ_GRADE) == 33


def test_real_client_builds_from_config_and_keeps_separate_timeouts() -> None:
    """Dựng client thật từ `Settings` — tương đương phần "GeminiClient thật dựng được từ nó"
    của bản Java."""
    settings = Settings(
        GEMINI_API_KEY="k",
        GEMINI_BASE_URL="http://gemini.test",
        GEMINI_TIMEOUT_SECONDS=11,
        GEMINI_QUIZ_GENERATE_TIMEOUT_SECONDS=22,
        GEMINI_QUIZ_GRADE_TIMEOUT_SECONDS=33,
    )
    client = GeminiClient(settings)
    try:
        assert client._client(GeminiTimeout.TRANSLATE).timeout.read == 11
        assert client._client(GeminiTimeout.QUIZ_GENERATE).timeout.read == 22
        assert client._client(GeminiTimeout.QUIZ_GRADE).timeout.read == 33
        # Bắt tay TCP không phụ thuộc độ dài output nên dùng chung cho cả ba mức.
        for tier in GeminiTimeout:
            assert client._client(tier).timeout.connect == CONNECT_TIMEOUT_SECONDS
        # Ba client RIÊNG BIỆT: dùng chung một client là read-timeout của mức cuối cùng
        # dựng ra sẽ áp cho cả ba.
        assert len({id(client._client(t)) for t in GeminiTimeout}) == 3
    finally:
        client.close()


def test_base_url_comes_from_config_not_hardcoded() -> None:
    """Ràng buộc #6: không hardcode giá trị nào. `GEMINI_BASE_URL` cũng là thứ test trỏ về
    cổng chết để không lượt gọi nào lọt ra mạng thật."""
    settings = Settings(GEMINI_BASE_URL="http://127.0.0.1:1")
    client = GeminiClient(settings)
    try:
        assert str(client._client(GeminiTimeout.TRANSLATE).base_url) == "http://127.0.0.1:1"
    finally:
        client.close()
