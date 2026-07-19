package com.taxerp.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxerp.dto.HealthResponse;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureTestMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Integration tests for HealthController.
 * Tests the complete health check workflow with real Spring context and database.
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
        "eri.api.base-url=https://uat.eri.incometax.gov.in",
        "eri.api.connection-timeout=30000",
        "eri.api.read-timeout=60000",
        "eri.headers.user-agent=TaxERP-Phase1/1.0",
        "eri.retry.max-attempts=3",
        "logging.level.com.taxerp=DEBUG"
})
@Testcontainers
@DisplayName("HealthController Integration Tests")
class HealthControllerIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15-alpine")
            .withDatabaseName("taxerp_test")
            .withUsername("test")
            .withPassword("test");

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    @DisplayName("Should return health status via REST endpoint")
    void shouldReturnHealthStatusViaRESTEndpoint() throws Exception {
        // When & Then
        MvcResult result = mockMvc.perform(get("/api/health")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").exists())
                .andExpect(jsonPath("$.timestamp").exists())
                .andExpect(jsonPath("$.responseTimeMs").exists())
                .andExpect(jsonPath("$.version").exists())
                .andExpect(jsonPath("$.environment").exists())
                .andExpect(jsonPath("$.checks").exists())
                .andExpect(jsonPath("$.checks.dsc_keystore").exists())
                .andExpect(jsonPath("$.checks.eri_configuration").exists())
                .andExpect(jsonPath("$.checks.database_connectivity").exists())
                .andExpect(jsonPath("$.checks.eri_connectivity").exists())
                .andReturn();

        // Verify response structure
        String responseContent = result.getResponse().getContentAsString();
        HealthResponse healthResponse = objectMapper.readValue(responseContent, HealthResponse.class);
        
        assertNotNull(healthResponse);
        assertNotNull(healthResponse.getStatus());
        assertNotNull(healthResponse.getTimestamp());
        assertNotNull(healthResponse.getChecks());
        assertTrue(healthResponse.getResponseTimeMs() >= 0);
        assertEquals(4, healthResponse.getChecks().size());
    }

    @Test
    @DisplayName("Should complete health check within 5 seconds")
    void shouldCompleteHealthCheckWithin5Seconds() throws Exception {
        // When
        long startTime = System.currentTimeMillis();
        
        MvcResult result = mockMvc.perform(get("/api/health")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andReturn();
        
        long endTime = System.currentTimeMillis();
        long actualResponseTime = endTime - startTime;

        // Then
        assertTrue(actualResponseTime < 5000, 
                "Health check should complete within 5 seconds, but took " + actualResponseTime + "ms");

        // Verify the response also reports reasonable timing
        String responseContent = result.getResponse().getContentAsString();
        HealthResponse healthResponse = objectMapper.readValue(responseContent, HealthResponse.class);
        
        assertTrue(healthResponse.getResponseTimeMs() < 5000,
                "Reported response time should be under 5 seconds");
    }

    @Test
    @DisplayName("Should return proper HTTP status codes based on health")
    void shouldReturnProperHTTPStatusCodesBasedOnHealth() throws Exception {
        // When & Then - Test that endpoint returns appropriate status
        // Note: In integration test, some checks might fail due to missing keystore or ERI connectivity
        // but the endpoint should still respond with proper structure
        
        mockMvc.perform(get("/api/health")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk()) // or SERVICE_UNAVAILABLE depending on actual system state
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.status").value(org.hamcrest.Matchers.oneOf("UP", "DOWN")))
                .andExpect(jsonPath("$.checks").exists());
    }

    @Test
    @DisplayName("Should validate individual health check components")
    void shouldValidateIndividualHealthCheckComponents() throws Exception {
        // When
        MvcResult result = mockMvc.perform(get("/api/health")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andReturn();

        // Then
        String responseContent = result.getResponse().getContentAsString();
        HealthResponse healthResponse = objectMapper.readValue(responseContent, HealthResponse.class);
        
        // Verify each health check component exists and has proper structure
        assertNotNull(healthResponse.getChecks().get("dsc_keystore"));
        assertNotNull(healthResponse.getChecks().get("eri_configuration"));
        assertNotNull(healthResponse.getChecks().get("database_connectivity"));
        assertNotNull(healthResponse.getChecks().get("eri_connectivity"));
        
        // Verify each check has required fields
        for (HealthResponse.HealthCheck check : healthResponse.getChecks().values()) {
            assertNotNull(check.getStatus());
            assertNotNull(check.getMessage());
            assertNotNull(check.getResponseTimeMs());
            assertTrue(check.getResponseTimeMs() >= 0);
            
            // Status should be either UP or DOWN
            assertTrue(check.getStatus().equals("UP") || check.getStatus().equals("DOWN"));
        }
    }

    @Test
    @DisplayName("Should handle database connectivity check properly")
    void shouldHandleDatabaseConnectivityCheckProperly() throws Exception {
        // When
        MvcResult result = mockMvc.perform(get("/api/health")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andReturn();

        // Then
        String responseContent = result.getResponse().getContentAsString();
        HealthResponse healthResponse = objectMapper.readValue(responseContent, HealthResponse.class);
        
        HealthResponse.HealthCheck dbCheck = healthResponse.getChecks().get("database_connectivity");
        assertNotNull(dbCheck);
        
        // Database should be UP since we're using TestContainers
        assertEquals("UP", dbCheck.getStatus());
        assertTrue(dbCheck.isHealthy());
        
        // Should have database details
        assertNotNull(dbCheck.getDetails());
        assertTrue(dbCheck.getDetails().containsKey("databaseUrl"));
        assertTrue(dbCheck.getDetails().containsKey("databaseProduct"));
        assertTrue(dbCheck.getDetails().containsKey("databaseVersion"));
        assertTrue(dbCheck.getDetails().containsKey("driverName"));
        assertTrue(dbCheck.getDetails().containsKey("driverVersion"));
    }

    @Test
    @DisplayName("Should validate ERI configuration check")
    void shouldValidateERIConfigurationCheck() throws Exception {
        // When
        MvcResult result = mockMvc.perform(get("/api/health")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andReturn();

        // Then
        String responseContent = result.getResponse().getContentAsString();
        HealthResponse healthResponse = objectMapper.readValue(responseContent, HealthResponse.class);
        
        HealthResponse.HealthCheck eriConfigCheck = healthResponse.getChecks().get("eri_configuration");
        assertNotNull(eriConfigCheck);
        
        // ERI configuration should be UP since we have valid test properties
        assertEquals("UP", eriConfigCheck.getStatus());
        assertTrue(eriConfigCheck.isHealthy());
        
        // Should have configuration details
        assertNotNull(eriConfigCheck.getDetails());
        assertTrue(eriConfigCheck.getDetails().containsKey("baseUrl"));
        assertTrue(eriConfigCheck.getDetails().containsKey("connectionTimeout"));
        assertTrue(eriConfigCheck.getDetails().containsKey("readTimeout"));
        assertTrue(eriConfigCheck.getDetails().containsKey("sslVerification"));
        assertTrue(eriConfigCheck.getDetails().containsKey("maxRetryAttempts"));
        assertTrue(eriConfigCheck.getDetails().containsKey("userAgent"));
        
        assertEquals("https://uat.eri.incometax.gov.in", eriConfigCheck.getDetails().get("baseUrl"));
        assertEquals(30000, eriConfigCheck.getDetails().get("connectionTimeout"));
        assertEquals("TaxERP-Phase1/1.0", eriConfigCheck.getDetails().get("userAgent"));
    }

    @Test
    @DisplayName("Should provide proper error reporting for failed checks")
    void shouldProvideProperErrorReportingForFailedChecks() throws Exception {
        // When
        MvcResult result = mockMvc.perform(get("/api/health")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk()) // May be SERVICE_UNAVAILABLE if checks fail
                .andReturn();

        // Then
        String responseContent = result.getResponse().getContentAsString();
        HealthResponse healthResponse = objectMapper.readValue(responseContent, HealthResponse.class);
        
        // Check that any failed health checks have proper error information
        for (HealthResponse.HealthCheck check : healthResponse.getChecks().values()) {
            if ("DOWN".equals(check.getStatus())) {
                // Failed checks should have error information
                assertNotNull(check.getError(), 
                        "Failed health check should have error message");
                assertFalse(check.getError().trim().isEmpty(), 
                        "Error message should not be empty");
            }
        }
    }

    @Test
    @DisplayName("Should return consistent response format across multiple calls")
    void shouldReturnConsistentResponseFormatAcrossMultipleCalls() throws Exception {
        // When - Make multiple calls
        MvcResult result1 = mockMvc.perform(get("/api/health")).andReturn();
        MvcResult result2 = mockMvc.perform(get("/api/health")).andReturn();
        MvcResult result3 = mockMvc.perform(get("/api/health")).andReturn();

        // Then - Parse responses
        HealthResponse response1 = objectMapper.readValue(result1.getResponse().getContentAsString(), HealthResponse.class);
        HealthResponse response2 = objectMapper.readValue(result2.getResponse().getContentAsString(), HealthResponse.class);
        HealthResponse response3 = objectMapper.readValue(result3.getResponse().getContentAsString(), HealthResponse.class);

        // Verify consistent structure
        assertEquals(response1.getChecks().size(), response2.getChecks().size());
        assertEquals(response2.getChecks().size(), response3.getChecks().size());
        
        // Verify same check names exist
        assertEquals(response1.getChecks().keySet(), response2.getChecks().keySet());
        assertEquals(response2.getChecks().keySet(), response3.getChecks().keySet());
        
        // Verify version and environment are consistent
        assertEquals(response1.getVersion(), response2.getVersion());
        assertEquals(response1.getEnvironment(), response2.getEnvironment());
    }
}