"use client";

import { useState, useCallback } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  Copy,
  Check,
  ExternalLink,
  AlertCircle,
  Webhook,
  Code,
  ChevronRight,
  X,
  Info,
} from "lucide-react";

interface TradingViewExportProps {
  strategyId: string;
  strategyName: string;
  pair?: string;
  condition?: string;
  generatedScript?: string;
  webhookUrl?: string;
}

export default function TradingViewExport({
  strategyId,
  strategyName,
  pair = "BTCUSDT",
  condition = "Cross above EMA 20",
  generatedScript = SAMPLE_PINE_SCRIPT,
  webhookUrl: initialWebhookUrl,
}: TradingViewExportProps) {
  const [copied, setCopied] = useState(false);
  const [showAlertGuide, setShowAlertGuide] = useState(false);
  const [webhookUrl, setWebhookUrl] = useState(initialWebhookUrl || "");
  const [showWebhookModal, setShowWebhookModal] = useState(false);
  const [loadingWebhook, setLoadingWebhook] = useState(false);

  // Copy to clipboard handler
  const copyToClipboard = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      // Fallback for older browsers
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
  }, []);

  // Generate webhook URL
  const generateWebhookUrl = useCallback(async () => {
    setLoadingWebhook(true);
    try {
      const response = await fetch(`/api/v1/export/tradingview/webhook-url/${strategyId}`);
      if (response.ok) {
        const data = await response.json();
        setWebhookUrl(data.webhook_url);
      } else {
        // Use a placeholder URL if API doesn't exist yet
        setWebhookUrl(`https://api.example.com/webhook/tradingview/${strategyId}`);
      }
    } catch (err) {
      // Fallback URL
      setWebhookUrl(`https://api.example.com/webhook/tradingview/${strategyId}`);
    } finally {
      setLoadingWebhook(false);
    }
  }, [strategyId]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-primary/10 rounded-lg">
          <Webhook className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-text-primary">TradingView Export</h3>
          <p className="text-sm text-text-muted">Export {strategyName} to TradingView</p>
        </div>
      </div>

      {/* Copy Pine Script Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-sm font-medium text-text-primary flex items-center gap-2">
            <Code size={16} className="text-text-muted" />
            Pine Script v5
          </label>
          <Button
            variant="outline"
            size="sm"
            onClick={() => copyToClipboard(generatedScript)}
            className="flex items-center gap-2"
          >
            {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
            {copied ? "Copied!" : "Copy Script"}
          </Button>
        </div>

        {/* Script Preview */}
        <div className="bg-[#1e1e2e] rounded-lg border border-border overflow-hidden">
          <div className="bg-[#2a2a3e] px-4 py-2 border-b border-border flex items-center justify-between">
            <span className="text-xs text-text-muted font-mono">Pine Script</span>
            <span className="text-xs text-text-muted">{generatedScript.split('\n').length} lines</span>
          </div>
          <pre className="p-4 text-xs font-mono text-text-secondary overflow-x-auto max-h-64 overflow-y-auto">
            {generatedScript}
          </pre>
        </div>
      </div>

      {/* Webhook URL Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-sm font-medium text-text-primary flex items-center gap-2">
            <Webhook size={16} className="text-text-muted" />
            Webhook URL
          </label>
          <Button
            variant="outline"
            size="sm"
            onClick={() => copyToClipboard(webhookUrl)}
            disabled={!webhookUrl}
            className="flex items-center gap-2"
          >
            <Copy size={14} />
            Copy URL
          </Button>
        </div>

        <div className="flex gap-2">
          <Input
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
            placeholder="Generate or enter webhook URL..."
            className="flex-1 font-mono text-xs"
            readOnly={false}
          />
          <Button
            variant="outline"
            size="md"
            onClick={generateWebhookUrl}
            disabled={loadingWebhook}
            className="shrink-0"
          >
            {loadingWebhook ? "Generating..." : "Generate"}
          </Button>
        </div>

        {webhookUrl && (
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <Info size={12} />
            <span>Use this URL in TradingView alert webhook settings</span>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3 pt-2">
        <Button
          variant="default"
          size="md"
          onClick={() => copyToClipboard(generatedScript)}
          className="flex items-center gap-2"
        >
          <Copy size={16} />
          Copy Pine Script
        </Button>
        <Button
          variant="outline"
          size="md"
          onClick={() => setShowAlertGuide(true)}
          className="flex items-center gap-2"
        >
          <AlertCircle size={16} />
          Alert Setup Guide
        </Button>
        <Button
          variant="ghost"
          size="md"
          onClick={() => setShowWebhookModal(true)}
          className="flex items-center gap-2"
        >
          <ExternalLink size={16} />
          View Signal Format
        </Button>
      </div>

      {/* Alert Setup Guide Modal */}
      {showAlertGuide && (
        <AlertSetupModal
          onClose={() => setShowAlertGuide(false)}
          condition={condition}
          pair={pair}
          webhookUrl={webhookUrl}
          onCopyScript={() => copyToClipboard(generatedScript)}
        />
      )}

      {/* Signal Format Modal */}
      {showWebhookModal && (
        <SignalFormatModal
          onClose={() => setShowWebhookModal(false)}
          webhookUrl={webhookUrl}
          strategyId={strategyId}
          pair={pair}
        />
      )}
    </div>
  );
}

