"use client";

import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  Download,
  Copy,
  Check,
  ChevronDown,
  Code,
  Webhook,
  RefreshCw,
  ExternalLink,
  Info,
} from "lucide-react";
import { authFetch } from "@/lib/authFetch";

type StrategyType =
  | "ma_crossover"
  | "bollinger_rsi"
  | "macd_momentum"
  | "grid_trading"
  | "donchian_breakout"
  | "moon_phase";

interface TemplateResponse {
  type: StrategyType;
  name: string;
  description: string;
  script: string;
  version: string;
}

const STRATEGY_TYPES: { value: StrategyType; label: string; description: string }[] = [
  {
    value: "ma_crossover",
    label: "EMA Crossover",
    description: "Trend following strategy using fast and slow EMA crossover signals",
  },
  {
    value: "bollinger_rsi",
    label: "Bollinger RSI",
    description: "Mean reversion strategy combining Bollinger Bands and RSI indicators",
  },
  {
    value: "macd_momentum",
    label: "MACD Momentum",
    description: "Momentum strategy using MACD histogram and signal crossovers",
  },
  {
    value: "grid_trading",
    label: "Grid Trading",
    description: "Grid bot strategy with buy high, sell low automation",
  },
  {
    value: "donchian_breakout",
    label: "Donchian Breakout",
    description: "Breakout strategy using Donchian Channel price breakouts",
  },
  {
    value: "moon_phase",
    label: "Moon Phase",
    description: "Seasonal strategy based on lunar cycle patterns",
  },
];

