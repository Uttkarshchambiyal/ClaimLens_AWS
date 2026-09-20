import { Activity, BarChart3, CircleCheck, FileWarning, ShieldCheck } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, Label, Pie, PieChart, XAxis, YAxis } from 'recharts'

import type { Analysis, CheckStatus } from '../types'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from './ui/chart'

const requiresAttention = (status: CheckStatus) =>
  status === 'FINDING' || status === 'INSUFFICIENT_EVIDENCE' || status === 'ERROR'

const queueChartConfig = {
  attention: {
    label: 'Needs attention',
    theme: { light: '#9d431d', dark: '#f1a87d' },
  },
  resolved: {
    label: 'Resolved',
    theme: { light: '#607b35', dark: '#c5e38f' },
  },
  high: { label: 'High', theme: { light: '#9d431d', dark: '#f1a87d' } },
  medium: { label: 'Medium', theme: { light: '#b58a26', dark: '#e4c46c' } },
  low: { label: 'Low', theme: { light: '#607b35', dark: '#c5e38f' } },
} satisfies ChartConfig

const claimChartConfig = {
  quality: {
    label: 'Extraction quality',
    theme: { light: '#607b35', dark: '#c5e38f' },
  },
  finding: {
    label: 'Needs review',
    theme: { light: '#9d431d', dark: '#f1a87d' },
  },
  evidence: {
    label: 'Evidence needed',
    theme: { light: '#b58a26', dark: '#e4c46c' },
  },
  pass: { label: 'Passed', theme: { light: '#237450', dark: '#8bd6ad' } },
  unavailable: {
    label: 'Unavailable / N/A',
    theme: { light: '#8a9390', dark: '#9da7a4' },
  },
} satisfies ChartConfig

function ChartEmpty({ detail }: { detail: string }) {
  return (
    <div className="chart-empty">
      <BarChart3 size={25} />
      <p>{detail}</p>
    </div>
  )
}

