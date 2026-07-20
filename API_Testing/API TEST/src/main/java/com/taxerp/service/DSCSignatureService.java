package com.taxerp.service;

import com.taxerp.exception.SignatureException;

/**
 * DSC Signature Service - HTTP Client Interface
 * 
 * AWS Backend uses this to call the LOCAL DSC signing service over HTTP.
 * This service does NOT perform signing - it delegates to local USB DSC signer.
 * 
 * Architecture:
 * - AWS Backend (this interface) → HTTP → Local DSC Signer (USB token)
 */
public interface DSCSignatureService {

    /**
     * Signs a JSON payload by calling the local DSC signing service over HTTP.
     * 
     * @param jsonPayload The JSON payload to be signed
     * @return SigningResult containing signed data and signature
     * @throws SignatureException if signing operation fails
     */
    SigningResult signPayload(String jsonPayload) throws SignatureException;

    /**
     * Checks if the local DSC signing service is available.
     * 
     * @return true if local signer is reachable and healthy
     */
    boolean isLocalSignerAvailable();

    /**
     * Result of signing operation from local DSC signer
     */
    class SigningResult {
        private final String signedData;      // Base64 encoded signed data
        private final String signature;       // Base64 encoded CMS signature
        private final String certificate;     // Base64 encoded certificate (optional)
        private final boolean success;
        private final String error;

        public SigningResult(String signedData, String signature, String certificate, 
                           boolean success, String error) {
            this.signedData = signedData;
            this.signature = signature;
            this.certificate = certificate;
            this.success = success;
            this.error = error;
        }

        public String getSignedData() { return signedData; }
        public String getSignature() { return signature; }
        public String getCertificate() { return certificate; }
        public boolean isSuccess() { return success; }
        public String getError() { return error; }
    }
}
