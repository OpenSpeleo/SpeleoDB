// Utility functions
const hexToRGB = (h) => {
  let r = 0;
  let g = 0;
  let b = 0;
  if (h.length === 4) {
    r = `0x${h[1]}${h[1]}`;
    g = `0x${h[2]}${h[2]}`;
    b = `0x${h[3]}${h[3]}`;
  } else if (h.length === 7) {
    r = `0x${h[1]}${h[2]}`;
    g = `0x${h[3]}${h[4]}`;
    b = `0x${h[5]}${h[6]}`;
  }
  return `${+r},${+g},${+b}`;
};

const formatThousands = (value) => Intl.NumberFormat('en-US', {
  maximumSignificantDigits: 3,
  notation: 'compact',
}).format(value);

// Define Chart.js default settings
Chart.defaults.font.family = '"Inter", sans-serif';
Chart.defaults.font.weight = '500';
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.plugins.tooltip.displayColors = false;
Chart.defaults.plugins.tooltip.mode = 'nearest';
Chart.defaults.plugins.tooltip.intersect = false;
Chart.defaults.plugins.tooltip.position = 'nearest';
Chart.defaults.plugins.tooltip.caretSize = 0;
Chart.defaults.plugins.tooltip.caretPadding = 20;
Chart.defaults.plugins.tooltip.cornerRadius = 4;
Chart.defaults.plugins.tooltip.padding = 8;

// Register Chart.js plugin to add a bg option for chart area
Chart.register({
  id: 'chartAreaPlugin',
  // eslint-disable-next-line object-shorthand
  beforeDraw: (chart) => {
    if (chart.config.options.chartArea && chart.config.options.chartArea.backgroundColor) {
      const ctx = chart.canvas.getContext('2d');
      const { chartArea } = chart;
      ctx.save();
      ctx.fillStyle = chart.config.options.chartArea.backgroundColor;
      // eslint-disable-next-line max-len
      ctx.fillRect(chartArea.left, chartArea.top, chartArea.right - chartArea.left, chartArea.bottom - chartArea.top);
      ctx.restore();
    }
  },
});

// Init #analytics-01 chart
const analyticsCard01 = () => {
  const ctx = document.getElementById('analytics-card-01');
  if (!ctx) return;

  const darkMode = localStorage.getItem('dark-mode') === 'true';

  const textColor = {
    light: '#94a3b8',
    dark: '#64748B'
  };

  const gridColor = {
    light: '#f1f5f9',
    dark: '#334155'
  };

  const tooltipBodyColor = {
    light: '#1e293b',
    dark: '#f1f5f9'
  };

  const tooltipBgColor = {
    light: '#ffffff',
    dark: '#334155'
  };

  const tooltipBorderColor = {
    light: '#e2e8f0',
    dark: '#475569'
  };   

  // eslint-disable-next-line no-unused-vars
  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [
        '12-01-2020', '01-01-2021', '02-01-2021',
        '03-01-2021', '04-01-2021', '05-01-2021',
        '06-01-2021', '07-01-2021', '08-01-2021',
        '09-01-2021', '10-01-2021', '11-01-2021',
        '12-01-2021', '01-01-2022', '02-01-2022',
        '03-01-2022', '04-01-2022', '05-01-2022',
        '06-01-2022', '07-01-2022', '08-01-2022',
        '09-01-2022', '10-01-2022', '11-01-2022',
        '12-01-2022', '01-01-2023',
      ],
      datasets: [
        // Indigo line
        {
          label: 'Current',
          data: [
            5000, 8700, 7500, 12000, 11000, 9500, 10500,
            10000, 15000, 9000, 10000, 7000, 22000, 7200,
            9800, 9000, 10000, 8000, 15000, 12000, 11000,
            13000, 11000, 15000, 17000, 18000,
          ],
          fill: true,
          backgroundColor: `rgba(${hexToRGB('#3b82f6')}, 0.08)`,
          borderColor: '#6366f1',
          borderWidth: 2,
          tension: 0,
          pointRadius: 0,
          pointHoverRadius: 3,
          pointBackgroundColor: '#6366f1',
          pointHoverBackgroundColor: '#6366f1',
          pointBorderWidth: 0,
          pointBorderWidth: 0,
          pointHoverBorderWidth: 0,       
          clip: 20,
        },
        // Gray line
        {
          label: 'Previous',
          data: [
            8000, 5000, 6500, 5000, 6500, 12000, 8000,
            9000, 8000, 8000, 12500, 10000, 10000, 12000,
            11000, 16000, 12000, 10000, 10000, 14000, 9000,
            10000, 15000, 12500, 14000, 11000,
          ],
          borderColor: `rgba(${hexToRGB('#64748B')}, 0.25)`,
          fill: false,
          borderWidth: 2,
          tension: 0,
          pointRadius: 0,
          pointHoverRadius: 3,
          pointBackgroundColor: `rgba(${hexToRGB('#64748B')}, 0.25)`,
          pointHoverBackgroundColor: `rgba(${hexToRGB('#64748B')}, 0.25)`,
          pointBorderWidth: 0,
          pointHoverBorderWidth: 0,          
          clip: 20,
        },
      ],
    },
    options: {
      layout: {
        padding: 20,
      },
      scales: {      
        y: {
          beginAtZero: true,
          border: {
            display: false,
          },  
          ticks: {
            callback: (value) => formatThousands(value),
            color: darkMode ? textColor.dark : textColor.light,
          },
          grid: {
            color: darkMode ? gridColor.dark : gridColor.light,
          },   
        },
        x: {
          type: 'time',
          time: {
            parser: 'MM-DD-YYYY',
            unit: 'month',
            displayFormats: {
              month: 'MMM YY',
            },
          },
          border: {
            display: false,
          },            
          grid: {
            display: false,
          },
          ticks: {
            autoSkipPadding: 48,
            maxRotation: 0,
            color: darkMode ? textColor.dark : textColor.light,
          },
        },
      },
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          callbacks: {
            title: () => false, // Disable tooltip title
            label: (context) => formatThousands(context.parsed.y),
          },
          bodyColor: darkMode ? tooltipBodyColor.dark : tooltipBodyColor.light,
          backgroundColor: darkMode ? tooltipBgColor.dark : tooltipBgColor.light,
          borderColor: darkMode ? tooltipBorderColor.dark : tooltipBorderColor.light,          
        },
      },
      interaction: {
        intersect: false,
        mode: 'nearest',
      },
      maintainAspectRatio: false,
    },
  });

  document.addEventListener('darkMode', (e) => {
    const { mode } = e.detail;
    if (mode === 'on') {
      chart.options.scales.x.ticks.color = textColor.dark;
      chart.options.scales.y.ticks.color = textColor.dark;
      chart.options.scales.y.grid.color = gridColor.dark;
      chart.options.plugins.tooltip.bodyColor = tooltipBodyColor.dark;
      chart.options.plugins.tooltip.backgroundColor = tooltipBgColor.dark;
      chart.options.plugins.tooltip.borderColor = tooltipBorderColor.dark;
    } else {
      chart.options.scales.x.ticks.color = textColor.light;
      chart.options.scales.y.ticks.color = textColor.light;
      chart.options.scales.y.grid.color = gridColor.light;
      chart.options.plugins.tooltip.bodyColor = tooltipBodyColor.light;
      chart.options.plugins.tooltip.backgroundColor = tooltipBgColor.light;
      chart.options.plugins.tooltip.borderColor = tooltipBorderColor.light;
    }
    chart.update('none');
  });
};
analyticsCard01();

