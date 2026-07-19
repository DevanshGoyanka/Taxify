package com.taxerp.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * Data Transfer Object for health check responses.
 * Provides comprehensive system health status information.
 */
public class HealthResponse {

    @JsonProperty("status")
    private String status;

    @JsonProperty("timestamp")
    private LocalDateTime timestamp;

    @JsonProperty("responseTimeMs")
    private long responseTimeMs;

    @JsonProperty("version")
    private String version;

    @JsonProperty("environment")
    private String environment;

    @JsonProperty("checks")
    private Map<String, HealthCheck> checks;

    public HealthResponse() {
        this.timestamp = LocalDateTime.now();
    }

    public HealthResponse(String status, Map<String, HealthCheck> checks) {
        this();
        this.status = status;
        this.checks = checks;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public LocalDateTime getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(LocalDateTime timestamp) {
        this.timestamp = timestamp;
    }

    public long getResponseTimeMs() {
        return responseTimeMs;
    }

    public void setResponseTimeMs(long responseTimeMs) {
        this.responseTimeMs = responseTimeMs;
    }

    public String getVersion() {
        return version;
    }

    public void setVersion(String version) {
        this.version = version;
    }

    public String getEnvironment() {
        return environment;
    }

    public void setEnvironment(String environment) {
        this.environment = environment;
    }

    public Map<String, HealthCheck> getChecks() {
        return checks;
    }

    public void setChecks(Map<String, HealthCheck> checks) {
        this.checks = checks;
    }

    /**
     * Individual health check result
     */
    public static class HealthCheck {
        
        @JsonProperty("status")
        private String status;

        @JsonProperty("message")
        private String message;

        @JsonProperty("responseTimeMs")
        private Long responseTimeMs;

        @JsonProperty("details")
        private Map<String, Object> details;

        @JsonProperty("error")
        private String error;

        public HealthCheck() {
        }

        public HealthCheck(String status, String message) {
            this.status = status;
            this.message = message;
        }

        public HealthCheck(String status, String message, Long responseTimeMs) {
            this.status = status;
            this.message = message;
            this.responseTimeMs = responseTimeMs;
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

        public Long getResponseTimeMs() {
            return responseTimeMs;
        }

        public void setResponseTimeMs(Long responseTimeMs) {
            this.responseTimeMs = responseTimeMs;
        }

        public Map<String, Object> getDetails() {
            return details;
        }

        public void setDetails(Map<String, Object> details) {
            this.details = details;
        }

        public String getError() {
            return error;
        }

        public void setError(String error) {
            this.error = error;
        }

        public boolean isHealthy() {
            return "UP".equalsIgnoreCase(status) || "HEALTHY".equalsIgnoreCase(status);
        }
    }
}