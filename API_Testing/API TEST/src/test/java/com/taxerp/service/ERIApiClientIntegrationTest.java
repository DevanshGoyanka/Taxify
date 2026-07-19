package com.taxerp.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxerp.config.ERIConfig;
import com.taxerp.dto.ERIRequest;
import com.taxerp.dto.ERIResponse;
import com.taxerp.exception.ERIApiException;
import com.taxerp.util.ERILoggingUtil;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.RecordedRequest;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import java.io.IOException;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Integration tests for ERIApiClient.
 * Tests ERI API communication, retry logic, error handling, and data masking.
 * Uses MockWebServer to simulate ERI endpoints for comprehensive testing.
 */
@SpringBootTest
@ActiveProfiles("test")
class ERIApiClientIntegrationTest {

    private ERIApiClient eriApiClient;
    private ERIConfig eriConfig;
    private ObjectMapper objectMapper;
    private MockWebServer mockWebServer;

    @BeforeEach
    void setUp() throws IOException {
        // Start mock web server
        mockWebServer = new MockWebServer();
        mockWebServer.start();

        // Create and configure ERI config
        eriConfig = createTestERIConfig();
        objectMapper = new ObjectMapper();

        // Create ERI API client with mock server URL
        eriApiClient = new ERIApiClientImpl(eriConfig, objectMapper);
    }

    @AfterEach
    void tearDown() throws IOException {
        if (mockWebServer != null) {
            mockWebServer.shutdown();
        }
    }

    @Test
    @DisplayName("Should successfully make test call with valid signed payload")
    void testMakeTestCallSuccess() throws Exception {
        // Arrange
        String signedPayload = createTestSignedPayload();
        ERIResponse expectedResponse = createSuccessResponse();
        
        mockWebServer.enqueue(new MockResponse()
                .setResponseCode(200)
                .setHeader("Content-Type", "application/json")
                .setBody(objectMapper.writeValueAsString(expectedResponse)));

        // Act
        ERIResponse actualResponse = eriApiClient.makeTestCall(signedPayload);

        // Assert
        assertNotNull(actualResponse, "Response should not be null");
        assertEquals("SUCCESS", actualResponse.getStatus(), "Status should be SUCCESS");
        assertTrue(actualResponse.isSuccess(), "Response should indicate success");
        assertNotNull(actualResponse.getCorrelationId(), "Correlation ID should be set");
        assertTrue(actualResponse.getResponseTimeMs() > 0, "Response time should be positive");

        // Verify request was made correctly
        RecordedRequest recordedRequest = mockWebServer.takeRequest(1, TimeUnit.SECONDS);
        assertNotNull(recordedRequest, "Request should have been made");
        assertEquals("POST", recordedRequest.getMethod(), "Should use POST method");
        assertEquals("/api/test", recordedRequest.getPath(), "Should call test endpoint");
        
        // Verify mandatory headers
        assertNotNull(recordedRequest.getHeader("User-Agent"), "User-Agent header should be present");
        assertNotNull(recordedRequest.getHeader("Content-Type"), "Content-Type header should be present");
        assertNotNull(recordedRequest.getHeader("X-Correlation-ID"), "Correlation ID header should be present");
    }

    @Test
    @DisplayName("Should successfully submit data with valid request")
    void testSubmitDataSuccess() throws Exception {
        // Arrange
        ERIRequest request = createTestERIRequest();
        ERIResponse expectedResponse = createSuccessResponse();
        
        mockWebServer.enqueue(new MockResponse()
                .setResponseCode(200)
                .setHeader("Content-Type", "application/json")
                .setBody(objectMapper.writeValueAsString(expectedResponse)));

        // Act
        ERIResponse actualResponse = eriApiClient.submitData(request);

        // Assert
        assertNotNull(actualResponse, "Response should not be null");
        assertEquals("SUCCESS", actualResponse.getStatus(), "Status should be SUCCESS");
        assertNotNull(actualResponse.getCorrelationId(), "Correlation ID should be set");
        assertTrue(actualResponse.getResponseTimeMs() > 0, "Response time should be positive");

        // Verify request
        RecordedRequest recordedRequest = mockWebServer.takeRequest(1, TimeUnit.SECONDS);
        assertNotNull(recordedRequest, "Request should have been made");
        assertEquals("POST", recordedRequest.getMethod(), "Should use POST method");
        assertEquals("/api/submit", recordedRequest.getPath(), "Should call submit endpoint");
    }

