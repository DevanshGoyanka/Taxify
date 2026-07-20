package com.taxerp.util;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.taxerp.dto.ERIRequest;
import com.taxerp.dto.ERIResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Arrays;
import java.util.List;
import java.util.regex.Pattern;

/**
 * Utility class for comprehensive ERI API request/response logging with data masking.
 * Provides secure logging capabilities that mask sensitive information while maintaining audit trails.
 */
public class ERILoggingUtil {

    private static final Logger logger = LoggerFactory.getLogger(ERILoggingUtil.class);
    private static final ObjectMapper objectMapper = new ObjectMapper();

    // Sensitive field patterns for masking
    private static final List<String> SENSITIVE_FIELDS = Arrays.asList(
            "signature", "password", "token", "key", "secret", "auth", "credential",
            "pan", "aadhaar", "aadhar", "ssn", "tin", "gstin", "bankAccount", "accountNumber"
    );

    // PII patterns for regex-based masking
    private static final List<Pattern> PII_PATTERNS = Arrays.asList(
            Pattern.compile("\\b[A-Z]{5}[0-9]{4}[A-Z]\\b"), // PAN pattern
            Pattern.compile("\\b[0-9]{4}\\s?[0-9]{4}\\s?[0-9]{4}\\b"), // Aadhaar pattern
            Pattern.compile("\\b[0-9]{10,16}\\b"), // Bank account pattern
            Pattern.compile("\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b", Pattern.CASE_INSENSITIVE) // Email pattern
    );

    private static final String MASK_VALUE = "[MASKED]";
    private static final String PARTIAL_MASK_PATTERN = "****";

    /**
     * Logs ERI API request with data masking and correlation tracking
     *
     * @param request The ERI request to log
     * @param endpoint The API endpoint being called
     * @param operationName The name of the operation
     */
    public static void logERIRequest(ERIRequest request, String endpoint, String operationName) {
        String correlationId = request.getCorrelationId();
        
        try {
            // Set MDC for correlation tracking
            MDC.put("correlationId", correlationId);
            MDC.put("operation", operationName);
            MDC.put("endpoint", endpoint);
            
            // Create masked request for logging
            String maskedRequest = maskSensitiveData(objectMapper.writeValueAsString(request));
            
            logger.info("ERI API Request - Operation: {}, Endpoint: {}, CorrelationId: {}, Timestamp: {}", 
                    operationName, endpoint, correlationId, getCurrentTimestamp());
            logger.debug("ERI Request Details - CorrelationId: {}, Payload: {}", correlationId, maskedRequest);
            
            // Log request metadata
            logger.info("ERI Request Metadata - CorrelationId: {}, EriUserId: {}, HasSignature: {}, DataType: {}", 
                    correlationId, 
                    request.getEriUserId(),
                    request.getSignature() != null && !request.getSignature().isEmpty(),
                    request.getData() != null ? request.getData().getClass().getSimpleName() : "null");
                    
        } catch (JsonProcessingException e) {
            logger.error("Failed to serialize ERI request for logging - CorrelationId: {}", correlationId, e);
        } finally {
            // Clear MDC to prevent memory leaks
            MDC.clear();
        }
    }

    /**
     * Logs ERI API response with data masking and performance metrics
     *
     * @param response The ERI response to log
     * @param operationName The name of the operation
     * @param responseTimeMs The response time in milliseconds
     */
    public static void logERIResponse(ERIResponse response, String operationName, long responseTimeMs) {
        String correlationId = response != null ? response.getCorrelationId() : "unknown";
        
        try {
            // Set MDC for correlation tracking
            MDC.put("correlationId", correlationId);
            MDC.put("operation", operationName);
            
            if (response != null) {
                // Create masked response for logging
                String maskedResponse = maskSensitiveData(objectMapper.writeValueAsString(response));
                
                logger.info("ERI API Response - Operation: {}, CorrelationId: {}, Status: {}, ResponseTime: {}ms, HttpStatus: {}", 
                        operationName, correlationId, response.getStatus(), responseTimeMs, response.getHttpStatusCode());
                logger.debug("ERI Response Details - CorrelationId: {}, Payload: {}", correlationId, maskedResponse);
                
                // Log response metadata
                logger.info("ERI Response Metadata - CorrelationId: {}, Success: {}, HasData: {}, TransactionId: {}, ErrorCode: {}", 
                        correlationId,
                        response.isSuccess(),
                        response.getData() != null,
                        response.getTransactionId(),
                        response.getErrorCode());
                        
                // Log performance metrics
                if (responseTimeMs > 5000) { // Log slow responses
                    logger.warn("Slow ERI API Response - Operation: {}, CorrelationId: {}, ResponseTime: {}ms", 
                            operationName, correlationId, responseTimeMs);
                }
            } else {
                logger.error("ERI API Response is null - Operation: {}, CorrelationId: {}, ResponseTime: {}ms", 
                        operationName, correlationId, responseTimeMs);
            }
            
        } catch (JsonProcessingException e) {
            logger.error("Failed to serialize ERI response for logging - CorrelationId: {}", correlationId, e);
        } finally {
            // Clear MDC to prevent memory leaks
            MDC.clear();
        }
    }

