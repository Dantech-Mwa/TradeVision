// chart-core.js - Advanced chart core for indicator and drawing engines
const ChartCore = (function() {
    // Internal state
    let charts = {};
    let mainChart = null;
    let mainSeries = null;
    let overlays = {};
    let indicatorPanes = {};
    let candles = [];
    
    const core = {
        // ==================== CHART CREATION & MANAGEMENT ====================
        createChart: function(container, options) {
            if (typeof LightweightCharts === 'undefined') {
                console.error('LightweightCharts not loaded!');
                return null;
            }
            const chart = LightweightCharts.createChart(container, options);
            const id = 'chart_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            charts[id] = chart;
            return chart;
        },
        
        setMainChart: function(chart, series) {
            mainChart = chart;
            mainSeries = series;
            console.log('✅ ChartCore: Main chart and series set');
        },
        
        getMainChart: function() {
            return mainChart || Object.values(charts)[0];
        },
        
        getMainSeries: function() {
            return mainSeries;
        },
        
        // ==================== OVERLAY SERIES MANAGEMENT ====================
        addOverlay: function(name, data, options = {}) {
            console.log(`[ChartCore] Adding overlay: ${name}`, data?.length || 0, 'data points');
            
            if (!mainChart) {
                console.warn('[ChartCore] No main chart found');
                return null;
            }
            
            // Remove existing overlay with same name
            if (overlays[name]) {
                this.removeOverlay(name);
            }
            
            const seriesOptions = {
                color: options.color || getIndicatorColor(name),
                lineWidth: options.lineWidth || 2,
                title: options.title || name,
                priceScaleId: options.priceScaleId || 'right',
                lastValueVisible: options.lastValueVisible !== undefined ? options.lastValueVisible : true,
                priceLineVisible: options.priceLineVisible !== undefined ? options.priceLineVisible : true,
                ...options
            };
            
            try {
                const series = mainChart.addLineSeries(seriesOptions);
                
                // Filter out invalid data points
                const validData = (data || []).filter(point => 
                    point && 
                    point.time !== undefined && 
                    point.time !== null && 
                    point.value !== undefined && 
                    point.value !== null &&
                    !isNaN(point.time) && 
                    !isNaN(point.value)
                );
                
                if (validData.length > 0) {
                    series.setData(validData);
                }
                
                overlays[name] = series;
                console.log(`✅ ChartCore: Overlay "${name}" added with ${validData.length} points`);
                return series;
            } catch (error) {
                console.error(`[ChartCore] Error adding overlay "${name}":`, error);
                return null;
            }
        },
        
        removeOverlay: function(name) {
            console.log(`[ChartCore] Removing overlay: ${name}`);
            if (overlays[name] && mainChart) {
                try {
                    mainChart.removeSeries(overlays[name]);
                    delete overlays[name];
                    console.log(`✅ ChartCore: Overlay "${name}" removed`);
                } catch (e) {
                    console.error('[ChartCore] Error removing overlay:', e);
                }
            }
        },
        
        removeAllOverlays: function() {
            Object.keys(overlays).forEach(name => {
                this.removeOverlay(name);
            });
        },
        
        getOverlay: function(name) {
            return overlays[name];
        },
        
        getAllOverlays: function() {
            return { ...overlays };
        },
        
        // ==================== INDICATOR PANES MANAGEMENT ====================
        addIndicatorPane: function(paneId, chart, options = {}) {
            console.log(`[ChartCore] Adding indicator pane: ${paneId}`);
            indicatorPanes[paneId] = {
                chart: chart,
                series: {},
                options: options
            };
            return indicatorPanes[paneId];
        },
        
        addIndicatorSeries: function(paneId, name, data, options = {}) {
            console.log(`[ChartCore] Adding indicator series: ${paneId} - ${name}`, data?.length || 0, 'data points');
            
            const pane = indicatorPanes[paneId];
            if (!pane || !pane.chart) {
                console.warn(`[ChartCore] Indicator pane "${paneId}" not found`);
                return null;
            }
            
            try {
                const seriesOptions = {
                    color: options.color || getIndicatorColor(name),
                    lineWidth: options.lineWidth || 2,
                    title: options.title || name,
                    ...options
                };
                
                const series = pane.chart.addLineSeries(seriesOptions);
                
                // Filter out invalid data points
                const validData = (data || []).filter(point => 
                    point && 
                    point.time !== undefined && 
                    point.time !== null && 
                    point.value !== undefined && 
                    point.value !== null &&
                    !isNaN(point.time) && 
                    !isNaN(point.value)
                );
                
                if (validData.length > 0) {
                    series.setData(validData);
                }
                
                pane.series[name] = series;
                console.log(`✅ ChartCore: Indicator series "${name}" added to pane "${paneId}"`);
                return series;
            } catch (error) {
                console.error(`[ChartCore] Error adding indicator series "${name}":`, error);
                return null;
            }
        },
        
        removeIndicatorSeries: function(paneId, name) {
            const pane = indicatorPanes[paneId];
            if (pane && pane.series[name] && pane.chart) {
                try {
                    pane.chart.removeSeries(pane.series[name]);
                    delete pane.series[name];
                    console.log(`✅ ChartCore: Indicator series "${name}" removed from pane "${paneId}"`);
                } catch (e) {
                    console.error('[ChartCore] Error removing indicator series:', e);
                }
            }
        },
        
        removeIndicatorPane: function(paneId) {
            console.log(`[ChartCore] Removing indicator pane: ${paneId}`);
            const pane = indicatorPanes[paneId];
            if (pane && pane.chart) {
                try {
                    // Remove all series first
                    Object.keys(pane.series).forEach(seriesName => {
                        try {
                            pane.chart.removeSeries(pane.series[seriesName]);
                        } catch (e) {
                            // Ignore removal errors
                        }
                    });
                    
                    // Remove the chart
                    pane.chart.remove();
                    delete indicatorPanes[paneId];
                    console.log(`✅ ChartCore: Indicator pane "${paneId}" removed`);
                } catch (e) {
                    console.error('[ChartCore] Error removing indicator pane:', e);
                }
            }
        },
        
        getIndicatorPane: function(paneId) {
            return indicatorPanes[paneId];
        },
        
        getAllIndicatorPanes: function() {
            return { ...indicatorPanes };
        },
        
        // ==================== COORDINATE CONVERSION ====================
        pixelToAnchor: function(x, y) {
            try {
                if (!mainChart || !mainSeries) {
                    console.warn('ChartCore: mainChart or mainSeries not available');
                    return { time: null, price: null, x: x, y: y };
                }
                
                const timeScale = mainChart.timeScale();
                const priceScale = mainSeries.priceScale();
                
                if (!timeScale || !priceScale) {
                    return { time: null, price: null, x: x, y: y };
                }
                
                // Convert x pixel to time
                const time = timeScale.coordinateToTime(x);
                
                // Convert y pixel to price  
                const price = priceScale.coordinateToPrice(y);
                
                return { 
                    time: time !== null ? Math.floor(time) : null, 
                    price: price !== null ? Number(price.toFixed(8)) : null,
                    x: x,
                    y: y
                };
            } catch (error) {
                console.error('ChartCore.pixelToAnchor error:', error);
                return { time: null, price: null, x: x, y: y };
            }
        },
        
        anchorToPixel: function(anchor) {
            try {
                if (!mainChart || !mainSeries || !anchor) {
                    console.warn('ChartCore: Missing required parameters');
                    return null;
                }
                
                const timeScale = mainChart.timeScale();
                const priceScale = mainSeries.priceScale();
                
                if (!timeScale || !priceScale) {
                    return null;
                }
                
                let x, y;
                
                // Handle different anchor formats
                if (anchor.time !== undefined && anchor.price !== undefined) {
                    // Convert time to x pixel
                    x = timeScale.timeToCoordinate(anchor.time);
                    
                    // Convert price to y pixel
                    y = priceScale.priceToCoordinate(anchor.price);
                } else if (anchor.x !== undefined && anchor.y !== undefined) {
                    // Already in pixel coordinates
                    x = anchor.x;
                    y = anchor.y;
                } else {
                    console.warn('ChartCore: Invalid anchor format', anchor);
                    return null;
                }
                
                // Handle null results (out of visible range)
                if (x === null || y === null) {
                    // Return fallback using normalized coordinates
                    const rect = mainChart.container().getBoundingClientRect();
                    const fallbackX = anchor.x !== undefined ? anchor.x : 0;
                    const fallbackY = anchor.y !== undefined ? anchor.y : 0;
                    
                    return { 
                        x: clamp(fallbackX, 0, rect.width),
                        y: clamp(fallbackY, 0, rect.height)
                    };
                }
                
                return { x, y };
            } catch (error) {
                console.error('ChartCore.anchorToPixel error:', error);
                return null;
            }
        },
        
        // ==================== DRAWING ENGINE INTEGRATION ====================
        createDrawingProxy: function() {
            return {
                pixelToCoordinate: (pt) => {
                    return this.pixelToAnchor(pt.x, pt.y);
                },
                coordinateToPixel: (coord) => {
                    return this.anchorToPixel(coord);
                }
            };
        },
        
        // ==================== DATA MANAGEMENT ====================
        setCandles: function(newCandles) {
            console.log('[ChartCore] Setting candles:', newCandles?.length || 0);
            candles = newCandles || [];
            return candles;
        },
        
        getCandles: function() {
            return [...candles];
        },
        
        getLastCandle: function() {
            return candles.length > 0 ? candles[candles.length - 1] : null;
        },
        
        getCandleAtTime: function(time) {
            return candles.find(candle => Math.floor(candle.time) === Math.floor(time));
        },
        
        // ==================== UTILITY FUNCTIONS ====================
        synchronizeCharts: function() {
            const allCharts = Object.values(charts).filter(chart => chart && chart.timeScale);
            
            if (allCharts.length < 2) return;
            
            allCharts.forEach(chart => {
                try {
                    chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
                        if (!range || range.from === null || range.to === null) return;
                        
                        allCharts.forEach(other => {
                            if (other === chart) return;
                            try {
                                other.timeScale().setVisibleRange({ 
                                    from: range.from, 
                                    to: range.to 
                                });
                            } catch (e) {
                                // Ignore synchronization errors
                            }
                        });
                    });
                } catch (e) {
                    console.warn('ChartCore: Error synchronizing charts', e);
                }
            });
            
            console.log('✅ ChartCore: Charts synchronized');
        },
        
        fitAllContent: function() {
            Object.values(charts).forEach(chart => {
                try {
                    if (chart && chart.timeScale) {
                        chart.timeScale().fitContent();
                    }
                } catch (e) {
                    console.warn('ChartCore: Error fitting content', e);
                }
            });
        },
        
        getChartContainerRect: function(chartId) {
            const chart = chartId ? charts[chartId] : mainChart;
            if (!chart) return null;
            
            const container = chart.container();
            if (!container) return null;
            
            return container.getBoundingClientRect();
        },
        
        // ==================== EXPORT/IMPORT ====================
        exportLayout: function() {
            const layout = {
                mainChart: !!mainChart,
                overlays: Object.keys(overlays),
                indicatorPanes: Object.keys(indicatorPanes),
                candleCount: candles.length,
                timestamp: Date.now()
            };
            return JSON.stringify(layout);
        },
        
        reset: function() {
            // Remove all overlays
            this.removeAllOverlays();
            
            // Remove all indicator panes
            Object.keys(indicatorPanes).forEach(paneId => {
                this.removeIndicatorPane(paneId);
            });
            
            // Clear data
            candles = [];
            
            console.log('✅ ChartCore: Reset complete');
        }
    };
    
    // Helper functions
    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }
    
    function getIndicatorColor(indicatorName) {
        const colors = {
            'SMA': '#ff6b6b',
            'EMA': '#4ecdc4',
            'WMA': '#45b7d1',
            'HMA': '#96ceb4',
            'Bollinger': '#feca57',
            'Bollinger_mid': '#feca57',
            'Bollinger_upper': '#ff9ff3',
            'Bollinger_lower': '#ff9ff3',
            'VWAP': '#54a0ff',
            'RSI': '#9b6cff',
            'MACD': '#3399ff',
            'MACD_hist': '#26a69a',
            'MACD_signal': '#ffa500',
            'Stochastic_k': '#FF6B6B',
            'Stochastic_d': '#4ECADC',
            'ATR': '#5f27cd',
            'CCI': '#00d2d3',
            'Volume': '#26a69a',
            'default': '#338fff'
        };
        
        return colors[indicatorName] || colors.default;
    }
    
    // Make globally available
    if (typeof window !== 'undefined') {
        window.ChartCore = core;
    }
    
    return core;
})();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChartCore;
}
