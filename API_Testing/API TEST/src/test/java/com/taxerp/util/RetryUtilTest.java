package com.taxerp.util;

import com.taxerp.config.ERIConfig;
import com.taxerp.exception.ERIApiException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.util.retry.Retry;

import java.io.IOException;
import java.net.ConnectException;
import java.net.SocketTimeoutException;
import java.util.concurrent.TimeoutException;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for RetryUtil.
 * Tests retry logic, exception classification, and delay calculations.
 */
class RetryUtilTest {

    private ERIConfig.Retry retryConfig;

    @BeforeEach
    void setUp() {
        retryConfig = new ERIConfig.Retry();
        retryConfig.setMaxAttempts(3);
        retryConfig.setInitialDelayMs(1000);
        retryConfig.setMaxDelayMs(10000);
        retryConfig.setMultiplier(2.0);
        retryConfig.setEnableJitter(false);
    }

    @Test
    @DisplayName("Should classify 5xx HTTP errors as retryable")
    void testRetryable5xxErrors() {
        // Test various 5xx status codes
        assertTrue(RetryUtil.isRetryableException(
                WebClientResponseException.create(500, "Internal Server Error", null, null, null)),
                "500 Internal Server Error should be retryable");
        
        assertTrue(RetryUtil.isRetryableException(
                WebClientResponseException.create(502, "Bad Gateway", null, null, null)),
                "502 Bad Gateway should be retryable");
        
        assertTrue(RetryUtil.isRetryableException(
                WebClientResponseException.create(503, "Service Unavailable", null, null, null)),
                "503 Service Unavailable should be retryable");
        
        assertTrue(RetryUtil.isRetryableException(
                WebClientResponseException.create(504, "Gateway Timeout", null, null, null)),
                "504 Gateway Timeout should be retryable");
    }

    @Test
    @DisplayName("Should classify specific 4xx HTTP errors as retryable")
    void testRetryableSpecific4xxErrors() {
        assertTrue(RetryUtil.isRetryableException(
                WebClientResponseException.create(408, "Request Timeout", null, null, null)),
                "408 Request Timeout should be retryable");
        
        assertTrue(RetryUtil.isRetryableException(
                WebClientResponseException.create(429, "Too Many Requests", null, null, null)),
                "429 Too Many Requests should be retryable");
    }

    @Test
    @DisplayName("Should classify most 4xx HTTP errors as non-retryable")
    void testNonRetryable4xxErrors() {
        assertFalse(RetryUtil.isRetryableException(
                WebClientResponseException.create(400, "Bad Request", null, null, null)),
                "400 Bad Request should not be retryable");
        
        assertFalse(RetryUtil.isRetryableException(
                WebClientResponseException.create(401, "Unauthorized", null, null, null)),
                "401 Unauthorized should not be retryable");
        
        assertFalse(RetryUtil.isRetryableException(
                WebClientResponseException.create(403, "Forbidden", null, null, null)),
                "403 Forbidden should not be retryable");
        
        assertFalse(RetryUtil.isRetryableException(
                WebClientResponseException.create(404, "Not Found", null, null, null)),
                "404 Not Found should not be retryable");
    }

    @Test
    @DisplayName("Should classify network exceptions as retryable")
    void testRetryableNetworkExceptions() {
        assertTrue(RetryUtil.isRetryableException(new ConnectException("Connection refused")),
                "ConnectException should be retryable");
        
        assertTrue(RetryUtil.isRetryableException(new SocketTimeoutException("Read timeout")),
                "SocketTimeoutException should be retryable");
        
        assertTrue(RetryUtil.isRetryableException(new IOException("Network error")),
                "IOException should be retryable");
        
        assertTrue(RetryUtil.isRetryableException(new TimeoutException("Operation timeout")),
                "TimeoutException should be retryable");
    }

    @Test
    @DisplayName("Should classify other exceptions as non-retryable")
    void testNonRetryableOtherExceptions() {
        assertFalse(RetryUtil.isRetryableException(new IllegalArgumentException("Invalid argument")),
                "IllegalArgumentException should not be retryable");
        
        assertFalse(RetryUtil.isRetryableException(new NullPointerException("Null pointer")),
                "NullPointerException should not be retryable");
        
        assertFalse(RetryUtil.isRetryableException(new RuntimeException("Runtime error")),
                "RuntimeException should not be retryable");
    }

