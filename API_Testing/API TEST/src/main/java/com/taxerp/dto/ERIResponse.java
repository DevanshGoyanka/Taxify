package com.taxerp.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Data Transfer Object for ERI API responses.
 * Represents the structure of responses received from ITD ERI endpoints.
 */
public class ERIResponse {

    @JsonProperty("status")
    private String status;

    @JsonProperty("message")
    private String message;

    @JsonProperty("data")
    private Object data;

    @JsonProperty("errorCode")
    private String errorCode;

    @JsonProperty("timestamp")
    private String timestamp;

    @JsonProperty("correlationId")
    private String correlationId;

    @JsonProperty("transactionId")
    private String transactionId;

    // HTTP response metadata
    private int httpStatusCode;
    private long responseTimeMs;

    public ERIResponse() {
    }

    public ERIResponse(String status, String message) {
        this.status = status;
        this.message = message;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public Object getData() {
        return data;
    }

    public void setData(Object data) {
        this.data = data;
    }

    public String getErrorCode() {
        return errorCode;
    }

    public void setErrorCode(String errorCode) {
        this.errorCode = errorCode;
    }

    public String getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(String timestamp) {
        this.timestamp = timestamp;
    }

    public String getCorrelationId() {
        return correlationId;
    }

    public void setCorrelationId(String correlationId) {
        this.correlationId = correlationId;
    }

    public String getTransactionId() {
        return transactionId;
    }

    public void setTransactionId(String transactionId) {
        this.transactionId = transactionId;
    }

    public int getHttpStatusCode() {
        return httpStatusCode;
    }

    public void setHttpStatusCode(int httpStatusCode) {
        this.httpStatusCode = httpStatusCode;
    }

    public long getResponseTimeMs() {
        return responseTimeMs;
    }

    public void setResponseTimeMs(long responseTimeMs) {
        this.responseTimeMs = responseTimeMs;
    }

    public boolean isSuccess() {
        return "SUCCESS".equalsIgnoreCase(status) || "OK".equalsIgnoreCase(status);
    }

    @Override
    public String toString() {
        return "ERIResponse{" +
                "status='" + status + '\'' +
                ", message='" + message + '\'' +
                ", data=" + data +
                ", errorCode='" + errorCode + '\'' +
                ", timestamp='" + timestamp + '\'' +
                ", correlationId='" + correlationId + '\'' +
                ", transactionId='" + transactionId + '\'' +
                ", httpStatusCode=" + httpStatusCode +
                ", responseTimeMs=" + responseTimeMs +
                '}';
    }
}