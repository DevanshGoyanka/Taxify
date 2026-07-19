//Local DSC Signer APPLICATION
package com.taxerp.signer;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Local DSC Signing Service Application
 * 
 * Purpose: USB DSC token signing ONLY
 * Runs on: Windows laptop with USB token
 * Port: 9090
 * 
 * This service does NOT:
 * - Call ERI APIs
 * - Have database
 * - Have authentication
 * - Know about AWS
 * 
 * This service ONLY:
 * - Signs payloads using USB DSC token via PKCS#11
 * - Returns signed data and signature
 */
@SpringBootApplication
public class LocalDscSignerApplication {

    public static void main(String[] args) {
        // Set BouncyCastle system properties
        System.setProperty("org.bouncycastle.asn1.allow_unsafe_integer", "true");
        
        System.out.println("========================================");
        System.out.println("Local DSC Signing Service");
        System.out.println("Port: 9090");
        System.out.println("USB DSC Token Required");
        System.out.println("========================================");
        
        SpringApplication.run(LocalDscSignerApplication.class, args);
    }
}
