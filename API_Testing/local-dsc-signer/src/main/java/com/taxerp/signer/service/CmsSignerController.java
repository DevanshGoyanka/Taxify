package com.taxerp.signer.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxerp.signer.service.CmsTokenSigningService;
import com.taxerp.signer.service.CmsTokenSigningService.SigningResult;
import com.taxerp.signer.service.CmsTokenSigningService.TokenStatus;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.Base64;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "*")
public class CmsSignerController {

    private static final Logger logger = LoggerFactory.getLogger(CmsSignerController.class);

    @Autowired
    private CmsTokenSigningService signingService;

    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * Sign payload endpoint
     * Input: { "payload": {...} }
     * Output: { "success": true, "data": "base64", "sign": "base64" }
     */
    @PostMapping("/sign")
    public ResponseEntity<Map<String, Object>> signPayload(@RequestBody Map<String, Object> request) {
        logger.info("=== Sign Request Received ===");

        Object payloadObj = request.get("payload");

        if (payloadObj == null) {
            logger.error("Missing 'payload' field");
            Map<String, Object> errorResponse = new HashMap<>();
            errorResponse.put("success", false);
            errorResponse.put("error", "Missing 'payload' field");
            return ResponseEntity.badRequest().body(errorResponse);
        }

        try {
            // Convert payload to JSON string
            String plainJson;
            
            if (payloadObj instanceof Map) {
                plainJson = objectMapper.writeValueAsString(payloadObj);
            } else if (payloadObj instanceof String) {
                plainJson = (String) payloadObj;
            } else {
                logger.error("Invalid payload type: {}", payloadObj.getClass().getName());
                Map<String, Object> errorResponse = new HashMap<>();
                errorResponse.put("success", false);
                errorResponse.put("error", "Invalid payload type");
                return ResponseEntity.badRequest().body(errorResponse);
            }

            byte[] plainJsonBytes = plainJson.getBytes(StandardCharsets.UTF_8);

            logger.info("Payload to sign: {} bytes", plainJsonBytes.length);
            logger.debug("Payload JSON: {}", plainJson);

            // Sign the data
            SigningResult result = signingService.signData(plainJsonBytes);

            if (!result.isSuccess()) {
                logger.error("Signing failed: {}", result.getError());
                Map<String, Object> errorResponse = new HashMap<>();
                errorResponse.put("success", false);
                errorResponse.put("error", result.getError());
                return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(errorResponse);
            }

            // Prepare response
            String signatureBase64 = result.getSignature();
            String dataBase64 = Base64.getEncoder().encodeToString(plainJsonBytes);

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("success", true);
            response.put("data", dataBase64);
            response.put("sign", signatureBase64);

            logger.info("✅ Signing successful");
            logger.info("   Data: {} chars (base64)", dataBase64.length());
            logger.info("   Signature: {} chars (base64)", signatureBase64.length());
            
            return ResponseEntity.ok(response);

        } catch (Exception e) {
            logger.error("❌ Sign request failed", e);
            Map<String, Object> errorResponse = new HashMap<>();
            errorResponse.put("success", false);
            errorResponse.put("error", e.getMessage());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(errorResponse);
        }
    }

    /**
     * Check token status
     */
    @GetMapping("/token/status")
    public ResponseEntity<Map<String, Object>> getTokenStatus() {
        TokenStatus status = signingService.getTokenStatus();
        
        Map<String, Object> response = new HashMap<>();
        response.put("available", status.isAvailable());
        response.put("message", status.getMessage());
        response.put("driverPath", status.getDriverPath());
        
        return ResponseEntity.ok(response);
    }

    /**
     * Health check
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        Map<String, Object> response = new HashMap<>();
        response.put("status", "UP");
        response.put("timestamp", LocalDateTime.now(ZoneOffset.UTC).toString());
        return ResponseEntity.ok(response);
    }
}