    @Test
    @DisplayName("Should handle HTTP 4xx client errors without retry")
    void testClientErrorNoRetry() throws Exception {
        // Arrange
        ERIRequest request = createTestERIRequest();
        
        mockWebServer.enqueue(new MockResponse()
                .setResponseCode(400)
                .setHeader("Content-Type", "application/json")
                .setBody("{\"error\":\"Bad Request\",\"message\":\"Invalid payload\"}"));

        // Act & Assert
        ERIApiException exception = assertThrows(ERIApiException.class, () -> {
            eriApiClient.submitData(request);
        });

        assertEquals(400, exception.getHttpStatus(), "Should preserve HTTP status code");
        assertTrue(exception.getMessage().contains("ERI API returned error"), "Should contain error message");

        // Verify only one request was made (no retry for 4xx errors)
        assertEquals(1, mockWebServer.getRequestCount(), "Should not retry 4xx errors");
    }

    @Test
    @DisplayName("Should retry on HTTP 5xx server errors with exponential backoff")
    void testServerErrorRetry() throws Exception {
        // Arrange
        ERIRequest request = createTestERIRequest();
        ERIResponse successResponse = createSuccessResponse();
        
        // First two requests fail with 500, third succeeds
        mockWebServer.enqueue(new MockResponse().setResponseCode(500).setBody("Internal Server Error"));
        mockWebServer.enqueue(new MockResponse().setResponseCode(500).setBody("Internal Server Error"));
        mockWebServer.enqueue(new MockResponse()
                .setResponseCode(200)
                .setHeader("Content-Type", "application/json")
                .setBody(objectMapper.writeValueAsString(successResponse)));

        // Act
        ERIResponse actualResponse = eriApiClient.submitData(request);

        // Assert
        assertNotNull(actualResponse, "Response should not be null");
        assertEquals("SUCCESS", actualResponse.getStatus(), "Should eventually succeed");

        // Verify retry attempts were made
        assertEquals(3, mockWebServer.getRequestCount(), "Should have made 3 requests (2 retries)");
    }

    @Test
    @DisplayName("Should exhaust retries and throw exception after max attempts")
    void testRetryExhaustion() throws Exception {
        // Arrange
        ERIRequest request = createTestERIRequest();
        
        // All requests fail with 500
        for (int i = 0; i < 5; i++) {
            mockWebServer.enqueue(new MockResponse().setResponseCode(500).setBody("Internal Server Error"));
        }

        // Act & Assert
        ERIApiException exception = assertThrows(ERIApiException.class, () -> {
            eriApiClient.submitData(request);
        });

        assertTrue(exception.getMessage().contains("failed after"), "Should indicate retry exhaustion");
        assertEquals("ERI_RETRY_EXHAUSTED", exception.getErrorCode(), "Should have retry exhausted error code");

        // Verify max attempts were made (3 attempts = 1 initial + 2 retries)
        assertEquals(3, mockWebServer.getRequestCount(), "Should have made max retry attempts");
    }

    @Test
    @DisplayName("Should retry on timeout errors")
    void testTimeoutRetry() throws Exception {
        // Arrange
        ERIRequest request = createTestERIRequest();
        ERIResponse successResponse = createSuccessResponse();
        
        // First request times out, second succeeds
        mockWebServer.enqueue(new MockResponse().setSocketPolicy(okhttp3.mockwebserver.SocketPolicy.NO_RESPONSE));
        mockWebServer.enqueue(new MockResponse()
                .setResponseCode(200)
                .setHeader("Content-Type", "application/json")
                .setBody(objectMapper.writeValueAsString(successResponse)));

        // Act
        ERIResponse actualResponse = eriApiClient.submitData(request);

        // Assert
        assertNotNull(actualResponse, "Response should not be null");
        assertEquals("SUCCESS", actualResponse.getStatus(), "Should eventually succeed after timeout retry");
    }

    @Test
    @DisplayName("Should validate connectivity successfully")
    void testValidateConnectivitySuccess() throws Exception {
        // Arrange
        mockWebServer.enqueue(new MockResponse()
                .setResponseCode(200)
                .setBody("OK"));

        // Act
        boolean isConnected = eriApiClient.validateConnectivity();

        // Assert
        assertTrue(isConnected, "Should validate connectivity successfully");

        // Verify request
        RecordedRequest recordedRequest = mockWebServer.takeRequest(1, TimeUnit.SECONDS);
        assertNotNull(recordedRequest, "Request should have been made");
        assertEquals("GET", recordedRequest.getMethod(), "Should use GET method");
        assertEquals("/api/health", recordedRequest.getPath(), "Should call health endpoint");
    }

    @Test
    @DisplayName("Should fail connectivity validation on server error")
    void testValidateConnectivityFailure() throws Exception {
        // Arrange
        mockWebServer.enqueue(new MockResponse().setResponseCode(500));

        // Act & Assert
        ERIApiException exception = assertThrows(ERIApiException.class, () -> {
            eriApiClient.validateConnectivity();
        });

        assertEquals("CONNECTIVITY_ERROR", exception.getErrorCode(), "Should have connectivity error code");
        assertTrue(exception.getMessage().contains("connectivity validation failed"), "Should contain validation failure message");
    }