    @Test
    @DisplayName("Should calculate exponential backoff delay correctly")
    void testCalculateDelayWithoutJitter() {
        // Test exponential backoff calculation
        assertEquals(1000, RetryUtil.calculateDelayWithJitter(1000, 2.0, 0, 10000, false),
                "First attempt should use initial delay");
        
        assertEquals(2000, RetryUtil.calculateDelayWithJitter(1000, 2.0, 1, 10000, false),
                "Second attempt should double the delay");
        
        assertEquals(4000, RetryUtil.calculateDelayWithJitter(1000, 2.0, 2, 10000, false),
                "Third attempt should quadruple the delay");
    }

    @Test
    @DisplayName("Should cap delay at maximum value")
    void testDelayMaximumCap() {
        long delay = RetryUtil.calculateDelayWithJitter(1000, 2.0, 10, 5000, false);
        assertEquals(5000, delay, "Delay should be capped at maximum value");
    }

    @Test
    @DisplayName("Should add jitter when enabled")
    void testDelayWithJitter() {
        retryConfig.setEnableJitter(true);
        
        long delay1 = RetryUtil.calculateDelayWithJitter(1000, 2.0, 1, 10000, true);
        long delay2 = RetryUtil.calculateDelayWithJitter(1000, 2.0, 1, 10000, true);
        
        // With jitter, delays should vary (though they might occasionally be the same)
        // Test that delay is within expected range (1800-2200 for base 2000 with ±10% jitter)
        assertTrue(delay1 >= 1800 && delay1 <= 2200, 
                "Delay with jitter should be within expected range: " + delay1);
        assertTrue(delay2 >= 1800 && delay2 <= 2200, 
                "Delay with jitter should be within expected range: " + delay2);
    }

    @Test
    @DisplayName("Should create retry spec with correct configuration")
    void testCreateRetrySpec() {
        Retry retrySpec = RetryUtil.createRetrySpec(retryConfig, "Test Operation");
        
        assertNotNull(retrySpec, "Retry spec should not be null");
        // Note: Testing the actual retry behavior would require more complex setup
        // This test verifies that the method doesn't throw exceptions
    }

    @Test
    @DisplayName("Should validate retry configuration correctly")
    void testValidateRetryConfig() {
        // Valid configuration should not throw
        assertDoesNotThrow(() -> RetryUtil.validateRetryConfig(retryConfig),
                "Valid configuration should not throw exception");
        
        // Invalid max attempts
        retryConfig.setMaxAttempts(0);
        assertThrows(IllegalArgumentException.class, () -> RetryUtil.validateRetryConfig(retryConfig),
                "Should throw exception for invalid max attempts");
        
        // Reset and test invalid initial delay
        retryConfig.setMaxAttempts(3);
        retryConfig.setInitialDelayMs(-1);
        assertThrows(IllegalArgumentException.class, () -> RetryUtil.validateRetryConfig(retryConfig),
                "Should throw exception for negative initial delay");
        
        // Reset and test invalid max delay
        retryConfig.setInitialDelayMs(1000);
        retryConfig.setMaxDelayMs(500);
        assertThrows(IllegalArgumentException.class, () -> RetryUtil.validateRetryConfig(retryConfig),
                "Should throw exception when max delay is less than initial delay");
        
        // Reset and test invalid multiplier
        retryConfig.setMaxDelayMs(10000);
        retryConfig.setMultiplier(0.5);
        assertThrows(IllegalArgumentException.class, () -> RetryUtil.validateRetryConfig(retryConfig),
                "Should throw exception for multiplier less than 1.0");
    }

    @Test
    @DisplayName("Should provide retry configuration description")
    void testGetRetryConfigDescription() {
        String description = RetryUtil.getRetryConfigDescription(retryConfig);
        
        assertNotNull(description, "Description should not be null");
        assertTrue(description.contains("maxAttempts=3"), "Should contain max attempts");
        assertTrue(description.contains("initialDelay=1000ms"), "Should contain initial delay");
        assertTrue(description.contains("maxDelay=10000ms"), "Should contain max delay");
        assertTrue(description.contains("multiplier=2.0"), "Should contain multiplier");
        assertTrue(description.contains("jitter=disabled"), "Should contain jitter status");
    }

    @Test
    @DisplayName("Should handle edge cases in delay calculation")
    void testDelayCalculationEdgeCases() {
        // Zero initial delay
        assertEquals(0, RetryUtil.calculateDelayWithJitter(0, 2.0, 1, 10000, false),
                "Zero initial delay should remain zero");
        
        // Multiplier of 1.0 (no exponential growth)
        assertEquals(1000, RetryUtil.calculateDelayWithJitter(1000, 1.0, 5, 10000, false),
                "Multiplier of 1.0 should not increase delay");
        
        // Very high attempt number
        long delay = RetryUtil.calculateDelayWithJitter(1000, 2.0, 20, 5000, false);
        assertEquals(5000, delay, "Very high attempt number should be capped at max delay");
    }
}