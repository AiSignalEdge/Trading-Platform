"""
Export Routes - Data export endpoints including Pine Script v5 export.

Section 13: API Server from PLAN-v2.md
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db

router = APIRouter(prefix="/api/v1/export", tags=["export"])


# ====================
# Pine Script Templates
# ====================

PINE_SCRIPT_TEMPLATES = {
    "ma_crossover": '''//@version=5
strategy("{{STRATEGY_NAME}} - MA Crossover", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=10)

// ─── Inputs ───────────────────────────────────────────────────────────────────
sourceInput = input.source({{SOURCE}},"Price Source")
fastLength = input.int({{FAST_MA_PERIOD}}, "Fast MA Length", minval=1)
slowLength = input.int({{SLOW_MA_PERIOD}}, "Slow MA Length", minval=1)
maType = input.string("SMA", "MA Type", options=["SMA","EMA","RMA","WMA","VWMA"])
stopLossPct = input.float({{STOP_LOSS_PCT}} * 100, "Stop Loss %", minval=0.1, maxval=50, step=0.1) / 100
takeProfitPct = input.float({{TAKE_PROFIT_PCT}} * 100, "Take Profit %", minval=0.1, maxval=100, step=0.1) / 100
useMultiTimeframe = input.bool({{USE_MULTI_TIMEFRAME}}, "Use Multi-Timeframe")
higherTimeframe = input.timeframe("{{HIGHER_TIMEFRAME}}", "Higher Timeframe")

// ─── MA Calculation ───────────────────────────────────────────────────────────
ma(source, length, type) =>
    switch type
        "SMA" => ta.sma(source, length)
        "EMA" => ta.ema(source, length)
        "RMA" => ta.rma(source, length)
        "WMA" => ta.wma(source, length)
        "VWMA" => ta.vwma(source, length)

// ─── Multi-Timeframe Analysis ─────────────────────────────────────────────────
[fasterMA, slowerMA] = useMultiTimeframe ? request.security(syminfo.tickerid, higherTimeframe, [ma(sourceInput, fastLength, maType), ma(sourceInput, slowLength, maType)]) : [na, na]
[fasterMACurrent, slowerMACurrent] = [ma(sourceInput, fastLength, maType), ma(sourceInput, slowLength, maType)]

fastMA = useMultiTimeframe ? fasterMA : fasterMACurrent
slowMA = useMultiTimeframe ? slowerMA : slowerMACurrent

// ─── Entry Signals ────────────────────────────────────────────────────────────
bullishCross = ta.crossover(fastMA, slowMA)
bearishCross = ta.crossunder(fastMA, slowMA)

// ─── Risk Management ─────────────────────────────────────────────────────────
longStopPrice = close * (1 - stopLossPct)
shortStopPrice = close * (1 + stopLossPct)
longTakePrice = close * (1 + takeProfitPct)
shortTakePrice = close * (1 - takeProfitPct)

// ─── Strategy Entries ─────────────────────────────────────────────────────────
if bullishCross
    strategy.entry("Long", strategy.long)
    strategy.exit("Long Exit", "Long", stop=longStopPrice, limit=longTakePrice)

if bearishCross
    strategy.entry("Short", strategy.short)
    strategy.exit("Short Exit", "Short", stop=shortStopPrice, limit=shortTakePrice)

// ─── Visual Plots ──────────────────────────────────────────────────────────────
plot(fastMA, "Fast MA", color=color.new(color.blue, 0), linewidth=2)
plot(slowMA, "Slow MA", color=color.new(color.red, 0), linewidth=2)

// Plot entry markers
plotshape(bullishCross, title="Golden Cross", location=location.belowbar, style=shape.triangleup, color=color.lime, size=size.small, text="LONG")
plotshape(bearishCross, title="Death Cross", location=location.abovebar, style=shape.triangledown, color=color.red, size=size.small, text="SHORT")

// ─── Dashboard Table ──────────────────────────────────────────────────────────
var table dashboard = table.new(position.top_right, 2, 2, bgcolor=color.new(color.black, 80))
if barstate.date != na
    table.cell(dashboard, 0, 0, "Entry Price", text_color=color.white)
    table.cell(dashboard, 1, 0, str.tostring({{ENTRY_PRICE}}, format.mintick), text_color=color.lime)
    table.cell(dashboard, 0, 1, "PnL %", text_color=color.white)
    table.cell(dashboard, 1, 1, str.tostring(strategy.openprofit / strategy.equity * 100, "#.##") + "%", text_color=color.lime)
''',

    "bollinger_rsi": '''//@version=5
strategy("{{STRATEGY_NAME}} - Bollinger + RSI", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=10)

// ─── Inputs ───────────────────────────────────────────────────────────────────
bbLength = input.int({{BB_PERIOD}}, "Bollinger Length", minval=1)
bbMult = input.float({{BB_STD_DEV}}, "Bollinger Std Dev", minval=0.1, step=0.1)
rsiLength = input.int({{RSI_PERIOD}}, "RSI Length", minval=1)
rsiSource = input.source({{RSI_SOURCE}}, "RSI Source")
rsiOverbought = input.float({{RSI_OVERBOUGHT}}, "RSI Overbought", minval=50, maxval=100)
rsiOversold = input.float({{RSI_OVERSOLD}}, "RSI Oversold", minval=0, maxval=50)
stopLossPct = input.float({{STOP_LOSS_PCT}} * 100, "Stop Loss %", minval=0.1, maxval=50, step=0.1) / 100
takeProfitPct = input.float({{TAKE_PROFIT_PCT}} * 100, "Take Profit %", minval=0.1, maxval=100, step=0.1) / 100
useMultiTimeframe = input.bool({{USE_MULTI_TIMEFRAME}}, "Use Multi-Timeframe")
higherTimeframe = input.timeframe("{{HIGHER_TIMEFRAME}}", "Higher Timeframe")

// ─── Indicators ──────────────────────────────────────────────────────────────
[bbUpper, bbMiddle, bbLower] = ta.bb(rsiSource, bbLength, bbMult)
rsiValue = ta.rsi(rsiSource, rsiLength)

// Multi-timeframe RSI
rsiHTF = useMultiTimeframe ? request.security(syminfo.tickerid, higherTimeframe, ta.rsi(rsiSource, rsiLength)) : na
rsiCurrent = useMultiTimeframe ? rsiValue : rsiValue

// ─── Entry Signals ────────────────────────────────────────────────────────────
longCondition = ta.crossover(rsiValue, rsiOversold) and rsiValue < rsiOverbought and close < bbUpper
shortCondition = ta.crossunder(rsiValue, rsiOverbought) and rsiValue > rsiOversold and close > bbLower

// ─── Risk Management ─────────────────────────────────────────────────────────
longStopPrice = close * (1 - stopLossPct)
shortStopPrice = close * (1 + stopLossPct)
longTakePrice = close * (1 + takeProfitPct)
shortTakePrice = close * (1 - takeProfitPct)

// ─── Strategy Entries ─────────────────────────────────────────────────────────
if longCondition
    strategy.entry("Long", strategy.long)
    strategy.exit("Long Exit", "Long", stop=longStopPrice, limit=longTakePrice)

if shortCondition
    strategy.entry("Short", strategy.short)
    strategy.exit("Short Exit", "Short", stop=shortStopPrice, limit=shortTakePrice)

// ─── Visual Plots ──────────────────────────────────────────────────────────────
plot(bbUpper, "BB Upper", color=color.red, linewidth=1)
plot(bbMiddle, "BB Middle", color=color.orange, linewidth=1)
plot(bbLower, "BB Lower", color=color.green, linewidth=1)
plot(rsiValue, "RSI", color=color.purple, linewidth=2)
hline(rsiOverbought, "Overbought", color=color.red, linestyle=hline.style_dashed)
hline(rsiOversold, "Oversold", color=color.green, linestyle=hline.style_dashed)

// Entry markers
plotshape(longCondition, title="RSI Oversold Bounce", location=location.belowbar, style=shape.triangleup, color=color.lime, size=size.small, text="LONG")
plotshape(shortCondition, title="RSI Overbought Drop", location=location.abovebar, style=shape.triangledown, color=color.red, size=size.small, text="SHORT")

// ─── Dashboard Table ──────────────────────────────────────────────────────────
var table dashboard = table.new(position.top_right, 2, 3, bgcolor=color.new(color.black, 80))
if barstate.date != na
    table.cell(dashboard, 0, 0, "RSI", text_color=color.white)
    table.cell(dashboard, 1, 0, str.tostring(rsiValue, "#.#"), text_color=color.yellow)
    table.cell(dashboard, 0, 1, "BB Position", text_color=color.white)
    table.cell(dashboard, 1, 1, (close > bbUpper ? "Above" : close < bbLower ? "Below" : "Inside"), text_color=color.white)
    table.cell(dashboard, 0, 2, "PnL %", text_color=color.white)
    table.cell(dashboard, 1, 2, str.tostring(strategy.openprofit / strategy.equity * 100, "#.##") + "%", text_color=color.lime)
''',

    "macd_momentum": '''//@version=5
strategy("{{STRATEGY_NAME}} - MACD Momentum", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=10)

// ─── Inputs ───────────────────────────────────────────────────────────────────
macdFast = input.int({{MACD_FAST}}, "MACD Fast Length", minval=2, maxval=200)
macdSlow = input.int({{MACD_SLOW}}, "MACD Slow Length", minval=2, maxval=200)
macdSignal = input.int({{MACD_SIGNAL}}, "Signal Length", minval=2, maxval=200)
sourceInput = input.source({{SOURCE}}, "Price Source")
stopLossPct = input.float({{STOP_LOSS_PCT}} * 100, "Stop Loss %", minval=0.1, maxval=50, step=0.1) / 100
takeProfitPct = input.float({{TAKE_PROFIT_PCT}} * 100, "Take Profit %", minval=0.1, maxval=100, step=0.1) / 100
useMultiTimeframe = input.bool({{USE_MULTI_TIMEFRAME}}, "Use Multi-Timeframe")
higherTimeframe = input.timeframe("{{HIGHER_TIMEFRAME}}", "Higher Timeframe")

// ─── MACD Calculation ──────────────────────────────────────────────────────────
[macdLine, signalLine, histLine] = ta.macd(sourceInput, macdFast, macdSlow, macdSignal)

// Multi-timeframe MACD
[macdHTF, signalHTF] = useMultiTimeframe ? request.security(syminfo.tickerid, higherTimeframe, [macdLine, signalLine]) : [na, na]
macd = useMultiTimeframe ? macdHTF : macdLine
signal = useMultiTimeframe ? signalHTF : signalLine

// ─── Momentum Signals ─────────────────────────────────────────────────────────
bullishMACD = ta.crossover(macd, signal)
bearishMACD = ta.crossunder(macd, signal)

// Strong momentum: histogram expanding
histogramGrowing = histLine > histLine[1] and histLine > 0
histogramFalling = histLine < histLine[1] and histLine < 0

// ─── Risk Management ─────────────────────────────────────────────────────────
longStopPrice = close * (1 - stopLossPct)
shortStopPrice = close * (1 + stopLossPct)
longTakePrice = close * (1 + takeProfitPct)
shortTakePrice = close * (1 - takeProfitPct)

// ─── Strategy Entries ─────────────────────────────────────────────────────────
if bullishMACD and (histogramGrowing or histLine > 0)
    strategy.entry("Long", strategy.long)
    strategy.exit("Long Exit", "Long", stop=longStopPrice, limit=longTakePrice)

if bearishMACD and (histogramFalling or histLine < 0)
    strategy.entry("Short", strategy.short)
    strategy.exit("Short Exit", "Short", stop=shortStopPrice, limit=shortTakePrice)

// ─── Visual Plots ──────────────────────────────────────────────────────────────
plot(macd, "MACD", color=color.blue, linewidth=2)
plot(signal, "Signal", color=color.orange, linewidth=2)
plot(histLine, "Histogram", color=color.maroon, style=plot.style_histogram)

// Entry markers
plotshape(bullishMACD, title="MACD Bullish Cross", location=location.belowbar, style=shape.triangleup, color=color.lime, size=size.small, text="LONG")
plotshape(bearishMACD, title="MACD Bearish Cross", location=location.abovebar, style=shape.triangledown, color=color.red, size=size.small, text="SHORT")

// ─── Dashboard Table ──────────────────────────────────────────────────────────
var table dashboard = table.new(position.top_right, 2, 3, bgcolor=color.new(color.black, 80))
if barstate.date != na
    table.cell(dashboard, 0, 0, "MACD", text_color=color.white)
    table.cell(dashboard, 1, 0, str.tostring(macd, "#.####"), text_color=color.blue)
    table.cell(dashboard, 0, 1, "Signal", text_color=color.white)
    table.cell(dashboard, 1, 1, str.tostring(signal, "#.####"), text_color=color.orange)
    table.cell(dashboard, 0, 2, "PnL %", text_color=color.white)
    table.cell(dashboard, 1, 2, str.tostring(strategy.openprofit / strategy.equity * 100, "#.##") + "%", text_color=color.lime)
''',

    "supertrend": '''//@version=5
strategy("{{STRATEGY_NAME}} - Supertrend", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=10)

// ─── Inputs ───────────────────────────────────────────────────────────────────
atrPeriod = input.int({{ATR_PERIOD}}, "ATR Period", minval=1)
atrMultiplier = input.float({{ATR_MULTIPLIER}}, "ATR Multiplier", minval=0.1, step=0.1)
stopLossPct = input.float({{STOP_LOSS_PCT}} * 100, "Stop Loss %", minval=0.1, maxval=50, step=0.1) / 100
takeProfitPct = input.float({{TAKE_PROFIT_PCT}} * 100, "Take Profit %", minval=0.1, maxval=100, step=0.1) / 100
useMultiTimeframe = input.bool({{USE_MULTI_TIMEFRAME}}, "Use Multi-Timeframe")
higherTimeframe = input.timeframe("{{HIGHER_TIMEFRAME}}", "Higher Timeframe")

// ─── Supertrend Calculation ───────────────────────────────────────────────────
supertrend(atrPeriod, multiplier) =>
    atr = ta.atr(atrPeriod)
    upperBand = hl2 + multiplier * atr
    lowerBand = hl2 - multiplier * atr
    prevUpperBand = nz(upperBand[1])
    prevLowerBand = nz(lowerBand[1])
    
    upperBand := lowerBand := na
    upperBand := close[1] > prevUpperBand ? math.max(upperBand, prevUpperBand) : upperBand
    lowerBand := close[1] < prevLowerBand ? math.min(lowerBand, prevLowerBand) : lowerBand

    intDirection = na
    prevAtrTrend = nz(atrTrend[1], 1)
    atrTrend = na
    if na(upperBand) and na(lowerBand)
        intDirection := 1
    else
        intDirection := close > prevUpperBand ? 1 : close < prevLowerBand ? -1 : prevAtrTrend
    [upperBand, lowerBand, intDirection]

[stUpper, stLower, stDirection] = supertrend(atrPeriod, atrMultiplier)

// Multi-timeframe Supertrend
[intDirHTF] = useMultiTimeframe ? request.security(syminfo.tickerid, higherTimeframe, [stDirection]) : [na]
currentDirection = useMultiTimeframe ? intDirHTF : stDirection

// ─── Entry Signals ────────────────────────────────────────────────────────────
bullishSupertrend = ta.change(currentDirection) < 0
bearishSupertrend = ta.change(currentDirection) > 0

// ─── Risk Management ─────────────────────────────────────────────────────────
longStopPrice = close * (1 - stopLossPct)
shortStopPrice = close * (1 + stopLossPct)
longTakePrice = close * (1 + takeProfitPct)
shortTakePrice = close * (1 - takeProfitPct)

// ─── Strategy Entries ─────────────────────────────────────────────────────────
if bullishSupertrend
    strategy.entry("Long", strategy.long)
    strategy.exit("Long Exit", "Long", stop=longStopPrice, limit=longTakePrice)

if bearishSupertrend
    strategy.entry("Short", strategy.short)
    strategy.exit("Short Exit", "Short", stop=shortStopPrice, limit=shortTakePrice)

// ─── Visual Plots ──────────────────────────────────────────────────────────────
plot(currentDirection < 0 ? stUpper : na, "Supertrend Up", color=color.green, linewidth=2, style=plot.style_line)
plot(currentDirection > 0 ? stLower : na, "Supertrend Down", color=color.red, linewidth=2, style=plot.style_line)

// Entry markers
plotshape(bullishSupertrend, title="Supertrend Long", location=location.belowbar, style=shape.triangleup, color=color.lime, size=size.small, text="LONG")
plotshape(bearishSupertrend, title="Supertrend Short", location=location.abovebar, style=shape.triangledown, color=color.red, size=size.small, text="SHORT")

// ─── Dashboard Table ──────────────────────────────────────────────────────────
var table dashboard = table.new(position.top_right, 2, 2, bgcolor=color.new(color.black, 80))
if barstate.date != na
    table.cell(dashboard, 0, 0, "Direction", text_color=color.white)
    table.cell(dashboard, 1, 0, currentDirection < 0 ? "Long" : "Short", text_color=currentDirection < 0 ? color.lime : color.red)
    table.cell(dashboard, 0, 1, "PnL %", text_color=color.white)
    table.cell(dashboard, 1, 1, str.tostring(strategy.openprofit / strategy.equity * 100, "#.##") + "%", text_color=color.lime)
''',

    "donchian_breakout": '''//@version=5
strategy("{{STRATEGY_NAME}} - Donchian Breakout", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=10)

// ─── Inputs ───────────────────────────────────────────────────────────────────
donchianLength = input.int({{DONCHIAN_PERIOD}}, "Donchian Period", minval=1)
stopLossPct = input.float({{STOP_LOSS_PCT}} * 100, "Stop Loss %", minval=0.1, maxval=50, step=0.1) / 100
takeProfitPct = input.float({{TAKE_PROFIT_PCT}} * 100, "Take Profit %", minval=0.1, maxval=100, step=0.1) / 100
breakoutThreshold = input.float({{BREAKOUT_THRESHOLD}}, "Breakout Threshold %", minval=0, maxval=10, step=0.1) / 100
useMultiTimeframe = input.bool({{USE_MULTI_TIMEFRAME}}, "Use Multi-Timeframe")
higherTimeframe = input.timeframe("{{HIGHER_TIMEFRAME}}", "Higher Timeframe")

// ─── Donchian Channels ─────────────────────────────────────────────────────────
donchianUpper = ta.highest(high, donchianLength)
donchianLower = ta.lowest(low, donchianLength)
donchianMiddle = (donchianUpper + donchianLower) / 2

// Multi-timeframe Donchian
[dcUpperHTF, dcLowerHTF] = useMultiTimeframe ? request.security(syminfo.tickerid, higherTimeframe, [donchianUpper, donchianLower]) : [na, na]
dcUpper = useMultiTimeframe ? dcUpperHTF : donchianUpper
dcLower = useMultiTimeframe ? dcLowerHTF : donchianLower

// ─── Breakout Signals ─────────────────────────────────────────────────────────
upperBreakout = close > dcUpper * (1 + breakoutThreshold)
lowerBreakout = close < dcLower * (1 - breakoutThreshold)

// ─── Risk Management ─────────────────────────────────────────────────────────
longStopPrice = close * (1 - stopLossPct)
shortStopPrice = close * (1 + stopLossPct)
longTakePrice = close * (1 + takeProfitPct)
shortTakePrice = close * (1 - takeProfitPct)

// ─── Strategy Entries ─────────────────────────────────────────────────────────
if upperBreakout
    strategy.entry("Long", strategy.long)
    strategy.exit("Long Exit", "Long", stop=longStopPrice, limit=longTakePrice)

if lowerBreakout
    strategy.entry("Short", strategy.short)
    strategy.exit("Short Exit", "Short", stop=shortStopPrice, limit=shortTakePrice)

// ─── Visual Plots ──────────────────────────────────────────────────────────────
plot(dcUpper, "Donchian Upper", color=color.red, linewidth=1, style=plot.style_stepline)
plot(dcLower, "Donchian Lower", color=color.green, linewidth=1, style=plot.style_stepline)
plot(donchianMiddle, "Donchian Middle", color=color.gray, linewidth=1, style=plot.style_dotted)

// Entry markers
plotshape(upperBreakout, title="Upper Breakout", location=location.belowbar, style=shape.triangleup, color=color.lime, size=size.small, text="LONG")
plotshape(lowerBreakout, title="Lower Breakout", location=location.abovebar, style=shape.triangledown, color=color.red, size=size.small, text="SHORT")

// ─── Dashboard Table ──────────────────────────────────────────────────────────
var table dashboard = table.new(position.top_right, 2, 3, bgcolor=color.new(color.black, 80))
if barstate.date != na
    table.cell(dashboard, 0, 0, "Upper Band", text_color=color.white)
    table.cell(dashboard, 1, 0, str.tostring(dcUpper, format.mintick), text_color=color.red)
    table.cell(dashboard, 0, 1, "Lower Band", text_color=color.white)
    table.cell(dashboard, 1, 1, str.tostring(dcLower, format.mintick), text_color=color.green)
    table.cell(dashboard, 0, 2, "PnL %", text_color=color.white)
    table.cell(dashboard, 1, 2, str.tostring(strategy.openprofit / strategy.equity * 100, "#.##") + "%", text_color=color.lime)
''',

    "grid_trading": '''//@version=5
strategy("{{STRATEGY_NAME}} - Grid Trading", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=10)

// ─── Inputs ───────────────────────────────────────────────────────────────────
gridLevels = input.int({{GRID_LEVELS}}, "Grid Levels", minval=2, maxval=20)
gridSpacing = input.float({{GRID_SPACING_PCT}}, "Grid Spacing %", minval=0.1, maxval=10, step=0.1) / 100
basePrice = input.float({{BASE_PRICE}}, "Base Price", minval=0)
stopLossPct = input.float({{STOP_LOSS_PCT}} * 100, "Stop Loss %", minval=0.1, maxval=50, step=0.1) / 100
takeProfitPct = input.float({{TAKE_PROFIT_PCT}} * 100, "Take Profit %", minval=0.1, maxval=100, step=0.1) / 100
useMultiTimeframe = input.bool({{USE_MULTI_TIMEFRAME}}, "Use Multi-Timeframe")
higherTimeframe = input.timeframe("{{HIGHER_TIMEFRAME}}", "Higher Timeframe")

// ─── Grid Calculation ─────────────────────────────────────────────────────────
gridUpper = basePrice * (1 + gridSpacing * gridLevels)
gridLower = basePrice * (1 - gridSpacing * gridLevels)
gridStep = (gridUpper - gridLower) / gridLevels

// Current price position in grid
pricePosition = (close - gridLower) / (gridUpper - gridLower) * 100

// ─── Grid Signals ─────────────────────────────────────────────────────────────
// Buy when price enters a grid zone from below
// Sell when price exits a grid zone upward
var int gridLevel = 0
for i = 0 to gridLevels
    if close > gridLower + gridStep * i and close < gridLower + gridStep * (i + 1)
        gridLevel := i
        break

gridBuySignal = close > basePrice and close < gridUpper
gridSellSignal = close >= gridUpper

// ─── Risk Management ─────────────────────────────────────────────────────────
longStopPrice = close * (1 - stopLossPct)
shortStopPrice = close * (1 + stopLossPct)
longTakePrice = close * (1 + takeProfitPct)
shortTakePrice = close * (1 - takeProfitPct)

// ─── Strategy Entries ─────────────────────────────────────────────────────────
if gridBuySignal and strategy.position_size == 0
    strategy.entry("Grid Long", strategy.long)
    strategy.exit("Grid Long Exit", "Grid Long", stop=longStopPrice, limit=longTakePrice)

if gridSellSignal and strategy.position_size > 0
    strategy.close("Grid Long")

// ─── Visual Plots ──────────────────────────────────────────────────────────────
for i = 0 to gridLevels
    line.new(x1=bar_index, y1=gridLower + gridStep * i, x2=bar_index + 1, y2=gridLower + gridStep * i, color=color.gray, style=line.style_dashed, linewidth=1)

// Entry markers
plotshape(gridBuySignal and strategy.position_size == 0, title="Grid Buy", location=location.belowbar, style=shape.triangleup, color=color.lime, size=size.small, text="BUY")
plotshape(gridSellSignal, title="Grid Sell", location=location.abovebar, style=shape.triangledown, color=color.red, size=size.small, text="SELL")

// ─── Dashboard Table ──────────────────────────────────────────────────────────
var table dashboard = table.new(position.top_right, 2, 4, bgcolor=color.new(color.black, 80))
if barstate.date != na
    table.cell(dashboard, 0, 0, "Grid Level", text_color=color.white)
    table.cell(dashboard, 1, 0, str.tostring(gridLevel) + "/" + str.tostring(gridLevels), text_color=color.yellow)
    table.cell(dashboard, 0, 1, "Position %", text_color=color.white)
    table.cell(dashboard, 1, 1, str.tostring(pricePosition, "#.#") + "%", text_color=color.white)
    table.cell(dashboard, 0, 2, "Grid Spacing", text_color=color.white)
    table.cell(dashboard, 1, 2, str.tostring(gridSpacing * 100, "#.#") + "%", text_color=color.white)
    table.cell(dashboard, 0, 3, "PnL %", text_color=color.white)
    table.cell(dashboard, 1, 3, str.tostring(strategy.openprofit / strategy.equity * 100, "#.##") + "%", text_color=color.lime)
''',

    "moon_phase": '''//@version=5
strategy("{{STRATEGY_NAME}} - Moon Phase", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=10)

// ─── Inputs ───────────────────────────────────────────────────────────────────
moonCycleLength = input.int({{MOON_CYCLE_DAYS}}, "Moon Cycle (Days)", minval=20, maxval=35)
stopLossPct = input.float({{STOP_LOSS_PCT}} * 100, "Stop Loss %", minval=0.1, maxval=50, step=0.1) / 100
takeProfitPct = input.float({{TAKE_PROFIT_PCT}} * 100, "Take Profit %", minval=0.1, maxval=100, step=0.1) / 100
useConfirmation = input.bool({{USE_CONFIRMATION}}, "Use Price Confirmation")
confirmationPeriod = input.int({{CONFIRMATION_PERIOD}}, "Confirmation Period", minval=1, maxval=20)
useMultiTimeframe = input.bool({{USE_MULTI_TIMEFRAME}}, "Use Multi-Timeframe")
higherTimeframe = input.timeframe("{{HIGHER_TIMEFRAME}}", "Higher Timeframe")

// ─── Moon Phase Calculation (Approximation) ────────────────────────────────────
// Uses a simple sinusoidal model based on date to approximate moon phase
moonPhase(cycleLength) =>
    // Days since known new moon (Jan 6, 2000)
    daysSinceNewMoon = (timestamp - timestamp(2000, 1, 6, 0, 0)) / (1000 * 60 * 60 * 24)
    cyclePosition = (daysSinceNewMoon % cycleLength) / cycleLength
    // Convert to phase angle (0 to 2π)
    phaseAngle = cyclePosition * 2 * math.pi
    // Return phase (0 = new moon, 0.5 = full moon)
    (math.sin(phaseAngle - math.pi / 2) + 1) / 2

currentPhase = moonPhase(moonCycleLength)

// Lunar strength (how close to full or new moon)
lunarStrength = math.abs(currentPhase - 0.5) * 2  // 1 at full/new moon, 0 at quarters

// ─── Entry Signals ─────────────────────────────────────────────────────────────
longCondition = currentPhase > {{MOON_BUY_THRESHOLD}} and lunarStrength > {{LUNAR_STRENGTH_THRESHOLD}}
shortCondition = currentPhase < {{MOON_SELL_THRESHOLD}} and lunarStrength > {{LUNAR_STRENGTH_THRESHOLD}}

// Confirmation: price moving in expected direction
priceConfirmation = useConfirmation ? (close > close[confirmationPeriod] and longCondition) or (close < close[confirmationPeriod] and shortCondition) : true

if longCondition and priceConfirmation
    strategy.entry("Lunar Long", strategy.long)

if shortCondition and priceConfirmation
    strategy.entry("Lunar Short", strategy.short)

// ─── Risk Management ─────────────────────────────────────────────────────────
longStopPrice = close * (1 - stopLossPct)
shortStopPrice = close * (1 + stopLossPct)
longTakePrice = close * (1 + takeProfitPct)
shortTakePrice = close * (1 - takeProfitPct)

// ─── Strategy Exits ─────────────────────────────────────────────────────────
if strategy.position_size > 0
    strategy.exit("Lunar Long Exit", "Lunar Long", stop=longStopPrice, limit=longTakePrice)

if strategy.position_size < 0
    strategy.exit("Lunar Short Exit", "Lunar Short", stop=shortStopPrice, limit=shortTakePrice)

// ─── Visual Plots ──────────────────────────────────────────────────────────────
plot(currentPhase, "Moon Phase", color=color.gray, linewidth=2)
plot(lunarStrength, "Lunar Strength", color=color(152, 0, 255, 0), linewidth=3)
hline({{MOON_BUY_THRESHOLD}}, "Buy Threshold", color=color.green, linestyle=hline.style_dashed)
hline({{MOON_SELL_THRESHOLD}}, "Sell Threshold", color=color.red, linestyle=hline.style_dashed)

// Entry markers
plotshape(longCondition and priceConfirmation, title="Lunar Long", location=location.belowbar, style=shape.triangleup, color=color.cyan, size=size.small, text="LONG")
plotshape(shortCondition and priceConfirmation, title="Lunar Short", location=location.abovebar, style=shape.triangledown, color=color.purple, size=size.small, text="SHORT")

// Phase labels
var label phaseLabel = na
if barstate.islast
    phaseText = currentPhase > 0.45 and currentPhase < 0.55 ? "🌕 Full Moon" : currentPhase > 0.95 or currentPhase < 0.05 ? "🌑 New Moon" : currentPhase > 0.2 and currentPhase < 0.3 ? "🌗 Last Quarter" : currentPhase > 0.7 and currentPhase < 0.8 ? "🌓 First Quarter" : "🌔 Waxing/Growing"
    label.delete(phaseLabel)
    phaseLabel := label.new(x=bar_index - 50, y=high * 1.005, text=phaseText, color=color.blue, textcolor=color.white, size=size.small)

// ─── Dashboard Table ──────────────────────────────────────────────────────────
var table dashboard = table.new(position.top_right, 2, 4, bgcolor=color.new(color.black, 80))
if barstate.date != na
    table.cell(dashboard, 0, 0, "Moon Phase", text_color=color.white)
    table.cell(dashboard, 1, 0, str.tostring(currentPhase, "#.##"), text_color=color.gray)
    table.cell(dashboard, 0, 1, "Lunar Strength", text_color=color.white)
    table.cell(dashboard, 1, 1, str.tostring(lunarStrength, "#.##"), text_color=color.purple)
    table.cell(dashboard, 0, 2, "Strategy Dir", text_color=color.white)
    table.cell(dashboard, 1, 2, strategy.position_size > 0 ? "Long" : strategy.position_size < 0 ? "Short" : "Flat", text_color=color.white)
    table.cell(dashboard, 0, 3, "PnL %", text_color=color.white)
    table.cell(dashboard, 1, 3, str.tostring(strategy.openprofit / strategy.equity * 100, "#.##") + "%", text_color=color.lime)
'''
}


# ====================
# Default Parameters Per Strategy Type
# ====================

DEFAULT_PARAMS = {
    "ma_crossover": {
        "STRATEGY_NAME": "MA Crossover Strategy",
        "SOURCE": "close",
        "FAST_MA_PERIOD": 10,
        "SLOW_MA_PERIOD": 30,
        "STOP_LOSS_PCT": 0.02,
        "TAKE_PROFIT_PCT": 0.05,
        "USE_MULTI_TIMEFRAME": False,
        "HIGHER_TIMEFRAME": "1D",
        "ENTRY_PRICE": 0,
    },
    "bollinger_rsi": {
        "STRATEGY_NAME": "Bollinger + RSI Strategy",
        "BB_PERIOD": 20,
        "BB_STD_DEV": 2.0,
        "RSI_PERIOD": 14,
        "RSI_SOURCE": "close",
        "RSI_OVERBOUGHT": 70,
        "RSI_OVERSOLD": 30,
        "STOP_LOSS_PCT": 0.02,
        "TAKE_PROFIT_PCT": 0.05,
        "USE_MULTI_TIMEFRAME": False,
        "HIGHER_TIMEFRAME": "1D",
    },
    "macd_momentum": {
        "STRATEGY_NAME": "MACD Momentum Strategy",
        "MACD_FAST": 12,
        "MACD_SLOW": 26,
        "MACD_SIGNAL": 9,
        "SOURCE": "close",
        "STOP_LOSS_PCT": 0.02,
        "TAKE_PROFIT_PCT": 0.05,
        "USE_MULTI_TIMEFRAME": False,
        "HIGHER_TIMEFRAME": "1D",
    },
    "supertrend": {
        "STRATEGY_NAME": "Supertrend Strategy",
        "ATR_PERIOD": 10,
        "ATR_MULTIPLIER": 3.0,
        "STOP_LOSS_PCT": 0.02,
        "TAKE_PROFIT_PCT": 0.05,
        "USE_MULTI_TIMEFRAME": False,
        "HIGHER_TIMEFRAME": "1D",
    },
    "donchian_breakout": {
        "STRATEGY_NAME": "Donchian Breakout Strategy",
        "DONCHIAN_PERIOD": 20,
        "STOP_LOSS_PCT": 0.02,
        "TAKE_PROFIT_PCT": 0.05,
        "BREAKOUT_THRESHOLD": 0,
        "USE_MULTI_TIMEFRAME": False,
        "HIGHER_TIMEFRAME": "1D",
    },
    "grid_trading": {
        "STRATEGY_NAME": "Grid Trading Strategy",
        "GRID_LEVELS": 5,
        "GRID_SPACING_PCT": 1.0,
        "BASE_PRICE": 100,
        "STOP_LOSS_PCT": 0.02,
        "TAKE_PROFIT_PCT": 0.05,
        "USE_MULTI_TIMEFRAME": False,
        "HIGHER_TIMEFRAME": "1D",
    },
    "moon_phase": {
        "STRATEGY_NAME": "Moon Phase Strategy",
        "MOON_CYCLE_DAYS": 29,
        "STOP_LOSS_PCT": 0.02,
        "TAKE_PROFIT_PCT": 0.05,
        "USE_CONFIRMATION": True,
        "CONFIRMATION_PERIOD": 5,
        "MOON_BUY_THRESHOLD": 0.6,
        "MOON_SELL_THRESHOLD": 0.4,
        "LUNAR_STRENGTH_THRESHOLD": 0.5,
        "USE_MULTI_TIMEFRAME": False,
        "HIGHER_TIMEFRAME": "1D",
    },
}


# ====================
# Pydantic Schemas
# ====================

class ExportFormat(str):
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    EXCEL = "excel"


class ExportRequest(BaseModel):
    format: str = "json"
    include_indicators: bool = True
    include_history: bool = False


class ExportResponse(BaseModel):
    export_id: str
    status: str
    download_url: Optional[str] = None
    expires_at: Optional[str] = None

    class Config:
        from_attributes = True


class PineScriptTemplateResponse(BaseModel):
    strategy_type: str
    template: str


# ====================
# Routes
# ====================

@router.get(
    "/pine-script/{strategy_id}",
    response_class=PlainTextResponse,
    summary="Export Strategy as Pine Script v5",
    description="Returns the Pine Script v5 code for a specific strategy by ID.",
)
async def export_pine_script(
    strategy_id: UUID = Path(..., description="The strategy UUID to export"),
    db: AsyncSession = Depends(get_db),
):
    """
    Export a strategy as TradingView Pine Script v5 code.
    Fetches strategy from DB, replaces template parameters, returns plain text.
    """
    # Try to fetch strategy from database
    from models.strategy import Strategy
    
    try:
        from sqlalchemy import select
        result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
        strategy = result.scalar_one_or_none()
    except Exception:
        strategy = None
    
    if not strategy:
        # Return template with default parameters for a ma_crossover example
        template = PINE_SCRIPT_TEMPLATES.get("ma_crossover", "")
        if template:
            return PlainTextResponse(
                content=template,
                media_type="text/plain; charset=utf-8",
            )
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # Get strategy type and parameters
    strategy_type = strategy.strategy_type if hasattr(strategy, 'strategy_type') else "ma_crossover"
    params = strategy.parameters if hasattr(strategy, 'parameters') and strategy.parameters else {}
    
    # Merge with defaults
    defaults = DEFAULT_PARAMS.get(strategy_type, DEFAULT_PARAMS["ma_crossover"])
    merged_params = {**defaults, **params}
    
    # Override strategy name
    merged_params["STRATEGY_NAME"] = strategy.name if hasattr(strategy, 'name') else strategy_type
    
    # Get template
    template = PINE_SCRIPT_TEMPLATES.get(strategy_type, PINE_SCRIPT_TEMPLATES["ma_crossover"])
    
    # Replace placeholders
    pine_script = template
    for key, value in merged_params.items():
        placeholder = f"{{{{{key}}}}}"
        if placeholder in pine_script:
            if isinstance(value, bool):
                pine_script = pine_script.replace(placeholder, str(value).lower())
            else:
                pine_script = pine_script.replace(placeholder, str(value))
    
    return PlainTextResponse(content=pine_script, media_type="text/plain; charset=utf-8")


@router.get(
    "/pine-script/template/{strategy_type}",
    response_class=PlainTextResponse,
    summary="Get Pine Script Template",
    description="Returns the Pine Script v5 template for a specific strategy type.",
)
async def get_pine_script_template(
    strategy_type: str = Path(..., description="Strategy type (ma_crossover, bollinger_rsi, macd_momentum, supertrend, donchian_breakout, grid_trading, moon_phase)"),
):
    """
    Get the Pine Script v5 template for a strategy type.
    Returns a template with {{PARAM_NAME}} placeholders for customization.
    """
    if strategy_type not in PINE_SCRIPT_TEMPLATES:
        valid_types = ", ".join(PINE_SCRIPT_TEMPLATES.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy type: {strategy_type}. Valid types: {valid_types}",
        )
    
    template = PINE_SCRIPT_TEMPLATES[strategy_type]
    return PlainTextResponse(content=template, media_type="text/plain; charset=utf-8")


# ====================
# Legacy Export Routes (kept for backwards compatibility)
# ====================

@router.get("/strategies/{strategy_id}")
async def export_strategy(
    strategy_id: UUID,
    format: str = Query("json", enum=["json", "pine_script"]),
    db: AsyncSession = Depends(get_db),
):
    """
    Export a strategy in the specified format.
    """
    if format == "pine_script":
        return await export_pine_script(strategy_id, db)
    raise HTTPException(status_code=404, detail="Strategy not found")


@router.get("/backtests/{backtest_id}")
async def export_backtest(
    backtest_id: UUID,
    format: str = Query("json", enum=["json", "csv", "pdf"]),
    db: AsyncSession = Depends(get_db),
):
    """
    Export a backtest result in the specified format.
    """
    raise HTTPException(status_code=404, detail="Backtest not found")


@router.get("/portfolios/{portfolio_id}")
async def export_portfolio(
    portfolio_id: UUID,
    format: str = Query("json", enum=["json", "csv", "pdf", "excel"]),
    db: AsyncSession = Depends(get_db),
):
    """
    Export a portfolio in the specified format.
    """
    raise HTTPException(status_code=404, detail="Portfolio not found")


@router.get("/signals/{signal_id}")
async def export_signal(
    signal_id: UUID,
    format: str = Query("json", enum=["json", "csv"]),
    db: AsyncSession = Depends(get_db),
):
    """
    Export a trading signal in the specified format.
    """
    raise HTTPException(status_code=404, detail="Signal not found")


@router.get("/batch")
async def batch_export(
    ids: str,
    export_type: str = Query(..., enum=["strategies", "backtests", "portfolios"]),
    format: str = Query("json", enum=["json", "csv", "zip"]),
    db: AsyncSession = Depends(get_db),
):
    """
    Export multiple items as a batch.
    """
    return {"export_id": "", "status": "pending", "items_count": 0}
