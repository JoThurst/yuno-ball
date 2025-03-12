const path = require('path');

module.exports = {
    mode: 'production',
    entry: {
        charts: './app/static/js/charts.js',
        team_charts: './app/static/js/team_charts.js'
    },
    output: {
        filename: '[name].bundle.js',
        path: path.resolve(__dirname, 'app/static/dist'),
        clean: true
    }
}; 