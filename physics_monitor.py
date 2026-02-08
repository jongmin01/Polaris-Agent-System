#!/usr/bin/env python3
"""
physics_monitor.py - ALCF Polaris VASP Job Monitor

Phase 1.2: Physics-Agent
- Zombie guard (10s timeout)
- Hierarchy: qstat → stat → tail → grep
- MFA session detection
"""

import subprocess
import logging
import time
import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime
from enum import Enum


class JobStatus(Enum):
    """VASP job status states"""
    RUNNING = "RUNNING"
    CONVERGED = "CONVERGED"
    ERROR = "ERROR"
    NOT_FOUND = "NOT_FOUND"
    MFA_EXPIRED = "MFA_EXPIRED"
    ZOMBIE = "ZOMBIE"


class PhysicsMonitor:
    """
    Monitor VASP jobs on ALCF Polaris

    Features:
    - SSH connection zombie guard
    - Job status hierarchy (qstat → stat → tail → grep)
    - MFA session detection
    - Crash-safe logging
    """

    def __init__(self, log_path: Optional[Path] = None):
        """Initialize Physics Monitor"""
        if log_path is None:
            project_dir = Path(__file__).parent
            log_path = project_dir / "logs" / "physics.log"

        # Ensure log directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Set up logging
        self.logger = logging.getLogger('physics_monitor')
        self.logger.setLevel(logging.INFO)

        # File handler
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        self.logger.addHandler(file_handler)

        # Console handler for debugging
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        self.logger.addHandler(console_handler)

        self.logger.info("Physics Monitor initialized")

    def zombie_guard(self) -> bool:
        """
        Probe SSH connection with 10s timeout

        Returns:
            True if connection alive, False if zombie/timeout
        """
        try:
            result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=10', 'polaris', 'echo heartbeat'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and 'heartbeat' in result.stdout:
                self.logger.debug("Zombie guard: Connection alive")
                return True
            else:
                self.logger.warning(f"Zombie guard: Connection failed (code {result.returncode})")
                return False

        except subprocess.TimeoutExpired:
            self.logger.error("Zombie guard: SSH timeout (10s)")
            return False
        except Exception as e:
            self.logger.error(f"Zombie guard: Exception - {e}")
            return False

    def check_mfa_session(self, stderr: str) -> bool:
        """
        Check if MFA session has expired

        Args:
            stderr: SSH command stderr output

        Returns:
            True if MFA expired
        """
        mfa_indicators = [
            'Permission denied',
            'publickey',
            'Authentication failed',
            'Connection closed by remote host'
        ]

        for indicator in mfa_indicators:
            if indicator.lower() in stderr.lower():
                self.logger.warning(f"MFA indicator detected: {indicator}")
                return True

        return False

    def run_ssh_command(self, command: str, timeout: int = 30) -> Tuple[bool, str, str]:
        """
        Run SSH command on Polaris with timeout

        Args:
            command: Command to execute
            timeout: Timeout in seconds

        Returns:
            (success, stdout, stderr)
        """
        try:
            result = subprocess.run(
                ['ssh', 'polaris', command],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            success = result.returncode == 0
            return success, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            self.logger.error(f"SSH command timeout: {command}")
            return False, "", "Timeout"
        except Exception as e:
            self.logger.error(f"SSH command exception: {e}")
            return False, "", str(e)

    def check_job_queue(self, job_id: str) -> Tuple[JobStatus, str]:
        """
        Step 1: Check if job is in queue (qstat)

        Args:
            job_id: PBS job ID

        Returns:
            (status, message)
        """
        self.logger.info(f"Step 1: Checking queue for job {job_id}")

        success, stdout, stderr = self.run_ssh_command(f'qstat -u jbaek27')

        if not success:
            if self.check_mfa_session(stderr):
                return JobStatus.MFA_EXPIRED, "MFA session expired"
            return JobStatus.ERROR, f"qstat failed: {stderr}"

        # Parse qstat output for job_id
        if job_id in stdout:
            # Extract job status (R = Running, Q = Queued, etc.)
            for line in stdout.split('\n'):
                if job_id in line:
                    parts = line.split()
                    if len(parts) >= 10:
                        qstat_status = parts[9]  # PBS status column
                        self.logger.info(f"Job {job_id} found in queue: {qstat_status}")

                        if qstat_status == 'R':
                            return JobStatus.RUNNING, f"Job running (qstat: {qstat_status})"
                        else:
                            return JobStatus.RUNNING, f"Job in queue (qstat: {qstat_status})"

        self.logger.warning(f"Job {job_id} not found in qstat output")
        return JobStatus.NOT_FOUND, "Job not in queue"

    def check_outcar_modification(self, path: str) -> Tuple[JobStatus, str, Optional[int]]:
        """
        Step 2: Check OUTCAR modification time

        Args:
            path: Path to VASP calculation directory

        Returns:
            (status, message, last_modified_timestamp)
        """
        self.logger.info(f"Step 2: Checking OUTCAR modification time in {path}")

        outcar_path = f"{path}/OUTCAR"
        success, stdout, stderr = self.run_ssh_command(f'stat -c %Y {outcar_path}')

        if not success:
            if self.check_mfa_session(stderr):
                return JobStatus.MFA_EXPIRED, "MFA session expired", None
            return JobStatus.ERROR, f"OUTCAR not found or inaccessible", None

        try:
            mtime = int(stdout.strip())
            current_time = int(time.time())
            age_seconds = current_time - mtime
            age_minutes = age_seconds / 60

            self.logger.info(f"OUTCAR last modified {age_minutes:.1f} minutes ago")

            # If modified within last 10 minutes, assume still running
            if age_minutes < 10:
                return JobStatus.RUNNING, f"OUTCAR recently modified ({age_minutes:.1f}m ago)", mtime
            else:
                return JobStatus.RUNNING, f"OUTCAR stale ({age_minutes:.1f}m ago, may be stuck)", mtime

        except ValueError:
            return JobStatus.ERROR, "Failed to parse OUTCAR modification time", None

    def check_oszicar_progress(self, path: str) -> Tuple[JobStatus, str, Optional[Dict]]:
        """
        Step 3: Parse OSZICAR for steps and energy

        Args:
            path: Path to VASP calculation directory

        Returns:
            (status, message, progress_dict)
        """
        self.logger.info(f"Step 3: Parsing OSZICAR in {path}")

        oszicar_path = f"{path}/OSZICAR"
        success, stdout, stderr = self.run_ssh_command(f'tail -1 {oszicar_path}')

        if not success:
            if self.check_mfa_session(stderr):
                return JobStatus.MFA_EXPIRED, "MFA session expired", None
            return JobStatus.ERROR, "OSZICAR not found or empty", None

        try:
            # Parse OSZICAR line: "  1 F= -.12345678E+02 E0= -.12345678E+02  d E =0.123456E+00"
            line = stdout.strip()
            parts = line.split()

            if len(parts) >= 3:
                step = int(parts[0])
                energy_str = parts[2]

                # Extract energy value
                energy = float(energy_str.replace('E', 'e'))

                progress = {
                    'step': step,
                    'energy': energy,
                    'raw_line': line
                }

                self.logger.info(f"OSZICAR progress: Step {step}, Energy {energy:.6f} eV")
                return JobStatus.RUNNING, f"Step {step}, E={energy:.6f} eV", progress
            else:
                return JobStatus.ERROR, "Failed to parse OSZICAR format", None

        except (ValueError, IndexError) as e:
            self.logger.error(f"OSZICAR parsing error: {e}")
            return JobStatus.ERROR, f"OSZICAR parse error: {e}", None

    def check_convergence(self, path: str) -> Tuple[JobStatus, str]:
        """
        Step 4: Check if calculation converged

        Args:
            path: Path to VASP calculation directory

        Returns:
            (status, message)
        """
        self.logger.info(f"Step 4: Checking convergence in {path}")

        outcar_path = f"{path}/OUTCAR"
        success, stdout, stderr = self.run_ssh_command(
            f'grep "reached required accuracy" {outcar_path}'
        )

        if not success:
            if self.check_mfa_session(stderr):
                return JobStatus.MFA_EXPIRED, "MFA session expired"
            # grep returns non-zero if pattern not found (not an error)
            if "reached required accuracy" not in stdout:
                return JobStatus.RUNNING, "Not converged yet"
            return JobStatus.ERROR, "Failed to check convergence"

        if "reached required accuracy" in stdout:
            self.logger.info("✅ Calculation converged!")
            return JobStatus.CONVERGED, "Calculation converged successfully"
        else:
            return JobStatus.RUNNING, "Not converged yet"

    def monitor_job(self, job_id: str, path: str) -> Dict:
        """
        Full monitoring hierarchy for a VASP job

        Args:
            job_id: PBS job ID
            path: Path to VASP calculation directory

        Returns:
            Status dict with full hierarchy results
        """
        self.logger.info(f"=== Monitoring job {job_id} at {path} ===")

        result = {
            'job_id': job_id,
            'path': path,
            'timestamp': datetime.now().isoformat(),
            'status': JobStatus.ERROR.value,
            'message': '',
            'details': {}
        }

        # Zombie guard
        if not self.zombie_guard():
            result['status'] = JobStatus.ZOMBIE.value
            result['message'] = "SSH connection timeout or zombie"
            self.logger.error("Zombie guard failed - aborting monitor")
            return result

        # Step 1: Check job queue
        queue_status, queue_msg = self.check_job_queue(job_id)
        result['details']['queue'] = {'status': queue_status.value, 'message': queue_msg}

        if queue_status == JobStatus.MFA_EXPIRED:
            result['status'] = JobStatus.MFA_EXPIRED.value
            result['message'] = queue_msg
            return result

        if queue_status == JobStatus.NOT_FOUND:
            # Job not in queue - might be finished or never existed
            # Continue to check files for convergence
            pass

        # Step 2: Check OUTCAR modification
        outcar_status, outcar_msg, mtime = self.check_outcar_modification(path)
        result['details']['outcar'] = {
            'status': outcar_status.value,
            'message': outcar_msg,
            'mtime': mtime
        }

        if outcar_status == JobStatus.MFA_EXPIRED:
            result['status'] = JobStatus.MFA_EXPIRED.value
            result['message'] = outcar_msg
            return result

        if outcar_status == JobStatus.ERROR:
            result['status'] = JobStatus.ERROR.value
            result['message'] = outcar_msg
            return result

        # Step 3: Parse OSZICAR
        oszicar_status, oszicar_msg, progress = self.check_oszicar_progress(path)
        result['details']['oszicar'] = {
            'status': oszicar_status.value,
            'message': oszicar_msg,
            'progress': progress
        }

        if oszicar_status == JobStatus.MFA_EXPIRED:
            result['status'] = JobStatus.MFA_EXPIRED.value
            result['message'] = oszicar_msg
            return result

        # Step 4: Check convergence
        conv_status, conv_msg = self.check_convergence(path)
        result['details']['convergence'] = {
            'status': conv_status.value,
            'message': conv_msg
        }

        if conv_status == JobStatus.MFA_EXPIRED:
            result['status'] = JobStatus.MFA_EXPIRED.value
            result['message'] = conv_msg
            return result

        if conv_status == JobStatus.CONVERGED:
            result['status'] = JobStatus.CONVERGED.value
            result['message'] = "✅ Calculation converged!"
            return result

        # If we got here, job is still running
        result['status'] = JobStatus.RUNNING.value
        result['message'] = oszicar_msg if oszicar_msg else "Job running"

        self.logger.info(f"Monitor complete: {result['status']} - {result['message']}")
        return result


# Test function
def test_physics_monitor():
    """Test Physics Monitor"""
    print("=" * 60)
    print("  🔬 Physics Monitor Test")
    print("=" * 60)
    print()

    monitor = PhysicsMonitor()

    print("[1/2] Testing zombie guard...")
    if monitor.zombie_guard():
        print("✅ SSH connection alive")
    else:
        print("❌ SSH connection failed")

    print()
    print("[2/2] Testing job monitoring...")
    # Example: monitor.monitor_job('12345', '/path/to/vasp')
    print("⚠️  Skipping job test (requires valid job_id and path)")

    print()
    print("=" * 60)
    print("  ✅ Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    test_physics_monitor()
