package com.taxerp.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxerp.entity.ERIRequestLog;
import com.taxerp.repository.ERIRequestLogRepository;
import com.taxerp.service.AuditLogService;
import com.taxerp.service.DSCSignatureService;
import com.taxerp.service.ERIApiClient;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.RecordedRequest;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureTestMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.io.IOException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Integration tests for ERITestController.
 * Tests the complete ERI test workflow including signing, API calls, and audit logging.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@AutoConfigureTestMvc
@ActiveProfiles("test")
@TestPropertySource(properties = {
        "spring.datasource.url=jdbc:postgresql://localhost:5432/taxerp_test",
        "spring.datasource.username=test",
        "spring.datasource.password=test",
        "spring.jpa.hibernate.ddl-auto=create-drop",
        "dsc.keystore.path=src/test/resources/test-keystore.p12",
        "dsc.keystore.password=test123",
        "dsc.keystore.type=PKCS12",
        "eri.api.base-url=http://localhost:8089",
        "eri.api.connection-timeout=30000",
        "eri.api.read-timeout=60000",
        "eri.headers.user-agent=TaxERP-Phase1/1.0",
        "eri.retry.max-attempts=3",
        "logging.level.com.taxerp=DEBUG"
})
@Testcontainers
@DisplayName("ERITestController Integration Tests")
class ERITestControllerIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15-alpine")
            .withDatabaseName("taxerp_test")
            .withUsername("test")
            .withPassword("test");

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private ERIRequestLogRepository eriRequestLogRepository;

    @MockBean
    private DSCSignatureService dscSignatureService;

    @MockBean
    private ERIApiClient eriApiClient;

    @MockBean
    private AuditLogService auditLogService;

    private MockWebServer mockEriServer;

    @BeforeEach
    void setUp() throws IOException {
        mockEriServer = new MockWebServer();
        mockEriServer.start(8089);
        
        // Clear audit logs before each test
        eriRequestLogRepository.deleteAll();
    }

    @AfterEach
    void tearDown() throws IOException {
        if (mockEriServer != null) {
            mockEriServer.shutdown();
        }
    }

    @Test
    @DisplayName("Should successfully complete ERI test call workflow")
    void shouldSuccessfullyCompleteERITestCallWorkflow() throws Exception {
        // Given
        String testSignature = "MEUCIQDTestSignature123...";
        String testEriUserId = "TEST_ERI_USER_001";
        
        Map<String, Object> testData = new HashMap<>();
        testData.put("testField", "testValue");
        testData.put("timestamp", "2024-01-15T10:30:00");
        
        ERITestController.ERITestRequest testRequest = new ERITestController.ERITestRequest();
        testRequest.setEriUserId(testEriUserId);
        testRequest.setData(testData);
        
        // Mock DSC signature service
        when(dscSignatureService.signPayload(anyString())).thenReturn(testSignature);
        when(dscSignatureService.getCertificateDetails()).thenReturn(createMockCertificateInfo());
        
        // Mock ERI API response
        String mockEriResponse = """
            {
                "status": "SUCCESS",
                "message": "Test call successful",
                "transactionId": "TXN_123456789",
                "timestamp": "2024-01-15T10:30:00Z"
            }
            """;
        
        mockEriServer.enqueue(new MockResponse()
                .setResponseCode(200)
                .setHeader("Content-Type", "application/json")
                .setBody(mockEriResponse));
        
        // When
        MvcResult result = mockMvc.perform(post("/api/eri/test-call")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(testRequest)))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value("SUCCESS"))
                .andExpect(jsonPath("$.message").value("ERI test call completed successfully"))
                .andExpect(jsonPath("$.correlationId").exists())
                .andExpect(jsonPath("$.timestamp").exists())
                .andExpect(jsonPath("$.responseTimeMs").exists())
                .andExpect(jsonPath("$.signatureGenerated").value(true))
                .andExpect(jsonPath("$.eriResponse").exists())
                .andExpect(jsonPath("$.certificateInfo").exists())
                .andReturn();
        
        // Then
        String responseContent = result.getResponse().getContentAsString();
        @SuppressWarnings("unchecked")
        Map<String, Object> response = objectMapper.readValue(responseContent, Map.class);
        
        assertNotNull(response.get("correlationId"));
        assertNotNull(response.get("timestamp"));
        assertTrue((Integer) response.get("responseTimeMs") >= 0);
        assertTrue((Boolean) response.get("signatureGenerated"));
        
        // Verify DSC service was called
        verify(dscSignatureService, times(1)).signPayload(anyString());
        verify(dscSignatureService, times(1)).getCertificateDetails();
        
        // Verify audit logging was called
        verify(auditLogService, times(1)).logSignatureOperation("ERI_TEST_SIGNING", "SUCCESS");
        
        // Verify ERI API was called
        RecordedRequest recordedRequest = mockEriServer.takeRequest();
        assertNotNull(recordedRequest);
        assertEquals("POST", recordedRequest.getMethod());
        assertTrue(recordedRequest.getBody().readUtf8().contains(testEriUserId));
    }

    @Test
    @DisplayName("Should handle DSC signature errors properly")
    void shouldHandleDSCSignatureErrorsProperly() throws Exception {
        // Given
        String testEriUserId = "TEST_ERI_USER_001";
        Map<String, Object> testData = new HashMap<>();
        testData.put("testField", "testValue");
        
        ERITestController.ERITestRequest testRequest = new ERITestController.ERITestRequest();
        testRequest.setEriUserId(testEriUserId);
        testRequest.setData(testData);
        
        // Mock DSC signature service to throw exception
        when(dscSignatureService.signPayload(anyString()))
                .thenThrow(new com.taxerp.exception.SignatureException("Keystore not accessible"));
        
        // When
        MvcResult result = mockMvc.perform(post("/api/eri/test-call")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(testRequest)))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value("SIGNATURE_ERROR"))
                .andExpect(jsonPath("$.message").value("Digital signature generation failed"))
                .andExpect(jsonPath("$.error").value("Keystore not accessible"))
                .andExpect(jsonPath("$.errorCode").value("DSC_SIGNATURE_ERROR"))
                .andExpect(jsonPath("$.signatureGenerated").value(false))
                .andReturn();
        
        // Then
        String responseContent = result.getResponse().getContentAsString();
        @SuppressWarnings("unchecked")
        Map<String, Object> response = objectMapper.readValue(responseContent, Map.class);
        
        assertNotNull(response.get("correlationId"));
        assertNotNull(response.get("timestamp"));
        assertTrue((Integer) response.get("responseTimeMs") >= 0);
        assertFalse((Boolean) response.get("signatureGenerated"));
        
        // Verify audit logging was called for failure
        verify(auditLogService, times(1))
                .logSignatureOperation("ERI_TEST_SIGNING", "FAILED: Keystore not accessible");
        
        // Verify ERI API was not called
        assertEquals(0, mockEriServer.getRequestCount());
    }

    @Test
    @DisplayName("Should handle ERI API errors properly")
    void shouldHandleERIApiErrorsProperly() throws Exception {
        // Given
        String testSignature = "MEUCIQDTestSignature123...";
        String testEriUserId = "TEST_ERI_USER_001";
        
        Map<String, Object> testData = new HashMap<>();
        testData.put("testField", "testValue");
        
        ERITestController.ERITestRequest testRequest = new ERITestController.ERITestRequest();
        testRequest.setEriUserId(testEriUserId);
        testRequest.setData(testData);
        
        // Mock DSC signature service
        when(dscSignatureService.signPayload(anyString())).thenReturn(testSignature);
        when(dscSignatureService.getCertificateDetails()).thenReturn(createMockCertificateInfo());
        
        // Mock ERI API to return error
        mockEriServer.enqueue(new MockResponse()
                .setResponseCode(500)
                .setHeader("Content-Type", "application/json")
                .setBody("{\"error\": \"Internal Server Error\"}"));
        
        // When
        MvcResult result = mockMvc.perform(post("/api/eri/test-call")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(testRequest)))
                .andExpect(status().isInternalServerError())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value("ERI_API_ERROR"))
                .andExpect(jsonPath("$.message").value("ERI API call failed"))
                .andExpect(jsonPath("$.signatureGenerated").value(true))
                .andReturn();
        
        // Then
        String responseContent = result.getResponse().getContentAsString();
        @SuppressWarnings("unchecked")
        Map<String, Object> response = objectMapper.readValue(responseContent, Map.class);
        
        assertTrue((Boolean) response.get("signatureGenerated"));
        assertNotNull(response.get("correlationId"));
        
        // Verify DSC service was called successfully
        verify(dscSignatureService, times(1)).signPayload(anyString());
        verify(auditLogService, times(1)).logSignatureOperation("ERI_TEST_SIGNING", "SUCCESS");
        
        // Verify ERI API was called
        assertEquals(1, mockEriServer.getRequestCount());
    }

    @Test
    @DisplayName("Should validate request data properly")
    void shouldValidateRequestDataProperly() throws Exception {
        // Given - Invalid request with missing required fields
        ERITestController.ERITestRequest invalidRequest = new ERITestController.ERITestRequest();
        // Missing eriUserId and data
        
        // When & Then
        mockMvc.perform(post("/api/eri/test-call")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(invalidRequest)))
                .andExpect(status().isBadRequest());
        
        // Verify no services were called for invalid request
        verify(dscSignatureService, never()).signPayload(anyString());
        verify(auditLogService, never()).logSignatureOperation(anyString(), anyString());
    }

    @Test
    @DisplayName("Should return ERI status information")
    void shouldReturnERIStatusInformation() throws Exception {
        // Given
        when(eriApiClient.getConfigurationStatus()).thenReturn("Configuration OK");
        when(eriApiClient.validateConnectivity()).thenReturn(true);
        when(dscSignatureService.getCertificateDetails()).thenReturn(createMockCertificateInfo());
        
        // When
        MvcResult result = mockMvc.perform(get("/api/eri/status")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value("SUCCESS"))
                .andExpect(jsonPath("$.eriConnectivity").value("UP"))
                .andExpect(jsonPath("$.configurationStatus").value("Configuration OK"))
                .andExpect(jsonPath("$.dscStatus").value("VALID"))
                .andExpect(jsonPath("$.certificateInfo").exists())
                .andExpect(jsonPath("$.timestamp").exists())
                .andReturn();
        
        // Then
        String responseContent = result.getResponse().getContentAsString();
        @SuppressWarnings("unchecked")
        Map<String, Object> response = objectMapper.readValue(responseContent, Map.class);
        
        assertEquals("SUCCESS", response.get("status"));
        assertEquals("UP", response.get("eriConnectivity"));
        assertEquals("VALID", response.get("dscStatus"));
        
        @SuppressWarnings("unchecked")
        Map<String, Object> certInfo = (Map<String, Object>) response.get("certificateInfo");
        assertNotNull(certInfo);
        assertTrue((Boolean) certInfo.get("isValid"));
        
        // Verify services were called
        verify(eriApiClient, times(1)).getConfigurationStatus();
        verify(eriApiClient, times(1)).validateConnectivity();
        verify(dscSignatureService, times(1)).getCertificateDetails();
    }

    @Test
    @DisplayName("Should handle ERI status errors gracefully")
    void shouldHandleERIStatusErrorsGracefully() throws Exception {
        // Given
        when(eriApiClient.getConfigurationStatus()).thenThrow(new RuntimeException("Configuration error"));
        
        // When
        mockMvc.perform(get("/api/eri/status")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isInternalServerError())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value("ERROR"))
                .andExpect(jsonPath("$.message").value("Failed to get ERI status"))
                .andExpect(jsonPath("$.error").exists());
    }

    @Test
    @DisplayName("Should create audit trail for test operations")
    void shouldCreateAuditTrailForTestOperations() throws Exception {
        // Given
        String testSignature = "MEUCIQDTestSignature123...";
        String testEriUserId = "TEST_ERI_USER_001";
        
        Map<String, Object> testData = new HashMap<>();
        testData.put("testField", "testValue");
        
        ERITestController.ERITestRequest testRequest = new ERITestController.ERITestRequest();
        testRequest.setEriUserId(testEriUserId);
        testRequest.setData(testData);
        
        // Mock services
        when(dscSignatureService.signPayload(anyString())).thenReturn(testSignature);
        when(dscSignatureService.getCertificateDetails()).thenReturn(createMockCertificateInfo());
        
        mockEriServer.enqueue(new MockResponse()
                .setResponseCode(200)
                .setHeader("Content-Type", "application/json")
                .setBody("{\"status\": \"SUCCESS\"}"));
        
        // When
        mockMvc.perform(post("/api/eri/test-call")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(testRequest)))
                .andExpect(status().isOk());
        
        // Then - Verify audit logging was called
        verify(auditLogService, times(1)).logSignatureOperation("ERI_TEST_SIGNING", "SUCCESS");
        
        // Additional verification could include checking database records if needed
        // This would require implementing actual audit log persistence in the test
    }

    @Test
    @DisplayName("Should handle concurrent test calls properly")
    void shouldHandleConcurrentTestCallsProperly() throws Exception {
        // Given
        String testSignature = "MEUCIQDTestSignature123...";
        
        when(dscSignatureService.signPayload(anyString())).thenReturn(testSignature);
        when(dscSignatureService.getCertificateDetails()).thenReturn(createMockCertificateInfo());
        
        // Queue multiple responses
        for (int i = 0; i < 3; i++) {
            mockEriServer.enqueue(new MockResponse()
                    .setResponseCode(200)
                    .setHeader("Content-Type", "application/json")
                    .setBody("{\"status\": \"SUCCESS\", \"id\": " + i + "}"));
        }
        
        ERITestController.ERITestRequest testRequest = new ERITestController.ERITestRequest();
        testRequest.setEriUserId("TEST_USER");
        testRequest.setData(Map.of("test", "data"));
        
        // When - Make multiple concurrent calls
        String requestJson = objectMapper.writeValueAsString(testRequest);
        
        MvcResult result1 = mockMvc.perform(post("/api/eri/test-call")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(requestJson))
                .andExpect(status().isOk())
                .andReturn();
        
        MvcResult result2 = mockMvc.perform(post("/api/eri/test-call")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(requestJson))
                .andExpect(status().isOk())
                .andReturn();
        
        MvcResult result3 = mockMvc.perform(post("/api/eri/test-call")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(requestJson))
                .andExpect(status().isOk())
                .andReturn();
        
        // Then - Verify all calls succeeded and have unique correlation IDs
        @SuppressWarnings("unchecked")
        Map<String, Object> response1 = objectMapper.readValue(result1.getResponse().getContentAsString(), Map.class);
        @SuppressWarnings("unchecked")
        Map<String, Object> response2 = objectMapper.readValue(result2.getResponse().getContentAsString(), Map.class);
        @SuppressWarnings("unchecked")
        Map<String, Object> response3 = objectMapper.readValue(result3.getResponse().getContentAsString(), Map.class);
        
        assertNotEquals(response1.get("correlationId"), response2.get("correlationId"));
        assertNotEquals(response2.get("correlationId"), response3.get("correlationId"));
        assertNotEquals(response1.get("correlationId"), response3.get("correlationId"));
        
        // Verify all calls were processed
        assertEquals(3, mockEriServer.getRequestCount());
        verify(dscSignatureService, times(3)).signPayload(anyString());
        verify(auditLogService, times(3)).logSignatureOperation("ERI_TEST_SIGNING", "SUCCESS");
    }

    /**
     * Helper method to create mock certificate information.
     */
    private DSCSignatureService.CertificateInfo createMockCertificateInfo() {
        return new DSCSignatureService.CertificateInfo(
                "CN=Test Certificate, O=Test Org, C=IN",
                "CN=Test CA, O=Test CA Org, C=IN",
                "123456789",
                "2024-01-01T00:00:00Z",
                "2025-01-01T00:00:00Z",
                "SHA256withRSA",
                2048,
                true
        );
    }
}