// Init #analytics-02 chart
const analyticsCard02 = () => {
  const ctx = document.getElementById('analytics-card-02');
  if (!ctx) return;

  const darkMode = localStorage.getItem('dark-mode') === 'true';

  const chartAreaBg = {
    light: '#f8fafc',
    dark: `rgba(${hexToRGB('#0F172A')}, 0.24)`
  };

  const tooltipBodyColor = {
    light: '#1e293b',
    dark: '#f1f5f9'
  };

  const tooltipBgColor = {
    light: '#ffffff',
    dark: '#334155'
  };

  const tooltipBorderColor = {
    light: '#e2e8f0',
    dark: '#475569'
  };

  // eslint-disable-next-line no-unused-vars
  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [
        '12-01-2020', '01-01-2021', '02-01-2021',
        '03-01-2021', '04-01-2021', '05-01-2021',
        '06-01-2021', '07-01-2021', '08-01-2021',
        '09-01-2021', '10-01-2021', '11-01-2021',
        '12-01-2021', '01-01-2022', '02-01-2022',
        '03-01-2022', '04-01-2022', '05-01-2022',
        '06-01-2022', '07-01-2022', '08-01-2022',
        '09-01-2022', '10-01-2022', '11-01-2022',
        '12-01-2022', '01-01-2023',
      ],
      datasets: [
        // Indigo line
        {
          data: [
            732, 610, 610, 504, 504, 504, 349,
            349, 504, 342, 504, 610, 391, 192,
            154, 273, 191, 191, 126, 263, 349,
            252, 423, 622, 470, 532,
          ],
          fill: true,
          backgroundColor: `rgba(${hexToRGB('#3b82f6')}, 0.08)`,
          borderColor: '#6366f1',
          borderWidth: 2,
          tension: 0,
          pointRadius: 0,
          pointHoverRadius: 3,
          pointBackgroundColor: '#6366f1',
          pointHoverBackgroundColor: '#6366f1',
          pointBorderWidth: 0,
          pointHoverBorderWidth: 0,              
          clip: 20,
        },
      ],
    },
    options: {
      chartArea: {
        backgroundColor: darkMode ? chartAreaBg.dark : chartAreaBg.light,
      },
      layout: {
        padding: {
          left: 20,
          right: 20,
        },
      },
      scales: {
        y: {
          display: false,
          beginAtZero: true,
        },
        x: {
          type: 'time',
          time: {
            parser: 'MM-DD-YYYY',
            unit: 'month',
          },
          display: false,
        },
      },
      plugins: {
        tooltip: {
          callbacks: {
            title: () => false, // Disable tooltip title
            label: (context) => formatThousands(context.parsed.y),
          },
          bodyColor: darkMode ? tooltipBodyColor.dark : tooltipBodyColor.light,
          backgroundColor: darkMode ? tooltipBgColor.dark : tooltipBgColor.light,
          borderColor: darkMode ? tooltipBorderColor.dark : tooltipBorderColor.light,          
        },
        legend: {
          display: false,
        },
      },
      interaction: {
        intersect: false,
        mode: 'nearest',
      },
      maintainAspectRatio: false,
    },
  });
  document.addEventListener('darkMode', (e) => {
    const { mode } = e.detail;
    if (mode === 'on') {
      chart.options.chartArea.backgroundColor = chartAreaBg.dark;
      chart.options.plugins.tooltip.bodyColor = tooltipBodyColor.dark;
      chart.options.plugins.tooltip.backgroundColor = tooltipBgColor.dark;
      chart.options.plugins.tooltip.borderColor = tooltipBorderColor.dark;
    } else {
      chart.options.chartArea.backgroundColor = chartAreaBg.light;
      chart.options.plugins.tooltip.bodyColor = tooltipBodyColor.light;
      chart.options.plugins.tooltip.backgroundColor = tooltipBgColor.light;
      chart.options.plugins.tooltip.borderColor = tooltipBorderColor.light;
    }
    chart.update('none');
  });  
};
analyticsCard02();

