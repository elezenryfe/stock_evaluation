import re
import logging

from app.schemas.guidance import GuidanceItem, ValidationResult, ExtractionResult

logger = logging.getLogger(__name__)

MAX_EPS_DEVIATION = 2.0  # 200% deviation from current TTM EPS


class HallucinationGuard:

    def validate_eps_item(
        self,
        item: GuidanceItem,
        current_eps_ttm: float | None,
        peer_eps_range: tuple[float, float] | None = None,
    ) -> ValidationResult:
        flags: list[str] = []

        midpoint = item.value_midpoint
        if midpoint is None and item.value_low is not None and item.value_high is not None:
            midpoint = (item.value_low + item.value_high) / 2
        if midpoint is None:
            midpoint = item.value_low or item.value_high

        if midpoint is None:
            return ValidationResult(valid=False, reason="No numeric value in guidance item", flags=["no_value"])

        if current_eps_ttm is not None and current_eps_ttm != 0:
            deviation = abs(midpoint - current_eps_ttm) / abs(current_eps_ttm)
            if deviation > MAX_EPS_DEVIATION:
                reason = (
                    f"Extracted EPS {midpoint} deviates {deviation:.0%} "
                    f"from TTM EPS {current_eps_ttm} (max: {MAX_EPS_DEVIATION:.0%})"
                )
                return ValidationResult(valid=False, reason=reason, flags=["eps_out_of_range"])

        if peer_eps_range is not None:
            lo, hi = peer_eps_range
            if not (lo * 0.5 <= midpoint <= hi * 2.0):
                reason = f"EPS {midpoint} outside peer range [{lo}, {hi}]"
                flags.append("outside_peer_range")

        if item.source_quote and not self._quote_contains_value(item.source_quote, midpoint):
            flags.append("quote_mismatch")

        if flags:
            return ValidationResult(
                valid=True,
                reason=f"Passed with warnings: {', '.join(flags)}",
                flags=flags,
            )
        return ValidationResult(valid=True)

    def validate_all_items(
        self,
        result: ExtractionResult,
        current_eps_ttm: float | None = None,
        current_revenue_ttm: float | None = None,
    ) -> list[tuple[GuidanceItem, ValidationResult]]:
        outcomes: list[tuple[GuidanceItem, ValidationResult]] = []
        for item in result.guidance_items:
            if item.metric == "EPS":
                vr = self.validate_eps_item(item, current_eps_ttm)
            elif item.metric == "Revenue" and current_revenue_ttm is not None:
                vr = self._validate_revenue_item(item, current_revenue_ttm)
            else:
                vr = ValidationResult(valid=True, reason="No validation rule for metric")
            outcomes.append((item, vr))
            if not vr.valid:
                logger.warning(f"Validation failed for {item.metric}: {vr.reason}")
        return outcomes

    def filter_valid_items(
        self,
        result: ExtractionResult,
        current_eps_ttm: float | None = None,
        current_revenue_ttm: float | None = None,
    ) -> ExtractionResult:
        outcomes = self.validate_all_items(result, current_eps_ttm, current_revenue_ttm)
        valid_items = []
        invalid_count = 0
        for item, vr in outcomes:
            if vr.valid:
                valid_items.append(item)
            else:
                invalid_count += 1
        if invalid_count > 0:
            note = f"Filtered {invalid_count} invalid item(s)"
            result.extraction_notes = f"{result.extraction_notes}; {note}".strip("; ")
        result.guidance_items = valid_items
        return result

    def check_dual_run_consistency(
        self,
        run1: ExtractionResult,
        run2: ExtractionResult,
    ) -> bool:
        items1 = {(i.metric, i.period_label, i.value_midpoint) for i in run1.guidance_items}
        items2 = {(i.metric, i.period_label, i.value_midpoint) for i in run2.guidance_items}
        overlap = items1 & items2
        total = max(len(items1), len(items2), 1)
        return len(overlap) / total >= 0.7

    def _validate_revenue_item(
        self,
        item: GuidanceItem,
        current_revenue_ttm: float,
    ) -> ValidationResult:
        value = item.value_midpoint
        if value is None and item.value_low is not None and item.value_high is not None:
            value = (item.value_low + item.value_high) / 2
        if value is None:
            value = item.value_low or item.value_high
        if value is None:
            return ValidationResult(valid=False, reason="No revenue value", flags=["no_value"])

        if item.unit == "USD_billions":
            value_bn = value
        elif item.unit == "USD_millions":
            value_bn = value / 1000
        else:
            value_bn = value / 1e9

        if current_revenue_ttm > 0:
            revenue_ttm_bn = current_revenue_ttm / 1e9
            deviation = abs(value_bn - revenue_ttm_bn) / revenue_ttm_bn
            if deviation > 5.0:
                return ValidationResult(
                    valid=False,
                    reason=f"Revenue {value_bn:.1f}B deviates {deviation:.0%} from TTM {revenue_ttm_bn:.1f}B",
                    flags=["revenue_out_of_range"],
                )

        if item.source_quote and value is not None and not self._quote_contains_value(item.source_quote, value):
            return ValidationResult(valid=True, reason="Passed with warnings", flags=["quote_mismatch"])

        return ValidationResult(valid=True)

    def _quote_contains_value(self, quote: str, value: float) -> bool:
        numbers_in_quote = re.findall(
            r"\$?(\d+\.?\d*)\s*(?:billion|million|trillion|B|M|T)?",
            quote,
        )
        if not numbers_in_quote:
            return False
        try:
            extracted = [self._normalize_number(n, quote) for n in numbers_in_quote]
            return any(
                abs(n - value) / max(abs(value), 1e-9) < 0.10
                for n in extracted
                if n is not None
            )
        except Exception:
            return True

    def _normalize_number(self, num_str: str, context: str) -> float | None:
        try:
            n = float(num_str)
            if "billion" in context.lower():
                n *= 1e9
            elif "million" in context.lower():
                n *= 1e6
            return n
        except ValueError:
            return None
