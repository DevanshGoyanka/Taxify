package com.taxerp.util;

import com.taxerp.config.ERIConfig;
import com.taxerp.exception.ERIApiException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.util.retry.Retry;

import java.time.Duration;
import java.util.concurrent.ThreadLocalRandom;

/**
 * Utility class for implementing retry logic with exponential backoff and jitter.
 * Provides configurable retry mechanisms for ERI API operations.
 */
public class RetryUtil {

    private static final Logger logger = LoggerFactory.getLogger(RetryUtil.class);

    /**
     * Creates a retry specification with exponential backoff and jitter
     *
     * @param retryConfig The retry configuration
     * @param operationName The name of the operation being retried (for logging)
     * @return Configured Retry specification
     */
    public static Retry createRetrySpec(ERIConfig.Retry retryConfig, String operationName) {
        return Retry.backoff(retryConfig.getMaxAttempts() - 1, Duration.ofMillis(retryConfig.getInitialDelayMs()))
                .maxBackoff(Duration.ofMillis(retryConfig.getMaxDelayMs()))
                .jitter(retryConfig.isEnableJitter() ? 0.1 : 0.0)
                .filter(throwable -> isRetryableException(throwable))
                .doBeforeRetry(retrySignal -> {
                    long delay = calculateDelayWithJitter(
                            retryConfig.getInitialDelayMs(),
                            retryConfig.getMultiplier(),
                            retrySignal.totalRetries(),
                            retryConfig.getMaxDelayMs(),
                            retryConfig.isEnableJitter()
                    );
                    
                    logger.warn("Retrying {} (attempt {}/{}) after {}ms delay: {}", 
                            operationName, 
                            retrySignal.totalRetries() + 1, 
                            retryConfig.getMaxAttempts(),
                            delay,
                            retrySignal.failure().getMessage());
                })
                .onRetryExhaustedThrow((retryBackoffSpec, retrySignal) -> {
                    logger.error("Retry exhausted for {} after {} attempts. Final error: {}", 
                            operationName, 
                            retrySignal.totalRetries(),
                            retrySignal.failure().getMessage());
                    return new ERIApiException(
                            String.format("%s failed after %d retry attempts: %s", 
                                    operationName, 
                                    retrySignal.totalRetries(),
                                    retrySignal.failure().getMessage()),
                            "ERI_RETRY_EXHAUSTED",
                            503,
                            retrySignal.failure()
                    );
                });
    }

    /**
     * Determines if an exception is retryable based on error classification
     *
     * @param throwable The exception to evaluate
     * @return true if the exception is retryable, false otherwise
     */
    public static boolean isRetryableException(Throwable throwable) {
        // HTTP response exceptions
        if (throwable instanceof WebClientResponseException) {
            WebClientResponseException webEx = (WebClientResponseException) throwable;
            HttpStatus status = webEx.getStatusCode();
            
            // Retryable HTTP status codes
            if (status.is5xxServerError()) {
                logger.debug("Retryable server error: {}", status);
                return true;
            }
            
            if (status == HttpStatus.REQUEST_TIMEOUT || 
                status == HttpStatus.TOO_MANY_REQUESTS ||
                status == HttpStatus.SERVICE_UNAVAILABLE ||
                status == HttpStatus.BAD_GATEWAY ||
                status == HttpStatus.GATEWAY_TIMEOUT) {
                logger.debug("Retryable client error: {}", status);
                return true;
            }
            
            // Non-retryable client errors (4xx except specific ones above)
            if (status.is4xxClientError()) {
                logger.debug("Non-retryable client error: {}", status);
                return false;
            }
        }
        
        // Network-related exceptions (retryable)
        if (isNetworkException(throwable)) {
            logger.debug("Retryable network exception: {}", throwable.getClass().getSimpleName());
            return true;
        }
        
        // Timeout exceptions (retryable)
        if (isTimeoutException(throwable)) {
            logger.debug("Retryable timeout exception: {}", throwable.getClass().getSimpleName());
            return true;
        }
        
        // Default: non-retryable
        logger.debug("Non-retryable exception: {}", throwable.getClass().getSimpleName());
        return false;
    }

    /**
     * Checks if the exception is network-related
     */
    private static boolean isNetworkException(Throwable throwable) {
        return throwable instanceof java.net.ConnectException ||
               throwable instanceof java.net.UnknownHostException ||
               throwable instanceof java.net.NoRouteToHostException ||
               throwable instanceof java.net.PortUnreachableException ||
               throwable instanceof java.io.IOException;
    }

    /**
     * Checks if the exception is timeout-related
     */
    private static boolean isTimeoutException(Throwable throwable) {
        return throwable instanceof java.net.SocketTimeoutException ||
               throwable instanceof java.util.concurrent.TimeoutException ||
               throwable.getMessage() != null && throwable.getMessage().toLowerCase().contains("timeout");
    }

    /**
     * Calculates delay with exponential backoff and optional jitter
     *
     * @param initialDelayMs Initial delay in milliseconds
     * @param multiplier Exponential backoff multiplier
     * @param attemptNumber Current attempt number (0-based)
     * @param maxDelayMs Maximum delay in milliseconds
     * @param enableJitter Whether to add jitter to the delay
     * @return Calculated delay in milliseconds
     */
    public static long calculateDelayWithJitter(long initialDelayMs, double multiplier, 
                                               long attemptNumber, long maxDelayMs, boolean enableJitter) {
        // Calculate exponential backoff delay
        long delay = (long) (initialDelayMs * Math.pow(multiplier, attemptNumber));
        
        // Cap at maximum delay
        delay = Math.min(delay, maxDelayMs);
        
        // Add jitter if enabled (±10% random variation)
        if (enableJitter) {
            double jitterFactor = 0.9 + (ThreadLocalRandom.current().nextDouble() * 0.2); // 0.9 to 1.1
            delay = (long) (delay * jitterFactor);
        }
        
        return delay;
    }

    /**
     * Gets a human-readable description of retry configuration
     *
     * @param retryConfig The retry configuration
     * @return Configuration description
     */
    public static String getRetryConfigDescription(ERIConfig.Retry retryConfig) {
        return String.format("Retry Config: maxAttempts=%d, initialDelay=%dms, maxDelay=%dms, multiplier=%.1f, jitter=%s",
                retryConfig.getMaxAttempts(),
                retryConfig.getInitialDelayMs(),
                retryConfig.getMaxDelayMs(),
                retryConfig.getMultiplier(),
                retryConfig.isEnableJitter() ? "enabled" : "disabled");
    }

    /**
     * Validates retry configuration parameters
     *
     * @param retryConfig The retry configuration to validate
     * @throws IllegalArgumentException if configuration is invalid
     */
    public static void validateRetryConfig(ERIConfig.Retry retryConfig) {
        if (retryConfig.getMaxAttempts() < 1) {
            throw new IllegalArgumentException("Max attempts must be at least 1");
        }
        
        if (retryConfig.getInitialDelayMs() < 0) {
            throw new IllegalArgumentException("Initial delay must be non-negative");
        }
        
        if (retryConfig.getMaxDelayMs() < retryConfig.getInitialDelayMs()) {
            throw new IllegalArgumentException("Max delay must be greater than or equal to initial delay");
        }
        
        if (retryConfig.getMultiplier() < 1.0) {
            throw new IllegalArgumentException("Multiplier must be at least 1.0");
        }
    }
}