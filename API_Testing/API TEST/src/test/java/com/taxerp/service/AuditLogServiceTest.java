package com.taxerp.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxerp.dto.ERIRequest;
import com.taxerp.dto.ERIResponse;
import com.taxerp.entity.ERIApiResponse;
import com.taxerp.entity.ERIRequestLog;
import com.taxerp.entity.User;
import com.taxerp.repository.ERIApiResponseRepository;
import com.taxerp.repository.ERIRequestLogRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/**
 * Unit tests for AuditLogService functionality.
 * Tests audit log creation, data masking, and correlation ID tracking.
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("AuditLogService Tests")
class AuditLogServiceTest {

    @Mock
    private ERIRequestLogRepository requestLogRepository;

    @Mock
    private ERIApiResponseRepository responseRepository;

    @Mock
    private ObjectMapper objectMapper;

    @InjectMocks
    private AuditLogServiceImpl auditLogService;

    private User testUser;
    private ERIRequest testRequest;
    private ERIResponse testResponse;
    private ERIRequestLog testRequestLog;

    @BeforeEach
    void setUp() {
        // Create test user
        testUser = new User("testuser", "test@example.com");
        testUser.setId(UUID.randomUUID());
        testUser.setFullName("Test User");

        // Create test ERI request
        testRequest = new ERIRequest();
        testRequest.setEriUserId("TEST_USER_123");
        testRequest.setData("{\"taxYear\":\"2024\",\"pan\":\"ABCDE1234F\"}");
        testRequest.setSignature("test_signature_data");
        testRequest.setCorrelationId("test-correlation-123");

        // Create test ERI response
        testResponse = new ERIResponse();
        testResponse.setStatus("SUCCESS");
        testResponse.setMessage("Request processed successfully");
        testResponse.setHttpStatusCode(200);
        testResponse.setCorrelationId("test-correlation-123");
        testResponse.setTransactionId("TXN_123456");

        // Create test request log
        testRequestLog = new ERIRequestLog("test-correlation-123", "/api/test", "POST");
        testRequestLog.setId(UUID.randomUUID());
        testRequestLog.setUser(testUser);
    }

    @Test
    @DisplayName("Should generate unique correlation IDs")
    void shouldGenerateUniqueCorrelationIds() {
        // When
        String correlationId1 = auditLogService.generateCorrelationId();
        String correlationId2 = auditLogService.generateCorrelationId();

        // Then
        assertNotNull(correlationId1);
        assertNotNull(correlationId2);
        assertNotEquals(correlationId1, correlationId2);
        assertTrue(correlationId1.startsWith("req-"));
        assertTrue(correlationId2.startsWith("req-"));
    }

    @Test
    @DisplayName("Should mask sensitive data in JSON payloads")
    void shouldMaskSensitiveDataInJsonPayloads() {
        // Given
        String sensitivePayload = "{\"pan\":\"ABCDE1234F\",\"signature\":\"secret_signature\",\"password\":\"mypassword\"}";

        // When
        String maskedPayload = auditLogService.maskSensitiveData(sensitivePayload);

        // Then
        assertNotNull(maskedPayload);
        assertFalse(maskedPayload.contains("ABCDE1234F"));
        assertFalse(maskedPayload.contains("secret_signature"));
        assertFalse(maskedPayload.contains("mypassword"));
        assertTrue(maskedPayload.contains("***PAN_MASKED***"));
        assertTrue(maskedPayload.contains("***SIGNATURE_MASKED***"));
        assertTrue(maskedPayload.contains("***PASSWORD_MASKED***"));
    }

    @Test
    @DisplayName("Should handle null and empty payloads for masking")
    void shouldHandleNullAndEmptyPayloadsForMasking() {
        // When & Then
        assertNull(auditLogService.maskSensitiveData(null));
        assertEquals("", auditLogService.maskSensitiveData(""));
        assertEquals("   ", auditLogService.maskSensitiveData("   "));
    }

    @Test
    @DisplayName("Should log ERI request successfully")
    void shouldLogERIRequestSuccessfully() throws Exception {
        // Given
        String correlationId = "test-correlation-123";
        String endpoint = "/api/test";
        String httpMethod = "POST";
        String requestJson = "{\"eriUserId\":\"TEST_USER_123\"}";

        when(objectMapper.writeValueAsString(testRequest)).thenReturn(requestJson);
        when(requestLogRepository.save(any(ERIRequestLog.class))).thenReturn(testRequestLog);

        // When
        ERIRequestLog result = auditLogService.logERIRequest(correlationId, testRequest, testUser, endpoint, httpMethod);

        // Then
        assertNotNull(result);
        assertEquals(testRequestLog, result);

        ArgumentCaptor<ERIRequestLog> logCaptor = ArgumentCaptor.forClass(ERIRequestLog.class);
        verify(requestLogRepository).save(logCaptor.capture());

        ERIRequestLog capturedLog = logCaptor.getValue();
        assertEquals(correlationId, capturedLog.getCorrelationId());
        assertEquals(endpoint, capturedLog.getEndpoint());
        assertEquals(httpMethod, capturedLog.getHttpMethod());
        assertEquals(testUser, capturedLog.getUser());
        assertEquals(requestJson, capturedLog.getRequestPayload());
        assertNotNull(capturedLog.getMaskedPayload());
    }

    @Test
    @DisplayName("Should handle serialization errors when logging ERI request")
    void shouldHandleSerializationErrorsWhenLoggingERIRequest() throws Exception {
        // Given
        String correlationId = "test-correlation-123";
        String endpoint = "/api/test";
        String httpMethod = "POST";

        when(objectMapper.writeValueAsString(testRequest)).thenThrow(new RuntimeException("Serialization failed"));
        when(requestLogRepository.save(any(ERIRequestLog.class))).thenReturn(testRequestLog);

        // When
        ERIRequestLog result = auditLogService.logERIRequest(correlationId, testRequest, testUser, endpoint, httpMethod);

        // Then
        assertNotNull(result);
        verify(requestLogRepository).save(any(ERIRequestLog.class));

        ArgumentCaptor<ERIRequestLog> logCaptor = ArgumentCaptor.forClass(ERIRequestLog.class);
        verify(requestLogRepository).save(logCaptor.capture());

        ERIRequestLog capturedLog = logCaptor.getValue();
        assertTrue(capturedLog.getRequestPayload().contains("SERIALIZATION_ERROR"));
        assertEquals("SERIALIZATION_ERROR", capturedLog.getMaskedPayload());
    }

    @Test
    @DisplayName("Should log ERI response successfully")
    void shouldLogERIResponseSuccessfully() throws Exception {
        // Given
        String correlationId = "test-correlation-123";
        long responseTimeMs = 1500L;
        String responseJson = "{\"status\":\"SUCCESS\"}";

        when(objectMapper.writeValueAsString(testResponse)).thenReturn(responseJson);
        
        ERIApiResponse expectedResponse = new ERIApiResponse(correlationId, testRequestLog, 200);
        when(responseRepository.save(any(ERIApiResponse.class))).thenReturn(expectedResponse);

        // When
        ERIApiResponse result = auditLogService.logERIResponse(correlationId, testResponse, testRequestLog, responseTimeMs);

        // Then
        assertNotNull(result);
        assertEquals(expectedResponse, result);

        ArgumentCaptor<ERIApiResponse> responseCaptor = ArgumentCaptor.forClass(ERIApiResponse.class);
        verify(responseRepository).save(responseCaptor.capture());

        ERIApiResponse capturedResponse = responseCaptor.getValue();
        assertEquals(correlationId, capturedResponse.getCorrelationId());
        assertEquals(testRequestLog, capturedResponse.getRequestLog());
        assertEquals(200, capturedResponse.getStatusCode());
        assertEquals((int) responseTimeMs, capturedResponse.getResponseTimeMs());
        assertEquals(responseJson, capturedResponse.getResponsePayload());
        assertNotNull(capturedResponse.getMaskedResponse());
    }

    @Test
    @DisplayName("Should log error message for failed ERI response")
    void shouldLogErrorMessageForFailedERIResponse() throws Exception {
        // Given
        String correlationId = "test-correlation-123";
        long responseTimeMs = 2000L;
        String responseJson = "{\"status\":\"ERROR\"}";

        ERIResponse errorResponse = new ERIResponse();
        errorResponse.setStatus("ERROR");
        errorResponse.setMessage("Processing failed");
        errorResponse.setHttpStatusCode(500);
        errorResponse.setCorrelationId(correlationId);

        when(objectMapper.writeValueAsString(errorResponse)).thenReturn(responseJson);
        
        ERIApiResponse expectedResponse = new ERIApiResponse(correlationId, testRequestLog, 500);
        when(responseRepository.save(any(ERIApiResponse.class))).thenReturn(expectedResponse);

        // When
        ERIApiResponse result = auditLogService.logERIResponse(correlationId, errorResponse, testRequestLog, responseTimeMs);

        // Then
        assertNotNull(result);

        ArgumentCaptor<ERIApiResponse> responseCaptor = ArgumentCaptor.forClass(ERIApiResponse.class);
        verify(responseRepository).save(responseCaptor.capture());

        ERIApiResponse capturedResponse = responseCaptor.getValue();
        assertEquals("Processing failed", capturedResponse.getErrorMessage());
    }

    @Test
    @DisplayName("Should log signature operations with correlation ID tracking")
    void shouldLogSignatureOperationsWithCorrelationIdTracking() {
        // Given
        String correlationId = "test-correlation-123";
        String operation = "SIGN_PAYLOAD";
        String status = "SUCCESS";
        String details = "Payload signed successfully";

        when(requestLogRepository.save(any(ERIRequestLog.class))).thenReturn(testRequestLog);

        // When
        auditLogService.logSignatureOperation(correlationId, operation, status, details, testUser);

        // Then - Should not throw exception and should log appropriately
        // For critical operations like SIGN_PAYLOAD, it should also create database entries
        verify(requestLogRepository).save(any(ERIRequestLog.class));

        ArgumentCaptor<ERIRequestLog> logCaptor = ArgumentCaptor.forClass(ERIRequestLog.class);
        verify(requestLogRepository).save(logCaptor.capture());

        ERIRequestLog capturedLog = logCaptor.getValue();
        assertEquals(correlationId, capturedLog.getCorrelationId());
        assertEquals("DSC_SIGNATURE_SERVICE", capturedLog.getEndpoint());
        assertEquals(operation, capturedLog.getHttpMethod());
        assertEquals(testUser, capturedLog.getUser());
    }

    @Test
    @DisplayName("Should log signature operations without database entry for non-critical operations")
    void shouldLogSignatureOperationsWithoutDatabaseEntryForNonCriticalOperations() {
        // Given
        String correlationId = "test-correlation-123";
        String operation = "GET_CERTIFICATE_INFO";
        String status = "SUCCESS";
        String details = "Certificate info retrieved";

        // When
        auditLogService.logSignatureOperation(correlationId, operation, status, details, testUser);

        // Then - Should not create database entry for non-critical operations
        verify(requestLogRepository, never()).save(any(ERIRequestLog.class));
    }

    @Test
    @DisplayName("Should retrieve complete audit trail by correlation ID")
    void shouldRetrieveCompleteAuditTrailByCorrelationId() {
        // Given
        String correlationId = "test-correlation-123";
        
        ERIApiResponse testApiResponse = new ERIApiResponse(correlationId, testRequestLog, 200);
        
        when(requestLogRepository.findByCorrelationId(correlationId)).thenReturn(Optional.of(testRequestLog));
        when(responseRepository.findByCorrelationId(correlationId)).thenReturn(Optional.of(testApiResponse));

        // When
        AuditLogService.AuditTrail auditTrail = auditLogService.getAuditTrail(correlationId);

        // Then
        assertNotNull(auditTrail);
        assertEquals(correlationId, auditTrail.getCorrelationId());
        assertEquals(testRequestLog, auditTrail.getRequestLog());
        assertEquals(testApiResponse, auditTrail.getResponseLog());
        assertTrue(auditTrail.isComplete());
    }

    @Test
    @DisplayName("Should retrieve incomplete audit trail when response is missing")
    void shouldRetrieveIncompleteAuditTrailWhenResponseIsMissing() {
        // Given
        String correlationId = "test-correlation-123";
        
        when(requestLogRepository.findByCorrelationId(correlationId)).thenReturn(Optional.of(testRequestLog));
        when(responseRepository.findByCorrelationId(correlationId)).thenReturn(Optional.empty());

        // When
        AuditLogService.AuditTrail auditTrail = auditLogService.getAuditTrail(correlationId);

        // Then
        assertNotNull(auditTrail);
        assertEquals(correlationId, auditTrail.getCorrelationId());
        assertEquals(testRequestLog, auditTrail.getRequestLog());
        assertNull(auditTrail.getResponseLog());
        assertFalse(auditTrail.isComplete());
    }

    @Test
    @DisplayName("Should return empty audit trail for non-existent correlation ID")
    void shouldReturnEmptyAuditTrailForNonExistentCorrelationId() {
        // Given
        String correlationId = "non-existent-correlation-123";
        
        when(requestLogRepository.findByCorrelationId(correlationId)).thenReturn(Optional.empty());
        when(responseRepository.findByCorrelationId(correlationId)).thenReturn(Optional.empty());

        // When
        AuditLogService.AuditTrail auditTrail = auditLogService.getAuditTrail(correlationId);

        // Then
        assertNotNull(auditTrail);
        assertEquals(correlationId, auditTrail.getCorrelationId());
        assertNull(auditTrail.getRequestLog());
        assertNull(auditTrail.getResponseLog());
        assertFalse(auditTrail.isComplete());
    }

    @Test
    @DisplayName("Should handle repository exceptions gracefully")
    void shouldHandleRepositoryExceptionsGracefully() {
        // Given
        String correlationId = "test-correlation-123";
        
        when(requestLogRepository.findByCorrelationId(correlationId)).thenThrow(new RuntimeException("Database error"));

        // When
        AuditLogService.AuditTrail auditTrail = auditLogService.getAuditTrail(correlationId);

        // Then - Should not throw exception and return empty audit trail
        assertNotNull(auditTrail);
        assertEquals(correlationId, auditTrail.getCorrelationId());
        assertNull(auditTrail.getRequestLog());
        assertNull(auditTrail.getResponseLog());
        assertFalse(auditTrail.isComplete());
    }
}