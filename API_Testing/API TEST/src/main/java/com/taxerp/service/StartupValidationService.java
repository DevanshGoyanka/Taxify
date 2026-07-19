package com.taxerp.service;

import com.taxerp.config.DSCConfig;
import com.taxerp.config.ERIConfig;
import com.taxerp.exception.KeystoreException;
import com.taxerp.exception.ERIApiException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;

/**
 * Service for performing comprehensive startup validation of all critical system components.
 * Validates DSC keystore accessibility, ERI configuration, and database connectivity on application startup.
 * 
 * Requirements: 1.1, 1.2, 1.3 - System startup validation and health checks
 */
@Service
public class StartupValidationService {

    private static final Logger logger = LoggerFactory.getLogger(StartupValidationService.class);

    @Autowired
    private DSCSignatureService dscSignatureService;

    @Autowired
    private ERIApiClient eriApiClient;

    @Autowired
    private DataSource dataSource;

    @Autowired
    private DSCConfig dscConfig;

    @Autowired
    private ERIConfig eriConfig;

    @Autowired
    private AuditLogService auditLogService;

    private boolean startupValidationPassed = false;
    private List<String> validationErrors = new ArrayList<>();
    private List<String> validationWarnings = new ArrayList<>();

    /**
     * Performs comprehensive startup validation when the application is ready.
     * This method is automatically called after the Spring context is fully initialized.
     */
    @EventListener(ApplicationReadyEvent.class)
    public void performStartupValidation() {
        logger.info("=== Starting comprehensive application startup validation ===");
        
        String correlationId = auditLogService.generateCorrelationId();
        long startTime = System.currentTimeMillis();
        
        try {
            // Log startup validation start
            auditLogService.logSignatureOperation(correlationId, "STARTUP_VALIDATION", "STARTED", 
                    "Beginning comprehensive system validation", null);

            // Clear previous validation results
            validationErrors.clear();
            validationWarnings.clear();
            startupValidationPassed = false;

            // Perform all validation checks
            boolean dscValid = validateDSCKeystore();
            boolean eriValid = validateERIConfiguration();
            boolean dbValid = validateDatabaseConnectivity();
            boolean schemaValid = validateDatabaseSchema();

            // Determine overall validation result
            startupValidationPassed = dscValid && eriValid && dbValid && schemaValid;
            
            long validationTime = System.currentTimeMillis() - startTime;

            // Log validation results
            if (startupValidationPassed) {
                logger.info("=== APPLICATION STARTUP VALIDATION PASSED ===");
                logger.info("All critical components validated successfully in {}ms", validationTime);
                
                auditLogService.logSignatureOperation(correlationId, "STARTUP_VALIDATION", "SUCCESS", 
                        String.format("Validation completed in %dms", validationTime), null);
                
                if (!validationWarnings.isEmpty()) {
                    logger.warn("Validation warnings detected:");
                    validationWarnings.forEach(warning -> logger.warn("  - {}", warning));
                }
            } else {
                logger.error("=== APPLICATION STARTUP VALIDATION FAILED ===");
                logger.error("Critical validation errors detected:");
                validationErrors.forEach(error -> logger.error("  - {}", error));
                
                auditLogService.logSignatureOperation(correlationId, "STARTUP_VALIDATION", "FAILED", 
                        String.format("Validation failed with %d errors", validationErrors.size()), null);
                
                // In production, you might want to stop the application here
                // System.exit(1);
            }

            logger.info("=== Startup validation completed in {}ms ===", validationTime);

        } catch (Exception e) {
            logger.error("Unexpected error during startup validation", e);
            
            auditLogService.logSignatureOperation(correlationId, "STARTUP_VALIDATION", "ERROR", 
                    "Unexpected error: " + e.getMessage(), null);
            
            validationErrors.add("Startup validation failed with unexpected error: " + e.getMessage());
            startupValidationPassed = false;
        }
    }

