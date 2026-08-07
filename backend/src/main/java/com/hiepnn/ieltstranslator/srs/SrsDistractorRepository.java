package com.hiepnn.ieltstranslator.srs;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface SrsDistractorRepository extends JpaRepository<SrsDistractor, Long> {

    Optional<SrsDistractor> findByVocabEntry_Id(Long vocabEntryId);

    /**
     * Chỉ trả bản ghi còn hiệu lực. Lọc {@code promptVersion} ngay trong truy vấn là cách
     * làm mồi nhử cũ tự biến mất khi tăng version prompt, không cần xoá dữ liệu.
     */
    List<SrsDistractor> findByVocabEntry_IdInAndPromptVersion(Collection<Long> vocabEntryIds,
                                                              int promptVersion);
}
