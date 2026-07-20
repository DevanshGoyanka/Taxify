package com.taxerp.controller;

import com.taxerp.integration.HybridERIIntegrationService;
import com.taxerp.integration.HybridERIIntegrationService.ERILoginResult;
import com.taxerp.integration.HybridERIIntegrationService.IntegrationTestResult;
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
 * Hybrid Integration Controller
 * Provides endpoints for testing and executing the complete hybrid ERI integration flow
 * 
 * This controller orchestrates the interaction between:
 * - Local DSC signing service (localhost:9090)
 * - AWS ERI backend (13.204.49.125:8080)
 * - ITD ERI API (via AWS)
 */
@RestController
@RequestMapping("/api/integration")
@CrossOrigin(origins = "*")
public class HybridIntegrationController {

    private static final Logger logger = LoggerFactory.getLogger(HybridIntegrationController.class);

    @Autowired
    private HybridERIIntegrationService integrationService;

    /**
     * Execute complete ERI login flow using hybrid architecture
     * 
     * POST /api/integration/eri/login
     * 
     * Flow:
     * 1. Generate canonical JSON payload
     * 2. Call local DSC signer (localhost:9090)
     * 3. Send signed payload to AWS backend (13.204.49.125:8080)
     * 4. AWS calls ITD ERI API from whitelisted IP
     * 5. Return session ID
     */
    @PostMapping("/eri/login")
    public ResponseEntity<Map<String, Object>> performERILogin() {
        logger.info("Hybrid ERI login requested");
        
        Map<String, Object> response = new HashMap<>();
        response.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        response.put("service", "Hybrid ERI Integration");
        response.put("flow", "Local DSC → AWS Backend → ITD ERI");
        
        try {
            ERILoginResult result = integrationService.performERILogin();
            
            response.put("correlationId", result.getCorrelationId());
            response.put("success", result.isSuccess());
            
            if (result.isSuccess()) {
                response.put("sessionId", result.getSessionId());
                response.put("message", "ERI login successful via hybrid architecture");
                
                logger.info("Hybrid ERI login successful - SessionId: {} [{}]", 
                           result.getSessionId(), result.getCorrelationId());
                
                return ResponseEntity.ok(response);
                
            } else {
                response.put("error", result.getError());
                response.put("errorCode", result.getErrorCode());
                response.put("message", "ERI login failed");
                
                logger.error("Hybrid ERI login failed: {} [{}]", 
                            result.getError(), result.getCorrelationId());
                
                return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(response);
            }
            
        } catch (Exception e) {
            logger.error("Hybrid ERI login error: {}", e.getMessage(), e);
            
            response.put("success", false);
            response.put("error", "Integration error: " + e.getMessage());
            response.put("errorCode", "INTEGRATION_ERROR");
            
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
        }
    }

