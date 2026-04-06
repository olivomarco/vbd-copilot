import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Button, Spinner, Text } from "@fluentui/react-components";
import { ArrowLeft20Regular, ArrowDownload20Regular } from "@fluentui/react-icons";
import { readFile } from "@/api/client";
import { DrawioRenderer } from "./DrawioRenderer";

export function DrawioViewer() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const filePath = params.get("path") || "";

  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fileName = filePath.split("/").pop() || "diagram.drawio";

  useEffect(() => {
    if (!filePath) return;
    setLoading(true);
    readFile(filePath)
      .then((r) => {
        setContent(r.content);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message || "Failed to load file");
        setLoading(false);
      });
  }, [filePath]);

  // Escape to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") navigate("/library");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [navigate]);

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 80 }}>
        <Spinner label="Loading diagram..." size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: 80, gap: 16 }}>
        <Text size={400}>Failed to load diagram</Text>
        <Text size={200} style={{ color: "var(--text-secondary)" }}>{error}</Text>
        <Button appearance="primary" onClick={() => navigate("/library")}>
          Back to Library
        </Button>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 24px",
          borderBottom: "1px solid var(--border)",
          background: "var(--card-bg)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Button
            appearance="subtle"
            icon={<ArrowLeft20Regular />}
            onClick={() => navigate("/library")}
          >
            Back to Library
          </Button>
          <Text size={300} style={{ color: "var(--text-secondary)" }}>
            {fileName}
          </Text>
        </div>
        <Button
          appearance="subtle"
          icon={<ArrowDownload20Regular />}
          size="small"
          onClick={async () => {
            try {
              const res = await fetch(`/file/download?path=${encodeURIComponent(filePath)}`);
              if (!res.ok) throw new Error(`HTTP ${res.status}`);
              const blob = await res.blob();
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = fileName;
              a.click();
              URL.revokeObjectURL(url);
            } catch (e: any) {
              alert(`Download failed: ${e.message}`);
            }
          }}
        >
          Download
        </Button>
      </div>

      {/* Diagram */}
      <div style={{ flex: 1 }}>
        <DrawioRenderer xml={content} />
      </div>
    </div>
  );
}
