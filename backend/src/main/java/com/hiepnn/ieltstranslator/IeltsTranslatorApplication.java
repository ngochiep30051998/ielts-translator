package com.hiepnn.ieltstranslator;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class IeltsTranslatorApplication {
    public static void main(String[] args) {
        SpringApplication.run(IeltsTranslatorApplication.class, args);
    }
}
