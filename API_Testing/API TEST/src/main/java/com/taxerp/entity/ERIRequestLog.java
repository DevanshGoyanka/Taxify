package com.taxerp.entity;

import jakarta.persistence.*;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * ERIRequestLog entity for auditing ERI API requests.
 * Tracks all requests made to ERI endpoints with correlation IDs for traceability.
 */
@Entity
@Table(name = "eri_request_logs")
public class ERIRequestLog {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "correlation_id", unique = true, nullable = false, length = 100)
    private String correlationId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    private User user;

    @Column(nullable = false, length = 200)
    private String endpoint;

    @Column(name = "request_payload", columnDefinition = "TEXT")
    private String requestPayload;

    @Column(name = "masked_payload", columnDefinition = "TEXT")
    private String maskedPayload;

    @Column(name = "http_method", length = 10)
    private String httpMethod;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    // Default constructor
    public ERIRequestLog() {
    }

    // Constructor with required fields
    public ERIRequestLog(String correlationId, String endpoint, String httpMethod) {
        this.correlationId = correlationId;
        this.endpoint = endpoint;
        this.httpMethod = httpMethod;
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

    public User getUser() {
        return user;
    }

    public void setUser(User user) {
        this.user = user;
    }

    public String getEndpoint() {
        return endpoint;
    }

    public void setEndpoint(String endpoint) {
        this.endpoint = endpoint;
    }

    public String getRequestPayload() {
        return requestPayload;
    }

    public void setRequestPayload(String requestPayload) {
        this.requestPayload = requestPayload;
    }

    public String getMaskedPayload() {
        return maskedPayload;
    }

    public void setMaskedPayload(String maskedPayload) {
        this.maskedPayload = maskedPayload;
    }

    public String getHttpMethod() {
        return httpMethod;
    }

    public void setHttpMethod(String httpMethod) {
        this.httpMethod = httpMethod;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }

    @Override
    public String toString() {
        return "ERIRequestLog{" +
                "id=" + id +
                ", correlationId='" + correlationId + '\'' +
                ", endpoint='" + endpoint + '\'' +
                ", httpMethod='" + httpMethod + '\'' +
                ", createdAt=" + createdAt +
                '}';
    }
}