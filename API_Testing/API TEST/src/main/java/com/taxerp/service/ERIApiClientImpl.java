package com.taxerp.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxerp.config.ERIConfig;
import com.taxerp.dto.ERIRequest;
import com.taxerp.dto.ERIResponse;
import com.taxerp.exception.ERIApiException;
import com.taxerp.util.RetryUtil;
import com.taxerp.util.ERILoggingUtil;
import com.taxerp.entity.ERIRequestLog;
import com.taxerp.entity.ERIApiResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;
import reactor.util.retry.Retry;

import java.time.Duration;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Map;
import java.util.UUID;

/**
 * Implementation of ERIApiClient for secure communication with ITD ERI endpoints.
 * Provides retry logic, request/response logging, and comprehensive error handling.
 */
@Service
public class ERIApiClientImpl implements ERIApiClient {

    private static final Logger logger = LoggerFactory.getLogger(ERIApiClientImpl.class);
    private static final String TEST_ENDPOINT = "/api/test";
    private static final String SUBMIT_ENDPOINT = "/api/submit";
    private static final String HEALTH_ENDPOINT = "/api/health";

    private final WebClient webClient;
    private final ERIConfig eriConfig;
    private final ObjectMapper objectMapper;
    private final AuditLogService auditLogService;

    @Autowired
    public ERIApiClientImpl(ERIConfig eriConfig, ObjectMapper objectMapper, AuditLogService auditLogService) {
        this.eriConfig = eriConfig;
        this.objectMapper = objectMapper;
        this.auditLogService = auditLogService;
        this.webClient = createWebClient();
    }

    /**
     * Creates and configures the WebClient with ERI-specific settings
     */
    private WebClient createWebClient() {
        return WebClient.builder()
                .baseUrl(eriConfig.getApi().getBaseUrl())
                .defaultHeaders(this::addMandatoryHeaders)
                .codecs(configurer -> configurer.defaultCodecs().maxInMemorySize(10 * 1024 * 1024)) // 10MB
                .build();
    }

    /**
     * Adds mandatory ITD headers to all requests
     */
    private void addMandatoryHeaders(HttpHeaders headers) {
        ERIConfig.Headers headerConfig = eriConfig.getHeaders();
        
        headers.set(HttpHeaders.USER_AGENT, headerConfig.getUserAgent());
        headers.set(HttpHeaders.CONTENT_TYPE, headerConfig.getContentType());
        headers.set(HttpHeaders.ACCEPT, headerConfig.getAccept());
        headers.set(HttpHeaders.ACCEPT_ENCODING, headerConfig.getAcceptEncoding());
        headers.set(HttpHeaders.ACCEPT_LANGUAGE, headerConfig.getAcceptLanguage());
        headers.set(HttpHeaders.CACHE_CONTROL, headerConfig.getCacheControl());
        headers.set(HttpHeaders.CONNECTION, headerConfig.getConnection());

        // Add custom headers if configured
        if (headerConfig.getCustom() != null) {
            headerConfig.getCustom().forEach(headers::set);
        }

        // Add correlation ID for request tracking
        headers.set("X-Correlation-ID", generateCorrelationId());
        headers.set("X-Request-Timestamp", getCurrentTimestamp());
    }

    @Override
    public ERIResponse makeTestCall(String signedPayload) throws ERIApiException {
        logger.info("Making ERI test call with signed payload");
        
        try {
            // Parse the signed payload to create ERIRequest
            ERIRequest request = parseSignedPayload(signedPayload);
            request.setCorrelationId(generateCorrelationId());
            request.setTimestamp(getCurrentTimestamp());

            return executeRequest(TEST_ENDPOINT, request, "ERI Test Call");
            
        } catch (JsonProcessingException e) {
            logger.error("Failed to parse signed payload for test call", e);
            throw new ERIApiException("Invalid signed payload format", "INVALID_PAYLOAD", 400, e);
        }
    }

