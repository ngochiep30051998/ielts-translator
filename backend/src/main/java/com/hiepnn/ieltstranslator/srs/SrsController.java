package com.hiepnn.ieltstranslator.srs;

import com.hiepnn.ieltstranslator.srs.dto.CardDto;
import com.hiepnn.ieltstranslator.srs.dto.ReviewRequest;
import com.hiepnn.ieltstranslator.srs.dto.ReviewResponse;
import com.hiepnn.ieltstranslator.srs.dto.SrsStatsDto;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/srs")
public class SrsController {

    private static final int MAX_LIMIT = 200;

    private final SrsService srsService;

    public SrsController(SrsService srsService) {
        this.srsService = srsService;
    }

    @GetMapping("/due")
    public List<CardDto> due(@RequestParam(defaultValue = "50") int limit,
                             @RequestParam(defaultValue = "30") int newLimit) {
        return srsService.due(clamp(limit, MAX_LIMIT), Math.max(0, newLimit));
    }

    @GetMapping("/stats")
    public SrsStatsDto stats(@RequestParam(defaultValue = "30") int newLimit) {
        return srsService.stats(Math.max(0, newLimit));
    }

    @PostMapping("/review")
    public ReviewResponse review(@Valid @RequestBody ReviewRequest request) {
        return srsService.review(request.cardId(), request.rating());
    }

    /** limit phải >= 1 vì PageRequest.of(0, size) ném IllegalArgument khi size = 0. */
    private int clamp(int value, int max) {
        return Math.max(1, Math.min(value, max));
    }
}
