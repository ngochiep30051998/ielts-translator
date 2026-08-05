package com.hiepnn.ieltstranslator.vocabulary;

import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabRequest;
import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabResponse;
import com.hiepnn.ieltstranslator.vocabulary.dto.VocabEntryDto;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/vocab")
public class VocabController {

    private final VocabService vocabService;

    public VocabController(VocabService vocabService) {
        this.vocabService = vocabService;
    }

    @PostMapping
    public SaveVocabResponse save(@Valid @RequestBody SaveVocabRequest request) {
        return vocabService.save(request);
    }

    @GetMapping
    public Page<VocabEntryDto> search(@RequestParam(required = false) String q,
                                      @RequestParam(required = false) String tag,
                                      @RequestParam(defaultValue = "0") int page,
                                      @RequestParam(defaultValue = "20") int size) {
        return vocabService.search(q, tag, PageRequest.of(page, Math.min(size, 100)));
    }

    @GetMapping("/{id}")
    public VocabEntryDto findById(@PathVariable Long id) {
        return vocabService.findById(id);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        vocabService.delete(id);
        return ResponseEntity.noContent().build();
    }

    @GetMapping(value = "/export.csv", produces = "text/csv")
    public ResponseEntity<String> exportCsv() {
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"vocabulary.csv\"")
                .contentType(MediaType.parseMediaType("text/csv; charset=UTF-8"))
                .body(vocabService.exportCsv());
    }
}
