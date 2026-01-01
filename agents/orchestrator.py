"""
Autonomous System Orchestrator
Continuously breaks, detects, reasons, fixes, and verifies the system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fault-injection'))

import time
import random
from datetime import datetime
from agents.detection_agent import DetectionAgent
from agents.remediation_agent import RemediationAgent
from fault_injector import FaultInjector

class AutonomousOrchestrator:
    def __init__(self):
        print("="*60)
        print("AUTONOMOUS SYSTEM ORCHESTRATOR")
        print("="*60)
        print("\nInitializing agents...")
        
        self.detection_agent = DetectionAgent()
        self.remediation_agent = RemediationAgent()
        self.fault_injector = FaultInjector()
        
        self.cycle_count = 0
        self.total_incidents = 0
        self.total_remediations = 0
        self.successful_remediations = 0
        
        print("\n✓ All agents initialized")
        print("="*60)
    
    def run_cycle(self):
        """Execute one complete autonomous cycle"""
        self.cycle_count += 1
        
        print(f"\n{'#'*60}")
        print(f"AUTONOMOUS CYCLE #{self.cycle_count}")
        print(f"{'#'*60}")
        print(f"Time: {datetime.now().isoformat()}")
        print(f"Stats: {self.total_incidents} incidents, {self.successful_remediations}/{self.total_remediations} fixes")
        print(f"{'#'*60}\n")
        
        # PHASE 1: FAULT INJECTION
        print("\n" + "▶"*60)
        print("PHASE 1: FAULT INJECTION")
        print("▶"*60)
        
        if self.cycle_count % 3 == 1:
            # Inject fault every 3rd cycle
            print("Injecting random fault to test system resilience...")
            self.fault_injector.inject_random_fault()
        else:
            print("Skipping fault injection this cycle")
        
        # Quick MVP mode - minimal wait
        print("\nMVP Mode: Quick system check...")
        time.sleep(2)
        
        # PHASE 2: DETECTION
        print("\n" + "▶"*60)
        print("PHASE 2: INCIDENT DETECTION & PREDICTION")
        print("▶"*60)
        
        analysis = self.detection_agent.detect_and_predict()
        
        current_failures = analysis.get('current_failures', [])
        future_risks = analysis.get('future_risks', [])
        should_remediate = analysis.get('trigger_remediation', False)
        
        print(f"\nDetection Summary:")
        print(f"  - Current failures: {len(current_failures)}")
        print(f"  - Future risks: {len(future_risks)}")
        print(f"  - Remediation needed: {should_remediate}")
        
        self.total_incidents += len(current_failures)
        
        # PHASE 3: REMEDIATION
        if should_remediate and current_failures:
            print("\n" + "▶"*60)
            print("PHASE 3: AUTOMATED REMEDIATION")
            print("▶"*60)
            
            # Remediate each critical failure
            for failure in current_failures:
                severity = failure.get('severity', 'MEDIUM')
                
                if severity in ['CRITICAL', 'HIGH']:
                    print(f"\n→ Remediating: {failure.get('type', 'UNKNOWN')} (Severity: {severity})")
                    
                    self.total_remediations += 1
                    
                    try:
                        result = self.remediation_agent.remediate_incident(failure)
                        
                        if result['verification'].get('success', False):
                            self.successful_remediations += 1
                            print(f"  ✓ Remediation successful")
                        else:
                            print(f"  ✗ Remediation failed or incomplete")
                    except Exception as e:
                        print(f"  ✗ Remediation error: {e}")
                else:
                    print(f"\n→ Skipping remediation for {severity} severity incident")
        else:
            print("\n" + "▶"*60)
            print("PHASE 3: NO REMEDIATION NEEDED")
            print("▶"*60)
            print("System is healthy or issues are below remediation threshold")
        
        # PHASE 4: VERIFICATION & REPORTING
        print("\n" + "▶"*60)
        print("PHASE 4: VERIFICATION & REPORTING")
        print("▶"*60)
        
        # Re-check system health
        print("\nRe-checking system health...")
        post_check = self.detection_agent.collect_metrics()
        post_health = post_check['system_health']
        
        print(f"  Current Status: {post_health['status']}")
        print(f"  Error Count: {post_health['error_count']}")
        print(f"  Warning Count: {post_health['warning_count']}")
        
        # Calculate success rate
        if self.total_remediations > 0:
            success_rate = (self.successful_remediations / self.total_remediations) * 100
        else:
            success_rate = 0
        
        print(f"\n  Overall Success Rate: {success_rate:.1f}%")
        
        # PHASE 5: CLEANUP
        print("\n" + "▶"*60)
        print("PHASE 5: CLEANUP")
        print("▶"*60)
        
        print("Cleaning up transient faults...")
        self.fault_injector.cleanup_faults()
        
        print(f"\n{'#'*60}")
        print(f"CYCLE #{self.cycle_count} COMPLETE")
        print(f"{'#'*60}\n")
    
    def run_continuous(self, cycle_interval=300, max_cycles=None):
        """
        Run autonomous system continuously
        
        Args:
            cycle_interval: Seconds between cycles (default: 300 = 5 minutes)
            max_cycles: Maximum number of cycles (None = infinite)
        """
        print(f"\n{'='*60}")
        print("STARTING CONTINUOUS AUTONOMOUS OPERATION")
        print(f"{'='*60}")
        print(f"Cycle Interval: {cycle_interval}s")
        print(f"Max Cycles: {max_cycles or 'Infinite'}")
        print("\nThe system will now:")
        print("  1. Inject faults periodically")
        print("  2. Detect failures and predict risks")
        print("  3. Automatically remediate issues")
        print("  4. Verify fixes")
        print("  5. Repeat forever")
        print("\nPress Ctrl+C to stop")
        print(f"{'='*60}\n")
        
        try:
            while True:
                if max_cycles and self.cycle_count >= max_cycles:
                    print(f"\nReached maximum cycles ({max_cycles}), stopping...")
                    break
                
                # Run one cycle
                self.run_cycle()
                
                # Wait before next cycle
                print(f"\n⏸  Waiting {cycle_interval}s before next cycle...")
                print(f"   Next cycle will be #{self.cycle_count + 1}")
                time.sleep(cycle_interval)
                
        except KeyboardInterrupt:
            print("\n\n" + "="*60)
            print("AUTONOMOUS SYSTEM STOPPED BY USER")
            print("="*60)
            print(f"\nFinal Statistics:")
            print(f"  Total Cycles: {self.cycle_count}")
            print(f"  Total Incidents: {self.total_incidents}")
            print(f"  Total Remediations: {self.total_remediations}")
            print(f"  Successful Remediations: {self.successful_remediations}")
            
            if self.total_remediations > 0:
                success_rate = (self.successful_remediations / self.total_remediations) * 100
                print(f"  Success Rate: {success_rate:.1f}%")
            
            print("="*60)
        
        except Exception as e:
            print(f"\n\n{'='*60}")
            print("AUTONOMOUS SYSTEM ERROR")
            print(f"{'='*60}")
            print(f"Error: {e}")
            print(f"{'='*60}")
            raise
        
        finally:
            # Cleanup
            print("\nPerforming final cleanup...")
            self.fault_injector.cleanup_faults()
            print("✓ Cleanup complete")
    
    def run_demo(self, cycles=3):
        """Run a short demonstration"""
        print(f"\n{'='*60}")
        print("DEMO MODE")
        print(f"{'='*60}")
        print(f"Running {cycles} cycles with 30s intervals for demonstration")
        print(f"{'='*60}\n")
        
        self.run_continuous(cycle_interval=30, max_cycles=cycles)


if __name__ == '__main__':
    import sys
    
    orchestrator = AutonomousOrchestrator()
    
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == 'demo':
        # Demo mode: 3 quick cycles
        orchestrator.run_demo(cycles=3)
    elif len(sys.argv) > 1 and sys.argv[1] == 'single':
        # Single cycle test
        print("\nRunning single cycle test...")
        orchestrator.run_cycle()
    else:
        # Full continuous mode
        orchestrator.run_continuous(cycle_interval=300)
