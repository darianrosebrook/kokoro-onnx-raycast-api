#!/usr/bin/env python3
"""
Environment Checker for Kokoro TTS

This script analyzes your Python environment and provides specific recommendations
for resolving common setup issues. It builds on the existing system diagnostics
but provides more detailed analysis and troubleshooting guidance.

@author @darianrosebrook
"""

import os
import sys
import subprocess
import platform
import json
from pathlib import Path

def analyze_python_environment():
    """Analyze the current Python environment setup."""
    
    print(" Python Environment Analysis")
    print("=" * 50)
    
    analysis = {
        'python_version': sys.version,
        'python_path': sys.executable,
        'platform': platform.platform(),
        'architecture': platform.machine(),
        'virtual_env': None,
        'externally_managed': False,
        'packages': {},
        'issues': [],
        'recommendations': []
    }
    
    # Check virtual environment
    venv_path = os.environ.get('VIRTUAL_ENV', '')
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    
    if in_venv:
        analysis['virtual_env'] = venv_path
        print(f"✅ Virtual Environment: {venv_path}")
    else:
        analysis['issues'].append("Not in virtual environment")
        print("  System Python (not in virtual environment)")
    
    # Check for externally managed environment
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--help'],
            capture_output=True, text=True, timeout=10
        )
        if 'externally-managed' in result.stderr.lower():
            analysis['externally_managed'] = True
            if not in_venv:
                analysis['issues'].append("Externally managed environment without virtual environment")
    except:
        pass
    
    print(f" Python: {sys.version}")
    print(f" Path: {sys.executable}")
    print(f"  Platform: {platform.platform()}")
    print(f" Architecture: {platform.machine()}")
    print()
    
    return analysis

def check_required_packages():
    """Check installation status of required packages."""
    
    print(" Package Installation Status")
    print("=" * 50)
    
    # Core packages for the TTS system
    required_packages = [
        ('onnxruntime', 'onnxruntime'),
        ('kokoro-onnx', 'kokoro_onnx'),
        ('numpy', 'numpy'),
        ('fastapi', 'fastapi'),
        ('uvicorn', 'uvicorn'),
        ('pydantic', 'pydantic'),
    ]
    
    # Optional packages (for additional features)
    optional_packages = [
        ('transformers', 'transformers'),
    ]
    
    package_status = {}
    missing_packages = []
    
    # Check required packages
    for pip_name, import_name in required_packages:
        try:
            module = __import__(import_name)
            version = getattr(module, '__version__', 'unknown')
            package_status[pip_name] = {'installed': True, 'version': version, 'required': True}
            print(f"✅ {pip_name}: {version}")
        except ImportError:
            package_status[pip_name] = {'installed': False, 'version': None, 'required': True}
            missing_packages.append(pip_name)
            print(f" {pip_name}: Missing")
    
    # Check optional packages
    for pip_name, import_name in optional_packages:
        try:
            module = __import__(import_name)
            version = getattr(module, '__version__', 'unknown')
            package_status[pip_name] = {'installed': True, 'version': version, 'required': False}
            print(f"✅ {pip_name}: {version} (optional)")
        except ImportError:
            package_status[pip_name] = {'installed': False, 'version': None, 'required': False}
            print(f"ℹ  {pip_name}: Missing (optional)")
    
    # Check ONNX Runtime providers if available
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        package_status['onnxruntime']['providers'] = providers
        
        print(f"\n ONNX Runtime Providers:")
        for provider in providers:
            marker = "✅" if provider == 'CoreMLExecutionProvider' else ""
            print(f"   {marker} {provider}")
        
        if 'CoreMLExecutionProvider' not in providers:
            print("     CoreMLExecutionProvider not available")
    except ImportError:
        print(" ONNX Runtime: Not installed")
    
    print()
    return package_status, missing_packages

