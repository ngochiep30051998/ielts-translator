package com.hiepnn.ieltstranslator.translation;

import com.hiepnn.ieltstranslator.translation.dto.TranslateRequest;
import com.hiepnn.ieltstranslator.translation.dto.TranslateResponse;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/translate")
public class TranslateController {

    private final TranslationService translationService;
    private final com.hiepnn.ieltstranslator.auth.AuthContext auth;

    public TranslateController(TranslationService translationService,
                               com.hiepnn.ieltstranslator.auth.AuthContext auth) {
        this.translationService = translationService;
        this.auth = auth;
    }

    @PostMapping
    public TranslateResponse translate(@Valid @RequestBody TranslateRequest request) {
        return translationService.translate(auth.requireUserId(), request);
    }
}