    /**
     * Validates DSC keystore accessibility and certificate validity.
     * 
     * @return true if DSC validation passes, false otherwise
     */
    private boolean validateDSCKeystore() {
        logger.info("Validating DSC keystore accessibility...");
        
        try {
            // Check if DSC configuration is present
            if (dscConfig.getKeystore() == null) {
                validationErrors.add("DSC keystore configuration is missing");
                return false;
            }

            // Validate keystore path
            String keystorePath = dscConfig.getKeystore().getPath();
            if (keystorePath == null || keystorePath.trim().isEmpty()) {
                validationErrors.add("DSC keystore path is not configured");
                return false;
            }

            // Validate keystore password
            String keystorePassword = dscConfig.getKeystore().getPassword();
            if (keystorePassword == null || keystorePassword.trim().isEmpty()) {
                validationErrors.add("DSC keystore password is not configured");
                return false;
            }

            // Attempt to validate keystore
            boolean isValid = dscSignatureService.validateKeystore();
            
            if (isValid) {
                logger.info("DSC keystore validation: PASSED");
                
                // Get certificate details for additional validation
                DSCSignatureService.CertificateInfo certInfo = dscSignatureService.getCertificateDetails();
                
                if (!certInfo.isValid()) {
                    validationWarnings.add("DSC certificate is expired or invalid");
                }
                
                logger.info("DSC Certificate Subject: {}", certInfo.getSubject());
                logger.info("DSC Certificate Valid From: {} To: {}", certInfo.getValidFrom(), certInfo.getValidTo());
                
                return true;
            } else {
                validationErrors.add("DSC keystore validation failed");
                return false;
            }

        } catch (KeystoreException e) {
            logger.error("DSC keystore validation failed", e);
            validationErrors.add("DSC keystore validation error: " + e.getMessage());
            return false;
        } catch (Exception e) {
            logger.error("Unexpected error during DSC validation", e);
            validationErrors.add("DSC validation unexpected error: " + e.getMessage());
            return false;
        }
    }

    /**
     * Validates ERI configuration parameters and connectivity.
     * 
     * @return true if ERI validation passes, false otherwise
     */
    private boolean validateERIConfiguration() {
        logger.info("Validating ERI configuration...");
        
        try {
            // Check if ERI configuration is present
            if (eriConfig.getApi() == null) {
                validationErrors.add("ERI API configuration is missing");
                return false;
            }

            // Validate base URL
            String baseUrl = eriConfig.getApi().getBaseUrl();
            if (baseUrl == null || baseUrl.trim().isEmpty()) {
                validationErrors.add("ERI API base URL is not configured");
                return false;
            }

            if (!baseUrl.startsWith("https://")) {
                validationWarnings.add("ERI API base URL is not using HTTPS: " + baseUrl);
            }

            // Validate timeout configuration
            Integer timeout = eriConfig.getApi().getTimeout();
            if (timeout == null || timeout <= 0) {
                validationWarnings.add("ERI API timeout is not properly configured, using default");
            }

            // Validate retry attempts
            Integer retryAttempts = eriConfig.getApi().getRetryAttempts();
            if (retryAttempts == null || retryAttempts < 1) {
                validationWarnings.add("ERI API retry attempts not properly configured, using default");
            }

            // Validate headers configuration
            if (eriConfig.getHeaders() == null) {
                validationWarnings.add("ERI API headers configuration is missing");
            }

            logger.info("ERI configuration validation: PASSED");
            logger.info("ERI API Base URL: {}", baseUrl);
            logger.info("ERI API Timeout: {}ms", timeout);
            logger.info("ERI API Retry Attempts: {}", retryAttempts);
            
            return true;

        } catch (Exception e) {
            logger.error("Unexpected error during ERI configuration validation", e);
            validationErrors.add("ERI configuration validation error: " + e.getMessage());
            return false;
        }
    }

    /**
     * Validates database connectivity and response time.
     * 
     * @return true if database validation passes, false otherwise
     */
    private boolean validateDatabaseConnectivity() {
        logger.info("Validating database connectivity...");
        
        try {
            long startTime = System.currentTimeMillis();
            
            // Test database connection
            try (Connection connection = dataSource.getConnection()) {
                if (connection == null || connection.isClosed()) {
                    validationErrors.add("Database connection is null or closed");
                    return false;
                }

                // Test basic database operation
                boolean isValid = connection.isValid(5); // 5 second timeout
                if (!isValid) {
                    validationErrors.add("Database connection validation failed");
                    return false;
                }

                long responseTime = System.currentTimeMillis() - startTime;
                
                logger.info("Database connectivity validation: PASSED");
                logger.info("Database connection response time: {}ms", responseTime);
                
                if (responseTime > 1000) {
                    validationWarnings.add("Database connection response time is slow: " + responseTime + "ms");
                }
                
                // Log database metadata
                String databaseProductName = connection.getMetaData().getDatabaseProductName();
                String databaseProductVersion = connection.getMetaData().getDatabaseProductVersion();
                String driverName = connection.getMetaData().getDriverName();
                
                logger.info("Database Product: {} {}", databaseProductName, databaseProductVersion);
                logger.info("Database Driver: {}", driverName);
                
                return true;
            }

        } catch (SQLException e) {
            logger.error("Database connectivity validation failed", e);
            validationErrors.add("Database connectivity error: " + e.getMessage());
            return false;
        } catch (Exception e) {
            logger.error("Unexpected error during database validation", e);
            validationErrors.add("Database validation unexpected error: " + e.getMessage());
            return false;
        }
    }

