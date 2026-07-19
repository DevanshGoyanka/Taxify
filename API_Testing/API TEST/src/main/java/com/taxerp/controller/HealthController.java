package com.taxerp.controller;

import com.taxerp.dto.HealthResponse;
import com.taxerp.service.DSCSignatureService;
import com.taxerp.service.ERIApiClient;
import com.taxerp.service.StartupValidationService;
import com.taxerp.config.ERIConfig;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.env.Environment;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.sql.DataSource;
import java.sql.Connection;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

/**
 * Health monitoring controller for comprehensive system validation.
 * Provides detailed health checks for all critical system components.
 */
@RestController
@RequestMapping("/api/health")
public class HealthController {

    private static final Logger logger = LoggerFactory.getLogger(HealthController.class);

    @Autowired
    private DSCSignatureService dscSignatureService;

    @Autowired
    private ERIApiClient eriApiClient;

    @Autowired
    private ERIConfig eriConfig;

    @Autowired
    private DataSource dataSource;

    @Autowired
    private Environment environment;

    @Autowired
    private StartupValidationService startupValidationService;

    @Value("${spring.application.name:TaxERP}")
    private String applicationName;

    @Value("${spring.application.version:1.0.0}")
    private String applicationVersion;

    /**
     * Comprehensive health check endpoint.
     * Validates all critical system components and returns detailed status.
     *
     * @return HealthResponse with detailed system status
     */
    @GetMapping
    public ResponseEntity<HealthResponse> health() {
        long startTime = System.currentTimeMillis();
        
        logger.info("Starting comprehensive health check");
        
        Map<String, HealthResponse.HealthCheck> checks = new HashMap<>();
        boolean overallHealthy = true;

        // Perform individual health checks
        overallHealthy &= performDSCKeystoreCheck(checks);
        overallHealthy &= performERIConfigurationCheck(checks);
        overallHealthy &= performDatabaseConnectivityCheck(checks);
        overallHealthy &= performERIConnectivityCheck(checks);

        // Calculate total response time
        long totalResponseTime = System.currentTimeMillis() - startTime;

        // Build response
        HealthResponse response = new HealthResponse();
        response.setStatus(overallHealthy ? "UP" : "DOWN");
        response.setResponseTimeMs(totalResponseTime);
        response.setVersion(applicationVersion);
        response.setEnvironment(getActiveProfile());
        response.setChecks(checks);

        // Determine HTTP status based on health
        HttpStatus httpStatus = overallHealthy ? HttpStatus.OK : HttpStatus.SERVICE_UNAVAILABLE;

        logger.info("Health check completed in {}ms with status: {}", 
                   totalResponseTime, response.getStatus());

        return ResponseEntity.status(httpStatus).body(response);
    }

    /**
     * Startup validation status endpoint.
     * Returns the results of the comprehensive startup validation performed when the application started.
     *
     * @return ResponseEntity with startup validation results
     */
    @GetMapping("/startup")
    public ResponseEntity<Map<String, Object>> startupValidation() {
        logger.info("Getting startup validation status");
        
        Map<String, Object> response = new HashMap<>();
        response.put("timestamp", LocalDateTime.now());
        response.put("applicationName", applicationName);
        response.put("version", applicationVersion);
        response.put("environment", getActiveProfile());
        
        // Get startup validation results
        boolean validationPassed = startupValidationService.isStartupValidationPassed();
        response.put("startupValidationPassed", validationPassed);
        response.put("validationErrors", startupValidationService.getValidationErrors());
        response.put("validationWarnings", startupValidationService.getValidationWarnings());
        
        // Perform a fresh validation check
        StartupValidationService.ValidationResult freshValidation = 
                startupValidationService.performManualValidation();
        
        Map<String, Object> currentStatus = new HashMap<>();
        currentStatus.put("overallValid", freshValidation.isOverallValid());
        currentStatus.put("dscValid", freshValidation.isDscValid());
        currentStatus.put("eriValid", freshValidation.isEriValid());
        currentStatus.put("databaseValid", freshValidation.isDatabaseValid());
        currentStatus.put("errors", freshValidation.getErrors());
        currentStatus.put("warnings", freshValidation.getWarnings());
        
        response.put("currentStatus", currentStatus);
        
        // Determine HTTP status
        HttpStatus httpStatus = validationPassed && freshValidation.isOverallValid() ? 
                HttpStatus.OK : HttpStatus.SERVICE_UNAVAILABLE;
        
        logger.info("Startup validation status: startup={}, current={}", 
                   validationPassed, freshValidation.isOverallValid());
        
        return ResponseEntity.status(httpStatus).body(response);
    }

