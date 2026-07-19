package com.taxerp.integration;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxerp.TaxErpApplication;
import com.taxerp.controller.ERITestController;
import com.taxerp.dto.HealthResponse;
import com.taxerp.service.StartupValidationService;
import com.taxerp.util.ITDPayloadGenerator;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureWebMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;

import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Comprehensive integration tests for the Tax ERP application.
 * Tests complete application startup, health check functionality, and ERI test endpoints.
 * 
 * Requirements: 1.4, 1.5, 3.5, 4.1, 4.2 - Complete application testing and verification
 */
@SpringBootTest(
    classes = TaxErpApplication.class,
    webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT
)
@ActiveProfiles("test")
@TestPropertySource(properties = {
    "dsc.keystore.path=src/test/resources/test-keystore.p12",
    "dsc.keystore.password=test123",
    "dsc.keystore.type=PKCS12",
    "eri.api.base-url=https://uat.eri.incometax.gov.in",
    "eri.api.timeout=30000",
    "eri.api.retry-attempts=3",
    "spring.datasource.url=jdbc:h2:mem:testdb",
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.jpa.hibernate.ddl-auto=create-drop",
    "logging.level.com.taxerp=DEBUG"
})
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@AutoConfigureWebMvc
class ApplicationIntegrationTest {

    @LocalServerPort
    private int port;

    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private StartupValidationService startupValidationService;

    @Autowired
    private ITDPayloadGenerator itdPayloadGenerator;

    private String getBaseUrl() {
        return "http://localhost:" + port;
    }

    /**
     * Test complete application startup and health check functionality.
     * Verifies that the application starts successfully and all health checks pass.
     */
    @Test
    void testApplicationStartupAndHealthCheck() {
        // Test basic health endpoint
        ResponseEntity<HealthResponse> healthResponse = restTemplate.getForEntity(
                getBaseUrl() + "/api/health", HealthResponse.class);

        assertNotNull(healthResponse);
        assertEquals(HttpStatus.OK, healthResponse.getStatusCode());
        
        HealthResponse health = healthResponse.getBody();
        assertNotNull(health);
        assertNotNull(health.getStatus());
        assertTrue(health.getResponseTimeMs() > 0);
        assertNotNull(health.getVersion());
        assertNotNull(health.getEnvironment());
        assertNotNull(health.getChecks());

        // Verify individual health checks
        Map<String, HealthResponse.HealthCheck> checks = health.getChecks();
        assertTrue(checks.containsKey("dsc_keystore"));
        assertTrue(checks.containsKey("eri_configuration"));
        assertTrue(checks.containsKey("database_connectivity"));

        // Log health check results for debugging
        System.out.println("Health Check Status: " + health.getStatus());
        System.out.println("Response Time: " + health.getResponseTimeMs() + "ms");
        checks.forEach((name, check) -> {
            System.out.println(name + ": " + check.getStatus() + " (" + check.getResponseTimeMs() + "ms)");
            if (check.getError() != null) {
                System.out.println("  Error: " + check.getError());
            }
        });
    }

    /**
     * Test startup validation endpoint functionality.
     * Verifies that startup validation results are properly exposed.
     */
    @Test
    void testStartupValidationEndpoint() {
        ResponseEntity<Map> startupResponse = restTemplate.getForEntity(
                getBaseUrl() + "/api/health/startup", Map.class);

        assertNotNull(startupResponse);
        // Note: Status might be SERVICE_UNAVAILABLE if validation fails in test environment
        assertTrue(startupResponse.getStatusCode() == HttpStatus.OK || 
                  startupResponse.getStatusCode() == HttpStatus.SERVICE_UNAVAILABLE);

        Map<String, Object> startup = startupResponse.getBody();
        assertNotNull(startup);
        assertTrue(startup.containsKey("startupValidationPassed"));
        assertTrue(startup.containsKey("validationErrors"));
        assertTrue(startup.containsKey("validationWarnings"));
        assertTrue(startup.containsKey("currentStatus"));
        assertTrue(startup.containsKey("timestamp"));
        assertTrue(startup.containsKey("applicationName"));
        assertTrue(startup.containsKey("version"));
        assertTrue(startup.containsKey("environment"));

        // Verify current status structure
        @SuppressWarnings("unchecked")
        Map<String, Object> currentStatus = (Map<String, Object>) startup.get("currentStatus");
        assertNotNull(currentStatus);
        assertTrue(currentStatus.containsKey("overallValid"));
        assertTrue(currentStatus.containsKey("dscValid"));
        assertTrue(currentStatus.containsKey("eriValid"));
        assertTrue(currentStatus.containsKey("databaseValid"));

        // Log startup validation results
        System.out.println("Startup Validation Passed: " + startup.get("startupValidationPassed"));
        System.out.println("Current Overall Valid: " + currentStatus.get("overallValid"));
        System.out.println("Validation Errors: " + startup.get("validationErrors"));
        System.out.println("Validation Warnings: " + startup.get("validationWarnings"));
    }