    @Test
    @DisplayName("Should return configuration status")
    void testGetConfigurationStatus() {
        // Act
        String status = eriApiClient.getConfigurationStatus();

        // Assert
        assertNotNull(status, "Configuration status should not be null");
        assertTrue(status.contains("ERI API Configuration"), "Should contain configuration info");
        assertTrue(status.contains(eriConfig.getApi().getBaseUrl()), "Should contain base URL");
        assertTrue(status.contains(String.valueOf(eriConfig.getApi().getConnectionTimeout())), "Should contain timeout");
    }

    @Test
    @DisplayName("Should handle invalid JSON in signed payload")
    void testMakeTestCallInvalidJson() {
        // Arrange
        String invalidSignedPayload = "{invalid json}";

        // Act & Assert
        ERIApiException exception = assertThrows(ERIApiException.class, () -> {
            eriApiClient.makeTestCall(invalidSignedPayload);
        });

        assertEquals("INVALID_PAYLOAD", exception.getErrorCode(), "Should have invalid payload error code");
        assertEquals(400, exception.getHttpStatus(), "Should have 400 status code");
    }

    @Test
    @DisplayName("Should mask sensitive data in logs")
    void testDataMasking() {
        // Test data masking utility
        String sensitiveData = "{\"signature\":\"secret123\",\"password\":\"pass123\",\"data\":\"normal\"}";
        String maskedData = ERILoggingUtil.maskSensitiveData(sensitiveData);

        assertNotNull(maskedData, "Masked data should not be null");
        assertFalse(maskedData.contains("secret123"), "Should mask signature");
        assertFalse(maskedData.contains("pass123"), "Should mask password");
        assertTrue(maskedData.contains("normal"), "Should preserve non-sensitive data");
        assertTrue(maskedData.contains("[MASKED]"), "Should contain mask placeholder");
    }

    @Test
    @DisplayName("Should set correlation ID automatically if not provided")
    void testAutomaticCorrelationId() throws Exception {
        // Arrange
        ERIRequest request = createTestERIRequest();
        request.setCorrelationId(null); // Remove correlation ID
        
        ERIResponse expectedResponse = createSuccessResponse();
        mockWebServer.enqueue(new MockResponse()
                .setResponseCode(200)
                .setHeader("Content-Type", "application/json")
                .setBody(objectMapper.writeValueAsString(expectedResponse)));

        // Act
        ERIResponse actualResponse = eriApiClient.submitData(request);

        // Assert
        assertNotNull(actualResponse.getCorrelationId(), "Correlation ID should be automatically set");
        assertTrue(actualResponse.getCorrelationId().startsWith("eri-"), "Correlation ID should have ERI prefix");
    }

    @Test
    @DisplayName("Should handle network connection errors")
    void testNetworkConnectionError() throws Exception {
        // Arrange - shutdown server to simulate network error
        mockWebServer.shutdown();
        ERIRequest request = createTestERIRequest();

        // Act & Assert
        ERIApiException exception = assertThrows(ERIApiException.class, () -> {
            eriApiClient.submitData(request);
        });

        assertTrue(exception.getMessage().contains("failed"), "Should indicate operation failure");
    }

    /**
     * Creates test ERI configuration
     */
    private ERIConfig createTestERIConfig() {
        ERIConfig config = new ERIConfig();
        
        // API configuration
        config.getApi().setBaseUrl(mockWebServer.url("/").toString().replaceAll("/$", ""));
        config.getApi().setConnectionTimeout(5000);
        config.getApi().setReadTimeout(10000);
        config.getApi().setWriteTimeout(10000);
        
        // Headers configuration
        config.getHeaders().setUserAgent("TaxERP-Test/1.0");
        config.getHeaders().setContentType("application/json");
        config.getHeaders().setAccept("application/json");
        
        // Retry configuration
        config.getRetry().setMaxAttempts(3);
        config.getRetry().setInitialDelayMs(100); // Shorter delays for testing
        config.getRetry().setMaxDelayMs(1000);
        config.getRetry().setMultiplier(2.0);
        config.getRetry().setEnableJitter(false); // Disable jitter for predictable testing
        
        return config;
    }

    /**
     * Creates test signed payload
     */
    private String createTestSignedPayload() {
        return "{\"eriUserId\":\"TEST123\",\"data\":{\"test\":\"data\"},\"signature\":\"test-signature-123\"}";
    }

    /**
     * Creates test ERI request
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
     * Creates test success response
     */
    private ERIResponse createSuccessResponse() {
        ERIResponse response = new ERIResponse();
        response.setStatus("SUCCESS");
        response.setMessage("Operation completed successfully");
        response.setData("{\"result\":\"success\"}");
        response.setTransactionId("TXN123456");
        response.setTimestamp("2024-01-15T10:30:01");
        return response;
    }
}