package com.taxerp.util;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxerp.service.DSCSignatureService;
import com.taxerp.exception.SignatureException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Base64;
import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

/**
 * Unit tests for ITDPayloadGenerator.
 * Tests the generation and validation of ITD-compliant signed payloads.
 */
@ExtendWith(MockitoExtension.class)
class ITDPayloadGeneratorTest {

    @Mock
    private DSCSignatureService dscSignatureService;

    @InjectMocks
    private ITDPayloadGenerator itdPayloadGenerator;

    private ObjectMapper objectMapper;
    private static final String TEST_ERI_USER_ID = "ERIP011535";
    private static final String MOCK_SIGNATURE = "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";

    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper();
        // Inject ObjectMapper manually since @InjectMocks doesn't handle it
        itdPayloadGenerator = new ITDPayloadGenerator();
        itdPayloadGenerator.dscSignatureService = dscSignatureService;
        itdPayloadGenerator.objectMapper = objectMapper;
    }

    @Test
    void testGenerateSampleSignedPayload() throws Exception {
        // Arrange
        Map<String, Object> testData = new HashMap<>();
        testData.put("message", "Test message for signature");
        testData.put("timestamp", System.currentTimeMillis());

        when(dscSignatureService.signPayload(anyString())).thenReturn(MOCK_SIGNATURE);

        // Act
        String signedPayload = itdPayloadGenerator.generateSampleSignedPayload(testData, TEST_ERI_USER_ID);

        // Assert
        assertNotNull(signedPayload);
        assertTrue(signedPayload.length() > 0);

        // Verify ITD format structure
        @SuppressWarnings("unchecked")
        Map<String, Object> payload = objectMapper.readValue(signedPayload, Map.class);
        
        assertTrue(payload.containsKey("sign"));
        assertTrue(payload.containsKey("data"));
        assertTrue(payload.containsKey("eriUserId"));
        
        assertEquals(MOCK_SIGNATURE, payload.get("sign"));
        assertEquals(TEST_ERI_USER_ID, payload.get("eriUserId"));
        
        // Verify data is Base64 encoded
        String base64Data = (String) payload.get("data");
        assertNotNull(base64Data);
        
        // Decode and verify original data
        byte[] decodedBytes = Base64.getDecoder().decode(base64Data);
        String originalJson = new String(decodedBytes, "UTF-8");
        @SuppressWarnings("unchecked")
        Map<String, Object> originalData = objectMapper.readValue(originalJson, Map.class);
        
        assertEquals("Test message for signature", originalData.get("message"));
        assertTrue(originalData.containsKey("timestamp"));
    }

    @Test
    void testGenerateDefaultSamplePayload() throws Exception {
        // Arrange
        when(dscSignatureService.signPayload(anyString())).thenReturn(MOCK_SIGNATURE);

        // Act
        String signedPayload = itdPayloadGenerator.generateDefaultSamplePayload(TEST_ERI_USER_ID);

        // Assert
        assertNotNull(signedPayload);
        assertTrue(itdPayloadGenerator.validatePayloadStructure(signedPayload));

        @SuppressWarnings("unchecked")
        Map<String, Object> payload = objectMapper.readValue(signedPayload, Map.class);
        assertEquals(TEST_ERI_USER_ID, payload.get("eriUserId"));
        assertEquals(MOCK_SIGNATURE, payload.get("sign"));

        // Verify default data structure
        String originalData = itdPayloadGenerator.extractDataFromPayload(signedPayload);
        @SuppressWarnings("unchecked")
        Map<String, Object> dataMap = objectMapper.readValue(originalData, Map.class);
        
        assertTrue(dataMap.containsKey("formData"));
        assertTrue(dataMap.containsKey("submissionType"));
        assertTrue(dataMap.containsKey("acknowledgmentNumber"));
        
        @SuppressWarnings("unchecked")
        Map<String, Object> formData = (Map<String, Object>) dataMap.get("formData");
        assertEquals("2024-25", formData.get("assessmentYear"));
        assertEquals("ABCDE1234F", formData.get("panNumber"));
        assertEquals("ITR-1", formData.get("returnType"));
    }

    @Test
    void testGenerateSimpleTestPayload() throws Exception {
        // Arrange
        String testMessage = "Hello, this is a CMS signature test!";
        when(dscSignatureService.signPayload(anyString())).thenReturn(MOCK_SIGNATURE);

        // Act
        String signedPayload = itdPayloadGenerator.generateSimpleTestPayload(testMessage, TEST_ERI_USER_ID);

        // Assert
        assertNotNull(signedPayload);
        assertTrue(itdPayloadGenerator.validatePayloadStructure(signedPayload));

        // Verify the message is preserved
        String originalData = itdPayloadGenerator.extractDataFromPayload(signedPayload);
        @SuppressWarnings("unchecked")
        Map<String, Object> dataMap = objectMapper.readValue(originalData, Map.class);
        
        assertEquals(testMessage, dataMap.get("message"));
        assertEquals("SIGNATURE_VERIFICATION", dataMap.get("testType"));
        assertTrue(dataMap.containsKey("timestamp"));
    }

    @Test
    void testValidatePayloadStructure() throws Exception {
        // Test valid payload
        Map<String, Object> validPayload = new HashMap<>();
        validPayload.put("sign", MOCK_SIGNATURE);
        validPayload.put("data", "SGVsbG8gV29ybGQ="); // "Hello World" in Base64
        validPayload.put("eriUserId", TEST_ERI_USER_ID);
        
        String validJson = objectMapper.writeValueAsString(validPayload);
        assertTrue(itdPayloadGenerator.validatePayloadStructure(validJson));

        // Test invalid payload - missing signature
        Map<String, Object> invalidPayload = new HashMap<>();
        invalidPayload.put("data", "SGVsbG8gV29ybGQ=");
        invalidPayload.put("eriUserId", TEST_ERI_USER_ID);
        
        String invalidJson = objectMapper.writeValueAsString(invalidPayload);
        assertFalse(itdPayloadGenerator.validatePayloadStructure(invalidJson));

        // Test invalid payload - missing data
        invalidPayload.clear();
        invalidPayload.put("sign", MOCK_SIGNATURE);
        invalidPayload.put("eriUserId", TEST_ERI_USER_ID);
        
        invalidJson = objectMapper.writeValueAsString(invalidPayload);
        assertFalse(itdPayloadGenerator.validatePayloadStructure(invalidJson));

        // Test invalid payload - missing eriUserId
        invalidPayload.clear();
        invalidPayload.put("sign", MOCK_SIGNATURE);
        invalidPayload.put("data", "SGVsbG8gV29ybGQ=");
        
        invalidJson = objectMapper.writeValueAsString(invalidPayload);
        assertFalse(itdPayloadGenerator.validatePayloadStructure(invalidJson));
    }

    @Test
    void testExtractDataFromPayload() throws Exception {
        // Arrange
        String originalMessage = "Test data extraction";
        Map<String, Object> originalData = new HashMap<>();
        originalData.put("message", originalMessage);
        originalData.put("type", "extraction_test");
        
        String originalJson = objectMapper.writeValueAsString(originalData);
        String base64Data = Base64.getEncoder().encodeToString(originalJson.getBytes("UTF-8"));
        
        Map<String, Object> payload = new HashMap<>();
        payload.put("sign", MOCK_SIGNATURE);
        payload.put("data", base64Data);
        payload.put("eriUserId", TEST_ERI_USER_ID);
        
        String signedPayload = objectMapper.writeValueAsString(payload);

        // Act
        String extractedData = itdPayloadGenerator.extractDataFromPayload(signedPayload);

        // Assert
        assertNotNull(extractedData);
        @SuppressWarnings("unchecked")
        Map<String, Object> extractedMap = objectMapper.readValue(extractedData, Map.class);
        
        assertEquals(originalMessage, extractedMap.get("message"));
        assertEquals("extraction_test", extractedMap.get("type"));
    }

    @Test
    void testExtractDataFromPayloadWithMissingData() {
        // Arrange
        Map<String, Object> payload = new HashMap<>();
        payload.put("sign", MOCK_SIGNATURE);
        payload.put("eriUserId", TEST_ERI_USER_ID);
        // Missing "data" field
        
        try {
            String signedPayload = objectMapper.writeValueAsString(payload);
            
            // Act & Assert
            Exception exception = assertThrows(IllegalArgumentException.class, () -> {
                itdPayloadGenerator.extractDataFromPayload(signedPayload);
            });
            
            assertEquals("No data field found in payload", exception.getMessage());
        } catch (Exception e) {
            fail("Test setup failed: " + e.getMessage());
        }
    }

    @Test
    void testSignatureExceptionHandling() throws Exception {
        // Arrange
        Map<String, Object> testData = new HashMap<>();
        testData.put("message", "Test error handling");
        
        when(dscSignatureService.signPayload(anyString())).thenThrow(new SignatureException("Mock signature error"));

        // Act & Assert
        SignatureException exception = assertThrows(SignatureException.class, () -> {
            itdPayloadGenerator.generateSampleSignedPayload(testData, TEST_ERI_USER_ID);
        });
        
        assertTrue(exception.getMessage().contains("Failed to generate ITD-compliant signed payload"));
        assertTrue(exception.getMessage().contains("Mock signature error"));
    }
}