export function QueueAnalytics({ analyses }: { analyses: Analysis[] }) {
  const packetData = analyses
    .slice(0, 7)
    .reverse()
    .map((item) => ({
      packet: item.claimId.replace(/^CLM-/, '#'),
      attention: item.findings.filter((finding) => requiresAttention(finding.status)).length,
      resolved: item.findings.filter((finding) => finding.reviewerAction === 'RESOLVED').length,
    }))
  const priorityData = (['HIGH', 'MEDIUM', 'LOW'] as const).map((priority) => ({
    name: priority.toLowerCase(),
    value: analyses.filter((item) => item.reviewPriority === priority).length,
    fill: `var(--color-${priority.toLowerCase()})`,
  }))
  const outstanding = analyses.reduce(
    (total, item) =>
      total +
      item.findings.filter(
        (finding) => requiresAttention(finding.status) && finding.reviewerAction !== 'RESOLVED',
      ).length,
    0,
  )

  return (
    <section className="analytics-section" aria-labelledby="queue-insights-title">
      <div className="analytics-heading">
        <div>
          <span className="eyebrow">Review intelligence</span>
          <h2 id="queue-insights-title">See the workload at a glance</h2>
          <p>Charts use only the claim packets currently visible to this workspace.</p>
        </div>
        <span className="analytics-live">
          <Activity size={14} /> Current queue
        </span>
      </div>
      <div className="analytics-grid queue-analytics-grid">
        <Card className="analytics-card analytics-card-wide">
          <CardHeader>
            <div>
              <CardTitle>Attention by packet</CardTitle>
              <CardDescription>
                Open review signals compared with resolved findings.
              </CardDescription>
            </div>
            <span className="analytics-number">
              {outstanding}
              <small>open signals</small>
            </span>
          </CardHeader>
          <CardContent>
            {packetData.length ? (
              <ChartContainer
                config={queueChartConfig}
                className="analytics-chart"
                aria-label="Needs-attention and resolved findings by claim packet"
              >
                <BarChart accessibilityLayer data={packetData} margin={{ left: 0, right: 8 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="packet" tickLine={false} axisLine={false} tickMargin={10} />
                  <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={24} />
                  <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
                  <ChartLegend content={<ChartLegendContent />} />
                  <Bar
                    dataKey="attention"
                    fill="var(--color-attention)"
                    radius={[6, 6, 0, 0]}
                    isAnimationActive={false}
                  />
                  <Bar
                    dataKey="resolved"
                    fill="var(--color-resolved)"
                    radius={[6, 6, 0, 0]}
                    isAnimationActive={false}
                  />
                </BarChart>
              </ChartContainer>
            ) : (
              <ChartEmpty detail="Charts will appear after the first packet is added." />
            )}
          </CardContent>
        </Card>
        <Card className="analytics-card priority-card">
          <CardHeader>
            <div>
              <CardTitle>Priority mix</CardTitle>
              <CardDescription>How the queue is distributed.</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            {analyses.length ? (
              <ChartContainer
                config={queueChartConfig}
                className="analytics-chart analytics-donut"
                aria-label="Claim packets by review priority"
              >
                <PieChart accessibilityLayer>
                  <ChartTooltip content={<ChartTooltipContent hideLabel nameKey="name" />} />
                  <Pie
                    data={priorityData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={58}
                    outerRadius={83}
                    paddingAngle={3}
                    stroke="none"
                    isAnimationActive={false}
                  >
                    {priorityData.map((entry) => (
                      <Cell key={entry.name} fill={entry.fill} />
                    ))}
                    <Label
                      content={({ viewBox }) => {
                        if (!viewBox || !('cx' in viewBox) || !('cy' in viewBox)) return null
                        return (
                          <text
                            x={viewBox.cx}
                            y={viewBox.cy}
                            textAnchor="middle"
                            dominantBaseline="middle"
                          >
                            <tspan className="donut-value" x={viewBox.cx} y={viewBox.cy}>
                              {analyses.length}
                            </tspan>
                            <tspan
                              className="donut-label"
                              x={viewBox.cx}
                              y={(viewBox.cy || 0) + 21}
                            >
                              packets
                            </tspan>
                          </text>
                        )
                      }}
                    />
                  </Pie>
                  <ChartLegend content={<ChartLegendContent nameKey="name" />} />
                </PieChart>
              </ChartContainer>
            ) : (
              <ChartEmpty detail="No priority distribution is available yet." />
            )}
          </CardContent>
        </Card>
      </div>
    </section>
  )
}

export function ClaimAnalytics({ analysis }: { analysis: Analysis }) {
  const documentData = analysis.documents.map((document) => ({
    document:
      document.type === 'BILL'
        ? 'Bill'
        : document.type === 'DISCHARGE_SUMMARY'
          ? 'Discharge'
          : 'Report',
    quality: document.extractionQuality || 0,
  }))
  const findingData = [
    {
      name: 'finding',
      value: analysis.findings.filter((item) => item.status === 'FINDING').length,
      fill: 'var(--color-finding)',
    },
    {
      name: 'evidence',
      value: analysis.findings.filter((item) => item.status === 'INSUFFICIENT_EVIDENCE').length,
      fill: 'var(--color-evidence)',
    },
    {
      name: 'pass',
      value: analysis.findings.filter((item) => item.status === 'PASS').length,
      fill: 'var(--color-pass)',
    },
    {
      name: 'unavailable',
      value: analysis.findings.filter(
        (item) => item.status === 'ERROR' || item.status === 'NOT_APPLICABLE',
      ).length,
      fill: 'var(--color-unavailable)',
    },
  ]
  const evidenceRefs = analysis.findings.flatMap((item) => item.evidence)
  const averageConfidence = evidenceRefs.length
    ? Math.round(
        evidenceRefs.reduce((total, evidence) => total + evidence.confidence, 0) /
          evidenceRefs.length,
      )
    : 0
  const resolved = analysis.findings.filter((item) => item.reviewerAction === 'RESOLVED').length

  return (
    <section className="analytics-section claim-analytics" aria-labelledby="claim-insights-title">
      <div className="analytics-heading">
        <div>
          <span className="eyebrow">Packet perspective</span>
          <h2 id="claim-insights-title">Review insights</h2>
          <p>
            Visual summaries support triage; source evidence remains the basis for every decision.
          </p>
        </div>
        <span className="analytics-live">
          <ShieldCheck size={14} /> Human decision required
        </span>
      </div>
      <div className="insight-strip">
        <div>
          <CircleCheck size={18} />
          <span>Resolved</span>
          <strong>
            {resolved}/{analysis.findings.length}
          </strong>
        </div>
        <div>
          <Activity size={18} />
          <span>Average source confidence</span>
          <strong>{evidenceRefs.length ? `${averageConfidence}%` : 'N/A'}</strong>
        </div>
        <div>
          <FileWarning size={18} />
          <span>Coverage gaps</span>
          <strong>{Math.max(0, 100 - analysis.coverage)}%</strong>
        </div>
      </div>
      <div className="analytics-grid claim-analytics-grid">
        <Card className="analytics-card analytics-card-wide">
          <CardHeader>
            <div>
              <CardTitle>Document extraction quality</CardTitle>
              <CardDescription>OCR confidence by uploaded document type.</CardDescription>
            </div>
            <span className="analytics-number">
              {analysis.extractionQuality}%<small>packet quality</small>
            </span>
          </CardHeader>
          <CardContent>
            {documentData.length ? (
              <ChartContainer
                config={claimChartConfig}
                className="analytics-chart"
                aria-label="Extraction quality by document"
              >
                <BarChart
                  accessibilityLayer
                  data={documentData}
                  layout="vertical"
                  margin={{ left: 4, right: 24 }}
                >
                  <CartesianGrid horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} tickLine={false} axisLine={false} />
                  <YAxis
                    type="category"
                    dataKey="document"
                    tickLine={false}
                    axisLine={false}
                    width={72}
                  />
                  <ChartTooltip
                    cursor={false}
                    content={
                      <ChartTooltipContent
                        hideLabel
                        formatter={(value) => (
                          <>
                            <span>Extraction quality</span>
                            <b>{String(value)}%</b>
                          </>
                        )}
                      />
                    }
                  />
                  <Bar
                    dataKey="quality"
                    fill="var(--color-quality)"
                    radius={[0, 7, 7, 0]}
                    isAnimationActive={false}
                  />
                </BarChart>
              </ChartContainer>
            ) : (
              <ChartEmpty detail="No document quality results are available." />
            )}
          </CardContent>
        </Card>
        <Card className="analytics-card priority-card">
          <CardHeader>
            <div>
              <CardTitle>Check outcomes</CardTitle>
              <CardDescription>Evidence-backed status distribution.</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            {analysis.findings.length ? (
              <ChartContainer
                config={claimChartConfig}
                className="analytics-chart analytics-donut"
                aria-label="Finding status distribution"
              >
                <PieChart accessibilityLayer>
                  <ChartTooltip content={<ChartTooltipContent hideLabel nameKey="name" />} />
                  <Pie
                    data={findingData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={58}
                    outerRadius={83}
                    paddingAngle={3}
                    stroke="none"
                    isAnimationActive={false}
                  >
                    {findingData.map((entry) => (
                      <Cell key={entry.name} fill={entry.fill} />
                    ))}
                    <Label
                      content={({ viewBox }) => {
                        if (!viewBox || !('cx' in viewBox) || !('cy' in viewBox)) return null
                        return (
                          <text
                            x={viewBox.cx}
                            y={viewBox.cy}
                            textAnchor="middle"
                            dominantBaseline="middle"
                          >
                            <tspan className="donut-value" x={viewBox.cx} y={viewBox.cy}>
                              {analysis.findings.length}
                            </tspan>
                            <tspan
                              className="donut-label"
                              x={viewBox.cx}
                              y={(viewBox.cy || 0) + 21}
                            >
                              checks
                            </tspan>
                          </text>
                        )
                      }}
                    />
                  </Pie>
                  <ChartLegend content={<ChartLegendContent nameKey="name" />} />
                </PieChart>
              </ChartContainer>
            ) : (
              <ChartEmpty detail="No check outcomes are available." />
            )}
          </CardContent>
        </Card>
      </div>
      <p className="analytics-disclaimer">
        These charts summarize extracted evidence and workflow status. They are not fraud scores and
        do not approve or reject a claim.
      </p>
    </section>
  )
}
