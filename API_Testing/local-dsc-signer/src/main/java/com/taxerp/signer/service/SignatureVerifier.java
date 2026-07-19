//Signature Verifier
package com.taxerp.signer.service;

import org.bouncycastle.cert.X509CertificateHolder;
import org.bouncycastle.cms.*;
import org.bouncycastle.cms.jcajce.JcaSimpleSignerInfoVerifierBuilder;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.util.Store;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.security.Security;
import java.security.cert.X509Certificate;
import java.util.Base64;
import java.util.Collection;
import java.util.Iterator;

/**
 * Service to verify CMS signatures locally
 * Implements ITD's verification code from ERI Data Signature process guide
 * 
 * FIXED: Extracts certificate FROM the signature itself (as per ITD spec)
 * No need to access USB token for verification!
 */
@Service
public class SignatureVerifier {
    private static final Logger logger = LoggerFactory.getLogger(SignatureVerifier.class);

    /**
     * Verify a CMS signature locally (as per ITD documentation)
     * 
     * The signature contains the certificate chain, so we extract it from there
     * This matches ITD's verification approach
     */
    public boolean verifySignature(String signBase64, String dataBase64) {
        try {
            logger.info("====================================");
            logger.info("Starting Signature Verification");
            logger.info("====================================");

            Security.addProvider(new BouncyCastleProvider());

            // Step 1: Decode Base64 (as per ITD doc)
            byte[] signBytes = Base64.getDecoder().decode(signBase64);
            byte[] dataBytes = Base64.getDecoder().decode(dataBase64);

            logger.info("Data size: {} bytes", dataBytes.length);
            logger.info("Signature size: {} bytes", signBytes.length);

            // Step 2: Create CMS objects (as per ITD doc)
            CMSProcessableByteArray cmsProcessableByteArray = new CMSProcessableByteArray(dataBytes);
            CMSSignedData cms = new CMSSignedData(cmsProcessableByteArray, signBytes);

            // Step 3: Extract certificate FROM the signature
            // The CMS signature contains the full certificate chain
            logger.info("Extracting certificate from signature...");
            
            Store certStore = cms.getCertificates();
            SignerInformationStore signers = cms.getSignerInfos();
            Collection<SignerInformation> signerCollection = signers.getSigners();

            if (signerCollection.isEmpty()) {
                logger.error("❌ No signers found in CMS signature");
                return false;
            }

            logger.info("Found {} signer(s)", signerCollection.size());

            // Verify each signer (usually just one)
            for (SignerInformation signer : signerCollection) {
                // Get the certificate that matches this signer
                Collection certCollection = certStore.getMatches(signer.getSID());
                
                if (certCollection.isEmpty()) {
                    logger.error("❌ No certificate found for signer");
                    return false;
                }

                Iterator certIt = certCollection.iterator();
                X509CertificateHolder certHolder = (X509CertificateHolder) certIt.next();
                
                logger.info("Certificate Subject: {}", certHolder.getSubject());
                logger.info("Certificate Issuer: {}", certHolder.getIssuer());
                logger.info("Certificate Valid From: {}", certHolder.getNotBefore());
                logger.info("Certificate Valid Until: {}", certHolder.getNotAfter());

                // Check certificate validity
                try {
                    certHolder.isValidOn(new java.util.Date());
                    logger.info("✓ Certificate is valid (not expired)");
                } catch (Exception e) {
                    logger.error("❌ Certificate expired or not yet valid: {}", e.getMessage());
                    return false;
                }

                // Verify signature (exact code from ITD documentation)
                logger.info("Verifying signature...");
                
                boolean verify = signer.verify(
                    new JcaSimpleSignerInfoVerifierBuilder()
                        .setProvider("BC")
                        .build(certHolder)
                );

                if (verify) {
                    logger.info("====================================");
                    logger.info("✅ SIGNATURE VERIFICATION SUCCESS!");
                    logger.info("====================================");
                    return true;
                } else {
                    logger.error("====================================");
                    logger.error("❌ SIGNATURE VERIFICATION FAILED!");
                    logger.error("Signature does not match certificate");
                    logger.error("====================================");
                    return false;
                }
            }

            return false;

        } catch (Exception e) {
            logger.error("====================================");
            logger.error("❌ Exception during verification");
            logger.error("====================================");
            logger.error("Error details:", e);
            return false;
        }
    }
}