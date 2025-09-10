#!/usr/bin/env python3
"""
Baseline Performance Comparison Script

This script allows you to compare current TTS performance against a baseline commit
to validate the claimed optimization improvements. It can automatically checkout
a previous commit, run performance tests, and provide detailed comparisons.

## Usage

```bash
# Compare against specific commit
python scripts/baseline_comparison.py --baseline-commit abc123

# Compare against commit from X days ago
python scripts/baseline_comparison.py --days-ago 7

# Compare against specific branch
python scripts/baseline_comparison.py --baseline-branch pre-optimization

# Interactive mode to find the right baseline
python scripts/baseline_comparison.py --interactive
```

@author @darianrosebrook
@date 2025-07-10
@version 1.0.0
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )


class BaselineComparator:
    """
    Performance comparison system for validating TTS optimizations.
    
    This class provides comprehensive baseline comparison capabilities to validate
    optimization claims by comparing current performance against historical baselines.
    """
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Git repository information
        self.repo_root = Path.cwd()
        self.current_branch = None
        self.baseline_results = {}
        self.current_results = {}
        
        # Ensure we're in a git repository
        if not (self.repo_root / '.git').exists():
            raise RuntimeError("Not in a git repository")
    
    def get_git_info(self) -> Dict[str, str]:
        """Get current git repository information."""
        try:
            # Get current branch
            result = subprocess.run(['git', 'branch', '--show-current'], 
                                  capture_output=True, text=True, check=True)
            current_branch = result.stdout.strip()
            
            # Get current commit hash
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  capture_output=True, text=True, check=True)
            current_commit = result.stdout.strip()
            
            # Get current commit date
            result = subprocess.run(['git', 'log', '-1', '--format=%ci'], 
                                  capture_output=True, text=True, check=True)
            current_date = result.stdout.strip()
            
            return {
                'branch': current_branch,
                'commit': current_commit,
                'date': current_date,
                'short_commit': current_commit[:8]
            }
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to get git info: {e}")
            raise
    
    def find_baseline_commit(self, days_ago: int = 7) -> Optional[str]:
        """Find a commit from N days ago as baseline."""
        try:
            # Get commit from N days ago
            date_ago = datetime.now() - timedelta(days=days_ago)
            date_str = date_ago.strftime('%Y-%m-%d')
            
            result = subprocess.run([
                'git', 'log', '--until', date_str, '--format=%H', '-1'
            ], capture_output=True, text=True, check=True)
            
            commit_hash = result.stdout.strip()
            if commit_hash:
                self.logger.info(f"Found baseline commit from {days_ago} days ago: {commit_hash[:8]}")
                return commit_hash
            else:
                self.logger.warning(f"No commits found from {days_ago} days ago")
                return None
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to find baseline commit: {e}")
            return None
    
    def list_recent_commits(self, limit: int = 10) -> List[Dict[str, str]]:
        """List recent commits for interactive selection."""
        try:
            result = subprocess.run([
                'git', 'log', '--oneline', f'-{limit}', '--format=%H|%s|%ci'
            ], capture_output=True, text=True, check=True)
            
            commits = []
            for line in result.stdout.strip().split('\n'):
                if '|' in line:
                    parts = line.split('|', 2)
                    if len(parts) >= 3:
                        commits.append({
                            'hash': parts[0],
                            'message': parts[1],
                            'date': parts[2],
                            'short_hash': parts[0][:8]
                        })
            
            return commits
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to list commits: {e}")
            return []
    
    def interactive_baseline_selection(self) -> Optional[str]:
        """Interactive baseline commit selection."""
        commits = self.list_recent_commits(20)
        
        if not commits:
            self.logger.error("No commits found for selection")
            return None
        
        print("\n" + "="*80)
        print("INTERACTIVE BASELINE SELECTION")
        print("="*80)
        print("\nRecent commits (select a baseline for comparison):")
        print("-"*80)
        
        for i, commit in enumerate(commits):
            print(f"{i+1:2d}. {commit['short_hash']} - {commit['message'][:50]}")
            print(f"    Date: {commit['date']}")
            print()
        
        while True:
            try:
                choice = input(f"Select commit (1-{len(commits)}) or 'q' to quit: ").strip()
                if choice.lower() == 'q':
                    return None
                
                index = int(choice) - 1
                if 0 <= index < len(commits):
                    selected_commit = commits[index]
                    print(f"\nSelected: {selected_commit['short_hash']} - {selected_commit['message']}")
                    confirm = input("Confirm selection? (y/n): ").strip().lower()
                    if confirm == 'y':
                        return selected_commit['hash']
                else:
                    print("Invalid selection. Please try again.")
            except (ValueError, KeyboardInterrupt):
                print("\nSelection cancelled.")
                return None
    
    def checkout_commit(self, commit_hash: str) -> bool:
        """Checkout a specific commit."""
        try:
            self.logger.info(f"Checking out commit: {commit_hash[:8]}")
            
            # Stash any uncommitted changes
            subprocess.run(['git', 'stash', '-u'], capture_output=True, check=False)
            
            # Checkout the commit
            result = subprocess.run(['git', 'checkout', commit_hash], 
                                  capture_output=True, text=True, check=True)
            
            self.logger.info(f"✅ Checked out commit: {commit_hash[:8]}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to checkout commit: {e}")
            return False
    
    def restore_current_branch(self) -> bool:
        """Restore the original branch."""
        try:
            if self.current_branch:
                self.logger.info(f"Restoring branch: {self.current_branch}")
                subprocess.run(['git', 'checkout', self.current_branch], 
                              capture_output=True, text=True, check=True)
                
                # Restore stashed changes if any
                result = subprocess.run(['git', 'stash', 'pop'], 
                                      capture_output=True, text=True, check=False)
                
                self.logger.info(f"✅ Restored branch: {self.current_branch}")
                return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to restore branch: {e}")
            return False
    
    def run_performance_test(self, test_name: str = "baseline") -> Dict[str, any]:
        """Run performance test for current state."""
        self.logger.info(f" Running {test_name} performance test...")
        
        try:
            # Import here to avoid issues with different commit states
            from validate_optimization_performance import PerformanceValidator
            
            # Run quick validation
            validator = PerformanceValidator(quick_mode=True, verbose=self.verbose)
            
            # Get system capabilities
            capabilities = validator.detect_system_capabilities()
            
            # Run basic performance tests
            features = validator.validate_optimization_features()
            inference_perf = validator.measure_inference_performance()
            memory_usage = validator.measure_memory_usage()
            
            # Compile results
            results = {
                'test_name': test_name,
                'timestamp': datetime.now().isoformat(),
                'git_info': self.get_git_info(),
                'system_capabilities': capabilities,
                'optimization_features': features,
                'inference_performance': inference_perf,
                'memory_usage': memory_usage
            }
            
            self.logger.info(f"✅ {test_name} test completed")
            return results
            
        except Exception as e:
            self.logger.error(f" {test_name} test failed: {e}")
            return {
                'test_name': test_name,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def compare_results(self, baseline_results: Dict, current_results: Dict) -> Dict[str, any]:
        """Compare baseline and current results."""
        self.logger.info(" Comparing performance results...")
        
        comparison = {
            'baseline_info': {
                'commit': baseline_results.get('git_info', {}).get('short_commit', 'unknown'),
                'date': baseline_results.get('git_info', {}).get('date', 'unknown')
            },
            'current_info': {
                'commit': current_results.get('git_info', {}).get('short_commit', 'unknown'),
                'date': current_results.get('git_info', {}).get('date', 'unknown')
            },
            'improvements': {},
            'regressions': {},
            'summary': {}
        }
        
        # Compare inference performance
        baseline_inference = baseline_results.get('inference_performance', {})
        current_inference = current_results.get('inference_performance', {})
        
        for text_type in ['short', 'medium', 'long']:
            if (text_type in baseline_inference and text_type in current_inference and
                'mean_time' in baseline_inference[text_type] and 
                'mean_time' in current_inference[text_type]):
                
                baseline_time = baseline_inference[text_type]['mean_time']
                current_time = current_inference[text_type]['mean_time']
                
                if baseline_time > 0:
                    improvement = ((baseline_time - current_time) / baseline_time) * 100
                    
                    comparison['improvements'][f'{text_type}_inference'] = {
                        'baseline': baseline_time,
                        'current': current_time,
                        'improvement_percent': improvement,
                        'faster_by': baseline_time - current_time
                    }
        
        # Compare memory usage
        baseline_memory = baseline_results.get('memory_usage', {})
        current_memory = current_results.get('memory_usage', {})
        
        if ('memory_increase_mb' in baseline_memory and 
            'memory_increase_mb' in current_memory):
            
            baseline_mem = baseline_memory['memory_increase_mb']
            current_mem = current_memory['memory_increase_mb']
            
            if baseline_mem > 0:
                mem_improvement = ((baseline_mem - current_mem) / baseline_mem) * 100
                
                comparison['improvements']['memory_usage'] = {
                    'baseline': baseline_mem,
                    'current': current_mem,
                    'improvement_percent': mem_improvement,
                    'reduction_mb': baseline_mem - current_mem
                }
        
        # Calculate overall summary
        improvements = list(comparison['improvements'].values())
        if improvements:
            avg_improvement = sum(imp.get('improvement_percent', 0) for imp in improvements) / len(improvements)
            comparison['summary']['average_improvement'] = avg_improvement
            comparison['summary']['total_improvements'] = len(improvements)
        
        return comparison
    
    def generate_comparison_report(self, comparison: Dict) -> str:
        """Generate a detailed comparison report."""
        
        report_lines = [
            "# TTS Performance Baseline Comparison Report",
            "",
            f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Comparison Summary",
            "",
            f"**Baseline**: {comparison['baseline_info']['commit']} ({comparison['baseline_info']['date']})",
            f"**Current**: {comparison['current_info']['commit']} ({comparison['current_info']['date']})",
            "",
        ]
        
        # Overall summary
        summary = comparison.get('summary', {})
        if 'average_improvement' in summary:
            avg_improvement = summary['average_improvement']
            if avg_improvement > 0:
                report_lines.append(f"**Overall Performance**: ✅ {avg_improvement:.1f}% improvement")
            else:
                report_lines.append(f"**Overall Performance**:  {abs(avg_improvement):.1f}% regression")
        
        report_lines.append("")
        
        # Detailed improvements
        improvements = comparison.get('improvements', {})
        if improvements:
            report_lines.extend([
                "## Performance Improvements",
                "",
                "| Metric | Baseline | Current | Improvement |",
                "|--------|----------|---------|-------------|",
            ])
            
            for metric_name, metric_data in improvements.items():
                baseline_val = metric_data['baseline']
                current_val = metric_data['current']
                improvement = metric_data['improvement_percent']
                
                if 'inference' in metric_name:
                    baseline_str = f"{baseline_val:.3f}s"
                    current_str = f"{current_val:.3f}s"
                elif 'memory' in metric_name:
                    baseline_str = f"{baseline_val:.1f}MB"
                    current_str = f"{current_val:.1f}MB"
                else:
                    baseline_str = str(baseline_val)
                    current_str = str(current_val)
                
                status = "✅" if improvement > 0 else ""
                report_lines.append(
                    f"| {metric_name.replace('_', ' ').title()} | {baseline_str} | {current_str} | "
                    f"{status} {improvement:+.1f}% |"
                )
            
            report_lines.append("")
        
        # Validation against claims
        report_lines.extend([
            "## Optimization Claims Validation",
            "",
        ])
        
        # Check specific claims
        claims_validated = 0
        total_claims = 4
        
        # Claim 1: 50-70% inference reduction
        inference_improvements = [v for k, v in improvements.items() if 'inference' in k]
        if inference_improvements:
            avg_inference_improvement = sum(imp['improvement_percent'] for imp in inference_improvements) / len(inference_improvements)
            if 50 <= avg_inference_improvement <= 70:
                report_lines.append("✅ **Inference Time Reduction**: 50-70% claim validated")
                claims_validated += 1
            elif avg_inference_improvement > 0:
                report_lines.append(f" **Inference Time Reduction**: {avg_inference_improvement:.1f}% improvement (claim: 50-70%)")
            else:
                report_lines.append(" **Inference Time Reduction**: No improvement detected")
        else:
            report_lines.append(" **Inference Time Reduction**: Could not validate (no data)")
        
        # Claim 2: 30% memory reduction
        if 'memory_usage' in improvements:
            mem_improvement = improvements['memory_usage']['improvement_percent']
            if mem_improvement >= 30:
                report_lines.append("✅ **Memory Usage Reduction**: 30% claim validated")
                claims_validated += 1
            elif mem_improvement > 0:
                report_lines.append(f" **Memory Usage Reduction**: {mem_improvement:.1f}% improvement (claim: 30%)")
            else:
                report_lines.append(" **Memory Usage Reduction**: No improvement detected")
        else:
            report_lines.append(" **Memory Usage Reduction**: Could not validate (no data)")
        
        # Add remaining claims (would need throughput/latency data)
        report_lines.extend([
            " **Throughput Increase**: 2x claim (requires API throughput test)",
            " **P95 Latency Reduction**: 70% claim (requires latency distribution test)",
            "",
            f"**Claims Validated**: {claims_validated}/{total_claims}",
            "",
        ])
        
        # Recommendations
        report_lines.extend([
            "## Recommendations",
            "",
        ])
        
        if claims_validated >= 2:
            report_lines.append("✅ **Good Progress**: Major optimization claims are being validated")
        elif claims_validated >= 1:
            report_lines.append(" **Partial Success**: Some optimizations working, others need attention")
        else:
            report_lines.append(" **Needs Work**: Optimization claims not validated by testing")
        
        report_lines.extend([
            "",
            "### Next Steps",
            "",
            "1. **Complete Testing**: Run full API throughput and latency tests",
            "2. **Performance Monitoring**: Set up continuous performance monitoring",
            "3. **Optimization Tuning**: Fine-tune optimizations based on results",
            "",
            "---",
            "*Report generated by TTS Baseline Comparison Tool*"
        ])
        
        return "\n".join(report_lines)
    
    def save_results(self, comparison: Dict, output_prefix: str = "comparison") -> str:
        """Save comparison results."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create reports directory
        reports_dir = Path("reports/comparison")
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Save JSON results
        json_file = reports_dir / f"{output_prefix}_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump(comparison, f, indent=2, default=str)
        
        # Save markdown report
        md_file = reports_dir / f"{output_prefix}_{timestamp}.md"
        report_content = self.generate_comparison_report(comparison)
        with open(md_file, 'w') as f:
            f.write(report_content)
        
        self.logger.info(f"✅ Comparison saved to {json_file}")
        self.logger.info(f"✅ Report saved to {md_file}")
        
        return str(md_file)