// Init #analytics-03 chart
const analyticsCard03 = () => {
  const ctx = document.getElementById('analytics-card-03');
  if (!ctx) return;

  const darkMode = localStorage.getItem('dark-mode') === 'true';

  const textColor = {
    light: '#94a3b8',
    dark: '#64748B'
  };

  const gridColor = {
    light: '#f1f5f9',
    dark: '#334155'
  };

  const tooltipBodyColor = {
    light: '#1e293b',
    dark: '#f1f5f9'
  };

  const tooltipBgColor = {
    light: '#ffffff',
    dark: '#334155'
  };

  const tooltipBorderColor = {
    light: '#e2e8f0',
    dark: '#475569'
  }; 

  // eslint-disable-next-line no-unused-vars
  const chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: [
        '12-01-2020', '01-01-2021', '02-01-2021',
        '03-01-2021', '04-01-2021', '05-01-2021',
      ],
      datasets: [
        // Stack
        {
          label: 'Direct',
          data: [
            5000, 4000, 4000, 3800, 5200, 5100,
          ],
          backgroundColor: '#4338ca',
          hoverBackgroundColor: '#3730a3',
          barPercentage: 0.66,
          categoryPercentage: 0.66,
        },
        // Stack
        {
          label: 'Referral',
          data: [
            2500, 2600, 4000, 4000, 4800, 3500,
          ],
          backgroundColor: '#6366f1',
          hoverBackgroundColor: '#4f46e5',
          barPercentage: 0.66,
          categoryPercentage: 0.66,
        },
        // Stack
        {
          label: 'Organic Search',
          data: [
            2300, 2000, 3100, 2700, 1300, 2600,
          ],
          backgroundColor: '#a5b4fc',
          hoverBackgroundColor: '#818cf8',
          barPercentage: 0.66,
          categoryPercentage: 0.66,
        },
        // Stack
        {
          label: 'Social',
          data: [
            4800, 4200, 4800, 1800, 3300, 3500,
          ],
          backgroundColor: '#e0e7ff',
          hoverBackgroundColor: '#c7d2fe',
          barPercentage: 0.66,
          categoryPercentage: 0.66,
        },
      ],
    },
    options: {
      layout: {
        padding: {
          top: 12,
          bottom: 16,
          left: 20,
          right: 20,
        },
      },
      scales: {
        y: {
          stacked: true,
          border: {
            display: false,
          },  
          beginAtZero: true,
          ticks: {
            maxTicksLimit: 5,
            callback: (value) => formatThousands(value),
            color: darkMode ? textColor.dark : textColor.light,
          },
          grid: {
            color: darkMode ? gridColor.dark : gridColor.light,
          },
        },
        x: {
          stacked: true,
          type: 'time',
          time: {
            parser: 'MM-DD-YYYY',
            unit: 'month',
            displayFormats: {
              month: 'MMM',
            },
          },
          border: {
            display: false,
          },            
          grid: {
            display: false,
          },
          ticks: {
            autoSkipPadding: 48,
            maxRotation: 0,
            color: darkMode ? textColor.dark : textColor.light,
          },
        },
      },
      plugins: {
        legend: {
          display: false,
        },
        htmlLegend: {
          // ID of the container to put the legend in
          containerID: 'analytics-card-03-legend',
        },
        tooltip: {
          callbacks: {
            title: () => false, // Disable tooltip title
            label: (context) => formatThousands(context.parsed.y),
          },
          bodyColor: darkMode ? tooltipBodyColor.dark : tooltipBodyColor.light,
          backgroundColor: darkMode ? tooltipBgColor.dark : tooltipBgColor.light,
          borderColor: darkMode ? tooltipBorderColor.dark : tooltipBorderColor.light,             
        },
      },
      interaction: {
        intersect: false,
        mode: 'nearest',
      },
      animation: {
        duration: 200,
      },
      maintainAspectRatio: false,
    },
    plugins: [{
      id: 'htmlLegend',
      afterUpdate(c, args, options) {
        const legendContainer = document.getElementById(options.containerID);
        const ul = legendContainer.querySelector('ul');
        if (!ul) return;
        // Remove old legend items
        while (ul.firstChild) {
          ul.firstChild.remove();
        }
        // Reuse the built-in legendItems generator
        const items = c.options.plugins.legend.labels.generateLabels(c);
        items.forEach((item) => {
          const li = document.createElement('li');
          li.style.marginRight = '12px';
          // Button element
          const button = document.createElement('button');
          button.style.display = 'inline-flex';
          button.style.alignItems = 'center';
          button.style.opacity = item.hidden ? '.3' : '';
          button.onclick = () => {
            c.setDatasetVisibility(item.datasetIndex, !c.isDatasetVisible(item.datasetIndex));
            c.update();
          };
          // Color box
          const box = document.createElement('span');
          box.style.display = 'block';
          box.style.width = '12px';
          box.style.height = '12px';
          box.style.borderRadius = '9999px';
          box.style.marginRight = '8px';
          box.style.borderWidth = '3px';
          box.style.borderColor = item.fillStyle;
          box.style.pointerEvents = 'none';
          // Label
          const label = document.createElement('span');
          label.classList.add('text-slate-500', 'dark:text-slate-400');
          label.style.fontSize = '0.875rem';
          label.style.lineHeight = '1.5715';
          const labelText = document.createTextNode(item.text);
          label.appendChild(labelText);
          li.appendChild(button);
          button.appendChild(box);
          button.appendChild(label);
          ul.appendChild(li);
        });
      },
    }],
  });

  document.addEventListener('darkMode', (e) => {
    const { mode } = e.detail;
    if (mode === 'on') {
      chart.options.scales.x.ticks.color = textColor.dark;
      chart.options.scales.y.ticks.color = textColor.dark;
      chart.options.scales.y.grid.color = gridColor.dark;
      chart.options.plugins.tooltip.bodyColor = tooltipBodyColor.dark;
      chart.options.plugins.tooltip.backgroundColor = tooltipBgColor.dark;
      chart.options.plugins.tooltip.borderColor = tooltipBorderColor.dark;
    } else {
      chart.options.scales.x.ticks.color = textColor.light;
      chart.options.scales.y.ticks.color = textColor.light;
      chart.options.scales.y.grid.color = gridColor.light;
      chart.options.plugins.tooltip.bodyColor = tooltipBodyColor.light;
      chart.options.plugins.tooltip.backgroundColor = tooltipBgColor.light;
      chart.options.plugins.tooltip.borderColor = tooltipBorderColor.light;
    }
    chart.update('none');
  });  
};
analyticsCard03();

