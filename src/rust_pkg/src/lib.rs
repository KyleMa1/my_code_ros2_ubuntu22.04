pub fn greet(name: &str) -> String {
    format!("Hello from Rust, {name}!")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_greet() {
        assert_eq!(greet("World"), "Hello from Rust, World!");
    }
}
