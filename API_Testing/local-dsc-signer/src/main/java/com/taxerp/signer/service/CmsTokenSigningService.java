package com.taxerp.signer.service;

import org.bouncycastle.cert.X509CertificateHolder;
import org.bouncycastle.cert.jcajce.JcaCertStore;
import org.bouncycastle.cert.jcajce.JcaX509CertificateHolder;
import org.bouncycastle.cms.*;
import org.bouncycastle.cms.jcajce.JcaSignerInfoGeneratorBuilder;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.operator.ContentSigner;
import org.bouncycastle.operator.DigestCalculatorProvider;
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder;
import org.bouncycastle.operator.jcajce.JcaDigestCalculatorProviderBuilder;
import org.bouncycastle.util.Store;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import java.security.*;
import java.security.cert.Certificate;
import java.security.cert.X509Certificate;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Enumeration;
import java.util.List;

@Service
public class CmsTokenSigningService {

    private static final Logger logger = LoggerFactory.getLogger(CmsTokenSigningService.class);
    
    @Autowired
    private Pkcs11Service pkcs11Service;

    @Value("${dsc.token.pin:123456789}")
    private String dscPin;
    
    private KeyStore keyStore;
    private Provider signingProvider;
    private boolean isPkcs11 = false;

    @PostConstruct
    public void init() {
        try {
            // Add BouncyCastle provider for CMS operations
            Security.addProvider(new BouncyCastleProvider());
            logger.info("✅ BouncyCastle provider added");

            // Load Windows-MY or PKCS11 keystore
            loadKeyStore();
            
        } catch (Exception e) {
            logger.error("❌ Initialization failed", e);
            throw new RuntimeException("Failed to initialize signing service", e);
        }
    }

    private void loadKeyStore() throws Exception {
        try {
            logger.info("Attempting to load PKCS11 keystore using driver: {}", pkcs11Service.getDriverPath());
            keyStore = pkcs11Service.getKeyStore();
            signingProvider = keyStore.getProvider();
            isPkcs11 = true;
            logger.info("✅ PKCS11 keystore loaded successfully!");
        } catch (Exception e) {
            logger.warn("⚠️ PKCS11 load failed. Falling back to Windows-MY...", e);
            keyStore = KeyStore.getInstance("Windows-MY");
            keyStore.load(null, dscPin.toCharArray());
            signingProvider = keyStore.getProvider();
            isPkcs11 = false;
            logger.info("✅ Windows-MY keystore loaded successfully!");
        }
        
        if (signingProvider == null) {
            throw new Exception("Signing provider not available");
        }
    }

