//! ID generation using Base62 encoding

use rand::Rng;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;

/// Base62 character set: 0-9, a-z, A-Z
const CHARSET: &[u8] = b"0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
const BASE: u64 = 62;

/// ID Generator for creating short codes
#[derive(Debug, Clone)]
pub struct IdGenerator {
    /// Current counter value
    counter: Arc<AtomicU64>,

    /// Code length
    code_length: usize,

    /// Range start (for distributed counter allocation)
    range_start: u64,

    /// Range end
    range_end: u64,
}

impl IdGenerator {
    /// Create a new ID generator
    pub fn new(code_length: usize) -> Self {
        Self {
            counter: Arc::new(AtomicU64::new(0)),
            code_length,
            range_start: 0,
            range_end: u64::MAX,
        }
    }

    /// Create a new ID generator with a specific range
    /// Used for distributed systems where each instance gets a range
    pub fn with_range(code_length: usize, range_start: u64, range_end: u64) -> Self {
        Self {
            counter: Arc::new(AtomicU64::new(range_start)),
            code_length,
            range_start,
            range_end,
        }
    }

    /// Generate a new short code
    pub fn generate(&self) -> String {
        // Get next counter value
        let counter = self.counter.fetch_add(1, Ordering::SeqCst);

        // Check if we've exhausted our range
        if counter >= self.range_end {
            // In production, this would trigger a range refresh from DynamoDB
            // For now, we'll wrap around with a random offset
            let random_offset: u64 = rand::thread_rng().gen();
            self.counter.store(self.range_start + (random_offset % 1000), Ordering::SeqCst);
        }

        // Encode to base62
        self.encode(counter)
    }

    /// Generate a random short code (fallback for collisions)
    pub fn generate_random(&self) -> String {
        let mut rng = rand::thread_rng();
        let mut code = String::with_capacity(self.code_length);

        for _ in 0..self.code_length {
            let idx = rng.gen_range(0..BASE as usize);
            code.push(CHARSET[idx] as char);
        }

        code
    }

    /// Encode a number to base62 string
    pub fn encode(&self, mut num: u64) -> String {
        if num == 0 {
            return self.pad("0".to_string());
        }

        let mut result = String::new();

        while num > 0 {
            let remainder = (num % BASE) as usize;
            result.insert(0, CHARSET[remainder] as char);
            num /= BASE;
        }

        self.pad(result)
    }

    /// Decode a base62 string to number
    pub fn decode(&self, code: &str) -> Option<u64> {
        let mut result: u64 = 0;

        for c in code.chars() {
            let value = match c {
                '0'..='9' => (c as u64) - ('0' as u64),
                'a'..='z' => (c as u64) - ('a' as u64) + 10,
                'A'..='Z' => (c as u64) - ('A' as u64) + 36,
                _ => return None,
            };

            result = result.checked_mul(BASE)?.checked_add(value)?;
        }

        Some(result)
    }

    /// Pad the code to the required length
    fn pad(&self, mut code: String) -> String {
        while code.len() < self.code_length {
            code.insert(0, '0');
        }
        code
    }

    /// Validate a short code format
    pub fn is_valid_code(&self, code: &str) -> bool {
        if code.len() != self.code_length {
            return false;
        }

        code.chars().all(|c| matches!(c, '0'..='9' | 'a'..='z' | 'A'..='Z'))
    }

    /// Validate a custom alias
    pub fn is_valid_custom_alias(alias: &str, max_length: usize) -> bool {
        if alias.len() < 4 || alias.len() > max_length {
            return false;
        }

        // Must be alphanumeric or hyphens
        if !alias.chars().all(|c| c.is_alphanumeric() || c == '-') {
            return false;
        }

        // Cannot start or end with hyphen
        if alias.starts_with('-') || alias.ends_with('-') {
            return false;
        }

        // Cannot have consecutive hyphens
        if alias.contains("--") {
            return false;
        }

        true
    }
}

impl Default for IdGenerator {
    fn default() -> Self {
        Self::new(7) // Default to 7-character codes
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_encode_decode() {
        let gen = IdGenerator::new(7);

        // Test various numbers
        let test_cases = [0u64, 1, 61, 62, 100, 1000, 1_000_000, 1_234_567_890];

        for num in test_cases {
            let encoded = gen.encode(num);
            let decoded = gen.decode(&encoded).unwrap();
            assert_eq!(decoded, num, "Failed for {}: encoded as {}", num, encoded);
        }
    }

    #[test]
    fn test_code_length() {
        let gen = IdGenerator::new(7);

        for _ in 0..100 {
            let code = gen.generate();
            assert_eq!(code.len(), 7);
        }
    }

    #[test]
    fn test_uniqueness() {
        let gen = IdGenerator::new(7);
        let mut codes = std::collections::HashSet::new();

        for _ in 0..10000 {
            let code = gen.generate();
            assert!(!codes.contains(&code), "Duplicate code generated: {}", code);
            codes.insert(code);
        }
    }

    #[test]
    fn test_valid_custom_alias() {
        assert!(IdGenerator::is_valid_custom_alias("my-link", 20));
        assert!(IdGenerator::is_valid_custom_alias("mylink123", 20));
        assert!(IdGenerator::is_valid_custom_alias("test", 20));

        assert!(!IdGenerator::is_valid_custom_alias("ab", 20)); // Too short
        assert!(!IdGenerator::is_valid_custom_alias("-mylink", 20)); // Starts with hyphen
        assert!(!IdGenerator::is_valid_custom_alias("mylink-", 20)); // Ends with hyphen
        assert!(!IdGenerator::is_valid_custom_alias("my--link", 20)); // Consecutive hyphens
        assert!(!IdGenerator::is_valid_custom_alias("my_link", 20)); // Underscore not allowed
    }
}