def check_system_compatibility():
    """Check system compatibility for CoreML and hardware acceleration."""
    
    print(" System Compatibility")
    print("=" * 50)
    
    compatibility = {
        'is_macos': sys.platform == 'darwin',
        'is_apple_silicon': False,
        'macos_version': None,
        'issues': [],
        'recommendations': []
    }
    
    if not compatibility['is_macos']:
        compatibility['issues'].append("CoreML requires macOS")
        print(f"  Platform: {sys.platform} (CoreML requires macOS)")
        return compatibility
    
    # Check Apple Silicon
    try:
        result = subprocess.run(['uname', '-m'], capture_output=True, text=True)
        if result.returncode == 0:
            arch = result.stdout.strip()
            compatibility['is_apple_silicon'] = arch == 'arm64'
            print(f" Architecture: {arch}")
            
            if not compatibility['is_apple_silicon']:
                compatibility['recommendations'].append(
                    "Consider using CPU execution instead of CoreML on Intel"
                )
    except:
        print(" Could not determine architecture")
    
    # Check macOS version
    try:
        result = subprocess.run(['sw_vers', '-productVersion'], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            compatibility['macos_version'] = version
            print(f" macOS Version: {version}")
            
            # Parse version for compatibility check
            version_parts = version.split('.')
            major = int(version_parts[0])
            
            if major < 11:
                compatibility['issues'].append(
                    f"macOS 11.0+ required for CoreML - current: {version}"
                )
    except:
        print(" Could not determine macOS version")
    
    print()
    return compatibility

def provide_installation_recommendations(analysis, missing_packages, package_status):
    """Provide specific installation recommendations based on the analysis."""
    
    print(" Installation Recommendations")
    print("=" * 50)
    
    # Filter to only required missing packages
    required_missing = [pkg for pkg in missing_packages if package_status.get(pkg, {}).get('required', True)]
    
    if not required_missing:
        print("✅ All required packages are installed!")
        return
    
    print(" Missing packages need to be installed:")
    print(f"   Packages: {', '.join(required_missing)}")
    print()
    
    if analysis['externally_managed'] and not analysis['virtual_env']:
        print(" Externally-managed environment detected")
        print("   This is common with Homebrew Python on macOS")
        print()
        
        print(" Recommended solution: Use virtual environment")
        print("   python3 -m venv kokoro-env")
        print("   source kokoro-env/bin/activate")
        print(f"   pip install {' '.join(missing_packages)}")
        print()
        
        print(" Alternative: Install with --user flag")
        print(f"   pip3 install --user {' '.join(missing_packages)}")
        print()
        
        print("  Not recommended: Override system protection")
        print(f"   pip3 install --break-system-packages {' '.join(missing_packages)}")
    
    elif analysis['virtual_env']:
        print("✅ Virtual environment detected - normal installation:")
        print(f"   pip install {' '.join(missing_packages)}")
    
    else:
        print(" Standard installation:")
        print(f"   pip install {' '.join(missing_packages)}")
    
    print()

def check_project_structure():
    """Check if the project structure is correct."""
    
    print(" Project Structure")
    print("=" * 50)
    
    expected_files = [
        'kokoro-v1.0.int8.onnx',
        'voices-v1.0.bin',
        'api/main.py',
        'api/config.py',
        'api/model/loader.py',
        'requirements.txt'
    ]
    
    structure_status = {}
    missing_files = []
    
    for file_path in expected_files:
        exists = os.path.exists(file_path)
        structure_status[file_path] = exists
        
        if exists:
            print(f"✅ {file_path}")
        else:
            print(f" {file_path}")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n  Missing files: {', '.join(missing_files)}")
        print("   Make sure you're in the correct project directory")
    
    print()
    return structure_status, missing_files

def generate_diagnostic_report(analysis, package_status, compatibility, structure_status):
    """Generate a comprehensive diagnostic report."""
    
    report = {
        'timestamp': subprocess.run(['date'], capture_output=True, text=True).stdout.strip(),
        'environment': analysis,
        'packages': package_status,
        'compatibility': compatibility,
        'project_structure': structure_status,
        'overall_status': 'ready' if (
            not analysis['issues'] and 
            not compatibility['issues'] and
            all(pkg['installed'] for pkg in package_status.values() if isinstance(pkg, dict) and pkg.get('required', True))
        ) else 'needs_attention'
    }
    
    return report

def main():
    """Main diagnostic function."""
    
    print(" Kokoro TTS Environment Diagnostic Tool")
    print("=" * 60)
    print()
    
    try:
        # Run all diagnostic checks
        analysis = analyze_python_environment()
        package_status, missing_packages = check_required_packages()
        compatibility = check_system_compatibility()
        structure_status, missing_files = check_project_structure()
        
        # Provide recommendations
        provide_installation_recommendations(analysis, missing_packages, package_status)
        
        # Generate diagnostic report
        report = generate_diagnostic_report(analysis, package_status, compatibility, structure_status)
        
        # Save diagnostic report
        report_file = '.cache/environment_diagnostic.json'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(" Next Steps")
        print("=" * 50)
        
        if report['overall_status'] == 'ready':
            print("✅ Environment is ready!")
            print("   You can now run: ./start_development.sh")
        else:
            print("  Environment needs attention:")
            if missing_packages:
                print(f"   1. Install missing packages: {', '.join(missing_packages)}")
            if missing_files:
                print(f"   2. Ensure required files are present: {', '.join(missing_files)}")
            if compatibility['issues']:
                print(f"   3. Address compatibility issues: {', '.join(compatibility['issues'])}")
        
        print(f"\n Full diagnostic report saved to: {report_file}")
        print("\nFor setup help, see: ORT_OPTIMIZATION_GUIDE.md")
        
        return 0 if report['overall_status'] == 'ready' else 1
        
    except Exception as e:
        print(f" Diagnostic failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 