import * as React from 'react'
import * as RechartsPrimitive from 'recharts'

import { cn } from '@/lib/utils'

const THEMES = { light: '', dark: '.dark' } as const

export type ChartConfig = Record<
  string,
  {
    label?: React.ReactNode
    icon?: React.ComponentType
  } & (
    | { color?: string; theme?: never }
    | { color?: never; theme: Record<keyof typeof THEMES, string> }
  )
>

const ChartContext = React.createContext<{ config: ChartConfig } | null>(null)

function useChart() {
  const context = React.useContext(ChartContext)
  if (!context) throw new Error('useChart must be used within a <ChartContainer />')
  return context
}

const ChartContainer = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<'div'> & {
    config: ChartConfig
    children: React.ComponentProps<typeof RechartsPrimitive.ResponsiveContainer>['children']
  }
>(({ id, className, children, config, ...props }, ref) => {
  const uniqueId = React.useId()
  const chartId = `chart-${id || uniqueId.replace(/:/g, '')}`

  return (
    <ChartContext.Provider value={{ config }}>
      <div ref={ref} data-chart={chartId} className={cn('chart-container', className)} {...props}>
        <ChartStyle id={chartId} config={config} />
        <RechartsPrimitive.ResponsiveContainer>{children}</RechartsPrimitive.ResponsiveContainer>
      </div>
    </ChartContext.Provider>
  )
})
ChartContainer.displayName = 'Chart'

function ChartStyle({ id, config }: { id: string; config: ChartConfig }) {
  const colorConfig = Object.entries(config).filter(([, value]) => value.theme || value.color)
  if (!colorConfig.length) return null

  return (
    <style
      dangerouslySetInnerHTML={{
        __html: Object.entries(THEMES)
          .map(
            ([theme, prefix]) => `${prefix} [data-chart=${id}] {
${colorConfig
  .map(([key, value]) => {
    const color = value.theme?.[theme as keyof typeof value.theme] || value.color
    return color ? `  --color-${key}: ${color};` : null
  })
  .filter(Boolean)
  .join('\n')}
}`,
          )
          .join('\n'),
      }}
    />
  )
}

const ChartTooltip = RechartsPrimitive.Tooltip

type ChartTooltipContentProps = React.ComponentProps<'div'> &
  Partial<RechartsPrimitive.TooltipContentProps> & {
    hideLabel?: boolean
    hideIndicator?: boolean
    indicator?: 'line' | 'dot' | 'dashed'
    nameKey?: string
    labelKey?: string
  }

const ChartTooltipContent = React.forwardRef<HTMLDivElement, ChartTooltipContentProps>(
  (
    {
      active,
      payload,
      className,
      indicator = 'dot',
      hideLabel = false,
      hideIndicator = false,
      label,
      labelFormatter,
      formatter,
      color,
      nameKey,
      labelKey,
    },
    ref,
  ) => {
    const { config } = useChart()
    if (!active || !payload?.length) return null

    const labelItem = payload[0]
    const labelConfig = getPayloadConfigFromPayload(
      config,
      labelItem,
      `${labelKey || labelItem.dataKey || labelItem.name || 'value'}`,
    )
    const resolvedLabel =
      !labelKey && typeof label === 'string' ? config[label]?.label || label : labelConfig?.label

    return (
      <div ref={ref} className={cn('chart-tooltip', className)}>
        {!hideLabel && resolvedLabel ? (
          <strong>{labelFormatter ? labelFormatter(resolvedLabel, payload) : resolvedLabel}</strong>
        ) : null}
        <div className="chart-tooltip-list">
          {payload.map((item, index) => {
            const key = `${nameKey || item.name || item.dataKey || 'value'}`
            const itemConfig = getPayloadConfigFromPayload(config, item, key)
            const indicatorColor = color || item.payload?.fill || item.color
            return (
              <div className="chart-tooltip-row" key={`${String(item.dataKey)}-${index}`}>
                {!hideIndicator && (
                  <span
                    className={`chart-indicator chart-indicator-${indicator}`}
                    style={{ '--indicator-color': indicatorColor } as React.CSSProperties}
                  />
                )}
                {formatter && item.value !== undefined && item.name ? (
                  formatter(item.value, item.name, item, index, item.payload)
                ) : (
                  <>
                    <span>{itemConfig?.label || item.name}</span>
                    <b>
                      {typeof item.value === 'number' ? item.value.toLocaleString() : item.value}
                    </b>
                  </>
                )}
              </div>
            )
          })}
        </div>
      </div>
    )
  },
)
ChartTooltipContent.displayName = 'ChartTooltip'

const ChartLegend = RechartsPrimitive.Legend

const ChartLegendContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<'div'> & {
    payload?: ReadonlyArray<RechartsPrimitive.LegendPayload>
    verticalAlign?: RechartsPrimitive.LegendProps['verticalAlign']
    hideIcon?: boolean
    nameKey?: string
  }
>(({ className, hideIcon = false, payload, verticalAlign = 'bottom', nameKey }, ref) => {
  const { config } = useChart()
  if (!payload?.length) return null

  return (
    <div
      ref={ref}
      className={cn('chart-legend', verticalAlign === 'top' && 'chart-legend-top', className)}
    >
      {payload.map((item) => {
        const key = `${nameKey || item.dataKey || 'value'}`
        const itemConfig = getPayloadConfigFromPayload(config, item, key)
        return (
          <span key={String(item.value)}>
            {!hideIcon && <i style={{ backgroundColor: item.color }} />}
            {itemConfig?.label || item.value}
          </span>
        )
      })}
    </div>
  )
})
ChartLegendContent.displayName = 'ChartLegend'

function getPayloadConfigFromPayload(config: ChartConfig, payload: unknown, key: string) {
  if (typeof payload !== 'object' || payload === null) return undefined
  const nested =
    'payload' in payload && typeof payload.payload === 'object' && payload.payload !== null
      ? payload.payload
      : undefined
  let configKey = key
  if (key in payload && typeof payload[key as keyof typeof payload] === 'string')
    configKey = payload[key as keyof typeof payload] as string
  else if (nested && key in nested && typeof nested[key as keyof typeof nested] === 'string')
    configKey = nested[key as keyof typeof nested] as string
  return config[configKey] || config[key]
}

export {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartStyle,
  ChartTooltip,
  ChartTooltipContent,
}
