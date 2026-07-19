package com.taxerp.controller;

import com.taxerp.config.ERIConfig;
import com.taxerp.dto.HealthResponse;
import com.taxerp.service.DSCSignatureService;
import com.taxerp.service.ERIApiClient;
import com.taxerp.exception.KeystoreException;
import com.taxerp.exception.ERIApiException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.core.env.Environment;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.util.ReflectionTestUtils;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.SQLException;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

/**
 * Unit tests for HealthController functionality.
 * Tests health endpoint response format, timing, and individual health check components.
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("HealthController Tests")
class HealthControllerTest {

    @Mock
    private DSCSignatureService dscSignatureService;

    @Mock
    private ERIApiClient eriApiClient;

    @Mock
    private ERIConfig eriConfig;

    @Mock
    private DataSource dataSource;

    @Mock
    private Environment environment;

    @Mock
    private Connection connection;

    @Mock
    private DatabaseMetaData databaseMetaData;

    @InjectMocks
    private HealthController healthController;

    private ERIConfig.Api apiConfig;
    private ERIConfig.Headers headersConfig;
    private ERIConfig.Retry retryConfig;
    private DSCSignatureService.CertificateInfo certificateInfo;

    @BeforeEach
    void setUp() {
        // Set up application properties
        ReflectionTestUtils.setField(healthController, "applicationName", "TaxERP");
        ReflectionTestUtils.setField(healthController, "applicationVersion", "1.0.0");

        // Set up ERI configuration mocks
        apiConfig = new ERIConfig.Api();
        apiConfig.setBaseUrl("https://uat.eri.incometax.gov.in");
        apiConfig.setConnectionTimeout(30000);
        apiConfig.setReadTimeout(60000);
        apiConfig.setSslVerification(true);

        headersConfig = new ERIConfig.Headers();
        headersConfig.setUserAgent("TaxERP-Phase1/1.0");
        headersConfig.setContentType("application/json");

        retryConfig = new ERIConfig.Retry();
        retryConfig.setMaxAttempts(3);
        retryConfig.setInitialDelayMs(1000);

        when(eriConfig.getApi()).thenReturn(apiConfig);
        when(eriConfig.getHeaders()).thenReturn(headersConfig);
        when(eriConfig.getRetry()).thenReturn(retryConfig);

        // Set up certificate info mock
        certificateInfo = new DSCSignatureService.CertificateInfo(
                "CN=Test User, O=Test Org",
                "CN=Test CA, O=Test CA Org",
                "123456789",
                "2024-01-01T00:00:00",
                "2025-01-01T00:00:00",
                "RSA",
                2048,
                true
        );

        // Set up environment mock
        when(environment.getActiveProfiles()).thenReturn(new String[]{"test"});
    }

    @Test
    @DisplayName("Should return healthy status when all checks pass")
    void shouldReturnHealthyStatusWhenAllChecksPass() throws Exception {
        // Given
        when(dscSignatureService.validateKeystore()).thenReturn(true);
        when(dscSignatureService.getCertificateDetails()).thenReturn(certificateInfo);
        when(eriApiClient.validateConnectivity()).thenReturn(true);
        when(eriApiClient.getConfigurationStatus()).thenReturn("ERI API Configuration - Base URL: https://uat.eri.incometax.gov.in, Timeout: 30000ms, Max Attempts: 3");
        
        when(dataSource.getConnection()).thenReturn(connection);
        when(connection.isValid(5)).thenReturn(true);
        when(connection.getMetaData()).thenReturn(databaseMetaData);
        when(databaseMetaData.getURL()).thenReturn("jdbc:postgresql://localhost:5432/taxerp_test");
        when(databaseMetaData.getDatabaseProductName()).thenReturn("PostgreSQL");
        when(databaseMetaData.getDatabaseProductVersion()).thenReturn("15.0");
        when(databaseMetaData.getDriverName()).thenReturn("PostgreSQL JDBC Driver");
        when(databaseMetaData.getDriverVersion()).thenReturn("42.6.0");

        // When
        ResponseEntity<HealthResponse> response = healthController.health();

        // Then
        assertNotNull(response);
        assertEquals(HttpStatus.OK, response.getStatusCode());
        
        HealthResponse healthResponse = response.getBody();
        assertNotNull(healthResponse);
        assertEquals("UP", healthResponse.getStatus());
        assertEquals("1.0.0", healthResponse.getVersion());
        assertEquals("test", healthResponse.getEnvironment());
        assertTrue(healthResponse.getResponseTimeMs() >= 0);
        
        Map<String, HealthResponse.HealthCheck> checks = healthResponse.getChecks();
        assertNotNull(checks);
        assertEquals(4, checks.size());
        
        // Verify DSC keystore check
        HealthResponse.HealthCheck dscCheck = checks.get("dsc_keystore");
        assertNotNull(dscCheck);
        assertEquals("UP", dscCheck.getStatus());
        assertTrue(dscCheck.isHealthy());
        assertNotNull(dscCheck.getDetails());
        assertEquals("CN=Test User, O=Test Org", dscCheck.getDetails().get("certificateSubject"));
        
        // Verify ERI configuration check
        HealthResponse.HealthCheck eriConfigCheck = checks.get("eri_configuration");
        assertNotNull(eriConfigCheck);
        assertEquals("UP", eriConfigCheck.getStatus());
        assertTrue(eriConfigCheck.isHealthy());
        
        // Verify database connectivity check
        HealthResponse.HealthCheck dbCheck = checks.get("database_connectivity");
        assertNotNull(dbCheck);
        assertEquals("UP", dbCheck.getStatus());
        assertTrue(dbCheck.isHealthy());
        
        // Verify ERI connectivity check
        HealthResponse.HealthCheck eriConnCheck = checks.get("eri_connectivity");
        assertNotNull(eriConnCheck);
        assertEquals("UP", eriConnCheck.getStatus());
        assertTrue(eriConnCheck.isHealthy());
    }

    @Test
    @DisplayName("Should return unhealthy status when DSC keystore check fails")
    void shouldReturnUnhealthyStatusWhenDSCKeystoreCheckFails() throws Exception {
        // Given
        when(dscSignatureService.validateKeystore()).thenThrow(new KeystoreException("Keystore not found", "KEYSTORE_NOT_FOUND", 500));
        when(eriApiClient.validateConnectivity()).thenReturn(true);
        when(eriApiClient.getConfigurationStatus()).thenReturn("ERI API Configuration - OK");
        
        when(dataSource.getConnection()).thenReturn(connection);
        when(connection.isValid(5)).thenReturn(true);
        when(connection.getMetaData()).thenReturn(databaseMetaData);
        when(databaseMetaData.getURL()).thenReturn("jdbc:postgresql://localhost:5432/taxerp_test");
        when(databaseMetaData.getDatabaseProductName()).thenReturn("PostgreSQL");
        when(databaseMetaData.getDatabaseProductVersion()).thenReturn("15.0");
        when(databaseMetaData.getDriverName()).thenReturn("PostgreSQL JDBC Driver");
        when(databaseMetaData.getDriverVersion()).thenReturn("42.6.0");

        // When
        ResponseEntity<HealthResponse> response = healthController.health();

        // Then
        assertNotNull(response);
        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, response.getStatusCode());
        
        HealthResponse healthResponse = response.getBody();
        assertNotNull(healthResponse);
        assertEquals("DOWN", healthResponse.getStatus());
        
        Map<String, HealthResponse.HealthCheck> checks = healthResponse.getChecks();
        HealthResponse.HealthCheck dscCheck = checks.get("dsc_keystore");
        assertNotNull(dscCheck);
        assertEquals("DOWN", dscCheck.getStatus());
        assertFalse(dscCheck.isHealthy());
        assertEquals("Keystore not found", dscCheck.getError());
    }

    @Test
    @DisplayName("Should return unhealthy status when ERI configuration is invalid")
    void shouldReturnUnhealthyStatusWhenERIConfigurationIsInvalid() throws Exception {
        // Given - Invalid ERI configuration
        apiConfig.setBaseUrl(""); // Invalid empty URL
        when(dscSignatureService.validateKeystore()).thenReturn(true);
        when(dscSignatureService.getCertificateDetails()).thenReturn(certificateInfo);
        when(eriApiClient.validateConnectivity()).thenReturn(true);
        when(eriApiClient.getConfigurationStatus()).thenReturn("ERI API Configuration - OK");
        
        when(dataSource.getConnection()).thenReturn(connection);
        when(connection.isValid(5)).thenReturn(true);
        when(connection.getMetaData()).thenReturn(databaseMetaData);
        when(databaseMetaData.getURL()).thenReturn("jdbc:postgresql://localhost:5432/taxerp_test");
        when(databaseMetaData.getDatabaseProductName()).thenReturn("PostgreSQL");
        when(databaseMetaData.getDatabaseProductVersion()).thenReturn("15.0");
        when(databaseMetaData.getDriverName()).thenReturn("PostgreSQL JDBC Driver");
        when(databaseMetaData.getDriverVersion()).thenReturn("42.6.0");

        // When
        ResponseEntity<HealthResponse> response = healthController.health();

        // Then
        assertNotNull(response);
        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, response.getStatusCode());
        
        HealthResponse healthResponse = response.getBody();
        assertNotNull(healthResponse);
        assertEquals("DOWN", healthResponse.getStatus());
        
        Map<String, HealthResponse.HealthCheck> checks = healthResponse.getChecks();
        HealthResponse.HealthCheck eriConfigCheck = checks.get("eri_configuration");
        assertNotNull(eriConfigCheck);
        assertEquals("DOWN", eriConfigCheck.getStatus());
        assertFalse(eriConfigCheck.isHealthy());
    }

    @Test
    @DisplayName("Should return unhealthy status when database connectivity fails")
    void shouldReturnUnhealthyStatusWhenDatabaseConnectivityFails() throws Exception {
        // Given
        when(dscSignatureService.validateKeystore()).thenReturn(true);
        when(dscSignatureService.getCertificateDetails()).thenReturn(certificateInfo);
        when(eriApiClient.validateConnectivity()).thenReturn(true);
        when(eriApiClient.getConfigurationStatus()).thenReturn("ERI API Configuration - OK");
        
        when(dataSource.getConnection()).thenThrow(new SQLException("Connection failed"));

        // When
        ResponseEntity<HealthResponse> response = healthController.health();

        // Then
        assertNotNull(response);
        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, response.getStatusCode());
        
        HealthResponse healthResponse = response.getBody();
        assertNotNull(healthResponse);
        assertEquals("DOWN", healthResponse.getStatus());
        
        Map<String, HealthResponse.HealthCheck> checks = healthResponse.getChecks();
        HealthResponse.HealthCheck dbCheck = checks.get("database_connectivity");
        assertNotNull(dbCheck);
        assertEquals("DOWN", dbCheck.getStatus());
        assertFalse(dbCheck.isHealthy());
        assertEquals("Connection failed", dbCheck.getError());
    }

    @Test
    @DisplayName("Should return unhealthy status when ERI connectivity fails")
    void shouldReturnUnhealthyStatusWhenERIConnectivityFails() throws Exception {
        // Given
        when(dscSignatureService.validateKeystore()).thenReturn(true);
        when(dscSignatureService.getCertificateDetails()).thenReturn(certificateInfo);
        when(eriApiClient.validateConnectivity()).thenThrow(new ERIApiException("ERI API not accessible", "CONNECTIVITY_ERROR", 503));
        
        when(dataSource.getConnection()).thenReturn(connection);
        when(connection.isValid(5)).thenReturn(true);
        when(connection.getMetaData()).thenReturn(databaseMetaData);
        when(databaseMetaData.getURL()).thenReturn("jdbc:postgresql://localhost:5432/taxerp_test");
        when(databaseMetaData.getDatabaseProductName()).thenReturn("PostgreSQL");
        when(databaseMetaData.getDatabaseProductVersion()).thenReturn("15.0");
        when(databaseMetaData.getDriverName()).thenReturn("PostgreSQL JDBC Driver");
        when(databaseMetaData.getDriverVersion()).thenReturn("42.6.0");

        // When
        ResponseEntity<HealthResponse> response = healthController.health();

        // Then
        assertNotNull(response);
        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, response.getStatusCode());
        
        HealthResponse healthResponse = response.getBody();
        assertNotNull(healthResponse);
        assertEquals("DOWN", healthResponse.getStatus());
        
        Map<String, HealthResponse.HealthCheck> checks = healthResponse.getChecks();
        HealthResponse.HealthCheck eriConnCheck = checks.get("eri_connectivity");
        assertNotNull(eriConnCheck);
        assertEquals("DOWN", eriConnCheck.getStatus());
        assertFalse(eriConnCheck.isHealthy());
        assertEquals("ERI API not accessible", eriConnCheck.getError());
    }

    @Test
    @DisplayName("Should measure response times for individual health checks")
    void shouldMeasureResponseTimesForIndividualHealthChecks() throws Exception {
        // Given
        when(dscSignatureService.validateKeystore()).thenReturn(true);
        when(dscSignatureService.getCertificateDetails()).thenReturn(certificateInfo);
        when(eriApiClient.validateConnectivity()).thenReturn(true);
        when(eriApiClient.getConfigurationStatus()).thenReturn("ERI API Configuration - OK");
        
        when(dataSource.getConnection()).thenReturn(connection);
        when(connection.isValid(5)).thenReturn(true);
        when(connection.getMetaData()).thenReturn(databaseMetaData);
        when(databaseMetaData.getURL()).thenReturn("jdbc:postgresql://localhost:5432/taxerp_test");
        when(databaseMetaData.getDatabaseProductName()).thenReturn("PostgreSQL");
        when(databaseMetaData.getDatabaseProductVersion()).thenReturn("15.0");
        when(databaseMetaData.getDriverName()).thenReturn("PostgreSQL JDBC Driver");
        when(databaseMetaData.getDriverVersion()).thenReturn("42.6.0");

        // When
        ResponseEntity<HealthResponse> response = healthController.health();

        // Then
        assertNotNull(response);
        HealthResponse healthResponse = response.getBody();
        assertNotNull(healthResponse);
        
        Map<String, HealthResponse.HealthCheck> checks = healthResponse.getChecks();
        
        // Verify that all checks have response times measured
        for (HealthResponse.HealthCheck check : checks.values()) {
            assertNotNull(check.getResponseTimeMs());
            assertTrue(check.getResponseTimeMs() >= 0);
        }
        
        // Verify overall response time is measured
        assertTrue(healthResponse.getResponseTimeMs() >= 0);
    }

    @Test
    @DisplayName("Should handle multiple failures gracefully")
    void shouldHandleMultipleFailuresGracefully() throws Exception {
        // Given - Multiple failures
        when(dscSignatureService.validateKeystore()).thenThrow(new KeystoreException("Keystore error", "KEYSTORE_ERROR", 500));
        when(eriApiClient.validateConnectivity()).thenThrow(new ERIApiException("ERI error", "ERI_ERROR", 503));
        when(dataSource.getConnection()).thenThrow(new SQLException("Database error"));

        // When
        ResponseEntity<HealthResponse> response = healthController.health();

        // Then
        assertNotNull(response);
        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, response.getStatusCode());
        
        HealthResponse healthResponse = response.getBody();
        assertNotNull(healthResponse);
        assertEquals("DOWN", healthResponse.getStatus());
        
        Map<String, HealthResponse.HealthCheck> checks = healthResponse.getChecks();
        assertEquals(4, checks.size());
        
        // Verify all checks are marked as DOWN
        for (HealthResponse.HealthCheck check : checks.values()) {
            assertEquals("DOWN", check.getStatus());
            assertFalse(check.isHealthy());
            assertNotNull(check.getError());
        }
    }

    @Test
    @DisplayName("Should return proper response format and timing within 5 seconds")
    void shouldReturnProperResponseFormatAndTimingWithin5Seconds() throws Exception {
        // Given
        when(dscSignatureService.validateKeystore()).thenReturn(true);
        when(dscSignatureService.getCertificateDetails()).thenReturn(certificateInfo);
        when(eriApiClient.validateConnectivity()).thenReturn(true);
        when(eriApiClient.getConfigurationStatus()).thenReturn("ERI API Configuration - OK");
        
        when(dataSource.getConnection()).thenReturn(connection);
        when(connection.isValid(5)).thenReturn(true);
        when(connection.getMetaData()).thenReturn(databaseMetaData);
        when(databaseMetaData.getURL()).thenReturn("jdbc:postgresql://localhost:5432/taxerp_test");
        when(databaseMetaData.getDatabaseProductName()).thenReturn("PostgreSQL");
        when(databaseMetaData.getDatabaseProductVersion()).thenReturn("15.0");
        when(databaseMetaData.getDriverName()).thenReturn("PostgreSQL JDBC Driver");
        when(databaseMetaData.getDriverVersion()).thenReturn("42.6.0");

        // When
        long startTime = System.currentTimeMillis();
        ResponseEntity<HealthResponse> response = healthController.health();
        long endTime = System.currentTimeMillis();

        // Then
        assertNotNull(response);
        
        // Verify response timing (should be well under 5 seconds for unit tests)
        long actualResponseTime = endTime - startTime;
        assertTrue(actualResponseTime < 5000, "Health check should complete within 5 seconds");
        
        HealthResponse healthResponse = response.getBody();
        assertNotNull(healthResponse);
        
        // Verify response format
        assertNotNull(healthResponse.getStatus());
        assertNotNull(healthResponse.getTimestamp());
        assertNotNull(healthResponse.getVersion());
        assertNotNull(healthResponse.getEnvironment());
        assertNotNull(healthResponse.getChecks());
        assertTrue(healthResponse.getResponseTimeMs() >= 0);
        assertTrue(healthResponse.getResponseTimeMs() < 5000);
    }

    @Test
    @DisplayName("Should validate ERI configuration parameters correctly")
    void shouldValidateERIConfigurationParametersCorrectly() throws Exception {
        // Given - Test various invalid configurations
        when(dscSignatureService.validateKeystore()).thenReturn(true);
        when(dscSignatureService.getCertificateDetails()).thenReturn(certificateInfo);
        when(eriApiClient.validateConnectivity()).thenReturn(true);
        when(eriApiClient.getConfigurationStatus()).thenReturn("ERI API Configuration - OK");
        
        when(dataSource.getConnection()).thenReturn(connection);
        when(connection.isValid(5)).thenReturn(true);
        when(connection.getMetaData()).thenReturn(databaseMetaData);
        when(databaseMetaData.getURL()).thenReturn("jdbc:postgresql://localhost:5432/taxerp_test");
        when(databaseMetaData.getDatabaseProductName()).thenReturn("PostgreSQL");
        when(databaseMetaData.getDatabaseProductVersion()).thenReturn("15.0");
        when(databaseMetaData.getDriverName()).thenReturn("PostgreSQL JDBC Driver");
        when(databaseMetaData.getDriverVersion()).thenReturn("42.6.0");

        // Test case 1: Invalid connection timeout
        apiConfig.setConnectionTimeout(-1);
        ResponseEntity<HealthResponse> response1 = healthController.health();
        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, response1.getStatusCode());
        
        // Reset and test case 2: Invalid read timeout
        apiConfig.setConnectionTimeout(30000);
        apiConfig.setReadTimeout(0);
        ResponseEntity<HealthResponse> response2 = healthController.health();
        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, response2.getStatusCode());
        
        // Reset and test case 3: Empty User-Agent
        apiConfig.setReadTimeout(60000);
        headersConfig.setUserAgent("");
        ResponseEntity<HealthResponse> response3 = healthController.health();
        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, response3.getStatusCode());
        
        // Reset and test case 4: Invalid retry attempts
        headersConfig.setUserAgent("TaxERP-Phase1/1.0");
        retryConfig.setMaxAttempts(0);
        ResponseEntity<HealthResponse> response4 = healthController.health();
        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, response4.getStatusCode());
    }
}