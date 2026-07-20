package com.taxerp.util;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * Utility class for cryptographic hash operations, specifically SHA-256 hashing.
 * This class provides secure hash generation methods for both string and byte array inputs,
 * with proper error handling for cryptographic operations.
 */
public class HashUtil {
    
    private static final Logger logger = LoggerFactory.getLogger(HashUtil.class);
    private static final String SHA256_ALGORITHM = "SHA-256";
    
    /**
     * Generates SHA-256 hash of the input string using UTF-8 encoding.
     * 
     * @param data The string data to hash
     * @return Hexadecimal representation of the SHA-256 hash
     * @throws HashException if hashing operation fails or input is invalid
     */
    public static String sha256(String data) throws HashException {
        if (data == null) {
            throw new HashException("Input data cannot be null");
        }
        
        try {
            logger.debug("Generating SHA-256 hash for string data of length: {}", data.length());
            
            // Convert string to bytes using UTF-8 encoding for consistency
            byte[] dataBytes = data.getBytes(StandardCharsets.UTF_8);
            return sha256(dataBytes);
            
        } catch (Exception e) {
            logger.error("Failed to generate SHA-256 hash for string data: {}", e.getMessage());
            throw new HashException("SHA-256 hash generation failed for string input: " + e.getMessage(), e);
        }
    }
    
    /**
     * Generates SHA-256 hash of the input byte array.
     * 
     * @param data The byte array data to hash
     * @return Hexadecimal representation of the SHA-256 hash
     * @throws HashException if hashing operation fails or input is invalid
     */
    public static String sha256(byte[] data) throws HashException {
        if (data == null) {
            throw new HashException("Input data cannot be null");
        }
        
        try {
            logger.debug("Generating SHA-256 hash for byte array of length: {}", data.length);
            
            MessageDigest digest = MessageDigest.getInstance(SHA256_ALGORITHM);
            byte[] hashBytes = digest.digest(data);
            
            // Convert hash bytes to hexadecimal string
            String hexHash = bytesToHex(hashBytes);
            
            logger.debug("SHA-256 hash generated successfully, length: {}", hexHash.length());
            return hexHash;
            
        } catch (NoSuchAlgorithmException e) {
            logger.error("SHA-256 algorithm not available: {}", e.getMessage());
            throw new HashException("SHA-256 algorithm not available", e);
        } catch (Exception e) {
            logger.error("Failed to generate SHA-256 hash for byte array: {}", e.getMessage());
            throw new HashException("SHA-256 hash generation failed: " + e.getMessage(), e);
        }
    }
    
    /**
     * Generates SHA-256 hash and returns it as a byte array.
     * This method is useful when the hash needs to be used in binary operations.
     * 
     * @param data The string data to hash
     * @return SHA-256 hash as byte array
     * @throws HashException if hashing operation fails or input is invalid
     */
    public static byte[] sha256Bytes(String data) throws HashException {
        if (data == null) {
            throw new HashException("Input data cannot be null");
        }
        
        try {
            logger.debug("Generating SHA-256 hash bytes for string data of length: {}", data.length());
            
            byte[] dataBytes = data.getBytes(StandardCharsets.UTF_8);
            return sha256Bytes(dataBytes);
            
        } catch (Exception e) {
            logger.error("Failed to generate SHA-256 hash bytes for string data: {}", e.getMessage());
            throw new HashException("SHA-256 hash generation failed for string input: " + e.getMessage(), e);
        }
    }
    
    /**
     * Generates SHA-256 hash and returns it as a byte array.
     * This method is useful when the hash needs to be used in binary operations.
     * 
     * @param data The byte array data to hash
     * @return SHA-256 hash as byte array
     * @throws HashException if hashing operation fails or input is invalid
     */
    public static byte[] sha256Bytes(byte[] data) throws HashException {
        if (data == null) {
            throw new HashException("Input data cannot be null");
        }
        
        try {
            logger.debug("Generating SHA-256 hash bytes for byte array of length: {}", data.length);
            
            MessageDigest digest = MessageDigest.getInstance(SHA256_ALGORITHM);
            byte[] hashBytes = digest.digest(data);
            
            logger.debug("SHA-256 hash bytes generated successfully, length: {}", hashBytes.length);
            return hashBytes;
            
        } catch (NoSuchAlgorithmException e) {
            logger.error("SHA-256 algorithm not available: {}", e.getMessage());
            throw new HashException("SHA-256 algorithm not available", e);
        } catch (Exception e) {
            logger.error("Failed to generate SHA-256 hash bytes for byte array: {}", e.getMessage());
            throw new HashException("SHA-256 hash generation failed: " + e.getMessage(), e);
        }
    }
    
    /**
     * Verifies if the provided hash matches the SHA-256 hash of the input data.
     * This method is useful for hash validation operations.
     * 
     * @param data The original data to verify
     * @param expectedHash The expected hash in hexadecimal format
     * @return true if the hash matches, false otherwise
     * @throws HashException if verification operation fails
     */
    public static boolean verifySha256(String data, String expectedHash) throws HashException {
        if (data == null || expectedHash == null) {
            throw new HashException("Data and expected hash cannot be null");
        }
        
        try {
            logger.debug("Verifying SHA-256 hash for data of length: {}", data.length());
            
            String actualHash = sha256(data);
            boolean matches = actualHash.equalsIgnoreCase(expectedHash);
            
            logger.debug("SHA-256 hash verification result: {}", matches);
            return matches;
            
        } catch (Exception e) {
            logger.error("Failed to verify SHA-256 hash: {}", e.getMessage());
            throw new HashException("SHA-256 hash verification failed: " + e.getMessage(), e);
        }
    }
    
    /**
     * Converts byte array to hexadecimal string representation.
     * 
     * @param bytes The byte array to convert
     * @return Hexadecimal string representation (lowercase)
     */
    private static String bytesToHex(byte[] bytes) {
        StringBuilder hexString = new StringBuilder();
        for (byte b : bytes) {
            String hex = Integer.toHexString(0xff & b);
            if (hex.length() == 1) {
                hexString.append('0');
            }
            hexString.append(hex);
        }
        return hexString.toString();
    }
    
    /**
     * Custom exception for hash operation errors.
     */
    public static class HashException extends Exception {
        public HashException(String message) {
            super(message);
        }
        
        public HashException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}