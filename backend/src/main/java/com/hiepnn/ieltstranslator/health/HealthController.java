package com.hiepnn.ieltstranslator.health;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/health")
public class HealthController {

    private final JdbcTemplate jdbcTemplate;
    private final String geminiApiKey;

    public HealthController(JdbcTemplate jdbcTemplate,
                            @Value("${gemini.api-key:}") String geminiApiKey) {
        this.jdbcTemplate = jdbcTemplate;
        this.geminiApiKey = geminiApiKey;
    }

    @GetMapping
    public Map<String, Object> health() {
        boolean dbConnected;
        try {
            jdbcTemplate.queryForObject("SELECT 1", Integer.class);
            dbConnected = true;
        } catch (Exception e) {
            dbConnected = false;
        }
        return Map.of(
                "status", dbConnected ? "UP" : "DOWN",
                "dbConnected", dbConnected,
                "geminiConfigured", !geminiApiKey.isBlank()
        );
    }
}
