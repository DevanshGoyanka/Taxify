package com.taxerp.service;

import com.taxerp.dto.ERIRequest;
import com.taxerp.dto.ERIResponse;
import com.taxerp.entity.ERIApiResponse;
import com.taxerp.entity.ERIRequestLog;
import com.taxerp.entity.User;
import com.taxerp.repository.ERIApiResponseRepository;
import com.taxerp.repository.ERIRequestLogRepository;
import com.taxerp.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Integration tests for AuditLogService with real database operations.
 * Tests end-to-end audit logging functionality including database persistence.
 */
@SpringBootTest
@ActiveProfiles("test")
@Transactional
@DisplayName("AuditLogService Integration Tests")
class AuditLogServiceIntegrationTest {

    @Autowired
    private AuditLogService auditLogService;

    @Autowired
    private ERIRequestLogRepository requestLogRepository;

    @Autowired
    private ERIApiResponseRepository responseRepository;

    @Autowired
    private UserRepository userRepository;

    private User testUser;
    private ERIRequest testRequest;
    private ERIResponse testResponse;

    @BeforeEach
    void setUp() {
        // Create and save test user
        testUser = new User("integrationtest", "integration@test.com");
        testUser.setFullName("Integration Test User");
        testUser.setOrganization("Test Organization");
        testUser = userRepository.save(testUser);

        // Create test ERI request
        testRequest = new ERIRequest();
        testRequest.setEriUserId("INTEGRATION_TEST_USER");
        testRequest.setData("{\"taxYear\":\"2024\",\"pan\":\"ABCDE1234F\",\"income\":50000}");
        testRequest.setSignature("integration_test_signature_data_12345");
        testRequest.setTimestamp(LocalDateTime.now().toString());

        // Create test ERI response
        testResponse = new ERIResponse();
        testResponse.setStatus("SUCCESS");
        testResponse.setMessage("Integration test processed successfully");
        testResponse.setHttpStatusCode(200);
        testResponse.setTransactionId("INTEGRATION_TXN_123456");
    }

    @Test
    @DisplayName("Should create complete audit trail with database persistence")
    void shouldCreateCompleteAuditTrailWithDatabasePersistence() {
        // Given
        String correlationId = auditLogService.generateCorrelationId();
        String endpoint = "/api/integration-test";
        String httpMethod = "POST";
        long responseTimeMs = 1200L;

        testRequest.setCorrelationId(correlationId);
        testResponse.setCorrelationId(correlationId);

        // When - Log request
        ERIRequestLog requestLog = auditLogService.logERIRequest(correlationId, testRequest, testUser, endpoint, httpMethod);

        // Then - Verify request log is persisted
        assertNotNull(requestLog);
        assertNotNull(requestLog.getId());
        assertEquals(correlationId, requestLog.getCorrelationId());
        assertEquals(testUser.getId(), requestLog.getUser().getId());
        assertEquals(endpoint, requestLog.getEndpoint());
        assertEquals(httpMethod, requestLog.getHttpMethod());
        assertNotNull(requestLog.getCreatedAt());

        // Verify sensitive data is masked
        assertFalse(requestLog.getMaskedPayload().contains("ABCDE1234F"));
        assertFalse(requestLog.getMaskedPayload().contains("integration_test_signature_data_12345"));
        assertTrue(requestLog.getMaskedPayload().contains("***PAN_MASKED***"));
        assertTrue(requestLog.getMaskedPayload().contains("***SIGNATURE_MASKED***"));

        // When - Log response
        ERIApiResponse responseLog = auditLogService.logERIResponse(correlationId, testResponse, requestLog, responseTimeMs);

        // Then - Verify response log is persisted
        assertNotNull(responseLog);
        assertNotNull(responseLog.getId());
        assertEquals(correlationId, responseLog.getCorrelationId());
        assertEquals(requestLog.getId(), responseLog.getRequestLog().getId());
        assertEquals(200, responseLog.getStatusCode());
        assertEquals((int) responseTimeMs, responseLog.getResponseTimeMs());
        assertNotNull(responseLog.getCreatedAt());

        // Verify audit trail can be retrieved
        AuditLogService.AuditTrail auditTrail = auditLogService.getAuditTrail(correlationId);
        assertNotNull(auditTrail);
        assertTrue(auditTrail.isComplete());
        assertEquals(requestLog.getId(), auditTrail.getRequestLog().getId());
        assertEquals(responseLog.getId(), auditTrail.getResponseLog().getId());
    }

