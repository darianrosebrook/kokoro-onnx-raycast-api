#!/usr/bin/env python3
"""
Advanced Load Testing and Stress Testing Framework for Kokoro TTS API.

This script provides comprehensive load testing capabilities including:
- Concurrent request testing
- Stress testing with increasing load
- Endurance testing for memory leaks
- Performance regression testing
- Real-time monitoring and reporting
"""
import asyncio
import aiohttp
import json
import time
import statistics
import sys
import signal
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
import random
import psutil
from concurrent.futures import ThreadPoolExecutor
import matplotlib.pyplot as plt
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class LoadTestResult:
    """Load test result data structure."""
    test_name: str
    start_time: float
    end_time: float
    duration: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    response_times: List[float]
    ttfa_times: List[float]
    error_messages: List[str]
    concurrent_users: int
    requests_per_second: float

@dataclass
class StressTestConfig:
    """Stress test configuration."""
    name: str
    min_users: int
    max_users: int
    ramp_up_seconds: int
    hold_seconds: int
    ramp_down_seconds: int
    requests_per_user: int
    text_length: str  # 'short', 'medium', 'long'
    voice: str
    speed: float
    lang: str

@dataclass
class EnduranceTestConfig:
    """Endurance test configuration."""
    name: str
    duration_hours: int
    concurrent_users: int
    request_interval_seconds: int
    text_length: str
    voice: str
    speed: float
    lang: str

