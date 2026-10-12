import PriceSummaryCard from './PriceSummaryCard'
import ConfidenceMeter from './ConfidenceMeter'
import GuidancePeriodBadge from './GuidancePeriodBadge'
import KeyMetricsGrid from '../Metrics/KeyMetricsGrid'
import ValuationScenarios from '../Charts/ValuationScenarios'
import PEHistoryChart from '../Charts/PEHistoryChart'
import GuidanceTable from '../Guidance/GuidanceTable'
import SourceList from '../Guidance/SourceList'

function fmtCurrency(v) {
  if (v == null) return '?'
  return `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`
}

function buildValuationBreakdown(result) {
  const method = result.valuation_method
  const geps = result.guidance_eps
  const price = result.current_price
  const est = result.estimated_price
  const upside = result.upside_pct

  if (method === 'extracted_eps_x_median_pe' || method === 'guided_eps_x_median_pe') {
    const medianPE = result.median_pe
    return {
      methodLabel: 'Multiplies the guidance EPS by the 5-year historical median PE ratio.',
      formulaLines: [
        `${fmtCurrency(est)} = ${fmtCurrency(geps)} × ${Number(medianPE).toFixed(1)}`,
        '',
        `Upside = (${fmtCurrency(est)} − ${fmtCurrency(price)}) / ${fmtCurrency(price)}`,
        `       = ${upside != null ? (upside >= 0 ? '+' : '') + Number(upside).toFixed(1) + '%' : '?'}`,
      ],
      note: `Guidance EPS: ${fmtCurrency(geps)} · Median PE: ${Number(medianPE).toFixed(1)} (from ${result.pe_observations || '?'} monthly observations over ${result.pe_years_used || 5} years)`,
    }
  }

  if (method === 'forward_eps_x_current_pe') {
    const pe = result.current_pe_ttm
    return {
      methodLabel: 'Multiplies forward EPS by the current PE (historical median unavailable).',
      formulaLines: [
        `${fmtCurrency(est)} = ${fmtCurrency(geps)} × ${Number(pe).toFixed(1)}`,
        '',
        `Upside = (${fmtCurrency(est)} − ${fmtCurrency(price)}) / ${fmtCurrency(price)}`,
        `       = ${upside != null ? (upside >= 0 ? '+' : '') + Number(upside).toFixed(1) + '%' : '?'}`,
      ],
      note: 'Low confidence — using current PE ratio, not historical median.',
    }
  }

  if (method === 'ps_ratio_fallback') {
    const alt = result.alternative_valuations?.ps_ratio
    return {
      methodLabel: 'Negative EPS — uses Price-to-Sales ratio fallback.',
      formulaLines: alt
        ? [
            `P/S ratio = Market Cap / Revenue`,
            `          = ${fmtCurrency(result.market_cap)} / ${fmtCurrency(result.current_revenue_ttm)}`,
            `          = ${Number(alt.current_ps_ratio).toFixed(2)}`,
            '',
            `Estimated P/S = Current P/S × 0.8`,
            `              = ${Number(alt.estimated_ps_ratio).toFixed(2)}`,
          ]
        : ['Insufficient data for P/S valuation.'],
      note: 'Low confidence — PE-based valuation is meaningless when EPS is negative.',
    }
  }

  return null
}

export default function DashboardLayout({ data }) {
  const { result, guidance, confidence, sources } = data

  const guidancePeriod =
    guidance?.guidance_period ||
    result.guidance_period ||
    (result.guidance_source === 'analyst_consensus' ? 'Forward estimate' : null)

  const valuationBreakdown = buildValuationBreakdown(result)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">{result.ticker}</h1>
          <p className="text-slate-400">{result.company_name}</p>
        </div>
        <GuidancePeriodBadge period={guidancePeriod} />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <PriceSummaryCard label="Current Price" value={result.current_price} format="currency" />
        <PriceSummaryCard
          label="Estimated Price"
          value={result.estimated_price}
          format="currency"
          subLabel={guidancePeriod}
          formulaBreakdown={valuationBreakdown}
        />
        <PriceSummaryCard
          label="Upside / Downside"
          value={result.upside_pct}
          format="percent"
          positive={result.upside_pct > 0}
        />
      </div>

      <div className="flex gap-4">
        <div className="flex-1">
          <ConfidenceMeter
            score={confidence?.valuation_confidence || result.confidence_score}
            label={confidence?.confidence_label}
            breakdown={confidence?.breakdown}
          />
        </div>
        <KeyMetricsGrid result={result} guidance={guidance} />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <ValuationScenarios result={result} />
        <PEHistoryChart result={result} />
      </div>

      {guidance?.eps_guidance && (
        <GuidanceTable guidance={guidance} />
      )}

      {sources?.length > 0 && (
        <SourceList sources={sources} />
      )}
    </div>
  )
}
