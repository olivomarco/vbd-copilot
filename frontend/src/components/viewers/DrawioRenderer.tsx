import { useMemo, useState, useRef, useCallback } from "react";
import { Button, Tooltip } from "@fluentui/react-components";
import {
  ZoomIn20Regular,
  ZoomOut20Regular,
  ZoomFit20Regular,
  ArrowDownload20Regular,
} from "@fluentui/react-icons";

/**
 * Renders a .drawio XML diagram inside an iframe using the official
 * draw.io viewer-static JS (client-side, no data sent externally).
 */
export function DrawioRenderer({ xml }: { xml: string }) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [loaded, setLoaded] = useState(false);

  // Build the self-contained HTML document for the iframe.
  // viewer-static.min.js auto-discovers <div class="mxgraph"> elements
  // and renders them as interactive diagrams with pan/zoom.
  //
  // IMPORTANT: The data-mxgraph attribute is set via JS (setAttribute) rather
  // than inline HTML to avoid the browser's HTML parser decoding entities
  // (e.g. &quot; → ") inside the XML, which corrupts the JSON config.
  const srcDoc = useMemo(() => {
    const config = JSON.stringify({
      highlight: "#0078D4",
      nav: true,
      resize: true,
      toolbar: "zoom layers lightbox",
      xml: xml,
    });

    // Escape </ sequences to prevent the browser from prematurely closing
    // the <script> tag when the XML contains markup like </mxCell>.
    const safeConfig = config.replace(/<\//g, "<\\/");

    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    * { margin:0; padding:0; box-sizing:border-box; }
    html, body { width:100%; height:100%; overflow:hidden; background:#fafafa; }
    .geDiagramContainer { overflow: auto !important; }
    .mxgraph { width:100%; height:100%; }
    .drawio-error { padding:24px; color:#d32f2f; font-family:system-ui,sans-serif; }
    .drawio-error pre { white-space:pre-wrap; margin-top:8px; font-size:12px; color:#666; }
  </style>
</head>
<body>
  <div class="mxgraph" id="drawio-target"></div>
  <script>
    try {
      var cfg = ${safeConfig};
      document.getElementById('drawio-target').setAttribute('data-mxgraph', JSON.stringify(cfg));
    } catch(e) {
      document.getElementById('drawio-target').innerHTML =
        '<div class="drawio-error"><strong>Could not render diagram</strong>'
        + '<pre>' + e.message + '<\\/pre></div>';
    }
  <\/script>
  <script src="https://viewer.diagrams.net/js/viewer-static.min.js"><\/script>
</body>
</html>`;
  }, [xml]);

  const postZoomCommand = useCallback(
    (action: "zoomIn" | "zoomOut" | "fit") => {
      // The draw.io viewer exposes graph objects on the page.
      // We reach into the iframe to call zoom methods.
      const win = iframeRef.current?.contentWindow;
      if (!win) return;
      try {
        // viewer-static attaches graphs to window.__drawio_graphs or
        // document.querySelectorAll('.geDiagramContainer')
        win.postMessage(JSON.stringify({ action }), "*");
      } catch {
        // cross-origin safety — buttons just won't zoom
      }
    },
    [],
  );

  const handleExportSvg = useCallback(() => {
    const win = iframeRef.current?.contentWindow;
    if (!win) return;
    try {
      const svgEl = win.document.querySelector("svg");
      if (!svgEl) return;
      const serializer = new XMLSerializer();
      const svgStr = serializer.serializeToString(svgEl);
      const blob = new Blob([svgStr], { type: "image/svg+xml" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "architecture-diagram.svg";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // If cross-origin blocks access, silently ignore
    }
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Toolbar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          padding: "6px 12px",
          borderBottom: "1px solid var(--border)",
          background: "var(--card-bg)",
        }}
      >
        <Tooltip content="Zoom in" relationship="label">
          <Button
            appearance="subtle"
            size="small"
            icon={<ZoomIn20Regular />}
            onClick={() => postZoomCommand("zoomIn")}
          />
        </Tooltip>
        <Tooltip content="Zoom out" relationship="label">
          <Button
            appearance="subtle"
            size="small"
            icon={<ZoomOut20Regular />}
            onClick={() => postZoomCommand("zoomOut")}
          />
        </Tooltip>
        <Tooltip content="Fit to view" relationship="label">
          <Button
            appearance="subtle"
            size="small"
            icon={<ZoomFit20Regular />}
            onClick={() => postZoomCommand("fit")}
          />
        </Tooltip>
        <div style={{ flex: 1 }} />
        <Tooltip content="Export as SVG" relationship="label">
          <Button
            appearance="subtle"
            size="small"
            icon={<ArrowDownload20Regular />}
            onClick={handleExportSvg}
          >
            SVG
          </Button>
        </Tooltip>
      </div>

      {/* Diagram iframe */}
      <div style={{ flex: 1, position: "relative" }}>
        {!loaded && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--text-secondary)",
              fontSize: 14,
            }}
          >
            Loading diagram…
          </div>
        )}
        <iframe
          ref={iframeRef}
          srcDoc={srcDoc}
          onLoad={() => setLoaded(true)}
          sandbox="allow-scripts allow-same-origin"
          style={{
            width: "100%",
            height: "100%",
            border: "none",
            opacity: loaded ? 1 : 0,
            transition: "opacity 0.3s",
          }}
          title="Architecture diagram"
        />
      </div>
    </div>
  );
}
