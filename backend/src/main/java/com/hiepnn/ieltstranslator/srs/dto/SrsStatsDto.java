package com.hiepnn.ieltstranslator.srs.dto;

/**
 * @param dueCount    số thẻ người dùng thực sự phải ôn hôm nay — đã cộng phần thẻ mới
 *                    còn được phép học. Đây là con số hiện trên badge. Khớp đúng độ dài
 *                    hàng đợi của /api/srs/due khi gọi CÙNG {@code newLimit} và
 *                    {@code limit} chưa phải ràng buộc chặn; vượt {@code limit} thì con
 *                    số này vẫn là tổng nợ thật còn hàng đợi bị cắt bớt — cố ý, vì badge
 *                    phải nói đúng người dùng còn nợ bao nhiêu.
 * @param newCount    tổng số thẻ NEW, không trừ giới hạn ngày
 * @param learnedCount số thẻ đã ôn ít nhất một lượt
 */
public record SrsStatsDto(long dueCount, long newCount, long learnedCount) {
}
