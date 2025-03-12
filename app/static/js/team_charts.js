// Import Chart.js
import { Chart } from 'chart.js/auto';

// Create a global object for our chart functions
window.YunoCharts = {
    initializeTeamStatsChart: function(ctx, data) {
        return new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['Points', 'Rebounds', 'Assists', 'Steals', 'Blocks', 'FG%'],
                datasets: [{
                    label: 'Team Stats',
                    data: data,
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    pointBackgroundColor: 'rgba(54, 162, 235, 1)',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: 'rgba(54, 162, 235, 1)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    r: {
                        angleLines: { color: 'rgba(255, 255, 255, 0.1)' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        pointLabels: { color: '#ffffff' },
                        ticks: {
                            backdropColor: 'transparent',
                            color: 'rgba(255, 255, 255, 0.5)'
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: { color: '#ffffff' }
                    }
                }
            }
        });
    },

    initializeWinLossChart: function(ctx, data) {
        return new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Wins', 'Losses'],
                datasets: [{
                    data: [data.wins, data.losses],
                    backgroundColor: [
                        'rgba(72, 187, 120, 0.8)',  // Green for wins
                        'rgba(239, 68, 68, 0.8)'    // Red for losses
                    ],
                    borderColor: [
                        'rgba(72, 187, 120, 1)',
                        'rgba(239, 68, 68, 1)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#ffffff',
                            padding: 20
                        }
                    }
                }
            }
        });
    }
};