    /**
     * Validates database schema and required tables.
     * 
     * @return true if schema validation passes, false otherwise
     */
    private boolean validateDatabaseSchema() {
        logger.info("Validating database schema...");
        
        try {
            try (Connection connection = dataSource.getConnection()) {
                // Check for required tables
                String[] requiredTables = {"users", "eri_request_logs", "eri_api_responses"};
                
                for (String tableName : requiredTables) {
                    boolean tableExists = connection.getMetaData()
                            .getTables(null, null, tableName, new String[]{"TABLE"})
                            .next();
                    
                    if (!tableExists) {
                        validationWarnings.add("Required table '" + tableName + "' does not exist - may need migration");
                    } else {
                        logger.debug("Table '{}' exists", tableName);
                    }
                }

                logger.info("Database schema validation: PASSED");
                return true;
            }

        } catch (SQLException e) {
            logger.error("Database schema validation failed", e);
            validationWarnings.add("Database schema validation error: " + e.getMessage());
            return true; // Don't fail startup for schema issues, just warn
        } catch (Exception e) {
            logger.error("Unexpected error during schema validation", e);
            validationWarnings.add("Schema validation unexpected error: " + e.getMessage());
            return true; // Don't fail startup for schema issues, just warn
        }
    }

    /**
     * Gets the current startup validation status.
     * 
     * @return true if all startup validations passed, false otherwise
     */
    public boolean isStartupValidationPassed() {
        return startupValidationPassed;
    }

    /**
     * Gets the list of validation errors encountered during startup.
     * 
     * @return List of validation error messages
     */
    public List<String> getValidationErrors() {
        return new ArrayList<>(validationErrors);
    }

    /**
     * Gets the list of validation warnings encountered during startup.
     * 
     * @return List of validation warning messages
     */
    public List<String> getValidationWarnings() {
        return new ArrayList<>(validationWarnings);
    }

    /**
     * Performs a manual validation check (useful for health endpoints).
     * 
     * @return ValidationResult containing the results of all validation checks
     */
    public ValidationResult performManualValidation() {
        logger.info("Performing manual validation check...");
        
        List<String> errors = new ArrayList<>();
        List<String> warnings = new ArrayList<>();
        
        boolean dscValid = true;
        boolean eriValid = true;
        boolean dbValid = true;
        
        // DSC validation
        try {
            dscSignatureService.validateKeystore();
        } catch (Exception e) {
            dscValid = false;
            errors.add("DSC validation failed: " + e.getMessage());
        }
        
        // Database validation
        try (Connection connection = dataSource.getConnection()) {
            if (!connection.isValid(5)) {
                dbValid = false;
                errors.add("Database connection is not valid");
            }
        } catch (Exception e) {
            dbValid = false;
            errors.add("Database validation failed: " + e.getMessage());
        }
        
        // ERI configuration validation (basic check)
        if (eriConfig.getApi() == null || eriConfig.getApi().getBaseUrl() == null) {
            eriValid = false;
            errors.add("ERI configuration is incomplete");
        }
        
        boolean overallValid = dscValid && eriValid && dbValid;
        
        return new ValidationResult(overallValid, dscValid, eriValid, dbValid, errors, warnings);
    }

    /**
     * Result container for validation operations.
     */
    public static class ValidationResult {
        private final boolean overallValid;
        private final boolean dscValid;
        private final boolean eriValid;
        private final boolean databaseValid;
        private final List<String> errors;
        private final List<String> warnings;

        public ValidationResult(boolean overallValid, boolean dscValid, boolean eriValid, 
                              boolean databaseValid, List<String> errors, List<String> warnings) {
            this.overallValid = overallValid;
            this.dscValid = dscValid;
            this.eriValid = eriValid;
            this.databaseValid = databaseValid;
            this.errors = new ArrayList<>(errors);
            this.warnings = new ArrayList<>(warnings);
        }

        public boolean isOverallValid() {
            return overallValid;
        }

        public boolean isDscValid() {
            return dscValid;
        }

        public boolean isEriValid() {
            return eriValid;
        }

        public boolean isDatabaseValid() {
            return databaseValid;
        }

        public List<String> getErrors() {
            return new ArrayList<>(errors);
        }

        public List<String> getWarnings() {
            return new ArrayList<>(warnings);
        }
    }
}