    /**
     * Validates local DSC signer availability (HTTP client check).
     * Requirements: 1.1, 1.2
     */
    private boolean performDSCKeystoreCheck(Map<String, HealthResponse.HealthCheck> checks) {
        long startTime = System.currentTimeMillis();
        String checkName = "local_dsc_signer";
        
        try {
            logger.debug("Checking local DSC signer availability");
            
            boolean isAvailable = dscSignatureService.isLocalSignerAvailable();
            long responseTime = System.currentTimeMillis() - startTime;
            
            if (isAvailable) {
                Map<String, Object> details = new HashMap<>();
                details.put("signerType", "Local USB DSC via HTTP");
                details.put("connection", "Available");
                
                HealthResponse.HealthCheck check = new HealthResponse.HealthCheck(
                    "UP", "Local DSC signer is accessible", responseTime);
                check.setDetails(details);
                checks.put(checkName, check);
                
                logger.debug("Local DSC signer check passed in {}ms", responseTime);
                return true;
            } else {
                HealthResponse.HealthCheck check = new HealthResponse.HealthCheck(
                    "DOWN", "Local DSC signer not available", responseTime);
                check.setError("Cannot reach local signer service");
                checks.put(checkName, check);
                
                logger.warn("Local DSC signer check failed in {}ms", responseTime);
                return false;
            }
            
        } catch (Exception e) {
            long responseTime = System.currentTimeMillis() - startTime;
            
            HealthResponse.HealthCheck check = new HealthResponse.HealthCheck(
                "DOWN", "Local DSC signer check failed", responseTime);
            check.setError(e.getMessage());
            checks.put(checkName, check);
            
            logger.error("Local DSC signer check failed in {}ms: {}", responseTime, e.getMessage(), e);
            return false;
        }
    }

    /**
     * Validates ERI configuration parameters.
     * Requirements: 1.2, 1.3
     */
    private boolean performERIConfigurationCheck(Map<String, HealthResponse.HealthCheck> checks) {
        long startTime = System.currentTimeMillis();
        String checkName = "eri_configuration";
        
        try {
            logger.debug("Performing ERI configuration validation");
            
            // Validate configuration parameters
            boolean configValid = validateERIConfiguration();
            long responseTime = System.currentTimeMillis() - startTime;
            
            if (configValid) {
                Map<String, Object> details = new HashMap<>();
                details.put("baseUrl", eriConfig.getApi().getBaseUrl());
                details.put("connectionTimeout", eriConfig.getApi().getConnectionTimeout());
                details.put("readTimeout", eriConfig.getApi().getReadTimeout());
                details.put("sslVerification", eriConfig.getApi().isSslVerification());
                details.put("maxRetryAttempts", eriConfig.getRetry().getMaxAttempts());
                details.put("userAgent", eriConfig.getHeaders().getUserAgent());
                
                HealthResponse.HealthCheck check = new HealthResponse.HealthCheck(
                    "UP", "ERI configuration is valid", responseTime);
                check.setDetails(details);
                checks.put(checkName, check);
                
                logger.debug("ERI configuration check passed in {}ms", responseTime);
                return true;
            } else {
                HealthResponse.HealthCheck check = new HealthResponse.HealthCheck(
                    "DOWN", "ERI configuration validation failed", responseTime);
                check.setError("Invalid configuration parameters detected");
                checks.put(checkName, check);
                
                logger.warn("ERI configuration check failed in {}ms", responseTime);
                return false;
            }
            
        } catch (Exception e) {
            long responseTime = System.currentTimeMillis() - startTime;
            
            HealthResponse.HealthCheck check = new HealthResponse.HealthCheck(
                "DOWN", "ERI configuration check failed with exception", responseTime);
            check.setError(e.getMessage());
            checks.put(checkName, check);
            
            logger.error("ERI configuration check failed in {}ms: {}", responseTime, e.getMessage(), e);
            return false;
        }
    }

