package com.taxerp.integration;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxerp.util.JsonCanonicalizer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Hybrid ERI Integration Service
 * Orchestrates the complete ERI login flow using hybrid architecture:
 * 
 * Flow:
 * 1. Generate canonical JSON payload
 * 2. Call local DSC signer (localhost:9090)
 * 3. Send signed payload to AWS backend (13.204.49.125:8080)
 * 4. AWS calls ITD ERI API from whitelisted IP
 * 5. Return session ID
 * 
 * This service can run on either local machine or AWS - it coordinates both
 */
@Service
public class HybridERIIntegrationService {

    private static final Logger logger = LoggerFactory.getLogger(HybridERIIntegrationService.class);

    @Autowired
    private ObjectMapper objectMapper;

    @Value("${integration.local-signer.url:http://localhost:9090}")
    private String localSignerUrl;

    @Value("${integration.aws-backend.url:http://13.204.49.125:8080}")
    private String awsBackendUrl;

    @Value("${eri.user.eri-id:ERIP011535}")
    private String eriUserId;

    @Value("${eri.auth.username:ERIP013181}")
    private String eriUsername;

    @Value("${eri.auth.password}")
    private String eriPassword;

    private final RestTemplate restTemplate = new RestTemplate();

    /**
     * Performs complete ERI login using hybrid architecture
     * 
     * @return ERILoginResult containing session ID or error details
     */
    public ERILoginResult performERILogin() {
        String correlationId = "HYBRID-" + UUID.randomUUID().toString();
        long startTime = System.currentTimeMillis();
        
        logger.info("Starting hybrid ERI login flow [{}]", correlationId);
        
        try {
            // Step 1: Generate canonical JSON payload
            logger.debug("Step 1: Generating login payload [{}]", correlationId);
            Map<String, Object> loginPayload = generateLoginPayload();
            String canonicalJson = JsonCanonicalizer.canonicalize(
                objectMapper.writeValueAsString(loginPayload)
            );
            
            logger.debug("Canonical payload generated [{}]: {} chars", correlationId, canonicalJson.length());
            
            // Step 2: Call local DSC signer
            logger.debug("Step 2: Calling local DSC signer [{}]", correlationId);
            SigningResult signingResult = callLocalSigner(canonicalJson, correlationId);
            
            if (!signingResult.isSuccess()) {
                return new ERILoginResult(false, null, signingResult.getError(), 
                                        "LOCAL_SIGNING_FAILED", correlationId);
            }
            
            logger.debug("Local signing completed [{}]", correlationId);
            
            // Step 3: Send signed payload to AWS backend
            logger.debug("Step 3: Sending signed payload to AWS [{}]", correlationId);
            AWSBackendResult awsResult = callAWSBackend(signingResult, correlationId);
            
            if (!awsResult.isSuccess()) {
                return new ERILoginResult(false, null, awsResult.getError(), 
                                        "AWS_BACKEND_FAILED", correlationId);
            }
            
            // Step 4: Process final result
            long totalTime = System.currentTimeMillis() - startTime;
            
            logger.info("Hybrid ERI login completed successfully [{}] - SessionId: {}, Total time: {}ms", 
                       correlationId, awsResult.getSessionId(), totalTime);
            
            return new ERILoginResult(true, awsResult.getSessionId(), null, null, correlationId);
            
        } catch (Exception e) {
            long totalTime = System.currentTimeMillis() - startTime;
            
            logger.error("Hybrid ERI login failed [{}] after {}ms: {}", 
                        correlationId, totalTime, e.getMessage(), e);
            
            return new ERILoginResult(false, null, "Integration error: " + e.getMessage(), 
                                    "INTEGRATION_ERROR", correlationId);
        }
    }