class LoadTester:
    """Advanced load testing framework."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[LoadTestResult] = []
        self.running = False
        
        # Test text samples
        self.test_texts = {
            'short': [
                "Hello, this is a test.",
                "How are you today?",
                "Testing the TTS system.",
                "Short audio generation.",
                "Quick response test."
            ],
            'medium': [
                "This is a medium-length text for testing the TTS system performance under moderate load conditions.",
                "We are conducting comprehensive load testing to ensure the system can handle multiple concurrent requests.",
                "The text-to-speech system should maintain consistent performance even with increased user demand.",
                "Medium-length sentences help us evaluate the system's ability to process moderately complex content.",
                "Load testing with medium text provides insights into the system's scalability and reliability."
            ],
            'long': [
                "This is a comprehensive long-form text designed to test the TTS system's ability to handle extended content generation. The system should maintain consistent performance even when processing lengthy paragraphs that require significant computational resources. This type of testing helps us identify potential bottlenecks in the audio generation pipeline and ensures that the system can handle real-world usage scenarios where users might request synthesis of longer documents or articles. The performance metrics collected during long-text testing provide valuable insights into memory usage, processing time, and overall system stability under sustained load conditions.",
                "Load testing with long-form content is essential for validating the TTS system's scalability and reliability. When users request synthesis of extended text passages, the system must efficiently manage memory allocation, maintain consistent audio quality, and deliver results within acceptable timeframes. This comprehensive testing approach helps identify potential issues such as memory leaks, performance degradation, or resource contention that might not be apparent during shorter text testing scenarios. The data collected from these tests informs optimization strategies and helps ensure the system meets production requirements for handling diverse content types and user demands.",
                "Advanced load testing frameworks enable comprehensive evaluation of TTS system performance under various conditions. By simulating realistic user behavior patterns, including concurrent requests, varying text lengths, and different voice parameters, we can identify potential bottlenecks and optimization opportunities. The testing process involves monitoring key performance indicators such as response times, throughput, error rates, and resource utilization to ensure the system meets quality and reliability standards. This systematic approach to performance validation helps maintain consistent user experience and system stability across different usage scenarios and load conditions."
            ]
        }
    
    def get_test_text(self, length: str) -> str:
        """Get a random test text of specified length."""
        texts = self.test_texts.get(length, self.test_texts['short'])
        return random.choice(texts)
    
    async def single_request(self, session: aiohttp.ClientSession, text: str, voice: str, 
                           speed: float, lang: str, stream: bool = True) -> Tuple[float, float, bool, str]:
        """Execute a single TTS request and measure performance."""
        request_data = {
            "text": text,
            "voice": voice,
            "speed": speed,
            "lang": lang,
            "stream": stream,
            "format": "pcm"
        }
        
        start_time = time.time()
        ttfa_time = 0.0
        success = False
        error_msg = ""
        
        try:
            async with session.post(f"{self.base_url}/v1/audio/speech", json=request_data) as response:
                if response.status == 200:
                    if stream:
                        # Measure TTFA for streaming
                        first_chunk_time = None
                        async for chunk in response.content.iter_chunked(1024):
                            if first_chunk_time is None:
                                first_chunk_time = time.time()
                                break
                        
                        if first_chunk_time:
                            ttfa_time = (first_chunk_time - start_time) * 1000
                    else:
                        # For non-streaming, TTFA is the same as response time
                        await response.read()
                        ttfa_time = (time.time() - start_time) * 1000
                    
                    success = True
                else:
                    error_msg = f"HTTP {response.status}"
        
        except Exception as e:
            error_msg = str(e)
        
        response_time = (time.time() - start_time) * 1000
        return response_time, ttfa_time, success, error_msg
    
    async def concurrent_load_test(self, concurrent_users: int, requests_per_user: int, 
                                 text_length: str = 'short', voice: str = 'af_heart',
                                 speed: float = 1.0, lang: str = 'en-us') -> LoadTestResult:
        """Run concurrent load test."""
        test_name = f"concurrent_{concurrent_users}_users_{requests_per_user}_requests"
        logger.info(f"Starting {test_name}")
        
        start_time = time.time()
        response_times = []
        ttfa_times = []
        error_messages = []
        successful_requests = 0
        failed_requests = 0
        
        async with aiohttp.ClientSession() as session:
            # Create tasks for all users
            tasks = []
            for user_id in range(concurrent_users):
                for request_id in range(requests_per_user):
                    text = self.get_test_text(text_length)
                    task = self.single_request(session, text, voice, speed, lang)
                    tasks.append(task)
            
            # Execute all requests concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    failed_requests += 1
                    error_messages.append(str(result))
                else:
                    response_time, ttfa_time, success, error_msg = result
                    response_times.append(response_time)
                    ttfa_times.append(ttfa_time)
                    
                    if success:
                        successful_requests += 1
                    else:
                        failed_requests += 1
                        error_messages.append(error_msg)
        
        end_time = time.time()
        duration = end_time - start_time
        total_requests = concurrent_users * requests_per_user
        requests_per_second = total_requests / duration if duration > 0 else 0
        
        result = LoadTestResult(
            test_name=test_name,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            response_times=response_times,
            ttfa_times=ttfa_times,
            error_messages=error_messages,
            concurrent_users=concurrent_users,
            requests_per_second=requests_per_second
        )
        
        self.results.append(result)
        return result
    
    async def stress_test(self, config: StressTestConfig) -> List[LoadTestResult]:
        """Run stress test with increasing load."""
        logger.info(f"Starting stress test: {config.name}")
        
        results = []
        total_duration = config.ramp_up_seconds + config.hold_seconds + config.ramp_down_seconds
        
        # Ramp up phase
        logger.info("Ramp up phase...")
        for users in range(config.min_users, config.max_users + 1, max(1, (config.max_users - config.min_users) // 10)):
            ramp_duration = config.ramp_up_seconds / ((config.max_users - config.min_users) // max(1, (config.max_users - config.min_users) // 10))
            result = await self.concurrent_load_test(
                concurrent_users=users,
                requests_per_user=config.requests_per_user,
                text_length=config.text_length,
                voice=config.voice,
                speed=config.speed,
                lang=config.lang
            )
            results.append(result)
            await asyncio.sleep(ramp_duration)
        
        # Hold phase
        logger.info("Hold phase...")
        hold_interval = config.hold_seconds / 5  # 5 tests during hold
        for _ in range(5):
            result = await self.concurrent_load_test(
                concurrent_users=config.max_users,
                requests_per_user=config.requests_per_user,
                text_length=config.text_length,
                voice=config.voice,
                speed=config.speed,
                lang=config.lang
            )
            results.append(result)
            await asyncio.sleep(hold_interval)
        
        # Ramp down phase
        logger.info("Ramp down phase...")
        for users in range(config.max_users, config.min_users - 1, -max(1, (config.max_users - config.min_users) // 10)):
            ramp_duration = config.ramp_down_seconds / ((config.max_users - config.min_users) // max(1, (config.max_users - config.min_users) // 10))
            result = await self.concurrent_load_test(
                concurrent_users=users,
                requests_per_user=config.requests_per_user,
                text_length=config.text_length,
                voice=config.voice,
                speed=config.speed,
                lang=config.lang
            )
            results.append(result)
            await asyncio.sleep(ramp_duration)
        
        return results
    
    async def endurance_test(self, config: EnduranceTestConfig) -> LoadTestResult:
        """Run endurance test for memory leak detection."""
        logger.info(f"Starting endurance test: {config.name}")
        
        start_time = time.time()
        end_time = start_time + (config.duration_hours * 3600)
        
        response_times = []
        ttfa_times = []
        error_messages = []
        successful_requests = 0
        failed_requests = 0
        total_requests = 0
        
        async with aiohttp.ClientSession() as session:
            while time.time() < end_time and self.running:
                # Create concurrent requests
                tasks = []
                for _ in range(config.concurrent_users):
                    text = self.get_test_text(config.text_length)
                    task = self.single_request(session, text, config.voice, config.speed, config.lang)
                    tasks.append(task)
                
                # Execute requests
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for result in results:
                    total_requests += 1
                    if isinstance(result, Exception):
                        failed_requests += 1
                        error_messages.append(str(result))
                    else:
                        response_time, ttfa_time, success, error_msg = result
                        response_times.append(response_time)
                        ttfa_times.append(ttfa_time)
                        
                        if success:
                            successful_requests += 1
                        else:
                            failed_requests += 1
                            error_messages.append(error_msg)
                
                # Wait for next interval
                await asyncio.sleep(config.request_interval_seconds)
        
        duration = time.time() - start_time
        requests_per_second = total_requests / duration if duration > 0 else 0
        
        result = LoadTestResult(
            test_name=config.name,
            start_time=start_time,
            end_time=time.time(),
            duration=duration,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            response_times=response_times,
            ttfa_times=ttfa_times,
            error_messages=error_messages,
            concurrent_users=config.concurrent_users,
            requests_per_second=requests_per_second
        )
        
        self.results.append(result)
        return result
    
    def analyze_results(self, result: LoadTestResult) -> Dict[str, Any]:
        """Analyze load test results."""
        if not result.response_times:
            return {"error": "No response time data available"}
        
        analysis = {
            "test_name": result.test_name,
            "duration": result.duration,
            "total_requests": result.total_requests,
            "successful_requests": result.successful_requests,
            "failed_requests": result.failed_requests,
            "success_rate": result.successful_requests / result.total_requests if result.total_requests > 0 else 0,
            "requests_per_second": result.requests_per_second,
            "response_time_stats": {
                "min": min(result.response_times),
                "max": max(result.response_times),
                "avg": statistics.mean(result.response_times),
                "median": statistics.median(result.response_times),
                "p95": statistics.quantiles(result.response_times, n=20)[18] if len(result.response_times) >= 20 else max(result.response_times),
                "p99": statistics.quantiles(result.response_times, n=100)[98] if len(result.response_times) >= 100 else max(result.response_times)
            }
        }
        
        if result.ttfa_times:
            analysis["ttfa_stats"] = {
                "min": min(result.ttfa_times),
                "max": max(result.ttfa_times),
                "avg": statistics.mean(result.ttfa_times),
                "median": statistics.median(result.ttfa_times),
                "p95": statistics.quantiles(result.ttfa_times, n=20)[18] if len(result.ttfa_times) >= 20 else max(result.ttfa_times),
                "p99": statistics.quantiles(result.ttfa_times, n=100)[98] if len(result.ttfa_times) >= 100 else max(result.ttfa_times)
            }
        
        # Performance assessment
        analysis["performance_assessment"] = {
            "ttfa_target_met": analysis.get("ttfa_stats", {}).get("p95", 0) <= 500.0,
            "latency_target_met": analysis["response_time_stats"]["p95"] <= 1000.0,
            "success_rate_acceptable": analysis["success_rate"] >= 0.99,
            "throughput_acceptable": analysis["requests_per_second"] >= 10.0
        }
        
        return analysis
    
    def generate_report(self, output_file: str = "load-test-report.json"):
        """Generate comprehensive load test report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(self.results),
            "test_results": []
        }
        
        for result in self.results:
            analysis = self.analyze_results(result)
            report["test_results"].append(analysis)
        
        # Overall summary
        if self.results:
            all_success_rates = [r.successful_requests / r.total_requests for r in self.results if r.total_requests > 0]
            all_rps = [r.requests_per_second for r in self.results]
            
            report["overall_summary"] = {
                "avg_success_rate": statistics.mean(all_success_rates) if all_success_rates else 0,
                "avg_requests_per_second": statistics.mean(all_rps) if all_rps else 0,
                "total_requests": sum(r.total_requests for r in self.results),
                "total_successful_requests": sum(r.successful_requests for r in self.results),
                "total_failed_requests": sum(r.failed_requests for r in self.results)
            }
        
        # Save report
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Load test report saved to {output_file}")
        return report
    
    def plot_results(self, output_file: str = "load-test-charts.png"):
        """Generate performance charts."""
        if not self.results:
            logger.warning("No results to plot")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Load Test Performance Analysis', fontsize=16)
        
        # Response time distribution
        all_response_times = []
        for result in self.results:
            all_response_times.extend(result.response_times)
        
        if all_response_times:
            axes[0, 0].hist(all_response_times, bins=50, alpha=0.7, color='blue')
            axes[0, 0].set_title('Response Time Distribution')
            axes[0, 0].set_xlabel('Response Time (ms)')
            axes[0, 0].set_ylabel('Frequency')
            axes[0, 0].axvline(statistics.mean(all_response_times), color='red', linestyle='--', label='Mean')
            axes[0, 0].legend()
        
        # TTFA distribution
        all_ttfa_times = []
        for result in self.results:
            all_ttfa_times.extend(result.ttfa_times)
        
        if all_ttfa_times:
            axes[0, 1].hist(all_ttfa_times, bins=50, alpha=0.7, color='green')
            axes[0, 1].set_title('TTFA Distribution')
            axes[0, 1].set_xlabel('TTFA (ms)')
            axes[0, 1].set_ylabel('Frequency')
            axes[0, 1].axvline(statistics.mean(all_ttfa_times), color='red', linestyle='--', label='Mean')
            axes[0, 1].legend()
        
        # Requests per second over time
        test_names = [r.test_name for r in self.results]
        rps_values = [r.requests_per_second for r in self.results]
        
        axes[1, 0].plot(range(len(rps_values)), rps_values, marker='o', color='purple')
        axes[1, 0].set_title('Requests per Second Over Time')
        axes[1, 0].set_xlabel('Test Number')
        axes[1, 0].set_ylabel('Requests/Second')
        axes[1, 0].grid(True)
        
        # Success rate over time
        success_rates = [r.successful_requests / r.total_requests for r in self.results if r.total_requests > 0]
        
        axes[1, 1].plot(range(len(success_rates)), success_rates, marker='o', color='orange')
        axes[1, 1].set_title('Success Rate Over Time')
        axes[1, 1].set_xlabel('Test Number')
        axes[1, 1].set_ylabel('Success Rate')
        axes[1, 1].set_ylim(0, 1)
        axes[1, 1].grid(True)
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        logger.info(f"Performance charts saved to {output_file}")

