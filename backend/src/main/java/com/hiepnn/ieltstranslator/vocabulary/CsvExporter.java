package com.hiepnn.ieltstranslator.vocabulary;

import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class CsvExporter {

    private static final String HEADER =
            "term,pos,ipa,meaning_vi,definition_en,cefr,band_level,tags,source_url,created_at";

    public String toCsv(List<VocabEntry> entries) {
        StringBuilder sb = new StringBuilder(HEADER);
        for (VocabEntry e : entries) {
            sb.append('\n')
              .append(String.join(",",
                      escape(e.getTerm()),
                      escape(e.getPos()),
                      escape(e.getIpa()),
                      escape(e.getMeaningVi()),
                      escape(e.getDefinitionEn()),
                      escape(e.getCefr()),
                      escape(e.getBandLevel()),
                      escape(String.join(";", e.getTags())),
                      escape(e.getSourceUrl()),
                      escape(e.getCreatedAt() == null ? "" : e.getCreatedAt().toString())));
        }
        return sb.toString();
    }

    /** Bọc dấu ngoặc kép khi field chứa dấu phẩy, ngoặc kép hoặc xuống dòng (RFC 4180). */
    private String escape(String value) {
        if (value == null) {
            return "";
        }
        if (value.contains(",") || value.contains("\"") || value.contains("\n") || value.contains("\r")) {
            return '"' + value.replace("\"", "\"\"") + '"';
        }
        return value;
    }
}
