package com.taxerp.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxerp.service.AuditLogService;
import com.taxerp.service.ERIApiClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import jakarta.validation.Valid;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * ERI Signed Login Controller
 * Handles pre-signed payloads from local DSC signing service
 * Makes actual ERI API calls from whitelisted AWS IP
 * 
 * This controller runs on AWS EC2 (13.204.49.125)
 * It does NOT perform signing - only accepts pre-signed payloads
 */
@RestController
@RequestMapping("/api/eri")
@CrossOrigin(origins = "*") // Allow calls from local signer
public class ERISignedLoginController {

    private static final Logger logger = LoggerFactory.getLogger(ERISignedLoginController.class);

    @Autowired
    private ERIApiClient eriApiClient;

    @Autowired
    private AuditLogService auditLogService;

    @Autowired
    private ObjectMapper objectMapper;

    @Value("${eri.base-url:https://uatocpservices.incometax.gov.in/v1}")
    private String eriBaseUrl;

    @Value("${eri.auth.client-id}")
    private String clientId;

    @Value("${eri.auth.client-secret}")
    private String clientSecret;

    @Value("${eri.auth.username:ERIP013181}")
    private String eriUsername;

    @Value("${eri.auth.password}")
    private String eriPassword;

    /**
     * ERI Login with Pre-signed Payload
     * Accepts signed payload from local DSC service and calls ITD ERI API
     * 
     * POST /api/eri/login-signed
     * Body: {
     *   "data": "base64_encoded_json",
     *   "signature": "base64_cms_signature", 
     *   "eriUserId": "ERIP011535"
     * }
     */
    @PostMapping("/login-signed")
    public ResponseEntity<Map<String, Object>> loginWithSignedPayload(
            @Valid @RequestBody ERISignedLoginRequest request) {
        
        String correlationId = UUID.randomUUID().toString();
        long startTime = System.currentTimeMillis();
        
        logger.info("ERI signed login request received [{}]", correlationId);
        
        Map<String, Object> response = new HashMap<>();
        response.put("correlationId", correlationId);
        response.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        response.put("service", "AWS ERI Backend");
        response.put("sourceIP", "13.204.49.125");
        
        try {
            // Step 1: Validate request
            validateSignedLoginRequest(request);
            
            // Step 2: Construct ITD ERI login payload
            Map<String, Object> eriPayload = constructERILoginPayload(request);
            
            // Step 3: Log request for audit
            auditLogService.logERIRequest(correlationId, "ERI_LOGIN", 
                    objectMapper.writeValueAsString(eriPayload), request.getEriUserId());
            
            // Step 4: Make ERI API call
            logger.debug("Calling ITD ERI login API [{}]", correlationId);
            ERILoginResponse eriResponse = callERILoginAPI(eriPayload, correlationId);
            
            // Step 5: Process response
            long responseTime = System.currentTimeMillis() - startTime;
            
            if (eriResponse.isSuccess()) {
                response.put("success", true);
                response.put("message", "ERI login successful");
                response.put("sessionId", eriResponse.getSessionId());
                response.put("eriResponse", eriResponse.getRawResponse());
                response.put("responseTimeMs", responseTime);
                
                // Log successful response
                auditLogService.logERIResponse(correlationId, 200, 
                        eriResponse.getRawResponse(), responseTime);
                
                logger.info("ERI login successful [{}] - SessionId: {}, Time: {}ms", 
                           correlationId, eriResponse.getSessionId(), responseTime);
                
                return ResponseEntity.ok(response);
                
            } else {
                response.put("success", false);
                response.put("message", "ERI login failed");
                response.put("error", eriResponse.getErrorMessage());
                response.put("eriErrorCode", eriResponse.getErrorCode());
                response.put("eriResponse", eriResponse.getRawResponse());
                response.put("responseTimeMs", responseTime);
                
                // Log error response
                auditLogService.logERIResponse(correlationId, eriResponse.getHttpStatus(), 
                        eriResponse.getRawResponse(), responseTime);
                
                logger.error("ERI login failed [{}]: {} (Code: {})", 
                            correlationId, eriResponse.getErrorMessage(), eriResponse.getErrorCode());
                
                return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(response);
            }
            
        } catch (ValidationException e) {
            return handleValidationError(e, correlationId, startTime, response);
        } catch (ERIApiException e) {
            return handleERIApiError(e, correlationId, startTime, response);
        } catch (Exception e) {
            return handleGenericError(e, correlationId, startTime, response);
        }
    }