    /**
     * Sign data with DSC token and return PKCS#7 signature
     */
    public SigningResult signData(byte[] dataBytes) {
        try {
            // Find the signing certificate alias
            String alias = findSigningAlias();
            if (alias == null) {
                return SigningResult.error("No valid signing certificate found in keystore");
            }

            logger.info("Using certificate alias: {}", alias);

            // Get private key and certificate
            PrivateKey privateKey = (PrivateKey) keyStore.getKey(alias, dscPin.toCharArray());
            X509Certificate certificate = (X509Certificate) keyStore.getCertificate(alias);

            if (privateKey == null) {
                return SigningResult.error("Private key not found for alias: " + alias);
            }
            if (certificate == null) {
                return SigningResult.error("Certificate not found for alias: " + alias);
            }

            logger.info("Certificate Subject: {}", certificate.getSubjectX500Principal().getName());
            logger.info("Certificate Valid Until: {}", certificate.getNotAfter());

            // Build certificate chain
            Certificate[] certChain = keyStore.getCertificateChain(alias);
            List<Certificate> certList = new ArrayList<>();
            if (certChain != null && certChain.length > 0) {
                for (Certificate cert : certChain) {
                    certList.add(cert);
                }
                logger.info("Certificate chain length: {}", certChain.length);
            } else {
                certList.add(certificate);
                logger.info("No certificate chain found, using single certificate");
            }

            // Create certificate store
            Store certStore = new JcaCertStore(certList);

            // Create CMS signed data generator
            CMSSignedDataGenerator cmsGenerator = new CMSSignedDataGenerator();

            // CRITICAL: Use the configured provider directly
            ContentSigner contentSigner = new JcaContentSignerBuilder("SHA256withRSA")
                    .setProvider(signingProvider)
                    .build(privateKey);

            // Use BouncyCastle for digest calculation
            DigestCalculatorProvider digestProvider = new JcaDigestCalculatorProviderBuilder()
                    .setProvider("BC")
                    .build();

            // Add signer info
            X509CertificateHolder certHolder = new X509CertificateHolder(certificate.getEncoded());
            cmsGenerator.addSignerInfoGenerator(
                    new JcaSignerInfoGeneratorBuilder(digestProvider)
                            .build(contentSigner, certHolder)
            );

            // Add certificates
            cmsGenerator.addCertificates(certStore);

            // Create CMS signed data (detached signature - data NOT included)
            CMSTypedData cmsData = new CMSProcessableByteArray(dataBytes);
            CMSSignedData cmsSignedData = cmsGenerator.generate(cmsData, false); // false = detached

            // Encode to base64
            byte[] signedBytes = cmsSignedData.getEncoded();
            String signatureBase64 = Base64.getEncoder().encodeToString(signedBytes);

            logger.info("✅ Signing successful");
            logger.info("   Data size: {} bytes", dataBytes.length);
            logger.info("   Signature size: {} bytes (base64: {} chars)", 
                signedBytes.length, signatureBase64.length());

            return SigningResult.success(signatureBase64);

        } catch (Exception e) {
            logger.error("❌ Signing failed", e);
            return SigningResult.error("Signing failed: " + e.getMessage());
        }
    }

    /**
     * Find the first valid signing certificate in the keystore
     */
    private String findSigningAlias() throws Exception {
        Enumeration<String> aliases = keyStore.aliases();
        
        while (aliases.hasMoreElements()) {
            String alias = aliases.nextElement();
            
            if (keyStore.isKeyEntry(alias)) {
                X509Certificate cert = (X509Certificate) keyStore.getCertificate(alias);
                
                if (cert != null) {
                    // Check if certificate is valid
                    try {
                        cert.checkValidity();
                        
                        // Check if it has key usage for digital signature
                        boolean[] keyUsage = cert.getKeyUsage();
                        if (keyUsage != null && keyUsage[0]) { // digitalSignature
                            logger.info("Found valid signing certificate: {}", alias);
                            return alias;
                        }
                    } catch (Exception e) {
                        logger.debug("Certificate {} is not valid or not for signing", alias);
                    }
                }
            }
        }
        
        return null;
    }

    /**
     * Get token status for health check
     */
    public TokenStatus getTokenStatus() {
        try {
            if (keyStore == null) {
                return new TokenStatus(false, "KeyStore not initialized", null);
            }

            Enumeration<String> aliases = keyStore.aliases();
            int certCount = 0;
            
            while (aliases.hasMoreElements()) {
                aliases.nextElement();
                certCount++;
            }

            return new TokenStatus(true, 
                    "USB DSC token accessible via Windows-MY. Found " + certCount + " certificate(s)", 
                    "Windows-MY");
        } catch (Exception e) {
            return new TokenStatus(false, "Error accessing token: " + e.getMessage(), null);
        }
    }

    // Result classes
    public static class SigningResult {
        private final boolean success;
        private final String signature;
        private final String error;

        private SigningResult(boolean success, String signature, String error) {
            this.success = success;
            this.signature = signature;
            this.error = error;
        }

        public static SigningResult success(String signature) {
            return new SigningResult(true, signature, null);
        }

        public static SigningResult error(String error) {
            return new SigningResult(false, null, error);
        }

        public boolean isSuccess() { return success; }
        public String getSignature() { return signature; }
        public String getError() { return error; }
    }

    public static class TokenStatus {
        private final boolean available;
        private final String message;
        private final String driverPath;

        public TokenStatus(boolean available, String message, String driverPath) {
            this.available = available;
            this.message = message;
            this.driverPath = driverPath;
        }

        public boolean isAvailable() { return available; }
        public String getMessage() { return message; }
        public String getDriverPath() { return driverPath; }
    }
}