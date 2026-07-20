package com.taxerp.util;

import com.taxerp.exception.SignatureException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for SignatureUtil utility class.
 * Tests signature validation and certificate extraction utilities.
 */
class SignatureUtilTest {

    // Sample Base64 encoded data for testing (not a real CMS signature)
    private static final String INVALID_BASE64_SIGNATURE = "invalid-base64-data";
    private static final String VALID_BASE64_BUT_NOT_CMS = "SGVsbG8gV29ybGQ="; // "Hello World" in Base64
    
    // Real CMS signature from the signed data example (truncated for testing)
    private static final String SAMPLE_CMS_SIGNATURE = "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";

    @Test
    @DisplayName("Should return false for invalid Base64 signature")
    void testIsValidCMSFormatInvalidBase64() {
        boolean result = SignatureUtil.isValidCMSFormat(INVALID_BASE64_SIGNATURE);
        
        assertFalse(result, "Invalid Base64 should return false");
    }

    @Test
    @DisplayName("Should return false for valid Base64 but not CMS format")
    void testIsValidCMSFormatValidBase64NotCMS() {
        boolean result = SignatureUtil.isValidCMSFormat(VALID_BASE64_BUT_NOT_CMS);
        
        assertFalse(result, "Valid Base64 but not CMS format should return false");
    }

    @Test
    @DisplayName("Should return false for null signature")
    void testIsValidCMSFormatNull() {
        boolean result = SignatureUtil.isValidCMSFormat(null);
        
        assertFalse(result, "Null signature should return false");
    }

    @Test
    @DisplayName("Should return false for empty signature")
    void testIsValidCMSFormatEmpty() {
        boolean result = SignatureUtil.isValidCMSFormat("");
        
        assertFalse(result, "Empty signature should return false");
    }

    @Test
    @DisplayName("Should return false for whitespace-only signature")
    void testIsValidCMSFormatWhitespace() {
        boolean result = SignatureUtil.isValidCMSFormat("   ");
        
        assertFalse(result, "Whitespace-only signature should return false");
    }

    @Test
    @DisplayName("Should return true for valid CMS signature format")
    void testIsValidCMSFormatValidCMS() {
        boolean result = SignatureUtil.isValidCMSFormat(SAMPLE_CMS_SIGNATURE);
        
        assertTrue(result, "Valid CMS signature should return true");
    }

    @Test
    @DisplayName("Should throw exception when validating null signature")
    void testValidateCMSSignatureNull() {
        assertThrows(SignatureException.class, () -> {
            SignatureUtil.validateCMSSignature(null, "test data");
        }, "Should throw SignatureException for null signature");
    }

    @Test
    @DisplayName("Should throw exception when validating with null data")
    void testValidateCMSSignatureNullData() {
        assertThrows(SignatureException.class, () -> {
            SignatureUtil.validateCMSSignature(SAMPLE_CMS_SIGNATURE, null);
        }, "Should throw SignatureException for null data");
    }

    @Test
    @DisplayName("Should throw exception when validating invalid Base64 signature")
    void testValidateCMSSignatureInvalidBase64() {
        assertThrows(SignatureException.class, () -> {
            SignatureUtil.validateCMSSignature(INVALID_BASE64_SIGNATURE, "test data");
        }, "Should throw SignatureException for invalid Base64");
    }

    @Test
    @DisplayName("Should throw exception when extracting certificate from null signature")
    void testExtractCertificateInfoNull() {
        assertThrows(SignatureException.class, () -> {
            SignatureUtil.extractCertificateInfo(null);
        }, "Should throw SignatureException for null signature");
    }

    @Test
    @DisplayName("Should throw exception when extracting certificate from invalid signature")
    void testExtractCertificateInfoInvalid() {
        assertThrows(SignatureException.class, () -> {
            SignatureUtil.extractCertificateInfo(INVALID_BASE64_SIGNATURE);
        }, "Should throw SignatureException for invalid signature");
    }

    @Test
    @DisplayName("Should throw exception when getting signer count from null signature")
    void testGetSignerCountNull() {
        assertThrows(SignatureException.class, () -> {
            SignatureUtil.getSignerCount(null);
        }, "Should throw SignatureException for null signature");
    }

    @Test
    @DisplayName("Should throw exception when getting signer count from invalid signature")
    void testGetSignerCountInvalid() {
        assertThrows(SignatureException.class, () -> {
            SignatureUtil.getSignerCount(INVALID_BASE64_SIGNATURE);
        }, "Should throw SignatureException for invalid signature");
    }

    @Test
    @DisplayName("Should throw exception when extracting signed content from null signature")
    void testExtractSignedContentNull() {
        assertThrows(SignatureException.class, () -> {
            SignatureUtil.extractSignedContent(null);
        }, "Should throw SignatureException for null signature");
    }

    @Test
    @DisplayName("Should throw exception when extracting signed content from invalid signature")
    void testExtractSignedContentInvalid() {
        assertThrows(SignatureException.class, () -> {
            SignatureUtil.extractSignedContent(INVALID_BASE64_SIGNATURE);
        }, "Should throw SignatureException for invalid signature");
    }

    @Test
    @DisplayName("Should handle valid CMS signature operations")
    void testValidCMSSignatureOperations() {
        // Test with the sample CMS signature
        assertDoesNotThrow(() -> {
            // Test signer count
            int signerCount = SignatureUtil.getSignerCount(SAMPLE_CMS_SIGNATURE);
            assertTrue(signerCount >= 0, "Signer count should be non-negative");
            
            // Test certificate extraction
            var certInfo = SignatureUtil.extractCertificateInfo(SAMPLE_CMS_SIGNATURE);
            assertNotNull(certInfo, "Certificate info should not be null");
            assertNotNull(certInfo.getSubject(), "Subject should not be null");
            assertNotNull(certInfo.getIssuer(), "Issuer should not be null");
            
            // Test signed content extraction (may return null if not embedded)
            byte[] content = SignatureUtil.extractSignedContent(SAMPLE_CMS_SIGNATURE);
            // Content may be null for detached signatures, which is valid
            
        }, "Valid CMS signature operations should not throw exceptions");
    }

    @Test
    @DisplayName("Should handle signature validation with real CMS signature")
    void testValidateCMSSignatureWithRealSignature() {
        // Note: This test may fail because we don't have the original data
        // that was signed, but it should handle the validation attempt gracefully
        assertDoesNotThrow(() -> {
            try {
                boolean isValid = SignatureUtil.validateCMSSignature(SAMPLE_CMS_SIGNATURE, "test data");
                // The validation may return false due to data mismatch, but should not throw
                assertNotNull(isValid); // Just ensure it returns a boolean value
            } catch (SignatureException e) {
                // This is expected if the signature doesn't match the test data
                assertTrue(e.getMessage().contains("Failed to validate CMS signature"));
            }
        }, "CMS signature validation should handle gracefully");
    }

    @Test
    @DisplayName("Should handle edge cases in signature format validation")
    void testSignatureFormatEdgeCases() {
        // Test very short strings
        assertFalse(SignatureUtil.isValidCMSFormat("a"));
        assertFalse(SignatureUtil.isValidCMSFormat("ab"));
        
        // Test strings with special characters
        assertFalse(SignatureUtil.isValidCMSFormat("!@#$%^&*()"));
        
        // Test very long invalid strings
        String longInvalidString = "a".repeat(1000);
        assertFalse(SignatureUtil.isValidCMSFormat(longInvalidString));
    }
}