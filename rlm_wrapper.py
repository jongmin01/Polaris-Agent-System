#!/usr/bin/env python3
"""
RLM Wrapper (Recursive Learning Monitor)
Phase 1.3 - Hardened Ensemble Voting & SSH Stealth

Non-invasive wrapper for email classification with:
- Ensemble voting (parallel inferences with quorum)
- SSH stealth management (daily connection limits, jitter)
- Recursive contradiction detection (from corrections.jsonl)
"""

import yaml
import asyncio
import logging
import random
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime, time as dt_time
from collections import Counter
import hashlib

# Setup logging
logger = logging.getLogger(__name__)


class RLMConfig:
    """Load and validate RLM configuration from YAML"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent / "config" / "RLM_CONFIG.yaml"

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Voting parameters
        self.n_inferences = self.config['voting']['n_inferences']
        self.temperature = self.config['voting']['temperature']
        self.min_quorum = self.config['voting']['min_quorum']
        self.confidence_threshold = self.config['voting']['confidence_threshold']

        # SSH parameters
        self.ssh_batch_commands = self.config['ssh']['batch_commands']
        self.ssh_timeout = self.config['ssh']['timeout_seconds']
        self.ssh_jitter_range = self.config['ssh']['jitter_range_seconds']
        self.ssh_max_daily = self.config['ssh']['max_daily_connections']

        # Logic parameters
        self.max_recursion_depth = self.config['logic']['max_recursion_depth']
        self.contradiction_mode = self.config['logic']['contradiction_detection']
        self.fallback_category = self.config['logic']['fallback_category']

        # Templates
        self.uncertain_msg = self.config['templates']['uncertain_msg']

        logger.info(f"✅ RLM Config loaded: {self.n_inferences} inferences, quorum={self.min_quorum}")

    def __repr__(self):
        return f"RLMConfig(n={self.n_inferences}, quorum={self.min_quorum}, threshold={self.confidence_threshold})"


class EnsembleVoter:
    """
    Ensemble voting for email classification with parallel inferences.

    Features:
    - Execute n_inferences in parallel
    - Quorum validation (min successful calls)
    - Confidence calculation (majority_votes / successful_calls)
    - UNCERTAIN fallback on low confidence
    """

    def __init__(self, config: RLMConfig):
        self.config = config
        self.audit_log = Path(__file__).parent / "logs" / "rlm_audit.log"
        self.audit_log.parent.mkdir(parents=True, exist_ok=True)

    async def vote_classify(self, classify_func, mail: Dict) -> Tuple[str, float, List[str]]:
        """
        Execute ensemble voting on email classification.

        Args:
            classify_func: The original classification function to wrap
            mail: Email dictionary with subject, sender, content

        Returns:
            (category, confidence, all_votes)
            - category: ACTION, FYI, or UNCERTAIN
            - confidence: float 0.0-1.0
            - all_votes: list of all inference results (including failures)
        """
        subject = mail.get('subject', 'Unknown')

        # Execute parallel inferences
        tasks = [
            self._single_inference(classify_func, mail, i)
            for i in range(self.config.n_inferences)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter successful results
        successful_votes = [
            r for r in results
            if isinstance(r, str) and r in ['ACTION', 'FYI']
        ]

        # Log all results
        self._audit_log(
            event_type="ENSEMBLE_VOTE",
            details={
                "subject": subject,
                "total_inferences": self.config.n_inferences,
                "successful": len(successful_votes),
                "votes": successful_votes,
                "failures": [str(r) for r in results if not isinstance(r, str) or r not in ['ACTION', 'FYI']]
            }
        )

        # Quorum check
        if len(successful_votes) < self.config.min_quorum:
            logger.warning(f"⚠️ Quorum not met: {len(successful_votes)}/{self.config.min_quorum} for '{subject}'")
            return self.config.fallback_category, 0.0, successful_votes

        # Calculate majority and confidence
        vote_counts = Counter(successful_votes)
        majority_vote, majority_count = vote_counts.most_common(1)[0]
        confidence = majority_count / len(successful_votes)

        # Confidence threshold check
        if confidence < self.config.confidence_threshold:
            logger.warning(
                f"⚠️ Low confidence: {confidence:.2f} < {self.config.confidence_threshold} for '{subject}'"
            )
            return self.config.fallback_category, confidence, successful_votes

        logger.info(
            f"✅ Ensemble vote: {majority_vote} (confidence={confidence:.2f}, votes={vote_counts})"
        )

        return majority_vote, confidence, successful_votes

    async def _single_inference(self, classify_func, mail: Dict, inference_num: int) -> str:
        """Execute single classification inference with error handling"""
        try:
            # Call original classification function
            # Note: classify_func should be wrapped to accept temperature parameter
            result = await asyncio.to_thread(classify_func, mail)
            logger.debug(f"Inference {inference_num}: {result}")
            return result
        except Exception as e:
            logger.error(f"Inference {inference_num} failed: {e}")
            return f"ERROR: {str(e)}"

    def _audit_log(self, event_type: str, details: Dict):
        """Write event to RLM audit log"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "event_type": event_type,
            "details": details
        }

        with open(self.audit_log, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')


class SSHStealth:
    """
    SSH connection stealth manager for Physics Agent.

    Features:
    - Daily connection counter (resets at midnight)
    - Command timeout wrapping
    - Jitter application to polling intervals
    """

    def __init__(self, config: RLMConfig):
        self.config = config
        self.counter_file = Path(__file__).parent / "data" / "ssh_counter.json"
        self.counter_file.parent.mkdir(parents=True, exist_ok=True)

    def check_daily_limit(self) -> bool:
        """
        Check if daily SSH connection limit has been reached.

        Returns:
            True if connections are allowed, False if limit exceeded
        """
        counter_data = self._load_counter()
        today = datetime.now().date().isoformat()

        # Reset counter if new day
        if counter_data.get('date') != today:
            counter_data = {'date': today, 'count': 0}
            self._save_counter(counter_data)

        # Check limit
        if counter_data['count'] >= self.config.ssh_max_daily:
            logger.warning(
                f"🚫 SSH daily limit reached: {counter_data['count']}/{self.config.ssh_max_daily}"
            )
            return False

        return True

    def increment_counter(self):
        """Increment daily SSH connection counter"""
        counter_data = self._load_counter()
        today = datetime.now().date().isoformat()

        if counter_data.get('date') != today:
            counter_data = {'date': today, 'count': 0}

        counter_data['count'] += 1
        self._save_counter(counter_data)

        logger.info(
            f"📊 SSH connections today: {counter_data['count']}/{self.config.ssh_max_daily}"
        )

    def wrap_ssh_timeout(self, command: str) -> str:
        """
        Wrap SSH command with timeout.

        Args:
            command: Original SSH command

        Returns:
            Command wrapped with timeout
        """
        timeout = self.config.ssh_timeout
        return f"timeout {timeout} {command}"

    def apply_jitter(self, interval_seconds: int) -> int:
        """
        Apply random jitter to polling interval.

        Args:
            interval_seconds: Base interval (e.g., 3600 for 1 hour)

        Returns:
            Jittered interval
        """
        jitter = random.uniform(
            -self.config.ssh_jitter_range,
            self.config.ssh_jitter_range
        )
        jittered = int(interval_seconds + jitter)

        logger.debug(f"Jitter applied: {interval_seconds}s → {jittered}s (Δ={jitter:.1f}s)")

        return jittered

    def _load_counter(self) -> Dict:
        """Load SSH counter from file"""
        if not self.counter_file.exists():
            return {'date': datetime.now().date().isoformat(), 'count': 0}

        with open(self.counter_file, 'r') as f:
            return json.load(f)

    def _save_counter(self, data: Dict):
        """Save SSH counter to file"""
        with open(self.counter_file, 'w') as f:
            json.dump(data, f, indent=2)


class RecursiveController:
    """
    Recursive contradiction detection from feedback loop.

    Features:
    - Scan corrections.jsonl for subject contradictions
    - Max recursion depth enforcement
    - Exact string matching on email subjects
    """

    def __init__(self, config: RLMConfig):
        self.config = config
        self.corrections_file = Path(__file__).parent / "data" / "feedback" / "corrections.jsonl"

    def check_contradictions(self, subject: str) -> Optional[str]:
        """
        Check if email subject has contradictory classifications in history.

        Args:
            subject: Email subject to check

        Returns:
            None if no contradiction, warning message if contradiction found
        """
        if self.config.contradiction_mode == "disabled":
            return None

        if not self.corrections_file.exists():
            return None

        # Load corrections and find matches
        corrections = self._load_corrections()
        matches = [
            c for c in corrections
            if c.get('subject') == subject  # Exact match
        ]

        if len(matches) < 2:
            return None

        # Check for contradictions (same subject, different labels)
        labels = set([c.get('corrected_label') for c in matches])

        if len(labels) > 1:
            logger.warning(
                f"⚠️ Contradiction detected for subject '{subject}': labels={labels}"
            )
            return f"CONTRADICTION: Subject has conflicting labels: {labels}"

        return None

    def enforce_depth_limit(self, current_depth: int) -> bool:
        """
        Check if current recursion depth exceeds limit.

        Args:
            current_depth: Current recursion level

        Returns:
            True if depth is acceptable, False if limit exceeded
        """
        if current_depth > self.config.max_recursion_depth:
            logger.warning(
                f"🚫 Recursion depth limit exceeded: {current_depth} > {self.config.max_recursion_depth}"
            )
            return False

        return True

    def _load_corrections(self) -> List[Dict]:
        """Load corrections from JSONL file"""
        corrections = []

        with open(self.corrections_file, 'r') as f:
            for line in f:
                try:
                    corrections.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue

        return corrections


class RLMWrapper:
    """
    Main RLM Wrapper orchestrating all components.

    This is the non-invasive wrapper that should be used to enhance
    the existing email classification without replacing Phase 0/1.1 logic.
    """

    def __init__(self, config_path: str = None):
        self.config = RLMConfig(config_path)
        self.voter = EnsembleVoter(self.config)
        self.ssh_stealth = SSHStealth(self.config)
        self.recursive_ctrl = RecursiveController(self.config)

        logger.info("✅ RLM Wrapper initialized (Phase 1.3)")

    async def classify_with_ensemble(self, classify_func, mail: Dict) -> Tuple[str, float, Dict]:
        """
        Wrap classification function with ensemble voting.

        Args:
            classify_func: Original classification function
            mail: Email dictionary

        Returns:
            (category, confidence, metadata)
        """
        subject = mail.get('subject', 'Unknown')

        # Check for contradictions
        contradiction = self.recursive_ctrl.check_contradictions(subject)
        if contradiction:
            logger.warning(f"Contradiction detected, returning UNCERTAIN: {contradiction}")
            return self.config.fallback_category, 0.0, {
                "contradiction": contradiction,
                "votes": []
            }

        # Perform ensemble voting
        category, confidence, votes = await self.voter.vote_classify(classify_func, mail)

        metadata = {
            "votes": votes,
            "confidence": confidence,
            "n_inferences": self.config.n_inferences,
            "quorum_met": len(votes) >= self.config.min_quorum
        }

        return category, confidence, metadata

    def get_ssh_manager(self) -> SSHStealth:
        """Get SSH stealth manager instance"""
        return self.ssh_stealth

    def get_recursive_controller(self) -> RecursiveController:
        """Get recursive controller instance"""
        return self.recursive_ctrl


# Convenience function for integration
def create_rlm_wrapper(config_path: str = None) -> RLMWrapper:
    """Factory function to create RLM wrapper instance"""
    return RLMWrapper(config_path)


if __name__ == "__main__":
    # Test configuration loading
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Testing RLM Wrapper...")
    wrapper = create_rlm_wrapper()
    print(f"Config: {wrapper.config}")
    print(f"SSH daily limit check: {wrapper.ssh_stealth.check_daily_limit()}")
    print(f"Jitter example (3600s): {wrapper.ssh_stealth.apply_jitter(3600)}s")
    print("✅ RLM Wrapper test complete")
