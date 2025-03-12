import { Chart } from 'chart.js/auto';

// Export Chart.js functionality for use in templates
window.createChart = function(canvasId, type, data, options = {}) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: type,
        data: data,
        options: options
    });
};

// Make Chart available globally for any legacy code
window.Chart = Chart; 