def main():
    """Main function for baseline comparison."""
    parser = argparse.ArgumentParser(
        description="Compare TTS performance against baseline commit",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--baseline-commit', type=str, help='Baseline commit hash')
    parser.add_argument('--days-ago', type=int, default=7, help='Days ago for baseline (default: 7)')
    parser.add_argument('--baseline-branch', type=str, help='Baseline branch name')
    parser.add_argument('--interactive', action='store_true', help='Interactive baseline selection')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    parser.add_argument('--output-prefix', type=str, default='comparison', help='Output file prefix')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger('main')
    
    logger.info(" Starting TTS Baseline Performance Comparison")
    
    try:
        # Initialize comparator
        comparator = BaselineComparator(verbose=args.verbose)
        
        # Get current git info
        current_git_info = comparator.get_git_info()
        comparator.current_branch = current_git_info['branch']
        
        logger.info(f"Current branch: {current_git_info['branch']}")
        logger.info(f"Current commit: {current_git_info['short_commit']}")
        
        # Determine baseline commit
        baseline_commit = None
        
        if args.baseline_commit:
            baseline_commit = args.baseline_commit
        elif args.baseline_branch:
            # Get commit hash for branch
            result = subprocess.run(['git', 'rev-parse', args.baseline_branch], 
                                  capture_output=True, text=True, check=True)
            baseline_commit = result.stdout.strip()
        elif args.interactive:
            baseline_commit = comparator.interactive_baseline_selection()
        else:
            baseline_commit = comparator.find_baseline_commit(args.days_ago)
        
        if not baseline_commit:
            logger.error(" No baseline commit specified or found")
            return 1
        
        logger.info(f"Baseline commit: {baseline_commit[:8]}")
        
        # Run current performance test first
        logger.info("=" * 60)
        current_results = comparator.run_performance_test("current")
        
        # Checkout baseline and test
        logger.info("=" * 60)
        if comparator.checkout_commit(baseline_commit):
            try:
                baseline_results = comparator.run_performance_test("baseline")
            finally:
                # Always restore current branch
                comparator.restore_current_branch()
        else:
            logger.error(" Failed to checkout baseline commit")
            return 1
        
        # Compare results
        logger.info("=" * 60)
        comparison = comparator.compare_results(baseline_results, current_results)
        
        # Save results
        report_file = comparator.save_results(comparison, args.output_prefix)
        
        # Show summary
        logger.info("=" * 60)
        logger.info(" COMPARISON COMPLETE")
        
        summary = comparison.get('summary', {})
        if 'average_improvement' in summary:
            avg_improvement = summary['average_improvement']
            if avg_improvement > 0:
                logger.info(f"✅ Overall Performance: {avg_improvement:.1f}% improvement")
            else:
                logger.info(f" Overall Performance: {abs(avg_improvement):.1f}% regression")
        
        logger.info(f" Detailed Report: {report_file}")
        
        return 0
        
    except Exception as e:
        logger.error(f" Comparison failed: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main()) 