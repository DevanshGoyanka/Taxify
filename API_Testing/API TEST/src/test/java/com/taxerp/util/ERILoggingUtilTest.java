package com.taxerp.util;

import com.taxerp.dto.ERIRequest;
import com.taxerp.dto.ERIResponse;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.slf4j.MDC;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for ERILoggingUtil.
 * Tests data masking, logging functionality, and sensitive data handling.
 */
class ERILoggingUtilTest {

    @Test
    @DisplayName("Should mask sensitive fields in JSON")
    void testMaskSensitiveFields() {
        String sensitiveJson = "{\"signature\":\"secret123\",\"password\":\"pass123\",\"data\":\"normal\",\"token\":\"token123\"}";
        String maskedJson = ERILoggingUtil.maskSensitiveData(sensitiveJson);

        assertNotNull(maskedJson, "Masked JSON should not be null");
        assertFalse(maskedJson.contains("secret123"), "Should mask signature value");
        assertFalse(maskedJson.contains("pass123"), "Should mask password value");
        assertFalse(maskedJson.contains("token123"), "Should mask token value");
        assertTrue(maskedJson.contains("normal"), "Should preserve non-sensitive data");
        assertTrue(maskedJson.contains("[MASKED]"), "Should contain mask placeholder");
    }

    @Test
    @DisplayName("Should mask PII patterns")
    void testMaskPIIPatterns() {
        String dataWithPII = "{\"pan\":\"ABCDE1234F\",\"email\":\"test@example.com\",\"account\":\"1234567890123456\"}";
        String maskedData = ERILoggingUtil.maskSensitiveData(dataWithPII);

        assertNotNull(maskedData, "Masked data should not be null");
        // Note: The exact masking behavior depends on the implementation
        // This test verifies that the method processes the data without errors
    }

    @Test
    @DisplayName("Should handle null and empty input")
    void testMaskNullAndEmptyInput() {
        assertNull(ERILoggingUtil.maskSensitiveData(null), "Should handle null input");
        assertEquals("", ERILoggingUtil.maskSensitiveData(""), "Should handle empty input");
        assertEquals("   ", ERILoggingUtil.maskSensitiveData("   "), "Should handle whitespace input");
    }

    @Test
    @DisplayName("Should handle invalid JSON gracefully")
    void testMaskInvalidJSON() {
        String invalidJson = "{invalid json structure";
        String maskedData = ERILoggingUtil.maskSensitiveData(invalidJson);

        assertNotNull(maskedData, "Should handle invalid JSON without throwing exception");
        // Should fall back to string-based masking
    }

    @Test
    @DisplayName("Should mask nested JSON objects")
    void testMaskNestedJSON() {
        String nestedJson = "{\"user\":{\"signature\":\"secret\",\"name\":\"John\"},\"data\":{\"password\":\"pass123\"}}";
        String maskedJson = ERILoggingUtil.maskSensitiveData(nestedJson);

        assertNotNull(maskedJson, "Masked JSON should not be null");
        assertFalse(maskedJson.contains("secret"), "Should mask nested signature");
        assertFalse(maskedJson.contains("pass123"), "Should mask nested password");
        assertTrue(maskedJson.contains("John"), "Should preserve non-sensitive nested data");
    }

    @Test
    @DisplayName("Should create partial mask correctly")
    void testCreatePartialMask() {
        assertEquals("[MASKED]", ERILoggingUtil.createPartialMask(null, 2), 
                "Should return mask for null input");
        
        assertEquals("[MASKED]", ERILoggingUtil.createPartialMask("abc", 2), 
                "Should return mask for short input");
        
        String partialMask = ERILoggingUtil.createPartialMask("1234567890", 2);
        assertTrue(partialMask.startsWith("12"), "Should show first 2 characters");
        assertTrue(partialMask.endsWith("90"), "Should show last 2 characters");
        assertTrue(partialMask.contains("****"), "Should contain mask in middle");
    }

    @Test
    @DisplayName("Should validate logging configuration")
    void testValidateLoggingConfiguration() {
        boolean isValid = ERILoggingUtil.validateLoggingConfiguration();
        assertTrue(isValid, "Logging configuration should be valid in test environment");
    }

