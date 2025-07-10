#!/usr/bin/env python3
"""
Comprehensive CoreML Troubleshooting Tool

This script provides advanced diagnostic and troubleshooting capabilities for CoreML
issues, building on the existing system architecture while providing deeper insights
into configuration, compatibility, and performance issues.

@author @darianrosebrook
"""

import os
import sys
import json
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add the parent directory to the path so we can import from the API
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.config import TTSConfig
from api.model.loader import detect_apple_silicon_capabilities, validate_provider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CoreMLTroubleshooter:
    """Advanced CoreML troubleshooting with comprehensive diagnostics."""
    
    def __init__(self):
        self.issues_found = []
        self.recommendations = []
        self.temp_dir = tempfile.mkdtemp(prefix="kokoro_coreml_troubleshoot_")
        logger.info(f"🔧 Using temp directory: {self.temp_dir}")
    
    def check_system_requirements(self) -> Dict[str, Any]:
        """Check comprehensive system requirements for CoreML."""
        
        logger.info("🔍 Checking system requirements...")
        
        # Use existing hardware detection
        capabilities = detect_apple_silicon_capabilities()
        
        results = {
            'platform': sys.platform,
            'capabilities': capabilities,
            'issues': [],
            'recommendations': []
        }
        
        # Validate macOS requirement
        if not capabilities.get('is_apple_silicon', False) and sys.platform != 'darwin':
            results['issues'].append(f"CoreML requires macOS - running on {sys.platform}")
            return results
        
        # Check Apple Silicon optimization
        if not capabilities['is_apple_silicon']:
            results['issues'].append(f"Running on {capabilities['cpu_arch']} - Apple Silicon recommended")
            results['recommendations'].append("Consider using CPU execution instead of CoreML")
        
        # Check Neural Engine availability
        if capabilities['is_apple_silicon'] and not capabilities['has_neural_engine']:
            results['recommendations'].append("Neural Engine not detected - using CPU+GPU CoreML")
        
        # Check macOS version compatibility
        try:
            import subprocess
            result = subprocess.run(['sw_vers', '-productVersion'], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip()
                results['macos_version'] = version
                
                # Parse version for compatibility
                version_parts = version.split('.')
                major = int(version_parts[0])
                
                if major < 11:
                    results['issues'].append(f"macOS 11.0+ required - current: {version}")
        except Exception as e:
            logger.warning(f"Could not determine macOS version: {e}")
        
        return results
    
    def check_package_installation(self) -> Dict[str, Any]:
        """Check package installation with version compatibility."""
        
        logger.info("🔍 Checking package installation...")
        
        results = {
            'packages': {},
            'issues': [],
            'recommendations': []
        }
        
        # Check core packages
        required_packages = [
            ('onnxruntime', 'onnxruntime'),
            ('kokoro-onnx', 'kokoro_onnx'),
            ('numpy', 'numpy'),
            ('transformers', 'transformers'),
        ]
        
        for pip_name, import_name in required_packages:
            try:
                module = __import__(import_name)
                version = getattr(module, '__version__', 'unknown')
                results['packages'][pip_name] = {
                    'installed': True,
                    'version': version,
                    'location': getattr(module, '__file__', 'unknown')
                }
                logger.info(f"✅ {pip_name}: {version}")
            except ImportError:
                results['packages'][pip_name] = {'installed': False}
                results['issues'].append(f"Package '{pip_name}' not installed")
                logger.error(f"❌ {pip_name}: Missing")
        
        # Check ONNX Runtime providers
        try:
            import onnxruntime as ort
            providers = ort.get_available_providers()
            results['available_providers'] = providers
            results['onnxruntime_version'] = ort.__version__
            
            logger.info(f"🔧 ONNX Runtime {ort.__version__} providers:")
            for provider in providers:
                marker = "✅" if provider == 'CoreMLExecutionProvider' else "ℹ️"
                logger.info(f"   {marker} {provider}")
            
            if 'CoreMLExecutionProvider' not in providers:
                results['issues'].append("CoreMLExecutionProvider not available")
                results['recommendations'].append("Install ONNX Runtime with CoreML support")
        except ImportError:
            results['issues'].append("ONNX Runtime not installed")
        
        return results
    
    def check_model_files(self) -> Dict[str, Any]:
        """Check model file accessibility and validation."""
        
        logger.info("🔍 Checking model files...")
        
        results = {
            'model_status': {},
            'issues': [],
            'recommendations': []
        }
        
        # Check main model file
        model_path = TTSConfig.MODEL_PATH
        if not os.path.exists(model_path):
            results['issues'].append(f"Model file not found: {model_path}")
            results['model_status']['main_model'] = {'exists': False, 'path': model_path}
        else:
            size_mb = os.path.getsize(model_path) / (1024 * 1024)
            results['model_status']['main_model'] = {
                'exists': True,
                'path': model_path,
                'size_mb': size_mb
            }
            logger.info(f"✅ Model file: {model_path} ({size_mb:.1f}MB)")
            
            # Check for potential issues
            if size_mb > 1000:  # 1GB
                results['issues'].append(f"Large model size ({size_mb:.1f}MB) may cause CoreML issues")
                results['recommendations'].append("Consider model quantization")
        
        # Check voices file
        voices_path = TTSConfig.VOICES_PATH
        if not os.path.exists(voices_path):
            results['issues'].append(f"Voices file not found: {voices_path}")
            results['model_status']['voices'] = {'exists': False, 'path': voices_path}
        else:
            size_mb = os.path.getsize(voices_path) / (1024 * 1024)
            results['model_status']['voices'] = {
                'exists': True,
                'path': voices_path,
                'size_mb': size_mb
            }
            logger.info(f"✅ Voices file: {voices_path} ({size_mb:.1f}MB)")
        
        # Check for ORT model
        try:
            from api.model.loader import get_or_create_ort_model
            ort_path = TTSConfig.ORT_CACHE_DIR
            if os.path.exists(ort_path):
                ort_files = [f for f in os.listdir(ort_path) if f.endswith('.ort')]
                results['model_status']['ort_models'] = {
                    'cache_dir': ort_path,
                    'files': ort_files
                }
                logger.info(f"📁 ORT cache directory: {ort_path}")
                for ort_file in ort_files:
                    logger.info(f"   📄 {ort_file}")
        except Exception as e:
            logger.warning(f"Could not check ORT models: {e}")
        
        return results
    
    def test_coreml_functionality(self) -> Dict[str, Any]:
        """Test CoreML functionality with comprehensive diagnostics."""
        
        logger.info("🔍 Testing CoreML functionality...")
        
        results = {
            'provider_validation': {},
            'session_creation': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            import onnxruntime as ort
            
            # Test provider validation
            coreml_available = validate_provider('CoreMLExecutionProvider')
            results['provider_validation']['coreml'] = coreml_available
            
            if not coreml_available:
                results['issues'].append("CoreML provider validation failed")
                logger.error("❌ CoreML provider not available")
                return results
            
            # Test session creation with different configurations
            test_configs = [
                {
                    'name': 'Basic CoreML',
                    'providers': ['CoreMLExecutionProvider', 'CPUExecutionProvider'],
                    'provider_options': [{'device_type': 'CPUOnly'}, {}]
                },
                {
                    'name': 'CoreML with GPU',
                    'providers': ['CoreMLExecutionProvider', 'CPUExecutionProvider'],
                    'provider_options': [{'device_type': 'CPUAndGPU'}, {}]
                },
                {
                    'name': 'CoreML with Neural Engine',
                    'providers': ['CoreMLExecutionProvider', 'CPUExecutionProvider'],
                    'provider_options': [{'device_type': 'CPUAndNeuralEngine'}, {}]
                }
            ]
            
            for config in test_configs:
                try:
                    session_options = ort.SessionOptions()
                    session_options.log_severity_level = 3  # Minimize logging
                    
                    # Configure local temp directory for CoreML to avoid permission issues
                    local_temp_dir = os.path.join(".cache", "coreml_temp")
                    os.makedirs(local_temp_dir, exist_ok=True)
                    
                    if os.path.exists(TTSConfig.MODEL_PATH):
                        session = ort.InferenceSession(
                            TTSConfig.MODEL_PATH,
                            session_options,
                            providers=config['providers'],
                            provider_options=config['provider_options']
                        )
                        
                        actual_providers = session.get_providers()
                        results['session_creation'][config['name']] = {
                            'success': True,
                            'requested_providers': config['providers'],
                            'actual_providers': actual_providers,
                            'coreml_active': 'CoreMLExecutionProvider' in actual_providers
                        }
                        
                        logger.info(f"✅ {config['name']}: Success")
                        
                        # Clean up
                        del session
                        
                    else:
                        results['session_creation'][config['name']] = {
                            'success': False,
                            'error': 'Model file not found'
                        }
                        
                except Exception as e:
                    results['session_creation'][config['name']] = {
                        'success': False,
                        'error': str(e)
                    }
                    logger.warning(f"⚠️ {config['name']}: {e}")
                    
                    # Analyze common error patterns
                    if "Error in building plan" in str(e):
                        results['issues'].append("CoreML model compilation failed")
                        results['recommendations'].append("Try converting model to ORT format")
                    elif "Permission denied" in str(e):
                        results['issues'].append("Permission issues with temporary directories")
                        results['recommendations'].append("Check temporary directory permissions")
        
        except ImportError:
            results['issues'].append("ONNX Runtime not available for testing")
        
        return results
    
    def generate_troubleshooting_recommendations(self) -> List[str]:
        """Generate specific troubleshooting recommendations based on findings."""
        
        recommendations = []
        
        # Environment fixes
        recommendations.append("# Environment Configuration")
        recommendations.append("export KOKORO_ORT_OPTIMIZATION=true")
        recommendations.append("export TMPDIR=$(pwd)/.cache")
        recommendations.append("")
        
        # Package recommendations
        recommendations.append("# Package Updates")
        recommendations.append("pip install --upgrade onnxruntime")
        recommendations.append("pip install --upgrade kokoro-onnx")
        recommendations.append("")
        
        # Model optimization
        recommendations.append("# Model Optimization")
        recommendations.append("python scripts/convert_to_ort.py kokoro-v1.0.int8.onnx")
        recommendations.append("")
        
        # Advanced configuration
        recommendations.append("# Advanced CoreML Configuration")
        recommendations.append("export COREML_DEVICE_TYPE=CPUAndNeuralEngine")
        recommendations.append("export COREML_ENABLE_FAST_PATH=false")
        recommendations.append("")
        
        # System-specific recommendations
        recommendations.extend(self.recommendations)
        
        return recommendations
    
    def run_comprehensive_diagnosis(self) -> Dict[str, Any]:
        """Run comprehensive CoreML diagnosis."""
        
        logger.info("🚀 Starting comprehensive CoreML diagnosis...")
        
        diagnosis = {
            'timestamp': str(os.popen('date').read().strip()),
            'system_requirements': self.check_system_requirements(),
            'package_installation': self.check_package_installation(),
            'model_files': self.check_model_files(),
            'coreml_functionality': self.test_coreml_functionality(),
            'issues_summary': [],
            'recommendations': []
        }
        
        # Collect all issues
        for section_name, section_results in diagnosis.items():
            if isinstance(section_results, dict) and 'issues' in section_results:
                diagnosis['issues_summary'].extend(section_results['issues'])
                if 'recommendations' in section_results:
                    diagnosis['recommendations'].extend(section_results['recommendations'])
        
        # Generate troubleshooting recommendations
        diagnosis['troubleshooting_recommendations'] = self.generate_troubleshooting_recommendations()
        
        # Overall assessment
        total_issues = len(diagnosis['issues_summary'])
        diagnosis['overall_status'] = 'healthy' if total_issues == 0 else 'issues_found'
        
        if total_issues == 0:
            logger.info("✅ No issues found - CoreML should work optimally!")
        else:
            logger.warning(f"⚠️ Found {total_issues} issues that may affect CoreML performance")
        
        return diagnosis
    
    def print_comprehensive_report(self, diagnosis: Dict[str, Any]):
        """Print a comprehensive troubleshooting report."""
        
        print("\n" + "="*70)
        print("🔍 COMPREHENSIVE COREML TROUBLESHOOTING REPORT")
        print("="*70)
        
        print(f"\n📅 Generated: {diagnosis['timestamp']}")
        print(f"🎯 Overall Status: {diagnosis['overall_status'].upper()}")
        
        # System summary
        sys_req = diagnosis['system_requirements']
        capabilities = sys_req.get('capabilities', {})
        print(f"\n🖥️  SYSTEM SUMMARY:")
        print(f"   Platform: {sys_req['platform']}")
        print(f"   Apple Silicon: {capabilities.get('is_apple_silicon', 'unknown')}")
        print(f"   Neural Engine: {capabilities.get('has_neural_engine', 'unknown')}")
        print(f"   CPU Cores: {capabilities.get('cpu_cores', 'unknown')}")
        print(f"   Memory: {capabilities.get('memory_gb', 'unknown')}GB")
        
        # Package status
        pkg_info = diagnosis['package_installation']
        print(f"\n📦 PACKAGE STATUS:")
        for pkg, info in pkg_info.get('packages', {}).items():
            if info.get('installed', False):
                print(f"   ✅ {pkg}: {info.get('version', 'unknown')}")
            else:
                print(f"   ❌ {pkg}: Missing")
        
        # Model files
        model_info = diagnosis['model_files']
        print(f"\n📁 MODEL FILES:")
        for model_type, info in model_info.get('model_status', {}).items():
            if info.get('exists', False):
                size = info.get('size_mb', 0)
                print(f"   ✅ {model_type}: {info['path']} ({size:.1f}MB)")
            else:
                print(f"   ❌ {model_type}: {info.get('path', 'unknown')} (missing)")
        
        # CoreML functionality
        coreml_info = diagnosis['coreml_functionality']
        print(f"\n🔧 COREML FUNCTIONALITY:")
        for test_name, result in coreml_info.get('session_creation', {}).items():
            if result.get('success', False):
                active = result.get('coreml_active', False)
                status = "✅ Active" if active else "⚠️ Fallback"
                print(f"   {status} {test_name}")
            else:
                print(f"   ❌ {test_name}: {result.get('error', 'unknown')}")
        
        # Issues summary
        issues = diagnosis['issues_summary']
        if issues:
            print(f"\n⚠️  ISSUES FOUND ({len(issues)}):")
            for issue in issues:
                print(f"   • {issue}")
        
        # Recommendations
        recommendations = diagnosis['recommendations']
        if recommendations:
            print(f"\n💡 RECOMMENDATIONS:")
            for rec in recommendations:
                print(f"   • {rec}")
        
        # Troubleshooting steps
        print(f"\n🔧 TROUBLESHOOTING STEPS:")
        for step in diagnosis['troubleshooting_recommendations']:
            print(f"   {step}")
        
        print("\n" + "="*70)
        print("✅ Report complete! Follow the troubleshooting steps above.")
        print("="*70)
    
    def cleanup(self):
        """Clean up temporary files."""
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
            logger.debug(f"🧹 Cleaned up temp directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to cleanup temp directory: {e}")

def main():
    """Main troubleshooting function."""
    
    print("🔍 Comprehensive CoreML Troubleshooting Tool")
    print("=" * 60)
    
    troubleshooter = CoreMLTroubleshooter()
    
    try:
        # Run comprehensive diagnosis
        diagnosis = troubleshooter.run_comprehensive_diagnosis()
        
        # Print comprehensive report
        troubleshooter.print_comprehensive_report(diagnosis)
        
        # Save report to file
        report_file = ".cache/coreml_troubleshooting_report.json"
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(diagnosis, f, indent=2)
        
        print(f"\n📄 Full diagnosis saved to: {report_file}")
        
        # Return appropriate exit code
        return 0 if diagnosis['overall_status'] == 'healthy' else 1
        
    except Exception as e:
        logger.error(f"❌ Troubleshooting failed: {e}")
        return 1
    
    finally:
        troubleshooter.cleanup()

if __name__ == "__main__":
    sys.exit(main()) 