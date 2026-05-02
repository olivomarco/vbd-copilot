import { useEffect, useState, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  Text,
  Button,
  Spinner,
  Card,
} from "@fluentui/react-components";
import {
  ArrowLeft20Regular,
  ArrowDownload20Regular,
  Delete20Regular,
} from "@fluentui/react-icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { readFile } from "@/api/client";

function extractToc(markdown: string): Array<{ level: number; text: string; id: string }> {
  const toc: Array<{ level: number; text: string; id: string }> = [];
  const lines = markdown.split("\n");
  for (const line of lines) {
    const m = line.match(/^(#{1,4})\s+(.+)/);
    if (m) {
      const text = m[2].replace(/[*_`]/g, "");
      const id = text
        .toLowerCase()
        .replace(/[^\w\s-]/g, "")
        .replace(/\s+/g, "-");
      toc.push({ level: m[1].length, text, id });
    }
  }
  return toc;
}

export function MarkdownViewer() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const path = params.get("path") || "";
  const fileName = path.split("/").pop() || "Document";

  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!path) return;
    setLoading(true);
    readFile(path)
      .then((r) => {
        setContent(r.content);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, [path]);

  // Escape to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") navigate("/library");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [navigate]);

  // Strip HTML comments so they aren't rendered as visible text
  const cleaned = useMemo(() => content.replace(/<!--[\s\S]*?-->/g, ""), [content]);
  const toc = useMemo(() => extractToc(cleaned), [cleaned]);

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 80 }}>
        <Spinner label="Loading document..." size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 48 }}>
        <Text style={{ color: "#d13438" }}>Error: {error}</Text>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      {/* TOC Sidebar */}
      {toc.length > 2 && (
        <div
          style={{
            width: 240,
            borderRight: "1px solid var(--border)",
            padding: "24px 0 24px 16px",
            overflowY: "auto",
            flexShrink: 0,
            background: "var(--card-bg)",
          }}
        >
          <Text
            weight="semibold"
            size={200}
            style={{
              display: "block",
              marginBottom: 12,
              color: "var(--text-secondary)",
              textTransform: "uppercase",
              fontSize: 10,
              letterSpacing: "0.06em",
              paddingLeft: 8,
            }}
          >
            Contents
          </Text>
          {toc.map((item, i) => (
            <a
              key={i}
              href={`#${item.id}`}
              style={{
                display: "block",
                padding: "4px 8px",
                paddingLeft: 8 + (item.level - 1) * 14,
                color: "var(--text-primary)",
                textDecoration: "none",
                fontSize: 13,
                lineHeight: 1.5,
                borderRadius: 4,
                transition: "background 0.1s",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.background = "var(--border-subtle)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.background = "transparent";
              }}
            >
              {item.text}
            </a>
          ))}
        </div>
      )}

      {/* Main content */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "20px 40px",
            borderBottom: "1px solid var(--border)",
            background: "var(--card-bg)",
            position: "sticky",
            top: 0,
            zIndex: 10,
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
            <Text weight="semibold" size={400}>
              {fileName}
            </Text>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Button
              appearance="primary"
              icon={<ArrowDownload20Regular />}
              onClick={() => {
                const blob = new Blob([content], { type: "text/markdown" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = fileName;
                a.click();
                URL.revokeObjectURL(url);
              }}
            >
              Download
            </Button>
            <Button
              appearance="subtle"
              icon={<Delete20Regular />}
              onClick={async () => {
                if (!confirm(`Delete "${fileName}"? This cannot be undone.`)) return;
                try {
                  await fetch(`/outputs?path=${encodeURIComponent(path)}`, { method: "DELETE" });
                  navigate("/library");
                } catch (e) {
                  alert("Failed to delete");
                }
              }}
              style={{ color: "#d13438" }}
            >
              Delete
            </Button>
          </div>
        </div>

        {/* Rendered Markdown */}
        <div
          className="md-content"
          style={{
            padding: "32px 48px 80px",
            maxWidth: 840,
            margin: "0 auto",
          }}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeHighlight]}
            components={{
              // Add IDs to headings for TOC linking
              h1: ({ children, ...props }) => {
                const text = String(children);
                const id = text
                  .toLowerCase()
                  .replace(/[^\w\s-]/g, "")
                  .replace(/\s+/g, "-");
                return <h1 id={id} {...props}>{children}</h1>;
              },
              h2: ({ children, ...props }) => {
                const text = String(children);
                const id = text
                  .toLowerCase()
                  .replace(/[^\w\s-]/g, "")
                  .replace(/\s+/g, "-");
                return <h2 id={id} {...props}>{children}</h2>;
              },
              h3: ({ children, ...props }) => {
                const text = String(children);
                const id = text
                  .toLowerCase()
                  .replace(/[^\w\s-]/g, "")
                  .replace(/\s+/g, "-");
                return <h3 id={id} {...props}>{children}</h3>;
              },
              // Code copy button
              pre: ({ children, ...props }) => (
                <div style={{ position: "relative" }}>
                  <pre {...props}>{children}</pre>
                  <button
                    onClick={() => {
                      const el = (props as any).ref?.current;
                      const text =
                        el?.textContent ||
                        (children as any)?.props?.children ||
                        "";
                      navigator.clipboard.writeText(String(text));
                    }}
                    style={{
                      position: "absolute",
                      top: 8,
                      right: 8,
                      background: "rgba(255,255,255,0.1)",
                      border: "1px solid rgba(255,255,255,0.2)",
                      borderRadius: 4,
                      color: "#ccc",
                      padding: "4px 8px",
                      fontSize: 11,
                      cursor: "pointer",
                    }}
                  >
                    Copy
                  </button>
                </div>
              ),
            }}
          >
            {cleaned}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