// Init #analytics-04 chart
const analyticsCard04 = () => {
  const ctx = document.getElementById('analytics-card-04');
  if (!ctx) return;

  const darkMode = localStorage.getItem('dark-mode') === 'true';

  const textColor = {
    light: '#94a3b8',
    dark: '#64748B'
  };

  const gridColor = {
    light: '#f1f5f9',
    dark: '#334155'
  };

  const tooltipBodyColor = {
    light: '#1e293b',
    dark: '#f1f5f9'
  };

  const tooltipBgColor = {
    light: '#ffffff',
    dark: '#334155'
  };

  const tooltipBorderColor = {
    light: '#e2e8f0',
    dark: '#475569'
  };   

  // eslint-disable-next-line no-unused-vars
  const chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: [
        '02-01-2021', '03-01-2021', '04-01-2021', '05-01-2021',
      ],
      datasets: [
        // Blue bars
        {
          label: 'New Visitors',
          data: [
            8000, 3800, 5350, 7800,
          ],
          backgroundColor: '#6366f1',
          hoverBackgroundColor: '#4f46e5',
          categoryPercentage: 0.66,
        },
        // Light blue bars
        {
          label: 'Returning Visitors',
          data: [
            4000, 6500, 2200, 5800,
          ],
          backgroundColor: '#38bdf8',
          hoverBackgroundColor: '#0ea5e9',
          categoryPercentage: 0.66,
        },
      ],
    },
    options: {
      indexAxis: 'y',
      layout: {
        padding: {
          top: 12,
          bottom: 16,
          left: 20,
          right: 20,
        },
      },
      scales: {
        y: {
          type: 'time',
          time: {
            parser: 'MM-DD-YYYY',
            unit: 'month',
            displayFormats: {
              month: 'MMM',
            },
          },
          border: {
            display: false,
          },            
          grid: {
            display: false,
          },
          ticks: {
            color: darkMode ? textColor.dark : textColor.light,
          },           
        },
        x: {
          border: {
            display: false,
          },  
          ticks: {
            maxTicksLimit: 3,
            align: 'end',
            callback: (value) => formatThousands(value),
            color: darkMode ? textColor.dark : textColor.light,
          },
          grid: {
            color: darkMode ? gridColor.dark : gridColor.light,
          },
        },
      },
      plugins: {
        legend: {
          display: false,
        },
        htmlLegend: {
          // ID of the container to put the legend in
          containerID: 'analytics-card-04-legend',
        },
        tooltip: {
          callbacks: {
            title: () => false, // Disable tooltip title
            label: (context) => formatThousands(context.parsed.x),
          },
          bodyColor: darkMode ? tooltipBodyColor.dark : tooltipBodyColor.light,
          backgroundColor: darkMode ? tooltipBgColor.dark : tooltipBgColor.light,
          borderColor: darkMode ? tooltipBorderColor.dark : tooltipBorderColor.light,          
        },
      },
      interaction: {
        intersect: false,
        mode: 'nearest',
      },
      animation: {
        duration: 200,
      },
      maintainAspectRatio: false,
    },
    plugins: [{
      id: 'htmlLegend',
      afterUpdate(c, args, options) {
        const legendContainer = document.getElementById(options.containerID);
        const ul = legendContainer.querySelector('ul');
        if (!ul) return;
        // Remove old legend items
        while (ul.firstChild) {
          ul.firstChild.remove();
        }
        // Reuse the built-in legendItems generator
        const items = c.options.plugins.legend.labels.generateLabels(c);
        items.forEach((item) => {
          const li = document.createElement('li');
          li.style.marginRight = '16px';
          // Button element
          const button = document.createElement('button');
          button.style.display = 'inline-flex';
          button.style.alignItems = 'center';
          button.style.opacity = item.hidden ? '.3' : '';
          button.onclick = () => {
            c.setDatasetVisibility(item.datasetIndex, !c.isDatasetVisible(item.datasetIndex));
            c.update();
          };
          // Color box
          const box = document.createElement('span');
          box.style.display = 'block';
          box.style.width = '12px';
          box.style.height = '12px';
          box.style.borderRadius = '9999px';
          box.style.marginRight = '8px';
          box.style.borderWidth = '3px';
          box.style.borderColor = item.fillStyle;
          box.style.pointerEvents = 'none';
          // Label
          const label = document.createElement('span');
          label.classList.add('text-slate-500', 'dark:text-slate-400');
          label.style.fontSize = '0.875rem';
          label.style.lineHeight = '1.5715';
          const labelText = document.createTextNode(item.text);
          label.appendChild(labelText);
          li.appendChild(button);
          button.appendChild(box);
          button.appendChild(label);
          ul.appendChild(li);
        });
      },
    }],
  });

  document.addEventListener('darkMode', (e) => {
    const { mode } = e.detail;
    if (mode === 'on') {
      chart.options.scales.x.ticks.color = textColor.dark;
      chart.options.scales.x.grid.color = gridColor.dark;
      chart.options.scales.y.ticks.color = textColor.dark;
      chart.options.plugins.tooltip.bodyColor = tooltipBodyColor.dark;
      chart.options.plugins.tooltip.backgroundColor = tooltipBgColor.dark;
      chart.options.plugins.tooltip.borderColor = tooltipBorderColor.dark;
    } else {
      chart.options.scales.x.ticks.color = textColor.light;
      chart.options.scales.x.grid.color = gridColor.light;
      chart.options.scales.y.ticks.color = textColor.light;
      chart.options.plugins.tooltip.bodyColor = tooltipBodyColor.light;
      chart.options.plugins.tooltip.backgroundColor = tooltipBgColor.light;
      chart.options.plugins.tooltip.borderColor = tooltipBorderColor.light;
    }
    chart.update('none');
  }); 
};
analyticsCard04();

