package com.taxerp.service;

import com.taxerp.config.DSCConfig;
import com.taxerp.config.ERIConfig;
import com.taxerp.exception.KeystoreException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.ResultSet;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

/**
 * Unit tests for StartupValidationService.
 * Tests comprehensive startup validation functionality.
 */
@ExtendWith(MockitoExtension.class)
class StartupValidationServiceTest {

    @Mock
    private DSCSignatureService dscSignatureService;

    @Mock
    private ERIApiClient eriApiClient;

    @Mock
    private DataSource dataSource;

    @Mock
    private DSCConfig dscConfig;

    @Mock
    private ERIConfig eriConfig;

    @Mock
    private AuditLogService auditLogService;

    @Mock
    private Connection connection;

    @Mock
    private DatabaseMetaData databaseMetaData;

    @Mock
    private ResultSet resultSet;

    @InjectMocks
    private StartupValidationService startupValidationService;

    private DSCConfig.KeystoreConfig keystoreConfig;
    private ERIConfig.ApiConfig apiConfig;
    private ERIConfig.HeadersConfig headersConfig;

    @BeforeEach
    void setUp() throws Exception {
        // Setup DSC config mock
        keystoreConfig = mock(DSCConfig.KeystoreConfig.class);
        when(keystoreConfig.getPath()).thenReturn("/path/to/keystore.p12");
        when(keystoreConfig.getPassword()).thenReturn("password123");
        when(dscConfig.getKeystore()).thenReturn(keystoreConfig);

        // Setup ERI config mock
        apiConfig = mock(ERIConfig.ApiConfig.class);
        when(apiConfig.getBaseUrl()).thenReturn("https://uat.eri.incometax.gov.in");
        when(apiConfig.getTimeout()).thenReturn(30000);
        when(apiConfig.getRetryAttempts()).thenReturn(3);
        
        headersConfig = mock(ERIConfig.HeadersConfig.class);
        when(eriConfig.getApi()).thenReturn(apiConfig);
        when(eriConfig.getHeaders()).thenReturn(headersConfig);

        // Setup audit log service mock
        when(auditLogService.generateCorrelationId()).thenReturn("test-correlation-id");

        // Setup database mocks
        when(dataSource.getConnection()).thenReturn(connection);
        when(connection.isValid(anyInt())).thenReturn(true);
        when(connection.isClosed()).thenReturn(false);
        when(connection.getMetaData()).thenReturn(databaseMetaData);
        when(databaseMetaData.getDatabaseProductName()).thenReturn("PostgreSQL");
        when(databaseMetaData.getDatabaseProductVersion()).thenReturn("13.0");
        when(databaseMetaData.getDriverName()).thenReturn("PostgreSQL JDBC Driver");
        when(databaseMetaData.getTables(any(), any(), anyString(), any())).thenReturn(resultSet);
        when(resultSet.next()).thenReturn(true); // Tables exist
    }

    @Test
    void testPerformManualValidation_AllComponentsHealthy() throws Exception {
        // Arrange
        when(dscSignatureService.validateKeystore()).thenReturn(true);

        // Act
        StartupValidationService.ValidationResult result = startupValidationService.performManualValidation();

        // Assert
        assertTrue(result.isOverallValid());
        assertTrue(result.isDscValid());
        assertTrue(result.isEriValid());
        assertTrue(result.isDatabaseValid());
        assertTrue(result.getErrors().isEmpty());
        assertTrue(result.getWarnings().isEmpty());

        verify(dscSignatureService).validateKeystore();
        verify(dataSource).getConnection();
        verify(connection).isValid(5);
    }

    @Test
    void testPerformManualValidation_DSCValidationFails() throws Exception {
        // Arrange
        when(dscSignatureService.validateKeystore()).thenThrow(new KeystoreException("Keystore not found"));

        // Act
        StartupValidationService.ValidationResult result = startupValidationService.performManualValidation();

        // Assert
        assertFalse(result.isOverallValid());
        assertFalse(result.isDscValid());
        assertTrue(result.isEriValid());
        assertTrue(result.isDatabaseValid());
        assertFalse(result.getErrors().isEmpty());
        assertTrue(result.getErrors().get(0).contains("DSC validation failed"));
        assertTrue(result.getErrors().get(0).contains("Keystore not found"));
    }

