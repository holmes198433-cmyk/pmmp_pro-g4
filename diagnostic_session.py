from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class DiagnosticEvidence:
    hypothesis: str
    probability: float
    supporting_signatures: List[str] = field(default_factory=list)
    contradicting_signatures: List[str] = field(default_factory=list)
    next_best_tests: List[str] = field(default_factory=list)
    suggested_action: str = ""
    explanation: str = ""


@dataclass
class DiagnosticSession:
    operating_state: str
    telemetry: Dict[str, Any] = field(default_factory=dict)
    active_dtcs: List[str] = field(default_factory=list)
    evidence: List[DiagnosticEvidence] = field(default_factory=list)
    recommended_tests: List[str] = field(default_factory=list)
    status: str = "OBSERVING"

    @classmethod
    def from_hypotheses(
        cls,
        telemetry: Dict[str, Any],
        dtc_analysis: Dict[str, Any],
        hypotheses: List[Any],
        operating_state: str = "unknown",
    ) -> "DiagnosticSession":
        evidence: List[DiagnosticEvidence] = []
        recommendations: List[str] = []

        for hypothesis in hypotheses[:3]:
            evidence.append(
                DiagnosticEvidence(
                    hypothesis=hypothesis.hypothesis,
                    probability=hypothesis.probability,
                    supporting_signatures=list(hypothesis.supporting_signatures),
                    contradicting_signatures=list(hypothesis.contradicting_signatures),
                    next_best_tests=list(hypothesis.next_best_tests),
                    suggested_action=hypothesis.suggested_action,
                    explanation=hypothesis.explanation,
                )
            )
            recommendations.extend(hypothesis.next_best_tests)

        recommendations = sorted(set(recommendations))
        top_probability = evidence[0].probability if evidence else 0.0
        status = "NO_FAULTS" if not evidence else ("READY" if top_probability >= 0.5 else "OBSERVING")

        return cls(
            operating_state=operating_state,
            telemetry=dict(telemetry),
            active_dtcs=list(dtc_analysis.get("raw_input_codes", []) or dtc_analysis.get("root_causes", [])),
            evidence=evidence,
            recommended_tests=recommendations,
            status=status,
        )

    def summary(self) -> str:
        if not self.evidence:
            return "Diagnostic session: no active evidence; system is observing passively."

        top = self.evidence[0]
        lines = [
            f"Diagnostic session: {self.status} | operating state={self.operating_state}",
            f"Top hypothesis: {top.hypothesis} ({top.probability * 100:.1f}% confidence)",
        ]
        if top.supporting_signatures:
            lines.append(f"Evidence: {top.supporting_signatures[0]}")
        if self.recommended_tests:
            lines.append(f"Recommended next tests: {', '.join(self.recommended_tests[:3])}")
        return " | ".join(lines)

