package com.taxerp.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.taxerp.exception.SignatureException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

/**
 * DSC Signature Service HTTP Client Implementation
 * 
 * Calls the LOCAL DSC signing service running on developer laptop.
 * This is the AWS backend's way to get payloads signed without having USB token access.
 */
@Service
public class DSCSignatureServiceHttpClient implements DSCSignatureService {

    private static final Logger logger = LoggerFactory.getLogger(DSCSignatureServiceHttpClient.class);

    @Value("${dsc.local-signer.url:http://localhost:9090}")
    private String localSignerUrl;

    private final RestTemplate restTemplate = new RestTemplate();
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    public SigningResult signPayload(String jsonPayload) throws SignatureException {
        logger.info("Calling local DSC signer for payload signing");
        
        try {
            String signEndpoint = localSignerUrl + "/sign";
            
            // Prepare request
            Map<String, Object> request = new HashMap<>();
            request.put("payload", jsonPayload);
            
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            
            HttpEntity<Map<String, Object>> entity = new HttpEntity<>(request, headers);
            
            // Call local signer
            logger.debug("Calling local signer: {}", signEndpoint);
            ResponseEntity<Map> response = restTemplate.postForEntity(signEndpoint, entity, Map.class);
            
            if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                Map<String, Object> responseBody = response.getBody();
                
                Boolean success = (Boolean) responseBody.get("success");
                if (Boolean.TRUE.equals(success)) {
                    String signedData = (String) responseBody.get("data");
                    String signature = (String) responseBody.get("signature");
                    String certificate = (String) responseBody.get("certificate");
                    
                    logger.info("Local DSC signing successful");
                    return new SigningResult(signedData, signature, certificate, true, null);
                } else {
                    String error = (String) responseBody.get("error");
                    logger.error("Local DSC signing failed: {}", error);
                    return new SigningResult(null, null, null, false, error);
                }
            } else {
                String error = "Local signer returned HTTP " + response.getStatusCode();
                logger.error(error);
                throw new SignatureException(error);
            }
            
        } catch (Exception e) {
            logger.error("Failed to call local DSC signer", e);
            throw new SignatureException("Local DSC signer unavailable: " + e.getMessage(), e);
        }
    }

    @Override
    public boolean isLocalSignerAvailable() {
        try {
            String healthEndpoint = localSignerUrl + "/health";
            ResponseEntity<String> response = restTemplate.getForEntity(healthEndpoint, String.class);
            return response.getStatusCode().is2xxSuccessful();
        } catch (Exception e) {
            logger.debug("Local signer not available: {}", e.getMessage());
            return false;
        }
    }
}
