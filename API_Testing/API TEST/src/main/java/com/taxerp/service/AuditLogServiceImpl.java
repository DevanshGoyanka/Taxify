package com.taxerp.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxerp.dto.ERIRequest;
import com.taxerp.dto.ERIResponse;
import com.taxerp.entity.ERIApiResponse;
import com.taxerp.entity.ERIRequestLog;
import com.taxerp.entity.User;
import com.taxerp.repository.ERIApiResponseRepository;
import com.taxerp.repository.ERIRequestLogRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;
import java.util.regex.Pattern;

/**
 * Implementation of AuditLogService for comprehensive audit logging functionality.
 * Handles logging of ERI API interactions, signature operations, and audit trail management.
 */
@Service
@Transactional
public class AuditLogServiceImpl implements AuditLogService {

    private static final Logger logger = LoggerFactory.getLogger(AuditLogServiceImpl.class);
    
    // Patterns for sensitive data masking
    private static final Pattern PAN_PATTERN = Pattern.compile("([A-Z]{5}[0-9]{4}[A-Z]{1})", Pattern.CASE_INSENSITIVE);
    private static final Pattern AADHAAR_PATTERN = Pattern.compile("\\b\\d{4}\\s?\\d{4}\\s?\\d{4}\\b");
    private static final Pattern SIGNATURE_PATTERN = Pattern.compile("\"signature\"\\s*:\\s*\"[^\"]+\"", Pattern.CASE_INSENSITIVE);
    private static final Pattern PASSWORD_PATTERN = Pattern.compile("\"password\"\\s*:\\s*\"[^\"]+\"", Pattern.CASE_INSENSITIVE);
    private static final Pattern TOKEN_PATTERN = Pattern.compile("\"token\"\\s*:\\s*\"[^\"]+\"", Pattern.CASE_INSENSITIVE);

    private final ERIRequestLogRepository requestLogRepository;
    private final ERIApiResponseRepository responseRepository;
    private final ObjectMapper objectMapper;

    @Autowired
    public AuditLogServiceImpl(ERIRequestLogRepository requestLogRepository,
                              ERIApiResponseRepository responseRepository,
                              ObjectMapper objectMapper) {
        this.requestLogRepository = requestLogRepository;
        this.responseRepository = responseRepository;
        this.objectMapper = objectMapper;
    }

    @Override
    public ERIRequestLog logERIRequest(String correlationId, ERIRequest request, User user, String endpoint, String httpMethod) {
        logger.debug("Logging ERI request with correlation ID: {}", correlationId);
        
        try {
            // Convert request to JSON string
            String requestPayload = objectMapper.writeValueAsString(request);
            String maskedPayload = maskSensitiveData(requestPayload);
            
            // Create and populate request log entity
            ERIRequestLog requestLog = new ERIRequestLog(correlationId, endpoint, httpMethod);
            requestLog.setUser(user);
            requestLog.setRequestPayload(requestPayload);
            requestLog.setMaskedPayload(maskedPayload);
            
            // Save to database
            ERIRequestLog savedLog = requestLogRepository.save(requestLog);
            
            logger.info("ERI request logged successfully - Correlation ID: {}, Endpoint: {}, Method: {}", 
                       correlationId, endpoint, httpMethod);
            
            return savedLog;
            
        } catch (JsonProcessingException e) {
            logger.error("Failed to serialize ERI request for logging - Correlation ID: {}", correlationId, e);
            
            // Create minimal log entry even if serialization fails
            ERIRequestLog requestLog = new ERIRequestLog(correlationId, endpoint, httpMethod);
            requestLog.setUser(user);
            requestLog.setRequestPayload("SERIALIZATION_ERROR: " + e.getMessage());
            requestLog.setMaskedPayload("SERIALIZATION_ERROR");
            
            return requestLogRepository.save(requestLog);
            
        } catch (Exception e) {
            logger.error("Failed to log ERI request - Correlation ID: {}", correlationId, e);
            throw new RuntimeException("Audit logging failed for ERI request", e);
        }
    }

