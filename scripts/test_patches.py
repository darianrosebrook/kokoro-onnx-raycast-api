#!/usr/bin/env python3
"""
Test script for patch functionality.

This script tests if the patches are being applied correctly.
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_patches():
    """Test if the patches are being applied correctly."""
    
    print("Testing Patch Application")
    print("=" * 30)
    
    # Test 1: Check if patches are applied
    print("=== Test 1: Patch Status ===")
    try:
        from api.model.patch import get_patch_status
        patch_status = get_patch_status()
        print(f"Patch status: {patch_status}")
        
        if patch_status.get('applied', False):
            print("  ✅ Patches are applied")
        else:
            print("  ❌ Patches are not applied")
            return
    except Exception as e:
        print(f"  ❌ Error checking patch status: {e}")
        return
    
    # Test 2: Check if EspeakWrapper has set_data_path method
    print("\n=== Test 2: EspeakWrapper Patch ===")
    try:
        from kokoro_onnx.tokenizer import EspeakWrapper
        
        if hasattr(EspeakWrapper, 'set_data_path'):
            print("  ✅ EspeakWrapper.set_data_path method exists")
        else:
            print("  ❌ EspeakWrapper.set_data_path method missing")
            return
    except Exception as e:
        print(f"  ❌ Error checking EspeakWrapper: {e}")
        return
    
    # Test 3: Test the set_data_path method
    print("\n=== Test 3: set_data_path Method Test ===")
    try:
        from kokoro_onnx.tokenizer import EspeakWrapper
        
        # Test the method
        test_path = "/tmp/test_path"
        EspeakWrapper.set_data_path(test_path)
        print("  ✅ set_data_path method works")
    except Exception as e:
        print(f"  ❌ set_data_path method failed: {e}")
        return
    
    # Test 4: Check if patches are applied before model loading
    print("\n=== Test 4: Patch Application Order ===")
    try:
        # Apply patches explicitly
        from api.model.patch import apply_all_patches
        apply_all_patches()
        print("  ✅ Patches applied successfully")
        
        # Check status again
        from api.model.patch import get_patch_status
        patch_status = get_patch_status()
        print(f"  Patch status after explicit application: {patch_status}")
        
    except Exception as e:
        print(f"  ❌ Error applying patches: {e}")
        return
    
    print("\n=== Summary ===")
    print("✅ All patch tests passed!")
    print("The patches should be working correctly.")

if __name__ == "__main__":
    test_patches()