    /**
     * Validates database connectivity with response time measurement.
     * Requirements: 1.3, 1.4
     */
    private boolean performDatabaseConnectivityCheck(Map<String, HealthResponse.HealthCheck> checks) {
        long startTime = System.currentTimeMillis();
        String checkName = "database_connectivity";
        
        try {
            logger.debug("Performing database connectivity check");
            
            // Test database connection
            try (Connection connection = dataSource.getConnection()) {
                // Execute a simple query to verify connectivity
                boolean isValid = connection.isValid(5); // 5 second timeout
                long responseTime = System.currentTimeMillis() - startTime;
                
                if (isValid) {
                    Map<String, Object> details = new HashMap<>();
                    details.put("databaseUrl", connection.getMetaData().getURL());
                    details.put("databaseProduct", connection.getMetaData().getDatabaseProductName());
                    details.put("databaseVersion", connection.getMetaData().getDatabaseProductVersion());
                    details.put("driverName", connection.getMetaData().getDriverName());
                    details.put("driverVersion", connection.getMetaData().getDriverVersion());
                    
                    HealthResponse.HealthCheck check = new HealthResponse.HealthCheck(
                        "UP", "Database connectivity is healthy", responseTime);
                    check.setDetails(details);
                    checks.put(checkName, check);
                    
                    logger.debug("Database connectivity check passed in {}ms", responseTime);
                    return true;
                } else {
                    HealthResponse.HealthCheck check = new HealthResponse.HealthCheck(
                        "DOWN", "Database connection validation failed", responseTime);
                    check.setError("Connection.isValid() returned false");
                    checks.put(checkName, check);
                    
                    logger.warn("Database connectivity check failed in {}ms", responseTime);
                    return false;
                }
            }
            
        } catch (Exception e) {
            long responseTime = System.currentTimeMillis() - startTime;
            
            HealthResponse.HealthCheck check = new HealthResponse.HealthCheck(
                "DOWN", "Database connectivity check failed with exception", responseTime);
            check.setError(e.getMessage());
            checks.put(checkName, check);
            
            logger.error("Database connectivity check failed in {}ms: {}", responseTime, e.getMessage(), e);
            return false;
        }
    }

    /**
     * Validates ERI API connectivity.
     * Requirements: 1.4, 1.5
     */
    private boolean performERIConnectivityCheck(Map<String, HealthResponse.HealthCheck> checks) {
        long startTime = System.currentTimeMillis();
        String checkName = "eri_connectivity";
        
        try {
            logger.debug("Performing ERI API connectivity check");
            
            // Test ERI API connectivity
            boolean isConnected = eriApiClient.validateConnectivity();
            long responseTime = System.currentTimeMillis() - startTime;
            
            if (isConnected) {
                Map<String, Object> details = new HashMap<>();
                details.put("configurationStatus", eriApiClient.getConfigurationStatus());
                details.put("endpoint", eriConfig.getApi().getBaseUrl());
                
                HealthResponse.HealthCheck check = new HealthResponse.HealthCheck(
                    "UP", "ERI API connectivity is healthy", responseTime);
                check.setDetails(details);
                checks.put(checkName, check);
                
                logger.debug("ERI connectivity check passed in {}ms", responseTime);
                return true;
            } else {
                HealthResponse.HealthCheck check = new HealthResponse.HealthCheck(
                    "DOWN", "ERI API connectivity validation failed", responseTime);
                check.setError("ERI API is not accessible");
                checks.put(checkName, check);
                
                logger.warn("ERI connectivity check failed in {}ms", responseTime);
                return false;
            }
            
        } catch (Exception e) {
            long responseTime = System.currentTimeMillis() - startTime;
            
            HealthResponse.HealthCheck check = new HealthResponse.HealthCheck(
                "DOWN", "ERI connectivity check failed with exception", responseTime);
            check.setError(e.getMessage());
            checks.put(checkName, check);
            
            logger.error("ERI connectivity check failed in {}ms: {}", responseTime, e.getMessage(), e);
            return false;
        }
    }

    /**
     * Validates ERI configuration parameters.
     */
    private boolean validateERIConfiguration() {
        // Check required configuration values
        if (eriConfig.getApi().getBaseUrl() == null || eriConfig.getApi().getBaseUrl().trim().isEmpty()) {
            logger.error("ERI base URL is not configured");
            return false;
        }
        
        if (eriConfig.getApi().getConnectionTimeout() <= 0) {
            logger.error("ERI connection timeout is invalid: {}", eriConfig.getApi().getConnectionTimeout());
            return false;
        }
        
        if (eriConfig.getApi().getReadTimeout() <= 0) {
            logger.error("ERI read timeout is invalid: {}", eriConfig.getApi().getReadTimeout());
            return false;
        }
        
        if (eriConfig.getHeaders().getUserAgent() == null || eriConfig.getHeaders().getUserAgent().trim().isEmpty()) {
            logger.error("ERI User-Agent header is not configured");
            return false;
        }
        
        if (eriConfig.getRetry().getMaxAttempts() <= 0) {
            logger.error("ERI max retry attempts is invalid: {}", eriConfig.getRetry().getMaxAttempts());
            return false;
        }
        
        return true;
    }

    /**
     * Gets the active Spring profile.
     */
    private String getActiveProfile() {
        String[] activeProfiles = environment.getActiveProfiles();
        return activeProfiles.length > 0 ? activeProfiles[0] : "default";
    }
}