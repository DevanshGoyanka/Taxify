package com.taxerp.controller;

import com.taxerp.dto.ERIRequest;
import com.taxerp.dto.ERIResponse;
import com.taxerp.exception.ERIApiException;
import com.taxerp.exception.SignatureException;
import com.taxerp.service.AuditLogService;
import com.taxerp.service.DSCSignatureService;
import com.taxerp.service.ERIApiClient;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Controller for ERI API testing and UAT verification.
 * Provides endpoints for testing ERI connectivity with digitally signed payloads.
 */
@RestController
@RequestMapping("/api/eri")
public class ERITestController {

    private static final Logger logger = LoggerFactory.getLogger(ERITestController.class);

    @Autowired
    private DSCSignatureService dscSignatureService;

    @Autowired
    private ERIApiClient eriApiClient;

    @Autowired
    private AuditLogService auditLogService;

    @Autowired
    private ObjectMapper objectMapper;

    /**
     * Test endpoint for ERI API connectivity with signed payload.
     * This endpoint accepts test data, signs it using DSC, and makes a test call to ERI API.
     * 
     * Requirements: 3.5 - ERI API testing endpoint for UAT verification
     *
     * @param testRequest The test request containing data to be signed and sent to ERI
     * @return ResponseEntity with test results and audit information
     */
    @PostMapping("/test-call")
    public ResponseEntity<Map<String, Object>> testCall(@Valid @RequestBody ERITestRequest testRequest) {
        String correlationId = UUID.randomUUID().toString();
        long startTime = System.currentTimeMillis();
        
        logger.info("Starting ERI test call with correlation ID: {}", correlationId);
        
        Map<String, Object> response = new HashMap<>();
        response.put("correlationId", correlationId);
        response.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        
        try {
            // Step 1: Validate and prepare test data
            logger.debug("Preparing test data for signing");
            String jsonPayload = objectMapper.writeValueAsString(testRequest.getData());
            
            // Step 2: Sign the payload using DSC
            logger.debug("Signing payload with DSC");
            String signature = dscSignatureService.signPayload(jsonPayload);
            
            // Log signature operation
            auditLogService.logSignatureOperation("ERI_TEST_SIGNING", "SUCCESS");
            
            // Step 3: Create ERI request with signed payload
            ERIRequest eriRequest = new ERIRequest();
            eriRequest.setEriUserId(testRequest.getEriUserId());
            eriRequest.setData(testRequest.getData());
            eriRequest.setSignature(signature);
            eriRequest.setTimestamp(LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
            eriRequest.setCorrelationId(correlationId);
            
            // Step 4: Make test call to ERI API
            logger.debug("Making test call to ERI API");
            ERIResponse eriResponse = eriApiClient.makeTestCall(objectMapper.writeValueAsString(eriRequest));
            
            // Step 5: Calculate response time and build success response
            long responseTime = System.currentTimeMillis() - startTime;
            
            response.put("status", "SUCCESS");
            response.put("message", "ERI test call completed successfully");
            response.put("responseTimeMs", responseTime);
            response.put("eriResponse", eriResponse);
            response.put("signatureGenerated", true);
            response.put("certificateInfo", getCertificateInfo());
            
            logger.info("ERI test call completed successfully in {}ms with correlation ID: {}", 
                       responseTime, correlationId);
            
            return ResponseEntity.ok(response);
            
        } catch (SignatureException e) {
            return handleSignatureError(e, correlationId, startTime, response);
        } catch (ERIApiException e) {
            return handleERIApiError(e, correlationId, startTime, response);
        } catch (Exception e) {
            return handleGenericError(e, correlationId, startTime, response);
        }
    }

    /**
     * Get ERI API status and configuration information.
     * Provides information about ERI connectivity and configuration without making actual API calls.
     *
     * @return ResponseEntity with ERI status information
     */
    @GetMapping("/status")
    public ResponseEntity<Map<String, Object>> getERIStatus() {
        logger.info("Getting ERI API status");
        
        Map<String, Object> response = new HashMap<>();
        response.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        
        try {
            // Get ERI configuration status
            String configStatus = eriApiClient.getConfigurationStatus();
            
            // Validate ERI connectivity
            boolean isConnected = eriApiClient.validateConnectivity();
            
            // Get DSC certificate information
            DSCSignatureService.CertificateInfo certInfo = dscSignatureService.getCertificateDetails();
            
            response.put("status", "SUCCESS");
            response.put("eriConnectivity", isConnected ? "UP" : "DOWN");
            response.put("configurationStatus", configStatus);
            response.put("dscStatus", certInfo.isValid() ? "VALID" : "INVALID");
            response.put("certificateInfo", Map.of(
                "subject", certInfo.getSubject(),
                "issuer", certInfo.getIssuer(),
                "validFrom", certInfo.getValidFrom(),
                "validTo", certInfo.getValidTo(),
                "isValid", certInfo.isValid()
            ));
            
            HttpStatus httpStatus = isConnected && certInfo.isValid() ? HttpStatus.OK : HttpStatus.SERVICE_UNAVAILABLE;
            
            logger.info("ERI status check completed - Connectivity: {}, DSC: {}", 
                       isConnected ? "UP" : "DOWN", certInfo.isValid() ? "VALID" : "INVALID");
            
            return ResponseEntity.status(httpStatus).body(response);
            
        } catch (Exception e) {
            logger.error("Error getting ERI status: {}", e.getMessage(), e);
            
            response.put("status", "ERROR");
            response.put("message", "Failed to get ERI status");
            response.put("error", e.getMessage());
            
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
        }
    }

    /**
     * Handle signature-related errors.
     */
    private ResponseEntity<Map<String, Object>> handleSignatureError(SignatureException e, String correlationId, 
                                                                   long startTime, Map<String, Object> response) {
        long responseTime = System.currentTimeMillis() - startTime;
        
        logger.error("Signature error in ERI test call [{}]: {}", correlationId, e.getMessage(), e);
        
        // Log signature operation failure
        auditLogService.logSignatureOperation("ERI_TEST_SIGNING", "FAILED: " + e.getMessage());
        
        response.put("status", "SIGNATURE_ERROR");
        response.put("message", "Digital signature generation failed");
        response.put("error", e.getMessage());
        response.put("errorCode", "DSC_SIGNATURE_ERROR");
        response.put("responseTimeMs", responseTime);
        response.put("signatureGenerated", false);
        
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(response);
    }

    /**
     * Handle ERI API-related errors.
     */
    private ResponseEntity<Map<String, Object>> handleERIApiError(ERIApiException e, String correlationId, 
                                                                long startTime, Map<String, Object> response) {
        long responseTime = System.currentTimeMillis() - startTime;
        
        logger.error("ERI API error in test call [{}]: {}", correlationId, e.getMessage(), e);
        
        response.put("status", "ERI_API_ERROR");
        response.put("message", "ERI API call failed");
        response.put("error", e.getMessage());
        response.put("errorCode", e.getErrorCode());
        response.put("httpStatus", e.getHttpStatus());
        response.put("responseTimeMs", responseTime);
        response.put("signatureGenerated", true); // Signature was generated but API call failed
        
        HttpStatus httpStatus = HttpStatus.valueOf(e.getHttpStatus());
        return ResponseEntity.status(httpStatus).body(response);
    }

    /**
     * Handle generic errors.
     */
    private ResponseEntity<Map<String, Object>> handleGenericError(Exception e, String correlationId, 
                                                                 long startTime, Map<String, Object> response) {
        long responseTime = System.currentTimeMillis() - startTime;
        
        logger.error("Unexpected error in ERI test call [{}]: {}", correlationId, e.getMessage(), e);
        
        response.put("status", "ERROR");
        response.put("message", "Unexpected error occurred during ERI test call");
        response.put("error", e.getMessage());
        response.put("errorCode", "INTERNAL_ERROR");
        response.put("responseTimeMs", responseTime);
        
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
    }

    /**
     * Get certificate information for response.
     */
    private Map<String, Object> getCertificateInfo() {
        try {
            DSCSignatureService.CertificateInfo certInfo = dscSignatureService.getCertificateDetails();
            return Map.of(
                "subject", certInfo.getSubject(),
                "issuer", certInfo.getIssuer(),
                "serialNumber", certInfo.getSerialNumber(),
                "algorithm", certInfo.getAlgorithm(),
                "keyLength", certInfo.getKeyLength(),
                "isValid", certInfo.isValid()
            );
        } catch (Exception e) {
            logger.warn("Could not retrieve certificate information: {}", e.getMessage());
            return Map.of("error", "Certificate information not available");
        }
    }

    /**
     * Request DTO for ERI test calls.
     */
    public static class ERITestRequest {
        
        @jakarta.validation.constraints.NotBlank(message = "ERI User ID is required")
        private String eriUserId;
        
        @jakarta.validation.constraints.NotNull(message = "Test data is required")
        private Object data;
        
        public ERITestRequest() {
        }
        
        public ERITestRequest(String eriUserId, Object data) {
            this.eriUserId = eriUserId;
            this.data = data;
        }
        
        public String getEriUserId() {
            return eriUserId;
        }
        
        public void setEriUserId(String eriUserId) {
            this.eriUserId = eriUserId;
        }
        
        public Object getData() {
            return data;
        }
        
        public void setData(Object data) {
            this.data = data;
        }
        
        @Override
        public String toString() {
            return "ERITestRequest{" +
                    "eriUserId='" + eriUserId + '\'' +
                    ", data=" + data +
                    '}';
        }
    }
}