// Init #analytics-08 chart
const analyticsCard08 = () => {
  const ctx = document.getElementById('analytics-card-08');
  if (!ctx) return;

  const darkMode = localStorage.getItem('dark-mode') === 'true';

  const tooltipTitleColor = {
    light: '#1e293b',
    dark: '#f1f5f9'
  };

  const tooltipBodyColor = {
    light: '#1e293b',
    dark: '#f1f5f9'
  };

  const tooltipBgColor = {
    light: '#ffffff',
    dark: '#334155'
  };

  const tooltipBorderColor = {
    light: '#e2e8f0',
    dark: '#475569'
  }; 

  // eslint-disable-next-line no-unused-vars
  const chart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Desktop', 'Mobile', 'Tablet'],
      datasets: [
        {
          label: 'Sessions By Device',
          data: [
            12, 50, 38,
          ],
          backgroundColor: [
            '#6366f1',
            '#38bdf8',
            '#3730a3',
          ],
          hoverBackgroundColor: [
            '#4f46e5',
            '#0ea5e9',
            '#312e81',
          ],
          borderWidth: 0,
        },
      ],
    },
    options: {
      cutout: '80%',
      layout: {
        padding: 24,
      },
      plugins: {
        legend: {
          display: false,
        },
        htmlLegend: {
          // ID of the container to put the legend in
          containerID: 'analytics-card-08-legend',
        },
        tooltip: {
          titleColor: darkMode ? tooltipTitleColor.dark : tooltipTitleColor.light,
          bodyColor: darkMode ? tooltipBodyColor.dark : tooltipBodyColor.light,
          backgroundColor: darkMode ? tooltipBgColor.dark : tooltipBgColor.light,
          borderColor: darkMode ? tooltipBorderColor.dark : tooltipBorderColor.light,
        },         
      },
      interaction: {
        intersect: false,
        mode: 'nearest',
      },
      animation: {
        duration: 200,
      },
      maintainAspectRatio: false,
    },
    plugins: [{
      id: 'htmlLegend',
      afterUpdate(c, args, options) {
        const legendContainer = document.getElementById(options.containerID);
        const ul = legendContainer.querySelector('ul');
        if (!ul) return;
        // Remove old legend items
        while (ul.firstChild) {
          ul.firstChild.remove();
        }
        // Reuse the built-in legendItems generator
        const items = c.options.plugins.legend.labels.generateLabels(c);
        items.forEach((item) => {
          const li = document.createElement('li');
          li.style.margin = '4px';
          // Button element
          const button = document.createElement('button');
          button.classList.add('btn-xs', 'bg-white', 'dark:bg-slate-800', 'text-slate-500', 'dark:text-slate-400', 'border', 'border-slate-200', 'dark:border-slate-700', 'shadow-md');
          button.style.opacity = item.hidden ? '.3' : '';
          button.onclick = () => {
            c.toggleDataVisibility(item.index, !item.index);
            c.update();
          };
          // Color box
          const box = document.createElement('span');
          box.style.display = 'block';
          box.style.width = '8px';
          box.style.height = '8px';
          box.style.backgroundColor = item.fillStyle;
          box.style.borderRadius = '2px';
          box.style.marginRight = '4px';
          box.style.pointerEvents = 'none';
          // Label
          const label = document.createElement('span');
          label.style.display = 'flex';
          label.style.alignItems = 'center';
          const labelText = document.createTextNode(item.text);
          label.appendChild(labelText);
          li.appendChild(button);
          button.appendChild(box);
          button.appendChild(label);
          ul.appendChild(li);
        });
      },
    }],
  });

  document.addEventListener('darkMode', (e) => {
    const { mode } = e.detail;
    if (mode === 'on') {
      chart.options.plugins.tooltip.titleColor = tooltipTitleColor.dark;
      chart.options.plugins.tooltip.bodyColor = tooltipBodyColor.dark;
      chart.options.plugins.tooltip.backgroundColor = tooltipBgColor.dark;
      chart.options.plugins.tooltip.borderColor = tooltipBorderColor.dark;      
    } else {
      chart.options.plugins.tooltip.titleColor = tooltipTitleColor.light;
      chart.options.plugins.tooltip.bodyColor = tooltipBodyColor.light;
      chart.options.plugins.tooltip.backgroundColor = tooltipBgColor.light;
      chart.options.plugins.tooltip.borderColor = tooltipBorderColor.light;      
    }
    chart.update('none');
  }); 
};
analyticsCard08();