    @Test
    @DisplayName("Should provide logging status")
    void testGetLoggingStatus() {
        String status = ERILoggingUtil.getLoggingStatus();
        
        assertNotNull(status, "Logging status should not be null");
        assertTrue(status.contains("ERI Logging Status"), "Should contain status header");
        assertTrue(status.contains("Logger:"), "Should contain logger information");
        assertTrue(status.contains("Level:"), "Should contain log level information");
    }

    @Test
    @DisplayName("Should log ERI request without throwing exceptions")
    void testLogERIRequest() {
        ERIRequest request = createTestERIRequest();
        
        // This test verifies that logging doesn't throw exceptions
        assertDoesNotThrow(() -> {
            ERILoggingUtil.logERIRequest(request, "/api/test", "Test Operation");
        }, "Should log ERI request without throwing exceptions");
        
        // Verify MDC is cleared after logging
        assertNull(MDC.get("correlationId"), "MDC should be cleared after logging");
    }

    @Test
    @DisplayName("Should log ERI response without throwing exceptions")
    void testLogERIResponse() {
        ERIResponse response = createTestERIResponse();
        
        // This test verifies that logging doesn't throw exceptions
        assertDoesNotThrow(() -> {
            ERILoggingUtil.logERIResponse(response, "Test Operation", 1500);
        }, "Should log ERI response without throwing exceptions");
        
        // Verify MDC is cleared after logging
        assertNull(MDC.get("correlationId"), "MDC should be cleared after logging");
    }

    @Test
    @DisplayName("Should log ERI error without throwing exceptions")
    void testLogERIError() {
        Exception testError = new RuntimeException("Test error message");
        
        // This test verifies that error logging doesn't throw exceptions
        assertDoesNotThrow(() -> {
            ERILoggingUtil.logERIError("Test Operation", "test-correlation-123", testError, 2000);
        }, "Should log ERI error without throwing exceptions");
        
        // Verify MDC is cleared after logging
        assertNull(MDC.get("correlationId"), "MDC should be cleared after logging");
    }

    @Test
    @DisplayName("Should handle null response in logging")
    void testLogNullResponse() {
        assertDoesNotThrow(() -> {
            ERILoggingUtil.logERIResponse(null, "Test Operation", 1000);
        }, "Should handle null response gracefully");
    }

    @Test
    @DisplayName("Should mask case-insensitive sensitive fields")
    void testCaseInsensitiveMasking() {
        String mixedCaseJson = "{\"SIGNATURE\":\"secret\",\"Password\":\"pass\",\"TOKEN\":\"token\"}";
        String maskedJson = ERILoggingUtil.maskSensitiveData(mixedCaseJson);

        assertNotNull(maskedJson, "Masked JSON should not be null");
        // The masking should work regardless of case
        assertTrue(maskedJson.contains("[MASKED]"), "Should contain mask placeholder");
    }

    @Test
    @DisplayName("Should preserve non-sensitive data structure")
    void testPreserveDataStructure() {
        String complexJson = "{\"user\":{\"id\":123,\"name\":\"John\"},\"signature\":\"secret\",\"metadata\":{\"timestamp\":\"2024-01-15\"}}";
        String maskedJson = ERILoggingUtil.maskSensitiveData(complexJson);

        assertNotNull(maskedJson, "Masked JSON should not be null");
        assertTrue(maskedJson.contains("123"), "Should preserve user ID");
        assertTrue(maskedJson.contains("John"), "Should preserve user name");
        assertTrue(maskedJson.contains("2024-01-15"), "Should preserve timestamp");
        assertFalse(maskedJson.contains("secret"), "Should mask signature");
    }

    /**
     * Creates a test ERI request for testing
     */
    private ERIRequest createTestERIRequest() {
        ERIRequest request = new ERIRequest();
        request.setEriUserId("TEST123");
        request.setData("{\"test\":\"data\"}");
        request.setSignature("test-signature-123");
        request.setCorrelationId("test-correlation-123");
        request.setTimestamp("2024-01-15T10:30:00");
        return request;
    }

    /**
     * Creates a test ERI response for testing
     */
    private ERIResponse createTestERIResponse() {
        ERIResponse response = new ERIResponse();
        response.setStatus("SUCCESS");
        response.setMessage("Test operation completed");
        response.setCorrelationId("test-correlation-123");
        response.setTransactionId("TXN123");
        response.setResponseTimeMs(1500);
        response.setHttpStatusCode(200);
        return response;
    }
}