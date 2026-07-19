package com.taxerp.service;

import com.taxerp.dto.ERIRequest;
import com.taxerp.dto.ERIResponse;
import com.taxerp.entity.ERIApiResponse;
import com.taxerp.entity.ERIRequestLog;
import com.taxerp.entity.User;

/**
 * Service interface for comprehensive audit logging functionality.
 * Provides methods for logging ERI API interactions, signature operations, and maintaining audit trails.
 */
public interface AuditLogService {

    /**
     * Logs an ERI API request with correlation ID tracking.
     * Creates a new audit record for the outgoing request to ERI endpoints.
     *
     * @param correlationId Unique identifier for tracking the request across services
     * @param request The ERI request being made
     * @param user The user making the request (optional, can be null for system requests)
     * @param endpoint The ERI endpoint being called
     * @param httpMethod The HTTP method used (GET, POST, etc.)
     * @return The created ERIRequestLog entity for further reference
     */
    ERIRequestLog logERIRequest(String correlationId, ERIRequest request, User user, String endpoint, String httpMethod);

    /**
     * Logs an ERI API response with timing and status information.
     * Creates a response audit record linked to the original request.
     *
     * @param correlationId Unique identifier linking to the original request
     * @param response The ERI response received
     * @param requestLog The original request log entry to link to
     * @param responseTimeMs The response time in milliseconds
     * @return The created ERIApiResponse entity for further reference
     */
    ERIApiResponse logERIResponse(String correlationId, ERIResponse response, ERIRequestLog requestLog, long responseTimeMs);

    /**
     * Logs signature operations for audit trail compliance.
     * Records DSC signature generation, validation, and related operations.
     *
     * @param correlationId Unique identifier for tracking the operation
     * @param operation Description of the signature operation (e.g., "SIGN_PAYLOAD", "VALIDATE_KEYSTORE")
     * @param status Status of the operation (e.g., "SUCCESS", "FAILED")
     * @param details Additional details about the operation (optional)
     * @param user The user performing the operation (optional)
     */
    void logSignatureOperation(String correlationId, String operation, String status, String details, User user);

    /**
     * Generates a unique correlation ID for tracking operations across services.
     * Uses UUID format with a prefix for easy identification.
     *
     * @return A unique correlation ID string
     */
    String generateCorrelationId();

    /**
     * Masks sensitive data in payloads for secure logging.
     * Removes or masks PII, authentication tokens, and other sensitive information.
     *
     * @param payload The original payload to mask
     * @return The masked payload safe for logging
     */
    String maskSensitiveData(String payload);

    /**
     * Retrieves audit logs by correlation ID for investigation purposes.
     * Returns both request and response logs associated with the correlation ID.
     *
     * @param correlationId The correlation ID to search for
     * @return AuditTrail containing related request and response logs
     */
    AuditTrail getAuditTrail(String correlationId);

    /**
     * Container class for audit trail information
     */
    class AuditTrail {
        private final ERIRequestLog requestLog;
        private final ERIApiResponse responseLog;
        private final String correlationId;

        public AuditTrail(String correlationId, ERIRequestLog requestLog, ERIApiResponse responseLog) {
            this.correlationId = correlationId;
            this.requestLog = requestLog;
            this.responseLog = responseLog;
        }

        public ERIRequestLog getRequestLog() {
            return requestLog;
        }

        public ERIApiResponse getResponseLog() {
            return responseLog;
        }

        public String getCorrelationId() {
            return correlationId;
        }

        public boolean isComplete() {
            return requestLog != null && responseLog != null;
        }

        @Override
        public String toString() {
            return "AuditTrail{" +
                    "correlationId='" + correlationId + '\'' +
                    ", hasRequest=" + (requestLog != null) +
                    ", hasResponse=" + (responseLog != null) +
                    ", isComplete=" + isComplete() +
                    '}';
        }
    }
}