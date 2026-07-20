package com.taxerp.util;

import com.taxerp.util.JsonCanonicalizer.JsonException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for JsonCanonicalizer utility class.
 * Tests various JSON structures, edge cases, and error conditions.
 */
class JsonCanonicalizerTest {

    @Test
    @DisplayName("Should canonicalize simple object with sorted keys")
    void testSimpleObjectCanonicalization() throws JsonException {
        String input = "{\"name\":\"John\",\"age\":30,\"city\":\"New York\"}";
        String expected = "{\"age\":30,\"city\":\"New York\",\"name\":\"John\"}";
        
        String result = JsonCanonicalizer.canonicalize(input);
        
        assertEquals(expected, result);
    }

    @Test
    @DisplayName("Should canonicalize nested objects with sorted keys")
    void testNestedObjectCanonicalization() throws JsonException {
        String input = "{\"person\":{\"name\":\"John\",\"age\":30},\"address\":{\"street\":\"Main St\",\"city\":\"NYC\"}}";
        String expected = "{\"address\":{\"city\":\"NYC\",\"street\":\"Main St\"},\"person\":{\"age\":30,\"name\":\"John\"}}";
        
        String result = JsonCanonicalizer.canonicalize(input);
        
        assertEquals(expected, result);
    }

    @Test
    @DisplayName("Should canonicalize arrays while preserving order")
    void testArrayCanonicalization() throws JsonException {
        String input = "{\"numbers\":[3,1,2],\"items\":[{\"name\":\"B\",\"id\":2},{\"name\":\"A\",\"id\":1}]}";
        String expected = "{\"items\":[{\"id\":2,\"name\":\"B\"},{\"id\":1,\"name\":\"A\"}],\"numbers\":[3,1,2]}";
        
        String result = JsonCanonicalizer.canonicalize(input);
        
        assertEquals(expected, result);
    }

    @Test
    @DisplayName("Should handle complex nested structure")
    void testComplexNestedStructure() throws JsonException {
        String input = """
            {
                "user": {
                    "profile": {
                        "name": "John Doe",
                        "email": "john@example.com"
                    },
                    "settings": {
                        "theme": "dark",
                        "notifications": true
                    }
                },
                "data": [
                    {"type": "A", "value": 1},
                    {"type": "B", "value": 2}
                ]
            }
            """;
        
        String expected = "{\"data\":[{\"type\":\"A\",\"value\":1},{\"type\":\"B\",\"value\":2}],\"user\":{\"profile\":{\"email\":\"john@example.com\",\"name\":\"John Doe\"},\"settings\":{\"notifications\":true,\"theme\":\"dark\"}}}";
        
        String result = JsonCanonicalizer.canonicalize(input);
        
        assertEquals(expected, result);
    }

    @Test
    @DisplayName("Should handle different data types correctly")
    void testDifferentDataTypes() throws JsonException {
        String input = "{\"string\":\"value\",\"number\":42,\"boolean\":true,\"nullValue\":null,\"decimal\":3.14}";
        String expected = "{\"boolean\":true,\"decimal\":3.14,\"nullValue\":null,\"number\":42,\"string\":\"value\"}";
        
        String result = JsonCanonicalizer.canonicalize(input);
        
        assertEquals(expected, result);
    }

    @Test
    @DisplayName("Should remove whitespace and format consistently")
    void testWhitespaceRemoval() throws JsonException {
        String input = """
            {
                "name"  :  "John"  ,
                "age"   :  30      ,
                "city"  :  "NYC"
            }
            """;
        String expected = "{\"age\":30,\"city\":\"NYC\",\"name\":\"John\"}";
        
        String result = JsonCanonicalizer.canonicalize(input);
        
        assertEquals(expected, result);
    }

    @Test
    @DisplayName("Should handle empty object")
    void testEmptyObject() throws JsonException {
        String input = "{}";
        String expected = "{}";
        
        String result = JsonCanonicalizer.canonicalize(input);
        
        assertEquals(expected, result);
    }

    @Test
    @DisplayName("Should handle empty array")
    void testEmptyArray() throws JsonException {
        String input = "[]";
        String expected = "[]";
        
        String result = JsonCanonicalizer.canonicalize(input);
        
        assertEquals(expected, result);
    }

