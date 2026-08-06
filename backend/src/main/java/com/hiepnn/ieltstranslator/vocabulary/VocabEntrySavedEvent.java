package com.hiepnn.ieltstranslator.vocabulary;

/**
 * Phát ra khi một từ MỚI được lưu vào sổ (không phát khi lưu trùng).
 *
 * <p>Tồn tại để module srs tạo thẻ ôn tập mà vocabulary không phải biết srs tồn tại —
 * giữ chiều phụ thuộc srs → vocabulary như spec chốt.
 */
public record VocabEntrySavedEvent(VocabEntry entry) {
}