// Init #analytics-09 chart
const analyticsCard09 = () => {
  const ctx = document.getElementById('analytics-card-09');
  if (!ctx) return;

  const darkMode = localStorage.getItem('dark-mode') === 'true';

  const tooltipTitleColor = {
    light: '#1e293b',
    dark: '#f1f5f9'
  };

  const tooltipBodyColor = {
    light: '#1e293b',
    dark: '#f1f5f9'
  };

  const tooltipBgColor = {
    light: '#ffffff',
    dark: '#334155'
  };

  const tooltipBorderColor = {
    light: '#e2e8f0',
    dark: '#475569'
  }; 

  // eslint-disable-next-line no-unused-vars
  const chart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['<18', '18-24', '24-36', '>35'],
      datasets: [
        {
          label: 'Visit By Age Category',
          data: [
            30, 50, 5, 15,
          ],
          backgroundColor: [
            '#6366f1',
            '#38bdf8',
            '#f43f5e',
            '#10b981',
          ],
          hoverBackgroundColor: [
            '#4f46e5',
            '#0ea5e9',
            '#e11d48',
            '#059669',
          ],
          borderWidth: 0,
        },
      ],
    },
    options: {
      cutout: '80%',
      layout: {
        padding: 24,
      },
      plugins: {
        legend: {
          display: false,
        },
        htmlLegend: {
          // ID of the container to put the legend in
          containerID: 'analytics-card-09-legend',
        },
        tooltip: {
          titleColor: darkMode ? tooltipTitleColor.dark : tooltipTitleColor.light,
          bodyColor: darkMode ? tooltipBodyColor.dark : tooltipBodyColor.light,
          backgroundColor: darkMode ? tooltipBgColor.dark : tooltipBgColor.light,
          borderColor: darkMode ? tooltipBorderColor.dark : tooltipBorderColor.light,
        },         
      },
      interaction: {
        intersect: false,
        mode: 'nearest',
      },
      animation: {
        duration: 200,
      },
      maintainAspectRatio: false,
    },
    plugins: [{
      id: 'htmlLegend',
      afterUpdate(c, args, options) {
        const legendContainer = document.getElementById(options.containerID);
        const ul = legendContainer.querySelector('ul');
        if (!ul) return;
        // Remove old legend items
        while (ul.firstChild) {
          ul.firstChild.remove();
        }
        // Reuse the built-in legendItems generator
        const items = c.options.plugins.legend.labels.generateLabels(c);
        items.forEach((item) => {
          const li = document.createElement('li');
          li.style.margin = '4px';
          // Button element
          const button = document.createElement('button');
          button.classList.add('btn-xs', 'bg-white', 'dark:bg-slate-800', 'text-slate-500', 'dark:text-slate-400', 'border', 'border-slate-200', 'dark:border-slate-700', 'shadow-md');
          button.style.opacity = item.hidden ? '.3' : '';
          button.onclick = () => {
            c.toggleDataVisibility(item.index, !item.index);
            c.update();
          };
          // Color box
          const box = document.createElement('span');
          box.style.display = 'block';
          box.style.width = '8px';
          box.style.height = '8px';
          box.style.backgroundColor = item.fillStyle;
          box.style.borderRadius = '2px';
          box.style.marginRight = '4px';
          box.style.pointerEvents = 'none';
          // Label
          const label = document.createElement('span');
          label.style.display = 'flex';
          label.style.alignItems = 'center';
          const labelText = document.createTextNode(item.text);
          label.appendChild(labelText);
          li.appendChild(button);
          button.appendChild(box);
          button.appendChild(label);
          ul.appendChild(li);
        });
      },
    }],
  });

  document.addEventListener('darkMode', (e) => {
    const { mode } = e.detail;
    if (mode === 'on') {
      chart.options.plugins.tooltip.titleColor = tooltipTitleColor.dark;
      chart.options.plugins.tooltip.bodyColor = tooltipBodyColor.dark;
      chart.options.plugins.tooltip.backgroundColor = tooltipBgColor.dark;
      chart.options.plugins.tooltip.borderColor = tooltipBorderColor.dark;      
    } else {
      chart.options.plugins.tooltip.titleColor = tooltipTitleColor.light;
      chart.options.plugins.tooltip.bodyColor = tooltipBodyColor.light;
      chart.options.plugins.tooltip.backgroundColor = tooltipBgColor.light;
      chart.options.plugins.tooltip.borderColor = tooltipBorderColor.light;      
    }
    chart.update('none');
  }); 
};
analyticsCard09();