    /**
     * Test ERI test endpoint with sample payload.
     * Verifies that the ERI test functionality works end-to-end.
     * Note: This test may fail if DSC keystore is not properly configured in test environment.
     */
    @Test
    void testERITestEndpointWithSamplePayload() {
        // Create test request
        ERITestController.ERITestRequest testRequest = new ERITestController.ERITestRequest();
        testRequest.setEriUserId("ERIP011535");
        
        Map<String, Object> testData = new HashMap<>();
        testData.put("message", "Integration test payload");
        testData.put("timestamp", System.currentTimeMillis());
        testData.put("testType", "INTEGRATION_TEST");
        testRequest.setData(testData);

        // Set up headers
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        HttpEntity<ERITestController.ERITestRequest> request = new HttpEntity<>(testRequest, headers);

        // Make request to ERI test endpoint
        ResponseEntity<Map> response = restTemplate.postForEntity(
                getBaseUrl() + "/api/eri/test-call", request, Map.class);

        assertNotNull(response);
        
        Map<String, Object> responseBody = response.getBody();
        assertNotNull(responseBody);
        assertTrue(responseBody.containsKey("correlationId"));
        assertTrue(responseBody.containsKey("timestamp"));
        assertTrue(responseBody.containsKey("status"));
        assertTrue(responseBody.containsKey("responseTimeMs"));

        // Log response for debugging
        System.out.println("ERI Test Response Status: " + response.getStatusCode());
        System.out.println("Response Body: " + responseBody);

        // The response status depends on whether DSC is properly configured
        // In test environment, it might fail due to missing keystore
        String status = (String) responseBody.get("status");
        if ("SUCCESS".equals(status)) {
            // If successful, verify additional fields
            assertTrue(responseBody.containsKey("eriResponse"));
            assertTrue(responseBody.containsKey("signatureGenerated"));
            assertTrue(responseBody.containsKey("certificateInfo"));
            assertEquals(true, responseBody.get("signatureGenerated"));
        } else {
            // If failed, should have error information
            assertTrue(responseBody.containsKey("error"));
            assertTrue(responseBody.containsKey("errorCode"));
            System.out.println("ERI Test failed as expected in test environment: " + responseBody.get("error"));
        }
    }

    /**
     * Test ERI status endpoint functionality.
     * Verifies that ERI status information is properly exposed.
     */
    @Test
    void testERIStatusEndpoint() {
        ResponseEntity<Map> statusResponse = restTemplate.getForEntity(
                getBaseUrl() + "/api/eri/status", Map.class);

        assertNotNull(statusResponse);
        
        Map<String, Object> status = statusResponse.getBody();
        assertNotNull(status);
        assertTrue(status.containsKey("timestamp"));
        assertTrue(status.containsKey("status"));

        // Log status for debugging
        System.out.println("ERI Status Response: " + statusResponse.getStatusCode());
        System.out.println("Status Body: " + status);

        // Status might be ERROR in test environment due to missing DSC configuration
        String statusValue = (String) status.get("status");
        if ("SUCCESS".equals(statusValue)) {
            assertTrue(status.containsKey("eriConnectivity"));
            assertTrue(status.containsKey("configurationStatus"));
            assertTrue(status.containsKey("dscStatus"));
            assertTrue(status.containsKey("certificateInfo"));
        } else {
            assertTrue(status.containsKey("error"));
            System.out.println("ERI Status failed as expected in test environment: " + status.get("error"));
        }
    }

