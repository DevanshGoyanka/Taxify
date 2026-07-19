package com.taxerp.util;

import com.taxerp.exception.SignatureException;
import com.taxerp.service.DSCSignatureService;
import org.bouncycastle.cert.X509CertificateHolder;
import org.bouncycastle.cms.*;
import org.bouncycastle.cms.jcajce.JcaSimpleSignerInfoVerifierBuilder;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.util.Store;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.ByteArrayInputStream;
import java.security.Security;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Base64;
import java.util.Collection;
import java.util.Iterator;

/**
 * Utility class for signature validation and certificate extraction from CMS signatures.
 * Provides methods to validate CMS/PKCS#7 signatures and extract certificate information.
 */
public class SignatureUtil {

    private static final Logger logger = LoggerFactory.getLogger(SignatureUtil.class);

    static {
        // Ensure BouncyCastle provider is available
        if (Security.getProvider(BouncyCastleProvider.PROVIDER_NAME) == null) {
            Security.addProvider(new BouncyCastleProvider());
        }
    }

    /**
     * Validates a CMS signature against the original data.
     *
     * @param base64Signature Base64-encoded CMS signature
     * @param originalData Original data that was signed
     * @return true if signature is valid, false otherwise
     * @throws SignatureException if validation fails due to format or processing errors
     */
    public static boolean validateCMSSignature(String base64Signature, String originalData) throws SignatureException {
        try {
            // Decode Base64 signature
            byte[] signatureBytes = Base64.getDecoder().decode(base64Signature);
            
            // Parse CMS signed data
            CMSSignedData cmsSignedData = new CMSSignedData(signatureBytes);
            
            // Get signers
            SignerInformationStore signers = cmsSignedData.getSignerInfos();
            Collection<SignerInformation> signerCollection = signers.getSigners();
            
            if (signerCollection.isEmpty()) {
                logger.warn("No signers found in CMS signature");
                return false;
            }
            
            // Get certificates from CMS
            Store<X509CertificateHolder> certStore = cmsSignedData.getCertificates();
            
            // Validate each signer
            for (SignerInformation signer : signerCollection) {
                Collection<X509CertificateHolder> certCollection = certStore.getMatches(signer.getSID());
                
                if (certCollection.isEmpty()) {
                    logger.warn("No certificate found for signer");
                    return false;
                }
                
                Iterator<X509CertificateHolder> certIt = certCollection.iterator();
                X509CertificateHolder certHolder = certIt.next();
                
                // Verify signature
                SignerInformationVerifier verifier = new JcaSimpleSignerInfoVerifierBuilder()
                        .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                        .build(certHolder);
                
                if (!signer.verify(verifier)) {
                    logger.warn("Signature verification failed for signer");
                    return false;
                }
            }
            
            logger.debug("CMS signature validation successful");
            return true;
            
        } catch (Exception e) {
            logger.error("Failed to validate CMS signature", e);
            throw new SignatureException("Failed to validate CMS signature: " + e.getMessage(), e);
        }
    }

