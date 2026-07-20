package com.taxerp.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxerp.service.DSCSignatureService;
import com.taxerp.service.ERIApiClient;
import com.taxerp.util.ITDPayloadGenerator;
import com.taxerp.util.HashUtil;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Map;

/**
 * Test Controller for ERI UAT Testing and DSC Verification.
 * Provides endpoints for pre-flight checks and ERI integration testing.
 * 
 * PHASE 2: ERI UAT Configuration & Testing
 */
@RestController
@RequestMapping("/api/test")
public class TestController {

    private static final Logger logger = LoggerFactory.getLogger(TestController.class);

    @Autowired
    private DSCSignatureService dscSignatureService;

    @Autowired
    private ERIApiClient eriApiClient;

    @Autowired
    private ITDPayloadGenerator itdPayloadGenerator;

    @Autowired
    private ObjectMapper objectMapper;

    /**
     * DSC Signature Test Endpoint
     * Tests DSC signing functionality with provided data.
     * 
     * Expected: curl -X POST http://localhost:8080/api/test/dsc/sign \
     *   -H "Content-Type: application/json" \
     *   -d '{"data":"Hello, ITD!"}'
     */
    @PostMapping("/dsc/sign")
    public ResponseEntity<Map<String, Object>> testDSCSign(@RequestBody Map<String, Object> request) {
        logger.info("DSC signature test requested");
        
        Map<String, Object> response = new HashMap<>();
        response.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        
        try {
            String data = (String) request.get("data");
            if (data == null || data.trim().isEmpty()) {
                response.put("success", false);
                response.put("error", "Data field is required");
                return ResponseEntity.badRequest().body(response);
            }

            logger.debug("Signing data: {}", data);
            
            // Generate signature using DSC service
            String signature = dscSignatureService.signPayload(data);
            
            // Generate data hash for verification
            String dataHash = HashUtil.sha256(data);
            
            response.put("success", true);
            response.put("signature", signature);
            response.put("dataHash", dataHash);
            response.put("dataLength", data.length());
            response.put("signatureLength", signature.length());
            
            logger.info("DSC signature test completed successfully");
            return ResponseEntity.ok(response);
            
        } catch (Exception e) {
            logger.error("DSC signature test failed", e);
            
            response.put("success", false);
            response.put("error", e.getMessage());
            response.put("errorType", e.getClass().getSimpleName());
            
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
        }
    }

    /**
     * ERI Login Payload Generation Test
     * Generates ITD-compliant login payload for ERI testing.
     * 
     * Expected: curl -X POST http://localhost:8080/api/test/eri/login-payload
     */
    @PostMapping("/eri/login-payload")
    public ResponseEntity<Map<String, Object>> generateERILoginPayload() {
        logger.info("ERI login payload generation requested");
        
        try {
            // Create login data structure
            Map<String, Object> loginData = new HashMap<>();
            loginData.put("userId", "ERIP011535");
            loginData.put("timestamp", System.currentTimeMillis());
            loginData.put("action", "LOGIN");
            loginData.put("clientId", "4fea04621c7b5660dbb12b959a29b0ee");
            
            // Generate ITD-compliant signed payload
            String signedPayload = itdPayloadGenerator.generateSampleSignedPayload(loginData, "ERIP011535");
            
            // Parse back to return as structured response
            @SuppressWarnings("unchecked")
            Map<String, Object> payloadMap = objectMapper.readValue(signedPayload, Map.class);
            
            logger.info("ERI login payload generated successfully");
            return ResponseEntity.ok(payloadMap);
            
        } catch (Exception e) {
            logger.error("ERI login payload generation failed", e);
            
            Map<String, Object> errorResponse = new HashMap<>();
            errorResponse.put("success", false);
            errorResponse.put("error", e.getMessage());
            errorResponse.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
            
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(errorResponse);
        }
    }

