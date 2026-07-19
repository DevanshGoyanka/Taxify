package com.taxerp.exception;

/**
 * Exception thrown when keystore operations fail.
 * This includes keystore loading, validation, and certificate access errors.
 */
public class KeystoreException extends Exception {

    private final String errorCode;

    public KeystoreException(String message) {
        super(message);
        this.errorCode = "KEYSTORE_ERROR";
    }

    public KeystoreException(String message, Throwable cause) {
        super(message, cause);
        this.errorCode = "KEYSTORE_ERROR";
    }

    public KeystoreException(String message, String errorCode) {
        super(message);
        this.errorCode = errorCode;
    }

    public KeystoreException(String message, String errorCode, Throwable cause) {
        super(message, cause);
        this.errorCode = errorCode;
    }

    public String getErrorCode() {
        return errorCode;
    }
}