    /**
     * Logs ERI API errors with detailed error information
     *
     * @param operationName The name of the operation
     * @param correlationId The correlation ID
     * @param error The error that occurred
     * @param responseTimeMs The response time in milliseconds
     */
    public static void logERIError(String operationName, String correlationId, Throwable error, long responseTimeMs) {
        try {
            // Set MDC for correlation tracking
            MDC.put("correlationId", correlationId);
            MDC.put("operation", operationName);
            
            logger.error("ERI API Error - Operation: {}, CorrelationId: {}, ErrorType: {}, ResponseTime: {}ms, Message: {}", 
                    operationName, correlationId, error.getClass().getSimpleName(), responseTimeMs, error.getMessage());
            
            // Log additional error details for debugging
            if (logger.isDebugEnabled()) {
                logger.debug("ERI API Error Details - CorrelationId: {}, StackTrace: ", correlationId, error);
            }
            
        } finally {
            // Clear MDC to prevent memory leaks
            MDC.clear();
        }
    }

    /**
     * Masks sensitive data in JSON strings
     *
     * @param jsonString The JSON string to mask
     * @return Masked JSON string
     */
    public static String maskSensitiveData(String jsonString) {
        if (jsonString == null || jsonString.trim().isEmpty()) {
            return jsonString;
        }

        try {
            // Parse JSON and mask sensitive fields
            JsonNode rootNode = objectMapper.readTree(jsonString);
            JsonNode maskedNode = maskJsonNode(rootNode);
            String maskedJson = objectMapper.writeValueAsString(maskedNode);
            
            // Apply regex-based PII masking
            return maskPIIPatterns(maskedJson);
            
        } catch (JsonProcessingException e) {
            logger.debug("Failed to parse JSON for masking, applying string-based masking", e);
            return maskSensitiveDataString(jsonString);
        }
    }

    /**
     * Recursively masks sensitive fields in JSON nodes
     */
    private static JsonNode maskJsonNode(JsonNode node) {
        if (node.isObject()) {
            ObjectNode objectNode = (ObjectNode) node;
            ObjectNode maskedNode = objectMapper.createObjectNode();
            
            objectNode.fields().forEachRemaining(entry -> {
                String fieldName = entry.getKey();
                JsonNode fieldValue = entry.getValue();
                
                if (isSensitiveField(fieldName)) {
                    maskedNode.put(fieldName, MASK_VALUE);
                } else if (fieldValue.isObject() || fieldValue.isArray()) {
                    maskedNode.set(fieldName, maskJsonNode(fieldValue));
                } else {
                    maskedNode.set(fieldName, fieldValue);
                }
            });
            
            return maskedNode;
            
        } else if (node.isArray()) {
            for (int i = 0; i < node.size(); i++) {
                JsonNode arrayElement = node.get(i);
                if (arrayElement.isObject() || arrayElement.isArray()) {
                    ((ObjectNode) node).set(String.valueOf(i), maskJsonNode(arrayElement));
                }
            }
        }
        
        return node;
    }

    /**
     * Checks if a field name is considered sensitive
     */
    private static boolean isSensitiveField(String fieldName) {
        String lowerFieldName = fieldName.toLowerCase();
        return SENSITIVE_FIELDS.stream().anyMatch(lowerFieldName::contains);
    }

    /**
     * Applies string-based masking for non-JSON content
     */
    private static String maskSensitiveDataString(String data) {
        String maskedData = data;
        
        // Mask sensitive field patterns
        for (String sensitiveField : SENSITIVE_FIELDS) {
            String pattern = "\"" + sensitiveField + "\"\\s*:\\s*\"[^\"]+\"";
            maskedData = maskedData.replaceAll("(?i)" + pattern, "\"" + sensitiveField + "\":\"" + MASK_VALUE + "\"");
        }
        
        return maskedData;
    }

    /**
     * Masks PII patterns using regex
     */
    private static String maskPIIPatterns(String data) {
        String maskedData = data;
        
        for (Pattern pattern : PII_PATTERNS) {
            maskedData = pattern.matcher(maskedData).replaceAll(PARTIAL_MASK_PATTERN);
        }
        
        return maskedData;
    }

    /**
     * Creates a partial mask for sensitive values (shows first and last characters)
     *
     * @param value The value to partially mask
     * @param visibleChars Number of characters to show at start and end
     * @return Partially masked value
     */
    public static String createPartialMask(String value, int visibleChars) {
        if (value == null || value.length() <= visibleChars * 2) {
            return MASK_VALUE;
        }
        
        String start = value.substring(0, visibleChars);
        String end = value.substring(value.length() - visibleChars);
        return start + PARTIAL_MASK_PATTERN + end;
    }

    /**
     * Gets current timestamp in ISO format
     */
    private static String getCurrentTimestamp() {
        return LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME);
    }

    /**
     * Validates if logging configuration is properly set up
     *
     * @return true if logging is properly configured
     */
    public static boolean validateLoggingConfiguration() {
        try {
            // Test basic logging functionality
            logger.info("ERI Logging validation test");
            
            // Test MDC functionality
            MDC.put("test", "validation");
            logger.debug("MDC test");
            MDC.clear();
            
            return true;
            
        } catch (Exception e) {
            logger.error("Logging configuration validation failed", e);
            return false;
        }
    }

    /**
     * Gets logging statistics and configuration info
     *
     * @return Logging configuration description
     */
    public static String getLoggingStatus() {
        return String.format("ERI Logging Status - Logger: %s, Level: %s, MDC Support: %s, Masking: enabled",
                logger.getName(),
                logger.isDebugEnabled() ? "DEBUG" : logger.isInfoEnabled() ? "INFO" : "WARN",
                MDC.getCopyOfContextMap() != null ? "available" : "not available");
    }
}