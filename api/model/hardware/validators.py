"""
Hardware validation utilities.

This module provides validation functions for hardware requirements
and system compatibility checks.
"""

import logging
from typing import Dict, Any, List, Optional


def validate_hardware_requirements(capabilities: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Validate that the system meets minimum hardware requirements.
    
    @param capabilities: Hardware capabilities dict (auto-detected if not provided)
    @returns Dict[str, Any]: Validation results with recommendations
    """
    logger = logging.getLogger(__name__)
    
    if capabilities is None:
        from .detection import detect_apple_silicon_capabilities
        capabilities = detect_apple_silicon_capabilities()
    
    validation_results = {
        'meets_requirements': True,
        'warnings': [],
        'errors': [],
        'recommendations': []
    }
    
    # Check minimum memory requirements
    memory_gb = capabilities.get('memory_gb', 0)
    if memory_gb < 4:
        validation_results['meets_requirements'] = False
        validation_results['errors'].append(
            f"Insufficient memory: {memory_gb}GB (minimum 4GB required)")
    elif memory_gb < 8:
        validation_results['warnings'].append(
            f"Low memory: {memory_gb}GB (8GB+ recommended for optimal performance)")
        validation_results['recommendations'].append(
            "Consider upgrading memory for better performance")
    
    # Check CPU core requirements
    cpu_cores = capabilities.get('cpu_cores', 0)
    if cpu_cores < 2:
        validation_results['meets_requirements'] = False
        validation_results['errors'].append(
            f"Insufficient CPU cores: {cpu_cores} (minimum 2 required)")
    elif cpu_cores < 4:
        validation_results['warnings'].append(
            f"Low CPU cores: {cpu_cores} (4+ recommended)")
    
    # Check for Apple Silicon benefits
    if capabilities.get('is_apple_silicon', False):
        if capabilities.get('has_neural_engine', False):
            validation_results['recommendations'].append(
                "Neural Engine detected - CoreML provider recommended for optimal performance")
        else:
            validation_results['warnings'].append(
                "Apple Silicon detected but Neural Engine not available")
    else:
        validation_results['recommendations'].append(
            "Consider upgrading to Apple Silicon for enhanced performance")
    
    # Check for hardware issues
    hardware_issues = capabilities.get('hardware_issues', [])
    if hardware_issues:
        validation_results['warnings'].extend([
            f"Hardware issue: {issue}" for issue in hardware_issues
        ])
    
    # Check provider availability
    provider_priority = capabilities.get('provider_priority', [])
    if not provider_priority:
        validation_results['meets_requirements'] = False
        validation_results['errors'].append("No ONNX Runtime providers available")
    elif 'CPUExecutionProvider' not in provider_priority:
        validation_results['warnings'].append("CPU provider not available as fallback")
    
    logger.info(f"Hardware validation: {'✅ PASSED' if validation_results['meets_requirements'] else ' FAILED'}")
    
    return validation_results


def validate_provider_compatibility(provider_name: str, capabilities: Optional[Dict[str, Any]] = None) -> bool:
    """
    Validate that a specific provider is compatible with the current hardware.
    
    @param provider_name: Name of the provider to validate
    @param capabilities: Hardware capabilities dict (auto-detected if not provided)
    @returns bool: True if provider is compatible
    """
    if capabilities is None:
        from .detection import detect_apple_silicon_capabilities
        capabilities = detect_apple_silicon_capabilities()
    
    available_providers = capabilities.get('available_providers', [])
    
    # Basic availability check
    if provider_name not in available_providers:
        return False
    
    # Provider-specific compatibility checks
    if provider_name == 'CoreMLExecutionProvider':
        # CoreML requires Apple Silicon and Neural Engine
        return (capabilities.get('is_apple_silicon', False) and 
                capabilities.get('has_neural_engine', False))
    
    elif provider_name == 'CPUExecutionProvider':
        # CPU provider should work on all systems
        return True
    
    # Other providers - basic availability check
    return True


def get_optimal_provider_recommendation(capabilities: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get optimal provider recommendation based on hardware capabilities.
    
    @param capabilities: Hardware capabilities dict (auto-detected if not provided)
    @returns Dict[str, Any]: Provider recommendation with reasoning
    """
    if capabilities is None:
        from .detection import detect_apple_silicon_capabilities
        capabilities = detect_apple_silicon_capabilities()
    
    recommendation = {
        'primary_provider': 'CPUExecutionProvider',
        'fallback_providers': [],
        'reasoning': [],
        'performance_estimate': 'baseline'
    }
    
    # Apple Silicon optimization
    if capabilities.get('is_apple_silicon', False):
        if capabilities.get('has_neural_engine', False):
            if validate_provider_compatibility('CoreMLExecutionProvider', capabilities):
                recommendation['primary_provider'] = 'CoreMLExecutionProvider'
                recommendation['fallback_providers'] = ['CPUExecutionProvider']
                recommendation['reasoning'].append(
                    "Apple Silicon with Neural Engine detected - CoreML optimal")
                recommendation['performance_estimate'] = 'excellent'
        
        # CPU fallback for Apple Silicon
        if validate_provider_compatibility('CPUExecutionProvider', capabilities):
            if 'CPUExecutionProvider' not in recommendation['fallback_providers']:
                recommendation['fallback_providers'].append('CPUExecutionProvider')
    
    # Memory-based adjustments
    memory_gb = capabilities.get('memory_gb', 8)
    if memory_gb >= 16:
        recommendation['reasoning'].append(
            f"High memory ({memory_gb}GB) - can handle complex models")
    elif memory_gb < 8:
        recommendation['reasoning'].append(
            f"Limited memory ({memory_gb}GB) - may need conservative settings")
        if recommendation['performance_estimate'] == 'excellent':
            recommendation['performance_estimate'] = 'good'
    
    # CPU core adjustments
    cpu_cores = capabilities.get('cpu_cores', 4)
    if cpu_cores >= 8:
        recommendation['reasoning'].append(
            f"Multi-core CPU ({cpu_cores} cores) - good for CPU provider")
    elif cpu_cores < 4:
        recommendation['reasoning'].append(
            f"Limited CPU cores ({cpu_cores}) - may impact performance")
    
    return recommendation


def diagnose_hardware_issues(capabilities: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Diagnose potential hardware-related performance issues.
    
    @param capabilities: Hardware capabilities dict (auto-detected if not provided)
    @returns Dict[str, Any]: Diagnostic results with suggested fixes
    """
    if capabilities is None:
        from .detection import detect_apple_silicon_capabilities
        capabilities = detect_apple_silicon_capabilities()
    
    diagnosis = {
        'issues_found': [],
        'suggested_fixes': [],
        'performance_impact': 'none',
        'confidence': 'high'
    }
    
    # Check for known hardware issues
    hardware_issues = capabilities.get('hardware_issues', [])
    if hardware_issues:
        diagnosis['issues_found'].extend(hardware_issues)
        diagnosis['performance_impact'] = 'moderate'
        
        for issue in hardware_issues:
            if 'CoreML provider unavailable' in issue:
                diagnosis['suggested_fixes'].append(
                    "Install onnxruntime-coreml for Apple Silicon optimization")
            elif 'Neural Engine not available' in issue:
                diagnosis['suggested_fixes'].append(
                    "Verify Apple Silicon system and macOS version compatibility")
    
    # Memory pressure checks
    memory_gb = capabilities.get('memory_gb', 8)
    if memory_gb < 6:
        diagnosis['issues_found'].append(f"Low system memory: {memory_gb}GB")
        diagnosis['suggested_fixes'].append(
            "Close unnecessary applications to free memory")
        diagnosis['performance_impact'] = 'high'
    
    # Provider availability issues
    available_providers = capabilities.get('available_providers', [])
    if len(available_providers) < 2:
        diagnosis['issues_found'].append("Limited provider options available")
        diagnosis['suggested_fixes'].append(
            "Install additional ONNX Runtime providers for better fallback options")
        diagnosis['confidence'] = 'medium'
    
    return diagnosis
