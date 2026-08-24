(function () {
  "use strict";

  const readouts = {
    "orientation-map-graph": "orientation-cursor-readout",
    "stereo-plot-graph": "stereo-cursor-readout",
  };

  function formatCoordinate(value) {
    const number = Number(value);
    return Number.isFinite(number)
      ? Number(number.toPrecision(6)).toString()
      : "—";
  }

  function updateReadout(readoutId, eventData) {
    const readout = document.getElementById(readoutId);
    if (!readout || !eventData) return;

    let x;
    let y;
    if (eventData.xvals && eventData.xvals.length && eventData.yvals && eventData.yvals.length) {
      [x] = eventData.xvals;
      [y] = eventData.yvals;
    } else if (eventData.points && eventData.points.length) {
      [{x, y}] = eventData.points;
    } else {
      return;
    }

    readout.textContent = `x: ${formatCoordinate(x)}   y: ${formatCoordinate(y)}`;
  }

  function bindReadouts() {
    Object.entries(readouts).forEach(([graphId, readoutId]) => {
      const graph = document.getElementById(graphId);
      const plot = graph && (
        graph.matches(".js-plotly-plot") ? graph : graph.querySelector(".js-plotly-plot")
      );
      if (!plot || typeof plot.on !== "function" || plot.dataset.cursorReadoutBound) return;

      plot.dataset.cursorReadoutBound = "true";
      plot.on("plotly_hover", eventData => updateReadout(readoutId, eventData));
    });
  }

  const observer = new MutationObserver(bindReadouts);
  observer.observe(document.documentElement, {childList: true, subtree: true});
  window.addEventListener("load", bindReadouts);
  bindReadouts();
})();
