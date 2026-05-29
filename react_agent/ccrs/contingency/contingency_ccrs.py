"""Python wrapper for Java contingency `ContingencyCcrs`.

This module evaluates Java contingency strategies for a `Situation`, records
the resulting `CcrsTrace` through a `CcrsContext`, and converts Java strategy
results into dictionaries for the React/LangGraph adapter.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from react_agent.ccrs.audit import log_ccrs_event
from react_agent.ccrs.contingency.ccrs_context import InMemoryCcrsContext
from react_agent.ccrs.contingency.situation import Situation
from react_agent.ccrs.java_runtime import CcrsJavaRuntime, CcrsJavaRuntimeError


logger = logging.getLogger(__name__)
LOG_PREFIX = "[React CCRS][Contingency]"


@dataclass
class ContingencyCcrs:
    """Runs Java contingency CCRS strategy evaluation."""

    java_runtime: CcrsJavaRuntime = field(default_factory=CcrsJavaRuntime.from_maven_local)
    discover_strategy_providers: bool = False

    _contingency_ccrs: Any = field(default=None, init=False, repr=False)
    _classes: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _runtime_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @classmethod
    def from_maven_local(
        cls,
        *,
        group: str = "io.github.stefanmhsg.ccrs",
        version: str = "0.1.0-SNAPSHOT",
        modules: Iterable[str] = ("ccrs-core",),
        maven_repo: str | Path | None = None,
        gradle_cache: str | Path | None = None,
        extra_classpath: Iterable[str | Path] = (),
        discover_strategy_providers: bool = False,
    ) -> "ContingencyCcrs":
        return cls(
            java_runtime=CcrsJavaRuntime.from_maven_local(
                group=group,
                version=version,
                modules=modules,
                maven_repo=maven_repo,
                gradle_cache=gradle_cache,
                extra_classpath=extra_classpath,
            ),
            discover_strategy_providers=discover_strategy_providers,
        )

    def evaluate(
        self,
        situation: Situation | Mapping[str, Any],
        context: Any | None = None,
    ) -> dict[str, Any]:
        """Evaluate Java `ContingencyCcrs` and return a trace dictionary."""

        normalized = _normalize_situation(situation)
        self._ensure_runtime()
        java_situation = self._to_java_situation(normalized)
        java_context, trace_recorder = self._to_java_context(context, normalized)

        log_ccrs_event(
            logger,
            "react.ccrs.contingency.evaluate",
            {
                **self._strategy_policy_fields(),
                "situation_type": normalized.type_name,
                "trigger": normalized.trigger,
                "current_resource": normalized.current_resource,
                "target_resource": normalized.target_resource,
                "failed_action": normalized.failed_action,
            },
        )

        try:
            trace = self._contingency_ccrs.evaluateWithTrace(java_situation, java_context)
            if trace_recorder is not None:
                trace_recorder.recordCcrsInvocation(trace)
            else:
                java_context.recordCcrsInvocation(trace)
        except Exception as exc:
            raise CcrsJavaRuntimeError("Java contingency CCRS evaluation failed.") from exc

        result = self._trace_to_dict(trace)
        top = result.get("top_suggestion") or {}
        log_ccrs_event(
            logger,
            "react.ccrs.contingency.returned",
            {
                **self._strategy_policy_fields(),
                "trace_id": result.get("trace_id"),
                "evaluations": len(result.get("evaluations", [])),
                "suggestions": len(result.get("suggestions", [])),
                "no_help": len(result.get("no_help", [])),
                "opportunistic_guidance": len(result.get("opportunistic_guidance", [])),
                "top_strategy_id": top.get("strategy_id"),
                "top_action_type": top.get("action_type"),
                "stop": result.get("stop"),
            },
        )
        return result

    def _ensure_runtime(self) -> None:
        """Load Java contingency classes and create the Java evaluator."""

        jpype = self.java_runtime.ensure_jvm(
            audit_event_namespace="react.ccrs.contingency",
            log=logger,
            log_prefix=LOG_PREFIX,
        )

        with self._runtime_lock:
            self._load_classes(jpype)
            if self._contingency_ccrs is None:
                self._contingency_ccrs = self._new_contingency_ccrs(jpype)
                log_ccrs_event(
                    logger,
                    "react.ccrs.contingency.runtime.ready",
                    {
                        "entrypoint": "ccrs.core.contingency.ContingencyCcrs",
                        "discovered_providers": self.discover_strategy_providers,
                        "registered_strategies": self._registered_strategy_ids(),
                        **self._strategy_policy_fields(),
                    },
                )

    def _load_classes(self, jpype: Any) -> None:
        if self._classes:
            return

        try:
            self._classes = {
                "ArrayList": self.java_runtime.class_(jpype, "java.util.ArrayList"),
                "HashMap": self.java_runtime.class_(jpype, "java.util.HashMap"),
                "Optional": self.java_runtime.class_(jpype, "java.util.Optional"),
                "RdfTriple": self.java_runtime.class_(jpype, "ccrs.core.rdf.RdfTriple"),
                "CcrsContext": self.java_runtime.class_(jpype, "ccrs.core.rdf.CcrsContext"),
                "Neighborhood": self.java_runtime.class_(jpype, "ccrs.core.rdf.CcrsContext$Neighborhood"),
                "Interaction": self.java_runtime.class_(jpype, "ccrs.core.contingency.dto.Interaction"),
                "InteractionOutcome": self.java_runtime.class_(jpype, "ccrs.core.contingency.dto.Interaction$Outcome"),
                "Situation": self.java_runtime.class_(jpype, "ccrs.core.contingency.dto.Situation"),
                "SituationType": self.java_runtime.class_(jpype, "ccrs.core.contingency.dto.Situation$Type"),
                "ContingencyCcrs": self.java_runtime.class_(jpype, "ccrs.core.contingency.ContingencyCcrs"),
                "ContingencyCcrsFactory": self.java_runtime.class_(
                    jpype,
                    "ccrs.core.contingency.ContingencyCcrsFactory",
                ),
            }
            logger.info("%s Loaded Java contingency CCRS classes through JPype.", LOG_PREFIX)
        except Exception as exc:
            raise CcrsJavaRuntimeError(
                "Failed to load Java contingency CCRS classes. Check that ccrs-core "
                "and its dependencies are on the JPype classpath."
            ) from exc

    def _new_contingency_ccrs(self, jpype: Any) -> Any:
        if self.discover_strategy_providers:
            class_loader = jpype.JClass("org.jpype.JPypeContext").getInstance().getClassLoader()
            return self._classes["ContingencyCcrsFactory"].withDefaultsAndDiscoveredProviders(class_loader)
        return self._classes["ContingencyCcrs"].withDefaults()

    def _to_java_situation(self, situation: Situation) -> Any:
        """Convert Python `Situation` input into Java `Situation`."""

        try:
            java_type = self._classes["SituationType"].valueOf(situation.type_name)
        except Exception as exc:
            raise ValueError(f"Unsupported contingency situation type: {situation.type_name}") from exc

        builder = self._classes["Situation"].builder(java_type)
        if situation.trigger is not None:
            builder.trigger(str(situation.trigger))
        if situation.current_resource is not None:
            builder.currentResource(str(situation.current_resource))
        if situation.target_resource is not None:
            builder.targetResource(str(situation.target_resource))
        if situation.failed_action is not None:
            builder.failedAction(str(situation.failed_action))
        for key, value in situation.error_info.items():
            if value is not None:
                builder.errorInfo(str(key), _java_scalar(value))
        for key, value in situation.metadata.items():
            if value is not None:
                builder.metadata(str(key), _java_scalar(value))
        return builder.build()

    def _to_java_context(
        self,
        context: Any | None,
        situation: Situation,
    ) -> tuple[Any, Any | None]:
        if context is None:
            context = InMemoryCcrsContext(
                agent_id=str(situation.metadata.get("agent_name", "React")),
                current_resource=situation.current_resource,
            )

        if hasattr(context, "as_java_proxy"):
            jpype = self.java_runtime.ensure_jvm(
                audit_event_namespace="react.ccrs.contingency",
                log=logger,
                log_prefix=LOG_PREFIX,
            )
            return (
                context.as_java_proxy(jpype, self._classes["CcrsContext"], self._classes),
                context,
            )
        return context, None

    def _trace_to_dict(self, trace: Any) -> dict[str, Any]:
        """Convert Java `CcrsTrace` into the adapter result schema."""

        selected_results = [
            self._strategy_result_to_dict(result)
            for result in trace.getSelectedResults()
        ]
        evaluations = [
            self._strategy_evaluation_to_dict(evaluation)
            for evaluation in trace.getEvaluations()
        ]
        suggestions = [
            result for result in selected_results
            if result.get("result_type") == "suggestion"
        ]
        no_help = [
            evaluation["result"]
            for evaluation in evaluations
            if evaluation.get("result", {}).get("result_type") == "no_help"
        ]
        opportunistic_guidance: list[dict[str, Any]] = []
        for suggestion in suggestions:
            opportunistic_guidance.extend(suggestion.get("opportunistic_guidance", []))

        return {
            "ccrs_type": "contingency",
            "trace_id": str(trace.getId()),
            "timestamp": str(trace.getTimestamp()),
            "strategy_selection": self._strategy_policy_fields(),
            "situation": self._situation_to_dict(trace.getSituation()),
            "selection_reason": str(trace.getSelectionReason()),
            "total_evaluation_time_ms": int(trace.getTotalEvaluationTimeMs()),
            "outcome": str(trace.getOutcome()),
            "evaluations": evaluations,
            "selected_results": selected_results,
            "suggestions": suggestions,
            "no_help": no_help,
            "opportunistic_guidance": opportunistic_guidance,
            "top_suggestion": suggestions[0] if suggestions else None,
            "stop": any(
                suggestion.get("action_type") == "stop"
                for suggestion in suggestions
            ),
        }

    def _strategy_evaluation_to_dict(self, evaluation: Any) -> dict[str, Any]:
        result = evaluation.getResult()
        return {
            "strategy_id": str(evaluation.getStrategyId()),
            "escalation_level": int(evaluation.getEscalationLevel()),
            "applicability": str(evaluation.getApplicability()),
            "evaluation_time_ms": int(evaluation.getEvaluationTimeMs()),
            "result": self._strategy_result_to_dict(result) if result is not None else {"result_type": "none"},
        }

    def _strategy_result_to_dict(self, result: Any) -> dict[str, Any]:
        """Convert Java `StrategyResult` to a suggestion or no-help dictionary."""

        strategy_id = str(result.getStrategyId())
        if result.isSuggestion():
            suggestion = result.asSuggestion()
            guidance = [
                self._opportunistic_result_to_dict(entry)
                for entry in suggestion.getOpportunisticGuidance()
            ]
            return {
                "ccrs_type": "contingency",
                "result_type": "suggestion",
                "strategy_id": strategy_id,
                "action_type": _none_or_str(suggestion.getActionType()),
                "action_target": _none_or_str(suggestion.getActionTarget()),
                "action_params": _java_map_to_python(suggestion.getActionParams()),
                "confidence": float(suggestion.getConfidence()),
                "rationale": _none_or_str(suggestion.getRationale()),
                "opportunistic_guidance": guidance,
            }

        no_help = result.asNoHelp()
        return {
            "ccrs_type": "contingency",
            "result_type": "no_help",
            "strategy_id": strategy_id,
            "reason": str(no_help.getReason()),
            "explanation": _none_or_str(no_help.getExplanation()),
        }

    def _opportunistic_result_to_dict(self, result: Any) -> dict[str, Any]:
        metadata = _java_map_to_python(result.getMetadataMap())
        return {
            "ccrs_type": "opportunistic",
            "type": str(result.type),
            "target": str(result.target),
            "pattern_id": str(result.patternId),
            "utility": float(result.utility),
            "metadata": metadata,
        }

    def _situation_to_dict(self, situation: Any) -> dict[str, Any]:
        return {
            "type": str(situation.getType()),
            "trigger": _none_or_str(situation.getTrigger()),
            "current_resource": _none_or_str(situation.getCurrentResource()),
            "target_resource": _none_or_str(situation.getTargetResource()),
            "failed_action": _none_or_str(situation.getFailedAction()),
            "error_info": _java_map_to_python(situation.getErrorInfo()),
            "metadata": _java_map_to_python(situation.getMetadata()),
        }

    def _strategy_policy_fields(self) -> dict[str, Any]:
        if self._contingency_ccrs is None:
            return {}
        config = self._contingency_ccrs.getConfig()
        policy = self._contingency_ccrs.getStrategySelectionPolicy()
        return {
            "escalation_policy": str(config.getEscalationPolicy()),
            "learned_selection_enabled": bool(config.isLearnedSelectionEnabled()),
            "selection_policy": str(policy.getDescription()),
        }

    def _registered_strategy_ids(self) -> str:
        if self._contingency_ccrs is None:
            return ""
        return ",".join(
            str(strategy.getId())
            for strategy in self._contingency_ccrs.getRegistry().getAll()
        )


def get_default_contingency_ccrs() -> ContingencyCcrs:
    """Return the process-local Java `ContingencyCcrs` wrapper."""

    global _default_contingency_ccrs
    if _default_contingency_ccrs is None:
        _default_contingency_ccrs = ContingencyCcrs.from_maven_local()
    return _default_contingency_ccrs


def _normalize_situation(
    situation: Situation | Mapping[str, Any],
) -> Situation:
    if isinstance(situation, Situation):
        return situation
    return Situation.from_mapping(situation)


def _java_scalar(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _none_or_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _java_map_to_python(java_map: Any) -> dict[str, Any]:
    if java_map is None:
        return {}
    return {
        str(entry.getKey()): _java_value_to_python(entry.getValue())
        for entry in java_map.entrySet()
    }


def _java_value_to_python(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "entrySet"):
        return _java_map_to_python(value)
    if hasattr(value, "toArray") and hasattr(value, "size"):
        return [_java_value_to_python(item) for item in list(value)]
    return str(value)


_default_contingency_ccrs: ContingencyCcrs | None = None
