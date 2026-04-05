import { useEffect, useCallback, useState, useRef } from "react";
import { Text, Button } from "@fluentui/react-components";
import {
  ArrowRight16Regular,
  ArrowLeft16Regular,
  Dismiss16Regular,
  Checkmark16Regular,
} from "@fluentui/react-icons";
import { useTutorialStore } from "@/stores/tutorialStore";
import { TUTORIAL_STEPS, type TutorialStep } from "./tutorialSteps";

/* ── Spotlight + Tooltip Positions ──────────────────────────────────── */

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

function getElementRect(selector: string): Rect | null {
  const el = document.querySelector(selector);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { top: r.top, left: r.left, width: r.width, height: r.height };
}

const PADDING = 8;
const CARD_W = 360;
const CARD_H_APPROX = 180;
const GAP = 16;

function computeTooltipPosition(
  rect: Rect | null,
  placement: TutorialStep["placement"],
): React.CSSProperties {
  if (!rect || placement === "center") {
    return {
      top: "50%",
      left: "50%",
      transform: "translate(-50%, -50%)",
    };
  }

  const { top, left, width, height } = rect;
  const vw = window.innerWidth;
  const vh = window.innerHeight;

  let style: React.CSSProperties = {};

  switch (placement) {
    case "right":
      style = {
        top: Math.max(16, Math.min(top + height / 2 - CARD_H_APPROX / 2, vh - CARD_H_APPROX - 16)),
        left: Math.min(left + width + GAP + PADDING, vw - CARD_W - 16),
      };
      break;
    case "left":
      style = {
        top: Math.max(16, Math.min(top + height / 2 - CARD_H_APPROX / 2, vh - CARD_H_APPROX - 16)),
        left: Math.max(16, left - CARD_W - GAP - PADDING),
      };
      break;
    case "bottom":
      style = {
        top: Math.min(top + height + GAP + PADDING, vh - CARD_H_APPROX - 16),
        left: Math.max(16, Math.min(left + width / 2 - CARD_W / 2, vw - CARD_W - 16)),
      };
      break;
    case "top":
      style = {
        top: Math.max(16, top - CARD_H_APPROX - GAP - PADDING),
        left: Math.max(16, Math.min(left + width / 2 - CARD_W / 2, vw - CARD_W - 16)),
      };
      break;
  }

  return style;
}

/* ── Component ─────────────────────────────────────────────────────── */