    @Test
    @DisplayName("Should persist signature operation audit logs for critical operations")
    void shouldPersistSignatureOperationAuditLogsForCriticalOperations() {
        // Given
        String correlationId = auditLogService.generateCorrelationId();
        String operation = "SIGN_PAYLOAD";
        String status = "SUCCESS";
        String details = "Integration test payload signed successfully";

        // When
        auditLogService.logSignatureOperation(correlationId, operation, status, details, testUser);

        // Then - Verify signature operation is persisted for critical operations
        Optional<ERIRequestLog> signatureLog = requestLogRepository.findByCorrelationId(correlationId);
        assertTrue(signatureLog.isPresent());

        ERIRequestLog log = signatureLog.get();
        assertEquals(correlationId, log.getCorrelationId());
        assertEquals("DSC_SIGNATURE_SERVICE", log.getEndpoint());
        assertEquals(operation, log.getHttpMethod());
        assertEquals(testUser.getId(), log.getUser().getId());
        assertTrue(log.getRequestPayload().contains("Operation: " + operation));
        assertTrue(log.getRequestPayload().contains("Status: " + status));
    }

    @Test
    @DisplayName("Should handle error responses with proper audit logging")
    void shouldHandleErrorResponsesWithProperAuditLogging() {
        // Given
        String correlationId = auditLogService.generateCorrelationId();
        String endpoint = "/api/error-test";
        String httpMethod = "POST";
        long responseTimeMs = 3000L;

        testRequest.setCorrelationId(correlationId);

        ERIResponse errorResponse = new ERIResponse();
        errorResponse.setStatus("ERROR");
        errorResponse.setMessage("Integration test error occurred");
        errorResponse.setHttpStatusCode(500);
        errorResponse.setCorrelationId(correlationId);
        errorResponse.setErrorCode("INTEGRATION_TEST_ERROR");

        // When
        ERIRequestLog requestLog = auditLogService.logERIRequest(correlationId, testRequest, testUser, endpoint, httpMethod);
        ERIApiResponse responseLog = auditLogService.logERIResponse(correlationId, errorResponse, requestLog, responseTimeMs);

        // Then
        assertNotNull(responseLog);
        assertEquals(500, responseLog.getStatusCode());
        assertEquals("Integration test error occurred", responseLog.getErrorMessage());
        assertEquals((int) responseTimeMs, responseLog.getResponseTimeMs());

        // Verify audit trail shows error
        AuditLogService.AuditTrail auditTrail = auditLogService.getAuditTrail(correlationId);
        assertTrue(auditTrail.isComplete());
        assertEquals(500, auditTrail.getResponseLog().getStatusCode());
        assertNotNull(auditTrail.getResponseLog().getErrorMessage());
    }

    @Test
    @DisplayName("Should mask various types of sensitive data in real payloads")
    void shouldMaskVariousTypesOfSensitiveDataInRealPayloads() {
        // Given
        String sensitivePayload = "{\n" +
                "  \"pan\": \"ABCDE1234F\",\n" +
                "  \"aadhaar\": \"1234 5678 9012\",\n" +
                "  \"signature\": \"MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC\",\n" +
                "  \"password\": \"mySecretPassword123\",\n" +
                "  \"token\": \"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\",\n" +
                "  \"normalField\": \"this should not be masked\"\n" +
                "}";

        // When
        String maskedPayload = auditLogService.maskSensitiveData(sensitivePayload);

        // Then
        assertNotNull(maskedPayload);
        
        // Verify PAN is masked
        assertFalse(maskedPayload.contains("ABCDE1234F"));
        assertTrue(maskedPayload.contains("***PAN_MASKED***"));
        
        // Verify Aadhaar is masked
        assertFalse(maskedPayload.contains("1234 5678 9012"));
        assertTrue(maskedPayload.contains("***AADHAAR_MASKED***"));
        
        // Verify signature is masked
        assertFalse(maskedPayload.contains("MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC"));
        assertTrue(maskedPayload.contains("***SIGNATURE_MASKED***"));
        
        // Verify password is masked
        assertFalse(maskedPayload.contains("mySecretPassword123"));
        assertTrue(maskedPayload.contains("***PASSWORD_MASKED***"));
        
        // Verify token is masked
        assertFalse(maskedPayload.contains("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"));
        assertTrue(maskedPayload.contains("***TOKEN_MASKED***"));
        
        // Verify normal field is not masked
        assertTrue(maskedPayload.contains("this should not be masked"));
    }

