package com.hiepnn.ieltstranslator.vocabulary;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabRequest;
import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabResponse;
import com.hiepnn.ieltstranslator.vocabulary.dto.VocabEntryDto;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;

@Service
public class VocabService {

    private final VocabEntryRepository repository;
    private final com.hiepnn.ieltstranslator.auth.AppUserRepository userRepository;
    private final CsvExporter csvExporter;
    private final ObjectMapper objectMapper;
    private final ApplicationEventPublisher events;

    public VocabService(VocabEntryRepository repository,
                        com.hiepnn.ieltstranslator.auth.AppUserRepository userRepository,
                        CsvExporter csvExporter,
                        ObjectMapper objectMapper, ApplicationEventPublisher events) {
        this.repository = repository;
        this.userRepository = userRepository;
        this.csvExporter = csvExporter;
        this.objectMapper = objectMapper;
        this.events = events;
    }

    /**
     * Lưu từ mới. Nếu (term, pos) đã có thì KHÔNG ghi đè nội dung cũ — chỉ gộp
     * thêm tag mới — và báo alreadyExists để UI hiện "Đã có trong sổ".
     */
    @Transactional
    public SaveVocabResponse save(Long userId, SaveVocabRequest request) {
        String pos = request.pos() == null ? "" : request.pos();
        Optional<VocabEntry> existing =
                repository.findByUser_IdAndTermAndPos(userId, request.term(), pos);

        if (existing.isPresent()) {
            VocabEntry entry = existing.get();
            mergeTags(entry, request.tags());
            return new SaveVocabResponse(entry.getId(), true);
        }

        VocabEntry entry = new VocabEntry();
        // Tham chiếu lười: chỉ cần khoá ngoại, không cần nạp cả hàng app_user.
        entry.setUser(userRepository.getReferenceById(userId));
        entry.setTerm(request.term());
        entry.setLemma(request.lemma());
        entry.setLang(request.lang());
        entry.setPos(pos);
        entry.setIpa(request.ipa());
        entry.setMeaningVi(request.meaningVi());
        entry.setDefinitionEn(request.definitionEn());
        entry.setCefr(request.cefr());
        entry.setBandLevel(request.bandLevel());
        entry.setTags(request.tags() == null ? new String[0] : request.tags().toArray(new String[0]));
        entry.setSourceUrl(request.sourceUrl());
        entry.setSourceSentence(request.sourceSentence());
        entry.setCollocations(request.collocations() == null
                ? objectMapper.createArrayNode() : request.collocations());
        entry.setExamples(request.examples() == null
                ? objectMapper.createArrayNode() : request.examples());

        // Chỉ phát sự kiện ở nhánh lưu MỚI. Nhánh alreadyExists đã return sớm ở trên,
        // nên không có chuyện lưu lại một từ cũ mà lịch ôn của nó bị đặt lại từ đầu.
        VocabEntry saved = repository.save(entry);
        events.publishEvent(new VocabEntrySavedEvent(saved));
        return new SaveVocabResponse(saved.getId(), false);
    }

    private void mergeTags(VocabEntry entry, List<String> incoming) {
        if (incoming == null || incoming.isEmpty()) {
            return;
        }
        Set<String> merged = new LinkedHashSet<>(List.of(entry.getTags()));
        merged.addAll(incoming);
        entry.setTags(merged.toArray(new String[0]));
    }

    @Transactional(readOnly = true)
    public Page<VocabEntryDto> search(Long userId, String q, String tag, Pageable pageable) {
        String normalisedQ = (q == null || q.isBlank()) ? null : q;
        String normalisedTag = (tag == null || tag.isBlank()) ? null : tag;
        return repository.search(userId, normalisedQ, normalisedTag, pageable).map(this::toDto);
    }

    /**
     * Tra thẳng theo (id, userId) chứ KHÔNG tra theo id rồi so chủ sở hữu sau — một bước,
     * không có khe hở giữa đọc và kiểm.
     *
     * <p>Trả NOT_FOUND chứ không FORBIDDEN khi từ thuộc về người khác: FORBIDDEN xác nhận
     * "id này có tồn tại", tức là một kênh dò id.
     */
    @Transactional(readOnly = true)
    public VocabEntryDto findById(Long userId, Long id) {
        return repository.findByIdAndUser_Id(id, userId).map(this::toDto)
                .orElseThrow(() -> AppException.of(ErrorCode.NOT_FOUND, "Không tìm thấy từ id=" + id));
    }

    @Transactional
    public void delete(Long userId, Long id) {
        VocabEntry entry = repository.findByIdAndUser_Id(id, userId)
                .orElseThrow(() -> AppException.of(ErrorCode.NOT_FOUND, "Không tìm thấy từ id=" + id));
        repository.delete(entry);
    }

    @Transactional(readOnly = true)
    public String exportCsv(Long userId) {
        return csvExporter.toCsv(repository.findAllByUser_IdOrderByCreatedAtDesc(userId));
    }

    /** Lọc id client gửi lên xuống còn id thuộc về user. Dùng cho /api/quiz/generate. */
    @Transactional(readOnly = true)
    public List<Long> filterOwnedIds(Long userId, List<Long> ids) {
        return (ids == null || ids.isEmpty()) ? List.of() : repository.findOwnedIds(userId, ids);
    }

    private VocabEntryDto toDto(VocabEntry e) {
        return new VocabEntryDto(e.getId(), e.getTerm(), e.getLemma(), e.getLang(), e.getPos(),
                e.getIpa(), e.getMeaningVi(), e.getDefinitionEn(), e.getCefr(), e.getBandLevel(),
                List.of(e.getTags()), e.getSourceUrl(), e.getSourceSentence(),
                e.getCollocations(), e.getExamples(), e.getCreatedAt());
    }
}
