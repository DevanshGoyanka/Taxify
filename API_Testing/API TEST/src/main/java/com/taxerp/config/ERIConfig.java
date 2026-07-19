package com.taxerp.config;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.validation.annotation.Validated;

import java.util.Map;

/**
 * Configuration properties for ERI (e-Return Intermediary) API integration.
 * Manages ERI API endpoints, timeouts, retry settings, and mandatory ITD headers.
 */
@Configuration
@ConfigurationProperties(prefix = "eri")
@Validated
public class ERIConfig {

    /**
     * ERI API configuration properties
     */
    private Api api = new Api();

    /**
     * Mandatory ITD headers configuration
     */
    private Headers headers = new Headers();

    /**
     * Retry configuration for ERI API calls
     */
    private Retry retry = new Retry();

    public Api getApi() {
        return api;
    }

    public void setApi(Api api) {
        this.api = api;
    }

    public Headers getHeaders() {
        return headers;
    }

    public void setHeaders(Headers headers) {
        this.headers = headers;
    }

    public Retry getRetry() {
        return retry;
    }

    public void setRetry(Retry retry) {
        this.retry = retry;
    }

    /**
     * ERI API endpoint and connection configuration
     */
    public static class Api {
        
        @NotBlank(message = "ERI API base URL is required")
        private String baseUrl = "https://uat.eri.incometax.gov.in";

        @Positive(message = "Connection timeout must be positive")
        private int connectionTimeout = 30000; // 30 seconds

        @Positive(message = "Read timeout must be positive")
        private int readTimeout = 60000; // 60 seconds

        @Positive(message = "Write timeout must be positive")
        private int writeTimeout = 60000; // 60 seconds

        @NotNull(message = "SSL verification flag is required")
        private boolean sslVerification = true;

        public String getBaseUrl() {
            return baseUrl;
        }

        public void setBaseUrl(String baseUrl) {
            this.baseUrl = baseUrl;
        }

        public int getConnectionTimeout() {
            return connectionTimeout;
        }

        public void setConnectionTimeout(int connectionTimeout) {
            this.connectionTimeout = connectionTimeout;
        }

        public int getReadTimeout() {
            return readTimeout;
        }

        public void setReadTimeout(int readTimeout) {
            this.readTimeout = readTimeout;
        }

        public int getWriteTimeout() {
            return writeTimeout;
        }

        public void setWriteTimeout(int writeTimeout) {
            this.writeTimeout = writeTimeout;
        }

        public boolean isSslVerification() {
            return sslVerification;
        }

        public void setSslVerification(boolean sslVerification) {
            this.sslVerification = sslVerification;
        }
    }

    /**
     * Mandatory ITD headers configuration
     */
    public static class Headers {
        
        @NotBlank(message = "User-Agent header is required")
        private String userAgent = "TaxERP-Phase1/1.0";

        @NotBlank(message = "Content-Type header is required")
        private String contentType = "application/json";

        @NotBlank(message = "Accept header is required")
        private String accept = "application/json";

        private String acceptEncoding = "gzip, deflate";

        private String acceptLanguage = "en-US,en;q=0.9";

        private String cacheControl = "no-cache";

        private String connection = "keep-alive";

        /**
         * Additional custom headers for ITD compliance
         */
        private Map<String, String> custom;

        public String getUserAgent() {
            return userAgent;
        }

        public void setUserAgent(String userAgent) {
            this.userAgent = userAgent;
        }

        public String getContentType() {
            return contentType;
        }

        public void setContentType(String contentType) {
            this.contentType = contentType;
        }

        public String getAccept() {
            return accept;
        }

        public void setAccept(String accept) {
            this.accept = accept;
        }

        public String getAcceptEncoding() {
            return acceptEncoding;
        }

        public void setAcceptEncoding(String acceptEncoding) {
            this.acceptEncoding = acceptEncoding;
        }

        public String getAcceptLanguage() {
            return acceptLanguage;
        }

        public void setAcceptLanguage(String acceptLanguage) {
            this.acceptLanguage = acceptLanguage;
        }

        public String getCacheControl() {
            return cacheControl;
        }

        public void setCacheControl(String cacheControl) {
            this.cacheControl = cacheControl;
        }

        public String getConnection() {
            return connection;
        }

        public void setConnection(String connection) {
            this.connection = connection;
        }

        public Map<String, String> getCustom() {
            return custom;
        }

        public void setCustom(Map<String, String> custom) {
            this.custom = custom;
        }
    }

    /**
     * Retry configuration for ERI API calls
     */
    public static class Retry {
        
        @Positive(message = "Max attempts must be positive")
        private int maxAttempts = 3;

        @Positive(message = "Initial delay must be positive")
        private long initialDelayMs = 1000; // 1 second

        @Positive(message = "Max delay must be positive")
        private long maxDelayMs = 10000; // 10 seconds

        private double multiplier = 2.0;

        private boolean enableJitter = true;

        public int getMaxAttempts() {
            return maxAttempts;
        }

        public void setMaxAttempts(int maxAttempts) {
            this.maxAttempts = maxAttempts;
        }

        public long getInitialDelayMs() {
            return initialDelayMs;
        }

        public void setInitialDelayMs(long initialDelayMs) {
            this.initialDelayMs = initialDelayMs;
        }

        public long getMaxDelayMs() {
            return maxDelayMs;
        }

        public void setMaxDelayMs(long maxDelayMs) {
            this.maxDelayMs = maxDelayMs;
        }

        public double getMultiplier() {
            return multiplier;
        }

        public void setMultiplier(double multiplier) {
            this.multiplier = multiplier;
        }

        public boolean isEnableJitter() {
            return enableJitter;
        }

        public void setEnableJitter(boolean enableJitter) {
            this.enableJitter = enableJitter;
        }
    }
}