    /**
     * Execute ERI login with custom payload
     * 
     * POST /api/integration/eri/login-custom
     * Body: { "customData": { ... } }
     */
    @PostMapping("/eri/login-custom")
    public ResponseEntity<Map<String, Object>> performERILoginWithCustomPayload(
            @RequestBody Map<String, Object> request) {
        
        logger.info("Hybrid ERI login with custom payload requested");
        
        Map<String, Object> response = new HashMap<>();
        response.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        response.put("service", "Hybrid ERI Integration");
        response.put("flow", "Custom Payload → Local DSC → AWS Backend → ITD ERI");
        
        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> customPayload = (Map<String, Object>) request.get("customData");
            
            if (customPayload == null) {
                response.put("success", false);
                response.put("error", "Missing 'customData' field in request");
                return ResponseEntity.badRequest().body(response);
            }
            
            ERILoginResult result = integrationService.performERILoginWithPayload(customPayload);
            
            response.put("correlationId", result.getCorrelationId());
            response.put("success", result.isSuccess());
            
            if (result.isSuccess()) {
                response.put("sessionId", result.getSessionId());
                response.put("message", "Custom payload ERI login successful");
                
                logger.info("Custom payload ERI login successful - SessionId: {} [{}]", 
                           result.getSessionId(), result.getCorrelationId());
                
                return ResponseEntity.ok(response);
                
            } else {
                response.put("error", result.getError());
                response.put("errorCode", result.getErrorCode());
                response.put("message", "Custom payload ERI login failed");
                
                logger.error("Custom payload ERI login failed: {} [{}]", 
                            result.getError(), result.getCorrelationId());
                
                return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(response);
            }
            
        } catch (Exception e) {
            logger.error("Custom payload ERI login error: {}", e.getMessage(), e);
            
            response.put("success", false);
            response.put("error", "Integration error: " + e.getMessage());
            response.put("errorCode", "INTEGRATION_ERROR");
            
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
        }
    }

    /**
     * Test complete integration flow without actual ERI login
     * 
     * GET /api/integration/test
     * 
     * Tests:
     * - Local DSC signer availability
     * - AWS backend availability  
     * - End-to-end flow readiness
     */
    @GetMapping("/test")
    public ResponseEntity<Map<String, Object>> testIntegrationFlow() {
        logger.info("Integration flow test requested");
        
        Map<String, Object> response = new HashMap<>();
        response.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        response.put("service", "Hybrid ERI Integration Test");
        
        try {
            IntegrationTestResult result = integrationService.testIntegrationFlow();
            
            response.put("correlationId", result.getCorrelationId());
            response.put("overallHealthy", result.isOverallHealthy());
            
            // Component status
            Map<String, Object> components = new HashMap<>();
            
            Map<String, Object> localSigner = new HashMap<>();
            localSigner.put("available", result.isLocalSignerAvailable());
            localSigner.put("url", "http://localhost:9090");
            if (result.getLocalSignerError() != null) {
                localSigner.put("error", result.getLocalSignerError());
            }
            components.put("localDSCSigner", localSigner);
            
            Map<String, Object> awsBackend = new HashMap<>();
            awsBackend.put("available", result.isAwsBackendAvailable());
            awsBackend.put("url", "http://13.204.49.125:8080");
            if (result.getAwsBackendError() != null) {
                awsBackend.put("error", result.getAwsBackendError());
            }
            components.put("awsBackend", awsBackend);
            
            Map<String, Object> endToEnd = new HashMap<>();
            endToEnd.put("available", result.isEndToEndAvailable());
            if (result.getEndToEndError() != null) {
                endToEnd.put("error", result.getEndToEndError());
            }
            components.put("endToEndFlow", endToEnd);
            
            response.put("components", components);
            
            // Recommendations
            if (result.isOverallHealthy()) {
                response.put("message", "Integration flow is healthy and ready");
                response.put("recommendation", "System ready for ERI UAT testing");
                
                logger.info("Integration flow test passed [{}]", result.getCorrelationId());
                return ResponseEntity.ok(response);
                
            } else {
                response.put("message", "Integration flow has issues");
                response.put("recommendation", "Fix component issues before proceeding");
                
                logger.warn("Integration flow test failed [{}]", result.getCorrelationId());
                return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(response);
            }
            
        } catch (Exception e) {
            logger.error("Integration flow test error: {}", e.getMessage(), e);
            
            response.put("overallHealthy", false);
            response.put("error", "Test execution error: " + e.getMessage());
            response.put("recommendation", "Check system configuration and try again");
            
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
        }
    }

    /**
     * Get integration status and configuration
     * 
     * GET /api/integration/status
     */
    @GetMapping("/status")
    public ResponseEntity<Map<String, Object>> getIntegrationStatus() {
        logger.info("Integration status requested");
        
        Map<String, Object> response = new HashMap<>();
        response.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        response.put("service", "Hybrid ERI Integration");
        
        // Architecture information
        Map<String, Object> architecture = new HashMap<>();
        architecture.put("type", "Hybrid");
        architecture.put("description", "Local DSC signing + AWS ERI backend");
        
        Map<String, Object> components = new HashMap<>();
        components.put("localDSCSigner", Map.of(
            "location", "Windows Laptop",
            "url", "http://localhost:9090",
            "purpose", "USB DSC token signing",
            "port", 9090
        ));
        components.put("awsBackend", Map.of(
            "location", "AWS EC2",
            "url", "http://13.204.49.125:8080", 
            "purpose", "ERI API calls from whitelisted IP",
            "port", 8080
        ));
        components.put("eriAPI", Map.of(
            "location", "ITD Servers",
            "url", "https://uatocpservices.incometax.gov.in/v1",
            "purpose", "Income Tax Department ERI services",
            "environment", "UAT"
        ));
        
        architecture.put("components", components);
        response.put("architecture", architecture);
        
        // Flow information
        Map<String, Object> flow = new HashMap<>();
        flow.put("steps", new String[]{
            "1. Generate canonical JSON payload",
            "2. Sign payload with local DSC service",
            "3. Send signed payload to AWS backend", 
            "4. AWS backend calls ITD ERI API",
            "5. Return session ID to client"
        });
        flow.put("security", new String[]{
            "Private key never leaves USB token",
            "All ERI calls from whitelisted IP only",
            "Comprehensive audit logging",
            "Encrypted communication"
        });
        response.put("flow", flow);
        
        // Prerequisites
        Map<String, Object> prerequisites = new HashMap<>();
        prerequisites.put("hardware", new String[]{
            "USB DSC token inserted",
            "AWS EC2 instance running",
            "Network connectivity"
        });
        prerequisites.put("software", new String[]{
            "Local DSC signer running (port 9090)",
            "AWS backend running (port 8080)",
            "Database accessible"
        });
        prerequisites.put("network", new String[]{
            "VPN connection to ITD",
            "IP 13.204.49.125 whitelisted",
            "Firewall rules configured"
        });
        response.put("prerequisites", prerequisites);
        
        logger.debug("Integration status provided");
        return ResponseEntity.ok(response);
    }

    /**
     * Get integration health summary
     * 
     * GET /api/integration/health
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> getIntegrationHealth() {
        logger.debug("Integration health check requested");
        
        Map<String, Object> response = new HashMap<>();
        response.put("timestamp", LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
        response.put("service", "Hybrid ERI Integration Health");
        
        try {
            // Quick health check
            IntegrationTestResult result = integrationService.testIntegrationFlow();
            
            response.put("status", result.isOverallHealthy() ? "UP" : "DOWN");
            response.put("correlationId", result.getCorrelationId());
            
            Map<String, String> componentStatus = new HashMap<>();
            componentStatus.put("localDSCSigner", result.isLocalSignerAvailable() ? "UP" : "DOWN");
            componentStatus.put("awsBackend", result.isAwsBackendAvailable() ? "UP" : "DOWN");
            componentStatus.put("endToEndFlow", result.isEndToEndAvailable() ? "UP" : "DOWN");
            
            response.put("components", componentStatus);
            
            if (result.isOverallHealthy()) {
                response.put("message", "All integration components healthy");
                return ResponseEntity.ok(response);
            } else {
                response.put("message", "Some integration components unhealthy");
                return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(response);
            }
            
        } catch (Exception e) {
            logger.error("Integration health check failed: {}", e.getMessage());
            
            response.put("status", "DOWN");
            response.put("error", e.getMessage());
            response.put("message", "Health check failed");
            
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
        }
    }
}