    /**
     * ERI Session Status Check
     * Validates existing ERI session
     * 
     * GET /api/eri/session/{sessionId}/status
     */
    @GetMapping("/session/{sessionId}/status")
    public ResponseEntity<Map<String, Object>> checkSessionStatus(@PathVariable String sessionId) {
        String correlationId = UUID.randomUUID().toString();
        logger.info("ERI session status check [{}] - SessionId: {}", correlationId, sessionId);
        
        Map<String, Object> response = new HashMap<>();
        response.put("correlationId", correlationId);
        response.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        response.put("sessionId", sessionId);
        
        try {
            // Call ERI session validation endpoint
            boolean isValid = eriApiClient.validateSession(sessionId);
            
            response.put("valid", isValid);
            response.put("message", isValid ? "Session is active" : "Session is invalid or expired");
            
            HttpStatus status = isValid ? HttpStatus.OK : HttpStatus.UNAUTHORIZED;
            
            logger.info("Session status check [{}] - Valid: {}", correlationId, isValid);
            return ResponseEntity.status(status).body(response);
            
        } catch (Exception e) {
            logger.error("Session status check failed [{}]: {}", correlationId, e.getMessage(), e);
            
            response.put("valid", false);
            response.put("error", e.getMessage());
            
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
        }
    }

    /**
     * ERI Logout
     * Terminates ERI session
     * 
     * POST /api/eri/logout
     * Body: { "sessionId": "session_id" }
     */
    @PostMapping("/logout")
    public ResponseEntity<Map<String, Object>> logout(@RequestBody Map<String, String> request) {
        String correlationId = UUID.randomUUID().toString();
        String sessionId = request.get("sessionId");
        
        logger.info("ERI logout request [{}] - SessionId: {}", correlationId, sessionId);
        
        Map<String, Object> response = new HashMap<>();
        response.put("correlationId", correlationId);
        response.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        
        try {
            if (sessionId == null || sessionId.trim().isEmpty()) {
                response.put("success", false);
                response.put("error", "SessionId is required");
                return ResponseEntity.badRequest().body(response);
            }
            
            // Call ERI logout API
            boolean success = eriApiClient.logout(sessionId);
            
            response.put("success", success);
            response.put("message", success ? "Logout successful" : "Logout failed");
            
            logger.info("ERI logout [{}] - Success: {}", correlationId, success);
            return ResponseEntity.ok(response);
            
        } catch (Exception e) {
            logger.error("ERI logout failed [{}]: {}", correlationId, e.getMessage(), e);
            
            response.put("success", false);
            response.put("error", e.getMessage());
            
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
        }
    }

    /**
     * Validates the signed login request
     */
    private void validateSignedLoginRequest(ERISignedLoginRequest request) throws ValidationException {
        if (request.getData() == null || request.getData().trim().isEmpty()) {
            throw new ValidationException("Missing or empty 'data' field");
        }
        
        if (request.getSignature() == null || request.getSignature().trim().isEmpty()) {
            throw new ValidationException("Missing or empty 'signature' field");
        }
        
        if (request.getEriUserId() == null || request.getEriUserId().trim().isEmpty()) {
            throw new ValidationException("Missing or empty 'eriUserId' field");
        }
        
        // Validate Base64 format
        try {
            java.util.Base64.getDecoder().decode(request.getData());
            java.util.Base64.getDecoder().decode(request.getSignature());
        } catch (IllegalArgumentException e) {
            throw new ValidationException("Invalid Base64 encoding in data or signature");
        }
    }

    /**
     * Constructs ITD ERI login payload
     */
    private Map<String, Object> constructERILoginPayload(ERISignedLoginRequest request) {
        Map<String, Object> payload = new HashMap<>();
        
        // ITD ERI login format
        payload.put("sign", request.getSignature());
        payload.put("data", request.getData());
        payload.put("eriUserId", request.getEriUserId());
        
        // Add authentication headers data
        Map<String, Object> authData = new HashMap<>();
        authData.put("clientId", clientId);
        authData.put("clientSecret", clientSecret);
        authData.put("username", eriUsername);
        authData.put("password", eriPassword);
        
        payload.put("auth", authData);
        
        return payload;
    }

    /**
     * Makes actual ERI API call
     */
    private ERILoginResponse callERILoginAPI(Map<String, Object> payload, String correlationId) 
            throws ERIApiException {
        
        try {
            RestTemplate restTemplate = new RestTemplate();
            
            // Set headers
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.set("User-Agent", "TaxERP-AWS-Backend/1.0");
            headers.set("X-Correlation-ID", correlationId);
            headers.set("client-id", clientId);
            headers.set("client-secret", clientSecret);
            
            HttpEntity<Map<String, Object>> entity = new HttpEntity<>(payload, headers);
            
            // Make API call
            String loginUrl = eriBaseUrl + "/auth/login";
            logger.debug("Calling ERI login URL: {}", loginUrl);
            
            ResponseEntity<String> response = restTemplate.postForEntity(loginUrl, entity, String.class);
            
            // Parse response
            return parseERILoginResponse(response);
            
        } catch (Exception e) {
            logger.error("ERI API call failed [{}]: {}", correlationId, e.getMessage(), e);
            throw new ERIApiException("ERI API call failed: " + e.getMessage(), e);
        }
    }