(function() {
  // Function to initialize charts
  function initCharts() {
    // Check if Chart.js is loaded
    if (typeof Chart === 'undefined') {
      console.error('Chart.js is not loaded. Please include the Chart.js library.');
      
      // Display error messages for all canvas elements
      document.querySelectorAll('canvas').forEach(canvas => {
        canvas.style.display = 'none';
        const errorMsg = document.createElement('p');
        errorMsg.textContent = 'Chart.js could not be loaded. Charts are unavailable.';
        errorMsg.className = 'text-red-400 text-center py-10';
        canvas.parentNode.appendChild(errorMsg);
      });
      
      return;
    }

    // Team Stats Chart
    const statsCanvas = document.getElementById('teamStatsChart');
    if (statsCanvas) {
      try {
        const ctx = statsCanvas.getContext('2d');
        const teamName = statsCanvas.getAttribute('data-team-name') || 'Team';
        
        // Get stats from data attributes with fallbacks to 0
        const pts = parseFloat(statsCanvas.getAttribute('data-pts') || 0);
        const reb = parseFloat(statsCanvas.getAttribute('data-reb') || 0);
        const ast = parseFloat(statsCanvas.getAttribute('data-ast') || 0);
        const stl = parseFloat(statsCanvas.getAttribute('data-stl') || 0);
        const blk = parseFloat(statsCanvas.getAttribute('data-blk') || 0);
        const tov = parseFloat(statsCanvas.getAttribute('data-tov') || 0);
        
        // Check if we have any valid stats to display
        if (pts || reb || ast || stl || blk || tov) {
          const statsData = {
            labels: ['Points', 'Rebounds', 'Assists', 'Steals', 'Blocks', 'Turnovers'],
            datasets: [{
              label: `${teamName} Statistics`,
              data: [pts, reb, ast, stl, blk, tov],
              backgroundColor: [
                'rgba(54, 162, 235, 0.6)',
                'rgba(75, 192, 192, 0.6)',
                'rgba(153, 102, 255, 0.6)',
                'rgba(255, 159, 64, 0.6)',
                'rgba(255, 99, 132, 0.6)',
                'rgba(255, 205, 86, 0.6)'
              ],
              borderColor: [
                'rgba(54, 162, 235, 1)',
                'rgba(75, 192, 192, 1)',
                'rgba(153, 102, 255, 1)',
                'rgba(255, 159, 64, 1)',
                'rgba(255, 99, 132, 1)',
                'rgba(255, 205, 86, 1)'
              ],
              borderWidth: 1
            }]
          };
          
          new Chart(ctx, {
            type: 'bar',
            data: statsData,
            options: {
              responsive: true,
              maintainAspectRatio: false,
              scales: {
                y: {
                  beginAtZero: true,
                  grid: {
                    color: 'rgba(255, 255, 255, 0.1)'
                  },
                  ticks: {
                    color: 'rgba(255, 255, 255, 0.7)'
                  }
                },
                x: {
                  grid: {
                    color: 'rgba(255, 255, 255, 0.1)'
                  },
                  ticks: {
                    color: 'rgba(255, 255, 255, 0.7)'
                  }
                }
              },
              plugins: {
                legend: {
                  labels: {
                    color: 'rgba(255, 255, 255, 0.7)'
                  }
                }
              }
            }
          });
        } else {
          // Display a message if no stats are available
          statsCanvas.style.display = 'none';
          const noStatsMsg = document.createElement('p');
          noStatsMsg.textContent = 'No statistics available to display';
          noStatsMsg.className = 'text-gray-400 text-center py-10';
          statsCanvas.parentNode.appendChild(noStatsMsg);
        }
      } catch (error) {
        console.error('Error creating team stats chart:', error);
        statsCanvas.style.display = 'none';
        const errorMsg = document.createElement('p');
        errorMsg.textContent = 'Error creating chart. Please check the console for details.';
        errorMsg.className = 'text-red-400 text-center py-10';
        statsCanvas.parentNode.appendChild(errorMsg);
      }
    }
    
    // Win/Loss Pie Chart
    const winLossCanvas = document.getElementById('winLossChart');
    if (winLossCanvas) {
      try {
        const ctx = winLossCanvas.getContext('2d');
        
        // Get win/loss data from data attributes
        const record = winLossCanvas.getAttribute('data-record') || '';
        const winPct = parseFloat(winLossCanvas.getAttribute('data-win-pct') || 0);
        
        // Parse record string (e.g., "17 - 48") to get wins and losses
        let wins = 0;
        let losses = 0;
        
        if (record) {
          const recordParts = record.split('-').map(part => parseInt(part.trim()));
          if (recordParts.length === 2) {
            wins = recordParts[0] || 0;
            losses = recordParts[1] || 0;
          }
        }
        
        // Only create chart if we have wins or losses
        if (wins > 0 || losses > 0) {
          new Chart(ctx, {
            type: 'pie',
            data: {
              labels: ['Wins', 'Losses'],
              datasets: [{
                data: [wins, losses],
                backgroundColor: [
                  'rgba(75, 192, 192, 0.8)',
                  'rgba(255, 99, 132, 0.8)'
                ],
                borderColor: [
                  'rgba(75, 192, 192, 1)',
                  'rgba(255, 99, 132, 1)'
                ],
                borderWidth: 1
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: {
                  position: 'bottom',
                  labels: {
                    color: 'rgba(255, 255, 255, 0.7)'
                  }
                },
                tooltip: {
                  callbacks: {
                    label: function(context) {
                      const label = context.label || '';
                      const value = context.raw || 0;
                      const total = wins + losses;
                      const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                      return `${label}: ${value} (${percentage}%)`;
                    }
                  }
                }
              }
            }
          });
        } else {
          // Display a message if no win/loss data is available
          winLossCanvas.style.display = 'none';
          const noDataMsg = document.createElement('p');
          noDataMsg.textContent = 'No win/loss data available to display';
          noDataMsg.className = 'text-gray-400 text-center py-10';
          winLossCanvas.parentNode.appendChild(noDataMsg);
        }
      } catch (error) {
        console.error('Error creating win/loss chart:', error);
        winLossCanvas.style.display = 'none';
        const errorMsg = document.createElement('p');
        errorMsg.textContent = 'Error creating chart. Please check the console for details.';
        errorMsg.className = 'text-red-400 text-center py-10';
        winLossCanvas.parentNode.appendChild(errorMsg);
      }
    }
  }

  // If the document is already loaded, initialize charts immediately
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setTimeout(initCharts, 1);
  } else {
    // Otherwise wait for DOMContentLoaded
    document.addEventListener('DOMContentLoaded', initCharts);
  }
})(); 