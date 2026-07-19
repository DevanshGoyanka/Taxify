package com.taxerp.util;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxerp.service.DSCSignatureService;
import com.taxerp.exception.SignatureException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.Base64;
import java.util.HashMap;
import java.util.Map;

/**
 * Utility class for generating ITD-compliant signed payloads.
 * Creates sample payloads matching the ITD format specifications with signature, data, and eriUserId fields.
 */
@Component
public class ITDPayloadGenerator {

    private static final Logger logger = LoggerFactory.getLogger(ITDPayloadGenerator.class);

    @Autowired
    private DSCSignatureService dscSignatureService;

    @Autowired
    private ObjectMapper objectMapper;

    /**
     * Generates a sample signed payload matching ITD format specifications.
     * The payload includes signature, Base64-encoded data, and eriUserId fields as required by ITD.
     *
     * @param testData The test data to be signed and encoded
     * @param eriUserId The ERI user ID for the payload
     * @return ITD-compliant signed payload as JSON string
     * @throws SignatureException if payload generation fails
     */
    public String generateSampleSignedPayload(Object testData, String eriUserId) throws SignatureException {
        try {
            logger.info("Generating ITD-compliant signed payload for ERI User ID: {}", eriUserId);

            // Step 1: Convert test data to JSON string
            String jsonData = objectMapper.writeValueAsString(testData);
            logger.debug("Test data converted to JSON, length: {} characters", jsonData.length());

            // Step 2: Generate CMS signature using DSC service
            String cmsSignature = dscSignatureService.signPayload(jsonData);
            logger.debug("CMS signature generated, length: {} characters", cmsSignature.length());

            // Step 3: Encode the original data as Base64 (as per ITD format)
            String base64Data = Base64.getEncoder().encodeToString(jsonData.getBytes("UTF-8"));
            logger.debug("Data encoded to Base64, length: {} characters", base64Data.length());

            // Step 4: Create ITD-compliant payload structure
            Map<String, Object> itdPayload = new HashMap<>();
            itdPayload.put("sign", cmsSignature);
            itdPayload.put("data", base64Data);
            itdPayload.put("eriUserId", eriUserId);

            // Step 5: Convert to JSON string
            String signedPayload = objectMapper.writeValueAsString(itdPayload);
            
            logger.info("Successfully generated ITD-compliant signed payload, total size: {} characters", 
                       signedPayload.length());
            logger.debug("Payload structure - Signature: {} chars, Data: {} chars, ERI User ID: {}", 
                        cmsSignature.length(), base64Data.length(), eriUserId);

            return signedPayload;

        } catch (Exception e) {
            logger.error("Failed to generate ITD-compliant signed payload", e);
            throw new SignatureException("Failed to generate ITD-compliant signed payload: " + e.getMessage(), e);
        }
    }

    /**
     * Generates a sample signed payload with default test data.
     * Uses predefined test data structure for demonstration and testing purposes.
     *
     * @param eriUserId The ERI user ID for the payload
     * @return ITD-compliant signed payload as JSON string
     * @throws SignatureException if payload generation fails
     */
    public String generateDefaultSamplePayload(String eriUserId) throws SignatureException {
        // Create sample test data matching typical tax return structure
        Map<String, Object> sampleData = new HashMap<>();
        sampleData.put("assessmentYear", "2024-25");
        sampleData.put("panNumber", "ABCDE1234F");
        sampleData.put("returnType", "ITR-1");
        sampleData.put("filingDate", "2024-07-31");
        sampleData.put("totalIncome", 500000);
        sampleData.put("taxPayable", 12500);
        
        Map<String, Object> testPayload = new HashMap<>();
        testPayload.put("formData", sampleData);
        testPayload.put("submissionType", "ORIGINAL");
        testPayload.put("acknowledgmentNumber", "TEST" + System.currentTimeMillis());

        return generateSampleSignedPayload(testPayload, eriUserId);
    }

    /**
     * Validates the structure of a signed payload against ITD format requirements.
     * Checks for presence of required fields: sign, data, and eriUserId.
     *
     * @param signedPayload The signed payload JSON string to validate
     * @return true if payload structure is valid, false otherwise
     */
    public boolean validatePayloadStructure(String signedPayload) {
        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> payload = objectMapper.readValue(signedPayload, Map.class);
            
            // Check for required ITD fields
            boolean hasSignature = payload.containsKey("sign") && payload.get("sign") != null;
            boolean hasData = payload.containsKey("data") && payload.get("data") != null;
            boolean hasEriUserId = payload.containsKey("eriUserId") && payload.get("eriUserId") != null;
            
            boolean isValid = hasSignature && hasData && hasEriUserId;
            
            if (isValid) {
                logger.debug("Payload structure validation passed - all required fields present");
            } else {
                logger.warn("Payload structure validation failed - missing fields: signature={}, data={}, eriUserId={}", 
                           hasSignature, hasData, hasEriUserId);
            }
            
            return isValid;
            
        } catch (Exception e) {
            logger.error("Failed to validate payload structure: {}", e.getMessage());
            return false;
        }
    }

    /**
     * Extracts and decodes the data portion from an ITD-compliant signed payload.
     * Decodes the Base64-encoded data field and returns the original JSON.
     *
     * @param signedPayload The ITD-compliant signed payload
     * @return Decoded original data as JSON string
     * @throws Exception if extraction or decoding fails
     */
    public String extractDataFromPayload(String signedPayload) throws Exception {
        @SuppressWarnings("unchecked")
        Map<String, Object> payload = objectMapper.readValue(signedPayload, Map.class);
        
        String base64Data = (String) payload.get("data");
        if (base64Data == null) {
            throw new IllegalArgumentException("No data field found in payload");
        }
        
        byte[] decodedBytes = Base64.getDecoder().decode(base64Data);
        String originalData = new String(decodedBytes, "UTF-8");
        
        logger.debug("Successfully extracted and decoded data from payload, length: {} characters", 
                    originalData.length());
        
        return originalData;
    }

    /**
     * Creates a simple test message payload for basic signature testing.
     * Generates a minimal payload for testing signature functionality.
     *
     * @param message The test message to include in the payload
     * @param eriUserId The ERI user ID for the payload
     * @return ITD-compliant signed payload as JSON string
     * @throws SignatureException if payload generation fails
     */
    public String generateSimpleTestPayload(String message, String eriUserId) throws SignatureException {
        Map<String, Object> simpleData = new HashMap<>();
        simpleData.put("message", message);
        simpleData.put("timestamp", System.currentTimeMillis());
        simpleData.put("testType", "SIGNATURE_VERIFICATION");
        
        return generateSampleSignedPayload(simpleData, eriUserId);
    }
}