const FALLBACK_SCRIPTS: Record<StrategyType, string> = {
  "ma_crossover": `//@version=5
strategy("EMA Cross Alert", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=10)

// Input parameters
emaFastLength = input.int(20, "Fast EMA Length")
emaSlowLength = input.int(50, "Slow EMA Length")
src = input.source(close, "Source")

// Calculate EMAs
emaFast = ta.ema(src, emaFastLength)
emaSlow = ta.ema(src, emaSlowLength)

// Plot EMAs
plot(emaFast, color=color.blue, title="Fast EMA")
plot(emaSlow, color=color.orange, title="Slow EMA")

// Determine crossover signals
bullCross = ta.crossover(emaFast, emaSlow)
bearCross = ta.crossunder(emaFast, emaSlow)

// Plot signals on chart
plotshape(bullCross, title="Bull Cross", location=location.belowbar, color=color.green, style=shape.triangleup, size=size.small, text="BUY")
plotshape(bearCross, title="Bear Cross", location=location.abovebar, color=color.red, style=shape.triangledown, size=size.small, text="SELL")

// Alert conditions
alertcondition(bullCross, title="Bull Cross Alert", message="Cross above EMA - BUY Signal")
alertcondition(bearCross, title="Bear Cross Alert", message="Cross below EMA - SELL Signal")

// Execute strategy (for backtesting)
if (bullCross)
    strategy.entry(id="Long", direction=strategy.long)
if (bearCross)
    strategy.close(id="Long")
`,
  "bollinger_rsi": `//@version=5
strategy("Bollinger RSI", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=10)

// Input parameters
length = input.int(20, "Bollinger Length")
mult = input.float(2.0, "Multiplier")
rsiLength = input.int(14, "RSI Length")
rsiOverbought = input.int(70, "RSI Overbought")
rsiOversold = input.int(30, "RSI Oversold")

// Calculate Bollinger Bands
[middle, upper, lower] = ta.bb(close, length, mult)

// Calculate RSI
rsi = ta.rsi(close, rsiLength)

// Plot Bollinger Bands
plot(middle, color=color.blue, title="Middle Band")
p1 = plot(upper, color=color.red, title="Upper Band")
p2 = plot(lower, color=color.green, title="Lower Band")
fill(p1, p2, color=color.new(color.blue, 90), title="Band Fill")

// Strategy signals
longSignal = ta.crossover(close, lower) and rsi < rsiOversold
shortSignal = ta.crossunder(close, upper) and rsi > rsiOverbought

plotshape(longSignal, title="Long Signal", location=location.belowbar, color=color.green, style=shape.triangleup, size=size.small, text="LONG")
plotshape(shortSignal, title="Short Signal", location=location.abovebar, color=color.red, style=shape.triangledown, size=size.small, text="SHORT")

// Alert conditions
alertcondition(longSignal, title="Long Signal", message="RSI Oversold - BUY Signal")
alertcondition(shortSignal, title="Short Signal", message="RSI Overbought - SELL Signal")

// Execute strategy
if (longSignal)
    strategy.entry(id="Long", direction=strategy.long)
if (shortSignal)
    strategy.entry(id="Short", direction=strategy.short)
`,
  "macd_momentum": `//@version=5
strategy("MACD Momentum", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=10)

// Input parameters
fastLength = input.int(12, "Fast EMA Length")
slowLength = input.int(26, "Slow EMA Length")
signalLength = input.int(9, "Signal Smoothing")
history = input.int(20, "History for momentum")

// Calculate MACD
[macdLine, signalLine, histLine] = ta.macd(close, fastLength, slowLength, signalLength)

// Plot MACD
plot(macdLine, color=color.blue, title="MACD Line")
plot(signalLine, color=color.orange, title="Signal Line")

// MACD Histogram
histColor = histLine >= 0 ? (histLine > histLine[1] ? color.lime : color.green) : (histLine < histLine[1] ? color.red : color.maroon)
plot(histLine, color=histColor, style=plot.style_histogram, title="Histogram")

// Momentum confirmation
momentumPositive = ta.change(macdLine) > 0
momentumNegative = ta.change(macdLine) < 0

// Signals
bullCross = ta.crossover(macdLine, signalLine)
bearCross = ta.crossunder(macdLine, signalLine)

// Confirm with momentum
confirmedLong = bullCross and momentumPositive
confirmedShort = bearCross and momentumNegative

plotshape(confirmedLong, title="Confirmed Long", location=location.belowbar, color=color.green, style=shape.triangleup, size=size.small, text="BUY")
plotshape(confirmedShort, title="Confirmed Short", location=location.abovebar, color=color.red, style=shape.triangledown, size=size.small, text="SELL")

// Alerts
alertcondition(confirmedLong, title="Confirmed Long", message="MACD Bull Cross - BUY Signal")
alertcondition(confirmedShort, title="Confirmed Short", message="MACD Bear Cross - SELL Signal")

// Strategy execution
if (confirmedLong)
    strategy.entry(id="Long", direction=strategy.long)
if (confirmedShort)
    strategy.close(id="Long")
`,
  "grid_trading": `//@version=5
strategy("Grid Trading", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=10)

// Input parameters
gridLevels = input.int(5, "Grid Levels")
gridSpacing = input.float(0.5, "Grid Spacing (%)")

// Calculate grid lines
basePrice = close
gridStep = basePrice * (gridSpacing / 100)

// Upper and lower grid bounds
upperBound = basePrice * (1 + gridSpacing * gridLevels / 100)
lowerBound = basePrice * (1 - gridSpacing * gridLevels / 100)

// Generate grid levels
var float[] gridPrices = array.new_float()

if bar_index == 0
    for i = 0 to gridLevels
        array.push(gridPrices, lowerBound + gridStep * i)

// Plot grid levels (dashed lines)
for i = 0 to gridLevels
    levelPrice = array.get(gridPrices, i)
    plot(levelPrice, color=color.gray, linestyle=line.style_dashed, title="Grid Level " + str.tostring(i))

// Grid entry signals
priceCrossAbove = ta.crossover(close, basePrice + gridStep)
priceCrossBelow = ta.crossunder(close, basePrice - gridStep)

// Entry at grid levels
for i = 1 to gridLevels
    levelPrice = array.get(gridPrices, i)
    if ta.crossover(close, levelPrice)
        label.new(bar_index, close, "BUY @" + str.tostring(levelPrice), color=color.green)
    if ta.crossunder(close, levelPrice)
        label.new(bar_index, close, "SELL @" + str.tostring(levelPrice), color=color.red)

// Alert conditions
alertcondition(priceCrossAbove, title="Price Above Grid", message="Price crossed above grid level")
alertcondition(priceCrossBelow, title="Price Below Grid", message="Price crossed below grid level")

// Grid strategy (simplified for demonstration)
if priceCrossAbove
    strategy.entry(id="GridBuy", direction=strategy.long)
if priceCrossBelow
    strategy.close(id="GridBuy")
`,
  "donchian_breakout": `//@version=5
strategy("Donchian Breakout", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=10)

// Input parameters
donchianLength = input.int(20, "Donchian Channel Length")
breakoutThreshold = input.float(0.1, "Breakout Threshold (%)")

// Calculate Donchian Channel
upper = ta.highest(high, donchianLength)
lower = ta.lowest(low, donchianLength)
middle = (upper + lower) / 2

// Plot channel
plot(upper, color=color.red, title="Upper Channel")
plot(lower, color=color.green, title="Lower Channel")
plot(middle, color=color.blue, title="Middle Line", linestyle=line.style_dashed)

// Calculate breakout threshold
breakoutLevel = ta.highest(high, donchianLength) * (1 + breakoutThreshold / 100)

// Breakout signals
breakoutAbove = ta.crossover(close, upper[1])
breakoutBelow = ta.crossunder(close, lower[1])

// Plot signals on chart
plotshape(breakoutAbove, title="Breakout Above", location=location.belowbar, color=color.green, style=shape.triangleup, size=size.small, text="BUY")
plotshape(breakoutBelow, title="Breakout Below", location=location.abovebar, color=color.red, style=shape.triangledown, size=size.small, text="SELL")

// Alert conditions
alertcondition(breakoutAbove, title="Breakout Above", message="Price broke above Donchian Channel - BUY Signal")
alertcondition(breakoutBelow, title="Breakout Below", message="Price broke below Donchian Channel - SELL Signal")

// Strategy execution
if (breakoutAbove)
    strategy.entry(id="Long", direction=strategy.long)
if (breakoutBelow)
    strategy.close(id="Long")
`,
  "moon_phase": `//@version=5
strategy("Moon Phase Strategy", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=10)

//moonphase library is not built-in; we use a simplified approximation
//https://www.tradingview.com/script/QHPXJX4U-Moon-Phases/
moonphase = request.security("MCEP", "D", close)

// Input parameters
moonThreshold = input.float(0.5, "Moon Phase Threshold")

// Define moon phases (simplified lunar cycle approximation)
// This is a placeholder - real implementation would use moonphase library

// Plot moon phase indicator
plotseries(moonphase, na, color.orange, plot.styleHistogram, 2)

// Trading signals based on moon phase
// Phase > 0.7 = Full Moon = Buy, Phase < 0.3 = New Moon = Sell
moonBuy = moonphase > (1 - moonThreshold) and moonphase[1] <= (1 - moonThreshold)
moonSell = moonphase < moonThreshold and moonphase[1] >= moonThreshold

plotshape(moonBuy, title="Moon Buy", location=location.belowbar, color=color.green, style=shape.triangleup, size=size.small, text="MOON BUY")
plotshape(moonSell, title="Moon Sell", location=location.abovebar, color=color.red, style=shape.triangledown, size=size.small, text="MOON SELL")

// Alerts
alertcondition(moonBuy, title="Full Moon Buy", message="Full Moon phase detected - BUY signal")
alertcondition(moonSell, title="New Moon Sell", message="New Moon phase detected - SELL signal")

// Strategy execution
if moonBuy
    strategy.entry(id="MoonLong", direction=strategy.long)
if moonSell
    strategy.close(id="MoonLong")
`,
};

