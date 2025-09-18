import secrets
import os

def generate_secret_key():
    """Generate a cryptographically secure secret key"""
    return secrets.token_hex(32)  # 64 character hex string

def generate_base64_key():
    """Generate a base64 encoded secret key"""
    return secrets.token_urlsafe(32)  # URL-safe base64 string

if __name__ == "__main__":
    print("=== Secret Key Generator ===\n")
    
    print("Option 1 - Hex Secret Key:")
    hex_key = generate_secret_key()
    print(f"SECRET_KEY={hex_key}")
    
    print("\nOption 2 - Base64 Secret Key:")
    b64_key = generate_base64_key()
    print(f"SECRET_KEY={b64_key}")
    
    print("\n=== How to use ===")
    print("1. Copy one of the keys above")
    print("2. Set as environment variable:")
    print(f"   export SECRET_KEY='{hex_key}'")
    print("3. Or add to docker-compose.yml environment section")
    print("4. Or create .env file with the key")
    
    print("\n  IMPORTANT:")
    print("- Never commit secret keys to version control")
    print("- Use different keys for development/production")
    print("- Store keys securely (environment variables, secrets manager)")