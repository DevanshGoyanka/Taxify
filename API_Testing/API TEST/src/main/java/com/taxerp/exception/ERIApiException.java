package com.taxerp.exception;

/**
 * Exception thrown when ERI API communication fails.
 * This includes network errors, HTTP errors, and API response validation failures.
 */
public class ERIApiException extends ERIException {

    public ERIApiException(String message) {
        super(message, "ERI_API_ERROR");
    }

    public ERIApiException(String message, Throwable cause) {
        super(message, "ERI_API_ERROR", 500, cause);
    }

    public ERIApiException(String message, int httpStatus) {
        super(message, "ERI_API_ERROR", httpStatus);
    }

    public ERIApiException(String message, int httpStatus, Throwable cause) {
        super(message, "ERI_API_ERROR", httpStatus, cause);
    }

    public ERIApiException(String message, String errorCode, int httpStatus) {
        super(message, errorCode, httpStatus);
    }

    public ERIApiException(String message, String errorCode, int httpStatus, Throwable cause) {
        super(message, errorCode, httpStatus, cause);
    }
}