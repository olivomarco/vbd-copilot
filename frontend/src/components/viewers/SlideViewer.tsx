import { useEffect, useState, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  Text,
  Button,
  Spinner,
} from "@fluentui/react-components";
import {
  ArrowLeft20Regular,
  ArrowDownload20Regular,
  Delete20Regular,
} from "@fluentui/react-icons";
import { previewPptx, previewPptxHifi } from "@/api/client";
import type { PptxSlide } from "@/api/types";

export function SlideViewer() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const path = params.get("path") || "";
  const fileName = path.split("/").pop() || "Presentation";

  const [slides, setSlides] = useState<PptxSlide[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    if (!path) return;
    setLoading(true);
    // Try high-fidelity first; if it returns fewer than 2 slides
    // (LibreOffice produces a single composite image), fall back to basic
    previewPptxHifi(path, 960)
      .then((r) => (r.total >= 2 ? r : previewPptx(path, 960)))
      .catch(() => previewPptx(path, 960))
      .then((r) => {
        setSlides(r.slides);
        setCurrent(0);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, [path]);

  const goTo = useCallback(
    (idx: number) => {
      if (idx >= 0 && idx < slides.length) setCurrent(idx);
    },
    [slides.length],
  );

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") goTo(current - 1);
      else if (e.key === "ArrowRight") goTo(current + 1);
      else if (e.key === "Escape") navigate("/library");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [current, goTo, navigate]);

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 80 }}>
        <Spinner label="Loading slides..." size="large" />
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

  const slide = slides[current];

  return (
    <div style={{ padding: "24px 48px", maxWidth: 1200, margin: "0 auto" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 20,
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
          <Text weight="semibold" size={500}>{fileName.replace(/\.pptx$/i, "")}</Text>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Button
            appearance="primary"
            icon={<ArrowDownload20Regular />}
            onClick={() => {
              const a = document.createElement("a");
              a.href = `/file/download?path=${encodeURIComponent(path)}`;
              a.download = fileName;
              a.click();
            }}
          >
            Download .pptx
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

      {/* Thumbnail strip */}
      <div
        style={{
          display: "flex",
          gap: 10,
          overflowX: "auto",
          paddingBottom: 12,
          marginBottom: 20,
          scrollSnapType: "x mandatory",
        }}
        className="hide-scrollbar"
      >
        {slides.map((s, i) => (
          <button
            key={i}
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setCurrent(i);
            }}
            style={{
              flex: "0 0 auto",
              width: 130,
              height: 74,
              borderRadius: 8,
              border: i === current
                ? "3px solid var(--brand-primary)"
                : "2px solid var(--border)",
              overflow: "hidden",
              cursor: "pointer",
              opacity: i === current ? 1 : 0.65,
              transition: "all 0.15s ease",
              position: "relative",
              background: "#12121a",
              padding: 0,
              scrollSnapAlign: "start",
              outline: "none",
            }}
            onMouseEnter={(e) => {
              if (i !== current) (e.currentTarget as HTMLElement).style.opacity = "0.9";
            }}
            onMouseLeave={(e) => {
              if (i !== current) (e.currentTarget as HTMLElement).style.opacity = "0.65";
            }}
            aria-label={`Slide ${i + 1}${s.title ? `: ${s.title}` : ""}`}
          >
            {s.png_base64 ? (
              <img
                src={`data:image/png;base64,${s.png_base64}`}
                alt={`Slide ${i + 1}`}
                style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
              />
            ) : (
              <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <span style={{ color: "#888", fontSize: 11, fontWeight: 500 }}>{s.title || `Slide ${i + 1}`}</span>
              </div>
            )}
            <div
              style={{
                position: "absolute",
                bottom: 3,
                right: 5,
                fontSize: 10,
                color: "#fff",
                fontWeight: 700,
                textShadow: "0 1px 3px rgba(0,0,0,0.9)",
                background: "rgba(0,0,0,0.4)",
                borderRadius: 4,
                padding: "1px 5px",
              }}
            >
              {i + 1}
            </div>
          </button>
        ))}
      </div>

      {/* Main slide view */}
      {slide && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div
            style={{
              border: "1px solid var(--border)",
              borderRadius: 12,
              overflow: "hidden",
              position: "relative",
              aspectRatio: `${slide.width} / ${slide.height}`,
              background: "#12121a",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {slide.png_base64 ? (
              <img
                src={`data:image/png;base64,${slide.png_base64}`}
                alt={`Slide ${current + 1}`}
                style={{ width: "100%", height: "100%", objectFit: "contain" }}
              />
            ) : (
              <div style={{ padding: 40, textAlign: "center", color: "#888" }}>
                {slide.title && (
                  <Text
                    size={700}
                    weight="bold"
                    style={{ display: "block", color: "#fff", marginBottom: 16 }}
                  >
                    {slide.title}
                  </Text>
                )}
                {slide.body_preview && (
                  <Text
                    size={400}
                    style={{ color: "#ccc", whiteSpace: "pre-line" }}
                  >
                    {slide.body_preview}
                  </Text>
                )}
              </div>
            )}

            {/* Navigation arrows — plain buttons for guaranteed clickability */}
            {current > 0 && (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); goTo(current - 1); }}
                style={{
                  position: "absolute",
                  left: 12,
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "rgba(0,0,0,0.6)",
                  color: "#fff",
                  border: "none",
                  borderRadius: "50%",
                  width: 44,
                  height: 44,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 20,
                  zIndex: 5,
                }}
                aria-label="Previous slide"
              >
                ‹
              </button>
            )}
            {current < slides.length - 1 && (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); goTo(current + 1); }}
                style={{
                  position: "absolute",
                  right: 12,
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "rgba(0,0,0,0.6)",
                  color: "#fff",
                  border: "none",
                  borderRadius: "50%",
                  width: 44,
                  height: 44,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 20,
                  zIndex: 5,
                }}
                aria-label="Next slide"
              >
                ›
              </button>
            )}

            {/* Slide counter */}
            <div
              style={{
                position: "absolute",
                bottom: 12,
                right: 16,
                background: "rgba(0,0,0,0.6)",
                color: "#fff",
                padding: "4px 10px",
                borderRadius: 12,
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              {current + 1} / {slides.length}
            </div>
          </div>

          {/* Speaker Notes */}
          {slide.notes && (
            <div
              style={{
                border: "1px solid var(--border)",
                borderRadius: 10,
                padding: "16px 20px",
                background: "var(--card-bg)",
              }}
            >
              <Text
                weight="semibold"
                size={300}
                style={{
                  display: "block",
                  marginBottom: 8,
                  color: "var(--text-secondary)",
                  textTransform: "uppercase",
                  fontSize: 11,
                  letterSpacing: "0.04em",
                }}
              >
                Speaker Notes
              </Text>
              <Text
                size={300}
                style={{
                  whiteSpace: "pre-line",
                  lineHeight: 1.6,
                  color: "var(--text-primary)",
                }}
              >
                {slide.notes}
              </Text>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