// Init #analytics-10 chart
const analyticsCard10 = () => {
  const ctx = document.getElementById('analytics-card-10');
  if (!ctx) return;

  const darkMode = localStorage.getItem('dark-mode') === 'true';

  const gridColor = {
    light: '#f1f5f9',
    dark: '#334155'
  };

  const textColor = {
    light: '#94a3b8',
    dark: '#64748B'
  };  

  const backdropColor = {
    light: '#ffffff',
    dark: '#1e293b'
  };  

  const tooltipTitleColor = {
    light: '#1e293b',
    dark: '#f1f5f9'
  };

  const tooltipBodyColor = {
    light: '#1e293b',
    dark: '#f1f5f9'
  };

  const tooltipBgColor = {
    light: '#ffffff',
    dark: '#334155'
  };

  const tooltipBorderColor = {
    light: '#e2e8f0',
    dark: '#475569'
  }; 

  // eslint-disable-next-line no-unused-vars
  const chart = new Chart(ctx, {
    type: 'polarArea',
    data: {
      labels: ['Males', 'Females', 'Unknown'],
      datasets: [
        {
          label: 'Sessions By Gender',
          data: [
            500, 326, 242,
          ],
          backgroundColor: [
            `rgba(${hexToRGB('#6366f1')}, 0.8)`,
            `rgba(${hexToRGB('#38bdf8')}, 0.8)`,
            `rgba(${hexToRGB('#10b981')}, 0.8)`,
          ],
          hoverBackgroundColor: [
            `rgba(${hexToRGB('#4f46e5')}, 0.8)`,
            `rgba(${hexToRGB('#0ea5e9')}, 0.8)`,
            `rgba(${hexToRGB('#059669')}, 0.8)`,
          ],
          borderWidth: 0,
        },
      ],
    },
    options: {
      layout: {
        padding: 24,
      },
      scales: {
        r: {
          grid: {
            color: darkMode ? gridColor.dark : gridColor.light,
          },
          ticks: {
            color: darkMode ? textColor.dark : textColor.light,
            backdropColor: darkMode ? backdropColor.dark : backdropColor.light,
          },
        },
      },      
      plugins: {
        legend: {
          display: false,
        },
        htmlLegend: {
          // ID of the container to put the legend in
          containerID: 'analytics-card-10-legend',
        },
        tooltip: {
          titleColor: darkMode ? tooltipTitleColor.dark : tooltipTitleColor.light,
          bodyColor: darkMode ? tooltipBodyColor.dark : tooltipBodyColor.light,
          backgroundColor: darkMode ? tooltipBgColor.dark : tooltipBgColor.light,
          borderColor: darkMode ? tooltipBorderColor.dark : tooltipBorderColor.light,
        },         
      },
      interaction: {
        intersect: false,
        mode: 'nearest',
      },
      animation: {
        duration: 200,
      },
      maintainAspectRatio: false,
    },
    plugins: [{
      id: 'htmlLegend',
      afterUpdate(c, args, options) {
        const legendContainer = document.getElementById(options.containerID);
        const ul = legendContainer.querySelector('ul');
        if (!ul) return;
        // Remove old legend items
        while (ul.firstChild) {
          ul.firstChild.remove();
        }
        // Reuse the built-in legendItems generator
        const items = c.options.plugins.legend.labels.generateLabels(c);
        items.forEach((item) => {
          const li = document.createElement('li');
          li.style.margin = '4px';
          // Button element
          const button = document.createElement('button');
          button.classList.add('btn-xs', 'bg-white', 'dark:bg-slate-800', 'text-slate-500', 'dark:text-slate-400', 'border', 'border-slate-200', 'dark:border-slate-700', 'shadow-md');
          button.style.opacity = item.hidden ? '.3' : '';
          button.onclick = () => {
            c.toggleDataVisibility(item.index, !item.index);
            c.update();
          };
          // Color box
          const box = document.createElement('span');
          box.style.display = 'block';
          box.style.width = '8px';
          box.style.height = '8px';
          box.style.backgroundColor = item.fillStyle;
          box.style.borderRadius = '2px';
          box.style.marginRight = '4px';
          box.style.pointerEvents = 'none';
          // Label
          const label = document.createElement('span');
          label.style.display = 'flex';
          label.style.alignItems = 'center';
          const labelText = document.createTextNode(item.text);
          label.appendChild(labelText);
          li.appendChild(button);
          button.appendChild(box);
          button.appendChild(label);
          ul.appendChild(li);
        });
      },
    }],
  });

  document.addEventListener('darkMode', (e) => {
    const { mode } = e.detail;
    if (mode === 'on') {
      chart.options.scales.r.grid.color = gridColor.dark;
      chart.options.scales.r.ticks.color = textColor.dark;
      chart.options.scales.r.ticks.backdropColor = backdropColor.dark;
      chart.options.plugins.tooltip.titleColor = tooltipTitleColor.dark;
      chart.options.plugins.tooltip.bodyColor = tooltipBodyColor.dark;
      chart.options.plugins.tooltip.backgroundColor = tooltipBgColor.dark;
      chart.options.plugins.tooltip.borderColor = tooltipBorderColor.dark;      
    } else {
      chart.options.scales.r.grid.color = gridColor.light;
      chart.options.scales.r.ticks.color = textColor.light;
      chart.options.scales.r.ticks.backdropColor = backdropColor.light;
      chart.options.plugins.tooltip.titleColor = tooltipTitleColor.light;
      chart.options.plugins.tooltip.bodyColor = tooltipBodyColor.light;
      chart.options.plugins.tooltip.backgroundColor = tooltipBgColor.light;
      chart.options.plugins.tooltip.borderColor = tooltipBorderColor.light;      
    }
    chart.update('none');
  }); 
};
analyticsCard10();    