    @Override
    public ERIResponse submitData(ERIRequest request) throws ERIApiException {
        logger.info("Submitting data to ERI API for correlation ID: {}", request.getCorrelationId());
        
        // Ensure correlation ID and timestamp are set
        if (request.getCorrelationId() == null) {
            request.setCorrelationId(generateCorrelationId());
        }
        if (request.getTimestamp() == null) {
            request.setTimestamp(getCurrentTimestamp());
        }

        return executeRequest(SUBMIT_ENDPOINT, request, "ERI Data Submission");
    }

    @Override
    public boolean validateConnectivity() throws ERIApiException {
        String correlationId = generateCorrelationId();
        String operationName = "ERI Connectivity Validation";
        long startTime = System.currentTimeMillis();
        
        logger.info("Validating ERI API connectivity with correlation ID: {}", correlationId);
        
        try {
            String response = webClient.get()
                    .uri(HEALTH_ENDPOINT)
                    .header("X-Correlation-ID", correlationId)
                    .retrieve()
                    .bodyToMono(String.class)
                    .timeout(Duration.ofMillis(eriConfig.getApi().getConnectionTimeout()))
                    .block();
            
            long responseTime = System.currentTimeMillis() - startTime;
            logger.info("ERI API connectivity validated successfully in {}ms for correlation ID: {}", responseTime, correlationId);
            
            return response != null;
            
        } catch (Exception e) {
            long responseTime = System.currentTimeMillis() - startTime;
            ERILoggingUtil.logERIError(operationName, correlationId, e, responseTime);
            throw new ERIApiException("ERI API connectivity validation failed", "CONNECTIVITY_ERROR", 503, e);
        }
    }

    @Override
    public String getConfigurationStatus() {
        return String.format("ERI API Configuration - Base URL: %s, Timeout: %dms, Max Attempts: %d",
                eriConfig.getApi().getBaseUrl(),
                eriConfig.getApi().getConnectionTimeout(),
                eriConfig.getRetry().getMaxAttempts());
    }