    @Test
    @DisplayName("Should track correlation IDs across multiple operations")
    void shouldTrackCorrelationIdsAcrossMultipleOperations() {
        // Given
        String correlationId = auditLogService.generateCorrelationId();
        
        // When - Perform multiple operations with same correlation ID
        
        // 1. Signature operation
        auditLogService.logSignatureOperation(correlationId, "VALIDATE_KEYSTORE", "SUCCESS", 
                "Keystore validation successful", testUser);
        
        // 2. ERI request
        testRequest.setCorrelationId(correlationId);
        ERIRequestLog requestLog = auditLogService.logERIRequest(correlationId, testRequest, testUser, 
                "/api/multi-op-test", "POST");
        
        // 3. Another signature operation
        auditLogService.logSignatureOperation(correlationId, "SIGN_PAYLOAD", "SUCCESS", 
                "Payload signed for multi-operation test", testUser);
        
        // 4. ERI response
        testResponse.setCorrelationId(correlationId);
        ERIApiResponse responseLog = auditLogService.logERIResponse(correlationId, testResponse, requestLog, 1500L);

        // Then - Verify all operations are linked by correlation ID
        AuditLogService.AuditTrail auditTrail = auditLogService.getAuditTrail(correlationId);
        assertTrue(auditTrail.isComplete());
        assertEquals(correlationId, auditTrail.getCorrelationId());
        
        // Verify signature operations are also logged (for critical operations)
        Optional<ERIRequestLog> signatureLog = requestLogRepository.findByCorrelationId(correlationId);
        assertTrue(signatureLog.isPresent());
        assertEquals("SIGN_PAYLOAD", signatureLog.get().getHttpMethod()); // Last critical operation
    }

    @Test
    @DisplayName("Should handle concurrent audit logging operations")
    void shouldHandleConcurrentAuditLoggingOperations() throws InterruptedException {
        // Given
        int numberOfThreads = 5;
        Thread[] threads = new Thread[numberOfThreads];
        String[] correlationIds = new String[numberOfThreads];

        // When - Create multiple threads performing audit logging
        for (int i = 0; i < numberOfThreads; i++) {
            final int threadIndex = i;
            correlationIds[i] = auditLogService.generateCorrelationId();
            
            threads[i] = new Thread(() -> {
                try {
                    String correlationId = correlationIds[threadIndex];
                    
                    ERIRequest request = new ERIRequest();
                    request.setEriUserId("CONCURRENT_TEST_" + threadIndex);
                    request.setData("{\"threadId\":" + threadIndex + "}");
                    request.setSignature("concurrent_signature_" + threadIndex);
                    request.setCorrelationId(correlationId);
                    
                    ERIResponse response = new ERIResponse();
                    response.setStatus("SUCCESS");
                    response.setMessage("Concurrent test " + threadIndex);
                    response.setHttpStatusCode(200);
                    response.setCorrelationId(correlationId);
                    
                    ERIRequestLog requestLog = auditLogService.logERIRequest(correlationId, request, testUser, 
                            "/api/concurrent-test", "POST");
                    auditLogService.logERIResponse(correlationId, response, requestLog, 1000L);
                    
                } catch (Exception e) {
                    fail("Concurrent audit logging failed: " + e.getMessage());
                }
            });
        }

        // Start all threads
        for (Thread thread : threads) {
            thread.start();
        }

        // Wait for all threads to complete
        for (Thread thread : threads) {
            thread.join(5000); // 5 second timeout
        }

        // Then - Verify all audit logs were created successfully
        for (String correlationId : correlationIds) {
            AuditLogService.AuditTrail auditTrail = auditLogService.getAuditTrail(correlationId);
            assertTrue(auditTrail.isComplete(), "Audit trail should be complete for correlation ID: " + correlationId);
        }
    }
}