const STRATEGY_ICONS: Record<StrategyType, string> = {
  "ma_crossover": "📈",
  "bollinger_rsi": "📊",
  "macd_momentum": "⚡",
  "grid_trading": "🔲",
  "donchian_breakout": "🎯",
  "moon_phase": "🌙",
};

export default function ExportPage() {
  const [selectedType, setSelectedType] = React.useState<StrategyType>("ma_crossover");
  const [template, setTemplate] = React.useState<TemplateResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [copied, setCopied] = React.useState(false);
  const [dropdownOpen, setDropdownOpen] = React.useState(false);

  const selectedTypeInfo = STRATEGY_TYPES.find((t) => t.value === selectedType);
  const scriptContent = template?.script || FALLBACK_SCRIPTS[selectedType];

  const fetchTemplate = React.useCallback(async (type: StrategyType) => {
    setLoading(true);
    try {
      const res = await authFetch(`/api/v1/export/pine-script/template/${type}`);
      if (res.ok) {
        const data: TemplateResponse = await res.json();
        setTemplate(data);
      } else {
        // Use fallback if API doesn't exist
        setTemplate({
          type,
          name: STRATEGY_TYPES.find((t) => t.value === type)?.label || type,
          description: STRATEGY_TYPES.find((t) => t.value === type)?.description || "",
          script: FALLBACK_SCRIPTS[type],
          version: "5",
        });
      }
    } catch {
      setTemplate({
        type,
        name: STRATEGY_TYPES.find((t) => t.value === type)?.label || type,
        description: STRATEGY_TYPES.find((t) => t.value === type)?.description || "",
        script: FALLBACK_SCRIPTS[type],
        version: "5",
      });
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch on selection change
  React.useEffect(() => {
    fetchTemplate(selectedType);
  }, [selectedType, fetchTemplate]);

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Export Strategies</h1>
          <p className="text-text-secondary">
            Export your strategies as Pine Script v5 for TradingView
          </p>
        </div>
      </div>

      {/* Strategy Type Selector */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Code className="h-5 w-5 text-primary" />
            Select Strategy Type
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative">
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="w-full flex items-center justify-between rounded-lg border border-border bg-card px-4 py-3 text-left hover:border-primary/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="text-xl">{STRATEGY_ICONS[selectedType]}</span>
                <div>
                  <p className="text-sm font-medium text-text-primary">
                    {selectedTypeInfo?.label}
                  </p>
                  <p className="text-xs text-text-muted">{selectedTypeInfo?.description}</p>
                </div>
              </div>
              <ChevronDown
                className={`h-4 w-4 text-text-muted transition-transform ${
                  dropdownOpen ? "rotate-180" : ""
                }`}
              />
            </button>

            {dropdownOpen && (
              <div className="absolute z-10 mt-2 w-full rounded-lg border border-border bg-card shadow-xl">
                {STRATEGY_TYPES.map((type) => (
                  <button
                    key={type.value}
                    onClick={() => {
                      setSelectedType(type.value);
                      setDropdownOpen(false);
                    }}
                    className={`w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-accent/10 transition-colors ${
                      selectedType === type.value ? "bg-primary/10" : ""
                    }`}
                  >
                    <span className="text-xl">{STRATEGY_ICONS[type.value]}</span>
                    <div className="flex-1">
                      <p
                        className={`text-sm font-medium ${
                          selectedType === type.value
                            ? "text-primary"
                            : "text-text-primary"
                        }`}
                      >
                        {type.label}
                      </p>
                      <p className="text-xs text-text-muted">{type.description}</p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Generated Script */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Code className="h-5 w-5 text-primary" />
              Pine Script v5 — {selectedTypeInfo?.label || selectedType}
            </CardTitle>
            <div className="flex gap-2">
              <Badge variant="info">v5</Badge>
 {loading && (
                <Badge variant="warning">
                  <RefreshCw className="h-3 w-3 animate-spin mr-1" />
                  Loading...
                </Badge>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {template?.description && (
            <p className="text-sm text-text-secondary">{template.description}</p>
          )}

          {/* Script Preview */}
          <div className="bg-[#1e1e2e] rounded-lg border border-border overflow-hidden">
            <div className="bg-[#2a2a3e] px-4 py-2 border-b border-border flex items-center justify-between">
              <span className="text-xs text-text-muted font-mono">Pine Script</span>
              <span className="text-xs text-text-muted">
                {scriptContent.split("\n").length} lines
              </span>
            </div>
            <div className="flex justify-end p-2 border-b border-border">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => copyToClipboard(scriptContent)}
                className="flex items-center gap-1.5 text-xs"
              >
                {copied ? (
                  <Check className="h-3 w-3 text-emerald-400" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
                {copied ? "Copied!" : "Copy to Clipboard"}
              </Button>
            </div>
            <pre className="p-4 text-xs font-mono text-text-secondary overflow-x-auto max-h-96 overflow-y-auto">
              {scriptContent}
            </pre>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-3">
            <Button
              onClick={() => copyToClipboard(scriptContent)}
              className="flex items-center gap-2"
            >
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              {copied ? "Copied!" : "Copy Pine Script"}
            </Button>
            <Button
              variant="outline"
              onClick={() => fetchTemplate(selectedType)}
              disabled={loading}
              className="flex items-center gap-2"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              Regenerate
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Webhook Integration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Webhook className="h-5 w-5 text-primary" />
            Webhook Integration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-text-secondary">
            Connect this strategy to TradingView alerts using webhook. Copy the webhook URL
            below and set it in your TradingView alert settings.
          </p>

          <div className="bg-[#1e1e2e] rounded-lg p-4">
            <label className="text-sm font-medium text-text-primary block mb-2">
              Webhook URL
            </label>
            <div className="flex gap-2">
              <Input
                value={`https://api.example.com/webhook/strategy/${selectedType}`}
                readOnly
                className="flex-1 font-mono text-xs"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  copyToClipboard(
                    `https://api.example.com/webhook/strategy/${selectedType}`
                  )
                }
                className="flex items-center gap-1 shrink-0"
              >
                <Copy className="h-3 w-3" />
                Copy
              </Button>
            </div>
          </div>

          <div className="flex items-start gap-2 text-xs text-text-muted">
            <Info className="h-3 w-3 mt-0.5 shrink-0" />
            <span>
              The webhook will send JSON signals whenalert conditions are met. Configure
              this URL in your TradingView alert's webhook settings.
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Quick Reference */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Signal Payload Format</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="bg-[#1e1e2e] rounded-lg p-4 overflow-x-auto" suppressHydrationWarning>
            <pre className="font-mono text-xs text-text-secondary whitespace-pre-wrap" suppressHydrationWarning>
{`{
  "strategy_id": "${selectedType}",
  "strategy_name": "${selectedTypeInfo?.label || selectedType}",
  "timestamp": "${new Date().toISOString()}",
  "action": "buy" | "sell" | "close",
  "price": 67500.00,
  "confidence": 0.85,
  "metadata": {
    "timeframe": "1h",
    "pair": "BTCUSDT"
  }
}`}
            </pre>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
