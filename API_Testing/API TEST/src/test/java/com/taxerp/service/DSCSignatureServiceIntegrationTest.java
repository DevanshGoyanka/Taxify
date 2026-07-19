package com.taxerp.service;

import com.taxerp.config.DSCConfig;
import com.taxerp.exception.KeystoreException;
import com.taxerp.exception.SignatureException;
import com.taxerp.util.SignatureUtil;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Integration tests for DSCSignatureService.
 * Tests keystore loading, signature generation, and validation workflows.
 * Note: These tests focus on error handling and configuration validation.
 * For full signature testing, a real DSC keystore file would be needed.
 */
@SpringBootTest
@ActiveProfiles("test")
class DSCSignatureServiceIntegrationTest {

    private DSCSignatureService dscSignatureService;
    private DSCConfig dscConfig;

    @TempDir
    Path tempDir;

    private Path testKeystorePath;
    private static final String TEST_KEYSTORE_PASSWORD = "test123";

    @BeforeEach
    void setUp() throws Exception {
        // Create DSC config for testing
        dscConfig = new DSCConfig();
        testKeystorePath = tempDir.resolve("test-keystore.p12");
        
        // Create DSC service implementation
        dscSignatureService = new DSCSignatureServiceImpl();
        
        // Use reflection to set the config (since we can't use @Autowired in this test setup)
        java.lang.reflect.Field configField = DSCSignatureServiceImpl.class.getDeclaredField("dscConfig");
        configField.setAccessible(true);
        configField.set(dscSignatureService, dscConfig);
        
        // Initialize the service
        java.lang.reflect.Method initMethod = DSCSignatureServiceImpl.class.getDeclaredMethod("init");
        initMethod.setAccessible(true);
        initMethod.invoke(dscSignatureService);
    }

    @Test
    @DisplayName("Should throw exception when keystore file does not exist")
    void testValidateKeystoreFileNotFound() {
        // Configure with non-existent keystore path
        configureDSCConfig(tempDir.resolve("nonexistent.p12").toString(), TEST_KEYSTORE_PASSWORD);
        
        KeystoreException exception = assertThrows(KeystoreException.class, () -> {
            dscSignatureService.validateKeystore();
        });
        
        assertTrue(exception.getMessage().contains("Failed to load keystore"), 
                  "Exception should indicate keystore loading failure");
    }

    @Test
    @DisplayName("Should throw exception with empty keystore path")
    void testValidateKeystoreEmptyPath() {
        // Configure with empty keystore path
        configureDSCConfig("", TEST_KEYSTORE_PASSWORD);
        
        KeystoreException exception = assertThrows(KeystoreException.class, () -> {
            dscSignatureService.validateKeystore();
        });
        
        assertTrue(exception.getMessage().contains("Failed to load keystore"), 
                  "Exception should indicate keystore loading failure");
    }

    @Test
    @DisplayName("Should throw exception with null keystore path")
    void testValidateKeystoreNullPath() {
        // Configure with null keystore path
        configureDSCConfig(null, TEST_KEYSTORE_PASSWORD);
        
        assertThrows(Exception.class, () -> {
            dscSignatureService.validateKeystore();
        }, "Should throw exception with null keystore path");
    }

    @Test
    @DisplayName("Should throw exception when getting certificate details without valid keystore")
    void testGetCertificateDetailsWithoutKeystore() {
        // Configure with non-existent keystore
        configureDSCConfig(tempDir.resolve("nonexistent.p12").toString(), TEST_KEYSTORE_PASSWORD);
        
        assertThrows(KeystoreException.class, () -> {
            dscSignatureService.getCertificateDetails();
        }, "Should throw KeystoreException when keystore is not accessible");
    }

    @Test
    @DisplayName("Should throw exception when signing payload without valid keystore")
    void testSignPayloadWithoutKeystore() {
        // Configure with non-existent keystore
        configureDSCConfig(tempDir.resolve("nonexistent.p12").toString(), TEST_KEYSTORE_PASSWORD);
        
        String testPayload = "{\"test\":\"data\"}";
        
        assertThrows(SignatureException.class, () -> {
            dscSignatureService.signPayload(testPayload);
        }, "Should throw SignatureException when keystore is not accessible");
    }

    @Test
    @DisplayName("Should throw exception for null payload")
    void testSignNullPayload() {
        // Configure with valid path but invalid keystore to test null payload handling
        configureDSCConfig(testKeystorePath.toString(), TEST_KEYSTORE_PASSWORD);
        
        assertThrows(Exception.class, () -> {
            dscSignatureService.signPayload(null);
        }, "Should throw exception for null payload");
    }

    @Test
    @DisplayName("Should throw exception for empty payload")
    void testSignEmptyPayload() {
        // Configure with valid path but invalid keystore to test empty payload handling
        configureDSCConfig(testKeystorePath.toString(), TEST_KEYSTORE_PASSWORD);
        
        assertThrows(Exception.class, () -> {
            dscSignatureService.signPayload("");
        }, "Should throw exception for empty payload");
    }

    @Test
    @DisplayName("Should handle invalid JSON payload gracefully")
    void testSignInvalidJsonPayload() {
        // Configure with valid path but invalid keystore
        configureDSCConfig(testKeystorePath.toString(), TEST_KEYSTORE_PASSWORD);
        
        String invalidJson = "{invalid json structure";
        
        // Should throw exception due to invalid JSON or keystore issues
        assertThrows(Exception.class, () -> {
            dscSignatureService.signPayload(invalidJson);
        }, "Should throw exception for invalid JSON or keystore issues");
    }

    @Test
    @DisplayName("Should handle PKCS11 configuration validation")
    void testPKCS11ConfigurationValidation() {
        // Configure for PKCS11 without library path
        dscConfig.getKeystore().setType(DSCConfig.KeystoreType.PKCS11);
        dscConfig.getKeystore().setPath(""); // PKCS11 doesn't use file path
        dscConfig.getKeystore().setPassword(TEST_KEYSTORE_PASSWORD);
        dscConfig.getPkcs11().setLibraryPath(null); // No library path
        
        KeystoreException exception = assertThrows(KeystoreException.class, () -> {
            dscSignatureService.validateKeystore();
        });
        
        assertTrue(exception.getMessage().contains("PKCS#11 library path not configured"), 
                  "Should indicate missing PKCS#11 library path");
    }

    @Test
    @DisplayName("Should validate DSC configuration properties")
    void testDSCConfigurationValidation() {
        // Test various configuration scenarios
        DSCConfig config = new DSCConfig();
        
        // Test keystore configuration
        assertNotNull(config.getKeystore(), "Keystore config should not be null");
        assertNotNull(config.getPkcs11(), "PKCS11 config should not be null");
        
        // Test default values
        assertEquals(DSCConfig.KeystoreType.PKCS12, config.getKeystore().getType(), 
                    "Default keystore type should be PKCS12");
    }

    /**
     * Configures DSC config for testing
     */
    private void configureDSCConfig(String keystorePath, String password) {
        dscConfig.getKeystore().setPath(keystorePath);
        dscConfig.getKeystore().setPassword(password);
        dscConfig.getKeystore().setType(DSCConfig.KeystoreType.PKCS12);
        dscConfig.getKeystore().setAlias("testcert");
    }

    /**
     * Creates an empty file to simulate invalid keystore
     */
    private void createInvalidKeystoreFile() throws IOException {
        Files.write(testKeystorePath, "invalid keystore content".getBytes());
    }
}