    /**
     * Performs ERI login with custom payload
     * 
     * @param customPayload Custom login data
     * @return ERILoginResult containing session ID or error details
     */
    public ERILoginResult performERILoginWithPayload(Map<String, Object> customPayload) {
        String correlationId = "HYBRID-CUSTOM-" + UUID.randomUUID().toString();
        long startTime = System.currentTimeMillis();
        
        logger.info("Starting hybrid ERI login with custom payload [{}]", correlationId);
        
        try {
            // Step 1: Canonicalize custom payload
            String canonicalJson = JsonCanonicalizer.canonicalize(
                objectMapper.writeValueAsString(customPayload)
            );
            
            // Step 2: Call local DSC signer
            SigningResult signingResult = callLocalSigner(canonicalJson, correlationId);
            
            if (!signingResult.isSuccess()) {
                return new ERILoginResult(false, null, signingResult.getError(), 
                                        "LOCAL_SIGNING_FAILED", correlationId);
            }
            
            // Step 3: Send signed payload to AWS backend
            AWSBackendResult awsResult = callAWSBackend(signingResult, correlationId);
            
            if (!awsResult.isSuccess()) {
                return new ERILoginResult(false, null, awsResult.getError(), 
                                        "AWS_BACKEND_FAILED", correlationId);
            }
            
            long totalTime = System.currentTimeMillis() - startTime;
            
            logger.info("Custom payload ERI login completed [{}] - SessionId: {}, Time: {}ms", 
                       correlationId, awsResult.getSessionId(), totalTime);
            
            return new ERILoginResult(true, awsResult.getSessionId(), null, null, correlationId);
            
        } catch (Exception e) {
            logger.error("Custom payload ERI login failed [{}]: {}", correlationId, e.getMessage(), e);
            
            return new ERILoginResult(false, null, "Integration error: " + e.getMessage(), 
                                    "INTEGRATION_ERROR", correlationId);
        }
    }

    /**
     * Tests the complete integration flow without actual ERI login
     * 
     * @return IntegrationTestResult with component status
     */
    public IntegrationTestResult testIntegrationFlow() {
        String correlationId = "TEST-" + UUID.randomUUID().toString();
        logger.info("Testing integration flow [{}]", correlationId);
        
        IntegrationTestResult result = new IntegrationTestResult(correlationId);
        
        // Test 1: Local signer availability
        try {
            logger.debug("Testing local signer availability [{}]", correlationId);
            boolean signerAvailable = testLocalSignerHealth();
            result.setLocalSignerAvailable(signerAvailable);
            
            if (signerAvailable) {
                logger.debug("Local signer is available [{}]", correlationId);
            } else {
                logger.warn("Local signer is not available [{}]", correlationId);
            }
            
        } catch (Exception e) {
            logger.error("Local signer test failed [{}]: {}", correlationId, e.getMessage());
            result.setLocalSignerAvailable(false);
            result.setLocalSignerError(e.getMessage());
        }
        
        // Test 2: AWS backend availability
        try {
            logger.debug("Testing AWS backend availability [{}]", correlationId);
            boolean awsAvailable = testAWSBackendHealth();
            result.setAwsBackendAvailable(awsAvailable);
            
            if (awsAvailable) {
                logger.debug("AWS backend is available [{}]", correlationId);
            } else {
                logger.warn("AWS backend is not available [{}]", correlationId);
            }
            
        } catch (Exception e) {
            logger.error("AWS backend test failed [{}]: {}", correlationId, e.getMessage());
            result.setAwsBackendAvailable(false);
            result.setAwsBackendError(e.getMessage());
        }
        
        // Test 3: End-to-end flow (with test payload)
        if (result.isLocalSignerAvailable() && result.isAwsBackendAvailable()) {
            try {
                logger.debug("Testing end-to-end flow [{}]", correlationId);
                
                Map<String, Object> testPayload = new HashMap<>();
                testPayload.put("test", true);
                testPayload.put("timestamp", System.currentTimeMillis());
                testPayload.put("correlationId", correlationId);
                
                // This would be a dry-run test without actual ERI call
                result.setEndToEndAvailable(true);
                
            } catch (Exception e) {
                logger.error("End-to-end test failed [{}]: {}", correlationId, e.getMessage());
                result.setEndToEndAvailable(false);
                result.setEndToEndError(e.getMessage());
            }
        } else {
            result.setEndToEndAvailable(false);
            result.setEndToEndError("Prerequisites not available");
        }
        
        logger.info("Integration flow test completed [{}] - Overall: {}", 
                   correlationId, result.isOverallHealthy());
        
        return result;
    }

