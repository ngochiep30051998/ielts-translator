package com.hiepnn.ieltstranslator.health;

import com.hiepnn.ieltstranslator.AbstractPostgresIT;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@AutoConfigureMockMvc
class HealthControllerIT extends AbstractPostgresIT {

    @Autowired
    MockMvc mockMvc;

    @Test
    void healthReportsDbAndGeminiConfigured() throws Exception {
        mockMvc.perform(get("/api/health"))
               .andExpect(status().isOk())
               .andExpect(jsonPath("$.status").value("UP"))
               .andExpect(jsonPath("$.dbConnected").value(true))
               .andExpect(jsonPath("$.geminiConfigured").value(true));
    }
}