    /**
     * Executes an ERI API request with retry logic and comprehensive error handling
     */
    private ERIResponse executeRequest(String endpoint, ERIRequest request, String operationName) throws ERIApiException {
        String correlationId = request.getCorrelationId();
        long startTime = System.currentTimeMillis();
        
        // Log the request using both existing utility and audit service
        ERILoggingUtil.logERIRequest(request, endpoint, operationName);
        
        // Create audit log entry for the request
        ERIRequestLog requestLog = auditLogService.logERIRequest(correlationId, request, null, endpoint, "POST");
        
        try {
            ERIResponse response = webClient.post()
                    .uri(endpoint)
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(request)
                    .retrieve()
                    .onStatus(HttpStatus::isError, clientResponse -> {
                        return clientResponse.bodyToMono(String.class)
                                .map(errorBody -> {
                                    long errorResponseTime = System.currentTimeMillis() - startTime;
                                    logger.error("ERI API error response for {}: Status={}, Body={}", 
                                            operationName, clientResponse.statusCode(), ERILoggingUtil.maskSensitiveData(errorBody));
                                    
                                    ERIApiException apiException = new ERIApiException(
                                            "ERI API returned error: " + errorBody,
                                            "ERI_API_ERROR",
                                            clientResponse.statusCode().value()
                                    );
                                    
                                    // Log the error
                                    ERILoggingUtil.logERIError(operationName, correlationId, apiException, errorResponseTime);
                                    
                                    return apiException;
                                });
                    })
                    .bodyToMono(ERIResponse.class)
                    .retryWhen(createRetrySpec(operationName))
                    .timeout(Duration.ofMillis(eriConfig.getApi().getReadTimeout()))
                    .block();
            
            long responseTime = System.currentTimeMillis() - startTime;
            
            if (response != null) {
                response.setResponseTimeMs(responseTime);
                response.setCorrelationId(correlationId);
                
                // Log the response using both existing utility and audit service
                ERILoggingUtil.logERIResponse(response, operationName, responseTime);
                
                // Create audit log entry for the response
                auditLogService.logERIResponse(correlationId, response, requestLog, responseTime);
            }
            
            return response;
            
        } catch (WebClientResponseException e) {
            long responseTime = System.currentTimeMillis() - startTime;
            
            ERIApiException apiException = new ERIApiException(
                    String.format("%s failed: %s", operationName, e.getMessage()),
                    "ERI_HTTP_ERROR",
                    e.getStatusCode().value(),
                    e
            );
            
            // Log the error using existing utility
            ERILoggingUtil.logERIError(operationName, correlationId, apiException, responseTime);
            
            // Create error response for audit logging
            ERIResponse errorResponse = new ERIResponse("ERROR", e.getMessage());
            errorResponse.setHttpStatusCode(e.getStatusCode().value());
            errorResponse.setCorrelationId(correlationId);
            errorResponse.setErrorCode("ERI_HTTP_ERROR");
            auditLogService.logERIResponse(correlationId, errorResponse, requestLog, responseTime);
            
            throw apiException;
            
        } catch (JsonProcessingException e) {
            long responseTime = System.currentTimeMillis() - startTime;
            
            ERIApiException apiException = new ERIApiException("Request serialization failed", "SERIALIZATION_ERROR", 400, e);
            
            // Log the error using existing utility
            ERILoggingUtil.logERIError(operationName, correlationId, apiException, responseTime);
            
            // Create error response for audit logging
            ERIResponse errorResponse = new ERIResponse("ERROR", "Request serialization failed");
            errorResponse.setHttpStatusCode(400);
            errorResponse.setCorrelationId(correlationId);
            errorResponse.setErrorCode("SERIALIZATION_ERROR");
            auditLogService.logERIResponse(correlationId, errorResponse, requestLog, responseTime);
            
            throw apiException;
            
        } catch (Exception e) {
            long responseTime = System.currentTimeMillis() - startTime;
            
            ERIApiException apiException = new ERIApiException(
                    String.format("%s failed: %s", operationName, e.getMessage()),
                    "ERI_UNEXPECTED_ERROR",
                    500,
                    e
            );
            
            // Log the error using existing utility
            ERILoggingUtil.logERIError(operationName, correlationId, apiException, responseTime);
            
            // Create error response for audit logging
            ERIResponse errorResponse = new ERIResponse("ERROR", e.getMessage());
            errorResponse.setHttpStatusCode(500);
            errorResponse.setCorrelationId(correlationId);
            errorResponse.setErrorCode("ERI_UNEXPECTED_ERROR");
            auditLogService.logERIResponse(correlationId, errorResponse, requestLog, responseTime);
            
            throw apiException;
        }
    }

    /**
     * Creates retry specification with exponential backoff and jitter
     */
    private Retry createRetrySpec(String operationName) {
        ERIConfig.Retry retryConfig = eriConfig.getRetry();
        
        // Validate retry configuration
        RetryUtil.validateRetryConfig(retryConfig);
        
        logger.debug("Creating retry spec for {}: {}", operationName, RetryUtil.getRetryConfigDescription(retryConfig));
        
        return RetryUtil.createRetrySpec(retryConfig, operationName);
    }

    /**
     * Parses signed payload string into ERIRequest object
     */
    private ERIRequest parseSignedPayload(String signedPayload) throws JsonProcessingException {
        // Assuming signed payload is in JSON format with signature, data, and eriUserId
        Map<String, Object> payloadMap = objectMapper.readValue(signedPayload, Map.class);
        
        ERIRequest request = new ERIRequest();
        request.setEriUserId((String) payloadMap.get("eriUserId"));
        request.setData(payloadMap.get("data"));
        request.setSignature((String) payloadMap.get("signature"));
        
        return request;
    }



    /**
     * Generates a unique correlation ID for request tracking
     */
    private String generateCorrelationId() {
        return auditLogService.generateCorrelationId();
    }

    /**
     * Gets current timestamp in ISO format
     */
    private String getCurrentTimestamp() {
        return LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME);
    }
}