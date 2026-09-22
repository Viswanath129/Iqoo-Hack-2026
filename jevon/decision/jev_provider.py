"""Cloud-assisted decision provider with safe local fallback for JEVON."""

from __future__ import annotations

import logging
import os

from jevon.decision.actions import DeveloperAction, DeveloperDecision, normalize_probabilities
from jevon.decision.local_provider import LocalDecisionProvider
from jevon.decision.provider import DecisionProvider, StateObservation
from jevon.truth_first.state import TruthFirstState

logger = logging.getLogger(__name__)


class TypeSafeJevProvider(DecisionProvider):
    """Cloud-assisted decision provider using TypeSafe classification with guaranteed local fallback."""

    def __init__(
        self,
        api_key: str | None = None,
        local_fallback: LocalDecisionProvider | None = None,
    ) -> None:
        """Initialize provider with optional API key and fallback provider."""
        self._api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
        self._local_provider = local_fallback or LocalDecisionProvider()

    @property
    def name(self) -> str:
        return "TypeSafeJevProvider"

    def is_available(self) -> bool:
        """Provider is always operational via offline fallback."""
        return True

    def has_cloud_credentials(self) -> bool:
        """Return True if cloud API credentials are configured."""
        return bool(self._api_key and self._api_key.strip())

    def _call_cloud_classifier(
        self, state: TruthFirstState, observation: StateObservation
    ) -> DeveloperDecision:
        """Invoke TypeSafe Choice classifier over the bounded action space."""
        try:
            from typesafe_sdk import Choice, TypeSafeClient  # type: ignore
        except ImportError as err:
            raise RuntimeError("typesafe_sdk not installed in environment") from err

        prompt_context = (
            f"Goal: {state.goal}\n"
            f"Exit code: {observation.compiler_exit_code}\n"
            f"Active file: {observation.active_file}\n"
            f"Recent error: {observation.recent_error}\n"
            f"Terminal: {observation.terminal_output[-300:] if observation.terminal_output else ''}"
        )

        criteria = {
            DeveloperAction.INSPECT_ERROR.value: "Parse compiler or test error trace to find culprit file",
            DeveloperAction.INSPECT_FILE.value: "Read source code context around the failing line",
            DeveloperAction.RUN_TARGETED_TEST.value: "Run the specific failing test to verify a fix",
            DeveloperAction.RERUN_BUILD.value: "Rerun project build/test suite to verify workspace",
            DeveloperAction.INSPECT_RECENT_CHANGE.value: "Inspect git diff to find introduced regressions",
            DeveloperAction.APPLY_FIX.value: "Apply targeted code patch or replacement to culprit file",
            DeveloperAction.REQUEST_CONFIRMATION.value: "Pause to ask human developer approval",
            DeveloperAction.DONE.value: "Build and tests pass cleanly, task complete",
        }

        # Initialize Choice classifier with bounded criteria
        choice = Choice(
            instructions=(
                "You are an on-device developer decision engine. Select the single best next "
                "action to make progress on diagnosing and resolving the developer task."
            ),
            criteria=criteria,
        )
        client = TypeSafeClient(api_key=self._api_key)
        response = client.system_one(
            state={"context": prompt_context},
            questions={"decision": choice},
        )
        result = response.answers["decision"]

        # Extract predicted action and confidence
        action_str = getattr(result, "choice", DeveloperAction.INSPECT_ERROR.value)
        action = DeveloperAction(action_str)
        confidence = float(getattr(result, "confidence", 0.85))

        # Extract or construct probability distribution
        raw_probs = getattr(result, "probabilities", {})
        if not raw_probs:
            raw_probs = {a.value: (confidence if a == action else (1.0 - confidence) / 7.0) for a in DeveloperAction.all_actions()}

        probs = normalize_probabilities(raw_probs)

        return DeveloperDecision(
            action=action,
            confidence=confidence,
            probabilities=probs,
            parameters={"cloud_routed": True},
            metadata={"provider": self.name, "cloud_classified": True},
        )

    def decide(self, state: TruthFirstState, observation: StateObservation) -> DeveloperDecision:
        """Evaluate state; try cloud classification if credentials exist, falling back safely to local FSM."""
        if not self.has_cloud_credentials():
            logger.debug("[JevProvider] No TYPESAFE_API_KEY; using LocalDecisionProvider fallback.")
            decision = self._local_provider.decide(state, observation)
            decision.metadata["cloud_fallback"] = True
            decision.metadata["fallback_reason"] = "no_credentials"
            return decision

        try:
            return self._call_cloud_classifier(state, observation)
        except Exception as e:
            logger.warning("[JevProvider] Cloud classification failed (%s); falling back to local.", e)
            decision = self._local_provider.decide(state, observation)
            decision.metadata["cloud_fallback"] = True
            decision.metadata["fallback_reason"] = str(e)
            return decision
