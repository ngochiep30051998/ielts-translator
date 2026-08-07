package com.hiepnn.ieltstranslator.srs;

import java.util.List;

/**
 * Ba mồi nhử cho mỗi chiều hỏi. {@code viOptions} là nghĩa tiếng Việt sai (dùng cho
 * câu hỏi EN → VI), {@code enOptions} là từ tiếng Anh sai (dùng cho VI → EN).
 */
public record DistractorSet(List<String> viOptions, List<String> enOptions) {
}