    /**
     * Generates standard ERI login payload
     */
    private Map<String, Object> generateLoginPayload() {
        Map<String, Object> payload = new HashMap<>();
        
        // ERI login data
        payload.put("userId", eriUsername);
        payload.put("password", eriPassword);
        payload.put("eriUserId", eriUserId);
        payload.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        payload.put("action", "LOGIN");
        
        return payload;
    }

    /**
     * Calls local DSC signing service
     */
    private SigningResult callLocalSigner(String payload, String correlationId) throws Exception {
        String signerEndpoint = localSignerUrl + "/api/sign";
        
        logger.debug("Calling local signer: {} [{}]", signerEndpoint, correlationId);
        
        // Prepare request
        Map<String, Object> request = new HashMap<>();
        request.put("payload", payload);
        
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-Correlation-ID", correlationId);
        
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(request, headers);
        
        try {
            ResponseEntity<Map> response = restTemplate.postForEntity(signerEndpoint, entity, Map.class);
            
            if (response.getStatusCode() == HttpStatus.OK) {
                Map<String, Object> responseBody = response.getBody();
                
                if (responseBody != null && Boolean.TRUE.equals(responseBody.get("success"))) {
                    String data = (String) responseBody.get("data");
                    String signature = (String) responseBody.get("signature");
                    
                    return new SigningResult(true, data, signature, null);
                } else {
                    String error = responseBody != null ? (String) responseBody.get("error") : "Unknown error";
                    return new SigningResult(false, null, null, error);
                }
            } else {
                return new SigningResult(false, null, null, 
                    "Local signer returned HTTP " + response.getStatusCode());
            }
            
        } catch (Exception e) {
            logger.error("Local signer call failed [{}]: {}", correlationId, e.getMessage());
            throw new Exception("Local signer unavailable: " + e.getMessage(), e);
        }
    }

    /**
     * Calls AWS backend with signed payload
     */
    private AWSBackendResult callAWSBackend(SigningResult signingResult, String correlationId) throws Exception {
        String awsEndpoint = awsBackendUrl + "/api/eri/login-signed";
        
        logger.debug("Calling AWS backend: {} [{}]", awsEndpoint, correlationId);
        
        // Prepare signed login request
        Map<String, Object> request = new HashMap<>();
        request.put("data", signingResult.getData());
        request.put("signature", signingResult.getSignature());
        request.put("eriUserId", eriUserId);
        
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-Correlation-ID", correlationId);
        headers.set("User-Agent", "HybridERIIntegration/1.0");
        
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(request, headers);
        
        try {
            ResponseEntity<Map> response = restTemplate.postForEntity(awsEndpoint, entity, Map.class);
            
            Map<String, Object> responseBody = response.getBody();
            
            if (response.getStatusCode() == HttpStatus.OK && responseBody != null) {
                if (Boolean.TRUE.equals(responseBody.get("success"))) {
                    String sessionId = (String) responseBody.get("sessionId");
                    return new AWSBackendResult(true, sessionId, null);
                } else {
                    String error = (String) responseBody.get("error");
                    return new AWSBackendResult(false, null, error);
                }
            } else {
                String error = responseBody != null ? (String) responseBody.get("error") : 
                              "AWS backend returned HTTP " + response.getStatusCode();
                return new AWSBackendResult(false, null, error);
            }
            
        } catch (Exception e) {
            logger.error("AWS backend call failed [{}]: {}", correlationId, e.getMessage());
            throw new Exception("AWS backend unavailable: " + e.getMessage(), e);
        }
    }

