package com.taxerp.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/**
 * Data Transfer Object for ERI API requests.
 * Represents the structure of requests sent to ITD ERI endpoints.
 */
public class ERIRequest {

    @NotBlank(message = "ERI User ID is required")
    @JsonProperty("eriUserId")
    private String eriUserId;

    @NotNull(message = "Data payload is required")
    @JsonProperty("data")
    private Object data;

    @NotBlank(message = "Signature is required")
    @JsonProperty("signature")
    private String signature;

    @JsonProperty("timestamp")
    private String timestamp;

    @JsonProperty("correlationId")
    private String correlationId;

    public ERIRequest() {
    }

    public ERIRequest(String eriUserId, Object data, String signature) {
        this.eriUserId = eriUserId;
        this.data = data;
        this.signature = signature;
    }

    public String getEriUserId() {
        return eriUserId;
    }

    public void setEriUserId(String eriUserId) {
        this.eriUserId = eriUserId;
    }

    public Object getData() {
        return data;
    }

    public void setData(Object data) {
        this.data = data;
    }

    public String getSignature() {
        return signature;
    }

    public void setSignature(String signature) {
        this.signature = signature;
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

    @Override
    public String toString() {
        return "ERIRequest{" +
                "eriUserId='" + eriUserId + '\'' +
                ", data=" + data +
                ", signature='[MASKED]'" +
                ", timestamp='" + timestamp + '\'' +
                ", correlationId='" + correlationId + '\'' +
                '}';
    }
}