async def main():
    """Main load testing function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Load Testing Framework")
    parser.add_argument("--url", default="http://localhost:8000", help="TTS API base URL")
    parser.add_argument("--test-type", choices=['concurrent', 'stress', 'endurance'], default='concurrent', help="Test type")
    parser.add_argument("--users", type=int, default=10, help="Number of concurrent users")
    parser.add_argument("--requests", type=int, default=5, help="Requests per user")
    parser.add_argument("--text-length", choices=['short', 'medium', 'long'], default='short', help="Text length")
    parser.add_argument("--voice", default='af_heart', help="Voice to use")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed")
    parser.add_argument("--lang", default='en-us', help="Language")
    parser.add_argument("--output", default='load-test-report.json', help="Output report file")
    parser.add_argument("--charts", default='load-test-charts.png', help="Output charts file")
    
    args = parser.parse_args()
    
    # Create load tester
    tester = LoadTester(args.url)
    
    try:
        if args.test_type == 'concurrent':
            # Run concurrent load test
            result = await tester.concurrent_load_test(
                concurrent_users=args.users,
                requests_per_user=args.requests,
                text_length=args.text_length,
                voice=args.voice,
                speed=args.speed,
                lang=args.lang
            )
            
            # Analyze and print results
            analysis = tester.analyze_results(result)
            print(f"📊 Load Test Results:")
            print(f"  Test: {analysis['test_name']}")
            print(f"  Duration: {analysis['duration']:.2f}s")
            print(f"  Total Requests: {analysis['total_requests']}")
            print(f"  Success Rate: {analysis['success_rate']:.2%}")
            print(f"  Requests/Second: {analysis['requests_per_second']:.2f}")
            print(f"  Response Time P95: {analysis['response_time_stats']['p95']:.2f}ms")
            if 'ttfa_stats' in analysis:
                print(f"  TTFA P95: {analysis['ttfa_stats']['p95']:.2f}ms")
            
            # Performance assessment
            assessment = analysis['performance_assessment']
            print(f"  Performance Assessment:")
            print(f"    TTFA Target Met: {'✅' if assessment['ttfa_target_met'] else '❌'}")
            print(f"    Latency Target Met: {'✅' if assessment['latency_target_met'] else '❌'}")
            print(f"    Success Rate Acceptable: {'✅' if assessment['success_rate_acceptable'] else '❌'}")
            print(f"    Throughput Acceptable: {'✅' if assessment['throughput_acceptable'] else '❌'}")
        
        elif args.test_type == 'stress':
            # Run stress test
            config = StressTestConfig(
                name="stress_test",
                min_users=1,
                max_users=args.users,
                ramp_up_seconds=60,
                hold_seconds=120,
                ramp_down_seconds=60,
                requests_per_user=args.requests,
                text_length=args.text_length,
                voice=args.voice,
                speed=args.speed,
                lang=args.lang
            )
            
            results = await tester.stress_test(config)
            print(f"📊 Stress Test Completed: {len(results)} test phases")
        
        elif args.test_type == 'endurance':
            # Run endurance test
            config = EnduranceTestConfig(
                name="endurance_test",
                duration_hours=1,  # 1 hour for demo
                concurrent_users=args.users,
                request_interval_seconds=10,
                text_length=args.text_length,
                voice=args.voice,
                speed=args.speed,
                lang=args.lang
            )
            
            result = await tester.endurance_test(config)
            print(f"📊 Endurance Test Completed: {result.duration:.2f}s duration")
        
        # Generate report and charts
        report = tester.generate_report(args.output)
        tester.plot_results(args.charts)
        
        print(f"📄 Report saved to {args.output}")
        print(f"📊 Charts saved to {args.charts}")
        
    except KeyboardInterrupt:
        logger.info("Load testing interrupted by user")
    except Exception as e:
        logger.error(f"Load testing failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
