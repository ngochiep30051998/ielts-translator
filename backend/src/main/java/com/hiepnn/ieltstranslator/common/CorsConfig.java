package com.hiepnn.ieltstranslator.common;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class CorsConfig implements WebMvcConfigurer {

    private final String extensionId;

    public CorsConfig(@Value("${extension.id:}") String extensionId) {
        this.extensionId = extensionId;
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        if (extensionId.isBlank()) {
            return;
        }
        registry.addMapping("/api/**")
                .allowedOrigins("chrome-extension://" + extensionId)
                .allowedMethods("GET", "POST", "DELETE")
                .allowedHeaders("*");
    }
}