    @Override
    public ERIApiResponse logERIResponse(String correlationId, ERIResponse response, ERIRequestLog requestLog, long responseTimeMs) {
        logger.debug("Logging ERI response with correlation ID: {}", correlationId);
        
        try {
            // Convert response to JSON string
            String responsePayload = objectMapper.writeValueAsString(response);
            String maskedResponse = maskSensitiveData(responsePayload);
            
            // Create and populate response entity
            ERIApiResponse apiResponse = new ERIApiResponse(correlationId, requestLog, response.getHttpStatusCode());
            apiResponse.setResponsePayload(responsePayload);
            apiResponse.setMaskedResponse(maskedResponse);
            apiResponse.setResponseTimeMs((int) responseTimeMs);
            
            // Set error message if response indicates failure
            if (!response.isSuccess() && response.getMessage() != null) {
                apiResponse.setErrorMessage(response.getMessage());
            }
            
            // Save to database
            ERIApiResponse savedResponse = responseRepository.save(apiResponse);
            
            logger.info("ERI response logged successfully - Correlation ID: {}, Status: {}, Response Time: {}ms", 
                       correlationId, response.getHttpStatusCode(), responseTimeMs);
            
            return savedResponse;
            
        } catch (JsonProcessingException e) {
            logger.error("Failed to serialize ERI response for logging - Correlation ID: {}", correlationId, e);
            
            // Create minimal log entry even if serialization fails
            ERIApiResponse apiResponse = new ERIApiResponse(correlationId, requestLog, response.getHttpStatusCode());
            apiResponse.setResponsePayload("SERIALIZATION_ERROR: " + e.getMessage());
            apiResponse.setMaskedResponse("SERIALIZATION_ERROR");
            apiResponse.setResponseTimeMs((int) responseTimeMs);
            apiResponse.setErrorMessage("Response serialization failed");
            
            return responseRepository.save(apiResponse);
            
        } catch (Exception e) {
            logger.error("Failed to log ERI response - Correlation ID: {}", correlationId, e);
            throw new RuntimeException("Audit logging failed for ERI response", e);
        }
    }

    @Override
    public void logSignatureOperation(String correlationId, String operation, String status, String details, User user) {
        logger.debug("Logging signature operation - Correlation ID: {}, Operation: {}, Status: {}", 
                    correlationId, operation, status);
        
        try {
            // Log signature operations using structured logging
            if (user != null) {
                logger.info("DSC_OPERATION - Correlation ID: {}, Operation: {}, Status: {}, User: {}, Details: {}", 
                           correlationId, operation, status, user.getUsername(), 
                           details != null ? maskSensitiveData(details) : "N/A");
            } else {
                logger.info("DSC_OPERATION - Correlation ID: {}, Operation: {}, Status: {}, User: SYSTEM, Details: {}", 
                           correlationId, operation, status, 
                           details != null ? maskSensitiveData(details) : "N/A");
            }
            
            // For critical signature operations, also create database audit entries
            if ("SIGN_PAYLOAD".equals(operation) || "VALIDATE_KEYSTORE".equals(operation)) {
                // Create a special request log entry for signature operations
                ERIRequestLog signatureLog = new ERIRequestLog(correlationId, "DSC_SIGNATURE_SERVICE", operation);
                signatureLog.setUser(user);
                signatureLog.setRequestPayload(String.format("Operation: %s, Status: %s", operation, status));
                signatureLog.setMaskedPayload(String.format("Operation: %s, Status: %s", operation, status));
                
                requestLogRepository.save(signatureLog);
                
                logger.debug("Signature operation persisted to database - Correlation ID: {}", correlationId);
            }
            
        } catch (Exception e) {
            logger.error("Failed to log signature operation - Correlation ID: {}, Operation: {}", 
                        correlationId, operation, e);
            // Don't throw exception for signature logging failures to avoid disrupting main operations
        }
    }

    @Override
    public String generateCorrelationId() {
        return "req-" + UUID.randomUUID().toString();
    }

    @Override
    public String maskSensitiveData(String payload) {
        if (payload == null || payload.trim().isEmpty()) {
            return payload;
        }
        
        try {
            String masked = payload;
            
            // Mask PAN numbers
            masked = PAN_PATTERN.matcher(masked).replaceAll("***PAN_MASKED***");
            
            // Mask Aadhaar numbers
            masked = AADHAAR_PATTERN.matcher(masked).replaceAll("***AADHAAR_MASKED***");
            
            // Mask signatures
            masked = SIGNATURE_PATTERN.matcher(masked).replaceAll("\"signature\":\"***SIGNATURE_MASKED***\"");
            
            // Mask passwords
            masked = PASSWORD_PATTERN.matcher(masked).replaceAll("\"password\":\"***PASSWORD_MASKED***\"");
            
            // Mask tokens
            masked = TOKEN_PATTERN.matcher(masked).replaceAll("\"token\":\"***TOKEN_MASKED***\"");
            
            return masked;
            
        } catch (Exception e) {
            logger.warn("Failed to mask sensitive data, returning original payload", e);
            return payload;
        }
    }

    @Override
    @Transactional(readOnly = true)
    public AuditTrail getAuditTrail(String correlationId) {
        logger.debug("Retrieving audit trail for correlation ID: {}", correlationId);
        
        try {
            // Find request log by correlation ID
            ERIRequestLog requestLog = requestLogRepository.findByCorrelationId(correlationId).orElse(null);
            
            // Find response log by correlation ID
            ERIApiResponse responseLog = responseRepository.findByCorrelationId(correlationId).orElse(null);
            
            AuditTrail auditTrail = new AuditTrail(correlationId, requestLog, responseLog);
            
            logger.debug("Audit trail retrieved - Correlation ID: {}, Complete: {}", 
                        correlationId, auditTrail.isComplete());
            
            return auditTrail;
            
        } catch (Exception e) {
            logger.error("Failed to retrieve audit trail - Correlation ID: {}", correlationId, e);
            return new AuditTrail(correlationId, null, null);
        }
    }
}