// ─── Alert Setup Modal ─────────────────────────────────────────────────────────

interface AlertSetupModalProps {
  onClose: () => void;
  condition: string;
  pair: string;
  webhookUrl: string;
  onCopyScript: () => void;
}

function AlertSetupModal({ onClose, condition, pair, webhookUrl, onCopyScript }: AlertSetupModalProps) {
  const [copiedStep, setCopiedStep] = useState<number | null>(null);

  const steps = [
    {
      title: "Open TradingView Chart",
      description: "Navigate to the chart for the trading pair you want to monitor.",
    },
    {
      title: "Apply Pine Script",
      description: "Copy the Pine Script and add it to your chart via Pine Editor.",
    },
    {
      title: "Create Alert",
      description: "Right-click on the chart → Add Alert, or use the Alert button in the toolbar.",
    },
    {
      title: "Configure Alert Condition",
      description: (
        <div className="space-y-2">
          <p className="text-text-primary">Set the alert condition to:</p>
          <div className="bg-[#1e1e2e] rounded-lg p-3 font-mono text-sm">
            <span className="text-emerald-400">{pair}</span>{" "}
            <span className="text-text-secondary">{condition}</span>
          </div>
          <button
            onClick={() => {
              navigator.clipboard.writeText(`${pair} ${condition}`);
              setCopiedStep(4);
              setTimeout(() => setCopiedStep(null), 2000);
            }}
            className="text-xs text-primary hover:text-primary/80 flex items-center gap-1"
          >
            {copiedStep === 4 ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
            Copy condition text
          </button>
        </div>
      ),
    },
    {
      title: "Enable Webhook",
      description: (
        <div className="space-y-2">
          <p className="text-text-primary">In the alert settings, find the "Webhook URL" option and enable it.</p>
          {webhookUrl ? (
            <div className="bg-[#1e1e2e] rounded-lg p-3 font-mono text-xs break-all">
              <span className="text-text-muted">URL:</span> <span className="text-primary">{webhookUrl}</span>
            </div>
          ) : (
            <p className="text-xs text-amber-400">Generate a webhook URL first using the button above.</p>
          )}
        </div>
      ),
    },
    {
      title: "Set Expiration",
      description: "Set the alert to expire after a reasonable time or to repeat as needed.",
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-[#1a1a2e] rounded-xl border border-border w-full max-w-lg mx-4 max-h-[85vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/10 rounded-lg">
              <AlertCircle className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-text-primary">TradingView Alert Setup</h3>
              <p className="text-sm text-text-muted">Step-by-step guide</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-card rounded-lg transition-colors text-text-muted hover:text-text-primary"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {steps.map((step, index) => (
            <div key={index} className="flex gap-4">
              <div className="flex flex-col items-center">
                <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-sm font-semibold text-primary shrink-0">
                  {index + 1}
                </div>
                {index < steps.length - 1 && (
                  <div className="w-0.5 h-full bg-border mt-2" />
                )}
              </div>
              <div className="pb-6">
                <h4 className="text-sm font-medium text-text-primary mb-1">{step.title}</h4>
                {typeof step.description === "string" ? (
                  <p className="text-sm text-text-muted">{step.description}</p>
                ) : (
                  step.description
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-border flex justify-end gap-3">
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
          <Button variant="default" size="sm" onClick={onCopyScript} className="flex items-center gap-2">
            <Copy size={14} />
            Copy Pine Script
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Signal Format Modal ───────────────────────────────────────────────────────

interface SignalFormatModalProps {
  onClose: () => void;
  webhookUrl: string;
  strategyId: string;
  pair: string;
}

function SignalFormatModal({ onClose, webhookUrl, strategyId, pair }: SignalFormatModalProps) {
  const sampleSignal = {
    strategy_id: strategyId,
    pair: pair,
    action: "buy",
    price: 67500.0,
    timestamp: new Date().toISOString(),
  };

  const [copied, setCopied] = useState(false);

  const copySignal = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(sampleSignal, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      // Fallback
      const textarea = document.createElement("textarea");
      textarea.value = JSON.stringify(sampleSignal, null, 2);
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-[#1a1a2e] rounded-xl border border-border w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <Webhook className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-text-primary">Webhook Signal Format</h3>
              <p className="text-sm text-text-muted">JSON payload structure</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-card rounded-lg transition-colors text-text-muted hover:text-text-primary"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Webhook URL */}
          <div>
            <label className="text-xs font-medium text-text-muted uppercase tracking-wide">Webhook URL</label>
            <div className="mt-1 bg-[#1e1e2e] rounded-lg p-3 font-mono text-xs break-all text-text-secondary">
              {webhookUrl || "Not generated yet"}
            </div>
          </div>

          {/* Signal Format */}
          <div>
            <label className="text-xs font-medium text-text-muted uppercase tracking-wide flex items-center justify-between">
              Signal Payload
              <button
                onClick={copySignal}
                className="text-primary hover:text-primary/80 flex items-center gap-1 uppercase tracking-normal font-normal"
              >
                {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                {copied ? "Copied!" : "Copy"}
              </button>
            </label>
            <div className="mt-1 bg-[#1e1e2e] rounded-lg p-4 overflow-x-auto">
              <pre className="font-mono text-xs text-text-secondary whitespace-pre-wrap">
                {JSON.stringify(sampleSignal, null, 2)}
              </pre>
            </div>
          </div>

          {/* Field Descriptions */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wide">Field Reference</label>
            <div className="space-y-2 text-xs">
              <div className="flex gap-2 items-start">
                <span className="text-primary font-mono min-w-[80px]">strategy_id</span>
                <span className="text-text-muted">Unique identifier for your strategy</span>
              </div>
              <div className="flex gap-2 items-start">
                <span className="text-primary font-mono min-w-[80px]">pair</span>
                <span className="text-text-muted">Trading pair symbol (e.g., BTCUSDT)</span>
              </div>
              <div className="flex gap-2 items-start">
                <span className="text-primary font-mono min-w-[80px]">action</span>
                <span className="text-text-muted">Signal type: "buy" or "sell"</span>
              </div>
              <div className="flex gap-2 items-start">
                <span className="text-primary font-mono min-w-[80px]">price</span>
                <span className="text-text-muted">Current price at signal generation</span>
              </div>
              <div className="flex gap-2 items-start">
                <span className="text-primary font-mono min-w-[80px]">timestamp</span>
                <span className="text-text-muted">ISO 8601 timestamp of the signal</span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-border flex justify-end">
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Sample Pine Script ────────────────────────────────────────────────────────

const SAMPLE_PINE_SCRIPT = `//@version=5
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
alertcondition(bullCross, title="Bull Cross Alert", message="BTCUSDT Cross above EMA 20 - BUY Signal")
alertcondition(bearCross, title="Bear Cross Alert", message="BTCUSDT Cross below EMA 20 - SELL Signal")

// Execute strategy (for backtesting)
if (bullCross)
    strategy.entry(id="Long", direction=strategy.long)

if (bearCross)
    strategy.close(id="Long")
`;