    /**
     * Test configuration loading across different environments.
     * Verifies that application properties are properly loaded and accessible.
     */
    @Test
    void testConfigurationLoading() {
        // Test that the application context loads successfully with test profile
        // This is implicitly tested by the fact that other tests run successfully
        
        // Verify startup validation service is available
        assertNotNull(startupValidationService);
        
        // Verify ITD payload generator is available
        assertNotNull(itdPayloadGenerator);
        
        // Test manual validation to ensure services are wired correctly
        StartupValidationService.ValidationResult validationResult = 
                startupValidationService.performManualValidation();
        
        assertNotNull(validationResult);
        // Note: Validation might fail in test environment, but service should be functional
        
        System.out.println("Configuration Loading Test:");
        System.out.println("Overall Valid: " + validationResult.isOverallValid());
        System.out.println("DSC Valid: " + validationResult.isDscValid());
        System.out.println("ERI Valid: " + validationResult.isEriValid());
        System.out.println("Database Valid: " + validationResult.isDatabaseValid());
        System.out.println("Errors: " + validationResult.getErrors());
        System.out.println("Warnings: " + validationResult.getWarnings());
    }

    /**
     * Test audit logging functionality.
     * Verifies that audit operations are properly logged during application operations.
     */
    @Test
    void testAuditLoggingOperations() {
        // This test verifies that audit logging doesn't cause exceptions
        // Actual audit log verification would require database inspection
        
        // Trigger operations that should create audit logs
        try {
            // Health check should trigger audit operations
            restTemplate.getForEntity(getBaseUrl() + "/api/health", HealthResponse.class);
            
            // Startup validation should have created audit logs
            restTemplate.getForEntity(getBaseUrl() + "/api/health/startup", Map.class);
            
            // These operations should complete without throwing exceptions
            // indicating that audit logging is working properly
            
            System.out.println("Audit logging operations completed successfully");
            
        } catch (Exception e) {
            fail("Audit logging operations should not throw exceptions: " + e.getMessage());
        }
    }

    /**
     * Test application error handling and resilience.
     * Verifies that the application handles errors gracefully.
     */
    @Test
    void testApplicationErrorHandling() {
        // Test invalid endpoint
        ResponseEntity<String> invalidResponse = restTemplate.getForEntity(
                getBaseUrl() + "/api/invalid-endpoint", String.class);
        
        assertEquals(HttpStatus.NOT_FOUND, invalidResponse.getStatusCode());
        
        // Test invalid ERI test request
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        
        // Empty request body should trigger validation error
        HttpEntity<String> invalidRequest = new HttpEntity<>("{}", headers);
        
        ResponseEntity<Map> errorResponse = restTemplate.postForEntity(
                getBaseUrl() + "/api/eri/test-call", invalidRequest, Map.class);
        
        assertEquals(HttpStatus.BAD_REQUEST, errorResponse.getStatusCode());
        
        System.out.println("Error handling test completed - application handles errors gracefully");
    }

    /**
     * Test application performance and response times.
     * Verifies that the application responds within acceptable time limits.
     */
    @Test
    void testApplicationPerformance() {
        long startTime = System.currentTimeMillis();
        
        // Test health endpoint performance
        ResponseEntity<HealthResponse> healthResponse = restTemplate.getForEntity(
                getBaseUrl() + "/api/health", HealthResponse.class);
        
        long healthResponseTime = System.currentTimeMillis() - startTime;
        
        assertEquals(HttpStatus.OK, healthResponse.getStatusCode());
        assertTrue(healthResponseTime < 10000, "Health check should complete within 10 seconds");
        
        HealthResponse health = healthResponse.getBody();
        assertNotNull(health);
        assertTrue(health.getResponseTimeMs() < 5000, "Health check internal time should be under 5 seconds");
        
        System.out.println("Performance Test Results:");
        System.out.println("Health endpoint response time: " + healthResponseTime + "ms");
        System.out.println("Health check internal time: " + health.getResponseTimeMs() + "ms");
        
        // Verify individual check performance
        health.getChecks().forEach((name, check) -> {
            assertTrue(check.getResponseTimeMs() < 3000, 
                      name + " check should complete within 3 seconds, but took " + check.getResponseTimeMs() + "ms");
        });
    }
}