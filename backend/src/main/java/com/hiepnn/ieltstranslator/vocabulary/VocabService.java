package com.hiepnn.ieltstranslator.vocabulary;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabRequest;
import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabResponse;
import com.hiepnn.ieltstranslator.vocabulary.dto.VocabEntryDto;
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
    private final CsvExporter csvExporter;
    private final ObjectMapper objectMapper;

    public VocabService(VocabEntryRepository repository, CsvExporter csvExporter,
                        ObjectMapper objectMapper) {
        this.repository = repository;
        this.csvExporter = csvExporter;
        this.objectMapper = objectMapper;
    }

    /**
     * Lưu từ mới. Nếu (term, pos) đã có thì KHÔNG ghi đè nội dung cũ — chỉ gộp
     * thêm tag mới — và báo alreadyExists để UI hiện "Đã có trong sổ".
     */
    @Transactional
    public SaveVocabResponse save(SaveVocabRequest request) {
        String pos = request.pos() == null ? "" : request.pos();
        Optional<VocabEntry> existing = repository.findByTermAndPos(request.term(), pos);

        if (existing.isPresent()) {
            VocabEntry entry = existing.get();
            mergeTags(entry, request.tags());
            return new SaveVocabResponse(entry.getId(), true);
        }

        VocabEntry entry = new VocabEntry();
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

        return new SaveVocabResponse(repository.save(entry).getId(), false);
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
    public Page<VocabEntryDto> search(String q, String tag, Pageable pageable) {
        String normalisedQ = (q == null || q.isBlank()) ? null : q;
        String normalisedTag = (tag == null || tag.isBlank()) ? null : tag;
        return repository.search(normalisedQ, normalisedTag, pageable).map(this::toDto);
    }

    @Transactional(readOnly = true)
    public VocabEntryDto findById(Long id) {
        return repository.findById(id).map(this::toDto)
                .orElseThrow(() -> AppException.of(ErrorCode.NOT_FOUND, "Không tìm thấy từ id=" + id));
    }

    @Transactional
    public void delete(Long id) {
        if (!repository.existsById(id)) {
            throw AppException.of(ErrorCode.NOT_FOUND, "Không tìm thấy từ id=" + id);
        }
        repository.deleteById(id);
    }

    @Transactional(readOnly = true)
    public String exportCsv() {
        return csvExporter.toCsv(repository.findAllByOrderByCreatedAtDesc());
    }

    private VocabEntryDto toDto(VocabEntry e) {
        return new VocabEntryDto(e.getId(), e.getTerm(), e.getLemma(), e.getLang(), e.getPos(),
                e.getIpa(), e.getMeaningVi(), e.getDefinitionEn(), e.getCefr(), e.getBandLevel(),
                List.of(e.getTags()), e.getSourceUrl(), e.getSourceSentence(),
                e.getCollocations(), e.getExamples(), e.getCreatedAt());
    }
}
