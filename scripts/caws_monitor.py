#!/usr/bin/env python3
"""
CAWS Compliance Monitor

Continuous monitoring of CAWS compliance metrics with alerts and reporting.
"""

import json
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
import argparse


class CAWSMonitor:
    """CAWS compliance monitoring system."""
    
    def __init__(self, config_path: str = '.caws/monitor_config.json'):
        self.config_path = Path(config_path)
        self.config = self.load_config()
        self.metrics_history = []
        self.alerts = []
    
    def load_config(self) -> Dict[str, Any]:
        """Load monitoring configuration."""
        default_config = {
            'monitoring_interval': 300,  # 5 minutes
            'alert_thresholds': {
                'coverage_drop': 0.05,  # 5% drop
                'mutation_drop': 0.1,   # 10% drop
                'flake_rate_increase': 0.05,  # 5% increase
                'trust_score_drop': 10  # 10 point drop
            },
            'retention_days': 30,
            'alert_channels': ['console', 'file'],
            'baseline_metrics': {
                'coverage': 0.23,
                'mutation_score': 1.0,
                'flake_rate': 0.14,
                'trust_score': 76
            }
        }
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                # Merge with defaults
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
            except Exception as e:
                print(f"Warning: Could not load config: {e}")
        
        return default_config
    
    def save_config(self):
        """Save monitoring configuration."""
        self.config_path.parent.mkdir(exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def collect_metrics(self) -> Dict[str, Any]:
        """Collect current CAWS metrics."""
        metrics = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'coverage': self.get_coverage_metrics(),
            'mutation': self.get_mutation_metrics(),
            'tests': self.get_test_metrics(),
            'contracts': self.get_contract_metrics(),
            'ci': self.get_ci_metrics(),
            'trust_score': 0
        }
        
        # Calculate trust score
        metrics['trust_score'] = self.calculate_trust_score(metrics)
        
        return metrics
    
    def get_coverage_metrics(self) -> Dict[str, Any]:
        """Get coverage metrics."""
        coverage_path = Path('coverage.xml')
        if not coverage_path.exists():
            return {'status': 'missing', 'line_coverage': 0, 'branch_coverage': 0}
        
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(coverage_path)
            root = tree.getroot()
            
            return {
                'status': 'available',
                'line_coverage': float(root.get('line-rate', 0)),
                'branch_coverage': float(root.get('branch-rate', 0)),
                'total_lines': int(root.get('lines-valid', 0)),
                'covered_lines': int(root.get('lines-covered', 0))
            }
        except Exception as e:
            return {'status': 'error', 'line_coverage': 0, 'branch_coverage': 0}
    
    def get_mutation_metrics(self) -> Dict[str, Any]:
        """Get mutation testing metrics."""
        mutation_path = Path('mutmut-results.json')
        if not mutation_path.exists():
            return {'status': 'missing', 'score': 0, 'total': 0, 'killed': 0}
        
        try:
            with open(mutation_path, 'r') as f:
                data = json.load(f)
            
            return {
                'status': 'available',
                'score': data.get('mutation_score', 0),
                'total': data.get('total_mutations', 0),
                'killed': data.get('killed_mutations', 0),
                'survived': data.get('survived_mutations', 0)
            }
        except Exception as e:
            return {'status': 'error', 'score': 0, 'total': 0, 'killed': 0}
    
    def get_test_metrics(self) -> Dict[str, Any]:
        """Get test execution metrics."""
        # This would typically parse recent test results
        # For now, return current known state
        return {
            'status': 'recent_run',
            'total_tests': 218,
            'passed': 187,
            'failed': 31,
            'flake_rate': 0.14
        }
    
    def get_contract_metrics(self) -> Dict[str, Any]:
        """Get contract testing metrics."""
        contracts_dir = Path('contracts')
        return {
            'status': 'available' if contracts_dir.exists() else 'missing',
            'provider': contracts_dir.exists(),
            'consumer': contracts_dir.exists(),
            'openapi_spec': (contracts_dir / 'kokoro-tts-api.yaml').exists()
        }
    
    def get_ci_metrics(self) -> Dict[str, Any]:
        """Get CI/CD pipeline metrics."""
        workflow_path = Path('.github/workflows/caws.yml')
        return {
            'status': 'configured' if workflow_path.exists() else 'missing',
            'workflow_exists': workflow_path.exists()
        }
    
    def calculate_trust_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate trust score from metrics."""
        weights = {
            'coverage': 0.25,
            'mutation': 0.25,
            'test_stability': 0.2,
            'contracts': 0.15,
            'ci_pipeline': 0.15
        }
        
        coverage_score = min(1.0, metrics['coverage'].get('line_coverage', 0) / 0.8)
        mutation_score = min(1.0, metrics['mutation'].get('score', 0) / 0.5)
        test_score = 1.0 if metrics['tests'].get('flake_rate', 1) < 0.05 else 0.5
        contract_score = 1.0 if metrics['contracts'].get('provider', False) else 0.0
        ci_score = 1.0 if metrics['ci'].get('workflow_exists', False) else 0.0
        
        trust_score = (
            weights['coverage'] * coverage_score +
            weights['mutation'] * mutation_score +
            weights['test_stability'] * test_score +
            weights['contracts'] * contract_score +
            weights['ci_pipeline'] * ci_score
        ) * 100
        
        return trust_score
    
    def check_alerts(self, current_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for alert conditions."""
        new_alerts = []
        thresholds = self.config['alert_thresholds']
        baseline = self.config['baseline_metrics']
        
        # Coverage drop alert
        if current_metrics['coverage']['line_coverage'] < baseline['coverage'] - thresholds['coverage_drop']:
            new_alerts.append({
                'type': 'coverage_drop',
                'severity': 'warning',
                'message': f"Coverage dropped to {current_metrics['coverage']['line_coverage']:.1%}",
                'timestamp': current_metrics['timestamp']
            })
        
        # Mutation score drop alert
        if current_metrics['mutation']['score'] < baseline['mutation_score'] - thresholds['mutation_drop']:
            new_alerts.append({
                'type': 'mutation_drop',
                'severity': 'critical',
                'message': f"Mutation score dropped to {current_metrics['mutation']['score']:.1%}",
                'timestamp': current_metrics['timestamp']
            })
        
        # Flake rate increase alert
        if current_metrics['tests']['flake_rate'] > baseline['flake_rate'] + thresholds['flake_rate_increase']:
            new_alerts.append({
                'type': 'flake_rate_increase',
                'severity': 'warning',
                'message': f"Flake rate increased to {current_metrics['tests']['flake_rate']:.1%}",
                'timestamp': current_metrics['timestamp']
            })
        
        # Trust score drop alert
        if current_metrics['trust_score'] < baseline['trust_score'] - thresholds['trust_score_drop']:
            new_alerts.append({
                'type': 'trust_score_drop',
                'severity': 'critical',
                'message': f"Trust score dropped to {current_metrics['trust_score']:.0f}",
                'timestamp': current_metrics['timestamp']
            })
        
        return new_alerts
    
    def save_metrics(self, metrics: Dict[str, Any]):
        """Save metrics to history."""
        self.metrics_history.append(metrics)
        
        # Clean up old metrics
        cutoff_date = datetime.utcnow() - timedelta(days=self.config['retention_days'])
        self.metrics_history = [
            m for m in self.metrics_history
            if datetime.fromisoformat(m['timestamp'].replace('Z', '')) > cutoff_date
        ]
        
        # Save to file
        metrics_path = Path('.agent/metrics_history.json')
        metrics_path.parent.mkdir(exist_ok=True)
        with open(metrics_path, 'w') as f:
            json.dump(self.metrics_history, f, indent=2)
    
    def send_alerts(self, alerts: List[Dict[str, Any]]):
        """Send alerts through configured channels."""
        for alert in alerts:
            self.alerts.append(alert)
            
            # Console alert
            if 'console' in self.config['alert_channels']:
                severity_emoji = "🔴" if alert['severity'] == 'critical' else "🟡"
                print(f"{severity_emoji} ALERT: {alert['message']}")
            
            # File alert
            if 'file' in self.config['alert_channels']:
                alerts_path = Path('.agent/alerts.json')
                alerts_path.parent.mkdir(exist_ok=True)
                
                existing_alerts = []
                if alerts_path.exists():
                    with open(alerts_path, 'r') as f:
                        existing_alerts = json.load(f)
                
                existing_alerts.append(alert)
                with open(alerts_path, 'w') as f:
                    json.dump(existing_alerts, f, indent=2)
    
    def generate_report(self) -> str:
        """Generate monitoring report."""
        if not self.metrics_history:
            return "No metrics available for reporting."
        
        latest = self.metrics_history[-1]
        baseline = self.config['baseline_metrics']
        
        report = f"""
CAWS Compliance Monitoring Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Current Metrics:
- Trust Score: {latest['trust_score']:.0f}/100 (baseline: {baseline['trust_score']})
- Coverage: {latest['coverage']['line_coverage']:.1%} (baseline: {baseline['coverage']:.1%})
- Mutation Score: {latest['mutation']['score']:.1%} (baseline: {baseline['mutation_score']:.1%})
- Flake Rate: {latest['tests']['flake_rate']:.1%} (baseline: {baseline['flake_rate']:.1%})

Recent Alerts: {len(self.alerts)}
Metrics History: {len(self.metrics_history)} entries
"""
        return report
    
    def run_monitoring_cycle(self):
        """Run a single monitoring cycle."""
        print(f"🔍 Collecting CAWS metrics at {datetime.now().strftime('%H:%M:%S')}")
        
        # Collect metrics
        metrics = self.collect_metrics()
        
        # Check for alerts
        alerts = self.check_alerts(metrics)
        
        # Send alerts
        if alerts:
            self.send_alerts(alerts)
        
        # Save metrics
        self.save_metrics(metrics)
        
        # Print summary
        print(f"📊 Trust Score: {metrics['trust_score']:.0f}/100")
        if alerts:
            print(f"⚠️  {len(alerts)} new alerts")
        
        return metrics
    
    def run_continuous_monitoring(self):
        """Run continuous monitoring."""
        print("🚀 Starting CAWS compliance monitoring...")
        print(f"📅 Monitoring interval: {self.config['monitoring_interval']} seconds")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                self.run_monitoring_cycle()
                time.sleep(self.config['monitoring_interval'])
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
        except Exception as e:
            print(f"❌ Monitoring error: {e}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='CAWS Compliance Monitor')
    parser.add_argument('--config', default='.caws/monitor_config.json', help='Config file path')
    parser.add_argument('--once', action='store_true', help='Run once instead of continuous')
    parser.add_argument('--report', action='store_true', help='Generate report only')
    
    args = parser.parse_args()
    
    monitor = CAWSMonitor(args.config)
    
    if args.report:
        print(monitor.generate_report())
    elif args.once:
        monitor.run_monitoring_cycle()
    else:
        monitor.run_continuous_monitoring()


if __name__ == "__main__":
    main()