    @Test
    void testPerformManualValidation_DatabaseValidationFails() throws Exception {
        // Arrange
        when(dscSignatureService.validateKeystore()).thenReturn(true);
        when(connection.isValid(5)).thenReturn(false);

        // Act
        StartupValidationService.ValidationResult result = startupValidationService.performManualValidation();

        // Assert
        assertFalse(result.isOverallValid());
        assertTrue(result.isDscValid());
        assertTrue(result.isEriValid());
        assertFalse(result.isDatabaseValid());
        assertFalse(result.getErrors().isEmpty());
        assertTrue(result.getErrors().get(0).contains("Database connection is not valid"));
    }

    @Test
    void testPerformManualValidation_ERIConfigurationIncomplete() throws Exception {
        // Arrange
        when(dscSignatureService.validateKeystore()).thenReturn(true);
        when(eriConfig.getApi()).thenReturn(null); // Incomplete ERI config

        // Act
        StartupValidationService.ValidationResult result = startupValidationService.performManualValidation();

        // Assert
        assertFalse(result.isOverallValid());
        assertTrue(result.isDscValid());
        assertFalse(result.isEriValid());
        assertTrue(result.isDatabaseValid());
        assertFalse(result.getErrors().isEmpty());
        assertTrue(result.getErrors().get(0).contains("ERI configuration is incomplete"));
    }

    @Test
    void testPerformManualValidation_DatabaseConnectionException() throws Exception {
        // Arrange
        when(dscSignatureService.validateKeystore()).thenReturn(true);
        when(dataSource.getConnection()).thenThrow(new RuntimeException("Database connection failed"));

        // Act
        StartupValidationService.ValidationResult result = startupValidationService.performManualValidation();

        // Assert
        assertFalse(result.isOverallValid());
        assertTrue(result.isDscValid());
        assertTrue(result.isEriValid());
        assertFalse(result.isDatabaseValid());
        assertFalse(result.getErrors().isEmpty());
        assertTrue(result.getErrors().get(0).contains("Database validation failed"));
        assertTrue(result.getErrors().get(0).contains("Database connection failed"));
    }

    @Test
    void testValidationResult_GettersAndConstructor() {
        // Arrange
        java.util.List<String> errors = java.util.Arrays.asList("Error 1", "Error 2");
        java.util.List<String> warnings = java.util.Arrays.asList("Warning 1");

        // Act
        StartupValidationService.ValidationResult result = new StartupValidationService.ValidationResult(
                false, true, false, true, errors, warnings);

        // Assert
        assertFalse(result.isOverallValid());
        assertTrue(result.isDscValid());
        assertFalse(result.isEriValid());
        assertTrue(result.isDatabaseValid());
        assertEquals(2, result.getErrors().size());
        assertEquals(1, result.getWarnings().size());
        assertEquals("Error 1", result.getErrors().get(0));
        assertEquals("Warning 1", result.getWarnings().get(0));

        // Verify immutability - returned lists should be copies
        result.getErrors().clear();
        result.getWarnings().clear();
        assertEquals(2, result.getErrors().size()); // Should still have original errors
        assertEquals(1, result.getWarnings().size()); // Should still have original warnings
    }

    @Test
    void testInitialValidationState() {
        // Act & Assert
        assertFalse(startupValidationService.isStartupValidationPassed());
        assertTrue(startupValidationService.getValidationErrors().isEmpty());
        assertTrue(startupValidationService.getValidationWarnings().isEmpty());
    }

    @Test
    void testGetValidationErrorsAndWarnings_ReturnsCopies() {
        // This test verifies that the getter methods return defensive copies
        // to prevent external modification of internal state
        
        // Act
        java.util.List<String> errors1 = startupValidationService.getValidationErrors();
        java.util.List<String> errors2 = startupValidationService.getValidationErrors();
        java.util.List<String> warnings1 = startupValidationService.getValidationWarnings();
        java.util.List<String> warnings2 = startupValidationService.getValidationWarnings();

        // Assert
        assertNotSame(errors1, errors2); // Should be different instances
        assertNotSame(warnings1, warnings2); // Should be different instances
        assertEquals(errors1, errors2); // But should have same content
        assertEquals(warnings1, warnings2); // But should have same content
    }
}