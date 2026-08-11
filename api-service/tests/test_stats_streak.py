"""Streak là hàm thuần — KHÔNG chạm DB, không fixture `db`/`client`.

`today` là tham số chứ không phải `date.today()` gọi bên trong: đó là điều kiện duy nhất để
test được "hôm nay chưa ôn thì streak vẫn tính từ hôm qua" mà không phải giả lập đồng hồ.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.stats.streak import tinh_streak

HOM_NAY = date(2026, 8, 11)


def _truoc(so_ngay: int) -> date:
    return HOM_NAY - timedelta(days=so_ngay)


def test_chua_on_ngay_nao() -> None:
    ket_qua = tinh_streak([], HOM_NAY)
    assert ket_qua.current == 0
    assert ket_qua.longest == 0
    assert ket_qua.last_active is None


def test_chi_on_hom_nay() -> None:
    ket_qua = tinh_streak([HOM_NAY], HOM_NAY)
    assert ket_qua.current == 1
    assert ket_qua.longest == 1
    assert ket_qua.last_active == HOM_NAY


def test_chi_on_hom_qua_van_giu_streak() -> None:
    """9 giờ sáng chưa kịp ôn mà thấy streak về 0 là sai, và sai đúng lúc phản tác dụng
    nhất. Streak chỉ đứt khi CẢ hôm nay lẫn hôm qua đều trống."""
    ket_qua = tinh_streak([_truoc(1)], HOM_NAY)
    assert ket_qua.current == 1
    assert ket_qua.last_active == _truoc(1)


def test_on_lan_cuoi_cach_day_hai_ngay_thi_dut() -> None:
    ket_qua = tinh_streak([_truoc(2)], HOM_NAY)
    assert ket_qua.current == 0
    assert ket_qua.longest == 1
    assert ket_qua.last_active == _truoc(2)


def test_ba_ngay_lien_tiep_ket_thuc_hom_nay() -> None:
    ket_qua = tinh_streak([_truoc(2), _truoc(1), HOM_NAY], HOM_NAY)
    assert ket_qua.current == 3
    assert ket_qua.longest == 3


def test_ba_ngay_lien_tiep_ket_thuc_hom_qua() -> None:
    ket_qua = tinh_streak([_truoc(3), _truoc(2), _truoc(1)], HOM_NAY)
    assert ket_qua.current == 3
    assert ket_qua.longest == 3


def test_chuoi_dai_nhat_nam_o_qua_khu() -> None:
    """current và longest là hai con số khác nhau — trả cùng một giá trị cho cả hai là lỗi
    dễ lọt nhất ở đây."""
    ngay = [_truoc(n) for n in (20, 19, 18, 17, 16)] + [_truoc(1), HOM_NAY]
    ket_qua = tinh_streak(sorted(ngay), HOM_NAY)
    assert ket_qua.current == 2
    assert ket_qua.longest == 5
    assert ket_qua.last_active == HOM_NAY


def test_mot_ngay_duy_nhat_cach_day_mot_nam() -> None:
    xa = HOM_NAY - timedelta(days=365)
    ket_qua = tinh_streak([xa], HOM_NAY)
    assert ket_qua.current == 0
    assert ket_qua.longest == 1
    assert ket_qua.last_active == xa