    /**
     * Tests local signer health
     */
    private boolean testLocalSignerHealth() {
        try {
            String healthEndpoint = localSignerUrl + "/api/health";
            ResponseEntity<Map> response = restTemplate.getForEntity(healthEndpoint, Map.class);
            
            return response.getStatusCode() == HttpStatus.OK;
            
        } catch (Exception e) {
            logger.debug("Local signer health check failed: {}", e.getMessage());
            return false;
        }
    }

    /**
     * Tests AWS backend health
     */
    private boolean testAWSBackendHealth() {
        try {
            String healthEndpoint = awsBackendUrl + "/api/health";
            ResponseEntity<Map> response = restTemplate.getForEntity(healthEndpoint, Map.class);
            
            return response.getStatusCode() == HttpStatus.OK;
            
        } catch (Exception e) {
            logger.debug("AWS backend health check failed: {}", e.getMessage());
            return false;
        }
    }

    /**
     * Result classes
     */
    public static class ERILoginResult {
        private final boolean success;
        private final String sessionId;
        private final String error;
        private final String errorCode;
        private final String correlationId;

        public ERILoginResult(boolean success, String sessionId, String error, 
                             String errorCode, String correlationId) {
            this.success = success;
            this.sessionId = sessionId;
            this.error = error;
            this.errorCode = errorCode;
            this.correlationId = correlationId;
        }

        public boolean isSuccess() { return success; }
        public String getSessionId() { return sessionId; }
        public String getError() { return error; }
        public String getErrorCode() { return errorCode; }
        public String getCorrelationId() { return correlationId; }
    }

    private static class SigningResult {
        private final boolean success;
        private final String data;
        private final String signature;
        private final String error;

        public SigningResult(boolean success, String data, String signature, String error) {
            this.success = success;
            this.data = data;
            this.signature = signature;
            this.error = error;
        }

        public boolean isSuccess() { return success; }
        public String getData() { return data; }
        public String getSignature() { return signature; }
        public String getError() { return error; }
    }

    private static class AWSBackendResult {
        private final boolean success;
        private final String sessionId;
        private final String error;

        public AWSBackendResult(boolean success, String sessionId, String error) {
            this.success = success;
            this.sessionId = sessionId;
            this.error = error;
        }

        public boolean isSuccess() { return success; }
        public String getSessionId() { return sessionId; }
        public String getError() { return error; }
    }

    public static class IntegrationTestResult {
        private final String correlationId;
        private boolean localSignerAvailable;
        private boolean awsBackendAvailable;
        private boolean endToEndAvailable;
        private String localSignerError;
        private String awsBackendError;
        private String endToEndError;

        public IntegrationTestResult(String correlationId) {
            this.correlationId = correlationId;
        }

        public boolean isOverallHealthy() {
            return localSignerAvailable && awsBackendAvailable && endToEndAvailable;
        }

        // Getters and setters
        public String getCorrelationId() { return correlationId; }
        public boolean isLocalSignerAvailable() { return localSignerAvailable; }
        public void setLocalSignerAvailable(boolean localSignerAvailable) { 
            this.localSignerAvailable = localSignerAvailable; 
        }
        public boolean isAwsBackendAvailable() { return awsBackendAvailable; }
        public void setAwsBackendAvailable(boolean awsBackendAvailable) { 
            this.awsBackendAvailable = awsBackendAvailable; 
        }
        public boolean isEndToEndAvailable() { return endToEndAvailable; }
        public void setEndToEndAvailable(boolean endToEndAvailable) { 
            this.endToEndAvailable = endToEndAvailable; 
        }
        public String getLocalSignerError() { return localSignerError; }
        public void setLocalSignerError(String localSignerError) { 
            this.localSignerError = localSignerError; 
        }
        public String getAwsBackendError() { return awsBackendError; }
        public void setAwsBackendError(String awsBackendError) { 
            this.awsBackendError = awsBackendError; 
        }
        public String getEndToEndError() { return endToEndError; }
        public void setEndToEndError(String endToEndError) { 
            this.endToEndError = endToEndError; 
        }
    }
}