export function GuidedTutorial() {
  const { active, currentStep, next, prev, finish, skip } = useTutorialStore();
  const [targetRect, setTargetRect] = useState<Rect | null>(null);
  const overlayRef = useRef<HTMLDivElement>(null);

  const step = TUTORIAL_STEPS[currentStep];
  const isFirst = currentStep === 0;
  const isLast = currentStep === TUTORIAL_STEPS.length - 1;

  // Measure the target element
  const measure = useCallback(() => {
    if (!active || !step) return;
    if (!step.target) {
      setTargetRect(null);
      return;
    }
    const rect = getElementRect(step.target);
    setTargetRect(rect);
  }, [active, step]);

  useEffect(() => {
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [measure]);

  // Keyboard navigation
  useEffect(() => {
    if (!active) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        skip();
      } else if (e.key === "ArrowRight" || e.key === "Enter") {
        if (isLast) finish();
        else next();
      } else if (e.key === "ArrowLeft") {
        prev();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [active, isLast, next, prev, finish, skip]);

  if (!active || !step) return null;

  const spotlightPad = PADDING;
  const hasTarget = step.target && targetRect;
  const tooltipStyle = computeTooltipPosition(targetRect, step.placement);
  const color = step.color || "#0078D4";

  return (
    <div
      ref={overlayRef}
      className="tutorial-overlay"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 10000,
      }}
    >
      {/* Darkened overlay with spotlight cutout */}
      <svg
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
        onClick={skip}
      >
        <defs>
          <mask id="tutorial-spotlight-mask">
            <rect width="100%" height="100%" fill="white" />
            {hasTarget && (
              <rect
                x={targetRect.left - spotlightPad}
                y={targetRect.top - spotlightPad}
                width={targetRect.width + spotlightPad * 2}
                height={targetRect.height + spotlightPad * 2}
                rx={12}
                ry={12}
                fill="black"
              />
            )}
          </mask>
        </defs>
        <rect
          width="100%"
          height="100%"
          fill="rgba(0, 0, 0, 0.55)"
          mask="url(#tutorial-spotlight-mask)"
        />
      </svg>

      {/* Spotlight ring glow */}
      {hasTarget && (
        <div
          className="tutorial-spotlight-ring"
          style={{
            position: "absolute",
            top: targetRect.top - spotlightPad - 2,
            left: targetRect.left - spotlightPad - 2,
            width: targetRect.width + (spotlightPad + 2) * 2,
            height: targetRect.height + (spotlightPad + 2) * 2,
            borderRadius: 14,
            border: `2px solid ${color}`,
            boxShadow: `0 0 20px 4px ${color}40`,
            pointerEvents: "none",
          }}
        />
      )}

      {/* Tooltip card */}
      <div
        className="tutorial-card animate-in"
        key={currentStep}
        style={{
          position: "absolute",
          ...tooltipStyle,
          width: CARD_W,
          background: "var(--card-bg, #fff)",
          borderRadius: 16,
          boxShadow: `0 20px 60px rgba(0, 0, 0, 0.25), 0 0 0 1px ${color}30`,
          overflow: "hidden",
          zIndex: 10001,
        }}
      >
        {/* Top accent bar */}
        <div style={{ height: 4, background: color }} />

        <div style={{ padding: "24px 28px 20px" }}>
          {/* Step counter */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 12,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  background: color,
                  color: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 13,
                  fontWeight: 700,
                }}
              >
                {currentStep + 1}
              </div>
              <Text
                size={100}
                style={{ color: "var(--text-secondary)", fontWeight: 500 }}
              >
                of {TUTORIAL_STEPS.length}
              </Text>
            </div>

            {/* Skip / Close */}
            {!isLast && (
              <Button
                appearance="transparent"
                size="small"
                icon={<Dismiss16Regular />}
                onClick={skip}
                style={{ color: "var(--text-secondary)", minWidth: 0 }}
              >
                Skip
              </Button>
            )}
          </div>

          {/* Title */}
          <Text
            weight="bold"
            size={500}
            style={{
              display: "block",
              marginBottom: 8,
              letterSpacing: "-0.01em",
              color: "var(--text-primary)",
            }}
          >
            {step.title}
          </Text>

          {/* Description */}
          <Text
            size={300}
            style={{
              display: "block",
              lineHeight: 1.6,
              color: "var(--text-secondary)",
              marginBottom: 20,
            }}
          >
            {step.description}
          </Text>

          {/* Progress dots */}
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              gap: 6,
              marginBottom: 16,
            }}
          >
            {TUTORIAL_STEPS.map((_, i) => (
              <div
                key={i}
                style={{
                  width: i === currentStep ? 20 : 8,
                  height: 8,
                  borderRadius: 4,
                  background:
                    i === currentStep
                      ? color
                      : i < currentStep
                        ? `${color}60`
                        : "var(--border)",
                  transition: "all 0.3s ease",
                }}
              />
            ))}
          </div>

          {/* Navigation buttons */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <Button
              appearance="subtle"
              size="small"
              icon={<ArrowLeft16Regular />}
              onClick={prev}
              disabled={isFirst}
              style={{ visibility: isFirst ? "hidden" : "visible" }}
            >
              Back
            </Button>

            {isLast ? (
              <Button
                appearance="primary"
                icon={<Checkmark16Regular />}
                onClick={finish}
                style={{
                  background: color,
                  borderColor: color,
                }}
              >
                Done
              </Button>
            ) : (
              <Button
                appearance="primary"
                icon={<ArrowRight16Regular />}
                iconPosition="after"
                onClick={next}
                style={{
                  background: color,
                  borderColor: color,
                }}
              >
                Next
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
