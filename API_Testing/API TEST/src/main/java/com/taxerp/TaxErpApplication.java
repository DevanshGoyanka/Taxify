package com.taxerp;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.transaction.annotation.EnableTransactionManagement;

/**
 * Main Spring Boot application class for ERI Tax ERP Phase 1.
 * 
 * This application provides:
 * - Digital Signature Certificate (DSC) integration for tax document signing
 * - ERI API client for Income Tax Department integration
 * - Comprehensive audit logging for compliance
 * - Health monitoring and system validation
 * 
 * Phase 1 focuses on backend foundation with secure DSC operations
 * and ERI API connectivity for UAT testing.
 */
@SpringBootApplication
@EnableJpaRepositories(basePackages = "com.taxerp.repository")
@EnableJpaAuditing
@EnableTransactionManagement
@EnableAsync
@ConfigurationPropertiesScan(basePackages = "com.taxerp.config")
public class TaxErpApplication {

    public static void main(String[] args) {
        // Set system properties for BouncyCastle provider
        System.setProperty("org.bouncycastle.asn1.allow_unsafe_integer", "true");
        
        SpringApplication application = new SpringApplication(TaxErpApplication.class);
        
        // Set default profile if none specified
        application.setAdditionalProfiles("dev");
        
        application.run(args);
    }
}