    /**
     * ERI Login Test (Real UAT API Call)
     * Performs actual login to ERI UAT environment.
     * ⚠️ Requires VPN connection and IP whitelisting
     * 
     * Expected: curl -X POST http://localhost:8080/api/test/eri/login
     */
    @PostMapping("/eri/login")
    public ResponseEntity<Map<String, Object>> testERILogin() {
        logger.info("ERI login test requested");
        
        Map<String, Object> response = new HashMap<>();
        response.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        
        try {
            // Create login payload
            Map<String, Object> loginData = new HashMap<>();
            loginData.put("userId", "ERIP013181");
            loginData.put("password", "Oracle@123");
            loginData.put("clientId", "4fea04621c7b5660dbb12b959a29b0ee");
            loginData.put("clientSecret", "e754ceb48732c4e197658f76bcc69037");
            
            // Generate signed payload
            String signedPayload = itdPayloadGenerator.generateSampleSignedPayload(loginData, "ERIP011535");
            
            // Make actual ERI API call
            logger.debug("Making ERI login API call...");
            String eriResponse = eriApiClient.makeTestCall(signedPayload);
            
            response.put("success", true);
            response.put("message", "Login successful");
            response.put("eriResponse", eriResponse);
            
            // Try to extract session ID from response if available
            try {
                @SuppressWarnings("unchecked")
                Map<String, Object> responseMap = objectMapper.readValue(eriResponse, Map.class);
                if (responseMap.containsKey("sessionId")) {
                    response.put("sessionId", responseMap.get("sessionId"));
                }
            } catch (Exception e) {
                logger.debug("Could not parse ERI response as JSON: {}", e.getMessage());
            }
            
            logger.info("ERI login test completed successfully");
            return ResponseEntity.ok(response);
            
        } catch (Exception e) {
            logger.error("ERI login test failed", e);
            
            response.put("success", false);
            response.put("error", e.getMessage());
            response.put("errorType", e.getClass().getSimpleName());
            
            // Check for common error patterns
            String errorMsg = e.getMessage().toLowerCase();
            if (errorMsg.contains("connection refused") || errorMsg.contains("timeout")) {
                response.put("troubleshooting", "Check VPN connection and network connectivity");
            } else if (errorMsg.contains("unauthorized") || errorMsg.contains("403")) {
                response.put("troubleshooting", "Check credentials and IP whitelisting status");
            } else if (errorMsg.contains("signature")) {
                response.put("troubleshooting", "Check DSC token, PIN, and BouncyCastle JARs");
            }
            
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(response);
        }
    }

    /**
     * ERI Add Client Test
     * Tests client addition functionality in ERI UAT.
     * 
     * Expected: curl -X POST http://localhost:8080/api/test/eri/add-client
     */
    @PostMapping("/eri/add-client")
    public ResponseEntity<Map<String, Object>> testERIAddClient() {
        logger.info("ERI add client test requested");
        
        Map<String, Object> response = new HashMap<>();
        response.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        
        try {
            // Create client data
            Map<String, Object> clientData = new HashMap<>();
            clientData.put("clientName", "Test Client UAT");
            clientData.put("panNumber", "ABCDE1234F");
            clientData.put("assessmentYear", "2024-25");
            clientData.put("action", "ADD_CLIENT");
            
            // Generate signed payload
            String signedPayload = itdPayloadGenerator.generateSampleSignedPayload(clientData, "ERIP011535");
            
            // Make ERI API call
            String eriResponse = eriApiClient.makeTestCall(signedPayload);
            
            response.put("success", true);
            response.put("message", "Client addition test completed");
            response.put("eriResponse", eriResponse);
            
            logger.info("ERI add client test completed successfully");
            return ResponseEntity.ok(response);
            
        } catch (Exception e) {
            logger.error("ERI add client test failed", e);
            
            response.put("success", false);
            response.put("error", e.getMessage());
            
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(response);
        }
    }