    @Test
    @DisplayName("Should handle array of primitives")
    void testArrayOfPrimitives() throws JsonException {
        String input = "[\"apple\", \"banana\", \"cherry\"]";
        String expected = "[\"apple\",\"banana\",\"cherry\"]";
        
        String result = JsonCanonicalizer.canonicalize(input);
        
        assertEquals(expected, result);
    }

    @Test
    @DisplayName("Should produce identical output for logically identical JSON")
    void testConsistentOutput() throws JsonException {
        String input1 = "{\"b\":2,\"a\":1,\"c\":3}";
        String input2 = "{\"a\":1,\"b\":2,\"c\":3}";
        String input3 = "{ \"c\" : 3 , \"a\" : 1 , \"b\" : 2 }";
        
        String result1 = JsonCanonicalizer.canonicalize(input1);
        String result2 = JsonCanonicalizer.canonicalize(input2);
        String result3 = JsonCanonicalizer.canonicalize(input3);
        
        assertEquals(result1, result2);
        assertEquals(result2, result3);
        assertEquals("{\"a\":1,\"b\":2,\"c\":3}", result1);
    }

    @Test
    @DisplayName("Should handle Unicode characters correctly")
    void testUnicodeCharacters() throws JsonException {
        String input = "{\"message\":\"Hello 世界\",\"emoji\":\"😀\"}";
        String expected = "{\"emoji\":\"😀\",\"message\":\"Hello 世界\"}";
        
        String result = JsonCanonicalizer.canonicalize(input);
        
        assertEquals(expected, result);
    }

    @Test
    @DisplayName("Should throw exception for null input")
    void testNullInput() {
        JsonException exception = assertThrows(JsonException.class, () -> {
            JsonCanonicalizer.canonicalize(null);
        });
        
        assertTrue(exception.getMessage().contains("cannot be null or empty"));
    }

    @Test
    @DisplayName("Should throw exception for empty input")
    void testEmptyInput() {
        JsonException exception = assertThrows(JsonException.class, () -> {
            JsonCanonicalizer.canonicalize("");
        });
        
        assertTrue(exception.getMessage().contains("cannot be null or empty"));
    }

    @Test
    @DisplayName("Should throw exception for whitespace-only input")
    void testWhitespaceOnlyInput() {
        JsonException exception = assertThrows(JsonException.class, () -> {
            JsonCanonicalizer.canonicalize("   ");
        });
        
        assertTrue(exception.getMessage().contains("cannot be null or empty"));
    }

    @ParameterizedTest
    @ValueSource(strings = {
        "{invalid json}",
        "{\"key\": }",
        "{\"key\": \"value\",}",
        "[1, 2, 3,]",
        "not json at all"
    })
    @DisplayName("Should throw exception for invalid JSON")
    void testInvalidJson(String invalidJson) {
        JsonException exception = assertThrows(JsonException.class, () -> {
            JsonCanonicalizer.canonicalize(invalidJson);
        });
        
        assertTrue(exception.getMessage().contains("Invalid JSON format") || 
                  exception.getMessage().contains("JSON canonicalization failed"));
    }

    @Test
    @DisplayName("Should handle deeply nested structures")
    void testDeeplyNestedStructure() throws JsonException {
        String input = "{\"level1\":{\"level2\":{\"level3\":{\"level4\":{\"value\":\"deep\"}}}}}";
        String expected = "{\"level1\":{\"level2\":{\"level3\":{\"level4\":{\"value\":\"deep\"}}}}}";
        
        String result = JsonCanonicalizer.canonicalize(input);
        
        assertEquals(expected, result);
    }

    @Test
    @DisplayName("Should handle mixed array content")
    void testMixedArrayContent() throws JsonException {
        String input = "[{\"z\":1,\"a\":2}, \"string\", 42, true, null, [1,2,3]]";
        String expected = "[{\"a\":2,\"z\":1},\"string\",42,true,null,[1,2,3]]";
        
        String result = JsonCanonicalizer.canonicalize(input);
        
        assertEquals(expected, result);
    }
}