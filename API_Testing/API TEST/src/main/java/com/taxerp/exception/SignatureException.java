package com.taxerp.exception;

/**
 * Exception thrown when digital signature operations fail.
 * This includes signature generation, validation, and format errors.
 */
public class SignatureException extends Exception {

    private final String errorCode;

    public SignatureException(String message) {
        super(message);
        this.errorCode = "SIGNATURE_ERROR";
    }

    public SignatureException(String message, Throwable cause) {
        super(message, cause);
        this.errorCode = "SIGNATURE_ERROR";
    }

    public SignatureException(String message, String errorCode) {
        super(message);
        this.errorCode = errorCode;
    }

    public SignatureException(String message, String errorCode, Throwable cause) {
        super(message, cause);
        this.errorCode = errorCode;
    }

    public String getErrorCode() {
        return errorCode;
    }
}