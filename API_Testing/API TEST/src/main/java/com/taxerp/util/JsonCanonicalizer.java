package com.taxerp.util;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.charset.StandardCharsets;
import java.util.Iterator;
import java.util.Map;
import java.util.TreeMap;

/**
 * Utility class for JSON canonicalization to ensure consistent JSON structure
 * for digital signature operations. This class standardizes JSON formatting
 * by removing whitespace, sorting object keys alphabetically, and ensuring
 * consistent UTF-8 encoding.
 */
public class JsonCanonicalizer {
    
    private static final Logger logger = LoggerFactory.getLogger(JsonCanonicalizer.class);
    private static final ObjectMapper objectMapper = new ObjectMapper();
    
    static {
        // Configure ObjectMapper for consistent output
        objectMapper.configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true);
        objectMapper.configure(SerializationFeature.WRITE_NULL_MAP_VALUES, false);
    }
    
    /**
     * Canonicalizes a JSON string by standardizing its structure.
     * This method:
     * - Parses the JSON to validate structure
     * - Sorts all object keys alphabetically
     * - Removes unnecessary whitespace
     * - Ensures consistent UTF-8 encoding
     * - Produces deterministic output for identical logical content
     * 
     * @param jsonString The JSON string to canonicalize
     * @return Canonicalized JSON string with sorted keys and no whitespace
     * @throws JsonException if the input is not valid JSON or canonicalization fails
     */
    public static String canonicalize(String jsonString) throws JsonException {
        if (jsonString == null || jsonString.trim().isEmpty()) {
            throw new JsonException("JSON string cannot be null or empty");
        }
        
        try {
            logger.debug("Starting JSON canonicalization for input length: {}", jsonString.length());
            
            // Parse JSON to validate structure and create tree
            JsonNode rootNode = objectMapper.readTree(jsonString);
            
            // Recursively sort all object keys
            JsonNode canonicalNode = canonicalizeNode(rootNode);
            
            // Convert back to string with no pretty printing (compact format)
            String canonicalJson = objectMapper.writeValueAsString(canonicalNode);
            
            // Ensure UTF-8 encoding consistency
            byte[] utf8Bytes = canonicalJson.getBytes(StandardCharsets.UTF_8);
            String result = new String(utf8Bytes, StandardCharsets.UTF_8);
            
            logger.debug("JSON canonicalization completed. Output length: {}", result.length());
            return result;
            
        } catch (JsonProcessingException e) {
            logger.error("Failed to canonicalize JSON: {}", e.getMessage());
            throw new JsonException("Invalid JSON format: " + e.getMessage(), e);
        } catch (Exception e) {
            logger.error("Unexpected error during JSON canonicalization: {}", e.getMessage());
            throw new JsonException("JSON canonicalization failed: " + e.getMessage(), e);
        }
    }
    
    /**
     * Recursively canonicalizes a JsonNode by sorting object keys and processing nested structures.
     * 
     * @param node The JsonNode to canonicalize
     * @return Canonicalized JsonNode with sorted keys
     */
    private static JsonNode canonicalizeNode(JsonNode node) {
        if (node.isObject()) {
            return canonicalizeObject((ObjectNode) node);
        } else if (node.isArray()) {
            return canonicalizeArray((ArrayNode) node);
        } else {
            // Primitive values (string, number, boolean, null) remain unchanged
            return node;
        }
    }
    
    /**
     * Canonicalizes an ObjectNode by sorting its keys alphabetically and
     * recursively canonicalizing nested values.
     * 
     * @param objectNode The ObjectNode to canonicalize
     * @return New ObjectNode with sorted keys
     */
    private static ObjectNode canonicalizeObject(ObjectNode objectNode) {
        ObjectNode canonicalObject = objectMapper.createObjectNode();
        
        // Use TreeMap to automatically sort keys alphabetically
        TreeMap<String, JsonNode> sortedFields = new TreeMap<>();
        
        Iterator<Map.Entry<String, JsonNode>> fields = objectNode.fields();
        while (fields.hasNext()) {
            Map.Entry<String, JsonNode> field = fields.next();
            sortedFields.put(field.getKey(), canonicalizeNode(field.getValue()));
        }
        
        // Add sorted fields to new object
        for (Map.Entry<String, JsonNode> entry : sortedFields.entrySet()) {
            canonicalObject.set(entry.getKey(), entry.getValue());
        }
        
        return canonicalObject;
    }
    
    /**
     * Canonicalizes an ArrayNode by recursively canonicalizing each element.
     * Array order is preserved as it may be semantically significant.
     * 
     * @param arrayNode The ArrayNode to canonicalize
     * @return New ArrayNode with canonicalized elements
     */
    private static ArrayNode canonicalizeArray(ArrayNode arrayNode) {
        ArrayNode canonicalArray = objectMapper.createArrayNode();
        
        for (JsonNode element : arrayNode) {
            canonicalArray.add(canonicalizeNode(element));
        }
        
        return canonicalArray;
    }
    
    /**
     * Custom exception for JSON canonicalization errors.
     */
    public static class JsonException extends Exception {
        public JsonException(String message) {
            super(message);
        }
        
        public JsonException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}