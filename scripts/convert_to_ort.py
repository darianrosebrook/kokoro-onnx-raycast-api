#!/usr/bin/env python3
"""
Standalone ORT Conversion Script

This script provides a command-line interface for converting ONNX models to ORT format
for better CoreML compatibility and performance. It builds on the existing ORT optimization
system but provides manual control for pre-deployment optimization.

@author @darianrosebrook
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Add the parent directory to the path so we can import from the API
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.config import TTSConfig
from api.model.loader import detect_apple_silicon_capabilities

def setup_logging(verbose: bool = False):
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def convert_onnx_to_ort(input_path: str, output_path: str = None, optimize_for_hardware: bool = True):
    """
    Convert ONNX model to ORT format with hardware-specific optimizations.
    
    Args:
        input_path: Path to the input ONNX model
        output_path: Path for the output ORT model (optional)
        optimize_for_hardware: Whether to apply hardware-specific optimizations
    
    Returns:
        str: Path to the created ORT model
    """
    import onnxruntime as ort
    
    logger = logging.getLogger(__name__)
    
    # Validate input
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input model not found: {input_path}")
    
    # Generate output path if not provided
    if output_path is None:
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        output_dir = os.path.dirname(input_path)
        output_path = os.path.join(output_dir, f"{base_name}.ort")
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    logger.info(f"Converting {input_path} to ORT format...")
    logger.info(f"Output path: {output_path}")
    
    try:
        # Create session options with optimization
        session_options = ort.SessionOptions()
        session_options.optimized_model_filepath = output_path
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        # Apply hardware-specific optimizations
        if optimize_for_hardware:
            capabilities = detect_apple_silicon_capabilities()
            logger.info(f"Hardware capabilities: {capabilities}")
            
            if capabilities['is_apple_silicon']:
                logger.info("🍎 Applying Apple Silicon optimizations...")
                session_options.enable_cpu_mem_arena = False
                session_options.enable_mem_pattern = False
                session_options.use_deterministic_compute = True
                session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
                session_options.intra_op_num_threads = 1
                session_options.inter_op_num_threads = 1
        
        # Create session to trigger optimization
        logger.info("🔧 Creating optimized session...")
        session = ort.InferenceSession(input_path, session_options)
        
        # Validate the output was created
        if not os.path.exists(output_path):
            raise RuntimeError("ORT model creation failed - output file not generated")
        
        # Get file sizes for comparison
        input_size = os.path.getsize(input_path) / (1024 * 1024)
        output_size = os.path.getsize(output_path) / (1024 * 1024)
        
        logger.info(f"✅ Conversion successful!")
        logger.info(f"📊 Input size: {input_size:.1f}MB")
        logger.info(f"📊 Output size: {output_size:.1f}MB")
        logger.info(f"📊 Size change: {((output_size - input_size) / input_size * 100):+.1f}%")
        
        # Clean up session
        del session
        
        return output_path
        
    except Exception as e:
        logger.error(f"❌ Conversion failed: {e}")
        # Clean up partial output on failure
        if os.path.exists(output_path):
            os.remove(output_path)
        raise

def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Convert ONNX models to ORT format for better CoreML compatibility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s kokoro-v1.0.int8.onnx
  %(prog)s input.onnx -o output.ort
  %(prog)s input.onnx --no-hardware-optimization
  %(prog)s input.onnx --verbose
        """
    )
    
    parser.add_argument(
        "input_model",
        help="Path to the input ONNX model"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Path for the output ORT model (default: input_name.ort)"
    )
    
    parser.add_argument(
        "--no-hardware-optimization",
        action="store_true",
        help="Disable hardware-specific optimizations"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.verbose)
    
    try:
        # Convert the model
        output_path = convert_onnx_to_ort(
            input_path=args.input_model,
            output_path=args.output,
            optimize_for_hardware=not args.no_hardware_optimization
        )
        
        print(f"\n✅ Successfully converted to: {output_path}")
        print("\n💡 To use the optimized model:")
        print(f"   export KOKORO_ORT_MODEL_PATH={output_path}")
        print("   ./start_development.sh")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Conversion failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 