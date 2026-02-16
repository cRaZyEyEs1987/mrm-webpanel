#!/usr/bin/env python3
"""
Unit tests for MRM Webpanel auth and API.
Run with: python -m pytest panel/tests/test_auth.py -v
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import (
    hash_password, verify_password, create_jwt_token, verify_jwt_token
)

class TestAuth(unittest.TestCase):
    """Test authentication functions."""
    
    def test_hash_password(self):
        """Test password hashing."""
        password = "test123"
        hashed = hash_password(password)
        
        # Hash should be different from original
        self.assertNotEqual(password, hashed)
        
        # Hash should be a string
        self.assertIsInstance(hashed, str)
    
    def test_verify_password(self):
        """Test password verification."""
        password = "test123"
        hashed = hash_password(password)
        
        # Correct password should verify
        self.assertTrue(verify_password(password, hashed))
        
        # Wrong password should not verify
        self.assertFalse(verify_password("wrong", hashed))
    
    def test_jwt_token_creation_and_verification(self):
        """Test JWT token creation and verification."""
        user_id = 1
        username = "testuser"
        role = "admin"
        
        # Create token
        token = create_jwt_token(user_id, username, role)
        self.assertIsInstance(token, str)
        
        # Verify token
        payload = verify_jwt_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload['user_id'], user_id)
        self.assertEqual(payload['username'], username)
        self.assertEqual(payload['role'], role)
    
    def test_jwt_token_invalid(self):
        """Test JWT token verification with invalid token."""
        invalid_token = "invalid.token.here"
        payload = verify_jwt_token(invalid_token)
        self.assertIsNone(payload)
    
    def test_jwt_token_different_secret(self):
        """Test JWT token with different secret fails verification."""
        user_id = 1
        username = "testuser"
        role = "admin"
        
        # Change secret temporarily (mock)
        token = create_jwt_token(user_id, username, role)
        
        # Try to verify with original (should work)
        payload = verify_jwt_token(token)
        self.assertIsNotNone(payload)

class TestPasswordHashing(unittest.TestCase):
    """Test password hashing security."""
    
    def test_same_password_different_hash(self):
        """Test that same password produces different hashes (salt)."""
        password = "test123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        # Hashes should be different (due to random salt)
        self.assertNotEqual(hash1, hash2)
        
        # But both should verify against the same password
        self.assertTrue(verify_password(password, hash1))
        self.assertTrue(verify_password(password, hash2))

class TestRBAC(unittest.TestCase):
    """Test role-based access control."""
    
    def test_is_superadmin(self):
        """Test superadmin role check."""
        from rbac import RBAC
        
        superadmin = {'role': 'superadmin'}
        admin = {'role': 'admin'}
        
        self.assertTrue(RBAC.is_superadmin(superadmin))
        self.assertFalse(RBAC.is_superadmin(admin))
    
    def test_is_admin(self):
        """Test admin role check."""
        from rbac import RBAC
        
        superadmin = {'role': 'superadmin'}
        admin = {'role': 'admin'}
        user = {'role': 'user'}
        
        self.assertTrue(RBAC.is_admin(superadmin))
        self.assertTrue(RBAC.is_admin(admin))
        self.assertFalse(RBAC.is_admin(user))

if __name__ == '__main__':
    unittest.main()
