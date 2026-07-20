package com.taxerp.exception;

/**
 * Base exception for ERI (e-Return Intermediary) API operations.
 * This includes API communication errors, authentication failures, and data validation errors.
 */
public class ERIException extends Exception {

    private final String errorCode;
    private final int httpStatus;

    public ERIException(String message) {
        super(message);
        this.errorCode = "ERI_ERROR";
        this.httpStatus = 500;
    }

    public ERIException(String message, Throwable cause) {
        super(message, cause);
        this.errorCode = "ERI_ERROR";
        this.httpStatus = 500;
    }

    public ERIException(String message, String errorCode) {
        super(message);
        this.errorCode = errorCode;
        this.httpStatus = 500;
    }

    public ERIException(String message, String errorCode, int httpStatus) {
        super(message);
        this.errorCode = errorCode;
        this.httpStatus = httpStatus;
    }

    public ERIException(String message, String errorCode, int httpStatus, Throwable cause) {
        super(message, cause);
        this.errorCode = errorCode;
        this.httpStatus = httpStatus;
    }

    public String getErrorCode() {
        return errorCode;
    }

    public int getHttpStatus() {
        return httpStatus;
    }
}