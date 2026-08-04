package com.hiepnn.ieltstranslator.translation;

import com.hiepnn.ieltstranslator.translation.dto.TranslateRequest;
import com.hiepnn.ieltstranslator.translation.dto.TranslateResponse;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/translate")
public class TranslateController {

    private final TranslationService translationService;

    public TranslateController(TranslationService translationService) {
        this.translationService = translationService;
    }

    @PostMapping
    public TranslateResponse translate(@Valid @RequestBody TranslateRequest request) {
        return translationService.translate(request);
    }
}
