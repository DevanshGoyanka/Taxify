//PKCS11 SERVICE
package com.taxerp.signer.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.ByteArrayInputStream;
import java.lang.reflect.Constructor;
import java.security.KeyStore;
import java.security.Provider;
import java.security.Security;
import java.util.Enumeration;

/**
 * PKCS#11 Service for USB Token Access
 * Uses reflection to access sun.security.pkcs11.SunPKCS11
 */
@Service
public class Pkcs11Service {
    
    private static final Logger logger = LoggerFactory.getLogger(Pkcs11Service.class);

    @Value("${dsc.token.driver-path:C:\\Windows\\System32\\eps2003csp11v2.dll}")
    private String driverPath;

    @Value("${dsc.token.pin:123456789}")
    private String tokenPin;

    @Value("${dsc.token.alias:MyKey}")
    private String certificateAlias;

    public KeyStore getKeyStore() throws Exception {
        logger.debug("Loading KeyStore from USB token");
        logger.debug("Driver path: {}", driverPath);

        // Create PKCS11 configuration
        String pkcs11Config = String.format(
            "name=ePass2003%nlibrary=%s", 
            driverPath
        );

        // Configure PKCS11 provider (Java 17 style)
        Provider pkcs11Provider = Security.getProvider("SunPKCS11");
        if (pkcs11Provider == null) {
            throw new Exception("SunPKCS11 provider not available");
        }

        // Write config to temp file
        java.io.File configFile = java.io.File.createTempFile("pkcs11-", ".cfg");
        java.nio.file.Files.write(configFile.toPath(), pkcs11Config.getBytes());
        
        try {
            pkcs11Provider = pkcs11Provider.configure(configFile.getAbsolutePath());
            Security.addProvider(pkcs11Provider);
        } finally {
            configFile.delete();
        }

        // Load KeyStore
        KeyStore keyStore = KeyStore.getInstance("PKCS11", pkcs11Provider);
        keyStore.load(null, tokenPin.toCharArray());

        logger.debug("KeyStore loaded successfully");
        
        // Log available aliases for debugging
        Enumeration<String> aliases = keyStore.aliases();
        logger.debug("Available certificate aliases:");
        while (aliases.hasMoreElements()) {
            String alias = aliases.nextElement();
            logger.debug("  - {}", alias);
        }

        return keyStore;
    }

    /**
     * Get certificate alias
     */
    public String getCertificateAlias() {
        return certificateAlias;
    }

    /**
     * Get driver path
     */
    public String getDriverPath() {
        return driverPath;
    }

    /**
     * Get token PIN
     */
    public String getTokenPin() {
        return tokenPin;
    }
}