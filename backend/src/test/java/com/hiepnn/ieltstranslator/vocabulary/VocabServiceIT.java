package com.hiepnn.ieltstranslator.vocabulary;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import com.hiepnn.ieltstranslator.common.AppException;
import com.hiepnn.ieltstranslator.common.ErrorCode;
import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabRequest;
import com.hiepnn.ieltstranslator.vocabulary.dto.SaveVocabResponse;
import com.hiepnn.ieltstranslator.vocabulary.dto.VocabEntryDto;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.PageRequest;

import java.util.List;

import static org.assertj.core.api.Assertions.*;

class VocabServiceIT extends AbstractPostgresIT {

    @Autowired VocabService service;
    @Autowired VocabEntryRepository repository;
    @Autowired ObjectMapper objectMapper;

    @BeforeEach
    void reset() {
        repository.deleteAll();
    }

    private SaveVocabRequest request(String term, String pos, String meaning, List<String> tags) {
        return new SaveVocabRequest(term, term, "en", pos, "/test/", meaning,
                "an English definition", "B2", "6.5", tags,
                "https://example.com", "A source sentence.",
                objectMapper.createArrayNode().add("renewable energy"),
                objectMapper.createArrayNode());
    }

    @Test
    void savesNewEntry() {
        SaveVocabResponse response = service.save(request("renewable", "adj", "tái tạo", List.of()));

        assertThat(response.id()).isNotNull();
        assertThat(response.alreadyExists()).isFalse();
        assertThat(repository.count()).isEqualTo(1);
    }

    @Test
    void savingSameTermAndPosReturnsAlreadyExistsWithoutDuplicating() {
        SaveVocabResponse first = service.save(request("renewable", "adj", "tái tạo", List.of()));
        SaveVocabResponse second = service.save(request("renewable", "adj", "nghĩa khác", List.of()));

        assertThat(second.alreadyExists()).isTrue();
        assertThat(second.id()).isEqualTo(first.id());
        assertThat(repository.count()).isEqualTo(1);
    }

    @Test
    void existingEntryKeepsItsOriginalMeaning() {
        service.save(request("renewable", "adj", "tái tạo", List.of()));
        service.save(request("renewable", "adj", "nghĩa bị ghi đè", List.of()));

        assertThat(repository.findAll().get(0).getMeaningVi()).isEqualTo("tái tạo");
    }

    @Test
    void savingExistingEntryMergesNewTags() {
        service.save(request("renewable", "adj", "tái tạo", List.of("environment")));
        service.save(request("renewable", "adj", "tái tạo", List.of("environment", "writing")));

        assertThat(repository.findAll().get(0).getTags())
                .containsExactlyInAnyOrder("environment", "writing");
    }

    @Test
    void sameTermWithDifferentPosAreSeparateEntries() {
        service.save(request("run", "v", "chạy", List.of()));
        service.save(request("run", "n", "lượt chạy", List.of()));

        assertThat(repository.count()).isEqualTo(2);
    }

    @Test
    void searchMatchesTermSubstringCaseInsensitively() {
        service.save(request("renewable", "adj", "tái tạo", List.of()));
        service.save(request("mitigate", "v", "giảm nhẹ", List.of()));

        List<VocabEntryDto> found = service.search("RENEW", null, PageRequest.of(0, 20)).getContent();

        assertThat(found).hasSize(1);
        assertThat(found.get(0).term()).isEqualTo("renewable");
    }

    @Test
    void searchMatchesVietnameseMeaning() {
        service.save(request("mitigate", "v", "giảm nhẹ", List.of()));

        assertThat(service.search("giảm", null, PageRequest.of(0, 20)).getContent()).hasSize(1);
    }

    @Test
    void searchFiltersByTag() {
        service.save(request("renewable", "adj", "tái tạo", List.of("environment")));
        service.save(request("mitigate", "v", "giảm nhẹ", List.of("writing")));

        List<VocabEntryDto> found = service.search(null, "writing", PageRequest.of(0, 20)).getContent();

        assertThat(found).hasSize(1);
        assertThat(found.get(0).term()).isEqualTo("mitigate");
    }

    @Test
    void searchWithoutFiltersReturnsAllNewestFirst() {
        service.save(request("first", "n", "một", List.of()));
        service.save(request("second", "n", "hai", List.of()));

        List<VocabEntryDto> found = service.search(null, null, PageRequest.of(0, 20)).getContent();

        assertThat(found).extracting(VocabEntryDto::term).containsExactly("second", "first");
    }

    @Test
    void deleteRemovesEntry() {
        Long id = service.save(request("renewable", "adj", "tái tạo", List.of())).id();

        service.delete(id);

        assertThat(repository.count()).isZero();
    }

    @Test
    void deletingUnknownIdThrowsNotFound() {
        assertThatThrownBy(() -> service.delete(999999L))
                .isInstanceOf(AppException.class)
                .satisfies(ex -> assertThat(((AppException) ex).code()).isEqualTo(ErrorCode.NOT_FOUND));
    }

    @Test
    void findByIdReturnsEntry() {
        Long id = service.save(request("renewable", "adj", "tái tạo", List.of())).id();

        assertThat(service.findById(id).term()).isEqualTo("renewable");
    }
}