    /**
     * Parses ERI login response
     */
    private ERILoginResponse parseERILoginResponse(ResponseEntity<String> response) {
        try {
            String responseBody = response.getBody();
            int httpStatus = response.getStatusCode().value();
            
            if (httpStatus == 200) {
                // Parse successful response
                @SuppressWarnings("unchecked")
                Map<String, Object> responseMap = objectMapper.readValue(responseBody, Map.class);
                
                String sessionId = (String) responseMap.get("sessionId");
                if (sessionId != null) {
                    return new ERILoginResponse(true, sessionId, null, null, httpStatus, responseBody);
                } else {
                    return new ERILoginResponse(false, null, "No sessionId in response", 
                                              "MISSING_SESSION_ID", httpStatus, responseBody);
                }
            } else {
                // Parse error response
                String errorMessage = "ERI login failed with HTTP " + httpStatus;
                String errorCode = "HTTP_" + httpStatus;
                
                try {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> errorMap = objectMapper.readValue(responseBody, Map.class);
                    errorMessage = (String) errorMap.getOrDefault("message", errorMessage);
                    errorCode = (String) errorMap.getOrDefault("errorCode", errorCode);
                } catch (Exception e) {
                    // Use default error message if parsing fails
                }
                
                return new ERILoginResponse(false, null, errorMessage, errorCode, httpStatus, responseBody);
            }
            
        } catch (Exception e) {
            return new ERILoginResponse(false, null, "Failed to parse ERI response: " + e.getMessage(), 
                                      "PARSE_ERROR", 500, response.getBody());
        }
    }

    /**
     * Error handling methods
     */
    private ResponseEntity<Map<String, Object>> handleValidationError(ValidationException e, 
            String correlationId, long startTime, Map<String, Object> response) {
        
        long responseTime = System.currentTimeMillis() - startTime;
        
        response.put("success", false);
        response.put("error", e.getMessage());
        response.put("errorCode", "VALIDATION_ERROR");
        response.put("responseTimeMs", responseTime);
        
        logger.warn("Validation error [{}]: {}", correlationId, e.getMessage());
        return ResponseEntity.badRequest().body(response);
    }

    private ResponseEntity<Map<String, Object>> handleERIApiError(ERIApiException e, 
            String correlationId, long startTime, Map<String, Object> response) {
        
        long responseTime = System.currentTimeMillis() - startTime;
        
        response.put("success", false);
        response.put("error", e.getMessage());
        response.put("errorCode", "ERI_API_ERROR");
        response.put("responseTimeMs", responseTime);
        
        logger.error("ERI API error [{}]: {}", correlationId, e.getMessage(), e);
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(response);
    }

    private ResponseEntity<Map<String, Object>> handleGenericError(Exception e, 
            String correlationId, long startTime, Map<String, Object> response) {
        
        long responseTime = System.currentTimeMillis() - startTime;
        
        response.put("success", false);
        response.put("error", "Internal server error: " + e.getMessage());
        response.put("errorCode", "INTERNAL_ERROR");
        response.put("responseTimeMs", responseTime);
        
        logger.error("Unexpected error [{}]: {}", correlationId, e.getMessage(), e);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
    }

    /**
     * Request DTO for signed login
     */
    public static class ERISignedLoginRequest {
        private String data;
        private String signature;
        private String eriUserId;

        public String getData() { return data; }
        public void setData(String data) { this.data = data; }
        
        public String getSignature() { return signature; }
        public void setSignature(String signature) { this.signature = signature; }
        
        public String getEriUserId() { return eriUserId; }
        public void setEriUserId(String eriUserId) { this.eriUserId = eriUserId; }
    }

    /**
     * ERI login response wrapper
     */
    private static class ERILoginResponse {
        private final boolean success;
        private final String sessionId;
        private final String errorMessage;
        private final String errorCode;
        private final int httpStatus;
        private final String rawResponse;

        public ERILoginResponse(boolean success, String sessionId, String errorMessage, 
                               String errorCode, int httpStatus, String rawResponse) {
            this.success = success;
            this.sessionId = sessionId;
            this.errorMessage = errorMessage;
            this.errorCode = errorCode;
            this.httpStatus = httpStatus;
            this.rawResponse = rawResponse;
        }

        public boolean isSuccess() { return success; }
        public String getSessionId() { return sessionId; }
        public String getErrorMessage() { return errorMessage; }
        public String getErrorCode() { return errorCode; }
        public int getHttpStatus() { return httpStatus; }
        public String getRawResponse() { return rawResponse; }
    }

    /**
     * Custom exceptions
     */
    private static class ValidationException extends Exception {
        public ValidationException(String message) {
            super(message);
        }
    }

    private static class ERIApiException extends Exception {
        public ERIApiException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}