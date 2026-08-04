package com.hiepnn.ieltstranslator.common;

public record ApiError(String code, String message, boolean retryable) {}
