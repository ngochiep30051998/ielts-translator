package com.hiepnn.ieltstranslator.vocabulary;

import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@AutoConfigureMockMvc
class VocabControllerIT extends AbstractPostgresIT {

    @Autowired MockMvc mockMvc;
    @Autowired VocabEntryRepository repository;

    private static final String BODY = """
            {"term":"renewable","lemma":"renewable","lang":"en","pos":"adj",
             "ipa":"/rɪˈnjuːəbl/","meaningVi":"tái tạo","definitionEn":"able to be renewed",
             "cefr":"B2","bandLevel":"6.5","tags":["environment"],
             "sourceUrl":"https://example.com","sourceSentence":"We need renewable energy.",
             "collocations":["renewable energy"],"examples":[]}
            """;

    @BeforeEach
    void reset() {
        repository.deleteAll();
    }

    @Test
    void savesAndReturnsId() throws Exception {
        mockMvc.perform(post("/api/vocab").contentType(MediaType.APPLICATION_JSON).content(BODY))
               .andExpect(status().isOk())
               .andExpect(jsonPath("$.id").isNumber())
               .andExpect(jsonPath("$.alreadyExists").value(false));
    }

    @Test
    void secondSaveReportsAlreadyExists() throws Exception {
        mockMvc.perform(post("/api/vocab").contentType(MediaType.APPLICATION_JSON).content(BODY));

        mockMvc.perform(post("/api/vocab").contentType(MediaType.APPLICATION_JSON).content(BODY))
               .andExpect(status().isOk())
               .andExpect(jsonPath("$.alreadyExists").value(true));
    }

    @Test
    void searchReturnsPagedResult() throws Exception {
        mockMvc.perform(post("/api/vocab").contentType(MediaType.APPLICATION_JSON).content(BODY));

        mockMvc.perform(get("/api/vocab").param("q", "renew"))
               .andExpect(status().isOk())
               .andExpect(jsonPath("$.content[0].term").value("renewable"))
               .andExpect(jsonPath("$.totalElements").value(1));
    }

    @Test
    void deleteReturns204ThenGetReturns404() throws Exception {
        String response = mockMvc.perform(post("/api/vocab")
                        .contentType(MediaType.APPLICATION_JSON).content(BODY))
                .andReturn().getResponse().getContentAsString();
        long id = com.jayway.jsonpath.JsonPath.parse(response).read("$.id", Integer.class);

        mockMvc.perform(delete("/api/vocab/" + id)).andExpect(status().isNoContent());
        mockMvc.perform(get("/api/vocab/" + id))
               .andExpect(status().isNotFound())
               .andExpect(jsonPath("$.code").value("NOT_FOUND"));
    }

    @Test
    void exportReturnsCsvWithHeaderRow() throws Exception {
        mockMvc.perform(post("/api/vocab").contentType(MediaType.APPLICATION_JSON).content(BODY));

        mockMvc.perform(get("/api/vocab/export.csv"))
               .andExpect(status().isOk())
               .andExpect(header().string("Content-Disposition",
                       "attachment; filename=\"vocabulary.csv\""))
               .andExpect(content().string(org.hamcrest.Matchers.startsWith("term,pos,ipa")))
               .andExpect(content().string(org.hamcrest.Matchers.containsString("renewable")));
    }
}
