package com.taxerp.config;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.validation.annotation.Validated;

/**
 * Configuration properties for DSC (Digital Signature Certificate) operations.
 * Manages keystore path, password, type, and PKCS#11 specific settings.
 */
@Configuration
@ConfigurationProperties(prefix = "dsc")
@Validated
public class DSCConfig {

    /**
     * Keystore configuration properties
     */
    private Keystore keystore = new Keystore();

    /**
     * PKCS#11 specific configuration for USB tokens
     */
    private Pkcs11 pkcs11 = new Pkcs11();

    public Keystore getKeystore() {
        return keystore;
    }

    public void setKeystore(Keystore keystore) {
        this.keystore = keystore;
    }

    public Pkcs11 getPkcs11() {
        return pkcs11;
    }

    public void setPkcs11(Pkcs11 pkcs11) {
        this.pkcs11 = pkcs11;
    }

    /**
     * Keystore configuration for DSC operations
     */
    public static class Keystore {
        
        @NotBlank(message = "DSC keystore path is required")
        private String path;

        @NotBlank(message = "DSC keystore password is required")
        private String password;

        @NotNull(message = "DSC keystore type is required")
        private KeystoreType type = KeystoreType.PKCS12;

        /**
         * Alias for the certificate in the keystore (optional)
         */
        private String alias;

        public String getPath() {
            return path;
        }

        public void setPath(String path) {
            this.path = path;
        }

        public String getPassword() {
            return password;
        }

        public void setPassword(String password) {
            this.password = password;
        }

        public KeystoreType getType() {
            return type;
        }

        public void setType(KeystoreType type) {
            this.type = type;
        }

        public String getAlias() {
            return alias;
        }

        public void setAlias(String alias) {
            this.alias = alias;
        }
    }

    /**
     * PKCS#11 configuration for USB token support
     */
    public static class Pkcs11 {
        
        /**
         * Path to PKCS#11 library (e.g., eToken library)
         */
        private String libraryPath;

        /**
         * Slot ID for the token (optional, auto-detect if not specified)
         */
        private Integer slotId;

        /**
         * Token label (optional)
         */
        private String tokenLabel;

        public String getLibraryPath() {
            return libraryPath;
        }

        public void setLibraryPath(String libraryPath) {
            this.libraryPath = libraryPath;
        }

        public Integer getSlotId() {
            return slotId;
        }

        public void setSlotId(Integer slotId) {
            this.slotId = slotId;
        }

        public String getTokenLabel() {
            return tokenLabel;
        }

        public void setTokenLabel(String tokenLabel) {
            this.tokenLabel = tokenLabel;
        }
    }

    /**
     * Supported keystore types
     */
    public enum KeystoreType {
        PKCS12("PKCS12"),
        PKCS11("PKCS11"),
        JKS("JKS");

        private final String value;

        KeystoreType(String value) {
            this.value = value;
        }

        public String getValue() {
            return value;
        }

        @Override
        public String toString() {
            return value;
        }
    }
}