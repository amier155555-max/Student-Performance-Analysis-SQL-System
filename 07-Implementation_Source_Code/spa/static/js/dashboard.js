// Renders each hypothesis-testing query result as a small Chart.js chart.
// Data arrives already aggregated from SQL, so this file only formats it.
(function () {
  const ACCENT = "#5C7F6C";
  const ACCENT_DARK = "#3F5B4C";
  const INK_SOFT = "#566360";
  const LINE = "#DEDACD";
  // Palette for pie / doughnut slices.
  const PALETTE = [
    "#5C7F6C", "#C08457", "#4E6E81", "#B0553F", "#8A9B6E",
    "#3F5B4C", "#D6A461", "#6D8299",
  ];

  // Safety net: if the charting library failed to load, tell the user
  // instead of leaving every chart box blank.
  if (typeof Chart === "undefined") {
    document.querySelectorAll(".chart-canvas-wrap").forEach((wrap) => {
      wrap.innerHTML =
        '<p class="muted" style="padding:12px;">Chart library could not be loaded. ' +
        "Please refresh the page (Ctrl+F5).</p>";
    });
    return;
  }

  document.querySelectorAll(".chart-canvas").forEach((canvas) => {
    let rows = [];
    try {
      rows = JSON.parse(canvas.dataset.chart || "[]");
    } catch (e) {
      return;
    }
    if (!rows.length) return;

    const kind = canvas.dataset.kind || "bar";
    const labels = rows.map((r) => String(r.category));
    const grades = rows.map((r) => r.avg_final_grade);
    const counts = rows.map((r) => r.student_count);
    const ctx = canvas.getContext("2d");

    // Pie / doughnut show the composition of students across categories.
    if (kind === "pie" || kind === "doughnut") {
      new Chart(ctx, {
        type: kind,
        data: {
          labels: labels,
          datasets: [
            {
              label: "Students",
              data: counts,
              backgroundColor: labels.map((_, i) => PALETTE[i % PALETTE.length]),
              borderColor: "#F7F4EC",
              borderWidth: 2,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: "bottom",
              labels: { color: INK_SOFT, font: { family: "IBM Plex Sans", size: 11 } },
            },
            tooltip: {
              backgroundColor: "#23302D",
              padding: 10,
              callbacks: {
                label: (c) => `${c.label}: ${c.raw} students (avg G3 ${grades[c.dataIndex]})`,
              },
            },
          },
        },
      });
      return;
    }

    // Bar / line compare the average final grade across categories.
    const chartType = kind === "line" ? "line" : "bar";
    new Chart(ctx, {
      type: chartType,
      data: {
        labels: labels,
        datasets: [
          {
            label: "Avg. final grade",
            data: grades,
            backgroundColor: chartType === "line" ? "rgba(92,127,108,0.12)" : ACCENT,
            borderColor: ACCENT_DARK,
            borderWidth: chartType === "line" ? 2 : 1,
            borderRadius: chartType === "bar" ? 6 : 0,
            tension: 0.35,
            fill: chartType === "line",
            pointBackgroundColor: ACCENT_DARK,
            maxBarThickness: 46,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#23302D",
            padding: 10,
            callbacks: {
              afterLabel: (ctx) => `n = ${counts[ctx.dataIndex]} students`,
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: INK_SOFT, font: { family: "IBM Plex Sans", size: 11 } },
          },
          y: {
            beginAtZero: true,
            max: 20,
            grid: { color: LINE },
            ticks: { color: INK_SOFT, font: { family: "IBM Plex Sans", size: 11 } },
          },
        },
      },
    });
  });

  // Generic-file per-column charts: data is {x_label, y_label, labels, values}.
  document.querySelectorAll(".gchart-canvas").forEach((canvas) => {
    let spec = {};
    try {
      spec = JSON.parse(canvas.dataset.chart || "{}");
    } catch (e) {
      return;
    }
    const labels = spec.labels || [];
    const values = spec.values || [];
    if (!labels.length) return;
    const type = spec.type || "bar";
    const ctx = canvas.getContext("2d");

    if (type === "pie" || type === "doughnut") {
      new Chart(ctx, {
        type: type,
        data: {
          labels: labels,
          datasets: [
            {
              label: spec.y_label || "Count",
              data: values,
              backgroundColor: labels.map((_, i) => PALETTE[i % PALETTE.length]),
              borderColor: "#F7F4EC",
              borderWidth: 2,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: "bottom",
              labels: { color: INK_SOFT, font: { family: "IBM Plex Sans", size: 11 } },
            },
            tooltip: { backgroundColor: "#23302D", padding: 10 },
          },
        },
      });
      return;
    }

    new Chart(ctx, {
      type: type,
      data: {
        labels: labels,
        datasets: [
          {
            label: spec.y_label || "Value",
            data: values,
            backgroundColor: ACCENT,
            borderColor: ACCENT_DARK,
            borderWidth: 1,
            borderRadius: 6,
            maxBarThickness: 46,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { backgroundColor: "#23302D", padding: 10 },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: INK_SOFT, font: { family: "IBM Plex Sans", size: 11 } },
          },
          y: {
            beginAtZero: true,
            grid: { color: LINE },
            ticks: { color: INK_SOFT, font: { family: "IBM Plex Sans", size: 11 } },
          },
        },
      },
    });
  });
})();