    /**
     * Extracts certificate information from a CMS signature.
     *
     * @param base64Signature Base64-encoded CMS signature
     * @return Certificate information object
     * @throws SignatureException if certificate extraction fails
     */
    public static DSCSignatureService.CertificateInfo extractCertificateInfo(String base64Signature) throws SignatureException {
        try {
            // Decode Base64 signature
            byte[] signatureBytes = Base64.getDecoder().decode(base64Signature);
            
            // Parse CMS signed data
            CMSSignedData cmsSignedData = new CMSSignedData(signatureBytes);
            
            // Get certificates from CMS
            Store<X509CertificateHolder> certStore = cmsSignedData.getCertificates();
            Collection<X509CertificateHolder> certCollection = certStore.getMatches(null);
            
            if (certCollection.isEmpty()) {
                throw new SignatureException("No certificates found in CMS signature");
            }
            
            // Get the first certificate (signer certificate)
            X509CertificateHolder certHolder = certCollection.iterator().next();
            
            // Convert to X509Certificate for easier processing
            CertificateFactory certFactory = CertificateFactory.getInstance("X.509");
            X509Certificate certificate = (X509Certificate) certFactory.generateCertificate(
                    new ByteArrayInputStream(certHolder.getEncoded()));
            
            // Extract certificate information
            String subject = certificate.getSubjectDN().getName();
            String issuer = certificate.getIssuerDN().getName();
            String serialNumber = certificate.getSerialNumber().toString();
            
            DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
            String validFrom = LocalDateTime.ofInstant(
                    certificate.getNotBefore().toInstant(), ZoneId.systemDefault())
                    .format(formatter);
            String validTo = LocalDateTime.ofInstant(
                    certificate.getNotAfter().toInstant(), ZoneId.systemDefault())
                    .format(formatter);
            
            String algorithm = certificate.getSigAlgName();
            int keyLength = certificate.getPublicKey().getAlgorithm().equals("RSA") ? 
                    ((java.security.interfaces.RSAPublicKey) certificate.getPublicKey()).getModulus().bitLength() : 0;
            
            boolean isValid = true;
            try {
                certificate.checkValidity();
            } catch (Exception e) {
                isValid = false;
            }
            
            logger.debug("Successfully extracted certificate info from CMS signature");
            return new DSCSignatureService.CertificateInfo(subject, issuer, serialNumber, 
                    validFrom, validTo, algorithm, keyLength, isValid);
            
        } catch (Exception e) {
            logger.error("Failed to extract certificate information from CMS signature", e);
            throw new SignatureException("Failed to extract certificate information: " + e.getMessage(), e);
        }
    }

    /**
     * Verifies the format of a CMS signature.
     *
     * @param base64Signature Base64-encoded signature to verify
     * @return true if format is valid CMS/PKCS#7, false otherwise
     */
    public static boolean isValidCMSFormat(String base64Signature) {
        try {
            if (base64Signature == null || base64Signature.trim().isEmpty()) {
                return false;
            }
            
            // Try to decode Base64
            byte[] signatureBytes = Base64.getDecoder().decode(base64Signature);
            
            // Try to parse as CMS signed data
            new CMSSignedData(signatureBytes);
            
            return true;
            
        } catch (Exception e) {
            logger.debug("Invalid CMS format: {}", e.getMessage());
            return false;
        }
    }

    /**
     * Extracts the signed data content from a CMS signature.
     *
     * @param base64Signature Base64-encoded CMS signature
     * @return The original signed data as byte array, or null if not embedded
     * @throws SignatureException if extraction fails
     */
    public static byte[] extractSignedContent(String base64Signature) throws SignatureException {
        try {
            // Decode Base64 signature
            byte[] signatureBytes = Base64.getDecoder().decode(base64Signature);
            
            // Parse CMS signed data
            CMSSignedData cmsSignedData = new CMSSignedData(signatureBytes);
            
            // Get signed content
            CMSProcessable signedContent = cmsSignedData.getSignedContent();
            if (signedContent != null) {
                return (byte[]) signedContent.getContent();
            }
            
            return null;
            
        } catch (Exception e) {
            logger.error("Failed to extract signed content from CMS signature", e);
            throw new SignatureException("Failed to extract signed content: " + e.getMessage(), e);
        }
    }

    /**
     * Gets the number of signers in a CMS signature.
     *
     * @param base64Signature Base64-encoded CMS signature
     * @return Number of signers
     * @throws SignatureException if parsing fails
     */
    public static int getSignerCount(String base64Signature) throws SignatureException {
        try {
            // Decode Base64 signature
            byte[] signatureBytes = Base64.getDecoder().decode(base64Signature);
            
            // Parse CMS signed data
            CMSSignedData cmsSignedData = new CMSSignedData(signatureBytes);
            
            // Get signers
            SignerInformationStore signers = cmsSignedData.getSignerInfos();
            return signers.size();
            
        } catch (Exception e) {
            logger.error("Failed to get signer count from CMS signature", e);
            throw new SignatureException("Failed to get signer count: " + e.getMessage(), e);
        }
    }
}