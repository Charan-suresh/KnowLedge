import threading
import queue
import time
import logging
import uuid
import random
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from . import db
from . import config
from .scout import tag_content
from .sage import run_session, ClearingResult
from .lens import verify_image, ExaminerResult
from .integrity.session_fingerprint import build_session_fingerprint, sign_fingerprint
from .integrity.anti_spoof import analyze_integrity, make_lens_signature
from .prompt_engineering import generate_solo_question
from .assessment import evaluate_real_learning
from .anti_gaming import generate_probe

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self):
        self.input_queue = queue.Queue()
        self.event_bus = queue.Queue()
        self._scout_thread = None
        self._stop_event = threading.Event()
        self.resource_lock = threading.Lock()

    def start_scout_loop(self):
        """Runs Scout in a background thread, polling input_queue."""
        if self._scout_thread is not None and self._scout_thread.is_alive():
            return

        self._stop_event.clear()
        self._scout_thread = threading.Thread(target=self._scout_worker, daemon=True)
        self._scout_thread.start()

    def stop_scout_loop(self):
        self._stop_event.set()

    def _scout_worker(self):
        while not self._stop_event.is_set():
            try:
                # Poll queue with timeout to allow checking stop_event
                text = self.input_queue.get(timeout=1.0)
                if text:
                    concepts = tag_content(text)
                    for concept in concepts:
                        db.insert_debt(concept.concept_tag, text, concept.confidence_score)
                        self.event_bus.put({"type": "DEBT_ADDED", "concept": concept.concept_tag})
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in Scout worker: {e}")

    def _extract_first_sentence(self, text: str) -> str:
        snippet = (text or "").strip()
        if not snippet:
            return ""
        parts = re.split(r"(?<=[.!?])\s+", snippet, maxsplit=1)
        return parts[0].strip()

    def trigger_clearing(
        self,
        concept: str,
        chat_history: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        student_id: Optional[str] = None,
        db_session_id: Optional[int] = None,
    ) -> ClearingResult:
        """
        Pulls the debt log for that concept from SQLite, invokes Sage synchronously.
        Updates the row status to clear or persists in SQLite. Emits CLEARING_COMPLETE if clear.
        """
        # If Low RAM, ensure Lens isn't running
        if config.LOW_RAM:
            self.resource_lock.acquire()

        try:
            db.mark_aborted_interrupts_and_penalize(idle_seconds=5 * 60)
            debt_log = db.get_debt_by_concept(concept)
            effective_session_id = session_id or f"sage-{uuid.uuid4().hex[:10]}"
            active_student_message = ""
            for msg in reversed(chat_history):
                if (msg.get("role") or "").lower() in {"user", "student"}:
                    active_student_message = str(msg.get("content") or "")
                    break

            should_interrupt = (
                bool(active_student_message.strip())
                and random.random() < max(0.0, min(1.0, config.SOCRATIC_INTERRUPT_PROBABILITY))
            )
            if should_interrupt:
                first_sentence = self._extract_first_sentence(active_student_message)
                probe_data = generate_probe(
                    student_response=first_sentence,
                    concept=concept,
                    artifact_context=first_sentence,
                    difficulty="medium",
                    strategy="SPECIFICITY_PROBE",
                )
                probe_text = probe_data["probe"]
                if db_session_id is not None:
                    db.register_socratic_interrupt(str(db_session_id), concept, first_sentence, probe_text)
                else:
                    db.register_socratic_interrupt(effective_session_id, concept, first_sentence, probe_text)
                db.log_audit_event(
                    event_type="socratic_interrupt",
                    session_id=str(db_session_id) if db_session_id is not None else effective_session_id,
                    student_id=student_id,
                    concept=concept,
                    inputs={"first_sentence": first_sentence},
                    decision={"probe": probe_text, "strategy": "SPECIFICITY_PROBE"},
                )
                self.event_bus.put({"type": "SOCRATIC_INTERRUPT", "concept": concept})
                return ClearingResult(cleared=False, response=f"Hold on - before you finish, {probe_text}")

            started_at = datetime.utcnow() - timedelta(seconds=max(5, len(chat_history) * 2))
            result = run_session(concept, debt_log, chat_history)
            db.resolve_socratic_interrupts(str(db_session_id) if db_session_id is not None else effective_session_id)

            fingerprint = build_session_fingerprint(
                session_id=effective_session_id,
                concept=concept,
                chat_history=chat_history,
                started_at=started_at,
                ended_at=datetime.utcnow(),
            )
            session_hash = sign_fingerprint(fingerprint)
            fingerprint["session_hash"] = session_hash
            db.save_session_fingerprint(fingerprint)
            integrity = analyze_integrity(fingerprint)

            if result.cleared and not integrity["integrity_suspect"]:
                db.update_status(concept, "clear")
                db.set_debt_integrity(concept, integrity_suspect=False, clearing_method="sage_only")
                db.insert_clearing_history(
                    concept,
                    "clear",
                    result.response,
                    session_hash=session_hash,
                    spoof_attempts=integrity["spoof_attempts"],
                    paste_detected=fingerprint["paste_detected"],
                    integrity_suspect=False,
                    voice_mode=config.VOICE_MODE,
                )
                self.event_bus.put({"type": "CLEARING_COMPLETE", "concept": concept})
            elif result.cleared and integrity["integrity_suspect"]:
                db.set_debt_integrity(concept, integrity_suspect=True, clearing_method="sage_only")
                db.insert_clearing_history(
                    concept,
                    "persists",
                    f"Integrity suspect: {', '.join(integrity['reasons'])}",
                    session_hash=session_hash,
                    spoof_attempts=integrity["spoof_attempts"],
                    paste_detected=fingerprint["paste_detected"],
                    integrity_suspect=True,
                    voice_mode=config.VOICE_MODE,
                )
                result = ClearingResult(cleared=False, response="Session flagged for integrity review. Please complete Solo Mode.")
            else:
                db.insert_clearing_history(
                    concept,
                    "persists",
                    result.response,
                    session_hash=session_hash,
                    spoof_attempts=integrity["spoof_attempts"],
                    paste_detected=fingerprint["paste_detected"],
                    integrity_suspect=integrity["integrity_suspect"],
                    voice_mode=config.VOICE_MODE,
                )
                if integrity["integrity_suspect"]:
                    db.set_debt_integrity(concept, integrity_suspect=True, clearing_method="sage_only")
            
            return result
        finally:
            if config.LOW_RAM:
                self.resource_lock.release()

    def trigger_lens_check(self, image_bytes: bytes, concept: str) -> ExaminerResult:
        """
        Calls Lens, returns result to caller, logs outcome.
        """
        if config.LOW_RAM:
            self.resource_lock.acquire()

        try:
            result = verify_image(image_bytes, concept)
            
            # Persist handwritten verification only when the model actually recognized handwriting
            # or found a concrete issue worth carrying into the ledger.
            if (result.handwritten or result.has_issue) and result.explanation and "Unknown error" not in result.explanation:
                db.update_status(concept, "persists")
                signature = make_lens_signature(image_bytes, result.explanation)
                db.set_debt_integrity(concept, integrity_suspect=False, clearing_method="lens_verified", lens_signature=signature)
                self.event_bus.put({"type": "DEBT_PERSISTS", "concept": concept})
            
            return result
        finally:
            if config.LOW_RAM:
                self.resource_lock.release()

    def trigger_solo_mode(self, concept: str, response: str, session_id: str) -> Dict[str, Any]:
        prior = db.get_prior_solo_questions(concept)
        solo = db.get_solo_session(session_id)
        if solo:
            question = solo.get("question", "")
        else:
            question = generate_solo_question(concept, prior)
            started_at = datetime.utcnow()
            expires_at = started_at + timedelta(seconds=config.SOLO_TIMEOUT_SECONDS)
            db.create_solo_session(
                session_id=session_id,
                concept=concept,
                question=question,
                started_at=started_at.isoformat(),
                expires_at=expires_at.isoformat(),
            )

        evaluation = evaluate_real_learning(concept, question, response)
        db.save_real_performance(
            session_id=session_id,
            concept=concept,
            mode="solo",
            score=evaluation["score"],
            reasoning=evaluation["reasoning"],
            specific_gaps=evaluation["specific_gaps"],
            question=question,
            response=response,
        )

        passed = evaluation["score"] >= 70
        if passed:
            db.update_status(concept, "clear")
            db.set_debt_integrity(concept, integrity_suspect=False, clearing_method="solo_mode")
            db.update_solo_session_status(session_id, "completed")
        else:
            db.set_debt_integrity(concept, integrity_suspect=True, clearing_method="solo_mode")
            db.update_solo_session_status(session_id, "failed")

        return {
            "concept": concept,
            "session_id": session_id,
            "question": question,
            "passed": passed,
            "evaluation": evaluation,
        }
