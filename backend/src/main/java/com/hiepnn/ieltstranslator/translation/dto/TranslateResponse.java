package com.hiepnn.ieltstranslator.translation.dto;

import com.fasterxml.jackson.databind.JsonNode;
import com.hiepnn.ieltstranslator.translation.Direction;
import com.hiepnn.ieltstranslator.translation.Mode;

public record TranslateResponse(
        Direction direction,
        Mode mode,
        boolean cached,
        JsonNode payload
) {}