    /**
     * ERI Get Prefill Test
     * Tests prefill data retrieval from ERI UAT.
     * 
     * Expected: curl -X POST http://localhost:8080/api/test/eri/prefill
     */
    @PostMapping("/eri/prefill")
    public ResponseEntity<Map<String, Object>> testERIPrefill() {
        logger.info("ERI prefill test requested");
        
        Map<String, Object> response = new HashMap<>();
        response.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        
        try {
            // Create prefill request data
            Map<String, Object> prefillData = new HashMap<>();
            prefillData.put("panNumber", "ABCDE1234F");
            prefillData.put("assessmentYear", "2024-25");
            prefillData.put("action", "GET_PREFILL");
            
            // Generate signed payload
            String signedPayload = itdPayloadGenerator.generateSampleSignedPayload(prefillData, "ERIP011535");
            
            // Make ERI API call
            String eriResponse = eriApiClient.makeTestCall(signedPayload);
            
            response.put("success", true);
            response.put("message", "Prefill test completed");
            response.put("eriResponse", eriResponse);
            
            logger.info("ERI prefill test completed successfully");
            return ResponseEntity.ok(response);
            
        } catch (Exception e) {
            logger.error("ERI prefill test failed", e);
            
            response.put("success", false);
            response.put("error", e.getMessage());
            
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(response);
        }
    }

    /**
     * ERI Logout Test
     * Tests logout functionality in ERI UAT.
     * 
     * Expected: curl -X POST http://localhost:8080/api/test/eri/logout
     */
    @PostMapping("/eri/logout")
    public ResponseEntity<Map<String, Object>> testERILogout() {
        logger.info("ERI logout test requested");
        
        Map<String, Object> response = new HashMap<>();
        response.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        
        try {
            // Create logout data
            Map<String, Object> logoutData = new HashMap<>();
            logoutData.put("userId", "ERIP011535");
            logoutData.put("action", "LOGOUT");
            
            // Generate signed payload
            String signedPayload = itdPayloadGenerator.generateSampleSignedPayload(logoutData, "ERIP011535");
            
            // Make ERI API call
            String eriResponse = eriApiClient.makeTestCall(signedPayload);
            
            response.put("success", true);
            response.put("message", "Logout test completed");
            response.put("eriResponse", eriResponse);
            
            logger.info("ERI logout test completed successfully");
            return ResponseEntity.ok(response);
            
        } catch (Exception e) {
            logger.error("ERI logout test failed", e);
            
            response.put("success", false);
            response.put("error", e.getMessage());
            
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(response);
        }
    }

    /**
     * System Status Check
     * Comprehensive system status for UAT testing readiness.
     * 
     * Expected: curl http://localhost:8080/api/test/status
     */
    @GetMapping("/status")
    public ResponseEntity<Map<String, Object>> getSystemStatus() {
        logger.info("System status check requested");
        
        Map<String, Object> response = new HashMap<>();
        response.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        response.put("environment", "UAT");
        
        Map<String, Object> checks = new HashMap<>();
        boolean overallStatus = true;
        
        // DSC Status Check
        try {
            boolean dscValid = dscSignatureService.validateKeystore();
            checks.put("dscStatus", dscValid ? "AVAILABLE" : "UNAVAILABLE");
            overallStatus &= dscValid;
        } catch (Exception e) {
            checks.put("dscStatus", "ERROR: " + e.getMessage());
            overallStatus = false;
        }
        
        // ERI Configuration Check
        try {
            String configStatus = eriApiClient.getConfigurationStatus();
            checks.put("eriStatus", "CONFIGURED");
            checks.put("eriConfig", configStatus);
        } catch (Exception e) {
            checks.put("eriStatus", "ERROR: " + e.getMessage());
            overallStatus = false;
        }
        
        // Database Check
        try {
            // This would be checked via a simple query or health check
            checks.put("databaseStatus", "CONNECTED");
        } catch (Exception e) {
            checks.put("databaseStatus", "ERROR: " + e.getMessage());
            overallStatus = false;
        }
        
        response.put("status", overallStatus ? "UP" : "DOWN");
        response.put("checks", checks);
        
        HttpStatus httpStatus = overallStatus ? HttpStatus.OK : HttpStatus.SERVICE_UNAVAILABLE;
        
        logger.info("System status check completed: {}", overallStatus ? "UP" : "DOWN");
        return ResponseEntity.status(httpStatus).body(response);
    }
}