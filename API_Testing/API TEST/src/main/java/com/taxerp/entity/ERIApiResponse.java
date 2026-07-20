package com.taxerp.entity;

import jakarta.persistence.*;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * ERIApiResponse entity for storing ERI API response details.
 * Links to ERIRequestLog to maintain complete audit trail of API interactions.
 */
@Entity
@Table(name = "eri_api_responses")
public class ERIApiResponse {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "correlation_id", nullable = false, length = 100)
    private String correlationId;

    @OneToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "request_log_id", nullable = false)
    private ERIRequestLog requestLog;

    @Column(name = "status_code", nullable = false)
    private Integer statusCode;

    @Column(name = "response_payload", columnDefinition = "TEXT")
    private String responsePayload;

    @Column(name = "masked_response", columnDefinition = "TEXT")
    private String maskedResponse;

    @Column(name = "response_time_ms")
    private Integer responseTimeMs;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    // Default constructor
    public ERIApiResponse() {
    }

    // Constructor with required fields
    public ERIApiResponse(String correlationId, ERIRequestLog requestLog, Integer statusCode) {
        this.correlationId = correlationId;
        this.requestLog = requestLog;
        this.statusCode = statusCode;
    }

    // Getters and Setters
    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public String getCorrelationId() {
        return correlationId;
    }

    public void setCorrelationId(String correlationId) {
        this.correlationId = correlationId;
    }

    public ERIRequestLog getRequestLog() {
        return requestLog;
    }

    public void setRequestLog(ERIRequestLog requestLog) {
        this.requestLog = requestLog;
    }

    public Integer getStatusCode() {
        return statusCode;
    }

    public void setStatusCode(Integer statusCode) {
        this.statusCode = statusCode;
    }

    public String getResponsePayload() {
        return responsePayload;
    }

    public void setResponsePayload(String responsePayload) {
        this.responsePayload = responsePayload;
    }

    public String getMaskedResponse() {
        return maskedResponse;
    }

    public void setMaskedResponse(String maskedResponse) {
        this.maskedResponse = maskedResponse;
    }

    public Integer getResponseTimeMs() {
        return responseTimeMs;
    }

    public void setResponseTimeMs(Integer responseTimeMs) {
        this.responseTimeMs = responseTimeMs;
    }

    public String getErrorMessage() {
        return errorMessage;
    }

    public void setErrorMessage(String errorMessage) {
        this.errorMessage = errorMessage;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }

    @Override
    public String toString() {
        return "ERIApiResponse{" +
                "id=" + id +
                ", correlationId='" + correlationId + '\'' +
                ", statusCode=" + statusCode +
                ", responseTimeMs=" + responseTimeMs +
                ", createdAt=" + createdAt +
                '}';
    }
}